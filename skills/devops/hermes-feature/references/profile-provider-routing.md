# Profile/provider routing for custom Hermes endpoints

## Symptom observed

A profile (e.g. `tz-dev`) or a cron job can fail with provider-auth errors even when the model name looks valid.

Observed failure pattern in this session:
- profile showed `model: openai/gpt-5.4-mini`
- provider was set to an internal nickname from another config state (`tutu`)
- gateway/logs then reported `Unknown provider 'tutu'` or `Provider authentication failed`
- after switching the provider to a valid Hermes provider name and pairing it with the intended endpoint, the profile became usable

## Checks that matter

1. Inspect the *effective* profile config, not only the global config.
2. Ensure the provider name is a Hermes-recognized provider string.
3. Keep `model`, `provider`, and `base_url` internally consistent.
4. Re-check cron jobs separately: a cron can still carry stale provider/base_url values even after the profile is fixed.
5. If a provider uses a vendor-prefixed model slug, make sure the provider/endpoint choice matches that routing style.

## Verification commands

- `hermes profile show <profile>`
- `hermes doctor`
- `hermes cron list`
- inspect the relevant profile config and cron job config directly

## What to avoid

- Do not assume the profile inherits the main Hermes provider automatically.
- Do not leave old provider nicknames in a target profile or job after switching model families.
- Do not treat `Unknown provider ...` as a pure model-name issue; fix provider routing first.
