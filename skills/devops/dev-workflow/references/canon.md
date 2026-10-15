# Канон процесса (операционная копия)

Зеркало `TZ/GLOSSARY.md` для работы без vault. Сверка с vault: `pipeline status --check`. Мастер-нормы — `DevWorkflow_TZ.md` (актуальная `version:` в шапке), блок **Б6** (роли Б6.4, guard-ы Б6.5 включая **G6**).

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

Новый тип работы — только строка в этой таблице **и** согласование Саши. Кейс и сужение до LIGHT — **таблица триггеров** (`cases-guide.md`), не меню слагов; архитектор кейс не выбирает и фазы не укорачивает.

## Роли (Б6.4)

| Роль | Кто | Модель (default этого контура) | Делает | Не делает |
|---|---|---|---|---|
| Оркестратор | Сирень | родная модель Hermes | бриф (факты, не решения), `init`/`next`, HITL по закрытому словарю, ORCH, показ статуса | **не** пишет ТЗ и код; **не предлагай слаги / технические варианты** (`dev/<slug>/`, `entities.task_slug`); **не** подменяет архитектора (Б37, AC-044) |
| Архитектор | `invoke --role architect` | `cursor-grok-4.6-high` (LIGHT допустим medium) | ТЗ, план+IAC, диагноз, риски, вопросы Саше (`Q-n`); предположения слагов **по ТЗ инструмента** | не выбирает кейс, не skip фаз, **не** финальный боевой код, **не** ведёт `HF:test` |
| Ревизор | `invoke --role reviewer` | `claude-sonnet-5-medium` | слабые места ТЗ/плана; вердикт APPROVE / REQUEST-CHANGES в канон `REV-tz.md` / `REV-plan.md` | не ход процесса; не пишет ТЗ и код |
| Исполнитель | `invoke --role executor` | `composer-2.5` | код и прогон тестов **только по плану архитектора**; мелкие локальные отклонения допустимы | не ТЗ, не план; глобальное отклонение / неясно → **возврат архитектору** |
| Компрессор | Сирень | родная модель Hermes | выжимка-индекс 3–5 КБ; файл пишет Python после валидации | без Cursor; не SoT смысла |

Один `invoke-role` = одна модель = одна роль. Модели на другом хосте — из `tools.dev_workflow.roles` в YAML.

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

**`GATE:done` на workflow-only — закрывать через `pipeline next` → `AUTO_GATE` → `complete-phase`** (AC-отчёт доставлен в origin, journal-маркер `AC-delivered: origin`). Legacy-скрипт `pipeline_gate_done_preflight.py` читает `kanban.db` и требует корень `DEV/<slug>` в канбан-БД — на чисто файловом слаге (fresh-init на workflow-only, канбан выключен) он упадёт с «корень DEV/<slug> не найден» вне зависимости от готовности файлов. Это не сигнал чинить граф: префлайт-скрипт не учитывает файловую модель, а GATE:done корректно закрывается auto-gate pipeline. Исключение — слаги с живой канбан-записью корня (миграционные): там префлайт применим.

**Never auto** (ждут фразу/действие в origin):

- `GATE:go` (DECOMM и аналоги).
- `GATE:block-accept`.

Показ AC ≠ ожидание (класс **S**). Действие Саши для закрытия AC — класс **O** (operator-hold).

### Operator-глаголы (закрытый словарь)

`поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n` · `rollback-to-kanban`

Снятие: `pipeline operator-done --verb <глагол> --evidence …`. Новый глагол — только через `TZ:patch` DevWorkflow/DKP.

## Guard-ы G1–G6

| Guard | Смысл |
|---|---|
| **G1** | фаза из рецепта слага; version/mtime ТЗ совпадают с диском; выжимка от текущей `tz_version`; после красного git-proof не стартовать test/docs |
| **G2** | на complete TZ/HF/BUG/REV есть маркер `context-used:` (emit-prompt вызывали) |
| **G3** | перед `HF:test` и `GATE:done` — изменения из `HF:impl` закоммичены (git-proof) |
| **G4** | при init и при закрытии — рецепт полон для кейса |
| **G5** | архитектор/исполнитель не меняют кейс и не skip обязательные фазы |
| **G6** | `--role` совпадает с таблицей фаза→роль; `slug_source` ∈ {`suggest-cli`,`sasha-verbatim`,`reuse`}; не отдавать stdout `suggest-slug` Саше нумерованным списком; канонические имена REV-артефактов |

### G6 — фаза → роль (исчерпывающая для `recipe[]` десяти кейсов)

| Фазы | `--role` / кто |
|---|---|
| `TZ:patch`, `TZ:finalize`, `HF:plan`, `BUG:diagnose`, `RS:collect`, `RS:analyze`, `MIG:plan`, `MIG:block-k`, `DEC:inventory`, `IDEA:analyze` | `architect` |
| `REV:tz`, `REV:plan`, `REV:report` | `reviewer` |
| `HF:impl`, `HF:test`, `DEC:exec` | `executor` |
| `TZ:compress`, `HF:compress` | `compressor` |
| `TZ:stabilize`, `SK:preflight`, `HF:backup`, `HF:docs-handoff`, `ORCH:shared-state`, гейты | оркестратор (Сирень); Cursor-роль не звать |

Нет строки для фазы из рецепта = G6 fail. `pipeline recipe-add` (`MIG:block-k` и динамические блоки) наследует роль `MIG:block-k` = `architect`. Нормы покрытия: `RS:collect` — architect (read-only как диагноз); `SK:preflight` — оркестратор (механика как `TZ:stabilize`); `MIG:block-k` — architect по умолчанию.

Несовпадение → emit-prompt / `invoke-role` / `complete-phase` **exit 1** (журнал `g6_role_mismatch`).

## Запрет склейки

`HF:impl` и `HF:test` — **разные** фазы и разные вызовы роли. Один промпт на весь хвост запрещён.
