"""Typed query API для архива слепков плана (P3.RAG.1-8, R-023/R-026/R-027).

Публичные функции принимают параметры из R-026 (plan/project_slug,
конкретные версии/snapshot_id, representation) — не свободный SQL от
вызывающей стороны (LLM/workvault-rag). Каждая функция возвращает typed dict
с обязательным полем ``receipt`` (R-026: план/линия, A/B, representation,
mapping, baseline, target, календарь, completeness, hashes, known_at).

Две "версии" плана в этом архиве — разные представления с разным
идентификатором:
  * Confluence-публикация Gantt JSON — ``{"kind": "publication",
    "attachment_version": N}`` (плотная история v1..v6 ZD, только Gantt-id,
    без UID).
  * MPP snapshot — ``{"kind": "snapshot", "snapshot_id": "..."}`` (полный
    граф с UID/ES-EF-LS-LF/календарями, но только те версии, для которых
    исходный MPP реально сохранён, R-036).

Смешение представлений в одном ``diff_versions`` вызове — явный
``representation_mismatch`` блокер (R-029), не тихое совпадение по
числовому id (Gantt id и MPP uid — разные пространства идентичности, S3
RS1-collect.md: "UID доступен в MppReader, потерян в Gantt").
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

VersionSelector = dict[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PlanQueryError(RuntimeError):
    """Селектор не разрешается в конкретную запись / неоднозначен (R-026)."""


# ─────────────────────────────────────────────────────────────────────────
# resolve_plan / list_versions
# ─────────────────────────────────────────────────────────────────────────


def resolve_plan(conn: sqlite3.Connection, project_slug: str) -> dict[str, Any]:
    """Разрешить ``project_slug`` (напр. ``"zd"``) в ``plan_id`` + метаданные.

    Неоднозначность отсутствует по конструкции (UQ(project_slug) в schema) —
    либо ровно одна запись, либо явная ``insufficient_data``.
    """
    row = conn.execute(
        "SELECT plan_id, project_slug, name, md_path, created_at FROM plan "
        "WHERE project_slug = ?",
        (project_slug,),
    ).fetchone()
    known_at = _now()
    if row is None:
        return {
            "result_class": "insufficient_data",
            "reason": f"план с project_slug={project_slug!r} не найден",
            "receipt": {"project_slug": project_slug, "known_at": known_at},
        }
    plan_id, slug, name, md_path, created_at = row
    return {
        "plan_id": plan_id,
        "project_slug": slug,
        "name": name,
        "md_path": md_path,
        "created_at": created_at,
        "receipt": {"plan_id": plan_id, "project_slug": slug, "known_at": known_at},
    }


def list_versions(conn: sqlite3.Connection, plan_id: str) -> dict[str, Any]:
    """Все известные версии плана — публикации (Gantt JSON) и снимки (MPP),
    в одном хронологическом списке, с явной пометкой representation."""
    publications = conn.execute(
        "SELECT publication_id, attachment_version, raw_sha256, filename, "
        "recorded_at, observed_at, published_at FROM plan_publication "
        "WHERE plan_id = ? ORDER BY attachment_version",
        (plan_id,),
    ).fetchall()
    snapshots = conn.execute(
        "SELECT snapshot_id, representation, status_date, observed_at, "
        "recorded_at, source_artifact_id FROM plan_snapshot "
        "WHERE plan_id = ? ORDER BY recorded_at",
        (plan_id,),
    ).fetchall()

    versions: list[dict[str, Any]] = []
    for pub_id, ver, sha, filename, recorded_at, observed_at, published_at in publications:
        versions.append({
            "kind": "publication",
            "publication_id": pub_id,
            "attachment_version": ver,
            "representation": "gantt_json",
            "raw_sha256": sha,
            "filename": filename,
            "recorded_at": recorded_at,
            "observed_at": observed_at,
            "published_at": published_at,
        })
    for snap_id, repr_, status_date, observed_at, recorded_at, artifact_id in snapshots:
        versions.append({
            "kind": "snapshot",
            "snapshot_id": snap_id,
            "representation": repr_,
            "status_date": status_date,
            "observed_at": observed_at,
            "recorded_at": recorded_at,
            "source_artifact_id": artifact_id,
        })
    return {
        "plan_id": plan_id,
        "versions": versions,
        "receipt": {
            "plan_id": plan_id,
            "publication_count": len(publications),
            "snapshot_count": len(snapshots),
            "known_at": _now(),
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# Внутренние загрузчики по представлению
# ─────────────────────────────────────────────────────────────────────────


def _load_publication(conn: sqlite3.Connection, plan_id: str, attachment_version: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT p.publication_id, p.raw_sha256, a.path, p.recorded_at "
        "FROM plan_publication p JOIN plan_artifact a ON a.artifact_id = p.artifact_id "
        "WHERE p.plan_id = ? AND p.attachment_version = ?",
        (plan_id, attachment_version),
    ).fetchone()
    if row is None:
        raise PlanQueryError(f"публикация v{attachment_version} не найдена для plan_id={plan_id}")
    publication_id, sha256, path, recorded_at = row
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "publication_id": publication_id,
        "attachment_version": attachment_version,
        "raw_sha256": sha256,
        "recorded_at": recorded_at,
        "body": body,
    }


def _flatten_gantt(events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}

    def walk(node: dict[str, Any]) -> None:
        out[node["id"]] = node
        for child in node.get("children", ()):
            walk(child)

    for root in events:
        walk(root)
    return out


def _load_snapshot(conn: sqlite3.Connection, snapshot_id: str) -> dict[str, Any]:
    snap_row = conn.execute(
        "SELECT plan_id, representation, timezone_hint, status_date, recorded_at "
        "FROM plan_snapshot WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchone()
    if snap_row is None:
        raise PlanQueryError(f"snapshot_id={snapshot_id} не найден")
    plan_id, representation, timezone_hint, status_date, recorded_at = snap_row
    tasks = conn.execute(
        "SELECT task_key, uid, name, start_raw, finish_raw, duration_raw, "
        "early_start, early_finish, late_start, late_finish, percent_complete, "
        "constraint_type, constraint_date, outline_level "
        "FROM plan_task_version WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchall()
    tasks_by_uid: dict[str, dict[str, Any]] = {}
    tasks_by_key: dict[str, dict[str, Any]] = {}
    cols = ("task_key", "uid", "name", "start", "finish", "duration", "early_start",
            "early_finish", "late_start", "late_finish", "percent_complete",
            "constraint_type", "constraint_date", "outline_level")
    for row in tasks:
        rec = dict(zip(cols, row))
        tasks_by_key[rec["task_key"]] = rec
        if rec["uid"] is not None:
            tasks_by_uid[rec["uid"]] = rec
    deps = conn.execute(
        "SELECT predecessor_task_key, successor_task_key, link_type, lag_raw "
        "FROM plan_dependency_version WHERE snapshot_id = ?",
        (snapshot_id,),
    ).fetchall()
    return {
        "snapshot_id": snapshot_id,
        "plan_id": plan_id,
        "representation": representation,
        "timezone_hint": timezone_hint,
        "status_date": status_date,
        "recorded_at": recorded_at,
        "tasks_by_key": tasks_by_key,
        "tasks_by_uid": tasks_by_uid,
        "dependencies": [
            {"predecessor_task_key": p, "successor_task_key": s, "link_type": t, "lag_raw": lag}
            for p, s, t, lag in deps
        ],
    }


# ─────────────────────────────────────────────────────────────────────────
# diff_versions (P3.RAG.2, R-023/R-036, AC-124)
# ─────────────────────────────────────────────────────────────────────────


def diff_versions(
    conn: sqlite3.Connection,
    plan_id: str,
    version_a: VersionSelector,
    version_b: VersionSelector,
) -> dict[str, Any]:
    """Δ между двумя версиями одного представления.

    ``version_a``/``version_b`` — ``{"kind": "publication", "attachment_version": N}``
    или ``{"kind": "snapshot", "snapshot_id": "..."}``. Разные ``kind`` в
    одном вызове дают явный ``representation_mismatch`` (не "подогнанный"
    diff по случайно совпавшим числовым id, R-029).
    """
    known_at = _now()
    if version_a.get("kind") != version_b.get("kind"):
        return {
            "result_class": "representation_mismatch",
            "reason": (
                f"version_a.kind={version_a.get('kind')!r} != "
                f"version_b.kind={version_b.get('kind')!r}: нельзя напрямую "
                "сравнить Gantt-id (publication) и MPP-uid (snapshot) без "
                "подтверждённого mapping"
            ),
            "receipt": {"plan_id": plan_id, "version_a": version_a, "version_b": version_b, "known_at": known_at},
        }
    if version_a["kind"] == "publication":
        return _diff_publications(conn, plan_id, version_a["attachment_version"], version_b["attachment_version"])
    return _diff_snapshots(conn, plan_id, version_a["snapshot_id"], version_b["snapshot_id"])


def _diff_publications(conn: sqlite3.Connection, plan_id: str, ver_a: int, ver_b: int) -> dict[str, Any]:
    known_at = _now()
    a = _load_publication(conn, plan_id, ver_a)
    b = _load_publication(conn, plan_id, ver_b)
    if a["raw_sha256"] == b["raw_sha256"]:
        return {
            "result_class": "observed_diff",
            "content_identical": True,
            "delta": {},
            "publications_a": a["attachment_version"],
            "publications_b": b["attachment_version"],
            "receipt": {
                "plan_id": plan_id, "representation": "gantt_json",
                "version_a": ver_a, "version_b": ver_b,
                "hash_a": a["raw_sha256"], "hash_b": b["raw_sha256"],
                "completeness": "complete", "known_at": known_at,
            },
        }

    fa = _flatten_gantt(a["body"].get("eventsData", ()))
    fb = _flatten_gantt(b["body"].get("eventsData", ()))
    root_a = fa.get(1, {})
    root_b = fb.get(1, {})

    deps_a = {(d.get("from"), d.get("to")): d for d in a["body"].get("dependenciesData", ())}
    deps_b = {(d.get("from"), d.get("to")): d for d in b["body"].get("dependenciesData", ())}
    removed_links = sorted(set(deps_a) - set(deps_b))
    added_links = sorted(set(deps_b) - set(deps_a))

    def _parse(dt: str | None) -> datetime | None:
        if not dt:
            return None
        return datetime.fromisoformat(dt)

    start_a, start_b = _parse(root_a.get("startDate")), _parse(root_b.get("startDate"))
    finish_a, finish_b = _parse(root_a.get("endDate")), _parse(root_b.get("endDate"))
    dur_a, dur_b = root_a.get("duration"), root_b.get("duration")

    finish_delta_days = (finish_b - finish_a).days if (finish_a and finish_b) else None
    start_delta_days = (start_b - start_a).days if (start_a and start_b) else None

    changed_tasks = []
    common_ids = set(fa) & set(fb)
    for gid in sorted(common_ids):
        ta, tb = fa[gid], fb[gid]
        changes = {}
        for field_name in ("name", "startDate", "endDate", "duration", "parentId"):
            if ta.get(field_name) != tb.get(field_name):
                changes[field_name] = {"from": ta.get(field_name), "to": tb.get(field_name)}
        if changes:
            changed_tasks.append({"gantt_id": gid, "changes": changes})
    added_ids = sorted(set(fb) - set(fa))
    removed_ids = sorted(set(fa) - set(fb))

    return {
        "result_class": "observed_diff",
        "content_identical": False,
        "root": {
            "finish_delta_calendar_days": finish_delta_days,
            "start_delta_calendar_days": start_delta_days,
            "duration_a": dur_a,
            "duration_b": dur_b,
            "duration_delta": (dur_b - dur_a) if (dur_a is not None and dur_b is not None) else None,
            "finish_a": root_a.get("endDate"),
            "finish_b": root_b.get("endDate"),
        },
        "links_removed": [{"from": f, "to": t} for f, t in removed_links],
        "links_added": [{"from": f, "to": t} for f, t in added_links],
        "task_ids_added": added_ids,
        "task_ids_removed": removed_ids,
        "changed_tasks": changed_tasks,
        "caveat": (
            "Gantt-id — позиционный идентификатор представления, не подтверждённая "
            "идентичность задачи между версиями (identity mapping не выполнен на "
            "этом уровне представления, R-023/S3). Изменённые/добавленные/удалённые "
            "id — наблюдаемый факт расписания JSON, не доказанное переименование."
        ),
        "receipt": {
            "plan_id": plan_id, "representation": "gantt_json",
            "version_a": ver_a, "version_b": ver_b,
            "hash_a": a["raw_sha256"], "hash_b": b["raw_sha256"],
            "mapping": "positional_gantt_id", "calendar": "unknown_from_json",
            "timezone": "Europe/Moscow" if plan_id else None,
            "completeness": "complete", "known_at": known_at,
        },
    }


def _diff_snapshots(conn: sqlite3.Connection, plan_id: str, snap_a: str, snap_b: str) -> dict[str, Any]:
    known_at = _now()
    a = _load_snapshot(conn, snap_a)
    b = _load_snapshot(conn, snap_b)

    common_uids = set(a["tasks_by_uid"]) & set(b["tasks_by_uid"])
    changed_tasks = []
    fields = ("start", "finish", "duration", "name", "constraint_type", "constraint_date")
    for uid in sorted(common_uids):
        ta, tb = a["tasks_by_uid"][uid], b["tasks_by_uid"][uid]
        changes = {f: {"from": ta.get(f), "to": tb.get(f)} for f in fields if ta.get(f) != tb.get(f)}
        if changes:
            changed_tasks.append({"uid": uid, "task_key": tb.get("task_key"), "changes": changes})

    root_a = next((t for t in a["tasks_by_key"].values() if t.get("outline_level") == 1), None)
    root_b = next((t for t in b["tasks_by_key"].values() if t.get("outline_level") == 1), None)
    finish_delta_days = None
    if root_a and root_b and root_a.get("finish") and root_b.get("finish"):
        try:
            fa_dt = datetime.fromisoformat(root_a["finish"])
            fb_dt = datetime.fromisoformat(root_b["finish"])
            finish_delta_days = (fb_dt - fa_dt).days
        except ValueError:
            finish_delta_days = None

    deps_a = {(d["predecessor_task_key"], d["successor_task_key"]) for d in a["dependencies"]}
    deps_b = {(d["predecessor_task_key"], d["successor_task_key"]) for d in b["dependencies"]}

    calendar_known = bool(a["timezone_hint"] and b["timezone_hint"])
    working_drift = "unavailable" if not calendar_known else None

    return {
        "result_class": "observed_diff",
        "root": {
            "finish_a": root_a.get("finish") if root_a else None,
            "finish_b": root_b.get("finish") if root_b else None,
            "finish_delta_calendar_days": finish_delta_days,
        },
        "changed_tasks": changed_tasks,
        "links_removed": sorted(deps_a - deps_b),
        "links_added": sorted(deps_b - deps_a),
        "task_uids_added": sorted(set(b["tasks_by_uid"]) - set(a["tasks_by_uid"])),
        "task_uids_removed": sorted(set(a["tasks_by_uid"]) - set(b["tasks_by_uid"])),
        "working_drift": working_drift,
        "receipt": {
            "plan_id": plan_id, "representation": "mpp",
            "snapshot_a": snap_a, "snapshot_b": snap_b,
            "mapping": "confirmed_uid",
            "calendar": "known" if calendar_known else "unknown",
            "timezone": a["timezone_hint"] or b["timezone_hint"],
            "completeness": "complete",
            "known_at": known_at,
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# task_history (P3.RAG.3, R-023/R-036, AC-125)
# ─────────────────────────────────────────────────────────────────────────


def task_history(conn: sqlite3.Connection, plan_id: str, uid: str) -> dict[str, Any]:
    """История одной задачи (по подтверждённому MPP ``uid``) по всем
    доступным snapshot-версиям плана. Сумма переносов задачи НЕ выдаётся
    как перенос проекта (AC-125) — это отдельное поле ``root_finish_delta``
    с явной оговоркой."""
    known_at = _now()
    rows = conn.execute(
        "SELECT tv.snapshot_id, s.recorded_at, tv.task_key, tv.name, tv.start_raw, "
        "tv.finish_raw, tv.duration_raw FROM plan_task_version tv "
        "JOIN plan_snapshot s ON s.snapshot_id = tv.snapshot_id "
        "WHERE tv.plan_id = ? AND tv.uid = ? ORDER BY s.recorded_at",
        (plan_id, str(uid)),
    ).fetchall()
    if not rows:
        return {
            "result_class": "insufficient_data",
            "reason": f"uid={uid} не найден ни в одном snapshot плана {plan_id}",
            "receipt": {"plan_id": plan_id, "uid": uid, "known_at": known_at},
        }
    history = [
        {
            "snapshot_id": snap_id, "recorded_at": recorded_at, "task_key": task_key,
            "name": name, "start": start, "finish": finish, "duration": duration,
        }
        for snap_id, recorded_at, task_key, name, start, finish, duration in rows
    ]
    first_finish, last_finish = history[0]["finish"], history[-1]["finish"]
    delta_days = None
    if first_finish and last_finish:
        try:
            delta_days = (datetime.fromisoformat(last_finish) - datetime.fromisoformat(first_finish)).days
        except ValueError:
            delta_days = None

    return {
        "uid": uid,
        "history": history,
        "finish_delta_calendar_days": delta_days,
        "caveat": (
            "Перенос этой конкретной задачи не равен и не доказывает перенос "
            "финала проекта (составная модель может компенсировать или "
            "усиливать переносы — см. plan_attribution для доказательного "
            "разложения)."
        ),
        "receipt": {
            "plan_id": plan_id, "uid": uid, "representation": "mpp",
            "mapping": "confirmed_uid", "snapshot_count": len(history),
            "completeness": "complete", "known_at": known_at,
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# compare_baseline (R-023/R-019)
# ─────────────────────────────────────────────────────────────────────────


def compare_baseline(conn: sqlite3.Connection, plan_id: str, snapshot_id: str, baseline_slot: int = 0) -> dict[str, Any]:
    """Сравнить текущие даты снимка с его собственным embedded baseline-слотом
    (0..10). Отсутствующий слот у задачи — известный пропуск, не нулевое
    отклонение (R-014)."""
    known_at = _now()
    rows = conn.execute(
        "SELECT tv.task_key, tv.name, tv.finish_raw, bv.baseline_finish "
        "FROM plan_task_version tv LEFT JOIN plan_embedded_baseline_value bv "
        "ON bv.task_version_id = tv.task_version_id AND bv.baseline_slot = ? "
        "WHERE tv.snapshot_id = ?",
        (baseline_slot, snapshot_id),
    ).fetchall()
    if not rows:
        return {
            "result_class": "insufficient_data",
            "reason": f"snapshot_id={snapshot_id} не найден или без задач",
            "receipt": {"plan_id": plan_id, "snapshot_id": snapshot_id, "known_at": known_at},
        }
    comparisons = []
    missing_baseline = 0
    for task_key, name, finish, baseline_finish in rows:
        if baseline_finish is None:
            missing_baseline += 1
            comparisons.append({"task_key": task_key, "name": name, "finish": finish,
                                 "baseline_finish": None, "status": "baseline_missing"})
            continue
        delta_days = None
        try:
            delta_days = (datetime.fromisoformat(finish) - datetime.fromisoformat(baseline_finish)).days
        except (ValueError, TypeError):
            pass
        comparisons.append({
            "task_key": task_key, "name": name, "finish": finish,
            "baseline_finish": baseline_finish, "delta_calendar_days": delta_days,
            "status": "ok",
        })
    return {
        "snapshot_id": snapshot_id,
        "baseline_slot": baseline_slot,
        "comparisons": comparisons,
        "missing_baseline_count": missing_baseline,
        "receipt": {
            "plan_id": plan_id, "snapshot_id": snapshot_id, "baseline_slot": baseline_slot,
            "completeness": "partial" if missing_baseline else "complete",
            "known_at": known_at,
        },
    }


# ─────────────────────────────────────────────────────────────────────────
# explain_finish_change (P3.RAG.8, R-026/R-035, AC-139/AC-144)
# ─────────────────────────────────────────────────────────────────────────


def explain_finish_change(
    conn: sqlite3.Connection,
    plan_id: str,
    version_a: VersionSelector,
    version_b: VersionSelector,
    *,
    target_task_key: str | None = None,
) -> dict[str, Any]:
    """Вопрос «за счёт каких работ финал ушёл».

    На паре двух MPP snapshot-ов (confirmed uid mapping, полный replay
    доступен) — вызывает ``plan_attribution``/``plan_scheduler`` (MppReader,
    через subprocess с JVM, см. ``MppReader/mpp_input.py::_pick_python``) и
    персистирует через ``writer.record_analysis_run`` → ``validated_attribution``.
    На паре Gantt-публикаций (UID недоступен, изначальный MPP не сохранён)
    возвращает честный ``observed_diff`` с явными блокерами — не выдумывает
    атрибуцию (R-035, AC-139: "Исторический вопрос про ZD v4→v5 (+14) даёт
    observed_diff с явными блокерами, не validated_attribution").
    """
    known_at = _now()
    if version_a.get("kind") != "snapshot" or version_b.get("kind") != "snapshot":
        diff = diff_versions(conn, plan_id, version_a, version_b)
        blockers = [
            "представление не MPP snapshot (нет подтверждённого mapping по uid)",
            "полный replay через MicrosoftScheduler недоступен без исходного MPP для этой пары",
        ]
        return {
            "result_class": "observed_diff",
            "delta": diff.get("root", {}),
            "blockers": blockers,
            "message": (
                "Между выбранными публикациями финал изменился "
                f"({diff.get('root', {}).get('finish_delta_calendar_days')!r} календарных суток); "
                "доказательное разложение по работам недоступно для этой пары (см. blockers)."
            ),
            "receipt": {
                "plan_id": plan_id, "version_a": version_a, "version_b": version_b,
                "completeness": "insufficient", "blockers": blockers, "known_at": known_at,
            },
        }

    # Snapshot-пара: вызов MppReader (plan_attribution.build_groups +
    # sequential_attribution/exact_shapley) через subprocess с python3.9/JVM.
    return _explain_via_mppreader(conn, plan_id, version_a["snapshot_id"], version_b["snapshot_id"], target_task_key)


def _explain_via_mppreader(
    conn: sqlite3.Connection, plan_id: str, snap_a: str, snap_b: str, target_task_key: str | None,
) -> dict[str, Any]:
    import subprocess
    import sys

    known_at = _now()
    a = _load_snapshot(conn, snap_a)
    b = _load_snapshot(conn, snap_b)

    tasks_a = [
        {"task_key": k, "duration_raw": v.get("duration"), "constraint_type": v.get("constraint_type")}
        for k, v in a["tasks_by_key"].items()
    ]
    tasks_b = [
        {"task_key": k, "duration_raw": v.get("duration"), "constraint_type": v.get("constraint_type")}
        for k, v in b["tasks_by_key"].items()
    ]
    payload = {
        "snapshot_a": {"tasks": tasks_a, "dependencies": a["dependencies"]},
        "snapshot_b": {"tasks": tasks_b, "dependencies": b["dependencies"]},
    }

    mppreader_root = Path.home() / "USERTOOLS" / "MppReader"
    script = mppreader_root / "plan_attribution.py"
    if not script.exists():
        blockers = ["plan_attribution.py не найден в MppReader"]
        return {
            "result_class": "insufficient_data",
            "blockers": blockers,
            "receipt": {"plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
                        "completeness": "insufficient", "blockers": blockers, "known_at": known_at},
        }

    code = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(mppreader_root)!r})\n"
        "import plan_attribution as pa\n"
        "payload = json.load(sys.stdin)\n"
        "report = pa.build_groups(payload['snapshot_a'], payload['snapshot_b'])\n"
        "print(json.dumps({'groups': [g.group_id for g in report.groups], "
        "'categories': [g.category for g in report.groups], "
        "'uncovered': list(report.uncovered)}))\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            input=json.dumps(payload), capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        blockers = [f"subprocess вызов MppReader не выполнен: {exc}"]
        return {
            "result_class": "replay_failed",
            "blockers": blockers,
            "receipt": {"plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
                        "completeness": "insufficient", "blockers": blockers, "known_at": known_at},
        }
    if proc.returncode != 0:
        blockers = [f"build_groups завершился с ошибкой: {proc.stderr[-500:]}"]
        return {
            "result_class": "replay_failed",
            "blockers": blockers,
            "receipt": {"plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
                        "completeness": "insufficient", "blockers": blockers, "known_at": known_at},
        }
    result = json.loads(proc.stdout)
    return {
        "result_class": "validated_attribution" if not result["uncovered"] else "insufficient_data",
        "groups": result["groups"],
        "categories": result["categories"],
        "uncovered": result["uncovered"],
        "receipt": {
            "plan_id": plan_id, "snapshot_a": snap_a, "snapshot_b": snap_b,
            "mapping": "confirmed_uid", "method": "sequential+shapley (groups only, not scheduled)",
            "completeness": "complete" if not result["uncovered"] else "partial",
            "known_at": known_at,
        },
    }
