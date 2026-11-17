# История, compare и проверка публикаций

Истина — typed `mofs_index.plan.history/history(HistoryRequest)` и
`query.resolve_plan/list_versions/diff_versions/task_history`, тот же API у
workvault-rag и CLI. Свободный SQL и MD-витрина как доказательство запрещены.
`<slug>.ganttchart.md` — производная проекция с IDs/quality/receipt.

```cli-example
cli.py history --project-slug trisigma --view files --order ingested
cli.py history --project-slug trisigma --view snapshots
cli.py history --project-slug trisigma --view publications
cli.py history --project-slug trisigma --view files --time-field received --since 2026-11-17T00:00:00+03:00 --until 2026-11-18T00:00:00+03:00
```

Files — все поступления, включая ошибки, дубликаты и незавершённые;
snapshots — уникальные снимки; publications — точные регистрации/links/trust
и append-only observations. Времена received/observed, frozen, recorded,
source_version_date, status_date, published_at, verified_at различны.
У files recorded_at относится к событию этого поступления;
snapshot_recorded_at — к созданию переиспользованного snapshot.
Имя файла и время импорта не восстанавливают неизвестные даты версии/публикации.

Для «сегодня» вычислить начало и конец локального календарного дня на момент
запроса. Зона пользователя для Саши Europe/Moscow, не timezone MPP.
Каждая граница включает свой UTC offset, в том числе при переходе DST:

```python
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
zone = ZoneInfo('Europe/Moscow')
day = datetime.now(zone).date()
since = datetime.combine(day, time.min, zone).isoformat()
until = datetime.combine(day + timedelta(days=1), time.min, zone).isoformat()
```

Фильтр `[since,until)`. На 17.11.2026 пример выше — +03:00…+03:00.
Дата без времени/offset отклоняется. Defaults time-field: files=received,
snapshots=recorded, publications=published. `--order source` меняет только
порядок. Неизвестное выбранное время — unknown_time_count и исключение из
периода, неизвестные даты версии — отдельные unknown_source_dates/count.
Читать records и unknown_source_dates каждой страницы. Непрозрачный next_cursor
повторять с теми же фильтрами/порядком; limit можно менять. Cursor фиксирует
состав, поздние backdated-поступления видны новому обходу. known_at — время
запроса, не восстановленное знание прошлого.

## Точные версии и compare

```cli-example
cli.py compare --project-slug trisigma --from snapshot:test-a --to snapshot:test-b --mapping-revision test-revision
cli.py compare --project-slug trisigma --from publication:test-pub-a --to publication:test-pub-b
```

Сначала выбрать ID через history/list_versions. «v2» не selector: уточнить
page/attachment и выбрать точный publication ID. Не брать произвольную страницу.
Оба селектора проверяются по проекту до сравнения; публикация содержит
page/attachment/version/snapshot/lineage и качество связи. Typed assertions
page_id/attachment_id/attachment_version/snapshot_id разрешены только с ID и
проверяются на совпадение. MPP/Gantt без подтверждённого mapping точной пары —
representation_mismatch/4. Link публикации к исходному MPP не доказывает
позиционные Gantt ID. Не связанные с Gantt snapshot публикации дают raw
representation_fields/unmatched_entities, а не доказанный перенос задач.

Сравниваются все сохранённые поля задач, splits/baseline; зависимости как
мультимножества с type/signed lag/units/elapsed/calendar basis; календари с
интервалами/исключениями/наследованием/коэффициентами/bindings; назначения с
units/work/датами/timephased/календарём и ресурсами. Partial/unknown mapping
сохраняет структурные остатки; их нельзя назвать доказанными добавлениями или
удалениями одной сущности. Unknown timezone/date-only не дают абсолютный delta.
Timezone сама по себе не доказывает completeness. Working-time drift unavailable;
без schedule replay причинность сдвига финала не установлена.

## «Какая версия опубликована?»

Вернуть последнюю подтверждённую регистрацию с точными IDs, trust и временем
подтверждения отдельно от текущего наблюдения цели. Более поздняя legacy запись
не становится подтверждённой лишь из-за порядка. Проверить связанные публикации
через typed API: NULL snapshot.published_at не доказывает их отсутствия.
Если подтверждённой версии нет, явно сообщить это и показать имеющиеся регистрации.

```cli-example
cli.py publication verify --project-slug trisigma --publication-id test-pub-a --scope current_state
cli.py publication verify --project-slug trisigma --publication-id test-pub-a --scope historical_version
```

Verify делает только GET, проверяет expected archived bytes точной версии,
metadata/storage и для current scope — свежую актуальную цель. Historical
scope проверяет сохранённую версию страницы. Добавляет только локальное
наблюдение с ID/scope/verified_at, без роста версии вложения и без изменения
старых trust/status/published_at. POST/PUT/PATCH/DELETE запрещены транспортом.
Нет bytes/storage/link или mismatch → not_verified/5 с конкретным verification_status.
Успех — verified_observation/0; schedule остаётся независимым.

Trust регистрации legacy_unverified/verified_v1 не путать с результатом
наблюдения verified_observation/not_verified/verification_failed. Текущее
совпадение не доказывает прошлую дату. Historical версия может совпадать,
когда текущая уже чужая. Без свежего наблюдения говорить «последняя известная
регистрация на момент …», с trust и временем; не обещать актуальность сейчас.
`archive-history` — GET-only импорт legacy истории; не повышает доверие.

## Д4: актуальность и изменения задач

`history --project-slug SLUG --view files` дополняет строки `source_mtime_ns` и
возвращает `result.current_plan` по всему архиву проекта (независимо от limit,
порядка поступления и фильтра периода). `basis=source_file_mtime_ns` — исходный
mtime при согласованном чтении; у ZIP — доставленного контейнера. Источник может
быть удалён после архивирования: история читает сохранённое событие MofsIndex.
Старые записи без mtime остаются unknown; разные snapshot с одинаковым максимумом
дают ambiguous. При публикации явно указанного файла выбор пользователя сохраняется.

`compare --project-slug SLUG --from snapshot:OLD --to snapshot:NEW` возвращает
`result.task_history.added/removed`: каждая запись содержит исходную задачу и
все её входящие/исходящие связи соответствующей версии, включая внешние.
`basis=source_local_key_diff` отличает дифф записей от доказанной идентичности:
изменение ключа без mapping — удалённая/добавленная запись, без догадки о переименовании.
Подтверждённые mapping-пары не попадают в добавления/удаления только из-за нового UID.
Технический diff и его независимые статусы identity/quality сохранены.
