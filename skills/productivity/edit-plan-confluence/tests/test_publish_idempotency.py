from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import pipeline
from mofs_index.plan import writer as w, query as q
from prepared_plan import canonical_bytes
from plan_archive import store_artifact
from test_publish_prepare import prepare, _fake_raw_upload
from test_publish_resume import resume, calls

pytestmark = pytest.mark.unit


def test_same_source_profile_target_no_upload_put_or_duplicate_publication(publish_case, monkeypatch):
    c = publish_case; _fake_raw_upload(c, monkeypatch)
    first = pipeline.publish_prepared(c['client'], prepare(c))
    assert first.exit_code == 0, first.receipt
    again = pipeline.publish_prepared(c['client'], prepare(c))
    assert again.exit_code == 0 and again.receipt['status'] == 'unchanged', again.receipt
    assert again.receipt['published'] is True and again.receipt['external_effect'] == 'none'
    assert again.counters['POST'] == again.counters['PUT'] == 0
    assert calls(c, 'POST_ATTACHMENT') == calls(c, 'PUT') == 1
    assert c['conn'].execute('SELECT count(*) FROM plan_publication').fetchone()[0] == 1
    assert c['conn'].execute('SELECT count(*) FROM plan_import_item').fetchone()[0] == 2
    assert c['conn'].execute('SELECT count(*) FROM plan_snapshot').fetchone()[0] == 1
    resumed = resume(c, first.receipt['operation_id'])
    assert resumed.exit_code == 0 and resumed.receipt['status'] == 'unchanged', resumed.receipt
    assert calls(c, 'POST_ATTACHMENT') == calls(c, 'PUT') == 1


def corrected_preparation(case):
    """New durable admission: only expected summary changes, bytes stay fixed.

    This deliberately models a new summary preparation, without mutating old
    admissions, converter profiles, the MPP snapshot or its source.
    """
    c = case; prepared = prepare(c)
    old = q.get_preparation_result(c['conn'], prepared.receipt['operation_id'])
    evidence = json.loads(Path(w.verify_artifact(c['conn'], old['evidence_artifact_id'])).read_text())
    result = copy.deepcopy(old['result']);result['summary']['n_days'] += 1
    aid, _ = store_artifact(canonical_bytes(evidence), 'admission_evidence', ext='json',
        project_slug='test',conn=c['conn'],workvault=c['wv'])
    prepared.result_id = w.record_preparation_result(c['conn'],w.PreparationResultSpec(prepared.receipt['operation_id'],
        old['preparation_revision'],old['representation_artifact_id'],aid,old['admission'],result))
    return prepared


def test_new_expected_itogo_is_storage_only(publish_case, monkeypatch):
    c = publish_case; _fake_raw_upload(c, monkeypatch)
    first = pipeline.publish_prepared(c['client'], prepare(c));assert first.exit_code == 0
    corrected = pipeline.publish_prepared(c['client'], corrected_preparation(c))
    assert corrected.exit_code == 0, corrected.receipt
    assert corrected.counters['POST'] == 0 and corrected.counters['PUT'] == 1
    assert calls(c, 'POST_ATTACHMENT') == 1 and calls(c, 'PUT') == 2
    assert c['conn'].execute('SELECT count(*) FROM plan_publication').fetchone()[0] == 1
    assert c['conn'].execute('SELECT count(*) FROM plan_publish_confirmation').fetchone()[0] == 2


def test_confirmed_operation_never_repairs_changed_target(publish_case, monkeypatch):
    c = publish_case; _fake_raw_upload(c, monkeypatch)
    first = pipeline.publish_prepared(c['client'], prepare(c));assert first.exit_code == 0
    c['client'].page['body']['storage']['value'] = c['client'].page['body']['storage']['value'].replace('Итого:', 'Чужое Итого:')
    result = resume(c, first.receipt['operation_id'])
    assert result.exit_code == 4, result.receipt
    assert calls(c, 'POST_ATTACHMENT') == calls(c, 'PUT') == 1


def test_full_confirmation_links_and_legacy_writer_cannot_promote(publish_case, monkeypatch):
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    result=pipeline.publish_prepared(c['client'],prepare(c));assert result.exit_code==0,result.receipt
    confirmation=q.get_publish_confirmation(c['conn'],result.receipt['operation_id'])
    row=dict(c['conn'].execute('SELECT * FROM plan_publication').fetchone())
    assert row['trust']=='verified_v1'
    assert c['conn'].execute('SELECT snapshot_id FROM plan_publication_snapshot WHERE publication_id=?',(row['publication_id'],)).fetchone()[0]==result.receipt['snapshot_id']
    for key in ('evidence_artifact_id',):w.verify_artifact(c['conn'],confirmation[key])
    evidence=json.loads(Path(w.verify_artifact(c['conn'],confirmation['evidence_artifact_id'])).read_text())
    assert evidence['admission_evidence_id'] and evidence['diagnostics'] and evidence['profiles']
    assert confirmation['schedule']['status']=='not_verified'
    with pytest.raises(w.PlanWriterError):
        w.record_publication(c['conn'],w.PublicationSpec(row['plan_id'],'test','fake',1,trust='verified_v1'))


def test_operation_show_omits_storage_from_network_journal(publish_case,monkeypatch):
    from plan_operation import show_operation
    c=publish_case;_fake_raw_upload(c,monkeypatch)
    marker='Foreign page content that must stay in the durable artifact only'
    c['client'].page['body']['storage']['value']+='<p>'+marker+'</p>'
    result=pipeline.publish_prepared(c['client'],prepare(c));assert result.exit_code==0,result.receipt
    shown=show_operation(result.receipt['operation_id'],db_path=c['db'],workvault=c['wv'],cache_dir=c['cache'])
    assert shown['exit_code']==0 and shown['published'] is True
    assert marker not in json.dumps(shown,ensure_ascii=False)
    assert any('journal_event_id' in e['detail'] for e in shown['events'])
    # Internal reconciliation still has the exact immutable storage intent.
    events=q.get_operation_events(c['conn'],result.receipt['operation_id'])
    assert any(marker in (e['detail'] or '') for e in events)
