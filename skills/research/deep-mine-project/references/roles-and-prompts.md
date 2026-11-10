# Roles and agent prompts

One `agent -p` = one model = one role.

| Role | Model | Step | Source |
|---|---|---|---|
| Coordinator | Сирень + механич. | A–E, refresh | L0 (collect/refresh) |
| Compressor | gpt-6.1-terra (codex CLI) | F (`project-context-compressor-prompt.md`) | **L0** (`index.md`) |
| Architect | gpt-6-astra (codex CLI) | G | **pack + digest** (no L0) |
| Executor | gpt-6.1-sol (codex CLI) | H | **plan + digest** (no L0) |

## Compress leaf

```bash
cd ~/WorkVault/Projects/<Slug>
invoke-role --role compressor --model gpt-6.1-terra --backend codex \
  --prompt-file ~/WorkVault/Registries/project-context-compressor-prompt.md \
  --context "Сожми L0: <local_path>"
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
