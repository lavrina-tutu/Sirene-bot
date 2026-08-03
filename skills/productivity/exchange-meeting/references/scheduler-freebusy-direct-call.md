# Прямой вызов get_free_busy_info (обход find_slots)

Используй этот паттерн когда `find_slots(draft)` падает с ошибкой `Mailbox` / `Email` типов.

## Рабочий код (проверен 2026-06-18)

```python
import sys, zoneinfo
from datetime import datetime
sys.path.insert(0, '/home/tkachenkoav/USERTOOLS')
from MeetingScheduler.meeting_scheduler import MeetingScheduler
from MeetingScheduler.exchange_client import MSK
from exchangelib import EWSDateTime
from exchangelib.properties import Email

scheduler = MeetingScheduler()

# Резолвим участника
participant = scheduler.resolve_contact("Фамилия")[0]

# Временное окно (сегодня)
msk_tz = zoneinfo.ZoneInfo("Europe/Moscow")
today = datetime.now(msk_tz).date()
start_ews = EWSDateTime(today.year, today.month, today.day, 0, 0, tzinfo=MSK)
end_ews   = EWSDateTime(today.year, today.month, today.day, 23, 59, tzinfo=MSK)

# Список email-адресов (Саша + участник)
emails = ['tkachenkoav@tutu.ru', participant.email]
accounts = [(Email(email_address=e), "Required", False) for e in emails]

# Запрос
results = list(scheduler.account.protocol.get_free_busy_info(
    accounts=accounts,
    start=start_ews,
    end=end_ews,
    merged_free_busy_interval=30,
    requested_view="DetailedMerged",
))
# results[i].calendar_events — список CalendarEvent(start, end, busy_type, details)
# results[i].working_hours   — рабочие часы участника
# results[i].merged          — строка типа "000022110..." (0=Free,1=Tentative,2=Busy)
```

## Анализ слотов вручную

```python
from datetime import timedelta

def find_free_slots(calendar_events_per_user, work_start_h=9, work_end_h=17, duration_h=1):
    """
    calendar_events_per_user: list of list[CalendarEvent]
    Возвращает [(start_min, end_min), ...] свободных слотов.
    """
    all_busy = []
    for events in calendar_events_per_user:
        for ev in (events or []):
            if ev.busy_type != 'Free':
                s = ev.start.hour * 60 + ev.start.minute
                e = ev.end.hour * 60 + ev.end.minute
                all_busy.append((s, e))

    now_min = datetime.now(zoneinfo.ZoneInfo("Europe/Moscow"))
    current_min = now_min.hour * 60 + now_min.minute

    work_start = work_start_h * 60
    work_end   = work_end_h * 60
    duration   = duration_h * 60

    t = max(work_start, current_min)
    if t % 30: t = (t // 30 + 1) * 30  # округление вверх до 30 мин

    slots = []
    while t + duration <= work_end:
        blocked = any(not (t + duration <= bs or t >= be) for bs, be in all_busy)
        if not blocked:
            slots.append((t, t + duration))
        t += 30

    return slots
```

## Типичная структура ответа

- Детальный ответ (`DetailedMerged`): `calendar_events` содержит детали (тему, location).  
  Детали доступны только для **своего** аккаунта — чужие события возвращаются без `details`.
- Упрощённый ответ (`MergedOnly`): только строка `merged` без `calendar_events`.
- `working_hours`: `[WorkingPeriod(weekdays=[1..5], start=time(9,0), end=time(19,0))]`

## Питфоллы

- `timezone(timedelta(hours=3))` → `UnknownTimeZone` в exchangelib. Только `zoneinfo` или `MSK` из exchange_client.
- `EWSDateTime` нельзя передавать в `EWSDateTime.from_datetime()` — только обычный `datetime`.
- `Mailbox(email_address=e)` не принимается в `get_free_busy_info` — нужен `Email(email_address=e)`.
