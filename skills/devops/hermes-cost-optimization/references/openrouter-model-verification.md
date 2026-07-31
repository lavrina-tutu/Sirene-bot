# OpenRouter model verification

Use the lightest possible query to confirm a model really exists in the target catalog before recommending it.

## Pattern

1. Search the provider page or model slug with a minimal exact query.
2. Confirm the model card exists and note:
   - provider family
   - model slug
   - context
   - price
3. Do not infer availability from blog posts or comparisons alone.

## Session result

Verified as available in OpenRouter for the current Hermes setup:

- `x-ai/grok-4.20`
- `google/gemini-3-flash-preview`
- `deepseek/deepseek-v4-pro`

## Pitfalls

- A comparison page may mention a model even when the model card is not directly available.
- A provider family page may include several models; still verify the exact slug.
- Use one exact search per candidate model when the goal is only existence, not exhaustive market research.