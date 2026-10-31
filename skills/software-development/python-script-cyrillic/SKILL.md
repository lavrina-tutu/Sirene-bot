---
name: python-script-cyrillic
description: "Use when writing .py with Cyrillic/non-ASCII string literals"
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [python, cyrillic, codegen, writing, unicode]
    related_skills: [spike, python-debugpy]
---

# Python script generation with Cyrillic (non-ASCII)

## When to use
Generating or hand-writing a `.py` file whose string literals contain Cyrillic
(`"Малый"`, `"Трисигма"`, Russian text in prints/messages) or other non-ASCII
characters. Applies whether the file is created via `write_file`, a shell
heredoc, or `cat > file << EOF`.

## Core pitfall (observed 2026-09-03, repeated ~10x in one session)
Tool-generated Python code containing Cyrillic **string literals** was silently
corrupted when written to disk:
- CJK / fullwidth characters injected where Cyrillic should be (`print(...)):` → `print(...）:`, `datetime(... )` → `datetime(...¥9...)`, `（`/`）` fullwidth parens, `：` fullwidth colon);
- Brackets/parens came back mismatched (`]` for `)`, missing closing paren) — a lone typo shifted to an unrelated brace;
- `py_compile` flagged it, but the corruption is **non-obvious** in the lint message (often reported at a different line than the true fault).

Both `write_file` and heredoc paths were affected. This is not a "tool is
broken" claim — it is a **generation fragility**; the fix below makes output
immune regardless of the write path.

## Prevention (do FIRST — saves the whole repair loop)
1. **Prefer ASCII-only code.** When the script needs Cyrillic text as *data*
   (prints, exception messages, subject lines), write it as unicode escapes:
   ```python
   # ASCII source → robust
   name = "\u041c\u0430\u043b\u044b\u0439"   # "Малый"
   msg = "\u0413\u043b\u0430\u0434\u043a\u0438\u0445"  # Гладких
   ```
   i.e. generate the escape codes yourself and put ONLY ASCII in the file.
   Python evaluates `"\uXXXX"` in string literals at runtime, so the file
   stays pure ASCII and is immune to the corruption.
2. Never put Cyrillic inside `.py` outside a `\u`-escaped or
   `bytes(...).decode()` literal. Comment text in `.py` — also keep ASCII or
   use it sparingly.
3. **Verify before running:** `python3 -m py_compile file.py` (or the venv's
   python) immediately after writing. Fix any error BEFORE executing.

## If corruption already happened (repair pattern)
1. Re-read the file on disk (`read_file`) — do NOT trust the tool's
   "diff: ok" or the last lint message; the on-disk bytes are what run.
2. Spot-fix the exact mis-characters with `patch(old_string, new_string)`
   using ASCII-safe context. Search for fullwidth `（ ） ： ｛｝【】` and CJK
   runes in the file.
3. Re-run `py_compile` and only then execute.
4. For heavily-corrupted files, prefer **rewriting ASCII-only** over N rounds
   of patching — patching Cyrillic-adjacent lines tends to add fresh errors.

## Cheap robustness for one-off scripts
- Keep the script in `/tmp/` and `py_compile` gate it before the real run.
- Log what you sent (`print(...)`) and what the recipient saw — if a Cyrillic
  message is part of the contract (e.g. Loop/Telegram text), confirm the
  rendered string, not just the exit code.

## Related
- Session instance: MeetingScheduler Loop-уведомления и free/busy probes.
- For the MeetingScheduler tool itself (Loop domain rule, reschedule
  `save()` kwarg) see the user-owned `exchange-meeting` skill (правится
  через Cursor/hermes-feature, не `skill_manage`).