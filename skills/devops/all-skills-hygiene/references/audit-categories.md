Historical source: the active rules and scope in SKILL.md supersede conflicting model, live-fix and pointer instructions below.

## Finding categories (what to look for)

| Category | Signal | Action |
|---|---|---|
| **Content duplication** | 2+ skills state the same fact (URL, token location, procedure) near-verbatim | Identify source-of-truth skill → convert the rest to a one-line pointer or `absorbed_into` merge |
| **System-flagged stale** | `.usage.json` entry has `"state": "stale"` (set by the platform itself, not a computed heuristic) | Treat as a priority candidate even if it doesn't independently meet the 60-day zero-usage bar — investigate first (file may still exist and be topically relevant), present alongside dead-skill findings, same one-item-at-a-time approval |
| **Dead skill** | `use_count=0` AND `view_count=0` for **≥60 days** since `created_at` (or since last mass re-index if that's more recent — see Pitfalls), NOT `pinned` | Flag to Sasha — NEVER auto-delete; propose delete or keep with reasoning |
| **Index noise (stale∩zero)** | `.usage.json`: `state=stale`, `use_count=0`, `view_count=0`, not `pinned`, not `ESSENTIAL_SKILLS` | Prune the **index** via `skills.disabled` in `config.yaml` (`save_disabled_skills`) — files stay on disk; NEVER auto-delete; no cron delete |
| **Orphaned usage.json entry** | Skill name exists in `.usage.json` but `skill_view(name)` returns "not found" / not in `skills_list()` — the skill file was deleted but its metrics record wasn't cleaned up | Propose removing the stale `.usage.json` entry (metrics cleanup, not a skill deletion — no `skill_manage(action='delete')` needed) |
| **Oversized SKILL.md** | >14–20k chars (soft threshold from `hermes-agent-skill-authoring`; hard limit 100k) | Delegate a structural rewrite to Opus (see "Delegating structural fixes to Opus" below) — don't rewrite a 50k+ file yourself turn-by-turn |
| **Stale technical detail inside one skill** | Dates/versions/URLs that may no longer be true (e.g. "VPN needed" after VM moved into corp domain); also applies to individual entries in a `## Common Pitfalls` list describing a specific code bug | Verify against live system state (read the actual current source, not the skill's last-edited date) — ask Sasha when unsure. **If verification shows the bug is still genuinely open** (not just stale prose), this audit can extend into a live fix in the same pass: minimal patch + a regression test proving the exact failure mode + full test-suite run, THEN collapse the pitfall text to "FIXED — <what changed>, see `<test file>`" (keep the entry, don't delete it — the lesson stays useful even once the code is fixed). **If already fixed elsewhere**, collapse to a short confirmation note instead of re-describing the original incident at length. |
| **Dangling references** | A skill's `related_skills` or body text points to a deleted/renamed skill | Find via `search_files` for the old name across all SKILL.md + MEMORY.md + USER.md; fix or remove |
| **Frontmatter hygiene** | Missing `version`/`author`, or `platforms: [all]` (known to break indexing) | Low-risk — fix directly without asking |

