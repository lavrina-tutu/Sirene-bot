---
name: cursor-code
description: "Delegate coding to Cursor Agent CLI (PRs, bugfixes)"
version: 1.0.1
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  description: "Delegate coding to Cursor Agent CLI (features, TZ implementation, bugfixes)."
  tags: [Coding-Agent, Cursor, Autonomous, Refactoring, Code-Review]
  related_skills: [claude-code, codex, opencode, hermes-agent, hermes-feature, tz-workflow]
---

# Cursor Code CLI

Delegate coding tasks to [Cursor Agent CLI](https://cursor.com/cli) via the Hermes terminal. Cursor CLI is Cursor's autonomous coding agent — same models, rules, and MCP as the IDE, but driven from the command line.

## When to use

- Building features
- Refactoring
- Bugfixes
- PR reviews
- Batch issue fixing

Requires `agent` CLI and a Cursor account with API key.

## Prerequisites

- **Install:** See Installation section below
- **Auth:** `CURSOR_API_KEY` env var (from Cursor Dashboard → API Keys) or `agent login`
- **Verify:** `agent --list-models` should return model list
- **Git repo required** for code tasks (agent reads project context from it)
- **`-f` flag required for headless** — bypasses workspace trust dialog

## Installation

```bash
# IMPORTANT: use shell redirect (>), NOT -o flag
curl -fsS https://cursor.com/install > /tmp/cursor-install.sh
bash /tmp/cursor-install.sh
```

Verify:
```bash
agent --version  # e.g. 2026.07.23-e383d2b
agent --list-models  # requires CURSOR_API_KEY
```

Binary location: `~/.local/bin/agent` (symlink to `~/.local/share/cursor-agent/versions/<version>/cursor-agent`)

## Authentication

Get API key from Cursor Dashboard → API Keys (left sidebar, under "Data Management"). Key format: `crsr_...`. Set on VM:

```bash
export CURSOR_API_KEY=crsr_your_key_here
agent --list-models  # verify
```

Alternative: `NO_OPEN_BROWSER=1 agent login` — prints URL, open on any computer with browser.

## One-Shot Tasks (Print Mode)

Print mode (`-p`) is the primary integration path for Hermes. Non-interactive, runs and exits.

```bash
agent -p "Add dark mode toggle to settings" -f --output-format json
```

**Required flags for headless:**
- `-p` — print mode (non-interactive)
- `-f` — force/trust workspace (CRITICAL: without this, agent asks for workspace trust and hangs)

**Recommended:**
- `--output-format json` — returns structured result with usage, session_id, duration

### JSON Output

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 12898,
  "result": "Done. All 3 tests pass.",
  "session_id": "587fdbe6-...",
  "usage": {
    "inputTokens": 12053,
    "outputTokens": 406,
    "cacheReadTokens": 23680,
    "cacheWriteTokens": 0
  }
}
```

Key fields: `subtype` (success/error), `session_id` (for resumption), `usage` (token tracking).

## Modes

| Mode | Flag | Effect |
|------|------|--------|
| Agent (default) | — | Full access: read, write, execute |
| Plan | `--mode plan` | Read-only, planning/analysis only |
| Ask | `--mode ask` | Q&A, explanations, no edits |

```bash
# Planning — safe for initial analysis
agent -p "Analyze auth module for security issues" -f --mode plan --output-format json

# Q&A — quick questions
agent -p "What does the middleware stack look like?" -f --mode ask --output-format json
```

## Model Selection

```bash
agent -p "task" -f --model claude-opus-4-8 --output-format json
agent -p "task" -f --model gpt-5 --output-format json
```

Parameterized models:
```bash
agent -p "task" -f --model 'claude-opus-4-8[context=1m,effort=high,fast=false]' --output-format json
```

List available models: `agent --list-models`

Full model catalog with reasoning levels: `references/models.md`.

## Session Management

```bash
# Continue most recent session in current directory
agent -p "Add error handling too" -f --continue --output-format json

# Resume specific session (session_id from JSON output)
agent -p "Now add tests" -f --resume 587fdbe6-f879-4b74-aaf9-62c46f4aa5c6 --output-format json
```

Sessions are tied to working directory. `--continue` finds the most recent one for current dir.

## Role in Hermes ecosystem

Cursor CLI can fulfil any of the three roles defined in `hermes-feature` and `tz-workflow`. **Important:** Cursor does NOT have DeepSeek models. Use Claude/GPT equivalents with matching reasoning levels.

| Роль | Hermes (DSV4) | Cursor equivalent | Mode |
|------|--------------|-------------------|------|
| Архитектор | DSV4-H (high) | `claude-sonnet-5-thinking-xhigh` or `claude-opus-4-8-thinking-high` | `--mode plan` or default agent |
| Исполнитель | DSV4-M (medium) | `claude-sonnet-5-medium` or `claude-opus-4-8-medium` | default agent |
| Координатор | DSV4-L (low) | `claude-sonnet-5-low` or `gpt-5.5-low` | `--mode ask` |

Other available families: GPT-5.x (Sol, Terra, Luna, Codex), Cursor Grok, Composer, Gemini, Kimi, GLM. Full model list: `references/models.md`.

## Custom subagents

Define specialized agents in `.cursor/agents/<name>.md` (project-level, git-tracked):

```markdown
---
name: tz-implementer
description: Implements features from ТЗ specifications
model: claude-opus-4-8
tools: [Read, Write, Bash]
---
You implement features from technical specifications.
Follow the plan exactly. Report progress after each step.
Write tests for all new code.
```

Use: `agent -p "@tz-implementer реализуй блок авторизации по плану" -f`

Subagents can also be defined globally at `~/.cursor/agents/`. Cursor CLI auto-discovers them.

## Hermes Integration Pattern

```bash
terminal(
  command='agent -p "Fix the auth bug: tokens expire without refresh" -f --output-format json',
  workdir='/path/to/project',
  timeout=300
)
```

### For scratch/temp work (agent needs a git repo)

```bash
terminal(
  command='cd $(mktemp -d) && git init && agent -p "Build X" -f --output-format json',
  timeout=300
)
```

### Hermes terminal() parameters

| Parameter | Recommendation |
|-----------|---------------|
| `command` | `agent -p "prompt" -f --output-format json` |
| `workdir` | Project directory (must have `.git`) |
| `timeout` | 120-300s (simple tasks ~15s, complex ~60-120s) |

## Parallel Tasks

Run multiple agents in separate worktrees:

```bash
terminal(command="agent -p 'Fix issue #101' -f --output-format json", workdir="/tmp/issue-101", background=True)
terminal(command="agent -p 'Fix issue #102' -f --output-format json", workdir="/tmp/issue-102", background=True)
```

## Pitfalls

1. **`curl -o` returns HTML, not script** — always use `curl ... > file.sh`, never `-o file.sh`. Cursor's CDN detects output target and serves HTML to `-o` requests.
2. **`-f` is mandatory for headless** — without it, agent prompts for workspace trust and hangs in non-interactive contexts.
3. **Must run in a git repository** — agent reads project context from `.git`. Use `git init` for scratch work.
4. **Auth required before any command** — `agent --list-models` is the quickest smoke test.
5. **API key from Dashboard, not IDE settings** — IDE settings use provider API keys (OpenAI/Anthropic), not Cursor's own key. Go to `cursor.com/dashboard` → API Keys.
6. **Session scope is per-directory** — `--continue` resumes the most recent session for the current working directory only.

## Rules

1. **Код меняет ТОЛЬКО Cursor.** Hermes-агент НЕ правит код сам — ни багфиксы, ни фичи, ни скрипты, ни конфиги кодовых проектов. Это абсолютное правило, без исключений.
2. Always use `-f` in headless/terminal contexts
2. Always use `--output-format json` for structured results
3. Use `--mode plan` for analysis-only tasks (safer, cheaper)
4. Set `workdir` to the project root
5. Set generous `timeout` (120-300s)
6. Parse JSON output for `subtype` to detect errors
7. Save `session_id` for resumption in multi-step work
