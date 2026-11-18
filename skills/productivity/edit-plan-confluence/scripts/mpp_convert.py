"""PreparedPlan → versioned Gantt representation; legacy CSV adapter is separate."""
from __future__ import annotations

import ast
import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
EMPTY_TEMPLATE = SKILL_ROOT / "references" / "empty-gantt-template.json"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _parse_duration_days(raw: str, milestone: str) -> float:
    if milestone == "True":
        return 0.0
    val = raw.replace(" d", "").strip()
    if not val:
        return 0.0
    return float(val)


def _normalize_dt(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.replace("T09:00", "T09:00:00").replace("T18:00", "T18:00:00")
    if "T" in s and s.count(":") == 1:
        s = s + ":00"
    return s


def _base_event(leaf_template: dict[str, Any]) -> dict[str, Any]:
    return {
        "baselines": [],
        "calendar": leaf_template.get("calendar"),
        "constraintType": leaf_template.get("constraintType", ""),
        "durationUnit": "day",
        "effort": None,
        "effortDriven": leaf_template.get("effortDriven", False),
        "effortUnit": "hour",
        "ignoreResourceCalendar": leaf_template.get("ignoreResourceCalendar"),
        "inactive": leaf_template.get("inactive"),
        "manuallyScheduled": False,
        "percentDone": 0,
        "segments": None,
        "schedulingMode": "FixedDuration",
        "unscheduled": False,
    }


def _leaf_template(tmpl: dict[str, Any]) -> dict[str, Any]:
    root = tmpl["eventsData"][0]
    if root.get("children"):
        return root["children"][0]
    return root


def _parse_outline_level(raw: str | None) -> int:
    """Пустое / мусор / нечисло → 0. '1.0' → 1. Не бросать ValueError."""
    s = str(raw).strip() if raw is not None else ""
    if not s:
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def build_event_tree(tasks: list[dict[str, str]], leaf_template: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rows = [
        r for r in tasks
        if r.get("id") and r["id"] != "0" and _parse_outline_level(r.get("outline_level")) > 0
    ]
    root: dict[str, Any] | None = None
    stack: list[tuple[int, dict[str, Any]]] = []
    for r in rows:
        lvl = _parse_outline_level(r.get("outline_level"))
        node = _base_event(leaf_template)
        node["name"] = r["name"]
        node["duration"] = _parse_duration_days(r.get("duration", ""), r.get("milestone", "False"))
        node["startDate"] = _normalize_dt(r.get("start"))
        node["endDate"] = _normalize_dt(r.get("finish"))
        node["rollup"] = r.get("summary") == "True"
        node["id"] = int(r["id"])
        node["children"] = []
        if r.get("percent_complete"):
            node["percentDone"] = _number(r["percent_complete"])
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root = node
        stack.append((lvl, node))
    if root is None:
        raise ValueError("No root task (outline_level=1) in MPP CSV")
    return root, rows


def fill_parent_fields(node: dict[str, Any], parent_id: int | None = None, parent_index: int = 0) -> None:
    node["parentId"] = parent_id
    node["parentIndex"] = parent_index
    for i, child in enumerate(node.get("children", [])):
        fill_parent_fields(child, node["id"], i)


def flatten_events(root: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}

    def walk(n: dict[str, Any]) -> None:
        out[n["id"]] = n
        for c in n.get("children", []):
            walk(c)

    walk(root)
    return out


def active_resources(resources_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for r in resources_data:
        nm = r["name"]
        if nm not in by_name or by_name[nm]["id"] < r["id"]:
            by_name[nm] = r
    return sorted(by_name.values(), key=lambda x: x["id"])


def build_resources(
    mpp_resources: list[dict[str, str]],
    existing_resources: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    plugin_res = active_resources(existing_resources or [])
    name_to_id = {r["name"]: r["id"] for r in plugin_res}
    used_ids = {r["id"] for r in plugin_res}
    next_id = (max(used_ids) if used_ids else 0) + 1
    for r in mpp_resources:
        if not r.get("id") or r["id"] == "0":
            continue
        nm = r["name"]
        if nm and nm not in name_to_id:
            plugin_res.append(
                {
                    "id": next_id,
                    "parentId": None,
                    "name": nm,
                    "eventColor": "red",
                    "resourceType": "custom",
                }
            )
            name_to_id[nm] = next_id
            next_id += 1
    plugin_res.sort(key=lambda x: x["id"])
    return plugin_res, name_to_id


def _csv_dependencies(rows, flat, start_id, drop_links=None):
    deps: list[dict[str, Any]] = []
    warnings: list[str] = []
    dep_id = start_id
    dropped = set(drop_links or ())
    for r in rows:
        preds_raw = r.get("predecessors") or ""
        if not preds_raw or preds_raw == "[]":
            continue
        try:
            pids = ast.literal_eval(preds_raw)
        except (SyntaxError, ValueError):
            pids = []
        tid = int(r["id"])
        for p in pids:
            p = int(p)
            if (p, tid) in dropped:
                continue
            if p in flat and tid in flat and tid != p:
                deps.append(
                    {
                        "id": dep_id,
                        "from": p,
                        "to": tid,
                        "type": 2,
                        "lag": 0,
                        "lagUnit": "day",
                        "active": True,
                    }
                )
                dep_id += 1
    return deps, warnings


def critical_path_days(gantt: dict[str, Any]) -> float:
    """Legacy FS/zero-lag longest-path heuristic, never a plugin observation.

    No calendar/resource/constraint support. Do not use for schedule verification
    or automatic link removal. The prepared branch does not call this function.
    """
    def walk(nodes):
        for n in nodes:
            yield n
            if n.get("children"):
                yield from walk(n["children"])

    nodes = {n["id"]: n for n in walk(gantt.get("eventsData", []))}
    if not nodes:
        return 0.0
    pred: dict[int, list[int]] = {nid: [] for nid in nodes}
    for d in gantt.get("dependenciesData", []):
        if d.get("active", True) is False:
            continue
        pred[d["to"]].append(d["from"])
    dur = {nid: (n.get("duration") or 0.0) for nid, n in nodes.items()}
    fin: dict[int, float] = {}

    def longest(nid: int) -> float:
        if nid in fin:
            return fin[nid]
        best = max((longest(p) for p in pred[nid]), default=0.0)
        fin[nid] = best + dur[nid]
        return fin[nid]

    return max(longest(nid) for nid in nodes)


def _csv_assignments(
    assignments: list[dict[str, str]],
    flat: dict[int, dict[str, Any]],
    name_to_id: dict[str, int],
    start_id: int,
) -> tuple[list[dict[str, Any]], dict[int, float]]:
    asn_out: list[dict[str, Any]] = []
    eff_acc: dict[int, float] = {}
    asn_id = start_id
    for a in assignments:
        if not a.get("resource_id") and not a.get("resource_name"):
            continue
        eid = int(a["task_id"])
        if eid not in flat:
            continue
        rnm = a.get("resource_name", "")
        pid = name_to_id.get(rnm)
        if pid is None:
            continue
        units = float(a.get("units") or 100)
        asn_out.append({"id": asn_id, "event": eid, "resource": pid, "units": units})
        asn_id += 1
        work_raw = (a.get("work") or "0").replace(" h", "").strip()
        try:
            work = float(work_raw)
        except ValueError:
            work = 0.0
        eff_acc[eid] = eff_acc.get(eid, 0.0) + work
    for eid, hrs in eff_acc.items():
        if eid in flat:
            flat[eid]["effort"] = round(hrs, 3)
    return asn_out, eff_acc


def compute_id_counter(data: dict[str, Any]) -> int:
    ids: list[int] = []

    def walk_event(n: dict[str, Any]) -> None:
        ids.append(int(n["id"]))
        for c in n.get("children", []):
            walk_event(c)

    for e in data.get("eventsData", []):
        walk_event(e)
    for r in data.get("resourcesData", []):
        ids.append(int(r["id"]))
    for d in data.get("dependenciesData", []):
        ids.append(int(d["id"]))
    for a in data.get("assignmentsData", []):
        ids.append(int(a["id"]))
    return max(ids) + 1 if ids else 1


def preserve_meta_keys(tmpl: dict[str, Any], out: dict[str, Any]) -> None:
    for key in (
        "macroConfig",
        "initialState",
        "baselineVersions",
        "customColumns",
        "linkedSites",
    ):
        if key in tmpl:
            out[key] = deepcopy(tmpl[key])


def convert_mpp_csv(
    tasks_csv: Path,
    resources_csv: Path,
    assignments_csv: Path,
    *,
    template_json: dict[str, Any] | None = None,
    calendars_data: list[dict[str, Any]] | None = None,
    drop_links: list[tuple[int, int]] | None = None,
) -> dict[str, Any]:
    tmpl = template_json or json.loads(EMPTY_TEMPLATE.read_text(encoding="utf-8"))
    leaf = _leaf_template(tmpl)
    tasks = read_csv_rows(tasks_csv)
    mpp_res = read_csv_rows(resources_csv)
    asns = read_csv_rows(assignments_csv)

    root, rows = build_event_tree(tasks, leaf)
    fill_parent_fields(root)

    flat = flatten_events(root)
    plugin_res, name_to_id = build_resources(mpp_res, tmpl.get("resourcesData"))
    max_used = max(
        [int(r["id"]) for r in rows]
        + [r["id"] for r in plugin_res]
        + ([int(x) for x in flat] if flat else [0]),
        default=0,
    )
    deps, _warn = _csv_dependencies(rows, flat, max_used + 1, drop_links=drop_links)
    max_used = max(max_used, max((d["id"] for d in deps), default=0))
    asn_out, _ = _csv_assignments(asns, flat, name_to_id, max_used + 1)

    out = deepcopy(tmpl)
    preserve_meta_keys(tmpl, out)
    out["eventsData"] = [root]
    out["resourcesData"] = plugin_res
    out["dependenciesData"] = deps
    out["assignmentsData"] = asn_out
    if root.get("startDate"):
        out["startDate"] = str(root["startDate"])[:10]
    if calendars_data is not None:
        out["calendarsData"] = calendars_data
    out["idCounter"] = compute_id_counter(out)
    return out


def empty_gantt(title: str | None = None, template_path: Path | None = None) -> dict[str, Any]:
    path = template_path or EMPTY_TEMPLATE
    out = json.loads(path.read_text(encoding="utf-8"))
    if title:
        out["eventsData"][0]["name"] = title
    out["dependenciesData"] = []
    out["assignmentsData"] = []
    out["eventsData"][0]["children"] = []
    out["idCounter"] = compute_id_counter(out)
    return out


def copy_parent_gantt(parent: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(parent)
    out["idCounter"] = compute_id_counter(out)
    return out


def count_tasks(root: dict[str, Any]) -> int:
    n = 0

    def walk(node: dict[str, Any]) -> None:
        nonlocal n
        n += 1
        for c in node.get("children", []):
            walk(c)

    walk(root)
    return n


CONVERTER_VERSION = 'prepared-gantt-v9-calendar-24h-snapshot'

PUBLICATION_MODE = 'planned_schedule_with_actuals_columns'
PUBLICATION_LABEL = 'по плану; факт — в колонках'

# The wrapper registers these fields before loading tasks. Text columns preserve
# source decimals and summary values; they do not participate in scheduling.
SOURCE_COLUMNS = {
    'percent_complete': ('custom_mpp_percent_complete', 'Процент MPP (исходный)'),
    'actual_finish': ('custom_mpp_actual_finish', 'Фактическое окончание MPP'),
    'actual_start': ('custom_mpp_actual_start', 'Фактическое начало MPP'),
    'actual_duration': ('custom_mpp_actual_duration', 'Фактическая длительность MPP'),
    'actual_work': ('custom_mpp_actual_work', 'Фактическая работа MPP'),
    'stop': ('custom_mpp_stop', 'Остановка MPP'),
    'resume': ('custom_mpp_resume', 'Возобновление MPP'),
    'source_state': ('custom_mpp_source_state', 'Проверка исходных фактов MPP'),
}


def source_value_text(raw):
    """Lossless decimal text and explicit absence, without deriving actuals."""
    from decimal import Decimal, InvalidOperation
    from itogo import field_value
    if not isinstance(raw, dict):
        return 'неизвестно'
    value = field_value(raw)
    if raw.get('quality') not in (None, 'ok'):
        if raw.get('quality') == 'missing' and raw.get('reason') == 'not_set':
            return 'не задано'
        return 'неизвестно (' + str(raw.get('reason') or raw.get('quality')) + ')'
    quantity = raw.get('quantity')
    if quantity and quantity.get('amount') is not None:
        amount = format(Decimal(str(quantity['amount'])), 'f')
        unit = quantity.get('source_units') or quantity.get('units')
        return amount + (' ' + str(unit) if unit else '')
    if value is None:
        return 'не задано'
    # Numeric strings use plain decimal notation, never binary-float arithmetic.
    try:
        number = Decimal(str(value))
        if number.is_finite():
            return format(number, 'f')
    except InvalidOperation:
        pass
    return str(value)


def source_fact_values(task):
    from itogo import field_value, decimal_value
    values = {column: source_value_text(task.get(field))
              for field, (column, _) in SOURCE_COLUMNS.items() if field != 'source_state'}
    percent = decimal_value(field_value(task.get('percent_complete')))
    reasons = []
    if percent is None or not percent.is_finite() or not 0 <= percent <= 100:
        reasons.append('процент неизвестен или недопустим')
    else:
        if percent == 0 and field_value(task.get('actual_start')) is not None:
            reasons.append('0% при заданном фактическом начале')
        if percent < 100 and field_value(task.get('actual_finish')) is not None:
            reasons.append('менее 100% при заданном фактическом окончании')
    values['custom_mpp_source_state'] = ('требует проверки: ' + '; '.join(reasons) if reasons
        else 'по исходному проценту: ' + ('new' if percent == 0 else 'done' if percent == 100 else 'indeterminate'))
    if field_value(task.get('active')) is False:
        values['custom_mpp_source_state'] += '; неактивна'
    return values


SNAPSHOT_COLUMN = 'custom_mpp_schedule_mode'
UNASSIGNED_COLUMN = 'custom_mpp_unassigned'

def snapshot_text(task, addition=None):
    text = 'Сохранённые даты MPP; исходный режим: ' + source_value_text(task.get('task_mode'))
    return text + (('\n' + addition) if addition else '')


def unassigned_source(assignment, source_tasks):
    """Only an explicitly absent resource; invalid/unknown references still block."""
    from itogo import field_value
    raw = assignment.get('resource_uid', {})
    return (assignment.get('resource_key') is None and raw.get('quality') == 'missing'
        and raw.get('reason') == 'not_set' and raw.get('value') is None
        and assignment.get('task_key') in source_tasks and 'error' not in assignment
        and _number(field_value(assignment.get('units'))) is not None)


def unassigned_text(assignment):
    fields = ('start','finish','work','actual_work','remaining_work','overtime_work','units')
    return (assignment['assignment_key'] + '; resource_uid: missing; ресурс: ; '
        + '; '.join(field + ': ' + source_value_text(assignment.get(field)) for field in fields))


def add_source_columns(gantt, *, include_unassigned=False, include_snapshot=False):
    """Use the installed wrapper's customColumns object and customtext fields."""
    columns = gantt.setdefault('customColumns', {})
    values = list(SOURCE_COLUMNS.values())
    if include_unassigned:
        values.append((UNASSIGNED_COLUMN, 'Назначения без ресурса (исходник)'))
    if include_snapshot:
        values.append((SNAPSHOT_COLUMN, 'Показ дат / исходный режим MPP'))
    for column, title in values:
        columns[column] = {'id': column, 'text': title, 'type': 'customtext'}
    for mode in ('view', 'edit'):
        state = gantt.setdefault('initialState', {}).setdefault(mode, {})
        rows = state.setdefault('columns', [])
        existing = {row['id']: row for row in rows}
        for column, _ in values:
            if column not in existing:
                rows.append({'id': column, 'width': 210, 'hidden': False, 'order': len(rows)})
            else:
                existing[column]['hidden'] = False


def _number(value):
    """Plugin JSON numbers: reject precision loss, retain exact source in evidence."""
    from itogo import decimal_value
    amount = decimal_value(value)
    if amount is None:
        return None
    out = int(amount) if amount == amount.to_integral_value() else float(amount)
    return out if decimal_value(out) == amount else None


def build_dependencies(rows, task_mapping, start_id, *, plugin_profile, diagnostics, project, task_calendars=None):
    from itogo import field_value, decimal_value
    deps = []
    for index, row in enumerate(rows):
        key = row.get('dependency_key',f'row:{index}')
        problems = []
        pred = task_mapping.get(row.get('predecessor_task_key'))
        succ = task_mapping.get(row.get('successor_task_key'))
        if 'error' in row or pred is None or succ is None or pred == succ or row.get('external'):
            problems.append('dependency_endpoint_invalid')
        typ = row.get('link_type')
        code = plugin_profile.code('relation',typ)
        if code is None:
            problems.append('dependency_type_unsupported')
        lag = field_value(row.get('lag_value'))
        amount = _number(lag.get('amount')) if isinstance(lag,dict) else None
        unit = lag.get('units') if isinstance(lag,dict) else None
        unit_code = plugin_profile.code('lag_unit',unit)
        elapsed = lag.get('elapsed') if isinstance(lag,dict) else None
        if unit_code is None or type(elapsed) is not bool or elapsed != str(unit).startswith('ELAPSED_'):
            problems.append('dependency_lag_unit_unsupported')
        if amount is None:
            problems.append('dependency_lag_missing_or_imprecise')
        if amount is not None:
            sign = 'negative' if amount < 0 else 'positive' if amount > 0 else 'zero'
            if not plugin_profile.supports('lag:'+sign):
                problems.append('dependency_lag_sign_unsupported')
            if not plugin_profile.supports('dependency:'+str(typ)+':'+str(unit)+':'+sign):
                problems.append('dependency_combination_unverified')
        basis = field_value(row.get('lag_calendar')) or field_value(row.get('project_lag_calendar'))
        if basis is None:
            basis = field_value(project.get('relationship_lag_calendar'))
        supported_basis = plugin_profile.supports('lag_basis:'+str(basis))
        if not supported_basis and basis in ('PREDECESSOR','SUCCESSOR','PROJECT') and task_calendars:
            pred_cal = task_calendars.get(row.get('predecessor_task_key'))
            succ_cal = task_calendars.get(row.get('successor_task_key'))
            default_cal = field_value(project.get('default_calendar_key'))
            supported_basis = (plugin_profile.supports('lag_basis:equal_endpoint_calendars')
                               and pred_cal is not None and pred_cal == succ_cal == default_cal)
        if not supported_basis:
            problems.append('dependency_calendar_basis_unsupported')
        if problems:
            diagnostics.extend({'code':p,'entity':key,'source':deepcopy(row),'represented':None} for p in problems)
            continue
        deps.append({'id':start_id+index,'from':pred,'to':succ,'type':code,
                     'lag':amount,'lagUnit':unit_code,'active':True})
    return deps


def build_assignments(assignments, task_mapping, resource_mapping, start_id, *, diagnostics, excluded_task_keys=(), source_tasks=None, plugin_profile=None, transformations=None):
    from itogo import field_value
    out = []
    for index,a in enumerate(assignments):
        if a.get('task_key') in excluded_task_keys:
            continue
        task, resource = task_mapping.get(a.get('task_key')), resource_mapping.get(a.get('resource_key'))
        units = _number(field_value(a.get('units')))
        source_task=(source_tasks or {}).get(a.get('task_key'))
        from mpp_calendar import coincident_assignment_interval
        coincident=coincident_assignment_interval(a,source_task)
        if (resource is None and a.get('resource_key') is None
                and a.get('resource_uid',{}).get('quality') == 'missing'
                and a.get('resource_uid',{}).get('reason') == 'not_set'
                and a.get('resource_uid',{}).get('value') is None
                and source_task and source_task.get('milestone') is True
                and source_task.get('duration',{}).get('quantity',{}).get('amount')=='0'
                and coincident and all(a.get(field,{}).get('quality')=='ok'
                    and a.get(field,{}).get('quantity',{}).get('amount')=='0'
                    for field in ('work','actual_work','remaining_work','overtime_work'))):
            if transformations is not None:
                transformations.append({'entity':a['assignment_key'],'field':'resource_key','kind':'zero_work_unassigned_milestone',
                    'source':deepcopy(a),'normalized':None,'represented':None,
                    'basis':'no_resource_and_all_work_known_zero_milestone_duration_zero_coincident_dates'})
            continue
        if unassigned_source(a, source_tasks or {}):
            from plan_policy import owner_decision
            decision = owner_decision()
            if decision['unassigned_resources'] == 'preserve_source_display':
                if transformations is not None:
                    transformations.append({'entity':a['assignment_key'], 'field':'resource_key',
                        'kind':'unassigned_source_display', 'source':deepcopy(a), 'normalized':None,
                        'represented':{'task':task, 'resource':None, 'text':unassigned_text(a)},
                        'basis':'назначение без ресурса публикуется как есть (resource_uid: missing)',
                        'owner_decision':decision})
                continue
        if task is None or resource is None or units is None or 'error' in a:
            diagnostics.append({'code':'assignment_partial','entity':a.get('assignment_key'),
                                'source':deepcopy(a),'represented':None})
            continue
        node={'id':start_id+index,'event':task,'resource':resource,'units':units}
        if coincident and plugin_profile is not None and plugin_profile.supports('assignment:coincident_task_interval'):
            node.update(startDate=field_value(a.get('start')),endDate=field_value(a.get('finish')))
            if transformations is not None:
                transformations.append({'entity':a['assignment_key'],'field':'segments','kind':'assignment_task_envelope',
                    'source':deepcopy(a),'normalized':{'start':node['startDate'],'finish':node['endDate']},
                    'represented':deepcopy(node),'basis':'coincident_task_interval_and_no_independent_split'})
        out.append(node)
    return out


def _source_working_minutes(data, calendar_key, start, finish):
    """Exact source calendar windows for segment durations; reject unknowns."""
    from datetime import datetime, timedelta
    from decimal import Decimal
    from itogo import field_value
    calendars={c['calendar_key']:c for c in data['calendars'] if 'error' not in c}
    chain=[];seen=set();key=calendar_key
    while key is not None:
        if key in seen or key not in calendars:raise ValueError('segment_calendar_unresolved')
        seen.add(key);cal=calendars[key];chain.append(cal);key=field_value(cal.get('parent_key'))
        if cal.get('work_weeks'):raise ValueError('segment_work_weeks_unverified')
    if not chain:raise ValueError('segment_calendar_unresolved')
    begin,end=datetime.fromisoformat(start),datetime.fromisoformat(finish)
    if begin.tzinfo != end.tzinfo or begin>end:raise ValueError('segment_dates_invalid')
    weekdays=['MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY']
    def windows(day):
        chosen=None
        for cal in reversed(chain):
            source=next((d for d in cal.get('weekdays',[]) if d.get('day')==weekdays[day.weekday()]),None)
            if source is None:raise ValueError('segment_calendar_day_missing')
            if field_value(source.get('day_type')) != 'DEFAULT':chosen=source
            for exc in cal.get('exceptions',[]):
                if field_value(exc.get('recurrence')) is not None:raise ValueError('segment_recurrence_unverified')
                a,b=field_value(exc.get('from_date')),field_value(exc.get('to_date'))
                if a is None or b is None:raise ValueError('segment_exception_incomplete')
                if a[:10]<=day.isoformat()<=b[:10]:chosen=exc
        if chosen is None:raise ValueError('segment_calendar_day_missing')
        working=field_value(chosen.get('working'))
        if working is False:return []
        ranges=field_value(chosen.get('intervals'))
        if working is not True or ranges is None:raise ValueError('segment_calendar_intervals_missing')
        return ranges
    def at(day,clock):
        if clock is None:raise ValueError('segment_clock_missing')
        if clock in ('24:00','24:00:00'):return datetime.combine(day+timedelta(days=1),datetime.min.time()).replace(tzinfo=begin.tzinfo)
        return datetime.fromisoformat(day.isoformat()+'T'+clock).replace(tzinfo=begin.tzinfo)
    day=begin.date();total=Decimal(0)
    while day<=end.date():
        for window in windows(day):
            a=at(day,field_value(window.get('start')));b=at(day,field_value(window.get('end')))
            if a>=b:raise ValueError('segment_calendar_interval_invalid')
            a,b=max(a,begin),min(b,end)
            if b>a:total+=Decimal(str((b-a).total_seconds()))/Decimal(60)
        day+=timedelta(days=1)
    return total


def convert_prepared_plan(prepared, *, plugin_profile=None, template_json=None, root_task_key=None):
    """Pure conversion result with publishable bytes and explicit semantic losses.

    Diagnostics stay outside plugin JSON. Unsupported rows remain in source_semantics;
    publishable=False prevents a caller treating omitted/partial data as admitted.
    Admission, archival and network execution belong to the subsequent stage.
    """
    from decimal import localcontext
    from itogo import compute_itogo_from_prepared, field_value, quantity_minutes, decimal_value
    from mpp_calendar import calendar_from_prepared
    from plugin_profile import PluginProfile
    prepared.validate()
    profile = plugin_profile or PluginProfile.load()
    profile.validate()
    data = prepared.normalized_data
    tmpl = deepcopy(template_json if template_json is not None else json.loads(EMPTY_TEMPLATE.read_text()))
    summary = compute_itogo_from_prepared(prepared,root_task_key=root_task_key)
    cal = calendar_from_prepared(prepared,plugin_profile=profile)
    diagnostics = cal['diagnostics'][:]
    transformations = cal['transformations'][:]
    diagnostics.extend({'code':r,'entity':'summary','source':summary['source_duration'],'represented':None} for r in summary['reasons'])
    tasks = [t for t in data['tasks'] if 'error' not in t and t.get('id') != 0]
    task_mapping = {}
    from plan_policy import round_the_clock_calendars, owner_decision
    round_clock = round_the_clock_calendars(data)
    round_clock_decision = owner_decision() if round_clock else None
    round_clock_note = ('В исходнике круглосуточный календарь (7 дней, 00:00–00:00). '
        'Даты показаны снимком MPP без пересчёта; исходные интервалы сохранены в архиве.'
        + '\nКалендари: ' + ', '.join(round_clock))
    # Source-local keys define identity; ID collisions never merge tasks.
    source_ids = [t.get('id') for t in tasks]
    used_ids = set()
    for i,t in enumerate(tasks):
        sid = t.get('id')
        ident = sid if type(sid) is int and sid > 0 and source_ids.count(sid) == 1 else max([0,*[x for x in source_ids if type(x) is int],*used_ids])+1
        task_mapping[t['task_key']] = ident; used_ids.add(ident)
    nodes = {}
    with localcontext() as ctx:
        ctx.prec = 80
        for t in tasks:
            key=t['task_key']
            node=_base_event({})
            node.update(id=task_mapping[key],name=t.get('name'),startDate=field_value(t.get('start')),
                        endDate=field_value(t.get('finish')),rollup=t.get('summary'),children=[])
            minutes,_,reason=quantity_minutes(t.get('duration'),data['project'],working_only=True)
            day=decimal_value(field_value(data['project'].get('minutes_per_day')))
            duration=_number(minutes/day) if minutes is not None and day is not None and day > 0 else None
            if duration is not None and duration < 0:
                reason='task_duration_negative'
            if reason or duration is None:
                diagnostics.append({'code':reason or 'task_duration_basis_missing','entity':key,'source':t.get('duration'),'represented':None})
            node['duration']=duration
            if node['startDate'] is None or node['endDate'] is None:
                diagnostics.append({'code':'task_dates_missing','entity':key,'source':deepcopy(t),'represented':None})
            node['percentDone']=_number(field_value(t.get('percent_complete')))
            node.update(source_fact_values(t))
            mode=field_value(t.get('task_mode'))
            if mode in ('AUTO_SCHEDULED','Auto Scheduled','AUTO'):
                node['manuallyScheduled']=False
            else:
                diagnostics.append({'code':'task_mode_unverified','entity':key,'source':t.get('task_mode'),'represented':None})
            if profile.supports('publication:source_snapshot_dates'):
                from plan_policy import owner_decision
                decision = owner_decision()
                node.update(manuallyScheduled=True, skipNonWorkingTimeWhenSchedulingManually=False)
                node[SNAPSHOT_COLUMN] = snapshot_text(t)
                transformations.append({'entity':key,'field':'task_mode','kind':'source_snapshot_dates',
                    'source':deepcopy(t.get('task_mode')),'normalized':None,
                    'represented':{'manuallyScheduled':True,'skipNonWorkingTimeWhenSchedulingManually':False},
                    'basis':'Source dates are the published snapshot; no plugin schedule recalculation claimed',
                    'owner_decision':decision})
            if field_value(t.get('active')) is False:
                if profile.supports('task:active'):
                    node['inactive'] = True
                else:
                    diagnostics.append({'code':'inactive_task_unverified','entity':key,'source':t.get('active'),'represented':None})
            leveling = t.get('leveling_delay',{}).get('quantity')
            if leveling and decimal_value(leveling.get('amount')) != 0:
                diagnostics.append({'code':'leveling_delay_unrepresented','entity':key,'source':t.get('leveling_delay'),'represented':None})
            if t.get('milestone') is True and duration != 0:
                diagnostics.append({'code':'milestone_duration_nonzero','entity':key,'source':t.get('duration'),'represented':None})
            node['calendar']=None
            binding=field_value(t.get('effective_calendar_key'))
            if profile.supports('calendar:bindings:tasks') and binding in cal['mapping']:
                node['calendar']=cal['mapping'][binding]
            metric=summary['work']['per_task'].get(key)
            node['effort']=_number(metric['hours']) if metric and metric['quality']=='complete' else None
            nodes[key]=node
            task_type = field_value(t.get('task_type'))
            modes = {'FIXED_UNITS':'FixedUnits','FIXED_DURATION':'FixedDuration','FIXED_WORK':'FixedEffort'}
            if task_type == 'FIXED_DURATION' or profile.supports('task:task_type:'+str(task_type)):
                node['schedulingMode'] = modes.get(task_type)
            elif task_type is not None:
                diagnostics.append({'code':'task_semantics_unrepresented:task_type','entity':key,'source':deepcopy(t['task_type']),'represented':None})
            constraint = field_value(t.get('constraint_type'))
            constraints = {'START_NO_EARLIER_THAN':'startnoearlierthan','FINISH_NO_EARLIER_THAN':'finishnoearlierthan',
                           'MUST_START_ON':'muststarton','MUST_FINISH_ON':'mustfinishon',
                           'START_NO_LATER_THAN':'startnolaterthan','FINISH_NO_LATER_THAN':'finishnolaterthan'}
            if constraint in constraints and profile.supports('task:constraint:'+constraint):
                node['constraintType'] = constraints[constraint]
                node['constraintDate'] = field_value(t.get('constraint_date'))
                if node['constraintDate'] is None:
                    diagnostics.append({'code':'task_constraint_date_missing','entity':key,'source':t.get('constraint_date'),'represented':None})
            elif constraint not in (None,'AS_SOON_AS_POSSIBLE','As Soon As Possible'):
                diagnostics.append({'code':'task_semantics_unrepresented:constraint_type','entity':key,'source':deepcopy(t.get('constraint_type')),'represented':None})
            segments = field_value(t.get('segments'))
            if segments:
                envelope = len(segments) == 1 and all(field_value(segments[0].get(src)) == field_value(t.get(dest))
                    for src,dest in [('start','start'),('end','finish')])
                if envelope:
                    transformations.append({'entity':key,'field':'segments','kind':'single_work_envelope',
                        'source':deepcopy(t['segments']),'normalized':[],
                        'represented':{'startDate':node['startDate'],'endDate':node['endDate'],'duration':node['duration']},
                        'basis':'one_working_period_equals_task_start_and_finish_no_interruption'})
                elif len(segments) > 1 and profile.supports('task:segments'):
                    periods = [(field_value(part.get('start')),field_value(part.get('end'))) for part in segments]
                    if (all(a is not None and b is not None and a < b for a,b in periods)
                            and all(periods[i][1] <= periods[i+1][0] for i in range(len(periods)-1))):
                        try:
                            lengths = [_source_working_minutes(data, binding, a, b) for a,b in periods]
                            if minutes is None or sum(lengths) != minutes:
                                raise ValueError('segment_duration_source_mismatch')
                            values = [_number(length/day) for length in lengths]
                            if any(v is None for v in values):raise ValueError('segment_duration_imprecise')
                            node['segments'] = [{'startDate':a,'endDate':b,'duration':v,'durationUnit':'day'}
                                                for (a,b),v in zip(periods,values)]
                        except (ValueError,TypeError) as exc:
                            diagnostics.append({'code':str(exc),'entity':key,'source':deepcopy(t['segments']),'represented':None})
                    else:
                        diagnostics.append({'code':'task_segments_invalid','entity':key,'source':deepcopy(t['segments']),'represented':None})
                else:
                    diagnostics.append({'code':'task_semantics_unrepresented:segments','entity':key,'source':deepcopy(t['segments']),'represented':None})
            for field in ('secondary_constraint_type','secondary_constraint_date','deadline','ignore_resource_calendar','effort_driven'):
                value=field_value(t.get(field))
                if value not in (None,False,[]):
                    diagnostics.append({'code':'task_semantics_unrepresented:'+field,'entity':key,'source':deepcopy(t.get(field)),'represented':None})
    roots=[]
    source_tasks={t['task_key']:t for t in data['tasks'] if 'error' not in t}
    for t in tasks:
        key=t['task_key']; parent=field_value(t.get('parent_task_key')); seen={key}
        while parent in source_tasks and source_tasks[parent].get('id')==0:
            if parent in seen:
                raise ValueError('cyclic_task_hierarchy')
            seen.add(parent);parent=field_value(source_tasks[parent].get('parent_task_key'))
        check=parent
        while check in nodes:
            if check in seen:
                raise ValueError('cyclic_task_hierarchy')
            seen.add(check);check=field_value(source_tasks[check].get('parent_task_key'))
        if parent in nodes:
            nodes[parent]['children'].append(nodes[key])
        else:
            roots.append(nodes[key])
            if parent is not None:
                diagnostics.append({'code':'task_parent_missing','entity':key,'source':parent,'represented':None})
    for i,node in enumerate(roots):
        fill_parent_fields(node,parent_index=i)
    if (round_clock and profile.supports('publication:source_snapshot_dates')
            and round_clock_decision.get('round_the_clock_calendar') == 'publish_as_is'
            and round_clock_decision.get('round_the_clock_calendar_evidence_verified')):
        root_key = summary.get('root_task_key')
        root_id = task_mapping.get(root_key)
        flattened = {ident:node for root in roots for ident,node in flatten_events(root).items()}
        root_node = flattened.get(root_id) if root_id is not None else None
        if root_node is not None:
            root_task = next((task for task in tasks if task.get('task_key') == root_key), {})
            root_node[SNAPSHOT_COLUMN] = snapshot_text(root_task, round_clock_note)
            transformations.append({'entity':root_key,'field':SNAPSHOT_COLUMN,'kind':'round_the_clock_calendar_snapshot',
                'source':round_clock,'normalized':{'calendar_keys':list(round_clock)},
                'represented':root_node[SNAPSHOT_COLUMN], 'owner_decision':round_clock_decision,
                'decision_id':round_clock_decision['round_the_clock_calendar_evidence']['decision_id'],
                'evidence':round_clock_decision['round_the_clock_calendar_evidence_verified']})
    resources=[];resource_mapping={};next_id=max(used_ids,default=0)+1
    for r in data['resources']:
        if 'error' in r:
            diagnostics.append({'code':'resource_partial','entity':r.get('resource_key'),'source':r,'represented':None});continue
        key=r['resource_key'];resource_mapping[key]=next_id
        node={'id':next_id,'parentId':None,'name':r.get('name'),'resourceType':'custom','eventColor':'red'}
        binding=field_value(r.get('calendar_key')) or field_value(r.get('base_calendar_key'))
        if profile.supports('calendar:bindings:resources') and binding in cal['mapping']:
            node['calendar']=cal['mapping'][binding]
        from mpp_calendar import default_availability_equivalent
        if profile.supports('resource:default_availability') and default_availability_equivalent(r,data):
            transformations.append({'entity':key,'field':'availability','kind':'default_availability_within_plan',
                'source':deepcopy(r['availability']),'normalized':{'max_units':100},'represented':deepcopy(node),
                'basis':'known_100_percent_window_covers_all_assigned_task_intervals_and_units'})
        resources.append(node);next_id+=1
    for dependency in data['dependencies']:
        endpoints = [source_tasks.get(dependency.get(k),{}) for k in ('predecessor_task_key','successor_task_key')]
        if any(t.get('summary') is True for t in endpoints) and not profile.supports('dependency:summary_endpoint'):
            diagnostics.append({'code':'summary_dependency_unverified','entity':dependency.get('dependency_key'),
                                'source':deepcopy(dependency),'represented':None})
    dependency_start = next_id
    deps=build_dependencies(data['dependencies'],task_mapping,next_id,plugin_profile=profile,diagnostics=diagnostics,project=data['project'],
                            task_calendars={t['task_key']:field_value(t.get('effective_calendar_key')) for t in tasks})
    next_id+=len(data['dependencies'])
    assignment_start = next_id
    assignments=build_assignments(data['assignments'],task_mapping,resource_mapping,next_id,diagnostics=diagnostics,
                                  excluded_task_keys={t['task_key'] for t in data['tasks'] if t.get('id') == 0},
                                  source_tasks=source_tasks,plugin_profile=profile,transformations=transformations)
    for name in ('tasks','dependencies','external_dependencies','resources','assignments'):
        if data['collections'][name]['status']!='complete':
            diagnostics.append({'code':'source_collection_incomplete','entity':name,'source':data['collections'][name],'represented':None})
    graph=data['diagnose_graph']
    for name in ('cycles','self_references','dangling_dependencies','external_dependencies'):
        if graph.get(name):
            diagnostics.append({'code':'graph_problem:'+name,'entity':'graph','source':graph[name],'represented':None})
    out=deepcopy(tmpl)
    out.update(eventsData=roots,resourcesData=resources,dependenciesData=deps,assignmentsData=assignments,calendarsData=cal['calendarsData'])
    unassigned = [a for a in data['assignments'] if unassigned_source(a, source_tasks) and a['task_key'] in nodes]
    add_source_columns(out, include_unassigned=bool(unassigned),
        include_snapshot=profile.supports('publication:source_snapshot_dates'))
    if unassigned:
        for key, node in nodes.items():
            node[UNASSIGNED_COLUMN] = '\n'.join(unassigned_text(a) for a in unassigned if a['task_key'] == key)
    default_cal=cal['bindings']['project']
    if profile.supports('calendar:bindings:project') and default_cal in cal['mapping']:
        out['calendar']=cal['mapping'][default_cal]
    else:
        out.pop('calendar',None)
    if summary['start']:
        out['startDate']=summary['start']
    out['idCounter']=compute_id_counter(out)
    source_semantics={k:deepcopy(data[k]) for k in ('tasks','dependencies','external_dependencies','resources','assignments','calendars','project','collections','diagnose_graph')}
    return {'converter_version':CONVERTER_VERSION,'normalized_sha256':prepared.semantic_hash,
            'plugin_profile_fingerprint':profile.fingerprint,'summary':summary,'gantt':out,
            'mappings':{'tasks':task_mapping,'resources':resource_mapping,'calendars':cal['mapping'],
                        'dependencies':{r.get('dependency_key',f'row:{i}'):dependency_start+i for i,r in enumerate(data['dependencies']) if any(d['id']==dependency_start+i for d in deps)},
                        'assignments':{r.get('assignment_key',f'row:{i}'):assignment_start+i for i,r in enumerate(data['assignments']) if any(a['id']==assignment_start+i for a in assignments)}},
            'source_semantics':source_semantics,'semantic_transformations':transformations,'diagnostics':diagnostics,'publishable':not diagnostics,
            'schedule':{'status':'not_verified','source':'no_model_replay_or_live_observation'}}


def representation_bytes(result):
    """Only plugin data is published, never diagnostics, work summary or provenance."""
    from prepared_plan import canonical_bytes
    return canonical_bytes(result['gantt'])
