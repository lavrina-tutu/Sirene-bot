---
name: hermes-upstream-check
description: «Проверить обновления upstream Hermes»
version: 2.3.1
author: agent
tags: [hermes, upstream, git, update, devops, cron]
platforms: [linux]
---

# Hermes Upstream Check

Analyze changes in `NousResearch/hermes-agent` against the confirmed baseline and prepare a reasoned update decision. A separate mode executes a plan already approved by the architect. Use discovery for third-party skills, not this process. The active monitor `d77329d35ca5`, `0 4 * * 6`, uses this skill's name.

## Analysis

1. Establish the baseline and `origin/main`; prefer `~/.hermes/scripts/upstream_monitor.sh` as the source of categories and `watch_list`. Do not run the production monitor to test its changes: use isolated repository and state copies, test scenarios with and without an update, and verify that production state remains unchanged.
2. Before risk analysis, check the ancestry of `last_sha` against `origin/main`. On DRIFT use the confirmed git baseline (`git merge-base HEAD origin/main`) and report the monitor defect. Advance `last_sha` only after the repository has actually been updated and ancestry confirmed; otherwise the range accumulates.
3. Analyze content and directory/path diffs, including file moves. Consider eight criteria: conflicts and migrations; tokens/cost; fixes to our functionality; reliability; quarantine of questionable commits; urgent security; irrelevant platform noise; and new capabilities. Inspect actual changes, not just titles.
4. For platform conflicts, compare live YAML and both `.env` files: effective allowlist, token source bot IDs, multiplex and precedence. Do not display full secrets. Check ancestry and authorship of `+N carried commits`: they are not necessarily our patches.
5. Save the analysis to `~/WorkVault/Hermes-Backlog/upstream-update-analysis-<date>.md`; present categories, quarantine, irrelevant changes and a justified green/yellow/red verdict.

Detailed commands, criteria, `watch_list`, DRIFT and format: [upstream-analysis.md](references/upstream-analysis.md).

## Execute an approved plan

Follow the current DevWorkflow and the architect-approved plan; historical automatic cron orchestration does not itself authorize cron creation. The architect performs read-only risk analysis and writes `~/WorkVault/Hermes-Backlog/upstream-update-PLAN-<date>-v<N>.md`; the executor acts only on the plan. Check roles and models against the current role-config.

- At the start of an attempt, create the plan's backup branch `backup/pre-upstream-<date>` and copies of `~/.hermes/config.yaml`, `~/.hermes/.env`, `~/.hermes/profiles/default/.env` once; retain them throughout the attempt.
- Perform the staged merge in `upstream-merge-in-progress`, recording completed stages and the checklist. Include modular tests for cron/scheduler, gateway/platforms, auxiliary, config migration, MCP and base smoke in the plan; define success for each stage in advance.
- Maintain a complete self-contained whitelist: explicitly carry all test and file exclusions from diagnostics into the next plan version. Each escalation includes the chronology of all versions, every resolved issue with its rationale, and the exact previous whitelist.
- On any unknown deviation, stop, preserve state, error, SHA and progress, and escalate to the architect. Do not improvise, fix or roll back independently. Only the architect decides on a workaround or rollback in a new plan and specifies the point; do not automatically reset the progress branch.
- Count plan versions as cycles; after the fifth, stop and present Sasha with a summary and a question about continuing. Do not start a sixth cycle independently. On completion or stopping, do not automatically delete the backup, config backup or progress branch.
- Finalize git by fast-forwarding the progress branch into the original working branch according to the plan. Restart is not automatic. FF and green tests alone do not complete acceptance.

Context handoff and cycle history: [update-cycle.md](references/update-cycle.md). Merge commands and rollback conditions: [upstream-merge-steps.md](references/upstream-merge-steps.md).

## Post-FF acceptance and restrictions

Audit disk immediately after FF. Preserve YAML and both `.env` files before migration; after migration compare backup and current values: bot IDs, effective allowlist and multiplex. `hermes config migrate` does not guarantee `.env` fixes. All token sources must point to the one intended bot; another fallback bot is not normal. Check topic policy against the current catalog, not a historical count.

Separate restart from git work. The original rule permits it only after fresh explicit permission from Sasha for a specific window; permission does not carry over to another attempt.

> Context (RU): Особое право сохранено решением Саши (17.11.2026): агент может выполнить рестарт gateway в явно разрешённом Сашей окне при остальном общем правиле «рестарт — руками Саши».

Do not expand that authority. After an authorized restart and a separately authorized live check, verify an inbound message and reply in the group with the same `message_thread_id`, as well as DM. Without that permission, limit checks to disk audit and existing inbound logs; do not declare full acceptance before the prescribed smoke. `doctor`, `status`, cron outbound and DM-only do not prove the group inbound path. Do not call concurrent `getUpdates` on a running poller's token: it can cause 409 and queue loss. If the group is silent while DM works, first check the allowlist and poller bot ID.

Detailed disk audit, backup/diff and group+DM smoke: [post-ff-verification.md](references/post-ff-verification.md). Nine historical precedents: [upstream-incident-history.md](references/upstream-incident-history.md).

## Verification checklist

Use this checklist to verify the approved plan and the evidence before reporting the attempt. The linked references define the procedures and commands; this checklist does not authorize operations outside the plan or the permissions for the attempt.

### Analysis and plan

- [ ] Check `last_sha` ancestry before calculating the upstream range. If it has drifted, use `git merge-base HEAD origin/main` as the confirmed baseline and report the monitor defect. Leave `last_sha` unchanged until the local repository is actually updated and ancestry is confirmed.
- [ ] Inspect actual content and directory-tree changes for affected paths, including renamed or moved files. Evaluate all eight criteria, distinguish quarantined commits from irrelevant platform noise, and explain the verdict with evidence.
- [ ] Compare the live platform YAML with both `.env` files, including bot IDs, the effective allowlist and multiplex. Account for environment precedence and avoid exposing full secrets. Check authorship and ancestry before interpreting the carried-commit count.
- [ ] Write the analysis and an architect-approved, versioned plan at the paths specified above. Define staged success criteria and modular test coverage, including migration and delivery verification. Check current roles and models rather than assuming historical assignments.
- [ ] Create the backup branch and copies of config and both `.env` files once per attempt. Reuse them across cycles; retain the backups and progress branch after completion or stopping.

### Execution and escalation

- [ ] Establish the test baseline with `bash scripts/run_tests.sh`; use the same runner after the merge. Compare failures with the baseline and follow the architect's criteria. Do not substitute `python -m pytest`.
- [ ] Merge in `upstream-merge-in-progress` under the approved plan. Preserve local commit identities: use merge, not rebase or squash. Record completed stages and maintain the plan checklist.
- [ ] On an unlisted deviation, preserve the exact error, state, SHA and progress, then escalate. Do not independently resolve it or roll back. The architect's next plan must explicitly decide any workaround or rollback and identify the rollback point.
- [ ] Carry the complete chronology, prior whitelist and rationale for resolved issues into every escalation. Explicitly transfer test and file exclusions from diagnostics to the next self-contained whitelist.
- [ ] Count each plan version as a cycle. Stop after the fifth and ask Sasha whether to continue or close; do not start a sixth independently. If successful earlier, stop and report the result.

### Acceptance

- [ ] Fast-forward the progress branch into the original working branch according to the plan. Audit disk immediately afterward, including backup-to-live token IDs, effective allowlist and multiplex after migration.
- [ ] Obtain Sasha's fresh explicit permission for a specific restart window before restarting; do not carry permission over to another attempt. A live check also requires separate authorization. Until then, restrict verification to disk and existing inbound logs.
- [ ] After authorized restart and live check, verify both a DM reply and group inbound with a reply in the same `message_thread_id`. Do not use concurrent production `getUpdates`. Health commands, outbound cron messages and DM alone do not establish group delivery.
