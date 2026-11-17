from __future__ import annotations

import pytest

from mpp_calendar import base_recurrent_intervals, calendar_from_mpp


def test_base_recurrent_intervals():
    ivs = base_recurrent_intervals()
    assert len(ivs) == 4
    lunch = ivs[0]
    assert lunch["recurrentStartDate"] == "at 12:00"
    assert lunch["recurrentEndDate"] == "at 13:00"
    night = ivs[1]
    assert night["recurrentStartDate"] == "at 18:00"
    assert night["recurrentEndDate"] == "at 09:00"


@pytest.mark.slow
def test_calendar_from_mpp_fixture(mpp_fixture):
    cal = calendar_from_mpp(mpp_fixture)
    assert len(cal) == 1
    assert cal[0]["id"] == "general"
    intervals = cal[0]["intervals"]
    assert len(intervals) > 4
    exceptions = [i for i in intervals if "startDate" in i]
    assert exceptions
    for ex in exceptions:
        assert ex["endDate"].endswith("00:00")
        assert ex["isWorking"] is False


from copy import deepcopy
from prepared_plan import PreparedPlan
from mpp_calendar import calendar_from_prepared


def test_prepared_calendar_intervals_exceptions_inheritance_bindings(stage08_export,stage08_profile):
    child=deepcopy(stage08_export['calendars'][0]);child.update(calendar_key='child',name='Child')
    child['parent_key']['value']='cal';child['parent_key'].update(quality='ok',reason=None)
    child['weekdays'][0]['day_type']['value']='DEFAULT'
    stage08_export['calendars'].append(child);stage08_export['collections']['calendars']['count']+=1
    p=PreparedPlan.from_export(stage08_export)
    out=calendar_from_prepared(p,plugin_profile=stage08_profile)
    base=out['calendarsData'][0];ivs=base['intervals']
    monday=[iv for iv in ivs if iv.get('recurrentStartDate','').startswith('on Mon')]
    assert [iv['recurrentStartDate'] for iv in monday]==['on Mon at 09:00','on Mon at 13:00']
    exception=[iv for iv in ivs if 'startDate' in iv]
    assert exception[0]['endDate']=='2026-01-07T00:00:00'
    assert exception[1]['startDate']=='2026-01-06T10:00:00'
    assert out['calendarsData'][0]['children'][0]['parentId']==base['id']
    assert out['bindings']['project']=='cal'
    assert out['bindings']['tasks']['a']['effective']=='cal'
    assert out['bindings']['resources']['r1']['explicit']=='cal'
    assert out['bindings']['assignments']['asn1']=='cal'
    assert out['source_calendars']==stage08_export['calendars']


def test_prepared_calendar_unsupported_is_explicit(stage08_export,stage08_profile):
    stage08_profile.document['capabilities']['calendar:exceptions']['status']='not_verified'
    stage08_profile.document['capabilities']['calendar:bindings:resources']['status']='not_verified'
    stage08_export['calendars'][0]['work_weeks']=[{'name':'Special'}]
    stage08_export['resources'][0]['calendar_key']['value']='different'
    result=calendar_from_prepared(PreparedPlan.from_export(stage08_export),plugin_profile=stage08_profile)
    codes={d['code'] for d in result['diagnostics']}
    assert {'calendar_exceptions_unsupported','calendar_binding_unsupported','calendar_work_weeks_unsupported'}<=codes
    assert not any('startDate' in iv for iv in result['calendarsData'][0]['intervals'])



def test_prepared_calendar_source_day_basis_mismatch_is_explicit(stage08_export):
    from plugin_profile import PluginProfile
    stage08_export['project']['minutes_per_day']['value']='300'
    result=calendar_from_prepared(PreparedPlan.from_export(stage08_export),plugin_profile=PluginProfile.load())
    mismatch=next(d for d in result['diagnostics'] if d['code']=='calendar_duration_day_basis_mismatch')
    assert mismatch['source']=={'project_minutes_per_day':'300','calendar_minutes_per_day':None,'plugin_day_minutes_from_intervals':'480'}
