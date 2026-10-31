# `/model <id>` валится «Sorry, I encountered an unexpected error» — модель не в allowlist custom_providers

Реальный инцидент 10.09.2026. Алиас `/anl` = `/model z-ai/glm-5.3-flash` роутился на `openrouter` (нет ключа) вместо Tutu, потому что `z-ai/glm-5.3-flash` не было в `custom_providers[].models` провайдера `tutu`.

## Почему так происходит (механика)

В Hermes роутинг `/model <id>` без `--provider` идёт через `hermes_cli/model_switch.switch_model()` → `detect_provider_for_model()` (PATH B):

1. `_model_in_provider_catalog("<id>", _provider_keys(current_provider))` — False, если `<id>` НЕТ в `custom_providers[].models` провайдера. ВАЖНО: каталог для этой проверки строится из `_PROVIDER_MODELS` (жёстко зашитой таблицы) + `get_compatible_custom_providers()` (из config). Если модели нет в config-allowlist, она туда не попадает.
2. `_find_openrouter_slug("<id>")` — находит `<id>` в каталоге OpenRouter (т.к. модель публично доступна) → возвращает `('openrouter', <id>)`.
3. Сессия переключается на `provider=openrouter`, у которого нет `OPENROUTER_API_KEY` → `resolve_provider_client: openrouter requested but OPENROUTER_API_KEY not set` → `RuntimeError: No LLM provider configured` → юзеру «Sorry, I encountered an unexpected error» на каждый запрос.

Модель при этом на шлюзе `tutu` валидна и отвечает — проблема только в allowlist конфига.

## Диагностика (по шагам)

```bash
# 1. Симптом в логах
grep -nE "switch_model.*openrouter" ~/.hermes/logs/agent.log | tail
grep -nE "No LLM provider configured" ~/.hermes/logs/errors.log | tail
# agent.log: switch_model: ... -> z-ai/glm-5.3-flash (openrouter)
# errors.log: resolve_provider_client: openrouter requested but OPENROUTER_API_KEY not set

# 2. Проверить allowlist в config — есть ли <id> в models: провайдера tutu
grep -nA30 "^custom_providers" ~/.hermes/config.yaml | grep -nE "glm|deepseek|name: tutu"

# 3. NOT полагаться на `agent --list-models` — он показывает только picker-модели,
#    не полный каталог шлюза. z-ai/glm-5.3-flash там НЕ будет.

# 4. Smoke-тест самой модели на шлюзе (если HTTP 200 — модель валидна, дело в allowlist)
KEY=$(python3 -c "import yaml;print(yaml.safe_load(open('/home/tkachenkoav/.hermes/config.yaml'))['custom_providers'][0]['api_key'])")
curl -s -w "\nHTTP:%{http_code}\n" https://llm-gateway.tutu.ru/api/openrouter/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"z-ai/glm-5.3-flash","messages":[{"role":"user","content":"ок"}],"max_tokens":10}'
```

## Фикс

1. Бэкап: `cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-<что>-$ (date +%Y%m%d-%H%M%S)`
2. Добавить `<id>` (и нужные вариации: `:batch`, `~alias-latest`) в `custom_providers[].models` провайдера `tutu`. YAML-safe (список строк — можно добавить вручную, но проверить валидность после).
3. Верификация на реальном коде (ДО фикса → `openrouter`, ПОСЛЕ → `custom:tutu`):

```bash
cd ~/hermes-agent && .venv/bin/python - <<'PY'
import yaml
from hermes_cli.model_switch import switch_model
cfg=yaml.safe_load(open('/home/tkachenkoav/.hermes/config.yaml'))
r=switch_model("z-ai/glm-5.3-flash", current_provider="tutu",
               current_model="deepseek/deepseek-v4-flash-0731",
               custom_providers=cfg["custom_providers"])
print(r.success, r.target_provider)
# Ожидаемо: True custom:tutu
PY
```

4. Рестарт gateway НЕ обязателен для смены модели в сессии, но config перечитывается на новой сессии.

## Что сказать пользователю

- Сессия, залипшая на openrouter, не починится сама: `/reset`, затем снова `/model <id>` или алиас.
- Диагноз: алиас/модель не была в allowlist провайдера.

## Профилактика

- После создания алиаса quick_command (`/anl`→`/model z-ai/...`) — сразу проверять, что целевая модель есть в `custom_providers[].models` провайдера, и switch_model резолвит в `custom:`. Исключает оффлайн-ошибку при первом же использовании.
- Каталог шлюза НЕ равно каталог `custom_providers[].models`: первый — что физически доступно, второй — белый список для роутинга. Не путать.