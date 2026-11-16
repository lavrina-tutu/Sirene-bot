"""Stage 09 real HTTP: isolated child targets, synthetic admitted plan and binary blocker.

The admitted source is explicitly a synthetic parsed contract, not a fabricated
MPXJ measurement. A separate unmodified binary MPP uses the real exporter and
must be archived but blocked by its extraction limitations.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit

import pytest

pytestmark=pytest.mark.confluence_live
PARENT='519501810'


def test_stage09_live_publish_bytes_storage_and_binary_blocker(tmp_path,request,stage09_export,monkeypatch):
    import conf_client,gantt_attachment
    from conf_client import ConfluenceClient
    from env import load_confluence_env
    from plan_context import PlanContext
    from pipeline import prepare_publish,publish_prepared,publish_plan
    from mofs_index.db import connect_durable
    from mofs_index.plan import query as q
    root=getattr(request.config,'_acceptance_root',tmp_path)
    folder=root/'live-stage09';folder.mkdir(exist_ok=True)
    calls=[];status={'status':'not_run','test_parent':PARENT,'scope':'stage09 admission, bytes and storage; schedule:not_verified',
        'admitted_fixture':'explicit synthetic export, no MPXJ read claimed','calls':calls}
    def trace(original):
        def call(req,*args,**kwargs):
            calls.append({'method':req.get_method(),'path':urlsplit(req.full_url).path})
            return original(req,*args,**kwargs)
        return call
    monkeypatch.setattr(conf_client,'urlopen',trace(conf_client.urlopen))
    monkeypatch.setattr(gantt_attachment,'urlopen',trace(gantt_attachment.urlopen))
    try:
        token=load_confluence_env(Path.home()/'USERTOOLS/ConfluenceSync/.env')['CONFLUENCE_TOKEN']
        client=ConfluenceClient(token=token)
        parent=client.get_page(PARENT)
        child=client.create_page('EditPlanConfluence stage 09 admission '+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'),
            parent['space']['key'],'<p>Stage 09 acceptance neighbour</p>',PARENT)
        page_id=str(child['id']);status['page_id']=page_id
        assert page_id not in ('519492935',PARENT)
        source=tmp_path/'synthetic-parsed-contract.mpp';source.write_bytes(b'Synthetic parsed fixture: no claim of binary MPP extraction')
        data=stage09_export;data['provenance'].update(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),size_bytes=source.stat().st_size)
        context=PlanContext.resolve(db=tmp_path/'state/index.sqlite',workvault=tmp_path/'WorkVault',cache_dir=tmp_path/'cache')
        before=sum(c['method'] in ('POST','PUT') for c in calls)
        prepared=prepare_publish(client,page_id,source,project_slug='stage09-live-test',timezone_hint='Europe/Moscow',
            context=context,export=data)
        assert prepared.exit_code==0,prepared.receipt
        assert sum(c['method'] in ('POST','PUT') for c in calls)==before
        result=publish_prepared(client,prepared)
        status.update(receipt=result.receipt,counters=result.counters)
        assert result.exit_code==0 and result.receipt['published'] is True,result.receipt
        assert result.receipt['verification']['schedule']['status']=='not_verified'
        observed=client.get_page(page_id)
        (folder/'storage.xml').write_text(observed['body']['storage']['value'])
        conn=connect_durable(context.db)
        stored=q.get_preparation_result(conn,result.receipt['operation_id']);artifact=q.get_artifact(conn,stored['representation_artifact_id'])
        raw=Path(artifact['path']).read_bytes();(folder/'expected.json').write_bytes(raw)
        from macro import find_macro
        macro=find_macro(observed['body']['storage']['value'])
        attachments=client.list_attachments(page_id);attachment=next(a for a in attachments if a['title']==macro.attachment_name)
        metadata=client.get_attachment(attachment['id']) # no version/status=any endpoint
        assert metadata['version']['number']==result.receipt['attachment_version']
        received=client.download_attachment(page_id,macro.attachment_name,result.receipt['attachment_version'])
        (folder/'received.json').write_bytes(received)
        assert received==raw
        status['attachment_id']=str(attachment['id']);status['received_sha256']=hashlib.sha256(received).hexdigest()
        status['page_version']=observed['version']['number'];conn.close()
        # Real binary through publish in another clean archive/cache/DB, same
        # dedicated target. Incomplete extraction must produce no HTTP writes.
        binary=tmp_path/'real-input.mpp';shutil.copy2(Path(__file__).parent/'fixtures/synthetic/relations-all-types.mpp',binary)
        other=PlanContext.resolve(db=tmp_path/'binary/state/index.sqlite',workvault=tmp_path/'binary/WorkVault',cache_dir=tmp_path/'binary/cache')
        before=len(calls)
        blocked=publish_plan(client,page_id=page_id,mpp_path=binary,project_slug='stage09-binary-test',
            timezone_hint='Europe/Moscow',context=other)
        status['binary']={'receipt':blocked.receipt,'counters':blocked.counters,'calls':calls[before:]}
        assert blocked.exit_code==5 and blocked.receipt['snapshot_id'] and blocked.receipt['verification']['archive']=='verified'
        assert blocked.counters['MPXJ_read']==1
        assert all(c['method']=='GET' for c in calls[before:])
        status['status']='passed'
    finally:
        status['POST']=sum(c['method']=='POST' for c in calls);status['PUT']=sum(c['method']=='PUT' for c in calls)
        request.config._acceptance_counters['live_POST']+=status['POST']
        request.config._acceptance_counters['live_PUT']+=status['PUT']
        (root/'reports').mkdir(exist_ok=True)
        (root/'reports/stage09-live.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
