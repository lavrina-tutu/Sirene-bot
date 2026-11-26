# Закрытие карточек ErrorBus по вердикту архитектора

Класс задачи: Саша просит «закрой устаревшее/неактуальное» в triage (карточки ErrorBus). Проводится как RESEARCH через dev-workflow (см. SKILL.md), затем штатное разрешение карточек по вердикту.

## Порядок

1. Запустить RESEARCH-поезд (suggest-slug → init → brief.md с handoff-contract → emit-prompt → invoke-role architect; фазы RS:collect, RS:analyze, GATE:done). В brief Саше дать полный список открытых карточек + статусы связанных поездов из `queue.json`, и попросить вердикт по каждой: **resolved** (устарела/неактуальна) или **open** (живая), отдельно разобрав не dev_workflow-карточки (UpstreamMonitor, SkillSizeMonitor). Контракт роли — вердикт в `RS-analyze.md`, не resolve из роли.
2. После GATE:done выполнить resolve **только по подтверждённому вердикту архитектора**. Перед каждым resolve перечитать текущий `status/count/last_seen` карточки и сверить с контрольным снимком из RS-analyze — если событие обновилось или карточка уже закрыта, прежний вердикт не переносится (и повторное разрешение не нужно).
3. Закрывать штатным путём: `error_bus_cli.py resolve <id> --note '<зaранее текст от архитектора>'`. Text resolved_note готовит архитектор в RS-analyze; использовать его, не писать своё поверх.
4. **Верифицировать результат чтением из БД** (read-only), не доверять пустому stdout `resolve`:

   ```python
   import sqlite3
   db = sqlite3.connect("file:/home/tkachenkoav/.hermes/error_bus/events.db?mode=ro", uri=True)
   print(db.execute("SELECT id,status,resolved_at FROM errors WHERE id=1877").fetchone())
   ```

## Питфоллы

- **Читать карточки напрямую SQLite `mode=ro`, а не `error_bus_cli.py list/show`.** Кли «list»/«show» вызывают `bootstrap_db` (сторонняя запись/инициализация), что не нужно при read-only исследовании. `error_bus_cli.py list` для detail-полей тоже отдаёт мультиjson — `show <id>` надёжнее; если show не парсится, читать нужное поле из БД.
- **`resolved` после закрытия — читать как `status=resolved` + `resolved_at`, не полагаться на текст приглашения `resolve id N`.** Успешный resolve печатает короткую строку; фактическое состояние подтверждается только SELECT-eм.
- **Карточка закрывается по КРИТЕРИЮ завершённой связанной работы/принятого шума, не по возрасту.** `status:done` связанного поезда в `queue.json`, `effective_done=true`, журнальный `GATE:done` — достаточные основания; возраст, `rc=0`, отсутствие новых событий и `last_status=ok` монитора — сами по себе нет. Friday-шум монитора (lock_held exit 2) закрывать с конкретной причиной (не все «exit 2 безопасны»).
- **Не объявлять общий класс системы устранённым из одного закрытия.** Закрытие 401/connection-reset/turn-budget одной карточки не означает «auth/сеть/бюджет вообще исправлены»; новые однотипные события оценивать отдельно.
- **`job_id` в карточке может быть не фактическим cron-идентификатором**, а именем wrapper-скрипта; реальный job искать в `jobs.json`, прежде чем судить о восстановлении (`last_failure`, `failure_streak`).
- `error_bus_cli.py` лежит в `~/.hermes/scripts/`; префикс всегда `python3 <path>`.
