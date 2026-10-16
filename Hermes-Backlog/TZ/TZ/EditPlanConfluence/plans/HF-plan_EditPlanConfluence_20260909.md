---
type: hf-plan
title: "Пофайловый план скилла productivity/edit-plan-confluence (HF:plan, 09.09)"
slug: EditPlanConfluence
case: SKILL-DEV
phase: HF:plan
date: 2026-09-09
status: draft-plan
author: архитектор (cursor-grok-4.6-high, HF:plan)
source_tz: TZ/EditPlanConfluence/EditPlanConfluence_TZ.md v0.2.0 (approved)
source_skills:
  - hermes-workspace/skills/productivity/tutu-confluence-jira/SKILL.md (паттерн load_confluence_env)
  - hermes-workspace/skills/productivity/read-mpp/SKILL.md (вход .zip)
source_artifacts:
  - /tmp/mpp_to_gantt.py
  - /tmp/build_calendar2.py
  - /tmp/gantt_test.json
  - /tmp/gantt_newplan.json
executor: composer-2.5
next_phases: REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done
---

# HF:plan — EditPlanConfluence (скилл `edit-plan-confluence`)

Кейс **SKILL-DEV** (GLOSSARY §2 / §5.2): новый скилл в `~/hermes-workspace/skills/`. Этот файл — артефакт фазы **HF:plan** (Блок 1А `hermes-feature`). Код в этом вызове не писать. Объект для `REV:plan` и `GATE:plan-approve`.

Канон: master-ТЗ v0.2.0. Эталоны `/tmp/mpp_to_gantt.py` и `/tmp/build_calendar2.py` — **не** runtime-зависимости; логику перенести в `scripts/` скилла. `idCounter=300000` из эталона **не** переносить.

Новая сущность EntityRegistry / пакет USERTOOLS **не** предлагаются (ТЗ §4 reuse-first). Новый скилл согласован постановкой Саши.

---

## 0. Факт на диске (09.09) — не считать реализацию закрытой

Промпт фазы исходил из «каталога ещё нет». Проверка `which`/`ls` 09.09:

| Артефакт | На диске 09.09 | Цель этого плана | Делать на HF:impl |
|---|---|---|---|
| `~/hermes-workspace/skills/productivity/edit-plan-confluence/` | **есть** (черновик до `GATE:plan-approve`) | канон SKILL-DEV | **сверить с этим планом**, закрыть дельту; не удалять вслепую и не писать второй параллельный скилл |
| `scripts/{env,conf_client,gantt_attachment,mpp_input,mpp_convert,mpp_calendar,itogo,macro,child_page,gate_diff,pipeline,cli}.py` | есть | те же 12 файлов | keep + точечные фиксы из §2.13 |
| `references/{empty-gantt-template.json,mpp-to-gantt.md}` | есть | шаблон + рецепт | keep; шаблон = ключи §6, не живой план AB |
| `tests/` + CSV 080926 | есть | 9 обязательных сценариев | дополнить (дерево, копия/пустой, «Итого» нет-блока, live skipped); убрать зависимость фикстуры от `/tmp` |
| `~/.hermes/skills/productivity/confluence-gantt-plan/` | **есть** (не workspace) | погасить после канона | Т7 |
| `read_mpp.py`, ConfluenceSync, `tutu-confluence-jira` | не менялись | не трогать | **нет** |
| `EditPlanConfluence_TZ.md`, `MAIN_TZ_INVENTORY.md`, манифест, `.env`, `jobs.json`, `restore-all-skills.sh` | — | не трогать исполнителем | **нет** (манифест/restore — `ORCH:shared-state`) |

Черновик **не** заменяет этот план и **не** есть `HF:impl` done. Исполнитель идёт сверху вниз по §2–§5: если функция/тест уже совпадает с контрактом — оставить; если расходится — править. Новых имён файлов сверх §2 не плодить.

---

## 1. Цель фазы и критерии «готово»

### 1.1 Цель HF:plan

Полный пофайловый план v1 скилла `productivity/edit-plan-confluence`: конвертер MPP CSV→JSON, календарь Default Calendar, блок «Итого», REST вложения/дочки/storage, гейт «лей», CLI, оффлайн-тесты, гигиена коллизии, откат, приёмка.

### 1.2 Критерии «готово» этой фазы

- Этот файл записан в `TZ/EditPlanConfluence/plans/HF-plan_EditPlanConfluence_20260909.md`.
- Покрыты ТЗ §4–§11, §14–§16 и 9 оффлайн-сценариев на фикстуре CSV 080926.
- Код / мастер-ТЗ / инвентарь / манифест / чужие инструменты **не** изменены этим вызовом.
- POST/PUT на Confluence **не** выполнялись.

Снятие `GATE:plan-approve` (Саша / one-pass auto-complete) — **не** эта фаза. Реализация — `HF:impl` (исполнитель `composer-2.5`). Тесты live REST — только по явной команде Саши на `HF:test`.

### 1.3 Критерии «готово» всего SKILL-DEV (для ориентира хвоста)

См. ТЗ §15. Коротко: на тесте `519501810` после «лей» вложение бампает версию; плагин показывает дерево/FS/ресурсы/исключения MPP; две строки «Итого» (N/M ceil, даты корня `DD.MM.YY`); дочка REST с новыми uuid; без «лей» записи нет; без pageId не пишем на `519492935`; `read_mpp.py` и соседи не изменены.

---

## 2. Пофайловый план `scripts/` скилла

**Корень скилла (создаётся / уже есть, канон структуры):**

```
~/hermes-workspace/skills/productivity/edit-plan-confluence/
  SKILL.md
  references/empty-gantt-template.json
  references/mpp-to-gantt.md
  scripts/          # 12 модулей ниже
  tests/            # §3
```

Python: stdlib + (для календаря) `mpxj`/`jpype1` из `~/hermes-agent/.venv`. Интерпретатор CLI: `~/hermes-agent/.venv/bin/python3`. JVM: `org.mpxj.*`, Java 17 — уже есть для MppReader.

Общий контракт импорта: тесты добавляют `scripts/` в `sys.path` (как `page-to-schedule` / `tutu-confluence-jira`). Не ставить пакет USERTOOLS.

---

### 2.1 `scripts/env.py` — токен без `source` всего `.env`

**Назначение.** Python-эквивалент bash-паттерна `load_confluence_env` из `tutu-confluence-jira/SKILL.md` (блок «Авторизация»). Самодостаточность скилла: **скопировать логику**, не `import` из соседнего скилла, не `source` `.env`.

**Сигнатуры:**

```python
ENV_PATH = Path.home() / "USERTOOLS" / "ConfluenceSync" / ".env"
CONFLUENCE_BASE = "https://dom.tutu.ru"

def load_confluence_env(env_path: Path = ENV_PATH) -> dict[str, str]
def get_token() -> str
def page_url(page_id: str | int) -> str
```

**Вход:** файл `.env`. Читать построчно `KEY=VALUE`; ключи **только** `CONFLUENCE_TOKEN` и (опц.) `WORKVAULT_PATH`. Срезать кавычки. Остальные переменные игнорировать (баг MOFS CONF-001).

**Выход:** `{"CONFLUENCE_TOKEN": "...", ...}`. Нет токена → исключение с понятным текстом.

**Boundary:** не трогать ConfluenceSync-код; не писать в `.env`; не читать `~/.hermes/.env` / `~/.config/hermes/.env`.

**Кого вызывает:** все REST-модули (`conf_client`). CLI не печатает токен.

**Тот же паттерн в SKILL.md** (bash, для агента в чате) — дословно как в `tutu-confluence-jira`, с вызовом `load_confluence_env` после определения.

---

### 2.2 `scripts/mpp_input.py` — `.mpp` / `.zip` → CSV через `read_mpp.py`

**Назначение.** Вход Telegram: `.mpp` или `.zip` с `.mpp` внутри (как `read-mpp`). Вызов **существующего** `~/USERTOOLS/MppReader/read_mpp.py`. Файл **не модифицировать**.

**Сигнатуры:**

```python
@dataclass
class MppCsvPaths:
    mpp_path: Path
    tasks_csv: Path
    resources_csv: Path
    assignments_csv: Path
    out_dir: Path

def resolve_mpp_path(path: str | Path) -> Path
def export_csv(mpp_path: Path, out_dir: Path | None = None) -> MppCsvPaths
```

**Контракт вызова (не менять):**

```text
{venv}/python3 ~/USERTOOLS/MppReader/read_mpp.py <path> --format csv [--out-dir DIR]
→ {stem}__tasks.csv, {stem}__resources.csv, {stem}__assignments.csv
```

**Вход:** путь к файлу. `.zip` → распаковать во временный каталог рядом, взять **первый** `.mpp`. `.mpp` → как есть. Иной суффикс → ошибка.

**Выход:** абсолютные пути трёх CSV + путь к распакованному `.mpp` (нужен календарю).

**Boundary:** `--format csv` (не json-пайплайн `read-mpp` в Google Sheets). Не вызывать скиллы `read-mpp` / `mpp-to-google-sheets`. Колонки CSV как отдаёт MppReader: `id, outline_level, name, duration, start, finish, percent_complete, milestone, summary, predecessors` + `work`/`units`/`resource_name`/`task_id` в assignments. Типа связи (FS/SS) в CSV **нет** — см. §2.3.

---

### 2.3 `scripts/mpp_convert.py` — CSV → JSON вложения (логика `/tmp/mpp_to_gantt.py` без 300000)

**Назначение.** Собрать ключи §6: `eventsData` (один корень, дерево `children`), `resourcesData`, `dependenciesData`, `assignmentsData`, `startDate`, `idCounter`; сохранить из шаблона `macroConfig`, `initialState`, `baselineVersions`, `customColumns`, `linkedSites`.

**Сигнатуры (канон):**

```python
def read_csv_rows(path: Path) -> list[dict[str, str]]
def build_event_tree(tasks, leaf_template) -> tuple[dict, list]
def match_resources(mpp_res, template_resources) -> tuple[list[dict], dict[str, int]]
def build_dependencies(task_rows, event_ids: set[int], next_id: int) -> tuple[list[dict], int]
def build_assignments(asn_rows, event_ids, name_to_id, next_id) -> tuple[list[dict], dict[int, float], int]
def compute_id_counter(gantt: dict) -> int   # max(все id событий/ресурсов/связей/назначений)+1
def convert_mpp_csv(tasks_csv, resources_csv, assignments_csv, *, template_json: dict,
                    calendars_data: list | None = None) -> dict
def empty_gantt(title: str | None = None, template_path: Path | None = None) -> dict
def copy_parent_gantt(parent: dict) -> dict  # deepcopy + idCounter = compute_id_counter
```

**Вход:** три CSV + JSON-шаблон (существующее вложение страницы **или** `references/empty-gantt-template.json`).

**Выход:** dict ключей §6.

**Правила задач (ТЗ §8):**

- Строки с пустым `id` и `id=0` не брать (служебный корень MPP).
- Ровно один корень: `outline_level=1`. Дерево стеком по `outline_level`.
- `summary=True` → `rollup: true`. Вехи (`milestone=True` или duration 0) → `duration=0`, `effort=0`.
- `start`/`finish` → `startDate`/`endDate`, нормализовать до секунд (`T09:00`→`T09:00:00`, `T18:00`→`T18:00:00`).
- После дерева: `parentId` / `parentIndex`.
- `percentDone` из `percent_complete` (колонка есть в CSV 080926); иначе 0. Каскад % по родителям не считать.
- `schedulingMode`: `FixedDuration`. Поля-заготовки как в эталоне листа: `baselines=[], calendar=None, constraintType='', durationUnit=day, effortDriven=False, effortUnit=hour, manuallyScheduled=False, unscheduled=False, segments=None, …`.
- Даты **не** пересчитывать (каскада нет). `startDate` верхнего уровня JSON = дата старта корня `YYYY-MM-DD`.

**Ресурсы:**

- Матч MPP → шаблон **по точному `name`**.
- Активная группа шаблона = **max id на имя**. Низкие id копий **не** включать в новый `resourcesData`.
- Имя MPP без матча → новый `{id, parentId: None, name, eventColor: "red", resourceType: "custom"}`. Фикстура: ресурс **«Найм»**.
- Нет шаблона ресурсов (пустая страница): все ресурсы MPP — новые custom; id выделять **после** `max(event ids)`, чтобы не столкнуться с id задач 1..N (MPP resource id=1 совпадёт с событием id=1).
- Цвета существующих активных записей сохранять при матче.

**Назначения и effort:**

- В `assignmentsData` только строки с непустым `resource_id`/`resource_name`, имя нашлось в пуле: `{id, event, resource, units}` (`units` = % из MPP).
- `effort` листа = сумма `work` (часы) **всех** строк `__assignments.csv` этой задачи (включая строки без ресурса — у 080926 это «Подготовка» 40h, «Резерв» 240h, «Отпуска» 160h). Сводные: **не** суммировать детей в `effort` корня.
- Строки без `resource_id` в `assignmentsData` не попадают, но их `work` входит в effort события и в M «Итого».

**Связи:**

- `predecessors` вида `[2]` / `[15, 17, 19]` → `{from, to, type: 2, lag: 0, lagUnit: "day", active: true}`.
- CSV MppReader **не отдаёт тип связи**. v1 маппит все id как FS. Не-FS: если при наличии `.mpp` отдельным (опциональным) проходом `org.mpxj` `RelationType != FINISH_START` — пропустить связь и добавить warning в дифф; не падать. Без `.mpp` (только CSV) — все как FS, без warning.
- Не хардкодить id связей `100000` / назначений `200000`. После событий+ресурсов: `next_id = max(used)+1`, инкремент.

**idCounter:** `max(все id)+1`. Запрещено копировать `300000` из `/tmp/gantt_newplan.json`. В `gantt_test.json` эталон = 354 (= max used, не +1) — для **нового** JSON канон ТЗ: **max+1**.

**Boundary:** не вызывать REST; не читать MPP напрямую (кроме опц. RelationType). Календарь подмешивает `mpp_calendar.py`.

---

### 2.4 `scripts/mpp_calendar.py` — `calendarsData` (логика `/tmp/build_calendar2.py`)

**Назначение.** Только `getDefaultCalendar()`. Календари ресурсов — не в v1.

**Сигнатуры:**

```python
def base_recurrent_intervals() -> list[dict]  # обед 12–13, ночь 18–09, сб/вс
def exceptions_to_intervals(from_date: date, to_date: date) -> dict
def calendar_from_mpp(mpp_path: Path) -> list[dict]
def empty_template_calendar() -> list[dict]  # сб/вс + часы КАК В шаблоне теста (ночь 17–08), без исключений MPP
```

**Рекуррент при заливке MPP (доказано «да супер»):**

- обед `at 12:00`–`at 13:00`, `isWorking: False`;
- ночь по часам MPP 09–13 / 14–18 → `at 18:00`–`at 09:00` (как `build_calendar2.py`, **не** `17:00`–`08:00` из живого `gantt_test.json`);
- `on Sat`–`on Sun`; `on Sun`–`on Mon`.

**Исключения:** `getCalendarExceptions()` где `working=False`; `startDate: YYYY-MM-DD 00:00`, `endDate: (toDate+1 день) 00:00`.

**Выход:** `[{"id":"general","name":"General","unspecifiedTimeIsWorking": true, "intervals": [...]}]`.

**JVM:** тот же паттерн, что `read_mpp.py` (`import mpxj`, `jpype.startJVM`, `org.mpxj.reader.UniversalProjectReader`). Не дублировать парсер задач.

**Различие шаблонов (ТЗ TZ:patch):** пустой шаблон / копия без MPP может нести ночь 17–08 из `gantt_test.json`; заливка MPP **всегда** 18–09 + исключения файла. Эталон `/tmp/gantt_test.json` не переписывать и не считать рецептом заливки.

**Кого вызывает:** `pipeline.build_plan_from_mpp` после CSV.

---

### 2.5 `scripts/itogo.py` — две строки «Итого» (ТЗ §9)

**Назначение.** Счёт цифр и патч `body.storage`. Третью строку про 70% не создавать и не менять.

**Сигнатуры:**

```python
def format_thousands(n: int) -> str          # 1960 → "1 960"; 154 → "154"
def format_date_ddmmyy(dt: str | None) -> str  # 2026-09-28 → 28.09.26
def compute_itogo_from_csv(tasks_csv, assignments_csv) -> tuple[str, str, int, int]
def compute_itogo_from_gantt(gantt: dict) -> tuple[str, str, int, int]
def build_itogo_html(d1, d2, n_days, m_hours) -> str
def patch_itogo(storage, d1, d2, n_days, m_hours) -> str
def insert_itogo_above_macro(storage, macro_start: int, itogo_html: str) -> str
def apply_itogo(storage, d1, d2, n_days, m_hours, macro_start: int | None = None) -> str
```

**Канон текста (разделитель ` - `, не em-dash):**

```
Итого: с <ДД.ММ.ГГ> по <ДД.ММ.ГГ> - <N> рабочих дней
Трудозатраты: <M> человек-часа
```

HTML: `<p><strong>…</strong></p>` × 2.

**Цифры при заливке MPP:**

| Поле | Источник |
|---|---|
| дата1, дата2 | start/finish **корня** `outline_level=1`, не id=0 |
| N | `ceil(duration корня)` в днях |
| M | `ceil(sum work ВСЕХ строк __assignments.csv)`; не суммировать summary-задачи отдельно (work на summary в 080926 нет — сумма = 2355.2 → **2356**) |

**Важно:** M ≠ сумма `effort` листьев JSON (у 080926 effort с ресурсом = 1915.2). В M входят work без `resource_id` (440h).

**Копия / пустой шаблон:** даты и N с корня `eventsData`; M = ceil(сумма `effort` листьев `rollup=false`); пустые assignments → M=0; N=0 если duration 0; даты с `startDate` или одинаковые границы корня (ТЗ §13).

**Патч:**

1. Блока нет → вставить **над макросом** (`insert_itogo_above_macro`), не в начало страницы «вслепую», если макрос найден.
2. Блок есть → в первых двух строках заменить **только** даты/N/M. Хвост (в т.ч. 70%) не трогать.
3. Не искать «Итого» на других страницах.

**Фикстура 080926 (ожидаемые цифры, проверены по CSV):**  
`28.09.26` … `18.05.27` … `154` рабочих дней; `2 356` человек-часа.

---

### 2.6 `scripts/templates.py` логика — в `mpp_convert.empty_gantt` / `copy_parent_gantt` + `references/empty-gantt-template.json`

Отдельный модуль **не обязателен**, если функции живут в `mpp_convert.py` (черновик так и сделал — keep).

**Пустой шаблон:** один корень (имя «Новый план» или title страницы), `duration=0`, без детей, пустые `dependenciesData`/`assignmentsData`, `idCounter=max+1`, `calendarsData` = минимальный General (сб/вс + рабочие часы шаблона теста). В диффе: «план пустой».

**Копия родителя (дочка без MPP, у родителя есть гант):** deepcopy JSON родителя; содержимое то же; `idCounter = compute_id_counter` (починить битый 300000, если попался); макрос дочки — **новые** uuid (это `macro.py`, не JSON). «Итого» пересчитать из JSON.

Источник полей шаблона: `/tmp/gantt_test.json` (ключи §6), **не** живая AB. В репозиторий скилла положить урезанную копию в `references/empty-gantt-template.json` (корень без 36 задач).

---

### 2.7 `scripts/conf_client.py` — тонкий REST

**Назначение.** Единственная точка HTTP. Не `web_extract`. `Authorization: Bearer`. На запись: `X-Atlassian-Token: no-check`.

**Сигнатуры:**

```python
class ConfluenceClient:
    def _request(self, method, path, *, data=None, headers=None, query=None) -> Any
    def get_page(self, page_id, expand="body.storage,version,space") -> dict
    def put_page(self, page_id, title, storage, version) -> dict
    def create_page(self, title, space_key, parent_id, storage_html) -> dict
    def list_attachments(self, page_id) -> list
    def download_attachment(self, page_id, filename, version: int | None = None) -> bytes
    def upload_attachment_data(self, page_id, attach_id, filename, content: bytes) -> dict
    def create_attachment(self, page_id, filename, content: bytes) -> dict
```

**Таблица ТЗ §7:**

| Операция | Метод |
|---|---|
| страница | `GET /rest/api/content/{pageId}?expand=body.storage,version,space` |
| вложения | `GET /rest/api/content/{pageId}/child/attachment` |
| скачать JSON | `GET /download/attachments/{pageId}/{filename}?version=N&api=v2` или `_links.download` |
| обновить вложение | **POST** `.../child/attachment/{attachId}/data?conflictPolicy=override` multipart `file=@...;type=application/json;filename=...`. PUT → 405, не использовать |
| создать вложение | POST `.../child/attachment` multipart |
| дочка | POST `/rest/api/content` `{type:page, title, space:{key}, ancestors:[{id:parentId}], body.storage}` |
| тело | PUT `/rest/api/content/{pageId}` с текущим `version.number` |

**Гонка version:** перед PUT storage — **повторный GET** `expand=version` (после POST вложения UI мог бампнуть страницу). Не использовать `version+1` от GET начала прогона вслепую.

**Кого вызывает:** `gantt_attachment`, `child_page`, `pipeline`. Токен через `env.get_token`.

**Мок для тестов:** подмена `_request` / `urlopen` (unittest.mock). Live не звать.

---

### 2.8 `scripts/gantt_attachment.py` — найти / скачать / залить JSON

**Сигнатуры:**

```python
@dataclass
class AttachmentInfo:
    id: str
    title: str
    version: int

def find_gantt_attachment(attachments: list, macro) -> AttachmentInfo | None
def load_gantt_json(client, page_id, macro) -> tuple[dict | None, AttachmentInfo | None]
def upload_gantt_json(client, page_id, filename, gantt: dict, existing: AttachmentInfo | None) -> int
```

Имя файла: `gantt-chart-<macro-id>.json`. Если вложение есть → POST `/data?conflictPolicy=override`. Нет → POST create. Возврат: новая `version` вложения.

Порядок записи прогона: **сначала вложение, потом PUT storage** (ТЗ §5.7, §13: если storage упал — гант новый, «Итого» старое; повторить PUT, вложение не откатывать).

---

### 2.9 `scripts/macro.py` — найти / собрать макрос

**Сигнатуры:**

```python
@dataclass
class MacroRef:
    macro_id: str
    param_id: str
    param_hash: str
    attachment_name: str  # gantt-chart-<macro-id>.json

def find_macro(storage: str) -> MacroRef | None
def macro_span(storage: str) -> tuple[int, int] | None  # start,end в storage
def new_macro_ids() -> tuple[str, str, str]  # новые uuid; id/hash не копировать с 519501810
def build_macro_html(macro_id, param_id, param_hash) -> str
```

Storage эталон:

```html
<p><ac:structured-macro ac:name="gantt-chart-planner" ac:schema-version="1" ac:macro-id="<uuid>">
<ac:parameter ac:name="id"><uuid-or-hex></ac:parameter>
<ac:parameter ac:name="hash"><uuid-or-hex></ac:parameter>
</ac:structured-macro></p>
```

На **существующем** макросе `macro-id` / `id` / `hash` **не менять**. Ключ страницы = **pageId** (пара id+hash у теста `519501810` и живой `519492935` совпала из копии).

Тестовый макрос (не копировать на новые страницы): `ac:macro-id=25b9de75-cb34-4cc1-a17a-c314457308b2`. Вложение теста: id `519501809`.

---

### 2.10 `scripts/child_page.py` — POST дочки

**Сигнатуры:**

```python
def default_child_title(parent_title: str, today: date | None = None) -> str
    # «<title родителя>. План <ДД.ММ.ГГ>»
def build_child_storage(itogo_html: str, macro_html: str) -> str
def create_child_page(client, parent_id, title, itogo_html) -> tuple[dict, str, str, str]
    # GET родителя → space.key; new_macro_ids; POST content; вернуть page + uuid
```

Спайк (не эталон содержимого): родитель `519501810` → дочка `519502120`, space `~tkachenkoav`. Регресс на `HF:test` — новая дочка от того же родителя, не перетирая спайк без нужды.

Правило C (ТЗ §3 Q3): MPP → из MPP; иначе родитель с гантом → копия JSON; иначе пустой шаблон.

---

### 2.11 `scripts/gate_diff.py` — гейт §11

**Сигнатуры:**

```python
def is_confirmed(text: str) -> bool  # лей / пиши / да (регистр неважен; иное → False)
def build_diff(*, page_id, title, operation, gantt=None, had_existing_plan=False,
               itogo_before=None, itogo_after=None, child_title=None,
               empty_plan=False, warnings: list[str] | None = None,
               new_resource_names: list[str] | None = None) -> str
```

Показывать до любого POST/PUT:

- pageId, title, URL (`env.page_url`);
- операция: замена JSON / установка макроса / новая дочка;
- для дочки — черновик title;
- сводка: число задач, start–end корня, новые ресурсы (имена без матча, напр. «Найм»);
- «Итого» было → стало;
- если на странице уже был план: **«план будет заменён целиком; правки не из этого MPP сгорят»**.

Без подтверждения CLI/pipeline **ноль** write-методов.

---

### 2.12 `scripts/pipeline.py` + `scripts/cli.py` — прогон §5 и точка входа

**Трубопровод (после резолва pageId и наличия `.mpp` или ветки «дочка без файла»):**

1. Резолв цели: pageId из сообщения / `--page-id` / сессия чата; иначе стоп. Для дочки — parentId обязателен.
2. GET storage + attachments. Есть ли макрос.
3. Собрать JSON: MPP → convert+calendar; нет MPP + дочка + гант родителя → копия; нет источника → пустой шаблон.
4. Нет макроса / новая дочка → новые uuid; имя вложения `gantt-chart-<macro-id>.json`. Существующий макрос не трогать.
5. Две строки «Итого».
6. Гейт: печать диффа; ждать `--confirm лей`.
7. Запись: вложение → (свежий version) PUT storage.
8. Отчёт: URL, version вложения, «Итого».

**Защита живой AB:** pageId `519492935` без явного флага/`--allow-live-ab` **и** явного pageId от Саши → `PermissionError`. Не подставлять AB по умолчанию. Тестовый дефолт агента в SKILL.md: `519501810`.

**CLI (`scripts/cli.py`):**

```text
preview  --page-id ID                         # только GET
diff     --page-id ID [--mpp PATH] [--child] [--title T]
apply    --page-id ID --confirm лей|пиши|да [--mpp PATH] [--child] [--title T] [--allow-live-ab]
convert  --mpp PATH [--out FILE] [--template JSON]   # оффлайн, без REST
```

`--mpp` принимает `.mpp` и `.zip`. `apply` без `--confirm` → exit 2, HTTP write нет.

**Сессия pageId:** в CLI не persist-файл между сессиями Hermes. Память — реплика чата (SKILL.md). Новая сессия — пусто.

**Отказ «добавь задачу» без файла:** не в Python (это ветка SKILL.md); CLI без `--mpp` на `apply` не-child → ошибка.

---

### 2.13 Дельта черновика 09.09 → закрыть на HF:impl

Не invent-новые файлы. Точечно:

1. **Фикстуры самодостаточны:** скопировать `/tmp/gantt_test.json` (или урезанный) в `tests/fixtures/`; `conftest.gantt_test_template` не читать `/tmp`. CSV уже в `tests/fixtures/`. `.mpp` 080926 — положить в fixtures **или** `pytest.mark.skipif(not path.exists())` для JVM-календаря.
2. **«Итого» нет блока:** всегда вставка **над макросом**, если макрос найден. Сейчас `apply_plan` при `macro is None` делает `apply_itogo(storage)+macro_html` (макрос в конце, «Итого» может оказаться не над ним, если в storage уже был текст).
3. **PUT version:** повторный GET после upload вложения.
4. **Тесты §3:** дерево; копия/пустой; «Итого» нет-блока; live skipped; мок REST без сети.
5. **`prepare_apply_diff`:** ветка без MPP на странице с макросом — не патчить задачи (ТЗ §10); CLI и так требует `--mpp` для apply не-child — OK, описать в SKILL.md.
6. **Warning не-FS** — опциональный проход mpxj, не блокер v1.
7. Не вызывать `restore-all-skills.sh` из `HF:impl`.

---

### 2.14 `references/`

| Файл | Назначение |
|---|---|
| `empty-gantt-template.json` | Пустой план: ключи §6, один корень, `idCounter=2`, календарь шаблона теста (ночь 17–08 допустима **только здесь**) |
| `mpp-to-gantt.md` | Рецепт для агента: колонки CSV, rollup, Найм, idCounter, запрет 300000. Не runtime |

---

## 3. Юнит-тесты (pytest оффлайн)

**Канон запуска (HF:test, без live):**

```bash
cd ~/hermes-workspace/skills/productivity/edit-plan-confluence
~/hermes-agent/.venv/bin/python3 -m pytest tests -q -m "not live"
```

`tests/conftest.py`: `sys.path ← scripts/`; фикстуры CSV 080926 из `tests/fixtures/` (копия `/tmp/ab_080926_пункт12__*.csv`, utf-8-sig). **Не** зависеть от `/tmp` на runtime тестов.

`tests/pytest.ini`: маркер `live`.

### 3.1 Девять обязательных сценариев (фикстура CSV 080926)

| # | Файл (или test-функция) | Критерий pass |
|---|---|---|
| 1 | `test_mpp_convert.py::test_convert_task_count` | событий в дереве **33** (без id=0); CSV rows 34 |
| 2 | `test_mpp_convert.py::test_tree_structure` (**добавить**) | один корень id=1, `outline_level`→`children`; `parentId`/`parentIndex`; rollup у summary; вехи id=2 и id=33 `duration=0`; 18 детей корня |
| 3 | `test_mpp_convert.py::test_fs_dependencies_only` | все deps `type=2`, `lag=0`; число ≥1 (эталон newplan = 28) |
| 4 | `test_mpp_convert.py::test_naim_resource_added` | имя «Найм» в `resourcesData`; по одному id на имя (мёртвые копии шаблона отброшены) |
| 5 | `test_itogo.py::test_itogo_from_csv_080926` | даты `28.09.26`/`18.05.27`, N=`154`, M=`2356`; `format_thousands(1960)=="1 960"`; в HTML разделитель ` - `, нет `70%` |
| 6 | `test_pipeline.py` / `test_mpp_convert.py::test_copy_and_empty` (**добавить**) | пустой: 1 корень, 0 детей, пустые deps/assignments, дифф содержит «план пустой»; копия: deepcopy родителя, `idCounter==max+1` даже если в родителе было 300000 |
| 7 | `test_mpp_convert.py::test_id_counter_not_300000` | `idCounter != 300000` и `== max(все id)+1` |
| 8 | `test_itogo.py` патч (**дополнить**) | **нет блока** → две строки вставлены **над** `gantt-chart-planner`; **есть блок** → даты/N/M заменены; **хвост 70%** сохранён, третья строка не создана |
| 9 | `test_mpp_calendar.py` | `base_recurrent_intervals`: обед 12–13, ночь **18–09**, Sat/Sun; `exceptions_to_intervals` `toDate+1`. JVM `calendar_from_mpp` — skip если нет `.mpp` в fixtures |

### 3.2 Мок REST (оффлайн, обязательно)

Файл `tests/test_gantt_attachment.py` / `tests/test_conf_client.py`:

- `unittest.mock.patch` на `ConfluenceClient._request` или `urllib.request.urlopen`.
- `upload_gantt_json` при существующем attach: URL содержит `/data?conflictPolicy=override`, метод POST, не PUT.
- `apply_plan` / `create_child_with_plan` с `confirm="нет"` / пустым → исключение, **число write-вызовов = 0**.
- `confirm="лей"` на моке: порядок upload затем put_page.
- `_guard_page("519492935")` без флага → PermissionError.

Сеть в этих тестах не открывать.

### 3.3 Live REST — только skipped

`tests/test_rest_live.py`:

```python
pytestmark = pytest.mark.live
```

И внутри: `pytest.skip` если `os.environ.get("EDITPLAN_LIVE") != "1"`.

Сценарии (не гонять на HF:impl / по умолчанию HF:test):

- GET `519501810` + download вложения (read-only можно отдельно, но всё равно только по команде Саши — единый маркер live).
- POST `/data` на тесте + PUT «Итого».
- POST дочки от `519501810`.

**Запрет:** любые вызовы к `519492935` в тестах, даже live.

Запуск live **только** явная команда Саши:

```bash
EDITPLAN_LIVE=1 ~/hermes-agent/.venv/bin/python3 -m pytest tests -m live
```

### 3.4 Прочие оффлайн (желательно, не вместо девяти)

- `test_mpp_input.py`: zip с `.mpp` внутри → `resolve_mpp_path` возвращает `.mpp` (синтетический zip в tmp_path).
- `test_macro.py`: новые uuid ≠ тестового `25b9de75-…`; `find_macro` на эталонном HTML.
- `test_gate_diff.py`: `is_confirmed`; текст предупреждения полной замены.
- `test_cli.py`: `--help`; `convert` оффлайн; `apply` без `--confirm` → exit 2.
- `test_env.py`: парсер игнорирует чужие ключи `.env` (tmp файл).

---

## 4. Структура `SKILL.md`

Путь: `~/hermes-workspace/skills/productivity/edit-plan-confluence/SKILL.md`.

### 4.1 Frontmatter

```yaml
name: edit-plan-confluence
description: >-
  Заливка плана MS Project (.mpp/.zip) на страницу Confluence с макросом
  gantt-chart-planner. Триггеры: «поправь план», «обнови план», «помести план»,
  «скорректируй план», «добавь задачу в план», «создай страницу с планом»,
  «поставь гант на страницу». Гейт: дифф + «лей». Без pageId — спросить.
  Живую AB 519492935 не трогать без явного pageId.
version: "0.2.0"   # или 1.0.0, но согласовать с ТЗ v0.2.0; не 300000-история
platforms: [linux]
tools: [terminal, read_file, write_file]
metadata:
  hermes:
    tags: [confluence, gantt, plan, mpp, gantt-chart-planner]
    related_skills: [tutu-confluence-jira, read-mpp]
```

### 4.2 Разделы тела (обязательные)

1. **Overview** — JSON живёт во вложении, не в storage плагина; v1 = полная заливка MPP; чат-патчи = этап 2.
2. **Триггеры** — полный список из ТЗ §10.
3. **Подготовка / Авторизация** — bash `load_confluence_env` (CONFLUENCE_TOKEN + WORKVAULT_PATH, не `source` всего `.env`); zip: «переименуй .mpp в .zip»; venv + `read_mpp.py`; запрет `web_extract` на `dom.tutu.ru`.
4. **Входные ветки (§10)** — таблица: файл+pageId; файл без страницы → спросить; «создай дочку» → title-черновик + правило C; «добавь задачу» без файла → **отказ** (этап 2); триггер без файла на странице с макросом → спросить файл, не патчить задачи.
5. **Гейт §11** — дифф; ждать «лей»/«пиши»/«да»; предупреждение полной замены; нет pageId — спросить, **не** писать на `519492935`.
6. **Сессия pageId** — помнить последний подтверждённый id **в этой сессии**; новая сессия пустая.
7. **Прогон** — шаги §5 + команды CLI из §2.12.
8. **Пост-flow** — короткий отчёт: URL `https://dom.tutu.ru/pages/viewpage.action?pageId=`, version вложения, две строки «Итого». Если PUT storage упал после JSON — повторить PUT, не откатывать вложение.
9. **Питфоллы** — idCounter max+1; POST `/data` не PUT; ключ=pageId; мёртвые группы ресурсов; M = sum work CSV; ночь 18–09 на заливке MPP.
10. **Соседи / коллизия** — не вызывать `read-mpp` пайплайн GS, `page-to-schedule`, `mpp-to-google-sheets`; `confluence-gantt-plan` не канон (после Т7 — удалён).

---

## 5. Точки проверки (Т0…Т8)

Исполнитель проходит промежуточные точки **молча** (`hermes-feature` Блок 1А). Live (Т4–Т6) — не в `HF:impl`; только `HF:test` после явной команды Саши.

Тестовая страница: **`519501810`**. Живая AB **`519492935` не трогать** без явного OK Саши.

| Точка | Когда | Критерий pass | Fail |
|---|---|---|---|
| **Т0** | старт `HF:impl` | каталог скилла канон `{SKILL.md, references/, scripts/, tests/}`; фикстуры CSV в `tests/fixtures/`; чужие репо не изменены | правки `read_mpp.py` / ТЗ / манифеста |
| **Т1** | конвертер | pytest сценарии 1–4, 7: 33 задачи, дерево, FS, «Найм», idCounter=max+1 ≠300000 | idCounter 300000; несколько корней; копии ресурсов |
| **Т2** | календарь + «Итого» цифры | сценарии 5 и 9: N=154, M=2356, даты корня; рекуррент 18–09; toDate+1 | M=1915; ночь 17–08 на ветке MPP |
| **Т3** | патч storage | сценарий 8: нет/есть/хвост 70% | третья строка создана; хвост изменён; вставка не над макросом |
| **Т4** | копия/пустой + гейт оффлайн | сценарий 6; мок REST: без confirm write=0; дифф содержит предупреждение полной замены | apply без лей ходит в HTTP |
| **Т5** | live GET/POST на **`519501810`** | только `EDITPLAN_LIVE=1` + команда Саши; version вложения бамп; макрос id/hash не сменились | запись на `519492935`; PUT attachment 405 |
| **Т6** | регресс спайка | дочка REST от `519501810`: новые uuid, вложение, «Итого» над макросом, плагин рендерит; не обязаны совпасть с `519502120` | скопирован `macro-id=25b9de75-…` |
| **Т7** | гигиена коллизии | после появления канона: каталог `~/.hermes/skills/productivity/confluence-gantt-plan/` убран (перенос в `~/.hermes/_Archives/…/confluence-gantt-plan/` или удаление); триггеры ведут только на `edit-plan-confluence`. `restore-all-skills.sh` — **не** здесь, а `ORCH:shared-state` | два скилла с «поправь план» |
| **Т8** | приёмка с Сашей на тесте | ТЗ §15: дерево/FS/ресурсы/праздники; «Итого» = даты корня + ceil; рендер плагина. Статус «готово» плана ставит Саша (`GATE:done`) | само-complete без Саши в пошаговом ходе |

`HF:docs-handoff`: добить SKILL.md §4; `manifest_hints` в metadata complete (исполнитель **не** пишет `EcosystemManifest.json`).  
`ORCH:shared-state`: `restore-all-skills.sh`, манифест, digest — оркестратор.

---

## 6. Откат (Блок 5 `hermes-feature`)

### 6.1 Конфиг Hermes

`HF:backup` (координатор) **до** `HF:impl`. Этот SKILL-DEV **не** должен трогать `config.yaml` / `jobs.json`. Если карточка backup подтвердила «не затронуты» — архив конфига можно не копировать. Если всё же затронуты — `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (хранение 2 недели).

Исполнитель в `HF:impl` бэкап конфига **не** делает (правило Блока 5: исполнитель — только если затронут config/jobs).

### 6.2 Незакоммиченные скрипты скилла

Канон ещё не в git-релизе Hermes. Откат кода:

```text
# вернуть скилл к состоянию «нет канона» (только по ОК Саши / авария)
mv ~/hermes-workspace/skills/productivity/edit-plan-confluence \
   ~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/edit-plan-confluence
```

Не делать `git push --force`, не чистить `_Archives` моложе 2 недель.

Коллизия: перед удалением `confluence-gantt-plan` — скопировать в тот же backup. Откат гигиены = вернуть каталог из архива.

### 6.3 REST-записи (Confluence)

Авто-отката вложения **нет** (`conflictPolicy=override` необратим без повторной заливки предыдущего JSON).

| Сбой | Действие |
|---|---|
| POST вложения ок, PUT storage упал | Повторить PUT storage со свежим `version`; JSON не откатывать |
| Нужен откат теста `519501810` | Взять JSON из `/tmp/spike-backup/testpage_attachment_v4.json` (если жив) или скачать предыдущую version вложения; POST `/data` + PUT storage. Только по команде Саши |
| Случайно записали не ту страницу | СТОП + Саша. Не «чинить» живую AB без явного pageId |

Кроны не создавались — откатывать `jobs.json` нечего.

Gateway не рестартовать.

---

## 7. Что НЕ трогать (исполнитель / этот план)

- Мастер-ТЗ `EditPlanConfluence_TZ.md`, `MAIN_TZ_INVENTORY.md`, `EcosystemManifest.json`, `entities.json`, `.env`, `jobs.json`, `restore-all-skills.sh`.
- `~/USERTOOLS/MppReader/read_mpp.py` — только вызов.
- Скиллы `page-to-schedule`, `read-mpp`, `mpp-to-google-sheets`, пакет ConfluenceSync, `tutu-confluence-jira` (паттерн env **скопировать**, файлы соседа не патчить).
- Любые pageId кроме явно указанного / сессионного / созданной дочки. По умолчанию тест = `519501810`.
- `macroConfig.jiraFieldMappings`, крон, Gateway, `contacts.enc`.
- Этап 2 ТЗ (поштучные правки, каскад, SS/FF, JSON→MPP, проза 70%).

---

## Прогресс выполнения

Чекбоксы для устойчивости к сбою. Эту фазу отмечает архитектор; хвост — исполнитель/координатор/оркестратор по своим карточкам.

### HF:plan (эта карточка)

- [x] Прочитаны GLOSSARY §5.2, `hermes-feature` Блок 1А, master-ТЗ v0.2.0 §4–§16
- [x] Прочитаны эталоны `/tmp/mpp_to_gantt.py`, `/tmp/build_calendar2.py`, JSON/CSV 080926
- [x] Сверка диска: черновик скилла есть; коллизия `confluence-gantt-plan` есть; `read_mpp.py` на месте
- [x] План-файл записан: `TZ/EditPlanConfluence/plans/HF-plan_EditPlanConfluence_20260909.md`
- [ ] `REV:plan` (ревизор) — **не эта фаза**
- [ ] `GATE:plan-approve` — ждёт Сашу / one-pass

### HF:backup → HF:impl (после approve)

- [ ] `HF:backup`: config/jobs не трогаем или архив создан
- [ ] Т0 каркас + фикстуры без `/tmp`
- [ ] `env.py` + bash-паттерн в SKILL.md
- [ ] `mpp_input.py` вызывает `read_mpp.py`, zip
- [ ] `mpp_convert.py` (дерево, FS, Найм, idCounter max+1, effort листьев)
- [ ] `mpp_calendar.py` (18–09, toDate+1)
- [ ] `itogo.py` (ceil N/M, патч нет/есть/хвост, вставка над макросом)
- [ ] REST: `conf_client` / `gantt_attachment` / `macro` / `child_page` (POST `/data`, свежий version)
- [ ] `gate_diff.py` + `pipeline.py` + `cli.py` (§5)
- [ ] SKILL.md §4 (ветки, гейт, сессия, отказ без файла, post-flow)
- [ ] Дельта §2.13 закрыта

### HF:test

- [ ] pytest `-m "not live"`: 9 сценариев зелёные
- [ ] мок REST: без лей write=0
- [ ] Т5–Т6 live — только по команде Саши
- [ ] Т7 коллизия погашена
- [ ] `519492935` не записывалась

### HF:docs-handoff → ORCH:shared-state → GATE:done

- [ ] SKILL.md финальный; `manifest_hints` отданы оркестратору
- [ ] `ORCH:shared-state`: restore + манифест (не исполнитель)
- [ ] Т8 приёмка Саши на `519501810`
- [ ] `GATE:done` после preflight

---

## Приложение A. Ожидаемые цифры фикстуры 080926 (проверено 09.09)

Источник: `/tmp/ab_080926_пункт12__{tasks,resources,assignments}.csv`.

- Задач в CSV: 34 (id=0 служебный + 33 в дереве).
- Корень: id=1, «Доработки АБ-платформы ТУТУ до Trisigma - оценка», duration `154.0 d`, start `2026-09-28T09:00`, finish `2027-05-18T18:00`.
- Ресурсы с именами: 16 включая **Найм**.
- Назначений: 32 строк, из них 27 с `resource_id`; sum work всех = **2355.2** → ceil **2356**.
- Эталон `/tmp/gantt_newplan.json`: 33 events, 28 FS, 16 resources, `idCounter=300000` (**брак, не копировать**).
- Эталон `/tmp/gantt_test.json`: ночь 17–08 = живой шаблон вложения, не рецепт MPP.

## Приложение B. Карта модулей → вызовы

```
cli.py
  ├─ env.load_confluence_env          (паттерн tutu-confluence-jira, не import соседа)
  ├─ mpp_input.resolve_mpp_path/export_csv → USERTOOLS/MppReader/read_mpp.py
  └─ pipeline.preview/diff/apply/child
        ├─ conf_client (GET/POST/PUT REST)
        ├─ gantt_attachment
        ├─ macro
        ├─ child_page
        ├─ mpp_convert + mpp_calendar
        ├─ itogo
        └─ gate_diff  (стоп без «лей»)
```
