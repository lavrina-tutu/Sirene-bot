---
name: protocolfromsummary
description: "Use when working with the ProtocolFromSummary (PFS) tool — publishes Fireflies meeting-summary .md files into Confluence protocol tables (~/USERTOOLS/ProtocolFromSummary). Триггеры: PFS, протокол встречи, опубликовать протокол, задача не резолвится/не мешенится, ROUTES, page_layout, republish, страница протокола поменялась."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, ProtocolFromSummary, PFS, Confluence, Fireflies, WorkVault, protocol]
    related_skills: [tutu-confluence-jira, obsidian, hermes-feature]
---

# ProtocolFromSummary (PFS)

Publishes parsed Fireflies meeting `.md` summaries from `WorkVault/Meetings/NewMeetings/` into
per-project protocol tables on Confluence (dom.tutu.ru). Code lives at
`~/USERTOOLS/ProtocolFromSummary/protocolfromsummary/`, venv at
`~/USERTOOLS/ProtocolFromSummary/.venv`.

## Architecture (read before touching anything)

- **`config.py` → `ROUTES` dict** — pageId → {tag, kind, name_match, page_layout?}. This is the
  single source of truth for "which Confluence page does meeting X's protocol go to, with what
  tag prefix, and what table shape". `kind` ∈ {project, one_on_one, multisync, sync_aid, unknown}.
- **`route.py`** — matches `meeting_name`/participants against `ROUTES[*].name_match` (+ a few
  hardcoded exceptions like Саша+Аралов → aralov_1on1, or department-fallback routing).
- **`summary_parser.py`** — parses the `.md` summary into `MeetingSummary`/`MeetingTask`. UTC→MSK
  conversion happens here (filenames from Fireflies are UTC). `split_assignees()` splits a raw
  assignee string on "и"/commas into individual names (see Pitfall 1).
- **`contacts_resolver.py`** — ФИО string → Confluence userkey via `contacts.enc` + Confluence API
  fallback (`find_user_by_fullname`). Handles "Фамилия И.О." shorthand, ambiguous-surname
  disambiguation, DEFAULT_ASSIGNEE_LOGIN fallback for true ties.
- **`storage_xml.py` → `render_row()`** — builds the `<tr>` storage-XML fragment for one meeting
  row. `layout` param selects `2col` (default) / `5col_aid` / `3col_content_last`, must match the
  REAL column count of the target Confluence table (see Pitfall 2).
- **`page_merger.py`** — GET page → parse existing `<table>` → insert/replace row by
  `row_anchor` (stable anchor-macro survives PUT/GET, invisible in render) or `task_id` fallback →
  chronological insertion. `count_header_columns()` is a sanity-check helper (see Pitfall 2).
- **`pipeline.py` → `run_pilot()`** — orchestrates the whole flow: parse → route → resolve
  participants/assignees → render row → GET page → merge → (dry_run ? stop : PUT).

## Standard operating pattern

1. **Always `dry_run=True` first**, inspect `result.row_xml`, THEN `dry_run=False`. Never go
   straight to a live write when debugging or after a code change.
2. For a meeting already published, republish requires `confirm_republish=True` (otherwise
   `skipped_duplicate`). Republish reuses the existing `row_anchor`/task-ids — it replaces the
   row in place, it does not duplicate it.
3. After any live write, **GET the page back and grep the relevant fragment** to confirm the real
   HTML — don't trust `result.action == "published"` alone as proof of correctness.
4. Run the offline suite before and after any code change:
   `cd ~/USERTOOLS/ProtocolFromSummary && source .venv/bin/activate && python3 -m pytest -q -m "not live_confluence"`.
   `-m live_confluence` tests hit real Confluence pages — don't run those casually.

## Pitfalls

1. **Multiple assignees in one task line ("Иванов И. и Петров П.: ...") silently fail to
   resolve.** `pipeline.py` used to pass the WHOLE `assignee_raw` string to
   `resolve_participants()` as a single candidate — no such contact exists, so the entire task
   stayed as unlinked text even though each name resolves fine individually. Fix: split first via
   `summary_parser.split_assignees()` (handles "и" and comma separators), resolve each name
   separately, then render as multiple `ac:link` mentions joined by `, ` in one task line
   (`storage_xml._task_body()` accepts either a single `ResolvedParticipant` or a `list[...]`).
   Room-redirect logic (meeting-room "assignee" → DEFAULT_ASSIGNEE_LOGIN) now also handles the
   mixed case (some assignees are rooms, some are people). See
   `references/multi-assignee-fix-2026-07-15.md` for the full before/after and test names.
2. **`page_layout` in `ROUTES` can silently drift from the REAL Confluence table structure** — the
   user sometimes manually edits a protocol page's table (adds/removes a column) without telling
   the tool. A stale `page_layout` will render the wrong number of `<td>` cells and corrupt the
   table. `pipeline.py` now calls `page_merger.count_header_columns()` on every run and logs a
   loud WARNING (not a hard-stop — publication still proceeds) if the live `<th>` count doesn't
   match what the configured layout expects (`2col`→2, `5col_aid`→5, `3col_content_last`→3). If
   you see this warning: GET the page, look at the real `<th>` row, and update (or remove) the
   `page_layout`/`content_column_index` override in `config.py` to match — don't just silence the
   warning. Concrete precedent: `ai_analitik` (pageId 477061038) was hardcoded to
   `3col_content_last` after a one-off BUG-1 fix; the user later reverted the page to the default
   2-column shape and the override became stale until this session caught and removed it.
3. **Contacts resolution is substring-based** (`store.find_contacts(query)` matches `query` as a
   substring of `fio`/login) — a bare "Ткаченко" without initials is ambiguous between namesakes;
   `contacts_resolver` disambiguates via `DEFAULT_ASSIGNEE_LOGIN` fallback only when it's among
   the ambiguous candidates, otherwise leaves it as unresolved text. "Фамилия И.О." shorthand
   (Fireflies' typical format) is handled by a dedicated regex path BEFORE the substring search,
   because "Ткаченко А.В." is not literally a substring of "Ткаченко Александр Владимирович".
4. **`row_anchor`** is an invisible `ac:structured-macro name="anchor"` embedded in the date cell
   — Confluence's storage sanitizer strips plain HTML comments/data-attributes on PUT, but the
   anchor macro survives. This is the only reliable way to find "this meeting's row" again on
   republish; task-id-based lookup is the fallback for rows published before this mechanism
   existed.

## Verification checklist

- [ ] Ran `dry_run=True` and inspected `row_xml` before any live write
- [ ] Multi-assignee task lines split via `split_assignees()`, not passed whole to
      `resolve_participants()`
- [ ] No `page_layout mismatch` WARNING in logs — if there is one, `ROUTES` config updated to
      match the live page, not silenced
- [ ] After a live write, GET the page back and grepped the actual fragment (mentions, dates,
      task-ids) — didn't trust `action == "published"`/`"republished"` alone
- [ ] Full offline suite green (`pytest -q -m "not live_confluence"`) before AND after any code
      change to `pipeline.py`/`storage_xml.py`/`contacts_resolver.py`/`summary_parser.py`
