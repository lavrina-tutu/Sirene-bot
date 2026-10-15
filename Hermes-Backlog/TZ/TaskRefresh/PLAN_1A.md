---
tool: TaskRefresh
doc: Блок 1А — пофайловый план реализации
version: 1.0
date: 2026-07-13
author: Opus
source-of-truth: ./TaskRefresh_TZ.md (v1.0, status=active, §12 — финальные решения по Q-1…Q-12)
---

# TaskRefresh — Блок 1А. Пофайловый план реализации

Основано на ТЗ v1.0 (все 12 Q брифа закрыты §12). Код — Sonnet, отдельным следующим
шагом. Здесь только план: структура пакета, файлы, сигнатуры, тесты, критерии
завершения этапов.

## 0. Принятые допущения (техническая неопределённость вне уже решённых Q)

Ниже — консервативные решения, принятые Opus'ом самостоятельно; каждое ≤3 строк.

**A-1. Реестр pageId ↔ slug ↔ project_tag.** Выносим в отдельный JSON-файл
`WorkVault/Tools/TaskRefresh/project_registry.json`, инициализируем ровно строками
таблицы §1.3 `ProtocolFromSummary_TZ.md`. В шапке модуля `project_registry.py` —
комментарий «источник истины — PFS §1.3, обновлять вручную при расхождении».
Программного парсинга markdown-таблицы PFS не делаем (лишняя связность, PFS-таблица
редко меняется). Причина консервативного выбора: JSON проще диффать/чинить руками
и он идентичен по семантике таблице; парсер PFS.md — риск сломаться от разметки.

**A-2. Механизм состояния сессии между репликами диалога.** Единственный
файл-снапшот `WorkVault/Tools/TaskRefresh/session/current.json`, перезаписывается
на каждый успешный READ. Содержит: timestamp, фильтры запроса, полный
JSON-массив объектов задач (см. ТЗ §4.1) с сохранённым порядком нумерации `#N`,
которую Сирень показала Саше. TTL мягкий — 24 часа (при попытке WRITE с
`current.json` старше 24ч выводится предупреждение и предлагается перезапустить
READ). Одновременных сессий нет (`current.json` один, диалог у Саши один). Также
кладём копии в `session/history/<timestamp>.json` для аудита (без ротации в MVP).

**A-3. Точка входа и интерфейс.** TaskRefresh — Python-пакет с CLI (`python -m
taskrefresh …`), но основной пользовательский путь — вызов Сиренью через
skill/tool-wrapper, который просто вызывает функции пакета напрямую (без
subprocess). CLI-режим — для отладки и ручного запуска. Три сабкоманды: `read`
(фильтры → показ + сохранение session), `apply` (список изменений → показ
было→станет + подтверждение → PUT), `show` (перепечатать last session без нового
GET).

**A-4. Фильтрация F4 (дата создания) для страниц без табличной структуры.**
Определяем «табличную структуру» так: `<ac:task>` физически лежит внутри `<tr>`
(любой глубины вложенности), и первая `<td>` этого `<tr>` содержит распарсиваемую
дату (ISO/DD.MM.YYYY/DD.MM/дата с русским месяцем). Если структура не такая —
у задачи `meeting_date = null`. При активном фильтре F4 такие задачи молча из
результата НЕ выкидываются: в брифе явно показывается блок «Исключены из F4
(нет даты в строке): N задач с M страниц» с перечнем страниц (см. §12 ТЗ,
«прозрачность»).

**A-5. Парсинг даты первой колонки.** Отдельный модуль `date_parse.py` c набором
regex/локалей (русские месяцы, DD.MM, DD.MM.YYYY, YYYY-MM-DD, DD.MM.YY). Если
несколько дат в одной ячейке — берём первую. Если ни одна не парсится — `null`
и попадание в «Исключены из F4».

**A-6. Пересборка блока `<ac:task>` (Q-5).** Через `lxml.etree` парсим сам блок
как фрагмент (обёрнутый в фиктивный root с деклариями `ac:`/`ri:` неймспейсов),
меняем нужные атрибуты/элементы, сериализуем обратно (`tostring`), убираем
фиктивный root. В storage_html страницы — `str.replace(old_block, new_block, 1)`
(count=1 — защита от гипотетических дубликатов; при 0 замен = задача исчезла,
graceful degradation). Соседний XML не трогается.

**A-7. Матч задачи в storage_html при PUT.** По `ac:task-id` в свежем GET
находим блок регуляркой `<ac:task>\s*<ac:task-id>ID</ac:task-id>.*?</ac:task>`
(нежадная, `re.DOTALL`). Один матч → работаем, ноль → «not-found, пропуск»,
>1 → тревога в лог (не должно случаться, `ac:task-id` уникален на страницу).

**A-8. Retry при 409.** Один повтор: свежий GET → пересборка нового блока
(старый блок мог измениться) → PUT. Если снова 409 — «conflict, отложено», лог
+ бриф. Реализация — в `write_ops.py`, простая обёртка вокруг update_page.

**A-9. Матч проекта (F2).** Двумя стратегиями (OR): (a) `source_page_id ∈
registry[slug].pageIds`; (b) `text_clean.startswith(registry[slug].tag)`.
Тег регистронезависимо. Пресеты — по ключам реестра (`Trisigma`, `AI-ready`, …).

**A-10. Резолв нового исполнителя.** Импортируем `ContactStore` из
`anywherecontacts` и функции `find_user_by_fullname` / `find_user_by_key` из
`protocolfromsummary.confluence_ext` — НЕ копируем логику. Тонкая обёртка
`resolve_assignee(raw) -> (userkey|None, display|None)` возвращает `(None, raw)`
при неудаче (Q-9: оставляем текстом).

## 1. Структура пакета

Аналогично `USERTOOLS/ProtocolFromSummary/protocolfromsummary/`:

```
USERTOOLS/TaskRefresh/
├── pyproject.toml
├── README.md
├── taskrefresh/
│   ├── __init__.py
│   ├── __main__.py           # CLI entry (argparse: read / apply / show)
│   ├── config.py             # пути, TTL, дефолты, ENV
│   ├── logger.py             # общий формат логов (совместим с PFS/CS)
│   ├── project_registry.py   # загрузка project_registry.json, матч slug/tag/pageId
│   ├── confluence_scan.py    # CQL label="_aid" → список pageId (Q-1, живой)
│   ├── page_reader.py        # GET страницы + извлечение всех <ac:task> через lxml
│   ├── task_model.py         # dataclass Task (поля из §4.1 ТЗ) + serialize/deserialize
│   ├── date_parse.py         # парсинг дат из первого <td> (A-5) + F3-пресеты
│   ├── filters.py            # F1-F6 применение к списку Task (комбинация И)
│   ├── contacts_resolver.py  # ТОНКАЯ обёртка над PFS/AnywhereContacts (A-10)
│   ├── formatter.py          # форматирование брифа: группировка/сортировка/номера (Q-6)
│   ├── session_store.py      # save/load current.json + history (A-2)
│   ├── task_block.py         # lxml пересборка одного <ac:task> (A-6)
│   ├── write_ops.py          # применение W1/W2/W3 к странице, retry 409 (A-7/A-8)
│   ├── pipeline.py           # верхнеуровневые run_read / run_apply / run_show
│   └── change_spec.py        # парсинг команды Саши "#3 дедлайн 20.07" → ChangeSpec
└── tests/
    ├── conftest.py
    ├── fixtures/             # sample storage_html, sample CQL responses, sample tasks
    ├── test_project_registry.py
    ├── test_confluence_scan.py
    ├── test_page_reader.py
    ├── test_date_parse.py
    ├── test_filters.py
    ├── test_contacts_resolver.py
    ├── test_formatter.py
    ├── test_session_store.py
    ├── test_task_block.py
    ├── test_write_ops.py
    ├── test_change_spec.py
    └── test_pipeline_e2e.py  # интеграционный, mocked ConfluenceClient
```

Runtime-vault:

```
WorkVault/Tools/TaskRefresh/
├── project_registry.json           # A-1 (source of truth §1.3 PFS)
├── config.yml                      # опциональные runtime-настройки, стартово почти пустой
├── session/
│   ├── current.json                # A-2, последняя READ-сессия
│   └── history/<timestamp>.json    # аудит
└── logs/
    └── ops-YYYY-MM.log             # append-only, formatter §6.8 ТЗ (audit trail)
```

---

## 2. Пофайловый план

### 2.1 `taskrefresh/config.py`
- Константы: `VAULT_ROOT`, `PROJECT_REGISTRY_PATH`, `SESSION_PATH`, `HISTORY_DIR`,
  `LOG_DIR`, `SESSION_TTL_HOURS=24`, `CQL_LABEL="_aid"`.
- `load_runtime_config() -> dict` — читает `config.yml` (yaml, опциональный).
- ENV: `CONFLUENCE_BASE_URL`, `CONFLUENCE_TOKEN` (те же, что использует PFS).
- **Тесты (test_config.py — включим в conftest, отдельного файла не заводим):**
  smoke — модуль импортируется, пути существуют/создаются.
- **Точка проверки:** `python -c "from taskrefresh import config; print(config.VAULT_ROOT)"`
  печатает путь без ошибки.

### 2.2 `taskrefresh/logger.py`
- `get_logger(name) -> logging.Logger` — тот же формат, что PFS/CS.
- Отдельный audit-логгер `get_audit_logger()` пишет в `logs/ops-YYYY-MM.log`
  структурированные строки (JSON per-line) по требованию §6.8 ТЗ.
- **Тест:** logger пишет ожидаемую строку в tmp-файл.

### 2.3 `taskrefresh/project_registry.py`
- `class ProjectRegistry: load() / match_by_page_id(pid) / match_by_text(text)
  / list_slugs() / lookup(slug)`.
- Формат JSON: `{"Trisigma": {"pageIds":[490170597], "tag":"Trisigma."}, ...}`.
- Комментарий в шапке модуля: «источник — PFS §1.3, обновлять вручную».
- **Тесты (`test_project_registry.py`):**
  1. load из фикстурного JSON;
  2. match_by_page_id находит slug для 490170597 → Trisigma;
  3. match_by_text «Trisigma. Собрать таймлайн» → Trisigma;
  4. регистронезависимость тега;
  5. текст без известного тега → None.
- **Точка проверки:** unit-тесты зелёные.

### 2.4 `taskrefresh/confluence_scan.py`
- `scan_pages(client) -> list[dict]` — вызывает `client._req("GET",
  "/rest/api/content/search", params={"cql": 'label="_aid"', "limit": 200,
  "expand": "space"})`, пагинация по `_links.next` пока есть.
- Возвращает список dict `{pageId, title, spaceKey}`, БЕЗ фильтра по space
  (Q-1). Живой каждый вызов, ничего не кэширует.
- **Тесты (`test_confluence_scan.py`):**
  1. одна страница CQL-результата → корректный dict;
  2. пагинация в 2 страницы объединяется;
  3. пустой ответ → пустой список.
- **Точка проверки:** реальный smoke на VM Саши (staging-safe: только GET) —
  число страниц ≥ 30 (сейчас 35).

### 2.5 `taskrefresh/task_model.py`
- `@dataclass Task` с полями §4.1 ТЗ (13 полей).
- `Task.from_storage(block_xml, page_meta, tr_first_td_text) -> Task` — конструирует
  задачу из блока `<ac:task>` и контекста строки.
- `to_dict/from_dict` для сериализации сессии.
- **Тесты:** round-trip dict, from_storage на минимальном фикстурном блоке.

### 2.6 `taskrefresh/page_reader.py`
- `read_page_tasks(client, page_id) -> tuple[int, list[Task]]` — GET страницы
  (`expand=body.storage,version,title,space`), lxml-парсинг storage_html,
  сбор всех `<ac:task>`, для каждой — определение `<tr>` предка (если есть)
  и текста первой `<td>`, конструкция Task, добавление `page_version_at_read`.
- Возвращает (version, tasks).
- **Тесты (`test_page_reader.py`):**
  1. страница с 3 задачами в таблице «Дата | Задачи» → правильные meeting_date;
  2. страница с задачами в плоском списке → meeting_date=null;
  3. задача с mention resolves в userkey;
  4. задача без `<time>` → deadline=null;
  5. задача с несколькими `<time>` → берём первую (лог warning).
- **Точка проверки:** offline тесты на реальном storage-fragment’е OpenTasks
  (сохранить в fixtures/) — извлекаем 27 incomplete Саши по фильтру.

### 2.7 `taskrefresh/date_parse.py`
- `parse_first_td_date(td_text) -> date|None` — locale-aware (русские месяцы),
  A-5.
- `resolve_f3_preset(preset_str, today) -> (date_from, date_to)` — реализация
  всех пресетов Q-3: `overdue`, `no-deadline`, `today`, `tomorrow`, `this-week`
  (пн-вс от today), `next-week`, `next-N-days`, диапазон `YYYY-MM-DD..YYYY-MM-DD`,
  точная дата `YYYY-MM-DD`. Возвращает `(None,None)` для маркёров типа
  `no-deadline`, спец. sentinel — интерпретируется filters.py.
- `parse_time_deadline(time_str) -> date|None`.
- **Тесты (`test_date_parse.py`):**
  1. «10.07.2026», «10.07», «10 июля 2026», «2026-07-10» — все → 2026-07-10;
  2. «не дата» → None;
  3. `this-week` при today=среда 2026-07-15 → (2026-07-13, 2026-07-19);
  4. `next-N-days` N=3 today=2026-07-15 → (2026-07-15, 2026-07-18);
  5. диапазон парсится;
  6. `overdue` возвращает специальный маркёр (deadline<today AND incomplete).

### 2.8 `taskrefresh/filters.py`
- `class TaskFilter` собирает F1-F6 из аргументов.
- `TaskFilter.apply(tasks: list[Task]) -> FilterResult` где
  `FilterResult = {kept: list[Task], excluded_no_meeting_date: list[Task]}` —
  для явного показа в брифе (A-4, «прозрачность»).
- **Тесты (`test_filters.py`):**
  1. F5 default incomplete;
  2. F1 (userkey) единичный, F1 множественный OR;
  3. F2 матч по pageId, F2 матч по тегу, F2 отсутствие проекта;
  4. F3 overdue (сегодня 2026-07-13, задача с 2026-07-10 incomplete → in);
  5. F3 no-deadline;
  6. F3 next-7-days;
  7. F3 диапазон;
  8. F4 today (табличная страница);
  9. F4 при активном фильтре собирает excluded_no_meeting_date;
  10. F6 whitelist/blacklist pageId;
  11. **комбинация F1+F2+F3** одновременно;
  12. **комбинация F1+F3+F4** с страницами и с и без даты.

### 2.9 `taskrefresh/contacts_resolver.py`
- Тонкая обёртка (A-10):
  - `resolve_display(userkey) -> str|None` — обратный резолв через `contacts.enc`;
  - `resolve_assignee(raw) -> tuple[str|None, str]` — использует
    `protocolfromsummary.contacts_resolver._resolve_one` через `store`/`confluence`
    (импорт готовый). Возвращает `(userkey_or_None, display_string)`.
- **Тесты (`test_contacts_resolver.py`):**
  1. известное ФИО → userkey;
  2. неизвестное → (None, raw) без исключений (Q-9);
  3. обратный резолв userkey → ФИО из contacts.enc;
  4. mocked ContactStore, реальный сетевой Confluence НЕ дёргается.

### 2.10 `taskrefresh/formatter.py`
- `format_brief(tasks: list[Task], excluded: list[Task]|None) -> str`:
  - группировка по `project_tag` (пусто → «Без проекта»);
  - внутри группы сортировка: сначала overdue (deadline<today), затем по deadline
    возрастающе, `no-deadline` последними;
  - нумерация сквозная `#1..#N`;
  - формат строки: `#N. [Проект] «текст» — исполн: Ф.И.О. — дедлайн: 20.07`
    (или «нет»);
  - блок «Исключены из F4 (нет даты в строке): N задач с M страниц» с
    перечислением страниц (когда `excluded` непусто, только при активном F4);
  - Q-6 требование: цифровая нумерация, не буквы (это касается и подсписков).
- `format_change_preview(specs: list[ChangeSpec]) -> str` — точный формат Q-7:
  ```
  Подтверди изменения (N задач):
  1. [Проект] "текст задачи" — было ДД.ММ → станет ДД.ММ
  2. ...
  ```
  (для W2/W1 — соответственно «было исполнитель X → станет Y», «было текст ... → станет ...»).
- **Тесты (`test_formatter.py`):**
  1. 5 задач из 3 проектов → 3 группы, сортировка внутри;
  2. overdue первыми;
  3. no-deadline последними;
  4. excluded-блок появляется при F4 и содержит перечень страниц;
  5. `format_change_preview` для W3 даёт формат ровно как в Q-7;
  6. `format_change_preview` для смеси W1+W2+W3 в одной пачке;
  7. пустой список — сообщение «задач по фильтрам не найдено».

### 2.11 `taskrefresh/session_store.py`
- `save_session(request_filters, tasks) -> Path` (пишет current.json + history копию).
- `load_session() -> Session|None` (с проверкой TTL — при протухании возвращает
  Session с флагом `stale=True`, не None; решение об использовании — за pipeline).
- `Session.task_by_number(n) -> Task`.
- **Тесты (`test_session_store.py`):**
  1. save→load round-trip;
  2. TTL — stale=True при timestamp старше 24ч;
  3. history-копия создаётся;
  4. task_by_number корректно возвращает по позиции.

### 2.12 `taskrefresh/task_block.py`
- `rebuild_task_block(original_xml: str, *, new_userkey=None, new_deadline=None,
  new_text=None, remove_deadline=False) -> str` — A-6 реализация: lxml, фиктивный
  root с nsmap для `ac:`/`ri:`, точечные правки атрибутов/детей, сериализация,
  возврат ровно `<ac:task>...</ac:task>` строкой.
- Никаких изменений вне указанных параметров. Порядок дочерних элементов task-body
  — сохраняется исходный (mention → текст → time), кроме случая добавления
  отсутствовавшего `<time>` (добавляется в конец task-body).
- **Тесты (`test_task_block.py`):**
  1. смена даты (существовал `<time>`) → в новом блоке только `<time datetime>` изменён,
     остальное побайтно идентично;
  2. добавление даты (не было `<time>`) → появляется в конце task-body;
  3. удаление даты (`remove_deadline=True`) → `<time>` исчезает;
  4. смена userkey mention → атрибут заменён, остальное как было;
  5. смена текста (W1) → mention и `<time>` сохранены bytes-for-bytes;
  6. параллельная смена userkey+deadline одним вызовом;
  7. блок без mention — W2 добавляет mention корректно (или, если новый резолв
     не удался — оставляет текстовое имя без mention: см. Q-9 сценарий);
  8. сериализация не портит русские символы (utf-8).

### 2.13 `taskrefresh/write_ops.py`
- `class ChangeSpec` (в `change_spec.py`, но используется здесь) — что менять.
- `apply_changes(client, specs: list[ChangeSpec]) -> ApplyReport`:
  1. группируем specs по `source_page_id`;
  2. по каждой странице: свежий GET → для каждой spec: найти блок по
     `ac:task-id` регуляркой (A-7) → построить новый блок через
     `rebuild_task_block` → `storage_html.replace(old, new, 1)`;
  3. один PUT на страницу с обновлённым storage_html и version+1;
  4. при 409 — один retry (A-8);
  5. per-task результат в `ApplyReport`: ok / conflict / not_found /
     partial_no_mention (Q-9).
- **Тесты (`test_write_ops.py`), моки ConfluenceClient:**
  1. W3 одиночный, ok;
  2. W2 с успешным резолвом;
  3. **Q-9 сценарий:** W2 с нерезолвленным ФИО — PUT проходит, mention
     без userkey (текст), report помечает partial_no_mention;
  4. W1+W3 пачка на 3 задачи одной страницы → один PUT, три per-task ok;
  5. **пачка на 2 страницы**, 5 задач → два PUT;
  6. **409 на первый PUT → retry с обновлённым GET → ok** (свежий блок,
     свежая version);
  7. **409 дважды подряд → conflict, лог, следующая задача продолжает**;
  8. **задача исчезла между READ и apply** (0 матчей регуляркой) → not_found,
     warning, пропуск, остальные PUT проходят (graceful degradation);
  9. audit-log содержит per-task запись.

### 2.14 `taskrefresh/change_spec.py`
- `parse_change_command(cmd: str, session: Session) -> list[ChangeSpec]` —
  парсит команды Саши:
  - `#3 дедлайн 20.07` / `#3 дедлайн 2026-07-20` / `#3 дедлайн +7д` / `#3 без дедлайна`;
  - `#5,#7,#9 → Кирилл` / `#5,#7 исполнитель Кирилл Криворотов`;
  - `#12 текст: "новый текст"`;
  - `все просроченные +7д` (batch по F3=overdue из текущей сессии);
  - `все #{filter} → Илье` — общий шаблон.
- Возвращает нормализованный список ChangeSpec (по одной на задачу).
- **Тесты (`test_change_spec.py`):**
  1. одиночный `#3 дедлайн 20.07`;
  2. диапазон `#5-#8 дедлайн today`;
  3. batch `все просроченные +7д` → корректный список ChangeSpec из session;
  4. смена исполнителя нескольким `#5,#7,#9 → Кирилл`;
  5. `#12 без дедлайна`;
  6. неизвестный `#N` (за пределами session) → понятная ошибка;
  7. `#N` при stale session → предупреждение.

### 2.15 `taskrefresh/pipeline.py`
- `run_read(filter_args) -> str` — верх: scan → per-page read → filter →
  save_session → format_brief → возврат строки для показа Саше.
- `run_apply(cmd: str) -> str` — load_session → parse_change_command →
  format_change_preview → **возврат превью, ЖДЁМ подтверждения ВНЕ функции**.
- `run_apply_confirmed(specs) -> str` — apply_changes → format отчёт.
- `run_show() -> str` — просто format_brief по last session.

Т.к. это диалоговый инструмент, шаг «ждать подтверждения» лежит на вызывающей
стороне (Сирень/CLI). Pipeline не блокируется на input(). Между preview и
apply в тот же диалог сохраняем `pending_apply.json` в `session/` — второй
короткий файл со списком specs, ждущих подтверждения.

- **Тесты (`test_pipeline_e2e.py`, mocked client):**
  1. полный цикл READ→APPLY(preview)→APPLY(confirmed) на 3 задачах,
     проверка последовательности вызовов клиента (GET-скана, GET-страницы, PUT);
  2. подтверждение через `run_apply_confirmed` действительно вызывает write_ops.

### 2.16 `taskrefresh/__main__.py`
- argparse CLI:
  - `python -m taskrefresh read --assignee ... --project ... --deadline overdue
    --created 2026-07-01..2026-07-13 --status incomplete`;
  - `python -m taskrefresh apply "#3 дедлайн 20.07"` → печатает preview;
  - `python -m taskrefresh confirm` → применяет pending;
  - `python -m taskrefresh show`.
- **Тест:** smoke — `python -m taskrefresh read --help` возвращает 0.

### 2.17 `pyproject.toml`
- Зависимости: `lxml`, `pyyaml`, `requests`, ссылки на локальные пакеты
  `anywherecontacts`, `confluencesync`, `protocolfromsummary` (те же, что PFS).
- Python ≥ 3.11.
- Точка входа `taskrefresh = "taskrefresh.__main__:main"`.

### 2.18 `README.md`
- Кратко: назначение, ссылка на ТЗ, примеры команд, где живёт runtime.

---

## 3. Промежуточные точки проверки (последовательные этапы Sonnet'у)

1. **Skeleton (0.5 дня):** папки, pyproject, config, logger, project_registry
   + `test_project_registry.py`. Критерий: `pytest tests/test_project_registry.py`
   зелёный.
2. **READ path (1 день):** confluence_scan, page_reader, task_model, date_parse,
   filters + их тесты. Критерий: `pytest tests/test_{confluence_scan,page_reader,
   date_parse,filters}.py` зелёный, **реальный smoke на VM**: scan → чтение 3
   страниц → отфильтровать incomplete Саши → count > 0.
3. **UX брифа (0.5 дня):** formatter, session_store, contacts_resolver + тесты.
   Критерий: `run_read` возвращает валидный брифинг с 27+ задачами Саши (сверка
   с OpenTasks по критерию §6.1 ТЗ).
4. **WRITE path (1 день):** task_block, write_ops, change_spec + тесты (все
   9+7 кейсов). Критерий: `pytest tests/test_{task_block,write_ops,change_spec}.py`
   зелёный, ручной smoke на **тестовой странице** Саши (создать один `<ac:task>`,
   изменить дедлайн, сверить diff).
5. **E2E (0.5 дня):** pipeline + `test_pipeline_e2e.py` + CLI. Критерий: полный
   ручной цикл READ→APPLY→confirm на реальной странице (~tkachenkoav/*), критерии
   §6.1-6.8 ТЗ выполняются.
6. **Аудит и логирование:** после каждого apply — запись в `logs/ops-YYYY-MM.log`
   ровно того, что перечислено в §6.8 ТЗ. Критерий: 3 разные операции → 3
   строки лога с корректными полями.

---

## 4. Кейсы, обязательно покрытые тестами (перекрёстная таблица к ТЗ)

| Требование ТЗ | Файл теста | Кейс |
|---|---|---|
| F1 одиночный | test_filters | 2 |
| F1 мульти OR | test_filters | 2 |
| F2 pageId | test_filters | 3 |
| F2 тег | test_filters | 3 |
| F3 overdue | test_filters | 4 |
| F3 no-deadline | test_filters | 5 |
| F3 today/tomorrow | test_date_parse | 3-4 |
| F3 this-week/next-week | test_date_parse | 3 |
| F3 next-N-days | test_date_parse | 4 |
| F3 диапазон | test_date_parse | 5 |
| F4 табличная | test_filters | 8 |
| F4 без табличной (Q-8) | test_page_reader, test_filters | 2, 9 |
| F5 default incomplete | test_filters | 1 |
| F6 white/blacklist | test_filters | 10 |
| Комбинация фильтров | test_filters | 11, 12 |
| W1 текст | test_task_block, test_write_ops | 5, — |
| W2 исполнитель | test_task_block, test_write_ops | 4, 2 |
| W3 дедлайн (все три сценария: смена/добавление/удаление) | test_task_block | 1-3 |
| Пачка «было→станет» (Q-7) | test_formatter, test_write_ops | 5-6, 4-5 |
| Q-8 excluded_no_meeting_date показ | test_formatter | 4 |
| Q-9 нерезолвленный исполнитель | test_contacts_resolver, test_write_ops, test_task_block | 2, 3, 7 |
| Graceful degradation (задача удалена) | test_write_ops | 8 |
| 409 conflict + retry | test_write_ops | 6-7 |
| Session TTL / #N нумерация | test_session_store, test_change_spec | 2-4, 1-7 |
| Живой CQL scan (Q-1) | test_confluence_scan | 1-3 + реальный smoke этап 2 |
| Group-by-page PUT (Q-7 tech) | test_write_ops | 4-5 |

---

## 5. Что НЕ входит в план 1А (по ТЗ §7/§8 явно)

- W4 (статус) — не реализуем в MVP (Q-10).
- Отдельный dry-run флаг / auto-mode (Q-11).
- config.yml как whitelist spaces (Q-1 отменил).
- Собственный HTTP-слой (используем ConfluenceClient из ConfluenceSync).
- Собственный резолв контактов (используем PFS/AnywhereContacts).
- Модификация `_registry.json` PFS (только чтение — и то не требуется, F4 без anchor).
- Bulk-удаление, перенос между страницами, синхр. в Jira, telegram-cron.

---

## 6. Оценка объёма

- Файлы кода: **17** (`taskrefresh/` пакет + `__main__` + `pyproject` + `README`).
- Файлы тестов: **12** (по одному на модуль + e2e).
- Совокупно кейсов в тестах: **~70** (см. §4 выше — детальный подсчёт по файлам).
- Внешних зависимостей новых: **0** (всё уже стоит для PFS/CS).
- Ожидаемое время реализации Sonnet: 3-4 дня по этапам §3.
