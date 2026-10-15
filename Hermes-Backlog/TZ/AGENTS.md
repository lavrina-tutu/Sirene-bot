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

### `tz-workflow`
Load for TZ creation/updates/archival. Defines steps 1-4, models, dev cycle, autonomy rules.

### `hermes-feature`
Load for Hermes code impl: setup, skill dev, integration, testing. Blocks: 0 → 1 → 1A → 2 → 3 → 4.

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

**R1 — Ответ первым.** Вопрос Саши → первый абзац ответа прямо по существу.
Затем можно: встречный вопрос, идею, рекомендацию. Нельзя: поднимать
старое неактуальное уточнение.

**R2 — Старое не блокирует.** Открытое уточнение без ответа + новое
сообщение от Саши → уточнение отменено. Вернуться можно одной строкой
в конце ответа.

**R3 — Вопросы Саше. По одному, варианты, рекомендация.** Есть неясность → сказать общее количество вопросов, задавать по одному. Каждый: контекст + нумерованные варианты + моя рекомендация.

---

## Cursor CLI Usage

```bash
agent -p "задача" -f --model <MODEL> --output-format json
```

Details: `~/.hermes/skills/devops/cursor-cli/references/cursor-cli-patterns.md`

---

## Термины
Имена фаз/ролей/скиллов — ТОЛЬКО из `GLOSSARY.md` (этот каталог). Формат фазы: `PREFIX:фаза`.
Перед первым `PREFIX:фаза` — прочитать `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`.
Голые `TZ`/`HF`/`ORCH`/`DEV` без двоеточия запрещены.

## Key Paths

- Cron logs: `~/.hermes/cron/output/<job_id>/`
- Working data: `~/WorkVault/` (Entities, Meetings, TZ)
