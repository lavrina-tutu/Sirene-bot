---
name: tz-workflow
description: "Use when: создание, доработка, архивация ТЗ и инфраструктурных планов. Triggers: ТЗ, техническое задание, спецификация, доработка ТЗ, дорабатываем ТЗ, правки в ТЗ, обнови ТЗ, архивация ТЗ, план установки, инфраструктурный план, добавь в ТЗ, секция в ТЗ, примечание в ТЗ."
version: 2.1.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [workflow, tz, workvault, hermes, documentation]
    related_skills: [hermes-feature, workvault-rag, hermes-ops]
---

# tz-workflow

## Overview

Единые правила хранения, версионирования и архивации ТЗ инструментов Hermes/USERTOOLS, включая инфраструктурные планы. Содержательная работа — через Cursor CLI (`agent -p`).

## When to Use

- Создание/доработка/архивация ТЗ инструмента
- Задача касается USERTOOLS (`MoveFromFF`, `AggregateFromMeetings`, …) и упоминается «ТЗ»
- Обновление реестра `MAIN_TZ_INVENTORY.md`
- План установки/настройки (RAG, systemd, MCP-интеграции) — по той же схеме `TZ/<Topic>/<Topic>_TZ.md`

Не применять: рабочие данные vault (`Projects/`, `People/`, `Meetings/`), git-репозитории конфига.

**Связь с hermes-feature:** после финализации ТЗ и получения «берём в работу» — перейти к hermes-feature для реализации.

## Workflow (Шаги 0–4)

### Модели (Cursor CLI) — раздельные задачи

**Инвариант:** один вызов `agent -p` = одна модель = одна роль. Сирень координирует цепочку, **не смешивает** модели в одном промпте.

| Шаг | Модель | Когда |
|---|---|---|
| Шаг 0 — Компрессия ТЗ | `composer-2.5` | Перед архитектурой: экстракт master-ТЗ 3–5 КБ |
| Шаг 1 — Анализ и драфт | `cursor-grok-4.6-high` | Начало каждого нового ТЗ (вход: digest + экстракты Шага 0) |
| Шаги 2–4 — Архитектура, написание, финализация | `cursor-grok-4.6-high` | Архитектурные решения и текст ТЗ |
| Механические задачи | `composer-2.5` | Операторские кроны, инвентарь без семантики |

### Шаг 0 — Компрессия ТЗ (отдельная задача Cursor)

- **Промпт:** `~/WorkVault/Registries/tz-compressor-prompt.md`
- **Модель:** `composer-2.5`.
- **Вход:** полный текст master-ТЗ инструмента (+ зависимые ТЗ, если связаны).
- **Выход:** «актуальная спецификация» 3–5 КБ, full-coverage (100% сущностей/полей/API/лимитов, имена дословно).
- **Без кэша:** экстракты не сохраняются между задачами — только в памяти сессии до передачи архитектору.
- Если исходное ТЗ упоминает предложения новых инструментов/приложений/сущностей — сохранить в экстракте пометку [NEW-ENTITY], не потерять при сжатии.
- **Контекст экосистемы:** опционально `EcosystemManifest.digest.md` для связей (не вместо экстракта своего ТЗ).

```bash
cd ~/WorkVault/Hermes-Backlog/TZ && agent -p "Шаг 0 tz-workflow: компрессия ТЗ по tz-compressor-prompt.md для [Tool]. Полный текст ТЗ: …" \
  -f --model composer-2.5 --output-format json
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
  - [ ] Раздел "## Контракты экосистемы" заполнен по стандарту (references/contracts-standard.md), или явно "Нет внешних контрактов"
  - [ ] Открытые вопросы закрыты или зафиксированы в `## Открытые вопросы`
  - [ ] Краткость + полнота: ни одной лишней фразы, ни одной пропущенной детали

### Цикл разработки

1. **Бриф** — вопросы по процедуре H, фиксация решений в чате и драфте ТЗ.
2. **ТЗ** — Шаги 2-4 через Cursor CLI (`agent -p`), версионирование, регистрация в `MAIN_TZ_INVENTORY.md`.
3. **Обновление ТЗ** — после каждого брифа исполнитель (composer-2.5) вносит правки; архитектурные изменения — архитектор (cursor-grok-4.6-high через Cursor CLI).
4. **Реализация** — ждать явного «берём в работу». Реализация — отдельный процесс через hermes-feature.

### Правила автономии

- **Side-effect только по императиву** — никаких правок без явного «делай».
- **Кроны НЕ создаются автоматически** — перечисляются в отчёте, создаются только по «ставь».
- **НЕТ шорткатов даже для багфиксов с известным root cause.** Прецедент (MoveFromLoop v0.4.2, 07.08.2026): агент с готовой диагностикой от архитектора предложил «использовать диагностику как spec → сразу hermes-feature» или «короткий бриф вместо ТЗ» — пользователь отклонил. **Правило:** для ЛЮБОЙ задачи доработки ТЗ ИЛИ реализации — всегда tz-workflow (Шаги 1-4 → ТЗ-файл → MAIN_TZ_INVENTORY.md) → ждать «берём в работу» → hermes-feature. Нет исключений для багфиксов, хотфиксов, мелких правок. Если сомнения в правильном варианте — **спросить Сашу**, НЕ предлагать альтернативы.

## Канбан-шаг

> DevKanbanPipeline (`TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md`). Все карточки `assignee=default`. Граф задаёт скилл, не decomposer (`auto_decompose: false`).

### Когда создавать граф

Создавать граф `DEV/<slug>/…`, если: цикл 2+ шагов tz-workflow/hermes-feature; работа должна пережить обрыв сессии; есть гейт Саши; нужен audit trail. **Не создавать** для одношагового ответа / `delegate_task` / однострочного вопроса Саши.

### Вход триггера (до Шага 0)

Если графа ещё нет — `kanban_create` корня `DEV/<slug>` + фазы TZ:* + `GATE:take-into-work` с `parents=[...]` **в том же create** (сначала родители, `task_id` из return, затем дети). Все карточки `assignee=default`.

Граф TZ-фаз (parents обязательны):

```
DEV/<slug>                          корень (живёт до GATE:done)
├─ TZ:stabilize
├─ TZ:compress          parents=[TZ:stabilize]
├─ TZ:analyze           parents=[TZ:compress]
├─ TZ:architect         parents=[TZ:analyze]
├─ TZ:finalize          parents=[TZ:architect]
└─ GATE:take-into-work  parents=[TZ:finalize]
```

`workspace_kind`: `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` для TZ-шагов. Skills на карточке: `tz-workflow`, `cursor-cli`, `cursor-task-context`. Idempotency: `devpipe:<slug>:<phase>:<tz_version_or_none>`.

### Шаги 0–4 (воркер)

На каждом Шаге 0–4:

1. `kanban_show()` — статус мог смениться (blocked/archived → стоп).
2. Сверка `version`/`mtime` мастер-ТЗ с диска (см. `cursor-task-context`).
3. `kanban_heartbeat` на длинных `agent -p`.
4. По успеху — `kanban_complete` текущей фазы (metadata: `tz_path`, `tz_version`, `tz_mtime`, `extract_chars` для compress, `cursor_session_ids`).
5. Следующая фаза станет `ready` автоматически (`auto_promote_children`).

| Шаг | Фаза | Модель |
|---|---|---|
| 0 | TZ:compress | composer-2.5 |
| 1 | TZ:analyze | cursor-grok-4.6-high |
| 2–4 | TZ:architect | cursor-grok-4.6-high (`--resume`) |
| 4 | TZ:finalize | cursor-grok-4.6-high — запись `TZ/<Tool>/<Tool>_TZ.md` + `MAIN_TZ_INVENTORY.md` |

Шаг 4 — роль архитектора на карточке `TZ:finalize`, не исполнителя HF.

### HITL-вопросы (процедура H / R3)

Вопрос Саше → `kanban_comment` с полным контекстом + `kanban_block(kind=needs_input, reason=<один вопрос>)`. **Не** `clarify` (у воркера нет живого пользователя). Снятие: ответ Саши в Telegram **или** unblock на дашборде канбана — равнозначны; Сирень: `kanban_comment` + `kanban_unblock`. Повторное снятие — no-op.

### После TZ:finalize

- **Пошаговый ход** — не стартовать hermes-feature; `GATE:take-into-work` → `kanban_comment` (путь ТЗ) + `kanban_block(reason="review-required: ждать «берём в работу»")`.
- **Режим «делай в 1 проход»** (ТЗ на диске, открытых вопросов нет, фраза Саши «делай в 1 проход»): `GATE:take-into-work` — comment `auto-pass: one-pass mode` + `kanban_complete` без block; переход к HF-ветке (создаёт hermes-feature).

### Гейты — оба канала

`GATE:take-into-work` снимается фразой «берём в работу» в Telegram **или** unblock/approve на дашборде канбана. Оба канала действуют одновременно; на конкретном гейте Саша выбирает один. `kanban_complete` на гейте — только после unblock: `approved by Sasha` (или `auto-pass: one-pass mode`).

### Ручной feed идеи (бэклог)

Триггер: явная фраза Саши «положить в бэклог / triage / разбери идею». **Не** запускать DEV-граф.

1. `kanban_create` корня `IDEA/<slug>` + child `IDEA:analyze` (`--triage` на create).
2. Сразу в том же ходе перевести `IDEA:analyze` в `ready` (без decomposer): `kanban_specify` / `hermes kanban specify <id>` (triage→todo→ready); **не** `promote` с triage.
3. Silent-воркер `default` → `agent -p --model cursor-grok-4.6-high` → заключение в `kanban_comment` → `kanban_block(reason="review-required: заключение по идее, ждать Сашу")`.
4. «Берём в работу» по заключению (Telegram **или** дашборд) → `IDEA:analyze` complete → оркестратор создаёт граф `DEV/<slug>` обычного цикла; корень `IDEA/<slug>` → `done`/`archived`.

Idempotency: `devpipe:idea:<slug>:analyze`.

### TZ drift / reclaim

Расхождение disk vs card → comment `TZ drift: …` + `kanban_block(kind=dependency, reason="TZ master changed on disk")`. Mid-flight bump → `hermes kanban reclaim` + comment «не retry этой карточки, TZ bumped» + **новая** child той же phase с обновлёнными parents; старую — `archived` с summary `superseded`.

## Ключевые инварианты (топ-5)

1. **Один master-файл на инструмент:** `TZ/<Tool>/<Tool>_TZ.md`. Доработка = секция внутри, не новый файл.
2. **Латиница-only** для новых имён файлов/папок. Версия — только во frontmatter.
3. **Содержательный текст ТЗ пишет только архитектор (cursor-grok-4.6-high через Cursor).** Исполнитель (composer-2.5) / координатор (composer-2.5) — механика (переносы, frontmatter, инвентарь).
4. **Согласование ТЗ ≠ команда на реализацию.** Ждать отдельного «берём в работу».
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
- [ ] Согласование ≠ реализация (ждём «берём в работу»)
- [ ] После записи ТЗ — `mofs-index index docs` (инкрементально)
- [ ] В цепочке ТЗ→бриф→обновление каждый Cursor CLI вызов явно помечен «правка ТЗ» / «начинаю реализацию»
- [ ] Приложения к ТЗ — в `appendix_*.md`, таблица в master-ТЗ обновлена
- [ ] Если ТЗ вводит новую сущность/приложение — явно помечено „требует согласования Саши“, не внедрено как решённое.
- [ ] Раздел "## Контракты экосистемы" заполнен по стандарту (references/contracts-standard.md), или явно "Нет внешних контрактов"
