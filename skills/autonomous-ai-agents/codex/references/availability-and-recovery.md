

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

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
