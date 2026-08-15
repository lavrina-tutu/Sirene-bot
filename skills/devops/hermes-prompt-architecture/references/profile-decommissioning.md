# Profile decommissioning — consolidating a dev profile back into the main one

When a split-profile setup (main + dev profile, e.g. `default` + `tz-dev`) is collapsed
back into a single profile, the routing scaffolding built for the split (see Pattern 1 in
SKILL.md) must be unwound. Precedent: `tz-dev` decommissioned into `default`/«Сирень»
(2026-08-13).

## Checklist — sweep every prompt layer for the retired profile's identity

Search by BOTH the profile id AND its localized alias(es) (e.g. `tz-dev` + «Стажер» + the
old name «Архитектор»). Use the P12 grep pattern (`grep -rn`, NOT `search_files`, inside
`~/.hermes`).

1. **SOUL.md** — remove/replace the routing one-liner:
   `«передаю в профиль tz-dev (Стажеру)»` → `«веду dev-работу сама через скиллы tz-workflow/hermes-feature»`.
2. **AGENTS.md** (project context, CWD-based) — replace the header
   `«Profile tz-dev (Стажер) handles TZ, skills, and Hermes tools dev.»` with the
   surviving profile (`Profile default (Сирень) …`).
3. **Skills** — grep each dev skill's `SKILL.md` AND `references/*` for the profile id;
   fix mentions. **Do NOT touch role names** — «архитектор» / «исполнитель» /
   «координатор» are Cursor CLI model roles, not the profile, and survive consolidation.
4. **memories/MEMORY.md** — stale records like «профиль переименован из … в …» become
   obsolete; replace with a one-line decommission fact (date + «заменён на default»).
5. **Cron** — inspect `profiles/<name>/cron/jobs.json`: only *recurring* jobs need
   migration. One-shot `once` jobs that already ran are historical noise.
6. **Profile folder fate** — delete after backing up `config.yaml` to
   `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`, or leave deactivated.
   Recommendation: delete-after-backup (a half-live profile is the source of future
   cron/config confusion).

## Key architectural correction (user-corrected, 2026-08-13)

Do **NOT** re-introduce a separation mechanism after consolidation.

- Dev vs non-dev tasks are already separated by the **trigger words** in `tz-workflow`
  and `hermes-feature` — those skills load only on dev triggers. No extra routing,
  routing table, or `workdir`-vs-`SOUL.md-block` decision is needed.
- Content work (ТЗ drafting, implementation) happens inside Cursor CLI (`agent -p`)
  with **explicitly-directed context**, so «personality tokens leaking into Cursor» is a
  phantom concern. There is no token-leak problem to solve.
- The only real change to the main profile is the single SOUL.md line (item 1).
- `TZ/AGENTS.md` (project context) still reaches Cursor automatically via
  `cd TZ && agent -p` (workdir), but should **NOT** be injected into the chat context of
  the main profile — the rules already live in the skills.

## Pitfall observed

`search_files` (ripgrep) returns 0 inside `~/.hermes` because the directory is hidden;
`rg --hidden` alone also misses files that are gitignored. Plain `grep -rn` descends into
hidden + ignored dirs without flags and is the reliable tool for these sweeps. (This is
already documented as P12 in SKILL.md — kept here for the decommissioning context.)

## Execution pitfalls (decommission sweep)

- **Sweep the WHOLE tree, not one category.** `grep -rn <id> ~/.hermes/skills/devops/*/SKILL.md`
  silently misses skills living under `productivity/`, `persona/`, `research/`, etc.
  Real misses (2026-08-14): `mattermost-loop-api` (productivity/) and `sirene-chat-friends`
  (persona/) both survived a `devops/`-scoped sweep. Use `grep -rn <id> ~/.hermes/skills`
  (whole tree) or Python `os.walk(base, followlinks=True)`.
- **`find` does NOT follow symlinks; `grep -rn` does.** Most skills are symlinks —
  `~/.hermes/skills/<cat>/<skill>` → `~/hermes-workspace/skills/<cat>/<skill>` (the git
  canonical source) — but a few are REAL "non-synced" directories edited in place
  (e.g. `hermes-prompt-architecture`, `hermes-multi-profile-skills`). Consequently
  `find ~/.hermes/skills -name SKILL.md` misses the symlinked skills. Before editing any
  skill, run `readlink -f <skill-dir>` to learn its canonical path and edit THERE (this is
  the "несинканная копия" pitfall from hermes-ops, applied to the sweep itself).
- **`read_file` can flag valid UTF-8 SKILL.md files as "binary".** Emoji (⚠️) or a stray
  byte trips the heuristic. Read such files with `grep -n` / `sed` / Python; perform the
  actual edit by line-number in Python (`text.split('\n')` → replace → `'\n'.join`), which
  also sidesteps backslash-escaping drift (e.g. a literal `\<name\>` in the file) that
  breaks `patch` old_string matching.
- **Gateway guard false positive.** A `terminal` command that touches the
  `hermes-gateway-setup` skill path can be rejected as "cannot restart the gateway". For
  those files use `read_file` / `patch` / `execute_code` instead of `ls`/`grep` on the
  literal path.
