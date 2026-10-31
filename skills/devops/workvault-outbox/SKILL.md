---
name: workvault-outbox
description: "Use when передать файл Саше: клади в Outbox, не Inbox."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [WorkVault, Outbox, ownCloud, file-transfer, sync]
    related_skills: [workvault-sync, workvault-sync-infra, obsidian]
---

# WorkVault Outbox — передача файлов от Сирени к Саше

Правило (Саша, 12.10.2026): **все файлы, которые я (Сирень) передаю Саше, кладутся в `~/WorkVault/Outbox/`** — на одном уровне с `Inbox`. `Inbox` оставлен **только** под файлы, которые Саша присылает мне (от тебя → ко мне); из своей стороны туда ничего не класть.

## Зачем это отдельная папка

`Inbox/**` **исключён из главного пуша** (`~/.config/rclone/workvault-exclude.lst`): он живёт по одно-way `owncloud-inbox-pull` с ноутбука Саши → ВМ. Поэтому файл, положенный мной в `Inbox`, **НЕ уходит в ownCloud** — Саша его не увидит (ошибка 11.10.2026: три Фреймворк-файла «синхронизировались», а на облаке их не было).

`Outbox` не в exclude → main `owncloud-sync.timer` (bidirectional `rclone sync ~/WorkVault owncloud:WorkVault`) пуш-ит его в облако **автоматически**, как любой обычный файл WorkVault. Саша видит файл локально в ownCloud/Obsidian после тика таймера или по `systemctl --user start owncloud-sync.service`.

## Как передать файл Саше (порядок)

1. **Положить файл в `~/WorkVault/Outbox/`** (вместо Inbox).
2. **Запустить синк через сервис** (не ручным rclone — канон, см. `workvault-sync` и `workvault-sync-infra`):
   ```bash
   systemctl --user start owncloud-sync.service
   ```
3. **Проверить статус**: `systemctl --user status owncloud-sync.service` → `status=0/SUCCESS`.
4. **Подтвердить реальную доставку на облако** (НЕ верить exit 0 — лог main sync не логирует имена файлов из-за `--log-level NOTICE`):
   ```bash
   rclone lsjson owncloud:WorkVault/Outbox/ | python3 -c "import sys,json;print([f['Name'] for f in json.load(sys.stdin)])"
   ```
   Целевой файл должен быть в списке. Пока его нет в выводе `lsjson` — доставка НЕ завершена, даже если сервис вернул 0.

## Восстановление, если файлы уже ушли в облако Inbox

Если файл был ошибочно загружен в `owncloud:WorkVault/Inbox/` (например явным `rclone copy`), после переноса локального файла в Outbox не забыть **удалить устаревшую копию из облачного Inbox**, иначе она останется висеть и будет путать/конфликтовать с правками Саши:

```bash
mv ~/WorkVault/Inbox/<file>.md ~/WorkVault/Outbox/
systemctl --user start owncloud-sync.service   # Outbox уходит штатным пушем
rclone delete "owncloud:WorkVault/Inbox/<file>.md"   # убрать устаревший дубль
rclone ls owncloud:WorkVault/Inbox/                  # подтвердить, что чисто
rclone ls owncloud:WorkVault/Outbox/                 # подтвердить, что новый на месте
```

Правило жёстко: **Inbox (локальный и облачный) не трогать вообще** — не класть, не копировать, не оставлять там своих файлов. Саша формулирует это как "постарайся не трогать более inbox".

## Ключевой pitfall

**`rclone sync` exit 0 ≠ файл ушёл в облако.** Main sync на `--log-level NOTICE` не печатает имена скопированных файлов — только прогресс и `Forced to upload...`. Единственный надёжный способ убедиться в доставке — `rclone lsjson` целевой папки на облаке и поиск имени файла. Никогда не сообщать Саше «синхронизировано» без этой проверки.

## Связанные

- `workvault-sync` — триггер синка по словам rclone/синк
- `workvault-sync-infra` — диагностика синка, exclude-список, канон сервиса
- `obsidian` — работа с WorkVault
