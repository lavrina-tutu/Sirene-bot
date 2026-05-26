# ТЗ: Инструмент MoveFromExchange v1.0 — синхронизация контактов
# Exchange GAL → зашифрованный локальный справочник
# Версия: 1.0 | Дата: 2026-05-23 | Статус: На согласовании (обновлено 2026-05-23) + обновлено 2026-05-25

---

## 0. Философия (главное)

**MoveFromExchange делает ОДНО:** забирает Global Address List (GAL) из Exchange и синхронизирует в локальный, зашифрованный справочник контактов (`contacts.enc`). Идемпотентно и надёжно.

Всё остальное — задача следующих инструментов конвейера. В первую очередь — **MoveFromFF** и **MarkObjectsFromSummary** (они используют `contacts.enc` для резолва email → ФИО участников встреч).

**Принцип не-делания:**
- Не строит граф связей между контактами.
- Не ходит в Jira/Zulip, не публикует контакты автономно.
- Не редактирует Exchange-поля вручную (обновления только через синк).
- Не разрешает конфликты слияния; поле → либо Exchange, либо кастомное локально.
- Не требует дополнительного API (только EWS).

**Один источник истины — `contacts.enc`:** структурированный справочник, зашифрованный, с разделением на Exchange-поля и кастомные.

---

## 1. Что делает

- ✅ Подключается к Exchange EWS с учётом сервера и таймаутов (exchangelib + tenacity).
- ✅ Выгружает GAL (~1000 контактов: **только активные** — люди с активной учётной записью + переговорки / комнаты).
- ✅ Синхронизирует в локальный файл: новые контакты добавляет, существующие обновляет (Exchange-поля), удалённых из Exchange помечает как `active: false`.
- ✅ Сохраняет кастомные поля (aliases, messenger_ids, notes) при обновлении через синк.
- ✅ Шифрует файл AES-256-GCM (ключ в `.env`). При отсутствии ключа — генерирует и выводит инструкцию.
- ✅ Редактирует кастомные поля через CLI и TG-команды (edit, show, find).
- ✅ Экспортирует справочник в `.xlsx` (openpyxl) и отправляет в TG.
- ✅ Логирует все синки в `_sync_log.md` (одна строка) и `logs/contacts.jsonl` (события).
- ✅ TG-уведомления при ручном запуске и ошибках Exchange.

---

## 2. Чего НЕ делает

- ❌ Не публикует контакты в другие системы (Jira, Zulip, Slack и т. д.).
- ❌ Не строит граф организационной структуры (это upstream от других инструментов).
- ❌ Не синхронизирует **из** кастомных полей **в** Exchange (синк однонаправленный: Exchange → local).
- ❌ Не ведёт истории изменений контактов (только текущее состояние + `synced_at`, `custom_updated_at`).
- ❌ Не резолвит email в другие системы (это задача MarkObjectsFromSummary).
- ❌ Не удаляет контакты физически; помечает как неактивные.
- ❌ Не авторизует пользователя вручную (берёт креденшалы из `.env`).
- ❌ Не делает dry-run для синка (только для экспорта и редактирования).
- ❌ Не подтягивает скрытые / отключённые учётные записи из Exchange (синхронизирует только активные контакты).
- ❌ Не отправляет TG-алерты при появлении новых контактов — только логирует события в `logs/contacts.jsonl`.

---

## 3. Алгоритм синхронизации (Шаги 0-4)

### Шаг 0. Preflight
1. Взять `portalocker`-лок `.locks/movefromexchange.lock`. Занят → exit 2.
2. Проверить `.env`: `EXCHANGE_SERVER`, `EXCHANGE_LOGIN`, `EXCHANGE_PASSWORD`, `CONTACTS_ENCRYPTION_KEY` (опционально). Нет обязательных → exit 2 (+ TG если `--mode manual`).
3. Создать недостающие папки: `logs/`, `.locks/`.

### Шаг 1. Ping Exchange EWS
|- **Подключение к Exchange:** автодискавери через Kerberos (Windows domain authentication).
  - **Авторизация:** Windows Kerberos (на домене ТУТУ в офисе) — пароль НЕ требуется.
  - **access_type=DELEGATE — обязателен** (для корректной работы EWS с делегированными правами).
  - **Версию EWS НЕ указываем явно** (exchangelib определяет автоматически).
  - **Статус:** ✅ Работает в домене (Inbox ✅ 14 писем, Calendar ✅ 43 события, GAL resolve_names ✅).
  - **Примечание:** `TUTU_PASSWORD=***` в `.env` — плейсхолдер, обычно не используется при Kerberos.
|- Простой запрос (например, `get_account()` или поиск пустой папки, test на GAL resolve_names).
|- Таймаут 15 с, 3 retry с backoff 2/4/8 с (tenacity).
|- Недоступен → exit 3 (+ TG если `--mode manual`).

### Шаг 2. Выгрузка GAL
- Запрос GAL через EWS: `find_items()` с фильтром по `ItemClass` (контакты + комнаты), **только активные контакты** (`IsHidden=false`, аккаунт не отключён в AD).
- Пагинация по 100 элементов, всего ~1000 записей.
- Для каждого контакта собрать: `email`, `login`, `fio` (FullName), `display_name`, `department`, `team` (если есть в атрибутах), `position`, `is_room` (флаг комнаты).
- При ошибке на одном контакте → пропустить, продолжить со следующего. Ошибка общая → выход 3.

### Шаг 3. Merge (синхронизация в локальный справочник)
1. **Прочитать текущий `contacts.enc`** (расшифровать AES-256-GCM).
2. **Для каждого контакта из Exchange:**
   - **Если email уже в локальном справочнике:**
     - Обновить Exchange-поля: `email`, `login`, `fio`, `display_name`, `department`, `team`, `position`, `is_room`, `active` (проставить `true`), `synced_at` (текущее время).
     - **Сохранить кастомные поля:** `aliases`, `messenger_ids`, `notes`, `custom_updated_at` (не трогать).
     - **Определить `is_internal`:** если email имеет домен `@tutu.ru` или `@tutu.tech` → `is_internal: true`; иные домены → `is_internal: false`.
   - **Если новый контакт:**
     - Добавить с Exchange-полями + пустыми кастомными (empty list, empty dict, empty string, null).
     - **Установить `is_internal`:** проверить домен email (см. выше).
     - **ВАЖНО (2026-05-25):** кастомные поля (aliases, messenger_ids, notes) сохраняются при создании нового контакта (баг исправлен в merger.py).
3. **Для каждого контакта в локальном справочнике (не в Exchange на этой итерации):**
   - Если раньше был синхронизирован (есть поле `synced_at`) → проставить `active: false`.
   - Кастомные поля сохранить, данные контакта оставить как есть.

### Шаг 4. Зашифровать и записать
1. Сгенерировать fresh nonce (16 байт, случайный).
2. Шифровать JSON через AES-256-GCM (ключ из `.env`).
3. Записать файл атомарно: `tmp + os.replace()`.
4. Дописать строку в `_sync_log.md` (одна строка-итог, см. §8).
5. Записать события в `logs/contacts.jsonl`.
6. Снять лок.
7. Если `--mode manual` → отправить TG-алерт (см. §8). Для `--mode cron` TG не дёргать.
8. Exit 0 (успех) / 1 (часть упала) / 2 (лок занят) / 3 (Exchange недоступен) / 4 (фатально).

---

## 4. Схема `contacts.json` (внутри `contacts.enc`)

```json
{
  "schema_version": "1.0",
  "updated_at": "2026-05-23T14:30:00Z",
  "contacts": {
    "email@tutu.ru": {
      "email": "email@tutu.ru",
      "login": "username",
      "fio": "Иванов Иван Иванович",
      "display_name": "Иван Иванов",
      "department": "Отдел продаж",
      "team": "Team Alpha",
      "position": "Менеджер",
      "is_room": false,
      "is_internal": true,
      "active": true,
      "synced_at": "2026-05-23T14:30:00Z",
      "aliases": ["Ваня", "Иван"],
      "messenger_ids": {
        "telegram": "@ivanov",
        "zulip": "ivanov.ivan",
        "jira_login": "iivanov"
      },
      "notes": "Ответственный за проект X",
      "custom_updated_at": "2026-05-22T10:15:00Z"
    },
    "room@tutu.ru": {
      "email": "room@tutu.ru",
      "login": "переговорка_314",
      "fio": "Переговорная 3-14",
      "display_name": "3-14",
      "department": "Офис",
      "team": null,
      "position": null,
      "is_room": true,
      "is_internal": true,
      "active": true,
      "synced_at": "2026-05-23T14:30:00Z",
      "aliases": [],
      "messenger_ids": {},
      "notes": "",
      "custom_updated_at": null
    },
    "external@partner.com": {
      "email": "external@partner.com",
      "login": "external_user",
      "fio": "Партнёр Петр",
      "display_name": "Петр П.",
      "department": "Партнёр",
      "team": null,
      "position": "Консультант",
      "is_room": false,
      "is_internal": false,
      "active": true,
      "synced_at": "2026-05-23T14:30:00Z",
      "aliases": [],
      "messenger_ids": {},
      "notes": "Внешний партнёр",
      "custom_updated_at": null
    }
  }
}
```

**Exchange-поля (перезаписываются при синке):** `email`, `login`, `fio`, `display_name`, `department`, `team`, `position`, `is_room`, `is_internal`, `active`, `synced_at`.

**Кастомные поля (не трогаются при синке):** `aliases`, `messenger_ids`, `notes`, `custom_updated_at`.

**Правила:**
- Все даты — UTC ISO-8601 с `Z`.
- `email` — ключ объекта `contacts`.
- `is_internal: bool` — `true` если домен `@tutu.ru` или `@tutu.tech`, иначе `false`. Внешние контакты хранятся в том же `contacts.enc` (единый источник правды).
- `active: false` → контакт удалён из Exchange, но данные хранятся (может потребоваться downstream для истории).
- `aliases` — list строк (другие имена / ники).
- `messenger_ids` — dict (telegram, zulip, jira_login и другие по необходимости).
- `notes` — свободный текст.
- `custom_updated_at` — дата последнего редактирования кастомных полей (null если не редактировались).

---

## 5. Шифрование

**Алгоритм:** AES-256-GCM.

**Ключ:** 32 байта, base64-кодированный, хранится в `.env` как `CONTACTS_ENCRYPTION_KEY`.

**Nonce:** 16 байт (128 бит), генерируется случайно при каждой записи.

**Формат файла `contacts.enc`:**
```
[16 байт nonce (binary)][TAG (16 байт, от GCM)][зашифрованные данные JSON]
```

**При чтении:**
1. Прочитать первые 16 байт → nonce.
2. Прочитать следующие 16 байт → authentication tag.
3. Расшифровать остаток с AES-256-GCM, передав nonce и tag.
4. Парсить JSON.

**При отсутствии ключа в `.env`:**
1. Сгенерировать случайный ключ (32 байта).
2. Закодировать в base64.
3. Вывести инструкцию:
   ```
   ⚠️  CONTACTS_ENCRYPTION_KEY не найден в .env
   Сгенерирован новый ключ (одноразовый, для этого запуска):
   CONTACTS_ENCRYPTION_KEY = <base64>
   
   Добавьте эту строку в .env и перезапустите синк.
   Контакты будут зашифрованы и сохранены с этим ключом.
   ```
4. Exit 2 (ошибка конфигурации, требуется вмешательство).

---

## 6. Редактирование кастомных полей

**Через CLI:**
```bash
python -m movefromexchange contact show email@tutu.ru
python -m movefromexchange contact edit email@tutu.ru aliases '["Ваня", "Иван"]'
python -m movefromexchange contact edit email@tutu.ru messenger_ids '{"zulip": "ivanov.ivan", "jira_login": "iivanov"}'
python -m movefromexchange contact edit email@tutu.ru notes "Ответственный за проект X"
python -m movefromexchange contact find "Иванов"
```

**Через TG-команды:**
```
/contact show email@tutu.ru
/contact edit email@tutu.ru aliases ["Ваня"]
/contact edit email@tutu.ru messenger_ids {"zulip": "login"}
/contact edit email@tutu.ru notes "текст"
/contact find Иванов
```

**При редактировании кастомного поля:**
1. Расшифровать `contacts.enc`.
2. Найти контакт по email.
3. Обновить поле (aliases / messenger_ids / notes).
4. Проставить `custom_updated_at` = текущее время UTC.
5. Перешифровать и записать атомарно.
6. Логировать в `logs/contacts.jsonl` событие `custom_field_edited`.

**Поиск** (`find`):
- По `fio` (полнотекстовый поиск или регулярное выражение).
- По `email` (точное совпадение или подстрока).
- По `aliases` (проверка наличия в list).
- Вернуть список совпадений с выводом email, fio, department, team.

---

## 6a. Запросы и фильтрация контактов (CLI + TG)

**Назначение:** пользователь может запрашивать выборки из `contacts.enc` **без синхронизации с Exchange**, используя CLI или Telegram. Единый источник правды — файл `contacts.enc`.

### CLI-команды для запросов и фильтрации

```bash
# Список контактов (базовые и с фильтрацией)
python -m movefromexchange contacts list                    # все контакты
python -m movefromexchange contacts list --unmatched        # без совпадения с GAL (не синхронизирован)
python -m movefromexchange contacts list --matched          # синхронизированные с GAL (active=true)
python -m movefromexchange contacts list --external         # внешние (is_internal=false)
python -m movefromexchange contacts list --internal         # внутренние (is_internal=true)
python -m movefromexchange contacts list --dept "Аналитики и данных"  # по названию департамента
python -m movefromexchange contacts list --status undefined # по статусу (undefined / active / inactive)

# Сводка контактов
python -m movefromexchange contacts stats                   # вывести статистику (см. формат ниже)
```

**Вывод `contacts list`:**
- Если результаты ≤ 20 записей: таблица в консоль (или Telegram) с колонками: `email | fio | department | is_internal | active`.
- Если результаты > 20 записей: автоматически экспортировать в `.xlsx` и указать путь.

**Формат `contacts stats`:**
```
📊 Контакты:
Всего: 1024
Внутренних: 856 (из них синхронизированных с GAL: 820, undefined: 36)
Внешних: 168
Несинхронизированных (active=false): 42
```

### TG-команды для запросов и фильтрации

Добавить в §9 (TG-команды):

```
# Запросы и фильтрация
/contacts list                        — все контакты (первые 20 + счётчик)
/contacts list unmatched              — несинхронизированные (active=false)
/contacts list matched                — синхронизированные с GAL (active=true)
/contacts list external               — внешние контакты (is_internal=false)
/contacts list internal               — внутренние контакты (is_internal=true)
/contacts list dept <название>        — по названию департамента (частичное совпадение)
/contacts list status <undefined|active|inactive>  — по статусу
/contacts stats                       — сводка по статистике (см. формат выше)
```

**Поведение в Telegram:**
- Результат списка ≤ 20 записей: вывести таблицу в сообщение (используя форматирование Telegram).
- Результат > 20 записей: экспортировать в XLSX, отправить документ (с текстом "📊 Контакты (N записей)").
- Команда `/contacts stats` всегда выводит текстовую сводку в одном сообщении.

---

## 7. Экспорт в `.xlsx`

**CLI:**
```bash
python -m movefromexchange --export
```

**TG-команда:**
```
/contacts export
```

**Процесс:**
1. Расшифровать `contacts.enc`.
2. Создать XLSX через openpyxl с колонками:
   - email
   - fio
   - department
   - team
   - position
   - is_room
   - aliases (JSON-строка или список)
   - messenger_ids (JSON-строка)
   - notes
3. Сохранить во временный файл (с timestamp в имени).
4. Если `--mode manual` / TG → отправить файл в TG (через `send_document`).
5. Удалить временный файл.
6. Exit 0.

**Колонки XLSX:**
| email | fio | department | team | position | is_room | aliases | messenger_ids | notes |
|---|---|---|---|---|---|---|---|---|

---

## 8. TG-уведомления

**Главный принцип:** TG-алерты шлёт **только ручной запуск**. Cron работает молча — все статусы пишутся только в лог.

| Сценарий | TG? | Текст |
|---|---|---|
| **Ручной запуск** (`--mode manual`) — успех | ✅ | Итог: «Синхронизировано N, новых M, обновлено K, неактивных L» |
| **Ручной запуск** — любая ошибка (preflight, Exchange недоступен) | ✅ | Текст ошибки (какой сервер, какая проблема) |
| **Cron** (`--mode cron`) — успех или ошибки | ❌ | Только в `_sync_log.md` и `logs/contacts.jsonl` |
| **Ошибка Exchange (недоступен, timeout)** — всегда | ✅ | Текст ошибки + текущее время + возможная рекомендация |

Флаг `--no-tg` отключает TG-алерт и в ручном режиме (на случай отладки).

---

## 9. Логирование

**`_sync_log.md`** — одна строка на запуск (append-only):
```
2026-05-23 14:30:00Z [manual] synced=42 new=3 updated=5 inactive=2 duration=12.5s
2026-05-23 18:30:00Z [cron] synced=40 new=0 updated=2 inactive=0 duration=8.1s
```

**`logs/contacts.jsonl`** — одна строка JSON на событие:
```json
{"ts":"2026-05-23T14:30:05Z","event":"sync_start","mode":"manual"}
{"ts":"2026-05-23T14:30:15Z","event":"sync_ok","synced":42,"new":3,"updated":5,"inactive":2}
{"ts":"2026-05-23T14:30:20Z","event":"custom_field_edited","email":"user@tutu.ru","field":"aliases"}
{"ts":"2026-05-23T14:30:25Z","event":"export_ok","filename":"contacts_2026-05-23.xlsx"}
{"ts":"2026-05-23T14:30:30Z","event":"sync_error","error":"Exchange timeout"}
```

---

## 10. CLI

```bash
# Синхронизация
python -m movefromexchange --mode cron              # фоновый запуск, без TG
python -m movefromexchange --mode manual            # ручной запуск, с TG-уведомлением
python -m movefromexchange --mode manual --dry-run  # показать что будет синхронизировано, без записи

# Работа с контактами (редактирование)
python -m movefromexchange contact show email@tutu.ru
python -m movefromexchange contact edit email@tutu.ru aliases '["Ваня"]'
python -m movefromexchange contact edit email@tutu.ru messenger_ids '{"zulip": "login"}'
python -m movefromexchange contact edit email@tutu.ru notes "текст"
python -m movefromexchange contact find "Иванов"

# Запросы и фильтрация контактов
python -m movefromexchange contacts list                    # все контакты
python -m movefromexchange contacts list --unmatched        # не синхронизированные (active=false)
python -m movefromexchange contacts list --matched          # синхронизированные (active=true)
python -m movefromexchange contacts list --external         # внешние (is_internal=false)
python -m movefromexchange contacts list --internal         # внутренние (is_internal=true)
python -m movefromexchange contacts list --dept "Аналитики и данных"
python -m movefromexchange contacts list --status undefined
python -m movefromexchange contacts stats                   # сводка

# Экспорт
python -m movefromexchange --export
python -m movefromexchange --export --no-tg        # без отправки в TG

# Утилиты
python -m movefromexchange --verbose                # DEBUG лог
python -m movefromexchange --no-tg                  # отключить TG для всех операций
```

**Коды выхода:**
- `0` — успех
- `1` — частичный успех (часть контактов упала, но основное выполнено)
- `2` — ошибка конфигурации (лок занят, `.env` неполный, ключ отсутствует)
- `3` — Exchange недоступен (сервер не отвечает, таймаут)
- `4` — фатальная ошибка (крах внутри синка, невосстановимая ошибка данных)

---

## 11. Структура проекта

```
MoveFromExchange/
├── .venv/
├── .env                       # EXCHANGE_SERVER, EXCHANGE_LOGIN, EXCHANGE_PASSWORD, 
│                              # CONTACTS_ENCRYPTION_KEY, TELEGRAM_*
├── .env.example
├── pyproject.toml
├── README.md
├── movefromexchange/
│   ├── __main__.py            # CLI + оркестрация (Шаги 0-4)
│   ├── config.py              # pydantic Settings из .env
│   ├── exchange_client.py     # exchangelib + tenacity для подключения к EWS
│   ├── crypto.py              # AES-256-GCM шифрование/расшифровка
│   ├── store.py               # read/write contacts.enc (атомарно)
│   ├── merger.py              # merge Exchange → local (синхронизация, сохранение кастомных полей)
│   ├── exporter.py            # XLSX-экспорт (openpyxl)
│   ├── lock.py                # portalocker
│   ├── logger.py              # _sync_log.md + jsonl
│   ├── tg.py                  # TG-уведомления
│   ├── commands.py            # CLI команды (show, edit, find, export)
│   ├── queries.py             # CLI команды запросов (contacts list, contacts stats)
│   ├── tg_handlers.py         # TG обработчики (включая /contacts list/stats)
│   └── templates/
│       └── (при необходимости шаблоны)
├── tests/
│   ├── test_crypto.py
│   ├── test_merger.py
│   ├── test_exporter.py
│   ├── test_store.py
│   └── fixtures/
└── scripts/
    └── run_cron.bat
```

---

## 12. DoD (Критерии приёмки, 7 пунктов)

1. ✅ `--mode manual --dry-run` выводит список контактов из Exchange (синтаксис: `NEW <email> <fio>` / `UPDATE <email>` / `INACTIVE <email>`) без записи в `contacts.enc`.
2. ✅ Повторный синк не затирает кастомные поля (`aliases`, `messenger_ids`, `notes`, `custom_updated_at`).
3. ✅ Удалённый из Exchange контакт → `active: false`, все остальные данные и кастомные поля сохранены.
4. ✅ Без ключа (`CONTACTS_ENCRYPTION_KEY` в `.env`) → понятная ошибка с инструкцией по генерированию ключа. Exit 2.
5. ✅ `--export` создаёт валидный XLSX-файл с 9 колонками, отправляет в TG (если `--mode manual`), удаляет временный файл.
6. ✅ Параллельный запуск (второй процесс) → exit 2 (лок занят).
7. ✅ Секреты (пароли, ключи) — только в `.env`, в коде нет хардкодов путей и креденшалов.

---

## 13. Интеграция с другими инструментами

### Обновление 2026-05-25: Zulip — первичный источник контактов

**Статус:** Zulip теперь содержит 1167 активных контактов (загружены в `contacts.enc`). API Zulip работает без VPN.

- **MoveFromExchange** по-прежнему важен для:
  - (а) Обогащения `contacts.enc` полями **department** и **position** из GAL (непосредственно из Exchange).
  - (б) Синхронизации информации из Active Directory (при изменении должностей / структуры организации).
  - (в) Будущих инструментов: создание встреч и анализ почты.
- **MoveFromFF + Zulip контакты:** MarkObjectsFromSummary может использовать данные как из Exchange GAL (для внутренних ТУТУ), так и из Zulip (более расширенная база).

### MoveFromFF (синхронизация встреч)
- **MoveFromFF** при обработке встреч заполняет поле `participants` (список email участников) в `_registry.json`.
- **MoveFromFF НЕ делает резолв email → ФИО сам** — это задача downstream-инструмента (MarkObjectsFromSummary).
- **MoveFromFF просто сохраняет email как есть** и полагается на доступность `contacts.enc` для других инструментов.

### MarkObjectsFromSummary (разметка встреч)
- Читает `_registry.json` из MoveFromFF (поле `participants`).
- Для резолва email → ФИО обращается к `contacts.enc` (через `crypto.py` инструмента MoveFromExchange).
- Может использовать данные из Zulip API (1167 контактов) в дополнение к Exchange GAL.
- Обогащает frontmatter встречи данными из справочника (ФИО, department, team).

### Контракт между инструментами
- **MoveFromExchange** гарантирует: зашифрованный, актуальный справочник `contacts.enc` со схемой v1.0, обновляемый регулярно через cron. **Специализируется на данных GAL (department, position из Exchange).**
- **MoveFromFF** гарантирует: email в поле `participants` в `_registry.json`.
- **MarkObjectsFromSummary** читает оба файла и обогащает свои метаданные встреч (может использовать данные как из Exchange, так и из Zulip).
- **Если `contacts.enc` недоступен** — downstream-инструменты работают в режиме graceful degradation (используют email как есть, потребуется дополнительный резолв через Zulip API).

### Confluence/Jira: переход на Keycloak SSO (2026-05-25)
- **Статус:** PAT (Personal Access Token) больше не работает через REST API.
- **Миграция:** используется Keycloak SSO для авторизации (только через браузер).
- **Влияние на MoveFromConfluence:** требуется обновление авторизации для синхронизации задач через REST API (будет рассмотрено в отдельном ТЗ v1.1).

---

## 14. Статус и следующие шаги

**Дата:** 2026-05-23 (обновлено с функционалом запросов) → 2026-05-25 (обновлено с находками о Kerberos, Zulip, Keycloak)  
**Статус:** На согласовании (расширено).

**Подтверждено на практике (2026-05-25):**
- ✅ Exchange EWS: авторизация через Windows Kerberos (пароль НЕ нужен, работает в домене).
- ✅ access_type=DELEGATE обязателен.
- ✅ Версию EWS НЕ указываем явно.
- ✅ Inbox (14 писем), Calendar (43 события), GAL resolve_names работают.
- ✅ Zulip: 1167 активных контактов загружены в `contacts.enc`, API работает без VPN.
- ✅ Confluence/Jira: PAT больше не работает, миграция на Keycloak SSO.
- ✅ merger.py баг исправлен: кастомные поля сохраняются при создании нового контакта.

**Предусмотрены для v1.1+ (out of scope v1.0):**
- Синхронизация кастомных полей **из** Exchange (если появятся custom properties в GAL).
- Интеграция с LDAP/Active Directory для дополнительных источников контактов.
- Версионирование истории контактов (для аудита).
- Web-интерфейс для редактирования справочника.
- Обновление авторизации для Confluence/Jira REST API (переход на Keycloak SSO).
