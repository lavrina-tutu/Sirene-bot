# deep-mine-project CLI

Entry-point:

```bash
~/hermes-agent/.venv/bin/python3 \
  ~/hermes-workspace/skills/research/deep-mine-project/scripts/deep_mine.py \
  <command> --slug TrisigmaFull [flags]
```

## Commands

| Command | Steps | LLM |
|---|---|---|
| `init` | overlay skeleton + PROJECT.yaml | no |
| `collect` | A→B→C(CSV)→D→entity→E | no |
| `refresh` | version poll + stale report | no |
| `digest` | F (compress leaves/themes/plan) | composer-2.5 |
| `pack` | task pack (PACK.md + BRIEF.md) | no |
| `mine` | collect + digest | mixed |
| `analyze` | G (pack-based if `--task`, or `--full-archive`) | cursor-grok-4.6-high |
| `document` | H | composer-2.5 |

## Common flags

- `--slug` — overlay slug (required)
- `--workvault` — default `~/WorkVault`
- `--dry-run` — refresh report only
- `--json` — machine-readable summary

## collect skip flags

- `--skip-a` — skip Confluence pull
- `--skip-b` — skip attachments
- `--skip-c` — skip MPP CSV
- `--skip-d` — skip meetings index
- `--skip-e` — skip manifest rebuild
- `--skip-entity` — skip entity pointer
- `--extract-tables` — after manifest rebuild, extract L0 tables for `task_pages`

## refresh flags

- `--extract-tables` — extract tables for `task_pages` after refresh (requires pages in MANIFEST)

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 2 | validation / PROJECT.yaml |
| 3 | Confluence down / 401 / 403 |
| 4 | MPP / Java error |
| 5 | meetings index unavailable |
| 6 | digest validation rejected |

## analyze

Requires `--task <task_id>` **or** `--full-archive` (exclusive). Without either → exit 2.

```bash
python3 deep_mine.py analyze --slug TrisigmaFull --task feature_compare
python3 deep_mine.py analyze --slug TrisigmaFull --full-archive
```

- `--allow-stale` — analyze only; tolerate stale digests (not pack/document).
- Full-archive: all manifest pages must have fresh digest (or stale with `--allow-stale`); otherwise fail with unready list.
- Task mode: `require_fresh_digest` on task page before agent starts.

Step G requires filled `BRIEF.md` checklist. Run `pack` first, then analyze.

## pack

```bash
python3 deep_mine.py pack --slug TrisigmaFull --task feature_compare [--page-id PAGE]
```

Output: `docs/_inbox/<task_id>/{PACK.md,BRIEF.md,extracts/}`. Fail-loud if page not in MANIFEST or digest not fresh.

`PACK.md` indexes leaf digest (no L0 `local_path`), CSV extracts, and **theme digests** from `digest/themes/` when:
- theme is listed in `PROJECT.yaml` `themes`;
- theme appears in the task leaf's `related` frontmatter (built from leaves, not raw L0);
- file exists and `status` is not `rejected`.

Missing theme file does not fail pack (theme not compressed yet).

## document

Preflight: `architect-plan.md` exists; every `page_id` from plan/pack has fresh digest. Fail-loud otherwise.

```bash
python3 deep_mine.py document --slug TrisigmaFull
```
