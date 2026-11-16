"""Stage 04 save orchestration, immutable context, receipts and recovery."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

import plan_save as ps
from plan_context import PlanContext
from plan_operation import ImportOperation, begin_import, freeze_operation_input
from plan_reconcile import saved_operation_receipt
from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w
from mofs_index.plan.migrate import ensure_plan_schema

pytestmark = pytest.mark.archive_integration
FIXTURES = Path(__file__).parent / "fixtures/synthetic"


@pytest.fixture
def save_case(tmp_path, monkeypatch):
    # No credential lookup/client construction allowed, even in in-process tests.
    import env
    import conf_client
    def forbidden(*a, **k):
        raise NotImplementedError("Confluence is forbidden on save")
    monkeypatch.setattr(conf_client.ConfluenceClient, "__init__", forbidden)
    monkeypatch.setattr(env, "load_confluence_env", forbidden)
    monkeypatch.delenv("CONFLUENCE_TOKEN", raising=False)
    context = PlanContext.resolve(db=tmp_path/"state/index.sqlite", workvault=tmp_path/"WorkVault", cache_dir=tmp_path/"cache")
    source = tmp_path/"first.mpp"
    shutil.copy2(FIXTURES/"relations-all-types.mpp", source)
    export = json.loads((FIXTURES/"relations-all-types.json").read_text())
    return context, source, export


def _conn(context):
    c = connect_durable(context.db)
    ensure_plan_schema(c)
    return c


def _save(case, **kwargs):
    context, source, export = case
    return ps.save_snapshot(source, context=context, export=export, **{"project_slug":"test-project", **kwargs})


def _protected_rows(conn):
    # Test-only exact SQL observation, product writes exclusively typed API.
    return {table:conn.execute("SELECT * FROM " + table + " ORDER BY 1").fetchall() for table in
            ("plan_baseline_selection", "plan_snapshot_selection", "plan_publication", "plan_publication_snapshot")}


def _frozen_operation(context, source, *, project_slug="test-project", **request):
    c = _conn(context)
    try:
        op = begin_import(c, source, context={**context.snapshot(), "save":{"project_slug":project_slug, **request}})
        frozen = freeze_operation_input(c, op)
        return op, frozen
    finally:
        c.close()


def test_save_creates_snapshot_without_page_id(save_case):
    context, source, export = save_case
    result = _save(save_case)
    assert result.exit_code == 0, result.receipt
    assert result.status == "saved_with_warnings"
    assert (result.task_count, result.display_task_count, result.dependency_count) == (6, 5, 4)
    assert result.published is False and result.page_id is None and result.page_url is None
    c = _conn(context)
    try:
        assert all(not rows for rows in _protected_rows(c).values())
        w.verify_snapshot(c, result.snapshot_id)
        source_row = q.get_artifact(c, result.mpp_artifact_id)
        assert Path(source_row["path"]).read_bytes() == source.read_bytes()
        snapshot = q.get_snapshot(c, result.snapshot_id)
        archived = Path(q.get_artifact(c, result.export_artifact_id)["path"]).read_bytes()
        assert archived == snapshot["source_json"].encode()
        assert hashlib.sha256(archived).hexdigest() == snapshot["normalized_data_sha256"]
        assert saved_operation_receipt(c, result.operation_id) == result.to_dict()
    finally:
        c.close()


def test_save_deduplicates_and_preserves_each_arrival(save_case):
    context, source, export = save_case
    first = _save(save_case)
    renamed = source.with_name("renamed.mpp")
    source.rename(renamed)
    second = ps.save_snapshot(renamed, context=context, project_slug="test-project", export=export)
    assert second.status == "unchanged", second.receipt
    assert first.snapshot_id == second.snapshot_id
    assert first.lineage_id == second.lineage_id
    assert first.operation_id != second.operation_id and first.item_id != second.item_id
    c = _conn(context)
    try:
        assert c.execute("SELECT count(*) FROM plan_import_item").fetchone()[0] == 2
        assert c.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0] == 1
    finally:
        c.close()


def test_save_preserves_populated_baseline_and_publication_rows(save_case):
    context, *_ = save_case
    first = _save(save_case)
    c = _conn(context)
    try:
        w.select_snapshot_baseline(c, first.lineage_id, first.snapshot_id, is_explicit=True, basis="acceptance baseline")
        w.select_plan_baseline(c, first.plan_id, first.snapshot_id, 0, is_explicit=True, basis="acceptance baseline")
        w.record_publication(c, w.PublicationSpec(first.plan_id, "test-local", "existing-attachment", 1,
            lineage_id=first.lineage_id, artifact_id=first.mpp_artifact_id, page_id="local-only",
            raw_sha256=first.mpp_sha256))
        before = _protected_rows(c)
    finally:
        c.close()
    result = _save(save_case, timezone_hint="Europe/Moscow")
    assert result.exit_code == 0 and result.snapshot_id != first.snapshot_id
    c = _conn(context)
    try:
        assert _protected_rows(c) == before
    finally:
        c.close()


def test_save_requires_project_slug_preserves_input(save_case):
    context, *_ = save_case
    result = _save(save_case, project_slug=None)
    assert result.exit_code == 2 and result.error["code"] == "project_slug_required"
    c = _conn(context)
    try:
        item = q.get_import_item(c, result.item_id)
        assert Path(item["frozen_locator"]).is_file()
        assert item["snapshot_id"] is None and item["plan_id"] is None
        assert (context.workvault/"_plan-receipts"/result.operation_id/"prepared.json").is_file()
    finally:
        c.close()


def test_save_with_page_id_reuses_existing_lineage(save_case):
    from plan_archive import resolve_plan_binding
    context, *_ = save_case
    c = _conn(context)
    try:
        binding = resolve_plan_binding("900001", "test-project", conn=c)
    finally:
        c.close()
    result = _save(save_case, page_id="900001", project_slug=None)
    assert result.exit_code == 0, result.receipt
    assert result.lineage_id == binding["lineage_id"]
    assert result.page_id is None and result.page_url is None
    conflict = _save(save_case, page_id="900001", project_slug="foreign")
    assert conflict.exit_code == 4 and conflict.snapshot_id is None


def test_save_explicit_lineage_and_version_date(save_case):
    context, *_ = save_case
    first = _save(save_case)
    result = _save(save_case, lineage_id=first.lineage_id, source_version_date="2026-11-15")
    assert result.status == "unchanged"
    c = _conn(context)
    try:
        item = q.get_import_item(c, result.item_id)
        assert item["source_version_date"] == "2026-11-15"
        assert item["source_version_basis"] == "explicit_user"
        assert item["received_at"] != item["source_version_date"]
    finally:
        c.close()
    assert _save(save_case, lineage_id="foreign").exit_code == 4


@pytest.mark.parametrize("field,value", [("source_version_date", "2026-02-30"), ("source_version_date", "20261115"), ("timezone_hint", "Not/AZone")])
def test_invalid_arguments_before_intake(save_case, field, value):
    result = _save(save_case, **{field:value})
    assert result.exit_code == 2
    assert result.operation_id is None and result.item_id is None


def test_save_missing_input_is_failed_arrival(save_case):
    context, source, export = save_case
    source.unlink()
    result = _save(save_case)
    assert result.exit_code == 5 and result.error["code"] == "input_missing"
    assert result.item_id and result.operation_id and result.snapshot_id is None


@pytest.mark.parametrize("kind", ["no_tasks", "bad_count", "wrong_source", "legacy_export", "invalid_schema"])
def test_unusable_snapshot_is_not_success(save_case, kind):
    context, source, export = save_case
    if kind == "no_tasks":
        export["tasks"] = []; export["collections"]["tasks"]["count"] = 0
    elif kind == "bad_count":
        export["collections"]["tasks"]["count"] += 1
    elif kind == "wrong_source":
        export["provenance"]["sha256"] = "a"*64
    elif kind == "invalid_schema":
        del export["tasks"][0]["task_mode"]
    else:
        export.pop("export_version")
    result = _save(save_case)
    assert result.exit_code in (4,5) and result.snapshot_id is None
    assert result.verification["archive"] != "verified"
    if kind == "invalid_schema":
        assert result.error["code"] == "invalid_snapshot"
    c = _conn(context)
    try:
        assert q.get_import_item(c, result.item_id)["frozen_locator"]
        assert c.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0] == 0
    finally:
        c.close()


def test_quality_warnings_do_not_block_archive(save_case):
    context, source, export = save_case
    export["diagnose_graph"].update(has_cycle=True, multiple_roots=True, self_references=["d1"], dangling_dependencies=["d2"], external_records=["external"])
    export["collections"]["resources"].update(status="unsupported", reason="fixture")
    result = _save(save_case)
    assert result.status == "saved_with_warnings" and result.verification["archive"] == "verified"
    assert {"timezone_unknown","graph_has_cycle","graph_self_references","graph_dangling_dependencies","graph_multiple_roots","collection_resources_unsupported"} <= {w["code"] for w in result.warnings}
    assert result.verification["schedule"]["status"] == "not_verified"


def test_frozen_input_never_refreezes_or_opens_original(save_case, monkeypatch):
    context, source, export = save_case
    op, frozen = _frozen_operation(context, source)
    source.unlink()
    monkeypatch.setattr(ps, "freeze_operation_input", lambda *a, **k: pytest.fail("second freeze"))
    result = ps.save_frozen_input(frozen, sha256=frozen.sha256, context=context, operation=op, export=export)
    assert result.exit_code == 0, result.receipt
    assert result.snapshot_id
    assert ps.save_frozen_input(frozen, sha256="b"*64, context=context, operation=op).exit_code == 4
    different = replace(context, cache_dir=context.cache_dir/"changed")
    assert ps.save_frozen_input(frozen, sha256=frozen.sha256, context=different, operation=op).exit_code == 4


def test_recovery_after_commit_before_readback_no_reader(save_case, monkeypatch):
    context, source, export = save_case
    op, frozen = _frozen_operation(context, source)
    real = ps.reconcile_import
    monkeypatch.setattr(ps, "reconcile_import", lambda *a, **k: (_ for _ in ()).throw(OSError("readback unavailable")))
    failed = ps.save_frozen_input(frozen, sha256=frozen.sha256, context=context, operation=op, export=export)
    assert failed.exit_code == 5 and failed.snapshot_id
    source.unlink()
    shutil.rmtree(context.cache_dir, ignore_errors=True)
    monkeypatch.setattr(ps, "reconcile_import", real)
    monkeypatch.setattr(ps, "select_mpxj_python", lambda *a, **k: pytest.fail("runtime on committed input"))
    c = _conn(context)
    try:
        restored_context = PlanContext.from_snapshot(json.loads(q.get_operation(c, op.operation_id)["context_json"]))
    finally:
        c.close()
    restored = ps.save_frozen_input(frozen, sha256=frozen.sha256, context=restored_context, operation=op)
    assert restored.exit_code == 0 and restored.snapshot_id == failed.snapshot_id
    assert restored.counters["MPXJ_read"] == 0


def test_receipt_mirror_failure_preserves_commit_and_recovers(save_case, monkeypatch):
    import plan_receipt
    context, source, export = save_case
    op, frozen = _frozen_operation(context, source)
    real = plan_receipt.write_receipt
    def writer(attempt, event, payload, **kwargs):
        if event == "save":
            raise OSError("mirror unavailable")
        return real(attempt, event, payload, **kwargs)
    monkeypatch.setattr(plan_receipt, "write_receipt", writer)
    failed = ps.save_frozen_input(frozen, sha256=frozen.sha256, context=context, operation=op, export=export)
    assert failed.exit_code == 5 and failed.snapshot_id
    assert failed.error["code"] == "receipt_mirror_failed"
    assert failed.verification["archive"] == "verified"
    assert not (context.workvault/"_plan-receipts"/op.operation_id/"save.json").exists()
    c = _conn(context)
    try:
        assert saved_operation_receipt(c, op.operation_id) == failed.to_dict()
        assert any(e["event_kind"] == "save_result" and json.loads(e["detail"])["exit_code"] == 0 for e in q.get_operation_events(c, op.operation_id))
    finally:
        c.close()
    monkeypatch.setattr(plan_receipt, "write_receipt", real)
    monkeypatch.setattr(ps, "select_mpxj_python", lambda *a, **k: pytest.fail("reader on mirror recovery"))
    restored = ps.save_frozen_input(frozen, sha256=frozen.sha256, context=context, operation=op)
    assert restored.exit_code == 0 and restored.snapshot_id == failed.snapshot_id
    assert json.loads((context.workvault/"_plan-receipts"/op.operation_id/"save.json").read_text()) == restored.to_dict()


@pytest.mark.parametrize("kind", ["source", "export"])
def test_corrupt_archived_source_or_export_never_duplicate_success(save_case, kind):
    context, source, export = save_case
    first = _save(save_case)
    c = _conn(context)
    try:
        Path(q.get_artifact(c, first.export_artifact_id if kind == "export" else first.mpp_artifact_id)["path"]).write_bytes(b"corrupt artifact")
    finally:
        c.close()
    result = _save(save_case)
    assert result.exit_code == 5
    assert result.error["code"] == "artifact_hash_mismatch"


def test_reader_diagnostics_use_stderr_and_artifacts(save_case, monkeypatch, capsys, tmp_path):
    from env import MpxjRuntime
    from types import SimpleNamespace
    context, source, export = save_case
    diagnostics = context.workvault/"_plan-receipts/op/reader"
    def run(command, **kwargs):
        Path(command[command.index("--out")+1]).write_text(json.dumps(export))
        assert kwargs["timeout"] == context.settings["MPP_READ_TIMEOUT_SECONDS"]
        return SimpleNamespace(returncode=0, stdout="noisy {log} Authorization: Bearer secret-token\n", stderr="reader diagnostic\n")
    monkeypatch.setattr(ps.subprocess, "run", run)
    result = ps.run_export_full(source, context=context, diagnostics_dir=diagnostics,
                                runtime=MpxjRuntime("/fixture/python", {}))
    captured = capsys.readouterr()
    assert result == export and captured.out == ""
    assert "reader diagnostic" in captured.err and "noisy" in captured.err
    assert "secret-token" not in captured.err
    assert "secret-token" not in (diagnostics/"stdout.log").read_text()


def test_complete_save_and_unknown_timezone_sql_status(save_case):
    context, source, export = save_case
    # A contract-valid complete export, including the normal ID=0 service row.
    known_field = lambda value: {"value":value, "quality":"ok", "reason":None}
    export["project"] = {"default_calendar_key":known_field("cal:1"), "minutes_per_day":known_field("480"),
                         "minutes_per_week":known_field("2400"), "status_date":known_field("2026-11-16")}
    export["tasks"] = []
    for task_id in (0,1):
        task = {"task_key":"uid:"+str(task_id), "id":task_id, "uid":task_id, "name":"Task", "wbs":str(task_id),
                "outline_level":1, "summary":False, "milestone":False, "baseline_values":[]}
        for key in ("identity_quality", "parent_task_key", "child_task_keys", "calendar_key", "effective_calendar_key",
                    "start", "finish", "duration", "early_start", "early_finish", "late_start", "late_finish",
                    "constraint_type", "constraint_date", "task_mode", "actual_start", "actual_finish", "actual_duration",
                    "actual_work", "remaining_duration", "ignore_resource_calendar"):
            task[key] = known_field("0")
        task["segments"] = known_field([])
        export["tasks"].append(task)
    for name in ("dependencies", "external_dependencies", "resources", "assignments", "calendars"):
        export[name] = []
    export["collections"] = {name:{"status":"complete", "count":len(export[name]), "reason":None}
        for name in ("tasks", "dependencies", "external_dependencies", "resources", "assignments", "calendars")}
    export["collections"]["baseline_values"] = {"status":"complete", "count":0, "reason":None}
    export["diagnose_graph"] = {"has_service_row":True, "cycles":[], "self_references":[],
                                "dangling_dependencies":[], "external_dependencies":[], "schedule_status":"not_verified"}
    export["summary_inputs"] = {}
    known = _save(save_case, timezone_hint="Europe/Moscow")
    assert known.status == "saved" and known.warnings == [], known.receipt
    unknown = _save(save_case)
    assert unknown.status == "saved_with_warnings"
    assert {warning["code"] for warning in unknown.warnings} == {"timezone_unknown"}
    c = _conn(context)
    try:
        assert q.get_import_item(c, known.item_id)["status"] == known.status
        assert q.get_import_item(c, unknown.item_id)["status"] == unknown.status
    finally:
        c.close()


def test_missing_runtime_is_explicit_failure_before_read(save_case, monkeypatch):
    context, source, export = save_case
    def unavailable(**kwargs):
        raise RuntimeError("no MPXJ Python")
    monkeypatch.setattr(ps, "select_mpxj_python", unavailable)
    result = ps.save_snapshot(source, context=context, project_slug="test-project")
    assert result.exit_code == 5 and result.error["code"] == "mpxj_runtime_unavailable"
    assert result.item_id and result.snapshot_id is None
    assert result.counters["MPXJ_read"] == 0
