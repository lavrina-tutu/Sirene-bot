"""Owner source semantics, mtime and archived task/link history regressions."""
from copy import deepcopy
import hashlib
import json
import os
import pytest

from test_fix2_schedule_boundaries import converted
from test_plan_save import save_case
from plan_diagnostics import capability_findings, flatten
from mpp_convert import convert_prepared_plan, UNASSIGNED_COLUMN
from prepared_plan import PreparedPlan

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('damage', ['none','text','hidden','date','resource_uid','error'])
def test_missing_resource_requires_exact_source_display(damage):
    data, prepared, profile, conversion = converted('D')
    assignment = next(a for a in data['assignments'] if a['assignment_key']=='uid:441')
    if damage in ('resource_uid','error'):
        if damage == 'resource_uid':
            assignment['resource_uid'] = {'value':99999,'quality':'ok','reason':None}
        else:
            assignment['error'] = 'read_failed'
        from mpp_convert import build_assignments
        diagnostics = []
        build_assignments([assignment], conversion['mappings']['tasks'], {}, 1000,
            diagnostics=diagnostics, source_tasks={t['task_key']:t for t in data['tasks']})
        assert any(d['code']=='assignment_partial' for d in diagnostics)
        return
    node = flatten(conversion['gantt']['eventsData'])[conversion['mappings']['tasks'][assignment['task_key']]]
    assert 'resource_uid: missing' in node[UNASSIGNED_COLUMN]
    if damage == 'text': node[UNASSIGNED_COLUMN] = ''
    elif damage == 'date': node['endDate'] = '2099-01-01T09:00'
    elif damage == 'hidden':
        next(c for c in conversion['gantt']['initialState']['view']['columns'] if c['id']==UNASSIGNED_COLUMN)['hidden'] = True
    findings = capability_findings(prepared.normalized_data, profile, conversion)
    row = next(f for f in findings if f['entity']=='uid:441' and f['code'].startswith('unassigned_resource_'))
    assert row['category'] == ('display_only' if damage=='none' else 'unsupported_semantics')
    assert conversion['source_semantics']['assignments'] == prepared.normalized_data['assignments']


@pytest.mark.archive_integration
def test_current_mtime_and_history_task_links(save_case):
    import plan_save as ps
    from plan_queries import query_history, query_compare
    from mofs_index.db import connect_durable
    from mofs_index.plan import query as q
    context, source, export = save_case
    os.utime(source, ns=(1000000000000000000,1000000000000000000))
    first = ps.save_snapshot(source,project_slug='test-project',context=context,export=export)
    assert first.exit_code == 0
    original = source.read_bytes()
    new = source.parent/'new.mpp';new.write_bytes(original+b'fixture revision')
    revised = deepcopy(export)
    revised['provenance'].update(sha256=hashlib.sha256(new.read_bytes()).hexdigest(),size_bytes=new.stat().st_size)
    old_key = next(t['task_key'] for t in revised['tasks'] if t.get('id') == 2)
    new_key = 'uid:900001'
    for task in revised['tasks']:
        if task['task_key']==old_key: task.update(task_key=new_key,uid=900001)
        for field in ('parent_task_key','child_task_keys'):
            raw = task.get(field, {})
            value = raw.get('value')
            if value==old_key: raw['value']=new_key
            if isinstance(value,list):raw['value']=[new_key if k==old_key else k for k in value]
    for group in ('dependencies','assignments'):
        for row in revised[group]:
            for key in ('task_key','predecessor_task_key','successor_task_key'):
                if row.get(key)==old_key:row[key]=new_key
    os.utime(new,ns=(2000000000000000000,2000000000000000000))
    second = ps.save_snapshot(new,project_slug='test-project',context=context,export=revised)
    assert second.exit_code == 0,second.receipt
    # A later arrival of the older file must not win over the newer mtime.
    again = ps.save_snapshot(source,project_slug='test-project',context=context,export=export)
    assert again.exit_code == 0
    params=dict(db_path=context.db,workvault=context.workvault,cache_dir=context.cache_dir)
    history = query_history(project_slug='test-project', limit=1, **params)
    current = history['result']['current_plan']
    assert current['status']=='selected' and current['snapshot_id']==second.snapshot_id
    assert current['source_mtime_ns']==2000000000000000000
    source.unlink();new.unlink()
    assert query_history(project_slug='test-project', **params)['result']['current_plan']==current
    diff = query_compare(project_slug='test-project',from_selector='snapshot:'+first.snapshot_id,
        to_selector='snapshot:'+second.snapshot_id,**params)
    assert diff['exit_code']==0,diff
    delta = diff['result']['task_history']
    assert {r['task_key'] for r in delta['removed']}=={old_key}
    assert {r['task_key'] for r in delta['added']}=={new_key}
    assert delta['identity']=='unknown'
    assert delta['removed'][0]['links'] and delta['added'][0]['links']
    assert all(old_key in (d['predecessor_task_key'],d['successor_task_key']) for d in delta['removed'][0]['links'])
    # An equal maximum across different snapshots is explicitly ambiguous.
    source.write_bytes(original);os.utime(source,ns=(2000000000000000000,2000000000000000000))
    ps.save_snapshot(source,project_slug='test-project',context=context,export=export)
    assert query_history(project_slug='test-project',**params)['result']['current_plan']['status']=='ambiguous'


@pytest.mark.parametrize('damage', ['none','manual','source_mode','hidden'])
def test_snapshot_display_preserves_dates_links_and_source_mode(damage):
    from mpp_convert import SNAPSHOT_COLUMN
    from plan_policy import evaluate
    data, prepared, profile, conversion = converted('B')
    node = next(iter(flatten(conversion['gantt']['eventsData']).values()))
    assert node['manuallyScheduled'] is True and node['skipNonWorkingTimeWhenSchedulingManually'] is False
    assert 'AUTO' in node[SNAPSHOT_COLUMN]
    assert len(conversion['gantt']['dependenciesData'])==len(data['dependencies'])
    if damage=='manual': node['manuallyScheduled']=False
    elif damage=='source_mode': node[SNAPSHOT_COLUMN]=''
    elif damage=='hidden':
        next(c for c in conversion['gantt']['initialState']['view']['columns'] if c['id']==SNAPSHOT_COLUMN)['hidden']=True
    findings = capability_findings(prepared.normalized_data,profile,conversion)
    assert evaluate(findings)['exit_code'] == (0 if damage=='none' else 5)
    assert conversion['source_semantics']['tasks']==prepared.normalized_data['tasks']


def test_zero_duration_milestone_with_different_dates_is_not_silently_fixed():
    data, prepared, profile, conversion = converted('D')
    from plan_policy import evaluate
    findings = capability_findings(prepared.normalized_data,profile,conversion)
    conflicts = [f for f in findings if f['code']=='source_milestone_interval_conflict']
    assert len(conflicts)==1 and conflicts[0]['entity']=='uid:373'
    assert conflicts[0]['source']['start']['value']=='2026-03-30T09:00'
    assert conflicts[0]['source']['finish']['value']=='2026-04-22T18:00'
    assert conflicts[0]['source']['duration']['quantity']['amount']=='0'
    assert evaluate(findings)['exit_code']==5
    assert {f['entity'] for f in findings if f['code']=='unassigned_resource_source_display'} >= {'uid:441','uid:699','uid:700','uid:701'}
