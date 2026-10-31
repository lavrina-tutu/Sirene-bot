# Loop API — диагностика 502 и тестирование эндпоинтов

## Инцидент 07.08.2026

**Симптом:** крон `f61b26cbbdf5` (MoveFromLoop urgent) упал с exit=1:
```
[urgency_checker] API error resolving usernames: POST /api/v4/users/usernames → 502: <html>...
```

**Причина:** временный 502 Bad Gateway от бэкенда Mattermost (не наш gateway).
`loop_api.py` делает 3 ретрая (backoff 1/3/9с = 13с суммарно), при всех 502 кидает `LoopApiError`.

**Результат тестирования (07.08.2026, после восстановления Mattermost):**
| Эндпоинт | Метод | Статус |
|---|---|---|
| `/api/v4/users/me` | GET | ✅ 200 |
| `/api/v4/teams` | GET | ✅ 200 |
| `/api/v4/users/usernames` | POST | ✅ 200 |
| `/api/v4/users/ids` | POST | ✅ 200 |
| `channel_members` | GET | ✅ 200, 3358 членов |

**Клиент:** `requests` в `loop_api.py` работает стабильно (retry 3×, 5xx/429/timeout). Старый питфолл «requests зависает на loop.tutu.ru» больше не актуален.

**Окружение крона:**
- `.env` грузится из `~/.hermes/profiles/anthropic/.env` (там LOOP_TOKEN=ujde9bzq...)
- `LOOP_URL` не задан, используется дефолт `https://loop.tutu.ru`
- `tz-dev/.env` содержит тот же LOOP_TOKEN (файлы синхронизированы)
- `TUTU_DOMAIN_PASSWORD` НЕТ в этих файлах — нужен `~/.config/hermes/.env` для ExchangeMonitor

**Баг в `mfl_urgent_check.py`:** при падении ExchangeMonitor (`RuntimeError: TUTU_DOMAIN_PASSWORD не задан`) — весь скрипт делает `sys.exit(1)`, хотя Loop-часть отработала нормально (SILENT). Нужно разделить обработку.
