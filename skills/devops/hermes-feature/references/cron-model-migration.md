# Cron and profile model migration notes

## Verified migration pattern

When bulk-updating model families across cron jobs and a profile, verify three layers separately:

1. **Profile runtime model** — the active model used by the profile is the one in `~/.hermes/profiles/<profile>/config.yaml` (`model.default` + `model.provider`), not `profile.yaml` (that file may only carry description metadata).
2. **Cron job models** — inspect `~/.hermes/cron/jobs.json` directly; `cronjob list` may still show stale names in `name`/`prompt`/`last_error` even after the effective model fields are updated.
3. **Historical error text** — if the goal is to remove stale references to old models, clear or rewrite `last_error` / `last_delivery_error` only after confirming the job is no longer using those values for diagnostics.

## Verification recipe

- Read profile runtime config:
  - `~/.hermes/profiles/<profile>/config.yaml`
- Read cron job records:
  - `~/.hermes/cron/jobs.json`
- Search for old model strings after migration:
  - `claude-sonnet-4-6`
  - `claude-opus-4-7`
  - `claude-haiku-4-5`
- Ensure `reasoning_effort: high` is present only on jobs migrated from the old Opus slot to the DeepSeek reasoning model.

## Why this matters

The profile shell (`profile.yaml`) is not the source of truth for model selection. Cron jobs also preserve historical execution errors, so a successful migration can still leave old model names behind unless those fields are cleaned intentionally.
