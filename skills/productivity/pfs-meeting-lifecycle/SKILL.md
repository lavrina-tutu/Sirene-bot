---
name: pfs-meeting-lifecycle
description: "Use when отменить/исключить встречу из PFS/Confluence."
version: 1.0.0
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pfs, confluence, meetings, pipeline, exclude, cancel, registry]
    related_skills: [protocolfromsummary, meeting-ingest-pipeline]
---

# Жизненный цикл записи встречи PFS после публикации (отмена / исключение / возврат)

Операции над встречей, уже попавшей в контур ProtocolFromSummary, когда её нужно
убрать или остановить от повторной публикации. Обе операции строятся вокруг одного
факта: **`run-pending` публикует только файлы `* summary.md`, у которых в PFS-реестре
`_registry.json` нет записи по `meeting_id`** (и дата >= CUTOVER_DATE). Запись в реестре = признак
«обработано/исключено» — это единственный штатный выключатель повторной публикации.

Детали контура (публикация, маршрутизация, реестр) — в `protocolfromsummary` и
`meeting-ingest-pipeline`; здесь — процедура удаления и исключения.

## Исключить встречу из публикации, оставив файл в архиве («не грузить в Confluence»)

Когда файл должен остаться в `WorkVault/Meetings/NewMeetings/` (для истории/Obsidian), но
публиковаться в Confluence больше не должен:

1. Добавить в `_registry.json` (`WorkVault/ProtocolFromSummary/_registry.json`) запись по
   `meeting_id` с маркером исключения:
   `entity: "excluded"`, `last_action: "excluded"`, `historical_no_reload: true` (notify
   пропускает такие безусловно — уведомление не уйдёт), плюс человекочитаемые
   `excluded: true` и `excluded_reason: "<почему>"`.
2. `Registry.get` фильтрует только известные dataclass-поля — лишние ключи (`excluded`,
   `excluded_reason`) безопасны (теряются при чтении, но остаются в JSON как признак).
3. Проверка: `run-pending --dry-run` — встречи нет в pending (`published: 0`); ручной
   `run <file>` вернёт `skipped_duplicate`.

Штатного CLI для пометки исключения нет — запись пишется вручную (тот же контур, что пломба
`historical_no_reload` у исторического архива встреч < CUTOVER_DATE). Реестр править только с
бэкапом (`cp _registry.json _registry.json.bak-<дата>-<причина>`) и атомарно.

## Полная отмена опубликованной встречи

1. Убрать строку со страницы-цели (минутки, route.page_id) И с площадки `523032632` — один
   `row_anchor` у обеих. Вырезать `<tr>...</tr>` по anchor: `rfind('<tr>', 0, anchor_pos)` +
   счётчик глубины до matching `</tr>`, PUT `version+1` c body без строки. Верифицировать GET-ом
   (anchor отсутствует) — не доверять PUT.
2. Удалить запись из `_registry.json` (бэкап перед правкой; это `_registry.json`, НЕ
   `_registry_meet.json` — последний реестр источника MoveFromFF/KTalk).
3. Удалить sidecar прохода 1 из `GOLD_PROTOCOLS_DIR` (`~/WorkVault/Meetings/GoldProtocols/`):
   `{meeting_id}-first-pass.md` и `{meeting_id}-first-pass.td1.html`.
4. ⚠️ **Файл summary, оставшийся в NewMeetings без записи в реестре, на следующем тике
   `run-pending` опубликует заново** — «удалил со страницы» не равно «удалил из контура».
   Либо убрать файл из NewMeetings, либо поставить excluded-маркер (раздел выше).

## Версии страницы в истории Confluence не удаляются

Через REST API нет эндпоинта на удаление отдельной версии страницы — откат контента выполняется
новой версией (version+1), старая версия остаётся в истории страницы. Не обещать «чистку истории»;
честно говорить: контент убран, но версии страницы с удалённой строкой остаются, почистить их
можно только вручную через админку Confluence.

## Pitfalls

- **Не «чинить» нежелательный резолв имён при ручной имитации ingest** — однословные имена
  без ФИО ложно матчатся на комнаты по substring (напр. «Оля» ⊂ «Изолятор» → в задаче
  «(переговорка Оля)» и исполнитель DEFAULT_ASSIGNEE_LOGIN); относительные дедлайны
  «через N дней» не парсятся → fallback +7. Это состояние контура, а не баг файла.
- **Запись в MOFS-реестре** (`_mark_objects_registry.json`) при удалении/исключении встречи
  можно не трогать: после удаления файла MOFS больше не обработает, а маркер в PFS-реестре
  останавливает именно публикацию.
- **`CONFLUENCE_TOKEN`/`CONFLUENCE_URL`** для прямой REST-верификации — из
  `protocolfromsummary.config` (`CONFLUENCE_BASE_URL`, `CONFLUENCE_TOKEN`); модуля-клиента
  `confluence` в пакете нет (`import confluence` падает) — GET через urllib/requests.
