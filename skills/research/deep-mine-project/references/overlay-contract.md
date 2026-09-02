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

## Invariants

- L0 bodies stay in `WorkVault/Confluence/**` — not copied to overlay.
- `content_sha256` = full 64-char sha256 of MD body after YAML frontmatter.
- TREE.md = hierarchical parent→children, not flat by space.
- PMO seeds appear at top level alongside DPAN root tree.
