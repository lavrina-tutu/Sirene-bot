# Этап 07 — подтверждение идентичности и mapping revision

Gate: **passed**. S rc=0; selected=379; passed=379.

- `M/mofs_index/plan/identity.py`: единая политика точной пары, scope, continuity/mapping, same_source, выбор и проверки evidence.
- `M/mofs_index/plan/schema.py`: только новая 0010_identity_revisions; scope/evidence/supersedes/отзыв, calendar/assignment, append-only требования/выбор/проверки.
- `M/mofs_index/plan/writer.py`: typed подтверждение/отзыв/требования; атомарный достаточный выбор; идемпотентность, конфликт и отсутствие автоподмены.
- `M/mofs_index/plan/query.py`: diff/task_history/causal guard используют доказательства; unknown и несопоставленные остатки вместо ложного confirmed_uid.
- `S/scripts/plan_identity.py`: внутренние confirm/show адаптеры; immutable content-addressed evidence, без reader/автозапуска/публикации.
- `S/scripts/plan_operation.py`: identity_requirements с точными парами/hashes/rule/revision/evidence/checks и внутренний typed выбор.
- `S/scripts/cli.py`: identity confirm/show, selectors, форма mapping/continuity, глобальные пути и JSON ошибок.
- `S/references/schemas/identity-mapping.schema.json`: строгая схема v1; четыре типа, null/unknown/пустые ключи запрещены.
- `S/references/cli-contract.md + Q/references/plan-queries.md`: контракт identity/revision; убраны обещания подтверждения UID без evidence; исполняемый Q пример.
- `M/tests/plan/test_identity.py + test_query.py + test_migrate.py`: прямые контракты, миграция с legacy данными, checksums 0001–0009, атомарность и два процесса; новые ожидаемые результаты query/migrations.
- `S/tests/test_plan_identity.py + fixtures/synthetic/identity-confirmation`: CLI, строгая схема, immutable evidence, partial→sufficient, operation show, Q и отсутствие автозапуска.
- `S/tests/conftest.py`: добавлены карта обязательных test ID и отчёт/gate этапа 07; прежние карты/отчёты сохранены.

Выбор: явная пригодная → единственная активная → unknown; несколько → mapping_ambiguous/3. Partial без требуемых сущностей не занимает слот. Выбор фиксируется атомарно; повтор идемпотентен, замена mapping_revision_conflict/4. Отзыв/supersedes блокирует сохранённый выбор. История сохраняется.

Ложное confirmed_uid в diff/task_history и причинном query убрано; подтверждение возможно только через выбранную revision/evidence. Same-source ограничен источником и профилем. Автоматической транзитивности нет.

Команда S:

```text
/usr/bin/python3.9 -m pytest -c /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests/pytest.ini /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/tests --acceptance-stage 07 --test-root /home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage07/stage-07 -m unit or archive_integration --junitxml=/home/tkachenkoav/.cache/edit-plan-confluence-acceptance/20261116-stage07/stage-07/reports/junit.xml
```

M/Q, команды/rc/JUnit/stdout/stderr, восстановление patch/after-copy и protected hashes: external-checks.json. Реальные CLI argv/results: identity-cli.json.

Дерево: `a8c3113ea7b0228474946939569fed788bc5394a04a5d216dc7d5e7205d4f092`. Защищено файлов: 271; изменено: 0. Комплекты usertools/MofsIndex/ и usertools/workvault-rag/ включаются в завершающий commit; SHA после commit записывается в журнал плана.

Ограничения:

- Только этап 07. Правила B/C и публичный publish/resume с ними — этап 09; stage-07 select hook не исполняет правила или сетевые стадии.
- Полные semantic diff связей/календарей/назначений и точные publication selectors — этап 11. Snapshot diff честно completeness:partial/calendar:unknown.
- Task history требует прямое доказательство каждой пары; без опорного snapshot совпавшие UID показываются раздельно; абсолютная дельта при неизвестной таймзоне не заявляется.
- Evidence хранится в существующем artifact-контуре; append-only SQL и SHA-256 проверяются при использовании. Изменение/утрата байтов блокирует применение.
- Schedule:not_verified. Live Confluence не запускался; полномасштабная приёмка §20 не заявлена.
- OwnCloud sync не подтверждён. Production-БД/страницы/настройки/baseline, Gateway и расписания не менялись.
