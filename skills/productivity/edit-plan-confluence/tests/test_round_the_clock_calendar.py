"""Owner-directed calendar v2: calendar is out of admission; task values stay exact."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest

SKILL = Path(__file__).resolve().parents[1]
V2_ID = 'owner-20261118-calendar-publish-as-is-v2'
V2_SHA = '7ede8a9c5a098c89f1c17897163d8acf925b16d2ba41176de51e117dbf5b16b3'


@pytest.mark.unit
def test_calendar_owner_v2():
    from plan_policy import owner_decision, calendar_publish_as_is
    policy = owner_decision()
    active, authority = calendar_publish_as_is()
    assert active is True
    assert policy['calendar'] == 'publish_as_is'
    assert policy['calendar_evidence']['decision_id'] == V2_ID
    assert policy['calendar_evidence_verified']['sha256'] == V2_SHA
    assert authority['decision_id'] == V2_ID
    assert hashlib.sha256((SKILL / policy['calendar_evidence']['evidence_path']).read_bytes()).hexdigest() == V2_SHA
    assert 'round_the_clock_calendar' not in policy


@pytest.mark.parametrize('damage', ['value', 'id', 'path', 'hash', 'missing'])
@pytest.mark.unit
def test_calendar_owner_invalid(tmp_path, monkeypatch, damage):
    import prepared_plan, plan_policy
    from plan_policy import owner_decision
    original_root = Path(prepared_plan.ROOT)
    target = tmp_path / 'skill'
    (target / 'references/profiles').mkdir(parents=True)
    (target / 'references/decisions').mkdir(parents=True)
    (target / 'references/implementation/20261116/stage-13-fix4').mkdir(parents=True)
    policy = json.loads((original_root / 'references/profiles/owner-decision-v1.json').read_text())
    (target / policy['evidence_path']).write_bytes((original_root / policy['evidence_path']).read_bytes())
    evidence_path = target / 'references/decisions/owner-calendar-20261118-v2.md'
    evidence_path.write_bytes((original_root / 'references/decisions/owner-calendar-20261118-v2.md').read_bytes())
    if damage == 'value': policy['calendar'] = 'ignore'
    elif damage == 'id': policy['calendar_evidence']['decision_id'] = 'other'
    elif damage == 'path': policy['calendar_evidence']['evidence_path'] = '../decisions/owner-calendar-20261118-v2.md'
    elif damage == 'hash': policy['calendar_evidence']['evidence_sha256'] = '0' * 64
    elif damage == 'missing': policy.pop('calendar_evidence')
    (target / 'references/profiles/owner-decision-v1.json').write_text(json.dumps(policy))
    monkeypatch.setattr(prepared_plan, 'ROOT', target)
    with pytest.raises((ValueError, KeyError)):
        owner_decision()


@pytest.mark.unit
def test_calendar_without_directive_blocks(publish_case, monkeypatch):
    import plan_policy
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan
    from plan_diagnostics import diagnose
    original = plan_policy.owner_decision
    def no_v2():
        policy = original()
        policy.pop('calendar', None)
        policy.pop('calendar_evidence', None)
        policy.pop('calendar_evidence_verified', None)
        return policy
    monkeypatch.setattr(plan_policy, 'owner_decision', no_v2)
    source = deepcopy(publish_case['export'])
    source['calendars'][0]['weekdays'][0]['intervals'] = {'value':None,'quality':'unsupported','reason':'getter_missing'}
    prepared = PreparedPlan.from_export(source, timezone_hint='Europe/Moscow')
    conversion = convert_prepared_plan(prepared, plugin_profile=deepcopy(publish_case['profile']))
    result = diagnose(prepared, conversion, plugin_profile=deepcopy(publish_case['profile']))
    assert any(f['code'].startswith('calendar_') for f in result['findings'])


@pytest.mark.unit
def test_calendar_not_inspected(publish_case, monkeypatch):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan
    import mpp_calendar
    def forbidden(*args, **kwargs):
        raise AssertionError('calendar analyzer called')
    monkeypatch.setattr(mpp_calendar, 'calendar_from_prepared', forbidden)
    prepared = PreparedPlan.from_export(deepcopy(publish_case['export']), timezone_hint='Europe/Moscow')
    profile = deepcopy(publish_case['profile'])
    convert_prepared_plan(prepared, plugin_profile=profile)


@pytest.mark.unit
def test_calendar_classification(publish_case):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan
    from plan_diagnostics import diagnose, compact_receipt_diagnostics
    from plan_policy import evaluate
    prepared = PreparedPlan.from_export(deepcopy(publish_case['export']), timezone_hint='Europe/Moscow')
    profile = deepcopy(publish_case['profile'])
    result = diagnose(prepared, convert_prepared_plan(prepared, plugin_profile=profile), plugin_profile=profile)
    warnings = [f for f in result['findings'] if f['code'] == 'source_calendar_publish_as_is']
    assert len(warnings) == 1
    assert warnings[0]['represented']['calendar_analysis'] == 'not_performed'
    admission = evaluate(result['findings'])
    assert admission['schedule']['status'] == 'not_verified'
    _, compact = compact_receipt_diagnostics(admission, 'test-evidence')
    warning = next(w for w in compact if w['code'] == 'source_calendar_publish_as_is')
    assert warning['details_ref'] == 'artifact:test-evidence'


@pytest.mark.unit
def test_calendar_noncalendar_blockers(publish_case):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan
    from plan_diagnostics import diagnose
    from plan_policy import evaluate
    prepared = PreparedPlan.from_export(deepcopy(publish_case['export']), timezone_hint='Europe/Moscow')
    profile = deepcopy(publish_case['profile'])
    conversion = convert_prepared_plan(prepared, plugin_profile=profile)
    conversion['diagnostics'].append({'code':'task_dates_missing','entity':'negative-control','source':None,'represented':None})
    result = diagnose(prepared, conversion, plugin_profile=profile)
    admission = evaluate(result['findings'])
    assert admission['exit_code'] == 5
    assert any(f['entity'] == 'negative-control' for f in admission['blockers'])


@pytest.mark.unit
def test_calendar_exact_source_values(publish_case):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan, flatten_events
    from itogo import field_value
    from decimal import Decimal
    prepared = PreparedPlan.from_export(deepcopy(publish_case['export']), timezone_hint='Europe/Moscow')
    profile = deepcopy(publish_case['profile'])
    conversion = convert_prepared_plan(prepared, plugin_profile=profile)
    nodes = {i:n for root in conversion['gantt']['eventsData'] for i,n in flatten_events(root).items()}
    for task in prepared.normalized_data['tasks']:
        if task.get('id') == 0 or 'error' in task:
            continue
        node = nodes[conversion['mappings']['tasks'][task['task_key']]]
        assert node['startDate'] == field_value(task.get('start'))
        assert node['endDate'] == field_value(task.get('finish'))
        from itogo import quantity_minutes
        minutes, _, _ = quantity_minutes(task.get('duration'), prepared.normalized_data['project'], working_only=True)
        per_day = Decimal(str(field_value(prepared.normalized_data['project'].get('minutes_per_day'))))
        assert Decimal(str(node['duration'])) * per_day == minutes


@pytest.mark.parametrize('damage', ['hidden_column', 'altered_note', 'missing_root'])
@pytest.mark.unit
def test_calendar_snapshot_guard(publish_case, damage):
    from prepared_plan import PreparedPlan
    from mpp_convert import convert_prepared_plan, SNAPSHOT_COLUMN, flatten_events
    from plan_diagnostics import diagnose
    prepared = PreparedPlan.from_export(deepcopy(publish_case['export']), timezone_hint='Europe/Moscow')
    profile = deepcopy(publish_case['profile'])
    supports = profile.supports
    # The generic unit profile does not claim snapshot publication. This guard
    # fixture must opt into that exact capability before preparing its view.
    profile.supports = lambda name: name == 'publication:source_snapshot_dates' or supports(name)
    conversion = convert_prepared_plan(prepared, plugin_profile=profile)
    root_key = conversion['summary']['root_task_key']
    root_id = conversion['mappings']['tasks'][root_key]
    node = next(n for root in conversion['gantt']['eventsData'] for n in flatten_events(root).values() if n['id'] == root_id)
    if damage == 'hidden_column':
        next(c for c in conversion['gantt']['initialState']['view']['columns'] if c['id'] == SNAPSHOT_COLUMN)['hidden'] = True
    elif damage == 'altered_note': node[SNAPSHOT_COLUMN] = 'edited'
    else: node.pop(SNAPSHOT_COLUMN)
    findings = diagnose(prepared, conversion, plugin_profile=profile)['findings']
    assert any(f['code'] == 'source_snapshot_display_unverified' for f in findings)


@pytest.mark.unit
def test_calendar_resume_same_snapshot(publish_case, monkeypatch):
    import plan_policy
    from test_publish_prepare import prepare, _fake_raw_upload
    from test_publish_resume import resume
    case = publish_case
    _fake_raw_upload(case, monkeypatch)
    profile = deepcopy(case['profile']); supports = profile.supports
    profile.supports = lambda name: name == 'publication:source_snapshot_dates' or supports(name)
    source = calendar_24h(case['export'])
    current = plan_policy.owner_decision
    def previous_policy():
        result = current(); result.pop('calendar', None); result.pop('calendar_evidence', None)
        result.pop('calendar_evidence_verified', None); return result
    monkeypatch.setattr(plan_policy, 'owner_decision', previous_policy)
    blocked = prepare(case, export=source, plugin_profile=profile)
    assert blocked.exit_code == 5 and blocked.receipt['verification']['archive'] == 'verified'
    operation_id, snapshot_id = blocked.receipt['operation_id'], blocked.receipt['snapshot_id']
    monkeypatch.setattr(plan_policy, 'owner_decision', current)
    resumed = resume(case, operation_id, plugin_profile=profile)
    assert resumed.exit_code == 0 and resumed.receipt['published'] is True
    assert resumed.receipt['operation_id'] == operation_id
    assert resumed.receipt['snapshot_id'] == snapshot_id
    assert case['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0] == 1


@pytest.mark.mpp_fixtures
def test_calendar_real_zd(tmp_path, monkeypatch):
    import os, subprocess
    from env import select_mpxj_python
    from plan_context import PlanContext
    from prepared_plan import PreparedPlan
    from plugin_profile import PluginProfile
    from mpp_convert import convert_prepared_plan
    from plan_diagnostics import diagnose
    from plan_policy import evaluate
    source = Path(os.environ.get('EDITPLAN_ZD_MPP',
        '/home/tkachenkoav/WorkVault/Entities/zd/Sources/plans/zd.ganttchart/artifacts/'
        '777641df7b9bae75e13a566fec315cc7cac5864c31214ab03c46603add7abe17.mpp'))
    if not source.is_file():
        pytest.skip('ZD binary fixture is unavailable')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == '777641df7b9bae75e13a566fec315cc7cac5864c31214ab03c46603add7abe17'
    runtime = select_mpxj_python(); context = PlanContext.resolve()
    proc = subprocess.run([runtime.python, str(context.mpp_reader/'plan_export.py'), str(source)],
        capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr
    raw = proc.stdout[proc.stdout.index('{'):]
    export = json.loads(raw)
    assert export['telemetry']['MPXJ_read'] == 1
    prepared = PreparedPlan.from_export(export, timezone_hint='Europe/Moscow')
    profile = PluginProfile.load()
    import mpp_calendar, plan_policy
    monkeypatch.setattr(mpp_calendar, 'calendar_from_prepared', lambda *a, **k: (_ for _ in ()).throw(AssertionError('calendar analyzer called')))
    monkeypatch.setattr(plan_policy, 'round_the_clock_calendars', lambda *a, **k: (_ for _ in ()).throw(AssertionError('calendar predicate called')))
    conversion = convert_prepared_plan(prepared, plugin_profile=profile)
    result = diagnose(prepared, conversion, plugin_profile=profile)
    admission = evaluate(result['findings'])
    assert len(export['tasks']) == 34 and conversion['summary']['counts']['display_task_count'] == 33
    assert len(export['dependencies']) == 35
    assert admission['schedule']['status'] == 'not_verified'
    assert admission['allowed'] is True, admission
    assert not [check for check in result['dates'] if check.get('field') and check.get('delta_seconds') not in (0, 0.0)]


@pytest.mark.confluence_live
def test_calendar_live_snapshot():
    import os
    if os.environ.get('EDITPLAN_LIVE') != '1':
        pytest.skip('explicit live environment is not enabled')
    pytest.skip('live assertion is owned by the stage-13 ZD operation observer and receipt')

# Retained v1 node IDs are regression checks for the retired recognizer only;
# none of these predicates participate in active v2 admission.
DAYS = ('MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY')

def calendar_24h(source):
    data = deepcopy(source)
    cal = data['calendars'][0]
    by_day = {d['day']: d for d in cal['weekdays']}
    cal['weekdays'] = [by_day[d] for d in reversed(DAYS)]
    for day in cal['weekdays']:
        day['day_type'] = {'value':'WORKING','quality':'ok','reason':None}
        day['working'] = {'value':True,'quality':'ok','reason':None}
        day['intervals'] = {'value':[{'start':{'value':'00:00','quality':'ok','reason':None},
            'end':{'value':'00:00:00','quality':'ok','reason':None}}],'quality':'ok','reason':None}
    cal['weekdays_quality'] = 'ok'; cal['exceptions'] = []; cal['work_weeks'] = []
    cal['exceptions_quality'] = {'status':'complete','count':0,'reason':None}
    cal['work_weeks_quality'] = {'status':'complete','count':0,'reason':None}
    data['collections']['calendars'] = {'status':'complete','enumeration_complete':True,
        'count':len(data['calendars']),'record_count':len(data['calendars']),'error_count':0,'reason':None}
    return data


@pytest.mark.unit
def test_24h_owner_evidence():
    test_calendar_owner_v2()


@pytest.mark.unit
def test_24h_owner_evidence_corrupt_fails_closed(tmp_path, monkeypatch):
    test_calendar_owner_invalid(tmp_path, monkeypatch, 'hash')


@pytest.mark.unit
def test_24h_predicate(publish_case):
    from plan_policy import round_the_clock_calendars
    data = calendar_24h(publish_case['export'])
    assert list(round_the_clock_calendars(data)) == [data['calendars'][0]['calendar_key']]


@pytest.mark.parametrize('damage', [
    'six_days','duplicate_day','false_working','default_day','two_intervals','non_midnight','seconds',
    '24_hour_end','bad_quality','parent','exception','work_week','eight_days','unknown_day','string_bool',
    'empty_intervals','same_nonzero','partial_day','missing_exception_quality','missing_work_week_quality','duplicate_calendar_key',
])
@pytest.mark.unit
def test_predicate_rejects_near_matches(publish_case, damage):
    from plan_policy import round_the_clock_calendars
    data = calendar_24h(publish_case['export']); cal = data['calendars'][0]
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
        cal['weekdays'][0]['intervals']['value'][0]['start']['value'] = '09:00'; cal['weekdays'][0]['intervals']['value'][0]['end']['value'] = '09:00'
    elif damage == 'partial_day': cal['weekdays'][0]['working']['quality'] = 'partial'
    elif damage == 'missing_exception_quality': cal.pop('exceptions_quality')
    elif damage == 'missing_work_week_quality': cal.pop('work_weeks_quality')
    elif damage == 'duplicate_calendar_key': data['calendars'].append(deepcopy(cal)); data['collections']['calendars']['count'] += 1; data['collections']['calendars']['record_count'] += 1
    assert round_the_clock_calendars(data) == {}


@pytest.mark.unit
def test_collection_must_be_complete(publish_case):
    from plan_policy import round_the_clock_calendars
    data = calendar_24h(publish_case['export']); data['collections']['calendars']['enumeration_complete'] = False
    assert round_the_clock_calendars(data) == {}


@pytest.mark.unit
def test_24h_classification(publish_case):
    test_calendar_classification(publish_case)


@pytest.mark.parametrize('damage', ['hidden_column','altered_note','missing_root'])
@pytest.mark.unit
def test_24h_snapshot_guard(publish_case, damage):
    test_calendar_snapshot_guard(publish_case, damage)


@pytest.mark.unit
def test_24h_mixed_blockers(publish_case):
    test_calendar_noncalendar_blockers(publish_case)


@pytest.mark.unit
def test_24h_resume_same_snapshot(publish_case, monkeypatch):
    test_calendar_resume_same_snapshot(publish_case, monkeypatch)
