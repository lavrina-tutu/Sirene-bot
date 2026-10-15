---
tool: AggregateFromMeetings
type: tz-audit-findings
model_family: non-anthropic
date: 2026-07-02
author: Cursor
scope:
  - TZ_aggregate_main.md (v1.8)
  - modules/TZ_*.md (A-H)
  - pm/sessions/2026-06-30_cursor-tz-integrity-report.md
  - pm/PM_DECISIONS_LOG.md (PD-053..058)
status: findings-detected
rules: "No fixes, findings only"
---

# TZ Audit Findings (Non-Anthropic pass)

## Severity: HIGH

1. **Internal contradiction in 1-1 ID model (`#N` vs `^{login3}{hex}`).**
   - `modules/TZ_E_1on1.md` still contains an active semantics line in artifact description: commitments with numbering `#N` ("Нумерация `#N` сквозная по контакту").
   - The same module later states `#N` format is removed and IDs are `^{login3}{hex}`.
   - Impact: implementation ambiguity for parser, storage, and PM command interpretation in 1-1 domain.

2. **PD log vs canonical TZ conflict for PM Notes block format (PD-051).**
   - `pm/PM_DECISIONS_LOG.md` (PD-051 row) describes hash granularity over `<!-- pm: -->…<!-- /pm -->` blocks.
   - Canonical modules (`TZ_F_orchestration.md`, `TZ_D_projects.md`, `TZ_G_snapshot.md`) define active format as `### PM Notes (tasks|decisions|risks)`.
   - Impact: source-of-truth mismatch between decisions log and module specs for reconciler hashing logic.

## Severity: MEDIUM

3. **Project `short_id` source is described inconsistently across decision artifacts vs TZ text.**
   - `pm/sessions/2026-06-30_cursor-phaseB-answers.md` (Q-C3) states explicit PM-defined `short_id` for projects.
   - `TZ_aggregate_main.md` v1.8 / `modules/TZ_G_snapshot.md` phrase it as "Projects/Syncs — из slug", which implies derivation from slug, not explicit PM assignment.
   - Impact: governance ambiguity for ID stability and collision handling policy.

4. **People ID governance wording mismatch (`short_id` vs `login3`).**
   - `modules/TZ_G_snapshot.md` uses a combined phrase "явный `short_id` ... People — `login3`", mixing explicit-assignment and derived-ID concepts in one rule sentence.
   - `pm/sessions/2026-06-30_cursor-tz-integrity-report.md` states People uses `login3` and no extra field in `People/card.md`.
   - Impact: potential confusion in implementation contracts for People entity ID source.

## Severity: LOW

5. **Historical/deprecated notation remains in active narrative areas (non-normative but noisy).**
   - Legacy syntax examples (`<!-- pm: #N ... -->`) remain in migration explanation sections.
   - Not a direct spec conflict, but increases chance of accidental reuse of deprecated syntax by downstream implementers/LLM prompts.

---

## Audit Outcome

- Findings detected: **5**
  - HIGH: 2
  - MEDIUM: 2
  - LOW: 1
- Scope covered completely for requested files.
- This report intentionally includes **no remediation proposals**.