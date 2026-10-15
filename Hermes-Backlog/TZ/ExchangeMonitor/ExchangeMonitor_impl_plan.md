---
name: ExchangeMonitor — пофайловый план реализации
version: 0.1.0
status: ready-for-sonnet
created: 2026-07-24
author: Opus
based_on: ExchangeMonitor_TZ.md v0.1.0
---

# ExchangeMonitor — пофайловый план реализации

Цель документа — дать Sonnet-исполнителю пошаговый контракт: что за файл, что публикует, от чего зависит, что тестировать. **Код не пишется**, только контракты и алгоритмы.

Важное предусловие, обнаруженное на этапе плана: `exchangelib` **не установлен ни в одном системном Python** (`/usr/bin/python3`, `/usr/bin/python3.11`) и **отсутствует venv у `ExchangeMeeting`**. ТЗ утверждает обратное — расхождение. Живая проверка EWS-доступа выполнена быть не может, пока Sonnet не создаст venv и не поставит зависимости (см. §11, Фаза 0).

---

## §1. Новые файлы

Раскладка:
```
USERTOOLS/ExchangeMonitor/
  exchangemonitor/
    __init__.py
    config.py
    client.py
    fetcher.py
    person_checker.py
    tagger.py
    formatter.py
    owa.py
    urgent.py
    digest.py
    ex_state.py           # тонкая надстройка над movefromloop.state.State
  tests/
    __init__.py
    test_person_checker.py
    test_tagger.py
    test_formatter.py
    test_owa.py
    test_ex_state.py
    test_fetcher_smoke.py         # @pytest.mark.integration
  requirements.txt
  pyproject.toml
  README.md
```

### 1.1 `exchangemonitor/__init__.py`
- **Назначение:** пакет, реэкспорт публичного API.
- **Публичный интерфейс:** `from .urgent import run_urgent_exchange`, `from .digest import run_digest_exchange`.
- **Зависимости:** только внутренние.

### 1.2 `exchangemonitor/config.py`
- **Назначение:** загрузка `loop_rules.yaml` и `~/.config/hermes/.env` (пароль домена).
- **Публичный интерфейс:**
  - `load_rules(path: Path) -> ExchangeRules` (dataclass: `enabled: bool`, `inbox_folder: str`, `urgent_limit: int`, `digest_limit: int`, `urgent_contacts: list[str]`, `my_email: str`).
  - `load_password() -> str` — читает `TUTU_DOMAIN_PASSWORD` из `~/.config/hermes/.env` (алгоритм скопировать из `ExchangeMeeting/create_meeting.py::load_password`, вынести в общий helper здесь).
- **Зависимости:** `pyyaml`, stdlib. Не тянет exchangelib.
- **Инвариант:** дефолты — `enabled=False`, `inbox_folder="Inbox"`, `urgent_limit=200`, `digest_limit=500`, `my_email="tkachenkoav@tutu.ru"`. Отсутствующие поля в YAML не ломают загрузку.

### 1.3 `exchangemonitor/client.py`
- **Назначение:** EWS-клиент, авторизация, singleton-сессия в рамках процесса, ретраи попыток username.
- **Публичный интерфейс:**
  - `get_account() -> exchangelib.Account` — идемпотентно, кэширует в модульной переменной `_ACCOUNT`.
  - `close_account() -> None` — сброс кэша (для тестов).
- **Алгоритм авторизации:** копия из `ExchangeMeeting/create_meeting.py` — по очереди `tkachenkoav@tutu.ru` → `TUTU\\tkachenkoav` → `tkachenkoav`; на успехе `_ = account.root.name` как smoke-запрос.
- **Зависимости:** `exchangelib`, `.config.load_password`.
- **Обработка ошибок:** пробрасывает последнюю ошибку наверх — вызов в `urgent.py`/`digest.py` обёрнут try/except (fail-quiet).

### 1.4 `exchangemonitor/fetcher.py`
- **Назначение:** чтение Inbox с фильтром `datetime_received > from_ts_ms` и лимитом.
- **Публичный интерфейс:**
  - `fetch_inbox_since(account, from_ts_ms: int, limit: int) -> list[Item]` — возвращает список писем, отсортированных по возрастанию `datetime_received`.
  - CLI: `python -m exchangemonitor.fetcher --last N` печатает N последних писем (smoke).
- **Реализация:** `account.inbox.filter(datetime_received__gt=<EWSDateTime UTC>).order_by('-datetime_received').only('id','subject','sender','to_recipients','cc_recipients','datetime_received','text_body')[:limit]`, затем `reversed` для восходящего порядка.
- **Зависимости:** `exchangelib`, `.client`.
- **Конверсия времени:** `EWSDateTime.from_datetime(datetime.fromtimestamp(from_ts_ms/1000, tz=timezone.utc))`.

### 1.5 `exchangemonitor/person_checker.py`
- **Назначение:** решить, «реальный человек» ли отправитель.
- **Публичный интерфейс:**
  - `BOT_MARKERS: tuple[str, ...]` — константа.
  - `is_real_person(email: str, sender_name: str | None, contacts_store) -> bool` — `contacts_store` может быть `None` (тогда без contacts-ветки).
  - `PersonCache(state)` с `get(email) -> bool | None` и `put(email, value)` — TTL 24 ч; хранение в `state.data["exchange_person_cache"]`.
- **Зависимости:** `anywhere_contacts.store.ContactStore`, stdlib.
- **Логика — детально §5 ниже.**

### 1.6 `exchangemonitor/tagger.py`
- **Назначение:** вычислить тег письма `(приватное)` / `(личное)` / `""`.
- **Публичный интерфейс:** `compute_tag(item, me_email: str) -> str` — возвращает `"(приватное)"`, `"(личное)"` или `""`.
- **Зависимости:** только `exchangelib` (структурно — только `.to_recipients`, `.cc_recipients`).
- **Правила — §6.**

### 1.7 `exchangemonitor/formatter.py`
- **Назначение:** формат одного письма в строку Telegram.
- **Публичный интерфейс:**
  - `format_email(item, tag: str, fio: str, owa_link: str, tz_name: str = "Europe/Moscow") -> str`.
  - Хелперы (private): `_extract_snippet(text_body: str) -> str`, `_trim_by_word(s: str, max_len: int = 150) -> str`.
  - `format_urgent_ex(items: list[str]) -> str` — общий блок срочного (заголовок `🔴 Exchange · N` или префикс `🔴 ` для одного письма).
  - `format_digest_ex(items: list[str]) -> str` — заголовок `📧 Exchange · N писем` + склейка.
- **Зависимости:** stdlib, `exchangelib.EWSTimeZone`.
- **Формат — §7.**

### 1.8 `exchangemonitor/owa.py`
- **Назначение:** построение OWA-ссылки из `item.id`.
- **Публичный интерфейс:** `build_link(item_id: str, base: str = "https://cas.tutu.ru/owa") -> str`.
- **Реализация Фазы 1:** `f"{base}/?ItemID={quote(item_id, safe='')}&exvsurl=1&viewmodel=ReadMessageItem"`.
- **Зависимости:** stdlib (`urllib.parse.quote`).

### 1.9 `exchangemonitor/ex_state.py`
- **Назначение:** тонкая надстройка над `movefromloop.state.State` для новых ключей ExchangeMonitor (не форк).
- **Публичный интерфейс (принимает уже загруженный `State`):**
  - `get_urgent_watermark(state) -> int | None` (None → первый запуск).
  - `set_urgent_watermark(state, ts_ms: int)`.
  - `get_digest_watermark(state) -> int | None`.
  - `set_digest_watermark(state, ts_ms: int)`.
  - `get_user_email(state, login: str, ttl_h: int = 24) -> str | None` / `set_user_email(state, login, email)`.
  - `mark_seen(state, item_id: str, ts_ms: int)` / `is_seen(state, item_id: str) -> bool`.
  - `prune_ex(state, seen_ttl_h: int = 48, cache_ttl_h: int = 24)`.
- **Хранит в `state.data`:** `exchange_urgent_last_ts`, `exchange_digest_last_ts`, `exchange_user_cache`, `exchange_urgent_seen_ids`, `exchange_person_cache`.
- **Зависимости:** `movefromloop.state.State`, `movefromloop.state.now_ms`.

### 1.10 `exchangemonitor/urgent.py`
- **Назначение:** оркестратор срочного режима.
- **Публичный интерфейс:** `run_urgent_exchange(rules_path: Path, state_path: Path) -> str` — возвращает пустую строку `""` если нечего показывать. Никогда не бросает наружу.
- **Зависимости:** все внутренние модули + `movefromloop.state.State`.
- **Алгоритм — §3.**

### 1.11 `exchangemonitor/digest.py`
- **Назначение:** оркестратор дайджеста.
- **Публичный интерфейс:** `run_digest_exchange(rules_path: Path, state_path: Path) -> str`.
- **Алгоритм — §4.**

### 1.12 `tests/…`
- `__init__.py` — пустой.
- `test_person_checker.py`, `test_tagger.py`, `test_formatter.py`, `test_owa.py`, `test_ex_state.py` — unit, без сети. Моки `exchangelib`-объектов (простые namedtuple/SimpleNamespace с полями `sender.email_address`, `sender.name`, `to_recipients`, `cc_recipients`, `datetime_received`, `text_body`, `subject`, `id`).
- `test_fetcher_smoke.py` — интеграционный, `@pytest.mark.integration`, читает 5 последних писем на реальный `tkachenkoav@tutu.ru`, не трогает боевой state.

### 1.13 `requirements.txt`
```
exchangelib>=5.6,<6
pyyaml>=6
python-dotenv>=1
```
(`anywhere_contacts` и `movefromloop` подключаются через `sys.path`, не через pip.)

### 1.14 `pyproject.toml`
- Минимальный PEP-621: name=`exchangemonitor`, version=`0.1.0`, python `>=3.11`, зависимости — те же, что в `requirements.txt`. `[tool.pytest.ini_options] markers = ["integration: hits real Exchange"]`.

### 1.15 `README.md`
- 1 экран: назначение, установка venv, переменные окружения (`TUTU_DOMAIN_PASSWORD`, `CONTACTS_PATH`, `CONTACTS_ENCRYPTION_KEY`), как запустить smoke и unit-тесты.

---

## §2. Интеграция в MFL-скрипты

Патч ОДИНАКОВЫЙ для `~/.hermes/scripts/mfl_urgent_check.py` и `mfl_digest.py`. Ниже — на примере urgent (для digest — заменить `urgent` → `digest` в двух местах).

### 2.1 Что добавляется в `mfl_urgent_check.py`

**Куда:** внутрь `main()`, СРАЗУ после `result = run_urgent(RULES_PATH, STATE_PATH)`, ДО блока `if result: print(result)`.

**Что добавляется (только вставка новых строк, существующие не меняются):**
```python
    # ── ExchangeMonitor ────────────────────────────────────────────
    ex_block = ""
    try:
        sys.path.insert(0, "/home/tkachenkoav/USERTOOLS/ExchangeMonitor")
        from exchangemonitor.urgent import run_urgent_exchange
        ex_block = run_urgent_exchange(RULES_PATH, STATE_PATH)
    except Exception as exc:
        print(f"[urgent_check] Exchange FAIL: {exc}", file=sys.stderr)
        ex_block = ""
```

**Замена финального блока вывода** (было `if result: print(result)`):
```python
    parts = [p for p in (result, ex_block) if p]
    if parts:
        print("\n\n".join(parts))
```

### 2.2 Порядок: Loop → Exchange

**Loop первым.** Причины:
1. Loop — быстрый локальный HTTP, стабильнее по времени ответа; Exchange — EWS через HTTPS + Basic-auth, дольше и чаще падает. Ставить нестабильное в конец, чтобы уже принятые Loop-сообщения не терялись из-за таймаутов Exchange.
2. Loop — основной канал рабочих упоминаний, Exchange — «страховка от пропуска писем». Психологически ожидаемый порядок «сначала мессенджер, потом почта».
3. `run_urgent_exchange` и `run_digest_exchange` — оба возвращают строку без хвостового `\n` и без своего служебного разделителя. Склейка `"\n\n".join(...)` — единая для обоих режимов.

### 2.3 Что НЕ меняется

- Логика `run_urgent`/`run_digest` из MoveFromLoop.
- Схема state.json Loop-части (`urgent_last_ts`, `digest_last_ts`, `seen_ids`, `user_cache`, `channel_cache`) — Exchange добавляет НОВЫЕ ключи, не трогает старые.
- Загрузка `.env` и путей `RULES_PATH`/`STATE_PATH`.

### 2.4 Отключение

Установка `exchange_enabled: false` в `loop_rules.yaml` → `run_urgent_exchange` возвращает `""` на первой же строке (см. §3.1). Патч в MFL при этом не убирается — он тихо становится no-op.

---

## §3. Алгоритм срочного (`run_urgent_exchange`) — детально

| # | Шаг | Файл / функция |
|---|---|---|
| 1 | Загрузить `loop_rules.yaml`. Если `exchange_enabled != True` → `return ""`. | `config.load_rules` |
| 2 | `State(state_path).load()`, вызвать `prune()` (Loop-часть) и `ex_state.prune_ex(state)`. | `movefromloop.state.State`, `ex_state.prune_ex` |
| 3 | `wm = ex_state.get_urgent_watermark(state)`. Если `wm is None` → первый запуск: `ex_state.set_urgent_watermark(state, now_ms())`, `state.save()`, `return ""`. | `ex_state` |
| 4 | Резолв `urgent_contacts` (list of Loop-login) → set of email через `AnywhereContacts.ContactStore.get_contact(login)["email"]`. Кешировать в `exchange_user_cache` (TTL 24 ч). Если ни один login не резолвится → warning в stderr, `set_urgent_watermark(now_ms())`, save, `return ""`. | `ex_state.get_user_email` + `anywhere_contacts` |
| 5 | `account = client.get_account()`. Ошибка → stderr, save, `return ""`. | `client.get_account` |
| 6 | `items = fetcher.fetch_inbox_since(account, wm, limit=rules.urgent_limit)`. | `fetcher.fetch_inbox_since` |
| 7 | Для каждого `item`: (a) `email = item.sender.email_address.lower()`; (b) `if email not in urgent_emails: continue`; (c) person-check `is_real_person(email, item.sender.name, contacts_store)` — на случай, что login в urgent_contacts, но помечен ботом; отбраковать → continue; (d) `tag = compute_tag(item, me_email)`; (e) `fio = contacts_store.get_contact_by_email(email)["fio"] or item.sender.name or email`; (f) `link = owa.build_link(item.id)`; (g) `line = format_email(item, tag, fio, link)`; (h) `ex_state.mark_seen(state, item.id, ts_ms=int(item.datetime_received.timestamp()*1000))`; накопить `line`. | `person_checker`, `tagger`, `formatter`, `owa`, `ex_state` |
| 8 | Watermark: если письма обработаны — `new_wm = max(int(item.datetime_received.timestamp()*1000) for item in processed)`; иначе `new_wm = now_ms()`. `ex_state.set_urgent_watermark(state, new_wm)`. | `ex_state` |
| 9 | `state.save()`. | `State.save` |
| 10 | Если строк нет → `return ""`. Иначе → `return formatter.format_urgent_ex(lines)`. | `formatter.format_urgent_ex` |

Весь блок 3-10 обёрнут `try/except Exception as e: print(f"[exchange_urgent] {e}", file=sys.stderr); return ""` — fail-quiet.

---

## §4. Алгоритм дайджеста (`run_digest_exchange`) — детально

| # | Шаг | Файл / функция |
|---|---|---|
| 1 | Загрузить rules; `exchange_enabled` → `return ""`. | `config.load_rules` |
| 2 | `State(...).load()`, `prune()`, `prune_ex()`. | `state`, `ex_state` |
| 3 | `wm = ex_state.get_digest_watermark(state)`. Если `None` → первый запуск: `set_digest_watermark(now_ms())`, save, `return ""`. | `ex_state` |
| 4 | `account = client.get_account()`. | `client` |
| 5 | `items = fetcher.fetch_inbox_since(account, wm, limit=rules.digest_limit)`. | `fetcher` |
| 6 | Для каждого `item`: (a) `email = item.sender.email_address.lower()`; (b) `if ex_state.is_seen(state, item.id): continue` — де-дубль со срочным; (c) `if not is_real_person(email, item.sender.name, contacts_store): continue`; (d) tag; (e) fio (contacts → sender.name → email); (f) OWA link; (g) `line = format_email(...)`; накопить. **`mark_seen` в дайджесте НЕ вызываем** — seen_ids ведёт только срочный. | `person_checker`, `tagger`, `formatter`, `owa` |
| 7 | Watermark: `new_wm = max(ts) if processed else now_ms()`. `set_digest_watermark(new_wm)`, save. | `ex_state` |
| 8 | Пусто → `""`. Иначе → `formatter.format_digest_ex(lines)`. | `formatter.format_digest_ex` |

Fail-quiet как в §3.

---

## §5. `person_checker` — детальная логика

Порядок фильтров (первое сработавшее — вердикт), с кэшем на входе/выходе:

**0. Кеш.** `PersonCache.get(email)` → если `True/False` возвращён — вернуть его, без дальнейших проверок. TTL 24 ч, хранение в `state.data["exchange_person_cache"] = {email: {"val": bool, "ts": ms}}`. Кеш пишется на выходе (шаг 5).

**1. BOT_MARKERS в email.** Подстрочная проверка `email.lower()` против:
```
noreply, no-reply, donotreply, notification, notifications,
alert, alerts, system, bot, jira, confluence, jenkins, bamboo,
mailer-daemon, postmaster, automation, builds, ci-, gitlab, github
```
Хит → `False`. **Иначе** идём дальше (НЕ возвращаем `True` — надо ещё пройти пункт 2/3).

**2. contacts.enc — hit.** Если `contacts_store.get_contact_by_email(email)` вернул не-None → `True`.

**3. `sender.name`-fallback.** Если `item.sender.name` непустой:
- нормализовать: `sn = sender_name.strip()`;
- если `sn.lower() == email.lower()` → пропустить (мусорный DisplayName);
- если `sn.lower()` содержит любой BOT_MARKER (по той же таблице) → `False`;
- иначе → `True`.

**4. Иначе.** `False`. Никаких `resolve_names()` в шаге 1 — `sender.name` в exchangelib заполнен уже при `.only('sender', ...)`; отдельный API-вызов не делаем (важное отступление ТЗ §6.4 в сторону упрощения — если Sonnet увидит, что `sender.name` реально приходит пустым для внешних SMTP, добавить `resolve_names()` как отдельный шаг 3.5, но по умолчанию — не делаем).

**5. Запись в кеш.** `PersonCache.put(email, verdict)` перед `return verdict`.

---

## §6. `tagger` — правила тегов

Вход: `item` (нужны `.to_recipients: list | None`, `.cc_recipients: list | None`, каждый элемент имеет `.email_address`), `me_email: str`.

```
to = { r.email_address.lower() for r in (item.to_recipients or []) }
cc = { r.email_address.lower() for r in (item.cc_recipients or []) }
me = me_email.lower()

Правила (первое подходящее):
  (me in to) and (len(to) == 1) and (me not in cc)  →  "(приватное)"
  (me in cc) and (me not in to)                      →  "(личное)"
  (me in to) and (len(to) > 1)                       →  ""
  else                                                →  ""
```

Тесты — 5 матриц: private / group-to / cc-only / to+cc одновременно (нестандарт, без тега) / BCC (я ни в to, ни в cc — без тега).

---

## §7. `formatter` — формат строки

Шаблон:
```
📧 {tag_prefix}от {ФИО} [ЧЧ:ММ]
{second_line}
🔗 {owa_link}
```

- `tag_prefix`: `"(приватное) "`, `"(личное) "` или `""`. Если тег есть — со скобками и пробелом на конце.
- `ФИО` — как передано параметром (`urgent.py`/`digest.py` уже выбрали: contacts.fio → sender.name → email).
- `ЧЧ:ММ` — `item.datetime_received.astimezone(EWSTimeZone("Europe/Moscow")).strftime("%H:%M")`.
- `second_line`:
  - `subject = item.subject or "(без темы)"`, схлопнуть `\s+` в один пробел, strip.
  - `body = _extract_snippet(item.text_body or "")`:
    - разбить по `\n`, отфильтровать строки, начинающиеся с `>` (цитата), обрезать всё после отдельной строки `-- ` (подпись),
    - схлопнуть пробелы, взять первые ~40 слов как черновик.
  - `sep = " — " if body else ""`.
  - `raw = subject + sep + body`.
  - `second_line = _trim_by_word(raw, max_len=150)`: если `len(raw) <= 150` — как есть; иначе обрезать до последнего пробела в первых 149 символах и добавить `…`. Если пробелов нет — жёсткий срез `raw[:149] + "…"`.
- `owa_link` — из `owa.build_link(item.id)`.

`format_urgent_ex(lines)`:
- 0 писем → `""`.
- 1 письмо → `"🔴 " + line`.
- N писем → `f"🔴 Exchange · СРОЧНО · {N}\n\n" + "\n\n───\n\n".join(lines)`.

`format_digest_ex(lines)`:
- 0 → `""`.
- N → `f"📧 Exchange · {N} писем\n\n" + "\n\n".join(lines)`.

Разделители подобраны так же, как в MFL `format_urgent`/`format_digest` — единый визуальный язык.

---

## §8. Watermark в state.json — новые ключи

Добавляются к существующему `MoveFromLoop/state/watermark.json`, старые ключи не трогаются.

| Ключ | Тип | Смысл | TTL |
|---|---|---|---|
| `exchange_urgent_last_ts` | int (ms) | верхняя граница обработанных срочных | — |
| `exchange_digest_last_ts` | int (ms) | то же для дайджеста | — |
| `exchange_urgent_seen_ids` | `[{"id": str, "ts": int}]` | письма, ушедшие срочным (для де-дубля дайджеста) | 48 ч |
| `exchange_user_cache` | `{login: {"email": str, "ts": int}}` | резолв login→email из contacts.enc | 24 ч |
| `exchange_person_cache` | `{email: {"val": bool, "ts": int}}` | результат person-check | 24 ч |

**Первый запуск (для КАЖДОГО из urgent/digest независимо):** если ключа `exchange_urgent_last_ts` (или `_digest_`) НЕТ в state → записать `now_ms()`, сохранить, вернуть `""`. Историю Inbox не тянем.

**Атомарная запись:** через существующий `State.save()` — единый файл, одна атомарная замена `os.replace`. Гонок нет: MFL и ExchangeMonitor работают последовательно в одном процессе одного `mfl_*` скрипта.

---

## §9. `loop_rules.yaml` — добавить секцию

В хвост существующего файла (обратно-совместимо):

```yaml
# ─── Exchange monitoring ─────────────────────────────────────────
exchange_enabled: true
exchange_inbox_folder: Inbox
exchange_urgent_limit: 200
exchange_digest_limit: 500
```

`urgent_contacts` — те же login-и Loop; ExchangeMonitor резолвит их в email через `contacts.enc`, отдельного списка email не заводим.

---

## §10. Тест-кейсы (по модулям)

### `test_person_checker.py`
- 12 кейсов BOT_MARKERS в email (по одному на каждый маркер + `no-reply@corp` + `donotreply@x` + `NOREPLY@X.COM` (регистр)).
- Contacts hit: fake store, `get_contact_by_email` возвращает dict → `True`.
- Contacts miss + `sender.name = "Малый Денис"` → `True`.
- Contacts miss + `sender.name = "Jira Automation"` (маркер в имени) → `False`.
- Contacts miss + `sender.name` совпадает с email → `False`.
- Contacts miss + `sender.name is None` → `False`.
- Регистронезависимость email (mixed case).
- Кеш: второй вызов не идёт в contacts_store (мок с счётчиком).

### `test_tagger.py`
- to=[me] cc=[] → `(приватное)`.
- to=[me, other] cc=[] → `""`.
- to=[other] cc=[me] → `(личное)`.
- to=[me] cc=[me] → `""` (странно; правило «not in cc» блокирует приватное; в личное не попадёт т.к. «me in to»).
- to=[] cc=[] (BCC) → `""`.
- Регистр email.

### `test_formatter.py`
- Обрезка по границе слова на 150.
- Пустая тема → `(без темы)`.
- Схлопывание `\n` в теме и теле.
- Вырезка цитат `> `.
- Вырезка подписи после `-- \n`.
- Europe/Moscow TZ: приём EWSDateTime UTC → отображение +03:00.
- `tag=""` → нет префикса.
- `format_urgent_ex` / `format_digest_ex` пустой список → `""`.
- `format_urgent_ex` 1 письмо vs N писем.

### `test_owa.py`
- URL-encoding для `+`, `/`, `=` в `item.id` (base64 EwsId).
- Кастомная база (`base` параметр).

### `test_ex_state.py`
- Round-trip watermark: set → save → load → get.
- `get_urgent_watermark` на пустом state → `None` (первый запуск).
- `mark_seen` + `is_seen` работают.
- `prune_ex`: seen_id старше 48 ч удаляется; user_cache старше 24 ч удаляется; person_cache старше 24 ч удаляется.
- Соседство с MFL-ключами: `seen_ids`, `user_cache` Loop не трогаются.

### `test_fetcher_smoke.py` (`@pytest.mark.integration`)
- Реально коннектится к `cas.tutu.ru`, читает 5 последних писем, ассертит что у каждого есть `id`, `sender.email_address`, `datetime_received`, `subject is not None`. Использует tmp state, не боевой.

---

## §11. Порядок реализации для Sonnet (фазы)

### Фаза 0 — окружение (НЕ было в брифе, но обнаружено на плане)
- Создать venv: `python3 -m venv /home/tkachenkoav/USERTOOLS/ExchangeMonitor/.venv`.
- `pip install -r requirements.txt` в этот venv.
- Проверить: `.venv/bin/python -c "import exchangelib; print(exchangelib.__version__)"` — ожидается `5.6.x`.
- **Отдельная задача Саши:** решить, куда ставить exchangelib для боевого запуска (mfl_*.py используют `/usr/bin/python3.11`, куда `exchangelib` нужно поставить, либо переключить cron на venv). Без этого патч MFL не заработает в бою. См. Питфолл 12.1.
- Прогнать `ExchangeMeeting/create_meeting.py` из venv для подтверждения живости EWS.

### Фаза 1 — EWS + чтение Inbox
- `config.py`, `client.py`, `fetcher.py`, `owa.py`.
- Deliverable: `python -m exchangemonitor.fetcher --last 5` печатает 5 последних писем.

### Фаза 2 — фильтры
- `person_checker.py`, `tagger.py`.
- Deliverable: `pytest tests/test_person_checker.py tests/test_tagger.py` — зелёный.

### Фаза 3 — формат + state
- `formatter.py`, `ex_state.py`.
- Deliverable: `pytest tests/test_formatter.py tests/test_owa.py tests/test_ex_state.py` — зелёный.

### Фаза 4 — оркестраторы
- `urgent.py`, `digest.py`.
- Deliverable: локальный dry-run с копией state в `/tmp/watermark_dryrun.json` — обе функции возвращают строку либо `""`, повторный запуск сразу — `""`.

### Фаза 5 — интеграция + прод
- Патч `~/.hermes/scripts/mfl_urgent_check.py` и `mfl_digest.py` (см. §2).
- Добавить секцию в `loop_rules.yaml` (см. §9).
- Ручной прогон обоих скриптов (`no_agent=true` — stdout сразу в Telegram).
- Подтверждение Саши.

---

## §12. Питфоллы (актуальные для реализации)

**12.1 `exchangelib` не установлен.** Живая проверка EWS на этапе плана НЕ прошла — модуля нет ни в одном системном Python, у `ExchangeMeeting` нет своего venv. ТЗ утверждает обратное. До фазы 1 необходимо решить, где именно живёт python для ExchangeMonitor и как его вызывают из `mfl_*.py` в проде (сейчас cron дергает `/usr/bin/python3.11`). Варианты: (а) поставить exchangelib глобально в `/usr/bin/python3.11`; (б) перенастроить cron на `ExchangeMonitor/.venv/bin/python`; (в) shim-скрипт с shebang на venv. Решение — за Сашей.

**12.2 EWS сессия — singleton только в процессе.** Cron поднимает свежий процесс каждые 3 минуты — сессия не переиспользуется между тиками. Это ок, но за минуту-две логина к CAS может уходить заметное время → закладывать таймаут ≤ 90с на open+fetch, иначе Telegram-минута протухнет.

**12.3 `item.text_body` может быть `None` или очень большим.** Обрабатывать None; из большого тела читаем только начало (в `.only(...)` включён, но exchangelib грузит целиком). Оптимизация — использовать `.only('id','subject','sender','to_recipients','cc_recipients','datetime_received')` и отдельным запросом дозагружать `text_body` только для прошедших фильтр писем. Решение — по факту скорости в Фазе 1.

**12.4 Time zone mismatch.** `datetime_received` из EWS — timezone-aware UTC. `EWSDateTime.from_datetime(datetime.fromtimestamp(ms/1000, tz=timezone.utc))` — правильный способ построить фильтр. **Не** использовать наивные datetime — exchangelib кинет `NaiveDateTimeNotAllowed`.

**12.5 OWA ссылка может не открывать письмо.** Формат `?ItemID=...&exvsurl=1&viewmodel=ReadMessageItem` — deep-link для OWA 2013/2016. Проверка в Фазе 3 на первом реальном письме — открывается ли по клику. Если нет — Фаза 2 из ТЗ §8: ConvertId → OwaId (отдельный тикет).

**12.6 EwsId содержит символы `/`, `+`, `=`.** Обязательно `urllib.parse.quote(item.id, safe='')` (без safe-символов), иначе OWA получит битый ID.

**12.7 Первый запуск после долгого простоя.** Watermark ставим в `now_ms()`, историю не тянем. Иначе после недели простоя первый прогон отправит в Telegram сотни писем. Явно закреплено в §8.

**12.8 Basic-auth на CAS.** Если ТУТУ отключит Basic на `cas.tutu.ru` — сломается и `ExchangeMeeting`, и `ExchangeMonitor` одновременно. Наблюдение за stderr `[urgent_check] Exchange FAIL: ...` — уже есть в патче §2.

**12.9 `contacts.enc` не содержит нового сотрудника.** Тогда person-check пройдёт по `sender.name`-ветке; тег `(приватное)` посчитается корректно; ФИО в шапке будет `sender.name`, не «Фамилия Имя» из HR. Приемлемо.

**12.10 `urgent_contacts` — Loop-login, не email.** Резолв — обязательно, кеш `exchange_user_cache` TTL 24 ч. Если login не найден в contacts.enc → отсутствует в urgent-фильтре (тихо), warning в stderr при отсутствии ВСЕХ.

**12.11 Дедупликация срочный↔дайджест.** `mark_seen` вызывает ТОЛЬКО `urgent.py`. Дайджест читает `is_seen` и пропускает. Если срочный упал до `state.save()` — письмо приедет в дайджест (это ок, не пропадёт).

**12.12 seen_ids раздуваются при простое.** TTL 48 ч в `prune_ex`. При простое >48 ч возможно дублирование срочный+дайджест на пограничных письмах — задокументировано и принято.

**12.13 `sender.email_address` может быть `None`.** Для системных Exchange-объектов (напр., «Undeliverable»). Обрабатывать: `email = (item.sender.email_address or "").lower()`; пустая строка → отбрасывается по BOT_MARKERS не пройдёт, зато не пройдёт contacts-hit и sender.name-check → `False`. Явно проверить в тесте.

**12.14 Ошибки записи state.** MFL уже пишет state — если Exchange упадёт с исключением до `state.save()`, Loop-часть тоже не сохранится. Поэтому Exchange-блок в orchestrator обёрнут в try/except **внутри** `run_*_exchange` (fail-quiet), и в `mfl_*_check.py` — второй try/except как страховка. Двойная обёртка — сознательное решение.

**12.15 Пустой `to_recipients`/`cc_recipients` в EWS.** exchangelib отдаёт `None`, не `[]`. `tagger` использует `(item.to_recipients or [])` — обязательно.

---

## §13. Готовность к передаче Sonnet

- Все интерфейсы модулей описаны.
- Все алгоритмы разложены до уровня «шаг → файл/функция».
- Формат state и патча MFL зафиксирован.
- Тест-кейсы перечислены.
- Питфоллы обновлены с учётом ТЗ + обнаруженного расхождения по exchangelib.
- Одна открытая позиция для Саши: где живёт python с exchangelib для прод-запуска (Фаза 0, Питфолл 12.1).
