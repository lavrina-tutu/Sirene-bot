---
name: background-agent-run
description: Run long agent tasks in background from a spec file.
version: 1.0.0
platforms: [linux, macos]
---

# Background Agent Runs (Long Tasks)

For long-running agent tasks (multi-hour analyses, big refactors, graph
building), do NOT run them in the foreground turn. Launch a background
`hermes agent run` driven by a spec file.

## Procedure

1. **Write the spec first.** Compose the full task as a markdown spec file
   (goal, inputs, steps, deliverables, output paths) and save it with
   `write_file` to `/tmp/<slug>-<topic>.md`. The spec is the single source of
   truth — the background agent gets no conversation context, so everything
   it needs must be in the file: exact file paths, expected outputs, and
   verification steps.
2. **Launch in background.** Run via `terminal` with:
   - `command`: `hermes agent run <flags> "<instruction referencing the spec file path>"`
   - `background: true` (returns immediately; the run continues server-side)
   - `notify: ["done"]` so the user gets pinged on completion
   - `workdir`: the repo/root the agent should operate in
   - `pty: false`
3. **Confirm to the user** that the run started, where the spec lives, and
   that they'll be notified on completion. Do not poll in the same turn.

## Restore from checkpoints

- If a run is killed or interrupted mid-way, do NOT restart from scratch.
- Have the spec instruct the agent to write checkpoint files (per-phase
  artifacts) to disk as it progresses.
- On restore, regenerate the spec with completed phases marked done and
  point the agent at the existing checkpoint artifacts so it resumes after
  the last checkpoint.

## Pitfalls

- Never assume the background agent saw the conversation. It only sees the
  instruction text — embed all context in the spec file. (Mechanism: a
  background run is a fresh process with no session history.)
- Use `background: true` on the terminal call, not a foreground
  long-running command — a foreground call blocks the turn until the whole
  task finishes or times out.
- Pass `background: true` together with `notify`/`persist_on_release` in ONE
  shot — setting `notify: true` or `persist_on_release: true` WITHOUT
  `background: true` is refused instantly (`notify only applies to background
  commands`). This is a call-contract error, not a transient backend failure:
  do NOT re-send the identical invalid call (the identical-call guard then
  halts you, burning tokens with no state change). Fix the flags, then retry.
- Validate deliverables after `done`: read the produced artifacts
  (e.g. with a node client against the artifact files) rather than trusting
  the completion notification alone.
