---
name: MoveFromLoop v2 — impl plan
version: 2.0
status: ready-for-sonnet
date: 2026-07-24
author: Opus
scope: итерация 1 «мониторинг сообщений Loop», новая архитектура (mention_count-based)
---

# MoveFromLoop v2 — пофайловый план реализации (v2.0)

План рассчитан на Sonnet: без кода, только структура, интерфейсы, алгоритмы, тест-кейсы и порядок реализации.

**Ключевое отличие от v1.0:** источник упоминаний — эндпоинт `/channels/members` с полем `mention_count`. Это точный аналог вкладки «Упоминания и реакции» в Loop UI. Больше не нужно самим парсить `@tkachenkoav`/`@all`/reply-to-me по всем горячим каналам — Mattermost уже посчитал за нас.

Все пути относительно `/home/tkachenkoav/USERTOOLS/MoveFromLoop/`. Токен `LOOP_TOKEN` в `.env`. Team id: `b1mrmr41dtrhbgk3a9qa7bxhqe` (tutu). `my_username: tkachenkoav`.

---

## §1 Архитектура (overview)

Два независимых режима, **один источник данных для упоминаний** — `mention_count > 0` в `/channels/members`.

### Срочный режим (`*/3 * * * *`, круглосуточно)
- Опрос `channel_members` → каналы с `mention_count > 0`.
- Для каждого: `posts?since=urgent_watermark_ms` → фильтр по автору (`user_id ∈ urgent_contacts`).
- Найденное → немедленная доставка в Telegram, **`no_agent=true`**.
- Дедуп через `seen_ids` (TTL 48 ч).

### Дайджест (`0 8-20 * * 1-5`, пн–пт)
- Опрос `channel_members` → каналы с `mention_count > 0` → все упоминания за период (без фильтра по автору).
- Плюс `watch_channels` из конфига → фильтр по `keywords` (регистронезависимая подстрока).
- Объединение → сортировка по `create_at` → один пост в Telegram, **`no_agent=true`**.
- Ничего нет → SILENT.

### Единый формат строки
```
<первая непустая строка сообщения, обрезана до 200 символов>
🔗 https://loop.tutu.ru/tutu/pl/<post_id>
#<channel_display> · @<author_username>
```

### Конфиг `loop_rules.yaml`
Минимальный: `my_username`, `team_id`, `urgent_contacts` (username-ы), `watch_channels`, `keywords`.

### State
Один файл `state/watermark.json`: `urgent_last_ts`, `digest_last_ts`, `seen_ids: [{id, ts}]` с TTL 48 ч. Плюс кеш резолвов `username→user_id` и `channel_id→display` (TTL 24 ч).

---

## §2 Новые файлы

### `movefromloop/state.py`
- **Назначение:** атомарное чтение/запись `state/watermark.json`, управление `seen_ids` с TTL.
- **Публичный интерфейс:**
  - `class State(path: Path)`:
    - `.load() -> dict` — `{urgent_last_ts, digest_last_ts, seen_ids: [{id, ts}], user_cache: {username: {id, ts}}, channel_cache: {channel_id: {display, ts}}}`. Дефолты для отсутствующих полей.
    - `.save() -> None` — атомарная запись (`tmp → os.replace`).
    - `.mark_seen(post_ids: list[str]) -> None` — добавляет `{id, ts=now_ms}` в `seen_ids`.
    - `.is_seen(post_id) -> bool`.
    - `.prune(ttl_hours=48) -> None` — вычищает `seen_ids`, `user_cache`, `channel_cache` старше TTL.
    - `.set_urgent_watermark(ts_ms)`, `.set_digest_watermark(ts_ms)`.
    - `.get_urgent_watermark(default_lookback_min=10) -> int`, `.get_digest_watermark(default_lookback_hours=2) -> int` — если пусто, `now_ms - lookback`.
  - `now_ms() -> int` helper.
- **Зависимости:** stdlib.

### `movefromloop/loop_api.py`
- **Назначение:** тонкий Mattermost-клиент (v1 fetcher переиспользуем только для users, у него другая семантика).
- **Публичный интерфейс:**
  - `class LoopClient`:
    - `.me() -> dict`
    - `.channel_members(team_id, per_page=200) -> list[dict]` — пагинация до пустой страницы. Возвращает `[{channel_id, mention_count, last_update_at, last_viewed_at, ...}]`.
    - `.channel_info(channel_id) -> dict` — `GET /channels/{id}` → `{name, display_name, type}`.
    - `.channels_by_name(team_id, name) -> dict | None`
    - `.posts_since(channel_id, since_ms) -> list[dict]` — плоский, отсортированный ASC, отфильтрованы `delete_at != 0` и `type != ''`.
    - `.users_by_usernames(usernames: list[str]) -> dict[username, user]` — `POST /users/usernames`.
    - `.users_by_ids(ids: list[str]) -> dict[id, user]` — `POST /users/ids`.
  - `class LoopApiError(Exception)`.
- Retry 3× (1/3/9 c) на 5xx/429/таймауты, пауза 0.1 с между запросами.
- **Зависимости:** `requests`, `python-dotenv`.

### `movefromloop/channel_resolver.py`
- **Назначение:** `channel_name ↔ channel_id`, кеш display-имени канала (в т.ч. для DM — резолв собеседника).
- **Публичный интерфейс:**
  - `class ChannelResolver(client, team_id, state)`:
    - `.resolve_id(name_or_id) -> str | None` — id (26 alnum) → passthrough; иначе `channels_by_name`.
    - `.display(channel_id) -> str` — берёт `state.channel_cache` (TTL 24 ч), иначе `channel_info`. Для DM (`type=D`) — резолвит собеседника из `name` (`"userA__userB"`), запрашивает username через `users_by_ids`, возвращает `dm:@username`. Иначе — `display_name` или `name`.
- **Зависимости:** `loop_api`, `state`.

### `movefromloop/mentions_fetcher.py`
- **Назначение:** ядро новой архитектуры — «дай мне посты, где меня упомянули, начиная с since_ms».
- **Публичный интерфейс:**
  - `fetch_mentions(client, team_id, since_ms) -> list[dict]`:
    1. `client.channel_members(team_id)` → фильтр `mention_count > 0`.
    2. Для каждого такого канала: `client.posts_since(channel_id, since_ms)`.
    3. Возврат: плоский список постов, обогащённый `channel_id` (в каждом посте это поле уже есть от MM).
  - `fetch_watched(client, resolver, watch_channels: list[str], since_ms) -> list[dict]` — посты из `watch_channels`, без фильтра.
- **Зависимости:** `loop_api`, `channel_resolver`.

### `movefromloop/urgency_checker.py`
- **Назначение:** чистый фильтр «пост от срочного контакта».
- **Публичный интерфейс:**
  - `is_urgent(post: dict, urgent_user_ids: set[str]) -> bool` — `post['user_id'] in urgent_user_ids`.
  - `resolve_urgent_user_ids(client, contacts_source, usernames: list[str], state) -> set[str]`:
    - Сначала пробует `state.user_cache` (TTL 24 ч).
    - Промахи резолвим через **contacts.enc** по `sources.loop.username == username` → `sources.loop.user_id`.
    - Если в contacts.enc нет — фолбэк на `client.users_by_usernames`.
    - Обновляет `state.user_cache`, возвращает set user_id.
- **Зависимости:** `loop_api`, `state`, contacts-модуль v1 (для чтения `contacts.enc`).

### `movefromloop/keyword_checker.py`
- **Назначение:** чистый фильтр «пост содержит одно из ключевых слов».
- **Публичный интерфейс:**
  - `matches_keywords(text: str, keywords: list[str]) -> tuple[bool, str | None]` — регистронезависимая подстрока; возвращает первое совпавшее слово (для отладки, не для вывода).
- **Зависимости:** stdlib.

### `movefromloop/formatter.py`
- **Назначение:** пост Loop → строка Telegram (единый формат для обоих режимов).
- **Публичный интерфейс:**
  - `format_post(post, channel_display, author_username) -> str`:
    ```
    <первая непустая строка post['message'], truncate 200 + …>
    🔗 https://loop.tutu.ru/tutu/pl/<post_id>
    #<channel_display> · @<author_username>
    ```
  - `format_digest(items: list[str]) -> str` — заголовок `📬 Loop · N сообщ.` + элементы через `\n\n`.
  - `format_urgent(items: list[str]) -> str` — заголовок `🔴 СРОЧНО · N` + элементы через `\n\n───\n\n`. Если N=1 — заголовок опустить, оставить одну карточку с префиксом `🔴 `.
  - `truncate_first_line(text, max_len=200) -> str`.
- **Зависимости:** stdlib.

### `movefromloop/rules.py`
- **Назначение:** загрузка/сохранение `loop_rules.yaml` с сохранением комментариев.
- **Публичный интерфейс:**
  - `@dataclass Rules(my_username: str, team_id: str, urgent_contacts: list[str], watch_channels: list[str], keywords: list[str])`.
  - `load_rules(path) -> Rules`, `save_rules(path, rules)`.
  - Мутаторы: `add_channel`, `remove_channel`, `add_keyword`, `remove_keyword`, `add_urgent`, `remove_urgent` — идемпотентны.
- **Зависимости:** `ruamel.yaml`.

### `movefromloop/urgent.py`
- **Назначение:** оркестратор срочного.
- **Публичный интерфейс:** `run_urgent(rules_path, state_path) -> str | None`.

### `movefromloop/digest.py`
- **Назначение:** оркестратор дайджеста.
- **Публичный интерфейс:** `run_digest(rules_path, state_path) -> str | None`.

### `scripts/urgent_check.py`
- **Назначение:** CLI-точка входа, `no_agent=true`. Печатает готовый текст или ничего.
- **Логика:** `run_urgent()` → print, exit 0.

### `scripts/digest.py`
- Аналогично, `run_digest()` → print, exit 0. **Тоже `no_agent=true`** (см. §6).

### `loop_rules.yaml`
```yaml
# MoveFromLoop v2 — правила мониторинга Loop.
# Управляется Сиренью через команды в чате.

my_username: tkachenkoav
team_id: b1mrmr41dtrhbgk3a9qa7bxhqe

# Срочные контакты (username в Loop). Резолв → user_id через contacts.enc.
urgent_contacts: []
  # - aralov

# Каналы для дайджеста по ключевым словам (name без #, либо channel_id 26 симв).
watch_channels: []
  # - general

# Ключевые слова (регистронезависимая подстрока).
keywords: []
  # - ML-платформа
```

### `state/watermark.json`
```json
{
  "urgent_last_ts": 1784806508743,
  "digest_last_ts": 1784800000000,
  "seen_ids": [{"id": "abc...", "ts": 1784806508000}],
  "user_cache": {"aralov": {"id": "xyz...", "ts": 1784800000000}},
  "channel_cache": {"chan_id_26": {"display": "general", "ts": 1784800000000}}
}
```

---

## §3 Алгоритм срочного (детально)

1. **Bootstrap.** `scripts/urgent_check.py` → `urgent.run_urgent(rules_path, state_path)`.
2. **Load.** `rules = load_rules(...)`; `state = State(...)`; `state.prune(48)`.
3. **Watermark.** `since_ms = state.get_urgent_watermark(default_lookback_min=10)`.
4. **Client.** `client = LoopClient()`.
5. **Резолв urgent_user_ids.** `urgent_ids = urgency_checker.resolve_urgent_user_ids(client, contacts_source, rules.urgent_contacts, state)`. Если пусто — `return None` (нечего искать → SILENT), но watermark продвинуть на `now_ms` (защита от накопления).
6. **Fetch mentions.** `posts = mentions_fetcher.fetch_mentions(client, rules.team_id, since_ms)`.
7. **Фильтр урочности.** `urgent_posts = [p for p in posts if urgency_checker.is_urgent(p, urgent_ids)]`.
8. **Дедуп.** Убрать те, у которых `state.is_seen(post_id)`.
9. **Резолв авторов.** Один батч `client.users_by_ids(unique_user_ids)` → карта id→username.
10. **Резолв каналов.** Через `ChannelResolver.display` (кеш).
11. **Формат.** `items = [formatter.format_post(p, ch_display, author) for p in urgent_posts]` → `text = formatter.format_urgent(items)`.
12. **State update.** `state.mark_seen([p.id ...])`; `state.set_urgent_watermark(max(create_at) - 5000)` (небольшой overlap, дедуп прикроет). Если постов не было — просто `set_urgent_watermark(now_ms)`. `state.save()`.
13. **Return.** `text` или `None` (SILENT).

**Ответственность:** шаги 2/12 — `state.py`+`rules.py`; 5 — `urgency_checker.py`+contacts v1; 6 — `mentions_fetcher.py`+`loop_api.py`; 7 — `urgency_checker.py`; 10 — `channel_resolver.py`; 11 — `formatter.py`; 1/13 — `urgent.py`+`scripts/urgent_check.py`.

---

## §4 Алгоритм дайджеста (детально)

1. **Bootstrap.** `scripts/digest.py` → `digest.run_digest(...)`.
2. **Load.** `rules`, `state`, `state.prune(48)`.
3. **Watermark.** `since_ms = state.get_digest_watermark(default_lookback_hours=2)`.
4. **Client, resolver.**
5. **Mentions bucket.** `mention_posts = mentions_fetcher.fetch_mentions(client, rules.team_id, since_ms)` — все упоминания за окно.
6. **Watched-channels bucket.** Для каждого `name` из `rules.watch_channels`:
   - `cid = resolver.resolve_id(name)` (пропуски логировать).
   - `posts = client.posts_since(cid, since_ms)`.
   - Фильтр: `keyword_checker.matches_keywords(post['message'], rules.keywords)[0]`.
   - Собрать в `keyword_posts`.
7. **Merge.** `all_posts = mention_posts + keyword_posts`, дедуп по `post_id` (пост из watch-канала может быть одновременно упоминанием), убрать `state.is_seen`, отсортировать по `create_at ASC`.
8. **Пусто → SILENT.** Watermark всё равно продвинуть на `now_ms - 5000`, `state.save()`, `return None`.
9. **Резолв авторов** (один батч) **и каналов** (через кеш).
10. **Формат.** `items = [formatter.format_post(...) for p in all_posts]` → `text = formatter.format_digest(items)`.
11. **State.** `mark_seen`, `set_digest_watermark(max(create_at) - 5000)`, `save`.
12. **Return `text`.**

---

## §5 Резолв `urgent_contacts` (username → user_id)

- **Конфиг** хранит **только username** (например `aralov`) — так удобно человеку и Сирени.
- **Источник истины для маппинга:** `contacts.enc` из v1. Каждый контакт содержит `sources.loop.{username, user_id}`.
- **Процедура (`urgency_checker.resolve_urgent_user_ids`):**
  1. Для каждого username в `rules.urgent_contacts`:
     - Если есть свежая запись в `state.user_cache` (TTL 24 ч) — берём id оттуда.
     - Иначе ищем в `contacts.enc` по `sources.loop.username == username` → `sources.loop.user_id`.
     - Если и в contacts.enc нет (нового контакта ещё не синкали) — фолбэк `client.users_by_usernames([username])`.
     - Кладём `{username: {id, ts=now_ms}}` в `state.user_cache`.
  2. Возвращаем `set(user_id for username in list if resolved)`.
  3. Нерезолвнутые логируем в stderr (в stdout не пишем — cron ловит только stdout как сообщение).

- **Инвалидация кеша.** `state.prune(24)` при каждом запуске (для user_cache и channel_cache). При переименовании пользователя в Loop — переживём до 24 ч, приемлемо.

---

## §6 Кроны (точные параметры)

### Срочный
- `schedule`: `*/3 * * * *`
- `no_agent`: **true**
- `deliver`: `telegram:-1004300127777:6556`
- `command`: `cd ~/USERTOOLS/MoveFromLoop && venv_linux/bin/python scripts/urgent_check.py`
- `model` / `enabled_toolsets` / `prompt`: не заданы (no_agent их игнорирует).

### Дайджест
- `schedule`: `0 8-20 * * 1-5`
- `no_agent`: **true**
- `deliver`: `telegram:-1004300127777:6556`
- `command`: `cd ~/USERTOOLS/MoveFromLoop && venv_linux/bin/python scripts/digest.py`

### Решение по `no_agent` (зафиксировано)

Саша: «ничего лишнего — только первая строка + ссылка + канал + автор». Формат детерминированный, LLM ничего не добавит. Экономим токены и латентность. **Оба крона — `no_agent=true`.** Скрипты сами формируют финальный текст; Hermes отдаёт его как есть в Telegram. Пустой stdout = SILENT.

---

## §7 Питфоллы (актуальные для новой архитектуры)

1. **`since` в миллисекундах** (13 цифр). Везде `int(time.time() * 1000)`.

2. **`mention_count` сбрасывается при mark-as-read.** Если Саша прочитал канал в UI раньше крона — `mention_count` упадёт до 0, и мы пропустим упоминание. **Watermark обязан быть по времени (`create_at`), не по `mention_count`.** Мы используем `mention_count > 0` только как **быстрый фильтр каналов**, а посты уже тянем по `since_ms`. Если Саша прочитал канал до крона — упоминание всё равно попадёт в тот же тик (mention_count > 0 в момент прихода), а следующий тик его не увидит благодаря `seen_ids` и watermark.

   **Слабое место:** если Саша прочитал канал МЕЖДУ приходом сообщения и запуском крона (окно ≤ 3 мин), `mention_count` уже 0 → пропуск. Митигация в итерации 1.5: добавить сканирование всех `last_update_at > since_ms` каналов, а не только `mention_count > 0`. Для v2.0 принимаем риск: маловероятно, что Саша прочитает канал через мобилку за 3-минутное окно и это будет критично.

3. **DM-каналы и `mention_count`.** В Mattermost **любое непрочитанное сообщение в DM инкрементит `mention_count`** (DM трактуется как персональное обращение по умолчанию). То есть `mention_count > 0` **покрывает DM автоматически**, отдельный проход по DM-каналам не нужен. См. финальный ответ ниже.

4. **`@all` / `@channel` / `@here`.** MM инкрементит `mention_count` при этих упоминаниях у всех участников канала. Значит массовый `@all` от левого человека в шумном канале **тоже попадёт в срочный/дайджест**. В срочном это отсекается фильтром по автору (`urgent_contacts`). В дайджесте — попадёт, и это ОК (Саша хотел «всё где меня упомянули»). Regex парсить `@all` вручную **не нужно** — MM сам решил.

5. **Системные посты** (`type != ''`, напр. `system_join_channel`) — `posts_since` их вернёт. Фильтровать на уровне `loop_api.posts_since` (`type != ''` → skip).

6. **Удалённые посты** (`delete_at != 0`) — фильтровать там же.

7. **Первый запуск без state.** `urgent_last_ts = now - 10 min`, `digest_last_ts = now - 2 h`. НЕ ставить 0 — иначе первый прогон вывалит вагон истории.

8. **`seen_ids` дедупликация.** Watermark продвигается с overlap `-5 сек`, поэтому один и тот же пост может попасть в два соседних тика. `seen_ids` (TTL 48 ч) гарантирует, что доставим один раз. Формат `[{id, ts}]`, а не `[id]` — чтобы честно чистить TTL.

9. **Пагинация `channel_members`.** У Саши ~3344 записи → `per_page=200`, 17 страниц, ~1.7 c. Уложимся в 3-минутный тик.

10. **`no_agent=true` и несколько срочных.** Один тик = одна доставка. Несколько срочных постов конкатенируем через `\n\n───\n\n` внутри одного сообщения (см. `formatter.format_urgent`).

11. **Ссылка на пост** — `https://loop.tutu.ru/tutu/pl/<post_id>`, `team=tutu` жёстко.

12. **`ruamel.yaml`** вместо `pyyaml` — сохраняет комментарии при round-trip (Сирень редактирует конфиг из чата).

---

## §8 Тест-кейсы (по модулям)

### `state.py`
- `test_load_missing_returns_defaults`.
- `test_save_atomic` (запись через tmp+replace).
- `test_prune_removes_old_seen_ids` (id старше 48 ч чистятся).
- `test_prune_removes_old_user_cache` (24 ч).
- `test_watermark_default_lookback` — пустой state → `now_ms - 10*60*1000`.

### `loop_api.py`
- `test_channel_members_paginates_until_empty`.
- `test_posts_since_filters_deleted_and_system`.
- `test_retry_on_5xx_then_success`.
- `test_429_treated_as_retryable`.
- `test_4xx_no_retry`.
- `test_users_by_usernames_batch`.

### `channel_resolver.py`
- `test_resolve_by_id_passthrough` (26 alnum).
- `test_resolve_by_name_strips_hash`.
- `test_display_uses_cache` (второй вызов без API-обращения).
- `test_display_for_dm_resolves_partner_username`.

### `mentions_fetcher.py`
- `test_fetch_mentions_filters_by_mention_count`.
- `test_fetch_mentions_calls_posts_since_only_for_hot_channels` (mock: 3000 каналов, 5 с mention_count>0 → posts_since вызван 5 раз).
- `test_fetch_watched_returns_all_posts_no_filter`.

### `urgency_checker.py`
- `test_is_urgent_true_when_author_in_set`.
- `test_is_urgent_false_when_not`.
- `test_resolve_uses_state_cache_first`.
- `test_resolve_falls_back_to_contacts_enc`.
- `test_resolve_falls_back_to_api_when_contact_missing`.
- `test_resolve_logs_unresolved_to_stderr_not_stdout`.

### `keyword_checker.py`
- `test_case_insensitive_substring`.
- `test_returns_first_match`.
- `test_empty_keywords_returns_false`.

### `formatter.py`
- `test_first_nonempty_line_truncated_to_200`.
- `test_format_post_layout` (три строки в правильном порядке).
- `test_format_urgent_single_no_header`.
- `test_format_urgent_multiple_with_separator`.
- `test_format_digest_header_with_count`.

### `rules.py`
- `test_load_empty_yaml_defaults`.
- `test_round_trip_preserves_comments`.
- `test_add_channel_idempotent`.
- `test_remove_missing_is_noop`.

### `urgent.py` (интеграционные, моки)
- `test_silent_when_no_urgent_contacts_configured` (пустой urgent_contacts → None).
- `test_silent_when_no_matching_posts`.
- `test_dedup_by_seen_ids` — один и тот же post_id во втором тике не доставляется.
- `test_watermark_advances_with_overlap` (`-5000` мс).
- `test_multiple_urgent_joined_with_separator`.

### `digest.py` (интеграционные, моки)
- `test_silent_when_empty`.
- `test_merges_mentions_and_keyword_matches`.
- `test_dedup_across_buckets` (пост из watch-канала = упоминание — один раз).
- `test_watermark_advances_on_silent` (даже при пустом дайджесте).

---

## §9 Порядок реализации (5 фаз для Sonnet)

### Фаза 1 — фундамент (state + API) · 1–1.5 ч
1. `movefromloop/state.py` + тесты.
2. `movefromloop/loop_api.py` (методы: `me`, `channel_members`, `channel_info`, `channels_by_name`, `posts_since`, `users_by_usernames`, `users_by_ids`) + retry + тесты.
3. `movefromloop/channel_resolver.py` + тесты.

Ручная проверка: `python -c "..."` — вывести все каналы с `mention_count > 0` прямо сейчас.

### Фаза 2 — фетчеры и фильтры · 1 ч
4. `movefromloop/mentions_fetcher.py` + тесты.
5. `movefromloop/urgency_checker.py` (включая резолв через contacts.enc) + тесты.
6. `movefromloop/keyword_checker.py` + тесты.

### Фаза 3 — конфиг и формат · 40 мин
7. `movefromloop/rules.py` (`ruamel.yaml`) + тесты.
8. `movefromloop/formatter.py` + тесты.
9. Начальный `loop_rules.yaml` с шаблонными комментариями.

### Фаза 4 — оркестраторы и cron-entrypoints · 1 ч
10. `movefromloop/urgent.py` + интеграционные тесты.
11. `movefromloop/digest.py` + интеграционные тесты.
12. `scripts/urgent_check.py`, `scripts/digest.py`.
13. Ручной прогон обоих скриптов, проверить SILENT-поведение при пустом конфиге.

### Фаза 5 — кроны и e2e · 30 мин
14. Создать оба крона через `cronjob(action='create')` (§6). Оба `no_agent=true`.
15. Добавить пару `urgent_contacts` для проверки, попросить коллегу написать в DM → в течение 3 мин прилетело в топик Messages.
16. Дождаться следующего часа 8–20 в будни → дайджест или SILENT.
17. Обновить `README.md` в `USERTOOLS/MoveFromLoop/`.

**Оценка суммарно:** ~4 часа.

---

## §10 Что НЕ делаем в этой итерации

- Ответы из Telegram обратно в Loop.
- Архивация переписки (итерация 1.5).
- Скилл Сирени с командами «добавь канал/…» — покрывается в отдельном ТЗ Сирени.
- Обработка `edit_at` (редактирование постов).
- Реакции emoji, вложения/файлы.
- Митигация сценария «Саша прочитал канал между приходом и кроном» через `last_update_at` (итерация 1.5).
