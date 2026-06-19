# Grafana (monitoring.tutu.ru) — Keycloak OAuth авторизация через curl

## Контекст
- Grafana: `https://grafana.monitoring.tutu.ru`
- Защита: oauth2-proxy + Keycloak SSO (`keycloak.tutu.ru/realms/tutu`)
- Bearer-токен НЕ работает — oauth2-proxy требует cookie-сессию
- ROPC через `admin-cli` выдаёт токен, но oauth2-proxy его не принимает
- **Рабочий способ**: полный OAuth2 Authorization Code flow через curl с cookie jar

## Рабочий flow (проверен 03.06.2026)

```bash
PASSWORD=$(grep TUTU_DOMAIN_PASSWORD ~/.config/hermes/.env | cut -d'=' -f2)
rm -f /tmp/gc.txt

# Шаг 1: инициируем OAuth flow — получаем форму логина Keycloak
curl -s -c /tmp/gc.txt -b /tmp/gc.txt \
  "https://grafana.monitoring.tutu.ru/login/generic_oauth" -L -o /tmp/g1.html

# Шаг 2: извлекаем action URL формы
ACTION=$(grep -o 'action="[^"]*"' /tmp/g1.html | head -1 | sed 's/action="//;s/"$//' | sed 's/&amp;/\&/g')

# Шаг 3: POST логин → Keycloak выдаёт code и редиректит на Grafana
LOCATION=$(curl -s -c /tmp/gc.txt -b /tmp/gc.txt \
  -X POST "$ACTION" \
  --data-urlencode "username=tkachenkoav" \
  --data-urlencode "password=${PASSWORD}" \
  -D - -o /tmp/g2.html 2>/dev/null | grep -i "^location:" | head -1)

REDIRECT_URL=$(echo "$LOCATION" | sed 's/location: //i' | tr -d '\r')

# Шаг 4: следуем Location — Grafana завершает OAuth и выдаёт grafana_session cookie
curl -s -c /tmp/gc.txt -b /tmp/gc.txt \
  "$REDIRECT_URL" -L -o /tmp/g3.html

# Проверка — должен появиться grafana_session_expiry
grep "grafana_session" /tmp/gc.txt
```

## Проверка авторизации
```bash
curl -s -c /tmp/gc.txt -b /tmp/gc.txt \
  "https://grafana.monitoring.tutu.ru/api/org"
# Ожидается: {"id":1,"name":"TUTU.RU",...}
```

## Запрос данных через datasource proxy
- Datasource MySQL uid: `bfevw4pelknb4e`
- Dataset: `cursordatacollector`
- Таблицы: `usage_events`, `team_members`

```bash
curl -s -c /tmp/gc.txt -b /tmp/gc.txt \
  -X POST "https://grafana.monitoring.tutu.ru/api/ds/query" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "queries": [{
      "datasource": {"type": "mysql", "uid": "bfevw4pelknb4e"},
      "rawSql": "SELECT DATE_FORMAT(event_time, \"%Y-%m-%d\") as day, ROUND(SUM(charged_cents)/100,4) as dollars, model FROM usage_events WHERE user = \"tkachenkoav@tutu.ru\" AND event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY) GROUP BY day, model ORDER BY day",
      "format": "table",
      "refId": "A"
    }],
    "from": "now-30d",
    "to": "now"
  }'
```

## Важные питфоллы
- **Кавычки в SQL**: использовать `\"` внутри `--data-raw '...'` для экранирования
- **Одинарные кавычки в SQL через shell**: вместо `'value'` использовать `\"value\"` (двойные)
- **Сессия живёт**: grafana_session_expiry хранится в /tmp/gc.txt — не удалять между запросами
- **web_extract заблокирован** для внутренних адресов — только curl

## Схема БД (usage_events)
```
event_time, user, model, kind, max_mode,
input_tokens, output_tokens, is_token_based_call,
cache_write_tokens, charged_cents, total_cents,
cursor_token_fee_cents, requests_costs,
is_chargeable, is_headless, updated_at
```

## Дашборд Cursor Usage
- uid: `podmnqh`
- URL: `https://grafana.monitoring.tutu.ru/d/podmnqh/cursor-usage`
- Переменная `$user` фильтрует по email
