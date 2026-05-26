---
name: custom-llm-endpoint-delegation
description: "Подключение кастомного LLM эндпоинта (exo, LM Studio, Ollama) для delegation субагентов с автопереключением на fallback модель."
version: 1.0.0
author: agent
tags: [hermes, delegation, custom-llm, exo, fallback, vpn]
platforms: [linux, macos, windows]
---

# Custom LLM Endpoint для Delegation

Настройка кастомного OpenAI-совместимого эндпоинта (exo кластер, LM Studio, Ollama) как модели для субагентов (`delegate_task`), с автоматическим fallback на облачную модель при недоступности.

## Подключение эндпоинта

### Шаг 1: Проверить доступность и список моделей
```bash
curl http://<host>:<port>/v1/models
```

### Шаг 2: Тестовый запрос
```python
import urllib.request, json

url = "http://<host>:<port>/v1/chat/completions"
data = json.dumps({
    "model": "<model-id>",
    "messages": [{"role": "user", "content": "Привет!"}],
    "max_tokens": 100,
    "stream": False
}).encode("utf-8")

req = urllib.request.Request(url, data=data, headers={
    "Content-Type": "application/json",
    "Authorization": "Bearer <signing-key>"
})
with urllib.request.urlopen(req, timeout=30) as resp:
    print(json.loads(resp.read())["choices"][0]["message"]["content"])
```

⚠️ Если ответ пустой (`b''`) — модель ещё не загружена в память. Отправь запрос через UI кластера чтобы "разбудить" модель.

### Шаг 3: Настроить delegation
```bash
hermes config set delegation.model "<model-id>"
hermes config set delegation.base_url "http://<host>:<port>/v1"
hermes config set delegation.api_key "<signing-key>"
hermes config set delegation.provider "custom"
```

### Шаг 4: Перезапустить gateway
```bash
hermes gateway restart
```
**Обязательно** — конфиг delegation читается при старте процесса, не на лету.

## exo Кластер (специфика)

- UI страница интеграций: `http://<host>:<port>/#/integrations`
- **SIGNING KEY** на странице интеграций — это `api_key` для запросов
- Поддерживает OpenAI-совместимый эндпоинт: `http://<host>:<port>/v1`
- Активная модель должна быть загружена через UI прежде чем принимать запросы через API

## ⚠️ Per-task модель в delegate_task — не поддерживается

Исследование исходного кода (`tools/delegate_tool.py`, строка 2066) показало:

```python
model=creds["model"]  # всегда из delegation.model в config
```

`delegate_task` **не принимает per-task model/provider** — модель задаётся глобально через `delegation.model`. Параметра `model` в схеме `tasks[]` нет. Любой вызов `delegate_task` идёт на одну и ту же модель.

**Следствие**: маршрутизация «Opus для сложных, Qwen для простых» через `delegate_task` невозможна без изменения кода. Правильный подход — логика на уровне основной модели:
- Простые задачи → основная модель выполняет **сама**, без делегирования
- Сложные → `delegate_task` на Opus (`delegation.model = claude-opus-4-7`)

### Если всё-таки нужен per-call patch

См. `references/delegate-per-call-model-patch.md` — точный план патча на 4 точки в `tools/delegate_tool.py` (схема + handler + пересборка `creds`). Это редко нужно, но если кто-то снова придёт с этим вопросом — не повторяй исследование, открой файл.

## Полная цепочка resolve модели для субагента (где что читать в коде)

Чтобы не перерывать `delegate_tool.py` снова при следующем вопросе «откуда берётся модель»:

1. **`tools/delegate_tool.py:2459 _load_config()`** — читает секцию `delegation:` из `CLI_CONFIG` (cli.py) или `load_config()` (hermes_cli/config.py). Работает одинаково из CLI, gateway, cron.
2. **`tools/delegate_tool.py:2345 _resolve_delegation_credentials(cfg, parent_agent)`** — возвращает dict с `model/provider/base_url/api_key/api_mode`:
   - если задан `delegation.base_url` → direct endpoint (custom/openai-codex/anthropic — детектится по hostname);
   - иначе если задан `delegation.provider` → `resolve_runtime_provider(requested=provider, target_model=model)` собирает полный набор;
   - иначе все поля `None` → дитя наследует от родителя.
3. **`tools/delegate_tool.py:875 _build_child_agent(..., model=creds["model"], override_provider=creds["provider"], ...)`** — подставляет в `AIAgent(...)`.
4. **`tools/delegate_tool.py:1021–1036`** — финальный merge: `effective_model = model or parent_agent.model`. **api_mode НЕ наследуется когда provider отличается** (баг #20558 / PR #20563): иначе MiniMax/DeepSeek роутятся не на ту API.
5. **`tools/delegate_tool.py:1050`** — если задан `override_provider` без `override_acp_command`, ACP-транспорт принудительно сбрасывается. Иначе `CopilotACPClient` обходит override credentials.

### Cron — другая дверь

В отличие от delegate_task, **`cronjob` принимает `model={"model":..., "provider":...}` как параметр инструмента** (см. `cron/scheduler.py:1416–1556`, где `model` идёт напрямую в `AIAgent(model=..., provider=...)`). Если нужен «одноразовый запуск тяжёлой модели не блокируя текущий ход» — это рабочий обходной путь вместо delegate_task. Минус: результат не возвращается в текущий контекст, доставляется отдельным сообщением.

## Профили Hermes — правильный способ маршрутизации по моделям

`delegate_task` не поддерживает per-task модель. Правильное решение — **профили Hermes**, каждый со своим `model.*` и `delegation.*`.

### Создание профилей под разные модели

```bash
# Профиль для быстрых задач на Qwen (корп. сервер)
hermes profile create qwen-fast --clone --description "Простые/быстрые задачи на Qwen3.6-35B"
hermes -p qwen-fast config set model.default "mlx-community/Qwen3.6-35B-A3B-8bit"
hermes -p qwen-fast config set model.provider custom
hermes -p qwen-fast config set model.base_url "http://<host>:<port>/v1"
hermes -p qwen-fast config set model.api_key "dummy"
hermes -p qwen-fast config set delegation.model "mlx-community/Qwen3.6-35B-A3B-8bit"
hermes -p qwen-fast config set delegation.provider custom
hermes -p qwen-fast config set delegation.base_url "http://<host>:<port>/v1"
hermes -p qwen-fast config set delegation.api_key "dummy"
# ⚠️ Обязательно очистить reasoning_effort — exo/MLX не поддерживает:
hermes -p qwen-fast config set delegation.reasoning_effort ""
hermes -p qwen-fast config set agent.reasoning_effort ""

# Профиль fallback на Haiku
hermes profile create haiku-fallback --clone --description "Средние задачи и fallback при недоступности Qwen"
hermes -p haiku-fallback config set model.default "claude-haiku-4-5"
hermes -p haiku-fallback config set model.provider anthropic
hermes -p haiku-fallback config set delegation.model "claude-haiku-4-5"
hermes -p haiku-fallback config set delegation.provider anthropic
hermes -p haiku-fallback config set delegation.base_url ""
```

### Использование профилей из основной сессии

Основная модель (Sonnet) сама решает что использовать:

```
# Простая задача → запуск через профиль qwen-fast
terminal(command='hermes -p qwen-fast chat -q "распарси JSON и верни список email"', timeout=120)

# Средняя задача или Qwen недоступен
terminal(command='hermes -p haiku-fallback chat -q "..."', timeout=120)

# Сложная задача (исследование/разработка)
delegate_task(goal="...", ...)  # идёт на delegation.model = Opus
```

### Auxiliary модели на Qwen (экономия токенов)

```bash
hermes config set auxiliary.session_search.provider custom
hermes config set auxiliary.session_search.model "mlx-community/Qwen3.6-35B-A3B-8bit"
hermes config set auxiliary.session_search.base_url "http://<host>:<port>/v1"
hermes config set auxiliary.session_search.api_key "dummy"
# compression — лучше оставить на Haiku (надёжность важнее экономии):
hermes config set auxiliary.compression.provider anthropic
hermes config set auxiliary.compression.model "claude-haiku-4-5"
hermes config set auxiliary.compression.base_url ""
```

⚠️ **Важно**: при настройке `auxiliary.session_search` на custom провайдер — обязательно указать `base_url` И `api_key`, иначе запрос уйдёт на дефолтный OpenAI endpoint и упадёт с ошибкой аутентификации.

### Cron-задачи с явной моделью

Cron поддерживает per-job override модели (в отличие от delegate_task):

```python
cronjob(action="create", schedule="every 1h", prompt="...",
        model={"model": "mlx-community/Qwen3.6-35B-A3B-8bit", "provider": "custom"})
```

## Правила выбора модели по типу задачи

Вместо cron-автопереключения — задать разные модели для разных классов задач через правила delegation. Agент сам выбирает нужную модель по триггерам в запросе.

### Схема приоритетов (пример для tkachenkoav)

| Класс задачи | Модель | Провайдер |
|---|---|---|
| Исследования, разработка, Python, API, скрипты | claude-opus-4-7 | anthropic |
| Основные задачи | claude-sonnet-4-6 | anthropic |
| Простые/быстрые задачи | Qwen3.6-35B-A3B-8bit | custom (exo) |
| Qwen недоступен (fallback) | claude-haiku-4-5 | anthropic |

### Настройка fallback при недоступности кастомного эндпоинта

```bash
hermes config set fallback_providers '[{"model": "claude-haiku-4-5", "provider": "anthropic"}]'
```

Fallback срабатывает автоматически при connection error — cron-скрипт мониторинга **не нужен**.

### Настройка delegation.model для исследований/разработки

```bash
hermes config set delegation.model claude-opus-4-7
hermes config set delegation.provider anthropic
hermes config set delegation.base_url ''
hermes config set delegation.api_key ''
```

Для простых задач через exo переключать вручную или выполнять без делегирования.

## Индикатор активной модели в Telegram

При работе через Telegram — в начале каждого ответа выводить строку:

```
🤖 Модель: claude-opus-4-7 (исследование/разработка)
🤖 Модель: claude-sonnet-4-6 (основная)
🤖 Модель: Qwen3.6-35B (простая задача)
🤖 Модель: claude-haiku-4-5 (простая задача, Qwen недоступен)
```

Это помогает пользователю контролировать какая модель фактически обрабатывает запрос.

### Два способа реализации

**Способ A (ненадёжный) — через `agent.system_prompt`.** Инструкция «в начале каждого ответа выводи строку...». Модели Sonnet/Haiku регулярно её пропускают. Используется по умолчанию, но не гарантирует 100%.

**Способ B (гарантированный) — через runtime_header в gateway.** Зеркальный механизм к существующему `runtime_footer` (см. `gateway/runtime_footer.py` + `gateway/run.py:8542–8557`). Текст добавляется к `response` **после возврата от агента, до отправки адаптеру** — это вне контроля модели, не пропускается.

Точный план патча и почему хуки/prefill не подходят — см. `references/gateway-response-injection.md`.

## Проверка что субагент использует нужную модель

После настройки убедиться через `delegate_task`:
```python
delegate_task(goal="Ответь одной строкой: 'Opus работает, модель: [твоё название модели]'")
# В метаданных результата проверить поле model
```

Если субагент всё равно использует старую модель — **перезапустить gateway**.

## Диагностика: субагент вызывает tool но возвращает пустой/галлюцинированный результат

**Симптом 1 — Модель не вызывает инструменты:** субагент вместо реальных tool calls пишет JSON в текст (`{"name": "web_search", ...}`). Это означает что toolset не активирован в сессии субагента. Попробовать снова — при следующем вызове инициализация может пройти успешно.

**Симптом 2 — web_search галлюцинирует:** tool_trace показывает вызовы, но URL вымышленные без реальных данных. Причина: поисковый API-ключ не настроен. Проверить и добавить:
```bash
grep -i "TAVILY\|EXA\|SERPER\|FIRECRAWL" ~/.hermes/.env
echo "TAVILY_API_KEY=tvly-..." >> ~/.hermes/.env
# Перезапустить gateway
```

**Симптом 3 — Connection error в delegation:** временный сбой, повторить вызов — обычно решается.

## Pitfalls

- `delegation.*` конфиг не применяется без перезапуска gateway/CLI
- exo возвращает пустой ответ (`b''`) если модель не загружена — это не ошибка сети
- `curl` с JSON телом может давать `"There was an error parsing the body"` из-за кодировки на Windows — используй Python urllib вместо curl для тестов
- `provider: custom` обязателен при использовании `base_url`
- **`reasoning_effort` на exo/MLX**: параметр не поддерживается — при клонировании профиля он наследуется из default и вызывает 400. Обязательно очищать в профилях с custom provider: `hermes -p <profile> config set delegation.reasoning_effort ""`
- **`api_key` в блоке `model:`**: для custom provider openai SDK требует непустой ключ даже для локального сервера — ставить `dummy`
- **`child_timeout_seconds`**: наследуется при клонировании. Для Qwen 1200с — норм, для haiku можно оставить как есть

## References

- `references/auto-switch-delegation.md` — полный скрипт автопереключения
- `references/delegate-per-call-model-patch.md` — план патча для per-call model в `delegate_task` (4 точки в `tools/delegate_tool.py`); используй когда профили и `cronjob(model=...)` не покрывают кейс
- `references/gateway-response-injection.md` — паттерн `runtime_footer`/`runtime_header` для гарантированной дописки текста к каждому gateway ответу (вне контроля модели); почему хуки и prefill не работают для этого
