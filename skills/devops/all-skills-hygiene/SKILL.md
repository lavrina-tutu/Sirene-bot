---
name: all-skills-hygiene
description: "Use when auditing all Hermes skills for duplication, staleness, or bloat — cross-skill dedup, dead-skill detection via .usage.json, oversized SKILL.md, dangling references. Триггеры: проверь скиллы, почисти скиллы, ревизия скиллов, audit skills."
version: 0.1.0
author: agent
license: MIT
platforms: [linux, macos, windows]
tags: [hermes, skills, decluttering, audit, dedup]
metadata:
  hermes:
    related_skills: [hermes-memory-hygiene, hermes-agent-skill-authoring]
---

# All-Skills Hygiene

**DRAFT v0.1 — not yet run against real data.** First interactive pass with Sasha's per-item approval is required before this skill is scheduled on a cron. Update this file with corrections learned from that pass before enabling scheduled mode.

## Overview

Hermes accumulates skills over time (106+ as of 05.07.2026). This skill audits the SKILLS layer itself — duplication between skills, dead skills nobody uses, oversized SKILL.md files, and dangling cross-references. It is the sibling of `hermes-memory-hygiene`, which governs MEMORY/USER PROFILE — a different store with different mechanics (no shared char budget here; the problems are dedup/staleness/bloat, not overflow).

## When to Use

- User says "проверь скиллы" / "почисти скиллы" / "ревизия скиллов" / "audit skills"
- Scheduled monthly run (once this skill graduates from draft — see "Two run modes" below)
- You notice the same fact duplicated across 2+ skills while working on something else

**Don't use for:** MEMORY/USER PROFILE cleanup (`hermes-memory-hygiene`), authoring a single new skill (`hermes-agent-skill-authoring`).

## Data sources

- `skills_list()` — full inventory: name, description, category, for all skills
- `~/.hermes/skills/.usage.json` — real usage metrics per skill: `use_count`, `view_count`, `last_used_at`, `last_viewed_at`, `patch_count`, `pinned`, `state`, `created_at`. Read this file directly (`read_file`) rather than guessing — it's the only ground truth for "is this skill actually used."

## Finding categories (what to look for)

| Category | Signal | Action |
|---|---|---|
| **Content duplication** | 2+ skills state the same fact (URL, token location, procedure) near-verbatim | Identify source-of-truth skill → convert the rest to a one-line pointer or `absorbed_into` merge |
| **Dead skill** | `use_count=0` AND `view_count=0` for **≥60 days** since `created_at` (or since last mass re-index if that's more recent — see Pitfall below), NOT `pinned` | Flag to Sasha — NEVER auto-delete; propose delete or keep with reasoning. Confirmed 05.07.2026: 60-day threshold, always requires Sasha's explicit approval. |
| **Orphaned usage.json entry** | Skill name exists in `.usage.json` but `skill_view(name)` returns "not found" / not in `skills_list()` — the skill file was deleted but its metrics record wasn't cleaned up | Propose removing the stale `.usage.json` entry (metrics cleanup, not a skill deletion — no `skill_manage(action='delete')` needed, just data hygiene) |
| **Oversized SKILL.md** | >14–20k chars (soft threshold from `hermes-agent-skill-authoring`; hard limit 100k) | Propose moving bulk content to `references/`, keep only the procedure in SKILL.md |
| **Stale technical detail inside one skill** | Dates/versions/URLs that may no longer be true (e.g. "VPN needed" after VM moved into corp domain) | Verify against live system state, not the skill's last-edited date — ask Sasha when unsure |
| **Dangling references** | A skill's `related_skills` or body text points to a deleted/renamed skill | Find via `search_files` for the old name across all SKILL.md + MEMORY.md + USER.md; fix or remove |
| **Frontmatter hygiene** | Missing `version`/`author`, or `platforms: [all]` (known to break indexing) | Low-risk — fix directly without asking |

## Procedure

1. **Collect candidates by category, one category at a time** — don't mix duplication findings with dead-skill findings with size findings in one big list. Read `.usage.json` once per pass, `skills_list()` once per pass.
2. **Present findings to Sasha per the universal open-question protocol** (see `hermes-memory-hygiene` → "Universal open-question protocol"): full list of findings first, then go one at a time, each with brief context + recommendation + numbered options.
3. **Act only after explicit per-item approval** — same discipline as memory hygiene, not batch-executed after one blanket "ok."
4. **Consolidation** → `skill_manage(action='delete', name=..., absorbed_into=<target-skill>)`. **Pure pruning** → `absorbed_into=''`.
5. **After every delete** — grep MEMORY.md, USER.md, and all remaining skills for the deleted skill's name (`search_files`) and fix any dangling "see skill X" references.

## Two run modes (mirrors hermes-memory-hygiene)

- **Interactive (first pass, and any ad-hoc "проверь скиллы"):** full audit, present findings, wait for per-item approval, execute, then report before/after skill count.
- **Scheduled (cron, once graduated from draft):** detect-only — collect findings, write them to the self-check report or a dedicated file, do NOT delete/merge anything unattended. Sasha reviews and approves in a follow-up interactive session.

**Status as of 05.07.2026: draft, interactive-only.** Do not attach to a cron until the first real pass is complete and this file has been corrected based on what was actually found (see Overview).

## What this skill does NOT do

- Does not touch MEMORY/USER PROFILE (that's `hermes-memory-hygiene`)
- Does not delete `pinned` skills (the tool itself refuses this)
- Does not flag a skill as dead purely on "not patched recently" — must combine with `use_count`/`view_count`

## Common Pitfalls

- **A plausible skill name is not proof of duplication** — before merging two skills, `skill_view` both and confirm the specific fact is actually restated, not just topically adjacent.
- **`use_count=0` alone isn't proof of "dead"** — a skill can be legitimately used without the counter incrementing in every code path (e.g. injected via cron `skills=[...]` rather than triggered by description match). Cross-check against cron job configs (`cronjob(action='list')` → `skills` field) before recommending deletion.
- **A mass `.usage.json` re-index resets `created_at` for the whole catalog at once — don't mistake that for real 0-day-old skills.** Confirmed 05.07.2026: 64/65 zero-usage skills all shared the same `created_at` (~10 days old at audit time) from one bulk re-registration event, which would false-trigger a naive "0/0 = dead" rule. Always check whether `created_at` clusters suspiciously across many skills before trusting age as a staleness signal — if most of the catalog shares one birth date, that date reflects a re-index, not real skill age. Prefer the 60-day-since-actual-first-use-opportunity threshold, and sanity-check outliers (one skill much older than its neighbors) as the strongest real signal.
- **Don't auto-delete anything** — every finding in this skill is a recommendation, execution needs Sasha's explicit per-item "да".

## Verification Checklist

- [ ] Findings grouped by category, not mixed
- [ ] Each finding has a clear recommendation + alternative (per universal open-question protocol)
- [ ] No delete/merge executed without explicit per-item approval
- [ ] Dangling references checked and fixed after any delete
- [ ] `.usage.json` read fresh, not assumed from memory
