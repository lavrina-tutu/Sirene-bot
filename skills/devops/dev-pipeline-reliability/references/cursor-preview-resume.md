# Cursor/Grok: preview-answer → resume by session_id

## Symptom
Long analytical tasks via `agent -p ... --model cursor-grok-4.6-high --output-format json`
may return `subtype: success` with a **short preview** of the plan ("Сначала сверюсь со
скиллами и входными документами, затем соберу...") instead of the full report — the
agent stopped early. This looks like success but has almost no useful output.

## Rule
When the JSON `result` reads like an opening narration ("Сначала... Дальше..."),
NOT the final deliverable, the work is unfinished. Resume the same logical session
rather than re-running from scratch (re-run duplicates tokens / may diverge):

```bash
agent -p "$(cat /tmp/task.md)" -f --model cursor-grok-4.6-high \
  --output-format json --resume <SESSION_ID>
```
Use the `session_id` from the first (preview) call's JSON.

## Notes
- Distinguish from a genuinely complete short result (e.g. "Made the edit, tests pass")
  — that IS the answer. Look for opening-frame phrasing AND missing deliverable.
- Resume reuses cache (cacheReadTokens stays high), so it's cheap.
- If two sequential resume calls still return previews, the analytic path is getting
  truncated by `-p` — check cursor-cli for `--mode plan`/output-size flags before
  assuming it worked.