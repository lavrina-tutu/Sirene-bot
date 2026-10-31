---
name: confluence-people-resolve
description: "Резолв email людей из таблиц Confluence по ri:user."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [confluence, tutu, email, resolve, contacts, table]
    related_skills: [tutu-confluence-jira, exchange-meeting, anywherecontacts-api]
---

# Confluence People Resolve — извлечение email из таблиц Confluence

Резолв людей из Confluence-страницы в корпоративные email, когда имена в таблице — это не текст, а **user-упоминания** (`<ac:link><ri:user ri:userkey="..."/></ac:link>`), часто с табличной датой/ролью рядом. Типовой запрос Саши: «найди mail всех, кто в столбцах „Тимлид“ и „Аналитики“ в этой таблице…».

## Триггеры
- «найди mail всех в столбцах X/Y на странице <pageId>»
- «собери участников из таблицы», «кто там в ролях», «резолв людей из минуток/реестра»
- любой сценарий, где email-адреса надо получить пачкой для добавления на встречу/рассылку

## ⚠️ Pitfall №1: `BeautifulSoup` НЕ находит `<ri:user>` (namespace)

`<ri:user>` в Confluence storage-формате — не обычный HTML-тег (namespace-префикс `ri`). `soup.find_all('ri', attrs={'userkey':...})` возвращает **пусто**, даже если в сыром body теги есть (проверено live на pageId=353012747, 03.09.2026).

**Не полагаться на BeautifulSoup для userkey.** Парсить сырой `body.storage` регэкспами:

```python
import json, re
data = json.load(open('/tmp/page.json'))          # см. pitfall про backslash ниже
body = data['body']['storage']['value']
rows = re.findall(r'<tr>(.*?)</tr>', body, re.S)
for r in rows:
    tds = re.findall(r'<td>(.*?)</td>', r, re.S)
    if len(tds) < 3: continue
    product = re.sub(r'<[^>]+>', '', tds[0]).strip()
    def keys(td): return re.findall(r'ri:userkey="([^"]+)"', td)
    timlidy = keys(tds[COL_TL])    # COL_TL = индекс столбца «Тимлид»
    analitiki = keys(tds[COL_AN])  # COL_AN = индекс столбца «Аналитики»
```

Внимание на индексы `<td>`: считать с 0, `[0]` обычно = продукт/название, дальше роли. Одна ячейка может содержать **несколько** user-упоминаний (по строке/дате на человека).

## Шаг 1 — скачать страницу и сохранить в файл

```bash
load_confluence_env() {
  while IFS='=' read -r _k _v; do
    case "$_k" in CONFLUENCE_TOKEN|WORKVAULT_PATH)
      [ -n "$_v" ] && export "$_k=$_v";;
    esac
  done < "$HOME/USERTOOLS/ConfluenceSync/.env"
}
load_confluence_env
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/<pageId>?expand=body.storage" > /tmp/page.json
```

**Pitfall:** тело Confluence содержит backslash-последовательности → `json.loads(stdout)` падает `JSONDecodeError: Invalid \escape`. Сохранять в файл и читать `json.load(open(...))`. Удалить `/tmp/page.json` после (внутренний контент).

## Шаг 2 — резолв userkey → username/displayName (Confluence)

```bash
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/user?key=<userkey>"
# → {"username": <login>, "displayName": <ФИО>, ...}
```

## Шаг 3 — username → email (AnywhereContacts, ВСЕ source-домены)

Confluence API в этой инсталляции **НЕ возвращает email** (`user?username=` → `email: null`; CQL `user.fullname~"ФИО"` тоже без email). Email берётся из `contacts.enc`.

```python
import os, sys
from pathlib import Path
for line in open('/home/tkachenkoav/USERTOOLS/AnywhereContacts/.env'):
    line=line.strip()
    if '=' in line and not line.startswith('#'):
        k,v=line.split('=',1); os.environ[k]=v.strip()
sys.path.insert(0,'/home/tkachenkoav/USERTOOLS/AnywhereContacts')
from anywhere_contacts import create_store, ContactsBaseSettings
s=ContactsBaseSettings()
store=create_store(Path('/home/tkachenkoav/WorkVault/Contacts/contacts.enc'), s.contacts_encryption_key)
contacts=store.read().get('contacts',{})

def email_for(login):
    info=contacts.get(login) or {}
    src=info.get('sources',{})
    em = src.get('exchange',{}).get('email')
    if not em:
        em = (src.get('exchange',{}).get('smtp_addresses') or [None])[0]
    if not em:
        em = src.get('zulip',{}).get('email')
    return em or '', info.get('display_name') or info.get('fio','')
```

**Порядок источников email:** `exchange.email` → `exchange.smtp_addresses[0]` → `zulip.email`. **Не останавливаться на отсутствии exchange** — многие контакты в ТУТУ имеют только `zulip` или только `loop` source, но там email есть.

## ⚠️ Pitfall №2: loop-поле и отсутствие записи

- У контакта может не быть `sources.exchange`/`zulip`, но быть `sources.loop.email` (например `source: {'loop': {'email': 'x@tutu.ru'}}`). Если других email нет — использовать loop-email как подтверждённую кандидатуру.
- Человек из Confluence может **вообще отсутствовать в `contacts.enc`** (без записи под своим логином и без поиска по ФИО). Тогда корпоративный email неизвестен — **не выдумывать**: пометить «нет в контактах» и либо искать через Loop/People-карточку, либо показать Саше для подтверждения.

## Домены: `@tutu.ru` vs `@tutu.tech`

Люди из нашего Exchange встречаются на **разных** доменах: `@tutu.ru`, `@tutu.tech` (напр. `dashkevich@tutu.tech`, `sisyov@tutu.tech`). Домен не помечает человека «внешним» и не блокирует резолв/добавление на встречу/рассылку (правило Саши 03.09.2026 — см. `exchange-meeting`).

## Питфоллы
- `loguru`/`pydantic-settings` нужны для `anywhere_contacts` — запускать через venv `/home/tkachenkoav/USERTOOLS/AnywhereContacts/venv_linux/bin/python3`, НЕ через execute_code-интерпретатор (в нём нет пакетов).
- `create_store()` требует путь к **файлу** `contacts.enc`, не к директории (иначе `IsADirectoryError`).
- Один человек может встречаться в нескольких продуктах/ролях — дедуплицировать по логину, агрегировать роли/продукты, в итог выдавать одного человека с одним email.
- После скачки страницы (`confluencesync pull`) текст-рендер теряет user-упоминания (вместо ФИО показываются даты ролей). Для извлечения людей всегда читать **сырой body.storage**, не рендер.

## Verification
- Каждому человеку из целевых столбцов назначен email (или явно помечен «нет в контактах»).
- Дубли (один человек в нескольких ролях) схлопнуты.
- Список отдан с продуктом и ролью каждого (Саше часто важно, кто из какого продукта).
- Удалён `/tmp/page.json`.