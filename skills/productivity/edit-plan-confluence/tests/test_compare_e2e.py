"""Stage 11: public CLI and typed readers share the evidence contract."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from mofs_index.db import connect_durable
from mofs_index.plan import writer as w, query as q
from mofs_index.plan.identity import MappingPair

pytestmark = pytest.mark.archive_integration
CLI = Path(__file__).resolve().parents[1]/'scripts/cli.py'


def cli(root,*args):
    proc=subprocess.run(['/usr/bin/python3',str(CLI),'--db',str(root/'state/index.sqlite'),
        '--workvault',str(root/'WorkVault'),'--cache-dir',str(root/'cache'),*args],text=True,capture_output=True,timeout=30)
    result=json.loads(proc.stdout)
    with (root/'cli-results.jsonl').open('a') as evidence:
        identity=root/'test-id.txt'
        evidence.write(json.dumps({'test_id':identity.read_text() if identity.exists() else root.name,
            'command':proc.args,'rc':proc.returncode,'result':result},ensure_ascii=False)+'\n')
    assert result['exit_code']==proc.returncode,(proc.stderr,result)
    return result


@pytest.fixture
def pair(tmp_path,request):
    (tmp_path/'test-id.txt').write_text(request.node.nodeid)
    conn=connect_durable(tmp_path/'state/index.sqlite')
    plan=w.ensure_plan(conn,'stage11')
    tasks=(w.TaskVersionSpec('t1',uid='1',name='Root',outline_level=1,finish_raw='2026-11-01T09:00:00'),
           w.TaskVersionSpec('t2',uid='2',name='Child'))
    dep=w.DependencyVersionSpec('t1','t2',link_type='FS',lag_amount='1',lag_units='DAYS',lag_elapsed=False,calendar_basis='predecessor')
    def snapshot(tag='a',**kwargs):
        params=dict(plan_id=plan,representation='mpp',source_mpp_sha256=hashlib.sha256(tag.encode()).hexdigest(),
            resolved_timezone='Europe/Moscow',tasks=tasks,dependencies=(dep,dep),
            resources=(w.ResourceVersionSpec('r1',uid='1'),w.ResourceVersionSpec('r2',uid='2')),
            calendars=(w.CalendarVersionSpec('c1',intervals=(w.CalendarIntervalSpec('weekday','MONDAY',True,'09:00','12:00'),)),),
            assignments=(w.AssignmentVersionSpec('t1','r1',assignment_key='a1',uid='1',work_amount='8'),))
        params.update(kwargs)
        return w.ingest_snapshot(conn,w.SnapshotSpec(**params))
    def confirm(a,b,partial=False,mode='mapping',reason='explicit synthetic fixture assertion'):
        path=tmp_path/'identity.txt';path.write_text('Synthetic fixture confirms this exact pair; not real user evidence')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        eid=w.record_artifact(conn,digest,'other',str(path))
        pairs=tuple(MappingPair(kind,key,key,kind+':'+key) for kind,keys in (
            ('task',('t1',) if partial else ('t1','t2')),('resource',() if partial else ('r1','r2')),
            ('calendar',() if partial else ('c1',)),('assignment',() if partial else ('a1',))) for key in keys)
        return w.register_identity_confirmation(conn,w.IdentityConfirmationSpec('stage11',a,b,mode,eid,digest,reason,'test','pytest',
            pairs=() if mode=='continuity' else pairs))['mapping_revision_id']
    yield conn,plan,snapshot,confirm
    conn.close()


def compare(tmp_path,a,b,*rest):
    return cli(tmp_path,'compare','--project-slug','stage11','--from','snapshot:'+a,'--to','snapshot:'+b,*rest)


@pytest.mark.parametrize('case',range(1,11),ids=lambda n:'AC24-'+str(n))
def test_ac24_cli(pair,tmp_path,case):
    conn,plan,snapshot,confirm=pair
    a=snapshot()
    kwargs={}
    if case==3:
        kwargs['dependencies']=(w.DependencyVersionSpec('t1','t2',link_type='SS',lag_amount='1',lag_units='DAYS',lag_elapsed=False,calendar_basis='predecessor'),)*2
    if case==4:
        kwargs['dependencies']=(w.DependencyVersionSpec('t1','t2',link_type='FS',lag_amount='-2',lag_units='HOURS',lag_elapsed=True,calendar_basis='resource'),)*2
    if case==5:
        kwargs['calendars']=(w.CalendarVersionSpec('c1',intervals=(w.CalendarIntervalSpec('exception','2026-11-01',False),)),)
    if case==6:
        kwargs['assignments']=(w.AssignmentVersionSpec('t2','r2',assignment_key='a1',uid='1',work_amount='9',units_decimal='50',finish_raw='2026-11-02T09:00'),)
    if case==7:
        foreign=w.ensure_plan(conn,'foreign')
        kwargs['plan_id']=foreign
    b=snapshot('b',**kwargs)
    if case==1:
        d=compare(tmp_path,a,b)['result']
        assert d['receipt']['mapping']=='unknown' and not d['changed_tasks'] and not d['links_removed']
        assert len(d['unmatched_entities']['task']['from'])==2
        return
    if case==7:
        for left,right in ((a,b),(b,a)):
            result=compare(tmp_path,left,right)
            assert result['exit_code']==4 and result['error']['code']=='selector_project_mismatch'
        return
    rev=confirm(a,b,partial=case==10,mode='continuity' if case==2 else 'mapping')
    args=['--mapping-revision',rev]
    if case==8:
        c=snapshot('c')
        result=compare(tmp_path,a,c,*args)
        assert result['exit_code']==4 and result['error']['code']=='mapping_revision_scope_mismatch'
        return
    if case==9:
        confirm(a,b,reason='second independent synthetic confirmation')
        result=compare(tmp_path,a,b)
        assert result['exit_code']==3 and result['error']['code']=='mapping_ambiguous'
    result=compare(tmp_path,a,b,*args)
    assert result['exit_code']==0,result
    d=result['result']
    assert d['receipt']['mapping_revision_id']==rev and d['receipt']['evidence_id']
    if case in (3,4):
        assert len(d['links_removed'])==len(d['links_added'])==2
    if case==5:assert d['changed_calendars']
    if case==6:assert d['changed_assignments']
    if case==10:
        assert len(d['unmatched_entities']['task']['from'])==1
        assert d['unmatched_entities']['calendar']['from'] and d['unmatched_entities']['assignment']['to']


def test_compare_same_source_precision_unknown_zone_and_causality(pair,tmp_path):
    conn,plan,snapshot,confirm=pair
    a=snapshot();b=snapshot('b',tasks=(w.TaskVersionSpec('t1',uid='1',name='Root',outline_level=1,finish_raw='2026-11-01T09:00:30'),w.TaskVersionSpec('t2',uid='2',name='Child')))
    confirm(a,b)
    d=compare(tmp_path,a,b)['result']
    assert d['root']['finish_delta_seconds']==30 and d['receipt']['completeness']=='partial'
    assert compare(tmp_path,a,a)['result']['receipt']['mapping']=='same_source'
    c=snapshot('c',resolved_timezone='unknown')
    confirm(a,c)
    assert compare(tmp_path,a,c)['result']['root']['finish_delta_seconds'] is None
    cause=q.explain_finish_change(conn,plan,{'kind':'snapshot','snapshot_id':a},{'kind':'snapshot','snapshot_id':b})
    assert cause['result_class']!='validated_attribution'


def test_compare_exact_publication_ids_same_v2_on_different_pages(pair,tmp_path):
    conn,plan,snapshot,confirm=pair
    raw=b'{"eventsData":[{"id":1}],"dependenciesData":[]}'
    path=tmp_path/'gantt.json';path.write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest();artifact=w.record_artifact(conn,digest,'downloaded_json',str(path))
    pubs=[]
    for page in ('test-page-1','test-page-2'):
        line=w.ensure_lineage(conn,plan,'test',page_id=page)
        pubs.append(w.record_publication(conn,w.PublicationSpec(plan,'test','att-'+page,2,lineage_id=line,artifact_id=artifact,page_id=page,filename='gantt.json',raw_sha256=digest)))
    result=cli(tmp_path,'compare','--project-slug','stage11','--from','publication:'+pubs[0],'--to','publication:'+pubs[1])
    d=result['result']
    assert result['exit_code']==0 and d['content_identical'] and d['receipt']['mapping']=='unknown'
    assert d['publications']['from']['page_id']!=d['publications']['to']['page_id']
    assert d['receipt']['publication_a']==pubs[0]
    assert cli(tmp_path,'compare','--project-slug','stage11','--from','v2','--to','publication:'+pubs[0])['exit_code']==2
    a=snapshot()
    mismatch=cli(tmp_path,'compare','--project-slug','stage11','--from','snapshot:'+a,'--to','publication:'+pubs[0])
    assert mismatch['exit_code']==4 and mismatch['result']['result_class']=='representation_mismatch'
