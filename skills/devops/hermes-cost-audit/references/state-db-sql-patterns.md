# State.db SQL Patterns for Cost Analysis

Ready-to-run Python+SQL snippets. Execute via:
```bash
cd ~/.hermes/profiles/<profile> && python3 -c "..."
```

## Tool-call breakdown per session

The `messages` table stores `tool_calls` as JSON. Parse it in Python:

```python
import sqlite3, json
db = os.path.expanduser('~/.hermes/state.db')
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute('SELECT tool_calls FROM messages WHERE session_id = ? AND tool_calls IS NOT NULL', (session_id,))
tool_counts = {}
for row in cur.fetchall():
    tc = json.loads(row['tool_calls'])
    if isinstance(tc, list):
        for t in tc:
            name = t.get('function',{}).get('name','?')
            tool_counts[name] = tool_counts.get(name, 0) + 1

for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
    print(f'  {name:30s} {count}')
```

## Input/Output ratio by model

```sql
SELECT model,
       SUM(input_tokens + cache_read_tokens + cache_write_tokens) as total_in,
       SUM(output_tokens) as total_out,
       SUM(estimated_cost_usd) as total_cost,
       COUNT(*) as sessions
FROM sessions
GROUP BY model
HAVING total_cost > 0
ORDER BY total_cost DESC;
```

**Finding (Aug 2026):** input/output ratio is ~221:1 across all models. Cache read dominates. This is normal for long Telegram sessions with history accumulation.

## Detect duplicate input storms

```sql
-- Find sessions where the same user message appears multiple times at the same timestamp
SELECT session_id, content, COUNT(*) as dup_count
FROM messages
WHERE role = 'user'
GROUP BY session_id, content, timestamp
HAVING COUNT(*) > 1
ORDER BY dup_count DESC
LIMIT 10;
```

**Finding (Aug 2026):** Top session ($220.98) had "Кто ты?" repeated 8+ times at the same timestamp — a gateway/platform retry bug that caused the model to reprocess everything.

## Cost trend over time

```sql
SELECT DATE(started_at, 'unixepoch') as day,
       COUNT(*) as sessions,
       SUM(estimated_cost_usd) as daily_cost
FROM sessions
GROUP BY DATE(started_at, 'unixepoch')
ORDER BY day DESC
LIMIT 30;
```

## Custom provider caveat (Jul 2026)

**When a custom provider is configured** (`provider: <name>`, `base_url: ...`), the `model` column in state.db records the **config string**, not the actual upstream model that responded. Example: `model: deepseek/deepseek-v4-pro` through a TUTU OpenRouter gateway may have actually hit Claude upstream.

**Detection queries:**

```sql
-- Find sessions with NULL model (proxy format mismatch)
SELECT COUNT(*) as null_model_sessions
FROM sessions
WHERE model IS NULL AND source = 'telegram';

-- Find clusters of NULL sessions after a custom-provider session
-- (indicates the proxy was active but responses weren't parsed)
```

**Audit rule:** Before attributing costs to a specific model, check `config.yaml` for custom providers during that time period. Cross-reference `model` column values with `model.default` in config. If custom providers were active, the model name in state.db is unreliable.

**Better detection via billing columns (Jul 2026):**

```sql
-- Show billing metadata alongside model for sessions in a period
SELECT datetime(started_at, 'unixepoch') as t,
       model, billing_provider, billing_base_url, billing_mode,
       round(estimated_cost_usd, 2) as cost
FROM sessions
WHERE started_at >= ? AND started_at < ?
ORDER BY started_at;
```

If `billing_base_url` differs from the canonical API URL for the model's nominal provider (e.g., `model=deepseek/...` but `billing_base_url=api.anthropic.com`), the model name is wrong — the actual upstream was different. `billing_provider='custom'` or `'custom:tutu'` signals a proxy is in use.

**NULL model clusters:** When `model IS NULL` for sessions immediately after a custom-provider switch, the proxy returned responses in a format Hermes couldn't parse. Those sessions used a real model, just not recorded.

**User word > state.db:** If the user states which providers/models were active during a period, accept their word over what state.db shows. Config strings may not match the real upstream.

## Multi-profile state.db architecture (Aug 2026)

**Important:** `~/.hermes/state.db` (main, ~900MB) is the authoritative historical database. Profile-specific state.db files under `~/.hermes/profiles/<name>/state.db` may have a **different schema** — older versions lack `started_at` or `model` columns. Always audit from `~/.hermes/state.db`.

**Discovery query:** Find which profiles sessions belong to:
```sql
SELECT COALESCE(profile_name, 'no-profile') as prof, model,
       COUNT(*) as sessions, round(sum(estimated_cost_usd), 2) as cost
FROM sessions
WHERE started_at >= ? AND started_at < ?
GROUP BY prof, model
ORDER BY cost DESC;
```

**Verification:** If a profile state.db returns 0 sessions or has a schema with only `(id, source, created_at, updated_at, metadata)`, it's an old version — don't use it for audit.
