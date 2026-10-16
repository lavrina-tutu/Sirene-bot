---
tool: ProtocolFromSummary
version: 0.1-pilot
role: implementation-plan
author: Opus (architect)
executor: Sonnet
date: 2026-07-10
scope: pilot (Trisigma project + Кирилл 1-1 only)
---

# ProtocolFromSummary — Пофайловый план реализации и тестирования (пилот)

Документ описывает, что и как должен реализовать Sonnet по пилотному скоупу
§3 ТЗ (Trisigma pageId 490170597 + Кирилл 1-1 pageId 508804979). Всё, что не
упомянуто явно, — вне скоупа этой итерации.

Опорное ТЗ: `../ProtocolFromSummary_TZ.md` (§1.1–1.7, §3). При расхождении
между этим планом и ТЗ — победа за ТЗ.

## 0. Корневая раскладка

Инструмент живёт как отдельный Python-пакет в `USERTOOLS/`, по аналогии с
`MoveFromFF`, `ConfluenceSync`, `AggregateFromMeetings`:

```
/home/tkachenkoav/USERTOOLS/ProtocolFromSummary/
├── pyproject.toml
├── README.md
├── protocolfromsummary/
│   ├── __init__.py
│   ├── __main__.py            # CLI entrypoint (python -m protocolfromsummary)
│   ├── config.py              # env, пути, константы реестра pageId→prefix
│   ├── logger.py              # logging setup (аналог MoveFromFF/logger.py)
│   ├── summary_parser.py      # parse .md summary → dataclass MeetingSummary
│   ├── route.py               # определение сущности по имени файла встречи
│   ├── contacts_resolver.py   # ФИО → confluence userkey (contacts.enc + Confluence API fallback)
│   ├── rooms.py               # meeting-rooms.md → set имён/подстрок
│   ├── date_utils.py          # словесная дата → YYYY-MM-DD; fallback +7 дней
│   ├── storage_xml.py         # генерация фрагмента storage XML для новой строки таблицы
│   ├── page_merger.py         # GET page → парс таблицы → insert row after header → PUT
│   ├── confluence_ext.py      # тонкая обёртка/переиспользование ConfluenceClient + user resolve
│   ├── registry.py            # локальный реестр meeting_id → {pageId, published_at, ...}
│   └── pipeline.py            # публичная функция run_pilot(summary_path, *, confirm_republish)
├── tests/
│   ├── conftest.py
│   ├── test_summary_parser.py
│   ├── test_route.py
│   ├── test_contacts_resolver.py
│   ├── test_date_utils.py
│   ├── test_storage_xml.py
│   ├── test_page_merger.py
│   └── test_pipeline_e2e_real.py   # РЕАЛЬНЫЕ прогоны, помечены @pytest.mark.live_confluence
└── state/                     # gitignore; создаётся при первом запуске
    └── _registry.json         # meeting_id → {...}
```

Runtime state (реестр публикаций) не в пакете, а в
`/home/tkachenkoav/WorkVault/ProtocolFromSummary/_registry.json` — по аналогии
с MoveFromFF, чтобы данные жили в WorkVault, а код — в USERTOOLS.

## 1. Зависимости и повторное использование

Реюзаем уже имеющееся, ничего не форкаем:

- `USERTOOLS/ConfluenceSync/confluencesync/confluence_client.py`
  - `ConfluenceClient(base_url, token)` — Bearer-сессия с retry.
  - `get_page(page_id, expand="body.storage,version")` — читаем storage.
  - `update_page(page_id, title, storage_html, version)` — PUT.
- `USERTOOLS/AnywhereContacts/anywhere_contacts/store.py`
  - `create_store()` / `ContactStore` (`find_contacts`, `get_contact`,
    `update_contact`). Ключ шифрования — `CONTACTS_ENCRYPTION_KEY` из
    `USERTOOLS/AnywhereContacts/.env`.
  - `CUSTOM_FIELDS` уже включает `confluence_login`, `confluence_userkey` —
    защищены от перезаписи синком.
- `.env` файлы:
  - `USERTOOLS/ConfluenceSync/.env` → `CONFLUENCE_TOKEN`, base URL `https://dom.tutu.ru`.
  - `USERTOOLS/AnywhereContacts/.env` → `CONTACTS_ENCRYPTION_KEY`.

`pyproject.toml` пакета:
```toml
[project]
name = "protocolfromsummary"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "requests>=2.31",
  "python-dotenv>=1.0",
  "lxml>=4.9",
  "pydantic>=2.5",
  "tenacity>=8.2",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-mock>=3"]

[tool.setuptools.packages.find]
include = ["protocolfromsummary*"]
```

Установка в тот же venv, что и ConfluenceSync/AnywhereContacts, чтобы импорты
работали (`pip install -e .` из директории пакета; в тестах —
`sys.path`-манипуляции не нужны, если venv общий; иначе `pip install -e` для
`AnywhereContacts` и `ConfluenceSync` тоже).

## 2. Модули — сигнатуры и контракты

### 2.1 `config.py`

```python
from pathlib import Path

MEETINGS_DIR = Path("/home/tkachenkoav/WorkVault/Meetings/NewMeetings")
CONTACTS_ENC = Path("/home/tkachenkoav/WorkVault/Contacts/contacts.enc")
ROOMS_MD     = Path("/home/tkachenkoav/WorkVault/Contacts/meeting-rooms.md")
STATE_DIR    = Path("/home/tkachenkoav/WorkVault/ProtocolFromSummary")
REGISTRY_JSON = STATE_DIR / "_registry.json"

CONFLUENCE_BASE_URL = "https://dom.tutu.ru"

# pageId → (entity_slug, tag_prefix_or_None, kind)
# kind ∈ {"project", "one_on_one"}
PILOT_ROUTES = {
    "trisigma":     {"page_id": "490170597", "tag": "Trisigma.", "kind": "project",
                     "name_match": ["trisigma"]},
    "kirill_1on1":  {"page_id": "508804979", "tag": None,        "kind": "one_on_one",
                     "name_match": ["кирилл 1-1", "кирилл - саша", "кирилл — саша",
                                    "саша - кирилл", "криворотов"]},
}
DEFAULT_ASSIGNEE_LOGIN = "tkachenkoav"
DEADLINE_FALLBACK_DAYS = 7
```

`name_match` — список подстрок в lower-case; матч на имя встречи через `any(sub in name_lower for sub in name_match)`. Для встреч типа `AB-платформа` (тот же pageId) в пилот НЕ входит — оставляем на итерацию 2.

### 2.2 `summary_parser.py`

```python
@dataclass
class MeetingTask:
    assignee_raw: str          # "Криворотов Кирилл" / "Юра" / "Ткаченко Александр Владимирович"
    text: str                  # "Обновить токены Motor-Mast и Loop Assistant"
    deadline_raw: str | None   # "после получения ответа от Кости", "до пятницы", "без срока"

@dataclass
class MeetingSummary:
    source_path: Path
    meeting_id: str            # stem файла без " - summary" (используется как ключ реестра)
    meeting_name: str          # часть имени файла после "YYYY-MM-DD HH-MM-SS "
    meeting_date: date         # из имени файла
    participants: list[str]    # ["Ткаченко Александр Владимирович", ...]
    decisions: list[str]
    blockers: list[str]
    tasks: list[MeetingTask]
    risks: list[str]           # для пилота НЕ выводим в протокол, но парсим

def parse_summary_file(path: Path) -> MeetingSummary: ...
```

Парсинг: разделы по markdown-заголовкам `##`/`#` и по строкам-подписям
`Участники:`, `Решения:`, `Блокеры:`, `Задачи:`, `Риски:` / `## Задачи:` — в
двух реальных summary формат «плоский» с `- ` пунктами (см. Trisigma
09.07.2026 — плоские `Участники:`, `Решения:` без `##`; Кирилл 09.07.2026 —
`## Участники:`). Парсер должен переваривать оба варианта: любое вхождение
подстроки-заголовка (регистронезависимо, с `##`/`#`/без) начинает секцию до
следующей секции или EOF.

Формат строки задачи: `- <assignee_raw>: <task_text> / <deadline_raw>`.
Разделитель — последний ` / ` в строке (без него `deadline_raw=None`).

### 2.3 `route.py`

```python
@dataclass
class Route:
    entity: str           # "trisigma" | "kirill_1on1"
    page_id: str
    tag_prefix: str | None
    kind: str             # "project" | "one_on_one"

def resolve_route(meeting_name: str) -> Route | None: ...
```

Логика пилота: перебираем `PILOT_ROUTES`, matching по substring из
`name_match`. Первый match — победа. Нет match → вернуть `None` (пилот НЕ
публикует, только логирует «out of pilot scope», не идёт в неразобранное —
это вне скоупа).

### 2.4 `rooms.py`

```python
def load_room_names(rooms_md: Path) -> set[str]:
    """Возвращает нижнерегистровые "имена" переговорок из первой колонки
    таблицы meeting-rooms.md (например: "англетер (спб) (8) - zoom")."""

def is_meeting_room(name: str, rooms: set[str]) -> bool:
    """True если участник — переговорка (совпадение по substring в обе стороны)."""
```

### 2.5 `contacts_resolver.py`

```python
@dataclass
class ResolvedParticipant:
    raw: str                # исходное ФИО из summary
    login: str | None       # tkachenkoav
    userkey: str | None     # 8a...  (Confluence userKey)
    fio: str | None
    is_room: bool = False
    resolved: bool = False  # False → mention не строим, оставляем текстом

def resolve_participants(
    raws: list[str],
    *,
    store: "ContactStore",
    confluence: "ConfluenceClient",
    rooms: set[str],
) -> list[ResolvedParticipant]:
```

Алгоритм на каждый raw (ТЗ §1.4, шаги 1–3; шаг 4–5 Haiku — ВНЕ пилота):
1. Если `is_meeting_room(raw, rooms)` → `is_room=True`, `resolved=False`.
2. `store.find_contacts(raw)` — если ровно 1 результат, берём его.
   Если несколько: пробуем сузить более специфичной подстрокой (последнее
   слово — обычно фамилия; для формата «Фамилия Имя Отчество» — первое
   слово). Если всё равно >1 — `resolved=False`, warning в лог, оставляем
   текстом.
3. Если у контакта есть `confluence_userkey` — заполняем и возвращаем.
4. Иначе — Confluence API:
   `GET /rest/api/search?cql=user.fullname~"<FIO>"&limit=5&expand=user`.
   Из результата достаём `user.username` и `user.userKey`.
   Если ровно один осмысленный кандидат — `store.update_contact(login,
   {"confluence_login": username, "confluence_userkey": userkey})` (кэш) и
   возвращаем resolved.
5. Не резолвится → `resolved=False`, оставляем текстом, в лог warning.

Резолвер ЗАДАЧИ на исполнителя (`MeetingTask.assignee_raw`) — та же логика
`resolve_participants([assignee_raw], ...)`. Если `is_room=True` — задача
переадресуется на `DEFAULT_ASSIGNEE_LOGIN` (`tkachenkoav`), исходный текст
задачи ПРЕФИКСУЕТСЯ комментарием `(переговорка <имя>) ` — так Саша при
разборе видит, что задача пришла с переговорки.

Реализация Confluence-поиска пользователя — в `confluence_ext.py`:

```python
def find_user_by_fullname(client: ConfluenceClient, fio: str) -> dict | None:
    """GET /rest/api/search?cql=user.fullname~"<fio>". Возвращает dict с
    ключами username, userKey, displayName либо None."""
    # Реальный запрос:
    # GET https://dom.tutu.ru/rest/api/search?cql=user.fullname~%22<fio>%22&limit=5
    # Ответ: {"results":[{"user":{"type":"known","username":"...","userKey":"...","displayName":"..."}}]}
```

### 2.6 `date_utils.py`

```python
def parse_deadline(text: str | None, *, meeting_date: date, today: date) -> date:
    """
    Слова → дата.
    Правила пилота:
    - None/пусто/"без срока"/"не указан" → today + DEADLINE_FALLBACK_DAYS.
    - "сегодня"                          → today.
    - "завтра"                           → today + 1.
    - "послезавтра"                      → today + 2.
    - "до пятницы"/"к пятнице"/"пятница" → ближайшая пятница ≥ today (weekday map: пн=0..вс=6).
    - "на следующей неделе"              → today + 7.
    - "к концу недели"/"до конца недели" → ближайшая пятница ≥ today.
    - "до конца месяца"                  → последний день текущего месяца.
    - "к <день>-<день>.<месяц>" (напр.  "к 15-18 июля")
                                         → берётся ПЕРВАЯ дата (15 июля текущего года).
    - "к <день> <месяц>"/"к <день>.<месяц>" → соотв. дата (в текущем году).
    - "к началу августа"                 → 1-е число месяца.
    - "к концу <месяц>"                  → последний день месяца.
    - Всё остальное неразборчивое        → today + DEADLINE_FALLBACK_DAYS + warning.
    """
```

`today` инъектируется параметром — тестируемо.

### 2.7 `storage_xml.py`

```python
def render_row(
    *,
    meeting_date: date,
    meeting_name: str,
    participants: list[ResolvedParticipant],
    decisions: list[str],
    blockers: list[str],
    tasks: list[tuple[MeetingTask, ResolvedParticipant, date]],  # task + resolved + deadline
    tag_prefix: str | None,
    task_id_start: int = 1,
) -> str:
    """
    Возвращает строку storage XML:
    <tr>
      <td><p>DD.MM.YYYY</p></td>
      <td>
        <p><strong>{meeting_name}</strong></p>
        <p><strong>Участники:</strong> ... </p>
        <p><strong>Решения:</strong></p>
        <ul>...</ul>
        <p><strong>Блокеры:</strong></p>
        <ul>...</ul>
        <p><strong>Задачи:</strong></p>
        <ac:task-list>
          <ac:task>...</ac:task>
          ...
        </ac:task-list>
      </td>
    </tr>
    """
```

Формат mention:
```xml
<ac:link><ri:user ri:userkey="{userkey}"/></ac:link>
```

Формат задачи:
```xml
<ac:task>
  <ac:task-id>{n}</ac:task-id>
  <ac:task-status>incomplete</ac:task-status>
  <ac:task-body>
    <span class="placeholder-inline-tasks">
      {mention_or_plain_name} {tag_prefix_if_any}{task_text}
      <time datetime="YYYY-MM-DD" />
    </ac:task-body>
</ac:task>
```

Точный шаблон — свериться с реальными Trisigma (pageId 490170597) и Кирилл
1-1 (pageId 508804979) через `client.get_page(page_id).body.storage.value`
ПЕРЕД тем как рендерить (`test_page_merger.py::test_dump_reference_row`
делает это, кладёт эталонный фрагмент в `tests/fixtures/`, дальше рендер
сверяется по структурному equality через `lxml`).

Правила состава колонки «Задачи и Договорённости»:
- Пустые секции пропускаются (нет пустых `<ul/>`).
- Список участников — plain text, разделитель `, `, mention НЕ ставим для
  участников (mention — только внутри задач). Переговорки исключаются из
  строки участников.
- Если `tag_prefix` задан (Trisigma) — префикс идёт первой лексемой в
  `ac:task-body` перед mention: `Trisigma. <mention> текст <time/>`. Для
  1:1 — без префикса.
- `task-id` в новой строке нумеруется от `task_id_start`. Итоговое значение
  считает `page_merger` из максимального существующего `task-id` +1.

### 2.8 `page_merger.py`

```python
def insert_row_top(storage_html: str, new_row_xml: str) -> str:
    """
    Парсит storage через lxml (в XML-режиме, с фиктивным корнем и
    объявлениями ns: ac, ri). Находит ПЕРВУЮ <table>, внутри — <tbody>,
    вставляет new_row_xml сразу после первого <tr> (заголовок).
    Возвращает изменённый storage_html.

    Если <thead> используется — new_row вставляется первым в <tbody>.
    Если таблицы нет — ValueError (пилот не создаёт таблицу с нуля).
    """

def next_task_id(storage_html: str) -> int:
    """Возвращает max(<ac:task-id>) + 1 по всей странице, или 1 если задач нет."""
```

Замечания:
- lxml + `etree.fromstring` требует объявления namespace. Оборачиваем в
  корневой `<root xmlns:ac="..." xmlns:ri="...">…</root>` перед парсингом,
  затем сериализуем и разворачиваем обёртку регэкспом (или через
  `tostring(root)[len("<root ...>"):-len("</root>")]`).
- Namespaces:
  `ac="http://atlassian.com/content"`, `ri="http://atlassian.com/resource/identifier"`.

### 2.9 `registry.py`

```python
@dataclass
class RegistryEntry:
    meeting_id: str
    page_id: str
    entity: str
    meeting_date: str        # ISO date
    published_at: str        # ISO 8601 UTC
    row_task_ids: list[int]  # для будущего «перепривязать»
    source_summary: str      # basename исходного summary

class Registry:
    def __init__(self, path: Path): ...
    def get(self, meeting_id: str) -> RegistryEntry | None: ...
    def put(self, entry: RegistryEntry) -> None: ...  # atomic write через tmp+rename
    def all(self) -> list[RegistryEntry]: ...
```

Файл: `WorkVault/ProtocolFromSummary/_registry.json`:
```json
{"schema_version": "1.0", "entries": {"<meeting_id>": {...}}}
```

### 2.10 `pipeline.py`

```python
@dataclass
class PublishResult:
    meeting_id: str
    entity: str
    page_id: str
    action: str        # "published" | "skipped_duplicate" | "republished" | "out_of_scope" | "error"
    version_before: int | None
    version_after: int | None
    error: str | None = None

def run_pilot(
    summary_path: Path,
    *,
    confirm_republish: bool = False,
    dry_run: bool = False,
    today: date | None = None,
) -> PublishResult:
    """
    1. parse_summary_file(summary_path) → MeetingSummary
    2. route = resolve_route(summary.meeting_name); нет → out_of_scope, return.
    3. registry.get(meeting_id): если уже опубликовано → если
       confirm_republish=False → skipped_duplicate + warning. Если True →
       republish (вставить новую строку сверху ещё раз).
    4. rooms = load_room_names(); resolve_participants(...); фильтровать
       переговорки из списка людей.
    5. Для каждой задачи: parse_deadline(deadline_raw, meeting_date, today);
       resolve исполнителя (см. §2.5); переговорка-исполнитель → tkachenkoav.
    6. client.get_page(page_id) → storage_html, version, title.
    7. task_id_start = next_task_id(storage_html)
    8. row_xml = render_row(...)
    9. new_storage = insert_row_top(storage_html, row_xml)
    10. if dry_run → вернуть, ничего не PUT. Иначе:
        client.update_page(page_id, title, new_storage, version)
        registry.put(entry)
    11. Верификация: снова client.get_page(page_id), убедиться что
        new_storage.count("<tr>") == old.count + 1 и что первая строка после
        заголовка содержит meeting_date.
    """
```

### 2.11 `__main__.py` (CLI)

```
python -m protocolfromsummary run <path-to-summary.md> [--dry-run] [--confirm-republish]
python -m protocolfromsummary status         # список записей реестра
python -m protocolfromsummary verify <meeting_id>  # GET страницу, проверить наличие строки
```

Использует `argparse`. Логи — INFO по умолчанию, `--verbose` → DEBUG. По
итогу — печать `PublishResult` в человекочитаемом виде + JSON-строка для
скриптов.

## 3. Порядок реализации (для Sonnet)

1. `config.py`, `logger.py`, `pyproject.toml`, README stub.
2. `summary_parser.py` + `test_summary_parser.py` (юнит на двух реальных summary — см. §4.1).
3. `route.py` + тесты (юнит на именах реальных встреч).
4. `rooms.py` + тесты.
5. `date_utils.py` + тесты (все правила из §2.6, инъекция `today`).
6. `contacts_resolver.py` + `confluence_ext.py`. Юнит на mock-ах store и
   ConfluenceClient. Отдельный live-тест (`@pytest.mark.live_confluence`)
   на реальный резолв «Криворотов Кирилл» и «Малый Денис».
7. `storage_xml.py` + `page_merger.py` — сначала загрузить эталон:
   `client.get_page("490170597")` и `client.get_page("508804979")`, положить
   `body.storage.value` в `tests/fixtures/trisigma_before.xml` и
   `tests/fixtures/kirill_before.xml`. По ним написать тесты рендера и
   вставки (структурное сравнение через lxml canonicalize / etree.tostring
   на извлечённом фрагменте).
8. `registry.py` + тесты (tmpdir).
9. `pipeline.py` + `__main__.py`.
10. Live e2e (§4.2).

Каждый шаг — коммит-точка. Sonnet может запускать `pytest -x -q` после
каждого шага. Пока `test_pipeline_e2e_real.py` без флага `--live`
скипается (fixture `pytest.mark.live_confluence` фильтруется).

## 4. Тестовый план

### 4.1 Unit — оффлайн, обязательные к прохождению

Фиксированный набор реальных summary-файлов из
`/home/tkachenkoav/WorkVault/Meetings/NewMeetings/`:

- **T1**: `2026-07-09 11-30-00 Trisigma. Обсуждаем мысли Ильи по подготовке к полному внедрению - summary.md`
- **T2**: `2026-07-06 11-15-00 Trisigma. внутренний регулярный статус - summary.md`
- **K1**: `2026-07-09 07-35-00 Кирилл 1-1 - summary.md`
- **K2**: `2026-07-08 11-05-00 Кирилл 1-1 - summary.md`

Тесты:

- `test_summary_parser.py`:
  - `parse(T1).participants == ["Ткаченко Александр Владимирович", "Малый Денис"]`.
  - `parse(T1).tasks[0] == MeetingTask("Малый Денис", "Запустить AB-тесты к 15-18 июля", "Завершить к началу августа")` — обратите внимание, что разделитель — последний ` / `, а не первый (в задаче встречаются даты со слэшами).
  - `parse(K1).tasks[-1].assignee_raw == "Ткаченко Александр Владимирович"`.
  - `parse(K1).decisions` содержит 6 пунктов.
  - `parse(K1).meeting_date == date(2026, 7, 9)`.
  - `parse(K1).meeting_name == "Кирилл 1-1"`.

- `test_route.py`:
  - `resolve_route("Trisigma. Обсуждаем мысли Ильи ...").entity == "trisigma"`
  - `resolve_route("Кирилл 1-1").entity == "kirill_1on1"`
  - `resolve_route("AB-платформа. ...")` → `None` (вне пилота).
  - `resolve_route("Синк АиД")` → `None`.

- `test_contacts_resolver.py` (mock-ContactStore):
  - Известный `tkachenkoav` с `confluence_userkey` → возвращается сразу без
    Confluence-запроса (`mock_client.assert_not_called`).
  - Контакт без `confluence_userkey`: mock `find_user_by_fullname` возвращает
    dict, проверяем что `store.update_contact` вызван с
    `{"confluence_login": ..., "confluence_userkey": ...}` и что защищённые
    поля не затираются (флаг custom_updated_at обновляется).
  - Переговорка `"Тайга (8) - Zoom"` → `is_room=True`, `resolved=False`.
  - Задача с исполнителем-переговоркой → переадресация на `tkachenkoav` с
    префиксом.

- `test_date_utils.py` (`today=date(2026, 7, 10)`, meeting_date=`2026-07-09`):
  - `parse_deadline(None, ...) == date(2026, 7, 17)`
  - `parse_deadline("сегодня", ...) == date(2026, 7, 10)`
  - `parse_deadline("до пятницы", ...) == date(2026, 7, 10)`  (10.07 — пятница)
  - `parse_deadline("к 15-18 июля", ...) == date(2026, 7, 15)`
  - `parse_deadline("к началу августа", ...) == date(2026, 8, 1)`
  - `parse_deadline("на следующей неделе", ...) == date(2026, 7, 17)`
  - `parse_deadline("после получения ответа от Кости Петрухина", ...) == date(2026, 7, 17)` (fallback + warning).

- `test_storage_xml.py`:
  - `render_row` для T1 генерирует ровно один `<tr>` c двумя `<td>`;
    внутри второго — `<ac:task-list>` с 3 задачами; первая задача имеет
    префикс `Trisigma. `; mention `<ri:user ri:userkey="..."/>` для Дениса
    Малого; `<time datetime="2026-07-15"/>` (deadline из «к 15-18 июля»).
  - `render_row` для K1 — без префикса; задачи на Кирилла с его userkey.

- `test_page_merger.py`:
  - Загружает fixture (реальный дамп Trisigma), вставляет заранее сгенерённый
    row, проверяет: `<tr>`-count +1; новая строка идёт сразу после header
    (первый `<tr>` в `<tbody>`); все остальные `<tr>` сохранили порядок;
    `next_task_id` возвращает корректный max+1.

- `test_registry.py`:
  - `put` создаёт файл; повторный `get` возвращает ту же запись; atomic
    write (tmp+rename) не оставляет мусора при исключении.

### 4.2 Live — реальный прогон в Confluence

Помечены `@pytest.mark.live_confluence`, запуск: `pytest -m live_confluence`.

**Подготовка** (один раз, не в тестах, а вручную командой Sonnet):
`python -m protocolfromsummary verify_baseline` — GET обеих страниц
(`490170597`, `508804979`), сохранение `body.storage.value` и `version` в
`tests/fixtures/live_baseline/<page_id>_<utc>.xml`. Это база для отката,
если что-то пойдёт не так, и материал для регрессии рендера.

**Прогон** (в этом порядке, каждый как отдельный шаг с проверкой):

1. **Dry-run на T1** (`Trisigma 09.07.2026`):
   `python -m protocolfromsummary run "<PATH T1>" --dry-run` →
   PublishResult.action=="published" (dry — не пишет в реестр и не PUT),
   логи содержат сгенерённый row_xml. Проверить глазами и через
   assertion, что row_xml содержит:
   - `<ac:link><ri:user ri:userkey="...` для Малого Дениса,
   - `Trisigma. Запустить AB-тесты`,
   - `<time datetime="2026-07-15"`.

2. **Live публикация T1**: тот же вызов без `--dry-run`.
   После PUT — сразу GET той же страницы. Assertions:
   - `version.number` увеличился на 1;
   - в `body.storage.value` появилась ровно одна новая `<tr>` со строкой
     `09.07.2026` (или соответствующим форматом), содержащая mention Дениса
     Малого;
   - все существующие строки сохранены (сравнение хэшей всех `<tr>` кроме
     новой первой — множество совпадает с baseline).
   - `_registry.json` содержит запись `2026-07-09 11-30-00 Trisigma. ...`
     с page_id=490170597.

3. **Идемпотентность**: повторный запуск на T1 без флага →
   action=="skipped_duplicate", ничего не публикуется, версия страницы не
   меняется (GET → та же `version.number`, что после шага 2).

4. **Republish (явное подтверждение)**: `--confirm-republish` → добавляется
   ещё одна строка сверху. После этого — **ручной откат Саши**: удалить
   лишнюю дублирующую строку через веб-интерфейс Confluence, обновить
   `_registry.json` руками при необходимости. В тесте автоматом это не
   откатывается (мы не хотим маскировать баги).

5. **Live публикация K1** (`Кирилл 1-1 09.07.2026`) — те же 4 проверки, но
   без tag_prefix. Дополнительно: `assignee_raw="Артур Марьян"` — проверить,
   что резолвится через контакты или Confluence API fallback (если нет —
   остаётся plain text, warning в логе; тест это допускает, но фиксирует).

6. **Резолв переговорки в 1:1**: если в реальном K1/K2 переговорки нет
   (в исходниках нет — участники: Криворотов, Ткаченко), Sonnet готовит
   **синтетический** summary-файл `tests/fixtures/synthetic_kirill_room.md`
   на основе K1, добавляя `- Тайга (8) - Zoom` в участников и задачу
   `Тайга (8) - Zoom: проверить оборудование / завтра`. Прогон в
   **dry-run** (не публиковать синтетику): проверить, что список
   участников в row_xml НЕ содержит "Тайга", а задача переадресована на
   `tkachenkoav` с префиксом `(переговорка Тайга (8) - Zoom) `.

**Критерии успеха пилота**:
- Все unit-тесты зелёные.
- Шаги 1–3, 5, 6 живого плана — как ожидается.
- Шаг 4 — воспроизводится осознанно, откатывается вручную, задокументирован в логе прогона.

### 4.3 Отчёт о прогоне

Sonnet после реального прогона кладёт отчёт в
`WorkVault/Hermes-Backlog/TZ/ProtocolFromSummary/pm/PILOT_RUN_REPORT.md`:
что запускалось, что вставилось (page_id, version_before/after, task_ids),
что откатывалось, какие warnings, какие контакты дописались в contacts.enc,
какие остались нерезолвленными.

## 5. Границы и запреты (пилот)

- Не создаём таблицу с нуля; если её нет — abort с внятной ошибкой.
- Не пишем в pageId 331125844 (Синк АиД) — вне пилота.
- Не создаём cron; запуск ручной через CLI. Cron — отдельная задача итерации 2.
- Не используем Haiku fallback — если substring в contacts не резолвит и
  Confluence API не находит — `resolved=False`, warning, plain text.
- Не публикуем встречи из «out of scope» (всё, что не Trisigma / не Кирилл 1-1).
- Не удаляем строки со страницы. Даже при republish — только вставка сверху.
- Все дедлайны только в календарном формате `YYYY-MM-DD` внутри `<time/>`.

## 6. Секреты и окружение

```bash
export CONFLUENCE_TOKEN=$(grep CONFLUENCE_TOKEN /home/tkachenkoav/USERTOOLS/ConfluenceSync/.env | cut -d= -f2-)
export CONTACTS_ENCRYPTION_KEY=$(grep CONTACTS_ENCRYPTION_KEY /home/tkachenkoav/USERTOOLS/AnywhereContacts/.env | cut -d= -f2-)
```

`config.py` подхватывает через `python-dotenv` из обоих `.env` (fallback на
`os.environ`).

## 7. Открытые технические детали, которые Sonnet проверяет во время реализации

1. Точный XML эталонной строки на pageId 490170597 и 508804979 — снять
   через GET перед §2.7 (см. §3 шаг 7). Если формат отличается от
   ожидаемого в §2.7 (например, `<ac:task-list>` не в `<td>`, а в `<p>`) —
   Sonnet приводит `render_row` к фактическому формату, документирует
   отклонение в PILOT_RUN_REPORT и НЕ меняет ТЗ.
2. Формат отображения даты в левой колонке (`DD.MM.YYYY` vs `YYYY-MM-DD`
   vs текстом) — брать как на реальной странице (сверить с ближайшей
   существующей строкой baseline).
3. CQL user-search endpoint может отдавать `expandable.user` вместо
   развёрнутого — при необходимости добавлять `&expand=user` или запасной
   `GET /rest/api/user?username=...`.

Конец плана.
