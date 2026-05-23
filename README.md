# hermes-workspace

Consolidated personal workspace for Hermes Agent.

Combines:
- **config/** — personal Hermes config (`config.yaml`, sanitized — no secrets)
- **skills/** — user skills (mirror of `~/AppData/Local/hermes/skills/`)
- **tools/** — automation tools family (MoveFrom*, WorkVault helpers)
  - `tools/movefromff/` — FreshFlow → Markdown summariser (formerly the `workvault-tools` repo)
  - `tools/shared/` — shared infra (logger, lock, config loader); empty for now
- **workflows/** — cross-tool processes
- **docs/** — backlog, vision, TZ, self-checks
- **upstream/** — pin/changelog for the upstream `NousResearch/hermes-agent` clone
- **scripts/** — autosync, upstream update/rollback, doctor

## Source of truth

- **Local is source of truth** for: `~/AppData/Local/hermes/skills/` and `~/AppData/Local/hermes/config.yaml`.
- This repo is the **mirror / backup**, synced one-way by `scripts/autosync.sh` (cron job `bc1b0ae442f0`).
- For `tools/*` — this repo IS the source of truth; local clones run from here.

## Quick start

```bash
# MoveFromFF
cd tools/movefromff
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
python -m movefromff --help
```

## Upstream tracking

The upstream `NousResearch/hermes-agent` lives in a **separate clone** at
`~/Documents/Cursor_projects/hermes-agent` — not inside this repo.
Pin file `upstream/pinned-version.txt` records the commit currently in use.
See `upstream/README.md` for update/rollback procedure.

## Layout

```
config/        skills/        tools/        workflows/
docs/          upstream/      scripts/
```

## History

- 2026-05-23 — initial consolidation from `workvault-tools` + `hermes-config`.
