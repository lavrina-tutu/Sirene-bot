# 2026-08-12: tz-dev SOUL.md / AGENTS.md Optimization

## Changes to SOUL.md

**Before (3.1 KB):**
- Role, Character, "New TZ" command, Workflow, Available Resources, Hard Rules
- Included: workvault-rag skill reference, QMD-Search path, Sonnet-5 model reference

**After (1.9 KB):**
- Role, Character, Core Principles, Hard Rules
- Removed: "New TZ" command (procedural), "Workflow" (skill reference), "Available Resources" (environment facts), QMD-Search path, Sonnet-5 model reference
- Added: "Говорить всегда честно и напрямую, даже если правда неудобна" to Character
- R3 "Главный принцип" section: "Делать точно как сказано. Правила не обходить. Хочешь отступить — спроси разрешения у Саши."
- "Лишняя информация — зло" principle added

**Classification by docs (hermes-agent docs/personality):**
- SOUL.md = personality, voice, core values ✅
- AGENTS.md = project context, conventions ✅
- Procedures/commands → AGENTS.md or skills (not SOUL.md)
- Environment facts → AGENTS.md (not SOUL.md)

## Changes to AGENTS.md

**Before (5.6 KB):**
- Full Hermes ASCII tree + "Ключевые файлы" sub-block
- TZ catalog, Skills (tz-workflow, hermes-feature), Rules (R3, backups, TЗ согласование, Skills)
- Cursor CLI pattern, Key paths table (7 rows)

**After (3.8 KB):**
- Removed: ASCII tree (duplicative of paths table), "Ключевые файлы" sub-block
- Added: Dialog rules (R1, R2, R3 "Вопросы Саше")
- Simplified: Key paths → 2 lines (cron logs, WorkVault data)
- Removed: "Один скилл = одна задача" (covered by skill authoring principles), symlink path detail
- R3 kept in both AGENTS.md and SOUL.md (user decision — reinforced in both)

## Key Decisions

1. **AGENTS.md is CWD-based, NOT profile-based** — tz-dev isolation achieved via `terminal.cwd` in config.yaml
2. **SOUL.md dedup rule:** procedural instructions, environment facts, tool references → move to AGENTS.md or skills
3. **Key paths optimization:** paths managed by built-in tools (config, skills, memory) don't need listing — only manual-access paths (cron logs, WorkVault)
