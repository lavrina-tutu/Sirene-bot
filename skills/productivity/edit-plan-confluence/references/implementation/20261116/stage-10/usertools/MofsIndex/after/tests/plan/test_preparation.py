"""Stage 09 typed API and migration history; no skill SQL is involved."""
from pathlib import Path
import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest
from mofs_index.db import connect,initialize
from mofs_index.plan import writer as w,query as q
from mofs_index.plan.migrate import ensure_plan_schema,_checksum
from mofs_index.plan.schema import MIGRATIONS


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


@pytest.fixture
def prepared(tmp_path):
    c=connect(tmp_path/'state.sqlite',durable=True);initialize(c);ensure_plan_schema(c)
    plan=w.ensure_plan(c,'test');line=w.ensure_lineage(c,plan,'test')
    def artifact(data,kind):
        digest=hashlib.sha256(data).hexdigest();p=tmp_path/digest;p.write_bytes(data)
        return w.record_artifact(c,digest,kind,str(p),size_bytes=len(data))
    source=b'typed synthetic source';digest=hashlib.sha256(source).hexdigest();aid=artifact(source,'mpp')
    op=w.create_operation(c,w.OperationSpec('publish',canonical({'fixture':'nonsecret'}),plan_id=plan,lineage_id=line))
    item=w.create_import_item(c,w.ImportItemSpec(op,'test.mpp','fixture',source_mpp_sha256=digest))
    attempt=w.begin_operation_attempt(c,op,item)
    def snapshot(tz):
        data={'resolved_timezone':tz,'source_identity':{'sha256':digest}}
        raw=canonical(data);semantic=hashlib.sha256(raw.encode()).hexdigest()
        spec=w.SnapshotSpec(plan,'mpp',lineage_id=line,source_artifact_id=aid,source_mpp_sha256=digest,
            normalization_profile_fingerprint='unit-v1',resolved_timezone=w.normalize_timezone(tz),source_json=raw,normalized_data_sha256=semantic,
            tasks=(w.TaskVersionSpec('uid:1',uid='1'),w.TaskVersionSpec('uid:2',uid='2')))
        envelope=artifact(canonical({'semantic_sha256':semantic,'normalized_data':data}).encode(),'prepared_json')
        return spec,envelope
    spec,envelope=snapshot('unknown');sid=w.commit_import_snapshot(c,item,attempt,spec).snapshot_id
    prep=w.PreparationSpec(op,1,sid,envelope,{'fixture':'nonsecret'},{'project_slug':'test','timezone_hint':None})
    w.record_preparation(c,prep)
    yield dict(c=c,op=op,item=item,attempt=attempt,prep=prep,sid=sid,snapshot=snapshot,artifact=artifact)
    c.close()


def result(d,*,allowed=False):
    admission={'allowed':allowed,'blockers':[] if allowed else [{'category':'timezone'}]}
    rep=d['artifact'](b'{}','prepared_json')
    evidence={'admission':admission,'context':d['prep'].context,'snapshot_id':d['sid'],'profiles':{},'rules':[],
              'diagnostics':{},'target':{},'archive':'verified','representation_sha256':hashlib.sha256(b'{}').hexdigest()}
    aid=d['artifact'](canonical(evidence).encode(),'admission_evidence')
    return w.PreparationResultSpec(d['op'],1,rep,aid,admission,{'basis_sha256':'unit-basis'})


def test_preparation_append_only_and_admission_requires_evidence(prepared):
    d=prepared;c=d['c'];spec=result(d,allowed=True)
    rid=w.record_preparation_result(c,spec)
    assert q.get_preparation_result(c,d['op'])['result_id']==rid
    assert q.get_preparation_result(c,d['op'])['state']=='admitted'
    with pytest.raises(w.PlanWriterError):w.record_preparation_result(c,replace(spec,admission={'allowed':True,'blockers':['bad']}))
    for table in ('plan_preparation','plan_preparation_result'):
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM '+table)
        c.rollback()
    assert w.record_preparation(c,d['prep'])==1


def test_timezone_preparation_preserves_intake_and_prior_snapshot(prepared):
    d=prepared;c=d['c'];w.record_preparation_result(c,result(d))
    spec,envelope=d['snapshot']('Europe/Moscow');sid=w.ingest_snapshot(c,spec)
    nextprep=replace(d['prep'],revision=2,snapshot_id=sid,prepared_artifact_id=envelope,
        request={'project_slug':'test','timezone_hint':'Europe/Moscow'})
    w.record_preparation(c,nextprep)
    assert q.get_operation_item(c,d['op'])['snapshot_id']==d['sid']
    assert len(q.get_preparation_history(c,d['op']))==2
    assert q.get_preparation(c,d['op'])['snapshot_id']==sid
    assert q.get_snapshot(c,d['sid'])['resolved_timezone']=='unknown'


def test_timezone_preparation_forbidden_after_intent(prepared):
    d=prepared;c=d['c'];w.record_preparation_result(c,result(d))
    w.record_operation_event(c,d['attempt'],'publish_network_intent',detail='test')
    spec,envelope=d['snapshot']('UTC');sid=w.ingest_snapshot(c,spec)
    with pytest.raises(w.PlanWriterError,match='timezone_revision_forbidden'):
        w.record_preparation(c,replace(d['prep'],revision=2,snapshot_id=sid,prepared_artifact_id=envelope))
    assert len(q.get_preparation_history(c,d['op']))==1


def test_proposal_decision_exact_context_idempotent_conflict(prepared):
    d=prepared;c=d['c'];w.record_preparation_result(c,result(d))
    content={'snapshot_id':d['sid'],'basis_sha256':'unit-basis','action':'exclude_dependency','losses':['one exact dependency']}
    pid=w.record_publish_proposal(c,w.PublishProposalSpec(d['op'],1,content))
    assert w.record_publish_proposal(c,w.PublishProposalSpec(d['op'],1,content))==pid
    spec=w.PublishDecisionSpec(d['op'],pid,'Explicit test consent')
    did=w.register_publish_decision(c,spec)
    assert w.register_publish_decision(c,spec)==did
    with pytest.raises(w.PlanWriterError,match='decision_conflict'):w.register_publish_decision(c,replace(spec,reason='changed'))
    assert q.get_publish_proposals(c,d['op'])[0]['decision_id']==did


def test_0011_prefix_checksums_migration_idempotency(tmp_path):
    # Earlier installed migration definitions are checked against committed stage 08 delivery.
    root=Path.home()/'hermes-workspace/skills/productivity/edit-plan-confluence/references/implementation/20261116/stage-07/usertools/MofsIndex/after/mofs_index/plan/schema.py'
    import importlib.util,sys
    spec=importlib.util.spec_from_file_location('_old_stage07_schema',root);old=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=old;spec.loader.exec_module(old)
    assert [(m.migration_id,_checksum(m)) for m in MIGRATIONS[:10]]==[(m.migration_id,_checksum(m)) for m in old.MIGRATIONS]
    c=connect(tmp_path/'legacy.sqlite',durable=True);initialize(c)
    from unittest.mock import patch
    with patch('mofs_index.plan.migrate.MIGRATIONS',MIGRATIONS[:10]):
        ensure_plan_schema(c)
        pid=w.ensure_plan(c,'preserved')
    with patch('mofs_index.plan.migrate.MIGRATIONS',MIGRATIONS[:11]):
        assert ensure_plan_schema(c)==['0011_publish_preparation']
    assert ensure_plan_schema(c)==['0012_publish_confirmation']
    assert ensure_plan_schema(c)==[]
    assert q.resolve_plan(c,'preserved')['plan_id']==pid
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    c.close()
