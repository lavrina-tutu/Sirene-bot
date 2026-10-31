# Loop DM: раздача персональных файлов (прочитать поток → скачать → резолв получателей)

Паттерн «из переписки с ботом забрать по одному файлу на пользователя и подготовить персональную рассылку». Проверено на живой ветке «Сбор кейсов Mattermost за август» (бот `hermes-test-users`): 43 файла, все скачаны, все получатели разрешены.

## 1. Найти DM-канал с другим пользователем/ботом

`POST /api/v4/channels/direct` принимает **JSON-массив id** `[my_id, other_id]` (не объект с `user_ids`). Резолв контрагента по username через `autocomplete`:

```python
import subprocess, json, os
tok = os.environ['LOOP_TOKEN']  # Bearer PAT
B = 'https://loop.tutu.ru/api/v4'

def curl(path, data=None):
    cmd = ['curl','-s','--max-time','15','-H',f'Authorization: Bearer {tok}']
    if data: cmd += ['-X','POST','-H','Content-Type: application/json','-d',json.dumps(data)]
    cmd.append(f'{B}{path}')
    return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)

me = curl('/users/me')
# autocomplete: users + out_of_channel (боты попадают в out_of_channel)
cc = curl('/users/autocomplete?')  # --get --data-urlencode name=...
other = (cc.get('users') or []) + (cc.get('out_of_channel') or [])
other = next(u for u in other if u['username']=='hermes-test-users')
ch = curl('/channels/direct', [me['id'], other['id']])   # → id == DM-канал
```

## 2. Собрать посты канала (включить граничный пост)

`GET /channels/{id}/posts?since={ms}` возвращает только посты **строго после** `since` (и может вернуть старый root-пост треда). **Не полагайся на `since` для включения самой границы** — пагинируй всю историю (`page=0..N, per_page=200`) и фильтруй в коде по `create_at >= REF_MS`. Это единственный надёжный способ включить «пост-ориентир» и не потерять пограничные файлы.

```python
posts = {}
p = 0
while True:
    data = curl(f'/channels/{chuid}/posts?page={p}&per_page=200')
    seg = data.get('posts', {})
    if not seg: break
    posts.update(seg); p += 1
# фильтр: delete_at==0, create_at >= REF_MS
```

## 3. Вложения из метаданных поста

У поста в `metadata.files` лежит список: `id`, `name`, `extension`, `size`, `mime_type`. Скачивание — `GET /api/v4/files/{file_id}`, сырые байты:

```python
r = subprocess.run(['curl','-s','--max-time','20','-H',f'Authorization: Bearer {tok}',
    f'{B}/files/{fid}'], capture_output=True)
open(f'/tmp/dl/{fname}','wb').write(r.stdout)
# успех: len(stdout) > 1000 и не похоже на json-ошибку
```

## 4. Эксцель выгрузки (паттерн case-коллектора)

Файл `<username>_cases.xlsx`: одна вкладка «Кейсы», строка-заголовок, `пользователь` в колонке 1, `решённость` в колонке 6. Число кейсов = число строк данных (считай через `openpyxl`, а не `ws.max_row` — могут быть пустые хвостовые строки).

## 5. Резолв получателя из имени файла

Имя файла = Loop username. `autocomplete(name)` → выбери кандидата с `username` == точному имени файла (не первый попавшийся по подстроке). Проверяй `delete_at == 0` (деактивированные). Если в списке есть сам Саша (`tkachenkoav`) — это, скорее всего, не целевой получатель, а собственный файл; вынеси на подтверждение.

## 6. Отчёт перед рассылкой (никогда не слать без подтверждения)

До «выполни рассылку» отдай: (1) понимание задачи, (2) таблицу получателей (username → ФИО из Loop → число кейсов), (3) статус «файл найден/не найден» и факт резолва получателя. Сверь число файлов с количеством имён — расхождение сигналит о потерянном пограничном посте.

Питфолл: отправка файла-вложения в пост Loop (в отличии от чистого текста через `/posts` с `channel_id`) в этой сессии НЕ проверялась — не декларируй «переслать смогу» как готовую механику, пока не подтверждена на живом посте.
