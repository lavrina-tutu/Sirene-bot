# Этап 13 — комплексная приёмка

Gate: **failed**; pytest rc=2; selected=718.

## Команда

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 13 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261117-stage13/final -m unit or archive_integration or mpp_fixtures or confluence_live --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261117-stage13/final/reports/junit.xml
```

## Матрица AC

| AC | Статус | Подслучаи passed / всего |
|---|---|---|
| AC-01 | not_run | 0/0 |
| AC-02 | not_run | 0/0 |
| AC-03 | not_run | 0/0 |
| AC-04 | not_run | 1/7 |
| AC-05 | passed | 0/0 |
| AC-06 | not_run | 0/0 |
| AC-07 | passed | 0/0 |
| AC-08 | not_run | 0/0 |
| AC-09 | not_run | 1/7 |
| AC-10 | passed | 0/0 |
| AC-11 | not_run | 0/0 |
| AC-12 | not_run | 0/0 |
| AC-13 | not_run | 0/0 |
| AC-14 | passed | 0/0 |
| AC-15 | passed | 0/0 |
| AC-16 | not_run | 0/0 |
| AC-17 | not_run | 0/0 |
| AC-18 | not_run | 0/0 |
| AC-19 | not_run | 0/20 |
| AC-20 | not_run | 0/11 |
| AC-21 | not_run | 0/0 |
| AC-22 | not_run | 0/11 |
| AC-23 | not_run | 0/0 |
| AC-24 | not_run | 0/10 |
| AC-25 | not_run | 0/0 |
| AC-26 | not_run | 0/0 |
| AC-27 | not_run | 0/0 |

Каждый подслучай с точными test ID, fixtures, требованиями evidence и результатом находится в acceptance-report.json.

## Кейсы

| Кейс | Статус | Evidence |
|---|---|---|
| A | not_run | [JSON](cases/A.json) |
| B | not_run | [JSON](cases/B.json) |
| C | not_run | [JSON](cases/C.json) |
| D | not_run | [JSON](cases/D.json) |
| E | not_run | [JSON](cases/E.json) |
| F | not_run | [JSON](cases/F.json) |
| G | not_run | [JSON](cases/G.json) |
| D-risks | not_run | [JSON](cases/D-risks.json) |

## Пользовательские сценарии

- 01-publish-no-general-consent: **not_run**.
- 02-save-no-client-baseline: **not_run**.
- 03-inbox-one-text-command: **not_run**.
- 04-batch-show-errors: **not_run**.
- 05-register-then-retry-decisions: **not_run**.
- 06-arrival-chronology: **not_run**.
- 07-today-local-offset: **not_run**.
- 08-exact-selectors: **not_run**.
- 09-current-vs-confirmed-publication: **not_run**.
- 10-reconcile-before-resume: **not_run**.
- 11-new-MPP-identity-resume: **not_run**.

## Gate checks

- nonempty_results: True.
- all_required_selected: True.
- all_required_passed: False.
- all_AC_passed: False.
- all_cases_passed: False.
- all_journeys_passed: False.
- fixtures_verified: True.
- populated_baseline_preserved: False.
- protected_files_unchanged: False.
- sources_stable: True.
- external_regression_passed: True.
- external_sources_restorable: True.
- prior_twelve_commits: True.
- no_production_live_targets: True.
- pytest_exit_zero: False.

## Ограничения

- Acceptance of §20 only; §19 W5/ZD/AC-101…144 remains independent.
- Master is actually v0.5.1 with separate §21; §20 and stages 01–12 were not edited.
- Product defects belong to earlier stages and are reported, not repaired in stage 13.
- No token economy claim: tokens were not measured.
- Process-death tests do not model power loss. Gateway, cron and watchers are unchanged.
- Unknown counters/observations remain null; absent live publication cannot pass.

Все проверки выполняются на изолированных БД/WorkVault/cache. Baseline before/after, hashes, источники, версии, счётчики, команды/rc, storage из GET и причины отказа сохранены в JSON и reports/evidence/.

Непрошедшие обязательные тесты:

- `test_batch_decisions.py::test_ac19_context_immutable[parameters0]`
- `test_batch_decisions.py::test_ac19_context_immutable[parameters1]`
- `test_batch_decisions.py::test_ac19_context_immutable[parameters2]`
- `test_batch_decisions.py::test_ac19_context_immutable[parameters3]`
- `test_batch_decisions.py::test_ac19_continue_registration_and_explicit_consumption`
- `test_batch_decisions.py::test_ac19_foreign_stale_and_changed_grounds`
- `test_batch_decisions.py::test_ac19_lineage_two_reasons_and_stop[continue-False]`
- `test_batch_decisions.py::test_ac19_lineage_two_reasons_and_stop[continue-True]`
- `test_batch_decisions.py::test_ac19_lineage_two_reasons_and_stop[stop-False]`
- `test_batch_decisions.py::test_ac19_lineage_two_reasons_and_stop[stop-True]`
- `test_batch_decisions.py::test_ac19_no_artificial_decisions`
- `test_batch_decisions.py::test_ac19_process_death_after_registration_and_commit[registered]`
- `test_batch_decisions.py::test_ac19_process_death_after_registration_and_commit[snapshot_committed]`
- `test_batch_decisions.py::test_ac19_proved_conflict_is_item_failure`
- `test_batch_decisions.py::test_ac19_real_cli_registration_and_retry`
- `test_batch_decisions.py::test_ac19_registration_batch_busy`
- `test_batch_decisions.py::test_ac19_registration_transaction_rollback`
- `test_batch_resume.py::test_freeze_failure_never_accepts_new_bytes_under_same_id[changed]`
- `test_batch_resume.py::test_freeze_failure_never_accepts_new_bytes_under_same_id[hash]`
- `test_batch_resume.py::test_freeze_failure_never_accepts_new_bytes_under_same_id[missing]`
- `test_batch_resume.py::test_journaling_failure_stops_after_confirmed_success`
- `test_batch_resume.py::test_lost_frozen_artifact_infrastructure_only_identical_repair`
- `test_batch_resume.py::test_mirror_failure_preserves_commit_and_restores_without_reader[batch]`
- `test_batch_resume.py::test_mirror_failure_preserves_commit_and_restores_without_reader[save]`
- `test_batch_resume.py::test_missing_mirror_recovery_verifies_committed_artifacts`
- `test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[after_first_freeze]`
- `test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[after_freeze_barrier]`
- `test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[after_item_result]`
- `test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[after_snapshot_commit]`
- `test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[before_batch_receipt]`
- `test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[before_freeze_barrier]`
- `test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[before_save_receipt]`
- `test_batch_resume.py::test_process_death_freeze_commit_receipt_boundaries[before_snapshot_commit]`
- `test_batch_resume.py::test_resume_rejects_changed_frozen_context`
- `test_batch_resume.py::test_resume_stop_retries_only_explicit_retryable_same_bytes`
- `test_cases_trisigma.py::test_real_cold_warm_archive[A]`
- `test_cases_trisigma.py::test_real_cold_warm_archive[B]`
- `test_cases_trisigma.py::test_real_cold_warm_archive[C]`
- `test_cases_trisigma.py::test_real_cold_warm_archive[D-risks]`
- `test_cases_trisigma.py::test_real_cold_warm_archive[D]`
- `test_cases_trisigma.py::test_real_cold_warm_archive[E]`
- `test_cases_trisigma.py::test_real_cold_warm_archive[F]`
- `test_cli.py::test_cli_convert_offline`
- `test_compare_e2e.py::test_ac24_cli[AC24-10]`
- `test_compare_e2e.py::test_ac24_cli[AC24-1]`
- `test_compare_e2e.py::test_ac24_cli[AC24-2]`
- `test_compare_e2e.py::test_ac24_cli[AC24-3]`
- `test_compare_e2e.py::test_ac24_cli[AC24-4]`
- `test_compare_e2e.py::test_ac24_cli[AC24-5]`
- `test_compare_e2e.py::test_ac24_cli[AC24-6]`
- `test_compare_e2e.py::test_ac24_cli[AC24-7]`
- `test_compare_e2e.py::test_ac24_cli[AC24-8]`
- `test_compare_e2e.py::test_ac24_cli[AC24-9]`
- `test_compare_e2e.py::test_compare_exact_publication_ids_same_v2_on_different_pages`
- `test_compare_e2e.py::test_compare_same_source_precision_unknown_zone_and_causality`
- `test_failure_matrix.py::test_identity_choice_complete_preparation_chain[missing]`
- `test_failure_matrix.py::test_identity_choice_complete_preparation_chain[replace-selected]`
- `test_failure_matrix.py::test_matrix_requires_all_ac_and_subcases`
- `test_failure_matrix.py::test_report_aggregate_rejects_missing_evidence`
- `test_failure_matrix.py::test_report_never_promotes_incomplete_execution[call-failed-failed]`
- `test_failure_matrix.py::test_report_never_promotes_incomplete_execution[call-passed-passed]`
- `test_failure_matrix.py::test_report_never_promotes_incomplete_execution[call-skipped-not_run]`
- `test_failure_matrix.py::test_report_never_promotes_incomplete_execution[setup-failed-failed]`
- `test_failure_matrix.py::test_report_never_promotes_incomplete_execution[setup-skipped-not_run]`
- `test_failure_matrix.py::test_report_never_promotes_incomplete_execution[teardown-failed-failed]`
- `test_history_queries.py::test_history_all_views_paginate_without_duplicates[files-item_id]`
- `test_history_queries.py::test_history_all_views_paginate_without_duplicates[publications-publication_id]`
- `test_history_queries.py::test_history_all_views_paginate_without_duplicates[snapshots-snapshot_id]`
- `test_history_queries.py::test_history_cli_matches_typed_api`
- `test_history_queries.py::test_history_cursor_cannot_change_filter`
- `test_history_queries.py::test_history_cursor_stable_ties_unknowns_and_new_backdated_arrival[ingested]`
- `test_history_queries.py::test_history_cursor_stable_ties_unknowns_and_new_backdated_arrival[source]`
- `test_history_queries.py::test_history_filter_fields_are_distinct_order_source_does_not_change_filter`
- `test_history_queries.py::test_history_half_open_timezone_and_equal_timestamps`
- `test_history_queries.py::test_history_invalid_parameters_fail_closed[parameters0]`
- `test_history_queries.py::test_history_invalid_parameters_fail_closed[parameters1]`
- `test_history_queries.py::test_history_invalid_parameters_fail_closed[parameters2]`
- `test_history_queries.py::test_history_invalid_parameters_fail_closed[parameters3]`
- `test_history_queries.py::test_history_invalid_parameters_fail_closed[parameters4]`
- `test_history_queries.py::test_history_invalid_parameters_fail_closed[parameters5]`
- `test_history_queries.py::test_history_invalid_parameters_fail_closed[parameters6]`
- `test_history_queries.py::test_history_invalid_parameters_fail_closed[parameters7]`
- `test_history_queries.py::test_history_project_lineage_scope_and_failed_arrivals`
- `test_history_queries.py::test_history_unknown_time_separate_count`
- `test_history_queries.py::test_history_views_and_defaults`
- `test_history_queries.py::test_q_history_integration_uses_same_api`
- `test_identity_resume_e2e.py::test_real_binary_bootstrap_identity_resume_without_preliminary_save`
- `test_identity_resume_e2e.py::test_real_mpp_new_snapshot_separate_clean_environments[diff]`
- `test_identity_resume_e2e.py::test_real_mpp_new_snapshot_separate_clean_environments[publish]`
- `test_import_atomicity.py::test_different_zip_containers_same_mpp_reuse_snapshot`
- `test_import_atomicity.py::test_failed_zip_receipt_retains_container_locator`
- `test_import_atomicity.py::test_operation_repeat_preserves_item_adds_attempt`
- `test_import_atomicity.py::test_process_death_commit_boundaries[after_commit]`
- `test_import_atomicity.py::test_process_death_commit_boundaries[after_event]`
- `test_import_atomicity.py::test_process_death_commit_boundaries[after_item_link]`
- `test_import_atomicity.py::test_process_death_commit_boundaries[after_snapshot]`
- `test_import_atomicity.py::test_process_death_commit_boundaries[after_versions]`
- `test_import_atomicity.py::test_process_death_commit_boundaries[before_commit]`
- `test_import_atomicity.py::test_process_death_commit_boundaries[before_readback]`
- `test_import_atomicity.py::test_process_death_commit_boundaries[before_receipt]`
- `test_import_atomicity.py::test_readback_failure_retains_commit_and_no_second_parse`
- `test_import_atomicity.py::test_two_processes_one_snapshot_two_receipts`
- `test_import_atomicity.py::test_unresolved_project_has_durable_input_no_fake_snapshot`
- `test_itogo.py::test_real_prepared_work_tolerance[A-1576]`
- `test_itogo.py::test_real_prepared_work_tolerance[B-2096]`
- `test_itogo.py::test_real_prepared_work_tolerance[C-2088]`
- `test_itogo.py::test_real_prepared_work_tolerance[D-3136]`
- `test_live_publication.py::test_installed_names_after_live`
- `test_live_publication.py::test_new_binary_identity_to_publication[diff]`
- `test_live_publication.py::test_new_binary_identity_to_publication[publish]`
- `test_live_publication.py::test_real_publish_repeat_and_observed_dates[A]`
- `test_live_publication.py::test_real_publish_repeat_and_observed_dates[B]`
- `test_live_publication.py::test_real_publish_repeat_and_observed_dates[C]`
- `test_live_publication.py::test_real_publish_repeat_and_observed_dates[D]`
- `test_mpp_calendar.py::test_calendar_from_mpp_fixture`
- `test_pipeline.py::test_build_plan_from_mpp_offline`
- `test_plan_archive.py::test_artifact_corruption_is_not_duplicate_success`
- `test_plan_archive.py::test_explicit_slug_and_contradictory_bindings_rejected`
- `test_plan_archive.py::test_resolve_plan_binding_creates_and_is_idempotent`
- `test_plan_archive.py::test_resolve_plan_binding_different_pages_different_lineage`
- `test_plan_archive.py::test_resolve_plan_binding_requires_slug_for_new_page`
- `test_plan_archive.py::test_same_filename_different_bytes_get_different_objects`
- `test_plan_archive.py::test_stable_local_lineage_preserves_old_filename_lines`
- `test_plan_archive.py::test_store_artifact_dedup_survives_tmp_deletion`
- `test_plan_batch.py::test_batch_cli_argument_errors_single_json[arguments0]`
- `test_plan_batch.py::test_batch_cli_argument_errors_single_json[arguments1]`
- `test_plan_batch.py::test_batch_cli_argument_errors_single_json[arguments2]`
- `test_plan_batch.py::test_batch_cli_argument_errors_single_json[arguments3]`
- `test_plan_batch.py::test_batch_cli_argument_errors_single_json[arguments4]`
- `test_plan_batch.py::test_corrupt_middle_continue_stop_freeze_whole_list[continue-expected0]`
- `test_plan_batch.py::test_corrupt_middle_continue_stop_freeze_whole_list[stop-expected1]`
- `test_plan_batch.py::test_duplicates_within_across_batches_and_same_names_different_bytes`
- `test_plan_batch.py::test_existing_batch_same_request_only_state_changed_manifest_conflicts`
- `test_plan_batch.py::test_fixtures_batch_hashes_and_manifest_cases`
- `test_plan_batch.py::test_foreign_lineage_is_local_failure_and_new_mpp_needs_no_decision`
- `test_plan_batch.py::test_freeze_all_before_first_reader_and_mutated_second_source`
- `test_plan_batch.py::test_inbox_late_file_excluded_diagnostics_and_sources_preserved`
- `test_plan_batch.py::test_infrastructure_after_success_has_priority_and_retains_counts`
- `test_plan_batch.py::test_missing_input_and_expected_hash_known_before_first_parse`
- `test_plan_batch.py::test_real_batch_cli_native_copies[inbox]`
- `test_plan_batch.py::test_real_batch_cli_native_copies[manifest]`
- `test_plan_batch.py::test_real_batch_cli_native_copies[mpp]`
- `test_plan_batch.py::test_real_batch_cli_native_copies[named-risks]`
- `test_plan_batch.py::test_receipt_balance_and_priority`
- `test_plan_batch.py::test_same_bytes_different_timezone_and_profile_new_scope`
- `test_plan_batch.py::test_structural_errors_precede_arrivals`
- `test_plan_cache.py::test_real_parse_cache_one_read_same_bytes_different_names`
- `test_plan_history.py::test_find_mpp_by_hash_missing_file_not_fabricated`
- `test_plan_history.py::test_import_history_distinguishes_403_404_timeout`
- `test_plan_history.py::test_import_history_missing_version_recorded_in_quality_issue`
- `test_plan_history.py::test_import_history_repeat_does_not_increase_counts`
- `test_plan_history.py::test_import_history_resume_attempt_id_does_not_duplicate_attempt`
- `test_plan_history.py::test_import_history_six_events_four_unique_hashes`
- `test_plan_history.py::test_import_history_without_resume_key_creates_new_attempt_each_call`
- `test_plan_identity.py::test_confirm_show_no_automatic_operation_start_and_evidence_copy`
- `test_plan_identity.py::test_foreign_project_pair_and_unknown_uid_are_conflicts`
- `test_plan_identity.py::test_mapping_rejects_duplicate_json_keys_and_continuity_mapping_argument`
- `test_plan_identity.py::test_operation_requirements_partial_then_sufficient_and_fixed_revision`
- `test_plan_identity.py::test_q_identity_integration_uses_same_api`
- `test_plan_identity.py::test_real_cli_confirm_show_errors_and_no_resume`
- `test_plan_identity.py::test_real_independent_mpp_same_uid_stays_unknown`
- `test_plan_identity.py::test_schema_matches_runtime_validator`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[None]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document1]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document2]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document3]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document4]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document5]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document6]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document7]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document8]`
- `test_plan_identity.py::test_strict_mapping_shape_before_mutation[document9]`
- `test_plan_lock.py::test_lock_busy_independent_process_and_release_after_death`
- `test_plan_lock.py::test_two_batch_handlers_busy_without_duplicate_arrivals`
- `test_plan_reconcile.py::test_import_reconcile_missing_link_is_not_reimported`
- `test_plan_reconcile.py::test_reconcile_no_candidate_gives_unknown`
- `test_plan_reconcile.py::test_reconcile_single_candidate_does_not_confirm_operation`
- `test_plan_reconcile.py::test_reconcile_two_candidates_same_version_gives_unknown`
- `test_plan_reconcile.py::test_reconcile_writes_event_and_receipt`
- `test_plan_save.py::test_complete_save_and_unknown_timezone_sql_status`
- `test_plan_save.py::test_corrupt_archived_source_or_export_never_duplicate_success[export]`
- `test_plan_save.py::test_corrupt_archived_source_or_export_never_duplicate_success[source]`
- `test_plan_save.py::test_frozen_input_never_refreezes_or_opens_original`
- `test_plan_save.py::test_invalid_arguments_before_intake[source_version_date-2026-02-30]`
- `test_plan_save.py::test_invalid_arguments_before_intake[source_version_date-20261115]`
- `test_plan_save.py::test_invalid_arguments_before_intake[timezone_hint-Not/AZone]`
- `test_plan_save.py::test_missing_runtime_is_explicit_failure_before_read`
- `test_plan_save.py::test_quality_warnings_do_not_block_archive`
- `test_plan_save.py::test_reader_diagnostics_use_stderr_and_artifacts`
- `test_plan_save.py::test_receipt_mirror_failure_preserves_commit_and_recovers`
- `test_plan_save.py::test_recovery_after_commit_before_readback_no_reader`
- `test_plan_save.py::test_save_creates_snapshot_without_page_id`
- `test_plan_save.py::test_save_deduplicates_and_preserves_each_arrival`
- `test_plan_save.py::test_save_explicit_lineage_and_version_date`
- `test_plan_save.py::test_save_missing_input_is_failed_arrival`
- `test_plan_save.py::test_save_preserves_populated_baseline_and_publication_rows`
- `test_plan_save.py::test_save_requires_project_slug_preserves_input`
- `test_plan_save.py::test_save_with_page_id_reuses_existing_lineage`
- `test_plan_save.py::test_unusable_snapshot_is_not_success[bad_count]`
- `test_plan_save.py::test_unusable_snapshot_is_not_success[invalid_schema]`
- `test_plan_save.py::test_unusable_snapshot_is_not_success[legacy_export]`
- `test_plan_save.py::test_unusable_snapshot_is_not_success[no_tasks]`
- `test_plan_save.py::test_unusable_snapshot_is_not_success[wrong_source]`
- `test_plan_verify.py::test_archive_client_construction_is_disabled`
- `test_plugin_controls_live.py::test_installed_plugin_controls_live`
- `test_publication_verify.py::test_stage11_live_verify_only_get_repeat_and_historical_scope`
- `test_publication_verify.py::test_verify_cli_loopback_concurrent_reads_append_observations`
- `test_publish_live.py::test_stage09_live_publish_bytes_storage_and_binary_blocker`
- `test_publish_resume.py::test_real_process_death_http_reconciliation[after_confirmation]`
- `test_publish_resume.py::test_real_process_death_http_reconciliation[after_post]`
- `test_publish_resume.py::test_real_process_death_http_reconciliation[after_put]`
- `test_publish_resume.py::test_real_process_death_http_reconciliation[before_post]`
- `test_publish_resume.py::test_real_process_death_http_reconciliation[before_put]`
- `test_publish_resume.py::test_real_process_death_http_reconciliation[hold_post]`
- `test_rest_live.py::test_live_get_test_page`
- `test_rest_live.py::test_stage10_live_recovery_idempotency_and_child`
- `test_save_e2e.py::test_cli_cache_corruption_rebuilds_once`
- `test_save_e2e.py::test_cli_corrupt_mpp_is_failed_not_empty_plan`
- `test_save_e2e.py::test_cli_zip_intake_inside_save`
- `test_save_e2e.py::test_cli_zip_multiple_candidates_retains_list`
- `test_save_e2e.py::test_real_cli_cold_warm_save[E-78-84]`
- `test_save_e2e.py::test_real_cli_cold_warm_save[F-86-93]`
- `test_skill_contract.py::test_real_archive_stdout_and_receipts_redact_secrets`
- `test_user_journeys.py::test_inbox_errors_resume_and_history[continue]`
- `test_user_journeys.py::test_inbox_errors_resume_and_history[stop]`
- `test_user_journeys.py::test_real_ef_batch_and_exact_compare`
- `test_user_journeys.py::test_today_cli_local_boundaries`
