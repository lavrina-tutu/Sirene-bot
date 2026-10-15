# Evidence — wave1 protocol_from_summary (eco-config-w1 HF:test)

Generated: 2026-10-11 19:00   |  Task: t_91cc435c (HF:test)  |  Role: испытатель

## 1. `explain protocol_from_summary` (each non-secret key -> YAML; zero legacy/overlay in migrated set)

Output (stdout of `python3 /home/tkachenkoav/.hermes/lib/usertools_config.py explain protocol_from_summary`):

```
ANTHROPIC_API_KEY source=shared_env
CONFLUENCE_URL source=shared
CONTACTS_ENC source=ecosystem_config
CONTACTS_ENCRYPTION_KEY source=shared_env
ENTITIES_REGISTRY_PATH source=ecosystem_config
FIREFLIES_API_KEY source=shared_env
GATEWAY_ALLOW_ALL_USERS source=shared_env
LOOP_TOKEN source=shared_env
MEETINGS_DIR source=ecosystem_config
OWNCLOUD_APP_TOKEN source=process_env
OWNCLOUD_URL source=process_env
OWNCLOUD_USER source=process_env
OWNCLOUD_WEBDAV_URL source=process_env
PREPARED_PROTOCOLS_DIR source=ecosystem_config
ROOMS_MD source=ecosystem_config
STATE_DIR source=ecosystem_config
TAVILY_API_KEY source=shared_env
TELEGRAM_ALLOWED_CHATS source=process_env
TELEGRAM_ALLOWED_USERS source=shared_env
TELEGRAM_ALLOW_ALL_USERS source=shared_env
TELEGRAM_BOT_TOKEN source=shared_env
TELEGRAM_EXCLUSIVE_BOT_MENTIONS source=process_env
TELEGRAM_HOME_CHANNEL source=shared_env
TELEGRAM_NOTIFY_CHAT_ID source=ecosystem_config
TELEGRAM_NOTIFY_TARGET source=ecosystem_config
TELEGRAM_NOTIFY_THREAD_ID source=ecosystem_config
TELEGRAM_REQUIRE_MENTION source=process_env
TUTU_DOMAIN_PASSWORD source=shared_env
WORKVAULT_PATH source=shared
enabled source=ecosystem_config
llm source=hermes_llm

```

Migrated-set verdict: `source=legacy`/`source=overlay` lines excluding
non-migrated shared-env/other-tool dump = **0** (fully-expected items
listed below explain; no business/migrated key resolves legacy/overlay).

## 2. ErrorBus — config/env/yaml/missing events

Count (tools=['ProtocolFromSummary', 'protocol_from_summary', 'a6e62d06249f', '21255143c523']): **0**  →  **PASS (0 no-new-config events)**

## 3. Boot-times / real-cycle (> =3 ticks or 1 working day or real call)

cron: 2 job ids a6e62d06249f (pfs_batch) / 21255143c523 (pfs_notify). Last runs 2026-10-09 pre-migration; post-migration weekday runs accrue from Mon.

Note: migration dual_read landed 2026-10-11T00:00:00 (Sunday).
FF/MFF/PFS crons are weekday-gated; post-migration >=3 consecutive ticks to be
collected in the Mon 9-19 window (plan HF-plan_wave1 Q-1) — not fabricatable now.

## 4. Real runtime smoke (not dry-run)

`load_tool_config("protocol_from_summary", keys=<migrated set>)` resolved without KeyError;
values populated from ecosystem_config/shared (see pytest IAC-05/07/09/11).
ConfluenceSync/PFS: `source=shared_env` for CONFLUENCE_TOKEN expected AFTER
ORCH adds it to shared .env (IAC-03, sequencing in HF-plan §Sekvencing).

## 5. Artifacts / links

- plan: `TZ/EcosystemIntegration/HF-plan_wave1_dualread_4pilots_20261011.md`
- config: `WorkVault/Registries/EcosystemConfig.yaml`
- loader: `~/.hermes/lib/usertools_config.py`
