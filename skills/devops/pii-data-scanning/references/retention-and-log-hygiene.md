

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

## TTL 5 дней и гигиена на записи (решение 09.09)
- **TTL 5 дней** (авто-удаление завершённых артефактов): `Tasks/TaskRefresh/session/history/*.json` (заверш. сессии; `current.json` остаётся) — в `session_store.py` `prune_history()` при `save_session`; `WorkVault_backup/llm-anomaly-audits/LLM-anomalies_*.json` — `find $OUTDIR -name 'LLM-anomalies_*.json' -mtime +5 -delete` в начале `llm_anomaly_scan.sh`. Питфолл ревизора: TTL(5д) < цикла крона(7д) llm-anomaly-audits — задокументировать в `hermes-cost-audit/SKILL.md`.
- **Гигиена логов:** `~/.hermes/logs/{agent,errors,gateway}.log` и `~/.hermes/cron/output/**` (MFL-дайджест `2865cc674493`, PFS `a6e62d06249f`) — **хранить только логины, не писать ФИО/тел/email** в телах и `inbound msg=`. Общий хелпер `~/.hermes/pii_scan/redact.py` → `redact_fio_email_phone(text)`. Gateway `~/hermes-agent/gateway/run.py`: убрать `msg=`/`reply_to_text=` из INFO (локальный патч разъедется при update — фиксировать pitfall). MFL `format_post`: `first_line` тела через redact. PFS `__main__.py`: не дампить `row_xml` в stdout (или redact).

- **TTL process-results:** receipts фоновых terminal-команд живут 7 суток / max 64 файла, prune ленивый (при следующей записи/чтении, не крон) — сырой дамп ПДн лежит на диске до недели. Ядро Hermes (`process_registry_results.py`) править нельзя (решение Саши — ядро вне скоупа); утилизировать дамп вручную (rm) и закрывать сводное событие одним `resolve_error`.
