# June–July 2026 Cost Audit — tz-dev Profile

Date: 2026-08-06
Profile: tz-dev
Period: 1 June — 31 July 2026 (61 days)

## Summary

| Period | Sessions | API Calls | Tools | Cost |
|---|---|---|---|---|
| June | 135 | 2,305 | 2,115 | $83.73 |
| July | 3,213 | 14,847 | 8,270 | $530.01 |
| **Total** | **3,348** | **17,152** | **10,385** | **$613.74** |

## Cost by Model

| Model | Sessions | Cost | % Budget | $/session | $/1K output tokens |
|---|---|---|---|---|---|
| claude-sonnet-4-6 | 110 | $378.19 | 61.6% | $3.44 | $0.1006 |
| claude-opus-4-7 | 184 | $130.36 | 21.2% | $0.71 | $0.0699 |
| claude-sonnet-5 | 1,848 | $34.67 | 5.6% | $0.02 | $0.0185 |
| deepseek/deepseek-v4-pro | 1 | $25.38 | 4.1% | $25.38 | $0.2602 |
| x-ai/grok-4.20 | 2 | $22.21 | 3.6% | $11.10 | $0.1593 |
| claude-haiku-4-5 | 617 | $16.92 | 2.8% | $0.03 | $0.0414 |

## Key Finding: Sonnet-4-6 Inefficiency

Sonnet-4-6 costs **$0.1006 per 1K output tokens** — **5.4× more than Sonnet-5** ($0.0185). Opus at $0.0699 is **30% cheaper** than Sonnet-4-6 per output token. This is counterintuitive: the "mid-tier" model is the worst value.

## DeepSeek/Grok Re-attribution (Aug 2026 follow-up)

The DeepSeek-v4-pro ($25.38) and Grok ($22.21) entries above were **config string artifacts**, not real model usage. The user confirmed only Claude models were used through July (Sonnet-5 default, Opus for analysis, Haiku for cron). State.db recorded `model.default` from config, not the actual responding model. Evidence:
- `billing_base_url` for "Grok" sessions = `api.anthropic.com` (real upstream was Anthropic)
- These were custom proxy sessions through `llm-gateway.tutu.ru`
- DeepSeek and Grok were only genuinely used starting 3 August

Corrected June–July total: ~$590 all-Claude.

## Top 5 Anomalies

1. **$220.98 (36% of budget)** — Gateway retry loop: 169× "1", 41× "да", 31× "2" in same session. 1,636 API calls, 337M context, I/O ratio 636:1.

2. **$39.59** — Context accumulation monster: 1,117 API calls, 332M context (97% cache read), I/O ratio 478:1.

3. **$130.36** — Cron on Opus: 150 cron runs, avg $0.87 each. Some justified (complex analysis), but 26 unnamed (title=null) sessions suspicious.

4. **$25.38 + $22.21** — DeepSeek + Grok experiments: cost per 1K out = $0.26 and $0.16 respectively — both more expensive than Opus ($0.07). Total $47.59 for minimal useful output.

5. **4 sessions >500 API calls** — All on Sonnet-4-6, all Telegram-sourced. No sessions >500 on Sonnet-5, Opus, or Haiku.

## Weekly Breakdown

| Week | Sessions | Cost | Note |
|---|---|---|---|
| W22 | 57 | $43.36 | Early June, Sonnet-4-6 |
| W25 | 54 | $40.38 | Quiet period |
| W26 | 315 | $73.15 | Transition to Sonnet-5 |
| W27 | 1,793 | $19.16 | Mass cheap Sonnet-5 crons |
| W28 | 694 | $55.95 | MOFS, PFS development |
| **W29** | **251** | **$338.59** | **Peak: monster $221 + dev** |
| W30 | 183 | $43.16 | Normal |

## Cron Cost Breakdown

| Model | Sessions | Cost | Note |
|---|---|---|---|
| claude-opus-4-7 | 150 | $130.36 | Implementation crons |
| claude-sonnet-4-6 | 39 | $29.53 | Implementation crons |
| claude-haiku-4-5 | 501 | $16.92 | Monitoring — efficient |

## Cost by Source

| Source | Sessions | API Calls | Cost |
|---|---|---|---|
| Telegram | 622 | 8,890 | $425.81 (69.3%) |
| Cron | 2,679 | 7,795 | $176.82 (28.8%) |
| Subagent | 31 | 395 | $9.80 (1.6%) |
| CLI | 6 | 72 | $1.31 |
