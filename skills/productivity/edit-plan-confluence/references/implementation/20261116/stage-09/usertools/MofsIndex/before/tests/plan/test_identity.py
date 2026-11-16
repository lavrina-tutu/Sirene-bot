"""Stage 07: evidence, exact scope, atomic immutable choices and safe queries."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest
from mofs_index.db import connect, initialize
from mofs_index.plan import writer as w, query as q, identity as i
from mofs_index.plan.migrate import ensure_plan_schema, _checksum
from mofs_index.plan.schema import MIGRATIONS


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path/'state.sqlite',durable=True)
    initialize(conn)
    ensure_plan_schema(conn)
    yield conn
    conn.close()


def make_snapshot(conn, *, slug='identity-test', tag='a', uid='1', task_key='uid:1',
                  profile='normalization-v1', representation='mpp', tasks=None, timezone='Europe/Moscow',
                  lineage=None, source=None):
    plan=w.ensure_plan(conn,slug)
    lineage=lineage or w.ensure_lineage(conn,plan,'test')
    raw=b'same bytes' if source else tag.encode()
    digest=hashlib.sha256(raw).hexdigest()
    path=Path(conn.execute('PRAGMA database_list').fetchone()[2]).parent/(digest+'.mpp')
    path.write_bytes(raw)
    artifact=w.record_artifact(conn,digest,'mpp',str(path),size_bytes=len(raw))
    return w.ingest_snapshot(conn,w.SnapshotSpec(plan,representation,lineage_id=lineage,source_artifact_id=artifact,
        source_mpp_sha256=source or hashlib.sha256(tag.encode()).hexdigest(),
        normalization_profile_fingerprint=profile,resolved_timezone=w.normalize_timezone(timezone),
        tasks=tasks or (w.TaskVersionSpec(task_key,uid=uid,name='Task '+tag,finish_raw='2026-01-01',outline_level=1),
                        w.TaskVersionSpec('uid:2',uid='2')),
        resources=(w.ResourceVersionSpec('uid:10',uid='10'),),
        calendars=(w.CalendarVersionSpec('cal:1'),),
        assignments=(w.AssignmentVersionSpec(task_key,'uid:10',assignment_key='uid:100',uid='100'),)))


def confirmation(conn,tmp_path,a,b,*,pairs=(),mode='continuity',reason='Пользователь явно подтвердил продолжение',supersedes=None):
    data=b'TEST ONLY: explicit user statement; second snapshot continues first UID namespace.'
    digest=hashlib.sha256(data).hexdigest()
    path=tmp_path/(digest+'.evidence')
    path.write_bytes(data)
    artifact=w.record_artifact(conn,digest,'identity_evidence',str(path),size_bytes=len(data))
    return w.IdentityConfirmationSpec('identity-test',a,b,mode,artifact,digest,reason,'test-user','test-explicit',pairs=pairs,supersedes=supersedes)


def revision(conn,tmp_path,a,b,**kwargs):
    return w.register_identity_confirmation(conn,confirmation(conn,tmp_path,a,b,**kwargs))


def operation_requirement(conn,a,b,required=None):
    snap=q.get_snapshot(conn,b)
    plan=snap['plan_id']
    op=w.create_operation(conn,w.OperationSpec('publish',plan_id=plan))
    artifact=q.get_artifact(conn,snap['source_artifact_id'])
    item=w.create_import_item(conn,w.ImportItemSpec(op,'test.mpp',artifact['path'],plan_id=plan,
        source_mpp_sha256=snap['source_mpp_sha256'],frozen_locator=artifact['path']))
    attempt=w.begin_operation_attempt(conn,op,item)
    w.commit_import_snapshot(conn,item,attempt,w.SnapshotSpec(plan,snap['representation'],lineage_id=snap['lineage_id'],
        source_artifact_id=snap['source_artifact_id'],source_mpp_sha256=snap['source_mpp_sha256'],
        normalization_profile_fingerprint=snap['normalization_profile_fingerprint'],resolved_timezone=snap['resolved_timezone'],snapshot_id=b))
    required=required or (i.EntityRequirement('task','uid:1'),i.EntityRequirement('task','uid:2'))
    spec=w.IdentityRequirementSpec(op,1,plan,a,b,'B','1',required)
    rid=w.register_identity_requirement(conn,spec)
    return op,rid,spec


def test_unknown_independent_same_uids_no_query_escalation(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='independent')
    plan=q.get_snapshot(db,a)['plan_id']
    proof=i.resolve_identity(db,plan,a,b)
    assert proof['mapping']=='unknown'
    diff=q.diff_versions(db,plan,{'kind':'snapshot','snapshot_id':a},{'kind':'snapshot','snapshot_id':b})
    assert diff['receipt']['mapping']=='unknown' and not diff['changed_tasks']
    assert not diff['task_uids_added'] and not diff['task_uids_removed']
    assert len(diff['unmatched_entities']['task']['from'])==2
    hist=q.task_history(db,plan,'1')
    assert hist['receipt']['mapping']=='unknown' and not hist['history']
    assert len(hist['unmatched_tasks'])==2 and hist['finish_delta_calendar_days'] is None
    assert q.explain_finish_change(db,plan,{'kind':'snapshot','snapshot_id':a},{'kind':'snapshot','snapshot_id':b})['result_class']=='insufficient_data'


def test_continuity_mapping_evidence_and_direct_history(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    rev=revision(db,tmp_path,a,b)
    plan=q.get_snapshot(db,a)['plan_id']
    assert rev['status']=='active' and rev['basis']=='continuity'
    assert len(rev['pairs'])==4 # 2 tasks, resource, assignment; no guessed calendar
    spec=confirmation(db,tmp_path,a,b)
    assert w.register_identity_confirmation(db,spec)['mapping_revision_id']==rev['mapping_revision_id']
    diff=q.diff_versions(db,plan,{'kind':'snapshot','snapshot_id':a},{'kind':'snapshot','snapshot_id':b})
    assert diff['receipt']['mapping']=='confirmed_uid'
    assert diff['receipt']['mapping_revision_id']==rev['mapping_revision_id'] and diff['receipt']['evidence_id']==rev['evidence_id']
    hist=q.task_history(db,plan,'1',from_snapshot_id=a,to_snapshot_id=b,mapping_revision_id=rev['mapping_revision_id'])
    assert len(hist['history'])==2 and hist['receipt']['mapping_revision_id']==rev['mapping_revision_id']
    c=make_snapshot(db,tag='c')
    revision(db,tmp_path,b,c)
    assert i.resolve_identity(db,plan,a,c)['mapping']=='unknown' # no transitivity
    assert len(q.task_history(db,plan,'1',from_snapshot_id=a)['history'])==2


@pytest.mark.parametrize('uid', ['-1','bad','01','',None,'2'])
def test_invalid_and_duplicate_uid_reject_continuity(db,tmp_path,uid):
    a=make_snapshot(db)
    b=make_snapshot(db,tag='b',uid=uid)
    with pytest.raises(i.IdentityError,match='invalid_or_duplicate_uid'):
        revision(db,tmp_path,a,b)
    assert db.execute('SELECT count(*) FROM plan_mapping_revision').fetchone()[0]==0


def test_duplicate_uid_can_only_use_explicit_unique_local_keys(db,tmp_path):
    a=make_snapshot(db)
    b=make_snapshot(db,tag='b',uid='2')
    pairs=(i.MappingPair('task','uid:1','uid:1','root'),)
    rev=revision(db,tmp_path,a,b,mode='mapping',pairs=pairs)
    assert rev['pairs'][0]['to_key']=='uid:1'
    diff=q._diff_snapshots(db,rev['plan_id'],a,b)
    assert diff['receipt']['mapping']=='confirmed_mapping'
    assert len(diff['unmatched_entities']['task']['to'])==1


def test_mapping_four_kinds_and_changed_uid(db,tmp_path):
    a=make_snapshot(db)
    b=make_snapshot(db,tag='b',uid='900',task_key='uid:900')
    pairs=tuple(i.MappingPair(kind,left,right,kind+':identity') for kind,left,right in (
        ('task','uid:1','uid:900'),('resource','uid:10','uid:10'),('calendar','cal:1','cal:1'),('assignment','uid:100','uid:100')))
    rev=revision(db,tmp_path,a,b,mode='mapping',pairs=pairs)
    assert len(rev['pairs'])==4
    hist=q.task_history(db,rev['plan_id'],'1',from_snapshot_id=a,to_snapshot_id=b,mapping_revision_id=rev['mapping_revision_id'])
    assert hist['history'][1]['task_key']=='uid:900'


@pytest.mark.parametrize('bad_pairs,code',[
    ((i.MappingPair('bogus','uid:1','uid:1','x'),),'invalid_mapping'),
    ((i.MappingPair('task','no','uid:1','x'),),'mapping_key_not_found'),
    ((i.MappingPair('task','uid:1','uid:1','x'),i.MappingPair('task','uid:1','uid:2','y')),'mapping_not_one_to_one'),
    ((i.MappingPair('task','uid:1','uid:1','x'),i.MappingPair('task','uid:2','uid:1','y')),'mapping_not_one_to_one'),
    ((i.MappingPair('task','uid:1','uid:1','x'),i.MappingPair('task','uid:2','uid:2','x')),'mapping_not_one_to_one'),
    ((i.MappingPair('resource','cal:1','uid:10','x'),),'mapping_key_not_found'),
])
def test_mapping_invalid_keys_and_bijection(db,tmp_path,bad_pairs,code):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    with pytest.raises(i.IdentityError,match=code):
        revision(db,tmp_path,a,b,mode='mapping',pairs=bad_pairs)


def test_pair_project_representation_scope_and_no_transitivity(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    rev=revision(db,tmp_path,a,b)
    foreign=make_snapshot(db,slug='foreign',tag='f')
    c=make_snapshot(db,tag='c')
    gantt=make_snapshot(db,tag='g',representation='gantt_json')
    for left,right,code in ((a,foreign,'selector_project_mismatch'),(a,gantt,'continuity_requires_mpp')):
        with pytest.raises(i.IdentityError,match=code):
            revision(db,tmp_path,left,right)
    for left,right in ((a,c),(b,a)):
        with pytest.raises(i.IdentityError,match='mapping_revision_scope_mismatch'):
            i.resolve_identity(db,rev['plan_id'],left,right,rev['mapping_revision_id'])
    with pytest.raises(i.IdentityError,match='mapping_revision_scope_mismatch'):
        i.show_revision(db,'foreign',rev['mapping_revision_id'])
    with pytest.raises(i.IdentityError,match='selector_project_mismatch'):
        q._diff_snapshots(db,rev['plan_id'],a,foreign)


def test_multiple_revision_explicit_and_conflicting_confirmations(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    r1=revision(db,tmp_path,a,b)
    r2=revision(db,tmp_path,a,b,reason='Другое явное свидетельство')
    with pytest.raises(i.IdentityError,match='mapping_ambiguous') as error:
        i.resolve_identity(db,r1['plan_id'],a,b)
    assert error.value.exit_code==3
    assert i.resolve_identity(db,r1['plan_id'],a,b,r1['mapping_revision_id'])['mapping_revision_id']==r1['mapping_revision_id']
    with pytest.raises(i.IdentityError,match='identity_confirmation_conflict'):
        revision(db,tmp_path,a,b,mode='mapping',pairs=(i.MappingPair('task','uid:1','uid:2','different'),))
    assert r1['mapping_revision_id'] != r2['mapping_revision_id']


def test_partial_then_sufficient_mapping_preserves_free_choice(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,_=operation_requirement(db,a,b,(
        i.EntityRequirement('task','uid:1'),i.EntityRequirement('task','uid:2'),i.EntityRequirement('calendar','cal:1')))
    r1=revision(db,tmp_path,a,b,mode='mapping',pairs=(i.MappingPair('task','uid:1','uid:1','root'),))
    selected=w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid))
    assert selected['error']['code']=='identity_mapping_incomplete'
    assert db.execute('SELECT count(*) FROM plan_operation_mapping').fetchone()[0]==0
    pairs=tuple(i.MappingPair(kind,key,key,kind+':'+key) for kind,key in (('task','uid:1'),('task','uid:2'),('calendar','cal:1')))
    r2=revision(db,tmp_path,a,b,mode='mapping',pairs=pairs,supersedes=r1['mapping_revision_id'])
    selected=w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid))
    assert selected['mapping_revision_id']==r2['mapping_revision_id']
    assert w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,r2['mapping_revision_id']))['exit_code']==0
    checks=i.operation_requirements(db,op)[0]['checks']
    assert checks[0]['result']=='identity_mapping_incomplete' and checks[-1]['result']=='sufficient'


def test_fixed_selection_idempotent_no_replacement_revoked_blocks(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,_=operation_requirement(db,a,b)
    assert w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid))['error']['code']=='identity_confirmation_required'
    r1=revision(db,tmp_path,a,b)
    w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,r1['mapping_revision_id']))
    r2=revision(db,tmp_path,a,b,reason='Another explicit statement')
    assert w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid))['mapping_revision_id']==r1['mapping_revision_id']
    with pytest.raises(i.IdentityError,match='mapping_revision_conflict') as error:
        w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,r2['mapping_revision_id']))
    assert error.value.exit_code==4
    revoke=w.IdentityRevocationSpec('identity-test',r1['mapping_revision_id'],'Пользователь отозвал','test-user')
    event=w.revoke_identity_revision(db,revoke)
    assert w.revoke_identity_revision(db,revoke)==event
    with pytest.raises(i.IdentityError,match='mapping_revision_inactive'):
        w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid))
    assert i.resolve_identity(db,r1['plan_id'],a,b)['mapping_revision_id']==r2['mapping_revision_id']


def test_supersedes_preserves_history_and_blocks_fixed_choice(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,_=operation_requirement(db,a,b)
    r1=revision(db,tmp_path,a,b)
    w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,r1['mapping_revision_id']))
    r2=revision(db,tmp_path,a,b,supersedes=r1['mapping_revision_id'])
    assert i.show_revision(db,'identity-test',r1['mapping_revision_id'])['status']=='superseded'
    assert i.resolve_identity(db,r1['plan_id'],a,b)['mapping_revision_id']==r2['mapping_revision_id']
    with pytest.raises(i.IdentityError,match='mapping_revision_inactive'):
        w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid))
    assert i.operation_requirements(db,op)[0]['mapping_revision_id']==r1['mapping_revision_id']


def test_requirement_scope_immutable_and_both_rule_tasks(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,spec=operation_requirement(db,a,b)
    assert w.register_identity_requirement(db,spec)==rid
    with pytest.raises(i.IdentityError,match='identity_requirement_conflict'):
        w.register_identity_requirement(db,replace(spec,required_entities=spec.required_entities+(i.EntityRequirement('calendar','cal:1'),)))
    with pytest.raises(i.IdentityError,match='both_rule_tasks_required'):
        w.register_identity_requirement(db,replace(spec,rule_revision='2',required_entities=spec.required_entities[:1]))
    with pytest.raises(i.IdentityError,match='operation_identity_scope_mismatch'):
        w.register_identity_requirement(db,replace(spec,preparation_revision=2))


def test_append_only_evidence_and_tampering_fails_closed(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    r=revision(db,tmp_path,a,b)
    before=json.dumps(i.show_revision(db,'identity-test',r['mapping_revision_id']),sort_keys=True)
    for table in ('plan_mapping_revision','plan_identity_mapping','plan_artifact'):
        for action in ('UPDATE','DELETE'):
            sql=f'UPDATE {table} SET '+('reason=reason' if table=='plan_mapping_revision' else 'local_key=local_key' if table=='plan_identity_mapping' else 'path=path') if action=='UPDATE' else f'DELETE FROM {table}'
            with pytest.raises(sqlite3.IntegrityError,match='append_only'):
                db.execute(sql)
            db.rollback()
    assert json.dumps(i.show_revision(db,'identity-test',r['mapping_revision_id']),sort_keys=True)==before
    path=db.execute('SELECT path FROM plan_artifact WHERE artifact_id=?',(r['evidence_id'],)).fetchone()[0]
    Path(path).write_bytes(b'changed bytes')
    with pytest.raises(i.IdentityError,match='identity_evidence_unavailable'):
        i.resolve_identity(db,r['plan_id'],a,b)


@pytest.mark.parametrize('profile,timezone,representation,expected',[
    ('normalization-v1','Europe/Moscow','mpp','same_source'),
    ('normalization-v2','Europe/Moscow','mpp','unknown'),
    ('normalization-v1','UTC','mpp','unknown'),
    ('normalization-v1','Europe/Moscow','gantt_json','unknown'),
    (None,'Europe/Moscow','mpp','unknown')])
def test_same_source_only_same_profile_and_scope(db,profile,timezone,representation,expected):
    source=hashlib.sha256(b'same bytes').hexdigest()
    a=make_snapshot(db,source=source)
    plan=q.get_snapshot(db,a)['plan_id']
    line=w.ensure_lineage(db,plan,'separate')
    b=make_snapshot(db,tag='b',source=source,profile=profile,timezone=timezone,representation=representation,lineage=line)
    assert i.resolve_identity(db,plan,a,b)['mapping']==expected
    assert i.resolve_identity(db,plan,a,a)['mapping']=='same_source'


def test_migration_0001_0009_unchanged_and_legacy_mapping_preserved(tmp_path):
    # Compare migration definitions to the approved external snapshot from stage 06.
    approved=Path('/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/references/implementation/20261116/stage-06/usertools/MofsIndex/after/mofs_index/plan/schema.py')
    current=Path(__file__).resolve().parents[2]/'mofs_index/plan/schema.py'
    assert approved.read_text().split('\ndef all_plan_table_names')[0].rstrip() == current.read_text().split('\n# Stage 07: legacy unscoped')[0].rstrip()
    conn=connect(tmp_path/'old.sqlite',durable=True)
    initialize(conn)
    from mofs_index.plan import migrate
    original=migrate.MIGRATIONS
    try:
        migrate.MIGRATIONS=original[:9]
        ensure_plan_schema(conn)
        plan=w.ensure_plan(conn,'legacy')
        conn.execute('INSERT INTO plan_mapping_revision VALUES (?,?,?,?)',('old',plan,'historical','2026-01-01'))
        for number in (1,2):
            conn.execute('INSERT INTO plan_identity_mapping VALUES (?,?,?,?,?,?,?,?)',
                         (str(number),'old','task',str(number),'shared','confirmed','legacy','2026-01-01'))
        conn.commit()
    finally:
        migrate.MIGRATIONS=original
    assert ensure_plan_schema(conn)==['0010_identity_revisions']
    assert ensure_plan_schema(conn)==[]
    assert conn.execute('SELECT count(*) FROM plan_identity_mapping').fetchone()[0]==2
    assert not conn.execute('PRAGMA foreign_key_check').fetchall()
    assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    with pytest.raises(i.IdentityError,match='mapping_revision_unconfirmed'):
        i.show_revision(conn,'legacy','old')
    conn.close()


def test_atomic_choice_rolls_back_if_check_insert_fails(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,_=operation_requirement(db,a,b)
    r=revision(db,tmp_path,a,b)
    db.execute("CREATE TRIGGER fail_choice BEFORE INSERT ON plan_operation_mapping BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(sqlite3.IntegrityError,match='injected'):
        w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,r['mapping_revision_id']))
    assert not db.execute('SELECT * FROM plan_identity_check').fetchall()
    assert not db.execute('SELECT * FROM plan_operation_mapping').fetchall()


def test_two_processes_choose_one_revision_atomically(db,tmp_path):
    import subprocess,sys
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,_=operation_requirement(db,a,b)
    r1=revision(db,tmp_path,a,b)
    r2=revision(db,tmp_path,a,b,reason='second explicit statement')
    code='''import sys,json
from mofs_index.db import connect_durable
from mofs_index.plan import writer as w,identity as i
c=connect_durable(sys.argv[1])
try:
 result=w.select_operation_identity(c,w.IdentityChoiceSpec(*sys.argv[2:]))
 print(json.dumps({'exit_code':0,'revision':result['mapping_revision_id']}))
except i.IdentityError as exc:
 print(json.dumps({'exit_code':exc.exit_code,'code':exc.code}))
finally: c.close()
'''
    path=db.execute('PRAGMA database_list').fetchone()[2]
    processes=[subprocess.Popen([sys.executable,'-c',code,path,op,rid,r['mapping_revision_id']],
                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for r in (r1,r2)]
    results=[]
    for process in processes:
        out,err=process.communicate(timeout=20)
        assert process.returncode==0,err
        results.append(json.loads(out))
    assert sorted(r['exit_code'] for r in results)==[0,4]
    assert next(r for r in results if r['exit_code']==4)['code']=='mapping_revision_conflict'
    assert db.execute('SELECT count(*) FROM plan_operation_mapping').fetchone()[0]==1


def test_pair_choice_shared_across_rules_and_all_selection_rows_immutable(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,spec=operation_requirement(db,a,b)
    r1=revision(db,tmp_path,a,b)
    r2=revision(db,tmp_path,a,b,reason='second explicit statement')
    w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,r1['mapping_revision_id']))
    other=w.register_identity_requirement(db,replace(spec,rule_id='C'))
    with pytest.raises(i.IdentityError,match='mapping_revision_conflict'):
        w.select_operation_identity(db,w.IdentityChoiceSpec(op,other,r2['mapping_revision_id']))
    assert w.select_operation_identity(db,w.IdentityChoiceSpec(op,other))['mapping_revision_id']==r1['mapping_revision_id']
    w.revoke_identity_revision(db,w.IdentityRevocationSpec('identity-test',r1['mapping_revision_id'],'revoke','test'))
    for table in ('plan_identity_requirement','plan_operation_mapping','plan_identity_check','plan_mapping_event'):
        assert db.execute('SELECT count(*) FROM '+table).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError,match='append_only'):
            db.execute('DELETE FROM '+table)
        db.rollback()


def test_reverse_conflict_does_not_create_implicit_reverse_identity(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    rev=revision(db,tmp_path,a,b)
    assert i.resolve_identity(db,rev['plan_id'],b,a)['mapping']=='unknown'
    with pytest.raises(i.IdentityError,match='identity_confirmation_conflict'):
        revision(db,tmp_path,b,a,mode='mapping',pairs=(i.MappingPair('task','uid:1','uid:2','other'),))


def test_partial_then_new_explicit_sufficient_without_supersedes(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,_=operation_requirement(db,a,b)
    partial=revision(db,tmp_path,a,b,mode='mapping',pairs=(i.MappingPair('task','uid:1','uid:1','one'),))
    assert w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,partial['mapping_revision_id']))['exit_code']==3
    complete=revision(db,tmp_path,a,b)
    with pytest.raises(i.IdentityError,match='mapping_ambiguous'):
        w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid))
    assert w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,complete['mapping_revision_id']))['exit_code']==0


def test_choice_checks_all_rules_for_pair_before_claiming_slot(db,tmp_path):
    a,b=make_snapshot(db),make_snapshot(db,tag='b')
    op,rid,spec=operation_requirement(db,a,b)
    other=w.register_identity_requirement(db,replace(spec,rule_id='C',required_entities=spec.required_entities+(i.EntityRequirement('calendar','cal:1'),)))
    rev=revision(db,tmp_path,a,b)
    result=w.select_operation_identity(db,w.IdentityChoiceSpec(op,rid,rev['mapping_revision_id']))
    assert result['error']['code']=='identity_mapping_incomplete'
    assert any(r['entity_kind']=='calendar' for r in result['missing'])
    assert not db.execute('SELECT * FROM plan_operation_mapping').fetchall()
