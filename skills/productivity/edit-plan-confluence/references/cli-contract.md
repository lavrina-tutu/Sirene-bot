# CLI-контракт (этапы 04–05)

Единственная точка входа — `scripts/cli.py`. Интерпретатор CLI — `/usr/bin/python3`;
MPXJ запускается выбранным и проверенным `MPXJ_PYTHON` из unified loader.

```text
cli.py [--db <sqlite>] [--workvault <dir>] [--cache-dir <dir>]
       [--allow-live-ab] save --mpp <file> [--project-slug <slug>]
       [--page-id <id>] [--lineage-id <id>] [--timezone-hint <IANA-zone>]
       [--source-version-date <YYYY-MM-DD>]
```

Глобальные пути стоят **до** подкоманды. Это overrides текущего запуска;
YAML не изменяется. Без overrides используются штатные пути unified config и
MofsIndex. Тесты обязаны передавать все три изолированных пути.

`--mpp` принимает локальный файл или ZIP с единственным MPP (определение по
содержимому). Источник фиксируется внутри CLI, исходный путь больше не читается.
`--project-slug` обязателен для новой локальной привязки. Совместимый `--page-id`
разрешает только локальную привязку через MofsIndex: HTTP и credentials не нужны.
`--lineage-id` выбирает существующую линию того же проекта; противоречие даёт
conflict. Имя файла не определяет lineage. `--timezone-hint` проверяется как IANA
timezone; при отсутствии остаётся unknown, таймзона другого проекта не подставляется.
`--source-version-date` — дата версии плана с основанием explicit_user; время
поступления хранится независимо. `--allow-live-ab` к локальному save не применяется.

stdout `save` содержит один короткий JSON по `schemas/single-receipt.schema.json`.
Диагностика reader идёт в stderr. Квитанция зеркалируется атомарно в
`<workvault>/_plan-receipts/<operation-id>/save.json`; контекст и результат также
хранятся через typed API MofsIndex. Полный нормализованный экспорт — в artifacts.
При отказе зеркала возвращается failed/5 с сохранённым snapshot_id, archive:verified
(если read-back прошёл) и error:receipt_mirror_failed; SQL commit сохраняется.
Нельзя считать зеркало записанным по одному наличию snapshot_id.

Коды: 0 — saved/saved_with_warnings/unchanged; 2 — аргументы; 4 — конфликт;
5 — ошибка исполнения/архива/журналирования. `save`: published=false,
page_id/page_url=null, external_effect=none; публикации и baseline не меняются.
Каждый новый вызов создаёт поступление, даже когда snapshot дедуплицирован.

Совместимые команды `preview`, `diff`, `apply --confirm`, `convert`,
`archive-history` сохраняют прежние параметры. Подключение общего publish,
history/identity/одиночного resume CLI выполняется на следующих этапах.
Глобальные пути применяются к save и batch; для остальных
команд явные overrides отклоняются, чтобы не создать ложную изоляцию.

Пример изолированного вызова (существующие каталоги, без отдельного config):

```bash
/usr/bin/python3 scripts/cli.py --db "$T/stage-04/state/index.sqlite" \
  --workvault "$T/stage-04/WorkVault" --cache-dir "$T/stage-04/cache" \
  save --mpp "$T/stage-04/fixtures/input.mpp" --project-slug trisigma \
  --source-version-date 2026-11-15
```

Внутренний `save_frozen_input(artifact, *, sha256, context, operation)` принимает
только `FrozenInput` уже зарегистрированного поступления. Все четыре аргумента
обязательны; locator/hash/размер сверяются с MofsIndex. Смена контекста возвращает
conflict/4 без перезаписи результата прежней операции. Исходный путь не открывается.
После commit восстановление выполняет read-back по item → snapshot, восстанавливает
квитанцию и не требует cache/reader/исходного пути. Самостоятельного CLI у модуля нет.

Исходник, `prepared.json`, context/settings/profiles в SQL и нормализованный JSON
остаются долговечными. Для ZIP с несколькими MPP сохраняются контейнер и список
кандидатов в `<operation-id>/input-error.json`; первый элемент не выбирается.
Краткий stdout содержит причину и ссылку на диагностический артефакт.
Неизвестные timezone/mapping, несколько корней, циклы и неполные/unsupported поля
не блокируют пригодный snapshot. Невалидный экспорт или неразбираемый MPP дают
failed/5 с поступлением и доступными байтами, без выдуманного пустого snapshot.

Счётчики успешного reader берутся из его telemetry; при неуспешном reader без
telemetry число чтений неизвестно (`null` в SQL-метриках). Счётчики и длительности
стадий — в `save_metrics`, время фиксации — в `input_metrics`. Полный экспорт и
диагностика reader не включаются в stdout. Нормализованный JSON проверяется по
SHA-256, каноническим байтам snapshot и доступности content-addressed артефакта.

Отсутствие рабочего MPXJ Python/JVM возвращает `mpxj_runtime_unavailable / 5`
после регистрации и фиксации поступления, до чтения проекта. Предупреждения
пригодного snapshot записываются typed API вместе с snapshot: SQL-статус
поступления согласован с квитанцией. Обычная служебная ID=0 сама по себе
не является предупреждением и остаётся в архивном task_count.

## Batch save/resume/show (этап 05)

```text
cli.py [--db <sqlite>] [--workvault <dir>] [--cache-dir <dir>]
  batch save (--mpp <path> [--mpp <path> ...] | --manifest <json> | --inbox <dir>)
  [--project-slug <slug>] [--lineage-id <id>] [--timezone-hint <IANA-zone>]
  [--batch-id <id>] [--on-error continue|stop]

cli.py [global paths] batch resume --batch-id <id> [--retry-failed]
cli.py [global paths] batch show --batch-id <id> [--view all|errors]
```

Три способа входа взаимоисключающие. Для `--mpp`/`--inbox` обязателен slug;
lineage/timezone необязательны. Для manifest все три общих аргумента запрещены:
контекст задаётся в элементах. Структура — `schemas/batch-manifest.schema.json`;
неизвестные поля, явный null, повтор item ID, неверная дата/IANA/SHA отклоняются
до регистрации пакета и поступлений. Дополнительные проверки IANA/календарной
даты/уникальности выполняет `validate_manifest`. Пути относительны к manifest;
expected_sha256 относится к фактическому MPP, включая извлечённый из ZIP.

Порядок `--mpp` и manifest сохраняется. Inbox сканируется один раз без рекурсии;
принимаются обычные стабильные `.mpp`, Unicode-сортировка по имени не зависит от
locale. Ссылки, скрытые/временные имена и не обычные файлы сохраняются в
`context_json.diagnostics` batch MofsIndex. Согласованность байтов проверяется
двумя чтениями и метаданными при freeze, без предположений по возрасту файла.
Исходники остаются на месте. Новые файлы не добавляются в уже созданный пакет.

Сначала атомарно регистрируются список и все поступления. Каждый вход получает
долговечные байты либо конкретную неповторяемую ошибку; только после атомарной
отметки `inputs_frozen_at` запускается последовательный общий save. `stop` не
прерывает freeze-all; он останавливает обработку на первом неуспешном элементе.
Остальные имеют not_started с уже известными ошибками фиксации, если они есть.
Общая ошибка БД/архива/журналирования останавливает любую политику.

Каноническое описание включает порядок, абсолютные пути, поля, label и эффективный
on_error (CLI → manifest → continue). Неявные lineage, timezone (включая unknown),
профили, runtime/reader versions и пути фиксируются в существующем MofsIndex.
При сравнении прежнего batch ID новые defaults не загружаются. Одинаковый запрос
возвращает только текущее состояние, без обработки и новых поступлений;
изменённый — batch_manifest_conflict/4. Для новой загрузки одинаковых байтов
нужен новый ID: поступления новые, snapshot дедуплицируется.

Resume читает только зафиксированный пакет. Глобальные явно переданные пути
должны совпадать с зафиксированными; без них, кроме пути БД для нахождения пакета,
используются сохранённые значения. Новые defaults и исходные locator не читаются.
Успешные пропускаются, потерянное зеркало восстанавливается из SQL; processing
сначала сверяется по committed-связи, без reader после commit. Только
`--retry-failed` повторяет явно retryable failed на прежних байтах. Неповторяемые
ошибки и ошибки freeze не повторяются. До общей отметки freeze resume возвращает
inputs_not_frozen/4: требуется новый пакет. Утрата/порча frozen bytes —
инфраструктурная ошибка 5; восстановление возможно только тем же SHA-256.
Изменение зафиксированного reader/runtime/профиля или явных путей —
batch_context_conflict/4, новый пакет. Блокировка flock по БД и batch ID действует
на всю фиксацию/обработку/reconciliation; занято — batch_busy/4. После смерти
процесса блокировка освобождается ядром; файл блокировки не удаляется.

stdout save/resume/show-all — квитанция `schemas/batch-receipt.schema.json`,
зеркало `<workvault>/_plan-receipts/<batch-id>/batch.json`. SQL — источник истины,
ошибка зеркала даёт infrastructure_stopped/5. Item ID квитанции локален пакету;
внутренний SQL item ID и operation ID включают идентичность пакета, поэтому
одинаковые manifest item ID допустимы в разных пакетах.

`batch show --view errors` возвращает отдельный read-only результат `action:show_batch`,
`exit_code:0`, `result` с состоянием/кодом пакета, полными counts и отфильтрованными
failed/needs_decision/not_started. Этот результат просмотра не является новой
пакетной квитанцией. `show --view all` возвращает полную текущую квитанцию и её код.
Show не запускает обработку и получает согласованное SQL-наблюдение без блокировки
работающего обработчика.

Баланс полной квитанции: total = saved + unchanged + failed + needs_decision +
not_started; saved_with_warnings входит в saved. Приоритет кодов batch:

1. 2 — аргументы/manifest до принятия запроса.
2. 4 — конфликт существующего ID/контекста, busy или незавершённый freeze.
3. 5 — общая инфраструктурная остановка, даже после частичного успеха.
4. 6 — ошибки элементов, needs_decision или оставшиеся not_started по stop.
5. 0 — все saved/saved_with_warnings/unchanged.

Локальный source_hash_mismatch/binding_conflict даёт failed элемента и итог 6,
а не общий 4. Published всегда false; baseline и публикации не меняются.
Нет сети, новых сервисов, registry.json, БД, кронов или наблюдателей.
Регистрация/потребление решений batch-item и `--retry-decisions` относятся к этапу 06
и пока не принимаются CLI. Состояние needs_decision при обычном resume сохраняется.

## Этап 06: решения batch-item и история

Все глобальные пути `--db`, `--workvault`, `--cache-dir` стоят перед подкомандой.

```text
operation show --operation-id ID
resume --operation-id ID --accept-proposal PROPOSAL [--rule-scope once] --reason TEXT
batch resume --batch-id ID [--retry-failed] [--retry-decisions]
history --project-slug SLUG [--view files|snapshots|publications]
        [--order ingested|source] [--lineage-id ID]
        [--since ISO-TIMESTAMP] [--until ISO-TIMESTAMP]
        [--time-field received|recorded|source|published] [--limit N] [--cursor CURSOR]
```

`operation show` — read-only состояние: operation/item/batch/source/snapshot,
completed_stages, preparation_revision (null до подготовки публикации),
identity_requirements (пока []), reasons, unresolved_reasons, proposals, decisions,
decision_ready и события. Старые proposals остаются в списке с active=false.
`batch show --view errors` включает failed/needs_decision/not_started, proposals,
решения и decision_ready.

Единственные причины batch needs_decision:
`archive_project_confirmation_required`, `archive_lineage_confirmation_required`.
Только явные неподтверждённые противоречащие provenance-сведения дают proposal.
Подтверждённые противоречия дают failed/binding_conflict; неподходящая lineage
также не согласуется общим согласием. Новизна MPP, неизвестные mapping/таймзона,
неполнота расписания не создают proposal. Подтверждение lineage не устанавливает
соответствие UID.

Регистрация берёт ту же flock-блокировку, проверяет frozen bytes, manifest и
контекст. В одной транзакции записываются решение с автором/источником/временем/
непустым основанием и событие decision_registered. Reader, snapshot-вставка и
сеть не запускаются, item остаётся needs_decision. Отдельный результат v1:
`action:register_batch_decision`, `status:decision_registered`, `exit_code:0`,
batch_id/item_id/operation_id/proposal_id/decision_id/manifest_sha256,
`decision_ready`, `published:false`, `error:null`. Код 0 означает регистрацию.
Повтор с тем же содержанием/основанием возвращает тот же decision_id без события.
Изменение основания — `decision_conflict / 4`; чужой/устаревший proposal —
`proposal_context_mismatch / 4`; живой обработчик — `batch_busy / 4`.

Обычный одиночный resume, --timezone-hint, --mapping-revision и --rule-scope project
для batch-item: `batch_context_immutable / 4`, next_action — новый пакет.
Сочетание взаимоисключающих форм или пустое основание — 2.
Только `batch resume --retry-decisions` проверяет актуальность и потребляет
зарегистрированные решения в исходном порядке. Без всех нужных решений item
остаётся needs_decision. Новое свидетельство создаёт новый proposal; прежние
решение/события сохраняются. Обычный batch resume решение не потребляет.
Все изменения frozen контекста требуют нового batch ID; изменённый запрос со
старым ID — `batch_manifest_conflict / 4`. Общие коды batch 2/4/5/6/0 сохраняются.

History возвращает результат запроса v1 (`action:history`, parameters, result,
quality, error), без квитанции записи. Defaults time-field: files=received,
snapshots=recorded, publications=published. Период [since, until), timestamps
обязательно с Z/offset, since < until; limit 1..1000 (default 100).
Некорректные запрос/период/cursor — 2; недоступная история — 5.
Фильтрация и порядок независимы. source_version_date — явно указанная календарная
дата на шкале UTC (00:00), без утверждения о таймзоне расписания. status_date и
имя файла её не заменяют. Неизвестное выбранное время исключено при фильтре и
посчитано в result.unknown_time_count. При order=source неизвестные даты идут
отдельно в result.unknown_source_dates, известные — в records; обе части составляют
одну страницу. unknown_source_date_count — общее число после фильтра.

Cursor — непрозрачный ключ с версией, fingerprint фильтров/порядка, границей
набора по таблицам и последним ключом (время/ordinal/точный ID). Следующая страница
требует того же запроса; limit можно менять. Поздние backdated-поступления не
включаются в начатый обход. Новый запрос видит их. При параллельном завершении
элементов текущее состояние может уточняться; cursor фиксирует состав, а не полную
копию меняющегося состояния. История читает SQLite одной read-транзакцией.

Files сохраняет повторные поступления и ошибки, snapshots выдаёт уникальные
снимки, publications — отдельные регистрации с trust и точными ID. Публикации
снимка определяются через связи, а не NULL snapshot.published_at. Время импорта
не подставляется вместо неизвестного published_at. История не повышает trust.
`plan_history.py` остаётся владельцем archive-history/import_history.

Для files `recorded_at` — время собственного события snapshot_committed данного
поступления, включая дедупликацию; `snapshot_recorded_at` — время создания
переиспользованного snapshot. Эти времена могут различаться. Публикационные
связи возвращают confidence/evidence отдельно от trust публикации.


## Identity — этап 07

Глобальные `--db`, `--workvault`, `--cache-dir` стоят перед `identity`.

```text
identity confirm --project-slug SLUG --from snapshot:FROM --to snapshot:TO
                 --mode continuity --evidence /absolute/user-statement.txt --reason "Явное утверждение пользователя"
identity confirm --project-slug SLUG --from snapshot:FROM --to snapshot:TO
                 --mode mapping --mapping /absolute/mapping.json
                 --evidence /absolute/user-statement.txt --reason "Явное соответствие"
                 [--supersedes REVISION]
identity show --project-slug SLUG --mapping-revision REVISION
```

Continuity требует явное свидетельство сохранения UID namespace; команда не
выводит это из метаданных. Evidence копируется в существующий content-addressed
архив WorkVault, записываются author/source/time/reason/policy и SHA-256.
`--mapping` обязателен только для mode=mapping; лишний mapping для continuity
отклоняется. Строгая схема: `schemas/identity-mapping.schema.json`; нет null и
неизвестных полей, допустимы task/resource/calendar/assignment, однозначность
обеих сторон. Локальные ключи берутся из version-данных точных snapshot.

Confirm возвращает schema_version:1, status:confirmed, exit_code:0,
project_slug, from_snapshot_id/to_snapshot_id, from_source_sha256/to_source_sha256,
mapping_revision_id, evidence_id/evidence_sha256, published:false, error:null.
Это регистрация подтверждения; она не выбирает revision в операции и не
запускает reader/правила/публикацию. Повтор той же регистрации возвращает тот
же ID. Show возвращает запись с scope, pairs, evidence и active/superseded/revoked.

Выбор выполняется typed `writer.select_operation_identity(IdentityChoiceSpec)`:
явная пригодная revision → единственная активная → unknown/identity_confirmation_required;
несколько активных — mapping_ambiguous/3. Неподходящая область/неактивность — 4,
недостаточный partial — identity_mapping_incomplete/3 без заполнения выбора.
После достаточности выбор атомарно фиксируется для точной пары/подготовки/правила,
повтор идемпотентен, замена — mapping_revision_conflict/4. Отзыв/supersedes
выбранного ID блокирует продолжение без автоматической подстановки другой.
`operation show.identity_requirements` содержит точные пары/hashes, rule/revision,
требуемые сущности, историю проверок и nullable выбранные revision/evidence.
Публичное исполнение publish/resume с правилами B/C добавляется этапом 09;
существующий batch-item resume сохраняет ограничения этапа 06.

### Этап 08: внутреннее представление (без нового CLI)

`convert_prepared_plan(PreparedPlan, plugin_profile=..., template_json=...,
root_task_key=...)` строит `gantt`, `summary`, `mappings`, `source_semantics`,
`diagnostics`, `publishable` и независимый `schedule:not_verified`. Только
`representation_bytes(result)` сериализует публикуемый JSON детерминированно.
CSV остаётся отдельным совместимым `convert_mpp_csv`-адаптером; prepared-путь
не вызывает CSV, JVM или reader. Публичное подключение к archive/admission
`diff/publish` выполняется этапом 09, сетевое исполнение — этапом 10.

`compute_itogo_from_prepared` использует профиль `summary-v1`, исходный summary
корень и параметры источника. Неоднозначность возвращает список кандидатов и
`summary_root_choice_required`; выбор передаётся по source-local `root_task_key`.
Неизвестные units, elapsed→working или timezone не дают storage-строки.
Work — десятичная известная сумма назначений обычных задач и вех, без ID=0,
summary и timephased-дубля; качество и missing сохраняются отдельно.
Отображение — до 3 знаков, `ROUND_HALF_UP`. В storage work отсутствует.

`calendar_from_prepared` сохраняет исходные календари/привязки и сообщает
неподдержанную семантику; ограничения локального scheduler из MppReader не
доказывают возможностей плагина. `representation_diagnostics` раздельно
показывает source / represented / model / observed. Локальный longest-path
остаётся ограниченной legacy-эвристикой, не наблюдением плагина.

Профиль выбирается существующими `SUMMARY_PROFILE` и `PLUGIN_PROFILE` в
Registries; evidence paths/hashes проверяются при загрузке профиля. Кэш
производного представления дополнительно зависит от converter/rules/plugin/
summary fingerprints, параметров шаблона и явного выбора корня. Кэш можно
удалить; он не заменяет долговечный архив или свежую проверку Confluence.

## Подготовка публикации — этап 09

`diff`, `publish` и `apply --confirm` используют `prepare_publish`: фиксация входа → prepared/cache → проект/lineage и GET цели → первичный MPP snapshot/read-back → identity/B/C → диагностика/допуск. До допуска POST/PUT запрещены. `diff` архивирует источник, возвращает одиночную JSON-квитанцию `prepared / 0` либо адресную остановку и никогда не пишет в Confluence.

```text
cli.py --db <isolated.sqlite> --workvault <vault> --cache-dir <cache> diff --mpp <file> --page-id <id> --project-slug <slug> --timezone-hint Europe/Moscow
cli.py publish --mpp <file> --page-id <id> --project-slug <slug> --timezone-hint Europe/Moscow
cli.py apply --mpp <file> --page-id <id> --project-slug <slug> --confirm да
cli.py operation show --operation-id <id>
cli.py resume --operation-id <id> --mapping-revision <revision>
cli.py resume --operation-id <id> --timezone-hint Europe/Moscow
cli.py resume --operation-id <id> --accept-proposal <proposal> --reason <text> [--rule-scope once|project]
```

Для новой страницы без архивного binding `--project-slug` обязателен: `project_slug_required / 2`, пригодный operation ID отсутствует; факт поступления и frozen bytes сохраняются. Slug из заголовка файла не выводится. Конфликт явного slug с binding — `binding_conflict / 4`. Для существующей однозначной привязки slug можно опустить.

После архива остановка содержит `snapshot_id`, `verification.archive:verified`, `published:false`, `external_effect:none`. Proposals/mapping/timezone взаимоисключающие. Подтверждение identity не запускает публикацию. Resume использует сохранённый контекст и источник без нового поступления/разбора. Смена неизвестной таймзоны до внешнего эффекта создаёт новую подготовку и snapshot, сохраняя прежние; mapping/решения не переносятся на новую пару. Разрешённую таймзону меняют новой операцией.

`--drop-dep FROM:TO` — конкретное предложение, привязанное к хэшу источника и устойчивым source-local ключам, а не автоматическое исключение. Принимается точный proposal с текстом основания; scope по умолчанию `once`. Явный scope `project` сохраняет версионированное правило с исходным snapshot и immutable consent evidence; для другого источника требуется точная достаточная mapping revision и повторная проверка причины/контекста. Неподтверждённые исторические B/C остаются неактивными; исправленная конвертация может дать `not_needed`.

Матрица §20.3.6.2 исполняется `plan_policy.py`: неизвестные поля считаются влияющими на представление, если версионный профиль не доказывает обратное. Для всех задач и вех допуск дат — 60 секунд; при неизвестной таймзоне абсолютное сравнение не утверждается. Локальный scheduler, повторно открывающий MPP, исключён из prepared-ветки. Допущенный план без наблюдения результата установленного плагина имеет `schedule:not_verified`.

До `admitted` в MofsIndex/архиве сохранены представление, решение, профили, правила, диагностика и контекст. Сетевая ветка этапа 09 использует эти bytes и точную версию скачивания, текущие metadata без старого `status=any` (HTTP 400). Проверки байтов/storage не ослабляются согласованием. Полное восстановление после сетевого эффекта, идемпотентность и регистрация `verified_v1` остаются этапу 10: пока такой resume возвращает `network_reconciliation_required / 5` и не повторяет запись.

MPP-ветка `diff/apply --child` также проходит первичный архив и допуск. Флаг дочерней страницы и заголовок сохраняются в контексте; `resume` после identity/timezone продолжает создание дочки, а не заменяет родительский план. До допуска POST создания страницы запрещён. Варианты копии родителя/пустой дочки без MPP и полное восстановление сетевого создания сохраняют отдельную границу этапа 10.

Квитанция содержит сгруппированную сводку проверок с количеством и примерами затронутых сущностей. Полные исходные/представленные значения и проверки всех дат остаются в immutable admission evidence; `verification.schedule.evidence_ids` и `warnings[].details_ref` указывают на этот артефакт. Полный нормализованный экспорт в штатный stdout не попадает.
