---
name: hermes-agent
description: "Configure, extend, or contribute to Hermes Agent."
version: 2.2.0
author: Hermes Agent + Teknium
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, setup, configuration, multi-agent, spawning, cli, gateway, development]
    homepage: https://github.com/NousResearch/hermes-agent
    related_skills: [claude-code, codex, opencode]
---

# Hermes Agent

Use this skill to configure, operate, troubleshoot, or contribute to Hermes Agent, including CLI, gateway, providers, profiles and independent processes. Hermes runs in terminal and messaging platforms, with skills, persistent memory, tools, and provider selection. See [Hermes documentation](https://hermes-agent.nousresearch.com/docs/).

## Basic operations and routing

- `hermes` starts interactive chat; `hermes chat -q "..."` is a noninteractive query; `hermes setup`, `hermes config`, `hermes doctor` and `hermes status` inspect or configure the installation. `hermes model` is interactive: use a supported noninteractive interface such as `hermes config set` for automation, after checking the installed version.
- Use `hermes --help` and [CLI reference](references/cli-reference.md) for commands; use `/help` and [slash commands](references/slash-commands.md) in an interactive session. `hermes_cli/commands.py` is the slash registry of record.
- `$HERMES_HOME` selects the profile home: configuration, secrets, skills, sessions, logs and auth live there. Default is `~/.hermes`; profiles have isolated homes. Never expose secrets in output.
- For configuration, provider and toolset tables, security/privacy and voice, read [configuration](references/configuration.md). For separate processes, tmux, delegation, cron, curator and kanban, read [process orchestration](references/process-orchestration.md). Use delegation for bounded subtasks; a separate process has an independent session. Follow local workflow and authorization rules.
- For platform-specific input, sandbox and test setup, read [Windows operations](references/windows-operations.md). For source layout, extensions and testing, read [contributing](references/contributing.md).

## Conditions of operation

- Verify each config key's actual reader in the current code before documenting or relying on it; an unknown key may be silently ignored. Historical statements about `routing` and required skill frontmatter conflict: check the installed version rather than assuming either. See [configuration history](references/configuration-history.md).
- Choose the compressor so its context can fit the main model's compression threshold. `auxiliary.compression.model` is a separate setting from delegation and session_search; changing one does not select the others. Check current code and provider limits, then lower the threshold or choose a suitable compressor when needed.
- On provider migration, check main model, delegation, auxiliary tasks including compression, and each cron override separately. `hermes config set` changes only the specified key. Verify each component before declaring migration complete.
- Apply the correct reload mechanism for the changed component: tool changes need a new session to preserve prompt caching; `/reload-skills` rescans skills, `/reload` reloads environment variables in CLI, and `/reload-mcp` reloads MCP. Check code and service requirements for config and code changes; do not promise one reload for all.
- For cron `no_agent` → agent, check the current API first; if JSON patching is necessary, find the job by ID, preserve that ID and update `no_agent` and `script` consistently. Do not temporarily rename the ID. Details: [process orchestration](references/process-orchestration.md).
- Use one primary identity source; a procedural skill should point to the persona source, not copy SOUL or duplicate personality instructions.
- For Copilot, verify its own authentication flow. For gateway platforms, check platform-specific intents, subscriptions and service prerequisites. Diagnose against actual logs and installed version.
- On Windows use the appropriate terminal keys, UTF-8 without BOM and the correct Python/test environment; inspect `SYSTEMROOT`, `WINDIR` and `COMSPEC` when sandbox child environment is suspect. For cross-platform tests patch all OS-information sources used by the code consistently. For remote backends describe the backend environment, not the host.
- Preserve prompt caching and message role alternation. Use `get_hermes_home()` for profile-safe paths; tool handlers return JSON strings and new tools require `check_fn`. Keep secrets in `.env` and configuration in `config.yaml`.

## Diagnosis and verification

- For an empty `session_search`, check recent sessions first, then search for 1–3 distinctive words. Inspect the index only if the problem persists. For auxiliary failures, check the task's provider and credentials independently.
- For unavailable tools, inspect toolset and requirements, then start a new session when needed. For skills, inspect the installed home, frontmatter and reload state. For gateway failures check status, logs, platform auth and prerequisites. For voice, check STT enablement, provider and dependencies.
- [Troubleshooting](references/troubleshooting.md) contains session search, provider migration, identity, compression and auxiliary recipes. Verify examples against current code; they describe their original environment.
- [Contributor guide](references/contributing.md) covers layout, tool and command registration, tests and execution-environment hints. Test the affected behavior using the appropriate environment and check real results before reporting success.
