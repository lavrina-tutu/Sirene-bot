---
name: multi-document-coordination
description: "Coordinated review, update, and cross-reference validation for interdependent documents (specs, APIs, configs, Russian ТЗ files). Prevent inconsistencies when changes in one file affect contracts in others."
version: 1.1.0
tags: [documents, specs, consistency, tz, workvault, coordination]
platforms: [windows, linux, macos]
triggers:
  - Task requires reviewing and updating multiple related documents
  - Need to ensure consistency across files that reference each other
  - Updates in one file affect contracts/expectations in other files
  - Domain involves interconnected modules, specs, APIs, or configurations
---

# Multi-Document Coordination: Review, Update, Validate

## Overview

When a task requires coordinated updates across multiple related documents (technical specs, API docs, configuration files, contract definitions, or interdependent system docs), a structured approach prevents inconsistencies, missing updates, and broken cross-references.

**Core principle:** A change in one document's contract may create obligations in others. Find all affected files, update them together, verify consistency before declaring done.

---

## Workflow (5 Phases)

### Phase 1: Discovery & Mapping

**Goal:** Identify all related documents and understand their relationships.

1. **Locate files** using `search_files` with relevant patterns (e.g., filenames, extensions).
2. **Note file paths** — you'll refer to them multiple times; keep a list.
3. **Skim for relationships** — which files reference which? (e.g., API docs → spec, schema → implementation guide).
4. **Create a simple map:**
   ```
   File A (source of truth) → File B (uses A's API) → File C (depends on B's format)
   ```
   This helps you understand update order and cascade effects.

**Pitfall:** If files are in multiple locations (archived, versioned, working directories), search **all** candidate paths before reading. Don't assume you found the "main" copy on first match.

---

### Phase 2: Complete Read (Full Context)

**Goal:** Understand the full scope of each document before making any edits.

1. **Read each file completely** using `read_file` — no peeking at snippets.
   - If a file is long (offset/limit pagination), read the full thing in sections to understand the whole.
   - Note section headers and key boundaries (where contracts/APIs are defined).

2. **As you read, mark**:
   - Sections that will need updates (based on your findings/requirements)
   - Cross-references to other documents (e.g., "see X_TZ_v1.0.md")
   - Key fields, schemas, or contracts that other files depend on

3. **After reading all files**, create a **change map**:
   ```
   File A: Update §3 (contract), §7 (integration with B)
   File B: Update §5 (uses A's new field), §9 (TG commands)
   File C: No changes needed (graceful degradation)
   ```

**Pitfall:** Don't start editing until you've read everything. A change in File A's contract may affect File B in ways you won't see if you patch A first, then read B.

---

### Phase 3: Surgical Patching

**Goal:** Apply focused, context-aware updates to each file.

1. **For each change in your map**, use `patch` (mode='replace') with **surrounding context**:
   ```
   old_string: "... 2 sentences before ... [exact text to change] ... 2 sentences after ..."
   new_string: "[updated text]"
   ```
   This ensures the patch finds the right occurrence and doesn't match unintended text.

2. **Order of patching matters:**
   - Start with **source-of-truth files** (specs, schemas, definitions).
   - Move to **consuming files** (docs that reference the source, code that implements it).
   - This way, when you patch consuming files, you have the final contract in front of you.

3. **Verify each patch** — read the diff output to confirm it applied as intended. If a file is longer than expected or uses offset/limit pagination, re-read the whole file before the next patch.

4. **For large or repeated updates**, consider `write_file` instead of multiple patches (faster, clearer intent).

**Pitfall:** Patches can fail silently if the old_string is not unique. Always include enough context. If a patch fails, re-read the file (pagination may have hidden the text) before retrying.

---

### Phase 4: Cross-Reference Consistency Check

**Goal:** Verify that all files now agree on shared contracts and interdependencies.

1. **Build a consistency matrix:**
   ```
   | Field/Contract | File A | File B | File C | Agree? |
   |---|---|---|---|---|
   | contacts.enc schema | v1.0 | uses v1.0 | reads v1.0 | ✅ |
   | graceful degradation | yes | yes | yes | ✅ |
   | Keycloak auth | v1.1 todo | requires v1.1 | N/A | ✅ |
   ```

2. **Look for:**
   - **Matching version numbers** (if one doc says "schema v2.0", others should too).
   - **Consistent terminology** (e.g., "contacts.enc" used the same way everywhere).
   - **Matching dependency statements** (e.g., if File A says "uses contacts from File B", File B should say "provides contacts to File A").
   - **Alignment on future work** (e.g., if one says "v1.1 will add X", others shouldn't claim X exists in v1.0).

3. **If inconsistencies found**, decide:
   - Is this a real conflict (e.g., one file says X is required, another says optional)? → Patch one or both.
   - Is this a known difference (e.g., one file is archived, newer is elsewhere)? → Document it and move on.
   - Is this just terminology (same concept, different name)? → Align the wording across files.

4. **Re-verify** after fixing inconsistencies.

**Pitfall:** Automated diff tools can miss semantic inconsistencies (e.g., "uses File B's API" ↔ "File B provides no API"). Read for meaning, not just syntax.

---

### Phase 5: Final Reporting

**Goal:** Document what changed, why, and what remains consistent.

1. **Create a summary report:**
   - List which files were updated and what changed in each.
   - Note any new cross-references or contracts.
   - Flag any inconsistencies **found but not fixed** (with rationale).
   - List any contradictions **resolved** during the update.

2. **Explicitly state:**
   - What was the **source of truth** for these changes? (e.g., "field findings from 2026-05-25")
   - Which documents are **interdependent** and how.
   - Which documents can operate **independently** (graceful degradation).
   - Any **breaking changes** or **migration requirements** (e.g., "v1.0 uses PAT, v1.1 will use Keycloak").

3. **Save the report** (e.g., as a reference file or in session output).

---

## Example: Technical Specs Coordination (Real Case)

**Scenario:** Three tools (MoveFromExchange, MoveFromFF, MoveFromConfluence) share contact data. A finding (Zulip has 1167 contacts) must be integrated consistently across all three spec docs.

### Phase 1: Mapping
```
MoveFromExchange_TZ_v1.0.md (source: creates contacts.enc)
  ↓ (provides contacts)
MoveFromFF_TZ_v2.0.md (reads contacts for resolving email→name)
MoveFromConfluence_TZ_v1.0.md (reads contacts for resolving email→name)
  ↓ (both feed into)
MarkObjectsFromSummary (downstream consumer — not edited, but mentioned)
```

### Phase 2: Read
- Read all three TZ files completely.
- Note: MoveFromExchange defines contacts.enc schema; others use it.
- Note: All three mention "downstream tools" and graceful degradation.

### Phase 3: Update Order
1. **MoveFromExchange first** — update integration section to mention Zulip as additional source.
2. **MoveFromFF next** — note that MarkObjectsFromSummary can now use Zulip contacts.
3. **MoveFromConfluence last** — add Zulip mention in same context.

### Phase 4: Cross-Check
- Matrix: All three now mention Zulip API (1167 contacts), graceful degradation, and Exchange GAL.
- Consistency: No conflicts found. All three correctly describe downstream tools' options.
- Flag: Keycloak SSO migration (MoveFromConfluence only) — deliberate, documented as v1.1 requirement.

### Phase 5: Report
- Created UPDATE_REPORT_2026-05-25.md listing all changes.
- Verified: No contradictions between files.
- Noted: Keycloak migration requires separate v1.1 ТЗ.

---

## WorkVault ТЗ Iteration (workvault-tz-iteration)

Specialized variant for applying batched edits to Russian ТЗ markdown specs in `C:\Users\tkachenkoav\WorkVault\Meetings\` after a Q&A review round.

**Triggers:** «внеси правки в ТЗ», «обнови файлы в WorkVault», user cites a sibling Q&A / Brief file and wants answers propagated into the main spec.

### Принципы
1. **Точечные правки** (`patch` mode='replace' с маленькими уникальными блоками), не переписывать целиком.
2. **Синхронность** — правка про таймзону/схему/именование затрагивает ВСЕ файлы пакета.
3. **Закрывать открытые вопросы** — обновить секцию `## Открытые вопросы`: `✅ QN: закрыт: <решение>`.
4. **Sanity-check** после всех правок: `search_files` по «удалённым» терминам → 0 совпадений.
5. **Отчёт** по файлам с § ссылками на русском.

### Алгоритм
1. Прочитать все файлы пакета целиком (`read_file`).
2. Сгруппировать правки по файлам (одна правка часто затрагивает 2-3 файла).
3. Параллельные `patch` для независимых правок в РАЗНЫХ файлах; последовательные — в ОДНОМ файле (race condition).
4. Обновить секцию «Открытые вопросы».
5. Sanity-check: поиск старых терминов (`Europe/Moscow`, `+03:00`, `bullet_gist`, `restored`).
6. Отчёт.

### ТЗ-специфичные pitfalls
- **`patch` race:** повторный patch к тому же файлу в одном tool block → `Failed to read file`. Разносить по разным tool block'ам.
- **Markdown table pipe escape:** `|` внутри ячеек → `\|`.
- **UTC ISO в примерах:** при переходе на UTC обновлять JSON-примеры в схемах (`"+03:00"` → `"Z"`, `14:30:00+03:00` → `11:30:00Z`).
- **«Не использовать X» — это правило, не предложение:** писать дословно с **жирным** «не».
- **Поля в нескольких местах:** таблица §13 + JSON-схема §9 + enum — обновлять все три.
- **Зеркальные ссылки между ТЗ:** если правка пробрасывает обязанность из A в B — добавить в оба.

### DoD
- Все нумерованные пункты из запроса применены.
- Кросс-файловая консистентность (одно поле/решение одинаково во всех файлах).
- Sanity-check = 0 совпадений.
- «Открытые вопросы» обновлены.
- Отчёт с § ссылками отправлен.

---

## Pitfalls & Prevention

| Pitfall | Prevention |
|---------|-----------|
| Read snippets; miss context; create inconsistency | Read entire files before patching. |
| Patch one file, discover it breaks contract in another | Build change map before patching. |
| Patch fails silently; apply wrong version | Always include surrounding context in old_string. Re-read file after pagination. |
| Update File A, forget to update File B | Use explicit change map (Phase 2) to track all affected docs. |
| Consistent terminology locally, inconsistent globally | Build consistency matrix (Phase 4) checking cross-file alignment. |
| Break a contract that downstream tools depend on | Read integration sections before deciding what's safe to change. |
| Miss that files are outdated copies (archive vs. current) | Search all candidate paths (dev, archive, versioned dirs) upfront. |

---

## DoD (Definition of Done)

- ✅ All related files located and identified.
- ✅ Each file read completely before any patching.
- ✅ Change map created showing which sections of which files need updates.
- ✅ Updates applied in dependency order (source-of-truth first).
- ✅ Cross-reference consistency verified (matrix: no contradictions).
- ✅ Summary report created documenting changes and rationale.
- ✅ Any unresolved inconsistencies explicitly flagged and explained.
