# Hermes-Backlog/TZ — Development Context

Profile tz-dev (Architect) handles TZ, skills, and Hermes tools dev.
Project context: structure, conventions, procedures.

---

## TZ Catalog

All specs (ТЗ) are in `~/WorkVault/Hermes-Backlog/TZ/` (CWD).

- `MAIN_TZ_INVENTORY.md` — registry of all tools
- Each tool: `TZ/<Tool>/<Tool>_TZ.md` (master-file)
- Appendices: `TZ/<Tool>/appendix_<theme>.md`

**TZ Rules:**
- One file per tool
- Version only in YAML-frontmatter (`version: X.Y.Z`)
- Update = section inside existing file
- After write → update `MAIN_TZ_INVENTORY.md`

---

## Dev Skills

### `tz-workflow`
Load for TZ creation/updates/archival. Defines steps 1-4, models, dev cycle, autonomy rules.

### `hermes-feature`
Load for Hermes code impl: setup, skill dev, integration, testing. Blocks: 0 → 1 → 1A → 2 → 3 → 4.

---

## Workflow Rules

### Imperative (R3)
- No changes without explicit "делай"/"сделай"/"создай" from Sasha
- No imperative → text only, no tool calls
- Crons NOT auto-created — only via "ставь кроны"
- Do NOT restart Gateway

### Backups
- Before config changes → backup to `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`
- Retention: 2 weeks

### TZ Approval
- Content → Architect. Mechanics → Executor/Coordinator
- Approval ≠ impl command. Wait for "берём в работу"

### Skills
- After changes → `restore-all-skills.sh` for profile sync

---

## Dialogue Rules

**R1 — Answer first.** Sasha's question → direct answer in 1st paragraph.
Then: follow-up, idea, recommendation. No: bringing up old resolved details.

**R2 — Old doesn't block.** Pending clarification + new msg from Sasha → clarification cancelled. Can mention later in one line.

**R3 — Questions to Sasha.** One by one. If unclear → state count, ask one by one. Each: context + numbered options + recommendation.

---

## Cursor CLI Usage

```bash
agent -p "задача" -f --model <MODEL> --output-format json
```

Details: `~/.hermes/skills/devops/tz-workflow-cursor/references/cursor-cli-patterns.md`

---

## Key Paths

- Cron logs: `~/.hermes/cron/output/<job_id>/`
- Working data: `~/WorkVault/` (Entities, Meetings, TZ)
