# Prompt Stack Investigation — 11.08.2026

Session investigating Hermes system prompt structure, context file discovery, and profile isolation.

## Test Setup

- **Profiles:** default (active, Telegram group "Сирень Workspace", thread 1), tz-dev
- **CWD:** `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ`
- **Gateway PID:** 1928797, CWD: `/home/tkachenkoav/.hermes/`
- **Config:** `display.personality: sirene`, `terminal.cwd: .` (default), `terminal.cwd: /home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` (tz-dev)

## Key Findings

### 1. Prompt stack order confirmed
By comparing what I see in my own prompt vs docs, the stack is:
SOUL.md → Personality → AGENTS.md → Skills → MEMORY → USER PROFILE → system_prompt → Session → Tools

### 2. AGENTS.md is CWD-based, not profile-based (confirmed)
- Creating `~/.hermes/profiles/default/AGENTS.md` does NOT load it — Hermes ignores profile dirs for context files
- Only CWD is checked: `.hermes.md` (walks to git root) → `AGENTS.md` (CWD + subdirs) → `CLAUDE.md` → `.cursorrules`
- No profile-level mechanism to select/block context files

### 3. state.db sessions.cwd is NULL
Query result: all recent sessions (default + tz-dev) have cwd=NULL in state.db. Session CWD is determined dynamically, not persisted.

### 4. gateway CWD vs session CWD mismatch
- Gateway runs from `~/.hermes/` (PID 1928797)
- Default config has `terminal.cwd: .` → should resolve to `~/.hermes/`
- Yet current session CWD = `~/WorkVault/Hermes-Backlog/TZ/`
- Source of this discrepancy not identified — possibly the Telegram gateway sets CWD from another mechanism

### 5. SOUL.md / personality / skill triplication found
Same persona (Sirene identity, values, R0-R3 rules) exists in:
- `~/.hermes/SOUL.md` — 5.9 KB, most complete
- `config.yaml → agent.personalities.sirene` — ~3 KB, older version
- `persona/sirene-chat-friends` skill — ~12 KB, includes operational procedures

Per the docs: SOUL.md = identity, personality = session overlay (delta), skills = procedures. Current setup violates this.

### 6. Profile tz-dev has own SOUL.md
`~/.hermes/profiles/tz-dev/SOUL.md` — "Архитектор", different personality (2.2 KB). Works correctly — profile isolation for SOUL.md is intact.

## Methodology

1. Loaded `hermes-agent` skill + official docs (personality + context-files pages)
2. Read `~/.hermes/SOUL.md`, `~/.hermes/profiles/tz-dev/SOUL.md`, `config.yaml`
3. Queried `state.db` via Python (sqlite3 CLI not available)
4. Checked gateway process CWD via `/proc/<pid>/cwd`
5. Tested other LLM's claim: AGENTS.md in profile dir — confirmed it won't load
