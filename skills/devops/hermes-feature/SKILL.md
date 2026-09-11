---
name: hermes-feature
description: "Use when: полный цикл разработки фич/инструментов Hermes (ТЗ → код → тесты → документация) + диагностика багов + процедура починки питфоллов (pitfall-remediation-workflow). Triggers: разработай, новый инструмент, сделай, напиши код, реализуй, реализация, почини, починка, баг, ошибка, не работает, упало, разберись, исследуй, проанализируй, доработка, дорабатываем, MoveFrom*, обновить гермес, обновление гермес, hermes update, апгрейд, merge upstream, upstream merge, обновление версии."
version: 2.4.0
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

**ЖЁСТКОЕ ПРАВИЛО:** Архитектор default (Сирень) НЕ пишет ТЗ, планы, анализ самостоятельно в чате. Все задачи архитектора — ТОЛЬКО через Cursor CLI (`agent -p`). Текущий агент default (Сирень) координирует: вызывает Cursor CLI, передаёт контекст, принимает результат. Никаких попыток «написать план самому» без Cursor CLI.

## When to Use

- «разработай», «новый инструмент», «напиши код», «реализуй» — Блоки 0–4
- «ошибка», «баг», «не работает», «упало», «разберись», «починить» — Блок 7 (диагностика)
- «проанализируй», «исследуй», «найди», «посчитай», «сравни» — Блок 8 (исследование)
- «обновить гермес», «merge upstream» — Блок 1 + `references/hermes-upgrade-pattern.md`
- Задача с 3+ изменениями конфига/скиллов/инструментов — Блок 6А (QA)

Не для: правок стиля общения (см. `hermes-memory-hygiene`), простой рутины без ТЗ и вариантов.

**Связь с tz-workflow:** после согласования ТЗ и получения «берём в работу» — перейти к этому скиллу для реализации.

---

## Канбан-шаг

> DevKanbanPipeline (`TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md`). Все карточки `assignee=default`. Исполнители **не** пишут в `EcosystemManifest.json` / `entities.json` / `.env` / `jobs.json` — только `ORCH:shared-state`.

### Вход

- Любой HF `agent -p` без корня `DEV/<slug>` → **стоп** + оркестратор. Исключения DPK: `BRF:*` в TG; одношаговый ответ; RESEARCH.
- Вход в HF-ветку только если корень `DEV/<slug>` существует **и** `GATE:take-into-work` снят (Саша **или** `auto-pass: one-pass mode`). Иначе стоп + текст «нет „берём в работу“ / нет one-pass».
- `GATE:plan-approve` / `HF:backup` / `HF:impl`: если `HF:plan` не `done` → **стоп** (GLOSSARY инвариант 6). Не skip плана в one-pass.
- Off-board: **предусловие** — сначала вывести граф из диспатча (comment корня `dispatch-paused: off-board`, снять/не диспатчить remaining), затем retro-create + comment `done off-board, session ids`. Без `dispatch-paused` прямой `agent -p` на живой граф запрещён (инвариант 8).

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

### Блок 6В (багфикс)

При триггере «почини» — **до** TZ-ветки (кейс BUGFIX, GLOSSARY §2):

```
BUG:diagnose            # read-only, план П.1…П.N → _fix_plan_YYYYMMDD.md
GATE:diagnose-review    parents=[BUG:diagnose]   # review-required
→ далее TZ-WRITE(patch) → GATE:take-into-work → PLAN-IMPL-TAIL
```

Диагноз → `BUG:diagnose`; реализация → `HF:impl`. **`HF:fix` запрещён** (GLOSSARY §7). Инвариант: даже с известным root cause — нет перехода в hermes-feature без ТЗ-файла. Режим «1 проход» **не** обходит `GATE:diagnose-review`.

### Воркер HF-фаз

1. `kanban_show()` → сверка TZ version/mtime → `cd $HERMES_KANBAN_WORKSPACE`.
2. `kanban_heartbeat` на длинных `agent -p`; `session_id` → `kanban_comment` после первого вызова.
3. Промпт Cursor CLI — **одна роль, одна фаза:**

```
Одна роль: {role} ({model}). Только фаза {phase}. Чужие фазы не выполнять.
```

Роли/модели (PI B3): compress=оркестратор `deepseek-v4-flash-0731` (без Cursor; заключение t_645aa647); plan/patch/finalize=архитектор `cursor-grok-4.6-high` (CHANGE-LIGHT ≤3 файла: допустим `cursor-grok-4.6-medium`); REV=ревизор `claude-sonnet-5-medium`; impl/test/docs-handoff=исполнитель `composer-2.5`; backup=координатор `composer-2.5`; ORCH=оркестратор.

4. `kanban_complete` с metadata:

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

5. **Свёртка по `changed_files`:** на фазах **исполнителя** `HF:impl` и `HF:test`: если `changed_files` содержит путь `*_TZ.md` **или** `HF-plan*` → не complete, а `kanban_block(reason="review-required: collapsed-chain")`. Не применять к `HF:plan` (план — его артефакт) и к `HF:docs-handoff` (ТЗ — его артефакт).
6. **Машинный факт на диске для read-only фаз `HF:plan`/`REV:plan`** (контроль premature-impl, инвариант 8/Блок 1А). На фазе планирования целевой каталог скилла не должен получать impl-артефактов:
   - **до** `agent -p`: снимок `disk_before` целевого каталога скилла из ТЗ — `python3 ~/WorkVault/Registries/pipeline_hf_plan_diskfact.py snapshot --skill-dir <abs>` → `kanban_comment` (JSON).
   - после: `disk_after` + `diff --before --after`. Если `PREMATURE_IMPL` (появились `SKILL.md`/`scripts/`/`tests/`/`references`/`cli.py`, которых не было в before) → `kanban_block(reason="review-required: impl-before-plan-approve")`; self-report «каталог есть» при `disk_before.exists=false` = это же block.
   - Легальный черновик (каталог был в before, код в этой фазе не менялся) → complete ок; `HF:impl` затем сверяет с планом, не пишет второй раз.
   - В `kanban_complete.metadata` класть `disk_before`, `disk_after`, `premature_impl: false|true`, `allowed_writes` (план-файлы `HF-plan_*.md`).


Непустой `registry_touches` → `kanban_block(kind=capability, reason="executor touched shared state")`.

### GATE:plan-approve

- **Пошаговый ход** — второе «берём в работу» по плану 1А: `review-required: ждать «берём в работу» по плану`. Снятие: Telegram **или** дашборд.
- **Режим «делай в 1 проход»** — авто-проход: comment `auto-pass: one-pass mode` + `kanban_complete` без block.

### Блок 4 — владелец общего state

- Исполнитель = `HF:docs-handoff`: текст скилла/ТЗ-секции **кроме** манифеста; `manifest_hints` в metadata.
- Запись манифеста, digest/render, `restore-all-skills.sh`, `.env`/`jobs.json`/`entities.json` — **только** `ORCH:shared-state` (после `done` всех инструментных карточек).
- `ORCH:shared-state` workspace: `dir:/home/tkachenkoav/WorkVault/Registries`.

### GATE:done — статус «готово»

Порядок воркера `GATE:done`:

1. `kanban_show()`.
2. **Первый рабочий шаг:**  
   `python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py --slug <slug> --case <DEV|CHANGE|BUGFIX> [--flag-rev]`  
   (`--case` с карточки/корня).
3. exit 0 → пошагово: итог в TG, ждать Сашу (Telegram **или** дашборд); one-pass: comment `auto-pass: one-pass mode` + `kanban_complete` + закрытие корня.
4. exit 1 или 2 → comment чек-лист stderr; `kanban_block`; **запрет** complete. reason: `review-required: preflight GATE:done` (exit 1) или `review-required: collapsed-chain` (exit 2).

**Пошаговый ход:** только Саша (Telegram «готово» **или** дашборд). После `ORCH:shared-state` Сирень показывает итог в Telegram и просит подтвердить. Корень `DEV/<slug>` закрывается только после `GATE:done`.

**Скриптовый one-pass (A1):** в режиме «1 проход» `GATE:done` **не требует отдельного LLM-воркера** — preflight (`pipeline_gate_done_preflight.py --case ...`) уже скрипт и единственная проверка. `kanban_complete` выполняет тот же воркер, что закрыл родителя (или 10-строчный hook), с comment `auto-pass: one-pass mode`. Не разворачивать `agent -p` ради написания «отчёта» — итог в TG пишет оркестратор.

**Режим «делай в 1 проход»:** `GATE:done` auto-complete **только после** preflight exit 0 — comment `auto-pass: one-pass mode` + `kanban_complete` + закрытие корня.

### Режим «делай в 1 проход»

Условия: мастер-ТЗ на диске; открытых вопросов нет; не обход diagnose-review.

**One-pass = auto-complete трёх гейтов:** `GATE:take-into-work`, `GATE:plan-approve`, `GATE:done`. Auto ≠ skip: карточка гейта создаётся и complete'ится (`auto-pass: one-pass mode`). `GATE:done` auto **только после** preflight exit 0.

**Не auto:** `GATE:diagnose-review`, `GATE:go`, `GATE:block-accept`.

One-pass — **не** склейка нескольких **дочерних** фаз в одном промпте на одной карточке (`TZ:patch`+`HF:impl` и т.п. — запрещено GLOSSARY). Это авто-гейты, а не «пропуск» обязательной работы.

#### One-pass не плодит хвост (оркестратор, правило C)

**Когда:** режим «делай в 1 проход» и корень `DEV/<slug>` (типично `CHANGE` / `SKILL-CHANGE` / малый `DEV`) **сам** выполняет цикл целиком — один воркер на корне закрывает ТЗ-правку, код, тесты, docs-handoff; на корне или в comment — `auto-pass: one-pass mode` / явная пометка one-pass от Саши.

**При постановке — не разворачивать полный хвост (~16 фаз):** вместе с корнем **не** создавать через `kanban_create` типовой граф `TZ-WRITE` (`TZ:stabilize` → … → `GATE:take-into-work`, см. `tz-workflow`) **плюс** `PLAN-IMPL-TAIL` + `HF-TAIL` (`HF:compress` → … → `ORCH:shared-state` → `GATE:done`, см. граф выше). Работа уже в корневом `agent -p`; дочерний граф после `complete` корня только дублирует её и съедает слот диспетчера.

Допустимые варианты:

- **Только корень** (предпочтительно для «корень сделал всё»).
- **Корень + гейты** без промежуточных TZ/HF-фаз (три гейта для audit, сразу `auto-pass: one-pass mode`).
- **Минимальный граф** по кейсу (например `CHANGE-LIGHT` в GLOSSARY §5.1), если размер задачи совпадает — не полный DEV/CHANGE.

Полный хвост «на всякий случай» при корневом one-pass **запрещён**.

**Пошаговый one-pass** (редко, если хвост уже нужен по размеру): промежуточные фазы графа — **отдельные** `agent -p` на каждую карточку; гейты — auto-pass. Не путать с корневым one-pass.

**После `kanban_complete` корня** (корневой one-pass, артефакты на диске), если дочерние фазы **уже** были созданы (legacy, ошибка постановки):

1. `kanban_show` корня — список детей в `todo|ready|running|blocked`.
2. Каждую такую карточку **снять с диспатча без нового `agent -p`:** `kanban archive` (CLI/tool), либо при block — `kanban_unblock`, затем `kanban_complete` с comment `auto-archived: one-pass root done`.
3. `GATE:done` (если карточка есть): `pipeline_gate_done_preflight.py` → exit 0 → `auto-pass: one-pass mode` + `kanban_complete` + закрытие корня.
4. Comment на корне: `one-pass tail archived: <N> cards` (audit).

**XOR-канал координатора (влечён из инварианта 8, GLOSSARY §5.2):** пока граф `DEV/<slug>` диспатчится (есть дети `todo/ready/running`), координатор **не** вызывает свой `agent -p` на фазы графа — гейты авто-проходятся, фазы выполняет диспетчер. Прежде чем сделать любой **ручной** cursor-cli по слагу:
1. `kanban_show` корня: дети в `todo|ready|running` → канал `kanban`, свой вызов **стоп** (ждать очередь / auto-pass гейтов).
2. Нужен прямой ход (crash-spawn, спешка) → **сначала** вывести граф: comment корня `dispatch-paused: off-board`, снять/не диспатчить remaining → потом свои вызовы + retro-create `done off-board, session ids`, **и только при снятом `GATE:plan-approve`** (для кодосодержащих фаз). Иначе живёт двойной канал (воркер + координатор) на одной фазе — запрещено.

---

## Модели (Cursor CLI) — раздельные задачи по шагам

**Инвариант:** один вызов `agent -p` = одна модель = одна роль. Сирень координирует цепочку из 4 отдельных задач Cursor — **не смешивать** модели в одном промпте.

| Шаг | Роль | Модель | Блок |
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

---

## Блок 0: ТЗ

ТЗ финализировано архитектором (скилл `tz-workflow`) и получено явное «берём в работу» от Саши. Реализация без финального ТЗ и явной команды — запрещена.

---

## Блок 1: Анализ вариантов

**Шаг 0 (оркестратор, без Cursor):** компрессия master-ТЗ по `tz-compressor-prompt.md` на `deepseek-v4-flash-0731` — full-coverage 3–5 КБ, без кэша.

**Шаг 1 (отдельный Cursor, архитектор):** анализ вариантов на входе digest + экстракты Шага 0.

- **Критерии:** токены / безопасность / консистентность / поддерживаемость + специфичные для задачи.
- **Количество:** 2-3 лучших; слабые архитектор отсеивает сам.
- **Reuse-first (см. references/reuse-first-rule.md):** варианты формируются через существующие USERTOOLS/applications/реестры; новое приложение/инструмент — только если существующие не закрывают, отдельным пунктом «требует согласования Саши».
- **Подача:** сначала рекомендация с обоснованием → остальные кратко.
- **Варианты только цифрами 1/2/3**, никогда не A/B/C.
- После выбора: уточняющие вопросы **по одному** → ждать «берём в работу».

**Completion criterion:** Саша сказал «берём в работу» по конкретному варианту.

---

## Блок 1А: Планирование *(до Блока 2)*

**Архитектор составляет пофайловый план:**
- Какие файлы создать / изменить
- Какие функции / классы / методы добавить
- Какие тесты написать
- Если план вводит новую сущность — отдельная строка „Новая сущность X — требует согласования Саши“ до Блока 2; без явного ОК реализация новой сущности не начинается.
- Промежуточные точки проверки с критериями

**ТЗ-файл только для задач с Python-кодом.** Для скиллов, конфигов, memory-правок — план в чате.

**Исполнитель проходит промежуточные точки молча** — без отчётов Саше.

**Перед «берём в работу»** — проверить ключевые фактические утверждения плана напрямую (`which`, `read_file`).

**⚠️ Неожиданный каталог скилла на диске = аномалия, не «сверить и дописать».** Если в фазе `HF:plan`/`REV:plan` (read-only по коду скилла) в workspace уже появились `SKILL.md`/`scripts/`/`tests/`, которых не было в `disk_before` — это impl-before-plan-approve (иначе параллельный процесс). Зафиксировать `premature_impl: true` в comment, `kanban_block("review-required: impl-before-plan-approve")`, НЕ копировать/дорабатывать чужой код в фазе планирования.

**Устойчивость к сбою:** `## Прогресс выполнения` с чекбоксами в файле плана.

**Completion criterion:** Саша сказал «берём в работу» по пофайловому плану.

---

## Блок 2: Реализация

### Кто пишет
- **Исполнитель (composer-2.5)** — пишет код по плану архитектора
- **Архитектор (cursor-grok-4.6-high) (fallback)** — только если исполнитель не справился: архитектурный тупик или повторяющиеся необъяснимые ошибки. Исполнитель даёт вывод → **Саша решает** запускать ли архитектора.

**Мелкое отклонение** (≤2 файла, не меняет архитектуру) → исполнитель сам.
**Крупное отклонение** → исполнитель стопится → архитектор делает доплан → исполнитель продолжает.
**Системный блокер** (пакеты, sudo) → исполнитель стопится → вопрос Саше напрямую.

### Чеклист перед первой строкой кода
1. ТЗ согласовано + явное «берём в работу».
2. **Бэкап создан** (см. Блок 5).
3. Пофайловый план архитектора согласован.
4. Если план вводит новую сущность — согласование Саши получено отдельно от общего „берём в работу“.
5. **Канбан:** `GATE:plan-approve` = done/unblocked **или** auto-pass one-pass (режим «делай в 1 проход»).
6. **Auto-pass гейта ≠ «можно код сейчас».** Auto-complete `GATE:plan-approve` (one-pass) разрешает **диспетчеру** запустить `HF:impl`; координатору он не даёт права писать код вне очереди графа (XOR-канал, инвариант 8). Прямой impl координатора — только после `dispatch-paused` + off-board.

---

## Блок 3: Тестирование

- **Исполнитель** тестирует по плану архитектора
- **Мелкий баг** (≤2 файла, очевидная причина) → исполнитель чинит сам (1 попытка)
- **Крупный баг** → исполнитель фиксирует причину → **Саша решает** → архитектор делает hotfix-план → исполнитель применяет
- **Готово =** все точки проверки из плана архитектора пройдены (✅/❌)
- Статус «completed» на весь план ставит только Саша.

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

**Пропускается** если архитектор уже написал план с тестами (Блок 1А) и исполнитель прошёл его (Блок 3).

**Применяется** для изменений БЕЗ предварительного плана архитектора (срочный hotfix, ручная правка).

Процесс: крон архитектора собирает чек-лист → исправить ❌ → повторить (макс 3 попытки) → все ✅ = короткий отчёт. Остались ❌ → откат + доклад.

---

## Блок 6Б: Делегирование субагентов

| Задача | Модель | Инструмент | Таймаут |
|---|---|---|---|
| Архитектор: ТЗ / план / анализ | `cursor-grok-4.6-high` | `cronjob(repeat=1)` | — |
| Архитектор: реализация (fallback) | то же | `cronjob(repeat=1)` | — |
| Исполнитель: реализация >5 мин | `composer-2.5` | `cronjob(repeat=1)` | — |
| Исполнитель: короткая <5 мин | `composer-2.5` | `delegate_task` | 300с |
| Координатор: справочный | `composer-2.5` | `delegate_task` | 120с |

### Toolsets

| Задача | enabled_toolsets |
|---|---|
| Архитектор: ТЗ / план | `["file", "terminal"]` |
| Исполнитель: реализация | `["file", "terminal"]` |
| Исполнитель: тестирование | `["file", "terminal"]` |
| Исследование с web | `["file", "terminal", "web"]` |

### Что передавать в промпт

1. Роль и среда, абсолютные пути
2. Полный текст ТЗ или плана (не ссылку)
3. Граница автономности: «механическое — делай сам; семантическое — СТОП»
4. Формат отчёта, явные запреты
5. **Критичные факты из MEMORY — явно в промпт.** Cron-сессии НЕ получают MEMORY/USER PROFILE.
6. **Reuse-first (см. references/reuse-first-rule.md):** субагент не внедряет новые сущности без явного согласования Саши.

Полные правила: `references/subagent-rules.md`.

---

## Блок 6В: Диагностика перед починкой

Когда «что-то не работает» — **не чинить сразу**. Порядок:

1. **Крон архитектора только на диагностику** (только чтение, запрет правок) → root cause, план П.1…П.N
2. Саша просматривает план
3. Крон исполнителя реализует по плану

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

**Модель:** координатор собирает данные → исполнитель анализирует в рамках одного инструмента → архитектор для интеграционных вопросов.

**Алгоритм:** Scope → Сбор (session_search, grep, API только чтение) → Анализ (таблица) → Рекомендации (2-3 варианта с оценкой).

**НЕ делать:** не менять код/конфиги/скиллы, не делать выводы без данных, не запускать API без ОК.

---

## Паттерн обновления Hermes (merge upstream)

Для обновления Hermes из upstream — загрузить `references/hermes-upgrade-pattern.md`.
Там: стратегия MERGE, risk zones, питфоллы (venv/pytest, index.lock, config migration), бэкап-конвенция, upstream turbulence signals.

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
- [ ] Пофайловый план архитектора согласован до первой строки кода (Блок 1А)
- [ ] Бэкап создан в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (Блок 5)
- [ ] Модели: архитектор (cursor-grok-4.6-high) планирует, исполнитель (composer-2.5) пишет/тестирует
- [ ] Cron-субагент: критичные факты из MEMORY переданы явно в промпт
- [ ] Перед каждым side-effect — категория разрешающего сигнала определена (Блок 5Б)
- [ ] Статус «готово»: пошагово — только Саша (Блок 3); в режиме «делай в 1 проход» — auto-complete трёх гейтов после preflight exit 0
- [ ] Все вызовы через Cursor CLI (`agent -p`)
- [ ] Новые сущности (если предлагались) — явно вынесены на согласование Саше, не внедрены самостоятельно.
