# Upstream merge — command reference (steps 0–8)

Perform all operations only under the architect-approved plan and in `upstream-merge-in-progress`. Stop and escalate any deviation outside the whitelist. Remove locks, resolve conflicts, fix tests or roll back only on the architect's explicit decision; never do these automatically.

## Process

### Step 0: Pre-flight
```bash
cd /home/tkachenkoav/hermes-agent
git status --porcelain | grep -E '^(UU|AA|DD)'   # empty
test -f .git/MERGE_HEAD && echo "MERGE IN PROGRESS" || echo "CLEAN"
test -f .git/index.lock && echo "INDEX LOCK: stop and report to the architect"
git log -1 --oneline                                 # confirm HEAD
```

### Step 1: Test baseline
```bash
# Targeted run (faster, our risk areas):
bash scripts/run_tests.sh -q tests/cron/ tests/gateway/ tests/agent/test_prompt_builder.py

# Full run (1-2 hours, background):
bash scripts/run_tests.sh -q 2>&1 | tee /tmp/baseline_full_tests.log
```

**IMPORTANT:** `python -m pytest -q` is unsuitable: nine collection errors on `tests/acp*`. Always use `scripts/run_tests.sh`.

### Step 2: Dry merge
```bash
git merge --no-commit --no-ff origin/main
git diff --name-only --diff-filter=U   # list conflicted files
```

### Step 3: Resolve trivial conflicts
For conflicts where upstream replaced our code with a common solution, only when explicitly authorized by the architect:
```bash
git checkout --theirs <file1> <file2>
git add <file1> <file2>
```

### Step 4: Resolve complex conflicts
Resolve code conflicts through the **only** route: the dev-workflow orchestrator (emit-prompt → invoke-role, role and model taken from the dev_workflow YAML). Any direct `invoke-role` with a hardcoded model is invalid and must not be used, neither as primary nor as fallback.

### Step 5: Update tests (if affected)
If a conflict affects code referenced by tests, update tests through the same single route (dev-workflow orchestrator, emit-prompt → invoke-role with role and model from YAML), supplying full context (function X removed, logic moved to Y).

### Step 6: Full test run
```bash
bash scripts/run_tests.sh -q 2>&1 | tee /tmp/postmerge_tests.log
# Compare with baseline: no more failures than before
```

### Step 7: Smoke checks (import/health, not delivery)
```bash
hermes -p default doctor
hermes -p default status
hermes -p default cron list
```

This does not close the attempt. After FF, and after a gateway restart if Sasha authorized it, follow the post-FF checklist in `SKILL.md`: token audit, effective allowlist, and group **and DM** smoke. `doctor`, `status`, one DM, or cron outbound to a topic are insufficient (16.09.2026 precedent). Do not run diagnostic `getUpdates` against the production token.

### Step 8: Commit
```bash
git commit --no-edit
git log -1 --oneline
```

## Strategy: merge (NOT rebase, NOT squash)

- Preserve local commit identities (`hermes --version` shows `+N carried commits`).
- Previous upgrades used merge commits.
- Rebase would rewrite hashes referenced by internal files.

## Pitfalls

1. For analysis/planning of 5000+ commits, use the architect role and model taken from the dev_workflow YAML; do not use the Claude thinking pattern for this (historical 07.08 note retained as precedent). If context is insufficient, split analysis by directory (cron/gateway/plugins/agent); do not fall back to Claude.
2. `.git/index.lock` can remain from previous sessions. Remove it with `rm .git/index.lock` only on an explicit architect decision.
3. Do not use `python -m pytest`: collection errors occur on `tests/acp*`. Always use `scripts/run_tests.sh` (per-file subprocess isolation).
4. Do not use `pkill -f` to stop background tests; use `process(action='kill')` with the session_id.
5. Split large executor prompts over 4K tokens / 12+ files into 2–3 prompts of 4–6 files to avoid timeouts (model from dev_workflow YAML).
6. After removing or moving functions, always search tests: `grep -rn "<func_name>" tests/`.

## Rollback — only on the architect's explicit decision in a new plan

None of the commands below is an automatic executor response. The architect specifies the action and rollback point considering state and progress.

| Scenario | Action |
|---|---|
| Dry merge went wrong | `git merge --abort` |
| Commit made but tests failed | `git reset --hard <pre-merge-hash>` |
| Runtime state damaged | Restore from `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS.tar.gz` |
