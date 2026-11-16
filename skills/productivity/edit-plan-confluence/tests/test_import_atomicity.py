"""Stage 03 real independent-process concurrency and process-death boundaries."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w
from mofs_index.plan.migrate import ensure_plan_schema
from plan_archive import resolve_plan_binding, store_artifact
from plan_operation import begin_import, freeze_operation_input, commit_prepared_import
from plan_reconcile import reconcile_import

pytestmark=pytest.mark.archive_integration


def _snapshot(config):
    return w.SnapshotSpec(plan_id=config["plan_id"],lineage_id=config["lineage_id"],representation="mpp",
        source_artifact_id=config["artifact_id"],source_mpp_sha256=config["sha256"],
        normalization_profile_fingerprint="a"*64,resolved_timezone="unknown",
        tasks=(w.TaskVersionSpec("uid:1",source_id="0",duration_amount="1.0000000000000000001",duration_units="HOURS"),),
        collections=(w.CollectionStatusSpec("tasks","complete",1),))


@pytest.fixture
def archive_case(tmp_path):
    from env import load_settings
    path=tmp_path/"index.sqlite"
    conn=connect_durable(path)
    ensure_plan_schema(conn)
    source=tmp_path/"first.mpp"
    source.write_bytes(b"stable source bytes; parser is not invoked by writer tests")
    context={"paths":{"workvault":str(tmp_path/"WorkVault")},"settings":load_settings().values}
    binding=resolve_plan_binding(None,"test-project",conn=conn)
    artifact,digest=store_artifact(source,"mpp",project_slug="test-project",conn=conn,workvault=tmp_path/"WorkVault")
    config={**binding,"artifact_id":artifact,"sha256":digest}
    operations=[]
    for _ in range(2):
        operation=begin_import(conn,source,context=context)
        freeze_operation_input(conn,operation)
        operations.append(operation)
    yield conn,path,config,operations,source,context
    conn.close()


def _worker(db, config_path, item_id, attempt_id, crash="", barrier=""):
    """Executed only by a test subprocess, never a product entrypoint."""
    conn=connect_durable(db)
    config=json.loads(Path(config_path).read_text())
    if barrier:
        Path(barrier+"."+item_id+".ready").touch()
        deadline=time.monotonic()+10
        while not Path(barrier).exists():
            if time.monotonic()>deadline:
                raise RuntimeError("barrier timeout")
            time.sleep(.01)
    class CrashConnection:
        def __getattr__(self,name):
            return getattr(conn,name)
        def execute(self,sql,parameters=()):
            if crash=="before_commit" and sql=="COMMIT":
                os._exit(79)
            cursor=conn.execute(sql,parameters)
            points={"after_snapshot":"INSERT INTO plan_snapshot(","after_versions":"INSERT INTO plan_task_version(",
                    "after_item_link":"UPDATE plan_import_item SET plan_id=", "after_event":"INSERT INTO plan_attempt_event("}
            if crash in points and points[crash] in sql:
                os._exit(79)
            if crash=="after_commit" and sql=="COMMIT":
                os._exit(79)
            return cursor
    result=w.commit_import_snapshot(CrashConnection(),item_id,attempt_id,_snapshot(config))
    if crash=="before_readback":
        os._exit(79)
    def mirror(_):
        if crash=="before_receipt":
            os._exit(79)
    recovered=reconcile_import(conn,item_id,receipt_writer=mirror)
    print(json.dumps({"status":result.status,"snapshot_id":recovered["snapshot_id"]}),flush=True)
    conn.close()


def _start_worker(db,config_path,operation,crash="",barrier=""):
    scripts=Path(__file__).resolve().parents[1]/"scripts"
    mofs=Path(w.__file__).resolve().parents[2]
    code=("import sys;sys.path[:0]="+repr([str(scripts),str(mofs),str(Path(__file__).parent)])+
          ";from test_import_atomicity import _worker;_worker(*sys.argv[1:])")
    return subprocess.Popen([sys.executable,"-c",code,str(db),str(config_path),operation.item_id,operation.attempt_id,crash,barrier],
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def test_two_processes_one_snapshot_two_receipts(archive_case,tmp_path):
    conn,db,config,operations,*_=archive_case
    cfg=tmp_path/"worker.json";cfg.write_text(json.dumps(config))
    barrier=str(tmp_path/"go")
    children=[_start_worker(db,cfg,op,barrier=barrier) for op in operations]
    try:
        deadline=time.monotonic()+10
        while not all(Path(barrier+"."+op.item_id+".ready").exists() for op in operations):
            assert time.monotonic()<deadline
            time.sleep(.01)
        Path(barrier).touch()
        outputs=[]
        for child in children:
            stdout,stderr=child.communicate(timeout=20)
            assert child.returncode==0,stderr
            outputs.append(json.loads(stdout))
        assert {o["status"] for o in outputs}=={"saved","unchanged"}
        assert len({o["snapshot_id"] for o in outputs})==1
        assert conn.execute("SELECT count(*) FROM plan_import_item WHERE snapshot_id IS NOT NULL").fetchone()[0]==2
        assert conn.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0]==1
        assert conn.execute("SELECT count(*) FROM plan_attempt_event WHERE event_kind='snapshot_committed'").fetchone()[0]==2
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        for child in children:
            if child.poll() is None:
                child.kill();child.wait()


@pytest.mark.parametrize("boundary",["after_snapshot","after_versions","after_item_link","after_event","before_commit",
                                     "after_commit","before_readback","before_receipt"])
def test_process_death_commit_boundaries(archive_case,tmp_path,boundary,monkeypatch):
    conn,db,config,operations,*_=archive_case
    op=operations[0]
    cfg=tmp_path/"worker.json";cfg.write_text(json.dumps(config))
    before={name:[tuple(r) for r in conn.execute("SELECT * FROM "+name)] for name in ("plan_snapshot_selection","plan_baseline_selection","plan_publication")}
    child=_start_worker(db,cfg,op,crash=boundary)
    _,stderr=child.communicate(timeout=20)
    assert child.returncode==79,stderr
    committed=boundary in {"after_commit","before_readback","before_receipt"}
    assert bool(q.get_import_item(conn,op.item_id)["snapshot_id"]) is committed
    assert conn.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0]==int(committed)
    assert conn.execute("SELECT count(*) FROM plan_task_version").fetchone()[0]==int(committed)
    assert conn.execute("SELECT count(*) FROM plan_attempt_event WHERE event_kind='snapshot_committed'").fetchone()[0]==int(committed)
    if committed:
        snapshot=q.get_import_item(conn,op.item_id)["snapshot_id"]
        # A committed path must neither parse nor insert a second snapshot.
        def forbidden(*args,**kwargs):
            raise AssertionError("reparse/reinsert after commit forbidden")
        monkeypatch.setattr(w,"_insert_snapshot",forbidden)
        assert reconcile_import(conn,op.item_id)["snapshot_id"]==snapshot
        assert w.commit_import_snapshot(conn,op.item_id,op.attempt_id,_snapshot(config)).snapshot_id==snapshot
    else:
        assert reconcile_import(conn,op.item_id) is None
        assert w.commit_import_snapshot(conn,op.item_id,op.attempt_id,_snapshot(config)).snapshot_id
    for name,rows in before.items():
        assert [tuple(r) for r in conn.execute("SELECT * FROM "+name)]==rows
    assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_operation_repeat_preserves_item_adds_attempt(archive_case):
    conn,_,config,operations,source,context=archive_case
    first=operations[0]
    w.commit_import_snapshot(conn,first.item_id,first.attempt_id,_snapshot(config))
    source.unlink()  # Resume never reads the vanished original.
    repeat=begin_import(conn,source,context={"changed_defaults":True},operation_id=first.operation_id)
    assert repeat.operation_id==first.operation_id and repeat.item_id==first.item_id
    assert repeat.attempt_id!=first.attempt_id
    assert freeze_operation_input(conn,repeat).sha256==config["sha256"]
    assert len(q.get_operation_events(conn,first.operation_id))==4  # two starts, freeze, commit
    assert commit_prepared_import(conn,repeat,binding={},prepared={})["snapshot_id"]==q.get_import_item(conn,first.item_id)["snapshot_id"]


def test_unresolved_project_has_durable_input_no_fake_snapshot(tmp_path):
    from env import load_settings
    conn=connect_durable(tmp_path/"index.sqlite");ensure_plan_schema(conn)
    source=tmp_path/"unbound.mpp";source.write_bytes(b"unresolved source")
    ctx={"paths":{"workvault":str(tmp_path/"WorkVault")},"settings":load_settings().values}
    op=begin_import(conn,source,context=ctx)
    frozen=freeze_operation_input(conn,op)
    assert str(tmp_path/"WorkVault/_plan-receipts"/op.operation_id/"input") in str(frozen.mpp_path)
    source.unlink()
    assert frozen.mpp_path.read_bytes()==b"unresolved source"
    assert q.get_operation(conn,op.operation_id)["plan_id"] is None
    assert q.get_attempt(conn,op.attempt_id)["plan_id"] is None
    for table in ("plan","plan_snapshot","plan_lineage"):
        assert conn.execute("SELECT count(*) FROM "+table).fetchone()[0]==0
    conn.close()


def test_different_zip_containers_same_mpp_reuse_snapshot(tmp_path):
    import zipfile
    from env import load_settings
    from prepared_plan import PreparedPlan
    source_export=json.loads((Path(__file__).parent/"fixtures/synthetic/relations-all-types.json").read_text())
    payload=(Path(__file__).parent/"fixtures/synthetic/relations-all-types.mpp").read_bytes()
    conn=connect_durable(tmp_path/"index.sqlite");ensure_plan_schema(conn)
    context={"paths":{"workvault":str(tmp_path/"WorkVault")},"settings":load_settings().values}
    binding=resolve_plan_binding(None,"project",conn=conn)
    prepared=PreparedPlan.from_export(source_export).to_dict()
    results=[];containers=[]
    for index,member in enumerate(("one.mpp","nested/renamed.mpp")):
        path=tmp_path/f"container-{index}.bin"
        with zipfile.ZipFile(path,"w") as archive:
            archive.writestr(member,payload)
        op=begin_import(conn,path,context=context)
        frozen=freeze_operation_input(conn,op)
        containers.append(frozen.container_sha256)
        results.append(commit_prepared_import(conn,op,binding=binding,prepared=prepared))
        item=q.get_import_item(conn,op.item_id)
        assert item["zip_member"]==member and item["container_sha256"]==frozen.container_sha256
        assert q.get_snapshot(conn,results[-1]["snapshot_id"])["source_json"]
    assert containers[0]!=containers[1]
    assert results[0]["snapshot_id"]==results[1]["snapshot_id"]
    assert results[1]["status"]=="unchanged"
    assert conn.execute("SELECT count(*) FROM plan_import_item").fetchone()[0]==2
    conn.close()


def test_readback_failure_retains_commit_and_no_second_parse(archive_case,monkeypatch):
    conn,_,config,operations,*_=archive_case
    operation=operations[0]
    result=w.commit_import_snapshot(conn,operation.item_id,operation.attempt_id,_snapshot(config))
    real_verify=w.verify_snapshot
    def failed(*args):
        raise OSError("simulated read-back failure")
    monkeypatch.setattr(w,"verify_snapshot",failed)
    with pytest.raises(OSError,match="read-back"):
        reconcile_import(conn,operation.item_id)
    assert q.get_import_item(conn,operation.item_id)["snapshot_id"]==result.snapshot_id
    monkeypatch.setattr(w,"verify_snapshot",real_verify)
    def mirror_failed(_):
        raise OSError("simulated receipt failure")
    with pytest.raises(OSError,match="receipt failure"):
        reconcile_import(conn,operation.item_id,receipt_writer=mirror_failed)
    assert reconcile_import(conn,operation.item_id)["snapshot_id"]==result.snapshot_id
    assert conn.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0]==1


def test_failed_zip_receipt_retains_container_locator(tmp_path):
    import zipfile
    from env import load_settings
    from mpp_input import InputError
    conn=connect_durable(tmp_path/"index.sqlite");ensure_plan_schema(conn)
    source=tmp_path/"multiple.zip"
    with zipfile.ZipFile(source,"w") as archive:
        archive.writestr("a.mpp",b"a");archive.writestr("b.mpp",b"b")
    context={"paths":{"workvault":str(tmp_path/"WorkVault")},"settings":load_settings().values}
    operation=begin_import(conn,source,context=context)
    with pytest.raises(InputError,match="multiple_mpp_candidates"):
        freeze_operation_input(conn,operation)
    item=q.get_import_item(conn,operation.item_id)
    assert item["status"]=="failed" and item["error_code"]=="multiple_mpp_candidates"
    assert Path(item["container_locator"]).read_bytes()==source.read_bytes()
    assert item["container_sha256"]==hashlib.sha256(source.read_bytes()).hexdigest()
    assert item["frozen_at"] is None and item["snapshot_id"] is None
    conn.close()
