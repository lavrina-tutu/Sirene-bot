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

Scripts auto-backup config, patch via Python (YAML-safe), print diff, restart `hermes-gateway` via systemd.

## ТУТУ gateway specifics

- **Type**: Anthropic-compatible proxy (NOT OpenRouter)
- **Endpoint**: `https://llm-gateway.tutu.ru/api/anthropic`
- **Auth**: standard `x-api-key` header (same as Anthropic SDK)
- **Models available**: `claude-sonnet-4-6`, `claude-opus-4-7`, `claude-haiku-4-5` ✅
- **Key 1 (main)**: in `~/.config/hermes/.env` (var: TUTU_LLM_KEY_MAIN)
- **Key 2 (reserve)**: in `~/.config/hermes/.env` (var: TUTU_LLM_KEY_RESERVE)
- OpenRouter hypothesis: **NOT needed** — `/v1/messages` responds 200 OK in native Anthropic format

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
`~/WorkVault/UserManuals/LLM-Migration/`
