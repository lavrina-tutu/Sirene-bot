# Этап 10 — сетевые стадии, идемпотентность и восстановление

Gate: **failed**; S rc=2; selected=570; passed=338.

prepared → archived → admitted → attachment_uploaded → attachment_verified → storage_written → storage_verified → confirmed.

- `S/scripts/pipeline.py`: admitted lifecycle, intent before effects, exact/current read-back, resume, bounded 409 patch, unchanged/storage-only, child, AB guard, sticky schedule mismatch.
- `S/scripts/plan_operation.py`: typed append-only network plan/intents/observations/stages with atomic receipt mirrors.
- `S/scripts/plan_reconcile.py`: current page/attachment versions and managed fingerprints before replay; uncertain POST/PUT resolved by reads.
- `S/scripts/plan_lock.py`: namespace/page/macro flock, live owner, release after process death.
- `S/scripts/conf_client.py`: frozen timeout/retry, bounded GET-only retries, exact version=N without status, parent/title child lookup.
- `S/scripts/gantt_attachment.py`: archived deterministic bytes, exact ID/version and timeout, no override.
- `S/scripts/plan_verify.py`: canonical full macro and summary fingerprint; preservation checks.
- `S/scripts/child_page.py`: exact parent/title/managed-state reconciliation after uncertain creation.
- `S/scripts/plan_receipt.py`: validated published true/false/null and external-effect semantics.
- `M/mofs_index/plan/schema.py`: only new 0012_publish_confirmation; previous definitions unchanged.
- `M/mofs_index/plan/writer.py + query.py`: atomic verified_v1 observation/publication/snapshot/admission/profile/schedule links and result event; scoped read API.
- `S/tests + M/tests/plan`: fault matrix, actual os._exit/SIGKILL over HTTP, concurrency, integrity/atomicity, live dedicated pages.
- `S/references/operations-and-recovery.md + cli-contract.md`: numeric settings and recovery contract.

Команда S:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 10 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/stage10-20261116T193250/stage-10 -m unit or archive_integration or confluence_live --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/stage10-20261116T193250/stage-10/reports/junit.xml
```

Команды/rc/JUnit MofsIndex и восстановление внешнего комплекта: external-checks.json.
HTTP dedicated pages: stage10-live.json; plugin controls: stage08-live.json; реальный process-death/HTTP: stage10-process-*.json.

Live stage10: {'POST': 2, 'PUT': 1, 'GET': 34}. Проверенное дерево: `9becea1038c9765110368351febfd7e291cca53c122189480be122bbee740c75`.

Защищённых файлов: 672, изменено: 0. canon.md исключён из поставки; hash проверен.

Ограничения:

- Only stage 10; stages 11–13 and full §20 acceptance are not claimed.
- Live admitted plan is an explicit synthetic parsed fixture. Real binary MPP extraction limitations remain; schedule:not_verified. No arbitrary-plan schedule equality is claimed.
- Flock protects processes sharing the configured WorkVault on this host; external writers are detected by fresh version/hash checks, not a distributed transaction.
- Confirmation describes the exact versions at observation time. A later foreign edit can change the page.
- Post-write schedule mismatch is retained as an error and never rolled back automatically.
- The on-disk master is 0.5.1 with a separate §21; stage 10 follows agreed §20. Master/§21 were not edited and that separate BUGFIX is not declared accepted.
- OwnCloud sync is not confirmed. Production DB/A–D/AB pages, Gateway, configs, crons, watchers and schedules were not changed.
