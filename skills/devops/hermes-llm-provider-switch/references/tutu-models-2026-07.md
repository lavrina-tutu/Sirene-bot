# ТУТУ Gateway — Available Models (2026-07)

Verified via `/v1/models` API call on 2026-07-02. Prices = official Anthropic API rates.

| Model | ID | Context | Output | Input /1M | Output /1M | Notes |
|-------|----|---------|--------|-----------|------------|-------|
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | 128K | $2→$3* | $10→$15* | Promo until 31.08.2026; new tokenizer +30% tokens vs 4.6 |
| Claude Fable 5 | `claude-fable-5` | 1M | 128K | $10 | $50 | Top-tier Mythos-class; 2× Opus 4.8 price |
| Claude Opus 4.8 | `claude-opus-4-8` | 1M | 128K | $5 | $25 | Flagship before Fable 5 |
| Claude Opus 4.7 | `claude-opus-4-7` | 1M | 128K | $5 | $25 | Used as Hermes delegation model |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | 128K | $3 | $15 | Current main model |
| Claude Opus 4.6 | `claude-opus-4-6` | 1M | 128K | $5 | $25 | |
| Claude Opus 4.5 | `claude-opus-4-5-20251101` | 200K | 64K | $5 | $25 | |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | 200K | 64K | $1 | $5 | Cheapest; used as fallback |
| Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | 1M | 64K | $3 | $15 | |
| Claude Opus 4.1 | `claude-opus-4-1-20250805` | 200K | 32K | $5 | $25 | |

*\* Sonnet 5 promo: $2/$10 until 31.08.2026, then reverts to $3/$15*

## Key notes on Sonnet 5

- New tokenizer: same English text = ~30% more tokens than Sonnet 4.6 → effective cost higher than sticker
- Performance ≈ Opus 4.8, but cheaper per token
- thinking: adaptive only (not `enabled` mode)
- effort levels: low/medium/high/xhigh/max all supported

## Key notes on Fable 5

- Anthropic's Mythos-class model (previously restricted)
- Most expensive publicly available model: $10/$50
- Same capabilities as Sonnet 5 (adaptive thinking, 1M context)
- Use only when maximum capability required and cost is not a constraint
