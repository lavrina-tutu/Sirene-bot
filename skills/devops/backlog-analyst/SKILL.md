---
name: backlog-analyst
description: "Показывает backlog — READ-запрос IDEA/* в triage (DevWorkflow, колонка pipeline status)."
version: 2.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
triggers:
  - "что в бэклоге"
  - "проверь бэклог"
  - "покажи бэклог"
  - "бэклог"
---

# Backlog Analyst (READ triage)

## Назначение

Тот же **READ-контракт**, что у `backlog-collector`: показать открытый backlog — `IDEA/*` в triage (`pipeline status`). Имя скилла не менять (исторический алиас).

## Алгоритм

1. `pipeline status` → колонка **triage** (IDEA/*).
2. Показать title, статус, краткое body-превью.
3. Не показывать закрытые/архивные и md-историю.
4. Отчёт — в чат источника команды.

## Что НЕ делает

- Не читает `dialog-backlog.md`.
- Не вызывает USERTOOLS / `backlog_analyst.py` / merge.
- Не ставит крон, не `suggest_close`, не интерактивный разбор пунктов md.

## Связанные скиллы

- `tz-workflow` — ручной feed и разбор идеи.
