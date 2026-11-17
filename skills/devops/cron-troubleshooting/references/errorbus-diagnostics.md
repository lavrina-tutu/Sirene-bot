# ErrorBus diagnostics

Historical source claims about auto-resolve conflict. Verify current code and reconcile/digest behavior; manual closure is only an authorized exception. Historical proposals are not authorization to make changes.

## Open events continue after a script fix

If ErrorBus continues delivering open events after the script or cron has recovered, compare each event's `last_seen` with recent cron results before assuming a current failure. `_report_error_bus`/`report_error.sh` writes to `~/.hermes/error_bus/events.db`; delivery may repeat events whose `status='open'`.

```python
   import sqlite3
   c=sqlite3.connect('/home/tkachenkoav/.hermes/error_bus/events.db')
   for r in c.execute("SELECT id, tool, stage, message, severity, count, last_seen, status FROM errors ORDER BY last_seen DESC"):
       print(r)
   ```

Inspect the latest output under `~/.hermes/cron/output/<job_id>/`. Old `last_seen` values alongside recent successful runs can indicate historical events. `Status: silent (empty output)` can be normal for no_agent when the contract expects no output; verify the contract and actual business delivery rather than declaring every silent run successful or failed.

Two historical examples of root causes:
- `KeyError: 'tag'` in `config.py` during cron import: a `ProtocolFromSummary` entity in `entities.json` had a `pfs` block without `tag`; the historical fix used `pfs.get("tag")` instead of `pfs["tag"]`. The source document is missing.
- `stale pending notifications` for nonexistent `meeting_id` such as `new1` can refer to a test fixture: `tests/test_notify_pending.py` uses `meeting_id="new1"`. Check `python3 scripts/notify_pending.py --dry-run` when its side effects are authorized. An old bus event alone is not evidence of a current stale warning.

After confirming recovery and no new failures, verify automatic resolution. If manual resolve is authorized and necessary, use `error_bus_cli.py resolve <id> --note` and preserve history; do not delete events. Do not restart the gateway without Sasha's explicit permission.

## Historical snapshots: contradictory auto-resolve claims

Historical snapshots below are retained in Russian. They contradict each other and are not evidence of current behavior.

> Context (RU): Исторический снимок, 27.08.2026, не подтверждён: авто-resolve в коде отсутствует. `report_error`/`reconcile` создают события только на failed-прогонах; `reconcile.py` использует `recovery_index`/`is_recovered` лишь чтобы не создавать новое событие, старые `open`-строки не закрывает. Ручной путь — `error_bus_cli.py resolve <id> --note`. `digest_rows_stale_open` фильтрует по `first_seen`, игнорируя `last_seen`, поэтому старые события видны ежедневно. Исходный подробный документ отсутствует.

> Context (RU): Исторический снимок, 27.08.2026, противоречит предыдущему и не подтверждён: авто-закрытие реализовано в ErrorBus v0.3.0. `digest_rows_stale_open` добавляет `AND last_seen >= datetime('now','-7 days')` (`STALE_RECENCY_DAYS=7`, `_db.py`). `auto_resolve_recovered(conn, recoveries)` в `_db.py` вызывается в конце `reconcile()` по `recovery_index` (job_id, `last_seen < recovered_at`). `auto_resolve_dormant(conn, days=DORMANT_DAYS=5)` в `_db.py` вызывается в `digest.py` перед `digest_rows_stale_open` для событий без job_id. История сохраняется через `UPDATE status='resolved'`, без `DELETE`; свежий мониторинг (`report_error`/wrap/severity/`already_reconciled`/`is_recovered`) не изменён. Заявлено 41/41 тестов.

Do not assume either snapshot describes the installation. Compare `last_seen` with cron results and check current code and actual reconcile/digest results. A recent recurring event may indicate a live failure; old events require investigation of the resolution path.

## Reconcile recreates events for old failed runs

If alerts continue after recovery and open events are resolved, check whether `error_bus_reconcile.py` recreates events for historical failures. The historical source describes `~/.hermes/error_bus/reconcile.py::reconcile()` calling `hermes_cron_runs(limit=200)` without a time filter, then `report_error(..., send_telegram=True)` for each run in `FAIL_STATUSES={"failed","timeout","error","unknown"}`. It says `already_reconciled()` deduplicated by exact `run_id` in detail; a sequence of failures such as `pfs_notify` every five minutes from 17:40–18:10 could therefore generate a new event for each old run. Verify current implementation.

Inspect `created` in a dry run, not only open status:

```bash
/usr/bin/python3.11 ~/.hermes/error_bus/reconcile.py --dry-run
# → {"created": N, "skipped": M, "backfilled": 0}
```

A positive `created` count while the cron has long been healthy can indicate historical failures will be recreated; inspect the proposed events before concluding. The historical fix direction was to add a freshness window based on run.ts or `~/.hermes/error_bus/.last_reconcile`, deduplicate matching `job_id`+detail/run_id including resolved records, and continue detecting fresh failures. Route changes through the authorized BUGFIX scope. Do not restart the gateway without explicit permission. The original detailed document is missing.

## Silent output after a fix

For a no_agent script such as `notify_pending.py`, `Status: silent (empty output)` can mean no new pending items even when delivery uses its own channel. Compare adjacent ticks, actual delivery, and timestamps. Earlier `script failed` with traceback followed by stable `silent`, with config.py mtime between them, can indicate a fix was picked up; confirm against the script contract and evidence.
