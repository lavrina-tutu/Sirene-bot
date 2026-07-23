---
name: mattermost-loop-api
description: "Работа с Loop (Mattermost ТУТУ, loop.tutu.ru) через API v4 — аутентификация, получение пользователей, паттерн синка контактов. Триггеры: loop api, mattermost api, MoveFromLoop, синк Loop контактов."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
tags: [loop, mattermost, api, contacts, tutu]
---

# Mattermost / Loop API

Loop — корпоративный мессенджер ТУТУ на базе Mattermost (loop.tutu.ru).

## Аутентификация

**Только Personal Access Token (Bearer) — логин/пароль не использовать.**

Токен хранится в `WorkVault/Inbox/Loop Hermes token.md`:
- Token ID: `u3sbn7obibrijj5ppdmiuj3r7r`
- Access Token: `ujde9bzqepb6t8hraym6wz73ir`

В `.env` инструмента: `LOOP_TOKEN=<access_token>`

```python
headers = {"Authorization": f"Bearer {LOOP_TOKEN}"}
```

## Проверка подключения

```bash
curl -s -H "Authorization: Bearer $LOOP_TOKEN" \
  "https://loop.tutu.ru/api/v4/users/me" | python3 -m json.tool
```

Возвращает: `username`, `email`, `id`, `first_name`, `last_name` текущего пользователя.

## Получение пользователей

```python
import requests

def get_all_users(token, base_url="https://loop.tutu.ru"):
    headers = {"Authorization": f"Bearer {token}"}
    page, per_page = 0, 200
    while True:
        r = requests.get(
            f"{base_url}/api/v4/users",
            headers=headers,
            params={"per_page": per_page, "page": page}
        )
        users = r.json()
        if not users:
            break
        yield from users
        page += 1
```

## Поля объекта пользователя

`id`, `username`, `email`, `first_name`, `last_name`, `nickname`, `position`,
`roles`, `locale`, `delete_at`, `create_at`, `update_at`

**Нет явного поля `is_bot`** — детектировать эвристикой.

## Фильтрация (паттерн MoveFromLoop)

```python
def is_active_human(user):
    # Деактивированные
    if user.get("delete_at", 0) > 0:
        return False
    # Боты по роли или email
    roles = user.get("roles", "")
    if "system_bot" in roles:
        return False
    email = user.get("email", "")
    if email.endswith("-bot@zulip.tutu.ru") or email.endswith("bot@loop.tutu.ru"):
        return False
    return True
```

## Маппинг в contacts.enc

```python
def user_to_contact(user):
    first = user.get("first_name", "").strip()
    last = user.get("last_name", "").strip()
    # Порядок «Фамилия Имя» — как в MoveFromZulip
    fio = f"{last} {first}".strip() if last or first else user.get("nickname", "")
    email = user.get("email", "").strip()
    login = email.split("@")[0].lower() if "@" in email else user.get("username", "")
    return {
        "login": login,
        "fio": fio,
        "email": email,
        "position": user.get("position") or None,  # None если пустой — не затирать
    }
```

**Правила записи в contacts.enc:**
- Дополнять, не перезатирать — если поле уже заполнено другим коннектором (Zulip, Exchange), не трогать
- `mattermost_id` не писать (решение 23.07.2026)
- `position` писать только если непустой
- Дедупликация по `login` (из email) — единый ключ с MoveFromZulip

## Крон MoveFromLoop

- Schedule: `30 3 * * 0` (воскресенье 03:30, аналогично MoveFromZulip)
- Model: Haiku
- deliver: local
- ТЗ: `WorkVault/Hermes-Backlog/TZ/MoveFromLoop/MoveFromLoop_TZ.md` v0.1.0

## Мониторинг сообщений (итерация 2, в разработке)

Помимо синка контактов — планируется чтение сообщений из Loop:

**Два режима:**
- **Дайджест** (раз в час) — сводка новых сообщений по подпискам → топик Messages в Telegram
- **Срочный** (каждые 2-3 мин) — DM + @упоминания + @all → немедленно в Telegram

**Что читать:**
- DM (личные сообщения)
- @упоминания пользователя
- @all в отслеживаемых каналах
- Ключевые слова в выбранных каналах (гибко настраиваемые правила)

**Управление правилами:** YAML-файл + команды через Сирень («добавь канал #devops», «следи за словом бюджет»)

**Ответы на сообщения** — из топика Messages в Telegram (итерация 2).

**API-эндпоинты для мониторинга:**
```bash
# Непрочитанные сообщения пользователя
GET /api/v4/users/me/posts/unread?limit=100

# Посты канала с момента времени
GET /api/v4/channels/{channel_id}/posts?since={unix_ms}

# Прямые каналы пользователя
GET /api/v4/users/me/channels

# Упоминания (поиск по тексту)
GET /api/v4/users/me/mentions
```

## Саммари по каналу (итерация 2 архивация, в разработке)

Помимо дайджеста — ежедневное саммари переписки канала через Haiku:
- **Когда:** раз в день, только если были сообщения (иначе не писать)
- **Куда:** `WorkVault/Entities/<slug>/Messages/YYYY-MM-DD.md` — файл на день
- **Содержание:** что обсуждали + проблемы + риски + решения
- **Матчинг канал→сущность:** через Сирень («подключи #pm-team к Trisigma»), slug резолвится через entities.json
- **Если slug не найден:** Сирень спрашивает подтверждения перед созданием новой папки

**Важно:** `WorkVault/Entities/<slug>/` — новая единая структура (миграция из Projects/ + People/). ТЗ: `WorkVault/Hermes-Backlog/TZ/EntitiesMigration/EntitiesMigration_TZ.md`.

## Pitfalls

- **Логин/пароль — не использовать.** Только Bearer PAT. Логин-пароль для Loop явно запрещён (решение Саши 23.07.2026).
- **`is_bot` отсутствует в `/api/v4/users`** — поле не возвращается. Детектировать через `roles` (`system_bot`) и суффикс email.
- **Первый пользователь в списке** часто оказывается деактивированным ботом (`123321123-bot`, `delete_at > 0`). Фильтр обязателен.
- **Порядок ФИО — «Фамилия Имя»** (last_name + first_name), а не «Имя Фамилия» как в API. Единообразие с MoveFromZulip и ожиданиями MOFS matcher.
- **Пустой `position`** — не писать в contacts.enc, чтобы не затереть значение от Exchange OrgLookup.
