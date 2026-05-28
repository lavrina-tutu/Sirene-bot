# MoveFromZulip — бриф v1 (2026-05-28)

## Контекст
Решение заменить MoveFromExchange как источник контактов на Zulip.
Exchange остаётся для будущей верификации, но не как основной источник.
Крон MoveFromExchange удалён до явного подтверждения Саши.

## Источник данных
- API: `GET /api/v1/users` — один запрос, все пользователи сразу
- Auth: Basic (`ZULIP_EMAIL` + `ZULIP_API_KEY`) из `.env`
- Env vars: `ZULIP_URL`, `ZULIP_EMAIL`, `ZULIP_API_KEY`
- Поля ответа: `email`, `full_name`, `user_id`, `is_active`, `is_bot`, `role`, `avatar_url`
- Telegram берётся из профиля Zulip автоматически (все сотрудники его указывают)

## Фильтрация
- `is_bot == true` → пропустить
- `is_active == false` → пропустить (не писать в contacts.enc вообще)

## Архитектурные решения (согласованы 28.05.2026)

### Первичный ключ — login (не email)
Причина: у одного человека может быть @tutu.ru в Exchange и @tutu.tech в Zulip.
Логин одинаков (`sereda`), email разный. По логину мержим в один контакт.

### Schema v2 — multi-source
```json
{
  "login": "sereda",
  "email": "sereda@tutu.ru",
  "sources": {
    "exchange": {"email": "sereda@tutu.ru", "synced_at": "...", "active": true},
    "zulip":    {"email": "sereda@tutu.tech", "synced_at": "...", "active": true}
  },
  "active": true
}
```
`active` верхнего уровня = `any(source.active)`. Требует migration contacts.enc v1 → v2.

### Общий lock
`WorkVault/Contacts/.contacts.enc.lock` — один на всех коннекторов.

### messenger_ids с source
```json
"messenger_ids": {
  "telegram": {"value": "@sereda", "source": "zulip", "synced_at": "..."},
  "zulip_id":  {"value": 12345,    "source": "zulip", "synced_at": "..."}
}
```
`source: "manual"` — коннектор не перезаписывает. `source: "zulip"` — перезаписывает.

## Архитектура пакетов
MoveFromZulip — тонкий коннектор поверх AnywhereContacts.
Зависимость: `pip install -e ../AnywhereContacts`.

```
MoveFromZulip/
└── movefromzulip/
    ├── zulip_client.py   # GET /api/v1/users
    ├── mapper.py         # zulip_user → contact dict
    ├── filters.py        # is_bot / is_active
    ├── config.py         # Settings(ContactsBaseSettings): zulip_site, email, api_key
    ├── sync.py           # run_sync() через MergeStrategy
    └── __main__.py       # CLI entrypoint
```

## Схема контакта (v2)
Все поля схемы Exchange сохраняются для совместимости.
Zulip не отдаёт: `department`, `team`, `position` — пустые строки.

## Хранилище
Единый `WorkVault/Contacts/contacts.enc`.
Первичный ключ — `login` (с v2).

## Мерж
- Контакт есть (по login) → обновить источник `sources.zulip`, не трогать другие источники
- Контакта нет → создать новую запись с `sources.zulip`
- Контакт был, но в новой выгрузке отсутствует → `sources.zulip.active: false`
- `active` верхнего уровня пересчитывается: `any(s.active for s in sources.values())`

## Маскировка в логах
Те же правила что MoveFromExchange v1.1:
- ФИО: первые 2 + `**` + последний символ каждого слова
- Email: local_part маскируется, домен открыт
- Login: первые 2 + `**` + последний
- `_sync_log.md` — только счётчики, без PII

## Расписание
Воскресенье 03:00 (еженедельно), как Exchange.

## Логи
- `WorkVault/_meta/MoveFromZulip/_sync_log.md`
- `WorkVault/_meta/MoveFromZulip/contacts.jsonl`
- Метрики: `synced`, `new`, `updated`, `skipped_bot`, `skipped_inactive`, `duration`

## Публичный API (через AnywhereContacts)
Hermes и другие инструменты читают контакты через:
- `create_store(path, key)` → ContactStore
- `store.get_contact(login)` — точный поиск по логину
- `store.find_contacts(query)` — substring-поиск по fio, email, aliases

## Статус
Бриф согласован 2026-05-28. ТЗ не написано — следующий шаг.
Блок 8 брифа (публичный API) — в процессе обсуждения.
