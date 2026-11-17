

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

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
