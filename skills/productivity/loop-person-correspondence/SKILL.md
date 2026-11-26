---
name: loop-person-correspondence
description: "Use when переписка человека в Loop: что стоит перед X, DM."
version: 1.0.0
license: MIT
platforms: [linux]
tags: [loop, mattermost, api, persona, correspondence]
---

# Loop: переписка конкретного человека

Get the Loop correspondence / open tasks of ONE person (a colleague Sasha has access to), their DM with Sasha, or their activity across channels. Companion to the git-stored `mattermost-loop-api` umbrella (auth, token, curl-via-subprocess, channel-id format live there).

## When to Use
- Saша asks what a specific colleague's open tasks are / «что стоит перед <имя>» per Loop correspondence and context.
- Need that person's DM thread with Sasha, or their recent activity across channels.
- Load `mattermost-loop-api` only for auth/token/curl transport; this skill carries the per-person retrieval procedure.

## Auth & token
- Bearer PAT; token in `~/.hermes/profiles/default/.env` (`LOOP_TOKEN=...`). If absent there: `grep -r 'LOOP_TOKEN' ~/.hermes/cron/output/ | grep -v '.example' | head -5`.
- Use `curl` via `subprocess` with `--max-time`; `requests` hangs on loop.tutu.ru.
- Loop `since`/`create_at` are MILLISECONDS (13 digits). Team ID ТУТУ: `b1mrmr41dtrhbgk3a9qa7bxhqe`.

## Resolve the person to a Loop username
- `GET /users/autocomplete?name=<ФИО or part>` → `{users, out_of_channel}`, each with `username`/`first_name`/`last_name`/`id`. Reliable for fuzzy names.
- **contacts.enc login ≠ Loop username.** The contacts/login key is built from the email (`eperetjatkova`) and is often NOT the real Loop username (`peretyatkova`). Resolve via autocomplete on the ФИО, never trust the contacts.enc login.
- `GET /users/username/<name>` only works for the exact username; use autocomplete for everything else.

## Step 1 — a person's posts across the channels you are in
```python
POST /teams/{team_id}/posts/search    body: {"terms": "from:<loop_username>"}
```
- The body key is **`terms`, not `term`** — else HTTP 400 «Неверно или пропущено terms».
- `from:` matches the Loop username, not the display name.
- Response `{order, posts, matches}`; `order` is NOT chronological — sort yourself by `create_at` desc.
- Name channels of posts by looking up `channel_id` via `GET /channels/{id}` (`display_name`, `type`).

## Step 2 — the DM between Sasha and that person
You CANNOT enumerate another user's channels: `GET /users/{id}/teams/{team}/channels` → HTTP 403 `edit_other_users` (no permission).
- Do NOT use `POST /channels/direct` with two user_ids — it returns a broken payload error.
- The DM channel resolves BY NAME: `GET /teams/{team_id}/channels/name/{userA_id}__{userB_id}` — the two user ids joined with `__`. Only ONE concatenation order resolves; try both.
- **The `channel_id` field on search-result DM posts is the composite NAME (`{id}__{id}`), NOT a routable channel id.** Passing it to `GET /channels/{id}/posts` gives 404. First resolve the real 26-char id via the name endpoint, then `GET /channels/{real_id}/posts` returns the full two-way conversation.

## Read the result (context stitch)
For «что стоит перед X»: pull her posts (Step 1) + the DM thread (Step 2), sort chronologically, and cross-reference her active channels by name. Identify: open questions awaiting a decision (who holds budget, partner choice), running projects (project, stage, deadlines), and blocked items — then attach concrete deliverable verbs (подготовить дизайн эксперимента / спланировать / решить) rather than topics only.

## Read forwarded posts (quote/cross-ref)
When a DM post **forwards** another post (the person asks you to look at an upstream post → or «вот вопрос от <X>» + loop link):
- `GET /posts/{forwarded_id}` returns **403 `read_channel_content`** if the source channel isn't one you're in — a permissions boundary, not a transient error. Do not retry harder.
- The Forwarded/O. first occurrences the caller quoted inline are usually enough to answer. The DM body that forwards typically carries the original text (`>привет...`) — parse the DM post's own `message`, and only note the source link as an attribution to that channel.
- If the forwarded post's body is the actual ask and you can't read the source channel, answer from the quoted fragment and say explicitly you could not open the original, do not invent the rest.

## Identify a person referenced only by first name
When an interviewee/peer says «вопрос от Даши / кто-то ей написал» without a surname, do NOT guess who they mean and do NOT assert an identity. Enumerate candidates with `GET /users/autocomplete?name=<first name>` (and rolls the position + email) and either match against context (role on the project, who holds budget) or report the shortlist to the user and let them pick.

## Pitfalls
- **403 on another user's channel list** is a permissions boundary, not a bug — route around it via `from:` search, do not retry harder.
- **403 on a forwarded post** whose source channel you are not in — same boundary; use the quoted fragment in the forwarding DM post, don't loop.
- **DM posts 404 when you use the composite `channel_id` from search** — always route through the name→real-id resolution first.
- **`terms` key, not `term`** — the search endpoint rejects the wrong key with 400.
- **Search `order` is not time-sorted** — sort posts by `create_at` yourself.
- **Contacts login and Loop username diverge** — always autocomplete-resolve the loop username.
