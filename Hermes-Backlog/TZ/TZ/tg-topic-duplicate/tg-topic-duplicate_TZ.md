---
tool: TgTopicDuplicate
type: bugfix
title: "Канонизация Telegram session key: запрет слота thread: (дубли general:1 / monitoring:7)"
version: 0.1.0
date: 2026-09-26
status: approved
author: архитектор (cursor-grok-4.6-high)
last-section-added: 2026-09-26 — TZ:patch v0.1.0: новый мастер-ТЗ FULL BUGFIX по диагнозу 24.09
workspace: ~/hermes-agent
diagnose: ~/hermes-agent/_fix_plan_20260924-tg-topic-duplicate.md
source_graph: DEV/tg-topic-duplicate
case: BUGFIX
classification: FULL
depends_on:
  - ~/hermes-agent/gateway/session.py
  - ~/hermes-agent/gateway/kanban_watchers_notifier.py
  - TZ/TelegramGroupTopics/TelegramGroupTopics_TZ.md (топики TG «Сирень Workspace», канон 7; forum/session keys там были вне скоупа)
  - TZ/ErrorBus/ErrorBus_TZ.md (разделение бизнес-канала Monitoring:7 vs техника Errors:11112)
  - TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md (kanban_notify_subs / подписки R5: Monitoring:7)
reuse_first: "не USERTOOL и не новый скилл; патч 2 файлов ядра gateway + ремонт данных kanban.db/state.db; session.py — shared-модуль роутинга → FULL BUGFIX, не LIGHT"
---

# TgTopicDuplicate — FULL BUGFIX канонизации идентичности Telegram-сессии

## Форма ТЗ

Это **новый самостоятельный мастер-ТЗ багфикса** (не секция внутри `TelegramGroupTopics`). Решение графа `DEV/tg-topic-duplicate` (Саша 26.09): FULL BUGFIX.

Близость к `TelegramGroupTopics` (топики группы `-1004300127777`) не делает этот кейс доработкой того ТЗ: там (v0.1.0 П.5 / v0.3.0) forum-роутинг и session keys были **явно вне скоупа** («Не чинить forum `_effective_message_thread_id` / session keys»). Этот файл — владелец именно той поверхности.

Классификация (из `BUG:diagnose`, утверждена на графе): **FULL BUGFIX**, не BUGFIX-LIGHT. Поверхность малая (2 файла кода + ремонт данных), но `gateway/session.py` — **shared-модуль** всего роутинга. По `GLOSSARY.md` LIGHT = ≤3 файла **вне** shared-модулей. Финальная классификация — на `GATE:diagnose-review`; Саша 26.09 зафиксировал FULL.

Кейс по `GLOSSARY.md` §2: `BUGFIX` = `DX` → `BRF(delta)` → `TZ-WRITE(patch)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL` (`HF:compress` skip; `REV:tz` по таблице OFF при ≤3 файлах, но shared → полный хвост с `HF:plan` / `REV:plan` / `GATE:plan-approve`).

Эта фаза (`TZ:patch`) пишет **только этот файл**. `MAIN_TZ_INVENTORY.md` — `TZ:finalize`. Код / `.env` / yaml / скиллы / telegram-адаптер / манифест / глоссарий — не трогать из этой фазы.

Диагноз (read-only, вход целиком): `~/hermes-agent/_fix_plan_20260924-tg-topic-duplicate.md` (`BUG:diagnose` 2026-09-24).

---

## Цель

Убрать дубли ответов Сирени в топиках general (`:1`) и monitoring (`:7`) группы `-1004300127777`, канонизировав идентичность сессии так, чтобы один физический Telegram-группос-топик никогда не кейлился как `thread:` и все wake/inbound сливались в одну `group:`-сессию.

## Симптом

Одно и то же сообщение Сирени приходит в **два** топика группы `-1004300127777`: general (`:1`) и monitoring (`:7`).

Наблюдение оператора: дубль виден одновременно в обоих топиках. Корневая механика — не «два send в один turn одного хелпера», а **две разошедшиеся Hermes-сессии** на один физический чат+топик, каждая выдаёт свой ответ в свой лейни (включая general `:1` при опущенном/фолбек-`thread_id`).

## Root cause

**Двойная (разошедшаяся) Hermes-сессия для одного физического чата+топика monitoring (`:7`), созданная утечкой `chat_type='thread'` из подписок канбана в wake-источник.**

Подтверждено фактами (`BUG:diagnose` 24.09), не гипотеза.

### Цепочка факторов

1. **Два набора notify-подписок на Monitoring:7.** В `kanban_notify_subs` (`~/.hermes/kanban.db`) для `chat_id=-1004300127777`, `thread_id=7` имеется 40 подписок: **26** с `chat_type='group'` и **14** с `chat_type='thread'` (включая все карточки недавних BUGFIX-графов: `t_d825c610`, `t_8092d149`, `t_af93edd0`, `t_c81bb8fe`, `t_0ec25672`, `t_94d917b3`, `t_ade34290`, `t_56b23dc6`, `t_466dcf8d` и др.).

2. **Notifier пробрасывает `chat_type` в wake-источник** (`gateway/kanban_watchers_notifier.py`, ≈530–532):

   ```
   _chat_type = sub.get("chat_type") or _delivery_meta.get("chat_type") or ""
   SessionSource(..., chat_type=_chat_type or "group", thread_id=sub.get("thread_id") or None, ...)
   ```

   Для `'thread'`-подписок wake-источник получает `chat_type='thread'`.

3. **`build_session_key` формирует РАЗНЫЙ ключ для одного чата+топика** (`gateway/session.py`, ≈674):

   ```
   chat_type_slot = "thread" if thread_id and not source.thread_id else source.chat_type
   ```

   - источник с `chat_type='group'`, `thread_id=7` → ключ `agent:main:telegram:group:-1004300127777:7`;
   - источник с `chat_type='thread'`, `thread_id=7` → ключ `agent:main:telegram:thread:-1004300127777:7`.

4. **Две живые сессии на monitoring:7** (`state.db`, sessions где `chat_id='-1004300127777'`, `chat_type IN (group, thread)`; thread-вариант единственный в чате, `n_thread=1`):

   | session_key | id | Факт |
   |---|---|---|
   | `agent:main:telegram:group:-1004300127777:7` | `20260924_100136_da2ca972` | 209 сообщений; каноническая |
   | `agent:main:telegram:thread:-1004300127777:7` | `20260924_125245_3924695c` | рождена **12:52:45** из `internal_notification` `[kanban] Task t_880b91fd completed` — канальный wake `'thread'`-подписки |

5. **Одна и та же входящая активность в `:7` обрабатывается ДВУМЯ сессиями** — и реальное сообщение Саши в `:7`, и каждый kanban-completion wake `'thread'`-подписки запускают **оба** turn в обеих сессиях. Каждая выдаёт свой ответ → то же содержание уезжает в разные лейны (включая general `:1` при опущенном/фолбек-thread). Это и есть «дубль в general и monitoring».

Критично: код notifier прямо пишет «a mismatch only degrades to a fresh session» — ровно то, что произошло: `chat_type='thread'` в подписке создал **параллельную свежую сессию** вместо того, чтобы присоединиться к канонической `group:...:7`.

Инвариант канона (этот ТЗ): **X физический Telegram-группос-топик НИКОГДА не кейлится как `thread:`**. Telegram нормализует чат к `group`/`forum` (`_normalize_chat_type` не возвращает `'thread'`); слот `thread` легитимен только для Discord / relay auto-thread лейнов.

### Вторичные / сопутствующие находки (НЕ причина дубля)

Зафиксированы диагнозом; в скоуп П.1–П.4 **не входят**, кроме операционного следствия A (рестарт по «поднимай»).

- **A. Config-drift.** Текущий gateway на момент диагноза запущен 23.09 16:18, а `config.yaml` изменён 23.09 19:07 — работающий процесс держит конфиг **до** правки (allowlist/топики из памяти до рестарта). После кодового фикса нужен рестарт gateway по явному «поднимай» от Саши (это П.4).
- **B. Повтор тревоги** «final stream delivery not confirmed; sending first response before continuing» (8–9× за 24.09) — вторичный вектор двойной отправки **внутри** turn (стриминг + повторный send первого ответа). Обычно в тот же топик; усугубляет кроссинг при двойной сессии, но не корень. Отдельная карточка, не этот фикс.
- **C. Отдельный баг ядра (П.5).** `TypeError: _to_thread_process_service() got an unexpected keyword argument 'max_in_progress_per_profile'` в `gateway/kanban_watchers.py:306-310` — сигнатура `func, /, *args` (только позиционные + `*args`) не принимает kwargs. Возникает на каждом тике диспетчера, когда `ready_pending` и нет спавнов. Касается канбан-диспатча, **не** telegram-дубля. Собственная карточка `BUG:diagnose`, не этот фикс.

---

## План починки П.1–П.4 (П.5 — вне скоупа)

Дословно по смыслу и точкам из диагноза; очередь реализации для `HF:impl` после `GATE:take-into-work`.

### П.1 (корневой фикс, канонизация идентичности)

Сделать так, чтобы X физический Telegram-группос-топик **НИКОГДА** не кейлился как `thread:`. Telegram нормализует чат к `group`/`forum` (`_normalize_chat_type` не возвращает `'thread'`); слот `thread` легитимен только для Discord/relay auto-thread лейнов.

**Точка:** в `gateway/session.py#build_session_key` для `Platform.TELEGRAM` не использовать слот `'thread'` (мапить `'thread'`→`'group'` для telegram) **ИЛИ** в telegram-адаптере нормализовать входящий `chat_type` `'thread'`→`'group'`.

**Рекомендация архитектора (закрывает вилку для `HF:impl`):** править **`build_session_key`** — это слой идентичности, через него проходят и inbound, и wake, и любой другой `SessionSource`. Адаптер — опциональный второй замок; в этом проходе **не обязателен** и **не входит** в обязательную поверхность (2 файла). Слот `'thread'` для не-Telegram платформ не трогать.

### П.2 (заткнуть утечку в notifier)

В `gateway/kanban_watchers_notifier.py#wake` (≈530–532) для `Platform.TELEGRAM` приложить `chat_type='group'`, когда `thread_id` присутствует (**никогда** `'thread'`), чтобы wake **сливался** в каноническую group-сессию. Это предотвращает новые форки независимо от данных подписок.

Даже если на диске останется «грязная» `'thread'`-подписка, wake не должен породить `telegram:thread:…`.

### П.3 (ремонт данных на диске)

- Переписать **14** `'thread'`-подписок Monitoring:7 (`kanban_notify_subs`) на `chat_type='group'` **и** убрать `'thread'` из `delivery_metadata.chat_type` **ИЛИ** снять устаревшие старые подписки. По канону подписки графа — только Monitoring:7, `chat_type='group'` (DevKanbanPipeline R5).
- **Рекомендация:** переписать, не снимать — иначе потеряется R5 `notify+wake` на живых карточках (`t_d825c610`, `t_8092d149`, …). Снятие — только если подписка доказуемо орфан (карточки уже нет).
- Заархивировать / «убить» вилку-сессию `agent:main:telegram:thread:-1004300127777:7` (id `20260924_125245_3924695c`), чтобы будущая активность `:7` шла только через `group:...:7` (`20260924_100136_da2ca972`).
- **Рекомендация:** архивировать (сохранить историю 12:52-форка), не hard-delete. Каноническую group-сессию не трогать.

### П.4 (операционный)

После кодового фикса — restart gateway по явному «поднимай» от Саши (загрузка актуального `config.yaml` + подписок; снимает и вторичный config-drift A). Gateway **НЕ** рестартовать самому. Не из `TZ:patch` / `TZ:finalize` / `HF:impl` без императива.

### П.5 (вне скоупа — отдельный баг)

Recurring `TypeError: max_in_progress_per_profile` в `gateway/kanban_watchers.py:306-310` → собственная карточка `BUG:diagnose` (не в этом фиксе). В этом ТЗ **не чинить**.

---

## Шаги реализации (атомарно)

Для `HF:impl` / `HF:test` после `GATE:take-into-work` + `HF:plan` (полный хвост FULL BUGFIX). Один шаг ≠ один `agent -p` автоматически, но каждый шаг атомарно проверяем.

1. **`HF:backup`.** Снимок в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`: `~/hermes-agent/gateway/session.py`, `~/hermes-agent/gateway/kanban_watchers_notifier.py`, `~/.hermes/kanban.db`, `~/.hermes/state.db` (и по канону бэкапа — `config.yaml`). Не рестартовать gateway.
2. **П.1 — канонизация ключа.** В `~/hermes-agent/gateway/session.py#build_session_key`: для `Platform.TELEGRAM` слот `'thread'` не использовать; мапить `'thread'`→`'group'` (и любой вход, где `source.chat_type == 'thread'` при telegram, схлопывать в `'group'`). Не-Telegram платформы без изменений. Адаптер в этом проходе не патчить, если ключ закрывает оба пути (inbound + wake).
3. **П.2 — утечка notifier.** В `~/hermes-agent/gateway/kanban_watchers_notifier.py#wake` (≈530–532): для `Platform.TELEGRAM` при наличии `thread_id` выставлять `chat_type='group'` в `SessionSource`, **никогда** `'thread'`. Не брать `'thread'` из `sub.chat_type` и не из `delivery_metadata.chat_type`.
4. **Юнит-тесты идентичности (без живого Telegram).**
   - `build_session_key(Platform.TELEGRAM, chat_type='thread', thread_id=7, chat_id=-1004300127777)` → ключ **без** слота `thread:` (ожидание `…:group:-1004300127777:7`).
   - тот же вход с `chat_type='group'` → тот же ключ (слияние, не вторая сессия).
   - Discord/relay с `chat_type='thread'` + `thread_id` → слот `thread` **сохраняется** (регрессия чужих платформ).
   - wake-конструктор: telegram + `thread_id` + грязный `sub.chat_type='thread'` → в `SessionSource` уходит `'group'`.
5. **П.3а — ремонт подписок.** В `~/.hermes/kanban.db`, таблица `kanban_notify_subs`: для `chat_id='-1004300127777'` AND `thread_id=7` AND `chat_type='thread'` — UPDATE `chat_type='group'`; в JSON `delivery_metadata` заменить `chat_type: thread` → `group` (или удалить ключ, если он только дублирует колонку). Предпочтительно идемпотентный скрипт/SQL в ходе `HF:impl`, не ручной одноразовый sqlite без бэкапа. Не снимать живые R5-подписки графа.
6. **П.3б — вилка-сессия.** В `state.db` заархивировать / деактивировать сессию id `20260924_125245_3924695c` (`session_key=agent:main:telegram:thread:-1004300127777:7`). Канон `20260924_100136_da2ca972` (`group:…:7`) не удалять, не prune-ить, не переименовывать. После архива `SELECT` по ключу `telegram:thread:-1004300127777:7` не возвращает живую сессию.
7. **Не рестартовать gateway.** Напечатать «нужен рестарт — ждать „поднимай“». Config-drift A сам не рассосётся до рестарта.
8. **П.4 — только по императиву Саши «поднимай».** Restart gateway. После старта: актуальный `config.yaml` в памяти + новые ключи/подписки.
9. **E2E / наблюдение (AC-005).** Активность в `:7` (сообщение Саши и/или kanban-completion wake) идёт **только** через `group:…:7`; новая `thread:…:7` не рождается; дубли general `:1` / monitoring `:7` не воспроизводятся. Смотреть оба топика и `state.db` (число живых сессий на этот chat+thread).
10. **Не закрывать** корень/граф `DEV/tg-topic-duplicate` до `GATE:done`. П.5 (`TypeError`) — не патчить; при необходимости завести отдельную карточку `BUG:diagnose` **после** или параллельно, не внутри этого impl.

`ORCH:shared-state` в этом кейсе: манифест/скиллы/digest **не** меняются (нет новой сущности, нет правки скилла). Координатор не вызывает restore ради этого фикса. `TZ:finalize` позже допишет строку инвентаря — не исполнитель.

---

## Что НЕ трогать

- `extra_or_secret` (env-over-YAML) — контракт после `3dedb71f2f` / TelegramGroupTopics. Не менять.
- UNION allowlist yaml∪env — **запрещён**.
- Gateway не рестартовать самому (только по императиву Саши «поднимай»). Не из `TZ:*`, не из скрипта ремонта данных.
- Корень / граф `DEV/tg-topic-duplicate` — не закрывать до `GATE:done`.
- Баг TypeError (П.5, `kanban_watchers.py:306-310`, `max_in_progress_per_profile`) — в этом фиксе **не чинить**.
- Telegram-адаптер (`plugins/platforms/telegram/adapter.py`) — не обязателен в этом проходе; forum-хелперы `_effective_message_thread_id` не переписывать «заодно».
- Слот `'thread'` для Discord / relay auto-thread — не запрещать глобально, только для `Platform.TELEGRAM`.
- Каноническая сессия `agent:main:telegram:group:-1004300127777:7` (`20260924_100136_da2ca972`) — не удалять, не prune.
- `tutu-telegram-delivery` / снимок 7 топиков / `restore_telegram_topics.sh` — не этот фикс.
- ErrorBus (`events.db`, `report_error.sh`, топик Errors `:11112`) — бизнес-канал Monitoring `:7` не переключать; шину не расширять.
- Ядро канбана `kanban_db.py` / `kanban_db_notify.py` / `TERMINAL_KINDS` — не менять схему подписок; только данные `kanban_notify_subs` (chat_type) и код notifier wake.
- `jobs.json`, кроны, `.env`, `TELEGRAM_ALLOWED_CHATS`, полный токен в ТЗ/логах/коммитах.
- `channel_directory.json` как «бэкап топиков»; multiplex; `drop_pending_updates`; ручной `getUpdates`.
- Вторичный вектор B (stream delivery not confirmed) — не этот фикс.
- `GLOSSARY.md`, `EcosystemManifest`, скиллы пайплайна — не эта фаза и не этот impl.

---

## Связи с экосистемой

Это **FULL BUGFIX** (2 файла кода + ремонт данных; `session.py` shared → **не LIGHT**).

| Что | Связь |
|---|---|
| core gateway `gateway/session.py` | shared-модуль роутинга; `build_session_key` — точка канона идентичности (П.1). Любая платформа читает этот ключ. Патч **только** ветки `Platform.TELEGRAM`. |
| core gateway `gateway/kanban_watchers_notifier.py` | `wake` ≈530–532 пробрасывал `chat_type` из подписки → утечка `'thread'` (П.2). |
| `state.db` sessions | вилка `thread:-1004300127777:7` id `20260924_125245_3924695c`; канон `group:…:7` id `20260924_100136_da2ca972`. Ремонт П.3б. |
| TelegramGroupTopics | канон 7 топиков группы «Сирень Workspace» (`-1004300127777`): General=1, Tools=3, WorkVault=5, Backlog=6, Monitoring=7, Errors=11112, Personal=8. Тот ТЗ **не** чинил session keys. Этот ТЗ — владелец канона `group:` vs запрет `thread:` для Telegram. |
| `tutu-telegram-delivery` | человекочитаемый каталог топиков / restore-снимок; потребители пишут `telegram:-1004300127777:<thread>`. Каталог не менять. |
| DevKanbanPipeline | `kanban_notify_subs` / подписки R5: канал по умолчанию Monitoring:7, `chat_type='group'`, `notify+wake` на корне и AC-гейтах. 14 `'thread'`-строк — drift данных, не смена R5. |
| ErrorBus | техника → Errors `:11112` напрямую (`TELEGRAM_BOT_TOKEN`); бизнес → свой `deliver` (Monitoring `:7` не переключать). Симптом дубля — бизнес-лейны `:1`/`:7`, не шина. |
| App:Telegram (digest) | канал связи с Сашей; inbound/outbound топиков группы. |
| `config.yaml` / allowlist | вторичный drift A; лечится рестартом П.4, не правкой allowlist. Контракт env-over-YAML не трогать. |

Digest (`EcosystemManifest.digest.md`, срез 2026-09-24): `TelegramGroupTopics` active infra-plan (`ent:sirene_workspace_topics`); `DevKanbanPipeline` active infra_service; `ErrorBus` active infra_service (`ent:error_bus_instrumentation_registry`); App:Telegram = gateway/уведомления. Новой сущности в манифест **не** заводить: это патч ядра, не USERTOOL.

---

## Контракты экосистемы

### Источник истины

- Владелец **идентичности сессии** (ключ `agent:main:telegram:<slot>:<chat_id>:<thread_id>`): `gateway/session.py#build_session_key`. После этого ТЗ для Telegram `<slot>` ∈ {`group`, `forum`, …} — **не** `thread`.
- Владелец **каталога топиков** (имена→`thread_id`): снимок `tutu-telegram-delivery` / TelegramGroupTopics v0.3.0 (ровно 7). Этот ТЗ каталог не меняет.
- Владелец **подписок notify/wake** графа: данные `kanban_notify_subs` + CLI `hermes kanban notify-subscribe`; канон канала R5 = Monitoring:7, `chat_type='group'`. Схема таблицы — ядро канбана (не трогать).
- Владелец **живых сессий**: `state.db` (`sessions`). Этот ТЗ архивирует одну вилку, не меняет схему.
- Владелец inbound-allowlist: env `TELEGRAM_ALLOWED_CHATS` (если непустой) иначе YAML — **не этот ТЗ**.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| Platform | enum | required | gateway / notifier / adapter | `TELEGRAM` — ветка канона; прочие без изменений |
| SessionSource.chat_type | str | optional | inbound adapter **или** `kanban_notify_subs.chat_type` / `delivery_metadata.chat_type` | до фикса: `group` \| `thread` \| `forum` \| …; после П.2 для telegram+`thread_id` wake всегда отдаёт `group` |
| SessionSource.thread_id | int \| str \| None | optional | топик TG / подписка | для Monitoring: `7`; General: `1` |
| SessionSource.chat_id | str | required | Telegram / подписка | `-1004300127777` (группа «Сирень Workspace») |
| kanban_notify_subs.chat_type | str | required (колонка) | DevKanbanPipeline R5 / notify-subscribe | канон `group`; drift `thread` — чистить П.3 |
| kanban_notify_subs.delivery_metadata.chat_type | str | optional | JSON метаданных подписки | не должен содержать `thread` после П.3 |
| kanban_notify_subs.thread_id | int | required для топика | R5 | `7` для Monitoring |
| sessions.id (вилка) | str | required для П.3б | state.db | `20260924_125245_3924695c` |
| sessions.session_key (вилка) | str | required для П.3б | state.db | `agent:main:telegram:thread:-1004300127777:7` |
| sessions.id (канон) | str | required (не трогать) | state.db | `20260924_100136_da2ca972` |
| sessions.session_key (канон) | str | required (не трогать) | state.db | `agent:main:telegram:group:-1004300127777:7` |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| session_key (Telegram + топик) | str | gateway routing, state.db, notifier wake | `agent:main:telegram:group:<chat_id>:<thread_id>` — **без** `:thread:` |
| SessionSource.chat_type (wake, Telegram, thread_id set) | str | `build_session_key` | всегда `group` |
| kanban_notify_subs.chat_type (Monitoring:7) | str | notifier | `group`; `SELECT … WHERE chat_type='thread'` → 0 строк |
| живые sessions на `-1004300127777` + thread 7 | count | оператор / AC-005 | ровно каноническая `group:`-сессия; `thread:`-вилка не живая |
| outbound в топик | int | Telegram (Саша) | ответ в тот же `message_thread_id`, что inbound/wake; без фантомной копии в `:1` |
| session_key (Discord/relay + thread) | str | чужие платформы | слот `thread` **сохраняется** (не регрессия) |

### Зависимости

- Получает от: [Telegram inbound / forum thread_id, `kanban_notify_subs` + `kanban_watchers_notifier.wake`, канон топиков TelegramGroupTopics / `tutu-telegram-delivery`]
- Отдаёт: [единственная каноническая group-сессия на физический TG-топик; ответы в тот же `message_thread_id`; R5-wake в Monitoring:7 без форка]

### Breaking changes policy

- Смена слота ключа для Telegram (`thread` → `group`) — **намеренный breaking** старых `telegram:thread:…` ключей. Живые такие сессии архивировать (П.3б), не мигрировать историю сообщений в group-сессию в этом проходе (канон уже имеет 209 сообщений).
- Схема `kanban_notify_subs` / `state.db` не меняется — только значения `chat_type` и статус вилки.
- Версия этого ТЗ (`0.1.0`) ≠ версия ядра hermes-agent. Патч ядра не бампит TelegramGroupTopics / ErrorBus / DevKanbanPipeline.
- Повторный drift `'thread'` в новых подписках: П.2 делает его безвредным для ключа; П.1 закрывает любой другой вход. Новые subscribe-вызовы должны писать `group` (канон R5) — смена CLI ядра не в скоупе.

### Границы («что НЕ трогать») — контрактный повтор

- Не UNION yaml∪env; не трогать `extra_or_secret`.
- Не глобальный запрет слота `thread` вне Telegram.
- Не рестарт gateway без «поднимай».
- Не чинить П.5 TypeError.
- Не закрывать `DEV/tg-topic-duplicate` до `GATE:done`.
- Не менять ErrorBus-канал `:11112` и бизнес-`deliver` `:7`.

---

## Критерии приёмки (AC)

Маркер I1: **target** (эта работа). `current` = прод на диагнозе 24.09 (две сессии, 14 `thread`-подписок, дубли `:1`/`:7`).

Якоря стабильны. Формулировки — наблюдаемые (команда / артефакт / поведение). Нормативный язык — стиль, не парсер-гейт. Выдача списка Саше — ход `TZ:finalize` → `GATE:take-into-work` (диалог, не Monitoring:7).

### AC-001 — канон ключа в `session.py`

Проверка кода `~/hermes-agent/gateway/session.py` (`build_session_key`): для `Platform.TELEGRAM` функция **никогда** не даёт ключ со слотом `'thread'` (ни когда `source.chat_type='thread'`, ни когда внутренний тернар выбирал бы `"thread" if thread_id and not source.thread_id`). Наблюдаемо: grep/normalize + юнит из шага 4 → ключ вида `agent:main:telegram:group:-1004300127777:7`, не `…:thread:…`.

### AC-002 — wake без утечки `'thread'`

Проверка кода `~/hermes-agent/gateway/kanban_watchers_notifier.py#wake` (≈530–532): для `Platform.TELEGRAM` при присутствующем `thread_id` в `SessionSource` приложен `chat_type='group'`, **не** `'thread'` — даже если `sub.chat_type` или `delivery_metadata.chat_type` равны `'thread'`. Наблюдаемо: чтение патча + юнит wake-конструктора.

### AC-003 — ремонт подписок Monitoring:7

В `kanban_notify_subs` для Monitoring:7 (`chat_id='-1004300127777'`, `thread_id=7`) нет `'thread'`-подписок.

Наблюдаемо:

```sql
SELECT COUNT(*) FROM kanban_notify_subs
 WHERE chat_id='-1004300127777' AND thread_id=7 AND chat_type='thread';
-- → 0
```

Плюс в `delivery_metadata` тех же строк нет `chat_type`=`thread` (14 бывших thread-строк переписаны в `group` либо явно сняты как орфаны). Живые R5-подписки графа на `:7` сохранились с `chat_type='group'`.

### AC-004 — вилка-сессия убрана

Сессия `agent:main:telegram:thread:-1004300127777:7` (id `20260924_125245_3924695c`) заархивирована / удалена (не живая). Канон `agent:main:telegram:group:-1004300127777:7` (id `20260924_100136_da2ca972`) на месте.

Наблюдаемо: `state.db` — вилка не active/не выбирается роутером; group-сессия жива.

### AC-005 — после «поднимай»: один лейни, без дубля

После явного «поднимай» Саши — restart gateway. Активность `:7` (inbound Саши и/или kanban wake) идёт **только** через group-сессию; новая `thread:…:7` не появляется; дубли не воспроизводятся.

Наблюдаемо: топики general `:1` и monitoring `:7` (нет второй копии того же ответа Сирени); `state.db` — одна живая сессия на этот chat+thread; `gateway.log` без пары параллельных turn на оба ключа.

### AC-006 — регрессия чужих платформ

`build_session_key` для не-Telegram (Discord / relay auto-thread) по-прежнему может дать слот `'thread'`. Наблюдаемо: юнит шага 4 (Discord+thread_id → ключ содержит `:thread:`).

### AC-007 — контракты allowlist не тронуты

`extra_or_secret` / env-over-YAML и запрет UNION yaml∪env не изменены. Наблюдаемо: diff не содержит правок `extra_or_secret`, `.env` `TELEGRAM_ALLOWED_CHATS`, логики allowlist в адаптере.

### AC-008 — П.5 вне поставки

`gateway/kanban_watchers.py` строки ≈306–310 (`max_in_progress_per_profile` / `_to_thread_process_service`) **не** являются частью этого фикса. Наблюдаемо: diff поставки не чинит этот TypeError.

### AC-009 — граф жив до `GATE:done`

Корень `DEV/tg-topic-duplicate` не complete до приёмки `GATE:done`. Наблюдаемо: граф на доске открыт после `HF:impl`/`HF:test`; закрытие — только хвост с отчётом AC.

### AC-010 — рестарт не самовольный

Исполнитель / скрипт ремонта **не** рестартовал gateway до фразы Саши «поднимай». Наблюдаемо: в отчёте `HF:impl` нет самовольного restart; П.4 выполнен только после императива (или явно помечен «ждёт поднимай»).

---

## Открытые вопросы

Бриф/диагноз закрыты Сашей 26.09 (FULL BUGFIX, отдельный мастер-ТЗ, граф `DEV/tg-topic-duplicate`). Ниже — развилки `HF:impl`, не блокеры `TZ:patch`. Снять может Саша; иначе исполнитель идёт по рекомендации.

**OQ-1. П.1: только `session.py` или ещё адаптер?**  
Диагноз допускает ИЛИ. Рекомендация: только `build_session_key` (слой ключа закрывает inbound и wake). Адаптер — не в обязательной поверхности; «заодно» не трогать forum-хелперы (граница TelegramGroupTopics + «Что НЕ трогать»).

**OQ-2. П.3: переписать 14 подписок или снять?**  
Рекомендация: UPDATE в `group` + вычистить `delivery_metadata`, чтобы R5 на живых карточках сохранился. Снимать только орфаны (нет карточки).

**OQ-3. П.3б: архив vs hard-delete вилки?**  
Рекомендация: архив / `active=0` / принятый в ядре prune-флаг — сохранить id `20260924_125245_3924695c` как историю форка. Hard-delete не нужен для AC-004.

**OQ-4. Переносить ли сообщения вилки (12:52+) в group-сессию?**  
Рекомендация: нет, не в этом проходе. Канон уже 209 сообщений; склейка истории — отдельный CHANGE, не блокер дубля.

**OQ-5. Вторичный вектор B (stream delivery not confirmed)?**  
Не этот фикс. Отдельная карточка, если повторится после слияния сессий (тогда это уже внутри одного turn, не кросс-топиковый дубль).

**OQ-6. Когда заводить `BUG:diagnose` на П.5 TypeError?**  
Не внутри этого графа. Рекомендация: отдельный корень после `GATE:diagnose-review` того бага (GLOSSARY §5.2.9: старт BUGFIX = корень + `BUG:diagnose` в одном create). Этот ТЗ его не открывает.

Открытых вопросов к содержанию **этого** ТЗ (цель, корень, П.1–П.4, запреты, AC) нет.

---

## Статус

`approved` — `TZ:patch` v0.1.0, 2026-09-26, архитектор (`cursor-grok-4.6-high`). Вход: полный `_fix_plan_20260924-tg-topic-duplicate.md`. Согласование ТЗ ≠ «берём в работу»: код и ремонт данных — после `TZ:finalize` + `GATE:take-into-work`. Gateway — только по «поднимай».

**Поставка `HF:impl` / `HF:test` (2026-09-28):** П.1 (`gateway/session.py#build_session_key`, Telegram `thread`→`group`), П.2 (`kanban_watchers_notifier.py`, `canonical_wake_chat_type` + wake), П.3а/П.3б ремонт данных (`scripts/repair_tg_topic_duplicate.py`, kanban.db + state.db). 32 юнит-теста зелёные; AC-001…AC-009 выполнены на диске. П.4 / AC-005 — gateway **не** рестартован, ждёт явного «поднимай» (AC-010). Корень `DEV/tg-topic-duplicate` открыт до `GATE:done` (AC-009). П.5 (`kanban_watchers.py` TypeError) вне поставки (AC-008).
