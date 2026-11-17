# Update cycle

Historical workflow details are subject to SKILL.md and the current route. Do not apply old cron orchestration or create crons automatically. Check roles and models against the approved workflow.

## Architect plan → execution → escalation

Apply this pattern to every upstream update of this repository. Historical role assignments below are examples; current role-config governs.

| Step | Role | Historical model |
|---|---|---|
| Risk analysis | architect | see current role-config |
| Plan vN | architect | see current role-config |
| Execution (staged merge) | executor | see current role-config |
| Escalation / plan vN+1 / rollback | architect | see current role-config |

The historical pattern excludes Anthropic Opus, Claude Sonnet and `claude-sonnet-5-thinking-*`; use the approved current role-config.

1. **Risk analysis (architect, read-only):** inspect actual `git diff`/`git show` for each potentially conflicting file, not just titles; assess security, breaking changes and config migration against our configuration. Avoid side effects: read or use `git worktree add /tmp/<name> origin/main` for investigation. Include directory-tree diff and audit live platform YAML and both `.env` files: `extra_or_secret` precedence `env → YAML extra → default` can override an apparently correct YAML with a narrow allowlist or different token. Save to `~/WorkVault/Hermes-Backlog/upstream-update-analysis-<date>.md`.
2. **Plan (architect):** read the analysis and write `~/WorkVault/Hermes-Backlog/upstream-update-PLAN-<date>-v<N>.md` with:
   - First, a git safety net: `backup/pre-upstream-<date>` and backups of `~/.hermes/config.yaml` and both `.env` files, created once per attempt and reused across cycles.
   - Progress branch `upstream-merge-in-progress`: commit the merge there, not directly to the working branch; do not automatically reset it on deviations.
   - Staged merge with success criteria for each step.
   - Modular tests (cron/scheduler, gateway/platforms, auxiliary, config migration, MCP, base smoke), cheapest first. Before config migrate back up `config.yaml`, `~/.hermes/.env` and `~/.hermes/profiles/default/.env`; afterward diff token/allowlist/multiplex. Unit tests do not replace post-FF group delivery.
   - A self-contained whitelist of resolved problems, following the handoff rule below.
   - An explicit prohibition on executor improvisation, independent fixes, scope expansion and unauthorized rollback.
   - The final post-FF checklist (group + DM); `hermes doctor`, `cron list` and one DM are insufficient.
3. **Execute:** follow the plan step by step in the progress branch, commit each completed stage and maintain the plan checklist. On any deviation outside the whitelist, do not fix, improvise or roll back; record exact state, error text, SHA and completed steps, then escalate. Leave the progress branch intact.
4. **Escalate:** the architect diagnoses the cause (upstream regression, flaky test, architectural refactor or our incompatibility) using branch progress. In `-v<N+1>.md`, specify either a workaround/fix in the same branch without rollback, or an explicit rollback and its point. Only the architect decides rollback in a new plan; it is never an automatic executor response.
5. **Finalize:** fast-forward `upstream-merge-in-progress` into the original working branch. Restart is a separate decision by Sasha, not automatic. FF and green tests do not close acceptance: audit disk immediately and perform group+DM live smoke after authorized restart and separately authorized live check.

## Context handoff (required for every escalation)

Include in the architect invocation text, not just as file links:
- Full chronology of every plan version in the attempt and what happened in each.
- Every resolved/whitelisted issue and its rationale.
- The exact whitelist from the preceding escalation.

Explicitly carry every test/file exclusion in architect diagnostics (`--deselect`, manual subtraction) into the next plan's whitelist. Make the whitelist self-contained so the executor need not reconstruct it from history. Sessions do not share memory unless context is explicitly passed.

> Context (RU): Прецедент 16.07: тест `test_honcho_cache_busting_config_memoized_by_mtime` признали flaky в диагностике к v4, но не внесли в whitelist плана v4; исполнитель повторно остановился на уже разобранном случае.

## Cycle limit

Count each plan version as a cycle and state its number in each invocation. Stop after cycle 5, whether successful or escalated; do not create a sixth independently. Gather the five-cycle summary and report status and decision history to Sasha with a question about continuing or closing. If successful earlier, stop and report; restart and the subsequent group+DM checklist remain separately authorized.

> Context (RU): «Прекращаем» — попытка закрывается; ветка прогресса/backup/config.bak не удаляются автоматически. «Продолжаем» — новый пайплайн с полной сводкой прошлых циклов, повторным использованием наработок и новым счётчиком от 1 до 5.

## Before the first cycle of a new attempt

Review MEMORY for upstream-update pitfalls and notes for this repository. Move them to upstream-incident-history.md and remove them from MEMORY after confirming the transfer; do not duplicate facts. Keep procedural details in the skill.
