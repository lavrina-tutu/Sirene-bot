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
| `mine` | collect + digest | mixed |
| `analyze` | G | cursor-grok-4.6-high |
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

## Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 2 | validation / PROJECT.yaml |
| 3 | Confluence down / 401 / 403 |
| 4 | MPP / Java error |
| 5 | meetings index unavailable |

No cron subcommand. No `--with-attachments` (ConfluenceSync scope).
