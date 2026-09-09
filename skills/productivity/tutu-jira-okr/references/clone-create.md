# Клонирование KR / создание Objective

Частый сценарий: скопировать набор KR с Q1 на Q2 для той же годовой цели.

## Порядок

1. **Утвердить постановку** — что меняется (summary/description, fixVersion), что копируется (assignee, reporter, приоритет, метрика), что обнуляется (все чекин-поля — **пусто**, не 0). Без явного «делай» — не создавать.
2. `GET /issue/{OLD-KR}?fields=summary,description,assignee,reporter,priority,fixVersions,customfield_43701,customfield_43743,customfield_43739,customfield_43711`
3. `POST /issue` — минимум: `project`, `issuetype: UserStory`, `summary`, `description`, `assignee`, `reporter`. `fixVersions`, `Тип OKR`, `Подразделение` на create часто `400` — нормально.
4. `POST /issue/{KEY}/transitions` (обычно id=101 Planning) — открывает поля edit-экрана.
5. `PUT /issue/{KEY}` — `fixVersions`, `customfield_43739`, `customfield_43711` (**числом**: `100`, не `"100"`).
6. `POST /issueLink` — `type.name="Contains"`, `inwardIssue`=Objective, `outwardIssue`=новая KR.
7. Финальный GET + построчная сверка с образцом.

## OKRS vs OKRAID

| | OKRS | OKRAID |
|---|---|---|
| Link | Contains (11400) | Link (10003) |
| Objective | стандарт | + `customfield_10007` Epic Name |
| Тип OKR у KR | обычно пусто | всегда пусто |

В незнакомом проекте — `createmeta`, не копировать по аналогии с OKRS.

## Префикс summary/description

`KR{n}.O{цель}.` или `KR{n}.O{цель}.Q{квартал}.` — проверить на финальной сверке в **обоих** полях, не предполагать по тексту пользователя.

Несколько KR под одну цель — у каждого свой префикс.

## Питфоллы

- **`PUT`/`POST` сразу после create → `400`** — сменить статус transition, повторить PUT.
- **Числовые customfield как строка** → `400 "должно быть числом"`.
- **«Пусто» ≠ 0** — не включать поле в payload (не `null`, не `""`, не `0`).
- **Transition только для открытия полей** — не «закрывать» задачу без команды.
- **OKRAID KR** — те же issuetype; `Тип OKR` не заполнять, если в образце пуст.

## Пометка на удаление

⚠️ Переименование summary в «Удалить» может привести к **реальному** удалению (асинхронно, 404 позже). См. `marking-for-deletion-incident.md`.

- Предупредить о риске, получить подтверждение.
- Выгрузить поля в WorkVault до переименования, если важно.
- Формат текста — уточнить у пользователя (в прецеденте строго «Удалить»).
- Менять только запрошенное поле; область (только задача / + дочерние) — уточнить.
- GET после PUT подтверждает переименование в моменте, не гарантию сохранности.
