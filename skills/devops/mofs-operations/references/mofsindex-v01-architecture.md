# MofsIndex v0.1.0 — архитектурные детали

## ⚠️ Известная проблема: namespace-package при editable install

`pip install -e .` с `[tool.setuptools.packages.find] include = ["mofs_index*"]` создаёт namespace-package — `__init__.py` не выполняется, публичный API недоступен.

Симптомы: `mofs_index.__file__ is None`, `from mofs_index import search_meetings` → ImportError.

Фикс — заменить в `pyproject.toml`:
```toml
# БЫЛО:
[tool.setuptools.packages.find]
include = ["mofs_index*"]

# СТАЛО:
[tool.setuptools]
packages = ["mofs_index"]   # явный список, без find-эвристики
```
Переустановить: `pip uninstall -y mofs-index && pip install -e /home/tkachenkoav/USERTOOLS/MofsIndex`

Проверка: `python3 -c "from mofs_index import search_meetings; print('OK')"`

Временный workaround (пока фикс не применён):
```python
import sys
sys.path.insert(0, '/home/tkachenkoav/USERTOOLS/MofsIndex')
from mofs_index.searcher import search_meetings
```

Дата реализации: 21.07.2026

## Структура пакета

```
~/USERTOOLS/MofsIndex/
  mofs_index/
    __init__.py     — публичный API (search_meetings, get_meeting, get_transcript_snippets)
    db.py           — DDL, connect/initialize/ensure_schema, WAL, SchemaMismatch
    parser.py       — ParsedMeeting, parse_summary_file, strip_frontmatter, parse_wiki_links
    indexer.py      — RegistryView, process_meeting, reindex, ReindexStats
    searcher.py     — MeetingHit, MeetingRecord, search_meetings, get_transcript_snippets
    hooks.py        — reindex_meeting, reindex_batch (fail-soft, MOFS_INDEX_AUTO)
    cli.py          — mofs-index index/stats/verify/vacuum
  tests/            — 65 тестов
  pyproject.toml    — editable install в ProtocolFromSummary/.venv
```

## Схема БД (SQLite, WAL)

```sql
-- Основная таблица
meetings (meeting_id PK, meeting_date, meeting_time, title,
          summary_path, transcript_path, transcript_present,
          summary_mtime_ns, transcript_mtime_ns, summary_sha1, transcript_sha1,
          mofs_status, objects_version, indexed_at, obsidian_url)

-- Нормализованные slugs
meeting_slugs (meeting_id FK, bucket, slug, display)
INDEX idx_slugs_by_slug ON (bucket, slug)

-- FTS5 (standalone, не content table — ограничение SQLite 3.34)
meetings_fts (meeting_id UNINDEXED, title, summary_body, transcript_body)

-- Метаданные
meta (key PK, value)  -- хранит schema_version, last_full_reindex_at
```

**Важно:** `summary_body` и `transcript_body` хранятся ТОЛЬКО в FTS-таблице, не в `meetings`.
Это экономит ~50 MB (без дублирования 108 MB → 57 MB).

## Отклонения от ТЗ (обоснованы ограничениями SQLite 3.34)

1. **FTS5 standalone** вместо `content=meetings` — external content table не поддерживает `DELETE ... WHERE meeting_id=?`, только полную перестройку
2. **`OR`-условия** вместо `WHERE (bucket,slug) IN (...)` — row-value syntax не поддерживается SQLite 3.34
3. **Rebuild в 3 прохода** (parse → meetings+slugs TX → FTS TX + optimize) — даёт 4.18с на 575 встречах вместо ~15с в одном цикле

## Производительность (575 встреч, июль 2026)

| Операция | Результат | Цель ТЗ | Статус |
|---|---|---|---|
| Full rebuild | 4.9с | <10с | ✅ |
| search по slug | 1.69мс | <10мс | ✅ |
| search FTS+дата | 20.5мс | <10мс | ⚠️ тикет v0.2 |
| get_meeting(id) | 0.91мс | <2мс | ✅ |
| Размер БД (после vacuum) | 57 MB | <60 MB | ✅ |

**FTS+дата 20.5мс** — превышение из-за FTS5 MATCH по 45 MB текста без дополнительной оптимизации.
Тикет v0.2: добавить `slugs_flat` колонку в FTS для раздельной индексации, рассмотреть разделение FTS по summary и transcript.

## Интеграция с MOFS

**pipeline.py** — хук в конце `run_pipeline` (только dry_run=False, stats.processed > 0):
```python
try:
    from mofs_index.hooks import reindex_batch
    reindex_batch(processed_meeting_ids, settings.new_meetings_path)
except ImportError:
    pass  # graceful degradation — MOFS работает без индексации
except Exception as e:
    print(f"WARN: mofs-index hook failed: {e}", file=sys.stderr)
```

**cli.py** — хук в конце `_cmd_edit` (после успешного commit):
```python
try:
    from mofs_index.hooks import reindex_meeting
    reindex_meeting(meeting_id, summary_path=summary_path)
except ImportError:
    pass
except Exception as e:
    print(f"WARN: mofs-index reindex failed: {e}", file=sys.stderr)
```

## Тесты после интеграции

- MofsIndex: 65/65 (test_db + test_parser + test_indexer + test_searcher + test_cli + test_hooks)
- MOFS: 108/108 (103 оригинальных + 5 интеграционных в test_hook_integration.py)
