"""New confirmation API: immutable evidence, scope and transactional closure."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import hashlib
import importlib.util
import json
import sqlite3
import sys

import pytest

from mofs_index.plan import query as q, writer as w
from mofs_index.plan.schema import MIGRATIONS
from mofs_index.plan.migrate import ensure_plan_schema, _checksum
from mofs_index.db import connect, initialize
from .test_preparation import prepared, result, canonical


@pytest.fixture
def confirmation(prepared):
    d=prepared;c=d['c'];spec=result(d,allowed=True);rid=w.record_preparation_result(c,spec)
    digest=hashlib.sha256(b'{}').hexdigest()
    storage='<p>verified storage observation</p>';storage_hash=hashlib.sha256(storage.encode()).hexdigest()
    storage_id=d['artifact'](storage.encode(),'storage_snapshot')
    checks={k:True for k in ('skeleton_version','skeleton_macro_count','page_version','one_gantt_macro',
        'macro_id','param_id','param_hash','attachment_name','one_itogo','itogo_values','itogo_above_macro','no_trudozatraty','storage_preserved')}
    attachment={'attachment_id':'att','attachment_version':1,'expected_sha256':digest,'actual_sha256':digest}
    schedule={'status':'not_verified','checks':[],'limitations':['No concrete plugin observation'],'evidence_ids':[]}
    receipt={'operation_id':d['op'],'snapshot_id':d['sid'],'published':True,'exit_code':0,'page_id':'page','attachment_version':1,
        'verification':{'archive':'verified','attachment':'verified','storage':'verified','schedule':schedule},
        'completed_stages':['prepared','archived','admitted','attachment_uploaded','attachment_verified','storage_written','storage_verified','confirmed']}
    proof={'operation_id':d['op'],'result_id':rid,'snapshot_id':d['sid'],'admission_evidence_id':spec.evidence_artifact_id,
        'profiles':{},'diagnostics':{},'schedule':schedule,'checks':checks,'attachment':attachment,'storage_sha256':storage_hash,
        'page_id':'page','page_version':2,'macro_id':'macro','filename':'plan.json'}
    proof_id=d['artifact'](canonical(proof).encode(),'publication_evidence')
    obs=w.PageObservationSpec(d['prep'].context.get('plan_id') or q.get_snapshot(c,d['sid'])['plan_id'],'page',page_version=2,
        storage_artifact_id=storage_id,itogo_raw=storage,verification_status='verified_observation',verification_scope='current_state',
        verification_profile='publish-v1',verification={'checks':checks,'attachment':attachment},storage_sha256=storage_hash)
    w.record_operation_event(c,d['attempt'],'publish_stage',detail=canonical({'stage':'storage_verified'}))
    d.update(spec=w.PublishConfirmationSpec(d['op'],d['attempt'],rid,'test','att',1,'macro','plan.json',proof_id,obs,receipt),proof=proof)
    return d


def test_confirmation_atomic_links_and_idempotent(confirmation):
    d=confirmation;c=d['c'];spec=d['spec']
    pub=w.confirm_publish(c,spec)
    assert w.confirm_publish(c,spec)==pub
    assert q.get_publish_confirmation(c,d['op'])['publication_id']==pub
    assert c.execute('SELECT trust FROM plan_publication').fetchone()[0]=='verified_v1'
    for table in ('plan_publication','plan_page_observation','plan_publication_page_link','plan_publication_snapshot','plan_publish_confirmation'):
        assert c.execute('SELECT count(*) FROM '+table).fetchone()[0]==1
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM plan_publish_confirmation')
    c.rollback()


@pytest.mark.parametrize('field',['operation_id','result_id','snapshot_id','admission_evidence_id','profiles','diagnostics','schedule','checks','attachment','page_id','page_version','macro_id','filename','storage_sha256'])
def test_confirmation_rejects_missing_or_foreign_evidence_without_rows(confirmation,field):
    d=confirmation;c=d['c'];proof=dict(d['proof']);proof.pop(field)
    aid=d['artifact'](canonical(proof).encode(),'publication_evidence')
    with pytest.raises(w.PlanWriterError):w.confirm_publish(c,replace(d['spec'],evidence_artifact_id=aid))
    for table in ('plan_publication','plan_page_observation','plan_publication_page_link','plan_publication_snapshot','plan_publish_confirmation'):
        assert c.execute('SELECT count(*) FROM '+table).fetchone()[0]==0


def test_confirmation_event_failure_rolls_back_every_link(confirmation,monkeypatch):
    d=confirmation;c=d['c']
    monkeypatch.setattr(w,'_operation_event',lambda *a,**k:(_ for _ in ()).throw(OSError('event failed')))
    with pytest.raises(OSError):w.confirm_publish(c,d['spec'])
    for table in ('plan_publication','plan_page_observation','plan_publication_page_link','plan_publication_snapshot','plan_publish_confirmation'):
        assert c.execute('SELECT count(*) FROM '+table).fetchone()[0]==0


def test_0012_preserves_0011_definitions_history_and_repeat(tmp_path):
    path=Path.home()/'hermes-workspace/skills/productivity/edit-plan-confluence/references/implementation/20261116/stage-09/usertools/MofsIndex/after/mofs_index/plan/schema.py'
    spec=importlib.util.spec_from_file_location('_confirmation_old_schema',path)
    old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
    assert [(m.migration_id,_checksum(m)) for m in MIGRATIONS[:11]]==[(m.migration_id,_checksum(m)) for m in old.MIGRATIONS]
    c=connect(tmp_path/'old.sqlite',durable=True);initialize(c)
    with patch('mofs_index.plan.migrate.MIGRATIONS',MIGRATIONS[:11]):
        ensure_plan_schema(c);w.ensure_plan(c,'old-project')
    names=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'plan_%'")]
    before={name:[tuple(r) for r in c.execute('SELECT * FROM '+name)] for name in names if name!='plan_schema_migration'}
    assert ensure_plan_schema(c)==['0012_publish_confirmation']
    assert ensure_plan_schema(c)==[]
    assert all([tuple(r) for r in c.execute('SELECT * FROM '+name)]==rows for name,rows in before.items())
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    c.close()
