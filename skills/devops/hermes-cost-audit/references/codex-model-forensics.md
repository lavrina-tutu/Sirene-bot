# Codex CLI cost forensics (gpt-6.x dev roles)

Use when the user asks how much the **Codex CLI dev contour** (architect/reviewer/executor roles, gpt-6.1-sol / gpt-6-astra / gpt-5.6-terra / gpt-6-luna) cost, or wants to compare cost of swapping models across roles. **Codex spend never appears in `~/.hermes/state.db`** — codex runs its own CLI and bills separately, so a "0 records for model X in state.db" result does not mean "model X was free".

## Where the data lives

**Tokens by model/role — `~/.codex/state_5.sqlite` → `threads`:**
`SELECT model, COUNT(*), SUM(tokens_used) FROM threads GROUP BY model ORDER BY COUNT(*) DESC`
Use `tokens_used` (total) per model. `agent_role` column is NULL in practice — the role is NOT stored; derive it from the model via `WorkVault/Registries/EcosystemConfig.yaml` → `dev_workflow.roles` (architect=sol, reviewer=astra, executor=terra, executor_light=luna). If the mapping is stale, ask the user which model maps to which role before attributing spend.

Do NOT use `~/.codex/thread_history_1.sqlite`.`thread_turns` for call counts — it holds ~1 turn per thread (matches the "capacity check" rule). For per-call token split, `usage` events in rollout JSONL carry `input_tokens` / `cached_input_tokens` / `output_tokens`, but they carry **no model string** — attribution to a model must come from the threads mapping, not from the usage event.

**Prices — `~/.hermes/cache/openrouter_model_metadata.json`, NOT `~/.codex/models_cache.json`.** `models_cache.json` has model lists/capabilities but **no pricing**; the price for corporate codex gpt-6.x models lives in Hermes cache under each model's `pricing` key: `{prompt, completion, input_cache_read, input_cache_write}` plus an `overrides` block activating above ~272K context. Read it with a recursive find on the slug (the file is a nested dict, not a flat model map).

## Known gpt-6.x prices (per 1M tokens)

| Model | input | output | cache-read | note |
|---|---|---|---|---|
| gpt-6.1-sol | $2 | $10 | $0.10 | >272K: $4/$15 |
| gpt-6-astra | $10 | $50 | $1.0 | >272K: $20/$75 — **5× sol on both sides** |

Astra is a flat 5× more expensive than Sol across input, output, and cache (both base and >272K tiers). When a swap analysis depends on prices, this proportionality is what drives the result.

## Role-swap cost analysis (is moving the stronger model to a bigger role worth it?)

To decide whether to assign a strong/expensive model to a higher-volume role and a cheap one elsewhere, compare **relative token volume × price ratio**, then solve for the breakeven on the non-price benefit (fewer return iterations).

1. Pull `SUM(tokens_used)` per model (see above), map to roles.
2. Attach per-model price. If the candidate is a tier where `price_expensive / price_cheap = R` and the expensive-model role has `V_e` tokens vs cheap-model role `V_c`, compute:
   - current cost ∝ `V_e*P_cheap + V_c*P_expensive`
   - swapped cost ∝ `V_e*P_expensive + V_c*P_cheap`
3. The swap is more expensive ON THE SAME TOKENS whenever the expensive model's NEW role is the higher-volume one (moves a big cost onto the higher rate).
4. **Breakeven on the qualitative win**: swap pays only if the fewer-error benefit cuts > `1 - swapped_cost/current_cost` of the combined spend. Solve this threshold explicitly and compare against a real estimate of the benefit (e.g. actual review-return rate) — never assert the swap is cheaper on intuition, and never pull it if the only stated benefit ("stronger architect asks for fewer redos") is unquantified.

Worked example (this stack): architect ran 2× the tokens of reviewer (442.7M vs 214.9M) and Astra costs 5× Sol. Swapping architect→Astra/reviewer→Sol makes it ~1.6× MORE expensive on identical tokens; it pays only if a stronger architect cuts combined arch+review spend by >~37%. That threshold is high — a "stronger might reduce redos" hunch is not evidence it clears it.

## Delivery

Report current-vs-scenario as token-unit costs side by side, state the exact breakeven threshold the proposal must clear, and flag what evidence would confirm it (count review-return/redo turns in the actual threads if relevant data exists) before any config change.
