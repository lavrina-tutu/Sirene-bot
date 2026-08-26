# MFE (ExchangeMonitor) — cron и классификация встреч

## Крон-задача

- **ID:** `f61b26cbbdf5`
- **Имя:** `MoveFromLoop — срочные сообщения`
- **Расписание:** `*/3 * * * *` (каждые 3 минуты, круглосуточно, без ограничений по часам)
- **Профиль:** `default` (не tz-dev)
- **Режим:** `no_agent=true` — скрипт `mfl_urgent_check.py`, stdout → Telegram
- **Скрипт:** `~/USERTOOLS/MoveFromLoop/scripts/urgent_check.py`

Если уведомления не приходят вне рабочего дня — это не крон молчит, а нет подходящих писем или watermark «уехал».

## Два кодовых пути (питфолл)

В коде существуют **две** реализации Exchange-мониторинга:

1. **`movefromloop/exchange_urgent.py`** — правильная, с `should_skip()`, покрыта тестами, **НО не вызывается entry-скриптом**. Это мёртвый код.
2. **`exchangemonitor/urgent.py`** (`~/USERTOOLS/ExchangeMonitor/`) — **реально работающий** путь крона. `should_skip()` подключён в v0.4.3.

При отладке MFE всегда смотреть `exchangemonitor/urgent.py`, а не `movefromloop/exchange_urgent.py`.

## EWS message_class — классификация встреч

| message_class | Тип | Поведение в should_skip() |
|---|---|---|
| `IPM.Schedule.Meeting.Resp.Pos` | Принятие (accept) | **SKIP** — не уведомлять |
| `IPM.Schedule.Meeting.Resp.Neg` | Отклонение (decline) | Forward |
| `IPM.Schedule.Meeting.Resp.Tent` | Tentative | Forward |
| `IPM.Schedule.Meeting.Counter` | Контр-предложение | Forward |
| `IPM.Schedule.Meeting.Update` | Перенос/обновление (организатор) | Forward |
| `IPM.Schedule.Meeting.Canceled` | Отмена | Forward |

`should_skip()` (в `movefromloop/exchange_filter.py`) проверяет **только** `Resp.Pos`. Все остальные типы встреч проходят как обычные письма.

Фетчер `exchangemonitor/fetcher.py` включает `message_class` в `.only()` (v0.4.3+) — поле доступно.

## Пароль Exchange

Берётся из `~/.config/hermes/.env` → `TUTU_DOMAIN_PASSWORD`. Если отсутствует в файле — фолбэк на env var. Без пароля Exchange-путь молча возвращает пустой результат.
