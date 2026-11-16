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
from dataclasses import dataclass
from datetime import datetime, timezone

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
    row = conn.execute(
        "SELECT plan_id FROM plan WHERE project_slug = ?", (project_slug,)
    ).fetchone()
    if row:
        return row[0]
    plan_id = _new_id("plan")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan(plan_id, project_slug, name, md_path, "
            "default_target, default_representation, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (plan_id, project_slug, name, md_path, default_target,
             default_representation, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
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
    row = conn.execute(
        "SELECT lineage_id FROM plan_lineage "
        "WHERE plan_id = ? AND source_namespace = ? AND page_id IS ?",
        (plan_id, source_namespace, page_id),
    ).fetchone()
    if row:
        return row[0]
    lineage_id = _new_id("lineage")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_lineage(lineage_id, plan_id, source_namespace, "
            "page_id, basis, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (lineage_id, plan_id, source_namespace, page_id, basis, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
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
    row = conn.execute(
        "SELECT artifact_id FROM plan_artifact WHERE raw_sha256 = ?",
        (raw_sha256,),
    ).fetchone()
    if row:
        return row[0]
    artifact_id = _new_id("artifact")
    conn.execute("BEGIN")
    try:
        conn.execute(
            "INSERT INTO plan_artifact(artifact_id, raw_sha256, kind, format, "
            "size_bytes, path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (artifact_id, raw_sha256, kind, format, size_bytes, path, _now()),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
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
    milestone: bool = False
    summary: bool = False
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


@dataclass(frozen=True)
class DependencyVersionSpec:
    predecessor_task_key: str
    successor_task_key: str
    link_type: str | None = None
    lag_raw: str | None = None
    lag_calendar: str | None = None


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


@dataclass(frozen=True)
class TimephasedSpec:
    period_start: str
    period_end: str
    work_raw: str | None = None


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


@dataclass(frozen=True)
class CalendarIntervalSpec:
    interval_kind: str  # 'weekday'|'exception'
    day_or_date: str
    working: bool
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


def ingest_snapshot(conn: sqlite3.Connection, spec: SnapshotSpec) -> str:
    """Записать полный снимок плана ОДНОЙ транзакцией (P2.SCHEMA.1-8).

    Любая ошибка на любом шаге откатывает ВСЮ транзакцию — не остаётся
    полуснимка последним "полным" (AC-116). Повтор с тем же явно переданным
    ``spec.snapshot_id`` идемпотентен на верхнем уровне (не создаёт вторую
    строку ``plan_snapshot`` и не повторяет вложенные вставки)."""
    snapshot_id = spec.snapshot_id or _new_id("snapshot")
    existing = conn.execute(
        "SELECT snapshot_id FROM plan_snapshot WHERE snapshot_id = ?", (snapshot_id,)
    ).fetchone()
    if existing:
        return snapshot_id
    now = _now()
    conn.execute("BEGIN")
    try:
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
                 task.late_finish, task.percent_complete, int(task.milestone),
                 int(task.summary), task.constraint_type, task.constraint_date,
                 task.actual_start, task.actual_finish, task.actual_duration_raw,
                 task.remaining_duration_raw, task.notes, task.quality, task.extensions, now),
            )
            for idx, seg in enumerate(task.segments):
                conn.execute(
                    "INSERT INTO plan_task_segment(segment_id, task_version_id, "
                    "segment_index, start_raw, finish_raw, recorded_at) VALUES (?,?,?,?,?,?)",
                    (_new_id("seg"), task_version_id, idx, seg.start_raw, seg.finish_raw, now),
                )
            for bv in task.baseline_values:
                conn.execute(
                    "INSERT INTO plan_embedded_baseline_value(baseline_value_id, "
                    "task_version_id, baseline_slot, baseline_start, baseline_finish, "
                    "baseline_duration_raw, baseline_work_raw, baseline_cost, recorded_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (_new_id("bv"), task_version_id, bv.baseline_slot, bv.baseline_start,
                     bv.baseline_finish, bv.baseline_duration_raw, bv.baseline_work_raw,
                     bv.baseline_cost, now),
                )

        for dep in spec.dependencies:
            conn.execute(
                "INSERT INTO plan_dependency_version(dependency_version_id, snapshot_id, "
                "predecessor_task_key, successor_task_key, link_type, lag_raw, "
                "lag_calendar, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                (_new_id("dep"), snapshot_id, dep.predecessor_task_key,
                 dep.successor_task_key, dep.link_type, dep.lag_raw, dep.lag_calendar, now),
            )

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
            for av in res.availability:
                conn.execute(
                    "INSERT INTO plan_resource_availability(availability_id, "
                    "resource_version_id, available_from, available_to, max_units, recorded_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (_new_id("avail"), resource_version_id, av.available_from,
                     av.available_to, av.max_units, now),
                )

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
            for tp in asg.timephased:
                conn.execute(
                    "INSERT INTO plan_assignment_timephased(timephased_id, "
                    "assignment_version_id, period_start, period_end, work_raw, recorded_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (_new_id("tp"), assignment_version_id, tp.period_start, tp.period_end,
                     tp.work_raw, now),
                )

        for cal in spec.calendars:
            calendar_version_id = _new_id("calv")
            conn.execute(
                "INSERT INTO plan_calendar_version(calendar_version_id, snapshot_id, "
                "calendar_key, name, base_calendar_key, minutes_per_day, minutes_per_week, "
                "recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                (calendar_version_id, snapshot_id, cal.calendar_key, cal.name,
                 cal.base_calendar_key, cal.minutes_per_day, cal.minutes_per_week, now),
            )
            for interval in cal.intervals:
                conn.execute(
                    "INSERT INTO plan_calendar_interval(interval_id, calendar_version_id, "
                    "interval_kind, day_or_date, working, time_from, time_to, recorded_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (_new_id("iv"), calendar_version_id, interval.interval_kind,
                     interval.day_or_date, int(interval.working), interval.time_from,
                     interval.time_to, now),
                )

        for issue in spec.quality_issues:
            conn.execute(
                "INSERT INTO plan_quality_issue(issue_id, plan_id, lineage_id, snapshot_id, "
                "issue_kind, severity, detail, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                (_new_id("issue"), spec.plan_id, spec.lineage_id, snapshot_id,
                 issue.issue_kind, issue.severity, issue.detail, now),
            )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
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
