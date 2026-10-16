---
type: appendix
title: "Единый канонический каркас цепочек (библиотека блоков) — архитектор 08.09"
date: 2026-09-08
source: архитектор session faec40c7 (cursor-grok-4.6-high)
status: draft (согласуется Сашей; встраивание — после «делай»)
related: appendix_chains-and-skills-audit_20260907.md, appendix_glossary-architecture_20260908.md, GLOSSARY.md
---

# Единый канонический каркас цепочек: библиотека блоков

Цель Саши: не 8 рукописных цепочек, а **единый каркас из переиспользуемых блоков** (как функции), консистентный с GLOSSARY и скиллами.

## 0. Новый слой «блок»
- Кейс (полное имя) ≠ **Блок** (`ALL-CAPS`/`PREFIX-TAIL`) ≠ Фаза (`PREFIX:фаза`).
- Блок разворачивается в последовательность фаз с parents. **Карточка = только фаза §5, не имя блока.**
- `BRF` = и префикс фаз, и блок брифа (как TZ=префикс фазы). Имя `BRIEF` не вводить (коллизия с BRF).

## 1. Библиотека блоков
| Блок | Состав | Модель | Артефакты | Не входит |
|---|---|---|---|---|
| **BRF** (бриф в TG) | intake→questions→ask*→rewrite* (ответ сразу в appendix) | оркестратор ничего не придумывает; вопросы/варианты — архитектор | appendix | карточки, GATE, master, код |
| **BRIEF-CLOSE** | GATE:brief-closed + создать граф (parents) | оркестратор | карточки todo+parents | сам бриф, take-into-work |
| **TZ-WRITE** | [stabilize]→[compress]→[patch]→[REV:tz]→finalize(+инвентарь) | арх+компрессор | master-ТЗ, appendix, инвентарь | бриф, analyze/architect-фазы |
| **REV** (крючок) | REV:tz (внутри TZ-WRITE), REV:plan (в PLAN-IMPL-TAIL), REV:report (RESEARCH) | ревизор claude-sonnet-5-medium | замечания | скилл, карточка «REV» |
| **TAKE-INTO-WORK** | GATE:take-into-work | Саша/one-pass | — | план, код |
| **HF-COMPRESS** (опц.) | HF:compress | компрессор | экстракт | план (не в PLAN-IMPL-TAIL) |
| **PLAN-IMPL-TAIL** (ключевой) | HF:plan→[REV:plan]→GATE:plan-approve→HF-TAIL | арх+ревизор+исполнитель+Сирень | план, код, манифест(ORCH) | BRF, TZ-WRITE, компресс |
| **DX** (только BUGFIX) | BUG:diagnose→GATE:diagnose-review | арх read-only | _fix_plan | HF:fix, код |
| **RS** | RS:collect→RS:analyze→[REV:report]→GATE:done | коорд+арх | research/ | impl/test/ORCH/инвентарь |
| **MIG-TAIL** | MIG:plan→plan-approve→backup→(MIG:block-k→block-accept)*→ORCH→done | арх+исп+Сирень | план миграции | HF:impl/test/docs |
| **DEC-PRE + DECOMM-TAIL** | DEC:inventory→GATE:go; backup→EXEC→ORCH→done | арх+коорд+Сирень | backup, exec | HF:impl/test/docs |
| **SK-PRE** (SKILL-CHANGE) | SK:preflight (>15k→compress) | коорд | — | — |

Ключевой **PLAN-IMPL-TAIL** = план + [ревизор плана] + гейт плана + HF-TAIL.
**HF-TAIL** (суффикс) = backup→impl→test→docs-handoff→ORCH:shared-state→GATE:done.
**DECOMM-TAIL** (замена HF-TAIL-min) = backup→EXEC→ORCH→done, EXEC∈{DEC:exec,MIG:exec}.

## 2. Сборка кейсов (кейс = блоки)
- **DEV** = BRF(full)→BRIEF-CLOSE→TZ-WRITE(new)→TAKE-INTO-WORK→[HF-COMPRESS]→PLAN-IMPL-TAIL
- **CHANGE** = BRF(light)→BRIEF-CLOSE→TZ-WRITE(full)→TAKE-INTO-WORK→[HF-COMPRESS]→PLAN-IMPL-TAIL
- **BUGFIX** = DX→BRF(delta)→TZ-WRITE(patch)→TAKE-INTO-WORK→PLAN-IMPL-TAIL (compress skip, REV OFF)
- **RESEARCH** = BRF(scope)→RS (нет TZ-WRITE/TAKE-INTO-WORK/PLAN-IMPL-TAIL/ORCH)
- **MIGRATION** = BRF(light)→BRIEF-CLOSE→TZ-WRITE(freeze)→TAKE-INTO-WORK→MIG-TAIL
- **DECOMM** = BRF(confirm)→DEC-PRE→DECOMM-TAIL(exec=DEC:exec)
- **SKILL-DEV** = DEV {workspace=skills, REV ON, ORCH restore}
- **SKILL-CHANGE** = SK-PRE→CHANGE | удаление SK-PRE→DECOMM; ≤2 файла compress skip/REV OFF

## 3. Сверка сокращений
Вычистить неканон: `HF:fix`→BUG:diagnose/HF:impl; `TZ:architect`/`TZ:analyze` (как бриф и фазы)→BRF/TZ:patch/finalize; `HF:docs`→HF:docs-handoff; «backup»→HF:backup; «ORCH»→ORCH:shared-state; «HF-хвост»→PLAN-IMPL-TAIL; `HF-TAIL-min`→DECOMM-TAIL.
Новых **фаз** нет. Новые **блоки** для GLOSSARY §5.1.

## 4. Консистентность (что поправить)
- **GLOSSARY** (v0.1.0→0.2.0): §1 добавить слой «блок»; §2 колонка «Хвост»=формулы; §4 tz-workflow=BRF+TZ-WRITE (не analyze/architect); §5 добавить «Блоки-компоненты», убрать HF-TAIL-min; §7 синонимы.
- **tz-workflow**: удалить карточки TZ:analyze/TZ:architect, `kanban_block(needs_input)`, старый граф.
- **hermes-feature**: удалить HF:fix, parent `[HF:backup,TZ:stabilize]`→`[HF:backup]`, запись манифеста из Блока 4 (только ORCH), добавить [REV:plan].
- **Каталог**: заменить простыни на таблицу «кейс=блоки».

## 5. Инварианты
1. Кейс не содержит развёртки PLAN-IMPL-TAIL — только вызов блока.
2. 1 agent -p = 1 модель = 1 роль.
3. Бриф не карточка; граф после BRIEF-CLOSE.
4. Реализация только после TAKE-INTO-WORK.
5. Манифест/restore/.env/jobs.json — только ORCH:shared-state.
6. One-pass auto: take-into-work/plan-approve/done. Никогда: diagnose-review/GATE:go/GATE:block-accept.
7. Заголовок карточки ∈ §5. Идемпотентность devpipe:<slug>:<phase>.

Статус: каркас готов к встраиванию в GLOSSARY (v0.2.0) и каталог; скиллы/DevKanbanPipeline — отдельным Stephan после «берём в работу».