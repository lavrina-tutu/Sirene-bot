# Резолв канала и участников Loop

## URL-токен канала ≠ channel_id

Ссылка `https://loop.tutu.ru/{team}/channels/{TOKEN}` содержит **имя канала**, а не id.
TOKEN — 32 символа; id канала — 26. Если передать TOKEN в `GET /api/v4/channels/{id}`,
получишь `api.context.invalid_url_param` («Неверный или пропущенный параметр channel_id»).

Резолв TOKEN → id через поиск по команде:
```bash
curl -s --max-time 20 -X POST \
  -H "Authorization: Bearer $LOOP_TOKEN" -H "Content-Type: application/json" \
  "https://loop.tutu.ru/api/v4/teams/b1mrmr41dtrhbgk3a9qa7bxhqe/channels/search" \
  -d '{"term":"<TOKEN>"}'
```
Ответ — **список** (не `{"channels": [...]}`): `[{id, name, display_name, type}, ...]`.
`name` = URL-токен, `display_name` = человекочитаемое название.

## Участники канала

```bash
curl -s --max-time 15 -H "Authorization: Bearer $LOOP_TOKEN" \
  "https://loop.tutu.ru/api/v4/channels/{channel_id}/members?per_page=200"
```
→ `[{user_id, ...}]`. Резолв user_id → человек (см. ниже).

## Резолв списка пользователей по id — через полную карту, НЕ `?ids=`

`GET /api/v4/users?ids=a,b,c,...` возвращает **частичный** список даже при верном наборе id
(батч на 50 → пришло 60 из 79). Не использовать для резолва участников.

Правильно — постранично собрать полную карту и проиндексировать по id:
```python
allu = {}
page = 0
while True:
    batch = api_curl(f"/api/v4/users?page={page}&per_page=200")
    if not batch:
        break
    for u in batch:
        allu[u["id"]] = u
    if len(batch) < 200:
        break
    page += 1
# затем: allu.get(uid) для каждого id из /channels/{id}/members
```
ФИО собирать как `f"{last_name} {first_name}"` (порядок «Фамилия Имя»).
Должность — `position` (может быть пустой → `-`).

## Токен для запросов

`LOOP_TOKEN` лежит в `~/.config/hermes/.env` (строка `LOOP_TOKEN=...`). Читать ручным
парсингом, а не `source`: в том же файле `TUTU_DOMAIN_PASSWORD` содержит символ `)`,
который ломает `source` (syntax error near unexpected token).
