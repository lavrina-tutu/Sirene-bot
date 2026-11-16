"""Block «Итого» above gantt macro in Confluence storage."""
from __future__ import annotations

import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from macro import macro_span


_MOFS_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(_MOFS_ROOT) not in sys.path:
    sys.path.insert(0, str(_MOFS_ROOT))

ITOGO_LINE1_RE = re.compile(
    r"(Итого:\s*с\s*)(\d{2}\.\d{2}\.\d{2})(\s*по\s*)(\d{2}\.\d{2}\.\d{2})(\s*-\s*)(\d[\d\s]*)(\s*рабочих дней)",
    re.IGNORECASE,
)
_TRUDOZATRATY_CORE = (
    r"Трудозатраты:\s*\d[\d\s\xa0]*\s*"
    r"(?:человеко?-часов?|человек-часа|человек-часов|человеко-часов)"
)
ITOGO_LINE2_RE = re.compile(
    rf"(?:<p>(?:<strong>)?{_TRUDOZATRATY_CORE}(?:</strong>)?</p>|{_TRUDOZATRATY_CORE})",
    re.IGNORECASE,
)


def format_thousands(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def format_date_ddmmyy(dt: str | None) -> str:
    if not dt:
        return "01.01.00"
    s = dt[:10]
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        d = datetime.fromisoformat(s.replace("Z", ""))
    return d.strftime("%d.%m.%y")


def compute_itogo_from_csv(tasks_csv: Path, assignments_csv: Path) -> tuple[str, str, int, int]:
    from mpp_convert import read_csv_rows
    tasks = read_csv_rows(tasks_csv)
    root = next((r for r in tasks if r.get("outline_level") == "1" and r.get("id") != "0"), None)
    if not root:
        raise ValueError("Root task (outline_level=1) not found in tasks CSV")
    d1 = format_date_ddmmyy(root.get("start"))
    d2 = format_date_ddmmyy(root.get("finish"))
    dur = root.get("duration", "0 d").replace(" d", "").strip()
    n_days = math.ceil(float(dur or 0))
    total_work = 0.0
    for a in read_csv_rows(assignments_csv):
        work_raw = (a.get("work") or "0").replace(" h", "").strip()
        try:
            total_work += float(work_raw)
        except ValueError:
            pass
    m_hours = math.ceil(total_work)
    return d1, d2, n_days, m_hours


def compute_itogo_from_gantt(gantt: dict[str, Any]) -> tuple[str, str, int, int]:
    root = gantt["eventsData"][0]
    d1 = format_date_ddmmyy(str(root.get("startDate", ""))[:10])
    d2 = format_date_ddmmyy(str(root.get("endDate", ""))[:10])
    n_days = math.ceil(float(root.get("duration") or 0))

    def leaf_effort(node: dict[str, Any]) -> float:
        if node.get("rollup"):
            return sum(leaf_effort(c) for c in node.get("children", []))
        return float(node.get("effort") or 0)

    m_hours = math.ceil(leaf_effort(root))
    return d1, d2, n_days, m_hours


def build_itogo_html(d1: str, d2: str, n_days: int, m_hours: int) -> str:
    return (
        f"<p><strong>Итого: с {d1} по {d2} - {format_thousands(n_days)} рабочих дней</strong></p>"
    )


def strip_trudozatraty(storage: str) -> str:
    """Удалить абзац/текст «Трудозатраты: …» целиком. Идемпотентно."""
    prev = None
    out = storage
    while out != prev:
        prev = out
        out = ITOGO_LINE2_RE.sub("", out)
    return out


def patch_itogo(storage: str, d1: str, d2: str, n_days: int, m_hours: int) -> str:
    storage = strip_trudozatraty(storage)
    n_fmt = format_thousands(n_days)
    if ITOGO_LINE1_RE.search(storage):
        storage = ITOGO_LINE1_RE.sub(
            lambda m: f"{m.group(1)}{d1}{m.group(3)}{d2}{m.group(5)}{n_fmt} рабочих дней",
            storage,
            count=1,
        )
        return storage
    return build_itogo_html(d1, d2, n_days, m_hours) + storage


def insert_itogo_above_macro(storage: str, macro_start: int, itogo_html: str) -> str:
    return storage[:macro_start] + itogo_html + storage[macro_start:]


def apply_itogo(storage: str, d1: str, d2: str, n_days: int, m_hours: int, macro_start: int | None = None) -> str:
    if ITOGO_LINE1_RE.search(storage):
        return patch_itogo(storage, d1, d2, n_days, m_hours)
    storage = strip_trudozatraty(storage)
    html = build_itogo_html(d1, d2, n_days, m_hours)
    if macro_start is not None:
        span = macro_span(storage)
        start = span[0] if span is not None else macro_start
        return insert_itogo_above_macro(storage, start, html)
    return html + storage


def parse_itogo_text(raw_html_or_text: str) -> tuple[str | None, str | None, int | None]:
    """Разобрать «Итого: с D1 по D2 - N рабочих дней» из текста/HTML, если
    строка присутствует. Возвращает (d1, d2, n) или (None, None, None), если
    строка не найдена — явная неизвестность, не выдуманный «01.01.00»."""
    m = ITOGO_LINE1_RE.search(raw_html_or_text)
    if not m:
        return None, None, None
    d1, d2, n_raw = m.group(2), m.group(4), m.group(6)
    n = int(n_raw.replace(" ", "").replace("\xa0", ""))
    return d1, d2, n


def record_itogo_observation(
    plan_id: str,
    page_id: str,
    *,
    page_version: int | None = None,
    raw_storage: str | None = None,
    storage_artifact_id: str | None = None,
    conn=None,
) -> str:
    """P1.W1.9: записать отдельное page observation «Итого»/storage, не
    привязанное 1:1 к номеру publication (R-015 §7.1, AC-110). Отсутствующий
    исторический «Итого» помечается ``unknown``, не выдумывается."""
    from mofs_index.plan import writer as plan_writer

    d1 = d2 = None
    n = None
    quality = "unknown"
    if raw_storage:
        d1, d2, n = parse_itogo_text(raw_storage)
        quality = "ok" if d1 else "unknown"

    spec = plan_writer.PageObservationSpec(
        plan_id=plan_id,
        page_id=page_id,
        page_version=page_version,
        storage_artifact_id=storage_artifact_id,
        itogo_raw=raw_storage,
        itogo_text=f"Итого: с {d1} по {d2} - {n} рабочих дней" if d1 else None,
        itogo_d1=d1,
        itogo_d2=d2,
        itogo_n=n,
        quality=quality,
    )
    own_conn = conn is None
    if own_conn:
        from mofs_index.db import connect_durable
        conn = connect_durable()
    try:
        return plan_writer.record_page_observation(conn, spec)
    finally:
        if own_conn:
            conn.close()


def verify_itogo(storage: str, d1: str, d2: str, n_days: int) -> dict[str, bool]:
    """One current summary, above Gantt, and no service labour block."""
    from html import unescape
    text = unescape(re.sub(r"<[^>]+>", "", storage))
    matches = list(ITOGO_LINE1_RE.finditer(text))
    values = parse_itogo_text(text)
    try:
        span = macro_span(storage)
    except ValueError:
        span = None
    prefix = unescape(re.sub(r"<[^>]+>", "", storage[:span[0]])) if span else ""
    return {
        "one_itogo": len(matches) == 1 and len(re.findall(r"Итого\s*:", text, re.I)) == 1,
        "itogo_values": values == (d1, d2, n_days),
        "itogo_above_macro": bool(ITOGO_LINE1_RE.search(prefix)),
        "no_trudozatraty": not bool(re.search(r"Трудозатрат", text, re.I)),
    }


# Prepared branch: pure computation from an already parsed immutable source.
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP, localcontext
from zoneinfo import ZoneInfo
import json


def field_value(field):
    if isinstance(field, dict):
        return field.get('value') if field.get('quality') == 'ok' else None
    return field


def decimal_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def quantity_minutes(field, project, *, working_only=False):
    """Exact minutes plus the explicit source coefficients; never assume 8h/day."""
    if not isinstance(field, dict) or field.get('quality') != 'ok':
        return None, {}, 'quantity_missing'
    q = field.get('quantity') or field.get('value')
    if not isinstance(q, dict):
        return None, {}, 'quantity_missing'
    amount = decimal_value(q.get('amount'))
    unit = q.get('units')
    elapsed = q.get('elapsed')
    if amount is None or not isinstance(unit, str) or type(elapsed) is not bool:
        return None, {}, 'quantity_invalid'
    if elapsed != unit.startswith('ELAPSED_'):
        return None, {}, 'elapsed_unit_conflict'
    if elapsed and working_only:
        return None, {}, 'elapsed_to_working_undefined'
    unit = unit.removeprefix('ELAPSED_')
    coefficients = {'MINUTES': Decimal(1), 'HOURS': Decimal(60)}
    parameters = {}
    if unit in ('DAYS', 'WEEKS', 'MONTHS', 'YEARS'):
        if elapsed:
            # Months/years have no fixed elapsed length.
            factor = {'DAYS': Decimal(1440), 'WEEKS': Decimal(10080)}.get(unit)
        else:
            key = 'minutes_per_' + {'DAYS':'day','WEEKS':'week','MONTHS':'month','YEARS':'year'}[unit]
            factor = decimal_value(field_value(project.get(key)))
            parameters[key] = str(factor) if factor is not None else None
        if factor is None or factor <= 0:
            return None, parameters, 'source_unit_basis_missing'
    else:
        factor = coefficients.get(unit)
    if factor is None:
        return None, parameters, 'unknown_quantity_units'
    return amount * factor, parameters, None


def summary_roots(data):
    tasks = {t['task_key']: t for t in data['tasks'] if 'error' not in t}
    roots = []
    for key, task in tasks.items():
        if task.get('id') == 0 or task.get('summary') is not True or not task.get('name'):
            continue
        parent = field_value(task.get('parent_task_key'))
        seen = {key}
        while parent in tasks and tasks[parent].get('id') == 0:
            if parent in seen:
                raise ValueError('cyclic_task_hierarchy')
            seen.add(parent)
            parent = field_value(tasks[parent].get('parent_task_key'))
        if parent is None:
            roots.append(key)
    return roots


def format_work_hours(value):
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = max(50, len(Decimal(value).as_tuple().digits) + 10)
        out = format(Decimal(value).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP), 'f')
    return out.rstrip('0').rstrip('.') if '.' in out else out


def work_metrics(data):
    tasks = {t['task_key']:t for t in data['tasks'] if 'error' not in t}
    total = Decimal(0)
    known = missing = excluded = 0
    seen = {}
    per_task = {}
    reasons = []
    with localcontext() as ctx:
        ctx.prec = 80
        for a in data['assignments']:
            key = a.get('assignment_key')
            if key in seen:
                if seen[key] != a:
                    missing += 1; reasons.append('conflicting_assignment_identity')
                continue
            if key is not None:
                seen[key] = a
            t = tasks.get(a.get('task_key'))
            if t and (t.get('id') == 0 or t.get('summary') is True):
                excluded += 1
                continue
            if not t or 'error' in a or t.get('summary') is None or t.get('id') is None or key is None:
                missing += 1; reasons.append('assignment_scope_unknown'); continue
            minutes, _, reason = quantity_minutes(a.get('work'), data['project'])
            task_total = per_task.setdefault(t['task_key'], {'known_hours': Decimal(0), 'missing': 0, 'known': 0})
            if reason:
                missing += 1; task_total['missing'] += 1; reasons.append(reason); continue
            hours = minutes / Decimal(60)
            total += hours; known += 1
            task_total['known_hours'] += hours; task_total['known'] += 1
    status = data['collections']['assignments']['status']
    complete = status == 'complete' and missing == 0
    value = str(total) if known or complete else None
    return {'hours':value, 'display_hours':format_work_hours(value),
            'quality':'complete' if complete else 'partial' if known else status if status != 'complete' else 'missing',
            'known_assignments':known, 'missing_assignments':missing, 'excluded_assignments':excluded,
            'reasons':sorted(set(reasons)),
            'per_task':{key:{**v,'known_hours':str(v['known_hours']),
                             'hours':str(v['known_hours']) if v['known'] or complete else None,
                             'quality':'partial' if v['missing'] or status != 'complete' else 'complete'}
                        for key,v in per_task.items()}}


def compute_itogo_from_prepared(prepared, *, root_task_key=None, summary_profile=None):
    from prepared_plan import ROOT, fingerprint
    prepared.validate()
    data = prepared.normalized_data
    expected = json.loads((ROOT / 'references/profiles/summary-v1.json').read_text())
    profile = summary_profile or expected
    if profile != expected:
        raise ValueError('unsupported_summary_profile')
    candidates = summary_roots(data)
    if root_task_key is None:
        chosen = candidates[0] if len(candidates) == 1 else None
    elif root_task_key not in candidates:
        raise ValueError('invalid_summary_root_choice')
    else:
        chosen = root_task_key
    reasons = []
    out = {'profile':profile['id'], 'profile_fingerprint':fingerprint(profile), 'root_candidates':candidates,
           'root_task_key':chosen, 'explicit_root_choice':root_task_key is not None,
           'start':None, 'finish':None, 'd1':None, 'd2':None, 'n_days':None,
           'duration_working_days':None,'source_duration':None,'coefficients':{}, 'work':work_metrics(data)}
    if chosen is None:
        reasons.append('summary_root_choice_required' if candidates else 'summary_root_missing')
    else:
        root = next(t for t in data['tasks'] if t.get('task_key') == chosen)
        out.update(start=field_value(root.get('start')), finish=field_value(root.get('finish')), source_duration=root.get('duration'))
        with localcontext() as ctx:
            ctx.prec = 80
            minutes, coefficients, reason = quantity_minutes(root.get('duration'), data['project'], working_only=True)
            per_day = decimal_value(field_value(data['project'].get('minutes_per_day')))
            coefficients['minutes_per_day'] = str(per_day) if per_day is not None else None
            out['coefficients'] = coefficients
            if reason or per_day is None or per_day <= 0 or minutes is None or minutes < 0:
                reasons.append(reason or 'source_day_basis_missing')
            else:
                days = minutes / per_day
                out['duration_working_days'] = str(days)
                out['n_days'] = int(days.to_integral_value(rounding=ROUND_CEILING))
        tz = data.get('resolved_timezone')
        if not tz:
            reasons.append('summary_timezone_unresolved')
        for src, dst in [('start','d1'),('finish','d2')]:
            if out[src] is None:
                reasons.append('summary_date_missing'); continue
            try:
                dt = datetime.fromisoformat(out[src].replace('Z','+00:00'))
                if tz and dt.tzinfo:
                    dt = dt.astimezone(ZoneInfo(tz))
                if tz:
                    out[dst] = dt.strftime('%d.%m.%y')
            except ValueError:
                reasons.append('summary_date_invalid')
    valid_tasks = [t for t in data['tasks'] if 'error' not in t]
    out['counts'] = {'task_count':len(valid_tasks),'archive_task_count':len(valid_tasks),
                     'service_task_count':sum(t.get('id') == 0 for t in valid_tasks),
                     'display_task_count':sum(t.get('id') != 0 for t in valid_tasks),
                     'dependency_count':sum('error' not in d for d in data['dependencies']),
                     'external_dependency_count':sum('error' not in d for d in data['external_dependencies']),
                     'task_extraction_errors':sum('error' in t for t in data['tasks'])}
    out['reasons'] = sorted(set(reasons))
    out['publishable'] = not reasons
    out['storage_html'] = build_itogo_html(out['d1'],out['d2'],out['n_days'],0) if not reasons else None
    return out
