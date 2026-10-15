---
tool: MoveFromKeyTalk
version: 0.1.0
date: 2026-10-15
status: draft
last-section-added: "v0.1.0 TZ:finalize DEV/movefromkeytalk после REV:tz APPROVE — канон + инвентарь; Q-1…Q-5 открыты (блокеры HF:impl)"
---

# MoveFromKeyTalk — ТЗ

выжимка ≠ SoT; при расхождении — открыть master.

Автор: архитектор (Cursor, фазы `TZ:patch` → `TZ:finalize`, кейс DEV).  
Пакет: `dev/movefromkeytalk`. Код на TZ-WRITE **не** пишется.

## §1 Назначение

Новый USERTOOL. Тянет **сырые транскрипты** встреч из корпоративного ВКС **Контур.Толк (KTalk)**, саммеризирует **нашим** промптом (`Registries/prompts/ff_summary.json`, тот же, что Fireflies Custom AI Skill `tkachenkoav ff summary prompt 01072026` / `app_id=6a44d3b85f38b61f42f21cf2`) и кладёт markdown в `WorkVault/Meetings/NewMeetings/` в формате, который уже едят **MoveFromFF → MOFS → ProtocolFromSummary → Confluence**.

Имя инструмента `MoveFromKeyTalk` — слаг Саши (`movefromkeytalk`). Продукт API — Контур.Толк. «Gitalk» в брифе = оговорка того же KTalk, не отдельный сервис.

Цепочка после записи файлов **не меняется**: PFS публикует протокол, MOFS размечает сущности. Этот инструмент **не** публикует в Confluence сам.

## §2 Reuse-first — что уже есть / почему не закрывает

| Уже есть | Что закрывает | Почему не закрывает этот бриф |
|---|---|---|
| **MoveFromFF** | Fireflies GraphQL → `NewMeetings/* - {transcript\|summary}.md` + `_registry_meet.json` | Другой источник (не FF). Патч MFF под второй API смешает backoff/дедуп/custom-skill-retry и ломает «не трогать» MFF. |
| **FirefliesAutojoin** | Зовёт бота Fred в Zoom | Не транскрипт, не саммари, не диск. |
| **ProtocolFromSummary** | `NewMeetings/* summary.md` → Confluence | Потребитель, не источник. `_gen_ff_summary.py` — ad-hoc обход пустого FF custom-skill, не крон и не KTalk-клиент. |
| **MarkObjectsFromSummary / MofsIndex** | Разметка и индекс уже лежащих файлов | Не ходят в ВКС. |
| **IDEA `ff-summary-generator`** (`t_609e8869`) | Самаризатор FF-транскриптов + `get_llm("ff_summarizer")` | RESEARCH, не код. Промпт и слот LLM **переиспользуем**; отдельный USERTOOL-саммаризатор не заводим. |
| **`Registries/prompts/ff_summary.json` v0.2.0** | Канон секций Участники / Обсудили / Решения / Блокеры / Задачи / Риски | **Reuse.** Форк промпта запрещён. |
| **ktalk-cli (PyPI)** | Справочник путей KTalk (`list-recordings`, `transcript`, `X-Auth-Token`) | Runtime-зависимость **нет**: Python ≥3.12, свой SQLite-реестр, session-token. У нас боевой контур 3.11 + свой реестр как MFF. Клиент — свой HTTP. |
| **EcosystemConfig / `usertools_config`** | Единый несекретный конфиг | **Reuse.** Новый tool сразу `unified_only` (Eco §10.4). |
| **ErrorBus** | `error_bus_wrap.sh` | **Reuse.** Mode B на крон. |

**Вывод:** новый инструмент в семействе `MoveFrom*`. Файловый контракт и промпт — reuse. Код MFF/PFS/MOFS/FF-Autojoin **не** расширять.

## §3 Место в экосистеме

```
Контур.Толк (KTalk REST)
        │  сырой транскрипт + метаданные
        ▼
MoveFromKeyTalk  ── LLM(ff_summary.json) ──► NewMeetings/
        │                                      ├─ YYYY-MM-DD HH-MM-SS Title - transcript.md
        │                                      └─ YYYY-MM-DD HH-MM-SS Title - summary.md
        │
        ├── собственный реестр (не _registry_meet.json)
        └── PFS / MOFS / MofsIndex  (без правок)
                    │
                    ▼
            Confluence протоколы  +  Entities
```

Параллель с Fireflies: MFF продолжает тянуть FF. Оба пишут в одну папку. Дедуп двух источников — §10.

## §4 Идентичность продукта и ключ пользователя

| Имя в брифе | Канон в этом ТЗ |
|---|---|
| KeyTalk | имя USERTOOL / слаг `MoveFromKeyTalk` |
| Gitalk | не сущность; синоним-оговорка KTalk |
| Контур.Толк / KTalk | внешнее приложение, REST `https://<domain>.ktalk.ru` |
| `talkusr.c1e5…` | публичный user-key владельца записей (`KTALK_USER_KEY`). **Не секрет.** Полное значение — Q-2. |

Авторизация крона: **персональный API-ключ** заголовком `X-Auth-Token` (не session cookie, не ключ пространства `X-API-Key`). Секрет: `KTALK_PERSONAL_API_KEY` только в shared `~/.config/hermes/.env`. Scope минимум `application.recording.read`.

Справочник путей (ktalk-cli, не копировать пакет):

| Метод | Путь | Зачем |
|---|---|---|
| GET | `/api/Domain/recordings/v2` | список записей окна |
| GET | `/api/Recordings/{recordingKey}` | метаданные |
| GET | `/api/recordings/{recordingKey}/transcript` | сырой транскрипт |
| GET | `/api/Recordings/{recordingKey}` + participants endpoint | полный состав (лимит 6 в list) |

**Запрет:** `GET .../summary` и `.../summary/{type}` как содержимое нашего `summary.md`. Саммари KTalk не канон.

Видеофайл, чат, архив reporting, создание встреч — вне скоупа.

## §5 Scope / Non-goals

**В скоупе v0.1:**

- Крон `no_agent` + ручной CLI (`cron` / `manual` / `test` / `dry-run`).
- Список записей умного окна, pending-backoff пока нет транскрипта.
- Саммаризация `ff_summary.json` v0.2.0 через Hermes LLM.
- Атомарная запись пары файлов в `NewMeetings/` (имена как MFF § filename).
- Свой реестр + TG stale-алерт по образцу MFF.
- Дедуп «уже есть файл FF на ту же встречу» (§10).
- Конфиг `unified_only`, секреты только shared `.env`.
- Тесты по шаблону MFF + контракт PFS-парсера.
- Тонкий скилл ручного синка.
- ErrorBus wrap крона.

**Non-goals:**

- Правки MoveFromFF / PFS / MOFS / FirefliesAutojoin / `ff_summary.json` / `_registry_meet.json`.
- Публикация в Confluence, TaskRefresh, promote.
- Runtime-зависимость `ktalk-cli`.
- Per-tool `.env`, dual-read, литералы путей.
- Скачивание видео, чат KTalk, планирование встреч.
- Реализация IDEA `ff-summary-generator` как отдельного инструмента.
- Gateway, `jobs.json` (крон — только по «ставь кроны»), ядро Hermes.

## §6 Архитектура

Два слоя, как LoopChannelDigest / MFF:

1. **CLI-пакет** `~/USERTOOLS/MoveFromKeyTalk/` — детерминированный Python (HTTP + реестр + запись файлов) + один вызов LLM на готовую расшифровку.
2. **Скилл** `productivity/move-from-keytalk` — триггеры и вызов CLI, без HTTP-логики.

Крон: обёртка `movefromkeytalk_sync.sh` → `venv/bin/python -m movefromkeytalk --mode cron`, `no_agent=true`, `error_bus_wrap.sh --tool MoveFromKeyTalk`. LLM-агент вокруг синка **запрещён** (урок MFF §3A).

Интерпретатор: свой venv (3.11, как MFF), не Hermes 3.14. Battle-interpreter регистрирует ORCH (не эта фаза).

## §7 Алгоритм синхронизации

Образец — MoveFromFF v2.1 шаги 1–4, плюс шаг LLM.

### Шаг 0. Preflight

flock; `usertools_config.load_tool_config("move_from_keytalk")`; секреты из shared `.env`; mkdir `NewMeetings/` + `state/`; нет ключа → fail loud (не silent).

### Шаг 1. Ping

Лёгкий запрос списка `top=1`. 401 → ошибка ключа. 403 → scope. Exit 3.

### Шаг 2. Умное окно

| mode | from | to |
|---|---|---|
| `test` | now − 5 суток | now |
| `manual` | `--from` / `--to` | как задано |
| `cron` | `max(last_synced_at, now − 24ч)`; первый запуск: now − 4ч30мин | now |

Список: `start-from` / `start-to`, пагинация `page-token`, `top` ≤ 100.

Фильтр: записи, видимые ключу; если задан `KTALK_USER_KEY` — только записи этого пользователя (автор/организатор). Пустой ключ до ответа Q-2 = не фильтровать по user-key, только то, что отдаёт персональный API-ключ.

### Шаг 3. На каждую запись `recording_key`

1. Свой реестр `completed` → `meeting_skipped`.
2. Свой `pending` и `now < next_retry_at` → `meeting_backoff`.
3. `attempts >= MAX_PENDING_ATTEMPTS` → `error`, `notify_meeting_stale`, skip.
4. §10: если в `NewMeetings/` уже есть пара/summary MFF на ту же встречу → `meeting_ff_exists`, статус `skipped_ff`, файлы **не** писать.
5. `GET` metadata + transcript. Нет реплик / пустой transcript → pending backoff как MFF (`PENDING_BACKOFF_MINUTES`, `MAX_PENDING_ATTEMPTS=12`).
6. LLM: тело `ff_summary.json` + транскрипт (паттерн `_gen_ff_summary.py`, не копировать скрипт PFS в runtime). Таймаут/пусто → pending, файл не писать.
7. Атомарно `write_meeting_files` (rollback при ошибке). Статус `completed`. `summary_format=custom`.

Встроенное саммари KTalk **не** fallback содержимого. Fallback «FF bullet_points» **не** использовать: у KTalk нет FF-overview.

### Шаг 4. Финализация

При `not dry_run` и `errors==0` и не точечный `--recording-key`: `last_synced_at = to`. Атомарный save реестра. Лог `run_summary`.

Константы backoff — как MFF §5 (копия значений, не import `movefromff`).

Коды лога: `meeting_skipped`, `meeting_backoff`, `meeting_pending`, `meeting_stale`, `meeting_ff_exists`, `download_ok`, `download_error`, `summarize_error`.

Exit: 0 успех; 1 частичный; 2 lock/preflight; 3 API недоступен; 4 фатально.

## §8 Формат файлов (контракт PFS/MOFS)

Канон имён — `MoveFromFF/movefromff/filename.py`:

```
YYYY-MM-DD HH-MM-SS <Title> - transcript.md
YYYY-MM-DD HH-MM-SS <Title> - summary.md
```

- Дата/время **UTC** (PFS сам переводит в МСК).
- Санитизация Windows-invalid, non-BMP, лимит **180 байт UTF-8** (ownCloud).
- Regex потребителя: `protocolfromsummary/summary_parser.py::_FILENAME_RE` — пробел перед `summary`, не слитно.

`summary.md` — как `summary_custom.md.j2`:

```
# Саммари: <Title>

Участники:
- …

Обсудили:
- …

Решения:
- …

Блокеры:

Задачи:
- …

Риски:
```

Заголовки секций — **ровно** `_SECTION_NAMES` = `["Участники", "Обсудили", "Решения", "Блокеры", "Задачи", "Риски"]`. Markdown `##` у секций **не** ставить (промпт явно запрещает). YAML-frontmatter MOFS **не** писать: его пишет MOFS после появления файла.

`transcript.md` — заголовок, дата UTC, длительность, участники, `Meeting ID: <recording_key>`, затем реплики `HH:MM:SS **Спикер:** текст`.

`meeting_id` для PFS = stem файла (как сейчас). Стабильный ключ нашего реестра = `recording_key` KTalk (не ULID Fireflies).

## §9 Свой реестр

Путь: `~/USERTOOLS/MoveFromKeyTalk/state/_registry.json` (не vault, не `_registry_meet.json`).

`schema_version: "1.0"`. Поля записи: `recording_key`, `title`, `meeting_date`, `duration_minutes`, `participants`, `files`, `status`, `attempts`, `next_retry_at`, `first_seen_at`, `summary_format`, `ff_skip_reason`.

Статусы: `pending` | `completed` | `error` | `skipped_ff`.

Атомарная запись tmp+replace. MFF `reconcile` / `detect_and_mark_duplicates` этот реестр **не** читают и файлы MFKT **не** удаляют (удаляют только `rec.files` своих записей).

## §10 Дедуп с Fireflies (два источника → одна папка)

Правило skip (все три):

1. Нормализованный `title` (strip, как MFF).
2. `|Δ meeting_date| ≤ 10 мин` (`DEDUP_TIME_THRESHOLD_MIN=10`).
3. Пересечение участников (email или ФИО). Пустой список у одной стороны = пересечение считается.

Ищем **существующие** `* - summary.md` в `NewMeetings/`, не записи `_registry_meet.json` (MFF-реестр не читаем, чтобы не стать вторым писателем).

Совпадение → не пишем файлы, `skipped_ff`. Иначе пишем — PFS увидит новую встречу.

Смена правила (всегда писать дубль / всегда побеждает KTalk) — только `TZ:patch` после Q-3.

## §11 Саммаризация

| | |
|---|---|
| Промпт | `/home/tkachenkoav/WorkVault/Registries/prompts/ff_summary.json` (`id=ff_summary`, `version=0.2.0`) |
| Транспорт | OpenAI-совместимый клиент к ТУТУ-шлюзу, как PFS §30 |
| Модель | Hermes `config.yaml` `model.default` / `model.provider`; override только `tools.move_from_keytalk.llm` или process env |
| Last-resort | те же `LLM_FALLBACK_*`, что PFS; `ANTHROPIC_API_KEY` не читать |
| Слот Eco `get_llm("ff_summarizer")` | **не** плодить ключ `tools.ff_summarizer` в YAML; этот tool — потребитель того же промпта |

Промпт на диск **не** копировать в USERTOOLS. Смена шаблона = правка канона `ff_summary.json` отдельным CHANGE, не этот DEV.

Пустой раздел = заголовок без буллитов (норма промпта). Пустой ответ LLM целиком = ошибка, pending.

Лимит транскрипта: чанкинг по границам реплик (ориентир ktalk-cli 30000 симв) → один вызов, если влезает; иначе последовательная суммаризация частей + финальный merge тем же промптом. Детали IAC на `HF:plan`.

## §12 Конфиг — unified_only с волны 0

Ключ манифеста: `move_from_keytalk` (snake, не имя папки).

Несекреты — только `EcosystemConfig.yaml` `tools.move_from_keytalk` + `shared.WORKVAULT_PATH`. Новый ключ **сначала** в `EcosystemConfig.schema.json`.

| Ключ YAML | Назначение |
|---|---|
| `enabled` | bool |
| `TOOL_DIR` | `~/USERTOOLS/MoveFromKeyTalk` |
| `LOGS_PATH` | `~/WorkVault/_meta/MoveFromKeyTalk` |
| `MEETINGS_DIR` | `~/WorkVault/Meetings/NewMeetings` (тот же каталог, что PFS) |
| `KTALK_BASE_URL` | origin без path, Q-1 |
| `KTALK_USER_KEY` | `talkusr.…`, не секрет, Q-2 |
| `PROMPT_PATH` | `~/WorkVault/Registries/prompts/ff_summary.json` |
| `TELEGRAM_CHAT_ID` | stale-алерт; reuse значения MFF `400307920`, не плодить второй чат |
| `llm` | optional override |

`WORKVAULT_PATH` в `tools.move_from_keytalk` **не** дублировать.

Секреты (имена с `API_KEY`/`TOKEN` в YAML схема отвергнет):

| Env | Где |
|---|---|
| `KTALK_PERSONAL_API_KEY` | shared `.env` |
| `TELEGRAM_BOT_TOKEN` | уже есть |
| LLM key | как PFS (`LLM_FALLBACK_*` / провайдер yaml) |

Per-tool `.env` **не** создавать. Dual-read **запрещён**. `migration_status: unified_only` пишет **ORCH:shared-state**, не архитектор и не исполнитель на `HF:impl`.

## §13 CLI

```text
python -m movefromkeytalk --mode cron|manual|test
    [--from ISO] [--to ISO]
    [--recording-key KEY]
    [--dry-run]
    [--no-tg]
```

`--mode cron` игнорирует from/to (умное окно). `--recording-key` — точечная догрузка, `last_synced_at` не двигать.

## §14 Дерево и тесты

```
USERTOOLS/MoveFromKeyTalk/
  movefromkeytalk/
    __init__.py
    __main__.py
    config.py          # usertools_config, fail loud
    ktalk_client.py    # httpx+retry; не ktalk-cli
    filename.py        # копия контракта MFF, не import movefromff
    registry.py
    writer.py          # atomic tmp+replace, rollback
    summarizer.py      # ff_summary.json + LLM
    dedup_ff.py        # §10 по файлам NewMeetings
    tg.py
    lock.py
    logger.py
  tests/
    test_filename.py           # regex = PFS _FILENAME_RE
    test_registry.py
    test_pending_backoff.py
    test_ktalk_client.py       # mock HTTP
    test_summarizer.py         # mock LLM, секции _SECTION_NAMES
    test_dedup_ff.py
    test_writer.py
    test_config_unified.py     # нет local .env; секрет не в YAML
  bin/movefromkeytalk_sync.sh
  pyproject.toml
  README.md
```

venv свой. Скилл: `hermes-workspace/skills/productivity/move-from-keytalk/SKILL.md` + `restore-all-skills.sh` на ORCH.

Тесты: pytest offline, без живого KTalk/LLM. Контракт имени: `FF_FILENAME_RE` ≡ смысл `_FILENAME_RE`. Живой ping — смоук `HF:test` при наличии ключа, иначе skip с пометкой, не fail пакета.

## §15 Крон

Расписание v0.1 (рекомендация = MFF): Пн–Пт каждые 2 ч в окне 10–20. Точное crontab — Q-4.

Класс **O**: `depends: operator:ставь кроны`. Без глагола Саши `jobs.json` не писать. Обёртка `error_bus_wrap.sh --tool MoveFromKeyTalk --job-id <id>`.

## §16 ErrorBus и уведомления

- Техсбой крона → шина (`tool=MoveFromKeyTalk`), топик Errors `:11112`.
- Бизнес `notify_meeting_stale` → personal DM как MFF, не Errors.
- `instrumentation_registry.json` — Mode B wrap, не self+wrap вместе. Пишет ORCH.

## §17 `[NEW-ENTITY, требует согласования Саши]`

Маркер не сглаживать. Внедрять **запрещено** до ответа Саши. На `TZ:patch` сущности **не** создаются (манифест / `entities.json` / YAML keys — ORCH после согласования).

| Кандидат | Зачем | Reuse вместо него? |
|---|---|---|
| `[NEW-ENTITY, требует согласования Саши]` `applications.kontur_talk` | 14-е внешнее приложение (сейчас 13, KTalk нет) | Fireflies ≠ KTalk. Без записи digest/drift не знают источник. |
| `[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` | `entity_ref` для приложения, по правилу Eco §8.1 | Можно отложить: app без `entity_ref`, как Fireflies (`entity_ref: null`). **Рекомендация:** сначала только `applications.kontur_talk` без `api_*`. |
| `[NEW-ENTITY, требует согласования Саши]` `tools.move_from_keytalk` | ключ `tools{}` + `config.tools` `unified_only` | Это и есть продукт DEV; без ключа `--check-drift` красный после появления папки USERTOOLS. Регистрация — ORCH, не HF:impl. |

Не NEW-ENTITY: секрет в существующем `.env`; копия filename-хелперов; свой `_registry.json` в `state/` инструмента; скилл в `hermes-workspace`.

## §18 Что НЕ трогать

- `~/USERTOOLS/MoveFromFF/**` включая `_registry_meet.json`, `filename.py`, cron `vm_movefromff`.
- `~/USERTOOLS/ProtocolFromSummary/**` включая `_gen_ff_summary.py`, `summary_parser._SECTION_NAMES` / `_FILENAME_RE`.
- `~/USERTOOLS/MarkObjectsFromSummary/**`, `MofsIndex/**`, `FirefliesAutojoin/**`.
- `Registries/prompts/ff_summary.json` (только чтение).
- `Meetings/NewMeetings/_registry_meet.json` и `_registry_meet.md`.
- Живые `* - summary.md` / `* - transcript.md`, которые MFKT не создавал.
- Gateway, ядро `~/hermes-agent`, канбан, чужие скиллы телом.
- `jobs.json` без «ставь кроны».
- Per-tool `.env`, dual-read, литералы путей/моделей/токенов.
- KTalk summary API как канон текста.
- Импорт пакета `movefromff` из нового venv (связка запрещена).
- Ключ пространства KTalk (`X-API-Key`).
- Создание/отмена встреч в Толке.

## Контракты экосистемы

### Источник истины

- Владелец сырых записей KTalk: Контур.Толк API.
- Владелец саммари-промпта: `Registries/prompts/ff_summary.json`.
- Владелец файлов, которые **этот** tool записал: MoveFromKeyTalk (`state/_registry.json` + имена в `files`).
- Владелец реестра Fireflies-встреч: MoveFromFF (`_registry_meet.json`) — **не мы**.
- Владелец публикации протоколов: ProtocolFromSummary.

### Входные контракты

| Поле | Тип | Обязательность | Источник | Формат/enum |
|---|---|---|---|---|
| recording_key | str | required | KTalk API | id записи |
| title | str | required | KTalk API | имя встречи |
| date | datetime(iso8601) | required | KTalk API | UTC |
| duration | int | optional | KTalk API | минуты |
| participants | str | optional | KTalk API | ФИО/email |
| transcript sentences | str | required для completed | KTalk `.../transcript` | спикер + таймкод + текст |
| ff_summary.body | str | required | `prompts/ff_summary.json` | промпт v0.2.0 |
| KTALK_PERSONAL_API_KEY | str | required | shared `.env` | `X-Auth-Token` |
| KTALK_BASE_URL | str | required | EcosystemConfig.yaml | origin |
| KTALK_USER_KEY | str | optional до Q-2 | EcosystemConfig.yaml | `talkusr.*` |
| model.default | str | required для LLM | Hermes `config.yaml` | OpenRouter-id |

### Выходные контракты

| Поле | Тип | Потребитель | Формат/enum |
|---|---|---|---|
| files.transcript | str | диск, MofsIndex | `YYYY-MM-DD HH-MM-SS Title - transcript.md` |
| files.summary | str | PFS, MOFS, MofsIndex | `... - summary.md`; секции `_SECTION_NAMES` |
| meeting_id (PFS) | str | ProtocolFromSummary | stem summary-файла |
| status | enum[pending, completed, error, skipped_ff] | свой реестр | |
| summary_format | enum[custom] | свой реестр | всегда custom при completed |

### Зависимости

- Получает от: [Контур.Толк API, Hermes LLM, `ff_summary.json`, `usertools_config`, shared `.env`]
- Отдаёт: [файлы `NewMeetings/`, ProtocolFromSummary, MarkObjectsFromSummary, MofsIndex, ErrorBus]
- Не получает от / не пишет в: [MoveFromFF registry, Fireflies GraphQL]

### Breaking changes policy

- Имена файлов и набор секций summary — **не ломать**: потребители уже в проде.
- Схема своего реестра: `schema_version`, `extra="ignore"`, автодефолты.
- Смена промпта = bump `ff_summary.json` + отдельный CHANGE.

### Границы («что НЕ трогать»)

См. §18. Кратко для drift-check: не писать `_registry_meet.json`; не звать KTalk summary; не плодить `.env`; не патчить PFS/MFF.

## Критерии приёмки (AC)

Класс S по умолчанию. Показ AC ≠ ожидание.

| ID | Класс | Формулировка |
|---|---|---|
| AC-001 | S | Пакет `~/USERTOOLS/MoveFromKeyTalk/` + CLI `--mode test\|cron\|manual\|dry-run`; живой KTalk не обязателен для pytest. |
| AC-002 | S | Конфиг только `usertools_config` + YAML `tools.move_from_keytalk` + shared `.env`. Нет per-tool `.env`. `explain move_from_keytalk`: несекреты `source=ecosystem_config`/`shared`, секрет `source=shared_env`. |
| AC-003 | S | `summary.md` проходит `summary_parser._FILENAME_RE` и содержит ровно шесть заголовков `_SECTION_NAMES` без `##`. |
| AC-004 | S | Саммари из `ff_summary.json` + LLM; тело KTalk `/summary` не попадает в файл. |
| AC-005 | S | Пустой транскрипт → pending backoff, файлов нет; после 12 попыток `error` + один TG stale. |
| AC-006 | S | §10: существующий FF-файл title±10мин+участники → `skipped_ff`, новый файл не создан. |
| AC-007 | S | Атомарная запись пары файлов; ошибка второго → rollback обоих. |
| AC-008 | S | Pytest offline зелёные (filename, backoff, mock client, mock LLM, dedup, writer, config). |
| AC-009 | S | MFF/PFS/MOFS/FF-Autojoin/`ff_summary.json`/`_registry_meet.json` без diff этого пакета. |
| AC-010 | S | Крон-скрипт `no_agent` + ErrorBus wrap в дереве; в `jobs.json` **нет** job до AC-011. |
| AC-011 | O | `depends: operator:ставь кроны`. Крон в `jobs.json` только после глагола Саши. |
| AC-012 | S | `[NEW-ENTITY]` из §17 не появляются в манифесте/`entities.json` без ответа Саши. Регистрация `tools.move_from_keytalk` — ORCH после согласования. |
| AC-013 | S | Скилл `move-from-keytalk` описывает CLI; HTTP/LLM в скилл не копируются. |

## Открытые вопросы

Не блокируют драфт ТЗ. Блокируют `HF:impl` по пометке.

**Q-1 (блокер impl).** `KTALK_BASE_URL` боевого контура ТУТУ. Варианты: (1) `https://<tenant>.ktalk.ru` из админки; (2) внутренний reverse-proxy. Рекомендация: (1), значение — цитата Саши, в YAML без секрета.

**Q-2 (блокер фильтра).** Полный `talkusr.c1e5…`. В брифе префикс обрезан. Рекомендация: положить целиком в YAML `KTALK_USER_KEY`. До ответа — фильтр выключен, тянем всё, что видит персональный ключ.

**Q-3.** Два источника одной встречи. (1) skip если FF уже есть — **рекомендация, заложено в §10**; (2) всегда писать KTalk-копию; (3) KTalk побеждает и перезаписывает FF-файлы. (3) запрещён без отдельного CHANGE: чужие файлы не трогаем.

**Q-4.** Расписание крона. (1) как MFF, 2 ч / 10–20 Пн–Пт — **рекомендация**; (2) каждые 30 мин. Ставит оркестратор после AC-011.

**Q-5.** `[NEW-ENTITY]` §17: принять `applications.kontur_talk` без `entities.api_ktalk` (**рекомендация**) / оба / отложить app до первого боевого прогона.

## Риски

1. Домен и ключ неизвестны до Q-1/Q-2 — клиент пишется по публичному API + mock.
2. Транскрипт KTalk запаздывает дольше FF summary — backoff 15 ч как MFF; калибровка после боя.
3. Длинный транскрипт vs окно LLM — чанкинг §11, иначе обрезка молча **запрещена**.
4. Параллельный MFF в ту же папку — flock раздельный; дедуп §10 по файлам, не по чужому JSON.
5. `talkusr` vs персональный ключ: ключ уже ограничивает видимость; user-key — доп. фильтр, не второй секрет.

## Changelog

- **2026-10-15 v0.1.0 TZ:finalize** (DEV/movefromkeytalk, REV:tz APPROVE). Текст §1–§18, AC-001…013, Q-1…Q-5 зафиксирован без bump версии. Строка `MAIN_TZ_INVENTORY.md`. `status: draft` — открытые Q блокируют `HF:impl`, не эту фазу. Код / манифест / `entities.json` / `jobs.json` / `[NEW-ENTITY]` — не этот ход (регистрация `applications.kontur_talk` / optional `entities.api_ktalk` / `tools.move_from_keytalk` — ORCH после ответа Саши). Замечания REV (точный массив `PENDING_BACKOFF_MINUTES`, порог чанкинга) — в `HF:plan` / IAC, не перепись канона.
