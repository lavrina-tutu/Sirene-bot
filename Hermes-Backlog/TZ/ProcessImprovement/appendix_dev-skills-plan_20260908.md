---
type: appendix
title: "План доработки dev-скиллов к канону GLOSSARY v0.2.0 (по рекомендации архитектора)"
date: 2026-09-08
status: to-implement (через Cursor, последовательно)
related: GLOSSARY.md v0.2.0, appendix_chains-and-skills-audit, appendix_chains-unification
---

# План доработки dev-скиллов к канону

Цель: привести все dev-скиллы к единому канону GLOSSARY v0.2.0 (блоки §5.1, сборка кейсов §2, синонимы §7, слои §1), убрав избыточность канбан-механики (по аудиту) и неканонические фазы.

## Инварианты канона (что внедряется во все)
1. Фаза = `PREFIX:фаза`; карточка = только фаза §5, не блок.
2. Бриф (BRF) в TG, не карточка. Запрет `kanban_block(needs_input)` на TZ/HF-фазах.
3. Граф после BRIEF-CLOSE. Parent impl = [HF:backup], не [HF:backup,TZ:stabilize].
4. Манифест/restore/.env/jobs.json/entities.json — только ORCH:shared-state.
5. Один агент -p = одна роль. Модели из §3.
6. read_file GLOSSARY перед первым PREFIX:фаза (блок «## Термины» уже есть).
7. Имена блоков (PLAN-IMPL-TAIL и др.) — из GLOSSARY, не карточки.

## Правки по скиллам

### tz-workflow (skills/devops/)
- **Граф TZ (канбан-шаг):** убрать `TZ:analyze`/`TZ:architect` из дерева фаз. Заменить стандартной головой `BRF(full/light/delta/scope/confirm)` → `BRIEF-CLOSE` → `TZ-WRITE(mode)`.
- **HITL-вопросы:** убрать `kanban_block(kind=needs_input)` на TZ-фазах (бриф только в TG, через оркестратора). Оставить только гейты `$GATE:take-into-work` через comment+block(review-required).
- **Модели/таблица:** шаги 1-4 (analyze/architect) → заменить на BRF+TZ-WRITE; компрессор = composer-2.5.
- **Сборка кейсов:** добавить ссылку на GLOSSARY §2 (кейс=блоки), убрать рукописные цепочки.
- Очистить TZ drift отсылку на `TZ:analyze`/`TZ:architect`.

### hermes-feature (skills/devops/)
- **Граф HF:** parent `HF:impl = [HF:backup]` (не [HF:backup,TZ:stabilize]); добавить `[REV:plan]` между HF:plan и GATE:plan-approve (опц. флаг).
- **Манифест:** Блок 4 «обновить EcosystemManifest» → только ORCH:shared-state (исполнитель не пишет манифест); убрать из шагов impl.
- **HF:fix:** убрать из Блока 6В (запрещён GLOSSARY §7); диагноз → BUG:diagnose, реализация → HF:impl.
- **Candidate читать GLOSSARY** для HF-TAIL/DECOMM-TAIL/DX/RS.
- Сборка кейсов: ссылка на GLOSSARY §2.

### cursor-cli (skills/devops, живёт в ~/.hermes)
- Добавить **ревизора** (claude-sonnet-5-medium) в таблицу ролей.
- Убедиться, что `--model`/`--resume` соответствуют канону; упомянуть PLAN-IMPL-TAIL блок? (min).

### cursor-task-context (skills/devops, живёт в ~/.hermes)
- Слой 0 = digest + GLOSSARY (путь к TZ/GLOSSARY.md).
- Починить дрейф модели компрессора (было gemini-3.6-flash-low → composer-2.5) по канону 31.08.

### skill-authoring-principles
- Согласовать упоминания фаз/терминов с каноном (если есть анализ/архитектор-фазы — убрать).

### kanban-* / epic-development / aggregate-tz-opus-workflow (по аудиту — деактивация/не-груз на DEV)
- **Не грузить на DEV-карточки**: kanban-orchestrator, kanban-worker, epic-development, aggregate-tz-opus-workflow.
- Отметить в их description/триггерах «не для DEV-пайплайна» (или деактивировать) по вердикту аудита.

### DevKanbanPipeline_TZ (TZ/DevKanbanPipeline/)
- Таблица фаз → **канон GLOSSARY §2/§5.1** (сборка кейсов из блоков, ORCH = Сирень).
- Заменить «один граф на всё» на каталог кейсов.

## Формат реализации
Последовательно, скилл за скиллом, через Cursor (composer-2.5 для механики, grok для содержания где нужно). После каждого — проверка grep, что неканон убран, канон-ссылка добавлена. Ядро канбана не трогать (по DevKanbanPipeline).

Статус: к реализации.