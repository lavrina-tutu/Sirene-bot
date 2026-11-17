# Gateway crash diagnosis and history

Follow [SKILL.md](../SKILL.md). Never run `hermes gateway run/stop/restart`, `schtasks /Run /TN "Hermes_Gateway"`, or any command that can create a second gateway from a cron job. Sasha decides whether to restart the gateway and performs an approved restart from an external shell. Do not create cron jobs without explicit instruction.

## Diagnosing a cronjob crash (Windows)

`Gateway runtime lock is already held by another instance. Exiting.` in gateway.log followed by loss of the main gateway and no atexit entry can indicate a cron job started a competing gateway. A direct `schtasks /run /tn Hermes_Gateway` can trigger `gateway run --replace` and `taskkill /F` against the live PID, followed by a race for the lock.

```bash
# Recent gateway events
tail -30 /c/Users/tkachenkoav/.local/share/hermes/logs/gateway.log

# Check for atexit (clean exit) versus hard kill
tail -20 /c/Users/tkachenkoav/.local/share/hermes/logs/gateway-exit-diag.log

# Cronjob activity at the time of the crash
grep "cron_<JOB_ID>" /c/Users/tkachenkoav/.local/share/hermes/logs/agent.log | tail -30
```

An `atexit.hook` entry indicates a clean exit, such as the lock race loser; absence can indicate a hard `TerminateProcess` kill. Find the responsible job and inspect the preceding five minutes:

```bash
grep -n "runtime lock is already held" logs/gateway.log
grep -n "2026-MM-DD HH:2[0-9]:" logs/agent.log | grep -E "(terminal|gateway)"
```

Example:

```text
23:26:09 ERROR gateway.run: Gateway runtime lock is already held by another instance. Exiting.
[cron_XXXXX] run_agent: tool terminal completed ... (contains "hermes gateway" or "schtasks /Run")
```

Include an explicit prohibition in diagnostic cron prompts:

```text
🚫 ABSOLUTE PROHIBITION: do not run hermes gateway run/stop/restart or schtasks /Run.
A violation can bring down the gateway and wake the user. READ + code edits only.
```

If a cron job causes a gateway crash, remove the offending job (`cronjob action=remove`) before further investigation; do not wait for a recurrence. Guards are not a substitute for this prohibition: a direct `schtasks /Run /TN "Hermes_Gateway"` creates a process that does not inherit `HERMES_CRON_SESSION` and can bypass the guard. Task Scheduler recovery depends on its actual configuration; do not assume it will recover automatically.

## Crash recovery and cron checks

Never create cron jobs using `restart_gateway_MANUAL_ONLY.sh`: a no_agent restart script runs within the gateway and systemd can kill its parent, causing a SIGTERM loop.

1. Diagnose the failure and report it briefly to Sasha.
2. Ask whether to bring it up and wait for explicit approval.
3. After approval, Sasha runs `bash ~/.hermes/scripts/restart_gateway_MANUAL_ONLY.sh` from an external shell.
4. No cron, no no_agent and no automated restart.

A `cronjob` does not see the conversation: include paths and restrictions in its prompt. Per-platform `notifications` overrides global `display.streaming` independently. Before reporting a cron job's status or identifying a report, check `cronjob(action='list')`, `ls -t cron/output/*/`, `ls cron/output/<job_id>/` and the latest `agent.log` lines; read the output instead of guessing.

A VPN interruption can produce `RuntimeError: Request timed out or interrupted` through loss of Anthropic API connectivity rather than a gateway bug. Check `cronjob(action='list')`, identify jobs with `last_status=error` and `enabled=true` (not paused), and, when authorized, run them one at a time, waiting for each to finish. Check `ls -t cron/output/<id>/*.md` for a new file with today's date and size >500 bytes. Do not run multiple Opus jobs concurrently.

## Historical context

### Guard and VBS fixes (29.05.2026)

The crash pattern involved `schtasks /run /tn Hermes_Gateway` → `gateway run --replace` → `taskkill /F` of the live PID without atexit → the new instance losing the lock race, leaving both dead.

1. `hermes_cli/gateway.py::_guard_against_cronjob_context()` exits via `sys.exit(2)` when `HERMES_CRON_SESSION=1` and `HERMES_ALLOW_GATEWAY_FROM_CRON=1` is absent, before lock operations in `run_gateway`.
2. `gateway/run.py` adds a defense-in-depth guard in `start_gateway()`, returning `False` before `acquire_gateway_runtime_lock()` and `terminate_pid()`.
3. `gateway_hidden.vbs` changed from `bWaitOnReturn=False` to `bWaitOnReturn=True` with `WScript.Quit(code)`, allowing Task Scheduler to see the exit code and apply configured RestartOnFailure (`Count=3`, `Interval=PT1M`). The VBS fix was intended to enable recovery within ≤1 minute when configured; direct schtasks remains a guard bypass.

`tests/gateway/test_cronjob_gateway_guard.py` contains five tests for the CLI and `start_gateway()` guards. An earlier note stated Task Scheduler's restart-on-failure was not configured by default; inspect the actual task rather than assuming either state.

### delegate_task crash and bk-115

Before April–June 2026, `delegate_task` with Opus (`reasoning_effort=high`, `child_timeout=1200`) could hold the parent stream until `Subagent stale (no progress 15 cycles)` and `Stream stale 180s`, followed by gateway failure. The old Opus-only-through-cronjob rule was a workaround.

In hermes-agent v0.18.0+, upstream `0cc63043e` raised heartbeat thresholds from idle 150→450s and in-tool 600→1200s; `bba9b519a` (June, #45149) changed default `child_timeout_seconds` from 600→0. During the bk-115 VM pilot (06.07–13.07.2026), `child_timeout_seconds` was 1800 and there were zero crashes/SIGTERM/stale events. On 13.07.2026 it was set to `child_timeout_seconds: 0` and bk-115 was closed in dialog-backlog.md.

From 13.07.2026, the recorded general guidance permitted Opus through `delegate_task` or `cronjob(repeat=1)`: the former for parallel work needing current session context, the latter for self-contained work or work surviving session closure. Current workflow and explicit cron authorization restrictions still apply. The recorded config was:

```yaml
delegation:
  model: claude-sonnet-5   # default; pin Opus per call if needed
  provider: anthropic
  reasoning_effort: medium
  max_iterations: 50
  child_timeout_seconds: 0   # no limit; matches upstream default
  max_concurrent_children: 3
```

The restart-script SIGTERM loop occurred on 26.06.2026. An older one-shot cron note recommended 2–5 minutes after scheduling instead of `action=run` because configuration was lost; check current behavior and obtain explicit authorization before creating any cron.
