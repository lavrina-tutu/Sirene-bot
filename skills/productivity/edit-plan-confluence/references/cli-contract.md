# Публичный CLI, §20

Единственный entrypoint:
`/usr/bin/python3 /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/scripts/cli.py`.
В примерах `cli.py` означает этот entrypoint. Пути входов абсолютные, кроме
manifest, где относительные paths разрешаются от его каталога.

## Глобальные флаги

`cli.py [--db SQLITE] [--workvault DIR] [--cache-dir DIR] [--allow-live-ab] COMMAND`.
Все глобальные флаги располагаются **до подкоманды**. Overrides не переписывают YAML.
Пути действуют для save/batch/operation/resume/history/identity/publish/diff/apply/compare/publication.
`preview`, `convert`, `archive-history` — совместимые адаптеры, path overrides
не поддерживают; при их передаче CLI возвращает 2. Для приёмки archive-history
нужны изолирующие dependencies/fixtures. AB `519492935` требует явной цели и
`--allow-live-ab` заново при resume. `--help` доступен на каждом уровне.

## Все команды и параметры

Квадратные скобки означают необязательность; вертикальная черта — выбор.

| Команда | Параметры |
|---|---|
| `publish` | `--mpp FILE --page-id ID [--project-slug SLUG] [--timezone-hint IANA] [--drop-dep FROM:TO]` |
| `save` | `--mpp FILE [--project-slug SLUG] [--page-id ID] [--lineage-id ID] [--timezone-hint IANA] [--source-version-date YYYY-MM-DD]` |
| `diff` | `--page-id ID [--mpp FILE] [--project-slug SLUG] [--timezone-hint IANA] [--child] [--title TEXT] [--drop-dep FROM:TO]` |
| `apply` | параметры diff и обязательный `--confirm лей\|пиши\|да` |
| `preview` | `[--page-id ID]`; CLI default — старая тестовая 519501810, агент всегда указывает цель |
| `convert` | `--mpp FILE [--out JSON] [--out-dir DIR]`; default output `/tmp/gantt_out.json` |
| `archive-history` | `--page-id ID --attachment-id ID --from-version N --to-version N [--project-slug SLUG]`; диапазон включительный, legacy default slug=zd, передавать явно |
| `batch save` | `(--mpp FILE [--mpp FILE] \| --manifest JSON \| --inbox DIR) [--project-slug SLUG] [--lineage-id ID] [--timezone-hint IANA] [--batch-id ID] [--on-error continue\|stop]` |
| `batch resume` | `--batch-id ID [--retry-failed] [--retry-decisions]` |
| `batch show` | `--batch-id ID [--view all\|errors]` (all) |
| `operation show` | `--operation-id ID` |
| `resume` | `--operation-id ID [--accept-proposal ID \| --timezone-hint IANA \| --mapping-revision ID] [--reason TEXT] [--rule-scope once\|project]` |
| `history` | `--project-slug SLUG [--view files\|snapshots\|publications] [--order ingested\|source] [--lineage-id ID] [--since TIMESTAMP] [--until TIMESTAMP] [--time-field received\|recorded\|source\|published] [--limit N] [--cursor TEXT]` |
| `compare` | `--project-slug SLUG --from snapshot:ID\|publication:ID --to snapshot:ID\|publication:ID [--mapping-revision ID]` |
| `identity confirm` | `--project-slug SLUG --from snapshot:ID --to snapshot:ID --mode continuity\|mapping --evidence FILE --reason TEXT [--mapping JSON] [--supersedes ID]` |
| `identity show` | `--project-slug SLUG --mapping-revision ID` |
| `publication verify` | `--project-slug SLUG --publication-id ID [--scope current_state\|historical_version]` (current_state) |

`--drop-dep` повторяемый, это предложение, не немедленное удаление.
Для новой привязки publish/diff/apply нужен slug, для локального save — slug
или существующий page binding. Обычный `publish` разрешён явной командой
пользователя; отдельного общего подтверждения нет. `diff` сохраняет источник
локально, GET-only для Confluence. `diff/apply --child` с MPP использует общий
допуск; без MPP остаётся legacy копирование/пустая дочка с `legacy_unverified`.
`publish` не имеет `--child`, lineage или source-version-date.

В batch manifest контекст задаётся отдельно каждому item; общие project/lineage/
timezone вместе с manifest запрещены. Для mpp/Inbox project обязателен.
Reason и scope относятся только к accept-proposal; reason непустой.
Для batch-item допустим только scope once. Unknown timezone можно уточнить
одиночным resume до внешнего эффекта; для batch требуется новый пакет.

## Примеры для parser smoke-tests

Ниже точные синтаксические примеры с вымышленными ID и путями. Блоки `cli-example`
проверяет `tests/test_skill_contract.py`; parser не выполняет сетевые команды.
Суффикс `cli.py` подставляется после указанного entrypoint.

```cli-example
cli.py --db /isolated/state/index.sqlite --workvault /isolated/WorkVault --cache-dir /isolated/cache publish --mpp /inputs/plan.mpp --page-id test-page --project-slug trisigma
cli.py --db /isolated/state/index.sqlite --workvault /isolated/WorkVault --cache-dir /isolated/cache save --mpp /inputs/plan.mpp --project-slug trisigma --page-id test-page --source-version-date 2026-11-17
cli.py diff --mpp /inputs/plan.mpp --page-id test-page --project-slug trisigma --timezone-hint Europe/Moscow
cli.py apply --mpp /inputs/plan.mpp --page-id test-page --project-slug trisigma --confirm лей --child --title "Тестовый план"
cli.py preview --page-id test-page
cli.py convert --mpp /inputs/plan.mpp --out /outputs/gantt.json --out-dir /outputs/csv
cli.py archive-history --page-id test-page --attachment-id test-attachment --from-version 1 --to-version 2 --project-slug trisigma
cli.py batch save --mpp /inputs/E.mpp --mpp /inputs/F.mpp --project-slug trisigma --batch-id inbox-001 --on-error continue
cli.py batch save --manifest /inputs/batch.json --batch-id manifest-001
cli.py batch save --inbox /inputs/Inbox/review --project-slug trisigma --batch-id review-001
cli.py batch show --batch-id review-001 --view errors
cli.py operation show --operation-id test-operation
cli.py resume --operation-id test-operation --accept-proposal test-proposal --rule-scope once --reason "Подтверждаю выбранное архивное размещение"
cli.py batch resume --batch-id review-001 --retry-decisions --retry-failed
cli.py identity confirm --project-slug trisigma --from snapshot:test-from --to snapshot:test-to --mode continuity --evidence /inputs/user-statement.txt --reason "Пользователь подтвердил сохранение UID namespace"
cli.py identity confirm --project-slug trisigma --from snapshot:test-from --to snapshot:test-to --mode mapping --mapping /inputs/mapping.json --evidence /inputs/user-statement.txt --reason "Явное соответствие" --supersedes test-old-revision
cli.py identity show --project-slug trisigma --mapping-revision test-revision
cli.py resume --operation-id test-operation --mapping-revision test-revision
cli.py resume --operation-id test-operation --timezone-hint Europe/Moscow
cli.py --allow-live-ab resume --operation-id test-ab-operation
cli.py history --project-slug trisigma --view files --time-field received --since 2026-11-17T00:00:00+03:00 --until 2026-11-18T00:00:00+03:00 --limit 100
cli.py history --project-slug trisigma --view publications --order source --lineage-id test-lineage --cursor opaque-cursor
cli.py compare --project-slug trisigma --from snapshot:test-from --to snapshot:test-to --mapping-revision test-revision
cli.py compare --project-slug trisigma --from publication:test-pub-a --to publication:test-pub-b
cli.py publication verify --project-slug trisigma --publication-id test-pub-a --scope current_state
cli.py publication verify --project-slug trisigma --publication-id test-pub-a --scope historical_version
```

## Результаты, схемы и коды

Save/publish/diff и одиночный resume дают одиночную JSON-квитанцию
[`single-receipt.schema.json`](schemas/single-receipt.schema.json).
Batch — [`batch-receipt.schema.json`](schemas/batch-receipt.schema.json),
вход — [`batch-manifest.schema.json`](schemas/batch-manifest.schema.json).
Регистрация batch-решения — отдельный action-result
[`batch-decision-result.schema.json`](schemas/batch-decision-result.schema.json).
Mapping — [`identity-mapping.schema.json`](schemas/identity-mapping.schema.json);
prepared export — [`prepared-plan.schema.json`](schemas/prepared-plan.schema.json).
Settings и plugin profile — `schemas/settings.schema.json` и
`profiles/plugin-profile.schema.json`. History/compare/verify/identity/show
возвращают action-specific JSON, без отдельной выдуманной receipt schema.

| Код | Значение |
|---|---|
| 0 | saved/saved_with_warnings/prepared/unchanged, успешный query/verify либо только регистрация решения |
| 2 | Ошибка аргументов или manifest |
| 3 | Адресное решение одиночной операции, неоднозначная mapping revision |
| 4 | Конфликт binding/цели/hash/проекта/mapping/batch-контекста |
| 5 | Сбой исполнения/инфраструктуры или неподтверждённый результат |
| 6 | Batch с failed/needs_decision/not_started после stop |

Приоритет batch: 2 до принятия → 4 конфликт ID/контекста → 5 инфраструктура →
6 неуспешные элементы → 0 все успешны. Error элемента не превращает batch в 3/4.
`batch show` показывает сохранённый итог; наличие JSON не означает rc=0.
История defaults: view files, order ingested, limit 100; максимальный limit 1000.
Фильтр `[since,until)` требует timezone-aware timestamps; order source фильтр не меняет.

Новый штатный stdout — один краткий JSON без полного экспорта/traceback/credentials.
Прогресс и reader diagnostics — stderr/артефакты. Совместимые preview/diff-child
без MPP/convert имеют текстовый stdout, archive-history и legacy child — свой JSON.
`published:false` до эффекта, `null` при неопределённом эффекте, `true` после
полной проверки. Архив/страница/расписание и trust независимы.
