---
name: movefrom-exchange-contacts
description: "MoveFromExchange contacts/GAL — синхронизация корпоративной адресной книги Exchange в зашифрованный локальный справочник contacts.enc (AES-256-GCM)."
version: 1.0.0
author: agent
tags: [exchange, ews, contacts, gal, encryption, workvault, tutu]
platforms: [windows]
---

# MoveFromExchange — contacts/GAL

Инструмент синхронизации Global Address List (GAL) из Exchange EWS в локальный зашифрованный справочник контактов. Является **эталонным источником людей** для всего конвейера MoveFrom* — email = универсальный ключ резолвера.

## Источник данных: Zulip (основной, май 2026)

Exchange GAL недоступен без разрешения проблемы авторизации. **Первичный bootstrap contacts.enc — из Zulip.** Zulip даёт email + ФИО + zulip_id для 1167 активных сотрудников.

Что Zulip **не даёт**: department, team, position — поля остаются пустыми. Обогащение через Exchange планируется позже.

### Скрипт однократного импорта из Zulip

Файл: `import_from_zulip.py` в корне проекта MoveFromExchange.

```python
import requests, os, warnings
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')

load_dotenv('C:/Users/tkachenkoav/Documents/Cursor_projects/MoveFromFF/.env')
load_dotenv('.env', override=False)

from movefromexchange.config import get_settings
from movefromexchange.store import ContactStore
from movefromexchange.merger import ContactMerger

ZULIP_URL = os.getenv('TUTU_ZULIP_URL')
ZULIP_KEY = os.getenv('TUTU_ZULIP_API_KEY')
ZULIP_USER = os.getenv('TUTU_USERNAME')

users = [m for m in requests.get(
    f'{ZULIP_URL}/api/v1/users',
    auth=(ZULIP_USER, ZULIP_KEY), verify=False, timeout=15
).json()['members'] if m.get('is_active') and not m.get('is_bot')]

def zulip_to_contact(u):
    email = u.get('email', '').lower()
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    return {
        'email': email, 'login': email.split('@')[0], 'fio': u.get('full_name', ''),
        'display_name': u.get('full_name', ''), 'department': '', 'team': '',
        'position': '', 'is_room': False, 'active': True, 'synced_at': now,
        'aliases': [],
        'messenger_ids': {'telegram': '', 'zulip': str(u.get('user_id', '')), 'jira_login': ''},
        'notes': '', 'custom_updated_at': None
    }

s = get_settings()
store = ContactStore(Path(s.contacts_enc_path), s.contacts_encryption_key)
empty = {'schema_version': '1.0', 'updated_at': '', 'contacts': {}}
updated_data, stats = ContactMerger.merge_contacts(empty, [zulip_to_contact(u) for u in users])
store.write(updated_data)
# Затем: python -m movefromexchange --export  → xlsx → TG
```

## Контекст

- **Пользователь:** tkachenkoav@tutu.ru (ТУТУ)
- **Источник:** Exchange EWS `https://cas.tutu.ru/EWS/Exchange.asmx`
- **Хранилище:** `{WORKVAULT_PATH}/Contacts/contacts.enc` (AES-256-GCM)
- **Объём GAL:** ~1000 записей (люди + переговорки)
- **Проект:** `C:/Users/tkachenkoav/Documents/Cursor_projects/MoveFromExchange/`
- **ТЗ:** `hermes-workspace/docs/tz/MoveFromExchange_TZ_contacts_v1.0.md`
- **Крон:** каждое воскресенье 03:00 МСК (job_id: 58ab10e1ee15)

## Что делает

Одно: синхронизировать **только активные** контакты из Exchange GAL (IsHidden=false, аккаунт не отключён в AD) в зашифрованный JSON-справочник.

**Тянем:** людей с активной учётной записью + переговорки/комнаты.  
**НЕ тянем:** скрытые учётные записи, отключённые аккаунты.

## Шифрование (AES-256-GCM)

```
CONTACTS_ENCRYPTION_KEY=<base64, 32 байта> в .env
```
- Если ключа нет → генерирует сам и выводит инструкцию добавить в .env
- Nonce генерируется при каждой записи, хранится в начале файла
- Экспорт: `--export` → `.xlsx` (openpyxl), отправить в TG, удалить

## Структура контакта (contacts.json внутри enc)

```json
{
  "schema_version": "1.0",
  "contacts": {
    "email@tutu.ru": {
      "email": "email@tutu.ru",
      "login": "username",
      "fio": "Иванов Иван Иванович",
      "display_name": "Иван Иванов",
      "department": "...",
      "team": "...",
      "position": "...",
      "is_room": false,
      "active": true,
      "synced_at": "...",
      "aliases": [],
      "messenger_ids": {"telegram": "", "zulip": "", "jira_login": ""},
      "notes": "",
      "custom_updated_at": null
    }
  }
}
```

**Exchange-поля** (перезаписываются при синке): `email, login, fio, display_name, department, team, position, is_room, active, synced_at`

**Кастомные поля** (НИКОГДА не перезаписываются при синке, только ручное редактирование): `aliases, messenger_ids, notes, custom_updated_at`

## CLI

```bash
python -m movefromexchange --mode cron           # синк без TG
python -m movefromexchange --mode manual         # синк + TG итог
python -m movefromexchange --mode manual --dry-run
python -m movefromexchange --export              # xlsx → TG → удалить
python -m movefromexchange --export --no-tg     # xlsx локально (без отправки в TG)
python -m movefromexchange contact show email@tutu.ru
python -m movefromexchange contact edit email@tutu.ru aliases '["Ваня"]'
python -m movefromexchange contact edit email@tutu.ru messenger_ids '{"zulip": "ivan"}'
python -m movefromexchange contact find "Иванов"
```

## Команда --export (май 2026)

**Цель:** Экспортировать контакты из contacts.enc → XLSX → отправить в TG → удалить файл.

**Колонки XLSX:** email, fio, department, team, position, is_room, aliases, messenger_ids, notes

**Режимы:**
- `--export` (default): XLSX → TG → удалить
- `--export --no-tg`: XLSX → сохранить локально

**Требования для --export:**
- `CONTACTS_ENCRYPTION_KEY` в .env (есть в contacts.enc)
- `TELEGRAM_BOT_TOKEN` в .env (для отправки в Telegram; скопировать из Hermes если не заполнен)
- `TELEGRAM_CHAT_ID` в .env (куда отправлять файл)

**Статус:** ✅ Работает (май 2026). Файл создаётся с данными, отправляется в TG, затем удаляется.

## TG-уведомления

| Режим | TG |
|---|---|
| `--mode manual` успех | ✅ "Синхронизировано N, новых M, обновлено K, неактивных L" |
| `--mode manual` ошибка | ✅ текст ошибки |
| `--mode cron` | ❌ только лог |
| Ошибка подключения к Exchange | ✅ всегда |

## Статус кода

✅ **v1.0 написан** (май 2026). 34/34 тестов ✅.

Модули: `__main__.py`, `config.py`, `crypto.py`, `exchange_client.py`, `merger.py`, `store.py`, `exporter.py`, `lock.py`, `logger.py`, `commands.py`, `tg.py`

Тесты: `test_crypto.py` (10), `test_merger.py` (7), `test_store.py` (10), `test_exporter.py` (7)

## Интеграция с конвейером

```
MoveFromExchange → contacts.enc
                        ↓
MoveFromFF → participants (email list в _registry.json)
                        ↓
MarkObjectsFromSummary → читает contacts.enc через crypto.py → резолв email → ФИО
```

**MoveFromExchange НЕ делает резолв сам** — только поддерживает справочник.

## Критические требования к exchangelib Configuration

**⚠️ ПРОТИВОРЕЧИЕ РАЗРЕШЕНО (май 2026):** Версию Build указывать НЕ нужно. В домене ТУТУ авторизация идёт через Windows Kerberos — exchangelib сам определяет версию. Явная версия Build мешает Kerberos negotiate и приводит к UnauthorizedError.

**ОБЯЗАТЕЛЬНО** в `exchange_client.py` при создании Configuration:

```python
from exchangelib import Configuration, BASIC, DELEGATE

# НЕ указывать version= (мешает Kerberos)
# НЕ указывать timeout= (TypeError в новых версиях)
config = Configuration(
    server=server,
    credentials=creds,
    auth_type=BASIC,
)
# ОБЯЗАТЕЛЕН access_type=DELEGATE (иначе ErrorImpersonateUserDenied)
account = Account(
    primary_smtp_address=user,
    config=config,
    autodiscover=False,
    access_type=DELEGATE,
)
```

**Почему Kerberos:** Exchange ТУТУ (15.2.1544.14) работает через доменную Windows-сессию. Пароль (`EXCHANGE_PASSWORD`) не нужен — поле `***` в .env это плейсхолдер. Работает только в офисной сети (домен ТУТУ). Дома без VPN — не работает.

## Питфоллы

- **exchangelib** — библиотека для Exchange EWS на Python. При самоподписанном сертификате ТУТУ: `verify=False` в настройках session.
- **Basic auth, не NTLM** — `auth_type=BASIC` из exchangelib работает, NTLM/DIGEST — нет. Подтверждено: `connect()` с BASIC возвращает True. Но `fetch_gal()` возвращает 0 из-за отсутствия VPN.
- **VPN блокирует LLM** — VPN ТУТУ + внешние LLM API не совместимы. EWS на `cas.tutu.ru` работает только с VPN → задача заморожена. Возможные решения: split-tunnel VPN, внешний EWS-эндпоинт у IT ТУТУ, OAuth2 Modern Auth.
- **`connect()` не проверяет реальное подключение** — Account-объект создаётся без сетевого запроса. `connect()` может вернуть `True` даже без сети. Реальная проверка — только первый `fetch_gal()` или `resolve_names()`.
- **GAL vs личные контакты** — выгружать из GAL (глобальная адресная книга), не из личных контактов почтового ящика.
- **active=false — не удалять** — удалённые из Exchange контакты помечаются `active=false`, данные сохраняются (могут быть в старых встречах).
- **merger.py баг (исправлен май 2026):** при создании нового контакта жёстко ставилось `"messenger_ids": {}, "aliases": [], "notes": ""` вместо значений из входного контакта. Итог: zulip_id не сохранялся. Исправлено — теперь `contact.get("messenger_ids", {})` и т.д. (строки 85-88 merger.py).
- **exchangelib Account() без access_type=DELEGATE** → `ErrorImpersonateUserDenied`. ОБЯЗАТЕЛЬНО добавлять `access_type=DELEGATE`.
- **Configuration(timeout=...)** → TypeError в новых версиях exchangelib. Убрать timeout из Configuration.
- **НЕ указывать Version(build=Build(...)) явно** — в домене ТУТУ мешает Kerberos negotiate → UnauthorizedError. Убрать, exchangelib сам определит версию.
- **EXCHANGE_PASSWORD = *** (плейсхолдер)** — реальный пароль не нужен. Авторизация через Windows Kerberos доменной сессии. Не пытаться «восстановить» пароль.
- **fetch_gal() возвращает 0 без VPN** — resolve_names с wildcards (a*, b*...) не работает без прямого SOAP-доступа. В домене работает, дома нет.
- **fetch_gal() тихо возвращает 0 — silent failure (май 2026):** Голый `except Exception: pass` в `_fetch_people()` глотает `UnauthorizedError` на каждом из 27 паттернов wildcards → 0 контактов без ошибок. Урок: только `except Exception as e: logger.warning(...)`, никогда pass.
- **Субагент может испортить .env и contacts.enc** — при делегировании задач диагностики субагент на Haiku менял .env (подставлял тестовые credentials) и удалял contacts.enc. Явно запрещать в промпте: "не удалять contacts.enc и .env".
- **contacts.enc восстанавливается из Zulip** — если файл удалён, запустить `reimport_zulip.py` в корне проекта.
- **⚠️ ДВА РАЗНЫХ contacts.enc (критично, май 2026):** В проекте MoveFromExchange есть `contacts.enc` с 2 тестовыми записями (966 байт). Настоящий рабочий файл с 1167 контактами живёт в `C:/Users/tkachenkoav/Documents/Cursor_projects/MoveFromFF/contacts.enc` (628 KB). Экспорт `--export` из MoveFromExchange берёт СВОЙ локальный файл → получается пустой xlsx. Для экспорта рабочих данных — запускать экспорт из папки MoveFromFF или явно передавать путь к нужному contacts.enc.
- **contacts.enc в MoveFromExchange** — содержит только тестовые данные (`test1@tutu.ru`, `test2@tutu.ru`). Не путать с рабочим файлом в MoveFromFF.
