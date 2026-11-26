# Дедуп и перенос recurring-встречи (exchangelib)

Проверено на автокроне SyncAralov (Синк 1-1 с Араловым, weekly-серия с master в 2025):
`filter(start__range=now, +2мес)` не видит серию (master вне окна) → ложное «встречи нет» → дубль.
`calendar.view` на дату серию видит (type=Occurrence/Exception).

## Найти дубль на слот (в т.ч. recurring)
```python
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from exchangelib import Account, EWSDateTime, CalendarItem

MSK = ZoneInfo("Europe/Moscow")
SUBJECT_NORM = " ".join("синк 1-1 саша - саша".split())


def _ews(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return EWSDateTime.from_datetime(dt.astimezone(MSK))


def _emails(item):
    out = set()
    for attr in ("required_attendees", "optional_attendees"):
        for a in getattr(item, attr, None) or []:
            mb = getattr(a, "mailbox", a)
            em = (getattr(mb, "email_address", None) or "").lower()
            if em:
                out.add(em)
    return out


def subject_hit(subj):
    if not subj:
        return False
    n = " ".join(str(subj).lower().split())
    return n == SUBJECT_NORM or SequenceMatcher(None, SUBJECT_NORM, n).ratio() >= 0.7


def find_in_slot(account, start, end, attendee_email):
    """view(start,end) + клиентский матч. view+filter вместе нельзя."""
    items = account.calendar.view(start=_ews(start), end=_ews(end)).only(
        "subject", "start", "end", "location", "type", "is_recurring", "uid", "organizer")
    hits = []
    for it in items:
        if not isinstance(it, CalendarItem) or not subject_hit(it.subject):
            continue
        it.refresh()
        if attendee_email.lower() in _emails(it):
            hits.append(it)
    return hits
```

## Перенос recurring-instance (Exception)
```python
def reschedule_recurring_item(account, item, manager, slot_start, slot_end, room_email=None):
    """Не мутировать Exception напрямую (calendar:UID-ошибка). Через master+Single."""
    # ДУБЛЬ НА ЦЕЛЕВУЮ ДАТУ ПРОВЕРИТЬ ДО cancel — иначе встреча пропадёт
    if find_in_slot(account, slot_start, slot_end, "aralov@tutu.tech"):
        return "unchanged"  # уже есть — не плодить, НЕ отменять
    master = item.recurring_master()
    master.refresh()
    item.cancel()            # отменить конкретный occurrence
    return manager.reschedule_meeting(  # или create_meeting на новом Single
        master.id, master.changekey, slot_start, slot_end, notify_loop=False,
        new_room_email=room_email)
```

`type`/`uid` нельзя в restriction (`ErrorUnsupportedPathForQuery`). Искать master через
`filter(subject__icontains='Синк 1-1 Саша')` без окна, клиентски `type == RecurringMaster`.

## ErrorServerBusy
Дефолт `Configuration` = FailFast (сразу raise). Для крона `retry_policy=FaultTolerance(max_wait=120)`;
при `ErrorServerBusy` — sleep `e.back_off` (часто 60с), ретрай 1 раз, узкие view-окна, `.only(...)` без участников.
