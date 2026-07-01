---
name: tutu-jira-contract-approval
description: "Use when надо создать задачу в JIRA ТУТУ на согласование договора/ДС/Приложения через АДД (Service Desk id=8, requestType=232) → TOMAKE. Покрывает КБК, участников, вложения, поля Service Desk."
version: 1.1.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [TUTU, JIRA, ServiceDesk, договор, TOMAKE, ADD, согласование]
    related_skills: [tutu-confluence-jira, pm-briefing]
---

# Согласование договоров ТУТУ через JIRA (АДД → TOMAKE)

Используй этот скилл когда надо создать задачу на согласование договора/ДС/Приложения в ТУТУ.

## Ключевые факты

- **Jira base:** `https://hq.tutu.ru`
- **Токен:** `JIRA_TOKEN` в `~/.hermes/profiles/anthropic/.env`
- **Service Desk ADD:** id=`8`, project=`ADD`
- **Новый договор** → requestTypeId=`232` «Помощь аккаунт-менеджеров»
- **ДС/Приложение/Заявка к существующему** → напрямую в TOMAKE (проект id=10700)

## Путь для нового договора

```
АДД (requestType 232) → автоматически создаётся задача MIX в TOMAKE
```

## Поля requestType 232 (ключевые)

| fieldId | Назначение | Формат |
|---|---|---|
| `summary` | Название | string |
| `customfield_41277` | С чем нужна помощь | `{"id": "48985"}` = Договор (расходный), `{"id": "50046"}` = Договор (доходный) |
| `customfield_42092` | ЗК проводилась? | `{"id": "50034"}` = Да, `{"id": "50035"}` = Нет |
| `customfield_42094` | Решение ЗК (ссылка) | string |
| `customfield_41344` | С регламентом ознакомлен | `[{"id": "49058"}]` (массив!) |
| `priority` | Приоритет | `{"id": "3"}` = Высокий, `{"id": "6"}` = Обычный |
| `description` | Описание | string |
| `customfield_41333` | Краткое описание сотрудничества | string |
| `customfield_41335` | Предмет договора | string |
| `customfield_41336` | Коммерческие условия | string |
| `customfield_13100` | Сумма договора | number (не строка!) |
| `customfield_12611` | Валюта | `{"id": "11630"}` = RUB |
| `customfield_42859` | Сумма без НДС | number |
| `customfield_32551` | КБК (кодировка) | string, напр. `"012 115 13"` |
| `customfield_42100` | Подтверждает оплату | `{"name": "login"}` |
| `customfield_42089` | Держатель бюджета | `{"name": "login"}` |
| `customfield_42099` | Бизнес-заказчик | `{"name": "login"}` |
| `customfield_41337` | Механика | string |
| `customfield_41338` | Способ взаимодействия | string |
| `customfield_41339` | Контакты партнёра | string |
| `customfield_42102` | ЭДО | `{"id": "50041"}` Диадок, `{"id": "50040"}` СБИС, `{"id": "50042"}` Другой, `{"id": "51439"}` Бумага |
| `customfield_41340` | Срок договора | string |
| `customfield_42763` | Ожидаемые сроки подписания | date `"YYYY-MM-DD"` |
| `customfield_42015` | Коммерческое название контрагента | string |
| `customfield_12608` | ЮЛ с нашей стороны | `{"id": "11602"}` = ГМ, `{"id": "11603"}` = МБГ, `{"id": "11604"}` = НТТ, `{"id": "20555"}` = ДДС |

## Создание задачи

```python
import requests, json
from pathlib import Path

env = {}
for line in Path('/home/tkachenkoav/.hermes/profiles/anthropic/.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

s = requests.Session()
s.headers['Authorization'] = f'Bearer {env["JIRA_TOKEN"]}'
s.headers['Content-Type'] = 'application/json'
BASE = env['JIRA_BASE_URL']  # https://hq.tutu.ru

payload = {
    'serviceDeskId': '8',
    'requestTypeId': '232',
    'requestFieldValues': {
        'summary': 'Название задачи',
        'customfield_41277': {'id': '48985'},  # Договор расходный
        # ... остальные поля
    }
}

r = s.post(f'{BASE}/rest/servicedeskapi/request', json=payload, timeout=30)
issue_key = r.json()['issueKey']  # напр. ADD-604561
issue_id = r.json()['issueId']
```

## Прикрепление файлов

```python
headers_attach = {
    'Authorization': f'Bearer {env["JIRA_TOKEN"]}',
    'X-Atlassian-Token': 'no-check',  # обязательно!
}
with open(file_path, 'rb') as f:
    requests.post(
        f'{BASE}/rest/api/2/issue/{issue_key}/attachments',
        headers=headers_attach,
        files={'file': (filename, f, 'application/octet-stream')},
        timeout=30
    )
```

## Добавление участников (watchers)

В ADD-задачах `watchers` API возвращает 401. Использовать **participants** через servicedeskapi:

```python
s.post(
    f'{BASE}/rest/servicedeskapi/request/{issue_id}/participant',
    json={'usernames': ['login1', 'login2', ...]},
    timeout=15
)
```

## Поиск пользователей

Для **русских имён** (кириллица) — только `/user/picker` с параметром `query`.
Для **латинских логинов** — `/user/search` с параметром `username`.

```python
# Русское имя / фамилия
r = s.get(f'{BASE}/rest/api/2/user/picker', params={'query': 'Абрамов', 'maxResults': 5})
users = r.json()['users']  # [{name, displayName, ...}]

# Латинский логин
r = s.get(f'{BASE}/rest/api/2/user/search', params={'username': 'abramov'})
```

**Важно:** `/rest/api/2/user/search?query=...` в этой Jira возвращает **400** — использовать только `username=` или переключаться на `/user/picker?query=`.

## КБК (кодировка) — структура

Короткий КБК = `ЭФС Статья Подстатья` (8 цифр через пробел, напр. `012 115 13`)

- **Блок 4 — Элемент финансовой структуры (ЭФС):** чья команда платит (DataScience=012, DataTeam=013, ...)
- **Блок 5 — Статья:** тип расхода (115=External IT services, 093=Consulting, 118=Technological projects...)
- **Блок 6 — Подстатья:** уточнение (115→13=ИИ сервисы, 115→01=Внешние инфо-сервисы...)

Справочник: `https://dom.tutu.ru/pages/viewpage.action?pageId=169153020`

## Брифование по договору — порядок вопросов

1. КБК (статья + подстатья — из справочника; элемент ЭФС — у заказчика)
2. Кто подтверждает оплату в JIRA
3. Срок договора
4. Механика работ
5. Контакты партнёра для CRM
6. ЭДО
7. Компонент JIRA
8. Уставные документы контрагента
9. Путь постановки (АДД = новый договор / TOMAKE напрямую = ДС к существующему)

## Формат описания (предпочтение Саши)

- **Без иконок/эмодзи** в теле описания
- Короче и проще — меньше букв
- За основу брать формулировку заказчика, делать точнее и чище
- Не дублировать поля, которые уже заполнены отдельными полями формы

## Живой пример (2026-07-01)

Задача **ADD-604561** «Согласовать проект договора на пилот ML-платформы Neoflex Dognauts» создана этим флоу:
1. Скачали 2 инструкции Confluence (pageId 389284624, 355431983) через `confluencesync pull --to-context --no-recursive`
2. Провели бриф по 11 вопросам (см. `tutu-confluence-jira` → раздел «Бриф»)
3. Создали задачу через `POST /rest/servicedeskapi/request` (sdId=8, rtId=232) с полным набором полей
4. Приложили 2 docx через `POST /rest/api/2/issue/ADD-604561/attachments`
5. Добавили Мария Осока / Диана Скворцова / Роман Абрамов через `/participant`

Мини-ТЗ: `WorkVault/Tasks/Неофлекс-согласование-договора.md`

## Инструкции (сохранены в WorkVault)

- `WorkVault/Confluence/UACCOUT/.../Как поставить задачу на аккаунта_ JIRA-TOMAKE/index.md`
- `WorkVault/Confluence/UACCOUT/.../MIX. Регламент _Передача договора.../index.md`

## Pitfalls

- `customfield_41344` («С регламентом ознакомлен») — **массив**, не объект: `[{"id": "49058"}]`
- `customfield_13100` и `customfield_42859` — **number**, не строка
- `customfield_42763` — дата в формате `"YYYY-MM-DD"`
- User-поля (`customfield_42100`, `customfield_42089`, `customfield_42099`) — передавать как `{"name": "login"}`, **не** строкой логина
- Watchers в ADD-задачах через `/rest/api/2/issue/{key}/watchers` дают **401** — использовать только `POST /rest/servicedeskapi/request/{issueId}/participant` с `{"usernames": [...]}`
- `GET /rest/api/2/issue/createmeta?...&expand=projects.issuetypes.fields` возвращает **404** в этой версии Jira — вместо этого использовать:
  - `GET /rest/servicedeskapi/servicedesk/{sdId}/requesttype/{rtId}/field` — список полей requestType
  - `GET /rest/api/2/issuetype` — все типы задач
- `/rest/api/2/user/search?query=...` → **400**. Только `username=<login>` (латиница) или `/user/picker?query=<Ф>` (кириллица)
- web_extract блокирует dom.tutu.ru (internal). Использовать `confluencesync pull <pageId> --to-context`
- страницы Confluence с ЗК могут быть недоступны через REST (404) при недостаточных правах — указывать ссылкой в описании
- Прикрепление файлов — **обязателен** header `X-Atlassian-Token: no-check`, иначе 403 (XSRF)
