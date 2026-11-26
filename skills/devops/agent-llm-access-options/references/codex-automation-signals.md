# Codex automation fingerprint — audit recipe

How to determine, from local Codex logs, whether an account was used as an automated API backend (and to distinguish our signals from content violations when a vendor deactivates an account). Also useful as a pre-trip checklist before routing autonomous work through any human-login plan.

## Data source

`~/.codex/state_5.sqlite` — table `threads` (one row per session/rollout). Query with python3 sqlite3 module (`sqlite3` CLI may be absent):

```python
import sqlite3, datetime
conn = sqlite3.connect('/home/tkachenkoav/.codex/state_5.sqlite')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
```

Key columns of `threads`: `first_user_message` (prompt), `source` ('exec' = CLI/script), `has_user_event` (0 = no interactive human input), `tokens_used`, `created_at`/`updated_at` (**unix SECONDS, not ms** — do not divide by 1000), `model`, `model_provider`, `cwd`.

## Signal queries

- Automation ratio: `SELECT count(*), sum(CASE WHEN has_user_event=0 THEN 1 ELSE 0 END) FROM threads` — all rows with 0 user events = fully automated account.
- Source mix: `SELECT source, count(*) FROM threads GROUP BY source` — only 'exec' = no interactive use at all.
- Session duration: `updated_at-created_at`; count `<60` — sub-minute sessions are bot-like (no human think time).
- Start intervals: sort `created_at`, diff neighbors; peers `<30 s` apart = batch launches; exact repeating intervals (~1860 s ±3 s) = cron pinger.
- Hour-of-day: `strftime('%H', created_at,'unixepoch','+3 hours')` — night traffic (23–06) = 24/7 automation.
- Prompt patterns: `first_user_message` grouping — repeated verbatim probes («Reply with exactly: OK», «Назови 2+2», «hi»), single-style task packets, canary file writes («write REV-CANARY …») are liveness/smoke markers.
- Model/provider mix + rejection strings: findViewById errors like «not supported when using Codex with a ChatGPT account» show the server detected a subscription account queried outside its product surface.
- Volume: tokens/day and sessions/day per account; 100M+ tokens/day or 10k+ calls/day are order-of-magnitude above any human subscription.

## Interpretation

Any combination of: all-`exec` + zero user events, sub-minute sessions, batch or cron-precise intervals, night traffic, repeated probe prompts, and 100M-token-scale volume = the account was used as an API backend. Signals are generated server-side (source, event stream, timing) — local masking (delays, shuffled prompts) cannot remove them.

Content violations (jailbreaks, harmful content) are a separate axis; check session prompts before blaming volume, but volume+automation alone is a valid deactivation cause.

## Prevention checklist for any human-login plan

- No cron/scheduled/CLI batches through the subscription account.
- No model-prompt liveness probes (curl the API endpoint for HTTP status instead).
- No smoke/canary prompts fired repeatedly.
- Volume kept in the interactive band; if the workload is bulk — API key or agent-first plan.
- On deactivation: expect a final refusal on re-appeal; plan the fix (channel separation + API key), do not re-appeal.
