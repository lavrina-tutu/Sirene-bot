# План HF:impl — §29 Per-task entity tag (`task_slug`)

Кейс: **CHANGE / DEV/pfs-task-human-slug**. Фаза: **HF:plan**. Архитектор: cursor-grok-4.6-high.
Исполнитель следующих фаз: composer-2.5. Код в этой фазе **не** писать.

Канон: `WorkVault/Hermes-Backlog/TZ/ProtocolFromSummary/ProtocolFromSummary_TZ.md` **v1.26.3 §29**.
Номера AC-001…015 — канон секции (не описка диагноз-плана). §30 — референт: литералы `DEDUP_LLM_*` / `LLM_FALLBACK_*` **не этот CHANGE**.
Рабочие директории:

- `/home/tkachenkoav/USERTOOLS/ProtocolFromSummary`
- `/home/tkachenkoav/USERTOOLS/EntityRegistryCLI`
- `/home/tkachenkoav/USERTOOLS/TaskRefresh`
- `/home/tkachenkoav/WorkVault/Registries/` (schema, `entities.json`, `prompts/`)

---

## 0. РЕЗЮМЕ ДИСКА (не переписывать работающее)

| Место | Факт с диска (проверено чтением 27.09) | §29 |
|---|---|---|
| `pipeline.py:202` `_dedup_llm_fn(prompt: str) -> str` | Единственная LLM-обёртка; читает `LLM_CONFIG` + `DEDUP_LLM_TIMEOUT` / routing / reasoning. Fail-soft → `""`. `_haiku_fn = _dedup_llm_fn` | AC-008: reuse, не второй клиент |
| `pipeline.py:232` `_post_switch_pass_one` | `render_row(..., tag_prefix=route.tag_prefix, ...)` на `:269`. Picker нет | Точка 2 вызова render; picker — **до** этого, в `run_pilot` |
| `pipeline.py:372` `run_pilot` | Резолв mention/дедлайн `:417–468` → пост-switch fork `:489` → DedupChecker `:555–595` → `render_row` `:597` + `render_content_block` `:616` с `tag_prefix=route.tag_prefix` | Picker вставить **после** `:468`, **до** fork `:470` |
| `pipeline.py:988` `protocol_publish` | Тонкий alias на `run_pilot`, сигнатура заморожена | Не дублировать логику |
| `storage_xml.py:40` `_task_body(task, resolved, deadline, tag_prefix)` | При `tag_prefix`: `mention + " " + tag_prefix + " " + text`. Сигнатура 4 аргумента | **Не менять**. In-scope: `tag_prefix=None`, префикс уже в `task.text` |
| `storage_xml.py:260` `render_row` | Один `tag_prefix` на всю строку, не per-task | In-scope после picker: всегда `None`; префиксы живут в `MeetingTask.text` |
| `prompt_loader.py:24` `_ID_TO_FILE` | Только `pfs_task_dedup` / `pfs_section_dedup` / `pfs_risk_dedup`. `registry_disabled()` читает `PFS_PROMPT_REGISTRY_OFF` | Добавить `pfs_task_slug`; kill-switch не плодить |
| `prompt_registry_cli.py:17` `CANON_IDS` | 5 id. `write_entry` отказывает unknown id | Добавить `pfs_task_slug` |
| `Registries/prompts/prompt.schema.json` | enum id без `pfs_task_slug` | Добавить в enum |
| `dedup.py:146` `_parse_task_text` | Комментарий «без tag_prefix», код стрипает только HTML/`<time>` — префикс остаётся в `PublishedTask.text` | AC-013: снять known prefixes |
| `dedup.py:358` `check_tasks` | `_fuzzy_ratio(task.text, pub_task.text)` as-is | Стрипать префиксы с обеих сторон |
| `playground_promote.py:399` `promote_meeting` | Копирует td1; DedupChecker через `_promote_dedup_minutes_against_target` (`:230`, `llm_fn=_dedup_llm_fn`). Picker нет | AC-012: assert 0 вызовов picker (не путать с LLM дедупа) |
| `entities.schema.json` | `additionalProperties: false` на записи. Поля `task_slug` нет. Блок `pfs` тоже `additionalProperties: false` | Слаг — **корень** записи, не `pfs.task_slug` |
| `entities.json` | `schema_version="1.2"`, 47 сущностей, **18** `kind=project` с непустым `pfs.tag`, 1 проект без pfs (`Contracts`). `ai_analitik.pfs.tag="AI-аналитик."`. `lenya_1on1` kind=`person_1on1`, tag=`Лёня 1-1.` | Backfill 18; Contracts → WARNING; schema_version не бампить |
| `EntityRegistryCLI/.../validator.py` | `Issue(code, message)` без severity. Любой Issue → exit 2 и блок `_write_and_backup` | Канал WARNING, иначе CLI станет красным на каждом edit |
| `taskrefresh/project_registry.py:96` `match_by_text` | Только `entry["tag"]` (`pfs.tag`). `_adapt_entities_to_registry` не копирует `task_slug` | AC-011: OR `task_slug` |
| `taskrefresh/filters.py:46` `_annotate_project` | Порядок **text → page_id**. Не менять | AC-011 |
| `_load_llm_config` / литералы модели | Inline `"deepseek/deepseek-v4-flash-0731"` + URL + `"tutu"` | §30, не этот граф |

**Инвариант last-resort LLM:** picker потребляет `LLM_CONFIG` / `_dedup_llm_fn` as-is. Новых литералов модели/URL/ключа в diff этого CHANGE нет.

**Инвариант mixed-batch (единственный способ не ломать `_task_body`):** `render_row` принимает один `tag_prefix` на строку. Во встрече часть задач может получить `task_slug`, часть — fail-soft с meeting-level `pfs.tag` (Лёня). Поэтому in-scope после picker:

1. выбранный слаг → `task.text = task_slug + task.text` (без пробела после точки);
2. fail-soft при непустом `route.tag_prefix` → `task.text = route.tag_prefix + " " + task.text` (как сейчас делает `_task_body`);
3. fail-soft без `tag_prefix` → текст as-is;
4. в `render_row` / `render_content_block` передать **`tag_prefix=None`**.

Иначе либо двойной префикс (slug в тексте + meeting tag в `_task_body`), либо потеря fallback Лёни.

---

## 1. ИТОГОВАЯ РЕКОМЕНДАЦИЯ (one-pass)

Новый модуль `protocolfromsummary/task_slug.py` (рядом с `dedup.py`, не раздувать `pipeline.py`). Один batch LLM на in-scope встречу через `_dedup_llm_fn`. Фильтр входа `startswith` по всем непустым `task_slug` ∪ `pfs.tag`. Kill-switch — только существующий `PFS_PROMPT_REGISTRY_OFF`. Поле — `entities.<slug>.task_slug` (корень). Писатель — EntityRegistryCLI `-y` (схема + WARNING + backfill 18 проектов). TaskRefresh F2 матчит `pfs.tag` **или** `task_slug`. Promote (проход 2) picker не импортирует. Сигнатуры боевого пути не менять. Кроны / Gateway / `.env` / `jobs.json` / `EcosystemManifest` / bump `schema_version` — вне раунда.

---

## 2. ЧТО НЕ ТРОГАТЬ (жёсткий список)

Сигнатуры (байт-в-байт, AC-014):

```
protocol_publish(summary_path, *, confirm_republish=False, dry_run=False, today=None, registry=None, confluence=None, store=None, llm_fn=None)
process_pending(...)          # отбор, не тело публикатора
resolve_route(...)            # route.py
row_anchor_for(...)
page_merger.*                 # все публичные функции
storage_xml._task_body(task, resolved, deadline, tag_prefix)
```

Также не трогать:

- `summary_parser._SECTION_NAMES`, `MeetingSummary.notes`, `_strip_bold`, поля dataclass `MeetingTask` (новых полей нет; `.text` мутировать in-place/через replace tuple — да).
- Алгоритмы §15 (порог 0.80, окно 3 недели, per-candidate assignee, severity) — кроме снятия known prefixes с текста.
- Канон §24/§27/§28 (пост-switch, sink_aid, защита правок Саши).
- MOFS / frontmatter `project_bind`. Grep `task_slug` в `USERTOOLS/MarkObjectsFromSummary` после impl = пусто (AC-009).
- `jobs.json`, `.env`, Gateway, `EcosystemManifest.json` / digest.
- Литералы `DEDUP_LLM_*` и fail-soft дефолты `_load_llm_config` (§30).
- Dual-render §22, AnywhereContacts, `contacts.enc`.
- Запись `523032632` в `pfs.page_id`. N-3 (не удалять в Confluence).
- Kill-switch `PFS_PROMPT_STORE` — **не создавать**.
- Бамп `schema_version` `entities.json` (факт диска `"1.2"`) и `_registry.json` (`"1.1"`).

---

## 3. ШАГИ 0–5 (Impl-привязка §29, атомарно, пофайлово)

Порядок обязателен: схема → промпт → picker → точки вызова → TaskRefresh → freeze-проверки.

### Шаг 0 — ER: поле `task_slug`, WARNING, backfill CLI `-y`

Покрывает: **AC-010, AC-004** (известные префиксы после backfill).

#### 0.1. `WorkVault/Registries/entities.schema.json`

**Роль.** Optional property на **корне записи** (patternProperties сущности). В блок `pfs` **не** класть (`additionalProperties: false` у `pfs` не расширять).

**Правка.** В `properties` сущности, рядом с `display_name` / `aliases`:

```json
"task_slug": {
  "type": ["string", "null"],
  "description": "человекочитаемый префикс задачи с хвостовой '.' без пробела"
}
```

`required` не расширять. `schema_version` в JSON-Schema не бампить (его там нет как semver артефакта; корневой `entities.json.schema_version` тоже не бампить).

**Не трогать:** `pfs.additionalProperties`, инвариант `(page_id, tag)`, запрет `523032632`.

#### 0.2. `EntityRegistryCLI/entityregistrycli/validator.py`

**Роль.** Канал WARNING + инварианты `task_slug`.

**Не ломать:** существующий `Issue(code, message)` для fail-кейсов. Тесты ищут `duplicate_pfs_key` / `broken_parent` в stderr.

**Правки:**

1. Расширить dataclass (default сохраняет старое поведение):

```python
@dataclass
class Issue:
    code: str
    message: str
    severity: str = "fail"  # "fail" | "warning"
```

`__str__` оставить `f"[{self.code}] {self.message}"` — не ломать grep тестов.

2. В `validate_invariants` (после существующих блоков, не меняя их) добавить `task_slug`-правила:

| Условие | code | severity |
|---|---|---|
| `kind=project` и (`task_slug` отсутствует / JSON `null` / `""` после strip) | `task_slug_missing` | **warning** |
| `kind=project` и задан `task_slug`, нет хвостовой `.` | `task_slug_no_dot` | fail |
| `kind=project` и задан `task_slug`, содержит пробел | `task_slug_space` | fail |
| `kind ∈ {one_on_one, person_1on1, person}` и непустой `task_slug` | `task_slug_forbidden_kind` | fail |
| два **заполненных** `task_slug` совпадают (после strip; регистр — как в файле, сравнение точное) | `task_slug_duplicate` | fail |

Пустой закрытый список (все проекты без слага) — это набор WARNING, не fail.

3. Хелпер для CLI/записи (чтобы не дублировать фильтр):

```python
def fail_issues(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity != "warning"]
```

**Сигнатуры:** `validate_schema` / `validate_invariants` / `validate_all` **не менять**.

#### 0.3. `EntityRegistryCLI/entityregistrycli/cli.py`

**`_write_and_backup` (`:41`).** Сейчас `if issues: raise EXIT_VALIDATION`. После шага 0.2 любой проект без слага блокировал бы **все** последующие `edit`/`add`. Правило:

- `fails = fail_issues(issues)`; если `fails` — как сейчас raise;
- warnings — не блокируют запись (можно `print` в stderr, не обязательно).

**`_cmd_validate` (`:484`).** Печатать все Issue. Если есть fail → exit 2. Если только warning → печатать `WARNING` + `validate: ok with N warnings` → **exit 0**.

**Не трогать:** argparse существующих команд, exit-коды 0/1/3/4/5.

#### 0.4. `EntityRegistryCLI/entityregistrycli/operations.py` + CLI-команда backfill

**Роль.** Единственный writer `task_slug` (не PFS).

**Новая чистая функция** (имя зафиксировать):

```python
def backfill_task_slug(instance: dict) -> tuple[dict, dict]:
    """Для kind=project с непустым pfs.tag: если task_slug отсутствует/null/'' —
    поставить task_slug = pfs.tag. Идемпотентно. Значений не выдумывать.
    Возвращает (new_instance, stats{updated:int, skipped:int, unchanged:int}).
    """
```

- Не трогать `Contracts` и прочие project без `pfs.tag`.
- Не затирать уже заданный отличающийся `task_slug`.
- Не бампить `schema_version`.

**CLI.** Новая подкоманда (не плодить отдельный USERTOOL):

```
entity-registry backfill-task-slug -y
```

Без `-y` — refuse (как `edit` для pfs / prompt-registry). С `-y`: load → `backfill_task_slug` → `_write_and_backup` (warnings не блокируют) → audit_log `backfill-task-slug`. На живом реестре ожидаемо `updated=18` при первом прогоне, `updated=0` при втором (идемпотентность).

`SchemaIntrospector` менять не нужно: после 0.1 `task_slug` сам появится в `list_fields()` / `edit <slug> task_slug <value> -y`.

#### 0.5. Фикстура схемы тестов ERC

Файл `EntityRegistryCLI/tests/fixtures/entities.schema.json` — **урезанная копия**, не live WorkVault. Добавить то же optional `task_slug` в properties сущности фикстуры (иначе тесты, пишущие поле, падут на `additionalProperties`). Kind-enum фикстуры можно не синхронизировать с live (для AC-010 хватает `one_on_one`).

Live `entities.json` в этом шаге пишет **только** CLI `-y` (0.4), не руками и не из PFS.

**Точка проверки шага 0:** `entity-registry validate` на копии реестра без слагов → exit 0 + WARNING `task_slug_missing`; `kirill`/`one_on_one` с `task_slug="X."` → exit 2; backfill дважды → второй раз 0 updates; `schema_version` живого файла остаётся `"1.2"`.

---

### Шаг 1 — Промпт `pfs_task_slug` + loader + kill-switch

Покрывает: **AC-015** (и инфраструктура AC-007/008).

Это **не** сущность графа. Новые файлы конфигурации/реестра:

| Путь | Что |
|---|---|
| `/home/tkachenkoav/WorkVault/Registries/prompts/pfs_task_slug.json` | канон промпта, писатель CLI `-y` |
| `/home/tkachenkoav/WorkVault/Registries/prompts/prompt.schema.json` | enum `id` += `pfs_task_slug` |
| `protocolfromsummary/prompt_loader.py` | `_ID_TO_FILE` += `"pfs_task_slug": "pfs_task_slug.json"` |
| `protocolfromsummary/prompt_registry_cli.py` | `CANON_IDS` += id; `default_catalog()` += draft body |

#### 1.1. Контракт JSON промпта (как `pfs_task_dedup.json`)

Поля: `id`, `tool="protocolfromsummary"`, `name`, `version="1.0.0"`, `body`, `updated_at`. Писать через:

```
python -m protocolfromsummary.prompt_registry_cli write \
  --id pfs_task_slug --tool protocolfromsummary \
  --name "PFS per-task entity tag" --version 1.0.0 \
  --body-file <draft.md> --yes
```

**Тело `body` (норматив §29 «Приложения»):**

- Роль: для каждой задачи **в переданном batch** (уже после фильтра входа) выбрать ровно один `entity_slug` из закрытого списка; вернуть канонический `task_slug` этой записи.
- Запрет: выдумывать префикс; выбирать 1-1 / non-project; оставлять пустым из-за низкой уверенности.
- Плейсхолдеры: `{meeting_name}`, `{notes}`, `{participants}`, `{closed_list_json}`, `{tasks_json}`.
- Выход: **строго JSON-массив**, по одной записи на каждую отправленную задачу:
  `{"task_index": N, "entity_slug": "...", "task_slug": "...", "confidence": 0..1}`
  где `N` — индекс в **отправленном** списке (0-based), не в полном списке встречи.

Константу-промпт в Python **не** использовать как «всё равно сходить в модель» при kill-switch. Draft в `default_catalog()` — только для `write`/`init`, не для runtime LLM при `PFS_PROMPT_REGISTRY_OFF`.

#### 1.2. `prompt_loader.py`

Добавить (имя зафиксировать):

```python
def resolve_task_slug_prompt(*, prompts_dir: Path | None = None) -> str | None:
    """None = picker не вызывать (kill-switch / нет файла / битый JSON).
    Не подменяет fallback-константой, чтобы всё равно звать LLM.
    """
```

- `registry_disabled()` True → `None` (0 LLM).
- Иначе `_read_body(..., "pfs_task_slug")` (reuse существующего reader).
- `resolve_dedup_prompts` **не менять**.

#### 1.3. `prompt.schema.json` + `CANON_IDS`

Иначе `write --id pfs_task_slug` отвергнется (`unknown id`) и schema-validate реестра промптов тоже.

**Точка проверки шага 1:** `PFS_PROMPT_REGISTRY_OFF=1` → `resolve_task_slug_prompt() is None`; файл на месте, флаг off → non-empty body; unknown id в CLI по-прежнему 2, новый id пишется с `-y`.

---

### Шаг 2 — Picker (in-scope, фильтр входа, batch, лучший кандидат)

Покрывает: **AC-001, AC-002, AC-003, AC-004, AC-005, AC-006, AC-007, AC-008**.

#### 2.1. Новый файл `protocolfromsummary/task_slug.py`

Публичные имена зафиксировать (исполнителю не переименовывать — на них якорятся тесты):

```python
IN_SCOPE_KINDS = frozenset({"one_on_one", "person_1on1", "unknown", "sync_aid"})

def route_in_scope(route) -> bool:
    """kind ∈ IN_SCOPE_KINDS OR entity == 'lenya_1on1'."""

def load_entities(path: Path | None = None) -> dict:
    """Читает entities.json; fail-soft → {}."""

def closed_list(entities: dict) -> list[dict]:
    """kind=project AND nonempty task_slug.
    Элемент: {slug, task_slug, display_name, aliases}.
    Не входят: 1-1 / person_1on1 / person / tool / misc / sync_aid / unknown / project без слага.
    """

def known_prefixes(entities: dict) -> list[str]:
    """Все непустые task_slug и pfs.tag, unique, sort key=(-len, s) — длинный первым."""

def text_has_known_prefix(text: str, prefixes: list[str]) -> bool:
    """startswith as-is (п.5 Scope). Не lower-case как единственный путь:
    сравнивать и точный префикс, и prefix.lower() vs text.lower() — F2/идемпотентность
    при расхождении регистра (AI-аналитик. vs ai-аналитик.)."""

def strip_known_prefix(text: str, prefixes: list[str]) -> str:
    """Снимает ровно один ведущий известный префикс (самый длинный). Для дедупа."""

def apply_task_slugs(
    *,
    route,
    summary,           # MeetingSummary: meeting_name, notes, participants
    resolved_tasks: list[tuple],  # (MeetingTask, resolved, deadline)
    llm_fn,            # Callable[[str], str] | None — тот же _dedup_llm_fn
    entities: dict | None = None,
) -> list[tuple]:
    """In-scope: фильтр входа → 0|1 LLM → дописывание слага в MeetingTask.text.
    Out-of-scope: вернуть resolved_tasks без изменения, 0 LLM.
    Возвращает новый список tuple (не мутировать исходный task, если это тот же объект summary —
    заменить MeetingTask новым экземпляром с новым .text).
    """
```

**Семантика `apply_task_slugs` (строго §29-ordering п.1–4):**

1. Если `not route_in_scope(route)` → return as-is, **0** вызовов `llm_fn`. (AC-002)
2. Kill-switch / `resolve_task_slug_prompt() is None` / пустой `closed_list` / `llm_fn is None` → **не** звать LLM. Для каждой задачи: fail-soft префикс = `route.tag_prefix + " "` если tag есть, иначе без префикса. ErrorBus warning (шаг 2.3). (AC-015)
3. Фильтр входа: задачи с `text_has_known_prefix(task.text, prefixes)` **не** входят в batch, текст не менять, **не** считать LLM-выбором. (AC-004)
4. Если после фильтра список пуст → **0** вызовов, вернуть задачи как есть. (AC-007 republish)
5. Иначе **ровно один** вызов `llm_fn(prompt)`. Промпт: body + JSON контекста:
   - название встречи, `summary.notes`, участники;
   - `closed_list` (`slug, task_slug, display_name, aliases`) — «память» как `_match_by_name`-подсказка модели, **не** второй резолвер ROUTES (`_match_by_name` на диске нет — не выдумывать функцию в `route.py`);
   - задачи batch: `{task_index, text as-is, assignee_raw}`.
6. Разбор ответа: reuse `dedup._parse_llm_json_array` (не копировать парсер). На каждый index:
   - взять `task_slug` **только** если `entity_slug` есть в closed_list **и** `task_slug` совпадает с полем реестра этой записи (модель не выдумывает префикс) — AC-006;
   - `confidence` игнорировать как порог: 0.1 + валидный slug → ставить (AC-005);
   - нет записи на index / невалидный JSON по этой задаче → fail-soft этой задачи, остальные не блокировать;
   - исключение `llm_fn` / пустой ответ / невалидный массив → весь batch fail-soft, публикация жива, ErrorBus warning (AC-015).
7. Дописывание: `new_text = chosen_slug + original_text` **без пробела** после точки. Второй префикс не клеить (задачи из п.3 сюда не попадают).
8. Fail-soft задачи (п.2/6): если `route.tag_prefix` — вписать `tag_prefix + " " + text`; иначе текст as-is. Meeting-level `Лёня 1-1.` **не** клеить вместе с выбранным проектным слагом (AC-003).

Счётчик вызовов: модульный `llm_fn` передаётся снаружи; тесты подставляют мок с `.call_count`.

**Не хардкодить** model/base_url/api_key. Не импортировать `openai` здесь.

#### 2.2. `storage_xml.py`

**Не менять** `_task_body` / `render_row` / `render_content_block` (сигнатуры и ветка `if tag_prefix:`). Поведение out-of-scope не меняется, потому что туда по-прежнему передаётся `route.tag_prefix`.

In-scope вызывающий передаёт `tag_prefix=None` (шаг 3).

#### 2.3. ErrorBus warning picker

В `pipeline.py` рядом с `_report_pfs_ingest_error` (тот же `REPORT_ERROR_SH`, `--tool ProtocolFromSummary`, fail-soft):

```python
def _report_pfs_picker_warning(meeting_id: str, entity: str | None, detail: str) -> None:
    # stage="task_slug", severity="warning"
```

Вызывать из `apply_task_slugs` через узкий callback или напрямую из pipeline-обёртки, чтобы `task_slug.py` не тащил subprocess. Рекомендация: `apply_task_slugs(..., on_warning: Callable[[str], None] | None = None)`; pipeline передаёт лямбду на `_report_pfs_picker_warning`. Новый контракт ErrorBus **не** заводить.

**Точка проверки шага 2:** юниты на фикстурном `entities` dict (не live write). Мок LLM. Без Confluence.

---

### Шаг 3 — Точки вызова: picker перед `render_row`; pass 2 = 0 picker

Покрывает: **AC-012** (+ проводка AC-001 на обоих контурах).

#### 3.1. `pipeline.py` — единственная точка picker

В `run_pilot`, **сразу после** сборки `resolved_tasks` (`:468`) и **до** чтения флагов пост-switch (`:470`):

```python
from .task_slug import apply_task_slugs, route_in_scope

effective_llm = llm_fn if llm_fn is not None else _dedup_llm_fn
resolved_tasks = apply_task_slugs(
    route=route,
    summary=summary,
    resolved_tasks=resolved_tasks,
    llm_fn=effective_llm,
    on_warning=lambda d: _report_pfs_picker_warning(meeting_id, route.entity, d),
)
in_scope = route_in_scope(route)
render_tag = None if in_scope else route.tag_prefix
```

Дальше **оба** `render_row` (в `_post_switch_pass_one` и в flag-off ветке) и `render_content_block` должны получить `tag_prefix=render_tag`, не сырой `route.tag_prefix`.

Чтобы не тащить флаг через сигнатуру `_post_switch_pass_one` (её тоже лучше не расширять без нужды — ТЗ не замораживает эту сигнатуру, но лишний kwarg не обязателен): in-scope задачи уже несут префикс в `.text`, достаточно передать `tag_prefix=None` внутри `_post_switch_pass_one`, если `route_in_scope(route)`. Считать `route_in_scope` в обоих местах — детерминировано, без состояния.

Правки:

- `_post_switch_pass_one` `:277`: `tag_prefix=(None if route_in_scope(route) else route.tag_prefix)`
- `run_pilot` `:605` и `:623`: то же для `render_row` / `render_content_block`

**Не менять** сигнатуры `run_pilot` / `protocol_publish` / `_post_switch_pass_one` (последнюю можно оставить как есть по kwargs).

Порядок относительно дедупа (flag off): picker → DedupChecker → render. На `PFS_POST_SWITCH` проход 1 дедуп по-прежнему не зовётся (§24) — не трогать.

`llm_fn` публикатора остаётся общим инжектом: тесты дедупа, передающие мок, попадут и в picker. Это приемлемо: in-scope тесты дедупа с project-маршрутом picker не зовут (AC-002); in-scope 1-1 тесты пайплайна должны мокать JSON picker **или** ставить `PFS_PROMPT_REGISTRY_OFF=1` в тех тестах, где picker не предмет проверки. Рекомендация для регресса offline: в `tests/conftest.py` **не** включать kill-switch глобально (иначе AC-001/007 не тестируются). Точечно: существующие e2e с `kind=project` не затронуты; тесты на Кирилл 1-1 (`test_pipeline_*` с K1) — проверить, нужен ли kill-switch или мок. Если тест ходит в реальный `_dedup_llm_fn` без ключа — picker fail-soft (пустой api_key → `""` → fail-soft), публикация жива (AC-015). Предпочтительно явный мок в новых тестах.

#### 3.2. `playground_promote.py` — 0 вызовов picker

- **Не** импортировать `task_slug.apply_task_slugs`.
- В начале `promote_meeting` (после docstring, до GET) — защитный комментарий + опциональный debug-assert, который тесты проверяют снаружи (spy), а не `assert False` в проде.
- DedupChecker прохода 2 остаётся; он выиграет от шага 5/AC-013 (снятие префиксов внутри `dedup.py`), без вызова picker.

Тест AC-012: `patch("protocolfromsummary.task_slug.apply_task_slugs")` на время `promote_meeting` → `assert_not_called`. **Не** патчить `_dedup_llm_fn` как «picker» — дедуп прохода 2 его легитимно зовёт.

**Сигнатура `promote_meeting` не менять.**

**Точка проверки шага 3:** spy picker=1 на in-scope `protocol_publish` dry_run с мок LLM; spy picker=0 на `kind=project`; spy picker=0 на `promote_meeting`; при `PFS_POST_SWITCH=1` td1 ingest-строки содержит литерал слага (мок pipeline + ingest, без live API).

---

### Шаг 4 — TaskRefresh F2: `pfs.tag` OR `task_slug`

Покрывает: **AC-011**.

#### 4.1. `taskrefresh/project_registry.py`

`_adapt_entities_to_registry`: в выходной dict добавить `"task_slug": entry.get("task_slug")` (может быть `None`). Legacy-ветка без этого ключа — `match_by_text` трактует как отсутствует.

`match_by_text`:

```python
def match_by_text(self, text: str) -> str | None:
    if not text:
        return None
    text_low = text.strip().lower()
    best_slug, best_len = None, -1
    for slug, entry in self.load().items():
        for key in ("tag", "task_slug"):
            pref = entry.get(key)
            if pref and text_low.startswith(pref.lower()) and len(pref) > best_len:
                best_slug, best_len = slug, len(pref)
    return best_slug
```

Длиннейший префикс — чтобы `AI.` не перебивал `AI-аналитик.` (уникальность заполненных `task_slug` — fail на стороне ER; `pfs.tag` уникален только в паре с page_id, поэтому longest-match обязателен).

Ключ реестра TR по-прежнему `display_name` (не entity slug). F2=`AI-аналитик` → `"AI-аналитик"`.

#### 4.2. `taskrefresh/filters.py`

**Не менять** порядок text → page_id. Не менять сигнатуры `TaskFilter` / `apply`.

Регресс AC-011: задача без префикса на 1-1 при `projects=["AI-аналитик"]` **не** в `kept` (page_id fallback даёт «Кирилл 1-1», не AI-аналитик). Существующий `test_page_id_fallback_when_no_text_tag` это уже фиксирует на уровне annotate; добавить F2-`apply` с `projects=["AI-аналитик"]`.

Задача с `text_clean="ai-аналитик.сделать перенос"` (без пробела после точки — формат picker) при `task_slug="ai-аналитик."` **и/или** `tag="AI-аналитик."` должна матчиться (startswith case-insensitive).

Фикстура `tests/conftest.py::project_registry_json` — legacy-формат без `task_slug`. Новые тесты AC-011 пусть собирают **entities-формат** tmp JSON (`schema_version` + `entities`) и кормят `ProjectRegistry(path)` — проверяет адаптер, не только legacy.

**Не трогать:** `test_entities_registry_adapter.py` пары (pageIds, tag), кроме аддитивной проверки, что после backfill `data["AI-аналитик"].get("task_slug")` либо отсутствует (до backfill), либо равен/является строкой (после). Не требовать live backfill в TR-тестах: для адаптера достаточно синтетики.

---

### Шаг 5 — Не трогать + AC-009/AC-014 + дедуп без префиксов (AC-013)

Покрывает: **AC-009, AC-013, AC-014**.

#### 5.1. `dedup.py` — снятие known prefixes (единственная разрешённая правка алгоритма §15)

Точки:

- `_parse_task_text`: после strip HTML вызвать `strip_known_prefix`.
- `_check_tasks_impl`: перед `_fuzzy_ratio` сравнивать `strip_known_prefix(task.text)` vs `strip_known_prefix(pub_task.text)`.
- `_llm_check_tasks`: в JSON кандидатов отдавать уже stripped text (иначе LLM видит разные префиксы как разный смысл).

Загрузка префиксов: `task_slug.known_prefixes(task_slug.load_entities())`, fail-soft `[]` (дедуп жив без реестра). Кэш на уровне вызова `DedupChecker.__init__` (один load на checker), не module-level (тесты подменяют path через env `ENTITIES_REGISTRY_PATH`).

Порог 0.80, окно 3 недели, incomplete-правило, `reason: Literal["fuzzy","llm"]` — без изменений.

Сигнатуры `DedupChecker.__init__` / `check_tasks` / `check_sections` / `check_risks` / `parse_published_rows` **не менять**.

Это покрывает и проход 1 (flag off), и проход 2 (`_promote_dedup_minutes_against_target` уже гоняет `check_tasks` по `pt.text` из parse — выиграет от `_parse_task_text`).

#### 5.2. Статический freeze (AC-009, AC-014)

Не «смотреть глазами на diff», а тесты:

- `inspect.signature(protocol_publish)` / `process_pending` / `resolve_route` / `row_anchor_for` / `_task_body` — сверить с каноном шага «Что НЕ трогать».
- `summary_parser._SECTION_NAMES` == `["Участники", "Обсудили", "Решения", "Блокеры", "Задачи", "Риски"]`.
- grep: в `USERTOOLS/MarkObjectsFromSummary` (исходники, не `.venv`) нет `task_slug`; в новом `task_slug.py` / diff pipeline нет литералов `deepseek/`, `llm-gateway.tutu.ru`, `claude-haiku`.

MOFS код не открывать на запись.

---

## 4. НОВАЯ «СУЩНОСТЬ» ПРОМПТА (не граф)

| Что | Путь | Writer |
|---|---|---|
| id | `pfs_task_slug` | — |
| файл канона | `/home/tkachenkoav/WorkVault/Registries/prompts/pfs_task_slug.json` | `prompt_registry_cli write -y` |
| schema enum | `/home/tkachenkoav/WorkVault/Registries/prompts/prompt.schema.json` | этот CHANGE |
| loader map | `protocolfromsummary/prompt_loader.py` `_ID_TO_FILE` | этот CHANGE |
| CLI allow-list | `protocolfromsummary/prompt_registry_cli.py` `CANON_IDS` | этот CHANGE |
| kill-switch | env `PFS_PROMPT_REGISTRY_OFF` (уже есть) | не создавать новый |

Learner auto-apply в канон — запрещён (как §22).

---

## 5. IAC — полное покрытие AC-001…015

Канон имён тестов зафиксировать. `depends` — шаг impl 0–5. Verify — из корня соответствующего пакета, offline (`-m "not live_confluence"` там, где маркер есть).

| IAC | AC | тест | файл | verify | depends | covers |
|---|---|---|---|---|---|---|
| IAC-01 | AC-001 | `test_onescope_1on1_task_body_slug_no_space_after_dot` | `ProtocolFromSummary/tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_onescope_1on1_task_body_slug_no_space_after_dot -q` | шаг 2–3 | in-scope 1-1: mention + ` ` + `AI-аналитик.` (или fixture slug) + текст без пробела после точки; `tag_prefix` 1-1 не дублируется; юнит `render_row`/`apply_task_slugs`, без live API |
| IAC-02 | AC-002 | `test_project_route_does_not_call_picker` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_project_route_does_not_call_picker -q` | шаг 2–3 | `kind=project`: `llm_fn.call_count==0`; в XML meeting-level `Trisigma.` |
| IAC-03 | AC-003 | `test_lenya_in_scope_no_double_person_tag` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_lenya_in_scope_no_double_person_tag -q` | шаг 2–3 | `entity=lenya_1on1` + выбранный slug: в теле нет `Лёня 1-1.`; ровно один проектный `task_slug` |
| IAC-04 | AC-004 | `test_input_filter_skips_prefixed_task_not_llm_choice` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_input_filter_skips_prefixed_task_not_llm_choice -q` | шаг 2 | `text` уже `startswith` known `task_slug` или `pfs.tag` → не в batch; второй префикс не клеится (`count==1`) |
| IAC-05 | AC-004 | `test_republish_all_prefixed_zero_llm` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_republish_all_prefixed_zero_llm -q` | шаг 2 | все in-scope уже с префиксом → `llm_fn.call_count==0` |
| IAC-06 | AC-005 | `test_low_confidence_still_applies_slug` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_low_confidence_still_applies_slug -q` | шаг 2 | мок `confidence=0.1` + валидный `entity_slug` → префикс ставится |
| IAC-07 | AC-005 | `test_missing_index_failsoft_one_task_not_whole_meeting` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_missing_index_failsoft_one_task_not_whole_meeting -q` | шаг 2 | нет записи на index → эта задача без нового слага, соседняя с валидным ответом — со слагом |
| IAC-08 | AC-006 | `test_closed_list_excludes_non_project_and_empty_slug` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_closed_list_excludes_non_project_and_empty_slug -q` | шаг 2 | 1-1/person/tool/project-без-слага нет в JSON промпта |
| IAC-09 | AC-006 | `test_invented_prefix_discarded` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_invented_prefix_discarded -q` | шаг 2 | ответ с `task_slug`, которого нет у выбранного slug реестра → fail-soft этой задачи |
| IAC-10 | AC-007 | `test_batch_one_llm_call_for_n_unprefixed` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_batch_one_llm_call_for_n_unprefixed -q` | шаг 2 | N≥2 непрефиксованных → ровно 1 вызов `llm_fn`; префиксованная третья в вызов не входит |
| IAC-11 | AC-008 | `test_picker_uses_injected_llm_fn_not_hardcoded_model` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_picker_uses_injected_llm_fn_not_hardcoded_model -q` | шаг 2 | мок `llm_fn` вызывается; `test_no_new_model_literals_in_task_slug_module` — grep `deepseek/` / `llm-gateway` / `claude-haiku` по `task_slug.py` пуст |
| IAC-12 | AC-009 | `test_mofs_sources_have_no_task_slug` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_mofs_sources_have_no_task_slug -q` | шаг 5 | `rg task_slug ~/USERTOOLS/MarkObjectsFromSummary -g '*.py'` пуст (исключить `.venv`) |
| IAC-13 | AC-010 | `test_project_missing_task_slug_is_warning_not_fail` | `EntityRegistryCLI/tests/test_validate_task_slug.py` | `cd ~/USERTOOLS/EntityRegistryCLI && python -m pytest tests/test_validate_task_slug.py::test_project_missing_task_slug_is_warning_not_fail -q` | шаг 0 | `validate` exit 0; stderr содержит `task_slug_missing`; нет EXIT_VALIDATION |
| IAC-14 | AC-010 | `test_one_on_one_nonempty_task_slug_fails` | `EntityRegistryCLI/tests/test_validate_task_slug.py` | `python -m pytest tests/test_validate_task_slug.py::test_one_on_one_nonempty_task_slug_fails -q` | шаг 0 | `kirill`/`one_on_one` с заполненным слагом → rc=2 `task_slug_forbidden_kind` |
| IAC-15 | AC-010 | `test_task_slug_format_and_uniqueness_fail` | `EntityRegistryCLI/tests/test_validate_task_slug.py` | `python -m pytest tests/test_validate_task_slug.py::test_task_slug_format_and_uniqueness_fail -q` | шаг 0 | нет `.` / есть пробел / дубль заполненных → rc=2 |
| IAC-16 | AC-010 | `test_backfill_from_pfs_tag_idempotent_no_schema_bump` | `EntityRegistryCLI/tests/test_backfill_task_slug.py` | `python -m pytest tests/test_backfill_task_slug.py -q` | шаг 0 | CLI `-y` на фикстуре с 2 проектами+тегами + 1 project без pfs: проставляет 2 слага `= pfs.tag`, второй прогон 0 updates, `schema_version` не меняется; без `-y` не пишет |
| IAC-17 | AC-011 | `test_match_by_text_task_slug_or_pfs_tag` | `TaskRefresh/tests/test_project_registry.py` | `cd ~/USERTOOLS/TaskRefresh && python -m pytest tests/test_project_registry.py::test_match_by_text_task_slug_or_pfs_tag -q` | шаг 4 | entities-фикстура: текст с `task_slug` и текст с `pfs.tag` резолвятся в display_name проекта |
| IAC-18 | AC-011 | `test_f2_1on1_glued_slug_included_unprefixed_excluded` | `TaskRefresh/tests/test_filters.py` | `python -m pytest tests/test_filters.py::test_f2_1on1_glued_slug_included_unprefixed_excluded -q` | шаг 4 | F2=`AI-аналитик`: 1-1 + `ai-аналитик.сделать…` в kept; 1-1 без префикса не в kept; порядок text→page_id не сломан (`test_text_tag_wins_over_container_page_id` регресс) |
| IAC-19 | AC-012 | `test_promote_meeting_does_not_call_apply_task_slugs` | `tests/test_promote_v2.py` | `pytest tests/test_promote_v2.py::test_promote_meeting_does_not_call_apply_task_slugs -q` | шаг 3 | spy `apply_task_slugs` = 0 на `promote_meeting` (dry_run и live-мок PUT) |
| IAC-20 | AC-012 | `test_post_switch_pass_one_td1_contains_slug` | `tests/test_post_switch.py` | `pytest tests/test_post_switch.py::test_post_switch_pass_one_td1_contains_slug -q` | шаг 3 | `PFS_POST_SWITCH=1`, in-scope route, мок picker/llm: XML/ingest td1 содержит `task_slug`; `update_page(route.page_id)` не звался |
| IAC-21 | AC-013 | `test_dedup_strips_known_prefixes_before_compare` | `tests/test_dedup.py` | `pytest tests/test_dedup.py::test_dedup_strips_known_prefixes_before_compare -q` | шаг 5 | «сделать перенос» vs `AI-аналитик.сделать перенос` / `Trisigma. сделать перенос` → fuzzy-дубль; `PublishedTask.text` после parse без ведущего known prefix |
| IAC-22 | AC-014 | `test_frozen_signatures_unchanged` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_frozen_signatures_unchanged -q` | шаг 3,5 | `inspect.signature` на `protocol_publish` / `process_pending` / `resolve_route` / `row_anchor_for` / `_task_body`; `_SECTION_NAMES` без диффа |
| IAC-23 | AC-015 | `test_kill_switch_no_llm_fallback_tag_or_bare` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_kill_switch_no_llm_fallback_tag_or_bare -q` | шаг 1–2 | `PFS_PROMPT_REGISTRY_OFF=1` → 0 LLM; Лёня → остаётся `Лёня 1-1. ` в тексте; 1-1 с `tag=None` → без префикса; пайплайн не падает |
| IAC-24 | AC-015 | `test_llm_error_or_empty_closed_list_failsoft` | `tests/test_task_slug.py` | `pytest tests/test_task_slug.py::test_llm_error_or_empty_closed_list_failsoft -q` | шаг 2 | `llm_fn` бросает / возвращает `""` / closed_list пуст → публикация (apply возвращает задачи), без нового слага |
| IAC-25 | AC-015 | `test_offline_pytest_not_live_confluence_green` | пакет PFS | `cd ~/USERTOOLS/ProtocolFromSummary && pytest -m "not live_confluence" -q` | шаги 0–5 | регресс offline; новые тесты аддитивны |
| IAC-26 | AC-015 | `test_prompt_loader_kill_switch_skips_task_slug_file` | `tests/test_prompt_loader.py` | `pytest tests/test_prompt_loader.py::test_kill_switch_task_slug_returns_none -q` | шаг 1 | флаг on → `resolve_task_slug_prompt() is None` даже если json на диске |

**Канонические AC для GATE:plan-approve:** 001 (IAC-01), 004 (IAC-04+05), 007 (IAC-10), 010 (IAC-13…16), 011 (IAC-17+18), 012 (IAC-19+20), 013 (IAC-21) — все имеют имя теста + файл + verify.

**Сводка покрытия:** AC-001…015 присутствуют в таблице, пробелов нет.

Регресс-пакеты после impl (не отдельные IAC, гонять на `HF:test`):

```
cd /home/tkachenkoav/USERTOOLS/ProtocolFromSummary && pytest -m "not live_confluence" -q
cd /home/tkachenkoav/USERTOOLS/EntityRegistryCLI && python -m pytest -q
cd /home/tkachenkoav/USERTOOLS/TaskRefresh && python -m pytest tests/test_project_registry.py tests/test_filters.py tests/test_entities_registry_adapter.py -q
```

---

## 6. СОЗДАВАЕМЫЕ / ИЗМЕНЯЕМЫЕ ФАЙЛЫ

### Создать

| Файл | Зачем |
|---|---|
| `protocolfromsummary/task_slug.py` | picker + closed list + фильтр входа + strip prefix |
| `tests/test_task_slug.py` | AC-001…008, 009, 014, 015 (ядро) |
| `EntityRegistryCLI/tests/test_validate_task_slug.py` | AC-010 validate |
| `EntityRegistryCLI/tests/test_backfill_task_slug.py` | AC-010 backfill CLI `-y` |
| `WorkVault/Registries/prompts/pfs_task_slug.json` | канон промпта (через CLI `-y`, не руками в обход writer) |

### Изменить (PFS)

| Файл | Что |
|---|---|
| `protocolfromsummary/pipeline.py` | вызов `apply_task_slugs` в `run_pilot`; `tag_prefix=None` in-scope в обоих render; `_report_pfs_picker_warning` |
| `protocolfromsummary/prompt_loader.py` | `_ID_TO_FILE` + `resolve_task_slug_prompt` |
| `protocolfromsummary/prompt_registry_cli.py` | `CANON_IDS` + catalog |
| `protocolfromsummary/dedup.py` | strip known prefixes в parse/compare/LLM-pool |
| `protocolfromsummary/playground_promote.py` | не вызывать picker; тест-якорь 0 вызовов |
| `tests/test_prompt_loader.py` | kill-switch для нового id |
| `tests/test_dedup.py` | AC-013 |
| `tests/test_promote_v2.py` | AC-012 spy |
| `tests/test_post_switch.py` | AC-012 td1 |

### Изменить (ER / Registries)

| Файл | Что |
|---|---|
| `WorkVault/Registries/entities.schema.json` | optional `task_slug` на корне записи |
| `WorkVault/Registries/entities.json` | **только** `entity-registry backfill-task-slug -y` |
| `WorkVault/Registries/prompts/prompt.schema.json` | enum += `pfs_task_slug` |
| `EntityRegistryCLI/entityregistrycli/validator.py` | WARNING + инварианты |
| `EntityRegistryCLI/entityregistrycli/cli.py` | validate/write игнорируют warning; subcommand backfill |
| `EntityRegistryCLI/entityregistrycli/operations.py` | `backfill_task_slug` |
| `EntityRegistryCLI/tests/fixtures/entities.schema.json` | optional `task_slug` |

### Изменить (TaskRefresh)

| Файл | Что |
|---|---|
| `taskrefresh/project_registry.py` | адаптер + `match_by_text` OR + longest |
| `tests/test_project_registry.py` | AC-011 |
| `tests/test_filters.py` | AC-011 F2 glued / unprefixed |

### Явно не в diff

`route.py`, `page_merger.py`, `storage_xml._task_body` (сигнатура), `summary_parser.py` (кроме использования `.text`), MOFS, `jobs.json`, `.env`, Gateway, `EcosystemManifest.json`, `config.py` LLM-литералы, `AnywhereContacts`.

---

## 7. ТЕСТОВЫЕ ФАЙЛЫ (счёт)

| Тип | Файлы | Число |
|---|---|---|
| **Новые** | `tests/test_task_slug.py`, `EntityRegistryCLI/tests/test_validate_task_slug.py`, `EntityRegistryCLI/tests/test_backfill_task_slug.py` | **3** |
| **Расширяемые** | `tests/test_prompt_loader.py`, `tests/test_dedup.py`, `tests/test_promote_v2.py`, `tests/test_post_switch.py`, `TaskRefresh/tests/test_project_registry.py`, `TaskRefresh/tests/test_filters.py` | **6** |
| Итого файлов с новыми/изменёнными тестами |  | **9** |

IAC-строк: 26 (все AC-001…015 покрыты; канонические 001/004/007/010/011/012/013 — множественными тестами где нужно).

---

## 8. РИСКИ / ЛОВУШКИ ДЛЯ ИСПОЛНИТЕЛЯ

1. **`_write_and_backup` + WARNING.** Если забыть фильтр `fail_issues`, CLI сломается на любом `edit`, пока `Contracts` без слага. Сделать в том же шаге 0, что и `Issue.severity`.
2. **Один `tag_prefix` на строку.** In-scope всегда `None` после picker; fallback Лёни — в `task.text`, не через `_task_body`.
3. **Picker LLM vs Dedup LLM.** Оба на `_dedup_llm_fn`. AC-012 считает вызовы `apply_task_slugs`, не `_dedup_llm_fn`.
4. **Фикстура ERC schema ≠ live schema.** Добавить `task_slug` в оба.
5. **`Contracts`.** `kind=project` без pfs → WARNING навсегда в этом CHANGE; backfill не выдумывает слаг.
6. **Autouse `PFS_PLAYGROUND_INGEST_OFF=1`** в `tests/conftest.py`. Тест AC-012 post-switch обязан `delenv` этого флага (как существующие post-switch тесты).
7. **Не звать live `entity-registry backfill-task-slug -y` из pytest** против прод-файла без tmp copy. Прод-backfill — шаг impl после зелёных фикстур, один раз, с `-y`.
8. **`is_one_on_one=route.kind == "one_on_one"`** для Лёни (`person_1on1`) остаётся False — не «чинить» в этом графе.
9. Не открывать §30 (константы `LLM_FALLBACK_*`).

---

## 9. ПРОГРЕСС ВЫПОЛНЕНИЯ

Устойчивость к падению координатора: отмечать по мере закрытия шага на `HF:impl` / `HF:test`. Не отмечать заранее.

### Шаг 0 — ER schema / WARNING / backfill

- [ ] 0.1 `entities.schema.json` (WorkVault): optional `task_slug` на корне записи
- [ ] 0.2 `validator.py`: `Issue.severity`, инварианты, `fail_issues`
- [ ] 0.3 `cli.py`: warnings не блокируют write; validate exit 0 на warning-only
- [ ] 0.4 `operations.backfill_task_slug` + `entity-registry backfill-task-slug -y`
- [ ] 0.5 фикстура `EntityRegistryCLI/tests/fixtures/entities.schema.json`
- [ ] 0.T IAC-13…16 зелёные на tmp
- [ ] 0.P прод-backfill `-y` (18 обновлений, schema_version=1.2) — после 0.T

### Шаг 1 — промпт

- [ ] 1.1 `prompt.schema.json` enum += `pfs_task_slug`
- [ ] 1.2 `prompt_loader.py` `_ID_TO_FILE` + `resolve_task_slug_prompt`
- [ ] 1.3 `prompt_registry_cli.py` `CANON_IDS` + catalog
- [ ] 1.4 запись канона `prompts/pfs_task_slug.json` через CLI `-y`
- [ ] 1.T IAC-26 зелёный

### Шаг 2 — picker-модуль

- [ ] 2.1 `protocolfromsummary/task_slug.py` (scope, closed_list, filter, apply)
- [ ] 2.2 ErrorBus callback / `_report_pfs_picker_warning`
- [ ] 2.T IAC-01…11, 23–24 зелёные (юнит без Confluence)

### Шаг 3 — точки вызова

- [ ] 3.1 `run_pilot`: `apply_task_slugs` после резолва, до fork
- [ ] 3.2 `tag_prefix=None` in-scope в `_post_switch_pass_one` + `render_row`/`render_content_block`
- [ ] 3.3 `playground_promote.py` без импорта picker
- [ ] 3.T IAC-19, IAC-20 зелёные
- [ ] 3.R регресс `test_post_switch.py` / `test_pipeline_dedup.py` (project) зелёный

### Шаг 4 — TaskRefresh F2

- [ ] 4.1 `_adapt_entities_to_registry` + `match_by_text` OR + longest
- [ ] 4.2 тесты IAC-17, IAC-18; регресс `test_text_tag_wins_over_container_page_id`
- [ ] 4.T `filters.py` порядок text→page_id без диффа логики

### Шаг 5 — freeze + дедуп prefixes

- [ ] 5.1 `dedup.py` strip prefixes (parse + fuzzy + LLM pool)
- [ ] 5.2 IAC-21, IAC-12, IAC-22
- [ ] 5.T `pytest -m "not live_confluence"` PFS зелёный (IAC-25)
- [ ] 5.R ERC `python -m pytest -q`; TR три файла из §5

### Запреты (чек самопроверки перед сдачей)

- [ ] сигнатуры из §2 без диффа
- [ ] `schema_version` entities.json не поднят
- [ ] нет `PFS_PROMPT_STORE`
- [ ] нет новых литералов модели
- [ ] MOFS grep `task_slug` пуст
- [ ] кроны/Gateway/jobs.json/.env/EcosystemManifest не в diff
- [ ] picker на promote = 0
- [ ] поле в `entities.<slug>.task_slug`, не в `pfs`

---

## 10. ГОТОВНОСТЬ К GATE:plan-approve

- Шаги 0–5 = таблица Impl-привязки §29, атомарно, пофайлово.
- Сигнатуры «не трогать» перечислены.
- Промпт `pfs_task_slug` — конфиг/реестр, пути указаны.
- IAC-таблица: AC-001…015 все покрыты; канонические 001/004/007/010/011/012/013 имеют имя теста + файл + verify.
- Прогресс — чекбоксы.

Код не писался. Следующая фаза после approve: `HF:backup` → `HF:impl`.
