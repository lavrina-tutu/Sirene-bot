# Что осталось от канбана (без живого диспетчера)

DevWorkflow **не** использует `kanban.db` как источник правды. История канбана — read-only архив после W4 (`migrate_kanban_history.py`).

## Слой 1 — ведение работы (сохранён)

- Статусы фазы и слага в `_state.json`.
- Переход «фаза готова → следующая» через `complete-phase` и `next`.
- Гейты и остановка на Сашу (HITL).
- **Нет:** heartbeat, reaper, claim_lock, слотов, возраста от `started_at`, минутного dispatch.

## Слой 2 — отчётность (минимум)

- `pipeline status` — тот же привычный layout, что `kanban_status_report.py`.
- Заголовок на W0–W3: «КАНБАН-СТАТУС» (переходная пометка); на W4 — «DEVWORKFLOW-СТАТУС» (`orchestration.status_banner` в YAML).
- Колонка triage — IDEA-бэклог (Б28).
- Отчёт **по запросу**, не крон каждую минуту.

Маппинг колонок:

| Привычная колонка | status в _state.json |
|---|---|
| blocked | `waiting_operator` или `blocked` |
| scheduled (подвисшие) | `interrupted` |
| ready | `idle` |
| running | `in_phase` + живой PID |
| done | `done` |

## Слой 3 — воркеры (заменён)

Роли вызываются через `invoke-role`, не через карточки kanban с model_override. Живость процесса — проверка PID на `status` / `next`, без reaper.

## Dual-path W2–W3

Канбан жив для слагов вне `pilot_slugs`. Пилотные слаги — `dispatch-paused` на доске, ведение через `dev-workflow` (`rollback.md`, `dual_path_banner.md`).

## Ошибки инструмента

Кейсовые notify → origin. Техника DevWorkflow → ErrorBus `:11112`, tool `dev_workflow`. Не смешивать.
