# Этап 03

Gate: **passed**. S rc=0; passed=221; selected=221.

MofsIndex: 43 обязательных, 82 в полной plan-регрессии. Подробные команды/rc/JUnit: external-checks.json.

Дерево исходников: `d81fcbbc2d58a3a217b9bc23751e0fc022ae479e9d50dc7928580f6ff3afd92e`. Master 0.5.0, hash в JSON. Миграции: 0007_durable_imports, 0008_snapshot_semantics.

Реализовано:

- `M/mofs_index/plan/schema.py`: 0007 durable imports/nullable operation context; 0008 semantic dedup and lossless version fields; all_plan_table_names.
- `M/mofs_index/plan/migrate.py`: transactional create-copy-drop-rename with FK restoration/check, checksums and migration concurrency; refuses caller transaction.
- `M/mofs_index/plan/writer.py`: typed operations/batches/items/attempts/events; one atomic snapshot-version-item-event commit; artifact verification; exact decimals.
- `M/mofs_index/plan/ingest_mpp.py`: legacy/v2/PreparedPlan adapters; complete source JSON, quantities/units, intervals and runtime/profile fingerprint.
- `M/mofs_index/plan/query.py`: typed reads for operation/item/batch/attempt/events/artifact/lineage/snapshot/dedup/committed link.
- `S/scripts/plan_archive.py`: atomic content-addressed artifact store/read-back; explicit slug/lineage/page conflicts; stable local archive lineage.
- `S/scripts/mpp_input.py`: consistent double-read freeze; durable locator; ZIP content detection, all-member safety and numeric limits; no first candidate selection.
- `S/scripts/plan_operation.py`: register unresolved operation/item before project; persist effective context, freeze/error provenance; new attempt on repeat; commit/reconcile adapter.
- `S/scripts/plan_reconcile.py`: committed link then read-back; no parser path; mirror failure retains SQL commit.
- `S/scripts/plan_save.py`: only replace filename-based local lineage with stable project archive binding; full pipeline wiring remains stage 04.
- `M/tests/plan/{test_schema,test_migrate,test_writer_snapshot,test_backup}.py`: new/legacy migrations, rollback, rebuild preservation, exact values, dedup and backup.
- `S/tests/{test_mpp_input,test_plan_archive,test_plan_reconcile,test_import_atomicity}.py`: ZIP/input adversarial tests, real two-process concurrency and eight os._exit crash boundaries.
- `S/tests/conftest.py + S/references/operations-and-recovery.md`: stage-03 mandatory IDs/gate/report and reproducible internal API/input profile contract.

Атомарность: single BEGIN IMMEDIATE: snapshot -> versions -> item.snapshot_id -> snapshot_committed -> COMMIT; no nested public writer

Дедупликация: plan+lineage+source_mpp_sha256+representation+normalization_profile_fingerprint+resolved_timezone; two DB unique indices; legacy NULL profile excluded

Восстановление: committed item/event link -> verified source/hash and normalized/version read-back -> optional receipt mirror; no reader after commit

Вход: input-v1; double open-file read/size/mtime/ctime/inode/hash plus fsync+atomic rename under explicit WorkVault; ZIP per-member/content/path/type/size/ratio checks

Команда S:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 03 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage03-141956/stage-03 -m unit or archive_integration --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage03-141956/stage-03/reports/junit.xml
```

Проверено восемь границ падения процесса: после snapshot, versions, item-link, event, до COMMIT, после COMMIT, до read-back, до квитанции. Два независимых процесса оставляют один snapshot и два поступления.

Комплект внешних изменений: usertools/MofsIndex/{before,after,changes.patch,manifest.json}; восстановление и hashes — external-checks.json. SHA завершающего коммита записывается в журнал канонического плана после commit.

Ограничения:

- Only stage 03: public prepared save/CLI integration is stage 04; batch orchestration is stages 05-06
- No production DB migration, Confluence/network publication or schedule verification
- No edits to stage-01/02 evidence, applied migrations 0001-0006, MppReader or EcosystemConfig
- ownCloud sync not confirmed; process-death tests do not simulate OS/power failure
