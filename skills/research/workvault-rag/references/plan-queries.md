# Планы — точные selectors, mapping и доверие

Источник истины — typed API MofsIndex (`mofs_index.plan.query`, `history`),
существующая plan-схема и архив байтов WorkVault. MD `<slug>.ganttchart.md` —
производная проекция. Свободный SQL и вывод идентичности из MD запрещены.

```python
import sys
sys.path.insert(0, '/home/tkachenkoav/USERTOOLS/MofsIndex')
from mofs_index.db import connect_durable
from mofs_index.plan.query import resolve_plan, list_versions, diff_versions, task_history, explain_finish_change
```

## Точные селекторы и сравнение

`list_versions(conn, plan_id)` возвращает publication ID, страницу, attachment ID,
версию, trust, snapshot links и наблюдения; у снимков — snapshot ID,
representation и связи публикаций. Выбрать обе записи до сравнения.
Один номер «v2» неоднозначен: нужны страница и вложение для разрешения
точного publication ID; произвольную подходящую строку не выбирать.

```python
# pub_a/pub_b — точные ID из списка, разрешённые с пользователем по странице/attachment.
d = diff_versions(conn, plan_id,
    {'kind': 'publication', 'publication_id': pub_a},
    {'kind': 'publication', 'publication_id': pub_b})
# d['receipt']: exact version_a/version_b, publication_a/publication_b,
# trust_a/trust_b, hash_a/hash_b, link_quality_a/link_quality_b,
# mapping, mapping_revision_id, completeness и known_at.
```

Оба селектора проверяются по проекту до diff. Дополнительные typed assertions
`page_id`, `attachment_id`, `attachment_version`, `snapshot_id` допустимы
только вместе с publication ID и проверяются на совпадение.
Отсутствующий/чужой ID не превращается в другую версию. CLI:

```text
cli.py --db /isolated/state/index.sqlite --workvault /isolated/WorkVault --cache-dir /isolated/cache compare --project-slug trisigma --from publication:<id-a> --to publication:<id-b>
cli.py --db /isolated/state/index.sqlite --workvault /isolated/WorkVault --cache-dir /isolated/cache compare --project-slug trisigma --from snapshot:<id-a> --to snapshot:<id-b> --mapping-revision <revision-id>
```

MPP и Gantt принадлежат разным пространствам. Без подтверждённого mapping
точной пары Gantt/MPP snapshot — `representation_mismatch / 4`.
Связь публикации с исходным MPP подтверждает provenance источника, но не
позиционные Gantt ID. Без доказанной связи с Gantt snapshot результат
сохраняет `representation_fields` и `unmatched_entities`, `mapping:unknown`;
совпадение raw bytes сообщается независимо. Исторический diff позиционных
ID нельзя повторять как доказанные добавления/удаления задач.

Snapshot diff сравнивает все сохранённые значимые поля задач, splits и baseline,
полные мультимножества зависимостей (тип, signed lag, units, elapsed,
calendar basis), интервалы/исключения/наследование/привязки календарей,
ресурсы, назначения, units/work, даты и timephased. Частичный mapping
не скрывает остатки. Коллекции/поля неполны → `completeness:partial`.
Timezone не доказывает полноту календаря. Неизвестная timezone или date-only
не дают абсолютного date delta; секундная разница сохраняется без округления
до целых суток. Working-time drift остаётся `unavailable`.

`task_history(conn, plan_id, uid, from_snapshot_id=..., to_snapshot_id=...,
mapping_revision_id=...)` объединяет только непосредственно подтверждённые
пары; UID без anchor — локальный поиск с несопоставленными остатками.
`explain_finish_change` сообщает наблюдаемые группы изменений и блокеры;
`build_groups` без schedule replay не даёт `validated_attribution`.
Перенос задачи не доказывает причину сдвига финала.

## Проверка публикаций и времена

```text
cli.py publication verify --project-slug trisigma --publication-id <id> --scope current_state
cli.py publication verify --project-slug trisigma --publication-id <id> --scope historical_version
```

Использовать тот же CLI edit-plan-confluence. Запросы Confluence — только GET,
в том числе точная версия и свежая актуальность для current scope. Новая
проверка добавляет наблюдение MofsIndex; страница, версия вложения, прежние
события, trust и published_at не переписываются. Нет ожидаемых bytes,
storage либо подтверждённой связи snapshot → `not_verified / 5` с причинами.
Проверка страницы и байтов не повышает `schedule:not_verified`.

Сохранённый trust регистрации (`legacy_unverified` / `verified_v1`) и
результаты наблюдений (`verified_observation`, `verification_failed`,
`not_verified`) показываются отдельно. Каждый observation содержит scope
`current_state` или `historical_version`, ID и verified_at. Текущее совпадение
не восстанавливает доказательство прежней даты публикации. Историческая
версия может совпасть при уже изменившейся текущей цели.
Без свежего наблюдения говорить «последняя известная регистрация на момент …».
`known_at` — время запроса, а не историческая дата знания.

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

Этап 11 использует тот же механизм identity для полного семантического diff.
Наличие таймзоны не доказывает полноту календаря; неполные поля и коллекции
сохраняют `completeness:partial`, а неизвестное соответствие — структурные остатки.
