# MoveFromZulip — бриф v1 (согласован 28.05.2026)

## Статус: ✅ РЕАЛИЗОВАНО

Пакет: `USERTOOLS/MoveFromZulip/`
Contacts: 2148 (1747 Exchange + 401 только Zulip)
Крон: воскресенье 03:00 (job_id: `50a30903f503`)

## Ключевые решения брифа

### Источник данных
- `GET /api/v1/users` — один запрос, весь список сразу (в отличие от Exchange ResolveNames с перебором букв)
- Авторизация: ZULIP_URL + ZULIP_EMAIL + ZULIP_API_KEY из `.env`

### Фильтрация
- `is_bot=True` → пропускаем
- `is_active=False` → пропускаем, **НЕ пишем в contacts.enc**

### Схема (schema v2)
- Первичный ключ: `login` (часть email до @)
- `sources: {zulip: {email, synced_at, active}}`
- `active = any(source.active)`
- `messenger_ids.telegram` из профиля Zulip → `{value, source: "zulip", synced_at}`
- Поля Exchange (department, position) — пустые строки, заполнятся при верификации

### Мерж
- Единый `contacts.enc` в `WorkVault/Contacts/`
- Общий lock: `WorkVault/Contacts/.contacts.enc.lock`
- Если контакт уже есть (по login) — обновляем `sources.zulip` и `synced_at`
- Новый контакт создаётся с `sources: {zulip: ...}`

### Логирование
- `WorkVault/_meta/MoveFromZulip/_sync_log.md`
- `WorkVault/_meta/MoveFromZulip/contacts.jsonl` (с PII-маскировкой)
- Маскировка: те же правила что MoveFromExchange (Кр**в, kr**v@tutu.ru)

### Расписание
- Воскресенье 03:00, тихий cron (уведомление только при ошибке)

### Архитектура (тонкий коннектор)
```
MoveFromZulip/
└── movefromzulip/
    ├── zulip_client.py  ← GET /api/v1/users
    ├── mapper.py        ← zulip_user → contact dict (schema v2)
    ├── filters.py       ← is_bot / is_active
    ├── config.py        ← Settings(ContactsBaseSettings)
    ├── sync.py          ← run_sync()
    └── __main__.py
```
Зависит от `anywhere_contacts` (AnywhereContacts пакет).

## Почему Zulip, не Exchange
Exchange ResolveNames возвращает max 100 результатов на запрос без пагинации.
На популярные буквы (s, a, k...) часть сотрудников молча теряется.
Zulip отдаёт всех одним запросом.
Exchange остаётся для будущей верификации (department, position, официальные ФИО).
