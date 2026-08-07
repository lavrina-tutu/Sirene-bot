# Pitfalls из багфикса MoveFromLoop v0.4.2 (07.08.2026)

## 1. Асимметричная обработка ошибок в cron-скриптах

При диагностике падения cron (exit != 0) stderr может содержать сообщение от ошибки, которая **уже обработана** (try/except поглотил), а сам exit код — от **другого** вызова в той же цепочке, который не обёрнут.

**Пример:** `mfl_urgent_check.py`
- stderr строка 1: `[urgency_checker] API error resolving usernames: 502` — ошибка **обработана** в `urgency_checker.py:80` (except Exception, исключение съедено)
- stderr строка 2: `[urgent_check] FATAL: ... channel_members → 502` — ошибка **НЕ обработана** в `urgent.py:51` (fetch_mentions без try/except) → `sys.exit(1)`

**Правило:** при диагностике cron-падений трассировать ВСЮ цепочку вызовов от entry-point функции до API, проверяя каждый вызов на наличие try/except. Не останавливаться на первом видимом сообщении в stderr.

## 2. Watermark потеря при полном отказе API

`urgent.py:44-48` — при пустом `urgent_ids` (протухший кеш + API down) watermark **всё равно** двигается на `now_ms()` → при следующем запуске сообщения в окне недоступности **навсегда потеряны**.

**Решение:** использовать независимую health-пробу (`client.me()`) → если API упал, watermark НЕ двигать → при следующем запуске проверим тот же период.

## 3. Race condition между кронами на общем state-файле

`urgent.py` и `digest.py` пишут один `watermark.json` через `State.save()` (атомарный `os.replace`). При пересечении по времени — один прогон **затирает** `seen_ids` и `watermark` другого → дубликаты в Telegram + откат watermark назад.

**Решение:** `fcntl.flock` на отдельном `.lock` sidecar-файле (НЕ на самом `.json`, иначе `os.replace` сломает lock). Retry 10× по 1с. При повторном отказе — warning в stderr, НЕ писать файл.

## 4. .env из неверного профиля

Скрипты `mfl_urgent_check.py` и `mfl_digest.py` грузили `.env` из `/home/tkachenkoav/.hermes/profiles/anthropic/.env` (старый профиль), а не из `tz-dev/.env` или `~/.config/hermes/.env`. Следствия:
- `TUTU_DOMAIN_PASSWORD` не грузится → ExchangeMonitor **постоянно и незаметно неработоспособен** (RuntimeError гасится в try/except)
- `CONTACTS_ENCRYPTION_KEY`, `CONTACTS_PATH` не заданы → проверка `contacts.enc` отключена

**Правило:** грузить `.env` из текущего профиля Hermes ИЛИ из `~/.config/hermes/.env`. Если модули из нескольких проектов — грузить `.env` из каждого источника.

## 5. RETRY_BACKOFF: последний бэкофф не применяется

`loop_api.py:41-69`: `RETRY_BACKOFF = (1, 3, 9)` — на 3-й (последней) попытке код **сразу** бросает исключение без `time.sleep(9)`. Документированное окно ~13с vs реальное ~4с.

**Исправление:** `time.sleep(backoff)` выполнять ВСЕГДА — и перед `continue`, и перед финальным `raise`.

## 6. Паттерн: health-probe при работе с неизменяемыми зависимостями

Когда диагностика указывает на баг в модуле, который «Что НЕ трогать», НЕ выходи за периметр. Вместо этого — добавь независимую health-пробу на уровне вызывающего кода.

**Прецедент:** `urgency_checker.py` (баг в молчании при частичном отказе API) был вне периметра → `client.me()` добавлен в `urgent.py` как независимый индикатор живости API → watermark не двигается при outage. Это не хак — это валидный инженерный паттерн: caller не зависит от internals callee, но добавляет защитную проверку на уровне контракта.
