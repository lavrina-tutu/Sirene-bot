---
name: hermes-llm-provider-switch
description: "Switch Hermes between LLM providers (Anthropic ↔ corporate proxy). Covers custom_providers, delegation model patching, backup/rollback scripts."
version: 1.0.0
tags: [hermes, llm, anthropic, proxy, config, migration]
platforms: [linux]
---

# Hermes LLM Provider Switch

Switching Hermes between Anthropic API and a corporate Anthropic-compatible proxy (e.g. ТУТУ LLM Gateway).

## Trigger conditions

- User wants to switch main LLM provider/key
- Corporate gateway onboarding
- API key rotation
- Cost optimisation (corporate proxy may be cheaper/free)

## Architecture

Hermes uses `custom_providers` in `config.yaml` to define named providers. Key fields that need changing:

| Field | Location in config.yaml |
|-------|------------------------|
| Main model provider | `model.provider` |
| Fallback model | `fallback_providers` (JSON string) |
| Delegation model | `delegation.provider` |
| Auxiliary models | `auxiliary.vision/compression/session_search.provider` |
| Provider definition | `custom_providers[]` |

## Scripts (on VM)

Located at `~/WorkVault/UserManuals/LLM-Migration/`:

| Script | Purpose |
|--------|---------|
| `user_change_delegation_models1.sh --provider tutu` | Switch all models to ТУТУ gateway |
| `user_change_delegation_models1.sh --provider anthropic` | Switch all models back to Anthropic |
| `switch_back_to_anthropic.sh` | Full rollback from backup |
| `switch_to_sonnet5.sh` | Switch main model: sonnet-4-6 → sonnet-5 |
| `switch_back_to_sonnet46.sh` | Switch main model: sonnet-5 → sonnet-4-6 |

Scripts auto-backup config, patch via Python (YAML-safe), print diff, restart `hermes-gateway` via systemd.

### Model-version switching (separate from provider)

There are two orthogonal switching operations:
1. **Provider switch** — changes `model.provider` + `custom_providers` (Anthropic ↔ ТУТУ)
2. **Model version switch** — changes `model.default`, `auxiliary.*.model`, `delegation.model`

Model-version scripts patch these fields: `model.default`, any `auxiliary.*` where the model matches, `delegation.model`, and model IDs in `cron/jobs.json`. They work regardless of which provider is active.

Pattern for new model-version switch scripts (reusable template):
```bash
FROM_MODEL="claude-sonnet-4-6"
TO_MODEL="claude-sonnet-5"
# Python loop: data["model"]["default"], aux sections, delegation["model"]
# Then patch cron/jobs.json separately
# Then diff + systemd restart
```

## ТУТУ gateway specifics

- **Type**: Anthropic-compatible proxy (NOT OpenRouter)
- **Endpoint**: `https://llm-gateway.tutu.ru/api/anthropic`
- **Auth**: standard `x-api-key` header (same as Anthropic SDK)
- **Models available**: see `references/tutu-models-2026-07.md` for full list with pricing
- **Key 1 (main)**: hardcoded in `config.yaml` custom_providers block (also in `~/.config/hermes/.env`)
- **Key 2 (reserve)**: in `~/.config/hermes/.env`
- OpenRouter hypothesis: **NOT needed** — `/v1/messages` responds 200 OK in native Anthropic format
- **Check available models**: `curl -s https://llm-gateway.tutu.ru/api/anthropic/v1/models -H "x-api-key: <key>" -H "anthropic-version: 2023-06-01" | python3 -m json.tool`

## config.yaml changes for custom provider

```yaml
custom_providers:
  - name: tutu
    type: anthropic
    base_url: https://llm-gateway.tutu.ru/api/anthropic
    api_key: <key>
```

Then set `provider: tutu` everywhere `provider: anthropic` appears (except `provider: auto` sections — leave those alone).

## Sections to leave as `provider: auto`

`web_extract`, `skills_hub`, `approval`, `mcp`, `title_generation`, `triage_specifier`, `curator`, `kanban_decomposer`, `profile_describer` — these inherit the main model automatically.

## Backup location

`~/backup_configs/hermes_config_anthropic_backup_<date>.yaml`

## Verification after switch

Gateway sends a startup notification to Telegram automatically on restart — no manual check needed. If the message arrives, it works.

## Pitfalls

- **`provider: auto` sections**: do NOT change these — they resolve to the main model automatically.
- **`fallback_providers` is a JSON string**: cannot be patched with sed; use Python/PyYAML.
- **`custom_providers: []`** must be populated for named provider `tutu` to resolve; if it stays empty, Hermes throws `provider 'tutu' not found`.
- **base_url trailing slash / `/v1` suffix**: use exactly `https://llm-gateway.tutu.ru/api/anthropic` — no trailing slash, no `/v1`.
- **Legacy `/v1/complete` endpoint**: returns 405 — this is expected; Hermes uses `/v1/messages` only.

## User manuals

Full instructions in WorkVault (sync via rclone to ownCloud):
`~/WorkVault/UserManuals/LLM-Migration/README.md` — single source of truth, contains SSH instructions, all script commands, full models table with pricing.

`references/tutu-models-2026-07.md` — condensed models + pricing snapshot for ТУТУ gateway (verified 2026-07-02).
