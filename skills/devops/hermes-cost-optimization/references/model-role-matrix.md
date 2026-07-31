# Role matrix for Hermes model selection

This reference captures a practical model split for a Hermes setup when selecting among currently verified OpenRouter models.

## Verified set

- `x-ai/grok-4.20`
- `google/gemini-3-flash-preview`
- `deepseek/deepseek-v4-pro`

## Recommended split from this session

| Role | Model | Why |
|---|---|---|
| Main | `x-ai/grok-4.20` | Fast, strict, low hallucination, large context |
| Title generation | `google/gemini-3-flash-preview` | Cheap and fast |
| Approval | `google/gemini-3-flash-preview` | Cheap and fast for trivial decisions |
| Web extract / summarization | `google/gemini-3-flash-preview` | Good speed/quality balance |
| Compression | `deepseek/deepseek-v4-pro` | Cheap, long context, suitable for summarization/compression |
| Code/file-heavy fallback | `deepseek/deepseek-v4-pro` | Cheap and strong for code / file tasks |
| Extra long-context fallback | `x-ai/grok-4.20` | Large context and speed |

## Notes

- The user explicitly wanted a setup limited to models actually present in OpenRouter.
- Gemini 3 Pro and Sonnet were intentionally excluded in the final configuration.
- Grok 4.20 was chosen as main after comparison on speed, strictness, and hallucination behavior.