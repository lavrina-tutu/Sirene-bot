---
name: skill-portability
description: "поделись/упакуй скилл: упаковка Hermes skills для обмена"
version: 1.0.1
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [skills, packaging, portability, export, sharing, depersonalization]
    related_skills: [hermes-agent-skill-authoring, all-skills-hygiene, hermes-memory-hygiene, hermes-gateway-setup]
---

# Skill Portability — packaging skills for another Hermes agent

## Overview

Class-level procedure for taking one or more skills from `~/.hermes/skills/` and turning them into a portable bundle another Hermes agent/user can install and use immediately — without any of the exporting user's personal details leaking across. This is a recurring need, not a one-off: every export should go through the same depersonalization discipline, decided explicitly (not case-by-case) after the first time this came up.

**Distinction from `hermes-agent-skill-authoring`:** that skill governs contributing a skill to the hermes-agent *git repo* itself (in-tree, validator-enforced, `skills/<category>/<name>/`). This skill governs exporting a *user-local* skill (`~/.hermes/skills/...`) to a **different person's** Hermes instance — no git, no validator, the concern is depersonalization + packaging + delivery, not repo conventions.

## When to Use

- User asks to share/export/package a skill (or several) for another Hermes agent, another user, or another instance/profile
- User generalizes a one-off export into a standing rule ("do this for all future skill shares") — treat every subsequent export request the same way, don't re-litigate depersonalization case by case

**Don't use for:** in-repo skill authoring for the hermes-agent project (`hermes-agent-skill-authoring`), routine skill hygiene within the same agent (`all-skills-hygiene`).

## Procedure

1. **Scope** — confirm exactly which skill(s) go in the bundle. Don't include smaller-scope things (a single reference file) unless asked; don't silently widen to "everything related."
2. **Read each skill in full** (`skill_view`) before touching anything — depersonalization requires seeing the actual content, not guessing from the description.
3. **Audit for hardcoded specifics** — this is the step that must happen on EVERY export, not just the first:
   - The exporting user's name/handle (anywhere it's used as an example person, not as a generic "the user")
   - Absolute paths specific to the exporting machine (`/home/<user>/...`, drive letters, VM hostnames)
   - Names of OTHER skills/cron-jobs/tools that only exist in the exporting user's own setup (e.g. a specific self-check cron job name, a specific persona-skill name) — generalize to a description of the *role* that thing plays ("a self-check cron", "a persona skill") instead of the specific name
   - Company/org-specific systems, URLs, or internal tool names used as illustrative examples — replace with generic placeholders unless the skill's whole point IS that specific integration (e.g. a Jira/Confluence skill is allowed to be integration-specific; a generic hygiene skill should not accidentally carry the exporting org's name)
   - Verify with `search_files` (grep) across the drafted bundle for the exporting user's name/handle and any machine-specific path fragments — do this AFTER drafting, as a final check, not only as an upfront read
4. **Generalize worked examples, don't delete them** — a skill's worked-example/pitfall sections are often its most valuable content. Rewrite specifics into illustrative-but-generic form ("a process skill shrunk from 58K → 28.4K" instead of naming the exact skill and exact session date) rather than stripping the example out entirely.
5. **Package**:
   ```
   <bundle-name>/
   ├── INSTALL.md                    ← install steps + what to verify + what to adapt
   ├── <skill-1-name>/SKILL.md  (+ references/, templates/, scripts/ if any)
   └── <skill-2-name>/SKILL.md  (+ ...)
   ```
   `INSTALL.md` must cover: where to extract to (`~/.hermes/skills/<any-category>/`), the fact that skill loaders are session-cached (new session required to see it), how to verify (`hermes skills list`), and a short note on what the receiving user may want to adapt further for their own environment.
6. **Archive** — `tar czf <bundle-name>.tgz -C <staging-dir> .`, store under `~/.hermes/_Archives/` (same place as config backups — consistent with existing backup conventions).
7. **Deliver** — see `hermes-gateway-setup` → "Deliverable Mode: verify actual file delivery" for the file-attachment delivery step and its known pitfalls. Always tell the user the exact absolute path as a fallback in the same message, in case the attachment doesn't actually arrive.
8. **Clean up staging** — remove the temporary unpacked staging directory once the archive is built; don't leave depersonalized copies scattered in `/tmp` or elsewhere.

## Common Pitfalls

- **Don't stop at "the parts I remember are personal."** Grep the drafted bundle for the exporting user's name/handle and machine-specific path fragments as an explicit final step — memory of what you wrote is not a substitute for a real search over the final text.
- **Don't generalize a skill's identity into uselessness.** A skill built around a specific external system (a specific SaaS product, a specific internal tool the receiving user won't have) doesn't need to be genericized if that specificity IS the skill's value — only strip details that are about the *exporting user personally* (their name, their machine, their unrelated other tools), not the skill's actual subject matter.
- **A single "share this" request that gets generalized ("do this for all future exports") is a standing rule, not a one-off decision** — apply the same depersonalization discipline automatically on every subsequent export without re-asking whether it's needed this time.
- **Don't trust a reported delivery success for the archive itself.** Treat the archive delivery exactly like any other file-attachment delivery (see `hermes-gateway-setup` pitfall) — confirm with the user that the file actually arrived before considering the task done.

## Verification Checklist

- [ ] Scope of the bundle was explicit (not silently widened)
- [ ] Every skill in the bundle was read in full before editing
- [ ] `search_files` grep over the drafted bundle for the exporting user's name/handle and machine paths returned zero hits
- [ ] Worked examples were generalized, not deleted outright
- [ ] `INSTALL.md` present with: extraction path, session-cache caveat, verification command, adaptation notes
- [ ] Archive stored under `~/.hermes/_Archives/` (or the exporting agent's equivalent backup location)
- [ ] Staging directory cleaned up after archiving
- [ ] Delivery of the archive itself was confirmed by the user, not assumed from a "success" report
- [ ] Absolute path to the archive was given as a fallback alongside the attachment attempt
