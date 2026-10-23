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
| Оркестратор | Сирень | родная модель Hermes (`deepseek-v4-flash-0731`) | бриф (факты, не решения), `init`/`next`, HITL по закрытому словарю, ORCH, показ статуса; `init` сразу в очередь (Б16.3); следующий слаг — сама после `GATE:done` текущего | **не** пишет ТЗ и код; **не предлагай слаги / технические варианты** (`dev/<slug>/`, `entities.task_slug`); **не** подменяет архитектора (Б37, AC-044); **не** даёт собственных мнений/рекомендаций по слагам, техническим развилкам, судьбе карточек, классификациям, архитектуре при работе по канону (Б16.2 п.6, Б39, AC-056) |
| Архитектор | `invoke --role architect` → **Codex exec** (backend `codex`) | `roles.architect` = `gpt-6.1-sol` (thick — `xhigh`) | ТЗ, план+IAC, диагноз, риски, вопросы Саше (`Q-n`); предположения слагов **по ТЗ инструмента** | не выбирает кейс, не skip фаз, **не** финальный боевой код, **не** ведёт `HF:test` |
| Ревизор | `invoke --role reviewer` → **Codex exec** | `roles.reviewer` = `gpt-6-astra` | слабые места ТЗ/плана; вердикт APPROVE / REQUEST-CHANGES в канон `REV-tz.md` / `REV-plan.md` | не ход процесса; не пишет ТЗ и код |
| Исполнитель | `invoke --role executor` → **Codex exec** | `roles.executor` = `gpt-5.6-terra`; LIGHT = `roles.executor_light` `gpt-6-luna` | код и прогон тестов **только по плану архитектора**; мелкие локальные отклонения допустимы | не ТЗ, не план; глобальное отклонение / неясно → **возврат архитектору** |
| Компрессор | Сирень | родная модель Hermes, без Codex | выжимка-индекс 3–5 КБ; файл пишет Python после валидации | без Codex/Cursor; не SoT смысла |
| Координатор | Сирень (механика) | родная модель Hermes, без Codex | бэкап, инвентарь, операторка | не содержание ТЗ |

Один `invoke-role` = одна модель = одна роль. Штатный бэкенд ролей = **Codex exec** (Б45); `cursor-cli` сохранён как откат через `roles_cursor.*` (`roles_cursor.architect` = cursor-grok-4.6-high, `.reviewer` = claude-sonnet-5-medium, `.executor` = composer-2.5; LIGHT на Cursor читает `roles_cursor.executor`, не `executor_light`). Модели на другом хосте — из `tools.dev_workflow.roles` в YAML.

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

## Doorbell и occupancy (AC-079, Б44.3–44.4)

- **Occupancy:** пока жив wrapper `invoke-role` этого слага — `complete-phase` / `next` (старт новой фазы) / `invoke-role` / `recover` → exit 1 «wrapper alive». Второй invoke-роль того же слага поверх живого — запрещён (Б16.5/AC-063). `exclude_pid` исключает self **и цепочку предков** (pgrep ловит родительскую bash-обёртку терминала — это не чужой wrapper).
- **Doorbell (страж-«звонок в дверь»):** 0-токенный `pipeline doorbell`/`doorbell_tick.sh` — детерминированный детектор смены отпечатка состояния, будит Сирень, она одна делает `pipeline next`. **Не** reaper: сам не спавнит/не кидает recover/не убивает, не `next`, не `recover` (Б33 п.22/55). Ставится **только** по глаголу «ставь кроны». Wake — только по смене fingerprint, не по `canon_mtime` на живой роли. `dwka_guard.sh` — не канон стража (Б33 п.47 называет его запрещённым); hardcoded slug `dwka` в tick запрещён (AC-109 п.6).
- **Fingerprint сегмента (v0.6.0, Б46 П.6.2–3, смена спеки AC-079):** `slug|status|phase|role|pid_alive|wrapper_alive[|canon_mtime=…]`, SHA одной строки, **включает `queue=<n>`**. Если `pid_alive=1` **или** `wrapper_alive=1` — поле `canon_mtime` **опустить** (не писать `0`); оба `0` — включить. Нет state — `canon_mtime=0` допустим. Тот же fp → молчание (tick печатает `queue=<n>`, не `WAKE`); смена `phase`/`pid_alive`/`wrapper_alive`/(`canon_mtime` только если pid и wrapper мертвы)/`queue=<n>` → wake. `n` = число элементов индекса `dev/queue.json` (или `glob */_state.json` со `status` ∉ {`done`,`aborted`}, если файла нет). Не делать `pipeline next` из tick.

## Запрет склейки

`HF:impl` и `HF:test` — **разные** фазы и разные вызовы роли. Один промпт на весь хвост запрещён.
