---
tool: MoveFromKeyTalk
version: 0.2.5
date: 2026-10-20
status: approved
last-section-added: "v0.2.5 TZ:finalize CHANGE-LIGHT/ktalk-kontur-schedule-10min-timeout-540: штамп корпуса §11/§15/§24 без правок смысла; крон */10 + timeout 540с; AC-027/028; [NEW-ENTITY] entities.api_ktalk не заводить"
---

# MoveFromKeyTalk — ТЗ

выжимка ≠ SoT; при расхождении — открыть master.

Автор: архитектор (Cursor, фаза `TZ:patch` CHANGE-LIGHT).  
Пакет: `dev/ktalk-kontur-schedule-10min-timeout-540`. Код на TZ-WRITE **не** пишется. Канон §1–§23 / AC-001…026 остаётся; дельта — §11/§15 timeout 540с + крон каждые 10 мин + §24 + AC-027/028.

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

Справочник путей **пользовательского контура** (персональный `X-Auth-Token`). ktalk-cli — справочник, не runtime: живой персональный контур **не равен** интеграторским путям ktalk-cli (`Domain/v2`, заглавная `Recordings`).

| Метод | Путь | Зачем |
|---|---|---|
| GET | `/api/recordings` | список записей, видимых персональным ключом. Query: `top` ≤ 100, `skip`. **Не** слать `start-from` / `start-to` / `page-token`. Окно дат — клиент по `createdDate` |
| GET | `/api/recordings/{id}` | метаданные (lowercase `recordings`, не `Recordings`) |
| GET | `/api/recordings/{id}/transcript` | сырой транскрипт (`tracks[].chunks[]`) |

**Запрет путей (не fallback):** `GET /api/Domain/recordings/v2` — интеграторский scope Domain; персональному ключу → 403. `GET /api/Recordings/{id}` (заглавная R) — не канон этого контура. `GET /api/recordings/{id}/participants` — 404; состав брать из list/detail (`participants[].userInfo.{firstname,surname}`).

**Запрет:** `GET .../summary` и `.../summary/{type}` — не вызывать и не подставлять в наш `summary.md`. Саммари KTalk не канон и не fallback. Канон — локальный LLM + `ff_summary.json`.

Видеофайл, чат, архив reporting, создание встреч — вне скоупа.

Боевой origin (Q-1 закрыт Сашей 15.10): `KTALK_BASE_URL=https://tutu.ktalk.ru`. YAML 2026-10-19 содержит `https://tutu.ktalk.ru/` (хвостовой `/` клиент `rstrip("/")`). Смена origin — новый `TZ:patch`.

## §5 Scope / Non-goals

**v0.2.5** (пакет `ktalk-kontur-schedule-10min-timeout-540`) не расширяет продукт: тот же ingest KTalk → `NewMeetings/`; конфигурация существующего job `4e689c13ae01` (`5 8-19 * * 1-5` → `*/10 8-19 * * 1-5`) и клиентский timeout LLM 600→**540с** (§11/§15/§24). Новый cron / `.env` / манифест / `[NEW-ENTITY]` **не** заводить. `CHUNK_CHAR_LIMIT=30000` без смены. `ff_summary.json` read-only. Форматы §8 и корпус AC-001…026 без пересмотра.

**v0.2.4** (пакет `ktalk-kontur-samari-dlinnye-transkripty-taimaut`) не расширяет продукт: тот же ingest KTalk → `NewMeetings/`; чинит канон заголовков секций (скобки шаблона `X (…):` → `X:` до validate) и клиентский timeout LLM 300→**600с** (§8/§11/§23). `CHUNK_CHAR_LIMIT=30000` без смены. `ff_summary.json` read-only.

**v0.2.3** (пакет `ktalk-kontur-samari-taimaut-llm-dlinnyj-transkript`) не расширяет продукт: тот же ingest KTalk → `NewMeetings/`; чинит клиентский timeout LLM самаризации (§11/§22). `CHUNK_CHAR_LIMIT=30000` без смены.

**v0.2.2** (пакет `ktalk-kontur-pravilnyj-put-api-recordings`) не расширяет продукт: тот же ingest KTalk → `NewMeetings/`; чинит путь и парсер пользовательского контура (§4/§7/§21).

**В скоупе v0.2.1 (пакет `ktalk-kontur-poluchenie-transkriptov-avtonomnaya`; нормы v0.2.0 пакета `ktalk-kontur-v-protsess` + корпус v0.1):**

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

Список: `GET /api/recordings`. Query только `top` (≤ 100) и `skip` (пагинация: `skip` += размер батча, пока батч непустой и `len(batch)==top`). `page-token` / `nextPageToken` **нет** — не ждать и не слать. Окно дат Шага 2 **не** класть в query `start-from` / `start-to` — фильтр клиента: запись в окне, если `createdDate` ∈ [from, to].

Фильтр пользователя:

1. `KTALK_USER_KEY` остаётся **required** в YAML (пустое/absent → Шаг 0 exit 2). Значение Q-2 не менять: `talkusr.c1e5b36a7f8b471d8d2437357dc125bc`.
2. Список строится из записей, которые вернул персональный токен (скоуп = токен; живой `GET /api/recordings` уже отдаёт встречи владельца ключа).
3. Жёсткий talkusr-матч (`user_key in {author_key, organizer_key}`) — **только если** в payload есть author-like поле (`authorKey` / `organizerKey` / `createdBy.userKey` / вложенный talkusr). Если identity только UUID / `createdBy.login` — **не отсекать**.
4. Не фильтровать по ФИО и не заводить маппинг talkusr→UUID в этом пакете.

### Шаг 3. На каждую запись `recording_key`

1. Свой реестр `completed` → `meeting_skipped`.
2. Свой `pending` и `now < next_retry_at` → `meeting_backoff`.
3. `attempts >= MAX_PENDING_ATTEMPTS` → `error`, `notify_meeting_stale`, skip.
4. §10: если в `NewMeetings/` уже есть пара/summary (в т.ч. исторический FF) на ту же встречу → `meeting_ff_exists`, статус `skipped_ff` (имя статуса историческое), файлы **не** писать.
5. `GET /api/recordings/{id}` (lowercase) + `GET /api/recordings/{id}/transcript`. Отдельный `GET .../participants` **не** вызывать (404; состав уже в list/detail). Нет реплик / пустой transcript → pending backoff как MFF: `PENDING_BACKOFF_MINUTES = [5, 10, 20, 30, 60, 60, 120, 120, 120, 120, 120, 120]`, `MAX_PENDING_ATTEMPTS=12` (копия значений MFF §5, не `import movefromff`). **Не** звать KTalk `/summary`.
6. LLM: тело `ff_summary.json` + транскрипт (паттерн `_gen_ff_summary.py`, не копировать скрипт PFS в runtime). Таймаут/пусто/невалидные секции → pending, файл не писать. Порог клиента LLM — §11 (default **540с**); заголовки канонизируются до validate (§8/§11); поведение pending **без смены**.
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

На диск уходит `Риски:`, не скобочный хвост шаблона промпта. Скобки `Риски (Кто высказал /Вероятность /Влияние):` — подсказка модели про формат буллитов, не опубликованный заголовок. Канонизация `X (…):` → `X:` — в summarizer **до** `validate_summary_sections` (§11); валидатор остаётся строгим (exact `Имя:`). `ff_summary.json` **не** править (§18 read-only).

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

Промпт на диск **не** копировать в USERTOOLS. Смена шаблона = правка канона `ff_summary.json` отдельным CHANGE, не этот пакет. `ff_summary.json` **read-only** (§18): скобки в шаблоне `Риски (Кто высказал /Вероятность /Влияние):` **не** убирать.

После ответа LLM и **до** `validate_summary_sections` нормализовать строку-заголовок известной секции: `Имя` ∈ `_SECTION_NAMES` + опционально `\s*\([^)]*\)` + `:` → ровно `{Имя}:`. Нормализация — все шесть имён (защита, если модель повесит скобки не только на «Риски»). `validate_summary_sections` **не** ослаблять: exact `Имя:`, запрет `##`. Тело буллитов не трогать. На диск — `Риски:`, не `Риски (…):`. Пустой текст / отсутствие секции по-прежнему False → pending, файл не писать (§7 Шаг 3 п.6).

Пустой раздел = заголовок без буллитов (норма промпта). Пустой ответ LLM целиком = ошибка, pending.

Лимит транскрипта: чанкинг по границам реплик, `CHUNK_CHAR_LIMIT=30000` (как в коде `registry.py`) → один вызов, если влезает; иначе последовательная суммаризация частей + финальный merge тем же промптом. Детали IAC на `HF:plan`. Обрезка молча **запрещена**. `CHUNK_CHAR_LIMIT=30000` этим пакетом **не** менять.

Клиентский timeout **LLM** (контур `summarizer.py`, не HTTP KTalk):

| | |
|---|---|
| Default | **540** секунд |
| Опора | 540 ≈ 5.3× типичной генерации 101с («Кирилл 1-1», 19.9К симв) и ≈1.8× худшего разброса шлюза (>300с при пороге 300с). 540 < интервал крона 600с (~60с запас до следующего тика). 600 в default **не** оставлять: при 10-мин кроне timeout=интервал → `lock_held` на каждом тике длинной встречи. 900 в default **не** ставить. История порогов: 60 (§22 до фикса) → 300 (AC-024) → 600 (AC-026 / §23) → **540** (этот пакет, AC-027) |
| Override | process env `MFKT_LLM_TIMEOUT` (не YAML, не per-tool `.env`); оператор может поставить 900 без нового поезда |
| Чтение | хелпер в `default_llm_caller` **при вызове**, не только на import модуля |
| SDK retries | `OpenAI(..., timeout=<sec>, max_retries=0)` **без смены**. Ретраи саммари = pending backoff §7 (`PENDING_BACKOFF_MINUTES`), не SDK. `max_retries=1` / SDK default 2 **запрещены**: 540×(1+2) ≈ 1620с стены на одну встречу |
| HTTP KTalk | `ktalk_client.py` timeout 60с — **другой** контур; не трогать и не «выравнивать» с LLM |

Таймаут/пусто LLM → pending, файл не писать (§7 Шаг 3 п.6) — контракт **без смены**.

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
    ktalk_client.py    # httpx+retry; GET /api/recordings (не Domain/v2); нет GET /summary, нет /participants
    filename.py        # копия контракта MFF, не import movefromff
    registry.py
    writer.py          # atomic tmp+replace, rollback
    summarizer.py      # единственный автор summary.md; ff_summary.json + LLM; канон заголовков до validate; timeout 540с, max_retries=0
    dedup_ff.py        # §10 по файлам NewMeetings
    tg.py
    lock.py
    logger.py
  tests/
    test_filename.py           # regex = PFS _FILENAME_RE
    test_registry.py
    test_pending_backoff.py
    test_ktalk_client.py       # mock HTTP; фикстуры `/api/recordings` + tracks/chunks; /summary, Domain/v2, /Recordings/, /participants не вызываются
    test_summarizer.py         # mock LLM, секции _SECTION_NAMES; канон `Риски (…):`→`Риски:`; timeout=540 / max_retries=0; CHUNK=30000
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

Q-4 закрыт Сашей 15.10: как MFF. Факт постановки: job `4e689c13ae01` (`script=movefromkeytalk_sync.sh`, `no_agent`) после «Зарускай кроны» 15.10. Исторический expr `5 8-19 * * 1-5` (каждый час в :05, раб. дни 08–19). Имя job на диске 20.10 всё ещё «каждые 2ч» — стигма, не канон.

**v0.2.5 (этот пакет, оператор 19.10):** expr существующего job → `*/10 8-19 * * 1-5` (каждые 10 мин, раб. дни 08:00–19:50). Новый job **не** создавать. `no_agent`, `script`, wrap `error_bus_wrap.sh --tool MoveFromKeyTalk`, `enabled`, id, origin/deliver — **без смены**. Имя/`schedule.display` выровнять под 10 мин (тот же файл). Другие jobs не трогать.

Обёртка: `error_bus_wrap.sh --tool MoveFromKeyTalk` (живой `~/.hermes/scripts/movefromkeytalk_sync.sh` → wrap → пакетный `bin/movefromkeytalk_sync.sh`). Крон без полного YAML §12 не «чинит сам» и не глотает `Missing required config` (норма: CLI exit 2 + ErrorBus, не тихий `last_status=ok`). `lock_held` (exit 2) при занятом flock → ErrorBus; шум при 10-мин шаге **принимаем** (оператор 19.10). Wrap `0|1→0` **не** расширять на 2, чтобы заглушить шум.

Переключение ingest: крон `vm_movefromff` на 2026-10-19 всё ещё `enabled: true` (dual-ingest живой). Выключение — AC-018, `depends: operator:ставь кроны`. Код MoveFromFF не патчить. `HF:impl` этого пакета пишет **только** expr/display/name job `4e689c13ae01` в `jobs.json` (§24); остальные jobs и `vm_movefromff` — нет.

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
- `~/USERTOOLS/ProtocolFromSummary/**` включая `_gen_ff_summary.py`, `summary_parser._SECTION_NAMES` / `_FILENAME_RE`, **`scripts/ofc_sync.py`**, **`protocolfromsummary/ofc_error_bus.py`**.
- `~/USERTOOLS/MarkObjectsFromSummary/**`, `MofsIndex/**`, `FirefliesAutojoin/**`.
- **ObsidianFromConfluence (OFC).** Каталога `~/USERTOOLS/ObsidianFromConfluence/` **нет** (факт 19.10 REV:plan, сверка 20.10). Живой код OFC лежит **внутри PFS** (`scripts/ofc_sync.py`, `protocolfromsummary/ofc_error_bus.py`) — уже под запретом строки PFS. ТЗ OFC: `TZ/ObsidianFromConfluence/ObsidianFromConfluence_TZ.md` (контракт: не пишет в `NewMeetings/`). Этим пакетом **не** создавать `USERTOOLS/ObsidianFromConfluence/` (`[NEW-ENTITY]` дерева не заводить).
- `Registries/prompts/ff_summary.json` (только чтение).
- `Meetings/NewMeetings/_registry_meet.json` и `_registry_meet.md`.
- Живые `* - summary.md` / `* - transcript.md`, которые MFKT не создавал.
- Gateway, ядро `~/hermes-agent`, канбан, чужие скиллы телом.
- `jobs.json` без «ставь кроны», **кроме** точечной правки expr/display/name существующего job `4e689c13ae01` пакетом §24 (оператор 19.10; новый job не создавать; `vm_movefromff` — AC-018).
- Per-tool `.env`, dual-read, литералы путей/моделей/токенов.
- KTalk summary API (не вызывать).
- Интеграторский `GET /api/Domain/recordings/v2` (не fallback персональному `X-Auth-Token`).
- `GET /api/recordings/{id}/participants` (404; состав из list/detail).
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

## §20 CHANGE `ktalk-kontur-poluchenie-transkriptov-avtonomnaya` (2026-10-20)

Пакет CHANGE. Наследник abort `ktalk-kontur-v-protsess` (19.10 16:02: Саша остановил поезд из‑за проблем пайплайна dead-pid / wrong-role / empty-result; мастер v0.2.0 + `HF-plan.md` + `REV:plan` APPROVE уже были; `HF:backup` / `HF:impl` не стартовали). Код / YAML / schema / `jobs.json` / манифест на этой фазе **не** пишутся.

**Задача Саши (19.10):** починить по канону получение транскрипта из KTalk → автономная самаризация → публикация в `WorkVault/Meetings/NewMeetings/`. ProtocolFromSummary / ObsidianFromConfluence / MarkObjectsFromSummary не трогать.

Нормы §1–§19 и AC-001…018 **остаются**. Этот ход не пересматривает продукт: (1) привязывает слаг-наследник; (2) чинит путь OFC в §18 (замечание REV:plan 19.10, отложено на `TZ:patch`); (3) сверяет I1-C с диском **20.10** — дыра жива.

**I1-A ingest.** `current` (20.10): dual-крон жив — `vm_movefromff.enabled=true` (`expr: 5 8-19 * * 1-5`) и MFKT `4e689c13ae01.enabled=true` (`last_status=ok`, `last_run_at=2026-10-19T19:05:58+03:00`, `repeat.completed=24`). `target`: новые встречи только из KTalk; крон MFF выключен (AC-018 O, `depends: operator:ставь кроны`). Код MFF **не** патчить; DECOMM инструмента — чужой поезд.

**I1-B саммари.** `current`: `summarizer.py` + `ff_summary.json`; клиент режет `/summary`. `target`: саммари first-class продукт MFKT; KTalk `/summary` не вызывать (AC-015). Не fallback.

**I1-C конфиг.** `current` (сверка 20.10, не гипотеза): YAML `tools.move_from_keytalk` = `enabled`, `TOOL_DIR`, `MEETINGS_DIR`, `TELEGRAM_CHAT_ID`, `KTALK_BASE_URL=https://tutu.ktalk.ru/` — **нет** `LOGS_PATH`, `PROMPT_PATH`, `KTALK_USER_KEY`. Schema: `LOGS_PATH` именован; `KTALK_BASE_URL` / `KTALK_USER_KEY` / `PROMPT_PATH` только `additionalProperties`. `_MFKT_CONFIG_KEYS` в `config.py` уже 7 ключей. `load_tool_config(..., required=True)` → **`KeyError`**; `run()` ловит только `RuntimeError` (`__main__.py`) → uncaught → Python exit **1**; `bin/movefromkeytalk_sync.sh` мапит `0|1 → 0`. Каталога `~/WorkVault/_meta/MoveFromKeyTalk/` нет. `USERTOOLS/MoveFromKeyTalk/state/_registry.json` нет. `target`: канон §12 заполнен (Q-2 значение 15.10); schema именует `KTALK_*`/`PROMPT_PATH`; `KeyError` и `RuntimeError` missing-config → CLI exit **2** + ErrorBus. Обёртка `0|1→0` **не** менять смысл. YAML/schema пишет **ORCH:shared-state**. Ловлю `KeyError` в `run()` пишет **`HF:impl`** (обязан, не «если IAC»).

**I1-D низ / путь OFC.** `current`: каталога `~/USERTOOLS/ObsidianFromConfluence/` нет. Живой OFC: `~/USERTOOLS/ProtocolFromSummary/scripts/ofc_sync.py` и `protocolfromsummary/ofc_error_bus.py`. ТЗ OFC: `TZ/ObsidianFromConfluence/ObsidianFromConfluence_TZ.md` (не пишет в `NewMeetings/`). `target`: PFS / MOFS / OFC / MofsIndex **без правок**; не создавать дерево `USERTOOLS/ObsidianFromConfluence/`; защита «не трогать» = файлы OFC внутри PFS + `MarkObjectsFromSummary/**` + `MofsIndex/**`. Имена и `_SECTION_NAMES` те же (AC-017).

Reuse-first: промпт, папка `NewMeetings/`, PFS-парсер, ErrorBus, unified config, уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` (Q-5). Новой сущности этот пакет не создаёт. `[NEW-ENTITY]` `entities.api_ktalk` **не** заводить (Q-5 отклонено 15.10).

Оценка объёма `HF:impl` (факт для оркестратора, **не** команда skip LIGHT / смены кейса): код саммари/клиента/`/summary`-бан уже на диске; YAML+schema — ORCH; выключение MFF-крона — operator AC-018. `HF:impl` **обязан** закрыть fail-loud: `run()` ловит `KeyError` **и** `RuntimeError` missing-config → exit 2; pytest на отсутствующий ключ YAML → exit 2, не 1. Два файла кода пакета: `movefromkeytalk/__main__.py` + `tests/test_config_unified.py`. План предыдущего поезда `dev/ktalk-kontur-v-protsess/HF-plan.md` (17 IAC, `REV:plan` APPROVE) — **ориентир**; этот поезд пишет свой `HF-plan.md` (фаза обязательна, G5).

Новых `Q-n` нет.

### Критерии приёмки (AC) пакета

Класс S по умолчанию. Показ AC ≠ ожидание. Новых якорей нет: пакет несёт **AC-014…018** (§19) + уточнение **AC-009** (путь OFC). Корпус AC-001…013 в силе.

| ID | Класс | Формулировка |
|---|---|---|
| AC-014 | S | Новые пары `transcript\|summary` в `NewMeetings/` пишет только MFKT из KTalk REST. В коде пакета нет Fireflies GraphQL. MFF/PFS/MOFS/OFC без diff этого пакета (прирост vs baseline). OFC = файлы внутри PFS, не отдельное дерево USERTOOLS. |
| AC-015 | S | `summary.md` всегда из `summarizer.py` + `PROMPT_PATH`→`ff_summary.json`. Клиент KTalk не делает `GET .../summary`. |
| AC-016 | S | YAML `tools.move_from_keytalk` с непустыми `LOGS_PATH`, `PROMPT_PATH`, `KTALK_USER_KEY=talkusr.c1e5b36a7f8b471d8d2437357dc125bc` (§12). Schema именует `KTALK_BASE_URL`, `KTALK_USER_KEY`, `PROMPT_PATH`. Отсутствие `_MFKT_CONFIG_KEYS` → `KeyError`/`RuntimeError` в `run()` → CLI exit 2 + ErrorBus, не wrap→ok. YAML/schema — ORCH; fail-loud в коде — `HF:impl`. |
| AC-017 | S | Контракт §8 (`_FILENAME_RE`, шесть `_SECTION_NAMES` без `##`, `meeting_id`=stem) без изменений. |
| AC-018 | O | `depends: operator:ставь кроны`. Крон `vm_movefromff` выключен. Код MoveFromFF без diff. Job MFKT `4e689c13ae01` не переписывать. |

## §21 BUGFIX-LIGHT `ktalk-kontur-pravilnyj-put-api-recordings` (2026-10-20)

Пакет BUGFIX-LIGHT. Диагноз: `dev/ktalk-kontur-pravilnyj-put-api-recordings/_fix_plan_20261020.md` (`GATE:diagnose-review` auto). Код / YAML / schema / `jobs.json` / манифест / крон на этой фазе **не** пишутся.

**Root cause (диск + живой API 20.10):** клиент ходит по интеграторскому `GET /api/Domain/recordings/v2` → 403 для персонального `X-Auth-Token`. Рабочий путь пользовательского контура — `GET /api/recordings` → 200 `{"recordings":[...]}`. Парсер под другой JSON (`start` / `sentences` / `authorKey` talkusr) отбросит все записи и отдаст пустой транскрипт даже после смены URL. Мастер §4/§7 до v0.2.1 канонизировал неверный путь. Чинить клиент **и** норму одним багфиксом.

Это **не** дыра I1-C (соседний CHANGE `ktalk-kontur-poluchenie-transkriptov-avtonomnaya` уже `GATE:done`: YAML 7 ключей, `run()` ловит `KeyError`). Живой стоп — Шаг 1 ping. Крон `4e689c13ae01` 20.10 08:05:59: exit 3, stderr `KTalk API scope insufficient (403)`.

Нормы §1–§20, AC-001…018, Q-1…Q-5, §18 «не трогать» **остаются**. Этот пакет меняет только канон HTTP-контура и парсера (§4 таблица путей, §7 список/окно/фильтр, контракт duration/transcript).

**I1-API путь.** `current`: `list_recordings` / `ping` → `/api/Domain/recordings/v2` + `page-token`; `fetch_metadata` → `/api/Recordings/{key}` (заглавная R) + `/participants` при ≥6; фильтр `user_key in {author_key, organizer_key}`; дата из `start`; транскрипт из `sentences`. `target`: таблица §4; пагинация `skip`+`top`≤100; окно — клиент по `createdDate`; фильтр §7 (UUID `createdBy.login` не дропает); metadata lowercase `/api/recordings/{id}`; `/participants` не вызывать; транскрипт `tracks[].chunks[]` (fallback плоский `sentences` оставить для чужого стенда).

**I1-DURATION.** API `duration` — секунды (якорь «Кирилл 1-1» 1363с). Контракт экосистемы / реестр — минуты: `duration_minutes = round(sec/60)` (1363 → 23). Не писать сырые секунды в `duration_minutes`.

`HF:impl` (после `TZ:finalize` / `GATE:take-into-work`): только `movefromkeytalk/ktalk_client.py` + `tests/test_ktalk_client.py`. Writer / `format_transcript_line`, `__main__`, YAML, крон — не трогать (контракт dataclass `KTalkRecording` / `TranscriptSentence` именами полей не менять). Скилл — одна строка про `/api/recordings` на `HF:docs-handoff`.

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` **не** заводить (Q-5 отклонено 15.10). Job `4e689c13ae01` не переписывать. AC-018 — чужой operator-hold, не этот фикс.

Новых `Q-n` нет.

### IAC LIGHT (`HF:plan` skip по рецепту BUGFIX-LIGHT)

1. Pytest `tests/test_ktalk_client.py` (+ полный `tests/` пакета): мок `GET /api/recordings` 200 `{recordings:[...]}`; в `request_log` нет `Domain`, `/recordings/v2`, `/Recordings/` (заглавная), `/participants`, `/summary`; запись с `id` / `createdDate` / `duration:1363` / `createdBy.login=<uuid>` / `participants[].userInfo` → не `None`; `duration_minutes≈23`; UUID-only `createdBy` не дропается; транскрипт `tracks[].chunks[]` → ≥1 `TranscriptSentence` с ФИО и `HH:MM:SS`; 401 на `/api/recordings` → `KTalkAuthError`.
2. Соседи: прирост diffstat 0 vs baseline (команда как в предыдущем MFKT `HF-plan`; non-git — та же sha-функция). YAML / cron / `jobs.json` / манифест без diff этого пакета.
3. Смоук optional: `--mode test --dry-run` при живом ключе exit ≠ 3; без ключа — skip, не fail пакета (§14).

### Критерии приёмки (AC) пакета

Класс S по умолчанию. Показ AC ≠ ожидание. Корпус AC-001…018 в силе.

| ID | Класс | Формулировка |
|---|---|---|
| AC-019 | S | Список и ping: `GET /api/recordings`. `Domain/recordings/v2` в `request_log` тестов нет. Живой ping с персональным ключом не 403 (смоук или skip). |
| AC-020 | S | Парсер ест `recordings[]` с `id` / `createdDate` / `duration` (сек) / `createdBy` / `participants.userInfo`. Запись с только этими полями не `None`. Talkusr-фильтр не дропает UUID-only `createdBy.login`. |
| AC-021 | S | Транскрипт из `tracks[].chunks[]`; пусто → pending, не completed. `/summary` не вызывается (AC-015 без изменений). |
| AC-022 | S | Metadata `GET /api/recordings/{id}` lowercase; `/participants` не вызывается. |
| AC-023 | S | Пагинация `skip`+`top`≤100; окно дат — фильтр клиента по `createdDate` (query `start-from` / `start-to` / `page-token` не слать). YAML / cron / `.env` / манифест без diff этого пакета. |

## §22 BUGFIX-LIGHT `ktalk-kontur-samari-taimaut-llm-dlinnyj-transkript` (2026-10-20)

Пакет BUGFIX-LIGHT. Диагноз: `dev/ktalk-kontur-samari-taimaut-llm-dlinnyj-transkript/_fix_plan_20261020.md` (`GATE:diagnose-review` auto). Код / YAML / schema / `jobs.json` / манифест / крон на этой фазе **не** пишутся.

**Root cause (диск 20.10):** транскрипты KTalk уже качаются. Самари длинной встречи («Кирилл 1-1», `5gm4NgR7bPdmcJC6eEnm`, 19907 симв.) падает: `LLM_TIMEOUT_DEFAULT=60` + SDK `max_retries` default 2 → ~180с стены; jsonl `summarize_error` `Request timed out.` (`APITimeoutError`). Чанкование не срабатывает: 19907 < `CHUNK_CHAR_LIMIT=30000`, вся встреча уходит одним запросом и при таймауте теряется целиком (pending, файлов нет).

Это **не** дыра пути API (соседний BUGFIX-LIGHT `ktalk-kontur-pravilnyj-put-api-recordings`, master v0.2.2, AC-019…023: `GET /api/recordings`, jsonl `download_ok`). Живой стоп — **Шаг 3 п.6 LLM**, не ping и не парсер транскрипта.

Нормы §1–§21, AC-001…023, Q-1…Q-5, §18 «не трогать» **остаются**. Этот пакет добавляет в §11 явное число LLM-timeout и `max_retries=0`. `CHUNK_CHAR_LIMIT=30000` **без смены**. Чанки в этом пакете не резать.

**I1-TIMEOUT.** `current`: `summarizer.py` `LLM_TIMEOUT_DEFAULT = int(os.environ.get("MFKT_LLM_TIMEOUT", "60"))`; `OpenAI(..., timeout=LLM_TIMEOUT_DEFAULT)` без `max_retries` → SDK default 2. `target`: default **300** секунд; timeout читать хелпером в `default_llm_caller` при вызове (не только на import); `OpenAI(..., timeout=<sec>, max_retries=0)`. Ретраи саммари = pending backoff §7, не SDK.

**Решение `max_retries`:** **0**, не 1 и не SDK default 2. При timeout 300с SDK-ретраи дают 600–900с стены на одну встречу; повтор уже есть в `PENDING_BACKOFF_MINUTES`.

`HF:impl` (после `TZ:finalize` / `GATE:take-into-work`): только `movefromkeytalk/summarizer.py` + `tests/test_summarizer.py`. `registry.py` / `CHUNK_CHAR_LIMIT`, `ktalk_client.py` (HTTP 60с), `__main__.py` (pending на summarize_error), YAML, крон — не трогать.

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` **не** заводить (Q-5 отклонено 15.10). Job `4e689c13ae01` не переписывать. AC-018 — чужой operator-hold.

Новых `Q-n` нет.

### IAC LIGHT (`HF:plan` skip по рецепту BUGFIX-LIGHT)

1. Pytest `tests/test_summarizer.py` (+ полный `tests/` пакета, offline, AC-008): default timeout 300; мок `OpenAI` видит `timeout=300` и `max_retries=0`; `MFKT_LLM_TIMEOUT=420` → в конструктор 420; `CHUNK_CHAR_LIMIT==30000`; существующие тесты секций/merge зелёные; мок `APITimeoutError` / `TimeoutError("Request timed out.")` **не** превращается в `"LLM summary failed section validation"`. Живой шлюз для pytest не обязателен.
2. Соседи: прирост diffstat 0 vs baseline (команда как в предыдущем MFKT `HF-plan`; non-git — та же sha-функция). YAML / cron / `jobs.json` / манифест / `ktalk_client.py` без diff этого пакета.
3. Смоук optional: `--mode test` на `5gm4NgR7bPdmcJC6eEnm` / окно с «Кирилл 1-1» (~20K) не `Request timed out.`; пара `transcript|summary` в `NewMeetings/` либо `skipped_ff` по §10, не pending-timeout. Без ключа — skip, не fail пакета (§14).

### Не трогать (этот пакет)

Master §18 целиком, плюс:

- `CHUNK_CHAR_LIMIT` / `registry.py`;
- `ktalk_client.py` (HTTP 60с на KTalk — другой контур);
- `__main__.py` (pending на summarize_error оставляем: пустой/timeout → pending, файл не писать);
- `MoveFromFF/**`, PFS/** (включая OFC внутри PFS и `_gen_ff_summary.py`), MOFS, MofsIndex, FirefliesAutojoin, `ff_summary.json`;
- `jobs.json`, крон `4e689c13ae01`, `vm_movefromff` (AC-018 / «ставь кроны»);
- YAML/schema, per-tool `.env`, dual-read, литералы токенов/моделей;
- KTalk `/summary`, `X-API-Key`, runtime `ktalk-cli`;
- `entities.api_ktalk`; дерево `USERTOOLS/ObsidianFromConfluence/`;
- флак `section validation` на других recording_key — не этот корень;
- чужие поезда `ktalk-kontur-pravilnyj-put-api-recordings` / `ktalk-kontur-poluchenie-transkriptov-avtonomnaya` — не откатывать пути API и fail-loud.

### Критерии приёмки (AC) пакета

Класс S по умолчанию. Показ AC ≠ ожидание. Корпус AC-001…023 в силе.

| ID | Класс | Формулировка |
|---|---|---|
| AC-024 | S | Default LLM timeout 300с (`MFKT_LLM_TIMEOUT` override, process env). `OpenAI` в summarizer с `max_retries=0`. Timeout читается при вызове, не только на import. Pytest: конструктор получает timeout=300 и max_retries=0; env override доходит до конструктора; `CHUNK_CHAR_LIMIT` остаётся 30000. Живой шлюз для pytest не обязателен. YAML / cron / `.env` / манифест / `ktalk_client.py` / `registry.py` без diff этого пакета. |

## §23 BUGFIX-LIGHT `ktalk-kontur-samari-dlinnye-transkripty-taimaut` (2026-10-20)

Пакет BUGFIX-LIGHT. Диагноз: `dev/ktalk-kontur-samari-dlinnye-transkripty-taimaut/_fix_plan_20261020.md` (`GATE:diagnose-review` auto). Код / YAML / schema / `jobs.json` / манифест / крон / `ff_summary.json` на этой фазе **не** пишутся.

**Root cause (диск 20.10, два независимых стопа на Шаге 3 п.6 LLM).** Транскрипт уже качается (`download_ok` для встреч 19.10). Блокер — самаризация.

**RC-1 (детерминированный).** `validate_summary_sections` требует строку ровно `Риски:` (regex `(^|\n)Риски:\s*$`). Канон промпта `Registries/prompts/ff_summary.json` v0.2.0 в шаблоне отдаёт `Риски (Кто высказал /Вероятность /Влияние):`. Модель следует шаблону → валидатор False → `RuntimeError("LLM summary failed section validation")` → pending, файла нет. Живой jsonl Кирилл `5gm4NgR7bPdmcJC6eEnm` 06:17:55Z / 06:28:57Z / 06:41:50Z после v0.2.3. Соседний поезд `ktalk-kontur-samari-taimaut-llm-dlinnyj-transkript` закрыл 60→300 + `max_retries=0` и **не** закрыл RC-1 (смотрел короткий мок `_valid_summary()` с `Риски:`).

**RC-2 (volatile).** Default `MFKT_LLM_TIMEOUT=300` на пике не хватает. Замер «Кирилл 1-1» (19.9К симв, 1 чанк): 300с → `httpx.ReadTimeout` / `openai.APITimeoutError` без ответа; 900с → ответ за **101.6с**. Порог 300с (пакет §22 / AC-024) недостаточен. `max_retries=0` **оставить**.

Нормы §1–§22, AC-001…024, Q-1…Q-5, §18 «не трогать» **остаются**. AC-024 = история пакета §22 (60→300). `CHUNK_CHAR_LIMIT=30000` **без смены**. Промпт **не** править.

**I1-HEADING.** `current`: LLM-выход с `Риски (Кто высказал /Вероятность /Влияние):` падает на строгом `validate_summary_sections`. `target`: после LLM и **до** validate канонизировать `Имя` ∈ `_SECTION_NAMES` + опц. `\s*\([^)]*\)` + `:` → ровно `{Имя}:`. Валидатор остаётся exact `Имя:` без `##`. На диск — `Риски:`, не скобки. `ff_summary.json` read-only (скобки в шаблоне — hint формата буллитов). Не ослаблять валидатор так, чтобы на диск ушло `Риски (…):`.

**I1-TIMEOUT.** `current`: default **300** (§11/§22). `target`: default **600** секунд (2× сорвавшегося порога 300с, ~6× от замера 101.6с). 900 в default не ставить (часовой крон AC-011). Override `MFKT_LLM_TIMEOUT` без смены. `OpenAI(..., timeout=<sec>, max_retries=0)` без смены.

`HF:impl` (после `TZ:finalize` / `GATE:take-into-work`): только `movefromkeytalk/summarizer.py` + `tests/test_summarizer.py`. `registry.py` / `CHUNK_CHAR_LIMIT`, `ktalk_client.py` (HTTP 60с), `__main__.py`, YAML, крон, `ff_summary.json`, PFS/MOFS — не трогать.

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` **не** заводить (Q-5 отклонено 15.10). Job `4e689c13ae01` не переписывать. AC-018 — чужой operator-hold.

Новых `Q-n` нет.

### IAC LIGHT (`HF:plan` skip по рецепту BUGFIX-LIGHT)

1. Pytest `tests/test_summarizer.py` (+ полный `tests/` пакета, offline, AC-008): default timeout **600**; мок `OpenAI` видит `timeout=600` и `max_retries=0`; `MFKT_LLM_TIMEOUT=420` → в конструктор 420; `CHUNK_CHAR_LIMIT==30000`; мок шаблона промпта (`Риски (Кто высказал /Вероятность /Влияние):` + остальные пять `X:`) → `summarize_transcript` **не** бросает section validation; в результате есть ровно `Риски:` и **нет** скобочного заголовка; точный `Риски:` (старый `_valid_summary`) без регресса; нет секции «Риски» / есть `##` — по-прежнему reject; мок `APITimeoutError` / `TimeoutError("Request timed out.")` **не** маскируются под `"LLM summary failed section validation"`. Живой шлюз для pytest не обязателен.
2. Соседи: прирост diffstat 0 vs baseline (команда как в предыдущем MFKT `HF-plan`; non-git — та же sha-функция). `ff_summary.json` sha без изменений. YAML / cron / `jobs.json` / манифест / `ktalk_client.py` / `registry.py` без diff этого пакета.
3. Смоук optional: `--mode test` на `5gm4NgR7bPdmcJC6eEnm` / окно «Кирилл 1-1» (~20K) не timeout и не `LLM summary failed section validation`; в записанном summary есть `Риски:` без скобочного хвоста. Без ключа — skip, не fail пакета (§14).

### Не трогать (этот пакет)

Master §18 целиком, плюс:

- `Registries/prompts/ff_summary.json` (read-only; скобки в шаблоне остаются);
- `CHUNK_CHAR_LIMIT` / `registry.py`;
- `ktalk_client.py` (HTTP 60с на KTalk — другой контур);
- `__main__.py` (pending на summarize_error оставляем: пустой/timeout/невалидно → pending, файл не писать);
- `MoveFromFF/**`, PFS/** (включая OFC внутри PFS, `_gen_ff_summary.py`, `summary_parser._SECTION_NAMES`), MOFS, MofsIndex, FirefliesAutojoin;
- `jobs.json`, крон `4e689c13ae01`, `vm_movefromff` (AC-018 / «ставь кроны»);
- YAML/schema, per-tool `.env`, dual-read, литералы токенов/моделей;
- KTalk `/summary`, `X-API-Key`, runtime `ktalk-cli`;
- `entities.api_ktalk`; дерево `USERTOOLS/ObsidianFromConfluence/`;
- чужие поезда `ktalk-kontur-samari-taimaut-llm-dlinnyj-transkript` / `ktalk-kontur-pravilnyj-put-api-recordings` / `ktalk-kontur-poluchenie-transkriptov-avtonomnaya` — не откатывать 0.2.3 (`max_retries=0`, хелпер timeout) и пути API.

### Критерии приёмки (AC) пакета

Класс S по умолчанию. Показ AC ≠ ожидание. Корпус AC-001…024 в силе.

| ID | Класс | Формулировка |
|---|---|---|
| AC-025 | S | LLM-выход с `Риски (Кто высказал /Вероятность /Влияние):` канонизируется в `Риски:` **до** `validate_summary_sections`. Фаза validate summarizer **принимает** этот скобочный заголовок как вход (через канонизацию); сама функция validate остаётся exact шесть `_SECTION_NAMES` без `##`. На диск — `Риски:`, не скобки. Pytest: мок шаблона промпта проходит `summarize_transcript` и отдаёт `Риски:` без скобочного хвоста. `ff_summary.json` / PFS / MOFS без diff. |
| AC-026 | S | Default LLM timeout **600с** (`MFKT_LLM_TIMEOUT` override). `OpenAI` с `max_retries=0`. Pytest: конструктор timeout=600 и max_retries=0; env override доходит; `CHUNK_CHAR_LIMIT=30000`. Живой шлюз для pytest не обязателен. YAML / cron / `.env` / манифест / `ktalk_client.py` / `registry.py` без diff этого пакета. |

## §24 CHANGE-LIGHT `ktalk-kontur-schedule-10min-timeout-540` (2026-10-20)

Пакет CHANGE-LIGHT (рецепт уже LIGHT; архитектор кейс **не** меняет, G5). Код / YAML / schema / манифест / `.env` / крон-обёртка на этой фазе **не** пишутся.

**Задача оператора (Саша, 19.10):** проверка появления новых встреч каждые 10 мин (раб. дни 08:00–19:59) + клиентский LLM timeout **540с**. Форматы §8 и корпус AC-001…026 **без пересмотра продукта**.

Это конфигурация **существующего** job `4e689c13ae01`, не новый крон и не `[NEW-ENTITY]`. `.env` / манифест не трогать. Факт объёма (не команда skip/set-case): ≤3 файла кода+тест — `jobs.json` (expr существующего job) + `summarizer.py` + `test_summarizer.py`.

**Обоснование (оператор 19.10, не гипотеза):**

- Листинг `GET /api/recordings` — no-LLM; частая проверка дёшева, токены не тратятся, если новых записей нет.
- Timeout 540с покрывает длинные транскрипты: живой замер 19.9К симв → ~101с генерация; разброс шлюза >300с при пороге 300с. 540 ≈ 5.3× типичной, ≈1.8× худшего. 540 < интервал крона 600с (~60с запас до следующего тика).
- Self-overlap исключён: non-blocking lock (`lock.py`, `LOCK_EX|LOCK_NB`); второй прогон при занятом lock → `lock_held`, CLI exit 2, параллельной LLM-нагрузки нет. Шум `lock_held` в ErrorBus при частых проверках — **принимаем** (оператор: «шум пусть приходит, пока что»). `lock.py` и маппинг wrap `0|1→0` **не** менять, чтобы заглушить шум.

Нормы §1–§23, AC-001…026, Q-1…Q-5, §18 «не трогать» **остаются** как корпус. AC-011 = история постановки job 15.10 (`5 8-19 * * 1-5`); AC-026 = история порога 600с пакета §23. Операционный default этого пакета — §11/§15 и AC-027/028.

**I1-SCHEDULE.** `current` (диск 20.10): job `4e689c13ae01` `enabled: true`, `no_agent: true`, `script: movefromkeytalk_sync.sh`, `expr: 5 8-19 * * 1-5` (каждый час в :05, раб. дни 08–19). Имя job на диске всё ещё «каждые 2ч» — стигма. Wrap: `~/.hermes/scripts/movefromkeytalk_sync.sh` → `error_bus_wrap.sh --tool MoveFromKeyTalk`. `target`: `schedule.expr` / `schedule.display` / `schedule_display` = `*/10 8-19 * * 1-5` (каждые 10 мин, раб. дни 08:00–19:50). `no_agent`, `script`, wrap, `enabled`, `id`, origin/deliver — **без смены**. Имя job выровнять под 10 мин (тот же файл, не новый job). Другие jobs не трогать. `vm_movefromff` — AC-018, не этот пакет.

**I1-TIMEOUT.** `current`: default **600** (§11/§23/AC-026). `target`: default **540** секунд. Override `MFKT_LLM_TIMEOUT` без смены. Чтение при вызове без смены. `OpenAI(..., timeout=<sec>, max_retries=0)` без смены.

`HF:impl` (после `TZ:finalize` / `GATE:take-into-work`): три файла LIGHT:

1. `~/.hermes/cron/jobs.json` — только job `4e689c13ae01`: expr / display / name.
2. `~/USERTOOLS/MoveFromKeyTalk/movefromkeytalk/summarizer.py` — `LLM_TIMEOUT_DEFAULT` / хелпер default **540**.
3. `~/USERTOOLS/MoveFromKeyTalk/tests/test_summarizer.py` — ассерты 600→540 (иначе AC-008 красный).

Скилл — одна строка про 10 мин + 540с на `HF:docs-handoff`.

Перед правкой `jobs.json` исполнитель кладёт копию в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (контур A). Фаза `HF:backup` в recipe LIGHT отсутствует — это локальная улика impl, не add/skip фазы.

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` **не** заводить (Q-5 отклонено 15.10). Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять.

Новых `Q-n` нет. Q-4 (расписание 15.10 `5 8-19 * * 1-5`) не переоткрывать: оператор 19.10 сменил expr существующего job.

### IAC LIGHT (`HF:plan` skip по рецепту CHANGE-LIGHT)

1. Pytest `tests/test_summarizer.py` (+ полный `tests/` пакета, offline, AC-008): default timeout **540**; мок `OpenAI` видит `timeout=540` и `max_retries=0`; `MFKT_LLM_TIMEOUT=420` → в конструктор 420; `CHUNK_CHAR_LIMIT==30000`; канон `Риски (…):`→`Риски:` без регресса (AC-025). Живой шлюз для pytest не обязателен.
2. Job `4e689c13ae01` в `~/.hermes/cron/jobs.json`: `schedule.expr` == `*/10 8-19 * * 1-5`; `no_agent==true`; `script` без смены; остальные jobs без прироста vs baseline. `ktalk_client.py` / `registry.py` / `lock.py` / `ff_summary.json` sha без изменений.
3. Соседи: прирост diffstat 0 vs baseline (команда как в предыдущем MFKT `HF-plan`; non-git — та же sha-функция). YAML / `.env` / манифест / `vm_movefromff` без diff этого пакета.

### Не трогать (этот пакет)

Master §18 целиком, плюс:

- `CHUNK_CHAR_LIMIT` / `registry.py`;
- `ktalk_client.py` (HTTP 60с на KTalk — другой контур);
- `lock.py` / поведение `lock_held` / wrap `0|1→0` (шум ErrorBus принимаем);
- `__main__.py` (pending на summarize_error оставляем: пустой/timeout/невалидно → pending, файл не писать);
- `MoveFromFF/**`, PFS/** (включая OFC внутри PFS, `_gen_ff_summary.py`, `summary_parser._SECTION_NAMES`), MOFS, MofsIndex, FirefliesAutojoin, `ff_summary.json`;
- другие jobs кроме expr/display/name `4e689c13ae01`; `vm_movefromff` (AC-018 / «ставь кроны»);
- YAML/schema, per-tool `.env`, dual-read, литералы токенов/моделей;
- KTalk `/summary`, `X-API-Key`, runtime `ktalk-cli`;
- `entities.api_ktalk`; дерево `USERTOOLS/ObsidianFromConfluence/`;
- чужие поезда `ktalk-kontur-samari-dlinnye-transkripty-taimaut` / `ktalk-kontur-samari-taimaut-llm-dlinnyj-transkript` / `ktalk-kontur-pravilnyj-put-api-recordings` — не откатывать канон заголовков, `max_retries=0` и пути API.

### Критерии приёмки (AC) пакета

Класс S по умолчанию. Показ AC ≠ ожидание. Корпус AC-001…026 в силе (AC-011/026 — история job 15.10 и порога 600с).

| ID | Класс | Формулировка |
|---|---|---|
| AC-027 | S | Default LLM timeout **540с** (`MFKT_LLM_TIMEOUT` override). `OpenAI` с `max_retries=0`. Timeout читается при вызове, не только на import. Pytest: конструктор timeout=540 и max_retries=0; env override доходит; `CHUNK_CHAR_LIMIT=30000`. Живой шлюз для pytest не обязателен. YAML / `.env` / манифест / `ktalk_client.py` / `registry.py` / `lock.py` без diff этого пакета. |
| AC-028 | S | Job MFKT `4e689c13ae01`: `schedule.expr` = `*/10 8-19 * * 1-5`; `no_agent` без смены; ErrorBus wrap без смены; новый job не создаётся. Другие jobs без diff этого пакета. `vm_movefromff` этим пакетом не трогать (AC-018). |

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
| recording_key | str | required | KTalk API | поле `id` записи |
| title | str | required | KTalk API | имя встречи |
| date | datetime(iso8601) | required | KTalk API | UTC; поле `createdDate` (не `start`) |
| duration | int | optional | KTalk API | API: **секунды**; хранение `duration_minutes`: минуты, `round(sec/60)` (1363с → 23). Не писать сырые секунды в `duration_minutes` |
| participants | str | optional | KTalk API (list/detail) | `participants[].userInfo.{firstname,surname}`; fallback `name`/`email`. Не отдельный `/participants` |
| transcript | str | required | KTalk `GET /api/recordings/{id}/transcript` | живой контур: `tracks[].chunks[]` (`text`; таймкод из `timeOffsetInMillis` или `startTimeOffsetInMillis` мс → `HH:MM:SS`; speaker из `tracks[].speaker.userInfo`). Fallback плоский `sentences` — оставить для чужого стенда. Внутренний dataclass `TranscriptSentence` без смены имён полей |
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

См. §18. Кратко для drift-check: не писать `_registry_meet.json`; не звать KTalk summary; не плодить `.env`; не патчить PFS/MFF/MOFS/OFC (OFC = `ProtocolFromSummary/scripts/ofc_sync.py` + `ofc_error_bus.py`, не `USERTOOLS/ObsidianFromConfluence/`); не ходить в `Domain/recordings/v2` и не звать `/participants`.

## Критерии приёмки (AC)

Класс S по умолчанию. Показ AC ≠ ожидание. AC-014…018 — пакет CHANGE (§19); AC-019…023 — пакет BUGFIX-LIGHT (§21); AC-024 — пакет BUGFIX-LIGHT (§22); AC-025/026 — пакет BUGFIX-LIGHT (§23); AC-027/028 — пакет CHANGE-LIGHT (§24); AC-001…013 — корпус (AC-011 больше не O). Операционный default timeout — §11 (**540с**, AC-027); AC-024/026 — история порогов 300/600. Операционный expr крона — §15 (`*/10 8-19 * * 1-5`, AC-028); AC-011 — история постановки job 15.10.

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
| AC-009 | S | MFF/PFS (включая `scripts/ofc_sync.py`, `protocolfromsummary/ofc_error_bus.py`)/MOFS/MofsIndex/FF-Autojoin/`ff_summary.json`/`_registry_meet.json` без diff этого пакета (прирост vs baseline). Каталог `USERTOOLS/ObsidianFromConfluence/` не существует и этим пакетом не создаётся. |
| AC-010 | S | Крон-скрипт `no_agent` + ErrorBus wrap в дереве пакета. Job в `jobs.json` — AC-011 (уже стоит, не этот ход). |
| AC-011 | S | Крон MFKT `4e689c13ae01` уже в `jobs.json` после «Зарускай кроны» 15.10 (`5 8-19 * * 1-5`, `no_agent`). Этот пакет его не переписывает. |
| AC-012 | S | `entities.api_ktalk` этим пакетом не создаётся (Q-5). Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять. |
| AC-013 | S | Скилл `move-from-keytalk` описывает CLI; HTTP/LLM в скилл не копируются. |
| AC-014 | S | §19: новые встречи только KTalk; нет Fireflies GraphQL в пакете. |
| AC-015 | S | §19: саммари first-class локально; `GET .../summary` не вызывается. |
| AC-016 | S | §19: YAML+schema `LOGS_PATH`/`PROMPT_PATH`/`KTALK_USER_KEY` (значение Q-2); missing → `KeyError`/`RuntimeError` → exit 2, не wrap→ok. ORCH пишет YAML; fail-loud — `HF:impl`. |
| AC-017 | S | §19: контракт §8 для PFS/MOFS/OFC без изменений. |
| AC-018 | O | §19: `depends: operator:ставь кроны` — выключить `vm_movefromff`; код MFF не патчить. |
| AC-019 | S | §21: список и ping — `GET /api/recordings`; `Domain/recordings/v2` в `request_log` нет. |
| AC-020 | S | §21: парсер `id`/`createdDate`/`duration`(сек)/`createdBy`/`userInfo`; UUID-only `createdBy.login` не дропается. |
| AC-021 | S | §21: транскрипт `tracks[].chunks[]`; пусто → pending; `/summary` не вызывается. |
| AC-022 | S | §21: metadata `GET /api/recordings/{id}` lowercase; `/participants` не вызывается. |
| AC-023 | S | §21: пагинация `skip`+`top`≤100; окно — клиент по `createdDate`; YAML/cron/.env/манифест без diff. |
| AC-024 | S | §22: LLM timeout default 300с, `MFKT_LLM_TIMEOUT` override, `max_retries=0`; `CHUNK_CHAR_LIMIT=30000` без смены; YAML/cron/.env/манифест/`ktalk_client.py` без diff. |
| AC-025 | S | §23: LLM-выход `Риски (Кто высказал /Вероятность /Влияние):` канонизируется в `Риски:` до validate; валидатор остаётся exact `_SECTION_NAMES` без `##`; `ff_summary.json` / PFS / MOFS без diff. |
| AC-026 | S | §23: LLM timeout default **600с**, `MFKT_LLM_TIMEOUT` override, `max_retries=0`; `CHUNK_CHAR_LIMIT=30000` без смены; YAML/cron/.env/манифест/`ktalk_client.py`/`registry.py` без diff. |
| AC-027 | S | §24: LLM timeout default **540с**, `MFKT_LLM_TIMEOUT` override, `max_retries=0`; `CHUNK_CHAR_LIMIT=30000` без смены; YAML/.env/манифест/`ktalk_client.py`/`registry.py`/`lock.py` без diff. |
| AC-028 | S | §24: job `4e689c13ae01` expr `*/10 8-19 * * 1-5`; `no_agent` и ErrorBus wrap без смены; новый job не создавать; другие jobs / `vm_movefromff` без diff. |

## Открытые вопросы

Новых Q у этого пакета нет. Корпус Q-1…Q-5 закрыт Сашей 15.10 (поезд `movefromkeytalk`, journal) и здесь фиксируется в master (раньше оставался «открытым» в тексте v0.1.0).

**Q-1 — закрыт 15.10.** `KTALK_BASE_URL=https://tutu.ktalk.ru`. YAML содержит хвостовой `/`; канон без path, клиент `rstrip("/")`.

**Q-2 — закрыт 15.10.** `KTALK_USER_KEY=talkusr.c1e5b36a7f8b471d8d2437357dc125bc` из `Inbox/Tokens/ktalk.md` (не секрет). В YAML 19.10 ключа нет — дыра ORCH, не отсутствующий ответ Саши.

**Q-3 — закрыт 15.10.** Leftover-skip если summary уже на диске (вариант 1 §10). Перезапись чужих файлов запрещена. Два **живых** источника (два крона) — больше не норма: AC-018.

**Q-4 — закрыт 15.10.** Job `4e689c13ae01` уже стоит (`no_agent`). Исторический expr `5 8-19 * * 1-5`. **Не переоткрывать:** оператор 19.10 сменил expr существующего job на `*/10 8-19 * * 1-5` (пакет §24 / AC-028), не новый Q и не новый job.

**Q-5 — закрыт 15.10.** `applications.kontur_talk` без `entities.api_ktalk`. Лежит в манифесте. Повторный вопрос не задавать.

## Риски

1. YAML без трёх ключей при живом кроне `4e689c13ae01` с `last_status=ok` — ingest может «молчать». Норма AC-016: exit 2 + ErrorBus.
2. Транскрипт KTalk запаздывает — backoff как MFF; калибровка после боя.
3. Длинный транскрипт vs окно LLM — чанкинг §11 (`CHUNK_CHAR_LIMIT=30000`), иначе обрезка молча **запрещена**. Клиентский timeout LLM default **540с** (§11/§24); SDK-ретраи саммари запрещены (`max_retries=0`). 540 ≈ 5.3× типичных 101с и < интервала крона 600с. Если 540с на пике мало — override `MFKT_LLM_TIMEOUT` (не YAML), не новый default в этом пакете. Скобочный заголовок шаблона «Риски (…)» канонизируется в `Риски:` до validate (§8/§11); промпт не трогать. Частый `lock_held` в ErrorBus при 10-мин шаге — принимаем (оператор 19.10); не глушить через wrap `0|1→0` на exit 2.
4. Исторические FF-файлы в той же папке — leftover §10 по файлам, не по чужому JSON; flock раздельный.
5. `KTALK_USER_KEY` (публичный talkusr в YAML) ≠ `KTALK_PERSONAL_API_KEY` (только shared `.env`, заголовок `X-Auth-Token`). Не копировать секрет в YAML/ТЗ.
6. Пока `vm_movefromff` enabled, dual-ingest жив; leftover-skip не заменяет выключение крона (AC-018). DECOMM кода MFF — чужой поезд.
7. Интеграторский `GET /api/Domain/recordings/v2` недоступен персональному `X-Auth-Token` (403). Норма §4: только `/api/recordings`. Domain/v2 не fallback.
8. `createdBy.login` в живом JSON — UUID, не `talkusr…`. Жёсткий матч `user_key in {author_key, organizer_key}` обнуляет список — норма фильтра §7.

## TZ:finalize v0.2.5 (2026-10-20)

Каноническая фиксация v0.2.5 + строка инвентаря (Б15 п.6 / Б18 / Б20 CHANGE-LIGHT). Версия **не** bump: корпус `TZ:patch` §11/§15/§24 без правок смысла. `REV:tz` skip по рецепту LIGHT (≤3 файла вне shared). `status: approved` — Q-1…Q-5 закрыты (легенда: `approved` только при закрытых Q). Код / YAML / schema / `jobs.json` / манифест / крон / `ff_summary.json` — не этот ход (`HF:impl` — `jobs.json` expr job `4e689c13ae01` + `summarizer.py` + `test_summarizer.py`; скилл — `HF:docs-handoff`).

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` — **отклонено Q-5**, этим пакетом **не** заводить. Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять.

AC-018 (`depends: operator:ставь кроны`, выключить `vm_movefromff`) — чужой operator-hold класса O; не этот пакет; hold на `GATE:done`, не на эту фазу.

## TZ:finalize v0.2.4 (2026-10-20)

Каноническая фиксация v0.2.4 + строка инвентаря (Б15 п.6 / Б18 / Б22 BUGFIX-LIGHT). Версия **не** bump: корпус `TZ:patch` §8/§11/§23 без правок смысла. `REV:tz` skip по рецепту LIGHT (≤3 файла вне shared). `status: approved` — Q-1…Q-5 закрыты (легенда: `approved` только при закрытых Q). Код / YAML / schema / `jobs.json` / манифест / крон / `ff_summary.json` — не этот ход (`HF:impl` — `summarizer.py` + `test_summarizer.py`; скилл — `HF:docs-handoff`).

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` — **отклонено Q-5**, этим пакетом **не** заводить. Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять.

AC-018 (`depends: operator:ставь кроны`, выключить `vm_movefromff`) — чужой operator-hold класса O; не этот фикс; hold на `GATE:done`, не на эту фазу.

## TZ:finalize v0.2.3 (2026-10-20)

Каноническая фиксация v0.2.3 + строка инвентаря (Б15 п.6 / Б18 / Б22 BUGFIX-LIGHT). Версия **не** bump: корпус `TZ:patch` §11/§22 без правок смысла. `REV:tz` skip по рецепту LIGHT (≤3 файла вне shared). `status: approved` — Q-1…Q-5 закрыты (легенда: `approved` только при закрытых Q). Код / YAML / schema / `jobs.json` / манифест / крон — не этот ход (`HF:impl` — `summarizer.py` + `test_summarizer.py`; скилл — `HF:docs-handoff`).

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` — **отклонено Q-5**, этим пакетом **не** заводить. Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять.

AC-018 (`depends: operator:ставь кроны`, выключить `vm_movefromff`) — чужой operator-hold класса O; не этот фикс; hold на `GATE:done`, не на эту фазу.

## TZ:finalize v0.2.2 (2026-10-20)

Каноническая фиксация v0.2.2 + строка инвентаря (Б15 п.6 / Б18 / Б22 BUGFIX-LIGHT). Версия **не** bump: корпус `TZ:patch` §21 без правок смысла. `REV:tz` skip по рецепту LIGHT (≤3 файла вне shared). `status: approved` — Q-1…Q-5 закрыты (легенда: `approved` только при закрытых Q). Код / YAML / schema / `jobs.json` / манифест / крон — не этот ход (`HF:impl` — `ktalk_client.py` + `test_ktalk_client.py`; скилл — `HF:docs-handoff`).

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` — **отклонено Q-5**, этим пакетом **не** заводить. Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять.

AC-018 (`depends: operator:ставь кроны`, выключить `vm_movefromff`) — чужой operator-hold класса O; не этот фикс; hold на `GATE:done`, не на эту фазу.

## TZ:finalize (2026-10-20)

Каноническая фиксация v0.2.1 + строка инвентаря (Б15 п.6 / Б18). Версия **не** bump: `REV:tz` APPROVE на тот же текст `TZ:patch` §20. `status: approved` — Q-1…Q-5 закрыты (легенда: `approved` только при закрытых Q). Код / YAML / schema / `jobs.json` / манифест — не этот ход (ORCH / `HF:impl` / operator AC-018).

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` — **отклонено Q-5**, этим пакетом **не** заводить. Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять (ORCH дописывает links, не `HF:impl`).

Замечания REV (не блокировали): план предыдущего поезда `dev/ktalk-kontur-v-protsess/HF-plan.md` — ориентир, этот поезд пишет свой `HF-plan.md` (G5); точная IAC-формулировка `except (KeyError, RuntimeError)` в `run()` — зона `HF:plan` / IAC, не перепись канона.

## TZ:finalize (2026-10-19)

Каноническая фиксация v0.2.0 + строка инвентаря (Б15 п.6 / Б18). Версия **не** bump: `REV:tz` APPROVE на тот же текст `TZ:patch`. `status: approved` — Q-1…Q-5 закрыты (легенда: `approved` только при закрытых Q). Код / YAML / schema / `jobs.json` / манифест — не этот ход (ORCH / `HF:impl` / operator AC-018).

`[NEW-ENTITY, требует согласования Саши]` `entities.api_ktalk` — **отклонено Q-5**, этим пакетом **не** заводить. Уже лежащие `applications.kontur_talk` / `tools.move_from_keytalk` не удалять (ORCH дописывает links, не `HF:impl`).

Замечания REV (не блокировали): точная IAC-формулировка `except (KeyError, RuntimeError)` в `run()`; §10 leftover-дедуп остаётся включённым до и после AC-018 без смены логики — зона `HF:plan` / IAC, не перепись канона.

## Changelog

- **2026-10-20 v0.2.5 TZ:finalize** (CHANGE-LIGHT/`ktalk-kontur-schedule-10min-timeout-540`). Текст §11/§15/§24, AC-027/028, Q-1…Q-5 закрыты — зафиксирован без bump версии. `REV:tz` skip (LIGHT). Строка `MAIN_TZ_INVENTORY.md`. `status: approved`. Код / YAML / cron / `jobs.json` / манифест / `ff_summary.json` / `[NEW-ENTITY]` — не этот ход.
- **2026-10-20 v0.2.5 TZ:patch** (CHANGE-LIGHT/`ktalk-kontur-schedule-10min-timeout-540`). Крон существующего job `4e689c13ae01`: expr `5 8-19 * * 1-5` → `*/10 8-19 * * 1-5` (каждые 10 мин, раб. дни 08:00–19:50); wrap/`no_agent` без смены; новый job не создавать. LLM timeout default **540с** (было 600; ≈5.3× типичных 101с, < интервала 600с), env `MFKT_LLM_TIMEOUT`, `max_retries=0` без смены. `CHUNK_CHAR_LIMIT=30000` **без смены**. AC-027/028 S. Корпус AC-001…026 / Q-1…Q-5 / §18 без пересмотра продукта. Шум `lock_held` в ErrorBus принимаем. `[NEW-ENTITY]` `entities.api_ktalk` не заводить. `status: draft` до `TZ:finalize`. Код / YAML / cron / `jobs.json` не этот ход.
- **2026-10-20 v0.2.4 TZ:finalize** (BUGFIX-LIGHT/`ktalk-kontur-samari-dlinnye-transkripty-taimaut`). Текст §8/§11/§23, AC-025/026, Q-1…Q-5 закрыты — зафиксирован без bump версии. `REV:tz` skip (LIGHT). Строка `MAIN_TZ_INVENTORY.md`. `status: approved`. Код / YAML / cron / `jobs.json` / манифест / `ff_summary.json` / `[NEW-ENTITY]` — не этот ход.
- **2026-10-20 v0.2.4 TZ:patch** (BUGFIX-LIGHT/`ktalk-kontur-samari-dlinnye-transkripty-taimaut`). Канон заголовков: `X (…):` → `X:` после LLM и до `validate_summary_sections`; валидатор остаётся строгим; `ff_summary.json` read-only. LLM timeout default **600с** (было 300; 2× сорвавшегося порога, buffer от замера 101.6с), env `MFKT_LLM_TIMEOUT`, `max_retries=0` без смены. `CHUNK_CHAR_LIMIT=30000` **без смены**. AC-025/026 S. Корпус AC-001…024 / Q-1…Q-5 / §18 без пересмотра продукта. `[NEW-ENTITY]` `entities.api_ktalk` не заводить. `status: draft` до `TZ:finalize`. Код / YAML / cron / `jobs.json` не этот ход.
- **2026-10-20 v0.2.3 TZ:finalize** (BUGFIX-LIGHT/`ktalk-kontur-samari-taimaut-llm-dlinnyj-transkript`). Текст §11/§22, AC-024, Q-1…Q-5 закрыты — зафиксирован без bump версии. `REV:tz` skip (LIGHT). Строка `MAIN_TZ_INVENTORY.md`. `status: approved`. Код / YAML / cron / `jobs.json` / манифест / `[NEW-ENTITY]` — не этот ход.
- **2026-10-20 v0.2.3 TZ:patch** (BUGFIX-LIGHT/`ktalk-kontur-samari-taimaut-llm-dlinnyj-transkript`). Клиентский LLM timeout default **300с**, env `MFKT_LLM_TIMEOUT`, `max_retries=0` (ретраи = pending §7). `CHUNK_CHAR_LIMIT=30000` **без смены**. AC-024 S. Корпус AC-001…023 / Q-1…Q-5 / §18 без пересмотра продукта. `[NEW-ENTITY]` `entities.api_ktalk` не заводить. `status: draft` до `TZ:finalize`. Код / YAML / cron / `jobs.json` не этот ход.
- **2026-10-20 v0.2.2 TZ:finalize** (BUGFIX-LIGHT/`ktalk-kontur-pravilnyj-put-api-recordings`). Текст §4/§7/§21, AC-019…023, Q-1…Q-5 закрыты — зафиксирован без bump версии. `REV:tz` skip (LIGHT). Строка `MAIN_TZ_INVENTORY.md`. `status: approved`. Код / YAML / cron / `jobs.json` / манифест / `[NEW-ENTITY]` — не этот ход.
- **2026-10-20 v0.2.2 TZ:patch** (BUGFIX-LIGHT/`ktalk-kontur-pravilnyj-put-api-recordings`). Канон пользовательского контура: `GET /api/recordings` (не `Domain/recordings/v2`); metadata lowercase `/api/recordings/{id}`; `/participants` не звать; пагинация `skip`+`top`≤100; окно дат — клиент по `createdDate`; парсер `createdDate` / `tracks[].chunks[]` / `userInfo`; фильтр не дропает UUID `createdBy.login`; duration API сек → минуты. AC-019…023 S. Корпус AC-001…018 / Q-1…Q-5 / §18 без пересмотра продукта. `[NEW-ENTITY]` `entities.api_ktalk` не заводить. `status: draft` до `TZ:finalize`. Код / YAML / cron / `jobs.json` не этот ход.
- **2026-10-20 v0.2.1 TZ:finalize** (CHANGE/`ktalk-kontur-poluchenie-transkriptov-avtonomnaya`, REV:tz APPROVE). Текст §1–§20, AC-001…018, Q-1…Q-5 закрыты — зафиксирован без bump версии. Строка `MAIN_TZ_INVENTORY.md`. `status: approved`. Код / YAML / schema / `jobs.json` / манифест / `[NEW-ENTITY]` — не этот ход. Замечания REV (свой `HF-plan.md`, IAC KeyError) — в `HF:plan` / IAC.
- **2026-10-20 v0.2.1 TZ:patch** (CHANGE/`ktalk-kontur-poluchenie-transkriptov-avtonomnaya`). Наследник abort `ktalk-kontur-v-protsess` (19.10 16:02, пайплайн; `HF:impl` не стартовал). Канон §1–§19 / AC-001…018 без пересмотра продукта. §18: путь OFC = файлы внутри PFS (`ofc_sync.py`, `ofc_error_bus.py`); каталога `USERTOOLS/ObsidianFromConfluence/` нет и не создавать. I1-C сверка 20.10: YAML всё ещё 5 из 7 ключей, `KeyError`→exit 1→wrap→ok жива. `status: draft` до `TZ:finalize`. Новых Q нет. `[NEW-ENTITY]` `entities.api_ktalk` не заводить. Код / YAML / schema / `jobs.json` не этот ход.
- **2026-10-19 v0.2.0 TZ:finalize** (CHANGE/`ktalk-kontur-v-protsess`, REV:tz APPROVE). Текст §1–§19, AC-001…018, Q-1…Q-5 закрыты — зафиксирован без bump версии. Строка `MAIN_TZ_INVENTORY.md`. `status: approved`. Код / YAML / schema / `jobs.json` / манифест / `[NEW-ENTITY]` — не этот ход. Замечания REV (IAC KeyError; §10 дедуп до/после AC-018) — в `HF:plan` / IAC.
- **2026-10-19 v0.2.0 TZ:patch** (CHANGE/`ktalk-kontur-v-protsess`). Единственный ingest новых встреч = KTalk. Саммари first-class локально. PFS / MOFS / OFC / MofsIndex без правок. YAML-канон §12: дописать `LOGS_PATH`/`PROMPT_PATH`/`KTALK_USER_KEY` (Q-2 значение 15.10) — пишет ORCH. Q-1…Q-5 закрыты Сашей 15.10 (в master v0.1 оставались «открытыми» — исправлено). AC-011 больше не O: крон MFKT уже стоит. AC-014…017 S; AC-018 O выключить `vm_movefromff`. `entities.api_ktalk` не заводить. Код / YAML / schema / `jobs.json` на этой фазе не пишутся. Повторный ход той же фазы: снято противоречие §3 («выключение крона MFF не этот пакет») vs AC-018; снято «HF:impl только если IAC» — дыра KeyError→exit 1→wrap→ok подтверждена диском, `HF:impl` обязан закрыть.
- **2026-10-15 v0.1.0 TZ:finalize** (DEV/movefromkeytalk, REV:tz APPROVE). Текст §1–§18, AC-001…013, Q-1…Q-5 зафиксирован без bump версии. Строка `MAIN_TZ_INVENTORY.md`. `status: draft` — открытые Q блокируют `HF:impl`, не эту фазу. Код / манифест / `entities.json` / `jobs.json` / `[NEW-ENTITY]` — не этот ход (регистрация `applications.kontur_talk` / optional `entities.api_ktalk` / `tools.move_from_keytalk` — ORCH после ответа Саши). Замечания REV (точный массив `PENDING_BACKOFF_MINUTES`, порог чанкинга) — в `HF:plan` / IAC, не перепись канона.
