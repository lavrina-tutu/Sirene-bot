"""Typed write API для core plan_*-таблиц Фазы 1 (P1.SCHEMA.4, R-026/R-016).

Каждая публичная функция принимает dataclass-параметры (не свободный SQL),
возвращает непрозрачные IDs, и выполняет ровно одну короткую транзакцию.
Повтор с тем же PK (``attempt_id``/``event_id``/``plan_id`` через
``project_slug``) идемпотентен — не плодит дубликаты.

Все соединения, пишущие ``plan_*``, обязаны быть открыты через
``mofs_index.db.connect_durable()`` (WAL+FULL, см. ``db.py::connect()``
docstring) — эта проверка не выполняется здесь автоматически (вызывающая
сторона отвечает за выбор соединения), но ни одна функция этого модуля не
переключает ``PRAGMA synchronous``.
"""
from __future__ import annotations

import json
import hashlib
import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from .migrate import ensure_plan_schema


class PlanWriterError(RuntimeError):
    """Нарушение инварианта writer-уровня (не просто SQL-ошибка)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


# ─────────────────────────────────────────────────────────────────────────
# plan / plan_lineage
# ─────────────────────────────────────────────────────────────────────────


def ensure_plan(
    conn: sqlite3.Connection,
    project_slug: str,
    *,
    name: str | None = None,
    md_path: str | None = None,
    default_target: str | None = None,
    default_representation: str | None = None,
) -> str:
    """Вернуть ``plan_id`` для ``project_slug``, создав запись при отсутствии.

    Идемпотентна: повторный вызов с тем же ``project_slug`` возвращает тот же
    ``plan_id`` и не создаёт вторую строку (UQ(project_slug), R-015).
    """
    ensure_plan_schema(conn)
    with _transaction(conn):
        row = conn.execute(
            "SELECT plan_id FROM plan WHERE project_slug = ?", (project_slug,)
        ).fetchone()
        if row:
            return row[0]
        plan_id = _new_id("plan")
        conn.execute(
            "INSERT INTO plan(plan_id, project_slug, name, md_path, "
            "default_target, default_representation, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (plan_id, project_slug, name, md_path, default_target,
             default_representation, _now()),
        )
        return plan_id

def ensure_lineage(
    conn: sqlite3.Connection,
    plan_id: str,
    source_namespace: str,
    *,
    page_id: str | None = None,
    basis: str = "explicit",
) -> str:
    """Вернуть ``lineage_id`` для (plan_id, source_namespace, page_id).

    Новая копия НЕ продолжает линию автоматически (R-015) — отдельный
    ``page_id``/``source_namespace`` всегда даёт новую линию; идемпотентность
    только по точному совпадению ключа UQ.
    """
    with _transaction(conn):
        row = conn.execute(
            "SELECT lineage_id FROM plan_lineage "
            "WHERE plan_id = ? AND source_namespace = ? AND page_id IS ?",
            (plan_id, source_namespace, page_id),
        ).fetchone()
        if row:
            return row[0]
        lineage_id = _new_id("lineage")
        conn.execute(
            "INSERT INTO plan_lineage(lineage_id, plan_id, source_namespace, "
            "page_id, basis, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (lineage_id, plan_id, source_namespace, page_id, basis, _now()),
        )
        return lineage_id


# ─────────────────────────────────────────────────────────────────────────
# plan_artifact
# ─────────────────────────────────────────────────────────────────────────

def record_artifact(
    conn: sqlite3.Connection,
    raw_sha256: str,
    kind: str,
    path: str,
    *,
    format: str | None = None,
    size_bytes: int | None = None,
) -> str:
    """Зарегистрировать content-addressed артефакт. Дедупликация по hash:
    повторная запись того же ``raw_sha256`` возвращает существующий
    ``artifact_id``, не создаёт вторую копию/строку."""
    with _transaction(conn):
        row = conn.execute(
            "SELECT artifact_id FROM plan_artifact WHERE raw_sha256 = ?",
            (raw_sha256,),
        ).fetchone()
        if row:
            return row[0]
        artifact_id = _new_id("artifact")
        conn.execute(
            "INSERT INTO plan_artifact(artifact_id, raw_sha256, kind, format, "
            "size_bytes, path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (artifact_id, raw_sha256, kind, format, size_bytes, path, _now()),
        )
        return artifact_id

# ─────────────────────────────────────────────────────────────────────────
# plan_import_attempt / plan_attempt_event (P1.SCHEMA.4)
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AttemptSpec:
    plan_id: str
    lineage_id: str | None = None
    source_namespace: str | None = None
    range_from: str | None = None
    range_to: str | None = None
    prepared_sha256: str | None = None
    attempt_id: str | None = None


def begin_attempt(conn: sqlite3.Connection, spec: AttemptSpec) -> str:
    """Зафиксировать подготовленную попытку записи **до** первого POST/PUT
    (R-009 п.5). Повтор с тем же ``attempt_id`` идемпотентен (не создаёт
    вторую строку).
    """
    attempt_id = spec.attempt_id or _new_id("attempt")
    existing = conn.execute(
        "SELECT attempt_id FROM plan_import_attempt WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()
    if existing:
        return attempt_id
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_import_attempt(attempt_id, plan_id, lineage_id, "
            "source_namespace, range_from, range_to, prepared_sha256, status, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'prepared', ?)",
            (attempt_id, spec.plan_id, spec.lineage_id, spec.source_namespace,
             spec.range_from, spec.range_to, spec.prepared_sha256, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return attempt_id


VALID_STAGES = frozenset({
    "archive", "page_create", "attachment_post", "attachment_verify",
    "storage_put", "storage_verify", "projection",
})
VALID_EVENT_STATUSES = frozenset({
    "not_started", "prepared", "confirmed", "failed",
    "unknown", "conflict", "not_applicable",
})


def record_event(
    conn: sqlite3.Connection,
    attempt_id: str,
    stage: str,
    status: str,
    *,
    event_id: str | None = None,
    detail: str | None = None,
) -> str:
    """Добавить append-only событие попытки (R-010). Идемпотентна по PK
    ``event_id`` — повтор с тем же ``event_id`` не дублирует строку и не
    изменяет уже записанное свидетельство."""
    if stage not in VALID_STAGES:
        raise PlanWriterError(f"неизвестная стадия: {stage!r}")
    if status not in VALID_EVENT_STATUSES:
        raise PlanWriterError(f"неизвестный статус события: {status!r}")
    event_id = event_id or _new_id("event")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT OR IGNORE INTO plan_attempt_event(event_id, attempt_id, "
            "stage, status, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, attempt_id, stage, status, detail, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return event_id


def set_attempt_status(conn: sqlite3.Connection, attempt_id: str, status: str) -> None:
    conn.execute("BEGIN")
    try:
        conn.execute(
            "UPDATE plan_import_attempt SET status = ? WHERE attempt_id = ?",
            (status, attempt_id),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ─────────────────────────────────────────────────────────────────────────
# plan_publication / plan_page_observation / plan_publication_page_link
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PublicationSpec:
    plan_id: str
    source_namespace: str
    attachment_id: str
    attachment_version: int
    lineage_id: str | None = None
    artifact_id: str | None = None
    page_id: str | None = None
    macro_id: str | None = None
    filename: str | None = None
    published_at: str | None = None
    observed_at: str | None = None
    page_version: int | None = None
    raw_sha256: str | None = None
    publication_id: str | None = None
    trust: str = "legacy_unverified"
    historical_status: str | None = None
    observation_id: str | None = None


class PublicationConflict(PlanWriterError):
    """Тот же (namespace, attachment_id, attachment_version), но иной hash."""


def record_publication(conn: sqlite3.Connection, spec: PublicationSpec) -> str:
    """Записать публикацию. UQ(source_namespace, attachment_id,
    attachment_version) — повторная вставка с тем же ключом и ТЕМ ЖЕ
    ``raw_sha256`` идемпотентна (возвращает существующий ``publication_id``);
    с иным hash — ``PublicationConflict`` (AC-112, не upsert, R-010)."""
    # Stage 01 repairs read-back only. Full admission/snapshot/schedule
    # evidence belongs to the later pipeline; no caller can promote it here.
    if spec.trust != "legacy_unverified":
        raise PlanWriterError("publication trust promotion requires the complete new pipeline")
    if spec.observation_id:
        obs = conn.execute(
            "SELECT plan_id, page_id, page_version, verification_status FROM plan_page_observation "
            "WHERE observation_id = ?", (spec.observation_id,),
        ).fetchone()
        if (not obs or tuple(obs) != (spec.plan_id, spec.page_id, spec.page_version, "verified_observation")):
            raise PlanWriterError("publication observation scope mismatch")
    existing = conn.execute(
        "SELECT publication_id, raw_sha256 FROM plan_publication "
        "WHERE source_namespace = ? AND attachment_id = ? AND attachment_version = ?",
        (spec.source_namespace, spec.attachment_id, spec.attachment_version),
    ).fetchone()
    if existing:
        existing_id, existing_hash = existing
        if spec.raw_sha256 is not None and existing_hash is not None and existing_hash != spec.raw_sha256:
            raise PublicationConflict(
                f"source={spec.source_namespace} attachment={spec.attachment_id} "
                f"version={spec.attachment_version}: existing hash {existing_hash} "
                f"!= new hash {spec.raw_sha256}"
            )
        if spec.observation_id:
            link_publication_page(conn, existing_id, spec.observation_id,
                                  link_kind="current_state_readback", confidence="confirmed",
                                  evidence="stage01-readback-v1; historical status unchanged")
        return existing_id
    publication_id = spec.publication_id or _new_id("pub")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_publication(publication_id, plan_id, lineage_id, "
            "artifact_id, source_namespace, attachment_id, attachment_version, "
            "page_id, macro_id, filename, published_at, observed_at, recorded_at, "
            "page_version, raw_sha256, trust, historical_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (publication_id, spec.plan_id, spec.lineage_id, spec.artifact_id,
             spec.source_namespace, spec.attachment_id, spec.attachment_version,
             spec.page_id, spec.macro_id, spec.filename, spec.published_at,
             spec.observed_at, _now(), spec.page_version, spec.raw_sha256,
             spec.trust, spec.historical_status),
        )
        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        raise
    except Exception:
        conn.execute("ROLLBACK")
        raise
    if spec.observation_id:
        link_publication_page(conn, publication_id, spec.observation_id,
                              link_kind="current_state_readback", confidence="confirmed",
                              evidence="stage01-readback-v1; schedule not verified")
    return publication_id


@dataclass(frozen=True)
class PageObservationSpec:
    plan_id: str
    page_id: str
    page_version: int | None = None
    storage_artifact_id: str | None = None
    itogo_raw: str | None = None
    itogo_text: str | None = None
    itogo_d1: str | None = None
    itogo_d2: str | None = None
    itogo_n: int | None = None
    itogo_m: int | None = None
    quality: str = "unknown"
    observation_id: str | None = None
    verification_status: str = "not_verified"
    verification_scope: str | None = None
    verification_profile: str | None = None
    verification: dict | None = None
    storage_sha256: str | None = None


def record_page_observation(conn: sqlite3.Connection, spec: PageObservationSpec) -> str:
    """Записать наблюдение страницы («Итого»/storage), не привязанное 1:1 к
    номеру публикации (R-015 §7.1, AC-110)."""
    if spec.verification_status not in ("not_verified", "verified_observation", "verification_failed"):
        raise PlanWriterError("invalid observation verification status")
    if spec.verification_status == "verified_observation":
        evidence = spec.verification or {}
        checks = evidence.get("checks", {})
        attachment = evidence.get("attachment", {})
        required_checks = {"skeleton_version", "skeleton_macro_count", "page_version", "one_gantt_macro",
                           "macro_id", "param_id", "param_hash", "attachment_name", "one_itogo",
                           "itogo_values", "itogo_above_macro", "no_trudozatraty", "storage_preserved"}
        if (not required_checks.issubset(checks) or spec.verification_scope not in ("current_state", "historical_version")
                or not spec.verification_profile or not spec.page_version or not spec.itogo_raw
                or not checks or not all(value is True for value in checks.values())
                or not attachment.get("attachment_id") or not attachment.get("attachment_version")
                or attachment.get("expected_sha256") != attachment.get("actual_sha256")
                or not attachment.get("actual_sha256")
                or hashlib.sha256(spec.itogo_raw.encode()).hexdigest() != spec.storage_sha256):
            raise PlanWriterError("incomplete read-back observation evidence")
    observation_id = spec.observation_id or _new_id("obs")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_page_observation(observation_id, plan_id, page_id, "
            "page_version, fetched_at, storage_artifact_id, itogo_raw, itogo_text, "
            "itogo_d1, itogo_d2, itogo_n, itogo_m, quality, verification_status, "
            "verification_scope, verification_profile, verification_json, storage_sha256) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (observation_id, spec.plan_id, spec.page_id, spec.page_version,
             _now(), spec.storage_artifact_id, spec.itogo_raw, spec.itogo_text,
             spec.itogo_d1, spec.itogo_d2, spec.itogo_n, spec.itogo_m, spec.quality,
             spec.verification_status, spec.verification_scope, spec.verification_profile,
             json.dumps(spec.verification, ensure_ascii=False) if spec.verification else None,
             spec.storage_sha256),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return observation_id


def link_publication_page(
    conn: sqlite3.Connection,
    publication_id: str,
    observation_id: str,
    *,
    link_kind: str = "observed",
    confidence: str = "unknown",
    evidence: str | None = None,
    supersedes: str | None = None,
) -> str:
    if confidence not in ("confirmed", "inferred", "unknown"):
        raise PlanWriterError(f"неизвестная confidence: {confidence!r}")
    pair = conn.execute(
        "SELECT p.plan_id, p.page_id, o.plan_id, o.page_id FROM plan_publication p "
        "JOIN plan_page_observation o ON o.observation_id=? WHERE p.publication_id=?",
        (observation_id, publication_id),
    ).fetchone()
    if not pair or pair[0] != pair[2] or (pair[1] is not None and pair[1] != pair[3]):
        raise PlanWriterError("cross-plan/page publication observation link")
    link_revision_id = _new_id("link")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_publication_page_link(link_revision_id, "
            "publication_id, observation_id, link_kind, confidence, evidence, "
            "supersedes, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (link_revision_id, publication_id, observation_id, link_kind,
             confidence, evidence, supersedes, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return link_revision_id


# ─────────────────────────────────────────────────────────────────────────
# Фаза 2 (P2.SCHEMA.1-8, R-012-019): typed writer для версионных snapshot-
# данных полного графа плана. ``ingest_snapshot`` — единственная точка входа,
# которая пишет снимок (задачи/связи/ресурсы/назначения/календари/baseline/
# качество) ОДНОЙ транзакцией: любая ошибка на любом шаге откатывает весь
# снимок (AC-116 — не остаётся полуснимка последним "полным").
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TaskSegmentSpec:
    start_raw: str | None = None
    finish_raw: str | None = None


@dataclass(frozen=True)
class BaselineValueSpec:
    baseline_slot: int
    baseline_start: str | None = None
    baseline_finish: str | None = None
    baseline_duration_raw: str | None = None
    baseline_work_raw: str | None = None
    baseline_cost: float | None = None
    baseline_cost_decimal: str | None = None
    source_json: str | None = None


@dataclass(frozen=True)
class TaskVersionSpec:
    task_key: str
    uid: str | None = None
    wbs: str | None = None
    name: str | None = None
    outline_level: int | None = None
    start_raw: str | None = None
    finish_raw: str | None = None
    duration_raw: str | None = None
    early_start: str | None = None
    early_finish: str | None = None
    late_start: str | None = None
    late_finish: str | None = None
    percent_complete: float | None = None
    milestone: bool | None = False
    summary: bool | None = False
    constraint_type: str | None = None
    constraint_date: str | None = None
    actual_start: str | None = None
    actual_finish: str | None = None
    actual_duration_raw: str | None = None
    remaining_duration_raw: str | None = None
    notes: str | None = None
    quality: str = "unknown"
    extensions: str | None = None
    segments: tuple[TaskSegmentSpec, ...] = ()
    baseline_values: tuple[BaselineValueSpec, ...] = ()
    source_id: str | None = None
    parent_task_key: str | None = None
    calendar_key: str | None = None
    effective_calendar_key: str | None = None
    task_mode: str | None = None
    duration_amount: str | None = None
    duration_units: str | None = None
    duration_elapsed: bool | None = None
    work_amount: str | None = None
    work_units: str | None = None
    percent_complete_decimal: str | None = None
    source_json: str | None = None


@dataclass(frozen=True)
class DependencyVersionSpec:
    predecessor_task_key: str
    successor_task_key: str
    link_type: str | None = None
    lag_raw: str | None = None
    lag_calendar: str | None = None
    dependency_key: str | None = None
    lag_amount: str | None = None
    lag_units: str | None = None
    lag_elapsed: bool | None = None
    calendar_basis: str | None = None
    source_json: str | None = None


@dataclass(frozen=True)
class ExternalDependencySpec:
    local_task_key: str
    direction: str  # 'predecessor'|'successor'
    reason: str
    external_ref: str | None = None


@dataclass(frozen=True)
class ResourceAvailabilitySpec:
    available_from: str | None = None
    available_to: str | None = None
    max_units: float | None = None
    max_units_decimal: str | None = None
    source_json: str | None = None


@dataclass(frozen=True)
class ResourceVersionSpec:
    resource_key: str
    uid: str | None = None
    name: str | None = None
    type: str | None = None
    email: str | None = None
    resource_group: str | None = None
    max_units: float | None = None
    std_rate_raw: str | None = None
    ot_rate_raw: str | None = None
    cost_per_use: float | None = None
    extensions: str | None = None
    availability: tuple[ResourceAvailabilitySpec, ...] = ()
    calendar_key: str | None = None
    base_calendar_key: str | None = None
    max_units_decimal: str | None = None
    cost_per_use_decimal: str | None = None
    source_json: str | None = None


@dataclass(frozen=True)
class TimephasedSpec:
    period_start: str
    period_end: str
    work_raw: str | None = None
    work_amount: str | None = None
    work_units: str | None = None
    source_json: str | None = None


@dataclass(frozen=True)
class AssignmentVersionSpec:
    task_key: str
    resource_key: str
    units: float | None = None
    work_raw: str | None = None
    start_raw: str | None = None
    finish_raw: str | None = None
    actual_work_raw: str | None = None
    remaining_work_raw: str | None = None
    timephased: tuple[TimephasedSpec, ...] = ()
    assignment_key: str | None = None
    uid: str | None = None
    units_decimal: str | None = None
    work_amount: str | None = None
    work_units: str | None = None
    effective_calendar_key: str | None = None
    source_json: str | None = None


@dataclass(frozen=True)
class CalendarIntervalSpec:
    interval_kind: str  # 'weekday'|'exception'
    day_or_date: str
    working: bool | None
    time_from: str | None = None
    time_to: str | None = None


@dataclass(frozen=True)
class CalendarVersionSpec:
    calendar_key: str
    name: str | None = None
    base_calendar_key: str | None = None
    minutes_per_day: float | None = None
    minutes_per_week: float | None = None
    intervals: tuple[CalendarIntervalSpec, ...] = ()
    parent_key: str | None = None
    minutes_per_day_decimal: str | None = None
    minutes_per_week_decimal: str | None = None
    source_json: str | None = None


@dataclass(frozen=True)
class CollectionStatusSpec:
    collection_kind: str
    status: str  # complete|partial|missing|unsupported
    count: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class QualityIssueSpec:
    issue_kind: str
    severity: str  # info|warning|error
    detail: str | None = None


@dataclass(frozen=True)
class SnapshotSpec:
    plan_id: str
    representation: str
    lineage_id: str | None = None
    source_artifact_id: str | None = None
    timezone_hint: str | None = None
    status_date: str | None = None
    published_at: str | None = None
    observed_at: str | None = None
    snapshot_id: str | None = None
    collections: tuple[CollectionStatusSpec, ...] = ()
    tasks: tuple[TaskVersionSpec, ...] = ()
    dependencies: tuple[DependencyVersionSpec, ...] = ()
    external_dependencies: tuple[ExternalDependencySpec, ...] = ()
    resources: tuple[ResourceVersionSpec, ...] = ()
    assignments: tuple[AssignmentVersionSpec, ...] = ()
    calendars: tuple[CalendarVersionSpec, ...] = ()
    quality_issues: tuple[QualityIssueSpec, ...] = ()
    normalization_profile_fingerprint: str | None = None
    resolved_timezone: str | None = None
    source_mpp_sha256: str | None = None
    normalized_data_sha256: str | None = None
    source_json: str | None = None


def _write_extra(conn, table, pk, value, spec):
    from .schema import VERSION_EXTRA_COLUMNS
    fields = {c: getattr(spec, c) for c in VERSION_EXTRA_COLUMNS[table] if getattr(spec, c) is not None}
    if fields:
        conn.execute(f"UPDATE {table} SET " + ",".join(f"{c}=?" for c in fields) + f" WHERE {pk}=?",
                     (*fields.values(), value))


@contextmanager
def _transaction(conn):
    if conn.in_transaction:
        raise PlanWriterError("writer requires an idle connection; no implicit/nested commit")
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def _insert_snapshot(conn, spec, snapshot_id):
    """SQL only. The caller owns the transaction, including item/event linkage."""
    if spec.normalization_profile_fingerprint and not spec.tasks:
        raise PlanWriterError("snapshot_has_no_readable_tasks")
    now = _now()
    conn.execute(
        "INSERT INTO plan_snapshot(snapshot_id, plan_id, lineage_id, "
        "source_artifact_id, representation, timezone_hint, status_date, "
        "published_at, observed_at, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (snapshot_id, spec.plan_id, spec.lineage_id, spec.source_artifact_id,
         spec.representation, spec.timezone_hint, spec.status_date,
         spec.published_at, spec.observed_at, now),
    )

    for col in spec.collections:
        conn.execute(
            "INSERT INTO plan_snapshot_collection(collection_id, snapshot_id, "
            "collection_kind, status, count, reason, recorded_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (_new_id("coll"), snapshot_id, col.collection_kind, col.status,
             col.count, col.reason, now),
        )

    for task in spec.tasks:
        task_version_id = _new_id("taskv")
        conn.execute(
            "INSERT INTO plan_task_version(task_version_id, snapshot_id, plan_id, "
            "task_key, uid, wbs, name, outline_level, start_raw, finish_raw, "
            "duration_raw, early_start, early_finish, late_start, late_finish, "
            "percent_complete, milestone, summary, constraint_type, constraint_date, "
            "actual_start, actual_finish, actual_duration_raw, remaining_duration_raw, "
            "notes, quality, extensions, recorded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (task_version_id, snapshot_id, spec.plan_id, task.task_key, task.uid,
             task.wbs, task.name, task.outline_level, task.start_raw, task.finish_raw,
             task.duration_raw, task.early_start, task.early_finish, task.late_start,
             task.late_finish, task.percent_complete, int(task.milestone) if task.milestone is not None else None,
             int(task.summary) if task.summary is not None else None, task.constraint_type, task.constraint_date,
             task.actual_start, task.actual_finish, task.actual_duration_raw,
             task.remaining_duration_raw, task.notes, task.quality, task.extensions, now),
        )
        _write_extra(conn, "plan_task_version", "task_version_id", task_version_id, task)
        for idx, seg in enumerate(task.segments):
            conn.execute(
                "INSERT INTO plan_task_segment(segment_id, task_version_id, "
                "segment_index, start_raw, finish_raw, recorded_at) VALUES (?,?,?,?,?,?)",
                (_new_id("seg"), task_version_id, idx, seg.start_raw, seg.finish_raw, now),
            )
        for bv in task.baseline_values:
            baseline_value_id = _new_id("bv")
            conn.execute(
                "INSERT INTO plan_embedded_baseline_value(baseline_value_id, "
                "task_version_id, baseline_slot, baseline_start, baseline_finish, "
                "baseline_duration_raw, baseline_work_raw, baseline_cost, recorded_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (baseline_value_id, task_version_id, bv.baseline_slot, bv.baseline_start,
                 bv.baseline_finish, bv.baseline_duration_raw, bv.baseline_work_raw,
                 bv.baseline_cost, now),
            )

            _write_extra(conn, "plan_embedded_baseline_value", "baseline_value_id", baseline_value_id, bv)

    for dep in spec.dependencies:
        dependency_version_id = _new_id("dep")
        conn.execute(
            "INSERT INTO plan_dependency_version(dependency_version_id, snapshot_id, "
            "predecessor_task_key, successor_task_key, link_type, lag_raw, "
            "lag_calendar, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (dependency_version_id, snapshot_id, dep.predecessor_task_key,
             dep.successor_task_key, dep.link_type, dep.lag_raw, dep.lag_calendar, now),
        )

        _write_extra(conn, "plan_dependency_version", "dependency_version_id", dependency_version_id, dep)

    for ext in spec.external_dependencies:
        conn.execute(
            "INSERT INTO plan_external_dependency(external_dependency_id, snapshot_id, "
            "local_task_key, external_ref, direction, reason, recorded_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (_new_id("extdep"), snapshot_id, ext.local_task_key, ext.external_ref,
             ext.direction, ext.reason, now),
        )

    for res in spec.resources:
        resource_version_id = _new_id("resv")
        conn.execute(
            "INSERT INTO plan_resource_version(resource_version_id, snapshot_id, "
            "plan_id, resource_key, uid, name, type, email, resource_group, "
            "max_units, std_rate_raw, ot_rate_raw, cost_per_use, extensions, recorded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (resource_version_id, snapshot_id, spec.plan_id, res.resource_key, res.uid,
             res.name, res.type, res.email, res.resource_group, res.max_units,
             res.std_rate_raw, res.ot_rate_raw, res.cost_per_use, res.extensions, now),
        )
        _write_extra(conn, "plan_resource_version", "resource_version_id", resource_version_id, res)
        for av in res.availability:
            availability_id = _new_id("avail")
            conn.execute(
                "INSERT INTO plan_resource_availability(availability_id, "
                "resource_version_id, available_from, available_to, max_units, recorded_at) "
                "VALUES (?,?,?,?,?,?)",
                (availability_id, resource_version_id, av.available_from,
                 av.available_to, av.max_units, now),
            )

            _write_extra(conn, "plan_resource_availability", "availability_id", availability_id, av)

    for asg in spec.assignments:
        assignment_version_id = _new_id("asgv")
        conn.execute(
            "INSERT INTO plan_assignment_version(assignment_version_id, snapshot_id, "
            "task_key, resource_key, units, work_raw, start_raw, finish_raw, "
            "actual_work_raw, remaining_work_raw, recorded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (assignment_version_id, snapshot_id, asg.task_key, asg.resource_key,
             asg.units, asg.work_raw, asg.start_raw, asg.finish_raw,
             asg.actual_work_raw, asg.remaining_work_raw, now),
        )
        _write_extra(conn, "plan_assignment_version", "assignment_version_id", assignment_version_id, asg)
        for tp in asg.timephased:
            timephased_id = _new_id("tp")
            conn.execute(
                "INSERT INTO plan_assignment_timephased(timephased_id, "
                "assignment_version_id, period_start, period_end, work_raw, recorded_at) "
                "VALUES (?,?,?,?,?,?)",
                (timephased_id, assignment_version_id, tp.period_start, tp.period_end,
                 tp.work_raw, now),
            )

            _write_extra(conn, "plan_assignment_timephased", "timephased_id", timephased_id, tp)

    for cal in spec.calendars:
        calendar_version_id = _new_id("calv")
        conn.execute(
            "INSERT INTO plan_calendar_version(calendar_version_id, snapshot_id, "
            "calendar_key, name, base_calendar_key, minutes_per_day, minutes_per_week, "
            "recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (calendar_version_id, snapshot_id, cal.calendar_key, cal.name,
             cal.base_calendar_key, cal.minutes_per_day, cal.minutes_per_week, now),
        )
        _write_extra(conn, "plan_calendar_version", "calendar_version_id", calendar_version_id, cal)
        for interval in cal.intervals:
            conn.execute(
                "INSERT INTO plan_calendar_interval(interval_id, calendar_version_id, "
                "interval_kind, day_or_date, working, time_from, time_to, recorded_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (_new_id("iv"), calendar_version_id, interval.interval_kind,
                 interval.day_or_date, int(interval.working) if interval.working is not None else None, interval.time_from,
                 interval.time_to, now),
            )

    for issue in spec.quality_issues:
        conn.execute(
            "INSERT INTO plan_quality_issue(issue_id, plan_id, lineage_id, snapshot_id, "
            "issue_kind, severity, detail, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (_new_id("issue"), spec.plan_id, spec.lineage_id, snapshot_id,
             issue.issue_kind, issue.severity, issue.detail, now),
        )

    fields = {c: getattr(spec, c) for c in (
        "normalization_profile_fingerprint", "resolved_timezone", "source_mpp_sha256",
        "normalized_data_sha256", "source_json") if getattr(spec, c) is not None}
    if spec.normalization_profile_fingerprint:
        fields["dedup_key"] = snapshot_dedup_key(spec)
        fields["version_counts_json"] = _json(_version_counts(spec))
    if fields:
        conn.execute("UPDATE plan_snapshot SET " + ",".join(f"{c}=?" for c in fields) + " WHERE snapshot_id=?",
                     (*fields.values(), snapshot_id))


def ingest_snapshot(conn: sqlite3.Connection, spec: SnapshotSpec) -> str:
    """Legacy ingest and profiled ingest share the same transaction-free inserter."""
    with _transaction(conn):
        snapshot_id = _find_snapshot(conn, spec)
        if snapshot_id:
            return snapshot_id
        snapshot_id = spec.snapshot_id or _new_id("snapshot")
        _insert_snapshot(conn, spec, snapshot_id)
        return snapshot_id


def record_quality_issue(
    conn: sqlite3.Connection,
    plan_id: str,
    issue_kind: str,
    severity: str,
    *,
    lineage_id: str | None = None,
    snapshot_id: str | None = None,
    detail: str | None = None,
    issue_id: str | None = None,
) -> str:
    """Записать проблему качества/диагностики без обязательной привязки к
    завершённому снимку (напр. персистентная отметка «MPP vN missing»,
    AC-111 хвост). Append-only: повтор с тем же ``issue_id`` идемпотентен."""
    if severity not in ("info", "warning", "error"):
        raise PlanWriterError(f"неизвестная severity: {severity!r}")
    issue_id = issue_id or _new_id("issue")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT OR IGNORE INTO plan_quality_issue(issue_id, plan_id, lineage_id, "
            "snapshot_id, issue_kind, severity, detail, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (issue_id, plan_id, lineage_id, snapshot_id, issue_kind, severity, detail, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return issue_id


def select_snapshot_baseline(
    conn: sqlite3.Connection,
    lineage_id: str,
    snapshot_id: str,
    *,
    is_explicit: bool = False,
    basis: str | None = None,
    selection_id: str | None = None,
) -> str:
    """R-019/AC-120: выбрать snapshot «базой» для lineage.

    Default (``is_explicit=False``) фиксирует первую доступную базу и НЕ
    переопределяет уже сделанный явный выбор владельца — если текущая
    активная выборка явная, вызов с ``is_explicit=False`` возвращает её
    ``selection_id`` без изменений. Явный вызов (``is_explicit=True``) всегда
    создаёт новую ревизию (append-only, ``supersedes`` предыдущую активную;
    старая строка не удаляется/не правится, R-016.3)."""
    current = conn.execute(
        "SELECT selection_id, snapshot_id, is_explicit FROM plan_snapshot_selection "
        "WHERE lineage_id = ? AND selection_id NOT IN ("
        "  SELECT supersedes FROM plan_snapshot_selection "
        "  WHERE supersedes IS NOT NULL AND lineage_id = ?"
        ") ORDER BY recorded_at DESC, selection_id DESC LIMIT 1",
        (lineage_id, lineage_id),
    ).fetchone()
    if current and not is_explicit:
        cur_id, cur_snapshot, cur_explicit = current
        if cur_explicit:
            return cur_id
        if cur_snapshot == snapshot_id:
            return cur_id
    new_id = selection_id or _new_id("sel")
    supersedes = current[0] if current else None
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_snapshot_selection(selection_id, lineage_id, snapshot_id, "
            "is_explicit, basis, supersedes, recorded_at) VALUES (?,?,?,?,?,?,?)",
            (new_id, lineage_id, snapshot_id, int(is_explicit),
             basis or ("explicit_owner" if is_explicit else "first_available_default"),
             supersedes, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return new_id


# ─────────────────────────────────────────────────────────────────────────
# Фаза 3 (P3.SCHEMA.1/P3.ANALYSIS.11, R-035): persistence аналитического
# прогона (plan_attribution.py/plan_scheduler.py в MppReader пишут сюда через
# subprocess-границу — сам расчёт не выполняется в этом модуле). Append-only:
# смена baseline/mapping создаёт НОВЫЙ run_id, старый run не переписывается
# (AC-140). ``record_analysis_run`` — одна транзакция на весь прогон
# (run + scenarios + task_results + contributions), по аналогии с
# ``ingest_snapshot``.
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AnalysisScenarioSpec:
    method: str  # 'sequential'|'sequential_reverse'|'shapley'
    group_ids_json: str
    applied_order: int | None = None
    is_valid: bool = True
    finish_scale_value: float | None = None
    finish_raw: str | None = None
    scenario_id: str | None = None


@dataclass(frozen=True)
class AnalysisTaskResultSpec:
    task_key: str
    scenario_id: str | None = None
    early_start: str | None = None
    early_finish: str | None = None
    late_start: str | None = None
    late_finish: str | None = None
    total_slack_raw: str | None = None
    free_slack_raw: str | None = None
    is_driving: bool = False


@dataclass(frozen=True)
class AnalysisContributionSpec:
    method: str  # 'sequential'|'sequential_reverse'|'shapley'
    group_id: str
    contribution_value: float
    group_category: str | None = None
    contribution_raw: str | None = None
    rank_in_order: int | None = None


@dataclass(frozen=True)
class AnalysisRunSpec:
    plan_id: str
    snapshot_a_id: str
    snapshot_b_id: str
    engine_name: str
    result_class: str
    receipt_json: str
    mapping_revision_id: str | None = None
    baseline_selection_id: str | None = None
    target_task_key: str | None = None
    engine_version: str | None = None
    scale_basis: str | None = None
    method: str | None = None
    delta_obs_raw: str | None = None
    delta_model_raw: str | None = None
    residual_raw: str | None = None
    completeness: str = "unknown"
    blockers: str | None = None
    input_hash_a: str | None = None
    input_hash_b: str | None = None
    duration_ms: int | None = None
    scenario_count: int | None = None
    run_id: str | None = None
    scenarios: tuple[AnalysisScenarioSpec, ...] = ()
    task_results: tuple[AnalysisTaskResultSpec, ...] = ()
    contributions: tuple[AnalysisContributionSpec, ...] = ()


def record_analysis_run(conn: sqlite3.Connection, spec: AnalysisRunSpec) -> str:
    """Записать один аналитический прогон (run+scenarios+task_results+
    contributions) ОДНОЙ транзакцией (R-035, AC-140).

    Повтор с тем же явно переданным ``spec.run_id`` — чистое чтение
    (идемпотентно, не пересчёт и не дублирование вложенных строк): смена
    входов (``baseline_selection_id``/``mapping_revision_id``/другие данные)
    обязана сопровождаться новым ``run_id`` на стороне вызывающего кода —
    этот writer не отличает "те же входы" от "другие входы" сам по себе.
    """
    if spec.result_class not in {
        "observed_diff", "validated_attribution", "hypothetical_scenario",
        "insufficient_data", "unsupported_profile", "replay_failed",
        "invalid_scenario", "method_limit",
    }:
        raise PlanWriterError(f"неизвестный result_class: {spec.result_class!r}")
    run_id = spec.run_id or _new_id("run")
    existing = conn.execute(
        "SELECT run_id FROM plan_analysis_run WHERE run_id = ?", (run_id,)
    ).fetchone()
    if existing:
        return run_id
    now = _now()
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_analysis_run(run_id, plan_id, snapshot_a_id, "
            "snapshot_b_id, mapping_revision_id, baseline_selection_id, "
            "target_task_key, engine_name, engine_version, scale_basis, "
            "result_class, method, delta_obs_raw, delta_model_raw, residual_raw, "
            "completeness, blockers, input_hash_a, input_hash_b, duration_ms, "
            "scenario_count, receipt_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, spec.plan_id, spec.snapshot_a_id, spec.snapshot_b_id,
             spec.mapping_revision_id, spec.baseline_selection_id,
             spec.target_task_key, spec.engine_name, spec.engine_version,
             spec.scale_basis, spec.result_class, spec.method,
             spec.delta_obs_raw, spec.delta_model_raw, spec.residual_raw,
             spec.completeness, spec.blockers, spec.input_hash_a,
             spec.input_hash_b, spec.duration_ms, spec.scenario_count,
             spec.receipt_json, now),
        )

        scenario_ids: dict[str, str] = {}
        for sc in spec.scenarios:
            scenario_id = sc.scenario_id or _new_id("scen")
            scenario_ids[sc.group_ids_json] = scenario_id
            conn.execute(
                "INSERT INTO plan_analysis_scenario(scenario_id, run_id, method, "
                "group_ids_json, applied_order, is_valid, finish_scale_value, "
                "finish_raw, recorded_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (scenario_id, run_id, sc.method, sc.group_ids_json,
                 sc.applied_order, int(sc.is_valid), sc.finish_scale_value,
                 sc.finish_raw, now),
            )

        for tr in spec.task_results:
            conn.execute(
                "INSERT INTO plan_analysis_task_result(task_result_id, run_id, "
                "scenario_id, task_key, early_start, early_finish, late_start, "
                "late_finish, total_slack_raw, free_slack_raw, is_driving, "
                "recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (_new_id("taskres"), run_id, tr.scenario_id, tr.task_key,
                 tr.early_start, tr.early_finish, tr.late_start, tr.late_finish,
                 tr.total_slack_raw, tr.free_slack_raw, int(tr.is_driving), now),
            )

        for c in spec.contributions:
            conn.execute(
                "INSERT INTO plan_analysis_contribution(contribution_id, run_id, "
                "method, group_id, group_category, contribution_value, "
                "contribution_raw, rank_in_order, recorded_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (_new_id("contrib"), run_id, c.method, c.group_id,
                 c.group_category, c.contribution_value, c.contribution_raw,
                 c.rank_in_order, now),
            )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return run_id


def select_plan_baseline(
    conn: sqlite3.Connection,
    plan_id: str,
    snapshot_id: str,
    baseline_slot: int,
    *,
    is_explicit: bool = False,
    basis: str | None = None,
    selection_id: str | None = None,
) -> str:
    """Аналог ``select_snapshot_baseline`` для выбора embedded baseline-слота
    (0..10) — отдельная политика default/explicit (R-019)."""
    current = conn.execute(
        "SELECT baseline_selection_id, baseline_slot, is_explicit FROM plan_baseline_selection "
        "WHERE plan_id = ? AND baseline_selection_id NOT IN ("
        "  SELECT supersedes FROM plan_baseline_selection "
        "  WHERE supersedes IS NOT NULL AND plan_id = ?"
        ") ORDER BY recorded_at DESC, baseline_selection_id DESC LIMIT 1",
        (plan_id, plan_id),
    ).fetchone()
    if current and not is_explicit:
        cur_id, cur_slot, cur_explicit = current
        if cur_explicit:
            return cur_id
        if cur_slot == baseline_slot:
            return cur_id
    new_id = selection_id or _new_id("bsel")
    supersedes = current[0] if current else None
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_baseline_selection(baseline_selection_id, plan_id, "
            "snapshot_id, baseline_slot, is_explicit, basis, supersedes, recorded_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (new_id, plan_id, snapshot_id, baseline_slot, int(is_explicit),
             basis or ("explicit_owner" if is_explicit else "first_available_default"),
             supersedes, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return new_id


# Stage 03: durable receipts and one atomic snapshot/item/event boundary.
def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class OperationSpec:
    action: str
    context_json: str = "{}"
    operation_id: str | None = None
    plan_id: str | None = None
    lineage_id: str | None = None


@dataclass(frozen=True)
class ImportBatchSpec:
    batch_id: str
    manifest_version: int
    manifest_json: str
    manifest_sha256: str
    source: str
    context_json: str
    on_error: str = "continue"
    status: str = "freezing_inputs"


@dataclass(frozen=True)
class ImportItemSpec:
    operation_id: str
    original_name: str
    original_locator: str
    item_id: str | None = None
    batch_id: str | None = None
    ordinal: int = 0
    plan_id: str | None = None
    lineage_id: str | None = None
    transport_json: str | None = None
    source_mpp_sha256: str | None = None
    size_bytes: int | None = None
    container_sha256: str | None = None
    container_locator: str | None = None
    zip_member: str | None = None
    received_at: str | None = None
    frozen_at: str | None = None
    frozen_locator: str | None = None
    source_version_date: str | None = None
    source_version_basis: str | None = None
    normalization_profile_fingerprint: str | None = None
    resolved_timezone: str | None = None
    status: str = "not_started"
    error_code: str | None = None
    retryable: bool = False


@dataclass(frozen=True)
class ImportCommitResult:
    item_id: str
    snapshot_id: str
    status: str


_VERSION_COLLECTIONS = {
    "plan_task_version": "tasks", "plan_dependency_version": "dependencies",
    "plan_external_dependency": "external_dependencies", "plan_resource_version": "resources",
    "plan_assignment_version": "assignments", "plan_calendar_version": "calendars",
    "plan_snapshot_collection": "collections", "plan_quality_issue": "quality_issues",
}


_VERSION_CHILDREN = {
    "plan_task_segment": ("plan_task_version","task_version_id"),
    "plan_embedded_baseline_value": ("plan_task_version","task_version_id"),
    "plan_resource_availability": ("plan_resource_version","resource_version_id"),
    "plan_assignment_timephased": ("plan_assignment_version","assignment_version_id"),
    "plan_calendar_interval": ("plan_calendar_version","calendar_version_id"),
}


def _version_counts(spec):
    counts={name:len(getattr(spec,attr)) for name,attr in _VERSION_COLLECTIONS.items()}
    counts.update(plan_task_segment=sum(len(t.segments) for t in spec.tasks),
                  plan_embedded_baseline_value=sum(len(t.baseline_values) for t in spec.tasks),
                  plan_resource_availability=sum(len(r.availability) for r in spec.resources),
                  plan_assignment_timephased=sum(len(a.timephased) for a in spec.assignments),
                  plan_calendar_interval=sum(len(c.intervals) for c in spec.calendars))
    return counts


@lru_cache(maxsize=512)
def normalize_timezone(value):
    if value is None or value == "unknown":
        return "unknown"
    zone = ZoneInfo(value)
    # RHEL tzdata also represents aliases as hardlinks. Its Link records give
    # semantic names; equal UTC offsets alone must never merge distinct zones.
    metadata=Path("/usr/share/zoneinfo/tzdata.zi")
    if metadata.is_file():
        links={}
        for line in metadata.read_text().splitlines():
            parts=line.split()
            if len(parts)==3 and parts[0] in ("L","Link"):
                links[parts[2]]=parts[1]
        canonical=zone.key
        seen=set()
        while canonical in links and canonical not in seen:
            seen.add(canonical)
            canonical=links[canonical]
        return canonical
    # Resolve tzdata symlink aliases (e.g. US/Eastern), independent of local TZ.
    for root in (Path("/usr/share/zoneinfo"),):
        candidate = root / zone.key
        try:
            canonical = candidate.resolve(strict=True).relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            continue
        if not canonical.startswith(("posix/", "right/")):
            return canonical
    return zone.key


def snapshot_dedup_key(spec: SnapshotSpec) -> str | None:
    if not spec.normalization_profile_fingerprint:
        return None  # Historical snapshots are never guessed equivalent.
    if not spec.lineage_id or not spec.source_mpp_sha256 or not spec.source_artifact_id:
        raise PlanWriterError("profiled snapshot requires lineage, source hash and artifact")
    if spec.resolved_timezone != normalize_timezone(spec.resolved_timezone):
        raise PlanWriterError("resolved_timezone must be normalized IANA or unknown")
    return hashlib.sha256(_json([spec.plan_id, spec.lineage_id, spec.source_mpp_sha256,
                                spec.representation, spec.normalization_profile_fingerprint,
                                spec.resolved_timezone]).encode()).hexdigest()


def verify_artifact(conn, artifact_id, expected_sha256=None):
    row = conn.execute("SELECT path,raw_sha256,size_bytes FROM plan_artifact WHERE artifact_id=?",
                       (artifact_id,)).fetchone()
    if not row:
        raise PlanWriterError("artifact_missing")
    path, digest, size = row
    if expected_sha256 and digest != expected_sha256:
        raise PlanWriterError("artifact_hash_mismatch")
    try:
        h = hashlib.sha256()
        count = 0
        with Path(path).open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                h.update(block)
                count += len(block)
        if h.hexdigest() != digest or (size is not None and size != count):
            raise PlanWriterError("artifact_hash_mismatch")
    except OSError as exc:
        raise PlanWriterError("artifact_missing") from exc
    return path


def verify_snapshot(conn, snapshot_id):
    row = conn.execute("SELECT source_artifact_id,source_mpp_sha256,version_counts_json "
                       "FROM plan_snapshot WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    if not row:
        raise PlanWriterError("snapshot_missing")
    artifact, digest, counts_json = row
    data=conn.execute("SELECT source_json,normalized_data_sha256 FROM plan_snapshot WHERE snapshot_id=?",(snapshot_id,)).fetchone()
    if data[0] is not None and hashlib.sha256(data[0].encode()).hexdigest() != data[1]:
        raise PlanWriterError("normalized_data_hash_mismatch")
    verify_artifact(conn, artifact, digest)
    if not counts_json:
        raise PlanWriterError("snapshot_profile_unknown")
    for table, expected in json.loads(counts_json).items():
        if table in _VERSION_COLLECTIONS:
            sql=f"SELECT count(*) FROM {table} WHERE snapshot_id=?"
        elif table in _VERSION_CHILDREN:
            parent,foreign_key=_VERSION_CHILDREN[table]
            sql=f"SELECT count(*) FROM {table} c JOIN {parent} p USING({foreign_key}) WHERE p.snapshot_id=?"
        else:
            raise PlanWriterError("snapshot_invalid_counts")
        count=conn.execute(sql,(snapshot_id,)).fetchone()[0]
        if count != expected:
            raise PlanWriterError("snapshot_incomplete")
    return snapshot_id


def _find_snapshot(conn, spec):
    key = snapshot_dedup_key(spec)
    if key:
        verify_artifact(conn, spec.source_artifact_id, spec.source_mpp_sha256)
        row = conn.execute("SELECT snapshot_id FROM plan_snapshot WHERE dedup_key=?", (key,)).fetchone()
        if row:
            verify_snapshot(conn, row[0])
            return row[0]
    if spec.snapshot_id:
        row = conn.execute("SELECT dedup_key FROM plan_snapshot WHERE snapshot_id=?", (spec.snapshot_id,)).fetchone()
        if row:
            if key and row[0] != key:
                raise PlanWriterError("snapshot_id_conflict")
            return spec.snapshot_id
    return None


def create_operation(conn, spec: OperationSpec) -> str:
    operation_id = spec.operation_id or _new_id("operation")
    with _transaction(conn):
        row = conn.execute("SELECT action,context_json,plan_id,lineage_id FROM plan_operation WHERE operation_id=?",
                           (operation_id,)).fetchone()
        values = (spec.action, spec.context_json, spec.plan_id, spec.lineage_id)
        if row:
            # Resolved project refs may have been filled after registration.
            if tuple(row)[:2] != values[:2] or any(v is not None and row[i] != v for i,v in enumerate(values[2:],2)):
                raise PlanWriterError("operation_context_conflict")
        else:
            conn.execute("INSERT INTO plan_operation(operation_id,action,context_json,plan_id,lineage_id,created_at) "
                         "VALUES (?,?,?,?,?,?)", (operation_id,*values,_now()))
    return operation_id


def create_import_batch(conn, spec: ImportBatchSpec) -> str:
    values = asdict(spec)
    canonical = _json(json.loads(spec.manifest_json))
    if hashlib.sha256(canonical.encode()).hexdigest() != spec.manifest_sha256:
        raise PlanWriterError("batch_manifest_hash_mismatch")
    values["manifest_json"] = canonical
    with _transaction(conn):
        row = conn.execute("SELECT manifest_sha256,context_json,on_error FROM plan_import_batch WHERE batch_id=?",
                           (spec.batch_id,)).fetchone()
        if row:
            if tuple(row) != (spec.manifest_sha256,spec.context_json,spec.on_error):
                raise PlanWriterError("batch_manifest_conflict")
        else:
            values["created_at"] = _now()
            conn.execute("INSERT INTO plan_import_batch("+",".join(values)+") VALUES ("+",".join("?" for _ in values)+")",
                         tuple(values.values()))
    return spec.batch_id


def create_import_item(conn, spec: ImportItemSpec) -> str:
    values = asdict(spec)
    values["item_id"] = spec.item_id or _new_id("item")
    values["received_at"] = spec.received_at or _now()
    with _transaction(conn):
        row = conn.execute("SELECT * FROM plan_import_item WHERE operation_id=? OR item_id=?",
                           (spec.operation_id,values["item_id"])).fetchone()
        if row:
            columns = [r[1] for r in conn.execute("PRAGMA table_info(plan_import_item)")]
            existing = dict(zip(columns,row))
            for name,value in values.items():
                if name in {"item_id","received_at","status","error_code","retryable"}:
                    continue
                if value is not None and existing[name] != value:
                    raise PlanWriterError("import_item_conflict")
            return existing["item_id"]
        conn.execute("INSERT INTO plan_import_item("+",".join(values)+") VALUES ("+",".join("?" for _ in values)+")",
                     tuple(values.values()))
    return values["item_id"]


def begin_operation_attempt(conn, operation_id: str, item_id: str) -> str:
    attempt_id = _new_id("attempt")
    with _transaction(conn):
        row = conn.execute("SELECT plan_id,lineage_id FROM plan_import_item WHERE item_id=? AND operation_id=?",
                           (item_id,operation_id)).fetchone()
        if not row:
            raise PlanWriterError("operation_item_mismatch")
        conn.execute("INSERT INTO plan_import_attempt(attempt_id,operation_id,item_id,plan_id,lineage_id,status,created_at) "
                     "VALUES (?,?,?,?,?,'prepared',?)", (attempt_id,operation_id,item_id,*row,_now()))
        _operation_event(conn,attempt_id,"attempt_started",None,item_id)
    return attempt_id


def _operation_event(conn, attempt_id, kind, snapshot_id, item_id, status="confirmed"):
    event_id = "snapshot_committed:"+item_id if kind == "snapshot_committed" else _new_id("event")
    conn.execute("INSERT INTO plan_attempt_event(event_id,attempt_id,stage,status,detail,created_at,event_kind,snapshot_id) "
                 "VALUES (?,?,'archive',?,?,?,?,?)",
                 (event_id,attempt_id,status,item_id,_now(),kind,snapshot_id))
    return event_id


def record_operation_event(conn, attempt_id: str, kind: str, *, detail: str | None = None, status="confirmed"):
    if kind == "snapshot_committed":
        raise PlanWriterError("snapshot_committed requires atomic commit_import_snapshot")
    with _transaction(conn):
        return _operation_event(conn,attempt_id,kind,None,detail,status)


def freeze_import_item(conn, item_id: str, *, frozen_locator: str, source_mpp_sha256: str,
                       size_bytes: int, frozen_at: str, container_sha256=None, container_locator=None,
                       zip_member=None):
    with _transaction(conn):
        row = conn.execute("SELECT frozen_locator,source_mpp_sha256 FROM plan_import_item WHERE item_id=?",(item_id,)).fetchone()
        if not row:
            raise PlanWriterError("item_missing")
        if row[0]:
            if tuple(row) != (frozen_locator,source_mpp_sha256):
                raise PlanWriterError("frozen_input_conflict")
            return
        conn.execute("UPDATE plan_import_item SET frozen_locator=?,source_mpp_sha256=?,size_bytes=?,frozen_at=?,"
                     "container_sha256=?,container_locator=?,zip_member=?,status='frozen' WHERE item_id=?",
                     (frozen_locator,source_mpp_sha256,size_bytes,frozen_at,container_sha256,container_locator,zip_member,item_id))


def fail_import_item(conn, item_id: str, attempt_id: str, error_code: str, *, retryable=False, container_sha256=None, container_locator=None):
    with _transaction(conn):
        row = conn.execute("SELECT item_id FROM plan_import_attempt WHERE attempt_id=?",(attempt_id,)).fetchone()
        if not row or row[0] != item_id:
            raise PlanWriterError("operation_attempt_mismatch")
        conn.execute("UPDATE plan_import_item SET status='failed',error_code=?,retryable=?,container_sha256=coalesce(?,container_sha256),container_locator=coalesce(?,container_locator) WHERE item_id=? AND snapshot_id IS NULL",
                     (error_code,int(retryable),container_sha256,container_locator,item_id))
        _operation_event(conn,attempt_id,"input_failed",None,error_code,"failed")


def commit_import_snapshot(conn, item_id: str, attempt_id: str, spec: SnapshotSpec) -> ImportCommitResult:
    """Single BEGIN IMMEDIATE: snapshot -> versions -> item -> commit event.

    The DB lock serializes competing writers. No public writer is called inside
    this transaction; process death before COMMIT leaves none of its four effects.
    """
    key = snapshot_dedup_key(spec)
    if not key:
        raise PlanWriterError("normalization_profile_required")
    with _transaction(conn):
        item = conn.execute("SELECT operation_id,snapshot_id,source_mpp_sha256,status FROM plan_import_item WHERE item_id=?",
                            (item_id,)).fetchone()
        attempt = conn.execute("SELECT operation_id,item_id FROM plan_import_attempt WHERE attempt_id=?",(attempt_id,)).fetchone()
        if not item or not attempt or tuple(attempt) != (item[0],item_id):
            raise PlanWriterError("operation_attempt_mismatch")
        if item[2] != spec.source_mpp_sha256:
            raise PlanWriterError("source_hash_mismatch")
        if item[1]:
            current = conn.execute("SELECT dedup_key FROM plan_snapshot WHERE snapshot_id=?",(item[1],)).fetchone()
            if not current or current[0] != key:
                raise PlanWriterError("committed_snapshot_conflict")
            verify_snapshot(conn,item[1])
            return ImportCommitResult(item_id,item[1],item[3])
        context=conn.execute("SELECT plan_id,lineage_id FROM plan_operation WHERE operation_id=?",(item[0],)).fetchone()
        scope=conn.execute("SELECT plan_id,lineage_id,normalization_profile_fingerprint,resolved_timezone FROM plan_import_item WHERE item_id=?",(item_id,)).fetchone()
        target=(spec.plan_id,spec.lineage_id,spec.normalization_profile_fingerprint,spec.resolved_timezone)
        if any(v is not None and v != target[i] for i,v in enumerate(scope)) or any(v is not None and v != target[i] for i,v in enumerate(context)):
            raise PlanWriterError("operation_binding_conflict")
        existing = _find_snapshot(conn,spec)
        snapshot_id = existing or spec.snapshot_id or _new_id("snapshot")
        if not existing:
            _insert_snapshot(conn,spec,snapshot_id)
        status = "unchanged" if existing else "saved_with_warnings" if spec.quality_issues or any(c.status != "complete" for c in spec.collections) else "saved"
        conn.execute("UPDATE plan_import_item SET plan_id=?,lineage_id=?,artifact_id=?,snapshot_id=?,"
                     "normalization_profile_fingerprint=?,resolved_timezone=?,dedup_key=?,status=?,error_code=NULL,retryable=0 WHERE item_id=?",
                     (spec.plan_id,spec.lineage_id,spec.source_artifact_id,snapshot_id,spec.normalization_profile_fingerprint,
                      spec.resolved_timezone,key,status,item_id))
        conn.execute("UPDATE plan_operation SET plan_id=?,lineage_id=? WHERE operation_id=? AND (plan_id IS NULL OR plan_id=?)",
                     (spec.plan_id,spec.lineage_id,item[0],spec.plan_id))
        if conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise PlanWriterError("operation_binding_conflict")
        conn.execute("UPDATE plan_import_attempt SET plan_id=?,lineage_id=?,status='confirmed' WHERE attempt_id=?",
                     (spec.plan_id,spec.lineage_id,attempt_id))
        _operation_event(conn,attempt_id,"snapshot_committed",snapshot_id,item_id)
        return ImportCommitResult(item_id,snapshot_id,status)


# Stage 05. Batch lifecycle uses the existing tables and operation event log.
@dataclass(frozen=True)
class BatchItemSpec:
    item_id: str  # external ID, unique within this batch
    path: str
    context_json: str
    source_version_date: str | None = None


def create_batch_with_items(conn, spec: ImportBatchSpec, items: tuple[BatchItemSpec, ...]):
    """Atomically register the immutable request and *all* arrivals, once."""
    manifest = json.loads(spec.manifest_json)
    if hashlib.sha256(_json(manifest).encode()).hexdigest() != spec.manifest_sha256:
        raise PlanWriterError("batch_manifest_hash_mismatch")
    if not items or len({item.item_id for item in items}) != len(items):
        raise PlanWriterError("invalid_batch_items")
    if spec.manifest_version != 1 or spec.status != "freezing_inputs" or spec.on_error != manifest.get("on_error"):
        raise PlanWriterError("invalid_batch_context")
    if [item.item_id for item in items] != [item["item_id"] for item in manifest["items"]]:
        raise PlanWriterError("batch_items_manifest_mismatch")
    with _transaction(conn):
        existing = conn.execute("SELECT manifest_sha256,context_json FROM plan_import_batch WHERE batch_id=?", (spec.batch_id,)).fetchone()
        if existing:
            if tuple(existing) != (spec.manifest_sha256, spec.context_json):
                raise PlanWriterError("batch_manifest_conflict")
            return False
        values = {**asdict(spec), "manifest_json": _json(manifest), "created_at": _now()}
        conn.execute("INSERT INTO plan_import_batch(" + ",".join(values) + ") VALUES (" + ",".join("?" for _ in values) + ")", tuple(values.values()))
        for ordinal, item in enumerate(items, 1):
            identity = hashlib.sha256(_json([spec.batch_id, item.item_id]).encode()).hexdigest()
            internal_id, operation_id = "batch-item-" + identity, "batch-op-" + identity
            conn.execute("INSERT INTO plan_operation(operation_id,action,context_json,created_at) VALUES (?,'save',?,?)",
                         (operation_id, item.context_json, _now()))
            conn.execute("INSERT INTO plan_import_item(item_id,operation_id,batch_id,ordinal,original_name,original_locator,"
                         "transport_json,source_version_date,source_version_basis,received_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (internal_id, operation_id, spec.batch_id, ordinal, Path(item.path).name, item.path,
                          _json({"manifest_item_id": item.item_id}), item.source_version_date,
                          "explicit_user" if item.source_version_date else None, _now()))
    return True


def finalize_batch_freeze(conn, batch_id: str):
    """Publish the barrier only when each arrival has bytes or a terminal error."""
    with _transaction(conn):
        batch = conn.execute("SELECT manifest_json,inputs_frozen_at FROM plan_import_batch WHERE batch_id=?", (batch_id,)).fetchone()
        if not batch:
            raise PlanWriterError("batch_missing")
        if batch[1]:
            return batch[1]
        rows = conn.execute("SELECT frozen_locator,source_mpp_sha256,frozen_at,status,error_code,retryable FROM plan_import_item WHERE batch_id=? ORDER BY ordinal", (batch_id,)).fetchall()
        if len(rows) != len(json.loads(batch[0])["items"]) or any(
                not (r[0] and r[1] and r[2]) and not (r[3] == "failed" and r[4] and not r[5]) for r in rows):
            raise PlanWriterError("inputs_not_frozen")
        now = _now()
        conn.execute("UPDATE plan_import_batch SET inputs_frozen_at=?,status='ready' WHERE batch_id=?", (now, batch_id))
        return now


def start_batch_item(conn, item_id: str):
    """Persist processing intent/attempt before the shared save can read MPP."""
    with _transaction(conn):
        row = conn.execute("SELECT i.operation_id,i.frozen_locator,b.inputs_frozen_at,i.snapshot_id FROM plan_import_item i "
                           "JOIN plan_import_batch b USING(batch_id) WHERE i.item_id=?", (item_id,)).fetchone()
        if not row or not row[2]:
            raise PlanWriterError("inputs_not_frozen")
        if not row[1]:
            raise PlanWriterError("input_freeze_failed")
        if conn.execute("SELECT 1 FROM plan_import_item WHERE batch_id=(SELECT batch_id FROM plan_import_item WHERE item_id=?) "
                        "AND item_id<>? AND status='processing'", (item_id, item_id)).fetchone():
            raise PlanWriterError("batch_item_processing")
        attempt_id = _new_id("attempt")
        conn.execute("INSERT INTO plan_import_attempt(attempt_id,operation_id,item_id,status,created_at) VALUES (?,?,?,'prepared',?)",
                     (attempt_id, row[0], item_id, _now()))
        if not row[3]:
            conn.execute("UPDATE plan_import_item SET status='processing',error_code=NULL,retryable=0 WHERE item_id=?", (item_id,))
        _operation_event(conn, attempt_id, "batch_processing", None, item_id)
        return attempt_id


def finish_batch_item(conn, item_id: str, attempt_id: str, result_json: str):
    """Current result plus append-only event. A commit link is never erased."""
    result = json.loads(result_json)
    status = result["status"]
    if status not in ("saved", "saved_with_warnings", "unchanged", "failed", "needs_decision"):
        raise PlanWriterError("invalid_batch_item_result")
    with _transaction(conn):
        row = conn.execute("SELECT i.snapshot_id FROM plan_import_item i JOIN plan_import_attempt a USING(item_id) "
                           "WHERE i.item_id=? AND a.attempt_id=? AND i.operation_id=a.operation_id", (item_id, attempt_id)).fetchone()
        if not row:
            raise PlanWriterError("operation_attempt_mismatch")
        if status in ("saved", "saved_with_warnings", "unchanged") and not row[0]:
            raise PlanWriterError("snapshot_missing")
        error = result.get("error") or {}
        if not row[0]:
            conn.execute("UPDATE plan_import_item SET status=?,error_code=?,retryable=? WHERE item_id=?",
                         (status, error.get("code"), int(error.get("retryable", False)), item_id))
        _operation_event(conn, attempt_id, "batch_item_result", None, _json(result), "confirmed" if not error else "failed")


def finish_import_batch(conn, batch_id: str, *, status: str, stop_reason: str | None = None):
    if status not in ("completed", "completed_with_errors", "stopped", "infrastructure_stopped"):
        raise PlanWriterError("invalid_batch_status")
    with _transaction(conn):
        row = conn.execute("SELECT inputs_frozen_at FROM plan_import_batch WHERE batch_id=?", (batch_id,)).fetchone()
        if not row:
            raise PlanWriterError("batch_missing")
        if not row[0]:
            raise PlanWriterError("inputs_not_frozen")
        conn.execute("UPDATE plan_import_batch SET status=?,stop_reason=?,completed_at=? WHERE batch_id=?",
                     (status, stop_reason, _now(), batch_id))
