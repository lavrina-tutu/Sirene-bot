---
name: agent-llm-access-options
description: Use when choosing LLM access for an autonomous agent.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llm, cost, subscription, api, local-llm, agent-access]
    related_skills: [hermes-cost-optimization, hermes-tutu-gateway]
---

# LLM access options for an autonomous agent

## When to Use

Саша спрашивает про подписки на модели (Claude Pro, Codex, GLM Coding, Kimi Code, MiniMax, Alibaba/Qwen, Coding Plan), «что дешевле для оркестрации/разработки», «хватит ли тарифа на наши объёмы», про «микс моделей», локальную модель вместо API или покупку железа (Mac mini и т.п.) под LLM. Также — перед любой рекомендацией платного доступа для Hermes.

Триггеры: подписка на модель, подписка для оркестрации, дешевле модели, снизить стоимость LLM, Codex подписка, GLM Coding, Kimi Code, MiniMax, Claude Pro для агента, локальная модель вместо API, Mac mini под LLM.

This skill covers the procurement/access-path side; the routing/config side (delegation/auxiliary slots, compression, custom endpoints) lives in `hermes-cost-optimization`.

How to pick a paid access path for an agent that runs a tool-loop, skills and crons (Hermes), not a human chat. Triggers: подписка на модель, подписка для оркестрации, дешевле модели, снизить стоимость LLM, Codex подписка, GLM Coding, Kimi Code, MiniMax, Claude Pro для агента, локальная модель вместо API, Mac mini под LLM.

Every recommendation must pass TWO gates: the vendor's terms, and the agent's technical needs (tools + reasoning + long context).

## Rule 1 — consumer chat subscriptions do not cover a third-party agent

Hermes is a third-party harness. Most consumer plans license only first-party surfaces:

- **Claude Pro / Max** — NOT usable. Access is limited to Anthropic's own tools (claude.ai, Claude Code CLI); third-party harnesses were expressly cut off, and any restored path is separate metered credit, not the plan quota. Never propose «Claude in the mix» as a subscription.
- **ChatGPT Business + Codex** — usable ONLY for interactive/light work. Treating the seat as an API backend for an autonomous dev chain (roles on a schedule, keepalive pings every ~30 min, hundreds of millions of tokens/month) is an automated-access ToS/Usage-Policies violation — OpenAI deactivates the ChatGPT account and the appeal is final-rejected (second appeal = final refusal, re-appealing is useless). Never route autonomous bulk work through a ChatGPT-login plan; use an API key or an agent-first plan (below). The automation fingerprint is visible server-side (all sessions `source=exec`/`has_user_event=0`, sub-minute sessions, machine-precise repeat intervals) — random delays or varied prompts do NOT mask it; the only real fix is channel separation: subscription = human interactive only, automation = API key / corporate contract.

Audit/forensics recipe for proving or excluding the fingerprint in Codex logs: `references/codex-automation-signals.md`.
- **Alibaba Cloud Coding Plan Pro ($50/mo)** — usable and explicitly agent-first: the official integration list includes Hermes Agent, Codex, Claude Code, Qwen Code, OpenCode, Cursor, Cline. Quota metered in REQUESTS, not tokens: 6,000/5h, 45,000/wk, 90,000/mo. Models: qwen3.7-plus/-3.6-plus (vision), kimi-k2.5, glm-5, MiniMax-M2.5, qwen3-coder-next/-plus, glm-4.7 — flash family and qwen3.8-max are NOT in the plan. Key `sk-sp-…`; endpoints `https://coding-intl.dashscope.aliyuncs.com/v1` (OpenAI-compatible) and `/apps/anthropic` (Anthropic-compatible). Lite discontinued Mar 2026. Sizing + full model/price table: `references/alibaba-qwen-plans.md`.
- **GLM Coding Plan (Z.AI)** — usable; the official allowlist includes general-purpose agents, best-effort under load (coding tools get priority). Cheapest entry tier.
- **MiniMax Token Plan** — usable; its setup wizard targets the agent's own config file (beware: it can rewrite the live config).
- **Kimi — two distinct tracks, do NOT mix** (keys are non-interchangeable → 401/403). (a) **Kimi Code subscription** (kimi.ai membership, e.g. PRO $31/mo annual): consumer/coding-agent plan, endpoints `api.kimi.com/coding/v1` (OpenAI) and `api.kimi.com/coding` (Anthropic). Gated by **User-Agent** — a plain call to `/coding/v1/chat/completions` returns **403 `access_terminated_error`** («only available for Coding Agents such as Kimi CLI, Claude Code, Roo Code...»); ToS is «personal interactive use only». It is NOT an API backend for an autonomous Hermes harness. (b) **Kimi Platform (Developer API)** `api.moonshot.ai/v1`, OpenAI-compatible, key `MOONSHOT_API_KEY`, **pay-as-you-go** — this is the only track usable for an agent. A Kimi subscription is never a per-role Hermes model source by itself.
- **The trap to name when Саша sees «Kimi subscription»**: the consumer/web subscription (kimi.ai PRO) is a product for interactive coding sessions, not a way to feed roles (default/arch/ha/exec) on a schedule. For an agent the only valid entry is the Developer API.

Model/price map for Kimi Platform on OpenRouter (verified via `api/openrouter/v1/models`): kimi-k3.1-pro has ~1M context; kimi-k3 ~1M; kimi-k2.7-code 262K; see `references/kimi-provider-tracks.md`.

Verify current terms on the vendor's own pricing/allowlist page before recommending — plans change quarterly.

## Rule 2 — a subscription is only a lever if the agent's role fits it

Separate roles before routing to a subscription:

- **Orchestrator / chat / crons** — many small tool-heavy calls. Route via pay-per-token API on the existing gateway; a near-floor input price beats a flat plan unless volume is genuinely high.
- **Reviewer / critical judgement** — heavy reasoning and full-context reads; keep on API unless the flat plan itself carries strong reasoning families (Alibaba Coding Plan exposes kimi-k2.5/glm-5 — an independent-family reviewer inside the same quota is a plus, not a compromise).
- **Architect / executor of a dev chain** — a coding-agent subscription (Codex) is the natural fit.

## Rule 3 — local hardware is not a cost lever for a cheap orchestrator

A machine bought to replace an orchestrator already running at near-floor API price does not pay back (payback in years, not months). Local inference is memory-bandwidth bound and capped by unified RAM (~32 GB runs ~30B Q4; ~64 GB reaches 70B-class). Fixed RAM tiers cannot be upgraded after purchase (and a vendor may skip a mid tier entirely). Buy local for privacy / sovereignty / offline — not for savings on an already-cheap model. To evaluate a SPECIFIC machine (mini-PC, NUC, laptop) under local inference — spec-by-criteria decision table in `references/hardware-eval-for-local-llm.md`. Always ask the scenario FIRST (orchestration vs supplementary private/offline): a machine that excels at one may be pointless for the other.

## Rule 4 — the real cost lever is role routing, not hardware

Before recommending any purchase, check in this order: (1) drop redundant per-role IDE subscriptions; (2) move dev-chain roles to the coding-agent subscription; (3) keep the orchestrator on the cheapest capable API model; (4) only then consider an overflow subscription. Ask for a usage breakdown (which model IDs consume the bill) before proposing a swap — without it you may cut crons instead of the intended waste.

## Pitfall — never probe model availability with a model prompt

Liveness/health checks like «Reply with exactly: OK», «Назови 2+2», «hi» are (a) an automation fingerprint — repeated verbatim probe prompts with machine-precise intervals scream bot — and (b) wasted billable calls. Probe availability with `curl` to the API endpoint (HTTP status) instead of an LLM call; if a check must pass through the model, do it once interactively, never on a schedule.

## Pitfall — never restate pricing from memory

Prices and plan terms move. Read the live catalog (`/api/openrouter/v1/models` via the gateway) and the vendor pricing page each time; quote them, never recall them.

## Pitfall — the vendor model name in a listing may be mangled

Promo text often garbles CPU/GPU model IDs (a nonexistent «Ryzen AI 9 HX 470» is actually the HX 370 series). Resolve the real series before evaluating; spec-and-quote against the actual silicon, never the listing string.

## Related

The routing/config side of cost reduction lives in `hermes-cost-optimization` (delegation/auxiliary slots, compression, custom endpoints); this skill covers the procurement/access-path side.

Alibaba/Qwen plans, models and quotas (verified 10.2026): `references/alibaba-qwen-plans.md`.
