# Hermes-Backlog/TZ — Development Context

Profile default (Сирень) handles TZ, skills, and Hermes tools dev.
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

Для ТЗ, кода и скиллов использовать `devops/dev-workflow` и его context/emit path. `tz-workflow` сохраняет хранение ТЗ; `hermes-feature` — предметные implementation/QA rules. Роли и модели — YAML; raw launch не использовать.

---

## Workflow Rules

### Imperative (R3)
- No changes without explicit «делай»/«сделай»/«создай» from Sasha
- No imperative → text only, no tool calls
- Crons NOT auto-created — only via «ставь кроны»
- Do NOT restart Gateway

### Backups
- Before config changes → backup to `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`
- Retention: 2 weeks

### TZ Approval
- Content → Architect. Mechanics → Executor/Coordinator
- Approval ≠ stop of implementation: after a closed brief and `TZ:finalize` the train runs itself
- The phrase «берём в работу» is not a hold; showing AC ≠ waiting for Sasha

### Skills
- After changes → `restore-all-skills.sh` for profile sync

---

## Правила диалога

Правила диалога (R1–R3) берутся из активного SOUL; этот каталог хранит правила ТЗ и среды.

---

## Термины
Имена фаз/ролей/скиллов — ТОЛЬКО из `GLOSSARY.md` (этот каталог). Формат фазы: `PREFIX:фаза`.
Перед первым `PREFIX:фаза` — прочитать `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`.
Голые `TZ`/`HF`/`ORCH`/`DEV` без двоеточия запрещены.

## Key Paths

- Cron logs: `~/.hermes/cron/output/<job_id>/`
- Working data: `~/WorkVault/` (Entities, Meetings, TZ)
