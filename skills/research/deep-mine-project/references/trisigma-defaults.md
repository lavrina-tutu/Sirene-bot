# TrisigmaFull defaults (first project)

| Field | Value |
|---|---|
| slug | TrisigmaFull |
| entity_slug | trisigma |
| root_page_id | 493477568 |
| PMO Бриф | 490166551 (v41) |
| PMO Устав | 490167911 (v11) |
| pages in P0 | 33 |
| meetings (trisigma slug) | ~91 |
| MPP expected_name | Антибот внедрение Отели + исследование внедрение вертикали 260925 |

## Expectations

- L0 under `WorkVault/Confluence/DPAN/...` and `Confluence/PMO/...`
- Overlay: `WorkVault/Projects/TrisigmaFull/`
- `children: []` in L0 frontmatter — rebuild TREE via parent inversion
- P0 `content_sha256` was 16 hex — wave 1 recalculates full sha256
- `search_meetings(..., limit=500)` for full meeting set
- VPN required for Confluence pull and attachment download

## Pitfalls

- `ab_platforma` ≠ `trisigma` entity slug
- pagetree macro on root — children come from pull depth, not macro
- `.zip` MPP may be OLE2 — detect signature, do not unzip blindly
- `get_attachments` returns `[]` on network error — always `ping()` first
