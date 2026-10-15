---
name: move-from-keytalk
description: "Синхронизация записей Контур.Толк (KTalk) в WorkVault: транскрипт + саммари в Meetings/NewMeetings. Триггеры: обнови ktalk, обнови толк, синк контур.толк, синк keytalk, MoveFromKeyTalk."
version: "0.1.0"
author: Sirene
license: MIT
platforms: [linux]
tags: [ktalk, keytalk, kontur, meetings, workvault, cron]
metadata:
  hermes:
    tags: [ktalk, meetings, workvault]
    related_skills: [fireflies-transcripts, protocol-from-summary]
---

# MoveFromKeyTalk — ручной синк KTalk

## Где код

Пакет: `/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/`  
Интерпретатор (Linux): `/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/.venv/bin/python`

Крон и ErrorBus — отдельно (`bin/movefromkeytalk_sync.sh` + `error_bus_wrap.sh`); в этом скилле только вызов CLI.

## Когда использовать

- «обнови ktalk», «обнови толк», «синк контур.толк», «синк keytalk»
- Нужно догрузить одну запись или прогнать тестовое окно без правки кода

## Команды (абсолютные пути)

Тестовое окно (последние ~5 суток), без записи на диск:

```bash
/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/.venv/bin/python -m movefromkeytalk --mode test --dry-run --no-tg
```

Ручной синк с интервалом (ISO-8601 UTC):

```bash
/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/.venv/bin/python -m movefromkeytalk --mode manual --from 2026-10-01T00:00:00Z --to 2026-10-15T23:59:59Z
```

Одна запись по `recording_key`:

```bash
/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/.venv/bin/python -m movefromkeytalk --mode manual --recording-key <KEY> --no-tg
```

Крон на сервере (не через агента):

```bash
/home/tkachenkoav/USERTOOLS/MoveFromKeyTalk/bin/movefromkeytalk_sync.sh
```

## Флаги

| Флаг | Назначение |
|---|---|
| `--mode cron\|manual\|test` | Режим окна и поведения |
| `--from` / `--to` | Границы для `manual` |
| `--recording-key` | Точечная запись; `last_synced_at` не сдвигается |
| `--dry-run` | Без записи файлов и реестра |
| `--no-tg` | Без Telegram stale-алертов |

## Чего нет в скилле

Сетевая логика, вызов модели и текст промпта саммари живут только в USERTOOL. Несекреты — ключ `tools.move_from_keytalk` в EcosystemConfig; персональный ключ KTalk — shared env (ORCH).
