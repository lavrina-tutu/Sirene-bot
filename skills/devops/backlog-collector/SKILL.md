---
name: backlog-collector
description: "Показывает backlog — READ-запрос карточек IDEA/* в статусе triage (kanban)."
version: 3.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
triggers:
  - "бэклог"
  - "что в бэклоге"
  - "проверь бэклог"
  - "покажи бэклог"
  - "собери бэклог"
---

# Backlog Collector (READ triage)

## Назначение

Единственная ответственность: **показывать backlog** — карточки `IDEA/*` в статусе `triage`. SoT: `~/.hermes/kanban.db`.

Не пишет markdown, не вызывает USERTOOLS DialogBacklog, не создаёт карточки (ручной feed — через `tz-workflow`).

## Алгоритм

1. `hermes kanban list --status triage` (или эквивалентные `kanban_*` tools) → карточки `IDEA/*`.
2. Показать для каждой: **title**, статус, краткое превью **body**.
3. Не показывать закрытые, архивные карточки и историю md-файла.
4. Отчёт — в чат, откуда пришла команда.

## Что НЕ делает

- Не зовёт `backlog_fetch.py`, `state.json`, `backlog_merge.py`.
- Не пишет `dialog-backlog.md`.
- Не вызывает `kanban_specify` / `promote`.
- Не создаёт карточки `IDEA/*` (режим feed — `tz-workflow`).
- Не ставит крон.

## Питфоллы

- **Passive triage:** карточки в `triage` воркер сам не берёт — это inbox.
- **Specify:** только через `tz-workflow`, фраза «разбери идею» (режим B).

## Связанные скиллы

- `tz-workflow` — ручной feed идеи в triage, разбор идеи (`IDEA:analyze`).
