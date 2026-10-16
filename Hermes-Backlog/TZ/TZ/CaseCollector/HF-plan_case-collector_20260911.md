---
tool: CaseCollector
phase: HF:plan
plan_version: 1.0
date: 2026-09-11
author: архитектор (cursor-grok-4.6-high)
case: SKILL-DEV
status: draft-plan
source_tz: TZ/CaseCollector/CaseCollector_TZ.md v0.1.0
executor: composer-2.5
next_phases: REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done
---

> HF:plan-patch 2026-09-11 — привязка критерия №8 ТЗ к именованному grep-тесту `test_no_jira_loop_exchange_jobsjson_in_scripts` по вердикту REV:plan (CHANGES_REQUIRED).

# HF:plan — CaseCollector (скилл `productivity/case-collector`)

Кейс **SKILL-DEV**: новый скилл в `~/hermes-workspace/skills/productivity/case-collector/`. Этот файл — самостоятельный артефакт фазы **HF:plan** (Блок 1А `hermes-feature`). Код скилла в этом вызове не писать. Каталог скилла на диске 11.09.2026 отсутствует (чистый старт). Объект для `REV:plan` и `GATE:plan-approve`.

Канон: master-ТЗ CaseCollector v0.1.0. Новая сущность USERTOOLS / `Tools/CaseCollector/` **не** заводится (OQ-1, OQ-8). Новый скилл обоснован постановкой (reuse-first: аналога в реестре нет).

---

## Прогресс выполнения

Устойчивость к сбою: чекбоксы отмечает исполнитель на `HF:impl` / `HF:test`. Архитектор на `HF:plan` их не закрывает. `ORCH:shared-state` — не эта фаза и не `HF:impl`.

- [x] **Этап 1.** Каркас скилла + CLI argparse + read-only `db.py` + dry-run инвентарь
- [x] **Этап 2.** Компакт-транскрипт + фильтры ролей / `active` / `compacted` / шум
- [x] **Этап 3.** JSON-контракт + фейковый адаптер (fixture) + чанки
- [x] **Этап 4.** Боевые адаптеры `HermesCallLlmAdapter` / `OpenAICompatAdapter`, модель из `--model` → env → `config.yaml`
- [x] **Этап 5.** Identity + `--user-map` + fallback суррогат
- [x] **Этап 6.** xlsx (`openpyxl`, `spreadsheet-deliverables`) + csv-fallback (`utf-8-sig`, `;`)
- [x] **Этап 7.** Pytest: fixture-sqlite (не живой `state.db`), overlap, chunk merge, exclude sources, no-write
- [ ] **Этап 8.** Ручной Linux-прогон 3 дня, отчёт Саше (после `GATE:plan-approve` + `HF:impl`/`HF:test`)
- [ ] **Этап 9.** `ORCH:shared-state`: restore-all-skills, манифест — **не сейчас**, не исполнителем

Легенда: `[x]` = этап принят по критерию проверки ниже. Не отмечать «на глаз».

---

## Цель плана

Спроектировать пофайловую поставку Hermes-скилла `productivity/case-collector`: по запросу Саши прочитать логи сессий (`state.db`, только чтение) за окно `--since`/`--until` и собрать таблицу **пользователь × тема кейса × начало × конец**, чтобы люди вручную сопоставили строки с Jira.

Инварианты, которые план обязан сохранить в реализации:

1. Кейсы — по **смыслу** (смена предмета задачи), не по 24-часовой границе сессии и не по `ended_at`.
2. Границы `начало`/`конец` считает **скрипт** (min/max `messages.timestamp` user-реплик с `id` в `[start_msg_id, end_msg_id]`). ISO-поля LLM игнорировать.
3. `state.db` — только read-only: `sqlite3.connect("file:<path>?mode=ro", uri=True)` + `PRAGMA query_only=ON`. Без `immutable=1`. Без write-SQL. `timeout ≥ 30`. Клиент — Python, не CLI `sqlite3`.
4. Модель не хардкодить: `--model` → env `CASE_COLLECTOR_LLM_MODEL` → `model.default` из `config.yaml`. Иначе exit ≠ 0.
5. LLM только через `complete()`; адаптеры `hermes` / `openai-compat` / `auto`. Запрещён `agent -p` / Cursor CLI как движок split.
6. В промпт — только `role=user` (+ опц. assistant stubs ≤200 символов). `tool` / `session_meta` никогда.
7. Выход: xlsx основной + csv-fallback. В чат — путь и счётчики, не таблица и не сырой диалог.
8. Переносимость: ни одного хардкода `/home/...`, Linux-specific chat/user id, Telegram `user_id` Саши. Путь к БД — параметр `--db`, дефолт `Path.home() / ".hermes" / "state.db"`.
9. Крон / `jobs.json` / ErrorBus / Jira / запись в `EcosystemManifest` / `MAIN_TZ_INVENTORY` — вне скоупа `HF:impl`.
10. Живой `~/.hermes/state.db` **не** открывать из pytest. Fixture-БД отдельная.

Критерии «готово» **этой** фазы (`HF:plan`): записан этот файл; код скилла / каталог `skills/productivity/case-collector/` / кроны / `state.db` / манифест **не** изменены. Снятие `GATE:plan-approve` — не эта фаза.

---

## Файлы

**Корень поставки (создаётся на `HF:impl`, сейчас отсутствует):**

```
/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/
  SKILL.md
  scripts/case_collector.py
  scripts/db.py
  scripts/transcript.py
  scripts/split_llm.py
  scripts/identity.py
  scripts/xlsx_out.py
  references/user-map.example.yaml
  references/split-prompt.md
  tests/conftest.py
  tests/test_db.py
  tests/test_transcript.py
  tests/test_split_llm.py
  tests/test_identity.py
  tests/test_xlsx_out.py
  tests/test_cli.py
```

`tests/` в master-ТЗ §12 не перечислены, но §14 шаг 7 и критерии успеха v1 требуют pytest. Создавать `tests/` на `HF:impl` вместе со скриптами; гонять на `HF:test`. `scripts/__init__.py` не заводить: модули — плоские скрипты, тесты добавляют `scripts/` в `sys.path` (паттерн `edit-plan-confluence`). Пакета USERTOOLS нет.

Интерпретатор: `Path.home() / "hermes-agent" / ".venv" / "bin" / "python3"` если файл существует, иначе `sys.executable` / `python3`. На Windows принимающий агент подставляет `Scripts/python.exe`. В коде и SKILL.md **запрещены** литералы `/home/tkachenkoav/...`.

Общий контракт импорта (все `scripts/*.py` и тесты):

```python
SCRIPTS_DIR = Path(__file__).resolve().parent          # для модулей в scripts/
# в tests/conftest.py:
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
```

Зависимости v1: stdlib + `openpyxl` (xlsx) + `PyYAML` (опц., для `--user-map` YAML; JSON работает без неё). HTTP для `OpenAICompatAdapter` — `urllib.request` stdlib или `openai` из venv Hermes. Новых pip-пакетов в системный Python не ставить без вопроса Саше; `openpyxl` ставить через `python3 -m pip` в venv Hermes, если отсутствует.

---

### 1. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/SKILL.md`

**Назначение.** Точка входа агента Hermes: триггеры («собери кейсы», «выгрузи темы за 3 дня», «case-collector»), как вызвать CLI, таблица параметров, запреты, формат отчёта в чат, предупреждение о латентности и бюджете. Не содержит полного split-промпта (он в `references/split-prompt.md`) и не содержит ФИО/реальные id (пример карты — `references/user-map.example.yaml`). Платформы: `linux, macos, windows`. Класс: on-demand analytical skill, как `loop-channel-digest`, не семейство `MoveFrom*`.

**Frontmatter (обязательные поля валидатора `hermes-agent-skill-authoring`):**

```yaml
---
name: case-collector
description: >-
  Use when: собери кейсы, выгрузи темы за N дней, case-collector,
  таблица пользователь × тема × период из логов сессий Hermes state.db.
  Read-only sqlite; LLM-split по смыслу; выход xlsx в Inbox.
version: 0.1.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [sessions, cases, xlsx, analytics, state-db]
    related_skills: [spreadsheet-deliverables]
---
```

`description` ≤ 1024 символов. Тело SKILL.md — короче 20 КБ: детали промпта/схемы БД не дублировать, дать ссылки на `references/` и «запусти CLI».

**Поведение агента (шаги с критерием завершения):**

1. Разобрать период из фразы Саши (`за 3 дня` → `--since` сегодня−3д, `--until` сегодня, таймзона `Europe/Moscow`). Если периода нет — спросить один раз, не выдумывать.
2. Если Саша не просил сразу «в бой» — сначала `--dry-run --limit 20`. Критерий: в чат ушёл инвентарь (числа), LLM не вызывался.
3. Собрать argv из таблицы параметров ниже. `--db` не подставлять хардкодом; дефолт CLI достаточен. `--user-map` — только если Саша дал файл; не коммитить карту.
4. Запустить интерпретатор venv (если есть) + `scripts/case_collector.py`. Не вызывать `agent -p`.
5. В чат вернуть **только** отчёт CLI (период, `--db`, сессии отобрано/пропущено/прогнано, кейсы, путь к xlsx или csv, usage, id `llm_error`). Таблицу целиком не ретранслировать. Сырой `content` сообщений не печатать.
6. Если отобранных > 200 и `--limit` нет — CLI сам предупредит; агент это пересказывает, прогон не запрещает. Дымовой прогон: `--limit 20`.
7. Латентность: предупредить, что ~150 последовательных вызовов × 5–15 с ≈ 15–40 мин (масштаб Windows-брифа; Linux-доказательство ≈ 24 сессии).

**Ключевые константы / запреты в тексте SKILL.md (не Python-константы):**

- Крон не ставить, `jobs.json` не трогать, ErrorBus не подключать.
- Jira / Confluence / Loop / `MoveFromJira` не вызывать.
- `state.db` не писать, не `VACUUM`, не checkpoint.
- Модель не выбирать «как в текущей сессии» и не подставлять Pro/reasoning-high по умолчанию.
- `PIIScan` не ослаблять: этому скиллу разрешено **читать** `state.db`, писать — нет.
- Не класть сырой диалог в Inbox / xlsx / логи.
- Windows-инстанс с Linux не трогать.

**Сигнатуры функций/классов:** нет (markdown).

**Тесты:** `tests/test_cli.py::test_skill_md_has_no_linux_abspath` — в `SKILL.md` нет подстроки `/home/tkachenkoav`. `test_skill_md_frontmatter` — есть `name: case-collector`, `platforms` содержит `windows`. Фикстура: чтение файла, без БД.

---

### 2. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/scripts/case_collector.py`

**Назначение.** Оркестратор прогона (ТЗ §4.6): argparse → отбор сессий → dry-run или LLM-split по сессии → identity → xlsx/csv → отчёт в stdout. Идемпотентность: каждый запуск перезаписывает `--output` (если путь — директория, писать timestamped файл). Watermark нет. Батч нескольких сессий в один LLM-вызов запрещён. Параллелизм — только `--concurrency` независимых сессий **после** того, как транскрипты уже вычитаны (чтобы не шарить sqlite-connection между потоками).

**Сигнатуры:**

```python
DEFAULT_EXCLUDE_SOURCES: tuple[str, ...] = ("cron", "kanban", "subagent")
DEFAULT_MAX_INPUT_CHARS: int = 12000
DEFAULT_CONCURRENCY: int = 1
MAX_CONCURRENCY: int = 3
DEFAULT_TZ_NAME: str = "Europe/Moscow"
VOLUME_WARN_THRESHOLD: int = 200
ENV_MODEL: str = "CASE_COLLECTOR_LLM_MODEL"

@dataclass
class RunConfig:
    since: datetime          # aware, Europe/Moscow unless --tz
    until: datetime          # полуинтервал [since, until)
    db_path: Path
    output: Path
    exclude_sources: list[str]
    include_sources: list[str] | None
    user_map_path: Path | None
    model: str
    llm_backend: str         # hermes | openai-compat | auto
    dry_run: bool
    limit: int | None
    max_input_chars: int
    include_assistant_stubs: bool
    concurrency: int
    tz_name: str
    prefer_origin_user_name: bool
    config_path: Path        # дефолт Path.home()/".hermes"/"config.yaml"

@dataclass
class RunStats:
    selected: int
    skipped: int
    llm_ran: int
    cases: int
    llm_error_ids: list[str]
    over_limit: int
    started_outside_count: int   # OQ-4, только счётчик
    usage_prompt_tokens: int
    usage_completion_tokens: int
    output_path: Path
    output_kind: str             # "xlsx" | "csv"
    warned_volume: bool

def parse_args(argv: list[str] | None = None) -> argparse.Namespace
    # реализует таблицу CLI ниже; --since/--until обязательны

def parse_window(raw: str, tz: ZoneInfo) -> datetime
    # ISO-8601; дата без времени = 00:00:00 в tz; naive → присвоить tz (не UTC)

def default_db_path() -> Path
    # Path.home() / ".hermes" / "state.db"  — единственная привязка к пути БД

def default_output_path(since: datetime, until: datetime) -> Path
    # Path.home() / "WorkVault" / "Inbox" / f"case-collector_{since:%Y-%m-%d}_{until:%Y-%m-%d}.xlsx"
    # Inbox как дефолт OQ-8, перекрывается --output; не единственно возможный путь

def default_config_path() -> Path
    # Path.home() / ".hermes" / "config.yaml"

def load_config_default_model(config_path: Path) -> str | None
    # читает YAML ключ model.default; файла нет / ключа нет → None
    # не читает и не копирует api_key

def resolve_model(cli_model: str | None, config_path: Path) -> str
    # 1) --model  2) env CASE_COLLECTOR_LLM_MODEL  3) model.default
    # иначе SystemExit с текстом «модель не задана» и кодом 2
    # в исходниках нет литерала slug модели

def build_config(ns: argparse.Namespace) -> RunConfig
    # concurrency > 3 → обрезать до 3 либо exit 2 (рекомендация: exit 2, fail-loud)
    # output если директория → stem timestamped внутри неё

def format_chat_report(cfg: RunConfig, stats: RunStats) -> str
    # период, --db, отобрано/пропущено/прогнано, кейсы, путь, usage, llm_error id
    # без тел сообщений и без полной таблицы

def process_one_session(
    session: SessionRow,
    messages: list[MessageRow],
    *,
    adapter: LlmAdapter | None,
    model: str,
    user_map: UserMap,
    cfg: RunConfig,
) -> tuple[list[CaseRow], SessionInventoryRow]
    # транскрипт → split (или skip) → identity → CaseRow
    # adapter is None только в dry-run (тогда LLM-ветка не вызывается)

def run(cfg: RunConfig) -> RunStats
    # 1 connect_ro  2 select_sessions  3 OQ-4 count
    # 4 warn if selected>200 and limit is None
    # 5 dry-run → инвентарь + write_workbook без листа кейсов или с пустым
    # 6 иначе: для каждой сессии fetch_messages (последовательно)
    #    затем split: concurrency=1 цикл; >1 ThreadPoolExecutor только на complete()
    # 7 write_workbook / csv fallback
    # 8 print format_chat_report
    # llm_error одной сессии НЕ поднимает исключение на весь прогон

def main(argv: list[str] | None = None) -> int
    # DbNotFoundError / SchemaMismatchError / ModelNotSetError → stderr + ненулевой код
    # --db к несуществующему файлу: код 2, без записи output
```

**CLI-аргументы (канон для argparse и SKILL.md):**

| Аргумент | Default | Обязателен | Требование ТЗ |
|---|---|---|---|
| `--since` | нет | да | ISO-8601, tz default `Europe/Moscow` |
| `--until` | нет | да | полуинтервал `[since, until)` |
| `--tz` | `Europe/Moscow` | нет | OQ-12; вывод всегда с оффсетом этой зоны (`+03:00` для Москвы), не TZ хоста |
| `--db` | `Path.home()/".hermes"/"state.db"` | нет, но флаг обязателен к наличию | единственная привязка к пути БД |
| `--output` | `~/WorkVault/Inbox/case-collector_<since>_<until>.xlsx` | нет | OQ-8 |
| `--exclude-sources` | `cron,kanban,subagent` | нет | CSV; дефолт служебных |
| `--include-sources` | нет | нет | белый список; пересечение с exclude |
| `--user-map` | нет | нет | YAML/JSON; не коммитить боевую карту |
| `--model` | нет | нет | первый приоритет резолва модели |
| `--llm-backend` | `auto` | нет | `hermes` \| `openai-compat` \| `auto` |
| `--dry-run` | выкл | нет | инвентарь без LLM |
| `--limit` | нет | нет | потолок сессий; без флага — все отобранные |
| `--max-input-chars` | `12000` | нет | порог чанков |
| `--include-assistant-stubs` | выкл | нет | assistant ≤200, без tool JSON |
| `--concurrency` | `1` | нет | верх 3 |
| `--prefer-origin-user-name` | выкл | нет | OQ-2, для Windows |
| `--config` | `Path.home()/".hermes"/"config.yaml"` | нет | откуда читать `model.default` |

Не делать флагов: `--profile` (OQ-13), `--jira`, `--cron`, `--watermark`, `--merge-across-sessions`.

**Exit codes:** `0` успех (в т.ч. нуль кейсов при валидном прогоне); `2` ошибка входа (нет БД, нет модели, нет адаптера, битое окно дат, concurrency вне диапазона); `1` неожиданное исключение. Битый JSON одной сессии → не `1`, а строка инвентаря `llm_error`.

**Поток `run()` (канон §4.6, развёрнутый):**

1. `connect_ro(cfg.db_path)` → `assert_required_schema`.
2. `select_sessions(...)`. Если `--limit` задан — обрезать **после** фильтров (статус оставшихся в выборке, но сверх лимита, в инвентарь не писать; либо писать `over_limit` только счётчиком в отчёте — рекомендация: счётчик в `RunStats.over_limit`, в лист «Сессии» не тащить необработанные, чтобы не путать с `skipped_empty`).
3. `count_sessions_with_messages_in_window_started_outside` — напечатать в отчёте, в выборку не добавлять (OQ-4).
4. Если `len(selected) > 200` и `limit is None` — warning в stderr, прогон продолжить.
5. `--dry-run`: для каждой сессии посчитать `user_msgs`/`user_chars` через транскрипт **без** LLM; status `ok` если есть user-turns, иначе `skipped_empty`; записать только лист «Сессии»; `adapter` не создавать (критерий успеха 9).
6. Боевой: `resolve_backend` + `resolve_model`; fail-loud если адаптер не сконфигурирован.
7. Последовательно `fetch_messages` на каждую сессию (свой SQL SELECT). Потом split: при `concurrency==1` — цикл; иначе пул только вокруг `split_session` уже собранных транскриптов.
8. `write_deliverable` → xlsx или csv.
9. Печать отчёта.

**Тесты (`tests/test_cli.py`):**

| Тест | Что проверяет | Fixture |
|---|---|---|
| `test_help_exit_0` | `--help` код 0, есть `--db`, `--dry-run`, `--since` | нет БД |
| `test_missing_since_until` | без дат → код 2 | нет БД |
| `test_db_not_found` | `--db` к несуществующему пути → код 2, output не создан | `tmp_path` |
| `test_model_unresolved` | нет `--model`, нет env, пустой config → код 2 «модель не задана» | `tmp_path` config без `model.default` |
| `test_model_cli_overrides_env_and_config` | приоритет 1/2/3 | monkeypatch env |
| `test_dry_run_does_not_call_llm` | Fake adapter `calls==0` при `--dry-run` | `fixture_db` |
| `test_no_hardcoded_model_slug_in_scripts` | grep `scripts/*.py` на `deepseek/` отсутствует | файлы исходников |
| `test_no_home_tkachenkoav_in_scripts` | нет `/home/tkachenkoav` | файлы исходников |
| `test_exclude_cron_kanban_subagent` | основной лист без этих source | `fixture_db` |
| `test_llm_error_does_not_abort` | одна сессия битый JSON → остальные кейсы есть, код 0 | Fake adapter |
| `test_volume_warn` | 201 сессия без `--limit` → warning в stderr, прогон идёт | маленькая генерация в tmp db |

Живой `~/.hermes/state.db` в этих тестах не указывать и не открывать.

---

### 3. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/scripts/db.py`

**Назначение.** Единственный слой доступа к SQLite (ТЗ §2.1–2.4, §5, OQ-3, OQ-4). Читает **только** таблицы `sessions` и `messages`. Не читает `messages_fts*`, `session_model_usage`, `gateway_routing`, `system_prompts`. FTS не использовать. Отбор окна — по `sessions.started_at`, не полным сканом. Клиент — Python `sqlite3`, не бинарь `sqlite3`. Паттерн read-only **скопировать идеей** у `DialogBacklog/backlog_fetch.py`, модуль **не** импортировать: `backlog_fetch.py` открывает БД **без** `mode=ro` и для другого продукта.

**Сигнатуры:**

```python
CONNECT_TIMEOUT_SEC: float = 30.0
REQUIRED_SESSION_COLS: tuple[str, ...] = ("id", "source", "started_at")
REQUIRED_MESSAGE_COLS: tuple[str, ...] = ("id", "session_id", "role", "content", "timestamp")
OPTIONAL_SESSION_COLS: tuple[str, ...] = (
    "user_id", "model", "parent_session_id", "ended_at", "end_reason",
    "message_count", "title", "session_key", "chat_id", "chat_type",
    "thread_id", "display_name", "origin_json", "profile_name",
    "last_activity_at", "archived",
)
OPTIONAL_MESSAGE_COLS: tuple[str, ...] = (
    "tool_name", "token_count", "active", "compacted",
)
WRITE_SQL_HEADS: tuple[str, ...] = (
    "insert", "update", "delete", "replace", "drop", "alter", "create",
    "vacuum", "reindex", "attach", "detach", "pragma wal_", "pragma journal_",
)

class DbError(Exception): ...
class DbNotFoundError(DbError): ...
class SchemaMismatchError(DbError): ...
class WriteAttemptError(DbError): ...

@dataclass
class SessionRow:
    id: str
    source: str
    started_at: float
    user_id: str | None = None
    title: str | None = None
    session_key: str | None = None
    chat_id: str | None = None
    chat_type: str | None = None
    thread_id: str | None = None
    display_name: str | None = None
    origin_json: str | None = None
    profile_name: str | None = None
    message_count: int | None = None
    archived: int | None = None
    extra: dict[str, object] = field(default_factory=dict)
    # extra — неизвестные optional, которые есть в этой БД; не выдумывать имена Mattermost

@dataclass
class MessageRow:
    id: int
    session_id: str
    role: str
    content: str | None
    timestamp: float
    tool_name: str | None = None
    token_count: int | None = None
    active: int | None = None
    compacted: int | None = None

def sqlite_uri(path: Path) -> str
    # POSIX: file:{resolve.as_posix()}?mode=ro
    # Windows: file:{resolve.as_posix()}?mode=ro  (C:/...)
    # ЗАПРЕЩЕНО: immutable=1
    # ЗАПРЕЩЕНО: литерал /home/...

def connect_ro(path: Path, timeout: float = CONNECT_TIMEOUT_SEC) -> sqlite3.Connection
    # path.exists() иначе DbNotFoundError
    # sqlite3.connect(uri, uri=True, timeout=timeout)
    # PRAGMA query_only=ON через execute_ro
    # row_factory = sqlite3.Row
    # check_same_thread=True (LLM-параллелизм — без шаринга conn)

def execute_ro(conn: sqlite3.Connection, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor
    # единственная точка SQL
    # разрешены: SELECT *; PRAGMA query_only=ON; PRAGMA table_info(sessions|messages)
    # всё остальное → WriteAttemptError (в т.ч. wal_checkpoint, VACUUM, INSERT)
    # реализация: lstrip + lower; head check; не «чёрный список после факта»

def table_columns(conn: sqlite3.Connection, table: str) -> list[str]
    # PRAGMA table_info; table только из белого списка sessions|messages

def assert_required_schema(conn: sqlite3.Connection) -> None
    # нет таблиц sessions/messages ИЛИ нет REQUIRED_* → SchemaMismatchError
    # понятный текст: каких колонок не хватает (OQ-3 fail-loud на обязательных)

def present_optional_columns(conn: sqlite3.Connection, table: str, candidates: tuple[str, ...]) -> list[str]
    # пересечение; отсутствующие optional тихо пропускать (OQ-3 degrade)

def select_sessions(
    conn: sqlite3.Connection,
    *,
    since_epoch: float,
    until_epoch: float,
    exclude_sources: Sequence[str],
    include_sources: Sequence[str] | None,
    limit: int | None,
) -> list[SessionRow]
    # WHERE started_at >= since AND started_at < until
    # AND (archived IS NULL OR archived != 1) если колонка archived есть; если колонки нет — не фильтровать по ней
    # source NOT IN exclude; если include задан — source IN include (пересечение: include минус exclude)
    # EXISTS живое user-сообщение: role='user' AND TRIM(content)<>'' AND content IS NOT NULL
    #   и (active=1 OR колонки active нет) — сессии без такого user отсекаются здесь
    # ORDER BY started_at ASC
    # SELECT явный список колонок (required + present optional), не SELECT *
    # limit применяется в Python после выборки ИЛИ LIMIT ? — допустимо LIMIT в SQL, params
    # профиль profile_name в v1 не фильтровать (OQ-13)

def count_sessions_with_activity_in_window_started_outside(
    conn: sqlite3.Connection,
    *,
    since_epoch: float,
    until_epoch: float,
    exclude_sources: Sequence[str],
    include_sources: Sequence[str] | None,
) -> int
    # OQ-4: started_at NOT IN [since, until) AND EXISTS message.timestamp IN [since, until)
    # только COUNT; не возвращать эти сессии в select_sessions

def fetch_messages(conn: sqlite3.Connection, session_id: str) -> list[MessageRow]
    # WHERE session_id=? ORDER BY timestamp ASC, id ASC
    # явный список колонок; optional degrade
    # не фильтровать роли на этом слое — фильтр в transcript.py
    # не использовать FTS
```

**Ключевые константы:** `CONNECT_TIMEOUT_SEC=30.0`; белый список таблиц; `WRITE_SQL_HEADS`. Индексы `idx_sessions_started` / `idx_messages_session_id` на живой БД есть — SQL должен быть SARGable по `started_at` (`WHERE started_at >= ? AND started_at < ?`), не `WHERE datetime(started_at)`.

**Жёсткие фильтры сессий (не параметры CLI):**

- `archived = 1` исключить, если колонка есть;
- нет ни одного user-сообщения с непустым `content` и живым `active` (если колонка есть — `active=1`; если нет — считать живым);
- `profile_name` не фильтровать.

**Тесты (`tests/test_db.py`):**

| Тест | Критерий | Fixture |
|---|---|---|
| `test_connect_ro_uri_mode` | URI содержит `mode=ro` и **не** содержит `immutable` | monkeypatch `sqlite3.connect` |
| `test_query_only_pragma` | после connect выполнен `PRAGMA query_only=ON` | `fixture_db` + перехват `execute_ro` |
| `test_execute_ro_rejects_insert` | `INSERT INTO sessions` → `WriteAttemptError` | `fixture_db` |
| `test_execute_ro_rejects_wal_checkpoint` | `PRAGMA wal_checkpoint` → `WriteAttemptError` | `fixture_db` |
| `test_no_write_mtime` | SELECT-прогон не меняет `mtime`/`size` fixture-файла | `fixture_db` + `stat()` до/после |
| `test_missing_file` | нет файла → `DbNotFoundError` | `tmp_path` |
| `test_missing_required_column` | нет `started_at` → `SchemaMismatchError` | `tmp_path` калечная схема |
| `test_optional_column_degrade` | нет `thread_id` — сессии читаются, `thread_id is None` | `fixture_db_minimal_cols` |
| `test_window_by_started_at` | сессия вне окна не попадает | `fixture_db` |
| `test_exclude_sources` | cron/kanban/subagent отсутствуют | `fixture_db` |
| `test_include_sources_intersection` | include=telegram,cli + exclude=cli → только telegram | `fixture_db` |
| `test_archived_excluded` | `archived=1` нет в результате | `fixture_db` |
| `test_no_user_message_excluded` | только tool-роли — сессии нет | `fixture_db` |
| `test_oq4_counter` | сессия started_at вне окна, message внутри — в select нет, счётчик ≥ 1 | `fixture_db` |
| `test_no_fts_in_sql` | исходник `db.py` не содержит `messages_fts` | grep файла |
| `test_timeout_default` | `connect` вызван с `timeout>=30` | monkeypatch |

**Запрет:** тесты не принимают путь `Path.home()/".hermes"/"state.db"` и не читают его «для сравнения».

---

### 4. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/scripts/transcript.py`

**Назначение.** Компакт-транскрипт сессии для LLM (ТЗ §4.2, §4.5, OQ-5): упорядоченные **user**-реплики, вырезание шума, опциональные assistant stubs, оценка токенов без tokenizer, нарезка чанков по user-репликам (не по байтам середины сообщения). Tool-роли в промпт запрещены на этом слое — даже если `fetch_messages` их вернул.

**Сигнатуры:**

```python
NOISE_PREFIXES: tuple[str, ...] = (
    "[IMPORTANT: Background process",   # conversation-handoff
)
ASSISTANT_STUB_MAX: int = 200
DEFAULT_CHUNK_CHARS: int = 8000
DEFAULT_OVERLAP_TURNS: int = 2
CHARS_PER_TOKEN: float = 2.5            # смесь RU/EN, консервативно; tokenizer не вызывать

@dataclass(frozen=True)
class Turn:
    id: int
    ts_iso: str                         # ISO-8601 с оффсетом --tz
    role: str                           # "user" или "assistant" (stub)
    text: str

@dataclass(frozen=True)
class Chunk:
    index: int                          # 0-based i
    total: int                          # n
    overlap_ids: tuple[int, ...]
    turns: tuple[Turn, ...]
    char_count: int                     # сумма len(user text) в чанке (для порога)

def is_live_user(msg: MessageRow) -> bool
    # role=='user'
    # content nonempty after strip
    # active is None or ==1          # колонки может не быть
    # compacted is None or ==0       # OQ-5: compacted=1 не подавать
    # role not in ('tool','session_meta') — и так отсекается role==user

def is_noise(text: str) -> bool
    # whitespace-only → True
    # startswith любой NOISE_PREFIXES → True

def strip_noise(text: str) -> str | None
    # None = выкинуть реплику

def next_assistant_stub(messages: Sequence[MessageRow], after_index: int) -> str | None
    # ближайший subsequent role=='assistant', active живой, compacted!=1
    # обрезать до 200 символов; выкинуть, если похоже на tool JSON (strip starts with '{' и '"tool' / '"name"')
    # tool role пропускать, не становиться stub

def ts_to_iso(ts: float, tz: ZoneInfo) -> str
    # datetime.fromtimestamp(ts, tz=tz).isoformat() — для Москвы будет +03:00
    # не использовать timezone.utc как вывод

def build_compact_transcript(
    messages: Sequence[MessageRow],
    *,
    tz: ZoneInfo,
    include_assistant_stubs: bool = False,
) -> list[Turn]
    # сортировка не нужна, если fetch уже ORDER BY; стабильно по (timestamp, id)
    # для каждого live user: Turn user; опц. Turn assistant stub сразу после
    # пустой список, если всех вырезали (→ skipped_empty / no_task)

def estimate_tokens(text: str) -> int
    # ceil(len(text) / 2.5); не вызывать tiktoken/transformers
    # token_count из БД игнорировать даже если не NULL (на Linux часто NULL; единый метод)

def user_char_count(turns: Sequence[Turn]) -> int
    # сумма len(text) только role==user

def chunk_turns(
    turns: Sequence[Turn],
    *,
    max_input_chars: int = 12000,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_n: int = DEFAULT_OVERLAP_TURNS,
) -> list[Chunk]
    # если user_char_count(turns) <= max_input_chars → один Chunk(i=0,n=1,overlap_ids=())
    # иначе резать по границам user-реплик, набор user-текста ≈ chunk_chars
    # assistant stubs следуют за своей user-репликой и не режутся отдельно
    # overlap = последние overlap_n **user**-реплики предыдущего чанка (со своими stubs)
    # overlap_ids = id этих user-реплик
    # чанк не начинает и не заканчивает посередине text
    # n = число чанков после нарезки; index 0..n-1
```

**Что не входит:** вызов LLM, валидация JSON, запись xlsx, чтение sqlite.

**Тесты (`tests/test_transcript.py`):**

| Тест | Критерий | Fixture |
|---|---|---|
| `test_drops_tool_and_session_meta` | в turns нет tool/session_meta | `sample_messages` |
| `test_drops_inactive_and_compacted` | `active=0`, `compacted=1` отсутствуют | `sample_messages` |
| `test_drops_noise_and_whitespace` | `[IMPORTANT: Background process...` вырезан | `sample_messages` |
| `test_stubs_off_by_default` | нет role=assistant | `sample_messages` |
| `test_stubs_truncated_200` | stub ≤ 200, без `{`-tool JSON | `sample_messages` |
| `test_empty_after_filter` | [] → дальше skipped | только tool msgs |
| `test_estimate_tokens_no_tokenizer` | `len/2.5`; модуль не импортирует tiktoken | grep |
| `test_single_chunk_under_limit` | 1000 символов, max=12000 → n=1 | синтетика |
| `test_chunk_by_user_not_mid_message` | ни один Turn.text не разрезан | длинная сессия |
| `test_chunk_overlap_two_user_ids` | `overlap_ids` чанка i+1 = последние 2 user id чанка i | длинная сессия |
| `test_ts_iso_moscow` | `--tz Europe/Moscow` → строка содержит `+03:00` | фиксированный epoch |

---

### 5. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/scripts/split_llm.py`

**Назначение.** Семантическое разбиение одной сессии (ТЗ §4.1, §4.3–4.5, §8.3): промпт, JSON-контракт `schema_version=1.0`, абстракция `complete()`, фейковый и боевые адаптеры, валидация, один retry на чанк, склейка чанков **без** второго merge-LLM (OQ-10), канонические timestamps скриптом. Категорически без `agent -p`, без Cursor CLI, без `subprocess` на `agent`.

**Сигнатуры:**

```python
SCHEMA_VERSION: str = "1.0"
CONFIDENCE_ALLOWED: frozenset[str] = frozenset({"high", "medium", "low"})
JSON_RETRY_ATTEMPTS: int = 1          # ровно один повтор; итого максимум 2 complete() на чанк
DEFAULT_COMPLETE_TIMEOUT: float = 180.0
DEFAULT_MAX_TOKENS: int = 2048
ENV_BASE_URL: str = "CASE_COLLECTOR_LLM_BASE_URL"
ENV_API_KEY: str = "CASE_COLLECTOR_LLM_API_KEY"

@dataclass
class LlmUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_usd: float | None = None

@dataclass
class LlmResult:
    text: str
    usage: LlmUsage | None = None

class LlmAdapter(Protocol):
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        timeout: float,
        max_tokens: int,
    ) -> LlmResult: ...
    # model — атрибут экземпляра, не константа класса и не дефолт в сигнатуре complete

@dataclass
class CaseDraft:
    topic: str
    start_msg_id: int
    end_msg_id: int
    confidence: str                    # high|medium|low
    flags: list[str] = field(default_factory=list)

@dataclass
class SplitResult:
    session_id: str
    cases: list[CaseDraft]
    status: str                        # ok | skipped_empty | no_task | llm_error
    usage: LlmUsage
    raw_error: str | None = None

def load_split_prompt(path: Path | None = None) -> str
    # default: рядом с skill / references/split-prompt.md
    # Path(__file__).resolve().parents[1] / "references" / "split-prompt.md"
    # не хардкодить /home/...

def strip_fences(text: str) -> str
    # снять ``` / ```json обёртку; strip

def build_payload(
    session_id: str,
    timezone_name: str,
    turns: Sequence[Turn],
    chunk: Chunk | None = None,
) -> dict
    # {
    #   "session_id": ...,
    #   "timezone": "Europe/Moscow",
    #   "turns": [{"id","ts","role","text"}, ...],
    #   опц. "chunk": {"i": chunk.index, "n": chunk.total, "overlap_ids": [...]}
    # }
    # в turns не должно быть role=tool

def build_messages(system_prompt: str, payload: dict, *, retry_hint: bool = False) -> list[dict[str, str]]
    # [{"role":"system","content": system_prompt [+ retry hint]},
    #  {"role":"user","content": json.dumps(payload, ensure_ascii=False)}]
    # retry_hint = «верни только JSON по схеме, без markdown-ограды»

def parse_and_validate(
    raw_text: str,
    *,
    session_id: str,
    allowed_ids: set[int],
) -> list[CaseDraft]
    # json.loads(strip_fences)
    # schema_version == "1.0" (иначе ValidationError → caller ретраит)
    # session_id совпал
    # cases — list
    # topic nonempty, len<=200; иначе эта case-строка отбрасывается
    # start_msg_id/end_msg_id ∈ allowed_ids и start<=end; иначе отброс case
    # confidence не из множества → "medium" (не fail)
    # ISO-поля LLM (start/end datetime) игнорировать, даже если пришли
    # пустой cases → валидный результат []  (no_task)

def normalize_topic(topic: str) -> str
    # casefold + схлопнуть whitespace; для merge чанков, не для записи в xlsx
    # в таблицу пишется исходный topic первой половины (или более длинный — зафиксировать: первой)

def mark_overlaps(cases: list[CaseDraft]) -> list[CaseDraft]
    # интервалы [start_msg_id, end_msg_id] по id (не по времени)
    # пересечение закрытых интервалов → обе строки остаются, flags += "overlap"
    # не удалять молча

def merge_chunk_cases(per_chunk: list[list[CaseDraft]]) -> list[CaseDraft]
    # OQ-10: без второго LLM
    # конкатенация по порядку чанков
    # если normalize_topic(последний чанка i) == normalize_topic(первый чанка i+1)
    #   → слить: start=min, end=max, topic=первого, confidence=худший из пары
    #     (high>medium>low; худший = min), flags += "chunked"
    # overlap_ids не делают автослияние сами по себе

def compute_bounds(
    turns: Sequence[Turn],
    start_msg_id: int,
    end_msg_id: int,
) -> tuple[str, str]
    # ТОЛЬКО user-turns с id в [start, end]
    # min/max по исходному timestamp → уже лежащему в Turn.ts_iso
    # если в диапазоне нет user (не должно после validate) → ValueError
    # LLM datetime не используется

def split_session(
    adapter: LlmAdapter,
    *,
    session_id: str,
    turns: Sequence[Turn],
    tz_name: str,
    max_input_chars: int,
    timeout: float = DEFAULT_COMPLETE_TIMEOUT,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> SplitResult
    # turns пустой → status skipped_empty, complete не вызывать
    # chunk_turns → для каждого чанка complete (1 retry при ValidationError/JSONDecodeError)
    # после двух отказов чанка: SplitResult(status=llm_error) для **сессии**
    #   (не продолжать остальные чанки этой сессии; соседние сессии — дело оркестратора)
    # успешные чанки → merge_chunk_cases → mark_overlaps
    # cases пустой после успеха → status no_task (лист кейсов без строки; инвентарь no_task)
    # usage суммировать по вызовам

# --- адаптеры ---

class FakeLlmAdapter:
    def __init__(self, mapping: dict[str, str] | Callable[..., str], *, fail_first: bool = False): ...
    def complete(self, messages, *, timeout, max_tokens) -> LlmResult
    # mapping[session_id] → JSON-строка; или callable(payload) -> text
    # fail_first: первый вызов — битый текст, второй — валидный (тест retry)
    # calls: int счётчик; тесты dry-run проверяют calls==0
    # НЕ ходит в сеть

class HermesCallLlmAdapter:
    def __init__(self, model: str, hermes_root: Path | None = None): ...
    # hermes_root default Path.home()/"hermes-agent" — без /home/tkachenkoav
    # ленивый sys.path + `from agent.auxiliary_client import call_llm`
    # complete: call_llm(task="case_collector", model=self.model, messages=..., timeout=..., max_tokens=..., tools=None)
    # брать ТОЛЬКО response.choices[0].message.content; не reasoning_details
    # пустой content → RuntimeError (caller ретраит как битый JSON / llm_error)
    # ключ/base_url в код не копировать — call_llm читает config сам
    # если import падает — понятная ошибка «hermes backend unavailable»

class OpenAICompatAdapter:
    def __init__(self, model: str, base_url: str, api_key: str): ...
    def complete(...) -> LlmResult
    # POST {base_url}/chat/completions JSON {model, messages, max_tokens}
    # Authorization: Bearer api_key
    # ключ не логировать, не писать в xlsx
    # usage из response.usage если есть

def load_openai_compat_from_env_or_config(
    model: str,
    config_path: Path,
) -> OpenAICompatAdapter
    # base_url: env CASE_COLLECTOR_LLM_BASE_URL иначе custom_providers[provider].base_url
    # api_key: env CASE_COLLECTOR_LLM_API_KEY иначе custom_providers[provider].api_key
    # provider имя: model.provider из config.yaml (на Linux сейчас tutu) — не хардкодить "tutu" как единственный
    # нет url/ключа → fail-loud, не молча ходить на api.openai.com

def resolve_backend(
    name: str,                     # hermes | openai-compat | auto
    *,
    model: str,
    config_path: Path,
) -> LlmAdapter
    # hermes → HermesCallLlmAdapter; import fail → ошибка (не тихо падать в openai)
    # openai-compat → load_openai_compat_from_env_or_config
    # auto: попробовать import call_llm → hermes; иначе openai-compat если env/config дают url+key;
    #       иначе SystemExit «адаптер не сконфигурирован»
```

**Контракт ответа LLM (встроить в промпт и в валидатор; не «см. ТЗ»):**

```json
{
  "schema_version": "1.0",
  "session_id": "<id>",
  "cases": [
    {
      "topic": "настройка доступов к протоколам встреч",
      "start_msg_id": 123,
      "end_msg_id": 140,
      "confidence": "high"
    }
  ]
}
```

Тема: по-русски, 5–15 слов, без транслита, без кавычек-обёрток, без «пользователь просит…». Границы — id из входа, не выдуманные даты. Нет рабочей задачи — `"cases": []`. Кросс-сессионное слияние тем **запрещено** (OQ-6): этот модуль видит одну `session_id`.

**Запреты в коде модуля (проверяются тестом grep):**

- нет `subprocess` с `agent`;
- нет импорта `cursor`;
- нет литерала `deepseek/deepseek-v4-flash-0731`;
- нет `/home/tkachenkoav`;
- нет вызова Jira / Loop / Exchange и нет записи в `jobs.json` (критерий 8; `test_no_jira_loop_exchange_jobsjson_in_scripts`).

**Тесты (`tests/test_split_llm.py`):**

| Тест | Критерий | Fixture |
|---|---|---|
| `test_parse_valid_json` | schema 1.0 → CaseDraft | строка JSON |
| `test_strip_fences` | ````json ...```` парсится | — |
| `test_session_id_mismatch_raises` | retry path | Fake fail |
| `test_invented_msg_id_dropped_or_retry` | id не из turns | Fake |
| `test_confidence_coerced` | `"maybe"` → `medium` | — |
| `test_ignore_llm_iso_dates` | поле `"start": "2020-01-01"` не влияет на bounds | turns с реальными ts |
| `test_compute_bounds_min_max_user` | начало=min ts, конец=max ts user в диапазоне | фиксированные turns |
| `test_retry_once_then_ok` | `fail_first=True` → `calls==2`, status ok | Fake |
| `test_retry_exhausted_llm_error` | два битых JSON → `llm_error` | Fake |
| `test_empty_cases_no_task` | `"cases":[]` → status `no_task`, complete был | Fake |
| `test_overlap_flag` | два интервала 1–5 и 4–8 → обе строки, `overlap` | Fake |
| `test_chunk_merge_same_topic` | два чанка одна тема после normalize → одна case, `chunked` | синтетика |
| `test_chunk_no_merge_different_topic` | темы разные → две строки | — |
| `test_no_second_merge_llm` | merge_chunk_cases не вызывает adapter | Fake.calls неизменен |
| `test_fake_no_network` | complete не открывает socket | Fake |
| `test_auto_fail_loud_without_backend` | monkeypatch import fail + нет env → SystemExit | — |
| `test_tools_never_in_payload` | build_payload не имеет role=tool | turns только user |
| `test_no_jira_loop_exchange_jobsjson_in_scripts` | grep `scripts/*.py` на паттерны `jira` / `Loop` / `Exchange` / `jobs.json` (внешние вызовы/записи) — ничего не найдено (критерий 8) | файлы исходников |

Мульти-кейс (OQ-15): fixture-диалог с двумя предметами в `FakeLlmAdapter` + `test_two_cases_in_one_session`. Успех v1 на живом Linux **не** требует найти multi-case в `state.db`; тест обязан это закрыть.

---

### 6. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/scripts/identity.py`

**Назначение.** Колонка «пользователь» (ТЗ §2.5, §6, OQ-2, OQ-3): карта `--user-map`, порядок ключей, fallback без выдумывания ФИО. На Linux-доказательстве `sessions.user_id` / `origin_json.user_name` / `display_name` **не** дефолт (один аккаунт / имя воркспейса схлопнет таблицу). Стабильный ключ идентичности v1: `session_key` если есть, иначе `source + chat_id + thread_id`. Тонкий `IdentityAdapter` — точка Windows-адаптации имён колонок, не отдельный скилл.

**Сигнатуры:**

```python
@dataclass(frozen=True)
class UserMap:
    by_session_key: dict[str, str]
    by_source_chat_thread: dict[str, str]     # ключ f"{source}:{chat_id}:{thread_id}"
    by_thread_id: dict[str, str]
    by_user_id: dict[str, str]
    # первый матч побеждает; порядок проверки фиксирован

class IdentityAdapter(Protocol):
    def session_key(self, row: SessionRow) -> str | None: ...
    def source(self, row: SessionRow) -> str: ...
    def chat_id(self, row: SessionRow) -> str | None: ...
    def thread_id(self, row: SessionRow) -> str | None: ...
    def user_id(self, row: SessionRow) -> str | None: ...
    def origin(self, row: SessionRow) -> dict: ...
    def chat_topic(self, row: SessionRow) -> str | None: ...
    def origin_user_name(self, row: SessionRow) -> str | None: ...

class DefaultIdentityAdapter:
    # читает одноимённые поля SessionRow; origin_json.loads при валидном JSON, иначе {}
    # OriginDecodeError не роняет прогон: origin = {}
    # неизвестные Mattermost-имена колонок не угадывать; Windows-агент подменит адаптер

def load_user_map(path: Path) -> UserMap
    # .json → json.load
    # .yaml/.yml → yaml.safe_load; нет PyYAML → ошибка «поставь PyYAML или дай JSON»
    # формат: mapping ключ→имя ИЛИ список {keys: [...], name: ...} — рекомендация: плоский dict
    # ключи вида:
    #   "agent:main:telegram:group:CHAT:THREAD"     → session_key
    #   "telegram:CHAT:THREAD"                      → source:chat_id:thread_id
    #   "THREAD"                                    → thread_id (использовать осторожно)
    #   "USERID"                                    → user_id
    # эвристика классификации ключа:
    #   если ключ содержит ≥2 двоеточия и начинается с source-подобного → source:chat:thread
    #   если ключ содержит "agent:" или ≥4 двоеточия → session_key
    #   иначе если ключ совпадает с известным user_id-паттерном — user_id
    #   иначе thread_id
    #   ПЛАН реализации проще и детерминированнее: в example.yaml три секции:
    #     session_key: {..}
    #     source_chat_thread: {..}
    #     thread_id: {..}
    #     user_id: {..}
    #   Исполнитель делает секционный формат (явный). Плоский dict — fallback: все ключи как session_key если ':'≥3, иначе thread_id.
    # боевой файл с ФИО в репозиторий скилла НЕ копировать

def source_chat_thread_key(source: str, chat_id: str | None, thread_id: str | None) -> str
    # f"{source}:{chat_id or ''}:{thread_id or ''}"

def resolve_display_name(
    row: SessionRow,
    user_map: UserMap | None,
    *,
    adapter: IdentityAdapter | None = None,
    prefer_origin_user_name: bool = False,
) -> str
    # adapter = adapter or DefaultIdentityAdapter()
    # 1) user_map.by_session_key[session_key]
    # 2) user_map.by_source_chat_thread[source:chat:thread]
    # 3) user_map.by_thread_id[thread_id]  — только если thread_id уникален в ВЫБОРКЕ?
    #    ТЗ: «если уникален в выборке». Для v1 модуля identity: матч по ключу всегда;
    #    уникальность обеспечивает автор карты. Не делать второй pass по всей выборке в v1
    #    (осложняет API). Зафиксировать: thread_id матчится всегда, если ключ есть в карте.
    # 4) user_map.by_user_id[user_id]
    # 5) если prefer_origin_user_name и origin.user_name nonempty → его (OQ-2 Windows)
    # 6) chat_topic из origin_json nonempty → его
    # 7) суррогат source:chat_id:thread_id
    # НЕ возвращать display_name чата и origin.user_name на шаге 6/7 без флага
    # НЕ хардкодить 400307920, -1004300127777, "Alex Tkachenko"
```

**Тесты (`tests/test_identity.py`):**

| Тест | Критерий | Fixture |
|---|---|---|
| `test_map_session_key_wins` | ключ 1 бьёт остальные | example-подобная карта |
| `test_map_source_chat_thread` | шаг 2 | — |
| `test_map_thread_id` | шаг 3 | — |
| `test_map_user_id` | шаг 4 | — |
| `test_fallback_chat_topic` | origin.chat_topic, карты нет | origin_json |
| `test_fallback_surrogate` | `telegram:chatA:t1` | без topic |
| `test_not_linux_user_name_by_default` | origin.user_name=`Alex Tkachenko` **не** берётся без флага | — |
| `test_prefer_origin_user_name` | флаг on → берётся user_name | — |
| `test_display_name_not_default` | `display_name` воркспейса игнорируется | — |
| `test_bad_origin_json` | битый JSON → суррогат, не exception | — |
| `test_example_yaml_loads` | `references/user-map.example.yaml` парсится, без реальных id | файл example |
| `test_no_real_linux_ids_in_example` | example не содержит `-1004300127777`, `400307920` | grep |

---

### 7. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/scripts/xlsx_out.py`

**Назначение.** Выходной артефакт для Саши (ТЗ §3, `spreadsheet-deliverables`, OQ-7, OQ-8, OQ-14): основной `.xlsx` через `openpyxl`; fallback `.csv` с `;` и `utf-8-sig`, если `openpyxl` нет или запись xlsx упала. Два листа: «Кейсы» и «Сессии». Тела сообщений, tool_calls, system prompt **не** писать. Пустых колонок «Jira» / «вердикт» не добавлять. Кириллица как есть, без транслита. Каждое поле — своя колонка.

**Сигнатуры:**

```python
SHEET_CASES: str = "Кейсы"
SHEET_SESSIONS: str = "Сессии"
CSV_DELIMITER: str = ";"
CSV_ENCODING: str = "utf-8-sig"        # UTF-8 с BOM
HEADER_FILL_HEX: str = "D9E2F3"        # светлая заливка
MIN_COL_WIDTH: float = 10.0
MAX_COL_WIDTH: float = 60.0

CASE_HEADERS: tuple[str, ...] = (
    "пользователь",
    "тема кейса",
    "начало",
    "конец",
    "session_id",
    "source",
    "chat_id",
    "thread_id",
    "session_title",
    "confidence",
    "flags",
    "start_msg_id",
    "end_msg_id",
)

SESSION_HEADERS: tuple[str, ...] = (
    "session_id",
    "пользователь",
    "source",
    "started_at",
    "message_count",
    "user_msgs",
    "user_chars",
    "status",
)
# status ∈ {ok, skipped_empty, llm_error, over_limit, no_task}

@dataclass
class CaseRow:
    user: str
    topic: str
    start: str                         # ISO-8601 +03:00 (или оффсет --tz)
    end: str
    session_id: str
    source: str
    chat_id: str
    thread_id: str
    session_title: str
    confidence: str
    flags: str                         # CSV внутри ячейки: chunked,overlap,llm_retry,empty_skip через запятую
    start_msg_id: int
    end_msg_id: int

@dataclass
class SessionInventoryRow:
    session_id: str
    user: str
    source: str
    started_at: str                    # ISO с оффсетом
    message_count: int
    user_msgs: int
    user_chars: int
    status: str

def style_header(ws: Any) -> None
    # row 1: bold + PatternFill HEADER_FILL_HEX; freeze panes A2

def autosize(ws: Any) -> None
    # ширина по max(len(cell), MIN) clip MAX; кириллица: len символов ок для v1

def case_to_tuple(row: CaseRow) -> tuple
    # порядок строго CASE_HEADERS; не row.__dict__ (имена dataclass ≠ заголовки)
    # питфолл spreadsheet-deliverables: брать атрибуты объекта, не JSON-ключи

def session_to_tuple(row: SessionInventoryRow) -> tuple
    # порядок SESSION_HEADERS

def assert_no_raw_content(row: CaseRow) -> None
    # защитный assert в тестах; в проде не сериализовать поле content — его нет в CaseRow

def write_xlsx(path: Path, cases: Sequence[CaseRow], sessions: Sequence[SessionInventoryRow]) -> Path
    # Workbook; два листа; headers; rows; style; save
    # родительские директории mkdir parents exist_ok (Inbox уже есть; не создавать Tools/CaseCollector)
    # перезапись path

def write_csv_pair(path_stem: Path, cases, sessions) -> tuple[Path, Path]
    # path_stem без суффикса или с .xlsx → {stem}.csv и {stem}_sessions.csv
    # csv.writer delimiter=';' encoding utf-8-sig newline=''
    # quoting minimal

def write_deliverable(
    output: Path,
    cases: Sequence[CaseRow],
    sessions: Sequence[SessionInventoryRow],
) -> tuple[Path, str]
    # пробует import openpyxl и write_xlsx
    # ImportError или OSError/PermissionError → write_csv_pair, kind="csv"
    # kind="xlsx" при успехе; csv рядом НЕ писать, если xlsx удался
    # возвращает (главный путь, kind) — для отчёта «какой файл открывать»
```

**Тесты (`tests/test_xlsx_out.py`):**

| Тест | Критерий | Fixture |
|---|---|---|
| `test_xlsx_headers_and_two_sheets` | листы «Кейсы»/«Сессии», заголовки §3.1 | `tmp_path`, skip если нет openpyxl |
| `test_header_bold_fill` | font.bold, fill не пустой | openpyxl |
| `test_cyrillic_intact` | тема «настройка доступов» читается обратно | — |
| `test_no_content_column` | нет заголовка `content` / `text` / `body` | — |
| `test_no_jira_columns` | нет «Jira»/«вердикт» | OQ-7 |
| `test_csv_fallback_delimiter` | monkeypatch `sys.modules['openpyxl']=None` → csv с `;`, utf-8-sig BOM `ef bb bf` | `tmp_path` |
| `test_csv_fallback_on_write_error` | write_xlsx бросает OSError → csv | monkeypatch |
| `test_flags_overlap_written` | ячейка flags содержит `overlap` | CaseRow |
| `test_dry_run_sessions_only` | cases=[] → лист Кейсы только заголовок, Сессии заполнен | — |

---

### 8. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/references/user-map.example.yaml`

**Назначение.** Схема карты пользователей без реальных id и без ФИО (ТЗ §2.5, §6.2). Боевой `--user-map` живёт у оператора, в git скилла не коммитится. Linux-доказательство: Саша может локально завести thread_id → ярлык топика (не в репозитории).

**Содержимое (канон для HF:impl — вписать как есть, подставив вымышленные ключи):**

```yaml
# Пример --user-map. Не содержит боевых id.
# Ключи: первый матч побеждает (session_key → source:chat:thread → thread_id → user_id).

session_key:
  "agent:main:telegram:group:chat-example:topic-1": "Топик Пример 1"

source_chat_thread:
  "telegram:chat-example:topic-2": "Топик Пример 2"

thread_id:
  "topic-3": "Топик Пример 3"

user_id:
  "u-example": "Аналитик Пример"
```

**Сигнатуры:** нет.

**Тесты:** `test_identity.py::test_example_yaml_loads`, `test_no_real_linux_ids_in_example`.

---

### 9. `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/references/split-prompt.md`

**Назначение.** Системная инструкция split (ТЗ §4.4). SKILL.md на неё ссылается; `load_split_prompt()` читает файл целиком. Менять формулировки тем можно принимающему Windows-агенту; схему JSON и правило «границы = id, не даты» — нельзя без секции ТЗ.

**Текст промпта (канон v1, вписать в файл на HF:impl):**

```
Ты разбиваешь один диалог пользователя с ассистентом на смысловые рабочие кейсы.

Правила:
- Новый кейс = смена ПРЕДМЕТА задачи, не смена времени и не пауза.
- Не начинай новый кейс на уточнениях, «ок», «поправь», продолжении той же работы, бытовом шуме внутри темы.
- Начинай новый кейс, если пользователь явно переходит к другой задаче, указывает другую цель, другую Jira-ссылку как другой предмет, начинает тему с нуля.
- Тема — по-русски, 5–15 слов, без транслита, без кавычек-обёрток, без префиксов «пользователь просит», «задача:».
- Границы кейса — поля start_msg_id и end_msg_id: это id сообщений ИЗ ВХОДА. Не выдумывай id и не ставь даты.
- Если рабочей задачи нет — верни "cases": [].
- Верни ТОЛЬКО JSON, без markdown-ограды, без комментариев, без текста вокруг.

Схема:
{
  "schema_version": "1.0",
  "session_id": "<тот же, что во входе>",
  "cases": [
    {
      "topic": "краткая тема",
      "start_msg_id": 123,
      "end_msg_id": 140,
      "confidence": "high"
    }
  ]
}

confidence только high, medium или low.
Не включай в JSON тексты сообщений и не включай ISO-даты начала/конца.
```

**Тесты:** `test_split_llm.py::test_prompt_file_exists_and_forbids_dates` — файл есть; содержит `schema_version`; содержит запрет дат / markdown-ограды.

---

### 10. Тестовый контур (создаётся на HF:impl, гоняется на HF:test)

Пути:

```
/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/tests/conftest.py
/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/tests/test_db.py
/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/tests/test_transcript.py
/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/tests/test_split_llm.py
/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/tests/test_identity.py
/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/tests/test_xlsx_out.py
/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/tests/test_cli.py
```

`tests/conftest.py` — см. раздел «Тесты и fixture». Не создавать бинарный `mini.db` в git: собирать схему в `tmp_path` каждый прогон.

---

## Порядок операций с критериями проверки

Порядок = master-ТЗ §14. Исполнитель (`HF:impl`) идёт сверху вниз и отмечает чекбоксы «Прогресс выполнения». Промежуточные точки — молча, без отчёта Саше (`hermes-feature` Блок 1А). `HF:test` гоняет полный pytest и критерии успеха v1, которые не требуют живого LLM. Этап 8 (ручной прогон) — только после зелёных тестов и явной команды/хвоста фазы, **не** открывая запись в `state.db`. Этап 9 — оркестратор, не исполнитель.

Общий критерий каждого этапа: `pytest` по тестам **этого** этапа зелёный; grep-инварианты (нет `/home/tkachenkoav`, нет slug модели в `scripts/*.py`, нет `immutable=1`, нет `agent -p`) держатся с этапа 1.

### Этап 1 — каркас + CLI + `db.py` + dry-run

**Сделать:** каталог скилла; `SKILL.md` (черновик триггеров+CLI, без обещания несуществующих флагов); `scripts/db.py`; `scripts/case_collector.py` с argparse + `run()` в режиме dry-run (лист «Сессии» можно пока печатать JSON в stdout, если `xlsx_out` ещё нет — допустимо на этапе 1 писать инвентарь как JSON-файл рядом, **сменить на xlsx на этапе 6**). Не вызывать LLM. Не открывать живой `state.db` в автотестах.

**Критерий готовности:**

- `python3 scripts/case_collector.py --help` код 0, видны `--db --since --until --dry-run --exclude-sources --model --llm-backend`.
- `tests/test_db.py` + `test_cli.py` (подмножество без xlsx/LLM) зелёные.
- `--db /tmp/nonexistent-cc-db.sqlite --since 2026-09-08 --until 2026-09-11` → код 2, понятный stderr, ничего не записано в Inbox.
- `connect_ro` в исходнике: `mode=ro`, `query_only`, timeout≥30, нет `immutable=1`.
- dry-run на `fixture_db` создаёт инвентарь и не инстанцирует боевой адаптер.

### Этап 2 — транскрипт + фильтры

**Сделать:** `scripts/transcript.py`; оркестратор считает `user_msgs`/`user_chars` через него (dry-run тоже).

**Критерий:** `tests/test_transcript.py` зелёный; tool/compacted/noise отсутствуют в turns; stubs выкл по умолчанию.

### Этап 3 — JSON-контракт + FakeLlmAdapter + чанки

**Сделать:** `scripts/split_llm.py` без боевых адаптеров (классы-заглушки `HermesCallLlmAdapter`/`OpenAICompatAdapter` могут `raise NotImplementedError`); `references/split-prompt.md`; `split_session` работает на Fake; чанки+merge+overlap; `compute_bounds` по timestamp.

**Критерий:** `tests/test_split_llm.py` без сетевых тестов зелёный; multi-case fixture даёт 2 строки; битый JSON не валит соседнюю сессию на уровне `run()` (можно пока unit `split_session`); даты LLM игнорируются; grep `scripts/` без `subprocess`+`agent`.

### Этап 4 — боевые адаптеры + резолв модели

**Сделать:** реализовать `HermesCallLlmAdapter` (ленивый import, только `message.content`) и `OpenAICompatAdapter`; `resolve_backend`; `resolve_model`. Сетевые вызовы в pytest **мокать**. Живой `call_llm` на этапе 4 в CI не обязателен.

**Критерий:**

- `test_model_cli_overrides_env_and_config` + `test_model_unresolved` зелёные.
- `grep -R "deepseek/" scripts/` пусто.
- `auto` без hermes и без env → ненулевой exit, не `api.openai.com`.
- Мок `call_llm` возвращает JSON → `split_session` ok; пустой `content` не читается из `reasoning_details` (адаптер не вызывает extract_content_or_reasoning — grep).

### Этап 5 — identity

**Сделать:** `scripts/identity.py`; `references/user-map.example.yaml`; оркестратор заполняет «пользователь».

**Критерий:** `tests/test_identity.py` зелёный; без карты суррогат `source:chat:thread`; `user_name` Linux-типа не дефолт; example без реальных id.

### Этап 6 — xlsx + csv

**Сделать:** `scripts/xlsx_out.py`; dry-run и боевой пишут xlsx (или csv-fallback); отчёт называет путь и kind.

**Критерий:** `tests/test_xlsx_out.py` зелёный; два листа; кириллические заголовки; нет колонок Jira/content; fallback `;` + BOM.

### Этап 7 — полный pytest (`HF:test`)

**Сделать:** добить сквозной `test_cli.py` (dry-run → xlsx инвентарь; fake-LLM → кейсы; exclude sources; no-write mtime). Не указывать `--db` на живой `state.db`.

**Критерий (критерии успеха v1, автоматизируемые):**

1. Прогон на fixture с `mode=ro` не меняет mtime/size fixture-БД; write-SQL не проходит.
2. xlsx с обязательными колонками; csv-fallback на mock openpyxl.
3. `source IN (cron, kanban, subagent)` нет в листе «Кейсы» при дефолтном exclude.
4. В xlsx нет сырого `content`.
5. В `scripts/*.py` нет захардкоженного slug модели.
6. Несуществующий `--db` → ненулевой exit, без output-файла.
7. Битый JSON одной сессии не убивает остальные (`status=llm_error` + другие `ok`).
8. В исходниках нет `jira`, `jobs.json` write, `Loop` API.
9. `--dry-run` → Fake/мок `complete.calls == 0`.

### Этап 8 — ручной Linux-прогон 3 дня

**Не автоматизировать в pytest.** Команда (после согласования Саши / хвоста):

```
<venv-python> scripts/case_collector.py \
  --since <сегодня-3д> --until <сегодня> \
  --dry-run --limit 20
```

затем без `--dry-run` с `--limit 20`, затем без `--limit` на фактических ~24 пригодных сессиях. `--db` можно не передавать (дефолт `Path.home()/".hermes"/"state.db"`). Перед боевым прогоном — `stat` mtime/size живой БД; после — сравнить (критерий успеха 1). В чат Саше: путь xlsx, числа, usage, список `llm_error`, счётчик OQ-4, факт multi-case (желательно, не blocking — OQ-15).

**Критерий:** валидный xlsx, обязательные колонки, несколько строк кейсов, cron/kanban/subagent отсутствуют, mtime `state.db` не вырос из-за нас, сырого диалога в файле нет.

### Этап 9 — `ORCH:shared-state`

**Не делать на HF:impl / HF:test / HF:plan.** Оркестратор: `EcosystemManifest` как `hermes_skill`, `restore-all-skills.sh`, digest. Кроны не создавать. `jobs.json` не трогать. `MAIN_TZ_INVENTORY.md` уже содержит CaseCollector после `TZ:finalize` — исполнителю не дублировать.

---

## Промежуточные точки

Исполнитель проходит молча. Каждая точка — бинарная. Сбой → стоп этапа, не перескакивать к xlsx «чтобы было что показать».

| ID | Когда | Проверка | Fail → |
|---|---|---|---|
| T1 | конец этапа 1 | `--help` + `test_db.py` + missing db exit 2 + URI `mode=ro` без `immutable` | не начинать transcript |
| T2 | конец этапа 1 | grep `scripts/db.py`: нет `INSERT`, нет CLI `sqlite3` | откатить db.py |
| T3 | конец этапа 2 | `test_transcript.py`; tool не в turns | не начинать split |
| T4 | конец этапа 3 | Fake split + chunk merge + overlap + bounds из timestamp | не включать сеть |
| T5 | конец этапа 4 | резолв модели 1/2/3; fail-loud; grep нет slug | не писать identity |
| T6 | конец этапа 5 | суррогат и карта; нет Linux ФИО-дефолта | не писать xlsx |
| T7 | конец этапа 6 | xlsx колонки §3.1; csv `;`+BOM | не объявлять impl done |
| T8 | этап 7 | полный pytest; 9 критериев успеха кроме живого 3-дневного прогона | не ручной прогон |
| T9 | этап 8 | mtime state.db неизменен; xlsx на 3 дня | отчёт Саше, не ORCH |
| T10 | всегда | нет каталога `Tools/CaseCollector/`, нет записи в `jobs.json`, нет правок чужих скиллов | откат по разделу ниже |

Точка **диск-факт premature-impl** относится к `HF:plan`/`REV:plan`, не к исполнителю: на момент этого плана каталог скилла **отсутствует**. Если к старту `HF:impl` каталог уже появится не из этого плана — сверить с § Файлы, не плодить второй скилл; неожиданный код до `GATE:plan-approve` — аномалия канбана, не «дописать».

---

## Тесты и fixture

**Команда `HF:test`:**

```
cd /home/tkachenkoav/hermes-workspace/skills/productivity/case-collector
<python> -m pytest tests/ -q
```

`PYTHONPATH` не обязателен, если `conftest.py` вставляет `scripts/` в `sys.path`. Живой `state.db` не передавать. Маркер `@pytest.mark.live` не вводить в v1 — живой прогон ручной (этап 8).

### `tests/conftest.py`

```python
# Назначение fixture (не код этой фазы — контракт для HF:impl):

@pytest.fixture
def skill_root() -> Path
    # parents[1] от tests/

@pytest.fixture
def scripts_dir(skill_root) -> Path

@pytest.fixture
def tz_moscow() -> ZoneInfo
    # ZoneInfo("Europe/Moscow")

@pytest.fixture
def fixture_db(tmp_path) -> Path
    # СОЗДАТЬ sqlite в tmp_path / "mini.db" обычным sqlite3.connect (запись в tmp — ок)
    # схема sessions/messages с required+optional колонками как Linux 11.09.2026
    # НЕ копировать ~/.hermes/state.db
    # наполнить фиксированными id (вымышленные):
    #   S-tg-1  source=telegram  started_at в окне 2026-09-09  thread_id=t-1  6 user msgs, 2 предмета
    #   S-tg-2  source=telegram  в окне  thread_id=t-2  2 user msgs, 1 предмет
    #   S-cron  source=cron      в окне  user msgs есть
    #   S-kan   source=kanban    в окне
    #   S-sub   source=subagent  в окне
    #   S-arch  source=telegram  archived=1  в окне
    #   S-tool  source=telegram  только role=tool
    #   S-comp  source=telegram  user compacted=1 only
    #   S-out   source=telegram  started_at ДО окна, user timestamp ВНУТРИ окна (OQ-4)
    #   S-noise source=telegram  user content = "[IMPORTANT: Background process ..."
    # timestamps: epoch float; окно канона тестов: since=2026-09-08T00:00+03:00 until=2026-09-11T00:00+03:00
    # ПОСЛЕ наполнения закрыть write-соединение; тесты открывают через connect_ro
    # chat_id/thread_id/user_id вымышленные: chat-example, t-1, u-test — не Linux боевые

@pytest.fixture
def fixture_db_minimal_cols(tmp_path) -> Path
    # только REQUIRED колонки sessions/messages — degrade optional

@pytest.fixture
def sample_messages() -> list[MessageRow]
    # разнообразие ролей/active/compacted/шум/assistant/tool для transcript

@pytest.fixture
def user_map_file(tmp_path) -> Path
    # YAML секций как example, ключи от fixture_db

@pytest.fixture
def fake_adapter() -> FakeLlmAdapter
    # S-tg-1 → 2 cases (два предмета, id из fixture)
    # S-tg-2 → 1 case
    # прочие → cases []

@pytest.fixture
def isolated_output(tmp_path) -> Path
    # tmp_path / "out.xlsx" — никогда Inbox в тестах
```

Константа окна тестов: не «сегодня», чтобы тесты не стали flaky 12.09.

Запрет в `conftest.py`: `Path.home() / ".hermes" / "state.db"` не должен встречаться как дефолт открытия. Можно явно:

```python
assert os.environ.get("CASE_COLLECTOR_TEST_FORBID_LIVE_DB", "1") == "1"
```

и в `connect_ro` тестов передавать только `tmp_path`.

### Матрица покрытия (сводка)

| Требование | Тест | Модуль |
|---|---|---|
| mode=ro + query_only, без immutable, timeout≥30 | `test_connect_ro_uri_mode`, `test_timeout_default` | db |
| no write-SQL + mtime | `test_execute_ro_rejects_*`, `test_no_write_mtime` | db, cli |
| exclude cron/kanban/subagent | `test_exclude_sources` | db, cli |
| OQ-4 счётчик | `test_oq4_counter` | db |
| OQ-3 degrade | `test_optional_column_degrade` | db |
| фильтры transcript | `test_drops_*` | transcript |
| чанки + overlap ids | `test_chunk_*` | transcript |
| JSON schema + retry | `test_parse_*`, `test_retry_*` | split_llm |
| bounds скриптом | `test_compute_bounds_*`, `test_ignore_llm_iso_dates` | split_llm |
| chunk merge без merge-LLM | `test_chunk_merge_*` | split_llm |
| overlap flag | `test_overlap_flag` | split_llm |
| multi-case fixture (OQ-15) | `test_two_cases_in_one_session` | split_llm |
| модель не хардкод | `test_no_hardcoded_model_slug_in_scripts` | cli |
| backend fail-loud | `test_auto_fail_loud_without_backend` | split_llm |
| identity fallback | `test_fallback_*`, `test_not_linux_user_name_by_default` | identity |
| xlsx колонки + csv `;` BOM | `test_xlsx_*`, `test_csv_fallback_*` | xlsx_out |
| нет сырого content / Jira колонок | `test_no_content_column`, `test_no_jira_columns` | xlsx_out |
| dry-run без LLM | `test_dry_run_does_not_call_llm` | cli |
| db missing | `test_db_not_found` | cli |
| llm_error изолирован | `test_llm_error_does_not_abort` | cli |
| нет `/home/tkachenkoav` | `test_no_home_tkachenkoav_in_scripts` | cli |
| нет `agent -p` | grep в `test_split_llm` | split_llm |
| нет вызовов Jira/Loop/Exchange, нет записей в jobs.json (критерий 8) | `test_no_jira_loop_exchange_jobsjson_in_scripts` | split_llm (grep по scripts) |

---

## Процедура отката

Каталог скилла на старте `HF:plan` отсутствует — откат **кода** = удаление дерева, которое создаст `HF:impl`, без восстановления из hermes-backup (конфиги не менялись).

1. **Откат незавершённого `HF:impl` (каталог появился, манифест ещё нет):**  
   удалить целиком  
   `/home/tkachenkoav/hermes-workspace/skills/productivity/case-collector/`  
   Проверить, что симлинков в `~/.hermes/skills/productivity/case-collector` ещё нет (их делает `ORCH:shared-state` / restore). Если симлинк уже появился вне канона — снять симлинк, **не** трогая `restore-all-skills.sh` содержимое чужих скиллов.

2. **Откат после частичной записи xlsx в Inbox:** удалить только файлы `case-collector_*.xlsx` / `*.csv`, которые создал этот прогон. Не чистить чужие файлы Inbox.

3. **Откат тестовых артефактов:** `tmp_path` pytest сам; не оставлять `/tmp/mini.db` с копией логов.

4. **Что откатывать нельзя и не нужно:** `~/.hermes/state.db` (мы в него не пишем — если mtime изменился, это gateway/WAL, не «наш откат VACUUM»). `jobs.json`, `config.yaml`, `.env`, `EcosystemManifest.json`, `MAIN_TZ_INVENTORY.md`, чужие скиллы — не должны меняться; если изменились, это дефект impl → `kanban_block`, не silent revert чужого.

5. **Откат этой фазы `HF:plan`:** удалить только  
   `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/CaseCollector/HF-plan_case-collector_20260911.md`  
   Master-ТЗ не откатывать.

6. **После `ORCH:shared-state` (будущее):** откат = оркестратор убирает запись манифеста + restore. Исполнитель это не планирует как свой шаг.

Бэкап конфигов (`HF:backup` → `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`) для этого скилла формально в хвосте канбана. Содержимое скилла живёт в `hermes-workspace`; архив Hermes не заменяет git workspace. Retention архивов — 2 недели, к этому плану не относится.

---

## Что НЕ трогать

Сводка master-ТЗ «Что НЕ трогать» + заморозка OQ + граница фазы `HF:plan`/`HF:impl`.

**Данные и рантайм Hermes**

- `~/.hermes/state.db`: никакой записи, смены схемы, `VACUUM`, WAL checkpoint, правок FTS. Даже «почистить секрет» — вне скоупа. Pytest **не** открывает живую БД даже на SELECT.
- `~/.hermes/cron/jobs.json` и любые кроны. Gateway не рестартовать.
- `~/.hermes/config.yaml` / `.env` — не писать; читать `model.default` и `custom_providers` только на прогоне. Ключи не копировать в скилл.
- Профили `tz-dev` / `anthropic` / `openai` не реанимировать.
- ErrorBus не подключать (OQ-9).

**Соседи и API**

- Jira, Confluence, Loop, Exchange, `MoveFromJira`, `jira_snapshot.json`, карточки канбана.
- Не патчить `backlog-collector`, `backlog_fetch.py`, `hermes-cost-audit`, `loop-channel-digest`, `PIIScan`, `cursor-task-context`. Паттерн read-only sqlite копировать, код не импортировать.
- Не ослаблять запрет PIIScan «не читать state.db» для **других** скиллов. Исключение чтения — только этот скилл, и только SELECT.

**Продуктовые границы v1 (OQ заморожены, Сашу не переспрашивать)**

- OQ-1: не заводить USERTOOLS-пакет `CaseCollector`.
- OQ-6: не склеивать темы across сессий.
- OQ-7: не добавлять пустые колонки Jira / «успешно».
- OQ-8: не писать артефакты в `TZ/CaseCollector/`; не создавать `Tools/CaseCollector/`.
- OQ-10: не делать второй merge-LLM.
- OQ-11: не батчить несколько сессий в один LLM-вызов.
- OQ-13: не фильтровать `profile_name`, нет `--profile`.
- OQ-14: не маскировать ФИО в темах; не публиковать таблицу в общий чат.

**Фаза и пайплайн**

- `HF:plan` не создаёт каталог скилла, не пишет Python скилла, не ставит кроны.
- `HF:impl` не пишет `EcosystemManifest.json`, `EcosystemManifest.digest.md`, `MAIN_TZ_INVENTORY.md`, `restore-all-skills.sh` — это `ORCH:shared-state`.
- Не использовать `agent -p` / Cursor CLI как движок split (ни в коде, ни как «временный» fallback в v1).
- Windows-инстанс и его БД с Linux не трогать.
- Не хардкодить `/home/tkachenkoav/...`, chat id `-1004300127777`, `user_id=400307920`, имя `Alex Tkachenko` как дефолт колонки.

**Поставка этого плана**

- Не редактировать `CaseCollector_TZ.md` в этой фазе.
- Не создавать второй файл плана в `plans/` — канон пути задан промптом фазы.

---

## Риски

| Риск | Почему вероятен | Смягчение в реализации |
|---|---|---|
| WAL/lock живой БД гейтвея | БД ≈ 1.68 ГБ, пишется gateway | `mode=ro` без `immutable=1`; timeout≥30; не checkpoint; dry-run сначала |
| Схема Windows/Mattermost иная | OQ-3 неизвестен `source` и колонки | fail-loud на required; degrade optional; `IdentityAdapter`; `--include-sources` параметром |
| Качество тем LLM / ложные смены кейса | семантика «предмет» размыта | промпт в references, не в коде-константе слишком короткой; multi-case закрыт fixture, не живым трафиком (OQ-15) |
| Чанки дублируют тему плохо | OQ-10 без merge-LLM | normalize+merge соседних; флаги `chunked`; не второй вызов |
| Сжигание бюджета | Pro/reasoning, assistant+tools, retry-шторм | дефолт модель из config (flash-класса); user-only; 1 retry; concurrency≤3; `--limit`; предупреждение >200 |
| Пустой `message.content` у flash (reasoning_details) | питфолл tutu | только `message.content`; пусто → retry/llm_error, не extract reasoning |
| `call_llm` недоступен на Windows | другой runtime | `--llm-backend openai-compat` + env; `auto` fail-loud |
| ru-Excel и CSV | прецедент ProxyCheckLinux | xlsx основной; csv только fallback с `;` и BOM |
| PII в темах | OQ-14 сознательно | файл в Inbox; в чат счётчики; не cron/output |
| Случайный SELECT по живой БД в pytest | привычка «проверить на проде» | fixture only; тест на отсутствие литерала live-path; этап 8 отдельный |
| Импорт `backlog_fetch.py` | «reuse» без read-only | прямой запрет в плане; свой `db.py` |
| Параллелизм sqlite | `--concurrency>1` | сначала вычитать сообщения, потом пул только на LLM; не шарить Connection |
| Дефолт Inbox на Windows без WorkVault | путь `Path.home()/WorkVault/Inbox` | `--output` обязателен к наличию; mkdir parents; понятная ошибка если нельзя писать |
| Латентность 15–40 мин | 150 вызовов | предупреждение в SKILL.md; `--limit 20` для дыма; concurrency max 3 |

Крупное отклонение (новый модуль, второй скилл, колонка Jira, крон) → исполнитель стоп, архитектор доплан. Мелкое (имя внутренней функции, порядок import) — сам.

---

## Прогресс выполнения

Дублирует чекбоксы после заголовка, чтобы хвост файла оставался источником статуса при сбое чтения середины.

- [x] **Этап 1.** Каркас скилла + CLI argparse + read-only `db.py` + dry-run инвентарь
- [x] **Этап 2.** Компакт-транскрипт + фильтры ролей / `active` / `compacted` / шум
- [x] **Этап 3.** JSON-контракт + фейковый адаптер (fixture) + чанки
- [x] **Этап 4.** Боевые адаптеры `HermesCallLlmAdapter` / `OpenAICompatAdapter`, модель из `--model` → env → `config.yaml`
- [x] **Этап 5.** Identity + `--user-map` + fallback суррогат
- [x] **Этап 6.** xlsx (`openpyxl`, `spreadsheet-deliverables`) + csv-fallback (`utf-8-sig`, `;`)
- [x] **Этап 7.** Pytest: fixture-sqlite (не живой `state.db`), overlap, chunk merge, exclude sources, no-write
- [ ] **Этап 8.** Ручной Linux-прогон 3 дня, отчёт Саше
- [ ] **Этап 9.** `ORCH:shared-state` (не сейчас)

Следующая фаза канбана после этого файла: `REV:plan`, затем `GATE:plan-approve`. Код — только после снятия гейта и `HF:backup`, исполнитель `composer-2.5`, фаза `HF:impl`.
