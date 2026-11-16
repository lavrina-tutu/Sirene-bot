# Этап 09 — первичный snapshot, допуск и B/C

Gate: **passed**. S rc=0; selected=528; passed=526.

- `S/scripts/pipeline.py`: prepare_publish; shared diff/publish/apply; primary archive/read-back before identity/admission; durable evidence then network primitives; exact-version download without status=any; valid storage paragraph assembly.
- `S/scripts/plan_policy.py`: all 19 normative rows; blockers cannot choose warning severity; concrete proposals only; accepted_deviation independent of verified.
- `S/scripts/plan_diagnostics.py`: conservative completeness, graph, capability losses, per-task/milestone minute dates and separated evidence layers; no reopening MPP for scheduler.
- `S/scripts/plan_rules.py`: immutable project rules, reference/evidence, exact sufficient mapping, original type/signed lag/basis and task context, current cause, derived-only exclusion, not_needed; source-bound legacy drop-dep.
- `S/scripts/plan_operation.py + plan_decision.py`: preparation history/show, addressed proposals and decisions, single resume and preserved batch contract, project-scoped consent persistence.
- `S/scripts/cli.py + references/cli-contract.md`: publish/diff/apply slug and paths; mutually exclusive resume forms; archive receipt and fixed context.
- `S/references/profiles/publication-policy-v1.json + project-rules-v1.json`: versioned conservative field/date policy and inactive unanchored historical B/C, without guessed stable keys or invented evidence.
- `M/mofs_index/plan/schema.py`: only 0011_publish_preparation; append-only preparations/rules/proposals/decisions/admission/artifact bindings; 0001–0010 unchanged.
- `M/mofs_index/plan/writer.py + query.py`: typed write/read APIs; new timezone snapshot link preserves intake and previous preparation; revision-scoped identity choices and audit.
- `S/tests/test_admission.py + test_plan_rules.py + test_publish_prepare.py + test_identity_resume_e2e.py + test_publish_live.py`: matrix, zero-write blockers, B/C, timezone, identity/bootstrap, real binary cold/resume, actual HTTP bytes/storage.
- `S/tests/fixtures/synthetic/new-source-identity-resume`: explicit test-only export and user evidence; no production identity assertion.
- `M/tests/plan/test_preparation.py + test_migrate.py + test_identity.py`: new migration/typed contracts, preservation and current migration expectations; older migration definitions remain fixed.
- `S/tests/test_pipeline.py`: existing stage-01 network verification cases explicitly exercise preserved legacy helper; public apply now uses mandatory admission.
- `S/tests/conftest.py`: stage-09 mandatory IDs, group order, actual report/gate; earlier maps/reports retained.

Порядок: frozen input → prepared → проект/lineage и GET цели → исходный snapshot → read-back → identity/B/C → повторная диагностика → долговечный artifact/evidence/admission → сеть. Diff завершает подготовку без POST/PUT.

Матрица: 19 строк с параметризованными тестами; запрещающие случаи сохраняют архив и имеют POST=PUT=0. Даты всех задач/вех: ≤60 секунд, без абсолютного сравнения при unknown timezone. Общего override предупреждений нет.

B/C: точная достаточная mapping revision и обе задачи, сохранность исходных связей и контекста, актуальная причина, повторный допуск, not_needed. Таймзона создаёт новую подготовку и snapshot без автоматического переноса решений.

Команда S:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 09 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage09-181250/stage-09 -m unit or archive_integration or mpp_fixtures or confluence_live --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage09-181250/stage-09/reports/junit.xml
```

MofsIndex: команды/rc/JUnit и восстановление before/after/patch — external-checks.json. Реальные MPP: stage09-real-diff.json / stage09-real-publish.json. HTTP: stage09-live.json. Отдельная успешная публикация синтетического плана и блокировка настоящего MPP различаются явно.

Live stage09: POST=2, PUT=1; stage08 controls: POST=11, PUT=0. Полные следы и версии сохранены.

Проверенное дерево: `482bd999883e1b3d4bb53abe6958ef4598e4cc29541c4de21f02715eff5100c2`. Защищено файлов: 412, изменено: 0. SHA коммита записывается в журнал плана после commit.

Ограничения:

- Only stage 09. Target locking, reconciliation/idempotency after HTTP effects and verified_v1 registration remain stage 10; post-effect resume returns network_reconciliation_required instead of repeating a write.
- The live admitted plan is an explicitly synthetic parsed fixture; its exporter is not presented as a real MPP read. Independent binary MPP diff/publish tests use real MPXJ and are correctly blocked by extraction/profile limitations after verified archival.
- schedule:not_verified. Prepared-only local scheduler is unsupported; legacy model/CSV paths are excluded from the new branch. No live per-plan schedule equality is claimed.
- Historical production B/C without reference snapshot/evidence/stable keys remain inactive. Test-only identity evidence does not confirm production Trisigma.
- MPP child diff/apply share archive/admission. Recovery after child creation and legacy parent-copy/empty-child lifecycle remain stage 10; no production child-page scenario is claimed accepted.
- Two legacy optional REST tests are not enabled; mandatory stage-08 controls and stage-09 HTTP publication run independently.
- OwnCloud sync is not confirmed. Production DB/WorkVault, A–D/AB pages, configs, Gateway, crons, watchers and schedules were not changed.
