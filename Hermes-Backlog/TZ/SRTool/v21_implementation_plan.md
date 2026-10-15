---
tool: SRTool
version: "2.1"
date: 2026-08-10
status: plan
based_on: SRTool_TZ.md §10 (строки 605-979)
variant: "Вариант 2 — Компактный"
---

# SRTool v2.1 — Пофайловый план реализации (режим `plan` + кэш OKR + батчинг)

> Источник требований: `SRTool_TZ.md` §10.1–10.9.
> Текущий код прочитан целиком: `jira_client.py`, `cli.py`, `config.py`, `confluence_sources.py`,
> `draft_manager.py`, `formatting.py`, `__init__.py`, `__main__.py`, `preview.py`, `selfcheck.py`,
> `task_mapper.py`, `brief.py`, `tests/*`, `pyproject.toml`.

## 0. Отличие от структуры §10.7 ТЗ

ТЗ (§10.7) предлагает 5 новых файлов (`okr_cache.py`, `plan_finder.py`, `pct_calculator.py`,
`plan_generator.py` + правки `jira_client.py`/`cli.py`). Задачей выбран **Вариант 2 — Компактный**:
вместо трёх узких модулей (`plan_finder.py`, `pct_calculator.py`, `plan_generator.py`) — один
оркестратор `plan.py` (по аналогии с ролью `selfcheck.py` для конца периода), плюс отдельный
`okr_cache.py` (кэш — самостоятельная переиспользуемая обвязка над диском, как `draft_manager.py`
для драфтов). Функции из §10.3.1–10.3.8 не переименовываются и не меняют сигнатур — меняется
только их физическое расположение (все в `plan.py`, кроме кэша).

Соответствие "функция из ТЗ → файл в этом плане":

| Функция/раздел ТЗ | Файл в этом плане | Файл по ТЗ §10.7 |
|---|---|---|
| `find_previous_sr` (§10.3.1) | `plan.py` | `plan_finder.py` |
| `extract_kr_framework` (§10.3.2) | `plan.py` | `plan_finder.py` |
| `load_kr_batch` (§10.3.3) | `plan.py` | (не указан явно, логически в plan_finder/plan.py) |
| `calc_target_pct` (§10.3.4) | `plan.py` | `pct_calculator.py` |
| `find_new_krs` (§10.3.5) | `plan.py` | `plan_finder.py` |
| генерация `_plan_draft.md` (§10.3.6) | `plan.py` (генерация) + `draft_manager.py` (сериализация/IO) | `plan_generator.py` |
| поштучный бриф плана (§10.3.7) | `brief.py` (расширение) | `plan_generator.py` |
| заливка + верификация (§10.3.8) | `plan.py` | — |
| `get_quarter`, `load_okr_from_cache`, `save_okr_cache` (§10.4) | `okr_cache.py` | `okr_cache.py` |
| `batch_search_issues` (§10.5) | `jira_client.py` | `jira_client.py` |
| `suggest_followup_tasks` (§10.6) | `plan.py` | — |
| CLI `plan` (§10.3) | `cli.py` | `cli.py` |

---

## 1. `jira_client.py` — добавить batch-поиск

### Изменения
- [ ] Добавить метод `JiraClient.search(jql, fields=None, max_results=50)`:
  - `GET /rest/api/2/search` с параметрами `jql`, `fields` (через запятую), `maxResults`.
  - Возвращает `{"issues": [...]}` — как отдаёт Jira, без пост-обработки (пост-обработка — в вызывающем коде `plan.py`).
  - Нужен как базовый примитив: `find_previous_sr`, `find_new_krs`, `batch_search_issues` (§10.3.1, §10.3.5, §10.5) все идут через JQL search, а не через `get_issue`.
- [ ] Добавить модульную функцию `batch_search_issues(jira_client, keys, fields=None) -> dict[str, dict]` (§10.5):
  - Пустой `keys` → `{}` без запроса.
  - `fields` по умолчанию: `["summary", "status", "customfield_43782", "issuelinks"]` (как в ТЗ; `customfield_43782` — поле % выполнения OKR, проверить реальный field ID перед реализацией, см. чекпоинт CP1).
  - Чанкинг по 100 ключей (лимит Jira Search API) — цикл с несколькими вызовами `jira_client.search`, результаты объединяются в один dict.
  - `jql = f"key IN ({', '.join(keys)})"`.
  - Возврат: `{issue["key"]: issue for issue in result["issues"]}`.
- [ ] Добавить константу `TRANSITION_START_OF_PERIOD = "61"` (уже упомянута в TZ v1.1 §5, в текущем `jira_client.py` есть только `TRANSITION_END_OF_PERIOD = "271"` — недостаёт симметричной константы для v2.1, `plan.py` её использует при заливке §10.3.8).

### Зависимости
- Не зависит от новых файлов. От неё зависят: `plan.py` (batch_search_issues, search, TRANSITION_START_OF_PERIOD), `okr_cache.py` не зависит от jira_client напрямую (принимает уже готовые данные).

### Тесты (`tests/test_jira_client.py` — новый файл)
- [ ] `test_search_builds_correct_request` — мок `requests.Session`, проверить URL/параметры GET `/rest/api/2/search`.
- [ ] `test_batch_search_issues_empty_keys_no_request` — `batch_search_issues(client, [])` не делает запросов, возвращает `{}`.
- [ ] `test_batch_search_issues_single_call_under_100_keys` — 7 ключей → ровно 1 вызов `search`.
- [ ] `test_batch_search_issues_chunks_over_100_keys` — 150 ключей → 2 вызова `search` с чанками по ≤100.
- [ ] `test_batch_search_issues_maps_by_key` — результат `{key: issue}` соответствует входным ключам.

### Чекпоинт CP1: batch API работает
- **Критерий:** `batch_search_issues` с реальными/мок-данными возвращает dict с нужными ключами; `pytest tests/test_jira_client.py` зелёный.
- ⚠️ Перед реализацией — уточнить у пользователя реальный field ID для "% выполнения OKR" (в ТЗ упомянут `customfield_43782` без ссылки на источник) — если поле не подтверждено, `load_kr_batch`/`calc_target_pct` (§2) не будут иметь данных для `current_pct`. Если поле не находится — запросить у пользователя точный field ID перед CP2.

---

## 2. `okr_cache.py` — новый файл, кэширование OKR-данных

### Функции (по §10.4, сигнатуры без изменений)
- [ ] `get_quarter(date: datetime) -> str` — `f"Q{(date.month-1)//3+1} {date.year}"`.
- [ ] `load_okr_from_cache(key: str, quarter: str, cache_dir: Path) -> dict | None`:
  - Путь `cache_dir / f"{key}.md"` (в проде `cache_dir = settings.workvault_path / "Projects" / "okr-tool"`, но параметризовать через `Settings`, не хардкодить путь — по аналогии с `draft_manager.py`/`sr_output_dir`, для тестируемости на `tmp_path`).
  - `None`, если файла нет или `get_quarter(mtime) != quarter`.
  - Иначе — `parse_okr_md(path)`.
- [ ] `save_okr_cache(key: str, data: dict, cache_dir: Path) -> None`:
  - `render_okr_md(cache_dir / f"{key}.md", data)`, создаёт `cache_dir` при необходимости (`mkdir(parents=True, exist_ok=True)`).
- [ ] `parse_okr_md(path: Path) -> dict` — парсинг YAML-frontmatter (`key`, `summary`, `status`, `pct`, `updated`) через `yaml.safe_load` (PyYAML уже в зависимостях). Возврат `{"key":..., "summary":..., "status":..., "pct":..., "updated":...}`.
- [ ] `render_okr_md(path: Path, data: dict) -> None` — сериализация frontmatter + человекочитаемое тело (см. пример §10.4). Атомарная запись через `.tmp` + `os.replace` (та же схема, что в `DraftManager.save`).

### Отличие от ТЗ (обязательно уточнить с пользователем на CP2)
ТЗ даёт сигнатуры `load_okr_from_cache(key, quarter)` / `save_okr_cache(key, data)` без параметра пути — путь хардкодится как `/home/tkachenkoav/WorkVault/Projects/okr-tool/{key}.md`. План добавляет параметр `cache_dir` для тестируемости (без tmp_path тесты будут писать в реальный WorkVault). В `plan.py` вызывать с `cache_dir=settings.okr_cache_dir` (новое свойство в `config.py`, см. §3).

### Зависимости
- Использует `yaml` (PyYAML, уже зависимость), `os`, `pathlib`, `datetime`. Не зависит от `jira_client.py` — принимает готовый `dict` от вызывающего кода (`plan.py`).
- От неё зависит `plan.py` (`load_kr_batch`).

### Тесты (`tests/test_okr_cache.py` — новый файл)
- [ ] `test_get_quarter_boundaries` — проверить все 4 квартала + границы месяцев (март/апрель, июнь/июль, сентябрь/октябрь, декабрь/январь).
- [ ] `test_load_from_cache_missing_file_returns_none`.
- [ ] `test_load_from_cache_stale_quarter_returns_none` — файл с mtime из прошлого квартала (через `os.utime`).
- [ ] `test_load_from_cache_fresh_returns_data` — записать валидный `.md`, mtime — текущий квартал, проверить парсинг полей.
- [ ] `test_save_and_load_roundtrip` — `save_okr_cache` → `load_okr_from_cache` возвращает те же данные.
- [ ] `test_parse_okr_md_frontmatter_fields` — все поля (`key`, `summary`, `status`, `pct`, `updated`) распознаются.
- [ ] `test_save_creates_cache_dir_if_missing`.

### Чекпоинт CP2: кэш работает изолированно
- **Критерий:** `pytest tests/test_okr_cache.py` зелёный; ручная проверка — записать `.md` с прошлым кварталом → `load_okr_from_cache` возвращает `None`; с текущим — возвращает dict.
- Здесь же согласовать с пользователем параметр `cache_dir` (отход от буквальной сигнатуры ТЗ).

---

## 3. `config.py` — расширение Settings

### Изменения
- [ ] Добавить свойство `Settings.okr_cache_dir -> Path`: `self.workvault_path / "Projects" / "okr-tool"` (аналог существующего `sr_output_dir`).
- [ ] Добавить свойство `Settings.plan_draft_dir -> Path` (если решим не переиспользовать `sr_output_dir` — по ТЗ §10.3.6 путь `_plan_draft.md` тот же `SR Ткаченко`, что и у `_draft.md`, так что отдельное свойство не нужно — **переиспользовать `sr_output_dir`**, добавить только `okr_cache_dir`).
- [ ] Добавить опцию `Settings.default_target_pct: int = 50` (значение `--target-pct` по умолчанию, §10.3) — читается из `os.getenv("SR_DEFAULT_TARGET_PCT", "50")`, чтобы не хардкодить магическое число в `cli.py`/`plan.py`.

### Тесты (добавить в существующий `tests/test_config.py`, если нет — создать)
- [ ] `test_okr_cache_dir_path` — путь строится корректно от `workvault_path`.
- [ ] `test_default_target_pct_from_env` и `test_default_target_pct_fallback`.

### Чекпоинт: без отдельного, входит в CP1/CP2 (не самостоятельная веха).

---

## 4. `plan.py` — новый файл, оркестратор режима `plan`

Аналог роли `selfcheck.py`, но для начала периода (блоки 1-3, transition 61).

### Датаклассы
- [ ] `KRFrameworkItem` (или переиспользовать `dict`, как в ТЗ — решить на CP3; рекомендация: датакласс для типобезопасности, аналогично `CriterionDraft`):
  ```python
  @dataclass
  class KRFrameworkItem:
      order: int
      key: str
      summary: str
      is_new: bool = False
      current_pct: float | None = None
      target_pct: int | None = None
      status: str = ""
  ```
- [ ] `PlanResult` (аналог `SelfcheckResult`): `success: bool`, `message: str`, `final_path: Optional[str]`.
- [ ] `PlanContext` (аналог `ReportContext`): `session` (расширенный `BriefSession`/новый `PlanBriefSession`, см. §5), `draft_manager`, `jira_client`, `framework: list[KRFrameworkItem]`.

### Исключения
- [ ] `PreviousSRNotFound(Exception)` (§10.3.1).
- [ ] `EmptyFramework(Exception)` (§10.3.2).

### Функции (сигнатуры из ТЗ, без изменений имён/аргументов)
- [ ] `find_previous_sr(jira_client, current_key: str, user: str) -> str` — §10.3.1, JQL с `assignee`, исключение статуса `"Оценка установлена"`, `ORDER BY created DESC`, `max_results=1`. Бросает `PreviousSRNotFound` при пустом результате.
- [ ] `extract_kr_framework(block3_text: str) -> list[dict]` — §10.3.2, regex `^(\d+)\.\s+([A-Z]+-\d+)\s+(.*)$` с `re.MULTILINE` по тексту с `\r\n → \n`. Бросает `EmptyFramework` при пустом списке.
  - ⚠️ Питфол по аналогии с `sr_fields.py`/§6 ТЗ v1.1: сверить реальный формат Блока 3 — в ТЗ v1.1 §4.4 (`derive_block3`) формат вывода `"{num}. {key} {summary}"` без таба — совпадает с regex здесь. Проверить на реальном SR при CP3 (не на синтетике).
- [ ] `load_kr_batch(jira_client, keys: list[str], quarter: str, settings) -> dict[str, dict]` — §10.3.3, cache-first через `okr_cache.load_okr_from_cache`/`save_okr_cache` (передавая `settings.okr_cache_dir`), для промахов — `batch_search_issues` из `jira_client.py`.
- [ ] `calc_target_pct(current_pct: float, target_pct_flag: int = 50) -> int` — §10.3.4, чистая функция, без побочных эффектов (легко юнит-тестируется отдельно).
- [ ] `find_new_krs(jira_client, user: str, fix_version: str, framework_keys: list[str]) -> list[dict]` — §10.3.5, JQL по `issuetype in (OKR, "Sub-task")`, `fixVersion`, `key NOT IN (...)`.
- [ ] `resolve_fix_version(now: datetime | None = None) -> str` — авторасчёт текущего квартала в формате версии Jira (нужно уточнить реальный формат версий на CP3 — `"Q3 2026"` из примера в ТЗ, но нужно свериться с реальным справочником версий Jira проекта).
- [ ] `build_plan_draft_state(sr_key, period, previous_sr_key, framework, jira_client) -> DraftState`:
  - Собирает `DraftState` для `_plan_draft.md`, используя расширенный `DraftState`/`CriterionDraft` из `draft_manager.py` (см. §6) — заполняет каркас (было%/цель%/статус) как контекст, без предзаполненных ответов (бриф формулировок — с нуля, в отличие от selfcheck).
- [ ] `generate_plan_draft_md(state) -> str` — рендер таблицы каркаса + заготовок блоков 1-3 (§10.3.6), делегирует сериализацию `DraftManager` (расширение, см. §6), не дублирует форматирование.
- [ ] `suggest_followup_tasks(framework: list[dict], sr_key: str, settings) -> list[dict]` — §10.6, использует `extract_project_tag` из существующего `task_mapper.py` (переиспользование, не дублирование) + `resolve_minutes_page(tag)` — реестр страниц минуток. ⚠️ Реестр `project_tag → pageId` в текущем коде явно не вынесен отдельно — в `confluence_sources.py` есть `SOURCE_PAGES` (используется для сбора задач selfcheck). Уточнить на CP4: тот же реестр или отдельный (TaskRefresh может иметь свой) — не изобретать новый маппинг без проверки реального реестра TaskRefresh.
- [ ] `begin_plan(sr_key, jira_client, settings, *, target_pct_flag=50, fix_version=None, draft_choice_fn=None) -> PlanContext` — аналог `begin_report`: проверка существующего `_plan_draft.md` (continue/restart, через `DraftManager`), иначе — `find_previous_sr` → `extract_kr_framework` → `load_kr_batch` → `find_new_krs` → построение `DraftState` → сохранение черновика → создание брифа.
- [ ] `finalize_plan(ctx: PlanContext) -> PlanResult` — заливка через `TRANSITION_START_OF_PERIOD` (transition 61, из `jira_client.py`), verification-запрос `GET` по `customfield_44401-44403` (§10.3.8), финализация `_plan_draft.md` → `{SR-KEY}_{период}.md`.
- [ ] `run(sr_key, jira_client, settings, *, target_pct_flag=50, fix_version=None, no_taskrefresh=False, dry_run=False, answer_fn=None, draft_choice_fn=None) -> PlanResult` — аналог `selfcheck.run`, полный флоу с обработкой `--dry-run` (шаги 1-6 без брифа/заливки — печать `_plan_draft.md` и выход) и `--no-taskrefresh`.

### Зависимости
- `jira_client.py` (`search`, `batch_search_issues`, `post_transition`, `get_transitions`, `TRANSITION_START_OF_PERIOD`).
- `okr_cache.py` (`get_quarter`, `load_okr_from_cache`, `save_okr_cache`).
- `draft_manager.py` (расширенный `DraftManager`/`DraftState`, см. §6).
- `brief.py` (расширенный `BriefSession` или новый режим, см. §5).
- `task_mapper.py` (`extract_project_tag`, переиспользование).
- `config.py` (`Settings.okr_cache_dir`, `Settings.default_target_pct`).
- Не зависит от `selfcheck.py` / `preview.py` (независимый сценарий, per §10.9).

### Тесты (`tests/test_plan.py` — новый файл, по аналогии с `test_selfcheck_flow.py`)
- [ ] `test_find_previous_sr_returns_key` — мок `jira_client.search` возвращает issue, проверить JQL содержит `assignee`, `!= "Оценка установлена"`.
- [ ] `test_find_previous_sr_raises_when_empty` — пустой `issues` → `PreviousSRNotFound`.
- [ ] `test_extract_kr_framework_parses_numbered_keys` — на реальном примере формата Блока 3 (взять из фикстур `conftest.py`, дополнить).
- [ ] `test_extract_kr_framework_raises_on_empty` → `EmptyFramework`.
- [ ] `test_calc_target_pct_below_100` — пример из ТЗ: `current=40, flag=50 → target=70`.
- [ ] `test_calc_target_pct_already_100` — `current_pct=100 → 100`.
- [ ] `test_calc_target_pct_flag_variations` — `flag=0` (без прироста) и `flag=100` (сразу 100%).
- [ ] `test_load_kr_batch_uses_cache_first` — часть ключей в кэше (мок `okr_cache`), часть — нет; проверить, что `batch_search_issues` вызван только с недостающими.
- [ ] `test_load_kr_batch_saves_fresh_to_cache` — после батч-запроса `save_okr_cache` вызван для новых ключей.
- [ ] `test_find_new_krs_excludes_framework_keys` — проверить JQL содержит `NOT IN`.
- [ ] `test_begin_plan_no_existing_draft` — полный путь без `_plan_draft.md`, все шаги 1-6 отработали.
- [ ] `test_begin_plan_existing_draft_continue` / `test_begin_plan_existing_draft_restart` — по аналогии с `begin_report`.
- [ ] `test_run_previous_sr_not_found_message` — CLI-уровневая проверка (или на уровне `run`) — понятное сообщение с подсказкой про v1.1 TG-флоу (§10.3.1 последний абзац).
- [ ] `test_run_dry_run_no_jira_write` — `dry_run=True` → `jira_client.post_transition` не вызван.
- [ ] `test_finalize_plan_posts_transition_61` — не 271.
- [ ] `test_finalize_plan_verification_get_called_once` — ровно 1 verification-запрос после заливки.
- [ ] `test_suggest_followup_tasks_maps_tags_to_pages`.

### Чекпоинт CP3: `plan.py` до брифа (шаги 1-6, `--dry-run`)
- **Критерий:** `srtool plan SR-XXXXX --dry-run` (или прямой вызов `run(..., dry_run=True)` в тесте) печатает валидный `_plan_draft.md`-контент, НЕ пишет в Jira, НЕ создаёт файл. Юнит-тесты на `find_previous_sr`, `extract_kr_framework`, `calc_target_pct`, `load_kr_batch`, `find_new_krs` зелёные. Ручная проверка на одном реальном SR-ключе (dry-run) — сверить каркас с реальным Блоком 3.

### Чекпоинт CP5 (после CP4 брифа): полный флоу + заливка
- **Критерий:** `srtool plan SR-XXXXX` на тестовом/реальном SR проходит бриф до конца, заливает transition 61, верифицирует, финализирует `_plan_draft.md → {SR-KEY}_{период}.md`, опционально предлагает follow-up задачи. Ручная проверка на реальном Jira (или staging) — поля 44401-44403 действительно записались.

---

## 5. `brief.py` — расширение для режима plan (§10.3.7)

### Проблема совместимости
Текущий `BriefSession` жёстко заточен под selfcheck: `_STEP_*` константы, порядок шагов (`criterion → mapping → status → reason → extension → control → problems → solutions → extra`), `_tasks_for`/`_task_mapping` (авто-маппинг задач) — не применимы к брифу плана (§10.3.7: подтверждение/правка формулировки результата+критерия, для новых KR — с нуля).

### Изменения
- [ ] Ввести общий подкласс/сестринский класс — рекомендация: **не расширять `BriefSession`**, а добавить `PlanBriefSession` в `brief.py` рядом (аналогичный интерфейс `next_prompt()`/`submit_answer()`/`is_complete()`, чтобы `cli.py` мог использовать общий цикл, как в текущем `report`-команде), но с собственными шагами:
  - `_STEP_PLAN_ITEM` — показ пункта каркаса (ключ, было%, авторасчётная цель).
  - `_STEP_PLAN_RESULT` — подтверждение/правка формулировки результата.
  - `_STEP_PLAN_CRITERION` — подтверждение/правка критерия (если не деривируется автоматически — сверить с §10.3.6 "деривация из блока 1 использует derive_block2/derive_block3, логика не дублируется" → уточнить на CP4, входит ли текст критерия в бриф вручную или чисто из авто-деривации после брифа Блока 1).
  - Для новых KR (`is_new=True`) — доп. шаг запроса формулировки "с нуля" вместо показа "было %".
- [ ] `PlanBriefStep` (датакласс, аналог `BriefStep`) — `prompt_text`, `step_type`, `framework_idx`.
- [ ] Автосохранение в `_plan_draft.md` после каждого ответа — через `DraftManager` (расширенный, см. §6), тот же паттерн, что `BriefSession.submit_answer` → `self.draft_manager.save(self.state)`.

### Зависимости
- `draft_manager.py` (расширенный `DraftState`/новый `PlanDraftState` — см. §6).
- Не зависит от `task_mapper.py` (нет авто-маппинга задач в режиме plan — там маппинг KR→формулировка, не задача→критерий).

### Тесты (добавить в `tests/test_brief.py` или новый `tests/test_plan_brief.py`)
- [ ] `test_plan_brief_shows_framework_item_with_was_and_target_pct`.
- [ ] `test_plan_brief_new_kr_asks_from_scratch` — для `is_new=True` пропускается "было %", запрашивается формулировка с нуля.
- [ ] `test_plan_brief_autosaves_after_each_answer` — мок `DraftManager.save` вызван после каждого `submit_answer`.
- [ ] `test_plan_brief_is_complete_after_all_items`.

### Чекпоинт CP4: бриф плана изолированно
- **Критерий:** `pytest tests/test_plan_brief.py` зелёный; ручной прогон брифа на 2-3 синтетических пунктах каркаса (включая один "новый KR") через `answer_fn` в тесте — все ветки (было/новый) проходятся без исключений.
- Здесь же — решить открытый вопрос: деривация критерия (Блок 2) вручную в брифе или полностью автоматически после ввода Блока 1 (рекомендация: по аналогии с v1.1 — **не спрашивать критерий отдельно**, деривировать автоматически через существующий `derive_block2`-эквивалент; но в текущем коде `derive_block2`/`derive_block3` из ТЗ v1.1 §4.3-4.4 **не перенесены в `srtool/` как отдельные функции** — они существовали в `sr_fields.py`/`draft_generator.py` по структуре ТЗ v1.1 §3, но в реальном каталоге `srtool/` этих файлов НЕТ (см. §7 ниже, gap-анализ) — нужно решить: портировать их в `plan.py` или писать заново).

---

## 6. `draft_manager.py` — расширение для `_plan_draft.md`

### Проблема
`DraftManager`/`DraftState`/`CriterionDraft` жёстко привязаны к selfcheck-домену (`status: done|partial|not_done|pending`, `mapped_task_ids`, `problems` и т.д. — поля из §3.3 v2.0). Формат `_plan_draft.md` (§10.3.6) — другой: таблица каркаса (№/Ключ/Было%/Цель%/Статус) + заготовки Блоков 1-3, без критериев-по-статусам.

### Изменения (минимально невмешательные — не трогать существующие selfcheck-тесты)
- [ ] Добавить новый датакласс `PlanFrameworkItem` в `draft_manager.py` (или импортировать из `plan.py` — решить направление зависимости на CP3, чтобы не было цикла `plan.py ↔ draft_manager.py`; рекомендация: датакласс определяется в `draft_manager.py` как более общий "хранитель форматов", `plan.py` его импортирует — тот же паттерн, что `selfcheck.py` импортирует `CriterionDraft` из `draft_manager.py`).
- [ ] Добавить `PlanDraftState` (параллельно `DraftState`, не наследование — избежать хрупкой связанности): `sr_key`, `period`, `previous_sr_key`, `framework: list[PlanFrameworkItem]`, `block1_draft: str`, `block2_draft: str`, `block3_draft: str`, `followup_confirmed: bool`.
- [ ] Расширить `DraftManager` методами (сохранив текущие `save`/`load`/`finalize` для selfcheck нетронутыми — либо через параметр `mode: Literal["selfcheck","plan"]`, либо новый класс `PlanDraftManager(DraftManager)`):
  - Рекомендация: **новый класс `PlanDraftManager`** в этом же файле, переиспользующий только `path`/`final_path`/`exists`/атомарную запись (можно выделить общий `_atomic_write` helper вместо дублирования), но с собственным `_serialize`/`load` под формат §10.3.6 (таблица каркаса + Блоки 1-3), и собственным `path` = `{sr_key}_{period}_plan_draft.md`.
  - `progress_summary` — по аналогии, но считает "N из M пунктов каркаса" вместо "критериев".

### Зависимости
- Не зависит от новых файлов. От неё зависят `plan.py`, `brief.py` (расширение).

### Тесты (`tests/test_plan_draft_manager.py` — новый файл)
- [ ] `test_serialize_plan_draft_format` — таблица каркаса рендерится корректно (заголовки столбцов, `[новый]` пометка).
- [ ] `test_save_and_load_roundtrip_plan_draft`.
- [ ] `test_progress_summary_plan` — "N из M пунктов".
- [ ] `test_finalize_renames_to_final_md` — `_plan_draft.md` → `{key}_{период}.md`, пометка черновика снята.
- [ ] `test_path_uses_plan_draft_suffix` — путь оканчивается на `_plan_draft.md`, не `_draft.md`.

### Чекпоинт: входит в CP3 (тестируется вместе с `plan.py`, не отдельная веха).

---

## 7. `cli.py` — subcommand `plan`

### Изменения
- [ ] Добавить команду:
  ```python
  @cli.command()
  @click.argument("sr_key")
  @click.option("--target-pct", type=int, default=None)
  @click.option("--fix-version", type=str, default=None)
  @click.option("--no-taskrefresh", is_flag=True, default=False)
  @click.option("--dry-run", is_flag=True, default=False)
  def plan(sr_key, target_pct, fix_version, no_taskrefresh, dry_run):
      """Автопланирование начала периода (блоки 1-3, transition 61)."""
  ```
- [ ] Резолвинг `target_pct` — если `None`, использовать `settings.default_target_pct` (см. §3).
- [ ] Обработка `PreviousSRNotFound`/`EmptyFramework` (импорт из `plan.py`) — понятное сообщение в `click.echo(..., err=True)` + `SystemExit(2)`, по аналогии с текущей обработкой `RuntimeError` в команде `report`.
- [ ] `--dry-run`: вызов `run(..., dry_run=True)`, вывод содержимого `_plan_draft.md` в stdout, без интерактивного цикла.
- [ ] Не-dry-run: интерактивный цикл `next_prompt()`/`submit_answer()`, аналогичный существующему в команде `report` (переиспользовать структуру цикла, не копипастить логику ретрая `ValueError` — возможно, выделить общий helper `_run_interactive_brief(session)` и использовать в обеих командах `report` и `plan`, устраняя текущее дублирование).
- [ ] После `finalize_plan` — если не `--no-taskrefresh` и есть предложения (`suggest_followup_tasks`), вывести список и запросить `click.confirm`/инлайн правку (§10.6) — вызов `taskrefresh` как внешней зависимости (аналогично тому, как `cli.py` уже импортирует `ConfluenceClient` из `confluencesync` — здесь по аналогии импортировать клиент/функцию из пакета `taskrefresh`, если он установлен как библиотека; если `taskrefresh` не является импортируемым пакетом (только CLI-скрипт `./tr`) — вызывать через `subprocess`, уточнить на CP4/CP5, какой способ интеграции реален).

### Зависимости
- `plan.py` (`run`, `begin_plan`, `finalize_plan`, исключения).
- Существующий паттерн `_clients(settings)` — переиспользовать без изменений (JiraClient + ConfluenceClient уже создаются там; для `plan.py` Confluence не нужен для основного флоу, но может понадобиться для follow-up интеграции с TaskRefresh — уточнить).

### Тесты (расширить `tests/test_cli.py`)
- [ ] `test_plan_command_dry_run_no_jira_write` — через `CliRunner`, мок `plan.run`.
- [ ] `test_plan_command_previous_sr_not_found_exit_code_2`.
- [ ] `test_plan_command_target_pct_default_from_settings`.
- [ ] `test_plan_command_no_taskrefresh_flag_skips_suggestion`.

### Чекпоинт CP5 (совмещён с §4): 
- **Критерий:** `srtool plan --help` показывает все флаги с верными defaults; `pytest tests/test_cli.py` зелёный; сквозной прогон `srtool plan SR-XXXXX --dry-run` в реальном окружении (или на mock-сервере) завершается без traceback.

---

## 8. Gap-анализ: чего в реальном коде нет, но ТЗ §10.3.6 на это ссылается

⚠️ **Важно выявленное при чтении кода несоответствие ТЗ и реальности**, требует решения до начала CP3:

ТЗ §10.3.6 говорит: "Генерация блоков 2 и 3 из черновика Блока 1 использует те же функции `derive_block2` / `derive_block3` (§4.3-4.4), что и v1.1 — логика деривации не дублируется." Однако в текущем каталоге `~/USERTOOLS/SRTool/srtool/` **функций `derive_block2`/`derive_block3` не существует** — они описаны в ТЗ v1.1 §3-4 как часть `sr_fields.py`/`draft_generator.py`/`okr_loader.py`, но эти файлы физически отсутствуют в проекте (в наличии только `jira_client.py`, `cli.py`, `config.py`, `confluence_sources.py`, `draft_manager.py`, `formatting.py`, `preview.py`, `selfcheck.py`, `task_mapper.py`, `brief.py`, `__init__.py`, `__main__.py`). Похоже, что v1.1 TG-флоу выполняется не через этот Python-пакет, а через отдельный скилл/Сирень напрямую (§2 ТЗ v1.1: "Сирень... Генерирует черновик блока 1... Автоматически генерирует блоки 2 и 3" — без указания, что это тот же код).

**Действие перед CP3:** уточнить у пользователя:
1. Нужно ли портировать `derive_block2`/`derive_block3` в `plan.py` (новая реализация по regex из §4.3-4.4 ТЗ v1.1) — вероятно, ДА, так как `srtool plan` — CLI-команда этого пакета, ей нужна собственная деривация, а не внешний скилл Сирени.
2. Либо этот функционал остаётся вне Python-пакета (деривация делается LLM-агентом до вызова `srtool plan`, а `plan.py` получает уже готовые блоки 2/3 как вход) — тогда часть §10.3.6 из плана выше (генерация Блока 2/3) не нужна в `plan.py`, только Блок 1 + каркас.

Рекомендация: включить `derive_block2`/`derive_block3` как новые функции в `plan.py` (портировать по regex из ТЗ v1.1 §4.3-4.4 буквально), так как весь остальной пайплайн (`begin_plan`/`finalize_plan`/заливка transition 61) явно ожидает работать полностью внутри `plan.py` без внешнего агента в цикле верификации (§10.3.8 требует программной GET-верификации после заливки — значит, весь флоу самодостаточен).

### Тесты
- [ ] `test_derive_block2_extracts_criteria` — на примере из ТЗ v1.1 §4.3.
- [ ] `test_derive_block3_extracts_okr_with_summary` — на примере из ТЗ v1.1 §4.4, мок `jira_client.get_issue`.

### Чекпоинт CP0 (перед CP1): решить gap
- **Критерий:** явное решение зафиксировано (в этом файле или отдельной заметке) — портировать `derive_block2`/`derive_block3` в `plan.py` или оставить вне пакета. Без этого решения `build_plan_draft_state`/`generate_plan_draft_md` не могут быть реализованы корректно.

---

## 9. Итоговая последовательность чекпоинтов

| № | Чекпоинт | Файлы | Блокирует |
|---|---|---|---|
| CP0 | Решить gap `derive_block2/3` (§8) | — (решение) | CP3 |
| CP1 | `jira_client.batch_search_issues` + `search` работают, field ID для `pct` подтверждён | `jira_client.py` | CP3 |
| CP2 | `okr_cache.py` изолированно работает, путь `cache_dir` согласован | `okr_cache.py`, `config.py` | CP3 |
| CP3 | `plan.py` шаги 1-6 + `--dry-run`, `PlanDraftManager` | `plan.py`, `draft_manager.py` | CP4 |
| CP4 | Бриф плана (`PlanBriefSession`), решён вопрос ручного/авто критерия | `brief.py` | CP5 |
| CP5 | Полный флоу `srtool plan`, заливка transition 61, verification, follow-up | `cli.py`, `plan.py` | релиз |

## 10. Итоговый список файлов

**Новые:**
- `srtool/okr_cache.py`
- `srtool/plan.py`
- `tests/test_jira_client.py`
- `tests/test_okr_cache.py`
- `tests/test_plan.py`
- `tests/test_plan_brief.py`
- `tests/test_plan_draft_manager.py`

**Изменённые:**
- `srtool/jira_client.py` (+ `search`, `batch_search_issues`, `TRANSITION_START_OF_PERIOD`)
- `srtool/config.py` (+ `okr_cache_dir`, `default_target_pct`)
- `srtool/draft_manager.py` (+ `PlanFrameworkItem`, `PlanDraftState`, `PlanDraftManager`)
- `srtool/brief.py` (+ `PlanBriefSession`, `PlanBriefStep`)
- `srtool/cli.py` (+ subcommand `plan`, возможный рефакторинг общего интерактивного цикла)
- `tests/test_cli.py` (+ тесты команды `plan`)
- `tests/conftest.py` (+ фикстуры: `fake_previous_sr_issue`, каркас Блока 3, mock для `okr_cache`)

**Не создаются (отход от буквального §10.7 ТЗ, см. §0):** `plan_finder.py`, `pct_calculator.py`, `plan_generator.py`.

**Не трогаются:** `confluence_sources.py`, `formatting.py`, `preview.py`, `selfcheck.py`, `task_mapper.py` (только читаются/переиспользуются функции `extract_project_tag`), `__init__.py`, `__main__.py`.
