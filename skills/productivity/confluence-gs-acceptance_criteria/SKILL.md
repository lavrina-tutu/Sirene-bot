---
name: confluence-gs-acceptance_criteria
description: "Use when переносим критерии/шкалы приёмочного пилота (PoC) и"
version: 1.0.1
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Confluence, GoogleSheets, AcceptanceCriteria, PoC, Оценки, Трисигма]
    related_skills: [tutu-confluence-jira, google-workspace]
---

# Confluence → Google Sheets: критерии успешности пилота (Acceptance Criteria)

Прецедент: страница Trisigma «Критерии успешности пилотного внедрения АВ-платформы» (pageId=499548597) → таблица собирает баллы по критериям от респондентов (Гладких, Белов, Лысенко, Малый, Ткаченко).

Цель: перенести критерии из Confluence так, чтобы **в строках остались критерии** (описания — примечаниями к строке), **в столбцах — ФИО респондентов** под баллы, а по каждому блоку считался **средний балл**.

## Готовый результат (эталон формата)

```
R1: Оценка успешности пилотного внедрения AB-платформы (Trisigma)
R2: Критерий | <Респондент 1> | <Респондент 2> | ... | Комментарий
R3: 1. Технические критерии | =AVERAGE(B4:B8) | ...             (ср. балл блока)
R4: 1.1. <критерий>          |  5                | ...
...
R9: 2. Продуктовые критерии  | =AVERAGE(B10:B12) | ...
```

- 7 колонок: A=критерий, B..F=респонденты, G=Комментарий.
- Строки-заголовки блоков (3,9,13,18) — жирные, с заливкой.
- Примечание (note) на ячейке критерия (колонка A) — полное описание «что оценивается» + шкала 1–5.
- Oценки вставлять **числами** (int), не строками — иначе AVERAGE даёт `#DIV/0!`.

## Шаги

### 1. Читаем Confluence (страницу критериев)
```bash
load_confluence_env() {
  while IFS='=' read -r _k _v; do
    case "$_k" in
      CONFLUENCE_TOKEN|WORKVAULT_PATH) [ -n "$_v" ] && export "$_k=$_v" ;;
    esac
  done < "$HOME/USERTOOLS/ConfluenceSync/.env"
}
load_confluence_env
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/content/<PAGE_ID>?expand=body.storage" > /tmp/conf.json
```
Извлекаем:
- **Разделы** — по `<h2>`, из них же userkey ответственных (`ri:userkey=...` в заголовке раздела).
- **Критерии** — по `<h3>`, описание — текст `<p>` + `ul` до следующего `<h3>`. Удалять таблицы шкал (`<table>`) — они не нужны в основной таблице邈.
- **Страницы с оценками респондентов** — те же критерии, но с `Оценка: N` и блоком `Проблемы:` (это → комментарий в колонку G).

### 2. Резолв userkey → ФИО
```bash
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "https://dom.tutu.ru/rest/api/user?key=<USERKEY>"
# → displayName (напр. "Гладких Юрий")
```

### 3. Инициализация Google Sheets (через REST API, не gws CLI)
Токен: `~/.hermes/google_token.json` → `token`/`access_token`.
Определить имя листа: `GET /v4/spreadsheets/{SHEET_ID}` → `sheets[].properties.title` (таблица была «Лист1», не «Sheet1» — `Sheet1!A1` кинет `400`).

Записать структуру таблицы через `PUT /v4/spreadsheets/{SID}/values/{лист}!A1:G{last}`, `valueInputOption=RAW`.

### 4. Оформление (batchUpdate)
- `repeatCell` для жирных заголовков/блоков (`userEnteredFormat.textFormat.bold` + `backgroundColor`).
- `updateCells` с `fields:"note"` — примечания-описания на ячейки критериев (колонка A).
- `updateDimensionProperties` — ширины колонок (A=360, B..F=110, G=200).

### 5. Запись оценок (числами!)
Для респондента с уже готовой страницей оценок:
```bash
PUT /v4/spreadsheets/{SID}/values/Лист1!B4:B8?valueInputOption=USER_ENTERED
body: {"range":"Лист1!B4:B8","values":[[5],[4],[2],[5],[2]]}
```
**ВАЖНО**: передавать целые числа (JSON int), а НЕ строки `"5"`. `valueInputOption=USER_ENTERED` строку `"5"` сохранит как текст, и AVERAGE даст `#DIV/0!`.

### 6. Средний по блоку (формула)
```bash
PUT /v4/spreadsheets/{SID}/values/Лист1!B3?valueInputOption=USER_ENTERED
body: {"range":"Лист1!B3","values":[["=AVERAGE(B4:B8)"]]}
```
Формула → считается автоматически, пересчитывается при правке оценок.

## Питфоллы
- **Оценки текстом → `#DIV/0!`**. Если записать `5` как строку, формула средней не видит числа (считает 0). Диагностика: `GET ?ranges=...&fields=sheets.data.rowData.values(userEnteredValue,effectiveValue,formattedValue)` — смотреть `userEnteredValue` (`stringValue`=текст, `numberValue`=число). Фикс: перезаписать числами.
- **Имя листа кириллицей** («Лист1»), не «Sheet1» — для A1-нотации URL-кодировать (`%D0%9B%D0%B8%D1%81%D1%821`), иначе 400.
- **Резолв ответственных** — userkey из заголовка `<h2>` раздела через `ri:userkey`, не через username.
- **Описания** — примечанием (note), не текстом в ячейке, чтобы таблица оставалась компактной.
- Google-токен протухает (`invalid_grant`) — переподключение через `google-workspace` skill (setup.py --auth-url).

## Авторизация Google
Если `~/.hermes/google_token.json` протух (`invalid_grant`), переподключить через скилл `google-workspace`:
```bash
python ~/.hermes/skills/productivity/google-workspace/scripts/setup.py --auth-url
# → дать ссылку пользователю → он возвращает URL после localhost:1?code=...
python .../setup.py --auth-code "<url>"
```
ВАЖНО: pending-состояние перезаписывается при каждом `--auth-url`. **Не генерировать ссылку повторно**, пока пользователь прошёл старую — иначе «Invalid code verifier». Скормить state/verifier из `~/.hermes/google_oauth_pending.json`, использовать последнюю выданную ссылку.

## Связанные скиллы
- `tutu-confluence-jira` — чтение Confluence, резолв userkey.
- `google-workspace` — авторизация Google, sheets CLI.