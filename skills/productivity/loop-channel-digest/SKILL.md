---
name: loop-channel-digest
description: "Use when: дайджест канала Loop, новости канала, новости в чате руководителей АИД, синк АИД, руководители аид, общий чат, чат компании, Trisigma, внутренний Trisigma, Внешний Trisigma, AI-аналитик, что в парсинге, новости по парсингу, LLM (БЯМ)."
version: 1.1.0
author: agent
license: MIT
platforms: [linux]
tags: [loop, digest, news, summary, tutu]
related_skills: [mattermost-loop-api, cursor-cli]
---

# Loop Channel Digest

## When to Use
- «сделай дайджест канала X», «новости канала Y», «что было в Loop за неделю/месяц»
- Colloquial: «новости в чате руководителей АИД», «синк АИД», «общий чат», «Trisigma», «AI-аналитик», «что в парсинге» (resolve via mapping; do not re-ask if mapped)
- Periodic short report of issue movement in a Loop channel

## Name → channel (resolve BEFORE CLI)
Match Sasha's phrase (case-insensitive, substring) → slug. **Do not ask** if mapped. Unmapped → ask.

URL pattern: `https://loop.tutu.ru/tutu/channels/<slug>`

| Colloquial (as Sasha says) | Slug |
|---|---|
| «чат руководителей АИД», «синк АИД», «руководители аид» | `chat-rukovoditeley-departamenta-aid` |
| «Общий чат», «чат компании» | `general` |
| «Trisigma чат», «внутренний Trisigma» | `trisigma-proyekt-pilot-vnutrenny` |
| «Внешний Trisigma» | `trisigma-proyekt-pilot-s-zakazchikom` |
| «AI-аналитик внутренний», «просто AI-аналитик чат» | `ai-analitik-multiagentnaya-sistema-aid` |
| «LLM (БЯМ)» | `llm-byam` |
| «парсинг», «новости по парсингу», «что в парсинге» | **GROUP** → procedure below |

`llm-byam` ≠ `llm` (`llm` has no topics). «LLM (БЯМ)» → `llm-byam`.

### Group «парсинг» — one combined digest
One colloquial name → several channels. Run CLI **once per slug**, **same** `--since`/`--until`, merge JSON into **one** markdown digest.

Fixed order:
1. `parsing-avia`
2. `parsing-avtobusy`
3. `parsing-zhd`
4. `parsing-oteli`
5. `parsing-elektrichki`
6. `fa7knzpx93f55gihaanxkrdbya` (Парсеры цен конкурентов)

Merge:
- Shared window for all calls. Save each stdout: `/tmp/digest-<slug>.json`.
- Header: `## 📰 Парсинг — дайджест <ДД.ММ-ДД.ММ>`
- Each theme names the source: `### <Тема> (<slug>) — <status>`
- Concatenate `topics[].threads[]` across JSONs; same theme-extraction/status rules.
- Empty channel in window → skip (no invented themes). All empty → «за период активности нет».
- Experts block: 2–4 most active across the **whole group**.
- Tool still handles **one** channel per invocation (incl. that channel's topics).

## Mechanics
Two layers: **CLI** aggregates deterministically (no LLM); **this model** writes markdown from JSON.

### 1. Call the tool
```bash
cd ~/USERTOOLS/LoopChannelDigest && venv_linux/bin/python -m loop_channel_digest \
  --channel <name> --since <YYYY-MM-DD> --until <YYYY-MM-DD> --format json
```
- Switchable: `--channel` (slug), `--since`/`--until`. Rest are constants.
- Default: **all topics** (`--topics all`).
- Optional: `--team <id>` (default ТУТУ), `--topics` (CSV), `--format md` (debug).
- stdout → `/tmp/digest.json` (single) or `/tmp/digest-<slug>.json` (group). Ignore stderr progress.
- Exit: 0 ok, 2 channel/config, 3 network. If ≠0, show stderr.

### 2. Write digest from JSON
Read JSON and generate STRICTLY in the format below. No FF template, timestamps, or verbatim quotes.

## Output format (constant)
```markdown
## 📰 <Канал> — дайджест <ДД.ММ-ДД.ММ>

### <Тема 1> — ✅ закрыто / 🔄 в работе / 📣 анонс
Суть вопроса одной-двумя фразами: что обсуждали, какой итог.
*Участники: Фамилия, Фамилия.*

### <Тема 2> — ...
...
**Ключевые вкладчики-эксперты:** Фамилия, Фамилия.
```
- Status exactly one of: ✅ закрыто / 🔄 в работе / 📣 анонс (upcoming, no outcome yet).
- Issue-progress only, brief. No time refs, no verbatim quotes.
- Participants = people who actually posted (`participants`/`author`).
- Experts = 2–4 most active/significant.
- No activity in window → «за период активности нет», do not invent.

## Theme extraction (from aggregated threads)
- JSON grouped by topic (`topics[].threads[]`). Default **1 topic = 1 digest theme**; split only if one topic has clearly unrelated discussions.
- Same-issue threads may split by `root_id` (esp. `root_missing=true`) — merge by meaning, no dupes.
- `truncated=true` — truncated (`...N сообщений пропущено...`); recover gist from saved head+tail.

## Pitfalls
- `requests`/`httpx` hang on loop.tutu.ru — tool uses curl+subprocess; do not change.
- Topic channels: parent may be empty; activity is in topics — tool already handles this.
- Unmapped name → ask Sasha. `llm` ≠ `llm-byam`.
- `since`/`until` in ms — conversion inside the tool; pass `YYYY-MM-DD`.
- Token (LOOP_TOKEN) from `~/.config/hermes/.env` or local `.env`; never hardcode or log.
