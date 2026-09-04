# Roles and agent prompts

One `agent -p` = one model = one role.

| Role | Model | Step | Source |
|---|---|---|---|
| Coordinator | Сирень + composer-2.5 mechanics | A–E, refresh | L0 (collect/refresh) |
| Compressor | composer-2.5 | F (`project-context-compressor-prompt.md`) | **L0** (`index.md`) |
| Architect | cursor-grok-4.6-high | G | **pack + digest** (no L0) |
| Executor | composer-2.5 | H | **plan + digest** (no L0) |

## Compress leaf

```bash
cd ~/WorkVault/Projects/<Slug>
agent -p "$(cat ~/WorkVault/Registries/project-context-compressor-prompt.md)
---
Сожми L0: <local_path>" -f --model composer-2.5 --output-format json
```

## Analyze (G)

Input: `docs/_inbox/<task_id>/PACK.md` + `BRIEF.md` (when `--task` set).  
Agent reads digest leaves by path from PACK — bodies are not inlined.  
**Forbidden:** raw `Confluence/**/index.md` and `WorkVault/Confluence/**`; starting G with empty invariant checklist.

For full-archive mode: `--full-archive` (all pages must have fresh digest; use `--allow-stale` for read-only stale tolerance).

Template: `references/architect-brief.template.md`. Manual brief in chat is bypass — forbidden in SKILL.md.

## Document (H)

Input: `docs/architect-plan.md` + digest paths from plan/pack → `docs/*.md` with `status: draft`.  
Preflight: every referenced page must have fresh digest (fail-loud otherwise).  
**Forbidden:** L0 `Confluence/**/index.md`.
