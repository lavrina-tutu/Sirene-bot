---
name: tutu-confluence-jira
description: "Confluence/JIRA ТУТУ: страницы, макросы, формат, резолв; постановка/правка задач в минутках — через taskrefresh"
version: 1.9.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, Confluence, JIRA, WorkVault, договор, согласование]
    related_skills: [tutu-jira-contract-approval, tutu-jira-okr, obsidian, pm-briefing]
---

# TUTU Confluence & JIRA

Корпоративные системы ТУТУ доступны только через VPN/internal network. `web_extract` блокирует `dom.tutu.ru` (resolves to 10.x.x.x). Всегда использовать `terminal` + `curl` или ConfluenceSync CLI.

## Авторизация

**Два разных токена — не путать:**

| Система | Файл | Переменная |
|---|---|---|
| Confluence (`dom.tutu.ru`) | `~/USERTOOLS/ConfluenceSync/.env` | `CONFLUENCE_TOKEN` |
| JIRA (`hq.tutu.ru`) | `~/.hermes/profiles/default/.env` (fallback: `anthropic/.env`) | `JIRA_TOKEN` + `JIRA_BASE_URL=https://hq.tutu.ru` |

⚠️ **`~/.config/hermes/.env` сломан** — содержит спецсимволы в `TUTU_DOMAIN_PASSWORD`, bash падает с syntax error при `source`. Для JIRA: канон `~/.hermes/profiles/default/.env`, fallback `~/.hermes/profiles/anthropic/.env`.

⚠️ **Массовый 404 на Confluence = сперва проверь токен, а не «страницы удалены».** Если ВСЕ страницы разом дают 404 (и даже заведомо живая контрольная), а тело ответа содержит `"authorized":false,"valid":true` — это **отказ авторизации, замаскированный под `No content found` (404)**, а не отсутствие страниц. Единичный 404 одного pageId (обычно SSO/private/space-rights) — другая история; правило ниже «404 = единственный выход вручную» про неё. Массовый 404 с `authorized:false` — проверь `load_confluence_env` и целостность скопированного токена: **повреждённый CONFLUENCE_TOKEN (валидные байты + мусорные хвостовые) в более-приоритетном env перекрывает рабочий** из `~/USERTOOLS/ConfluenceSync/.env`. Загрузка env идёт по порядку (`load_usertools_env()` центральный первый, фоллбек на tool-local только `if key not in os.environ`) — попавший в центральный `~/.config/hermes/.env` мусорный токен глушит валидный, ничего не бросая. Проверка: `curl -s -o /dev/null -w "%{http_code}"` на известный pageId валидным токеном (ожидай 200) — расхождение = сломан загруженный токен.

Загрузить Confluence (только нужные переменные, БЕЗ распыления generic-переменных):
```bash
# Загружает из ConfluenceSync/.env ТОЛЬКО токен и при необходимости WORKVAULT_PATH,
# НЕ мутируя окружение чужими generic-переменными (TOOL_DIR/LOGS_PATH и т.п.),
# которые распыляются из этого .env при использовании `source` и ломают другие тулы
# (см. баг MOFS CONF-001, решён 20.08.2026).
load_confluence_env() {
  while IFS='=' read -r _k _v; do
    case "$_k" in
      CONFLUENCE_TOKEN|WORKVAULT_PATH)
        [ -n "$_v" ] && export "$_k=$_v"
        ;;
    esac
  done < "$HOME/USERTOOLS/ConfluenceSync/.env"
}
load_confluence_env
```

Для Confluence curl:
```bash
curl -H "Authorization: Bearer $CONFLUENCE_TOKEN" "https://dom.tutu.ru/rest/api/..."
```

Для JIRA curl:
```bash
source ~/.hermes/profiles/default/.env  # fallback: anthropic/.env
curl -H "Authorization: Bearer $JIRA_TOKEN" \
     -H "Content-Type: application/json" \
     "https://hq.tutu.ru/rest/api/2/..."
```

---

## Патч секции (не PUT всего поля моделью)

**Запрет:** LLM (grok/composer) **не генерирует** `body.storage.value` целиком и не собирает XHTML «на глаз».  
Выход grok — markdown/текст поля. В storage вставляет **только скрипт** `scripts/section_patch.py`.

### Алгоритм (B0)

1. GET `?expand=body.storage,version` → файл JSON.
2. Найти секцию по маркеру-заголовку (напр. «Ключевые поставки и сроки»).
3. Заменить **только внутренность** секции (заголовок и пояснение под ним — вне span).
4. PUT: `title` + `type:page` + `version.number+1` + полный body; **`space` не передавать**.
5. Повторный GET + чеклист verify (7 пунктов, см. ниже).

Детали: `references/section-patch.md`, `references/verify-skeleton.md`.

```bash
python3 ~/hermes-workspace/skills/productivity/tutu-confluence-jira/scripts/section_patch.py \
  patch PAGE_ID --heading "Ключевые поставки и сроки" --inner-file /tmp/inner.html
```

Composer-2.5 как оператор **вызывает** скрипт; не имеет права писать storage руками в промпте.

### Verify skeleton (7 пунктов)

После каждого PUT координатор делает GET и проверяет:

1. `version` — ожидание или подхвачена ручная правка.
2. Счёт `ac:structured-macro` не изменился без причины в брифе.
3. Целевой **заголовок секции** на месте (по маркеру, не по данным таблицы).
4. Удаляемые значения отсутствуют (`kw not in body`).
5. Нет дубля `<table>` под одним заголовком.
6. Нет служебного текста брифа: «Не копировать», «Уточнить до ПК», «источник:», «см. бриф».
7. Число `<td>` в затронутой таблице = эталону шаблона.

Провал любого пункта = не «успех»; откат или повторный патч той же секции.

```bash
python3 ~/hermes-workspace/skills/productivity/tutu-confluence-jira/scripts/verify_skeleton.py \
  --storage /tmp/after.json --reference /tmp/before.json \
  --heading "Ключевые поставки и сроки"
```

---

## Батч-резолв userkey (не точечный curl)

Извлечь все `ri:userkey` со страницы → уникальный список → **один GET на ключ** (`/rest/api/user?key=`), повтор из кэша сессии.  
**Запрет:** plaintext-реестры контактов; `/rest/api/user/search` (404); выдумывать «Неизвестный пользователь». CQL `user.fullname` — только если userkey нет.

Запись `confluence_login` / `confluence_userkey` — **только** в `contacts.enc` через `ContactStore.update_contact` на существующих контактах.

```bash
# JSON {userkey, username, displayName}
python3 ~/hermes-workspace/skills/productivity/tutu-confluence-jira/scripts/userkey_resolve.py \
  --storage-file /tmp/page.json

python3 ~/hermes-workspace/skills/productivity/tutu-confluence-jira/scripts/userkey_resolve.py \
  --page-id 490170597 --write-contacts
```

Grok получает уже резолвнутую таблицу; REST не дергает.

---

## Confluence: скачать страницу в WorkVault

### Инструмент: ConfluenceSync CLI

```bash
cd ~/USERTOOLS/ConfluenceSync

# Скачать страницу в WorkVault (по умолчанию)
python3 -m confluencesync pull <pageId> --no-recursive

# Скачать и вывести MD в stdout (для агента)
python3 -m confluencesync pull <pageId> --to-context --no-recursive

# Скачать И в WorkVault И в stdout
python3 -m confluencesync pull <pageId> --to-both --no-recursive

# С дочерними страницами
python3 -m confluencesync pull <pageId> --depth 2
```

**Куда сохраняется:** `~/WorkVault/Confluence/<space-key>/.../<title>/index.md`  
Путь вычисляется по иерархии Confluence автоматически.

**Лог операций:** `python3 -m confluencesync log`

### Получить pageId из URL
URL вида `https://dom.tutu.ru/pages/viewpage.action?pageId=389284624` → pageId = `389284624`

### Прямой REST API (без сохранения)
```bash
load_confluence_env
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/<pageId>?expand=body.storage" \
  | python3 -c "
import sys, json, re, html
data = json.load(sys.stdin)
title = data.get('title', '')
body = data.get('body', {}).get('storage', {}).get('value', '')
print('# ' + title)
text = re.sub(r'<li>', '\n- ', body)
text = re.sub(r'<h[1-6][^>]*>', '\n## ', text)
text = re.sub(r'<[^>]+>', '', text)
text = html.unescape(text)
print(re.sub(r'\n{3,}', '\n\n', text).strip())
"
```

---

## JIRA: создать задачу

### Проект TOMAKE — согласование договора

**Путь:** JIRA → Проект `TOMAKE` → Тип задачи `Задача`

Обязательные поля при согласовании договора:
- `summary` — название (напр. `Согласовать договор с АО «Неофлекс Консалтинг»`)
- `components` — `Маркетинг` (для маркетинговых/расходных договоров)
- `priority` — `Обычный` по умолчанию
- `description` — все договорённости с партнёром (см. `references/tomake-contract-fields.md`)
- Вложение — файл договора

**Исполнитель проставляется автоматически.**

### REST API: создать задачу
```bash
load_confluence_env

curl -s -X POST \
  -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  -H "Content-Type: application/json" \
  "https://dom.tutu.ru/rest/api/2/issue" \
  -d '{
    "fields": {
      "project": {"key": "TOMAKE"},
      "issuetype": {"name": "Задача"},
      "summary": "Согласовать договор с ...",
      "priority": {"name": "Обычный"},
      "description": "...",
      "components": [{"name": "Маркетинг"}]
    }
  }'
```

### REST API: получить поля проекта
```bash
load_confluence_env
# Все задачи проекта
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/2/project/TOMAKE" | python3 -m json.tool

# Доступные компоненты
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/2/project/TOMAKE/components"

# Приоритеты
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/2/priority"
```

---

## JSM: создать запрос в сервисдеске (servicedeskapi)

Запрос в портал сервисдеска (напр. `https://hq.tutu.ru/servicedesk/customer/portal/8/...`) создаётся **не** через `/rest/api/2/issue`, а через `POST /rest/servicedeskapi/request`:

```bash
source ~/.hermes/profiles/default/.env
curl -s -X POST -H "Authorization: Bearer $JIRA_TOKEN" -H "Content-Type: application/json" \
  "https://hq.tutu.ru/rest/servicedeskapi/request" -d '{
    "serviceDeskId": "8",
    "requestTypeId": "125",
    "requestFieldValues": {
      "summary": "...",
      "customfield_25356": {"id": "20577"},
      "description": "..."
    }
  }'
```
Ответ — `issueKey` (напр. `ADD-...`).

### Найти правильный request type

1. `GET /rest/servicedeskapi/servicedesk/{id}/requesttype?limit=100&start=N` — список типов (пагинация через `isLastPage`/`start`).
2. `GET /rest/servicedeskapi/servicedesk/{id}/requesttype/{rtId}/field` — поля типа + `validValues` (опции) + `required`.

**Питфолл — ссылка на группу портала, которую даёт Саша, может НЕ содержать нужный тип.** Группа 65 «Доступы» в ADD содержит только специфичные типы (Директ Кредит, ПШ, Госуслуги, безопасность, веб-аналитика, SolarStaff, мобильные, BotHub) и «Выдать доступ (NEW)», который не принимает `summary`/`description` (только выбор групп). Для Metabase/BI правильный тип — «Инструменты аналитики» (125) с опцией «Инструменты BI (MetaBase, CH, Exasol)» в поле «С чем нужна помощь». **Искать по всем request types совпадение по теме, а не только в указанной группе.**

### Формат значения option-поля

Работают оба: `{"id":"<optionId>"}` и `{"value":"<label>"}`. **`{"value":"<optionId>"}` (числовой id в `value`) НЕ работает** — ошибка «Идентификатор функции "null" недействителен». `optionId` брать из `validValues[].value`.

### Питфоллы

- **НЕ тестировать несколько форматов значения живым POST** — каждый успешный POST создаёт реальный запрос, а права на удаление запросов через API НЕТ (`DELETE /rest/api/2/issue/{key}` → 403, `DELETE /rest/servicedeskapi/request/{key}` → 500). Дубликаты придётся удалять вручную. Определять формат по схеме поля заранее; если всё же тестируешь — ожидай дубли и сразу предупреди Сашу.
- **`description` может получить шаблонные заголовки типа** (Контекст, Польза от вашей задачи...) — отправленный текст ложится в конец под «Дополнительное описание». Отдельные поля-ссылки (напр. `customfield_27053` «Полезные ссылки») могут не заполниться — URL надёжнее класть прямо в текст `description`.

---

## Важные правила процесса (регламент ТУТУ)

1. **Новый договор** → задача через АДД «Нужна помощь аккаунт-менеджеров», поле «Договор (расходный/доходный)». АДД автоматически создаёт задачу MIX.
2. **ДС/Приложение/Заявка к существующему договору** → задача напрямую в TOMAKE, за 2 недели до старта работ.
3. **Договор согласовывается ДО даты начала работ/оказания услуг.**
4. Исполнитель назначается автоматически (руководитель отдела или его замена).
5. Статусы: `Сделать` → `В работе` → `Требуется доработка` (→ автору назад).

Инструкции сохранены в WorkVault:
- `WorkVault/Confluence/UACCOUT/.../Как поставить задачу на аккаунта_ JIRA-TOMAKE/index.md`
- `WorkVault/Confluence/UACCOUT/.../MIX. Регламент _Передача договора.../index.md`

---

## Резолв пользователя Confluence (username / userkey)

Нужен, когда требуется собрать реальный `@mention` (`<ac:link><ri:user ri:userkey="..."/></ac:link>`) для вставки в Confluence Storage Format — например, при переносе участника/исполнителя задачи в протокол/минутки.

**Три рабочих эндпоинта (Confluence Server REST API, не Cloud):**

```bash
load_confluence_env

# 1. По известному login (может не совпадать с корпоративным!) → userKey + displayName
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/user?username=<login>"

# 2. По известному userKey → username + displayName (обратный резолв)
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/user?key=<userkey>"

# 3. По ФИО (самый надёжный способ, когда login неизвестен/не совпадает с корп.логином) — CQL fullname-поиск
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  --get --data-urlencode 'cql=user.fullname~"Середа Илья"' \
  "https://dom.tutu.ru/rest/api/search"
# → results[0].user.{username, userKey, displayName}
```

**Питфоллы:**
- **Confluence `username` ≠ корпоративный `login`** в значимой части случаев — обычно это фамилия без первой буквы имени (`isereda`→`sereda`, `dnabiev`→`nabieva`, `kkrivorotov`→`krivorotov`, `azhirov`→`zhirov`). Не полагаться на прямое совпадение — резолвить по ФИО (способ 3).
- **Глобального листинга пользователей нет** — `/rest/api/user/search?username=...` возвращает `404` в этой инсталляции (типично для Confluence Server без Crowd-плагина/с ограниченными правами PAT). Резолвить только точечно (по одному человеку за раз), не пытаться выгрузить весь каталог одним запросом.
- **CQL с кириллицей** нужно передавать через `--get --data-urlencode`, не собирать URL руками — иначе Tomcat вернёт `400 Invalid character` (см. также аналогичный питфол для JIRA в `tutu-jira-okr`).
- **⚠️ КРИТИЧНО — куда сохранять найденные `confluence_login`/`confluence_userkey`: только в зашифрованный `contacts.enc`, НИКОГДА в отдельный/новый plaintext-файл.** Единственное разрешённое хранилище контактов — `WorkVault/Contacts/contacts.enc` (см. скилл `about_usr_skills` → `AnywhereContacts`/`ContactStore`). Явное правило пользователя (07.2026, дословно): «Все контакты храним только в одном месте и все энкриптед». Если `confluence_login`/`confluence_userkey` — новые поля, которых ещё нет в схеме `contacts.enc` (`schema.py` → `CUSTOM_FIELDS`), сначала добавить их туда как custom-поля (не перезаписываемые синком коннекторов), затем писать значения через `ContactStore.update_contact(login, {...})`. Прецедент этой сессии: агент по ошибке создал/расширил параллельный незашифрованный `WorkVault/Contacts/tutu-contacts.md` с этими колонками (для ~25+13 контактов) — пользователь потребовал перенести все данные в `contacts.enc` и удалить plaintext-файл полностью. Не повторять — при первом же упоминании "резолвить участника" сразу открывать `contacts.enc` через `ContactStore`, не создавать/не расширять параллельные `.md`-реестры контактов.
- Люди, которые есть в реальных Confluence-минутках, но отсутствуют в `contacts.enc` (напр. сотрудники смежных подразделений/вендоры, упомянутые как участники встреч) — резолвятся так же через способ 3 и добавляются как новые контакты через `ContactStore`, не в отдельный файл.

## Формат страниц-протоколов (Минутки) — знание для будущей автопубликации

Реальная структура найдена в проектах Trisigma / AI-ready / AI-аналитик / ML-платформа — детали и оба варианта таблицы см. `references/confluence-meeting-protocol-format.md`. Кратко: страница — дочерняя (`child/page`) от корневой страницы проекта, называется `<Проект>. Задачи и договоренности (Минутки)`; задачи хранятся как `<ac:task>` с `<ri:user>`-упоминаниями и inline `<time datetime="YYYY-MM-DD"/>` — не отдельный макрос даты. **Полный источник истины по всем брифованным бизнес-решениям (тег проекта, идемпотентность, резолв проекта/участников/переговорок, триггер, scope) — скилл `about_usr_skills` → `references/confluence-minutki-protocol-format.md`; файл здесь — только техническая справка по формату Confluence Storage.**

> **Постановка/правка задач в минутках — через скилл `taskrefresh`** (`./tr new` / ручной PUT; раздел «Вставка задач в минутки проекта из внешнего источника»). Здесь поддерживается только формат (userkey-резолв, `<ac:task>`, PUT), канонический рецепт — в taskrefresh.

## Извлечение закрытых задач `<ac:task>` со страницы минутки: `parse_tasks_from_page`

Готовый метод в `confluencesync.tasks` — парсит `<ac:task>` из `body.storage` страницы минутки и возвращает только задачи, закрытые конкретным человеком в заданном периоде. Реализован по запросу SRTool v2.0 (selfcheck конца периода, см. `tutu-jira-sr`), но общий — переиспользуется любым инструментом, которому нужны закрытые задачи со страницы минутки (TaskRefresh, ProtocolFromSummary), не только SRTool.

```python
from confluencesync.confluence_client import ConfluenceClient
from confluencesync.tasks import parse_tasks_from_page, TaskRecord

client = ConfluenceClient(base_url, token)  # см. авторизацию выше
tasks: list[TaskRecord] = parse_tasks_from_page(
    client,
    page_id="490170597",           # напр. Trisigma-минутки
    userkey="8a8383b593a26ea60194abdf8d090020",  # ri:userkey исполнителя, не username
    date_from=date(2026, 7, 1),
    date_to=date(2026, 7, 31),
)
for t in tasks:
    print(t.date, t.raw_text)      # TaskRecord: task_id, status, userkey, date, raw_text, source_page
```

**Фильтры (все обязательны, задача исключается если хоть один не проходит):**
- `<ac:task-status>complete</ac:task-status>` — статус проверяется по тексту дочернего элемента, не по атрибуту.
- `ri:userkey` внутри `<ac:link><ri:user ri:userkey="..."/></ac:link>` внутри `<ac:task-body>` — сравнение точное, передавать userkey (см. резолв выше), не username/login.
- `<time datetime="YYYY-MM-DD"/>` внутри `<ac:task-body>` — дата должна попадать в `[date_from, date_to]` включительно; задачи без `<time>` пропускаются молча (не ошибка).

`raw_text` — очищенный текст задачи (`<span>` unwrap, `<ac:link>`/`<ac:structured-macro>`/`<time>` удалены), пригодный для прямой вставки как plain text.

**Питфол:** страница минутки может редактироваться человеком вручную (см. принцип выше про правку `<time>`/`<ac:link>` внутри `<ac:task-body>`) — метод ищет теги через `BeautifulSoup.find()` внутри `task_body`, что учитывает произвольную глубину вложенности (в отличие от lxml `element.find()`, который смотрит только на прямых потомков), так что обёртка `<p><span>...</span></p>` вокруг содержимого не ломает парсинг.

## Скрытые маркеры в теле страницы (storage format) — что реально переживает API PUT

Если нужно встроить невидимый ID/якорь в ячейку/строку таблицы (например, привязать строку минуток к внешнему `meeting_id`), **не гадай — большинство «очевидных» вариантов не работают**, потому что Confluence Server/DC санитизирует storage-format уже на этапе API PUT (до всякого веб-редактора):

- ❌ HTML-комментарии (`<!-- ... -->`) — вырезаются сервером при PUT.
- ❌ Произвольные `data-*` атрибуты на `<td>`/`<tr>` — вырезаются сервером при PUT.
- ✅ `<ac:structured-macro ac:name="anchor">` с `<ac:parameter>` — переживает PUT/GET нетронутым, в рендере невидим (превращается в пустой `<span>` с id).
- ✅ Inline `<span style="display:none">ID</span>` — переживает PUT/GET нетронутым.
- ✅ Невидимый текст (zero-width space + текстовый ID) внутри обычного текста ячейки — переживает как есть (это просто юникод-текст, не HTML).
- ✅ Content Properties API (`/rest/api/content/{id}/property`, POST/GET/DELETE) — надёжно хранит произвольный JSON на уровне страницы (не строки/ячейки); для привязки к конкретной строке комбинировать с anchor-макросом в самой ячейке, а не с `row_index` (сбивается при перестановке/удалении строк человеком).

**Проверено и подтверждено (10.07.2026):** anchor-макрос пережил не только API round-trip, но и реальное ручное редактирование текста строки владельцем страницы через обычный веб-редактор Confluence — на двух боевых страницах (Trisigma, Кирилл 1-1), маркер остался нетронутым после правки. Anchor-макрос + Content Properties API — рабочая, эмпирически подтверждённая комбинация, можно строить pipeline без дополнительной защиты.

Полный протокол эксперимента (реальные PUT/GET на тестовой странице, точные payload'ы, финальное подтверждение живым тестом) — `references/confluence-storage-format-hidden-markers.md`.

## Правка существующего inline-тега (`<time>`, `<ac:link>` и т.п.) внутри `<ac:task-body>`/ячейки после ручного редактирования человеком (найдено 13.07.2026)

Когда владелец страницы регулярно правит опубликованный контент через веб-UI Confluence (см. принцип выше), редактор **оборачивает** исходно плоскую разметку в дополнительные inline-теги форматирования — типично `<p><span><span class="...">...</span></span></p>` вокруг содержимого `<ac:task-body>`. Это меняет глубину вложенности искомого тега.

**Баг:** код, который ищет существующий тег (`<time>`, `<ac:link>`) через `element.find("time")` (lxml — ищет только среди ПРЯМЫХ потомков), не находит его, если тег теперь на 2-3 уровня глубже из-за такой обёртки. Результат — код считает, что тега «не было», и **создаёт новый** рядом со старым (дубль), вместо того чтобы отредактировать существующий.

**Фикс:** искать через обход всего поддерева (`element.iter()` в lxml), а не только прямых потомков (`element.find()`), когда элемент может редактироваться человеком через WYSIWYG-интерфейс:

```python
# Вместо: time_el = body_el.find("time")  # только прямые потомки — ломается на вложенности
time_el = None
for el in body_el.iter():
    tag = etree.QName(el).localname if isinstance(el.tag, str) else None
    if tag == "time" and el is not body_el:
        time_el = el
        break
```

Аналогично при удалении — `parent = time_el.getparent(); parent.remove(time_el)` (не `body_el.remove(time_el)`, которое падает, если найденный элемент не прямой потомок `body_el`).

**Диагностика на живой странице перед фиксом:** после любой правки inline-значения (дедлайна, mention) — обязательно перепроверить результат прямым GET и посчитать вхождения тега в затронутом блоке (`block.count("<time")` должно быть 1, не 2). Не полагаться на то, что PUT прошёл без ошибки — санитайзер Confluence пропускает дубли молча, ошибка появляется только при повторном чтении контента человеком.

**Один и тот же баг может не проявляться на всех задачах одной страницы** — только на тех, где реально была ручная правка форматирования; соседние задачи с исходной плоской структурой продолжат работать корректно тем же кодом. Не считать единичный успешный тест на другой задаче доказательством отсутствия бага.

## Создание новой дочерней страницы (POST)

```bash
load_confluence_env
curl -s -X POST \
  -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  -H "Content-Type: application/json" \
  "https://dom.tutu.ru/rest/api/content" \
  -d @/tmp/payload.json
```

Минимальная структура payload:
```json
{
  "type": "page",
  "title": "Парсинг. Название сервиса",
  "ancestors": [{"id": "511554221"}],
  "space": {"key": "DPAN"},
  "body": {
    "storage": {
      "value": "<h1><a href=\"https://service.io\">Название</a></h1><table>...</table>",
      "representation": "storage"
    }
  }
}
```

- `ancestors[0].id` — pageId родительской страницы (не пространства!)
- `space.key` — ключ пространства, например `DPAN` или `~tkachenkoav`
- Ответ содержит `id` созданной страницы → URL: `https://dom.tutu.ru/pages/viewpage.action?pageId=<id>`

**Стиль заголовка H1 с гиперссылкой на сайт сервиса:**
```html
<h1><a href="https://webshare.io">Webshare</a></h1>
```
URL сервиса искать в сводной таблице родительской страницы — поле `href` рядом с именем сервиса.

**Стиль ссылок в тексте задач и страниц:** ссылка вшивается в осмысленное слово текста (`<a href="...">страничке</a>`), а не оформляется отдельным словом `(ссылка)` после текста. Это правило распространяется на задачи в Confluence-минутках и на тело страниц.

**Выдача ссылки Саше (vinc):** одна строка — `https://dom.tutu.ru/pages/viewpage.action?pageId=<id>` + page name (не голый id).

## Перенос строки таблицы между страницами Confluence

Паттерн: вырезать `<tr>...</tr>` из одной страницы и вставить в другую. Используется например при переносе протокола встречи из «неразобранных» в нужный проект.

**Алгоритм:**
1. GET обеих страниц (`?expand=body.storage,version`) → сохранить в `/tmp/src.json` и `/tmp/dst.json`
2. Найти строку в src: `tr_start = body.rfind('<tr>', 0, anchor_idx)`, `tr_end = body.find('</tr>', anchor_idx) + len('</tr>')`
3. Вырезать из src: `new_src = body[:tr_start] + body[tr_end:]`
4. Вставить в dst после первой строки (`</tr>`): `insert_at = body_dst.find('</tr>') + len('</tr>')`
5. PUT обе страницы с bumped version

**Питфолл:** `first_tr_end` находит заголовочную строку — вставка идёт после неё (вверх таблицы). Если нужно в конец — искать последний `</tr>` перед `</table>`.

**Поиск строки по `pfsrow-*` anchor:**
- `pfsrow-7e76e50296a9` — это row_anchor из реестра `~/WorkVault/ProtocolFromSummary/_registry.json`
- `grep -B5 -A15 'pfsrow-<id>' ~/WorkVault/ProtocolFromSummary/_registry.json` покажет `source_summary`, `meeting_name`, `page_id`
- Anchor физически живёт в теле страницы как `<ac:structured-macro ac:name="anchor"><ac:parameter>pfsrow-...</ac:parameter></ac:structured-macro>`

## Перенос страниц (с деревом) между пространствами Confluence

**Цель:** перенести родителя «Встречи неразобранные» и все дочерние минутки из личного `~tkachenkoav` в пространство `DPAN` под корень «Общий список задач» (432316254), сохранив pageId (чтобы не сломать PFS/OFC/TR, цепляющиеся на id).

### Главный питфолл: **move через REST НЕВОЗМОЖЕН на Server/DC**
Проверено (11.09.2026, Confluence 8.9.4). Автоматически перенести страницу в **другое пространство** через API нельзя:
- `PUT /rest/api/content/{id}` с `space:{key}` → **400 «You can't change an existing page's space»**
- Cloud-эндпоинты `/move/append/{targetId}`, `/move` → **404** (нет на Server)
- XML-RPC `confluence2.movePage` — метод есть, но требует `login(username, password)`; **PAT как пароль не проходит** (`AuthenticationFailedException`)

→ **Единственный способ — ручной Move через UI:** ⋯ → **Переместить (Move)** → в другое пространство → вставить как дочернюю к нужной. При move страницы **иерархия детей утащится следом**, pageId **не меняются** (CONTENTID в БД тот же) — ссылки `?pageId=`, вложения, история целы. Copy/recreate — НЕ использовать (новые id → ломает реестры).

**Проверка после move:**
```bash
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" "https://dom.tutu.ru/rest/api/content/<id>?expand=space,ancestors" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['space']['key'],[a['id'] for a in d['ancestors']])"
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" "https://dom.tutu.ru/rest/api/content/<parent>/child/page"  # дети сохранили id
```

**Совместимость с дашбордами задач (OpenTasks 492610494, «Активные задачи по проектам АиД» 412092707):** они построены на макросе `tasks-report-macro`, фильтрующем по `spaces` + `labels` (обычно `_aid`), **не по pageId**. Поэтому после переноса страниц в DPAN задачи продолжают отображаться автоматически — при условии, что на странице стоит метка, которую макрос требует. Проверять label: `GET /rest/api/content/{id}/label` → `results[].name`; отсутствие `_aid` на странице = её задачи не попадают в дашборд (это было так и до переноса).

## Правка дашборда задач OpenTasks (вкладки tabs-group / tasks-report-macro)

Дашборд OpenTasks (pageId 492610494) — макрос `tabs-group` → вкладки `tab-pane` → `tasks-report-macro` (`spaces` / `labels=_aid` / `assignees` = `<ri:user ri:userkey="..."/>`; **отсутствие `assignees` = все пользователи**; `status=complete` = DONE). Полный алгоритм правки вкладок (переименование, удаление, смена исполнителя, «все пользователи», перемещение в конец, verify) — `references/opentasks-tabs-editing.md`.

**Ключевые питфоллы:**
- Конец вложенного макроса (tab-pane с tasks-report внутри) искать **счётчиком глубины** `<ac:structured-macro>`/`</ac:structured-macro>`, не по первому `</ac:structured-macro>`.
- При перемещении вкладки в конец вставлять её ПЕРЕД хвостом (закрытием tabs-group): `b[:last_inside_end] + pane_text + b[last_inside_end:ps] + b[pe:]`. Вставка после хвоста даёт PUT ok, но панель рендерится отдельным блоком ПОД вкладками.
- `body.view` рендерит только активную (первую) вкладку; неактивные грузятся JS. Проверять структуру повторным GET, живой вид — глазами Саши (браузер ВМ упирается в SSO keycloak).

### Персональные права (restrictions) в Server/DC

Два слоя: **space permissions** (на всё пространство) и **content restrictions** на странице (сужают, операции `read`/`update`).

**Ставить restriction (Server 8.8+, PUT):**
```bash
curl -s -X PUT -H "Authorization: Bearer $CONFLUENCE_TOKEN" -H "Content-Type: application/json" \
  "https://dom.tutu.ru/rest/api/content/<pageId>/restriction" -d '[
    {"operation":"read","restrictions":{"user":[{"type":"known","username":"tkachenkoav"},{"type":"known","username":"<login>"}],"group":[]}},
    {"operation":"update","restrictions":{"user":[{"type":"known","username":"tkachenkoav"},{"type":"known","username":"<login>"}],"group":[]}}
  ]'
```
**Питфоллы:**
- **В список обязательно включать `tkachenkoav`** — Bearer инструментов = тот же аккаунт; иначе PFS/TR потеряют GET/PUT к странице.
- **GET `/restriction/byOperation` без суффикса возвращает `size: null`** (пусто выглядит так же, как нет данных). Читать по каждой операции: `/restriction/byOperation/read` и `/restriction/byOperation/update` — именно они показывают реальных юзеров.
- Restriction **не наследуется на детей** — приватность выставляется **на каждой странице отдельно** (вариант А: закрыть только сами 1-1, родитель оставить открытым — тогда в дереве видны заголовки чужих, но содержимое недоступно).
- При `PUT` пустые массивы `user:[]` снимают restriction по этой операции; **нельзя снять доступ у самого себя**.
- Для move в другой space на restricted-страницы нужна проверка права **Restrict** в целевом space; безопаснее: сначала move (страницы открытые), затем сразу restriction (окно утечки — минуты).

## Вставка JIRA-задачи в Confluence — два контекста

### 1. Ячейка таблицы (колонка «Задача JIRA»)

Когда переносишь список JIRA-задач в **таблицу** Confluence (колонка «Задача JIRA»), **не используй обычную гиперссылку** `<a href="https://hq.tutu.ru/browse/ADD-...">ADD-...</a>`. Саша предпочитает/переделывает на **JIRA-макрос** (`ac:structured-macro ac:name="jira"`) — он рендерится со статусом/иконкой задачи и кликабелен. Правило из практики (17.08.2026, страница Trisigma pageId=514890974): после вставки обычными ссылками Саша попросил переделать все на JIRA-макросы.

**Формат ячейки «Задача JIRA» (заменяет голую ссылку):**
```html
<div class="content-wrapper"><p><ac:structured-macro ac:name="jira" ac:schema-version="1" ac:macro-id="<uuid>">
<ac:parameter ac:name="server">hq.tutu.ru JIRA</ac:parameter>
<ac:parameter ac:name="serverId">96df2b63-d15b-3ac4-b14d-2b3359ac8420</ac:parameter>
<ac:parameter ac:name="key">ADD-620619</ac:parameter>
</ac:structured-macro></p></div>
```

**Правила сборки:**
- `key` — номер задачи (`ADD-...`) — единственное, что меняется от строки к строке
- `server` = `hq.tutu.ru JIRA`, `serverId` = `96df2b63-d15b-3ac4-b14d-2b3359ac8420` — константы JIRA-сервера ТУТУ
- `macro-id` — **уникальный uuid4 на каждый макрос** (не повторять один id на все строки)
- Обёртка `<div class="content-wrapper"><p>...</p></div>` вокруг макроса — как в выходе веб-редактора; при вставке внутри `<td>` её сохранить

**Питфоллы:**
- Не копировать один и тот же `macro-id` на все строки — каждая ячейка должна иметь свой uuid4
- Массовую замену существующих ссылок выполнять через строковую `replace` по ключу (`<a href="...">{KEY}</a>` → макрос), проверять результат повторным GET: `b.count('ac:name="jira"')` == числу задач, `len(re.findall(r'href="https://hq.tutu.ru/browse/', b))` == 0
- Схема таблицы (колонки Задача JIRA / Подразделение / Исполнитель) уже существует на странице — заполнять пустые `<tr>`, не пересоздавать таблицу

### 2. Тело задачи `<ac:task-body>` (минутки, OpenTasks)

Для **ссылок внутри задачи** (не ячейки таблицы) — использовать **TaskRefresh**:

```bash
cd ~/USERTOOLS/TaskRefresh
./tr apply "#N ссылка https://hq.tutu.ru/browse/ADD-568390"
./tr apply "#N ссылка https://hq.tutu.ru/browse/ADD-1,https://hq.tutu.ru/browse/TOMAKE-2"
./tr confirm
```

| URL | Куда вставляется | Формат |
|---|---|---|
| `https://hq.tutu.ru/browse/<KEY>` | `<ac:task-body>` | JIRA-макрос `ac:name="jira"` (через `./tr`) |
| Любой иной URL | `<ac:task-body>` | Обычная `<a href>` (через `./tr`) |
| JIRA в колонке таблицы | `<td>` ячейки | JIRA-макрос (ручной PUT или шаблон ниже) |

Подробности: скилл `taskrefresh`, раздел «JIRA-референсы в теле задачи» (§25).

## Ручное удаление строки таблицы минуток

**Загрузи скилл `taskrefresh` перед выполнением** — полная процедура там, раздел «Ручное удаление строки таблицы минуток». Общая техника «GET → find `<tr>...</tr>` → PUT» одинаковая, различается только семантика владельца задачи.

## Принцип для инструментов, пишущих в Confluence-страницы, которые человек регулярно правит руками (найдено 10.07.2026, ProtocolFromSummary)

Если владелец страницы (Саша) сам, часто и осознанно редактирует уже опубликованный ботом контент (шлифует формулировки, дополняет решения/задачи) — это меняет базовые допущения любого автосинк-инструмента:

1. **Инструмент никогда не удаляет ничего в Confluence сам.** Удаление — всегда явное действие человека вручную. Автоматика только **копирует** и **заменяет содержимое строки той же сущности** (например, republish = найти свою же строку и обновить её текст, не «удалить+вставить» как отдельные операции над чужим/неопределённым материалом). Если нужно перенести данные между двумя страницами («перепривязка», «copy в другой протокол») — это **copy без удаления источника**, а не move; человек сам решает, удалять ли исходную строку. **Явное исключение — Саша лично просит удалить конкретную запись:** загрузи скилл `taskrefresh`, раздел «Ручное удаление строки таблицы минуток».
2. **Любое GET-чтение существующего контента считается возможно устаревшим/изменённым human-ом к моменту записи** — не воспринимать расхождение как «испорченные данные» или ошибку конкурентной записи, а как нормальный facts-of-life; graceful degradation (не восстанавливать, не блокировать, залогировать и продолжить) — правильная реакция по умолчанию.
3. **Отслеживание "эта строка = вот эта исходная запись" не может опираться на видимый текст** (он меняется) — нужен `row_anchor`: невидимый маркер, физически размещённый в самой строке (anchor-макрос, см. выше), плюс Content Properties API как источник истины на уровне страницы. Вычисляется один раз при первой публикации (например хэш от внешнего ID), никогда не пересчитывается из текста.
4. Перед тем как полагаться на конкретный технический механизм маркера — эмпирически протестировать его (см. `references/confluence-storage-format-hidden-markers.md`), не полагаться на предположения о поведении Confluence storage-санитайзера.
5. **Не путать разные "источники истины" для операций copy/republish в такой системе — легко смешать, но семантика принципиально разная.** Прецедент 10.07.2026 (ProtocolFromSummary): агент сам смешал два похожих сценария, пользователь поправил явно ("там мы копировали инфу из конфлюенс в конфлюенс, а тут надо будет перезаливать ранее залитое самари из ФФ"):
   - **Copy между Confluence-страницами** — источник данных = **текущее живое содержимое** исходной Confluence-строки, включая любые ручные правки владельца после первой публикации. Читать строго через GET у Confluence, не из архива/файла.
   - **Замена целевой страницы + republish** (например, pageId сущности пересоздали) — источник данных = **оригинальный сырой файл из системы захвата** (Fireflies/summary-файл), НЕ то, что сейчас лежит в Confluence. Строка публикуется заново с нуля от исходных данных, минуя текущее состояние старой Confluence-страницы.
   При проектировании любой операции "перенести/восстановить/переопубликовать данные о встрече" — явно фиксировать для каждой из них, откуда именно берутся данные (живой Confluence vs исходный файл), не предполагать по умолчанию, что это одно и то же.

См. также `hermes-feature` (Pitfall 24-26) — процесс эмпирической проверки архитектурных решений через delegate_task перед их фиксацией в ТЗ, когда вопрос брифа зависит от непроверенного факта о поведении внешней системы.

## Workflow: creating/updating Jira tasks

Restate the task spec, wait for Sasha's answers, then act ("делай"). Task URL pattern: `https://hq.tutu.ru/browse/KEY`.

## Экспорт Jira-задач в Obsidian

**Именование файлов (per-task экспорт):** `{KEY} + первые ~60 символов названия задачи` — читаемые имена, не голый ключ. Кириллица в имени файла допустима ради читаемости (осознанное исключение из правила ASCII-only Obsidian-скилла).

## Питфоллы

- **`web_extract` блокирует dom.tutu.ru** — resolves to internal 10.x.x.x. Всегда использовать `terminal` + curl или ConfluenceSync CLI.
- **Ячейка таблицы с простым текстом**: Confluence-санитайзер storage-формата снимает `<td>` у ячеек вида `<td><p>текст</p></td>` — оставляет голый `<p>` прямо в `<tr>`, и таблица рендерится криво (текст «съезжает», колонки теряются). Каноничные форматы ячейки: простой текст — `<td>текст</td>` (без обёртки `<p>`); ячейка с макросом (`ac:link`, `time`, `status`, `expand`, `code`) — `<td><div class="content-wrapper"><p>...</p></div></td>`; пустая ячейка — `<td><p><br /></p></td>`. После PUT обязательно проверять живым GET, что в каждой вставленной строке ровно N `<td>` и нет голых `<p>` внутри `<tr>`.
- **table-filter «Запросы к данным»: строки класть в ГЛАВНЫЙ `<tbody>`, не во вложенную легенду.** В этом шаблоне заголовочный ряд `<tr class="">` содержит колонку «Статус (заполняет владелец данных)» с вложенным макросом `tooltip2`, а внутри него — вложенную `<table>`-легенду (4 строки «будут реализованы» → «В РАБОТЕ» и т.д.). Наивный анкер вида `</tbody></table><p …>` совпадает с концом этой ВЛОЖЕННОЙ таблицы, поэтому строки уходят ВНУТРЬ легенды и страница выглядит пустой (строки «запрятаны» в тултип) — Саша видит пустую таблицу и переспрашивает. Правильно: data-строки вставлять после закрытия заголовочного `</tr>` и перед первым вхождением `</tbody></table></ac:rich-text-body>` (это конец главной таблицы table-filter #0, а вложенная легенда закрывается как `</tbody></table>` + текст, без `</ac:rich-text-body>` сразу). Тег data-строки — `<tr>` без `class`; заголовочной — `<tr class="">`. Верифицировать: в главной таблице `<tr>`(без class) == числу строк, легенда остаётся ровно 4 шт `<tr class="">`.
- **НЕ пропускать HTML-теги через эскейпер.** Если хелпер вида `p(t)`/`esc(t)` делает `html.escape(t)`, в него можно передавать только чистый текст. Строки с готовой разметкой (`<strong>`, `<br/>`, `<a href>`, `<h3>`) собирать вручную (литеральные теги + `esc()` только на текстовых кусках). Иначе на странице виден буквальный текст `<strong>…</strong>`, `<br/>` — «маркеры», которые Саша просит убрать. После сборки обязательно проверять живым GET: `body.count('&lt;') == 0` в своих вставках. Confluence нормализует `<br/>` → `<br />` — это норм, не дефект.
- **ConfluenceSync .env содержит PAT** — `load_confluence_env` перед curl.
- **`--dest` флага нет** у confluencesync pull — путь сохранения определяется автоматически по иерархии Confluence; управление через `.env` WORKVAULT_PATH.
- После изменений в WorkVault — `rclone sync ~/WorkVault owncloud:WorkVault`.
- **REST API возвращает 404 на некоторые pageId** — не ошибка конфигурации. Причины: страница в пространстве без прав для PAT, или пространство использует SSO/keycloak-only авторизацию. Это нормально — зафиксируй ссылку для ручного открытия, не трать время на обходы. **Единственный выход при 404 — дать пользователю готовый текст/инструкцию и попросить вставить вручную.** Пример: pageId=511559466 («Настройка ссылки Zoom») — 404 через PAT даже при валидном токене (23.07.2026).
- **Zoom Marketplace Server-to-Server OAuth scope `meeting:write:meeting:admin`** — в корпоративном аккаунте ТУТУ этот scope недоступен для выбора (не отображается в UI, скрыт политикой аккаунта). Нужно обращаться к Zoom-админу ТУТУ. Токен и само приложение создаются нормально, ошибка проявляется только при вызове `POST /v2/users/{id}/meetings` → код 4711. Credentials хранятся в `~/.hermes/profiles/anthropic/.env` (`ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`). Скрипт тестирования: `/home/tkachenkoav/USERTOOLS/ZoomAPI/test_zoom.py`. Детали — `references/zoom-api-setup.md`.
- **confluencesync pull выводит «✓ pulled 0 page(s)»** на уже скачанной странице — нужен флаг `--resync` для перезаписи. Без флага пропускает существующие файлы молча.
- **Найти дочерние страницы проекта (протоколы/минутки/материалы)** — `curl ... "https://dom.tutu.ru/rest/api/content/<rootPageId>/child/page?limit=50"`, возвращает `results[].{id,title}`. Полезно, когда известен только `confluence_id` корня проекта (как в `card.md`), а не сама страница протокола.
- **Тело Confluence-страницы содержит backslash-последовательности** — `json.loads()` на stdout curl падает с `JSONDecodeError: Invalid \\escape`. Решение: сохранить в файл (`curl ... > /tmp/page.json`), читать через `json.load(open('/tmp/page.json'))`. Удалять `/tmp/page.json` сразу после использования (PII/внутренний контент).
- **Поле `space` отсутствует в GET-ответе по умолчанию** — `?expand=body.storage,version` не возвращает поле `space`. Для payload PUT существующей страницы нужны только `title` + `version.number` + `type: "page"` + `body` — `space` не требуется. Если space_key необходим явно — добавить `expand=body.storage,version,space`. Попытка читать `data['space']` без этого expand → `KeyError`.
- **Python в `terminal()` с кавычками и регэкспами**


## Вестник (VestnikTheme)

Триггеры: «добавь тему в вестник», «добавь в вестник», «тема для вестника», «размести на страничке вестника» + ссылка(и) на материал Confluence.

**Запрет:** LLM не генерирует `body.storage` Вестника. Строка таблицы собирается только скриптом `scripts/vestnik_theme.py`.

Страница: `pageId=324382467` («Вестник Аналитики и Данных», space `DPAN`). Патч — первая пустая `<tr>` таблицы «Итоговый материал» первого `horizontal-nav-item`.

```bash
# Превью (по умолчанию, PUT нет)
python3 ~/hermes-workspace/skills/productivity/tutu-confluence-jira/scripts/vestnik_theme.py \
  add --page-id 517103930

# Запись в Confluence
python3 ~/hermes-workspace/skills/productivity/tutu-confluence-jira/scripts/vestnik_theme.py \
  add --page-id 517103930 --apply
```

Для GAL/AC при live-run: `~/USERTOOLS/AnywhereContacts/venv_linux/bin/python` (тот же скрипт).

- `--dry-run` — режим по умолчанию (без `--apply`): GET разрешён, PUT нет.
- `--apply` — PUT с `version+1`, payload **без** `space`.
- HITL (контакт не найден, конфликт темы) — stdout, exit 2, **не** ErrorBus.
- Технические ошибки → `~/.hermes/scripts/report_error.sh --tool VestnikTheme --source-kind skill`.

---

## Связанные скиллы

- `obsidian` — работа с WorkVault напрямую
- `pm-briefing` — брифование PM по открытым вопросам задачи

## Бриф по договорным задачам

Когда готовим задачу TOMAKE, часть полей может быть неизвестна заранее.
Бриф проводить в формате pm-briefing: **один вопрос — номерованные варианты — рекомендация**.

**Куда записывать ответы:** `WorkVault/Tasks/<название-задачи>.md` (мини-ТЗ), не в pm/-структуру.

Порядок вопросов по приоритету (блокирующие сначала):
1. **КБК** — без него задача вернётся на доработку
2. **Кто подтверждает оплату** — только для расходных
3. **Срок действия договора** — начало/конец
4. Механика, контакты партнёра, ЭДО, уставные документы

Если КБК неизвестен — искать в `references/kbk-tech-articles.md`,
предложить подходящую статью, элемент финансовой структуры уточнить у заказчика.

---

## Ссылки

- `references/tomake-contract-fields.md` — обязательные поля для согласования договора в TOMAKE
- `references/kbk-tech-articles.md` — справочник технических статей КБК для ИТ-договоров
- `references/confluence-meeting-protocol-format.md` — реальный формат страниц-протоколов "Задачи и договоренности (Минутки)" (оба варианта таблицы, формат `<ac:task>`, userkey найденных людей вне основного реестра контактов)
- `references/section-patch.md` — патч одной секции storage (GET → inner replace → PUT)
- `references/verify-skeleton.md` — 7-пунктовый чеклист после PUT
- `references/confluence-storage-format-hidden-markers.md` — экспериментально проверенные варианты невидимых маркеров/ID в ячейках таблицы Confluence storage-формата: что переживает API PUT round-trip, что вырезается сервером, что осталось непроверенным (реальное ручное редактирование через веб-UI)
- `references/opentasks-tabs-editing.md` — правка дашборда OpenTasks: структура tabs-group/tab-pane/tasks-report-macro, парсинг вложенных макросов, операции над вкладками, питфоллы, verify
- `references/zoom-api-setup.md`

**Ключевые pageId:**
- Общий список задач: `432316254`
- Trisigma-минутки: `490170597`
- AI-аналитик минутки: `477061038`
- Неразобранные summary встреч: `508804852`
- Аралов 1-1: `508804897`
- OpenTasks: `492610494`

Работа с целями OKR (проекты OKRS/OKRAID) — отдельный скилл `tutu-jira-okr`, не здесь.
