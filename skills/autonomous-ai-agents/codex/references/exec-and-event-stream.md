

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

## `-c` effort quoting: shell vs argv (HTTP 400 `Invalid value`)

`model_reasoning_effort` must reach Codex as a TOML string. The quoting in the
examples above (`model_reasoning_effort='"high"'`) is **shell** notation: when
an integration builds the argv list in Python (`subprocess.run([...])`, no
shell), the outer single quotes are NOT stripped and the value lands as
`"high"` **with quotes** → Codex answers `HTTP 400 Invalid value: '"high"'`
and the call fails cleanly. In a non-shell argv element pass exactly
`model_reasoning_effort="high"` (double quotes only, no outer single). Compose
the element as a Python string `f'model_reasoning_effort="{effort}"'`.

Debug fast: when an `invoke-role` returns `canonical_artifact_fail` but the
model itself is suspect, call `run_codex` (or the raw `codex exec`) directly
and read the `--json` stream — a ``turn.failed`` with status 400 there is a
quoted-effort bug, not a missing write. The model is fine; the argv is not.

Also verify effort on the host, don't trust the model's default: if the
candidate model's default reasoning is `low` (e.g. Astra), pin `-c high`
explicitly or the role judges weaker than intended.

## Non-interactive: `codex exec`, not `codex run`

The canonical one-shot command is `codex exec` (alias `codex e`). Integrations
that call `codex run` will fail with "unknown subcommand" — fix the caller, or
verify the CLI version first. `--full-auto` is removed/deprecated; use
`--sandbox workspace-write` (or `--sandbox danger-full-access` under a gateway
where bubblewrap breaks).

Codex refuses to run outside a git repo; for non-git workspaces (e.g. a
Backlog/USERTOOLS tree) pass `--skip-git-repo-check`.

## Consuming `--json` output (event-stream format)

`codex exec ... --json` writes NDJSON **events**, not a single result envelope.
The final answer is the last `item.completed` whose `item.type == "agent_message"`
carrying `item.text`; `turn.failed` is the failure marker. A shell/script
consumer must parse lines for these, not `json.load` the whole stream:

```python
result, failed = "", False
for line in open(outfile, encoding="utf-8", errors="replace"):
    o = json.loads(line)
    if o.get("type") == "item.completed" and isinstance(o.get("item"), dict) \
       and o["item"].get("type") == "agent_message" and o["item"].get("text"):
        result = o["item"]["text"].strip()
    if o.get("type") == "turn.failed":
        failed = True
```

A model can emit several `agent_message` items (intermediate "I'll check…" lines
then the final answer); take the last non-empty one. Do not treat raw `--json`
as the report — strip tool/event payload before persisting (PII hygiene): keep
only `{result, is_error/failed}` like the Cursor `agent -p --output-format json`
envelope the consumer used to expect.
