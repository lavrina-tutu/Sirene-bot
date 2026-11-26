---
name: confluence-comments
description: "Use when комментарии Confluence: footer/inline, перенос."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, Confluence, комментарии, inline, footer]
    related_skills: [tutu-confluence-jira, confluence-page-editing]
---

# Комментарии Confluence Server/DC: footer vs inline

## When to Use

- Задача «перенеси комментарии/статусы с одной страницы на другую» в Confluence.
- Нужно создать комментарий, привязанный к выделенному тексту (inline), или внизу страницы (footer).
- Нужно удалить/почистить комментарии (в т.ч. тестовый мусор).

Класс задач: создать/перенести/удалить комментарии Confluence, привязать комментарий к выделенному тексту (inline) или вниз страницы (footer). Авторизация и base URL — как в `tutu-confluence-jira` (`load_confluence_env` + Bearer `CONFLUENCE_TOKEN`).

## Главное правило

REST API Server/DC создаёт **только footer-комментарии** (внизу страницы). Саша проверяет результат глазами по UI и отклоняет footer, когда ожидает inline: «ты пишешь комментарии внизу странички — это не те комментарии». НЕ докладывать footer как выполнение задачи про inline и НЕ перебирать версии payload в поисках рабочей привязки — это тупик на часы.

## Что работает

**Создать footer через REST:**
```bash
load_confluence_env
curl -s -X POST -H "Authorization: Bearer $CONFLUENCE_TOKEN" -H "Content-Type: application/json" \
  "https://dom.tutu.ru/rest/api/content" -d '{
    "type": "comment",
    "container": {"id": "<pageId>", "type": "page", "status": "current"},
    "body": {"storage": {"value": "<p>текст</p>", "representation": "storage"}}
  }'
```
Альтернатива — tinymce-endpoint: `POST /rest/tinymce/1/content/{pageId}/comment?actions=true` с form-urlencoded (html/watch/uuid) и заголовком `X-Atlassian-Token: no-check`; тоже создаёт footer.

**Удалить комментарий:** `DELETE /rest/api/content/{commentId}`. Если у комментария есть content property (например, `inline-serialized-highlights`) — сначала `DELETE /rest/api/content/{commentId}/property/{key}`, иначе 500.

**Список и тип:** `GET /rest/api/content/{pageId}/child/comment?limit=100`; тип читать через `GET /rest/api/content/{id}?expand=extensions.inlineProperties` → `extensions.location` = inline|footer. Не доверять HTTP-статусу POST.

## Что НЕ работает (проверено, не повторять)

- Передача `extensions.inlineProperties` (originalSelection/markerRef/matchIndex/lastFetchTime/serializedHighlights) → 400 «Can not create inline comment» без обязательных полей, стабильный 500 с ними. Сериализованный DOM-путь выделения UI строит по живому браузерному DOM; через REST вручную он не воспроизводится.
- `extensions.location=inline` без inlineProperties → комментарий location=inline, но inlineProperties пустые — к тексту не привязан, не считать успехом.
- Inline-создание через REST официально не поддержано (CONFCLOUD-74261 Won't Fix).

## Единственный точный путь для inline

Перехватить ОДИН реальный POST при ручном создании комментария: F12 → Network → Fetch/XHR → запрос с «comment» в URL → его тело (Payload). По телу воспроизвести exact payload для остальных. Либо подготовить текст для ручной вставки.

## Питфоллы

- REST-статус 200 при POST comment ≠ успех привязки: проверять `extensions.location` и заполненность `inlineProperties`.
- DELETE комментария с content property без удаления property — 500. Порядок: DELETE property, затем DELETE comment.
- Мусорные тестовые комментарии остаются на странице и видны Саше внизу — чистить сразу.
- Эксперименты с комментариями — на тестовой странице личного пространства (`~tkachenkoav`), не на боевой; после эксперимента удалить страницу и её комментарии.
- В рендере (`body.view`) inline-маркер виден как `span.inline-comment-marker[data-ref]`; искать по `data-ref`, не по `ac:inline-comment-marker`.

## Анатомия inline-комментария (эталон, создан руками через UI)

1. В storage страницы — маркер вокруг выделенного текста:
   `<ac:inline-comment-marker ac:ref="<UUID>">(приоритет 1)</ac:inline-comment-marker>`
2. Комментарий: `extensions.location=inline`, `extensions.inlineProperties={originalSelection, markerRef}`.
3. Content property `inline-serialized-highlights` хранит сериализованный DOM-путь: `[["текст","<DOM-path>",0,13]]` (путь вида `37:0:3:0:6:0:0:0:0:0` — индексы child-узлов до текстового узла; формируется только браузерным DOM).

Смежная механика переноса данных между страницами Confluence (строки таблиц, marker'ы) — в `tutu-confluence-jira`.
