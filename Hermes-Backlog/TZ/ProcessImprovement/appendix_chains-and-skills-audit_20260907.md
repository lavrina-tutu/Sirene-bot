---
type: appendix
title: "Каталог цепочек по кейсам + аудит dev-скиллов (решение архитектора 07.09)"
date: 2026-09-07
source: архитектор session 3ce57e54 (cursor-grok-4.6-high)
status: draft (согласуется Сашей по каждой цепочке)
updated: 2026-09-08 (сборка по GLOSSARY v0.2.0)
related: ProcessImprovement_TZ.md (Блоки 0-1)
---

# Каталог цепочек по кейсам + аудит dev-скиллов

Архитектор (session 3ce57e54) спроектировал набор жёстких цепочек по кейсам и провёл аудит dev-скиллов на дубли/избыточность. Итог одним предложением: **канбан = движок очереди, скиллы = содержание работы; вырезать из скиллов повтор диспетчера**.

## Инварианты
- Цепочка строго последовательная (одна ready в голове, дети todo+parents, без параллелизма).
- Бриф только в TG: базовая модель = оркестратор (варианты + рекомендация архитектора, ничего своего). Вопрос+ответ сразу в appendix ТЗ.
- Канбан-граф после закрытого брифа (или корень blocked без воркера). Запрет kanban_block(needs_input) на TZ/HF-фазах.
- Архитектор = cursor-grok-4.6-high; Ревизор = claude-sonnet-5-medium (опционален); Исполнитель/Компрессор/Координатор = composer-2.5.
- Артефакты: master `TZ/<Tool>/<Tool>_TZ.md`, appendix `appendix_<тема>_YYYYMMDD.md`, инвентарь `MAIN_TZ_INVENTORY.md`, бэкап `_Archives/hermes-backup-*`, ORCH пишет манифест + restore-all-skills.
- Пути: TZ → `dir:.../TZ`, код → `USERTOOLS/<Tool>` или `hermes-workspace/skills`.

## Сборка кейсов (блоки)

| Кейс | Код | Сборка (блоки) |
|---|---|---|
| DEV | DEV | `BRF(full)` → `BRIEF-CLOSE` → `TZ-WRITE(new)` → `TAKE-INTO-WORK` → `[HF-COMPRESS]` → `PLAN-IMPL-TAIL` |
| CHANGE | CHG | `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(full)` → `TAKE-INTO-WORK` → `[HF-COMPRESS]` → `PLAN-IMPL-TAIL` |
| BUGFIX | BUG | `DX` → `BRF(delta)` → `TZ-WRITE(patch)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL` (compress skip, REV OFF) |
| RESEARCH | RS | `BRF(scope)` → `RS` |
| MIGRATION | MIG | `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(freeze)` → `TAKE-INTO-WORK` → `MIG-TAIL` |
| DECOMM | DEC | `BRF(confirm)` → `DEC-PRE` → `DECOMM-TAIL(exec=DEC:exec)` |
| SKILL-DEV | SK | как DEV {workspace=hermes-workspace/skills, REV ON, ORCH restore} |
| SKILL-CHANGE | SK | `SK-PRE` → `CHANGE` \| удаление `SK-PRE` → `DECOMM`; ≤2 файла compress skip/REV OFF |

Полная сборка кейсов и развёртка блоков — в `TZ/GLOSSARY.md` §2 (сборка) и §5.1 (блоки-компоненты).

## Общие фрагменты

Общие фрагменты-блоки: `TZ/GLOSSARY.md` §5.1 (BRF/BRIEF-CLOSE/TZ-WRITE/REV/TAKE-INTO-WORK/HF-COMPRESS/PLAN-IMPL-TAIL/HF-TAIL/DX/RS/MIG-TAIL/DEC-PRE/DECOMM-TAIL/SK-PRE).

## Аудит dev-скиллов (вердикт)
- **tz-workflow** — оставить, урезать: выкинуть канбан-граф/HITL/needs_input/one-pass (дубль диспетчера), оставить артефакты+качество+BRF-в-TG.
- **hermes-feature** — оставить, урезать до HF-TAIL + DX + research-метод + роли моделей + backup + ORCH-правило.
- **DevKanbanPipeline TZ** — оставить как контракт очереди, но заменить «один граф» на каталог кейсов.
- **kanban-orchestrator** — НЕ грузить на DEV-карточки (правило параллельности вредно); только для не-dev fan-out.
- **kanban-worker** — не дублировать в tz/hermes; ядро уже инжектит KANBAN_GUIDANCE.
- **kanban-dev-pipeline-orchestration** — деактивировать (питфоллы → appendix ProcessImprovement); дрейф (нет в git).
- **kanban-pipeline-forensics** — оставить как ops (диагностика БД).
- **cursor-cli** — оставить, сжать, перенести в workspace; добавить модель ревизора в таблицу ролей.
- **cursor-task-context** — оставить тонким; вшить drift-check в HF; починить дрейф модели компрессора.
- **skill-authoring-principles** — оставить (контент SKILL-*).
- **epic-development** — деактивировать из default-load (дубль брифа, 68 КБ).
- **aggregate-tz-opus-workflow** — деактивировать (инструмент-специфичен, Opus-эпоха).
- **hermes-agent-skill-authoring** — не использовать (другой репозиторий).
- **hermes-bugfix-cursor** — оставить вне каталога (аварийный runbook).
- **restore-all-skills.sh** — вызывать только из ORCH:shared-state.
- Расходность: на карточку 1 скилл фазы, не пачка (tz+cursor-cli+cursor-task-context ≈ 60 КБ до работы) — главный скрытый токен-расход.

## Рекомендации (быстрее/качественнее/меньше токенов)
R1. Один каталог кейсов (в DevKanbanPipeline_TZ.md), не три ASCII-графа.
R2. Три скилла на пайплайн вместо десяти (tz-workflow, hermes-feature, cursor-cli+task-context).
R3. На карточку — 1 скилл фазы.
R4. Бриф никогда не карточка (подтверждено block_loop ×3 07.09).
R5. Ревизор — флаг кейса, не отдельный скилл.
R6. Не-код не притворяется HF (RESEARCH/DECOMM без impl/test/docs).
R7. Синхронизировать канон в git (4 скилла живут только в ~/.hermes, выпадают из workspace).

## Открытая развилка (Саше)
Куда кладём каталог цепочек:
1. Секция в DevKanbanPipeline_TZ.md (рекомендуют).
2. Appendix в ProcessImprovement (на время проработки), потом слить.
3. Новый тонкий скилл (против правила).

Статус: каждая цепочка согласуется Сашей явно.

## Урок процесса (замечание Саши 07.09)
Сокращения фаз (BRF/GATE/ORCH/HF…) неочевидны; Саша «еле отгадал BRF», и есть риск сбоя в итерациях. Решение (в проработке): единый **GLOSSARY** в корне `TZ/` (общий для всех кейсов/фаз, расшифровка на русском) + правило **«при первом упоминании акроним расшифровывается»**. Внимание к точности: TZ=ТЗ и скилл `tz-workflow`; HF=скилл `hermes-feature`; ORCH=роль оркестратора (Сирень), `ORCH:shared-state` — лишь фаза; DEV/CHG/BUG/RS/MIG/DEC/SK — кейсы, не родовые термины. Название файла — просто «GLOSSARY», без суффикса кейса.