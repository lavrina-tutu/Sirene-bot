---
name: hermes-memory-hygiene
description: "Declutter Hermes MEMORY and USER PROFILE when they approach their char budget — move technical/procedural detail into skills, keep only pointers, without losing information. Also governs WRITE-TIME discipline: before adding any new MEMORY/USER PROFILE entry, default to writing/patching a skill instead, and compress what actually needs to be a memory entry. Триггеры: почисти память, разбери память, проверь память, почисти профиль, ревизия памяти."
version: 1.4.0
author: agent
license: MIT
platforms: [linux, macos, windows]
tags: [hermes, memory, user-profile, skills, decluttering, context-hygiene]
---

# Hermes Memory & User-Profile Hygiene

Use this skill whenever MEMORY or USER PROFILE usage shown in the context header climbs near its limit (roughly ≥75%), the user asks to "review/clean up memory" (or the Russian equivalents: "почисти память", "разбери память", "проверь память", "почисти профиль" — this covers both an ad-hoc on-demand request and the weekly `vm_selfcheck` cron trigger below), a new `add` is rejected for being full, or you notice the same technical fact duplicated in both a memory entry and a skill.

**This skill also governs WRITE-TIME discipline — see the section right after Scope below — not just cleanup.** Load/apply it BEFORE every `memory(action='add')` call, not only when the store is already full.

## Write-time gate — apply BEFORE every `memory(action='add')` (added 13.07.2026)

This is the proactive half of this skill: cleanup (below) fixes an already-cluttered store; this gate stops new clutter from being written in the first place. Apply it every time you're about to persist a durable fact, whether triggered by an explicit "запомни X" from Sasha or by your own decision during a self-check/self-update pass.

**Категории разрешённых записей** (только они попадают в MEMORY):
- `env-quirk` — quirk среды/инструмента, не меняется → **предпочтительнее в `~/.hermes/HERMES.md`** (не char-budgeted, не инвалидирует кеш при правках MEMORY)
- `pointer` — указатель на скилл/файл где живёт процедура (напр. «PFS crons → about_usr_skills»)
- `decision` — зафиксированное решение Саши без TTL (напр. «contacts только в contacts.enc»)

**Правило роутинга нового факта:**
- «свойство среды/платформы/интеграции» (env-quirk) → `~/.hermes/HERMES.md` секция `## 🔧 Env quirks`
- «эвристика/паттерн/оперативное состояние» → `MEMORY.md`

**⚠️ HERMES.md — только uppercase:** реальный файл `~/.hermes/HERMES.md`. Строчный `~/.hermes/hermes.md` НЕ загружается — механизм `_find_hermes_md()` ищет `.hermes.md` или `HERMES.md` (walk from cwd к git root), Linux case-sensitive. Прецедент 23.07.2026: Sonnet записал изменения в строчный `hermes.md` — файл существовал на диске, но gateway его игнорировал. Симптом: изменение не влияло на поведение агента. Диагностика: `ls -la ~/.hermes/hermes.md ~/.hermes/HERMES.md`. При делегировании субагентам — явно указывать полный путь с заглавными.

**Запрещено в MEMORY** (нарушают стабильность):
- События с датой: «X произошло ДД.ММ» — это лог, не факт → в бэклог или насовсем
- Версии инструментов: «tool v1.2.3» — устареют → в скилл
- Открытые задачи/вопросы: «требует решения Саши» — это TODO → в бэклог
- Процедуры и how-to — это → в скилл

**Before calling `memory(action='add', ...)`, answer these in order:**

1. **Is this a procedure, technical detail, or reusable how-to** (an endpoint, a field ID, a script, a step-by-step workflow, a tool's behavior/quirk that only matters when using that tool)? → **It does NOT go to MEMORY/USER PROFILE at all.** Write it into the skill that owns that domain instead (`skill_manage(action='patch'|'create')`). If no skill owns that domain yet, that's a signal to create one (see `hermes-agent-skill-authoring`), not to default to MEMORY because "it's faster right now."
2. **Is this purely a fact about Sasha as a person** (a stable preference, a corrected behavior, an identity/role fact)? → USER PROFILE, not MEMORY, and only if no skill already documents this preference as part of a workflow.
3. **Is this a durable environment/tool-quirk fact NOT covered by any skill** (and genuinely won't be covered by one — a one-off fact, not a repeatable procedure)? → Only then does it go to MEMORY.
4. **If steps 1-3 all point away from MEMORY/USER PROFILE — don't write anything to either store.** A skill update or no write at all are both valid outcomes; "write it to memory just in case" is not.

**Compression rule for whatever DOES qualify for MEMORY/USER PROFILE (step 2 or 3 above):** write it in pointer form from the first draft, not as a first pass to be compressed later during the next cleanup round:
- Prefer `"<short fact/topic> — see skill <name>, section '<X>'"` over inline procedural detail, even on the very first write.
- No restating context obvious from the pointer itself (drop connective filler like "важно отметить", "стоит зафиксировать").
- If the fact naturally wants inline detail (e.g. a specific schedule, an ID, a numeric threshold) AND is not covered by a skill — keep only the inline detail that's not derivable from a doc elsewhere, no surrounding narrative.
- Target length: aim for what a terse commit message would say, not what a paragraph would say. If your draft entry is longer than ~2 lines, that's a signal steps 1-3 above were skipped — re-check whether it actually belongs in a skill.

**Why this exists:** the reactive cleanup procedure below (13.07.2026 full-purge worked example) found that **100% of existing MEMORY entries were skill duplicates written verbosely** — the gate above is meant to make that outcome the default at write-time, not something discovered only during the next audit.

## Scope: which stores this skill governs

This skill governs **MEMORY** and **USER PROFILE** only — the two char-budgeted stores. It does NOT cover:
- **SOUL.md** / **agent.system_prompt** — separate, not char-budgeted, not this skill's job (see table below for why)
- **SKILLS** themselves (dedup between skills, stale skill content, oversized SKILL.md) — that's a different hygiene pass with its own triggers/cadence, tracked separately (proposed skill `all-skills-hygiene`, not yet created as of 05.07.2026). Don't fold skill-to-skill audits into this procedure — the mechanics differ (no shared char limit, monthly cadence vs. reactive-on-%-threshold).

## Two run modes — interactive vs. scheduled

- **Interactive (Sasha in the chat, ad-hoc "почисти память"):** run the full block-by-block procedure below, one block per turn, wait for explicit confirmation before each edit. This is the default mode for anything triggered inside a live conversation.
- **Scheduled / cron (`vm_selfcheck`, weekly Saturday 03:30, no user present to reply):** do NOT edit MEMORY/USER PROFILE unattended — a cron run cannot wait for per-block confirmation. Instead: read current % usage for both stores, and if either is ≥75%, add ONE line to the self-check report flagging it (e.g. "⚠️ MEMORY 87% (1780/2200) — рекомендована ревизия, скажи «почисти память»"). If both are under threshold, say nothing about them (no need to pad the report). This keeps the weekly check as a detector, not an unattended editor — actual edits still require Sasha's explicit per-block "да" in a live session.
- **This wiring is already live (05.07.2026):** `vm_selfcheck`'s cron prompt has a step 8 ("Гигиена памяти") doing exactly this detect-and-report check, and the job's `skills` list includes `hermes-memory-hygiene`. Don't re-propose adding this hook — if it's ever missing (job edited/reset), re-add a step there rather than creating a second cron job for the same check.

## Trigger-phrase pitfall (skill-authoring lesson from this session)

When adding trigger keywords to a skill's `description` for auto-loading, include the **actual language the user writes in** — Sasha writes exclusively in Russian, so English-only trigger phrases ("review/clean up memory") in a description will reliably miss natural requests like "почисти память". Always add the Russian phrasing alongside the English one when the user is Russian-speaking; don't assume the matcher generalizes across languages.

## The four-tier model — what belongs where

Hermes actually has a fourth tier below USER/MEMORY/SKILLS: **`~/.hermes/SOUL.md`** — the primary agent-identity slot (loaded first, every session, byte-stable) — plus **`config.yaml → agent.system_prompt`**, an ephemeral-but-persistent slot for standing operational rules. Route agent-persona and cross-cutting operational rules there, not into a persona skill or MEMORY:

| Store | Purpose | Example content |
|---|---|---|
| **SOUL.md** | Agent identity — name, character, core values. One copy, no duplication with `agent.personalities` or a persona skill. | Character description, value list, implementation principles |
| **agent.system_prompt** | Standing operational rules that must apply every session regardless of topic (e.g. model-routing/delegation policy) | "Opus does code, Haiku does light chat, main model coordinates" |
| **USER PROFILE** | Who the user IS — identity, role, stable style/format preferences, recurring corrections | "PM at TUTU", "always reply in Russian, no unsolicited suggestions", "'.' means confirm in briefs" |
| **MEMORY** | Environment facts, tool quirks, conventions — durable but NOT tied to a specific person's identity | "gateway restart only via explicit cron", "chat IDs", pointers to where procedures live |
| **SKILLS** (`SKILL.md` + `references/`) | Procedures, technical detail — endpoints, tokens/keys locations, field IDs, scripts, step-by-step workflows | Full Confluence/JIRA auth flow, contract field IDs, model-switch scripts |

**Rule of thumb:** if a fact is a *procedure or technical detail* that a skill already covers (or could cover), it does not belong in MEMORY or USER PROFILE — replace it with a one-line pointer ("see skill X"). If a fact is *purely about the user as a person* (preference, identity, correction), it belongs in USER PROFILE, not MEMORY. If a fact is about the *agent's own persona or identity*, it belongs in SOUL.md, not duplicated across `agent.personalities`, a persona skill, and MEMORY simultaneously — pick SOUL.md as the single source and make everything else a pointer to it.

## Procedure

1. **Read current usage.** The context header shows `MEMORY (...) [XX% — used/limit chars]` and `USER PROFILE (...) [XX% — used/limit chars]` every turn — no tool call needed to check current fill level.
2. **For each entry near/over budget, ask:** does this duplicate content that already lives in a skill (or a project doc like a README)? Load the candidate skill with `skill_view` first — do NOT assume; confirm the skill actually contains the detail before deleting the memory copy, or you will lose the only copy of the fact.
3. **Replace, don't just delete.** Use `memory(action='replace', old_text=..., content=...)` to swap a verbose block for a short pointer line, e.g.:
   - Before: `TUTU: .env=~/.config/hermes/.env. Grafana: .... Keys: 60551e83...`
   - After: `TUTU LLM gateway: full info (endpoints, keys, scripts) — see ~/WorkVault/UserManuals/LLM-Migration/README.md`
4. **Batch multiple edits in one call.** `memory(action=..., operations=[...])` applies all ops atomically against the final char budget — this lets you free room and add new content in the same call, which a lone `add` cannot do when already full.
5. **USER PROFILE follows the same pattern** but the target is different: move *technical* details (API base URLs, token file paths, field IDs) out to the skill that owns that domain; keep only identity/preference/style facts.
6. **Verify nothing was lost** — re-open the skill that's now the sole source of truth and confirm the specific fact (key location, endpoint, ID) is actually present there, not just "probably covered."

## When Sasha asks for a block-by-block review (interactive declutter session)

If Sasha says "давай пробрифуемся по блокам" / "смотрим ещё раз юзер профайл" — this is NOT "go clean it all up silently." Go one block at a time:

1. **Describe first, propose second — never merge the two.** For each block: state verbatim what facts it actually contains (numbered list), THEN give your reduction proposal with reasoning. Sasha corrected this explicitly once ("сначала описание что реально есть, потом предложения") — don't jump straight to a proposal or a `clarify()` multiple-choice without first showing the raw content.
2. **One block per turn, wait for explicit reply** (usually "да" / "." / a specific edit instruction) before touching MEMORY/USER PROFILE for that block. Do not batch-execute all blocks after one blanket "ok."
3. **Execute immediately after confirmation** — one `memory(action='replace'|'remove', ...)` call per block, then state the before/after % and byte count, then ask "переходим к следующему блоку?".
4. **Common outcomes per block:** (a) duplicate of SOUL.md/a skill/another memory entry → remove or point to it; (b) stale version numbers/model names that will keep drifting → strip them, they're not durable; (c) genuinely unique and current → leave as-is, say so plainly instead of manufacturing a cut.

## Universal open-question protocol (generalized 05.07.2026, tightened 16.07.2026)

The block-by-block Q&A pattern below is NOT limited to memory/profile-review sessions anymore — Sasha explicitly generalized it to **all dialogs** with open questions, and it's recorded in USER PROFILE as a standing rule:

1. If there's a list of open questions, show the **full list** first, then ask them **one at a time** (don't dump a multi-question wall of text, but don't hide the scope either).
2. Each question gets: brief context → 1-2 best options → an explicit recommendation for which is best. Don't present options with no opinion attached.
3. Questions and answer options are **numbered** — **numerals only (1, 2, 3...), never letters (A, B, C)**. Sasha corrected this explicitly (16.07.2026, "варианты по номерам, не по буквам") after a question was presented with lettered options. Default to digits even for a 2-option question — don't switch to letters just because there are only two choices.
4. **Every single time you present a question, spell out the full option text again** — the question, each option's full description, and the recommendation. Do NOT shorten to a bare "1 или 2?" once the options are already "established" earlier in the conversation, even in a fast back-and-forth brief where the user is just replying with a bare number each time. Sasha corrected this explicitly (16.07.2026, "дай нормальное полное описание с номерами") after a terse "1 или 2?" follow-up — the full option text must appear on every question, not only the first time it's introduced. Brevity for its own sake is the wrong optimization here; the user needs the actual choice restated to answer confidently, especially across a multi-question brief spanning several turns.
5. **One question per message, one answer per message — never carry sequential numbering across separate questions.** If message N asked "1) X, 2) Y, 3) Z?" and Sasha replied "1", that "1" answers ONLY that message's question — a later, unrelated question in a DIFFERENT message must restart its own numbering from 1, not continue as "4/5/6" or assume Sasha's next bare digit reply refers to the earlier list. Sasha corrected this explicitly (16.07.2026, "Один вопрос один ответ это правила брифа") after the agent asked a fresh question and Sasha replied with a bare "3", which the agent almost mis-attributed to the wrong question's option list. When in doubt after a bare-digit reply arrives to a message that didn't clearly repeat the options — re-show the options before applying the answer, or ask which question it's answering.

This applies beyond memory hygiene — use it whenever a task surfaces multiple open decisions (TZ open questions, config choices, etc.), not only during a `USER PROFILE`/`MEMORY` cleanup pass.

## Skill audit pattern (when asked to review a skill)

Когда Саша просит «проверь/почисти скилл X»: читать целиком → брифовать по одному предложению (что есть + куда перенести) → список решений → один Opus-кронджоб на все патчи. Не запускать правки без явного «ок» по каждому пункту. Из скилла разработки удалять: прецеденты с датами (→ питфоллы), правила поведения агента (→ SOUL), специфику других скиллов (→ профильный скилл), разовые операции (→ насовсем).

## Pitfalls

- **Before declaring a memory block fully redundant, check ALL plausible candidate skills, not just the first match.** In one session a "corp systems ТУТУ" block looked like it belonged to one skill, but the facts were actually split across three (`tutu-confluence-jira`, `tutu-jira-contract-approval`, `about_usr_skills/references/tutu-corporate-integrations.md`). Load each candidate with `skill_view` and confirm the specific fact (URL, login, token name) is present before removing the memory copy — a plausible skill name is not proof.
- **A block can become fully removable for TWO different reasons — treat them differently:** (a) the fact is duplicated in a skill → replace with a pointer or delete outright if the skill is easily found by trigger words; (b) the fact is obsoleted by an environment change (e.g. "VPN needed for LLM" stopped being true once the VM moved inside the corporate domain) → delete outright, don't leave a stale pointer. Ask the user directly when unsure which case applies — don't assume staleness without confirmation.
- **Don't prune from memory before confirming the skill covers it.** A plausible-sounding skill name is not proof — `skill_view` it and grep for the specific fact.
- **Don't just delete — replace with a pointer.** A bare removal loses discoverability; a one-line "see skill X" keeps the trail for future sessions.
- **A single `memory(action='add')` call fails if the store is already full**, even if you intend to remove more than you add. Use the batched `operations` array so removal + addition are evaluated together against the limit.
- **`memory(action='replace', old_text=...)` requires an EXACT substring match** — not a paraphrase, not "close enough". If your `old_text` doesn't match byte-for-byte (including trailing words you may have mis-copied), the whole batch is rejected with "no entry matched", even when other operations in the same batch would have succeeded (it's all-or-nothing). When a `replace` fails: re-read the entry via the error's `current_entries` field, copy the EXACT text from there (or use a short, unambiguous substring instead of the full entry) rather than retyping from memory of what you wrote earlier.
- **A `replace` can ALSO fail purely on char budget, even with a perfect `old_text` match** — if the store is already near its limit and your replacement text is longer than the original (e.g. adding "повторилось дважды, дата X" context to an existing entry), the call is rejected with "Replacement would put memory at N/limit chars", distinct from the exact-match failure above. Don't retry the same longer text hoping it'll pass — either (a) make the replacement net-shorter than the original by cutting something else in the same entry, or (b) use the batched `operations` array in one call to simultaneously trim/remove a second, less-critical entry to free room, exactly like the "single add fails when full" pitfall above but applying to `replace` too. If a near-full store makes even one shortened replace impractical mid-task, it's a signal to stop and run the full hygiene procedure (this skill) rather than keep retrying single edits — repeated failed attempts burn turns without progress.
- **MEMORY vs USER PROFILE is not "environment vs everything"** — don't dump technical/procedural facts into USER PROFILE just because MEMORY is full; that only shifts the overflow problem to the other store. Route technical detail to skills instead of either memory store.
- **Session-level docs (e.g. a project README) can also be the pointer target**, not only a skill — if a README already has the full pricing/endpoint table, memory just needs the file path.
- **`~/.hermes/HERMES.md` — только UPPERCASE.** Механизм `_find_hermes_md()` ищет `.hermes.md` или `HERMES.md` при walk from cwd, Linux case-sensitive. Строчный `~/.hermes/hermes.md` существует на диске, но gateway его не загружает — изменения молча игнорируются. Симптом: env-quirk добавлен, но в следующей сессии агент его «не знает». Диагностика: `ls -la ~/.hermes/hermes.md ~/.hermes/HERMES.md`. При делегировании субагентам — передавать полный путь `~/.hermes/HERMES.md` явно.
- **Dead pointers are worse than no pointer.** Whenever you `skill_manage(action='delete')` a skill, immediately grep MEMORY.md, USER.md, and every other skill's SKILL.md/references for its name (`search_files` or `grep`) and fix or remove any "see skill X" references left dangling. A memory entry pointing at a skill that no longer exists sends the next session on a dead-end lookup.
- **A persona/identity skill duplicating SOUL.md is a smell, not a feature.** If you find a skill whose content substantially restates "who the agent is / character / core values" that already lives in SOUL.md, that's duplication to fix (move the identity into SOUL.md once, leave the skill with only the class-level procedures), not a second source of truth to maintain in parallel.
- **MEMORY.md/USER.md can end up storing literal `\uXXXX` escape sequences instead of real Cyrillic characters** — a sign of double JSON-escaping somewhere upstream (a prior write went through a JSON-encode step twice). Symptom: `read_file` shows garbage like `\u0431\u0430\u0442\u0447` instead of "батч", and `memory(action='replace', old_text=...)` fails with "no entry matched" even though the text visually looks present — because the stored bytes are the literal 6-character escape sequence, not the decoded character, so your `old_text` (typed with real Cyrillic) can never match byte-for-byte. **Fix:** read the raw file content, repair it with a regex substitution — `re.sub(r'\\\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), raw_text)` — then write the corrected (and, while you're at it, compressed per the write-time gate above) text back with `write_file` directly to the memory file path (`~/.hermes/memories/MEMORY.md` or `USER.md`), since the `memory` tool's `replace` action cannot target text it can't string-match. Verify the fix by re-reading the file and confirming real Cyrillic renders, not escape codes.

## MEMORY overflows char budget — write_file fallback (23.07.2026)

When `memory(action='add'|'replace')` is rejected because the store already exceeds its 2200-char budget (e.g. 3081/2200 = 140%), the `memory` tool cannot help at all — even a remove+add batch fails because the store is already corrupt. Fix: use `write_file` with `cross_profile=True` directly on `~/.hermes/memories/MEMORY.md`, writing only the entries that belong there (per the write-time gate above). After the write, verify with `wc -c` that the file is under 2200 bytes.

## hermes.md as a fifth tier for env-quirks (23.07.2026)

`~/.hermes/hermes.md` is auto-loaded every session, has NO char budget, and rarely changes → it is the correct home for **env-quirks** (platform/integration constraints that never change). MEMORY is for **operational state** (pointers, decisions, heuristics that evolve). Routing rule:
- **env/platform/integration property** (e.g. «Telegram strips hyperlinks», «cron deliver strips thread_id») → `hermes.md` under `## 🔧 Env quirks`
- **heuristic/pattern/operational pointer** (e.g. «PFS crons → skill X») → `MEMORY.md`

Why it wasn't done earlier: `memory` tool is available in-dialog and feels convenient; `write_file` on hermes.md requires an explicit deliberate step. The routing rule above closes the gap.

**Benefit:** env-quirks in hermes.md don't change → system prompt stays byte-stable → prompt cache is not invalidated. Env-quirks in MEMORY invalidate cache every time any MEMORY edit happens.

## Worked example: full MEMORY.md purge to zero (13.07.2026)

Sasha asked to "delete unneeded blocks in memory" after an unrelated debugging session. Audit of all 8 MEMORY entries found **every single one** was a duplicate of content already documented in more detail in a specific skill (gateway/cron routing → `hermes-gateway-setup`; WorkVault Inbox timer → `workvault-sync-infra`; open-question protocol → this skill + `hermes-feature` Block 1; Confluence "never deletes, only copies" rule → `hermes-feature` pitfall 43 + `tutu-confluence-jira` + `about_usr_skills`; contacts.enc/ContactStore → `about_usr_skills`; username≠login CQL resolve → `tutu-confluence-jira`; "don't confirm done on subagent's word" → `hermes-feature` Block 5Б/pitfalls; side-effect permission classification → `hermes-feature` Block 5Б itself). Result: MEMORY.md was reduced to 0 bytes.

**A fully-empty MEMORY store after verification is a legitimate outcome, not a sign the audit went too far or "removed too much."** Don't manufacture a residual entry just to leave something behind — if every fact really is covered elsewhere with more detail, deleting the last of them is correct. The store exists to hold NEW facts not yet covered by a skill; it doesn't need permanent occupants.

**Efficient verification technique for multi-entry passes:** instead of `skill_view`-ing candidate skills one at a time per memory entry (slow when there are 6+ entries to check), batch it — glob-read all `SKILL.md` files at once and grep each memory entry's key fact/keyword (a distinctive noun, function name, or exact phrase) against the full set in one pass, then only `skill_view` the specific hits to confirm the exact fact is present (not just topically adjacent). This turns an O(entries × candidate skills) sequence of tool calls into one batch scan plus a handful of targeted confirms.

## Worked example: retiring a persona skill entirely

When a persona skill (e.g. `sirene-chat-friends`) has fully migrated its identity content into SOUL.md and its remaining procedural content is redundant with `agent.system_prompt` or another umbrella skill, deleting it outright (not just trimming it) is the right call — don't leave a hollowed-out skill around "just in case."

**Safe deletion sequence used successfully:**
1. Audit every section of the skill — classify each as: duplicate of SOUL.md/system_prompt (delete), unique procedural content (relocate to the umbrella that owns that domain, e.g. cron/backlog rules → the backlog-rules skill; VM paths/infra → the VM-migration skill; restart protocol → the gateway-setup skill), or genuinely obsolete (delete).
2. Relocate unique content FIRST (via `skill_manage(action='write_file')` or `patch` on the target umbrella), confirm it landed, THEN delete the source skill — never delete before the destination write is confirmed.
2b. If it's actually the MEMORY.md pointer *format* (not the skill) that needs shrinking to make room, that's the `hermes-memory-hygiene` main procedure above, not this deletion sequence.
3. `skill_manage(action='delete', name=..., absorbed_into=<umbrella-or-''>)` — pass the real umbrella name if content was merged, empty string if it was pure pruning with no forwarding target.
4. Immediately grep MEMORY.md, USER.md, and all skills for the deleted skill's name — at least one dangling reference is likely (e.g. a doc-skill's "see skill X for persona details" line, or a `config.yaml` comment). Fix every hit found this way, not just the ones you remember creating.
5. If the deleted skill's identity role is now served by SOUL.md, add ONE MEMORY.md entry stating that fact explicitly (e.g. "Agent identity lives only in SOUL.md, not duplicated in config.yaml agent.personalities or skills") so a future session doesn't reintroduce the duplication by habit.
