# CLI-контракт (этап 04)

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
batch/history/identity/resume CLI выполняется на следующих этапах; этап 04
их не добавляет. Глобальные пути этапа 04 применяются к save; для остальных
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
