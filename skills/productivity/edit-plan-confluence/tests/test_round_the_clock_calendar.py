"""Owner-directed 24/7 calendar recognition is exact and fail-closed."""
from __future__ import annotations

from copy import deepcopy
import pytest

from plan_policy import round_the_clock_calendars, owner_decision

pytestmark = pytest.mark.unit
DAYS = ('MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY')


def calendar_24h(source):
    data = deepcopy(source)
    cal = data['calendars'][0]
    by_day = {d['day']: d for d in cal['weekdays']}
    cal['weekdays'] = [by_day[d] for d in reversed(DAYS)]
    for day in cal['weekdays']:
        day['day_type'] = {'value':'WORKING','quality':'ok','reason':None}
        day['working'] = {'value':True,'quality':'ok','reason':None}
        day['intervals'] = {'value':[{
            'start':{'value':'00:00','quality':'ok','reason':None},
            'end':{'value':'00:00:00','quality':'ok','reason':None}},
        ],'quality':'ok','reason':None}
    cal['weekdays_quality'] = 'ok'
    cal['exceptions'] = []
    cal['exceptions_quality'] = {'status':'complete','count':0,'reason':None}
    cal['work_weeks'] = []
    cal['work_weeks_quality'] = {'status':'complete','count':0,'reason':None}
    data['collections']['calendars'] = {'status':'complete','enumeration_complete':True,
        'count':len(data['calendars']),'record_count':len(data['calendars']),'error_count':0,'reason':None}
    return data


def test_24h_owner_evidence():
    decision = owner_decision()
    assert decision['round_the_clock_calendar'] == 'publish_as_is'
    assert decision['round_the_clock_calendar_evidence']['decision_id'] == 'owner-20261118-round-the-clock-calendar'
    assert decision['round_the_clock_calendar_evidence_verified']['sha256'] == decision['round_the_clock_calendar_evidence']['evidence_sha256']
    assert decision['evidence_path'] == 'references/implementation/20261116/stage-13-fix4/owner-decision.md'
    assert decision['evidence_sha256'] == '22455970f9d7667bfd98ba1e249339e4ec5cc33c530ab35145de6e492e4c521d'


def test_24h_owner_evidence_corrupt_fails_closed(tmp_path, monkeypatch):
    import json
    import prepared_plan
    import plan_policy
    from pathlib import Path
    original = Path(prepared_plan.ROOT)
    target = tmp_path/'skill'
    (target/'references/profiles').mkdir(parents=True)
    (target/'references/implementation/20261116/stage-13-fix4').mkdir(parents=True)
    (target/'references/decisions').mkdir(parents=True)
    policy = json.loads((original/'references/profiles/owner-decision-v1.json').read_text())
    (target/'references/profiles/owner-decision-v1.json').write_text(json.dumps(policy))
    (target/policy['evidence_path']).write_bytes((original/policy['evidence_path']).read_bytes())
    (target/policy['round_the_clock_calendar_evidence']['evidence_path']).write_text('tampered')
    monkeypatch.setattr(prepared_plan, 'ROOT', target)
    with pytest.raises(ValueError, match='owner_decision_evidence_integrity'):
        plan_policy.owner_decision()


def test_24h_predicate(publish_case):
    data = calendar_24h(publish_case['export'])
    found = round_the_clock_calendars(data)
    assert list(found) == [data['calendars'][0]['calendar_key']]


@pytest.mark.parametrize('damage', [
    'six_days','duplicate_day','false_working','default_day','two_intervals',
    'non_midnight','seconds','24_hour_end','bad_quality','parent','exception','work_week',
    'eight_days','unknown_day','string_bool','empty_intervals','same_nonzero','partial_day',
    'missing_exception_quality','missing_work_week_quality','duplicate_calendar_key',
])
def test_predicate_rejects_near_matches(publish_case, damage):
    data = calendar_24h(publish_case['export'])
    cal = data['calendars'][0]
    if damage == 'six_days': cal['weekdays'].pop()
    elif damage == 'duplicate_day': cal['weekdays'][-1]['day'] = cal['weekdays'][0]['day']
    elif damage == 'false_working': cal['weekdays'][0]['working']['value'] = False
    elif damage == 'default_day': cal['weekdays'][0]['day_type']['value'] = 'DEFAULT'
    elif damage == 'two_intervals': cal['weekdays'][0]['intervals']['value'].append(deepcopy(cal['weekdays'][0]['intervals']['value'][0]))
    elif damage == 'non_midnight': cal['weekdays'][0]['intervals']['value'][0]['start']['value'] = '09:00'
    elif damage == 'seconds': cal['weekdays'][0]['intervals']['value'][0]['start']['value'] = '00:00:30'
    elif damage == '24_hour_end': cal['weekdays'][0]['intervals']['value'][0]['end']['value'] = '24:00'
    elif damage == 'bad_quality': cal['weekdays'][0]['intervals']['quality'] = 'partial'
    elif damage == 'parent': cal['parent_key'] = {'value':'uid:2','quality':'ok','reason':None}
    elif damage == 'exception': cal['exceptions'] = [{'from_date':'2026-01-01'}]
    elif damage == 'work_week': cal['work_weeks'] = [{'name':'special'}]
    elif damage == 'eight_days': cal['weekdays'].append(deepcopy(cal['weekdays'][0]))
    elif damage == 'unknown_day': cal['weekdays'][0]['day'] = 'FUNDAY'
    elif damage == 'string_bool': cal['weekdays'][0]['working']['value'] = 'true'
    elif damage == 'empty_intervals': cal['weekdays'][0]['intervals']['value'] = []
    elif damage == 'same_nonzero':
        cal['weekdays'][0]['intervals']['value'][0]['start']['value'] = '09:00'
        cal['weekdays'][0]['intervals']['value'][0]['end']['value'] = '09:00'
    elif damage == 'partial_day': cal['weekdays'][0]['working']['quality'] = 'partial'
    elif damage == 'missing_exception_quality': cal.pop('exceptions_quality')
    elif damage == 'missing_work_week_quality': cal.pop('work_weeks_quality')
    elif damage == 'duplicate_calendar_key': data['calendars'].append(deepcopy(cal)); data['collections']['calendars']['count'] += 1; data['collections']['calendars']['record_count'] += 1
    assert round_the_clock_calendars(data) == {}


def test_collection_must_be_complete(publish_case):
    data = calendar_24h(publish_case['export'])
    data['collections']['calendars']['enumeration_complete'] = False
    assert round_the_clock_calendars(data) == {}


def test_24h_classification(publish_case):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan, SNAPSHOT_COLUMN
    from plan_diagnostics import diagnose
    source = calendar_24h(publish_case['export'])
    prepared = PreparedPlan.from_export(source, timezone_hint='Europe/Moscow')
    profile = deepcopy(publish_case['profile'])
    original_supports = profile.supports
    profile.supports = lambda name: name == 'publication:source_snapshot_dates' or original_supports(name)
    conversion = convert_prepared_plan(prepared, plugin_profile=profile)
    root_key = conversion['summary']['root_task_key']
    root_id = conversion['mappings']['tasks'][root_key]
    nodes = {node['id']:node for root in conversion['gantt']['eventsData']
        for node in __import__('mpp_convert').flatten_events(root).values()}
    assert 'В исходнике круглосуточный календарь' in nodes[root_id][SNAPSHOT_COLUMN]
    result = diagnose(prepared, conversion, plugin_profile=profile)
    calendar_warnings = [f for f in result['findings'] if f['code']=='source_calendar_24h_publish_as_is']
    assert len(calendar_warnings) == 1
    assert calendar_warnings[0]['entity'] == source['calendars'][0]['calendar_key']
    assert calendar_warnings[0]['represented']['decision_id'] == 'owner-20261118-round-the-clock-calendar'
    assert not any(f['entity']==source['calendars'][0]['calendar_key']
        and f['code'] in ('calendar_intervals_unsupported','calendar_interval_invalid')
        for f in result['findings'])
    from plan_policy import evaluate
    from plan_diagnostics import compact_receipt_diagnostics
    admission=evaluate(result['findings'])
    _,warnings=compact_receipt_diagnostics(admission,'test-evidence')
    warning=next(w for w in warnings if w['code']=='source_calendar_24h_publish_as_is')
    assert 'снимок MPP без пересчёта' in warning['message']
    assert warning['details_ref']=='artifact:test-evidence'


@pytest.mark.parametrize('damage', ['hidden_column','altered_note','missing_root'])
def test_24h_snapshot_guard(publish_case, damage):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan, SNAPSHOT_COLUMN, flatten_events
    from plan_diagnostics import diagnose
    from plan_policy import evaluate
    source=calendar_24h(publish_case['export'])
    prepared=PreparedPlan.from_export(source,timezone_hint='Europe/Moscow')
    profile=deepcopy(publish_case['profile'])
    original_supports=profile.supports
    profile.supports=lambda name: name=='publication:source_snapshot_dates' or original_supports(name)
    conversion=convert_prepared_plan(prepared,plugin_profile=profile)
    root_key=conversion['summary']['root_task_key']; root_id=conversion['mappings']["tasks"][root_key]
    if damage=='hidden_column':
        next(c for c in conversion['gantt']['initialState']['view']['columns'] if c['id']==SNAPSHOT_COLUMN)['hidden']=True
    else:
        node=next(n for root in conversion['gantt']['eventsData'] for n in flatten_events(root).values() if n['id']==root_id)
        if damage=='altered_note': node[SNAPSHOT_COLUMN]='manually edited'
        else: node.pop(SNAPSHOT_COLUMN)
    findings=diagnose(prepared,conversion,plugin_profile=profile)['findings']
    assert not any(f['code']=='source_calendar_24h_publish_as_is' for f in findings)
    admission=evaluate(findings)
    assert admission['exit_code']==5
    assert any(f['code'].startswith('calendar_') for f in admission['blockers']), [f['code'] for f in admission['blockers']]


def test_24h_mixed_blockers(publish_case):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan
    from plan_diagnostics import diagnose
    from plan_policy import evaluate
    source=calendar_24h(publish_case['export'])
    second=deepcopy(source['calendars'][0]); second['calendar_key']='other-calendar'
    second['uid']={'value':99,'quality':'ok','reason':None}
    for day in second['weekdays']:
        day['intervals']['value'][0]['start']['value']='08:00'
        day['intervals']['value'][0]['end']['value']='12:00'
    second['weekdays'][0]['intervals']['value'][0]['start']['value']='09:00'
    second['weekdays'][0]['intervals']['value'][0]['end']['value']='08:00'
    source['calendars'].append(second)
    source['collections']['calendars']['count']=2
    source['collections']['calendars']['record_count']=2
    prepared=PreparedPlan.from_export(source,timezone_hint='Europe/Moscow')
    profile=deepcopy(publish_case['profile']); original_supports=profile.supports
    profile.supports=lambda name: name=='publication:source_snapshot_dates' or original_supports(name)
    conversion=convert_prepared_plan(prepared,plugin_profile=profile)
    findings=diagnose(prepared,conversion,plugin_profile=profile)['findings']
    assert sum(f['code']=='source_calendar_24h_publish_as_is' for f in findings)==1
    assert any(f['entity']=='other-calendar' and f['code']=='calendar_interval_invalid' for f in findings)
    admission=evaluate(findings)
    assert admission['exit_code']==5 and not admission['allowed']


def test_24h_resume_same_snapshot(publish_case, monkeypatch):
    import plan_policy
    from test_publish_prepare import prepare, _fake_raw_upload
    from test_publish_resume import resume
    from copy import deepcopy
    c=publish_case; _fake_raw_upload(c,monkeypatch)
    source=calendar_24h(c['export'])
    profile=deepcopy(c['profile']); original_supports=profile.supports
    profile.supports=lambda name: name=='publication:source_snapshot_dates' or original_supports(name)
    current=plan_policy.owner_decision
    def previous_policy():
        result=current(); result.pop('round_the_clock_calendar',None); result.pop('round_the_clock_calendar_evidence',None)
        result.pop('round_the_clock_calendar_evidence_verified',None); return result
    monkeypatch.setattr(plan_policy,'owner_decision',previous_policy)
    blocked=prepare(c,export=source,plugin_profile=profile)
    assert blocked.exit_code==5 and blocked.receipt['verification']['archive']=='verified'
    operation_id=blocked.receipt['operation_id']; snapshot_id=blocked.receipt['snapshot_id']
    monkeypatch.setattr(plan_policy,'owner_decision',current)
    resumed=resume(c,operation_id,plugin_profile=profile)
    assert resumed.exit_code==0 and resumed.receipt['published'] is True,resumed.receipt
    assert resumed.receipt['operation_id']==operation_id and resumed.receipt['snapshot_id']==snapshot_id
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0]==1
