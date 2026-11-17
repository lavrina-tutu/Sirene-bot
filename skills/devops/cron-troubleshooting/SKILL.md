---
name: cron-troubleshooting
description: «Диагностика сбоев и тишины cron Hermes»
version: 1.1.2
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cron, troubleshooting, no_agent, venv, sys.path, diagnostics]
    related_skills: [hermes-feature, hermes-ops]
---
# Hermes cron diagnostics

Identify the source of a cron failure or unexpected silence, including no_agent execution, venvs, delivery, and ErrorBus. This skill is for diagnosis: route complex defect fixes through the BUGFIX graph `BUG:diagnose` → `GATE:diagnose-review`; do not implement arbitrary fixes outside the authorized scope. Do not create test crons without the explicit instruction quoted below. Do not restart the gateway without Sasha's explicit permission. Distinguish business delivery from technical errors: empty stdout alone proves neither absence of business delivery nor failure.

> Context (RU): «ставь кроны»

## Diagnostic tree

1. Establish the profile, job ID, time, and actual entrypoint. If `HERMES_CRON_JOB_ID` is empty, match the registry `id` and `last_run_at` to the session time and output. Check `enabled`, schedule, `script`, `no_agent`, `workdir`, `last_status`, `last_run_at`, `last_error`, executions history, and output for the relevant profile. Record what was observed and when; use the job ID rather than a name alone to correlate records.
2. If a notification contradicts the active registry and multiplex is enabled, inspect every profile's registry. Identical names or IDs can refer to different model/provider, schedule, and deliver settings. Do not remove a working instance just because its name matches. Empty `claim job` entries are candidates for investigation; remove only confirmed redundant records within authorized scope. Compare their profile, prompt, skills and delivery before deciding that they are duplicates.
3. For import failures, inspect `sys.executable`, Python version, and `sys.path` of the actual cron interpreter; compare the import with the tool's own venv Python. A no_agent `.py` can run under the runner's Python instead of its shebang. A binary module error despite an installed package can indicate an ABI mismatch. For tools with binary dependencies, use the intended wrapper and the tool venv's Python; do not add a foreign `lib/pythonX.Y/site-packages`. Inspect all neighboring entrypoints with the same root cause. Run pytest using the relevant project's venv, not an unrelated system or Hermes interpreter; verify the interpreter and installed dependencies before drawing conclusions from an import failure.
4. For `Blocked: resolves outside scripts/`, inspect the resolved path and the intended wrapper within `~/.hermes/scripts/`. For exit 127, inspect the wrapper's internal dependencies. If it hides a traceback, inspect its inner command and, only when its side effects are authorized, reproduce it with the same env, venv, cwd, and flags. A bare exit code from a wrapper may conceal the actual traceback captured in a shell variable.
5. Evaluate empty output or `silent` against the script contract and neighboring results: it can be normal, for example when there are no new events. Compare recent output, status, and actual business delivery. Cron failure and ErrorBus delivery are separate paths. For silent-fail, avoid unnecessary intervention: first inspect existing evidence and the expected behavior, then act only on a demonstrated failure. Do not treat quiet operation alone as a reason to change a script, create a cron, or restart the gateway.
6. For HTTP 400 `model not allowed`, verify the actual slug and provider. Reasoning effort is a separate parameter, not automatically a model suffix. Determine per-cron effort availability from current code/API, not historical assumptions. Do not send an external verification request without authorization.

For profile, registry, executions, and reproduction, see [cron-diagnostic-recipes.md](references/cron-diagnostic-recipes.md). For ABI and neighboring entrypoints, see [cron-venv-abi.md](references/cron-venv-abi.md). For paths, exit 127, and tracebacks, see [cron-script-paths.md](references/cron-script-paths.md). For model verification, see [model-reasoning-verification.md](references/model-reasoning-verification.md).

## ErrorBus and recovery

Compare event `last_seen` with the latest cron results: an old open event alone does not prove a current failure. If events concern old runs, inspect the reconcile dry-run, its `created` count, and deduplication; preserve detection of fresh errors and do not mask the problem by restarting the gateway. After recovery, verify auto-resolve against current code and actual results. Manual resolve is an authorized exception that preserves history, not event deletion. If old failures are recreated, investigate reconcile independently of the script and preserve monitoring of new failures.

**Unresolved contradiction in the source:** a historical analysis dated 27.08.2026 claims there is no auto-resolve; another entry from the same day claims it was implemented in ErrorBus v0.3.0. Confirm the status of the specific installation from code and behavior. See [errorbus-diagnostics.md](references/errorbus-diagnostics.md).

## Verification and result

A manual run is allowed only when its side effects are authorized. After a fix, verify the actual cron path and delivery within the existing authorization, using existing results or an authorized check. **Unresolved contradiction in the source:** `hermes cron run` is described both as unreliable under multiprofile and as a verification method. Confirm its applicability against current code and environment; do not assume it is reliable. A one-off cron does not bypass the prohibition on creating schedules.

Report the profile and job ID, time, entrypoint, observed status/output, root cause or remaining uncertainty, interpreter and dependencies checked, ErrorBus state, and verification result. The formerly absent `scripts/diagnose_exchange.py` is not an available resource of this skill. Separate historical files promised by the source are absent; surviving information was moved into the references above, and full recovery has not been confirmed.

When assessing evidence, distinguish a runner status from the result of the business operation. An agent cron and a no_agent cron have different execution paths: identify which one ran before choosing interpreter and delivery checks. For no_agent, inspect the runner's interpreter and wrapper; for an agent cron, inspect its model, provider, prompt, and profile as well as execution history. A successful direct invocation does not by itself prove the scheduled path used the same environment. Compare the actual cron environment and output before concluding that the issue is resolved.

Use existing logs and registry records first, especially when a manual invocation could send notifications or alter data. Check timestamps against the reported incident, and explain any gaps rather than inferring a failure from a stale event. If evidence is inconclusive, report the uncertainty and the next authorized diagnostic step. Historical examples in the references describe past conditions; they do not authorize changes to current jobs, scripts, or event records. Verify current behavior before relying on historical implementation details.
