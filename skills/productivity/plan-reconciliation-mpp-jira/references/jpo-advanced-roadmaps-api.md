# Advanced Roadmaps (Jpo plugin) — REST API reconnaissance

Проверено 14.08.2026 на hq.tutu.ru (Jira Data Center, plugin Advanced Roadmaps / Portfolio / "Jpo").
Auth: Bearer PAT из `~/.hermes/profiles/default/.env` (`JIRA_TOKEN`, base `https://hq.tutu.ru`).

## Факт

**Нет публичного REST API для чтения структуры/состава отдельного плана Advanced Roadmaps.**
Community/Atlassian Dev подтверждают: `GET /rest/jpo/1.0/info/query` существует, но требует внутренний
заголовок `ap-client-key` и для приложений отдаёт 403/500. Единственный доступный извне эндпоинт
(read-only для Apps) отсутствует; реквест на его добавление: JRACLOUD-89504.

## Проба эндпоинтов (реальные коды)

| Метод | Путь | Результат |
|---|---|---|
| GET | `/rest/jpo/1.0/info/query` | 404 |
| GET | `/rest/jpo/1.0/plans` | 500 `unexpected-error` (jersey TerminatingRule) |
| POST | `/rest/jpo/1.0/plans` | 500 `element must not be null` |
| GET | `/rest/jpo/1.0/config` | 404 |
| GET | `/rest/jpo/1.0/plan/88` | 404 |
| GET | `/rest/jpo/1.0/plan/88/issues` | 404 |
| GET | `/rest/jpo/1.0/plan/88/detail` | 404 |
| GET | `/rest/jpo/1.0/export` | 404 |
| POST | `/rest/jpo/1.0/export` | 404 |

Примечание: `GET/POST /rest/jpo/1.0/export` и `/import` документированы только для **экспорта/импорта
всей инсталляции** (JIRA_SHARED_HOME/export/advanced-roadmaps), не для чтения одного плана.

## Рабочий обход

План Advanced Roadmaps берёт источник из проекта/борда/фильтра; его задачи — это **обычные живые
задачи Jira**. Значит состав и статусы плана достаются штатным search API:

```
GET /rest/api/2/search?jql=project=<KEY> ORDER BY key&maxResults=100&startAt=<N>
    &fields=summary,status,resolutiondate,resolution,issuetype,parent
```

Пагинация по 100 до `total`. Проект определяется по задачам, найденным по названиям пунктов MPP
(в кейсе ML-платформы — проект `MLE`, ~490 задач; задачи плана = подмножество задач проекта).

## Завершённость задачи Jira

Завершена = `status.name` в {Выполнена, Выполнено, Готово, Закрыто} И есть `resolution.name`.
Дата завершения — `resolutiondate[:10]`; fallback `statuscategorychangedate[:10]` (но это дата
перехода в категорию, может отличаться).