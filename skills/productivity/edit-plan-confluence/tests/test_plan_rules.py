from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import pytest

from mofs_index.plan import writer as w, query as q
from prepared_plan import fingerprint
from plan_rules import relation_signature, task_context, resolve_drop_links
from plan_identity import identity_action
from test_publish_prepare import prepare

pytestmark=pytest.mark.unit
FIXTURE=Path(__file__).parent/'fixtures/synthetic/new-source-identity-resume'


def cyclic(data):
    data=deepcopy(data)
    dep=deepcopy(data['dependencies'][0]);dep.update(dependency_key='reverse',predecessor_task_key='uid:3',successor_task_key='uid:2')
    data['dependencies'].append(dep);data['collections']['dependencies']['count']=2
    data['diagnose_graph']['cycles']=['uid:2','uid:3']
    return data


def register_rule(c,reference,data,*,cause='cycle',no_reference=False,rule_id='B',dependency_index=0):
    from plan_archive import store_artifact
    evidence,digest=store_artifact((FIXTURE/'test-only-user-evidence.txt').read_bytes(),'rule_evidence',
        ext='txt',project_slug='test',conn=c['conn'],workvault=c['wv'])
    dep=data['dependencies'][dependency_index];expected=relation_signature(dep,data['project'])
    keys=(dep['predecessor_task_key'],dep['successor_task_key']);tasks={t['task_key']:t for t in data['tasks']}
    content={'predecessor_key':keys[0],'successor_key':keys[1],'expected_relation':expected,
        'task_contexts':{k:task_context(tasks[k]) for k in keys},'action':'exclude_dependency',
        'reason':'Test-only historical B/C consent in versioned fixture','approved_at':'2026-11-16T00:00:00Z',
        'policy_revision':'publication-admission-v1','termination':'Context, relation, cause or identity proof changed',
        'cause':{'code':cause,'entity':dep['dependency_key'],'source_sha256':fingerprint(expected)}}
    w.record_project_rule(c['conn'],w.ProjectRuleSpec(rule_id,'1','test',None if no_reference else reference,
        None if no_reference else evidence,None if no_reference else digest,content))
    return content


def change_source(c,data):
    import hashlib
    c['source'].write_bytes(c['source'].read_bytes()+b' new revision')
    data=deepcopy(data);data['provenance'].update(sha256=hashlib.sha256(c['source'].read_bytes()).hexdigest(),size_bytes=c['source'].stat().st_size)
    c['export']=data
    return data


def confirm(c,reference,target,*,mapping=None):
    return identity_action('confirm',project_slug='test',from_selector='snapshot:'+reference,to_selector='snapshot:'+target,
        mode='mapping' if mapping else 'continuity',mapping=mapping,evidence=FIXTURE/'test-only-user-evidence.txt',
        reason='Explicit test-only identity assertion from fixture',db_path=c['db'],workvault=c['wv'],cache_dir=c['cache'])


def resume(c,operation_id,**kw):
    from pipeline import prepare_publish
    return prepare_publish(c['client'],operation_id=operation_id,db_path=c['db'],workvault=c['wv'],cache_dir=c['cache'],
        plugin_profile=c['profile'],**kw)


@pytest.mark.parametrize('case',['reorder','new_uid','context','relation','not_needed','missing_reference'])
def test_bc_exact_mapping_and_context(publish_case,case):
    c=publish_case;data=cyclic(c['export']) if case!='not_needed' else deepcopy(c['export'])
    anchor=prepare(c,export=data).receipt['snapshot_id']
    register_rule(c,anchor,data,cause='dependency_type_unsupported' if case=='not_needed' else 'cycle',no_reference=case=='missing_reference')
    new=change_source(c,data);mapping=None
    if case=='reorder':new['tasks'].reverse()
    elif case=='new_uid':
        for t in new['tasks']:
            if t['task_key']=='uid:2':t.update(task_key='uid:900',uid=900,id=77)
        for t in new['tasks']:
            if t['child_task_keys'].get('value'):t['child_task_keys']['value']=['uid:900' if k=='uid:2' else k for k in t['child_task_keys']['value']]
        for d in new['dependencies']:
            for key in ('predecessor_task_key','successor_task_key'):
                if d[key]=='uid:2':d[key]='uid:900'
        mapping=c['tmp']/'mapping.json'
        mapping.write_text(json.dumps({'schema_version':1,'pairs':[{'entity_kind':'task','from_key':k,'to_key':'uid:900' if k=='uid:2' else k,'identity_key':'test:'+k} for k in ('uid:1','uid:2','uid:3')]}))
    elif case=='context':new['tasks'][1]['wbs']='9.9'
    elif case=='relation':new['dependencies'][0]['lag_value']['value']['amount']='-1'
    first=prepare(c,export=new)
    assert first.exit_code in (3,5),first.receipt
    assert first.receipt['snapshot_id'] and first.receipt['verification']['archive']=='verified'
    if case=='missing_reference':
        assert first.receipt['exceptions'][0]['result']=='inactive'
        assert not q.get_identity_requirements(c['conn'],first.receipt['operation_id']);return
    selected=confirm(c,anchor,first.receipt['snapshot_id'],mapping=mapping)
    assert selected['exit_code']==0,selected
    after=resume(c,first.receipt['operation_id'],mapping_revision=selected['mapping_revision_id'])
    if case in ('context','relation'):
        assert after.exit_code==5,after.receipt # graph blocker has no applicable transformation
        assert after.receipt['exceptions'][0]['result']=='inactive'
    else:
        assert after.exit_code==0,after.receipt
        assert after.receipt['exceptions'][0]['result']==('not_needed' if case=='not_needed' else 'applied')
        assert len(after.conversion['gantt']['dependenciesData'])==1
    snapshot=q.get_snapshot(c['conn'],first.receipt['snapshot_id'])
    assert json.loads(snapshot['source_json'])['dependencies']==new['dependencies']
    assert c['conn'].execute('SELECT count(*) FROM plan_import_item').fetchone()[0]==2
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0]==2
    assert after.counters['MPXJ_read']==0


def test_drop_dep_resolves_exact_source_and_does_not_apply_without_consent(publish_case):
    c=publish_case
    from prepared_plan import PreparedPlan
    resolved=resolve_drop_links(PreparedPlan.from_export(c['export']).normalized_data,[(2,3)])
    assert resolved[0]['source_sha256']==c['export']['provenance']['sha256']
    r=prepare(c,drop_links=[(2,3)])
    assert r.exit_code==3 and len(r.conversion['gantt']['dependenciesData'])==1
    proposals=q.get_publish_proposals(c['conn'],r.receipt['operation_id'])
    assert len(proposals)==1 and proposals[0]['content']['dependency_key']=='dep:2:3'
    after=resume(c,r.receipt['operation_id'],accept_proposal=proposals[0]['proposal_id'],reason='Test: exclude exactly this relation')
    assert after.exit_code==0,after.receipt
    assert not after.conversion['gantt']['dependenciesData']
    assert len(json.loads(q.get_snapshot(c['conn'],r.receipt['snapshot_id'])['source_json'])['dependencies'])==1


def test_explicit_project_scope_persists_versioned_rule(publish_case):
    c=publish_case;r=prepare(c,drop_links=[(2,3)])
    proposal=q.get_publish_proposals(c['conn'],r.receipt['operation_id'])[0]
    after=resume(c,r.receipt['operation_id'],accept_proposal=proposal['proposal_id'],reason='Test project-scoped explicit consent',rule_scope='project')
    assert after.exit_code==0,after.receipt
    rules=q.get_project_rules(c['conn'],'test')
    assert len(rules)==1 and rules[0]['reference_snapshot_id']==r.receipt['snapshot_id']
    assert rules[0]['content']['reason']=='Test project-scoped explicit consent'
    w.verify_artifact(c['conn'],rules[0]['evidence_id'],rules[0]['evidence_sha256'])


def test_changed_hierarchy_blocks_even_when_wbs_and_uid_match(publish_case):
    c=publish_case;d=cyclic(c['export'])
    anchor=prepare(c,export=d).receipt['snapshot_id'];register_rule(c,anchor,d)
    new=change_source(c,d)
    new['tasks'][1]['parent_task_key']={'value':None,'quality':'missing','reason':'not_set'}
    start=prepare(c,export=new)
    proof=confirm(c,anchor,start.receipt['snapshot_id'])
    after=resume(c,start.receipt['operation_id'],mapping_revision=proof['mapping_revision_id'])
    assert after.exit_code==5
    assert after.receipt['exceptions'][0]['result']=='inactive'
