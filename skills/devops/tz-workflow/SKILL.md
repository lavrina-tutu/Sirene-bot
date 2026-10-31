---
name: tz-workflow
description: "Use when: создание/доработка/архивация ТЗ и инфрасхем"
version: 2.11.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [workflow, tz, workvault, hermes, documentation]
    related_skills: [hermes-feature, workvault-rag, hermes-ops]
---

# tz-workflow

## Dual-path (DevWorkflow W2)

Пока `orchestration.mode` ≠ `workflow-only`: не `pipeline init` вне `pilot_slugs`; slug в `pilot_slugs` → стоп, отдать `dev-workflow`; иначе канбан + `hermes-feature` / `tz-workflow`. Два поезда на slug запрещены; пилот — один slug за раз.

Конфиг: `EcosystemConfig.yaml` → `tools.dev_workflow.orchestration`. W1: `pilot_slugs: []`, `mode: kanban-primary`. Откат W2: `git checkout` SKILL.md + `restore-all-skills.sh`. Баннер 10–15 строк не переписывает тела старых скиллов; действует только маршрутизация. Стоп при живом `kanban-running` на том же slug.

## Термины

Перед первым `PREFIX:фаза` читать `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`. Имена фаз, ролей и скиллов — только из канона; голые `TZ/HF/ORCH/DEV` без двоеточия запрещены.

## Overview

Единые правила хранения, версионирования и архивации ТЗ инструментов Hermes/USERTOOLS и инфраструктурных планов. Содержательный текст ТЗ пишет архитектор через Cursor CLI (`agent -p`); механика остаётся координатору/исполнителю.

## When to Use

- Создание, доработка или архивация ТЗ инструмента.
- Задача про USERTOOLS (`MoveFromFF`, `AggregateFromMeetings`, …) и упоминается «ТЗ».
- Обновление `MAIN_TZ_INVENTORY.md`.
- План установки/настройки (RAG, systemd, MCP) по схеме `TZ/<Topic>/<Topic>_TZ.md`.

Не применять к рабочим данным vault (`Projects/`, `People/`, `Meetings/`) и git-репозиториям конфигурации.

После `TZ:finalize` AC дословно показываются в origin-топике, `GATE:take-into-work` auto-pass, затем `hermes-feature` стартует без отдельной фразы Саши.

## Workflow (Шаги 0–4)

- Один `invoke-role` = одна модель = одна роль; модели не смешивать.
- Валидацию и рекомендации по постановке передавать архитектору; Сирень не подменяет его решения.
- TZ-WRITE не склеивать: `TZ:stabilize`, `TZ:compress`, `TZ:patch`, `REV:tz`, `TZ:finalize` — отдельные фазы/вызовы; канон кейсов — GLOSSARY §2/§5.1.
- `TZ:compress` выполняет оркестратор без Cursor: полный master-ТЗ → актуальная спецификация 3–5 КБ, full-coverage, без кэша; новые сущности сохраняются с `[NEW-ENTITY]`.
- `TZ:patch`/`TZ:finalize` — архитектор; `REV:tz` — ревизор по умолчанию; механика, inventory и cron-операции — координатор. На create `model_override`/`--model` не задавать; Cursor-модель указывать только внутри `agent -p`.
- Шаги 1–4, подробный чеклист финализации, открытый бриф и правила автономии: [references/workflow-phases.md](references/workflow-phases.md).

## DevWorkflow-шаг

Граф `DEV/<slug>` создавать при многошаговом цикле, необходимости пережить обрыв, гейте Саши или audit trail; не создавать для одношагового ответа, `delegate_task` или однострочного вопроса. Бриф закрывается в TG; после `GATE:brief-closed` оркестратор одним `pipeline init` создаёт полный рецепт из GLOSSARY, с родителями и preflight G4. Живой `_state.json` не дублировать.

Полный граф: `TZ:stabilize → TZ:compress → TZ:patch → REV:tz → TZ:finalize → GATE:take-into-work → HF:plan → REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done`. Для LIGHT и BUGFIX действуют отдельные канонические хвосты; `GATE:take-into-work` всегда auto-pass после показа AC.

На каждой фазе проверять status и `version`/`mtime`, применять `emit-prompt`/context-bundle перед Cursor, после успеха делать `complete-phase` с metadata и ждать auto-promote. Подробности графа, LIGHT/BUGFIX, origin, worker, TZ-WRITE, HITL, gates, feed и drift: [references/devworkflow-operations.md](references/devworkflow-operations.md).

## Ключевые инварианты

1. Один master-файл на инструмент: `TZ/<Tool>/<Tool>_TZ.md`; доработка — секция внутри.
2. Новые имена файлов/папок — только латиница; версию хранить только во frontmatter.
3. Содержательный текст пишет архитектор (`cursor-grok-4.6-high` через Cursor); исполнитель/координатор делают механику.
4. Согласование ТЗ не является командой реализации: после finalize AC показываются в origin, gate auto-pass, поезд идёт сам.
5. `TZ/<Tool>/` содержит только ТЗ-документы; брифы, research и runtime-json — в папке инструмента.
6. Reuse-first: новые сущности/приложения только после согласования Саши — [references/reuse-first-rule.md](references/reuse-first-rule.md).

## Приложения к ТЗ

Справочные материалы хранить в `TZ/<Tool>/appendix_<тема>_<YYYYMMDD>.md`; в master-ТЗ поддерживать таблицу `## Приложения к ТЗ`. Полные smoke/checklist и инварианты: [references/quality-and-checklist.md](references/quality-and-checklist.md).

## Быстрая проверка (smoke)

«Создай ТЗ для `FooBar`» → `~/WorkVault/Hermes-Backlog/TZ/FooBar/FooBar_TZ.md`, латиница, без v-суффикса, `MAIN_TZ_INVENTORY.md` обновлён.

## Связанные файлы

- [references/workflow-phases.md](references/workflow-phases.md) — Шаги 0–4, модели, бриф, финализация, автономия.
- [references/devworkflow-operations.md](references/devworkflow-operations.md) — графы DevWorkflow, LIGHT/BUGFIX, гейты, HITL, idea feed, drift.
- [references/quality-and-checklist.md](references/quality-and-checklist.md) — приложения, smoke и Verification Checklist.
- [references/cursor-cli-patterns.md](references/cursor-cli-patterns.md) — канонический справочник вызовов Cursor CLI.
- [references/cursor-cli.md](references/cursor-cli.md) — установка, аутентификация и pitfall'ы Cursor CLI.
- [references/reuse-first-rule.md](references/reuse-first-rule.md) — правило переиспользования.
- [references/contracts-standard.md](references/contracts-standard.md) — стандарт `## Контракты экосистемы`.

## Verification Checklist

- [ ] Путь `TZ/<Tool>/<Tool>_TZ.md`, латиница, без v-суффикса; `MAIN_TZ_INVENTORY.md` обновлён.
- [ ] Содержательный текст — архитектор; механика — исполнитель/координатор.
- [ ] После `TZ:finalize`: AC показаны в origin → `GATE:take-into-work` auto-pass; «берём в работу» не ждём.
- [ ] После записи: `mofs-index index docs` (инкрементально).
- [ ] Каждый Cursor CLI вызов явно помечен «правка ТЗ» или «начинаю реализацию».
- [ ] Приложения лежат в `appendix_*`, таблица master-ТЗ обновлена.
- [ ] Новые сущности/приложения помечены «требует согласования Саши» и не внедрены как решённые.
- [ ] Для новых ТЗ заполнен `## Контракты экосистемы` по [contracts-standard.md](references/contracts-standard.md) или явно указано отсутствие внешних контрактов; исторические ТЗ при DECOMM не ретрофитить.
- [ ] Новый несекретный конфиг-ключ — только в `~/WorkVault/Registries/EcosystemConfig.yaml` и `EcosystemConfig.schema.json`; литералы пути/модели/токена и новый per-tool `.env` запрещены; `config.overlay.yaml` dual-read для новых tools запрещён.
