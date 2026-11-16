"""Identity CLI and operation projection, using only typed MofsIndex mutations."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from mofs_index.db import connect_durable, initialize
from mofs_index.plan import writer as w, query as q, identity as i
from mofs_index.plan.migrate import ensure_plan_schema
from plan_identity import identity_action, load_mapping
from plan_operation import show_operation, select_identity

pytestmark=pytest.mark.archive_integration


@pytest.fixture
def case(tmp_path):
    db=tmp_path/'state/index.sqlite'; db.parent.mkdir()
    wv=tmp_path/'WorkVault'; wv.mkdir(exist_ok=True)
    cache=tmp_path/'cache'; cache.mkdir(exist_ok=True)
    c=connect_durable(db); initialize(c); ensure_plan_schema(c)
    plan=w.ensure_plan(c,'identity-test')
    lineage=w.ensure_lineage(c,plan,'local-archive-v1')
    specs=[]
    for tag in ('a','b'):
        raw=('synthetic MPP source bytes '+tag).encode(); source=tmp_path/(tag+'.mpp'); source.write_bytes(raw)
        digest=hashlib.sha256(raw).hexdigest()
        artifact=w.record_artifact(c,digest,'mpp',str(source),size_bytes=len(raw))
        specs.append(w.SnapshotSpec(plan,'mpp',lineage_id=lineage,source_artifact_id=artifact,
            normalization_profile_fingerprint='identity-test-v1',resolved_timezone='unknown',source_mpp_sha256=digest,
            tasks=(w.TaskVersionSpec('uid:1',uid='1'),w.TaskVersionSpec('uid:2',uid='2')),
            resources=(w.ResourceVersionSpec('uid:10',uid='10'),),calendars=(w.CalendarVersionSpec('cal:1'),),
            assignments=(w.AssignmentVersionSpec('uid:1','uid:10',assignment_key='uid:100',uid='100'),)))
    a=w.ingest_snapshot(c,specs[0])
    context={'paths':{'db':str(db),'workvault':str(wv),'cache_dir':str(cache)}}
    op=w.create_operation(c,w.OperationSpec('publish',json.dumps(context),plan_id=plan,lineage_id=lineage))
    item=w.create_import_item(c,w.ImportItemSpec(op,'b.mpp',str(tmp_path/'b.mpp'),plan_id=plan,lineage_id=lineage,
        source_mpp_sha256=specs[1].source_mpp_sha256,frozen_locator=str(tmp_path/'b.mpp'),frozen_at='2026-11-16T00:00:00Z'))
    attempt=w.begin_operation_attempt(c,op,item)
    b=w.commit_import_snapshot(c,item,attempt,specs[1]).snapshot_id
    req=w.register_identity_requirement(c,w.IdentityRequirementSpec(op,1,plan,a,b,'B','1',(
        i.EntityRequirement('task','uid:1'),i.EntityRequirement('task','uid:2'),i.EntityRequirement('calendar','cal:1'))))
    evidence=tmp_path/'user-statement.txt'
    fixture=Path(__file__).parent/'fixtures/synthetic/identity-confirmation/user-statement.txt'
    evidence.write_bytes(fixture.read_bytes())
    manifest=json.loads((fixture.parent/'manifest.json').read_text())
    assert hashlib.sha256(evidence.read_bytes()).hexdigest()==manifest['sha256']
    data=dict(c=c,db=db,wv=wv,cache=cache,plan=plan,a=a,b=b,op=op,req=req,item=item,evidence=evidence,root=tmp_path)
    yield data
    c.close()


def confirm(case,**options):
    return identity_action('confirm',project_slug='identity-test',from_selector='snapshot:'+case['a'],
        to_selector='snapshot:'+case['b'],mode=options.pop('mode','continuity'),evidence=case['evidence'],
        reason=options.pop('reason','Тестовое явное подтверждение пользователя'),
        db_path=case['db'],workvault=case['wv'],cache_dir=case['cache'],**options)


def mapping_file(case,pairs):
    path=case['root']/'mapping.json'
    path.write_text(json.dumps({'schema_version':1,'pairs':pairs}))
    return path


def pair(kind,key):
    return dict(entity_kind=kind,from_key=key,to_key=key,identity_key=kind+':'+key)


def preserved(case):
    c=case['c']
    return {table:[tuple(r) for r in c.execute('SELECT * FROM '+table+' ORDER BY 1')] for table in (
        'plan_operation','plan_import_item','plan_import_attempt','plan_attempt_event','plan_publication',
        'plan_baseline_selection','plan_snapshot_selection','plan_snapshot','plan_operation_mapping')}


def test_confirm_show_no_automatic_operation_start_and_evidence_copy(case,monkeypatch):
    before=preserved(case)
    def forbidden(*a,**kw):
        raise AssertionError('automatic work forbidden')
    monkeypatch.setattr('plan_save.run_export_full',forbidden)
    monkeypatch.setattr(w,'commit_import_snapshot',forbidden)
    result=confirm(case)
    assert result['status']=='confirmed' and result['exit_code']==0 and result['published'] is False
    assert result['from_snapshot_id']==case['a'] and result['to_snapshot_id']==case['b']
    assert preserved(case)==before
    case['evidence'].write_text('source evidence file changed after confirmation')
    shown=identity_action('show',project_slug='identity-test',mapping_revision=result['mapping_revision_id'],db_path=case['db'])
    assert shown['exit_code']==0 and shown['result']['status']=='active'
    artifact=q.get_artifact(case['c'],result['evidence_id'])
    assert artifact['path'] != str(case['evidence'])
    assert hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest()==result['evidence_sha256']


def test_operation_requirements_partial_then_sufficient_and_fixed_revision(case):
    show=show_operation(case['op'],db_path=case['db'],workvault=case['wv'],cache_dir=case['cache'])
    assert show['exit_code']==0 and show['preparation_revision']==1
    req=show['identity_requirements'][0]
    assert req['from_snapshot_id']==case['a'] and req['to_snapshot_id']==case['b']
    assert req['from_source_sha256'] and req['to_source_sha256'] and req['mapping_revision_id'] is None
    partial=confirm(case,mode='mapping',mapping=mapping_file(case,[pair('task','uid:1')]))
    check=select_identity(case['c'],case['op'],case['req'],partial['mapping_revision_id'])
    assert check['error']['code']=='identity_mapping_incomplete'
    show=show_operation(case['op'],db_path=case['db'])
    assert show['identity_requirements'][0]['mapping_revision_id'] is None
    full=confirm(case,mode='mapping',mapping=mapping_file(case,[pair('task','uid:1'),pair('task','uid:2'),pair('calendar','cal:1')]),
                 supersedes=partial['mapping_revision_id'])
    selected=select_identity(case['c'],case['op'],case['req'])
    assert selected['mapping_revision_id']==full['mapping_revision_id']
    repeated=select_identity(case['c'],case['op'],case['req'],full['mapping_revision_id'])
    assert repeated['exit_code']==0
    other=confirm(case,mode='mapping',mapping=mapping_file(case,[pair('task','uid:1'),pair('task','uid:2'),pair('calendar','cal:1')]),reason='another')
    with pytest.raises(i.IdentityError,match='mapping_revision_conflict'):
        select_identity(case['c'],case['op'],case['req'],other['mapping_revision_id'])
    shown=show_operation(case['op'],db_path=case['db'])['identity_requirements'][0]
    assert shown['mapping_revision_id']==full['mapping_revision_id'] and shown['evidence_id']==full['evidence_id']


@pytest.mark.parametrize('document',[
    None,[],{}, {'schema_version':True,'pairs':[]}, {'schema_version':1,'pairs':[]},
    {'schema_version':1,'pairs':[{'entity_kind':'task','from_key':'x','to_key':None,'identity_key':'x'}]},
    {'schema_version':1,'pairs':[{'entity_kind':'task','from_key':'x','to_key':'x','identity_key':'x','extra':1}]},
    {'schema_version':1,'pairs':[{'entity_kind':'dependency','from_key':'x','to_key':'x','identity_key':'x'}]},
    {'schema_version':1,'pairs':[{'entity_kind':'task','from_key':' ','to_key':'x','identity_key':'x'}]},
    {'schema_version':1,'pairs':[],'extra':1},
])
def test_strict_mapping_shape_before_mutation(case,document):
    mapping=case['root']/'invalid.json'; mapping.write_text(json.dumps(document))
    before=preserved(case)
    result=confirm(case,mode='mapping',mapping=mapping)
    assert result['exit_code']==2 and result['error']['code']=='invalid_mapping'
    assert not case['c'].execute('SELECT * FROM plan_mapping_revision').fetchall()
    assert preserved(case)==before


def test_mapping_rejects_duplicate_json_keys_and_continuity_mapping_argument(case):
    path=case['root']/'duplicate.json';path.write_text('{"schema_version":1,"schema_version":1,"pairs":[]}')
    with pytest.raises(i.IdentityError,match='invalid_mapping'):
        load_mapping(path)
    assert confirm(case,mapping=path)['exit_code']==2
    assert confirm(case,mode='mapping')['exit_code']==2


def test_schema_matches_runtime_validator(case):
    import jsonschema
    schema=json.loads((Path(__file__).parents[1]/'references/schemas/identity-mapping.schema.json').read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    valid={'schema_version':1,'pairs':[pair(kind,key) for kind,key in (('task','uid:1'),('resource','uid:10'),('calendar','cal:1'),('assignment','uid:100'))]}
    jsonschema.validate(valid,schema)
    assert len(i.validate_mapping(valid))==4
    for invalid in (None,{}, {'schema_version':1,'pairs':[]}, {'schema_version':1,'pairs':[dict(pair('task','uid:1'),to_key=None)]}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid,schema)
        with pytest.raises(i.IdentityError):
            i.validate_mapping(invalid)


def test_foreign_project_pair_and_unknown_uid_are_conflicts(case):
    c=case['c']
    other=w.ensure_plan(c,'other-project'); line=w.ensure_lineage(c,other,'test')
    foreign=w.ingest_snapshot(c,w.SnapshotSpec(other,'mpp',lineage_id=line,tasks=(w.TaskVersionSpec('uid:1',uid='1'),)))
    result=identity_action('confirm',project_slug='identity-test',from_selector='snapshot:'+case['a'],
        to_selector='snapshot:'+foreign,mode='continuity',evidence=case['evidence'],reason='explicit',db_path=case['db'],workvault=case['wv'])
    assert result['exit_code']==4 and result['error']['code']=='selector_project_mismatch'
    missing=confirm(case,mode='mapping',mapping=mapping_file(case,[pair('task','uid:missing')]))
    assert missing['exit_code']==4 and missing['error']['code']=='mapping_key_not_found'


def test_real_cli_confirm_show_errors_and_no_resume(case,pytestconfig):
    skill=Path(__file__).resolve().parents[1]
    guard=case['root']/'guard';guard.mkdir()
    (guard/'sitecustomize.py').write_text('''import socket,sqlite3,os,sys,importlib.abc
from pathlib import Path
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('conf_client','pipeline','plan_save'): raise AssertionError('work forbidden')
sys.meta_path.insert(0,Guard())
def denied(*a,**kw): raise AssertionError('network forbidden')
socket.socket.connect=denied
socket.create_connection=denied
original=sqlite3.connect
def connect(path,*a,**kw):
 if str(path) != ':memory:': assert Path(os.environ['IDENTITY_TEST_ROOT']) in Path(str(path)).resolve().parents
 return original(path,*a,**kw)
sqlite3.connect=connect
''')
    env=dict(os.environ,IDENTITY_TEST_ROOT=str(case['root']))
    env['PYTHONPATH']=str(guard)+os.pathsep+env.get('PYTHONPATH','')
    base=['/usr/bin/python3',str(skill/'scripts/cli.py'),'--db',str(case['db']),'--workvault',str(case['wv']),'--cache-dir',str(case['cache'])]
    calls=[]
    def cli(*args):
        proc=subprocess.run(base+list(args),env=env,capture_output=True,text=True,timeout=20)
        assert proc.stdout, proc.stderr
        result=json.loads(proc.stdout)
        calls.append({'command':base+list(args),'rc':proc.returncode,'result':result,'stderr':proc.stderr})
        assert result['exit_code']==proc.returncode
        return result
    before=preserved(case)
    args=('identity','confirm','--project-slug','identity-test','--from','snapshot:'+case['a'],'--to','snapshot:'+case['b'],
          '--mode','continuity','--evidence',str(case['evidence']),'--reason','TEST ONLY explicit user statement')
    first=cli(*args); assert first['exit_code']==0
    assert cli(*args)['mapping_revision_id']==first['mapping_revision_id']
    shown=cli('identity','show','--project-slug','identity-test','--mapping-revision',first['mapping_revision_id'])
    assert shown['result']['evidence_sha256']==first['evidence_sha256']
    assert cli('identity','show','--project-slug','other','--mapping-revision',first['mapping_revision_id'])['exit_code']==4
    assert cli('identity','confirm','--project-slug','identity-test')['exit_code']==2
    assert preserved(case)==before
    root=getattr(pytestconfig,'_acceptance_root',None)
    if root:
        (root/'reports/identity-cli.json').write_text(json.dumps({'calls':calls,'reader_reads':0,'POST':0,'PUT':0,
            'no_automatic_resume':True},ensure_ascii=False,indent=2))


def test_q_identity_integration_uses_same_api(case):
    result=confirm(case)
    document=(Path(__file__).parents[3]/'research/workvault-rag/references/plan-queries.md').read_text()
    code=document.split('<!-- stage07-identity-example -->')[1].split('```python',1)[1].split('```',1)[0]
    namespace=dict(conn=case['c'],plan_id=case['plan'],snap_a=case['a'],snap_b=case['b'],revision_id=result['mapping_revision_id'])
    exec(compile(code,'Q/references/plan-queries.md','exec'),namespace)
    assert namespace['proof']['mapping']=='confirmed_uid'
    assert namespace['proof']['evidence_id']==result['evidence_id']
    assert namespace['difference']['unmatched_entities']['calendar']['from']


# Reuse the existing real CLI/MPXJ harness, including its subprocess network guard.
from test_save_e2e import cli_case


def test_real_independent_mpp_same_uid_stays_unknown(cli_case,pytestconfig):
    root,run=cli_case
    fixtures=Path(__file__).parent/'fixtures/synthetic'
    manifest=json.loads((fixtures/'upstream-manifest.json').read_text())
    receipts=[]
    calls=[]
    for name in ('mpp14relations.mpp','mpp14calendar.mpp'):
        row=next(r for r in manifest['fixtures'] if r['path']==name)
        data=(fixtures/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==row['sha256']
        copy=root/name;copy.write_bytes(data)
        receipt,proc,command=run(copy)
        assert proc.returncode==0,(receipt,proc.stderr)
        receipts.append(receipt)
        calls.append({'command':command,'rc':proc.returncode,'receipt':receipt})
    assert receipts[0]['source']['sha256'] != receipts[1]['source']['sha256']
    c=connect_durable(root/'state/index.sqlite')
    try:
        a,b=(r['snapshot_id'] for r in receipts)
        plan=q.get_snapshot(c,a)['plan_id']
        ua={r[0] for r in c.execute('SELECT uid FROM plan_task_version WHERE snapshot_id=?',(a,))}
        ub={r[0] for r in c.execute('SELECT uid FROM plan_task_version WHERE snapshot_id=?',(b,))}
        common=sorted((ua&ub)-{None})
        assert common
        diff=q._diff_snapshots(c,plan,a,b)
        assert diff['receipt']['mapping']=='unknown' and not diff['changed_tasks']
        hist=q.task_history(c,plan,common[0])
        assert hist['receipt']['mapping']=='unknown' and not hist['history']
        assert len(hist['unmatched_tasks'])==2
        from test_save_e2e import _metrics
        reads=[_metrics(c,r['operation_id'])['counters']['MPXJ_read'] for r in receipts]
        assert reads==[1,1]
    finally:
        c.close()
    output=getattr(pytestconfig,'_acceptance_root',None)
    if output:
        (output/'reports/identity-real-mpp.json').write_text(json.dumps({'calls':calls,'common_uids':common,
            'mapping':'unknown','MPXJ_read':reads,'POST':0,'PUT':0},ensure_ascii=False,indent=2))
