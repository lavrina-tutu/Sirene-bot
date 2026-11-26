---
name: skills-git-storage
description: "Use when: аудит хранения и переноса скиллов в git."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
tags: [hermes, skills, storage, git, migration, symlink]
metadata:
  hermes:
    tags: [hermes, skills, storage, git, migration, symlink]
    related_skills: [all-skills-hygiene, hermes-multi-profile-skills, skill-portability]
---

# Skills: git-backed uniform storage

Audits and maintains the *storage topology* of the skills layer — that custom skills are versioned in git and laid out uniformly — as distinct from `all-skills-hygiene`, which handles content duplication / dead skills / bloat. Trigger: «проверь что скиллы хранятся единообразно», «скиллы синкаются с git», «перенеси скиллы в git», «скиллы пропали». For content dedup use `all-skills-hygiene` instead; for single-skill authoring use `hermes-agent-skill-authoring`.

## When to Use

- «проверь что скиллы хранятся единообразно», «скиллы синкаются с git», «перенеси скиллы в git», «скиллы пропали» — audit or migrate the storage topology.
- Not for content duplication / dead skills / bloat (that is `all-skills-hygiene`) and not for authoring one skill (`hermes-agent-skill-authoring`).

## Canon topology (this machine)

- Source of truth for custom skills: `~/hermes-workspace/skills/<cat>/<name>` (git repo, autosync to GitHub).
- `~/.hermes/profiles/default/skills/<cat>/<name>` → symlink to the workspace ABS path.
- `~/.hermes/skills/<cat>/<name>` → symlink to profiles/default (relative; number of `../` == depth in `~/.hermes/skills`; root-level skills have no category).

Anything that deviates is a storage violation: skills with a physical file under `~/.hermes/skills` or `profiles/default` are out of git and at drift risk.

## Drift source

`skill_manage` writes new and edited skills physically into `~/.hermes/skills`, NOT into the workspace — so a custom skill edited via skill_manage silently diverges from its git copy or is never versioned. `skill_manage` also cannot address skills that live only in the general `~/.hermes/skills/<cat>/` catalog (it resolves against the active profile's dir) — to audit/edit those, operate directly on the files (realpath/patch), not via skill_manage.

## Verify git before reworking a skill (Sasha's rule)

A user-defined custom skill can be physically present in `~/.hermes/skills`
(SKILL.md has a real file, not a symlink → out of git, at drift risk) even though
the workspace is the canonical store. Before starting to rework ANY custom skill,
sync its current state to git first so the work isn't lost: classify by realpath;
if the physical file is under `~/.hermes/skills`/`profiles/default` (not a symlink
into `hermes-workspace`), copy it into the workspace tree (`cp -r`), commit and
push, and note the dual physical copy as a topology item to resolve to the
canonical dual-symlink later — do not leave a half-done rework on top of an out-
of-git file. For the rework itself, the current SKILL.md in `~/.hermes/skills` is
the live one Hermes loads even after the commit; edit it (or the committed copy)
per the migration recipe, keeping behavior consistent.

## Audit procedure

1. **Classify by realpath, never by name or bare `find`.** For every SKILL.md walk both `~/.hermes/skills` and `profiles/default/skills`, resolve `os.path.realpath`, and decide: physical file under `hermes-workspace` (in git — ok) or not (out of git — candidate). A skill name can have TWO real copies (`~/.hermes/skills` AND `profiles/default`) with diverging content.
2. **Custom vs store/bundled**, mutually exclusive by priority: store/bundled if `author` (YAML frontmatter) is a known third party (Nous Research / Ben Barclay / Chris Kim / Orchestra Research / Teknium / Hermes Agent) OR the skill's own catalog contains a `.hub/lock.json` / `.locks` sidecar; user-defined if `author ∈ {agent, sirene, ''}`; else unknown.
3. **Only user-defined custom skills belong in git-symlink storage.** Store/bundled skills MUST stay physical — the skill-store/hub installer rejects a symlink target (`Unsafe install path`), so converting one breaks its install/update. Physical store skills, covered by the full VM tgz backup, are the correct non-negotiable exception to "everything in git". Unknown classification: do not touch, report.
4. Report counts and the conflict/left-behind lists; never auto-resolve a name with two diverging physical copies — present it for a decision.

## Migration recipe

Backup → move → dual symlink → verify. Full idempotent step-by-step in `references/migration-recipe.md`. Key invariants: backup each dir to `~/.hermes/_Archives/skill-git-migrate-<run-id>/<logical-path-underscored>/`; `mv` into workspace (mkdir parents); create BOTH symlinks in the same batch (mv and ln are separate syscalls — a live Hermes may briefly see a missing path until the next session start); per-skill trap returns the skill to its prior state on any step failure without aborting the run; sidecar SHAs (`.usage.json`, `.usage.json.lock`, `.hub/lock.json`, `.locks`) must be unchanged before/after.

## Pitfalls

- **`find` without `-L` undercounts skills** — it does not descend into directory symlinks, so physical files reached only through a symlink are missed; and pathlib `.is_symlink()` on intermediate components misleads. Inventory with `find -L` + `realpath` classification.
- **Store/bundled skills cannot be symlinked** — the hub installer validates the install path and rejects a symlink target, breaking their install/update. Leave them physical.
- **A same-named skill can exist physically in both `~/.hermes/skills` and `profiles/default` with different content** — decide by realpath; if the two SHA-catalogues diverge, both are left untouched and reported, never auto-merged.
- **Rollback must not leave a copy behind** — restore an A1 move by `mv` back from the workspace to the original logical path, not by `cp` from the archive (else two copies survive). Archive is the safety net, not the restore source for the primary move.
- **Do not rewrite this kind of inventory by hand in the session** — counting 100+ skills is error-prone; delegate the reliable inventory + migration to an executor (Codex) with the explicit plan, or drive it with a script, and accept only its manifest/realpath output.
- **Re-pointing the workspace sync to a DIFFERENT GitHub account — patch BOTH remote set-url copies.** The push script has two live copies of the remote constant: `~/.hermes/scripts/autosync_github.sh` (the one the cron runs) and `~/hermes-workspace/scripts/autosync.sh` (its mirror inside the workspace repo); each runs `git remote set-url origin ...` on EVERY launch. Patching only one leaves the other to reset origin back to the old account on the next sync. When a user's account is being deactivated but its repos must not be deleted: re-point to the replacement account's repo (which may be named differently, e.g. not `hermes-workspace` — check `GET /user/repos`), put the target's HTTPS token into `~/.git-credentials` (login:token, chmod 600) + `git config --global credential.helper store` so the cron pushes without the old SSH key, resume the cron (job `5d16b96a9ed5`), then verify by a real push and an external API read of the target repo (branches/commits/contents) — not by the script's stdout alone. Never delete the deactivated account/repos; only detach the remote.

## Verification checklist

- [ ] Classified by realpath, not name
- [ ] Only user-defined custom skills migrated; store/bundled/unknown untouched
- [ ] Dual symlinks resolve (readlink+realpath); 0 dangling symlinks
- [ ] Sidecar SHAs (usage.json, .locks) unchanged before/after
- [ ] Conflict/left-behind lists present and un-auto-resolved
