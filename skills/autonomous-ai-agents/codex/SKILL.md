---
name: codex
description: "Use Codex CLI for coding, review and availability."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Codex, OpenAI, Code-Review, Refactoring]
    related_skills: [claude-code, hermes-agent]
---

# Codex CLI

Use Codex CLI for coding, refactoring, PR review and availability diagnosis. This skill describes the CLI; it does not replace DevWorkflow routing or its configured role models. For DevWorkflow phases use the canonical `emit-prompt` → `invoke-role` path and its binding contract. A consultation outside a phase uses the appropriate direct interface and the configured role; do not invoke a phase without its slug and phase.

## Authentication and configuration

Codex CLI OAuth (`~/.codex/auth.json` or OS keyring), Hermes provider OAuth (`~/.hermes/auth.json`, `openai-codex`) and an OpenAI API key are different authentication paths. A missing `OPENAI_API_KEY` alone does not establish CLI failure. Treat auth files and access tokens as secrets. `codex login status` reports local login state, not a proven usable model call.

On a headless host select the supported device flow, access-token flow or API-key flow for the account and CLI; API-key billing and model availability can differ. Device flow is complete only when the login process completes, not when a code is displayed. Keep scalar TOML keys such as `cli_auth_credentials_store`, `model` and `approval_policy` in the schema expected by the installed CLI. For config errors test with a minimal configuration. See `references/headless-auth.md` for the original recipes and historical context; confirm current CLI help before use.

## Roles and review

Read the role model and effort from `tools.dev_workflow` in `~/WorkVault/Registries/EcosystemConfig.yaml`; verify the actual model ID and supported effort in the host catalog. Do not hardcode the old conflicting reviewer tables. Model/effort suitability and independence are governed by the current approved role contract; do not assume a model's default effort applies to another. Historical role selection: `references/role-selection.md`.

For a DevWorkflow review write `## Вердикт`, put the exact `verdict=APPROVE` or `verdict=REQUEST-CHANGES` on its first line, and make the following review sections H2 (`##`), so the parser terminates the verdict block at the next H2. Do not put a contrary verdict marker in the verdict block. Preserve the expected canonical artifacts and H2 boundaries. Details: `references/devworkflow-integration.md`.

## Execution and result

Use `codex exec` (alias `codex e`) for one-shot, non-interactive calls; check the installed version's help for flags. Git is normally checked; for a non-git workspace use the supported `--skip-git-repo-check`. A PTY is appropriate for interactive device login or other modes that require a terminal; it is not a blanket requirement for `exec`. Select the sandbox for the explicit authorization and environment; sandbox failures require diagnosis, not an automatic permission to disable isolation.

Pass the prompt as a positional argument or on stdin. In the installed CLI `-p` selects a profile, not a prompt; do not copy the historical migration recipe's `-p "$(cat ...)"`. For `model_reasoning_effort`, distinguish shell quoting from argument-vector quoting: in shell `-c 'model_reasoning_effort="high"'`; in a Python argv element use `model_reasoning_effort="high"` with no literal outer single quotes. Inspect `turn.failed` and HTTP 400 in the event stream before changing a task or model.

`codex exec --json` emits NDJSON events, not a single JSON document. Parse each line; retain the last nonempty `item.completed` with `item.type == "agent_message"` and `item.text`, and separately record `turn.failed`. Do not persist raw tool events as the report. A migration adapter must preserve the existing consumer envelope `{subtype,is_error,result}` and accurately set error status; use the last final message as `result` and do not mistake an empty result or failed turn for success. See `references/exec-and-event-stream.md` for parser and quoting details.

When migrating Cursor callers, audit all *live* executable and authoritative callers, including cron prompts and tool entrypoints; documentation fallback and dead scripts are not live calls. Keep the consumer envelope compatible, syntax-check edited scripts and verify the actual path when authorized. See `references/cursor-migration.md` for the historical migration audit; the command there uses a superseded `-p` syntax.

## Availability and recovery

A successful model response with errors inspected is the availability signal. Login status, process rc=0, a prompt echo and unauthenticated HTTP 401/403 do not establish a successful model call. Examine the event stream and stderr for expired-token/authentication errors and distinguish them from reachability. `codex models list` may not exist; inspect the host model catalog and CLI help.

The exact spend-cap message `You hit your spend cap set by the owner of your workspace` means account quota exhaustion, not an instruction-quality error; do not repeatedly strengthen the prompt. Once the cap is lifted, resume the same phase with the **complete original task prompt** and the canonical phase binding. Verify a re-emitted packet contains the task body and expected artifacts; never invoke a header-only packet. If the pipeline cannot legally bind the complete prompt, stop for the workflow's recovery procedure rather than bypassing it. See `references/availability-and-recovery.md`.

For service-context sandbox failures inspect the actual bubblewrap/user-namespace error, workdir and permissions separately from auth and quota. Any change of sandbox policy must be authorized for the task. Diagnostic history: `references/gateway-sandbox-diagnostics.md`.

Worktree, background and PR examples are historical recipes in `references/worktree-recipes.md`; check current CLI help and authorization before using them. Do not send comments, create PRs or change external state without the user's instruction.

## Practical invocation checks

Before invoking a role, identify whether it is a DevWorkflow phase or an independent consultation. A phase is bound to its emitted packet, workspace and canonical artifact. Do not assemble a second manual pipeline prompt or treat successful process exit as proof the artifact was accepted. For a consultation, pass the question, the relevant current facts and the requested output scope to the direct interface; obtain its model and effort from the configured role rather than an old example.

Before any one-shot command, check the installed `codex exec --help`, the intended working directory, the user's authorized sandbox and the required output form. If a non-git work directory is intended, the supported flag allows it without creating a temporary root repository. Authentication and model configuration belong to the CLI account actually used by that process; the Hermes provider's credentials are not interchangeable evidence.

For shell commands, the shell removes its quoting before arguments reach the CLI. An integration using a Python argv list has no such shell step. An extra literal quote changes the parsed TOML or API value; a 400 in `turn.failed` can therefore indicate a malformed effort argument rather than a model or prompt failure. Save the final model answer and error indicator, not the raw stream of tool output or intermediate messages.

For a stateful caller migration, find the callers that actually execute, including inline job definitions. A documentation mention of a fallback is not itself an active invocation. Preserve the contract consumed downstream, including `subtype`, `is_error` and `result`; compare the adapter output to that consumer's expectations. Verify error cases as well as a successful final message when safe, and do not call external services just to validate documentation.

During quota recovery, keep the task body, canonical artifact destination and phase identity together. A packet that contains only headers or MUST-read pointers is not an equivalent prompt. If the old full prompt cannot be bound by the current pipeline contract, document the blockage and follow the workflow's recovery mechanism. The history reference records an earlier manual recovery, not permission to bypass current binding requirements.

Background processing and worktrees are operational choices, not default approval to create branches, push, post PR comments or remove worktrees containing other people's work. Monitor the selected process and inspect its completion and error evidence before reporting an outcome.
