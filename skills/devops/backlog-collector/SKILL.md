---
name: backlog-collector
description: "Показывает backlog — READ-запрос IDEA/* в triage (DevWorkflow, колонка pipeline status)."
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

Единственная ответственность: **показывать backlog** — записи `IDEA/*` в triage. SoT: колонка **triage** у `pipeline status` (Б28 DevWorkflow); `kanban.db` — read-only архив после W4.

Не пишет markdown, не вызывает USERTOOLS DialogBacklog, не создаёт IDEA-записи (ручной feed — через `tz-workflow`).

## Алгоритм

1. `pipeline status` → колонка **triage** (IDEA/*); детали полей — Б28 DevWorkflow.
2. Показать для каждой: **title**, статус, краткое превью **body**.
3. Не показывать закрытые, архивные записи и историю md-файла.
4. Отчёт — в чат, откуда пришла команда.

## Что НЕ делает

- Не зовёт `backlog_fetch.py`, `state.json`, `backlog_merge.py`.
- Не пишет `dialog-backlog.md`.
- Не запускает `IDEA:analyze` — только READ.
- Не создаёт записи `IDEA/*` (режим feed — `tz-workflow`).
- Не ставит крон.

## Питфоллы

- **Passive triage:** записи в `triage` воркер сам не берёт — это inbox.
- **Specify:** только через `tz-workflow`, фраза «разбери идею» (режим B).

## Связанные скиллы

- `tz-workflow` — ручной feed идеи в triage, разбор идеи (`IDEA:analyze`).
