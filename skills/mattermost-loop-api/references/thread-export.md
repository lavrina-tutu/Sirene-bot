# Выгрузка треда Loop по пермалинку (полный текст + файлы)

Задача Саши: «выгрузи тред/топик из Loop // забери файлы из Loop по ссылке https://loop.tutu.ru/tutu/pl/<id>». Проверено живыми запросами 19.10.2026.

## 1. Корневой пост по пермалинку
`GET /api/v4/posts/{post_id}` → `channel_id`, `root_id` (у корня пуст), `reply_count`, `metadata.files`.

## 2. Собрать весь тред
`GET /api/v4/threads/{team}/{channel}/{root}` — **НЕ существует**, возвращает 404. Правильно — посты канала с фильтром `root_id`:
```
GET /api/v4/channels/{channel_id}/posts?root_id={root_id}&per_page=200
```
- Ответ: `order` (list id) + `posts` (dict id→post) + `prev_post_id`/`next_post_id`.
- Тред длиннее 200 постов → пагинация **назад** по `before={prev_post_id}`, пока `prev_post_id` не опустеет. Мерджить `posts` по id (dedup).
- Тред = посты с `root_id == главный_root` ИЛИ `id == главный_root`. В том же канале бывают другие корни (это другие темы) — фильтровать строго по `root_id`, не брать «всё из канала».
- Пропускать системные (`type != ''`) и удалённые (`delete_at != 0`).
- Сортировать по `create_at`.

## 3. Файлы
- `GET /api/v4/files/{file_id}` → **фактические байты файла** (не JSON!). Отдаёт `PK..`/xlsx/zip/png. Сохранять как `{file_id}.{extension}`. Валидировать размер против `metadata.files[].size`.
- `GET /api/v4/files/{file_id}/info` → метаданные JSON.
- `GET /api/v4/files/{file_id}/link` → **403 «Публичные ссылки отключены»** — не использовать.
- Список файлов каждого поста — в `metadata.files[]` (id, name, extension, size).

## 4. Авторы для подписи
`GET /api/v4/users/{user_id}` → `username` + `first_name` `last_name`.

## 5. Доставка Саше (предпочтение)
- **Один MD** с полным текстом треда: каждый пост `### [ДД.ММ.ГГГГ ЧЧ:ММ MSK] ФИО` + текст + список файлов.
- **Один zip** со всеми файлами треда + MD внутри. Одноимённые вложения (несколько `Эталонные_кейсы_JIRA.xlsx`, `image.png`) разводить суффиксом `_(N)` перед расширением — иначе коллизии в архиве.
- Оба файла — как `MEDIA:/путь` в топик Telegram, откуда пришёл запрос.

## Рабочий каркас (curl через subprocess, `requests` зависает)
```python
import subprocess, json
TOKEN = os.environ['LOOP_TOKEN']
def api(path, params=None):
    url = f"https://loop.tutu.ru/api/v4/{path}"
    if params: url += "?" + "&".join(f"{k}={v}" for k,v in params.items())
    return json.loads(subprocess.run(["curl","-s","--max-time","30","-H",f"Authorization: Bearer {TOKEN}",url],capture_output=True,text=True).stdout)

def api_bytes(path):
    url = f"https://loop.tutu.ru/api/v4/{path}"
    return subprocess.run(["curl","-s","--max-time","30","-H",f"Authorization: Bearer {TOKEN}",url],capture_output=True).stdout

root = api(f"posts/{PID}")              # channel_id, root_id
posts = {}
prev = None
while True:
    p = {**{"per_page":200, "root_id": root['id']}, **({"before": prev} if prev else {})}
    pg = api(f"channels/{root['channel_id']}/posts", p)
    posts.update(pg['posts'])
    prev = pg.get('prev_post_id') or None
    if not prev: break
thread = [x for x in posts.values() if x['id']==root['id'] or x.get('root_id')==root['id']]
thread.sort(key=lambda x: x['create_at'])
```
