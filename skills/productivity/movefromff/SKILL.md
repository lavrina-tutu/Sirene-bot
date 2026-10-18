---
name: movefromff
description: "Запуск инструмента MoveFromFF: синхронизация встреч из Firef"
version: 1.0.1
author: Hermes Agent
platforms: [telegram, cli]
---

# MoveFromFF

Инструмент синхронизации встреч из Fireflies.ai → WorkVault/Meetings/NewMeetings/.

## TG-команды

- `обнови fireflies` / `обнови ff` — синхронизировать встречи за последние 5 дней

## Запуск

```bash
cd C:\Users\tkachenkoav\Documents\Cursor_projects\MoveFromFF
.venv\Scripts\python.exe -m movefromff --mode test --no-tg
```

## Режимы

- `--mode test` — последние 5 дней
- `--mode cron` — последние 4 часа
- `--mode manual --from-date YYYY-MM-DD --to-date YYYY-MM-DD` — произвольный период
- `--mode deleted-check` — пометить удалённые в FF (раз в месяц)
- `--reconcile-only` — только сверка диск ↔ реестр
- `--dry-run` — план без записи
- `--no-tg` — без TG-уведомлений

## При получении команд "обнови fireflies" или "обнови ff":

Запусти инструмент MoveFromFF в ручном режиме:

```bash
cd C:\Users\tkachenkoav\Documents\Cursor_projects\MoveFromFF
.venv\Scripts\python.exe -m movefromff --mode test
```

После завершения сообщи пользователю итог из лога:
- сколько встреч скачано
- сколько пропущено
- есть ли ошибки
