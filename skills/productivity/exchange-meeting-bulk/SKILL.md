---
name: exchange-meeting-bulk
description: "Use when создаём массовую встречу без Loop."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [exchange, ews, meeting, bulk, mass, schedulers, tutu]
    related_skills: [exchange-meeting, tutu-confluence-jira, about_usr_skills]
---

# Exchange Meeting — Bulk / Mass scheduling

Расширение флоу единичной встречи (`exchange-meeting`) для массовых собраний: демонстрации, рассылки по списку PM, встречи на 10–50 человек, добавление optional/Cc пачкой. Код: `/home/tkachenkoav/USERTOOLS/MeetingScheduler/` (meeting_scheduler.py, manage_meeting.py, rooms_cache.py, models.py, loop_notify.py, exchange_client.py).

## When to Use
- Создать встречу на много участников (10+): демонстрация, презентация, рассылка по роли/отделу.
- Пригласить список людей (ФИО) как необязательных (optional/Cc) к уже созданной встрече.
- Массовая встреча БЕЗ спама Loop-уведомлений каждому участнику.
- Выбор переговорки «без примыкающих встреч» и с заданной вместимостью, только МСК.

## Ключевые паттерны (v1.8, ТЗ: `~/WorkVault/Hermes-Backlog/TZ/MeetingScheduler/MeetingScheduler_TZ.md`)

### 1. Отключить Loop для массовой встречи
`MeetingScheduler.create_meeting(draft, notify_loop=False)` и `add_participant(..., notify_loop=False)` — пропускают блок Loop-уведомлений, приглашения уходят только через Exchange. **Всегда включать для массовых рассылок** (Саша: «массовые встречи — Loop не слать никому»).

### 2. Bulk-резолв списка ФИО → email
`resolve_contact` для одного имени блокирует при неоднозначности. Для массового списка (N имен):
- ровно 1 кандидат → берём;
- 2+ кандидатов → не блокировать, но в отчёт сводная строка «Резолвлено N из M, не резолвлено: …» (решение В3: сводка, не переспрос);
- используй `display_name or fio or login` (в контактах бывает пустой display_name, но заполнен `fio` — как у Алексеевой Анастасии из login `alekseevaas`);
- чужой домен (не `@tutu.ru`, напр. `@alfabank.ru`) → внешний участник, обычно исключать по решению Саши.

### 3. Массовое добавление optional-участников
`add_participant()` шлёт письма только новому и требует повторного `get()` changekey перед каждым вызовом → N round-trip и риск `ErrorStaleObject`. Для пачки использовать `add_participants_bulk()` (один `get()`, один `save()`, дедуп против existing и внутри списка). Refresh changekey после каждого save при ручном циклическом добавлении.

### 4. Поиск слота для массовой встречи
- Слот ищется **по первым N (default 5) обязательным участникам**, не по всем (решение В2).
- Недоступных весь день на дату — молча исключать из расчёта, но в приглашение с пометкой «недоступен весь день»; занятых только на выбранный слот — тоже приглашаем, помечаем.
- Ориентир на конкретного участника (Саша называет «по свободному времени [Имя]») — подбирать под него.

### 5. Переговорка: вместимость + буфер + location
- `find_rooms` параметры: `min_capacity`/`max_capacity` (не хардкод 4–8), только МСК.
- Буфер: мягкое предпочтение — сначала переговорка без примыкающих встреч (`[start-buffer, end+buffer]`, default 15 мин); если нет — любая свободная с пометкой ⚠️ (решение В5).
- Автозаполнить `item.location = "Zoom - <Переговорка>"` (или платформа без переговорки) — Саша требует именно этот формат местоположения.

## Pitfalls (проверено на живом коде)

**ПДн календаря (19.09.2026):** участников/темы — только через CLI JSON, без одноразовых
exchangelib-скриптов с `print` списков (stdout оседает в process-results, PIIScan-шторм).
Подробно: скилл `exchange-meeting` → «Pitfall: ПДн календаря».
```bash
# 1. rooms_cache: get_rooms(rl) НЕ работает — нужен rl.email_address
account.protocol.get_rooms(rl.email_address)   # ✅
account.protocol.get_rooms(rl)                  # ❌ TypeError must be of type str

# 2. find_meetings_by_hint падает на сортировке
# TypeError: can't compare EWSDateTime to EWSDate
# → обходить: acc.calendar.get(id=item_id) напрямую для актуального changekey

# 3. changekey меняется после КАЖДОГО save — при добавлении нескольких участников
#    по отдельности перечитывать item перед следующим add
```
Подробности: `references/bulk-session-notes-20260831.md`.

## Workflow (пошагово, массовая встреча)
1. Резолв списка ФИО (см. §2) — молча пропустить неоднозначные + сводка.
2. Отфильтровать уже приглашённых участников существующей встречи (no-duplicate по email required∪optional).
3. `create_meeting(draft, notify_loop=False)` ИЛИ добавить optional пачкой через `add_participants_bulk()`.
4. Найти переговорку: min вместимость под кол-во людей, MСК, буфер без примыканий (fallback ⚠️).
5. `item.location = "Zoom - <Переговорка>"`.
6. Верифицировать на диске: `acc.calendar.get(id=...)` → required/optional/resources/location.

## Notes
- External-участники (@не-tutu) — по умолчанию исключать, подтверждать у Саши.
- Guard bk-172: прямой `CalendarItem` без `create_meeting`/`add_participant` блокируется shell-хуком `pre_tool_call` — всегда идти через MeetingScheduler.
- Hermes-память не должна подменять это ТЗ: реальные решения В1–В5 и константы (BULK_THRESHOLD=8, SOFT_LIMIT=50, BULK_SLOT_HEAD_N=5) — в master-ТЗ.

## References
- `references/bulk-session-notes-20260831.md` — разбор реального кейса 31.08 (массовая встреча Trisigma), точные фрагменты кода и обходы