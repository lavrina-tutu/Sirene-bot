---
name: hermes-multi-profile-skills
description: "скиллы пропали: sync workspace и профиль Hermes"
version: 2.1.0
author: agent
tags: [hermes, skills, profiles, symlinks, git, sync]
platforms: [linux]
---

# Hermes Multi-Profile Skills

## Scope and architecture

Use when custom skills are missing, links fail, skills need synchronization, restoration after update, or an audit of `hermes-workspace/skills/` and links. External-provider isolation belongs to `hermes-honcho-setup`. This skill covers custom skills in default, not mass synchronization of other profiles.

Canonical custom skills live in `~/hermes-workspace/skills/` (git). The intended chain is workspace → `~/.hermes/profiles/default/skills/` → live `~/.hermes/skills/`. The live directory is what runtime scans. `sync-to-hermes.sh [profile]` defaults to default and creates/repairs profile links; `restore-all-skills.sh` calls `sync-to-hermes.sh default` and is idempotent. Neither establishes that the separate live layer exists. The old tz-dev layer was decommissioned: do not recreate it.

Keep bundled and hub-managed skills as physical installations; the hub installer rejects symlink install paths. Before conversion classify custom/bundled/hub using provenance and `.hub/lock.json`, and back up any eligible custom physical folder. Do not replace a bundled or hub folder with a symlink.

## Direction and schedules

Skills flow **git workspace → profile → live runtime**. WorkVault is the source of truth for ТЗ and data and flows **WorkVault → git mirror** (`hermes-workspace/Hermes-Backlog`), never back from an old mirror to WorkVault. `restore-all-skills.sh` restores skill links, not WorkVault data. Never overwrite workspace skills with a runtime copy during autosync.

The existing autosync job `5d16b96a9ed5` runs at 02:00 via `autosync_full_with_cleanup.sh`; restore job `74c93fa1e357` runs at 03:00. Preserve their existing configuration. `~/.hermes/scripts/autosync_github.sh` is referenced by the existing sync setup; inspect the actual chain before making any operational claims. Historical data-loss and ТЗ rollback: `references/autosync-bug-fix.md`.

## Diagnosis and operation

1. Search both workspace and live roots; explicitly follow or resolve symlinks. Ordinary `find` without follow does not traverse symlink directories. Inspect `readlink -f` for each layer and identify physical shadow copies.
2. Compare the resolved path and content/version at workspace, profile and the actual live path for each affected custom skill. A sync report or profile link alone does not establish runtime visibility; check `skill_view`/the loader in a new session as applicable.
3. For authorized setup or recovery use the existing `sync-to-hermes.sh default` and `restore-all-skills.sh` interfaces, checking each layer. A default restore does not automatically restore the live layer. Full commands and inventory: `references/skill-sync-recipes.md`; diagnosis and shadow copies: `references/live-skill-links.md`.
4. For curator backup recovery use `references/skills-inventory.md`. Do not apply restoration as a documentation check. Preserve hub/bundled installations and back up eligible custom content before any conversion.
5. Execute multi-step recovery, migration or setup one step at a time; check each result, stop on error and report before continuing. This is Sasha's rule of 03.08.2026.
6. Cover backup ignore patterns with `.`, `-`, and `_` separators, then verify tracked and ignored files and that they do not re-enter the index. See `references/backup-ignore-patterns.md`.

## Verification and history

- Confirm custom/bundled/hub classification, backup and permitted scope before changing links.
- Confirm no broken links, both link layers, runtime content/version, and availability in the relevant loader; inspect shadow copies rather than trusting source version alone.
- Verify sync direction and actual scheduled entrypoints without running production jobs.
- Historical architecture: `references/historical-tz-dev-architecture.md`, `references/architecture-implementation-2026-08-03.md`, `references/skill-storage-audit.md`; these are snapshots, not a mandate to revive tz-dev.
- Non-default cron context: `references/cron-multi-profile-pitfall.md`.
