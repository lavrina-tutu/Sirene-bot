# Планы (gantt/mpp) — typed query API (code snippets)

Справочный материал к `SKILL.md`, секция «Планы (gantt/mpp)». Модуль:
`/home/tkachenkoav/USERTOOLS/MofsIndex/mofs_index/plan/query.py` (+ `render.py` —
MD-витрина, `writer.py`/`schema.py` — persistence). Источник истины — SQLite
(`~/USERTOOLS/MofsIndex/state/index.sqlite`), пилот-витрина
`Entities/zd/Pages/zd.ganttchart.md` — производная (рендерится из тех же таблиц,
Q2 DECISIONS-owner.md). ТЗ: `WorkVault/Hermes-Backlog/dev/pochinka-tz-arhiv-plana-
20261113/out/FINAL-TZ-arhiv-plana.md` (R-023…R-036).

## Импорт

```python
import sys
sys.path.insert(0, '/home/tkachenkoav/USERTOOLS/MofsIndex')
from mofs_index.db import connect_durable
from mofs_index import (
    resolve_plan, list_versions, diff_versions, task_history,
    compare_baseline, explain_finish_change,
)

conn = connect_durable()
plan = resolve_plan(conn, 'zd')
plan_id = plan['plan_id']
```

Каждая функция возвращает `dict` с обязательным полем `receipt` — приводить
вместе с числом в ответе, не только голое число (R-026).

## Представления версий — не смешивать

- Confluence-публикация (Gantt JSON): `{"kind": "publication", "attachment_version": N}`
  — числовой gantt-id, **нет** UID, история плотная (v1..v6 ZD).
- MPP-снимок: `{"kind": "snapshot", "snapshot_id": "..."}` — подтверждённый `uid`,
  полный граф (ES/EF/LS/LF/календари), но только для версий с реально сохранённым
  исходным MPP (R-036 — не для всех публикаций MPP сохранён).

`diff_versions()` с разными `kind` в `version_a`/`version_b` даёт
`result_class == "representation_mismatch"` — это честный ответ (разные
пространства идентичности, S3 RS1-collect.md), не ошибка вызова.

```python
versions = list_versions(conn, plan_id)['versions']
publications = [v for v in versions if v['kind'] == 'publication']
snapshots = [v for v in versions if v['kind'] == 'snapshot']
```

## Сценарий 1 — «Что поменялось в ZD [между версиями]?»

```python
d = diff_versions(conn, plan_id,
                   {'kind': 'publication', 'attachment_version': 3},
                   {'kind': 'publication', 'attachment_version': 4})
d['links_removed']   # [{'from': 28, 'to': 19}]  — реальное число на боевой БД
d['content_identical']  # False
```

## Сценарий 2 — «На сколько дней уехал финал?»

```python
d = diff_versions(conn, plan_id,
                   {'kind': 'publication', 'attachment_version': 4},
                   {'kind': 'publication', 'attachment_version': 5})
d['root']['finish_delta_calendar_days']  # 14 (реально, боевая БД ZD)
d['root']['duration_delta']               # 3.0 (37 -> 40), отдельно от финала (R-031)
```

## Сценарий 3 — «Как менялись сроки у юристов/конкретной задачи?»

По подтверждённому MPP `uid`, не по имени задачи (имя может повториться/не быть
уникальным идентификатором):

```python
hist = task_history(conn, plan_id, '744')
hist['finish_delta_calendar_days']  # 4 (реально, ZD UID 744: 12 -> 16 ноября)
hist['caveat']  # перенос ОДНОЙ задачи не равен переносу проекта — явная оговорка
```

## Сценарий 4 — «Какие связи удалили?»

```python
d = diff_versions(conn, plan_id,
                   {'kind': 'publication', 'attachment_version': 3},
                   {'kind': 'publication', 'attachment_version': 4})
d['links_removed']  # [{'from': 28, 'to': 19}]
```

## Сценарий 5 — «За счёт каких работ финал ушёл?»

```python
result = explain_finish_change(conn, plan_id,
                                {'kind': 'snapshot', 'snapshot_id': snap_a},
                                {'kind': 'snapshot', 'snapshot_id': snap_b})
result['result_class']  # 'validated_attribution' на полной MPP-паре без split/leveling,
                         # 'observed_diff' с result['blockers'] на паре публикаций
                         # (нет UID-mapping) или на MPP-паре со split-сегментами
                         # (честно — не выдумывает атрибуцию, R-035/AC-139)
```

На ПАРЕ ПУБЛИКАЦИЙ (не snapshot) `explain_finish_change()` сразу возвращает
`observed_diff` + явные `blockers` ("представление не MPP snapshot", "полный
replay недоступен без исходного MPP") — это ожидаемо для исторических вопросов
без сохранённого исходника (напр. ZD v4→v5 +14 — задокументированный пример
честного отказа в R-036 §10 ТЗ).

## Сценарий 6 — «Что знали на дату X (known_at)?»

```python
versions = list_versions(conn, plan_id)
versions['receipt']['known_at']  # момент вызова — снимок знания "сейчас",
                                   # не "текущая правда задним числом"
```

Каждый `receipt` несёт `known_at` отдельно — при вопросах про состояние
знания на прошлую дату сверяться с `recorded_at`/`observed_at` конкретных
версий (`list_versions`), а не с `known_at` ответа (это всегда "сейчас").

## Реальные числа ZD (боевая БД, сверено с R-036 §10 ТЗ)

| Пара | Факт | Источник |
|---|---|---|
| v1→v3 | байты идентичны, diff=0, три публикации | `diff_versions` (publication) |
| v3→v4 | удалена связь `28→19` | `diff_versions` → `links_removed` |
| v4→v5 | финал +14 календарных суток (30.12.2026→13.01.2027), duration 37→40 (+3) | `diff_versions` → `root` |
| v5↔v6 (MPP-пара) | финал неизменен (13.01.2027), UID 744 +4 суток (12→16 ноября), UID 748 +2 суток (18→20 ноября) | `task_history('744')`/`task_history('748')` |

## Ограничения (честно)

- Полный `explain_finish_change` уровня В (`validated_attribution` через
  `plan_scheduler.replay`) на реальных MPP ZD заблокирован split-сегментами
  в исходнике (`UnsupportedProfileError`, см. MppReader
  `references/scheduler-capability-matrix.md`) — для ZD пока доступен только
  уровень групп изменений (`build_groups`) без полного CPM-пересчёта.
- `plan_fts` (R-027) разрешает "последний" через typed SQL `list_versions`/
  `diff_versions`, не через FTS rank — FTS используется только для
  полнотекстового поиска по MD-телу, не для разрешения версии.

## История поступлений, snapshot и публикаций (§20, этап 06)

«Покажи хронологию планов» и «какие файлы загрузили сегодня» — история
**поступлений**, включая повторные байты, ошибки и незавершённые элементы.
Использовать тот же typed API `mofs_index.plan.history`, что и CLI скилла
edit-plan-confluence. `plan_history.py` по-прежнему импортирует историю вложений;
его `import_history()` не является запросом истории поступлений.

```python
from mofs_index.plan.history import history, HistoryRequest
answer = history(conn, HistoryRequest(
    project_slug='trisigma', view='files', time_field='received',
    since='2026-11-16T00:00:00+03:00', until='2026-11-17T00:00:00+03:00',
    limit=100,
))
# Следующая страница: тот же запрос, cursor=answer['result']['next_cursor'].
```

CLI (глобальные пути перед подкомандой):

```text
/usr/bin/python3 /home/tkachenkoav/hermes-workspace/skills/productivity/edit-plan-confluence/scripts/cli.py history --project-slug trisigma --view files --time-field received --since 2026-11-16T00:00:00+03:00 --until 2026-11-17T00:00:00+03:00
```

Для «сегодня» вычислять локальные границы суток пользователя (Europe/Moscow,
если пользователь не задал другую зону), сохраняя offset. Период — **[since, until)**;
дата без времени/offset отклоняется. `files` по умолчанию фильтруется по
`received`, `snapshots` — по `recorded`, `publications` — по `published`.
`--order source` меняет только сортировку; фильтр остаётся прежним.

Различать received/observed, frozen, recorded, source_version_date, status_date,
published и verified. Ни имя файла, ни время импорта не восстанавливают дату
версии или исторической публикации. Явная дата версии сравнивается на календарной
шкале UTC с полуночью; это не устанавливает таймзону задач MPP.

`result.unknown_time_count` — количество записей с неизвестным выбранным временем
в области проекта/lineage; при фильтре они исключены. При source-сортировке
`records` содержит известные даты, `unknown_source_dates` — отдельную часть той же
страницы с неизвестными датами; `unknown_source_date_count` — их общее количество
после фильтра. Для полного обхода читать обе части каждой страницы и непрозрачный
`next_cursor`. Cursor сохраняет границу набора и ключ последней записи, требует
неизменных фильтров/порядка; новые поступления не сдвигают страницы старого обхода.

Поступления содержат имена, locator, hash, времена, item/operation/batch/snapshot ID,
результат и ошибку. Snapshot не дублируется при повторном поступлении. Публикации
содержат точный publication ID, page/attachment/version, observed/published/recorded
и сохранённый trust. NULL `snapshot.published_at` не доказывает отсутствие связанной
публикации. Без нового наблюдения страницы формулировать «последняя известная
регистрация на момент …», явно указывая trust; не объявлять её текущей подтверждённой.

«Что не загрузилось в пакете?» → `batch show --batch-id ID --view errors`;
«почему нужно решение?» → `operation show --operation-id ID`. Принятие proposal
только регистрирует решение; обработку запускает явный `batch resume --retry-decisions`.
История не подтверждает идентичность UID и не запускает reader/сеть/публикацию.
