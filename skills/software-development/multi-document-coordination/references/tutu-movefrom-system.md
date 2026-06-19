# TUTU MoveFrom Tools System — Coordination Case Study

**Session Date:** 2026-05-25  
**Domain:** Technical specs for three interdependent ETL/sync tools  
**Trigger:** Field findings required coordinated updates across three v1.0 spec documents to keep contracts aligned.

---

## System Architecture

Three tools synchronize and transform data in the TUTU corporate environment:

```
┌─────────────────────┐
│  MoveFromExchange   │  SOURCE: syncs Global Address List (GAL)
│   (contacts.enc)    │  from Exchange EWS via Kerberos auth
└──────────┬──────────┘
           │ (creates/updates)
           ↓
┌─────────────────────────────────────────────────┐
│  contacts.enc (AES-256-GCM encrypted JSON)      │
│  ├─ Exchange fields: email, fio, department,    │
│  │                   position, is_internal, ...  │
│  └─ Custom fields: aliases, messenger_ids, ...  │
└──────┬──────────────────────┬───────────────────┘
       │ (reads)              │ (reads)
       ↓                      ↓
┌─────────────────┐    ┌──────────────────┐
│  MoveFromFF     │    │ MoveFromConfluence│
│ (Fireflies.ai)  │    │ (Confluence/Jira) │
│  _registry.json │    │  pages.json       │
│ participants: [ │    │  assignee: email  │
│    a@tutu.ru,  │    │                    │
│    b@ext.com   │    │                    │
│  ]              │    │                    │
└─────────┬───────┘    └──────┬─────────────┘
          │                    │
          └──────────┬─────────┘
                     ↓
         MarkObjectsFromSummary
         (downstream: uses contacts
          to enrich meeting metadata)
```

---

## Key Contracts & Version Numbers

### MoveFromExchange
- **Schema:** contacts.enc v1.0 (JSON with AES-256-GCM)
- **EWS auth:** Windows Kerberos (domain-only, no password needed)
- **access_type:** DELEGATE (mandatory)
- **Output:** `contacts.enc` with Exchange-managed fields + custom fields (preserved on update)

### MoveFromFF
- **Schema:** _registry.json v2.0 (minimal: meeting_id, title, participants[], files{}, status)
- **Participants:** list of email addresses (no name resolution; delegated to downstream)
- **Output:** Two markdown files per meeting (transcript, summary) in `{WORKVAULT_PATH}/Meetings/NewMeetings/`
- **Naming:** Deterministic: `YYYY-MM-DD HH-MM-SS <Title> - {kind}.md` (UTC)

### MoveFromConfluence
- **Pages list:** pages.json v1.0 (list of tracked Confluence page IDs)
- **Task schema:** YAML frontmatter in `.md` (page_id, task_id, assignee email, status, ...)
- **Auth:** PAT (personal access token) — **will migrate to Keycloak SSO in v1.1**
- **Contacts:** stores assignee as email, reads display names from contacts.enc (optional, graceful degradation)

---

## Critical Findings (2026-05-25)

### 1. Exchange Kerberos Auth ✅
- **Status:** Working in domain (office)
- **Verification:** Inbox (14 emails), Calendar (43 events), GAL resolve_names ✅
- **Access method:** Windows domain auth, no password needed in TUTU domain
- **Config:** `access_type=DELEGATE` mandatory; don't specify EWS version explicitly

### 2. Zulip as Primary Contact Source ✅
- **Size:** 1167 active contacts loaded into `contacts.enc`
- **API:** Works without VPN
- **Use:** Downstream tools (MarkObjectsFromSummary) can use Zulip + Exchange GAL for email→name resolution
- **Impact:** All three tools now mention Zulip API as optional enrichment source

### 3. Keycloak SSO Migration ⚠️
- **PAT Status:** No longer works through REST API v2 (as of 2026-05-25)
- **Migration:** Confluence/Jira now require Keycloak SSO
- **MoveFromConfluence impact:** v1.0 uses PAT (temporary); v1.1 must implement Keycloak OAuth2
- **Timeline:** MoveFromConfluence v1.0 guaranteed to work in TUTU domain (via browser or active session); v1.1 will have proper SSO integration

### 4. Bug Fix in merger.py ✅
- **Issue:** Custom fields (aliases, messenger_ids, notes) were lost when adding new contacts from Exchange
- **Status:** Fixed
- **Impact:** Custom fields now preserved when syncing new Exchange contacts

---

## Consistency Checks Performed

| Element | Exchange | MoveFromFF | Confluence | Status |
|---------|----------|-----------|-----------|--------|
| **Contacts source** | creates contacts.enc | reads contacts.enc | reads contacts.enc | ✅ Aligned |
| **Graceful degradation** | N/A | works without contacts.enc | works without contacts.enc | ✅ Consistent |
| **Zulip mention** | as enrichment source | as enrichment for downstream | as enrichment for downstream | ✅ Consistent |
| **Email as key** | email is dict key in contacts.enc | email stored in participants[] | email stored in assignee field | ✅ Compatible |
| **Keycloak status** | N/A | N/A | v1.0 uses PAT, v1.1 needs SSO | ✅ Documented |
| **Version numbers** | v1.0 | v2.0 minimal | v1.0 (→v1.1 for Keycloak) | ✅ Clear |

**Result:** No contradictions found. All three documents accurately describe their roles and interdependencies.

---

## Lessons for Future Coordination Tasks

1. **Source-of-truth strategy:** When three tools share data, identify which creates the source (MoveFromExchange with contacts.enc) and update that spec first.

2. **Graceful degradation as contract:** If downstream tools can work without a data source, this must be explicitly stated in all affected specs. Verify it's mentioned consistently.

3. **Version/schema alignment:** When one tool's output format changes (e.g., _registry.json v2.0 minimal), trace impact through consuming tools and ensure all mention the same version.

4. **Breaking changes require propagation:** When MoveFromConfluence's auth method changes (PAT → Keycloak), this affects not just MoveFromConfluence's spec but also any spec that claims it "reads from Confluence via REST API v2".

5. **Terminology consistency:** Across all three specs, use "email" consistently (not email_address, contact_email, etc.) to avoid confusion in integration code.

---

## Files Updated (Session 2026-05-25)

1. **MoveFromExchange_TZ_contacts_v1.0.md**
   - §1 Ping Exchange: detailed Kerberos auth, access_type=DELEGATE, EWS version handling
   - §3 Merge: clarified custom field preservation on new contact creation
   - §13 Integration: added Zulip context, Keycloak SSO impact
   - §14 Status: added "Verified 2026-05-25" checklist

2. **MoveFromFF_TZ_v2.0_minimal.md**
   - §13 Integration: added Zulip API mention (1167 contacts available to downstream)

3. **MoveFromConfluence_TZ_v1.0.md**
   - §14 Status: added critical warning about Keycloak SSO migration
   - Integration sections: added Zulip context for cross-tool consistency

---

## Next Actions (Recommended)

1. Create **MoveFromConfluence v1.1 ТЗ** with Keycloak OAuth2 integration (currently PAT is temporary solution).
2. Consider creating **MarkObjectsFromSummary spec** that explicitly documents Zulip + Exchange GAL dual-source strategy.
3. Document **TUTU domain constraints** in each tool (MoveFromExchange EWS only works in domain; MoveFromConfluence works best in domain with browser/session).
