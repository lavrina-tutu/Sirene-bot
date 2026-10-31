---
name: workvault-sync
description: "rclone / синк хранилища: systemd WorkVault, без вопросов"
version: 1.0.1
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [WorkVault, rclone, systemd, sync]
    related_skills: [workvault-sync-infra]
---

# WorkVault Sync (Trigger)

Автоматический триггер синхронизации WorkVault ↔ ownCloud.

## Trigger words

Любое из этих слов/фраз в сообщении Саши → немедленно выполнить синхронизацию, **не спрашивая подтверждения**:

- `rclone`
- `синк хранилища`
- `синк архива`
- `рклон`

## Action

```bash
systemctl --user start owncloud-sync.service
```

После запуска — проверить статус (`systemctl --user status owncloud-sync.service`) и сообщить результат (SUCCESS/FAIL).

## Why this skill exists

Саша явно потребовал (05.08.2026): при команде `rclone` не переспрашивать, а сразу выполнять синхронизацию. Скилл создан чтобы закрепить это правило и не отвлекать Сашу лишними вопросами.

## ⚠️ NEVER hand-type rclone sync

Использовать **только** systemd-сервис — см. `workvault-sync-infra` для деталей (риск потери данных 15.07.2026).

## Related

- `workvault-sync-infra` — диагностика и конфигурация sync-инфраструктуры
- `obsidian` — работа с WorkVault
