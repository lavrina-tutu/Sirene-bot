"""Each normative admission row has an executable assertion, including network denial."""
from __future__ import annotations

from copy import deepcopy
import pytest

from plan_policy import MATRIX, evaluate
from plan_diagnostics import finding, diagnose, compare_dates
from prepared_plan import PreparedPlan, fingerprint
from test_publish_prepare import prepare

pytestmark=pytest.mark.unit


@pytest.mark.parametrize('rule',MATRIX,ids=lambda r:'row-'+str(r.row))
def test_matrix_row(rule):
    f=finding(rule.category,rule.category,'test-entity')
    decision=evaluate([f])
    assert decision['exit_code']==rule.code
    assert decision['allowed']==(rule.code==0)
    assert decision['checks'][0]['row']==rule.row
    # General approval, a severity label or an unrelated proposal has no power.
    ignored=evaluate([{**f,'severity':'warning','approved':True}],proposals=[{'action':'ignore_all','losses':['anything']}])
    assert ignored['exit_code']==rule.code


@pytest.mark.parametrize('rule',[r for r in MATRIX if r.code],ids=lambda r:'row-'+str(r.row))
def test_matrix_blocker_archives_and_performs_zero_writes(rule,publish_case,monkeypatch):
    import plan_diagnostics,pipeline
    c=publish_case;original=plan_diagnostics.diagnose
    def inject(*a,**kw):
        d=original(*a,**kw);d['findings'].append(finding(rule.category,rule.category,'controlled-test'));return d
    monkeypatch.setattr(plan_diagnostics,'diagnose',inject)
    r=pipeline.publish_plan(c['client'],page_id='test-page',mpp_path=c['source'],project_slug='test',timezone_hint='Europe/Moscow',
        context=c['context'],export=c['export'],plugin_profile=c['profile'])
    assert r.exit_code==(3 if rule.category=='date_mismatch' else rule.code),r.receipt
    assert r.receipt['snapshot_id'] and r.receipt['verification']['archive']=='verified'
    assert r.receipt['published'] is False and r.receipt['external_effect']=='none'
    assert r.counters['POST']==r.counters['PUT']==0
    assert not any(call[0].startswith(('POST','PUT')) for call in c['client'].calls)


def test_specific_proposal_cannot_override_archive_or_profile():
    for category in ('incomplete','graph','unsupported_semantics','date_mismatch'):
        f=finding(category,'controlled','dep')
        proposal={'action':'exclude_dependency','finding_sha256':fingerprint(f),'losses':['one relation']}
        assert evaluate([f],proposals=[proposal])['exit_code']==3
    for category in ('archive','plugin_unknown','attachment','storage','target_conflict','network_unknown'):
        f=finding(category,'controlled','dep')
        proposal={'action':'exclude_dependency','finding_sha256':fingerprint(f),'losses':['one relation']}
        assert evaluate([f],proposals=[proposal])['exit_code'] in (4,5)


@pytest.mark.parametrize('milestone',[False,True],ids=['task','milestone'])
@pytest.mark.parametrize('seconds,expected',[(60,0),(61,5),(-61,5)])
def test_dates_each_task_and_milestone_with_matching_root(publish_case,milestone,seconds,expected,monkeypatch):
    from mpp_convert import convert_prepared_plan
    from datetime import datetime,timedelta
    import plan_policy
    original=plan_policy.owner_decision
    def without_v2():
        result=original();result.pop('calendar',None);result.pop('calendar_evidence',None);result.pop('calendar_evidence_verified',None);return result
    monkeypatch.setattr(plan_policy,'owner_decision',without_v2)
    d=deepcopy(publish_case['export']);d['tasks'][1]['milestone']=milestone
    p=PreparedPlan.from_export(d,timezone_hint='Europe/Moscow')
    result=convert_prepared_plan(p,plugin_profile=publish_case['profile'])
    node=result['gantt']['eventsData'][0]['children'][0]
    node['startDate']=(datetime.fromisoformat(node['startDate'])+timedelta(seconds=seconds)).isoformat()
    fs,checks=compare_dates(p.normalized_data,result)
    assert evaluate(fs)['exit_code']==expected
    assert len(checks)==6 and all(c['absolute_comparison'] for c in checks)


def test_unknown_timezone_never_claims_absolute_date_delta(publish_case):
    from mpp_convert import convert_prepared_plan
    p=PreparedPlan.from_export(publish_case['export'])
    r=convert_prepared_plan(p,plugin_profile=publish_case['profile'])
    _,checks=compare_dates(p.normalized_data,r)
    assert all(not c['absolute_comparison'] and c['delta_seconds'] is None for c in checks)


def test_unknown_field_blocks_but_proven_nonimpact_warns(publish_case):
    c=publish_case;d=deepcopy(c['export'])
    d['tasks'][1]['mystery']={'quality':'unsupported','value':None,'reason':'getter_unavailable'}
    assert prepare(c,export=d).exit_code==5
    from test_plan_rules import change_source
    d=change_source(c,c['export']);d['project']['status_date']={'quality':'unsupported','value':None,'reason':'getter_unavailable'}
    r=prepare(c,export=d)
    assert r.exit_code==0 and any(w['code']=='field_unsupported' for w in r.receipt['warnings'])


def test_local_scheduler_unsupported_and_plan_unobserved_are_warnings(publish_case):
    r=prepare(publish_case)
    assert r.exit_code==0 and r.receipt['verification']['schedule']['status']=='not_verified'
    assert {'local_scheduler_prepared_unsupported','specific_plan_plugin_result_not_verified'} <= {w['code'] for w in r.receipt['warnings']}


@pytest.mark.parametrize('kind',['type','signed_lag','calendar','assignment','graph_cycle','self_reference','dangling','external'])
def test_semantic_losses_block_after_archive(publish_case,kind,monkeypatch):
    c=publish_case;d=deepcopy(c['export'])
    if kind=='calendar':
        import plan_policy
        original=plan_policy.owner_decision
        def without_v2():
            result=original();result.pop('calendar',None);result.pop('calendar_evidence',None);result.pop('calendar_evidence_verified',None);return result
        monkeypatch.setattr(plan_policy,'owner_decision',without_v2)
    if kind=='type':
        d['dependencies'][0]['link_type']=None
        d['dependencies'][0]['type_quality']={'quality':'unsupported','value':None,'reason':'unknown_source_type'}
    elif kind=='signed_lag':d['dependencies'][0]['lag_value']['value']['units']='ELAPSED_WEEKS'
    elif kind=='calendar':d['calendars'][0]['weekdays'][0]['intervals']={'value':None,'quality':'unsupported','reason':'getter_missing'}
    elif kind=='assignment':
        donor=deepcopy(c['export']['dependencies'][0]);d['collections']['assignments'].update(status='partial',reason='getter_missing')
    elif kind=='graph_cycle':
        dep=deepcopy(d['dependencies'][0]);dep.update(dependency_key='reverse',predecessor_task_key='uid:3',successor_task_key='uid:2');d['dependencies'].append(dep);d['collections']['dependencies']['count']=2
    elif kind=='self_reference':d['dependencies'][0]['successor_task_key']='uid:2'
    elif kind=='dangling':d['dependencies'][0]['successor_task_key']='uid:999'
    else:d['dependencies'][0]['external']=True
    r=prepare(c,export=d)
    assert r.exit_code==5,r.receipt
    assert r.receipt['snapshot_id'] and r.receipt['verification']['archive']=='verified'


def test_accepted_date_deviation_never_becomes_verified():
    f=finding('date_mismatch','task_date_mismatch','uid:2:start','old','new')
    result=evaluate([f],accepted_deviations=[fingerprint(f)])
    assert result['allowed'] and result['schedule']['status']=='accepted_deviation'


def test_legacy_longest_path_excludes_root_and_never_proposes_auto_removal():
    from pipeline import gantt_critical_warning
    gantt={'eventsData':[{'id':1,'duration':100,'rollup':True,'children':[
        {'id':2,'duration':1,'children':[]},{'id':3,'duration':1,'children':[]}]}],
        'dependenciesData':[{'from':2,'to':3,'type':2,'lag':0}]}
    text=gantt_critical_warning(gantt)
    assert '2 дней' in text and 'не основание' in text and 'schedule:not_verified' in text
    assert 'исключи' not in text and 'плагин покажет' not in text
    gantt['dependenciesData'][0]['type']=0
    assert 'неприменима' in gantt_critical_warning(gantt)
