# Отправка DM в Loop (Mattermost API v4) — проверено 17.08.2026

Полный живой флоу отправки личного сообщения одному пользователю: резолв → DM-канал → пост → ссылка.

## Шаг 1 — резолв пользователя (autocomplete)
```bash
curl -s --max-time 15 -H "Authorization: Bearer $LOOP_TOKEN" \
  --get --data-urlencode "name=krivorotov" "https://loop.tutu.ru/api/v4/users/autocomplete"
```
Берём `users[0].{id, username, first_name, last_name}`. Если ФИО задано как «Фамилия Имя» — искать по фамилии, сверять `first_name`/`last_name`.

## Шаг 2 — создать DM-канал
⚠️ **BODY — JSON-МАССИВ строк user_id, НЕ объект:**
```bash
MY="<id из /users/me>"; OTHER="<id получателя>"
curl -s --max-time 15 -X POST -H "Authorization: Bearer $LOOP_TOKEN" \
  -H "Content-Type: application/json" \
  -d "[\"$MY\",\"$OTHER\"]" "https://loop.tutu.ru/api/v4/channels/direct"
# → {"id":"<channel_id>","type":"D",...}
```
**Питфолл:** `{"user_ids":[...]}` (объект) → `api.payload.parse.error`, `json: cannot unmarshal object into Go value of type []string` (400).

## Шаг 3 — отправить пост
⚠️ Для DM-канала (`type=D`, `team_id=""`) `POST /api/v4/channels/{channel_id}/posts` возвращает **404** (`api.context.404.app_error`). Рабочий путь — глобальный `POST /api/v4/posts`:
```python
import subprocess, json
payload = json.dumps({"channel_id": "<channel_id>", "message": "текст"})
r = subprocess.run(["curl","-s","--max-time","15","-X","POST",
  "-H",f"Authorization: Bearer {TOKEN}","-H","Content-Type: application/json",
  "-d",payload,"https://loop.tutu.ru/api/v4/posts"], capture_output=True, text=True)
post = json.loads(r.stdout)
# post['id'] = <post_id>
```
Ссылка на отправленное: `https://loop.tutu.ru/tutu/pl/{post_id}`.

## Форматирование текста
Loop (Mattermost) поддерживает Markdown: JIRA-ссылка в теле — `[ADD-620619](https://hq.tutu.ru/browse/ADD-620619)`, пустые строки между абзацами. Отправлять через `curl` в Python (`requests` на loop.tutu.ru зависает — см. раздел «HTTP-клиент» в SKILL.md).
