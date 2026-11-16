"""Конвертер ``MppReader/plan_export.export_full()`` JSON → ``writer.SnapshotSpec``
(P3.SCHEMA.1 доб., используется P3.RAG.2/3 для реальных diff-чисел ZD).

Эта часть НЕ требует JVM/mpxj — она работает с уже сериализованным словарём
(вывод ``plan_export.export_full``, записанный в JSON ``/usr/bin/python3.9
plan_export.py <mpp> --out <json>``), поэтому живёт в ``mofs_index`` (python3,
без JVM) отдельно от самого экспорта (MppReader, требует JVM). Конвертация
чистая: не домысливает поля, которых нет в экспорте (``quality="unknown"``
по умолчанию, не ``"ok"``).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import writer as plan_writer


def _field_value(field: dict[str, Any] | None) -> tuple[Any, str]:
    if not isinstance(field, dict):
        return field, "unknown"
    return field.get("value"), field.get("quality", "unknown")


def _num(field: dict[str, Any] | None) -> float | None:
    value, _ = _field_value(field)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def task_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.TaskVersionSpec, ...]:
    out = []
    for t in export.get("tasks", ()):
        if "error" in t:
            continue
        segments = tuple(
            plan_writer.TaskSegmentSpec(start_raw=s.get("start"), finish_raw=s.get("finish"))
            for s in t.get("segments", ())
        )
        baseline_values = tuple(
            plan_writer.BaselineValueSpec(
                baseline_slot=bv["slot"],
                baseline_start=bv.get("start"),
                baseline_finish=bv.get("finish"),
                baseline_duration_raw=bv.get("duration"),
                baseline_work_raw=bv.get("work"),
                baseline_cost=bv.get("cost"),
            )
            for bv in t.get("baseline_values", ())
        )
        start_v, start_q = _field_value(t.get("start"))
        finish_v, finish_q = _field_value(t.get("finish"))
        dur_v, dur_q = _field_value(t.get("duration"))
        es_v, _ = _field_value(t.get("early_start"))
        ef_v, _ = _field_value(t.get("early_finish"))
        ls_v, _ = _field_value(t.get("late_start"))
        lf_v, _ = _field_value(t.get("late_finish"))
        ct_v, _ = _field_value(t.get("constraint_type"))
        cd_v, _ = _field_value(t.get("constraint_date"))
        as_v, _ = _field_value(t.get("actual_start"))
        af_v, _ = _field_value(t.get("actual_finish"))
        ad_v, _ = _field_value(t.get("actual_duration"))
        rd_v, _ = _field_value(t.get("remaining_duration"))
        notes_v, _ = _field_value(t.get("notes"))
        overall_quality = "ok" if "missing" not in (start_q, finish_q, dur_q) else "partial"
        out.append(plan_writer.TaskVersionSpec(
            task_key=t["task_key"],
            uid=str(t["uid"]) if t.get("uid") is not None else None,
            wbs=t.get("wbs"),
            name=t.get("name"),
            outline_level=t.get("outline_level"),
            start_raw=start_v,
            finish_raw=finish_v,
            duration_raw=dur_v,
            early_start=es_v,
            early_finish=ef_v,
            late_start=ls_v,
            late_finish=lf_v,
            percent_complete=_num(t.get("percent_complete")),
            milestone=bool(t.get("milestone")),
            summary=bool(t.get("summary")),
            constraint_type=ct_v,
            constraint_date=cd_v,
            actual_start=as_v,
            actual_finish=af_v,
            actual_duration_raw=ad_v,
            remaining_duration_raw=rd_v,
            notes=notes_v,
            quality=overall_quality,
            segments=segments,
            baseline_values=baseline_values,
        ))
    return tuple(out)


def dependency_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.DependencyVersionSpec, ...]:
    out = []
    for d in export.get("dependencies", ()):
        lag_v, _ = _field_value(d.get("lag")) if isinstance(d.get("lag"), dict) else (d.get("lag"), "ok")
        lag_cal_v, _ = _field_value(d.get("lag_calendar"))
        out.append(plan_writer.DependencyVersionSpec(
            predecessor_task_key=d["predecessor_task_key"],
            successor_task_key=d["successor_task_key"],
            link_type=d.get("link_type"),
            lag_raw=lag_v if not isinstance(lag_v, dict) else None,
            lag_calendar=lag_cal_v,
        ))
    return tuple(out)


def external_dependency_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.ExternalDependencySpec, ...]:
    return tuple(
        plan_writer.ExternalDependencySpec(
            local_task_key=e["local_task_key"],
            direction=e["direction"],
            reason=e["reason"],
            external_ref=e.get("external_ref"),
        )
        for e in export.get("external_dependencies", ())
    )


def resource_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.ResourceVersionSpec, ...]:
    out = []
    for r in export.get("resources", ()):
        if "error" in r:
            continue
        availability = tuple(
            plan_writer.ResourceAvailabilitySpec(
                available_from=a.get("available_from"),
                available_to=a.get("available_to"),
                max_units=a.get("max_units"),
            )
            for a in r.get("availability", ())
        )
        std_rate_v, _ = _field_value(r.get("std_rate"))
        out.append(plan_writer.ResourceVersionSpec(
            resource_key=r["resource_key"],
            uid=str(r["uid"]) if r.get("uid") is not None else None,
            name=r.get("name"),
            type=r.get("type"),
            email=r.get("email"),
            resource_group=r.get("group"),
            max_units=_num(r.get("max_units")),
            std_rate_raw=std_rate_v,
            cost_per_use=_num(r.get("cost_per_use")),
            availability=availability,
        ))
    return tuple(out)


def assignment_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.AssignmentVersionSpec, ...]:
    out = []
    for a in export.get("assignments", ()):
        if "error" in a or a.get("task_key") is None or a.get("resource_key") is None:
            continue
        timephased = tuple(
            plan_writer.TimephasedSpec(
                period_start=tp["period_start"], period_end=tp["period_end"], work_raw=tp.get("work"),
            )
            for tp in a.get("timephased", ())
        )
        start_v, _ = _field_value(a.get("start"))
        finish_v, _ = _field_value(a.get("finish"))
        work_v, _ = _field_value(a.get("work"))
        aw_v, _ = _field_value(a.get("actual_work"))
        rw_v, _ = _field_value(a.get("remaining_work"))
        out.append(plan_writer.AssignmentVersionSpec(
            task_key=a["task_key"],
            resource_key=a["resource_key"],
            units=_num(a.get("units")),
            work_raw=work_v,
            start_raw=start_v,
            finish_raw=finish_v,
            actual_work_raw=aw_v,
            remaining_work_raw=rw_v,
            timephased=timephased,
        ))
    return tuple(out)


def calendar_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.CalendarVersionSpec, ...]:
    out = []
    for c in export.get("calendars", ()):
        if "error" in c:
            continue
        intervals = []
        for wd in c.get("weekdays", ()):
            intervals.append(plan_writer.CalendarIntervalSpec(
                interval_kind="weekday", day_or_date=str(wd.get("day")), working=bool(wd.get("working")),
            ))
        for exc in c.get("exceptions", ()):
            intervals.append(plan_writer.CalendarIntervalSpec(
                interval_kind="exception",
                day_or_date=f"{exc.get('from_date')}..{exc.get('to_date')}",
                working=bool(exc.get("working")),
            ))
        out.append(plan_writer.CalendarVersionSpec(
            calendar_key=c["calendar_key"],
            name=c.get("name"),
            base_calendar_key=str(c["parent_uid"]) if c.get("parent_uid") is not None else None,
            minutes_per_day=_num(c.get("minutes_per_day")),
            minutes_per_week=_num(c.get("minutes_per_week")),
            intervals=tuple(intervals),
        ))
    return tuple(out)


def collection_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.CollectionStatusSpec, ...]:
    out = []
    for kind, info in (export.get("collections") or {}).items():
        out.append(plan_writer.CollectionStatusSpec(
            collection_kind=kind,
            status=info.get("status", "unsupported"),
            count=info.get("count"),
            reason=info.get("reason"),
        ))
    return tuple(out)


def quality_issue_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.QualityIssueSpec, ...]:
    out = []
    graph = export.get("diagnose_graph") or {}
    if graph.get("multiple_roots"):
        out.append(plan_writer.QualityIssueSpec(
            issue_kind="multiple_roots", severity="warning",
            detail=f"roots={graph.get('roots')}",
        ))
    if graph.get("has_cycle"):
        out.append(plan_writer.QualityIssueSpec(
            issue_kind="dependency_cycle", severity="error",
            detail=f"cycles={graph.get('cycles')}",
        ))
    if graph.get("has_service_row"):
        out.append(plan_writer.QualityIssueSpec(
            issue_kind="service_row", severity="info",
            detail=f"service_rows={graph.get('service_rows')}",
        ))
    return tuple(out)


def build_snapshot_spec(
    export: dict[str, Any],
    *,
    plan_id: str,
    lineage_id: str | None = None,
    source_artifact_id: str | None = None,
    representation: str = "mpp",
    timezone_hint: str | None = None,
    published_at: str | None = None,
    observed_at: str | None = None,
) -> plan_writer.SnapshotSpec:
    """Собрать ``SnapshotSpec`` из словаря ``plan_export.export_full()``.

    Не выдумывает ``status_date``/``timezone_hint`` — если явно не передано
    вызывающей стороной (R-012/R-013), берёт то, что реально в экспорте
    (``project.status_date.value``), иначе ``None``.
    """
    status_date_v, _ = _field_value(export.get("project", {}).get("status_date"))
    return plan_writer.SnapshotSpec(
        plan_id=plan_id,
        lineage_id=lineage_id,
        source_artifact_id=source_artifact_id,
        representation=representation,
        timezone_hint=timezone_hint,
        status_date=status_date_v,
        published_at=published_at,
        observed_at=observed_at,
        collections=collection_specs_from_export(export),
        tasks=task_specs_from_export(export),
        dependencies=dependency_specs_from_export(export),
        external_dependencies=external_dependency_specs_from_export(export),
        resources=resource_specs_from_export(export),
        assignments=assignment_specs_from_export(export),
        calendars=calendar_specs_from_export(export),
        quality_issues=quality_issue_specs_from_export(export),
    )


def ingest_export_json(
    conn,
    json_path: str | Path,
    *,
    plan_id: str,
    lineage_id: str | None = None,
    source_artifact_id: str | None = None,
    representation: str = "mpp",
    timezone_hint: str | None = None,
    published_at: str | None = None,
    observed_at: str | None = None,
) -> str:
    """Прочитать JSON-вывод ``plan_export.export_full`` (выполненный отдельно
    под python3.9/JVM) и записать снимок через ``writer.ingest_snapshot``."""
    export = json.loads(Path(json_path).read_text(encoding="utf-8"))
    spec = build_snapshot_spec(
        export,
        plan_id=plan_id,
        lineage_id=lineage_id,
        source_artifact_id=source_artifact_id,
        representation=representation,
        timezone_hint=timezone_hint,
        published_at=published_at,
        observed_at=observed_at,
    )
    return plan_writer.ingest_snapshot(conn, spec)
