"""Stage 05 typed batch lifecycle on isolated databases; no skill-side SQL."""
import hashlib
import json
from pathlib import Path

import pytest

from mofs_index.db import connect_durable
from mofs_index.plan.migrate import ensure_plan_schema
from mofs_index.plan import query as q, writer as w


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",", ":"))


@pytest.fixture
def batch_case(tmp_path):
    c=connect_durable(tmp_path/"index.sqlite"); ensure_plan_schema(c)
    manifest={"schema_version":1,"on_error":"continue","items":[{"item_id":"e","path":"/e.mpp"},{"item_id":"f","path":"/f.mpp"}]}
    content=canonical(manifest)
    spec=w.ImportBatchSpec("batch",1,content,hashlib.sha256(content.encode()).hexdigest(),"manifest","{}")
    entries=tuple(w.BatchItemSpec(item["item_id"],item["path"],"{}") for item in manifest["items"])
    yield c,spec,entries
    c.close()


def test_atomic_creation_idempotence_and_external_ids_scoped_to_batch(batch_case):
    from dataclasses import replace
    c,spec,entries=batch_case
    assert w.create_batch_with_items(c,spec,entries) is True
    rows=q.get_batch_items(c,"batch")
    assert [json.loads(r["transport_json"])["manifest_item_id"] for r in rows] == ["e","f"]
    assert [r["ordinal"] for r in rows] == [1,2]
    assert w.create_batch_with_items(c,spec,entries) is False
    assert len(q.get_batch_items(c,"batch")) == 2
    assert w.create_batch_with_items(c,replace(spec,batch_id="second"),entries)
    assert len({r["item_id"] for b in ("batch","second") for r in q.get_batch_items(c,b)}) == 4
    with pytest.raises(w.PlanWriterError,match="batch_manifest_conflict"):
        w.create_batch_with_items(c,replace(spec,context_json='{"changed":true}'),entries)
    assert q.read_batch_state(c,"batch")["batch"]["inputs_frozen_at"] is None


def test_creation_rolls_back_all_records_on_intermediate_sql_failure(batch_case):
    c,spec,entries=batch_case
    class FailingConnection:
        def __getattr__(self,name): return getattr(c,name)
        def execute(self,sql,params=()):
            if sql.startswith("INSERT INTO plan_import_item") and params[3] == 2:
                raise RuntimeError("test boundary after second operation")
            return c.execute(sql,params)
    with pytest.raises(RuntimeError):
        w.create_batch_with_items(FailingConnection(),spec,entries)
    for table in ("plan_import_batch","plan_import_item","plan_operation"):
        assert c.execute("SELECT * FROM "+table).fetchall() == []


def test_freeze_barrier_blocks_processing_until_all_bytes_or_errors(batch_case,tmp_path):
    c,spec,entries=batch_case
    w.create_batch_with_items(c,spec,entries)
    rows=q.get_batch_items(c,"batch")
    with pytest.raises(w.PlanWriterError,match="inputs_not_frozen"):
        w.start_batch_item(c,rows[0]["item_id"])
    with pytest.raises(w.PlanWriterError,match="inputs_not_frozen"):
        w.finalize_batch_freeze(c,"batch")
    source=tmp_path/"source.mpp"; source.write_bytes(b"frozen")
    w.freeze_import_item(c,rows[0]["item_id"],frozen_locator=str(source),source_mpp_sha256=hashlib.sha256(b"frozen").hexdigest(),
                         size_bytes=6,frozen_at="2026-11-16T10:00:00Z")
    with pytest.raises(w.PlanWriterError,match="inputs_not_frozen"):
        w.finalize_batch_freeze(c,"batch")
    attempt=w.begin_operation_attempt(c,rows[1]["operation_id"],rows[1]["item_id"])
    w.fail_import_item(c,rows[1]["item_id"],attempt,"input_missing",retryable=False)
    when=w.finalize_batch_freeze(c,"batch")
    assert w.finalize_batch_freeze(c,"batch") == when
    processing=w.start_batch_item(c,rows[0]["item_id"])
    assert q.get_attempt(c,processing)["item_id"] == rows[0]["item_id"]
    with pytest.raises(w.PlanWriterError,match="input_freeze_failed"):
        w.start_batch_item(c,rows[1]["item_id"])
    result={"status":"failed","error":{"code":"mpp_read_timeout","retryable":True},"warnings":[]}
    w.finish_batch_item(c,rows[0]["item_id"],processing,canonical(result))
    assert q.get_batch_item_result(c,rows[0]["operation_id"]) == result
    w.finish_import_batch(c,"batch",status="infrastructure_stopped",stop_reason=canonical(result["error"]))
    assert q.get_import_batch(c,"batch")["completed_at"]
    assert not c.execute("PRAGMA foreign_key_check").fetchall()
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
