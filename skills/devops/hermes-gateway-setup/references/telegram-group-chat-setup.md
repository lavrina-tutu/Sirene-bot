# Telegram Group Chat Setup — Debug Notes

## Three levels of group filtering

```text
Telegram Bot API → polling → adapter.py
                                 ↓
                    [1] Bot Privacy Mode
                        can_read_all_group_messages
                        (configured in @BotFather)
                                 ↓
                    [2] _telegram_allowed_chats()
                        config.yaml: telegram.allowed_chats
                        .env: TELEGRAM_ALLOWED_CHATS
                        (empty = no DM restrictions)
                                 ↓
                    [3] _telegram_group_allowed_chats()
                        .env: TELEGRAM_GROUP_ALLOWED_CHATS
                        (separate group allowlist)
                                 ↓
                    Silent drop without a log if rejected
```

## Why `getUpdates` may be empty

Gateway long polling consumes updates and advances the offset. Do not run a competing `getUpdates` request against a running poller. Use existing data and logs; only Sasha decides on a gateway restart, under [SKILL.md](../SKILL.md).

## Why group messages may not reach gateway.log

Filtering occurs before `inbound message:` is logged, so rejected group messages may leave no error. In `plugins/platforms/telegram/adapter.py` around line 5884:

```python
if not allowed or chat_id_str not in allowed:
    return False  # silently dropped, no log
```

## Check Privacy using getMe

```bash
TOKEN=$(grep TELEGRAM_BOT_TOKEN ~/.config/hermes/.env | cut -d= -f2)
curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | python3 -m json.tool
```

Do not print the token. `"can_read_all_group_messages": true` means Privacy is disabled; `false` means it is enabled and the bot sees only mentions.

## Troubleshoot a silent bot

1. Check `getMe` → `can_read_all_group_messages` and BotFather Privacy Mode.
2. Check `TELEGRAM_ALLOWED_CHATS` and `TELEGRAM_GROUP_ALLOWED_CHATS` in the effective `.env` and `telegram.allowed_chats` in the effective `config.yaml`.
3. Obtain the group ID from `tutu-telegram-delivery/references/sirene-workspace-topics.yaml`; set the appropriate allowlists without opening access to everyone.
4. Configuration changes affect disk first. If needed, explain to Sasha that manual application requires his decision and external-shell restart; verify actual messages afterward.

> Context (RU): Сирень Workspace

Example group allowlist entry:

```env
TELEGRAM_GROUP_ALLOWED_CHATS=<group_id>
GATEWAY_ALLOW_ALL_USERS=false
```

## Historical extract from the original SKILL.md (not instructions)

Do not execute the historical stop, restart, open-access, or concurrent `getUpdates` recipes below. Current restrictions and canonical addresses are in [SKILL.md](../SKILL.md). Commands are preserved as evidence of earlier procedures.

## Telegram: connecting group chats

### Historical checklist for a silent bot

All three filters must permit the group:

| Level | Where | Check |
|---|---|---|
| 1. Bot Privacy | @BotFather | `can_read_all_group_messages` should be `true`; otherwise the bot sees only @mentions. Check with `curl .../getMe`. |
| 2. `TELEGRAM_ALLOWED_CHATS` | `.env` + `config.yaml` | Both empty or containing the group ID; `config.yaml: telegram.allowed_chats: ''`. |
| 3. `TELEGRAM_GROUP_ALLOWED_CHATS` | `.env` | Separate group allowlist, needed for the group to receive responses rather than only be observed. |

### Historical Privacy Mode procedure

1. @BotFather → `/mybots` → select the bot.
2. `Bot Settings` → `Group Privacy` → **Turn off**.
3. The old recipe used `systemctl --user restart hermes-gateway.service`; follow the current manual restart rule instead.
4. Check `curl -s "https://api.telegram.org/bot${TOKEN}/getMe" | python3 -m json.tool | grep can_read`; expect `"can_read_all_group_messages": true`.

### Historical method for finding a group chat ID

Long polling consumes updates; filtered messages may be dropped before logging. The old method stopped the gateway, wrote to the group, obtained updates and started it again. It is retained only as history:

```bash
# 1. Stop the gateway
systemctl --user stop hermes-gateway.service

# 2. Receive updates (write to the group AFTER this command)
TOKEN=$(grep TELEGRAM_BOT_TOKEN ~/.config/hermes/.env | cut -d= -f2)
curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates?limit=50" | python3 -c "
import json, sys
data = json.load(sys.stdin)
chats = {}
for u in data.get('result', []):
    for key in ['message', 'my_chat_member', 'chat_member']:
        if key in u:
            c = u[key].get('chat', {})
            if c.get('id'): chats[c['id']] = c
for cid, c in sorted(chats.items()):
    print(f'ID: {cid}  type: {c.get(\"type\")}  name: {c.get(\"title\") or c.get(\"first_name\",\"\")}')
"

# 3. Start the gateway again
systemctl --user start hermes-gateway.service
```

### Historical group configuration example

After obtaining an ID such as `-1001234567890`, the original recipe used:

```bash
# In .env:
TELEGRAM_GROUP_ALLOWED_CHATS=-1001234567890
TELEGRAM_ALLOWED_CHATS=-1001234567890   # if response filtering is needed

# In config.yaml:
# telegram.allowed_chats: '' (empty = no restrictions)
```

The old instructions then restarted the gateway and sent a group message. Apply current authority and restart boundaries instead.

### Code locations

- `plugins/platforms/telegram/adapter.py`: `_telegram_allowed_chats()` around line 5567 reads `config.extra["allowed_chats"]` or `TELEGRAM_ALLOWED_CHATS`.
- `_telegram_group_allowed_chats()` around line 5582 reads the separate `TELEGRAM_GROUP_ALLOWED_CHATS`.
- `_telegram_observe_allowed_chats()` around line 5591 combines both lists.
- Around line 5884, `if not allowed or chat_id_str not in allowed: return False` silently drops groups.

## Historical procedure for adding a Telegram group

Group messages may be filtered before `gateway.log`, so `tail -f gateway.log` alone may not reveal the ID. The former procedure temporarily allowed all chats:

```bash
# ~/.config/hermes/.env
GATEWAY_ALLOW_ALL_USERS=true
```

It then restarted the gateway from a separate terminal:

```bash
systemctl --user restart hermes-gateway.service
```

The old instructions noted that a gateway process cannot restart itself. They then sent a group message and inspected:

```bash
tail -f ~/.hermes/logs/gateway.log | grep "inbound message"
# Look for: chat=-1001234567890
```

The discovered negative group ID was added to the allowlist and open access turned back off:

```bash
# ~/.config/hermes/.env
TELEGRAM_ALLOWED_CHATS=400307920,-1001234567890
GATEWAY_ALLOW_ALL_USERS=false   # restore
```

The historical procedure ended with another external-terminal restart. Do not open access to everyone for diagnostics; Sasha decides whether to restart.

### Historical alternative: direct Telegram API

The previous instructions said this works only while the gateway is stopped, because polling consumes updates. Do not use it concurrently with the running poller:

```bash
source ~/.config/hermes/.env
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates?limit=100&offset=-100" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
chats = {}
for u in data.get('result', []):
    for key in ['message', 'my_chat_member', 'chat_member']:
        if key in u:
            c = u[key].get('chat', {})
            if c.get('id'): chats[c['id']] = c
for cid, c in sorted(chats.items()):
    print(f'ID: {cid}  type: {c.get(\"type\")}  name: {c.get(\"title\") or c.get(\"first_name\",\"\")}')
"
```

## Telegram forum topic thread IDs

Hermes uses a separate session per forum topic: `agent:main:telegram:group:<chat_id>:<thread_id>`. The historical notes report that `state.db` (`sessions.handoff_state`, `system_prompt`, `user_id`) and `session_search` metadata did not expose the thread ID; a running gateway consumed `getUpdates`.

### Correlating gateway.log

A `Flushing text batch` log line includes the session key and thread ID:

```
[Telegram] Flushing text batch agent:main:telegram:group:-1004300127777:**5** (16 chars)
```

The `inbound message` line can show `reply_to_id` as well. Preserved log example:

> Context (RU): `inbound message: ... msg='топик WorkVault' reply_to_id=**5** reply_to_text=''`

Historical extraction commands:

```bash
grep "Flushing text batch" ~/.hermes/logs/gateway.log \
  | grep -oP "group:-\d+:(\d+)" \
  | sort -t: -k2 -n | uniq
# Output: group:-1004300127777:1, :3, :5, ...
```

```bash
grep -E "Flushing text batch|inbound message" ~/.hermes/logs/gateway.log \
  | grep -v "reply_to_id=None"
# In a pair of lines: thread ID from the batch key and message content from inbound
```

The old initial mapping procedure was to write the topic name in each topic and correlate the message with `reply_to_id` in `gateway.log`, then save the mapping. The canonical source is now `tutu-telegram-delivery/references/sirene-workspace-topics.yaml`; logs are diagnostic evidence only.

> Context (RU): Сирень Workspace

### Historical topic mirror (chat=-1004300127777)

The notes identify the canonical topic list as `tutu-telegram-delivery` / `references/sirene-workspace-topics.yaml` and restore script `scripts/restore_telegram_topics.sh`. They describe seven canonical topics, exclude Hermes DEV :4 and :6556, and place Errors=`11112` outside the top group. The table below is a historical mirror, not the canonical list; Hermes DEV :4 was removed from the canon on 16.09.2026, CHANGE `telegram-topics-remove-hermesdev`. Do not extend this table.

| Topic | Thread ID | Deliver target |
|---|---|---|
| General | 1 | `telegram:-1004300127777:1` |
| Tools | 3 | `telegram:-1004300127777:3` |
| WorkVault | 5 | `telegram:-1004300127777:5` |
| Backlog | 6 | `telegram:-1004300127777:6` |
| Monitoring | 7 | `telegram:-1004300127777:7` |
| Personal | 8 | `telegram:-1004300127777:8` |

### Historical config.yaml/.env settings

```yaml
telegram:
  allowed_chats: '400307920,-1004300127777'
  require_mention: false
  guest_mode: false
```

The notes say BotFather Group Privacy was disabled to let the bot see all group messages, and startup notifications were delivered to the DM (400307920) and General (thread=1) through `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS`. Verify current configuration and canonical destinations before using these historical values.
