---
type: hf-plan
title: "Пофайловый план контура B chain-enforcement (HF:plan, 08.09)"
slug: chain-enforcement
case: CHANGE
phase: HF:plan
date: 2026-09-08
status: draft-plan
author: архитектор (cursor-grok-4.6-high, HF:plan)
source_tz:
  - TZ/GLOSSARY.md v0.2.2 §5.2
  - TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md v0.2.3 (Preflight GATE:done, off-board)
  - TZ/ProcessImprovement/ProcessImprovement_TZ.md v0.4.1 секция «Контур B» B1–B4
source_skills:
  - hermes-workspace/skills/devops/tz-workflow/SKILL.md 2.1.1
  - hermes-workspace/skills/devops/hermes-feature/SKILL.md 2.2.1
source_appendix: TZ/ProcessImprovement/appendix_exchange-finish-reliability_20260908.md (часть B)
executor: composer-2.5
---

# HF:plan — контур B (chain-enforcement)

CHANGE: скрипт preflight + правки двух скиллов. Код в этом вызове не писать. Объект для `GATE:plan-approve`. Канон — GLOSSARY §5.2, DevKanbanPipeline v0.2.3, ProcessImprovement «Контур B». Не выдумано.

Исполнитель идёт B2 → скиллы → HF:test сверху вниз. Промежуточные точки — молча. Новых сущностей нет. Новый скилл не заводится.

---

## 0. Факт на диске (08.09) — не переписывать как «сделано»

B1 (GLOSSARY §5.2, DKP preflight/off-board) **уже на диске**. HF:impl контура B их **не** трогает.

| Артефакт | На диске 08.09 | Цель HF:impl | Делать? |
|---|---|---|---|
| `TZ/GLOSSARY.md` | **0.2.2** (§5.2 есть) | 0.2.1 в ТЗ 0.4.1 — уже перекрыто | **нет** |
| `TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` | **0.2.3** (Preflight + `flag-waived`) | 0.2.2 в ТЗ 0.4.1 — уже перекрыто | **нет** |
| `tz-workflow/SKILL.md` | **2.1.1** | **2.2.0** | да |
| `hermes-feature/SKILL.md` | **2.2.1** | **2.3.0** | да |
| `~/WorkVault/Registries/pipeline_gate_done_preflight.py` | **есть** (~12 КБ), расходится с каноном | переписать под §5.2/DPK | да (не точечный фикс) |
| pytest скрипта | нет | `test_pipeline_gate_done_preflight.py` рядом | да (HF:test) |

Живой граф slug `chain-enforcement`: корень **`CHANGE/chain-enforcement`** (не канон DPK «`DEV/<slug>`»). Скрипт ищет **`DEV/<slug>`** — как DPK/PI B2/B4, не как этот граф.

Заготовка скрипта (не канон, при HF:impl заменить целиком):

- CLI: позиционный `slug`, нет обязательного `--slug`; `--case` без `BUGFIX`; `--flag-rev` opt-in; есть `--no-graph` (в каноне нет).
- Корень: поиск `CHANGE/<slug>` и `DEV/<slug>` — DPK: только `DEV/<slug>`.
- `MANDATORY_PHASES` один набор на все кейсы; в наборе `GATE:done` (циклично: preflight — **до** complete гейта).
- Гейты: нет правила «done **или** comment `auto-pass: one-pass mode`».
- План: glob `~/WorkVault/Registries/HF-plan_<slug>*.md` — канон артефакта: `TZ/<Tool>/HF-plan_<slug>*.md` (этот файл; прецедент exchange).
- ТЗ-маркер: ищет «на диске: нет» в **body карточек** docs-handoff, не в `*_TZ.md` на диске; нет маркера `ожидает HF:impl`.
- Свёртка: колонка `task_runs.session_id` **отсутствует** в схеме; `tasks.session_id` — сессия воркера Hermes, **общая на граф** (ложный collapsed). Канон: `cursor_session_ids` (metadata complete / comment), скоуп = reach графа.
- exit 2 на свёртку не ставится (DPK: 2 = collapsed-chain **или** ошибка вызова).

---

## 1. B2 — скрипт `pipeline_gate_done_preflight.py`

**Файл:** `~/WorkVault/Registries/pipeline_gate_done_preflight.py`  
**Создать:** `~/WorkVault/Registries/test_pipeline_gate_done_preflight.py` (HF:test, см. §4)  
**Не трогать:** `~/WorkVault/Registries/render_manifest.py`, `entities.json`, `EcosystemManifest.json`.

### 1.1 Интерфейс

Канон вызова (DPK + запрос фазы):

```
python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py \
  --slug <slug> \
  --case DEV|CHANGE|BUGFIX \
  [--flag-rev]
```

| Аргумент | Обязателен | Смысл |
|---|---|---|
| `--slug` | да | хвост корня `DEV/<slug>` (DPK «Именование») |
| `--case` | да | набор фаз GLOSSARY §5.2: `DEV` / `CHANGE` / `BUGFIX` |
| `--flag-rev` | нет | включить `REV:tz` в обязательный набор, если кейс его не требует (BUGFIX таблица: REV OFF при ≤3 файлах). Для `DEV`/`CHANGE` REV и так в наборе (default ON) — флаг идемпотентен |

Нет в каноне — **не** делать: `--no-graph`, позиционный slug без `--slug`, `--json` как требование (stderr-чек-лист достаточен).

ENV для тестов (как у заготовки): `HERMES_KANBAN_DB` — путь к sqlite; иначе `~/.hermes/kanban.db`.

**Кто вызывает / первый шаг воркера `GATE:done`:**

1. Воркер карточки `GATE:done` (скилл `hermes-feature`) **до** любого `kanban_complete` / auto-pass.
2. Сирень перед complete `GATE:done` (DPK: «Сирень перед `kanban_complete` карточки `GATE:done`»).
3. Fallback по имени — `dev-pipeline-reliability` (DPK); **новый скилл не создавать**.

После `ORCH:shared-state` done: запуск скрипта. `exit 0` → можно complete гейта (пошагово — после Саши; one-pass — auto-complete `auto-pass: one-pass mode`). `exit ≠ 0` → `GATE:done` **запрещён**: `kanban_comment` с чек-листом stderr + `kanban_block`. Авто-крон скрипта **нет**.

### 1.2 Read-only и лог

- Открытие: `sqlite3.connect("file:<path>?mode=ro", uri=True)`. Никаких INSERT/UPDATE/WAL-checkpoint. Схему SQLite **не** менять.
- Таблицы (факт `kanban.db`): `tasks`, `task_links`, `task_comments`, `task_runs`, `task_events`. Колонки `tasks`: `id,title,body,status,result,session_id,idempotency_key,…`. `task_runs.metadata` TEXT JSON. **`task_runs.session_id` нет.**
- Лог: `logging` → **stderr**, уровень INFO. Каждая проверка — строка `[OK]` / `[FAIL]` + текст. Итог PASS/FAIL — **stdout**. Чек-лист при exit 1 — тот же stderr (его копируют в `kanban_comment`).

### 1.3 Наборы фаз §5.2 (не один хардкод)

Развёртка блоков — GLOSSARY §5.1; skip — только таблица §5.2 или `flag-waived: Sasha`.

**Общий хвост `PLAN-IMPL-TAIL` + `HF-TAIL` (DEV, CHANGE, BUGFIX):**

`HF:plan` → [`REV:plan`] → `GATE:plan-approve` → `HF:backup` → `HF:impl` → `HF:test` → `HF:docs-handoff` → `ORCH:shared-state`

`GATE:done` — **текущая** карточка; в «обязательно done» **не** входит (иначе цикл). Parent `ORCH:shared-state` — входит.

**TZ-WRITE по `--case`:**

| `--case` | TZ-WRITE | Обязательно done | Skip / opt |
|---|---|---|---|
| `DEV` | `new` | `TZ:patch`, `TZ:finalize`, `GATE:take-into-work` + хвост выше; `TZ:stabilize`/`TZ:compress` если карточка есть | `HF:compress` opt; `REV:tz` в наборе (default ON) |
| `CHANGE` | `full` | `TZ:stabilize`, `TZ:compress`, `TZ:patch`, `TZ:finalize`, `GATE:take-into-work` + хвост (appendix: TZ-WRITE(full) = stabilize→compress→patch→REV→finalize) | `HF:compress` opt |
| `BUGFIX` | `patch` | `BUG:diagnose`, `GATE:diagnose-review` (DX, **не** auto), `TZ:patch`, `TZ:finalize`, `GATE:take-into-work` + хвост; `HF:compress` **не** требовать | `HF:compress` skip; `REV:tz` не в наборе, пока нет `--flag-rev` |

Опциональные карточки (`HF:compress`, `REV:plan`, `TZ:stabilize`/`TZ:compress` вне CHANGE-full): если **есть** в графе — status должен быть `done` (или off-board complete). Нет в графе — не fail.

**Гейты `GATE:take-into-work` и `GATE:plan-approve`:** status `done` **или** comment/result содержит ровно `auto-pass: one-pass mode` (DPK).  
**`GATE:diagnose-review` / `GATE:go` / `GATE:block-accept`:** auto-pass **не** засчитывается (GLOSSARY инвариант 3).

**Off-board:** status `done` + comment с `done off-board, session ids` — валидный complete, не замена графа.

**Парсинг title:** канон `PREFIX:фаза`; факт доски — `HF:plan — chain-enforcement (контур B)` и корень `DEV/<slug>`. Фаза = подстрока до ` — ` / ` – `; корень = точное `title == "DEV/" + slug`.

### 1.4 Пять проверок (порядок = DPK)

**(1) Корень существует.**  
`tasks.title = 'DEV/' || slug`. Нет строки → fail (exit 1). Не archived как единственный след без детей — fail. Не искать `CHANGE/<slug>` как канон.

**(2) Все фазы §5.2 для `--case` имеют done.**  
Reach от корня по `task_links` (parent→child). Для каждой обязательной фазы: есть карточка и `status=done`, **кроме** гейтов one-pass (см. выше). Нет фазы в reach → fail. `GATE:done` не требовать done.

**(3) Артефакты.**  
- План `HF:plan`: на диске файл `HF-plan_<slug>*.md` под `~/WorkVault/Hermes-Backlog/TZ/` (этот план: `TZ/ProcessImprovement/HF-plan_chain-enforcement_20260908.md`). Fallback DPK: план в comment карточки `HF:plan` (непустой путь/текст плана). Нет файла и нет плана в comment → fail.  
- ТЗ: **если** `HF:docs-handoff` в графе `done` — в файлах `*_TZ.md` из `changed_files` / `tz_path` metadata этой карточки (не глобальный grep всего инвентаря) нет подстрок `на диске: нет` и `ожидает HF:impl` (DPK). Если docs-handoff ещё не done — эту ветку не проверять (фаза (2) уже завалит).

**(4) REV.**  
Если `REV:tz` в обязательном наборе (DEV/CHANGE всегда; BUGFIX — только `--flag-rev` **или** карточка уже есть в графе): карточка `done` **или** comment содержит `flag-waived: Sasha` (GLOSSARY §5.2 = равно REV done). Если прогон ревизора был — в comment/metadata `cursor_session_ids` sonnet; отсутствие session при waive — не fail (waive без прогона). Нет ни done, ни маркера → fail (exit 1).

**(5) Эвристика свёртки.**  
По **reach графа**: собрать `cursor_session_ids` из `task_runs.metadata` JSON, `tasks.result` JSON, comments (явный `session_id=` / UUID после «session»). **Не** использовать `tasks.session_id` (Hermes worker). Роль фазы — таблица PI B3 / GLOSSARY §3:

| Фаза | Роль |
|---|---|
| `TZ:compress`, `HF:compress` | компрессор |
| `TZ:patch`, `TZ:finalize`, `HF:plan` | архитектор |
| `REV:tz`, `REV:plan` | ревизор |
| `HF:impl`, `HF:test`, `HF:docs-handoff` | исполнитель |
| `TZ:stabilize`, `HF:backup` | координатор |
| `ORCH:shared-state` | оркестратор |
| `GATE:*`, `BUG:diagnose` | нет роли для свёртки |

Один и тот же cursor `session_id` на **двух фазах разных ролей** → collapsed → **exit 2**. Гейты в эвристику не входят.

### 1.5 Exit

| Код | Когда |
|---|---|
| **0** | все пять проверок OK |
| **1** | чек-лист: нет корня / фазы / артефакты / REV (не свёртка) |
| **2** | collapsed-chain **или** ошибка вызова (нет БД, нет `--slug`/`--case`, не открыть sqlite, нет таблицы `tasks`) |

`sys.exit` только этими кодами. stdout не смешивать с чек-листом.

### 1.6 Шаги исполнителя (B2)

1. Заменить тело `pipeline_gate_done_preflight.py` (не патчить заготовку кусками).
2. argparse: только канон §1.1.
3. Функции: `connect_ro`, `find_root`, `collect_graph`, `phase_of_title`, `gate_ok`, `rev_ok`, `artifacts_ok`, `collapse_ok`, `main`.
4. Не писать в Registries ничего кроме этого файла (+ тест в HF:test).

**Проверка B2 (статическая, до HF:test):**

- [ ] `grep --slug` в скрипте — есть; позиционный slug как единственный вход — нет
- [ ] `mode=ro` / `uri=True` есть
- [ ] нет INSERT/UPDATE/CREATE
- [ ] строки `flag-waived: Sasha`, `auto-pass: one-pass mode`, `на диске: нет`, `ожидает HF:impl`
- [ ] `DEV/` + slug; нет канонизации `CHANGE/` как корня
- [ ] `GATE:done` не в mandatory-done
- [ ] свёртка не читает `tasks.session_id` как cursor session
- [ ] `sys.exit` 0/1/2 по таблице

---

## 2. Правки `tz-workflow` 2.1.1 → 2.2.0

**Файл:** `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md`  
**Только этот файл.** Не трогать `references/*`.

Frontmatter `version: 2.1.1` → **`2.2.0`**.

### 2.1 Запрет «напиши ТЗ целиком» одним промптом

Источник: appendix audit — «TZ-WRITE(full) свёрнут в 1 вызов исполнителя»; GLOSSARY §5.1: «Блок не схлопывается в один промпт»; §7: «одним заходом» ≠ один `agent -p`.

**Куда:** раздел «Модели (Cursor CLI) — раздельные задачи», сразу после инварианта «один вызов `agent -p` = одна модель = одна роль».

**Текст-норматив (смысл, не вольность):**

- Запрещены промпты вида «напиши ТЗ целиком», «весь TZ-WRITE одним `agent -p`», склейка `TZ:compress`+`TZ:patch`+`TZ:finalize` (и тем более с ролью исполнителя).
- `TZ-WRITE(mode)` = отдельные карточки и отдельные `agent -p` по §5.1.
- Один вызов закрывает **ровно одну** фазу из `{TZ:stabilize, TZ:compress, TZ:patch, REV:tz, TZ:finalize}`.

### 2.2 Чек-лист TZ-WRITE(full)

**Куда:** новый подраздел в «Канбан-шаг» (после графа TZ-фаз, до «Шаги 0–4»). Режим `full` = кейс CHANGE (GLOSSARY §2).

Чек-лист (все пункты — отдельные карточки; parents как в текущем графе скилла):

- [ ] `TZ:stabilize` done (path, `version`, `mtime` в metadata)
- [ ] `TZ:compress` done (экстракт 3–5 КБ, без кэша, модель компрессора `deepseek-v4-flash-0731`, без Cursor)
- [ ] `TZ:patch` done (архитектор `cursor-grok-4.6-high`, `--resume` своей сессии)
- [ ] `REV:tz` done **или** comment `flag-waived: Sasha` (default ON для CHANGE)
- [ ] `TZ:finalize` done (запись `TZ/<Tool>/<Tool>_TZ.md` + инвентарь) — **только после** родителей ниже
- [ ] ни один из шагов не выполнен «тем же» `agent -p`, что соседний

Для `TZ-WRITE(new)` / `(patch)` — тот же запрет склейки; набор карточек по §5.2 (stabilize/compress в скобках §5.1).

### 2.3 `TZ:finalize`: parents done

**Куда:** абзац «`TZ:finalize` — роль архитектора…» + протокол воркера шагов 0–4.

Перед записью master-ТЗ воркер `TZ:finalize`:

1. `kanban_show` текущей и родителей.
2. Parents: `TZ:compress` done, `TZ:patch` done, и (`REV:tz` done **или** waive). Если REV-карточки нет и кейс DEV с opt REV — parent = `TZ:patch` (как DPK граф `parents=[REV:tz|TZ:patch]`).
3. Любой parent не done → **стоп**, не писать ТЗ (карточка не complete).
4. Metadata complete: `role=архитектор`, `model=cursor-grok-4.6-high`, `cursor_session_ids`, `tz_path`/`tz_version`/`tz_mtime` (PI B3).

Усилить уже существующее: TZ `agent -p` без корня `DEV/<slug>` → стоп (не создавать корень «по памяти»).

**Проверка скилла tz-workflow:**

- [ ] frontmatter `2.2.0`
- [ ] grep: `напиши ТЗ целиком` **как запрет**; `TZ-WRITE(full)`; `flag-waived: Sasha`
- [ ] finalize: явное «parents compress+patch+REV done»
- [ ] нет нового скилла; нет правок ядра

---

## 3. Правки `hermes-feature` 2.2.1 → 2.3.0

**Файл:** `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md`  
**Только этот файл.** Не трогать `references/*`.

Frontmatter `version: 2.2.1` → **`2.3.0`**.

### 3.1 One-pass = три гейта (не склейка)

**Куда:** «Режим «делай в 1 проход»» (сейчас: «цепочка HF:* → ORCH:shared-state одним заходом») и «GATE:done» one-pass абзац; verification checklist пункт «Статус готово».

Канон GLOSSARY §5.2 / DPK п.8:

- One-pass = auto-complete **трёх** гейтов: `GATE:take-into-work`, `GATE:plan-approve`, `GATE:done`.
- `GATE:done` auto **только после** preflight **exit 0**.
- Не auto: `GATE:diagnose-review`, `GATE:go`, `GATE:block-accept`.
- Auto ≠ skip: карточка гейта создаётся и complete'ится (`auto-pass: one-pass mode`); родительские фазы выполняются отдельными `agent -p`.
- Снять формулировку «одним заходом» / «одним `agent -p` исполнителя» как смысл one-pass (корень сбоя 08.09, appendix B).

### 3.2 `GATE:done` = вызов preflight (первый шаг воркера)

**Куда:** заменить/дописать «### GATE:done — статус «готово»».

Порядок воркера `GATE:done`:

1. `kanban_show()`.
2. **Первый рабочий шаг:**  
   `python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py --slug <slug> --case <DEV|CHANGE|BUGFIX> [--flag-rev]`  
   (`--case` с карточки/корня; CHANGE этого контура = `CHANGE`).
3. exit 0 → пошагово: итог в TG, ждать Сашу (Telegram **или** дашборд); one-pass: comment `auto-pass: one-pass mode` + `kanban_complete` + закрытие корня.
4. exit 1 или 2 → comment чек-лист stderr; `kanban_block`; **запрет** complete. reason: `review-required: preflight GATE:done` (exit 1) или `review-required: collapsed-chain` (exit 2).

### 3.3 Вход HF без корня / без `HF:plan` done → стоп

**Куда:** «### Вход» (сейчас строка «Если HF-фаз ещё нет — создать HF:*…» — это мягкое «создать если нет», PI B4 **запрещает**).

Заменить на:

- Любой HF `agent -p` без корня `DEV/<slug>` → **стоп** + оркестратор. Исключения DPK: `BRF:*` в TG; одношаговый ответ; RESEARCH.
- Вход в HF-ветку только если корень есть **и** `GATE:take-into-work` снят (Саша или auto-pass).
- `GATE:plan-approve` / `HF:backup` / `HF:impl`: если `HF:plan` не `done` → **стоп** (GLOSSARY инвариант 6). Не skip плана в one-pass.
- Off-board: только retro-create + comment `done off-board, session ids`.

### 3.4 Промпт «одна роль, чужие фазы не выполнять»

**Куда:** «Воркер HF-фаз» + паттерн вызова Cursor CLI. Шаблон PI B3 **дословно по смыслу:**

```
Одна роль: {role} ({model}). Только фаза {phase}. Чужие фазы не выполнять.
```

Роли/модели — таблица PI B3 (compress=компрессор deepseek-v4-flash-0731 без Cursor; plan/patch/finalize=архитектор grok-high; REV=ревизор sonnet-5-medium; impl/test/docs-handoff=исполнитель composer-2.5).

Metadata `kanban_complete` дополнить полями PI B3: `role`, `model`, `cursor_session_ids` (к уже существующим `changed_files`, `tz_path`/`version`/`mtime`, `pipeline_schema`).

### 3.5 Свёртка по `changed_files`

**Куда:** «Воркер HF-фаз» после JSON metadata.

На фазах **исполнителя** `HF:impl` и `HF:test`: если `changed_files` содержит путь `*_TZ.md` **или** `HF-plan*` → не complete, а `kanban_block(reason="review-required: collapsed-chain")`.  
Не применять к `HF:plan` (план — его артефакт) и к `HF:docs-handoff` (ТЗ — его артефакт).

**Проверка скилла hermes-feature:**

- [ ] frontmatter `2.3.0`
- [ ] grep `pipeline_gate_done_preflight.py`; `auto-pass: one-pass mode`; `collapsed-chain`
- [ ] нет фразы «одним заходом» как описание one-pass (или явно = auto-гейты, не один `agent -p`)
- [ ] нет «создать HF если нет»
- [ ] «Одна роль» / «Чужие фазы не выполнять»
- [ ] вход без `HF:plan` done → стоп

---

## 4. Критерии приёмки HF:test (скрипт)

**Файл теста:** `~/WorkVault/Registries/test_pipeline_gate_done_preflight.py`  
**Прогон:** `cd ~/WorkVault/Registries && python3 -m pytest test_pipeline_gate_done_preflight.py -q`  
Живой `~/.hermes/kanban.db` **не** писать: фикстура — временный sqlite (схема `tasks`/`task_links`/`task_comments`/`task_runs` как на ВМ) + `HERMES_KANBAN_DB` + tmp `TZ/` с `HF-plan_<slug>*.md` и `*_TZ.md`.

Минимальная схема фикстуры: колонки, которые читает скрипт (`id,title,body,status,result,session_id` у tasks; `parent_id,child_id`; comments `task_id,body`; runs `task_id,metadata`).

| # | Сценарий | Ожидаемый exit |
|---|---|---|
| T0 | `--help` / нет `--slug` | **2** |
| T1 | Готовый граф `DEV/ready-slug`, `--case CHANGE`: все обязательные фазы done, план на диске, ТЗ без маркеров, `REV:tz` done, разные cursor session на ролях | **0** |
| T2 | Нет корня `DEV/<slug>` | **1** |
| T3 | Корень есть, нет `HF:plan` done | **1** |
| T4 | Фазы done, плана нет (и нет в comment) | **1** |
| T5 | `HF:docs-handoff` done, в `*_TZ.md` есть `на диске: нет` | **1** |
| T6 | `REV:tz` не done, comment `flag-waived: Sasha` (без `--flag-rev` на CHANGE всё равно REV в наборе) | **0** |
| T7 | CHANGE, нет REV done и нет waive | **1** |
| T8 | Один cursor `session_id` на `HF:plan` (архитектор) и `HF:impl` (исполнитель) | **2** |
| T9 | Нет файла БД / не sqlite | **2** |
| T10 | Гейт `GATE:plan-approve` не done, но comment `auto-pass: one-pass mode` — при прочих OK | **0** |
| T11 | BUGFIX без `--flag-rev`, нет карточки `REV:tz`, DX+хвост done | **0** |
| T12 | `tasks.session_id` общий на граф, cursor id разные — **не** collapsed | **0** |

Дополнительно: `mode=ro` — тест не требует write-доступа к фикстуре после наполнения.

**Проверка HF:test:**

- [ ] таблица T0–T12: фактические exit 0/1/2
- [ ] pytest green
- [ ] прогон не меняет `~/.hermes/kanban.db`

---

## 5. Порядок внедрения

B1 на диске — **пропустить**. Живой граф: `HF:backup` → `HF:impl` → `HF:test` → `HF:docs-handoff` → `ORCH:shared-state` → preflight → `GATE:done`.

| Шаг | Фаза | Кто | Что |
|---|---|---|---|
| 0 | `HF:backup` | координатор | архив двух SKILL.md + текущего preflight.py в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` |
| 1 | `HF:impl` | исполнитель | §1 скрипт (перезапись) |
| 2 | `HF:impl` | исполнитель | §2 tz-workflow 2.2.0 |
| 3 | `HF:impl` | исполнитель | §3 hermes-feature 2.3.0 |
| 4 | `HF:test` | исполнитель | §4 pytest T0–T12 |
| 5 | `HF:docs-handoff` | исполнитель | статус контура B в ProcessImprovement_TZ; bump версий скиллов в тексте ТЗ; **не** манифест |
| 6 | `ORCH:shared-state` | Сирень | `restore-all-skills.sh` по списку `tz-workflow`, `hermes-feature`; манифест если есть hints |
| 7 | `GATE:done` | воркер / Сирень | первый шаг = preflight `--slug chain-enforcement --case CHANGE` |

Два файла скиллов в одном `HF:impl` допустимы (один роль-исполнитель, одна фаза). Не склеивать с `HF:test` в один `agent -p`.

### Не трогать

Из DPK «Что НЕ трогать» + PI B «Не делать»:

- ядро канбана: `hermes-agent`, `kanban_db`, dashboard plugin, schema sqlite
- новый скилл **chain-guard** / любой третий скилл пайплайна
- форк `kanban-worker` / `kanban-orchestrator`
- авто-крон preflight и автокрон DialogBacklog
- GLOSSARY.md, DevKanbanPipeline_TZ.md (B1 закрыт)
- `cursor-cli`, `cursor-task-context` (не в цели контура B 0.4.1)
- `EcosystemManifest.json` / `entities.json` / `.env` / `jobs.json` — исполнитель
- gateway restart, новые профили, `auto_decompose`
- контур A (`USERTOOLS/AnywhereContacts`, `USERTOOLS/OrgLookup`)
- заготовка в опечатке пути `Work/Vault/` если есть — не использовать

---

## 6. Пофайловый чеклист исполнителя

| Волна | Файл | Действие |
|---|---|---|
| B2 | `~/WorkVault/Registries/pipeline_gate_done_preflight.py` | **переписать** под §1 |
| HF:test | `~/WorkVault/Registries/test_pipeline_gate_done_preflight.py` | **создать** |
| B3/B4 TZ | `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md` | version 2.2.0 + §2 |
| B3/B4 HF | `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md` | version 2.3.0 + §3 |
| docs | `TZ/ProcessImprovement/ProcessImprovement_TZ.md` | только в `HF:docs-handoff`: скрипт «на диске: да», версии скиллов |

---

## Прогресс выполнения

- [ ] B2 скрипт канон CLI + 5 проверок + exit 0/1/2 + ro + лог stderr
- [ ] tz-workflow 2.2.0: запрет «ТЗ целиком», чек-лист TZ-WRITE(full), finalize parents
- [ ] hermes-feature 2.3.0: три гейта, preflight на GATE:done, стоп без корня/без HF:plan, промпт одной роли, block collapsed-chain
- [ ] HF:test T0–T12 green
- [ ] Diff без «Не трогать»

План пройден по галочкам. Статус «completed» на кейс — не этот файл: после impl/test ещё docs, ORCH, preflight, `GATE:done`.
