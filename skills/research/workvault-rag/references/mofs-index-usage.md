# mofs_index — полное API-руководство (code snippets)

Справочный материал к `SKILL.md`. Модуль: `/home/tkachenkoav/USERTOOLS/MofsIndex/mofs_index/`
(`searcher.py` — встречи, `query.py` — документы ТЗ). Индекс: SQLite+FTS5,
`~/USERTOOLS/MofsIndex/state/index.sqlite`. Обновляется хуком в конце `mofs run`/`mofs rematch`
(только real-mode, не dry-run). ТЗ: `WorkVault/Hermes-Backlog/TZ/MofsIndex/MofsIndex_TZ.md`.

## Импорт

```python
import sys
sys.path.insert(0, '/home/tkachenkoav/USERTOOLS/MofsIndex')
from mofs_index import (
    search_meetings, get_meeting, get_meeting_body,
    get_transcript_snippets, list_slugs, search_docs, get_doc,
    search_protocols,
)
```

## Режим 1 — поиск встреч (список)

```python
# По slug проекта
hits = search_meetings(slugs={'projects': ['kirill_1on1']}, limit=20)

# По дате + slug
hits = search_meetings(
    date_from='2026-07-01', date_to='2026-07-31',
    slugs={'projects': ['ml_platforma']},
)

# По FTS-тексту + дата
hits = search_meetings(query='DWH метрики', date_from='2026-06-01')

# По контакту (покрытие 93%, см. references/known-limits.md)
hits = search_meetings(slugs={'contacts': ['Криворотов Кирилл']})

# MeetingHit — dataclass с атрибутами (НЕ dict, нет .get()):
for h in hits:
    print(h.meeting_date, h.title, h.meeting_id, h.obsidian_url, h.matched_slugs)
```

`slug_mode='all'` — пересечение корзин, `'any'` (по умолчанию) — объединение.
`order` — `'date_desc'` (по умолчанию), `'date_asc'`, `'relevance'`.

## Режим 2 — детали встречи (тело)

Основной способ — `get_meeting_body()`, одним SQL-запросом из FTS-таблицы, без чтения
файла с диска:

```python
body = get_meeting_body('2026-07-08 11-05-00 Кирилл 1-1')
# body — str (summary), или None если встречи нет в индексе, или '' если поле пустое
transcript_body = get_meeting_body(mid, include_transcript=True)
```

`get_meeting(meeting_id)` — карточка встречи без тела (метаданные + slugs):

```python
rec = get_meeting('2026-07-08 11-05-00 Кирилл 1-1')
# rec — MeetingRecord: meeting_id, meeting_date, title, mofs_status, obsidian_url,
# summary_path, transcript_path, transcript_present,
# slugs — {'projects': [(slug, display), ...], 'contacts': [...], ...}
# ⚠️ MeetingRecord НЕ содержит summary_body/transcript_body — за телом всегда get_meeting_body()
```

Комбинация «список → тела» для точечного чтения нескольких встреч без открытия N файлов:

```python
hits = search_meetings(slugs={'projects': ['ml_platforma']}, date_from='2026-07-01')
for h in hits:
    body = get_meeting_body(h.meeting_id)
    ...
```

Fallback на файл (если индекс не построен или meeting_id не найден): `read_file`
по `rec.summary_path` или `'/home/tkachenkoav/WorkVault/Meetings/NewMeetings/<meeting_id> - summary.md'`.

## Режим 3 — цитаты из транскрипта

```python
snippets = get_transcript_snippets('2026-07-08 11-05-00 Кирилл 1-1', 'ML-платформа',
                                    max_snippets=5, window=40)
# список строк-сниппетов с контекстом вокруг совпадения (FTS5 snippet())
```

Для полного текста — `get_meeting_body(mid, include_transcript=True)`, либо файл
`summary_path.replace('-summary.md', '-transcript.md')`.

## Поиск по документам ТЗ (`search_docs` / `get_doc`)

Работает поверх той же БД (таблицы `docs`/`docs_fts`) — для вопросов по ТЗ вместо
файлового grep+read по `Hermes-Backlog/TZ/`:

```python
hits = search_docs('матчер контактов', doc_type='tz', tool_name='MarkObjectsFromSummary')
# DocHit: doc_id, doc_type, title, tool_name, status, version, rank (BM25, меньше=лучше), snippet
for h in hits:
    print(h.title, h.snippet)

doc = get_doc(hits[0].doc_id)
# DocRecord: doc_id, doc_type, title, tool_name, status, version, mtime_ns, sha1, indexed_at
# (без тела — тело читать из файла по doc_id/path, если нужно полностью)
```

`doc_type` — `'tz'` / `'impl_plan'` / `None` (все). `query` — FTS5-выражение или
свободная строка (тогда OR по словам).

## Поиск по протоколам проектов (`search_protocols`)

Параллельный источник к встречам FF — согласованный протокол из Confluence
(`Entities/<slug>/protocol.md`, индексируется как `doc_type='protocol'`):

```python
hits = search_protocols('эксперимент alpha', entity_slug='trisigma')
# DocHit: doc_type='protocol', tool_name='trisigma' (entity_slug из frontmatter)
for h in hits:
    print(h.title, h.snippet)
```

В ответе пользователю подписывать слой: «Найдено в протоколе проекта (Confluence, согласовано)»
(симметрично «Найдено во встречах (FF, черновик)» для `search_meetings()`).

## list_slugs — список значений в корзине

```python
list_slugs('projects')  # [(slug, count), ...] по убыванию count
```

## Ripgrep — дополнение для точных цитат

`mofs index` даёт список встреч/тел; когда нужна точная строка с контекстом внутри
файла (например транскрипт целиком, не через `get_transcript_snippets`):

```bash
grep -rn -i 'КЛЮЧЕВОЕ_СЛОВО' \
  '/home/tkachenkoav/WorkVault/Meetings/NewMeetings/' \
  --include='*2026-07*summary*'
```

Контекст вокруг найденной строки транскрипта (±15 строк от номера N):

```bash
sed -n '$((N-15)),$((N+15))p' '/path/to/transcript.md'
```

## Проверка состояния индекса

```bash
source ~/USERTOOLS/ProtocolFromSummary/.venv/bin/activate
mofs-index stats    # число записей, дата последнего rebuild
mofs-index verify   # несогласованности файлов и БД
```

Если индекс устарел или не построен → `mofs-index index --rebuild --yes` (~5с).

## Формирование Obsidian-ссылки из meeting_id

```python
import urllib.parse
mid = '2026-07-08 11-05-00 Кирилл 1-1'
path = f'Meetings/NewMeetings/{mid} - summary.md'
url = 'obsidian://open?vault=WorkVault&file=' + urllib.parse.quote(path, safe='/')
```

(Либо использовать готовый `obsidian_url` из `MeetingHit`/`MeetingRecord`, если он
уже заполнен в индексе — предпочтительнее ручной сборки.)
