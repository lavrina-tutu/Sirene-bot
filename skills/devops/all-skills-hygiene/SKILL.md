---
name: all-skills-hygiene
description: "проверь скиллы: аудит дублей и stale"
version: 1.3.2
author: agent
license: MIT
platforms: [linux, macos, windows]
tags: [hermes, skills, decluttering, audit, dedup]
metadata:
  hermes:
    tags: [hermes, skills, decluttering, audit, dedup]
    related_skills: [hermes-memory-hygiene, hermes-agent-skill-authoring]
---

# All-Skills Hygiene

## Overview

Hermes accumulates skills over time (106+ as of 05.07.2026). This skill audits the SKILLS layer itself — duplication between skills, dead skills nobody uses, oversized SKILL.md files, and dangling cross-references. It is the sibling of `hermes-memory-hygiene`, which governs MEMORY/USER PROFILE — a different store with different mechanics (no shared char budget here; the problems are dedup/staleness/bloat, not overflow).

**Status: graduated from draft on 05.07.2026** after one full interactive pass against real data (see "Worked example" below for what that pass actually found and how it was executed). Ready for scheduled detect-only mode per "Two run modes."

## When to Use

- User says "проверь скиллы" / "почисти скиллы" / "ревизия скиллов" / "audit skills"
- Scheduled monthly run (detect-only, see "Two run modes")
- You notice the same fact duplicated across 2+ skills while working on something else

**Don't use for:** MEMORY/USER PROFILE cleanup (`hermes-memory-hygiene`), authoring a single new skill (`hermes-agent-skill-authoring`).

## Data sources

- `skills_list()` — full inventory: name, description, category, for all skills.
- `~/.hermes/skills/.usage.json` — real usage metrics per skill: `use_count`, `view_count`, `last_used_at`, `last_viewed_at`, `patch_count`, `pinned`, `state`, `created_at`. Read this file directly (`read_file`) rather than guessing — it's the only ground truth for "is this skill actually used."

## Finding categories (what to look for)

| Category | Signal | Action |
|---|---|---|
| **Content duplication** | 2+ skills state the same fact (URL, token location, procedure) near-verbatim | Identify source-of-truth skill → convert the rest to a one-line pointer or `absorbed_into` merge |
| **System-flagged stale** | `.usage.json` entry has `"state": "stale"` (set by the platform itself, not a computed heuristic) | Treat as a priority candidate even if it doesn't independently meet the 60-day zero-usage bar — investigate first (file may still exist and be topically relevant), present alongside dead-skill findings, same one-item-at-a-time approval |
| **Dead skill** | `use_count=0` AND `view_count=0` for **≥60 days** since `created_at` (or since last mass re-index if that's more recent — see Pitfalls), NOT `pinned` | Flag to Sasha — NEVER auto-delete; propose delete or keep with reasoning |
| **Index noise (stale∩zero)** | `.usage.json`: `state=stale`, `use_count=0`, `view_count=0`, not `pinned`, not `ESSENTIAL_SKILLS` | Prune the **index** via `skills.disabled` in `config.yaml` (`save_disabled_skills`) — files stay on disk; NEVER auto-delete; no cron delete |
| **Orphaned usage.json entry** | Skill name exists in `.usage.json` but `skill_view(name)` returns "not found" / not in `skills_list()` — the skill file was deleted but its metrics record wasn't cleaned up | Propose removing the stale `.usage.json` entry (metrics cleanup, not a skill deletion — no `skill_manage(action='delete')` needed) |
| **Oversized SKILL.md** | >14–20k chars (soft threshold from `hermes-agent-skill-authoring`; hard limit 100k) | Delegate a structural rewrite to Opus (see "Delegating structural fixes to Opus" below) — don't rewrite a 50k+ file yourself turn-by-turn |
| **Stale technical detail inside one skill** | Dates/versions/URLs that may no longer be true (e.g. "VPN needed" after VM moved into corp domain); also applies to individual entries in a `## Common Pitfalls` list describing a specific code bug | Verify against live system state (read the actual current source, not the skill's last-edited date) — ask Sasha when unsure. **If verification shows the bug is still genuinely open** (not just stale prose), this audit can extend into a live fix in the same pass: minimal patch + a regression test proving the exact failure mode + full test-suite run, THEN collapse the pitfall text to "FIXED — <what changed>, see `<test file>`" (keep the entry, don't delete it — the lesson stays useful even once the code is fixed). **If already fixed elsewhere**, collapse to a short confirmation note instead of re-describing the original incident at length. |
| **Dangling references** | A skill's `related_skills` or body text points to a deleted/renamed skill | Find via `search_files` for the old name across all SKILL.md + MEMORY.md + USER.md; fix or remove |
| **Frontmatter hygiene** | Missing `version`/`author`, or `platforms: [all]` (known to break indexing) | Low-risk — fix directly without asking |

## Procedure

1. **Collect candidates by category, one category at a time** — don't mix duplication findings with dead-skill findings with size findings in one big list. Read `.usage.json` once per pass, `skills_list()` once per pass.
2. **Present findings to Sasha per the universal open-question protocol** (see `hermes-memory-hygiene` → "Universal open-question protocol"): full list of findings first, then go one at a time, each with brief context + recommendation + numbered options.
3. **Act only after explicit per-item approval** — same discipline as memory hygiene, not batch-executed after one blanket "ok."
4. **Consolidation** → `skill_manage(action='delete', name=..., absorbed_into=<target-skill>)`. **Pure pruning** → `absorbed_into=''`.
5. **After every delete** — grep MEMORY.md, USER.md, and all remaining skills for the deleted skill's name (`search_files`) and fix any dangling "see skill X" references.
6. **Oversized skill found** — don't rewrite it yourself line-by-line in the chat session. Delegate to a one-shot cron (see next section) with a concrete pass/fail rule for when it may act autonomously vs. must stop for the user's decision. Default to Sonnet for this delegation; escalate to Opus only if the mechanical/semantic boundary itself can't be stated unambiguously up front (see next section).

## Delegating structural fixes: Sonnet by default, Opus only when the boundary itself is unclear (revised 13.07.2026)

Once you've identified an oversized/non-compliant skill through this audit, the actual rewrite is a large, mechanical, multi-file task — better suited to a one-shot cron than turn-by-turn `patch` calls in the live chat (token-expensive, and risks losing chat context mid-rewrite).

**Model choice: use Sonnet, not Opus, when the mechanical/semantic boundary can be stated explicitly and unambiguously in the prompt.** This class of work (moving content to `references/`, deduping near-identical repeated pitfalls without losing facts, filling missing frontmatter fields, fixing broken escape sequences from prior edits) is pattern-matching and careful copy-paste, not judgment-heavy authoring — it does not need Opus-level reasoning once the boundary rule is spelled out. Reserve Opus for cases where the mechanical/semantic line itself is fuzzy going in (e.g. deciding whether two skills' overlapping content is true duplication or subtly different domains) and the model has to make that call unattended.

**Cron prompt must give the model a clear autonomy boundary up front** — this is the key mechanism that lets it finish end-to-end in one shot without the user's mid-flight approval, regardless of which model runs it:

- **List the exact gaps found** against `hermes-agent-skill-authoring`'s checklist (missing sections, size, frontmatter fields).
- **State the explicit decision rule**: "if every fix is mechanical (moving content to `references/`, adding missing sections, filling frontmatter, deduping without losing facts) — implement immediately. If any fix would change agent behavior/semantics (deleting a block outright, merging two blocks in a way that drops nuance) — STOP, present the plan with explicit 'user decision needed: ...' items, do not implement." This single rule is what makes unattended one-shot execution safe.
- **Non-negotiable constraint stated explicitly**: no fact/case/example may be lost — compress wording freely, but a real incident, command, or number moved to a reference file must be moved in full, not paraphrased down to a summary.
- **Require a backup before touching the file**: `cp SKILL.md SKILL.md.bak-preopt-<timestamp>` before any edit.
- **Require the final report to state before/after size and NOT dump the full rewritten file into the chat** — the user reads the file themself; the report should be a change summary only.
- **Require a final self-check**: `grep "^## "` on the rewritten file to confirm every original top-level section header is still present, plus a manual read of the frontmatter block.

## Exporting skills to another Hermes agent (bundling + depersonalization)

Distinct from the audit/dedup work above, but same skill-layer territory: packaging one or more skills as a portable archive for a *different* Hermes instance/user to install. Applies to **every future skill export**, not just a one-off (explicit user rule, 09.07.2026) — treat this as the standing procedure whenever asked to "выгрузи скилл(ы) для другого агента/пользователя".

1. **Depersonalize before packaging.** Read every candidate skill fully and strip anything specific to the current user/environment: real names used as identity examples, real hostnames/paths, specific internal cron job IDs, specific company/tool names used only as illustrative context. Replace with generic placeholders or reworded examples that preserve the lesson without the identity. Verify with a targeted `search_files`/grep pass over the depersonalized copy for the user's name, machine hostname, and any other known-specific string before packaging — don't rely on having "remembered" to remove everything.
2. **Package as a directory tree**, one subfolder per skill (`<skill-name>/SKILL.md` + its `references/`/`templates/`/`scripts/` if any), plus a root **INSTALL.md** covering: where to extract it (`~/.hermes/skills/<any-category>/`), the fact that a **new session is required** before the skill loader picks it up (session-start cache, not live-reloaded), how to verify it landed (`hermes skills list`), and what — if anything — the receiving user should adapt for their own environment/terminology.
3. **Archive format**: `tar czf` is sufficient and portable; keep the working copy in a scratch location (e.g. `/tmp/...`) and emit the final artifact to a durable path (this agent's convention: `~/.hermes/_Archives/`), then clean up the scratch copy.
4. **Delivering the file**: if the destination is a chat platform (Telegram etc.), sending a bare absolute path in the response text is the documented trigger for the platform's own file-attachment upload mechanism — but don't assume success from the tool call completing. Explicitly ask the recipient to confirm the file actually arrived as an attachment (not as literal path text) before considering the handoff done; file-delivery-vs-path-echoed-as-text is a known category of platform bug, not something to take on faith.

## Two run modes (mirrors hermes-memory-hygiene)

- **Interactive (first pass, and any ad-hoc "проверь скиллы"):** full audit, present findings, wait for per-item approval, execute (or delegate to Opus per above), then report before/after skill count and sizes.
- **Scheduled (cron, monthly):** detect-only — collect findings, write them to the self-check report or a dedicated file, do NOT delete/merge/delegate-rewrite anything unattended. Sasha reviews and approves in a follow-up interactive session.

## What this skill does NOT do

- Does not touch MEMORY/USER PROFILE (that's `hermes-memory-hygiene`)
- Does not delete `pinned` skills (the tool itself refuses this)
- Does not flag a skill as dead purely on "not patched recently" — must combine with `use_count`/`view_count`
- Does not let a delegated rewrite (Sonnet or Opus) make semantic decisions (block deletion, meaning-changing merges) without stopping for the user

## Worked example: first full pass (05.07.2026)

This is what graduated the skill from draft — kept here as the concrete precedent for future passes, not just an abstract rule.

**Dead-skill category:** naive `use_count=0 AND view_count=0` flagged 65/92 skills. Investigation showed 64 of them shared one `created_at` (~10 days old) from a single bulk `.usage.json` re-registration event — a false signal, not real staleness (this is now baked into the Pitfalls below and the 60-day/outlier rule above). The one genuine outlier, `hermes-dev-patterns` (39 days old vs. the 10-day cluster), turned out to be an **orphaned usage.json entry** — the skill file itself no longer existed (`skill_view` → not found). Sasha approved removing just that stale metrics entry; zero real dead skills found this pass.

**Oversized-skill category, case `hermes-feature` (58K → 28.4K):** before delegating the structural rewrite, three smaller pitfall-level dedup fixes were done directly in the interactive session (each individually approved by Sasha): (1) three near-identical "gateway restart blocked from inside" entries collapsed into one; (2) a stray English `## Pitfalls` heading (1 item) merged into the main Russian `## Питфоллы` section instead of existing as a second parallel heading; (3) three long upstream-cutover pitfalls that duplicated `references/upstream-cutover-procedure.md` verbatim were compressed into one pointer block that preserves all three original incident case studies (translated to English for density), rather than being deleted.

Once those hand-fixes were in and Sasha confirmed the skill was checked against `hermes-agent-skill-authoring`'s checklist (missing `## Verification Checklist`, missing `license`/`metadata.hermes`, still 54K after manual dedup), the remaining structural work was delegated to a one-shot Opus cron per "Delegating structural fixes to Opus" above. Opus determined every remaining fix was mechanical (splitting Block 0 and other bulky sections into new `references/*.md` files, adding `## Verification Checklist`, filling `license`/`metadata.hermes`) and executed the full rewrite unattended — no mid-flight decision was needed from Sasha, confirming the autonomy-boundary rule worked as designed.

**Second pass, `state: stale` category (13.07.2026):** cross-checking `.usage.json` for the `state` field directly (not just zero-usage) surfaced 3 skills explicitly flagged `stale` by the platform: `dialog-backlog` (file exists but `skills_list()` reports it unsupported on this platform — a different failure mode than orphaned-entry), `local-llm-hardware` (topically unrelated to Sasha's actual work, 1.5 months idle), `multi-document-coordination` (overlaps `tz-workflow`, 1.5 months idle). Presented one-at-a-time per protocol; Sasha did not respond within the review window for any of the three — findings left open, no deletion executed. This is the correct outcome for a "no per-item yes yet" state, not a stall to fix.

**Third pass, verify-then-fix on "stale technical detail" pitfalls (13.07.2026):** Sasha asked to walk `hermes-feature`'s largest Common Pitfalls entries one by one, biggest-to-smallest, and for several ("didn't we already fix this in the tool?") to check the real code rather than trust the pitfall's prose. Of 4 checked: 2 turned out already fixed (confirmed by reading the actual source + existing tests, then shortened the pitfall to a brief confirmation note); 2 were genuinely still open and were fixed live in the same pass — one needed a new guard clause plus a new regression test file proving the exact original failure mode no longer causes an unhandled crash; the other needed only a missing test added for an inverse/rollback function that already existed in the source but had zero coverage. Full test suites re-run after each fix (153/153 and 130/130 respectively) before updating the corresponding pitfall text. This is the "Stale technical detail" category from the table above in its most active form — audit-that-becomes-a-fix, not just prose cleanup.

## Проверка пересечений триггеров между скиллами

При аудите description проверять не только дубли содержимого, но и **пересечения триггерных слов** — одно слово в двух description = оба скилла загружаются на один запрос.

**Паттерн:**
1. Выписать триггеры каждого скилла из description
2. Найти пересечения между близкими по теме скиллами
3. Для пересекающегося слова решить: где оно правильнее по смыслу?
4. Убрать из одного, оставить в другом

**Прецедент 26.07.2026:** `hermes-feature` имел триггеры «исследуй», «проанализируй» — при запросе «исследуй инструмент X» загружались и `hermes-feature`, и `tz-workflow`. Исправление: исследование = предпроектная фаза → триггеры переехали в `tz-workflow`.

**Правило роутинга по смыслу (ТУТУ-экосистема):**
- «исследуй», «проанализируй», «изучи инструмент» → `tz-workflow` (предпроектная фаза)
- «разработай», «реализуй», «баг», «не работает» → `hermes-feature` (фаза кода)
- «почисти память», «dev reset» → `hermes-memory-hygiene`

## Common Pitfalls

- **При сверке «скилл существует?» — искать во ВСЕХ категориях, не только devops/productivity.** Прецедент 26.07.2026: скрипт проверял только devops/ и productivity/, пропустил `get-obsidian-link` (note-taking/), `obsidian` (note-taking/), `workvault-rag` (research/) — они были ошибочно помечены как несуществующие. Правильный поиск: `find ~/.hermes/skills ~/.hermes/profiles/<profile>/skills -name "SKILL.md"` — по всему дереву без фильтра категории.
- **Скилл созданный Opus-кроном оседает в `profiles/default/`, а не в активном профиле.** Симптом: крон сообщает «Skill not found and skipped: \<name\>». Фикс: `cp -r ~/.hermes/profiles/default/skills/devops/<name> ~/.hermes/profiles/tz-dev/skills/devops/`. Профилактика: в промпте Opus явно указывать полный путь установки скилла: `Создай скилл в ~/.hermes/profiles/tz-dev/skills/devops/<name>/SKILL.md`. Прецедент 27.07.2026: `backlog-collector` и `backlog-analyst` созданы в default, не найдены при первом запуске кронов.
- **Two skills in one Opus cron is fine** — confirmed 06.07.2026: `hermes-gateway-setup` + `hermes-cost-optimization` processed sequentially in one cron job. Saves one context-launch worth of tokens vs two separate crons. Only combine skills that are truly independent (no shared files, no ordering dependency between them).
- **A plausible skill name is not proof of duplication** — before merging two skills, `skill_view` both and confirm the specific fact is actually restated, not just topically adjacent.
- **`use_count=0` alone isn't proof of "dead"** — a skill can be legitimately used without the counter incrementing in every code path (e.g. injected via cron `skills=[...]` rather than triggered by description match). Cross-check against cron job configs (`cronjob(action='list')` → `skills` field) before recommending deletion.
- **A mass `.usage.json` re-index resets `created_at` for the whole catalog at once — don't mistake that for real 0-day-old skills.** If most of the catalog shares one birth date, that date reflects a re-index, not real skill age. Prefer the 60-day threshold and sanity-check outliers (one skill much older than its neighbors) as the strongest real dead-skill signal.
- **Don't auto-delete anything** — every finding in this skill is a recommendation, execution needs the user's explicit per-item "да", even when delegating the rewrite (the autonomy boundary only covers mechanical formatting, never semantic deletion).
- **Don't rewrite a 50k+ SKILL.md yourself, turn-by-turn, in the live chat.** It burns tokens on repeated full-file reads and risks losing track of what's already been changed mid-session. Delegate to a one-shot cron (Sonnet by default) once the audit has identified what needs to change.
- **A cron delegation succeeding end-to-end confirms the model choice was right; a cron that stalls/loops on self-verification scripts is not a model-choice failure per se** — worked example 13.07.2026: an Opus cron on a genuinely mechanical rewrite spent several tool calls on broken verification one-liners (typos in inline Python) before finishing correctly — that's normal self-correction, not evidence the task needed a stronger model.
- **A user's uncertain claim that something "seems fixed" ("кажется исправили") is a lead to verify, not a fact to accept or reject on your own memory of the code.** Check every layer the original incident actually spans before answering — a fix can land in one place and not another (e.g. a validated data schema stayed correct, but the cron prompt that consumes it still has the old unguarded heuristic). Read the current source/prompt directly (`grep`/`read_file` on the real file, not recall from earlier in the session) and report exactly which layer is/isn't fixed, rather than confirming or denying the claim wholesale.

## Verification Checklist

- [ ] Findings grouped by category, not mixed
- [ ] Each finding has a clear recommendation + alternative (per universal open-question protocol)
- [ ] No delete/merge/rewrite executed without explicit per-item approval (directly, or via the Opus autonomy-boundary rule)
- [ ] Dangling references checked and fixed after any delete
- [ ] `.usage.json` read fresh, not assumed from memory
- [ ] For delegated Opus rewrites: backup created before edit, final report has before/after size and no full-file dump
- [ ] For "is this pitfall still true?" claims (yours or the user's) — verified against live source/tests, not answered from session memory; if a live fix was made, full test suite re-run before the pitfall text was updated
