"""Read-only publication verification, transport guard and append-only evidence."""
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request

import pytest
from mofs_index.db import connect_durable
from mofs_index.plan import query as q,writer as w
from mofs_index.plan.history import history,HistoryRequest
from conf_client import ConfluenceClient
from macro import build_macro_html
from plan_publication_verify import verify_publication,ReadOnlyConfluenceClient

pytestmark=pytest.mark.unit


@pytest.fixture
def publication(tmp_path):
    conn=connect_durable(tmp_path/'state/index.sqlite')
    plan=w.ensure_plan(conn,'verify-stage11');line=w.ensure_lineage(conn,plan,'test',page_id='test-page')
    raw=b'{"eventsData":[{"id":1,"name":"Root"}]}'
    path=tmp_path/'expected.json';path.write_bytes(raw);digest=hashlib.sha256(raw).hexdigest()
    artifact=w.record_artifact(conn,digest,'published_json',str(path))
    snap=w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan,representation='mpp',tasks=(w.TaskVersionSpec('t1',uid='1'),)))
    pub=w.record_publication(conn,w.PublicationSpec(plan,'test','test-attachment',2,lineage_id=line,
        artifact_id=artifact,page_id='test-page',filename='gantt-chart-param.json',macro_id='macro',raw_sha256=digest))
    w.link_publication_snapshot(conn,pub,snap,confidence='confirmed',evidence='Synthetic test source link')
    storage='<p>Neighbour</p><p>Итого: с 01.11.26 по 02.11.26 - 1 рабочих дней</p>'+build_macro_html('macro','param','hash')
    obs=w.record_page_observation(conn,w.PageObservationSpec(plan,'test-page',page_version=7,itogo_raw=storage,
        storage_sha256=hashlib.sha256(storage.encode()).hexdigest()))
    w.link_publication_page(conn,pub,obs,confidence='confirmed',evidence='Synthetic saved intended storage')
    state={'page_id':'test-page','attachment_id':'test-attachment','version':2,'page_version':7,'raw':raw,
        'storage':storage,'calls':[], 'historical_missing':False}
    yield conn,pub,state
    conn.close()


def fake_get(monkeypatch,state):
    def get(req,**kwargs):
        assert req.get_method()=='GET' and req.data is None
        url=urlsplit(req.full_url);query=parse_qs(url.query)
        state['calls'].append({'method':req.get_method(),'path':url.path,'query':query})
        if '/download/attachments/' in url.path:
            return io.BytesIO(state['raw'])
        if url.path.endswith('/child/attachment'):
            body={'results':[{'id':state['attachment_id'],'title':'gantt-chart-param.json','version':{'number':state['version']}}]}
        elif url.path.endswith('/test-attachment'):
            body={'id':state['attachment_id'],'title':'gantt-chart-param.json','container':{'id':state['page_id']},'version':{'number':2}}
        else:
            if state['historical_missing'] and 'version' in query:
                from conf_client import ConfluenceError
                raise ConfluenceError(404,'historical storage unavailable')
            body={'id':state['page_id'],'version':{'number':state['page_version']},'body':{'storage':{'value':state['storage']}}}
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr('conf_client.urlopen',get)
    return ConfluenceClient(token='synthetic-test-token',base_url='https://test.invalid',retry_limit=0)


def verify(tmp_path,pub,client,scope='current_state',project_slug='verify-stage11'):
    return verify_publication(project_slug=project_slug,publication_id=pub,scope=scope,
        db_path=tmp_path/'state/index.sqlite',workvault=tmp_path/'WorkVault',cache_dir=tmp_path/'cache',client=client)


@pytest.mark.parametrize('method',['POST','PUT','PATCH','DELETE'])
def test_verify_transport_technically_forbids_writes(monkeypatch,method):
    client=ReadOnlyConfluenceClient(token='test',base_url='https://test.invalid')
    monkeypatch.setattr('conf_client.urlopen',lambda *a,**k:pytest.fail('write reached transport'))
    with pytest.raises(ValueError,match='get_only'):client._request(method,'/forbidden')
    with pytest.raises(ValueError,match='get_only'):client._read(Request('https://test.invalid',method=method))
    with pytest.raises(ValueError,match='get_only'):client._request('GET','/forbidden',data=b'body')


def test_verify_current_repeat_append_only_no_attachment_version(publication,tmp_path,monkeypatch):
    conn,pub,state=publication;client=fake_get(monkeypatch,state)
    before=q._records(conn,'SELECT * FROM plan_publication')
    one=verify(tmp_path,pub,client);two=verify(tmp_path,pub,client)
    assert one['exit_code']==two['exit_code']==0,(one,two)
    assert one['observation_id']!=two['observation_id']
    assert before==q._records(conn,'SELECT * FROM plan_publication')
    assert state['version']==2 and all(c['method']=='GET' for c in state['calls'])
    observations=q.publication_observations(conn,pub)
    assert len(observations)==3 and all(o['verification_status']=='verified_observation' for o in observations[1:])
    assert all(o['verification_scope']=='current_state' for o in observations[1:])
    assert any(c['query'].get('version')==['2'] for c in state['calls'])
    h=history(conn,HistoryRequest('verify-stage11',view='publications',time_field='recorded'))
    row=h['result']['records'][0]
    assert row['trust']=='legacy_unverified' and row['verified_at'] and len(row['observations'])==3
    snapshots=history(conn,HistoryRequest('verify-stage11',view='snapshots'))
    assert snapshots['result']['records'][0]['publications'][0]['publication_id']==pub
    assert snapshots['result']['records'][0]['published_at'] is None


def test_verify_current_does_not_restore_historical_date(publication,tmp_path,monkeypatch):
    conn,pub,state=publication;client=fake_get(monkeypatch,state)
    current=verify(tmp_path,pub,client)
    historical=verify(tmp_path,pub,client,'historical_version')
    assert current['exit_code']==0 and current['historical_publication_proven'] is False
    assert historical['exit_code']==5 and 'historical_page_version_unknown' in historical['reasons']
    assert q._load_publication(conn,q.resolve_plan(conn,'verify-stage11')['plan_id'],pub)['trust']=='legacy_unverified'
    assert q.publication_observations(conn,pub)[-1]['verification_status']=='not_verified'


@pytest.mark.parametrize('change',['bytes','storage','current_version','page_id','attachment_id'])
def test_verify_mismatch_retains_previous_observations(publication,tmp_path,monkeypatch,change):
    conn,pub,state=publication;client=fake_get(monkeypatch,state)
    assert verify(tmp_path,pub,client)['exit_code']==0
    before=q.publication_observations(conn,pub)
    if change=='bytes':state['raw']=b'foreign bytes'
    if change=='storage':state['storage']=state['storage'].replace('1 рабочих','9 рабочих')
    if change=='current_version':state['version']=3
    if change=='page_id':state['page_id']='other-page'
    if change=='attachment_id':state['attachment_id']='other-attachment'
    result=verify(tmp_path,pub,client)
    assert result['exit_code']==5 and result['status']=='not_verified'
    after=q.publication_observations(conn,pub)
    assert after[:-1]==before and len(after)==len(before)+1
    assert all(p['trust']=='legacy_unverified' for p in q.list_versions(conn,before[0]['plan_id'])['versions'] if p['kind']=='publication')


def test_verify_legacy_missing_expected_bytes_storage_or_link(publication,tmp_path,monkeypatch):
    conn,base,state=publication;client=fake_get(monkeypatch,state)
    plan=q.resolve_plan(conn,'verify-stage11')['plan_id']
    pub=w.record_publication(conn,w.PublicationSpec(plan,'legacy','missing-evidence',1,page_id='test-page',filename='gantt-chart-param.json'))
    state.update(attachment_id='missing-evidence', version=1)
    result=verify(tmp_path,pub,client)
    assert result['exit_code']==5 and result['status']=='not_verified'
    assert {'expected_bytes_unavailable','expected_storage_unavailable','confirmed_snapshot_link_required'}<=set(result['reasons'])
    assert q.publication_observations(conn,pub)[-1]['verification_status']=='not_verified'


def test_verify_wrong_project_has_zero_requests(publication,tmp_path,monkeypatch):
    conn,pub,state=publication;client=fake_get(monkeypatch,state)
    w.ensure_plan(conn,'other')
    result=verify(tmp_path,pub,client,project_slug='other')
    assert result['exit_code']==4 and result['error']['code']=='selector_project_mismatch' and not state['calls']


@pytest.mark.confluence_live
def test_verify_cli_loopback_concurrent_reads_append_observations(publication,tmp_path,request):
    import os
    import subprocess
    import threading
    from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
    conn,pub,state=publication
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            state['calls'].append({'method':'GET','path':self.path})
            path=urlsplit(self.path).path
            if '/download/attachments/' in path:
                raw=state['raw']
            elif path.endswith('/child/attachment'):
                raw=json.dumps({'results':[{'id':state['attachment_id'],'title':'gantt-chart-param.json','version':{'number':2}}]}).encode()
            elif path.endswith('/test-attachment'):
                raw=json.dumps({'id':'test-attachment','title':'gantt-chart-param.json','container':{'id':'test-page'},'version':{'number':2}}).encode()
            else:
                raw=json.dumps({'id':'test-page','version':{'number':7},'body':{'storage':{'value':state['storage']}}}).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_POST(self):
            state['calls'].append({'method':'POST'});self.send_error(405)
        do_PUT=do_POST
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    args=['/usr/bin/python3',str(Path(__file__).parents[1]/'scripts/cli.py'),'--db',str(tmp_path/'state/index.sqlite'),
        '--workvault',str(tmp_path/'WorkVault'),'--cache-dir',str(tmp_path/'cache'),'publication','verify',
        '--project-slug','verify-stage11','--publication-id',pub]
    env={**os.environ,'CONFLUENCE_URL':'http://127.0.0.1:'+str(server.server_port),'CONFLUENCE_TOKEN':'synthetic-test-token'}
    try:
        # Two real processes read the same target and append independently.
        processes=[subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env) for _ in range(2)]
        results=[]
        for proc in processes:
            out,err=proc.communicate(timeout=30);result=json.loads(out)
            assert proc.returncode==result['exit_code']==0,(result,err)
            results.append(result)
        assert len({r['observation_id'] for r in results})==2
        assert len(q.publication_observations(conn,pub))==3
        assert state['version']==2 and all(c['method']=='GET' for c in state['calls'])
        evidence={'status':'passed','processes':2,'command':args,'rc':[p.returncode for p in processes],
            'results':results,'GET':len(state['calls']),'POST':0,'PUT':0,'attachment_version':2}
        root=getattr(request.config,'_acceptance_root',tmp_path)
        (root/'reports').mkdir(exist_ok=True)
        (root/'reports/stage11-loopback.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


@pytest.mark.confluence_live
def test_stage11_live_verify_only_get_repeat_and_historical_scope(tmp_path,request,monkeypatch):
    from env import load_confluence_env
    from macro import find_macro
    from urllib.parse import urlsplit
    import conf_client
    # Immutable stage-10 evidence; this is a dedicated acceptance page, not A–D/AB.
    base=Path(__file__).parents[1]/'references/implementation/20261116/stage-10'
    saved=json.loads((base/'live-stage10/put-evidence.json').read_text())
    report=json.loads((base/'reports/stage10-live.json').read_text())
    page_id=report['page_id']
    assert page_id=='537572835' and page_id not in ('519492935','496600693','506248940')
    raw=(base/'live-stage10/expected.json').read_bytes()
    storage=(base/'live-stage10/storage.xml').read_text()
    assert hashlib.sha256(raw).hexdigest()==saved['attachment']['expected_sha256']
    assert hashlib.sha256(storage.encode()).hexdigest()==saved['storage_sha256']
    macro=find_macro(storage)
    conn=connect_durable(tmp_path/'state/index.sqlite')
    plan=w.ensure_plan(conn,'stage11-live');line=w.ensure_lineage(conn,plan,'confluence:dom.tutu.ru',page_id=page_id)
    path=tmp_path/'expected.json';path.write_bytes(raw)
    artifact=w.record_artifact(conn,hashlib.sha256(raw).hexdigest(),'published_json',str(path))
    # This is a partial Gantt snapshot of archived synthetic bytes, not an MPP proof.
    snap=w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan,representation='gantt_json',source_artifact_id=artifact,
        source_json=json.dumps(json.loads(raw)),tasks=(w.TaskVersionSpec('gantt:1',source_id='1',name='Synthetic stage-10 Gantt root'),)))
    pub=w.record_publication(conn,w.PublicationSpec(plan,'confluence:dom.tutu.ru',saved['attachment']['attachment_id'],
        saved['attachment']['attachment_version'],lineage_id=line,artifact_id=artifact,page_id=page_id,
        page_version=saved['page_version'],filename=saved['filename'],macro_id=macro.macro_id,raw_sha256=hashlib.sha256(raw).hexdigest()))
    w.link_publication_snapshot(conn,pub,snap,confidence='confirmed',evidence='stage-10 immutable put-evidence; Gantt bytes, synthetic scope')
    obs=w.record_page_observation(conn,w.PageObservationSpec(plan,page_id,page_version=saved['page_version'],itogo_raw=storage,
        storage_sha256=saved['storage_sha256']))
    w.link_publication_page(conn,pub,obs,confidence='confirmed',evidence='stage-10 archived storage/hash; not restored publication date')
    calls=[]
    original=conf_client.urlopen
    def trace(req,*args,**kwargs):
        assert req.get_method()=='GET','publication verify attempted write'
        url=urlsplit(req.full_url);calls.append({'method':req.get_method(),'path':url.path,'query':url.query})
        return original(req,*args,**kwargs)
    monkeypatch.setattr(conf_client,'urlopen',trace)
    token=load_confluence_env(Path.home()/'USERTOOLS/ConfluenceSync/.env')['CONFLUENCE_TOKEN']
    client=ConfluenceClient(token=token,retry_limit=0)
    root=getattr(request.config,'_acceptance_root',tmp_path)
    status={'status':'not_run','page_id':page_id,'source':'immutable synthetic stage-10 expected bytes/storage',
        'calls':calls,'POST':0,'PUT':0}
    try:
        before=client.get_attachment(saved['attachment']['attachment_id'])['version']['number']
        historical=verify_publication(project_slug='stage11-live',publication_id=pub,scope='historical_version',db_path=tmp_path/'state/index.sqlite',client=client)
        assert historical['exit_code']==0,historical
        current=verify_publication(project_slug='stage11-live',publication_id=pub,db_path=tmp_path/'state/index.sqlite',client=client)
        repeated=verify_publication(project_slug='stage11-live',publication_id=pub,db_path=tmp_path/'state/index.sqlite',client=client)
        # Stage 10 deliberately wrote a foreign v2 after its confirmed v1.
        assert current['exit_code']==repeated['exit_code']==5,(current,repeated)
        assert current['checks']['current_attachment'] is False
        after=client.get_attachment(saved['attachment']['attachment_id'])['version']['number']
        assert before==after and len(q.publication_observations(conn,pub))==4
        assert current['observation_id']!=repeated['observation_id'] and historical['historical_publication_proven'] is False
        status.update(status='passed',attachment_version_before=before,attachment_version_after=after,
            historical=historical,current=current,repeated=repeated,GET=len(calls))
    finally:
        (root/'reports').mkdir(exist_ok=True)
        (root/'reports/stage11-live.json').write_text(json.dumps(status,ensure_ascii=False,indent=2))
        conn.close()


def test_get_only_verification_keeps_visible_source_values_unverified(publication, tmp_path, monkeypatch):
    # The read-back transport cannot observe the rendered browser grid.
    conn, pub, state = publication
    result = verify(tmp_path, pub, fake_get(monkeypatch, state))
    assert result['source_values']['status'] == 'not_verified'
    assert result['schedule'] == 'not_verified'


@pytest.mark.parametrize('change', ['hash','page','version','wrapper','visible','model','reopen'])
def test_source_value_browser_proof_rejects_wrong_binding(change):
    from copy import deepcopy
    from prepared_plan import ROOT
    from plugin_profile import PluginProfile
    from plan_publication_verify import verify_source_value_observation
    evidence = ROOT/'references/implementation/20261116/stage-13-fix2/group-4/live/source-values'
    gantt = json.loads((evidence/'input.json').read_text())
    observation = json.loads((evidence/'observation.json').read_text())
    profile = PluginProfile.load()
    def check(o):
        return verify_source_value_observation(gantt, o, plugin_profile=profile,
            page_id=observation['page_id'], attachment_version=observation['attachment_version'])
    assert check(observation)['status'] == 'verified'
    broken = deepcopy(observation)
    if change == 'hash': broken['browser_received_sha256'] = '0'*64
    elif change == 'page': broken['page_id'] = 'other-test-page'
    elif change == 'version': broken['attachment_version'] += 1
    elif change == 'wrapper': broken['wrapper_asset_sha256'] = '0'*64
    elif change == 'visible': broken['openings'][1]['visible_values']['custom_mpp_actual_finish'] = []
    elif change == 'model': broken['openings'][1]['tasks'][0]['model']['custom_mpp_percent_complete'] = 'wrong'
    else: broken['openings'] = broken['openings'][:1]
    assert check(broken)['status'] != 'verified'
