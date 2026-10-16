---
name: ErrorBus
version: 0.3.2
status: implemented
created: 2026-08-25
updated: 2026-08-29
author: Cursor (claude-sonnet-5-thinking-medium)
depends_on: []
---

# ErrorBus (Шина Ошибок) — ТЗ

## §1. Цель и контекст

Единая инфраструктурная «Шина Ошибок» для всей экосистемы Hermes/USERTOOLS. Цель — чтобы **всё, что ломается** (сбои кронов, ошибки интеграций, баги инструментов, падения сервисов), попадало в один Telegram-топик **Errors** («Сирень Workspace», `chat -1004300127777`, `thread_id 11112`) для человека, и **одновременно** — в единую машиночитаемую БД для автоматического разбора.

Первая версия — **крон-агрегатор**: классификация + дедупликация + ежедневная сводка «что сломалось и сколько раз». **Без авто-починки** — починка остаётся за человеком/по явной команде (side-effect только по императиву, согласно правилам tz-workflow).

Первый клиент шины — `ObsidianFromConfluence` (OFC), крон `bf52e6985523`, уже шлёт ошибки в Errors через `~/.hermes/scripts/ofc_sync.sh`.

**Жёсткое правило разделения потоков (Саша, 26.08.2026):**
- **Бизнес-информация** (то, ради чего инструмент существует: уведомления о публикациях, пришедшие сообщения/письма, пропущенные задачи) — доставляется в свой бизнес-канал через штатный `deliver`, как и сейчас (Monitoring `:7`, MFL `:6556`, personal DM, `:6` и т.д.). Этот путь шина **не трогает**.
- **Вся техническая информация** (ошибки, предупреждения, исключения — то, что говорит о состоянии самого инструмента, а не о бизнес-событии) — уходит в шину ошибок (`events.db` + топик Errors `:11112`), **сразу как выявлена**, с полной детализацией.
- Охват — **все** каналы экосистемы, не только те, что исторически шлют в Monitoring `:7` (детали миграции — §4).

## §2. AS-IS (проверено на диске 25.08.2026)

- Топик Errors создан, Саша подтвердил боту его назначение (сессия `20260825_193642_bd5793be` в `state.db`). Реальных ошибок туда пока не прилетало.
- 13 `no_agent`-крон-скриптов в `~/.hermes/scripts/` (`mofs_run_cron.sh`, `ofc_sync.sh`, `pfs_notify` и др.) — единообразный паттерн: `set -euo pipefail`, venv-активация, захват `OUTPUT=$(... 2>&1)`, `EXIT_CODE=$?`, при ошибке `echo "ERROR: ..."` в stderr → `deliver` уносит текст в Telegram. Молчат при успехе.
- Только `bf52e6985523` (OFC) доставляет ошибки в Errors (`:11112`). Остальные, у кого `deliver` содержит `telegram:-1004300127777:7`, шлют в **Monitoring**: `21255143c523` (pfs_notify), `37db83c83e86` (skill_size_monitor).
- **Критическая находка по механизму чтения топика**: у Telegram Bot API нет метода получения истории чата ботом; `getUpdates` уже занят long-polling'ом основного гейтвея — параллельный вызов конфликтует за offset. Локальная история сообщений гейтвея (`~/.hermes/state.db`, таблица `messages`) **не дублирует** cron-доставки в чужие для крона топики: в `hermes-agent/cron/scheduler.py` функция `_maybe_mirror_cron_delivery`/`_target_matches_origin` зеркалирует cron-доставку в session-историю **только если target-топик == origin-топик крона**. Errors для OFC-крона — fan-out-цель (`origin.thread_id == "1"`, Errors `== "11112"`), не origin → в `state.db` ничего не попадает независимо от `cron.mirror_delivery` (сейчас `False` в `config.yaml`).
  → **Решение**: агрегатор НЕ читает Telegram. Источник данных — отдельная локальная БД, в которую пишут сами компоненты в момент отправки ошибки (см. §3).
- **Вторая критическая находка (26.08.2026)**: доставка ошибки через штатный `echo → stderr → deliver` работает только если крон в итоге завершился с ненулевым кодом — на успешном запуске планировщик **стирает** захваченный stderr (сообщение об ошибке внутри в целом успешного прогона теряется). → `report_error.sh` шлёт в Errors **напрямую**, мимо `deliver`/scheduler'а (см. §3.3).
- Рассмотрены и отклонены для реюза (Reuse-first) два существующих SQLite-хранилища:
  - `~/USERTOOLS/MofsIndex/state/index.sqlite` — поисковый FTS-индекс встреч/документов (RAG), пересоздаётся при `mofs index rebuild`; семантически чужой, события затрутся.
  - `~/.hermes/cron/executions.db` — claim-lock БД ядра Hermes (`cron/executions.py`), одна таблица `executions` со статусами `claimed/running/completed/failed/unknown`. Отклонена по трём причинам: (1) горячий claim-цикл планировщика конкурирует за file-level lock SQLite с записями шины; (2) нет контракта на схему — апдейт ядра Hermes может пересоздать/изменить файл без учёта добавленной таблицы; (3) разная семантика жизненного цикла (короткоживущий lock-статус крона vs накопительная история ошибок за недели).
  - **Итог**: отдельная `~/.hermes/error_bus/events.db`. Reuse-first соблюдён на уровне паттерна («одна SQLite на одну задачу», как `state.db`/`executions.db`/`notepad.db`), а не файла чужого компонента.
- `sqlite3` CLI **отсутствует в системе** (`which sqlite3` → not found). `python3` (stdlib `sqlite3`) доступен везде — и в system `/usr/bin/python3.11`, и в любом venv инструментов.
- Job_id **не передаётся** `no_agent`-скриптам через env (проверено в `cron/scheduler.py::_run_script_job` — `subprocess.run` с `env=build_subprocess_env()`, без инъекции job_id/job_name). Ядро `scheduler.py` в рамках этого ТЗ **не меняется** (см. §6) — связь job_id↔событие устанавливается либо явной передачей `--job-id` вызывающим, либо позже `reconcile`-процессом через `hermes` CLI (см. §3.6).

## §3. TO-BE — архитектура

### 3.1 Компоненты

```
~/.hermes/error_bus/
  events.db                    # SQLite, WAL, единая таблица errors (см. §3.2)
  severity_rules.py            # regex-правила классификации критичности (см. §3.7)
  instrumentation_registry.json  # job_id → self|wrap|agent (см. §3.4)
  archive/                     # gzip JSONL архив по ретенции (см. §3.8)

~/.hermes/scripts/
  report_error.sh               # единая точка входа записи+доставки ошибки (см. §3.3)
  error_bus_wrap.sh              # внешняя обёртка команды, Mode B (см. §3.4)
  error_bus_cli.py               # list/show/resolve/stats/status/audit (см. §3.5)
  error_bus_reconcile.sh         # fallback + session_key backfill, ежечасно (см. §3.6, §3.12)
  error_bus_daily_digest.sh      # ежедневная сводка (см. §3.9)
  error_bus_retention.sh         # архивация + VACUUM, ежемесячно (см. §3.8, §3.12)
```

Никакого сервиса/демона — вся логика в bash+python3 скриптах без внешних зависимостей (только stdlib `sqlite3`, `hashlib`, `re`, `json`, `datetime`, `urllib`/`curl` для прямой отправки в Telegram).

### 3.2 Схема БД `events.db`

```sql
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS errors (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key         TEXT NOT NULL,
    tool              TEXT NOT NULL,
    source_kind       TEXT NOT NULL DEFAULT 'cron_script'
                      CHECK(source_kind IN ('cron_script','cron_agent','usertool','skill','integration','other')),
    stage             TEXT,
    severity          TEXT NOT NULL DEFAULT 'error'
                      CHECK(severity IN ('critical','error','warning','info')),
    message           TEXT NOT NULL,
    detail            TEXT,               -- ограничение 4KB, см. §3.8
    exit_code         INTEGER,            -- код, переданный вызывающим (Mode A)
    final_exit_code   INTEGER,            -- фактический код процесса (Mode B / wrap)
    job_id            TEXT,
    host              TEXT,
    context           TEXT,               -- JSON, ограничение 2KB, см. §3.8
    captured_by       TEXT NOT NULL DEFAULT 'self'
                      CHECK(captured_by IN ('self','wrap','reconcile')),
    script            TEXT,               -- путь/имя скрипта-источника
    cmdline           TEXT,               -- argv без секретов (Mode B)
    log_path          TEXT,               -- указатель на cron/output или лог, без дублирования
    session_key       TEXT,               -- заполняется reconcile'ом, см. §3.6
    status            TEXT NOT NULL DEFAULT 'open'
                      CHECK(status IN ('open','resolved')),
    resolved_at       TEXT,
    resolved_note     TEXT,
    first_seen        TEXT NOT NULL,
    last_seen         TEXT NOT NULL,
    last_notified_at  TEXT,               -- для тротлинга повторных Telegram-уведомлений, см. §3.8
    count             INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_errors_dedup  ON errors(dedup_key, last_seen);
CREATE INDEX IF NOT EXISTS idx_errors_tool_seen ON errors(tool, last_seen);
CREATE INDEX IF NOT EXISTS idx_errors_status ON errors(status, last_seen);
```

Семантика и обоснование новых полей (решения 26.08.2026):
- `captured_by` — кто зафиксировал событие: `self` (инлайн-вызов из скрипта/агента), `wrap` (перехват через `error_bus_wrap.sh`), `reconcile` (fallback после факта, по CLI ядра). Ровно одно значение на событие.
- `script`, `cmdline`, `final_exit_code`, `log_path` — полнота раскрытия для Mode B: что запускалось, с какими аргументами (без секретов), с каким итоговым кодом, где искать полный лог.
- `status`/`resolved_at`/`resolved_note` — минимальный жизненный цикл события без авто-починки: человек (или `error_bus_cli.py resolve`) помечает разобранное, сводка (§3.9) отдельно показывает то, что осталось открытым дольше 3 дней.
- `last_notified_at` — тротлинг повторных уведомлений (§3.8), не влияет на дедуп-логику вставки/инкремента.
- `session_key` — связь с LLM-стоимостью, заполняется асинхронно `reconcile`'ом (§3.6), не на этапе записи.

БД — это **агрегированное представление** (одна строка = одна dedup-группа), не построчный журнал каждого вхождения; рост базы = рост числа уникальных `dedup_key`, а не числа вхождений (см. §3.8).

**Доработка 27.08.2026 (версия 0.3.0) — авто-закрытие неактуальных `open` без изменения схемы**: используется уже существующий статус `resolved` (никаких новых колонок/значений в `CHECK`). В `_db.py` добавляются две функции — `auto_resolve_recovered(conn, recoveries)` (по `job_id`, вызывается из `reconcile.py`, см. §3.6) и `auto_resolve_dormant(conn, days=DORMANT_DAYS)` (без `job_id`, вызывается из `digest.py` перед `digest_rows_stale_open`, см. §3.9); обе делают `UPDATE status='resolved', resolved_at=now, resolved_note='auto-resolved: ...'` — **никогда `DELETE`**, история полностью сохраняется. Функция `digest_rows_stale_open` правится (добавление recency-условия по `last_seen`, N=7 дней) — сигнатура и место в схеме не меняются.

### 3.3 `report_error.sh` — единая точка входа

```
report_error.sh --tool "OFC" --message "ofc_sync.py завершился с кодом 2" \
  [--source-kind cron_script|cron_agent|usertool|skill|integration|other] \
  [--stage "sync"] [--severity error|critical|warning] \
  [--exit-code 2] [--detail "$OUTPUT"] [--job-id "bf52e6985523"] \
  [--context '{"key":"value"}'] [--captured-by self|wrap|reconcile] \
  [--script "ofc_sync.sh"] [--cmdline "..."] [--log-path "..."] \
  [--session-key "..."]
```

Обязательные аргументы: `--tool`, `--message`. Дефолты: `--source-kind cron_script`, `--severity error`, `--captured-by self`.

Алгоритм (пересмотрено 26.08.2026 — прямая доставка, минуя `deliver`):
1. Обрезает `--detail` до 4KB и `--context` до 2KB (с меткой `…[truncated, original N bytes]` при превышении) — до записи и до отправки.
2. Вызывает `report_error.py` (`~/.hermes/error_bus/report_error.py`), который делегирует всю логику общему shared-модулю `~/.hermes/error_bus/_db.py` (**решение при реализации, 26.08.2026, см. §9 №11** — вместо инлайн `python3 -c "..."`, который дублировал бы код bootstrap/дедупа в каждом клиенте): bootstrap схемы (`CREATE TABLE IF NOT EXISTS`, идемпотентно), нормализация `message` (вырезка чисел/PID/путей/таймстампов) → `dedup_key = sha256(f"{tool}:{stage}:{normalized}").hexdigest()[:16]`, поиск существующей строки за 24ч (`WHERE dedup_key=? AND last_seen >= datetime('now','-24 hours')`) → `UPDATE count+1/last_seen/detail/exit_code/final_exit_code` либо `INSERT` новой строки. `_db.py` также содержит `get_telegram_token()`/`send_telegram_message()` (см. правку токена ниже) и retention-хелперы, переиспользуемые `error_bus_cli.py`/`reconcile.py`/`retention.py`.
3. **Печатает человекочитаемую строку в stderr** (`ERROR: <tool>: <message>` + `--detail`) — сохраняется для обратной совместимости с логами/локальным выводом, но **не является** больше единственным путём доставки в Telegram.
4. **Отправляет напрямую** в Errors через HTTP `POST https://api.telegram.org/bot<TOKEN>/sendMessage` (`chat_id=-1004300127777`, `message_thread_id=11112`, без `parse_mode` — см. §3.10). Причина прямой отправки, а не через `deliver`/`echo`: на успешном (в целом) прогоне крона планировщик стирает захваченный stderr — сообщение о промежуточной ошибке никогда не попадёт в Telegram, если ждать `deliver` (см. §2, вторая находка).
   **Выбор `<TOKEN>` (правка решения при реализации, 26.08.2026 — см. §9, решение №11):** приоритет `TELEGRAM_BOT_TOKEN` (env, бот `sirene_vm_bot`), резерв — `hermes config get gateway.telegram.token`. Причина правки: бот из `gateway.telegram.token` не состоит в группе «Сирень Workspace» → не может слать в топик Errors; `sirene_vm_bot` состоит. Реализовано в `~/.hermes/error_bus/_db.py::get_telegram_token()`.
5. Тротлинг: перед отправкой в Telegram проверяет `last_notified_at` для найденного/созданного `dedup_key` — для `error`/`warning` не отправляет повторно чаще, чем раз в 30 минут; для `critical` отправляет всегда без тротлинга. Отправка обновляет `last_notified_at`; запись в БД происходит независимо от тротлинга (метрика count не занижается).
6. **Fail-soft**: сбой записи в БД или отправки в Telegram перехватывается, допечатывается в stderr (`[report_error] events.db insert failed: ...` / `[report_error] telegram send failed: ...`), но не блокирует ни возврат хелпера, ни исходный поток вызывающего скрипта.
7. `report_error.sh` всегда завершается `exit 0` — код возврата исходной команды продолжает выставлять сам вызывающий (Mode A) либо `error_bus_wrap.sh` (Mode B).

### 3.4 Режимы инструментирования: Self-report (A) / Wrap (B) / Reconcile (fallback)

Решение Саши (26.08.2026): все скрипты и агенты экосистемы приводятся к одному из двух взаимоисключающих режимов **на каждую точку сбоя** — никогда оба одновременно (риск задвоения записи/уведомления).

**Режим A — Self-report (инлайн).** Скрипт или агент сам вызывает `report_error.sh` в момент обнаружения ошибки, с точным `--stage` (например, конкретная стадия внутри OFC/`pfs_notify`/мониторинг-крона). Подходит там, где есть осмысленная точка перехвата внутри логики (`except`, проверка кода возврата подкоманды).

**Режим B — Wrap (внешний), `error_bus_wrap.sh`.**

```
error_bus_wrap.sh --tool "MOFS" --job-id "<id>" -- <command...>
```

- Оборачивает произвольную команду: запускает, прозрачно пробрасывает `stdout`/`stderr`/итоговый `exit code` вызывающему (внешне поведение не меняется).
- Перехватывает **любой** ненулевой exit-код команды, включая случаи, которые самоинструментирование не покрывает: синтаксическая ошибка, OOM, падение до входа в `try`/до первой осмысленной строки скрипта.
- Ровно **один вызов** `report_error.sh` на запуск обёрнутой команды (`--captured-by wrap --script <name> --cmdline "<argv без секретов>" --final-exit-code <code> --log-path <path>`), безусловно — репорт отправляется **до** того, как какая-либо внешняя логика решит подавить/проигнорировать ошибку (полнота раскрытия важнее тишины).

**Reconcile — агент-дефолт (страховочная сетка).** Для `cron_agent`-задач без явного self-report на конкретный сбой действует дефолт: если агент упал/завис до того, как успел вызвать `report_error.sh` сам, событие фиксирует `error_bus_reconcile.sh` (ежечасно, см. §3.6, §3.12) с `--captured-by reconcile`. Это не третий равноправный режим, а fallback для Mode A/агентных задач — не применяется к `no_agent`-скриптам, у которых для этого есть Mode B.

**`instrumentation_registry.json`** (`~/.hermes/error_bus/instrumentation_registry.json`) — реестр `{job_id: "self" | "wrap" | "agent"}`, фиксирует выбранный режим для каждой задачи из `jobs.json`. Правило: «либо A, либо B, никогда оба» — один и тот же вызов не должен одновременно быть обёрнут `error_bus_wrap.sh` и содержать внутренний self-report на тот же сбой (двойная запись/двойное уведомление). Аудит конфликтов и пробелов — команда `audit` в `error_bus_cli.py` (§3.5).

### 3.5 `error_bus_cli.py` — управление и аудит

Единая CLI-точка для человека/сводки, без чтения Telegram:

- `list [--tool ...] [--severity ...] [--status open|resolved] [--since ...]` — табличный вывод строк `errors`.
- `show <id>` — полная строка + **fail-soft, read-only** подтягивание штатных артефактов Hermes по указателям (не дублирование хранения): запись `jobs.json` по `job_id`, последний прогон из `~/.hermes/cron/output/<job_id>/`, сессия из `state.db` по `session_key` (если заполнен), хвост `errors.log`/`agent.log` — **on-demand**, только по явному флагу (`--with-logs`), чтобы не тянуть тяжёлые файлы по умолчанию.
- `resolve <id> [--note "..."]` — `status=resolved`, `resolved_at=now`, `resolved_note`.
- `stats [--window 24h|7d|30d]` — агрегаты по `tool`/`severity`.
- `status` — быстрый обзор состояния шины (число открытых `critical`, время последнего запуска `digest`/`reconcile`).
- `audit` — сверяет `instrumentation_registry.json` с `jobs.json`: находит (a) задачи без зарегистрированного режима, (b) задачи, заявленные как `wrap`, но при этом содержащие собственные вызовы `report_error.sh` внутри скрипта (конфликт A+B), (c) записи реестра, указывающие на несуществующий `job_id`.

### 3.6 Связь с ядром Hermes и LLM-стоимостью (`session_key`)

- Ядро `cron/scheduler.py` и `~/.hermes/cron/executions.db` шина **не трогает и не читает напрямую** (см. §6). Всё обращение к штатным данным о запусках — через `hermes` CLI (`hermes cron runs <job_id>`, `hermes logs errors`), и только из одного процесса — `error_bus_reconcile.sh`.
- `session_key` заполняется **только** `reconcile`'ом: сопоставление `job_id` + временное окно запуска с `state.db.sessions` (имя сессии содержит `job_id`) — единственный работающий механизм связи `cron_agent`-ошибки с LLM-сессией/стоимостью.
- Явный `--session-key` в `report_error.sh` остаётся как override для вызывающих, которые уже знают свою сессию.
- Autodetect `session_key` из env **не реализуется** — в окружении агентных обёрток нет инъекции `session_key`, реализация такого пути создала бы иллюзию рабочей связи без реальных данных (мёртвый код).
- Для `no_agent`-скриптов `session_key = NULL` — это **корректное** значение (нет LLM-вызова → нечего связывать), искусственная привязка не придумывается.
- `error_bus_reconcile.sh` — отдельный ежечасный крон (спецификация расписания — §3.12), не расходует LLM-токены (чисто механическая реконструкция по CLI ядра + SQLite).
- `llm_anomaly_scan.sh` становится клиентом шины (Mode A): **детерминированный SQL** к `state.db` (окно 7 дней, `mode=ro`) определяет, что репортить — `critical` только при подтверждённых **session monster** (`api_call_count>500` или `tool_call_count>1000`) или **cache write bloat** (`cache_write_tokens>5M`). Раздельные `--message` на каждый класс. **Не** grep по прозе LLM-отчёта (заголовки «не найдено» не триггерят шину). **Auto-resolve** (PIIScan Variant 2): если open-строка `tool=LLMAnomalyScan` не подтверждается текущим SQL-прогоном — `error_bus_cli.py resolve`, без `DELETE`/сырого SQL. **`session_reset` не репортится**, пока в `config.yaml` включён штатный `session_reset.mode` ∈ {`idle`, `daily`, `both`} (сейчас `both`).
- Прочие мониторинг-кроны (`vm_selfcheck`, `upstream_monitor`, `skill_size_monitor`) аналогично становятся клиентами Mode A **для найденных проблем**: в `events.db` попадает только сигнал о находке («red»), не security-риски (по определению Саши — security — это риск, а не проблема, вне охвата шины ошибок). Канал доставки самого мониторинг-крона (какой он есть сейчас) не меняется — репорт в Errors идёт **дополнительно**, а не взамен.

**Авто-resolve по факту восстановления (доработка 27.08.2026, версия 0.3.0, root cause и решение — §9, №12, детали фаз — §8 фаза 10):** `reconcile.py` уже строит `recovery_index` (последний успешный прогон по `job_id`) и использует `is_recovered()`, но раньше — только чтобы не создавать повторное событие; старая `open`-строка при этом не закрывалась и висела в сводке навсегда. В конце `reconcile()` добавляется вызов новой функции `auto_resolve_recovered(conn, recoveries)` (`_db.py`) — по `recovery_index` резолвит (`status='resolved'`, `resolved_note` с указанием `job_id`/времени восстановления; история не удаляется, только `UPDATE`) все `open`-строки с этим `job_id`, у которых `last_seen` раньше времени успешного восстановления. Результат (число резолвнутых строк) добавляется как `auto_resolved` в возвращаемый `dict` результата `reconcile()`, наравне с `created`/`skipped`/`backfilled` — для видимости в cron output/логах. Путь `report_error`/`already_reconciled`/`is_recovered` не меняется — это чисто дополнительный шаг после существующей логики.

### 3.7 Классификация критичности (для сводки, без LLM)

Файл `~/.hermes/error_bus/severity_rules.py` — список regex-правил, применяется поверх накопленных строк `errors`, результат пишется обратно в колонку `severity`:

| Правило | Severity |
|---|---|
| `count` за 24ч ≥ 5 (систематический повтор) **или** `message`/`detail` матчит `Traceback\|Unhandled\|Fatal\|corrupt\|database is locked\|PermissionError\|500 Internal Server Error` | `critical` |
| LLM-аномалия: session monster (`api_call>500` / `tool>1000`) или cache write bloat (`>5M`) — клиент `llm_anomaly_scan.sh`, SQL §3.6, явные `--message` | `critical` |
| `count` за 24ч < 5 **и** матчит `timeout\|rate.?limit\|429\|temporarily unavailable\|retry\|connection reset` | `warning` |
| Всё остальное | `error` (дефолт при записи) |
| — | `info` зарезервирован под v2 (не error-события) |

Порог `count ≥ 5` — стартовое значение, калибровка после накопления реальных данных (см. §10). Правила — простой список в отдельном файле, без LLM, легко расширяются под новый инструмент.

### 3.8 Лимиты, ретенция и анти-лавина

Решения 26.08.2026 против неограниченного роста БД и лавины уведомлений:

- **Лимиты на запись**: `detail` ≤ 4KB, `context` (JSON) ≤ 2KB — обрезка с меткой `…[truncated, original N bytes]` перед вставкой в БД и перед отправкой в Telegram (применяется в `report_error.sh`, §3.3).
- **Ретенция `events.db`**: `critical` — 180 дней, `error`/`warning` — 90 дней, `info` — 30 дней (считается от `last_seen`). По истечении — архивация в `~/.hermes/error_bus/archive/errors_YYYYMM.jsonl.gz` (по одной строке JSONL на архивируемую запись) + `DELETE` + `VACUUM`. Реализуется `error_bus_retention.sh`, крон 2 раза в месяц (1-е и 15-е число, §3.12; создание в `jobs.json` — по «ставь кроны»).
- **Агрегированная схема** (уже заложена в §3.2): рост базы = рост числа уникальных `dedup_key`, а не числа вхождений; систематический повтор увеличивает `count` в существующей строке.
- **Тротлинг повторных уведомлений**: `error`/`warning` — не чаще раза в 30 минут на `dedup_key` (поле `last_notified_at`); `critical` — без тротлинга, каждое срабатывание уходит немедленно. Тротлинг влияет только на отправку в Telegram, не на запись/инкремент в БД.

### 3.9 Ежедневная сводка — `error_bus_daily_digest.sh`

Новый `no_agent`-крон (создаётся только по явному «ставь кроны» от Саши — не создаётся автоматически при реализации ТЗ; расписание — §3.12: `0 9 * * *`, 09:00 МСК):

- Блок 1 «за 24ч»: читает `events.db` (`WHERE last_seen >= datetime('now','-24 hours')`), применяет правила §3.7, группирует по `tool` (сумма `count`, min `first_seen`, max `last_seen`, доминирующий `severity`).
- **Авто-закрытие неактуального перед формированием Блока 2 (доработка 27.08.2026, версия 0.3.0 — root cause, гибрид-решение см. §9 №12):** перед вызовом `digest_rows_stale_open(conn)` вызывается `auto_resolve_dormant(conn, days=DORMANT_DAYS)` (`_db.py`, новая константа модуля `digest.py`, дефолт **5 дней**) — fallback для событий **без `job_id`** (ручные/self-report без привязки к крону, которые `reconcile` не может закрыть через `recovery_index`, §3.6): резолвит `open`-строки без `job_id`, у которых `last_seen` не обновлялся ≥ `DORMANT_DAYS` (нет повторов — де-факто неактуально). `UPDATE status='resolved', resolved_note='auto-resolved: dormant, no recurrence'` — история не удаляется.
- Блок 2 «всё ещё открыто»: `WHERE status != 'resolved' AND first_seen <= datetime('now','-3 days') AND last_seen >= datetime('now','-N days')` — фикс структурного бага (было: фильтр только по `first_seen`, из-за чего любое событие старше 3 дней светилось в сводке бесконечно, даже без повторов с момента создания). Добавлено recency-условие по `last_seen` (константа **N=7 дней** в `_db.py`, функция `digest_rows_stale_open`) — в блок попадают только реально «живые»/повторяющиеся инциденты дольше 3 дней, не разобранные человеком, а не весь исторический open-мусор.
- Опционально в тексте сводки — строка «🔧 N кейсов авто-закрыто за 24ч» (сумма `auto_resolved` из последних прогонов `reconcile` за 24ч + результат `auto_resolve_dormant` текущего запуска digest) — для прозрачности механизма, не обязательно к реализации.
- Если оба блока пустые — `exit 0` без вывода (молчит, паттерн уже принят в экосистеме).
- Иначе формирует Markdown-отчёт:

```
🗞 Сводка Error Bus за 24ч: N ошибок, M уникальных

За 24ч:
🔴 critical:
  • <tool> — <count>× (первое: HH:MM, последнее: HH:MM)
⚠️ warning:
  • <tool> — <count>×
❌ error:
  • <tool> — <count>×

Всё ещё открыто (> 3 дней, не resolved, есть повторы за последние N дней):
  • <tool> — открыто с YYYY-MM-DD, <count>×

🔧 N кейсов авто-закрыто за 24ч (опционально)
```
- `deliver: telegram:-1004300127777:11112` (Errors — сводка часть того же смыслового канала, не Monitoring).

### 3.10 Формат сообщения в Telegram (человекочитаемый, прямая отправка)

Из `report_error.sh` (§3.3, шаг 4) — прямой HTTP-вызов, без `parse_mode` (без Markdown/HTML-escaping):

```
curl -s -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d chat_id="-1004300127777" \
  -d message_thread_id="11112" \
  -d text="ERROR: <tool>: <message>
<detail, если есть, обрезан до 4KB>"
```

Не требует машиночитаемости, т.к. источник данных для агрегатора — `events.db`, не текст сообщения. Опционально в будущем (не в v1) можно оформить эмодзи-префиксом (`❌ <tool> | <message>`) — чисто косметика доставки.

### 3.11 Онбординг нового инструмента (без доработки ядра шины)

1. Выбрать режим для каждой точки сбоя — Mode A (self-report) или Mode B (`error_bus_wrap.sh`), никогда оба (§3.4); зарегистрировать выбор в `instrumentation_registry.json`.
2. Mode A: вызывать при ошибке `~/.hermes/scripts/report_error.sh --tool "<CanonicalName>" --message "<текст>"` (+ опциональные флаги §3.3). Mode B: запускать команду через `error_bus_wrap.sh --tool "<CanonicalName>" -- <command>`.
3. `<CanonicalName>` — имя инструмента как в `MAIN_TZ_INVENTORY.md`/`EcosystemManifest.digest.md` (единое пространство имён, не придумывать новое).
4. Никакой регистрации «клиента шины» в схеме БД не требуется — `tool` — свободный текст; шина узнаёт о новом инструменте из первой же записи. Регистрация нужна только в `instrumentation_registry.json` (режим A/B) для аудита.
5. Схема БД не меняется под конкретный инструмент — специфичные данные идут в `context` (JSON, ≤2KB).
6. Для агентного крона без выделенной точки self-report — reconcile выступает страховочной сеткой автоматически, отдельного шага не требует (§3.4).

### 3.12 Расписания (спецификация; создание крона — только по «ставь кроны»)

Все три крона ниже фиксируются в ТЗ как **спецификация расписания**. Добавление в `jobs.json` — отдельный шаг, выполняемый исключительно по явному императиву «ставь кроны» (правило tz-workflow/R3), не автоматически при реализации ТЗ.

| Крон | Расписание | Назначение |
|---|---|---|
| `error_bus_reconcile` | ежечасно, `0 * * * *` | fallback-фиксация пропущенных сбоев через `hermes cron runs`/`hermes logs errors`, backfill `session_key` |
| `error_bus_daily_digest` | ежедневно, `0 9 * * *` (09:00 МСК) | сводка «за 24ч» + «всё ещё открыто» в Errors (§3.9) |
| `error_bus_retention` | 2 раза в месяц, `0 3 1,15 * *` (1-е и 15-е число, 03:00; правка Саши 27.08.2026) | архивация в gzip JSONL + `VACUUM` по срокам §3.8 |

## §4. Правило разделения каналов и миграция (обновлено 26.08.2026)

Действует правило §1: бизнес-`deliver` каждого крона/инструмента **не меняется**; техника (ошибки/предупреждения) подключается к `report_error.sh`/`error_bus_wrap.sh` **дополнительно**, поверх существующей доставки, для **всех** каналов экосистемы (не только Monitoring `:7`, как было зафиксировано 25.08).

Известные каналы/кроны и статус подключения техники к Errors (детали режима A/B и порядок — при реализации, Фаза 5, §8):

| job_id / крон | Бизнес-канал (`deliver`, не меняется) | Действие по технике |
|---|---|---|
| `21255143c523` pfs_notify | Monitoring `:7` | подключить `report_error.sh`/`wrap` --tool ProtocolFromSummary |
| `37db83c83e86` skill_size_monitor | Monitoring `:7` | подключить `report_error.sh`/`wrap`; found-issues также через Mode A (§3.6) |
| `bf52e6985523` OFC | уже Errors `:11112` | заменить чистый `echo` на структурированный `report_error.sh` |
| `d95502d8a82b` skills_digest | `:6` | подключить `report_error.sh`/`wrap`, `deliver :6` не меняется |
| `f61b26cbbdf5` / `2865cc674493` MoveFromLoop | `:6556` | подключить `report_error.sh`/`wrap`, `deliver :6556` не меняется |
| `vm_movefromff` / `gateway_watchdog` | personal DM | подключить `report_error.sh`/`wrap`, DM не меняется |
| остальные `no_agent` (`mofs_run_cron.sh`, `mofs_index_rebuild.sh`, `autosync_full_with_cleanup.sh`, `full_workvault_backup.sh`, `restore-all-skills.sh`) | `local`/DM | подключить по тому же паттерну, `deliver` не меняется |

Прежняя оговорка «расширение охвата за пределы `:7` — вне решения Саши» (см. §9, решение №10 от 25.08) **снята**: 26.08 Саша явно подтвердил охват «все каналы» для технической составляющей (см. §1). Конкретный порядок подключения каждого крона и выбор Mode A vs Mode B на реализации фиксируются в `instrumentation_registry.json` (§3.4).

## §5. Связи с экосистемой

- **Не пересекается** ни с одним активным ТЗ по функции (проверено по `MAIN_TZ_INVENTORY.md` и `EcosystemManifest.digest.md`) — Error Bus — новая инфраструктурная сущность уровня `TZ-storage-system`/`EcosystemIntegration`.
- **Регистрация в EcosystemManifest**: при реализации добавить `ErrorBus` в `infra_service` секцию `EcosystemManifest.json` (аналогично `EcosystemIntegration`) — **требует согласования Саши**, не выполняется в рамках этого ТЗ (см. §10).
- Зависимые/связанные инструменты для будущего подключения (§3.11, §4): все активные `no_agent`-кроны и агентные кроны из `jobs.json`, все USERTOOLS (`ProtocolFromSummary`, `MarkObjectsFromSummary`, `MofsIndex`, `ConfluenceSync`, `MoveFrom*`, `TaskRefresh`, `OKRTool`, `SRTool`, и т.д.) — подключение по мере обращения, не одномоментно.
- Новые артефакты шины, видимые остальной экосистеме: `error_bus_cli.py` (человеческий/скриптовый доступ к статусу ошибок любого инструмента), `instrumentation_registry.json` (реестр режимов инструментирования, растёт вместе с онбордингом новых инструментов).

## §6. Что НЕ трогать

- `~/.hermes/cron/executions.db` — не расширять схему, не писать напрямую.
- `~/.hermes/cron/scheduler.py` (ядро) — не трогаем, включая инъекцию `job_id`/`session_key` в env подпроцессов; связь job_id/session_key устанавливается снаружи ядра — явной передачей `--job-id`/`--session-key` либо `reconcile`'ом через `hermes` CLI (§3.6).
- `~/USERTOOLS/MofsIndex/state/index.sqlite` — не использовать как хранилище ошибок.
- `~/.hermes/state.db` — Error Bus не пишет в него; читает только `reconcile` (таблицу `sessions`, read-only, для backfill `session_key`); топик Errors не используется как источник данных, только как канал доставки для человека.
- `~/.hermes/errors.log`/`agent.log`/`~/.hermes/cron/output/` — не дублируются в `events.db`; `error_bus_cli.py show` и `reconcile` обращаются к ним как к штатным артефактам ядра, fail-soft, read-only, on-demand.
- Бизнес-`deliver`-адреса кронов (Monitoring `:7`, `:6`, `:6556`, personal DM и т.д.) — не переключаются нигде и никогда в рамках этого ТЗ; это постоянное правило (§1), а не временная оговорка.

## §7. Тест-кейсы (для фазы реализации)

Unit (без сети, без реального `events.db` — временный файл):
- `test_dedup.py` — нормализация сообщения, стабильность `dedup_key`.
- `test_report_error.py` — создание/инкремент/новая строка после выхода за окно 24ч; обрезка `detail`/`context` по лимитам §3.8.
- `test_severity_rules.py` — матрица примеров → ожидаемая критичность, включая LLM-аномалии (§3.7).
- `test_report_error_failsoft.py` — при недоступной БД и/или недоступном Telegram хелпер печатает stderr-строку и завершается `exit 0`.
- `test_wrap.py` — `error_bus_wrap.sh` перехватывает синтаксическую ошибку/OOM/падение до `try`, ровно 1 репорт на запуск, прозрачный passthrough stdout/stderr/exit code.
- `test_registry_audit.py` — `error_bus_cli.py audit` находит непокрытые job_id и конфликты A+B на тестовом `instrumentation_registry.json`.
- `test_throttle.py` — повторные события `error`/`warning` не шлют Telegram чаще раза в 30 минут; `critical` — без тротлинга.

Integration (ручные, помечены как smoke):
- Прогон `report_error.sh` из реальной venv-обёртки — подтверждение прямой доставки в Errors без `deliver`.
- Ручной запуск `error_bus_daily_digest.sh` на тестовых данных — проверка обоих блоков сводки и молчания при пустом окне.
- Ручной запуск `error_bus_reconcile.sh` — подтверждение backfill `session_key` через `hermes cron runs`/`hermes logs errors` без прямого чтения `executions.db`.
- Ручной запуск `error_bus_retention.sh` на записях с искусственно сдвинутыми датами — архивация в gzip JSONL + `VACUUM`.

## §8. Фазы реализации (для hermes-feature, после «берём в работу»)

| Фаза | Содержание | Deliverable |
|---|---|---|
| 1 | Схема `events.db` v2 (§3.2) + `report_error.sh` (прямая отправка в Errors, лимиты 4KB/2KB, тротлинг) | unit-тесты §7 зелёные, ручной вызов пишет строку и шлёт в Errors напрямую |
| 2 | `error_bus_wrap.sh` + `instrumentation_registry.json` + правило A/B | `test_wrap.py` зелёный, ровно 1 репорт на запуск |
| 3 | `error_bus_cli.py` (list/show/resolve/stats/status/audit) | `audit` находит конфликты/пробелы на тестовом реестре |
| 4 | `severity_rules.py` v2 (включая LLM-аномалии) | `test_severity_rules.py` зелёный |
| 5 | Миграция существующих скриптов на Mode A/B (§4, все каналы) | все `no_agent`/агентные кроны подключены, бизнес-`deliver` не изменён |
| 6 | `error_bus_reconcile.sh` (fallback + backfill `session_key` через `hermes` CLI) | ручной прогон закрывает «потерянный» таймаут, `session_key` заполняется |
| 7 | `error_bus_daily_digest.sh` v2 (24ч + «всё ещё открыто») | ручной прогон формирует корректную сводку |
| 8 | `error_bus_retention.sh` (лимиты, архивация, `VACUUM`) | ручной прогон архивирует старые записи по срокам §3.8 |
| 9 | **(доработка 27.08.2026, v0.3.0)** SQL-фикс `digest_rows_stale_open` (`_db.py`) — recency-условие по `last_seen` (N=7 дней) | `test_auto_resolve.py`: старый-но-неактивный кейс (`last_seen` давно) не возвращается блоком «всё ещё открыто» |
| 10 | **(доработка 27.08.2026, v0.3.0)** `auto_resolve_recovered(conn, recoveries)` в `_db.py` + вызов в конце `reconcile()`, `auto_resolved` в возвращаемом dict | `tests/test_reconcile_auto_resolve.py`: job с failure + последующим успешным прогоном → событие резолвится; без успеха — остаётся open; регрессия по `test_reconcile_no_dup.py`/`test_reconcile_freshness.py`/`test_reconcile_crosscheck.py` не нарушена |
| 11 | **(доработка 27.08.2026, v0.3.0)** `auto_resolve_dormant(conn, days=DORMANT_DAYS)` в `_db.py` + вызов в `digest.py` перед `digest_rows_stale_open`; опционально строка «N кейсов авто-закрыто» в тексте сводки | `tests/test_digest_dormant.py`: dormant open без `job_id` резолвится и исчезает из следующей сводки с ожидаемым `resolved_note` |
| 12 | Кроны (`reconcile`/`digest`/`retention`) в `jobs.json` — только по «ставь кроны». **Расписания**: reconcile `0 * * * *`, digest `0 9 * * *`, retention `0 3 1,15 * *` (1-е и 15-е число; правка Саши 27.08.2026) | подтверждение Саши на расписание, крон создан явным шагом |

## §9. Решения брифа (25.08–26.08.2026)

### 25.08.2026

| № | Решение |
|---|---|
| 1 | Хранилище — отдельная `~/.hermes/error_bus/events.db` (SQLite, WAL), не `executions.db`/`index.sqlite`. |
| 2 | Единая точка входа — `report_error.sh`, пишет в БД + сохраняет stderr-эхо (доставка позже пересмотрена, см. 26.08 №2). |
| 3 | Агентные кроны — инструкция в промпте вызывать `report_error.sh` через shell-tool, без отдельного MCP-tool. |
| 4 | Severity на входе не выставляется (дефолт `error`); поле в схеме — для классификации агрегатором и v2. |
| 5 | Дедуп — `sha256(tool:stage:normalized_message)`, окно 24ч, без LLM/fuzzy. |
| 6 | Сводка — ежедневная, доставка в Errors (не Monitoring). |
| 7 | Классификация критичности в сводке — детерминированные regex-правила + порог по `count`, без LLM (§3.7). |
| 8 | Охват — не только кроны: USERTOOLS-код и скиллы тоже подключаются через тот же `report_error.sh`. |
| 9 | Формат Telegram-сообщения — человекочитаемый, не обязан быть машиночитаемым. |
| 10 | Migration Monitoring→Errors — на 25.08 ограничена кронами с `deliver :7`; **26.08 охват расширен на все каналы** (см. №1 ниже). |

### 26.08.2026

| № | Решение | Раздел ТЗ |
|---|---|---|
| 1 | Жёсткое правило: бизнес → свой канал через штатный `deliver` (не трогаем); техника/ошибки → шина, сразу как выявлены; охват — все каналы | §1, §4 |
| 2 | `report_error.sh` шлёт в Errors напрямую (HTTP `sendMessage`, без `parse_mode`), мимо `deliver`/крона — на успехе stderr стирается scheduler'ом | §3.3, §3.10 |
| 3 | Взаимоисключающие режимы инструментирования: Mode A (self-report, инлайн) / Mode B (`error_bus_wrap.sh`) / agent-дефолт reconcile как fallback; `instrumentation_registry.json`, аудит конфликтов через `error_bus_cli.py` | §3.4 |
| 4 | Полнота раскрытия: `wrap` перехватывает любой ≠0 exit (включая синтаксис/OOM/падение до try) до решения о подавлении; новые поля `captured_by`/`script`/`cmdline`/`final_exit_code`/`log_path`/`status`/`resolved_at`/`resolved_note`/`last_notified_at` | §3.2, §3.4 |
| 5 | Связь со штатными механизмами Hermes: `reconcile` только через `hermes` CLI (не файлы ядра напрямую); `error_bus_cli.py` (list/show/resolve/stats/status/audit), `show` — fail-soft read-only указатели на штатные артефакты; мониторинг-кроны — клиенты Mode A для найденных проблем, security — вне охвата | §3.5, §3.6 |
| 6 | `session_key`: заполняется только `reconcile`'ом (job_id+окно → `state.db.sessions`); явный `--session-key` — override; autodetect из env не реализуется; `no_agent` → `NULL` корректно; `reconcile` ежечасно; `llm_anomaly_scan.sh` — клиент шины | §3.6 |
| 7 | Лимиты (`detail` 4KB/`context` 2KB), ретенция (`critical` 180д/`error-warning` 90д/`info` 30д, gzip JSONL + `VACUUM` ежемесячно), агрегированная схема, тротлинг 30 мин (`error`/`warning`), без тротлинга (`critical`) | §3.8 |
| 8 | Сводка: ежедневно 09:00 МСК в Errors, блоки «за 24ч» + «всё ещё открыто» (>3 дней, не resolved) | §3.9 |
| 9 | Кроны (`reconcile`/`digest`/`retention`) — расписания зафиксированы как спецификация; создание в `jobs.json` — отдельным шагом, только по «ставь кроны» | §3.12 |
| 10 | **(правка при реализации)** Общий shared-модуль `_db.py` вместо инлайн `python3 -c "..."` в `report_error.sh` — единая точка bootstrap/дедупа/лимитов/telegram/retention, переиспользуемая `report_error.py`/`error_bus_cli.py`/`reconcile.py`/`retention.py`/`digest.py` | §3.3 |
| 11 | **(правка ранее принятого решения)** Токен Telegram — приоритет `TELEGRAM_BOT_TOKEN` (env, `sirene_vm_bot`), резерв `hermes config get gateway.telegram.token`; причина: бот из `gateway.telegram.token` не в группе «Сирень Workspace», не может слать в топик Errors | §3.3, §3.10 |

### 26.08–27.08.2026 (доработка v0.3.0)

| № | Решение | Раздел ТЗ |
|---|---|---|
| 12 | Авто-закрытие неактуальных `open`-кейсов (запрос Саши: «не выводить неактуальные открытые ошибки») — **гибрид**: (а) SQL-фикс `digest_rows_stale_open` — recency-условие по `last_seen` (N=7 дней) вместо только `first_seen`; (б) основной канал — `auto_resolve_recovered(conn, recoveries)` по `recovery_index` в конце `reconcile()`, `auto_resolved` в результате; (в) fallback для событий без `job_id` — `auto_resolve_dormant(conn, days=DORMANT_DAYS=5)` перед `digest_rows_stale_open` в `digest.py`. Везде `UPDATE status='resolved'`, история сохраняется (без `DELETE`); схема БД не меняется (переиспользуется существующий статус `resolved`); путь `report_error`/`error_bus_wrap.sh`/`severity_rules.py`/`already_reconciled`/`is_recovered` не трогается | §3.2, §3.6, §3.9 |

## §10. Открытые вопросы / риски

1. **Порог `count ≥ 5` для `critical`** — стартовое значение (§3.7), может требовать калибровки после накопления реальных данных за первые недели.
2. ~~Регистрация в `EcosystemManifest.json`~~ — **закрыто 26.08.2026**: `ErrorBus` добавлен в `infra_service` (ключ `error_bus`), `error_bus_instrumentation_registry` — в `entities`, связи с клиентами — в `links`. `render_manifest.py --check-drift` без расхождений по ErrorBus.
3. ~~Первичное заполнение `instrumentation_registry.json`~~ — **закрыто 26.08.2026**: см. §11 «Реализация», фактическая таблица job_id→tool→режим.
4. **Конкретный список секретов для редактирования из `cmdline`** (Mode B, `error_bus_wrap.sh`) — какие паттерны (токены, пароли, API-ключи в аргументах) вырезаются перед записью в БД — уточняется на этапе реализации по фактическому набору кронов, не фиксируется в ТЗ заранее.
5. **Константы авто-resolve (доработка v0.3.0, §9 №12)** — recency-порог N для `digest_rows_stale_open` (предложено **7 дней**) и `DORMANT_DAYS` для `auto_resolve_dormant` (предложено **5 дней**) — стартовые значения, зафиксированы в §3.2/§3.6/§3.9; могут потребовать унификации в одну константу или калибровки после накопления данных по реальной частоте повторов. Нужна ли в сводке строка «N кейсов авто-закрыто» — опционально, не блокирует реализацию (§3.9).

## §11. Реализация (фактическое состояние на 26.08.2026)

Блоки 2/3 (`hermes-feature`) завершены. Код и тесты — на диске, без расхождений с этим разделом.

### 11.1 Фактическая структура файлов

```
~/.hermes/error_bus/
  _db.py                        # shared-модуль: bootstrap/DDL, дедуп, лимиты 4KB/2KB, get_telegram_token()/send_telegram_message(), retention-хелперы
  severity_rules.py             # regex-правила критичности (§3.7)
  report_error.py               # CLI-обёртка над _db.py, вызывается из report_error.sh
  reconcile.py                  # error_bus_reconcile.sh — backfill session_key, fallback-фиксация
  digest.py                     # error_bus_daily_digest.sh — сводка 24ч + «всё ещё открыто»
  retention.py                  # error_bus_retention.sh — архивация + VACUUM
  instrumentation_registry.json # {job_id: "self"|"agent"}, см. 11.2
  events.db                     # SQLite, WAL, bootstrap создаётся _db.py при первой записи
  archive/                      # gzip JSONL по ретенции (§3.8)
  tests/                        # 26 тестов, все зелёные (§7)

~/.hermes/scripts/
  report_error.sh                # единая точка входа, делегирует report_error.py (§3.3)
  error_bus_wrap.sh               # Mode B обёртка (§3.4)
  error_bus_cli.py                 # list/show/resolve/stats/status/audit (§3.5)
  error_bus_reconcile.sh            # запускает reconcile.py
  error_bus_daily_digest.sh          # запускает digest.py
  error_bus_retention.sh              # запускает retention.py
```

### 11.2 Фактическая таблица клиентов (`instrumentation_registry.json`)

Реестр — `{job_id: "self"|"agent"|"wrap"}`. Первый клиент с `wrap` — `proxycheck_linux` (27.08.2026, см. строку в таблице): standalone CLI, сбои процесса перехватываются внешней обёрткой `error_bus_wrap.sh`. Фактическое соответствие job_id → крон → `--tool`:

| job_id | Крон (`jobs.json`) | `--tool` в `report_error.sh` | Режим |
|---|---|---|---|
| `bf52e6985523` | OFC (`ofc_sync.sh`) | `ObsidianFromConfluence` | self |
| `aeeccba37e4a` | `mofs_run_cron.sh` | `MarkObjectsFromSummary` | self |
| `7e013cd5c6f9` | `mofs_index_rebuild.sh` | `MofsIndex` | self |
| `ecf85b797f9a` | `full_workvault_backup.sh` | `WorkVaultBackup` | self |
| `74c93fa1e357` | `restore-all-skills.sh` (restore-skills-daily) | `HermesSkills` | self |
| `5d16b96a9ed5` | `autosync_full_with_cleanup.sh` (GitHub автосинк) | `HermesWorkspaceSync` | self |
| `21255143c523` | `pfs_notify` + `notify_pending.py` (2 точки на одном job_id) | `ProtocolFromSummary` | self |
| `37db83c83e86` | `skill_size_monitor.sh` | `SkillSizeMonitor` | self |
| `d77329d35ca5` | `upstream_monitor.sh` (Upstream hermes-agent monitor) | `UpstreamMonitor` | self |
| `f61b26cbbdf5` | `mfl_urgent_check.py` (MoveFromLoop — срочные) | `MoveFromLoop` | self |
| `2865cc674493` | `mfl_digest.py` (MoveFromLoop — дайджест) | `MoveFromLoop` | self |
| `vm_selfcheck` | Сирень — ежедневный self-check (VM) | — (агентный крон-дефолт) | agent |
| `proxycheck_linux` | standalone CLI `proxycheck_linux` (`~/USERTOOLS/proxycheck/linux-agent/`) | `ProxyCheckLinux` | wrap |

`llm_anomaly_scan.sh` вызывает `report_error.sh --tool LLMAnomalyScan` (Mode A) без собственного `--job-id` в реестре — привязан к self-report точке внутри скрипта, не к отдельному job_id верхнего уровня. `ExchangeMonitor` не имеет отдельной точки `report_error.sh`: технические ошибки идут через общий Exchange-фетчер, используемый `mfl_urgent_check.py`/`mfl_digest.py` (см. `CONF-002` в `EcosystemManifest.json`), т.е. фактически покрыт тем же self-report, что и `MoveFromLoop`.

Итог: 13 названных клиентов (§0 брифа реализации) сведены к 11 уникальным `--tool`-именам + 12 job_id в реестре (agent-fallback `vm_selfcheck` считается отдельно от self-report кронов).

### 11.3 Тесты и статус

26/26 тестов в `~/.hermes/error_bus/tests/` зелёные (§7: дедуп, report_error, severity_rules, fail-soft, wrap, registry_audit, throttle).

### 11.4 Регистрация в экосистеме

`ErrorBus` зарегистрирован в `~/WorkVault/Registries/EcosystemManifest.json`:
- `tools.error_bus` — `category: infra_service`, `status: active`, `path: ~/.hermes/error_bus`, `tz_ref: TZ/ErrorBus/ErrorBus_TZ.md`.
- `entities.error_bus_instrumentation_registry` — `instrumentation_registry.json`, `owner_tool: ErrorBus`, `lifecycle: canonical`.
- `links` — `ErrorBus↔error_bus_instrumentation_registry` (reads_writes), `ObsidianFromConfluence/MoveFromLoop/ProtocolFromSummary → ErrorBus` (writes, репрезентативные клиенты), `ErrorBus → api_telegram` (writes).
- `render_manifest.py --render/--digest/--check-drift` — прогнаны, по ErrorBus расхождений нет.

---

## Контракты экосистемы

### Источник истины
- Владелец записи: ErrorBus (`events.db`, `~/.hermes/error_bus/events.db`, таблица `errors`)
- Реестр инструментирования: ErrorBus (`instrumentation_registry.json`, `~/.hermes/error_bus/instrumentation_registry.json`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| tool | str | required | клиент шины (ObsidianFromConfluence, MoveFromLoop, ProtocolFromSummary, и др.) | CanonicalName из MAIN_TZ_INVENTORY.md |
| message | str | required | клиент шины | текст ошибки/исключения |
| source_kind | enum[cron_script, cron_agent, usertool, skill, integration, other] | optional | клиент шины | дефолт cron_script |
| stage | str | optional | клиент шины | стадия/этап выполнения |
| severity | enum[critical, error, warning, info] | optional | клиент шины | дефолт error |
| exit_code | int | optional | клиент шины | код завершения команды Mode A |
| detail | str | optional | клиент шины | подробный стектрейс/вывод, max 4KB (обрезается) |
| job_id | str | optional | клиент шины | hex id крон-задачи из jobs.json |
| context | str | optional | клиент шины | JSON-строка контекста, max 2KB (обрезается) |
| captured_by | enum[self, wrap, reconcile] | optional | клиент шины | дефолт self |
| script | str | optional | клиент шины | имя/путь скрипта-источника |
| cmdline | str | optional | клиент шины | argv команды (Mode B) |
| log_path | str | optional | клиент шины | путь к лог-файлу |
| session_key | str | optional | клиент шины / error_bus_reconcile | ключ LLM-сессии в state.db |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| text | str | api_telegram | Текст сообщения с подробностями ошибки, без parse_mode |
| chat_id | str | api_telegram | "-1004300127777" (Сирень Workspace) |
| message_thread_id | int | api_telegram | 11112 (топик Errors) |

### Зависимости
- Получает от: [ObsidianFromConfluence, MoveFromLoop, ProtocolFromSummary, MofsIndex, MarkObjectsFromSummary, WorkVaultBackup, HermesSkills, HermesWorkspaceSync, SkillSizeMonitor, UpstreamMonitor, LLMAnomalyScan, ProxyCheckLinux]
- Отдаёт: [api_telegram]

### Breaking changes policy
- Версионирование формата: `events.db` управляемся через DDL с авто-миграцией в `_db.py` (`CREATE TABLE IF NOT EXISTS`).
- При breaking change в схеме `events.db`: добавить миграцию колонок в `_db.py`, сохранить совместимость CLI `report_error.sh`.

### Границы («что НЕ трогать»)
- Не читать и не писать в `executions.db` ядра Hermes.
- Не трогать `scheduler.py` и не менять бизнес-адреса `deliver` у клиентов.
- Не удалять исторические записи из `events.db` при авто-резолве (только `UPDATE status='resolved'`).

