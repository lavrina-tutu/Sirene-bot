# Multi-assignee resolution fix (15.07.2026)

## Symptom

Meeting "ML-платформа. Регулярный статус с Заказчиком" (2026-07-15) published with two task
lines left as unlinked text instead of `ac:link` mentions:

```
Ткаченко Александр Владимирович и Расов Арсений: Сформировать таймлайн развития ML-платформы / понедельник
Аралов Александр и Расов Арсений: Разместить roadmap развития ML-платформы в план / без указания срока
```

Both "Ткаченко Александр Владимирович", "Аралов Александр" and "Расов Арсений" resolve fine
individually via `contacts_resolver.resolve_participants()` — the problem was structural, not a
contacts-lookup gap.

## Root cause

`pipeline.py::run_pilot()` resolved each task's assignee like this:

```python
assignee_resolved = resolve_participants(
    [task.assignee_raw], store=store, confluence=confluence, rooms=rooms
)[0]
```

`task.assignee_raw` was the WHOLE string `"Ткаченко Александр Владимирович и Расов Арсений"` —
passed as a single candidate. No contact in `contacts.enc` has that as its `fio`, so
`store.find_contacts(...)` returns zero candidates and the whole task falls back to raw text.

## Fix

1. `summary_parser.py`: added `split_assignees(raw) -> list[str]`, splitting on `"\s*,\s*(?:и\s+)?|\s+и\s+"`
   (handles "A и B", "A, B", "A, B и C"). Single names without a separator pass through unchanged.
2. `pipeline.py`: `task.assignee_raw` is split BEFORE resolution; `resolve_participants()` is
   called once with the full list of split names, producing a `list[ResolvedParticipant]`.
   Room-redirect logic was extended to a 3-way branch: all-rooms (existing redirect-to-Sasha
   behaviour), no-rooms (normal), and mixed (replace only the room entries with the default
   assignee, keep real people as-is) — all in the SAME task line.
3. `storage_xml.py::_task_body()`: signature widened to accept
   `resolved: ResolvedParticipant | list[ResolvedParticipant]`. A single object is wrapped into a
   1-element list internally so all existing call sites/tests keep working unchanged. Multiple
   resolved participants render as `ac:link` mentions (or raw-text fallback per-person) joined by
   `", "` before the task text.

## Verification performed

- 4 new unit tests in `tests/test_multi_assignee.py`:
  `test_split_assignees_with_soyuz_i`, `test_split_assignees_single_name_unaffected`,
  `test_two_assignees_both_resolve_via_resolve_participants`,
  `test_render_row_multi_assignee_task_both_mentioned`.
- Full offline suite green (135 passed at the time of the fix, later 139 after the page_layout
  sanity check was added in the same session).
- Live verification: `dry_run=True` on the real summary file showed both mentions correctly
  rendered; then `confirm_republish=True, dry_run=False` republished the real page
  (pageId 490169504, version 136→137); GET-ed the page back afterward and confirmed both task
  bodies (`ac:task-id` 332/333) now contain two `ac:link` elements each instead of raw text.

## Generalization

Any place in this codebase (or a similar future tool) that takes a free-text "who is responsible"
field from a meeting-summary parser and feeds it into a name→ID resolver should split on natural
list conjunctions FIRST. Silent failure mode here is particularly nasty: resolution doesn't
error, it just quietly falls back to "leave as text" — which looks like a normal unresolved-name
case, not a code path bug. If several people's names show up correctly in `participants` (which
IS resolved one name at a time from a `list[str]`) but not in an assignee/owner field parsed as a
single flat string, suspect this exact bug shape.
