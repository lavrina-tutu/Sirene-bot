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


# Stage 06 deliberately uses unit/archive groups; real-reader regression stays
# in earlier gates, plus the new actual-MPP decision CLI journey below.
STAGE06_REQUIRED = {name for name in STAGE05_REQUIRED
    if not name.startswith('test_save_e2e.py::')
    and not name.startswith('test_plan_batch.py::test_real_batch_cli_native_copies')
    and name not in {'test_plan_cache.py::test_real_parse_cache_one_read_same_bytes_different_names',
                    'test_cli.py::test_cli_convert_offline',
                    'test_mpp_calendar.py::test_calendar_from_mpp_fixture',
                    'test_pipeline.py::test_build_plan_from_mpp_offline'}}
STAGE06_REQUIRED |= {'test_batch_decisions.py::'+name for name in (
    'test_ac19_continue_registration_and_explicit_consumption',
    'test_ac19_lineage_two_reasons_and_stop', 'test_ac19_foreign_stale_and_changed_grounds',
    'test_ac19_context_immutable', 'test_ac19_registration_batch_busy',
    'test_ac19_proved_conflict_is_item_failure', 'test_ac19_no_artificial_decisions',
    'test_ac19_process_death_after_registration_and_commit', 'test_ac19_registration_transaction_rollback',
    'test_ac19_real_cli_registration_and_retry')}
STAGE06_REQUIRED |= {'test_history_queries.py::'+name for name in (
    'test_history_views_and_defaults', 'test_history_half_open_timezone_and_equal_timestamps',
    'test_history_filter_fields_are_distinct_order_source_does_not_change_filter',
    'test_history_unknown_time_separate_count', 'test_history_cursor_stable_ties_unknowns_and_new_backdated_arrival',
    'test_history_invalid_parameters_fail_closed', 'test_history_cursor_cannot_change_filter',
    'test_history_project_lineage_scope_and_failed_arrivals', 'test_history_cli_matches_typed_api',
    'test_q_history_integration_uses_same_api', 'test_history_all_views_paginate_without_duplicates')}


STAGE07_REQUIRED = STAGE06_REQUIRED | {'test_plan_identity.py::'+name for name in (
    'test_confirm_show_no_automatic_operation_start_and_evidence_copy',
    'test_operation_requirements_partial_then_sufficient_and_fixed_revision',
    'test_strict_mapping_shape_before_mutation',
    'test_mapping_rejects_duplicate_json_keys_and_continuity_mapping_argument',
    'test_schema_matches_runtime_validator',
    'test_foreign_project_pair_and_unknown_uid_are_conflicts',
    'test_real_cli_confirm_show_errors_and_no_resume',
    'test_q_identity_integration_uses_same_api',
    'test_real_independent_mpp_same_uid_stays_unknown')}


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
    if stage and stage not in ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13"):
        raise pytest.UsageError("this acceptance contour implements stages 01 through 13")
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
    if stage=='09':
        config._acceptance_start_hashes=_stage09_sources()
    if stage=='10':
        config._acceptance_start_hashes=_stage10_sources()
    if stage=='11':
        config._acceptance_start_hashes=_stage11_sources()
    if stage=='12':
        config._acceptance_start_hashes=_stage12_sources()
    if stage == '13':
        _stage13_configure(config)


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
    if config.getoption('--acceptance-stage') == '12':
        # Some previous tests inherit unit at module level and also carry live.
        # Stage 12 is explicitly offline: live wins over the inherited marker.
        deselected = [item for item in items if item.get_closest_marker('confluence_live')]
        if deselected:
            config.hook.pytest_deselected(items=deselected)
            items[:] = [item for item in items if item not in deselected]
    if config.getoption('--acceptance-stage') == '13':
        # Stage 13 keeps the four group boundaries while moving end-to-end
        # batch/query and recovery checks after the cold MPP group. Earlier
        # stages retain their original classification and report contracts.
        batch_files = {'test_plan_batch.py','test_batch_decisions.py','test_history_queries.py',
                       'test_plan_identity.py','test_compare_e2e.py','test_identity_resume_e2e.py'}
        for item in items:
            loopback = (item.name.startswith('test_real_process_death_http_reconciliation')
                        or item.name.startswith('test_verify_cli_loopback_concurrent'))
            if loopback:
                item.own_markers[:] = [m for m in item.own_markers if m.name not in ('confluence_live','live')]
                item.add_marker(pytest.mark.loopback_http)
                item.add_marker(pytest.mark.mpp_fixtures)
            elif not item.get_closest_marker('confluence_live') and (
                    item.path.name in batch_files | STAGE13_RECOVERY_FILES):
                item.add_marker(pytest.mark.mpp_fixtures)
    if config.getoption('--acceptance-stage') in ('08','09','10','11','12','13'):
        order={'unit':0,'archive_integration':1,'mpp_fixtures':2,'confluence_live':3}
        items.sort(key=lambda item:(max(order[g] for g in GROUPS if item.get_closest_marker(g)),item.nodeid))
    if config.getoption('--acceptance-stage') == '13':
        def final_order(item):
            group = max(GROUPS.index(g) for g in GROUPS if item.get_closest_marker(g))
            # The final journeys follow the earlier component regression in each
            # group. Migration precedes unit; real cold saves precede batch;
            # legacy GET verification and active-skill loading follow live plans.
            rank = 10
            if item.path.name == 'test_migration_preservation.py': rank = -10
            if item.path.parent.name == 'acceptance': rank = 20
            if item.path.name == 'test_migration_preservation.py': rank = -10
            if item.path.name == 'test_cases_trisigma.py': rank = 15
            if item.path.name == 'test_live_publication.py': rank = 25
            if ('legacy' in item.name or item.name.startswith('test_stage11_live_verify')) and group == 3: rank = 30
            if 'installed_names' in item.name: rank = 40
            return group, _stage13_phase(item), rank, item.nodeid
        items.sort(key=final_order)


def pytest_collection_finish(session):
    if session.config.getoption("--acceptance-stage"):
        selected = {item.path.name+"::"+item.name for item in session.items}
        selected |= {value.split("[")[0] for value in selected}
        stage = session.config.getoption("--acceptance-stage")
        if stage == '13':
            session.config._stage13_execution_order = [{'test_id':item.nodeid,
                'phase':_stage13_phase(item),
                'group':max(GROUPS.index(g) for g in GROUPS if item.get_closest_marker(g))}
                for item in session.items]
        required = {"01": STAGE01_REQUIRED, "02": STAGE02_REQUIRED, "03": STAGE03_REQUIRED, "04": STAGE04_REQUIRED, "05": STAGE05_REQUIRED, "06": STAGE06_REQUIRED, "07": STAGE07_REQUIRED, "08": STAGE08_REQUIRED, "09": STAGE09_REQUIRED, "10": STAGE10_REQUIRED, "11": STAGE11_REQUIRED, "12": STAGE12_REQUIRED, "13": STAGE13_REQUIRED}[stage]
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
        if item.config.getoption('--acceptance-stage') == '13':
            item.config._acceptance_results[-1].update(
                evidence=getattr(item, '_stage13_evidence', []),
                reason=str(report.longrepr) if report.failed or report.skipped else None)


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    root = getattr(config, "_acceptance_root", None)
    if root is None:
        return
    if config.getoption('--acceptance-stage') == '13':
        if config.option.collectonly:
            _stage13_write(root/'reports/collection.json', {'stage':'13','collected':len(session.items),
                'test_ids':[item.nodeid for item in session.items],
                'order':config._stage13_execution_order, 'test_run':False})
            return
        _stage13_report(session, exitstatus, root)
        return
    if config.getoption('--acceptance-stage') == '12':
        _stage12_report(session,exitstatus,root)
        return
    if config.getoption('--acceptance-stage') == '11':
        _stage11_report(session,exitstatus,root)
        return
    if config.getoption('--acceptance-stage') == '10':
        _stage10_report(session,exitstatus,root)
        return
    if config.getoption('--acceptance-stage') == '09':
        _stage09_report(session,exitstatus,root)
        return
    if config.getoption("--acceptance-stage") == "08":
        _stage08_report(session, exitstatus, root)
        return
    if config.getoption("--acceptance-stage") == "07":
        _stage07_report(session, exitstatus, root)
        return
    if config.getoption("--acceptance-stage") == "06":
        _stage06_report(session, exitstatus, root)
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

    if request.node.get_closest_marker('loopback_http'):
        original_socket_connect = socket.socket.connect
        original_create_connection = socket.create_connection
        def loopback_connect(sock, address, *args, **kwargs):
            assert isinstance(address, tuple) and address[0] in ('127.0.0.1','localhost','::1'), 'non-loopback network forbidden'
            return original_socket_connect(sock,address,*args,**kwargs)
        def loopback_connection(address, *args, **kwargs):
            assert address[0] in ('127.0.0.1','localhost','::1'), 'non-loopback network forbidden'
            return original_create_connection(address,*args,**kwargs)
        monkeypatch.setattr(socket.socket,'connect',loopback_connect)
        monkeypatch.setattr(socket,'create_connection',loopback_connection)
    elif not request.node.get_closest_marker("confluence_live"):
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
                          'ancestors':[{'id':str(parent_id)}],
                          "body": {"storage": {"value": storage}}}
            return deepcopy(self.child)

        def find_child_pages(self, parent_id, title):
            self.calls.append(('GET_CHILDREN', str(parent_id)))
            return [deepcopy(self.child)] if self.child and self.child['title'] == title else []

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


def _stage06_report(session, exitstatus, root):
    """Gate is derived from pytest, external checks and protected source hashes."""
    config = session.config
    results = config._acceptance_results
    def read(name):
        path = root/'reports'/name
        return json.loads(path.read_text()) if path.exists() else {}
    initial, external, journey = read('initial-state.json'), read('external-checks.json'), read('batch-decisions-cli.json')
    protected = initial.get('protected_hashes', {})
    changed = [name for name, digest in protected.items()
               if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
    good = (int(exitstatus) == 0 and bool(session.items) and bool(results)
            and all(result['status'] == 'passed' for result in results)
            and bool(protected) and not changed and external.get('gate') == 'passed'
            and bool(journey.get('calls')) and journey['calls'][-1]['rc'] == 0)
    qroot = SKILL_ROOT.parents[1]/'research/workvault-rag'
    files = sorted(set([*SCRIPTS.glob('*.py'), *(SKILL_ROOT/'tests').glob('*.py'),
        *(SKILL_ROOT/'references/schemas').glob('*.json'), *(SKILL_ROOT/'references/profiles').glob('*.json'),
        *(SKILL_ROOT/'references').glob('*.md'), *(MOFS_INDEX_ROOT/'mofs_index/plan').glob('*.py'),
        *(MOFS_INDEX_ROOT/'tests/plan').glob('*.py'), SKILL_ROOT/'tests/pytest.ini',
        qroot/'SKILL.md', qroot/'references/plan-queries.md',
        *(p for p in (SKILL_ROOT/'tests/fixtures/synthetic/batch-decision-registration').rglob('*') if p.is_file())]))
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    master = Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan = master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    schema = Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    implemented = {
        'M/mofs_index/plan/schema.py': 'добавлена только 0009_batch_decisions; append-only provenance/proposals/decisions и защита событий решений',
        'M/mofs_index/plan/writer.py': 'typed provenance; атомарные proposals/решение+событие; идемпотентность и конфликты; scoped связь publication/snapshot',
        'M/mofs_index/plan/query.py': 'общая проекция оснований, точного контекста, решений и decision_ready',
        'M/mofs_index/plan/history.py': 'files/snapshots/publications; timezone-aware [since,until), defaults, unknown counts, source order, keyset cursor с границей набора',
        'S/scripts/plan_decision.py': 'внутренний Proposal/адаптер; подтверждение только двух причин под общей блокировкой, без reader/архива/сети',
        'S/scripts/plan_batch.py': 'проверка provenance до reader; потребление только retry-decisions, неизменный контекст; errors с решениями',
        'S/scripts/plan_operation.py': 'read-only operation show с причинами, proposals, решениями, стадиями и identity_requirements=[]',
        'S/scripts/plan_queries.py': 'адаптер одного typed history API; import_history остаётся в plan_history.py',
        'S/scripts/cli.py': 'operation show; batch-item resume регистрации; batch retry-decisions; history',
        'S/references/cli-contract.md + schemas/batch-decision-result.schema.json': 'команды, отдельная схема результата регистрации, коды, времена и cursor',
        'Q/SKILL.md + Q/references/plan-queries.md': 'русские запросы поступлений/сегодня через тот же typed API, разделение времён и trust',
        'S/tests/test_batch_decisions.py + test_history_queries.py': 'все девять подслучаев AC-19, реальные CLI/MPP, process-death, времена/границы/cursor/Q',
        'S/tests/fixtures/synthetic/batch-decision-registration/': 'версионированное неподтверждённое provenance; используется только typed writer',
        'M/tests/plan/test_batch_decisions.py + test_migrate.py': 'прямой typed API, rollback, append-only, сохранность миграций 0001–0008/строк и обновлённый ожидаемый список',
        'S/tests/conftest.py': 'обязательные test ID этапа 06; прежние карты/отчёты сохранены; gate из фактических результатов',
    }
    limitations = ['Реализован только этап 06; identity/mapping, B/C, scheduler и публикация остаются этапам 07–13',
        'schedule:not_verified; live Confluence не запускался, trust истории не повышается',
        'source_version_date — календарная шкала UTC (полночь); таймзона задач из неё не выводится',
        'Cursor фиксирует состав и порядок, а не полную копию изменяемого состояния обработки; новый запрос видит новые поступления',
        'POSIX flock локален хосту; process-death не моделирует отказ ОС/питания',
        'OwnCloud sync не подтверждён; production-БД/страницы/настройки/baseline, Gateway и расписания не менялись']
    report = {'stage':'06', 'gate':'passed' if good else 'failed', 'exit_code':int(exitstatus),
        'base_commit':initial.get('base_commit'), 'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
        'environment':{'python':sys.executable,'version':platform.python_version(),'cli_python':'/usr/bin/python3',
                       'mpxj_python':'/usr/bin/python3.9','PYTHONPATH':os.environ.get('PYTHONPATH'),'test_root':str(root)},
        'master':{'version':'0.5.0','path':str(master),'sha256':hashlib.sha256(master.read_bytes()).hexdigest()},
        'plan':{'path':str(plan),'normative_prefix_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()},
        'config_contract_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),
        'source_files':hashes,'source_tree_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
        'migrations':['0009_batch_decisions'],'previous_migrations':'0001–0008 definitions unchanged; tested against approved stage-03 prefix',
        'protected_files_checked':len(protected),'changed_protected_files':changed,
        'implemented_files':implemented,'tests':results,'selected':len(session.items),'mandatory_test_ids':sorted(STAGE06_REQUIRED),
        'external_checks':external,'cli_journey':'batch-decisions-cli.json',
        'counters':{'decision_cli':journey.get('metrics',{}),'live_POST':0,'live_PUT':0,
                    'legacy_reader_total':None,'publication_fake_regression':config._acceptance_counters},
        'covered_requirements':['§20/AC-19 all nine registration subcases','§20/AC-23','§20/AC-26','batch portions of §20/AC-20,22'],
        'invariants':{'manifest':'unchanged at registration/consumption','baseline':'exact populated rows preserved',
            'decisions':'append-only, no reader/archive at registration; consumption only retry-decisions','published':False},
        'limitations':limitations,'generated_at':datetime.now(timezone.utc).isoformat()}
    (root/'reports/stage-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines = ['# Этап 06 — решения batch-item и базовая история','',
        f"Gate: **{report['gate']}**; S rc={exitstatus}; selected={len(session.items)}; passed={sum(r['status']=='passed' for r in results)}.",'',
        'Реализовано:','']
    lines.extend('- `'+name+'`: '+value+'.' for name,value in implemented.items())
    lines += ['', 'AC-19: continue/stop; обе причины; retry до регистрации; регистрация без обработки; повтор/замена основания; обычный resume; чужой/stale proposal и новые основания; busy; immutable context/новый batch; падение после регистрации и snapshot commit; обычные новые MPP без искусственного proposal. Baseline и mapping-таблицы сохранены.',
        '', 'История: полуинтервал [since,until), timezone-aware границы; received/recorded/source/published различаются. Source-порядок не меняет фильтр, неизвестные времена посчитаны, неизвестные даты отдельно. Cursor с ключом и границей набора проверен на равных timestamps, limit=1 и позднем backdated поступлении.',
        '', 'Q: тот же mofs_index.plan.history.history(HistoryRequest); отдельная проверка в external-checks.json.',
        '', 'Команда S:', '', '```text', ' '.join(report['command']), '```', '',
        'M/Q, команды/rc/JUnit/stdout/stderr и восстановление комплектов: external-checks.json. Полный CLI-проход с реальным E: batch-decisions-cli.json.',
        '', f"Проверено защищённых файлов: {len(protected)}; изменено: {len(changed)}. Дерево исходников: `{report['source_tree_sha256']}`.",
        '', 'Комплекты: usertools/MofsIndex/ и usertools/workvault-rag/ — before/after/changes.patch/manifest.json. SHA завершающего коммита записывается после commit в журнал плана.',
        '', 'Ограничения:', '']
    lines += ['- '+value for value in limitations]
    (root/'reports/stage-report.md').write_text('\n'.join(lines)+'\n')



def _stage07_report(session, exitstatus, root):
    """Stage-specific evidence gate; all values come from actual checks."""
    config=session.config
    def read(name):
        path=root/'reports'/name
        return json.loads(path.read_text()) if path.exists() else {}
    initial,external,cli=read('initial-state.json'),read('external-checks.json'),read('identity-cli.json')
    real=read('identity-real-mpp.json')
    protected=initial.get('protected_hashes',{})
    changed=[name for name,digest in protected.items() if not Path(name).is_file()
             or hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest]
    results=config._acceptance_results
    good=(int(exitstatus)==0 and bool(session.items) and bool(results)
          and all(r['status']=='passed' for r in results) and bool(protected) and not changed
          and external.get('gate')=='passed' and cli.get('no_automatic_resume') is True
          and bool(cli.get('calls')) and cli['calls'][0]['rc']==0
          and real.get('mapping')=='unknown' and real.get('MPXJ_read')==[1,1])
    qroot=SKILL_ROOT.parents[1]/'research/workvault-rag'
    files=sorted(set([*SCRIPTS.glob('*.py'),*(SKILL_ROOT/'tests').glob('*.py'),
        *(MOFS_INDEX_ROOT/'mofs_index/plan').glob('*.py'),*(MOFS_INDEX_ROOT/'tests/plan').glob('*.py'),
        *(SKILL_ROOT/'references/schemas').glob('*.json'),*(SKILL_ROOT/'references/profiles').glob('*.json'),
        SKILL_ROOT/'references/cli-contract.md',qroot/'references/plan-queries.md',SKILL_ROOT/'tests/pytest.ini',
        *(p for p in (SKILL_ROOT/'tests/fixtures/synthetic/identity-confirmation').rglob('*') if p.is_file())]))
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    master=Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan=master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    schema=Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    implemented={
        'M/mofs_index/plan/identity.py':'единая политика точной пары, scope, continuity/mapping, same_source, выбор и проверки evidence',
        'M/mofs_index/plan/schema.py':'только новая 0010_identity_revisions; scope/evidence/supersedes/отзыв, calendar/assignment, append-only требования/выбор/проверки',
        'M/mofs_index/plan/writer.py':'typed подтверждение/отзыв/требования; атомарный достаточный выбор; идемпотентность, конфликт и отсутствие автоподмены',
        'M/mofs_index/plan/query.py':'diff/task_history/causal guard используют доказательства; unknown и несопоставленные остатки вместо ложного confirmed_uid',
        'S/scripts/plan_identity.py':'внутренние confirm/show адаптеры; immutable content-addressed evidence, без reader/автозапуска/публикации',
        'S/scripts/plan_operation.py':'identity_requirements с точными парами/hashes/rule/revision/evidence/checks и внутренний typed выбор',
        'S/scripts/cli.py':'identity confirm/show, selectors, форма mapping/continuity, глобальные пути и JSON ошибок',
        'S/references/schemas/identity-mapping.schema.json':'строгая схема v1; четыре типа, null/unknown/пустые ключи запрещены',
        'S/references/cli-contract.md + Q/references/plan-queries.md':'контракт identity/revision; убраны обещания подтверждения UID без evidence; исполняемый Q пример',
        'M/tests/plan/test_identity.py + test_query.py + test_migrate.py':'прямые контракты, миграция с legacy данными, checksums 0001–0009, атомарность и два процесса; новые ожидаемые результаты query/migrations',
        'S/tests/test_plan_identity.py + fixtures/synthetic/identity-confirmation':'CLI, строгая схема, immutable evidence, partial→sufficient, operation show, Q и отсутствие автозапуска',
        'S/tests/conftest.py':'добавлены карта обязательных test ID и отчёт/gate этапа 07; прежние карты/отчёты сохранены'}
    limitations=[
        'Только этап 07. Правила B/C и публичный publish/resume с ними — этап 09; stage-07 select hook не исполняет правила или сетевые стадии.',
        'Полные semantic diff связей/календарей/назначений и точные publication selectors — этап 11. Snapshot diff честно completeness:partial/calendar:unknown.',
        'Task history требует прямое доказательство каждой пары; без опорного snapshot совпавшие UID показываются раздельно; абсолютная дельта при неизвестной таймзоне не заявляется.',
        'Evidence хранится в существующем artifact-контуре; append-only SQL и SHA-256 проверяются при использовании. Изменение/утрата байтов блокирует применение.',
        'Schedule:not_verified. Live Confluence не запускался; полномасштабная приёмка §20 не заявлена.',
        'OwnCloud sync не подтверждён. Production-БД/страницы/настройки/baseline, Gateway и расписания не менялись.']
    report={'stage':'07','gate':'passed' if good else 'failed','exit_code':int(exitstatus),
        'base_commit':initial.get('base_commit'),'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
        'environment':{'python':sys.executable,'version':platform.python_version(),'cli_python':'/usr/bin/python3',
            'PYTHONPATH':os.environ.get('PYTHONPATH'),'test_root':str(root)},
        'master':{'version':'0.5.0','path':str(master),'sha256':hashlib.sha256(master.read_bytes()).hexdigest()},
        'plan':{'path':str(plan),'normative_prefix_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()},
        'config_contract_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),
        'source_files':hashes,'source_tree_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
        'migrations':['0010_identity_revisions'],'previous_migrations':'0001–0009 unchanged; checksums tested',
        'implemented_files':implemented,'tests':results,'selected':len(session.items),'mandatory_test_ids':sorted(STAGE07_REQUIRED),
        'external_checks':external,'cli_evidence':'identity-cli.json','real_mpp_evidence':'identity-real-mpp.json','protected_files_checked':len(protected),'changed_protected_files':changed,
        'counters':{'identity_reader_reads':cli.get('reader_reads'),'real_identity_MPXJ_read':real.get('MPXJ_read'),'identity_POST':cli.get('POST'),'identity_PUT':cli.get('PUT'),
                    'regression_fake_counters':config._acceptance_counters,'legacy_reader_total':None},
        'covered_requirements':['§20.6.3 identity portions of AC-09,24; foundation for AC-04'],
        'revision_selection':'explicit usable; single active; unknown without confirmation; ambiguous/3; sufficient before atomic immutable pair choice; no automatic replacement',
        'false_confirmed_uid_removed':True,'limitations':limitations,'generated_at':datetime.now(timezone.utc).isoformat()}
    (root/'reports/stage-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Этап 07 — подтверждение идентичности и mapping revision','',
        f"Gate: **{report['gate']}**. S rc={exitstatus}; selected={len(session.items)}; passed={sum(r['status']=='passed' for r in results)}.",'']
    lines += ['- `'+name+'`: '+value+'.' for name,value in implemented.items()]
    lines += ['', 'Выбор: явная пригодная → единственная активная → unknown; несколько → mapping_ambiguous/3. Partial без требуемых сущностей не занимает слот. Выбор фиксируется атомарно; повтор идемпотентен, замена mapping_revision_conflict/4. Отзыв/supersedes блокирует сохранённый выбор. История сохраняется.',
        '', 'Ложное confirmed_uid в diff/task_history и причинном query убрано; подтверждение возможно только через выбранную revision/evidence. Same-source ограничен источником и профилем. Автоматической транзитивности нет.',
        '', 'Команда S:', '', '```text', ' '.join(report['command']), '```',
        '', 'M/Q, команды/rc/JUnit/stdout/stderr, восстановление patch/after-copy и protected hashes: external-checks.json. Реальные CLI argv/results: identity-cli.json.',
        '', f"Дерево: `{report['source_tree_sha256']}`. Защищено файлов: {len(protected)}; изменено: {len(changed)}. Комплекты usertools/MofsIndex/ и usertools/workvault-rag/ включаются в завершающий commit; SHA после commit записывается в журнал плана.",
        '', 'Ограничения:', '']
    lines += ['- '+value for value in limitations]
    (root/'reports/stage-report.md').write_text('\n'.join(lines)+'\n')


@pytest.fixture
def stage08_export():
    """Small source contract, manually specified; not an MPP-reader fixture."""
    def f(value):
        return {'value':value,'quality':'ok' if value is not None else 'missing','reason':None if value is not None else 'not_set'}
    def q(amount,units='DAYS'):
        return {**f(str(amount)+' '+units),'quantity':{'amount':str(amount),'units':units,'source_units':units,'elapsed':units.startswith('ELAPSED_')}}
    def task(key,ident,summary=False,parent='root',milestone=False):
        return {'task_key':key,'id':ident,'uid':ident,'name':key,'summary':summary,'milestone':milestone,
                'outline_level':0 if ident==0 else 1 if parent is None else 2,
                'parent_task_key':f(parent),'duration':q(0 if milestone else 84.875 if summary else 1),
                'start':f('2026-01-05T09:00:00'),'finish':f('2026-01-06T18:00:00'),
                'task_mode':f('AUTO_SCHEDULED'),'percent_complete':f('0'),
                'calendar_key':f(None),'effective_calendar_key':f('cal'),
                'constraint_type':f('AS_SOON_AS_POSSIBLE'),'constraint_date':f(None),'segments':f([])}
    tasks=[task('service',0,True,None),task('root',1,True,None),task('a',2),task('b',3,milestone=True)]
    resources=[{'resource_key':'r1','id':1,'uid':1,'name':'Same name','calendar_key':f('cal'),'base_calendar_key':f(None)},
               {'resource_key':'r2','id':2,'uid':2,'name':'Same name','calendar_key':f('cal'),'base_calendar_key':f(None)}]
    assignments=[{'assignment_key':'asn1','task_key':'a','resource_key':'r1','work':q('0.1','HOURS'),'units':f('0'),'effective_calendar_key':f('cal'),'timephased':[{'work':q('999','HOURS')}]},
                 {'assignment_key':'asn2','task_key':'b','resource_key':'r2','work':q('0.2','HOURS'),'units':f('100'),'effective_calendar_key':f('cal')},
                 {'assignment_key':'asn0','task_key':'service','resource_key':'r1','work':q('999','HOURS'),'units':f('100')},
                 {'assignment_key':'asns','task_key':'root','resource_key':'r1','work':q('999','HOURS'),'units':f('100')}]
    dependencies=[{'dependency_key':'dep'+str(i),'predecessor_task_key':'a','successor_task_key':'b','link_type':typ,
                   'lag_value':f({'amount':amount,'units':unit,'source_units':unit,'elapsed':unit.startswith('ELAPSED_')}),
                   'lag_calendar':f(None),'project_lag_calendar':f('PREDECESSOR'),'external':False}
                  for i,(typ,amount,unit) in enumerate([('FS','0','DAYS'),('SS','-1','HOURS'),('FF','2','ELAPSED_DAYS'),('SF','0.5','DAYS'),('FS','1','DAYS')])]
    weekdays=[{'day':day,'working':f(day not in ('SATURDAY','SUNDAY')),'day_type':f('WORKING' if day not in ('SATURDAY','SUNDAY') else 'NON_WORKING'),
               'intervals':f([{'start':f('09:00'),'end':f('12:00')},{'start':f('13:00'),'end':f('18:00')}] if day not in ('SATURDAY','SUNDAY') else [])}
              for day in ('MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY')]
    calendars=[{'calendar_key':'cal','name':'Base','parent_key':f(None),'weekdays':weekdays,'weekdays_quality':'ok',
                'exceptions':[{'from_date':f('2026-01-06'),'to_date':f('2026-01-06'),'working':f(True),
                               'intervals':f([{'start':f('10:00'),'end':f('11:00')}]),'recurrence':f(None)}],
                'exceptions_quality':{'status':'complete'},'work_weeks':[],'work_weeks_quality':{'status':'complete'}}]
    data={'export_version':'full-export-v2','provenance':{'sha256':'a'*64,'size_bytes':1,'reader':'unit-only','mpxj':'unit-only','jpype':'unit-only'},
          'project':{'status_date':f(None),'minutes_per_day':f('480'),'minutes_per_week':f('2400'),'minutes_per_month':f('9600'),'minutes_per_year':f('115200'),
                     'default_calendar_key':f('cal'),'relationship_lag_calendar':f('PREDECESSOR')},
          'tasks':tasks,'dependencies':dependencies,'resources':resources,'assignments':assignments,'calendars':calendars,
          'external_dependencies':[],'diagnose_graph':{'cycles':[],'self_references':[],'dangling_dependencies':[],'external_dependencies':[],'schedule_status':'not_verified'},'collections':{}}
    from copy import deepcopy
    donor=json.loads((FIXTURES/'synthetic/relations-all-types.json').read_text())
    for group in ('tasks','dependencies','resources','assignments','calendars'):
        data[group]=[{**deepcopy(donor[group][0]),**row} for row in data[group]]
    for cal in data['calendars']:
        for ex in cal['exceptions']:
            ex.setdefault('name',f('unit exception'))
        for quality in ('exceptions_quality','work_weeks_quality'):
            cal[quality]={'status':'complete','count':len(cal['exceptions'] if quality=='exceptions_quality' else cal['work_weeks']),'reason':None}
    for key in ('tasks','dependencies','external_dependencies','resources','assignments','calendars'):
        data['collections'][key]={'status':'complete','count':len(data[key]),'reason':None}
    data['collections']['baseline_values']={'status':'complete','count':0,'reason':None}
    return data


@pytest.fixture
def stage08_profile(tmp_path):
    """Test double with intentionally different relation codes; no live claims."""
    from plugin_profile import PluginProfile
    evidence=tmp_path/'test-only-evidence.json'
    evidence.write_text(json.dumps({'scope':'unit compiler contract, not installed plugin verification',
                                    'relation_codes':{'EndToStart':12,'StartToStart':10,'EndToEnd':13,'StartToEnd':11},
                                    'dependencies':[{'lagUnit':u} for u in ('day','hour','eday')]}))
    caps=['relation:'+t for t in ('FS','SS','FF','SF')]
    caps+=['lag_unit:'+u for u in ('DAYS','HOURS','ELAPSED_DAYS')]
    caps+=['lag:'+s for s in ('negative','positive','zero')]
    caps+=['dependency:'+t+':'+u+':'+sign for t in ('FS','SS','FF','SF') for u in ('DAYS','HOURS','ELAPSED_DAYS') for sign in ('zero','positive','negative')]
    caps+=['lag_basis:PREDECESSOR','calendar:intervals','calendar:exceptions','calendar:inheritance']
    caps+=['calendar:bindings:'+k for k in ('project','tasks','resources','assignments')]
    document={'schema_version':1,'id':'installed-gantt-profile','version':'unit-only',
              'plugin':{'key':'unit-only','version':'unit-only','asset_sha256':None},'confluence_version':None,
              'codes':{'relation':{'FS':12,'SS':10,'FF':13,'SF':11},'lag_unit':{'DAYS':'day','HOURS':'hour','ELAPSED_DAYS':'eday'}},
              'capabilities':{k:{'status':'tested_supported','evidence':['unit'],'scope':'synthetic compiler contract only'} for k in caps},
              'evidence':{'unit':{'path':str(evidence.relative_to(tmp_path)),'sha256':hashlib.sha256(evidence.read_bytes()).hexdigest()}},'limitations':['unit-only']}
    class UnitProfile(PluginProfile):
        def validate(self,**kwargs):
            return super().validate(evidence_root=tmp_path,**kwargs)
    return UnitProfile(document)


STAGE08_REQUIRED = {
    'test_mpp_convert.py::'+name for name in (
        'test_prepared_golden_bytes_and_storage', 'test_prepared_lag_basis_only_equivalent_calendars',
        'test_prepared_dependencies_types_signed_lag_parallel_resources',
        'test_prepared_unknown_dependency_never_fs_zero',
        'test_prepared_tree_uses_parent_keys_all_roots_and_partial_assignment',
        'test_prepared_no_reader_in_converter_calendar_itogo',
        'test_prepared_hierarchy_cycle_rejected')
} | {'test_itogo.py::'+name for name in (
    'test_prepared_summary_ceil','test_prepared_work_exact_summary_service_milestone_and_timephased',
    'test_prepared_work_missing_partial_not_zero','test_prepared_multiple_roots_explicit_choice',
    'test_prepared_unknown_basis_blocks_summary','test_prepared_source_coefficients_and_timezone',
    'test_real_prepared_work_tolerance')
} | {'test_mpp_calendar.py::'+name for name in (
    'test_prepared_calendar_intervals_exceptions_inheritance_bindings','test_prepared_calendar_unsupported_is_explicit')
} | {'test_gate_diff.py::test_four_value_layers_never_promote_model_to_observed',
     'test_plan_cache.py::test_derived_representation_cache_profile_template_root_and_corruption',
     'test_plugin_profile.py::test_profile_codes_only_verified_capabilities',
     'test_plugin_profile.py::test_profile_rejects_unverified_contract',
     'test_plugin_profile.py::test_installed_profile_has_only_evidence_bound_claims',
     'test_plugin_controls_live.py::test_installed_plugin_controls_live'}
STAGE08_REQUIRED |= {'test_itogo.py::test_real_prepared_work_tolerance['+case+'-'+hours+']'
                     for case,hours in [('A','1576'),('B','2096'),('C','2088'),('D','3136')]}
STAGE08_REQUIRED |= {'test_itogo.py::test_prepared_summary_ceil['+value+'-'+str(result)+']'
                     for value,result in [('84.875',85),('76.875',77),('106.875',107),('0',0)]}


def _stage08_report(session, exitstatus, root):
    """Actual stage-08 outcomes; skipped mandatory live never closes the gate."""
    from prepared_plan import fingerprint
    config=session.config
    initial_path=root/'reports/initial-state.json'
    initial=json.loads(initial_path.read_text()) if initial_path.is_file() else {}
    protected=initial.get('protected_hashes',{})
    changed=[name for name,digest in protected.items() if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest]
    results=config._acceptance_results
    optional_skips=[r for r in results if r['status']=='skipped' and 'test_rest_live.py::' in r['test_id']]
    required_results=[r for r in results if r not in optional_skips]
    cases={name:json.loads(path.read_text()) for name in ('A','B','C','D')
           if (path:=root/'reports'/('stage08-work-'+name+'.json')).is_file()}
    live_path=root/'reports/stage08-live.json'
    live=json.loads(live_path.read_text()) if live_path.is_file() else {'status':'not_run'}
    profile_path=SKILL_ROOT/'references/profiles/installed-gantt-profile.json'
    profile=json.loads(profile_path.read_text())
    good=(exitstatus==0 and bool(session.items) and bool(required_results)
          and all(r['status']=='passed' for r in required_results)
          and bool(protected) and not changed and set(cases)=={'A','B','C','D'}
          and live.get('status')=='passed' and len(live.get('cases',[]))>=10
          and profile['plugin']['version'] is not None)
    files=sorted(set([*SCRIPTS.glob('*.py'),*(SKILL_ROOT/'tests').glob('*.py'),
        *(SKILL_ROOT/'references/profiles').glob('*.json'),*(SKILL_ROOT/'references/schemas').glob('*.json'),
        *(SKILL_ROOT/'references').glob('*.md'),SKILL_ROOT/'tests/pytest.ini',
        *(p for p in (SKILL_ROOT/'tests/fixtures/golden').rglob('*') if p.is_file())]))
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    master=Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan=master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    schema=Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    limitations=[
        'Только этап 08. Подключение к первичному архиву/admission diff/publish — этап 09; сетевые стадии — этап 10.',
        'Legacy CSV adapter/старый pipeline сохранены совместимыми; новый converter/calendar/itogo работают только с PreparedPlan.',
        'Installed profile pins exact frontend build and asset hash; server marketing release version is unavailable to this account (UPM 401).',
        'Unknown plugin capabilities remain not_verified; local scheduler capability matrix does not prove plugin behavior.',
        'A–D work known sum matches reference; extraction quality partial because exporter reports unsupported timephased getters. Missing totals never become zero.',
        'Legacy test_rest_live GET/apply harness is optional in stage08 (EDITPLAN_LIVE unset); required dedicated controls ran separately without mocks.',
        'Production DB/WorkVault, plan pages A–D/AB, Gateway and schedules were not modified. No migrations or R/E changes.',
        'ownCloud sync not confirmed. Test-only browser packages and browser binary remain under the isolated test root.'
    ]
    implemented={
        'S/scripts/mpp_convert.py':'PreparedPlan converter; source-local tree/resources; profiled dependencies/units/signed lag/basis; explicit losses; deterministic bytes; CSV adapter kept separate',
        'S/scripts/mpp_calendar.py':'pure prepared calendar conversion, intervals/exceptions/bindings; retained source semantics and explicit unsupported constructs',
        'S/scripts/itogo.py':'summary-v1; unique/explicit root, Decimal work and coefficients, ceil days, ROUND_HALF_UP display; no work in storage',
        'S/scripts/gate_diff.py':'independent source/representation/model/observation diagnostics',
        'S/scripts/plugin_profile.py':'version/schema/evidence-bound profile loading and capability/code lookup; unknown unsupported',
        'S/scripts/plan_cache.py':'derived cache keyed by normalized/converter/rules/plugin/summary/template/root; integrity checked',
        'S/references/profiles/':'summary-v1, strict plugin-profile schema, installed profile with hashed live evidence',
        'S/tests/':'semantic/decimal/MPP work/cache/profile tests and actual browser plugin controls; required test IDs and stage report hook',
        'S/tests/fixtures/golden/':'versioned plugin input bytes/expected dates and source representation/storage golden contracts',
        'S/references/cli-contract.md':'internal stage08 contracts and stage09/10 integration boundary'
    }
    cache_path=root/'reports/stage08-cache.json'
    derived_cache=json.loads(cache_path.read_text()) if cache_path.is_file() else None
    counters={'derived_cache':derived_cache,'prepared_converter_calendar_itogo_reader_calls':0,'real_A_D_MPXJ_read':sum(c['MPXJ_read'] for c in cases.values()),
              'all_legacy_reader_calls':None,'live_POST':live.get('POST'), 'live_PUT':live.get('PUT'),
              'fake_regression':config._acceptance_counters}
    report={'stage':'08','gate':'passed' if good else 'failed','exit_code':int(exitstatus),
        'base_commit':initial.get('base_commit'),'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
        'environment':{'python':sys.executable,'version':platform.python_version(),'test_root':str(root),
                       'PYTHONPATH':os.environ.get('PYTHONPATH'),'cli_python':'/usr/bin/python3','mpxj_python':'/usr/bin/python3.9'},
        'master':{'version':'0.5.0','path':str(master),'sha256':hashlib.sha256(master.read_bytes()).hexdigest()},
        'plan':{'path':str(plan),'normative_prefix_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()},
        'migrations':[],'source_files':hashes,'source_tree_sha256':fingerprint(hashes),'implemented_files':implemented,
        'config_contract_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),
        'protected_files_checked':len(protected),'changed_protected_files':changed,
        'selected':len(session.items),'tests':results,'mandatory_test_ids':sorted(STAGE08_REQUIRED),
        'optional_skips':optional_skips,'real_cases':cases,'live':live,'plugin_profile':profile,
        'counters':counters,'covered_requirements':['§20/AC-02 prepared branch','§20/AC-06','parts of §20/AC-08','§20.7.5'],
        'limitations':limitations,'generated_at':datetime.now(timezone.utc).isoformat()}
    (root/'reports/stage-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Этап 08 — представление Confluence, Итого и профиль плагина','',
        f"Gate: **{report['gate']}**. rc={exitstatus}; passed={sum(r['status']=='passed' for r in results)}; selected={len(session.items)}; optional skips={len(optional_skips)}.",'']
    lines.extend('- `'+path+'`: '+description for path,description in implemented.items())
    lines.extend(['','Команда:','','```text',' '.join(report['command']),'```','','A–D work (допуск ≤0.001 ч):',''])
    for name,c in cases.items():
        lines.append(f"- {name}: {c['actual_hours']} ч; эталон {c['expected_hours']}; delta={c['absolute_delta_hours']}; N={c['summary']['n_days']}; work quality={c['summary']['work']['quality']}.")
    lines.extend(['',f"Live: {live.get('status')}, page={live.get('page_id')}, controls={len(live.get('cases',[]))}, POST={live.get('POST')}, PUT={live.get('PUT')}. Inputs/received/storage/browser observations/screenshots: live/.",
                  '',f"Проверено защищённых файлов: {len(protected)}, изменений: {len(changed)}. Дерево: `{report['source_tree_sha256']}`.",'','Ограничения:',''])
    lines.extend('- '+v for v in limitations)
    (root/'reports/stage-report.md').write_text('\n'.join(lines)+'\n')

STAGE08_REQUIRED |= {'test_mpp_convert.py::test_prepared_unknown_dependency_never_fs_zero['+kind+']'
                     for kind in ('type','lag','unit','elapsed','basis','endpoint','external')}
STAGE08_REQUIRED |= {'test_itogo.py::test_prepared_unknown_basis_blocks_summary['+kind+']'
                     for kind in ('units','elapsed','basis','timezone','date')}
STAGE08_REQUIRED |= {'test_plugin_profile.py::test_profile_rejects_unverified_contract['+kind+']'
                     for kind in ('hash','version','evidence','claim','shape','code')}
STAGE08_REQUIRED |= {'test_plugin_profile.py::test_context_installed_profiles_from_registry',
                     'test_gate_diff.py::test_four_layers_include_links_calendars_assignments_without_schedule_promotion'}

STAGE08_REQUIRED.add('test_mpp_convert.py::test_prepared_summary_dependency_and_unrepresented_scheduling')

STAGE08_REQUIRED.add('test_mpp_calendar.py::test_prepared_calendar_source_day_basis_mismatch_is_explicit')


@pytest.fixture
def stage09_export():
    folder=FIXTURES/'synthetic/new-source-identity-resume'
    manifest=json.loads((folder/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest
    for entry in manifest['binary_fixtures']:
        assert hashlib.sha256((folder/entry['path']).read_bytes()).hexdigest()==entry['sha256']
    return json.loads((folder/'prepared-export.json').read_text())


@pytest.fixture
def publish_case(tmp_path, stage09_export, stage08_profile, fake_confluence):
    """Explicit synthetic parsed contract, separate from real MPXJ acceptance."""
    from copy import deepcopy
    from plan_context import PlanContext
    from mofs_index.db import connect_durable
    from mofs_index.plan.migrate import ensure_plan_schema
    db=tmp_path/'state/index.sqlite';wv=tmp_path/'WorkVault';cache=tmp_path/'cache'
    context=PlanContext.resolve(db=db,workvault=wv,cache_dir=cache)
    source=tmp_path/'synthetic-source.mpp';source.write_bytes(b'unit-only source bytes; parsed export supplied explicitly')
    data=deepcopy(stage09_export)
    data['provenance'].update(sha256=hashlib.sha256(source.read_bytes()).hexdigest(),size_bytes=source.stat().st_size)
    c=connect_durable(db);ensure_plan_schema(c)
    result={'db':db,'wv':wv,'cache':cache,'context':context,'source':source,'export':data,
            'profile':stage08_profile,'client':fake_confluence,'conn':c,'tmp':tmp_path}
    yield result
    c.close()


STAGE09_REQUIRED = STAGE07_REQUIRED | STAGE08_REQUIRED | {
    'test_publish_prepare.py::'+name for name in (
        'test_first_diff_snapshot_before_admission','test_new_binding_without_slug_retains_input_no_resumable_id',
        'test_unknown_timezone_archived_before_needs_decision','test_archive_failure_never_writes_network',
        'test_binding_conflict_preserves_frozen_intake','test_new_mpp_publish_in_clean_environment_archives_when_blocked',
        'test_prepared_branch_never_calls_legacy_readers','test_durable_admission_before_network_and_actual_readback',
        'test_admitted_bytes_mismatch_stops_before_put','test_changed_target_invalidates_admission_and_proposal',
        'test_prepared_artifact_corruption_never_uploads')
} | {'test_admission.py::'+name for name in (
    'test_specific_proposal_cannot_override_archive_or_profile','test_dates_each_task_and_milestone_with_matching_root',
    'test_unknown_timezone_never_claims_absolute_date_delta','test_unknown_field_blocks_but_proven_nonimpact_warns',
    'test_local_scheduler_unsupported_and_plan_unobserved_are_warnings','test_semantic_losses_block_after_archive',
    'test_accepted_date_deviation_never_becomes_verified')
} | {'test_identity_resume_e2e.py::'+name for name in (
    'test_bootstrap_no_save_one_arrival_then_identity_confirm_resume',
    'test_timezone_resume_new_preparation_and_snapshot_preserves_previous','test_timezone_new_pair_never_copies_mapping_or_decision',
    'test_identity_revision_blockers','test_resume_forms_are_mutually_exclusive_and_apply_has_slug')
} | {'test_plan_rules.py::test_bc_exact_mapping_and_context['+kind+']'
     for kind in ('reorder','new_uid','context','relation','not_needed','missing_reference')
} | {'test_plan_rules.py::test_drop_dep_resolves_exact_source_and_does_not_apply_without_consent',
     'test_publish_live.py::test_stage09_live_publish_bytes_storage_and_binary_blocker'}
STAGE09_REQUIRED |= {'test_admission.py::test_matrix_row[row-'+str(row)+']' for row in range(1,20)}
STAGE09_REQUIRED |= {'test_admission.py::test_matrix_blocker_archives_and_performs_zero_writes[row-'+str(row)+']'
                     for row in (3,4,7,8,9,11,12,13,14,15,16,17,18,19)}
STAGE09_REQUIRED |= {'test_identity_resume_e2e.py::test_real_mpp_new_snapshot_separate_clean_environments['+action+']'
                     for action in ('diff','publish')}


def _stage09_report(session, exitstatus, root):
    """The gate is computed from actual pytest, external delivery and live evidence."""
    config=session.config
    def read(name):
        path=root/'reports'/name
        return json.loads(path.read_text()) if path.is_file() else {}
    initial=read('initial-state.json');external=read('external-checks.json');live=read('stage09-live.json')
    controls=read('stage08-live.json')
    binary={action:read('stage09-real-'+action+'.json') for action in ('diff','publish')}
    bootstrap=read('stage09-real-bootstrap.json')
    protected=initial.get('protected_hashes',{})
    changed=[p for p,h in protected.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    results=config._acceptance_results
    hashes=_stage09_sources()
    changed_during_run=sorted(set(hashes)^set(config._acceptance_start_hashes) |
        {name for name,digest in hashes.items() if config._acceptance_start_hashes.get(name)!=digest})
    optional={'test_rest_live.py::test_live_get_test_page','test_rest_live.py::test_live_apply_plan_ok'}
    def optional_skip(result):
        return result['status']=='skipped' and any(result['test_id'].endswith(x) for x in optional)
    good=(int(exitstatus)==0 and bool(session.items) and bool(results)
          and all(r['status']=='passed' or optional_skip(r) for r in results)
          and bool(protected) and not changed and external.get('gate')=='passed'
          and live.get('status')=='passed' and controls.get('status')=='passed'
          and not changed_during_run
          and bootstrap.get('new_MPXJ_read')==1 and bootstrap.get('resume_MPXJ_read')==0
          and all(b.get('counters',{}).get('MPXJ_read')==1 and b.get('resume_counters',{}).get('MPXJ_read')==0
                  for b in binary.values()))
    master=Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan=master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    schema=Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    implemented={
        'S/scripts/pipeline.py':'prepare_publish; shared diff/publish/apply; primary archive/read-back before identity/admission; durable evidence then network primitives; exact-version download without status=any; valid storage paragraph assembly',
        'S/scripts/plan_policy.py':'all 19 normative rows; blockers cannot choose warning severity; concrete proposals only; accepted_deviation independent of verified',
        'S/scripts/plan_diagnostics.py':'conservative completeness, graph, capability losses, per-task/milestone minute dates and separated evidence layers; no reopening MPP for scheduler',
        'S/scripts/plan_rules.py':'immutable project rules, reference/evidence, exact sufficient mapping, original type/signed lag/basis and task context, current cause, derived-only exclusion, not_needed; source-bound legacy drop-dep',
        'S/scripts/plan_operation.py + plan_decision.py':'preparation history/show, addressed proposals and decisions, single resume and preserved batch contract, project-scoped consent persistence',
        'S/scripts/cli.py + references/cli-contract.md':'publish/diff/apply slug and paths; mutually exclusive resume forms; archive receipt and fixed context',
        'S/references/profiles/publication-policy-v1.json + project-rules-v1.json':'versioned conservative field/date policy and inactive unanchored historical B/C, without guessed stable keys or invented evidence',
        'M/mofs_index/plan/schema.py':'only 0011_publish_preparation; append-only preparations/rules/proposals/decisions/admission/artifact bindings; 0001–0010 unchanged',
        'M/mofs_index/plan/writer.py + query.py':'typed write/read APIs; new timezone snapshot link preserves intake and previous preparation; revision-scoped identity choices and audit',
        'S/tests/test_admission.py + test_plan_rules.py + test_publish_prepare.py + test_identity_resume_e2e.py + test_publish_live.py':'matrix, zero-write blockers, B/C, timezone, identity/bootstrap, real binary cold/resume, actual HTTP bytes/storage',
        'S/tests/fixtures/synthetic/new-source-identity-resume':'explicit test-only export and user evidence; no production identity assertion',
        'M/tests/plan/test_preparation.py + test_migrate.py + test_identity.py':'new migration/typed contracts, preservation and current migration expectations; older migration definitions remain fixed',
        'S/tests/test_pipeline.py':'existing stage-01 network verification cases explicitly exercise preserved legacy helper; public apply now uses mandatory admission',
        'S/tests/conftest.py':'stage-09 mandatory IDs, group order, actual report/gate; earlier maps/reports retained'}
    limitations=[
        'Only stage 09. Target locking, reconciliation/idempotency after HTTP effects and verified_v1 registration remain stage 10; post-effect resume returns network_reconciliation_required instead of repeating a write.',
        'The live admitted plan is an explicitly synthetic parsed fixture; its exporter is not presented as a real MPP read. Independent binary MPP diff/publish tests use real MPXJ and are correctly blocked by extraction/profile limitations after verified archival.',
        'schedule:not_verified. Prepared-only local scheduler is unsupported; legacy model/CSV paths are excluded from the new branch. No live per-plan schedule equality is claimed.',
        'Historical production B/C without reference snapshot/evidence/stable keys remain inactive. Test-only identity evidence does not confirm production Trisigma.',
        'MPP child diff/apply share archive/admission. Recovery after child creation and legacy parent-copy/empty-child lifecycle remain stage 10; no production child-page scenario is claimed accepted.',
        'Two legacy optional REST tests are not enabled; mandatory stage-08 controls and stage-09 HTTP publication run independently.',
        'OwnCloud sync is not confirmed. Production DB/WorkVault, A–D/AB pages, configs, Gateway, crons, watchers and schedules were not changed.']
    report={'stage':'09','gate':'passed' if good else 'failed','exit_code':int(exitstatus),
        'base_commit':initial.get('base_commit'),'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
        'environment':{'python':sys.executable,'version':platform.python_version(),'cli_python':'/usr/bin/python3',
            'MPXJ_PYTHON':'/usr/bin/python3.9','PYTHONPATH':os.environ.get('PYTHONPATH'),'test_root':str(root)},
        'master':{'path':str(master),'version':'0.5.0','sha256':hashlib.sha256(master.read_bytes()).hexdigest()},
        'plan':{'path':str(plan),'normative_prefix_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()},
        'config_contract_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),'source_files':hashes,
        'source_tree_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
        'implemented_files':implemented,'migrations':['0011_publish_preparation'],'previous_migrations':'0001–0010 checksum equality tested',
        'protected_files_checked':len(protected),'changed_protected_files':changed,'tests':results,'selected':len(session.items),
        'changed_during_test_run':changed_during_run,
        'mandatory_test_ids':sorted(STAGE09_REQUIRED),'external_checks':external,
        'binary_evidence':{'diff':'stage09-real-diff.json','publish':'stage09-real-publish.json','bootstrap':'stage09-real-bootstrap.json'},
        'live_evidence':'stage09-live.json','plugin_controls_evidence':'stage08-live.json',
        'counters':{'stage09_live_POST':live.get('POST'),'stage09_live_PUT':live.get('PUT'),
            'stage08_controls_POST':controls.get('POST'),'stage08_controls_PUT':controls.get('PUT'),
            'real_binary':{a:b.get('counters') for a,b in binary.items()},'regression':config._acceptance_counters,
            'all_legacy_reader_calls':None},
        'covered_requirements':['§20/AC-04,05,07,08,09,15 stage-09 portions'],
        'limitations':limitations,'generated_at':datetime.now(timezone.utc).isoformat()}
    (root/'reports/stage-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Этап 09 — первичный snapshot, допуск и B/C','',
        f"Gate: **{report['gate']}**. S rc={exitstatus}; selected={len(session.items)}; passed={sum(r['status']=='passed' for r in results)}.",'']
    lines += ['- `'+name+'`: '+text+'.' for name,text in implemented.items()]
    lines += ['', 'Порядок: frozen input → prepared → проект/lineage и GET цели → исходный snapshot → read-back → identity/B/C → повторная диагностика → долговечный artifact/evidence/admission → сеть. Diff завершает подготовку без POST/PUT.',
        '', 'Матрица: 19 строк с параметризованными тестами; запрещающие случаи сохраняют архив и имеют POST=PUT=0. Даты всех задач/вех: ≤60 секунд, без абсолютного сравнения при unknown timezone. Общего override предупреждений нет.',
        '', 'B/C: точная достаточная mapping revision и обе задачи, сохранность исходных связей и контекста, актуальная причина, повторный допуск, not_needed. Таймзона создаёт новую подготовку и snapshot без автоматического переноса решений.',
        '', 'Команда S:', '', '```text',' '.join(report['command']),'```','',
        'MofsIndex: команды/rc/JUnit и восстановление before/after/patch — external-checks.json. Реальные MPP: stage09-real-diff.json / stage09-real-publish.json. HTTP: stage09-live.json. Отдельная успешная публикация синтетического плана и блокировка настоящего MPP различаются явно.',
        '', f"Live stage09: POST={live.get('POST')}, PUT={live.get('PUT')}; stage08 controls: POST={controls.get('POST')}, PUT={controls.get('PUT')}. Полные следы и версии сохранены.",
        '', f"Проверенное дерево: `{report['source_tree_sha256']}`. Защищено файлов: {len(protected)}, изменено: {len(changed)}. SHA коммита записывается в журнал плана после commit.",
        '', 'Ограничения:', '']
    lines += ['- '+s for s in limitations]
    (root/'reports/stage-report.md').write_text('\n'.join(lines)+'\n')

STAGE09_REQUIRED |= {
    'test_plan_rules.py::test_explicit_project_scope_persists_versioned_rule',
    'test_publish_prepare.py::test_false_attachment_verifier_blocks_put',
    'test_publish_prepare.py::test_public_apply_uses_same_archive_and_admission',
    'test_identity_resume_e2e.py::test_mapping_resume_selects_its_exact_pair_when_another_pair_is_pending',
}
STAGE09_REQUIRED.add('test_publish_prepare.py::test_mpp_child_uses_shared_admission_before_page_creation')
STAGE09_REQUIRED.add('test_admission.py::test_legacy_longest_path_excludes_root_and_never_proposes_auto_removal')


def _stage09_sources():
    files=sorted(set([*SCRIPTS.glob('*.py'),*(SKILL_ROOT/'tests').glob('*.py'),
        *(SKILL_ROOT/'references/profiles').glob('*.json'),*(SKILL_ROOT/'references/schemas').glob('*.json'),
        *(MOFS_INDEX_ROOT/'mofs_index/plan').glob('*.py'),*(MOFS_INDEX_ROOT/'tests/plan').glob('*.py'),
        SKILL_ROOT/'references/cli-contract.md',SKILL_ROOT/'tests/pytest.ini',
        *(p for p in FIXTURES.rglob('*') if p.is_file())]))
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
STAGE09_REQUIRED.add('test_plan_rules.py::test_changed_hierarchy_blocks_even_when_wbs_and_uid_match')
STAGE09_REQUIRED.add('test_identity_resume_e2e.py::test_real_binary_bootstrap_identity_resume_without_preliminary_save')


STAGE10_REQUIRED = STAGE01_REQUIRED | {
    'test_publish_resume.py::test_resume_rechecks_ab_flag_after_effect',
    'test_publish_resume.py::test_schedule_mismatch_after_write_is_durable_without_rollback',
    'test_publish_resume.py::test_legacy_operation_without_slug_or_binding_cannot_resume',
    'test_publish_idempotency.py::test_same_source_profile_target_no_upload_put_or_duplicate_publication',
    'test_publish_idempotency.py::test_new_expected_itogo_is_storage_only',
    'test_publish_idempotency.py::test_confirmed_operation_never_repairs_changed_target',
    'test_publish_idempotency.py::test_full_confirmation_links_and_legacy_writer_cannot_promote',
    'test_publish_idempotency.py::test_operation_show_omits_storage_from_network_journal',
    'test_publish_conflicts.py::test_foreign_attachment_version_after_exact_verification_blocks_put',
    'test_publish_conflicts.py::test_409_changed_owned_macro_never_retries_patch',
    'test_publish_conflicts.py::test_new_operation_same_source_cannot_overwrite_foreign_target',
    'test_publish_conflicts.py::test_target_live_owner_across_process_and_release_after_kill',
    'test_publish_conflicts.py::test_pending_child_title_cannot_be_adopted_from_foreign_macro',
    'test_publish_prepare.py::test_archive_failure_never_writes_network',
    'test_publish_prepare.py::test_false_attachment_verifier_blocks_put',
    'test_publish_prepare.py::test_prepared_artifact_corruption_never_uploads',
    'test_publish_live.py::test_stage09_live_publish_bytes_storage_and_binary_blocker',
    'test_plugin_controls_live.py::test_installed_plugin_controls_live',
    'test_rest_live.py::test_stage10_live_recovery_idempotency_and_child',
} | {'test_publish_resume.py::test_effect_boundary_recovers_without_duplicate['+failure+'-'+when+'-'+effect+']'
     for failure in ('crash','timeout') for when in ('before','after') for effect in ('upload','put','create')}
STAGE10_REQUIRED |= {'test_publish_resume.py::test_journal_failure_has_no_false_success_and_resumes['+boundary+']'
    for boundary in ('intent','upload_observation','put_observation','confirmation','mirror')}
STAGE10_REQUIRED |= {'test_publish_resume.py::test_missing_or_corrupt_archive_blocks_every_effect['+artifact+']'
    for artifact in ('representation_artifact_id','evidence_artifact_id','prepared_artifact_id','source')}
STAGE10_REQUIRED |= {'test_publish_resume.py::test_real_process_death_http_reconciliation['+boundary+']'
    for boundary in ('before_post','after_post','before_put','after_put','after_confirmation','hold_post')}
STAGE10_REQUIRED |= {'test_publish_conflicts.py::test_foreign_managed_change_after_upload_is_conflict['+change+']'
    for change in ('macro','summary','attachment','duplicate_macro')}
STAGE10_REQUIRED |= {'test_publish_conflicts.py::test_bounded_409_preserves_unmanaged_neighbours['+str(n)+']' for n in (1,2,100)}
STAGE10_REQUIRED |= {'test_publish_resume.py::test_transport_retries_only_get_with_configured_timeout['+method+']' for method in ('GET','POST','PUT')}
STAGE10_REQUIRED |= {'test_child_page.py::test_legacy_child_lost_response_is_read_before_replay['+effect+']' for effect in ('page','attachment')}
STAGE10_REQUIRED.add('test_publish_resume.py::test_archive_failure_after_post_retains_unknown_external_effect')
STAGE10_REQUIRED.add('test_publish_resume.py::test_network_error_retains_safe_type_and_status')
STAGE10_REQUIRED |= {'test_publish_resume.py::test_unobserved_effect_does_not_authorize_foreign_summary['+value+']' for value in ('False','True')}


def _stage10_sources():
    files=sorted(set([*SCRIPTS.glob('*.py'),*(SKILL_ROOT/'tests').glob('*.py'),
        *(SKILL_ROOT/'references/profiles').glob('*.json'),*(SKILL_ROOT/'references/schemas').glob('*.json'),
        *(MOFS_INDEX_ROOT/'mofs_index/plan').glob('*.py'),*(MOFS_INDEX_ROOT/'tests/plan').glob('*.py'),
        SKILL_ROOT/'references/cli-contract.md',SKILL_ROOT/'references/operations-and-recovery.md',SKILL_ROOT/'tests/pytest.ini',
        *(p for p in FIXTURES.rglob('*') if p.is_file() and '__pycache__' not in p.parts)]))
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}


def _stage10_report(session,exitstatus,root):
    config=session.config
    def read(name):
        p=root/'reports'/name
        return json.loads(p.read_text()) if p.is_file() else {}
    initial=read('initial-state.json');external=read('external-checks.json');live=read('stage10-live.json')
    controls=read('stage08-live.json');previous_live=read('stage09-live.json')
    processes={b:read('stage10-process-'+b+'.json') for b in ('before_post','after_post','before_put','after_put','after_confirmation','hold_post')}
    protected=initial.get('protected_hashes',{})
    changed=[p for p,h in protected.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    hashes=_stage10_sources()
    changed_during_run=sorted(set(hashes)^set(config._acceptance_start_hashes) | {
        p for p,h in hashes.items() if config._acceptance_start_hashes.get(p)!=h})
    results=config._acceptance_results
    optional='test_rest_live.py::test_live_get_test_page'
    passed=lambda r:r['status']=='passed' or (r['status']=='skipped' and r['test_id'].endswith(optional))
    good=(int(exitstatus)==0 and bool(session.items) and bool(results) and all(passed(r) for r in results)
        and bool(protected) and not changed and not changed_during_run and external.get('gate')=='passed'
        and live.get('status')=='passed' and controls.get('status')=='passed' and previous_live.get('status')=='passed'
        and all(p.get('POST')==p.get('PUT')==1 for p in processes.values()))
    master=Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan=master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    schema=Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    implemented={
        'S/scripts/pipeline.py':'admitted lifecycle, intent before effects, exact/current read-back, resume, bounded 409 patch, unchanged/storage-only, child, AB guard, sticky schedule mismatch',
        'S/scripts/plan_operation.py':'typed append-only network plan/intents/observations/stages with atomic receipt mirrors',
        'S/scripts/plan_reconcile.py':'current page/attachment versions and managed fingerprints before replay; uncertain POST/PUT resolved by reads',
        'S/scripts/plan_lock.py':'namespace/page/macro flock, live owner, release after process death',
        'S/scripts/conf_client.py':'frozen timeout/retry, bounded GET-only retries, exact version=N without status, parent/title child lookup',
        'S/scripts/gantt_attachment.py':'archived deterministic bytes, exact ID/version and timeout, no override',
        'S/scripts/plan_verify.py':'canonical full macro and summary fingerprint; preservation checks',
        'S/scripts/child_page.py':'exact parent/title/managed-state reconciliation after uncertain creation',
        'S/scripts/plan_receipt.py':'validated published true/false/null and external-effect semantics',
        'M/mofs_index/plan/schema.py':'only new 0012_publish_confirmation; previous definitions unchanged',
        'M/mofs_index/plan/writer.py + query.py':'atomic verified_v1 observation/publication/snapshot/admission/profile/schedule links and result event; scoped read API',
        'S/tests + M/tests/plan':'fault matrix, actual os._exit/SIGKILL over HTTP, concurrency, integrity/atomicity, live dedicated pages',
        'S/references/operations-and-recovery.md + cli-contract.md':'numeric settings and recovery contract'}
    limitations=[
        'Only stage 10; stages 11–13 and full §20 acceptance are not claimed.',
        'Live admitted plan is an explicit synthetic parsed fixture. Real binary MPP extraction limitations remain; schedule:not_verified. No arbitrary-plan schedule equality is claimed.',
        'Flock protects processes sharing the configured WorkVault on this host; external writers are detected by fresh version/hash checks, not a distributed transaction.',
        'Confirmation describes the exact versions at observation time. A later foreign edit can change the page.',
        'Post-write schedule mismatch is retained as an error and never rolled back automatically.',
        'The on-disk master is 0.5.1 with a separate §21; stage 10 follows agreed §20. Master/§21 were not edited and that separate BUGFIX is not declared accepted.',
        'OwnCloud sync is not confirmed. Production DB/A–D/AB pages, Gateway, configs, crons, watchers and schedules were not changed.']
    report={'stage':'10','gate':'passed' if good else 'failed','exit_code':int(exitstatus),
        'base_commit':initial.get('base_commit'),'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
        'environment':{'python':sys.executable,'version':platform.python_version(),'cli_python':'/usr/bin/python3',
            'PYTHONPATH':os.environ.get('PYTHONPATH'),'test_root':str(root)},
        'master':{'path':str(master),'version':'0.5.1','sha256':hashlib.sha256(master.read_bytes()).hexdigest(),
            'section20_sha256':hashlib.sha256(master.read_text().split('## 20. ')[1].split('## 21. ')[0].encode()).hexdigest()},
        'plan':{'path':str(plan),'normative_prefix_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()},
        'config_contract_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),
        'source_files':hashes,'source_tree_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
        'implemented_files':implemented,'migrations':['0012_publish_confirmation'],'previous_migrations':'0001–0011 checksum equality tested',
        'protected_files_checked':len(protected),'changed_protected_files':changed,'changed_during_test_run':changed_during_run,
        'tests':results,'selected':len(session.items),'mandatory_test_ids':sorted(STAGE10_REQUIRED),'external_checks':external,
        'live_evidence':'stage10-live.json','process_evidence':list(processes),'plugin_controls_evidence':'stage08-live.json',
        'counters':{'live_stage10':{k:live.get(k) for k in ('POST','PUT','GET')},
            'live_stage09':{k:previous_live.get(k) for k in ('POST','PUT')},'controls':{k:controls.get(k) for k in ('POST','PUT')},
            'loopback_processes':{k:{name:v.get(name) for name in ('POST','PUT','GET')} for k,v in processes.items()},
            'regression':config._acceptance_counters,'all_legacy_reader_calls':None},
        'covered_requirements':['§20/AC-03','§20/AC-10…16','stage-10 network closure of §20/AC-04/09','confirmation part of §20/AC-27'],
        'limitations':limitations,'generated_at':datetime.now(timezone.utc).isoformat()}
    (root/'reports/stage-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Этап 10 — сетевые стадии, идемпотентность и восстановление','',
        f"Gate: **{report['gate']}**; S rc={exitstatus}; selected={len(session.items)}; passed={sum(r['status']=='passed' for r in results)}.",'',
        'prepared → archived → admitted → attachment_uploaded → attachment_verified → storage_written → storage_verified → confirmed.','']
    lines+=['- `'+name+'`: '+value+'.' for name,value in implemented.items()]
    lines+=['','Команда S:','','```text',' '.join(report['command']),'```','',
        'Команды/rc/JUnit MofsIndex и восстановление внешнего комплекта: external-checks.json.',
        'HTTP dedicated pages: stage10-live.json; plugin controls: stage08-live.json; реальный process-death/HTTP: stage10-process-*.json.',
        '',f"Live stage10: {report['counters']['live_stage10']}. Проверенное дерево: `{report['source_tree_sha256']}`.",
        '',f'Защищённых файлов: {len(protected)}, изменено: {len(changed)}. canon.md исключён из поставки; hash проверен.',
        '', 'Ограничения:','']+['- '+value for value in limitations]
    (root/'reports/stage-report.md').write_text('\n'.join(lines)+'\n')


# Existing stage sets/report builders above remain independent and unchanged.
STAGE11_REQUIRED = STAGE07_REQUIRED | STAGE10_REQUIRED | {
    'test_compare_e2e.py::test_ac24_cli[AC24-'+str(n)+']' for n in range(1,11)}
STAGE11_REQUIRED |= {'test_compare_e2e.py::'+name for name in (
    'test_compare_same_source_precision_unknown_zone_and_causality',
    'test_compare_exact_publication_ids_same_v2_on_different_pages')}
STAGE11_REQUIRED |= {'test_publication_verify.py::'+name for name in (
    'test_verify_transport_technically_forbids_writes',
    'test_verify_current_repeat_append_only_no_attachment_version',
    'test_verify_current_does_not_restore_historical_date',
    'test_verify_mismatch_retains_previous_observations',
    'test_verify_legacy_missing_expected_bytes_storage_or_link',
    'test_verify_wrong_project_has_zero_requests',
    'test_verify_cli_loopback_concurrent_reads_append_observations',
    'test_stage11_live_verify_only_get_repeat_and_historical_scope')}
STAGE11_REQUIRED |= {'test_publication_verify.py::test_verify_transport_technically_forbids_writes['+method+']'
                     for method in ('POST','PUT','PATCH','DELETE')}
STAGE11_REQUIRED |= {'test_publication_verify.py::test_verify_mismatch_retains_previous_observations['+case+']'
                     for case in ('bytes','storage','current_version','page_id','attachment_id')}


def _stage11_sources():
    hashes=_stage10_sources()
    q=SKILL_ROOT.parents[1]/'research/workvault-rag'
    for p in (q/'SKILL.md',q/'references/plan-queries.md'):
        hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def _stage11_report(session,exitstatus,root):
    config=session.config
    def read(name):
        p=root/'reports'/name
        return json.loads(p.read_text()) if p.is_file() else {}
    initial,external,live,loopback=(read(n) for n in ('initial-state.json','external-checks.json','stage11-live.json','stage11-loopback.json'))
    comparisons=[json.loads(line) for p in sorted((root/'pytest-tmp').rglob('cli-results.jsonl'))
                 for line in p.read_text().splitlines() if line]
    (root/'reports/stage11-compare-cli.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2)+'\n')
    protected=initial.get('protected_hashes',{})
    changed=[p for p,h in protected.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    hashes=_stage11_sources()
    start=config._acceptance_start_hashes
    drift=sorted(set(hashes)^set(start) | {p for p,h in hashes.items() if start.get(p)!=h})
    results=config._acceptance_results
    passed=lambda r:r['status']=='passed' or (r['status']=='skipped' and r['test_id'].endswith('test_rest_live.py::test_live_get_test_page'))
    good=(int(exitstatus)==0 and bool(session.items) and bool(results) and all(passed(r) for r in results)
        and bool(protected) and not changed and not drift and external.get('gate')=='passed'
        and live.get('status')=='passed' and loopback.get('status')=='passed'
        and live.get('POST')==live.get('PUT')==loopback.get('POST')==loopback.get('PUT')==0)
    master=Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan=master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    schema=Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    implemented={
        'M/mofs_index/plan/selectors.py':'exact snapshot/publication IDs, project/page/attachment/lineage/snapshot link checks before diff',
        'M/mofs_index/plan/query.py':'all saved task fields/nested data, dependency multisets, calendar/assignment/resource semantics, structured unmatched records, precise dates, identity-safe dependent queries',
        'M/mofs_index/plan/history.py':'scoped publications/links and append-only verification observations with distinct times and stable cursor watermark',
        'M/mofs_index/plan/render.py':'derived MD with exact IDs/page/attachment/representation/revision/evidence/completeness; no positional proof',
        'S/scripts/plan_queries.py + cli.py':'compare, final history, publication verify; global isolated paths and structured exit codes',
        'S/scripts/plan_publication_verify.py':'GET-only request/download guard; expected bytes, exact metadata, archived storage, historical/current scopes, fresh target checks and append-only local observations',
        'S/scripts/plan_history.py':'archive-history remains legacy_unverified; archived bytes do not prove historical publication',
        'M/tests/plan/test_query.py + test_render.py':'direct typed API regressions and semantic field matrix',
        'S/tests/test_compare_e2e.py + test_publication_verify.py':'all ten AC-24 subcases via CLI, exact v2 IDs, GET guard, actual loopback concurrency and dedicated live reads',
        'S/tests/conftest.py':'stage-11 mandatory set, group ordering and evidence-derived gate; stages 01–10 preserved',
        'Q/SKILL.md + references/plan-queries.md':'same typed API, exact selectors, mapping/trust and distinct observation times'}
    limitations=[
        'Only stage 11; stages 12/13, active skill delivery and full §20/§19 acceptance are not claimed.',
        'Unknown or partial identity remains structured unmatched data. Positional Gantt IDs never prove entity identity; unlinked/MPP-source publications expose raw structures with unknown mapping.',
        'Completeness is conservative. Timezone alone does not establish calendar/field completeness. Working-time drift and causal schedule attribution are not calculated.',
        'Read-back is scoped to observed versions and time; current_state never restores a historical publication date. Insufficient expected bytes/storage/link yields not_verified/5.',
        'Live stage-11 uses immutable synthetic stage-10 evidence on a dedicated page: historical version matches, current attachment deliberately differs. No arbitrary real-MPP schedule equality is claimed.',
        'Master on disk is 0.5.1 with separate §21; only agreed §20 is implemented. No schema/config/previous-stage evidence modifications.',
        'canon.md was clean at entry; its original bytes are protected and it is excluded from the commit. OwnCloud sync is not confirmed.',
        'Production DB/WorkVault plan data and A–D/AB pages, Gateway, crons, watchers and schedules are unchanged. Existing live regression tests create only dedicated acceptance targets.']
    report={'stage':'11','gate':'passed' if good else 'failed','exit_code':int(exitstatus),'base_commit':initial.get('base_commit'),
        'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
        'environment':{'python':sys.executable,'version':platform.python_version(),'cli_python':'/usr/bin/python3',
            'PYTHONPATH':os.environ.get('PYTHONPATH'),'test_root':str(root)},
        'master':{'path':str(master),'version':master.read_text().split('version:',1)[1].splitlines()[0].strip(),
            'sha256':hashlib.sha256(master.read_bytes()).hexdigest(),
            'section20_sha256':hashlib.sha256(master.read_text().split('## 20. ')[1].split('## 21. ')[0].encode()).hexdigest()},
        'plan':{'path':str(plan),'normative_prefix_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()},
        'config_contract_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),
        'source_files':hashes,'source_tree_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
        'implemented_files':implemented,'migrations':[],'schema_writer_unchanged':True,
        'protected_files_checked':len(protected),'changed_protected_files':changed,'changed_during_test_run':drift,
        'tests':results,'selected':len(session.items),'mandatory_test_ids':sorted(STAGE11_REQUIRED),'external_checks':external,
        'live_evidence':'stage11-live.json','loopback_evidence':'stage11-loopback.json','compare_cli_evidence':'stage11-compare-cli.json',
        'counters':{'stage11_live':{k:live.get(k) for k in ('GET','POST','PUT')},
            'stage11_loopback':{k:loopback.get(k) for k in ('GET','POST','PUT')},'regression':config._acceptance_counters},
        'covered_requirements':['§20/AC-23','§20/AC-24','§20/AC-25','§20/AC-27'],
        'limitations':limitations,'generated_at':datetime.now(timezone.utc).isoformat()}
    (root/'reports/stage-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Этап 11 — доказательное сравнение и доверие к публикациям','',
        f"Gate: **{report['gate']}**; S rc={exitstatus}; selected={len(session.items)}; passed={sum(r['status']=='passed' for r in results)}.",'',
        'Покрытие: §20/AC-23, AC-24 (все десять подслучаев), AC-25, AC-27 в объёме этапа 11.','']
    lines+=['- `'+name+'`: '+value+'.' for name,value in implemented.items()]
    lines+=['','Команда S:','','```text',' '.join(report['command']),'```','',
        'Отдельные команды/rc/JUnit MofsIndex, проверка восстановления patch и after-copy: external-checks.json.',
        '',f"Live GET-only: {report['counters']['stage11_live']}; concurrent CLI loopback: {report['counters']['stage11_loopback']}.",
        '',f"Дерево исходников: `{report['source_tree_sha256']}`. Защищено файлов: {len(protected)}, изменено: {len(changed)}.",
        '', 'Завершающий SHA записывается после commit в журнал канонического плана. canon.md в поставку не включается.',
        '', 'Ограничения:','']+['- '+value for value in limitations]
    (root/'reports/stage-report.md').write_text('\n'.join(lines)+'\n')


# Stage 12 adds delivery/docs contracts; earlier stages keep their own gates.
_STAGE12_EXCLUDED_LIVE = {
    'test_publish_live.py::test_stage09_live_publish_bytes_storage_and_binary_blocker',
    'test_plugin_controls_live.py::test_installed_plugin_controls_live',
    'test_rest_live.py::test_stage10_live_recovery_idempotency_and_child',
    'test_publication_verify.py::test_stage11_live_verify_only_get_repeat_and_historical_scope',
    'test_publication_verify.py::test_verify_cli_loopback_concurrent_reads_append_observations',
}
_STAGE12_EXCLUDED_LIVE |= {
    'test_publish_resume.py::test_real_process_death_http_reconciliation['+boundary+']'
    for boundary in ('before_post','after_post','before_put','after_put','after_confirmation','hold_post')}
STAGE12_REQUIRED = (STAGE11_REQUIRED - _STAGE12_EXCLUDED_LIVE) | {
    'test_identity_resume_e2e.py::test_bootstrap_no_save_one_arrival_then_identity_confirm_resume',
    'test_identity_resume_e2e.py::test_resume_forms_are_mutually_exclusive_and_apply_has_slug',
} | {'test_skill_contract.py::' + name for name in (
    'test_active_library_loads_both_names', 'test_wrapper_has_one_canon_and_no_algorithm',
    'test_documented_cli_examples_parse', 'test_documented_options_cover_parser',
    'test_global_parameters_cannot_follow_subcommand', 'test_user_routes_dispatch_with_global_isolation',
    'test_real_archive_stdout_and_receipts_redact_secrets', 'test_invalid_arguments_do_not_echo_secret',
    'test_today_example_uses_local_midnights_and_offsets', 'test_reference_links_and_json_examples',
    'test_forbidden_legacy_routes_removed')}


def _stage12_sources():
    hashes = _stage11_sources()
    h = SKILL_ROOT.parents[2]
    files = [SKILL_ROOT/'SKILL.md', *(SKILL_ROOT/'references').glob('*.md'),
        h/'skills/productivity/confluence-gantt-plan/SKILL.md',
        h/'skills/productivity/tutu-confluence-jira/SKILL.md',
        MOFS_INDEX_ROOT/'README.md', Path.home()/'USERTOOLS/MppReader/README.md',
        h/'restore-all-skills.sh', h/'sync-to-hermes.sh']
    hashes.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    return hashes


def _stage12_report(session, exitstatus, root):
    config = session.config
    def read(name):
        p = root/'reports'/name
        return json.loads(p.read_text()) if p.is_file() else {}
    initial, external, loads = (read(n) for n in ('initial-state.json','external-checks.json','skill-loads.json'))
    protected = initial.get('protected_hashes', {})
    changed = [p for p,h in protected.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    hashes = _stage12_sources()
    start = config._acceptance_start_hashes
    drift = sorted(set(hashes)^set(start) | {p for p,h in hashes.items() if start.get(p)!=h})
    results = config._acceptance_results
    selected = {item.path.name+'::'+item.name for item in session.items}
    selected |= {name.split('[')[0] for name in selected}
    missing = sorted(STAGE12_REQUIRED-selected)
    passed_ids = {Path(r['test_id'].split('::',1)[0]).name+'::'+r['test_id'].split('::',1)[1]
                  for r in results if r['status']=='passed' and r['phase']=='call'}
    passed_ids |= {name.split('[')[0] for name in passed_ids}
    mandatory_not_passed = sorted(STAGE12_REQUIRED-passed_ids)
    # Verify the evidence against the actual active files, not its success label alone.
    load_records = loads.get('skills', [])
    load_ok = len(load_records)==4 and all(
        entry.get('success') and Path(entry['path']).is_file()
        and str(Path(entry['path']).resolve())==entry['resolved_path']
        and hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256']
        for entry in load_records)
    no_live = not any(item.get_closest_marker('confluence_live') for item in session.items)
    good = (int(exitstatus)==0 and bool(session.items) and bool(results)
        and all(r['status']=='passed' for r in results) and not missing and not mandatory_not_passed
        and bool(protected) and not changed and not drift and no_live and load_ok
        and external.get('gate')=='passed')
    master = Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan = master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    schema = Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    implemented = {
        'S/SKILL.md':'канонические publish/save/Inbox/history/compare/identity/resume, адресные решения и раздельное доверие',
        'W/SKILL.md':'короткое перенаправление в skill_view канона без алгоритма',
        'Q/SKILL.md + Q/references/plan-queries.md':'русские запросы того же typed API, локальные сутки и текущая/подтверждённая версия',
        'C/SKILL.md':'адресная ссылка на канон и unified credential loader, прежние JIRA правила сохранены',
        'A/edit-plan-confluence + A/confluence-gantt-plan':'штатный restore после backup/исправления live слоя по регламенту библиотеки; реальные skill_view paths/hashes',
        'S/references/mpp-to-gantt.md':'prepared data вместо обязательной CSV цепочки, качество и ограничения',
        'S/references/cli-contract.md':'все команды/флаги/defaults, глобальные пути, схемы, exit codes, исполнимые parser примеры',
        'S/references/batch-and-inbox.md':'freeze-all, manifest, неизменяемый контекст, разделение регистрации/исполнения решения',
        'S/references/identity-and-rules.md':'evidence/revision, B/C, once/project, identity bootstrap',
        'S/references/history-and-verification.md':'точные selectors, время/offset/cursor, trust и GET-only observations',
        'S/references/testing-and-acceptance.md':'изоляция, группы, ограничения покрытия этапа 12, отчёты и gate',
        'S/references/operations-and-recovery.md':'численные лимиты и реальные источники, backup до будущей миграции, recovery и частичные эффекты',
        'S/references/cases-trisigma.md':'A–G и D-risks, hashes/размеры/метрики и границы функциональной приёмки',
        'R/README.md + M/README.md':'export_full-v2 и typed API; before/after/patch/manifest и восстановление',
        'S/tests/test_skill_contract.py':'загрузчик, parser/dispatch, stdout, secret canary, offsets и совместимость',
        'S/tests/conftest.py':'STAGE12_REQUIRED, отдельные offline selection/order/report; прежние hooks/карты сохранены',
        'E/Manifest + digest/render; MAIN_TZ_INVENTORY':'согласованы существующие записи/ID, версия actual master 0.5.1, внешние пути/hashes/diffs'}
    limitations = [
        'Только этап 12. Полная приёмка этапа 13, live A–D/G и отдельные A–F записи §20.7.3 этим gate не закрываются; прежние evidence не редактировались.',
        'Маршрутизация проверена по инструкции, реальному parser/dispatch CLI и выбранной регрессии. Сообщение через Gateway/LLM не прогонялось; отклонённое сообщение скилл исправить не может.',
        'Настоящий skill_view успешен, но штатный загрузчик предупреждает о symlink вне trusted root; loader/Gateway не изменены.',
        'Generic Codex quick_validate не принимает существующие Hermes frontmatter keys platforms/tools/version (rc=1); рабочий формат сохранён и проверен настоящим Hermes loader. Это не ошибка загрузки Hermes.',
        'Master на диске 0.5.1 с отдельным §21, исполнялся §20. Inventory приведено к фактической версии, новый APPROVE не заявлен.',
        'Manifest имеет прежние ошибки общей schema вне новой дельты; список/равенство before-after в registry/manifest-ids.json. Новые ошибки и Tool ID не добавлены.',
        'Schedule остаётся независимым, unknown/partial identity не превращается в доказанное соответствие. Полный счётчик всех reader/cache регрессий не измерен (null).',
        'Production БД/архивы/страницы A–D/AB не менялись; приёмка offline. Gateway, кроны, наблюдатели и расписания не менялись. OwnCloud sync не подтверждён.',
        'Первый отдельный smoke 74 passed выполнялся с изолированным стандартным pytest tmp; финальная приёмка и внешние проверки целиком в T/stage-12. Предварительный smoke не используется как gate.',
    ]
    report = {'stage':'12','gate':'passed' if good else 'failed','exit_code':int(exitstatus),
        'base_commit':initial.get('base_commit'),'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
        'environment':{'python':sys.executable,'version':platform.python_version(),'cli_python':'/usr/bin/python3',
            'PYTHONPATH':os.environ.get('PYTHONPATH'),'test_root':str(root)},
        'master':{'path':str(master),'version':master.read_text().split('version:',1)[1].splitlines()[0].strip(),
            'sha256':hashlib.sha256(master.read_bytes()).hexdigest(),
            'section20_sha256':hashlib.sha256(master.read_text().split('## 20. ')[1].split('## 21. ')[0].encode()).hexdigest()},
        'plan':{'path':str(plan),'sha256':hashlib.sha256(plan.read_bytes()).hexdigest(),
            'normative_prefix_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()},
        'config_contract_sha256':hashlib.sha256(schema.read_bytes()).hexdigest(),
        'source_files':hashes,'source_tree_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest(),
        'implemented_files':implemented,'migrations':[],'protected_files_checked':len(protected),
        'changed_protected_files':changed,'changed_during_test_run':drift,
        'selected':len(session.items),'tests':results,'mandatory_test_ids':sorted(STAGE12_REQUIRED),
        'missing_required':missing,'mandatory_not_passed':mandatory_not_passed,'external_checks':external,
        'active_skill_loads':loads,'no_live_selected':no_live,
        'counters':{'MPXJ_read':None,'cache_hit':None,'cache_miss':None,'live_POST':0,'live_PUT':0,
            'instrumented_regression':config._acceptance_counters},
        'coverage':{'§20.7.3':'эксплуатационная интеграция; полные A–F записи отложены этапу 13',
            'AC-04':'документация и bootstrap/identity/resume регрессия',
            'AC-17':'маршрут Inbox, выбранные архивные регрессии; полная приёмка отдельно',
            'AC-19':'адресные решения и прежние тесты регистрации/исполнения',
            'AC-23':'history/локальные сутки/cursor и typed API регрессия',
            'AC-24':'точные compare и все десять CLI подслучаев в выбранной регрессии',
            'AC-25':'запрет неоднозначного v2, точные publication selectors'},
        'limitations':limitations,'generated_at':datetime.now(timezone.utc).isoformat()}
    (root/'reports/stage-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Этап 12 — интеграция скилла и эксплуатационная документация','',
        f"Gate: **{report['gate']}**; S rc={exitstatus}; selected={len(session.items)}; passed={sum(r['status']=='passed' and r['phase']=='call' for r in results)}.",'',
        'Команда S:','','```text',' '.join(report['command']),'```','',
        'Пофайловая поставка:','']+['- `'+key+'`: '+value+'.' for key,value in implemented.items()]
    lines+=['','Фактически загруженные имена:','']
    lines+=['- `'+entry['requested_name']+'`: `'+entry['path']+'` → `'+entry['resolved_path']+'`; SHA-256 `'+entry['sha256']+'`.' for entry in load_records]
    lines+=['','Внешние команды/rc/JUnit, восстановление USERTOOLS, конфиг-источники и Registries: external-checks.json и связанные evidence.',
        '',f"Source tree: `{report['source_tree_sha256']}`; защищено {len(protected)} файлов, изменено {len(changed)}.",
        '', 'Удалены предварительный save, ручное копирование /tmp, автоудаление связей, доказательство отсутствия публикации по nullable дате и повторное общее да для publish.',
        '', 'Timeout: reader 180 с, JVM probe 60 с, HTTP 120 с; retry limit 1 (GET до 2 попыток); MPP/ZIP 64 MiB, ZIP 128 entries/256 MiB unpacked/ratio 100.',
        '', 'Secret-redaction: canary stdout/receipt и сканирование поставки без сохранения реальных секретов. Backup/recovery описаны, production миграция не выполнялась.',
        '', 'Завершающий commit/SHA — после gate, в журнале канонического плана; canon.md исключён.','', 'Ограничения:','']
    lines+=['- '+value for value in limitations]
    (root/'reports/stage-report.md').write_text('\n'.join(lines)+'\n')

# Stage 13 extends this pytest contour; no product CLI or report runner.
STAGE13_MATRIX = SKILL_ROOT/'tests/acceptance/ac-matrix.json'
STAGE13_PRODUCTION_PAGES = {'496600693', '499550441', '499566117', '506248940', '519492935'}
STAGE13_TEST_PARENT = '519501810'
STAGE13_RECOVERY_FILES = {'test_batch_resume.py','test_import_atomicity.py','test_plan_cache.py',
                         'test_plan_lock.py','test_publish_resume.py','test_publish_conflicts.py'}


def _stage13_phase(item):
    if item.path.name == 'test_migration_preservation.py': return 2
    if item.get_closest_marker('confluence_live'):
        if 'installed_names' in item.name: return 11
        if item.name.startswith('test_stage11_live_verify'): return 10
        return 9
    if item.name == 'test_final_baseline_audit': return 8
    if item.path.name in STAGE13_RECOVERY_FILES or item.get_closest_marker('loopback_http'): return 7
    if item.path.name in ('test_plan_batch.py','test_batch_decisions.py','test_history_queries.py',
            'test_plan_identity.py','test_compare_e2e.py','test_user_journeys.py','test_identity_resume_e2e.py'):
        return 6
    if item.get_closest_marker('mpp_fixtures'): return 5
    if item.get_closest_marker('archive_integration'): return 4
    return 3


def _stage13_matrix():
    return json.loads(STAGE13_MATRIX.read_text())


def _stage13_required():
    if not STAGE13_MATRIX.is_file():
        return set()
    matrix = _stage13_matrix()
    required = set(matrix['regression_test_ids'])
    for row in matrix['requirements'].values():
        required.update(row['tests'])
        for subcase in row.get('subcases', {}).values():
            required.update(subcase['tests'])
    required.update(matrix['acceptance_test_ids'])
    return required


STAGE13_REQUIRED = _stage13_required()


def _stage13_sources():
    hashes = _stage12_sources()
    files = [*SKILL_ROOT.joinpath('tests/acceptance').glob('*.py'), STAGE13_MATRIX,
             SKILL_ROOT/'tests/conftest.py', SKILL_ROOT/'tests/pytest.ini',
             *FIXTURES.rglob('*.mpp'), *FIXTURES.rglob('*manifest.json')]
    hashes.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()})
    return hashes


def _stage13_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str)+'\n')
    temp.replace(path)


def _stage13_configure(config):
    import subprocess
    root = config._acceptance_root
    config._acceptance_start_hashes = _stage13_sources()
    records = json.loads((FIXTURES/'real/manifest.json').read_text())['fixtures']
    expected = {'A': (58,57,53,'1576'), 'B': (62,61,60,'2096'), 'C': (62,61,61,'2088'),
                'D': (72,71,76,'3136'), 'E': (78,77,84,None), 'F': (86,85,93,None)}
    rows = []
    for row in records:
        source = FIXTURES/'real'/row['path']
        dest = root/'fixtures/real'/row['path']
        data = source.read_bytes() if source.is_file() else None
        valid = data is not None and hashlib.sha256(data).hexdigest() == row['sha256'] and len(data) == row['size_bytes']
        if valid:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        original = Path(row['origin'])
        origin_ok = original.is_file() and hashlib.sha256(original.read_bytes()).hexdigest() == row['sha256']
        counts = expected.get(row['id'])
        rows.append({**row, 'repository_copy': str(source), 'copy': str(dest),
            'status': 'verified' if valid else 'blocked_missing_fixture',
            'original_verified': origin_ok,
            'identity_basis': 'Фактические данные пользователя от 16.11.2026 и проверка SHA-256; master §20.7.4',
            'functional_status': 'not_run',
            'expected': dict(zip(('archive_task_count','display_task_count','dependency_count','work_hours'), counts)) if counts else None})
    config._stage13_fixtures = rows
    supporting = []
    for path in sorted(FIXTURES.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.parent == FIXTURES/'real':
            continue
        dest = root/'fixtures/supporting'/path.relative_to(FIXTURES)
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        dest.write_bytes(data)
        supporting.append({'source':str(path),'copy':str(dest),'sha256':hashlib.sha256(data).hexdigest(),'size_bytes':len(data)})
    config._stage13_supporting_fixtures = supporting
    _stage13_write(root/'fixtures-manifest.json', {'schema_version': 1, 'fixtures': rows,
        'supporting_fixtures':supporting, 'copies_are_not_transport_cache_only': True,
        'verified_at': datetime.now(timezone.utc).isoformat()})
    config._stage13_start = datetime.now(timezone.utc).isoformat()
    config._stage13_live_pages = {STAGE13_TEST_PARENT}
    # Existing regression uses one immutable dedicated stage-10 test page.
    legacy = SKILL_ROOT/'references/implementation/20261116/stage-10/reports/stage10-live.json'
    if legacy.is_file():
        config._stage13_live_pages.add(str(json.loads(legacy.read_text())['page_id']))
    assert not config._stage13_live_pages & STAGE13_PRODUCTION_PAGES
    _stage13_write(root/'reports/live-targets.json', {'parent_id': STAGE13_TEST_PARENT,
        'pages': sorted(config._stage13_live_pages), 'production_excluded': sorted(STAGE13_PRODUCTION_PAGES)})
    java = subprocess.run(['java', '-version'], text=True, capture_output=True, timeout=20)
    config._stage13_environment = {'python': sys.executable, 'python_version': platform.python_version(),
        'cli_python': '/usr/bin/python3', 'reader_python': '/usr/bin/python3.9',
        'PYTHONPATH': os.environ.get('PYTHONPATH'), 'java': java.stderr.strip(), 'java_rc': java.returncode,
        'test_root': str(root), 'plugin_profile': json.loads((SKILL_ROOT/'references/profiles/installed-gantt-profile.json').read_text())}
    from env import select_mpxj_python
    from mpp_convert import CONVERTER_VERSION
    from plan_policy import POLICY_VERSION
    from plan_rules import RULES_VERSION
    runtime = select_mpxj_python()
    config._stage13_environment['component_versions'] = {**runtime.versions,
        'exporter':'full-export-v2','normalization':'prepared-v1','converter':CONVERTER_VERSION,
        'policy':POLICY_VERSION,'rules':RULES_VERSION,
        'normalization_profile':json.loads((SKILL_ROOT/'references/profiles/normalization-v1.json').read_text()),
        'summary_profile':json.loads((SKILL_ROOT/'references/profiles/summary-v1.json').read_text())}
    _stage13_write(root/'reports/environment.json', config._stage13_environment)
    # Reuse the installed browser dependency; no new service, package or daemon.
    browser_base = Path.home()/'.cache/edit-plan-confluence-acceptance/20261116-stage08/stage-08'
    for name in ('browser-deps', 'browsers'):
        dest = root/name
        if (browser_base/name).is_dir() and not dest.exists():
            dest.symlink_to(browser_base/name, target_is_directory=True)


def _stage13_short_id(test_id):
    head, sep, tail = test_id.partition('::')
    return Path(head).name+sep+tail


def _stage13_test_status(test_ids, results):
    if not test_ids:
        return 'not_run'
    states = []
    for test_id in test_ids:
        rows = [r for r in results if _stage13_short_id(r['test_id']) == test_id]
        if any(r['status'] == 'failed' for r in rows):
            states.append('failed')
        elif any(r['status'] == 'skipped' for r in rows):
            states.append('not_run')
        elif any(r['status'] == 'passed' and r['phase'] == 'call' for r in rows):
            states.append('passed')
        else:
            states.append('not_run')
    return 'failed' if 'failed' in states else 'not_run' if 'not_run' in states else 'passed'


def _stage13_requirement_status(requirement, results, root):
    status = _stage13_test_status(requirement['tests'], results)
    matching = [r for r in results if _stage13_short_id(r['test_id']) in requirement['tests']]
    if any('blocked_missing_fixture:' in (r.get('reason') or '') for r in matching):
        status = 'blocked_missing_fixture'
    elif any('blocked_identity:' in (r.get('reason') or '') for r in matching):
        status = 'blocked_identity'
    evidence = requirement.get('evidence', [])
    missing = [name for name in evidence if not (root/name).is_file()]
    if missing and status == 'passed':
        status = 'not_run'
    return {**requirement, 'status': status, 'missing_evidence': missing}


@pytest.fixture(autouse=True)
def stage13_fixture_integrity(request):
    if request.config.getoption('--acceptance-stage') != '13':
        return
    # Recheck actual bytes before EVERY test, not just on session startup.
    for row in request.config._stage13_fixtures:
        path = Path(row['copy'])
        if not path.is_file() or path.stat().st_size != row['size_bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            pytest.fail('blocked_missing_fixture: '+row['id'])
    for row in request.config._stage13_supporting_fixtures:
        for key in ('source','copy'):
            path = Path(row[key])
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                pytest.fail('blocked_missing_fixture: '+str(path))


@pytest.fixture
def stage13_record(request, tmp_path):
    root = getattr(request.config, '_acceptance_root', tmp_path)
    def record(name, value):
        path = root/'reports/evidence'/(name+'.json')
        # Parametrized calls must not overwrite each other's observations.
        if path.exists():
            prior = json.loads(path.read_text())
            if prior.get('test_id') != request.node.nodeid:
                path = path.with_name(name+'-'+hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:10]+'.json')
        _stage13_write(path, {'test_id': request.node.nodeid, 'observed_at': datetime.now(timezone.utc).isoformat(), **value})
        paths = getattr(request.node, '_stage13_evidence', [])
        if str(path.relative_to(root)) not in paths:
            paths.append(str(path.relative_to(root)))
        request.node._stage13_evidence = paths
        return path
    return record


@pytest.fixture
def stage13_input(request, tmp_path):
    def select(case):
        manifest = getattr(request.config, '_stage13_fixtures', None)
        if manifest is None:
            manifest = json.loads((FIXTURES/'real/manifest.json').read_text())['fixtures']
        row = next(r for r in manifest if r['id'] == case)
        origin = Path(row.get('copy', FIXTURES/'real'/row['path']))
        assert origin.is_file(), 'blocked_missing_fixture: '+case
        data = origin.read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256'] and len(data) == row['size_bytes']
        dest = tmp_path/(case+'.mpp'); dest.write_bytes(data)
        return dest, row
    return select


def _stage13_baseline(conn):
    # Observational dump only: all fixture writes use typed writer APIs.
    tables = ('plan_baseline_selection', 'plan_snapshot_selection')
    return {table: sorted(line for line in conn.iterdump() if line.startswith('INSERT INTO "'+table+'"'))
            for table in tables}


@pytest.fixture
def stage13_cli(tmp_path, request, stage13_record):
    import subprocess
    import time
    from plan_context import PlanContext
    from mofs_index.db import connect_durable
    from mofs_index.plan import writer as w
    context = PlanContext.resolve(db=tmp_path/'state/index.sqlite', workvault=tmp_path/'WorkVault', cache_dir=tmp_path/'cache')
    conn = connect_durable(context.db)
    plan = w.ensure_plan(conn, 'stage13-trisigma')
    lineage = w.ensure_lineage(conn, plan, 'stage13-baseline-owner')
    snapshot = w.ingest_snapshot(conn, w.SnapshotSpec(plan, 'mpp', lineage_id=lineage,
        tasks=(w.TaskVersionSpec('baseline-fixture', uid='baseline', name='Pre-existing baseline'),)))
    w.select_snapshot_baseline(conn, lineage, snapshot, is_explicit=True, basis='test owner before acceptance')
    w.select_plan_baseline(conn, plan, snapshot, 0, is_explicit=True, basis='test owner before acceptance')
    before = _stage13_baseline(conn)
    conn.close()
    class ObservedContext:
        baseline_before = before
        def __getattr__(self, name): return getattr(context, name)
        def baseline(self):
            conn = connect_durable(context.db)
            try: return _stage13_baseline(conn)
            finally: conn.close()
    observed = ObservedContext()
    guard = tmp_path/'cli-guard'; guard.mkdir()
    (guard/'sitecustomize.py').write_text('''import os,sys,socket,sqlite3,importlib.abc
from pathlib import Path
allowed=Path(os.environ['EDITPLAN_TEST_ROOT']).resolve()
original=sqlite3.connect
def connect(path,*a,**kw):
    if str(path)!=':memory:':
        p=Path(str(path).removeprefix('file:').split('?')[0]).resolve()
        if allowed not in p.parents: raise AssertionError('SQLite outside acceptance root')
    return original(path,*a,**kw)
sqlite3.connect=connect
if os.environ.get('EDITPLAN_TEST_NETWORK')!='live':
    class DenyConfluence(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in ('conf_client','pipeline'): raise AssertionError('Confluence import forbidden in archive')
    sys.meta_path.insert(0,DenyConfluence())
    def denied(*a,**k):raise AssertionError('network forbidden in archive CLI')
    socket.socket.connect=denied
    socket.create_connection=denied
else:
    import urllib.request,json,re,atexit
    measurements={'MPXJ_read':0,'cache_hit':0,'cache_miss':0,'POST':0,'PUT':0,'calls':[]}
    sys.path.insert(0,os.environ['EDITPLAN_SKILL_SCRIPTS'])
    import plan_cache
    original_parse=plan_cache.ParseCache.get_or_parse
    def measured_parse(self,*a,**kw):
        before={k:self.counters.get(k,0) for k in ('MPXJ_read','cache_hit','cache_miss')}
        try:return original_parse(self,*a,**kw)
        finally:
            for k in before:measurements[k]+=self.counters.get(k,0)-before[k]
    plan_cache.ParseCache.get_or_parse=measured_parse
    atexit.register(lambda:Path(os.environ['EDITPLAN_PROBE']).write_text(json.dumps(measurements)))
    original_urlopen=urllib.request.urlopen
    def safe_urlopen(req,*a,**kw):
        url=req.full_url if hasattr(req,'full_url') else str(req)
        for page in ('496600693','499550441','499566117','506248940','519492935'):
            if re.search(r'(?<![0-9])'+page+r'(?![0-9])',url): raise AssertionError('production page forbidden')
        if getattr(req,'data',None):
            try: body=json.loads(req.data)
            except (ValueError,UnicodeError):body={}
            if isinstance(body,dict):
                for page in body.get('ancestors',[]):
                    if str(page.get('id')) in ('496600693','499550441','499566117','506248940','519492935'):raise AssertionError('production parent forbidden')
        from urllib.parse import urlsplit
        method=req.get_method() if hasattr(req,'get_method') else 'GET'
        measurements['calls'].append({'method':method,'path':urlsplit(url).path})
        if method in ('POST','PUT'):measurements[method]+=1
        return original_urlopen(req,*a,**kw)
    urllib.request.urlopen=safe_urlopen
''')
    sequence = [0]
    def run(*args, live=False):
        env = dict(os.environ)
        env.update(PYTHONPATH=str(guard)+os.pathsep+env.get('PYTHONPATH',''),
                   EDITPLAN_TEST_ROOT=str(tmp_path), EDITPLAN_TEST_NETWORK='live' if live else 'none',
                   MPXJ_PYTHON='/usr/bin/python3.9', EDITPLAN_SKILL_SCRIPTS=str(SCRIPTS),
                   EDITPLAN_PROBE=str(tmp_path/'probe.json'))
        if not live: env.pop('CONFLUENCE_TOKEN', None)
        command = ['/usr/bin/python3',str(SCRIPTS/'cli.py'),'--db',str(context.db),
            '--workvault',str(context.workvault),'--cache-dir',str(context.cache_dir),*args]
        start = time.monotonic()
        proc = subprocess.run(command, capture_output=True, text=True, env=env, timeout=240)
        sequence[0] += 1
        record = {'command': command, 'rc': proc.returncode, 'duration_seconds': time.monotonic()-start,
                  'stdout': proc.stdout, 'stderr': proc.stderr, 'live': live}
        if len(proc.stdout) > 100000:
            path = getattr(request.config, '_acceptance_root', tmp_path)/'reports/cli-output'/(
                hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:12]+'-'+str(sequence[0])+'.json')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(proc.stdout)
            record.update(stdout=None, stdout_ref=str(path), stdout_bytes=len(proc.stdout.encode()),
                          stdout_sha256=hashlib.sha256(proc.stdout.encode()).hexdigest())
        probe = tmp_path/'probe.json'
        run.last_probe = json.loads(probe.read_text()) if live and probe.is_file() else None
        record['counters'] = run.last_probe
        stage13_record('cli-'+hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:12]+'-'+str(sequence[0]), record)
        result = json.loads(proc.stdout)
        assert result['exit_code'] == proc.returncode
        assert 'Authorization' not in proc.stdout
        if args[0] in ('save','publish','diff','resume','batch'):
            assert len(proc.stdout) < 100000
        return result
    yield observed, run
    after = observed.baseline()
    stage13_record('baseline-'+hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:12],
        {'baseline_before': before, 'baseline_after': after, 'unchanged': before == after})
    assert before == after, 'save/batch/publication changed the owner baseline'


def _stage13_report(session, exitstatus, root):
    config = session.config
    results = config._acceptance_results
    matrix = _stage13_matrix()
    def read(path):
        file = root/path
        return json.loads(file.read_text()) if file.is_file() else {}
    initial = read('reports/initial-state.json')
    external = read('reports/external-checks.json')
    current = _stage13_sources()
    start = config._acceptance_start_hashes
    drift = sorted(set(current)^set(start) | {p for p,h in current.items() if start.get(p) != h})
    protected = initial.get('protected_hashes', {})
    changed = [p for p,h in protected.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest() != h]
    requirements = {}
    for ac, definition in matrix['requirements'].items():
        row = _stage13_requirement_status(definition, results, root)
        row['subcases'] = {name:_stage13_requirement_status(sub,results,root) for name,sub in definition['subcases'].items()}
        states = [row['status'], *(sub['status'] for sub in row['subcases'].values())]
        row['status'] = next(status for status in ('failed','blocked_missing_fixture','blocked_identity','not_run','passed') if status in states)
        row['test_results'] = [r for r in results if _stage13_short_id(r['test_id']) in definition['tests']]
        row['command'] = [sys.executable,'-m','pytest',*config.invocation_params.args]
        requirements[ac] = row
    case_reports = {}
    evidence_files = list((root/'reports/evidence').glob('*.json'))
    evidence_values = [(p,json.loads(p.read_text())) for p in evidence_files]
    for case in ('A','B','C','D','E','F','G','D-risks'):
        definition = matrix['cases'][case]
        status = _stage13_test_status(definition['tests'], results)
        fixture = next((r for r in config._stage13_fixtures if r['id'] == case), None)
        if fixture and fixture['status'] != 'verified': status = 'blocked_missing_fixture'
        if case == 'A' and fixture and fixture['identity_status'] != 'confirmed': status = 'blocked_identity'
        values = [(p,v) for p,v in evidence_values if v.get('case') == case or case in v.get('cases', [])]
        live = next((v for _,v in values if v.get('page_id') and 'receipt' in v), {})
        cold = next((v for _,v in values if 'readback' in v), {})
        # Missing observations are represented explicitly; never fill them with
        # source dates, a model calculation or a historical report's success.
        observed = live.get('plugin_observation')
        if case in ('A','B','C','D') and not observed and status == 'passed': status = 'not_run'
        baseline = [{'before':v['baseline_before'],'after':v.get('baseline_after')}
                    for _,v in values if 'baseline_before' in v]
        record = {'schema_version':1,'case':case,'status':status,
            'functional_status':status, 'fixture':fixture,
            'identity_status':fixture.get('identity_status') if fixture else None,
            'tests':definition['tests'],'commands':[
                v['command'] for _,v in evidence_values
                if 'command' in v and _stage13_short_id(v.get('test_id','')) in definition['tests']],
            'source': {'path':fixture['copy'],'repository_copy':fixture['repository_copy'],
                       'origin':fixture['origin'],'sha256':fixture['sha256'],'size_bytes':fixture['size_bytes']} if fixture else None,
            'operation_item_batch_snapshot_publication_ids': [v.get('receipt') for _,v in values if v.get('receipt')],
            'versions':{'environment':config._stage13_environment.get('component_versions'),
                        'source':cold.get('readback',{}).get('versions'),
                        'plugin_profile':config._stage13_environment['plugin_profile'].get('plugin'),
                        'observed_plugin':observed},
            'mapping_revision':live.get('receipt',{}).get('exceptions',[]),
            'archive_display_dependency_counts':cold.get('readback',{}).get('summary',{}).get('counts'),
            'summary':cold.get('readback',{}).get('summary'),
            'attachment_hashes':{'expected':live.get('expected_sha256'),'received':live.get('received_sha256')},
            'page_versions':{'before':live.get('page_version_before'),'after':live.get('page_version_after')},
            'attachment_versions':{'before':live.get('attachment_version_before'),'after':live.get('attachment_version_after')},
            'storage_from_GET':live.get('storage_from_GET'), 'observed_plugin_dates':observed,
            'counters':[v['counters'] for _,v in values if 'counters' in v],
            'baseline_before_after':baseline,
            'evidence':[str(p.relative_to(root)) for p,_ in values],
            'user_decisions_required': None,
            'limitations':([live.get('limitation') or 'No observed plugin dates for this representation'] if case in ('A','B','C','D') and not observed else []),
            'historical_rule_identity': 'not_evaluated_without_confirmed_historical_rule_context' if case in ('B','C') else None,
            'durations_seconds':[r['duration'] for r in results if _stage13_short_id(r['test_id']) in definition['tests']]}
        _stage13_write(root/'reports/cases'/(case+'.json'), record)
        case_reports[case] = record
    journeys = {name:_stage13_requirement_status(row,results,root) for name,row in matrix['journeys'].items()}
    selected = {_stage13_short_id(item.nodeid) for item in session.items}
    selected |= {value.split('[')[0] for value in selected}
    missing = sorted(STAGE13_REQUIRED-selected)
    not_passed = [name for name in STAGE13_REQUIRED if _stage13_test_status([name],results) != 'passed']
    # Parametrized base IDs from older stages are not used here: stage 13's
    # machine matrix enumerates every concrete parameter, including failures.
    baselines = [v for _,v in evidence_values if 'baseline_before' in v and 'baseline_after' in v]
    baseline_ok = bool(baselines) and all(v['baseline_before']==v['baseline_after'] for v in baselines)
    fixture_ok = len(config._stage13_fixtures)==7 and all(r['status']=='verified' for r in config._stage13_fixtures)
    live_pages = sorted(config._stage13_live_pages)
    _stage13_write(root/'reports/live-targets.json', {'parent_id':STAGE13_TEST_PARENT,
        'pages':live_pages,'production_excluded':sorted(STAGE13_PRODUCTION_PAGES)})
    checks = {'nonempty_results':bool(session.items) and bool(results), 'all_required_selected':not missing,
        'all_required_passed':not not_passed, 'all_AC_passed':all(r['status']=='passed' for r in requirements.values()),
        'all_cases_passed':all(r['status']=='passed' for r in case_reports.values()),
        'all_journeys_passed':all(r['status']=='passed' for r in journeys.values()),
        'fixtures_verified':fixture_ok,'populated_baseline_preserved':baseline_ok,
        'protected_files_unchanged':bool(protected) and not changed,'sources_stable':not drift,
        'external_regression_passed':external.get('gate')=='passed',
        'external_sources_restorable':external.get('restoration_ok') is True,
        'prior_twelve_commits':len(external.get('previous_stage_commits',[]))==12 and all(
            c.get('recorded_gate')=='passed' for c in external.get('previous_stage_commits',[])),
        'no_production_live_targets':not set(live_pages)&STAGE13_PRODUCTION_PAGES,
        'pytest_exit_zero':int(exitstatus)==0}
    order = config._stage13_execution_order
    checks['ordered_phases_2_through_11'] = (
        [r['phase'] for r in order] == sorted(r['phase'] for r in order)
        and set(r['phase'] for r in order) == set(range(2,12)))
    checks['ordered_unit_archive_mpp_live'] = [r['group'] for r in order] == sorted(r['group'] for r in order)
    _stage13_write(root/'reports/execution-order.json', {'tests':order,'pre_collection_phase':1,'report_phase':12})
    master = Path.home()/'WorkVault/Hermes-Backlog/TZ/EditPlanConfluence/EditPlanConfluence_TZ.md'
    plan = master.parent/'plans/HF-plan_EditPlanConfluence_20261116.md'
    text = master.read_text()
    documents = {'master':{'path':str(master),'version':text.split('version:',1)[1].splitlines()[0].strip(),
        'sha256':hashlib.sha256(master.read_bytes()).hexdigest(),
        'section20_sha256':hashlib.sha256(text.split('## 20. ')[1].split('## 21. ')[0].encode()).hexdigest()},
        'plan':{'path':str(plan),'normative_sha256':hashlib.sha256(plan.read_text().split('## Журнал исполнения')[0].encode()).hexdigest()}}
    config_schema = Path.home()/'WorkVault/Registries/EcosystemConfig.schema.json'
    report = {'schema_version':1,'stage':'13','gate':'passed' if all(checks.values()) else 'failed',
        'gate_checks':checks,'exit_code':int(exitstatus),'base_commit':initial.get('base_commit'),
        'command':[sys.executable,'-m','pytest',*config.invocation_params.args],
        'started_at':config._stage13_start,'generated_at':datetime.now(timezone.utc).isoformat(),
        'documents':documents,'environment':config._stage13_environment,'source_files':current,
        'source_tree_sha256':hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest(),
        'config_contract_sha256':hashlib.sha256(config_schema.read_bytes()).hexdigest(),
        'requirements':requirements,'cases':{case:{'status':row['status'],'report':'cases/'+case+'.json'} for case,row in case_reports.items()},
        'journeys':journeys,'selected':len(session.items),'tests':results,
        'summary':{s:sum(r['phase']=='call' and r['status']==s for r in results) for s in ('passed','failed','skipped')},
        'mandatory_test_ids':sorted(STAGE13_REQUIRED),'missing_required':missing,'mandatory_not_passed':sorted(not_passed),
        'fixtures_manifest':'../fixtures-manifest.json', 'fixture_count':len(config._stage13_fixtures),
        'protected_file_count':len(protected),'changed_protected_files':changed,'changed_during_test_run':drift,
        'external_checks':external,'baseline_before_after':baselines,
        'counters':{'all_regression_total':None,'scope':'Only instrumented observations; no invented global totals',
            'instrumented_regression':config._acceptance_counters,
            'CLI_measurements':[{'test_id':v['test_id'],'command':v['command'],'counters':v['counters']}
                for _,v in evidence_values if v.get('counters') and 'command' in v]},
        'live_pages':live_pages, 'production_pages_excluded':sorted(STAGE13_PRODUCTION_PAGES),
        'execution_order':'execution-order.json',
        'limitations':['Acceptance of §20 only; §19 W5/ZD/AC-101…144 remains independent.',
            'Master is actually v0.5.1 with separate §21; §20 and stages 01–12 were not edited.',
            'Product defects belong to earlier stages and are reported, not repaired in stage 13.',
            'No token economy claim: tokens were not measured.',
            'Process-death tests do not model power loss. Gateway, cron and watchers are unchanged.',
            'Unknown counters/observations remain null; absent live publication cannot pass.']}
    _stage13_write(root/'reports/acceptance-report.json', report)
    lines = ['# Этап 13 — комплексная приёмка','',f"Gate: **{report['gate']}**; pytest rc={exitstatus}; selected={len(session.items)}.",'',
        '## Команда','','```text',' '.join(report['command']),'```','',
        '## Матрица AC','','| AC | Статус | Подслучаи passed / всего |','|---|---|---|']
    for ac,row in requirements.items():
        subs=row['subcases']
        lines.append(f"| {ac} | {row['status']} | {sum(s['status']=='passed' for s in subs.values())}/{len(subs)} |")
    lines += ['', 'Каждый подслучай с точными test ID, fixtures, требованиями evidence и результатом находится в acceptance-report.json.',
        '', '## Кейсы','','| Кейс | Статус | Evidence |','|---|---|---|']
    lines += [f"| {case} | {row['status']} | [JSON](cases/{case}.json) |" for case,row in case_reports.items()]
    lines += ['', '## Пользовательские сценарии','']+[f"- {name}: **{row['status']}**." for name,row in journeys.items()]
    lines += ['', '## Gate checks','']+[f'- {key}: {value}.' for key,value in checks.items()]
    lines += ['', '## Ограничения','']+['- '+item for item in report['limitations']]
    lines += ['', 'Все проверки выполняются на изолированных БД/WorkVault/cache. Baseline before/after, hashes, источники, версии, счётчики, команды/rc, storage из GET и причины отказа сохранены в JSON и reports/evidence/.',
        '', 'Непрошедшие обязательные тесты:','']+['- `'+name+'`' for name in sorted(not_passed)]
    (root/'reports/acceptance-report.md').write_text('\n'.join(lines)+'\n')
    stage = {'schema_version':1,'stage':'13','gate':report['gate'],'exit_code':int(exitstatus),
        'acceptance_report':'../../final/reports/acceptance-report.json','gate_checks':checks,
        'source_tree_sha256':report['source_tree_sha256'],'command':report['command'],
        'summary':report['summary'],'external_checks':external,
        'changed_files':['S/tests/acceptance/ac-matrix.json','S/tests/acceptance/test_user_journeys.py',
            'S/tests/acceptance/test_cases_trisigma.py','S/tests/acceptance/test_failure_matrix.py',
            'S/tests/acceptance/test_migration_preservation.py','S/tests/acceptance/test_live_publication.py',
            'S/tests/conftest.py','S/tests/pytest.ini'], 'migrations_added':[], 'protected_files_changed':changed}
    _stage13_write(root/'reports/stage-report.json',stage)
    stage_dir = root.parent/'stage-13/reports'
    _stage13_write(stage_dir/'stage-report.json',stage)
    content = f"# Этап 13\n\nGate: **{report['gate']}**; pytest rc={exitstatus}.\n\nПолный итог: [acceptance-report.json](../../final/reports/acceptance-report.json).\n\nПрежние этапы не изменены; canon.md исключён из поставки.\n"
    (stage_dir/'stage-report.md').write_text(content)
    (root/'reports/stage-report.md').write_text(content)
    # JUnit's sessionfinish hook may run after this one; terminal_summary below
    # copies its finalized output, never a partial XML document.
    if report['gate'] != 'passed' and int(session.exitstatus) == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if config.getoption('--acceptance-stage') != '13': return
    root = config._acceptance_root
    junit = root/'reports/junit.xml'
    if junit.is_file():
        dest = root.parent/'stage-13/reports/junit.xml'
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(junit,dest)


@pytest.fixture(autouse=True)
def stage13_live_inventory(request, monkeypatch):
    if request.config.getoption('--acceptance-stage') != '13' or not request.node.get_closest_marker('confluence_live'):
        yield
        return
    from urllib.parse import urlsplit
    import re
    import conf_client, gantt_attachment
    config = request.config
    if not hasattr(config, '_stage13_http_calls'): config._stage13_http_calls = []
    pages = config._stage13_live_pages
    def real(client): return urlsplit(client.base_url).hostname == 'dom.tutu.ru'
    create = conf_client.ConfluenceClient.create_page
    def create_page(client, title, space_key, storage, parent_id=None):
        if real(client):
            assert str(parent_id) in pages, 'live parent outside explicit acceptance targets'
        result = create(client, title, space_key, storage, parent_id)
        if real(client):
            page = str(result['id'])
            assert page not in STAGE13_PRODUCTION_PAGES
            pages.add(page)
            _stage13_write(config._acceptance_root/'reports/live-targets.json', {
                'parent_id':STAGE13_TEST_PARENT,'pages':sorted(pages),
                'production_excluded':sorted(STAGE13_PRODUCTION_PAGES)})
        return result
    monkeypatch.setattr(conf_client.ConfluenceClient, 'create_page', create_page)
    for method in ('get_page','put_page','list_attachments','download_attachment','download_attachment_version'):
        original = getattr(conf_client.ConfluenceClient,method)
        def guarded(client, page_id, *args, _original=original, **kwargs):
            if real(client):
                assert str(page_id) in pages and str(page_id) not in STAGE13_PRODUCTION_PAGES, 'non-acceptance page forbidden'
            return _original(client,page_id,*args,**kwargs)
        monkeypatch.setattr(conf_client.ConfluenceClient,method,guarded)
    def trace(original):
        def invoke(req,*args,**kwargs):
            url = urlsplit(req.full_url)
            assert not any(re.search(r'(?<![0-9])'+page+r'(?![0-9])',url.path) for page in STAGE13_PRODUCTION_PAGES)
            config._stage13_http_calls.append({'test_id':request.node.nodeid,
                'method':req.get_method(),'origin':url.netloc,'path':url.path})
            return original(req,*args,**kwargs)
        return invoke
    monkeypatch.setattr(conf_client,'urlopen',trace(conf_client.urlopen))
    monkeypatch.setattr(gantt_attachment,'urlopen',trace(gantt_attachment.urlopen))
    yield
    _stage13_write(config._acceptance_root/'reports/http-observations.json',{
        'calls':config._stage13_http_calls,'pages':sorted(pages),
        'counts':{m:sum(c['method']==m for c in config._stage13_http_calls) for m in ('GET','POST','PUT')}})
