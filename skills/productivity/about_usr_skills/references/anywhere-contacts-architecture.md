# AnywhereContacts — архитектура (28.05.2026)

Общая библиотека для всех коннекторов MoveFrom*. MoveFrom* становятся тонкими коннекторами (~150 строк кода на новый).

## Статус реализации

**✅ Реализован и работает.** Opus выполнил все 4 этапа:
- `USERTOOLS/AnywhereContacts/` — пакет создан, 22/22 теста зелёные
- MoveFromExchange рефакторнут в тонкий коннектор, 32/32 теста зелёные
- MoveFromZulip создан, боевой синк выполнен: **2148 контактов** (1747 Exchange + 401 только Zulip)
- Schema v2 с `sources` в production
- migration v1→v2 происходит автоматически при первом чтении

## PII Masking при выводе контактов (КРИТИЧНО, обновлено 27.08.2026)

**Актуальный API (v0.2.0):** `render_contact(contact, level="summary"|"full")`
из `anywhere_contacts/display.py` — заменяет более ранний `mask_contact`.
Вызывать ВСЕГДА перед выводом в Telegram/CLI/чат, если не запрошен явный
`level="full"`.

```python
from anywhere_contacts import render_contact
hits_for_display = {k: render_contact(v, level="summary") for k, v in hits.items()}
```

Для чтения+показа за один вызов — `ContactStore.get_contact_for_display(login)`
/ `find_contacts_for_display(query)` (маскируют автоматически, читают через
штатные `get_contact`/`find_contacts`, которые сами не изменены и остаются
доступны внутренним потребителям полного email).

`summary` открывает fio/display_name/department/position/status/active;
маскирует email/login/messenger_ids/sources. `full` — без маскирования,
только по явному запросу.

Полные правила показа (включая OrgLookup `--reveal` и запрет генерации
`tutu-contacts.md`) — рантайм-скилл
`~/.hermes/skills/productivity/show-contacts/SKILL.md` и
`TZ/AnywhereContacts/AnywhereContacts_TZ.md` §9.

## Что переезжает в AnywhereContacts

- `crypto.py` — шифрование AES-256-GCM (generic)
- `store.py` — ContactStore, create_store (публичный API)
- `logger.py` — SyncLogger + PII-маскеры (расширяемые через register_pii_masker)
- `lock.py` — FileLock (общий lock на contacts.enc)
- `merger.py` — ContactMerger.merge(local, incoming, strategy) + MergeStrategy
- `settings.py` — ContactsBaseSettings (pydantic, базовый класс)
- `schema.py` — dataclass Contact + константы полей

## Что остаётся в коннекторах

- `filters.py` — правила отброса (Exchange: 4 правила; Zulip: is_bot/is_active)
- `<source>_client.py` — API-клиент к источнику
- `mapper.py` — нормализация raw API record → contact dict
- `config.py` — только специфичные credentials/URL (наследует ContactsBaseSettings)
- `sync.py` — оркестрация синка через MergeStrategy

## Ключевые архитектурные решения

**Первичный ключ — `login` (не email).** У одного человека может быть @tutu.ru в Exchange и @tutu.tech в Zulip. Логин одинаков, email разный. По логину мержим в один контакт.

**Schema v2 — multi-source:**
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
`active` верхнего уровня = `any(source.active)`. Migration contacts.enc v1 → v2 автомат при первом чтении.

**Общий lock — `WorkVault/Contacts/.contacts.enc.lock`.** Один файл на всех коннекторов. Параллельный запуск двух коннекторов безопасен.

**messenger_ids с source.** Каждое значение фиксирует источник:
```json
"messenger_ids": {
  "telegram": {"value": "@sereda", "source": "zulip", "synced_at": "..."},
  "zulip_id":  {"value": 12345,    "source": "zulip", "synced_at": "..."}
}
```
`source: "manual"` — коннектор не перезаписывает. `source: "zulip"` — перезаписывает при синке.

**is_active=false из Zulip — НЕ пишем в contacts.** Просто пропускаем.

**Кастомные поля не перезаписываются при синке** (iron rule): `aliases`, `messenger_ids`, `notes`, `custom_updated_at` — только ручное редактирование через TG-команды `/contact edit`.

**merger.py — исправленный баг (25.05.2026):** при создании НОВОГО контакта (не существующего в базе) поля `aliases`, `messenger_ids`, `notes`, `custom_updated_at` берутся из входного контакта, а не жёстко пустые `{}` / `[]`. Критично для Zulip-импорта где messenger_ids.zulip содержит реальный ID.

## Структура пакетов

```
USERTOOLS/
├── AnywhereContacts/          ← библиотека (не CLI)
│   └── anywhere_contacts/
│       ├── crypto.py, store.py, logger.py, lock.py, merger.py
│       ├── schema.py, settings.py, connector.py
│       └── __init__.py        ← публичный API (re-exports)
├── MoveFromZulip/             ← тонкий коннектор
│   └── movefromzulip/
│       ├── zulip_client.py, mapper.py, filters.py, config.py, sync.py
│       └── __main__.py
└── MoveFromExchange/          ← рефакторинг: только exchange-специфичные части
```

## Zulip как первичный источник контактов (25.05.2026)

contacts.enc первично заполнен из Zulip (не Exchange). 1167 активных людей загружены 25.05.2026.

**Поля из Zulip:** email, login, fio (full_name), display_name, zulip user_id в messenger_ids.zulip.
**Чего нет в Zulip:** department, position, team — обогащаются из Exchange GAL позже.

Exchange GAL нужен для: обогащения полями department/position, будущих инструментов создания встреч и анализа почты.

Скрипт повторной заливки Zulip → contacts.enc: `MoveFromExchange/reimport_zulip.py`
