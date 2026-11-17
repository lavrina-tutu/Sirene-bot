---
name: claude-code
description: "Run and supervise Claude Code CLI via Hermes."
version: 2.3.0
author: Hermes Agent + Teknium
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Claude, Anthropic, Code-Review, Refactoring, PTY, Automation]
    related_skills: [codex, hermes-agent, opencode]
---

# Claude Code — Hermes orchestration

Use this skill to run and supervise Claude Code CLI for an authorized task. Follow the active project's workflow, delegation and permission boundaries; this skill does not independently authorize parallel agents, network actions, writes or permission bypass.

## Prerequisites and mode

Check that `claude` is installed, authenticated and usable in the intended project directory; inspect `claude --version` and `claude --help` for the installed version. Check available budget and startup cost before a paid run. The CLI was unavailable in the environment checked on 2026-11-17: flag behavior and historical cost claims below require local verification. Do not assume a universal $0.05 minimum.

Choose print mode (`-p`) for a bounded one-shot task and an orchestrated terminal/tmux session for interactive multi-turn work. Specify the project working directory and only the tools and access needed for the authorized task. In print mode describe the task as ordinary text rather than relying on interactive slash commands. Where supported, set a suitable `--max-turns` and budget; the original guide describes these limits as print-mode features, so verify current support first. Allow enough turns for schema extraction to read its inputs. Verify the Python interpreter if the task requires Python.

For print mode examples, stdin, JSON and stream-json, continuation, bare and fallback: [print-mode.md](references/print-mode.md). For interactive launch, monitoring, keys and cleanup: [interactive-tmux.md](references/interactive-tmux.md). These contain version-sensitive historical examples; inspect actual dialogs and current CLI help before acting.

## Session and result handling

Capture the result and check exit status plus JSON `type`, `subtype` and error information when using structured output; do not infer success from text alone. Preserve `session_id` for a later `--resume`, keep the same project cwd for continue/resume, and verify the current CLI's session semantics. When requesting a schema, parse `structured_output` from the result and validate it against the required schema. Stream output may contain separate events; inspect completion and errors.

`--append-system-prompt` and its file form add to the default prompt; `--system-prompt` and its file form replace it in the original CLI guide. Verify these flags in the installed CLI and select intentionally, since replacement can remove built-in instructions. Before using `--bare`, verify the available authentication method and which project context, hooks, plugins or MCP settings it excludes; the source describes API-key authentication and absent OAuth in that mode, but this has not been verified locally.

For interactive work, inspect the actual screen before sending keys. Handle a displayed trust prompt only within the authorized scope; never blindly send Enter when trust may already be saved. Do not accept a permissions-bypass dialog automatically; use bypass only when explicitly permitted by the governing workflow. Monitor for progress or questions rather than killing a slow job. Close the tmux session you created after work is complete. Monitor context and compact or start a fresh session when appropriate; historical 70%/85% figures are heuristics, not verified quality thresholds.

## Completion

Review Claude's actual result and changed files, run the checks appropriate to the task, and report changes, verification and unresolved failures. Preserve the user's scope and the project workflow throughout. A CLI response alone is not proof that edits or tests succeeded.

- Historical flag, slash-command and environment inventory: [cli-reference.md](references/cli-reference.md).
- Settings, CLAUDE.md, rules and memory: [project-configuration.md](references/project-configuration.md).
- Agents, hooks and MCP examples: [extensions.md](references/extensions.md).
- Review and worktree examples: [review-and-parallel-work.md](references/review-and-parallel-work.md).
- Dated, unverified cost and context estimates: [version-sensitive-notes.md](references/version-sensitive-notes.md).
