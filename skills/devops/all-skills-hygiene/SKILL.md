---
name: all-skills-hygiene
description: "Use when auditing all Hermes skills for duplication, staleness, or bloat — cross-skill dedup, dead-skill detection via .usage.json, oversized SKILL.md, dangling references, and outsourcing structural rewrites to Opus. Триггеры: проверь скиллы, почисти скиллы, ревизия скиллов, audit skills."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
tags: [hermes, skills, decluttering, audit, dedup]
metadata:
  hermes:
    tags: [hermes, skills, decluttering, audit, dedup]
    related_skills: [hermes-memory-hygiene, hermes-agent-skill-authoring]
---

# All-Skills Hygiene

## Overview

Hermes accumulates skills over time (106+ as of 05.07.2026). This skill audits the SKILLS layer itself — duplication between skills, dead skills nobody uses, oversized SKILL.md files, and dangling cross-references. It is the sibling of `hermes-memory-hygiene`, which governs MEMORY/USER PROFILE — a different store with different mechanics (no shared char budget here; the problems are dedup/staleness/bloat, not overflow).

**Status: graduated from draft on 05.07.2026** after one full interactive pass against real data (see "Worked example" below for what that pass actually found and how it was executed). Ready for scheduled detect-only mode per "Two run modes."

## When to Use

- User says "проверь скиллы" / "почисти скиллы" / "ревизия скиллов" / "audit skills"
- Scheduled monthly run (detect-only, see "Two run modes")
- You notice the same fact duplicated across 2+ skills while working on something else

**Don't use for:** MEMORY/USER PROFILE cleanup (`hermes-memory-hygiene`), authoring a single new skill (`hermes-agent-skill-authoring`).

## Data sources

- `skills_list()` — full inventory: name, description, category, for all skills.
- `~/.hermes/skills/.usage.json` — real usage metrics per skill: `use_count`, `view_count`, `last_used_at`, `last_viewed_at`, `patch_count`, `pinned`, `state`, `created_at`. Read this file directly (`read_file`) rather than guessing — it's the only ground truth for "is this skill actually used."

## Finding categories (what to look for)

| Category | Signal | Action |
|---|---|---|
| **Content duplication** | 2+ skills state the same fact (URL, token location, procedure) near-verbatim | Identify source-of-truth skill → convert the rest to a one-line pointer or `absorbed_into` merge |
| **Dead skill** | `use_count=0` AND `view_count=0` for **≥60 days** since `created_at` (or since last mass re-index if that's more recent — see Pitfalls), NOT `pinned` | Flag to Sasha — NEVER auto-delete; propose delete or keep with reasoning |
| **Orphaned usage.json entry** | Skill name exists in `.usage.json` but `skill_view(name)` returns "not found" / not in `skills_list()` — the skill file was deleted but its metrics record wasn't cleaned up | Propose removing the stale `.usage.json` entry (metrics cleanup, not a skill deletion — no `skill_manage(action='delete')` needed) |
| **Oversized SKILL.md** | >14–20k chars (soft threshold from `hermes-agent-skill-authoring`; hard limit 100k) | Delegate a structural rewrite to Opus (see "Delegating structural fixes to Opus" below) — don't rewrite a 50k+ file yourself turn-by-turn |
| **Stale technical detail inside one skill** | Dates/versions/URLs that may no longer be true (e.g. "VPN needed" after VM moved into corp domain) | Verify against live system state, not the skill's last-edited date — ask Sasha when unsure |
| **Dangling references** | A skill's `related_skills` or body text points to a deleted/renamed skill | Find via `search_files` for the old name across all SKILL.md + MEMORY.md + USER.md; fix or remove |
| **Frontmatter hygiene** | Missing `version`/`author`, or `platforms: [all]` (known to break indexing) | Low-risk — fix directly without asking |

## Procedure

1. **Collect candidates by category, one category at a time** — don't mix duplication findings with dead-skill findings with size findings in one big list. Read `.usage.json` once per pass, `skills_list()` once per pass.
2. **Present findings to Sasha per the universal open-question protocol** (see `hermes-memory-hygiene` → "Universal open-question protocol"): full list of findings first, then go one at a time, each with brief context + recommendation + numbered options.
3. **Act only after explicit per-item approval** — same discipline as memory hygiene, not batch-executed after one blanket "ok."
4. **Consolidation** → `skill_manage(action='delete', name=..., absorbed_into=<target-skill>)`. **Pure pruning** → `absorbed_into=''`.
5. **After every delete** — grep MEMORY.md, USER.md, and all remaining skills for the deleted skill's name (`search_files`) and fix any dangling "see skill X" references.
6. **Oversized skill found** — don't rewrite it yourself line-by-line in the chat session. Delegate to Opus as a one-shot cron (see next section) with a concrete pass/fail rule for when it may act autonomously vs. must stop for Sasha's decision.

## Delegating structural fixes to Opus (worked pattern, 05.07.2026)

Once you've identified an oversized/non-compliant skill through this audit, the actual rewrite is a large, mechanical, multi-file task — better suited to a one-shot Opus cron than turn-by-turn `patch` calls in the live chat (token-expensive, and risks losing chat context mid-rewrite).

**Cron prompt must give Opus a clear autonomy boundary up front** — this is the key mechanism that let Opus finish end-to-end in one shot without Sasha's mid-flight approval:

- **List the exact gaps found** against `hermes-agent-skill-authoring`'s checklist (missing sections, size, frontmatter fields).
- **State the explicit decision rule**: "if every fix is mechanical (moving content to `references/`, adding missing sections, filling frontmatter, deduping without losing facts) — implement immediately. If any fix would change agent behavior/semantics (deleting a block outright, merging two blocks in a way that drops nuance) — STOP, present the plan with explicit 'Sasha decision needed: ...' items, do not implement." This single rule is what makes unattended one-shot execution safe.
- **Non-negotiable constraint stated explicitly**: no fact/case/example may be lost — compress wording freely, but a real incident, command, or number moved to a reference file must be moved in full, not paraphrased down to a summary.
- **Require a backup before touching the file**: `cp SKILL.md SKILL.md.bak-preopt-<timestamp>` before any edit.
- **Require the final report to state before/after size and NOT dump the full rewritten file into the chat** — Sasha reads the file himself; the report should be a change summary only.

## Two run modes (mirrors hermes-memory-hygiene)

- **Interactive (first pass, and any ad-hoc "проверь скиллы"):** full audit, present findings, wait for per-item approval, execute (or delegate to Opus per above), then report before/after skill count and sizes.
- **Scheduled (cron, monthly):** detect-only — collect findings, write them to the self-check report or a dedicated file, do NOT delete/merge/delegate-rewrite anything unattended. Sasha reviews and approves in a follow-up interactive session.

## What this skill does NOT do

- Does not touch MEMORY/USER PROFILE (that's `hermes-memory-hygiene`)
- Does not delete `pinned` skills (the tool itself refuses this)
- Does not flag a skill as dead purely on "not patched recently" — must combine with `use_count`/`view_count`
- Does not let a delegated Opus rewrite make semantic decisions (block deletion, meaning-changing merges) without stopping for Sasha

## Worked example: first full pass (05.07.2026)

This is what graduated the skill from draft — kept here as the concrete precedent for future passes, not just an abstract rule.

**Dead-skill category:** naive `use_count=0 AND view_count=0` flagged 65/92 skills. Investigation showed 64 of them shared one `created_at` (~10 days old) from a single bulk `.usage.json` re-registration event — a false signal, not real staleness (this is now baked into the Pitfalls below and the 60-day/outlier rule above). The one genuine outlier, `hermes-dev-patterns` (39 days old vs. the 10-day cluster), turned out to be an **orphaned usage.json entry** — the skill file itself no longer existed (`skill_view` → not found). Sasha approved removing just that stale metrics entry; zero real dead skills found this pass.

**Oversized-skill category, case `hermes-feature` (58K → 28.4K):** before delegating the structural rewrite, three smaller pitfall-level dedup fixes were done directly in the interactive session (each individually approved by Sasha): (1) three near-identical "gateway restart blocked from inside" entries collapsed into one; (2) a stray English `## Pitfalls` heading (1 item) merged into the main Russian `## Питфоллы` section instead of existing as a second parallel heading; (3) three long upstream-cutover pitfalls that duplicated `references/upstream-cutover-procedure.md` verbatim were compressed into one pointer block that preserves all three original incident case studies (translated to English for density), rather than being deleted.

Once those hand-fixes were in and Sasha confirmed the skill was checked against `hermes-agent-skill-authoring`'s checklist (missing `## Verification Checklist`, missing `license`/`metadata.hermes`, still 54K after manual dedup), the remaining structural work was delegated to a one-shot Opus cron per "Delegating structural fixes to Opus" above. Opus determined every remaining fix was mechanical (splitting Block 0 and other bulky sections into new `references/*.md` files, adding `## Verification Checklist`, filling `license`/`metadata.hermes`) and executed the full rewrite unattended — no mid-flight decision was needed from Sasha, confirming the autonomy-boundary rule worked as designed.

## Common Pitfalls

- **Two skills in one Opus cron is fine** — confirmed 06.07.2026: `hermes-gateway-setup` + `hermes-cost-optimization` processed sequentially in one cron job. Saves one context-launch worth of tokens vs two separate crons. Only combine skills that are truly independent (no shared files, no ordering dependency between them).
- **A plausible skill name is not proof of duplication** — before merging two skills, `skill_view` both and confirm the specific fact is actually restated, not just topically adjacent.
- **`use_count=0` alone isn't proof of "dead"** — a skill can be legitimately used without the counter incrementing in every code path (e.g. injected via cron `skills=[...]` rather than triggered by description match). Cross-check against cron job configs (`cronjob(action='list')` → `skills` field) before recommending deletion.
- **A mass `.usage.json` re-index resets `created_at` for the whole catalog at once — don't mistake that for real 0-day-old skills.** If most of the catalog shares one birth date, that date reflects a re-index, not real skill age. Prefer the 60-day threshold and sanity-check outliers (one skill much older than its neighbors) as the strongest real dead-skill signal.
- **Don't auto-delete anything** — every finding in this skill is a recommendation, execution needs Sasha's explicit per-item "да", even when delegating to Opus (the autonomy boundary only covers mechanical formatting, never semantic deletion).
- **Don't rewrite a 50k+ SKILL.md yourself, turn-by-turn, in the live chat.** It burns tokens on repeated full-file reads and risks losing track of what's already been changed mid-session. Delegate to a one-shot Opus cron once the audit has identified what needs to change.

## Verification Checklist

- [ ] Findings grouped by category, not mixed
- [ ] Each finding has a clear recommendation + alternative (per universal open-question protocol)
- [ ] No delete/merge/rewrite executed without explicit per-item approval (directly, or via the Opus autonomy-boundary rule)
- [ ] Dangling references checked and fixed after any delete
- [ ] `.usage.json` read fresh, not assumed from memory
- [ ] For delegated Opus rewrites: backup created before edit, final report has before/after size and no full-file dump
