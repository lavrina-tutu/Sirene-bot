---
name: cleanup-after-sync
description: "Чистка мусора после GitHub-синка. no_agent скрипт, 0 токенов. Запускается автоматически после autosync_github.sh."
triggers:
  - "чистка мусора"
  - "cleanup after sync"
  - "добавить в чистку"
---

# Cleanup After Sync

## Что чистит скрипт
`~/.hermes/scripts/cleanup_after_sync.sh` — запускается после GitHub autosync (02:00).

**Текущие правила:**
1. `__pycache__/` и `*.pyc` в `~/USERTOOLS/` и `~/hermes-agent/USERTOOLS/` (исключая `.venv/`, `venv/`, `.git/`)
2. `*.tmp` в `~/USERTOOLS/` и `~/WorkVault/`
3. Временные ТЗ в `~/WorkVault/Hermes-Backlog/` (maxdepth 1, шаблоны `ТЗ-*.md` / `TZ-*.md`) **старше 3 дней**
4. Cron output в `~/.hermes/cron/output/` **старше 14 дней**
5. Ротация логов > 10 МБ: `agent.log`, `gateway.log`, `owncloud-sync.log`

**Не трогает:** `_Done/`, `dialog-backlog.md`, `MigrationToVM/`, `.venv/`, `venv/`

## Поведение
- Пустой stdout = тихо (watchdog pattern — Hermes не шлёт сообщение)
- Если что-то удалено — выводит список и доставляет через cron deliver

## Как добавить новое правило
Отредактировать `~/.hermes/scripts/cleanup_after_sync.sh` — добавить блок по образцу существующих.

## Как протестировать
```bash
bash ~/.hermes/scripts/cleanup_after_sync.sh
```

## GitHub крон
Job ID: `5d16b96a9ed5` — script: `autosync_github.sh && bash ~/.hermes/scripts/cleanup_after_sync.sh`
