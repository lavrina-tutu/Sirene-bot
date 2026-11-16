"""Live Confluence tests — skipped unless EDITPLAN_LIVE=1."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live


def test_live_get_test_page():
    if os.environ.get("EDITPLAN_LIVE") != "1":
        pytest.skip("live REST only with EDITPLAN_LIVE=1")
    from conf_client import ConfluenceClient

    client = ConfluenceClient()
    page = client.get_page("519501810")
    assert page["id"] == "519501810"


@pytest.mark.confluence_live
def test_stage10_live_recovery_idempotency_and_child(tmp_path, request, stage09_export, monkeypatch):
    """Real REST on newly created acceptance targets; no production A–D/AB."""
    import copy
    import hashlib
    import json
    from pathlib import Path
    from datetime import datetime, timezone
    from urllib.parse import urlsplit
    import pipeline, conf_client, gantt_attachment
    from conf_client import ConfluenceClient
    from env import load_confluence_env
    from plan_context import PlanContext
    from mofs_index.db import connect_durable
    from mofs_index.plan import query as q, writer as w
    from prepared_plan import canonical_bytes
    from plan_archive import store_artifact
    from macro import find_macro
    from test_publish_resume import ProcessDeath
    root=getattr(request.config,'_acceptance_root',tmp_path)
    folder=root/'live-stage10';folder.mkdir(exist_ok=True)
    calls=[];status={'status':'not_run','parent_id':'519501810','calls':calls,
        'source':'explicit synthetic parsed export; no binary reader measurement', 'schedule':'not_verified'}
    def trace(original):
        def invoke(req,*args,**kwargs):
            call={'method':req.get_method(),'path':urlsplit(req.full_url).path,'query':urlsplit(req.full_url).query}
            calls.append(call)
            try:
                return original(req,*args,**kwargs)
            except Exception as exc:
                call.update(exception_type=type(exc).__name__,http_status=getattr(exc,'code',None),errno=getattr(exc,'errno',None))
                raise
        return invoke
    monkeypatch.setattr(conf_client,'urlopen',trace(conf_client.urlopen))
    monkeypatch.setattr(gantt_attachment,'urlopen',trace(gantt_attachment.urlopen))
    def writes():return sum(c['method'] in ('POST','PUT') for c in calls)
    token=load_confluence_env(Path.home()/'USERTOOLS/ConfluenceSync/.env')['CONFLUENCE_TOKEN']
    client=ConfluenceClient(token=token)
    context=PlanContext.resolve(db=tmp_path/'state/index.sqlite',workvault=tmp_path/'WorkVault',cache_dir=tmp_path/'cache')
    source=tmp_path/'synthetic.mpp';source.write_bytes(b'Stage 10 synthetic parsed plan; no claim of MPP extraction')
    data=copy.deepcopy(stage09_export);data['provenance'].update(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),size_bytes=source.stat().st_size)
    conn=None
    try:
        parent=client.get_page('519501810')
        created=client.create_page('EditPlanConfluence stage 10 '+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'),
            parent['space']['key'],'<p>Stage 10 acceptance neighbour</p>','519501810')
        page_id=str(created['id']);status['page_id']=page_id
        assert page_id not in ('519501810','519492935','496600693','506248940')
        def prepare(**kwargs):
            return pipeline.prepare_publish(client,page_id,source,project_slug='stage10-live-test',timezone_hint='Europe/Moscow',
                context=context,export=data,**kwargs)
        def resume(operation):
            p=pipeline.prepare_publish(client,operation_id=operation,db_path=context.db,workvault=context.workvault,cache_dir=context.cache_dir)
            assert p.exit_code==0,p.receipt
            return pipeline.publish_prepared(client,p)
        first=prepare();assert first.exit_code==0,first.receipt
        upload=pipeline._upload_prepared_bytes
        def lose_upload(*args):
            upload(*args)
            raise ProcessDeath()
        monkeypatch.setattr(pipeline,'_upload_prepared_bytes',lose_upload)
        with pytest.raises(ProcessDeath):pipeline.publish_prepared(client,first)
        monkeypatch.setattr(pipeline,'_upload_prepared_bytes',upload)
        count=writes();published=resume(first.receipt['operation_id'])
        assert published.exit_code==0 and published.counters['POST']==0 and published.counters['PUT']==1,published.receipt
        assert writes()==count+1
        status['post_recovery']=published.receipt
        count=writes();again=pipeline.publish_prepared(client,prepare())
        assert again.exit_code==0 and again.receipt['status']=='unchanged' and writes()==count,again.receipt
        conn=connect_durable(context.db)
        assert conn.execute('SELECT count(*) FROM plan_publication').fetchone()[0]==1
        correction=prepare();stored=q.get_preparation_result(conn,correction.receipt['operation_id'])
        result=copy.deepcopy(stored['result']);result['summary']['n_days']+=1
        correction.result_id=w.record_preparation_result(conn,w.PreparationResultSpec(correction.receipt['operation_id'],
            stored['preparation_revision'],stored['representation_artifact_id'],stored['evidence_artifact_id'],stored['admission'],result))
        put=client.put_page
        def lose_put(*args):
            put(*args)
            raise ProcessDeath()
        monkeypatch.setattr(client,'put_page',lose_put)
        count=writes()
        with pytest.raises(ProcessDeath):pipeline.publish_prepared(client,correction)
        assert writes()==count+1
        monkeypatch.setattr(client,'put_page',put)
        count=writes();corrected=resume(correction.receipt['operation_id'])
        assert corrected.exit_code==0 and writes()==count,corrected.receipt
        assert conn.execute('SELECT count(*) FROM plan_publication').fetchone()[0]==1
        status['put_recovery']=corrected.receipt
        observed=client.get_page(page_id);storage=observed['body']['storage']['value']
        (folder/'storage.xml').write_text(storage)
        macro=find_macro(storage)
        attachment=next(a for a in client.list_attachments(page_id) if a['title']==macro.attachment_name)
        raw=Path(w.verify_artifact(conn,stored['representation_artifact_id'])).read_bytes()
        received=client.download_attachment_version(page_id,attachment['id'],macro.attachment_name,attachment['version']['number'])
        assert received==raw
        (folder/'expected.json').write_bytes(raw);(folder/'received.json').write_bytes(received)
        info=gantt_attachment.attachment_info(attachment)
        # A foreign identical-byte newer version still invalidates the old target.
        foreign=gantt_attachment._post_attachment_data(client,page_id,info.attach_id,info.filename,raw)
        historical=client.download_attachment_version(page_id,info.attach_id,info.filename,info.version)
        assert historical==raw and foreign.version==info.version+1
        count=writes();conflict=resume(correction.receipt['operation_id'])
        assert conflict.exit_code==4 and writes()==count,conflict.receipt
        status['foreign_version']={'before':info.version,'current':foreign.version,'conflict':conflict.receipt}
        child=prepare(child=True,title='EditPlanConfluence stage 10 child '+datetime.now(timezone.utc).strftime('%H%M%S%f'))
        assert child.exit_code==0,child.receipt
        create=client.create_page
        def lose_create(*args):
            create(*args)
            raise ProcessDeath()
        monkeypatch.setattr(client,'create_page',lose_create)
        with pytest.raises(ProcessDeath):pipeline.publish_prepared(client,child)
        monkeypatch.setattr(client,'create_page',create)
        count=writes();child_result=resume(child.receipt['operation_id'])
        assert child_result.exit_code==0 and child_result.counters['POST']==1 and child_result.counters['PUT']==0,child_result.receipt
        assert writes()==count+1
        status['child']=child_result.receipt
        for name,r in [('post',published),('put',corrected),('child',child_result)]:
            proof=q.get_publish_confirmation(conn,r.receipt['operation_id'])
            assert proof and proof['verification_profile']=='publish-v1'
            (folder/(name+'-evidence.json')).write_bytes(Path(w.verify_artifact(conn,proof['evidence_artifact_id'])).read_bytes())
        assert all(c['method']=='GET' or page_id in c['path'] or c['path']=='/rest/api/content' or child_result.receipt['page_id'] in c['path'] for c in calls)
        assert all('conflictPolicy' not in c['query'] and 'status=any' not in c['query'] for c in calls)
        status['status']='passed'
    finally:
        if conn is not None:conn.close()
        status.update(POST=sum(c['method']=='POST' for c in calls),PUT=sum(c['method']=='PUT' for c in calls),GET=sum(c['method']=='GET' for c in calls))
        request.config._acceptance_counters['live_POST']+=status['POST'];request.config._acceptance_counters['live_PUT']+=status['PUT']
        (root/'reports/stage10-live.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
