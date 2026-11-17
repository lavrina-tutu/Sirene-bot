

## Historical source (superseded where it conflicts with SKILL.md; not current instruction)

## Ad-hoc ролевая консультация (мнение архитектора вне DevWorkflow)

When the user asks for an architect's verdict on a question that is NOT a
DevWorkflow phase (no slug/phase — e.g. «мнение архитектора» про смену
дефолтной модели) the role must still be invoked, but NOT via
`pipeline invoke-role`: without `--slug/--phase` it returns rc=0 and silently
swallows the role's stdout/stderr — you get nothing back. Call `codex exec`
directly, reading the model/effort from
`~/WorkVault/Registries/EcosystemConfig.yaml` → `tools.dev_workflow.invoke.roles.<role>`
(architect = `gpt-6.1-sol`, effort high) instead of hardcoding:

```bash
cd ~/WorkVault/Registries && codex exec -C <ABS-workspace> -m gpt-6.1-sol -c 'model_reasoning_effort="high"' --skip-git-repo-check --json --sandbox danger-full-access -- "$(cat /tmp/prompt.md)"
```

- Prompt file: question verbatim + live facts from the machine (config, model
  tables) + requested answer format + «только текст мнения, без реализации».
- Parse the result from the `--json` NDJSON stream (last `agent_message` item,
  see above); `json.load` of the whole file fails with «Extra data».
- Pass the role's verdict to the user as-is — no own recommendations, the
  architect owns design verdicts.
- CLI pitfall: the `pipeline` package must be run as `python3 -m pipeline.cli`
  from `~/WorkVault/Registries` (package root) — from inside
  `Registries/pipeline/` the relative import fails with
  `ImportError: attempted relative import with no known parent package`.

**Reviewer verdict files (dev-workflow REV-*.md): keep reviewing sections as
H2 (`## `), never H3 (`###`).** The downstream `rev_verdict()` parser takes the
block from `## Вердикт` to the *next H2 header*; if the reviewer writes its
narrative/argumentation as H3 sections, the verdict block is never terminated
and swallows the whole file — so any body mention of the OTHER verdict word
(e.g. explaining a past `REQUEST-CHANGES` round) makes the parser return
CONFLICT against the explicit `verdict=APPROVE`, and `complete-phase` fails
"REV verdict unknown or conflict" even though the verdict is genuinely
approve and the full test suite is green. When you (or a Codex reviewer) write
the review, put each reasoning section at `## ` level and keep the verdict
assertion as the first line under `## Вердикт`, away from any stray
`REQUEST-CHANGES` string above the next H2.
