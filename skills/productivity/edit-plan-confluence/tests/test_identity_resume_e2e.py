from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest

from mofs_index.plan import query as q, writer as w
from plan_identity import identity_action
from plan_operation import show_operation
from test_publish_prepare import prepare
from test_plan_rules import cyclic, register_rule, change_source, confirm, resume, FIXTURE

pytestmark=pytest.mark.unit


def test_bootstrap_no_save_one_arrival_then_identity_confirm_resume(publish_case):
    c=publish_case;source=cyclic(c['export'])
    reference=prepare(c,export=source).receipt['snapshot_id']
    register_rule(c,reference,source)
    new=change_source(c,source)
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot WHERE source_mpp_sha256=?',(new['provenance']['sha256'],)).fetchone()[0]==0
    start=prepare(c,export=new)
    assert start.exit_code==3,start.receipt
    operation=start.receipt['operation_id'];snapshot=start.receipt['snapshot_id']
    shown=show_operation(operation,db_path=c['db'],workvault=c['wv'],cache_dir=c['cache'])
    assert shown['snapshot_id']==snapshot and shown['identity_requirements'][0]['from_snapshot_id']==reference
    assert shown['identity_requirements'][0]['to_source_sha256']==new['provenance']['sha256']
    before=[tuple(r) for r in c['conn'].execute('SELECT * FROM plan_preparation_result')]
    identity=confirm(c,reference,snapshot)
    assert identity['exit_code']==0
    assert [tuple(r) for r in c['conn'].execute('SELECT * FROM plan_preparation_result')]==before # confirm cannot resume
    c['source'].unlink() # Resume cannot touch original input.
    result=resume(c,operation,mapping_revision=identity['mapping_revision_id'])
    assert result.exit_code==0,result.receipt
    again=resume(c,operation,mapping_revision=identity['mapping_revision_id'])
    assert again.exit_code==0 and again.receipt['snapshot_id']==snapshot
    assert c['conn'].execute('SELECT count(*) FROM plan_import_item WHERE operation_id=?',(operation,)).fetchone()[0]==1
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot WHERE source_mpp_sha256=?',(new['provenance']['sha256'],)).fetchone()[0]==1
    assert again.counters['MPXJ_read']==0 and not result.receipt['published']


def test_timezone_resume_new_preparation_and_snapshot_preserves_previous(publish_case):
    c=publish_case
    start=prepare(c,timezone_hint=None)
    assert start.exit_code==3
    operation=start.receipt['operation_id'];original=start.receipt['snapshot_id']
    old=q.get_preparation(c['conn'],operation)
    c['source'].unlink()
    result=resume(c,operation,timezone_hint='Europe/Moscow')
    assert result.exit_code==0,result.receipt
    assert result.receipt['snapshot_id']!=original
    history=q.get_preparation_history(c['conn'],operation)
    assert len(history)==2 and history[0]==old
    assert q.get_snapshot(c['conn'],original)['resolved_timezone']=='unknown'
    assert q.get_snapshot(c['conn'],history[1]['snapshot_id'])['resolved_timezone']=='Europe/Moscow'
    assert q.get_operation_item(c['conn'],operation)['snapshot_id']==original
    assert c['conn'].execute('SELECT count(*) FROM plan_import_item').fetchone()[0]==1
    denied=resume(c,operation,timezone_hint='UTC')
    assert denied.exit_code==4 and denied.receipt['error']['code']=='timezone_revision_forbidden'


def test_timezone_new_pair_never_copies_mapping_or_decision(publish_case):
    c=publish_case;d=cyclic(c['export'])
    reference=prepare(c,export=d).receipt['snapshot_id'];register_rule(c,reference,d)
    change_source(c,d)
    start=prepare(c,timezone_hint=None)
    operation=start.receipt['operation_id']
    proof=confirm(c,reference,start.receipt['snapshot_id'])
    first=resume(c,operation,mapping_revision=proof['mapping_revision_id'])
    assert first.exit_code==3 and q.get_identity_requirements(c['conn'],operation)[0]['mapping_revision_id']==proof['mapping_revision_id']
    new=resume(c,operation,timezone_hint='Europe/Moscow')
    assert new.exit_code==3,new.receipt
    requirements=q.get_identity_requirements(c['conn'],operation)
    assert len(requirements)==2
    assert requirements[0]['mapping_revision_id']==proof['mapping_revision_id']
    assert requirements[1]['mapping_revision_id'] is None and requirements[1]['preparation_revision']==2
    denied=resume(c,operation,mapping_revision=proof['mapping_revision_id'])
    assert denied.exit_code==4


@pytest.mark.parametrize('kind',['partial','ambiguous','foreign','revoked','replaced'])
def test_identity_revision_blockers(publish_case,kind):
    c=publish_case;d=cyclic(c['export'])
    reference=prepare(c,export=d).receipt['snapshot_id'];register_rule(c,reference,d)
    change_source(c,d);first=prepare(c);operation=first.receipt['operation_id'];target=first.receipt['snapshot_id']
    if kind=='partial':
        mapping=c['tmp']/'partial.json';mapping.write_text(json.dumps({'schema_version':1,'pairs':[
            {'entity_kind':'task','from_key':'uid:2','to_key':'uid:2','identity_key':'test:one'}]}))
        partial=confirm(c,reference,target,mapping=mapping)
        result=resume(c,operation,mapping_revision=partial['mapping_revision_id'])
        assert result.exit_code==3
        assert q.get_identity_requirements(c['conn'],operation)[0]['mapping_revision_id'] is None
        full=confirm(c,reference,target)
        assert resume(c,operation,mapping_revision=full['mapping_revision_id']).exit_code==0
        return
    proof=confirm(c,reference,target)
    if kind in ('revoked','replaced'):
        assert resume(c,operation,mapping_revision=proof['mapping_revision_id']).exit_code==0
    if kind=='revoked':
        w.revoke_identity_revision(c['conn'],w.IdentityRevocationSpec('test',proof['mapping_revision_id'],'Test revoke','test'))
    elif kind in ('replaced','ambiguous'):
        second=identity_action('confirm',project_slug='test',from_selector='snapshot:'+reference,to_selector='snapshot:'+target,
            mode='continuity',evidence=FIXTURE/'test-only-user-evidence.txt',reason='Second explicit test assertion',
            supersedes=proof['mapping_revision_id'] if kind=='replaced' else None,db_path=c['db'],workvault=c['wv'])
        assert second['exit_code']==0,second
    selected=None if kind=='ambiguous' else proof['mapping_revision_id']
    if kind=='foreign':
        # A different exact pair in the same project still has incompatible scope.
        change_source(c,c['export']);other=prepare(c)
        selected=confirm(c,reference,other.receipt['snapshot_id'])['mapping_revision_id']
    result=resume(c,operation,mapping_revision=selected)
    assert result.exit_code==(3 if kind=='ambiguous' else 4),result.receipt
    assert result.counters['POST']==result.counters['PUT']==0


def test_resume_forms_are_mutually_exclusive_and_apply_has_slug():
    from cli import build_parser
    p=build_parser()
    for flags in (['--mapping-revision','m','--timezone-hint','UTC'],['--accept-proposal','p','--mapping-revision','m']):
        with pytest.raises(SystemExit) as error:p.parse_args(['resume','--operation-id','o',*flags])
        assert error.value.code==2
    a=p.parse_args(['apply','--page-id','x','--mpp','x','--confirm','да','--project-slug','test'])
    assert a.project_slug=='test'


@pytest.mark.mpp_fixtures
@pytest.mark.parametrize('action',['diff','publish'])
def test_real_mpp_new_snapshot_separate_clean_environments(publish_case,request,action):
    import shutil
    from pipeline import prepare_publish,publish_plan
    c=publish_case
    fixture=Path(__file__).parent/'fixtures/synthetic/relations-all-types.mpp'
    shutil.copy2(fixture,c['source'])
    digest=hashlib.sha256(c['source'].read_bytes()).hexdigest()
    assert not c['conn'].execute('SELECT * FROM plan_snapshot').fetchall()
    call=prepare_publish if action=='diff' else publish_plan
    r=call(c['client'],page_id='test-page',mpp_path=c['source'],project_slug='test',timezone_hint='Europe/Moscow',
        context=c['context'])
    assert r.receipt['snapshot_id'] and r.receipt['verification']['archive']=='verified',r.receipt
    assert r.receipt['source']['sha256']==digest
    assert len(json.dumps(r.receipt,ensure_ascii=False).encode())<20000
    assert r.receipt['verification']['schedule']['evidence_ids']
    assert r.counters['MPXJ_read']==1 and r.counters['POST']==r.counters['PUT']==0
    assert r.exit_code==5 # Real reader's known partial extraction cannot be waived.
    c['source'].unlink()
    again=resume(c,r.receipt['operation_id'])
    assert again.receipt['snapshot_id']==r.receipt['snapshot_id'] and again.counters['MPXJ_read']==0
    assert c['conn'].execute('SELECT count(*) FROM plan_import_item').fetchone()[0]==1
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0]==1
    root=getattr(request.config,'_acceptance_root',c['tmp'])
    (root/'reports').mkdir(exist_ok=True)
    (root/'reports'/('stage09-real-'+action+'.json')).write_text(json.dumps({'action':action,'fixture':str(fixture),
        'sha256':digest,'cold':r.receipt,'counters':r.counters,'resume':again.receipt,'resume_counters':again.counters},indent=2))


def test_mapping_resume_selects_its_exact_pair_when_another_pair_is_pending(publish_case):
    c=publish_case;d=cyclic(c['export'])
    reference_b=prepare(c,export=d).receipt['snapshot_id']
    d=change_source(c,d);reference_c=prepare(c,export=d).receipt['snapshot_id']
    register_rule(c,reference_b,d,rule_id='B');register_rule(c,reference_c,d,rule_id='C')
    d=change_source(c,d);start=prepare(c,export=d);operation=start.receipt['operation_id']
    proof=confirm(c,reference_c,start.receipt['snapshot_id'])
    after=resume(c,operation,mapping_revision=proof['mapping_revision_id'])
    assert after.exit_code==3,after.receipt
    requirements=q.get_identity_requirements(c['conn'],operation)
    assert next(r for r in requirements if r['rule_id']=='C')['mapping_revision_id']==proof['mapping_revision_id']
    assert next(r for r in requirements if r['rule_id']=='B')['mapping_revision_id'] is None


@pytest.mark.mpp_fixtures
def test_real_binary_bootstrap_identity_resume_without_preliminary_save(publish_case,request):
    import shutil
    from pipeline import prepare_publish
    c=publish_case;fixtures=Path(__file__).parent/'fixtures/synthetic'
    shutil.copy2(fixtures/'mpp14relations.mpp',c['source'])
    anchor=prepare_publish(c['client'],'test-page',c['source'],project_slug='test',timezone_hint='Europe/Moscow',context=c['context'])
    assert anchor.receipt['snapshot_id'] and anchor.counters['MPXJ_read']==1,anchor.receipt
    reference=anchor.receipt['snapshot_id'];data=json.loads(q.get_snapshot(c['conn'],reference)['source_json'])
    index=next(i for i,d in enumerate(data['dependencies']) if d['link_type']=='FF')
    register_rule(c,reference,data,cause='dependency_type_unsupported',dependency_index=index)
    shutil.copy2(fixtures/'relations-all-types.mpp',c['source'])
    digest=hashlib.sha256(c['source'].read_bytes()).hexdigest()
    assert not c['conn'].execute('SELECT * FROM plan_snapshot WHERE source_mpp_sha256=?',(digest,)).fetchall()
    new=prepare_publish(c['client'],'test-page',c['source'],project_slug='test',timezone_hint='Europe/Moscow',context=c['context'])
    assert new.receipt['verification']['archive']=='verified' and new.counters['MPXJ_read']==1,new.receipt
    requirements=q.get_identity_requirements(c['conn'],new.receipt['operation_id'])
    assert len(requirements)==1 and requirements[0]['mapping_revision_id'] is None
    proof=confirm(c,reference,new.receipt['snapshot_id'])
    assert proof['exit_code']==0,proof
    c['source'].unlink()
    after=prepare_publish(c['client'],operation_id=new.receipt['operation_id'],mapping_revision=proof['mapping_revision_id'],
        db_path=c['db'],workvault=c['wv'],cache_dir=c['cache'])
    assert after.receipt['snapshot_id']==new.receipt['snapshot_id'] and after.counters['MPXJ_read']==0
    selected=q.get_identity_requirements(c['conn'],new.receipt['operation_id'])[0]
    assert selected['mapping_revision_id']==proof['mapping_revision_id']
    assert after.receipt['exceptions'][0]['result']=='not_needed',after.receipt
    assert after.exit_code==5 and after.counters['POST']==after.counters['PUT']==0 # other real extraction blockers remain
    assert c['conn'].execute('SELECT count(*) FROM plan_import_item WHERE operation_id=?',(new.receipt['operation_id'],)).fetchone()[0]==1
    root=getattr(request.config,'_acceptance_root',c['tmp']);(root/'reports').mkdir(exist_ok=True)
    (root/'reports/stage09-real-bootstrap.json').write_text(json.dumps({'reference':reference,'operation_id':new.receipt['operation_id'],
        'new_source_sha256':digest,'initial':new.receipt,'identity':proof,'resume':after.receipt,
        'new_MPXJ_read':new.counters['MPXJ_read'],'resume_MPXJ_read':after.counters['MPXJ_read'],
        'scope':'Actual binary MPP chain; test-only identity evidence; independent extraction blockers remain'},indent=2))
