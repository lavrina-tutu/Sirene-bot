---
name: hermes-tutu-gateway
description: "Tutu LLM gateway models. Use when routing to Tutu gateway."
version: 0.1.0
author: agent
tags: [hermes, tutu, gateway, models, llm]
platforms: [linux]
---

# Tutu LLM Gateway

Base URL: `https://llm-gateway.tutu.ru/api/openrouter/v1`
Auth: Bearer token из `custom_providers.tutu.api_key` в config.yaml

## Подтверждённые модели (2026-08-17)

| Модель | Работает | Tool Calling | Extended Thinking / Reasoning |
|---|---|---|---|
| `deepseek/deepseek-v4-pro` | ✅ | ✅ (нужно проверить) | ✅ (`reasoning` field в response) |
| `deepseek/deepseek-v4-flash-0731` | ✅ (verified 17.08) | ✅ | ✅ принимает `reasoning: {effort: high}` — HTTP 200, отвечает, в ответе есть `reasoning`/`reasoning_details` |
| `google/gemini-2.5-flash-lite` | ✅ | ✅ (verified) | ❌ (не требуется) |

## Ключ шлюза — НЕ `ANTHROPIC_API_KEY` (важно!)

Единственный валидный ключ ТУТУ-шлюза — `custom_providers.tutu.api_key` в `~/.hermes/config.yaml` (64-символьный hex, маска `8933...cbb0`).

- `ANTHROPIC_API_KEY` из `~/.hermes/.env` (108 симв., `sk-a...`) — **НЕ ключ шлюза**: запрос с ним возвращает `HTTP 401 invalid or missing API key` (`source: gateway, code: unauthorized`).
- Внешние инструменты (PFS/MFF/MOFS, `~/USERTOOLS/*`), которые лезут на шлюз напрямую и читают `ANTHROPIC_API_KEY`, фактически **не могут валидно ходить** → тихий fail-soft (пропуск работы). При подключении такого инструмента читай ключ из `custom_providers.tutu.api_key` (config.yaml) или давай env `LLM_GATEWAY_API_KEY`.
- Быстрый пробный вызов модели без ключа в логах:
```bash
KEY=$(python3 -c "import yaml;print(yaml.safe_load(open('/home/tkachenkoav/.hermes/config.yaml'))['custom_providers'][0]['api_key'])")
curl -s -w "\nHTTP:%{http_code}\n" https://llm-gateway.tutu.ru/api/openrouter/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"deepseek/deepseek-v4-flash-0731","messages":[{"role":"user","content":"hi"}],"reasoning":{"effort":"high"}}'
```
(HTTP 200 + usage.cost не ноль = модель и ключ валидны; HTTP 401 = ключ не тот.)

## Проверка доступности модели и цены (каталог OpenRouter)

Прямой `models.openrouter.ai/api/v1/models` из ВМ закрыт (HTTP 000), но каталог доступен ЧЕРЕЗ ТУТУ-шлюз. Отдаёт `id`, `pricing` (in/out), `context_length`, `supported_parameters` (tool calling / reasoning есть или нет) — можно сравнивать доступность и цены кандидатов до маршрутизации:

```bash
KEY=$(python3 -c "import yaml;print(yaml.safe_load(open('/home/tkachenkoav/.hermes/config.yaml'))['custom_providers'][0]['api_key'])")
curl -s "https://llm-gateway.tutu.ru/api/openrouter/v1/models" -H "Authorization: Bearer $KEY" -o /tmp/or_models.json
python3 -c "
import json
d=json.load(open('/tmp/or_models.json'))
models=d.get('data',d) if isinstance(d,dict) else d
for m in models:
    if 'glm' in m['id'].lower() or ('deepseek' in m['id'] and 'flash' in m['id']):
        p=m.get('pricing',{})
        print(m['id'], '| in', p.get('prompt'), '| out', p.get('completion'), '| ctx', m.get('context_length'))
"
```

Питфоллы: поле `data` может отсутствовать (массив прямо) — обрабатывать оба варианта; фильтровать по `id.lower()` (регистр разный: `GLM`, `z-ai`); цены в $ за токен, контекст в токенах.

## Alias-модели `*-latest` и поле `pricing` в `/models` (проверено 19.10.2026)

При сравнении моделей через `/api/v1/models` (или туту-каталог):

- **`<vendor>/deepseek-...-latest` (без `~`) в каталоге НЕ существует** → HTTP 404. `-latest`-алиасы живут под `~соавтор/семья-latest` (тильда — часть id). Искать по `~`, не по `deepseek/`.
- **`~deepseek/deepseek-v4-flash-latest` ≠ `~deepseek/deepseek-flash-latest`** — это РАЗНЫЕ семейства, не «тот же поновее». `v4-flash-latest` (= семейство V4 Flash) и `flash-latest` (= семейство Flash, уже другое поколение) резолвятся в разные снапшоты. Читать `alias_target.slug` — туда реально роутится алиас. «Просто flash-latest» ≠ «v4-flash-latest».
- **Поле `pricing` в `/models` для сравнения цен НЕ рекомендовать** — у алиаса оно агрегируется по провайдерам и может показывать заметно другие (часто ниже) цифры вход/выход, чем у закреплённого снапшота, на который он указывает. Сравнение `pricing` алиаса с `pricing` его же цели даёт ложный вывод «алиас в N раз дешевле» — хотя это одна и та же модель с одной фактической ценой. Авторитетная цена (их реальный биллинг) — на карточке модели (см. страницу openrouter.ai), а не в `pricing` из `/models`.
- Для выбора основной модели агенту (если кандидаты — snapshot и его алиас) сравнивать цену по **этой модели и её `alias_target` как одному пункту**, а не как двум конкурентам.

## Выбор модели под роль (через каталог шлюза)

Когда роль поезда/инструмента переводится на OpenRouter через шлюз (например ревизор при уходе Cursor на Codex), кандидатов из `/tmp/or_models.json` отбирать по 4 связанным критериям — совместно, а не по одному:
1. **Интерактивный режим**: id с `:batch` (напр. `anthropic/claude-haiku-5.5:batch`) НЕ пригоден для invoke-role — это не интерактивный запрос, а пакетный. Брать базовый id без суффикса.
2. **Tool calling обязателен** — фильтровать по `supported_parameters` (может быть список, а не dict — парсить и то и то); без tool-call роль не сможет сделать ни один вызов.
3. **Reasoning корректен**: снять, если `supported_parameters`/`id` не содержат `reason`/`think` (напр. `amazon/nova-micro-v1`).
4. **Независимость вендора**: ревизор ≠ модель оркестратора и ≠ семья архитектора/исполнителя. `deepseek-v4-flash` (default Сирени) и `openai/gpt-*` (семья Codex-архитектора) — отсев, иначе второй взгляд не независим. Цель — третий/независимый вендор (напр. Anthropic/GLM), если постановка это держит.

Цена (`pricing`) — последний фильтр при равных критериях; «дешёвый и сильный» решается вендорной независимостью и reasoning раньше, чем $/токен.

## Использование в Honcho

Для self-hosted Honcho: использовать Tutu gateway как единый LLM-провайдер вместо OpenRouter. Все env var `*_OVERRIDES__BASE_URL` → `https://llm-gateway.tutu.ru/api/openrouter/v1`.

**Важно:** Honcho требует tool calling support. Gemini 2.5 Flash Lite подтверждён. DeepSeek V4 Pro требует проверки перед использованием.

## Паттерн проверки модели

См. `references/tutu-gateway-models.md` — скрипты для проверки tool calling и extended thinking.

## Вызов из внешнего инструмента (не Cursor)

Компрессорные/экстрактные задачи выполняются НА `deepseek-v4-flash-0731` прямо из Python-скрипта через публичный `call_llm(task="compression")` (`agent.auxiliary_client`), **без обёртки Cursor CLI**. Полный рабочий паттерн (ленивый импорт, критичный питфолл `reasoning_details`, env-fallback на Cursor `--mode ask`, откат): см. `references/call-llm-from-external-tool.md`.

## Нативная эскалация на более сильную модель (внутри Hermes)

Как передать аналитическую задачу на более сильную модель (`deepseek-v4-pro` и др.) в том же топике с сохранением полного контекста диалога, **без Cursor**: штатный `/model <model> --once` + как сделать видимый в Telegram-подсказках `/analyst` (и почему quick_commands alias НЕ появляются в меню команд). См. `references/native-model-escalation.md`.

## Разовый вызов модели из диалога (Q&A к модели, промпт-файл)

Когда владелец просит «отдай вопрос модели X» (стратегия/план/вердикт по
большому контексту) — прямой HTTP к шлюзу из Python, модель из allowlist
(напр. `qwen/qwen3.7-plus`), промпт — файл, ответ — в файл:

```python
import json, urllib.request, yaml
cfg = yaml.safe_load(open('/home/tkachenkoav/.hermes/config.yaml'))
key = cfg['custom_providers'][0]['api_key']
prompt = open('/tmp/prompt.md').read()
payload = {"model": "qwen/qwen3.7-plus",
           "messages": [{"role": "system", "content": "…роль…"},
                         {"role": "user", "content": prompt}],
           "max_tokens": 6000, "temperature": 0.3}
req = urllib.request.Request(
    "https://llm-gateway.tutu.ru/api/openrouter/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    method="POST")
with urllib.request.urlopen(req, timeout=420) as resp:
    data = json.loads(resp.read())
content = data["choices"][0]["message"]["content"]
open('/tmp/response.md', 'w').write(content)
```

Правила для такого вызова:
- Промпт-файл: полный контекст (инцидент/переписка/факты с машины) +
  ограничения владельца + требуемый формат; русский, без воды.
- Ответ всегда сохранять в файл и пересказывать владельцу выжимкой —
  полный текст в /tmp (по запросу — в WorkVault).
- Если модель попросила дополнительные данные — собрать их с машины
  (конфиги, коды, логи) и перезвать тем же паттерном; это штатный цикл
  «передай ей, что она попросит».
- `data` может отсутствовать; `choices[0].message.content` — основной канал
  (reasoning — отдельные поля, не путать). HTTP error → читать
  `e.read().decode()` для диагностики.

## Роутинг `/model <id>` на Tutu: модель ОБЯЗАНА быть в allowlist `custom_providers[].models`

`/model z-ai/glm-5.3-flash` (и любой алиас на модель шлюза) резолвится на Tutu **только если модели нет** в `custom_providers[].models` провайдера `tutu`. Если её там нет, `switch_model()`/`detect_provider_for_model()` НЕ находит её в каталоге `tutu`, «добирает» в каталоге OpenRouter и молча переключает сессию на `provider=openrouter` — где нет ключа → `RuntimeError: No LLM provider configured` → каждый запрос падает «Sorry, I encountered an unexpected error». Реальный инцидент 10.09.2026: `/anl` → `/model z-ai/glm-5.3-flash`; модель была на шлюзе (`z-ai/glm-5.3` в allowlist, но без `-flash`), а сессия роутилась в openrouter.

**Симптом в логах** (`~/.hermes/logs/`):
- `agent.log`: `switch_model: ... -> <model> (openrouter)`
- `errors.log`: `resolve_provider_client: openrouter requested but OPENROUTER_API_KEY not set` + `RuntimeError: No LLM provider configured`

**Диагностика:**
1. `agent --list-models` показывает НЕ все модели шлюза (только picker) — не полагаться на него.
2. Сверять сам allowlist: `grep -nA30 "custom_providers" ~/.hermes/config.yaml` — есть ли `<id>` в `models:` провайдера `tutu`.
3. Smoke-тест самой модели на шлюзе (см. curl выше) — если HTTP 200, модель валидна, проблема в allowlist.

**Фикс:** добавить `<id>` в `custom_providers[].models` провайдера `tutu` (бэкап config!). Верифицировать python-тестом:
```bash
cd ~/hermes-agent && .venv/bin/python - <<'PY'
import yaml
from hermes_cli.model_switch import switch_model
cfg=yaml.safe_load(open('/home/tkachenkoav/.hermes/config.yaml'))
r=switch_model("z-ai/glm-5.3-flash", current_provider="tutu",
               current_model="deepseek/deepseek-v4-flash-0731",
               custom_providers=cfg["custom_providers"])
print(r.success, r.target_provider)  # ДО фикса: True openrouter; ПОСЛЕ: True custom:tutu
PY
```
Клиенту с залипшей сессией: `/reset`, затем снова `/model`/алиас. Полная процедура диагностики+фикса: `references/custom-provider-model-not-in-allowlist.md`.
