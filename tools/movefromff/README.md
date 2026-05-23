# MoveFromFF

Tool to move meetings from Fireflies.ai → Obsidian WorkVault (`NewMeetings/`).

See ТЗ: `WorkVault/Meetings/MoveFromFF_TZ_v1.md` and `MoveFromFF_TZ_v1.1_addendum.md`.

## Quick start

```bash
# install
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# configure
cp .env.example .env
# edit .env, fill FIREFLIES_API_KEY, TELEGRAM_*, WORKVAULT_PATH

# run
python -m movefromff --mode test --dry-run    # plan only, 5 days
python -m movefromff --mode test              # download last 5 days
python -m movefromff --mode cron              # last 4h + 30min overlap
python -m movefromff --mode manual --from-date 2026-01-01 --to-date 2026-01-31
python -m movefromff --mode deleted-check     # check FF deletions (90d)
python -m movefromff --reconcile-only         # only disk↔registry reconciliation
```

## CLI flags

- `--mode {test,cron,manual,deleted-check}` (required unless `--reconcile-only`)
- `--from-date YYYY-MM-DD`, `--to-date YYYY-MM-DD` (manual mode)
- `--reconcile-only` — only run reconciliation, no FF fetch
- `--dry-run` — show plan without writing
- `--verbose` — DEBUG logging
- `--no-tg` — disable Telegram alerts

## Exit codes

- 0 — success
- 1 — partial success (some meetings failed)
- 2 — lock busy / preflight failed
- 3 — FF unavailable / auth
- 4 — fatal

## Project layout

```
movefromff/        # source
tests/             # pytest unit-tests (≥70% coverage)
scripts/           # run_cron.bat, run_manual.bat
```

## Tests

```bash
.venv\Scripts\pytest tests/ -v --cov=movefromff
```
