# MoveFromConfluence — архитектура хранения в Obsidian (анализ Opus, 28.05.2026)

## Бриф-решения (согласовано с пользователем)

- **Структура папок:** гибрид — папка только если есть дочерние. Листья = просто `.md`
- **Корневая папка:** `WorkVault/Confluence/<Space>/<Страница>/` (с префиксом Confluence/)
- **Ссылки на изображения:** `![[image.png]]` (wiki-style, Obsidian default)
- **Ссылки вне скачанного дерева:** оставить как URL + пометить `🔗`
- **Удалённые в Confluence при ре-синке:** переносить в `_archive/` (не удалять)
- **Дополнительный режим:** выжимка страницы → TG + сохранение в vault по тем же правилам
- **Переключение API-токена:** хранить `CONFLUENCE_TOKEN_PREV` в `.env` для fallback дома
- **Инструмент:** один двусторонний (read + write), не два отдельных

## Структура папок (гибрид)

```
WorkVault/Confluence/<Space>/
├── Корневая страница/
│   ├── index.md                ← контент корневой страницы
│   ├── _assets/                ← вложения этой страницы
│   │   └── diagram.png
│   ├── Дочерняя без детей.md  ← лист = просто .md
│   └── Дочерняя с детьми/
│       ├── index.md
│       └── Внук.md
```

## Frontmatter (минимально полезный набор)

```yaml
---
confluence_id: "123456789"
confluence_url: "https://dom.tutu.ru/pages/viewpage.action?pageId=123456789"
confluence_space: "AA"
title: "Оригинальное название"
parent_id: "987654321"
parent: "[[Родительская страница]]"
children:
  - "[[Дочка 1]]"
  - "[[Дочка 2]]"
author: "ivanov@tutu.ru"
created: 2024-03-15T10:00:00Z
last_modified: 2025-11-20T14:30:00Z
version: 42
synced_at: 2026-05-28T16:14:00Z
tags:
  - confluence
  - space/AA
---
```

`confluence_id` + `version` — для инкрементального ре-синка (не качать если version не изменился).
`parent` как wiki-link — Obsidian Graph рисует связь вверх.
`children` — позволяет Dataview автогенерить TOC.

## Кросс-ссылки между страницами (двухфазный алгоритм)

1. **Pass 1:** скачиваем все страницы дерева, собираем индекс `page_id → relative_path`
2. **Pass 2:** проходим по markdown, резолвим ссылки:
   - Ссылка внутри дерева → `[[Title]]`
   - Ссылка вне дерева → `[Title](url) 🔗`
   - Ссылка на attachment → `![[file.png]]` или `[file.pdf](./_assets/file.pdf)`

## Что переиспользовать из текущего кода

| Файл | Статус |
|---|---|
| `confluence_client.py` | ✅ переиспользовать |
| `lock.py`, `logger.py`, `tg.py` | ✅ переиспользовать |
| `pages.py` | ⚠️ модель реестра годится, расширить |
| `parser.py` | ❌ для этой задачи (task extractor, не page parser) |
| `md_converter.py` | ❌ обратное направление (MD→Storage, не HTML→MD) |

## Что писать с нуля

1. `tree_walker.py` — рекурсивный обход через `/rest/api/content/{id}/child/page`
2. `html_to_md.py` — конвертация Storage Format → Markdown (markdownify + кастомные хэндлеры)
3. `attachments.py` — скачивание `/rest/api/content/{id}/child/attachment` → `_assets/`
4. `link_resolver.py` — pass-2 резолв по id→path индексу
5. `vault_writer.py` — материализация дерева на диск

## Confluece-специфичные макросы (конвертация)

- `ac:structured-macro[code]` → fenced code block
- `ac:structured-macro[info/warning/note]` → Obsidian callout `> [!info]`
- `ac:task` → `- [ ]` (задача)
- `ac:link` → wiki-link или URL

## Питфоллы

- **Именование файлов:** запрещённые символы Windows `< > : " / \ | ? *` → заменять на `-`
- **Конфликт title:** две страницы с одинаковым названием в одной папке → добавить ` (id12345)`
- **Зарезервированные имена Windows** (`CON`, `PRN`, `AUX`, `NUL`...) → добавить `_`
- **Для надёжного маппинга** вести `_meta/confluence_pages.json` (id → relative_path)
- **PAT дома vs в офисе:** токен привязан к сессии Kerberos. Дома может не работать → использовать `CONFLUENCE_TOKEN_PREV` в `.env` как fallback
