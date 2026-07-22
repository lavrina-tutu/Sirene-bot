---
name: movefrom-confluence
description: "MoveFromConfluence — двусторонняя синхронизация задач между Confluence и WorkVault, публикация summary встреч из FF на страницы Confluence."
version: 1.0.0
author: agent
tags: [confluence, tasks, workvault, sync, obsidian, tutu, meetings, summary]
platforms: [windows]
---

# MoveFromConfluence

Инструмент двусторонней синхронизации задач между Confluence и локальным WorkVault (Obsidian), а также публикации summary встреч из Fireflies на страницы Confluence.

## Контекст

- **Пользователь:** tkachenkoav@tutu.ru (ТУТУ)
- **Источник:** Confluence `dom.tutu.ru`, REST API v2, PAT-токен (`TUTU_ATLASSIAN_TOKEN` в `.env`)
- **Хранилище задач:** `{WORKVAULT_PATH}/Tasks/` — `.md` файлы с YAML frontmatter (Obsidian-совместимо)
- **Проект:** `/home/tkachenkoav/Documents/Cursor_projects/MoveFromConfluence/`
- **ТЗ:** `hermes-workspace/docs/tz/MoveFromConfluence_TZ_v1.0.md`
- **Тесты:** 37/37 ✅ (май 2026)

## Что делает

1. **Читает задачи** со страниц Confluence из списка отслеживаемых страниц (`pages.json`), сохраняет в WorkVault
2. **Двусторонняя синхронизация статусов** — задача закрыта/открыта в Confluence → обновляется в `.md`; статус изменён в `.md` → при следующем синке обновляется в Confluence
3. **Создаёт задачи** на страницах Confluence через TG-команду
4. **Публикует summary встреч** из `NewMeetings/` (MoveFromFF) как дочерние страницы в Confluence

## Форматы задач (парсинг)

Парсит 3 формата:
- **Action items** — `<ac:task>` элементы в Confluence Storage Format
- **@mention-задачи** — `@Имя: текст` в тексте страницы
- **Таблицы** — таблицы с колонками Задача/Исполнитель/Срок/Статус

## Схема задачи (YAML frontmatter в .md)

```yaml
confluence_page_id: "123456"
confluence_page_url: "https://dom.tutu.ru/..."
task_id: "task_001"
title: "Название задачи"
assignee: "email@tutu.ru"
project: "OKRS-123"
due_date: "2026-06-01"
status: "open"  # open / done / in_progress
description: "Детали что нужно сделать"
synced_at: "2026-05-23T14:00:00Z"
```

**Один .md файл = все задачи одной Confluence-страницы.** Разделитель: `<!-- TASK_SEPARATOR -->`.

## Список отслеживаемых страниц

Хранится в `pages.json` — не все страницы отслеживаются, только добавленные явно:
```bash
python -m movefromconfluence pages add <url>    # добавить страницу
python -m movefromconfluence pages list         # показать список
python -m movefromconfluence pages remove <url> # убрать из списка
```

## CLI

```bash
python -m movefromconfluence --mode cron         # синк всех страниц без TG
python -m movefromconfluence --mode manual       # синк + TG итог
python -m movefromconfluence --mode manual --dry-run
python -m movefromconfluence --mode sync --page-url <url>  # синк одной страницы

# Задачи
python -m movefromconfluence task add --page-url <url> --title "Название"

# Публикация summary встречи
python -m movefromconfluence summary publish --file <path> --page-url <url>
```

**Коды выхода:** 0/1/2/3/4 (стандарт MoveFrom*)

## TG-команды

| Команда | Действие |
|---|---|
| `/task add <page_url> <название>` | создать задачу на странице по шаблону Confluence |
| `/task sync <page_url>` | синк одной страницы |
| `/tasks sync` | синк всех страниц из списка |
| `/pages add <url>` | добавить страницу в список |
| `/pages list` | показать список страниц |
| `/pages remove <url>` | убрать страницу из списка |
| `/summary publish <meeting> <page_url>` | опубликовать summary встречи как дочернюю страницу |

## Публикация summary встреч (агентский сценарий)

### Явная команда
```
/summary publish <meeting_id или имя файла> <parent_page_url>
```
`parent_page_url` — **всегда указывается явно**, дефолта нет.

### По описанию встречи (natural language)
Пользователь говорит: *«Размести summary встречи от 20 мая с Ивановым по теме онбординг»*

Агент:
1. Извлекает дату (обязательно), ключевые слова (опционально)
2. Ищет файл `*- summary.md` в `NewMeetings/` по дате + fuzzy matching по названию
3. Если файла нет → проверяет `_registry.json` MoveFromFF → если есть → скачивает через `python -m movefromff --mode manual --meeting-id <id>`
4. Показывает карточку для подтверждения: *«Нашла: "Онбординг команды — 20.05.2026 14:00". Публикую?»*
5. После «да» → публикует через CLI

### Конвертация Markdown → Confluence XHTML
`md_converter.py` конвертирует: заголовки, жирный/курсив, списки, блоки кода.

## Голосовая постановка задачи (агентский сценарий)

Пользователь: *«Запиши задачку от сегодняшнего дня на Иванова по проекту Trisigma — создать сервер для размещения Trisigma, срок до 20 мая»*

Агент:
1. Извлекает: `title`, `assignee`, `project`, `due_date`, `description`, `date`
2. Показывает карточку, спрашивает страницу если не указана
3. После подтверждения → `/task add <page_url> <title>`
4. При следующем синке задача попадёт в `WorkVault/Tasks/`

CLI при этом **не меняется** — это агентский сценарий поверх существующих команд.

## Интеграция с конвейером

```
MoveFromExchange → contacts.enc → assignee резолв по email (через MarkObjectsFromSummary)
MoveFromFF → NewMeetings/ → summary.md → MoveFromConfluence summary publish
MoveFromConfluence → tasks.md в WorkVault/Tasks/
```

**Двусторонний контракт с Confluence:** merge по `synced_at` — последний писатель выигрывает. Кастомные поля `.md` не перезаписываются при синке.

## Питфоллы

- **Парсер action items** зависит от Confluence Storage Format (не XHTML) — при разных версиях Confluence структура `<ac:task>` может отличаться. Тестировать на реальной странице.
- **Дедупликация** по `task_id` = `{page_id}_{task_index}`. При удалении-добавлении задачи на той же странице индекс может измениться → дубль. Решение: тянуть встроенный ID задачи из `<ac:task-id>` если есть.
- **Двусторонний конфликт** — если задача обновлена и в Confluence, и в `.md` между синками → побеждает тот, чей `synced_at` новее. При конфликте лог предупреждение.
- **Rate limit Confluence API** — PAT-токены ТУТУ могут иметь ограничения. При получении 429 → tenacity backoff.
- **`parent_page_url` всегда явно** — нет дефолта в конфиге. Пользователь всегда указывает куда публиковать.
