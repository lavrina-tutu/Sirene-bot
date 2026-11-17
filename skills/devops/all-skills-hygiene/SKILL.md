---
name: all-skills-hygiene
description: "проверь скиллы: аудит дублей и stale"
version: 1.4.0
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

## Purpose and modes

Audit the skills layer for duplication, stale or dead skills, oversized files, broken references and trigger conflicts. Use for «проверь скиллы», «почисти скиллы», «ревизия скиллов», audit skills, export of skills, or a scheduled audit. Do not use for MEMORY/USER PROFILE cleanup or authoring a single new skill; use the respective skills. Audit findings do not authorize runtime code fixes.

Interactive runs present findings and act within the user's explicit scope. Scheduled runs are **detect-only**: report findings; do not delete, merge, rewrite or create a cron. Existing authorization for a specific mechanical cleanup is sufficient for that scope; it does not authorize deleting skills or semantic merges. Never auto-delete pinned skills. Record open bugs separately for the appropriate workflow.

## Evidence and categories

Read `skills_list()` and `~/.hermes/skills/.usage.json` once per pass. Inspect all categories and active roots, the actual installation profile and runtime visibility. Use usage fields `use_count`, `view_count`, `last_used_at`, `last_viewed_at`, `patch_count`, `pinned`, `state`, and `created_at`; cross-check zero use against cron `skills` and other callers.

- **Duplicate:** read both implementations and confirm the same fact, not just similar names. Identify the owner; preserve the short independent constraints needed for self-contained loading.
- **System stale:** `state=stale` is a platform signal and a priority candidate even without the dead-skill threshold; investigate the file and use before recommending action.
- **Dead candidate:** zero use AND zero views for at least **60 days**, not pinned; never delete automatically. A shared `created_at` after mass re-index is not actual age; check outliers and other evidence.
- **Index noise:** stale + zero use/views, neither pinned nor `ESSENTIAL_SKILLS`; disabling an index entry leaves files on disk and requires authorized scope. No cron deletion.
- **Orphan:** usage entry exists but skill is absent from both the actual inventory and runtime; metrics cleanup is distinct from deleting a skill.
- **Oversized:** compare to current authoring guidance, then plan a structural rewrite with explicit scope and verification.
- **Stale detail:** verify actual source, tests and callers; distinguish fixed, still open, and unknown. Do not automatically turn an audit into a live fix.
- **Dangling references/frontmatter:** inspect references to renamed/deleted skills and missing metadata; use valid platforms, not `[all]`.

Full original category signals: `references/audit-categories.md` (historical conflicting instructions are superseded here).

## Procedure and operating conditions

1. Collect and report findings by category. For decisions outside authorized scope present a recommendation and alternatives, one item at a time. Respect pinned and essential skills.
2. Check both implementations before a merge; group independent work only when files and ordering do not overlap. Retain a compact rule in each independently loaded skill when needed for safe operation.
3. For an authorized deletion/merge use the appropriate `skill_manage` operation (`absorbed_into` for consolidation), then inspect MEMORY.md, USER.md and remaining skills for dangling references. Do not infer deletion permission from a documentation cleanup.
4. For a large rewrite provide a concrete plan, mechanical/semantic boundary, backup outside the indexed tree and acceptance checks. Follow current authoring and workflow canon; assess actual results and errors rather than selecting a model from one failed one-liner. Do not require a cron as the universal mechanism.
5. Verify claims such as «кажется исправили» in all affected source layers and callers. Report evidence and uncertainty; obtain the applicable authorization before changing behavior.
6. Audit description triggers by meaning and investigate overlapping loads. Preserve request classes and exclusions, and verify current routing rather than applying historical examples as current policy. See `references/trigger-audit.md`.

The original rewrite handoff and backup details are in `references/rewrite-handoff.md`; old cron/model choices and the requirement to preserve every H2 are historical. Check **coverage of original meanings and links**, not identical headings.

## Export

For an authorized export, read every skill, depersonalize a scratch copy, inspect it for identifying strings, package each skill with its resources and an INSTALL guide, and verify delivery as an attachment. Preserve the transferable lesson. Full procedure: `references/skill-export.md`.

## Verification

- Group findings by category with evidence, recommendation and alternatives; distinguish stale, dead, index noise and orphan.
- Confirm 60-day evidence, pinned/essential exclusions, callers and runtime visibility before recommending removal.
- Confirm all changes are in scope, no semantic deletion is implied by a mechanical cleanup, and all affected links resolve.
- For rewrites verify backup, frontmatter, original meaning and link coverage, before/after size and runtime loading; report a summary rather than dumping the file.
- Historical examples: `references/audit-history-202607.md` and `references/hygiene-incident-history.md` (not current instructions).
