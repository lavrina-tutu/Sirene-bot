# Cursor CLI — Available Models

Snapshot from 2026-08-04 (`agent --list-models`). Account: Alexander Tkachenko (Team Plan).

## Model families with reasoning levels

Cursor uses `{family}-{level}` naming with optional `-thinking` and `-fast` suffixes.

### Claude Opus 4.8
| Level | Model ID |
|-------|----------|
| Low | `claude-opus-4-8-low`, `-fast` |
| Medium | `claude-opus-4-8-medium`, `-fast` |
| High | `claude-opus-4-8-high`, `-fast` |
| Extra High | `claude-opus-4-8-xhigh`, `-fast` |
| Max | `claude-opus-4-8-max`, `-fast` |
| Low Thinking | `claude-opus-4-8-thinking-low`, `-fast` |
| Medium Thinking | `claude-opus-4-8-thinking-medium`, `-fast` |
| High Thinking | `claude-opus-4-8-thinking-high`, `-fast` |
| Extra High Thinking | `claude-opus-4-8-thinking-xhigh`, `-fast` |
| Max Thinking | `claude-opus-4-8-thinking-max`, `-fast` |

### Claude Opus 5
Levels: low/medium/high/xhigh/max, with and without `-thinking`, all with `-fast` variants.

### Claude Sonnet 5
Levels: low/medium/high/xhigh/max, with and without `-thinking`, all with `-fast` variants.
- **Recommended for исполнитель (DSV4-M):** `claude-sonnet-5-medium`
- **Recommended for архитектор (DSV4-H):** `claude-sonnet-5-thinking-xhigh`

### Claude Fable 5
Levels: low/medium/high/xhigh/max, with and without `-thinking`. All marked "(NO ZDR)".
- Zero Data Retention mode — suitable for sensitive code.

### GPT-5.5
| Level | Model ID |
|-------|----------|
| None | `gpt-5.5-none`, `-fast` |
| Low | `gpt-5.5-low`, `-fast` |
| Medium | `gpt-5.5-medium`, `-fast` |
| High | `gpt-5.5-high`, `-fast` |
| Extra High | `gpt-5.5-extra-high`, `-fast` |

### GPT-5.6 Sol
Levels: none/low/medium/high/xhigh/max, all with `-fast` variants. Max context: 1M tokens.

### GPT-5.6 Terra
Same structure as Sol: none/low/medium/high/xhigh/max + fast variants.

### GPT-5.6 Luna
Same structure: none/low/medium/high/xhigh/max + fast variants.

### Cursor Grok 4.5
Levels: low/medium/high, all with `-fast` variants.

### Codex 5.3
Levels: low/medium/high/xhigh, all with `-fast` variants.

### Other models
- Composer 2.5, Composer 2.5 Fast
- GPT-5.4 (low/medium/high/xhigh + fast)
- GPT-5.4 Mini/Nano (none/low/medium/high/xhigh)
- GPT-5.2 (low/high/xhigh + fast)
- GPT-5.1 (low/default/high)
- GPT-5 Mini
- Gemini 3.6 Flash (minimal/low/medium/high)
- Gemini 3.1 Pro, Gemini 3.5 Flash, Gemini 3 Flash
- Kimi K3 (low/default/max), Kimi K2.7 Code
- GLM 5.2 (high/max)
- Claude Opus 4.7, 4.6, 4.5
- Claude Sonnet 4.6, 4.5, 4

### Parameterized model syntax
```
agent --model 'claude-opus-4-8[context=1m,effort=high,fast=false]'
```

## Key finding

**No DeepSeek models in Cursor CLI.** The DSV4-H/M/L roles from `hermes-feature` must be mapped to Claude/GPT equivalents when using Cursor as the executor.
