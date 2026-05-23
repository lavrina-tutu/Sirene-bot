---
name: contact-resolution
description: "Resolve person mentions (aliases, nicknames, logins) to canonical contact records in WorkVault Markdown tables."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [contacts, aliases, obsidian, name-resolution, tutu]
---

# Contact Resolution

Resolves free-form person references ("Саша", "Иванов", "a.ivanov") to canonical rows in the WorkVault contact tables.

## Files

- `C:\Users\tkachenkoav\WorkVault\Contacts\tutu-contacts.md` — tutu.ru employees
- `C:\Users\tkachenkoav\WorkVault\Contacts\external-contacts.md` — external contacts

## Resolution Steps

1. Take the mention string as-is (no normalisation needed).
2. Run `search_files` with `target="content"` on `WorkVault/Contacts/`, `file_glob="*.md"`, pattern = the mention string (case-insensitive regex).
3. If one row matches → that is the person.
4. If multiple rows match → ask the user to disambiguate.
5. If no match → the person may not be in the list yet; ask user to confirm before adding.

## Adding a New Contact

Append a single `|`-delimited row via `patch`. Never rewrite the whole file.

**tutu-contacts row format:**
```
| login | ФИО | aliases | telegram | email | подразделение | команда | должность |
```

**external-contacts row format:**
```
| ФИО | aliases | telegram | email | компания | заметки |
```

The `aliases` field: comma-separated list of ALL known name variants — short name, full name, login, document pseudonym. The richer this field, the better future resolution works.

## Exchange GAL как источник эталонных записей (зафиксировано 22 мая 2026)

Exchange GAL (глобальная адресная книга) — это корпоративный эталон людей:
- ФИО (полное, официальное)
- **Email (уникальный ключ)** — связывает все источники
- Должность, отдел

Email как универсальный ключ связывает:
- Fireflies → `participants[]` = список email участников встречи
- Zoom → участники по email
- Jira → маппинг логин ↔ email
- Zulip → email при регистрации

**Приоритет #1:** MoveFromExchange (режим contacts/GAL) должен быть реализован первым. Без него резолвер работает вслепую.

## Три состояния резолвера (зафиксировано 22 мая 2026)

| Состояние | Условие | Действие |
|---|---|---|
| `resolved` | Точное совпадение с `canonical_name`/`aliases` ИЛИ email совпал с GAL | Матчим, пишем |
| `ambiguous` | Низкая уверенность | Суффикс `(?)` в файле, например `ML платформа ТУТУ (?)` — сигнал для ручного ревью в Obsidian |
| `unknown` | Нет совпадений | Оставляем сырым текстом, не трогаем |

**Главное правило: не угадывать.** Лучше пропустить чем соврать.
Реестр aliases пополняется вручную — процент авторезолва растёт сам.

## Особенности резолвинга проектов

- Ключ проекта: `canonical_name` + список `aliases` в файле проекта
- За 5 лет в ТУТУ не повторилось ни одного проекта — коллизии маловероятны
- Исключение: один термин = разные сущности ("АБ платформа" = старая ТУТУ ИЛИ Trisigma) → `ambiguous (?)`
- Пользователь маркирует встречи проектами — это помогает резолверу

## Pitfalls

- Do not use `terminal` + `grep` for search — use `search_files` to avoid shell quoting issues with Cyrillic.
- Aliases field should cover every variant the user might say, including typos in common use.
- One person = one row. Never duplicate.
- When adding aliases to an existing contact, use `patch` to extend the `aliases` cell, not add a new row.
- **Не угадывать ambiguous сущности** — помечать `(?)` и оставлять пользователю. Публикация в Jira/Confluence только после подтверждения пользователем.
