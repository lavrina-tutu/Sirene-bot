---
name: hermes-cost-optimization
description: "Optimize Hermes model and token costs"
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, cost, tokens, optimization, delegation, auxiliary, haiku, local-llm, exo]
---

# Hermes cost optimization

Measure actual use, choose an appropriate route, and verify the result. Preserve quality and reliability; this skill does not authorize changing development policy, creating cron jobs, restarting the gateway, editing secrets or cleaning a database.

## Measure first

Identify the actual model, provider, endpoint, configuration source and token use for main chat, delegation and each auxiliary task. Compare cost using current verified prices and actual input, output and cached tokens; historical prices and ratios are not a current estimate. Compare representative tasks and quality, not just unit price. For context and usage measurement, see [context-window analysis](references/context-window-analysis.md).

DevWorkflow model/backend assignments come from the active `tools.dev_workflow` role configuration, not a historical task matrix. Check the applicable configuration and pipeline before recommending a role change. The former rules assigning every specification to Opus and «Opus only cron» are historical, not a current role policy. The dated source matrix is in [model and role matrix](references/model-role-matrix.md); previous claims and prices are in [model cost history](references/model-cost-history.md).

## Choose and configure

- Route simple, high-volume auxiliary work to a capable less expensive model where measured quality allows; retain an appropriate main model. Separately configure delegation, compression, session search and vision. Do not infer one slot from another.
- Before relying on a per-call delegation model, check the model-facing schema and active code: historical versions disagree about whether the parameter exists. Check when delegation config is read in the deployed runtime. Do not promise an immediate switch solely because YAML changed. See [delegation history](references/delegation-history.md) and [historical per-call patch](references/delegate-per-call-model-patch.md).
- When changing backend, align model, provider, base URL and key. Clear obsolete auxiliary endpoint/provider overrides where appropriate, and verify the effective route. Do not expose keys in output or search in ways that persist them in tool calls.
- Main-model fallback is not automatically delegation fallback. Check delegation's own route, fallback configuration and active implementation; absence of evidence is not a guarantee of fallback.
- Ensure the compression model can handle the effective compression threshold and prompt. Check actual context limits and headroom, especially when switching main models. Thresholds, examples and historical implementation are in [compression internals](references/compression-internals.md).
- For local or corporate endpoints, verify actual integration, loaded model, connectivity and warm-up. A blank first response is not a successful model test. Verify VPN availability and fallback independently. Details: [local endpoints and fallback](references/local-endpoints-and-fallback.md).
- For critical agent cron jobs choose a backend whose reliability has been demonstrated; a `no_agent` job does not need a cheap LLM. Do not create or modify cron without explicit authorization.

Review historical commands and their assumptions before use: [configuration recipes](references/configuration-recipes.md). Existing `scripts/switch_delegation_model.py` checks endpoint reachability, sets delegation model/provider/base URL/key via CLI, and tracks the selected state. Its documented direct or `no_agent=true` cron use is environment-specific; do not modify the script as part of documentation cleanup. Verify actual runtime application and effective settings, not merely a successful write. No cron is created by this instruction.

## Validate and display

Record baseline and after-change effective routes, representative output quality, errors, latency and usage; investigate unexpected provider, context or fallback behavior before declaring savings. Show the model in gateway replies through configured `display.runtime_footer` rather than duplicating an LLM prompt instruction. For footer mechanics and failed historical prefixes see [gateway response injection](references/gateway-response-injection.md).

Treat the old state.db secret-cleanup recipe as history only: [secret cleanup history](references/secret-cleanup-history.md). Secret cleanup requires its own authorized procedure and must avoid re-recording secrets in tool calls.
