"""Real CLI/Python3 -> frozen input -> MPXJ Python3.9/cache -> typed archive."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from mofs_index.db import connect_durable
from mofs_index.plan import query as q, writer as w
from plan_receipt import validate_single_receipt

pytestmark = pytest.mark.mpp_fixtures
SKILL = Path(__file__).resolve().parents[1]


@pytest.fixture
def cli_case(tmp_path):
    # Inherited by both CLI and every reader subprocess; no client module import,
    # credential loading or Python socket connection can silently bypass this.
    guard = tmp_path/"import-guard"
    guard.mkdir()
    (guard/"sitecustomize.py").write_text('''import sys, socket, importlib.abc
class DenyConfluence(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('conf_client', 'pipeline'):
            raise NotImplementedError('network/client import forbidden on save: '+fullname)
sys.meta_path.insert(0, DenyConfluence())
def denied(*a, **k):
    raise AssertionError('network forbidden on save')
socket.socket.connect = denied
socket.create_connection = denied
''')
    env = dict(os.environ)
    env.pop("CONFLUENCE_TOKEN", None)
    env["PYTHONPATH"] = str(guard) + os.pathsep + env.get("PYTHONPATH", "")
    env["MPXJ_PYTHON"] = "/usr/bin/python3.9"
    args = ["/usr/bin/python3", str(SKILL/"scripts/cli.py"), "--db", str(tmp_path/"state/index.sqlite"),
            "--workvault", str(tmp_path/"WorkVault"), "--cache-dir", str(tmp_path/"cache")]
    def run(path, **params):
        command = [*args, "save", "--mpp", str(path), "--project-slug", "acceptance-project"]
        for key, value in params.items():
            command.extend(["--"+key.replace("_", "-"), str(value)])
        proc = subprocess.run(command, capture_output=True, text=True, env=env, timeout=180)
        receipt = json.loads(proc.stdout)  # whole stdout must be one JSON document
        validate_single_receipt(receipt)
        assert receipt["exit_code"] == proc.returncode
        assert receipt["published"] is False and receipt["page_id"] is None and receipt["page_url"] is None
        assert receipt["external_effect"] == "none"
        assert len(proc.stdout) < 20000
        assert 'normalized_data' not in receipt and 'tasks' not in receipt and 'Authorization' not in proc.stdout
        return receipt, proc, command
    return tmp_path, run


def _metrics(conn, operation_id):
    return [json.loads(e["detail"]) for e in q.get_operation_events(conn, operation_id) if e["event_kind"] == "save_metrics"][-1]


def _assert_readback(root, receipt):
    conn = connect_durable(root/"state/index.sqlite")
    try:
        w.verify_snapshot(conn, receipt["snapshot_id"])
        snapshot = q.get_snapshot(conn, receipt["snapshot_id"])
        item = q.get_import_item(conn, receipt["item_id"])
        source = Path(w.verify_artifact(conn, snapshot["source_artifact_id"], receipt["source"]["sha256"]))
        assert hashlib.sha256(source.read_bytes()).hexdigest() == receipt["source"]["sha256"]
        export = q.find_artifact_by_hash(conn, snapshot["normalized_data_sha256"])
        assert Path(w.verify_artifact(conn, export["artifact_id"])).read_bytes() == snapshot["source_json"].encode()
        mirrored = root/"WorkVault/_plan-receipts"/receipt["operation_id"]/"save.json"
        assert json.loads(mirrored.read_text()) == receipt
        assert Path(item["frozen_locator"]).is_file()
        for table in ("plan_baseline_selection", "plan_snapshot_selection", "plan_publication", "plan_publication_snapshot"):
            assert conn.execute("SELECT * FROM " + table).fetchall() == []
        metrics = _metrics(conn, receipt["operation_id"])
        normalized = json.loads(snapshot["source_json"])
        metrics["versions"] = {"reader":normalized["source_identity"]["reader"],
            "mpxj":normalized["source_identity"]["mpxj"], "jpype":normalized["source_identity"]["jpype"],
            "export":normalized["export_version"], "normalization":normalized["normalization"],
            "resolved_timezone":normalized["resolved_timezone"]}
        return metrics
    finally:
        conn.close()


@pytest.mark.parametrize("case,tasks,deps", [("E",78,84), ("F",86,93)])
def test_real_cli_cold_warm_save(cli_case, request, case, tasks, deps):
    root, run = cli_case
    manifest = json.loads((SKILL/"tests/fixtures/real/manifest.json").read_text())
    fixture = next(row for row in manifest["fixtures"] if row["id"] == case)
    source = root/(case+".mpp")
    shutil.copy2(SKILL/"tests/fixtures/real"/fixture["path"], source)
    cold, proc, command = run(source, source_version_date="2026-11-15")
    assert proc.returncode == 0, (cold, proc.stderr)
    assert (cold["task_count"], cold["dependency_count"]) == (tasks, deps)
    assert cold["display_task_count"] == tasks-1
    assert cold["source"]["sha256"] == fixture["sha256"]
    cold_metrics = _assert_readback(root, cold)
    assert cold_metrics["counters"]["MPXJ_read"] == 1
    assert cold_metrics["counters"]["cache_miss"] == 1
    renamed = source.with_name(case+"-renamed.mpp")
    source.rename(renamed)
    warm, proc2, command2 = run(renamed)
    assert proc2.returncode == 0, (warm, proc2.stderr)
    assert warm["status"] == "unchanged" and warm["snapshot_id"] == cold["snapshot_id"]
    assert warm["item_id"] != cold["item_id"]
    warm_metrics = _assert_readback(root, warm)
    assert warm_metrics["counters"]["MPXJ_read"] == 0
    assert warm_metrics["counters"]["cache_hit"] == 1
    evidence = {"case":case, "cold":{"command":command,"rc":proc.returncode,"receipt":cold, **cold_metrics},
                "warm":{"command":command2,"rc":proc2.returncode,"receipt":warm, **warm_metrics},
                "client_import":"forbidden", "python_socket":"forbidden", "baseline_before":[],"baseline_after":[],
                "publication_rows":0, "POST":0,"PUT":0}
    report_root = getattr(request.config, "_acceptance_root", root)/"reports"
    report_root.mkdir(exist_ok=True)
    (report_root/("save-e2e-"+case+".json")).write_text(json.dumps(evidence, ensure_ascii=False, indent=2))


def test_cli_cache_corruption_rebuilds_once(cli_case):
    root, run = cli_case
    source = root/"source.mpp"
    shutil.copy2(SKILL/"tests/fixtures/synthetic/relations-all-types.mpp", source)
    first, proc, _ = run(source)
    assert proc.returncode == 0, first
    entry = next((root/"cache/parse-v1").glob("*.json"))
    entry.write_text('{"truncated":')
    second, proc2, _ = run(source)
    assert proc2.returncode == 0 and second["status"] == "unchanged", second
    assert second["snapshot_id"] == first["snapshot_id"]
    counters = _assert_readback(root, second)["counters"]
    assert counters["MPXJ_read"] == 1 and counters["cache_miss"] == 1


def test_cli_corrupt_mpp_is_failed_not_empty_plan(cli_case):
    root, run = cli_case
    source = root/"broken.mpp"
    source.write_bytes(b"corrupt MS Project input")
    receipt, proc, _ = run(source)
    assert proc.returncode == 5 and receipt["snapshot_id"] is None, (receipt, proc.stderr)
    assert receipt["error"]["code"] == "mpp_unreadable"
    assert receipt["task_count"] is None
    conn = connect_durable(root/"state/index.sqlite")
    try:
        item = q.get_import_item(conn, receipt["item_id"])
        assert Path(item["frozen_locator"]).read_bytes() == source.read_bytes()
        assert conn.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0] == 0
    finally:
        conn.close()


def test_cli_zip_intake_inside_save(cli_case):
    import zipfile
    root, run = cli_case
    source = root/"renamed-container.bin"
    with zipfile.ZipFile(source, "w") as z:
        z.write(SKILL/"tests/fixtures/synthetic/relations-all-types.mpp", "nested/plan.mpp")
    result, proc, _ = run(source)
    assert proc.returncode == 0, (result, proc.stderr)
    conn = connect_durable(root/"state/index.sqlite")
    try:
        item = q.get_import_item(conn, result["item_id"])
        assert item["zip_member"] == "nested/plan.mpp"
        assert item["container_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert Path(item["container_locator"]).read_bytes() == source.read_bytes()
    finally:
        conn.close()
    _assert_readback(root, result)


def test_cli_zip_multiple_candidates_retains_list(cli_case):
    import zipfile
    root, run = cli_case
    source = root/"two.zip"
    with zipfile.ZipFile(source,"w") as z:
        z.writestr("first.mpp", b"first")
        z.writestr("second.mpp", b"second")
    receipt, proc, _ = run(source)
    assert proc.returncode == 5 and receipt["error"]["code"] == "multiple_mpp_candidates"
    assert receipt["snapshot_id"] is None and receipt["task_count"] is None
    diagnostic = root/"WorkVault/_plan-receipts"/receipt["operation_id"]/"input-error.json"
    assert json.loads(diagnostic.read_text())["candidates"] == ["first.mpp", "second.mpp"]
