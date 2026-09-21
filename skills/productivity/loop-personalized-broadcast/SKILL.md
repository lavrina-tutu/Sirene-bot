---
name: loop-personalized-broadcast
description: "Send personalized Loop DM messages to a list of recipients."
version: 1.0.1
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [loop, broadcast, рассылка, dm, tutu]
    related_skills: [mattermost-loop-api, tutu-confluence-jira]
---

# Loop Personalized Broadcast

Send personalized DM messages from Sasha via Loop to a list of recipients, typically built from a Confluence table row: `Задача JIRA` / `Подразделение` / `Исполнитель`.

**Bulk broadcasts (10+ recipients):** do NOT also send to the Loop channel itself (никому Loop); do NOT include external attendees. Apply default venue «Платформа - Переговорка» and verbatim subject (same as bulk meeting defaults in `exchange-meeting`).

## Workflow (read-only plan first, then send on explicit OK)

1. **Restate the message template and substitutions.** For each recipient substitute:
   - `<Исполнитель>` → greeting **by first name exactly as written in the source list** (NOT the Loop full name). Format: `Привет, <Имя>!`
   - `<Подразделение(в дательном падеже)>` → department in dative case (e.g. `выдача`→`по выдаче`, `чекаут`→`по чекауту`, `жд`→`по ЖД`, `автобусы`→`по автобусам`, `главная страница`→`по главной странице`, `электрички`→`по электричкам`, `tutuid`→`по tutuid`, `мессенджеры`→`по мессенджерам`).
   - `<Задача JIRA>` → clickable link `[KEY](https://hq.tutu.ru/browse/KEY)`.
2. **Output the plan + final message text** and wait; do NOT send until Sasha says `отправляй` / `да`.
3. Handle exclusions if Sasha names them (e.g. "Криворотову и Некипелову не отправлять").

## Resolve recipients in Loop

Token: `WorkVault/Inbox/Loop Hermes token.md` — Bearer PAT only (no login/password). Always `curl` via subprocess, never `requests`/`httpx` (they hang on loop.tutu.ru).

```python
import subprocess, json
TOKEN = "..."  # Access Token from the md file
def autocomplete(q):
    r = subprocess.run(["curl","-s","--max-time","15","-H",f"Authorization: Bearer {TOKEN}",
        "--get","--data-urlencode",f"name={q}","https://loop.tutu.ru/api/v4/users/autocomplete"],
        capture_output=True,text=True)
    return json.loads(r.stdout or "{}")
d = autocomplete("<surname>")
users = (d.get('users') or []) + (d.get('out_of_channel') or [])
# pick the one matching the full name; keep user['id'], user['username'], user['first_name']/['last_name']
```

## Create DM channel

`POST /api/v4/channels/direct` — body is a **JSON array of user ids** (`[my_id, other_id]`), NOT an object. Returned `id` is the DM channel.

## Send message

For DM channels `POST /api/v4/channels/{id}/posts` returns `404`; use `POST /api/v4/posts` with body `{"channel_id": CH, "message": msg}`.

```python
payload = json.dumps({"channel_id": ch, "message": msg})
r = subprocess.run(["curl","-s","--max-time","15","-X","POST",
    "-H",f"Authorization: Bearer {TOKEN}","-H","Content-Type: application/json",
    "-d",payload,"https://loop.tutu.ru/api/v4/posts"], capture_output=True,text=True)
d = json.loads(r.stdout)          # d['id'] = post_id
link = f"https://loop.tutu.ru/tutu/pl/{d['id']}"
```

## Verification & report

After sending report a table of recipients with their post links. Verify via the returned `post_id` (check it doesn't start with `api.`). Send a link for every message.

## Pitfalls

- **Greeting name comes from the source list, NOT Loop resolution.** Sasha corrected this (17.08.2026): list has short names (`Саша`, `Оля`, `Настя`, `Миша`, `Маша`, `Аня`) while Loop has full (`Александр`, `Ольга`, `Анастасия`, `Михаил`, `Мария`, `Анна`). Always use the list form for `Привет, X!`.
- **`vorobeva` vs `vorobyeva`**: Воробьева Анна's Loop username is `vorobeva` (no 'й'). Query doesn't match on `vorobyeva`. Try alternative transcriptions when a surname isn't found.
- **`/channels/direct` expects a JSON array**, not `{"user_ids":[...]}` → else `api.payload.parse.error`.
- **DM post via `/channels/{id}/posts` → 404**; use `/posts` with `channel_id` instead.
- **Multiple Loop names for one surname** (e.g. many `Иванов*`): pick by full name; if ambiguity, surface to Sasha.
- Always preflight as read-only, get explicit send confirmation. This is a write/prod action.
