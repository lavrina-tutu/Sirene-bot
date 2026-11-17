---
name: hermes-gateway-setup
description: "Настройка и диагностика Hermes Gateway и платформ"
version: 1.3.3
author: agent
tags: [hermes, gateway, telegram, discord, slack, messaging, setup, windows]
platforms: [linux, macos, windows]
---

# Hermes Gateway: setup and operation

Configure Hermes Gateway connections to platforms and check delivery, configuration, routing, and process health. Upstream update analysis, business-tool repair, and development process management follow their respective separate procedures.

## Scope and authority

- From the gateway, its cron, or a child process, **do not start a second gateway or run stop/restart, `schtasks /Run`, or a restart script**. If the gateway fails, identify the cause and notify Sasha; after consent, Sasha runs `~/.hermes/scripts/restart_gateway_MANUAL_ONLY.sh` personally from an external shell. Do not create a restart cron.
- After changing startup configuration or `.env`, explicitly state: **the disk has changed, but the runtime is still unchanged**. Applying the configuration to the runtime requires a separately permitted manual restart; a new session alone does not replace it.
- Do not create cron jobs automatically. For background work, explicitly set the executor's access boundaries for `.env` and contact stores. Include an explicit prohibition on gateway run, stop, restart, and `schtasks /Run` in cron prompts; do not rely on guards alone, because scheduled-task launches can bypass the cron environment guard.
- Do not automatically allow everyone access for diagnostics. Do not issue a concurrent `getUpdates` request against the token of a running poller.
- The gateway listens on `0.0.0.0:9119`; the firewall must allow that port **only** from the VPN subnet `10.254.0.0/16` and loopback. Do not open port 9119 externally, and verify an external connection is blocked after any firewall change. This network contract (`10.254.0.0/16`, loopback) is mandatory; never broaden it without Sasha's explicit approval.

## Platform setup and verification

1. `hermes gateway setup` is available for initial setup; start and install the service only outside the running gateway and within the permitted procedure. Check status with `hermes gateway status`, the system service, and logs.
2. For Telegram, create a bot via @BotFather; check that `TELEGRAM_BOT_TOKEN` is present and that the platform is enabled in the configuration actually in use. Do not print the token. Specify allowed users and chats in the appropriate allowlists.
3. If a platform did not start, check token and enabled in the environment visible to the process at startup. If messages are rejected, check allowlists; do not expand access to everyone by default.
4. Check the connection and actual receipt of a message, not just startup status. Discord requires Message Content Intent; Slack requires the appropriate app/bot tokens and event subscription; Email requires the appropriate credentials. Platform details: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/.
5. Session commands `/help`, `/new`, `/model`, `/status`, `/sethome` help manage the session. A missing home channel message means the cron delivery address has not yet been set; `/sethome` assigns the current chat. `/restart` does not override the prohibition on self-restart.

### Telegram groups and topics

For incoming group messages, check all three filtering levels:

1. Bot Privacy Mode in @BotFather and `can_read_all_group_messages` via `getMe`.
2. `TELEGRAM_ALLOWED_CHATS` and `telegram.allowed_chats` in the `.env`/YAML actually in effect.
3. The separate `TELEGRAM_GROUP_ALLOWED_CHATS` for groups.

A rejection at any level may not appear in gateway.log. Use existing data and logs; do not start a concurrent poller. Take the group names, chat ID, and thread ID only from `tutu-telegram-delivery/references/sirene-workspace-topics.yaml`, not old tables. For diagnostics, correlate the session key `agent:<profile>:telegram:group:<chat_id>:<thread_id>` and `reply_to_id` in gateway.log; logs are not themselves the canonical source of names.

> Context (RU): Сирень Workspace

For filtering details and the archive of old connection methods, see [telegram-group-chat-setup.md](references/telegram-group-chat-setup.md).

### Profile routing

For `gateway.profile_routes`, check `gateway.multiplex_profiles: true`, the platform/chat/thread match, and the existence of the profile and its model (`hermes profile list`). Settings are read at startup; after permitted application, check a **new** session because the old one may remain on the previous profile. In gateway.log, compare `agent:<profile>:telegram:...` with the expected key; `agent:main:...` indicates the main profile, but confirm the cause against configuration and runtime state. For YAML and diagnostic examples, see [profile-routing.md](references/profile-routing.md).

## Operating conditions

- On Windows, check the actual `.venv` path in the service wrapper. For VBS, check `bWaitOnReturn=True` and propagation of the exit code through `WScript.Quit(code)`; the old example with `False` is not a current recipe. Before overnight work, check sleep/hibernate: screen locking and sleep have different effects. For HKCU Run, schtasks/Python, XML, and powercfg, see [windows-service-setup.md](references/windows-service-setup.md); for `.env` editing, see [windows-env-editing.md](references/windows-env-editing.md). All start and restart operations are subject to the boundaries above.
- If the startup notification is absent, check polling health and `send_path_degraded` in gateway.log: absence of the notification alone does not prove the process has failed. For the race history and checks, see [startup-notification-race.md](references/startup-notification-race.md).
- Use the supported `display.runtime_footer`; do not document `runtime_header` as a working key. `display.platforms.telegram.notifications: important` makes intermediate messages silent in Telegram; other platforms may use their own settings. See [gateway-telegram-notifications.md](references/gateway-telegram-notifications.md).
- For `no_agent`, check the job's actual `deliver` field: a script comment or docstring does not set the address. Check credentials and environment in the exact execution context where cron runs: an ordinary shell and a subprocess may see different variables. Previous `gh` authorization does not prove authorization in a new cron session. See [cron-environment.md](references/cron-environment.md).
- Confirm job status using the registry, fresh output, and the log. After a network failure, first establish whether the job actually completed, so that an already completed task is not run again. The source contains a conflict between advice to use `action=run` and a warning about losing configuration; until the current runner is checked, do not treat either recipe as universal.
- When working with `HERMES.md`, preserve case and check the actual load path: on a case-sensitive filesystem, `hermes.md` and `HERMES.md` are different files.
- When delivering a file, request confirmation that the attachment itself was received; provide its absolute path as a fallback. A successful send response does not prove actual receipt. For the mechanism and known failures, see [file-delivery.md](references/file-delivery.md).

## Diagnostics

1. Check process/service status (`systemctl --user status hermes-gateway.service` on Linux), last activity time, and recent gateway/agent/error logs in the actual profile directory. If the bot does not respond, distinguish an API or network error from a stopped process.
2. For SIGTERM, correlate gateway.log and gateway-exit-diag.log, timing, parent process, drain timeout, OOM indications, and systemd restart limits. On Windows, check the process, venv, and wrapper exit code. For chronology and commands, see [gateway-diagnostics.md](references/gateway-diagnostics.md).
3. For `Gateway runtime lock is already held`, correlate the event time with cron activity and the presence of a second process; do not attempt to resolve it by starting another gateway. For guard/VBS history, see [gateway-crash-history.md](references/gateway-crash-history.md).
4. For delivery to the wrong topic, compare the actual `deliver` with the canonical YAML; for a group response problem, check all three filters and then the incoming message and reply in the correct group/topic.
5. After changes, distinguish checking files on disk from checking the running process. If a manual restart is required, tell Sasha why and what to check afterward.
6. Before reporting a cron job as pending or completed, check its registry entry, latest `cron/output/<job_id>/` and recent `agent.log`; do not infer status from the conversation. After a network interruption, check whether work completed before attempting any authorized retry.
7. If a cron job causes a gateway crash, stop its recurrence within the authorized scope and investigate. Explain the failure to Sasha; await his explicit decision, and only Sasha may run `bash ~/.hermes/scripts/restart_gateway_MANUAL_ONLY.sh` from an external shell.

For the historical choice between cron and delegation, see [cronjob-vs-delegate-task.md](references/cronjob-vs-delegate-task.md); current cron restrictions and the development route are determined by the current profile and dev-workflow.
