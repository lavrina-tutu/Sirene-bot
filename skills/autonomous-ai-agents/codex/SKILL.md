---
name: codex
description: "Use when «кодекс»/Codex CLI for coding, PRs, availability."
version: 1.0.1
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Codex, OpenAI, Code-Review, Refactoring]
    related_skills: [claude-code, hermes-agent]
---

# Codex CLI

Delegate coding tasks to [Codex](https://github.com/openai/codex) via the Hermes terminal. Codex is OpenAI's autonomous coding agent CLI.

## When to use

- Building features
- Refactoring
- PR reviews
- Batch issue fixing

Requires the codex CLI and a git repository.

## Prerequisites

- Codex installed: `npm install -g @openai/codex`
- OpenAI auth configured: either `OPENAI_API_KEY` or Codex OAuth credentials
  from the Codex CLI login flow
- **Must run inside a git repository** — Codex refuses to run outside one
- Use `pty=true` in terminal calls — Codex is an interactive terminal app

For Hermes itself, `model.provider: openai-codex` uses Hermes-managed Codex
OAuth from `~/.hermes/auth.json` after `hermes auth add openai-codex`. For the
standalone Codex CLI, a valid CLI OAuth session may live under
`~/.codex/auth.json`; do not treat a missing `OPENAI_API_KEY` alone as proof
that Codex auth is missing.

## Headless VM: non-interactive login

On a server/VM (no browser, e.g. for pipeline roles) the browser OAuth flow
(`codex login` → localhost:1455) does not apply. Auth options, mutually
exclusive by billing/model set:

| Method | Command | Best for |
|---|---|---|
| ChatGPT Business/Enterprise access token | `printenv CODEX_ACCESS_TOKEN \| codex login --with-access-token` | automation, no browser; workspace identity |
| Device code (beta) | `codex login --device-auth` | SSH user with TTY; requires admin "Enable device code" |
| Platform API key | `printenv OPENAI_API_KEY \| codex login --with-api-key` | API-key billing; **different model catalog** than ChatGPT login |
| Copy `~/.codex/auth.json` | `scp` from a browser machine | quickest; file = password |

`~/.codex/auth.json` is plaintext **or** OS keyring; on a Linux VM without a
keyring set `cli_auth_credentials_store = "file"`. Verify with `codex login
status`. Admins may need Codex Local + token/device-code toggles enabled; on
Enterprise/Edu GPT-6.1 Sol is off by default.

### config.toml pitfalls (headless login)

For the file credential store, `cli_auth_credentials_store = "file"` must be a
**top-level** key — putting it inside a `[cli_auth]` section makes `codex login`
fail with `invalid type: map, expected a string`. Same rule for a `[model]`
section: bare `model = "gpt-6.1-sol"` is what the loader expects; a
`[model] model = "…"` section also trips the same error. When smoke-failing on
config syntax, strip the config down to the single top-level credential key and
drive the model via the `-m` flag on `codex exec` rather than fighting the
loader. `[approval_policy] mode = "…"` as a map is likewise rejected — a plain
top-level string is the accepted shape.

### Device-code flow (headless, no token yet)

`codex login --device-auth` is interactive: it prints a URL (`.../codex/device`)
and a one-time code, then waits. Run it as a background PTY process
(`terminal(..., background=true, pty=true)`), then read the code back from
`process(action="log")` and relay it to the user to type into the browser
(valid ~15 min). During Art, poll/log again to confirm the session completed
before `codex login status` / smoke. Confirming from a code shown by the device
auth is exactly what the CLI instructs; the code is long-lived enough to pass
to the user, never a real password.

## Model selection for agent roles (ChatGPT Business/Enterprise login)

Codex's native models are OpenAI's own family (Claude/Grok/Composer are NOT in
the picker — bringing them in means a Responses-API gateway, a new entity).
Catalog and reasoning are two independent axes: pick an ID, then an effort.
Choose by role, not by "the strongest model":

| Role | Model ID | reasoning effort |
|---|---|---|
| Architect (TZ/plan/judgment) | `gpt-6.1-sol` | high (xhigh on a fat TZ/plan) |
| Architect escalation (only on proven gaps) | `gpt-6-astra` | high |
| Executor (bulk code) | `gpt-6.1-sol` | medium (high on multi-file) |
| Executor LIGHT (≤3 files) | `gpt-6-luna` | high |
| Reviewer (if OpenAI) | `gpt-6.1-sol` | high |

**Verify the actual model catalog on the host before proposing a specific model**
as a candidate — do not assume a generation/nickname exists. On the VM the
useful list lives in `~/.codex/models_cache.json` (fields `slug`,
`default_reasoning_level`, `supported_reasoning_levels`); e.g. `gpt-5.6-terra`
and `gpt-6-luna` are real while `gpt-6-terra` is rejected by the API ("not
supported when using Codex with a ChatGPT account") even though it accepts the
name — a requested id absent from the catalog either falls back to generic
metadata or errors with a confusing 400. Read the cache, not the wishlist, when
answering "is model X a candidate".

Default the architect to Sol, not Astra: Astra ≈5× Sol's credit rate on the
same windowed allowance, while Sol sits within ~1 index point of Astra and
above the frontier non-OpenAI models it replaces — escalation to Astra is for a
specific `TZ:patch`/plan where a reviewer keeps catching gaps Sol missed, not a
standing choice. Don't use Ultra (sub-agents can't be driven by a single
invoke) and don't put transition models (gpt-5.6.*) in a role config; Luna is
extract/classify-class, never an architect or reviewer.

**Judge a role model by its class, not by "the slot it filled before".** A model
that occupied the same role on a different stack is not thereby equal in class
— compare by benchmark and by the kind of work the role does (spec/plan/judgment
vs bulk code). Conversely, a reviewer's required strength is calibrated to the
**output** it must criticize (the TZ/plan on disk) and to the review norms, not
to the benchmark of the author model: a weaker author does not license a weaker
reviewer — a weaker author produces MORE gaps, and a weak reviewer lets them
through.

**Compare a candidate role model against the model it actually REPLACES, not
against another candidate in the same selection.** When a role's model moves to
a new harness/lineage, its fair benchmark is the incumbent occupant of that slot
(e.g. swap Cursor composer into Codex Terra is judged against composer, NOT
against the architect's Sol). A candidate is adequate if it is not weaker than
whom it replaces; comparing it to a stronger, differently-scoped model of another
role yields a false rejection. A weak result from this mistake surfaces as
"the candidate is too weak" when the real issue is a mismatched baseline — check
which model fills the role today before arguing class.

**Reviewer within Codex is `gpt-6-astra`, never the author's own id.** The
independent-vendor reviewer exists only while an OpenRouter/Tutu gateway is
affordable; when it is not, the least-bad in-Codex reviewer is the model that is
stronger than the author AND a different id — e.g. author `gpt-6.1-sol`,
reviewer `gpt-6-astra` at high. Reusing the author's own id is a twin pass, not a
review: it smooths the same family's gaps (missed `[NEW-ENTITY]`, watered-down
"don't touch", extract drift). `codex-auto-review` is a hidden auto-approval
model for the sandbox, NOT a usable reviewer role. Many VMs expose Astra's
default reasoning as low, so always pin `-c model_reasoning_effort` to high, or
the reviewer judges weaker than the author. When both architect and reviewer
must sit on OpenAI, independence is consciously traded: the residual risk from a
shared prior is acceptable only if author and reviewer are different ids AND
the reviewer effort is pinned high. Effort per call:
`codex exec -C <ABS> -m gpt-6.1-sol -c model_reasoning_effort='"high"' --skip-git-repo-check --json "…"`.

**Reviewer verdict files (dev-workflow REV-*.md): keep reviewing sections as
H2 (`## `), never H3 (`###`).** The downstream `rev_verdict()` parser takes the
block from `## Вердикт` to the *next H2 header*; if the reviewer writes its
narrative/argumentation as H3 sections, the verdict block is never terminated
and swallows the whole file — so any body mention of the OTHER verdict word
(e.g. explaining a past `REQUEST-CHANGES` round) makes the parser return
CONFLICT against the explicit `verdict=APPROVE`, and `complete-phase` fails
"REV verdict unknown or conflict" even though the verdict is genuinely
approve and the full test suite is green. When you (or a Codex reviewer) write
the review, put each reasoning section at `## ` level and keep the verdict
assertion as the first line under `## Вердикт`, away from any stray
`REQUEST-CHANGES` string above the next H2.

If a reviewer must stay on an independent vendor (different family from the
architect's), run it through an OpenRouter/Tutu gateway instead of Codex — the
two roles then come from different providers, not different Codex models.

## `-c` effort quoting: shell vs argv (HTTP 400 `Invalid value`)

`model_reasoning_effort` must reach Codex as a TOML string. The quoting in the
examples above (`model_reasoning_effort='"high"'`) is **shell** notation: when
an integration builds the argv list in Python (`subprocess.run([...])`, no
shell), the outer single quotes are NOT stripped and the value lands as
`"high"` **with quotes** → Codex answers `HTTP 400 Invalid value: '"high"'`
and the call fails cleanly. In a non-shell argv element pass exactly
`model_reasoning_effort="high"` (double quotes only, no outer single). Compose
the element as a Python string `f'model_reasoning_effort="{effort}"'`.

Debug fast: when an `invoke-role` returns `canonical_artifact_fail` but the
model itself is suspect, call `run_codex` (or the raw `codex exec`) directly
and read the `--json` stream — a ``turn.failed`` with status 400 there is a
quoted-effort bug, not a missing write. The model is fine; the argv is not.

Also verify effort on the host, don't trust the model's default: if the
candidate model's default reasoning is `low` (e.g. Astra), pin `-c high`
explicitly or the role judges weaker than intended.

## Ad-hoc ролевая консультация (мнение архитектора вне DevWorkflow)

When the user asks for an architect's verdict on a question that is NOT a
DevWorkflow phase (no slug/phase — e.g. «мнение архитектора» про смену
дефолтной модели) the role must still be invoked, but NOT via
`pipeline invoke-role`: without `--slug/--phase` it returns rc=0 and silently
swallows the role's stdout/stderr — you get nothing back. Call `codex exec`
directly, reading the model/effort from
`~/WorkVault/Registries/EcosystemConfig.yaml` → `tools.dev_workflow.invoke.roles.<role>`
(architect = `gpt-6.1-sol`, effort high) instead of hardcoding:

```bash
cd ~/WorkVault/Registries && codex exec -C <ABS-workspace> -m gpt-6.1-sol -c 'model_reasoning_effort="high"' --skip-git-repo-check --json --sandbox danger-full-access -- "$(cat /tmp/prompt.md)"
```

- Prompt file: question verbatim + live facts from the machine (config, model
  tables) + requested answer format + «только текст мнения, без реализации».
- Parse the result from the `--json` NDJSON stream (last `agent_message` item,
  see above); `json.load` of the whole file fails with «Extra data».
- Pass the role's verdict to the user as-is — no own recommendations, the
  architect owns design verdicts.
- CLI pitfall: the `pipeline` package must be run as `python3 -m pipeline.cli`
  from `~/WorkVault/Registries` (package root) — from inside
  `Registries/pipeline/` the relative import fails with
  `ImportError: attempted relative import with no known parent package`.

## Non-interactive: `codex exec`, not `codex run`

The canonical one-shot command is `codex exec` (alias `codex e`). Integrations
that call `codex run` will fail with "unknown subcommand" — fix the caller, or
verify the CLI version first. `--full-auto` is removed/deprecated; use
`--sandbox workspace-write` (or `--sandbox danger-full-access` under a gateway
where bubblewrap breaks).

Codex refuses to run outside a git repo; for non-git workspaces (e.g. a
Backlog/USERTOOLS tree) pass `--skip-git-repo-check`.

## Consuming `--json` output (event-stream format)

`codex exec ... --json` writes NDJSON **events**, not a single result envelope.
The final answer is the last `item.completed` whose `item.type == "agent_message"`
carrying `item.text`; `turn.failed` is the failure marker. A shell/script
consumer must parse lines for these, not `json.load` the whole stream:

```python
result, failed = "", False
for line in open(outfile, encoding="utf-8", errors="replace"):
    o = json.loads(line)
    if o.get("type") == "item.completed" and isinstance(o.get("item"), dict) \
       and o["item"].get("type") == "agent_message" and o["item"].get("text"):
        result = o["item"]["text"].strip()
    if o.get("type") == "turn.failed":
        failed = True
```

A model can emit several `agent_message` items (intermediate "I'll check…" lines
then the final answer); take the last non-empty one. Do not treat raw `--json`
as the report — strip tool/event payload before persisting (PII hygiene): keep
only `{result, is_error/failed}` like the Cursor `agent -p --output-format json`
envelope the consumer used to expect.

## Migrating a Cursor-based script to Codex (Cursor→Codex move)

When a bash/scripts tool still drives roles through Cursor CLI
(`agent -p ... --model cursor-grok-4.6-high|claude-sonnet-5-medium|composer-2.5 --output-format json`)
and the pipeline backend is already Codex (`EcosystemConfig` `invoke.default_backend: codex`,
roles `gpt-6.1-sol`/`gpt-6-astra`/`gpt-5.6-terra`/`gpt-6-luna`), port the call to
`codex exec -C "$HOME" -m gpt-6.1-sol -c model_reasoning_effort='"high"' --skip-git-repo-check
--sandbox read-only --json -p "$(cat /tmp/task.md)"` (read-only role: `--sandbox read-only`
+ a hard prompt that forbids writes). Then swap the downstream parser from the Cursor
`{subtype,is_error,result}` envelope to the Codex event stream above (keep the emitted
file shape `{subtype,is_error,result}` so `llm_anomaly_errorbus.py`-style consumers stay compatible).

**Find ALL live (not documentation) Cursor references, not just the obvious ones.**
A migration audit must grep the executable/authoritative layer — `~/.hermes/scripts/*.sh`,
`~/.hermes/cron/jobs.json` (inline cron prompts), `~/USERTOOLS/` source, `~/WorkVault/AGENTS.md` —
for `agent -p`, `--model cursor-grok|composer-2\.5|claude-sonnet-5`, `roles_cursor`, `--backend cursor`.
Skills' SKILL.md and `references/` are documentation/history of the fallback path — a mention there
is NOT a live call; don't "fix" the docs (Cursor stays a valid rollback via `roles_cursor`). Two
gotchas while doing this:
- `jobs.json` stores prompts with escaped `\n` — `patch` won't match multi-line old_string; load,
  replace, re-validate as JSON (`json.loads`) instead.
- A dead script (no cron/jobs/output reference, old mtime) is a leftover, not a live call — report it,
  don't edit unless asked to delete.

**When patching a stateful script, do it in place and re-run.** After editing a working script,
`bash -n` it and run a short probe; do not declare the migration done on a self-report.

## Checking availability ("проверь доступность кодекс")

«Кодекс» = this Codex CLI, not an internal Tutu service. `codex login status`
("Logged in using ChatGPT") only proves a local OAuth file exists under
`~/.codex/` — an expired token still prints it. The only real availability
signal is a live model call:

```bash
codex exec -m gpt-6.1-sol --skip-git-repo-check --sandbox read-only "Reply with exactly one word: pong"
```

Pitfalls:
- **`codex exec` returns rc=0 even when auth fails.** A `401 token_expired` is
  emitted as `rmcp`/`codex_models_manager` ERROR lines on stderr while the
  process still exits 0 and may even echo the prompt text back. Classify by
  grepping the combined output for `token[_ ]?expired|401|authentication token`
  → AUTH_FAIL, never by exit code.
- **`codex models list` is not a subcommand** (v0.163: "unexpected argument
  'list' found"). The catalog lives in `~/.codex/models_cache.json`, not in a
  CLI subcommand.
- **Unauthenticated `curl` to `chatgpt.com/backend-api/...` returning 401/403
  is expected and only proves network reachability.** A raw 401/403 is an
  auth-state answer, not a "service down" signal — "service reachable but token
  expired" and "service down" are different conclusions. The retry/refresh can
  also make a single 401 transient, so when asked to "check N times every M
  minutes" run the same probe repeatedly instead of concluding from one sample,
  and report now + final.
- **Instant failure + `You hit your spend cap set by the owner of your workspace` =
  account quota, not a bug.** When every model call dies in ~3–4 s with that
  `error` line in the `--json` stream while `codex login status` still prints
  "Logged in using ChatGPT", the workspace spend cap is exhausted — auth is
  fine, quota is not. All models are affected at once. Symptom downstream: a
  role fails `canonical_artifact_fail` / `empty-result` in seconds, which looks
  like "the role didn't write its file" — do NOT burn retry turns strengthening
  the prompt or the caller; the fix belongs to the workspace owner raising the
  cap (or waiting for the window reset). Differentiate from `401 token_expired`
  (single refresh, retry) by grepping the combined output for the exact
  spend-cap sentence.

**Spend-cap stall ⇒ resume the SAME phase with the SAME prompt body, and
verify the re-emitted prompt still carries the task, not just the pointer.**
When a workspace spend cap kills role runs mid-`codex exec` (all models die in
~3–4 s with the exact spend-cap sentence, `codex login status` still "Logged
in"), a downstream `invoke-role` phase is left `doing`/`empty-result` with a
dead pid while auth is fine. Once the cap lifts, resuming that phase with a
fresh `emit-prompt` can return a HEADER-ONLY packet (MUST-read + Paths) with no
task body — e.g. when the phase has no `extract.md` to rebuild the body from —
and invoking the role against the empty header reproduces `empty-result`/
`canonical_artifact_fail`. Reuse the previous full prompt file for that same
phase (the failed run's prompt still holds the complete task statement:
reference paths, expected canonical artifact, output format) instead of
re-invoking on the stripped re-emit. Never re-invoke a blank header.

## One-Shot Tasks

```
terminal(command="codex exec 'Add dark mode toggle to settings'", workdir="~/project", pty=true)
```

For scratch work (Codex needs a git repo):
```
terminal(command="cd $(mktemp -d) && git init && codex exec 'Build a snake game in Python'", pty=true)
```

## Background Mode (Long Tasks)

```
# Start in background with PTY
terminal(command="codex exec --sandbox workspace-write 'Refactor the auth module'", workdir="~/project", background=true, pty=true)
# Returns session_id

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send input if Codex asks a question
process(action="submit", session_id="<id>", data="yes")

# Kill if needed
process(action="kill", session_id="<id>")
```

## Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--sandbox workspace-write` (`-s`) | Sandboxed but auto-approves file changes in the workspace (the recommended auto-build mode) |
| `--dangerously-bypass-approvals-and-sandbox` | No sandbox, no approvals (fastest, most dangerous; `--yolo` still works as a hidden alias) |
| `--sandbox danger-full-access` | No Codex sandbox; useful when the host service context breaks bubblewrap |

> **Deprecated:** `--full-auto` still works but the live CLI warns to use `--sandbox workspace-write` instead.

## Hermes Gateway Caveat

When invoking the Codex CLI from a Hermes gateway/service context (for example,
Telegram-driven agent sessions), Codex `workspace-write` sandboxing may fail even
when the same command works in the user's interactive shell. A typical symptom is
bubblewrap/user-namespace errors such as `setting up uid map: Permission denied`
or `loopback: Failed RTM_NEWADDR: Operation not permitted`.

In that context, prefer:

```
codex exec --sandbox danger-full-access "<task>"
```

Use process boundaries as the safety layer instead: explicit `workdir`, clean git
status before launch, narrow task prompts, `git diff` review, targeted tests, and
human/agent confirmation before committing broad changes.

## PR Reviews

Clone to a temp directory for safe review:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)
```

## Parallel Issue Fixing with Worktrees

```
# Create worktrees
terminal(command="git worktree add -b fix/issue-78 ~/.hermes/cache/scratch/issue-78 main", workdir="~/project")
terminal(command="git worktree add -b fix/issue-99 ~/.hermes/cache/scratch/issue-99 main", workdir="~/project")

# Launch Codex in each
terminal(command="codex --sandbox workspace-write exec 'Fix issue #78: <description>. Commit when done.'", workdir="~/.hermes/cache/scratch/issue-78", background=true, pty=true)
terminal(command="codex --sandbox workspace-write exec 'Fix issue #99: <description>. Commit when done.'", workdir="~/.hermes/cache/scratch/issue-99", background=true, pty=true)

# Monitor
process(action="list")

# After completion, push and create PRs
terminal(command="cd ~/.hermes/cache/scratch/issue-78 && git push -u origin fix/issue-78")
terminal(command="gh pr create --repo user/repo --head fix/issue-78 --title 'fix: ...' --body '...'")

# Cleanup
terminal(command="git worktree remove ~/.hermes/cache/scratch/issue-78", workdir="~/project")
```

## Batch PR Reviews

```
# Fetch all PR refs
terminal(command="git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'", workdir="~/project")

# Review multiple PRs in parallel
terminal(command="codex exec 'Review PR #86. git diff origin/main...origin/pr/86'", workdir="~/project", background=true, pty=true)
terminal(command="codex exec 'Review PR #87. git diff origin/main...origin/pr/87'", workdir="~/project", background=true, pty=true)

# Post results
terminal(command="gh pr comment 86 --body '<review>'", workdir="~/project")
```

## Rules

1. **Always use `pty=true`** — Codex is an interactive terminal app and hangs without a PTY
2. **Git repo required** — Codex won't run outside a git directory. Use `mktemp -d && git init` for scratch
3. **Use `exec` for one-shots** — `codex exec "prompt"` runs and exits cleanly
4. **`--sandbox workspace-write` for building** — auto-approves changes within the sandbox (`--full-auto` is deprecated for this)
5. **Background for long tasks** — use `background=true` and monitor with `process` tool
6. **Don't interfere** — monitor with `poll`/`log`, be patient with long-running tasks
7. **Parallel is fine** — run multiple Codex processes at once for batch work
