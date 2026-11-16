"""Lossless full-export-v2 (and legacy export) to MofsIndex typed specs. No JVM."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any
from . import writer as plan_writer


def _field_value(field):
    if isinstance(field,dict) and "value" in field:
        return field.get("value"),field.get("quality","unknown")
    return field,"unknown"


def _v(field):
    return _field_value(field)[0]


def _j(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",", ":"))


def _text(field):
    v = _v(field)
    return _j(v) if isinstance(v,(dict,list)) else None if v is None else str(v)


def _num(field):
    v = _v(field)
    try:
        return float(v) if v is not None else None
    except (ValueError,TypeError):
        return None


def _quantity(field):
    if not isinstance(field,dict):
        return {}
    q = field.get("quantity",field.get("value"))
    return q if isinstance(q,dict) else {}


def _amount(field):
    v = _quantity(field).get("amount")
    return None if v is None else str(v)


def _units(field):
    return _quantity(field).get("units")


def task_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.TaskVersionSpec, ...]:
    out=[]
    for t in export.get("tasks",()):
        if "error" in t:
            continue
        simple={name: _text(t.get(key)) for name,key in {
            "start_raw":"start","finish_raw":"finish","duration_raw":"duration",
            "early_start":"early_start","early_finish":"early_finish","late_start":"late_start","late_finish":"late_finish",
            "constraint_type":"constraint_type","constraint_date":"constraint_date","actual_start":"actual_start",
            "actual_finish":"actual_finish","actual_duration_raw":"actual_duration","remaining_duration_raw":"remaining_duration",
            "notes":"notes","source_id":"id","parent_task_key":"parent_task_key","calendar_key":"calendar_key",
            "effective_calendar_key":"effective_calendar_key","task_mode":"task_mode"}.items()}
        segments=tuple(plan_writer.TaskSegmentSpec(_text(s.get("start")),_text(s.get("finish"))) for s in (_v(t.get("segments")) or ()))
        baselines=tuple(plan_writer.BaselineValueSpec(baseline_slot=b["slot"],baseline_start=_text(b.get("start")),
            baseline_finish=_text(b.get("finish")),baseline_duration_raw=_text(b.get("duration")),baseline_work_raw=_text(b.get("work")),
            baseline_cost=_num(b.get("cost")),baseline_cost_decimal=_text(b.get("cost")),source_json=_j(b)) for b in t.get("baseline_values",()))
        out.append(plan_writer.TaskVersionSpec(task_key=t["task_key"],uid=_text(t.get("uid")),wbs=t.get("wbs"),name=t.get("name"),
            outline_level=t.get("outline_level"),percent_complete=_num(t.get("percent_complete")),
            percent_complete_decimal=_text(t.get("percent_complete")),milestone=_v(t.get("milestone")),summary=_v(t.get("summary")),
            duration_amount=_amount(t.get("duration")),duration_units=_units(t.get("duration")),
            duration_elapsed=_quantity(t.get("duration")).get("elapsed"),work_amount=_amount(t.get("work")),work_units=_units(t.get("work")),
            quality="partial" if t.get("issues") else "unknown",source_json=_j(t),segments=segments,baseline_values=baselines,**simple))
    return tuple(out)


def dependency_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.DependencyVersionSpec, ...]:
    return tuple(plan_writer.DependencyVersionSpec(
        predecessor_task_key=d["predecessor_task_key"],successor_task_key=d["successor_task_key"],link_type=_text(d.get("link_type")),
        lag_raw=_text(d.get("lag")),lag_calendar=_text(d.get("lag_calendar")),dependency_key=d.get("dependency_key"),
        lag_amount=_amount(d.get("lag_value")),lag_units=_units(d.get("lag_value")),
        lag_elapsed=_quantity(d.get("lag_value")).get("elapsed"),calendar_basis=_text(d.get("calendar_basis")),source_json=_j(d))
        for d in export.get("dependencies",()) if "error" not in d and d.get("predecessor_task_key") is not None and d.get("successor_task_key") is not None)


def external_dependency_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.ExternalDependencySpec, ...]:
    return tuple(plan_writer.ExternalDependencySpec(local_task_key=e["local_task_key"],direction=e["direction"],reason=e["reason"],
        external_ref=e.get("external_ref")) for e in export.get("external_dependencies",()) if e.get("local_task_key") is not None)


def resource_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.ResourceVersionSpec, ...]:
    return tuple(plan_writer.ResourceVersionSpec(resource_key=r["resource_key"],uid=_text(r.get("uid")),name=r.get("name"),
        type=_text(r.get("type")),email=_text(r.get("email")),resource_group=_text(r.get("group")),max_units=_num(r.get("max_units")),
        max_units_decimal=_text(r.get("max_units")),std_rate_raw=_text(r.get("std_rate")),ot_rate_raw=_text(r.get("ot_rate")),
        cost_per_use=_num(r.get("cost_per_use")),cost_per_use_decimal=_text(r.get("cost_per_use")),calendar_key=_text(r.get("calendar_key")),
        base_calendar_key=_text(r.get("base_calendar_key")),source_json=_j(r),
        availability=tuple(plan_writer.ResourceAvailabilitySpec(available_from=_text(a.get("available_from")),available_to=_text(a.get("available_to")),
            max_units=_num(a.get("max_units")),max_units_decimal=_text(a.get("max_units")),source_json=_j(a)) for a in r.get("availability",())))
        for r in export.get("resources",()) if "error" not in r)


def assignment_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.AssignmentVersionSpec, ...]:
    return tuple(plan_writer.AssignmentVersionSpec(task_key=a["task_key"],resource_key=a["resource_key"],assignment_key=a.get("assignment_key"),
        uid=_text(a.get("uid")),units=_num(a.get("units")),units_decimal=_text(a.get("units")),work_raw=_text(a.get("work")),
        work_amount=_amount(a.get("work")),work_units=_units(a.get("work")),start_raw=_text(a.get("start")),finish_raw=_text(a.get("finish")),
        actual_work_raw=_text(a.get("actual_work")),remaining_work_raw=_text(a.get("remaining_work")),
        effective_calendar_key=_text(a.get("effective_calendar_key")),source_json=_j(a),
        timephased=tuple(plan_writer.TimephasedSpec(period_start=_text(tp["period_start"]),period_end=_text(tp["period_end"]),
            work_raw=_text(tp.get("work")),work_amount=_amount(tp.get("work")),work_units=_units(tp.get("work")),source_json=_j(tp))
            for tp in a.get("timephased",()) if _v(tp.get("period_start")) is not None and _v(tp.get("period_end")) is not None))
        for a in export.get("assignments",()) if "error" not in a and a.get("task_key") is not None and a.get("resource_key") is not None)


def calendar_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.CalendarVersionSpec, ...]:
    out=[]
    for c in export.get("calendars",()):
        if "error" in c:
            continue
        intervals=[]
        for kind,days in (("weekday",c.get("weekdays",())),("exception",c.get("exceptions",()))):
            for day in days:
                label=str(day.get("day")) if kind == "weekday" else f"{_v(day.get('from_date'))}..{_v(day.get('to_date'))}"
                ranges=_v(day.get("intervals")) or ()
                for part in ranges or ({},):
                    intervals.append(plan_writer.CalendarIntervalSpec(kind,label,_v(day.get("working")),
                        _text(part.get("start")),_text(part.get("end"))))
        parent=_text(c.get("parent_key"))
        out.append(plan_writer.CalendarVersionSpec(calendar_key=c["calendar_key"],name=c.get("name"),
            base_calendar_key=parent or _text(c.get("parent_uid")),parent_key=parent,
            minutes_per_day=_num(c.get("minutes_per_day")),minutes_per_week=_num(c.get("minutes_per_week")),
            minutes_per_day_decimal=_text(c.get("minutes_per_day")),minutes_per_week_decimal=_text(c.get("minutes_per_week")),
            source_json=_j(c),intervals=tuple(intervals)))
    return tuple(out)


def collection_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.CollectionStatusSpec, ...]:
    return tuple(plan_writer.CollectionStatusSpec(kind,info.get("status","unsupported"),info.get("count"),info.get("reason"))
                 for kind,info in (export.get("collections") or {}).items())


def quality_issue_specs_from_export(export: dict[str, Any]) -> tuple[plan_writer.QualityIssueSpec, ...]:
    graph=export.get("diagnose_graph") or {}
    out=[]
    for key,severity in (("multiple_roots","warning"),("has_cycle","error"),("has_service_row","info"),
                         ("self_references","error"),("dangling_endpoints","error"),("external_dependencies","warning")):
        if graph.get(key):
            out.append(plan_writer.QualityIssueSpec(key,severity,_j(graph)))
    for name in ("tasks","dependencies","resources","assignments","calendars"):
        for row in export.get(name,()):
            if row.get("error"):
                out.append(plan_writer.QualityIssueSpec("unreadable_"+name,"warning",_j(row)))
    return tuple(out)


def build_snapshot_spec(export: dict[str,Any], *, plan_id: str, lineage_id=None, source_artifact_id=None,
                        representation="mpp",timezone_hint=None,published_at=None,observed_at=None,
                        normalization_profile_fingerprint=None,resolved_timezone=None,source_mpp_sha256=None) -> plan_writer.SnapshotSpec:
    # PreparedPlan carries the profile plus extraction/runtime versions. A bare
    # legacy export remains outside new dedup unless an explicit profile is supplied.
    data=export.get("normalized_data",export)
    source=data.get("source_identity",data.get("provenance",{}))
    profile=normalization_profile_fingerprint
    if profile is None and data.get("normalization"):
        material={"normalization":data["normalization"],"export_version":data.get("export_version"),
                  "schema_version":export.get("schema_version"),"runtime":{k:source.get(k) for k in ("reader","mpxj","jpype")}}
        profile=hashlib.sha256(_j(material).encode()).hexdigest()
    zone=resolved_timezone if resolved_timezone is not None else timezone_hint if timezone_hint is not None else data.get("resolved_timezone")
    zone=plan_writer.normalize_timezone(zone) if profile else None
    raw=_j(data)
    return plan_writer.SnapshotSpec(plan_id=plan_id,lineage_id=lineage_id,source_artifact_id=source_artifact_id,
        representation=representation,timezone_hint=timezone_hint,status_date=_text(data.get("project",{}).get("status_date")),
        published_at=published_at,observed_at=observed_at,normalization_profile_fingerprint=profile,resolved_timezone=zone,
        source_mpp_sha256=source_mpp_sha256 or source.get("sha256"),normalized_data_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        source_json=raw,collections=collection_specs_from_export(data),tasks=task_specs_from_export(data),
        dependencies=dependency_specs_from_export(data),external_dependencies=external_dependency_specs_from_export(data),
        resources=resource_specs_from_export(data),assignments=assignment_specs_from_export(data),calendars=calendar_specs_from_export(data),
        quality_issues=quality_issue_specs_from_export(data))


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
