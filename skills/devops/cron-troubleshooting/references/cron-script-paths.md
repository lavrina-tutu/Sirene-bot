# Cron script paths and wrappers

Diagnose first; historical examples of fixes do not authorize independent script changes.

## no_agent symlink blocked outside scripts/

A no_agent cron can fail with `Blocked: script path resolves outside the scripts directory` when `~/.hermes/scripts/<script>` is a symlink to a target outside that directory. The runner resolves and blocks it. Inspect `ls -la ~/.hermes/scripts/<script>`. Within authorized fix scope, replace the symlink with a wrapper:

```bash
rm ~/.hermes/scripts/<script>        # remove the symlink
cat > ~/.hermes/scripts/<script> << 'WRAPPER'
#!/bin/bash
# Wrapper: real script lives elsewhere; no_agent runner blocks symlinks
set -euo pipefail
exec bash "$HOME/<real_path>/<script>"
WRAPPER
chmod 711 ~/.hermes/scripts/<script>
```

> Context (RU): Прецедент 15.08.2026 — `restore-skills-daily` (74c93fa1e357), симлинк `restore-all-skills.sh` → `~/hermes-workspace/restore-all-skills.sh`, падал с 04.08. Починена заменой на враппер.

Related: `check-cron-results` describes no_agent symlinks resolving outside scripts/.

## no_agent missing dependency: exit code 127

Read the cron output for `exit code 127` and inspect stderr for the missing file. For a wrapper or script, inspect internal calls (`grep` for `$SCRIPT_DIR`, `source`, and direct `.sh` calls). A dependency may have been removed during cleanup while its call remained. Within authorized fix scope, remove an obsolete call or restore/rewrite the required file.

> Context (RU): Прецедент 15.08.2026 — `GitHub автосинк` (5d16b96a9ed5). `restore-all-skills.sh` вызывал удалённый при чистке tz-dev `link-tzdev-to-default.sh`. Вызов удалён.

## Bash wrapper hides traceback behind an exit code

A `no_agent` job can have `last_status="error"`, `last_error="Script exited with code N"`, while direct execution of its `.sh` prints only `exit N`. A wrapper may capture stdout and stderr in `OUTPUT=$(<cmd> 2>&1)` and exit via `exit $EXIT_CODE` without printing `$OUTPUT`. It may log elsewhere, but the direct wrapper invocation hides the traceback.

Inspect the wrapper for `source`/`activate`/`VENV`/`cd`/`$OUTPUT=$(` to identify the interpreter, venv, and inner command. Only when side effects are authorized, run the inner CLI in the same environment, venv, cwd, and flags:

```bash
VENV="<env_path_from_wrapper>/bin/activate"; DIR="<dir_from_wrapper>"
cd "$DIR"; source "$VENV"; unset <vars_the_wrapper_unset>
<CLI_command> 2>&1   # e.g. mofs run --mode=cron
```

The direct call can reveal the traceback (NameError, import, or another error). For a silent stderr and exit code N, inspect the internal call rather than assuming the wrapper itself is the source. Also inspect `failure_streak`/`last_status`/`last_error` in jobs.json for runner-level evidence.

`reconcile: cron run failed for job <id>` is a symptom of cron failure, not necessarily a reconcile failure. Investigate the cron/CLI and route fixes through BUGFIX (`BUG:diagnose` → `GATE:diagnose-review`). Verify auto-resolve in current code and behavior; historical claims conflict, so do not assume the event will close automatically. See [errorbus-diagnostics.md](errorbus-diagnostics.md).
