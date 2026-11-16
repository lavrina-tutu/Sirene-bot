from __future__ import annotations

import copy
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

import pipeline
from conf_client import ConfluenceError
from mofs_index.plan import query as q
from plan_lock import target_lock, TargetLockBusy
from test_publish_prepare import prepare, _fake_raw_upload
from test_publish_resume import resume, calls, ProcessDeath

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('change', ['macro', 'summary', 'attachment', 'duplicate_macro'])
def test_foreign_managed_change_after_upload_is_conflict(publish_case, monkeypatch, change):
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    first=pipeline.publish_prepared(c['client'],prepare(c));assert first.exit_code==0
    # New preparation models a changed representation but freezes the same target.
    prepared=prepare(c)
    old_put=c['client'].put_page
    original=pipeline._verify_stage09_attachment
    def foreign(*args):
        result=original(*args)
        storage=c['client'].page['body']['storage']['value']
        if change=='macro':
            c['client'].page['body']['storage']['value']=storage.replace('ac:schema-version="1"','ac:schema-version="2"')
        elif change=='summary':
            c['client'].page['body']['storage']['value']=storage.replace('Итого:', 'Новый Итого:')
        elif change=='duplicate_macro':
            c['client'].page['body']['storage']['value']+=storage[storage.index('<p><ac:structured-macro'):]
        else:
            c['client'].uploaded.version+=1
            c['client'].blobs[(c['client'].uploaded.filename,c['client'].uploaded.version)]=b'foreign'
        return result
    monkeypatch.setattr(pipeline,'_verify_stage09_attachment',foreign)
    result=pipeline.publish_prepared(c['client'],prepared)
    assert result.exit_code == 4 and result.receipt['published'] is not True,result.receipt
    assert calls(c,'POST_ATTACHMENT')==calls(c,'PUT')==1


def test_foreign_attachment_version_after_exact_verification_blocks_put(publish_case, monkeypatch):
    c=publish_case;_fake_raw_upload(c,monkeypatch);prepared=prepare(c)
    original=pipeline._verify_stage09_attachment
    count=0
    def replace_after_read(*args):
        nonlocal count
        result=original(*args);count+=1
        if count==1:
            c['client'].uploaded.version+=1
            c['client'].blobs[(c['client'].uploaded.filename,c['client'].uploaded.version)]=b'foreign'
        return result
    monkeypatch.setattr(pipeline,'_verify_stage09_attachment',replace_after_read)
    result=pipeline.publish_prepared(c['client'],prepared)
    assert result.exit_code == 4 and calls(c,'PUT')==0,result.receipt
    assert not q.get_publish_confirmation(c['conn'],prepared.receipt['operation_id'])


@pytest.mark.parametrize('conflicts', [1,2,100])
def test_bounded_409_preserves_unmanaged_neighbours(publish_case, monkeypatch, conflicts):
    c=publish_case;_fake_raw_upload(c,monkeypatch);c['client'].conflicts=conflicts
    prepared=prepare(c);limit=int(c['context'].settings['HTTP_RETRY_LIMIT'])+1
    result=pipeline.publish_prepared(c['client'],prepared)
    if conflicts<limit:
        assert result.exit_code==0,result.receipt
        assert 'Правка соседа' in c['client'].page['body']['storage']['value']
        assert calls(c,'PUT')==conflicts+1
    else:
        assert result.exit_code==5 and result.receipt['published'] is None,result.receipt
        assert calls(c,'PUT')==limit
        again=resume(c,prepared.receipt['operation_id'])
        assert again.exit_code==5 and calls(c,'PUT')==limit,again.receipt
    assert calls(c,'POST_ATTACHMENT')==1


def test_409_changed_owned_macro_never_retries_patch(publish_case, monkeypatch):
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    def conflict(page_id,title,storage,version):
        c['client'].calls.append(('PUT',str(page_id)))
        c['client'].page['body']['storage']['value']+='<p>Итого: с 01.01.26 по 02.01.26 - 2 рабочих дней</p>'
        c['client'].page['version']['number']+=1
        raise ConfluenceError(409,'foreign managed edit')
    monkeypatch.setattr(c['client'],'put_page',conflict)
    result=pipeline.publish_prepared(c['client'],prepare(c))
    assert result.exit_code==4 and calls(c,'PUT')==1,result.receipt


def test_new_operation_same_source_cannot_overwrite_foreign_target(publish_case, monkeypatch):
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    first=pipeline.publish_prepared(c['client'],prepare(c));assert first.exit_code==0
    c['client'].page['body']['storage']['value']=c['client'].page['body']['storage']['value'].replace('Итого:', 'Чужое Итого:')
    result=pipeline.publish_prepared(c['client'],prepare(c))
    assert result.exit_code==4 and calls(c,'POST_ATTACHMENT')==calls(c,'PUT')==1,result.receipt


def test_target_live_owner_across_process_and_release_after_kill(publish_case, monkeypatch):
    c=publish_case;_fake_raw_upload(c,monkeypatch);prepared=prepare(c)
    ready=c['tmp']/'lock-ready'
    scripts=Path(pipeline.__file__).parent
    code="import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from plan_lock import target_lock\nwith target_lock(Path(sys.argv[2]),'confluence:dom.tutu.ru','test-page','other-macro'):\n Path(sys.argv[3]).touch()\n time.sleep(30)\n"
    child=subprocess.Popen([sys.executable,'-c',code,str(scripts),str(c['wv']),str(ready)],stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+10
        while not ready.exists():
            assert child.poll() is None and time.monotonic()<deadline
            time.sleep(.01)
        result=pipeline.publish_prepared(c['client'],prepared)
        assert result.exit_code==4 and result.receipt['error']['code']=='target_busy',result.receipt
        assert calls(c,'POST_ATTACHMENT')==calls(c,'PUT')==0
    finally:
        child.kill();child.wait(timeout=5)
    result=resume(c,prepared.receipt['operation_id'])
    assert result.exit_code==0,result.receipt


def test_pending_child_title_cannot_be_adopted_from_foreign_macro(publish_case, monkeypatch):
    c=publish_case;_fake_raw_upload(c,monkeypatch);prepared=prepare(c,child=True)
    original=c['client'].create_page
    def crash(*args):
        original(*args)
        raise ProcessDeath()
    monkeypatch.setattr(c['client'],'create_page',crash)
    with pytest.raises(ProcessDeath):pipeline.publish_prepared(c['client'],prepared)
    c['client'].child['body']['storage']['value']=c['client'].child['body']['storage']['value'].replace('Итого:', 'Изменено Итого:')
    monkeypatch.setattr(c['client'],'create_page',original)
    result=resume(c,prepared.receipt['operation_id'])
    assert result.exit_code==4 and calls(c,'POST_PAGE')==1 and calls(c,'POST_ATTACHMENT')==0,result.receipt
