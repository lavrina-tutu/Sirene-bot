---
name: confluence-minutki-creation
description: "Use when: создание страницы-минуток проекта в Confluence."
version: 1.0.1
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, Confluence, минутки, протокол, entities, OFC, pfs]
    related_skills: [tutu-confluence-jira, about_usr_skills]
---

# Confluence: создание страницы-минуток проекта + привязка к сущности

Повторяемый кейс (зафиксирован Сашей 26.08.2026): для проекта, у которого ещё нет страницы протоколов, создать дочернюю страницу-минутки под главной страницей проекта и записать её `page_id` в `entities.json` как `pfs.page_id`, чтобы OFC начал синхронизировать протокол в `Entities/<slug>/protocol.md`.

## Триггеры
- «создай протоколы и возьми ИД»
- «создай минутки», «создай подстраницу с протоколами»
- Саша даёт главную страницу проекта в Confluence и просит сделать минутки

## Жёсткие правила (коррекции Саши)
1. **Работать строго поштучно** — одна сущность за раз, не валить все в кучу. После каждой — отчёт и ожидание следующей команды.
2. **Slug в названии страницы — ВСЕГДА с заглавной буквы** (Devrel, ЦУ, Атрибуция, Вестник), даже если slug в `entities.json` строчный (`devrel`, `cu`, `atribuciya`). Саша может дать slug явно (например «ЦУ» для `cu`) — использовать ровно как дал.
3. Название страницы: `«<Slug>. Задачи и договоренности (Минутки)»`.

## Шаги
1. **Проверить главную страницу** (space + title):
   ```bash
   load_confluence_env  # из tutu-confluence-jira
   curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
     "https://dom.tutu.ru/rest/api/content/<rootPageId>?expand=version,space"
   ```
2. **Взять тело стандартного шаблона минуток** — эталонная страница `508804894` («Саша Ж. 1-1. Задачи и договоренности (Минутки)»). GET её `body.storage.value` — это таблица «Дата постановки | Задачи и Договоренности» + подпись «Последние задачи сверху списка» + служебная строка «вверх».
3. **POST дочерней страницы** под `rootPageId` в том же space, title = `«<Slug>. Задачи и договоренности (Минутки)»`, body = тело шаблона:
   ```json
   {"type":"page","title":"<Slug>. Задачи и договоренности (Минутки)",
    "ancestors":[{"id":"<rootPageId>"}],"space":{"key":"<SPACE>"},
    "body":{"storage":{"value":"<тело шаблона>","representation":"storage"}}}
   ```
   Ответ содержит `id` новой страницы.
4. **Записать `pfs.page_id`** в `~/WorkVault/Registries/entities.json` для этого slug (создать блок `pfs` если нет). OFC подхватит и начнёт синхронизировать.
   **OFC direction:** Confluence → `~/WorkVault/Entities/<slug>/protocol.md`, driven by cron `ofc_sync.sh`. Opposite of PFS (PFS = summary → Confluence). Keep OFC logic HERE (minutki/protocol/OFC context), NOT in `protocolfromsummary`, to avoid trigger mixing.
5. **Отдать Саше кликабельный URL** `https://dom.tutu.ru/pages/viewpage.action?pageId=<id>` + название страницы (не голый pageId).

## Варианты
- **Страница протоколов уже существует** — Саша даёт её URL напрямую. Тогда НЕ создавать новую, только записать `pfs.page_id` = этот id в `entities.json`.

## Питфоллы
- Не переименовывать slug в названии страницы — использовать с заглавной, как дал Саша (не транслитерировать/не приводить к строчному).
- `space` не возвращается в GET по умолчанию — добавить `expand=version,space` или читать из ответа POST.
- После создания страницы не забыть записать `pfs.page_id` — иначе OFC не увидит сущность (фильтр `kind=project` + непустой `pfs.page_id`).
- В списке сущностей могут быть дубли-кандидаты (например `alfa`/`alpha`) — разбирать поштучно, не решать за Сашу.

## Связанные скиллы
- `tutu-confluence-jira` — авторизация Confluence, формат минуток, резолв userkey, JIRA-макросы
- `about_usr_skills` → `references/confluence-minutki-protocol-format.md` — канонический формат протокола
