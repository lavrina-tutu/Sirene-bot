---
name: exchange-monitor
description: "Мониторинг входящей почты Exchange (EWS) — фильтрация реальных людей, срочные уведомления и часовой дайджест в Telegram Messages. Интегрируется в кроны MoveFromLoop. Триггеры: Exchange мониторинг, входящие письма, ExchangeMeeting, email дайджест, письма от реальных людей."
version: 0.1.0
author: Sirene
license: MIT
platforms: [linux]
tags: [exchange, ews, email, monitor, tutu]
metadata:
  hermes:
    tags: [exchange, ews, email, monitor, tutu]
    related_skills: [mattermost-loop-api, workvault-entities]
---

# Exchange Monitor

Мониторинг входящих писем на `tkachenkoav@tutu.ru` через EWS (exchangelib).
Интегрируется в те же кроны что и MoveFromLoop v2.

## Существующий инструмент

`USERTOOLS/ExchangeMeeting/create_meeting.py` — proof-of-concept, умеет:
- Авторизацию через EWS (`cas.tutu.ru`)
- Создание встреч в Exchange с приглашением
- Проверку free/busy участников

## Решения брифа (24.07.2026)

| # | Вопрос | Решение |
|---|---|---|
| Q1 | Источник | Входящие на `tkachenkoav@tutu.ru` |
| Q2 | Критерий реального человека | (1) Есть в `contacts.enc` по email ИЛИ (2) в Exchange у отправителя заполнен DisplayName (ФИО) |
| Q3 | Срочные | Тот же список `urgent_contacts` что в Loop (gladkikh, malyy, fedotovav, klimovskiyrb, aralov) |
| Q4 | Теги | `(приватное)` — я единственный в `To:`, `(личное)` — я в `CC:`, без тега — я в `To:` среди других |
| Q5 | Расписание | Те же кроны MFL — срочный `*/3 * * * *`, дайджест `0 8-20 * * 1-5` |
| Q6 | Формат | Тема письма + тело (вместе ≤150 символов), время отправки `[HH:MM]`, ссылка на OWA |

## Формат уведомления

```
📧 (приватное) от Аралов Александр [14:32]
Согласование бюджета Q3 — Привет, можешь посмотреть документ...
🔗 https://cas.tutu.ru/owa/#ItemID=...
```

**Правила формата (утверждены 24.07.2026):**
- Первая строка: иконка + тег (если есть) + `от {ФИО из contacts.enc или DisplayName}` + `[HH:MM МСК]`
- Вторая строка: тема + ` — ` + начало тела (вместе ≤ 150 символов, обрезать по слову)
- Ссылка OWA: `https://cas.tutu.ru/owa/#ItemID={item.id}` (item.id из exchangelib)
- Мою почту (`tkachenkoav@tutu.ru`) в уведомлении НЕ писать

**Теги (единые для срочного и дайджеста):**
- `(приватное)` — я единственный в `To:` (письмо лично мне)
- `(личное)` — я в `CC:`
- без тега — я в `To:` среди нескольких получателей

## Критерий реального человека

```python
def is_real_person(sender_email, sender_display_name, contacts_store):
    # Критерий 1: есть в contacts.enc по email
    if contacts_store.get_contact_by_email(sender_email):
        return True
    # Критерий 2: в Exchange заполнен DisplayName (не пустой, не похож на сервис)
    if sender_display_name and len(sender_display_name) > 2:
        # Исключить паттерны сервисных имён
        service_patterns = ['noreply', 'no-reply', 'donotreply', 'notifications',
                           'mailer', 'daemon', 'jira', 'confluence', 'bot']
        name_lower = sender_display_name.lower()
        if not any(p in name_lower for p in service_patterns):
            return True
    return False
```

## Архитектура (в разработке)

**Новые файлы (дополнение к ExchangeMeeting):**
```
USERTOOLS/ExchangeMonitor/     # новый проект
  exchangemonitor/
    client.py        # EWS подключение (exchangelib), watermark по дате
    fetcher.py       # GET входящих с фильтром since_dt
    filters.py       # is_real_person, is_urgent, тег (приватное)/(личное)
    formatter.py     # format_email → строка TG
    urgent.py        # run_urgent — срочные письма
    digest.py        # run_digest — дайджест за час
  scripts/
    exchange_urgent.py  # точка входа (добавить в mfl_urgent_check.py)
    exchange_digest.py  # точка входа (добавить в mfl_digest.py)
  state/
    exchange_watermark.json   # {urgent_last_dt, digest_last_dt}
```

**Интеграция в кроны MFL:**
Не создавать отдельные кроны — добавить вызов Exchange в существующие скрипты:
- `~/.hermes/scripts/mfl_urgent_check.py` → добавить `run_exchange_urgent()`
- `~/.hermes/scripts/mfl_digest.py` → добавить `run_exchange_digest()`
Объединять результаты Loop + Exchange в одно сообщение (или два блока через `───`).

## Аутентификация EWS

```python
from exchangelib import Credentials, Account, Configuration, DELEGATE

user = "tkachenkoav@tutu.ru"
password = load_from_env("TUTU_DOMAIN_PASSWORD")  # ~/.config/hermes/.env
server = "cas.tutu.ru"

# Пробовать три варианта username (из create_meeting.py):
for username in (user, "TUTU\\tkachenkoav", "tkachenkoav"):
    try:
        creds = Credentials(username=username, password=password)
        config = Configuration(server=server, credentials=creds)
        account = Account(
            primary_smtp_address=user,
            config=config,
            autodiscover=False,
            access_type=DELEGATE,
        )
        _ = account.root.name  # проверочный запрос
        break
    except Exception:
        continue
```

## Получение входящих писем

```python
from exchangelib import Q
from datetime import datetime, timezone, timedelta

# Входящие с момента watermark
inbox = account.inbox
messages = inbox.filter(
    datetime_received__gt=since_dt
).order_by('datetime_received')

for msg in messages:
    sender_email = msg.sender.email_address
    sender_name = msg.sender.name
    subject = msg.subject
    body_preview = msg.text_body[:200] if msg.text_body else ""
    received_dt = msg.datetime_received
    to_recipients = [r.email_address for r in (msg.to_recipients or [])]
    cc_recipients = [r.email_address for r in (msg.cc_recipients or [])]
    my_email = "tkachenkoav@tutu.ru"
    
    # Определение тега
    if to_recipients == [my_email]:
        tag = "(приватное)"
    elif my_email in [r.lower() for r in cc_recipients]:
        tag = "(личное)"
    else:
        tag = ""
```

## Watermark

- Exchange watermark по дате (`datetime`), не по timestamp мс как в Loop
- `urgent_last_dt`: `now - 10 minutes` при первом запуске
- `digest_last_dt`: `now - 2 hours` при первом запуске
- Хранить в `state/exchange_watermark.json` как ISO строки

## Реализация (24.07.2026, Sonnet, 67/67 тестов ✅)

**Код:** `USERTOOLS/ExchangeMonitor/`

```
exchangemonitor/
  client.py        # singleton get_account(), 3 варианта username, autodiscover=False
  fetcher.py       # fetch_inbox_since(account, since_ms) → list[dict] (asc)
  owa.py           # build_link(item_id) — URL с urllib.parse.quote(safe='')
  person_checker.py # is_real_person(email, name, contacts_path, enc_key, cache)
  tagger.py        # compute_tag(item, me_email) → '(приватное)'/'(личное)'/''
  formatter.py     # format_email(item, tag, fio, owa_link) → строка TG
  ex_state.py      # надстройка над MFL State: exchange_*_last_ts, seen_ids TTL 48ч
  config.py        # load_rules(), load_password()
  urgent.py        # run_urgent_exchange(rules_path, state_path) → list[str]
  digest.py        # run_digest_exchange(...) → list[str]
tests/
  test_person_checker.py  # 23 теста
  test_tagger.py          # 7 тестов
  test_formatter.py       # 17 тестов
  test_owa.py             # 6 тестов
  test_ex_state.py        # 14 тестов
```

**Smoke-test результаты:**
- EWS OK: `tkachenkoav@tutu.ru` ✅
- exchangelib 5.6.0 уже установлен в системном python3.11 (не нужен отдельный venv)
- Писем за 2 часа: 3 (все Jira/Confluence нотификации → отфильтрованы как боты)

**Интеграция:** патч применён в `mfl_urgent_check.py` и `mfl_digest.py` — Exchange проверяется после Loop в том же тике.

**Watermark в `state/watermark.json` (общий с MFL):**
- `exchange_urgent_last_ts`: int ms
- `exchange_digest_last_ts`: int ms
- `exchange_urgent_seen_ids`: [{id, ts}] TTL 48ч

**Управляющая секция в `loop_rules.yaml`:**
```yaml
exchange_enabled: true
```

## TODO / открытые вопросы

- [x] Адрес OWA: `https://cas.tutu.ru/owa` (подтверждён 24.07.2026)
- [x] ТЗ ExchangeMonitor v0.1.0 создано (24.07.2026)
- [x] Реализация завершена (24.07.2026, 67/67 тестов)
- [x] exchangelib уже в системном python3.11 — отдельный venv не нужен

## Pitfalls

- **`TUTU_DOMAIN_PASSWORD` в `~/.config/hermes/.env`** — не в `.hermes/profiles/anthropic/.env`. Проверять оба файла.
- **Autodiscover отключён** — `autodiscover=False`, сервер задаётся явно как `cas.tutu.ru`.
- **Username может потребовать DOMAIN\\user** — пробовать три варианта как в `create_meeting.py`.
- **`msg.text_body` может быть None** — проверять перед срезом.
- **HTML письма** — `text_body` может содержать HTML-теги если `body_type='HTML'`. Использовать `BeautifulSoup` или `html2text` для очистки перед показом.
- **Рассылки без DisplayName** — у сервисных отправителей `sender.name` часто совпадает с email или пустой. Фильтр `is_real_person` покрывает это.
- **Часовой пояс** — Exchange возвращает `datetime_received` в UTC. Конвертировать в МСК (UTC+3) для отображения.
- **`item.sender.name` уже содержит DisplayName** — не нужен отдельный вызов `account.protocol.resolve_names()`. `resolve_names()` оставлять только как fallback если `sender.name` пустой (внешний SMTP без ORCPT).
- **OWA deep-link: `ItemID` ≠ `OwaId`** — `item.id` в EWS это `EwsId` (~150 симв base64). OWA принимает форму `?ItemID=<EwsId>&exvsurl=1&viewmodel=ReadMessageItem` на Exchange 2013/2016, но не гарантированно. Fallback: `ConvertId` EWS операция. Тестировать на реальном письме перед финализацией.
- **Watermark Exchange — миллисекунды или datetime?** В MoveFromLoop state.py всё в мс (int). Exchange watermark хранить тоже в мс для единообразия: `int(item.datetime_received.timestamp() * 1000)`. Не смешивать форматы в одном `watermark.json`.
- **Дедупликация срочный↔дайджест** — без `exchange_urgent_seen_ids` письмо от urgent-контакта придёт дважды: срочным, потом в часовом дайджесте. Реализовать TTL-48ч seen_ids аналогично Loop.
- **Entry-скрипты в `~/.hermes/scripts/` — хардкодить `_ROOT`:** при копировании скриптов из `USERTOOLS/ExchangeMonitor/scripts/` в `~/.hermes/scripts/mfl_*.py` — `Path(__file__).parent.parent` указывает на `~/.hermes/`, а не на проект. Правильный паттерн:
  ```python
  _ROOT = Path("/home/tkachenkoav/USERTOOLS/ExchangeMonitor")
  sys.path.insert(0, str(_ROOT))
  _ENV = Path("/home/tkachenkoav/.hermes/profiles/anthropic/.env")
  if _ENV.exists():
      from dotenv import load_dotenv; load_dotenv(_ENV)
  ```
  Без `load_dotenv` → `401 Unauthorized` (env не передаётся в крон-процесс).
- **Basic-auth single point of failure** — если ТУТУ выключит Basic на `cas.tutu.ru`, лягут ExchangeMeeting и ExchangeMonitor одновременно. Зафиксировать как риск, но за рамками текущего ТЗ.
