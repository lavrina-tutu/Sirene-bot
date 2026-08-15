# Hardcoded System Prompt Blocks

Investigated 2026-08-12 against `hermes-agent/agent/prompt_builder.py` and `system_prompt.py`.

## Tool-use Enforcement Block

**Source:** `prompt_builder.py` lines 309-431
**Config:** `agent.tool_use_enforcement` (global config.yaml)
**Default:** `"auto"`

**Injection logic:**
```python
TOOL_USE_ENFORCEMENT_MODELS = ("gpt", "codex", "gemini", "gemma", "grok", "glm", "qwen", "deepseek")
_inject = any(p in model_lower for p in TOOL_USE_ENFORCEMENT_MODELS)
```

When `auto` and model name matches → injects `<mandatory_tool_use>...</mandatory_tool_use>` block.
Can be set to `true` (always), `false` (never), or a custom list of substrings.

**Content (simplified):** "You MUST use your tools to take action — do not describe what you would do... immediately make the corresponding tool call... Every response should either contain tool calls or deliver a final result."

**Verified on tz-dev:** model `qwen/qwen3.6-plus` contains "qwen" → enforcement block IS injected.

## Honcho Block

**Source:** `plugins/memory/honcho/` (only when `memory.provider: honcho`)
**Default:** Not present (disabled by default)
**Content:** Dialectic user modeling data from Honcho's memory backend
**Cost:** Cloud $100 free + $2/M tokens; Self-host free (Docker: API + PostgreSQL+pgvector + Redis, ~2GB RAM)

## agent.system_prompt

**Source:** `config.yaml → agent.system_prompt` (per-profile)
**Default:** None
**Current tz-dev:** "Правило автономии: если api_call_count превысил 100, вызови /compress"
**Behavior:** Injected only when `display.personality: none`. When personality is active, appended after personality block.
