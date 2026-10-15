---
tool: ConfluenceSync
version: "1.0.1"
date: 2026-08-29
status: active
---

# ConfluenceSync — двусторонняя синхронизация страниц Confluence ↔ Obsidian (WorkVault)

## Контракты экосистемы

### Источник истины
- Владелец первичных страниц Confluence: `api_confluence` (Confluence REST API `https://conf.tutu.ru`)
- Владелец локальных MD-страниц: ConfluenceSync (`WorkVault/Confluence/<Space>/<Page>/index.md`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| confluence_id | str | required | api_confluence | ID страницы Confluence |
| title | str | required | api_confluence | Название страницы |
| space | str | required | api_confluence | Ключ пространства (Space key) |
| body.storage.value | str | required | api_confluence | Storage XHTML format |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| confluence_id | str | api_confluence | ID создаваемой/обновляемой страницы Confluence |
| title | str | api_confluence | Заголовок страницы Confluence |
| space | str | api_confluence | Ключ пространства (Space key) |
| body.storage.value | str | api_confluence | Confluence storage XHTML format |

### Зависимости
- Получает от: [api_confluence]
- Отдаёт: [api_confluence]

### Breaking changes policy
- Версионирование формата: frontmatter `index.md` и REST API Confluence Server/Data Center (on-prem)
- При breaking change API Confluence: адаптация REST-клиента в `confluencesync/confluence_client.py`

### Границы («что НЕ трогать»)
- Не менять структуру папок `WorkVault/Confluence/<Space>/<Page>/index.md` без обновления `vault_store.py`
- Не удалять страницы в Confluence при локальном удалении файлов
- Не перезаписывать существующие файлы при `pull` без флага `--resync`

## Обзор

`ConfluenceSync` — инструмент в составе `USERTOOLS/`, обеспечивающий:

- **Чтение** страниц Confluence (с дочерними рекурсивно) и сохранение их как Markdown-файлов в локальный Obsidian-vault (`WorkVault/Confluence/<Space>/<Page>/index.md`).
- **Выдачу контента в stdout** для подачи в контекст агента (без записи на диск).
- **Запись** изменённых/новых Markdown-страниц обратно в Confluence (обновление существующих по `confluence_id`, создание новых подстраниц от указанного родителя).
- **Использование как библиотеки** другими инструментами (`MoveFromFF`, `MoveFromZulip`, `MoveFromExchange` и пр.) — программное API + флаг `confirm=False`.

Аналог по архитектуре: `MoveFromZulip` (CLI через `click`, pip install -e, пакет Python).
Общая инфраструктура (лок, логирование, settings, .env): паттерны из `AnywhereContacts`.

Confluence: on-prem (Server/Data Center) — `https://conf.tutu.ru`. API: REST `/rest/api/content`, Bearer-токен.

---

## Use Cases

### UC-1: «Прочитай и сделай»
Пользователь даёт ссылку на страницу Confluence с инструкцией (например, «настрой dev-окружение»). Агент (Сирень) вызывает ConfluenceSync с `--to-context`, получает MD-контент в stdout, передаёт Opus, тот выполняет инструкцию. **Файл не пишется.**

### UC-2: «Встретил ссылку — обогати»
Другой инструмент (MoveFromFF, MoveFromZulip, MoveFromExchange) при обработке сущности (задачи, встречи, контакта) встречает ссылку на Confluence. Вызывает ConfluenceSync в режиме `--to-file` → страница сохраняется в `WorkVault/Confluence/...`, путь возвращается вызывающему инструменту для вставки ссылки рядом с сущностью.

### UC-3: Автообновление от другого инструмента
Инструмент программно вызывает `ConfluenceSync.push(page_id, content, confirm=False)` — обновление без подтверждения пользователя. Используется в пайплайнах (например, после генерации отчёта).

### UC-4: Ручной ре-синк
Пользователь явно запрашивает обновление дерева страниц (`--resync`). Без явного запроса локальные файлы не перезаписываются.

### UC-5: Push изменений из vault в Confluence
Пользователь правит `index.md` в WorkVault. Командой `confluencesync push <path>` инструмент читает frontmatter, берёт `confluence_id` и заливает изменения. Если `confluence_id` отсутствует — создаёт новую подстраницу от `parent` (тоже из frontmatter).

---

## Архитектура

```
                       ┌────────────────────────┐
                       │   CLI (click)          │
                       │   __main__.py          │
                       └─────────┬──────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
       ┌────────────┐    ┌────────────────┐  ┌──────────────┐
       │ pull       │    │ push           │  │ resync       │
       │ (Conf→MD)  │    │ (MD→Conf)      │  │ (refresh)    │
       └─────┬──────┘    └───────┬────────┘  └──────┬───────┘
             │                   │                  │
             └─────────┬─────────┴──────────────────┘
                       ▼
              ┌──────────────────┐
              │  confluence_     │  REST API клиент (atlassian-python-api
              │  client.py       │  или requests напрямую)
              └────────┬─────────┘
                       │
       ┌───────────────┼───────────────────┐
       ▼               ▼                   ▼
  ┌─────────┐   ┌──────────────┐   ┌────────────────┐
  │ converter│  │ vault_store  │   │ logger (JSONL) │
  │ HTML↔MD  │  │ FS layout    │   │ _sync_log.jsonl│
  │ + macros │  │ + frontmatter│   │                │
  └─────────┘   └──────────────┘   └────────────────┘
```

### Поток pull (Confluence → WorkVault)
1. CLI принимает URL/page_id страницы.
2. `confluence_client.get_page(id, expand=body.storage,version,ancestors,children.page,metadata,space)`.
3. Рекурсивно по дочерним (BFS).
4. Для каждой страницы:
   - `converter.html_to_md()` — Confluence storage XHTML → Markdown.
   - Получить комментарии (`/content/{id}/child/comment`), вложения (`/content/{id}/child/attachment`) — только метаданные.
   - Собрать frontmatter.
   - Записать в `vault_store` (`--to-file` или `--to-both`) и/или вернуть строку (`--to-context` или `--to-both`).
5. Залогировать в JSONL.

### Поток push (WorkVault → Confluence)
1. Прочитать MD-файл, распарсить frontmatter.
2. `converter.md_to_html()` — Markdown → Confluence storage XHTML.
3. Если есть `confluence_id` → `PUT /content/{id}` (с инкрементом version).
4. Если нет → `POST /content` под `parent`.
5. Спросить подтверждение (если `confirm=True`), показать diff.
6. Обновить frontmatter (`synced_at`, `last_modified`, новый `confluence_id` при create).

---

## CLI интерфейс

```bash
# Чтение страницы и поддерева в файлы
confluencesync pull <url-or-id> [--to-file|--to-context|--to-both]
                                [--depth N|--no-recursive]
                                [--resync]

# Запись локальной MD-страницы обратно
confluencesync push <path-to-md> [--no-confirm]

# Ре-синк уже сохранённого дерева (по корневому index.md или page_id)
confluencesync resync <path-or-id>

# Просмотр лога
confluencesync log [--tail N] [--operation pull|push|error]
```

Флаги:

| Флаг             | По умолч. | Описание                                                       |
|------------------|-----------|----------------------------------------------------------------|
| `--to-file`      | да        | Сохранить в `WorkVault/Confluence/...`                         |
| `--to-context`   | нет       | Только stdout (для агента)                                     |
| `--to-both`      | нет       | И файл, и stdout                                               |
| `--depth N`      | ∞         | Глубина рекурсии по дочерним                                   |
| `--no-recursive` | —         | Только указанная страница                                      |
| `--resync`       | нет       | Разрешить перезапись существующих локальных файлов             |
| `--no-confirm`   | —         | (push) не спрашивать подтверждения                             |
| `--dry-run`      | нет       | Не писать ни в файл, ни в Confluence — только показать план    |

### Программный API (для других инструментов)

```python
from confluencesync import ConfluenceSync

cs = ConfluenceSync()  # читает .env из MoveFromExchange

# Pull в файл, возвращает путь
path = cs.pull(page_id="123", to="file")

# Pull в строку (контекст агента)
md = cs.pull(url="https://conf.tutu.ru/display/SPACE/Page", to="context")

# Push без подтверждения
cs.push(md_path="path/to/index.md", confirm=False)

# Push новой страницы под родителя
cs.push_new(parent_id="456", title="...", content_md="...", confirm=False)
```

---

## Модули и их ответственность

### `confluencesync/__init__.py`
Экспорт класса `ConfluenceSync` (фасад API), версия.

### `confluencesync/__main__.py`
CLI на `click`. Команды: `pull`, `push`, `resync`, `log`. Парсинг URL → page_id. Маршрутизация в `sync.py`.

### `confluencesync/config.py`
- Загрузка `.env` из `USERTOOLS/MoveFromExchange/.env` (приоритет) и из локального `.env`.
- Поля: `CONFLUENCE_URL`, `CONFLUENCE_TOKEN`, `WORKVAULT_PATH` (default `C:\Users\tkachenkoav\WorkVault`).
- Settings-объект (pydantic или dataclass — как в `AnywhereContacts/settings.py`).

### `confluencesync/confluence_client.py`
- Тонкий клиент REST API: `get_page`, `get_children`, `get_comments`, `get_attachments`, `update_page`, `create_page`.
- Авторизация: `Bearer ${CONFLUENCE_TOKEN}`.
- Retry на 429/5xx (3 попытки, экспоненциальный backoff).
- Парсинг URL Confluence → page_id (поддержка `/display/SPACE/Title`, `/pages/viewpage.action?pageId=...`, `/spaces/SPACE/pages/ID/...`).

### `confluencesync/converter.py`
- `html_to_md(storage_xhtml) -> str`: парсит Confluence storage format (XHTML + `<ac:*>`/`<ri:*>` макросы).
  - Базовый текст: через `markdownify` или `html2text` + постобработка.
  - Макросы:
    - `<ac:structured-macro ac:name="info">` → `> [!info]`
    - `name="warning"` → `> [!warning]`
    - `name="note"` → `> [!note]`
    - `name="tip"` → `> [!tip]`
    - `name="code"` → ```` ```lang ... ``` ````
    - `name="expand"` → `<details><summary>…</summary>…</details>`
    - `name="toc"` → пропустить
    - Прочие → fallback: `> [!info] <macro-name>\n> <inner text>`
  - Изображения `<ac:image>` → `📎 [рисунок](<confluence-page-url>#image-N)` (без скачивания).
  - Вложения `<ri:attachment>` → `📎 [<filename>](<confluence-download-url>)`.
  - Ссылки `<ac:link>`:
    - На страницу в дереве → относительная ссылка `[[<title>]]` (Obsidian wiki-link).
    - Вне дерева → `🔗 [<title>](<url>)`.
- `md_to_html(md) -> str`: обратный конвертер.
  - Markdown → HTML (через `markdown` пакет).
  - Obsidian callouts `> [!info]` → `<ac:structured-macro ac:name="info">`.
  - Code fences → `<ac:structured-macro ac:name="code">`.

### `confluencesync/vault_store.py`
- Пути: `WorkVault/Confluence/<sanitized-space-key>/<sanitized-title>/index.md`.
- Дочерние страницы: подпапки от родителя.
- Санитизация имён (Windows-safe: убрать `<>:"/\|?*`, обрезать до 80 символов).
- Frontmatter (YAML):
  ```yaml
  ---
  confluence_id: "123456"
  title: "Название страницы"
  confluence_url: "https://conf.tutu.ru/pages/viewpage.action?pageId=123456"
  space: "SPACE"
  parent: "111111"           # confluence_id родителя (или null)
  children: ["222", "333"]   # confluence_id дочерних
  author: "ivanov"
  last_modified: "2026-05-28T10:00:00Z"  # из Confluence (version.when)
  synced_at: "2026-05-28T21:35:00Z"      # время локальной синхронизации
  ---
  ```
- Методы: `write(page_meta, md_body, overwrite=False)`, `read(path)`, `find_by_id(confluence_id)`, `path_for(space, title, parent_path)`.

### `confluencesync/sync.py`
- Оркестратор pull/push/resync.
- BFS по дереву страниц с учётом `--depth` / `--no-recursive`.
- Логика `--resync`: при существующем файле без флага — пропустить (залогировать `status=skipped_exists`).
- Сборка путей с учётом иерархии родителей.

### `confluencesync/logger.py`
- JSONL-логгер. Путь: `WorkVault/_meta/ConfluenceSync/_sync_log.jsonl`.
- Запись:
  ```json
  {"ts":"2026-05-28T21:35:00Z","op":"pull","page_id":"123","title":"...",
   "status":"ok","details":{"path":"...","bytes":1234}}
  ```
- Операции: `pull`, `push`, `create`, `update`, `skip`, `error`.
- Статусы: `ok`, `skipped_exists`, `skipped_unchanged`, `error`, `dry_run`.

### `confluencesync/lock.py`
- Файловый лок на `WorkVault/_meta/ConfluenceSync/.lock` (как `AnywhereContacts/lock.py`).
- Защищает от параллельных pull/push в один и тот же vault.

### `confluencesync/url_utils.py`
- Парсинг URL Confluence → `(space_key, page_id, title)`.

---

## Структура проекта

```
USERTOOLS/ConfluenceSync/
├── TZ.md                              ← этот файл
├── README.md                          ← краткое how-to (после реализации)
├── pyproject.toml                     ← пакет, deps, entry_point=confluencesync
├── .env.example                       ← шаблон, реальный .env лежит в MoveFromExchange/
├── confluencesync/
│   ├── __init__.py                    ← фасад ConfluenceSync, __version__
│   ├── __main__.py                    ← click CLI (pull/push/resync/log)
│   ├── config.py                      ← загрузка .env, Settings
│   ├── confluence_client.py           ← REST-клиент Confluence
│   ├── converter.py                   ← html_to_md, md_to_html, макросы
│   ├── vault_store.py                 ← FS layout, frontmatter
│   ├── sync.py                        ← оркестратор pull/push/resync
│   ├── url_utils.py                   ← парсинг URL Confluence
│   ├── logger.py                      ← JSONL логгер
│   └── lock.py                        ← файловый лок
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    ← фикстуры: tmp vault, mock client
│   ├── fixtures/
│   │   ├── page_simple.xml            ← пример storage XHTML
│   │   ├── page_with_macros.xml
│   │   └── page_with_children.json
│   ├── test_url_utils.py              ← парсинг разных форматов URL
│   ├── test_converter_html_to_md.py   ← макросы, callouts, ссылки, картинки
│   ├── test_converter_md_to_html.py   ← обратный конвертер
│   ├── test_vault_store.py            ← пути, санитизация, frontmatter
│   ├── test_sync_pull.py              ← mock client, проверка дерева
│   ├── test_sync_push.py              ← mock client, create/update
│   ├── test_logger.py                 ← JSONL формат
│   ├── test_cli.py                    ← click CliRunner
│   └── test_integration_smoke.py      ← реальный Confluence, marked @pytest.mark.integration
└── скилл (отдельно, в ~/.hermes/skills/movefrom-confluence/):
    └── SKILL.md                        ← инструкция для агента, когда вызывать инструмент
```

---

## Тесты

### Unit (без сети, моки)
- `test_url_utils.py`: парсинг 4+ форматов URL Confluence → `page_id`.
- `test_converter_html_to_md.py`:
  - Простой текст и форматирование.
  - Все поддерживаемые макросы → callouts.
  - Изображения → пометка `📎 [рисунок](...)`.
  - Внешние ссылки → `🔗 [..](..)`.
  - Внутренние ссылки → `[[..]]`.
- `test_converter_md_to_html.py`: round-trip для базовых случаев (MD → HTML → MD дает эквивалент).
- `test_vault_store.py`: формирование пути, санитизация Windows-имён, чтение/запись frontmatter.
- `test_sync_pull.py`: на моке клиента — BFS по дереву, `--depth`, `--no-recursive`, `--resync`.
- `test_sync_push.py`: на моке — update по `confluence_id`, create под `parent`, инкремент `version`.
- `test_logger.py`: формат JSONL, типы полей, ротация (если будет).
- `test_cli.py`: `click.testing.CliRunner` для всех команд, проверка кодов выхода и stdout.

### Integration (smoke)
- `test_integration_smoke.py` — маркер `@pytest.mark.integration`, запускается отдельно (`pytest -m integration`).
- Использует реальную **тестовую** страницу Confluence (`CONFLUENCE_TEST_PAGE_ID` в `.env`).
- Сценарий: pull → push (с правкой) → pull → проверка, что правка применилась → откат.

### Запуск
```bash
pytest                              # unit
pytest -m integration               # smoke
pytest --cov=confluencesync         # покрытие
```

---

## Открытые вопросы

1. **Cloud vs Server API.** ТЗ исходит из on-prem (`conf.tutu.ru`). Если когда-то понадобится Cloud — у него отличающийся auth (email+API token) и слегка иной формат content endpoints. Сейчас не закладываем, но клиент стоит сделать через тонкий интерфейс, чтобы заменить было дёшево.
2. **Конфликты при push.** Что делать, если на сервере страница изменилась с момента pull (version mismatch)? Предлагаемое поведение: блокировать push, показать сообщение «remote changed since pull, do --resync first». Подтвердить.
3. **Вложения-файлы.** Сейчас не скачиваем, только ссылки. Может, в будущем добавить флаг `--with-attachments` для скачивания в `WorkVault/Confluence/<...>/_attachments/`.
4. **Двунаправленность wiki-ссылок.** При push `[[Title]]` нужно резолвить обратно в `<ac:link><ri:page ri:content-title="Title"/></ac:link>`. Если страница с таким title не найдена в Space — оставлять как plain text? Залогировать warning.
5. **Лимиты Confluence.** Большие body (>5MB) могут получаться при больших страницах — есть ли смысл стримить или хранить как есть?
6. **Скилл `movefrom-confluence`.** SKILL.md как отдельная задача — описывает агенту триггеры использования (ссылка на conf.tutu.ru в сообщении пользователя → автозапуск pull `--to-context`).

---

## Полный список файлов для создания

### Корень пакета
1. `USERTOOLS/ConfluenceSync/TZ.md` *(этот файл — создан)*
2. `USERTOOLS/ConfluenceSync/README.md`
3. `USERTOOLS/ConfluenceSync/pyproject.toml`
4. `USERTOOLS/ConfluenceSync/.env.example`

### Пакет `confluencesync/`
5. `confluencesync/__init__.py`
6. `confluencesync/__main__.py`
7. `confluencesync/config.py`
8. `confluencesync/confluence_client.py`
9. `confluencesync/converter.py`
10. `confluencesync/vault_store.py`
11. `confluencesync/sync.py`
12. `confluencesync/url_utils.py`
13. `confluencesync/logger.py`
14. `confluencesync/lock.py`

### Тесты `tests/`
15. `tests/__init__.py`
16. `tests/conftest.py`
17. `tests/fixtures/page_simple.xml`
18. `tests/fixtures/page_with_macros.xml`
19. `tests/fixtures/page_with_children.json`
20. `tests/test_url_utils.py`
21. `tests/test_converter_html_to_md.py`
22. `tests/test_converter_md_to_html.py`
23. `tests/test_vault_store.py`
24. `tests/test_sync_pull.py`
25. `tests/test_sync_push.py`
26. `tests/test_logger.py`
27. `tests/test_cli.py`
28. `tests/test_integration_smoke.py`

### Скилл (отдельная директория, вне пакета)
29. `~/.hermes/skills/movefrom-confluence/SKILL.md`

**Итого: 29 файлов** (включая этот TZ.md).
