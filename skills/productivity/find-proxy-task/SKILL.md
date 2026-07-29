---
name: find-proxy-task
description: "Use when работаем с задачей поиска и оценки proxy-сервисов для Парсинг-К: скачивание страниц поставщиков из Confluence, перенос ответов в Google Sheets, заполнение таблицы критериев, создание страниц в Confluence по шаблону. Триггеры: proxy поставщики, таблица proxy, парсинг прокси, оценка proxy, find proxy, создай страничку по сервису."
version: 1.1.0
author: agent
license: MIT
platforms: [linux]
tags: [proxy, parsing, confluence, google-sheets, парсинг]
metadata:
  hermes:
    tags: [proxy, parsing, confluence, google-sheets, парсинг]
---

# Задача поиска и оценки PROXY-поставщиков (Парсинг-К)

## Контекст

Задача: найти и оценить сервисы, предоставляющие прокси, по набору критериев.

**Google Sheets с критериями:** `https://docs.google.com/spreadsheets/d/12JKbfPiq0OpyABaNVOiJb6eJosKJOiDNFGuzLos2fdo/edit`
- Строки = вопросы (13 технических + 3 по оплате, итого 16)
- Столбцы A–F заняты, новые сервисы вписываются начиная с G

**Confluence (страница с таблицей поставщиков):** `https://dom.tutu.ru/pages/viewpage.action?pageId=511554221`
- Корневая страница = сводная таблица всех поставщиков
- Дочерние страницы = ответы каждого поставщика на 16 вопросов

**Путь в WorkVault:**
`~/WorkVault/Confluence/DPAN/Департамент аналитики и данных/Проекты/Парсинг-К/Парсинг-К. Поиск PROXY. Требования/Парсинг-К. Таблица PROXY поставщики/`

## Паттерн работы

### Шаг 1 — Скачать страницы из Confluence
```bash
cd ~/USERTOOLS/ConfluenceSync
python3 -m confluencesync pull 511554221 --depth 3
```
Скачивает корневую страницу + все дочерние (страницы поставщиков).
После — синк: `rclone sync ~/WorkVault owncloud:WorkVault`

### Шаг 2 — Прочитать структуру таблицы GS
Читаем заголовки и вопросы перед заполнением:
```python
GAPI sheets get 12JKbfPiq0OpyABaNVOiJb6eJosKJOiDNFGuzLos2fdo "Sheet1!A1:Z3"
```
Строка 1 = заголовки столбцов (названия сервисов), столбец A = вопросы.

### Шаг 3 — Прочитать страницы поставщиков из WorkVault
Каждая дочерняя страница = `index.md` в подпапке. Читать через `read_file()`.

### Шаг 4 — Сопоставить ответы с вопросами
**Правила:**
- Ответы нумерованы (1. 2. 3...) → сопоставлять по номеру вопроса
- Отвечать на русском, теми же словами что в тексте; при необходимости переводить с английского
- Если ответ содержит повтор вопроса — брать только суть ответа, вопрос отбрасывать
- Если ответа на вопрос нет → оставить ячейку пустой (не придумывать)
- Сервисы с `Fixed fee: Нет` в сводной таблице — заполняем тех. данные если есть, коммерческие тоже

### Шаг 5 — Записать в GS
Определить свободный столбец (первый после последнего заполненного).
Строка 1 = название сервиса, строки 2–17 = ответы на вопросы 1–16.

```python
# Пример записи одного столбца
GAPI sheets update SHEET_ID "Sheet1!G1:G17" --values '[["Название сервиса"], ["ответ1"], ["ответ2"], ...]'
```

**Важно:** перед записью прочитать текущее состояние таблицы чтобы не затереть данные.

## 16 вопросов (порядок фиксирован)

**Технические (1–13):**
1. Аренда по IP или по трафику?
2. Автопродление аренды?
3. Выбор прокси в конкретном городе России?
4. Пробный период?
5. Объём пула серверных прокси в России?
6. Мобильные прокси?
7. API управления прокси?
8. Эксклюзивность IP (только у нас)?
9. Замена недоступных прокси?
10. Ручной выбор конкретных адресов?
11. Выбор адресов из разных подсетей?
12. Многопоточное использование одного прокси?
13. Уведомления о сбоях?

**Коммерческие (14–16):**
14. Работа с юрлицами / договор?
15. Способы оплаты / скидки?
16. Актуальный прайс-лист?

## Шаг 6 — Создать страницу сервиса в Confluence

Шаблон страницы (по образцу webshare, pageId 511562669):

- **Название:** `Парсинг. <Название сервиса>`
- **Родитель:** pageId `511554221` (таблица поставщиков), space `DPAN`
- **Структура:**
  1. `<h1><a href="URL сервиса">Название сервиса</a></h1>` — H1 = гиперссылка на сайт
  2. `<h2>Технические вопросы</h2>` + таблица (Вопрос | Ответ), вопросы 1–13
  3. `<h2>Коммерческие вопросы</h2>` + таблица (Вопрос | Ответ), вопросы 14–16
  4. `<h2>Вывод</h2>` + Confluence-макрос: `tip` (✅), `warning` (❌), `note` (⚠️), `info` (❓)

**URL сервиса** — брать из сводной таблицы pageId 511554221 (href в строке поставщика).

**Создание через curl:**
```bash
source ~/USERTOOLS/ConfluenceSync/.env
curl -s -X POST \
  -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  -H "Content-Type: application/json" \
  "https://dom.tutu.ru/rest/api/content" \
  -d @/tmp/payload.json
```

**Удаление старых страниц:**
```bash
curl -s -X DELETE -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/<pageId>"
```

**Текущие страницы сервисов (созданы 24.07.2026):**

| Сервис | pageId |
|---|---|
| Парсинг. webshare | 511562669 |
| Парсинг. proxy6.net | 511562679 |
| Парсинг. proxy5.net | 511562680 |
| Парсинг. proxywing.com | 511562681 |
| Парсинг. proxiempire.io | 511562682 |
| Парсинг. shifter.io | 511562683 |
| Парсинг. fineproxy.org | 511562684 |
| Парсинг. 2captcha.com | 511562685 |
| Парсинг. InfraProxy.ru | 511562686 |

**Текущие столбцы в GS (G=proxy6 → O=InfraProxy, строка 20 = Выводы):**
G=proxy6.net, H=proxy5.net, I=webshare, J=proxywing.com, K=proxiempire.io, L=shifter.io, M=fineproxy.org, N=2captcha.com, O=InfraProxy.ru

## Скачанные сервисы (по состоянию на 21.07.2026)

| Папка | Сервис |
|---|---|
| `2captcha.com/` | 2captcha.com |
| `fineproxy.org/` | fineproxy.org |
| `https___proxywing.com_/` | proxywing.com |
| `proxiempire.io/` | proxiempire.io |
| `proxy5.net/` | proxy5.net |
| `proxy6/` | proxy6.net |
| `shifter.io/` | shifter.io |
| `webshare/` | webshare.io |

## Шаг 2б — Exchange inbox как дополнительный источник

Помимо Confluence-страниц, ответы поставщиков могут приходить письмами через посредника (forward от mrsk.lk.test2@gmail.com). Читать через exchangelib:

```python
from exchangelib import Credentials, Account, Configuration, DELEGATE
from datetime import datetime, timezone

today_start = datetime(YYYY, MM, DD, 0, 0, 0, tzinfo=timezone.utc)
messages = list(account.inbox.filter(
    datetime_received__gte=today_start,
    sender__contains="mrsk.lk"
).order_by('datetime_received'))
```

Каждое письмо = 1 поставщик (forward от поставщика). Логика та же: ответы по номерам → сопоставить с 16 вопросами, перевести на русский. Если письмо содержит только уведомление Intercom/форму оценки — ответов нет, пропускать. Если у сервиса уже есть столбец в GS — обновить его (письмо обычно подробнее страницы Confluence).

## Питфоллы

- **Google токен протухает** — при `invalid_grant` нужна повторная авторизация: `python setup.py --auth-url`, пользователь открывает ссылку, копирует redirect URL, `setup.py --auth-code "..."`, затем `cp ~/.hermes/google_token.json ~/.hermes/profiles/anthropic/google_token.json`.
- **`googleapiclient` не в системном Python** — перед вызовом `google_api.py` активировать venv: `source ~/hermes-agent/.venv/bin/activate`. Иначе `No module named 'googleapiclient'`.
- **Имя листа GS не «Sheet1»** — при ошибке `Unable to parse range: Sheet1!A1:Z3` опустить имя листа: `"A1:Z3"` вместо `"Sheet1!A1:Z3"`.
- **TUTU_DOMAIN_PASSWORD со спецсимволами** — `set -a; source ~/.config/hermes/.env` падает с SyntaxError. Читать через `grep TUTU_DOMAIN_PASSWORD ~/.config/hermes/.env | cut -d= -f2-` и передавать через `shlex.quote()` в env-переменной.
- **ConfluenceSync** требует `source ~/USERTOOLS/ConfluenceSync/.env` — токен там. Для curl использовать `CONFLUENCE_TOKEN`.
- **Ответы в свободной форме** (не строго по номерам) — читать весь текст, самостоятельно определять к какому вопросу относится фрагмент.
- **Сервисы без ответов на некоторые вопросы** — не додумывать, оставлять пусто.
- **proxiempire.io** отвечал на английском — переводить.
- **Новые сервисы из Exchange могут не иметь Confluence-страницы** (InfraProxy.ru пришёл только письмом). Для них столбец GS заполнить из письма, страницу в Confluence создать вручную по тому же шаблону Шаг 6.
- **Субагент не всегда читает Exchange inbox корректно** — если пишешь промпт для делегата, явно указывай `sender__contains` и формат заголовков писем. Лучше самостоятельно прочитать Exchange и передать тексты писем в контексте делегата.
