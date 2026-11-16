"""Stage 10 fault boundaries. Synthetic parsed source, real durable typed journal."""
from __future__ import annotations

import json
import copy
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import pipeline
from mofs_index.plan import query as q, writer as w
from test_publish_prepare import prepare, _fake_raw_upload

pytestmark = pytest.mark.unit


class ProcessDeath(BaseException):
    pass


def resume(case, operation_id, **options):
    prepared = pipeline.prepare_publish(case['client'], operation_id=operation_id,
        db_path=case['db'], workvault=case['wv'], cache_dir=case['cache'], **options)
    if prepared.exit_code:
        return prepared
    return pipeline.publish_prepared(case['client'], prepared, allow_live_ab=options.get('allow_live_ab', False))


def calls(case, name):
    return sum(call[0] == name for call in case['client'].calls)


@pytest.mark.parametrize('effect', ['upload', 'put', 'create'])
@pytest.mark.parametrize('when', ['before', 'after'])
@pytest.mark.parametrize('failure', ['crash', 'timeout'])
def test_effect_boundary_recovers_without_duplicate(publish_case, monkeypatch, effect, when, failure):
    c = publish_case; _fake_raw_upload(c, monkeypatch)
    prepared = prepare(c, child=effect == 'create')
    owner, attr = (pipeline, '_upload_prepared_bytes') if effect == 'upload' else (c['client'], 'put_page' if effect == 'put' else 'create_page')
    original = getattr(owner, attr)
    fired = False
    def interrupt(*args, **kwargs):
        nonlocal fired
        if fired:
            return original(*args, **kwargs)
        fired = True
        if when == 'after':
            original(*args, **kwargs)
        raise ProcessDeath() if failure == 'crash' else TimeoutError('controlled lost response')
    monkeypatch.setattr(owner, attr, interrupt)
    if failure == 'crash':
        with pytest.raises(ProcessDeath):
            pipeline.publish_prepared(c['client'], prepared)
    else:
        result = pipeline.publish_prepared(c['client'], prepared)
        assert result.receipt['published'] in (None, True)
        if when == 'after':
            assert result.exit_code == 0, result.receipt
        else:
            assert result.exit_code == 5, result.receipt
    monkeypatch.setattr(owner, attr, original)
    result = resume(c, prepared.receipt['operation_id'])
    assert result.exit_code == 0 and result.receipt['published'] is True, result.receipt
    assert calls(c, 'POST_ATTACHMENT') == 1
    assert calls(c, 'POST_PAGE') == (effect == 'create')
    assert calls(c, 'PUT') == (effect != 'create')
    assert c['conn'].execute('SELECT count(*) FROM plan_publication').fetchone()[0] == 1
    confirmation = q.get_publish_confirmation(c['conn'], result.receipt['operation_id'])
    assert confirmation and confirmation['verification_profile'] == 'publish-v1'


@pytest.mark.parametrize('boundary', ['intent', 'upload_observation', 'put_observation', 'confirmation', 'mirror'])
def test_journal_failure_has_no_false_success_and_resumes(publish_case, monkeypatch, boundary):
    c = publish_case; _fake_raw_upload(c, monkeypatch); prepared = prepare(c)
    original = w.record_operation_event
    def fail_event(conn, attempt, kind, **kwargs):
        detail = json.loads(kwargs.get('detail') or '{}')
        fail = (boundary == 'intent' and kind == 'publish_network_intent'
            or boundary == 'upload_observation' and kind == 'publish_observation' and detail['effect'] == 'upload'
            or boundary == 'put_observation' and kind == 'publish_observation' and detail['effect'] == 'put')
        if fail:
            raise OSError('journal unavailable')
        return original(conn, attempt, kind, **kwargs)
    monkeypatch.setattr(w, 'record_operation_event', fail_event)
    if boundary == 'confirmation':
        original_confirm = w._operation_event
        def fail_confirmation(conn, attempt, kind, *args, **kwargs):
            if kind == 'publish_network_result':
                raise OSError('transaction event failed')
            return original_confirm(conn, attempt, kind, *args, **kwargs)
        monkeypatch.setattr(w, '_operation_event', fail_confirmation)
    if boundary == 'mirror':
        original_mirror = pipeline.write_receipt
        def fail_mirror(operation, name, *args, **kwargs):
            if name == 'publish':
                raise OSError('mirror unavailable')
            return original_mirror(operation, name, *args, **kwargs)
        monkeypatch.setattr(pipeline, 'write_receipt', fail_mirror)
    result = pipeline.publish_prepared(c['client'], prepared)
    assert result.exit_code == 5 and result.receipt['published'] is not True
    if boundary == 'intent':
        assert calls(c, 'POST_ATTACHMENT') == calls(c, 'PUT') == 0
    if boundary == 'confirmation':
        for table in ('plan_publication', 'plan_page_observation', 'plan_publish_confirmation', 'plan_publication_snapshot'):
            assert c['conn'].execute('SELECT count(*) FROM ' + table).fetchone()[0] == 0
        monkeypatch.setattr(w, '_operation_event', original_confirm)
    monkeypatch.setattr(w, 'record_operation_event', original)
    if boundary == 'mirror':
        monkeypatch.setattr(pipeline, 'write_receipt', original_mirror)
    result = resume(c, prepared.receipt['operation_id'])
    assert result.exit_code == 0, result.receipt
    assert calls(c, 'POST_ATTACHMENT') == calls(c, 'PUT') == 1


@pytest.mark.parametrize('artifact', ['representation_artifact_id', 'evidence_artifact_id', 'prepared_artifact_id', 'source'])
def test_missing_or_corrupt_archive_blocks_every_effect(publish_case, monkeypatch, artifact):
    c = publish_case; _fake_raw_upload(c, monkeypatch); prepared = prepare(c)
    prep = q.get_preparation(c['conn'], prepared.receipt['operation_id'])
    result = q.get_preparation_result(c['conn'], prepared.receipt['operation_id'])
    aid = (q.get_snapshot(c['conn'], prep['snapshot_id'])['source_artifact_id'] if artifact == 'source'
           else prep[artifact] if artifact == 'prepared_artifact_id' else result[artifact])
    Path(q.get_artifact(c['conn'], aid)['path']).write_bytes(b'corrupt')
    result = pipeline.publish_prepared(c['client'], prepared)
    assert result.exit_code == 5 and result.receipt['published'] is False
    assert calls(c, 'POST_ATTACHMENT') == calls(c, 'POST_PAGE') == calls(c, 'PUT') == 0


def test_resume_rechecks_ab_flag_after_effect(publish_case, monkeypatch):
    c = publish_case; _fake_raw_upload(c, monkeypatch)
    c['client'].page['id'] = pipeline.LIVE_AB_PAGE
    prepared = prepare(c, page_id=pipeline.LIVE_AB_PAGE, allow_live_ab=True)
    original = c['client'].put_page
    monkeypatch.setattr(c['client'], 'put_page', lambda *a, **k: (_ for _ in ()).throw(ProcessDeath()))
    with pytest.raises(ProcessDeath):
        pipeline.publish_prepared(c['client'], prepared, allow_live_ab=True)
    before = len(c['client'].calls)
    denied = resume(c, prepared.receipt['operation_id'])
    assert denied.exit_code and not any(x[0].startswith(('PUT','POST')) for x in c['client'].calls[before:])
    assert denied.receipt['operation_id']==prepared.receipt['operation_id'] and denied.receipt['published'] is None
    monkeypatch.setattr(c['client'], 'put_page', original)
    assert resume(c, prepared.receipt['operation_id'], allow_live_ab=True).exit_code == 0


def test_legacy_operation_without_slug_or_binding_cannot_resume(publish_case):
    c=publish_case
    context={**c['context'].snapshot(),'publish':{'page_id':'test-page'}}
    op=w.create_operation(c['conn'],w.OperationSpec('publish',json.dumps(context)))
    w.create_import_item(c['conn'],w.ImportItemSpec(op,'legacy.mpp','gone'))
    result=resume(c,op)
    assert result.exit_code==4 and result.receipt['error']['code']=='operation_context_incomplete',result.receipt
    assert not c['client'].calls


@pytest.mark.parametrize('after_put',[False,True])
def test_unobserved_effect_does_not_authorize_foreign_summary(publish_case,monkeypatch,after_put):
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    first=pipeline.publish_prepared(c['client'],prepare(c));assert first.exit_code==0
    from test_publish_idempotency import corrected_preparation
    prepared=corrected_preparation(c)
    original=c['client'].put_page
    def crash(*args):
        if after_put:original(*args)
        raise ProcessDeath()
    monkeypatch.setattr(c['client'],'put_page',crash)
    with pytest.raises(ProcessDeath):pipeline.publish_prepared(c['client'],prepared)
    c['client'].page['body']['storage']['value']=c['client'].page['body']['storage']['value'].replace('Итого:', 'Чужое Итого:')
    monkeypatch.setattr(c['client'],'put_page',original)
    before=calls(c,'PUT');result=resume(c,prepared.receipt['operation_id'])
    assert result.exit_code==4 and calls(c,'PUT')==before,result.receipt


def test_archive_failure_after_post_retains_unknown_external_effect(publish_case,monkeypatch):
    c=publish_case;_fake_raw_upload(c,monkeypatch);prepared=prepare(c)
    monkeypatch.setattr(c['client'],'put_page',lambda *a:(_ for _ in ()).throw(ProcessDeath()))
    with pytest.raises(ProcessDeath):pipeline.publish_prepared(c['client'],prepared)
    stored=q.get_preparation_result(c['conn'],prepared.receipt['operation_id'])
    Path(w.verify_artifact(c['conn'],stored['representation_artifact_id'])).write_bytes(b'corrupt after POST')
    result=resume(c,prepared.receipt['operation_id'])
    assert result.exit_code==5 and result.receipt['published'] is None,result.receipt
    assert result.receipt['external_effect']!='none' and calls(c,'POST_ATTACHMENT')==1 and calls(c,'PUT')==0


def test_network_error_retains_safe_type_and_status(publish_case,monkeypatch):
    from conf_client import ConfluenceError
    c=publish_case;prepared=prepare(c)
    def fail(*args,**kwargs):raise ConfluenceError(404,'do not persist raw server body')
    monkeypatch.setattr(c['client'],'get_page',fail)
    result=pipeline.publish_prepared(c['client'],prepared)
    assert result.exit_code==5 and result.receipt['published'] is False
    errors=[e for e in q.get_operation_events(c['conn'],result.receipt['operation_id']) if e['event_kind']=='publish_network_error']
    assert errors[-1]['status']=='failed'
    detail=json.loads(errors[-1]['detail'])
    assert detail['http_status']==404 and detail['exception_type']=='ConfluenceError'
    assert 'do not persist' not in errors[-1]['detail']
    assert calls(c,'POST_ATTACHMENT')==calls(c,'PUT')==0


@pytest.mark.parametrize('method',['GET','POST','PUT'])
def test_transport_retries_only_get_with_configured_timeout(monkeypatch,method):
    import conf_client
    from urllib.error import HTTPError
    from io import BytesIO
    client=conf_client.ConfluenceClient(token='unit',timeout=7,retry_limit=2)
    attempts=[]
    def open(req,timeout):
        attempts.append((req.get_method(),timeout))
        raise HTTPError(req.full_url,503,'controlled',{},BytesIO(b'controlled service unavailable'))
    monkeypatch.setattr(conf_client,'urlopen',open)
    monkeypatch.setattr(conf_client.time,'sleep',lambda _:None)
    with pytest.raises(conf_client.ConfluenceError):client._request(method,'/unit')
    assert attempts==[(method,7)]*(3 if method=='GET' else 1)


def test_schedule_mismatch_after_write_is_durable_without_rollback(publish_case, monkeypatch):
    c = publish_case; _fake_raw_upload(c, monkeypatch)
    c['client'].observe_plan_schedule = lambda *a: {'status':'mismatch','task':'T','source':'installed_plugin'}
    result = pipeline.publish_prepared(c['client'], prepare(c))
    assert result.exit_code == 5 and result.receipt['published'] is None
    assert result.receipt['verification']['schedule']['status'] == 'mismatch'
    assert result.receipt['external_effect'] == 'storage_written'
    assert calls(c, 'POST_ATTACHMENT') == calls(c, 'PUT') == 1

    assert not c['conn'].execute('SELECT * FROM plan_publication').fetchall()
    del c['client'].observe_plan_schedule
    again = resume(c, result.receipt['operation_id'])
    assert again.exit_code == 5 and again.receipt['verification']['schedule']['status'] == 'mismatch'
    assert calls(c, 'POST_ATTACHMENT') == calls(c, 'PUT') == 1


@pytest.fixture
def rest_server():
    """Actual loopback HTTP, isolated from the real plugin and its evidence."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlsplit, parse_qs
    state={'page':{'id':'test-page','title':'Test','space':{'key':'TEST'},'version':{'number':3},
        'body':{'storage':{'value':'<p>Соседний блок</p>'}}},'attachment':None,'blobs':{},'calls':[]}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,value,code=200):
            raw=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(code);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            path=urlsplit(self.path).path;query=parse_qs(urlsplit(self.path).query)
            state['calls'].append(('GET',self.path))
            if path.endswith('/child/attachment'):
                return self.send({'results':[state['attachment']] if state['attachment'] else []})
            if path=='/rest/api/content/att':
                att=copy.deepcopy(state['attachment']);att['container']={'id':'test-page'}
                att['version']['number']=int(query.get('version',[att['version']['number']])[0])
                assert 'status' not in query
                return self.send(att)
            if path.startswith('/download/attachments/'):
                return self.send(state['blobs'][int(query['version'][0])])
            if path=='/rest/api/content/test-page':return self.send(state['page'])
            self.send({},404)
        def do_POST(self):
            state['calls'].append(('POST',self.path))
            body=self.rfile.read(int(self.headers['Content-Length']))
            import re
            filename=re.search(br'filename="([^"]+)"',body).group(1).decode()
            raw=body.split(b'\r\n\r\n',1)[1].rsplit(b'\r\n--',1)[0]
            version=len(state['blobs'])+1;state['blobs'][version]=raw
            state['attachment']={'id':'att','title':filename,'version':{'number':version}}
            self.send({'results':[state['attachment']]})
        def do_PUT(self):
            state['calls'].append(('PUT',self.path))
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if body['version']['number']!=state['page']['version']['number']+1:return self.send({},409)
            state['page'].update(version=body['version'],body=body['body'],title=body['title'])
            self.send({})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port),state
    finally:server.shutdown();server.server_close();thread.join(timeout=5)


@pytest.mark.confluence_live
@pytest.mark.parametrize('boundary',['before_post','after_post','before_put','after_put','after_confirmation','hold_post'])
def test_real_process_death_http_reconciliation(publish_case,rest_server,boundary,request):
    """os._exit / SIGKILL, real REST and WAL journal, no second upload/PUT."""
    c=publish_case;url,state=rest_server
    from conf_client import ConfluenceClient
    c['client']=ConfluenceClient(token='loopback-test',base_url=url)
    prepared=prepare(c);assert prepared.exit_code==0,prepared.receipt
    config=c['tmp']/'process.json';ready=c['tmp']/'ready'
    config.write_text(json.dumps({'url':url,'operation':prepared.receipt['operation_id'],
        'db':str(c['db']),'wv':str(c['wv']),'cache':str(c['cache']),'boundary':boundary,'ready':str(ready)}))
    code='''import sys,json,os,time
from pathlib import Path
sys.path[:0]=sys.argv[2:]
import pipeline
from conf_client import ConfluenceClient
from mofs_index.plan import writer as w
cfg=json.loads(Path(sys.argv[1]).read_text());client=ConfluenceClient(token='loopback-test',base_url=cfg['url'])
def wrap(owner,name,where):
 original=getattr(owner,name)
 def effect(*a,**k):
  if cfg['boundary']=='before_'+where:os._exit(73)
  result=original(*a,**k)
  if cfg['boundary']=='after_'+where:os._exit(73)
  if cfg['boundary']=='hold_'+where:
   Path(cfg['ready']).touch();time.sleep(30)
  return result
 setattr(owner,name,effect)
wrap(pipeline,'_upload_prepared_bytes','post');wrap(client,'put_page','put');wrap(w,'confirm_publish','confirmation')
prepared=pipeline.prepare_publish(client,operation_id=cfg['operation'],db_path=cfg['db'],workvault=cfg['wv'],cache_dir=cfg['cache'])
result=pipeline.publish_prepared(client,prepared)
print(json.dumps(result.receipt));sys.exit(result.exit_code)
'''
    process=subprocess.Popen([sys.executable,'-c',code,str(config),str(Path(pipeline.__file__).parent),
        '/home/tkachenkoav/USERTOOLS/MofsIndex'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    busy=None
    if boundary=='hold_post':
        try:
            deadline=time.monotonic()+15
            while not ready.exists():
                assert process.poll() is None and time.monotonic()<deadline
                time.sleep(.02)
            busy=resume(c,prepared.receipt['operation_id'])
            assert busy.exit_code==4 and busy.receipt['error']['code']=='target_busy',busy.receipt
        finally:process.kill()
    out,err=process.communicate(timeout=25)
    assert process.returncode==(-9 if boundary=='hold_post' else 73),(out,err)
    result=resume(c,prepared.receipt['operation_id'])
    assert result.exit_code==0 and result.receipt['published'] is True,result.receipt
    assert sum(call[0]=='POST' for call in state['calls'])==1
    assert sum(call[0]=='PUT' for call in state['calls'])==1
    assert c['conn'].execute('SELECT count(*) FROM plan_publication').fetchone()[0]==1
    root=getattr(request.config,'_acceptance_root',c['tmp'])
    evidence={'boundary':boundary,'child_rc':process.returncode,'calls':state['calls'],'receipt':result.receipt,
        'busy':busy.receipt if busy else None,'POST':1,'PUT':1,'GET':sum(call[0]=='GET' for call in state['calls'])}
    (root/'reports'/('stage10-process-'+boundary+'.json')).write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
