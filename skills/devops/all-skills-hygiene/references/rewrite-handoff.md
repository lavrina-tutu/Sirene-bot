Historical source: model/cron selection and preserving each H2 are superseded by SKILL.md and the current authoring canon.

## Delegating structural fixes: Sonnet by default, Opus only when the boundary itself is unclear (revised 13.07.2026)

Once you've identified an oversized/non-compliant skill through this audit, the actual rewrite is a large, mechanical, multi-file task — better suited to a one-shot cron than turn-by-turn `patch` calls in the live chat (token-expensive, and risks losing chat context mid-rewrite).

**Model choice: use Sonnet, not Opus, when the mechanical/semantic boundary can be stated explicitly and unambiguously in the prompt.** This class of work (moving content to `references/`, deduping near-identical repeated pitfalls without losing facts, filling missing frontmatter fields, fixing broken escape sequences from prior edits) is pattern-matching and careful copy-paste, not judgment-heavy authoring — it does not need Opus-level reasoning once the boundary rule is spelled out. Reserve Opus for cases where the mechanical/semantic line itself is fuzzy going in (e.g. deciding whether two skills' overlapping content is true duplication or subtly different domains) and the model has to make that call unattended.

**Cron prompt must give the model a clear autonomy boundary up front** — this is the key mechanism that lets it finish end-to-end in one shot without the user's mid-flight approval, regardless of which model runs it:

- **List the exact gaps found** against `hermes-agent-skill-authoring`'s checklist (missing sections, size, frontmatter fields).
- **State the explicit decision rule**: "if every fix is mechanical (moving content to `references/`, adding missing sections, filling frontmatter, deduping without losing facts) — implement immediately. If any fix would change agent behavior/semantics (deleting a block outright, merging two blocks in a way that drops nuance) — STOP, present the plan with explicit 'user decision needed: ...' items, do not implement." This single rule is what makes unattended one-shot execution safe.
- **Non-negotiable constraint stated explicitly**: no fact/case/example may be lost — compress wording freely, but a real incident, command, or number moved to a reference file must be moved in full, not paraphrased down to a summary.
- **Require a backup before touching the file**: `cp SKILL.md SKILL.md.bak-preopt-<timestamp>` before any edit.
- **Require the final report to state before/after size and NOT dump the full rewritten file into the chat** — the user reads the file themself; the report should be a change summary only.
- **Require a final self-check**: `grep "^## "` on the rewritten file to confirm every original top-level section header is still present, plus a manual read of the frontmatter block.

