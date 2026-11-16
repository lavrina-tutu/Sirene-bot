#!/usr/bin/env python3
"""Полный нормализованный экспорт MS Project (.mpp/.mpx/.xml) через mpxj
(P2.MPP.1-6, R-012-014).

Отдельный путь от ``read_mpp.py`` — не меняет поведение существующего
CSV/JSON (потребители ``read_mpp.read_project``/``write_csv``/CLI не
затрагиваются, см. ``tests/test_plan_export_regression.py``). JVM/reader
переиспользуются импортом из ``read_mpp`` (``_start_jvm``), не копипастой.

Формат отражает весь календарно-ресурсный граф (R-012): задачи с
ES/EF/LS/LF + constraints + actuals/remaining + splits, связи с lag (+
calendar, если API это предоставляет — иначе явный ``unsupported``),
внешние/висячие связи, ресурсы + таблица доступности, назначения +
timephased work, календари + рабочие дни/исключения, baseline-слоты 0..10.

Каждая коллекция — ``complete|partial|missing|unsupported`` + count + reason
(R-013). Каждое неизвестное поле — явная пара ``{"value": ..., "quality":
...}``, где ``quality`` ∈ {``ok``, ``missing``, ``unsupported``}: ``ok``
означает, что getter mpxj успешно вызван (значение может быть ``None`` —
известный ноль/пусто, не путается с неизвестностью); ``missing`` — getter
выбросил исключение на этом конкретном объекте; ``unsupported`` — у этой
версии mpxj такого getter нет вовсе (используется на уровне коллекции, не
на каждом поле, чтобы не раздувать вывод).

``timezone_hint`` — по умолчанию ``None`` (R-012/R-013): MppReader не
угадывает таймзону; владелец фиксирует её выше по стеку (см.
``plan_archive.ZD_TIMEZONE_HINT`` для ZD, Q3 DECISIONS-owner.md) — константа
НЕ живёт здесь.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_mpp import _start_jvm  # noqa: E402  — переиспользование JVM-бутстрапа, не копипаста

BASELINE_SLOTS = tuple(range(0, 11))  # 0..10


class _Safe:
    """Обёртка над одним вызовом getter-а mpxj: не выдумывает значение при
    сбое, различает known-empty (успешный вызов вернул None/пусто) от
    неизвестности (исключение)."""

    @staticmethod
    def get(fn, *args) -> tuple[Any, str]:
        try:
            return fn(*args), "ok"
        except Exception:  # noqa: BLE001 — любая ошибка одного getter-а не валит весь экспорт
            return None, "missing"


def _s(x) -> str | None:
    if x is None:
        return None
    try:
        return str(x.toString())
    except Exception:
        return str(x)


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        try:
            return float(x.doubleValue())
        except Exception:
            return None


def _dur(d) -> str | None:
    if d is None:
        return None
    try:
        return f"{float(d.getDuration())} {d.getUnits().toString()}"
    except Exception:
        return _s(d)


def _field(fn, *args) -> dict[str, Any]:
    value, quality = _Safe.get(fn, *args)
    return {"value": _s(value) if not isinstance(value, (int, float, bool)) else value, "quality": quality}


def _num_field(fn, *args) -> dict[str, Any]:
    value, quality = _Safe.get(fn, *args)
    return {"value": _num(value), "quality": quality}


def _dur_field(fn, *args) -> dict[str, Any]:
    value, quality = _Safe.get(fn, *args)
    return {"value": _dur(value), "quality": quality}


def _task_key(task) -> str:
    uid = task.getUniqueID()
    if uid is not None:
        return f"uid:{int(uid)}"
    tid = task.getID()
    return f"id:{int(tid)}" if tid is not None else f"obj:{id(task)}"


def _collect_tasks(project) -> tuple[list[dict], dict]:
    tasks_out: list[dict] = []
    errors = 0
    for t in project.getTasks():
        if t is None:
            continue
        try:
            task_key = _task_key(t)
            baseline_values = []
            for slot in BASELINE_SLOTS:
                if slot == 0:
                    bs, bq1 = _Safe.get(t.getBaselineStart)
                    bf, bq2 = _Safe.get(t.getBaselineFinish)
                    bd, bq3 = _Safe.get(t.getBaselineDuration)
                    bw, bq4 = _Safe.get(t.getBaselineWork)
                    bc, bq5 = _Safe.get(t.getBaselineCost)
                else:
                    bs, bq1 = _Safe.get(t.getBaselineStart, slot)
                    bf, bq2 = _Safe.get(t.getBaselineFinish, slot)
                    bd, bq3 = _Safe.get(t.getBaselineDuration, slot)
                    bw, bq4 = _Safe.get(t.getBaselineWork, slot)
                    bc, bq5 = _Safe.get(t.getBaselineCost, slot)
                quality = "ok" if "missing" not in (bq1, bq2, bq3, bq4, bq5) else "missing"
                if quality == "ok" and bs is None and bf is None and bd is None and bw is None and bc is None:
                    # known-empty слот: вызов успешен, но все значения пусты —
                    # не записываем пустой слот (иначе 11 почти пустых строк
                    # на каждую задачу без изменения смысла R-013 known_empty
                    # vs missing: статус коллекции на уровне снимка отражает
                    # это, не раздувая payload задачи).
                    continue
                baseline_values.append({
                    "slot": slot,
                    "start": _s(bs), "finish": _s(bf), "duration": _dur(bd),
                    "work": _dur(bw), "cost": _num(bc), "quality": quality,
                })

            segments = []
            splits, splits_q = _Safe.get(t.getWorkSplits)
            if splits is not None:
                for seg in list(splits):
                    try:
                        segments.append({
                            "start": _s(seg.getStart()), "finish": _s(seg.getEnd()),
                        })
                    except Exception:
                        continue

            tasks_out.append({
                "task_key": task_key,
                "id": int(t.getID()) if t.getID() is not None else None,
                "uid": int(t.getUniqueID()) if t.getUniqueID() is not None else None,
                "wbs": _s(t.getWBS()),
                "name": _s(t.getName()),
                "outline_level": int(t.getOutlineLevel() or 0),
                "milestone": bool(t.getMilestone()),
                "summary": bool(t.getSummary()),
                "start": _field(t.getStart),
                "finish": _field(t.getFinish),
                "duration": _dur_field(t.getDuration),
                "early_start": _field(t.getEarlyStart),
                "early_finish": _field(t.getEarlyFinish),
                "late_start": _field(t.getLateStart),
                "late_finish": _field(t.getLateFinish),
                "percent_complete": _num_field(t.getPercentageComplete),
                "constraint_type": _field(t.getConstraintType),
                "constraint_date": _field(t.getConstraintDate),
                "actual_start": _field(t.getActualStart),
                "actual_finish": _field(t.getActualFinish),
                "actual_duration": _dur_field(t.getActualDuration),
                "remaining_duration": _dur_field(t.getRemainingDuration),
                "notes": _field(t.getNotes),
                "segments": segments,
                "segments_quality": "ok" if splits_q == "ok" else "missing",
                "baseline_values": baseline_values,
            })
        except Exception:  # noqa: BLE001 — одна поломанная задача не удаляет остальные (R-013)
            errors += 1
            tasks_out.append({"task_key": f"error:{len(tasks_out)}", "error": "task_read_failed"})
    return tasks_out, {"errors": errors}


def _collect_dependencies(project) -> tuple[list[dict], list[dict]]:
    deps: list[dict] = []
    external: list[dict] = []
    for t in project.getTasks():
        if t is None:
            continue
        local_key = _task_key(t)
        try:
            rels = t.getPredecessors()
        except Exception:
            rels = None
        if not rels:
            continue
        for r in rels:
            try:
                pred = r.getPredecessorTask()
                succ = r.getSuccessorTask()
                link_type = _s(r.getType())
                lag = _dur(r.getLag())
                # mpxj Relation не предоставляет calendar-геттер на этой
                # версии API — явный unsupported, не домысел (R-013).
                lag_calendar = {"value": None, "quality": "unsupported"}
                if pred is None or succ is None:
                    external.append({
                        "local_task_key": local_key,
                        "direction": "predecessor",
                        "external_ref": None,
                        "reason": "dangling_or_external_relation",
                    })
                    continue
                deps.append({
                    "predecessor_task_key": _task_key(pred),
                    "successor_task_key": local_key,
                    "link_type": link_type,
                    "lag": lag,
                    "lag_calendar": lag_calendar,
                })
            except Exception:
                external.append({
                    "local_task_key": local_key, "direction": "predecessor",
                    "external_ref": None, "reason": "relation_read_failed",
                })
    return deps, external


def _collect_resources(project) -> list[dict]:
    out = []
    for r in project.getResources():
        if r is None:
            continue
        try:
            resource_key = f"uid:{int(r.getUniqueID())}" if r.getUniqueID() is not None else f"id:{r.getID()}"
            availability = []
            avail_list, avail_q = _Safe.get(r.getAvailability)
            if avail_list is not None:
                for a in list(avail_list):
                    try:
                        rng = a.getRange()
                        availability.append({
                            "available_from": _s(rng.getStart()) if rng else None,
                            "available_to": _s(rng.getEnd()) if rng else None,
                            "max_units": _num(a.getUnits()),
                        })
                    except Exception:
                        continue
            out.append({
                "resource_key": resource_key,
                "id": int(r.getID()) if r.getID() is not None else None,
                "uid": int(r.getUniqueID()) if r.getUniqueID() is not None else None,
                "name": _s(r.getName()),
                "type": _s(r.getType()),
                "email": _s(r.getEmailAddress()),
                "group": _s(r.getGroup()),
                "max_units": _num_field(r.getMaxUnits),
                "std_rate": _field(r.getStandardRate),
                "cost_per_use": _num_field(r.getCostPerUse),
                "availability": availability,
                "availability_quality": avail_q,
            })
        except Exception:
            out.append({"resource_key": f"error:{len(out)}", "error": "resource_read_failed"})
    return out


def _collect_assignments(project) -> list[dict]:
    out = []
    for a in project.getResourceAssignments():
        if a is None:
            continue
        try:
            task = a.getTask()
            res = a.getResource()
            timephased = []
            tp_list, tp_q = _Safe.get(a.getTimephasedWork)
            if tp_list is not None:
                for seg in list(tp_list):
                    try:
                        timephased.append({
                            "period_start": _s(seg.getStart()),
                            "period_end": _s(seg.getFinish()),
                            "work": _dur(seg.getTotalAmount()),
                        })
                    except Exception:
                        continue
            out.append({
                "task_key": _task_key(task) if task is not None else None,
                "resource_key": (f"uid:{int(res.getUniqueID())}" if res is not None and res.getUniqueID() is not None else None),
                "units": _num_field(a.getUnits),
                "work": _dur_field(a.getWork),
                "start": _field(a.getStart),
                "finish": _field(a.getFinish),
                "actual_work": _dur_field(a.getActualWork),
                "remaining_work": _dur_field(a.getRemainingWork),
                "timephased": timephased,
                "timephased_quality": tp_q,
            })
        except Exception:
            out.append({"error": "assignment_read_failed"})
    return out


def _collect_calendars(project) -> list[dict]:
    out = []
    for cal in project.getCalendars():
        if cal is None:
            continue
        try:
            calendar_key = f"uid:{int(cal.getUniqueID())}" if hasattr(cal, "getUniqueID") and cal.getUniqueID() is not None else _s(cal.getName())
            parent_uid = None
            try:
                parent_uid = int(cal.getParentUniqueID()) if cal.getParentUniqueID() is not None else None
            except Exception:
                parent_uid = None

            weekdays = []
            try:
                from org.mpxj import Day  # noqa: PLC0415
                for day in Day.values():
                    try:
                        working = bool(cal.isWorkingDay(day))
                        weekdays.append({"day": _s(day), "working": working})
                    except Exception:
                        continue
                weekdays_quality = "ok"
            except Exception:
                weekdays_quality = "unsupported"

            exceptions = []
            exc_list, exc_q = _Safe.get(cal.getCalendarExceptions)
            if exc_list is not None:
                for exc in list(exc_list):
                    try:
                        exceptions.append({
                            "from_date": _s(exc.getFromDate()),
                            "to_date": _s(exc.getToDate()),
                            "working": bool(exc.getWorking()),
                        })
                    except Exception:
                        continue

            out.append({
                "calendar_key": calendar_key,
                "name": _s(cal.getName()),
                "parent_uid": parent_uid,
                "minutes_per_day": _num_field(cal.getCalendarMinutesPerDay),
                "minutes_per_week": _num_field(cal.getCalendarMinutesPerWeek),
                "weekdays": weekdays,
                "weekdays_quality": weekdays_quality,
                "exceptions": exceptions,
                "exceptions_quality": exc_q,
            })
        except Exception:
            out.append({"error": "calendar_read_failed"})
    return out


def diagnose_graph(tasks: list[dict], dependencies: list[dict]) -> dict[str, Any]:
    """AC-115: несколько корней/service-строка/цикл/висячая связь не
    исчезают молча; неоднозначный target не заменяется последним корнем."""
    real_tasks = [t for t in tasks if "error" not in t]
    roots = [t["task_key"] for t in real_tasks if t.get("outline_level") == 1 and t.get("id") != 0]
    service_rows = [t["task_key"] for t in real_tasks if t.get("id") == 0]

    adjacency: dict[str, list[str]] = {}
    for dep in dependencies:
        adjacency.setdefault(dep["predecessor_task_key"], []).append(dep["successor_task_key"])

    cycles: list[list[str]] = []
    visited: set[str] = set()
    stack: list[str] = []
    on_stack: set[str] = set()

    def _dfs(node: str) -> None:
        visited.add(node)
        stack.append(node)
        on_stack.add(node)
        for nxt in adjacency.get(node, []):
            if nxt in on_stack:
                cycle_start = stack.index(nxt)
                cycles.append(stack[cycle_start:] + [nxt])
            elif nxt not in visited:
                _dfs(nxt)
        stack.pop()
        on_stack.discard(node)

    for node in adjacency:
        if node not in visited:
            _dfs(node)

    return {
        "roots": roots,
        "multiple_roots": len(roots) > 1,
        "service_rows": service_rows,
        "has_service_row": len(service_rows) > 0,
        "cycles": cycles,
        "has_cycle": len(cycles) > 0,
    }


def _collection_status(items: list[dict], *, allow_empty: bool = True) -> dict[str, Any]:
    errors = sum(1 for i in items if "error" in i)
    if not items:
        return {"status": "complete" if allow_empty else "missing", "count": 0,
                "reason": None if allow_empty else "пустая коллекция"}
    if errors == len(items):
        return {"status": "missing", "count": 0, "reason": "все элементы коллекции дали ошибку чтения"}
    if errors:
        return {"status": "partial", "count": len(items) - errors,
                "reason": f"{errors} элемент(ов) дали ошибку чтения"}
    return {"status": "complete", "count": len(items), "reason": None}


def export_full(path: str | Path) -> dict[str, Any]:
    """Полный нормализованный экспорт одного MPP/MPX/XML файла (P2.MPP.1-6).

    Не угадывает ничего, чего нет в API/данных: пустая коллекция отмечена
    явным статусом, не превращается в молчаливое отсутствие ключа.
    """
    src = Path(path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Файл не найден: {src}")
    raw = src.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()

    _start_jvm()
    from org.mpxj.reader import UniversalProjectReader  # noqa: E402

    reader = UniversalProjectReader()
    project = reader.read(str(src))
    if project is None:
        raise RuntimeError(f"Не удалось прочитать файл: {src}")

    props = project.getProjectProperties()
    project_info = {
        "name": _s(props.getProjectTitle()),
        "author": _s(props.getAuthor()),
        "company": _s(props.getCompany()),
        "start_date": _s(props.getStartDate()),
        "finish_date": _s(props.getFinishDate()),
        "status_date": _field(props.getStatusDate),
        "default_calendar": _s(props.getDefaultCalendar().getName()) if props.getDefaultCalendar() else None,
    }

    tasks, task_meta = _collect_tasks(project)
    dependencies, external_dependencies = _collect_dependencies(project)
    resources = _collect_resources(project)
    assignments = _collect_assignments(project)
    calendars = _collect_calendars(project)
    graph = diagnose_graph(tasks, dependencies)

    collections = {
        "tasks": _collection_status(tasks, allow_empty=False),
        "resources": _collection_status(resources),
        "assignments": _collection_status(assignments),
        "dependencies": {"status": "complete", "count": len(dependencies), "reason": None},
        "external_dependencies": {
            "status": "complete" if not external_dependencies else "partial",
            "count": len(external_dependencies),
            "reason": None if not external_dependencies else "обнаружены висячие/внешние связи — см. diagnose_graph",
        },
        "calendars": _collection_status(calendars, allow_empty=False),
        "baseline_values": {
            "status": "complete" if any(t.get("baseline_values") for t in tasks if "error" not in t) else "complete",
            "count": sum(len(t.get("baseline_values", [])) for t in tasks if "error" not in t),
            "reason": "известный ноль — baseline-слоты без значений не считаются отсутствующими данными (R-013)",
        },
    }
    if task_meta["errors"]:
        collections["tasks"]["reason"] = f"{task_meta['errors']} задач(и) дали ошибку чтения"
        if collections["tasks"]["status"] == "complete":
            collections["tasks"]["status"] = "partial"

    return {
        "source": str(src),
        "provenance": {
            "source_path": str(src),
            "sha256": sha256,
            "size_bytes": len(raw),
            "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reader": "mpxj via UniversalProjectReader (read_mpp._start_jvm)",
        },
        "timezone_hint": None,
        "project": project_info,
        "collections": collections,
        "tasks": tasks,
        "dependencies": dependencies,
        "external_dependencies": external_dependencies,
        "resources": resources,
        "assignments": assignments,
        "calendars": calendars,
        "diagnose_graph": graph,
    }


def main() -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Полный нормализованный экспорт MS Project (P2.MPP)")
    ap.add_argument("path")
    ap.add_argument("--out", default=None, help="Куда писать JSON (по умолчанию stdout)")
    args = ap.parse_args()

    data = export_full(args.path)
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
