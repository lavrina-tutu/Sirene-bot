---
name: tz-workflow
description: "Use when: создание/доработка/архивация ТЗ и инфрасхем"
version: 2.10.1
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [workflow, tz, workvault, hermes, documentation]
    related_skills: [hermes-feature, workvault-rag, hermes-ops]
---

# tz-workflow

# Dual-path (DevWorkflow W2)

Пока `orchestration.mode` ≠ `workflow-only`:
не `pipeline init` вне `pilot_slugs`.
slug ∈ `pilot_slugs` → стоп, отдай `dev-workflow`.
Иначе канбан + `hermes-feature` / `tz-workflow`.
Два поезда на slug запрещены.
Конфиг: `EcosystemConfig.yaml` → `tools.dev_workflow.orchestration`.
W1: `pilot_slugs: []`, `mode: kanban-primary`.
Откат W2: `git checkout` SKILL.md + `restore-all-skills.sh`.
Баннер 10–15 строк — не переписывать тело старых скиллов.
Только маршрутизация dual-path.
Стоп при живом kanban-running на том же slug.
Пилот один слаг за раз (W2).
## Термины
Перед первым `PREFIX:фаза` читать `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`.
Имена фаз/ролей/скиллов только из канона. Голые TZ/HF/ORCH/DEV без двоеточия запрещены.

## Overview

Единые правила хранения, версионирования и архивации ТЗ инструментов Hermes/USERTOOLS, включая инфраструктурные планы. Содержательная работа — через Cursor CLI (`agent -p`).

## When to Use

- Создание/доработка/архивация ТЗ инструмента
- Задача касается USERTOOLS (`MoveFromFF`, `AggregateFromMeetings`, …) и упоминается «ТЗ»
- Обновление реестра `MAIN_TZ_INVENTORY.md`
- План установки/настройки (RAG, systemd, MCP-интеграции) — по той же схеме `TZ/<Topic>/<Topic>_TZ.md`

Не применять: рабочие данные vault (`Projects/`, `People/`, `Meetings/`), git-репозитории конфига.

**Связь с hermes-feature:** после `TZ:finalize` AC-список показывается в origin-топик (показ, не ожидание), `GATE:take-into-work` auto-pass, поезд идёт сам — hermes-feature стартует без фразы Саши (императив 28.09: старт→финиш).

## Workflow (Шаги 0–4)

### Модели (Codex exec) — раздельные задачи

**Инвариант:** один вызов `invoke-role` = одна модель = одна роль. Сирень координирует цепочку, **не смешивает** модели в одном промпте.

**Валидация и рекомендации по постановке — только от архитектора (требование 2).** Сирень не предлагает своё мнение/варианты по постановке и архитектуре задач — передаёт архитектору (`gpt-6.1-sol` через Codex exec `invoke-role`), выполняет по его рекомендациям. Фактологические вопросы Саше — текстом (процедура H / R3).

**Запрет склейки TZ-WRITE:** промпты вида «напиши ТЗ целиком», «весь TZ-WRITE одним `agent -p`», склейка `TZ:compress`+`TZ:patch`+`TZ:finalize` (и тем более с ролью исполнителя) — **запрещены**. `TZ-WRITE(mode)` = отдельные фазы и отдельные invoke-role по GLOSSARY §5.1. Один вызов закрывает **ровно одну** фазу из `{TZ:stabilize, TZ:compress, TZ:patch, REV:tz, TZ:finalize}`.

> **Колонка «Модель»** — внутри `invoke-role` (Codex exec); Cursor (roles_cursor.*) — откат через `agent -p`, **не** override на `pipeline init`. На фазах `TZ:*` / `REV:tz` модель задаёт роль, не init.

| Шаг | Роль | Модель (`invoke-role` → Codex exec; откат Cursor roles_cursor) | Когда |
|---|---|---|---|
| BRF | оркестратор | deepseek (TG, без Codex) | диалог; варианты постановки — сначала архитектор gpt-6.1-sol (Codex exec), затем ответ Саше |
| TZ:stabilize | воркер (диск) | — (без invoke-role) | path, version, mtime в metadata |
| Шаг 0 — Компрессия ТЗ | оркестратор (Сирень) | `deepseek-v4-flash-0731` (осн. Hermes) | `TZ:compress`: экстракт master-ТЗ 3–5 КБ, без Codex |
| TZ-WRITE | архитектор | `gpt-6.1-sol` | `TZ:patch` / `TZ:finalize`: анализ, архитектура, текст ТЗ |
| REV | ревизор | `gpt-6-astra` | `REV:tz` — по умолчанию во всех dev-задачах; искл. лёгкие BUGFIX/SKILL-CHANGE ≤3 файла (08.09.2026) |
| Механические задачи | координатор | Сирень (Hermes), без Codex | Операторские кроны, инвентарь без семантики |

Сборка кейсов (DEV/CHANGE/BUGFIX/…) — блоки из GLOSSARY §2/§5.1, не рукописные цепочки. Канон: `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`.

### Шаг 0 — Компрессия ТЗ (выполняет оркестратор, без Cursor)

- **Промпт:** `~/WorkVault/Registries/tz-compressor-prompt.md`
- **Модель:** `deepseek/deepseek-v4-flash-0731` (основная Hermes), оркестратор; **не через Cursor CLI**.
- **Вход:** полный текст master-ТЗ инструмента (+ зависимые ТЗ, если связаны).
- **Выход:** «актуальная спецификация» 3–5 КБ, full-coverage (100% сущностей/полей/API/лимитов, имена дословно).
- **Без кэша:** экстракты не сохраняются между задачами — только в памяти сессии до передачи архитектору.
- Если исходное ТЗ упоминает предложения новых инструментов/приложений/сущностей — сохранить в экстракте пометку [NEW-ENTITY], не потерять при сжатии.
- **Контекст экосистемы:** опционально `EcosystemManifest.digest.md` для связей (не вместо экстракта своего ТЗ).

```bash
Компрессию выполняет оркестратор (Сирень) напрямую: промпт tz-compressor-prompt.md + полный текст ТЗ → «Актуальная спецификация» 3–5 КБ в ответ. Без вызова `agent -p`.
```

### Паттерн вызова Cursor CLI (legacy, откат)

```bash
cd ~/WorkVault/Hermes-Backlog/TZ && agent -p "задача" -f --model cursor-grok-4.6-high --output-format json
```

- `-p` — print-mode (неинтерактивный)
- `-f` — force (пропуск диалогов доверия)
- `--model` — модель из таблицы выше
- `--output-format json` — структурированный вывод с usage/session_id

### Шаг 1 — Анализ и планирование

**Отдельная задача Cursor** на `cursor-grok-4.6-high` (не в том же вызове, что Шаг 0).

- Вход: экстракты Шага 0 (своего + зависимых инструментов) + `EcosystemManifest.digest.md` + бриф Саши.
- Прочитать `MAIN_TZ_INVENTORY.md` — полный список существующих инструментов.
- Для КАЖДОГО существующего ТЗ оценить: есть ли вероятность совместной работы с новым инструментом.
- **Перед планированием** — найти все ТЗ через `MAIN_TZ_INVENTORY.md`, проверить взаимосвязь между существующими ТЗ и новыми вводными; если есть связь — передать связанные ТЗ в промпт Cursor как контекст.
- Проверить инфраструктуру Hermes (`config.yaml`, скиллы, кроны).
- **Reuse-first (см. references/reuse-first-rule.md):** сначала проверить, решает ли задачу существующий tool/skill/entity/application из EcosystemManifest.digest.md + MAIN_TZ_INVENTORY.md. Новая сущность — только с пометкой „требует согласования Саши“.
- Результат: драфт ТЗ с разделами «Связи с существующими инструментами» и «Связи с инфраструктурой Hermes».

### Шаг 2 — Архитектура и функциональные блоки
- Проанализировать выявленные связи.
- Не додумывать — задавать вопросы с вариантами и рекомендациями (процедура H).
- Спроектировать функциональные блоки, общую схему, место в экосистеме.
- Планировать переиспользование справочников (entities.json, contacts.enc и т.п.).
- **Повторяется** до полной архитектурной ясности.

### Шаг 3 — Написание ТЗ
- Обрабатывать вопросы пользователя, разрабатывать ТЗ.
- Сверяться с мировым опытом.
- При нестыковках — уточнять у пользователя (с рекомендациями).
- При архитектурных нестыковках — возврат на Шаг 2.
- **Повторяется** до полной ясности.

### Шаг 4 — Финализация ТЗ
- Критерий готовности: внутренняя проверка архитектора завершена И пользователь сказал «финализируй».
- Чеклист качества:
  - [ ] Цель сформулирована одним предложением
  - [ ] Все входные данные и выходные артефакты описаны явно
  - [ ] Каждый шаг реализации атомарен
  - [ ] Критерии успеха проверяемы
  - [ ] Раздел «Что НЕ трогать» заполнен
  - [ ] Раздел «Связи с экосистемой» заполнен (или «Нет зависимостей»)
  - [ ] Раздел "## Контракты экосистемы" заполнен по стандарту (references/contracts-standard.md), или явно "Нет внешних контрактов" — **для новых ТЗ** (не ретрофит исторических при DECOMM)
  - [ ] Открытые вопросы закрыты или зафиксированы в `## Открытые вопросы`
  - [ ] Краткость + полнота: ни одной лишней фразы, ни одной пропущенной детали
  - [ ] В **новой** секции master-ТЗ пакета — маркеры I1 `current` / `target` (канон: DKP v0.3.2 + GLOSSARY §3 слой AC/IAC)
  - [ ] Подраздел `### Критерии приёмки (AC)` с якорями `AC-001`… **только пакета**, не ретрофит корпуса; формулировка наблюдаема (команда/артефакт)

### Цикл разработки

1. **Бриф** — вопросы по процедуре H, фиксация решений в чате и драфте ТЗ.

   **Постановка через открытый диалог («дослушай до конца, пока ничего не делай»):** требования собираются итеративно, по одному пункту за сообщение. Каждый новый пункт — **кратко пересказать и подтвердить понимание своими словами**, вплетая в накопительный контекст постановки. Технические/архитекторские side-effects (вызов Cursor, запись ТЗ, компрессия) — **не начинать**, пока не прозвучал явный закрывающий императив («зафиксируй все требования в ТЗ и передай архитектору»). Открытые развилки закрываются по одной вопросу с вариантами и рекомендацией, фиксируются в контекст, не в код/файл. При handoff архитектору — передать **все связанные упомянутые инструменты/ТЗ + общую схему экосистемы (digest)**, и явно предусмотреть ревизора (**REV:tz**, по умолчанию при крупной многосвязной постановке). Контекст остаётся read-only до закрытия открытых вопросов.
2. **ТЗ** — Шаги 2-4 через Cursor CLI (`agent -p`), версионирование, регистрация в `MAIN_TZ_INVENTORY.md`.
3. **Обновление ТЗ** — после каждого брифа исполнитель (composer-2.5) вносит правки; архитектурные изменения — архитектор (cursor-grok-4.6-high через Cursor CLI).
4. **Реализация** — после `TZ:finalize` AC показ в origin → `GATE:take-into-work` auto-pass → hermes-feature идёт сам (императив 28.09).

### Правила автономии

- **Side-effect только по императиву** — никаких правок без явного «делай».
- **Кроны НЕ создаются автоматически** — перечисляются в отчёте, создаются только по «ставь».
- **НЕТ шорткатов даже для багфиксов с известным root cause.** Прецедент (MoveFromLoop v0.4.2, 07.08.2026): агент с готовой диагностикой от архитектора предложил «использовать диагностику как spec → сразу hermes-feature» или «короткий бриф вместо ТЗ» — пользователь отклонил. **Правило:** для ЛЮБОЙ задачи доработки ТЗ ИЛИ реализации — всегда tz-workflow (Шаги 1-4 → ТЗ-файл → MAIN_TZ_INVENTORY.md) → `TZ:finalize` → AC показ в origin → `GATE:take-into-work` auto-pass → hermes-feature (без фразы «берём в работу»). Нет исключений для багфиксов, хотфиксов, мелких правок.
- **Валидация и рекомендации по постановке — только от архитектора (требование 2).** Сирень (Hermes) НЕ предлагает собственное мнение, собственные варианты решений или рекомендации по постановке задач — передаёт архитектору (`cursor-grok-4.6-high` через Cursor CLI), выполняет по его рекомендациям. Фактологические уточняющие вопросы Саше — текстом (процедура H / R3), без собственных вариантов по постановке. (См. также «Модели (Cursor CLI)» и Q2 бриф-фазы.)

## DevWorkflow-шаг

> DevWorkflow (`skills/devops/dev-workflow`). Рецепт в `dev/<slug>/_state.json` после `pipeline init`.

### Когда создавать граф

Создавать граф `DEV/<slug>/…`, если: цикл 2+ шагов tz-workflow/hermes-feature; работа должна пережить обрыв сессии; есть гейт Саши; нужен audit trail. **Не создавать** для одношагового ответа / `delegate_task` / однострочного вопроса Саши.

### Вход триггера (после BRIEF-CLOSE)

Бриф (`BRF:full` / `light` / `delta` / `scope` / `confirm`) — **только в TG** через оркестратора (Сирень), не фаза на диске. **Не вызывать `pipeline init`**, пока на slug (или в сессии брифа до init) есть `open-questions:` с `Q-n` в `status=open` — сначала закрыть вопрос. `pipeline init` / смена `--case` / skip §5.2 делает **ТОЛЬКО оркестратор после `GATE:brief-closed`** — не архитектор на `TZ:patch`/`TZ:finalize`/`REV:tz` (AC-H03/H09). После `GATE:brief-closed` — **один** `pipeline init` с полным рецептом кейса: `TZ-WRITE(mode)` + `GATE:take-into-work` + `PLAN-IMPL-TAIL` (или `-LIGHT` по GLOSSARY §2). `--case`/`mode` — из GLOSSARY §2 (`new` / `full` / `patch` / `freeze`).

После батча — **структурный preflight G4** (AC-H08): `python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py --slug <slug> --case <CASE> --mode create`. Fail → `interrupt` **корня** `kind=dependency`, воркеров не стартовать.

**Полный рецепт сразу после брифа** (императив 28.09): второй «разворот хвоста» после гейта запрещён (legacy unfold). Оркестратор ведёт фазы через `pipeline next`. `GATE:take-into-work` в рецепте и auto-pass после `TZ:finalize`.

- **Запрет `model` на create:** на `TZ:*`, `REV:tz`, `HF:*`, `BUG:*` и `IDEA:analyze` — **без** `--model` / `model=` (D1 = NULL, воркер default Hermes; анти-пример: `invoke-role` с model override (запрещено) на `TZ:patch` → HTTP 400 у Hermes-воркера, `protocol_violation`, прецедент `t_2c8ee3b2`). Роли grok/composer — только D2 внутри `agent -p --model …`.
- **Ключ на КАЖДУЮ фазу при create:** `devpipe:<slug>:<phase>:<tz_version_or_none>` (lookup до create, дубль = no-op; rework — суффикс `:rework:<n>:<tz_version>`).

- **Все задачи по умолчанию** после триггера «разработай/доработай/почини» ложатся в план (кейс DevWorkflow `DEV/<slug>`) и далее проводятся по канону, без дополнительной команды Саши.
- **Slug-guard (перед `pipeline init` для `<slug>`):** если `dev/<slug>/_state.json` уже живой (не `done`) — **не** второй init; reuse или `interrupt` до разрешения. Два поезда на slug запрещены (прецедент pfs-notify-link-unprocessed).
- **Идеи `triage` (`IDEA:*`)** НЕ переводятся в DEV-работу без явного «разбери»/«берём в работу» — это не противоречит «все задачи в план»: идеи в бэклоге — до постановки, по команде Саши (ЖЦ разделён, неконфликтующая формулировка).

Граф кейса — ОДИН батч: TZ-WRITE(mode) + `GATE:take-into-work` + `PLAN-IMPL-TAIL` (parents обязательны). Для DEV/CHANGE (полный) граф:

```
DEV/<slug>                          корень (живёт до GATE:done)
├─ TZ:stabilize
├─ TZ:compress          parents=[TZ:stabilize]
├─ TZ:patch             parents=[TZ:compress]     # архитектор, --resume
├─ REV:tz               parents=[TZ:patch]        # по умолчанию во всех dev-задачах
├─ TZ:finalize          parents=[REV:tz]          # + MAIN_TZ_INVENTORY.md
├─ GATE:take-into-work  parents=[TZ:finalize]     # auto-pass: ac-shown (показ AC ≠ ждать)
└─ PLAN-IMPL-TAIL: HF:plan (parents=[GATE:take-into-work]) ─ [REV:plan] ─ GATE:plan-approve (auto) ─ HF-TAIL (HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done)
```

LIGHT-кейсы (BUGFIX-LIGHT / CHANGE-LIGHT ≤3 файла) — короткий хвост в том же батче (GLOSSARY §5.2): `TZ:patch → TZ:finalize → GATE:take-into-work → HF:impl → HF:test → HF:docs-handoff → GATE:done`. Весь граф создаётся одним ``pipeline init` после брифа после брифа; второго unfold нет.

`workspace_kind`: `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` для TZ-шагов. Skills на фазах: `tz-workflow`, `cursor-cli`, `cursor-task-context`. Idempotency каждой фазы: `devpipe:<slug>:<phase>:<tz_version_or_none>`.

#### Origin и уведомления (DevWorkflow)

При `pipeline init` зафиксировать `--origin-chat` и `--origin-thread` (диалог/топик инициатора; не Monitoring `:7`, не Errors `:11112`). Ход кейса, AC и паузы на Сашу — в **origin**; техника CLI/инвариантов — ErrorBus. Норматив: скилл `dev-workflow` («HITL и уведомления», `references/invoke.md`). Команды `hermes kanban notify-*` и таблица `kanban_notify_subs` — **legacy**, не использовать (диспетчер снят с W4).

Terminal `blocked` / `waiting_operator` трактовать как «ждёт Сашу» в origin, не как зависание фонового dispatch. Рестарт gateway — только по фразе Саши «поднимай» (AC-010), не из этого скилла.

#### Быстрый путь CHANGE-LIGHT (опционально, ≤3 файла)

Для малых доработок существующего инструмента (без новых сущностей/cron/.env),
когда канон `GLOSSARY §2/§5.1` выбран кейс `CHANGE-LIGHT` (6 карточек вместо полного графа):

```
TZ:patch (секция + version bump + инвентарь в том же ходе, stabilize/compress skip)
  → HF:impl → HF:test → HF:docs-handoff (создаёт version-handoff)
  → GATE:done (auto-pass после preflight exit 0)
```

- `TZ:stabilize`/`TZ:compress` — **skip** (архитектор читает целевые §, не весь master-ТЗ).
- `REV:tz` — **OFF** при ≤3 файлах кода вне shared/foundational-модулей
  (не трогать общие модули: парсинг дат, запись задач, резолв людей).
- `HF:plan`/`GATE:plan-approve`/`HF:backup`/`ORCH:shared-state` — **skip** для ≤3 файлов
  (бэккап = git/копия 3 файлов; манифест не меняется).
- Такая карточка НЕ содержит «склейку фаз одним agent -p» — каждая из
  TZ:patch / HF:impl / HF:test / HF:docs-handoff — отдельная карточка/вызов.

- **Выбор LIGHT — оркестратор + Саша на старте** (семейство `*-LIGHT`); сужение
  CHANGE→CHANGE-LIGHT / BUGFIX→BUGFIX-LIGHT делает **оркестратор** после оценки
  объёма на `TZ:patch` / `GATE:diagnose-review`, **не архитектор** (AC-H10).
  Оценка «≤3 файла» в ТЗ — факт для решения, не команда skip.

`GLOSSARY` канон — источник истины; этот раздел — сокращённая шпаргалка.

#### Багфикс (кейс BUGFIX / BUGFIX-LIGHT)

Триггер «баг/ошибка/не работает/почини/разберись/cron run failed» — **первый tool-шаг**:
`pipeline init` корня `DEV/<slug>` **И** `BUG:diagnose` в одном create-батче
(инвариант 9, GLOSSARY §2/§5.2), **до** любого agent -p / cronjob / delegate.
Ретро-корень запрещён (прецедент pfs-promote-bugfix 22.09 → preflight красный).

```
корень DEV/<slug> + BUG:diagnose      # ОДИН create-батч, до agent -p
GATE:diagnose-review    parents=[BUG:diagnose]   # auto по артефакту _fix_plan_*.md / непустому body; не HITL Саши
→ TZ-WRITE(patch) → GATE:take-into-work (auto-pass: ac-shown) → ...
```

`GATE:diagnose-review` — **auto** (доработка B плана process-rework): воркер гейта complete сам, когда `BUG:diagnose` done и на диске есть `_fix_plan_*.md` **или** непустой body. Классификация LIGHT — в том же ходе, без ожидания Саши. REV качества ТЗ остаётся `REV:tz` в `TZ-WRITE`, не на этом гейте.

`GATE:take-into-work` — **always auto** (`auto-pass: ac-shown` после показа AC в origin), включая BUGFIX/BUGFIX-LIGHT (императив 28.09).

### Чек-лист TZ-WRITE(full)

Режим `full` = кейс CHANGE (GLOSSARY §2). Все пункты — **отдельные карточки**; parents как в графе выше:

- [ ] `TZ:stabilize` done (path, `version`, `mtime` в metadata)
- [ ] `TZ:compress` done (экстракт 3–5 КБ, без кэша, модель `deepseek-v4-flash-0731` оркестратором)
- [ ] `TZ:patch` done (архитектор `cursor-grok-4.6-high`, `--resume` своей сессии)
- [ ] `REV:tz` done **или** comment `flag-waived: Sasha` (default ON для CHANGE)
- [ ] `TZ:finalize` done (запись `TZ/<Tool>/<Tool>_TZ.md` + инвентарь) — **только после** родителей ниже
- [ ] на каждой фазе TZ-WRITE / `REV:tz` при create: `model_override` IS NULL (проверка `pipeline status --slug <slug>`)
- [ ] ни один из шагов не выполнен «тем же» `agent -p`, что соседний

Для `TZ-WRITE(new)` / `(patch)` — тот же запрет склейки; набор карточек по §5.2 (stabilize/compress в скобках §5.1).

### Шаги 0–4 (воркер)

На каждом Шаге 0–4:

1. `pipeline status --slug <slug>` — статус мог смениться (blocked/archived → стоп).
2. Сверка `version`/`mtime` мастер-ТЗ с диска (см. `cursor-task-context`).
3. На фазах с `agent -p` (`TZ:patch`, `TZ:finalize`, `REV:tz`, …) — сначала `emit-prompt` по контракту «TZ-WRITE: emit-prompt перед agent -p» (exit 0, иначе СТОП).
4. `фоновый invoke-role` на длинных `agent -p`.
5. По успеху — `complete-phase` текущей фазы (metadata: `tz_path`, `tz_version`, `tz_mtime`, `extract_chars` для compress, `cursor_session_ids`).
6. Следующая фаза станет `ready` автоматически (`auto_promote_children`).

D1 ≠ D2: на create `model_override` NULL; Cursor-slug только D2 внутри `agent -p`. Канон GLOSSARY §3.

| Шаг | Фаза | Модель (`agent -p`, не `pipeline init --model`) |
|---|---|---|
| stabilize | TZ:stabilize | — (без agent -p; stat/YAML) |
| 0 | TZ:compress | deepseek-v4-flash-0731 (оркестратор) |
| TZ-WRITE | TZ:patch | cursor-grok-4.6-high (`--resume`) |
| REV | REV:tz | claude-sonnet-5-medium |
| finalize | TZ:finalize | cursor-grok-4.6-high — запись `TZ/<Tool>/<Tool>_TZ.md` + `MAIN_TZ_INVENTORY.md` |

### TZ-WRITE (`TZ:patch`, `TZ:finalize`): emit-prompt перед `agent -p`

Перед **любым** `agent -p` на фазах `TZ:patch` и `TZ:finalize` (по инструменту):

- `pipeline emit-prompt --slug <slug> --phase <PHASE> --out /tmp/task.md
- exit 0 → **скопировать блок `context-used:` из `/tmp/task.md` в `journal.md`** (G2/AC-H06), затем `agent -p "$(cat /tmp/task.md)" -f --model <МОДЕЛЬ> --workspace <ABS_DIR> --output-format json`
- exit ≠ 0 → **СТОП**, `agent -p` не вызывать
- перед `complete-phase` фазы TZ-WRITE / `REV:tz`: `pipeline_context_bundle.py pipeline check --slug <slug> --phase <PHASE> <slug>` — exit 0 обязателен, иначе complete запрещён (G2)

Легальный `agent -p` — только от файла `--out` (`$(cat /tmp/task.md)`), не произвольная строка в `-p`.

**Обхода context-bundle нет (решение Саши 26.09, без исключений):** ни `flag-waived`, ни `--force` / `--force-bypass-sasha-ok` как обход тройки digest+GLOSSARY+мастер-ТЗ; `emit-prompt`/`check` блокируют всегда. (`flag-waived: Sasha` для skip `REV:tz` — отдельный механизм, не context-bundle.)

`TZ:finalize` — роль архитектора, не исполнителя HF. Перед записью master-ТЗ воркер `TZ:finalize`:

1. `pipeline status --slug <slug>` текущей и родителей.
2. Parents: `TZ:compress` done, `TZ:patch` done, и (`REV:tz` done **или** waive `flag-waived: Sasha`). Если REV-карточки нет и кейс DEV с opt REV — parent = `TZ:patch` (как DPK граф `parents=[REV:tz|TZ:patch]`).
3. Любой parent не done → **стоп**, не писать ТЗ (карточка не complete).
4. Metadata complete: `role=архитектор`, `model=cursor-grok-4.6-high`, `cursor_session_ids`, `tz_path`/`tz_version`/`tz_mtime` (PI B3).

**Усиление:** TZ `agent -p` без корня `DEV/<slug>` → **стоп** (не создавать корень «по памяти»).

**Промпт архитектора TZ-WRITE** (то, что попадает в `/tmp/task.md`): «исполняй поставленную задачу; не строй граф и не создавай недостающие карточки; выбор LIGHT / смену `--case` / skip фаз не делай — это оркестратор; вопросы Саше — через оркестратора» (AC-H03/H09).

### HITL-вопросы (процедура H / R3)

**Запрет** `interrupt(kind=needs_input)` на TZ-фазах и HF-фазах: бриф и вопросы — **в TG** через оркестратора (`BRF:*`) **и** durable на корне. Любой вопрос архитектора/воркера → на корне `open-questions: Q-n: … status=open` + пост в origin (один вопрос, варианты, рекомендация); `interrupt` **корня** `review-required: operator-action: answer:Q-n`. Не `needs_input` на TZ/HF. Не додумывать бриф за Сашу.

Гейты Саши — только `$GATE:*` через `journal.md` + `interrupt(reason="review-required: …")`. Снятие: ответ/фраза в Telegram **или** unblock на дашборде — равнозначны; Сирень: `journal.md` + `operator-done`. Повторное снятие — no-op.

**HITL-приёмка (AC-009-класс) — легальная пауза, не блок-цикл:** на HITL-гейте после успешного ревью воркер/ревизор **блокирует** фазу `kind=needs_input` и ждёт Сашу (например «по 12 инструментам нужна твоя реплика „принят"»). Это НЕ зависание и НЕ воркер-цикл: на HITL оркестратор ставит `waiting_operator` (см. `dev-workflow`). Сторож и `pipeline status` трактуют `blocked(needs_input)` как **«ждёт Сашу»**, а не «подвисла». Не путать с техническим `needs_input`-rekind (`dependency` без живого родителя) — тот по-прежнему эскалируется в triage как невозможный wait.

### После TZ:finalize

Порядок **одного хода** (не параллельно):

1. **СНАЧАЛА** — нумерованный список `AC-001`…`AC-NNN` **дословно** из master-ТЗ в **диалог = origin-топик** графа (не ops-канал Monitoring `:7`, не Errors `:11112`; если origin сам `:7` — дубля в другой топик нет). Показ AC ≠ ожидание **(класс S)**: доставка артефакта, не стоп Саши. Для AC с `depends: operator:<verb>` — в origin явно: «эти AC закрываются только после вашего `<verb>`; граф не станет done без operator-done + evidence».
2. **ЗАТЕМ** — на корень и `GATE:take-into-work` машинный блок `operator-holds:` (все O-AC из пакета, `status=open` на finalize) для строк `depends: operator:<verb>` в master-ТЗ; плюс `journal.md` payload на `GATE:take-into-work` = тот же список AC (маркер `auto-pass: ac-shown`). Hold на take-into-work **не** ставить — это показ (S) + предупреждение.
3. `GATE:take-into-work` — **auto-pass** (`auto-pass: ac-shown`), `complete-phase`, **не** `interrupt` (императив 28.09: старт→финиш, фраза «берём в работу» не стоп). Хвост сам становится `ready` по `parents`.
4. **Манифест vs диск (не ждать HF-хвоста):** если master-ТЗ/`tz_ref` уже на диске и в `MAIN_TZ_INVENTORY.md`, но пути нет в `EcosystemManifest.json` `tools{}` → stub-запись `tools{}` (`status` из инвентаря, не из frontmatter ТЗ) **или** явная карточка `ORCH:shared-state` с AC «`tools.<tz_ref>` зарегистрирован». Полные `links`/контракты — после auto take-into-work / ORCH хвоста.

Hermes-feature стартует без снятия гейта Сашей: хвост уже в рецепте; `pipeline next` после `GATE:take-into-work` done.

### Гейты — оба канала

`GATE:take-into-work` и `GATE:done` — **always auto** (auto-pass по канону: `ac-shown` / preflight exit 0 **после снятия operator-holds и пустых open-questions**). Снятие Сашей / фраза «готово» на них — идемпотентный no-op (гейт уже done). Hold класса O = fail preflight (`review-required: operator-action:<verb>`), не never-auto гейт. `GATE:plan-approve` — always auto (`auto-pass: architect-plan`). **Не auto** (кризисный HITL): `GATE:go`, `GATE:block-accept`, IDEA `blocked`, crisis-block корня (`review-required: crisis`). Повторное снятие — no-op.

### Ручной feed идеи (бэклог)

Два режима — **не смешивать**. См. `TZ/DialogBacklogToKanban/DialogBacklogToKanban_TZ.md`.

#### A) «Положить в бэклог» / «в triage» (passive-inbox)

Триггеры: «положи в бэклог», «положить в triage», «сохрани идею в бэклог», миграция. Показ triage («бэклог», «что в бэклоге») — скиллы `backlog-collector` / `backlog-analyst` (READ only). **Без** слова «разбери».

1. Passive-запись в IDEA-triage (Б28 DevWorkflow_TZ) для `IDEA/<slug>` — без DEV-`pipeline init`.
2. **Не** создавать child `IDEA:analyze`.
3. **Не** запускать `IDEA:analyze` — запись остаётся в triage.
4. Body при ручном feed: без `migrate:passive` (это маркер миграции); idempotency: `dialogbacklog-feed:<iso-timestamp>:<short-hash>`.

#### B) «Разбери идею» (analyze)

Триггеры: «разбери идею», «разбери bk-NNN», «разбери <slug>`. **Не** запускать DEV-граф до «берём в работу» по заключению.

1. Если записи `IDEA/<slug>` нет — создать в triage (Б28).
2. Оркестратор: рецепт с фазой `IDEA:analyze` (RESEARCH/IDEA, Б28).
3. `pipeline next` → `IDEA:analyze` → emit-prompt → invoke-role; без автопромоута без оркестратора.
4. Заключение в `journal.md` и origin; `WAIT_SASHA` до решения Саши.
5. «Берём в работу» → `complete-phase` `IDEA:analyze` → `pipeline init` DEV/CHANGE; IDEA → `done`.

Idempotency analyze: `devpipe:idea:<slug>:analyze`.

**Запрет:** на passive-inbox с `migrate:passive` без явного «разбери» — **не** создавать `IDEA:analyze`.

### TZ drift / reclaim

Расхождение disk vs `_state.json` → `journal.md`: `TZ drift: …` + `interrupt(kind=dependency, reason="TZ master changed on disk")`. Mid-flight bump → пересборка той же фазы с новым `tz_version` в рецепте; старый прогон — `superseded` в journal.

## Ключевые инварианты (топ-5)

1. **Один master-файл на инструмент:** `TZ/<Tool>/<Tool>_TZ.md`. Доработка = секция внутри, не новый файл.
2. **Латиница-only** для новых имён файлов/папок. Версия — только во frontmatter.
3. **Содержательный текст ТЗ пишет только архитектор (cursor-grok-4.6-high через Cursor).** Исполнитель (composer-2.5) / координатор (composer-2.5) — механика (переносы, frontmatter, инвентарь).
4. **Согласование ТЗ ≠ команда на реализацию.** После `TZ:finalize` AC показ в origin, `GATE:take-into-work` auto-pass, поезд идёт сам — отдельной фразы «берём в работу» не ждём (императив 28.09).
5. **`TZ/<Tool>/` содержит ТОЛЬКО ТЗ-документы.** Брифы, research, runtime-json — в папке инструмента.
6. **Reuse-first: новые сущности — только на согласование (см. references/reuse-first-rule.md).**

## Приложения к ТЗ

Справочные материалы (реестры, бриф-решения, таблицы анализа) — сохранять в `TZ/<Tool>/appendix_<тема>_<YYYYMMDD>.md`. В master-ТЗ добавлять таблицу `## Приложения к ТЗ`.

## Быстрая проверка (smoke)

«Создай ТЗ для `FooBar`» → файл должен быть `~/WorkVault/Hermes-Backlog/TZ/FooBar/FooBar_TZ.md` (латиница, без v-суффикса), `MAIN_TZ_INVENTORY.md` обновлён. Если нет — процедура нарушена.

## Связанные файлы

- `references/cursor-cli-patterns.md` — справочник вызовов Cursor CLI (флаги, модели, JSON, сессии, ошибки)
- `references/cursor-cli.md` — установка, аутентификация, pitfall'ы Cursor CLI
- `references/reuse-first-rule.md`
- `references/contracts-standard.md` — стандарт раздела `## Контракты экосистемы`

## Verification Checklist

- [ ] Новое ТЗ по пути `TZ/<Tool>/<Tool>_TZ.md` (латиница, без v-суффикса)
- [ ] `MAIN_TZ_INVENTORY.md` обновлён в той же операции
- [ ] Содержательный текст писал архитектор (cursor-grok-4.6-high через Cursor); механика — исполнитель (composer-2.5) / координатор (composer-2.5)
- [ ] Согласование ≠ реализация (после `TZ:finalize` AC показ в origin → `GATE:take-into-work` auto-pass, фразу «берём в работу» не ждём)
- [ ] После записи ТЗ — `mofs-index index docs` (инкрементально)
- [ ] В цепочке ТЗ→бриф→обновление каждый Cursor CLI вызов явно помечен «правка ТЗ» / «начинаю реализацию»
- [ ] Приложения к ТЗ — в `appendix_*.md`, таблица в master-ТЗ обновлена
- [ ] Если ТЗ вводит новую сущность/приложение — явно помечено „требует согласования Саши“, не внедрено как решённое.
- [ ] Раздел "## Контракты экосистемы" заполнен по стандарту (references/contracts-standard.md), или явно "Нет внешних контрактов" — **для новых ТЗ** (не ретрофит исторических при DECOMM)
- [ ] Новый несекретный конфиг-ключ инструмента — только в `~/WorkVault/Registries/EcosystemConfig.yaml` + `EcosystemConfig.schema.json`; литерал пути/модели/токена в коде и новый per-tool `.env` = дефект; dual-read (`config.overlay.yaml`) запрещён для **новых** tools (сразу `unified_only` через лоадер)
