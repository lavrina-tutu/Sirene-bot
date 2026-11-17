# Batch и Inbox

Основной вход: отдельная `WorkVault/Inbox/<пакет>/` и одно текстовое сообщение
«Сохрани все MPP из этой папки в архив проекта …». Отклонённое транспортом
Gateway сообщение скиллу недоступно. Скилл не чинит Gateway и не обещает
приём нескольких вложений в одном Telegram сообщении.

```cli-example
cli.py batch save --inbox /inputs/Inbox/plans-20261117 --project-slug trisigma --batch-id inbox-20261117 --on-error continue
cli.py batch save --mpp /inputs/E.mpp --mpp /inputs/F.mpp --project-slug trisigma --batch-id pair-001
cli.py batch save --manifest /inputs/batch.json --batch-id manifest-001
cli.py batch show --batch-id inbox-20261117 --view errors
```

Три способа взаимоисключающие. Inbox: только завершённые обычные `.mpp`
непосредственно в папке, без рекурсии, Unicode-сортировка; ссылки, временные
файлы и исключённые записи попадают в диагностику. Исходники не удаляются и
не перемещаются. Для ZIP с несколькими MPP — `multiple_mpp_candidates`, первый
не выбирается; подготовить отдельный вход/новый пакет с нужными байтами.

До первого reader каждый вход получает frozen bytes/hash/locator либо ошибку.
`inputs_frozen_at` фиксирует общую границу; без неё `resume` даёт
`inputs_not_frozen / 4`, нужен новый batch. Затем по одному item в исходном
порядке. Новые файлы Inbox после freeze не входят в пакет. Resume не читает
исходные paths, а проверяет неизменяемые frozen bytes и контекст.

## Manifest v1

```json
{"schema_version":1,"label":"Два архивных плана","on_error":"continue","items":[{"item_id":"e","path":"E.mpp","project_slug":"trisigma","source_version_date":"2026-07-09"},{"item_id":"f","path":"F.mpp","project_slug":"trisigma","timezone_hint":"Europe/Moscow"}]}
```

Схема `schemas/batch-manifest.schema.json`: уникальные item_id; обязательные
path/project_slug у каждого item; optional lineage_id/source_version_date/
expected_sha256/timezone_hint. Неизвестные поля и явный null запрещены.
Относительные paths — от manifest. Ожидаемый hash не заменяет freeze-all.
Общие project/lineage/timezone вместе с manifest не принимаются.

Канонический manifest учитывает порядок, абсолютные пути, label, поля и
эффективный on_error. Тот же ID с тем же запросом возвращает текущее состояние,
не запускает обработку; изменённый запрос — `batch_manifest_conflict / 4`.
Профиль, timezone (даже unknown→IANA), проект/lineage, дата, байты, порядок и
on_error неизменяемы; изменения требуют нового пакета и ID.

## Продолжение и решения

```cli-example
cli.py batch resume --batch-id inbox-20261117
cli.py batch resume --batch-id inbox-20261117 --retry-failed
cli.py operation show --operation-id item-operation
cli.py resume --operation-id item-operation --accept-proposal archive-proposal --rule-scope once --reason "Подтверждаю выбранное архивное размещение"
cli.py batch resume --batch-id inbox-20261117 --retry-decisions
cli.py batch show --batch-id inbox-20261117 --view all
```

Одинаковые глобальные пути перед командой во всех вызовах.

| Item | Действие |
|---|---|
| saved/saved_with_warnings/unchanged | Пропустить, при необходимости восстановить зеркало |
| not_started после freeze | Обработать автоматически |
| processing/неизвестный SQL | Сначала найти committed snapshot/event и read-back, без повторного reader |
| failed, retryable=true | Только `--retry-failed` после восстановления причины |
| failed, retryable=false / freeze failed | Новый пакет с исправленным входом |
| needs_decision | Обычный resume оставляет; исполнение только `--retry-decisions` |

Две допустимые причины решения: archive_project_confirmation_required и
archive_lineage_confirmation_required. Proposal привязан к item/operation/batch,
manifest/source/context hashes, размещению и противоречащим свидетельствам.
Новизна файла, неизвестный mapping/timezone не создают proposal сами по себе.
Доказанный конфликт не согласуется общим «да».

`resume --accept-proposal` под общей блокировкой лишь регистрирует решение,
не запускает reader, архив или сеть. Action `register_batch_decision`, rc=0
означает сохранение решения; item остаётся needs_decision, decision_ready
появляется после всех нужных решений. Повтор того же принятия даёт тот же ID;
замена основания — decision_conflict/4. Scope только once, контекст не меняется.
`batch resume --retry-decisions` отдельно проверяет актуальность и потребляет
решение. Новые противоречия дают новое предложение; история остаётся.

Continue идёт дальше после item error, stop оставляет хвост not_started;
инфраструктура останавливает независимо от политики. Утрата frozen artifact
требует восстановления тех же байтов из backup, не чтения изменившегося Inbox.
Успешная дедупликация даёт новое поступление, прежний snapshot и unchanged.
Квитанция содержит баланс всех item; приоритет rc описан в cli-contract.md.
Baseline и публикации не меняются, ConfluenceClient отсутствует.
