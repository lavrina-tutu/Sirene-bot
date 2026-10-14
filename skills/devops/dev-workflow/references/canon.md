# Канон процесса (операционная копия)

Зеркало `TZ/GLOSSARY.md` для работы без vault. Сверка с vault: `pipeline status --check`. Мастер-нормы также в `DevWorkflow_TZ.md` v0.3.2, блок Б6.

## Десять кейсов (закрытый список)

| Кейс | Когда |
|---|---|
| **DEV** | новый инструмент или крупная фича |
| **CHANGE** | доработка существующего (полный цикл ТЗ) |
| **CHANGE-LIGHT** | доработка ≤3 файлов кода+тест, аддитивная секция ТЗ, без новых сущностей/cron/.env |
| **BUGFIX** | баг (с диагнозом) |
| **BUGFIX-LIGHT** | лёгкий баг ≤3 файлов; LIGHT после `GATE:diagnose-review` |
| **RESEARCH** | анализ без кода |
| **MIGRATION** | миграция инфраструктуры |
| **DECOMM** | снятие инструмента |
| **SKILL-DEV** | новый скилл (workspace = hermes-workspace/skills) |
| **SKILL-CHANGE** | правка или удаление скилла |

Новый тип работы — только строка в этой таблице **и** согласование Саши. Кейс и сужение до LIGHT выбирают **Саша и оркестратор**; архитектор кейс не выбирает и фазы не укорачивает.

## Роли

| Роль | invoke `--role` | По умолчанию (этот контур) | Делает | Не делает |
|---|---|---|---|---|
| Оркестратор | — (ты) | родная Hermes | бриф, init/next, HITL, ORCH | ТЗ, код |
| Архитектор | `architect` | cursor-grok-4.6-high | ТЗ, план+тесты (IAC), риски | ход процесса |
| Ревизор | `reviewer` | claude-sonnet-5-medium | REV ТЗ/плана | ход процесса |
| Исполнитель | `executor` | composer-2.5 | код и `HF:test` | ТЗ, план |
| Компрессор | (Сирень, без Cursor) | родная Hermes | текст для `TZ:compress` / `HF:compress` | файл пишет Python |

Один вызов `invoke-role` = одна модель = одна роль. Модели на другом хосте — из `tools.dev_workflow.roles` в YAML.

## Префиксы фаз

- **BRF:** — только Telegram до `init`, в `recipe[]` не попадает.
- **GATE:** — гейты Саши (см. ниже).
- **TZ:** — stabilize, compress, patch, finalize.
- **HF:** — compress (опц.), plan, backup, impl, test, docs-handoff.
- **REV:** — tz, plan (согласование архитектор ↔ ревизор).
- **BUG:** — diagnose.
- **RS:** — collect, analyze (RESEARCH).
- **MIG:** — plan (MIGRATION).
- **DEC:** — inventory, exec (DECOMM).
- **SK:** — preflight (SKILL-CHANGE).
- **ORCH:** — shared-state (манифест, restore скиллов — зона ORCH на диске).

Рецепты по кейсам совпадают с `pipeline_recipe.py` в `Registries/pipeline/`.

## Гейты

**Auto** (после улики, поезд не ждёт Сашу для класса S):

- `GATE:take-into-work` — показан `AC-list.md` в origin.
- `GATE:plan-approve` — план архитектора на диске.
- `GATE:diagnose-review` — план фикса или тело диагноза.
- `GATE:done` — preflight 0 и отчёт AC в origin.

**Never auto** (ждут фразу/действие в origin):

- `GATE:go` (DECOMM и аналоги).
- `GATE:block-accept`.

Показ AC ≠ ожидание (класс **S**). Действие Саши для закрытия AC — класс **O** (operator-hold).

### Operator-глаголы (закрытый словарь)

`поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n` · `rollback-to-kanban`

Снятие: `pipeline operator-done --verb <глагол> --evidence …`. Новый глагол — только через `TZ:patch` DevWorkflow/DKP.

## Guard-ы G1–G5

| Guard | Смысл |
|---|---|
| **G1** | фаза из рецепта слага; version/mtime ТЗ совпадают с диском; выжимка от текущей `tz_version`; после красного git-proof не стартовать test/docs |
| **G2** | на complete TZ/HF/BUG/REV есть маркер `context-used:` (emit-prompt вызывали) |
| **G3** | перед `HF:test` и `GATE:done` — изменения из `HF:impl` закоммичены (git-proof) |
| **G4** | при init и при закрытии — рецепт полон для кейса |
| **G5** | архитектор/исполнитель не меняют кейс и не skip обязательные фазы |

Закрытие слага: только после `GATE:done`. `abort` папку не удаляет.

## Запрет склейки

`HF:impl` и `HF:test` — **разные** фазы и разные вызовы роли. Один промпт на весь хвост запрещён.
