---
name: confluence-gantt-plan
description: "Залей/обнови план из mpp на страницу Confluence gantt-plan."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [confluence, gantt, mpp, plan, gantt-chart-planner]
---

# Обновление плана Confluence (gantt-chart-planner) из .mpp

Страница плана проекта держит план в макросе **`gantt-chart-planner`**; сами данные хранятся в **JSON-вложении** макроса, а не в body.storage (storage содержит только `<ac:structured-macro>` с параметрами `id`/`hash`). Поэтому план нельзя поправить обычным GET→PUT storage — нужен CLI, который перезаливает JSON-вложение и строку «Итого».

## ⚠️ Скилл edit-plan-confluence НЕ ГРУЗИТСЯ через skill_view/skill_manage

Канон этого класса задач — `productivity/edit-plan-confluence`, но его файлы живут в `~/hermes-workspace/skills/productivity/edit-plan-confluence/` и **не зарегистрированы в активной библиотеке** — `skill_view`/`skill_manage` падают `Skill not found`. НЕ трать время на попытки загрузить/найти его в реестре: зови CLI **напрямую по пути на диске**.

## Найти страницу плана

Имя вида `<Проект>. План DD.MM.YY` (напр. `Закупка данных (Обогащение клиентских данных). План 11.11.26`, space `DPAN`). **Не спутать со страницей минуток** (`…Задачи и договоренности…`) и с брифом.

Страницу плана ищи **CQL-поиском по имени проекта** (`title~`), а не через entity card: `pfs.page_id` в `entities.json`/карточке указывает на **минутки**, не на план:
```bash
load_confluence_env
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" --get \
  --data-urlencode 'cql=type=page AND title~"<проект>"' --data-urlencode 'limit=30' \
  "https://dom.tutu.ru/rest/api/search" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);[print(r['content']['id'],'|',r['title']) for r in d['results'] if r['title']]"
```
результат может содержать `@@@hl@@@</endhl>@@@`-обёртки highlight — выбрать строку с «. План».

## Заливка плана (preview → diff → apply)

Порядок строгий и обязательный. CLI сам подбирает интерпретатор с `mpxj` (системный `/usr/bin/python3`; hermes-venv `mpxj` не имеет — не активируй его).

```bash
CLI=~/hermes-workspace/skills/productivity/edit-plan-confluence/scripts/cli.py
PY=/usr/bin/python3

# 1. preview — read-only: title / macro-id / версия вложения; убедиться что страница и макрос на месте
$PY $CLI preview --page-id <pageId>

# 2. diff — показать дифф ПЕРЕД записью, PUT не делает
$PY $CLI diff   --page-id <pageId> --mpp /tmp/plan.mpp

# 3. apply — только после явной команды Саши («лей»/«пиши»/«да»); --confirm обязателен
$PY $CLI apply  --page-id <pageId> --mpp /tmp/plan.mpp --confirm лей
```

mpp-путь: файл `.mpp` приходит из Telegram в `~/.hermes/cache/documents/native-inputs/` — скопировать во `/tmp/` с нормальным именем (`cp <original.mpp> /tmp/plan.mpp`).

## Архивная привязка: новая страница требует `save` до `apply`

`apply` на странице без plan/lineage-binding в MofsIndex падает `PlanBindingError: Нет привязки plan/lineage для pageId=…; project_slug должен быть указан явно до первого архивного commit` — но **`apply` не принимает `--project-slug`**, его принимает только `save`. Для новой страницы (нет строки в `plan_lineage`) сначала заведи привязку:
```bash
$PY $CLI save --mpp /tmp/plan.mpp --page-id <pageId> --project-slug <проект>
# snapshot_id / published:false — save только фиксирует базу, Confluence НЕ трогает
$PY $CLI apply --page-id <pageId> --mpp /tmp/plan.mpp --confirm лей
```
`project-slug` — имя сущности WorkVault (`Entities/<slug>`), не заголовок MPP (R-007 §4.2 не угадывает по нему). Повт��рный `apply` после создания binding идемпотентен по UQ — слаг передавать заново не нужно.

## «В архив только» — отдельный save (НЕ apply)

Команда «в архив» = `save` БЕЗ `--page-id` (БЕЗ `--project-slug` через apply):
```bash
$PY $CLI save --mpp /tmp/plan.mpp --project-slug <проект>
# snapshot_id / published:false — snapshot пишется в БД, Confluence НЕ трогается
```
Это НЕ публикация: не создаётся Confluence-клиент, baseline не сдвигается, страница не меняется. Подтверждать read-back из таблицы **`plan_snapshot`** (не `snapshot` — так таблица не существует) в `state/index.sqlite`: запись по `snapshot_id`, `published_at is NULL` → публикации не было. Проект MPP (`<<заголовок>>`/метаданные) разбирать через read_mpp, snapshot сам задаёт `task_count`/`dependency_count`.

## Питфоллы

- **План ≠ минутки.** Именование: план `«Проект». План DD.MM.YY`, минутки `«Проект». Задачи и договоренности (Минутки)`. `pfs.page_id` в entity-карточке всегда ведёт на минутки, не на план — не искать план через неё.
- **‎ПО УМОЛЧАНИЮ ВСЕГДА исключать сбойные зависимости** (решение Саши 16.11.2026). Плагин gantt-chart-planner **сам пересчитывает срок проекта как критический путь по связям** (игнорирует записанные в JSON start/end). Перед каждым apply сверять критический путь с корнем MPP (пересчёт longest-path по predecessors из `__tasks.csv`): если расходится — это лишняя зависимость, сериализующая параллельные ветки (типичный виновник: «1.0 Согласование архитектуры» → «1.1 Подготовка registry», связь 16→17, тянущая +13 дней); исключить её через `--drop-dep FROM:TO` и перепроверить путь = корню. Применить `--drop-dep` для каждой связи, чьё исключение возвращает путь к корню (можно несколько). Только если путь уже == корню — заливать как есть без drop. Расчёт: forward longest-path по duration leaf-задач вдоль самой длинной цепочки `dependenciesData` (type=2 FS, lag=0). Сбойная связь не всегда 16→17 в новых версиях — пересчитывать из актуальных predecessors.
- **Формат страницы сохраняется автоматически:** скилл не меняет `macro-id`/`id`/`hash` существующего макроса — обновляются только JSON-вложение (версия +1) и строка «Итого». Проверить живым GET: `gantt-макросов == 1`, `macro-id`/`id`/`hash` == прежним, «Итого» обновилось, в storage нет «Трудозатраты».
- Живая AB `519492935` — только `--allow-live-ab` + явная команда Саши.
- Авторизация: токен Confluence — `CONFLUENCE_TOKEN` из `~/USERTOOLS/ConfluenceSync/.env` (см. `load_confluence_env` в tutu-confluence-jira). `web_extract` блокирует `dom.tutu.ru` — только curl/CLI.
