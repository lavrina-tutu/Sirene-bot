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
