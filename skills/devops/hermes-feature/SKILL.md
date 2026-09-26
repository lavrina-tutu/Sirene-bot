---
name: hermes-feature
description: "Use when: полный цикл разработки фич/инструментов Hermes (ТЗ → код → тесты → документация) + диагностика багов + процедура починки питфоллов (pitfall-remediation-workflow). Triggers: разработай, новый инструмент, сделай, напиши код, реализуй, реализация, почини, починка, баг, ошибка, не работает, упало, разберись, исследуй, проанализируй, доработка, дорабатываем, MoveFrom*, обновить гермес, обновление гермес, hermes update, апгрейд, merge upstream, upstream merge, обновление версии."
version: 2.9.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, cursor, development, feature, process, debug, research]
    related_skills: [tz-workflow, hermes-agent-skill-authoring, hermes-ops]
---

# hermes-feature

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
| «баг», «ошибка», «не работает», «упало», «почини», «починка», «разберись», «проанализируй ошибки», «cron run failed», «отдай на разбор/план починки», «fix», «root cause» | канбан-граф BUGFIX = BUG:diagnose → GATE:diagnose-review → TZ-WRITE(patch/light) → PLAN-IMPL-TAIL(-LIGHT). ПЕРВЫЙ tool-шаг — `kanban_create` корня `DEV/<slug>` И карточки BUG:diagnose в одном create-батче, ДО любого agent -p / cronjob / delegate. Ретро-корень запрещён (инвариант 9). Классификация LIGHT — после GATE:diagnose-review (≤3 файла вне shared). После `TZ:finalize` (багфикс-ТЗ) `GATE:take-into-work` HITL never auto, payload=AC; `GATE:diagnose-review` не ждёт фразу Саши (не HITL Саши). Требование 4 отменено (DKP v0.3.2, HITL вариант 1) |
| «спроси», «проверь», «вычисли», «найди данные», «найди в архиве», «сколько», «покажи» | прямой ответ (без кода/процесса; нет карточки) |
| «одношаговый ответ», RESEARCH-триггеры («проанализируй», «исследуй» без починки) | прямой ответ / RS-граф (по DPK-исключениям) |

Правило сверху: «Работа с кодом/процессом (любое изменение) по баг-триггеру — ТОЛЬКО через канбан-граф. Прямой ответ — только когда НЕТ кода/процесса. Сомнение — всегда в сторону карточки BUG:diagnose.»

**Связь с tz-workflow:** после согласования ТЗ и получения «берём в работу» — перейти к этому скиллу для реализации.

---

## Канбан-шаг

> DevKanbanPipeline (`TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md`). Все карточки `assignee=default`. Исполнители **не** пишут в `EcosystemManifest.json` / `entities.json` / `.env` / `jobs.json` — только `ORCH:shared-state`.

### Вход

- Любой HF `agent -p` без корня `DEV/<slug>` → **стоп** + оркестратор. Исключения DPK: `BRF:*` в TG; одношаговый ответ; RESEARCH.
- Вход в HF-ветку только если корень `DEV/<slug>` существует **и** `GATE:take-into-work` снят **Сашей** (фраза/дашборд). Иначе стоп + текст «нет „берём в работу“».
- **Все задачи по умолчанию ложатся в план** (канбан-граф `DEV/<slug>`) после триггера «разработай/доработай/почини» и далее проводятся по канону, без дополнительной команды Саши (требование 1).
- **Slug-guard:** перед `kanban_create` корня `DEV/<slug>` (в т.ч. багфикс-батча) — проверка активного графа по слагу (`todo|ready|running|blocked`, не `done`/`archived`); дубли запрещены (кейс 1, прецедент pfs-notify-link-unprocessed). При совпадении — reuse существующего графа или `kanban_block` до разрешения.
- `GATE:plan-approve` / `HF:backup` / `HF:impl`: если `HF:plan` не `done` → **стоп** (GLOSSARY инвариант 6). Не skip плана в one-pass.
- Off-board: **предусловие** — сначала вывести граф из диспатча (comment корня `dispatch-paused: off-board`, снять/не диспатчить remaining), затем retro-create + comment `done off-board, session ids`. Без `dispatch-paused` прямой `agent -p` на живой граф запрещён (инвариант 8).
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

Граф выше — **пошаговый** режим (после снятия `GATE:take-into-work` оркестратор разворачивает `PLAN-IMPL-TAIL` + `HF-TAIL` через `kanban_create`). В **корневом** one-pass (корень сам делает работу) этот хвост **не создавать** — см. «One-pass не плодит хвост».

Skills: HF-* / GATE после take-into-work — `hermes-feature`, `cursor-cli`, `cursor-task-context`. ORCH:shared-state — только `hermes-feature`.

#### Подписка графа на уведомления (notify-subscribe)

Сразу после `kanban_create` (в том же ходе) подписать набор **R5** (наследования по `parents` **нет** — каждая карточка явно). Фиксированный контракт (топик мониторинга Monitoring :7, группа, Telegram — по умолчанию, без дублей в личный DM):

```bash
hermes kanban notify-subscribe <task_id> \
  --platform telegram --chat-id -1004300127777 --chat-type group \
  --delivery-mode notify+wake --notifier-profile default
```

Уведомитель шлёт в TG **только ключевые терминальные события** (по `TERMINAL_KINDS`: `completed`/`GATE:done`, `blocked`, `gave_up`, `crashed`, `timed_out`) — не каждую фазу графа (шум). Ядро канбана **не трогать**: ни `kanban_db.py`, ни `kanban_db_notify.py`, ни список `TERMINAL_KINDS`.

Репорты карточек — только в топик мониторинга (Monitoring :7), без дублей в личный DM, по умолчанию. Отдельное явное указание Саши может переопределить канал подписки конкретного графа.

- **Набор R5:** корень `DEV/<slug>` + `GATE:take-into-work` / `GATE:done` + `GATE:go` / `GATE:block-accept` / `IDEA:analyze` → `notify+wake`.
- **Не подписывать:** `TZ:*` / `HF:*` / `REV:*` / `BUG:diagnose` / `ORCH:*` / `RS:*` / `GATE:plan-approve` / `GATE:diagnose-review`.
- Багфикс-батч (`DEV/<slug>` + `BUG:diagnose`, Блок 6В): подписать **корень** `DEV/<slug>`.
- Ручной feed `IDEA/<slug>` + `IDEA:analyze`: корень `IDEA/<slug>` + `IDEA:analyze`.

### Блок 6В (багфикс)

При триггере «почини» — **до** TZ-ветки (кейс BUGFIX, GLOSSARY §2):

```none
корень DEV/<slug> + BUG:diagnose   # в ОДНОМ kanban_create-батче (инвариант 9), до agent -p
# сразу после батча — notify-subscribe R5 (контракт «Подписка графа на уведомления» выше)
GATE:diagnose-review  parents=[BUG:diagnose]   # never auto; субъект = архитектор+REV:tz; complete вручную архитектором
→ далее TZ-WRITE(patch|light) → GATE:take-into-work → PLAN-IMPL-TAIL | PLAN-IMPL-TAIL-LIGHT
```

`BUG:diagnose` — read-only, план П.1…П.N → `_fix_plan_YYYYMMDD.md`. Диагноз → `BUG:diagnose`; реализация → `HF:impl`. **`HF:fix` запрещён** (GLOSSARY §7). Инвариант: даже с известным root cause — нет перехода в hermes-feature без ТЗ-файла. Режим «1 проход» **не** обходит `GATE:diagnose-review`. Режим «1 проход» НЕ обходит GATE:diagnose-review И не отменяет создание карточки BUG:diagnose. DX всегда идёт как карточки на канбане, даже в one-pass. `GATE:plan-approve` — always auto; `GATE:take-into-work` / `GATE:done` — HITL never auto. Баг-триггер всегда начинает с карточки BUG:diagnose.

**Корень `DEV/<slug>` создаётся СРАЗУ, в том же create-батче, что и `BUG:diagnose`** (не ретро, инвариант 9). Ретро-корень = нарушение (прецедент pfs-promote-bugfix 22.09: preflight GATE:done красный). Первый tool-шаг при баг-триггере — `kanban_create` корня `DEV/<slug>` **И** DX в одном батче, **до** любого agent -p / cronjob(repeat=1) / delegate / cronjob-аутсорсинга диагностики.

**Классификация LIGHT (кейс BUGFIX-LIGHT, GLOSSARY §2/§5.2)** — **после** `GATE:diagnose-review`, а не на холодном старте. Критерий: ≤3 файла кода+тесты, вне shared-модулей, без новых сущностей/cron/.env/манифеста. Тогда:
- корень `DEV/<slug>` + `BUG:diagnose` → `GATE:diagnose-review` → `TZ:patch` → `TZ:finalize` → `GATE:take-into-work` → `HF:impl` → `HF:test` → `HF:docs-handoff` → `GATE:done` (preflight `--case BUGFIX-LIGHT`);
- skip: `HF:plan`, `GATE:plan-approve`, `HF:backup`, `REV:tz`/`REV:plan`, `HF:compress`, `ORCH:shared-state`;
- план = `_fix_plan_*.md` **или** непустой body `BUG:diagnose` (утверждён уже на diagnose-review);
- не генерировать пустые `auto-pass`-флаги (фальшивый audit).

**Требование 4 отменено (DKP v0.3.2):** после `TZ:finalize` `GATE:take-into-work` HITL never auto, payload=AC; `GATE:diagnose-review` не HITL Саши.

**Перед любым `agent -p` по инструменту на `BUG:diagnose` (и далее по багфикс-ветке):** обязательный `emit-prompt` — exit 0, иначе **СТОП**, `agent -p` не вызывать. Легальный вызов только от файла `--out` (промпт: `$(cat /tmp/task.md)`):

- `python3 /home/tkachenkoav/WorkVault/Registries/pipeline_context_bundle.py emit-prompt --tool <Name> --task-file <план> --out /tmp/task.md`
- exit 0 → `agent -p "$(cat /tmp/task.md)" -f --model <МОДЕЛЬ> --workspace <ABS_DIR> --output-format json`
- exit ≠ 0 → СТОП

**Обхода context-bundle нет (решение Саши 26.09, без исключений):** ни `flag-waived`, ни `--force` / `--force-bypass-sasha-ok` как обход тройки digest+GLOSSARY+мастер-ТЗ; скрипт `emit-prompt`/`check` блокируют всегда.

### Воркер HF-фаз

1. `kanban_show()` → сверка TZ version/mtime → `cd $HERMES_KANBAN_WORKSPACE`.
2. **Перед любым `agent -p` по инструменту** (все HF-фазы: `HF:plan`, `HF:impl`, `HF:test`, `HF:docs-handoff`, `HF:backup`, `REV:plan`, …): вызвать `emit-prompt` — **exit 0 обязателен**, иначе **СТОП**, `agent -p` не вызывать. Легальный `agent -p` — только от файла `--out` (`$(cat /tmp/task.md)`): `python3 /home/tkachenkoav/WorkVault/Registries/pipeline_context_bundle.py emit-prompt --tool <Name> --task-file <план> --out /tmp/task.md`; при exit 0 → `agent -p "$(cat /tmp/task.md)" -f --model <МОДЕЛЬ> --workspace <ABS_DIR> --output-format json`. Обхода context-bundle нет: `flag-waived` и `--force` / `--force-bypass-sasha-ok` не отменяют `emit-prompt`/`check`.
3. `kanban_heartbeat` на длинных `agent -p`; `session_id` → `kanban_comment` после первого вызова.
4. Промпт Cursor CLI — **одна роль, одна фаза:**

```
Одна роль: {role} ({model}). Только фаза {phase}. Чужие фазы не выполнять.
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
- `ORCH:shared-state` workspace: `dir:/home/tkachenkoav/WorkVault/Registries`.

### GATE:done — статус «готово»

Порядок воркера `GATE:done` (контракт AC-delivered):

1. `kanban_show()`.
2. Собрать отчёт AC-### → как тестировали (команда, лог/артефакт, результат).
3. Опубликовать отчёт в ДИАЛОГ Саши (не топик Monitoring :7, не личный DM оркестратору).
4. kanban_comment на карточку GATE:done: маркер `AC-delivered: dialog` + тело отчёта:
   ```
   AC-delivered: dialog
   ## Отчёт AC
   AC-001 → команда / лог / результат
   ```
   Маркер — ТОЛЬКО после реального поста в диалог. Не считать комментарий GATE:take-into-work
   (список AC-001) и подписку-уведомление Monitoring :7 доставкой отчёта.
5. Запустить preflight:
   `python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py --slug <slug> --case <DEV|CHANGE|BUGFIX|BUGFIX-LIGHT|CHANGE-LIGHT> [--flag-rev]`
6. exit 0 → `kanban_block(reason="review-required: ждать готово")`, complete запрещён (только Саша, never auto).
7. exit 1 или 2 → comment чек-лист stderr; `kanban_block`; **запрет** complete. reason: `review-required: preflight GATE:done` (exit 1) или `review-required: collapsed-chain` (exit 2).

**HITL never auto** (и в one-pass). Preflight exit 0 — необходимое, не достаточное. После `ORCH:shared-state` Сирень показывает итог в Telegram. Корень `DEV/<slug>` закрывается только после снятия `GATE:done` Сашей.

### Режим «делай в 1 проход»

Условия: мастер-ТЗ на диске; открытых вопросов нет; не обход diagnose-review.

Фраза **no-op для снятия AC-гейтов** (DKP v0.3.2): `GATE:take-into-work` / `GATE:done` — HITL never auto; `GATE:plan-approve` — always auto.

**Не auto:** `GATE:go`, `GATE:block-accept`. `GATE:diagnose-review` не обходится.

One-pass — **не** склейка нескольких **дочерних** фаз в одном промпте (`TZ:patch`+`HF:impl` — запрещено GLOSSARY). DX всегда карточки на канбане. Баг-триггер — с `BUG:diagnose`.

#### One-pass не плодит хвост (оркестратор, правило C)

**Когда:** режим «делай в 1 проход» и корень `DEV/<slug>` **сам** выполняет цикл — один воркер-корень, **несколько** вызовов `agent -p` по ролям (grok затем composer), не один промпт «ТЗ+код+тесты»; на корне — пометка one-pass.

**При постановке — не разворачивать полный хвост (~16 фаз):** вместе с корнем **не** создавать через `kanban_create` типовой граф `TZ-WRITE` (`TZ:stabilize` → … → `GATE:take-into-work`, см. `tz-workflow`) **плюс** `PLAN-IMPL-TAIL` + `HF-TAIL` (`HF:compress` → … → `ORCH:shared-state` → `GATE:done`, см. граф выше). Работа уже в корневом `agent -p`; дочерний граф после `complete` корня только дублирует её и съедает слот диспетчера.

Допустимые варианты:

- **Только корень** (предпочтительно для «корень сделал всё»).
- **Корень + гейты** без промежуточных TZ/HF-фаз (три гейта для audit: `GATE:plan-approve` always auto; `GATE:take-into-work` / `GATE:done` HITL never auto).
- **Минимальный граф** по кейсу (например `CHANGE-LIGHT` в GLOSSARY §5.1), если размер задачи совпадает — не полный DEV/CHANGE.

Полный хвост «на всякий случай» при корневом one-pass **запрещён**.

**Пошаговый one-pass** (редко, если хвост уже нужен по размеру): промежуточные фазы графа — **отдельные** `agent -p` на каждую карточку; гейты — auto-pass. Не путать с корневым one-pass.

**После `kanban_complete` корня** (корневой one-pass, артефакты на диске), если дочерние фазы **уже** были созданы (legacy, ошибка постановки):

1. `kanban_show` корня — список детей в `todo|ready|running|blocked`.
2. Каждую такую карточку **снять с диспатча без нового `agent -p`:** `kanban archive` (CLI/tool), либо при block — `kanban_unblock`, затем `kanban_complete` с comment `auto-archived: one-pass root done`.
3. `GATE:done` (если карточка есть): доставка отчёта AC в диалог Саши → комментарий c `AC-delivered: dialog` + тело отчёта → preflight → exit 0 → итог в TG, ждать Сашу; complete только после «готово»/дашборда.
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

ТЗ финализировано архитектором (скилл `tz-workflow`) и получено явное «берём в работу» от Саши. Реализация без финального ТЗ и явной команды — запрещена.

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
1. ТЗ согласовано + снят `GATE:take-into-work` («берём в работу»).
2. **Бэкап создан** (см. Блок 5).
3. `HF:plan` done + `GATE:plan-approve` auto (`auto-pass: architect-plan`).
4. Если план вводит новую сущность — согласование Саши получено отдельно от общего „берём в работу“.
5. **Канбан:** `GATE:plan-approve` = done/unblocked **или** auto-pass one-pass (режим «делай в 1 проход»).
6. **Auto-pass гейта ≠ «можно код сейчас».** Auto-complete `GATE:plan-approve` (one-pass) разрешает **диспетчеру** запустить `HF:impl`; координатору он не даёт права писать код вне очереди графа (XOR-канал, инвариант 8). Прямой impl координатора — только после `dispatch-paused` + off-board.

---

## Блок 3: Тестирование

- **Исполнитель** тестирует по плану архитектора
- **Мелкий баг** (≤2 файла, очевидная причина) → исполнитель чинит сам (1 попытка)
- **Крупный баг** → исполнитель фиксирует причину → **Саша решает** → архитектор делает hotfix-план → исполнитель применяет
- **Готово =** все точки проверки из плана архитектора пройдены (✅/❌)
- Статус «completed» на весь **граф** — только через снятие **`GATE:done`** Сашей (не приёмка `HF:plan`).

---

## Блок 4: Документирование

- ТЗ-файл в `TZ/<Tool>/<Tool>_TZ.md` пока инструмент используется. Архивация — только при выводе из эксплуатации.
- Исполнитель (`HF:docs-handoff`): текст скилла/ТЗ-секции **кроме** манифеста; `manifest_hints` в `kanban_complete.metadata`.
- **Манифест, digest/render, `restore-all-skills.sh`, `.env`/`jobs.json`/`entities.json` — только `ORCH:shared-state`** (оркестратор Сирень). Исполнитель не пишет в `EcosystemManifest.json`.
- **Скилл:** мелкая правка → архитектор сам; новый раздел → предлагает Саше.
- **MEMORY и скиллы:** см. `hermes-memory-hygiene`.

---

## Блок 5: Бэкапы и откат

- **Задачи архитектора:** бэкап всегда.
- **Задачи исполнителя:** только если затронут `config.yaml` или `jobs.json`.
- **Путь:** `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`.
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
2. `GATE:diagnose-review` — не ждать фразу Саши; `kanban_complete` — **архитектор вручную** после `REV:tz` (не HITL Саши).
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

- [ ] Явное «берём в работу» от Саши получено (Блок 0)
- [ ] `HF:plan` done + таблица IAC; `GATE:plan-approve` auto (Блок 1А)
- [ ] Бэкап создан в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (Блок 5)
- [ ] Модели: архитектор (cursor-grok-4.6-high) планирует, исполнитель (composer-2.5) пишет/тестирует
- [ ] Cron-субагент: критичные факты из MEMORY переданы явно в промпт
- [ ] Перед каждым side-effect — категория разрешающего сигнала определена (Блок 5Б)
- [ ] Статус «готово»: только Саша (`GATE:done` never auto, и в one-pass); preflight exit 0 необходим, не достаточен
- [ ] Все вызовы через Cursor CLI (`agent -p`)
- [ ] Полный документ в `agent -p`: `cat` без head/truncate, либо путь + «прочитай сам», либо явно «часть 1/N»; неполная копия не выдана как полная
- [ ] Новые сущности (если предлагались) — явно вынесены на согласование Саше, не внедрены самостоятельно.
- [ ] На любой баг-триггер первым tool-шагом было **kanban_create корня DEV/<slug> + BUG:diagnose в одном create-батче** (до agent -p), ретро-корень нет (инвариант 9)
- [ ] Если готовился вызвать agent -p / cronjob(repeat=1) / delegate_task на диагностику/план/реализацию бага — предварительно сделан kanban_show БУГ-карточки; карточка существует, иначе стоп
