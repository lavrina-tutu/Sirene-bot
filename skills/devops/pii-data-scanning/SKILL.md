---
name: pii-data-scanning
description: "Use for PIIScan, PII detection and masking."
version: 1.3.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pii, privacy, 152, workvault, masking, compliance]
    related_skills: [workvault-entities, hermes-memory-hygiene]
---

# PIIScan: local detection and masking contract

Use for Hermes/WorkVault PIIScan, local findings and masking. This is Sasha's agreed operational classification, not a universal legal definition of personal data. Do not read live `~/.hermes/state.db`, even read-only. It is out of scope. Do not modify the Hermes core or ErrorBus helpers as part of a scan task. Do not run a production scan or change data without authorization.

## Finding definition and scope

A local PII card requires **both** an identifier and an attribute in one context:

- Identifier: full Russian FIO or at least a two-word capitalized first and last name. A bare internal login is insufficient: «если рядом с логином нет полного ФИО или хотя бы ФИ — это не ПДн».
- Attribute: email, phone, messenger handle or position. Field types are `fio+email`, `fio+phone`, `fio+handle`, `fio+position`. A single email, name without an attribute, or bare login is not a card.

For ordinary JSON/JSONL, one string field is one context; do not cross fields of an object. For multiline or long fields over 500 characters, inspect line by line to avoid a Cartesian product of unrelated names and attributes. For text and logs use the line and adjacent line where needed for a split `ФИО:\nEmail:` context.

Outside exclusions, archive sessions `~/.hermes/sessions/*.jsonl`, `~/WorkVault`, `~/WorkVault_backup`, `~/.hermes/cron/output/`, `~/.hermes/logs/` and `~/.hermes/error_bus/` are critical scan zones. The live `~/.hermes/state.db` is never scanned. Do not infer that an ErrorBus severity or count equals a number of real leaks: triage the structured finding first.

Never scan either PII or credentials in these legitimate storage whitelist zones:

- `~/WorkVault/Contacts/`, `~/WorkVault/Entities/*`, `~/WorkVault/Inbox/`, `~/WorkVault/UserManuals/`;
- all of `~/WorkVault/Confluence/**`, all of `~/WorkVault/Projects/**`, and `~/WorkVault/Meetings/**`.

Skip `~/USERTOOLS/**` at traversal, except `~/USERTOOLS/TaskRefresh/session/`, which remains in scope as a TTL cache. This is a traversal skip, not a baseline whitelist. `Hermes-Backlog/TZ/**` and `~/.hermes/error_bus/tests/` remain in scope. Do not silently clean values or paths in the excluded Meetings zone: email in a filename is a separate path scope that requires explicit authorization.

Credentials are a separate category: an actual exposed key, PEM or Bearer secret outside the whitelist is critical independently of a PII card. Agreed URL embed query parameters such as `token`, `boardAccessToken` and `access_token` are excluded by the local rule. Do not classify declarations, variable passing, function calls or obvious placeholders (`AAFake*`, `Example`, `your_token_here`) as real credentials; retain detection of actual literals and secrets. Detection rules, post-filters and examples: `references/detection-and-masking.md`. Zone decisions and history: `references/pii-rule-20260909.md`.

## First run, reporting and atomicity

On the first run, when `baseline.json` is absent, record all findings as known baseline, without critical incidents, and produce one summary report. From the second run report only new findings; classify found baseline items as persisting and missing keys as vanished. Resolve vanished open findings according to the supported ErrorBus interface. Never delete their historical evidence from `audit_history.jsonl`.

Produce **one summary event per run** for new findings, including count, breakdown by file/category and masked sample in detail. When there are zero new findings, write no ErrorBus event; a stdout self-check summary is allowed. Per-finding events and per-run caps were superseded.

Keep the crash-safe order: collect `new/persisting/vanished` in memory → report and resolve → checkpoint baseline and audit in batches of `BATCH=20`. Save baseline through a temporary file in the same directory and `os.replace`. Never mark all findings saved before a successful report: interruption would turn unreported findings into persisting findings. Preserve append-only audit history. Details: `references/baseline-and-reporting.md`.

If a source was removed but its event remains open, inspect whether the key exists in the baseline: automatic vanished resolution only covers baseline keys. For an out-of-baseline batch, dry-run the intended selection first, then use the existing batch API in one process (`resolve_error(conn, err_id, note)`), not raw SQL or one subprocess per event. Do not alter ErrorBus helpers. Incident and recovery history: `references/pii-incident-20260921.md`.

## Masking and triage

For baseline, audit and reports mask both local and domain parts of email, for example `git@github.com → gi**@gi***`; mask short values of length ≤3 completely as `****`. Use PIIScan's `mask_identifier`, `mask_attribute` and `mask_credential` for sterile storage; AnywhereContacts `mask_pii` / `mask_contact` are display masks and can leave a domain or short value exposed. Never persist raw PII in a report or audit entry.

Group findings by structured data in `detail`, not by parsing `message`: paths may contain spaces. Locate the exact source with the scanner's `Finding.raw_value` locally because normalized adjacent-line context may not match a masked grep. Inspect raw data privately; do not copy it into reports. Before depersonalizing, verify that the raw value is an actual person rather than an administrative phrase such as «Решение Саши». Independently verify an authorized fix with the same dry scan, masking checks, and baseline/audit checks.

A large report from one long JSON field may be a cross product: compare unique names × attributes with the batch size, and apply the line-based context rule. Do not treat historical ErrorBus severity inflation or open event count as a legal assessment or a count of confirmed leaks.

## Components, retention and checks

PIIScan components are `~/.hermes/pii_scan/{pii_scan.py,patterns.py,redact.py}`, `baseline.json`, `audit_history.jsonl` and `~/.hermes/scripts/pii_scan.sh` (fail-soft wrapper). `report_error.sh` and `error_bus_cli.py` are under `~/.hermes/scripts/`; the ErrorBus database and `_db.py` are under `~/.hermes/error_bus/`. Use their supported interfaces; do not edit core or helpers for a scan.

Check `~/.hermes/logs/process-results/proc_*.json` as a separate potential channel: background command stdout may persist there for 7 days / at most 64 files, with lazy pruning. This differs from the 5-day TTL for completed TaskRefresh session history and `WorkVault_backup/llm-anomaly-audits/LLM-anomalies_*.json`; `current.json` is retained. Keep names, phone numbers and emails out of designated logs at write time, using the established redaction helper where appropriate. Integration points and retention history: `references/retention-and-log-hygiene.md`.

For an authorized implementation, follow `dev-workflow` and independently test the scanner, sterile masks and baseline/audit output; do not rely solely on an executor's self-report. Do not run a production scan, cron or delivery for a documentation check. The former `references/pii-errorbus-triage.md` is superseded; its conflicting historical instructions are not current policy.

## Review checklist

When asked to assess findings, establish the authorized source and scan scope first. Apply the whitelist before classification, then distinguish the local FIO-plus-attribute rule from the separate credential rule. Inspect the structured finding before describing it as an incident; the source path and category are safer grouping keys than a human-readable message containing a path with spaces.

Treat suspicious masked samples as leads rather than proof. Inspect `raw_value` only locally when needed to distinguish a real person from a false positive or placeholder, and keep raw values out of the delivered report. A path containing an email address is not repaired by masking a file's contents; apply the separately authorized path scope and respect the Meetings exclusion.

For a proposed fix, verify the exact interpretation of baseline state and event history. The first baseline has no critical incidents; a later new finding can generate one summary event, while zero new findings generate none. A vanished key can be resolved without deleting the original audit record. If the previous process failed between reporting and checkpoint, inspect the available baseline evidence before choosing a supported resolution path.

Use local tests and controlled fixtures for validation. Check that stored samples mask both parts of emails and short values, that long JSON fields do not pair every name with every attribute, and that actual credentials still match while variable declarations and placeholders do not. Report which checks actually ran and avoid presenting ErrorBus counts, a single exit code or a historical test result as present proof of a clean system.
