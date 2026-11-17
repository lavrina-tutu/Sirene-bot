---
name: mofs-operations
description: "Operate MOFS, entity matching and MofsIndex."
version: 1.4.0
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [mofs, entities, obsidian, workvault, tagging]
    related_skills: [tz-workflow, about_usr_skills]
---

# MOFS operations

Use for MarkObjectsFromSummary (MOFS), which tags `NewMeetings/*-summary.md` with Obsidian links in projects, tools, rooms and contacts, and for MofsIndex operations. Code and cron failures go through `BUG:diagnose` → `GATE:diagnose-review` → `HF:impl`/`HF:test`; do not repair `pipeline.py` or service scripts directly. An operational rematch or entity-registry action is a one-step response, not a code fix. Do not assign task slugs in place of PFS routing.

## Paths and boundaries

- Tool: `~/USERTOOLS/MarkObjectsFromSummary/`; entities: `~/WorkVault/Registries/entities.json`; index: `~/USERTOOLS/MofsIndex/state/index.sqlite`; unmatched queue: `~/WorkVault/Registries/mofs_unmatched.md`.
- Historical MOFS documentation identifies `~/USERTOOLS/AnywhereContacts/_mark_objects_registry.json`; the current source defaults `registry_path` to the MarkObjectsFromSummary `tool_dir`. A read-only Settings check in the MOFS virtualenv with TOOL_DIR and LOGS_PATH unset resolved to `~/USERTOOLS/MarkObjectsFromSummary/_mark_objects_registry.json`; a service environment may differ. Resolve the effective settings and overrides for the running process before reading a registry; do not assume the historical path or alter configuration to reconcile it.
- Preserve `mofs_run_cron` (job `aeeccba37e4a`), `mofs_index_rebuild` (job `7e013cd5c6f9`) and the docs-index hook. Create no cron without Sasha's explicit «ставь кроны». Do not modify service scripts or config as part of operational diagnosis.
- Existing schedule documented 22.07.2026: MOFS weekdays `16 8-19 * * 1-5`; full index rebuild daily at 23:00. Verify the actual job before relying on schedule; historical weekly guidance is superseded only as a schedule claim, not authority to change jobs.

## Runs, recovery and entities

1. Run a scoped dry-run, review each problem, correct aliases via the CLI, repeat dry-run, then run for real only after reviewing the plan. `mofs run --meeting-id "YYYY-MM-DD HH-MM-SS Название" --dry-run` takes the meeting ID without a path or ` - summary.md`. Scope by dates or meeting ID; `rematch --all` requires `--yes` for a real run.
2. Check file content and mtime before and after a dry-run; if a file changed, stop and diagnose before any archive run. Diagnostic tasks use `enabled_toolsets: ["file"]` and must carry the command literally with `--dry-run`; never let diagnosis silently become a real run.
3. Before a bulk change, make a full WorkVault backup with `bash ~/.hermes/scripts/full_workvault_backup.sh`. `mofs bootstrap --snapshot` captures the MOFS registry, not all vault files. For bootstrap, manifest and undo details see [bulk run and recovery](references/bulk-run-and-recovery.md); its original excerpts are historical.
4. Change `entities.json` only via `entity-registry`. Search existing entities and aliases before creating a new one; add typo aliases without renaming source files. For `add`, repeat `--alias` for each alias and specify the parent or `--parent-null` for a parentless project; `--aliases` is unsupported in the documented CLI. For short Cyrillic abbreviations use the checked dot/startswith pattern (e.g. `цу.`), not broad substring matching.
5. After entity changes, verify rematch coverage and index freshness. In the inspected source the hash hook runs only in real `mode=cron`, initializes an absent hash without rematching, and on a subsequent change resets idempotency for affected meetings; actual processing still follows the run scope. Manual and dry-run do not trigger it. Inspect the effective process, scope and logs; use an explicitly scoped `mofs rematch --bucket projects --from X --to Y --dry-run` followed by reviewed real rematch when needed. Do not assume every historical meeting was reprocessed.
6. MOFS real runs/rematches/edits have incremental MofsIndex hooks. Check hook outcome and `mofs-index stats` / `mofs-index verify`; do not add a duplicate full rebuild to the wrapper. The existing full rebuild job remains separate. After creating or editing TZ documents, retain the `mofs-index index docs` hook used by tz-workflow. Details: [MofsIndex architecture](references/mofsindex-v01-architecture.md).

## Briefs and contacts

- For projects read the summary body, including roughly the first 200 characters for unclear titles; do not infer a project solely from the filename. Group cases and count the actual N before the first question. Ask one question per message, give numbered options and an explicit recommendation, ordered by frequency and recency. Sasha's exact instruction: «не удобно абц или abc — так неприемлемо».
- For tools count archive frequency before the brief. Do not add python, docker, mlflow, redis, postgres, dbt, jenkins, gitlab, superset or slack without Sasha's explicit decision. See [project brief](references/projects-brief-22072026.md) and [tools brief](references/tools-registry-brief.md) for scripts and prior decisions.
- For old archive summaries without `Участники`, use `mofs backfill-contacts`: deterministic S1/S2 first, then S3 only for remaining empty contacts after a sample review (~10 files). Start with `--min-confidence 0.90`, then 0.80 as appropriate; backfill is manual, not cron. For the new format use scoped `mofs rematch --bucket contacts`. Unknown candidates belong in `unmatched_candidates.json`, not contacts.enc.
- Never guess an ambiguous contact. If contacts are absent, inspect supported `## Участники:`, `**Участники:**` and plain `Участники:` headings, and ContactStore access. If repeated rematch does not change results, inspect matcher behavior rather than repeating indefinitely. If unmatched candidates contain many section labels, check candidate filtering. ContactStore should be opened once per pipeline, not once per meeting. See [contacts and backfill](references/contacts-and-backfill.md).

## PFS, diagnostics and LLM

- Before PFS routing check the entity's `pfs` block, fallback `vstrechi_nerazobrannoe`, and archive cutover guard. Before broad aliases, inspect old-archive matches: aliases can make old meetings eligible for publication. Check section parsing if protocols are empty; MOFS H2 headings may lack a colon.
- If summary has `## Bullet points` / `## Notes` instead of Custom Summary sections, do not accept an empty protocol. Restore the source using the established MoveFromFF refetch procedure, verify sections, then use the PFS republish procedure. The historical sequence is in [incident history](references/mofs-incident-history.md); assess destructive steps before execution.
- For `skipped=N, processed=0`, inspect the effective registry entry and compare its `objects_version` to current `OBJECTS_VERSION`; use a scoped rematch to reprocess. A seemingly incomplete frontmatter alone does not prove a failed run.
- After editable installation verify the public API import; a namespace package can hide `__init__.py`. Send code defects to the BUGFIX graph. See [incident history](references/mofs-incident-history.md).
- LLM fallback uses the documented Hermes config, `MOFS_LLM_*` overrides and last-resort `LLM_FALLBACK_*`; `--llm-model` applies only to backfill and only overrides the model. Missing credentials warn and skip (fail-soft); `ANTHROPIC_API_KEY` is not the documented MOFS source. The historical project fallback confidence is 0.90; check the effective configuration and current code before relying on it.

## References

- [Release history](references/mofs-release-history.md): dated status, completed plan and historical counts.
- [Bulk run and recovery](references/bulk-run-and-recovery.md): original bootstrap, CLI and undo examples.
- [Contacts and backfill](references/contacts-and-backfill.md): matcher, formats and NER history.
- [Incident history](references/mofs-incident-history.md): original cases and procedures, dated; not current instructions.
- [MofsIndex architecture](references/mofsindex-v01-architecture.md): API, docs-index and historical measurements.
- [Project brief](references/projects-brief-22072026.md), [tools brief](references/tools-registry-brief.md), [v0.7 status](references/mofs-v07-status.md), [cron analysis](references/mofs-cron-analysis-22072026.md): background and historical decisions.
