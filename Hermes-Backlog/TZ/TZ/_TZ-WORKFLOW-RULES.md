---
type: workflow-rules
scope: WorkVault/Hermes-Backlog/TZ
audience: LLM (Hermes, Cursor, любой агент)
version: 1.4
updated: 2026-09-30
---

> **Синхронизация:** этот файл — зеркало ключевых правил скилла `tz-workflow`. Синхронизирован с дисковым `tz-workflow` **2.7.0** (волна W2 `dev-process-rework`, 28.09). Авто-гейты: `GATE:take-into-work` (`auto-pass: ac-shown`), `GATE:plan-approve`, `GATE:done` (после preflight exit 0, включая снятие operator-hold и пустые open-questions), `GATE:diagnose-review` (по `_fix_plan_*.md`) — **always auto**; never auto (кризисный HITL) = `GATE:go` / `GATE:block-accept`. Класс O (operator-hold) блокирует `GATE:done` до evidence факта; канон — `GLOSSARY.md` §3 и `DevKanbanPipeline_TZ.md` «Поезд — канон v0.4.0», не этот файл. При расхождении норматив = `GLOSSARY.md` + `DevKanbanPipeline_TZ.md` v0.4.2.

# TZ Workflow Rules

## Where to put TZ files
- Active master TZ for a tool: `WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md`
- Composite TZ (like AggregateFromMeetings): keep internal structure inside `TZ/<Tool>/` — modules that are logically parts of the master TZ (e.g. `modules/TZ_A_*.md`), and the PM decision log / open questions / implementation queue (`pm/PM_DECISIONS_LOG.md`, `pm/OPEN_QUESTIONS.md`, `pm/IMPLEMENTATION_QUEUE.md`, `pm/sessions/`) counted as TZ-adjacent decision history and stay under `TZ/<Tool>/pm/`.
- Ad-hoc / one-off TZ: `WorkVault/Hermes-Backlog/TZ/_misc/TZ-<topic>-<YYYYMMDD>.md`
- ALL new filenames and folder names — ASCII only (no Cyrillic). Obsidian vault requirement.

### TZ vs tool runtime/working data (strict split)
`TZ/<Tool>/` contains ONLY the TZ document(s): master TZ, TZ modules that are parts of it, and TZ-level decision history (`pm/`). Anything else lives in the tool's own directory:

- **Code-side tools** (Python packages) → `USERTOOLS/<Tool>/`
- **Vault-side tools** (data + config in WorkVault) → `WorkVault/Tools/<Tool>/`

The following categories are tool runtime/working data and MUST NOT be moved into `TZ/<Tool>/`:

| Category | Examples | Where it belongs |
|---|---|---|
| Briefs (input material for a future/current TZ) | `briefs/`, raw dumps of a Telegram/email discussion | `USERTOOLS/<Tool>/briefs/` or `WorkVault/Tools/<Tool>/briefs/` |
| Research notes / brainstorm | `research/`, external doc excerpts | `.../<Tool>/research/` |
| Review artefacts (agent QA output, patch reviews) | `_review/` | `.../<Tool>/_review/` |
| Runtime state / memory | `classification_memory.json`, `syncs_memory.json`, caches | `.../<Tool>/` (root or `state/`) |
| Test fixtures / sandbox snapshots | `_sandbox/`, sample inputs | `.../<Tool>/_sandbox/` |
| Logs | any `*.log`, run traces | `.../<Tool>/logs/` |

Rule of thumb: if a file is *about* the design of the tool (specification, requirements, decisions on scope) → `TZ/<Tool>/`. If it is *fuel* the tool eats or produces at runtime, or *input* the LLM chewed on to write the TZ → tool's own directory.

## Naming
- One live file per tool. No v1/v2/v3 in filename. Version and date live in YAML frontmatter.
- Frontmatter template: `tool`, `version`, `date`, `status`, `last-section-added`.

## How to edit
- Small addition (feature/enhancement): append a new dated section at the end of the master file. Bump `last-section-added`.
- Big rewrite: first snapshot current file (see Archiving), then rewrite, then bump `version`+`date`.
- TZ *content* is authored by Opus. Other models handle file mechanics (move, rename, index update, frontmatter bump).
- **Do not spread one tool across many documents.** A new enhancement of an existing tool = new dated section in the master TZ, NOT a new file.
- Новые требования пакета — якоря `AC-###` в той же новой секции master-ТЗ (`### Критерии приёмки (AC)`), не во второй документ.

## Archiving (mirror to `~/WorkVault_backup/`)
- Backup path mirrors WorkVault relative path.
- Snapshot before big edits: `tgz` → `WorkVault_backup/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz`
- Old superseded versions: `WorkVault_backup/.../<Tool>_TZ_v<old>_YYYYMMDD.md` (version-in-name allowed for archived copies only).
- Retention: last 5 tgz per tool, last 1 `.bak` per file, `.md` versions indefinitely.
- Log every move to `~/WorkVault_backup/_moved-YYYY-MM-DD.log` (one file per day, append).
- **A tool's master TZ stays in WorkVault as long as the tool is in use.** Finishing a specific enhancement does NOT move the TZ to backup — it stays `active` and gets a new dated section. Move to `WorkVault_backup/Hermes-Backlog/TZ/_archived/<Tool>/` ONLY when the tool itself is decommissioned/deleted, and only on Sasha's explicit instruction. No auto-timer, ever.
- **No "for history" copies.** Archive is ONLY for TZs of tools that were decommissioned/withdrawn from use. Do NOT keep a copy of a superseded draft "just in case" — the full pre-migration state is preserved in the general tgz backup (`~/.hermes/_Archives/hermes-backup-*.tgz`); the working tree stores exactly one live copy at the canonical path. Duplicate copies with no clear archival purpose must be removed.

## Inventory
- After any structural change to a TZ: update `WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md`
- After any restructure of vault itself: update `WorkVault/MAIN_WORKVAULT_INVENTORY.md`

## Do not touch
- `~/hermes-config-repo`, `~/hermes-config`, `~/hermes-workspace` (git repos, out of scope)
- `WorkVault/Projects`, `People`, `Meetings`, `Contacts` (working data)
- Gateway process — no restart from this workflow. Ever.

## Agreement ≠ stop of the train
Approval of a TZ (all open questions closed, text finalized) is NOT a stop of implementation. Согласование ТЗ ≠ стоп реализации. After `TZ:finalize` the DEV train continues by itself (AC list is shown in origin; `GATE:take-into-work` is a graph node, not a Sasha hold). The phrase «берём в работу» on AC-gates is an idempotent no-op if the gate is already auto-complete. Crisis HITL remains: `GATE:go`, `GATE:block-accept`, IDEA until «разбери».

## For remote LLMs (e.g. Cursor on laptop)
- `~/WorkVault_backup/` is VM-only, NOT synced. From laptop you see only `WorkVault/`.
- If archiving is needed, either do it on the VM (via Hermes) or note the intent in `MAIN_TZ_INVENTORY.md` for later.
