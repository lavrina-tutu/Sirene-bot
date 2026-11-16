"""Actual process death at freeze/commit/receipt boundaries and frozen recovery."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

import plan_batch as pb
import plan_save as ps
from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w
from plan_context import PlanContext
from plan_receipt import validate_batch_receipt
from test_plan_batch import batch_case, create, fake_export, fake_runtime

pytestmark = pytest.mark.archive_integration


def test_resume_stop_retries_only_explicit_retryable_same_bytes(batch_case, monkeypatch):
    context, sources = batch_case
    seen = []
    def reader(source, **kwargs):
        seen.append(Path(source).read_bytes())
        if len(seen) == 2:
            raise ps.PlanSaveError("mpp_read_timeout", retryable=True)
        return fake_export(source)
    monkeypatch.setattr(ps, "run_export_full", reader)
    first = create(batch_case, on_error="stop")
    assert first["exit_code"] == 6 and first["counts"]["not_started"] == 1, first
    assert pb.resume_batch("test", context=context)["exit_code"] == 6
    assert len(seen) == 2
    original = [p.read_bytes() for p in sources]
    for path in sources: path.unlink()
    monkeypatch.setattr(PlanContext, "resolve", lambda **k: pytest.fail("defaults during resume"))
    final = pb.resume_batch("test", db_path=context.db, retry_failed=True)
    validate_batch_receipt(final)
    assert final["exit_code"] == 0 and seen == [original[0], original[1], original[1], original[2]], final
    assert final["manifest_sha256"] == first["manifest_sha256"]
    assert final["items"][0] == first["items"][0]


@pytest.mark.parametrize("failure", ["missing", "hash", "changed"])
def test_freeze_failure_never_accepts_new_bytes_under_same_id(batch_case, tmp_path, monkeypatch, failure):
    from mpp_input import InputError
    context, sources = batch_case
    source = sources[1]
    expected = source.read_bytes()
    if failure == "missing": source.unlink()
    if failure == "changed":
        real = pb.freeze_operation_input
        def freeze(conn, operation):
            if q.get_import_item(conn, operation.item_id)["ordinal"] == 2:
                raise InputError("input_changed")
            return real(conn, operation)
        monkeypatch.setattr(pb, "freeze_operation_input", freeze)
    doc = {"schema_version":1,"on_error":"stop","items":[{"item_id":str(i), "path":str(p), "project_slug":"batch-project"} for i,p in enumerate(sources)]}
    if failure == "hash": doc["items"][1]["expected_sha256"] = "a"*64
    manifest = tmp_path/"request.json"; manifest.write_text(json.dumps(doc))
    first = pb.create_batch(context=context, manifest=manifest, batch_id="test")
    assert first["exit_code"] == 6 and first["counts"]["saved"] == 1, first
    source.write_bytes(expected + b"new bytes")
    monkeypatch.setattr(pb, "freeze_operation_input", lambda *a: pytest.fail("refreeze"))
    second = pb.resume_batch("test", context=context, retry_failed=True)
    assert second["exit_code"] == 6 and second["items"][1] == first["items"][1]
    assert second["items"][1]["error"]["retryable"] is False


def test_lost_frozen_artifact_infrastructure_only_identical_repair(batch_case, monkeypatch):
    context, sources = batch_case
    first = create((context, sources[:1]))
    c = connect_durable(context.db)
    row = q.get_batch_items(c, "test")[0]; c.close()
    frozen = Path(row["frozen_locator"]); original = frozen.read_bytes(); frozen.unlink()
    for path in sources: path.unlink()
    missing = pb.resume_batch("test", context=context)
    assert missing["exit_code"] == 5 and missing["error"]["code"] == "frozen_input_corrupt", missing
    frozen.write_bytes(b"replacement")
    assert pb.resume_batch("test", context=context)["exit_code"] == 5
    frozen.write_bytes(original)
    monkeypatch.setattr(ps, "run_export_full", lambda *a, **k: pytest.fail("reader on saved"))
    final = pb.resume_batch("test", context=context)
    assert final["exit_code"] == 0 and final["items"] == first["items"]


@pytest.mark.parametrize("mirror", ["save", "batch"])
def test_mirror_failure_preserves_commit_and_restores_without_reader(batch_case, monkeypatch, mirror):
    import plan_receipt
    context, sources = batch_case
    module = plan_receipt if mirror == "save" else pb
    real = module.write_receipt
    def write(owner, event, receipt, **kwargs):
        if event == mirror: raise OSError("mirror unavailable")
        return real(owner, event, receipt, **kwargs)
    monkeypatch.setattr(module, "write_receipt", write)
    first = create(batch_case)
    assert first["exit_code"] == 5 and first["items"][0]["snapshot_id"], first
    monkeypatch.setattr(module, "write_receipt", real)
    for path in sources: path.unlink()
    # For a single-receipt failure later items remain unprocessed; their frozen
    # bytes can be read, but the already committed first item must never parse.
    seen = []
    def reader(source, **kwargs):
        seen.append(str(source)); return fake_export(source)
    monkeypatch.setattr(ps, "run_export_full", reader)
    final = pb.resume_batch("test", context=context)
    assert final["exit_code"] == 0, final
    assert len(seen) == (2 if mirror == "save" else 0)
    assert final["items"][0]["snapshot_id"] == first["items"][0]["snapshot_id"]
    c = connect_durable(context.db)
    assert c.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0] == 3
    assert c.execute("SELECT count(*) FROM plan_import_item").fetchone()[0] == 3
    c.close()


def _crash_worker(config_path, boundary):
    """Test worker only; no product crash flags or secondary public CLI."""
    import plan_receipt
    cfg = json.loads(Path(config_path).read_text())
    context = PlanContext.from_snapshot(cfg["context"])
    pb.select_mpxj_python = ps.select_mpxj_python = fake_runtime
    ps.run_export_full = fake_export
    if boundary == "after_first_freeze":
        real = pb.freeze_operation_input
        def freeze(*args):
            real(*args); os._exit(79)
        pb.freeze_operation_input = freeze
    elif boundary in ("before_freeze_barrier", "after_freeze_barrier"):
        real = w.finalize_batch_freeze
        def barrier(*args):
            if boundary == "before_freeze_barrier": os._exit(79)
            real(*args); os._exit(79)
        w.finalize_batch_freeze = barrier
    elif boundary == "before_snapshot_commit":
        real = w._operation_event
        def event(*args, **kwargs):
            result = real(*args, **kwargs)
            if args[2] == "snapshot_committed": os._exit(79)
            return result
        w._operation_event = event
    elif boundary == "after_snapshot_commit":
        real = w.commit_import_snapshot
        def commit(*args):
            real(*args); os._exit(79)
        w.commit_import_snapshot = commit
    elif boundary == "after_item_result":
        real = w.finish_batch_item
        def finish(*args):
            real(*args); os._exit(79)
        w.finish_batch_item = finish
    elif boundary in ("before_save_receipt", "before_batch_receipt"):
        module = plan_receipt if boundary == "before_save_receipt" else pb
        real = module.write_receipt
        def write(owner, event, payload, **kwargs):
            if event == ("save" if boundary == "before_save_receipt" else "batch"): os._exit(79)
            return real(owner, event, payload, **kwargs)
        module.write_receipt = write
    result = pb.create_batch(context=context, mpp=[cfg["source"]], project_slug="batch-project", batch_id="crash")
    print(json.dumps(result))


def _start_crash(cfg, boundary):
    tests = str(Path(__file__).parent)
    scripts = str(Path(__file__).resolve().parents[1]/"scripts")
    code = "import sys;sys.path[:0]=" + repr([tests, scripts, str(Path(w.__file__).parents[2])]) + ";from test_batch_resume import _crash_worker;_crash_worker(*sys.argv[1:])"
    return subprocess.Popen([sys.executable,"-c",code,str(cfg),boundary], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


BOUNDARIES = ["after_first_freeze", "before_freeze_barrier", "after_freeze_barrier", "before_snapshot_commit",
              "after_snapshot_commit", "before_save_receipt", "after_item_result", "before_batch_receipt"]


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_process_death_freeze_commit_receipt_boundaries(batch_case, tmp_path, monkeypatch, boundary):
    context, sources = batch_case
    cfg = tmp_path/"crash.json"
    cfg.write_text(json.dumps({"context":context.snapshot(),"source":str(sources[0])}))
    child = _start_crash(cfg, boundary)
    stdout, stderr = child.communicate(timeout=30)
    assert child.returncode == 79, (stdout, stderr)
    c = connect_durable(context.db)
    batch = q.get_import_batch(c, "crash")
    rows = q.get_batch_items(c, "crash")
    snapshot = rows[0]["snapshot_id"]
    committed = boundary in ("after_snapshot_commit", "before_save_receipt", "after_item_result", "before_batch_receipt")
    assert bool(snapshot) is committed
    assert c.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0] == int(committed)
    c.close()
    sources[0].unlink(); shutil.rmtree(context.cache_dir, ignore_errors=True)
    if committed:
        monkeypatch.setattr(ps, "run_export_full", lambda *a, **k: pytest.fail("parse after committed crash"))
    result = pb.resume_batch("crash", db_path=context.db)
    validate_batch_receipt(result)
    if boundary in ("after_first_freeze", "before_freeze_barrier"):
        assert result["exit_code"] == 4 and result["error"]["code"] == "inputs_not_frozen"
        assert batch["inputs_frozen_at"] is None
    else:
        assert result["exit_code"] == 0, result
        assert not committed or result["items"][0]["snapshot_id"] == snapshot
        c = connect_durable(context.db)
        assert c.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM plan_import_item").fetchone()[0] == 1
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        c.close()


def test_resume_rejects_changed_frozen_context(batch_case, monkeypatch, tmp_path):
    context, sources = batch_case
    sources[1].write_bytes(b"broken")
    first = create(batch_case, on_error="stop")
    assert first["exit_code"] == 6
    # Changing only runtime defaults is ignored; explicit path changes conflict.
    assert pb.resume_batch("test", db_path=context.db, workvault=tmp_path/"other")["exit_code"] == 4
    # A temporarily failed uncommitted item is allowed retry only on pinned code.
    c = connect_durable(context.db); row=q.get_batch_items(c,"test")[1]
    attempt=q.get_operation_attempts(c,row["operation_id"])[-1]["attempt_id"]
    w.finish_batch_item(c,row["item_id"],attempt,json.dumps({"status":"failed","error":{"code":"mpp_read_timeout","retryable":True}})); c.close()
    monkeypatch.setattr(pb, "_code_fingerprints", lambda ctx: {"changed":"reader"})
    conflict=pb.resume_batch("test", db_path=context.db, retry_failed=True)
    assert conflict["exit_code"] == 4 and conflict["error"]["code"] == "batch_context_conflict", conflict


def test_journaling_failure_stops_after_confirmed_success(batch_case, monkeypatch):
    import sqlite3
    real=w.start_batch_item
    calls=[]
    def start(conn,item_id):
        calls.append(item_id)
        if len(calls)==2: raise sqlite3.OperationalError("journal unavailable")
        return real(conn,item_id)
    monkeypatch.setattr(w,"start_batch_item",start)
    result=create(batch_case)
    assert result["exit_code"]==5 and result["counts"]["saved"]==1 and result["counts"]["not_started"]==2, result


def test_missing_mirror_recovery_verifies_committed_artifacts(batch_case, monkeypatch):
    context,sources=batch_case
    result=create((context,sources[:1]))
    c=connect_durable(context.db);row=q.get_batch_items(c,"test")[0]
    snapshot=q.get_snapshot(c,row["snapshot_id"])
    artifact=q.get_artifact(c,snapshot["source_artifact_id"]);c.close()
    mirror=context.workvault/"_plan-receipts"/row["operation_id"]/"save.json"
    mirror.unlink()
    Path(artifact["path"]).write_bytes(b"damaged archived bytes")
    monkeypatch.setattr(ps,"run_export_full",lambda *a,**k:pytest.fail("reader on committed"))
    restored=pb.resume_batch("test",context=context)
    assert restored["exit_code"]==5 and restored["items"][0]["snapshot_id"]==result["items"][0]["snapshot_id"]
