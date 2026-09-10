---
name: plan-reconciliation-mpp-jira
description: "Use when: сверить план mpp с jira."
version: 1.1.0
author: agent
platforms: [linux]
tools: [terminal, read_file, write_file, execute_code]
metadata:
  hermes:
    tags: [mpp, jira, advanced-roadmaps, reconciliation, google-sheets, plan]
    related_skills: [read-mpp, tutu-confluence-jira, google-workspace]
---

# Сверка плана MPP с Jira Advanced Roadmaps

Сопоставление плана проекта из MS Project (.mpp) с планом **Jira Advanced Roadmaps (Plans)** в части завершённости задач. Итог — Google Sheets-таблица, где каждая строка MPP дополнена ссылкой на задачу Jira, статусом, датой и комментарием Сирени о надёжности матча.

## Рабочие скиллы (использовать, не обходить)

- `read-mpp` — парсинг .mpp в CSV и заливка в GS (`read_mpp.py`, `push_to_gs.py`, `google_api.py`).
- `tutu-confluence-jira` — Jira REST (hq.tutu.ru), токен `JIRA_TOKEN` из `~/.hermes/profiles/default/.env`, base `https://hq.tutu.ru`.
- `google-workspace` — OAuth/Sheets API (`google_api.py`), токен `~/.hermes/google_token.json`.

## Ключевой факт о Advanced Roadmaps (Jpo plugin)

**У Advanced Roadmaps (plugin Jpo) на Jira Server/DC НЕТ публичного REST API для чтения структуры плана.**

- `GET /rest/jpo/1.0/plans` → HTTP 500 (нужен внутренний заголовок `ap-client-key`, приложениям не доступен).
- `POST /rest/jpo/1.0/plans` → HTTP 500 `element must not be null`.
- `GET /rest/jpo/1.0/plan/{id}` → HTTP 404; `/rest/jpo/1.0/export` → HTTP 404 (это экспорт всей инсталляции, не отдельного плана).
- `GET/POST /rest/jpo/1.0/info/query`, `/config`, `/plan/{id}/issues` → 404.

**Рабочий обход:** задачи любого плана — это **живые задачи Jira** (план берёт источник из проекта/борда/фильтра). Поэтому состав и статусы плана tянем обычным Jira search API: `GET /rest/api/2/search?jql=project=<KEY> ORDER BY key`, пагинация по 100, поля `summary,status,resolutiondate,resolution,issuetype,parent`. Проект определяется по задачам, найденным по названиям пунктов MPP (в примере — проект `MLE`, ~490 задач). Детальную разведку эндпоинтов см. `references/jpo-advanced-roadmaps-api.md`.

## Процесс

1. **Парсинг MPP → CSV** (см. `read-mpp`): `read_mpp.py <file>.mpp --format csv`. Реальный .mpp приходит как .zip (переименованный OLE2, MS Project) — сначала `cp` в `.mpp`, затем парсить.
   - leaf-задачи плана — строки с `outline_level == 2` (level 0/1 — суммарные, вехи/отпуска в level 2 тоже попадают — их отсеивать по смыслу, т.к. не являются задачами Jira).
2. **Выгрузка всего набора задач проекта Jira** (не поштучные CQL — дают шум). Пагинация по 100 до `total`.
3. **Сопоставление по названию.**
   - Точное совпадение нормализованных имён почти всегда **пусто** (названия MPP и Jira отличаются).
   - Рабочий метод: **пересечение слов** (`re.findall(r'[a-zа-яё0-9]{3,}', name.lower())`) между именем MPP-пункта и summary задач Jira; брать единственного лучшего кандидата по числу общих слов (порог ≥2), при ничьей — все варианты.
   - Это даёт **шум**: дубли (два пункта MPP → одна и та же Jira-задача), ложные подтягивания (по общим словам), и матч несуществующих (методология/согласование/отпуск).
4. **Статус и дата из Jira:** поле `status.name`, резолюция `resolution.name`, дата завершения `resolutiondate[:10]` (иначе `statuscategorychangedate`). Завершена = статус `Выполнена/Выполнено/Готово/Закрыто` + есть резолюция.
5. **Выгрузка в GS** (см. `read-mpp` → `google_api.py`): создаём новую таблицу, заливаем `Лист1!A1:...`.
6. **Раздать права** writer на `tkachenkoav@tutu.ru` и `i.alex.tkachenko@gmail.com` (не `anyone`).
7. **Раскраска строк** по канону Саши (см. «Логика раскраски»): статическая заливка фона A–K через `spreadsheets().batchUpdate` + `updateCells` (GridRange). Делать **после** заливки значений. Раскраска = срок MPP vs факт закрытия в Jira, не цвет по статусу.

## Обязательный столбец «Комментарий» (предпочтение Саши)

Саша явно просит: **в отдельном столбце «Комментарий» писать мои сомнения и замечания по каждой строке**. НЕ молчать о неуверенных матчах. Пометки, которые реально встречались:

- «ок — точное совпадение по названию» (уверенный матч).
- Дубли: «в MPP два пункта, в Jira одна задача MLE-...» (например, «Создание и интеграция» + отдельно «Интеграция» = та же задача).
- Мисматч: «MLE-… это не X, а Y; возможно нужна другая/родительская задача» (напр. MLE-40 «ознакомление и план переезда» ≠ «переезд»).
- Не-задачи: «Отпуск — не задача Jira, а ресурс/дата»; «Веха, не задача».
- Открытые: «в Jira «Анализ задачи»/«Назначена» — не завершена, хотя пункт в плане активный».

Столбцы итоговой таблицы: `№ | Название задачи (MPP) | % MPP | Длительность | Начало | Окончание | Задача Jira | Ссылка Jira | Статус в Jira | Дата завершения | Комментарий`.

Любой матч по ненадёжному признаку (низкое пересечение слов, дубли, «ближайшее по смыслу, но не точное») — помечать в комментарии, не притворяться точным.

## Логика раскраски (color-coding) — канон Саши

Раскраска — **сравнение срока в MPP с фактом закрытия в Jira**, а НЕ цвет по статусу. «Анализ задачи» / «Назначена» / «Разработка» сами по себе цвет не задают. Важны: **Окончание (MPP)** vs **сегодня** vs **есть ли дата завершения в Jira** (или статус из набора закрытых).

Колонки итоговой таблицы (A–K, 11 шт.): `№ | Название задачи (MPP) | % MPP | Длительность | Начало | Окончание | Задача Jira | Ссылка Jira | Статус в Jira | Дата завершения | Комментарий`.
- **B** — название (серый: веха/отпуск)
- **F** — Окончание MPP (срок)
- **I** — Статус в Jira
- **J** — Дата завершения

| Цвет | HEX | Условие |
|---|---|---|
| 🟢 зелёный | `#D9EAD3` | Задача в Jira **закрыта**: в «Дата завершения» (J) есть дата **либо** статус из набора закрытых (`Выполнена` / `Выполнено` / `Готово` / `Закрыто`) |
| 🔴 розовый | `#F4CCCC` | Срок в MPP (Окончание, F) **меньше сегодня** И задача в Jira **НЕ закрыта** (включая **отсутствие матча**) |
| ⚪ серый | `#CCCCCC` | Веха (напр. «Точка начала отсчёта») и отпуска (напр. «Отпуск Лёши/Кристины») — **не учитываем** в сверке, красим серым |
| (без заливки) белый | — | Срок в MPP ещё не наступил (Окончание ≥ сегодня) |

**Приоритет** (первый матч побеждает): **серый (веха/отпуск) → зелёный (закрыта) → розовый (просрочена и не закрыта) → белый (срок не наступил)**.

Следствия:
- Просрочена, но в Jira закрыта → **зелёный** (зелёный выше розового).
- Веха/отпуск, даже с датой/статусом → **серый**.
- Нет матча в Jira и F < сегодня → **розовый** (отсутствие матча = не закрыта).
- Нет матча и F ≥ сегодня → **белый**.
- Для статической заливки «сегодня» = дата прогона (не формула `TODAY()`).

## Техника раскраски в GS

Статическая раскраска — через Sheets API **`spreadsheets().batchUpdate`** с **`updateCells`**. Не через `values().batchUpdate` (такого метода нет). `updateCells.range` — GridRange-объект, не A1-строка. Питфоллы — в «Питфоллы».

Проверенный формат запроса:

```python
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
svc = build("sheets", "v4", credentials=creds)
meta = svc.spreadsheets().get(spreadsheetId=SID).execute()
sheet_id = meta['sheets'][0]['properties']['sheetId']
requests=[]
for row_inx in range(1, N):  # data rows (строка 0 — заголовок)
    grange={"sheetId":sheet_id,"startRowIndex":row_inx,"endRowIndex":row_inx+1,
            "startColumnIndex":0,"endColumnIndex":11}  # A–K
    rgb={"red":217/255,"green":234/255,"blue":211/255}  # GREEN #D9EAD3 и т.д.
    rows=[{"values":[{"userEnteredFormat":{"backgroundColor":rgb}} for _ in range(11)]}]
    requests.append({"updateCells":{"range":grange,"fields":"userEnteredFormat.backgroundColor","rows":rows}})
resp=svc.spreadsheets().batchUpdate(spreadsheetId=SID, body={"requests":requests}).execute()
```

Точные RGB (задавать дробями `c/255`, не целыми):
- `#D9EAD3` (зелёный): `{"red":217/255,"green":234/255,"blue":211/255}`
- `#F4CCCC` (розовый): `{"red":244/255,"green":204/255,"blue":204/255}`
- `#CCCCCC` (серый): `{"red":204/255,"green":204/255,"blue":204/255}`
- белый: не слать `updateCells` на эту строку (оставить без заливки).

Клиент: `googleapiclient` из venv `~/hermes-agent/.venv`. OAuth: `~/.hermes/google_token.json` (скилл `google-workspace`). `sheetId` брать из `spreadsheets().get()`, не хардкодить 0.

Эквивалент короче: `repeatCell` с тем же `backgroundColor` на GridRange строки (паттерн скилла `google-sheets-tables`). Канон этой сверки — **`updateCells`**, он проверен на живой таблице.

Верификация раскраски: ответ `batchUpdate` содержит `replies` по числу перекрашенных строк. Спот-чек: закрытая (J заполнена) → зелёный; F < сегодня и J пусто (в т.ч. без матча) → розовый; «Отпуск…» / «Точка начала отсчёта» → серый; F ≥ сегодня → без заливки. Чтение фона: `spreadsheets().get(..., includeGridData=true)` → `effectiveFormat.backgroundColor`; пустые без заливки — через `rd.get('values', [{}])`.

## Переиспользование инструментов

Не писать парсер MPP, клиент Jira и OAuth Sheets заново. Следующая сверичность (другой `.mpp` / другой план Jira) идёт по тем же шагам, меняются только входы.

| Инструмент | Откуда | Как переиспользуется |
|---|---|---|
| `read-mpp` (`read_mpp.py`, `push_to_gs.py`) | скилл `read-mpp`; скрипты `~/USERTOOLS/MppReader/read_mpp.py`, `push_to_gs.py` | парсинг `.mpp` (часто приходит как `.zip`) → CSV без `--summary`. `push_to_gs.py` — готовый путь «MPP → новый GS + права», если нужна выгрузка в стиле MS Project; для сверки канон — своя таблица A–K через `google_api.py` |
| Jira search API `GET /rest/api/2/search?jql=project=<KEY> ORDER BY key` | скилл `tutu-confluence-jira`; токен `JIRA_TOKEN` из `~/.hermes/profiles/default/.env`, base `https://hq.tutu.ru` | выгрузка всех задач проекта (пагинация по 100): `summary,status,resolutiondate,resolution,issuetype,parent`. Jpo/Advanced Roadmaps REST не использовать |
| `google_api.py` sheets create/update/get | скилл `google-workspace`; `~/.hermes/skills/productivity/google-workspace/scripts/google_api.py`; OAuth `~/.hermes/google_token.json` | создание таблицы, заливка значений `Лист1!A1:K{1+N}`, чтение, права writer на `tkachenkoav@tutu.ru` и `i.alex.tkachenko@gmail.com` (не `anyone`) |
| Sheets API `batchUpdate` / условное форматирование | sdk `googleapiclient` (venv `~/hermes-agent/.venv`) | раскраска фона (`updateCells` / опц. `repeatCell`). Паттерн batchUpdate уже есть в `google-sheets-tables` — не плодить второй HTTP-клиент |

### Повторный прогон (без переоткрывания логики)

**Входы:** путь к `.mpp` (или `.zip` OLE2 → `cp` в `.mpp`); ключ проекта Jira (если не задан — вывести из матчей по названиям, как `MLE`).
**Выход:** URL новой Google-таблицы (каждая сверка — новый документ) + раскраска + столбец «Комментарий».

Шаги: (1) `read_mpp.py <file>.mpp --format csv` → leaf `outline_level==2`; (2) Jira search по проекту; (3) матч пересечением слов (порог ≥2), сомнения — в «Комментарий»; (4) статус/дата Jira; (5) `google_api.py` create + values update A–K; (6) права writer; (7) раскраска `batchUpdate`/`updateCells` по канону выше. Пороги матча, набор закрытых статусов, HEX/RGB и приоритет цветов **не менять**, пока Саша явно не переопределит канон.

### Условное форматирование — задел (Саша отказался, не делать в этом прогоне)

Вместо разовой заливки по дате прогона можно повесить правила условного форматирования с `TODAY()`, тогда цвет сам едет при дрейфе дат:
- зелёный: `$J2<>""`
- розовый: `AND($F2<>"",$F2<TODAY(),$J2="")`
- серый: по названию (веха/отпуск, напр. `REGEXMATCH($B2,"Отпуск|Точка начала")`)
- белый — умолчание

Ставить через `spreadsheets().batchUpdate` → `addConditionalFormatRule` (не через `values()`).

Оговорка: CF по `$J2<>""` уже зелёного статуса без даты в J не покрасит; статика закрывает это набором статусов. Если CF когда-нибудь включать — либо дописывать дату в J для закрытых без `resolutiondate`, либо добавить условие по столбцу I. Пока канон — **статическая** заливка.

## Питфоллы

- **Таб создаётся как «Лист1», а не «Sheet1».** `google_api.py sheets create` создаёт лист с именем `Лист1`. `update ... Sheet1!A1:K32` → HTTP 400 `Unable to parse range: Sheet1!...`. Узнать имя листа: `spreadsheets().get()` → `sheets[].properties.title`; писать в `Лист1!...`.
- **`setup.py` не принимает флаги `--services ...` и `--format json`** (вопреки документации bundled `google-workspace`). Вызывать `setup.py --auth-url` и `setup.py --auth-code "<код>"` без них.
- **Google-токен протухает/отзывается** (`invalid_grant`). Проверить `setup.py --check` заранее; при отзыве — `setup.py --auth-url`, дать ссылку Саше, получить код с `http://localhost:1/?...&code=...`, обменять `--auth-code`. Scopes достаточно drive+sheets (в коде от Google в scope только `drive` и `spreadsheets` — ок для Sheets).
- **Jpo API закрыт** — не тратить время на перебор эндпоинтов, сразу идти в `rest/api/2/search` по проекту.
- **Поштучный CQL по названию даёт шум** (like-поиск подхватывает старые/нерелевантные задачи). Надёжнее выгрузить весь проект и матчить локально.
- **`--summary` в read_mpp** оставляет только 20 задач — для полного плана запускать без него.
- **`values().batchUpdate` не существует.** Правильный метод раскраски: `spreadsheets().batchUpdate` с телом `{"requests":[...]}`. Иначе HttpError 400 «Invalid JSON payload received. Unknown name requests».
- **`updateCells.range` в batchUpdate — это GridRange**, объект `{sheetId, startRowIndex, endRowIndex, startColumnIndex, endColumnIndex}`, **не** A1-строка `"Лист1!A2:K2"`. A1 → HttpError 400 «Invalid value at requests[0].update_cells.range». Для раскраски нужен `sheetId` из `spreadsheets().get()`, не A1-имя листа.
- **Excel-округление цвета:** `217/255*255` может дать `#D9EAD2` вместо `#D9EAD3` из-за float. Задавать RGB напрямую дробями `217/255`, не целыми.
- **Пустая ячейка при чтении фона** может не иметь ключа `values`. Проверка: `rd.get('values', [{}])` и fallback, не `rd['values'][0]`.

## Верификация

- `updatedCells` и `updatedRange` в ответе `sheets update` — должно совпасть с ожидаемым числом ячеек (заголовок + N строк × 11 колонок).
- Повторное `values().get(range="Лист1!A1:K{1+N}")` — вернуть 1+N строк.
- Права: `permissions().create(fileId, {type:user, role:writer, emailAddress})` на оба адреса.

## Файлы

- `references/jpo-advanced-roadmaps-api.md` — разведка эндпоинтов плагина Jpo и обоснование обхода через search API.
- Рабочие скиллы: `read-mpp`, `tutu-confluence-jira`, `google-workspace`.