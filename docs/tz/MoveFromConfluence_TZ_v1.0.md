# ТЗ: Инструмент MoveFromConfluence v1.0 — синхронизация задач
# Двусторонняя синхронизация задач между Confluence и WorkVault + публикация summary встреч
# Версия: 1.0 | Дата: 2026-05-23 | Статус: На согласовании + обновлено 2026-05-25 (Keycloak SSO)

---

## 0. Философия (главное)

**MoveFromConfluence делает ОДНО:** синхронизирует задачи (и только задачи) в обе стороны между страницами Confluence и локальными Markdown-файлами в WorkVault. Идемпотентно и надёжно.

Двусторонний поток:
- **Confluence → WorkVault:** читать action items, @mention-задачи, задачи в таблицах → сохранять в `.md` с YAML frontmatter.
- **WorkVault → Confluence:** создавать задачи на странице через TG-команду `/task add <page_url> <название>`.
- **Статусы:** обновления статусов, сроков, исполнителей — синхронизируются в обе стороны.

Всё остальное — задача других инструментов. MoveFromFF читает встречи, MoveFromExchange читает контакты, MoveFromConfluence читает задачи.

**Принцип не-делания:**
- Не читает и не синхронизирует весь контент страницы (только задачи).
- Не создаёт новые Confluence-страницы (работает только с явно добавленными в `pages.json`).
- Не удаляет задачи из Confluence (только меняет статус).
- Не ведёт историю статусов; хранит только текущее состояние.
- Не конвертирует задачи в другие форматы (только Markdown с YAML frontmatter).
- Не синхронизирует описание задач после первой загрузки (берёт как есть из Confluence).

**Один источник истины — `pages.json`:** список явно добавленных страниц Confluence для синхронизации.

---

## 1. Что делает

- ✅ Читает задачи со страниц Confluence (action items, @mention-задачи, задачи в таблицах) через REST API v2.
- ✅ Парсит HTML/storage format Confluence и извлекает: название, исполнитель (email), проект, срок, описание, статус.
- ✅ Сохраняет все задачи одной страницы в один `.md` файл в `{WORKVAULT_PATH}/Tasks/`.
- ✅ Синхронизирует в обе стороны: статусы, сроки, исполнителей (Confluence ↔ .md).
- ✅ Создаёт задачи на странице Confluence через TG-команду `/task add <page_url> <название>`.
- ✅ Ведёт реестр задач (по `confluence_page_id + task_index`) для дедупликации.
- ✅ Публикует summary встреч (из WorkVault/MoveFromFF) как дочерние страницы Confluence через `/summary publish`.
- ✅ Конвертирует Markdown → Confluence Storage Format (XHTML) с сохранением разметки.
- ✅ Режимы: cron (регулярный синк всех страниц), manual (ручной запуск), sync (синк одной страницы).
- ✅ Dry-run режим (план без записи).
- ✅ TG-уведомления при ручном запуске и ошибках.
- ✅ Логирование в `_sync_log.md` (одна строка) и `logs/confluence.jsonl` (события).

---

## 2. Чего НЕ делает

- ❌ Не читает весь контент страницы — только задачи (action items, @mentions, таблицы).
- ❌ Не создаёт новые Confluence-страницы (за исключением дочерних при публикации summary).
- ❌ Не удаляет задачи из Confluence (меняет статус, но физически не удаляет).
- ❌ Не ведёт историю статусов задач (только текущее состояние).
- ❌ Не синхронизирует описание задачи после первой загрузки (кеширует как есть).
- ❌ Не поддерживает вложения и ссылки внутри задач (хранит только текст).
- ❌ Не создаёт подзадачи в Confluence (работает только с top-level задачами).
- ❌ Не требует наличия `contacts.enc` (email → ФИО — задача downstream-инструментов).
- ❌ Не конвертирует весь контент WorkVault в Confluence — только summary-файлы из MoveFromFF (паттерн `*- summary.md`).

---

## 3. Алгоритм (Шаги 0-4)

### Шаг 0. Preflight
1. Взять `portalocker`-лок `.locks/moveconfluence.lock`. Занят → exit 2.
2. Проверить `.env`: `TUTU_ATLASSIAN_TOKEN`, `WORKVAULT_PATH`, `CONFLUENCE_DOMAIN` (例: `dom.tutu.ru`). Нет обязательных → exit 2 (+ TG если `--mode manual`).
3. Создать недостающие папки: `Tasks/`, `Tasks/logs/`, `.locks/`, нужная структура под `{WORKVAULT_PATH}/Tasks/`.
4. Прочитать `{WORKVAULT_PATH}/pages.json` — список страниц для синхронизации.

### Шаг 1. Ping Confluence
- Простой запрос к REST API (например, `GET /rest/api/2/space`) с таймаутом 15 с, 3 retry (tenacity) с backoff 2/4/8 с.
- Недоступен → exit 3 (+ TG если `--mode manual`; для `cron`/`test` — только в логе).

### Шаг 2. Определение окна синхронизации
- `--mode cron` → полный синк всех страниц из `pages.json`.
- `--mode manual <page_url>` → синк одной страницы (или `/task sync <page_url>` из TG).
- `--mode sync <page_url>` → синк одной страницы (CLI).
- `--mode test` → синк всех страниц (для тестирования, как cron, но с extra логированием).

### Шаг 3. Для каждой страницы (или одной, если mode=sync):

#### 3a. Чтение задач из Confluence
1. Запрос страницы через REST API v2: `GET /api/v2/pages/{page_id}?body-format=storage`.
2. Парсинг HTML/storage format:
   - **Action items:** поиск блоков `<ac:task>` или `<ri:task-list>`
   - **@mention-задачи:** поиск паттерна `@user нужно сделать ...` (переносится в следующей строке или до конца строки).
   - **Задачи в таблицах:** строки, содержащие признаки задач (чекбокс, слово «задача», «@mention»).
3. Для каждой найденной задачи:
   - Извлечь: **название** (короткое, одна строка), **исполнитель** (email из @mention или поле assignee), **проект** (из metadata или тега), **срок** (дата, если указана), **описание** (контекст, детали), **статус** (open / done / in_progress).
   - Присвоить уникальный **task_id**: `confluence_page_id + "_" + task_index` (index = порядок в списке задач страницы).

#### 3b. Merge (синхронизация в локальный .md)
1. Прочитать текущий .md файл страницы (если существует): `{WORKVAULT_PATH}/Tasks/{page_title} - tasks.md`.
2. Для каждой задачи из Confluence:
   - Если `task_id` уже в локальном .md (по `confluence_page_id` + `task_index`):
     - **Обновить только изменяемые поля:** `status`, `due_date`, `assignee`, `synced_at`.
     - **Не трогать:** `description` (хранится как есть, только читается из Confluence один раз).
   - Если новая задача:
     - Добавить всю запись с YAML frontmatter (см. §4).
3. **Обратная синхронизация (WorkVault → Confluence):**
   - Если статус задачи в .md изменился вручную (отличается от последнего `synced_at`), обновить статус в Confluence.
   - Этап 3b выполняется **после** Шага 3a (читаем из Confluence, потом применяем локальные изменения).

#### 3c. Запись в Confluence (если есть новые задачи из TG-команды `/task add`)
1. Для каждой неправленой локальной задачи (с `synced_at = null` или пусто):
   - Создать action item / @mention на странице Confluence через REST API v2.
   - Формат: `@<assignee> <title>` (action item) или блок `<ac:task>`.
   - Получить `task_id` из ответа API (если есть в response).
   - Обновить локальный .md: проставить `synced_at` = текущее время.
   - Логировать в `logs/confluence.jsonl` событие `task_created`.

#### 3d. Финализация для страницы
1. Если был хоть один изменения (новые задачи, обновления статусов) → переписать .md файл атомарно (`tmp + os.replace()`).
2. Дописать в `logs/confluence.jsonl` событие `page_synced`: количество обновлённых, новых, ошибок.

### Шаг 4. Финализация запуска
1. Дописать одну строку в `_sync_log.md` (итог: см. §10).
2. Если `--mode manual` → отправить TG-алерт по правилам (см. §9).
3. Для `--mode cron` / `--mode test` TG не дёргать вообще.
4. Снять лок.
5. Exit 0 (всё ок) / 1 (часть упала) / 2 (лок или preflight) / 3 (Confluence недоступен) / 4 (фатально).

---

## 4. Схема задачи в .md (YAML frontmatter + содержимое)

**Один файл = все задачи одной Confluence-страницы.**

Имя файла:
```
{page_title} - tasks.md
```

**Пример содержимого файла:**
```markdown
---
confluence_page_id: "123456"
confluence_page_url: "https://dom.tutu.ru/pages/viewpage.action?pageId=123456"
task_id: "task_001"
title: "Подготовить отчёт Q2"
assignee: "ivanov@tutu.ru"
project: "OKRS-Q2"
due_date: "2026-06-15"
status: "open"
description: "Собрать метрики по KPI, написать аналитику, отправить на согласование"
synced_at: "2026-05-23T14:00:00Z"
---

## Задача: Подготовить отчёт Q2

**Исполнитель:** ivanov@tutu.ru  
**Проект:** OKRS-Q2  
**Срок:** 2026-06-15  
**Статус:** open  
**Синхронизировано:** 2026-05-23T14:00:00Z

### Детали
Собрать метрики по KPI, написать аналитику, отправить на согласование

---

---
confluence_page_id: "123456"
confluence_page_url: "https://dom.tutu.ru/pages/viewpage.action?pageId=123456"
task_id: "task_002"
title: "Закрыть баги из P1"
assignee: "petrov@tutu.ru"
project: "DEV-BUGS"
due_date: "2026-06-01"
status: "in_progress"
description: "Список багов в confluence.md, приоритет P1, время <= 8ч на каждый"
synced_at: "2026-05-23T14:00:00Z"
---

## Задача: Закрыть баги из P1
...
```

**YAML frontmatter полей (обязательные / опциональные):**

| Поле | Тип | Обязательный? | Комментарий |
|---|---|---|---|
| `confluence_page_id` | string | ✅ | ID страницы в Confluence (из URL или API) |
| `confluence_page_url` | string | ✅ | Полный URL страницы |
| `task_id` | string | ✅ | Уникальный ID задачи (page_id + index, или встроенный ID из Confluence) |
| `title` | string | ✅ | Короткое название, одна строка |
| `assignee` | string | ⚠️ | Email исполнителя (может быть null, если не указан) |
| `project` | string | ⚠️ | Код проекта (например, OKRS-Q2, DEV-BUGS; может быть null) |
| `due_date` | string (YYYY-MM-DD) | ⚠️ | Срок в формате ISO (может быть null) |
| `status` | string | ✅ | open / done / in_progress (по умолчанию open) |
| `description` | string | ✅ | Подробные детали, что нужно сделать |
| `synced_at` | string (ISO-8601 UTC) | ✅ | Дата последней синхронизации (2026-05-23T14:00:00Z) |

**Правила YAML:**
- Все даты — UTC ISO-8601 с `Z`.
- Поля `assignee`, `project`, `due_date` — могут быть `null`.
- Статусы: `open` / `done` / `in_progress` (рекомендуется 3 варианта, допускаются другие).
- `title` — не должен содержать переносы строк (одна строка максимум 100 символов).

---

## 5. Парсинг задач из Confluence

### Форматы источников

#### 5a. Action Items (встроенные в Confluence)
**Storage format:**
```xml
<ac:task-list>
  <ac:task>
    <ac:task-id>123</ac:task-id>
    <ac:task-status>incomplete</ac:task-status>
    <ac:task-body>@user123 Подготовить отчёт до пятницы</ac:task-body>
  </ac:task>
</ac:task-list>
```

**Парсинг:**
- Найти `<ac:task>` элементы.
- Извлечь `<ac:task-body>` → текст задачи.
- Если есть `@user` → это исполнитель (найти email по mention).
- Статус из `<ac:task-status>`: `incomplete` → `open`, `complete` → `done`.
- Описание: первая строка до точки (.) или запятой (,) → название. Остаток → описание.

#### 5b. @mention-задачи в тексте страницы
**Паттерны:**
```
@ivanov нужно подготовить отчёт до пятницы
@user на согласование, срок 2026-06-15
@petrov Закрыть баги (P1, до 2026-06-01)
```

**Парсинг:**
- Regex: `@(\w+)\s+([^\.]+)(?:\.|$)` (новая строка после @mention может быть разделителем).
- Извлечь: email по @mention → исполнитель.
- Текст после @mention → название + описание.
- Если в тексте есть дата (2026-MM-DD) → `due_date`.
- По умолчанию `status: open`.

#### 5c. Задачи в таблицах
**Пример таблицы:**
```
| Задача | Исполнитель | Срок | Статус |
|---|---|---|---|
| Подготовить отчёт | @ivanov | 2026-06-15 | open |
| Закрыть баги P1 | @petrov | 2026-06-01 | in_progress |
```

**Парсинг:**
- Если таблица содержит колонки "Задача", "Исполнитель" (или "Assignee"), "Срок" (или "Due Date"), "Статус" (или "Status"):
  - Каждая строка → одна задача.
  - Извлечь ячейки по столбцам.
  - Резолв @mention в колонке Исполнитель → email.
  - Парсинг даты из колонки Срок (формат YYYY-MM-DD или 2026-06-15).
  - Маппинг статуса: строка → `open` / `done` / `in_progress`.

### Дедупликация
- После парсинга каждой страницы → создать dict `{ task_id → task_data }`.
- `task_id` = `confluence_page_id + "_task_" + str(index).zfill(3)` (где index = порядок в списке задач).
- Если одна и та же задача найдена в разных форматах (action item + в таблице) → оставить первое вхождение по порядку в HTML.

---

## 5a. Публикация summary встреч в Confluence

### Суть

Пользователь хранит summary встреч (из Fireflies.ai) в WorkVault. Иногда нужно опубликовать summary на страницу Confluence — как красиво отформатированную дочернюю страницу.

### Команды TG

#### `/summary publish <meeting_id или имя файла> <parent_page_url>`

Публикует summary встречи из WorkVault как дочернюю страницу Confluence.

**Примеры:**
```
/summary publish 2026-05-20_11-30-00_Meeting https://dom.tutu.ru/pages/viewpage.action?pageId=123456
/summary publish "2026-05-20 11-30-00 Встреча с клиентом - summary.md" https://dom.tutu.ru/pages/viewpage.action?pageId=123456
```

#### `/summary list`

Показывает список доступных summary-файлов (последние 20 встреч) из `{WORKVAULT_PATH}/Meetings/NewMeetings/`.

**Пример вывода:**
```
📋 Доступные summary для публикации (20):
1. 2026-05-23 14:30 - Планёрка продакт
2. 2026-05-23 10:15 - Встреча с клиентом X
3. 2026-05-22 16:00 - Синк с командой
...
```

### Алгоритм публикации (5 шагов)

1. **Поиск файла summary**
   - Поиск в `{WORKVAULT_PATH}/Meetings/NewMeetings/` файла с паттерном `*- summary.md`.
   - Ищем по `meeting_id` (префикс имени файла) или по полному имени файла.
   - Если файл не найден → ошибка в TG: «Summary-файл не найден».

2. **Чтение Markdown-содержимого**
   - Прочитать файл `*.md`.
   - Извлечь из frontmatter (если есть) или имени файла: дата встречи, название встречи.
   - Формат имени файла (из MoveFromFF): `YYYY-MM-DD HH-MM-SS <Title> - summary.md`.

3. **Конвертация Markdown → Confluence Storage Format (XHTML)**
   - Парсинг Markdown с сохранением разметки:
     - Заголовки `# H1`, `## H2`, `### H3` → `<h1>`, `<h2>`, `<h3>` (Confluence storage format).
     - **Жирный** `**text**` → `<strong>text</strong>`.
     - *Курсив* `*text*` → `<em>text</em>`.
     - Неупорядоченные списки `- item` → `<ul><li>...</li></ul>`.
     - Упорядоченные списки `1. item` → `<ol><li>...</li></ol>`.
     - Блоки кода ` ``` ` → Confluence macro `<ac:structured-macro ac:name="code">`.
     - Ссылки `[text](url)` → `<a href="url">text</a>`.
     - Горизонтальная линия `---` → `<hr/>`.
   - **Модуль:** `md_converter.py` — Markdown → XHTML конвертер.

4. **Создание дочерней страницы в Confluence**
   - Парсинг `parent_page_url` → извлечь `parent_page_id`.
   - Запрос информации о родительской странице (проверка доступа).
   - Создание дочерней страницы через REST API v2:
     - **Endpoint:** `POST /api/v2/pages`.
     - **Параметры:**
       - `title`: `{дата встречи} {название встречи}` (например, `2026-05-23 14:30 - Планёрка продакт`).
       - `space_id`: из данных родительской страницы.
       - `parent_id`: `parent_page_id`.
       - `body.storage.value`: сконвертированный HTML-контент.
   - Получить ID созданной страницы из ответа API.

5. **Возврат ссылки и уведомление**
   - TG-ответ: `✅ Summary опубликована: <ссылка на созданную страницу>`.
   - Логирование в `logs/confluence.jsonl`: событие `summary_published`, `parent_page_id`, `created_page_id`, `title`.

### Защита от дублей

**Сценарий:** пользователь дважды запустил `/summary publish` с одинаковыми параметрами.

- Перед созданием новой страницы → проверить наличие дочерней страницы с идентичным заголовком под `parent_page_id`.
- Если страница **существует**:
  - TG-запрос: «Страница с таким названием уже существует. Хотите её обновить или создать новую копию? (1 = обновить, 2 = новая)».
  - Если выбран вариант **1 (обновить)** → заменить содержимое существующей страницы (PUT запрос).
  - Если выбран вариант **2 (новая)** → создать с суффиксом (например, `2026-05-23 14:30 - Планёрка продакт (копия 1)`).
  - Таймаут ответа: 60 сек. Если не ответил → отмена.

### Структура данных

Summary-файл читается из `{WORKVAULT_PATH}/Meetings/NewMeetings/`:
```
YYYY-MM-DD HH-MM-SS Meeting Title - summary.md
```

Содержимое (пример):
```markdown
# Саммари: Планёрка продакт

## Overview
Обсуждены метрики Q2, план релизов, боттленеки команды.

## Action Items
- @ivanov Подготовить отчёт по метрикам (до 2026-05-25)
- @petrov Провести интервью с клиентом (до 2026-05-24)

## Keywords
Product, roadmap, metrics, Q2, sprint
```

### 5а.2 Публикация по описанию встречи (natural language)

**Кейс:** пользователь не знает точного имени файла встречи. Он описывает встречу в свободной форме и просит опубликовать её summary.

**Примеры запроса пользователя:**
- *«Размести summary встречи от 20 мая с Ивановым по теме онбординг»*
- *«Опубликуй встречу вчера 14:00 с командой аналитики»*
- *«Выложи summary встречи от 2026-05-22 "Планёрка продакт"»*

**Алгоритм агента (Hermes в Telegram):**

1. **Парсинг описания пользователя** → извлечь из текста:
   - **Дата встречи (обязательно):** точная дата (2026-05-20, 20 мая), вчера, на выходных — парсить в YYYY-MM-DD.
   - **Время встречи (опционально):** 14:00, 14:30, утром/вечером — парсить в HH-MM (попытка, может быть null).
   - **Тема/ключевые слова (опционально):** названия встреч, упомянутые люди, слова (онбординг, планёрка, аналитика).

2. **Поиск файла в WorkVault** в `{WORKVAULT_PATH}/Meetings/NewMeetings/`:
   - Формат имени файла: `YYYY-MM-DD HH-MM-SS <Title> - summary.md`.
   - **По дате:** отфильтровать файлы по дате встречи (шаг 1).
   - **По времени (если указано):** отфильтровать по часу-минутам начала встречи.
   - **По ключевым словам (если указаны):** поиск слов из названия встречи в имени файла (нечёткий поиск).
   - Если найдено **ровно один файл** → перейти на шаг 4.
   - Если найдено **несколько файлов** → показать пользователю список и просить выбрать.
   - Если **не найдено файлов** → перейти на шаг 3.

3. **Проверка реестра MoveFromFF** (если файл не найден):
   - Прочитать реестр встреч: `{WORKVAULT_PATH}/Meetings/NewMeetings/_registry.json` (если существует).
   - Проверить: есть ли запись о встречи за эту дату?
   - Если есть в реестре, но файла `.md` нет → запустить загрузку:
     ```bash
     MoveFromFF --mode manual --from-date YYYY-MM-DD --to-date YYYY-MM-DD
     ```
     После загрузки → повторить поиск из шага 2.
   - Если нет в реестре → ответить пользователю: «Встреча не найдена ни в локальных файлах, ни в реестре Fireflies. Проверьте дату или название.»

4. **Подтверждение у пользователя** (найден файл):
   - Показать: `Нашла: "<Название встречи> — <дата> <время>". Публикую?`
   - Пример: `Нашла: "Онбординг команды — 20.05.2026 14:00". Публикую?`
   - Дождаться ответа (Да/✅ или Нет/❌) с таймаутом 60 сек. Если таймаут → отмена.

5. **Публикация summary** (после подтверждения):
   - Страница **всегда** указывается пользователем явно в команде (обязательный параметр).
   - Выполнить команду (внутренний вызов):
     ```
     /summary publish <найденный_файл> <parent_page_url>
     ```
   - Вернуть результат пользователю (успех или ошибка).

**TG-команда (натуральный язык через агента):**

Пользователь просто пишет в чат описание встречи на русском. Агент распознает это как запрос на публикацию summary и выполняет алгоритм выше.

Пример диалога:
```
Пользователь: Размести summary встречи от 20 мая с Ивановым по теме онбординг

Hermes: Проверяю... 🔍

Hermes: Нашла: "Онбординг команды — 20.05.2026 14:00". Публикую?

Пользователь: Да

Hermes: ✅ Summary опубликована: https://dom.tutu.ru/pages/viewpage.action?pageId=999999
```

**Важные детали:**
- **CLI не меняется.** Это сценарий работы агента (Hermes в TG), поверх существующих команд `/summary publish` и `/summary list`.
- **parent_page_url:** **всегда** указывается пользователем явно при запросе на публикацию. Это обязательный параметр.
- **Дата обязательна.** Если в описании нет даты → попросить уточнить: «Уточните дату встречи в формате ДД.MM или YYYY-MM-DD.»
- **Нечёткий поиск:** используется fuzzy matching для поиска по ключевым словам (библиотека `fuzzywuzzy` или аналог).

---

## 6. Запись задачи в Confluence (WorkVault → Confluence)

### TG-команда
```
/task add <page_url> <название>
```

**Пример:**
```
/task add https://dom.tutu.ru/pages/viewpage.action?pageId=123456 Подготовить презентацию
```

### Процесс
1. Парсинг `page_url` → извлечь `page_id` из параметра `pageId=...`.
2. Проверить, есть ли `page_id` в `pages.json` (список отслеживаемых страниц). Если нет → ошибка: «Страница не в списке синхронизируемых».
3. Создать action item в Confluence через REST API v2:
   - **Endpoint:** `POST /api/v2/pages/{page_id}/body` или нативный REST для добавления блока.
   - **Формат:** action item (встроенный формат Confluence) с телом `<title>`.
   - Если указан исполнитель (в .md файле) → добавить @mention в тело.
4. Получить ID созданной задачи из ответа API (если поддерживается).
5. Добавить локально в .md файл:
   - Новая запись с YAML frontmatter.
   - `task_id` = уникальный ID из Confluence (или сгенерированный).
   - `synced_at` = текущее время UTC.
6. Логировать в `logs/confluence.jsonl`: событие `task_created`, `page_id`, `task_id`, `title`.
7. Ответ в TG: `✅ Задача создана: <название>`.

### Шаблон задачи в Confluence
```
@<assignee> <title>
```

Исполнитель контролируется пользователем при создании в .md файле (поле `assignee`).

---

## 7. Двусторонняя синхронизация статусов

### Алгоритм разрешения конфликтов

**Правило:** последний писатель выигрывает (по `synced_at` и временным меткам изменений).

#### Сценарий 1: Статус изменился в Confluence
```
Confluence: status = done, updated_at = 2026-05-23T15:00:00Z
WorkVault:  status = open, synced_at = 2026-05-23T14:00:00Z
```
→ Обновить .md: status = done, synced_at = 2026-05-23T15:00:00Z

#### Сценарий 2: Статус изменился в .md вручную
```
Confluence: status = open, updated_at = 2026-05-23T14:30:00Z
WorkVault:  status = done, synced_at = 2026-05-23T14:00:00Z (ручное изменение без обновления synced_at)
```
→ Обновить Confluence: status = done
→ Обновить .md: synced_at = текущее время

#### Сценарий 3: Оба изменились
```
Confluence: status = done, updated_at = 2026-05-23T15:00:00Z
WorkVault:  status = in_progress, synced_at = 2026-05-23T14:00:00Z
```
→ **Confluence выигрывает** (более свежее время).
→ Обновить .md: status = done, synced_at = 2026-05-23T15:00:00Z
→ Логировать конфликт: `conflict_resolved`, `field: status`, `winner: confluence`

### Синхронизируемые поля
- `status` — open / done / in_progress.
- `due_date` — YYYY-MM-DD (если изменился срок в Confluence → обновить .md; и наоборот).
- `assignee` — email исполнителя.
- **Описание не синхронизируется** — берётся один раз из Confluence, затем хранится в .md как есть.

### История статусов
- **Не ведётся.** Только текущее состояние. Если требуется история — это задача отдельного аудит-инструмента.

---

## 8. Список отслеживаемых страниц (pages.json)

**Путь:** `{WORKVAULT_PATH}/pages.json`

**Содержимое:**
```json
{
  "schema_version": "1.0",
  "updated_at": "2026-05-23T14:30:00Z",
  "pages": {
    "123456": {
      "page_id": "123456",
      "page_url": "https://dom.tutu.ru/pages/viewpage.action?pageId=123456",
      "page_title": "Q2 OKRs",
      "added_at": "2026-05-20T10:00:00Z",
      "last_synced_at": "2026-05-23T14:30:00Z"
    },
    "789012": {
      "page_id": "789012",
      "page_url": "https://dom.tutu.ru/pages/viewpage.action?pageId=789012",
      "page_title": "Dev Bugs",
      "added_at": "2026-05-21T14:00:00Z",
      "last_synced_at": "2026-05-23T14:30:00Z"
    }
  }
}
```

### TG-команды управления страницами

#### `/pages add <page_url>`
```
/pages add https://dom.tutu.ru/pages/viewpage.action?pageId=123456
```
**Процесс:**
1. Парсинг URL → `page_id`.
2. Запрос страницы через REST API → получить `page_title`.
3. Добавить запись в `pages.json`.
4. Ответ: `✅ Страница добавлена: "Q2 OKRs" (ID 123456)`.

#### `/pages list`
**Вывод:**
```
📋 Отслеживаемые страницы (3):
1. Q2 OKRs (ID: 123456) — последний синк 2026-05-23 14:30
2. Dev Bugs (ID: 789012) — последний синк 2026-05-23 14:30
3. Team Tasks (ID: 345678) — последний синк 2026-05-22 10:15
```

#### `/pages remove <page_url>`
```
/pages remove https://dom.tutu.ru/pages/viewpage.action?pageId=123456
```
**Процесс:**
1. Парсинг URL → `page_id`.
2. Удалить запись из `pages.json`.
3. **Не удаляет** локальный .md файл (остаётся для истории).
4. Ответ: `✅ Страница удалена из списка синхронизируемых`.

---

## 9. TG-команды и уведомления

### Команды

|| Команда | Действие | Ответ |
||---|---|---|
|| `/task add <page_url> <название>` | Создать задачу на странице | ✅ Задача создана / ❌ Ошибка |
|| `/task sync <page_url>` | Синк одной страницы | Итог синка |
|| `/pages add <url>` | Добавить страницу | ✅ Добавлено |
|| `/pages list` | Показать список страниц | Список с датами синка |
|| `/pages remove <url>` | Убрать страницу | ✅ Удалено |
|| `/tasks sync` | Синк всех страниц | Итог всех синков |
|| `/summary publish <meeting_id или имя файла> <parent_page_url>` | Опубликовать summary встречи как дочернюю страницу | ✅ Ссылка на созданную страницу / ❌ Ошибка |
|| `/summary list` | Показать список доступных summary для публикации | Список последних 20 встреч |

### Уведомления

**Главный принцип:** TG-алерты шлёт **только ручной запуск**. Cron работает молча — статусы только в логе.

| Сценарий | TG? | Текст |
|---|---|---|
| **Ручной запуск** (`/task sync <url>` / `/tasks sync`) — успех | ✅ | Итог: «Синхронизировано N задач, обновлено M, новых K» |
| **Ручной запуск** (`/task add`) — успех | ✅ | ✅ Задача создана: «<название>» |
| **Ручной запуск** — любая ошибка (Confluence недоступен, конфликт данных) | ✅ | Текст ошибки + рекомендация |
| **Cron** (`--mode cron`) — успех или ошибки | ❌ | Только в `_sync_log.md` и `logs/confluence.jsonl` |

Флаг `--no-tg` отключает TG-алерты в ручном режиме (для отладки).

---

## 9а. Голосовая постановка задачи через агента

### Кейс

Пользователь говорит в Telegram свободным текстом:

> «Запиши задачку от сегодняшнего дня на Иванова по проекту Trisigma — создать сервер для размещения Trisigma, срок до 20 мая»

### Алгоритм агента (Hermes в TG, не CLI)

1. **Извлечение полей** из естественного текста:
   - `title` (короткое, одна строка) — основное действие (например, «Создать сервер для размещения Trisigma»).
   - `assignee` (email или ФИО) — кому назначена задача (найти в контактах, если имя указано; например, Иванов → ivanov@tutu.ru).
   - `project` (код проекта) — из упоминания (например, Trisigma → TRISIGMA).
   - `due_date` (дата в формате YYYY-MM-DD) — срок выполнения (например, 20 мая → 2026-05-20).
   - `description` (если есть) — дополнительные детали.
   - `date` (по умолчанию сегодня) — дата постановки задачи.

2. **Показать карточку для подтверждения**:
   ```
   📋 Новая задача:
   Название: Создать сервер для размещения Trisigma
   Исполнитель: Иванов (ivanov@tutu.ru)
   Проект: Trisigma
   Срок: 2026-05-20
   Дата постановки: 2026-05-23
   
   👉 Укажите страницу Confluence для размещения (если не указана):
   /summary publish <page_url>
   ```
   - Если страница **не указана** в команде → спросить явно: «Какую страницу Confluence указать как родительскую для этой задачи? (Пришлите URL)».
   - Ожидать ответ (URL страницы) с таймаутом 60 сек.

3. **После подтверждения** → вызвать внутренне:
   ```
   /task add <page_url> <title>
   ```
   с полным YAML frontmatter (включая assignee, project, due_date).

4. **При следующем синке** (`--mode cron` или `/tasks sync`) → задача автоматически попадёт в `{WORKVAULT_PATH}/Tasks/{page_title} - tasks.md`.

### Уточнения

- **CLI не меняется.** Это сценарий работы агента (Hermes в TG), поверх существующей команды `/task add`.
- **TG-взаимодействие полностью в агенте** — парсинг текста, извлечение полей, подтверждение — всё происходит в Hermes.
- **Резолв ФИО → email** — используется `contacts.enc` из MoveFromExchange (graceful degradation: если недоступен, спросить email явно).
- **Страница всегда явная** — в отличие от публикации summary, здесь нет дефолта; пользователь обязательно указывает URL Confluence-страницы.

---

## 10. Логирование

**`{WORKVAULT_PATH}/Tasks/_sync_log.md`** — одна строка на запуск (append-only):
```
2026-05-23 14:30:00Z [cron] pages=2 tasks_synced=8 tasks_new=2 updates=5 duration=3.2s
2026-05-23 18:30:00Z [manual] pages=1 tasks_synced=3 tasks_new=1 updates=1 duration=1.5s error=0
```

**`{WORKVAULT_PATH}/Tasks/logs/confluence.jsonl`** — одна строка JSON на событие:
```json
{"ts":"2026-05-23T14:30:05Z","event":"page_synced","page_id":"123456","page_title":"Q2 OKRs","tasks_read":5,"tasks_new":1,"tasks_updated":2}
{"ts":"2026-05-23T14:30:10Z","event":"task_created","page_id":"123456","task_id":"task_001","title":"Подготовить отчёт"}
{"ts":"2026-05-23T14:30:15Z","event":"status_updated","task_id":"task_002","field":"status","old":"open","new":"done","source":"confluence"}
{"ts":"2026-05-23T14:30:20Z","event":"sync_error","page_id":"123456","error":"Confluence timeout","retries":3}
{"ts":"2026-05-23T14:30:25Z","event":"run_summary","mode":"cron","pages":2,"total_synced":8,"total_new":2,"errors":0,"duration":3.2}
```

---

## 11. CLI

```bash
# Синхронизация
python -m moveconfluence --mode cron                              # фоновый синк всех страниц
python -m moveconfluence --mode manual                            # ручной синк всех страниц, с TG
python -m moveconfluence --mode sync https://dom.tutu.ru/pages/... # синк одной страницы
python -m moveconfluence --mode test                              # синк всех с extra логированием

# Управление страницами
python -m moveconfluence pages list
python -m moveconfluence pages add https://dom.tutu.ru/pages/...
python -m moveconfluence pages remove https://dom.tutu.ru/pages/...

# Управление задачами
python -m moveconfluence task show <page_id> <task_id>
python -m moveconfluence task edit <task_id> --status done

# Опции
python -m moveconfluence --mode cron --dry-run                    # план без записи
python -m moveconfluence --mode manual --no-tg                    # без TG-уведомлений
python -m moveconfluence --verbose                                # DEBUG лог
```

**Коды выхода:**
- `0` — успех
- `1` — частичный успех (часть страниц упала, но основное выполнено)
- `2` — ошибка конфигурации (лок занят, `.env` неполный, `pages.json` не существует)
- `3` — Confluence недоступен (сервер не отвечает, таймаут, auth ошибка)
- `4` — фатальная ошибка (невосстановимая ошибка данных, крах при merge)

---

## 12. Структура проекта

```
MoveFromConfluence/
├── .venv/
├── .env                                # TUTU_ATLASSIAN_TOKEN, WORKVAULT_PATH, CONFLUENCE_DOMAIN, TELEGRAM_*
├── .env.example
├── pyproject.toml
├── README.md
├── moveconfluence/
│   ├── __main__.py                    # CLI + оркестрация (Шаги 0-4)
│   ├── config.py                      # pydantic Settings из .env
│   ├── confluence_client.py           # REST API v2 + tenacity retry
│   ├── parser.py                      # парсинг HTML/storage format → задачи
│   ├── store.py                       # read/write .md файлы (атомарно)
│   ├── syncer.py                      # двусторонний merge (Confluence ↔ WorkVault)
│   ├── pages.py                       # управление pages.json
│   ├── md_converter.py                # конвертация Markdown → Confluence Storage Format (XHTML)
│   ├── lock.py                        # portalocker
│   ├── logger.py                      # _sync_log.md + jsonl
│   ├── tg.py                          # TG-команды и уведомления
│   └── templates/
│       └── (по необходимости)
├── tests/
│   ├── test_parser.py
│   ├── test_store.py
│   ├── test_syncer.py
│   ├── test_md_converter.py
│   ├── test_confluence_client.py
│   └── fixtures/
└── scripts/
    └── run_cron.bat
```

---

## 13. DoD (Критерии приёмки, 7 пунктов)

1. ✅ `--mode manual` читает задачи со всех страниц из `pages.json` и выводит в TG итог: «Синхронизировано N, новых M, обновлено K».
2. ✅ `/task add <page_url> <название>` создаёт action item на странице Confluence и добавляет запись в локальный .md файл с `synced_at`.
3. ✅ Статус, изменённый в Confluence → обновляется в .md при следующем синке.
4. ✅ Статус, изменённый в .md вручную → обновляется в Confluence при следующем синке (two-way sync).
5. ✅ Повторный синк одной страницы не создаёт дубликаты задач (дедупликация по `task_id`).
6. ✅ `pages.json` валиден по pydantic-схеме (`schema_version=1.0`); все локальные .md файлы содержат корректный YAML frontmatter.
7. ✅ Секреты (PAT-токен, пути) — только в `.env`, в коде нет хардкодов.

---

## 14. Интеграция с другими инструментами

### MoveFromExchange (контакты)
- **MoveFromConfluence** сохраняет email исполнителя в `assignee` (поле в YAML frontmatter).
- **Для резолва email → ФИО** используется `contacts.enc` из MoveFromExchange (опционально, downstream-задача).
- **Graceful degradation:** если `contacts.enc` недоступен, MoveFromConfluence продолжает работать, храня email как есть.
- **Обновление 2026-05-25:** Zulip содержит 1167 активных контактов; downstream-инструменты могут использовать оба источника (Exchange GAL + Zulip API) для резолва участников встреч и исполнителей задач.

### MoveFromFF (встречи и summary)
- **MoveFromConfluence** читает summary встреч из `{WORKVAULT_PATH}/Meetings/NewMeetings/` (паттерн `*- summary.md`).
- Summary создаёт MoveFromFF и сохраняет в `NewMeetings/` (см. контракт в MoveFromFF_TZ_v2.0).
- **Команда `/summary publish`** берёт файл summary из MoveFromFF и публикует как дочернюю страницу в Confluence.
- **Контракт:** MoveFromFF гарантирует стабильные имена файлов (детерминированные, YYYY-MM-DD HH-MM-SS Title - summary.md); MoveFromConfluence гарантирует коррект парсинг Markdown и конвертацию в Confluence Storage Format.
- **Независимость:** синхронизация задач (из страниц Confluence) и публикация summary (из встреч FF) — два разных потока, не пересекаются.

### MoveFromJira (проекты)
- **MoveFromConfluence** хранит `project` (code,例: OKRS-Q2, DEV-BUGS) в YAML frontmatter.
- **Резолв project → реальный проект в Jira** — задача downstream-инструментов (не входит в scope MoveFromConfluence).

### Обобщённый контракт
- **MoveFromConfluence** гарантирует: корректный парсинг задач из Confluence и двусторонний синк в .md.
- **Другие инструменты** (MarkObjectsFromSummary, custom скрипты) могут использовать `{WORKVAULT_PATH}/Tasks/` как источник истины для задач.
- **Резолв контактов и проектов** — задача downstream-инструментов или MoveFromExchange + MoveFromJira.

---

## Статус и следующие шаги

**Дата:** 2026-05-23 → обновлено 2026-05-25 (Keycloak SSO)  
**Статус:** На согласовании. **ТРЕБУЕТ ОБНОВЛЕНИЯ АВТОРИЗАЦИИ (v1.1).**

**⚠️ Критическое изменение (2026-05-25): Confluence/Jira переехали на Keycloak SSO**

- **Проблема:** Personal Access Token (PAT) **больше не работает** через REST API.
- **Текущий статус:** REST API v2 недоступен через PAT-авторизацию.
- **Решение:** требуется переход на Keycloak SSO для авторизации.
- **Влияние на MoveFromConfluence v1.0:**
  - Чтение задач из Confluence через REST API — может быть затронуто.
  - Создание задач на странице Confluence — может быть затронуто.
  - **Решение:** рассчитано на v1.1 ТЗ с обновленной авторизацией (Keycloak OAuth2 или браузерный session).

**Для текущих разработок v1.0:**
- Гарантирует работоспособность синхронизации задач **в домене ТУТУ (через браузер или при наличии активного session)**.
- PAT-токены — временное решение до миграции на Keycloak.
- При развёртывании v1.0 в production рекомендуется приготовиться к миграции авторизации на Keycloak.

**Предусмотрены для v1.1+ (out of scope v1.0):**
- Обновление авторизации для Confluence REST API (переход с PAT на Keycloak SSO).
- Синхронизация вложений (файлов, ссылок) в задачах.
- Создание подзадач в Confluence.
- Интеграция с MoveFromJira для резолва project → проект в Jira.
- Web-интерфейс для управления списком страниц и просмотра задач.
- История статусов (audit log).
