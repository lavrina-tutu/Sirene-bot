---
tool: MoveFromKeyTalk
version: 0.2.0
date: 2026-10-19
status: approved
last-section-added: "v0.2.0 TZ:finalize CHANGE/ktalk-kontur-v-protsess REV:tz APPROVE — канон без bump; Q-1…Q-5 закрыты; status approved; YAML/schema ORCH; fail-loud HF:impl; AC-018 O vm_movefromff; [NEW-ENTITY] entities.api_ktalk не заводить"
---

# MoveFromKeyTalk — ТЗ

выжимка ≠ SoT; при расхождении — открыть master.

Автор: архитектор (Cursor, фазы `TZ:patch` → `TZ:finalize`).  
Пакет: `dev/ktalk-kontur-v-protsess` (CHANGE поверх DEV v0.1.0). Код на TZ-WRITE **не** пишется.

## §1 Назначение

USERTOOL. **Единственный** источник новых встреч в `WorkVault/Meetings/NewMeetings/` — корпоративный ВКС **Контур.Толк (KTalk)**. Тянет **сырой транскрипт** записи, **сам** строит `summary.md` локально нашим промптом `Registries/prompts/ff_summary.json` v0.2.0 (тот же канон секций, что был у Fireflies Custom AI Skill `tkachenkoav ff summary prompt 01072026` / `app_id=6a44d3b85f38b61f42f21cf2`) и кладёт пару markdown в формате контракта MFF/PFS.

Контур **MoveFromFF (Fireflies) как поставщик новых встреч уходит.** Этот инструмент **не** ходит в Fireflies GraphQL и **не** ждёт саммари от KTalk: у KTalk готового канонического саммари нет (в отличие от FF). Модуль `summarizer.py` — владелец текста `summary.md` (комментарий канона в коде: `no KTalk /summary`).

Имя инструмента `MoveFromKeyTalk` — слаг Саши (`movefromkeytalk`). Продукт API — Контур.Толк. «Gitalk» в брифе = оговорка того же KTalk, не отдельный сервис.

Цепочка **после** записи файлов **не меняется**: ProtocolFromSummary публикует протокол, MarkObjectsFromSummary размечает сущности, ObsidianFromConfluence синкает страницы сущностей. Их контракт с `Meetings/NewMeetings/` сохраняется. Этот инструмент **не** публикует в Confluence сам.

## §2 Reuse-first — что уже есть / почему не закрывает

| Уже есть | Что закрывает | Почему не закрывает этот бриф |
|---|---|---|
| **MoveFromFF** | Fireflies GraphQL → `NewMeetings/* - {transcript\|summary}.md` + `_registry_meet.json` | Контур FF как ingest **уходит**. Патч/DECOMM MFF — **не** этот пакет (§18). Код MFF не расширять под KTalk. |
| **FirefliesAutojoin** | Зовёт бота Fred в Zoom | Не транскрипт, не саммари, не диск. |
| **ProtocolFromSummary** | `NewMeetings/* summary.md` → Confluence | Потребитель. Контракт имени/секций **без правок**. `_gen_ff_summary.py` — ad-hoc обход пустого FF custom-skill, не крон и не KTalk-клиент; в runtime MFKT не копировать. |
| **MarkObjectsFromSummary / MofsIndex** | Разметка и индекс уже лежащих файлов | Не ходят в ВКС. Контракт `NewMeetings/` без правок. |
| **ObsidianFromConfluence** | Confluence → `Entities/<slug>/protocol.md` | Не ingest встреч. Файлы `NewMeetings/` не трогает. Без правок. |
| **IDEA `ff-summary-generator`** (`t_609e8869`) | Самаризатор FF-транскриптов + `get_llm("ff_summarizer")` | RESEARCH, не код. Промпт и слот LLM **переиспользуем**; отдельный USERTOOL-саммаризатор не заводим — саммари делает этот же MFKT. |
| **`Registries/prompts/ff_summary.json` v0.2.0** | Канон секций Участники / Обсудили / Решения / Блокеры / Задачи / Риски | **Reuse.** Форк промпта запрещён. Read-only. |
| **ktalk-cli (PyPI)** | Справочник путей KTalk (`list-recordings`, `transcript`, `X-Auth-Token`) | Runtime-зависимость **нет**: Python ≥3.12, свой SQLite-реестр, session-token. У нас боевой контур 3.11 + свой реестр. Клиент — свой HTTP. |
| **EcosystemConfig / `usertools_config`** | Единый несекретный конфиг | **Reuse.** Tool `unified_only` (Eco §10.4). Ключи YAML обязаны совпадать с `_MFKT_CONFIG_KEYS`. |
| **ErrorBus** | `error_bus_wrap.sh` | **Reuse.** Mode B на крон. |

**Вывод:** семейство `MoveFrom*`, ingest = только KTalk. Файловый контракт и промпт — reuse. Код MFF/PFS/MOFS/OFC/FF-Autojoin **не** расширять.

## §3 Место в экосистеме

```
Контур.Толк (KTalk REST)
        │  сырой транскрипт + метаданные
        │  (саммари KTalk НЕ берём)
        ▼
MoveFromKeyTalk  ── LLM(ff_summary.json) ──► NewMeetings/
        │                                      ├─ YYYY-MM-DD HH-MM-SS Title - transcript.md
        │                                      └─ YYYY-MM-DD HH-MM-SS Title - summary.md
        │
        ├── собственный реестр (не _registry_meet.json)
        └── PFS / MOFS / MofsIndex / OFC  (без правок)
                    │
                    ▼
            Confluence протоколы  +  Entities
```

Единственный **писатель новых** пар `transcript|summary` в эту папку — MoveFromKeyTalk. Исторические файлы Fireflies в `NewMeetings/` остаются на месте (чужие live md не трогаем). Дедуп с ними — leftover-защита §10, не два живых источника.

DECOMM кода/ТЗ MoveFromFF — **не** этот пакет (чужой поезд). Выключение крона `vm_movefromff` — **этот** пакет, AC-018 класс O (`depends: operator:ставь кроны`), не `HF:impl`.

## §4 Идентичность продукта и ключ пользователя

| Имя в брифе | Канон в этом ТЗ |
|---|---|
| KeyTalk | имя USERTOOL / слаг `MoveFromKeyTalk` |
| Gitalk | не сущность; синоним-оговорка KTalk |
| Контур.Толк / KTalk | внешнее приложение, REST `https://<domain>.ktalk.ru` |
| `talkusr.c1e5b36a7f8b471d8d2437357dc125bc` | публичный user-key владельца записей (`KTALK_USER_KEY`). **Не секрет.** Q-2 закрыт Сашей 15.10 (`Inbox/Tokens/ktalk.md`). |

Авторизация крона: **персональный API-ключ** заголовком `X-Auth-Token` (не session cookie, не ключ пространства `X-API-Key`). Секрет: `KTALK_PERSONAL_API_KEY` только в shared `~/.config/hermes/.env`. Scope минимум `application.recording.read`.

Справочник путей (ktalk-cli, не копировать пакет):

| Метод | Путь | Зачем |
|---|---|---|
| GET | `/api/Domain/recordings/v2` | список записей окна |
| GET | `/api/Recordings/{recordingKey}` | метаданные |
| GET | `/api/recordings/{recordingKey}/transcript` | сырой транскрипт |
| GET | `/api/Recordings/{recordingKey}` + participants endpoint | полный состав (лимит 6 в list) |

**Запрет:** `GET .../summary` и `.../summary/{type}` — не вызывать и не подставлять в наш `summary.md`. Саммари KTalk не канон и не fallback. Канон — локальный LLM + `ff_summary.json`.

Видеофайл, чат, архив reporting, создание встреч — вне скоупа.

Боевой origin (Q-1 закрыт Сашей 15.10): `KTALK_BASE_URL=https://tutu.ktalk.ru`. YAML 2026-10-19 содержит `https://tutu.ktalk.ru/` (хвостовой `/` клиент `rstrip("/")`). Смена origin — новый `TZ:patch`.

## §5 Scope / Non-goals

**В скоупе v0.2 (пакет `ktalk-kontur-v-protsess` + корпус v0.1):**

- Крон `no_agent` + ручной CLI (`cron` / `manual` / `test` / `dry-run`).
- Список записей умного окна, pending-backoff пока нет транскрипта.
- **Самостоятельная** саммаризация `ff_summary.json` v0.2.0 через Hermes LLM (единственный путь к `summary.md`).
- Атомарная запись пары файлов в `NewMeetings/` (имена как MFF § filename — контракт потребителей).
- Свой реестр + TG stale-алерт по образцу MFF.
- Leftover-дедуп «в папке уже есть summary на ту же встречу» (§10).
- Конфиг `unified_only`: в YAML **обязаны** быть `LOGS_PATH`, `PROMPT_PATH`, `KTALK_USER_KEY` (и прочие `_MFKT_CONFIG_KEYS`); отсутствие → fail loud, не тихий крон.
- Тесты по шаблону MFF + контракт PFS-парсера.
- Тонкий скилл ручного синка.
- ErrorBus wrap крона.

**Non-goals:**

- Правки MoveFromFF / ProtocolFromSummary / MarkObjectsFromSummary / ObsidianFromConfluence / FirefliesAutojoin / `ff_summary.json` / `_registry_meet.json`.
- DECOMM кода/ТЗ MoveFromFF (чужой поезд). Выключение крона `vm_movefromff` — **этот** пакет, класс O AC-018 (`depends: operator:ставь кроны`), не `HF:impl`.
- Публикация в Confluence, TaskRefresh, promote.
- Runtime-зависимость `ktalk-cli`.
- Per-tool `.env`, dual-read, литералы путей.
- Скачивание видео, чат KTalk, планирование встреч.
- Реализация IDEA `ff-summary-generator` как отдельного инструмента.
- Gateway, `jobs.json` (крон — только по «ставь кроны»), ядро Hermes.
- Вызов KTalk summary API.

## §6 Архитектура

Два слоя, как LoopChannelDigest / MFF:

1. **CLI-пакет** `~/USERTOOLS/MoveFromKeyTalk/` — детерминированный Python (HTTP + реестр + запись файлов) + один вызов LLM на готовую расшифровку (`summarizer.py` — единственный автор `summary.md`).
2. **Скилл** `productivity/move-from-keytalk` — триггеры и вызов CLI, без HTTP-логики.

Крон: обёртка `movefromkeytalk_sync.sh` → `venv/bin/python -m movefromkeytalk --mode cron`, `no_agent=true`, `error_bus_wrap.sh --tool MoveFromKeyTalk`. LLM-агент вокруг синка **запрещён** (урок MFF §3A).

Интерпретатор: свой venv (3.11, как MFF), не Hermes 3.14. Battle-interpreter регистрирует ORCH (не эта фаза).

## §7 Алгоритм синхронизации

Образец — MoveFromFF v2.1 шаги 1–4, плюс шаг LLM (саммари **всегда** локальный).

### Шаг 0. Preflight

flock; `usertools_config.load_tool_config("move_from_keytalk", keys=_MFKT_CONFIG_KEYS)`; секреты из shared `.env`; **все** ключи `_MFKT_CONFIG_KEYS` непусты; mkdir `NewMeetings/` + `state/` + `LOGS_PATH`; нет ключа YAML/env → **fail loud** CLI exit **2** (не silent, не пустой jsonl).

Цепочка, которую этот CHANGE чинит (факт 19.10, не гипотеза): `load_tool_config(..., required=True)` на отсутствующем ключе бросает **`KeyError`**; `run()` ловит только `RuntimeError` → uncaught → Python exit **1**; `bin/movefromkeytalk_sync.sh` мапит `0|1 → 0` (как MFF partial). Итог: крон `last_status=ok`, output silent empty. Норма: `KeyError` и `RuntimeError` missing-config — один путь, CLI exit 2; обёртка мапит на 0 **только** 0 и 1 (частичный ingest), **не** 2/3/4. Список required YAML: §12.

### Шаг 1. Ping

Лёгкий запрос списка `top=1`. 401 → ошибка ключа. 403 → scope. Exit 3.

### Шаг 2. Умное окно

| mode | from | to |
|---|---|---|
| `test` | now − 5 суток | now |
| `manual` | `--from` / `--to` | как задано |
| `cron` | `max(last_synced_at, now − 24ч)`; первый запуск: now − 4ч30мин | now |

Список: `start-from` / `start-to`, пагинация `page-token`, `top` ≤ 100.

Фильтр: записи, видимые персональным ключом; `KTALK_USER_KEY` обязателен в YAML — только записи этого пользователя (автор/организатор). Пустой/absent ключ = дефект конфига (Шаг 0), не «фильтр выключен». Значение: `talkusr.c1e5b36a7f8b471d8d2437357dc125bc` (Q-2 закрыт 15.10).

### Шаг 3. На каждую запись `recording_key`

1. Свой реестр `completed` → `meeting_skipped`.
2. Свой `pending` и `now < next_retry_at` → `meeting_backoff`.
3. `attempts >= MAX_PENDING_ATTEMPTS` → `error`, `notify_meeting_stale`, skip.
4. §10: если в `NewMeetings/` уже есть пара/summary (в т.ч. исторический FF) на ту же встречу → `meeting_ff_exists`, статус `skipped_ff` (имя статуса историческое), файлы **не** писать.
5. `GET` metadata + transcript. Нет реплик / пустой transcript → pending backoff как MFF: `PENDING_BACKOFF_MINUTES = [5, 10, 20, 30, 60, 60, 120, 120, 120, 120, 120, 120]`, `MAX_PENDING_ATTEMPTS=12` (копия значений MFF §5, не `import movefromff`). **Не** звать KTalk `/summary`.
6. LLM: тело `ff_summary.json` + транскрипт (паттерн `_gen_ff_summary.py`, не копировать скрипт PFS в runtime). Таймаут/пусто → pending, файл не писать.
7. Атомарно `write_meeting_files` (rollback при ошибке). Статус `completed`. `summary_format=custom`.

Встроенное саммари KTalk **не** источник и **не** fallback. Fallback «FF bullet_points» **не** использовать: FF-контур ingest не живой, у KTalk нет FF-overview.

### Шаг 4. Финализация

При `not dry_run` и `errors==0` и не точечный `--recording-key`: `last_synced_at = to`. Атомарный save реестра. Лог `run_summary`.

Константы backoff — массив выше (копия MFF §5, не import `movefromff`).

Коды лога: `meeting_skipped`, `meeting_backoff`, `meeting_pending`, `meeting_stale`, `meeting_ff_exists`, `download_ok`, `download_error`, `summarize_error`.

Exit: 0 успех; 1 частичный; 2 lock/preflight; 3 API недоступен; 4 фатально.

## §8 Формат файлов (контракт PFS/MOFS)

Канон имён — `MoveFromFF/movefromff/filename.py` (копия контракта, не import):

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

Этот контракт — **вход** PFS / MOFS / MofsIndex / (косвенно) OFC. Ломать имена или шесть секций запрещено.

## §9 Свой реестр

Путь: `~/USERTOOLS/MoveFromKeyTalk/state/_registry.json` (не vault, не `_registry_meet.json`).

`schema_version: "1.0"`. Поля записи: `recording_key`, `title`, `meeting_date`, `duration_minutes`, `participants`, `files`, `status`, `attempts`, `next_retry_at`, `first_seen_at`, `summary_format`, `ff_skip_reason`.

Статусы: `pending` | `completed` | `error` | `skipped_ff`.

Атомарная запись tmp+replace. MFF `reconcile` / `detect_and_mark_duplicates` этот реестр **не** читают и файлы MFKT **не** удаляют (удаляют только `rec.files` своих записей). Мы чужой реестр **не** читаем.

## §10 Дедуп leftover-файлов (исторический FF и чужие summary)

Два живых источника в одну папку **больше не норма**. Правило skip остаётся, чтобы не плодить вторую пару на встречу, у которой в `NewMeetings/` уже лежит `* - summary.md` (исторический Fireflies или чужой файл).

Правило skip (все три):

1. Нормализованный `title` (strip, как MFF).
2. `|Δ meeting_date| ≤ 10 мин` (`DEDUP_TIME_THRESHOLD_MIN=10`).
3. Пересечение участников (email или ФИО). Пустой список у одной стороны = пересечение считается.

Ищем **существующие** `* - summary.md` в `NewMeetings/`, не записи `_registry_meet.json` (MFF-реестр не читаем, чтобы не стать вторым писателем).

Совпадение → не пишем файлы, `skipped_ff` (историческое имя статуса). Иначе пишем — PFS увидит новую встречу.

Перезапись чужих файлов **запрещена**. Смена правила — только новый `TZ:patch`.

## §11 Саммаризация (first-class, не fallback)

KTalk **не** отдаёт каноническое саммари в наш формат (в отличие от FF custom-skill). Текст `summary.md` — **самостоятельный продукт этого инструмента**, не «замена отсутствующего KTalk `/summary`» и не обход пустого FF.

| | |
|---|---|
| Владелец текста | `movefromkeytalk/summarizer.py` |
| Промпт | `/home/tkachenkoav/WorkVault/Registries/prompts/ff_summary.json` (`id=ff_summary`, `version=0.2.0`) |
| Путь на диске | YAML `PROMPT_PATH` (required, §12) |
| Транспорт | OpenAI-совместимый клиент к ТУТУ-шлюзу, как PFS §30 |
| Модель | Hermes `config.yaml` `model.default` / `model.provider`; override только `tools.move_from_keytalk.llm` или process env |
| Last-resort | те же `LLM_FALLBACK_*`, что PFS; `ANTHROPIC_API_KEY` не читать |
| Слот Eco `get_llm("ff_summarizer")` | **не** плодить ключ `tools.ff_summarizer` в YAML; этот tool — потребитель того же промпта |
| KTalk `GET .../summary` | **запрещён** (не вызывать; httpx-mock в тестах: путь `/summary` не дергается) |

Промпт на диск **не** копировать в USERTOOLS. Смена шаблона = правка канона `ff_summary.json` отдельным CHANGE, не этот пакет.

Пустой раздел = заголовок без буллитов (норма промпта). Пустой ответ LLM целиком = ошибка, pending.

Лимит транскрипта: чанкинг по границам реплик, `CHUNK_CHAR_LIMIT=30000` (как в коде `registry.py`) → один вызов, если влезает; иначе последовательная суммаризация частей + финальный merge тем же промптом. Детали IAC на `HF:plan`. Обрезка молча **запрещена**.

## §12 Конфиг — unified_only, полный набор ключей

Ключ манифеста: `move_from_keytalk` (snake, не имя папки).

Несекреты — только `EcosystemConfig.yaml` `tools.move_from_keytalk` + `shared.WORKVAULT_PATH`. Новый именованный ключ **сначала** в `EcosystemConfig.schema.json` `definitions.tool_section.properties`. **Факт 2026-10-19:** `LOGS_PATH` уже именован; `KTALK_BASE_URL` / `KTALK_USER_KEY` / `PROMPT_PATH` проходят лишь через `additionalProperties` — имена добавляет **ORCH:shared-state**, не `HF:impl` (workspace USERTOOLS).

Код: `movefromkeytalk/config.py` `_MFKT_CONFIG_KEYS` = `TOOL_DIR`, `LOGS_PATH`, `MEETINGS_DIR`, `KTALK_BASE_URL`, `KTALK_USER_KEY`, `PROMPT_PATH`, `TELEGRAM_CHAT_ID`. Пустое значение после резолва — `_req()` → `RuntimeError`. Отсутствующий ключ YAML — `load_tool_config` → **`KeyError`**. Оба — CLI exit 2 (§7 Шаг 0).

**Факт диска 2026-10-19 (дефект, этот CHANGE чинит нормой):** в YAML есть только `enabled`, `TOOL_DIR`, `MEETINGS_DIR`, `TELEGRAM_CHAT_ID`, `KTALK_BASE_URL=https://tutu.ktalk.ru/` (хвостовой `/` клиент `rstrip`). Нет `LOGS_PATH`, `KTALK_USER_KEY`, `PROMPT_PATH`. Каталога `~/WorkVault/_meta/MoveFromKeyTalk/` нет. `USERTOOLS/MoveFromKeyTalk/state/` пуст (нет `_registry.json`). Job `4e689c13ae01`: 18 прогонов, `last_status=ok`, output silent empty (последний 19.10 13:05). Норма: три ключа **обязаны** быть в YAML; отсутствие = exit 2 + ErrorBus, не тихий ok.

Канон блока YAML (значения путей — абсолютные, как у соседей):

```yaml
  move_from_keytalk:
    enabled: true
    TOOL_DIR: /home/tkachenkoav/USERTOOLS/MoveFromKeyTalk
    LOGS_PATH: /home/tkachenkoav/WorkVault/_meta/MoveFromKeyTalk
    MEETINGS_DIR: /home/tkachenkoav/WorkVault/Meetings/NewMeetings
    KTALK_BASE_URL: https://tutu.ktalk.ru
    KTALK_USER_KEY: talkusr.c1e5b36a7f8b471d8d2437357dc125bc
    PROMPT_PATH: /home/tkachenkoav/WorkVault/Registries/prompts/ff_summary.json
    TELEGRAM_CHAT_ID: "400307920"
    # llm: optional override
```

| Ключ YAML | Обязательность | Назначение / канон значения |
|---|---|---|
| `enabled` | required | bool |
| `TOOL_DIR` | required | `/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk` |
| `LOGS_PATH` | **required** | `/home/tkachenkoav/WorkVault/_meta/MoveFromKeyTalk` (mkdir на preflight) |
| `MEETINGS_DIR` | required | `/home/tkachenkoav/WorkVault/Meetings/NewMeetings` (тот же каталог, что PFS) |
| `KTALK_BASE_URL` | required | origin без path: `https://tutu.ktalk.ru` (Q-1 закрыт) |
| `KTALK_USER_KEY` | **required** | `talkusr.c1e5b36a7f8b471d8d2437357dc125bc` (Q-2 закрыт 15.10, `Inbox/Tokens/ktalk.md`). Не секрет. Пустая строка запрещена. |
| `PROMPT_PATH` | **required** | `/home/tkachenkoav/WorkVault/Registries/prompts/ff_summary.json` |
| `TELEGRAM_CHAT_ID` | required | stale-алерт; reuse MFF `400307920`, не плодить второй чат |
| `llm` | optional | override модели/провайдера |

`WORKVAULT_PATH` в `tools.move_from_keytalk` **не** дублировать (только `shared`).

Секреты (имена с `API_KEY`/`TOKEN` в YAML схема отвергнет):

| Env | Где |
|---|---|
| `KTALK_PERSONAL_API_KEY` | shared `.env` |
| `TELEGRAM_BOT_TOKEN` | уже есть |
| LLM key | как PFS (`LLM_FALLBACK_*` / провайдер yaml) |

Per-tool `.env` **не** создавать. Dual-read **запрещён**. В `EcosystemManifest.json` `config.tools` ключа `move_from_keytalk` **нет** (дефолт `migration_status=not_started`). `migration_status: unified_only` пишет **ORCH:shared-state**, не архитектор и не исполнитель на `HF:impl`.

Запись трёх недостающих ключей в YAML (`LOGS_PATH`, `PROMPT_PATH`, `KTALK_USER_KEY` с Q-2) + имён `KTALK_BASE_URL`/`KTALK_USER_KEY`/`PROMPT_PATH` в schema + `config.tools.move_from_keytalk.migration_status=unified_only` — **ORCH:shared-state** (Registries), не `HF:impl`.

`HF:impl` **обязан** закрыть fail-loud в коде пакета (не «если IAC покажет»): `run()` ловит `KeyError` и `RuntimeError` missing-config → exit 2; pytest: отсутствующий ключ → exit 2, не 1. Обёртка `0|1→0` для частичного ingest **не** менять смысл; 2/3/4 остаются ненулевыми. `jobs.json` не трогать.

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
    config.py          # usertools_config, fail loud на любой ключ _MFKT_CONFIG_KEYS
    ktalk_client.py    # httpx+retry; не ktalk-cli; нет GET /summary
    filename.py        # копия контракта MFF, не import movefromff
    registry.py
    writer.py          # atomic tmp+replace, rollback
    summarizer.py      # единственный автор summary.md; ff_summary.json + LLM
    dedup_ff.py        # §10 по файлам NewMeetings
    tg.py
    lock.py
    logger.py
  tests/
    test_filename.py           # regex = PFS _FILENAME_RE
    test_registry.py
    test_pending_backoff.py
    test_ktalk_client.py       # mock HTTP; /summary не вызывается
    test_summarizer.py         # mock LLM, секции _SECTION_NAMES
    test_dedup_ff.py
    test_writer.py
    test_config_unified.py     # нет local .env; секрет не в YAML; нет ключа → CLI exit 2 (KeyError и RuntimeError)
  bin/movefromkeytalk_sync.sh
  pyproject.toml
  README.md
```

venv свой. Скилл: `hermes-workspace/skills/productivity/move-from-keytalk/SKILL.md` + `restore-all-skills.sh` на ORCH.

Тесты: pytest offline, без живого KTalk/LLM. Контракт имени: `FF_FILENAME_RE` ≡ смысл `_FILENAME_RE`. Живой ping — смоук `HF:test` при наличии ключа, иначе skip с пометкой, не fail пакета.

## §15 Крон

Q-4 закрыт Сашей 15.10: как MFF. Факт: job `4e689c13ae01` (`MoveFromKeyTalk — синхронизация каждые 2ч`, `script=movefromkeytalk_sync.sh`, `no_agent`, `expr: 5 8-19 * * 1-5`) поставлен после «Зарускай кроны» 15.10. **Этот пакет job MFKT не переписывает.**

Обёртка: `error_bus_wrap.sh --tool MoveFromKeyTalk --job-id 4e689c13ae01`. Крон без полного YAML §12 не «чинит сам» и не глотает `Missing required config` (норма: CLI exit 2 + ErrorBus, не тихий `last_status=ok`).

Переключение ingest: крон `vm_movefromff` на 2026-10-19 всё ещё `enabled: true` (dual-ingest живой). Выключение — AC-018, `depends: operator:ставь кроны`. `HF:impl` `jobs.json` не пишет. Код MoveFromFF не патчить.

## §16 ErrorBus и уведомления

- Техсбой крона (в т.ч. preflight missing YAML) → шина (`tool=MoveFromKeyTalk`), топик Errors `:11112`.
- Бизнес `notify_meeting_stale` → personal DM как MFF, не Errors.
- `instrumentation_registry.json` — Mode B wrap, не self+wrap вместе. Пишет ORCH.

## §17 `[NEW-ENTITY]` — статус после Q-5 (15.10)

Маркер не сглаживать, пока нет ответа. **Ответ есть:** Q-5 закрыт Сашей 15.10 — как Fireflies: `applications.kontur_talk` без `entities.api_ktalk`. Повторно согласовывать не надо. На `TZ:patch` сущности **не** создаются.

| Кандидат | Статус 2026-10-19 |
|---|---|
| `[NEW-ENTITY]` `applications.kontur_talk` | **Согласовано Q-5.** В `EcosystemManifest.json`: `status: active`, `entity_ref: null`. Не удалять. |
| `[NEW-ENTITY]` `entities.api_ktalk` | **Отклонено Q-5** (отложить; как Fireflies `entity_ref: null`). Этим пакетом **не** заводить. |
| `[NEW-ENTITY]` `tools.move_from_keytalk` | **Согласовано** (ключ `tools{}` + YAML). Stub в манифесте есть. Полные `links`/контракты — ORCH, не `HF:impl`. |

Не NEW-ENTITY: секрет в существующем `.env`; копия filename-хелперов; свой `_registry.json` в `state/` инструмента; скилл в `hermes-workspace`; три YAML-ключа §12 (поля существующего `tools.move_from_keytalk`).

## §18 Что НЕ трогать

- `~/USERTOOLS/MoveFromFF/**` включая `_registry_meet.json`, `filename.py`. Крон `vm_movefromff` **кодом не патчить**; `enabled: false` только после AC-018 / «ставь кроны», не из `HF:impl`.
- `~/USERTOOLS/ProtocolFromSummary/**` включая `_gen_ff_summary.py`, `summary_parser._SECTION_NAMES` / `_FILENAME_RE`.
- `~/USERTOOLS/MarkObjectsFromSummary/**`, `MofsIndex/**`, `FirefliesAutojoin/**`.
- `~/USERTOOLS/ObsidianFromConfluence/**` (контракт: не пишет в `NewMeetings/`).
- `Registries/prompts/ff_summary.json` (только чтение).
- `Meetings/NewMeetings/_registry_meet.json` и `_registry_meet.md`.
- Живые `* - summary.md` / `* - transcript.md`, которые MFKT не создавал.
- Gateway, ядро `~/hermes-agent`, канбан, чужие скиллы телом.
- `jobs.json` без «ставь кроны».
- Per-tool `.env`, dual-read, литералы путей/моделей/токенов.
- KTalk summary API (не вызывать).
- Импорт пакета `movefromff` из нового venv (связка запрещена).
- Ключ пространства KTalk (`X-API-Key`).
- Создание/отмена встреч в Толке.

## §19 CHANGE `ktalk-kontur-v-protsess` (2026-10-19)

Пакет CHANGE. Код / YAML / schema на этой фазе **не** пишутся.

**I1-A ingest.** `current`: dual-контур живой — `vm_movefromff` `enabled: true` (последний ok 19.10) и MFKT `4e689c13ae01` оба пишут в `NewMeetings/`. `target`: новые встречи только из KTalk; MFKT — единственный писатель новых пар; крон MFF выключен (AC-018 O). Код MFF **не** патчить; DECOMM инструмента — чужой поезд.

**I1-B саммари.** `current`: код уже `summarizer.py` + `ff_summary.json`, клиент режет `/summary`. `target`: саммари **first-class** продукт MFKT; KTalk `/summary` не вызывается; это не fallback. Формулировки ТЗ v0.1 «как будто запасной канал» сняты.

**I1-C конфиг.** `current`: YAML без `LOGS_PATH`, `PROMPT_PATH`, `KTALK_USER_KEY`; `load_tool_config(..., required=True)` бросает **`KeyError`**; `run()` ловит только `RuntimeError` → uncaught → Python exit **1**; `bin/movefromkeytalk_sync.sh` мапит `0|1 → 0` → крон `4e689c13ae01` `last_status=ok`, output silent empty (**факт** 19.10, не подозрение). `target`: канон §12 заполнен (включая Q-2); schema именует `KTALK_*`/`PROMPT_PATH`; `KeyError` и `RuntimeError` missing-config → CLI exit **2** + ErrorBus. Обёртка `0|1→0` **не** менять смысл (частичный ingest); 2/3/4 остаются ненулевыми. YAML/schema пишет ORCH. Ловлю `KeyError` в `run()` пишет `HF:impl`.

**I1-D низ.** `current`: потребители завязаны на контракт MFF-файлов. `target`: PFS / MOFS / OFC / MofsIndex **без правок**; имена и `_SECTION_NAMES` те же.

Reuse-first: промпт, папка, PFS-парсер, ErrorBus, unified config, уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` (Q-5). Новой сущности этот пакет не создаёт. `entities.api_ktalk` не заводить.

Оценка объёма `HF:impl` (факт, не команда skip LIGHT): код саммари/клиента/`/summary`-бан уже на диске; YAML+schema — ORCH; выключение MFF-крона — operator AC-018. `HF:impl` **обязан** закрыть fail-loud: `run()` ловит `KeyError` **и** `RuntimeError` missing-config → exit 2; pytest на отсутствующий ключ YAML → exit 2, не 1. Дыра подтверждена диском 19.10 (`load_tool_config` → KeyError; `__main__.py` except только RuntimeError; wrap `0|1→0`). Оркестратор LIGHT не выбирает архитектор.

### Критерии приёмки (AC) пакета

Класс S по умолчанию. Показ AC ≠ ожидание. Корпус AC-001…013 остаётся в силе (ниже таблица обновлена формулировками, где пакет меняет смысл).

| ID | Класс | Формулировка |
|---|---|---|
| AC-014 | S | Новые пары `transcript\|summary` в `NewMeetings/` пишет только MFKT из KTalk REST. В коде пакета нет Fireflies GraphQL. MFF/PFS/MOFS/OFC без diff этого пакета (прирост vs baseline, не абсолютный пустой git). |
| AC-015 | S | `summary.md` всегда из `summarizer.py` + `PROMPT_PATH`→`ff_summary.json`. Клиент KTalk не делает `GET .../summary` (тест: mock httpx, путь `/summary` не вызывался). |
| AC-016 | S | В `EcosystemConfig.yaml` `tools.move_from_keytalk` присутствуют непустые `LOGS_PATH`, `PROMPT_PATH`, `KTALK_USER_KEY=talkusr.c1e5b36a7f8b471d8d2437357dc125bc` (канон §12). В schema `tool_section.properties` именованы `KTALK_BASE_URL`, `KTALK_USER_KEY`, `PROMPT_PATH` (`LOGS_PATH` уже есть). Отсутствие любого `_MFKT_CONFIG_KEYS` → `KeyError` (нет ключа YAML) или `RuntimeError` (`_req` пустое значение) ловятся в `run()` → CLI exit 2 + ErrorBus, не uncaught/`exit 1` и не silent `last_status=ok` через wrap `0|1→0`. YAML/schema пишет ORCH; fail-loud в коде пакета — `HF:impl`. |
| AC-017 | S | Контракт §8 (`_FILENAME_RE`, шесть `_SECTION_NAMES` без `##`, `meeting_id`=stem) без изменений. Тесты filename/summarizer зелёные. |
| AC-018 | O | `depends: operator:ставь кроны`. Крон `vm_movefromff` выключен (`enabled: false` или снят). Код MoveFromFF без diff этого пакета. Job MFKT `4e689c13ae01` не переписывать. |

## Контракты экосистемы

### Источник истины

- Владелец сырых записей KTalk: Контур.Толк API.
- Владелец текста `summary.md`, который **этот** tool записал: MoveFromKeyTalk (`summarizer.py` + `ff_summary.json`, не KTalk `/summary`).
- Владелец саммари-промпта: `Registries/prompts/ff_summary.json` (read-only).
- Владелец файлов, которые **этот** tool записал: MoveFromKeyTalk (`state/_registry.json` + имена в `files`).
- Владелец реестра исторических Fireflies-встреч: MoveFromFF (`_registry_meet.json`) — **не мы**.
- Владелец публикации протоколов: ProtocolFromSummary.
- Владелец frontmatter сущностей на summary: MarkObjectsFromSummary.
- Владелец `Entities/<slug>/protocol.md`: ObsidianFromConfluence — **не мы**.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| recording_key | str | required | KTalk API | id записи |
| title | str | required | KTalk API | имя встречи |
| date | datetime(iso8601) | required | KTalk API | UTC |
| duration | int | optional | KTalk API | минуты |
| participants | str | optional | KTalk API | ФИО/email |
| transcript sentences | str | required | KTalk `.../transcript` | спикер + таймкод + текст |
| ff_summary.body | str | required | `prompts/ff_summary.json` | промпт v0.2.0 |
| KTALK_PERSONAL_API_KEY | str | required | shared `.env` | `X-Auth-Token` |
| KTALK_BASE_URL | str | required | EcosystemConfig.yaml | origin `https://tutu.ktalk.ru` |
| KTALK_USER_KEY | str | required | EcosystemConfig.yaml | `talkusr.c1e5b36a7f8b471d8d2437357dc125bc` |
| LOGS_PATH | str | required | EcosystemConfig.yaml | каталог `_meta/MoveFromKeyTalk` |
| PROMPT_PATH | str | required | EcosystemConfig.yaml | путь к `ff_summary.json` |
| model.default | str | required | Hermes `config.yaml` | OpenRouter-id |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| files.transcript | str | диск, MofsIndex | `YYYY-MM-DD HH-MM-SS Title - transcript.md` |
| files.summary | str | ProtocolFromSummary, MarkObjectsFromSummary, MofsIndex | `... - summary.md`; секции `_SECTION_NAMES` |
| meeting_id | str | ProtocolFromSummary | stem summary-файла |
| status | enum[pending, completed, error, skipped_ff] | свой реестр | skipped_ff = leftover-дедуп §10 |
| summary_format | enum[custom] | свой реестр | всегда custom при completed |

### Зависимости

- Получает от: [Контур.Толк API, Hermes LLM, `ff_summary.json`, `usertools_config`, shared `.env`]
- Отдаёт: [файлы `NewMeetings/`, ProtocolFromSummary, MarkObjectsFromSummary, MofsIndex, ErrorBus]
- Не получает от / не пишет в: [MoveFromFF registry, Fireflies GraphQL, KTalk `/summary`, ObsidianFromConfluence runtime, чужие live md]

### Breaking changes policy

- Имена файлов и набор секций summary — **не ломать**: потребители уже в проде.
- Схема своего реестра: `schema_version`, `extra="ignore"`, автодефолты.
- Смена промпта = bump `ff_summary.json` + отдельный CHANGE.

### Границы («что НЕ трогать»)

См. §18. Кратко для drift-check: не писать `_registry_meet.json`; не звать KTalk summary; не плодить `.env`; не патчить PFS/MFF/MOFS/OFC.

## Критерии приёмки (AC)

Класс S по умолчанию. Показ AC ≠ ожидание. AC-014…018 — пакет CHANGE (§19); AC-001…013 — корпус (AC-011 больше не O).

| ID | Класс | Формулировка |
|---|---|---|
| AC-001 | S | Пакет `~/USERTOOLS/MoveFromKeyTalk/` + CLI `--mode test\|cron\|manual\|dry-run`; живой KTalk не обязателен для pytest. |
| AC-002 | S | Конфиг только `usertools_config` + YAML `tools.move_from_keytalk` + shared `.env`. Нет per-tool `.env`. `explain move_from_keytalk`: несекреты `source=ecosystem_config`/`shared`, секрет `source=shared_env`. Набор YAML = §12. |
| AC-003 | S | `summary.md` проходит `summary_parser._FILENAME_RE` и содержит ровно шесть заголовков `_SECTION_NAMES` без `##`. |
| AC-004 | S | Саммари из `ff_summary.json` + LLM (`summarizer.py`); тело KTalk `/summary` не попадает в файл и API `/summary` не вызывается. |
| AC-005 | S | Пустой транскрипт → pending backoff, файлов нет; после 12 попыток `error` + один TG stale. |
| AC-006 | S | §10: существующий summary title±10мин+участники → `skipped_ff`, новый файл не создан. |
| AC-007 | S | Атомарная запись пары файлов; ошибка второго → rollback обоих. |
| AC-008 | S | Pytest offline зелёные (filename, backoff, mock client, mock LLM, dedup, writer, config). |
| AC-009 | S | MFF/PFS/MOFS/OFC/FF-Autojoin/`ff_summary.json`/`_registry_meet.json` без diff этого пакета (прирост vs baseline). |
| AC-010 | S | Крон-скрипт `no_agent` + ErrorBus wrap в дереве пакета. Job в `jobs.json` — AC-011 (уже стоит, не этот ход). |
| AC-011 | S | Крон MFKT `4e689c13ae01` уже в `jobs.json` после «Зарускай кроны» 15.10 (`5 8-19 * * 1-5`, `no_agent`). Этот пакет его не переписывает. |
| AC-012 | S | `entities.api_ktalk` этим пакетом не создаётся (Q-5). Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять. |
| AC-013 | S | Скилл `move-from-keytalk` описывает CLI; HTTP/LLM в скилл не копируются. |
| AC-014 | S | §19: новые встречи только KTalk; нет Fireflies GraphQL в пакете. |
| AC-015 | S | §19: саммари first-class локально; `GET .../summary` не вызывается. |
| AC-016 | S | §19: YAML+schema `LOGS_PATH`/`PROMPT_PATH`/`KTALK_USER_KEY` (значение Q-2); missing → `KeyError`/`RuntimeError` → exit 2, не wrap→ok. ORCH пишет YAML; fail-loud — `HF:impl`. |
| AC-017 | S | §19: контракт §8 для PFS/MOFS/OFC без изменений. |
| AC-018 | O | §19: `depends: operator:ставь кроны` — выключить `vm_movefromff`; код MFF не патчить. |

## Открытые вопросы

Новых Q у этого пакета нет. Корпус Q-1…Q-5 закрыт Сашей 15.10 (поезд `movefromkeytalk`, journal) и здесь фиксируется в master (раньше оставался «открытым» в тексте v0.1.0).

**Q-1 — закрыт 15.10.** `KTALK_BASE_URL=https://tutu.ktalk.ru`. YAML содержит хвостовой `/`; канон без path, клиент `rstrip("/")`.

**Q-2 — закрыт 15.10.** `KTALK_USER_KEY=talkusr.c1e5b36a7f8b471d8d2437357dc125bc` из `Inbox/Tokens/ktalk.md` (не секрет). В YAML 19.10 ключа нет — дыра ORCH, не отсутствующий ответ Саши.

**Q-3 — закрыт 15.10.** Leftover-skip если summary уже на диске (вариант 1 §10). Перезапись чужих файлов запрещена. Два **живых** источника (два крона) — больше не норма: AC-018.

**Q-4 — закрыт 15.10.** Как MFF: `5 8-19 * * 1-5`. Job `4e689c13ae01` уже стоит.

**Q-5 — закрыт 15.10.** `applications.kontur_talk` без `entities.api_ktalk`. Лежит в манифесте. Повторный вопрос не задавать.

## Риски

1. YAML без трёх ключей при живом кроне `4e689c13ae01` с `last_status=ok` — ingest может «молчать». Норма AC-016: exit 2 + ErrorBus.
2. Транскрипт KTalk запаздывает — backoff как MFF; калибровка после боя.
3. Длинный транскрипт vs окно LLM — чанкинг §11, иначе обрезка молча **запрещена**.
4. Исторические FF-файлы в той же папке — leftover §10 по файлам, не по чужому JSON; flock раздельный.
5. `KTALK_USER_KEY` (публичный talkusr в YAML) ≠ `KTALK_PERSONAL_API_KEY` (только shared `.env`, заголовок `X-Auth-Token`). Не копировать секрет в YAML/ТЗ.
6. Пока `vm_movefromff` enabled, dual-ingest жив; leftover-skip не заменяет выключение крона (AC-018). DECOMM кода MFF — чужой поезд.

## TZ:finalize (2026-10-19)

Каноническая фиксация v0.2.0 + строка инвентаря (Б15 п.6 / Б18). Версия **не** bump: `REV:tz` APPROVE на тот же текст `TZ:patch`. `status: approved` — Q-1…Q-5 закрыты (легенда: `approved` только при закрытых Q). Код / YAML / schema / `jobs.json` / манифест — не этот ход (ORCH / `HF:impl` / operator AC-018).

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` — **отклонено Q-5**, этим пакетом **не** заводить. Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять (ORCH дописывает links, не `HF:impl`).

Замечания REV (не блокировали): точная IAC-формулировка `except (KeyError, RuntimeError)` в `run()`; §10 leftover-дедуп остаётся включённым до и после AC-018 без смены логики — зона `HF:plan` / IAC, не перепись канона.

## Changelog

- **2026-10-19 v0.2.0 TZ:finalize** (CHANGE/`ktalk-kontur-v-protsess`, REV:tz APPROVE). Текст §1–§19, AC-001…018, Q-1…Q-5 закрыты — зафиксирован без bump версии. Строка `MAIN_TZ_INVENTORY.md`. `status: approved`. Код / YAML / schema / `jobs.json` / манифест / `[NEW-ENTITY]` — не этот ход. Замечания REV (IAC KeyError; §10 дедуп до/после AC-018) — в `HF:plan` / IAC.
- **2026-10-19 v0.2.0 TZ:patch** (CHANGE/`ktalk-kontur-v-protsess`). Единственный ingest новых встреч = KTalk. Саммари first-class локально. PFS / MOFS / OFC / MofsIndex без правок. YAML-канон §12: дописать `LOGS_PATH`/`PROMPT_PATH`/`KTALK_USER_KEY` (Q-2 значение 15.10) — пишет ORCH. Q-1…Q-5 закрыты Сашей 15.10 (в master v0.1 оставались «открытыми» — исправлено). AC-011 больше не O: крон MFKT уже стоит. AC-014…017 S; AC-018 O выключить `vm_movefromff`. `entities.api_ktalk` не заводить. Код / YAML / schema / `jobs.json` на этой фазе не пишутся. Повторный ход той же фазы: снято противоречие §3 («выключение крона MFF не этот пакет») vs AC-018; снято «HF:impl только если IAC» — дыра KeyError→exit 1→wrap→ok подтверждена диском, `HF:impl` обязан закрыть.
- **2026-10-15 v0.1.0 TZ:finalize** (DEV/movefromkeytalk, REV:tz APPROVE). Текст §1–§18, AC-001…013, Q-1…Q-5 зафиксирован без bump версии. Строка `MAIN_TZ_INVENTORY.md`. `status: draft` — открытые Q блокируют `HF:impl`, не эту фазу. Код / манифест / `entities.json` / `jobs.json` / `[NEW-ENTITY]` — не этот ход (регистрация `applications.kontur_talk` / optional `entities.api_ktalk` / `tools.move_from_keytalk` — ORCH после ответа Саши). Замечания REV (точный массив `PENDING_BACKOFF_MINUTES`, порог чанкинга) — в `HF:plan` / IAC, не перепись канона.
