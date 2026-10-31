---
name: mattermost-loop-api
description: "loop api / mattermost api: Loop ТУТУ REST v4"
version: 2.0.1
author: agent
license: MIT
platforms: [linux]
tags: [loop, mattermost, api, contacts, tutu, mfl]
---

# Mattermost / Loop API

Loop — корпоративный мессенджер ТУТУ на базе Mattermost (loop.tutu.ru).

## Linked files

- `references/mfl-502-degradation.md` — graceful degradation при 502 Bad Gateway от сервера Mattermost
- `references/mfl-notify-debug-recipe.md` — рецепт диагностики когда urgent-уведомление не пришло

## Аутентификация

**Только Personal Access Token (Bearer) — логин/пароль не использовать.**

Токен хранится в `WorkVault/Inbox/Loop Hermes token.md`. В `.env` инструмента: `LOOP_TOKEN=<access_token>`.

## API-эндпоинты

```bash
# Проверка подключения
GET /api/v4/users/me

# Каналы с непрочитанными упоминаниями — КЛЮЧЕВОЙ эндпоинт
GET /api/v4/users/me/teams/{team_id}/channels/members?per_page=200&page=N

# Посты канала с момента (since в МИЛЛИСЕКУНДАХ!)
GET /api/v4/channels/{channel_id}/posts?since={unix_ms}&per_page=200

# Подтопики канала (топики) — КЛЮЧЕВОЙ для полного дайджеста канала (проверено 27.08.2026)
GET /api/v4/channels/{channel_id}/topics
# Родительский канал часто ПУСТ (total_msg_count=0), вся активность живёт в подтопиках
# (type=O, у каждого свой id/name/display_name). Для полного дайджеста канала:
# topics() → по каждому topic_id GET /channels/{topic_id}/posts. Топик — полноценный канал.

# Инфо о канале
GET /api/v4/channels/{channel_id}

# Резолв usernames → user_dict (может вернуть 502!)
POST /api/v4/users/usernames  json_body=["username1", "username2"]

## Резолв username из ФИО (эмпирически подтверждено 21.08.2026)

Когда известна только ФИО (из Confluence/минуток), а нужен Loop-username — **не гадай кириллическим поиском**: `GET /users/search?term=<кириллица>` и `GET /users/autocomplete?name=<кириллица>` возвращают **пусто** в этой инсталляции Loop.

**Рабочий способ:** Loop-username строится как фамилия латиницей в нижнем регистре **без первой буквы имени** (тот же паттерн, что у Confluence `username`). Собрать кандидатов и отдать одним `POST /users/usernames` — невалидные кандидаты молча отбрасываются:

```bash
POST /api/v4/users/usernames
json_body=["nabieva","kotelnikova","rasov","zhirov","sereda","soldatenkov","peretyatkova"]
# → [{"username":"nabieva","first_name":"Даяна","last_name":"Набиева"}, ...]
```

Проверенный пример (руководители АиД, 2026): Набиева→`nabieva`, Котельникова→`kotelnikova`, Расов→`rasov`, Жиров→`zhirov`, Середа→`sereda`, Перетяткова→`peretyatkova`, Солдатенков→`soldatenkov`. При сомнениях в раскладке перечислить все варианты фамилии.

# Резолв user_ids → user_dict
POST /api/v4/users/ids  json_body=["id1", "id2"]
```

Team ID ТУТУ: `b1mrmr41dtrhbgk3a9qa7bxhqe`

## HTTP-клиент: curl через subprocess, не requests

`requests` (и `httpx`) зависают на loop.tutu.ru. Использовать `curl` через `subprocess` с `--max-time 10`.

## Пост по ссылке `pl/<id>` — GET /posts/{id}

Ссылка из Loop вида `https://loop.tutu.ru/.../pl/<postId>` (id в конце пути — это **ID поста**, не канала) достаётся одним GET без резолва канала:

```bash
GET /api/v4/posts/{post_id}
# → {"id", "channel_id", "user_id", "root_id", "create_at", "message"}  (message — markdown)
```

`root_id` — ID первого поста ветки; по нему можно понять, что пост — часть треда.

## Многочастная таблица/документ: один контент в нескольких постах треда

Один логический артефакт (напр. длинная markdown-таблица «Вопрос — Ответ») автор иногда разбивает на **несколько последовательных постов одной ветки** (один `channel_id`, общий `root_id`, суффиксы `(1/4)`…`(4/4)` в конце message). При обработке:

1. Собери **все** посты треда (по `channel_id`/`root_id`), не бери только те, что дал пользователь, — обрежешь документ.
2. Конкатенируй `message` в порядке следования, **отрезав служебный вводный текст до первой строки таблицы** и маркеры `(N/4)` в конце частей (они прилипают к последней строке и ломают парсер).
3. Парси markdown-таблицу уже по полному единому тексту.
4. Перед итогом сверь: вытащил ли все строки (номерной регэксп `\| \*\*(\d+)\.` ловит 19 из 19, не 15) — падение имени счётчика = потерянные строки, искать огрехи парсинга, а не «всех данных нет».

## Мониторинг сообщений (MoveFromLoop v2)

**Два режима:**
- **Срочный** (каждые 3 мин) — DM + @упоминания от urgent_contacts → немедленно в Telegram
- **Дайджест** (раз в час, 8:00-20:00 пн-пт) — сводка всех упоминаний → в Telegram

Крон срочный: `f61b26cbbdf5`, крон дайджест: `2865cc674493`.
Deliver: `telegram:-1004300127777:6556`

**Код:** `~/USERTOOLS/MoveFromLoop/`
**Скрипты:** `~/.hermes/scripts/mfl_urgent_check.py`, `~/.hermes/scripts/mfl_digest.py`

## Pitfalls

- **`source` на `~/.config/hermes/.env` падает с syntax error** из-за спецсимволов в `TUTU_DOMAIN_PASSWORD`. Извлекай только `LOOP_TOKEN` без source: `TOKEN=$(grep 'LOOP_TOKEN' ~/.config/hermes/.env | cut -d= -f2- | tr -d '\"\r')`.
- **`since` в API — МИЛЛИСЕКУНДЫ, не секунды.** 13-значное число.
- **`per_page=200` в `/channels/members` игнорируется** — API возвращает все каналы одним ответом.
- **Неоднозначность имён каналов.** Возможны два канала с похожими именами (реальный кейс 27.08.2026: `llm-byam` = родитель с 38 подтопиками, и `llm` = самостоятельный канал без топиков). `GET /teams/{team}/channels/name/{name}` резолвит ТОЧНОЕ имя. Вызов `/topics` на канале, который НЕ родитель подтопиков, → **403 read_channel** (не 404). Для дайджеста канала с подтопиками передавать точное имя родителя, а не сокращение.
- **`mention_count` сбрасывается при прочтении.** Если прочитал в мобилке до тика крона — пропустит.
- **`POST /api/v4/users/usernames` → 502 Bad Gateway.** Сервер Mattermost лежит. См. `references/mfl-502-degradation.md`.
- **`requests` зависает на loop.tutu.ru** — использовать `curl` через subprocess.
- **Hermes no_agent скрипты: путь к модулям.** Скрипты копируются в `~/.hermes/scripts/`. Хардкодить `_ROOT = Path("/home/tkachenkoav/USERTOOLS/MoveFromLoop")` и грузить `.env` из `~/.hermes/profiles/anthropic/.env`.
- **`telegram disconnected` — deliver падает бесшумно.** `last_delivery_error` остаётся `null`. Проверяй `gateway_state.json` → `platforms.telegram.state`.
- **Логи urgent-крона (*/3) ротируются быстро** (~несколько часов). Нет логов ≠ крон не работал. Источник истины — `state/watermark.json`.
- **`seen_ids` помечаются ДО подтверждения deliver.** Структурный баг в `urgent.py` — если deliver падает, пост теряется навсегда.
- **Профиль `.env` для кронов — `anthropic`, не `default`.**
