"""Pytest fixtures for edit-plan-confluence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = Path(__file__).parent / "fixtures"
MOFS_INDEX_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(MOFS_INDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_INDEX_ROOT))


@pytest.fixture
def skill_root() -> Path:
    return SKILL_ROOT


@pytest.fixture
def fixtures_dir(tmp_path) -> Path:
    target = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, target)
    return target


@pytest.fixture
def tasks_csv(fixtures_dir: Path) -> Path:
    return fixtures_dir / "ab_080926_пункт12__tasks.csv"


@pytest.fixture
def resources_csv(fixtures_dir: Path) -> Path:
    return fixtures_dir / "ab_080926_пункт12__resources.csv"


@pytest.fixture
def assignments_csv(fixtures_dir: Path) -> Path:
    return fixtures_dir / "ab_080926_пункт12__assignments.csv"


@pytest.fixture
def mpp_fixture(fixtures_dir: Path) -> Path:
    return fixtures_dir / "ab_080926_пункт12.mpp"


@pytest.fixture
def empty_template(skill_root: Path) -> dict:
    return json.loads((skill_root / "references" / "empty-gantt-template.json").read_text(encoding="utf-8"))


@pytest.fixture
def gantt_test_template(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "gantt-test-template.json").read_text(encoding="utf-8"))


@pytest.fixture
def isolated_plan_db(tmp_path, monkeypatch):
    """Изолированная plan_*-БД + WorkVault-каталог для тестов, задействующих
    ``plan_archive``/``pipeline`` preflight archive (R-039: изолированные
    fixtures, не боевая БД/боевой Confluence)."""
    from mofs_index.db import connect as mofs_connect, initialize
    from mofs_index.plan.migrate import ensure_plan_schema

    db_path = tmp_path / "plan_index.sqlite"

    def fake_connect_durable(path=None):
        c = mofs_connect(db_path, durable=True)
        initialize(c)
        ensure_plan_schema(c)
        return c

    monkeypatch.setattr("mofs_index.db.connect_durable", fake_connect_durable)
    monkeypatch.setattr("plan_archive.connect_durable", fake_connect_durable)

    wv = tmp_path / "WorkVault"
    monkeypatch.setattr("plan_archive.get_workvault_path", lambda: wv)
    monkeypatch.setattr("plan_receipt.get_workvault_path", lambda: wv)
    return db_path

# Acceptance support stays in pytest; there is no separate runner/CLI.
import hashlib
import os
import platform
import shutil
import socket
import sqlite3
from datetime import datetime, timezone

GROUPS = ("unit", "archive_integration", "mpp_fixtures", "confluence_live")
STAGE01_REQUIRED = {
    "test_pipeline.py::test_attachment_failure_blocks_put",
    "test_pipeline.py::test_storage_readback_rejects_corruption",
    "test_pipeline.py::test_actual_current_attachment_changed",
    "test_pipeline.py::test_success_records_get_observation_and_actual_id",
    "test_child_page.py::test_child_rejects_attachment_failure",
    "test_child_page.py::test_child_storage_corruption",
    "test_child_page.py::test_resume_rechecks_actual_bytes",
    "test_gantt_attachment.py::test_download_requires_exact_metadata",
    "test_plan_verify.py::test_storage_negative_cases",
    "test_plan_reconcile.py::test_reconcile_single_candidate_does_not_confirm_operation",
}


def pytest_addoption(parser):
    parser.addoption("--acceptance-stage", default=None)
    parser.addoption("--test-root", default=None)


def _validate_test_root(path):
    resolved = Path(path).expanduser().resolve()
    protected = (Path.home() / "WorkVault", MOFS_INDEX_ROOT / "state", Path.home() / ".hermes")
    if any(resolved == p.resolve() or p.resolve() in resolved.parents or resolved in p.resolve().parents
           for p in protected):
        raise pytest.UsageError(f"production test root forbidden: {resolved}")
    return resolved


def pytest_configure(config):
    stage = config.getoption("--acceptance-stage")
    if stage and stage != "01":
        raise pytest.UsageError("this acceptance contour currently implements stage 01 only")
    root = config.getoption("--test-root")
    if stage and not root:
        raise pytest.UsageError("--test-root required for acceptance")
    config._acceptance_results = []
    config._acceptance_counters = {"MPXJ_read": 0, "cache_hit": 0, "cache_miss": 0,
                                   "attachment_POST_fake": 0, "page_POST_fake": 0, "page_PUT_fake": 0,
                                   "live_POST": 0, "live_PUT": 0}
    if root:
        root = _validate_test_root(root)
        for part in ("state", "WorkVault", "cache", "fixtures", "reports"):
            (root / part).mkdir(parents=True, exist_ok=True)
        config._acceptance_root = root
        # tmp_path and subprocess TMPDIR are confined to the same run.
        if not config.option.basetemp:
            config.option.basetemp = str(root / "pytest-tmp")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    archive = {"test_plan_archive.py", "test_plan_history.py", "test_plan_save.py", "test_plan_reconcile.py"}
    real_reader = {"test_build_plan_from_mpp_offline", "test_calendar_from_mpp_fixture", "test_cli_convert_offline"}
    for item in items:
        if any(item.get_closest_marker(group) for group in GROUPS):
            continue
        if item.get_closest_marker("live"):
            group = "confluence_live"
        elif item.originalname in real_reader:
            group = "mpp_fixtures"
        elif item.path.name in archive:
            group = "archive_integration"
        else:
            group = "unit"
        item.add_marker(getattr(pytest.mark, group))


def pytest_collection_finish(session):
    if session.config.getoption("--acceptance-stage"):
        selected = {item.nodeid.split("[")[0].split("/")[-1] for item in session.items}
        missing = sorted(STAGE01_REQUIRED - selected)
        if missing:
            raise pytest.UsageError("mandatory stage-01 tests not selected: " + ", ".join(missing))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or report.failed or report.skipped:
        item.config._acceptance_results.append({"test_id": report.nodeid, "phase": report.when,
                                               "status": report.outcome, "duration": report.duration})


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    root = getattr(config, "_acceptance_root", None)
    if root is None:
        return
    results = config._acceptance_results
    good = exitstatus == 0 and bool(session.items) and bool(results) and all(r["status"] == "passed" for r in results)
    files = sorted(list(SCRIPTS.glob("*.py")) + list((SKILL_ROOT / "tests").glob("*.py"))
                   + list((MOFS_INDEX_ROOT / "mofs_index/plan").glob("*.py"))
                   + list((MOFS_INDEX_ROOT / "tests/plan").glob("*.py"))
                   + [SKILL_ROOT / "tests/pytest.ini"])
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    tree_hash = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    schema = Path.home() / "WorkVault/Registries/EcosystemConfig.schema.json"
    if any(item.get_closest_marker("mpp_fixtures") for item in session.items):
        # Subprocess reader instrumentation belongs to later stages. Do not
        # report an unmeasured real-reader count as zero.
        config._acceptance_counters["MPXJ_read"] = None
    report = {"stage": "01", "gate": "passed" if good else "failed", "scope": "S tests only; external checks required",
              "exit_code": int(exitstatus), "command": [sys.executable, "-m", "pytest", *config.invocation_params.args],
              "environment": {"python": sys.executable, "version": platform.python_version(),
                              "test_root": str(root), "PYTHONPATH": os.environ.get("PYTHONPATH")},
              "source_tree_sha256": tree_hash, "source_files": hashes,
              "config_contract_sha256": hashlib.sha256(schema.read_bytes()).hexdigest() if schema.exists() else None,
              "tests": results, "selected": len(session.items), "counters": config._acceptance_counters,
              "covered_requirements": ["§20/AC-10", "§20/AC-11", "parts of §20/AC-12,13,27"],
              "limitations": ["full new pipeline and verified_v1 are outside stage 01", "no live Confluence"],
              "generated_at": datetime.now(timezone.utc).isoformat()}
    (root / "reports/stage-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (root / "reports/stage-report.md").write_text(
        f"# Этап 01\n\nGate S: {report['gate']}; rc={exitstatus}; выбрано={len(session.items)}.\n\n"
        f"Проверенное дерево: `{tree_hash}`.\n\nВнешний MofsIndex проверяется отдельным процессом.\n")


@pytest.fixture(autouse=True)
def acceptance_isolation(tmp_path, monkeypatch, request):
    """Default-deny network and production SQLite, explicit local dependencies."""
    import env
    import plan_archive
    import plan_receipt
    import plan_save
    import mofs_index.db as db
    from mofs_index.plan.migrate import ensure_plan_schema
    root = getattr(request.config, "_acceptance_root", tmp_path)
    wv = tmp_path / "WorkVault"
    cache = tmp_path / "cache"
    for p in (wv, cache):
        p.mkdir(exist_ok=True)
    monkeypatch.setenv("WORKVAULT_PATH", str(wv))
    monkeypatch.setenv("TMPDIR", str(cache))
    monkeypatch.setattr(env, "get_workvault_path", lambda: wv)
    monkeypatch.setattr(plan_archive, "get_workvault_path", lambda: wv)
    monkeypatch.setattr(plan_receipt, "get_workvault_path", lambda: wv)
    db_path = tmp_path / "state/index.sqlite"
    monkeypatch.setattr(plan_archive, "get_plan_db_path", lambda: db_path)
    monkeypatch.setattr(plan_save, "get_plan_db_path", lambda: db_path)
    original_connect = sqlite3.connect

    def guarded_sqlite(path, *args, **kwargs):
        value = str(path)
        if value != ":memory:":
            candidate = Path(value.removeprefix("file:").split("?")[0]).resolve()
            if root.resolve() not in candidate.parents:
                raise AssertionError(f"SQLite outside test root: {candidate}")
        return original_connect(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded_sqlite)

    def local_durable(path=None):
        c = db.connect(path or db_path, durable=True)
        db.initialize(c)
        ensure_plan_schema(c)
        return c

    monkeypatch.setattr(db, "connect_durable", local_durable)
    monkeypatch.setattr(plan_archive, "connect_durable", local_durable)
    monkeypatch.setattr(plan_save, "connect_durable", local_durable)

    if not request.node.get_closest_marker("confluence_live"):
        def no_network(*args, **kwargs):
            raise AssertionError("network forbidden in isolated acceptance")
        monkeypatch.setattr(socket.socket, "connect", no_network)
        monkeypatch.setattr(socket, "create_connection", no_network)
    if request.node.get_closest_marker("archive_integration"):
        def no_client(*args, **kwargs):
            raise AssertionError("ConfluenceClient forbidden for archive scenario")
        monkeypatch.setattr("conf_client.ConfluenceClient.__init__", no_client)


@pytest.fixture
def fake_confluence(request):
    from copy import deepcopy
    from gantt_attachment import AttachmentInfo
    from macro import find_macro

    class FakeConfluence:
        def __init__(self):
            self.page = {"id": "test-page", "title": "Test", "space": {"key": "TEST"},
                         "version": {"number": 3}, "body": {"storage": {"value": "<p>Соседний блок</p>"}}}
            self.child = None
            self.uploaded = None
            self.blobs = {}
            self.calls = []
            self.mutate_get = None
            self.download_error = None
            self.conflicts = 0
            self.foreign_storage = None

        def get_page(self, page_id, expand=None):
            self.calls.append(("GET", str(page_id)))
            page = deepcopy(self.child if str(page_id) == "test-child" else self.page)
            if self.mutate_get:
                return self.mutate_get(page)
            return page

        def put_page(self, page_id, title, storage, version):
            self.calls.append(("PUT", str(page_id)))
            request.config._acceptance_counters["page_PUT_fake"] += 1
            if self.conflicts:
                from conf_client import ConfluenceError
                self.conflicts -= 1
                self.page["version"]["number"] += 1
                self.page["body"]["storage"]["value"] += "<p>Правка соседа</p>"
                raise ConfluenceError(409, "simulated conflict")
            assert version == self.page["version"]["number"] + 1
            self.page["version"]["number"] = version
            self.page["body"]["storage"]["value"] = storage
            return {}  # response is deliberately not evidence

        def create_page(self, title, space_key, storage, parent_id):
            self.calls.append(("POST_PAGE", str(parent_id)))
            request.config._acceptance_counters["page_POST_fake"] += 1
            self.child = {"id": "test-child", "title": title, "version": {"number": 1},
                          "body": {"storage": {"value": storage}}}
            return deepcopy(self.child)

        def list_attachments(self, page_id):
            if self.uploaded is None:
                return []
            return [{"id": self.uploaded.attach_id, "title": self.uploaded.filename,
                     "version": {"number": self.uploaded.version}}]

        def upload(self, client, page_id, filename, gantt, existing):
            self.calls.append(("POST_ATTACHMENT", str(page_id)))
            request.config._acceptance_counters["attachment_POST_fake"] += 1
            version = self.uploaded.version + 1 if self.uploaded else 1
            self.uploaded = AttachmentInfo("actual-attachment-id", filename, version, filename)
            self.blobs[(filename, version)] = json.dumps(gantt, ensure_ascii=False).encode()
            return deepcopy(self.uploaded)

        def download_attachment_version(self, page_id, attachment_id, filename, version):
            self.calls.append(("GET_ATTACHMENT", version))
            assert attachment_id == "actual-attachment-id"
            if self.download_error:
                raise self.download_error
            return self.blobs[(filename, version)]

        def download_attachment(self, page_id, filename, version=None):
            return self.download_attachment_version(page_id, "actual-attachment-id", filename, version)

    return FakeConfluence()


@pytest.fixture
def prepared_input(tmp_path, tasks_csv, assignments_csv, resources_csv, monkeypatch, fake_confluence):
    from types import SimpleNamespace
    import pipeline
    source = tmp_path / "input.mpp"
    source.write_bytes(b"synthetic MPP placeholder; reader is stubbed in publication unit tests")
    paths = SimpleNamespace(tasks_csv=tasks_csv, assignments_csv=assignments_csv,
                            resources_csv=resources_csv, mpp_path=source)
    monkeypatch.setattr(pipeline, "build_plan_from_mpp", lambda *a, **k: pipeline.build_plan_empty("Plan"))
    monkeypatch.setattr(pipeline, "export_csv", lambda *a, **k: paths)
    monkeypatch.setattr(pipeline, "upload_gantt_json", fake_confluence.upload)
    return source
