---
title: _fix_plan — topic-origin-routing (политика топик-инициатор)
slug: topic-origin-routing
version: 1.2
date: 2026-09-26
case: BUGFIX
classification: FULL (не LIGHT)
status: diagnose
owner: ProcessImprovement / DevKanbanPipeline
kanban: DEV/topic-origin-routing · корень = t_5241780b · BUG:diagnose = t_efbb86ba
depends_on: DEV/tg-topic-duplicate (t_ff1191b0) — identity-фикс session key
diagnose_role: архитектор (cursor-grok-4.6-high)
diagnose_meta: |
  GATE:diagnose-review agreement-loop (REV:tz 26.09, recheck): TZ master DKP
  v0.3.8 status=approved уже на диске (mtime 2026-09-26 23:34:04 +03).
  Совпадает с §3+П.1, кроме дельты §3.1 шаг 3 (пустая thread_id → SILENCE) —
  разрешённый точечный addendum на TZ:finalize (П.1δ), не rewrite канона канала.
  Остальной текст v0.3.8 не переписывать. См. comment GATE:diagnose-review (item-0).
---

# План починки — политика «топик-инициатор»

Требование Саши 26.09: коммуникация по кейсу/графу идёт **только** в топике-инициаторе
(откуда создана карточка). Канбан-уведомления **не** хардкодятся в Monitoring `:7`.

Рабочий канал wake/notify = **`kanban_notify_subs.thread_id`**, не metadata карточки.

## 0. Классификация

**FULL BUGFIX**, не BUGFIX-LIGHT.

| Критерий LIGHT | Факт |
|---|---|
| ≤3 файла кода+тесты вне shared | формально 2 `SKILL.md` + аддитивная секция ТЗ, **без** Python |
| без новых сущностей/cron/.env/манифеста | да |
| вне shared-модулей | скиллы — да; ядро `kanban_db*` не трогаем |
| «механический патч» | **нет**: это смена канона R5, перекрытие решения Саши 24.09 т.3 / DKP п.15 |

Почему не LIGHT: нужен **consensus ТЗ** (много секций DKP называют Monitoring `:7`
единственным каналом по умолчанию) + семантический алгоритм origin (корень vs дети,
DM-тишина, запрет `:11112`, копирование `thread_id` с корня). GLOSSARY §2 LIGHT
после `GATE:diagnose-review` здесь **не** выбирать.

Кейс после гейта (GLOSSARY §2/§5.2 **BUGFIX** полный):
`TZ:patch` → `TZ:finalize` → `GATE:take-into-work` (HITL never auto, payload=AC)
→ `HF:plan` → `[REV:plan]` → `GATE:plan-approve` (always auto) → `HF:backup`
→ `HF:impl` → `HF:test` → `HF:docs-handoff` → `ORCH:shared-state` → `GATE:done`.

Skip `HF:compress`. `REV:tz` — таблично OFF при ≤3 файлах, но это **не** LIGHT:
канон DKP меняется семантически → `REV:tz` **оставить** (ревью текста политики).

`HF:impl` этой политики **не стартует**, пока не снят identity-прекондицион
`DEV/tg-topic-duplicate` (см. §2). `TZ:patch`/`TZ:finalize` можно параллельно
с хвостом duplicate (только текст) — **не** с открытым `GATE:diagnose-review`.

### Заметка гейта (item-0 / REV:tz 26.09)

На момент этого `GATE:diagnose-review` master DKP уже `version: 0.3.8`,
`status: approved` (mtime 2026-09-26 23:34:04 +03; `last-section-added`:
«v0.3.8 R5 origin-топик инициатора; перекрытие п.15/т.3 24.09»). Содержание
совпадает с §3+П.1, **кроме** дельты §3.1 шаг 3 (пустая строка `thread_id` =
отсутствие origin → SILENCE) — её нет в master (rg = 0); это **не** полный
текстуальный match. Этот сеанс ревизии диагноза master-ТЗ **не писал**
(read-only). Диск опередил гейт: запись `TZ:patch`/`TZ:finalize` пошла
параллельно с DX-гейтом, хотя цепочка требует текст **после** ратификации.
Второй rewrite канала **запрещён**. Единственная разрешённая правка master
после гейта — П.1δ (одна строка в `resolve_origin`, `TZ:finalize`).
Подробности — comment на `GATE:diagnose-review`.

## 1. Диагноз (подтверждён по диску, read-only)

### 1.1 Что должен делать канал

Терминальные события R5 (`notify+wake` на корне + AC/HITL-гейтах) должны
приземляться в **тот же forum-топик группы** `-1004300127777`, из которого
оркестратор завёл корень `DEV/<slug>` (или `IDEA/<slug>`).

Не в фиксированный Monitoring `:7`, не в DM, не в Errors `:11112`.

### 1.2 Почему «положить origin в metadata карточки» недостаточно

Wake **не читает** body/metadata задачи. Канал собирается только из строки
`kanban_notify_subs`:

| Слой | Файл | Что берёт |
|---|---|---|
| ключ сессии | `gateway/kanban_watchers_notifier.py` `wake` ≈530–533 | `SessionSource(chat_id=sub.chat_id, chat_type=sub.chat_type, thread_id=sub.thread_id)` |
| пассивный ping | тот же файл `_send_event` ≈552–554 | `metadata["thread_id"] = sub["thread_id"]` → `adapter.send` |
| SoT подписки | CLI `hermes kanban notify-subscribe --thread-id` | колонка `kanban_notify_subs.thread_id` (PK вместе с task/platform/chat) |

Карточка без подписки с нужным `thread_id` = **тишина или чужой топик**, даже если
origin записан в body.

### 1.3 Как сейчас ломается (три слоя)

**A. Скиллы хардкодят Monitoring и при этом опускают `--thread-id`.**

Контракт в `tz-workflow` 2.6.0 и `hermes-feature` 2.9.0 / DKP v0.3.7:

```bash
hermes kanban notify-subscribe <task_id> \
  --platform telegram --chat-id -1004300127777 --chat-type group \
  --delivery-mode notify+wake --notifier-profile default
```

CLI флаг `--thread-id` **есть** (`hermes_cli/kanban_parser.py`, help подтверждён).
В скилле его **нет**. Пустой `thread_id` → forum-send без топика → фактически
General `:1`.

**B. Параллельно кто-то всё же подписывает `:7` с `chat_type=thread`.**

Срез `kanban.db` 26.09 (python3 stdlib, `sqlite3` CLI нет):

| thread_id | chat_type | N |
|---|---|---|
| `''` | `group` | 30 |
| `7` | `group` | 26 |
| `7` | `thread` | 26 |
| `1` | NULL | 1 |

`chat_type='thread'` живых строк: **26** (диагноз 24.09 писал 14 — drift вырос).
Семь задач имеют **две** подписки на одну группу: пустой thread (`group`) **и**
`7/thread` (разный PK: `thread_id=''` vs `'7'`). Это два физических лейна:
General + Monitoring-форк.

**C. Ядро уже умеет origin-на-create — скилл его перебивает.**

`tools/kanban_tools.py` `_maybe_auto_subscribe` / `_resolve_notify_target`
(≈902–975): при `kanban_create` из gateway-сессии пишет подписку из
`HERMES_SESSION_PLATFORM` / `CHAT_ID` / `THREAD_ID` / `CHAT_TYPE`.
`kanban.auto_subscribe_on_create` в `config.yaml` **не задан** → default `True`.

Потом скилл добавляет **вторую** строку на `-1004300127777` без thread или с `:7`.
PK не конфликтует, если `thread_id` разный → оба канала живы.

Корень этой карточки (`t_5241780b`, `t_efbb86ba`): **0 подписок** — create шёл
не из TG-сессии (Cursor/воркер), R5 не отработал. Для политики это ожидаемо:
origin надо фиксировать в ходе **оркестратора в TG**, не воркера Cursor.

### 1.4 Что уже верно в предложении архитектора (верификация)

| Утверждение из корня | Вердикт |
|---|---|
| R5: сменить жёсткий `:7` на origin в `kanban_notify_subs.thread_id` при создании корня | **да** — единственный рычаг без ядра |
| `chat_type` всегда `group` | **да** — иначе снова слот `thread:` (баг duplicate) |
| набор подписок тот же (корень + AC-гейты) | **да** — рычаг R5 не менять, только канал |
| не класть топик только в metadata | **да** — wake его не читает |
| DM-origin → не подписывать, фоллбек тишина | **да** — не подставлять `:7` |
| `:7` остаётся для кронов/ops | **да** — ErrorBus / `deliver` кронов не этот скилл |
| ErrorBus `:11112` отдельно | **да** — никогда кейсовый notify |

Дополнить (дыр в корне не было, но без этого дети уедут не туда):

- Origin резолвится **на корне**. Поздние `GATE:*` часто создаёт воркер/чат
  **без** `HERMES_SESSION_THREAD_ID` origin'а (другой топик, Cursor, dispatcher).
  Для детей канал = **копия `thread_id` с подписки корня**, не текущий env.
- Ядро `_maybe_auto_subscribe` **переиспользуем**, не патчим
  (`kanban_tools.py` / `kanban_db*` вне скоупа). Скилл **выравнивает** явный
  R5-subscribe с origin и снимает stray-подписки (пустой thread, чужой chat).

## 2. Зависимость от `DEV/tg-topic-duplicate` — БЛОКИРУЕТ impl канала

**Да: смена канала до identity-фикса размножит вилки-сессии на каждый origin-топик,
не только `:7`.**

Граф `DEV/tg-topic-duplicate` (`t_ff1191b0`) на срезе 26.09:

| Фаза | id | status |
|---|---|---|
| корень | `t_ff1191b0` | `done` (!) — **не ждать закрытия корня**; смотреть хвост |
| `HF:plan` | `t_59fe8b02` | `done` |
| `REV:plan` | `t_ff6aff38` | **`blocked`** |
| `GATE:plan-approve` … `GATE:done` | `t_05fa708a` … `t_07c4913c` | `todo` |
| ТЗ | `TZ/tg-topic-duplicate/tg-topic-duplicate_TZ.md` v0.1.0 `approved` | код **не** влит |

Identity ещё не в проде: `build_session_key` по-прежнему

```
chat_type_slot = "thread" if thread_id and not source.thread_id else source.chat_type
```

(`gateway/session.py` ≈674). Wake по-прежнему пробрасывает `sub.chat_type`
(≈530–533). `chat_type='thread'` в `kanban_notify_subs`: 26 строк.

Если сейчас подписать Tools `:3` / WorkVault `:5` с `chat_type=thread` (или
оставить env `HERMES_SESSION_CHAT_TYPE=thread` на auto-sub) — получим новые
ключи `telegram:thread:-1004300127777:{3|5|6|8}` рядом с каноническими
`group:…`. Симптом duplicate размажется по всем топикам кейсов.

### Механизм передачи (обязательный стоп-кран)

| Фаза origin-routing | Можно ли | Условие |
|---|---|---|
| `BUG:diagnose` / этот файл | да | сейчас |
| `GATE:diagnose-review` | да | |
| `TZ:patch` / `TZ:finalize` / `REV:tz` | **да, параллельно** duplicate | только текст DKP |
| `GATE:take-into-work` | да | HITL по AC; **не** значит «можно impl» |
| `HF:plan` / `REV:plan` / `GATE:plan-approve` | да | план обязан содержать стоп-кран ниже |
| `HF:backup` / **`HF:impl` / `HF:test`** | **НЕТ** | пока не выполнен минимум identity |

**Минимум identity (рекомендация — ждать `GATE:done` duplicate):**

1. Предпочтительно: карточка `GATE:done` графа `DEV/tg-topic-duplicate` = `done`
   (Саша принял AC-001…005).
2. Допустимый ускоренный порог, если `GATE:done` держится только HITL, а код
   уже на диске: `HF:test` duplicate `done` **и** выполнены П.1–П.3 ТЗ
   TgTopicDuplicate **и** Саша сказал «поднимай» (П.4, рестарт gateway).
   Без рестарта старый процесс продолжает форкать.

Чеклист на входе `HF:impl` origin-routing (воркер **стоп**, если любой пункт ложен):

```
# 1) ключ Telegram без слота thread:
python3 -c "import pathlib,re; t=pathlib.Path('/home/tkachenkoav/hermes-agent/gateway/session.py').read_text();
assert 'Platform.TELEGRAM' in t or True"  # фактическая проверка — юнит duplicate AC-001
# наблюдаемо: build_session_key(TELEGRAM, chat_type='thread', thread_id=N) → ':group:' не ':thread:'

# 2) wake не утекает thread
# kanban_watchers_notifier.py: TELEGRAM + thread_id → SessionSource.chat_type=='group'

# 3) данные
python3 - <<'PY'
import sqlite3
c=sqlite3.connect('file:/home/tkachenkoav/.hermes/kanban.db?mode=ro', uri=True)
n=c.execute("SELECT COUNT(*) FROM kanban_notify_subs WHERE chat_id='-1004300127777' AND chat_type='thread'").fetchone()[0]
assert n==0, n
PY

# 4) нет живой вилки thread:-1004300127777:7 (и вообще telegram:thread: для этой группы)
```

Не начинать impl «под честное слово». Не делать origin-subscribe «уже сейчас
с chat_type=group» в обход duplicate: auto-sub всё равно запишет env
`chat_type=thread`, пока П.2/П.3 duplicate не закрыты.

**Не** ставить `parents=` на чужой граф в ядре канбана (ядро не трогаем).
Стоп-кран — чеклист скилла `hermes-feature` на `HF:impl` + строка в DKP
«реализация R5-origin после identity TgTopicDuplicate».

## 3. Целевой контракт (без правки ядра)

### 3.1 Резолв origin

Идентификатор канала кейса: `(platform=telegram, chat_id=-1004300127777, thread_id=ORIGIN, chat_type=group)`.

```
resolve_origin(kind=root|child, root_id):
  1. Явный override Саши на этом графе («пиши в :N» / «канал = …») → N.
  2. kind=child: notify-list(root_id) → единственная telegram-подписка
     на -1004300127777 с непустым thread_id ∉ {11112}. Нет такой → SILENCE.
  3. kind=root: env HERMES_SESSION_PLATFORM=telegram
     AND HERMES_SESSION_CHAT_ID=-1004300127777
     AND HERMES_SESSION_THREAD_ID непустой
     (пустая строка thread_id = отсутствие origin → не шаг 3, а SILENCE)
     AND thread_id ≠ 11112
     AND chat_type ∉ {dm, direct, private}
     AND chat_id ≠ 400307920
     → thread_id (канон каталога 1/3/5/6/7/8 — предпочтителен, но origin
       побеждает, если это реальный топик той же группы, кроме Errors).
  4. DM / неизвестно / CLI / Cursor без TG-env / Errors :11112 → SILENCE.
  5. SILENCE: notify-subscribe НЕ вызывать; :7 НЕ подставлять.
```

`HERMES_SESSION_CHAT_TYPE=thread` на корне **нормализовать в `group`** в команде
подписки (колонка), не копировать в sub. После identity-фикса это гигиена;
до него — всё равно нельзя impl.

### 3.2 Команда подписки (новый фиксированный контракт)

```bash
hermes kanban notify-subscribe <task_id> \
  --platform telegram --chat-id -1004300127777 --thread-id <ORIGIN> \
  --chat-type group \
  --delivery-mode notify+wake --notifier-profile default
```

`<ORIGIN>` обязателен. Без `--thread-id` команда **запрещена** (это и есть баг A).

Набор R5 **не менять**:

- подписывать: корень `DEV/<slug>` или `IDEA/<slug>`; `GATE:take-into-work`;
  `GATE:done`; `GATE:go`; `GATE:block-accept`; `IDEA:analyze`;
- не подписывать: `TZ:*` / `HF:*` / `REV:*` / `BUG:diagnose` / `ORCH:*` /
  `RS:*` / `GATE:plan-approve` / `GATE:diagnose-review`.

После subscribe на целевой `(chat, thread)` — снять stray той же задачи:

```bash
hermes kanban notify-unsubscribe <task_id> --platform telegram \
  --chat-id -1004300127777 --thread-id ''     # пустой thread → General
# плюс любая другая telegram-подписка с thread_id ≠ ORIGIN
```

Не снимать подписку на ORIGIN. Не подписывать DM «на всякий случай».

### 3.3 Два канала экосистемы (не смешивать)

| Канал | thread | Кто пишет | Кто не пишет |
|---|---|---|---|
| **Кейс / граф** | origin | R5 `notify-subscribe` | кроны, ErrorBus |
| **Ops / мониторинг кронов** | Monitoring `:7` | `jobs.json` `deliver`, штатный cron-пинг | кейсовый диалог пайплайна |
| **Техника ошибок** | Errors `:11112` | ErrorBus `report_error.sh` | kanban notify, AC-список, AC-отчёт |

AC-список (`GATE:take-into-work`) и AC-отчёт (`GATE:done`) — **в диалог Саши =
origin-топик**, не Monitoring (если origin не был `:7`). Формулировку DKP
«не Monitoring :7» заменить на «не ops-канал; в origin». Дубль в `:7`
по-прежнему запрещён, если origin другой.

Явное указание Саши переопределить канал графа — сохраняется.

## 4. Шаги реализации П.1…П.N

Ниже — очередь **после** `GATE:take-into-work`. П.0 — прекондиция.
Исполнитель не пересобирает алгоритм §3.

### П.0 — стоп-кран identity (HF:impl, механическое)

**Что:** чеклист §2 на входе `HF:impl`.  
**Куда:** `hermes-feature/SKILL.md` (Блок 2 / канбан-шаг origin-routing — одна
строка «если меняешь R5-канал: сначала identity duplicate»). В этом графе —
первый шаг `HF:impl`.  
**Как проверить:** все 4 пункта чеклиста истинны. Иначе `kanban_block(kind=dependency, reason="wait DEV/tg-topic-duplicate identity + поднимай")`, код скиллов не писать.

**Автономия:** механическое. Ложный green → СТОП, не «почти готово».

### П.1 — `TZ:patch` DKP (семантика, отдельная фаза, до HF:impl)

**Файл:** `TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md`  
**Bump:** `0.3.7` → `0.3.8` (уже на диске).  
**Инвентарь:** `TZ:finalize`, не эта фаза.  
**На диске на этот гейт:** v0.3.8 уже `approved` (см. `diagnose_meta` / §0 item-0). После ратификации — сверить канал с §3; **не** второй rewrite п.15/R5/snippet. Единственная дельта — **П.1δ** ниже.

Переписать / перекрыть (не оставлять двойной канон «только :7» как норму):

| Место (ориентир v0.3.7) | Было | Стало |
|---|---|---|
| «Решения Саши» п.15 | репорты только Monitoring `:7` | п.15 **перекрыт 26.09**: кейс → origin; `:7` = ops/cron |
| «Уведомления графа» / фиксированный контракт | snippet без `--thread-id`, текст Monitoring `:7` | snippet §3.2 с `--thread-id <ORIGIN>` |
| R5 «Канал по умолчанию — Monitoring :7» | хардкод | канал = origin; набор карточек тот же |
| Шаг реализации 15 / v0.3.0 т.3 | канал → `:7` | канал → origin; т.3 24.09 перекрыта |
| Критерии успеха «уведомления в Monitoring :7» | хардкод | уведомления в origin; не DM; не `:11112` |
| AC-список / AC-отчёт «не Monitoring :7» | негатив | позитив: диалог = origin |
| Preflight/GATE:done «опубликовать в диалог (не :7)» | то же | диалог = origin |
| Риски уведомителя | без origin | + риск: impl до identity duplicate |

Добавить явное решение 26.09 (как v0.3.2 перекрыл one-pass): таблица
«Старое → новое» для канала.

Не трогать: ядро, `TERMINAL_KINDS`, набор R5-карточек, HITL-точки AC,
ErrorBus, TelegramGroupTopics (каталог 7 топиков), `DialogBacklogToKanban`
(DEV-граф не меняет; IDEA наследует тот же R5 из `tz-workflow`).

**Проверка:** `rg -n "Monitoring :7" DevKanbanPipeline_TZ.md` — остаётся только
как ops-канал / история changelog / «не хардкодить». Норматив subscribe —
с `--thread-id <ORIGIN>`.

**Автономия:** **СТОП / семантическое.** Текст канона пишет архитектор на
`TZ:patch`, не исполнитель «заодно» в `HF:impl`.

### П.1δ — addendum `resolve_origin` шаг 3 (TZ:finalize, не rewrite)

Единственная разрешённая правка уже лежащего master v0.3.8. Не трогать п.15,
R5, snippet subscribe, критерии успеха, таблицу «Старое → новое».

**Куда:** алгоритм `resolve_origin` / kind=root (тот же блок, что §3.1 этого
плана), сразу после условия «`HERMES_SESSION_THREAD_ID` непустой».

**Что вставить (одна строка, дословно):**

```
(пустая строка thread_id = отсутствие origin → не шаг 3, а SILENCE)
```

**YAML:** bump `0.3.8` → `0.3.9` **только** из-за этой строки (инвентарь на
`TZ:finalize`). Остальной текст v0.3.8 не переписывать — только addendum.

**Проверка:** `rg -n "пустая строка thread_id" DevKanbanPipeline_TZ.md` — ≥1;
`rg` по контракту `--thread-id <ORIGIN>` без регрессии v0.3.8.

**Автономия:** семантическое, но объём фиксирован: одна строка + bump patch.
Шире — СТОП (это уже rewrite).

### П.2 — скилл `tz-workflow` (механическое после утверждённого ТЗ)

**Файл:** `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md` (канон; bump 2.6.0 → 2.7.0)  
**Секция:** «Подписка графа на уведомления (notify-subscribe)» ≈172–189.

Заменить snippet на §3.2. Вставить алгоритм `resolve_origin` §3.1
(корень = env; дети/гейты = копия с корня). Запрет subscribe без `--thread-id`.
DM/SILENCE. После батча IDEA/TZ-гейтов — тот же ORIGIN, не `:7`.

Порядок хода `TZ:finalize` → AC-список: публиковать в origin, не `:7`.

**Проверка:**

```
rg -n "notify-subscribe" ~/hermes-workspace/skills/devops/tz-workflow/SKILL.md
# есть --thread-id <ORIGIN> или эквивалент
# нет snippet без --thread-id на -1004300127777
rg -n "thread_id=7|--thread-id 7" …/tz-workflow/SKILL.md   # 0 в контракте subscribe
```

**Автономия:** механическое **если** П.1 уже на диске. Расхождение с ТЗ → СТОП.

### П.3 — скилл `hermes-feature` (механическое)

**Файл:** `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md` (bump 2.9.0 → 2.10.0)  
**Секции:** notify-subscribe ≈84–101; Блок 6В (подписать **корень**, не diagnose);
GATE:done шаг «опубликовать отчёт в диалог» ≈190 — диалог = origin.

Тот же алгоритм §3.1–3.2. На хвосте после `GATE:take-into-work` (создание
`GATE:done` и др.) — ORIGIN **с корня**, не из сессии воркера.

П.0 стоп-кран — в чек-лист фаз.

**Проверка:** зеркало П.2 + строка стоп-крана duplicate.  
`rg "Подписать ОБЕИХ|notify-subscribe ОБЕИХ"` — не вернуть подписку
`BUG:diagnose`.

**Автономия:** механическое после П.1.

### П.4 — stray-unsubscribe и auto-sub (механическое, скилл, не ядро)

Не патчить `kanban_tools.py`. После каждого явного R5-subscribe:

1. `notify-list <task_id>`;
2. оставить одну telegram-строку `(chat_id=-1004300127777, thread_id=ORIGIN, chat_type=group, mode=notify+wake)`;
3. `notify-unsubscribe` все прочие telegram-строки этой задачи (пустой thread,
   другой thread, DM `400307920`).

**Проверка (смоук, не live-кейсы Саши):** throwaway-корень `DEV/_smoke-origin/…`
создать **напрямую** `kanban_create` из топика Tools `:3` (после identity +
«поднимай») — **без** фразы-триггера («разработай» / «почини» / «напиши ТЗ»)
и **без** `BRF:intake`, чтобы не запускать побочный DEV-граф по GLOSSARY
инвариант 9. Не полный цикл BRF→TZ-WRITE — только техническая карточка +
нужные R5-дети смоука. Далее `notify-list` корня и `GATE:take-into-work`
показывают `thread_id=3`, `chat_type=group`, ровно 1 telegram-sub на задачу;
в `:7` пинга нет; в `:3` — terminal block/complete. Карточки смоука → archive.

DM-смоук: тот же прямой `kanban_create` из личного чата → 0 telegram-sub, тишина.

**Автономия:** механическое. Снимать **чужие живые** графы (не смоук) — **СТОП**.

### П.5 — не мигрировать исторические подписки (граница)

Существующие 30+26+26 строк `:7` / пустой thread **не** массово UPDATE на
«угаданный origin» (origin неизвестен). Identity-duplicate чистит только
`chat_type=thread` → `group` на `:7` (их П.3). Этот граф — **только новые**
подписки после вшивки скилла.

**Автономия:** запрет. Массовый rewrite — отдельная команда Саши.

### П.6 — `HF:docs-handoff` + `ORCH:shared-state`

Скиллы: bump version в frontmatter (П.2–П.3).  
`restore-all-skills.sh` — только `ORCH:shared-state`, не исполнитель.  
Манифест: новой сущности нет; `tools.dev_kanban_pipeline` purpose при желании
одна фраза про origin — **опционально**, не блокер AC.  
GLOSSARY: **не** трогать (новый термин фазы не нужен).  
`DialogBacklogToKanban_TZ.md`: не обязателен; IDEA идёт через `tz-workflow`.

**Автономия:** restore — оркестратор. Писать манифест исполнителю — запрет.

### П.7 — тесты / наблюдаемость (нет нового Python)

Кода ядра нет → pytest ядра не добавлять (это и есть «ядро не трогать»).
Наблюдаемые проверки = CLI + SQL read-only + смоук П.4.

Нельзя: юнит на `kanban_db_notify.py`, правка `test_kanban_notify.py`.

## 5. Границы автономии (сводка)

| Класс | Примеры | Поведение |
|---|---|---|
| **Механическое — делай** | snippet `--thread-id <ORIGIN> --chat-type group`; копия thread с корня; unsubscribe пустого thread; bump version скилла; чеклист П.0 | без вопроса |
| **Семантическое — СТОП** | фоллбек `:7` вместо тишины; подписать DM; слать кейс в `:11112`; массовый rewrite старых sub; impl до identity; выкинуть `REV:tz`; LIGHT-хвост; патч `kanban_db*` / `kanban_tools.py` / `session.py`; рестарт gateway | стоп + доклад |
| **Архитектурное — СТОП** | менять набор R5-карточек; фильтр `TERMINAL_KINDS`; новый скилл; `config.yaml` `auto_subscribe_on_create`; UNION allowlist | стоп |

## 6. Что НЕ трогать

- `hermes_cli/kanban_db.py`, `kanban_db_notify.py`, список `TERMINAL_KINDS`
- `tools/kanban_tools.py` `_maybe_auto_subscribe` (reuse, не патч)
- `gateway/session.py` / `kanban_watchers_notifier.py` — это граф
  `DEV/tg-topic-duplicate`, не этот
- `config.yaml`, `.env`, `jobs.json`, `entities.json`, EcosystemManifest
  (кроме опциональной фразы на ORCH)
- `GLOSSARY.md`
- ErrorBus (`events.db`, `report_error.sh`, `:11112`)
- каталог 7 топиков TelegramGroupTopics / `tutu-telegram-delivery`
- кроны; gateway restart (только «поднимай» на графе duplicate)
- `kanban_create` / `kanban_complete` / `kanban_block` из этой диагностики
  (уже соблюдено)

## 7. Критерии готовности (наблюдаемые)

**AC-001 — контракт скилла.** В `tz-workflow` и `hermes-feature` команда
`notify-subscribe` содержит `--thread-id` (плейсхолдер ORIGIN) и
`--chat-type group`. Snippet без `--thread-id` на группу — 0 попаданий.

**AC-002 — нет хардкода `:7` в subscribe.** В тех же секциях нет
`--thread-id 7` / «всегда Monitoring :7» как канала кейса. `:7` упоминается
только как ops/cron или «если origin сам `:7`».

**AC-003 — дети копируют корень.** Смоук: корень создан из Tools `:3`;
позже `GATE:take-into-work` / `GATE:done` имеют ту же `thread_id=3`,
даже если воркер сидел в другом чате.

**AC-004 — одна подписка на задачу.** Смоук-карточки: ровно одна telegram-строка
на R5-задачу; нет пары `''` + `7`.

**AC-005 — DM-тишина.** Create из DM `400307920` → 0 notify-sub, нет пинга в `:7`.

**AC-006 — Errors не кейс.** Ни одна новая R5-подписка не имеет `thread_id=11112`.

**AC-007 — ops `:7` жив.** Крон/`deliver` в Monitoring не перенастраивались
этим графом (`jobs.json` diff пуст).

**AC-008 — identity сначала.** `HF:impl` origin-routing начат только после
чеклиста П.0 (лучше `GATE:done` duplicate). Наблюдаемый маркер: отчёт /
`kanban_comment` карточки `HF:impl` содержит блок `identity-checklist:` —
copy-paste **вывода всех 4 пунктов** чек-листа §2 («Механизм передачи»),
не пересказ. Проверка: `rg -n "^identity-checklist:"` по comment/`result`
`HF:impl` + в блоке есть факты п.1–п.4 (ключ без слота `thread:`; wake
`chat_type=group`; SQL `chat_type='thread'` = 0; нет живой вилки
`telegram:thread:-1004300127777:*`). Иначе `GATE:done` запрещён:
`kanban_block(reason="review-required: AC-008 identity-checklist")`.

**AC-009 — wake в origin.** После «поднимай» duplicate: terminal `blocked` корня
смоука будит сессию `group:-1004300127777:<ORIGIN>`; сообщение в том топике;
копии в General `:1` и Monitoring `:7` нет (если ORIGIN другой).

**AC-010 — DKP канон.** v0.3.8: п.15/т.3 перекрыты; раздел «Уведомления графа»
и R5 описывают origin; критерии успеха не требуют Monitoring для кейса.
После `TZ:finalize`: в `resolve_origin` шаг 3 есть строка «пустая строка
thread_id = отсутствие origin → SILENCE» (П.1δ); YAML `0.3.9` если addendum
вшит (иначе регрессия item-0).

## 8. IAC LIGHT vs полный план

LIGHT IAC (1–3 строки) **не применяется**. Полный `HF:plan` после `TZ:finalize`:

```
IAC-01 | TZ:patch→TZ:finalize | DevKanbanPipeline_TZ.md | rg --thread-id ORIGIN + rg «пустая строка thread_id» (П.1δ) | — | AC-010
IAC-02 | HF:impl             | tz-workflow + hermes-feature SKILL.md; comment HF:impl | rg AC-001/002 + маркер identity-checklist: | IAC-01, П.0 | AC-001,002,008
IAC-03 | HF:test             | kanban.db + notify-list смоука | SQL/CLI AC-003…006,009 | IAC-02, П.0 | AC-003…007,009
```

`covers` — итоговые AC этого пакета (выдаст `TZ:finalize` в диалог origin).

## 9. Открытые развилки impl (не блокеры диагноза)

Снимает Саша; иначе исполнитель идёт по рекомендации.

**OQ-1.** Ждать `GATE:done` duplicate или ускоренный порог (`HF:test` + П.1–П.3 +
«поднимай»)? **Рекомендация: `GATE:done`.** Ускорение — только если Саша явно
скажет не ждать HITL done.

**OQ-2.** Origin вне каталога 7 (например `:6556`)? **Рекомендация: разрешить**,
кроме `:11112`. Каталог — предпочтение, не фильтр.

**OQ-3.** Чистить исторические dual-sub (7 задач `''`+`7/thread`)? **Не в этом
графе.** Duplicate чистит `thread`→`group` на `:7`; пустой thread — отдельная
команда или само изживёт, когда скилл снимет stray на **новых** задачах.

Корень `t_ff1191b0` уже `done` при живом хвосте — **не** трактовать как
«duplicate закрыт». Смотреть `REV:plan`/`HF:impl`/`GATE:done`.
