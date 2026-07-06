# Реорганизация файловой структуры (согласовано май 2026)

**Принцип:** WorkVault = данные, CursorProjects = исходники (устарело), hermes-agent/USERTOOLS = все пользовательские инструменты.

## Целевая структура

```
WorkVault/
├── Contacts/
│   ├── contacts.enc              ← единый для всех инструментов (Zulip + Exchange merge)
│   ├── _registry_cont.json
│   └── _registry_cont.md
├── Meetings/
│   └── NewMeetings/
│       ├── _registry_meet.json   ← было: _registry.json
│       ├── _registry_meet.md     ← было: _registry.md
│       └── _log_meet.md          ← было: _log.md
├── Projects/
│   ├── _registry_proj.json
│   └── _registry_proj.md
├── Tasks/
│   ├── _registry_task.json
│   └── _registry_task.md
└── _meta/
    ├── MoveFromFF/               ← логи и jsonl
    ├── MoveFromExchange/
    └── MoveFromConfluence/

hermes-agent/USERTOOLS/
├── MoveFromFF/
├── MoveFromExchange/
├── MoveFromConfluence/
└── MarkObjectsFromSummary/
```

## Соглашение по именованию реестров

Реестры **всегда** имеют суффикс сущности — не просто `_registry.json`:

| Сущность | Суффикс | Файлы |
|---|---|---|
| Meetings | `_meet` | `_registry_meet.json`, `_registry_meet.md`, `_log_meet.md` |
| Contacts | `_cont` | `_registry_cont.json`, `_registry_cont.md` |
| Projects | `_proj` | `_registry_proj.json`, `_registry_proj.md` |
| Tasks | `_task` | `_registry_task.json`, `_registry_task.md` |
| (новые) | `_[3-4 буквы]` | аналогично |

## contacts.enc — единый файл

- Один `WorkVault/Contacts/contacts.enc` для всех инструментов
- Источник истины: 1167 записей из Zulip (май 2026), впоследствии merge Exchange → 2148 (28.05.2026)
- contacts.enc в MoveFromExchange — только 2 тестовые записи → **удалить**
- При обогащении из Exchange GAL — merge в единый файл

## Чеклист миграции (стадии)

Стадии запускаются последовательно через Opus-cronjob. К следующей стадии — только если тесты GREEN.

- **Стадия 0** — Подготовка: создать папки, git commit, резервные копии contacts.enc
- **Стадия 1** — MoveFromFF (пилот): данные → `WorkVault/Contacts/` и `_meta/MoveFromFF/`, исходники → `USERTOOLS/MoveFromFF/`, обновить `.env` + `config.py`, переименовать `_registry.json` → `_registry_meet.json`, обновить крон `vm_movefromff`
- **Стадия 2** — MoveFromExchange: удалить тестовый contacts.enc, логи → `_meta/MoveFromExchange/`, исходники → `USERTOOLS/MoveFromExchange/` (крона нет)
- **Стадия 3** — MoveFromConfluence: исходники → `USERTOOLS/MoveFromConfluence/`, логи → `_meta/MoveFromConfluence/`
- **Стадия 4** — MarkObjectsFromSummary: исходники → `USERTOOLS/` (ТЗ ещё нет, только папка)
- **Стадия 5** — Финальная проверка: CursorProjects/ без данных, все кроны работают, Hermes memory обновлена

## Шифрование персональных данных

Для данных требующих шифрования (контакты, PII):
- Один файл `<name>.enc` (AES-256-GCM)
- Ключ 32 байта, base64-encoded, в `.env` как `<NAME>_ENCRYPTION_KEY`
- Nonce генерируется каждый раз при записи, хранится в начале файла
- При отсутствии ключа → сгенерировать и вывести инструкцию
- Экспорт для просмотра (устарело: XLSX убран из MoveFromExchange v1.1) — восстановление при потере: пересинхронизация из Exchange (кастомные поля теряются, приемлемо)
