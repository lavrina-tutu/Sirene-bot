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

## Статус v1.1 (реализован 27.05.2026)

**Что изменилось:**
- `filters.py` — 4 правила фильтрации мусора GAL, встроен в `merger.py` при синке
- `exporter.py` **удалён** полностью, флаг `--export`, зависимость `openpyxl` — исключены
- `contacts.jsonl` — маскировка ФИО/email при записи (первые 2 + последняя буква, середина `**`)
- `fetch_rooms()` убран из основного потока (dead code, комментарий `# out of scope v1.1`)
- WARNING в лог/TG при отсутствии ключа шифрования в .env

**После реализации v1.1 — обязательные пост-шаги:**
1. Удалить `contacts.enc` целиком (иначе старые 1787 записей без фильтрации)
2. Запустить внеплановый синк → чистая база ~944 контактов
3. Починить путь в cron job `58ab10e1ee15` (старый путь `Cursor_projects/MoveFromExchange`)

---

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

load_dotenv('/home/tkachenkoav/Documents/Cursor_projects/MoveFromFF/.env')
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

## ТЗ инструментов: где хранится

**Правило (согласовано 27.05.2026):** Полное живое ТЗ каждого инструмента хранится в папке инструмента:
`USERTOOLS/<Инструмент>/<Инструмент>_TZ_vX.Y.md`

Например: `USERTOOLS/MoveFromExchange/MoveFromExchange_TZ_v1.1.md`

`WorkVault/Hermes-Backlog/` — история точечных ТЗ (доработки). `USERTOOLS/<tool>/` — единая точка правды на весь инструмент. При каждой доработке обновлять master-ТЗ, не только точечный файл в Backlog.

## Анализ GAL-контактов для фильтрации мусора (методология)

При получении нового набора контактов из Exchange GAL — перед написанием фильтров провести анализ через `delegate_task` (не тратить токены Sonnet в интерактиве):

```
Измерения анализа:
1. Уникальные домены email + их количество
2. Паттерны в local_part: суффиксы (.dept, .room, .alias, .archive, .report), role-слова, тест-паттерны
3. Пустые поля: сколько без department, без position, без fio
4. display_name == email / local_part — сигнал служебного аккаунта
5. Количество записей с @ в display_name
```

**Результат анализа (ТУТУ, 1787 контактов, май 2026):**
- Реальных сотрудников: ~944 (hard-фильтр 4 правила)
- Ключевые паттерны мусора: суффиксы `.dept/.room/.alias/.archive/.report` (380), display_name==email (769), role-почты (27), тест-аккаунты (33)
- Поля `is_room` и `active` не размечены в Exchange GAL — нельзя использовать для фильтрации

## Контекст

- **Пользователь:** tkachenkoav@tutu.ru (ТУТУ)
- **Источник:** Exchange EWS `https://cas.tutu.ru/EWS/Exchange.asmx`
- **Хранилище:** `{WORKVAULT_PATH}/Contacts/contacts.enc` (AES-256-GCM)
- **Объём GAL:** 1787 записей (26.05.2026, первый полный синк)
- **Проект:** `/home/tkachenkoav/Documents/Cursor_projects/hermes-agent/USERTOOLS/MoveFromExchange/`
- **ТЗ:** нет отдельного файла в Hermes-Backlog, только README.md в проекте
- **Крон:** каждое воскресенье 03:00 МСК (job_id: 58ab10e1ee15)
- **pytest:** не установлен в venv проекта — перед запуском тестов: `pip install pytest`

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

## Команда --export (УБРАНА в v1.1)

**Статус:** ❌ Удалена в v1.1 (27.05.2026). `exporter.py`, флаг `--export`, зависимость `openpyxl` — полностью исключены. Никаких незашифрованных копий персданных на диске.

**Причина:** принципиальное решение — contacts.enc хранится только зашифрованно. Для проверки базы — поиск через Telegram с маскировкой.

## TG-уведомления

| Режим | TG |
|---|---|
| `--mode manual` успех | ✅ "Синхронизировано N, новых M, обновлено K, неактивных L" |
| `--mode manual` ошибка | ✅ текст ошибки |
| `--mode cron` | ❌ только лог |
| Ошибка подключения к Exchange | ✅ всегда |

## Статус кода

✅ **v1.1 реализован** (27.05.2026).

**Что изменилось в v1.1:**
- Новый модуль `filters.py` — 4 правила фильтрации мусора GAL, встроен в `merger.py`
- `exporter.py` удалён полностью, флаг `--export` убран
- `contacts.jsonl` — маскировка ФИО/email при записи (первые 2 + последняя буква)
- `fetch_rooms()` убран из scope (dead code)
- WARNING в лог/TG при отсутствии ключа шифрования в .env

Модули: `__main__.py`, `config.py`, `crypto.py`, `exchange_client.py`, `merger.py`, `store.py`, `filters.py`, `lock.py`, `logger.py`, `commands.py`, `tg.py`

Тесты: `test_crypto.py`, `test_merger.py`, `test_store.py`, `test_filters.py`, `test_logger_masking.py` ✅

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

## Маскировка персданных при выводе (согласовано 27.05.2026)

При любом выводе контактов пользователю (Telegram, лог) — **маскировать** ФИО, email, логин, Telegram handle:

**Правило маскировки:** первые 2 + последняя буква открыты, середина `**`
- ФИО: `Ив**в Ал**р`
- Email: `iv**v@tutu.ru` (домен открыт полностью)
- Логин: `iv**v`
- Telegram handle: `@iv**v`

**Поля для отображения** (при поиске, до 5 контактов): ФИО, email, логин, отдел, команда, должность, алиасы, мессенджеры. `is_room` и `synced_at` — пользователю не показывать.

**Поиск через Telegram:** по имени/фамилии (частичное совпадение), до 5 контактов. Реализация — отдельный бриф (TG-команды).

## Архитектурные решения (зафиксированы 27.05.2026)

- **Переговорки (is_room) — НЕ синхронизируем.** `fetch_rooms()` убран из scope. Комнаты не нужны в справочнике контактов.
- **MarkObjectsFromSummary читает contacts.enc напрямую** через Python API (`movefromexchange.store.create_store`). Не через отдельные Markdown-файлы Obsidian. Формат хранения един — `contacts.enc`. Публичный API: `store.find_contacts(query)` и `store.get_contact(email)` — стабильный интерфейс для внешних инструментов.
- **Фильтрация «мусора» в GAL — реализована в filters.py (ТЗ v1.1).** Из 1787 контактов реальных людей ~944 (hard-фильтр). 4 захардкоженных правила без LLM — см. раздел ниже.
- **XLSX-экспорт — УБРАН.** Никаких выгрузок персональных данных в открытый вид. Команда `--export` и `exporter.py` исключены из инструмента. contacts.enc хранится только зашифрованно.
- **Хранение персданных: только contacts.enc (AES-256-GCM).** Никаких открытых копий, XLSX-бэкапов, экспортов. Ключ в `.env` — нормально. Если contacts.enc потерян — пересинхронизация из Exchange (кастомные поля теряются, Exchange-данные восстановятся).
- **contacts.jsonl — маскировать ФИО и email** при записи событий (первые 2 + последняя буква, середина `**`).
- **Кастомные поля (aliases, messenger_ids, notes) — оставить**, заполнять через Telegram-бота (отдельный бриф).
- **CLI-команды через Telegram — отдельный бриф.** Пункт полностью переделывается, обсуждение не завершено.
- **WARNING при отсутствии ключа** в .env при старте — не падать, только предупреждение в лог и TG.
- **Полное ТЗ инструмента:** `USERTOOLS/MoveFromExchange/MoveFromExchange_TZ_v1.1.md` (master, обновляется при доработках). Hermes-Backlog — история точечных ТЗ.

## Фильтрация служебных аккаунтов GAL (filters.py, v1.1)

**Анализ 1787 контактов (май 2026):** из них реальных людей ~944. Остальные — служебные.

**4 правила (чистый Python, без LLM):**

**Правило 1 — суффиксы в email** (380 контактов, 0 ложных):
```python
any(tag in email for tag in ['.dept@', '.room@', '.alias@', '.archive@', '.report@'])
```

**Правило 2 — role-почты RFC** (~27 контактов):
```python
local_part = email.split('@')[0]
local_part in {'noreply', 'no-reply', 'no_reply', 'abuse', 'postmaster',
               'mailer-daemon', 'admin', 'support', 'info', 'webmaster',
               'hostmaster', 'billing', 'feedback', 'reception', 'press', 'legal'}
```

**Правило 3 — тест-аккаунты** (~33 контакта):
```python
any(p in email for p in ['qatest', 'sectest', 'testops', 'interview-testing',
                          'ab_test', '_test@', 'test_'])
```

**Правило 4 — display_name = email/логин** (~769 контактов с пересечением):
```python
display_name == email or display_name == email.split('@')[0]
```

**Применение:** фильтр в `merger.py` до записи в store. Служебные контакты не сохраняются.

**Поля `is_room` и `active`** из Exchange не размечены (везде 0/True) — на них нельзя опираться для фильтрации.

- **Cron починить после реализации v1.1:** путь в job `58ab10e1ee15` указывает на старое расположение. Обновить после завершения реализации filters.py + удаления XLSX.
- **Перед первым запуском после реализации v1.1:** удалить `contacts.enc` целиком → синк запишет с нуля с фильтрацией, без старых 1787 записей. Это предотвратит задвоение.
- **XLSX-экспорт полностью убран (v1.1):** `exporter.py`, флаг `--export`, зависимость `openpyxl` — всё удалено. Никаких незашифрованных копий персданных.
- **contacts.jsonl — маскировать ФИО и email при записи** (первые 2 + последняя буква, середина `**`).

## Контакты отсутствующие в Exchange GAL

**Проблема:** некоторые сотрудники скрыты в GAL или используют нестандартные аккаунты — Exchange не вернёт их при синке.

**Решение — добавить вручную через Python API:**
```python
from movefromexchange.store import create_store
from movefromexchange.config import Settings
from pathlib import Path
from datetime import datetime, timezone

s = Settings()
store = create_store(Path(s.contacts_enc_path), s.contacts_encryption_key)
data = store.read()
now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
data['contacts']['email@tutu.ru'] = {
    'email': 'email@tutu.ru', 'login': 'login',
    'fio': 'Фамилия Имя Отчество', 'display_name': 'Имя Фамилия',
    'department': 'Название отдела', 'team': 'Название команды',
    'position': 'Должность', 'is_room': False, 'active': True,
    'synced_at': None,  # None = добавлен вручную, не из Exchange
    'aliases': ['Псевдоним'], 'messenger_ids': {},
    'notes': 'Добавлен вручную', 'custom_updated_at': now
}
store.write(data)
```

**Защита от перезаписи:** `synced_at=None` + `custom_updated_at` установлен → при синке Exchange-поля обновятся только если Exchange вернёт этот email. Кастомные поля (aliases, notes) никогда не перезаписываются.

**Email — первичный ключ, всегда уникален.** Однофамильцы с разными email — разные записи. Никогда не дедуплицировать по ФИО/имени.

## Известные проблемы (актуально, май 2026)

- **⚠️ ResolveNames возвращает max 100 результатов на запрос — часть сотрудников теряется (обнаружено 28.05.2026):** `_fetch_people()` ищет по однобуквенным паттернам (a-z + а-я). На популярные буквы (s, a, k, m, n и т.д.) сотрудников больше 100 — Exchange молча обрезает список. `sereda@tutu.tech` не попал именно по этой причине. **Решение:** перейти на двухбуквенные паттерны (`se`, `si`, `sa`...) — ~676 запросов вместо ~56, но полное покрытие. Задача в бэклоге.

- **Cron (job `58ab10e1ee15`) использует старый путь** `C:/Users/.../Cursor_projects/MoveFromExchange` вместо `hermes-agent/USERTOOLS/MoveFromExchange`. ⚠️ Починить после завершения реализации v1.1.
- **Перед первым запуском после v1.1:** удалить `contacts.enc` целиком → синк запишет с нуля с фильтрацией. Без удаления старые 1787 записей без фильтрации останутся.
- **Некоторые сотрудники не в GAL:** скрытые аккаунты, нестандартные домены — добавлять вручную (см. раздел выше). Системное решение — MarkObjectsFromSummary (добирает участников встреч из FF).

## Питфоллы

- **ResolveNames лимит 100 на однобуквенный паттерн** — популярные буквы обрезаются молча. Переход на двухбуквенные паттерны устраняет проблему. Обнаружено 2026-05-28: `sereda@tutu.tech` отсутствовал по этой причине.
- **Exchange переведён в режим верификации (2026-05-28).** Основной источник контактов — Zulip (`GET /api/v1/users`, один запрос, все пользователи). Крон MoveFromExchange удалён до явного подтверждения Саши.
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
- **⚠️ ДВА РАЗНЫХ contacts.enc (критично, май 2026):** В проекте MoveFromExchange есть `contacts.enc` с 2 тестовыми записями (966 байт). Настоящий рабочий файл с 1167 контактами живёт в `/home/tkachenkoav/Documents/Cursor_projects/MoveFromFF/contacts.enc` (628 KB). Экспорт `--export` из MoveFromExchange берёт СВОЙ локальный файл → получается пустой xlsx. Для экспорта рабочих данных — запускать экспорт из папки MoveFromFF или явно передавать путь к нужному contacts.enc.
- **contacts.enc в MoveFromExchange** — содержит только тестовые данные (`test1@tutu.ru`, `test2@tutu.ru`). Не путать с рабочим файлом в MoveFromFF.
- **Email — первичный ключ, всегда уникален.** Однофамильцы и тёзки с разными email — разные записи, никогда не схлопываются. `merger.py` использует email как ключ словаря. Не пытаться дедуплицировать по ФИО/имени.
- **Перед первым запуском после реализации filters.py:** удалить `contacts.enc` целиком → синк пишет с нуля с фильтрацией. Без удаления старые 1787 записей останутся без фильтрации.
- **`--mode manual` без флага `--from-date`/`--to-date` упадёт** — это требование Exchange CLI, не баг. Аналогично MoveFromFF: для запуска без дат — `--mode test`.
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

## Источник контактов

`C:\\Users\\tkachenkoav\\WorkVault\\Contacts\\contacts.enc` — единый зашифрованный справочник (AnywhereContacts, schema v2). Источники: Exchange GAL + Zulip. Первичный ключ — `login` (часть email до @).

Старые Markdown-файлы (`tutu-contacts.md`, `external-contacts.md`) — **устарели, не использовать**.

## ⚠️ PII Masking при выводе пользователю (КРИТИЧНО)

Все данные контакта (ФИО, email, login, telegram) — PII. Перед **любым** выводом пользователю вызывать `mask_contact`:

```python
from anywhere_contacts import mask_contact
hits_for_display = {k: mask_contact(v) for k, v in hits.items()}
# показывать только hits_for_display
```

Правильно: `Кр**в Ки**л`, `kr**v@tutu.ru`
Неправильно: `Криворотов Кирилл`, `krivorotov@tutu.ru`

Сырые данные допустимы только внутри инструментов (запись в Jira, Confluence) — не в чате.

## Resolution Steps

1. Взять строку упоминания как есть.
2. Поискать через Python:
```python
import sys
sys.path.insert(0, '/home/tkachenkoav/Documents/Cursor_projects/hermes-agent/USERTOOLS/AnywhereContacts')
from anywhere_contacts.store import create_store
from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv('/home/tkachenkoav/Documents/Cursor_projects/hermes-agent/USERTOOLS/MoveFromExchange/.env')
store = create_store(
    Path('/home/tkachenkoav/WorkVault/Contacts/contacts.enc'),
    os.environ['CONTACTS_ENCRYPTION_KEY']
)
data = store.read()
contacts = data.get('contacts', {})
# поиск по login, fio, display_name (регистронезависимо)
query = 'запрос'.lower()
hits = {k: v for k, v in contacts.items()
        if query in k.lower() or query in v.get('fio','').lower() or query in v.get('display_name','').lower()}
```
3. Одно совпадение → это человек.
4. Несколько совпадений → уточнить у пользователя.
5. Нет совпадений → сообщить, не угадывать.

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

## Exchange GAL и Zulip как источники (обновлено 28 мая 2026)

`contacts.enc` объединяет два источника:
- **Exchange GAL** — ФИО, email, должность, отдел (`sources.exchange`)
- **Zulip** — email, zulip_id, telegram (`sources.zulip`)

Первичный ключ — `login` (локальная часть email до @). Один логин = один человек, даже если email в Exchange и Zulip разные (например `sereda@tutu.ru` и `sereda@tutu.tech`).

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
