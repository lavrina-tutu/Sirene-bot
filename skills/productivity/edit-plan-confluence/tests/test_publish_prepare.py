from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from pipeline import prepare_publish, publish_plan
from mofs_index.plan import writer as w, query as q
from plan_receipt import validate_single_receipt

pytestmark=pytest.mark.unit


def prepare(case,**options):
    return prepare_publish(case['client'],options.pop('page_id','test-page'),case['source'],
        project_slug=options.pop('project_slug','test'),timezone_hint=options.pop('timezone_hint','Europe/Moscow'),
        context=case['context'],export=options.pop('export',case['export']),
        plugin_profile=options.pop('plugin_profile',case['profile']),**options)


def test_first_diff_snapshot_before_admission(publish_case):
    c=publish_case
    assert not c['conn'].execute('SELECT * FROM plan_snapshot').fetchall()
    result=prepare(c)
    assert result.exit_code==0,result.receipt
    r=result.receipt;validate_single_receipt(r)
    assert r['snapshot_id'] and r['verification']['archive']=='verified' and r['published'] is False
    assert r['external_effect']=='none' and 'admitted' in r['completed_stages']
    assert not any(call[0].startswith(('POST','PUT')) for call in c['client'].calls)
    prep=q.get_preparation(c['conn'],r['operation_id']);latest=q.get_preparation_result(c['conn'],r['operation_id'])
    assert prep['snapshot_id']==r['snapshot_id'] and latest['state']=='admitted'
    for aid in ('representation_artifact_id','evidence_artifact_id'):w.verify_artifact(c['conn'],latest[aid])


def test_new_binding_without_slug_retains_input_no_resumable_id(publish_case):
    c=publish_case;result=prepare(c,project_slug=None)
    assert result.exit_code==2 and result.receipt['error']['code']=='project_slug_required'
    assert result.receipt['operation_id'] is None and result.receipt['snapshot_id'] is None
    assert not c['conn'].execute('SELECT * FROM plan_snapshot').fetchall()
    item=dict(c['conn'].execute('SELECT * FROM plan_import_item').fetchone())
    assert Path(item['frozen_locator']).is_file()


def test_unknown_timezone_archived_before_needs_decision(publish_case):
    r=prepare(publish_case,timezone_hint=None)
    assert r.exit_code==3,r.receipt
    assert r.receipt['snapshot_id'] and r.receipt['verification']['archive']=='verified'
    assert r.receipt['verification']['schedule']['status']=='not_verified'
    assert not r.receipt['published']


@pytest.mark.parametrize('failure',['write','readback'])
def test_archive_failure_never_writes_network(publish_case,monkeypatch,failure):
    import pipeline
    c=publish_case
    def fail(*a,**k):raise OSError('controlled archive failure')
    monkeypatch.setattr(w,'commit_import_snapshot',fail) if failure=='write' else monkeypatch.setattr(pipeline,'_publish_readback',fail)
    r=publish_plan(c['client'],page_id='test-page',mpp_path=c['source'],project_slug='test',timezone_hint='Europe/Moscow',
        context=c['context'],export=c['export'],plugin_profile=c['profile'])
    assert r.exit_code==5 and not r.receipt['published']
    assert r.counters['POST']==r.counters['PUT']==0
    assert bool(r.receipt['snapshot_id'])==(failure=='readback')


def test_binding_conflict_preserves_frozen_intake(publish_case):
    c=publish_case;first=prepare(c)
    r=prepare(c,project_slug='other')
    assert r.exit_code==4 and r.receipt['error']['code']=='binding_conflict'
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0]==1


def test_new_mpp_publish_in_clean_environment_archives_when_blocked(publish_case):
    c=publish_case
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0]==0
    data=copy.deepcopy(c['export']);data['tasks'][1]['new_unknown_field']={'quality':'unsupported','value':None,'reason':'getter_not_available'}
    r=publish_plan(c['client'],page_id='test-page',mpp_path=c['source'],project_slug='test',timezone_hint='Europe/Moscow',
        context=c['context'],export=data,plugin_profile=c['profile'])
    assert r.exit_code==5 and r.receipt['snapshot_id'] and r.receipt['verification']['archive']=='verified'
    assert r.counters['POST']==r.counters['PUT']==0


def test_prepared_branch_never_calls_legacy_readers(publish_case,monkeypatch):
    import pipeline
    def forbidden(*a,**kw):raise AssertionError('legacy reader/model forbidden')
    for name in ('export_csv','calendar_from_mpp','compute_itogo_from_csv','gantt_critical_warning'):
        monkeypatch.setattr(pipeline,name,forbidden)
    assert prepare(publish_case).exit_code==0


def _fake_raw_upload(case,monkeypatch):
    import pipeline
    def upload(client,page_id,filename,raw,existing):
        # Delegate identity/version behavior, then keep the exact prepared bytes.
        result=client.upload(client,page_id,filename,json.loads(raw),existing)
        client.blobs[(filename,result.version)]=raw
        return result
    monkeypatch.setattr(pipeline,'_upload_prepared_bytes',upload)


def test_durable_admission_before_network_and_actual_readback(publish_case,monkeypatch):
    import pipeline
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    original=pipeline._upload_prepared_bytes
    def assert_durable(client,page_id,filename,raw,existing):
        latest=c['conn'].execute('SELECT * FROM plan_preparation_result ORDER BY rowid DESC LIMIT 1').fetchone()
        assert latest['state']=='admitted'
        evidence=q.get_artifact(c['conn'],latest['evidence_artifact_id'])
        d=json.loads(Path(evidence['path']).read_text())
        assert all(k in d for k in ('admission','profiles','rules','context','target','decisions'))
        return original(client,page_id,filename,raw,existing)
    monkeypatch.setattr(pipeline,'_upload_prepared_bytes',assert_durable)
    p=prepare(c);r=pipeline.publish_prepared(c['client'],p)
    assert r.exit_code==0 and r.receipt['published'] is True,r.receipt
    assert r.receipt['verification']['attachment']==r.receipt['verification']['storage']=='verified'
    assert r.receipt['verification']['schedule']['status']=='not_verified'
    assert r.counters['POST']==r.counters['PUT']==1


def test_admitted_bytes_mismatch_stops_before_put(publish_case,monkeypatch):
    import pipeline
    c=publish_case;_fake_raw_upload(c,monkeypatch);original=pipeline._upload_prepared_bytes
    def corrupt(*args):
        result=original(*args);c['client'].blobs[(result.filename,result.version)]=b'bad bytes';return result
    monkeypatch.setattr(pipeline,'_upload_prepared_bytes',corrupt)
    r=pipeline.publish_prepared(c['client'],prepare(c))
    assert r.exit_code==5 and r.receipt['published'] is None
    assert r.counters['POST']==1 and r.counters['PUT']==0


def test_changed_target_invalidates_admission_and_proposal(publish_case,monkeypatch):
    import pipeline
    c=publish_case;prepared=prepare(c,drop_links=[(2,3)])
    pid=q.get_publish_proposals(c['conn'],prepared.receipt['operation_id'])[0]['proposal_id']
    c['client'].page['body']['storage']['value']+='<p>Foreign edit</p>'
    from test_plan_rules import resume
    r=resume(c,prepared.receipt['operation_id'],accept_proposal=pid,reason='test')
    assert r.exit_code==4 and r.receipt['error']['code']=='target_conflict'
    assert not q.get_publish_proposals(c['conn'],prepared.receipt['operation_id'])[0]['decision_id']
    assert r.counters['POST']==r.counters['PUT']==0


def test_prepared_artifact_corruption_never_uploads(publish_case):
    import pipeline
    c=publish_case;prepared=prepare(c)
    result=q.get_preparation_result(c['conn'],prepared.receipt['operation_id'])
    path=Path(q.get_artifact(c['conn'],result['representation_artifact_id'])['path']);path.write_bytes(b'corrupt')
    r=pipeline.publish_prepared(c['client'],prepared)
    assert r.exit_code==5 and r.receipt['published'] is False and r.counters['POST']==r.counters['PUT']==0


def test_false_attachment_verifier_blocks_put(publish_case,monkeypatch):
    import pipeline
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    monkeypatch.setattr(pipeline,'_verify_stage09_attachment',lambda *a:False)
    r=pipeline.publish_prepared(c['client'],prepare(c))
    assert r.exit_code==5 and r.receipt['published'] is None
    assert r.counters['POST']==1 and r.counters['PUT']==0


def test_public_apply_uses_same_archive_and_admission(publish_case):
    from pipeline import apply_plan
    c=publish_case
    r=apply_plan(c['client'],'test-page',c['source'],'да',project_slug='test',context=c['context'],export=c['export'],
        plugin_profile=c['profile'])
    assert r.exit_code==3 and r.receipt['snapshot_id'] and r.receipt['verification']['archive']=='verified'
    assert r.counters['POST']==r.counters['PUT']==0


def test_mpp_child_uses_shared_admission_before_page_creation(publish_case,monkeypatch):
    import pipeline
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    before=prepare(c,child=True,timezone_hint=None)
    assert before.exit_code==3 and not any(call[0].startswith('POST') for call in c['client'].calls)
    from test_plan_rules import resume
    admitted=resume(c,before.receipt['operation_id'],timezone_hint='Europe/Moscow')
    assert admitted.exit_code==0,admitted.receipt
    result=pipeline.publish_prepared(c['client'],admitted)
    assert result.exit_code==0 and result.receipt['page_id']=='test-child',result.receipt
    assert result.counters['POST']==2 and result.counters['PUT']==0
    assert c['conn'].execute('SELECT count(*) FROM plan_import_item').fetchone()[0]==1


@pytest.mark.parametrize('unavailable', ['client', 'server', 'profile'])
def test_primary_archive_survives_unavailable_confluence(publish_case, monkeypatch, unavailable):
    """Remote failure cannot precede the complete local archive/read-back."""
    import pipeline
    from plugin_profile import PluginProfile
    c = publish_case
    original = pipeline._publish_readback
    checked = []
    def readback(conn, snapshot_id):
        original(conn, snapshot_id)
        checked.append(snapshot_id)
    def fail(*args, **kwargs):
        assert checked, 'remote/profile work preceded snapshot read-back'
        raise OSError('controlled unavailable dependency')
    monkeypatch.setattr(pipeline, '_publish_readback', readback)
    client, profile = c['client'], c['profile']
    if unavailable == 'client':
        client = None
        monkeypatch.setattr(pipeline, 'ConfluenceClient', fail)
    elif unavailable == 'server':
        monkeypatch.setattr(client, 'get_page', fail)
    else:
        profile = None
        monkeypatch.setattr(PluginProfile, 'load', fail)
    r = pipeline.prepare_publish(client, 'test-page', c['source'], project_slug='test',
        timezone_hint='Europe/Moscow', context=c['context'], export=c['export'], plugin_profile=profile)
    assert r.exit_code == 5 and r.receipt['published'] is False, r.receipt
    assert r.receipt['snapshot_id'] in checked
    assert r.receipt['verification']['archive'] == 'verified'
    assert 'archived' in r.receipt['completed_stages']
    w.verify_snapshot(c['conn'], r.receipt['snapshot_id'])
    assert r.counters['POST'] == r.counters['PUT'] == 0


def test_archive_before_remote_failure_resumes_same_snapshot(publish_case, monkeypatch):
    import pipeline
    c = publish_case
    original = c['client'].get_page
    def fail(*args, **kwargs):
        raise OSError('controlled offline')
    monkeypatch.setattr(c['client'], 'get_page', fail)
    first = prepare(c)
    assert first.receipt['verification']['archive'] == 'verified'
    monkeypatch.setattr(c['client'], 'get_page', original)
    c['source'].unlink()
    resumed = pipeline.prepare_publish(c['client'], operation_id=first.receipt['operation_id'],
        db_path=c['context'].db, workvault=c['context'].workvault, cache_dir=c['context'].cache_dir,
        plugin_profile=c['profile'])
    assert resumed.exit_code == 0, resumed.receipt
    assert resumed.receipt['snapshot_id'] == first.receipt['snapshot_id']
    assert resumed.counters['MPXJ_read'] == 0
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0] == 1
