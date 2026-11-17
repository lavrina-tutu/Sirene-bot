# Cron environment and delivery

Follow the gateway restrictions in [SKILL.md](../SKILL.md). Sasha decides whether to restart the gateway and performs any approved restart from an external shell. Do not record passwords or tokens.

## Delivery target mismatch — no_agent cron (23.07.2026)

`no_agent` cron jobs with `script:` deliver messages to the `deliver` field in jobs.json. A hardcoded chat_id/thread_id in the script's docstring or comments is documentation only; the actual destination is the cronjob's `deliver` field. If messages reach the wrong topic, inspect `hermes cron list` and its `deliver` field. After correcting `deliver`, update the script's docstring/comments to match.

### Historical context

On 23.07.2026, `pfs_notify` delivered to thread 5 (WorkVault) instead of thread 7 (Monitoring) because `deliver` was `:5`. The correction was `cronjob(action='update', job_id=..., deliver='telegram:-1004300127777:7')`.

## Subprocess environment and credentials

A `no_agent` cron script or a subprocess spawned via `terminal(background=...)` may not see `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `GH_TOKEN`, `TELEGRAM_BOT_TOKEN` and other Hermes-managed credentials from `.env`, even when exported there. An interactive `terminal` session can see them, so an interactive test alone is misleading.

`tools/environments/local.py::_ALWAYS_STRIP_KEYS` unconditionally strips `GH_TOKEN`, `GITHUB_TOKEN`, `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`, `SLACK_BOT_TOKEN`, gateway relay credentials and others from spawned child processes. Separately, `_HERMES_PROVIDER_ENV_BLOCKLIST`, built from `PROVIDER_REGISTRY.api_key_env_vars`, strips provider keys including `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` unless registered through `env_passthrough` (a skill's `required_environment_variables` or `terminal.env_passthrough` in config.yaml). Passthrough does not override the unconditional Tier-1 stripping of `GITHUB_TOKEN` or `GH_TOKEN`. This is a credential-leak protection (GHSA-rhgp-j443-p4rf).

For a secret needed by a `no_agent` script, use a separate skill-specific credential under a name outside the blocklist, such as `HERMES_SKILLS_DIGEST_GH_TOKEN` or `HERMES_SKILLS_DIGEST_ANTHROPIC_KEY`. Set the values securely in `~/.hermes/.env`; never put actual passwords or tokens in documentation or prompts. Read the custom name in the script, e.g. `os.environ.get("HERMES_SKILLS_DIGEST_GH_TOKEN")`.

The gateway reads `.env` at process startup. A change is not visible to already running cron jobs until the gateway is restarted. The relevant commands are `systemctl --user restart hermes-gateway.service` on Linux and `hermes gateway restart` or VBS restart on Windows; Sasha decides on and performs the restart externally. Do not restart the gateway from a cron job or agent.

Validate the real subprocess path with `cronjob(action='run', job_id=...)` when a run is authorized; `python3 script.py` in an interactive `terminal` does not reproduce the cron environment. Do not create cron jobs without Sasha's explicit instruction.
