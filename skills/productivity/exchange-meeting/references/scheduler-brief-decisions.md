# Итоги брифа bk-084 — «Назначить встречу» (17.06.2026)

Все решения финальные, внесены в ТЗ v1.2 и скилл.

| Вопрос | Решение |
|---|---|
| В1 — Триггер | Свободная фраза, LLM-разбор по семантике |
| В2а — Праздники | Из Exchange-сервера (CalendarView на «Russian Holidays»/«Праздники»). Fallback — hardcode 2026 |
| В2б — Переговорки | EWS GetRoomLists. Email-формат исследовать при первом подключении. МСК: 13floor + cloudy_land. Исключить «Кабинет», «Лес» |
| В3 — Неоднозначность | Все уточнения **одним** сообщением. ФИО-кандидаты и номера слотов — в backtick (тап в TG копирует) |
| В4 — Приоритет слотов | Строго хронологически — чем раньше, тем выше |
| В5 — Лимит участников | Максимум 10 включая организатора |
| В6 — Preview | Оставить. Подтверждение «да/нет» обязательно |
| В7 — Fireflies | fred@fireflies.ai добавляем всегда, статус ответа не проверяем |
| Zoom | Отложено до получения credentials от IT. В v1.0 не упоминать |
| Перенос/отмена | В том же инструменте (Раздел 9 ТЗ) |

## Статус реализации (17.06.2026)

- ✅ `models.py` — dataclasses
- ✅ `exchange_client.py` — get_account, check_vpn, get_free_busy
- ✅ `meeting_scheduler.py` — parse_phrase, find_slots, find_rooms, create_meeting, format_slots, format_candidates
- ✅ `rooms_cache.py` — кэш переговорок 24ч
- ✅ `holidays.py` — праздники из Exchange + fallback
- ✅ `manage_meeting.py` — find_meetings_by_hint, reschedule_meeting
- ✅ `test_meeting.py` — smoke-тест (встреча с Криворотовым создана)
- ⏳ Zoom — ждём credentials
- ⏳ LLM-разбор фразы — в v1.0 regex/heuristics, LLM-интеграция позже

## ТЗ
`/home/tkachenkoav/WorkVault/Tools/MeetingScheduler/TZ_meeting_scheduler_v1.0.md` (актуальная версия 1.2)

## Email тестового контакта
Криворотов Кирилл: `krivorotov@tutu.ru` (из AnywhereContacts, источник zulip)
