---
name: usertools-llm-integration
description: "Diagnose USERTOOLS LLM, environment and cron failures."
version: 1.1.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [usertools, PFS, MOFS, llm-config, cron, env-leak, dedup]
    related_skills: [protocolfromsummary, mofs-operations, hermes-feature, pfs-mff-troubleshooting]
---

# USERTOOLS × LLM integration

Use for shared LLM, environment, config and cron integration contracts in `<USERTOOLS_ROOT>` (`~/USERTOOLS`); business logic belongs to each tool. External tools use their own processes and may call the corporate gateway without appearing in Hermes `state.db` or `agent.log`. Gateway usage absent from those logs can originate in PFS, MOFS or another external tool. Identify the actual caller, entrypoint, interpreter, configuration and environment before attributing usage or changing anything.

## LLM contract and ownership

- New LLM features take `model.default`, `model.provider` and the matching `custom_providers` base URL and API key from `~/.hermes/config.yaml`. Do not introduce fallback model or endpoint literals. If the required default model or endpoint is absent, fail soft without making the call.
- Reuse the owning tool's existing transport and model configuration where appropriate; do not import another tool's configuration as its library. A shared reader or a direct Hermes `call_llm` integration is an architectural choice, not permission to bypass the default contract.
- MOFS owns meeting → project association; PFS owns task → slug. «Слаг в MOFS не устанавливаем, работаем только в PFS». Do not extend MOFS to set task slugs. Resolve ownership before changing a neighboring package.
- Current MOFS `_load_llm_config` reads Hermes defaults and then applies `MOFS_LLM_*` overrides; its existing implementation also has fallback literals. Its `llm_fallback.py` uses an OpenAI-compatible client, not the historical Anthropic implementation. Treat any alignment of existing fallback behavior as a separate change; the stricter no-literal rule above governs new functionality.
- Before converting an agent cron to script mode, inspect all mandatory LLM steps. Preserve PFS semantic dedup and alert on repeated empty or failed runs; a script may be used only if it still runs the required orchestration.
- For PFS dedup, filter candidate tasks programmatically by the same `assignee_userkey` before fuzzy and LLM comparison. A prompt telling the model that different assignees mean different tasks is not a structural filter.

Details and original decisions: `references/default-llm-contract.md`; historical workdir and PFS dedup case: `references/integration-history.md`.

## Environment and registry drift

`~/.hermes/lib/usertools_env.py` loads the central `~/.config/hermes/.env`, then the optional local file, using `os.environ.setdefault`. Existing process environment wins over both; the central file wins over the local file for duplicate keys. Call the loader before code reads environment settings. Do not claim local precedence or add `override=True` to the shared loader without a separately approved change.

When a registry or state appears under a neighboring tool, inspect the configuration file *and* the actual process/session environment for generic names such as `TOOL_DIR` and `LOGS_PATH`. A cleaned file does not clean variables inherited by a long-lived process. Isolate generic paths with tool-specific names and verify in a fresh session and the real cron context. For registry repair, back up copies, deduplicate by key, choose the record with maximum `processed_at` on collision, write atomically with a same-directory temporary file and `os.replace`, then handle stale locks only after confirming they are orphaned. Do not execute repairs outside their authorized scope.

Before removing a local secret duplicate, confirm that its source exists in the central file and save a backup; retain tool-specific keys. On widespread unauthorized responses or misleading Confluence 404s, check actual secret resolution and compare safe indicators such as length or equality, without printing full values. A 404 containing `authorized:false` can be an authorization failure, not evidence that every page disappeared.

Registry diagnostics: `references/env-leak-registry-merge-20260817.md`; rollout and backups: `references/usertools-env-loader-rollout-20260827.md`; token diagnosis: `references/authentication-diagnostics.md`. Historical material in these files is not current loader precedence.

## Runtime and verification

1. Trace the actual cron or wrapper to its production entrypoint, interpreter, venv, environment and flags. Run import checks with that interpreter, not a convenient neighboring Python. A neighboring venv can hide a missing dependency or produce unrelated `ModuleNotFoundError`.
2. Every tool using `usertools_config.load_tool_config` needs PyYAML declared in its own dependencies and installed in its production venv: the loader imports `yaml` at module level. Verify `import yaml` with that exact binary. Do not use a cross-version `site-packages` insertion or a shared Python 3.11 package directory in Python 3.14.
3. If `load_tool_config(..., keys=...)` is explicit, include every environment key that downstream settings read, including shared keys such as `WORKVAULT_PATH`; otherwise use the supported complete mode `keys=None`. A dry-run that never reaches `load_settings` is insufficient evidence.
4. Reproduce the real entrypoint and its flags for acceptance when authorized. For PFS reproduce the actual cron mode, including `PFS_POST_SWITCH=1` for `run-pending` where applicable: another mode can write to different targets. Creating a one-shot cron or executing a real tick requires explicit authorization; use safe, non-mutating checks until then.
5. Verify results independently: inspect relevant diffs without exposing secrets, check declared dependencies and the real interpreter, and confirm retained secret sources. Do not infer a production tick from a unit test or an import alone.
6. For Codex outside a git repository verify current `codex exec --help` and use `--skip-git-repo-check` when supported. Do not create a temporary root `.git` merely to satisfy an outdated prerequisite; root git can affect manifest drift.

Actual wrapper, interpreter and ABI contract: `references/usertools-cron-venv-syspath.md`; config-loader dependencies, explicit keys and entrypoints: `references/config-loader-verification.md`. Tool-specific business rules are in `protocolfromsummary` and `mofs-operations`; use `dev-workflow` for development routing.

## Diagnostic sequence

- First map observed usage or a failed job to its owner. Search USERTOOLS source and the job's actual wrapper for client construction and LLM calls; exclude virtual environments and generated package copies when identifying authoritative code. Gateway usage alone does not establish which component made the request.
- For misplaced state, trace both the configured destination and the inherited environment. Check login-shell and service context as well as the current file, without exposing secret values. Confirm the expected canonical registry before considering a merge. Compare by registry key rather than overwriting one whole copy with another.
- For an environment migration, inspect the central and local key *names* before deduplication. Existing inherited variables override both files; a central duplicate suppresses a local value even if that value is valid. Check the effective source, make a backup and retain unique local settings. Length and equality comparisons can reveal corruption without disclosing a token.
- For import failures, trace the actual launched binary through the job definition and wrapper. A Python script launched by the Hermes scheduler may run under the Hermes interpreter regardless of its shebang. Where the owning tool has a separate venv, the documented shell wrapper `exec`s that tool's interpreter; do not splice incompatible binary packages into the running process.
- For configuration checks, exercise every environment key used by the actual settings path and verify the loader's dependency in the actual production venv. Treat import success as a diagnostic, not proof that an integration call or cron tick has succeeded.
- For PFS, compare both the assignee and the intended cron flags. Semantic similarity across different assignees must not merge tasks. A manual run with a different post-switch mode exercises a different write path and is not acceptance evidence.

A change to the shared loader, live configuration, production jobs or service behavior is a separate implementation task. Preserve the documented fail-soft behavior, the tool boundaries and authorized write set when reporting the result.
