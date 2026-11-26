---
name: hermes-cost-audit
description: "Audit Hermes API costs from state"
version: 1.1.1
author: Сирень (default)
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, cost, audit, finops, state-db, sql, analysis]
---

# Hermes Cost Audit

Analyze Hermes API spending by querying `state.db` (SQLite). Use when the user asks "сколько потратили", "где утекают токены", "топ дорогих сессий", "proанализируй затраты", or wants a FinOps review.

## How it works

All cost data lives in `~/.hermes/state.db`, table `sessions`. Key columns:

| Column | Meaning |
|---|---|
| `model` | Model used (e.g. `claude-sonnet-4-6`, `qwen/qwen3.6-plus`) |
| `input_tokens` | New (non-cached) input tokens per session |
| `output_tokens` | Output tokens per session |
| `cache_read_tokens` | Tokens read from Anthropic prompt cache (cheap: ~$0.30/MTok) |
| `cache_write_tokens` | Tokens written to cache (paid: same as new input) |
| `api_call_count` | Number of LLM API calls in the session |
| `tool_call_count` | Total tool invocations |
| `estimated_cost_usd` | Hermes-calculated cost |
| `message_count` | Total messages (user + assistant + tool) |
| `source` | Platform: `telegram`, `cron`, `subagent`, `cli`, `tui` |
| `title` | Session title |
| `started_at` | Unix timestamp |

**Note:** `cache_read_tokens` is ~10x cheaper than `input_tokens`. High cache_read with low input = good (cache hit reuse). High cache_write = expensive (writing large system prompts / long context to cache each turn).

## Standard audit queries

Run via `terminal(command='cd ~/.hermes/profiles/<profile> && python3 -c "..."')`. Replace `<profile>` as needed (for `default`: `~/.hermes/profiles/default`).

### 1. Cost by model (total spend)

```sql
SELECT model, COUNT(*) as sessions,
       SUM(input_tokens) as total_input,
       SUM(output_tokens) as total_output,
       SUM(cache_read_tokens) as total_cache_read,
       SUM(cache_write_tokens) as total_cache_write,
       SUM(estimated_cost_usd) as total_cost
FROM sessions
GROUP BY model
ORDER BY total_cost DESC;
```

### 2. Top 10 most expensive sessions

```sql
SELECT id, model, source, title, input_tokens, output_tokens,
       cache_read_tokens, cache_write_tokens, api_call_count,
       estimated_cost_usd, started_at
FROM sessions
ORDER BY estimated_cost_usd DESC
LIMIT 10;
```

### 3. Tool-call breakdown per expensive session

```sql
-- Requires reading tool_calls JSON from messages table
-- Run as Python to parse JSON (see references/state-db-sql-patterns.md)
```

### 4. Sessions with excessive API calls ("session monsters")

```sql
SELECT id, model, api_call_count, tool_call_count,
       estimated_cost_usd, started_at, title
FROM sessions
WHERE api_call_count > 200
ORDER BY api_call_count DESC;
```

### 5. Context size analysis (>100M tokens)

```sql
SELECT id, model,
       (input_tokens + cache_read_tokens + cache_write_tokens) as total_context,
       estimated_cost_usd, started_at, title
FROM sessions
WHERE (input_tokens + cache_read_tokens + cache_write_tokens) > 100000000
ORDER BY total_context DESC;
```

### 6. Cost by source/platform

```sql
SELECT source, COUNT(*) as sessions, SUM(estimated_cost_usd) as cost
FROM sessions
GROUP BY source
ORDER BY cost DESC;
```

## Session monster: detection + safe stop (P.0)

Session monster — `api_call_count` кратно больше `message_count` (~10 api на сообщение: агентный цикл не завершается) и `ended_at IS NULL`. Детекция в ErrorBus идёт постфактум (порог api>500/tool>1000), поэтому монстр успевает накопить сотни вызовов до алерта.

**Перечислять открытые сессии по `ended_at IS NULL`, НЕ по `last_activity_at`.** Колонка `last_activity_at` часто NULL даже у живых/крупных сессий, и фильтр `WHERE last_activity_at > now-Nd` молча выкидывает их — так можно недооценить радиус взрыва и пропустить самые дорогие сессии (из-за этого ревью вернуло правку). Корректный общий запрос: `SELECT id, api_call_count, estimated_cost_usd, chat_id, thread_id, started_at FROM sessions WHERE source='telegram' AND ended_at IS NULL AND api_call_count>100`. Возраст/«живость» суди по свежести последнего сообщения через `SELECT MAX(timestamp) FROM messages WHERE session_id=?...`, а не по `last_activity_at`. После загрузки списка классифицируй каждую строку (живой рабочий тред / инертная / orphan) и только потом решай, что закрывать.

**P.0 — безопасная остановка через state.db (не рубить gateway!):**
1. Снять факты до остановки (api_call_count, message_count, input/cache_read/estimated_cost, started_at, title, session_key).
2. Проверить, что нет активного turn: `gateway_state.json` → `active_agents:0` (иначе дать завершиться или прервать по session_key).
3. Финализировать строку сессии:
```sql
UPDATE sessions SET ended_at=<now>, end_reason='monster_limit_manual', expiry_finalized=1 WHERE id='<session_id>';
```
4. Проверить, что gateway-роутинг создал свежую сессию для того же routing key в `sessions/sessions.json` — он сам это делает, т.к. `gateway/session.py` `_apply_route_checks` видит ended-строку через `_is_session_ended_in_db` и на следующем входящем сообщении заводит новую. Разговор в чате не теряется. Это штатный механизм, отдельный safety-net-скрипт не нужен.

**Классификация «живая vs инертная» — смотри `gateway_routing`.** Таблица `gateway_routing` (колонки `session_key`, `entry_json` с `session_id`/`thread_id`/`expiry_finalized`) показывает, какая сессия СЕЙЧАС привязана к живому каналу/треду. Открытую дорогую сессию, которая всё ещё биндим к живому треду, закрывать P.0-механизмом обязательно (gateway авто-ротирует на свежую при следующем сообщении) — она прямо в scope CRITICAL. А вот общий тред группы (session_key без `:thread`) не форсить: закрытие без команды потеряет биндинг. Сессию с `chat_id`/`session_key` = NULL (orphan) закрывать смело — привязки нет, инертна.

## Waste detection patterns

| Pattern | Indicator | What it means |
|---|---|---|
| **Session monster** | api_call_count > 500 | Model looping — regeneration cycles, excessive tool calls |
| **Cache write bloat** | cache_write_tokens > 5M | Large system prompt or long context being re-cached every turn |
| **Terminal spam** | terminal tool > 50% of tool_calls | Model using terminal for trivial ops (ls, cd) instead of batching |
| **execute_code spam** | execute_code > 100 calls | Testing/validation on full dataset instead of sample |
| **Duplicate input storm** | Same user message repeated N times at same timestamp | Platform retry/gateway bug causing duplicate processing |
| **Cache miss on agent loop** | `cache_read/(input+cache_read) < 0.50` при `api_call_count ≥ 10` | Prompt prefix не кэшируется → каждый вызов платит полный вход. Сессия может стоить 13× соседней с hit 97%. Считать долю кэша по сессии, не только суммы |
| **Big uncached input per call** | `input_tokens/api_call_count > 80K` | Агент тащит system prompt + накопленные tool-results без кэш-hit на каждом ходу (TZ-фаза: 32 вызова × 118K = $1.70 vs 37 вызовов с hit 97% = $0.13) |

**DeepSeek-специфика учёта (важно для интерпретации):** у DeepSeek через tutu `cache_write_tokens=0` всегда (server-side автокэш, не Anthropic-style write); `input_tokens` в state.db = **uncached** (`prompt_total − cache_read`); hit живёт в `prompt_cache_hit_tokens`. `cache_control` маркеры НЕ включать на DeepSeek — риск 400. Промах точечный (по сессии), не глобальный: соседние сессии на том же ключе могут давать 9% и 97% hit в один день.

**Qwen/Alibaba-кэш (в Hermes, наличие хитов):** маркеры `cache_control: ephemeral` (envelope, OpenAI-wire) Hermes добавляет только если provider входит в alibaba-семейство `{opencode, opencode-go, opencode-zen, alibaba}` — иначе 0% хитов, полный промпт каждый ход (кейс qwen3.6-plus). Model Studio поддерживает и implicit-кэш (авто, `cached_tokens`) и explicit (`cache_control`, мин 1024 токена, до 4 маркеров). Qwen/alibaba-TTL срезается на 5м (`effective_cache_ttl`). Факт хитов смотреть `usage.prompt_tokens_details.cached_tokens` (DashScope Singapore: `usage.cached_tokens`); кастомному провайдеру кэш включается capability `prompt_caching`.

## Capacity check — does a flat plan's quota cover the load

When sizing a flat plan (e.g. Alibaba Coding Plan Pro: 6,000 requests/5h · 45,000/wk · 90,000/mo) against real work, measure CALL counts from logs, not feelings:

- **Hermes side** — table `session_model_usage` in `~/.hermes/state.db`: per-session-per-model rows with `api_call_count`, `input_tokens`, `output_tokens`, `first_seen`/`last_seen`. Aggregate `SUM(api_call_count)` over the window by model — it directly equals the request count a plan quota must absorb. Prefer it over `sessions` when the question is per-model call volume per period.
- **Dev-contour side (Codex CLI)** — `~/.codex/state_5.sqlite` → `threads` (`tokens_used`, `first_user_message`, `created_at`) for thread/token counts. Do NOT use `thread_history_1.sqlite`.`thread_turns` for call counts — it holds ~1 turn per thread. For agent-session call volume, count lines in rollout JSONL: `wc -l ~/.codex/sessions/YYYY/MM/rollout-*.jsonl` — each line is one event, 1 model call ≈ 1–2 events, so events/2 is an order-of-magnitude call estimate.

Rule of thumb:
- A requests-metered plan wins on context-heavy workloads (few calls, big payloads) and loses on many tiny calls — size by CALL COUNT, not tokens.
- Keep ≥2× monthly headroom; the dangerous edge is a short window (6,000/5h) on bursty agent days (single-day batches can reach 5–8k calls).
- A flat plan's model list is closed — the cheap flash family is usually NOT included, so orchestrator routing may still need a pay-per-token model on the gateway.

## Output format

When delivering audit results:
1. Summary table (model, input, output, cache, cost)
2. Top expensive sessions with root-cause classification
3. Waste pattern matrix
4. Actionable recommendations (config changes, operational rules)

## Related

- `hermes-cost-optimization` — configuration changes to reduce costs (delegation routing, compression, auxiliary models)
- `references/state-db-sql-patterns.md` — ready-to-run Python+SQL scripts for deep analysis
- `references/aug-2026-findings.md` — baseline audit results from August 2026
- `references/june-july-2026-findings.md` — June–July 2026 audit: per-model costs, anomalies, weekly breakdown. Key finding: Sonnet-4-6 is 5.4× more expensive per output token than Sonnet-5; Opus is 30% cheaper than Sonnet-4-6.
- `references/aug-2026-model-routing-and-pricing.md` — current model routing (DeepSeek-v4-pro, Qwen3.6-plus, Gemini-3-flash, free cron models), Cursor CLI routing (Sonnet-5, Composer 2.5), verified OpenRouter prices (August 2026), and cost projection (86% API savings).
- `references/locate-llm-callers.md` — как найти, кто именно ходит в LLM-гейтвей по конкретному ключу/модели (чеклист обхода кронов/auxiliary/USERTOOLS/скиллов/env + поиск по хвосту ключа, без раскрытия значения). Применять при «вижу расход на модель X по ключу …NNN — кто это».
- `references/cron-model-forensics.md` — как выяснить, на какой модели РЕАЛЬНО исполняется крон-джоб. jobs.json у агентного крона может показывать `model: null`, а факт исполнения живёт в `state.db` (`source='cron'` + title). Пользоваться при подозрении «крутится крон на нештатной модели», симптоме `Model generated invalid tool call: <name>` / `The <run> tool is not available`, задержке публикации из-за сбойного крон-агента. Включает историю по бэкапам `jobs.json.bak-*`.
- `references/codex-model-forensics.md` — аудит расхода **Codex CLI** (dev-роли architect/reviewer/executor, gpt-6.1-sol/gpt-6-astra/gpt-5.6-terra). Codex-спенд невидим в `state.db` — данные в `~/.codex/state_5.sqlite` (threads.tokens_used), цены в `~/.hermes/cache/openrouter_model_metadata.json` (НЕ models_cache.json). Включает анализ «поменять модели ролей местами» (breakeven по экономии на повторах).
- `references/cursor-model-forensics.md` — как отличить модель, **реально исполнявшуюся** в Cursor CLI, от моделей, которые лишь **упомянуты в каталоге** (Cursor вкладывает весь список доступных моделей в system-промпт каждой сессии → `grep -ri <model> ~/.cursor` даёт ложные срабатывания). Истина: `--model <name>` в agent.log + строка `powered by <Model>` в system-блобе store.db сессии; config.yaml-строка провайдера = доступность, не маршрут. Применять при «зачем использовалась модель kimi/gpt-5.6-terra/muse-spark в Cursor`.
- `references/model-transition-artifacts.md` — как отличать «живые» модели от исторических артефактов (переход уже случился, мёртвые профили, qwen-кэш vs server-side кэш DeepSeek/Gemini, достоверность estimated-cost).
- `scripts/llm_anomaly_scan.sh` — автономный еженедельный аудит LLM за последние 7 дней через Cursor-архитектора (read-only, без `--mode plan`): формирует промпт → зовёт `agent ... cursor-grok-4.6-high` → сохраняет полный JSON-отчёт в `~/WorkVault_backup/llm-anomaly-audits/LLM-anomalies_<дата>.json` → печатает компактное резюме на stdout. **ErrorBus:** SQL-детектор (`llm_anomaly_errorbus.py`) + auto-resolve open-строк через `error_bus_cli.py resolve` (PIIScan Variant 2); `session_reset` при `session_reset.mode` ∈ {idle,daily,both} не репортится. Подключён как п.11 в крон `vm_selfcheck`. Запуск: `bash ~/.hermes/scripts/llm_anomaly_scan.sh`.
- **Питфолл TTL (09.09):** `llm_anomaly_scan.sh` пишет только компакт `{subtype,is_error,result}` (без tool/conversation payload) и держит TTL 5 дней (`find $OUTDIR -name 'LLM-anomalies_*.json' -mtime +5 -delete`). TTL(5д) < цикла крона(7д) — нормально: скрипт не читает старые JSON для трендов, тренды идут через SQL к `state.db`, JSON — только последний отчёт для контекста. Не откатывать компакт/не удлинять TTL.

## Weekly automated audit (7-day anomaly scan)

Для регулярного (не разового) контроля расхода без ручного прогона SQL используй `scripts/llm_anomaly_scan.sh`. Он делегирует Cursor-архитектору полный анализ (breakdown по моделям, топ-5 дорогих сессий, session monster / cache-write / terminal-spam / пустые-дубли / session_reset / дорогие cron, признаки ошибок, рекомендации с оценкой экономии в $) за окно `started_at >= now-604800`.

**Ключевые уроки автономного вариантa:**
- **НЕ использовать `--mode plan`** в headless/одноразовом прогоне — архитектор остановится на плане и сохранит почти пустой отчёт. Вместо плана держи read-only на жёстком промпте (запрет записи, только SELECT / `mode=ro`). Тогда полный отчёт приходит за один вызов.
- Отчёт — JSON (не markdown), сам чек-скрипт достаёт и печатает `result` как резюме. Полный текст всегда в сохранённом файле бэкапа.
- Регулярно сверять рекомендации архитектора с реальным `jobs.json`/конфигом: исторические записи в `state.db` (мёртвые профили, старые модели вроде gpt-5.5-pro/deepseek-*-low) могут маскироваться под актуальные проблемы.

## Pitfalls

- **state.db ≠ весь биллинг — внешние инструменты невидимы:** state.db фиксирует только расход Hermes-агента (оценка по публичному прайсу в `estimated_cost_usd`). Отдельные инструменты (PFS/MFF/MOFS, MoveFrom*, см. `~/USERTOOLS/`) ходят на tutu-гейтвей **своим API-ключом** и не попадают ни в state.db, ни в agent.log. Источник истины по реальному счёту — админка `https://llm-gateway-admin.tutu.ru/usage`. Если юзер говорит «я вижу расход на модель X в биллинге», это приоритетнее «0 записей в state.db» — не оспаривай. Ищи потребителя и за пределами `~/.hermes/`: `grep -rn "model-slug" ~/USERTOOLS/`, дефолты `*.get("SOME_LLM_MODEL", ...)` в `config.py`/`.py`/`.sh`. Если известен сам **ключ по хвосту** (напр. …730) → полный обход по чеклисту `references/locate-llm-callers.md`. Подробности и прецедент (PFS DEDUP_LLM_MODEL=deepseek-v4-pro): `references/external-tools-billing.md`.
- **When the user states their active models/providers, accept it over state.db:** Config strings in state.db may not match the real upstream model. If the user says "we only used Claude", the DeepSeek/Grok entries in state.db are config artifacts, not real model usage.
- **Live vs historical models:** Before saying "where the money goes", cross-check the current active models from `config.yaml` (`model.default`, `fallback_providers`, non-auto `auxiliary.*`) and `cron/jobs.json` against a short 7-day `state.db` window. Expensive models (qwen3.6-plus, deepseek-v4-pro, gpt-5.5-pro, deepseek-*-low) may be historical artifacts of already completed transitions or removed profiles — don't build optimization plans on them. See `references/model-transition-artifacts.md`.
- **Don't patch qwen-cache if qwen isn't active:** DeepSeek/Gemini cache server-side automatically (high cache_read, cache_write=0); Qwen needs explicit `cache_control` or its cache stays at 0. If qwen is not in the current config, skip qwen-cache patches — historical problem.
- **Cron on expensive models:** Opus crons average $0.87/run — justified for analysis but wasteful for monitoring/status checks. Route monitoring crons to Haiku ($0.03/session avg).
- **Multi-profile state.db schema mismatch:** Profile-specific state.db files (`~/.hermes/profiles/<name>/state.db`) may have an older schema lacking `started_at` and `model` columns. Always audit from `~/.hermes/state.db` (the main ~900MB database) for historical analysis. Use the `profile_name` column to filter by profile.
