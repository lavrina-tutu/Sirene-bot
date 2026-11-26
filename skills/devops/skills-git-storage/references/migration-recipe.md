# Migration recipe: physical custom skill → git + dual symlink

Goal: a user-defined custom skill that physically lives in `~/.hermes/skills` (out of git) is moved to `~/hermes-workspace/skills` and exposed through two symlinks, per the storage canon. Store/bundled/unknown skills are never migrated.

## Invariants (test each before/after)

- Sidecar SHAs unchanged by cp/mv: `.usage.json`, `.usage.json.lock`, `.hub/lock.json`, `.locks`.
- No dangling symlink anywhere (`find -L <tree> -xtype l` is empty).
- Real file of every migrated skill resolves under `hermes-workspace`.
- No copy left behind (single canonical location).

## Per-skill steps (dirs are `<cat>/<name>`, root-level skills have no cat)

1. **Classify.** Confirm the skill is user-defined (author ∈ {agent, sirene, ''}, no `.hub`/`.locks` sidecar in its own catalog). If store/bundled or unknown — stop, report, do not touch.
2. **Dedup two trees.** If the name also exists physically in `profiles/default/skills`, compare SHA-256 of the whole catalog (all files, not just SKILL.md). Identical → canonical copy is `~/.hermes/skills` (the working one); the other is left alone and covered by the new symlink. Diverging → stop, report, both untouched (no auto-resolve).
3. **Backup.** `cp -r <src> ~/.hermes/_Archives/skill-git-migrate-<run-id>/<logical-path-underscored>/` (run-id unique per run). Archive is the safety net only.
4. **Move.** `mv <src> ~/hermes-workspace/skills/<cat>/<name>` (mkdir -p all parents).
5. **Profile symlink (abs target):** `ln -s /home/tkachenkoav/hermes-workspace/skills/<cat>/<name> ~/.hermes/profiles/default/skills/<cat>/<name>` (mkdir -p parents).
6. **Top-level symlink (relative target):** `ln -s <rel> ~/.hermes/skills/<cat>/<name>` where `<rel>` leads to `profiles/default/skills/<cat>/<name>` and the number of `../` equals the depth in `~/.hermes/skills`:
   - root: `../profiles/default/skills/<name>`
   - cat: `../../profiles/default/skills/<cat>/<name>`
   - cat/subcat: `../../../profiles/default/skills/<cat>/<subcat>/<name>` (mkdir -p all parents in both catalogs)

Steps 4–6 form one batch per skill; mv and ln are separate syscalls, so a live Hermes can briefly see a missing path until a new session starts (expected — do not restart the gateway).

## Idempotence & recovery

- Before each step, check the target state: correct symlink → skip; target exists and is not our symlink → never clobber, log and stop.
- If any step of a skill fails, a trap returns that skill to its prior state (rm created symlinks, `mv` dir back from workspace), logs it, and the run continues with the next skill.
- Append an operation log (LIST) for rollback.

## Rollback

Restore in reverse order of LIST: `rm` created symlinks → for a plain move, `mv` the dir back from workspace to the ORIGINAL logical path (never `cp` from archive — that leaves two copies; archive stays as the safety net). For a name that had a pre-existing divergent workspace copy (A2), restore that prior workspace version and the src from archive.

## Git

`git add skills/<cat>/<name>` for exactly the migrated paths, `git commit`; do not touch unrelated working-tree changes. Push is handled by the workspace autosync.
