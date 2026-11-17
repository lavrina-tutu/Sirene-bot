# Gateway diagnostics

Follow [SKILL.md](../SKILL.md). Sasha decides whether to restart the gateway and performs any approved restart from an external shell; never restart it from an agent or cron job.

## Unresponsive gateway

If the Telegram bot does not respond, inspect Linux (VM) status:

```bash
systemctl --user status hermes-gateway.service --no-pager | head -10
```

If `failed` or `inactive`, diagnose and inform Sasha. After Sasha decides to restart, the external-shell command is:

```bash
systemctl --user restart hermes-gateway.service && sleep 3 && systemctl --user status hermes-gateway.service --no-pager | head -5
```

On Windows, check whether the process exists:

```bash
wmic process get ProcessId,CommandLine 2>/dev/null | grep "gateway run"
# An empty result indicates that the gateway has stopped.
```

Check recent activity and errors:

```bash
tail -30 ~/.local/share/hermes/logs/gateway.log   # Windows
tail -30 ~/.hermes/logs/gateway.log                # Linux
tail -20 ~/.local/share/hermes/logs/errors.log
```

Typical symptoms:

- `HTTP 403: Request not allowed`: Anthropic API rejected the request (limit, invalid key, or temporary block); the gateway may remain running while the session stops.
- Three consecutive `APITimeoutError` events followed by `API call failed after 3 retries`: unstable network or overloaded API; the process may eventually stop.
- `[MEMORY] rss=...` entries stop: the process may have died.
- `Gateway runtime lock is already held`: a cron job may have started a second gateway; see [gateway-crash-history.md](gateway-crash-history.md).

## SIGTERM and shutdown diagnosis (Linux)

A SIGTERM from systemd or another process starts a 180s drain. If an agent remains active, the drain may time out and the gateway exits with code 1. `Restart=on-failure` should restart it but may fail when restart attempts are exhausted. Diagnose and inform Sasha; only Sasha decides on a manual restart.

If the cause is not visible in gateway.log, inspect `gateway-exit-diag.log`, which records date, ps auxf, pstree, loadavg and dmesg at SIGTERM:

```bash
# Date and time of SIGTERM:
grep -A1 "shutdown diagnostic" ~/.hermes/logs/gateway-exit-diag.log | grep "^20"

# Parent process (systemd, shell, or other):
grep "pstree of self" -A3 ~/.hermes/logs/gateway-exit-diag.log

# Check for OOM killer:
grep -i "oom\|killed" ~/.hermes/logs/gateway-exit-diag.log
```

`under_systemd=yes` with `parent_name=systemd` can indicate a reboot, `systemctl stop`, update or restart limit. Low loadavg and no OOM entries suggest an administrative rather than resource cause. Repeated SIGTERM at 1–10 minute intervals may exhaust systemd's `RestartAttempts` and leave the unit failed.

```bash
cat ~/.config/systemd/user/hermes-gateway.service | grep -E "Restart|StartLimit"
```

Log example:

```text
Received SIGTERM — initiating shutdown
Gateway drain timed out after 180.0s with 1 active agent(s); interrupting remaining work.
Exiting with code 1 (signal-initiated shutdown without restart request)
```

Where `journalctl --user` is unavailable without adm/wheel privileges, read the log directly:

```bash
tail -60 ~/.hermes/logs/gateway.log
```

## Crash chronology

```bash
# 1. Find the crash time:
grep -n "runtime lock\|ERROR\|Exiting" logs/gateway.log | tail -20

# 2. Check agent.log around the crash (substitute the time ±5 minutes):
grep -n "2026-MM-DD HH:[23][0-9]:" logs/agent.log | grep -E "cron_|terminal|gateway" | tail -30

# 3. Check exit-diag.log for a clean exit or hard kill:
# Clean exit: atexit.hook with sys_exc=(None, None, None)
# Hard kill: no entry
tail -10 logs/gateway-exit-diag.log
```

For an approved Windows restart, Sasha can run externally:

```bash
wscript.exe "C:\Users\<USER>\AppData\Local\hermes\gateway_hidden.vbs"
sleep 8
tail -5 ~/.local/share/hermes/logs/gateway.log
```

After a VPN interruption, inspect logs and `cronjob(action='list')` before running anything, to avoid repeating a completed job. A subagent without explicit restrictions may damage `.env` or delete contacts.enc.

See `references/gateway-telegram-notifications.md` for the code walkthrough and notification handling, `references/cronjob-vs-delegate-task.md` for delegation decisions, and `references/telegram-group-chat-setup.md` for group filters and diagnostics. Use the gateway.log technique and `reply_to_id` to map topic names to thread IDs.

## Historical context

A GitHub autosync was once run again after VPN recovery before its logs were read; check the job status first.
