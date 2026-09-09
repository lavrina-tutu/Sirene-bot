# TrisigmaFull defaults (first project)

| Field | Value |
|---|---|
| slug | TrisigmaFull |
| entity_slug | trisigma |
| root_page_id | 493477568 |
| PMO Бриф | 490166551 (v41) |
| PMO Устав | 490167911 (v11) |
| Gantt page | 519492770 («Таймлайн и Стоимость полного внедрения Trisigma») |
| Gantt instance | b10931f5-7163-4270-95c4-b8d1ca9d23ac |
| Gantt attachment | `gantt-chart-b10931f5-7163-4270-95c4-b8d1ca9d23ac.json` |
| rate_rub_per_hour | 3000 |
| pages in P0 | 33 |
| meetings (trisigma slug) | ~91 |

## Plan source

Canonical plan is the Confluence Gantt JSON on page 519492770, not `Trisigma_Plan.mpp`.

- Стоимость = «Трудозатраты» блока «Итого» на странице 519492770 × 3000 ₽/чел-час (6 512 × 3000 = 19 536 000 ₽). Сумма листьев Gantt JSON **не** канон.
- Длительность периода — «Итого: с 07.09.26 по 13.09.27 - 252 рабочих дня».
- `PROJECT.yaml` section: `plan:` (`source`, `gantt_page_id`, `gantt_instance`, `rate_rub_per_hour`). Legacy `mpp:` is still read.

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
- `.zip` MPP (fallback only) may be OLE2 — detect signature, do not unzip blindly
- `get_attachments` returns `[]` on network error — always `ping()` first
- Prefer `gantt-chart-*.json` over any leftover `.mpp` in `attachments/`
