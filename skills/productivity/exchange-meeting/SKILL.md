---
name: exchange-meeting
description: "Exchange calendar operations via EWS: create meetings, check free/busy, find slots, invite attendees. Integrates with AnywhereContacts for email lookup and Zoom API for meeting links."
version: "1.1.0"
platforms: [linux, macos, windows]
tools: [terminal]
metadata:
  hermes:
    tags: [exchange, ews, calendar, meeting, tutu, exchangelib]
---

# Exchange Meeting — управление встречами через EWS

## Триггеры
- «Назначь встречу с [контакт]»
- «Создай встречу», «Найди слоты», «Проверь календарь»
- Инструмент bk-084: «Назначить встречу»

## ⚠️ ОБЯЗАТЕЛЬНОЕ ПРАВИЛО: только Exchange
**Все встречи создаются ИСКЛЮЧИТЕЛЬНО через Exchange EWS (cas.tutu.ru).**
Google Calendar не используется никогда — даже если упоминается в контексте.
Причина: в ТУТУ корпоративный календарь = Exchange. Google OAuth настроен без Calendar scope.

## Обязательные проверки перед созданием встречи

**СТОП — не создавать встречу если:**
1. ❌ Повестка не указана → спросить явно: «Какая повестка встречи?»
2. ❌ Участник не найден в AnywhereContacts → показать похожих, уточнить у Саши
3. ❌ У участника нет email → уточнить контакт

На уровне кода защищено: `MeetingScheduler.create_meeting()` поднимает `ValueError` при пустой `agenda`, пустых `participants` или участнике без email. `MeetingDraft.validate()` возвращает список ошибок. `parse_phrase()` оставляет `agenda=None` если повестка не извлечена.

**Поиск контакта — алгоритм (`MeetingScheduler.resolve_contact`):**
1. Точный поиск: все слова запроса должны входить в `display_name`.
2. Если 0 результатов → нечёткий поиск по каждому слову (длина ≥ 3) отдельно.
3. **1 кандидат** → уточнить: «Ты имеешь в виду [Имя] ([email])?»
4. **2–5 кандидатов** → показать список, Саша выбирает.
5. **0 кандидатов** → «Не нашла [имя] в контактах, уточни написание».

**⚠️ Pitfall MeetingScheduler relative imports:** `meeting_scheduler.py` использует `from .models import ...` — это сломается при запуске как скрипт (`python3 meeting_scheduler.py`). Запускать через `python3 -m MeetingScheduler` (требует `PYTHONPATH=/home/tkachenkoav/USERTOOLS`, иначе `No module named MeetingScheduler`) или добавить `__init__.py` и использовать как пакет. Зависимости: `pip install exchangelib portalocker loguru pydantic-settings`.

**⚠️ Pitfall Whisper:** голосовой ввод (Whisper/VoiceFlow) искажает русские фамилии — буква может замениться (Криворотов → «Кривородов», Калмыкова → «Колмыкова»). Всегда запускать нечёткий поиск, не только точный. Если нашли похожих — показать список, не угадывать.

## Окружение ТУТУ
- **EWS endpoint:** `https://cas.tutu.ru/EWS/Exchange.asmx`
- **Пользователь:** `tkachenkoav@tutu.ru`
- **Пароль:** `TUTU_DOMAIN_PASSWORD` из `~/.config/hermes/.env`
- **VPN:** обязателен — без него `cas.tutu.ru` недоступен
- **Библиотека:** `exchangelib` (`pip install exchangelib`)

## Проверка доступности Exchange
```bash
source ~/.config/hermes/.env
curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
  -u "tkachenkoav:$TUTU_DOMAIN_PASSWORD" \
  https://cas.tutu.ru/EWS/Exchange.asmx
```
- `200` / `401` — хост доступен (401 = нужна правильная аутентификация)
- `timeout` / `000` — VPN не подключён

## Подключение через exchangelib
```python
import os
from exchangelib import (
    Credentials, Account, Configuration, DELEGATE,
    EWSDateTime, EWSTimeZone
)
from exchangelib.items import CalendarItem
from exchangelib.properties import Attendee, Mailbox

creds = Credentials(
    username="tkachenkoav",
    password=os.environ["TUTU_DOMAIN_PASSWORD"]
)
config = Configuration(
    server="cas.tutu.ru",
    credentials=creds
)
account = Account(
    primary_smtp_address="tkachenkoav@tutu.ru",
    config=config,
    autodiscover=False,
    access_type=DELEGATE
)
```

## Создание встречи
```python
from datetime import datetime, timedelta

tz = EWSTimeZone("Europe/Moscow")  # НЕ .timezone() — см. pitfall ниже
start = EWSDateTime(2026, 6, 18, 10, 0, tzinfo=tz)
end = start + timedelta(minutes=30)

item = CalendarItem(
    account=account,
    folder=account.calendar,
    subject="Название встречи",
    body="Повестка встречи",
    start=start,
    end=end,
    required_attendees=[
        Attendee(mailbox=Mailbox(email_address="krivorotov@tutu.ru")),
        Attendee(mailbox=Mailbox(email_address="fred@fireflies.ai"), response_type="Unknown"),  # всегда добавлять
    ]
)
item.save(send_meeting_invitations="SendToAllAndSaveCopy")
print("Created:", item.id)
```

## Переговорки ТУТУ (МСК)

**МСК-переговорки** определяются по email:
- Содержит `13floor` в адресе — комнаты на 13 этаже МСК
- Точное совпадение `cloudy_land.room@tutu.ru` — Мутный материк (МСК)

**Исключать** при автовыборе: названия содержащие «Кабинет» или «Лес» (case-insensitive).

**Предпочтительная вместимость:** 3–8 человек, сортировка: сначала [3..8] ≥ N участников, потом >8.

**Все МСК-переговорки имеют встроенный Zoom** (суффикс `- Zoom` в названии).

Получение списка через EWS:
```python
rooms = account.protocol.get_roomlists()
for rl in rooms:
    members = account.protocol.get_rooms(rl)
```
Кэшировать на сутки в `~/.cache/hermes/meeting_rooms.json`.

## Рабочие часы для поиска слотов

**Жёстко 10:00–19:00 МСК** — игнорировать настройки Working Hours в Exchange у сотрудников.
Шаг перебора предлагаемых слотов: **30 минут**. Кандидаты **только в будущем**: старт перебора = округление текущего времени МСК вверх до ближайшего получаса (11:47 → первый слот 12:00; 12:01 → 12:30; ровно 12:00 → можно 12:00). Только Пн–Пт, исключая праздники РФ. (Интервал EWS free/busy остаётся 15 мин.)

## Anti-duplicate guard (реализован в MeetingScheduler v1.1)

**Проблема:** встреча задваивается если пользователь уже создал её вручную или бот вызван дважды.

Перед каждым созданием — `MeetingScheduler.check_duplicate(draft)` (окно ±5 мин, overlap ≥2 участников ИЛИ fuzzy-тема ≥0.7). При дубле без явного подтверждения — **не создавать**.

**CLI:** флаг `--force` обходит guard (только после явного «да» от Саши).

**Python (если не CLI):**
```python
dup = scheduler.check_duplicate(draft)
if dup is not None:
    respond(f"Похоже, такая встреча уже есть:\n📅 {dup.subject}\n🕒 {dup.start}\n\nВсё равно создать?")
    return  # ждём явного «да» → повтор с force или --force в CLI
```

⚠️ **Реальный кейс (18.06.2026):** встреча задвоилась — guard обязателен.

## Fireflies

Всегда добавлять `fred@fireflies.ai` (НЕ стандартный notetaker@fireflies.ai) как Attendee с `response_type="Unknown"`.

## Free/Busy запрос (слоты участников)
```python
from exchangelib.services import GetUserAvailability
from exchangelib.properties import MailboxData, FreeBusyViewOptions, TimeWindow

# Запросить занятость на 5 дней
tz = EWSTimeZone("Europe/Moscow")  # НЕ .timezone()
start = EWSDateTime.now(tz)
end = start + timedelta(days=5)

result = account.protocol.get_free_busy_info(
    accounts=[(account, "Required", False),
               (Mailbox(email_address="krivorotov@tutu.ru"), "Required", False)],
    start=start,
    end=end,
    merged_free_busy_interval=30  # минут
)
```

## Поиск email через AnywhereContacts
```python
import dotenv
from pathlib import Path
from anywhere_contacts import create_store, ContactsBaseSettings

dotenv.load_dotenv("/home/tkachenkoav/USERTOOLS/AnywhereContacts/.env")
s = ContactsBaseSettings()

# ВАЖНО: путь должен указывать на ФАЙЛ contacts.enc, не на директорию
store = create_store(
    Path("/home/tkachenkoav/WorkVault/Contacts/contacts.enc"),
    s.contacts_encryption_key
)
data = store.read()
contacts = data.get("contacts", {})

# Поиск по имени
query = "Криворотов"
for login, info in contacts.items():
    if query.lower() in info.get("display_name", "").lower():
        # Email: sources.exchange.email или sources.zulip.email (на верхнем уровне, не smtp_addresses)
        src = info.get("sources", {})
        email = (src.get("exchange", {}).get("email") or
                 src.get("zulip", {}).get("email"))
        print(login, info.get("display_name"), email)
```

**⚠️ Pitfall:** `create_store()` требует путь к файлу `contacts.enc`, не к директории. Если передать директорию `~/WorkVault/Contacts/` — будет `IsADirectoryError`.

**⚠️ Pitfall:** `ContactStore` не имеет методов `search()` и `load()`. Правильный API: `store.read()` → dict с ключом `"contacts"`.

## venv для exchangelib
```bash
cd /home/tkachenkoav/USERTOOLS/ExchangeMeeting
python3 -m venv venv
source venv/bin/activate
pip install exchangelib python-dotenv
```

## ⚠️ Pitfall: EWSTimeZone API в exchangelib 5.6.0

`EWSTimeZone.timezone("Europe/Moscow")` → `AttributeError: type object 'EWSTimeZone' has no attribute 'timezone'`

**Правильно:**
```python
tz = EWSTimeZone("Europe/Moscow")
```

## ⚠️ Pitfall: ПДн календаря — не печатать списки участников (инцидент 19.09.2026)

Ад-хок exchangelib-скрипты в терминале (перебор календаря с печатью тем встреч и списков
участников) оставляют stdout в `~/.hermes/logs/process-results/proc_*.json` в сыром виде
(ФИО+email, до 7 суток) и порождают шторм PIIScan (19.09 — 4764 находок, 811 critical в ErrorBus).

Правила:
- Календарь/участников смотреть **только через CLI JSON** (`MeetingScheduler`, `ExchangeMonitor`) —
  там поля разнесены и не создают декартовых «ФИО × email».
- Никаких одноразовых `exchangelib`-скриптов с `print` списков участников/тем.
- В чат/TG — имя/логин, **не** пары ФИО+email; при уточнении кандидата — одно имя.
- Не трогать: `process_registry_results.py` (ядро Hermes, вне скоупа — решение Саши 21.09).

## ⚠️ Pitfall: чтение пароля из ~/.config/hermes/.env

`dotenv.load_dotenv()` ломается на этом файле (syntax error near unexpected token). Использовать ручной парсинг:
```python
password = None
for line in open(os.path.expanduser("~/.config/hermes/.env")):
    key = "TUTU_DOMAIN_PASSWORD=***    if line.startswith(key):
        v = line[len(key):].rstrip("\n")
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        password = v
        break
```

## ⚠️ Pitfall: названия категорий в русском Outlook

Категории в Exchange именуются с окончанием — **не** `"Оранжевый"`, а `"Оранжевая категория"`.
Полный список стандартных русских категорий:
- `"Оранжевая категория"`
- `"Зелёная категория"` (встречается как `"Зеленая категория"`)
- `"Красная категория"`
- `"Синяя категория"`
- `"Жёлтая категория"`
- `"Фиолетовая категория"`

При создании события:
```python
item = CalendarItem(
    ...
    categories=["Оранжевая категория"],  # НЕ "Оранжевый"
    legacy_free_busy_status="Busy",
    reminder_is_set=True,
    reminder_minutes_before_start=0,
)
item.save(send_meeting_invitations="SendToNone")  # для личных событий без участников
```

Чтобы узнать реальные названия категорий у пользователя — можно прочитать существующие события и посмотреть `item.categories` у тех, где категория уже выставлена.

## Создание личного события (без участников / appointment)

Отличается от митинга: `send_meeting_invitations="SendToNone"`, без `required_attendees`.
```python
item = CalendarItem(
    account=account,
    folder=account.calendar,
    subject="Название события",
    body="Описание",
    start=start,
    end=end,
    categories=["Оранжевая категория"],
    legacy_free_busy_status="Busy",   # Занят
    reminder_is_set=True,
    reminder_minutes_before_start=0,  # напоминание за 0 минут
)
item.save(send_meeting_invitations="SendToNone")
```

## ⚠️ Pitfall: EWSTimeZone API

`EWSTimeZone.timezone("Europe/Moscow")` → `AttributeError: type object 'EWSTimeZone' has no attribute 'timezone'`

Правильно (exchangelib 5.x):
```python
tz = EWSTimeZone("Europe/Moscow")
```

## ⚠️ Pitfall: загрузка пароля из ~/.config/hermes/.env

`python-dotenv` ломается на файле `~/.config/hermes/.env` из-за синтаксиса (кавычки, спецсимволы). Использовать ручной парсинг:

```python
password = None
for line in open(os.path.expanduser("~/.config/hermes/.env")):
    key = "TUTU_DOMAIN_PASSWORD="
    if line.startswith(key):
        v = line[len(key):].rstrip("\n")
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        password = v
        break
```

## Категории календаря (Outlook)

Для цвета события используй `categories=[...]` в `CalendarItem`.

**⚠️ ВНИМАНИЕ:** названия категорий в русском Outlook — полные с окончанием «категория»!

Стандартные названия в **русском** Outlook:
- `"Оранжевая категория"` — оранжевый/рыжий
- `"Красная категория"`, `"Жёлтая категория"`, `"Зелёная категория"`, `"Синяя категория"`, `"Фиолетовая категория"`

В **английском** Outlook: `"Orange Category"`, `"Red Category"`, и т.д.

⚠️ Если категория с таким именем не создана у пользователя — цвет не применится, событие создастся без цвета.

**Реальный кейс (19.06.2026):** `categories=["Оранжевый"]` не работало — пришлось исправлять на `"Оранжевая категория"`. Запомни: полное название!

```python
item = CalendarItem(
    ...
    categories=["Оранжевая категория"],  # НЕ просто "Оранжевый"!
    legacy_free_busy_status="Busy",
    reminder_is_set=True,
    reminder_minutes_before_start=0,
)
item.save(send_meeting_invitations="SendToNone")  # личное событие без приглашений
```

## Связь со скиллом schedule-meeting (absorbed)

**UX флоу MeetingScheduler** (диалог с Сашей, форматирование слотов, confirm/preview, перенос/отмена) был в отдельном скилле `schedule-meeting`. Содержимое поглощено сюда — загружай только `exchange-meeting`.

## Личные события (appointments без участников)

Для создания личных событий (конференции, напоминания, поездки) — **НЕ использовать MeetingScheduler**, он требует участников.

Паттерн для личных событий напрямую:
```python
import os
from datetime import datetime
from exchangelib import (
    Account, Configuration, Credentials, DELEGATE,
    EWSDateTime, EWSTimeZone, CalendarItem,
)

# Пароль через ручной парсинг (НЕ dotenv!)
password = None
for line in open(os.path.expanduser("~/.config/hermes/.env")):
    if line.startswith("TUTU_DOMAIN_PASSWORD="):
        v = line.split("=", 1)[1].rstrip("\n")
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        password = v
        break

# Подключение
creds = Credentials(username="tkachenkoav", password=password)
config = Configuration(server="cas.tutu.ru", credentials=creds)
account = Account("tkachenkoav@tutu.ru", config=config, autodiscover=False, access_type=DELEGATE)

tz = EWSTimeZone("Europe/Moscow")

# Создание события
item = CalendarItem(
    account=account,
    folder=account.calendar,
    subject="Конференция: Больше чем менеджмент",
    body="Описание...",
    start=EWSDateTime(2026, 6, 20, 10, 0, tzinfo=tz),
    end=EWSDateTime(2026, 6, 20, 11, 0, tzinfo=tz),
    categories=["Оранжевая категория"],  # цвет в русском Outlook
    legacy_free_busy_status="Busy",       # Занят/Free/Tentative/OOF
    reminder_is_set=True,
    reminder_minutes_before_start=0,      # напоминание в начале
)
item.save(send_meeting_invitations="SendToNone")  # БЕЗ приглашений
print(f"Created: {item.id}")
```

**⚠️ Pitfall (19.06.2026):** категории в русском Outlook = `"Оранжевая категория"`, НЕ `"Оранжевый"`. Полное название с окончанием!

### MeetingScheduler Python Tool (расположение кода)

**Путь:** `/home/tkachenkoav/USERTOOLS/MeetingScheduler/`

**Запуск Python с зависимостями:**
```bash
/home/tkachenkoav/USERTOOLS/AnywhereContacts/venv_linux/bin/python3
```
и `sys.path.insert(0, '/home/tkachenkoav/USERTOOLS')` перед импортом.

### Создание встречи — ТОЛЬКО через CLI

**⚠️ ЗАПРЕЩЕНО при создании и мутациях встреч:** `write_file` / heredoc / `python3 -c` с `MeetingDraft(...)` или прямым `CalendarItem` с `required_attendees` (bk-172). Единственный путь — CLI MeetingScheduler.

**СТОП перед `create` / `reschedule`:**
1. `--subject` = дословная формулировка Саши (допустима только орфография по-русски, В23). **Запрещено** укороченный subject / ярлык / обрезка по первой точке.
2. Обязателен `--notify-loop` **или** `--no-notify-loop` (без флага CLI exit ≠ 0). На переносе вопрос задаётся **заново**, ответ create не наследуется (В22).
3. `--duration` default 60 — не спрашивать, если Саша не указал.
4. `--agenda` = только блок 3 тела; HTML собирает `_build_html_body`.

```bash
PYTHONPATH=/home/tkachenkoav/USERTOOLS /home/tkachenkoav/USERTOOLS/AnywhereContacts/venv_linux/bin/python3 -m MeetingScheduler create \
  --attendee krivorotov@tutu.ru \
  --subject "AI-аналитик. Обсуждаем задачи необходимые и достаточные для достижения целей + видение архитектуры" \
  --agenda "Обсуждаем как достигаем цель …" \
  --duration 60 \
  --start "2026-09-02T11:00:00+03:00" \
  --notify-loop \
  --dry-run
```

Флаги `create`:
| Флаг | Назначение |
|------|------------|
| `--attendee` | повторяемый; email напрямую или имя → `resolve_contact` |
| `--subject` | тема дословно (± орфография В23); дефолт «Собрание Ткаченко А.» |
| `--duration` | минуты (дефолт 60, не спрашивать) |
| `--no-room` | `need_room=False` |
| `--room-name` | переговорка по названию |
| `--start` | ISO datetime; без него — первый слот через `find-slots` / `find_slots` |
| `--window-end` | верхняя граница окна поиска слота |
| `--agenda` / `--agenda-file` | повестка / блок 3 (обязательна) |
| `--notify-loop` / `--no-notify-loop` | **обязательная пара** на create и reschedule |
| `--dry-run` | preview JSON без создания |
| `--force` | обойти `check_duplicate` после явного «да» |

**Мутации — только CLI** (без Loop-флагов на add/remove/cancel):
```bash
PYTHONPATH=/home/tkachenkoav/USERTOOLS python3 -m MeetingScheduler add --item-id ID --changekey CK --participant email@tutu.ru
PYTHONPATH=/home/tkachenkoav/USERTOOLS python3 -m MeetingScheduler remove --item-id ID --changekey CK --participant email@tutu.ru
PYTHONPATH=/home/tkachenkoav/USERTOOLS python3 -m MeetingScheduler reschedule --item-id ID --changekey CK --start ISO --notify-loop
PYTHONPATH=/home/tkachenkoav/USERTOOLS python3 -m MeetingScheduler cancel --item-id ID --changekey CK
PYTHONPATH=/home/tkachenkoav/USERTOOLS python3 -m MeetingScheduler find-slots --attendee … --agenda …
```

Алгоритм CLI create: VPN → `MeetingDraft` → (без `--start`) `find_slots` → `--dry-run`? → `check_duplicate` → `create_meeting` (Loop только при `--notify-loop`) → JSON.

При `status: duplicate` в JSON — спросить Сашу; при «да» — повтор с `--force`.

### parse_phrase (только для разбора фразы в диалоге)

```python
import sys
sys.path.insert(0, '/home/tkachenkoav/USERTOOLS')
from MeetingScheduler.meeting_scheduler import MeetingScheduler
scheduler = MeetingScheduler()
draft = scheduler.parse_phrase(phrase)
```

`parse_phrase` — для извлечения полей из фразы Саши. **Создание встречи** — только CLI (см. выше), не `MeetingDraft(...)` + `create_meeting()` вручную.

Проверить draft: участники (если пусто — «Кого пригласить?»), `agenda` (если `None` — спросить), `duration_minutes` (дефолт 60).

**Вопрос о переговорке (обязательный шаг):** если Саша явно указал тему и/или текст встречи, но НЕ сказал явно, нужна ли переговорка — Сирень обязана задать вопрос «Нужна ли переговорка?» (и, если да — на сколько человек). Вопрос не задаётся только если про переговорку сказано явно (например «в переговорке на 5» или «без переговорки»). Если переговорка нужна — ищем свободную переговорку МСК ёмкостью 4–8 человек. Только после этого — free/busy и поиск слотов.

**Лимит участников:** если `len(draft.participants) + 1 > 10` — немедленно «Слишком много участников (N), максимум 10», free/busy не запрашивать.

### Форматирование слотов

```python
def format_slots(slots):
    lines = ["Нашла варианты:\n"]
    day_names = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    month_names = ["","янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]
    for i, s in enumerate(slots, 1):
        day = day_names[s.start.weekday()]
        date_str = f"{day} {s.start.day} {month_names[s.start.month]}"
        time_str = f"{s.start.strftime('%H:%M')}–{s.end.strftime('%H:%M')} МСК"
        room_str = f" · «{s.room_name}»" if s.room_name else " · без переговорки ⚠️"
        cap_str = f" ({s.room_capacity} чел)" if s.room_capacity else ""
        lines.append(f"`{i}` {date_str} {time_str}{room_str}{cap_str}")
    return "\n".join(lines)
```

Числа в backtick — тап в TG копирует в буфер. При 0 слотов → предложить расширить окно.

### Preview перед созданием

```
📅 <тема>
🕒 <день недели, дата, время МСК>
👥 <участники через запятую>
🏢 <переговорка> (если есть)
📝 <повестка>

Создаём? (да/нет/правки)
```

### ⚠️ Verify: не закрывать тур, пока create реально не отработал

**Правило (15.10.2026):** после фактического запуска `MeetingScheduler create` НЕ завершать ход и НЕ сообщать «создаю», пока в JSON нет `"status": "created"`.

- Смотрю поля в выводе CLI: `status` должен быть `created` (или `duplicate` — тогда вопрос Саше). `dry_run` / `error` / отсутствие `meeting_id` = встреча НЕ создана.
- Только получив `status: created` + `meeting_id` + `loop_delivered` — объявлять создание.
- Это защита от кейса, когда ход прерывается (interrupt) и tool-call реально не выполняется, а я уже заявила «создаю». **Сначала tool-call с результатом, потом слова.**

### Anti-duplicate guard (ВСЕГДА перед созданием)

Используй `check_duplicate(draft)` / CLI без `--force`. При дубле — предупреждение Саше, ждать «да», затем `--force`.

```bash
# dry-run для preview, затем create; при duplicate — повтор с --force
PYTHONPATH=/home/tkachenkoav/USERTOOLS /home/tkachenkoav/USERTOOLS/AnywhereContacts/venv_linux/bin/python3 -m MeetingScheduler create ... --dry-run
PYTHONPATH=/home/tkachenkoav/USERTOOLS /home/tkachenkoav/USERTOOLS/AnywhereContacts/venv_linux/bin/python3 -m MeetingScheduler create ... 
PYTHONPATH=/home/tkachenkoav/USERTOOLS /home/tkachenkoav/USERTOOLS/AnywhereContacts/venv_linux/bin/python3 -m MeetingScheduler create ... --force   # только после «да»
```

### Loop-уведомление Required-участникам (v1.9)

**Обязательный вопрос перед create и reschedule:** «уведомление в Loop? (да/нет)». Без ответа CLI не вызывать. `--no-notify-loop` → 0 постов в Loop. Add/remove/cancel — Loop без переспроса (add — только новому; cancel — всем Required кроме организатора).

«Привет!» в Loop — по переписке **за сегодня** (00:00 МСК), не по дню встречи. Ссылка в Loop — PMI `https://tutu-ru.zoom.us/my/tkachenkoav.meet`.

**«Направил встречу» (отдельная ветка, не смешивать с «Привет!»):** Loop-notify on **meeting date**, not message activity: if the meeting is **TODAY** → auto-send «Направил встречу»; otherwise (future date) → **ASK Sasha** before notifying. SEPARATE branch from the «Привет!» greeting-on-today's-correspondence rule — do NOT merge them.

**Create (шаблон §6.2):** между строкой со ссылкой Zoom и строкой «на …» (дата/время) — отдельная строка `Тема: <subject из Exchange>`. В add / reschedule / cancel отдельной строки «Тема:» нет (тема в заголовке сообщения).

Loop вызывается **внутри** `create_meeting` / `reschedule_meeting` / `add_participant` / `cancel_meeting` — **не** вызывать `LoopNotifier` напрямую из скилла при штатном флоу.

**`--notify-loop` JSON contract:** interpret `loop_report_line=null` as «тихий успех» (silent success); `loop_delivered` = success. Do not treat `null` as failure/no-op.

### Перенос и отмена встречи — только CLI

```bash
PYTHONPATH=/home/tkachenkoav/USERTOOLS python3 -m MeetingScheduler reschedule \
  --item-id ID --changekey CK --start "2026-09-02T15:00:00+03:00" --notify-loop
PYTHONPATH=/home/tkachenkoav/USERTOOLS python3 -m MeetingScheduler cancel \
  --item-id ID --changekey CK
```

Идентификация встречи в диалоге: `find_meetings_by_hint(hint)` через Python **только для поиска**, мутация — CLI.

### Добавление участника — только CLI

```bash
PYTHONPATH=/home/tkachenkoav/USERTOOLS python3 -m MeetingScheduler add \
  --item-id ID --changekey CK --participant email@tutu.ru
```

Loop на add — автоматически новому участнику (без вопроса «уведомление в Loop?»).

### Массовые встречи (v1.8, >8 участников)

**Create defaults (bulk 10+):** default venue `location` = «Платформа - Переговорка»; `--subject` verbatim (дословно); no external attendees (без внешних участников). Limit `>10` already enforced (see above).

**Подтверждение размера** — перед free/busy, если обязательных > 8:
```
Точно {N} человек? Подтверди, чтобы продолжить
```
После «да» → `draft.bulk_size_confirmed = True` → `find_slots(draft)`.

**Строка резолва bulk** (если не все имена резолвились):
```
👥 Резолвлено {resolved} из {total}, не резолвлено: {имена}
```
Или через `draft.resolve_summary.as_report_line()`.

**Недоступные участники** (bulk, tail после head-5):
```
⚠️ Приглашены, но недоступны: {имена}
```

**Переговорка впритык** (буфер 15 мин не влез):
```
«{room_name}» ⚠️ впритык
```

**Массовое добавление** — `MeetingManager.add_participants_bulk(item_id, changekey, participants)`:
один get/save, optional_attendees, Loop не отправляется.

### Ключевые питфоллы MeetingScheduler

- `MeetingDraft` использует `chosen_start`/`chosen_end`, НЕ `start`/`end`
- `get_free_busy_info` требует `Email(email_address=...)`, не `Mailbox(...)` — TypeError иначе
- `EWSDateTime` не принимает `timezone(timedelta(hours=3))` — использовать `zoneinfo.ZoneInfo("Europe/Moscow")` + `MSK` из exchange_client только для EWSDateTime
- VPN проверять перед каждым действием: `from MeetingScheduler.exchange_client import check_vpn`

### Дополнительные справочники (absorbed from schedule-meeting)

- `references/scheduler-brief-decisions.md` — итоги брифа bk-084: UX, алгоритмы, интеграции, статус
- `references/scheduler-freebusy-direct-call.md` — рабочий паттерн прямого вызова `get_free_busy_info` (обход сломанного `find_slots`)

## Связанные файлы
- `references/anywherecontacts-api.md` — правильный API ContactStore + паттерн нечёткого поиска, схема полей контакта, pitfalls Whisper-ошибок в фамилиях
- `references/zoom-tutu-setup.md` — Zoom S2S OAuth setup для ТУТУ
- `references/conference-schedule-pattern.md` — паттерн сохранения расписания конференции в WorkVault + последующее создание событий в календаре

## Zoom API (корпоративный ТУТУ)

**⚠️ Pitfall:** `marketplace.zoom.us/develop/create` даёт 404 — администратор `tutu-ru.zoom.us` отключил developer privileges для пользователей. Без IT-отдела Marketplace закрыт.

**Краткосрочный обходной путь:**
- Для встреч в переговорках `- Zoom` — там стоит Zoom Room с постоянным join-URL. Собрать маппинг `room_email → join_url` в YAML (`/home/tkachenkoav/USERTOOLS/ZoomAPI/rooms_map.yaml`).
- Для встреч без переговорки — ссылка на личную постоянную Zoom-комнату пользователя (Personal Meeting ID).

**Долгосрочно:** попросить IT одним письмом — либо выдать developer privileges на `tkachenkoav@tutu.ru`, либо создать S2S OAuth app от их имени и передать `Account ID`, `Client ID`, `Client Secret`. После этого — инструкция в `/home/tkachenkoav/USERTOOLS/ZoomAPI/README.md`.

**⚠️ Pitfall:** Zoom Personal Access Token (PAT) для REST API **не существует** — только S2S OAuth или user-level OAuth. Ссылка на PAT-документацию в devforum — ошибочна.

**⚠️ Pitfall:** Zoom add-in Outlook нельзя дёрнуть из EWS/exchangelib — он работает только через UI. `IsOnlineMeeting` в EWS относится к Teams, не Zoom.

## Инструмент «Назначить встречу» (bk-084)

ТЗ: `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/MeetingScheduler/MeetingScheduler_TZ.md`
Код: `/home/tkachenkoav/USERTOOLS/MeetingScheduler/` — CLI: `python -m MeetingScheduler create ...`

Флоу: фраза → парсинг (AnywhereContacts) → вопрос о переговорке (если не указано явно) → free/busy → 3 слота → выбор → переговорка → preview → подтверждение → **CLI create** → Exchange + Loop.

## Интеграции
- **Fireflies** → `fred@fireflies.ai` как Attendee (см. выше)
- **People/ карточки** → `/home/tkachenkoav/WorkVault/People/<Имя>/card.md`
- **Zoom** → `references/zoom-tutu-setup.md`

---

## Личные события (appointments без участников)

Для создания личных событий в календаре (конференции, напоминания, блокировка времени) — БЕЗ приглашений участникам:

```python
import sys, os

# Чтение пароля — ТОЛЬКО ручным парсингом, dotenv не работает из-за спецсимволов
password = None
for line in open(os.path.expanduser("~/.config/hermes/.env")):
    key = "TUTU_DOMAIN_PASSWORD=***    if line.startswith(key):
        v = line[len(key):].rstrip("\n")
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        password = v
        break

from exchangelib import Credentials, Account, Configuration, DELEGATE, EWSDateTime, EWSTimeZone
from exchangelib.items import CalendarItem

tz = EWSTimeZone("Europe/Moscow")  # ⚠️ НЕ EWSTimeZone.timezone() — не работает в exchangelib 5.6.0

creds = Credentials(username="tkachenkoav", password=password)
config = Configuration(server="cas.tutu.ru", credentials=creds)
account = Account(
    primary_smtp_address="tkachenkoav@tutu.ru",
    config=config, autodiscover=False, access_type=DELEGATE
)

item = CalendarItem(
    account=account,
    folder=account.calendar,
    subject="Название события",
    body="Описание",
    start=EWSDateTime(2026, 6, 19, 10, 0, tzinfo=tz),
    end=EWSDateTime(2026, 6, 19, 11, 0, tzinfo=tz),
    categories=["Оранжевая категория"],   # русский Outlook: полное название с окончанием
    legacy_free_busy_status="Busy",
    reminder_is_set=True,
    reminder_minutes_before_start=0,
)
item.save(send_meeting_invitations="SendToNone")  # личное, без рассылки
```

### Категории в русском Outlook (полные названия)
| Цвет | Название |
|------|----------|
| 🔴 Красный | `"Красная категория"` |
| 🟠 Оранжевый | `"Оранжевая категория"` |
| 🟡 Жёлтый | `"Жёлтая категория"` |
| 🟢 Зелёный | `"Зелёная категория"` |
| 🔵 Синий | `"Синяя категория"` |
| 🟣 Фиолетовый | `"Фиолетовая категория"` |

⚠️ **Pitfall (19.06.2026):** `categories=["Оранжевый"]` не работает — категория не применяется. Нужно полное русское название с окончанием: `"Оранжевая категория"`.

### Когда использовать напрямую vs MeetingScheduler
- **Личные события БЕЗ участников** (participants == [], конференции-для-себя, блокировка времени, напоминания) →
  `CalendarItem` напрямую по паттерну выше, ОБЯЗАТЕЛЬНО с комментарием `# guard-override: personal-event`
  в исполняемом коде (иначе guard-хук bk-172 заблокирует вызов) и `required_attendees` не задан / пуст.
- **Любая встреча с ≥1 участником** (создание, перенос, отмена, добавление участника) →
  ТОЛЬКО через MeetingScheduler / MeetingManager (`create_meeting`, `reschedule_meeting`,
  `cancel_meeting`, `add_participant`). Прямой `CalendarItem(...)` с `required_attendees`
  ЗАПРЕЩЁН — это инцидент bk-172 (31.08, «Парсинг. Прокси»): терялись Привет!/Zoom/Loop.

---

## Section C: Teams Meeting Pipeline (Microsoft Graph)

**When to use:** User asks about Microsoft Teams meeting summaries, transcripts, recordings, action items, or Graph webhook subscriptions. Uses `hermes teams-pipeline` CLI subcommands — no new model tools needed.

**Prerequisites** (in `~/.hermes/.env`):
```bash
MSGRAPH_TENANT_ID=...
MSGRAPH_CLIENT_ID=...
MSGRAPH_CLIENT_SECRET=...
```
If missing → direct user to Azure AD app registration with admin-consented Graph application permissions.

### Command Reference

```bash
hermes teams-pipeline validate              # config snapshot — run first after any change
hermes teams-pipeline token-health          # Graph token status
hermes teams-pipeline list                  # recent meeting jobs
hermes teams-pipeline list --status failed  # only failed jobs
hermes teams-pipeline show <job-id>         # full detail of one job
hermes teams-pipeline subscriptions         # current Graph webhook subscriptions
hermes teams-pipeline run <job-id>          # replay a stored job
hermes teams-pipeline fetch --meeting-id <id>   # dry-run: resolve meeting + transcript
```

### Subscription Management
```bash
hermes teams-pipeline subscribe \
  --resource communications/onlineMeetings/getAllTranscripts \
  --notification-url https://<your-public-host>/msgraph/webhook \
  --client-state "$MSGRAPH_WEBHOOK_CLIENT_STATE"

hermes teams-pipeline maintain-subscriptions   # renew near-expiry subscriptions
hermes teams-pipeline renew-subscription <sub-id> --expiration <iso-8601>
hermes teams-pipeline delete-subscription <sub-id>
```

### Decision Tree
- "Why didn't I get a summary?" → `list --status failed` → `show <job-id>`. If no job exists → check `subscriptions` (webhook may have expired).
- "Is setup working?" → `validate` → `token-health` → `subscriptions`.
- "Re-run summary for meeting X" → `list` to find job ID → `run <job-id>`.

### ⚠️ Critical Pitfall: Graph subscriptions expire in 72 hours

Graph caps webhooks at 72 hours and **won't auto-renew**. Schedule `maintain-subscriptions` via cron at 12-hour intervals (6× safety margin):
```python
cronjob(action='create', schedule='0 */12 * * *',
        prompt='hermes teams-pipeline maintain-subscriptions',
        no_agent=True)
```

### Other Pitfalls
- Transcript not available yet: Teams needs 2-5 min after meeting ends for transcript artifact
- 401/403 despite clean token-health: admin consent wasn't re-granted after permission changes — revisit Azure portal → "Grant admin consent"
- Delivery mode mismatch: check `platforms.teams.extra.delivery_mode` in config.yaml

### Docs
- Azure app registration: `/docs/guides/microsoft-graph-app-registration`
- Full pipeline setup: `/docs/user-guide/messaging/teams-meetings`
- Operator runbook: `/docs/guides/operate-teams-meeting-pipeline`
