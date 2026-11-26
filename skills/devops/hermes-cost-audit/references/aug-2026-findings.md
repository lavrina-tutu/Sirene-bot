# August 2026 Baseline Audit — tz-dev Profile

Date: 2026-08-06
Profile: tz-dev
Period: 22 May — 6 August 2026 (77 days)

## Summary

| Model | Sessions | Input | Output | Cost ($) |
|---|---|---|---|---|
| claude-sonnet-4-6 | 143 | 1.54B | 4.58M | $559.77 |
| claude-opus-4-7 | 315 | 169.3M | 3.20M | $252.49 |
| deepseek-v4-pro | 6 | 123.2M | 361K | $35.39 |
| claude-sonnet-5 | 1848 | 478.1M | 1.88M | $34.67 |
| x-ai/grok-4.20 | 6 | 48.4M | 174K | $25.53 |
| claude-haiku-4-5 | 680 | 67.3M | 789K | $23.49 |
| qwen/qwen3.6-plus | 4 | 30.2M | 101K | $9.92 |
| **Total** | **3009** | **2.48B** | **11.2M** | **~$950.40** |

By source: Telegram $671.49 (70.6%), Cron $263.95 (27.8%), Subagent $10.94, CLI $2.54, TUI $1.51.

## Top 3 sessions (73% of total cost)

1. **$220.98** — "Знакомство с AI ассистентом" — Sonnet-4-6, 1636 calls, 2558 tools, 336.7M context
   - Root cause: duplicate "Кто ты?" × 8+ at same timestamp → gateway retry loop
   - Tools: terminal 57%, cronjob 11%, patch 8%

2. **$44.78** — "Проверка работы чат-бота" — Sonnet-4-6, 559 calls, 62.9M context
   - Root cause: excessive memory calls (22), long session accumulation

3. **$39.59** — Unnamed — Sonnet-4-6, 1117 calls, 332.2M context, 686K output
   - Root cause: regeneration loops with full context

## Key findings

- **81% of cost** from Sonnet-4-6 + Opus-4-7 (historical, before qwen3.6-plus adoption)
- **Input/output ratio: 221:1** — cache read dominates (normal for long sessions)
- **Cache write = 271.2M tokens** — expensive re-caching of system prompts + history
- **Session monsters:** 4 sessions with >500 API calls, all on Sonnet-4-6
- **Current config (qwen3.6-plus)** already achieving ~80% savings vs historical Sonnet

## Current config (good)

```yaml
model:
  default: qwen/qwen3.6-plus
  provider: tutu
auxiliary:
  compression: { model: deepseek/deepseek-v4-pro }
  session_search: { model: google/gemini-3-flash-preview }
delegation:
  model: deepseek/deepseek-v4-pro
```

## Post-audit correction (Aug 2026 follow-up)

The DeepSeek-v4-pro ($25.45 on 5 Jul) and Grok ($22.21 on 21–22 Jul) entries in June–July were **NOT actual usage of those models** — they were config string artifacts from a brief period when `model.default` was set to those strings. The user confirmed only Claude models were used through July: Sonnet-5 as default, Opus for deep analysis, Haiku for cron monitoring and auxiliary. DeepSeek and Grok were only used starting 3 August.

### Key diagnostic signals

- `billing_base_url` in state.db showed `api.anthropic.com` for sessions where `model = grok` — confirming requests actually went to Anthropic
- A cluster of NULL-model sessions with 0 API calls immediately followed the DeepSeek session — gateway couldn't parse the custom provider's response format
- **Lesson:** state.db `model` field stores the config string, not the actual responding model when custom providers are used

### Corrected current config (Aug 2026)

After full pipeline refactoring:
- Main agent: deepseek-v4-pro (via TUTU gateway) instead of Sonnet-4-6
- Auxiliary compression: google/gemini-3-flash-preview instead of Haiku
- Research/orchestration: qwen/qwen3.6-plus
- Crons: nvidia/nemotron-nano-9b-v2:free + gpt-oss-20b:free ($0)
- TZ/dev skills via Cursor CLI: Sonnet-5 (planning), Composer-2.5 (implementation + testing)
- Context compression threshold: 0.30 (down from 0.50)
- Auto-compression at >100 API calls/turn
- Max turns: 60

Result: estimated **86% API cost reduction** ($307 → $44/mo) at same task density.
