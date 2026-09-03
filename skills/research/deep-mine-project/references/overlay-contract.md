# Overlay contract (MANIFEST 1.0)

## MANIFEST.json

```json
{
  "schema_version": "1.0",
  "slug": "TrisigmaFull",
  "pages": {
    "<pageId>": {
      "title": "...",
      "space": "DPAN|PMO",
      "confluence_url": "https://dom.tutu.ru/pages/viewpage.action?pageId=...",
      "version": "N",
      "local_path": "Confluence/.../index.md",
      "content_sha256": "<64 hex sha of body without frontmatter>",
      "parent": "<pageId>|null",
      "children": ["<pageId>", ...],
      "kind": "confluence_page",
      "digest_slug": "p<pageId>",
      "digest_path": "digest/leaves/p<pageId>.md"
    }
  },
  "attachments": [],
  "digests": {}
}
```

P0 flat map migrates to `pages` wrapper. `children` rebuilt by parent inversion (L0 `children: []` is normal).

## Digest frontmatter

See `project-context-compressor-prompt.md`. Block «Источники» must be first in body.

### Digest body contract (A0)

`digest_status` enum: `fresh` | `stale` | `missing_remote` | `rejected`.

**Required in body** (after «Источники»): page facts; tables from L0 as markdown table or CSV extract reference; named entities.

**Rejected** (`status: rejected`, not `fresh`) if body contains:
- compressor journal («сжал до», «% от L0», «Digest записан», «Сначала посмотрю», «Создаю digest», «Самопроверка инвентаря» as process report);
- YAML frontmatter dump in body;
- author instructions («не копировать», «уточнить до ПК»).

Validated by `digest_validate.py` after compress; fail-loud exit 6.

### task_pages (A1)

Optional `PROJECT.yaml` field:

```yaml
task_pages:
  - { page_id: "519487958", role: charter_draft, space: PMO }
  - { page_id: "519489611", role: feature_gap }
  - { page_id: "514903239", role: feature_compare }
```

`collect`/`refresh` pull each `task_pages` entry like `pmo_seeds` (`--no-recursive --resync`).  
Page not in MANIFEST → fail-loud «добавь в task_pages и collect».  
`--extract-tables` writes `docs/_inbox/<role>/extracts/<pageId>__<role>.csv`.  
If L0 has a table and CSV extract is missing → `pack` fails.

### Pack (A0)

`pack --task <task_id>` → `docs/_inbox/<task_id>/{PACK.md,BRIEF.md,extracts/}`.  
Step G reads pack only (not full overlay). BRIEF checklist must be filled before analyze.

### Theme digests in pack (A2)

`digest/themes/<theme>.md` — compressed from **leaf** digests (`compress_theme`), same «no journal» contract as leaves.  
Pack lists themes where `theme ∈ PROJECT.yaml.themes ∩ leaf.related` (if leaf has `related`; else all configured themes).  
Missing theme file → skip (not fail). `status: rejected` → omit from PACK.md.

## Invariants

- L0 bodies stay in `WorkVault/Confluence/**` — not copied to overlay.
- `content_sha256` = full 64-char sha256 of MD body after YAML frontmatter.
- TREE.md = hierarchical parent→children, not flat by space.
- PMO seeds appear at top level alongside DPAN root tree.
