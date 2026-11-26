---
name: exchange-recurring-meetings
description: "Use when: recurring Exchange встречи (дедуп/перенос)."
version: "1.0.0"
platforms: [linux]
tools: [terminal]
metadata:
  hermes:
    tags: [exchange, ews, exchangelib, recurring, meeting, dedup, tutu]
---

# Exchange recurring-серии: дедуп, поиск, перенос

Класс задач: автоматика вокруг **периодических (recurring)** встреч Exchange через exchangelib — проверка наличия, дедуп перед созданием, перенос существующих экземпляров. Фактический среда: автокрон SyncAralov (weekly «Синк 1-1 Саша-Аралов», master-серии в 2025).

## Pitfall №1 — `filter(start__range)` НЕ разворачивает recurring-серии

**ПДн календаря (19.09.2026):** участников/темы — только через CLI JSON, без одноразовых
exchangelib-скриптов с `print` списков (stdout оседает в process-results, PIIScan-шторм).
Подробно: скилл `exchange-meeting` → «Pitfall: ПДн календаря».

`account.calendar.filter(start__range=now, now+2мес)` возвращает только **master** серии. Мастер recurring-встречи стоит на дате **первого** вхождения (напр. 13.11.2025), а не в просматриваемом окне → серия выглядит «пропавшей», хотя экземпляр на нужную дату существует.

**Правило: окно времени — только `calendar.view(start, end)`, НЕ `filter(start=...)`/`start__range`.** view разворачивает recurring-элементы (`type=Occurrence`/`Exception`). Outlook рисует CalendarView — поэтому «в календаре вижу, бот — нет».

## Поля не searchable в EWS-restriction
- `calendar:UID` — не searchable.
- `type` — не searchable.
`filter(uid=...)`/`filter(type=...)` → `ErrorUnsupportedPathForQuery`. Брать после выборки (клиентски).

## Алгоритм дедупа перед create
1. Слот в МСК (aware) → `EWSDateTime`.
2. `calendar.view(start, end)` по 2–4 ближайшим окнам-датам (для recurring — не один ±5 мин). Узкие окна — `ErrorCalendarViewRangeTooBig` на широких.
3. **`view` + `.filter()` не чейнить** — EWS запрещает; отсев субъект/участников на клиенте (`view(...).only(...)` затем python-фильтр).
4. Игнорировать не-`CalendarItem`: `calendar.all()` может вернуть `Message` без `required_attendees` → `isinstance(item, CalendarItem)`.
5. Матч дубля: нормализовать subject (регистр/пробелы) ≈ эталон ИЛИ `SequenceMatcher(subj, эталон).ratio() >= 0.7`; затем `item.refresh()` (attendees не searchable) и резолв участника в required/optional. **Не** матчить по комнате — её имя бывает у нескольких серий.
6. Для ответа «существует ли серия вообще» — `filter(subject__icontains=...)` без окна start, клиентски `type == RecurringMaster` + участник. Не `filter(type=...)`.

## Pitfall №2 — перенос экземпляра ≠ мутация найденного объекта

`calendar.view` на дату находит объект **Exception** (у него `recurrence=None`; паттерн серии — только на master через `item.recurring_master()`). Прямой `reschedule_meeting(item.id, item.changekey, ...)` на Exception → EWS-ошибка:
`Single calendar item or recurring master is expected. (field: FieldURI(field_uri='calendar:UID'))`

**Для переноса recurring-instance:** работай через master — `item.recurring_master().refresh()`, отмена конкретного occurrence (`item.cancel()`), затем создание свежего **Single** на целевом слоте (`create_meeting`/`reschedule_meeting` нового). **Проверяй дубль на целевую дату ДО cancel** — иначе при конфликте переносимая встреча пропадёт (guard: если дубль уже есть — не cancel, action=unchanged).

## Pitfall №3 — `get_free_busy_info` возвращает генератор
`len()` неприменим («object of type 'generator' has no len()»). На аккаунт приходит `FreeBusyMerged` + `DetailedMerged`. Запрашивать **по одному участнику за раз**, фильтровать `view_type=='FreeBusyMerged'`, busy-интервалы — из `calendar_events` с `busy_type!='Free'`. Записи `00:00-00:00 Busy/OOF` означают весь день занят / отпуск — индикатор недоступности.

## ErrorServerBusy
Дефолт `Configuration` = FailFast (сразу raise). Для крона — `Configuration(retry_policy=FaultTolerance(max_wait=120))`. При `ErrorServerBusy`: sleep `e.back_off` (часто 60с), 1 retry, затем raise. Не крутить широкие `subject__contains` по всему ящику пачками — сервер busy.

## Готовый сниппет
`references/recurring-meeting-dedup.md` — `find_in_slot()`/`subject_hit` + `reschedule_recurring_item()` (master+cancel+Single, дубль до cancel).
