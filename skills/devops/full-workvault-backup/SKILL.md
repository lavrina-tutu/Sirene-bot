---
name: full-workvault-backup
description: "Полный tgz-бэкап ~/WorkVault → ~/WorkVault_backup/_full-Work"
version: 1.0.1
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [WorkVault, backup, rclone, systemd]
    related_skills: [workvault-sync-infra]
---

# full-workvault-backup

## Когда применять

Триггеры (прямые команды Саши):
- «сделай бэкап хранилища»
- «сделай бэкап WorkVault»
- «сделай полный бэкап»

Также запускается автоматически кроном `full_workvault_backup` ежедневно в 23:30 (no_agent).

## Что делает

Создаёт полный tgz-архив всего `~/WorkVault/` (включая все поддиректории) в папку `~/WorkVault_backup/_full-WorkVault-backup/`.

- **Папка назначения:** `~/WorkVault_backup/_full-WorkVault-backup/` (не синкается с ownCloud, только на ВМ)
- **Именование:** `WorkVault_full_YYYY-MM-DD_HH-MM-SS.tgz`
- **Ретеншн:** последние **5** архивов, старые удаляются автоматически
- **Лог:** запись в `~/WorkVault_backup/_moved-YYYY-MM-DD.log`

## Выполнение (по прямой команде)

```bash
bash ~/.hermes/scripts/full_workvault_backup.sh
```

Скрипт выводит путь, размер, список последних 5 архивов.

## Питфолы

- `WorkVault_backup/` — VM-only, не защищает от падения ВМ целиком. Это защита от логических ошибок (случайное удаление/перезапись через rclone).
- Не запускать `tar` с `--exclude WorkVault_backup` вручную — скрипт архивирует `~/WorkVault`, а не `~/WorkVault_backup`, конфликта нет.
- Скрипт не запускает rclone sync — это отдельная операция (см. workvault-sync-infra).
