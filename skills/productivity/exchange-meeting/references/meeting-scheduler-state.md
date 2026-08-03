# MeetingScheduler — состояние реализации (17.06.2026)

## Файлы
```
/home/tkachenkoav/USERTOOLS/MeetingScheduler/
  exchange_client.py   — подключение EWS, VPN-check, free/busy
  rooms_cache.py       — список переговорок МСК, кэш 24ч
  models.py            — MeetingDraft, SlotCandidate, MeetingResult, validate()
  meeting_scheduler.py — MeetingScheduler: find_slots, find_rooms, create_meeting, resolve_contact
  manage_meeting.py    — MeetingManager: find_meetings_by_hint, reschedule, cancel
  holidays.py          — праздники РФ из Exchange CalendarView
  test_meeting.py      — тест создания встречи
  test_manage.py       — тест поиска/переноса
```

## ТЗ
`/home/tkachenkoav/WorkVault/Tools/MeetingScheduler/TZ_meeting_scheduler_v1.0.md` (v1.2)

## Что работает
- ✅ Exchange EWS подключение (TUTU_DOMAIN_PASSWORD, VPN required)
- ✅ Создание CalendarItem с участниками + Fireflies (fred@fireflies.ai)
- ✅ Free/busy через GetUserAvailability
- ✅ models.py с validate()
- ✅ Поиск переговорок МСК (GetRooms, фильтры 13floor/cloudy_land)

## Что не работает / pending
- ❌ Zoom — ждём IT (marketplace.zoom.us 404, developer privileges отключены)
- ❌ relative imports в meeting_scheduler.py — нужно исправить для запуска как скрипт
- 🟡 Validation guards (bk084-validation-guards, job 7a7d412fe48b) — Opus ещё не завершил
- 🟡 Скилл schedule-meeting — создан, но не тестировался

## Zoom обходной путь (пока нет credentials)
Все МСК-переговорки имеют встроенный Zoom Room.
Маппинг: `/home/tkachenkoav/USERTOOLS/ZoomAPI/rooms_map.yaml` (нужно создать).
Для встреч без переговорки — Personal Meeting ID пользователя.
