---
tool: SRTool
doc: implementation_plan
version: 2.0.0-draft
date: 2026-08-06
based_on: SRTool_TZ_v2.md (base_version 1.1)
status: draft
---

# SRTool v2.0 — пофайловый план реализации (selfcheck конца периода)

> Это план, НЕ код. Составлен по `SRTool_TZ_v2.md`, с учётом фактической структуры
> `~/USERTOOLS/ConfluenceSync/` (пакет Python + tests, baseline 48/48 passed) и того, что
> `~/USERTOOLS/SRTool/` **не существует** — весь пакет создаётся с нуля.

## 0. Предпосылки, проверенные перед планом

- `SRTool_TZ.md` (v1.1) описывает только структуру `~/USERTOOLS/SRTool/` как **план** (sr_fill.py,
  srtool/jira_client.py, sr_fields.py, okr_loader.py, draft_generator.py, cli.py) — по факту
  директории `~/USERTOOLS/SRTool/` на диске нет. Ничего не переиспользуется, но конвенции
  (buллит `·`, `\r\n`, только POST/transitions, JIRA API v2, Bearer-токен) обязательны к
  соблюдению и в v2.
- `ConfluenceSync` — эталон структуры пакета: `pyproject.toml` (setuptools, console-script,
  pytest в `[tool.pytest.ini_options]`), `confluencesync/config.py` (Settings + `.env` через
  `python-dotenv`, приоритет env-файлов), `confluencesync/confluence_client.py` (тонкий REST-клиент
  с `tenacity`-ретраями), `__main__.py` (`click`-группа команд), тесты — по одному файлу на модуль,
  фикстура `tmp_vault` в `conftest.py` мокает `.env`/`WORKVAULT_PATH` через `monkeypatch`.
- Baseline тестов ConfluenceSync **до** изменений: `48 passed` (`pytest -q`, 0.62s) — контрольная
  точка, к которой нужно вернуться после доработки (плюс новые тесты).
- Формат `<ac:task>` подтверждён `confluence-meeting-protocol-format.md`: статус — элемент
  `<ac:task-status>`, не атрибут; дата — `<time datetime="YYYY-MM-DD" />` inline внутри
  `<ac:task-body>`; тег проекта — вручную напечатанный текстовый префикс (`"Trisigma. "`,
  `"AI-аналитик."`), не макрос; исполнитель — `<ac:link><ri:user ri:userkey="..."/></ac:link>`.
- Transition `271` («Заполнить итоги») и поля `customfield_44404/44405/44406` уже задокументированы
  в `SKILL.md` (`tutu-jira-sr`) как найденные эмпирически (05-06.08.2026) — план ниже их только
  формализует в коде, не открывает заново.

---

## Часть 1 — ConfluenceSync: метод `parse_tasks_from_page`

### 1.1. `confluencesync/confluence_client.py` (правка существующего файла)

Изменения:
- Новый публичный метод `ConfluenceClient.get_page_tasks_raw(page_id: str) -> str`:
  тонкая обёртка над существующим `get_page(page_id, expand="body.storage")`, возвращает
  `body["storage"]["value"]`. Не дублирует `get_page` — переиспользует его.
  - Альтернатива (проще): не добавлять метод в клиент, а сразу дергать
    `client.get_page(page_id, expand="body.storage")` из нового модуля `tasks.py` (см. 1.2).
    **Решение: не трогать `confluence_client.py` вообще**, чтобы не расширять и так тонкий
    REST-слой бизнес-логикой парсинга — экономит правки и риск регресса в 4 существующих
    тестах на клиент (косвенно покрыт `test_sync_pull.py`/`test_integration_smoke.py`).
- Итог: `confluence_client.py` **не редактируется**. Пункт оставлен в плане как явно
  рассмотренная и отклонённая опция (чтобы не открывать вопрос повторно на ревью).

### 1.2. `confluencesync/tasks.py` (новый файл)

Модуль извлечения задач из storage-формата страницы минутки. Соответствует §4 ТЗ.

Публичный API:
```python
def parse_tasks_from_page(
    client: "ConfluenceClient",
    page_id: str,
    userkey: str,
    date_from: date,
    date_to: date,
) -> List[TaskRecord]:
    ...
```

- `TaskRecord` — `@dataclass`: `task_id: str`, `status: str`, `userkey: str`,
  `date: Optional[date]`, `raw_text: str` (очищенный текст), `project_tag: Optional[str]`
  (первое слово-тег до точки, если распознано — используется в Части 2 `task_mapper.py`,
  здесь только извлекается эвристикой `re.match(r'^([А-ЯA-Za-z\-]+)\.\s*', text)`).
- Шаги реализации:
  1. `storage_html = client.get_page(page_id, expand="body.storage")["body"]["storage"]["value"]`.
  2. Парсинг через `BeautifulSoup(storage_html, "html.parser")` — тот же парсер, что и в
     `converter.py`, для консистентности (не `lxml.etree`, чтобы не тянуть вторую XML-стратегию
     в проект).
  3. Найти все `<ac:task>` (`soup.find_all("ac:task")`).
  4. Для каждой — прочитать дочерний `<ac:task-status>` (`.get_text()`, НЕ `.get("status")` —
     явный питфол из ТЗ §3.2).
  5. Фильтр по статусу: пропустить, если текст статуса ≠ `"complete"`.
  6. Прочитать `<ac:task-body>` → найти `<ac:link><ri:user ri:userkey="...">` внутри →
     сравнить `ri:userkey` с параметром `userkey`; если не совпадает — пропустить.
  7. Прочитать `<time datetime="YYYY-MM-DD" />` внутри `task-body` → распарсить `date.fromisoformat`.
     Если `<time>` отсутствует — пропустить задачу (не имеющую даты нельзя отнести к периоду) и
     залогировать через `warnings.warn`/возврат в отдельный список `skipped` (см. ниже про
     сигнатуру — не усложнять до необходимости отладки).
  8. Фильтр по дате: `date_from <= task_date <= date_to`.
  9. Очистка текста `task-body`: удалить `<span>` (`unwrap()`, сохранить текст), удалить
     `<ac:link>` целиком (`decompose()` — это mention исполнителя, не часть текста задачи) и
     `<ac:structured-macro>` целиком (`decompose()` — напр. `jira`-макросы, инлайн-комментарии),
     затем `.get_text(" ", strip=True)`; убрать саму дату из хвоста текста (regex
     `\s*$` после точки datetime уже не в тексте, т.к. `<time>` — отдельный тег, не текстовый
     узел — просто не включать его при сборке текста).
  10. Извлечь `project_tag` эвристикой по первому слову до `.`/пробела с заглавной буквы
      (см. `task_mapper.py`, Часть 2 — эвристика единая, но живёт в `SRTool`, не дублируется
      здесь; `tasks.py` возвращает **чистый** `raw_text`, тег парсит вызывающая сторона —
      следуя правилу ТЗ §4 «не дублировать логику», парсинг Confluence remains здесь, маппинг
      на критерии — в SRTool).
  11. Собрать `TaskRecord(task_id, status="complete", userkey, date=task_date, raw_text=...)`
      и добавить в результат.
- Публичная сигнатура НЕ принимает `project_tag` — убрать пункт 10 из ответственности этого
  модуля целиком (правка решения выше): `tasks.py` отвечает только за извлечение/фильтр/очистку,
  тегирование по проекту — обязанность `SRTool/task_mapper.py` (Часть 2), т.к. это доменная
  логика SRTool, а не общий Confluence-парсинг, которым могут пользоваться и другие инструменты
  (TaskRefresh, ProtocolFromSummary — см. §4 ТЗ, «переиспользуется другими инструментами»).
- Обработка ошибок: если страница не найдена/нет `body.storage` — пробрасывать
  `ConfluenceAPIError` (уже определён в `confluence_client.py`), не создавать новый класс
  исключений.

### 1.3. `confluencesync/__init__.py` (правка)

- Экспортировать `parse_tasks_from_page` и `TaskRecord` наравне с существующими экспортами
  (сверить текущий состав `__init__.py` перед правкой — сейчас 212 байт, вероятно экспортирует
  `ConfluenceSync`/`ConfluenceClient`; добавить туда же).

### 1.4. `confluencesync/__main__.py` (правка, опционально)

- Добавить CLI-команду `confluencesync tasks <page_id> --userkey <key> --from <date> --to <date>`
  для ручной отладки и как read-only-инспектор (полезно и для §3.5 read-only режима SRTool,
  который может звать эту же команду напрямую через subprocess либо, что чище, импортировать
  `parse_tasks_from_page` напрямую как Python-зависимость — **решение: SRTool импортирует
  функцию напрямую** (`from confluencesync.tasks import parse_tasks_from_page`), CLI-команда в
  ConfluenceSync — для ручной отладки инструмента отдельно от SRTool, не является обязательной
  зависимостью SRTool). Вывод команды — `json.dumps` списка задач, по аналогии с `show_log`.

### 1.5. Тесты — `tests/test_tasks.py` (новый файл)

По образцу `test_converter_html_to_md.py` (чистые unit-тесты на функцию с inline HTML-фикстурами,
без реальных HTTP-запросов — `client` мокается `unittest.mock.Mock`/простым stub-объектом с
методом `get_page`, возвращающим заранее заданный dict).

Кейсы:
1. `test_complete_task_in_range_matched` — одна задача, `status=complete`, нужный `userkey`,
   дата в диапазоне → попадает в результат, текст очищен от `<ac:link>`.
2. `test_incomplete_task_excluded` — `status=incomplete` → не попадает.
3. `test_wrong_userkey_excluded` — другой `userkey` в `<ri:user>` → не попадает.
4. `test_date_out_of_range_excluded` — дата раньше `date_from` и позже `date_to` → не попадает
   (два подслучая).
5. `test_task_without_time_tag_excluded` — нет `<time>` → не попадает, не падает исключением.
6. `test_body_cleaned_from_span_and_macro` — `<span class="...">` вокруг текста (питфол из
   SKILL.md — ручное редактирование в web-UI оборачивает контент) → текст извлечён без тегов;
   `<ac:structured-macro ac:name="jira">` внутри `task-body` → полностью удалён из текста.
7. `test_multiple_tasks_mixed_page` — страница с 4-5 задач, разные комбинации условий →
   в выводе только валидные, порядок сохранён как на странице.
8. `test_project_tag_prefix_preserved_in_raw_text` — `"Trisigma. Сделать X"` → `raw_text`
   содержит префикс тега как есть (тегирование — не ответственность этого модуля, но текст не
   должен обрезаться).
9. `test_page_without_task_list_returns_empty` — HTML без `<ac:task>` → `[]`, без ошибки.
10. `test_client_get_page_error_propagates` — stub кидает `ConfluenceAPIError` → пробрасывается
    наружу без подмены.

### 1.6. Контрольная точка Части 1

- `cd ~/USERTOOLS/ConfluenceSync && python3 -m pytest -q` → ожидается `48 + N passed`
  (N = число новых тестов из 1.5), 0 regressions в существующих 48.
- `ruff`/`mypy`, если настроены в проекте — проверить, есть ли конфиг (на момент baseline не
  обнаружен `ruff.toml`/`mypy.ini` в `pyproject.toml` — секции нет, значит линт не обязателен,
  но следовать стилю существующего кода: `from __future__ import annotations`, type hints,
  докстринги на русском в существующем стиле).

---

## Часть 2 — SRTool: новый пакет `~/USERTOOLS/SRTool/`

Структура пакета — по аналогии с ConfluenceSync (`pyproject.toml` + пакет-каталог + `tests/`),
а не по плану из `SRTool_TZ.md` v1.1 (`sr_fill.py` плоским скриптом + `srtool/`), т.к. v1.1
план не был реализован и де-факто отсутствует; выравниваем на актуальный эталон в репозитории.

```
~/USERTOOLS/SRTool/
├── pyproject.toml
├── .env.example
├── README.md
├── srtool/
│   ├── __init__.py
│   ├── config.py            # Settings (JIRA_TOKEN, JIRA_URL, WORKVAULT_PATH, tkachenkoav userkey)
│   ├── jira_client.py       # JiraClient: get_issue, get_transitions, post_transition
│   ├── confluence_sources.py# обёртка над ConfluenceSync.parse_tasks_from_page + список источников-минуток
│   ├── task_mapper.py       # гибридный маппинг задач → критерии
│   ├── draft_manager.py     # _draft.md: чтение/запись/резюме/финализация
│   ├── brief.py             # интерактивный поштучный бриф (шаги §3.4)
│   ├── selfcheck.py         # основной флоу — оркестрация всех модулей
│   ├── preview.py           # read-only режим (§3.5)
│   ├── formatting.py        # сборка plain-text блоков 4/5/6 для Jira (без markdown)
│   └── cli.py               # click-обёртки: sr report / sr preview
├── __main__.py               # entry-point, аналог ConfluenceSync/__main__.py
└── tests/
    ├── conftest.py
    ├── test_task_mapper.py
    ├── test_draft_manager.py
    ├── test_formatting.py
    ├── test_selfcheck_flow.py
    ├── test_preview.py
    ├── test_jira_client.py
    └── test_cli.py
```

### 2.1. `pyproject.toml`

- Скопировать структуру секций из `ConfluenceSync/pyproject.toml`.
- `dependencies`: `click>=8.1`, `requests>=2.31`, `tenacity>=8.2`, `python-dotenv>=1.0`,
  `PyYAML>=6.0`, `confluencesync` (локальная зависимость — путь `../ConfluenceSync` через
  `pip install -e` или `[tool.uv.sources]`/`file:` URL — согласовать способ подключения
  локального пакета на этапе реализации, т.к. `confluencesync` не опубликован в PyPI/индексе).
  Не дублировать `beautifulsoup4`/`markdownify` — SRTool не парсит Confluence storage сам
  (см. §4 ТЗ, делегирование в ConfluenceSync).
- `[project.scripts]`: `srtool = "srtool.__main__:cli"`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`.

### 2.2. `srtool/config.py`

По аналогии с `confluencesync/config.py`:
- `Settings`: `jira_url` (`https://hq.tutu.ru`), `jira_token` (env `JIRA_TOKEN`),
  `confluence_url`/`confluence_token` — переиспользовать те же env-переменные, что и
  ConfluenceSync (`.env` приоритет: `~/USERTOOLS/SRTool/.env`, fallback на общий), `workvault_path`
  (по умолчанию `~/WorkVault`), `sr_output_dir` (property → `workvault_path / "Projects/adm/SR/SR Ткаченко"`),
  `owner_userkey` (env `SR_OWNER_USERKEY`, дефолт — userkey tkachenkoav из ТЗ §3.2, но не
  хардкодить его как константу в коде без env-фолбэка — если Саша сменит владельца/переиспользует
  инструмент под другой SR, не должно требовать правки кода).
- Отдельный `_find_env_file()` по аналогии — искать `.env` рядом с пакетом.

### 2.3. `srtool/jira_client.py`

Тонкий REST-клиент JIRA v2, зеркалирует стиль `confluence_client.py` (Bearer, `tenacity`-ретраи,
`ConfluenceAPIError`-подобный `JiraAPIError`).

Методы:
- `get_issue(key: str, fields: Optional[List[str]] = None) -> dict` — GET
  `/rest/api/2/issue/{key}` с явным списком полей (44401-44406) по умолчанию, как в SKILL.md
  примере curl.
- `get_transitions(key: str) -> List[dict]` — GET `/rest/api/2/issue/{key}/transitions`.
  **Обязательный вызов перед КАЖДЫМ POST** (питфол из SKILL.md — статус может измениться между
  этапами сессии) — реализуется как явный шаг в `selfcheck.py`, не кешируется внутри клиента.
- `post_transition(key: str, transition_id: str, fields: Dict[str, str]) -> dict` — POST
  `/rest/api/2/issue/{key}/transitions` с `{"transition": {"id": transition_id}, "fields": fields}`.
  **Никогда не использовать PUT** — явный докстринг-предупреждение, зеркалирующий комментарий в
  `confluence_client.update_page`.
- Константа `TRANSITION_END_OF_PERIOD = "271"` — только для конца периода; НЕ заводить константу
  `TRANSITION_START_OF_PERIOD = "61"` в этом же файле без явного namespace-разделения
  (`transitions.py`? — решение: держать обе константы рядом с комментарием "v1.1 vs v2.0, см.
  ТЗ §2", т.к. один клиент обслуживает оба сценария, путать нельзя —assert в `post_transition`,
  что вызывающий код передаёт transition_id явно, не полагается на дефолт).

### 2.4. `srtool/confluence_sources.py`

- `SOURCE_PAGES: Dict[str, int]` — реестр минуток по проектным тегам (`{"AI-аналитик": 477061038,
  "Trisigma": 490170597, ...}`) — по аналогии с реестром тегов, упомянутым в
  `confluence-meeting-protocol-format.md` («реестр тегов по фактическому употреблению»,
  собирается вручную, не парсится). На старте — минимум 2 записи из ТЗ §3.2, расширяемый список
  (не хардкод в `selfcheck.py`, а отдельный модуль, чтобы менять без правки основного флоу).
- `collect_tasks(period_from: date, period_to: date, userkey: str) -> List[TaskRecord]`:
  для каждой страницы в `SOURCE_PAGES` вызывает `confluencesync.tasks.parse_tasks_from_page`
  (Часть 1), агрегирует результат, добавляет `source_project` (ключ реестра, тег) к каждому
  `TaskRecord` — **здесь**, а не в ConfluenceSync (см. решение в 1.2, п. 11).
- Не открывает свой `ConfluenceClient` — принимает готовый экземпляр параметром (DI, упрощает
  тестирование мок-клиентом).

### 2.5. `srtool/task_mapper.py`

Гибридный маппинг (§3.3, §6 п.1 ТЗ):
- `auto_map(tasks: List[TaskRecord], criteria_text: str) -> Dict[int, List[TaskRecord]]`:
  1. `parse_criteria(criteria_text) -> Dict[int, str]` — переиспользует regex-подход
     `derive_block2` из `SRTool_TZ.md` v1.1 §4.3 (пункты `N. текст`, разделённые `\r\n`), но в
     обратную сторону — не деривация, а разбор уже готового блока 2 на пункты с номерами.
  2. Для каждого проектного тега (по `source_project`/эвристике первого слова, см. решение 1.2
     п.11) — посчитать релевантность каждому критерию через пересечение ключевых слов
     (простое множество токенов, нижний регистр, без стоп-слов; без ML/эмбеддингов — MVP).
  3. Тег → критерий с максимальным пересечением; если пересечение = 0 у всех критериев →
     задачи тега уходят в специальную группу `0` = «Прочие результаты» (соответствует
     формулировке ТЗ §3.3).
  4. Вернуть `dict[criterion_number, list[TaskRecord]]`, включая ключ `0` для непримапленных.
- `apply_user_correction(mapping, correction_cmd: str) -> mapping` — парсинг команд вида
  «перенеси задачу N к критерию M» из §3.3 п.2; регэксп на номер задачи + номер критерия;
  бросает понятную ошибку при нераспознанном формате команды (бриф должен переспросить, не падать).
- Чистая функция, не знает про Jira/Confluence/файлы — легко тестируется.

### 2.6. `srtool/draft_manager.py`

Реализует §3.3, §3.4 п.9, §8.2.

- `DraftManager(sr_key: str, period: str, settings: Settings)`:
  - `path` property → `{sr_output_dir}/{sr_key}_{period}_draft.md`.
  - `exists() -> bool`.
  - `load() -> DraftState` — парсит существующий `_draft.md` в структуру (какие критерии уже
    заполнены, что именно — блоки 4/5/6 частично). Формат MD должен быть парсибельным обратно
    (не свободный текст) — заголовки `### N. <критерий>` + маркеры полей, аналогично формату,
    зафиксированному в SKILL.md `tutu-jira-sr` §"draft.md" (`**Плановый результат:**`,
    `**Дополнительный результат:**`, `**Проблема:**`/`**Решение:**` — переиспользовать этот уже
    выверенный шаблон 1:1, не изобретать новый).
  - `save(state: DraftState) -> None` — атомарная перезапись (write to `.tmp` + `os.replace`,
    защита от обрыва процесса на середине записи — вызывается после **каждого** ответа
    пользователя в брифе, см. §3.4 п.9).
  - `progress_summary() -> str` — «заполнено N из M критериев» для сообщения при повторном
    запуске (§3.3).
  - `finalize() -> Path` — переименование/слияние `_draft.md` → финальный `{sr_key}_{period}.md`
    (снятие пометки "черновик", см. §3.6, срабатывает только после успешного `post_transition`).
  - Заголовок черновика — `> Статус: черновик, брифинг не завершён (N/M критериев)` (§8.2),
    убирается в `finalize()`.
- `DraftState` — dataclass: `sr_key`, `period`, `blocks_1_3` (текст, read-only контекст),
  `criteria: Dict[int, CriterionDraft]`, где `CriterionDraft` содержит статус
  (`done|partial|not_done|pending`), причину, расширение, контроль, проблемы/решения,
  доп. результаты, подтверждённый маппинг задач.

### 2.7. `srtool/brief.py`

Реализует диалоговый цикл §3.4 (шаги 1-9) как **генератор шагов**, а не монолитную функцию —
инструмент работает в TG/CLI сессии, где каждый шаг = один обмен репликами, не блокирующий ввод
внутри процесса. Дизайн:

- `BriefSession` — держит `DraftState`, `DraftManager`, текущий индекс критерия/под-шага.
- `next_prompt() -> BriefStep` — возвращает, что показать пользователю дальше (текст критерия +
  авто-маппинг / запрос статуса / запрос причины / и т.д.), согласно детерминированному конечному
  автомату из §3.4 (9 шагов на критерий, с условным пропуском шага 4 если статус ≠ «частично»,
  и условным пропуском повторного запроса маппинга для тегов без пересечений).
- `submit_answer(text: str) -> None` — принимает ответ пользователя на текущий шаг, обновляет
  `DraftState`, вызывает `draft_manager.save()` (автосохранение — §3.4 п.9), продвигает автомат.
- `is_complete() -> bool`.
- Этот модуль **не делает I/O с пользователем напрямую** (не `input()`/`print()`) — вызывающая
  сторона (CLI в интерактивном режиме или TG-обвязка Сирени вне этого пакета) сама решает, как
  показывать `next_prompt()` и откуда брать `submit_answer()`. Это ключевое архитектурное решение:
  делает `brief.py` тестируемым без моков stdin и переиспользуемым и в CLI, и в TG-скилле.

### 2.8. `srtool/formatting.py`

Реализует §3.3 («без markdown, plain text») и точный шаблон из `tutu-jira-sr` SKILL.md
(строки про `### N. <тема>`, `**Плановый результат:**` и т.д. — но с оговоркой самого SKILL.md,
что **в Jira** это идёт как обычный текст без markdown-рендера, только с переносами строк для
читаемости):

- `format_block4(state: DraftState) -> str` — «выполнено», по критериям.
- `format_block5(state: DraftState) -> str` — «сложности» (проблема/решение пары, пустая пара
  не выводится — питфол из SKILL.md).
- `format_block6(state: DraftState) -> str` — «развитие».
- Общее: убрать markdown-разметку (`**`, `#`) перед отправкой в Jira-поле (в `_draft.md` она
  нужна для читаемости файла человеком, а в payload transition 271 — только текст с переносами);
  реализовать как два режима одной функции или два отдельных рендерера
  (`render_for_draft_md` vs `render_for_jira_plain`) — **решение: два явных рендерера**,
  чтобы не протаскивать флаг через всю цепочку вызовов.

### 2.9. `srtool/selfcheck.py`

Оркестратор основного флоу (§3.1-3.4, 3.6):
1. `load_plan(sr_key) -> PlanBlocks` — `jira_client.get_issue`, читает 44401-44403 (read-only,
   контекст, не редактируется — §3.1).
2. Проверить наличие `_draft.md` (`DraftManager.exists()`) → если есть, вызвать
   `progress_summary()`, вернуть пользователю выбор «продолжить / начать заново» (не решать
   самостоятельно — реализуется как явный шаг наружу, аналогично `brief.py`, не блокирующий
   `input()`).
3. Если начинаем заново: `confluence_sources.collect_tasks(period_from, period_to, owner_userkey)`
   → `task_mapper.auto_map(tasks, plan.block2)` → создать `DraftState` с пустыми критериями и
   предварительным маппингом.
4. Запустить `BriefSession` до `is_complete()`.
5. По завершении брифа: `formatting.format_block4/5/6` (Jira-режим) →
   `jira_client.get_transitions(sr_key)` (обязательная свежая проверка, питфол SKILL.md) →
   найти id `271` в списке доступных → `jira_client.post_transition(sr_key, "271", {...})`.
6. При успехе — `draft_manager.finalize()`.
7. При ошибке (напр. transition 271 недоступна — SR не в нужном статусе) — сообщить пользователю
   статус и НЕ трогать `_draft.md` (оставить как есть для повторной попытки), согласно питфолу
   SKILL.md «пере-проверять transitions перед КАЖДОЙ заливкой».
- **Не вызывает rclone/systemctl** — явный отказ, зафиксированный в ТЗ §7. Комментарий в коде
  со ссылкой на §7, чтобы не восстановили вызов по аналогии со старым код-ревью.

### 2.10. `srtool/preview.py`

Реализует §3.5 (read-only):
- `preview(sr_key, period_from, period_to, owner_userkey) -> PreviewResult`: шаги 3.1-3.3 без
  записи — переиспользует `selfcheck.load_plan` + `confluence_sources.collect_tasks` +
  `task_mapper.auto_map`, но **не создаёт** `DraftManager`, **не** зовёт `jira_client.get_transitions`
  /`post_transition` вообще (даже проверочно) — прямое требование ТЗ («НЕ обращается к JIRA
  transition 271»).
- `PreviewResult.to_table() -> str` — «критерий → авто-замапленные задачи → задачи без
  маппинга», текстовая таблица для TG/CLI (не файл на диск).

### 2.11. `srtool/cli.py` + `__main__.py`

По образцу `confluencesync/__main__.py` (`click`-группа):
- `srtool report SR-XXXXX [--from DATE] [--to DATE]` → интерактивный CLI-цикл поверх
  `selfcheck.py`: пока `not brief.is_complete()`, печатать `next_prompt()`, читать `input()`,
  вызывать `submit_answer()`. Это единственное место в пакете, где допустим `input()`/`click.echo`
  — вся бизнес-логика в `brief.py`/`selfcheck.py` остаётся I/O-агностичной (тестируемость).
- `srtool preview SR-XXXXX [--from DATE] [--to DATE]` → вызывает `preview.preview()`, печатает
  `to_table()`, никогда не создаёт файлов.
- Даты `--from/--to` по умолчанию — «отчётный месяц + 7 дней» (ТЗ §3.2), реализовать как
  функцию `default_period(now) -> (date, date)` в `selfcheck.py` или отдельном `periods.py`
  (решение: класть в `selfcheck.py`, не плодить файл ради одной функции на MVP).

### 2.12. Тесты (`tests/`)

По образцу структуры ConfluenceSync — один файл на модуль, `conftest.py` с фикстурами
`tmp_workvault` (аналог `tmp_vault`) и mock-клиентами `jira_client`/`confluence_client`
(простые `Mock()`/руками написанные stub-классы, без реальных HTTP — весь пакет не должен
делать сетевые вызовы в тестах, зеркалируя подход ConfluenceSync).

- `tests/conftest.py` — `tmp_workvault(tmp_path, monkeypatch)`, `fake_jira_client()`,
  `fake_confluence_client()`.
- `tests/test_task_mapper.py` — покрытие `auto_map`/`apply_user_correction`: явный матч по
  ключевым словам, случай «нет пересечений → группа 0», разбор команды коррекции, ошибка на
  некорректной команде.
- `tests/test_draft_manager.py` — save/load roundtrip, `progress_summary()` на частично
  заполненном состоянии, `finalize()` убирает пометку черновика и переименовывает файл, атомарность
  записи (файл не остаётся пустым/битым при имитации сбоя — проверить, что `.tmp` не остаётся
  после успешного `save`).
- `tests/test_formatting.py` — `format_block4/5/6`: пустая пара «проблема без решения» не
  печатает `**Решение:**`; отсутствие markdown-символов в Jira-режиме (`render_for_jira_plain`);
  соответствие критерий-в-критерий нумерации плана (пункт N плана = пункт N факта, из SKILL.md
  §"CHECK/SELFCHECK").
- `tests/test_selfcheck_flow.py` — оркестрация с fake-клиентами: полный happy-path от
  `load_plan` до `post_transition`, проверка что при недоступной transition 271 `_draft.md`
  не создаётся/не трогается финализация, проверка что `_draft.md` резюмируется корректно при
  повторном запуске (найден existing draft → предложен выбор).
- `tests/test_preview.py` — `preview()` не создаёт файлов на диске (assert на `tmp_path`),
  не вызывает `get_transitions`/`post_transition` на fake-клиенте (assert `call_count == 0`).
- `tests/test_jira_client.py` — `post_transition` формирует корректный payload
  (`{"transition": {"id": ...}, "fields": {...}}`), константа `271` используется только явно
  переданной, не как дефолт функции; ретраи через `tenacity` на `RequestException` (по аналогии
  с тестами клиента, если такие есть в ConfluenceSync — проверить `test_sync_pull.py` на паттерн
  мока `requests`).
- `tests/test_cli.py` — по аналогии с `ConfluenceSync/tests/test_cli.py` (`click.testing.CliRunner`):
  smoke-тест, что `srtool preview` и `srtool report --help` не падают на уровне парсинга аргументов.

### 2.13. Контрольная точка Части 2

- Новый venv/зависимости: `cd ~/USERTOOLS/SRTool && python3 -m venv .venv && .venv/bin/pip install -e . -e ../ConfluenceSync[dev]`
  (порядок и способ подключения локального `confluencesync` — уточнить на этапе реализации,
  вариант через `pip install -e ../ConfluenceSync` до `pip install -e .`, чтобы egg-link
  подхватился).
- `python3 -m pytest -q` в `~/USERTOOLS/SRTool` → все тесты зелёные, без сетевых вызовов
  (проверить явно — ни один тест не должен требовать `JIRA_TOKEN`/`CONFLUENCE_TOKEN` из
  реального `.env`, все клиенты — fake/mock).

---

## 3. Порядок реализации (зависимости между частями)

1. Часть 1 целиком (ConfluenceSync: `tasks.py` + тесты) — **блокер** для Части 2, т.к.
   `confluence_sources.py` импортирует `parse_tasks_from_page` напрямую (см. ТЗ §4 —
   «Реализация доработки ConfluenceSync — блокер для §3.2», зафиксировано и в §10 ТЗ).
2. `srtool/config.py`, `srtool/jira_client.py` — независимы от Части 1, можно параллельно.
3. `srtool/task_mapper.py`, `srtool/formatting.py`, `srtool/draft_manager.py` — чистая логика,
   без внешних зависимостей, разрабатываются и тестируются независимо друг от друга и от Части 1.
4. `srtool/confluence_sources.py` — после готовности Части 1.
5. `srtool/brief.py`, `srtool/preview.py`, `srtool/selfcheck.py` — оркестрация, после готовности
   пп. 2-4.
6. `srtool/cli.py`, `__main__.py`, `pyproject.toml` — финальная сборка пакета.
7. Полный прогон тестов обеих частей + ручной smoke-тест на реальном SR (вне этого плана,
   отдельная сессия с реальными токенами) — только после согласования плана Сашей, не
   автоматически.

## 4. Что осознанно вынесено за рамки этого плана (не реализуется сейчас)

- Обновление `tutu-jira-sr`/`tutu-confluence-jira` **SKILL.md** под вызов нового кода (§5, §9
  ТЗ) — отдельная задача после того, как код реализован и провёрен, не часть кодовой реализации.
- §3.7 (создание задач в минутках по итогам брифа) — прямо помечено в ТЗ как ручной шаг через
  TaskRefresh, не автоматизируется.
- Мерж `SRTool_TZ_v2.md` в мастер-файл `SRTool_TZ.md` и обновление `MAIN_TZ_INVENTORY.md`
  (§9, §10 ТЗ) — документационная задача после реализации и обкатки на следующем SR.
- rclone/`workvault-sync` — явно не вызывается из кода (§7 ТЗ), интеграция не требуется.
