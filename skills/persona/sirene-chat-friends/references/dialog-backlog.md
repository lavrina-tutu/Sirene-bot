# Бэклог (kanban triage)

**Бэклог** — это карточки `IDEA/*` в канбане со статусом `triage`.

- **SoT:** `~/.hermes/kanban.db`
- **Показать:** `hermes kanban list --status triage` (скиллы `backlog-collector` / `backlog-analyst`)
- **Поля:** title, status, body (краткое превью в ответе)

Ручное добавление идеи в triage и разбор — `tz-workflow` («положи в бэклог», «разбери идею»).

Наследование от инструмента DialogBacklog и формата md — в архиве `_Archives/dialogbacklog-*`.
