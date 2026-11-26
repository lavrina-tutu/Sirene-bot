# Direct-mode role launch + addressable rework (dev-workflow)

## Background role launch (must ping on completion)
Running a role (architect/reviewer/executor) via `codex exec` in direct mode:
- Launch as a background process at the TOOL level: `terminal(command=..., background=true, notify=true, persist_on_release=true)`. `notify=true` is what pings you when the role exits.
- Do NOT append `&` inside the shell command. A shell-level background job runs SILENTLY (no ping), so you never learn the role finished and can't advance the serial chain.
- Running the same command foreground with `notify` is refused with `"notify only applies to background commands"` — set `background=true` at tool level, not shell level.
- After a `pkill` of a mislaunched run, re-launch the same command as a proper background call in the next turn rather than re-typing the prompt path.
- Probe the model before a heavy run: short `codex exec -m <model> -c 'model_reasoning_effort="high"' --json --sandbox danger-full-access "Reply with exactly: OK"` fails fast on a bad alias/billing before you spend ~7M input tokens.
- Token-account each role run from the final `{"type":"turn.completed", ... "usage":{...}}` event in its own log file (tee every invocation into `evidence/<STEP>.<role>.log`).

## Addressable REV rework loop (REQUEST-CHANGES -> izd.N)
A reviewer REQUEST-CHANGES lists R1..Rn plus optional M1 (non-blocking). Close it correctly:
- Architect applies EXACTLY R1..Rn (and M1) as a numbered edition (izd.2/izd.3) of the SAME files, plus a changeset file mapping old->new address for every fix.
- Re-run the reviewer on the corrected files; it re-verifies per fix (R1..Rn/M1 PASS/FAIL). Hash the reviewed files so a stale hash can't pass as the corrected edit.
- Do not expand scope while fixing; the goal is to satisfy R1..Rn, not to add content.

## Honest partial: spans outside the addressable map
When transferring an adopted decision (D/Q norms etc.) into master, apply ONLY the addressable arrows that were reviewed. If an ACTIVE span contradicts the new norm but is not covered by an arrow:
- Do NOT silently widen the change to cover it — that is precisely the un-approved expansion the workflow forbids.
- Leave it unchanged, report it as an OPEN item with an exact L-address, return the choice to the owner (never default), and keep the transfer status PARTIAL (not DONE) while any OPEN remains.
- The owner either grants an addressable arrow for it (then apply narrowly and re-verify) or defers it — do not pick the outcome yourself.

## Addressable delivery evidence
After an addressable delivery to production/normative files:
- Read back the on-disk SHA-256 of EVERY touched file and compare to the report's claimed "after" hash — a report alone is not verification.
- Have a reviewer verify the EXACT new bytes (reverse-diff to the original baseline hashes) before wiring anything that depends on them.