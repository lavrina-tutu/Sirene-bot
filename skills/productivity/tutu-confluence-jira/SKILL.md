---
name: tutu-confluence-jira
description: "ТУТУ корп. системы: Confluence + JIRA. Загружать при: скачать/открыть страницу Confluence, создать/найти задачу в Jira, кто такой X (оргструктура: Аралов→Ткаченко→Криворотов), согласование договора, резолв участника по ФИО/userkey, публикация протокола встречи, экспорт Jira-задач в Obsidian. URL: dom.tutu.ru / hq.tutu.ru. Auth: ConfluenceSync .env."
version: 1.3.0
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
| JIRA (`hq.tutu.ru`) | `~/.hermes/profiles/anthropic/.env` | `JIRA_TOKEN` + `JIRA_BASE_URL=https://hq.tutu.ru` |

⚠️ **`~/.config/hermes/.env` сломан** — содержит спецсимволы в `TUTU_DOMAIN_PASSWORD`, bash падает с syntax error при `source`. Для JIRA использовать **только** `~/.hermes/profiles/anthropic/.env`.

Загрузить Confluence: `source ~/USERTOOLS/ConfluenceSync/.env`

Для Confluence curl:
```bash
curl -H "Authorization: Bearer $CONFLUENCE_TOKEN" "https://dom.tutu.ru/rest/api/..."
```

Для JIRA curl:
```bash
source ~/.hermes/profiles/anthropic/.env
curl -H "Authorization: Bearer $JIRA_TOKEN" \
     -H "Content-Type: application/json" \
     "https://hq.tutu.ru/rest/api/2/..."
```

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
source ~/USERTOOLS/ConfluenceSync/.env
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
source ~/USERTOOLS/ConfluenceSync/.env

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
source ~/USERTOOLS/ConfluenceSync/.env
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
source ~/USERTOOLS/ConfluenceSync/.env

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
source ~/USERTOOLS/ConfluenceSync/.env
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
- **ConfluenceSync .env содержит PAT** — `source ~/USERTOOLS/ConfluenceSync/.env` перед curl.
- **`--dest` флага нет** у confluencesync pull — путь сохранения определяется автоматически по иерархии Confluence; управление через `.env` WORKVAULT_PATH.
- После изменений в WorkVault — `rclone sync ~/WorkVault owncloud:WorkVault`.
- **REST API возвращает 404 на некоторые pageId** — не ошибка конфигурации. Причины: страница в пространстве без прав для PAT, или пространство использует SSO/keycloak-only авторизацию. Это нормально — зафиксируй ссылку для ручного открытия, не трать время на обходы. **Единственный выход при 404 — дать пользователю готовый текст/инструкцию и попросить вставить вручную.** Пример: pageId=511559466 («Настройка ссылки Zoom») — 404 через PAT даже при валидном токене (23.07.2026).
- **Zoom Marketplace Server-to-Server OAuth scope `meeting:write:meeting:admin`** — в корпоративном аккаунте ТУТУ этот scope недоступен для выбора (не отображается в UI, скрыт политикой аккаунта). Нужно обращаться к Zoom-админу ТУТУ. Токен и само приложение создаются нормально, ошибка проявляется только при вызове `POST /v2/users/{id}/meetings` → код 4711. Credentials хранятся в `~/.hermes/profiles/anthropic/.env` (`ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`). Скрипт тестирования: `/home/tkachenkoav/USERTOOLS/ZoomAPI/test_zoom.py`. Детали — `references/zoom-api-setup.md`.
- **confluencesync pull выводит «✓ pulled 0 page(s)»** на уже скачанной странице — нужен флаг `--resync` для перезаписи. Без флага пропускает существующие файлы молча.
- **Найти дочерние страницы проекта (протоколы/минутки/материалы)** — `curl ... "https://dom.tutu.ru/rest/api/content/<rootPageId>/child/page?limit=50"`, возвращает `results[].{id,title}`. Полезно, когда известен только `confluence_id` корня проекта (как в `card.md`), а не сама страница протокола.
- **Тело Confluence-страницы содержит backslash-последовательности** — `json.loads()` на stdout curl падает с `JSONDecodeError: Invalid \\escape`. Решение: сохранить в файл (`curl ... > /tmp/page.json`), читать через `json.load(open('/tmp/page.json'))`. Удалять `/tmp/page.json` сразу после использования (PII/внутренний контент).
- **Поле `space` отсутствует в GET-ответе по умолчанию** — `?expand=body.storage,version` не возвращает поле `space`. Для payload PUT существующей страницы нужны только `title` + `version.number` + `type: "page"` + `body` — `space` не требуется. Если space_key необходим явно — добавить `expand=body.storage,version,space`. Попытка читать `data['space']` без этого expand → `KeyError`.
- **Python в `terminal()` с кавычками и регэкспами**


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
- `references/confluence-storage-format-hidden-markers.md` — экспериментально проверенные варианты невидимых маркеров/ID в ячейках таблицы Confluence storage-формата: что переживает API PUT round-trip, что вырезается сервером, что осталось непроверенным (реальное ручное редактирование через веб-UI)
- `references/zoom-api-setup.md`

**Ключевые pageId:**
- Общий список задач: `432316254`
- Trisigma-минутки: `490170597`
- AI-аналитик минутки: `477061038`
- Неразобранные summary встреч: `508804852`
- Аралов 1-1: `508804897`
- OpenTasks: `492610494`

Работа с целями OKR (проекты OKRS/OKRAID) — отдельный скилл `tutu-jira-okr`, не здесь.
