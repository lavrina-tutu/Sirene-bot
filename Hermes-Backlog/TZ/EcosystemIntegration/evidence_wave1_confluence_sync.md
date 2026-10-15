# Evidence — wave1 confluence_sync (eco-config-w1 HF:test)

Generated: 2026-10-11 19:00   |  Task: t_91cc435c (HF:test)  |  Role: испытатель

## 1. `explain confluence_sync` (each non-secret key -> YAML; zero legacy/overlay in migrated set)

Output (stdout of `python3 /home/tkachenkoav/.hermes/lib/usertools_config.py explain confluence_sync`):

```
ANTHROPIC_API_KEY source=shared_env
CONFLUENCE_TOKEN source=legacy
CONFLUENCE_URL source=shared
CONTACTS_ENCRYPTION_KEY source=shared_env
FIREFLIES_API_KEY source=shared_env
GATEWAY_ALLOW_ALL_USERS source=shared_env
LOGS_PATH source=ecosystem_config
LOOP_TOKEN source=shared_env
OWNCLOUD_APP_TOKEN source=process_env
OWNCLOUD_URL source=process_env
OWNCLOUD_USER source=process_env
OWNCLOUD_WEBDAV_URL source=process_env
TAVILY_API_KEY source=shared_env
TELEGRAM_ALLOWED_CHATS source=process_env
TELEGRAM_ALLOWED_USERS source=shared_env
TELEGRAM_ALLOW_ALL_USERS source=shared_env
TELEGRAM_BOT_TOKEN source=shared_env
TELEGRAM_EXCLUSIVE_BOT_MENTIONS source=process_env
TELEGRAM_HOME_CHANNEL source=shared_env
TELEGRAM_REQUIRE_MENTION source=process_env
TOOL_DIR source=ecosystem_config
TUTU_DOMAIN_PASSWORD source=shared_env
WORKVAULT_PATH source=shared
enabled source=ecosystem_config
llm source=hermes_llm

```

Migrated-set verdict: the single `legacy` line is `CONFLUENCE_TOKEN`,
**expected** at this stage — per HF-plan `Sekvencing CONFLUENCE_TOKEN`, it flips to
`source=shared_env` only AFTER `ORCH:shared-state` (IAC-03) copies it into
`~/.config/hermes/.env`. All migrated non-secret keys (TOOL_DIR, LOGS_PATH,
CONFLUENCE_URL, WORKVAULT_PATH) resolve `ecosystem_config`/`shared`. Not a defect.

## 2. ErrorBus — config/env/yaml/missing events

Count (tools=['ConfluenceSync', 'confluence_sync']): **0**  →  **PASS (0 no-new-config events)**

## 3. Boot-times / real-cycle (> =3 ticks or 1 working day or real call)

no own cron (IAC-17b: real CLI call — confluencesync import+config smoke passed).

Note: migration dual_read landed 2026-10-11T00:00:00 (Sunday).
FF/MFF/PFS crons are weekday-gated; post-migration >=3 consecutive ticks to be
collected in the Mon 9-19 window (plan HF-plan_wave1 Q-1) — not fabricatable now.

## 4. Real runtime smoke (not dry-run)

`load_tool_config("confluence_sync", keys=<migrated set>)` resolved without KeyError;
values populated from ecosystem_config/shared (see pytest IAC-05/07/09/11).
ConfluenceSync/PFS: `source=shared_env` for CONFLUENCE_TOKEN expected AFTER
ORCH adds it to shared .env (IAC-03, sequencing in HF-plan §Sekvencing).

## 5. Artifacts / links

- plan: `TZ/EcosystemIntegration/HF-plan_wave1_dualread_4pilots_20261011.md`
- config: `WorkVault/Registries/EcosystemConfig.yaml`
- loader: `~/.hermes/lib/usertools_config.py`
