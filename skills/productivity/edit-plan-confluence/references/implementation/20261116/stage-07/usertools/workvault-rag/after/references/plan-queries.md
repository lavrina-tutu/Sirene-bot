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
- MPP-снимок: `{"kind": "snapshot", "snapshot_id": "..."}` — локальный `uid` (сам по себе не доказывает идентичность),
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

UID служит локальным ключом поиска. Без явного основания совпавшие UID разных MPP
возвращаются как `unmatched_tasks`; общая история и перенос не вычисляются.
Для доказанной истории нужны опорный snapshot и прямое подтверждение каждой
пары; подтверждение A→B и B→C не создаёт A→C.

```python
hist = task_history(conn, plan_id, '744', from_snapshot_id=snap_a,
                    to_snapshot_id=snap_b, mapping_revision_id=revision_id)
# hist['receipt']: mapping, mapping_revision_id, evidence_id, identity_proofs.
# Изменившийся UID разрешается по выбранному mapping, а не по совпадению номера.
# Перенос задачи не доказывает перенос финала проекта.
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
result['result_class']  # без прямого подтверждённого соответствия — insufficient_data;
                         # на паре публикаций — observed_diff с blockers.
                         # Статус групп не доказывает расписание или причинность.
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
| v5↔v6 (MPP-пара) | финал неизменен (13.01.2027), UID 744 +4 суток (12→16 ноября), UID 748 +2 суток (18→20 ноября) | историческое наблюдение; новый task_history требует прямую revision/evidence |

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


## Идентичность и revision (§20.6.3, этап 07)

MPP snapshots сравниваются через тот же `query.diff_versions`, что использует
архив. Сначала проверяется проект обоих snapshot. Общая lineage, имя файла,
метаданные и совпавший UID не подтверждают происхождение. Без свидетельств —
`receipt.mapping:unknown`, `unmatched_entities` для task/resource/calendar/assignment;
не выдавать эти остатки за доказанные добавления/удаления одной задачи.

<!-- stage07-identity-example -->
```python
from mofs_index.plan.query import diff_versions
difference = diff_versions(conn, plan_id,
    {'kind': 'snapshot', 'snapshot_id': snap_a},
    {'kind': 'snapshot', 'snapshot_id': snap_b},
    mapping_revision_id=revision_id)
proof = difference['receipt']
# proof['mapping_revision_id'], proof['evidence_id'], proof['evidence_sha256']
# difference['unmatched_entities'] сохраняет остатки частичного mapping.
```

Явная revision должна соответствовать проекту, направленной паре snapshot,
представлениям, SHA-256 источников и профилям, быть активной и иметь доступное
свидетельство с тем же SHA-256. Без явного ID выбирается единственная активная;
несколько дают `mapping_ambiguous / 3`. Старые неограниченные mapping-записи
не становятся подтверждениями после миграции. Same-source допустим только
для одного snapshot либо одинакового источника в одинаковом профиле,
представлении и таймзоне; на другие файлы это доказательство не переносится.

`identity confirm/show` — CLI edit-plan-confluence, глобальные пути перед командой.
Confirm сохраняет явное пользовательское свидетельство неизменяемым артефактом;
он не запускает ожидающую операцию. Исправление revision — явный `--supersedes`,
предыдущая остаётся в истории. Отзыв — typed writer `revoke_identity_revision`.
Зафиксированная для операции revision повторно проверяется, автоматически
не заменяется; другая даёт `mapping_revision_conflict / 4`. Недостаточный partial
mapping не занимает слот выбора. Для B/C достаточно только соответствия обеих
задач и всех остальных требуемых сущностей; применение правил относится к этапу 09.

В этапе 07 снято ложное подтверждение UID; полное семантическое сравнение связей,
календарей/назначений и точные publication selectors относятся к этапу 11.
Текущий snapshot diff сообщает `completeness:partial`, `calendar:unknown` и
свою ограниченную область. Наличие таймзоны не доказывает полноту календаря.
