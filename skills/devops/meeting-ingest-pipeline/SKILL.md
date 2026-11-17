---
name: meeting-ingest-pipeline
description: "перенос встреч в Необработанные: проверка контура"
version: 1.1.0
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [meetings, pipeline, ktalk, mofs, pfs, ofc, confluence, playground]
    related_skills: [move-from-keytalk, protocolfromsummary, mofs-operations, hermes-feature]
---

# Meeting Ingest Pipeline

## Purpose and scope

Use for «перенеси встречи в Необработанные», rewriting meetings for a period, or checking the entire ingest chain, including incorrect names, task slugs, row attributes or missing notifications. Diagnose individual tools with their own skills while checking end-to-end evidence here. The chain is MoveFromKeyTalk (MFKT) → summarization → MOFS → PFS → OFC. PFC means PFS, not a separate entity.

## Mandatory routing and recovery

1. **Pass 1 always ends at «Необработанные задачи» playground `523032632`.** Never publish directly to project minutes, including multisync and 1:1. Promote to project minutes is a separate pass 2, only after the row is marked «обработано» (`td3`). A minutes row without this sequence is a routing defect.
2. Use the established tools and entrypoints. Do not repair the mechanism with manual HTML/JSON, direct Confluence curl instead of PFS, or an ad hoc bypass. For a bug trigger create the standard DevWorkflow BUGFIX case with `pipeline init --case BUGFIX` before invoking a role; repair through that workflow.
3. Rewriting requires the full authorized replay from Obsidian transcript through summary, resolve, playground and notification. Use PFS row deletion/replacement by `row_anchor` and registry mechanisms. Republish alone is **not** replacement: `ingest_after_publish` can return `skipped_present` for an existing anchor without PUT, even with `run --confirm-republish`. Verify actual replacement with a subsequent GET. Full details: `references/replay-and-republish.md`.
4. Do not invent utterance timestamps and represent them as meeting source data. Clearly label any explicitly requested synthetic example and keep it separate from real ingest. Manual file pair and real MOFS/PFS entrypoints: `references/manual-meeting-ingest.md`.

## Diagnostic route

- Compare period source pairs `*-transcript.md` / `*-summary.md` in `WorkVault/Meetings/NewMeetings/`, the configured MOFS registry and the PFS registry `~/WorkVault/ProtocolFromSummary/_registry.json`. Resolve the MOFS registry path from the installed tool/config; historical paths differ.
- MOFS processed (`objects_version`) **does not mean** PFS published. Confirm PFS registry and live page. When PFS record is absent, check `skipped_empty`: empty Tasks/Decisions/Blockers/Risks require normal source resummarization, not forced publication of an empty row.
- Compare `published_at` with MOFS `processed_at`. A later MOFS pass does not repair an already published row; a complete authorized replay with replacement is needed.
- GET playground `523032632`, locate the row by `row_anchor`, and inspect all tasks, participant/assignee `<ri:user>` links, task prefixes and the target minutes column. Logs, return codes, a code fix or a rebuilt XML alone do not prove the live row changed.
- Classify evidence as source present / MOFS ok or bad / PFS published or missing before diagnosing a component. Do not edit registries by hand. Details and GET evidence: `references/ingest-diagnostics.md`; race and old-row incidents: `references/ingest-incident-history.md`.

## Slugs, contacts and notifications

Determine each task slug from its own context and eligible binding, not the meeting title. For 1:1 retain LLM → union → home fallback: `union==0` uses route `pfs.tag` or meeting entity `{display_name}. ` with a space; project `AI-аналитик.` retains its no-space form. `union>=2` does not automatically use home. Check **every** task in the row, not a sample; missing required prefix after replay is a mechanism defect.

For `contacts: []`, check contact-store availability, dependency in the actual cron venv and `CONTACTS_ENCRYPTION_KEY` availability before concluding people are unknown; do not expose the key. Source detail: `references/task-slugs-and-contacts.md`.

Pass 1 sends a notification pointing to the playground; successful promote is silent. A replay may reset `notified` and send the notification again. OFC copies a confirmed Confluence protocol to `WorkVault/Entities/<slug>/protocol.md`; assess it at the appropriate stage, and do not call the absence of a not-yet-performed promote an OFC failure.

## Acceptance

- Verify source file pairs and MOFS frontmatter (`projects`, `contacts`, `project_bind`), accounting for eligible unbound cases.
- Verify PFS published record, `playground_ingested_at`, notification, and live playground row by GET; distinguish a legitimate `skipped_empty`.
- Verify all required names, task prefixes and target column; pass 1 must be on `523032632` only. Confirm `td3` before any promote.
- For replay verify the row actually changed by anchor and the full chain was rerun; inspect the actual artifact, not only logs.
- Check OFC and `confluence_version` after the relevant publication/promote stage. Report each stage and unresolved discrepancy with evidence.
