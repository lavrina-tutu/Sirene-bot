---
tool: MoveFromZulip
version: "1.0"
date: 2026-07-03
status: active
---

# MoveFromZulip — синхронизация контактов из Zulip

Тонкий коннектор поверх `AnywhereContacts`. Источник: `GET /api/v1/users` Zulip API.

## Что делает
1. Одним запросом тащит всех пользователей рабочего пространства Zulip.
2. Фильтрует ботов (`is_bot=True`) и отключённых (`is_active=False`).
3. Маппит запись Zulip → `Contact` (schema v2, source=`zulip`).
4. Под общим `contacts.enc.lock` мержит в `contacts.enc`.

## Конфиг (.env)
Собственный `.env` рядом с пакетом (`USERTOOLS/MoveFromZulip/.env`) — содержит `CONTACTS_ENCRYPTION_KEY` (общий ключ шифрования contacts.enc, синхронизирован с AnywhereContacts) плюс:

```
ZULIP_URL=https://zulip.tutu.ru
ZULIP_EMAIL=bot@tutu.ru
ZULIP_API_KEY=...
```

## Запуск
```bash
python -m movefromzulip --mode manual --dry-run
python -m movefromzulip --mode manual
```

## Маппинг
- `login = local-part(delivery_email or email)`;
- `email = delivery_email or email`;
- `fio = full_name`;
- `display_name = full_name`;
- `messenger_ids.zulip = email` (handle для Zulip — это сам email).
