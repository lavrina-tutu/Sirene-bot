# Чтение полной переписки DM с конкретным пользователем

Рецепт для запроса «посмотри переписку с <ФИО> за <период>» — вытащить весь личный диалог с одним человеком из Loop.

## Шаги

1. **Найди пользователя** — `GET /api/v4/users/autocomplete?name=<часть-имени>`. Возьми `id` и `username`. (автокомплит, не `?term=` — тот ненадёжен).
2. **Получи DM-канал** — `POST /api/v4/channels/direct` с JSON-массивом из двух id: `["<my_id>", "<other_id>"]`. Возвращает существующий канал (type=`D`), не создаёт новый. Мой id — из `GET /api/v4/users/me`.
3. **Вытяни все посты** — `GET /api/v4/channels/{channel_id}/posts?per_page=500`. Ответ содержит `posts` (map id→post) и `order` (список id в хронологическом порядке). Сортируй вывод по `order`, не по `create_at` вручную.
   - Для больших каналов (>200 постов) иди назад страницами: повторяй запрос с `before=order[0]` предыдущего ответа.
   - DM Саши с одним человеком почти всегда <200 постов — один запрос `per_page=500` даёт всю историю.
4. **Резолв авторов** — для каждого уникального `user_id` сделан `GET /api/v4/users/{user_id}` → `username` (кешируй в dict).
5. **Фильтруй по дате** — `datetime.fromtimestamp(post["create_at"]/1000, tz=MSK)`; `create_at` в миллисекундах.

## Реализация api-хелпера (curl, не requests)

```python
import subprocess, json

def api(path, method="GET", body=None):
    cmd = ["curl", "-s", "--max-time", "15", "-X", method,
           "-H", f"Authorization: Bearer {TOKEN}", "https://loop.tutu.ru" + path]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout)

me = api("/api/v4/users/me")
ch = api("/api/v4/channels/direct", "POST", [me["id"], other_id])
data = api(f"/api/v4/channels/{ch['id']}/posts?per_page=500")
for pid in data["order"]:
    p = data["posts"][pid]
    ...
```

## Pitfalls

- **Токен для интерактивного чтения** — парси его прямо из файла в Python, не через `grep | cut` в шелле (спецсимволы ломают подстановку):
  ```python
  tok = next(line.split('=', 1)[1].strip() for line in open('/home/tkachenkoav/.hermes/profiles/default/.env') if line.startswith('LOOP_TOKEN='))
  ```
- **Не дублируй `/api/v4` в пути.** Если хелпер склеивает `base + path` и base уже `https://loop.tutu.ru/api/v4` — path бери БЕЗ префикса, иначе задвоишь и получишь пустой/404 ответ. Единый способ: base = `https://loop.tutu.ru`, path всегда с `/api/v4/...`.
- **Фильтруй системные и удалённые посты** — `post["type"] != ''` (join/leave и пр.) и `post["delete_at"] != 0` пропускать.
- **Сортируй по `order`**, он уже хронологический; `create_at` используй только для фильтра по годам.

## Связанный навык

Этот рецепт — часть `mattermost-loop-api`; про формат постов, `mention_count`, дайджест/срочный мониторинг см. основной SKILL.md.
