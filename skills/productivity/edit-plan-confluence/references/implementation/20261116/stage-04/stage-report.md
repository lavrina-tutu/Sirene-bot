# Этап 04 — общий однопроходный save

Gate: **passed**; rc=0; selected=267; passed=267.

Реализовано:

- `S/scripts/plan_save.py`: единый freeze → parse/cache → quality → typed archive/dedup → read-back → receipt; save_frozen_input с обязательными artifact/hash/context/operation; краткий SaveResult; восстановление без reader.
- `S/scripts/cli.py`: lazy client/pipeline imports; локальный save --page-id; глобальные пути, lineage и дата версии; JSON результата и ошибок; rc 0/2/4/5.
- `S/scripts/plan_context.py`: изолированные db/WorkVault/cache передаются явно; восстановление settings/sources/profile hashes без loader.
- `S/scripts/plan_receipt.py`: полный nullable контракт v1; атомарная замена/fsync/read-back; маскирование; безопасные имена зеркал.
- `S/scripts/plan_operation.py`: save_result в SQL до файлового зеркала; ошибка зеркала сохраняет snapshot и SQL-историю.
- `S/scripts/plan_reconcile.py`: чтение полной последней квитанции из SQL; committed read-back без повторного разбора.
- `S/references/schemas/single-receipt.schema.json`: полная схема §20.3.12.1 и save-инварианты.
- `S/references/cli-contract.md`: все добавленные параметры, размещение overrides, exit codes, обязательные пути и сохранённая совместимость.
- `S/tests/test_plan_save.py + test_plan_receipt.py + test_cli.py + test_env.py`: контракты, populated baseline, предупреждения, ошибки, recovery commit/mirror, JSON и изоляция.
- `S/tests/test_save_e2e.py`: CLI /usr/bin/python3 и реальный MPXJ /usr/bin/python3.9; E/F cold/warm, corruption rebuild, unreadable MPP, ZIP; импорт клиента и сеть запрещены.
- `S/tests/conftest.py`: обязательные test ID этапа 04 и отчёт из фактических результатов; проверка неизменности внешних компонентов и evidence 01–03.

Цепочка: freeze → parse/cache → quality → typed archive/dedup → read-back → receipt. Каждый повтор регистрирует новое поступление, snapshot дедуплицируется. После commit reader не вызывается.

Квитанция v1 содержит все обязательные поля §20.3.12.1. Save: published=false, page_id/page_url=null, external_effect=none. Baseline проверен точным сравнением заполненных таблиц. При отказе зеркала failed/5 сохраняет snapshot_id и подтверждённый archive read-back; SQL-результат не теряется.

CLI: глобальные --db/--workvault/--cache-dir до подкоманды; save --mpp, --project-slug, --lineage-id, --timezone-hint, --source-version-date; совместимый --page-id только локальный. Полный контракт: references/cli-contract.md.

Команда проверки:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 04 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage04-145347/stage-04 -m unit or archive_integration or mpp_fixtures --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage04-145347/stage-04/reports/junit.xml
```

Реальные E/F:

- E: tasks/dependencies=78/84; cold MPXJ=1; warm MPXJ=0, cache_hit=1; rc=0/0. Evidence: save-e2e-E.json.
- F: tasks/dependencies=86/93; cold MPXJ=1; warm MPXJ=0, cache_hit=1; rc=0/0. Evidence: save-e2e-F.json.

Проверено защищённых файлов: 193; изменений: 0. M/R/E, миграции и evidence 01–03 без изменений. Внешнего комплекта нет. Незакоммиченные заготовки, найденные при входе, сохранены в T/preexisting и включены после проверки в реализацию этапа 04.

Дерево исходников: `cdba8fdb8dec5bceb3811e409104c63a6edefd0a6d3083d6fb9e1802130aee43`. Версия master 0.5.0; hashes, версии, test ID/длительности и счётчики — в JSON. JUnit: junit.xml. SHA коммита записывается после commit в журнал канонического плана.

Ограничения:

- Только этап 04; batch, identity, publish/resume CLI и активная регистрация остаются последующим этапам
- schedule:not_verified; live Confluence и проверка установленного плагина не выполнялись
- Общее число MPXJ-read старых CSV/calendar-путей не измерено; failed reader без экспортной telemetry имеет счётчик null
- Production-БД/страницы/настройки/baseline не изменялись; новые миграции отсутствуют
- MofsIndex/MppReader только читались; внешний комплект изменений не требуется
- ownCloud sync не подтверждён; Gateway/кроны/наблюдатели/расписания не изменялись
