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
