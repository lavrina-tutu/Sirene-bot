# Roles and agent prompts

One `agent -p` = one model = one role.

| Role | Model | Step |
|---|---|---|
| Coordinator | Сирень + composer-2.5 mechanics | A–E, refresh |
| Compressor | composer-2.5 | F (`project-context-compressor-prompt.md`) |
| Architect | cursor-grok-4.6-high | G |
| Executor | composer-2.5 | H |

## Compress leaf

```bash
cd ~/WorkVault/Projects/<Slug>
agent -p "$(cat ~/WorkVault/Registries/project-context-compressor-prompt.md)
---
Сожми L0: <local_path>" -f --model composer-2.5 --output-format json
```

## Analyze (G)

Input: `digest/_index.md`, `digest/themes/*.md`, `docs/_inbox/diff.md`.  
**Forbidden:** raw `Confluence/**/index.md` bodies.

## Document (H)

Input: `docs/architect-plan.md` + specified digests → `docs/*.md` with `status: draft`.
