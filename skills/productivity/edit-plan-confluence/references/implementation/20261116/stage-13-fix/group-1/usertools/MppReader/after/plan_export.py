#!/usr/bin/env python3
"""Versioned full MPXJ export. CSV consumers remain in read_mpp.py.

Nullable fields carry value/quality/reason. `missing/not_set` means the getter
returned null, never zero. Getter/serialization failures and absent APIs lower
collection quality. Lists retain failed entries and their deterministic position.
Collection completeness describes extraction, not schedule verification.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_mpp import read_project_file, reader_versions

EXPORT_VERSION = "full-export-v2"
BASELINE_SLOTS = tuple(range(11))


def _s(value):
    if value is None:
        return None
    text = str(value)
    if re.search(r"(?:obj:|object at 0x|@[0-9a-fA-F]{5,})", text):
        raise ValueError("unstable_object_representation")
    return text


def _decimal(value):
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("non_finite_number")
    return format(number.normalize(), "f")


def _duration(value):
    unit = value.getUnits()
    name = str(unit.name())
    amount = _decimal(value.getDuration())
    return {"amount": amount, "units": name, "source_units": str(unit),
            "elapsed": name.startswith("ELAPSED_")}


def _read(obj, getter, convert=_s, *args):
    """Resolve getattr inside the guard, including unsupported getters."""
    try:
        fn = getattr(obj, getter)
    except AttributeError:
        return {"value": None, "quality": "unsupported", "reason": f"getter_unavailable:{getter}"}
    try:
        raw = fn(*args)
        if raw is None:
            return {"value": None, "quality": "missing", "reason": "not_set"}
        value = convert(raw)
        return {"value": value, "quality": "ok", "reason": None}
    except Exception as exc:
        # Stable reason only: Java exception strings may contain file paths or addresses.
        return {"value": None, "quality": "missing", "reason": f"getter_failed:{getter}:{type(exc).__name__}"}


def _raw(obj, getter, *args):
    return _read(obj, getter, lambda v: v, *args)


def _value(obj, getter, convert=_s):
    return _read(obj, getter, convert)["value"]


def _dur_field(obj, getter):
    field = _read(obj, getter, _duration)
    result = dict(field)
    result["quantity"] = field["value"]
    if field["value"] is not None:
        q = field["value"]
        result["value"] = f"{q['amount']} {q['source_units']}"
    return result


def _problem(field):
    return isinstance(field, dict) and field.get("quality") in ("missing", "unsupported", "partial") and field.get("reason") != "not_set"


def _issues(value, path=""):
    result = []
    if isinstance(value, dict):
        if value.get("status") in ("partial", "missing", "unsupported") and value.get("reason") != "not_set":
            result.append({"field": path, "quality": value["status"], "reason": value.get("reason")})
        if _problem(value):
            result.append({"field": path, "quality": value["quality"], "reason": value.get("reason")})
        for key, item in value.items():
            if key != "quality_issues":
                result.extend(_issues(item, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            result.extend(_issues(item, f"{path}[{i}]"))
    return result


def _finish(row):
    row["quality_issues"] = _issues(row)
    return row


class _Keys:
    """Project-local deterministic IDs; object references never enter the export."""
    def __init__(self, objects, kind):
        self.kind = kind
        self.entries = []
        counts = {}
        for position, obj in enumerate(objects):
            uid = _read(obj, "getUniqueID", int)
            tid = _read(obj, "getID", int)
            key = f"uid:{uid['value']}" if uid["value"] is not None else (
                f"id:{tid['value']}" if tid["value"] is not None else f"local:{kind}:{position:06d}")
            counts[key] = counts.get(key, 0) + 1
            quality = {"value": key, "quality": "ok", "reason": None}
            if key.startswith("local:"):
                quality.update(quality="partial", reason="no_stable_source_id")
            if counts[key] > 1:
                key += f"#row:{position}"
                quality.update(value=key, quality="partial", reason="duplicate_source_id")
            self.entries.append((obj, key, quality))

    def get(self, obj):
        if obj is None:
            return None
        for candidate, key, _ in self.entries:
            if candidate == obj:
                return key
        uid = _value(obj, "getUniqueID", int)
        tid = _value(obj, "getID", int)
        return f"external:{self.kind}:uid:{uid}" if uid is not None else (
            f"external:{self.kind}:id:{tid}" if tid is not None else f"external:{self.kind}:unresolved")

    def quality(self, obj):
        return next(q for candidate, _, q in self.entries if candidate == obj)


def _sequence(obj, getter):
    f = _read(obj, getter, list)
    if f["value"] is None:
        return [], {"status": f["quality"], "count": 0, "reason": f["reason"]}
    return [v for v in f["value"] if v is not None], {"status": "complete", "count": len(f["value"]), "reason": None}


def _collection_status(items, *, allow_empty=True, source=None):
    if source and source["status"] != "complete":
        return source
    errors = sum("error" in i for i in items)
    problems = sum(bool(_issues(i)) for i in items)
    status = "missing" if not items and not allow_empty else "complete"
    reason = "empty_required_collection" if status == "missing" else None
    if errors or problems:
        status = "missing" if errors == len(items) else "partial"
        reason = f"read_errors:{errors};items_with_field_issues:{problems}"
    return {"status": status, "count": len(items) - errors, "reason": reason,
            "error_count": errors, "record_count": len(items)}


def _ranges(ranges):
    """MPXJ work ranges (not gaps); preserve every period without interpretation."""
    if ranges is None:
        return []
    return [{"start": _read(rng, "getStart"), "end": _read(rng, "getEnd")} for rng in ranges]


def _timephased(assignment):
    """16.4.0: raw source series and parameterized actual+remaining projection.

    Raw planned is a distinct source, never substituted by actual+remaining.
    The projection uses explicit source period boundaries, HOURS, and labels
    its basis. No generated planned series is presented as extracted raw data.
    """
    from java.util import ArrayList
    from org.mpxj import LocalDateTimeRange, TimeUnit
    raw = {}
    boundaries = set()
    for kind, getter in [("planned", "getRawTimephasedPlannedWork"),
                         ("actual_regular", "getRawTimephasedActualRegularWork"),
                         ("remaining_regular", "getRawTimephasedRemainingRegularWork"),
                         ("actual_overtime", "getRawTimephasedActualOvertimeWork"),
                         ("remaining_overtime", "getRawTimephasedRemainingOvertimeWork")]:
        result = _read(assignment, getter, list)
        rows = []
        for period in result["value"] or []:
            start, finish = period.getStart(), period.getFinish()
            if start is not None: boundaries.add(start)
            if finish is not None: boundaries.add(finish)
            rows.append({"period_start": _read(period, "getStart"),
                         "period_end": _read(period, "getFinish"),
                         "work": _dur_field(period, "getTotalAmount"),
                         "work_per_hour": _dur_field(period, "getAmountPerHour")})
        raw[kind] = {**result, "value": rows if result["value"] is not None else None}
    ranges = ArrayList()
    dates = sorted(boundaries)
    for start, finish in zip(dates, dates[1:]):
        if start < finish: ranges.add(LocalDateTimeRange(start, finish))
    projected = _read(assignment, "getTimephasedWork", list, ranges, TimeUnit.HOURS)
    rows = []
    for period, work in zip(ranges, projected["value"] or []):
        rows.append({"period_start": _read(period, "getStart"), "period_end": _read(period, "getEnd"),
                     "work": {"value": None if work is None else str(work),
                              "quantity": None if work is None else _duration(work),
                              "quality": "missing" if work is None else "ok",
                              "reason": "not_set" if work is None else None}})
    quality = {"status": "complete" if projected["quality"] == "ok" else projected["quality"],
               "count": len(rows), "reason": projected["reason"],
               "basis": "actual_plus_remaining", "units": "HOURS"}
    return rows, quality, raw


def _relation_audit(project):
    """Observation emitted by the patched reader in its existing binary pass."""
    try:
        from org.mpxj.mpp import RelationReadAudit
        audit = RelationReadAudit.get(project)
        if audit is None:
            raise ValueError("no_audit_for_reader_format")
        records = []
        for row in audit.get("records"):
            records.append({str(k): (int(v) if str(k) in ("uid", "predecessor_uid", "successor_uid", "type_code", "position") else str(v))
                            for k,v in row.entrySet()})
        expected = int(audit.get("expected_count"))
        complete = bool(audit.get("complete")) and len(records) == expected
        return {"value": {"records": records, "expected_count": expected,
                          "observed_count": len(records), "enumeration_complete": complete},
                "quality": "ok" if complete else "partial",
                "reason": None if complete else "raw_relation_enumeration_incomplete"}
    except Exception as exc:
        return {"value": None, "quality": "unsupported", "reason": "raw_relation_audit_unavailable:" + type(exc).__name__}


def _collect_tasks(project, *, objects=None, keys=None, calendars=None):
    objects = objects if objects is not None else _sequence(project, "getTasks")[0]
    keys = keys or _Keys(objects, "task")
    calendars = calendars or _Keys(_sequence(project, "getCalendars")[0], "calendar")
    out = []
    fields = {"start": "getStart", "finish": "getFinish", "early_start": "getEarlyStart",
              "early_finish": "getEarlyFinish", "late_start": "getLateStart", "late_finish": "getLateFinish",
              "constraint_type": "getConstraintType", "constraint_date": "getConstraintDate",
              "secondary_constraint_type": "getSecondaryConstraintType", "secondary_constraint_date": "getSecondaryConstraintDate",
              "actual_start": "getActualStart", "actual_finish": "getActualFinish", "deadline": "getDeadline",
              "task_mode": "getTaskMode", "task_type": "getType", "stop": "getStop", "resume": "getResume",
              "scheduled_start": "getScheduledStart", "scheduled_finish": "getScheduledFinish", "notes": "getNotes",
              "external_project": "getExternalProject", "subproject_file": "getSubprojectFile"}
    for t in objects:
        if _value(t, "getNull", bool) is True:
            continue  # MPXJ's explicit blank row is not a readable task.
        row = {"task_key": keys.get(t), "identity_quality": keys.quality(t)}
        fq = {}
        for name, getter, convert in [("id", "getID", int), ("uid", "getUniqueID", int), ("wbs", "getWBS", _s),
                                      ("name", "getName", _s), ("outline_level", "getOutlineLevel", int),
                                      ("outline_number", "getOutlineNumber", _s), ("milestone", "getMilestone", bool),
                                      ("summary", "getSummary", bool)]:
            fq[name] = _read(t, getter, convert)
            row[name] = fq[name]["value"]
        row["field_quality"] = fq
        row.update({name: _read(t, getter) for name, getter in fields.items()})
        for name in ("duration", "actual_duration", "remaining_duration", "manual_duration", "scheduled_duration",
                     "work", "actual_work", "remaining_work", "leveling_delay", "total_slack", "free_slack"):
            row[name] = _dur_field(t, "get" + "".join(w.title() for w in name.split("_")))
        for name, getter in [("percent_complete", "getPercentageComplete"), ("percent_work_complete", "getPercentageWorkComplete")]:
            row[name] = _read(t, getter, _decimal)
        for name, getter in [("effort_driven", "getEffortDriven"), ("ignore_resource_calendar", "getIgnoreResourceCalendar"),
                             ("active", "getActive"), ("external_task", "getExternalTask"), ("estimated", "getEstimated"),
                             ("leveling_can_split", "getLevelingCanSplit")]:
            row[name] = _read(t, getter, bool)
        row["parent_task_key"] = _read(t, "getParentTask", keys.get)
        row["child_task_keys"] = _read(t, "getChildTasks", lambda ts: [keys.get(c) for c in ts])
        row["calendar_key"] = _read(t, "getCalendar", calendars.get)
        row["effective_calendar_key"] = _read(t, "getEffectiveCalendar", calendars.get)
        row["calendar_uid"] = _read(t, "getCalendarUniqueID", int)
        row["segments"] = _read(t, "getWorkSplits", _ranges)
        row["segments_quality"] = row["segments"]["quality"]
        baselines = []
        for slot in BASELINE_SLOTS:
            vals = {"start": _read(t, "getBaselineStart", _s, *(() if slot == 0 else (slot,))),
                    "finish": _read(t, "getBaselineFinish", _s, *(() if slot == 0 else (slot,)))}
            for name in ("duration", "work"):
                vals[name] = _read(t, "getBaseline" + name.title(), _duration, *(() if slot == 0 else (slot,)))
            vals["cost"] = _read(t, "getBaselineCost", _decimal, *(() if slot == 0 else (slot,)))
            if any(v["value"] is not None or _problem(v) for v in vals.values()):
                baselines.append({"slot": slot, **{k: v["value"] for k, v in vals.items()}, "field_quality": vals})
        row["baseline_values"] = baselines
        if all(row[k] is None for k in ("id", "uid", "name")):
            row["error"] = "task_identity_unreadable"
        out.append(_finish(row))
    return out, {"errors": sum("error" in r for r in out)}


def _collect_dependencies(project, *, objects=None, keys=None):
    objects = objects if objects is not None else _sequence(project, "getTasks")[0]
    keys = keys or _Keys(objects, "task")
    deps, external = [], []
    for t in objects:
        rels, status = _sequence(t, "getPredecessors")
        if status["status"] != "complete":
            deps.append({"error": "predecessors_unreadable", "local_task_key": keys.get(t), "source_quality": status})
        for r in rels:
            pred = _raw(r, "getPredecessorTask")
            succ = _raw(r, "getSuccessorTask")
            p, s = pred["value"], succ["value"]
            lag = _read(r, "getLag", _duration)
            typ = _read(r, "getType")
            mapping = {"FS": "FS", "SS": "SS", "FF": "FF", "SF": "SF", "FINISH_START": "FS",
                       "START_START": "SS", "FINISH_FINISH": "FF", "START_FINISH": "SF"}
            normalized = mapping.get(typ["value"])
            row = {"dependency_key": f"local:dependency:{len(deps):06d}", "uid": _read(r, "getUniqueID", int),
                   "predecessor_task_key": keys.get(p), "successor_task_key": keys.get(s),
                   "predecessor_id": _read(p, "getID", int), "predecessor_uid": _read(p, "getUniqueID", int),
                   "successor_id": _read(s, "getID", int), "successor_uid": _read(s, "getUniqueID", int),
                   "source_link_type": typ, "link_type": normalized,
                   "type_quality": {"value": normalized, "quality": "ok" if normalized else typ["quality"] if typ["quality"] != "ok" else "unsupported",
                                    "reason": None if normalized else typ["reason"] or "unknown_relation_type"},
                   "lag": None if lag["value"] is None else f"{lag['value']['amount']} {lag['value']['source_units']}",
                   "lag_value": lag, "lag_calendar": _read(project.getProjectProperties(), "getRelationshipLagCalendar"),
                   "project_lag_calendar": _read(project.getProjectProperties(), "getRelationshipLagCalendar"),
                   "driving": _read(r, "getDriving", bool),
                   "endpoint_quality": {"predecessor": {k:v for k,v in pred.items() if k != "value"},
                                        "successor": {k:v for k,v in succ.items() if k != "value"}}}
            is_external = any(k is not None and k.startswith("external:") for k in [keys.get(p), keys.get(s)])
            is_external = is_external or any(_value(o, "getExternalTask", bool) is True for o in [p,s] if o is not None)
            row["external"] = is_external
            deps.append(_finish(row))
            if p is None or s is None or is_external:
                external.append({"local_task_key": keys.get(t), "dependency_key": row["dependency_key"],
                                 "direction": "predecessor", "external_ref": _read(p, "getExternalProject"),
                                 "reason": "external_relation" if is_external else "dangling_relation"})
    return deps, external


def _collect_resources(project, *, objects=None, keys=None, calendars=None):
    objects = objects if objects is not None else _sequence(project, "getResources")[0]
    keys = keys or _Keys(objects, "resource")
    calendars = calendars or _Keys(_sequence(project, "getCalendars")[0], "calendar")
    out = []
    for r in objects:
        row = {"resource_key": keys.get(r), "identity_quality": keys.quality(r)}
        for name, getter in [("id", "getID"), ("uid", "getUniqueID"), ("name", "getName"), ("type", "getType"),
                             ("email", "getEmailAddress"), ("group", "getGroup")]:
            f = _read(r, getter, int if name in ("id", "uid") else _s)
            row[name] = f["value"]
            row.setdefault("field_quality", {})[name] = f
        for name, getter, convert in [("max_units", "getMaxUnits", _decimal), ("std_rate", "getStandardRate", _s),
                                      ("cost_per_use", "getCostPerUse", _decimal), ("calendar_key", "getCalendar", calendars.get),
                                      ("base_calendar_key", "getBaseCalendar", calendars.get), ("calendar_uid", "getCalendarUniqueID", int),
                                      ("start", "getStart", _s), ("finish", "getFinish", _s)]:
            row[name] = _read(r, getter, convert)
        avail, quality = _sequence(r, "getAvailability")
        row["availability"] = []
        for a in avail:
            rng = _raw(a, "getRange")
            row["availability"].append({"available_from": _read(rng["value"], "getStart"),
                                         "available_to": _read(rng["value"], "getEnd"), "max_units": _read(a, "getUnits", _decimal)})
        row["availability_quality"] = quality
        out.append(_finish(row))
    return out


def _collect_assignments(project, *, objects=None, keys=None, tasks=None, resources=None, calendars=None):
    objects = objects if objects is not None else _sequence(project, "getResourceAssignments")[0]
    keys = keys or _Keys(objects, "assignment")
    tasks = tasks or _Keys(_sequence(project, "getTasks")[0], "task")
    resources = resources or _Keys(_sequence(project, "getResources")[0], "resource")
    calendars = calendars or _Keys(_sequence(project, "getCalendars")[0], "calendar")
    out = []
    for a in objects:
        task, res = _raw(a, "getTask"), _raw(a, "getResource")
        row = {"assignment_key": keys.get(a), "identity_quality": keys.quality(a), "uid": _read(a, "getUniqueID", int),
               "task_key": tasks.get(task["value"]), "resource_key": resources.get(res["value"]),
               "task_uid": _read(a, "getTaskUniqueID", int), "resource_uid": _read(a, "getResourceUniqueID", int),
               "endpoint_quality": {"task": {k:v for k,v in task.items() if k != "value"},
                                    "resource": {k:v for k,v in res.items() if k != "value"}}}
        for name in ("start", "finish", "actual_start", "actual_finish", "stop", "resume", "work_contour"):
            row[name] = _read(a, "get" + "".join(w.title() for w in name.split("_")))
        for name in ("work", "actual_work", "remaining_work", "overtime_work", "delay", "leveling_delay"):
            row[name] = _dur_field(a, "get" + "".join(w.title() for w in name.split("_")))
        row["units"] = _read(a, "getUnits", _decimal)
        row["effective_calendar_key"] = _read(a, "getEffectiveCalendar", calendars.get)
        row["segments"] = _read(a, "getWorkSplits", _ranges)
        row["timephased"], row["timephased_quality"], row["raw_timephased"] = _timephased(a)
        out.append(_finish(row))
    return out


def _calendar_days(cal):
    from java.time import DayOfWeek
    days = []
    for day in DayOfWeek.values():
        hours = _read(cal, "getCalendarHours", _ranges, day)
        days.append({"day": str(day), "day_type": _read(cal, "getCalendarDayType", _s, day),
                     "working": _read(cal, "isWorkingDay", bool, day), "intervals": hours})
    return days


def _recurrence(data):
    fields = {"start_date": "getStartDate", "finish_date": "getFinishDate", "type": "getRecurrenceType",
              "frequency": "getFrequency", "occurrences": "getOccurrences", "day_number": "getDayNumber",
              "day_of_week": "getDayOfWeek", "month_number": "getMonthNumber", "relative": "getRelative",
              "use_end_date": "getUseEndDate", "working_days_only": "getWorkingDaysOnly"}
    out = {name: _read(data, getter) for name, getter in fields.items()}
    from java.time import DayOfWeek
    out["weekly_days"] = {str(d): _read(data, "getWeeklyDay", bool, d) for d in DayOfWeek.values()}
    return out


def _collect_calendars(project, *, objects=None, keys=None):
    objects = objects if objects is not None else _sequence(project, "getCalendars")[0]
    keys = keys or _Keys(objects, "calendar")
    out = []
    for cal in objects:
        row = {"calendar_key": keys.get(cal), "identity_quality": keys.quality(cal),
               "name": _value(cal, "getName"), "uid": _read(cal, "getUniqueID", int),
               "parent_uid": _value(cal, "getParentUniqueID", int), "parent_key": _read(cal, "getParent", keys.get),
               "type": _read(cal, "getType"), "personal": _read(cal, "getPersonal", bool)}
        for suffix in ("Day", "Week", "Month", "Year"):
            row["minutes_per_" + suffix.lower()] = _read(cal, "getCalendarMinutesPer" + suffix, _decimal)
        row["weekdays"] = _calendar_days(cal)
        row["weekdays_quality"] = "partial" if _issues(row["weekdays"]) else "ok"
        exceptions, excq = _sequence(cal, "getCalendarExceptions")
        row["exceptions"] = [{"name": _read(e, "getName"), "from_date": _read(e, "getFromDate"),
                              "to_date": _read(e, "getToDate"), "working": _read(e, "getWorking", bool),
                              "intervals": _read(e, "iterator", lambda it: _ranges(it)),
                              "recurrence": _read(e, "getRecurring", _recurrence)} for e in exceptions]
        row["exceptions_quality"] = excq
        weeks, wq = _sequence(cal, "getWorkWeeks")
        row["work_weeks"] = [{"name": _read(w, "getName"), "date_range": _read(w, "getDateRange", lambda r:
                              {"start": _read(r, "getStart"), "end": _read(r, "getEnd")}),
                              "weekdays": _calendar_days(w)} for w in weeks]
        row["work_weeks_quality"] = wq
        out.append(_finish(row))
    return out


def diagnose_graph(tasks, dependencies, external_dependencies=None):
    """Structural diagnostics only; no scheduler claim or graph mutation."""
    valid = [t for t in tasks if "error" not in t]
    keys = {t["task_key"] for t in valid}
    roots = [t["task_key"] for t in valid if t.get("outline_level") == 1 and t.get("id") != 0]
    service = [t["task_key"] for t in valid if t.get("id") == 0]
    adjacency, self_refs, dangling, external = {}, [], [], []
    for i, d in enumerate(dependencies):
        if "error" in d:
            continue
        p, s = d.get("predecessor_task_key"), d.get("successor_task_key")
        ref = d.get("dependency_key", f"row:{i}")
        if p == s and p is not None:
            self_refs.append(ref)
        if p not in keys or s not in keys:
            dangling.append({"dependency_key": ref, "predecessor": p, "successor": s})
        if d.get("external"):
            external.append(ref)
        if p in keys and s in keys:
            adjacency.setdefault(p, []).append(s)
    # Iterative DFS supports long plans without Python recursion limits.
    cycles, done, active, path = [], set(), set(), []
    for node in sorted(keys):
        if node in done:
            continue
        stack = [(node, iter(adjacency.get(node, [])))]
        active.add(node); path.append(node)
        while stack:
            current, children = stack[-1]
            nxt = next(children, None)
            if nxt is None:
                stack.pop(); done.add(current); active.remove(current); path.pop()
            elif nxt in active:
                cycles.append(path[path.index(nxt):] + [nxt])
            elif nxt not in done:
                active.add(nxt); path.append(nxt); stack.append((nxt, iter(adjacency.get(nxt, []))))
    return {"roots": roots, "multiple_roots": len(roots) > 1, "service_rows": service, "has_service_row": bool(service),
            "cycles": cycles, "has_cycle": bool(cycles), "self_references": self_refs,
            "dangling_dependencies": dangling, "external_dependencies": external,
            "external_records": external_dependencies or [], "schedule_status": "not_verified"}


def export_full(path: str | Path, *, read_observer=None):
    src = Path(path).expanduser().resolve()
    raw = src.read_bytes()
    count = 0
    def observe(event):
        nonlocal count
        count += 1
        if read_observer:
            read_observer(event)
    project = read_project_file(str(src), read_observer=observe)
    props = project.getProjectProperties()
    inputs, sources, keys = {}, {}, {}
    for kind, getter in [("task", "getTasks"), ("resource", "getResources"), ("assignment", "getResourceAssignments"), ("calendar", "getCalendars")]:
        inputs[kind], sources[kind] = _sequence(project, getter)
        keys[kind] = _Keys(inputs[kind], kind)
    tasks, _ = _collect_tasks(project, objects=inputs["task"], keys=keys["task"], calendars=keys["calendar"])
    deps, external = _collect_dependencies(project, objects=inputs["task"], keys=keys["task"])
    resources = _collect_resources(project, objects=inputs["resource"], keys=keys["resource"], calendars=keys["calendar"])
    assignments = _collect_assignments(project, objects=inputs["assignment"], keys=keys["assignment"], tasks=keys["task"],
                                       resources=keys["resource"], calendars=keys["calendar"])
    calendars = _collect_calendars(project, objects=inputs["calendar"], keys=keys["calendar"])
    project_info = {"name": _value(props, "getProjectTitle"), "author": _value(props, "getAuthor"), "company": _value(props, "getCompany"),
                    "start_date": _value(props, "getStartDate"), "finish_date": _value(props, "getFinishDate"),
                    "status_date": _read(props, "getStatusDate"), "default_calendar": _read(props, "getDefaultCalendar", lambda c: _value(c, "getName")),
                    "default_calendar_key": _read(props, "getDefaultCalendar", keys["calendar"].get),
                    "field_quality": {k: _read(props,g) for k,g in [("name","getProjectTitle"),("author","getAuthor"),
                        ("company","getCompany"),("start_date","getStartDate"),("finish_date","getFinishDate")]}}
    for suffix in ("Day", "Week", "Month", "Year"):
        project_info["minutes_per_" + suffix.lower()] = _read(props, "getMinutesPer" + suffix, _decimal)
    for name, getter in [("days_per_month", "getDaysPerMonth"), ("default_duration_units", "getDefaultDurationUnits"),
                          ("default_work_units", "getDefaultWorkUnits"), ("schedule_from", "getScheduleFrom"),
                          ("relationship_lag_calendar", "getRelationshipLagCalendar"), ("default_start_time", "getDefaultStartTime"),
                          ("default_end_time", "getDefaultEndTime"), ("split_in_progress_tasks", "getSplitInProgressTasks")]:
        project_info[name] = _read(props, getter)
    collections = {name: _collection_status(rows, allow_empty=name not in ("tasks", "calendars"), source=sources[kind])
                   for name, rows, kind in [("tasks", tasks, "task"), ("resources", resources, "resource"),
                                             ("assignments", assignments, "assignment"), ("calendars", calendars, "calendar")]}
    collections["dependencies"] = _collection_status(deps, source=sources["task"])
    collections["external_dependencies"] = _collection_status(external)
    collections["baseline_values"] = _collection_status([b for t in tasks for b in t.get("baseline_values", [])])
    graph = diagnose_graph(tasks, deps, external)
    audit = _relation_audit(project)
    graph["raw_relation_enumeration"] = audit
    records = (audit["value"] or {}).get("records", [])
    discarded = [row for row in records if row["disposition"] not in ("represented", "deleted")]
    graph["discarded_relation_records"] = discarded
    enumeration_complete = audit["quality"] == "ok"
    collections["dependencies"]["enumeration_complete"] = enumeration_complete
    collections["dependencies"]["source_record_count"] = len(records)
    from collections import Counter
    represented = [row for row in records if row['disposition'] == 'represented']
    visible_matches = (Counter(row.get('uid') for row in represented) ==
                       Counter(row.get('uid',{}).get('value') for row in deps))
    graph['raw_relation_enumeration']['visible_records_match'] = visible_matches
    if not enumeration_complete or discarded or not visible_matches:
        collections["dependencies"].update(status="partial",
            reason="raw_relations_discarded" if discarded else "raw_visible_relation_mismatch" if not visible_matches else audit["reason"])
    if src.read_bytes() != raw:
        raise RuntimeError("input_changed_during_MPXJ_read")
    return {"export_version": EXPORT_VERSION, "source": str(src),
            "provenance": {"source_path": str(src), "original_name": src.name, "source_origin": "local_file",
                           "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw),
                           "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **reader_versions()},
            "timezone_hint": None, "project": project_info, "collections": collections,
            "tasks": tasks, "dependencies": deps, "external_dependencies": external, "resources": resources,
            "assignments": assignments, "calendars": calendars, "diagnose_graph": graph,
            "summary_inputs": {"root_candidates": graph["roots"], "rule": "source-values-only;summary-v1 deferred to stage-08",
                               "computed": {"value": None, "quality": "unsupported", "reason": "summary_profile_not_applied"}},
            "telemetry": {"MPXJ_read": count}}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Полный экспорт MS Project")
    parser.add_argument("path")
    parser.add_argument("--out")
    args = parser.parse_args()
    payload = json.dumps(export_full(args.path), ensure_ascii=False, indent=2, allow_nan=False)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
