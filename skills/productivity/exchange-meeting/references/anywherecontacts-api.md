# AnywhereContacts API — справочник

## Подключение

```python
import os, sys
from pathlib import Path

# Загрузить .env (portalocker, loguru, pydantic-settings нужны)
for line in open('/home/tkachenkoav/USERTOOLS/AnywhereContacts/.env'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ[k] = v.strip()

sys.path.insert(0, '/home/tkachenkoav/USERTOOLS/AnywhereContacts')
from anywhere_contacts import create_store, ContactsBaseSettings

s = ContactsBaseSettings()
store = create_store(
    Path('/home/tkachenkoav/WorkVault/Contacts/contacts.enc'),  # файл, не директория!
    s.contacts_encryption_key
)
contacts = store.read().get('contacts', {})
```

**⚠️ pip install:** `pip install portalocker loguru pydantic-settings` — все три нужны, без них ImportError.

## Схема поля контакта (актуальная, проверено 17.06.2026)

```python
{
    "login": "abankin",                    # логин в домене
    "fio": "Абанькин Ярослав",            # ФИО из Exchange
    "display_name": "Абанькин Ярослав",   # отображаемое имя (для поиска)
    "department": "Отдел разработки",     # отдел
    "team": "",                           # команда (часто пусто)
    "position": "Инженер-разработчик",    # ДОЛЖНОСТЬ — верхний уровень!
    "is_room": False,                     # True если это переговорка
    "active": True,
    "sources": {
        "exchange": {
            "email": "abankin@tutu.ru",   # email из Exchange — ОСНОВНОЙ
            "synced_at": "...",
            "active": True
        },
        "zulip": {
            "email": "abankin@tutu.ru",   # email из Zulip — fallback
            "synced_at": "...",
            "active": True
        }
    },
    "aliases": [],
    "messenger_ids": {"zulip": {"value": "abankin@tutu.ru", ...}},
    "notes": "",
    "custom_updated_at": None
}
```

**⚠️ НЕТ поля `smtp_addresses`** — это старая схема. Правильно: `sources.exchange.email`.
**Должность** = `contact["position"]` (верхний уровень), НЕ `sources.exchange.title`.

## Получение email

```python
src = info.get("sources", {})
email = (src.get("exchange", {}).get("email") or
         src.get("zulip", {}).get("email") or "")
```

## Нечёткий поиск (двухуровневый)

```python
def resolve_contact(query: str, contacts: dict) -> list[dict]:
    """Ищет контакт по имени/фамилии. Возвращает список кандидатов."""
    query = query.strip().lower()
    parts = [p for p in query.split() if len(p) >= 3]

    results = []
    seen = set()

    # 1. Точный поиск — все слова должны быть в display_name
    for login, info in contacts.items():
        dn = info.get("display_name", "").lower()
        if all(p in dn for p in parts):
            src = info.get("sources", {})
            email = src.get("exchange", {}).get("email") or src.get("zulip", {}).get("email") or ""
            c = {"login": login, "display_name": info.get("display_name"), "email": email, "position": info.get("position", "")}
            results.append(c)
            seen.add(login)

    if results:
        return results[:10]

    # 2. Нечёткий поиск — хотя бы одно слово совпадает
    for part in parts:
        for login, info in contacts.items():
            if login in seen:
                continue
            dn = info.get("display_name", "").lower()
            if part in dn:
                src = info.get("sources", {})
                email = src.get("exchange", {}).get("email") or src.get("zulip", {}).get("email") or ""
                results.append({"login": login, "display_name": info.get("display_name"), "email": email, "position": info.get("position", "")})
                seen.add(login)

    return results[:10]
```

## Ошибки Whisper в именах (реальные примеры)

| Whisper сказал | Реальная фамилия | Почему |
|---|---|---|
| Кривородов | Криворотов | «т» → «д» |
| Колмыкова | Калмыкова | «о» → «а» |

**Правило:** если точный поиск дал 0 — всегда запускать нечёткий, не просить пользователя уточнять сразу.

## Всего контактов
2163 записи (обновлено 17.06.2026, источники: Exchange + Zulip).
