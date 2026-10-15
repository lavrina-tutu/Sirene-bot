---
tool: TelegramGroupTopics
phase: HF:plan
plan_version: 1.0
date: 2026-09-16
author: архитектор (cursor-grok-4.6-high)
case: CHANGE
status: draft-plan
source_tz: TZ/TelegramGroupTopics/TelegramGroupTopics_TZ.md v0.2.0 approved
diagnose: /home/tkachenkoav/hermes-agent/_fix_plan_20260916.md
executor: composer-2.5
next_phases: REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done
---

# HF:plan — TelegramGroupTopics (скилл `devops/tutu-telegram-delivery`)

Кейс **CHANGE**: единый модуль восстановления маршрутизации топиков TG «Сирень Workspace» внутри **уже существующего** скилла `tutu-telegram-delivery` + разовый WARNING в ядре. Этот файл — самостоятельный артефакт фазы **HF:plan** (Блок 1А `hermes-feature`). Код скилла, `adapter.py`, `.env`, `config.yaml`, `jobs.json` в этом вызове **не** писать.

Канон: master-ТЗ TelegramGroupTopics v0.2.0 (`approved`, Q1 вариант 1: снимок = ровно 8 топиков, **без** `:6556`). Очередь `HF:impl` — П.1'–П.7' (поглощает v0.1.0 П.1б+П.2 в `apply`; WARNING кода остаётся разовым П.5').

**Новых сущностей нет.** USERTOOL / новый скилл / `HERMES_*` / второй адаптер **не предлагаются**. Строка «Новая сущность X — требует согласования Саши» **не выставляется**.

Канон пути этого плана (исполнитель читает **его**, не черновики в `~/hermes-agent/`):

`/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/TelegramGroupTopics/HF-plan_telegram-group-topics_20260916.md`

---

## Прогресс выполнения

Устойчивость к сбою: чекбоксы отмечает исполнитель на `HF:impl` / `HF:test`. Архитектор на `HF:plan` их не закрывает. `ORCH:shared-state` — не эта фаза и не `HF:impl`. Рестарт gateway — только по «поднимай», не из скрипта.

- [ ] **Этап 1.** П.1' — YAML-снимок `references/sirene-workspace-topics.yaml` (ровно 8 топиков, без `:6556`, без секретов)
- [ ] **Этап 2.** П.2'/П.3'/П.4' — `scripts/restore_telegram_topics.py` + `.sh` (`apply|check|dry-run`), без live-`apply`
- [ ] **Этап 3.** П.2'/П.6' — SKILL.md: команда restore в шапке + таблица=зеркало; указатель в `hermes-gateway-setup`
- [ ] **Этап 4.** Pytest скрипта на temp `HERMES_HOME` (check/apply/dry-run, токен не печатается, `:6556` в `jobs.json` не drift)
- [ ] **Этап 5.** П.5' — WARNING в `adapter.py` + 2 инварианта `scripts/run_tests.sh`
- [ ] **Этап 6.** Live `dry-run` → `apply` → `check` (после `HF:backup`; скрипт сам gateway не трогает)
- [ ] **Этап 7.** Рестарт по «поднимай» + E2E `:6` без @mention (не pytest)
- [ ] **Этап 8.** `ORCH:shared-state`: `restore-all-skills.sh` — **не сейчас**, не исполнителем

Легенда: `[x]` = этап принят по критерию проверки ниже. Не отмечать «на глаз».

`disk_before` целевого скилла на эту фазу: существует только `SKILL.md`; нет `scripts/` / `references/` / `tests/`. Появление их **до** `GATE:plan-approve` = `PREMATURE_IMPL`.

---

## Цель плана

Спроектировать пофайловую поставку модуля «снимок + одна команда restore»: при полном крахе маршрутизации топиков группы «Сирень Workspace» (`-1004300127777`) оператор делает `apply` + рестарт по «поднимай» и получает inbound группы как до инцидента 16.09, **не** правя файлы руками и **не** ломая контракт env-over-YAML.

`apply` поглощает BUGFIX v0.1.0 **П.1б** (allowlist в обе копии `.env`) и **П.2** (YAML `gateway.telegram.token` = env `TELEGRAM_BOT_TOKEN`, prefix `863022`). Разовый WARNING на silent drop по allowlist — **П.5'**, скрипт его не повторяет.

Инварианты, которые план обязан сохранить в реализации:

1. **Env-over-YAML священен.** Непустой `TELEGRAM_ALLOWED_CHATS` побеждает YAML `telegram.allowed_chats` (`extra_or_secret`, `3dedb71f2f`, #108440). UNION yaml∪env **запрещён**. П.1а (удалить ключ из `.env`) этим проходом не делать.
2. **Снимок = ровно 8 топиков**, Q1 вариант 1: General=1, Tools=3, Hermes DEV=4, WorkVault=5, Backlog=6, Monitoring=7, Errors=11112, Personal=8. Топик `:6556` (Messages) в снимок **не** входит.
3. **`check` не читает `jobs.json`.** Наличие `:6556` там — не drift; `apply` его не создаёт, не удаляет, не «вычищает».
4. **Полный токен никуда не писать:** не в снимок, не в SKILL.md, не в stdout/stderr `check`/`dry-run`/`apply`, не в тесты как боевое значение, не в git. Только bot id prefix (`863022` / `882117`) и имя ключа `TELEGRAM_BOT_TOKEN`. `apply` копирует значение env → YAML, не наоборот.
5. **Скрипт не рестартует gateway** и не вызывает Telegram API / `getUpdates` (409). Печатает «нужен рестарт; ждать „поднимай“».
6. **П.5' не поглощается скриптом.** WARNING — точечный патч `adapter.py`. Forum-хелперы / session keys / prune / multiplex / `drop_pending_updates` не трогать.
7. **Errors=11112 совпадает с ErrorBus.** Снимок обязан совпасть с `~/.hermes/error_bus/_db.py` (`TELEGRAM_CHAT_ID`, `TELEGRAM_THREAD_ID`). Код ErrorBus этим проходом не менять.
8. **Reuse-first.** Модуль живёт в `tutu-telegram-delivery`. Не USERTOOL, не новый скилл, не `HERMES_*`, не core tool.
9. **Обе копии `.env`.** Узкий default-профиль снова даст тишину группы. `apply` пишет allowlist в `$HERMES_HOME/.env` и `$HERMES_HOME/profiles/default/.env`, если файлы существуют. Несуществующий `profiles/default/.env` **не** создавать с нуля.
10. **`TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` — не allowlist.** Канон `-1004300127777:1` (General) восстанавливается как «как было», но не используется как inbound-гейт.

Критерии «готово» **этой** фазы (`HF:plan`): записан этот файл; каталог скилла / `adapter.py` / `.env` / `config.yaml` / `jobs.json` / ТЗ / диагноз **не** изменены. Снятие `GATE:plan-approve` — не эта фаза.

---

## Факт на диске (проверено чтением 16.09)

| Артефакт | На диске | Цель плана | Делать на HF:impl |
|---|---|---|---|
| `~/.hermes/skills/devops/tutu-telegram-delivery/` | **реальный каталог**, только `SKILL.md` v1.1.0; **не** симлинк; **нет** в `~/hermes-workspace/skills/` | дом модуля | создать `references/` + `scripts/` + `tests/`; поправить SKILL.md |
| `~/.hermes/skills/devops/hermes-gateway-setup` | симлинк → `profiles/default/skills/...` → **`~/hermes-workspace/skills/devops/hermes-gateway-setup`** | П.6' указатель | патч **workspace-файла** (тот же inode, что live SKILL.md) |
| `~/hermes-agent/plugins/platforms/telegram/adapter.py` | `_should_process_message` ~5815: allowlist-miss → `return guest_mention` **без лога**; `_gate_or_observe` ~5888 зовёт его; `_handle_command` ~5924 и `_handle_media_message` ~6224 зовут `_should_process_message` **напрямую** | П.5' | WARNING в ветке allowlist `_should_process_message` (покрывает text/command/media) |
| `~/hermes-agent/gateway/platforms/_shared.py` `extra_or_secret` | env-first, blank unset | контракт | **не трогать** |
| `~/hermes-agent/tests/gateway/test_telegram_group_gating.py` | ~959 строк; `_make_adapter` ставит `allowed_chats=[]` если не передали; autouse чистит `TELEGRAM_*` | сосед | **не дописывать**; новый файл тестов |
| `~/hermes-agent/tests/plugins/platforms/telegram/test_allowlist_json_adapter.py` | JSON-string allowlist | сосед | **не расширять** |
| `~/.hermes/.env` и `profiles/default/.env` | `TELEGRAM_ALLOWED_CHATS=400307920` (без группы); `TELEGRAM_BOT_TOKEN` prefix `863022`; startup `-1004300127777:1` | П.1б | пишет **только** `apply` после `HF:backup` |
| `~/.hermes/config.yaml` | `telegram.allowed_chats` уже с группой; `require_mention: false`; `guest_mode: false`; `gateway.telegram.token` prefix **`882117`** | П.2 + YAML extra | пишет **только** `apply`; round-trip `ruamel.yaml` |
| `~/.hermes/error_bus/_db.py` | `TELEGRAM_CHAT_ID = "-1004300127777"`; `TELEGRAM_THREAD_ID = "11112"` | сверка канона | **не трогать** код; `check` сверяет, если файл есть |
| `jobs.json` / `sessions.json` / `channel_directory.json` | `:6556` Messages живёт в jobs | Q1 вариант 1 | **не трогать** |

Два дерева правок на `HF:impl`:

- **A. in-tree `~/hermes-agent` (git):** `adapter.py` + 1 тест-файл.
- **B. user-skill `~/.hermes/skills/devops/tutu-telegram-delivery/` (не git hermes-agent):** снимок, скрипт, тесты скрипта, SKILL.md.
- **C. workspace-скилл указателя:** `~/hermes-workspace/skills/devops/hermes-gateway-setup/SKILL.md` (одна строка).
- **D. runtime (после `apply`):** обе `.env` + `config.yaml`. Не коммитить.

Интерпретатор скрипта: `Path.home() / "hermes-agent" / ".venv" / "bin" / "python3"` если файл существует, иначе `sys.executable` / `python3`. В коде скрипта **запрещены** литералы `/home/tkachenkoav/...`. `ruamel.yaml==0.18.17` уже в venv Hermes (`pyproject.toml`); новых pip-пакетов не ставить. Если `ruamel` нет — fail-loud «запусти через venv Hermes», не fallback на `yaml.dump` всего `config.yaml`.

---

## Файлы

**Корень поставки скилла (на `HF:plan` существует только `SKILL.md`; остальное создаётся на `HF:impl`):**

```
/home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery/
  SKILL.md                                          # изменить
  references/sirene-workspace-topics.yaml           # создать (П.1')
  scripts/restore_telegram_topics.sh                # создать (точка входа ТЗ)
  scripts/restore_telegram_topics.py                # создать (реализация, тестируемая)
  tests/conftest.py                                 # создать
  tests/test_restore_telegram_topics.py             # создать
```

`scripts/__init__.py` не заводить: модули — плоские скрипты; тесты добавляют `scripts/` в `sys.path`. Пакета USERTOOLS нет. Не регистрировать в `model_tools` / `toolsets.py`.

**Ядро (git `~/hermes-agent`):**

```
/home/tkachenkoav/hermes-agent/plugins/platforms/telegram/adapter.py
/home/tkachenkoav/hermes-agent/tests/plugins/platforms/telegram/test_allowlist_env_over_yaml.py
```

**Указатель (П.6'):**

```
/home/tkachenkoav/hermes-workspace/skills/devops/hermes-gateway-setup/SKILL.md
```

Общий контракт импорта тестов скилла:

```python
# в tests/conftest.py:
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
```

---

### 1. `/home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery/references/sirene-workspace-topics.yaml`

**Назначение.** Единственный машиночитаемый канон маршрутизации (П.1'). Без секретов. `schema_version: "1.0"` внутри YAML — версия формата снимка, не версия ТЗ. Скилл-таблица — человекочитаемое зеркало, не второй канон.

**Содержимое (вписать как есть; имена ключей — контракт скрипта):**

```yaml
schema_version: "1.0"
chat_id: "-1004300127777"
dm_chat_id: "400307920"
topics:
  General: 1
  Tools: 3
  "Hermes DEV": 4
  WorkVault: 5
  Backlog: 6
  Monitoring: 7
  Errors: 11112
  Personal: 8
allowlist_csv: "400307920,-1004300127777"
yaml_extra:
  allowed_chats: "400307920,-1004300127777"
  require_mention: false
  guest_mode: false
bot:
  env_key: TELEGRAM_BOT_TOKEN
  id_prefix: "863022"
  username: sirene_vm_bot
env_files:
  - "$HERMES_HOME/.env"
  - "$HERMES_HOME/profiles/default/.env"
config_yaml: "$HERMES_HOME/config.yaml"
startup_channels: "-1004300127777:1"
deliver_form: "telegram:-1004300127777:<thread>"
error_bus:
  chat_id: "-1004300127777"
  thread_id: 11112
```

**Поля снимка (~20 констант) — канон для `load_snapshot` / `collect_drift`:**

| # | Поле | Значение | Зачем |
|---|---|---|---|
| 1 | `schema_version` | `"1.0"` | версия формата; breaking каталога → bump |
| 2 | `chat_id` | `"-1004300127777"` | группа Сирень Workspace |
| 3 | `dm_chat_id` | `"400307920"` | DM; inbound-гейт чата не проходит |
| 4 | `topics.General` | `1` | thread_id |
| 5 | `topics.Tools` | `3` | |
| 6 | `topics["Hermes DEV"]` | `4` | ключ с пробелом — в YAML в кавычках |
| 7 | `topics.WorkVault` | `5` | |
| 8 | `topics.Backlog` | `6` | E2E-топик |
| 9 | `topics.Monitoring` | `7` | |
| 10 | `topics.Errors` | `11112` | совпасть с ErrorBus |
| 11 | `topics.Personal` | `8` | |
| 12 | `allowlist_csv` | `"400307920,-1004300127777"` | П.1б; без пробелов |
| 13 | `yaml_extra.allowed_chats` | тот же CSV | не побеждает env, не должен разъехаться |
| 14 | `yaml_extra.require_mention` | `false` | как до 13:11 |
| 15 | `yaml_extra.guest_mode` | `false` | не обход allowlist |
| 16 | `bot.env_key` | `TELEGRAM_BOT_TOKEN` | имя ключа, не значение |
| 17 | `bot.id_prefix` | `"863022"` | poller / `sirene_vm_bot` |
| 18 | `bot.username` | `sirene_vm_bot` | идентичность, не секрет |
| 19 | `env_files[0]` | `$HERMES_HOME/.env` | первая копия |
| 20 | `env_files[1]` | `$HERMES_HOME/profiles/default/.env` | вторая копия |
| 21 | `config_yaml` | `$HERMES_HOME/config.yaml` | YAML extras + token |
| 22 | `startup_channels` | `"-1004300127777:1"` | не allowlist |
| 23 | `deliver_form` | `telegram:-1004300127777:<thread>` | канон для людей; `jobs.json` не писать |
| 24 | `error_bus.thread_id` | `11112` | сверка, не правка ErrorBus |

**Запреты в файле:** полный токен; ключ/значение `6556`; имя `Messages`; пути `jobs.json`; литерал `/home/tkachenkoav`.

**Сигнатуры:** нет (данные). Читатель — `load_snapshot()`.

**Тесты:** `test_snapshot_exactly_eight_topics_no_6556`; `test_snapshot_has_no_token_pattern`; косвенно все `check`/`apply`.

---

### 2. `/home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh`

**Назначение.** Публичная точка входа ТЗ. Тонкая обёртка над `.py`. Не рестартует gateway. Не вызывает `curl` к `api.telegram.org`.

**Контракт оболочки:**

```bash
#!/usr/bin/env bash
set -euo pipefail
# usage: restore_telegram_topics.sh apply|check|dry-run
# резолв SCRIPT_DIR; PYTHON: $HERMES_AGENT_ROOT/.venv/bin/python3 если файл есть,
#   иначе $HOME/hermes-agent/.venv/bin/python3 если есть, иначе python3
# exec "$PYTHON" "$SCRIPT_DIR/restore_telegram_topics.py" "$@"
```

**CLI-аргументы:** ровно один позиционный: `apply` | `check` | `dry-run`. `--help` / `-h` → usage, exit 0. Иной argv → usage на stderr, exit 2. Флагов `--profile` / `--restart` / `--jobs` / `--union` **не** делать. `HERMES_HOME` — только из окружения (для тестов).

**Exit codes обёртки:** проксируют код `.py`.

**Тесты:** `test_help_exit_0` (через `.py` `--help` достаточно); grep `.sh` не содержит `getUpdates`, `systemctl`, `restart_gateway`.

---

### 3. `/home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.py`

**Назначение.** Реализация `apply|check|dry-run` (П.2'/П.3'/П.4'). Идемпотентность: повторный `apply` на уже выровненном дереве не портит прочие ключи `.env` / прочие ключи YAML; делает новый бэкап трёх файлов (это норма). Watermark нет.

**Сигнатуры:**

```python
SCHEMA_VERSION: str = "1.0"
CANON_TOPICS: dict[str, int] = {
    "General": 1,
    "Tools": 3,
    "Hermes DEV": 4,
    "WorkVault": 5,
    "Backlog": 6,
    "Monitoring": 7,
    "Errors": 11112,
    "Personal": 8,
}
FORBIDDEN_THREAD_IDS: frozenset[int] = frozenset({6556})
BOT_ID_PREFIX: str = "863022"
ALLOWLIST_CSV: str = "400307920,-1004300127777"
STARTUP_CHANNELS: str = "-1004300127777:1"
ENV_ALLOWLIST_KEY: str = "TELEGRAM_ALLOWED_CHATS"
ENV_BOT_KEY: str = "TELEGRAM_BOT_TOKEN"
ENV_STARTUP_KEY: str = "TELEGRAM_ADDITIONAL_STARTUP_CHANNELS"
TOKEN_RE: re.Pattern[str] = re.compile(r"\d{8,}:[A-Za-z0-9_-]{20,}")

class RestoreError(Exception): ...
class SnapshotError(RestoreError): ...

@dataclass(frozen=True)
class Drift:
    file: str          # путь или логическое имя ("snapshot", "error_bus")
    key: str
    expected: str      # без полного токена
    actual: str        # уже redact()'нутый

def hermes_home() -> Path
    # os.environ["HERMES_HOME"] если непустой, иначе Path.home() / ".hermes"
    # НЕ импортировать hermes_constants обязательно (тест скрипта без sys.path на репо)
    # ЗАПРЕЩЕНО: литерал /home/tkachenkoav и хардкод "~/.hermes" как единственный корень

def skill_root() -> Path
    # Path(__file__).resolve().parents[1]

def default_snapshot_path() -> Path
    # skill_root() / "references" / "sirene-workspace-topics.yaml"

def load_snapshot(path: Path | None = None) -> dict
    # yaml.safe_load; нет файла → SnapshotError
    # schema_version == "1.0"
    # set(topics.keys()) == set(CANON_TOPICS)
    # все values == CANON_TOPICS[name] (int)
    # 6556 not in values; "Messages" not in keys
    # TOKEN_RE не матчится на dump снимка
    # chat_id / dm_chat_id / allowlist_csv / bot.id_prefix как в таблице полей

def expand_path(template: str) -> Path
    # заменить $HERMES_HOME и ${HERMES_HOME} на str(hermes_home())
    # Path.expanduser() после замены

def redact(text: str) -> str
    # TOKEN_RE → "<redacted-token>"
    # в stdout/stderr/str(Drift) вызывать всегда

def token_prefix(token: str | None) -> str
    # часть до ':' ; пусто → ""
    # для канона достаточно первых 6 символов ("863022" / "882117")

def csv_set(raw: str | None) -> set[str]
    # split ",", strip, drop empty; сравнение множеством, не порядком

def read_env_key(env_path: Path, key: str) -> str | None
    # нет файла → None
    # первая строка ^KEY= (не коммент); value без окружающих кавычек
    # не логировать value если "TOKEN" in key

def write_env_key(env_path: Path, key: str, value: str) -> None
    # файл должен существовать (apply не создаёт .env с нуля)
    # заменить существующую строку KEY=... ИЛИ дописать KEY=value\n
    # прочие строки/комментарии/порядок не менять
    # не переписывать файл через dict (съест комментарии)

def backup_targets(paths: Sequence[Path]) -> Path
    # dest = hermes_home() / "_Archives" / f"hermes-backup-{YYYYMMDD-HHMMSS}"
    # mkdir parents; copy2 только существующие файлы (basename сохраняется;
    #   для двух .env: класть как "dot-env" и "profiles-default.env" ИЛИ
    #   поддерево .env + profiles/default/.env — рекомендация: поддерево
    #   относительно hermes_home(), чтобы не столкнуть два файла с именем .env)
    # вернуть dest

def load_yaml_rt(path: Path):
    # ruamel.yaml RoundTripLoader; нет ruamel → RestoreError с текстом про venv

def patch_config_yaml(config_path: Path, snapshot: dict, bot_token: str) -> None
    # round-trip: выставить
    #   telegram.allowed_chats = snapshot allowlist_csv (строка CSV, не JSON-list)
    #   telegram.require_mention = False
    #   telegram.guest_mode = False
    #   gateway.telegram.token = bot_token (полное значение из env, не prefix)
    # прочие ключи/комментарии не менять
    # ЗАПРЕЩЕНО: yaml.dump всего файла через PyYAML

def collect_drift(snapshot: dict) -> list[Drift]
    # см. инварианты ниже; jobs.json НЕ открывать

def format_drift(rows: Sequence[Drift]) -> str
    # по строке: file, key, expected, actual; прогнать через redact()
    # пустой список → ""

def cmd_check(snapshot: dict | None = None) -> int
    # drift пуст → 0; иначе печать format_drift в stdout + 1
    # SnapshotError → stderr + 2

def cmd_dry_run(snapshot: dict | None = None) -> int
    # как check, плюс блок "would write" по тем же ключам (allowlist, token prefix,
    #   require_mention, startup_channels) — без значений полного токена
    # ноль записей на диск (не создавать _Archives)
    # exit 1 при drift, 0 если совпало, 2 на ошибку входа

def cmd_apply(snapshot: dict | None = None) -> int
    # 1 backup существующих из env_files + config_yaml
    # 2 для каждого существующего env_files:
    #      write TELEGRAM_ALLOWED_CHATS = allowlist_csv
    #      write TELEGRAM_ADDITIONAL_STARTUP_CHANNELS = startup_channels
    #      НЕ трогать TELEGRAM_BOT_TOKEN и любые другие ключи
    #    несуществующий env_files: warning на stderr, не создавать
    # 3 bot_token = read_env_key($HERMES_HOME/.env, TELEGRAM_BOT_TOKEN)
    #      если пусто — попробовать вторую копию; всё ещё пусто → exit 2
    #      prefix должен быть 863022 иначе warning (всё равно копируем значение env → YAML:
    #      источник истины poller = env)
    # 4 patch_config_yaml(...)
    # 5 печать: "нужен рестарт gateway (скрипт сам не рестартует; ждать «поднимай»)"
    # 6 return cmd_check()   # 0 если диск = снимок

def parse_args(argv: list[str] | None = None) -> argparse.Namespace
    # positional: command ∈ {apply, check, dry-run}
    # --help

def main(argv: list[str] | None = None) -> int
    # dispatch; unknown command → 2
```

**Инварианты `collect_drift` (каждый пункт — отдельный `Drift`):**

1. Каждая **существующая** копия из `env_files`: `csv_set(TELEGRAM_ALLOWED_CHATS) == csv_set(allowlist_csv)`.
2. `config.yaml` `telegram.allowed_chats` — то же множество (строка или list → `csv_set`).
3. `telegram.require_mention is false`, `telegram.guest_mode is false`.
4. `token_prefix(gateway.telegram.token) == bot.id_prefix` (`863022`).
5. Снимок: ровно `CANON_TOPICS`; `6556 not in values`.
6. Если ключ `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` задан в `$HERMES_HOME/.env` — равен `startup_channels`. Если ключа нет — drift (канон «как было» его имеет). Несуществующий `.env` — drift «file missing», не NPE.
7. **Не** читать `jobs.json`. Наличие `:6556` там не drift.
8. Если существует `hermes_home()/error_bus/_db.py`: regex `TELEGRAM_THREAD_ID\s*=\s*"11112"` и `TELEGRAM_CHAT_ID\s*=\s*"-1004300127777"`. Файла нет (temp-фикстура) — пропуск, не ошибка.
9. `str(Drift)` и `format_drift` не содержат `TOKEN_RE`.

**Не делать в скрипте:** UNION; правка `adapter.py`; `restart_gateway_MANUAL_ONLY.sh`; создание топиков в Telegram; запись `jobs.json` / `sessions.json` / `channel_directory.json`; второй бот в группу; создание отсутствующего профиля `.env`.

**CLI (канон для argparse и SKILL.md):**

| Аргумент | Default | Обязателен | Требование ТЗ |
|---|---|---|---|
| `command` (positional) | нет | да | `apply` \| `check` \| `dry-run` |

Не делать флагов: `--restart`, `--jobs`, `--union`, `--include-6556`, `--profile`.

**Exit codes:** `0` диск = снимок (в т.ч. dry-run без drift; apply+post-check ok); `1` drift; `2` ошибка входа (нет снимка, нет команды, нет `TELEGRAM_BOT_TOKEN` на apply, нет ruamel, битый YAML).

**Куда бэкап:** `$HERMES_HOME/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (на живой машине это `~/.hermes/_Archives/...`). Копировать только три runtime-файла (оба `.env` если есть + `config.yaml`), не весь home. `HF:backup` до impl сделает свой архив; `apply` делает второй — это норма.

**Тесты:** см. `tests/test_restore_telegram_topics.py` ниже.

---

### 4. `/home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery/SKILL.md`

**Назначение.** Человекочитаемое зеркало снимка + **единственная** команда restore в шапке (П.2'). Диагностика причин 1–3 тишины остаётся, но фикс = `apply`, не ручной grep.

**Дельта (не переписывать скилл целиком):**

1. Frontmatter `version: 1.1.0` → `1.2.0`. `description` не раздувать; можно добавить «restore маршрутизации топиков apply\|check\|dry-run». `description` ≤ 1024 символов.
2. Сразу после H1 — блок:

```markdown
## Восстановление маршрутизации топиков

Единая команда (канон id — `references/sirene-workspace-topics.yaml`):

```bash
bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh apply|check|dry-run
```

`dry-run` — diff снимок vs диск, ничего не писать. `apply` — бэкап трёх файлов → allowlist в обе `.env` + unify YAML-токена с `TELEGRAM_BOT_TOKEN` + YAML extras. `check` — exit 0 только если диск = снимок. Скрипт gateway **не** рестартует: после `apply` ждать «поднимай». Не править `.env`/`config.yaml` руками.
```

3. Таблица 8 топиков **остаётся** (те же 8 строк, без `:6556`). Одна фраза над таблицей: «канон thread_id — `references/sirene-workspace-topics.yaml`; таблица — зеркало».
4. Блок «ДВА бота»: после П.2 это **мина прошлого**, не текущий канон. Переписать правило: poller и YAML-токен **должны** быть `TELEGRAM_BOT_TOKEN` / `sirene_vm_bot` / prefix `863022`. Бот prefix `882117` не в группе; `apply` копирует env→YAML. Таблицу «YAML=DM / env=группа» не оставлять как актуальное состояние; можно оставить как «если check показывает prefix 882117 — это drift, лечится apply».
5. В причине (1) и (2) диагностики шаг фикса указывает на скрипт, не на «выровняй `.env` grep'ом» как основной путь.
6. Не копировать ТЗ. Целевой объём — текущий порядок (~150 строк) + ~20 строк шапки restore. Полный токен не писать.

**Сигнатуры:** нет (markdown).

**Тесты:** нет теста «читать SKILL.md как поведение» (запрет change-detector исходника). Косвенно: `check` не зависит от текста скилла. Допустимо: `test_skill_md_points_at_restore_script` — в SKILL.md есть подстрока `restore_telegram_topics.sh` и `apply|check|dry-run` (контракт точки входа, не снимок всего файла).

---

### 5. `/home/tkachenkoav/hermes-workspace/skills/devops/hermes-gateway-setup/SKILL.md`

**Назначение.** П.6': одна строка-указатель, чтобы не плодить третий канон. Live-путь `~/.hermes/skills/devops/hermes-gateway-setup` — симлинк на этот workspace-файл; патч workspace = патч live.

**Место:** сразу под заголовком `### Топики группы «Сирень Workspace»` (таблица из **7** строк **без Errors**).

**Дельта — одна строка.** Таблицу 7 строк **не** переписывать и **не** добавлять Errors:

> Канон топиков (ровно 8, включая Errors=`11112`) — скилл `tutu-telegram-delivery` / `references/sirene-workspace-topics.yaml`. Restore: `scripts/restore_telegram_topics.sh`. Эта таблица — историческое зеркало без Errors; не расширять.

**Не делать:** правка YAML-примера `allowed_chats` в том же разделе (уже совпадает со снимком); запрет cron-рестарта gateway — не трогать; не править `~/hermes-config-repo/...` копию.

---

### 6. `/home/tkachenkoav/hermes-agent/plugins/platforms/telegram/adapter.py` (П.5')

**Назначение.** Один WARNING на `(chat_id, thread_id)` при drop по allowlist. Скрипт restore это **не** повторяет.

**Почему не только `_gate_or_observe`.** На диске 16.09:

- `_gate_or_observe` (~5888) — text/location; при False — `return` без лога (`_handle_text_message` ~5914).
- `_handle_command` (~5924) и `_handle_media_message` (~6224) зовут `_should_process_message` **напрямую**.

Патч только в `_gate_or_observe` оставит silent drop на command/media. Класс бага — allowlist, не «только text». ТЗ называет `_gate_or_observe / reject по allowed_chats`; фактический reject — ветка allowlist в `_should_process_message`. Туда и ставить WARNING: тогда все три пути покрыты. Это не расширение скоупа и не новый helper.

**Место правки:** `_should_process_message`, ветка:

```python
allowed = self._telegram_allowed_chats()
if allowed and chat_id_str not in allowed:
    return guest_mention
```

**Дельта (inline, без нового god-helper и без нового env/ключа):**

```python
allowed = self._telegram_allowed_chats()
if allowed and chat_id_str not in allowed:
    if not guest_mention:
        logger.warning(
            "[%s] Dropped inbound: chat=%s thread=%s not in TELEGRAM_ALLOWED_CHATS "
            "(env, %d ids); YAML extra ignored",
            self.name, chat_id_str, thread_id, len(allowed),
        )
    return guest_mention
```

`thread_id` здесь уже посчитан (`_effective_message_thread_id`). Logger — существующий `logging.getLogger(__name__)` (`plugins.platforms.telegram.adapter`). Rate-limit/кэш пар **не** вводить (вне среза). Полный токен в строку лога не попадает (его там нет).

**Не делать:** лог на любом False гейта (`require_mention`, own message, ignored threads) — только allowlist-miss. Не трогать `_effective_message_thread_id`, `_topic_gates_pass`, `extra_or_secret`, `_extra_str_set`. Не выносить метод в новый sibling (8 строк в существующей ветке). Guest-mention bypass (`guest_mention True`) — без WARNING (это не drop).

**Тесты:** `test_allowlist_env_over_yaml.py` (caplog в тесте 1).

---

### 7. `/home/tkachenkoav/hermes-agent/tests/plugins/platforms/telegram/test_allowlist_env_over_yaml.py`

**Назначение.** 2 инварианта DoD на контракт env-over-YAML через **реальный** `load_gateway_config` + реальный `extra_or_secret` (без мока). Новый файл: `test_telegram_group_gating.py` уже god и по умолчанию ставит `allowed_chats=[]`, пряча env.

**Запреты:** `unittest.mock.patch` на `extra_or_secret` / `gateway.platforms._shared.extra_or_secret`; чтение `.py` исходника; freeze `_config_version`; `sys.platform` patch; живой `~/.hermes/.env`; UNION как «починка» теста 1.

**Фикстура (канон для impl):**

```python
GROUP_ID = "-1004300127777"
DM_ID = "400307920"
YAML_ALLOWLIST = "400307920,-1004300127777"
NARROW_ENV = "400307920"
WIDE_ENV = "400307920,-1004300127777"

@pytest.fixture
def tg_home(tmp_path, monkeypatch) -> Path:
    # hermes_home = tmp_path / ".hermes"; mkdir
    # config.yaml:
    #   telegram:
    #     allowed_chats: "400307920,-1004300127777"
    #     require_mention: false
    #     guest_mode: false
    #   gateway:
    #     telegram:
    #       token: "8821170000:AAFakeYamlTokenValue________"
    # monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    # delenv ВСЕХ TELEGRAM_* (урок test_telegram_group_gating ~569–585;
    #   ambient load_dotenv иначе протечёт)
    # return hermes_home

def _adapter_from_loaded_config():
    # config = load_gateway_config()          # реальный loader
    # tg = config.platforms[Platform.TELEGRAM]
    # extra = dict(tg.extra or {})            # extra ИЗ загруженного конфига
    # НЕ подменять allowed_chats=[] 
    # object.__new__(TelegramAdapter) + поля как test_allowlist_json_adapter._adapter
    #   + _compile_mention_patterns(); _bot = SimpleNamespace(id=999, username="hermes_bot")
    #   platform = Platform.TELEGRAM
    # return adapter

def _group_msg():
    # SimpleNamespace: chat.id=-1004300127777, type="supergroup", is_forum=True,
    #   message_thread_id=6, is_topic_message=True,
    #   from_user.id=111 (≠ bot 999), text="hello", entities=[]

def _dm_msg():
    # chat.id=400307920, type="private", is_forum=False, message_thread_id=None
```

`extra_or_secret` читает env **в момент вызова**, не при load. После `load_gateway_config()` **ещё раз** `monkeypatch.setenv("TELEGRAM_ALLOWED_CHATS", ...)` — защита от `load_dotenv` третьей стороны (комментарий в `test_telegram_group_gating.py` ~589–595). YAML extra при этом остаётся на объекте — это и есть доказательство «env победил YAML».

**Тесты:**

| Тест | Критерий | Fixture |
|---|---|---|
| `test_narrow_env_beats_yaml_group_false_dm_true` | env `TELEGRAM_ALLOWED_CHATS=400307920` + YAML extra с группой → `_should_process_message(group)` is **False**, `(dm)` is **True**; `caplog` WARNING содержит `chat=` и `TELEGRAM_ALLOWED_CHATS` и id группы; `TOKEN_RE` в caplog нет; DM **без** этого WARNING | `tg_home`, caplog |
| `test_wide_env_group_true_no_allowlist_warning` | env с группой + YAML extra с группой → group **True**, dm **True**; WARNING с `TELEGRAM_ALLOWED_CHATS` / `Dropped inbound` **нет** | `tg_home`, caplog |

Это ровно 2 инварианта ТЗ. Третий («check/apply») живёт в скилле, не здесь. Намеренно: если кто-то «починит» гейт UNION yaml∪env — тест 1 красный → **откат**, не ослаблять assert.

Запуск: `scripts/run_tests.sh tests/plugins/platforms/telegram/test_allowlist_env_over_yaml.py` (не голый pytest).

---

### 8. `/home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery/tests/conftest.py` + `test_restore_telegram_topics.py`

**Назначение.** DoD модуля восстановления на temp `HERMES_HOME`. Скилл **не** bundled — CI гермеса этот файл не увидит; гоняет `HF:test` исполнитель. Живой `~/.hermes/.env` не читать и не указывать.

Не класть в `~/hermes-agent/tests/`.

**`conftest.py`:**

```python
@pytest.fixture
def skill_root() -> Path
    # parents[1] от tests/

@pytest.fixture
def isolated_home(tmp_path, monkeypatch) -> Path:
    # home = tmp_path / ".hermes"; mkdir
    # (home / "profiles" / "default").mkdir(parents=True)
    # оба .env: TELEGRAM_ALLOWED_CHATS=400307920
    #          TELEGRAM_BOT_TOKEN=8630220000:AAFakeSireneTokenValue________
    #          # startup ключ ОТСУТСТВУЕТ в одном из тестов и ПРИСУТСТВУЕТ узкий/чужой — см. тесты
    # config.yaml: telegram.allowed_chats с группой; require_mention false; guest_mode false;
    #              gateway.telegram.token: "8821170000:AAFakeYamlTokenValue________"
    # jobs.json: {"jobs":[{"deliver":"telegram:-1004300127777:6556"}]}  # не канон; не drift
    # monkeypatch.setenv("HERMES_HOME", str(home))
    # delenv боевых TELEGRAM_* кроме явно заданных фикстурой
    # НЕ копировать ~/.hermes/.env
    # return home
```

Фейк-токены **только** в temp-фикстуре, префиксы как у боя (`863022` / `882117`), хвост явно `Fake`. Боевой токен в тесты не тащить.

**`test_restore_telegram_topics.py`:**

| Тест | Критерий | Fixture |
|---|---|---|
| `test_snapshot_exactly_eight_topics_no_6556` | `load_snapshot()`: `len(topics)==8`; values == `{1,3,4,5,6,7,11112,8}`; `6556 not in values`; `"Messages" not in keys` | реальный файл скилла |
| `test_snapshot_has_no_token_pattern` | `TOKEN_RE` не матчится на текст снимка | файл снимка |
| `test_check_nonzero_on_narrow_env` | `cmd_check()` != 0 на `isolated_home`; stdout/stderr содержат ключ `TELEGRAM_ALLOWED_CHATS` или `allowed_chats`; **не** содержат полный фейк-токен (`8630220000:AAF` / `8821170000:AAF` целиком). Prefix в drift — можно | `isolated_home` |
| `test_apply_then_check_zero_both_env_copies` | `cmd_apply()` → 0; обе `.env`: `csv_set` содержит `-1004300127777` и `400307920`; `token_prefix(config.yaml gateway.telegram.token)=="863022"`; повторный `cmd_check()` == 0; `TELEGRAM_BOT_TOKEN` в `.env` **не** изменился | `isolated_home` |
| `test_dry_run_writes_nothing` | на выровненном дереве `cmd_dry_run()==0` и mtime `config.yaml` не растёт; на узком — exit==1 и mtime обоих `.env` + `config.yaml` не растут, `_Archives` не появляется | `isolated_home` |
| `test_jobs_json_6556_is_not_drift` | после успешного apply: `jobs.json` всё ещё содержит `:6556`; mtime не вырос от `cmd_check()`; `cmd_check()==0`; в drift-выводе нет `6556` / `jobs.json` | `isolated_home` |
| `test_apply_does_not_create_missing_profile_env` | нет `profiles/default/.env` → apply не создаёт его; пишет существующий `$HERMES_HOME/.env`; exit 0 если единственная копия выровнена (отсутствие второй — warning, не fail, **если** файла не было; если файл был узкий — fail). Зафиксировать: **отсутствие** второй копии = warning + не drift-fail; **существование узкой** второй копии = drift/apply target | tmp_path вариант |
| `test_script_source_has_no_getupdates_and_no_jobs_write` | исходник `.py`+`.sh` не содержит `getUpdates`, `restart_gateway`, `jobs.json` write (подстрока `jobs.json` как путь записи; чтение тоже запрещено — grep `jobs.json` пусто) | файлы исходников |
| `test_no_home_tkachenkoav_in_scripts` | нет `/home/tkachenkoav` в `scripts/` | grep |

Не делать: live Telegram; assert точного текста drift-строки как snapshot (только: non-zero / ключ присутствует / токен отсутствует / 6556 отсутствует).

Запуск HF:test:

```
cd /home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery
/home/tkachenkoav/hermes-agent/.venv/bin/python -m pytest tests/test_restore_telegram_topics.py -q
```

(в команде запуска абсолютный путь к venv допустим; в **исходниках скилла** литерал `/home/tkachenkoav` запрещён.)

---

## Порядок операций с критериями проверки

Порядок = ТЗ «Шаги реализации» + П.1'–П.7'. Исполнитель (`HF:impl`) идёт сверху вниз и отмечает чекбоксы «Прогресс выполнения». Промежуточные точки — молча, без отчёта Саше. `HF:test` гоняет pytest скилла + `scripts/run_tests.sh` на in-tree файл. Этап 7 (E2E) — только после «поднимай». Этап 8 — оркестратор, не исполнитель.

Общий критерий каждого этапа: тесты **этого** этапа зелёные; grep-инварианты (нет полного токена в снимке/stdout, нет `6556` в снимке, нет `getUpdates` в скрипте, `extra_or_secret` не изменён) держатся с этапа 1.

До первой строки кода: `GATE:plan-approve` снят + `HF:backup` трёх runtime-файлов в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`. Без гейта и бэкапа `apply` на живом диске не запускать.

### Этап 1 — П.1' снимок YAML

**Сделать:** `references/sirene-workspace-topics.yaml` с полями таблицы §1. Каталог `references/` создать. Не запускать apply. Не трогать `.env`.

**Критерий готовности:**

- Файл есть; `yaml.safe_load` → `len(topics)==8`; values `{1,3,4,5,6,7,11112,8}`.
- `rg '6556|Messages'` по снимку пусто.
- `TOKEN_RE` по снимку пусто.
- `bot.id_prefix == "863022"`; `error_bus.thread_id == 11112`; `allowlist_csv` без пробелов.

### Этап 2 — скрипт `apply|check|dry-run` (без live-записи)

**Сделать:** `restore_telegram_topics.py` + `.sh` с сигнатурами §3. Не вызывать `cmd_apply()` против живого `~/.hermes`.

**Критерий:**

- `bash scripts/restore_telegram_topics.sh` без argv → exit 2 + usage.
- `--help` → 0.
- Функции импортируются из тестов через `sys.path`.
- Исходник без `getUpdates` / `jobs.json` / `/home/tkachenkoav`.

### Этап 3 — SKILL.md + указатель gateway-setup

**Сделать:** дельты §4 и §5. Не раздувать таблицу gateway-setup до 8 строк.

**Критерий:**

- В `tutu-telegram-delivery/SKILL.md` есть команда `restore_telegram_topics.sh apply|check|dry-run` в шапке; таблица топиков = 8 строк снимка; version 1.2.0.
- В `hermes-gateway-setup/SKILL.md` ровно одна новая строка-указатель под заголовком топиков; таблица по-прежнему 7 строк без Errors.
- Фикс тишины в диагностике указывает на `apply`, не на «почини grep'ом» как основной путь.

### Этап 4 — pytest скрипта (`HF:test` часть A)

**Сделать:** `tests/conftest.py` + `test_restore_telegram_topics.py`. Гонять на temp `HERMES_HOME`.

**Критерий:** таблица §8 зелёная, в том числе:

- `check` ≠ 0 на узком `.env`; = 0 после `apply`.
- обе копии `.env` с группой после apply.
- полный фейк-токен в выводе check/apply/dry-run отсутствует.
- `:6556` в `jobs.json` не drift; `jobs.json` не переписан.

### Этап 5 — П.5' WARNING + in-tree тесты (`HF:test` часть B)

**Сделать:** патч `adapter.py`; создать `test_allowlist_env_over_yaml.py`.

**Критерий:**

- `scripts/run_tests.sh tests/plugins/platforms/telegram/test_allowlist_env_over_yaml.py` зелёный.
- Тест 1: group False, dm True, WARNING на группу, не на DM.
- Тест 2: group True, allowlist-WARNING нет.
- `gateway/platforms/_shared.py` `extra_or_secret` без diff.

### Этап 6 — live dry-run / apply / check

**Сделать:** только после этапов 1–5 и `HF:backup`.

```
bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh dry-run
bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh apply
bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh check
```

На состоянии 16.09 `dry-run` **обязан** показать drift: allowlist обеих `.env` без группы; YAML-токен prefix `882117` ≠ `863022`. Exit ≠ 0. Полного токена в выводе нет.

**Критерий:**

- `check` exit 0 на живом диске.
- `rg '^TELEGRAM_ALLOWED_CHATS='` обе копии содержат `-1004300127777`.
- `hermes config get gateway.telegram.token` — prefix `863022` (полный токен **не** копировать в отчёт/git/чат).
- `TELEGRAM_BOT_TOKEN` в `.env` не изменился (тот же prefix `863022`).
- Скрипт напечатал про рестарт и **не** рестартнул gateway.

**Стоп.** Без «поднимай» этап 7 не начинать. Inbound без рестарта не оживёт (dotenv на старте процесса).

### Этап 7 — рестарт + E2E (не pytest)

**Не автоматизировать в pytest.** После явного «поднимай»: Саша (или оператор по его команде) запускает `bash ~/.hermes/scripts/restart_gateway_MANUAL_ONLY.sh` из **внешнего** шелла. Исполнитель cron-рестарт не ставит.

Чеклист:

1. Сообщение в топик Backlog (`thread_id=6`) **без** `@mention`.
2. В `~/.hermes/logs/gateway.log`: `inbound message:` с `chat=-1004300127777`.
3. Ответ бота в том же `message_thread_id` (=6).
4. DM `400307920` отвечает (нет регрессии).
5. Опционально: `getChatMember` poller-бота = member/administrator; `sendMessage` в Errors `:11112` с `TELEGRAM_BOT_TOKEN` → `ok:true`.
6. **Не** вызывать ручной `getUpdates` на токене poller (409).

**Критерий:** пункты 1–4. Тишина группы при `check` 0 → не этот баг (смотреть 409/членство), не «доделывать forum».

### Этап 8 — `ORCH:shared-state`

**Не делать на HF:impl / HF:test / HF:plan.** Оркестратор: `restore-all-skills.sh`; промоут `tutu-telegram-delivery` в `~/hermes-workspace/skills/devops/` (сейчас скилла там нет — иначе следующий restore не подхватит модуль). Манифест / `jobs.json` / `EcosystemManifest.json` / `MAIN_TZ_INVENTORY.md` исполнителю не дублировать. Кроны не создавать.

---

## Промежуточные точки

Исполнитель проходит молча. Каждая точка — бинарная. Сбой → стоп этапа, не перескакивать к live-`apply` «чтобы группа заговорила».

| ID | Когда | Проверка | Fail → |
|---|---|---|---|
| T1 | конец этапа 1 | 8 топиков; нет `6556`; нет `TOKEN_RE` в снимке | не писать скрипт |
| T2 | конец этапа 2 | `--help` 0; без argv 2; grep нет `getUpdates`/`jobs.json` | не править SKILL.md |
| T3 | конец этапа 3 | одна команда restore в шапке; gateway-setup таблица всё ещё 7 строк | не live-apply |
| T4 | конец этапа 4 | pytest скилла зелёный; check≠0 на узком; 0 после apply; токен не печатается; 6556 не drift | не патчить адаптер |
| T5 | конец этапа 5 | `scripts/run_tests.sh` 2 инварианта green; `extra_or_secret` без diff | не live-apply |
| T6 | этап 6 dry-run live | exit≠0; drift allowlist+prefix; нет полного токена | не apply |
| T7 | этап 6 apply+check | exit 0; обе `.env` с группой; YAML prefix `863022` | откат runtime из `_Archives` |
| T8 | этап 7 | inbound `:6` + reply thread + DM жив | не forum-патч; смотреть 409/членство |
| T9 | всегда | нет USERTOOLS-пакета, нет правки `jobs.json`, нет UNION, нет рестарта из скрипта | откат по разделу ниже |
| T10 | всегда | in-tree diff только `adapter.py` + `test_allowlist_env_over_yaml.py` | не коммитить `.env`/`config.yaml` |

Точка **диск-факт premature-impl** относится к `HF:plan`/`REV:plan`, не к исполнителю: на момент этого плана в скилле **только** `SKILL.md`. Если к старту `HF:impl` уже появятся `scripts/`/`references/`/`tests/` не из этого плана — сверить с § Файлы, не плодить второй модуль; неожиданный код до `GATE:plan-approve` — аномалия канбана, не «дописать».

---

## Тесты и fixture (сводка DoD)

**Команды `HF:test`:**

```
# A. скилл (temp HERMES_HOME внутри тестов)
cd /home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery
~/hermes-agent/.venv/bin/python -m pytest tests/test_restore_telegram_topics.py -q

# B. ядро (CI-parity)
cd /home/tkachenkoav/hermes-agent
scripts/run_tests.sh tests/plugins/platforms/telegram/test_allowlist_env_over_yaml.py
```

Маркер `@pytest.mark.live` не вводить — живой E2E ручной (этап 7).

### Матрица покрытия

| Требование ТЗ / DoD | Тест | Где |
|---|---|---|
| env-over-YAML: узкий env → group False, private True | `test_narrow_env_beats_yaml_group_false_dm_true` | in-tree |
| после apply/широкого env → group True | `test_wide_env_group_true_no_allowlist_warning` | in-tree |
| WARNING на silent drop (chat, thread), не тишина | caplog в тесте 1; нет WARNING на DM | in-tree |
| не мокать `extra_or_secret`; real `load_gateway_config` | оба in-tree теста | in-tree |
| `check` ≠ 0 на узком `.env` | `test_check_nonzero_on_narrow_env` | скилл |
| `check` = 0 после `apply` | `test_apply_then_check_zero_both_env_copies` | скилл |
| `check` не печатает полный токен | те же + redact | скилл |
| снимок ровно 8 без `:6556` | `test_snapshot_exactly_eight_topics_no_6556` | скилл |
| `:6556` в `jobs.json` не drift | `test_jobs_json_6556_is_not_drift` | скилл |
| обе копии `.env` с группой | `test_apply_then_check_zero_both_env_copies` | скилл |
| YAML token prefix `863022` после apply | тот же | скилл |
| dry-run ничего не пишет | `test_dry_run_writes_nothing` | скилл |
| Errors=11112 в снимке | `test_snapshot_*` + поле `error_bus.thread_id` | скилл |
| нет `getUpdates` / записи `jobs.json` | `test_script_source_has_no_getupdates_and_no_jobs_write` | скилл |

---

## Процедура отката

1. **Откат незавершённого `HF:impl` (скилл частично создан, live `.env` ещё не писали):**  
   удалить только новые пути  
   `references/`, `scripts/`, `tests/`  
   внутри `/home/tkachenkoav/.hermes/skills/devops/tutu-telegram-delivery/`.  
   `SKILL.md` вернуть к содержимому до правки (из git workspace **нет** — скилл не в hermes-agent; взять из `HF:backup` / копии до impl). Не удалять сам каталог скилла и не трогать чужие скиллы.

2. **Откат указателя gateway-setup:** revert одной строки в  
   `/home/tkachenkoav/hermes-workspace/skills/devops/hermes-gateway-setup/SKILL.md`  
   (таблица 7 строк должна остаться как была).

3. **Откат in-tree:** `git checkout -- plugins/platforms/telegram/adapter.py` и удалить  
   `tests/plugins/platforms/telegram/test_allowlist_env_over_yaml.py`  
   если файл создан этим проходом. Не revert'ать чужие коммиты.

4. **Откат runtime после `apply`:** восстановить три файла из  
   `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`  
   (архив `HF:backup` **или** архив, который создал сам `apply` — более поздний, если apply уже испортил). Затем рестарт только по «поднимай». Не `VACUUM`, не трогать `state.db`.

5. **Откат тестовых артефактов:** `tmp_path` pytest сам; не оставлять фейк-токены в Inbox / WorkVault.

6. **Что откатывать нельзя и не нужно:** `jobs.json` (мы его не пишем — если изменился, это дефект impl → стоп, не silent revert чужого). Код ErrorBus. `extra_or_secret`. Forum-хелперы. `sessions.json` / `channel_directory.json`.

7. **Откат этой фазы `HF:plan`:** удалить только  
   `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/TelegramGroupTopics/HF-plan_telegram-group-topics_20260916.md`  
   Master-ТЗ и диагноз не откатывать.

8. **После `ORCH:shared-state` (будущее):** откат = оркестратор убирает копию в `hermes-workspace` + restore. Исполнитель это не планирует как свой шаг.

Retention архивов Hermes — 2 недели, к этому плану не относится.

---

## Что НЕ трогать

Сводка ТЗ «Не делать лишнего» + П.7' + граница фазы.

**Контракт и ядро**

- `gateway/platforms/_shared.py` `extra_or_secret`, `yaml_env_setter` (`3dedb71f2f`, #108440). Не UNION yaml∪env.
- `adapter.py` `_effective_message_thread_id`, `_topic_gates_pass`, session keys, `_handle_polling_conflict`, `drop_pending_updates`.
- Forum-роутинг, prune `sessions.json`, `multiplex_profiles`.
- Новый core tool / `HERMES_*` / plugin / MCP / второй адаптер / `guest_mode` как способ «включить группу».

**Runtime и соседи**

- `~/.hermes/cron/jobs.json` (включая `:6556` / Messages — не в снимок, не удалять, не «вычищать»).
- `channel_directory.json` / `sessions.json` как «бэкап топиков».
- `~/USERTOOLS/**`, код ErrorBus (`_db.py` только read-сверка `:11112`).
- `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS` как inbound-allowlist.
- Ручной `getUpdates` на токене poller; вызов Telegram API из скрипта.
- Gateway из `TZ:*` / из скрипта / cron-рестарт (`restart_gateway_MANUAL_ONLY.sh` только по «поднимай» из внешнего шелла).

**Секреты**

- Полные токены в ТЗ/плане/снимке/логах/stdout check/git/чате. Только prefix.
- Не коммитить `.env` / `config.yaml` в `hermes-agent`.

**Фаза и пайплайн**

- `HF:plan` не создаёт `scripts/`/`references/`/`tests/` скилла, не патчит `adapter.py`, не пишет `.env`.
- `HF:impl` не пишет `EcosystemManifest.json`, `MAIN_TZ_INVENTORY.md`, не гоняет `restore-all-skills.sh`.
- Не создавать второй скилл / пакет `TelegramGroupTopics` в `~/USERTOOLS/`.
- Не править `TelegramGroupTopics_TZ.md` и `_fix_plan_20260916.md` в этой фазе.
- Не создавать второй файл плана в `~/hermes-agent/` — канон пути задан промптом фазы (этот файл).

**П.7' (явный список «не делать» как этап без файлов)**

Forum, UNION, cron, `getUpdates`, правка `jobs.json`, новый пакет. Исполнитель сверяет grep'ом на T2/T9, отдельного кода не пишет.

---

## Риски

| Риск | Почему вероятен | Смягчение в реализации |
|---|---|---|
| PyYAML dump всего `config.yaml` | файл ~1000 строк с комментариями | только `ruamel.yaml` round-trip точечных ключей; нет ruamel → exit 2, не dump |
| `apply` создаёт `profiles/default/.env` с нуля | «чтобы обе копии были» | не создавать; нет файла → warning; узкий существующий → писать |
| Рестарт из скрипта | «подключил → заработало» без «поднимай» | запрет; обязательная печать; инвариант hermes-gateway-setup |
| Тест адаптера без `delenv TELEGRAM_*` | ambient `.env` / `load_dotenv` Teams | delenv всех `TELEGRAM_*` + setenv **после** `load_gateway_config`; `scripts/run_tests.sh` |
| Хардкод `~/.hermes` в скрипте | temp `HERMES_HOME` умрёт | только `hermes_home()` / `$HERMES_HOME` |
| Коммит боевого `config.yaml` / `.env` | привычка «зафиксировать фикс» | in-tree только `adapter.py` + тест |
| `check` читает `jobs.json` | «полный аудит топиков» | grep-запрет; тест 6556 не drift |
| Два канона (скилл vs снимок) | таблица скилла разъедется | SKILL.md явно «зеркало»; id только в YAML |
| Третий канон в gateway-setup | «добавим Errors в таблицу» | одна строка-указатель; таблицу 7 строк не расширять |
| WARNING только в `_gate_or_observe` | буквальное чтение ТЗ | ставить в `_should_process_message` (общая ветка reject) |
| UNION «чтобы тест 1 позеленел» | желание «YAML тоже должен работать» | тест 1 обязан остаться False; красный → откат |
| Скилл только в `~/.hermes/skills`, нет в workspace | `restore-all-skills.sh` его не подхватит | ORCH промоутит в workspace; impl пишет в TZ-дом |
| «Подключил модуль» без рестарта | dotenv на старте | скрипт печатает факт; E2E не начинать до «поднимай» |
| Dual-token 882117 снова в YAML | миграция/апдейт ядра | `check` ловит prefix; `apply` копирует env→YAML |
| П.1 включает ответы во **все** топики | `require_mention: false` — так было до 13:11 | не вводить `allowed_topics` этим проходом |

Крупное отклонение (новый скилл, USERTOOL, UNION, правка forum, крон, `jobs.json`) → исполнитель стоп, архитектор доплан. Мелкое (имя внутренней функции, порядок import) — сам.

---

## Прогресс выполнения

Дублирует чекбоксы после заголовка, чтобы хвост файла оставался источником статуса при сбое чтения середины.

- [ ] **Этап 1.** П.1' — YAML-снимок (ровно 8, без `:6556`, без секретов)
- [ ] **Этап 2.** Скрипт `apply\|check\|dry-run` (без live-записи)
- [ ] **Этап 3.** SKILL.md + указатель `hermes-gateway-setup`
- [ ] **Этап 4.** Pytest скрипта на temp `HERMES_HOME`
- [ ] **Этап 5.** WARNING в `adapter.py` + 2 инварианта `scripts/run_tests.sh`
- [ ] **Этап 6.** Live `dry-run` → `apply` → `check`
- [ ] **Этап 7.** Рестарт по «поднимай» + E2E `:6`
- [ ] **Этап 8.** `ORCH:shared-state` (не сейчас)

Следующая фаза канбана после этого файла: `REV:plan`, затем `GATE:plan-approve`. Код — только после снятия гейта и `HF:backup`, исполнитель `composer-2.5`, фаза `HF:impl`.
