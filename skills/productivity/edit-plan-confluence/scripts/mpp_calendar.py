"""MPP default calendar → calendarsData for gantt-chart-planner."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path


def _ensure_jvm() -> None:
    import mpxj  # noqa: F401
    import jpype
    import jpype.imports  # noqa: F401

    if not jpype.isJVMStarted():
        jpype.startJVM()


def _to_str(x) -> str | None:
    return None if x is None else str(x)


def base_recurrent_intervals() -> list[dict]:
    return [
        {"recurrentStartDate": "at 12:00", "recurrentEndDate": "at 13:00", "isWorking": False},
        {"recurrentStartDate": "at 18:00", "recurrentEndDate": "at 09:00", "isWorking": False},
        {"recurrentStartDate": "on Sun", "recurrentEndDate": "on Mon", "isWorking": False},
        {"recurrentStartDate": "on Sat", "recurrentEndDate": "on Sun", "isWorking": False},
    ]


def calendar_from_mpp(mpp_path: Path) -> list[dict]:
    _ensure_jvm()
    from org.mpxj.reader import UniversalProjectReader

    pj = UniversalProjectReader().read(str(mpp_path))
    cal = pj.getDefaultCalendar()
    intervals = base_recurrent_intervals()
    for x in cal.getCalendarExceptions():
        if not x.getWorking():
            f = date.fromisoformat(_to_str(x.getFromDate()))
            t = date.fromisoformat(_to_str(x.getToDate()))
            intervals.append(
                {
                    "startDate": f.isoformat() + " 00:00",
                    "endDate": (t + timedelta(days=1)).isoformat() + " 00:00",
                    "isWorking": False,
                }
            )
    return [{"id": "general", "name": "General", "unspecifiedTimeIsWorking": True, "intervals": intervals}]


def calendar_from_prepared(prepared, *, plugin_profile):
    """Transfer source calendars, retaining every unsupported construct in evidence.

    Each calendar has explicit working windows with a nonworking default.
    Child calendars inherit only when the installed engine has been verified.
    """
    from copy import deepcopy
    from itogo import field_value
    prepared.validate()
    data = prepared.normalized_data
    out, diagnostics = [], []
    default_key = field_value(data['project'].get('default_calendar_key'))
    mapping = {c['calendar_key']: ('general' if c['calendar_key'] == default_key and plugin_profile.supports('calendar:project_id_general') else 'calendar-' + str(i + 1)) for i,c in enumerate(data['calendars']) if 'error' not in c}
    days = {'MONDAY':'Mon','TUESDAY':'Tue','WEDNESDAY':'Wed','THURSDAY':'Thu','FRIDAY':'Fri','SATURDAY':'Sat','SUNDAY':'Sun'}

    def issue(code, key, source=None):
        diagnostics.append({'code':code,'entity':key,'source':deepcopy(source),'represented':None})

    def clock(raw):
        raw = field_value(raw)
        return str(raw)[:5] if raw is not None else None

    for cal in data['calendars']:
        key = cal.get('calendar_key')
        if 'error' in cal:
            issue('calendar_unreadable',key,cal); continue
        intervals = []
        node = {'id':mapping[key],'name':cal.get('name') or key,'unspecifiedTimeIsWorking':False,'intervals':intervals}
        parent = field_value(cal.get('parent_key'))
        if parent:
            if plugin_profile.supports('calendar:inheritance') and parent in mapping:
                node['parentId'] = mapping[parent]
                node.pop('unspecifiedTimeIsWorking')
            else:
                issue('calendar_inheritance_unsupported', key, cal.get('parent_key'))
        weekdays = cal.get('weekdays',[])
        uniform = False
        if plugin_profile.supports('calendar:uniform_weekdays') and not parent:
            working_days = [d for d in weekdays if field_value(d.get('working')) is True]
            windows = field_value(working_days[0].get('intervals')) if working_days else None
            uniform = (len(weekdays) == 7 and len(windows or []) == 2
                       and all(field_value(d.get('working')) is (d.get('day') not in ('SATURDAY','SUNDAY')) for d in weekdays)
                       and all(field_value(d.get('intervals')) == windows for d in working_days)
                       and all(field_value(d.get('working')) is not None for d in weekdays))
            if uniform:
                # Ricksoft derives hoursPerDay from global nonworking time ranges.
                # Positive 'on Mon at ...' intervals do not implement that contract.
                normalized = [(clock(w.get('start')),clock(w.get('end'))) for w in windows]
                uniform = all(a and b and a < b for a,b in normalized) and all(normalized[i][1] <= normalized[i+1][0] for i in range(len(normalized)-1))
                if uniform:
                    from decimal import Decimal
                    from itogo import decimal_value
                    def minute_of_day(text):
                        hours, minutes = text.split(':')
                        return Decimal(hours) * 60 + Decimal(minutes)
                    working_minutes = sum((minute_of_day(b)-minute_of_day(a) for a,b in normalized),Decimal(0))
                    source_minutes = decimal_value(field_value(data['project'].get('minutes_per_day')))
                    calendar_minutes = decimal_value(field_value(cal.get('minutes_per_day')))
                    if source_minutes is None or source_minutes != working_minutes or calendar_minutes not in (None,source_minutes):
                        issue('calendar_duration_day_basis_mismatch',key,{
                            'project_minutes_per_day':str(source_minutes) if source_minutes is not None else None,
                            'calendar_minutes_per_day':str(calendar_minutes) if calendar_minutes is not None else None,
                            'plugin_day_minutes_from_intervals':str(working_minutes)})
                    node['unspecifiedTimeIsWorking'] = True
                    for i in range(len(normalized)-1):
                        if normalized[i][1] != normalized[i+1][0]:
                            intervals.append({'recurrentStartDate':'at '+normalized[i][1], 'recurrentEndDate':'at '+normalized[i+1][0],'isWorking':False})
                    intervals.append({'recurrentStartDate':'at '+normalized[-1][1], 'recurrentEndDate':'at '+normalized[0][0],'isWorking':False})
                    labels=list(days.values())
                    for d in weekdays:
                        if field_value(d.get('working')) is False:
                            label=days[d['day']];following=labels[(labels.index(label)+1)%7]
                            intervals.append({'recurrentStartDate':'on '+label,'recurrentEndDate':'on '+following,'isWorking':False})
        for day in ([] if uniform else weekdays):
            working = field_value(day.get('working'))
            typ = field_value(day.get('day_type'))
            windows = field_value(day.get('intervals'))
            if typ == 'DEFAULT' and parent:
                continue
            label = days.get(day.get('day'))
            if working is None or windows is None or not label:
                issue('calendar_day_incomplete',key,day); continue
            if not plugin_profile.supports('calendar:intervals'):
                issue('calendar_intervals_unsupported',key,day); continue
            # An explicit day override masks inherited time before working windows.
            if parent or not working:
                intervals.append({'recurrentStartDate':'on '+label+' at 00:00',
                                  'recurrentEndDate':'on '+label+' at 24:00','isWorking':False})
            if working:
                for window in windows:
                    start, end = clock(window.get('start')), clock(window.get('end'))
                    if not start or not end or start >= end:
                        issue('calendar_interval_invalid',key,window); continue
                    intervals.append({'recurrentStartDate':f'on {label} at {start}',
                                      'recurrentEndDate':f'on {label} at {end}','isWorking':True})
        for ex in cal.get('exceptions',[]):
            recurrence = field_value(ex.get('recurrence'))
            if recurrence is not None:
                issue('calendar_recurrence_unsupported',key,ex); continue
            first, last = field_value(ex.get('from_date')),field_value(ex.get('to_date'))
            working = field_value(ex.get('working'))
            windows = field_value(ex.get('intervals'))
            if first is None or last is None or working is None or (working and windows is None):
                issue('calendar_exception_incomplete',key,ex); continue
            if not plugin_profile.supports('calendar:exceptions'):
                issue('calendar_exceptions_unsupported',key,ex); continue
            try:
                begin, finish = date.fromisoformat(first[:10]),date.fromisoformat(last[:10])
            except ValueError:
                issue('calendar_exception_invalid',key,ex); continue
            if finish < begin:
                issue('calendar_exception_invalid',key,ex); continue
            intervals.append({'startDate':begin.isoformat()+'T00:00:00',
                              'endDate':(finish+timedelta(days=1)).isoformat()+'T00:00:00','isWorking':False,'priority':20})
            if working:
                current = begin
                while current <= finish:
                    for window in windows:
                        start,end=clock(window.get('start')),clock(window.get('end'))
                        if not start or not end or start >= end:
                            issue('calendar_exception_interval_invalid',key,window); continue
                        intervals.append({'startDate':current.isoformat()+'T'+start+':00',
                                          'endDate':current.isoformat()+'T'+end+':00','isWorking':True,'priority':30})
                    current += timedelta(days=1)
        if cal.get('work_weeks'):
            issue('calendar_work_weeks_unsupported',key,cal['work_weeks'])
        for quality in ('weekdays_quality','exceptions_quality','work_weeks_quality'):
            q=cal.get(quality)
            status=q.get('status') if isinstance(q,dict) else q
            if status not in ('ok','complete'):
                issue('calendar_collection_incomplete',key,{quality:q})
        out.append(node)
    for name in ('calendars',):
        if data['collections'][name]['status'] != 'complete':
            issue('calendar_collection_incomplete',name,data['collections'][name])
    project_calendar = field_value(data['project'].get('default_calendar_key'))
    bindings = {'project':project_calendar,
                'tasks':{t['task_key']:{'explicit':field_value(t.get('calendar_key')),'effective':field_value(t.get('effective_calendar_key'))} for t in data['tasks'] if 'error' not in t},
                'resources':{r['resource_key']:{'explicit':field_value(r.get('calendar_key')),'base':field_value(r.get('base_calendar_key'))} for r in data['resources'] if 'error' not in r},
                'assignments':{a['assignment_key']:field_value(a.get('effective_calendar_key')) for a in data['assignments'] if 'error' not in a}}
    for kind, values in bindings.items():
        if kind == 'project':
            required = values is None or not plugin_profile.supports('calendar:bindings:project')
        elif kind == 'tasks':
            required = any(v['effective'] is None or v['effective'] != project_calendar
                           or v['explicit'] not in (None,project_calendar) for v in values.values())
        elif kind == 'resources':
            required = any(v['explicit'] not in (None,project_calendar) or v['base'] not in (None,project_calendar) for v in values.values())
        else:
            required = any(v is None or v != project_calendar for v in values.values())
        if required and not plugin_profile.supports('calendar:bindings:'+kind):
            issue('calendar_binding_unsupported',kind,values)
    return {'calendarsData':out,'mapping':mapping,'bindings':bindings,
            'source_calendars':deepcopy(data['calendars']),'diagnostics':diagnostics}
