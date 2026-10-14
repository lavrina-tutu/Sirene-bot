---
name: dev-workflow
version: 0.3.2
description: DevWorkflow orchestration (file pipeline + 10 cases)
---

# Dual-path (Блок F)

Пока `tools.dev_workflow.orchestration.mode` ≠ `workflow-only`:
- не `pipeline init` для слагов вне `orchestration.pilot_slugs` (W1: `[]`);
- если slug ∈ `pilot_slugs` и нет живого канбан-running — **стоп**, веди через этот скилл;
- иначе — `hermes-feature` / `tz-workflow` + канбан;
- два поезда на одном slug запрещены.

# dev-workflow

Маршрутизатор процесса разработки (10 кейсов). Канон: `references/canon.md`.

## Триггеры

разработай · доработай · почини · напиши ТЗ · исследуй · в бэклог → таблица в `references/cases-guide.md`.

## Цикл (Б16)

Бриф в TG → `pipeline init` → `pipeline next` → WORK: `emit-prompt` → `invoke_role` → `complete-phase` или `interrupt`. AUTO_GATE по улике. WAIT_SASHA — стоп.

## REV (Б16.1)

После `TZ:patch` / `HF:plan` → `invoke_role --role reviewer`. `REQUEST-CHANGES` → не `complete-phase` REV.

## Запреты

Не склеивать фазы. Не `agent -p` в обход `invoke_role`. Не `--continue` cursor-cli.

## HITL

Только глаголы Б6.3 (`references/canon.md`). Origin, не Errors.

## После hermes update

`restore-all-skills.sh` + `pipeline status --check`.

См. `references/invoke.md`, `references/context.md`, `references/rollback.md`.
