# QA Verification Checklist for MoveFrom* Projects

**Purpose:** Systematic audit to verify code matches current ТЗ when ТЗ is updated. Catches spec-vs-code drift early.

**When to run:** After ТЗ updates (especially mid-version refinements like 2026-05-25 addenda), before deployment cycles, or as a sanity check before major integration work.

**Scope:** All MoveFrom* projects (Exchange, FF, Confluence, Jira, etc.)

---

## Quick Checklist (15 min per project)

### Phase 1: Locate & Read Current ТЗ
- [ ] Find latest ТЗ file in `hermes-workspace/docs/tz/`
- [ ] Check date in YAML frontmatter or header comment — is it latest?
- [ ] Scan for "Обновлено [DATE]" sections that override earlier sections
- [ ] Look for **§ (section markers)** referenced in code comments

### Phase 2: Structural Code Review
For each critical module (client, config, main):
- [ ] Import statements: are optional imports (mock modes) present?
- [ ] Error handling: does code catch both business exceptions (auth, timeout) and infrastructure exceptions?
- [ ] Exit codes: do they match ТЗ-defined codes (0=success, 1=partial, 2=config, 3=service unavailable, 4=fatal)?
- [ ] Config vars: match ТЗ variable names exactly — case sensitivity varies by BaseSettings impl
- [ ] Timeout values: are they documented in ТЗ? If ТЗ says "15s" but code says "30s", that's a drift

### Phase 3: Version & API Specification Traps
These catch the hardest bugs (spec says don't do X, code does X):

#### exchangelib-specific:
- [ ] **Explicit version Build** — ТЗ says "версию НЕ указываем явно"? Check if `Version(build=Build(...))` appears. If yes, ТЗ-compliant code should use auto-discovery.
- [ ] **resolve_names return_full_contact_data** — Setting True can trigger 401 when user lacks SOAP permission. Check if ТЗ restricts this flag. Current status (as of 2026-05-25): works but risky, monitor for domain-specific failures.
- [ ] **BASIC vs NTLM auth** — ТЗ specifies which? Code must match.
- [ ] **access_type=DELEGATE** — Required by ТЗ, verify present in Account() constructor.

#### Fireflies/Confluence-specific:
- [ ] **return_full_contact_data** or equivalent — do API calls fetch heavy fields unnecessarily? Check if list queries bloat the response.
- [ ] **Keycloak SSO vs PAT** — If ТЗ mentions Keycloak migration, is code still using old PAT? Flag as TODO if ТЗ v1.1+ planned.

### Phase 4: Custom Field Merging (MoveFromExchange-specific)
- [ ] **On update:** Verify aliases, messenger_ids, notes, custom_updated_at are **read from local before overwriting Exchange fields**, then **restored after merge**.
  - Code pattern: `custom_x = local_contact.get("x"); ... update(exchange_fields); ... ["x"] = custom_x`
- [ ] **On create new contact:** Are custom fields initialized to empty/null, NOT left unset?
  - Look for: `"aliases": []`, `"messenger_ids": {}`, `"notes": ""`, `"custom_updated_at": null`
- [ ] **is_internal field:** ТЗ specifies domain-based logic (@tutu.ru/@tutu.tech = true). Check both update and create paths set this.

### Phase 5: Test Coverage
- [ ] Run full test suite for each project: `pytest tests/ -v`
- [ ] Verify counts match ТЗ or README (e.g., "34 tests", "48 tests")
- [ ] Check for import-time errors: `python -c "from module import *"` on each main module
- [ ] If tests pass but ТЗ counts differ, ТЗ may be stale — update ТЗ, not code

### Phase 6: Logging & Exit Codes
- [ ] **_log.md / _sync_log.md exists and is append-only**
- [ ] **TG alerts:** Cron mode = silent, manual mode = notify. Check for conditional sends.
- [ ] **Exit codes:** Match ТЗ table exactly. Code should return (0, 1, 2, 3, 4) not custom values.
- [ ] **Dry-run mode:** If ТЗ requires it, code must print what would happen without writing files.

### Phase 7: Integration Contract Verification
(From ТЗ §13 or equivalent)
- [ ] **contacts.enc accessibility:** If downstream tools (MarkObjectsFromSummary) depend on it, is encryption/decryption exported cleanly?
- [ ] **Email as universal key:** Is email field used consistently across all JSON schemas?
- [ ] **No autonomous publication:** Code doesn't publish to Jira/Slack/Confluence on its own — only on user command or TG trigger.

---

## Common Pitfalls Found in Practice

### 1. Explicit Version Specifications (exchangelib)
**Symptom:** Code has `Version(build=Build(15, 2, 1544, 14))`  
**Root cause:** Developer added this to work around 401 errors without VPN, but ТЗ says auto-detect.  
**Fix:** Remove version override, let exchangelib auto-discover via autodiscovery or fallback.  
**When to override:** Only if ТЗ explicitly says "Exchange 2019 requires Build X" AND downstream is breaking.

### 2. Custom Fields Lost on Update
**Symptom:** After sync, aliases/notes disappear.  
**Root cause:** Code reads Exchange response, overwrites entire contact dict, never re-reads custom fields from local.  
**Fix:** Pattern — read local custom fields BEFORE merge, restore AFTER.  
**Verification:** Test case `test_merge_update_preserves_custom_fields` must exist and pass.

### 3. is_internal Not Set on New Contacts
**Symptom:** New external contacts created without is_internal field.  
**Root cause:** Dev copied update logic but forgot to add domain check on create path.  
**Fix:** Add `"is_internal": email.endswith(("@tutu.ru", "@tutu.tech"))` in both update AND create branches.

### 4. TG Alerts in Cron Mode
**Symptom:** Users get Telegram spam from cron job.  
**Root cause:** Code sends TG regardless of mode, or mode check is missing.  
**Fix:** `if mode == "manual" and notifier: send_message(...)` — ALWAYS check mode first.

### 5. return_full_contact_data=True Triggering 401
**Symptom:** GAL fetch fails with 401 in some domains.  
**Root cause:** Full contact data requires SOAP permission user may not have.  
**Fix:** Remove flag OR catch 401 and retry without flag. ТЗ should specify which is acceptable.  
**Current status (2026-05-25):** Works but risky — monitor for domain-specific failures.

### 6. Missing .env Variable Validation
**Symptom:** Code crashes at runtime when var is missing.  
**Root cause:** Config parser doesn't check required vars early.  
**Fix:** Preflight step (Шаг 0) must validate all required vars and exit 2 with helpful message.  
**Pattern:** `_req = lambda name: os.environ.get(name) or error_exit(f"Missing: {name}")`

---

## ТЗ Version Reconciliation

When ТЗ is updated mid-project (e.g., 2026-05-25 addendum to 2026-05-23 ТЗ):

1. **Grep for section markers** in ТЗ: `§`, `##`, `###` — find the amendment section
2. **Search code for references to old sections** — grep commit messages, comments for "§2", "§3" etc.
3. **Cross-reference:** If old ТЗ said "do X", new ТЗ says "don't do X", code must flip
4. **Timestamp in code comments:** When you fix code to match ТЗ, **always add date**:
   ```python
   # По ТЗ v1.0 (2026-05-25): версию EWS НЕ указываем явно
   # (Было: Version(build=Build(...)), удалено согласно §14)
   ```

---

## Template: Session Audit Report

When verifying a project suite, produce a table like this:

| Проект | Версия | Статус | Тесты | Расхождения с ТЗ | Исправления |
|---|---|---|---|---|---|
| MoveFromExchange | v1.0 | ✅ ГОТОВ | 34/34 ✅ | 1 (версия Build) | ✅ Удалено |
| MoveFromFF | v2.0 | ✅ ГОТОВ | 48/48 ✅ | 0 | — |
| MoveFromConfluence | v1.0 | ✅ ГОТОВ | 37/37 ✅ | 0 | — |

---

## References

- **ТЗ locations:** `hermes-workspace/docs/tz/MoveFrom*_TZ_*.md`
- **Skill governing MoveFrom* architecture:** `about_usr_skills`
- **Typical run:** 15–30 min per project (depends on code size)
- **When to expand:** If new pitfall found, update this file under "Common Pitfalls"
