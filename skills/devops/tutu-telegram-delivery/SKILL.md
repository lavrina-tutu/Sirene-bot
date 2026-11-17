---
name: tutu-telegram-delivery
description: "Доставка в группы ТУТУ: топики, бот, маршрутизация"
version: 1.4.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [telegram, tutu, group, delivery, bot, errorbus]
    related_skills: [hermes-gateway-setup, hermes-feature]
---

# Tutu Telegram Delivery

## Scope and target

Use for routing and verifying delivery to the «Сирень Workspace» Telegram group from USERTOOLS, error buses and cron wrappers, or diagnosing inbound group replies. General gateway lifecycle and general cron diagnosis belong to their own skills. Resolve every destination against the **sole topic ID canon** `references/sirene-workspace-topics.yaml`: it contains eight topics, including Messages `6556` and Errors `11112`. Deleted `:2` and `:4` must not be used. Take human-readable topic names from the YAML; do not promise to obtain them from getChat/getUpdates.

Before an authorized send verify bot identity and the actual chat/thread where the message landed. An invalid thread may silently fall back to General despite `ok:true`; that response alone is not proof of the intended topic. Use `TELEGRAM_BOT_TOKEN` for group delivery and compare identity with the gateway token; the historical bot mismatch is explained in `references/delivery-incident-history.md`. Do not expose tokens.

## Delivery and restoration

The established interface is:

```bash
bash ~/.hermes/skills/devops/tutu-telegram-delivery/scripts/restore_telegram_topics.sh apply|check|dry-run
```

`dry-run` compares snapshot and disk without writing. `apply` backs up three files, sets YAML `telegram.allowed_chats`, `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS`, aligns YAML token to `TELEGRAM_BOT_TOKEN` and sets YAML extras; it does not write `TELEGRAM_ALLOWED_CHATS` into `.env`. `check` tests disk against the snapshot and its YAML allowlist; it does not check an env-over-YAML shadow. Do not edit `.env` or `config.yaml` by hand as a substitute for this interface. Preserve both restore scripts and their CLI modes. Full modes, backup and disk/runtime distinction: `references/routing-restore.md`.

After an authorized apply separately record disk and running gateway state. The gateway reads token/allowlist at startup, so disk changes do not establish runtime state. Restart is a separate action requiring Sasha's explicit authorization; the restore script does not restart it.

Distinguish cron `deliver` (the actual jobs configuration supplies the business target) from direct HTTP error-channel delivery; a script comment is not an address. For technical errors avoid `parse_mode` unless the content is correctly escaped. For a specifically authorized live smoke, verify bot with `getMe`, send to the canonical target and inspect actual delivery, including attachments where relevant. Full procedure: `references/delivery-verification.md`.

## Inbound diagnostics

- Inspect effective allowlist sources manually, including both relevant `.env` files and YAML: env may shadow YAML. `restore ... check` alone cannot detect this. Never print token or secret values.
- Confirm bot identity and group membership, then use process, service and log evidence for the poller. Do **not** run competing `getUpdates` against a live poller. Check gateway logs for polling conflict and inbound evidence.
- Distinguish `hermes-gateway.service` (Telegram poller) from `hermes-serve.service` (dashboard); do not treat serve environment as poller state.
- Outbound send success proves neither inbound processing nor a reply. Verify incoming message and answer in the same group/topic when authorized. Diagnostic detail and historical obsolete recipe: `references/telegram-inbound-diagnostics.md`.
- If a background task is unfinished before `/new`, save a handoff with task, paths and next step. Obtain status from actual process/results; history: `references/delivery-incident-history.md`.

## Verification

- Resolve target and names against the canonical YAML; check actual chat/thread and attachment, not only API status.
- Record bot identity, disk and runtime separately; investigate env shadow and gateway process for inbound issues.
- Verify inbound and reply independently from outbound delivery. Do not run production sends, apply or restart just to validate documentation.
