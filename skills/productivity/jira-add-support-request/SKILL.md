---
name: jira-add-support-request
description: "Use when создать обращение в техподдержку ADD (Jira)."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, JIRA, ServiceDesk, ADD, техподдержка, вложения]
    related_skills: [tutu-confluence-jira, tutu-jira-contract-approval]
---

# Обращение в техподдержку ADD (Jira Service Desk)

Триггер: «создать обращение в техподдержку», «обращение в ADD», «техподдержка ADD» + тема/описание, опционально файлы-вложения.

Создаёт запрос через `POST /rest/servicedeskapi/request` (НЕ `/rest/api/2/issue`).

## Авторизация

Токен JIRA — `~/.hermes/profiles/default/.env`, переменная `JIRA_TOKEN`, base `https://hq.tutu.ru`.

```bash
source ~/.hermes/profiles/default/.env  # fallback: anthropic/.env
```

## Тип запроса (requestType)

Для «Помощь с техникой, корпоративными сервисами и офисной инфраструктурой» — **requestTypeId `82`** (serviceDeskId `8`):
- `summary` (обязательно) — «С чем у Вас проблема?»
- `description` (обязательно) — «Что случилось?»
- `attachment` — вложения (опционально)
- `customfield_14904` — имя компьютера/стол (опционально)

Если тема иная — сначала перечислить типы и выбрать по теме:
```bash
curl -s -H "Authorization: Bearer $JIRA_TOKEN" \
  "https://hq.tutu.ru/rest/servicedeskapi/servicedesk/8/requesttype?limit=100"
# Поля конкретного типа:
curl -s -H "Authorization: Bearer $JIRA_TOKEN" \
  "https://hq.tutu.ru/rest/servicedeskapi/servicedesk/8/requesttype/<rtId>/field"
```
Поля обязательные помечены `required:true`; option-поля брать `validValues[].value`.

## Создание запроса

```bash
source ~/.hermes/profiles/default/.env
curl -s -X POST -H "Authorization: Bearer $JIRA_TOKEN" -H "Content-Type: application/json" \
  "https://hq.tutu.ru/rest/servicedeskapi/request" -d '{
    "serviceDeskId": "8",
    "requestTypeId": "82",
    "requestFieldValues": {
      "summary": "<Тема>",
      "description": "<Описание>"
    }
  }'
```

Ответ — `issueKey` (напр. `ADD-645053`), `issueId`, ссылка веб: `https://hq.tutu.ru/servicedesk/customer/portal/8/<KEY>`.

## Прикрепление вложений — ТОЛЬКО через curl

**Питфолл (важно):** Python-`requests` на attachments даёт **401** даже с валидным `JIRA_TOKEN` (тот же токен работает на создание/чтение). Вложения прикреплять **только через curl** — он работает (HTTP 200).

```bash
source ~/.hermes/profiles/default/.env
B="https://hq.tutu.ru/rest/api/2/issue/<KEY>/attachments"
H1="Authorization: Bearer $JIRA_TOKEN"; H2="X-Atlassian-Token: no-check"
curl -s -X POST -H "$H1" -H "$H2" \
  -F "file=@/path/to/file.msg" "$B" -o /dev/null -w "HTTP %{http_code}\n"
```
- Header `X-Atlassian-Token: no-check` обязателен (иначе 403 XSRF).
- Путь к файлу с пробелами в имени — просто в `-F "file=@..."`, кавычки уже в команде.

## Проверка (обязательно после создания)

```bash
curl -s -H "Authorization: Bearer $JIRA_TOKEN" \
  "https://hq.tutu.ru/rest/api/2/issue/<KEY>?fields=attachment" | python3 -c "import sys,json;d=json.load(sys.stdin);[print(a['filename'],'|',a['size'],'B') for a in d['fields']['attachment']]"
```
Каждый вложенный файл появляется отдельной записью. Все требуемые вложения на месте → задача выполнена.

## Отчёт Саше

- Номер задачи кликабельной ссылкой: `[KEY](https://hq.tutu.ru/browse/KEY)`
- Статус, тип запроса, список вложений (имя + размер)
- Веб-ссылка портала сервисдеска

## Питфоллы

- **НЕ создавать через `/rest/api/2/issue`** — это обычная задача, не запрос сервисдеска. Использовать `/rest/servicedeskapi/request`.
- **НЕ тестировать несколько форматов option-поля живым POST** — каждый успешный POST создаёт реальный запрос (прав на удаление через API нет). Определять формат по схеме заранее.
- **Python-requests на attachments → 401** — использовать curl (см. выше).
- `description` может получить шаблонные заголовки типа (Контекст, Польза...) — переданный текст ложится в конец под «Дополнительное описание».
