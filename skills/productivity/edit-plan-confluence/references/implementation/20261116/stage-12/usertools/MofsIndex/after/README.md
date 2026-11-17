# MofsIndex

SQLite/FTS5-индекс размеченных встреч из WorkVault — быстрый поиск по 4 корзинам (projects/tools/rooms/contacts), датам и полному тексту.

## Что это

Держит актуальный локальный SQLite-индекс поверх пар `summary.md + transcript.md` из `WorkVault/Meetings/NewMeetings/`. Скилл `workvault-rag` отвечает на структурные запросы за <10 мс вместо повторного grep/read по 600+ файлам.

## Установка

```bash
pip install -e /home/tkachenkoav/USERTOOLS/MofsIndex
```

Общий venv с MOFS/EntityRegistryCLI.

## Быстрый старт

```bash
# Полная перестройка индекса (575 встреч ~5с)
mofs-index index --rebuild --yes

# Инкрементальное обновление (только изменённые)
mofs-index index

# Статистика
mofs-index stats

# Проверка согласованности
mofs-index verify

# VACUUM + FTS optimize
mofs-index vacuum
```

## Python API

```python
from mofs_index import search_meetings, get_meeting, get_transcript_snippets, list_slugs

# Поиск по slug проекта
hits = search_meetings(slugs={"projects": ["kirill_1on1"]})

# FTS + дата
hits = search_meetings(query="DWH", date_from="2026-06-01")

# slug mode='all' — пересечение (встречи где есть ОБА slug)
hits = search_meetings(
    slugs={"projects": ["ai_analitik", "trisigma"]},
    slug_mode="all"
)

# Полная карточка встречи
rec = get_meeting("2026-07-08 11-05-00 Кирилл 1-1")

# Список всех slug в корзине с частотой
slugs = list_slugs("projects")  # [("kirill_1on1", 26), ...]

# Сниппеты из транскрипта
snippets = get_transcript_snippets("2026-07-08 11-05-00 Кирилл 1-1", "DWH")
```

## Параметры search_meetings

| Параметр | Тип | Описание |
|---|---|---|
| `query` | str | FTS5 MATCH по summary+transcript+title |
| `date_from` / `date_to` | str | YYYY-MM-DD включительно |
| `slugs` | dict | `{"projects": ["slug1", "slug2"]}` |
| `slug_mode` | str | `"any"` (объединение) / `"all"` (пересечение) |
| `limit` | int | Максимум результатов (default 50) |
| `order` | str | `"date_desc"` / `"date_asc"` / `"relevance"` |

## Интеграция с MOFS

Хуки автоиндексации встроены в конец `mofs run`, `mofs rematch` (real-mode) и `mofs edit`. Отключить: `MOFS_INDEX_AUTO=0`.

## Структура БД

- `meetings` — мета-данные встреч (без body)
- `meeting_slugs` — нормализованные корзины (projects/tools/rooms/contacts)
- `meetings_fts` — FTS5 по title + summary_body + transcript_body
- `meta` — schema_version, last_full_reindex_at

БД: `~/USERTOOLS/MofsIndex/state/index.sqlite` (~57 MB после VACUUM на 575 встречах).

## Производительность (реальные данные)

| Операция | Результат |
|---|---|
| Full rebuild (575 встреч) | ~5с |
| Инкрементальный проход (0 изменений) | <500мс |
| `search_meetings(slug)` | <5мс |
| `search_meetings(FTS+дата)` | <25мс |
| `get_meeting(id)` | <2мс |
| Размер БД | 57 MB |

## Plan typed API: архив, история, identity и публикации (§20)

Plan-состояние находится в той же `state/index.sqlite`; `mofs_index.plan.writer`
и `query/history/identity/selectors` — единственный путь записи/чтения.
SQL из скиллов, отдельная plan-БД и MD как источник истины запрещены.
`<slug>.ganttchart.md` — производная проекция `plan.render`.
Docs-only интеграция этапа 12 не мигрирует рабочую БД.

`writer.commit_import_snapshot` атомарно связывает snapshot/version-данные,
item и snapshot_committed event. Дедупликация: plan+lineage+source MPP SHA+
representation+normalization fingerprint+resolved timezone; новое поступление
сохраняется даже при unchanged. Batch frozen context/manifest и input locators
не меняются при resume. Reader не повторяется после committed read-back.

```python
from mofs_index.plan.history import history, HistoryRequest
from mofs_index.plan.query import resolve_plan, list_versions, diff_versions, task_history
# conn — явное изолированное соединение; plan_id — результат resolve_plan.
answer = history(conn, HistoryRequest(project_slug='trisigma', view='files',
    time_field='received', since='2026-11-17T00:00:00+03:00',
    until='2026-11-18T00:00:00+03:00'))
versions = list_versions(conn, plan_id)
difference = diff_versions(conn, plan_id,
    {'kind': 'snapshot', 'snapshot_id': from_snapshot_id},
    {'kind': 'snapshot', 'snapshot_id': to_snapshot_id},
    mapping_revision_id=confirmed_revision_id)
```

History files/snapshots/publications разделяет поступления, уникальные снимки и
регистрации. Период `[since,until)` timezone-aware; локальные границы суток
пользователя включают offset. Unknown times/source dates — отдельные counts/
records, opaque cursor требует тех же фильтров/порядка. Received/observed/frozen/
recorded/source/status/published/verified не взаимозаменяемы.

Оба selector проверяются по проекту до diff. Publication выбирается точным
publication_id с page/attachment/version/snapshot/link quality, один v2 не ID.
Identity привязана к направленной паре и immutable evidence/revision; UID или
lineage не proof. `writer.register_identity_confirmation`,
`writer.select_operation_identity` и `writer.revoke_identity_revision` сохраняют
историю. Partial/unknown mapping даёт структурные остатки, MPP/Gantt без proof —
representation_mismatch. Dependencies сравниваются мультимножествами с type/
signed lag/units/elapsed/calendar basis, календари и назначения — по сохранённой
семантике; timezone не означает полноту, причинность без replay не установлена.

Публикационные links проверяются независимо от nullable snapshot.published_at.
Сохранённые legacy_unverified/verified_v1 не заменяются свежим наблюдением.
`edit-plan-confluence publication verify` — GET-only Confluence и append-only
локальное наблюдение current_state/historical_version. Текущее совпадение не
восстанавливает старую дату; недостаточные bytes/storage/link — not_verified/5.
Archive/page/schedule — независимые статусы; schedule может оставаться not_verified.

До будущей миграции production — `plan.backup.backup_to(dest, src_path=...)` и
`verify_backup(dest)` (online SQLite backup с WAL, integrity/FK); restore_from
по умолчанию dry_run, реальная запись требует dry_run=False и confirm=True.
Восстановление сначала проверяется в отдельном дереве; artifacts/receipts
копируются существующим backup-контуром отдельно. Переиндексация docs не удаляет
plan-таблицы и baseline. Приёмочные БД/WorkVault/cache только в T, tests/plan
запускаются отдельным pytest процессом.

Канон эксплуатации — `~/hermes-workspace/skills/productivity/edit-plan-confluence/`:
`references/cli-contract.md`, `history-and-verification.md`, `operations-and-recovery.md`.
