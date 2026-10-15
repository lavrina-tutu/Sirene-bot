---
tool: MoveFromJira
version: "0.1.1"
date: 2026-08-29
status: active
---

# MoveFromJira v0.1.1 — TZ

## Контракты экосистемы

### Источник истины
- Первичные данные по задачам и проектам: `api_jira` (Jira REST API v2, `https://hq.tutu.ru`)
- Локальный снимок проекта: MoveFromJira (`WorkVault/Projects/<slug>/jira_snapshot.json`, маппинг `WorkVault/Hermes-Backlog/jira_project_mapping.json`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| lead.displayName | str | optional | api_jira | ФИО лида проекта из `/rest/api/2/project/{key}` |
| project_statuses | str | required | api_jira | названия статусов проекта в Jira |
| open_issues_count | int | required | api_jira | число открытых задач по JQL `project = X AND statusCategory != Done` |
| recent_issues | str | optional | api_jira | список последних 5 изменённых задач (id, key, title, status, assignee, updated, url) |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| slug | str | WorkVault (карточка проекта) | идентификатор проекта |
| jira_key | str | WorkVault (карточка проекта) | ключ проекта в Jira |
| fetched_at | datetime(iso8601) | WorkVault (карточка проекта) | дата и время снимка (ISO-8601 UTC) |
| project | str | WorkVault (карточка проекта) | объект проекта (key, name, url, lead, description) |
| project_statuses | str | WorkVault (карточка проекта) | список названий статусов проекта |
| open_issues_count | int | WorkVault (карточка проекта) | количество открытых задач |
| recent_issues | str | WorkVault (карточка проекта) | JSON-массив из 5 последних задач (id, key, title, status, assignee, updated, url) |

### Зависимости
- Получает от: [api_jira]
- Отдаёт: [WorkVault (карточка проекта)]

### Breaking changes policy
- Формат снимка `jira_snapshot.json`: структура JSON на диске (`WorkVault/Projects/<slug>/jira_snapshot.json`).
- При изменениях структуры снимка или схемы Jira REST API v2: обновление `jira_client.py` и `mapper.py`.

### Границы («что НЕ трогать»)
- Не загружать полное дерево задач, комментарии, вложения, спринт-борды или worklog (только минимальный снимок v0.1).
- Не изменять данные в Jira (только чтение REST API `hq.tutu.ru`).
- Не модифицировать файлы в `Projects/<slug>/` кроме `jira_snapshot.json`.

## Цель
Тонкий коннектор: тянет из Jira ТУТУ (https://hq.tutu.ru, REST API v2, Basic Auth)
минимально-достаточные данные для обогащения карточек проектов в WorkVault.

## Что тянем
1. **project_statuses** — список статусов проекта (для enum карточки `status`).
2. **open_issues_count** — JQL: `project = X AND statusCategory != Done`.
3. **recent_issues** — последние 5 изменённых задач (id, key, title, status, assignee, updated, url).
4. **project_lead** — `lead.displayName` из `/rest/api/2/project/{key}`.

## Что НЕ тянем (v0.1)
- Полное дерево задач, комментарии, вложения, sprint board, worklog.

## Выход
`~/WorkVault/Projects/<slug>/jira_snapshot.json` — перезаписывается при каждом запуске.

```json
{
  "slug": "adm",
  "jira_key": "OKRS",
  "fetched_at": "2026-06-06T...Z",
  "project": {"key": "...", "name": "...", "url": "...", "lead": "...", "description": "..."},
  "project_statuses": ["Черновик", "В плане", "В работе", "На паузе", "Выполнено", "Отменено"],
  "open_issues_count": 17,
  "recent_issues": [ {"id": "...", "key": "OKRS-7", "title": "...", "status": "В работе", "assignee": "...", "updated": "...", "url": "..."} ]
}
```

## Маппинг slug → jira_key
- Извлекается из `projects_raw.json` (ищем `hq.tutu.ru/browse/XXX` в ссылках/raw).
- Fallback: имя проекта → известный ключ (Антибот→ANTIBOTHTL, Инструмент OKR→OKRTOOL).
- Сохраняется в `~/WorkVault/Hermes-Backlog/jira_project_mapping.json`.

## CLI
```
movefromjira --mode manual          # все проекты с jira_key
movefromjira --mode cron            # тихий режим
movefromjira --project adm          # один проект
movefromjira --dry-run              # не пишет файлы
```

## Конфиг (~/.config/hermes/.env)
- `JIRA_BASE_URL=https://hq.tutu.ru`
- `JIRA_USER=tkachenkoav`
- `TUTU_DOMAIN_PASSWORD=...`
- `PROJECTS_DIR=~/WorkVault/Projects`
- `BACKLOG_DIR=~/WorkVault/Hermes-Backlog`

## Структура
```
MoveFromJira/
├── movefromjira/{__init__,__main__,config,jira_client,mapper,sync}.py
├── tests/{test_mapper,test_sync}.py
├── pyproject.toml
└── TZ.md
```
