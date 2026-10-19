---
name: ExchangeMonitor
version: 0.3.1
status: draft
created: 2026-07-24
updated: 2026-10-19
author: Opus
depends_on: [MoveFromLoop, AnywhereContacts, ExchangeMeeting]
---

# ExchangeMonitor — ТЗ

## Контракты экосистемы

### Источник истины
- Владелец почтовых данных: `api_exchange` (`cas.tutu.ru`, Exchange EWS Inbox `tkachenkoav@tutu.ru`)
- Владелец контактов: AnywhereContacts (`contacts.enc`)
- Владелец правил и состояний: MoveFromLoop (`loop_rules.yaml`, `state/watermark.json`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| item.id | str | required | api_exchange | EwsId сообщения Exchange |
| item.subject | str | optional | api_exchange | Тема письма |
| item.sender.email_address | str | required | api_exchange | Email отправителя |
| item.sender.name | str | optional | api_exchange | DisplayName отправителя |
| item.datetime_received | datetime(iso8601) | required | api_exchange | Время получения письма |
| item.text_body | str | optional | api_exchange | Текст письма (plain text) |
| fio | str | optional | AnywhereContacts | ФИО контакта |
| email | str | required | AnywhereContacts | Email контакта |
| urgent_contacts | str | required | MoveFromLoop | Список логинов срочных контактов |
| exchange_urgent_last_ts | int | optional | MoveFromLoop | Watermark срочных писем (ms) |
| exchange_digest_last_ts | int | optional | MoveFromLoop | Watermark дайджеста писем (ms) |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| text | str | api_telegram | Срочные уведомления / дайджест писем в Telegram |
| exchange_urgent_last_ts | int | MoveFromLoop | Watermark срочных писем (ms) |
| exchange_digest_last_ts | int | MoveFromLoop | Watermark дайджеста писем (ms) |
| tool | str | ErrorBus | "ExchangeMonitor" |
| message | str | ErrorBus | Сообщение об ошибке |

### Зависимости
- Получает от: [api_exchange, AnywhereContacts, MoveFromLoop]
- Отдаёт: [api_telegram, MoveFromLoop, ErrorBus]

### Breaking changes policy
- Версионирование формата: версионирование полей `exchange_*` в `watermark.json` и формата stdout в `mfl_*`
- При breaking change EWS: обновление `exchangelib` и логики в `exchangemonitor/client.py`

### Границы («что НЕ трогать»)
- Не удалять и не менять статус писем в Inbox Exchange (read-only опрос)
- Не изменять оригинальные ключи MoveFromLoop в `loop_rules.yaml` и `watermark.json`
- Не выбрасывать необработанных исключений из `run_urgent_exchange` / `run_digest_exchange` (fail-quiet режим)

## §1. Цель и контекст

Exchange (`cas.tutu.ru`, OWA `https://cas.tutu.ru/owa`) — основной канал деловой коммуникации в ТУТУ. Задача инструмента — обеспечить, чтобы **ни одно письмо от реального сотрудника не пропало мимо Саши** и было доставлено в Telegram теми же двумя каналами, которыми уже ходит Loop-мониторинг (`MoveFromLoop`, далее MFL):

- **срочный режим** — раз в 3 минуты, только письма от контактов из `urgent_contacts`;
- **дайджест** — раз в час, все письма от реальных людей за интервал.

Ключевые интеграции:

- `AnywhereContacts` — источник истины для проверки «реальный сотрудник» (email → contacts.enc).
- `ExchangeMeeting` — уже отработанная авторизация через `exchangelib` (EWS, Basic-auth, доменные креды из `~/.config/hermes/.env`).
- `MoveFromLoop` — общий кронтик и общий `state/watermark.json`. ExchangeMonitor подключается в **те же** entry-скрипты (`~/.hermes/scripts/mfl_urgent_check.py`, `mfl_digest.py`) и **дописывает свой блок** к их stdout.

Проверено при подготовке ТЗ (24.07.2026): `exchangelib==5.6.0`, `TUTU_DOMAIN_PASSWORD` в `~/.config/hermes/.env` присутствует, `ExchangeMeeting/create_meeting.py` рабочий, `MoveFromLoop/state/watermark.json` содержит `urgent_last_ts` / `digest_last_ts` в **миллисекундах** (важно — см. §10 про несоответствие форматов времени).

## §2. AS-IS

- `USERTOOLS/ExchangeMeeting/create_meeting.py` — единственный код Exchange. Умеет только создание встречи и `get_free_busy_info`. Читать почту не умеет.
- Авторизация: `Credentials(username=..., password=...)` + `Configuration(server="cas.tutu.ru")` + `Account(primary_smtp_address="tkachenkoav@tutu.ru", autodiscover=False, access_type=DELEGATE)`. Порядок попыток username: `tkachenkoav@tutu.ru` → `TUTU\tkachenkoav` → `tkachenkoav`. Этот блок переиспользуется.
- `exchangelib` версии **5.6.0** установлен в системном Python 3.11 (глобально; тот же интерпретатор, которым запускаются `mfl_*` скрипты).
- `MoveFromLoop/state/watermark.json` — единый state-файл, атомарная запись через `os.replace`. Ключи `urgent_last_ts`/`digest_last_ts` хранятся как **int miliseconds since epoch** (см. `movefromloop/state.py`). ExchangeMonitor **обязан следовать той же схеме** (миллисекунды, не ISO-строка — расхождение с исходным брифом Q8, зафиксировано осознанно, см. §10).
- Entry-скрипты MFL лежат в `~/.hermes/scripts/mfl_urgent_check.py` и `~/.hermes/scripts/mfl_digest.py`; вкладывают `USERTOOLS/MoveFromLoop` в `sys.path` и вызывают `run_urgent(...)` / `run_digest(...)`. Оба — `no_agent=true`, stdout уходит прямо в Telegram.

## §3. TO-BE — архитектура

### 3.1 Раскладка модуля

```
USERTOOLS/ExchangeMonitor/
  exchangemonitor/
    __init__.py
    config.py           # чтение loop_rules.yaml (общий конфиг), .env
    client.py           # EWS-клиент: авторизация, singleton-сессия, ретраи
    fetcher.py          # чтение Inbox: список писем с datetime_received > watermark
    person_checker.py   # «реальный человек»: contacts.enc + DisplayName + черный список
    tagger.py           # тег: (приватное) / (личное) / без тега
    formatter.py        # форматирование одного письма → строка для Telegram
    owa.py              # построение OWA-ссылки из item.id
    urgent.py           # run_urgent_exchange(rules_path, state_path) -> str
    digest.py           # run_digest_exchange(rules_path, state_path) -> str
  tests/
    test_person_checker.py
    test_tagger.py
    test_formatter.py
    test_owa.py
    test_fetcher_smoke.py   # опциональный smoke, помечен @pytest.mark.integration
  requirements.txt      # exchangelib>=5.6, pyyaml, python-dotenv
  pyproject.toml
  README.md
```

### 3.2 Публичный API (то, что импортируется наружу)

```python
from exchangemonitor.urgent import run_urgent_exchange
from exchangemonitor.digest import run_digest_exchange

# Оба возвращают строку (может быть пустой '') — блок для stdout Telegram-сообщения.
# Оба не выбрасывают наружу неотловленных исключений в happy-path;
# всё, что упало — логируется в stderr и функция возвращает '' (fail-quiet).
```

Инвариант: возвращаемая строка НЕ содержит хвостового `\n` и НЕ содержит своего заголовка/разделителя от MFL — MFL-скрипт сам решает, как склеить.

### 3.3 Способ интеграции в MFL — решение

Из двух вариантов брифа выбран **вариант B: отдельный импорт из `exchangemonitor` в существующих `mfl_*.py`**. Причина — держать домены раздельно, чтобы ExchangeMonitor можно было выключить одним флагом (`exchange_enabled: false` в `loop_rules.yaml`) без правок MFL-логики.

Патч для `~/.hermes/scripts/mfl_urgent_check.py` (аналогично для digest):

```python
# после существующего вычисления result = run_urgent(...)
try:
    sys.path.insert(0, "/home/tkachenkoav/USERTOOLS/ExchangeMonitor")
    from exchangemonitor.urgent import run_urgent_exchange
    ex_block = run_urgent_exchange(RULES_PATH, STATE_PATH)
except Exception as exc:
    print(f"[urgent_check] Exchange FAIL: {exc}", file=sys.stderr)
    ex_block = ""

parts = [p for p in (result, ex_block) if p]
if parts:
    print("\n\n".join(parts))
```

Точно тот же приём в `mfl_digest.py`. Больше нигде правок нет.

## §4. Алгоритм срочного режима (`run_urgent_exchange`)

1. Загрузить `loop_rules.yaml`. Если `exchange_enabled != true` — вернуть `''`.
2. Открыть/загрузить `state/watermark.json`; прочитать `exchange_urgent_last_ts` (миллисекунды). Если ключа нет — **первый запуск**: не читаем историю, только фиксируем `now_ms()` в watermark и возвращаем `''`.
3. Собрать множество `urgent_emails`:
   - Для каждого `login` из `urgent_contacts`: найти запись в `contacts.enc` по `sources.loop.username == login` → взять `email`.
   - Если ни для одного login не резолвится email — предупреждение в stderr, возврат `''` (не спамим, но и не молчим).
   - Кэш login→email хранить в `state.data["exchange_user_cache"]` с TTL 24 ч (по аналогии с `user_cache` MFL).
4. Открыть Exchange-сессию (`client.get_account()` — singleton в рамках одного процесса).
5. Fetch Inbox: `account.inbox.filter(datetime_received__gt=<from_ts>).order_by('-datetime_received').only('id', 'subject', 'sender', 'to_recipients', 'cc_recipients', 'datetime_received', 'text_body')[:200]`. Лимит 200 — защита от накопления при простое.
6. Для каждого письма:
   a. `email = item.sender.email_address.lower()`; если `email not in urgent_emails` — пропустить.
   b. Person-check (§6) — на случай, если email в urgent_contacts, но помечен как бот (крайний edge — пропускаем).
   c. Определить тег (§7), форматировать (§7).
7. Обновить `exchange_urgent_last_ts = max(datetime_received среди обработанных).timestamp() * 1000` (или `now_ms()`, если писем не было — двигаем по времени всегда, чтобы не тащить хвост).
8. Сохранить state атомарно.
9. Вернуть строки, склеенные `"\n\n"`. Пустой список → `''`.

## §5. Алгоритм дайджеста (`run_digest_exchange`)

1. `exchange_enabled` check (см. §4.1).
2. `from_ts = state.exchange_digest_last_ts` (первый запуск — `now_ms()`, вернуть `''`).
3. Fetch Inbox с тем же `.only(...)` (лимит 500).
4. Отфильтровать: person-check (§6) — берём все от реальных людей.
5. **Де-дубль со срочным**: если письмо уже отдавалось срочным (по `item.id`) — не включать в дайджест. Хранить `exchange_urgent_seen_ids` в state (список `{"id": ..., "ts_ms": ...}`, TTL 48 ч), пополнять в `run_urgent_exchange` шаг 6.c, чистить `prune()`.
6. Форматировать (§7), обновить watermark, вернуть склеенное. Если пусто — `''` (не добавляем заголовок «Exchange: пусто»).

## §6. Проверка «реальный человек» (`person_checker.py`)

Порядок фильтров (первое сработавшее — вердикт):

1. **Служебные адреса — сразу отбросить.** Если `email` содержит подстроки: `noreply`, `no-reply`, `donotreply`, `notification`, `notifications`, `alert`, `alerts`, `system`, `bot`, `jira`, `confluence`, `jenkins`, `bamboo`, `mailer-daemon`, `postmaster`, `automation`, `builds`, `ci-`, `gitlab`, `github` — вернуть `False`. Список вынести в `person_checker.BOT_MARKERS` (константа модуля), тесты покрывают.
2. **contacts.enc**: если email найден в `contacts.enc` (поле `email`, регистр-независимо) → `True`.
3. **DisplayName из Exchange**: `sender.name` уже приходит в `item.sender` (не требует отдельного `resolve_names()` — важное отличие от исходной формулировки брифа §6.2, см. «Питфоллы EWS»). Если `sender.name` непустой, не совпадает с email и не проходит по BOT_MARKERS (проверить и `name.lower()` тоже) → `True`.
4. Иначе — `False`.

Отдельный `resolve_names()` вызывается **только** если `sender.name` пустой (редко, для внешних SMTP): `account.protocol.resolve_names(email, return_full_contact_data=True)`. Fail-soft: любая ошибка → `False`.

## §7. Формат уведомления и тегирование

### 7.1 Теги (`tagger.py`)

`me_email = "tkachenkoav@tutu.ru"`.

- `to = [r.email_address.lower() for r in item.to_recipients or []]`
- `cc = [r.email_address.lower() for r in item.cc_recipients or []]`
- Правила:
  - `me_email in to` **и** `len(to) == 1` **и** `me_email not in cc` → `(приватное)`;
  - `me_email in cc` **и** `me_email not in to` → `(личное)`;
  - `me_email in to` **и** `len(to) > 1` → без тега;
  - иначе (странный случай — я ни в To, ни в CC, например BCC) → без тега.

### 7.2 Строка (`formatter.py`)

```
📧 {tag_prefix}от {ФИО} [ЧЧ:ММ]
{subject}{sep}{body_snippet}
🔗 {owa_link}
```

- `tag_prefix` = `"(приватное) "`, `"(личное) "` или `""`.
- `ФИО` — берём из `contacts.enc` (поле `fio`), если резолвится по email; иначе `item.sender.name`; иначе `email`.
- `ЧЧ:ММ` — по `Europe/Moscow` (`item.datetime_received.astimezone(EWSTimeZone("Europe/Moscow"))`).
- `subject` — `item.subject or "(без темы)"`, схлопнуть переводы строк и повторные пробелы.
- `body_snippet` — первые слова `item.text_body` (не HTML!): убрать цитаты (`> `), подписи после `-- \n`, схлопнуть пробелы.
- `sep` — `" — "` если `body_snippet` непустой, иначе `""`.
- Общая длина второй строки (`subject + sep + body_snippet`) — **≤ 150 символов, обрезка по границе слова**, суффикс `…`.
- `owa_link` — см. §8.

Пустая строка между письмами при склейке (`"\n\n".join(...)`).

## §8. OWA-ссылка (`owa.py`)

Известные питфоллы OWA 2016 (`cas.tutu.ru` — старый Exchange, судя по OWA-пути):

- Прямой формат `https://cas.tutu.ru/owa/#path=/mail/inbox/<ItemID>` **не работает** без активной сессии — но у Саши OWA всегда открыта, так что кликабельная ссылка приемлема.
- `item.id` в EWS — это `EwsId` (base64, ~150 символов), а OWA принимает `OwaId` (короче). Конверсия — через `ConvertId` EWS-операцию:

```python
from exchangelib.services import ConvertId  # или ручной SOAP, если версия не даёт
```

**Первая реализация (Фаза 1)** — использовать простую форму, которая гарантированно открывает Inbox с фокусом на письме:

```
https://cas.tutu.ru/owa/?ItemID=<url_encoded item.id>&exvsurl=1&viewmodel=ReadMessageItem
```

Это стандартный «deep link» OWA 2013/2016. Если у Саши окажется, что не работает — Фаза 2: конверсия через `ConvertId` в `OwaId` и построение `#path=/mail/inbox/<OwaId>`. Ссылка формируется в `owa.build_link(item_id: str) -> str`, покрыта unit-тестом на url-encoding.

## §9. Интеграция с `loop_rules.yaml`

В существующий `MoveFromLoop/loop_rules.yaml` добавляются поля (обратно-совместимо, отсутствие = дефолт):

```yaml
# ─── Exchange monitoring ─────────────────────────────────────────
exchange_enabled: true            # true|false — общий флаг
exchange_inbox_folder: Inbox      # только Inbox (Q10)
exchange_urgent_limit: 200        # safety cap на fetch
exchange_digest_limit: 500
# urgent_contacts переиспользуются как есть (login-и Loop → резолвим в email через contacts.enc)
```

Секции `urgent_contacts`, `my_username`, `keywords`, `watch_channels` **не трогаем** — они принадлежат Loop-домену. Резолв login→email инкапсулирован в ExchangeMonitor.

## §10. Watermark и state

Общий файл: `~/USERTOOLS/MoveFromLoop/state/watermark.json`. Добавляемые ключи:

| Ключ | Тип | Смысл |
|---|---|---|
| `exchange_urgent_last_ts` | int (ms since epoch) | верхняя граница обработанных срочных писем |
| `exchange_digest_last_ts` | int (ms since epoch) | то же для дайджеста |
| `exchange_user_cache` | `{login: {email, ts}}` | кеш login→email из contacts.enc, TTL 24 ч |
| `exchange_urgent_seen_ids` | `[{id, ts_ms}, ...]` | письма, ушедшие срочным (для де-дубля в дайджесте), TTL 48 ч |
| `exchange_confluence_watch` | `{ids: [...], titles: [...], ts}` | кеш allowlist поддеревьев Confluence (pageId и titles), TTL 6 ч |

**Важное расхождение с брифом Q8**: бриф говорит «ISO datetime». Реальность — MFL хранит миллисекунды. Единство формата важнее, поэтому фиксируем **миллисекунды**. Конверсия из EWS: `int(item.datetime_received.timestamp() * 1000)`.

**Первый запуск**: если ключа `exchange_*_last_ts` в state нет — записать `now_ms()` и вернуть `''`. Историю Inbox не тянем (может быть тысячи писем).

Атомарная запись — переиспользовать `movefromloop.state.State` (расширить, не форкать): добавить методы `get_exchange_urgent_watermark` / `set_...` в отдельном mixin или сделать «тонкую надстройку» в `exchangemonitor.state`, которая принимает уже загруженный `State`. Реализация — на усмотрение Фазы 1, тест-кейс покрывает round-trip.

**Гонка**: MFL и ExchangeMonitor вызываются последовательно в одном процессе одного и того же mfl_* скрипта → state загружается один раз, обе части пишут в один объект, save в конце. Никакой конкурентной записи нет.

## §11. Тест-кейсы

Unit (без сети):

- `test_person_checker.py` — bot-markers (12 кейсов), contacts-hit, sender.name-fallback, пустой sender.name → False, регистронезависимость email.
- `test_tagger.py` — 4 матрицы (to-only-1, to-many, cc-only, оба; странный BCC).
- `test_formatter.py` — обрезка по границе слова на 150, `(без темы)`, схлопывание \n, вырезка `>`-цитат, вырезка signature `-- \n`, Europe/Moscow timezone.
- `test_owa.py` — url-encoding для `+`, `/`, `=` в `item.id`.
- `test_state.py` — round-trip новых ключей, первый запуск = watermark в now, TTL prune для `exchange_urgent_seen_ids` и `exchange_user_cache`.

Integration (помечены `@pytest.mark.integration`, запускаются вручную):

- `test_fetcher_smoke.py` — реальный вход в Exchange, чтение последних 5 писем Inbox, проверка что поля `sender/to/cc/datetime_received/text_body` заполняются. НЕ трогает watermark (использует tmp state).
- `test_end_to_end_dry.py` — прогон `run_urgent_exchange` на копии state в /tmp, вывод — только в stdout, ничего не отправляется. Проверка что запуск дважды подряд второй раз возвращает `''`.

## §12. Фазы реализации (для Sonnet)

| Фаза | Содержание | Deliverable |
|---|---|---|
| 1 | `client.py` + `fetcher.py` + smoke-тест чтения Inbox | скрипт `python -m exchangemonitor.fetcher --last 5` печатает 5 последних писем |
| 2 | `person_checker.py` + `tagger.py` + unit-тесты | зелёные `pytest tests/test_person_checker.py test_tagger.py` |
| 3 | `formatter.py` + `owa.py` + `state`-расширения | зелёный `pytest`, ручная проверка ссылки в OWA |
| 4 | `urgent.py` + `digest.py` + `config.py` | `run_urgent_exchange` / `run_digest_exchange` возвращают корректную строку на dev-mailbox |
| 5 | Патч `~/.hermes/scripts/mfl_urgent_check.py` и `mfl_digest.py`, добавление секции в `loop_rules.yaml`, интеграционный dry-run | подтверждение Саши, что срочные приходят и дайджест содержит блок Exchange |

## §13. Решения брифа (24.07.2026)

| Q | Решение |
|---|---|
| Q1 | Inbox на `tkachenkoav@tutu.ru`. |
| Q2 | Реальный человек = есть в `contacts.enc` по email, ИЛИ `DisplayName` (`item.sender.name`) заполнен, не совпадает с email и не подпадает под BOT_MARKERS (§6). |
| Q3 | Срочные — тот же список `urgent_contacts` из `loop_rules.yaml` (login-и Loop, резолв в email через `contacts.enc`). Дайджест — все письма от реальных людей. |
| Q4 | `(приватное)` = только я в To; `(личное)` = я в CC (и не в To); без тега = я в To вместе с другими. |
| Q5 | Те же кроны MFL — `mfl_urgent_check.py` и `mfl_digest.py`. Exchange проверяется в том же тике, отдельным блоком stdout. |
| Q6 | Формат: `📧 (тег) от ФИО [ЧЧ:ММ]\n{тема — первые слова тела ≤150 симв}\n🔗 {OWA}`. |
| Q7 | OWA: `https://cas.tutu.ru/owa`. Ссылка на письмо — deep-link с `ItemID` (§8). |
| Q8 | Watermark — по времени последней проверки в общем `state/watermark.json` MFL. **Формат — миллисекунды (int)**, а не ISO-строка, чтобы совпадать с существующей схемой MFL (сознательное отклонение от текста брифа). |
| Q9 | Фильтр только «реальный человек». BCC/List-Unsubscribe не проверяем. |
| Q10 | Только Inbox, без вложенных папок. |

## §14. Открытые вопросы / риски

1. **OWA-ссылка**: гарантированный ли `ItemID`-deep-link работает на `cas.tutu.ru`? — валидируется в Фазе 3 руками. Fallback описан (`ConvertId` → OwaId).
2. **Basic-auth**: если ТУТУ отключит Basic на CAS, весь стек (`ExchangeMeeting` + `ExchangeMonitor`) встанет одновременно. Мониторить логи, план миграции на OAuth — за пределами этого ТЗ.
3. **Throttling EWS**: 3-минутный опрос Inbox — маленькая нагрузка, но каждый тик открывает сессию. `client.py` реализует **singleton в рамках процесса** (не между вызовами cron). Между тиками кэша нет — это ок.
4. **contacts.enc обновляется отдельным инструментом**: если email нового сотрудника ещё не в базе, письмо пойдёт в дайджест только через DisplayName-ветку. Это ожидаемое поведение.
5. **exchange_urgent_seen_ids** может расти при простое дайджеста > 48 ч — TTL prune решает, но если MFL-крон не запускается неделю, оба watermark отъедут, seen_ids протухнут, часть писем задублируется срочным+дайджестом. Приемлемо.

## §15. Доработка 31.08.2026 — bk-170: баг «письма Ollama проходят в дайджест»

### Симптом
В часовых дайджестах `📧 (приватное) от Ollama` повторно показывается после двух прогонов (крон MoveFromLoop — дайджест, job 2865cc674493; 31.08 08:00/09:01/10:00, письмо от 29.08 05:23; также 26.08).

### Root cause
В `exchangemonitor/person_checker.py`, `is_real_person()` порядок проверок:
```
0. cache-hit → если email в exchange_person_cache, вернуть кэшированный результат
1. is_external_sender(email)  ← внешняя фильтрация
```
В `state/watermark.json` → `exchange_person_cache` адрес `hello@ollama.com` закеширован `val:true` (ts≈27.08). Проверка external стоит ПОСЛЕ cache → для Ollama всегда возвращается `True` из кеша, external-блок не выполняется. Тот же класс бага, что `hq@tutu.ru` contacts short-circuit. В кеше также `hotel@tutu.ru:true` и `hq@tutu.ru:true`.

### Решение (детерминированный False не проигрывает кешу)
В `is_real_person()` порядок становится:
1. `is_external_sender(email)` → сразу `False` (НЕ читать и лучше НЕ писать кеш).
2. `_has_bot_marker(email)` → сразу `False` (тот же класс бага: stale `True` переживает новый маркер). Раньше bot стоял после кеша — дыра того же типа, чинится в этом же диффе.
3. cache-hit.
4. contacts / `sender_name` — как сейчас, с `_return` в кеш.

**`hq@tutu.ru` НЕ добавлять в `EXTERNAL_SENDER_EMAILS`**: его нет в списке, Confluence-письма (bk-171) должны проходить `is_real_person`. Это другой баг (contacts short-circuit), его закрывает `confluence_filter`.

**Инвалидация кеша (гигиена, не требуется для корректности после переноса):** в `get_person_cache()` отбрасывать ключи, для которых `is_external_sender(email)` — тогда `hello@ollama.com` и `hotel@tutu.ru` исчезнут к ближайшему save. `hq@tutu.ru` не трогать.

### Изменяемые файлы
| Файл | Что |
|---|---|
| `exchangemonitor/person_checker.py` | Порядок проверок; hard-False без записи в кеш |
| `exchangemonitor/ex_state.py` | В `get_person_cache` фильтр `is_external_sender` |
| `tests/test_person_checker.py` | Новый инвариант + регрессия bot vs stale cache |
| `tests/test_ex_state.py` | Кеш не возвращает external-ключи |
| `MoveFromLoop/state/watermark.json` | Не править руками |

Не трогать: `urgent.py`, `digest.py`, `config.py`, `confluence_filter.py`.

### Порядок шагов
1. Тест, который сейчас красный: `cache={"hello@ollama.com": True}` → `is_real_person(...) is False`.
2. Перенос external (+ bot) перед cache в `person_checker.py`.
3. Фильтр в `get_person_cache`.
4. Дописать остальные тесты, прогнать pytest.

### Тесты (инварианты)
- External бьёт stale cache: `hello@ollama.com`/`hotel@tutu.ru` при `cache[email]=True` → `False`.
- External бьёт contacts — уже есть `test_external_sender_overrides_contacts`, оставить.
- Bot бьёт stale cache: `noreply@x.com` при `cache[...]=True` → `False`.
- Кеш жив для людей: `test_cache_hit_no_store_call` (`user@tutu.ru`) без изменений.
- `get_person_cache`: в state есть `hello@ollama.com:true` — в возврате ключа нет.
- Регрессия substring: `user@notcursor.com` по-прежнему `True`.

### Верификация
```
cd /home/tkachenkoav/USERTOOLS/ExchangeMonitor
python3 -m pytest tests/test_person_checker.py tests/test_ex_state.py -q
```
Ручной прогон: `python3 ~/.hermes/scripts/mfl_digest.py` (или дождаться крона 2865cc674493). В stdout не должно быть `от Ollama`. После прогона в `watermark.json` нет `hello@ollama.com` с `val:true`.

### Риски
- Urgent: тот же `is_real_person` + тот же кеш. Ollama в `urgent_contacts` нет — срочное поведение не меняется. Keyword-путь без person-check.
- Кеш между запусками: 24h TTL больше не спасает external — список EXTERNAL_SENDER_* действует сразу.
- Import: `ex_state` → `person_checker` допустим (`person_checker` не импортирует `ex_state`). Не тащить `is_external_sender` в `digest.py`.
- Не раздувать `EXTERNAL_SENDER_*` в этом тикете (`info@email.matemarketing.ru` в кеше `true` — вне скоупа).

---

## §16. Доработка 31.08.2026 — bk-171: allowlist поддеревьев Confluence

### Хочется
Получать Confluence-уведомления о изменении страниц и всех их подстраниц, независимо от упоминания пользователя в письме, для корней:
- `https://dom.tutu.ru/pages/viewpage.action?pageId=480923430` (Trisigma проект, DPAN, 50 страниц с потомками)
- `https://dom.tutu.ru/pages/viewpage.action?pageId=467458830` («ТОЧКА СБОРКИ AI-ready Туту», DPAN, 77 страниц с потомками)

Работает ТОЛЬКО в дайджесте (digest), НЕ в срочном канале (иначе `hq@tutu.ru` зальёт срочный канал).

### Текущее поведение
`exchangemonitor/confluence_filter.py` глушит все `[confluence]`-письма (`hq@tutu.ru` + маркер), если в теме/теле нет упоминания пользователя (`ткаченко александр владимирович`/`tkachenko`/`tkachenkoav@tutu.ru` — `is_user_mentioned`). Про pageId фильтр не знает, резолва поддерева нет.

### Решение архитектора (основной сигнал — pageId из тела, НЕ путь в теме)
Отбракован вариант «матч пути в теме» (вариант 2): реальная тема письма `[confluence] Департамент аналитики и данных > {title или parent / title}` не является цепочкой REST-ancestors; у потомков «ТОЧКА СБОРКИ…» в теме нет имени корня (например «AI-аналитик. …») — substring-матч их пропустит; у Trisigma часть страниц случайно начинается с «Trisigma проект.» — ложное чувство надёжности; разделители `>` vs `/`, коллизии title.

**Основной сигнал — pageId из тела письма ∩ prefetch-множество потомков корней.**

Снятие поддерева (проверено по REST 31.08):
- `/descendant/page` на этом DC НЕ работает (ошибка API).
- Рабочий съём: `GET /rest/api/content/search?cql=(id={ROOT} OR ancestor={ROOT}) AND type=page` с пагинацией `limit=100`. Глубина — все потомки, не crawl `child/page`.

Алгоритм на письмо (только digest):
```
если не confluence-уведомление → не глушить
если is_user_mentioned → не глушить          # как сейчас
если extract_page_ids(body) ∩ cached_ids → не глушить
если pageId есть, но не в кеше → один GET ?expand=ancestors;
     self или любой ancestor ∈ {480923430, 467458830} → не глушить
     (покрывает страницу, созданную внутри TTL)
если pageId нет → fallback: последний сегмент темы
     (после `>`, затем последний `/`) exact-match по cached titles
иначе → глушить
```

Кеш: ключ `exchange_confluence_watch` в том же `watermark.json`: `{ids: [...], titles: [...], ts}`. TTL **6 ч**. Refresh в начале `_run_digest`, НЕ per-письмо. Набор ~127 id — копейки.

Парсинг pageId: все `viewpage.action?pageId=(\d+)` / `pageId=(\d+)` в `subject + text_body + body`. **Любой** id из пересечения с allowlist (первый линк часто space home `310322545` — его в множестве нет). `focusedCommentId` не считать pageId; в шаблоне комментария pageId страницы уже есть.

Токен: только `CONFLUENCE_TOKEN` (+ опционально `CONFLUENCE_URL`) из `~/USERTOOLS/ConfluenceSync/.env`, **без `source` всего файла** (баг MOFS CONF-001). HTTP — `urllib.request` (в пакете нет `requests`). Пакет `ConfluenceSync` НЕ импортировать (`usertools_env`, лишние зависимости). Новая сущность USERTOOLS не нужна.

Константа корней — в модуле, стиль `EXTERNAL_SENDER_*`, не в `loop_rules.yaml`.

**Fail-closed**: при отсутствии токена / ошибке REST — пустой allowlist, поведение = сегодня (только mention), stderr, digest не падает.

### Изменяемые файлы
| Файл | Что |
|---|---|
| **новый** `exchangemonitor/confluence_tree.py` | CQL-prefetch, ancestor-miss, загрузка токена-вызов |
| `exchangemonitor/confluence_filter.py` | `WATCH_ROOT_IDS`, `extract_page_ids`, `subject_leaf_title`, расширение `should_suppress_confluence(...)` |
| `exchangemonitor/ex_state.py` | get/save `exchange_confluence_watch` |
| `exchangemonitor/config.py` | `_load_confluence_env()` — только TOKEN/URL |
| `exchangemonitor/digest.py` | refresh дерева → передать allowlist в фильтр |
| `tests/test_confluence_filter.py` | allowlist / mention / чужое дерево |
| **новый** `tests/test_confluence_tree.py` | мок HTTP, пагинация, miss→ancestors |
| `tests/test_ex_state.py` | roundtrip кеша дерева |
| `tests/test_config.py` | токен из файла, не оверрайд env |

Не трогать: `urgent.py`, `person_checker.py`, `mfl_digest.py`, `loop_rules.yaml`, `__init__.py` (не импортировать tree на уровне пакета).

Сигнатура (иллюстрация):
```python
def should_suppress_confluence(..., watch_ids: set[str] | None = None,
                               watch_titles: set[str] | None = None) -> bool:
```
`watch_*=None` → текущее поведение (совместимость тестов).

### Порядок шагов
1. Чистые парсеры + тесты в `confluence_filter.py` (без сети).
2. `ex_state` + `config` загрузка токена + тесты.
3. `confluence_tree.py` с моком `urlopen` (CQL pages, TTL, ancestor fallback).
4. Сшивка в `digest.py`: один refresh на прогон, внутрь цикла не ходить в REST кроме miss.
5. Регрессия старых confluence-тестов без watch → всё ещё suppress без mention.

### Тесты (инварианты)
- Confluence + mention → не глушить (как сейчас).
- Confluence без mention, `pageId` ∈ watch → **не** глушить.
- Confluence без mention, `pageId` только space-home / чужой → глушить (`ForPeople`, «Синк Департамента АиД»).
- Несколько `pageId` в теле: достаточно одного из watch.
- Комментарий: `viewpage.action?pageId=499548597&focusedCommentId=1#comment-1` → id страницы, не comment id.
- Нет pageId, leaf title точно совпал с watch title → не глушить; substring «Trisigma» в чужой теме → глушить.
- `should_suppress` без watch-аргументов ≡ старое поведение.
- Tree: две CQL, объединение id, пагинация `start`; 403/timeout → пустой set, без исключения.
- Miss: `expand=ancestors` содержит `480923430` → hit; не содержит → miss.
- Digest не импортирует tree из urgent-пути косвенно так, чтобы дергать сеть на import.

### Верификация
```
cd /home/tkachenkoav/USERTOOLS/ExchangeMonitor
python3 -m pytest tests/test_confluence_filter.py tests/test_confluence_tree.py tests/test_ex_state.py tests/test_config.py tests/test_person_checker.py -q
```
Живой prefetch (не в pytest): CQL по двум корням → ~50 и ~77. После крона в `watermark.json` появится `exchange_confluence_watch`.
Ручной `mfl_digest.py`: письма по Trisigma / AI-ready без упоминания Саши ЕСТЬ в дайджесте; `ForPeople`/«Синк Департамента» — нет (если не было mention). Ollama после bk-170 — нет.

### Риски
- Load REST: в штате 2–4 CQL / 6 ч; per-письмо GET только для неизвестного pageId. Деревья маленькие. Не импортировать ConfluenceSync.
- Import-циклы: `confluence_filter` (pure) ↛ tree; tree → config + urllib; `digest` → оба; `ex_state` ↛ tree. `person_checker` не связан.
- Urgent: не менять.
- Кеш деревьев: TTL 6 ч; miss+ancestors закрывает «страницу создали час назад». Переименование на pageId не влияет; fallback по title может промахнуться до refresh — ок, pageId основной.
- Тема `>`/`/`: только fallback; не строить иерархию из темы. Не матчить имя space «Департамент аналитики и данных» — иначе весь DPAN.
- `hq@tutu.ru` в person_cache `true`: для bk-171 НУЖНО, иначе allowlist недостижим (digest отсекает до `confluence_filter`). Согласовано с bk-170.
- Токен: cron сейчас не грузит ConfluenceSync `.env` — без явной загрузки allowlist молча пустой.
- Fail-closed при падении REST: возможный пропуск уведомления на один час, не спам.

### Порядок работ (общий)
1. bk-170 (узкий дифф, сразу глушит Ollama).
2. bk-171 (новый модуль + сшивка digest).
3. Совместный pytest пакета и один ручной `mfl_digest.py`.

## §17. Доработка 02.09.2026 — bk-NEW: схлопывание по объекту + новый формат

### Задача
Несколько уведомлений об одной странице Confluence / одной задаче Jira за период → одна последняя карточка с `×N`. И в дайджесте, и в срочных.

### Объект схлопывания
- **Confluence** — по `pageId` (watch∩ids, иначе все id из письма; не резать письмо по одному id).
- **Jira** — по issue-ключу `[A-Z]{2,}[A-Z0-9]*-\d+`.
- **Обычные письма** — не группируются (`item:{id}`).

### Jira-детектор (новый `jira_filter.py`)
- `is_jira_notification` — маркеры `[JIRA]` / `(Jira)` / `hq@tutu.ru` + `/browse/`.
- `extract_issue_keys` — регэксп отсекает ложные совпадения вроде `Q3-2026`.

### Модуль схлопывания (новый `collapse.py`)
- `object_key()` — ключ объекта для группировки.
- `collapse_last()` — оставляет карточку с максимальным `ts`, поле `n_collapsed`.

### Формат карточки (`formatter.py`)
Новый порядок:
```
{дата время}
от {fio}
{суть} [· {id}] [×N]
🔗 {ссылка}
```
- Confluence/Jira → URL объекта; иначе OWA.
- Приватное — в строке «от».

### `digest.py`
Кандидаты → `collapse` → `format`; watermark = max `ts` по **всем** кандидатам; `digest-seen`.

### `urgent.py`
То же после фильтров; `mark_seen` на всех кандидатах группы.

### `ex_state.py`
- `exchange_digest_seen_ids` — TTL 48 ч.
- `is_seen` = urgent ∪ digest.

### Изменяемые файлы
| Файл | Что |
|---|---|
| **новый** `exchangemonitor/jira_filter.py` | Детектор Jira-уведомлений, извлечение issue-ключей |
| **новый** `exchangemonitor/collapse.py` | `object_key`, `collapse_last` |
| `exchangemonitor/formatter.py` | Новый порядок полей карточки, `×N`, ссылки на объект |
| `exchangemonitor/digest.py` | Collapse перед format, watermark по всем кандидатам |
| `exchangemonitor/urgent.py` | Collapse после фильтров, mark_seen на всех |
| `exchangemonitor/ex_state.py` | `exchange_digest_seen_ids`, `is_seen` urgent∪digest |
| **новый** `tests/test_jira_filter.py` | Jira-детектор и issue-ключи |
| **новый** `tests/test_collapse.py` | Схлопывание по объекту |
| **новый** `tests/test_digest_collapse.py` | Collapse в digest-пути |
| `tests/test_formatter.py` | Новый формат карточки |
| `tests/test_urgent.py` | Collapse в urgent-пути |

### Тесты (инварианты)
- Несколько Confluence-писем с одним `pageId` → одна карточка `×N`.
- Несколько Jira-писем с одним issue-ключом → одна карточка `×N`.
- Обычные письма не схлопываются.
- `Q3-2026` не матчится как issue-ключ.
- Watermark / seen — по всем исходным кандидатам, не только по «последней» карточке.

### Верификация
```
cd /home/tkachenkoav/USERTOOLS/ExchangeMonitor
python3 -m pytest -q
```
Итог реализации: **160 passed**.

## §18. Доработка 02.09.2026 — bk-NEW: primary_page_id (фикс неверной Confluence-ссылки)

### Задача
Для письма hq@tutu.ru `[confluence] Департамент аналитики и данных > Trisigma проект. Обоснования...` дайджест ставил ссылку `pageId=285418089`, правильная — `519486095` (leaf-заголовок субъекта).

### Root-cause
`formatter._resolve_object` использовал `pid = sorted(page_ids)[0]` — **лексикографический минимум** множества всех pageId из subject+text_body+body. В теле Confluence-письма много ссылок на дочерние/связанные страницы (в Trisigma — 13 разных pageId). `285418089` начинается с «2» < «5», поэтому перебивал правильный `519486095`.

### Подтверждённый паттерн (47 Confluence-писем, 100%)
Правильная страница = **ПЕРВЫЙ pageId по позиции в `text_body`** (главная ссылка «[page icon]» в начале письма). Fallback — `body`, затем `subject`. Примеры: Trisigma→519486095, Переработка обучения→519474203, Отели результаты АБ→519486010.

### Изменения
| Файл | Что |
|---|---|
| `exchangemonitor/confluence_filter.py` | Добавлены `_first_page_id(blob)` и `primary_page_id(subject, text_body, body)` — первый pageId по очереди полей text_body→body→subject. `extract_page_ids` не тронут (по-прежнему set всех id для suppress/miss). |
| `exchangemonitor/formatter.py` | `_resolve_object`: `sorted(page_ids)[0]` → `primary_page_id(...)`. Ссылка и `· {oid}` теперь по главной странице. |
| `exchangemonitor/collapse.py` | `_conf_key(primary_id)` и `object_key(item, subject, text_body, body)` — ключ схлопывания по главной странице `conf:{primary_id}`. `watch_ids` полностью убраны из collapse (membership остаётся в `should_suppress_confluence`/digest miss-цикле). |
| `exchangemonitor/digest.py` | Вызов `object_key(item, subject, text_body, body)` (без `effective_watch`). |
| `exchangemonitor/urgent.py` | Вызов `object_key(item, subject, text_body, body)` (без `set()`). |

### Инварианты схемлопывания
- Ссылка/`· {id}` и ключ схлопывания берут **одно и то же** значение `primary_page_id`.
- Allowlist (watch_ids) по-прежнему смотрит на **все** pageId (через `extract_page_ids`) — в collapse membership не дублируется.
- Два письма одного листа с разными связанными ссылками → одна карточка `×N`.
- Разные primary с общим "корневым" id → две карточки (не склеиваются).

### Тесты
- `test_confluence_filter.py`: 7 новых (primary не lexmin, fallback body/subject, None, focusedCommentId, extract_page_ids не регрессия).
- `test_formatter.py`: `test_format_confluence_primary_not_lexmin`.
- `test_collapse.py`: изменён `test_multiple_page_ids_key_set` (→`conf:481000001`), убраны `watch_ids` из вызовов; добавлены 3 теста (same primary collapses, different primary not, primary_not_lexmin_key).
- `test_digest_collapse.py`: добавлен `test_digest_collapses_same_primary_different_related`.

### Верификация
```
cd /home/tkachenkoav/USERTOOLS/ExchangeMonitor
python3 -m pytest -q
```
Итог: **172 passed** (было 160).
Ручная (на реальном письме Trisigma): дайджест показывает `pageId=519486095`, не `285418089`; несколько апдейтов одной страницы за час → одна карточка `×N`.

### Остаточный риск (не блокер)
Пустой `text_body` + HTML, где первый линк — space home. На 47 письмах не воспроизведён; эвристику «пропускать `310322545`» не добавлять, пока не всплывёт живой кейс.



## §19. Доработка 01.10.2026 — blacklist метки `_aid` в Confluence-дайджесте

Пакет `DEV/exchange-monitor-confluence-blacklist`. CHANGE-LIGHT. Код на этой фазе не меняется.

**I1.** `current`: `should_suppress_confluence` после mention смотрит только watch-allowlist (`watch_ids` / `watch_titles`, §16). Страница с Confluence-меткой `_aid` (протоколы PFS и прочий машинный контент), лежащая под корнями Trisigma / «ТОЧКА СБОРКИ AI-ready», проходит allowlist и попадает в часовой MFE-дайджест при каждом PUT.  
`target`: в дайджесте метка `_aid` — blacklist **сильнее watch**. `primary_page_id` ∈ `aid_ids` → глушить. Mention (§16 шаг 2) по-прежнему не глушить. Срочный канал не менять. Fail-open по blacklist: нет `aid_ids` / REST не отдал labels → поведение = сегодня (лишнего глушения нет).

Reuse-first: тот же `CONFLUENCE_TOKEN` / `urllib` / ключ `exchange_confluence_watch`. Пакет ConfluenceSync не импортировать. Новой сущности USERTOOLS нет.

### Алгоритм (только digest)

Вставка **после** mention, **до** watch-hit:

```
если не confluence-уведомление → не глушить
если is_user_mentioned → не глушить          # как §16
если primary_page_id ∈ aid_ids → глушить     # NEW, бьёт watch
если extract_page_ids ∩ watch_ids → не глушить
если pageId нет и leaf title ∈ watch_titles → не глушить
иначе → глушить
```

`primary_page_id` — канон §18 (первый id в `text_body` → `body` → `subject`). Связанные id в теле на blacklist не влияют: письмо про незамеченную страницу, в котором есть ссылка на `_aid`-потомка, остаётся видимым.

### Откуда `aid_ids` (`confluence_tree`)

Константа `AID_LABEL = "_aid"` рядом с `WATCH_ROOT_IDS`.

1. **Prefetch (тот же CQL, что §16):** к search добавить `expand=metadata.labels`. Из `results[].metadata.labels.results[].name` собрать id, у которых имя метки ровно `_aid`.
2. **Miss-GET:** `page_under_roots` остаётся bool-обёрткой. Новый `inspect_watch_page(page_id) -> (under_roots, has_aid)` — один GET `expand=ancestors,metadata.labels`. Digest: under + не aid → в `effective_watch`; under + aid → в `aid_ids` (не в watch).
3. **Fallback:** если у CQL-results нет ключа `metadata.labels` (expand проигнорирован) — не считать дерево «без `_aid`». Для уникальных `primary_page_id` писем этого тика, которые иначе прошли бы watch, один GET labels (лимит = число таких писем, не размер дерева).

`refresh_confluence_watch` → `(ids, titles, aid_ids, ok)`.

Кеш: тот же `exchange_confluence_watch`, TTL 6 ч. Поле `aid_ids: [...]` дописывает `digest.py` **после** `xs.save_confluence_watch` (сигнатуру `ex_state` не менять). Старый кеш без ключа `aid_ids` считать просроченным → refresh, иначе до 6 ч после выкладки leak сохранится. Пустой `aid_ids` при `ok=True` и живых labels в payload — валидно (в деревьях нет `_aid`).

Fail-open: нет токена / 403 / timeout → `aid_ids=∅`, stderr, digest не падает (как fail-closed allowlist §16, но blacklist не ужесточает).

### Изменяемые файлы (ровно 3 кода; тесты сверх лимита LIGHT)

| Файл | Что |
|---|---|
| `exchangemonitor/confluence_filter.py` | `AID_LABEL`; `should_suppress_confluence(..., aid_ids=None)`; после mention, до watch: `primary_page_id ∈ aid_ids` → `True` |
| `exchangemonitor/confluence_tree.py` | expand labels в CQL; `inspect_watch_page`; `refresh` отдаёт `aid_ids`; fallback GET labels |
| `exchangemonitor/digest.py` | прокинуть `aid_ids`; miss через `inspect_watch_page`; дописать `aid_ids` в кеш; пустой ключ → refresh |

Не трогать: `ex_state.py` (сигнатура get/save), `urgent.py`, `person_checker.py`, `collapse.py`, `formatter.py`, `mfl_digest.py`, `loop_rules.yaml`, ConfluenceSync, `__init__.py`.

`aid_ids=None` → текущее поведение (регресс §16/§18).

### IAC (LIGHT: 1–3 строки; план = эта секция)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `confluence_filter.py` (`aid_ids` vs watch/mention) | `python3 -m pytest tests/test_confluence_filter.py -q` | — | AC-001…003 |
| **IAC-02** | `confluence_tree.py` (labels CQL + `inspect_watch_page` + fallback) | `python3 -m pytest tests/test_confluence_tree.py -q` | — | labels из payload; 403 → пустой set |
| **IAC-03** | `digest.py` (прокидка `aid_ids`, кеш без ключа → refresh) | `python3 -m pytest tests/test_digest_collapse.py tests/test_confluence_filter.py tests/test_confluence_tree.py -q` | IAC-01, IAC-02 | watch+_aid нет в stdout; watch без метки есть |

Нет `depends: operator:` (класс S).

### Критерии приёмки (AC)

Только этот пакет. Класс S.

### AC-001 — `_aid` бьёт watch

Confluence-письмо, `primary_page_id` ∈ watch **и** ∈ `aid_ids`, без mention → `should_suppress_confluence(...) is True`; карточки нет в stdout `run_digest_exchange` (мок inbox + мок tree).

### AC-002 — watch без метки жив

То же письмо, `aid_ids` не содержит primary → не глушить (регресс §16). Mention на `_aid`-странице → не глушить (регресс mention). `aid_ids=None` ≡ старое поведение.

### AC-003 — границы

Diff пакета: три модуля выше + их тесты. `urgent.py` без `confluence_tree` / `aid_ids`. `ex_state.get_confluence_watch` / `save_confluence_watch` без новой сигнатуры. ConfluenceSync не импортирован.

### Тесты (инварианты)

- Watch ∩ `_aid`, без mention → suppress.
- Watch, не `_aid` → не suppress.
- Mention + `_aid` → не suppress.
- Связанный `_aid` в теле, primary не `_aid` → не suppress.
- `aid_ids=None` ≡ сегодня.
- CQL fixture с `metadata.labels` → id в `aid_ids`; без метки — нет.
- 403/timeout prefetch → `aid_ids=∅`, без исключения.
- Miss: ancestors ∈ корням и label `_aid` → `(True, True)`; без метки → `(True, False)`.
- Digest: три письма одной `_aid`-страницы в watch → stdout без карточки, watermark/seen по кандидатам как сейчас (письмо отфильтровано до collapse, seen всё равно двигается — **нет**: текущий digest `mark_digest_seen` только по `candidates` после фильтра. `_aid`-suppress = `continue` до append → как сегодняшнее suppress: watermark по remaining / `now_ms()`, seen не ставится. **Оставить как suppress §16** — повтор через час снова отфильтруется. Не менять seen-семантику).
- `test_urgent_module_does_not_import_confluence_tree` без регресса.

### Верификация

```
cd /home/tkachenkoav/USERTOOLS/ExchangeMonitor
python3 -m pytest tests/test_confluence_filter.py tests/test_confluence_tree.py tests/test_digest_collapse.py tests/test_person_checker.py -q
```

Ручной `mfl_digest.py`: апдейт страницы с `_aid` под Trisigma / AI-ready **нет** в блоке Exchange; страница тех же деревьев без метки — есть; mention — есть; ForPeople / «Синк Департамента» — нет. После прогона в `exchange_confluence_watch` есть ключ `aid_ids`.

Итог реализации: **183 passed** (регресс + новые тесты §19, IAC-01/02/03 и AC-003 зелёные).

### Риски

| Риск | Митигация |
|---|---|
| CQL игнорирует `expand=metadata.labels` | fallback GET на watch-hit primary этого тика |
| Старый кеш без `aid_ids` | digest считает его miss → refresh |
| Mention на `_aid` всё ещё виден | намеренно; глушение mention — отдельный пакет |
| Blacklist по всем `extract_page_ids` скроет чужой watch-лист | только `primary_page_id` |
| `ex_state` четвёртым файлом | запрещено; `aid_ids` дописывается в тот же dict |
| Urgent зальёт `hq@tutu.ru` | urgent не трогаем (канон §16) |

### Что НЕ трогать

- `urgent.py`, person-check, collapse/formatter, OWA, Jira.
- `loop_rules.yaml`, кроны MFL, Gateway, `.env`, манифест.
- Импорт ConfluenceSync / `requests`.
- Корни watch и CQL `(id OR ancestor)` — не менять, только expand.

Объём (факт, не команда skip): 3 файла кода вне shared-модулей, без новых сущностей/cron/.env.

## §20. Доработка 19.10.2026 — info@tutu.ru в чёрном списке отправителей MFE

Пакет `DEV/exchange-monitor-blacklist-info-tutu`. CHANGE-LIGHT. Код реализован (commit b489c41), эта секция — аддитивная фиксация в ТЗ.

**I1.** `current`: маркетинговая рассылка `info@tutu.ru` («Туту») не входит в `EXTERNAL_SENDER_EMAILS` — проходит contacts-hit (§6 шаг 2) как реальный адрес и доставляется в часовой дайджест MFE (письма-рассылки в дайджесте).  
`target`: `info@tutu.ru` добавлен в кортеж `EXTERNAL_SENDER_EMAILS` в `person_checker.py` — проверяется **до** contacts-hit (детерминированный `False`, тот же порядок, что в bk-170 для external, §15) и не доставляется в дайджест MFE. Срочный канал и `urgent_contacts` не меняются (в списке его нет).

### Изменяемые файлы

| Файл | Что |
|---|---|
| `exchangemonitor/person_checker.py` | `info@tutu.ru` в кортеж `EXTERNAL_SENDER_EMAILS` (exact-match, не substring) |
| `tests/test_person_checker.py` | 2 теста: blacklist + overrides-contacts/name |

Не трогать: `urgent.py`, `digest.py`, `confluence_*`, `collapse.py`, `formatter.py`, `ex_state.py`, `loop_rules.yaml`, `.env`, манифест. Константа `EXTERNAL_SENDER_EMAILS` уже в модуле (§6/bk-170) — только пополняется кортеж.

### IAC (LIGHT: 1–3 строки; план = эта секция)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `person_checker.py` (info@tutu.ru в blacklist, до contacts) | `python3 -m pytest tests/test_person_checker.py -q` | — | AC-001…002 |

Нет `depends: operator:` (класс S).

### Критерии приёмки (AC)

Только этот пакет. Класс S.

### AC-001 — info@tutu.ru не проходит person-check

`is_real_person("info@tutu.ru", "Туту", store=None)` → `False`; в stdout `run_digest_exchange` карточка рассылки «от Туту» не появляется.

### AC-002 — external бьёт contacts/name (до contacts-hit)

`info@tutu.ru`, добавленный в contacts (`store` содержит его), с реальным DisplayName → всё равно `False` (порядок bk-170: external до contacts и кеша).

### Тесты (инварианты)

- `info@tutu.ru` + «Туту» → `False` (blacklist).
- `info@tutu.ru` в contacts + реальный name → `False` (external бьёт).
- Exact-match, не substring: адрес вида `*info-tutu*` не затрагивается.
- Регресс: `user@tutu.ru` по-прежнему `True`.

### Верификация

```
cd /home/tkachenkoav/USERTOOLS/ExchangeMonitor
python3 -m pytest -q
```

Итог реализации: **186 passed** (было 184, +2 новых теста).

### Риски

| Риск | Митигация |
|---|---|
| Рассылка идёт от `info@tutu.ru` с DisplayName «Туту» | exact-match адреса, не domain; сам `info@tutu.ru` — только этот кортеж |
| Substring-ложные срабатывания | `is_external_sender` — точное совпадение адреса/домена (§6, bk-170), не подстрока |
| Urgent / keyword-пути | `info@tutu.ru` в `urgent_contacts` нет; urgent не трогаем (канон) |
| `hq@tutu.ru` | НЕ добавлять (bk-170 §15: Confluence-письма должны проходить `is_real_person`) |
