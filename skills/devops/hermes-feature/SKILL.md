---
name: hermes-feature
description: "Use when: полный цикл разработки фич/инструментов Hermes (ТЗ → код → тесты → документация) + диагностика багов + процедура починки питфоллов (pitfall-remediation-workflow). Triggers: разработай, новый инструмент, сделай, напиши код, реализуй, реализация, почини, починка, баг, ошибка, не работает, упало, разберись, исследуй, проанализируй, доработка, дорабатываем, MoveFrom*, обновить гермес, обновление гермес, hermes update, апгрейд, merge upstream, upstream merge, обновление версии."
version: 2.13.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, cursor, development, feature, process, debug, research]
    related_skills: [tz-workflow, hermes-agent-skill-authoring, hermes-ops]
---

# hermes-feature

# Dual-path (DevWorkflow W2)

Пока `tools.dev_workflow.orchestration.mode` ≠ `workflow-only`:
- не начинай новый поезд через канбан/hermes-feature/tz-workflow для slug ∈ `orchestration.pilot_slugs`;
- если slug в списке и нет живого kanban-running на нём — стоп, отдай управление скиллу `dev-workflow`;
- иначе работай по этому скиллу как раньше;
- два поезда на одном slug запрещены.

Конфиг: `EcosystemConfig.yaml` → `tools.dev_workflow.orchestration`.
## Термины
Перед первым `PREFIX:фаза` читать `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`.
Имена фаз/ролей/скиллов только из канона. Голые TZ/HF/ORCH/DEV без двоеточия запрещены.

## Overview

Единый процесс работы над фичами Hermes и USERTOOLS: от ТЗ до кода, тестов, документации, диагностики и отката. Все блоки выполняются через Cursor CLI (`agent -p`). Архитектор (cursor-grok-4.6-high через Cursor) планирует, исполнитель (composer-2.5 через Cursor) пишет и тестирует.

**ЖЁСТКОЕ ПРАВИЛО:** Архитектор default (Сирень) НЕ пишет ТЗ, планы, анализ самостоятельно в чате. Все задачи архитектора — ТОЛЬКО через Cursor CLI (`agent -p`). Текущий агент default (Сирень) координирует: вызывает Cursor CLI, передаёт контекст, принимает результат. Полный документ (план / ТЗ / appendix / research / файл) в `agent -p` — без обрезки: полный `cat`, либо путь + «прочитай сам», либо явно «часть 1/N» (канон: pitfall cursor-cli). Никаких попыток «написать план самому» без Cursor CLI. ИСКЛЮЧЕНИЕ из „жёсткого правила": диагностика и план починки бага — НЕ напрямую, а через канбан-карточку BUG:diagnose (см. Блок 6В) ДО любого agent -p / cronjob(repeat=1) / делегирования. Прямой agent -p на диагностику/план/реализацию по багу-триггеру без существующей карточки BUG:diagnose = нарушение инварианта 8.

## When to Use

- «разработай», «новый инструмент», «напиши код», «реализуй» — Блоки 0–4
- «ошибка», «баг», «не работает», «упало», «разберись», «починить» — Блок 7 (диагностика)
- «проанализируй», «исследуй», «найди», «посчитай», «сравни» — Блок 8 (исследование)
- «обновить гермес», «merge upstream» — Блок 1 + `references/hermes-upgrade-pattern.md`
- Задача с 3+ изменениями конфига/скиллов/инструментов — Блок 6А (QA)

Не для: правок стиля общения (см. `hermes-memory-hygiene`), простой рутины без ТЗ и вариантов.

### Классификатор маршрута (баг vs прямой ответ)

| Триггерные слова | Маршрут (ОБЯЗАТЕЛЬНО) |
|---|---|
| «баг», «ошибка», «не работает», «упало», «почини», «починка», «разберись», «проанализируй ошибки», «cron run failed», «отдай на разбор/план починки», «fix», «root cause» | канбан-граф BUGFIX = BUG:diagnose → GATE:diagnose-review → TZ-WRITE(patch/light) → PLAN-IMPL-TAIL(-LIGHT). ПЕРВЫЙ tool-шаг — `kanban_create` корня `DEV/<slug>` И карточки BUG:diagnose в одном create-батче, ДО любого agent -p / cronjob / delegate. Ретро-корень запрещён (инвариант 9). Классификация LIGHT — после GATE:diagnose-review (≤3 файла вне shared). После `TZ:finalize` (багфикс-ТЗ) `GATE:take-into-work` **auto-pass** (`auto-pass: ac-shown`), payload=AC; `GATE:diagnose-review` **auto** по артефакту `_fix_plan_*.md`/непустому body (императив 28.09, старт→финиш) |
| «спроси», «проверь», «вычисли», «найди данные», «найди в архиве», «сколько», «покажи» | прямой ответ (без кода/процесса; нет карточки) |
| «одношаговый ответ», RESEARCH-триггеры («проанализируй», «исследуй» без починки) | прямой ответ / RS-граф (по DPK-исключениям) |

Правило сверху: «Работа с кодом/процессом (любое изменение) по баг-триггеру — ТОЛЬКО через канбан-граф. Прямой ответ — только когда НЕТ кода/процесса. Сомнение — всегда в сторону карточки BUG:diagnose.»

**Связь с tz-workflow:** после `TZ:finalize` AC показ в origin → `GATE:take-into-work` auto-pass, поезд идёт сам — этот скилл для реализации, без фразы «берём в работу».

---

## Канбан-шаг

> DevKanbanPipeline (`TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md`). Все карточки `assignee=default`. Исполнители **не** пишут в `EcosystemManifest.json` / `entities.json` / `.env` / `jobs.json` — только `ORCH:shared-state`.

### Вход

- Любой HF `agent -p` без корня `DEV/<slug>` → **стоп** + оркестратор. Исключения DPK: `BRF:*` в TG; одношаговый ответ; RESEARCH.
- Вход в HF-ветку: корень `DEV/<slug>` существует **и** `GATE:take-into-work` **done/auto-pass** (`auto-pass: ac-shown`) — не фраза Саши (императив 28.09). Постановщик завёл полный граф одним батчем, гейт авто-прошёлся после `TZ:finalize`.
- **Все задачи по умолчанию ложатся в план** (канбан-граф `DEV/<slug>`) после триггера «разработай/доработай/почини» и далее проводятся по канону, без дополнительной команды Саши (требование 1).
- **Slug-guard:** перед `kanban_create` корня `DEV/<slug>` (в т.ч. багфикс-батча) — проверка активного графа по слагу (`todo|ready|running|blocked`, не `done`/`archived`); дубли запрещены (кейс 1, прецедент pfs-notify-link-unprocessed). При совпадении — reuse существующего графа или `kanban_block` до разрешения.
- `GATE:plan-approve` / `HF:backup` / `HF:impl`: если `HF:plan` не `done` → **стоп** (GLOSSARY инвариант 6). Не skip плана в one-pass.
- Off-board: **предусловие** — сначала вывести граф из диспатча (comment корня `dispatch-paused: off-board`, снять/не диспатчить remaining), затем retro-create + comment `done off-board, session ids`. Без `dispatch-paused` прямой `agent -p` на живой граф запрещён (инвариант 8).
- **Снятие устаревшего графа (легаси/заменённый/перенесённый в другой канал):** когда разработку переносят из канбан-графа в прямой диалог/офф-борд и граф больше не целевой — НЕ оставлять его не-done карточки висеть. Крон «статус канбана» (каждые 15 мин в рабочее время → Monitoring) будет каждый тик репортить `blocked needs_input` как «ждёт Саши», хотя это легаси-дубль уже сделанной работы. Снять весь не-done хвост одной командой `hermes kanban archive <ids>`, оставив done-карточки историей, + comment на корне с причиной. Иначе ложный блокер спамит до снятия.
- **Запрет `model` на create:** `HF:plan` / `HF:impl` / `HF:test` / `HF:docs-handoff` / `HF:backup` / `BUG:diagnose` / `REV:plan` — `kanban_create` **без** `--model` / `model=`. Анти-пример: `model=cursor-grok-4.6-high` или `composer-2.5` на карточке → Hermes-воркер на tutu, HTTP 400, 0 tool-calls, `protocol_violation` (`t_2c8ee3b2`). Роли grok/composer — только внутри `agent -p --model …`.

Граф HF-фаз — развёртка `PLAN-IMPL-TAIL` + `HF-TAIL` (GLOSSARY §5.1; сборка кейсов — §2):

```
GATE:take-into-work  (уже снят)
├─ HF:compress          parents=[GATE:take-into-work]   # опц., skip на stub/BUGFIX/…
├─ HF:plan              parents=[HF:compress]
├─ REV:plan             parents=[HF:plan]               # по умолчанию; искл. лёгкие BUGFIX/SKILL-CHANGE ≤3 файла
├─ GATE:plan-approve    parents=[REV:plan|HF:plan]
├─ HF:backup            parents=[GATE:plan-approve]
├─ HF:impl              parents=[HF:backup]
├─ HF:test              parents=[HF:impl]
├─ HF:docs-handoff      parents=[HF:test]
├─ ORCH:shared-state    parents=[HF:docs-handoff]
└─ GATE:done            parents=[ORCH:shared-state]
```

Граф выше — **полный граф кейса, создан одним батчем после брифа** (tz-workflow «Вход триггера»): `GATE:take-into-work` + `PLAN-IMPL-TAIL` + `HF-TAIL` уже в графе с parents и ключами `devpipe:<slug>:<phase>`. **Unfold хвоста после гейта НЕТ** (дыра: второй ход → `children=[]`, фазы complete без детей). В **корневом** one-pass (корень сам делает работу) дочерний хвост **не создавать** вообще — см. «One-pass не плодит хвост».

Skills: HF-* / GATE после take-into-work — `hermes-feature`, `cursor-cli`, `cursor-task-context`. ORCH:shared-state — только `hermes-feature`.

#### Подписка графа на уведомления (notify-subscribe)

Сразу после `kanban_create` (в том же ходе) подписать набор **R5** (наследования по `parents` **нет** — каждая карточка явно). Канал = **origin-топик инициатора** (диалог/топик, откуда пришёл запрос; не ops-канал Monitoring `:7`, не Errors `:11112`). `--thread-id <ORIGIN>` обязателен. Отдельное явное указание Саши («пиши в :N» / «канал = …») переопределяет канал подписки конкретного графа.

```bash
hermes kanban notify-subscribe <task_id> \
  --platform telegram --chat-id -1004300127777 --thread-id <ORIGIN> \
  --chat-type group \
  --delivery-mode notify+wake --notifier-profile default
```

Команда **без** `--thread-id` **запрещена** (0 блоков суб без `--thread-id` на `-1004300127777`).

Уведомитель шлёт в TG **только ключевые терминальные события** (по `TERMINAL_KINDS`: `completed`/`GATE:done`, `blocked`, `gave_up`, `crashed`, `timed_out`) — не каждую фазу графа (шум). Ядро канбана **не трогать**: ни `kanban_db.py`, ни `kanban_db_notify.py`, ни список `TERMINAL_KINDS`.

**Рабочий канал wake/notify = колонка `kanban_notify_subs.thread_id`, не body/metadata карточки. Второе поле «канал origin» в metadata **не** заводить.**

- **Набор R5:** корень `DEV/<slug>` + `GATE:take-into-work` / `GATE:done` + `GATE:go` / `GATE:block-accept` / `IDEA:analyze` → `notify+wake`. **Набор R5 не расширять**; leftover «подписать все фазы / багфикс обе карточки» запрещён.
- **Не подписывать:** `TZ:*` / `HF:*` / `REV:*` / `BUG:diagnose` / `ORCH:*` / `RS:*` / `GATE:plan-approve` / `GATE:diagnose-review`.
- Багфикс-батч (`DEV/<slug>` + `BUG:diagnose`, Блок 6В): подписать **корень** `DEV/<slug>` (не `BUG:diagnose`, не «обе карточки»).
- Ручной feed `IDEA/<slug>` + `IDEA:analyze`: тот же `resolve_origin` + R5-subscribe/unsubscribe; пассивный inbox (`IDEA/<slug>` без analyze) — подписать **только корень** `IDEA/<slug>`.

##### resolve_origin

Канал подписки каждой R5-карточки определяется алгоритмом `resolve_origin(kind=root|child, root_id)` (дословно из DKP v0.3.9):

```
resolve_origin(kind=root|child, root_id):
  1. Явный override Саши («пиши в :N» / «канал = …») → N.
  2. kind=child: notify-list(root_id) → единственная telegram-подписка
     на -1004300127777 с непустым thread_id ∉ {11112}. Нет такой → SILENCE.
  3. kind=root: env HERMES_SESSION_PLATFORM=telegram
     AND HERMES_SESSION_CHAT_ID=-1004300127777
     AND HERMES_SESSION_THREAD_ID непустой
     (пустая строка thread_id = отсутствие origin → не шаг 3, а SILENCE)
     AND thread_id ≠ 11112
     AND chat_type ∉ {dm, direct, private}
     AND chat_id ≠ 400307920
     → thread_id.
  4. DM / неизвестно / CLI / Cursor без TG-env / Errors :11112 → SILENCE.
  5. SILENCE: notify-subscribe НЕ вызывать; :7 НЕ подставлять.
```

`HERMES_SESSION_CHAT_TYPE=thread` на корне **нормализовать в `group`** в команде (колонка `chat_type`), не копировать `thread` в sub.

Для детей хвоста после `GATE:take-into-work` (`GATE:done`, `GATE:go`, `GATE:block-accept`): `kind=child`, origin = **копия** `thread_id` с корня (не env воркера). `GATE:plan-approve` **не** подписывать. Исторических dual-sub (`''` + `7/thread`) **не** массово UPDATE.

##### SILENCE-unsubscribe

После каждого create R5-карточки:

1. `hermes kanban notify-list <task_id>` (лучше `--json`).
2. SILENCE → `notify-unsubscribe` **все** telegram-подписки этой задачи (в т.ч. auto-sub DM `400307920` и `--thread-id ''`). Пинга в `:7` нет.
3. Origin есть → оставить **ровно одну** строку `(chat_id=-1004300127777, thread_id=ORIGIN, chat_type=group, mode=notify+wake)`; снять прочие (пустой thread, другой thread, DM, `:11112`).
4. Не снимать ORIGIN. Не подписывать DM «на всякий случай». Не слать кейс в `:11112`. Запрет массового UPDATE исторических dual-sub.

##### Wake: terminal-blocked будит ORIGIN

terminal `blocked` корня будит `group:-1004300127777:<ORIGIN>`; копий в General `:1` / Monitoring `:7` нет, если ORIGIN другой. Сам рестарт gateway — **не** этот скилл (только по фразе Саши «поднимай», AC-010).

### Блок 6В (багфикс)

При триггере «почини» — **до** TZ-ветки (кейс BUGFIX, GLOSSARY §2):

```none
корень DEV/<slug> + BUG:diagnose   # в ОДНОМ kanban_create-батче (инвариант 9), до agent -p
# сразу после батча — notify-subscribe R5 (контракт «Подписка графа на уведомления» выше)
GATE:diagnose-review  parents=[BUG:diagnose]   # auto по артефакту _fix_plan_*.md / непустому body
→ далее TZ-WRITE(patch|light) → GATE:take-into-work (auto-pass: ac-shown) → PLAN-IMPL-TAIL | PLAN-IMPL-TAIL-LIGHT
```

`BUG:diagnose` — read-only, план П.1…П.N → `_fix_plan_YYYYMMDD.md`. Диагноз → `BUG:diagnose`; реализация → `HF:impl`. **`HF:fix` запрещён** (GLOSSARY §7). Инвариант: даже с известным root cause — нет перехода в hermes-feature без ТЗ-файла. `GATE:diagnose-review` — **auto** (доработка B): воркер гейта complete сам, когда `BUG:diagnose` done и на диске есть `_fix_plan_*.md` **или** непустой body; классификация LIGHT — в том же ходе. `GATE:plan-approve` — always auto; `GATE:take-into-work` / `GATE:done` — **always auto**. Баг-триггер всегда начинает с карточки BUG:diagnose.

**Корень `DEV/<slug>` создаётся СРАЗУ, в том же create-батче, что и `BUG:diagnose`** (не ретро, инвариант 9). Ретро-корень = нарушение (прецедент pfs-promote-bugfix 22.09: preflight GATE:done красный). Первый tool-шаг при баг-триггере — `kanban_create` корня `DEV/<slug>` **И** DX в одном батче, **до** любого agent -p / cronjob(repeat=1) / delegate / cronjob-аутсорсинга диагностики.

**Багфикс-батч создаёт ПОЛНЫЙ хвост сразу, не корень+DX на потом (прецедент 11.10: digest/pfs-notify стоят на DX done).** Развёл только
`корень DEV/<slug>` + `BUG:diagnose` (по букве инварианта 9) — когда DX выполнилась, граф встал: `GATE:diagnose-review` и LIGHT/полный хвост
ещё не существовали, диспетчеру нечего промоутить после DX done, пришлось добирать гейт и хвост вторым ходом. Правило: в том же оркестраторском
ходе, что корень+DX, создавать и `GATE:diagnose-review` (parents=[DX]) и (после классификации) LIGHT-хвост `TZ:patch→TZ:finalize→GATE:take-into-work→HF:impl→HF:test→HF:docs-handoff→GATE:done` — **целиком**, чтобы поезд от корня шёл до GATE:done без добивания. DX при этом выполняется первой (родитель корня done → ready), гейт и хвост ждут своей очереди по parents.

**Классификация LIGHT (кейс BUGFIX-LIGHT, GLOSSARY §2/§5.2)** — **после** `GATE:diagnose-review`, а не на холодном старте. Критерий: ≤3 файла кода+тесты, вне shared-модулей, без новых сущностей/cron/.env/манифеста. Тогда:
- корень `DEV/<slug>` + `BUG:diagnose` → `GATE:diagnose-review` → `TZ:patch` → `TZ:finalize` → `GATE:take-into-work` → `HF:impl` → `HF:test` → `HF:docs-handoff` → `GATE:done` (preflight `--case BUGFIX-LIGHT`);
- skip: `HF:plan`, `GATE:plan-approve`, `HF:backup`, `REV:tz`/`REV:plan`, `HF:compress`, `ORCH:shared-state`;
- план = `_fix_plan_*.md` **или** непустой body `BUG:diagnose` (утверждён уже на diagnose-review);
- не генерировать пустые `auto-pass`-флаги (фальшивый audit).

**Auto-гейт (DKP 0.4.0, императив 28.09):** после `TZ:finalize` `GATE:take-into-work` **auto-pass** (`auto-pass: ac-shown`), payload=AC; `GATE:diagnose-review` — **auto** по `_fix_plan_*.md` (доработка B). Leftover «never auto» на `take-into-work`/`done` — устранён.

**G5 (AC-H03/H09/H10):** воркер HF/BUG **не** `kanban_create` кейсовый граф и **не** skip фаз. `kanban_create` корня+DX / LIGHT-хвоста / смена `--case` — **только оркестратор (Сирень) на триггере в чате**, ДО любой карточки архитектора. Классификация BUGFIX→BUGFIX-LIGHT — **после** `GATE:diagnose-review` оркестратором (перепись хвоста / `--case`); архитектор в `_fix_plan` может написать оценку числа файлов, `kanban_create` LIGHT-хвоста ему **запрещён**.

**Перед любым `agent -p` по инструменту на `BUG:diagnose` (и далее по багфикс-ветке):** обязательный `emit-prompt` — exit 0, иначе **СТОП**, `agent -p` не вызывать. Легальный вызов только от файла `--out` (промпт: `$(cat /tmp/task.md)`):

- `python3 /home/tkachenkoav/WorkVault/Registries/pipeline_context_bundle.py emit-prompt --card $HERMES_KANBAN_TASK --tool <Name> --task-file <план> --out /tmp/task.md`
- exit 0 → **скопировать в `kanban_comment` ОБА блока из `/tmp/task.md`: `context-bundle:` (абс-пути digest/glossary/master TZ) И `context-used:`** (G2/AC-H06), затем `agent -p "$(cat /tmp/task.md)" -f --model <МОДЕЛЬ> --workspace <ABS_DIR> --output-format json`
- exit ≠ 0 → СТОП
- перед `kanban_complete` HF/BUG/REV: `pipeline_context_bundle.py check --card $HERMES_KANBAN_TASK` — exit 0 обязателен (G2)

**Питфолл `check`:** `check --card` читает **body+comments** карточки и ищет маркер `context-bundle:` с абс-тройкой (строки `key = /abs/path` для digest/glossary/master TZ) И отдельный блок `context-used:` с `card: <id>` + `tz_version`. Копирования одного `context-used:` (где всего card/root/phase/tz_version, без абс-путей) **недостаточно** — `check` упадёт «нет пути: digest» и `check` exit 1. Поэтому в комментарий кладёшь оба блока одним постом, и `check` проходит. Если `check` после копирования дал «нет пути» — дописать `context-bundle:` с тройкой, пере-прогнать `check`, потом `kanban_complete`.

**Обхода context-bundle нет (решение Саши 26.09, без исключений):** ни `flag-waived`, ни `--force` / `--force-bypass-sasha-ok` как обход тройки digest+GLOSSARY+мастер-ТЗ; скрипт `emit-prompt`/`check` блокируют всегда.

**Новая сущность / первый прогон ТЗ (chicken-and-egg):** на первом `TZ:patch` нового инструмента/скилла guard падает «инструмент не найден в манифесте: <Name>» — потому что `emit-prompt` требует И запись `tools.<key>` в EcosystemManifest.json, И мастер-ТЗ на диске, а у новой сущности ещё нет ни того ни другого. Это НЕ баг и НЕ повод `--force`: предусловие — **зарегистрировать stub** `tools.<key>` (status draft, `tz_ref` → целевой `TZ/<Name>/<Name>_TZ.md`) в манифесте ДО прогона; stub пишет оркестратор (зона ORCH по сути, хотя формально ORCH:shared-state позже — это аддитивный stub, не полная запись). Мастер-ТЗ даёт резолв по `tz_ref` или фоллбэку `TZ/<Name>/<Name>_TZ.md`, поэтому путь должен существовать. `resolve_tool_entry` матчит и по snake_case-ключу, и по полю `name`, поэтому ключ `dev_workflow` матчится и через `--tool DevWorkflow`.

### Воркер HF-фаз

1. `kanban_show()` → сверка TZ version/mtime → `cd $HERMES_KANBAN_WORKSPACE`.
2. **Перед любым `agent -p` по инструменту** (все HF-фазы: `HF:plan`, `HF:impl`, `HF:test`, `HF:docs-handoff`, `HF:backup`, `REV:plan`, …): вызвать `emit-prompt` — **exit 0 обязателен**, иначе **СТОП**, `agent -p` не вызывать. Легальный `agent -p` — только от файла `--out` (`$(cat /tmp/task.md)`): `python3 /home/tkachenkoav/WorkVault/Registries/pipeline_context_bundle.py emit-prompt --card $HERMES_KANBAN_TASK --tool <Name> --task-file <план> --out /tmp/task.md`; при exit 0 → **скопировать блок `context-used:` из `/tmp/task.md` в `kanban_comment`** (G2/AC-H06), затем `agent -p "$(cat /tmp/task.md)" -f --model <МОДЕЛЬ> --workspace <ABS_DIR> --output-format json`. Перед `kanban_complete` HF/BUG/REV: `check --card` exit 0 обязателен (G2). Обхода context-bundle нет: `flag-waived` и `--force` / `--force-bypass-sasha-ok` не отменяют `emit-prompt`/`check`.
3. `kanban_heartbeat` на длинных `agent -p`; `session_id` → `kanban_comment` после первого вызова.
4. Промпт Cursor CLI — **одна роль, одна фаза:**

```
Одна роль: {role} ({model}). Только фаза {phase}. Чужие фазы не выполнять.
G5: не строй кейсовый граф / не меняй --case / не skip фаз / не выбирай LIGHT — это оркестратор.
```

Роли/модели (PI B3): compress=оркестратор `deepseek-v4-flash-0731` (без Cursor; заключение t_645aa647); plan/patch/finalize=архитектор `cursor-grok-4.6-high` (CHANGE-LIGHT ≤3 файла: допустим `cursor-grok-4.6-medium`); REV=ревизор `claude-sonnet-5-medium`; impl/test/docs-handoff=исполнитель `composer-2.5`; backup=координатор `composer-2.5`; ORCH=оркестратор.

5. `kanban_complete` с metadata:

```json
{
  "changed_files": ["..."],
  "registry_touches": [],
  "manifest_hints": ["tools.<key> fields to set"],
  "skills_to_sync": ["tz-workflow"],
  "tz_version": "0.1.0",
  "tz_mtime": "2026-09-05T12:00:00Z",
  "cursor_session_ids": ["..."],
  "role": "исполнитель",
  "model": "composer-2.5",
  "pipeline_schema": "1.0"
}
```

6. **Свёртка по `changed_files`:** на фазах **исполнителя** `HF:impl` и `HF:test`: если `changed_files` содержит путь `*_TZ.md` **или** `HF-plan*` → не complete, а `kanban_block(reason="review-required: collapsed-chain")`. Не применять к `HF:plan` (план — его артефакт) и к `HF:docs-handoff` (ТЗ — его артефакт).
7. **Машинный факт на диске для read-only фаз `HF:plan`/`REV:plan`** (контроль premature-impl, инвариант 8/Блок 1А). На фазе планирования целевой каталог скилла не должен получать impl-артефактов:
   - **до** `agent -p`: снимок `disk_before` целевого каталога скилла из ТЗ — `python3 ~/WorkVault/Registries/pipeline_hf_plan_diskfact.py snapshot --skill-dir <abs>` → `kanban_comment` (JSON).
   - после: `disk_after` + `diff --before --after`. Если `PREMATURE_IMPL` (появились `SKILL.md`/`scripts/`/`tests/`/`references`/`cli.py`, которых не было в before) → `kanban_block(reason="review-required: impl-before-plan-approve")`; self-report «каталог есть» при `disk_before.exists=false` = это же block.
   - Легальный черновик (каталог был в before, код в этой фазе не менялся) → complete ок; `HF:impl` затем сверяет с планом, не пишет второй раз.
   - В `kanban_complete.metadata` класть `disk_before`, `disk_after`, `premature_impl: false|true`, `allowed_writes` (план-файлы `HF-plan_*.md`).


Непустой `registry_touches` → `kanban_block(kind=capability, reason="executor touched shared state")`.

### GATE:plan-approve

- **Always auto** (`auto-pass: architect-plan`); `HF:plan` обязателен до гейта. Саша план не согласовывает.

### Блок 4 — владелец общего state

- Исполнитель = `HF:docs-handoff`: текст скилла/ТЗ-секции **кроме** манифеста; `manifest_hints` в metadata.
- Запись манифеста, digest/render, `restore-all-skills.sh`, `.env`/`jobs.json`/`entities.json` — **только** `ORCH:shared-state` (после `done` всех инструментных карточек).
- **`ORCH:shared-state` (HF-TAIL и `DECOMM-TAIL`):** AC карточки — `python3 ~/WorkVault/Registries/render_manifest.py --check-drift` exit 0 **или** остаток дрейфа явно не про slug этого графа/DECOMM.
- **После `DEC:exec` (`DECOMM-TAIL`):** в `tools{}` — `status=archived`, `path` = каталог архива; `tz_ref` можно оставить; исторические `links` допустимы — contract-check в `render_manifest.py` пропускает `archived`/`completed`.
- `ORCH:shared-state` workspace: `dir:/home/tkachenkoav/WorkVault/Registries`.

### GATE:done — статус «готово»

Порядок воркера `GATE:done` (контракт AC-delivered):

1. `kanban_show()`.
2. Собрать отчёт AC-### → как тестировали (команда, лог/артефакт, результат).
3. Опубликовать отчёт AC в **диалог = origin-топик** графа (откуда пришёл запрос; не ops-канал Monitoring `:7`, не Errors `:11112`, не личный DM оркестратору; если origin сам `:7` — дубля в другой топик нет).
4. kanban_comment на карточку GATE:done: маркер `AC-delivered: origin` + тело отчёта:
   ```
   AC-delivered: origin
   ## Отчёт AC
   AC-001 → команда / лог / результат
   ```
   Маркер — ТОЛЬКО после реального поста в origin. Не считать комментарий GATE:take-into-work
   (список AC-001) и подписку-уведомление Monitoring `:7` доставкой отчёта, **если origin другой**.
5. Запустить preflight:
   `python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py --slug <slug> --case <DEV|CHANGE|CHANGE-LIGHT|BUGFIX|BUGFIX-LIGHT|RESEARCH|MIGRATION|DECOMM|SKILL-DEV|SKILL-CHANGE> --mode done [--flag-rev]` (`--case` ∈ 10 имён AC-H02, `--mode done` явно)
6. **exit 0 → `kanban_complete`** (`auto-pass: preflight-0`), НЕ block «ждать готово» (императив 28.09; preflight 0 достаточен **после снятия operator-holds `operator-done`+evidence и пустых open-questions**). **Нельзя** ✅ на operator-AC со `status=open` в отчёте — честно ⏳; при O open preflight → exit 1 → `kanban_block` `review-required: operator-action: <verb>`, complete запрещён. Корень `DEV/<slug>` закрывается **только** после `GATE:done` done (запрет `kanban_complete` корня, пока `GATE:done` не done).
7. exit 1 или 2 → comment чек-лист stderr; `kanban_block`; **запрет** complete. reason: `review-required: preflight GATE:done` (exit 1) — чинить граф, не ждать Сашу; operator-hold → `review-required: operator-action: <verb>`; или `review-required: collapsed-chain` (exit 2).

**G3 git-proof (AC-H07):** перед `kanban_complete` фаз `HF:test` и перед вызовом preflight `GATE:done` — impl-пути из `changed_files` HF:impl, лежащие в git-worktree, **должны быть закоммичены** (`git status --porcelain -- <path>` пуст). Untracked / modified → не complete. Если `emit-prompt` на `HF:test`/`HF:docs-handoff` дал exit 1 из-за untracked — `agent -p` **не** звать (AC-H05b).

**Always auto** (и в one-pass). Preflight exit 0 **достаточен** для `GATE:done` **после снятия holds и пустых Q**. Фраза Саши «готово» на этом гейте — идемпотентный no-op (гейт уже done). Отчёт AC уже доставлен в origin до auto-complete.

**Воркер `HF:plan`:** после `kanban_complete` плана проверить `kanban_show` — если `children=[]` у карточки плана (legacy unfold), `kanban_block` `review-required: broken-tail: HF:plan без детей`, **не** complete «план готов». На каноне v0.4.0+ дети хвоста уже в create-батче.

**Процедура H на `HF:plan`:** недосказанный бриф → стоп, `open-questions: Q-n` на корне, block корня `review-required: operator-action: answer:Q-n`, не `needs_input` на HF.

### Режим «делай в 1 проход»

Условия: мастер-ТЗ на диске; открытых вопросов нет; не обход diagnose-review.

Фраза **no-op для снятия AC-гейтов** (DKP 0.4.0): `GATE:take-into-work` / `GATE:done` — **always auto**; `GATE:plan-approve` — always auto.

**Не auto** (кризисный HITL): `GATE:go`, `GATE:block-accept`, IDEA `blocked`, crisis-block корня (`review-required: crisis`). `GATE:diagnose-review` — auto по артефакту.

One-pass — **не** склейка нескольких **дочерних** фаз в одном промпте (`TZ:patch`+`HF:impl` — запрещено GLOSSARY). DX всегда карточки на канбане. Баг-триггер — с `BUG:diagnose`.

#### One-pass не плодит хвост (оркестратор, правило C)

**Когда:** режим «делай в 1 проход» и корень `DEV/<slug>` **сам** выполняет цикл — один воркер-корень, **несколько** вызовов `agent -p` по ролям (grok затем composer), не один промпт «ТЗ+код+тесты»; на корне — пометка one-pass.

**При постановке — не разворачивать полный хвост (~16 фаз):** вместе с корнем **не** создавать через `kanban_create` типовой граф `TZ-WRITE` (`TZ:stabilize` → … → `GATE:take-into-work`, см. `tz-workflow`) **плюс** `PLAN-IMPL-TAIL` + `HF-TAIL` (`HF:compress` → … → `ORCH:shared-state` → `GATE:done`, см. граф выше). Работа уже в корневом `agent -p`; дочерний граф после `complete` корня только дублирует её и съедает слот диспетчера.

Допустимые варианты:

- **Только корень** (предпочтительно для «корень сделал всё»).
- **Корень + гейты** без промежуточных TZ/HF-фаз (три гейта для audit: `GATE:plan-approve` / `GATE:take-into-work` / `GATE:done` — always auto).
- **Минимальный граф** по кейсу (например `CHANGE-LIGHT` в GLOSSARY §5.1), если размер задачи совпадает — не полный DEV/CHANGE.

> **Ограничение G4/one-pass (AC-H08/H09):** укорочение графа / выбор «минимального» / корневой one-pass — решение **оркестратора + Саши** на постановке; архитектор на `TZ:patch`/`REV:tz` **не** решает сократить граф по собственной инициативе.

Полный хвост «на всякий случай» при корневом one-pass **запрещён**.

**Пошаговый one-pass** (редко, если хвост уже нужен по размеру): промежуточные фазы графа — **отдельные** `agent -p` на каждую карточку; гейты — auto-pass. Не путать с корневым one-pass.

**После `kanban_complete` корня** (корневой one-pass, артефакты на диске), если дочерние фазы **уже** были созданы (legacy, ошибка постановки):

1. `kanban_show` корня — список детей в `todo|ready|running|blocked`.
2. Каждую такую карточку **снять с диспатча без нового `agent -p`:** `kanban archive` (CLI/tool), либо при block — `kanban_unblock`, затем `kanban_complete` с comment `auto-archived: one-pass root done`.
3. `GATE:done` (если карточка есть): доставка отчёта AC в origin Саши → комментарий c `AC-delivered: origin` + тело отчёта → preflight → exit 0 → complete (auto-pass: preflight-0).
4. Comment на корне: `one-pass tail archived: <N> cards` (audit).

**XOR-канал координатора (влечён из инварианта 8, GLOSSARY §5.2):** пока граф `DEV/<slug>` диспатчится (есть дети `todo/ready/running`), координатор **не** вызывает свой `agent -p` на фазы графа — гейты авто-проходятся, фазы выполняет диспетчер. Прежде чем сделать любой **ручной** cursor-cli по слагу:
1. `kanban_show` корня: дети в `todo|ready|running` → канал `kanban`, свой вызов **стоп** (ждать очередь / auto-pass гейтов).
2. Нужен прямой ход (crash-spawn, спешка) → **сначала** вывести граф: comment корня `dispatch-paused: off-board`, снять/не диспатчить remaining → потом свои вызовы + retro-create `done off-board, session ids`, **и только при снятом `GATE:plan-approve`** (для кодосодержащих фаз). Иначе живёт двойной канал (воркер + координатор) на одной фазе — запрещено.

---

## Модели (Cursor CLI) — раздельные задачи по шагам

**Инвариант:** один вызов `agent -p` = одна модель = одна роль. Сирень координирует цепочку из 4 отдельных задач Cursor — **не смешивать** модели в одном промпте.

> Столбец «Модель» — аргумент бинарника `agent -p`, **не** `kanban_create --model` / `tasks.model_override`.

| Шаг | Роль | Модель (`agent -p`) | Блок |
|---|---|---|---|
| 0 | Компрессия ТЗ | `deepseek-v4-flash-0731` (оркестратор, без Cursor) | Блок 0 / tz-workflow Шаг 0 |
| 1 | Архитектор (ТЗ, план, риски) | `cursor-grok-4.6-high` | Блок 0, 1, 1А, 6В |
| 2 | Исполнитель (код, тесты) | `composer-2.5` | Блок 1А baseline, 2–4, 7 |
| 3 | Контроль (тесты, верификация) | `composer-2.5` | Блок 3 |
| — | Координатор (механика) | `composer-2.5` | бэкапы, инвентарь, операторка |

Промпт компрессии: `~/WorkVault/Registries/tz-compressor-prompt.md`. Экстракты **без кэша** между задачами.

### Паттерн вызова Cursor CLI

```bash
cd ~/WorkVault/Hermes-Backlog/TZ && agent -p "задача" -f --model cursor-grok-4.6-high --output-format json
```

- `-p` — print-mode (неинтерактивный)
- `-f` — force (пропуск диалогов доверия)
- `--model` — модель из таблицы выше
- `--output-format json` — структурированный вывод с usage/session_id

**Инвариант передачи полного документа:** `-p "$(cat /tmp/task.md)"` = весь файл, без `head -c` / `truncate` / `head -n`. Если не влезает — в промпте абсолютный путь + «прочитай сам», либо явно «часть 1/N». Неполная копия ≠ полный документ (канон: pitfall cursor-cli).

---

## Блок 0: ТЗ

ТЗ финализировано архитектором (скилл `tz-workflow`), AC показан в origin, `GATE:take-into-work` авто-пропущен. Реализация после `TZ:finalize` идёт сама (императив 28.09) — отдельной команды Саши не ждём. **Кризис** (невыполнимо / неоптимально / разрушающе) — архитектор пишет в origin и ставит `kanban_block` **корня** `review-required: crisis: …`; поезд стоит, пока Саша не решит.

---

## Блок 1: Анализ вариантов

**Валидация и рекомендации по постановке — только от архитектора (требование 2).** Сирень (Hermes) НЕ предлагает собственное мнение, варианты решений или рекомендации по постановке/архитектуре задач — передаёт архитектору (`cursor-grok-4.6-high` через Cursor CLI), выполняет по его рекомендациям. Фактологические уточняющие вопросы Саше — текстом (процедура H / R3), без собственных вариантов по постановке (стыковка с Q2 бриф-фазы).

**Шаг 0 (оркестратор, без Cursor):** компрессия master-ТЗ по `tz-compressor-prompt.md` на `deepseek-v4-flash-0731` — full-coverage 3–5 КБ, без кэша.

**Шаг 1 (отдельный Cursor, архитектор):** анализ вариантов на входе digest + экстракты Шага 0.

- **Критерии:** токены / безопасность / консистентность / поддерживаемость + специфичные для задачи.
- **Количество:** 2-3 лучших; слабые архитектор отсеивает сам.
- **Reuse-first (см. references/reuse-first-rule.md):** варианты формируются через существующие USERTOOLS/applications/реестры; новое приложение/инструмент — только если существующие не закрывают, отдельным пунктом «требует согласования Саши».
- **Подача:** сначала рекомендация с обоснованием → остальные кратко.
- **Варианты только цифрами 1/2/3**, никогда не A/B/C.
- После выбора варианта: уточняющие вопросы **по одному** (варианты закрыты на `BRF`/`TZ:patch`).

**Completion criterion:** архитектор зафиксировал выбор в ТЗ, **без** второго «берём в работу» на варианте.

---

## Блок 1А: Планирование *(до Блока 2)*

**Архитектор составляет пофайловый план:**
- Какие файлы создать / изменить
- Какие функции / классы / методы добавить
- Какие тесты написать
- Если план вводит новую сущность — отдельная строка „Новая сущность X — требует согласования Саши“ до Блока 2; без явного ОК реализация новой сущности не начинается.
- Промежуточные точки проверки с критериями

**ТЗ-файл только для задач с Python-кодом.** Для скиллов, конфигов, memory-правок — план в чате.

**Исполнитель проходит промежуточные точки молча** — без отчётов Саше; на границах `HF:impl`/`HF:test` гоняет `verify` из таблицы IAC; в `kanban_complete.metadata` — `iac_passed`.

**Таблица IAC** (синтаксис tasks.md, без отдельного файла `tasks.md` в пакете):

| IAC-## | phase_from→phase_to | path | verify | depends | covers AC-### |
|---|---|---|---|---|---|
| (строки пакета) | … | … | команда/артефакт | … | AC-00N |

План на диске: `HF-plan_*.md` в workspace пакета (секция с таблицей IAC). **LIGHT** (BUGFIX-LIGHT / CHANGE-LIGHT): 1–3 строки IAC в секции ТЗ / `_fix_plan_*.md` / body `BUG:diagnose` — **не** возвращать полный `HF:plan`.

**⚠️ Неожиданный каталог скилла на диске = аномалия, не «сверить и дописать».** Если в фазе `HF:plan`/`REV:plan` (read-only по коду скилла) в workspace уже появились `SKILL.md`/`scripts/`/`tests/`, которых не было в `disk_before` — это impl-before-plan-approve (иначе параллельный процесс). Зафиксировать `premature_impl: true` в comment, `kanban_block("review-required: impl-before-plan-approve")`, НЕ копировать/дорабатывать чужой код в фазе планирования.

**Устойчивость к сбою:** `## Прогресс выполнения` с чекбоксами в файле плана.

**Completion criterion:** таблица IAC на диске / в `HF-plan_*.md` + `HF:plan` done → `GATE:plan-approve` auto (`auto-pass: architect-plan`).

---

## Блок 2: Реализация

### Кто пишет
- **Исполнитель (composer-2.5)** — пишет код по плану архитектора
- **Архитектор (cursor-grok-4.6-high) (fallback)** — только если исполнитель не справился: архитектурный тупик или повторяющиеся необъяснимые ошибки. Исполнитель даёт вывод → **Саша решает** запускать ли архитектора.

**Мелкое отклонение** (≤2 файла, не меняет архитектуру) → исполнитель сам.
**Крупное отклонение** → исполнитель стопится → архитектор делает доплан → исполнитель продолжает.
**Системный блокер** (пакеты, sudo) → исполнитель стопится → вопрос Саше напрямую.

### Чеклист перед первой строкой кода
1. ТЗ согласовано + `GATE:take-into-work` done (`auto-pass: ac-shown`) — фразу «берём в работу» не ждём (императив 28.09).
2. **Бэкап создан** (см. Блок 5).
3. `HF:plan` done + `GATE:plan-approve` auto (`auto-pass: architect-plan`).
4. Если план вводит новую сущность — согласование Саши получено отдельно от общего „берём в работу“.
5. **Канбан:** `GATE:plan-approve` = done/unblocked **или** auto-pass one-pass (режим «делай в 1 проход»).
6. **Auto-pass гейта ≠ «можно код сейчас».** Auto-complete `GATE:plan-approve` (one-pass) разрешает **диспетчеру** запустить `HF:impl`; координатору он не даёт права писать код вне очереди графа (XOR-канал, инвариант 8). Прямой impl координатора — только после `dispatch-paused` + off-board.
7. **Стоп-кран identity (DKP «Прекондиция identity») — для HF:impl **origin-routing**: перед этим `HF:impl` воркер **стоп**, если любой из 4 пунктов ложен** → `kanban_block(kind=dependency, reason="wait DEV/tg-topic-duplicate identity + поднимай")`, файлы не писать. В `kanban_comment` карточки `HF:impl` — блок `identity-checklist:` с **выводом** 4 фактов (не пересказом). Канон 4 пункта:

   1. `build_session_key(TELEGRAM, chat_type='thread', thread_id=N)` → слот `:group:`, не `:thread:`.
   2. Wake: TELEGRAM + `thread_id` → `SessionSource.chat_type=='group'`.
   3. SQL: `SELECT COUNT(*) FROM kanban_notify_subs WHERE chat_id='-1004300127777' AND chat_type='thread'` = 0.
   4. Нет живой вилки `telegram:thread:-1004300127777:*` в `state.db`.

   (Live-wake смоук `AC-010` — только после фразы Саши **«поднимай»**: рестарт gateway этим графом **запрещён**; `kanban_block(kind=dependency, reason="wait поднимай for AC-010")`, не skip).

---

## Блок 3: Тестирование

- `HF:test` выполняет **исполнитель** (`composer-2.5`): гоняет `verify` из таблицы IAC плана архитектора, молча (AC-H04). **Отдельной роли «тестировщик» нет** (решение Саши 29.09; см. Блок 3 в GLOSSARY).
- **Мелкий баг** (≤2 файла, очевидная причина) → исполнитель чинит сам (1 попытка)
- **Крупный баг** → исполнитель фиксирует причину → **Саша решает** → архитектор делает hotfix-план → исполнитель применяет
- **Готово =** все точки проверки из плана архитектора пройдены (✅/❌)
- **Волна eco-config (w1–w4):** обязательный AC `HF:test` = `probe_battle_venv.py` PASS на боевом python **каждого** ключа волны; pytest PFS/hermes этот AC **не** закрывает (§10.12 EcologyIntegration)
- Статус «completed» на весь **граф** — через `GATE:done` auto-complete после preflight exit 0 (не приёмка `HF:plan`).

---

## Блок 4: Документирование

- ТЗ-файл в `TZ/<Tool>/<Tool>_TZ.md` пока инструмент используется. Архивация — только при выводе из эксплуатации.
- Исполнитель (`HF:docs-handoff`): текст скилла/ТЗ-секции **кроме** манифеста; `manifest_hints` в `kanban_complete.metadata`.
- **Манифест, digest/render, `restore-all-skills.sh`, `.env`/`jobs.json`/`entities.json` — только `ORCH:shared-state`** (оркестратор Сирень). Исполнитель не пишет в `EcosystemManifest.json`. AC `ORCH:shared-state` / `DECOMM-TAIL` по `--check-drift` — см. «Блок 4 — владелец общего state» (канбан-шаг).
- **Скилл:** мелкая правка → архитектор сам; новый раздел → предлагает Саше.
- **MEMORY и скиллы:** см. `hermes-memory-hygiene`.

---

## Блок 5: Бэкапы и откат

- **Задачи архитектора:** бэкап всегда.
- **Задачи исполнителя:** только если затронут `config.yaml` или `jobs.json`.
- **Путь:** `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`.
- **`DECOMM-TAIL`:** после `HF:backup` и `DEC:exec` — обновление манифеста в `ORCH:shared-state`; приёмка drift — тот же AC `--check-drift`, что у HF-TAIL (канбан «Блок 4 — владелец общего state»).
- **Хранение:** 2 недели, 1 бэкап в день. Self-check чистит.
- **Откат:** авария → архитектор немедленно; плановый → архитектор предлагает, ждёт ОК.

---

## Блок 5Б: Классификация разрешающего сигнала

**Триггер:** любой `write_file`/`patch` вне `_Archives/`, `cronjob(create|run)`, `curl -X POST|PUT|DELETE` к API.

| Категория | Разрешает? |
|---|---|
| `direct-imperative` — глагол-императив от Саши именно на это действие | ✅ |
| `continuation-of-approved-plan` — пункт из согласованного плана | ✅ |
| `question-answer` — ответ на вопрос, действие не запрошено | ❌ |
| `own-inference` — модель вывела «раз X, значит нужно Y» | ❌ |
| `conditional` — «если X — делай Y», истинность X оценивает модель | ❌ |

Если ❌ — отдельный turn без side-effect-инструментов, текстовый вопрос Саше.

---

## Блок 6: Эскалация

**Стоп + пишет Саше:** критическая поломка, неопределённость в ТЗ.
**Ночью:** сохранить состояние в ТЗ-файл → «жду решения» в TG → ждать утра.
**Молчит:** рутинные cron без ошибок.

---

## Блок 6А: QA-проверка

Не PREFIX:фаза. Не обязательный `agent -p`. Канон покрытия тестами пайплайна — `HF:test` (`composer-2.5`). 6А — только hotfix без плана 1А.

**Пропускается** если архитектор уже написал план с тестами (Блок 1А) и исполнитель прошёл его (Блок 3).

**Применяется** для изменений БЕЗ предварительного плана архитектора (срочный hotfix, ручная правка).

Процесс: крон архитектора собирает чек-лист → исправить ❌ → повторить (макс 3 попытки) → все ✅ = короткий отчёт. Остались ❌ → откат + доклад.

---

## Блок 6Б: Делегирование субагентов

Таблица 6Б — не канон PREFIX:фаза и не канон живого графа DEV/<slug>.
На живом графе: только agent -p по таблице DKP (инвариант 8). cronjob/delegate_task
на диспатчащихся детях запрещены.

Namespace (прецедент t_2c8ee3b2): cronjob(repeat=1) и delegate_task — D1
модель карточки / Hermes-воркера (hermes chat -m / toolsets file|terminal|web), НЕ нативный
Cursor CLI subagent и НЕ kanban_create. Передавать cursor-grok-* /
composer-2.5 / claude-sonnet-* в cronjob(model=) / delegate_task(model=)
запрещено (HTTP 400 tutu, 0 tool-calls, protocol_violation).
Если 6Б всё же вне пайплайна: D1 = NULL или tutu vendor/model;
роль Cursor (D2) — только внутри уже живого воркера через agent -p --model.
Колонка «Модель» ниже — slug внутреннего agent -p, не аргумент cronjob/delegate.

| Задача | Модель | Инструмент | Таймаут |
|---|---|---|---|
| Архитектор: ТЗ / план / анализ | `cursor-grok-4.6-high` | `cronjob(repeat=1)` | — |
| Архитектор: реализация (fallback) | то же | `cronjob(repeat=1)` | — |
| Исполнитель: реализация >5 мин | `composer-2.5` | `cronjob(repeat=1)` | — |
| Исполнитель: короткая <5 мин | `composer-2.5` | `delegate_task` | 300с |
| Координатор: справочный | `composer-2.5` | `delegate_task` | 120с |

НЕ для диагностики/починки багов инструментов и кронов — это канбан-кейс BUG:diagnose (Блок 6В), а не одноразовый cronjob-аутсорсинг. Архитектор на диагностику бага вызывается только как воркер карточки BUG:diagnose.

### Toolsets

| Задача | enabled_toolsets |
|---|---|
| Архитектор: ТЗ / план | `["file", "terminal"]` |
| Исполнитель: реализация | `["file", "terminal"]` |
| Исполнитель: тестирование | `["file", "terminal"]` |
| Исследование с web | `["file", "terminal", "web"]` |

### Что передавать в промпт

1. Роль и среда, абсолютные пути
2. Полный текст ТЗ или плана: `cat` без `head`/`truncate`. Если не влезает в один промпт — абсолютный путь к файлу + «прочитай сам», либо явно «часть 1/N». Запрещено молча обрезать и выдавать обрывок как полный документ. Wiki-ссылки / URL без тела по-прежнему недостаточно. (Канон: pitfall cursor-cli.)
3. Граница автономности: «механическое — делай сам; семантическое — СТОП»
4. Формат отчёта, явные запреты
5. **Критичные факты из MEMORY — явно в промпт.** Cron-сессии НЕ получают MEMORY/USER PROFILE.
6. **Reuse-first (см. references/reuse-first-rule.md):** субагент не внедряет новые сущности без явного согласования Саши.

Полные правила: `references/subagent-rules.md`.

---

## Блок 6В: Диагностика перед починкой

Когда «что-то не работает» — **не чинить сразу**. Порядок:

1. **Заведи карточку BUG:diagnose** (read-only: чтение, запрет правок). Воркер карточки: **сначала** `emit-prompt` (exit 0 обязателен, иначе СТОП), **затем** `agent -p "$(cat /tmp/task.md)"` с `--model cursor-grok-4.6-high` (архитектор) — не сырой промпт вне `--out`. Оркестратор **не** пишет `_fix_plan` сам. `kanban_create` **без** `--model`.
2. `GATE:diagnose-review` — **auto** (доработка B): воркер гейта complete сам, когда `BUG:diagnose` done и на диске есть `_fix_plan_*.md` **или** непустой body; классификация LIGHT — в том же ходе, без ожидания Саши. REV качества ТЗ остаётся `REV:tz` в `TZ-WRITE`.
3. Карточка-воркер/исполнитель реализует по плану (GLOSSARY §5.2)

План сохранить в `_fix_plan_YYYYMMDD.md` рядом с инструментом.

---

## Блок 7: Диагностика и отладка

**При изменении ТЗ** (параллельно передаче задачи в Cursor): запустить drift-check манифеста:

```bash
python3 ~/WorkVault/Registries/render_manifest.py --check-drift
```

Расхождения — в отчёт Саше; обновление манифеста — после согласованной реализации (Блок 4).

**Метод:** скилл `systematic-debugging` (4 фазы: root cause → pattern → hypothesis → fix). Диагноз — `BUG:diagnose`; фикс — `HF:impl` (не `HF:fix`).

**Reuse-first при фиксе (см. references/reuse-first-rule.md):** root cause чинится через существующие инструменты; новый инструмент — только предложение на согласование.

**Специфика:**
- Модель: исполнитель (composer-2.5)
- Мелкий баг → исполнитель чинит сам (1 попытка)
- Крупный → Саша решает → архитектор делает hotfix-план
- Системный блокер → вопрос Саше напрямую
- Эскалация к архитектору: root cause в архитектуре, не воспроизвелось за 2 попытки
- Эскалация к Саше: данные могут быть повреждены, production down

---

## Блок 8: Исследования и анализ

Триггеры: «проанализируй», «исследуй», «найди», «посчитай», «сравни», «что если».

**collect/analyze** = grok `agent -p`; **REV:report** = sonnet; постановка = карточки `RS:*`, не свободный чат без графа RESEARCH.

**Алгоритм:** Scope → Сбор → Анализ → Рекомендации.

**НЕ делать:** не менять код/конфиги/скиллы без графа RESEARCH, не делать выводы без данных.

---

## Паттерн обновления Hermes (merge upstream)

Для обновления Hermes из upstream — загрузить `references/hermes-upgrade-pattern.md`.
Там: стратегия MERGE, risk zones, питфоллы (venv/pytest, index.lock, config migration), бэкап-конвенция, upstream turbulence signals.

### venv-операции в USERTOOLS-инструментах (прецедент 23.09, PFS)

Любое пересоздание/пересборка `.venv` воркером (uv sync, recreate) может сломать боевой крон: shared-зависимости соседних пакетов пропадают. Правило: после ЛЮБОЙ venv-операции в инструменте — `uv sync --extra dev` и проверить импорты всего shared-стека (для PFS: `confluencesync`, `entityregistrycli`, `mofs_index`, `bs4`, `markobjectsfromsummary`), затем боевой импорт/сухой вызов. Smoke: `python -c "import markobjectsfromsummary"`. Sibling-зависимости объявлять в `pyproject.toml` инструмента (`pkg @ file:///${PROJECT_ROOT}/../<Tool>`), не ручным `uv pip install` — источник истины pyproject. Не ставить PyPI-пакет `bs4` (заглушка; нужен `beautifulsoup4`). `uv.lock` не коммитить, пока pyproject не описывает реальный runtime.

**Утверждено:** правки ядра hermes-agent — ТОЛЬКО с ревизором (reviewer). Никогда не патчить ядро без REV.

---

## Связанные файлы

- `references/hermes-upgrade-pattern.md` — паттерн обновления Hermes (merge, питфоллы, бэкапы)
- `references/cursor-cli.md` — установка, аутентификация, pitfall'ы Cursor CLI
- `references/cursor-cli-patterns.md` — справочник вызовов Cursor CLI
- `references/cursor-cli-limitations.md` — ограничения Cursor CLI
- `references/pitfall-remediation-workflow.md` — процедура починки код-питфоллов (Pitfall Scan → закрытие в *-pitfalls.md)
- `references/srtool-v2-pitfalls.md`
- `references/movefromloop-v042-pitfalls.md`
- `references/movefromloop-v043-pitfalls.md`
- `references/reuse-first-rule.md`

## Verification Checklist

- [ ] `TZ:finalize` done, AC показан в origin, `GATE:take-into-work` done (`auto-pass: ac-shown`) — фразу «берём в работу» не ждём (императив 28.09)
- [ ] `HF:plan` done + таблица IAC; `GATE:plan-approve` auto (Блок 1А)
- [ ] Бэкап создан в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (Блок 5)
- [ ] Модели: архитектор (cursor-grok-4.6-high) планирует, исполнитель (composer-2.5) пишет/тестирует
- [ ] Cron-субагент: критичные факты из MEMORY переданы явно в промпт
- [ ] Перед каждым side-effect — категория разрешающего сигнала определена (Блок 5Б)
- [ ] Статус «готово»: `GATE:done` always auto после preflight exit 0 (**holds сняты, Q пусты**); отчёт AC — в origin до auto-complete (маркер `AC-delivered: origin`); operator-AC без ✅ при open hold; корень не complete до `GATE:done` done; `HF:plan` + `children=[]` → broken-tail block
- [ ] Все вызовы через Cursor CLI (`agent -p`)
- [ ] Полный документ в `agent -p`: `cat` без head/truncate, либо путь + «прочитай сам», либо явно «часть 1/N»; неполная копия не выдана как полная
- [ ] Новые сущности (если предлагались) — явно вынесены на согласование Саше, не внедрены самостоятельно.
- [ ] На любой баг-триггер первым tool-шагом было **kanban_create корня DEV/<slug> + BUG:diagnose в одном create-батче** (до agent -p), ретро-корень нет (инвариант 9)
- [ ] Если готовился вызвать agent -p / cronjob(repeat=1) / delegate_task на диагностику/план/реализацию бага — предварительно сделан kanban_show БУГ-карточки; карточка существует, иначе стоп
- [ ] Новый несекретный конфиг-ключ инструмента — только в `~/WorkVault/Registries/EcosystemConfig.yaml` + `EcosystemConfig.schema.json`; литерал пути/модели/токена в коде и новый per-tool `.env` = дефект; dual-read (`config.overlay.yaml`) запрещён для **новых** tools (сразу `unified_only` через `~/.hermes/lib/usertools_config.py`)
- [ ] Волна eco-config (w1–w4): `probe_battle_venv.py` PASS на боевом python каждого ключа волны; pytest PFS/hermes этот AC не закрывает
