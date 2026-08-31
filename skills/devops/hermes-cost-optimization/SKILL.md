---
name: hermes-cost-optimization
description: "Reduce Hermes token costs: route delegation/auxiliary tasks to cheaper models, configure context compression, connect local/corporate LLM endpoints."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, cost, tokens, optimization, delegation, auxiliary, haiku, local-llm, exo]
---

# Hermes Cost Optimization

Strategies to reduce API token costs while keeping main conversation quality high.

## Роутинг по типу задачи (для пользователя tkachenkoav)

| Тип задачи | Модель |
|---|---|
| Терминальные / механические (ls, config set, статус) | claude-haiku-4-5 |
| Справочные вопросы по готовым инструментам/ТЗ/скиллам | claude-haiku-4-5 |
| Основной чат, координация, интерпретация запросов | claude-sonnet-4-6 |
| Разработка, **написание и правка ТЗ**, архитектура, дебаг | claude-opus-4-7 |

**Правило ТЗ:** ТЗ всегда пишет и правит Opus. После любой правки ТЗ — Opus проверяет все смежные ТЗ инструментов на непротиворечивость. Нарушение этого правила приводит к расхождениям между документами (как произошло в мае 2026: Haiku отредактировал ТЗ MoveFromExchange вместо Opus).

**Важно:** основной чат держать на Sonnet, не Haiku — Haiku теряет контекст длинных сессий и неточно формулирует задачи для субагентов. Sonnet дешевле Opus в ~5 раз при приемлемом качестве.

## Core Principle

Route expensive bulk/auxiliary work to cheap models; keep the main user-facing conversation on a capable model (e.g. Sonnet or a verified faster/stricter alternative).

---

## 1. Delegation (Subagents) → Cheap Model

When Hermes spawns subagents via `delegate_task`, they use the `delegation.*` config:

```bash
hermes config set delegation.model claude-haiku-4-5
hermes config set delegation.provider anthropic
```

Savings: Haiku is ~20x cheaper than Sonnet. Subagents handle ~30-50% of tokens in complex sessions.

---

## 2. Auxiliary Tasks → Cheap Model

Context compression, session search, and vision analysis each have their own model slot.

**⚠️ Compression model ≠ session_search model** — у каждой задачи свой слот, выбирай осознанно.

**Важно для compression:** модель сжатия должна иметь контекст **не меньше** порога сжатия основной модели. Иначе при каждом старте сессии будет предупреждение «Auto-lowered this session's threshold». Два варианта:
- Использовать **Sonnet** как compression model (контекст 1M, порог 500K работает)
- Использовать **Haiku** (200K) + снизить `compression.threshold: 0.17` (170K < 200K)

**Текущая конфигурация для tkachenkoav (май 2026):** compression → Sonnet (claude-sonnet-4-6), session_search → Haiku

## References

- `references/compression-internals.md` — исследование Opus (май 2026): где живёт логика в коде, как работает `update_model()`, почему per-model thresholds невозможны через конфиг.
- `references/delegate-per-call-model-patch.md` — план патча для per-call model в `delegate_task` (4 точки в `tools/delegate_tool.py`). Используй когда профили и `cronjob(model=...)` не покрывают кейс.
- `references/gateway-response-injection.md` — паттерн `runtime_footer`/`runtime_header` для гарантированной дописки текста к каждому gateway ответу (вне контроля модели); почему хуки и prefill не работают для этого.
- `references/context-window-analysis.md` — как измерить размер контекстного окна: структура state.db (sessions/messages), Anthropic API для лимитов моделей, count_tokens API для точной оценки, готовый скрипт анализа, расшифровка метрик (cache_read vs input_tokens).

### delegate_task model resolution (codebase reference)

`delegate_task` **не принимает per-task model/provider** (проверено: `tools/delegate_tool.py:2066` — `model=creds["model"]` всегда из delegation.model). Вся цепочка:
1. `delegate_tool.py:2459 _load_config()` — читает `delegation:` из `CLI_CONFIG`
2. `delegate_tool.py:2345 _resolve_delegation_credentials()` — if `delegation.base_url` → direct endpoint; else if `delegation.provider` → `resolve_runtime_provider`; else наследование от родителя.
3. `delegate_tool.py:875 _build_child_agent()` — подставляет `model=creds["model"]`
4. `delegate_tool.py:1021–1036` — `effective_model = model or parent_agent.model`. **api_mode НЕ наследуется когда provider отличается** (баг #20558): иначе MiniMax/DeepSeek роутятся не на ту API.
5. `delegate_tool.py:1050` — если задан `override_provider` без `override_acp_command`, ACP-транспорт принудительно сбрасывается.

**Cron — другая дверь:** `cronjob` принимает `model={"model":..., "provider":...}` напрямую (см. `cron/scheduler.py:1416–1556`). Результат доставляется отдельным сообщением, не в текущий контекст.

### Hermes Profiles для маршрутизации по моделям

Правильный способ «разные модели для разных задач» — профили, не per-task параметры:

```bash
# Профиль для быстрых задач на Qwen (корп. сервер)
hermes profile create qwen-fast --clone --description "Простые задачи на Qwen"
hermes -p qwen-fast config set model.default "mlx-community/Qwen3.6-35B-A3B-8bit"
hermes -p qwen-fast config set model.provider custom
hermes -p qwen-fast config set model.base_url "http://10.8.4.100:52415/v1"
hermes -p qwen-fast config set model.api_key "dummy"    # обязателен даже для local
hermes -p qwen-fast config set delegation.reasoning_effort ""   # exo не поддерживает
hermes -p qwen-fast config set agent.reasoning_effort ""

# Fallback профиль на Haiku
hermes profile create haiku-fallback --clone
hermes -p haiku-fallback config set model.default "claude-haiku-4-5"
hermes -p haiku-fallback config set model.provider anthropic
hermes -p haiku-fallback config set delegation.base_url ""
```

Использование из основной сессии:
```python
terminal(command='hermes -p qwen-fast chat -q "простая задача"', timeout=120)
```

### Indicator активной модели (Telegram)

Показ активной модели решён штатно через `display.runtime_footer` в config.yaml (см. Способ B ниже) — гейтвей дописывает модель + % контекста автоматически на каждый ответ. Не изобретать текстовые префиксы вида `🤖 Модель: ...` внутри ответа — это дублирует runtime_footer.

**Способ A (устарел, ненадёжный):** `agent.system_prompt` — модели Sonnet/Haiku регулярно пропускали инструкцию, к тому же создавало задвоение с runtime_footer.
**Способ B (актуальный, гарантированный):** `runtime_footer` (штатная функция, `display.runtime_footer.enabled: true`, `fields: [model, context_pct]`) — рисуется гейтвеем автоматически, модель в этом процессе не участвует. Детали в `references/gateway-response-injection.md`.

```bash
# Compression → Sonnet (дороже, но порог 500K корректен, Opus не теряет контекст)
hermes config set auxiliary.compression.model claude-sonnet-4-6
hermes config set auxiliary.compression.provider anthropic

# Session search → Haiku (дёшево, достаточно для поиска)
hermes config set auxiliary.session_search.model claude-haiku-4-5
hermes config set auxiliary.session_search.provider anthropic

# Vision → Haiku
hermes config set auxiliary.vision.model claude-haiku-4-5
hermes config set auxiliary.vision.provider anthropic
```

---

## 3. Context Compression Tuning

```bash
hermes config set compression.enabled true
hermes config set compression.threshold 0.50   # compress at 50% context fill
hermes config set compression.target_ratio 0.20 # compress down to 20%
```

**Как threshold взаимодействует с compression model:**

| Compression model | Контекст модели | Рекомендуемый threshold | Результат |
|---|---|---|---|
| claude-haiku-4-5 | 200K | `0.17` (170K < 200K) | Haiku справится, порог корректен |
| claude-sonnet-4-6 | 1M | `0.50` (500K ≪ 1M) | Оптимально, без предупреждений |
| claude-opus-4-7 | 1M | `0.50` | Оптимально, очень дорого |

**Почему нельзя задать разные пороги для разных моделей:** `compression.threshold` — глобальный параметр, per-model override отсутствует в config.yaml. Единственный встроенный override — функция `_compression_threshold_for_model()` в `agent/auxiliary_client.py` (захардкожена в исходнике). При смене модели (`update_model()`) Hermes переносит `threshold_percent` как есть на новую модель.

**Почему Sonnet лучше Haiku для compression при использовании Opus:** Opus пишет длинные ТЗ/исследования. При пороге 170K компрессия может сработать в середине задачи и Opus потеряет ранний контекст. Sonnet как compressor + threshold 500K даёт Opus запас на полную сессию разработки.

---

## 4. Connect a Local / Corporate LLM Endpoint

If a local or corporate OpenAI-compatible endpoint is available (e.g. **exo cluster**, LM Studio, Ollama):

### As delegation model (recommended — keeps main chat on cloud model):
```bash
hermes config set delegation.model <model-name>
hermes config set delegation.base_url http://<host>:<port>/v1
hermes config set delegation.api_key <signing-key-or-empty>
hermes config set delegation.provider custom
```

### As main model:
```bash
hermes config set model.base_url http://<host>:<port>/v1
hermes config set model.api_key <signing-key>
hermes config set model.default <model-name>
hermes config set model.provider custom
```

### exo cluster specifics
**exo** (distributed local inference) exposes three endpoints:
- OpenAI-compatible: `http://<host>:<port>/v1`
- Claude-compatible: `http://<host>:<port>`
- Ollama-compatible: `http://<host>:<port>/ollama`

The **signing key** shown in exo's `/#/integrations` page is the model name (e.g. `mlx-community/Qwen1.6-35B-A3B-8bit`). Use the OpenAI-compatible URL for Hermes.

---

## 5. VPN-Gated Corporate LLM — Fallback Pattern

When a corporate LLM is only reachable over VPN, there is no built-in per-delegation fallback. Options:

**Option A — Manual switch scripts (simplest):**
```bash
# VPN on — use corporate LLM
hermes config set delegation.model mlx-community/Qwen3.6-35B-A3B-8bit
hermes config set delegation.base_url http://10.8.4.100:52415/v1
hermes config set delegation.api_key mlx-community/Qwen1.6-35B-A3B-8bit
hermes config set delegation.provider custom

# VPN off — fall back to Haiku
hermes config set delegation.model claude-haiku-4-5
hermes config set delegation.provider anthropic
hermes config set delegation.base_url ''
hermes config set delegation.api_key ''
```

**Option B — Cron auto-switch (automatic):**
Create a cron job every 5 minutes that pings `http://10.8.4.100:52415` and switches delegation config based on reachability.

**Option C — `fallback_model` chain (for main model only):**
`fallback_model` in config.yaml applies to the main model, not delegation. Use it if running corporate LLM as the primary:
```yaml
fallback_model:
  - provider: custom
    model: mlx-community/Qwen3.6-35B-A3B-8bit
    base_url: http://10.8.4.100:52415/v1
    api_key: mlx-community/Qwen1.6-35B-A3B-8bit
  - provider: anthropic
    model: claude-haiku-4-5
```

---

## 6. Security Alongside Cost Config

Apply together with cost changes:
```bash
hermes config set security.redact_secrets true   # hide API keys from logs/context
```

---

## 7. Постоянные инструкции в системный промпт

Для добавления дополнительных инструкций к каждой сессии используй `agent.system_prompt`:

```bash
hermes config set agent.system_prompt 'Инструкция на русском языке'
```

- Загружается через `_load_ephemeral_system_prompt()` при каждом запуске агента
- Приоритет ниже env-переменной `HERMES_EPHEMERAL_SYSTEM_PROMPT` (если задана — перекрывает)
- Требует перезапуска сессии (`/reset` или `hermes gateway restart`) — читается при инициализации
- Альтернатива `agent.personalities` (словарь персон, нужно активировать явно через `/personality`) — `agent.system_prompt` проще и работает всегда

**Пример — не для индикации модели.** Раньше здесь была рекомендация класть в `agent.system_prompt` инструкцию вида «указывай модель в начале каждого ответа» — **это неверно и устарело**. Показ модели/контекста — штатная функция гейтвея через `display.runtime_footer` (`config.yaml`), рисуется автоматически, без участия модели. НЕ дублировать вручную текстом в ответе — будет задвоение. Используй `agent.system_prompt` только для правил, которые модель должна реально *учитывать при рассуждении* (делегирование, маршрутизация задач по сложности) — не для вывода метаданных, которые гейтвей и так добавляет сам.

---

## 8. Справочные вопросы по готовым инструментам → Haiku

Когда пользователь задаёт вопрос вида «как работает X», «что делает функция Y», «объясни алгоритм Z» про уже написанный инструмент/ТЗ/скилл — этот вопрос можно делегировать Haiku. Haiku читает код/документ и объясняет — качество достаточное, стоимость в 20x меньше.

**Кандидаты для Haiku:**
- «Как MoveFromFF синхронизирует новые встречи?»
- «Что делает функция fetch_range?»
- «Какие поля в реестре v2.0?»
- «Как работает блокировка через portalocker?»
- «Что настроено в config.yaml?»

**Оставлять на Sonnet/Opus:**
- Вопросы с архитектурными решениями («как лучше сделать X»)
- Вопросы по нескольким файлам сразу с выводами
- Отладка — найти где баг в коде

## 9. Роутинг по типу задачи (рекомендуемая схема для tkachenkoav)

| Тип задачи | Модель | Способ |
|---|---|---|
| Лёгкие терминальные (ls, date, du) | `claude-haiku-4-5` | `model={"model": "claude-haiku-4-5", "provider": "anthropic"}` |
| Исследовательские (research, анализ) | `claude-opus-4-7` | `model={"model": "claude-opus-4-7", "provider": "anthropic"}` |
| Разработка, код, debugging | `claude-opus-4-7` | явно в каждом `delegate_task` |
| Настройки Hermes, конфиг | `claude-opus-4-7` | явно в каждом `delegate_task` |
| Основной чат с пользователем | `claude-sonnet-4-6` | `model.default` в config |

**Важно:** всегда передавай модель явно через параметр `model` в `delegate_task` — конфиг `delegation.model` ненадёжен (см. Pitfalls).

---

## Quick Bulk Apply (Recommended Baseline)

```bash
# Delegation → Haiku
hermes config set delegation.model claude-haiku-4-5
hermes config set delegation.provider anthropic

# Compression → Sonnet (важно: Haiku 200K не покрывает threshold 500K)
hermes config set auxiliary.compression.model claude-sonnet-4-6
hermes config set auxiliary.compression.provider anthropic

# Session search + Vision → Haiku
hermes config set auxiliary.session_search.model claude-haiku-4-5
hermes config set auxiliary.session_search.provider anthropic
hermes config set auxiliary.vision.model claude-haiku-4-5
hermes config set auxiliary.vision.provider anthropic

# Security
hermes config set security.redact_secrets true
```

⚠️ После настройки — проверить `auxiliary.session_search.base_url` и `auxiliary.session_search.api_key`: если там остались значения от старой конфигурации (например кастомный эндпоинт), очистить:
```bash
hermes config set auxiliary.session_search.base_url ""
hermes config set auxiliary.session_search.api_key ""
```

No restart needed — takes effect on the next session or tool invocation.

---

## Cron Auto-Switch Script

A ready-made script lives in `scripts/switch_delegation_model.py`. It:
- Pings the corporate endpoint (3s timeout)
- Switches delegation config only when state changes (idempotent)
- Stays silent when no change → cron `no_agent=true` won't spam notifications

Deploy:
```bash
# Script is already at ~/.hermes/scripts/switch_delegation_model.py
# Create cron job:
hermes cron create "every 5m" --name "Auto-switch delegation model"
# Then edit the job to set: script=switch_delegation_model.py, no_agent=true, deliver=local
```
Or via Hermes tool:
```python
cronjob(action="create", name="Auto-switch delegation model (exo/haiku)",
        schedule="every 5m", no_agent=True,
        script="switch_delegation_model.py", deliver="local")
```

Edit the constants at the top of the script to change host/port/models.

---

## Очистка секретов из state.db

Если секрет (пароль, токен) засветился в сессии — он попадает в `state.db` и FTS-индекс. Процедура очистки:

```python
import sqlite3
db = '/home/tkachenkoav/.local/share/hermes/state.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

# Заменяем в messages
for col in ['content', 'tool_calls']:
    cur.execute(f"SELECT rowid, {col} FROM messages WHERE {col} LIKE ?", ('%SECRET%',))
    for rowid, val in cur.fetchall():
        cur.execute(f"UPDATE messages SET {col}=? WHERE rowid=?",
                    (val.replace('SECRET', '[REDACTED]'), rowid))

conn.commit()

# Перестраиваем FTS-индексы
cur.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
cur.execute("INSERT INTO messages_fts_trigram(messages_fts_trigram) VALUES('rebuild')")
conn.commit()
conn.close()
```

**Также чистить:** `logs/agent.log`, `logs/gateway.log` — через Python `str.replace()` (sed не работает на активных файлах Windows).

**Остаток после чистки:** grep-команды поиска секрета в tool_calls — безопасно, содержат паттерн поиска, не сам секрет.

---



## 10. Gateway-безопасное делегирование тяжёлых задач (tkachenkoav, май 2026)

**Проблема:** `delegate_task` с Opus (`reasoning_effort=high`, `child_timeout=1200`) держит родительский stream. При длинных задачах gateway падает с "Stream stale for 180s — Killing connection" и перезапускается. Сессия рвётся.

**Решение — cronjob вместо delegate_task для тяжёлых Opus-задач:**

```python
# Вместо delegate_task (блокирует gateway):
cronjob(action='create',
    name='my-task',
    prompt='...',
    model={'model': 'claude-opus-4-7', 'provider': 'anthropic'},
    schedule='1m',      # запуск через 1 минуту
    repeat=1,           # один раз
    deliver='origin',   # результат в текущий чат
    enabled_toolsets=['file', 'terminal']
)
```

**Правила:**
- Задачи >5 мин (разработка, исследования, ТЗ, настройка Hermes) → **cronjob**
- Короткие задачи (<2 мин) → **delegate_task** на Sonnet/Haiku

**Минусы cronjob:**
- Нет контекста разговора — всё нужно писать в prompt явно
- Нет обратной связи в процессе — итерации дороже
- Задержка 1+ мин до старта
- Нельзя видеть прогресс (только через `cronjob action='log'` пока running)

**Паттерн промпта для cronjob-задачи:** передавай максимум контекста явно: пути к файлам, что уже сделано, что именно нужно сделать, что нельзя трогать. Иначе Opus начнёт с нуля. There is no native per-delegation fallback — use manual switch scripts or a cron job.
- Changes to `delegation.*` take effect immediately for new `delegate_task` calls — no `/reset` needed.
- Changes to `auxiliary.*` also take effect immediately.
- exo signing key = the model name string shown on the integrations page, NOT a token/secret.
- When `delegation.base_url` is set, also set `delegation.provider custom` — otherwise Hermes may route to the wrong backend.
- **`delegate_task` игнорирует `delegation.model` из config.yaml.** Подтверждено дважды в реальных сессиях: subagent запускается на `claude-opus-4-7` даже при `delegation.model: claude-haiku-4-5`. Наследование от родительской сессии тоже не работает (parent=sonnet → child=opus). **Единственный надёжный workaround:** явно передавать `model={"model": "claude-haiku-4-5", "provider": "anthropic"}` в параметре каждого вызова `delegate_task`. Без явного параметра — модель непредсказуема.
- `fallback_model` в config.yaml применяется только к **основной модели**, NOT к delegation.
- `fallback_model` в config.yaml применяется только к **основной модели**, не к delegation.
- **`hermes config show` не отображает секцию `delegation`** — это UX-баг CLI. Параметры в config.yaml есть и работают, просто не показываются в выводе команды.
- **exo chat completions may return empty body** if the target model is not loaded in memory yet. First request to a cold model times out silently. Fix: send a warm-up request via the exo web UI (`http://<host>:<port>`) before using the endpoint programmatically.

## 11. Стек моделей Hermes (tutu-роутинг, DeepSeek/Gemini/Qwen)

Альтернативная схема роутинга — через tutu-гейтвей с DeepSeek/Gemini/Qwen (не через anthropic-модели). Актуально для профилей/задач с основным провайдером tutu.

### Текущая конфигурация (06.08.2026)

| Роль | Модель | Провайдер | Цена |
|---|---|---|---|
| Основной чат | `deepseek/deepseek-v4-pro` | tutu | $0.435/M in, $0.0036/M cache_hit, $0.87/M out |
| Compression | `google/gemini-3-flash-preview` | tutu | $0.50/M in, $0.05/M cache_hit, $3.00/M out |
| Session search | `google/gemini-3-flash-preview` | tutu | То же что compression |
| Исследования/оркестрация | `qwen/qwen3.6-plus` | tutu | $0.325/M in, $1.95/M out |
| Delegation | `deepseek/deepseek-v4-pro` | tutu | Как основной |

### Cursor CLI

| Роль | Модель |
|---|---|
| Архитектор (ТЗ, планы) | `cursor-grok-4.6-high` |
| Исполнитель (код, тесты) | `composer-2.5` |
| Координатор | `composer-2.5` |

### Кроны (free tier) — PITFALL

- `nvidia/nemotron-3-super-120b-a12b:free` — selfcheck, upstream, backlog
- `openai/gpt-oss-20b:free` — batch processing

**Pitfall (07.08.2026):** Free-tier модели на Tutu-гейтвее (`nemotron-3-super-120b:free`) нестабильны для критичных кронов. Причина: очереди на inference, низкий приоритет обработки, большие задержки. Результат — таймаут крона после 600s ожидания API-ответа (`TimeoutError: idle for 602s — waiting for non-streaming API response`).

**Правило:** Для критичных кронов (backlog-collector, pfs_batch и т.д.) использовать платные модели (Haiku-4-5, gpt-oss-20b:free допустим только для no_agent/скриптовых кронов). Экономия на free-tier не стоит потери надёжности.

### Исторические цены (Anthropic direct, июнь-июль 2026)

| Модель | $/1K in | $/1K cache_hit | $/1K out | Effective $/1K out |
|---|---|---|---|---|
| Sonnet-4-6 | $0.003 | $0.0003 | $0.015 | $0.1006 |
| Opus-4-7 | $0.005 | $0.0005 | $0.025 | $0.0699 |
| Sonnet-5 (intro ≤31.08) | $0.001 | $0.0001 | $0.005 | $0.0185 |
| Haiku-4-5 | $0.001 | $0.0001 | $0.005 | $0.0414 |

### Экономия

- API Hermes: $307/мес → $44/мес (**86%**)
- + Cursor Pro ($200/мес): $307 → $244/мес (**20%**)
