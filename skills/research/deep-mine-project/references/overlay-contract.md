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
  "digests": {
    "plan": {
      "kind": "gantt",
      "csv_tasks": "mpp/<stem>__tasks.csv",
      "csv_resources": "mpp/<stem>__resources.csv",
      "csv_assignments": "mpp/<stem>__assignments.csv",
      "plan_path": "mpp/plan.md",
      "status": "fresh|stale|pending_compress",
      "effort_hours": 6512,
      "rate_rub_per_hour": 3000,
      "cost_rub": 19536000,
      "effort_source": "l0-page-total"
    }
  }
}
```

P0 flat map migrates to `pages` wrapper. `children` rebuilt by parent inversion (L0 `children: []` is normal).

On read, `digests["plan"]` is canonical; `digests["mpp-plan"]` is accepted as a legacy alias. Cost = L0 «Трудозатраты» × `PROJECT.yaml` `plan.rate_rub_per_hour` (`effort_source: l0-page-total`). JSON leaf sum is not used.

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

**Document-work source = digest.** Pack requires **fresh** digest leaf (`require_fresh_digest`); missing / rejected / stale / `missing_remote` → fail-loud (exit 2), no silent L0 fallback. PACK.md lists `page_id`, title, version, digest path — **not** `local_path` (L0). Table CSV extracts come from `collect --extract-tables` only; pack does not read L0.

### Theme digests in pack (A2)

`digest/themes/<theme>.md` — compressed from **leaf** digests (`compress_theme`), same «no journal» contract as leaves.  
Pack lists themes where `theme ∈ PROJECT.yaml.themes ∩ leaf.related` (if leaf has `related`; else all configured themes).  
Missing theme file → skip (not fail). `status: rejected` → omit from PACK.md.

## Invariants

- L0 bodies stay in `WorkVault/Confluence/**` — not copied to overlay.
- **G/H/pack** use `digest/leaves` (+ theme digests, extracts, plan CSV from Gantt JSON) as canonical source; L0 is only for F (compress) and collect/refresh/table_extract.
- `content_sha256` = full 64-char sha256 of MD body after YAML frontmatter.
- TREE.md = hierarchical parent→children, not flat by space.
- PMO seeds appear at top level alongside DPAN root tree.
