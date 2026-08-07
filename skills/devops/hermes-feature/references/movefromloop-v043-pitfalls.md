# MoveFromLoop v0.4.3 — Dead Code vs. Working Code Pitfall

## Контекст

При диагностике Exchange-мониторинга обнаружено два параллельных Exchange-потока:

| Модуль | Статус | Описание |
|---|---|---|
| `movefromloop/exchange_urgent.py` | **Мёртвый код** | Имеет `should_skip()` из `exchange_filter`, покрыт тестами, но НИКОГДА не вызывается entry-скриптом `mfl_urgent_check.py` |
| `exchangemonitor/urgent.py` | **Рабочий код** | Вызывается из `mfl_urgent_check.py` через `run_urgent_exchange()`, НЕ имеет `should_skip()`, НЕ запрашивает `message_class` в `.only()` |

## Баг

`exchangemonitor/fetcher.py` не включил `message_class` в `.only()` → `should_skip()` всегда возвращал `False` даже если бы был добавлен.
`exchangemonitor/urgent.py` вообще не импортировал `should_skip` → все принятия встреч от срочных контактов летели в Telegram.

## Фикс

1. `exchangemonitor/fetcher.py` — добавить `"message_class"` в `.only()`
2. `exchangemonitor/urgent.py` — `from movefromloop.exchange_filter import should_skip`, вставить проверку в ветку `if not kw_hit` после `is_real_person()`

## Урок

При багфиксе: **всегда** проследить цепочку импортов от entry-point до бизнес-логики. Если в репозитории есть два модуля с похожей функциональностью — один может быть legacy/migrating, а другой — рабочим. Чинить только рабочий путь.
