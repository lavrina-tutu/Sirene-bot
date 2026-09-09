---
name: deep-mine-project
description: "Use when: глубокий анализ проекта, глубокое бурение, собери/обнови архив проекта, deep-mine refresh, digest проекта, проектная документация полного внедрения. Полуавтоматический сбор контекста (Confluence+Gantt JSON+встречи+сущность) в MD-overlay, сжатие digest, ручной refresh. Не для точечного RAG (workvault-rag), не sync одной страницы (ConfluenceSync), не компрессия ТЗ (tz-compressor-prompt)."
version: 0.5.0
platforms: [linux]
metadata:
  hermes:
    related_skills: [workvault-rag, hermes-feature, tutu-confluence-jira]
---

# deep-mine-project

Semi-automated deep project mining: Confluence L0 + Gantt-JSON plan + meetings + entity → overlay digest archive for Cursor architect.

> Context (RU): первый проект — TrisigmaFull (`Projects/TrisigmaFull`, entity `trisigma`). Источник плана — страница Confluence 519492770 (макрос `gantt-chart-planner`), не MPP.

## When to Use

- «глубокий анализ проекта», «глубокое бурение», «пробури проект»
- «собери архив проекта», «обнови архив», «deep-mine refresh»
- «digest проекта», «дай архитектору контекст»
- «проектная документация полного внедрения»

**Don't use:** single-page Q&A (`workvault-rag`); one-page Confluence sync (`ConfluenceSync`); TZ compression (`tz-compressor-prompt.md`); `read-mpp` skill for GS export (use overlay CSV+plan).

## Prerequisites

- VPN / on-prem for Confluence
- `CONFLUENCE_TOKEN`, venv `~/hermes-agent/.venv`
- Java 17 for MppReader **only if** Gantt JSON is absent (MPP fallback)
- Cursor CLI `agent`, MofsIndex built (`mofs-index verify`)

## How to Run

| User phrase | CLI |
|---|---|
| собери архив / пробури | `mine --slug TrisigmaFull` |
| обнови архив / refresh | `refresh --slug TrisigmaFull` |
| сожми digest | `digest --slug TrisigmaFull` |
| анализ архитектору | `analyze --slug TrisigmaFull --task <task_id>` |
| pack для задачи | `pack --slug TrisigmaFull --task feature_compare` |
| оформи документы | `document --slug TrisigmaFull` |

```bash
~/hermes-agent/.venv/bin/python3 \
  ~/hermes-workspace/skills/research/deep-mine-project/scripts/deep_mine.py \
  init|collect|refresh|digest|pack|mine|analyze|document --slug TrisigmaFull
```

**No crons** in v0.1 unless user says «ставь кроны».

## Procedure (A–I)

| Step | Action | Done when |
|---|---|---|
| A | `confluencesync pull` root depth 6 + PMO seeds + Gantt page | L0 pages on disk |
| B | REST whitelist attachments (`.json` + MPP) → `attachments/` | `gantt-chart-*.json` in overlay |
| C | `gantt_to_csv` → tasks/resources/assignments; cost = effort × rate; MPP fallback | 3 CSV + summary in `mpp/` |
| D | `search_meetings(limit=500)` → `pointers/meetings.md` | no transcript copies |
| E | MANIFEST 1.0, TREE, SOURCES, sha256 | hierarchical TREE |
| F | compress leaves/themes/plan (`project-context-compressor-prompt.md`) | digest `status: fresh` (journal → `rejected`) |
| G | architect analyze **pack** only (`BRIEF.md` checklist filled; PACK includes leaf + relevant theme digests) | no raw Confluence bodies |
| H | docs from `architect-plan.md` | `docs/*.md` draft |
| I | user acceptance | — |

### Plan source and cost (C)

Source of truth for **structure**: Confluence Gantt JSON (`gantt-chart-<instance>.json`), not `.mpp`.
Source of truth for **трудозатраты и стоимость**: блок «Итого» на L0-странице ганта (`plan.gantt_page_id`), не сумма листьев JSON.

- **Стоимость** = число «Трудозатраты: N человек-часа» × `plan.rate_rub_per_hour` (Trisigma: 6 512 × 3000 = 19 536 000 ₽). Нет числа / нет L0 → fail-loud (exit 4).
- **Длительность периода** — строка «Итого: с … по … - N рабочих дней» на той же странице.
- **ИСР / ресурсы / назначения / даты задач** — `eventsData` / `resourcesData` / `assignmentsData`.
- Manifest: `digests["plan"]` with `kind: gantt`, `effort_source: l0-page-total`.
- If JSON is missing, step C falls back to `read_mpp.py`.

Flags: `references/cli.md`. Contract: `references/overlay-contract.md`.

## Overlay invariant

L0 canonical MD stays in `Confluence/`, `Meetings/`, `Entities/`. Overlay holds pointers, manifest, digests, plan artifacts (Gantt JSON + CSV). Deleting overlay does not destroy canon.

**Document work (G/H/pack)** uses `digest/leaves` as canonical page source. L0 is allowed only for compressor F and collect/refresh/table_extract. Missing/rejected/stale digest → fail-loud (exit 2), not L0 fallback.

## Roles

One `agent -p` = one model. Compressor `composer-2.5`, architect `cursor-grok-4.6-high`, executor `composer-2.5`. Coordinator runs CLI steps A–E without mixing models.

## Pitfalls

- VPN fail-loud (exit 3); `ping()` before attachments (`get_attachments` silent `[]`)
- L0 `children: []` — rebuild TREE by parent inversion
- P0 sha was 16 hex — full 64 hex required
- `search_meetings` default limit 50 — use 500
- Do not feed G/H with `Confluence/**/index.md` — CLI enforces digest-only (no L0 in PACK/BRIEF; missing digest → exit 2)
- Do not use `tz-compressor-prompt.md`
- Do not treat `Trisigma_Plan.mpp` as the plan source — Gantt JSON on page 519492770 is canonical for WBS
- Cost is **not** JSON leaf sum: always «Трудозатраты» from L0 «Итого» × rate; JSON hours may drift

## Verification

```bash
# schema + pages
jq '.schema_version, (.pages|keys|length)' ~/WorkVault/Projects/TrisigmaFull/MANIFEST.json
# TREE not flat by space only
grep -c '^###' ~/WorkVault/Projects/TrisigmaFull/TREE.md
# meetings pointer, no transcript in overlay
test -f ~/WorkVault/Projects/TrisigmaFull/pointers/meetings.md
! find ~/WorkVault/Projects/TrisigmaFull -name '*transcript*' | grep -q .
# pytest
~/hermes-agent/.venv/bin/python3 -m pytest \
  ~/hermes-workspace/skills/research/deep-mine-project/tests -q -m "not live"
```
