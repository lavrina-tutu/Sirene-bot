# cronjob vs delegate_task — selection guide (updated 13.07.2026)

Current profile and dev-workflow restrictions take precedence over this dated guide: do not create cron jobs without explicit authorization, and do not use cron or delegation as an alternative dispatcher for a live DevWorkflow graph. See [SKILL.md](../SKILL.md).

## History of the problem (fixed upstream)

Before April–June 2026, heavy Opus `delegate_task` jobs caused gateway crashes:

```
Subagent 0 appears stale (no progress for 15 heartbeat cycles)
Stream stale for 180s — Killing connection
```

`reasoning_effort=high` and `child_timeout=1200` kept the parent HTTP stream open, falsely triggering heartbeat-stale detection. Upstream fixes in hermes-agent v0.18.0+:

- `0cc63043e` (April): heartbeat thresholds idle 150→450s, in-tool 600→1200s.
- `bba9b519a` (June, #45149): default `child_timeout_seconds` 600→0 (unlimited).

The bk-115 pilot, 06.07–13.07.2026, raised `child_timeout_seconds` to 1800 for a week with zero gateway crashes; on 13.07.2026 the limit was removed (`child_timeout_seconds: 0`).

## Selection rule as of 13.07.2026

Both tools were considered safe for Opus; select according to task context, subject to current restrictions.

| Criterion | cronjob | delegate_task |
|---|---|---|
| Needs current conversation context | No: write a complete, self-contained prompt | Yes |
| Must survive session closure | Yes | No: background work is lost on /new or process failure |
| Needs user feedback during execution | No | Yes, through the main chat |
| Schedule or repeat | Yes | No, one-shot call |
| Parallel tasks | Limited | Up to 3 (`max_concurrent_children`) |

## Example: self-contained cron job

Only create a cron when explicitly authorized; include the gateway command prohibitions and access boundaries required by [SKILL.md](../SKILL.md).

```python
cronjob(
    action='create',
    name='task-description',
    prompt='Complete self-contained prompt with context...',
    schedule='1m',           # minimum delay
    repeat=1,                # one-shot
    deliver='origin',        # reply to current chat
    model={'model': 'claude-opus-4-7', 'provider': 'anthropic'},
    enabled_toolsets=['file', 'terminal', 'skills']
)
```

## Example: delegate_task for parallel or conversational work

This historical configuration pins the model via `config.yaml` (not a field on the call):

```yaml
delegation:
  model: claude-opus-4-7   # temporary pin for a task requiring Opus
  provider: anthropic
  reasoning_effort: high
  child_timeout_seconds: 0   # unlimited; default at the time
```

Restore `delegation.model` to `claude-sonnet-5` after a temporary pin; otherwise later calls also use Opus. Gateway configuration is read at startup; apply changes only under the manual restart rule.

## Limitations

- cronjob has no conversation context or interactive feedback, starts after a minimum schedule delay of one minute, and can only be stopped with `cronjob(action='remove', job_id=...)`.
- delegate_task is not durable across `/new` or a process failure; model selection in this example is a global `config.yaml` pin affecting concurrent calls; it has no schedule or repeat.

## delegation configuration as of 13.07.2026

```yaml
delegation:
  model: claude-sonnet-5
  provider: anthropic
  reasoning_effort: medium
  max_iterations: 50
  child_timeout_seconds: 0   # unlimited, upstream default
  max_concurrent_children: 3
  max_spawn_depth: 1
```

## Historical extract from the original SKILL.md (not instructions)

Do not execute old recipes for self-stop, restart, open access, or concurrent getUpdates. Current restrictions and canonical addresses are in [SKILL.md](../SKILL.md).

### delegate_task → Gateway Crash Pattern (fixed upstream, bk-115 closed 13.07.2026)

Before April–June 2026, `delegate_task` with Opus (`reasoning_effort=high`, `child_timeout=1200`) held the parent stream open → `Subagent stale (no progress 15 cycles)` → `Stream stale 180s` → gateway crash. The rule “Opus only through cronjob” was a workaround.

Upstream fixes in hermes-agent v0.18.0+:

- `0cc63043e` (April): heartbeat thresholds increased, idle 150→450s and in-tool 600→1200s.
- `bba9b519a` (June, #45149): default `child_timeout_seconds` 600→0 (unlimited); a subagent fails on actual errors (API/tool/iteration budget), not a delegation timer.

During the bk-115 VM pilot, 06.07–13.07.2026, `child_timeout_seconds` was raised to 1800 for a week; there were zero crashes/SIGTERM/stale events. On 13.07.2026 the limit was removed (`child_timeout_seconds: 0`) and bk-115 closed in dialog-backlog.md.

The rule as of 13.07.2026 allowed Opus through either `delegate_task` or cronjob: `cronjob(repeat=1)` for a self-contained task or work surviving session closure; `delegate_task` for quick parallel work in the current session. Current profile restrictions supersede this historical guidance.

**Delegation config (`config.yaml`) at the time:**

```yaml
delegation:
  model: claude-sonnet-5   # default; pin Opus only when needed
  provider: anthropic
  reasoning_effort: medium
  max_iterations: 50
  child_timeout_seconds: 0   # unlimited, matching upstream default
  max_concurrent_children: 3
```
