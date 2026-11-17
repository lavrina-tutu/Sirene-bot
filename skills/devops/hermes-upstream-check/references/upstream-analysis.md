## Part 1 — Analysis: eight criteria and data collection

```bash
cd ~/hermes-agent
REPO_BASE=$(hermes --version | grep -oP 'upstream \K[a-f0-9]+')
git fetch origin main --quiet
HEAD_SHA=$(git rev-parse origin/main)
git log $REPO_BASE..$HEAD_SHA --format="%h %ai %s"
git diff --name-only $REPO_BASE $HEAD_SHA
```

The existing `~/.hermes/scripts/upstream_monitor.sh` also calculates feat/fix/refactor counts, finds our components and maintains `watch_list`; prefer it to writing git commands from scratch.

| # | Criterion | What to look for |
|---|---|---|
| 1 | Customization/conflict | Diff overlaps our files (`cron/`, `gateway/platforms`, `agent/prompt_builder.py`); `config.*schema\|DEFAULT_CONFIG` may mean config migration. Also inspect `extra_or_secret\|TELEGRAM_ALLOWED\|allowed_chats\|env.*YAML` against our `.env`, not YAML alone. |
| 2 | Token savings | `token\|cost\|cach\|compress` |
| 3 | Fixes to our functionality | `telegram\|gateway\|cron\|delegat\|subagent\|heartbeat\|stale`; explain in human terms what each fixes. |
| 4 | Stability/reliability | `crash\|corrupt\|WAL\|deadlock\|race\|leak\|drain\|SIGTERM`; the most important category for the VM. |
| 5 | Stability quarantine | A commit reverted in the same range, or a fix without a test in a critical area: quarantine for two cycles (see watch_list). |
| 6 | 🚨 Urgent security | `security\|CVE\|vulnerab\|auth.*bypass\|credential leak\|privilege escalation`; consider immediately. |
| 7 | 🔇 Platform noise | `windows\|win32\|macos\|darwin\|schtasks\|powershell`; outside the Linux VM focus. Do not confuse volume with relevance. |
| 8 | New features | `feat(...)` in interesting areas (providers, toolsets, delegation/cron API); assess upside as well as risk. |

**watch_list** (`~/.hermes/upstream-monitor.json`, alongside `last_sha`): add a criterion 5 commit with `cycles_pending: 1`; increment by one in the next weekly cycle if it remains in the range. At `cycles_pending >= 2`, it has passed quarantine and receives normal categorization. Remove its entry if `last_sha` advances past it.

**Advance `last_sha`** only when `~/hermes-agent` has actually been updated and `git merge-base --is-ancestor $LAST_SHA $LOCAL_HEAD` confirms HEAD has advanced. Otherwise leave `last_sha` unchanged and let the range accumulate until an actual update. Otherwise quarantine cannot work because commits disappear from the range prematurely.

**Check `last_sha` against `origin/main` before risk analysis:** it can fall outside the upstream history, causing a falsely enormous commit count and a wrong analysis baseline. Before calculating the diff run `git merge-base --is-ancestor $LAST_SHA origin/main && echo ok || echo DRIFT`. On DRIFT use the confirmed baseline `git merge-base HEAD origin/main`, not `last_sha`; report the discrepancy as a monitor defect to fix.

**Report format:**
```
🔔 Upstream hermes-agent: N new commits
## By category (nonempty only): 1/2/3/4/6🚨/8
⏳ In quarantine: N commits, M waiting 1 more cycle
🔇 Not relevant: N commits
## Verdict: 🟢/🟡/🔴 + rationale in 3–5 points
```
