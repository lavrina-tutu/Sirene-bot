# Model family switch verification

Use when a skill table or cron prompt changes from one model family to another and the role is encoded as a `{model, reasoning}` tuple.

## Rule

Treat `model` and `reasoning` as one atomic value. Update both together, then verify:

1. No old model IDs remain in the target skill file.
2. Every row that changed has the intended `reasoning` value.
3. Any intentional inheritance row (for example Sonnet in `hermes-feature`) is left untouched.
4. The prose around the table does not keep stale provider-specific claims after the migration.

## Minimal verification commands

```bash
grep -nE 'old-model-id|new-model-id|"reasoning": "(low|medium|high)"' ~/.hermes/skills/devops/<skill>/SKILL.md
```

If the skill also has a companion reference file for the migration, keep the table in SKILL.md and the exact mapping notes in the reference file, not duplicated across multiple skills.
