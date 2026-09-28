---
name: tz-workflow
description: "Use when: создание, доработка, архивация ТЗ и инфраструктурных планов. Triggers: ТЗ, техническое задание, спецификация, доработка ТЗ, дорабатываем ТЗ, правки в ТЗ, обнови ТЗ, архивация ТЗ, план установки, инфраструктурный план, добавь в ТЗ, секция в ТЗ, примечание в ТЗ."
version: 2.7.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [workflow, tz, workvault, hermes, documentation]
    related_skills: [hermes-feature, workvault-rag, hermes-ops]
---

# tz-workflow

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

### Модели (Cursor CLI) — раздельные задачи

**Инвариант:** один вызов `agent -p` = одна модель = одна роль. Сирень координирует цепочку, **не смешивает** модели в одном промпте.

**Валидация и рекомендации по постановке — только от архитектора (требование 2).** Сирень не предлагает своё мнение/варианты по постановке и архитектуре задач — передаёт архитектору (`cursor-grok-4.6-high` через Cursor CLI), выполняет по его рекомендациям. Фактологические вопросы Саше — текстом (процедура H / R3).

**Запрет склейки TZ-WRITE:** промпты вида «напиши ТЗ целиком», «весь TZ-WRITE одним `agent -p`», склейка `TZ:compress`+`TZ:patch`+`TZ:finalize` (и тем более с ролью исполнителя) — **запрещены**. `TZ-WRITE(mode)` = отдельные карточки и отдельные `agent -p` по GLOSSARY §5.1. Один вызов закрывает **ровно одну** фазу из `{TZ:stabilize, TZ:compress, TZ:patch, REV:tz, TZ:finalize}`.

> **Колонка «Модель»** — внутренний `agent -p --model`, **не** `kanban_create --model`. На карточках `TZ:*` / `REV:tz`: `model_override` = NULL (воркер = default Hermes).

| Шаг | Роль | Модель (`agent -p`, не kanban) | Когда |
|---|---|---|---|
| BRF | оркестратор | deepseek (TG, без Cursor) | диалог; варианты постановки — сначала agent -p cursor-grok-4.6-high, затем ответ Саше |
| TZ:stabilize | воркер (диск) | — (без agent -p) | path, version, mtime в metadata |
| Шаг 0 — Компрессия ТЗ | оркестратор (Сирень) | `deepseek-v4-flash-0731` (осн. Hermes) | `TZ:compress`: экстракт master-ТЗ 3–5 КБ, без Cursor |
| TZ-WRITE | архитектор | `cursor-grok-4.6-high` | `TZ:patch` / `TZ:finalize`: анализ, архитектура, текст ТЗ |
| REV | ревизор | `claude-sonnet-5-medium` | `REV:tz` — по умолчанию во всех dev-задачах; искл. лёгкие BUGFIX/SKILL-CHANGE ≤3 файла (08.09.2026) |
| Механические задачи | координатор | `composer-2.5` | Операторские кроны, инвентарь без семантики |

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

### Паттерн вызова Cursor CLI

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

## Канбан-шаг

> DevKanbanPipeline (`TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md`). Все карточки `assignee=default`. Граф задаёт скилл, не decomposer (`auto_decompose: false`).

### Когда создавать граф

Создавать граф `DEV/<slug>/…`, если: цикл 2+ шагов tz-workflow/hermes-feature; работа должна пережить обрыв сессии; есть гейт Саши; нужен audit trail. **Не создавать** для одношагового ответа / `delegate_task` / однострочного вопроса Саши.

### Вход триггера (после BRIEF-CLOSE)

Бриф (`BRF:full` / `light` / `delta` / `scope` / `confirm`) — **только в TG** через оркестратора (Сирень), не карточка. После `GATE:brief-closed` — **ОДИН `kanban_create`-батч полного графа кейса**: корень `DEV/<slug>` + `TZ-WRITE(mode)` + `GATE:take-into-work` + `PLAN-IMPL-TAIL` (или `-LIGHT` по кейсу GLOSSARY §2) **в том же create** (сначала родители, `task_id` из return, затем дети). Все карточки `assignee=default`. Режим `mode` — из кейса GLOSSARY §2 (`new` / `full` / `patch` / `freeze`).

**Полный граф одним батчем сразу после брифа** (императив 28.09, доработка A плана process-rework): второй «разворот хвоста» после гейта NOT (дыра unfold, дети `children=[]`). Диспетчер сам промоутит по `parents`. Доработка A: весь кейсовый граф — руками одного батча, `GATE:take-into-work` входит в него и авто-проходится после `TZ:finalize`.

- **Запрет `model` на create:** на `TZ:*`, `REV:tz`, `HF:*`, `BUG:*` и `IDEA:analyze` — **без** `--model` / `model=` (D1 = NULL, воркер default Hermes; анти-пример: `kanban_create(..., model=cursor-grok-4.6-high)` на `TZ:patch` → HTTP 400 у Hermes-воркера, `protocol_violation`, прецедент `t_2c8ee3b2`). Роли grok/composer — только D2 внутри `agent -p --model …`.
- **Ключ на КАЖДУЮ фазу при create:** `devpipe:<slug>:<phase>:<tz_version_or_none>` (lookup до create, дубль = no-op; rework — суффикс `:rework:<n>:<tz_version>`).

- **Все задачи по умолчанию** после триггера «разработай/доработай/почини» ложатся в план (канбан-граф `DEV/<slug>`) и далее проводятся по канону, без дополнительной команды Саши.
- **Slug-guard (перед `kanban_create` графа `DEV/<slug>`) — проверка активного графа по слагу:** если уже есть незакрытый граф (карточки в `todo|ready|running|blocked`, не `done`/`archived`) на тот же `<slug>` — **НЕ создавать дубль**; reuse существующего графа или `kanban_block` на новый create-интент до разрешения. Дубликаты графа на один слаг запрещены (прецедент pfs-notify-link-unprocessed: 2 параллельных графа).
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

LIGHT-кейсы (BUGFIX-LIGHT / CHANGE-LIGHT ≤3 файла) — короткий хвост в том же батче (GLOSSARY §5.2): `TZ:patch → TZ:finalize → GATE:take-into-work → HF:impl → HF:test → HF:docs-handoff → GATE:done`. Весь граф создаётся одним `kanban_create`-батчем после брифа; второго unfold нет.

`workspace_kind`: `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` для TZ-шагов. Skills на карточке: `tz-workflow`, `cursor-cli`, `cursor-task-context`. Idempotency каждой фазы: `devpipe:<slug>:<phase>:<tz_version_or_none>`.

#### Подписка графа на уведомления (notify-subscribe)

Сразу после `kanban_create` (в том же ходе) подписать набор **R5** (наследования по `parents` **нет** — каждая карточка явно). Фиксированный контракт (топик мониторинга Monitoring :7, группа, Telegram — по умолчанию, без дублей в личный DM):

```bash
hermes kanban notify-subscribe <task_id> \
  --platform telegram --chat-id -1004300127777 --chat-type group \
  --delivery-mode notify+wake --notifier-profile default
```

Уведомитель шлёт в TG **только ключевые терминальные события** (по `TERMINAL_KINDS`: `completed`/`GATE:done`, `blocked`, `gave_up`, `crashed`, `timed_out`) — не каждую фазу графа (шум). Ядро канбана **не трогать**: ни `kanban_db.py`, ни `kanban_db_notify.py`, ни сам список `TERMINAL_KINDS`.

Репорты карточек — только в топик мониторинга (Monitoring :7), без дублей в личный DM, по умолчанию. Отдельное явное указание Саши может переопределить канал подписки конкретного графа.

- **Набор R5:** корень `DEV/<slug>` (или `IDEA/<slug>` при feed) + `GATE:take-into-work` / `GATE:done` + `GATE:go` / `GATE:block-accept` / `IDEA:analyze` → `notify+wake`.
- **Не подписывать:** `TZ:*` / `HF:*` / `REV:*` / `BUG:diagnose` / `ORCH:*` / `RS:*` / `GATE:plan-approve` / `GATE:diagnose-review`.
- Багфикс-батч (`DEV/<slug>` + `BUG:diagnose`): подписать **корень** `DEV/<slug>` (не промежуточные фазы).
- Ручной feed `IDEA/<slug>` + `IDEA:analyze`: корень `IDEA/<slug>` + `IDEA:analyze`.

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

`GLOSSARY` канон — источник истины; этот раздел — сокращённая шпаргалка.

#### Багфикс (кейс BUGFIX / BUGFIX-LIGHT)

Триггер «баг/ошибка/не работает/почини/разберись/cron run failed» — **первый tool-шаг**:
`kanban_create` корня `DEV/<slug>` **И** `BUG:diagnose` в одном create-батче
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
- [ ] на каждой карточке TZ-WRITE / `REV:tz` при create: `model_override` IS NULL (проверка `kanban_show`)
- [ ] ни один из шагов не выполнен «тем же» `agent -p`, что соседний

Для `TZ-WRITE(new)` / `(patch)` — тот же запрет склейки; набор карточек по §5.2 (stabilize/compress в скобках §5.1).

### Шаги 0–4 (воркер)

На каждом Шаге 0–4:

1. `kanban_show()` — статус мог смениться (blocked/archived → стоп).
2. Сверка `version`/`mtime` мастер-ТЗ с диска (см. `cursor-task-context`).
3. На фазах с `agent -p` (`TZ:patch`, `TZ:finalize`, `REV:tz`, …) — сначала `emit-prompt` по контракту «TZ-WRITE: emit-prompt перед agent -p» (exit 0, иначе СТОП).
4. `kanban_heartbeat` на длинных `agent -p`.
5. По успеху — `kanban_complete` текущей фазы (metadata: `tz_path`, `tz_version`, `tz_mtime`, `extract_chars` для compress, `cursor_session_ids`).
6. Следующая фаза станет `ready` автоматически (`auto_promote_children`).

D1 ≠ D2: на create `model_override` NULL; Cursor-slug только D2 внутри `agent -p`. Канон GLOSSARY §3.

| Шаг | Фаза | Модель (`agent -p`, не `kanban_create --model`) |
|---|---|---|
| stabilize | TZ:stabilize | — (без agent -p; stat/YAML) |
| 0 | TZ:compress | deepseek-v4-flash-0731 (оркестратор) |
| TZ-WRITE | TZ:patch | cursor-grok-4.6-high (`--resume`) |
| REV | REV:tz | claude-sonnet-5-medium |
| finalize | TZ:finalize | cursor-grok-4.6-high — запись `TZ/<Tool>/<Tool>_TZ.md` + `MAIN_TZ_INVENTORY.md` |

### TZ-WRITE (`TZ:patch`, `TZ:finalize`): emit-prompt перед `agent -p`

Перед **любым** `agent -p` на фазах `TZ:patch` и `TZ:finalize` (по инструменту):

- `python3 /home/tkachenkoav/WorkVault/Registries/pipeline_context_bundle.py emit-prompt --tool <Name> --task-file <план> --out /tmp/task.md`
- exit 0 → `agent -p "$(cat /tmp/task.md)" -f --model <МОДЕЛЬ> --workspace <ABS_DIR> --output-format json`
- exit ≠ 0 → **СТОП**, `agent -p` не вызывать

Легальный `agent -p` — только от файла `--out` (`$(cat /tmp/task.md)`), не произвольная строка в `-p`.

**Обхода context-bundle нет (решение Саши 26.09, без исключений):** ни `flag-waived`, ни `--force` / `--force-bypass-sasha-ok` как обход тройки digest+GLOSSARY+мастер-ТЗ; `emit-prompt`/`check` блокируют всегда. (`flag-waived: Sasha` для skip `REV:tz` — отдельный механизм, не context-bundle.)

`TZ:finalize` — роль архитектора, не исполнителя HF. Перед записью master-ТЗ воркер `TZ:finalize`:

1. `kanban_show` текущей и родителей.
2. Parents: `TZ:compress` done, `TZ:patch` done, и (`REV:tz` done **или** waive `flag-waived: Sasha`). Если REV-карточки нет и кейс DEV с opt REV — parent = `TZ:patch` (как DPK граф `parents=[REV:tz|TZ:patch]`).
3. Любой parent не done → **стоп**, не писать ТЗ (карточка не complete).
4. Metadata complete: `role=архитектор`, `model=cursor-grok-4.6-high`, `cursor_session_ids`, `tz_path`/`tz_version`/`tz_mtime` (PI B3).

**Усиление:** TZ `agent -p` без корня `DEV/<slug>` → **стоп** (не создавать корень «по памяти»).

### HITL-вопросы (процедура H / R3)

**Запрет** `kanban_block(kind=needs_input)` на TZ-фазах: бриф и вопросы — **только в TG** через оркестратора (`BRF:*`). Воркер TZ-фаз не блокирует карточку вопросом.

Гейты Саши — только `$GATE:*` через `kanban_comment` + `kanban_block(reason="review-required: …")`. Снятие: ответ/фраза в Telegram **или** unblock на дашборде — равнозначны; Сирень: `kanban_comment` + `kanban_unblock`. Повторное снятие — no-op.

### После TZ:finalize

Порядок **одного хода** (не параллельно):

1. **СНАЧАЛА** — нумерованный список `AC-001`…`AC-NNN` **дословно** из master-ТЗ в **origin-топик** (в Monitoring :7 список дублировать). Показ AC ≠ ожидание: это доставка артефакта, не стоп Саши.
2. **ЗАТЕМ** — `kanban_comment` payload на `GATE:take-into-work` = тот же список AC (маркер `auto-pass: ac-shown`).
3. `GATE:take-into-work` — **auto-pass** (`auto-pass: ac-shown`), `kanban_complete`, **не** `kanban_block` (императив 28.09: старт→финиш, фраза «берём в работу» не стоп). Хвост сам становится `ready` по `parents`.
4. **Манифест vs диск (не ждать HF-хвоста):** если master-ТЗ/`tz_ref` уже на диске и в `MAIN_TZ_INVENTORY.md`, но пути нет в `EcosystemManifest.json` `tools{}` → stub-запись `tools{}` (`status` из инвентаря, не из frontmatter ТЗ) **или** явная карточка `ORCH:shared-state` с AC «`tools.<tz_ref>` зарегистрирован». Полные `links`/контракты — после auto take-into-work / ORCH хвоста.

Hermes-feature стартует без снятия гейта Сашей: хвост уже в графе и авто-промоушен запускает его после `GATE:take-into-work` done.

### Гейты — оба канала

`GATE:take-into-work` и `GATE:done` — **always auto** (auto-pass по канону: `ac-shown` / preflight exit 0). Снятие Сашей / фраза «готово» на них — идемпотентный no-op (гейт уже done). `GATE:plan-approve` — always auto (`auto-pass: architect-plan`). **Не auto** (кризисный HITL): `GATE:go`, `GATE:block-accept`, IDEA `blocked`, crisis-block корня (`review-required: crisis`). Повторное снятие — no-op.

### Ручной feed идеи (бэклог)

Два режима — **не смешивать**. См. `TZ/DialogBacklogToKanban/DialogBacklogToKanban_TZ.md`.

#### A) «Положить в бэклог» / «в triage» (passive-inbox)

Триггеры: «положи в бэклог», «положить в triage», «сохрани идею в бэклог», миграция. Показ triage («бэклог», «что в бэклоге») — скиллы `backlog-collector` / `backlog-analyst` (READ only). **Без** слова «разбери».

1. Только `kanban_create` корня `IDEA/<slug>` с `--triage`, `assignee=default`.
2. **Не** создавать child `IDEA:analyze`.
3. **Не** вызывать `kanban_specify` / `promote` — карточка остаётся в `triage`, воркер не берёт.
4. Body при ручном feed: без `migrate:passive` (это маркер миграции); idempotency: `dialogbacklog-feed:<iso-timestamp>:<short-hash>`.

#### B) «Разбери идею» (analyze)

Триггеры: «разбери идею», «разбери bk-NNN», «разбери <slug>`. **Не** запускать DEV-граф до «берём в работу» по заключению.

1. Если корня `IDEA/<slug>` нет — создать с `--triage`.
2. Создать child `IDEA:analyze` с `parents=[корень]`.
3. Сразу в том же ходе: `kanban_specify` / `hermes kanban specify <analyze_id>` (triage→todo→ready); **не** `promote` с triage.
4. Silent-воркер `default` → `agent -p --model cursor-grok-4.6-high` → заключение в `kanban_comment` → `kanban_block(reason="review-required: заключение по идее, ждать Сашу")`.
5. «Берём в работу» по заключению (Telegram **или** дашборд) → `IDEA:analyze` complete → оркестратор создаёт граф `DEV/<slug>` обычного цикла; корень `IDEA/<slug>` → `done`/`archived`.

Idempotency analyze: `devpipe:idea:<slug>:analyze`.

**Запрет:** на карточках с `migrate:passive` в body или passive-inbox без явного «разбери» — **не** specify, **не** создавать `IDEA:analyze`.

### TZ drift / reclaim

Расхождение disk vs card → comment `TZ drift: …` + `kanban_block(kind=dependency, reason="TZ master changed on disk")`. Mid-flight bump → `hermes kanban reclaim` + comment «не retry этой карточки, TZ bumped» + **новая** child той же phase с обновлёнными parents; старую — `archived` с summary `superseded`.

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
