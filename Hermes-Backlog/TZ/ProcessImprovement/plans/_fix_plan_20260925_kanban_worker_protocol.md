# Диагноз: kanban worker rc=0 без terminal (protocol_violation)

```yaml
date: 2026-09-25
graph: DEV/dev-pipeline-ac-criteria
symptom_card: t_2c8ee3b2
related: t_b4cb83bb (TZ:finalize), t_5e0d0b7e (REV:tz)
author: исполнитель (composer-2.5), по плану архитектора
status: canon-guard (П.3 артефакт + П.4 guards); ops П.1 — оркестратор
```

## Симптом

- Карточка `t_2c8ee3b2` (`TZ:patch: dev-pipeline-ac-criteria`): воркер завершается **rc=0**, **0 tool-calls**, без `kanban_complete` / `kanban_block`.
- Диспетчер: `protocol_violation`, ретраи до `gave_up` / `blocked` (≥10 прогонов на той же `model_override`).
- Лог: `~/.hermes/kanban/logs/t_2c8ee3b2.log` — HTTP 400, Aborting на первом LLM-ходе.

## Root cause

1. При `kanban_create` на фазу выставлен **`model_override=cursor-grok-4.6-high`** (slug Cursor CLI).
2. Диспетчер передаёт override воркеру как **`hermes chat -m cursor-grok-4.6-high`** (модель «воздуха» Hermes-воркера, не внутренний `agent -p`).
3. Шлюз tutu/OpenRouter (`llm-gateway.tutu.ru`, формат `vendor/model`) отвечает **HTTP 400** (`openrouter model "cursor-grok-4.6-high" must include upstream provider prefix`).
4. Воркер abort без tool-calls → **rc=0** без terminal → корректная классификация **`protocol_violation`**.

Источник путаницы: столбец «Модель» в таблице фаз `DevKanbanPipeline_TZ.md` / зеркала в скиллах читается как `kanban_create --model`, хотя это модель **внутреннего** `agent -p --model`.

## Подтверждение

- **Архитектор:** вердикт «не баг ядра»; цепочка фактов и инвариант двух namespace моделей — `DevKanbanPipeline/_fix_plan_20260925.md` (2026-09-25).
- **Ревизор:** согласован scope канона (guards в скиллах + сноска в master-ТЗ); ядро `hermes-agent` и `failure_limit` вне цикла.

## Blast radius

| Карточка | Фаза | Мина |
|---|---|---|
| `t_2c8ee3b2` | `TZ:patch` | `cursor-grok-4.6-high` (blocked) |
| `t_b4cb83bb` | `TZ:finalize` | `cursor-grok-4.6-high` (todo) |
| `t_5e0d0b7e` | `REV:tz` | `claude-sonnet-5-medium` (todo) |

**Класс фаз:** все строки таблицы «Фазы ↔ скиллы» в `DevKanbanPipeline_TZ.md`, где в колонке модели указаны `cursor-grok-*`, `claude-sonnet-*`, `composer-*` — при ошибочном `--model` на create.

## Действия (план фикса)

| Шаг | Кто | Суть |
|---|---|---|
| **П.1** | оркестратор | `set-model none` на `t_2c8ee3b2`, `t_b4cb83bb`, `t_5e0d0b7e`; затем `unblock`; dispatch-note |
| **П.2** | исполнитель (отдельная фаза) | `GLOSSARY.md` §3/§5.2 — инвариант двух моделей |
| **П.3** | исполнитель (этот артефакт) | диагноз в `ProcessImprovement/plans/` |
| **П.4** | исполнитель (этот цикл) | guards: `DevKanbanPipeline_TZ.md`, `tz-workflow`, `hermes-feature`, `kanban-dev-cases`, `cursor-cli` |
| **П.5** | исполнитель (отдельно) | `kanban-worker/SKILL.md` — pitfall на create |

## Запрет (этот цикл)

- Не патчить ядро `hermes-agent` / `kanban_db.py`.
- Не рестартовать gateway.
- Не менять `failure_limit`.
- Не трогать карточки канбана (`set-model` / `unblock`) — оркестратор.

## Критерий приёмки канона

1. В `DevKanbanPipeline_TZ.md` таблица фаз явно отделяет модель `agent -p` от `kanban_create --model`.
2. В `tz-workflow`, `hermes-feature`, `kanban-dev-cases`, `cursor-cli` — анти-пример / pitfall с прецедентом `t_2c8ee3b2`.
3. `rg 'kanban_create.*--model'` по перечисленным SKILL + сноска в master-ТЗ не утверждает override карточки для Cursor-slug.
4. После П.1 оркестратора: новый run `t_2c8ee3b2` без HTTP 400, tool calls > 0, terminal action.
