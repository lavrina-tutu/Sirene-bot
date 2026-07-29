---
name: mattermost-loop-api
description: "Работа с Loop (Mattermost ТУТУ, loop.tutu.ru) через API v4 — аутентификация, получение пользователей, паттерн синка контактов. Триггеры: loop api, mattermost api, MoveFromLoop, синк Loop контактов."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
tags: [loop, mattermost, api, contacts, tutu]
---

# Mattermost / Loop API

Loop — корпоративный мессенджер ТУТУ на базе Mattermost (loop.tutu.ru).

## Аутентификация

**Только Personal Access Token (Bearer) — логин/пароль не использовать.**

Токен хранится в `WorkVault/Inbox/Loop Hermes token.md`:
- Token ID: `u3sbn7obibrijj5ppdmiuj3r7r`
- Access Token: `ujde9bzqepb6t8hraym6wz73ir`

В `.env` инструмента: `LOOP_TOKEN=<access_token>`

```python
headers = {"Authorization": f"Bearer {LOOP_TOKEN}"}
```

## Проверка подключения

```bash
curl -s -H "Authorization: Bearer $LOOP_TOKEN" \
  "https://loop.tutu.ru/api/v4/users/me" | python3 -m json.tool
```

Возвращает: `username`, `email`, `id`, `first_name`, `last_name` текущего пользователя.

## Получение пользователей

```python
import requests

def get_all_users(token, base_url="https://loop.tutu.ru"):
    headers = {"Authorization": f"Bearer {token}"}
    page, per_page = 0, 200
    while True:
        r = requests.get(
            f"{base_url}/api/v4/users",
            headers=headers,
            params={"per_page": per_page, "page": page}
        )
        users = r.json()
        if not users:
            break
        yield from users
        page += 1
```

## Поля объекта пользователя

`id`, `username`, `email`, `first_name`, `last_name`, `nickname`, `position`,
`roles`, `locale`, `delete_at`, `create_at`, `update_at`

**Нет явного поля `is_bot`** — детектировать эвристикой.

## Фильтрация (паттерн MoveFromLoop)

```python
def is_active_human(user):
    # Деактивированные
    if user.get("delete_at", 0) > 0:
        return False
    # Боты по роли или email
    roles = user.get("roles", "")
    if "system_bot" in roles:
        return False
    email = user.get("email", "")
    if email.endswith("-bot@zulip.tutu.ru") or email.endswith("bot@loop.tutu.ru"):
        return False
    return True
```

## Маппинг в contacts.enc

```python
def user_to_contact(user):
    first = user.get("first_name", "").strip()
    last = user.get("last_name", "").strip()
    # Порядок «Фамилия Имя» — как в MoveFromZulip
    fio = f"{last} {first}".strip() if last or first else user.get("nickname", "")
    email = user.get("email", "").strip()
    login = email.split("@")[0].lower() if "@" in email else user.get("username", "")
    return {
        "login": login,
        "fio": fio,
        "email": email,
        "position": user.get("position") or None,  # None если пустой — не затирать
    }
```

**Правила записи в contacts.enc:**
- Дополнять, не перезатирать — если поле уже заполнено другим коннектором (Zulip, Exchange), не трогать
- `mattermost_id` не писать (решение 23.07.2026)
- `position` писать только если непустой
- Дедупликация по `login` (из email) — единый ключ с MoveFromZulip

## Крон MoveFromLoop (синк контактов)

- Schedule: `30 3 * * 0` (воскресенье 03:30, аналогично MoveFromZulip)
- no_agent: true, LLM не используется, токены = 0
- deliver: local
- ТЗ: `WorkVault/Hermes-Backlog/TZ/MoveFromLoop/MoveFromLoop_TZ.md` v0.4.0

**Результат первого реального синка (24.07.2026):**
- Всего в Loop: 2333 пользователей
- Добавлено новых: 88
- Обновлено существующих: 1132
- Пропущено ботов: 89, деактивированных: 1024

## Мониторинг сообщений (итерация 2, в разработке)

Помимо синка контактов — планируется чтение сообщений из Loop:

**Два режима:**
- **Дайджест** (раз в час) — сводка новых сообщений по подпискам → топик Messages в Telegram
- **Срочный** (каждые 2-3 мин) — DM + @упоминания + @all → немедленно в Telegram

**Топик Messages в Telegram:** создан 24.07.2026, thread_id = **6556**, группа `-1004300127777`
deliver: `telegram:-1004300127777:6556`

**Что читать:**
- DM (личные сообщения)
- @упоминания пользователя
- @all в отслеживаемых каналах
- Ключевые слова в выбранных каналах (гибко настраиваемые правила)

**Управление правилами:** YAML-файл + команды через Сирень («добавь канал #devops», «следи за словом бюджет»)

**Ответы на сообщения** — из топика Messages в Telegram (итерация 2).

**API-эндпоинты для мониторинга (проверено живыми запросами 24.07.2026):**

```bash
# ✅ Каналы с непрочитанными упоминаниями — КЛЮЧЕВОЙ эндпоинт
# Аналог вкладки «Упоминания и реакции» в Loop UI
GET /api/v4/users/me/teams/{team_id}/channels/members?per_page=200&page=N
# Ответ: [{channel_id, mention_count, last_update_at, urgent_mention_count, ...}]
# Фильтр: mention_count > 0 — покрывает @упоминания, @all, @channel, @here и DM

# ✅ Посты канала с момента времени (since в МИЛЛИСЕКУНДАХ, 13 цифр!)
GET /api/v4/channels/{channel_id}/posts?since={unix_ms}&per_page=200

# ✅ Инфо о канале (для display_name и type)
GET /api/v4/channels/{channel_id}

# ✅ Сохранённые посты (звёздочки) — НЕ упоминания
GET /api/v4/users/me/posts/flagged?per_page=200

# ❌ НЕ существует — возвращает 404
GET /api/v4/users/me/mentions
GET /api/v4/notifications
GET /api/v4/users/me/posts
```

**Статистика каналов Саши (24.07.2026):**
- Всего каналов: **3327** (O=2576 открытых, D=229 DM, P=516 приватных, G=6 групп)
- Team ID ТУТУ: `b1mrmr41dtrhbgk3a9qa7bxhqe`, team name: `tutu`

**Архитектура мониторинга (принятое решение):**

Вместо опроса всех 3327 каналов — один запрос `/channels/members` → `mention_count > 0`:
- `mention_count` покрывает DM, @упоминания, @all/@channel/@here — всё в одном
- DM (`type=D`) инкрементируют `mention_count` автоматически, без @username
- Групповые DM (`type=G`) тоже покрыты
- Отдельный проход по DM-каналам **не нужен**

**Единственный краевой случай:** если Саша прочитал сообщение в мобилке до прогона крона (≤3 мин) — `mention_count` уже 0, пропустим. Митигация: отдельный проход по `last_update_at > since_ms` в итерации 1.5.

**Срочный режим (каждые 3 мин):**
1. `GET /channels/members` → `mention_count > 0`
2. Для каждого: `GET /channels/{id}/posts?since={urgent_last_ts_ms}`
3. Фильтр: `user_id` ∈ `urgent_contacts` (список username → резолв через contacts.enc)
4. `no_agent=true`, stdout = текст в TG, пустой stdout = SILENT

**Дайджест (раз в час, 8:00-20:00 пн-пт):**
1. `GET /channels/members` → `mention_count > 0` → все упоминания
2. `watch_channels` из конфига → посты → фильтр по `keywords`
3. Объединить хронологически → один пост в Messages
4. `no_agent=true`

**Конфиг `loop_rules.yaml`:**
```yaml
my_username: tkachenkoav
team_id: b1mrmr41dtrhbgk3a9qa7bxhqe
urgent_contacts: []   # username в Loop
watch_channels: []    # имена каналов
keywords: []          # ключевые слова (регистронезависимо)
```

## Саммари по каналу (итерация 2 архивация, в разработке)

Помимо дайджеста — ежедневное саммари переписки канала через Haiku:
- **Когда:** раз в день, только если были сообщения (иначе не писать)
- **Куда:** `WorkVault/Entities/<slug>/Messages/YYYY-MM-DD.md` — файл на день
- **Содержание:** что обсуждали + проблемы + риски + решения
- **Матчинг канал→сущность:** через Сирень («подключи #pm-team к Trisigma»), slug резолвится через entities.json
- **Если slug не найден:** Сирень спрашивает подтверждения перед созданием новой папки

**Важно:** `WorkVault/Entities/<slug>/` — новая единая структура (миграция из Projects/ + People/). ТЗ: `WorkVault/Hermes-Backlog/TZ/EntitiesMigration/EntitiesMigration_TZ.md`.

## Формат ссылки на сообщение

Подтверждён на живом посте (24.07.2026):

```
https://loop.tutu.ru/{team}/pl/{post_id}
```

Пример: `https://loop.tutu.ru/tutu/pl/hpu6jmh7w7g8m8ht1hcy8xuuqw`

- `team` = `tutu` (корп. аккаунт ТУТУ)
- `pl/{post_id}` — прямая ссылка на конкретный пост
- НЕ `channels/{channel_name}?message={id}` — этот формат неверен

## Реализация MoveFromLoop v2 — мониторинг (24.07.2026)

Код: `USERTOOLS/MoveFromLoop/` — полностью реализован, 96/96 тестов.

**Структура новых файлов:**
```
movefromloop/
  state.py              # watermark.json + seen_ids TTL 48ч + user/channel cache TTL 24ч
  loop_api.py           # LoopClient: me, channel_members, channel_info, posts_since, users_by_ids
  channel_resolver.py   # резолв channel_name → channel_id
  mentions_fetcher.py   # fetch_mentions (mention_count>0), fetch_watched (watch_channels)
  urgency_checker.py    # is_urgent, resolve_urgent_user_ids (через API + state cache)
  keyword_checker.py    # matches_keywords (регистронезависимо)
  rules.py              # load_rules/save_rules через ruamel.yaml
  formatter.py          # format_post, format_urgent, format_digest
  urgent.py             # run_urgent — алгоритм срочного режима
  digest.py             # run_digest — алгоритм дайджеста
scripts/
  urgent_check.py       # точка входа крона срочных (no_agent=true)
  digest.py             # точка входа крона дайджеста (no_agent=true)
loop_rules.yaml         # конфиг (urgent_contacts, watch_channels, keywords)
state/watermark.json    # персистентный state
```

**Кроны (созданы 24.07.2026):**
- Срочный: job `f61b26cbbdf5`, `*/3 * * * *`, no_agent=true, deliver=`telegram:-1004300127777:6556`
- Дайджест: job `2865cc674493`, `0 8-20 * * 1-5`, no_agent=true, deliver=`telegram:-1004300127777:6556`

**Формат уведомления (финальный, утверждён 29.07.2026):**
```
📅 29 июл 2026, 14:35 МСК
Первая непустая строка сообщения
🔗 https://loop.tutu.ru/tutu/pl/{post_id}
#{channel_name} · @{username}
```
- Дата и время МСК — ПЕРВАЯ строка каждой карточки
- Собственные сообщения (`my_username: tkachenkoav`) фильтруются в `digest.py` и `urgent.py` после резолва авторов
- Срочный: несколько сообщений разделяются `───`
- Дайджест: заголовок `📬 Loop · N сообщ.` + все упоминания за период
- Пустой stdout = SILENT (ничего не доставляется)

**Управление `urgent_contacts`:** добавлять username из Loop. Пример: `gladkikh`, `malyy`, `fedotovav`, `klimovskiyrb`. Резолв через `GET /api/v4/users/username/{name}` с кешем в state на 24ч.

## Реализация MoveFromLoop v1 (24.07.2026)

Код: `USERTOOLS/MoveFromLoop/` — полностью реализован и протестирован.

**Результаты smoke-test:**
- Всего пользователей в Loop: **2333**
- После фильтрации: **1220** активных людей
- Пропущено: 89 ботов, 1024 деактивированных

**Структура:**
```
USERTOOLS/MoveFromLoop/
  movefromloop/fetcher.py, filters.py, mapper.py, sync.py
  scripts/sync_contacts.py
  tests/  (58 тестов, все зелёные)
  venv_linux/
```

**Запуск синка:**
```bash
cd ~/USERTOOLS/MoveFromLoop
source venv_linux/bin/activate
python -m movefromloop  # или python scripts/sync_contacts.py
```

## ContactStore API — питфоллы

```python
# ПРАВИЛЬНО — path к файлу, не к директории
store = ContactStore(Path("/home/tkachenkoav/WorkVault/Contacts/contacts.enc"), KEY)

# НЕПРАВИЛЬНО — IsADirectoryError
store = ContactStore(Path("/home/tkachenkoav/WorkVault/Contacts"), KEY)

# find_contacts возвращает Dict[login, record], не list
results = store.find_contacts("ткаченко")
for login, record in results.items():
    print(login, record.get("fio"))

# Нет метода load() — данные читаются при каждом вызове find_contacts/read
# Нет метода save() — write() принимает полный dict

# Запуск sync — нужны все переменные окружения:
CONTACTS_ENCRYPTION_KEY=... CONTACTS_PATH=.../contacts.enc \
  LOOP_TOKEN=... LOOP_URL=https://loop.tutu.ru \
  PYTHONPATH=/home/tkachenkoav/USERTOOLS/MoveFromLoop \
  python3 scripts/sync_contacts.py
```

## HTTP-клиент: используй curl через subprocess, не requests

`requests` (и `httpx`) зависают на loop.tutu.ru при вызове из Python — вероятно, проблема с SSL/SNI или прокси-конфигурацией на сервере. Вместо этого:

```python
import subprocess, json

def api_curl(path, params=None, token=TOKEN, base_url=BASE_URL):
    url = f"{base_url}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    result = subprocess.run(
        ["curl", "-s", "--max-time", "10",
         "-H", f"Authorization: Bearer {token}", url],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
```

`curl` работает штатно — проверено 24.07.2026. Используй `--max-time 10` (или 15 для тяжёлых запросов). Не переключайся на `requests` без отдельной проверки.

## Дайджест упоминаний: паттерн скрипта (проверено 24.07.2026)

```python
# 1. Получаем my_user_id
me = api_curl("/api/v4/users/me")
my_user_id = me["id"]

# 2. Каналы с mention_count > 0 (постранично)
channels_with_mentions = []
page = 0
while True:
    members = api_curl(
        f"/api/v4/users/me/teams/{TEAM_ID}/channels/members",
        {"per_page": 200, "page": page}
    )
    if not isinstance(members, list) or not members:
        break
    for m in members:
        if (m.get("mention_count", 0) or 0) > 0:
            channels_with_mentions.append(m["channel_id"])
    if len(members) < 200:
        break
    page += 1

# 3. Посты из каждого канала
all_posts = []
for ch_id in channels_with_mentions:
    data = api_curl(f"/api/v4/channels/{ch_id}/posts",
                    {"since": SINCE_MS, "per_page": 200})
    for post_id, post in data.get("posts", {}).items():
        if (post.get("type", "") == "" and
                post.get("delete_at", 0) == 0 and
                post.get("create_at", 0) > SINCE_MS):
            post["_channel_id"] = ch_id
            all_posts.append(post)

all_posts.sort(key=lambda p: p["create_at"])

# 4. Формат дайджеста
if not all_posts:
    print("[SILENT]")
else:
    for post in all_posts:
        username = get_username(post["user_id"])
        ch = get_channel(post["_channel_id"])
        dt = datetime.fromtimestamp(post["create_at"] / 1000, tz=MSK)
        first_line = next(
            (l for l in post["message"].splitlines() if l.strip()), ""
        )
        post_id = post["id"]
        print(f"@{username} [{dt:%H:%M}]:")
        print(first_line)
        print(f"🔗 https://loop.tutu.ru/tutu/pl/{post_id} | #{ch['name']} | @{username}")
```

## Формат уведомлений (финальный, утверждён 24.07.2026)

**Срочное:**
```
⚡ Срочное от @{username}
{первая строка текста} 
🔗 https://loop.tutu.ru/tutu/pl/{post_id} | #{channel_name} | @{username}
```

**Дайджест:**
```
📬 Loop — дайджест {HH:MM}

@{username} [{HH:MM}]:
{первая строка текста}
🔗 https://loop.tutu.ru/tutu/pl/{post_id} | #{channel_name} | @{username}
```

- Время сообщения в МСК (UTC+3), формат `HH:MM` — обязательно в обоих режимах
- **Формат времени:** Loop уведомления — `[HH:MM]` МСК. Exchange уведомления — `[DD.MM HH:MM]` МСК (дата обязательна, утверждено 24.07.2026).
- Несколько срочных в одном тике: разделитель `───`
- Пустой stdout = SILENT (ничего не доставляется в TG)
- Тег отправителя `@username` — из Loop, не из contacts.enc

## Urgent contacts (текущий список, 24.07.2026)

```yaml
urgent_contacts:
  - gladkikh      # Гладких Юрий
  - malyy         # Малый Денис
  - fedotovav     # Федотов Андрей
  - klimovskiyrb  # Климовский Руслан
  - aralov        # Аралов Александр
  - korneev       # Корнеев Александр (добавлен 24.07.2026)
```

## Поиск пользователя по имени

`GET /api/v4/users?term=X` ненадёжен — возвращает алфавитный список, совпадения по имени случайны.
Использовать autocomplete:

```python
r = requests.get(
    f"{base_url}/api/v4/users/autocomplete",
    params={"name": "kornee"},
    headers={"Authorization": f"Bearer {token}"}
)
for u in (r.json().get('users') or []) + (r.json().get('out_of_channel') or []):
    print(u['username'], u['first_name'], u['last_name'])
```

**LOOP_TOKEN не в .env** — искать в логах кронов:
```bash
grep -r 'LOOP_TOKEN' ~/.hermes/cron/output/ | grep -v '.example' | head -5
```

## Формат уведомлений — финальные правила (25.07.2026)

Время в уведомлениях:
- **Loop**: `[HH:MM]` МСК — без даты (сообщения приходят часто, дата очевидна)
- **Exchange**: `[DD.MM HH:MM]` МСК — с датой (письма реже, дата важна)

Теги Exchange (финальные, изменены 24.07.2026):
- `(приватное)` — ты единственный в `To:`
- `(личное)` — ты в `To:` среди других получателей
- `(инф)` — ты в `CC:`

Теги **не применяются** к Loop-уведомлениям — там нет `To:/CC:`.

## Pitfalls

- **`per_page=200` в `/channels/members` игнорируется** — API возвращает все каналы (~3344) одним ответом. Цикл пагинации: `if len(batch) != per_page: break` — корректно обработает и этот случай, но реально страниц не будет. Не добавлять sleep/retry при получении «всего» в первом ответе.
- **`since` в API — МИЛЛИСЕКУНДЫ, не секунды.** `create_at` = 13-значное число (напр. `1780408539561`). Передача секунд → API вернёт всю историю с 1970 года.
- **Проверяй год в timestamp перед использованием.** Если пользователь передаёт `since_ms` числом, всегда верифицируй: `datetime.fromtimestamp(since_ms/1000)`. Пример ловушки: `1753354980000` → **2025**-07-24, а не 2026. Правильный ts для 2026-07-24 13:03 МСК = `1784887380000`. Число 2026 > 2025: разница ~1 год = ~31.5 млрд мс. Шаблон проверки:
  ```python
  since_dt = datetime.fromtimestamp(SINCE_MS / 1000, tz=MSK)
  assert since_dt.year == 2026, f"Неверный год: {since_dt}"
  ```
- **`requests` зависает на loop.tutu.ru** — использовать `curl` через `subprocess`. См. раздел выше.
- **Hermes no_agent скрипты: путь к модулям.** Скрипты копируются в `~/.hermes/scripts/` (только оттуда Hermes их запускает). `Path(__file__).parent.parent` даёт `~/.hermes/`, а не `USERTOOLS/<project>/` — `ModuleNotFoundError`. Фикс — хардкодить абсолютный путь и грузить `.env` явно:
  ```python
  _ROOT = Path("/home/tkachenkoav/USERTOOLS/MoveFromLoop")
  sys.path.insert(0, str(_ROOT))
  from dotenv import load_dotenv
  load_dotenv(Path("/home/tkachenkoav/.hermes/profiles/anthropic/.env"))
  ```
  Без `load_dotenv` — `401 Unauthorized` (LOOP_TOKEN не передаётся в env крона).
- **Дедупликация срочный↔дайджест через `seen_ids`:** без дедупликации письмо/пост от urgent-контакта уйдёт дважды — сначала срочным, потом в дайджесте (watermark'и независимые). `urgent.py` метит посты через `state.mark_seen(ids)` (TTL 48ч); `digest.py` проверяет `state.is_seen(id)` перед добавлением. Это уже реализовано в коде — но в ТЗ нужно явно фиксировать, иначе при ревью кажется что двойная доставка возможна.
- **`mention_count` сбрасывается при прочтении.** Если Саша прочитал сообщение в мобилке до прогона крона (окно ≤3 мин) — `mention_count` уже 0, крон пропустит. Митигация: дополнительный проход по `last_update_at > since_ms` (итерация 1.5).
- **`mention_count` покрывает DM.** Отдельный проход по DM-каналам НЕ нужен — любое непрочитанное DM уже инкрементирует `mention_count` получателя.
- **Системные посты** (`type != ''`) — пропускать (join/leave и др.).
- **Удалённые посты** (`delete_at != 0`) — пропускать.
- **Первый запуск без state** — `urgent_last_ts = now_ms - 10*60*1000`, `digest_last_ts = now_ms - 2*60*60*1000`. НЕ 0 — иначе придёт вся история.
- **Логин/пароль — не использовать.** Только Bearer PAT. Логин-пароль для Loop явно запрещён (решение Саши 23.07.2026).
- **Баг в AnywhereContacts/merger.py (пофикшен 24.07.2026):** `ContactMerger` при записи `sources[source]` хардкодил только `email/synced_at/active` — поля `username`, `nickname` из mapper'а терялись. Фикс: при записи per-source meta копировать все доп. поля из `incoming_source` если они непустые и не базовые. Если `sources.loop.username` пустой у всех контактов после синка — это этот баг. Решение: пропатчить `merger.py` (`AnywhereContacts/anywhere_contacts/merger.py`, строки ~128-135) и перезапустить синк. **При добавлении новых коннекторов (Exchange и др.) — проверять что кастомные поля коннектора сохраняются после первого синка.**
- **`is_bot` отсутствует в `/api/v4/users`** — поле не возвращается. Детектировать через `roles` (`system_bot`) и суффикс email.
- **Первый пользователь в списке** часто оказывается деактивированным ботом (`123321123-bot`, `delete_at > 0`). Фильтр обязателен.
- **`find_contacts` возвращает `Dict[login, record]`, не list.** Итерировать через `.items()`, не напрямую. Поиск регистронезависимый, по подстроке — `find_contacts("ткаченко")` вернёт всех Ткаченко.
- **`ContactStore` требует path к файлу**, не к директории. `ContactStore(Path(".../Contacts/contacts.enc"), KEY)` — правильно. `ContactStore(Path(".../Contacts"), KEY)` → `IsADirectoryError`. (last_name + first_name), а не «Имя Фамилия» как в API. Единообразие с MoveFromZulip и ожиданиями MOFS matcher.
- **Пустой `position`** — не писать в contacts.enc, чтобы не затереть значение от Exchange OrgLookup.
- **Профиль `.env` для кронов — `anthropic`, не `default`.** `mfl_urgent_check.py` и `mfl_digest.py` грузят `.env` из `/home/tkachenkoav/.hermes/profiles/anthropic/.env` (там LOOP_TOKEN, CONTACTS_ENCRYPTION_KEY). Профиль `tz-dev` использует этот же файл. Не путать с `~/.config/hermes/.env` — там только TUTU_DOMAIN_PASSWORD для Exchange.
- **Скрипты `~/.hermes/scripts/` — только относительные пути.** `cronjob(script=...)` принимает только имя файла относительно `~/.hermes/scripts/`. Абсолютный путь или путь из USERTOOLS/ → «Script not found». Паттерн: скопировать entry-point в `~/.hermes/scripts/mfl_*.py`, хардкодить `_ROOT = Path("/home/tkachenkoav/USERTOOLS/MoveFromLoop")` внутри.
- **Кроны MoveFromLoop (24.07.2026):** срочный `f61b26cbbdf5` (*/3), дайджест `2865cc674493` (0 8-20 пн-пт). Оба `no_agent=true`, deliver=`telegram:-1004300127777:6556`. Скрипты: `mfl_urgent_check.py`, `mfl_digest.py`.
