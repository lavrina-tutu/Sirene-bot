# Model Routing & Pricing — August 2026 Update

**Date:** 2026-08-06
**Source:** Cost audit conversation + OpenRouter price verification

## Current routing (after 30.07.2026)

### Main agent (Telegram, Hermes, profile tz-dev)

| Role | Model | Price (OpenRouter, per MTok) |
|---|---|---|
| Main chat | deepseek/deepseek-v4-pro (via llm-gateway ТУТУ) | $0.435 in / $0.0036 cache_hit / $0.87 out |
| Research / orchestration | qwen/qwen3.6-plus | $0.325 in / $1.95 out |
| Auxiliary compression | google/gemini-3-flash-preview | $0.50 in / $0.05 cache_hit / $3.00 out |
| Session search | google/gemini-3-flash-preview | — |

### Cron jobs

| Task | Model |
|---|---|
| Planning / analysis | nvidia/nemotron-nano-9b-v2:free |
| Monitoring / status | openai/gpt-oss-20b:free |

### Development skills (Cursor CLI)

| Stage | Model |
|---|---|
| TZ writing + execution plan | claude-sonnet-5 |
| Code implementation | composer-2.5 |
| Testing | composer-2.5 |

## Current prices (verified August 2026, OpenRouter)

| Model | Input / MTok | Cache hit / MTok | Output / MTok |
|---|---|---|---|
| DeepSeek V4 Pro | $0.435 | $0.0036 | $0.87 |
| Qwen3.6 Plus | $0.325 | — | $1.95 |
| Gemini 3 Flash Preview | $0.50 | $0.05 | $3.00 |
| Sonnet 5 (until 31.08, Anthropic direct) | $1.00 | $0.10 | $5.00 |
| Sonnet 5 (until 31.08, OpenRouter) | $2.00 | $0.20 | $10.00 |
| Sonnet 5 (from 01.09, Anthropic direct) | $1.50 | $0.15 | $7.50 |
| Haiku 4.5 | $1.00 | $0.10 | $5.00 |

### Key observation: Sonnet 5 pricing asymmetry

Sonnet 5 through OpenRouter is **2× more expensive** than through Anthropic directly ($2/$10 vs $1/$5 intro pricing). After 31.08.2026, Anthropic direct rises to $1.50/$7.50. If Cursor CLI or other tools connect through OpenRouter, the price premium applies.

## Historical routing (before 30.07.2026) — for context only

| Role | Model |
|---|---|
| Terminal / mechanical | claude-haiku-4-5 |
| Reference questions | claude-haiku-4-5 |
| Main chat | claude-sonnet-4-6 |
| Development, TZ, architecture | claude-opus-4-7 |

## Cost projection: before vs after optimization

| Metric | Before (Jun-Jul avg) | After (same workload) |
|---|---|---|
| Telegram costs | $213/mo | $28/mo (DeepSeek-v4-pro) |
| Cron costs | $89/mo | $16/mo (Qwen + free models) |
| **Total API** | **$307/mo** | **$44/mo** |
| Total + Cursor Pro | $307/mo | $244/mo |
| Avg cost/session | $0.18 | $0.03 (API) / $0.07 (API+Cursor) |
| Monster sessions (>500 API) | 4 | 0 |

**Savings: 86% on API** ($307 → $44/mo), **20% on total** ($307 → $244/mo with Cursor Pro $200/mo).

## Additional measures

- Context compression threshold: reduced from 0.50 to 0.30 (triggers earlier)
- Auto-compression: when api_call_count > 100 in a session
- Max turns: 60 per session
