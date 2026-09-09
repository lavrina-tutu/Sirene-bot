---
name: deep-mine-project
description: "Use when: глубокий анализ проекта, глубокое бурение, собери/обнови архив проекта, deep-mine refresh, charter-context, architecture-context, проектная документация полного внедрения. Полуавтоматический сбор контекста (Confluence+Gantt JSON+встречи+сущность) в 3-слойный overlay (GRAPH/facts/contexts). Не для точечного RAG (workvault-rag), не sync одной страницы (ConfluenceSync), не компрессия ТЗ (tz-compressor-prompt)."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    related_skills: [workvault-rag, hermes-feature, tutu-confluence-jira, pmo-charter-fill]
---

# deep-mine-project

Semi-automated deep project mining v1.0.0: Confluence L0 + Gantt-JSON plan + meetings + entity → overlay with GRAPH (A), facts.json (B), charter/architecture contexts (C).

> Context (RU): первый проект — TrisigmaFull (`Projects/TrisigmaFull`, entity `trisigma`). Источник плана — страница Confluence 519492770 (макрос `gantt-chart-planner`), не MPP.

## When to Use

- «глубокий анализ проекта», «глубокое бурение», «пробури проект»
- «собери архив проекта», «обнови архив», «deep-mine refresh»
- «устав-контекст», «architecture-context», «дай архитектору контекст»
- «проектная документация полного внедрения»

**Don't use:** single-page Q&A (`workvault-rag`); one-page Confluence sync (`ConfluenceSync`); TZ compression (`tz-compressor-prompt.md`).

## Prerequisites

- VPN / on-prem for Confluence
- `CONFLUENCE_TOKEN`, venv `~/hermes-agent/.venv`
- Java 17 for MppReader **only if** Gantt JSON is absent (MPP fallback)
- Cursor CLI `agent` for G/H only; Hermes API for facts/context synthesis

## How to Run

| User phrase | CLI |
|---|---|
| собери архив / пробури | `mine --slug TrisigmaFull` |
| обнови архив / refresh | `refresh --slug TrisigmaFull` |
| граф проекта | `graph --slug TrisigmaFull` |
| факты | `facts --slug TrisigmaFull` |
| устав-контекст | `charter --slug TrisigmaFull` |
| architecture-context | `architecture --slug TrisigmaFull` |
| сожми digest (наследие F) | `digest --slug TrisigmaFull` |
| анализ архитектору | `analyze --slug TrisigmaFull --task <task_id>` |
| pack для задачи | `pack --slug TrisigmaFull --task feature_compare` |
| оформи документы | `document --slug TrisigmaFull` |

```bash
~/hermes-agent/.venv/bin/python3 \
  ~/hermes-workspace/skills/research/deep-mine-project/scripts/deep_mine.py \
  init|collect|graph|facts|charter|architecture|mine|refresh|pack|analyze|document --slug TrisigmaFull
```

**No crons** unless user says «ставь кроны».

## Procedure (A–I)

| Step | Action | Done when |
|---|---|---|
| A–E | collect: pull, attachments, plan CSV, meetings, MANIFEST | L0 + overlay skeleton |
| A | `graph`: GRAPH.json, LINKS.md, TREE from graph | edges: parent\|child\|links_to\|seed only |
| B | `facts`: script_only + llm_assisted (API-JSON) | facts.json |
| C | `charter` + `architecture`: 5+ batched grok API-JSON | charter-context.md, architecture-context.md |
| F (legacy) | `digest`: per-page compress | digest/leaves (not SoT for Q&A) |
| G | architect analyze from contexts + GRAPH | docs/architect-plan.md |
| H | executor docs from plan + contexts | docs/*.md draft |
| I | user acceptance | — |

`mine` = collect → graph → facts → charter → architecture (**not** digest).

### Plan source and cost (C-collect)

Source of truth for **structure**: Gantt JSON. **Трудозатраты/стоимость**: L0 «Итого» × `plan.rate_rub_per_hour`.

Flags: `references/cli.md`. Contract: `references/overlay-contract.md`, `references/j1-j8.md`.

## Overlay invariant

L0 canonical MD stays in `Confluence/`, `Meetings/`, `Entities/`. Overlay SoT for Q&A/pack/G/H:

- `GRAPH.json`, `facts.json`, `charter-context.md`, `architecture-context.md`
- `digest/` — legacy v0.x, not SoT for answers

## Roles

| Contour | Mechanism | Model |
|---|---|---|
| F digest (legacy) | Hermes call_llm | deepseek flash |
| B facts llm | Hermes API-JSON | deepseek flash |
| C contexts | Hermes API-JSON | x-ai/grok-4.6 |
| G analyze | Cursor agent | grok-high |
| H document | Cursor agent | composer-2.5 |

## Pitfalls

- VPN fail-loud (exit 3)
- Context synthesis reject → `*.rejected.json` + exit 6; valid `.md` not overwritten on fail (J4)
- Same `sources_sha` → 0 LLM for context (J8)
- Numbers from `facts.script_only` beat llm/model
- Do not use `digest/leaves` as SoT for pack/analyze/Q&A
- Do not use `tz-compressor-prompt.md`

## Verification

```bash
test -f ~/WorkVault/Projects/TrisigmaFull/GRAPH.json
test -f ~/WorkVault/Projects/TrisigmaFull/facts.json
test -f ~/WorkVault/Projects/TrisigmaFull/charter-context.md
~/hermes-agent/.venv/bin/python3 -m pytest \
  ~/hermes-workspace/skills/research/deep-mine-project/tests -q -m "not live"
```
