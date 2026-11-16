"""Stage 06 direct typed API: immutable evidence, atomic decisions, migration."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest
from mofs_index.db import connect_durable, drop_all, initialize
from mofs_index.plan import query as q, writer as w
from mofs_index.plan.migrate import ensure_plan_schema
from mofs_index.plan.schema import MIGRATIONS
from mofs_index.plan.history import HistoryRequest, history, HistoryQueryError


@pytest.fixture
def decision_case(tmp_path):
    c = connect_durable(tmp_path/'index.sqlite'); ensure_plan_schema(c)
    plan = w.ensure_plan(c, 'p')
    lineage = w.ensure_lineage(c, plan, 'local-archive-v1')
    context = {'save': {'project_slug':'p','lineage_id':lineage,'timezone_hint':None},
               'profiles':{'NORMALIZATION_PROFILE':{'sha256':'a'*64,'name':'normalization-v1'}}}
    manifest = {'schema_version':1,'on_error':'continue','items':[{'item_id':'one','path':'/one.mpp'}]}
    content = w._json(manifest)
    spec = w.ImportBatchSpec('batch',1,content,hashlib.sha256(content.encode()).hexdigest(),'mpp','{}')
    w.create_batch_with_items(c,spec,(w.BatchItemSpec('one','/one.mpp',w._json(context)),))
    row = q.get_batch_items(c,'batch')[0]
    source=tmp_path/'frozen.mpp';source.write_bytes(b'fixture')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    w.freeze_import_item(c,row['item_id'],frozen_locator=str(source),source_mpp_sha256=digest,size_bytes=7,frozen_at='2026-11-16T00:00:00Z')
    w.finalize_batch_freeze(c,'batch')
    evidence=w.ProvenanceSpec(digest,'other','{"explicit":"unconfirmed fixture"}','synthetic','not identity',evidence_id='ev')
    w.record_source_provenance(c,evidence)
    attempt=w.start_batch_item(c,row['item_id'])
    state=w.refresh_batch_proposals(c,row['operation_id'],attempt)
    w.finish_batch_item(c,row['item_id'],attempt,w._json({'status':'needs_decision','error':{'code':q.BATCH_REASONS[0]}}))
    yield c,row,state['proposals'][0],evidence
    c.close()


def test_typed_register_idempotence_context_and_immutability(decision_case):
    c,row,proposal,evidence=decision_case
    spec=w.BatchDecisionSpec(row['operation_id'],proposal['proposal_id'],'User explicitly confirms')
    first=w.register_batch_decision(c,spec)
    assert first['decision_ready'] and w.register_batch_decision(c,spec)['decision_id']==first['decision_id']
    assert q.get_import_item(c,row['item_id'])['status']=='needs_decision'
    assert w.record_source_provenance(c,evidence)=='ev'
    for table in ('plan_batch_decision','plan_batch_proposal','plan_provenance'):
        with pytest.raises(sqlite3.IntegrityError,match='append_only'):
            c.execute('DELETE FROM '+table)
        c.rollback()
    with pytest.raises(w.PlanWriterError,match='decision_conflict'):
        w.register_batch_decision(c,replace(spec,reason='Different reason'))
    with pytest.raises(w.PlanWriterError,match='batch_context_immutable'):
        w.register_batch_decision(c,replace(spec,rule_scope='project'))
    w.record_source_provenance(c,replace(evidence,evidence_id='new',evidence_json='{"new":true}'))
    assert not q.batch_decision_state(c,row['operation_id'])['decision_ready']
    with pytest.raises(w.PlanWriterError,match='proposal_context_mismatch'):
        w.register_batch_decision(c,spec)
    assert len(q.get_batch_decisions(c,row['operation_id']))==1
    assert not c.execute('PRAGMA foreign_key_check').fetchall()


def test_decision_event_failure_rolls_back_insert(decision_case,monkeypatch):
    c,row,proposal,_=decision_case
    original=w._operation_event
    def fail(conn,attempt,kind,*args,**kwargs):
        if kind=='decision_registered': raise RuntimeError('event write failed')
        return original(conn,attempt,kind,*args,**kwargs)
    monkeypatch.setattr(w,'_operation_event',fail)
    with pytest.raises(RuntimeError):
        w.register_batch_decision(c,w.BatchDecisionSpec(row['operation_id'],proposal['proposal_id'],'Confirm'))
    assert not q.get_batch_decisions(c,row['operation_id'])


def test_migration_0009_preserves_preceding_definitions_and_rows(tmp_path,monkeypatch):
    import mofs_index.plan.migrate as migrate
    approved=Path('/home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/references/implementation/20261116/stage-03/usertools/MofsIndex/after/mofs_index/plan/schema.py')
    current=Path(__file__).resolve().parents[2]/'mofs_index/plan/schema.py'
    assert approved.read_text().split('\n\ndef all_plan_table_names')[0] == current.read_text().split('\n\n# Stage 06:')[0]
    c=connect_durable(tmp_path/'old.sqlite')
    monkeypatch.setattr(migrate,'MIGRATIONS',MIGRATIONS[:8]);ensure_plan_schema(c)
    p=w.ensure_plan(c,'populated');l=w.ensure_lineage(c,p,'local')
    snap=w.ingest_snapshot(c,w.SnapshotSpec(plan_id=p,lineage_id=l,representation='mpp'))
    w.select_snapshot_baseline(c,l,snap,is_explicit=True,basis='existing')
    before={t:[tuple(row) for row in c.execute('SELECT * FROM '+t)] for t in ('plan','plan_lineage','plan_snapshot','plan_snapshot_selection','plan_schema_migration')}
    monkeypatch.setattr(migrate,'MIGRATIONS',MIGRATIONS)
    assert ensure_plan_schema(c)==['0009_batch_decisions']
    assert ensure_plan_schema(c)==[]
    for t,rows in before.items():
        after=[tuple(row) for row in c.execute('SELECT * FROM '+t)]
        assert after[:len(rows)]==rows
    drop_all(c);initialize(c)
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    c.close()


def test_typed_history_unknown_and_boundary_without_skill(tmp_path):
    c=connect_durable(tmp_path/'index.sqlite');ensure_plan_schema(c)
    p=w.ensure_plan(c,'p')
    w.record_publication(c,w.PublicationSpec(p,'fixture','attachment',1,published_at='2026-11-16T03:00:00+03:00'))
    w.record_publication(c,w.PublicationSpec(p,'fixture','attachment',2,published_at='2026-11-17T00:00:00Z'))
    w.record_publication(c,w.PublicationSpec(p,'fixture','attachment',3))
    r=history(c,HistoryRequest('p',view='publications',since='2026-11-16T00:00:00Z',until='2026-11-17T00:00:00Z'))
    assert r['result']['total']==1 and r['result']['unknown_time_count']==1
    assert r['result']['records'][0]['attachment_version']==1
    first=history(c,HistoryRequest('p',view='publications',limit=1))['result']
    assert first['next_cursor']
    second=history(c,HistoryRequest('p',view='publications',limit=2,cursor=first['next_cursor']))['result']
    assert len(second['records'])==2
    assert not ({r['publication_id'] for r in first['records']} & {r['publication_id'] for r in second['records']})
    c.close()


def test_typed_writer_rejects_artificial_batch_reason(decision_case):
    c,row,_,_=decision_case
    attempt=q.get_operation_attempts(c,row['operation_id'])[-1]['attempt_id']
    with pytest.raises(w.PlanWriterError,match='invalid_batch_decision_reason'):
        w.finish_batch_item(c,row['item_id'],attempt,w._json({'status':'needs_decision','error':{'code':'unknown_timezone'}}))
    assert q.get_import_item(c,row['item_id'])['error_code']==q.BATCH_REASONS[0]
