# Handoff живого слага (Б13.4)

**Установка инструмента** — `install.md`. Здесь — **передача одной доработки** на другой Hermes / другой диск, чтобы архитектор и ревизор видели тот же смысл и те же файлы.

## Единица обмена

Файловый **bundle** каталога слага + master-ТЗ на диске. Не SQLite, не строка в БД, не `/tmp/task.md` как единственный артефакт.

## Состав bundle

Минимум:

```
dev/<slug>/
  _state.json
  journal.md
  extract.md          # и extract-2.md … при частях 1/N
  AC-list.md
  AC-report.md
  origin.json
  REV-tz.md / REV-plan.md  # если уже были
```

Плюс **master-ТЗ**, на которое ссылается `tz_path` в state (тот же relative path в `TZ_ROOT` на принимающей стороне).

Опционально: бриф, план, IAC-файлы в `dev/<slug>/` если уже созданы.

## На принимающем хосте

1. Выполнить `install.md` (инструмент уже стоит).
2. Положить bundle в тот же `DEV_STATE_ROOT` (или восстановить из git/rsync WorkVault).
3. **Переписать пути** в `EcosystemConfig.yaml` (`DEV_STATE_ROOT`, `TZ_ROOT`, …) — только через YAML, без литералов хоста в Python.
4. Проверить `tz_version` / `tz_mtime` на диске vs `_state.json` (G1).
5. **Пересобрать пакет:** `emit-prompt` на текущей фазе, не копировать старый `/tmp/task.md`.
6. Single-writer: два хоста **не** пишут один `_state.json` одновременно. Общий sqlite/NFS-БД для очереди запрещён.

## WorkVault как шина

Если vault синхронизируется (ownCloud, rclone, git), handoff часто сводится к «дождаться синка» + `status --check`. SQLite `kanban.db` по синхронизируемой папке не использовать.

## ORCH на новом хосте

Регистрация ключа `dev_workflow` в манифесте, schema, battle_interpreters — зона **ORCH:shared-state**, не этот чеклист.
