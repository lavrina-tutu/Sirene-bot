"""Representation fixes: equivalent transformations and evidence boundaries."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from prepared_plan import PreparedPlan
from mpp_calendar import calendar_from_prepared
from mpp_convert import convert_prepared_plan
from plugin_profile import PluginProfile

pytestmark = pytest.mark.unit


def test_alias_only_for_calendar_without_any_override(stage08_export,stage08_profile):
    d=deepcopy(stage08_export);parent=d['calendars'][0]
    child=deepcopy(parent);child['calendar_key']='alias-child'
    child['parent_key']={'value':parent['calendar_key'],'quality':'ok','reason':None}
    child['exceptions']=[];child['work_weeks']=[]
    for day in child['weekdays']:
        day['day_type']={'value':'DEFAULT','quality':'ok','reason':None}
        day['intervals']={'value':None,'quality':'missing','reason':'not_set'}
    d['calendars'].append(child);d['collections']['calendars']['count']+=1
    p=PreparedPlan.from_export(d,timezone_hint='Europe/Moscow')
    out=calendar_from_prepared(p,plugin_profile=stage08_profile)
    assert out['mapping']['alias-child']==out['mapping'][parent['calendar_key']]
    assert any(t['kind']=='equivalent_calendar_alias' and t['source']==child for t in out['transformations'])
    assert p.normalized_data['calendars'][-1]==child
    d['calendars'][-1]['weekdays'][0]['day_type']['value']='NON_WORKING'
    out=calendar_from_prepared(PreparedPlan.from_export(d,timezone_hint='Europe/Moscow'),plugin_profile=stage08_profile)
    assert out['mapping']['alias-child']!=out['mapping'][parent['calendar_key']]


def test_one_working_envelope_is_not_a_split_loss(stage08_export,stage08_profile):
    d=deepcopy(stage08_export);task=d['tasks'][1]
    raw={'value':[{'start':deepcopy(task['start']),'end':deepcopy(task['finish'])}],'quality':'ok','reason':None}
    task['segments']=raw
    p=PreparedPlan.from_export(d,timezone_hint='Europe/Moscow')
    c=convert_prepared_plan(p,plugin_profile=stage08_profile)
    assert not any(x['code']=='task_semantics_unrepresented:segments' and x['entity']==task['task_key'] for x in c['diagnostics'])
    tr=next(t for t in c['semantic_transformations'] if t['entity']==task['task_key'] and t['field']=='segments')
    assert tr['source']==raw and tr['normalized']==[]
    assert p.normalized_data['tasks'][1]['segments']==raw
    task['segments']['value'][0]['start']['value']='2026-01-01T09:00:00'
    c=convert_prepared_plan(PreparedPlan.from_export(d,timezone_hint='Europe/Moscow'),plugin_profile=stage08_profile)
    assert any(x['code']=='task_semantics_unrepresented:segments' for x in c['diagnostics'])


def test_installed_claim_cannot_reuse_unrelated_control():
    d=deepcopy(PluginProfile.load().document)
    d['capabilities']['task:actual_start']={'status':'tested_supported',
        'evidence':d['capabilities']['relation:FS']['evidence'],'scope':'invalid unrelated evidence'}
    with pytest.raises(ValueError,match='capability_without_behavior_control'):
        PluginProfile(d).validate()


def test_supported_fields_and_segment_working_duration(stage08_export,stage08_profile):
    d=deepcopy(stage08_export);task=d['tasks'][1]
    def field(v):return {'value':v,'quality':'ok','reason':None}
    task.update(task_type=field('FIXED_UNITS'),constraint_type=field('START_NO_EARLIER_THAN'),
                constraint_date=field('2026-01-07T09:00:00'),active=field(False),
                start=field('2026-01-07T09:00:00'),finish=field('2026-01-09T18:00:00'))
    task['duration']={'value':'2 d','quality':'ok','reason':None,'quantity':{'amount':'2','units':'DAYS','source_units':'d','elapsed':False}}
    task['segments']=field([{'start':field('2026-01-07T09:00:00'),'end':field('2026-01-07T18:00:00')},
                            {'start':field('2026-01-09T09:00:00'),'end':field('2026-01-09T18:00:00')}])
    cap=deepcopy(stage08_profile.document['capabilities']['relation:FS'])
    for name in ('task:segments','task:active','task:task_type:FIXED_UNITS','task:constraint:START_NO_EARLIER_THAN'):
        stage08_profile.document['capabilities'][name]=deepcopy(cap)
    c=convert_prepared_plan(PreparedPlan.from_export(d,timezone_hint='Europe/Moscow'),plugin_profile=stage08_profile)
    from plan_diagnostics import flatten
    node=flatten(c['gantt']['eventsData'])[c['mappings']['tasks'][task['task_key']]]
    assert node['schedulingMode']=='FixedUnits' and node['inactive'] is True
    assert node['constraintType']=='startnoearlierthan' and node['constraintDate']=='2026-01-07T09:00:00'
    assert [part['duration'] for part in node['segments']]==[1,1]
    assert node['manuallyScheduled'] is False
    task['duration']['quantity']['amount']='3'
    c=convert_prepared_plan(PreparedPlan.from_export(d,timezone_hint='Europe/Moscow'),plugin_profile=stage08_profile)
    assert any(x['code']=='segment_duration_source_mismatch' for x in c['diagnostics'])
