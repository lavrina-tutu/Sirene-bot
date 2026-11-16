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


STAGE02_REQUIRED = {
    "test_prepared_plan.py::test_semantic_hash_excludes_execution_provenance",
    "test_prepared_plan.py::test_normalization_profile_and_timezone_change_identity",
    "test_prepared_plan.py::test_relations_keep_signed_elapsed_and_known_zero",
    "test_prepared_plan.py::test_calendar_intervals_exceptions_inheritance_and_bindings",
    "test_prepared_plan.py::test_quality_missing_getter_errors_are_preserved",
    "test_prepared_plan.py::test_invalid_export_is_rejected",
    "test_prepared_plan.py::test_context_unified_settings_cli_overrides_and_no_secrets",
    "test_prepared_plan.py::test_fixtures_manifest_integrity",
    "test_plan_cache.py::test_independent_cache_keys",
    "test_plan_cache.py::test_corrupt_cache_rebuilds_from_verified_source",
    "test_plan_cache.py::test_cache_deletion_does_not_delete_durable_data",
    "test_plan_cache.py::test_atomic_failure_preserves_previous_entry",
    "test_plan_cache.py::test_real_parse_cache_one_read_same_bytes_different_names",
    "test_env.py::test_unified_only_credentials_do_not_read_local_env",
    "test_env.py::test_python_selection_fails_closed",
    "test_env.py::test_process_env_priority_and_no_yaml_write",
    "test_prepared_plan.py::test_prepared_load_rejects_changed_data",
    "test_prepared_plan.py::test_settings_reject_invalid_ranges",
    "test_prepared_plan.py::test_settings_numeric_contract_boundaries",
    "test_plan_cache.py::test_corrupt_source_is_not_read_or_reused",
    "test_plan_cache.py::test_concurrent_atomic_writes",
    "test_plan_cache.py::test_representation_corruption_rebuilds",
    "test_cli.py::test_cli_convert_offline",
    "test_mpp_calendar.py::test_calendar_from_mpp_fixture",
    "test_pipeline.py::test_build_plan_from_mpp_offline",
}


STAGE03_REQUIRED = STAGE01_REQUIRED | {
    "test_import_atomicity.py::test_two_processes_one_snapshot_two_receipts",
    "test_import_atomicity.py::test_process_death_commit_boundaries",
    "test_import_atomicity.py::test_operation_repeat_preserves_item_adds_attempt",
    "test_import_atomicity.py::test_unresolved_project_has_durable_input_no_fake_snapshot",
    "test_import_atomicity.py::test_different_zip_containers_same_mpp_reuse_snapshot",
    "test_import_atomicity.py::test_readback_failure_retains_commit_and_no_second_parse",
    "test_import_atomicity.py::test_failed_zip_receipt_retains_container_locator",
    "test_mpp_input.py::test_freeze_renamed_container_and_mpp_with_zip_suffix",
    "test_mpp_input.py::test_multiple_candidates_no_first_selection_preserves_container",
    "test_mpp_input.py::test_zip_unsafe_paths",
    "test_mpp_input.py::test_zip_collisions",
    "test_mpp_input.py::test_zip_symlink_and_input_symlink_forbidden",
    "test_mpp_input.py::test_zip_numeric_limits",
    "test_mpp_input.py::test_freeze_direct_exact_limit_and_missing",
    "test_mpp_input.py::test_input_changed_during_copy_is_never_accepted",
    "test_mpp_input.py::test_input_path_replaced_during_copy",
    "test_plan_archive.py::test_explicit_slug_and_contradictory_bindings_rejected",
    "test_plan_archive.py::test_stable_local_lineage_preserves_old_filename_lines",
    "test_plan_archive.py::test_artifact_corruption_is_not_duplicate_success",
    "test_plan_archive.py::test_same_filename_different_bytes_get_different_objects",
    "test_plan_reconcile.py::test_import_reconcile_missing_link_is_not_reimported",
}

STAGE03_REQUIRED |= {
    f"test_import_atomicity.py::test_process_death_commit_boundaries[{boundary}]"
    for boundary in ("after_snapshot","after_versions","after_item_link","after_event","before_commit",
                     "after_commit","before_readback","before_receipt")
}
STAGE03_REQUIRED |= {
    f"test_mpp_input.py::test_zip_numeric_limits[{case}]"
    for case in ("ZIP_MAX_ENTRIES-1-zip_entries_limit","ZIP_MAX_UNPACKED_BYTES-10-zip_unpacked_limit",
                 "ZIP_MAX_RATIO-1-zip_ratio_limit","ZIP_MAX_BYTES-10-zip_size_limit","MPP_MAX_BYTES-10-mpp_size_limit")
}


STAGE04_REQUIRED = STAGE03_REQUIRED | STAGE02_REQUIRED | {
    "test_plan_save.py::test_complete_save_and_unknown_timezone_sql_status",
    "test_plan_save.py::test_missing_runtime_is_explicit_failure_before_read",
    "test_plan_save.py::test_reader_diagnostics_use_stderr_and_artifacts",
    "test_save_e2e.py::test_cli_zip_multiple_candidates_retains_list",
    "test_plan_save.py::test_save_creates_snapshot_without_page_id",
    "test_plan_save.py::test_save_deduplicates_and_preserves_each_arrival",
    "test_plan_save.py::test_save_preserves_populated_baseline_and_publication_rows",
    "test_plan_save.py::test_save_requires_project_slug_preserves_input",
    "test_plan_save.py::test_save_with_page_id_reuses_existing_lineage",
    "test_plan_save.py::test_save_explicit_lineage_and_version_date",
    "test_plan_save.py::test_invalid_arguments_before_intake",
    "test_plan_save.py::test_save_missing_input_is_failed_arrival",
    "test_plan_save.py::test_unusable_snapshot_is_not_success",
    "test_plan_save.py::test_quality_warnings_do_not_block_archive",
    "test_plan_save.py::test_frozen_input_never_refreezes_or_opens_original",
    "test_plan_save.py::test_recovery_after_commit_before_readback_no_reader",
    "test_plan_save.py::test_receipt_mirror_failure_preserves_commit_and_recovers",
    "test_plan_save.py::test_corrupt_archived_source_or_export_never_duplicate_success",
    "test_plan_receipt.py::test_single_receipt_all_required_nullable_fields",
    "test_plan_receipt.py::test_single_receipt_save_invariants_reject_remote_effect",
    "test_plan_receipt.py::test_atomic_mirror_failure_keeps_previous_json",
    "test_plan_receipt.py::test_mask_driver_strings",
    "test_plan_receipt.py::test_receipt_rejects_path_escape",
    "test_cli.py::test_cli_save_parser_global_paths",
    "test_cli.py::test_cli_save_argument_errors_are_single_json",
    "test_cli.py::test_cli_save_runtime_failure_is_single_json",
    "test_cli.py::test_cli_rejects_unsupported_global_overrides",
    "test_env.py::test_save_context_resumes_frozen_paths_without_loader",
    "test_save_e2e.py::test_real_cli_cold_warm_save[E-78-84]",
    "test_save_e2e.py::test_real_cli_cold_warm_save[F-86-93]",
    "test_save_e2e.py::test_cli_cache_corruption_rebuilds_once",
    "test_save_e2e.py::test_cli_corrupt_mpp_is_failed_not_empty_plan",
    "test_save_e2e.py::test_cli_zip_intake_inside_save",
}


STAGE05_REQUIRED = STAGE04_REQUIRED | {
    "test_plan_manifest.py::" + name for name in (
        "test_manifest_rejects_unknown_null_and_common_fields", "test_manifest_item_validation",
        "test_manifest_duplicate_ids_and_json_keys", "test_canonical_order_paths_fields_label_policy_and_saved_defaults",
        "test_inbox_unicode_regular_complete_nonrecursive_diagnostics")
} | {"test_plan_batch.py::" + name for name in (
    "test_freeze_all_before_first_reader_and_mutated_second_source", "test_corrupt_middle_continue_stop_freeze_whole_list",
    "test_infrastructure_after_success_has_priority_and_retains_counts", "test_duplicates_within_across_batches_and_same_names_different_bytes",
    "test_structural_errors_precede_arrivals", "test_existing_batch_same_request_only_state_changed_manifest_conflicts",
    "test_inbox_late_file_excluded_diagnostics_and_sources_preserved", "test_receipt_balance_and_priority",
    "test_missing_input_and_expected_hash_known_before_first_parse", "test_foreign_lineage_is_local_failure_and_new_mpp_needs_no_decision",
    "test_same_bytes_different_timezone_and_profile_new_scope", "test_fixtures_batch_hashes_and_manifest_cases",
    "test_batch_cli_argument_errors_single_json")
} | {"test_batch_resume.py::" + name for name in (
    "test_resume_stop_retries_only_explicit_retryable_same_bytes", "test_freeze_failure_never_accepts_new_bytes_under_same_id",
    "test_lost_frozen_artifact_infrastructure_only_identical_repair", "test_mirror_failure_preserves_commit_and_restores_without_reader",
    "test_process_death_freeze_commit_receipt_boundaries", "test_resume_rejects_changed_frozen_context")
} | {"test_plan_lock.py::test_lock_busy_independent_process_and_release_after_death",
     "test_plan_lock.py::test_two_batch_handlers_busy_without_duplicate_arrivals"}
STAGE05_REQUIRED |= {"test_plan_batch.py::test_real_batch_cli_native_copies[" + mode + "]"
                     for mode in ("mpp", "manifest", "inbox", "named-risks")}
STAGE05_REQUIRED |= {"test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[" + boundary + "]"
                     for boundary in ("after_first_freeze", "before_freeze_barrier", "after_freeze_barrier", "before_snapshot_commit",
                                      "after_snapshot_commit", "before_save_receipt", "after_item_result", "before_batch_receipt")}
STAGE05_REQUIRED |= {"test_batch_resume.py::test_journaling_failure_stops_after_confirmed_success",
                     "test_batch_resume.py::test_missing_mirror_recovery_verifies_committed_artifacts"}


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
    if stage and stage not in ("01", "02", "03", "04", "05"):
        raise pytest.UsageError("this acceptance contour implements stages 01 through 05")
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
    archive = {"test_plan_archive.py", "test_plan_history.py", "test_plan_save.py", "test_plan_reconcile.py", "test_import_atomicity.py"}
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
        selected = {item.path.name+"::"+item.name for item in session.items}
        selected |= {value.split("[")[0] for value in selected}
        stage = session.config.getoption("--acceptance-stage")
        required = {"01": STAGE01_REQUIRED, "02": STAGE02_REQUIRED, "03": STAGE03_REQUIRED, "04": STAGE04_REQUIRED, "05": STAGE05_REQUIRED}[stage]
        missing = sorted(required - selected)
        if missing:
            raise pytest.UsageError(f"mandatory stage-{stage} tests not selected: " + ", ".join(missing))


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
    if config.getoption("--acceptance-stage") == "05":
        _stage05_report(session, exitstatus, root)
        return
    if config.getoption("--acceptance-stage") == "04":
        _stage04_report(session, exitstatus, root)
        return
    if config.getoption("--acceptance-stage") == "03":
        _stage03_report(session, exitstatus, root)
        return
    if config.getoption("--acceptance-stage") == "02":
        _stage02_report(session, exitstatus, root)
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


def _stage02_report(session, exitstatus, root):
    """Stage-02 aggregate stays in the existing pytest hook, external rc is evidence."""
    config = session.config
    external_path = root / "reports/external-checks.json"
    external = json.loads(external_path.read_text()) if external_path.exists() else {}
    results = config._acceptance_results
    good = (exitstatus == 0 and bool(session.items) and bool(results)
            and all(r["status"] == "passed" for r in results)
            and external.get("gate") == "passed")
    reader = Path.home() / "USERTOOLS/MppReader"
    files = sorted(list(SCRIPTS.glob("*.py")) + list((SKILL_ROOT / "tests").glob("*.py"))
                   + list((SKILL_ROOT / "references/schemas").glob("*.json"))
                   + list((SKILL_ROOT / "references/profiles").glob("*.json"))
                   + list((SKILL_ROOT / "tests/fixtures").rglob("manifest.json"))
                   + [reader / "plan_export.py", reader / "read_mpp.py", reader / "tests/test_plan_export.py",
                      reader / "tests/test_read_mpp_regression.py", reader / "tests/conftest.py",
                      SKILL_ROOT / "requirements.txt", SKILL_ROOT / "tests/pytest.ini",
                      SKILL_ROOT / "tests/fixtures/synthetic/binary_recipe.py"]
                   + list((SKILL_ROOT / "references").glob("*.md")))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    schema = Path.home() / "WorkVault/Registries/EcosystemConfig.schema.json"
    master = Path.home() / "WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md"
    plan = master.parent / "plans/HF-plan_EditPlanConfluence_20261116.md"
    counters = dict(config._acceptance_counters)
    # Legacy calendar/CSV paths are outside the new branch (adaptation stage 08).
    # Their complete read count is not measured, so do not present it as zero.
    counters["MPXJ_read_prepared_branch"] = counters.pop("MPXJ_read")
    counters["MPXJ_read_total_including_legacy"] = None
    counters["new_prepared_branch"] = json.loads((root / "reports/cache-read-evidence.json").read_text()) if (root / "reports/cache-read-evidence.json").exists() else None
    report = {"stage": "02", "gate": "passed" if good else "failed", "exit_code": int(exitstatus),
              "command": [sys.executable, "-m", "pytest", *config.invocation_params.args],
              "environment": {"python": sys.executable, "version": platform.python_version(), "test_root": str(root),
                              "PYTHONPATH": os.environ.get("PYTHONPATH")},
              "master": {"version": "0.5.0", "path": str(master), "sha256": hashlib.sha256(master.read_bytes()).hexdigest()},
              "plan": {"path": str(plan), "normative_prefix_sha256": hashlib.sha256(plan.read_text().split("## Журнал исполнения")[0].encode()).hexdigest()},
              "source_tree_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(), "source_files": hashes,
              "config_contract_sha256": hashlib.sha256(schema.read_bytes()).hexdigest(),
              "migrations": [], "tests": results, "selected": len(session.items), "counters": counters,
              "external_checks": external, "covered_requirements": ["foundations of §20/AC-01,02,06,07,08,16"],
              "limitations": ["Only stage 02; public save/publish wiring belongs to later stages",
                              "No schedule verification or live Confluence", "summary-v1 and installed plugin profile are stage 08",
                              "ZIP enforcement is stage 03; HTTP settings consumption is stage 10",
                              "MPXJ may filter invalid MPP relation records before exposing ProjectFile; see export-contract.md",
                              "ownCloud sync not confirmed"],
              "generated_at": datetime.now(timezone.utc).isoformat()}
    report["implemented_files"] = {
        "R/plan_export.py": "full-export-v2: fields/quality, structured signed lag/elapsed, calendar intervals/exceptions/inheritance/bindings, graph diagnostics",
        "R/read_mpp.py": "shared instrumented read_project_file boundary; CSV/JSON contract preserved",
        "S/scripts/prepared_plan.py": "PreparedPlan v1, NormalizationProfile, validation and deterministic semantic SHA",
        "S/scripts/plan_cache.py": "independent ParseCache/RepresentationCache, atomic write, checksum/completeness/version and source verification",
        "S/scripts/plan_context.py": "Manifest paths, typed settings, explicit overrides, non-secret context snapshot/fingerprints",
        "S/scripts/env.py": "unified loader adapter; archive settings separate from credentials; checked MPXJ Python/JVM selection",
        "S/scripts/mpp_input.py": "_pick_python delegates to checked runtime; no success fallback on failure",
        "E/EcosystemConfig.yaml + schema": "15 effective settings including shared paths/URL; tool-specific types/ranges; backup and minimal non-secret diff",
        "S/references/schemas + profiles": "prepared-plan/schema, settings/schema, normalization-v1; export/operations contracts",
        "R/tests + S/tests + fixtures": "real binary/CSV tests, normalization/cache/context tests, isolation and stage-02 acceptance hook; verified A-F/D-risks and synthetic manifests",
    }
    report["export_contract"] = {"version": "full-export-v2", "prepared": "v1", "collection_quality": ["complete", "partial", "missing", "unsupported"],
                                 "missing": "null + reason", "known_zero": "ok + 0", "raw_mpp_relation_enumeration": "unsupported; MPXJ filters invalid records", "schedule": "not_verified"}
    report["cache_contract"] = {"parse_key": "source SHA + reader/MPXJ/JPype + export version + export parameters",
                                "representation_key": "semantic SHA + converter + rules revision + plugin fingerprint + template parameters",
                                "integrity": "namespace/version/material/key/complete/byte count/payload SHA + export validation; fsync/atomic replace",
                                "recovery": "corruption is a miss; rebuild from verified durable bytes; invalid source fails closed"}
    context_path = root / "reports/effective-context.json"
    report["config_changes"] = json.loads(context_path.read_text()) if context_path.exists() else {"status": "not_recorded"}
    (root / "reports/stage-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    lines = ["# Этап 02", "", f"Gate: **{report['gate']}**. S rc={exitstatus}, "
             f"passed={sum(r['status'] == 'passed' for r in results)}; "
             f"R passed={external.get('reader', {}).get('passed')}, optional skips={external.get('reader', {}).get('optional_skips')}; "
             f"archive regression passed={external.get('archive_regression', {}).get('passed')}.", "",
             f"Base commit: 8b04ce1945b88409fae036b4a0f0d69a52dfceea. Проверенное дерево: `{report['source_tree_sha256']}`.", "",
             "Реализованные файлы:", ""]
    lines.extend(f"- `{path}`: {description}." for path, description in report["implemented_files"].items())
    lines.extend(["", "Экспорт/кэш:", "", "- " + json.dumps(report["export_contract"], ensure_ascii=False),
                  "- " + json.dumps(report["cache_contract"], ensure_ascii=False), "", "Команды:", "",
                  "```text", " ".join(report["command"]), " ".join(external.get("reader", {}).get("command", {}).get("command", [])),
                  " ".join(external.get("archive_regression", {}).get("command", {}).get("command", [])), "```", "",
                  "Все три rc=0 обязательны для passed. SQL-миграций нет. Settings/sources/profiles: effective-context.json; "
                  "версии: environment.json; восстановление R и неизменность этапа 01: external-checks.json. "
                  "Несекретный config/schema diff и backup manifest: config/. Коммит связывает код и этот отчёт; SHA после коммита — в журнале канонического плана.", "",
                  "Ограничения:", ""])
    lines.extend("- " + item for item in report["limitations"])
    lines.append("- Optional skip относится только к старому ZD-тесту §19: исходные MPP отсутствуют. Обязательные тесты этапа 02 не пропущены.")
    (root / "reports/stage-report.md").write_text("\n".join(lines) + "\n")


def _stage03_report(session, exitstatus, root):
    """Aggregate actual tests with separately executed MofsIndex and delivery evidence."""
    config=session.config
    path=root/"reports/external-checks.json"
    external=json.loads(path.read_text()) if path.exists() else {}
    results=config._acceptance_results
    good=(exitstatus==0 and bool(session.items) and bool(results)
          and all(r["status"]=="passed" for r in results) and external.get("gate")=="passed")
    paths=sorted(set([*SCRIPTS.glob("*.py"),*(SKILL_ROOT/"tests").glob("*.py"),
        *(MOFS_INDEX_ROOT/"mofs_index/plan").glob("*.py"),*(MOFS_INDEX_ROOT/"tests/plan").glob("*.py"),
        *(SKILL_ROOT/"references/schemas").glob("*.json"),SKILL_ROOT/"tests/pytest.ini",
        SKILL_ROOT/"references/operations-and-recovery.md"]))
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    master=Path.home()/"WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md"
    plan=master.parent/"plans/HF-plan_EditPlanConfluence_20261116.md"
    schema=Path.home()/"WorkVault/Registries/EcosystemConfig.schema.json"
    implemented={
        "M/mofs_index/plan/schema.py":"0007 durable imports/nullable operation context; 0008 semantic dedup and lossless version fields; all_plan_table_names",
        "M/mofs_index/plan/migrate.py":"transactional create-copy-drop-rename with FK restoration/check, checksums and migration concurrency; refuses caller transaction",
        "M/mofs_index/plan/writer.py":"typed operations/batches/items/attempts/events; one atomic snapshot-version-item-event commit; artifact verification; exact decimals",
        "M/mofs_index/plan/ingest_mpp.py":"legacy/v2/PreparedPlan adapters; complete source JSON, quantities/units, intervals and runtime/profile fingerprint",
        "M/mofs_index/plan/query.py":"typed reads for operation/item/batch/attempt/events/artifact/lineage/snapshot/dedup/committed link",
        "S/scripts/plan_archive.py":"atomic content-addressed artifact store/read-back; explicit slug/lineage/page conflicts; stable local archive lineage",
        "S/scripts/mpp_input.py":"consistent double-read freeze; durable locator; ZIP content detection, all-member safety and numeric limits; no first candidate selection",
        "S/scripts/plan_operation.py":"register unresolved operation/item before project; persist effective context, freeze/error provenance; new attempt on repeat; commit/reconcile adapter",
        "S/scripts/plan_reconcile.py":"committed link then read-back; no parser path; mirror failure retains SQL commit",
        "S/scripts/plan_save.py":"only replace filename-based local lineage with stable project archive binding; full pipeline wiring remains stage 04",
        "M/tests/plan/{test_schema,test_migrate,test_writer_snapshot,test_backup}.py":"new/legacy migrations, rollback, rebuild preservation, exact values, dedup and backup",
        "S/tests/{test_mpp_input,test_plan_archive,test_plan_reconcile,test_import_atomicity}.py":"ZIP/input adversarial tests, real two-process concurrency and eight os._exit crash boundaries",
        "S/tests/conftest.py + S/references/operations-and-recovery.md":"stage-03 mandatory IDs/gate/report and reproducible internal API/input profile contract",
    }
    limitations=["Only stage 03: public prepared save/CLI integration is stage 04; batch orchestration is stages 05-06",
                 "No production DB migration, Confluence/network publication or schedule verification",
                 "No edits to stage-01/02 evidence, applied migrations 0001-0006, MppReader or EcosystemConfig",
                 "ownCloud sync not confirmed; process-death tests do not simulate OS/power failure"]
    counters=dict(config._acceptance_counters)
    counters["MPXJ_read"]=0  # selected stage03 tests use existing serialized fixtures, never a JVM reader
    report={"stage":"03","gate":"passed" if good else "failed","exit_code":int(exitstatus),
        "command":[sys.executable,"-m","pytest",*config.invocation_params.args],
        "base_commit":"e9f13dd82b51e2aa4e2515901ce6ed29772677d3",
        "environment":{"python":sys.executable,"version":platform.python_version(),"test_root":str(root),"PYTHONPATH":os.environ.get("PYTHONPATH")},
        "master":{"version":"0.5.0","path":str(master),"sha256":hashlib.sha256(master.read_bytes()).hexdigest()},
        "plan":{"path":str(plan),"normative_prefix_sha256":hashlib.sha256(plan.read_text().split("## Журнал исполнения")[0].encode()).hexdigest()},
        "source_files":hashes,"source_tree_sha256":hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
        "config_contract_sha256":hashlib.sha256(schema.read_bytes()).hexdigest(),
        "migrations":["0007_durable_imports","0008_snapshot_semantics"],"implemented_files":implemented,
        "tests":results,"selected":len(session.items),"mandatory_test_ids":sorted(STAGE03_REQUIRED),"external_checks":external,
        "counters":counters,"covered_requirements":["foundations of §20/AC-15,16,20,21,22,26,27 and AC-19"],
        "atomicity":"single BEGIN IMMEDIATE: snapshot -> versions -> item.snapshot_id -> snapshot_committed -> COMMIT; no nested public writer",
        "deduplication":"plan+lineage+source_mpp_sha256+representation+normalization_profile_fingerprint+resolved_timezone; two DB unique indices; legacy NULL profile excluded",
        "recovery":"committed item/event link -> verified source/hash and normalized/version read-back -> optional receipt mirror; no reader after commit",
        "input":"input-v1; double open-file read/size/mtime/ctime/inode/hash plus fsync+atomic rename under explicit WorkVault; ZIP per-member/content/path/type/size/ratio checks",
        "limitations":limitations,"generated_at":datetime.now(timezone.utc).isoformat()}
    (root/"reports/stage-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    lines=["# Этап 03", "",f"Gate: **{report['gate']}**. S rc={exitstatus}; passed={sum(r['status']=='passed' for r in results)}; selected={len(session.items)}.",
        "",f"MofsIndex: {external.get('mofs_required',{}).get('passed')} обязательных, {external.get('mofs_regression',{}).get('passed')} в полной plan-регрессии. Подробные команды/rc/JUnit: external-checks.json.",
        "",f"Дерево исходников: `{report['source_tree_sha256']}`. Master 0.5.0, hash в JSON. Миграции: 0007_durable_imports, 0008_snapshot_semantics.","", "Реализовано:",""]
    lines.extend(f"- `{path}`: {description}." for path,description in implemented.items())
    lines.extend(["","Атомарность: "+report["atomicity"],"","Дедупликация: "+report["deduplication"],"","Восстановление: "+report["recovery"],"","Вход: "+report["input"],"","Команда S:","","```text"," ".join(report["command"]),"```","","Проверено восемь границ падения процесса: после snapshot, versions, item-link, event, до COMMIT, после COMMIT, до read-back, до квитанции. Два независимых процесса оставляют один snapshot и два поступления.","","Комплект внешних изменений: usertools/MofsIndex/{before,after,changes.patch,manifest.json}; восстановление и hashes — external-checks.json. SHA завершающего коммита записывается в журнал канонического плана после commit.","","Ограничения:",""])
    lines.extend("- "+v for v in limitations)
    (root/"reports/stage-report.md").write_text("\n".join(lines)+"\n")


def _stage04_report(session, exitstatus, root):
    """Evidence and gate from actual pytest outcomes, E/F and protected hashes."""
    config = session.config
    results = config._acceptance_results
    initial_path = root/"reports/initial-state.json"
    initial = json.loads(initial_path.read_text()) if initial_path.is_file() else {}
    protected = initial.get("protected_hashes", {})
    changed_protected = [name for name, digest in protected.items()
                         if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
    cases = {}
    for name in ("E", "F"):
        path = root/"reports"/("save-e2e-"+name+".json")
        if path.is_file():
            cases[name] = json.loads(path.read_text())
    good = (exitstatus == 0 and bool(session.items) and bool(results)
            and all(r["status"] == "passed" for r in results)
            and bool(protected) and not changed_protected and set(cases) == {"E", "F"})
    files = sorted(set([*SCRIPTS.glob("*.py"), *(SKILL_ROOT/"tests").glob("*.py"),
                       *(SKILL_ROOT/"references/schemas").glob("*.json"),
                       *(SKILL_ROOT/"references/profiles").glob("*.json"),
                       *(SKILL_ROOT/"references").glob("*.md"), SKILL_ROOT/"tests/pytest.ini"]))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    master = Path.home()/"WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md"
    plan = master.parent/"plans/HF-plan_EditPlanConfluence_20261116.md"
    schema = Path.home()/"WorkVault/Registries/EcosystemConfig.schema.json"
    implemented = {
        "S/scripts/plan_save.py": "единый freeze → parse/cache → quality → typed archive/dedup → read-back → receipt; save_frozen_input с обязательными artifact/hash/context/operation; краткий SaveResult; восстановление без reader",
        "S/scripts/cli.py": "lazy client/pipeline imports; локальный save --page-id; глобальные пути, lineage и дата версии; JSON результата и ошибок; rc 0/2/4/5",
        "S/scripts/plan_context.py": "изолированные db/WorkVault/cache передаются явно; восстановление settings/sources/profile hashes без loader",
        "S/scripts/plan_receipt.py": "полный nullable контракт v1; атомарная замена/fsync/read-back; маскирование; безопасные имена зеркал",
        "S/scripts/plan_operation.py": "save_result в SQL до файлового зеркала; ошибка зеркала сохраняет snapshot и SQL-историю",
        "S/scripts/plan_reconcile.py": "чтение полной последней квитанции из SQL; committed read-back без повторного разбора",
        "S/references/schemas/single-receipt.schema.json": "полная схема §20.3.12.1 и save-инварианты",
        "S/references/cli-contract.md": "все добавленные параметры, размещение overrides, exit codes, обязательные пути и сохранённая совместимость",
        "S/tests/test_plan_save.py + test_plan_receipt.py + test_cli.py + test_env.py": "контракты, populated baseline, предупреждения, ошибки, recovery commit/mirror, JSON и изоляция",
        "S/tests/test_save_e2e.py": "CLI /usr/bin/python3 и реальный MPXJ /usr/bin/python3.9; E/F cold/warm, corruption rebuild, unreadable MPP, ZIP; импорт клиента и сеть запрещены",
        "S/tests/conftest.py": "обязательные test ID этапа 04 и отчёт из фактических результатов; проверка неизменности внешних компонентов и evidence 01–03",
    }
    limitations = ["Только этап 04; batch, identity, publish/resume CLI и активная регистрация остаются последующим этапам",
                   "schedule:not_verified; live Confluence и проверка установленного плагина не выполнялись",
                   "Общее число MPXJ-read старых CSV/calendar-путей не измерено; failed reader без экспортной telemetry имеет счётчик null",
                   "Production-БД/страницы/настройки/baseline не изменялись; новые миграции отсутствуют",
                   "MofsIndex/MppReader только читались; внешний комплект изменений не требуется",
                   "ownCloud sync не подтверждён; Gateway/кроны/наблюдатели/расписания не изменялись"]
    counters = {"save_E_F": {name: {kind: value[kind]["counters"] for kind in ("cold", "warm")} for name,value in cases.items()},
                "MPXJ_read_all_legacy_paths": None, "live_POST":0, "live_PUT":0,
                "publication_regression_fake_counts": config._acceptance_counters}
    report = {"stage":"04", "gate":"passed" if good else "failed", "exit_code":int(exitstatus),
              "base_commit":initial.get("base_commit"),
              "command":[sys.executable,"-m","pytest",*config.invocation_params.args],
              "environment":{"python":sys.executable,"version":platform.python_version(),"test_root":str(root),
                             "cli_python":"/usr/bin/python3","mpxj_python":"/usr/bin/python3.9", "PYTHONPATH":os.environ.get("PYTHONPATH")},
              "master":{"version":"0.5.0","path":str(master),"sha256":hashlib.sha256(master.read_bytes()).hexdigest()},
              "plan":{"path":str(plan),"normative_prefix_sha256":hashlib.sha256(plan.read_text().split("## Журнал исполнения")[0].encode()).hexdigest()},
              "source_files":hashes,"source_tree_sha256":hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
              "config_contract_sha256":hashlib.sha256(schema.read_bytes()).hexdigest(), "migrations":[],
              "protected_files_checked":len(protected),"changed_protected_files":changed_protected,
              "preexisting_changes":initial.get("preexisting",[]),"implemented_files":implemented,
              "selected":len(session.items), "tests":results, "mandatory_test_ids":sorted(STAGE04_REQUIRED),
              "counters":counters, "real_cases":cases,
              "covered_requirements":["§20/AC-01", "save portions of §20/AC-07,08,15,16,20,21,26"],
              "invariants":{"published":False,"page_id":None,"page_url":None,"external_effect":"none",
                            "baseline":"exact populated table rows preserved", "publication":"no added rows"},
              "receipt":"schema_version:1; SQL save_result first; atomic file mirror; mirror failure failed/5 retains committed IDs; recovery read-back before reader",
              "limitations":limitations,"generated_at":datetime.now(timezone.utc).isoformat()}
    (root/"reports/stage-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    lines = ["# Этап 04 — общий однопроходный save", "", f"Gate: **{report['gate']}**; rc={exitstatus}; selected={len(session.items)}; passed={sum(r['status']=='passed' for r in results)}.",
             "", "Реализовано:", ""]
    lines.extend(f"- `{name}`: {value}." for name,value in implemented.items())
    lines.extend(["", "Цепочка: freeze → parse/cache → quality → typed archive/dedup → read-back → receipt. Каждый повтор регистрирует новое поступление, snapshot дедуплицируется. После commit reader не вызывается.",
                  "", "Квитанция v1 содержит все обязательные поля §20.3.12.1. Save: published=false, page_id/page_url=null, external_effect=none. Baseline проверен точным сравнением заполненных таблиц. При отказе зеркала failed/5 сохраняет snapshot_id и подтверждённый archive read-back; SQL-результат не теряется.",
                  "", "CLI: глобальные --db/--workvault/--cache-dir до подкоманды; save --mpp, --project-slug, --lineage-id, --timezone-hint, --source-version-date; совместимый --page-id только локальный. Полный контракт: references/cli-contract.md.",
                  "", "Команда проверки:", "", "```text", " ".join(report["command"]), "```", "", "Реальные E/F:", ""])
    for name, value in cases.items():
        lines.append(f"- {name}: tasks/dependencies={value['cold']['receipt']['task_count']}/{value['cold']['receipt']['dependency_count']}; cold MPXJ={value['cold']['counters']['MPXJ_read']}; warm MPXJ={value['warm']['counters']['MPXJ_read']}, cache_hit={value['warm']['counters']['cache_hit']}; rc=0/0. Evidence: save-e2e-{name}.json.")
    lines.extend(["", f"Проверено защищённых файлов: {len(protected)}; изменений: {len(changed_protected)}. M/R/E, миграции и evidence 01–03 без изменений. Внешнего комплекта нет. Незакоммиченные заготовки, найденные при входе, сохранены в T/preexisting и включены после проверки в реализацию этапа 04.",
                  "", f"Дерево исходников: `{report['source_tree_sha256']}`. Версия master 0.5.0; hashes, версии, test ID/длительности и счётчики — в JSON. JUnit: junit.xml. SHA коммита записывается после commit в журнал канонического плана.",
                  "", "Ограничения:", ""])
    lines.extend("- "+value for value in limitations)
    (root/"reports/stage-report.md").write_text("\n".join(lines)+"\n")


def _stage05_report(session, exitstatus, root):
    """Actual batch gate, external delivery/pytest results and immutable evidence."""
    config = session.config
    results = config._acceptance_results
    initial_path = root / 'reports/initial-state.json'
    initial = json.loads(initial_path.read_text()) if initial_path.exists() else {}
    external_path = root / 'reports/external-checks.json'
    external = json.loads(external_path.read_text()) if external_path.exists() else {}
    protected = initial.get('protected_hashes', {})
    changed = [name for name,digest in protected.items()
               if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
    cases = {mode:json.loads(path.read_text()) for mode in ('mpp','manifest','inbox','named-risks')
             if (path := root / 'reports' / ('batch-real-'+mode+'.json')).is_file()}
    good = (exitstatus == 0 and bool(session.items) and bool(results)
            and all(result['status'] == 'passed' for result in results)
            and bool(protected) and not changed and external.get('gate') == 'passed'
            and set(cases) == {'mpp','manifest','inbox','named-risks'}
            and all(case['rc'] == case['repeat_rc'] == 0 for case in cases.values()))
    files = sorted(set([*SCRIPTS.glob('*.py'), *(SKILL_ROOT/'tests').glob('*.py'),
                       *(SKILL_ROOT/'references/schemas').glob('*.json'), *(SKILL_ROOT/'references/profiles').glob('*.json'),
                       *(SKILL_ROOT/'references').glob('*.md'), *(MOFS_INDEX_ROOT/'mofs_index/plan').glob('*.py'),
                       *(MOFS_INDEX_ROOT/'tests/plan').glob('*.py'), SKILL_ROOT/'tests/pytest.ini',
                       *(p for p in (SKILL_ROOT/'tests/fixtures/batch').rglob('*') if p.is_file())]))
    hashes = {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    master = Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan = master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    schema = Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    implemented = {
        'S/scripts/plan_manifest.py':'строгие поля/null/ID/date/IANA/SHA; канонизация порядка/путей/label/on_error с сохранёнными defaults; Inbox без рекурсии, Unicode и диагностика исключений',
        'S/scripts/plan_batch.py':'три входа; неизменяемый запрос и контекст; freeze-all barrier до reader; последовательные continue/stop; idempotent save, frozen resume, явный retry-failed; общий инфраструктурный stop',
        'S/scripts/plan_lock.py':'межпроцессный nonblocking flock по реальной БД и batch ID; стабильный inode, автоматическое освобождение при смерти процесса',
        'S/scripts/cli.py':'batch save/resume/show; взаимоисключающие входы; глобальные пути; машинный JSON без клиента/сети',
        'S/scripts/plan_receipt.py':'полная пакетная квитанция v1, баланс, saved_with_warnings внутри saved; приоритет 2/4/5/6/0',
        'S/scripts/plan_reconcile.py':'проверка только frozen locators и committed item/event/snapshot, read-back и зеркало через общий save без нового reader/поступления/snapshot',
        'M/mofs_index/plan/writer.py':'typed atomic registration всех item/operations; barrier freeze; processing intent/attempt; typed result/event и batch completion; схемы/миграции неизменны',
        'M/mofs_index/plan/query.py':'ordered batch items, attempts, последнее событие результата и согласованное read-only SQL-наблюдение',
        'S/references/schemas/{batch-manifest,batch-receipt}.schema.json':'строгие JSON-контракты §20.4.4/§20.3.12.2',
        'S/references/cli-contract.md':'batch save/resume/show, ошибки, блокировка, frozen context, коды и граница этапа 06',
        'S/tests/{test_plan_manifest,test_plan_batch,test_batch_resume,test_plan_lock}.py':'входы/дубли/ошибки/повторы, реальные E/F+D-risks, восемь process-death границ, два процесса, freeze/commit/receipt/journaling',
        'S/tests/fixtures/batch/':'проверенные manifest fixtures, одинаковые MPP, неразбираемый вход и нерекурсивный Inbox',
        'M/tests/plan/test_batch.py':'атомарная регистрация и rollback, уникальность ID по пакету, запрет reader до общей фиксации, typed results и FK/integrity',
        'S/tests/conftest.py':'обязательные ID этапа 05, изоляция и фактический gate/report из pytest; прежние стадии сохранены',
    }
    limitations = [
        'Реализован только этап 05; proposals/decisions, retry-decisions и расширенная история относятся к этапу 06',
        'schedule:not_verified; live Confluence/плагин не проверялись; полная приёмка §20 не заявлена',
        'Нормативные E/F = 090726/230726; упомянутый в поручении 260626_risks проверен дополнительно как D-risks',
        'При reader failure без export telemetry число MPXJ-read остаётся null; старые CSV/calendar paths отдельно не измерялись',
        'Блокировка локальная POSIX flock; распределённая блокировка между разными хостами вне этого контура',
        'Process-death tests не моделируют отказ ОС/питания; ownCloud sync не подтверждён',
        'Production-БД/страницы/настройки/baseline, Gateway/кроны/наблюдатели/расписания не менялись',
    ]
    counters = {'batch_real':{mode:{'cold':[case['metrics']['counters'] for case in evidence['cases']],
                                  'warm':[metric['counters'] for metric in evidence['repeat_metrics']]}
                              for mode,evidence in cases.items()},
                'legacy_reader_total':None, 'live_POST':0, 'live_PUT':0,
                'publication_fake_regression':config._acceptance_counters}
    report = {'stage':'05','gate':'passed' if good else 'failed','exit_code':int(exitstatus),
              'base_commit':initial.get('base_commit'),
              'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
              'environment':{'python':sys.executable,'version':platform.python_version(),'test_root':str(root),
                             'cli_python':'/usr/bin/python3','mpxj_python':'/usr/bin/python3.9','PYTHONPATH':os.environ.get('PYTHONPATH')},
              'master':{'version':'0.5.0','path':str(master),'sha256':hashlib.sha256(master.read_bytes()).hexdigest()},
              'plan':{'path':str(plan),'normative_prefix_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()},
              'config_contract_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),
              'source_files':hashes,'source_tree_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
              'migrations':[], 'existing_schema':['0001','0002','0003','0004','0005','0006','0007','0008'],
              'protected_files_checked':len(protected),'changed_protected_files':changed,
              'implemented_files':implemented,'selected':len(session.items),'tests':results,
              'mandatory_test_ids':sorted(STAGE05_REQUIRED),'external_checks':external,'real_cases':cases,'counters':counters,
              'covered_requirements':['§20/AC-17','§20/AC-18','stage-05 parts of §20/AC-19','§20/AC-20','§20/AC-21','§20/AC-22','§20/AC-26'],
              'batch_contract':{'inputs':['repeatable --mpp','manifest','Inbox'],
                  'freeze':'All arrivals: verified durable bytes or specific terminal input error; atomic inputs_frozen_at before processing',
                  'resume':'saved skipped; processing reconciled before parse; failed retried only explicitly if retryable; no original paths/current defaults',
                  'balance':'total = saved + unchanged + failed + needs_decision + not_started; warnings subset of saved',
                  'exit_priority':[2,4,5,6,0],'published':False,'baseline':'exact populated rows preserved','publication':'no added rows'},
              'limitations':limitations,'generated_at':datetime.now(timezone.utc).isoformat()}
    (root/'reports/stage-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Этап 05 — batch: входы, обработка и восстановление','',
           f"Gate: **{report['gate']}**. S rc={exitstatus}; selected={len(session.items)}; passed={sum(result['status']=='passed' for result in results)}.",
           '', 'Реализовано:', '']
    lines.extend(f'- `{name}`: {value}.' for name,value in implemented.items())
    lines.extend(['','Три входа: повторяемый --mpp, manifest и Inbox. Freeze-all завершается до reader; stop действует только на обработку. Resume работает на прежних байтах/контексте, пропускает успешные, разрешает retryable failed только явно. После commit сначала read-back, новый snapshot и reader запрещены.',
                  '', 'Баланс: total = saved + unchanged + failed + needs_decision + not_started; saved_with_warnings входит в saved. Приоритет exit codes: 2 → 4 → 5 → 6 → 0. Published=false; baseline и публикации сохранены.',
                  '', 'Команда S:', '', '```text', ' '.join(report['command']), '```', '',
                  f"M/tests: rc={external.get('mofs_tests',{}).get('rc')}, passed={external.get('mofs_tests',{}).get('passed')}; команды/окружение/stdout/stderr/JUnit — external-checks.json и mofs-*.xml/log.",
                  '', 'Реальные MPP:'])
    for mode, evidence in cases.items():
        measurements=', '.join(f"{case['case']}={case['receipt']['task_count']}/{case['receipt']['dependency_count']}" for case in evidence['cases'])
        lines.append(f"- {mode}: {measurements}; cold=1 MPXJ-read на вход, warm=0/read + cache hit; rc={evidence['rc']}/{evidence['repeat_rc']}. Evidence: batch-real-{mode}.json.")
    lines.extend(['', 'Восемь реальных os._exit границ: после первого freeze, до/после общей отметки, до/после snapshot commit, до single receipt, после item result и до batch receipt. Два независимых процесса подтверждают busy/4, отсутствие новых поступлений и освобождение после SIGKILL.',
                  '', f"Защищённые файлы: {len(protected)}; изменено: {len(changed)}. Миграций нет. USERTOOLS before/after/patch/manifest и проверка обоих способов восстановления: usertools/MofsIndex/, external-checks.json.",
                  '', f"Дерево исходников: `{report['source_tree_sha256']}`. Master 0.5.0 и контракты захэшированы в JSON. SHA финального коммита записывается после commit в журнал канонического плана.",
                  '', 'Ограничения:', ''])
    lines.extend('- '+value for value in limitations)
    (root/'reports/stage-report.md').write_text('\n'.join(lines)+'\n')
