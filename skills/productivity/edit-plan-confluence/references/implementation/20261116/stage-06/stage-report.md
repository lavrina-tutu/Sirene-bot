# Этап 06 — решения batch-item и базовая история

Gate: **passed**; S rc=0; selected=361; passed=361.

Реализовано:

- `M/mofs_index/plan/schema.py`: добавлена только 0009_batch_decisions; append-only provenance/proposals/decisions и защита событий решений.
- `M/mofs_index/plan/writer.py`: typed provenance; атомарные proposals/решение+событие; идемпотентность и конфликты; scoped связь publication/snapshot.
- `M/mofs_index/plan/query.py`: общая проекция оснований, точного контекста, решений и decision_ready.
- `M/mofs_index/plan/history.py`: files/snapshots/publications; timezone-aware [since,until), defaults, unknown counts, source order, keyset cursor с границей набора.
- `S/scripts/plan_decision.py`: внутренний Proposal/адаптер; подтверждение только двух причин под общей блокировкой, без reader/архива/сети.
- `S/scripts/plan_batch.py`: проверка provenance до reader; потребление только retry-decisions, неизменный контекст; errors с решениями.
- `S/scripts/plan_operation.py`: read-only operation show с причинами, proposals, решениями, стадиями и identity_requirements=[].
- `S/scripts/plan_queries.py`: адаптер одного typed history API; import_history остаётся в plan_history.py.
- `S/scripts/cli.py`: operation show; batch-item resume регистрации; batch retry-decisions; history.
- `S/references/cli-contract.md + schemas/batch-decision-result.schema.json`: команды, отдельная схема результата регистрации, коды, времена и cursor.
- `Q/SKILL.md + Q/references/plan-queries.md`: русские запросы поступлений/сегодня через тот же typed API, разделение времён и trust.
- `S/tests/test_batch_decisions.py + test_history_queries.py`: все девять подслучаев AC-19, реальные CLI/MPP, process-death, времена/границы/cursor/Q.
- `S/tests/fixtures/synthetic/batch-decision-registration/`: версионированное неподтверждённое provenance; используется только typed writer.
- `M/tests/plan/test_batch_decisions.py + test_migrate.py`: прямой typed API, rollback, append-only, сохранность миграций 0001–0008/строк и обновлённый ожидаемый список.
- `S/tests/conftest.py`: обязательные test ID этапа 06; прежние карты/отчёты сохранены; gate из фактических результатов.

AC-19: continue/stop; обе причины; retry до регистрации; регистрация без обработки; повтор/замена основания; обычный resume; чужой/stale proposal и новые основания; busy; immutable context/новый batch; падение после регистрации и snapshot commit; обычные новые MPP без искусственного proposal. Baseline и mapping-таблицы сохранены.

История: полуинтервал [since,until), timezone-aware границы; received/recorded/source/published различаются. Source-порядок не меняет фильтр, неизвестные времена посчитаны, неизвестные даты отдельно. Cursor с ключом и границей набора проверен на равных timestamps, limit=1 и позднем backdated поступлении.

Q: тот же mofs_index.plan.history.history(HistoryRequest); отдельная проверка в external-checks.json.

Команда S:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 06 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage06/stage-06 -m unit or archive_integration --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage06/stage-06/reports/junit.xml
```

M/Q, команды/rc/JUnit/stdout/stderr и восстановление комплектов: external-checks.json. Полный CLI-проход с реальным E: batch-decisions-cli.json.

Проверено защищённых файлов: 236; изменено: 0. Дерево исходников: `f248198eb185980c69ddd2fa8b03aca3a726377dcbd9759d03c06d7657a1c15e`.

Комплекты: usertools/MofsIndex/ и usertools/workvault-rag/ — before/after/changes.patch/manifest.json. SHA завершающего коммита записывается после commit в журнал плана.

Ограничения:

- Реализован только этап 06; identity/mapping, B/C, scheduler и публикация остаются этапам 07–13
- schedule:not_verified; live Confluence не запускался, trust истории не повышается
- source_version_date — календарная шкала UTC (полночь); таймзона задач из неё не выводится
- Cursor фиксирует состав и порядок, а не полную копию изменяемого состояния обработки; новый запрос видит новые поступления
- POSIX flock локален хосту; process-death не моделирует отказ ОС/питания
- OwnCloud sync не подтверждён; production-БД/страницы/настройки/baseline, Gateway и расписания не менялись
