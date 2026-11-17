"""Original-cause classification, exhaustive partial proof and exact mirrors."""
from copy import deepcopy
import pytest
from plan_diagnostics import completeness,policy_profile,graph_findings

pytestmark=pytest.mark.unit


def data(publish_case):return deepcopy(publish_case['export'])


def inject(d, *, influencing=False, reason='getter_failed:getLateStart:RuntimeError', mirrored=True):
    field='start' if influencing else 'late_start'
    source={'value':None,'quality':'missing','reason':reason}
    d['tasks'][1][field]=source
    if mirrored:d['tasks'][1]['quality_issues']=[{'field':field,'quality':'missing','reason':reason}]
    n=len(d['tasks'])
    d['collections']['tasks'].update(status='partial',reason='read_errors:0;items_with_field_issues:1',
        count=n,record_count=n,error_count=0)
    return field


def test_nonimpact_partial_proof_keeps_original_and_one_cause(publish_case):
    d=data(publish_case);inject(d);before=deepcopy(d)
    fs=completeness(d,policy_profile())
    own=[f for f in fs if f['entity']=='tasks.1.late_start']
    assert len(own)==1 and own[0]['category']=='nonimpact_incomplete'
    assert own[0]['provenance_paths']==['tasks.1.late_start','tasks.1.quality_issues.0']
    assert own[0]['collection_provenance'][0]['source']==d['collections']['tasks']
    assert not [f for f in fs if f['category']=='incomplete']
    assert d==before and d['collections']['tasks']['status']=='partial'


@pytest.mark.parametrize('defect',['influencing','unknown_reason','row_missing','count_missing','unknown_mirror','mirror_reason_changed','extra_cause'])
def test_partial_proof_fails_closed(publish_case,defect):
    d=data(publish_case);field=inject(d,influencing=defect=='influencing',reason='unknown_reason' if defect=='unknown_reason' else 'getter_failed:getLateStart:RuntimeError')
    if defect=='row_missing':d['collections']['tasks']['record_count']+=1
    if defect=='count_missing':del d['collections']['tasks']['record_count']
    if defect=='unknown_mirror':d['tasks'][1]['quality_issues'][0]['field']='not_a_source_field'
    if defect=='mirror_reason_changed':d['tasks'][1]['quality_issues'][0]['reason']='unknown_other'
    if defect=='extra_cause':d['tasks'][1]['constraint_date']={'value':None,'quality':'unsupported','reason':'getter_unavailable:getConstraintDate'}
    assert any(f['category']=='incomplete' for f in completeness(d,policy_profile()))


def test_adding_exact_mirror_does_not_change_classification(publish_case):
    d=data(publish_case);inject(d,mirrored=False)
    a=[(f['category'],f['code'],f['entity']) for f in completeness(d,policy_profile())]
    d['tasks'][1]['quality_issues']=[{'field':'late_start','quality':'missing','reason':'getter_failed:getLateStart:RuntimeError'}]
    assert a==[(f['category'],f['code'],f['entity']) for f in completeness(d,policy_profile())]


def test_raw_discarded_records_never_become_nonimpact(publish_case):
    d=data(publish_case);raw={'position':0,'disposition':'self_reference','predecessor_uid':2,'successor_uid':2,'raw_hex':'00'}
    d['diagnose_graph'].update(raw_relation_enumeration={'quality':'ok','value':{'expected_count':1,'observed_count':1,'records':[raw],'enumeration_complete':True},'reason':None},discarded_relation_records=[raw])
    d['collections']['dependencies'].update(status='partial',reason='raw_relations_discarded',enumeration_complete=True)
    fs=completeness(d,policy_profile())+graph_findings(d)
    assert any(f['category']=='graph' and f['code']=='raw_relation_self_reference' for f in fs)
    assert not any(f['category']=='nonimpact_incomplete' for f in fs)
    d['diagnose_graph']['raw_relation_enumeration']['value']['expected_count']=2
    assert any(f['code']=='raw_relation_completeness_unproven' for f in completeness(d,policy_profile()))


def test_policy_does_not_globally_allow_collections_assignments_or_mirrors():
    patterns=policy_profile()['nonimpact_fields']
    assert 'collections.dependencies' not in patterns
    assert 'assignments.*' not in patterns
    assert not any('quality_issues' in p for p in patterns)
