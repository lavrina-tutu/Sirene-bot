---
tool: MofsIndex
status: active
version: "0.5.1"
date: 2026-08-29
created: 2026-07-21
last-section-added: 2026-07-27 — Индексация ТЗ (таблица docs + docs_fts, скоуп Hermes-Backlog/TZ)
decisions_locked: 2026-07-21 (Q1-Q6 — все приняты Сашей)
depends_on:
  - MarkObjectsFromSummary >= 0.8.0
  - EntityRegistry >= 0.2.0
consumers:
  - skill:workvault-rag
---

# MofsIndex — SQLite/FTS5-индекс размеченных встреч

## 1. Цель

Держать актуальный локальный SQLite-индекс с FTS5 поверх frontmatter и тела пары `summary.md`+`transcript.md` каждой встречи из `WorkVault/Meetings/NewMeetings/`, чтобы скилл `workvault-rag` отвечал на структурные запросы (по 4 корзинам + дата + полный текст) за <10 мс вместо повторного grep/read по 600+ файлам.

## 2. Скоуп и не-скоуп

**В скоупе:**
- Индексация пар `«<meeting_id> - summary.md»` + одноимённого `«<meeting_id> - transcript.md»` в одну запись `meetings`.
- Инкрементальная переиндексация (по mtime+sha1) и полная перестройка (`--rebuild`).
- Read-only Python API для потребителей (`workvault-rag`): `search_meetings`, `get_meeting`, `get_transcript_snippets`.
- Хук автоиндексации в конце `mofs run`, `mofs rematch` (real-mode, не dry-run) и `mofs edit` (одна встреча).

**НЕ в скоупе:**
- Никакого векторного/семантического поиска (qmd retired 2026-07-16 — см. `workvault-rag/references/qmd-retired-2026-07-16.md`).
- Правка `_mark_objects_registry.json` MOFS — только читаем как справочник, никогда не пишем.
- Правка frontmatter/тел `.md` — read-only относительно WorkVault.
- Индексация чего-либо вне `Meetings/NewMeetings/` (Confluence, ТЗ, People — отдельные индексы, если понадобятся).
- Синхронизация с EntityRegistry — slug'и берутся as-is из frontmatter встреч; резолвинг в display_name делается потребителем (workvault-rag) через `entities.json`.

## 3. Место в экосистеме

```
MOFS (mofs run/rematch) ─► frontmatter/*.md + _mark_objects_registry.json
                                    │
                                    ▼
                          MofsIndex.reindex(scope)
                                    │
                                    ▼
                  ~/USERTOOLS/MofsIndex/state/index.sqlite
                                    │
                                    ▼
                     workvault-rag (search_meetings / get_meeting)
```

- **Источник истины:** `.md`-файлы в `NewMeetings/` (frontmatter содержит финальные списки корзин после MOFS v0.6+). Реестр MOFS используем как ускоритель обхода — но при расхождении **frontmatter побеждает**.
- **meeting_id:** имя файла без хвоста ` - summary.md` — тот же ID, что MOFS пишет в реестр и что читает `mofs edit --meeting-id`.
- **Связь summary↔transcript:** детерминированная замена суффикса ` - summary.md` → ` - transcript.md` в том же каталоге; если файла нет — запись всё равно создаётся, `transcript_present=0`.

## 4. Схема БД (SQLite)

Файл: `~/USERTOOLS/MofsIndex/state/index.sqlite` (создаётся при первом запуске; `PRAGMA journal_mode=WAL`).

### 4.1 Таблица `meetings`

| Поле | Тип | Описание |
|---|---|---|
| `meeting_id` | TEXT PRIMARY KEY | `"2026-07-01 07-30-00 Кирилл 1-1"` — имя файла без ` - summary.md` |
| `meeting_date` | TEXT NOT NULL | `YYYY-MM-DD` из имени файла (нормализовано; NULL-запись → skip) |
| `meeting_time` | TEXT | `HH:MM:SS` из имени (может быть NULL если не распознано) |
| `title` | TEXT | Часть имени после `YYYY-MM-DD HH-MM-SS ` (визуальное название встречи) |
| `summary_path` | TEXT NOT NULL | Абсолютный или относительный от WorkVault путь к summary.md |
| `transcript_path` | TEXT | NULL если transcript отсутствует |
| `transcript_present` | INTEGER NOT NULL DEFAULT 0 | 0/1 |
| `summary_mtime` | INTEGER NOT NULL | `os.stat().st_mtime_ns` — для инкрементальной проверки |
| `summary_sha1` | TEXT NOT NULL | sha1 тела summary (без frontmatter) — детектор изменений |
| `transcript_mtime` | INTEGER | mtime транскрипта |
| `transcript_sha1` | TEXT | sha1 транскрипта |
| `objects_version` | TEXT | значение `objects_version` из реестра MOFS (для аудита совместимости) |
| `mofs_status` | TEXT | `ok` / `skipped` / `error` — статус из реестра MOFS для этой встречи |
| `indexed_at` | TEXT NOT NULL | UTC ISO-8601 время последней записи |

### 4.2 Таблица `meeting_slugs` (нормализованная корзина)

| Поле | Тип | Описание |
|---|---|---|
| `meeting_id` | TEXT NOT NULL | FK → meetings.meeting_id, ON DELETE CASCADE |
| `bucket` | TEXT NOT NULL | `projects` \| `tools` \| `rooms` \| `contacts` |
| `slug` | TEXT NOT NULL | `ai_analitik`, `kirill_1on1`, `omd`, ... |
| `display_name` | TEXT | часть после `\|` из wiki-link (кэш; авторитет — entities.json) |

**Индексы:**
- `PRIMARY KEY (meeting_id, bucket, slug)`
- `CREATE INDEX idx_slugs_by_slug ON meeting_slugs(bucket, slug);` — быстрый обратный поиск «все встречи, где slug=X»

### 4.3 FTS5-таблица `meetings_fts`

```sql
CREATE VIRTUAL TABLE meetings_fts USING fts5(
    meeting_id UNINDEXED,
    title,
    summary_body,          -- тело summary.md без frontmatter
    transcript_body,       -- тело transcript.md без header (после '---' сепаратора)
    slugs_flat,            -- 'ai_analitik kirill_1on1 omd' — все slug через пробел, для быстрого фильтра
    tokenize = 'unicode61 remove_diacritics 2'
);
```

Синхронизация `meetings_fts` с `meetings` — вручную в upsert-транзакции (не через триггеры — тело хранится только в FTS, не дублируем в `meetings`).

**Решение по структуре FTS (Q2, 21.07.2026):** в v0.1 держим ровно одну FTS5-таблицу `meetings_fts` с двумя телесными колонками (`summary_body` + `transcript_body`). После первой полной индексации замеряем размер БД; если `meetings_fts` превысит **200 MB** — в v0.2 выделяем `transcript_fts` в отдельную виртуальную таблицу (lazy-attach только при `get_transcript_snippets`). До достижения порога — не усложняем.

### 4.4 Служебная `meta`

`key TEXT PRIMARY KEY, value TEXT` — хранит `schema_version`, `last_full_reindex_at`, `mofs_registry_mtime_at_last_scan`.

**Миграции (Q6, 21.07.2026):** автомиграций нет. На старте любой команды `mofs index ...` сравниваем `schema_version` из `meta` с текущим кодовым значением; при несовпадении — печатаем понятную инструкцию `mofs index --rebuild --yes` и выходим с ненулевым кодом. Данные полностью восстановимы из `.md`, поэтому rebuild безопасен и является штатным путём апгрейда схемы.

## 5. CLI

### 5.1 Основная команда

```
mofs index [--rebuild] [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--meeting-id ID] [--dry-run] [--json]
```

**Флаги:**
- (по умолчанию) — инкрементальный проход по всем summary-файлам в `NewMeetings`; upsert только тех, у которых `summary_mtime` или `summary_sha1` изменились (либо запись отсутствует в БД).
- `--rebuild` — DROP + CREATE всех таблиц и полная переиндексация. Требует подтверждения `--yes` в реальном режиме (аналог `mofs rematch --all --yes`).
- `--from`/`--to` — сузить скоуп прохода по дате в имени файла (та же семантика, что у `mofs run --from/--to`, см. `pipeline.filter_by_date`).
- `--meeting-id` — переиндексировать одну конкретную встречу.
- `--dry-run` — показать план (сколько файлов будет upsert/delete), не трогать БД.
- `--json` — машиночитаемый вывод статистики.

**Пример:**
```
$ mofs index --from 2026-07-01
SCOPE: 42 meetings in [2026-07-01..], mode=real
UPSERT: 3 changed, 39 unchanged, 0 deleted
indexed_at: 2026-07-21T14:22:11Z
```

### 5.2 Интеграция с `mofs run` / `mofs rematch`

- В конце успешного `mofs run` (mode=cron ИЛИ manual) и `mofs rematch` (real, не dry-run) автоматически вызывается `mofs_index.reindex(scope=changed_meeting_ids)` — переиндексируются только те `meeting_id`, что реально обработал pipeline (`stats.processed`).
- Если автоиндексация упала — MOFS печатает WARN в stderr, exit-код от MOFS не меняется (индекс не должен блокировать основной пайплайн). Ошибка логируется в `logs/mofs.md`.
- Отключить хук: env `MOFS_INDEX_AUTO=0` (для отладки).

**Хук в `mofs edit` (Q4, 21.07.2026):** в конце успешного `_cmd_edit` (после записи изменений в frontmatter и `_mark_objects_registry.json`) вызывается `hooks.reindex_meeting(meeting_id)` — точечная переиндексация одной встречи (<50 мс). Та же политика fail-soft: ошибка индекса → WARN в stderr, exit-код `mofs edit` не меняется. Отключается тем же `MOFS_INDEX_AUTO=0`.

**Конкурентный доступ (Q5, 21.07.2026):** `PRAGMA journal_mode=WAL` (см. §4) — единственная защита. Читатели `workvault-rag` не блокируются писателем; писатель у нас один за раз (`single_instance(lock_path)` уже держит `mofs run`, а `mofs edit`/`mofs index` — короткие транзакции). Дополнительных прикладных блокировок не вводим.

### 5.3 Read-only утилиты

```
mofs index stats                  # число записей, размер БД, last_full_reindex_at
mofs index verify                 # найти файлы в NewMeetings без записи в БД и записи в БД без файла
mofs index vacuum                 # VACUUM + optimize для FTS5
```

## 6. Алгоритм индексации (одна встреча)

Вход: `summary_path: Path`.

1. `meeting_id = summary_path.name` без хвоста ` - summary.md` (регэксп совпадает с `pipeline._MEETING_ID_RE`).
2. `meeting_date, meeting_time, title` — распарсить из `meeting_id` регэкспом `^(\d{4}-\d{2}-\d{2}) (\d{2}-\d{2}-\d{2}) (.+)$`. Если не парсится — записать с `meeting_date=NULL` и `mofs_status='error'` (не пропускать молча — потребитель увидит).
3. Прочитать frontmatter (`markobjectsfromsummary.frontmatter.read_frontmatter` — используем как библиотеку, не реализуем заново).
4. Извлечь корзины: для каждой из 4 (`projects/tools/rooms/contacts`) — распарсить список wiki-links `[[slug|display]]` → `(slug, display)`. Резервный формат `[[slug]]` без пайпа — display=slug.
5. Прочитать тело summary (всё после закрывающего `---`).
6. Проверить существование `transcript_path = summary_path.with_name(summary_path.name.replace(' - summary.md', ' - transcript.md'))`. Если есть — прочитать; отрезать header до первого `---` (там служебные строки: Дата/Длительность/Meeting ID); тело = всё после.
7. Посчитать sha1 обоих тел, взять mtime_ns.
8. Из реестра MOFS (`_mark_objects_registry.json`, читается один раз в начале прохода) вытащить `objects_version` и `status` для этого `meeting_id`. Если записи нет — `mofs_status='unmarked'`.
9. Открыть транзакцию:
   - `INSERT OR REPLACE INTO meetings(...)`;
   - `DELETE FROM meeting_slugs WHERE meeting_id=?; INSERT ... (batch)`;
   - `DELETE FROM meetings_fts WHERE meeting_id=?; INSERT INTO meetings_fts(...)`.
10. Commit.

**Проход по всем:**
- `iter_summary_files(new_meetings_path)` — те же файлы, что видит MOFS. Скоуп индексации жёстко привязан к наличию `summary.md`: **встреча без summary не индексируется** (Q3, 21.07.2026) — симметрично поведению MOFS. Одиночные транскрипты без пары игнорируются.
- Инкремент: сравнить (`summary_mtime`, `transcript_mtime`) с БД; если оба совпадают — skip. Sha1 считаем только когда mtime разошёлся (дёшево при холодном ходе).
- Удаления: в конце прохода `SELECT meeting_id, summary_path FROM meetings WHERE summary_path` отсутствует на диске → `DELETE`. Только при полном проходе без `--from/--to/--meeting-id`.

**Хук в `_cmd_edit` (Q4):** после успешного применения `--add/--remove/--set` вызвать `mofs_index.hooks.reindex_meeting(meeting_id)` — обёртка над `process_meeting(summary_path)` с fail-soft (см. §5.2). Не в транзакции `edit` — уже после её commit, чтобы падение индекса не откатывало правку frontmatter.

## 7. Read-only API для `workvault-rag`

Модуль `mofs_index.query`:

```python
def search_meetings(
    query: str | None = None,        # FTS5 MATCH по summary_body+transcript_body+title
    date_from: str | None = None,    # 'YYYY-MM-DD' включительно
    date_to: str | None = None,
    slugs: dict[str, list[str]] | None = None,  # {'projects':['ai_analitik'], 'contacts':['aralov']}
    slug_mode: str = 'any',          # 'any' | 'all'
    limit: int = 50,
    order: str = 'date_desc',        # 'date_desc' | 'date_asc' | 'relevance'
) -> list[MeetingHit]:
    ...

def get_meeting(meeting_id: str) -> MeetingRecord | None:
    """Полная карточка: пути, все slugs по 4 корзинам, mtime, sha1, objects_version."""

def get_transcript_snippets(
    meeting_id: str,
    query: str,
    max_snippets: int = 5,
    window: int = 40,                # слов вокруг матча
) -> list[str]:
    """Использует FTS5 snippet() по transcript_body конкретной встречи."""

def list_slugs(bucket: str) -> list[tuple[str, int]]:
    """('ai_analitik', 42) — сколько встреч упоминают slug. Для автодополнения в скилле."""
```

**`MeetingHit`:** `meeting_id, meeting_date, title, summary_path, transcript_present, matched_slugs, rank`.

**Порядок фильтров внутри `search_meetings`:**
1. Дата (SQL WHERE по `meeting_date` — использует индекс).
2. Slugs (JOIN на `meeting_slugs`, GROUP BY meeting_id, HAVING count = требуемое при slug_mode='all').
3. FTS MATCH по `meetings_fts` (JOIN по meeting_id).
4. ORDER + LIMIT.

Это тот же 4-шаговый алгоритм, что описан в `workvault-rag/SKILL.md` (шаги «период → участники → проект → извлечение сущностей»), только выполняется в SQL за один запрос.

## 8. Производительность (целевые показатели)

Профиль масштаба: ~600 пар summary+transcript, средний summary ~5 KB, transcript ~30 KB → ~20 MB сырого текста; ожидаемый размер БД <60 MB.

| Операция | Цель | Комментарий |
|---|---|---|
| Полная перестройка (`--rebuild`) на 600 встречах | <10 с | однопоточно, sha1+FTS5 tokenize |
| Инкрементальный проход, 0 изменений | <500 мс | только stat() всех файлов + сравнение mtime |
| Инкрементальный проход, 5 изменённых встреч | <1 с | |
| `search_meetings` (дата + 1 slug + FTS query, top-50) | <10 мс | горячий кэш ОС |
| `search_meetings` (только дата + slug) | <5 мс | |
| `get_meeting(meeting_id)` | <2 мс | PK lookup |
| `get_transcript_snippets` | <15 мс | одна FTS-строка, snippet() |

Тесты производительности — на реальном срезе (или его копии); если цели не достигнуты — фиксируем регресс в отдельном тикете.

**Ориентир для разделения FTS (Q2, 21.07.2026):** после первой полной индексации замерить размер файла БД и размер FTS-сегментов (`dbstat`/`sqlite_stat`). Пороговое значение для разделения `meetings_fts` на `summary_fts` + `transcript_fts` в v0.2 — **>200 MB** суммарного размера FTS-структур. Пока меньше — не трогаем.

## 9. Место в файловой системе

```
~/USERTOOLS/MofsIndex/
├── mofs_index/                    # Python-пакет
│   ├── __init__.py
│   ├── schema.py                  # DDL + миграции
│   ├── indexer.py                 # reindex(scope), process_meeting()
│   ├── query.py                   # search_meetings / get_meeting / ...
│   ├── cli.py                     # `mofs index ...` (entry-point)
│   └── hooks.py                   # интеграция с mofs run/rematch
├── state/
│   └── index.sqlite               # sqlite + WAL
├── tests/
├── pyproject.toml
└── README.md
```

- Entry-point в `pyproject.toml`: `mofs-index = mofs_index.cli:main` — плюс регистрация подкоманды в `markobjectsfromsummary.cli` (`mofs index ...`) через тонкий shim, импортирующий `mofs_index.cli`.
- Общий venv с MOFS/PFS/TaskRefresh/EntityRegistryCLI (тот же паттерн, что EntityRegistryCLI).
- Ни один файл индекса не лежит в `WorkVault/` — БД это runtime-state MOFS-семейства, её место в `USERTOOLS/MofsIndex/state/`.

## 10. Что НЕ трогает

- `_mark_objects_registry.json` — только чтение.
- `entities.json` — вообще не читает (резолвинг display_name делает потребитель).
- Frontmatter `.md`-файлов — только чтение.
- CLI существующих команд MOFS (`run`/`rematch`/`edit`/...) — только новый подкомманд `index` и хуки в конце run/rematch/edit (fail-soft, exit-код не меняют). Никаких изменений семантики существующих флагов.
- Работу `workvault-rag` со файловым фолбэком — скилл продолжает уметь работать без индекса (fallback на search_files, если БД недоступна или устарела).

## 11. Решения брифа (21.07.2026)

Все шесть открытых вопросов первичного драфта закрыты Сашей на брифе 21.07.2026. Ниже — принятые решения (детали интегрированы в §4-§8):

1. **Q1. Участники из тела summary отдельным полем — НЕТ (не в v0.1).** FTS по `summary_body` даёт полнотекстовый поиск по именам; отдельная нормализованная колонка появится только когда возникнет структурный запрос «встречи с N участниками».
2. **Q2. FTS-структура — одна таблица `meetings_fts` с двумя колонками (`summary_body`, `transcript_body`) в v0.1.** После первой полной индексации замеряем размер; порог для разделения на `summary_fts`+`transcript_fts` в v0.2 — **>200 MB**.
3. **Q3. Встреча без summary — НЕ индексируется.** Скоуп жёстко привязан к `iter_summary_files`; одиночные транскрипты игнорируются (симметрично MOFS).
4. **Q4. Хук в `mofs edit` — ДА.** В конце успешного `_cmd_edit` вызывается `hooks.reindex_meeting(meeting_id)`, fail-soft, отключается `MOFS_INDEX_AUTO=0`.
5. **Q5. Конкурентный доступ — WAL-режим SQLite, дополнительных прикладных блокировок нет.** Читатели `workvault-rag` не блокируются писателем; writer один за раз через `single_instance(lock_path)` в `mofs run`.
6. **Q6. Миграции схемы — только через `mofs index --rebuild --yes`, автомиграций нет.** `schema_version` в `meta`; при несовпадении — понятная инструкция и ненулевой exit. Данные восстановимы из `.md`.

## 12. Тесты (что покрыть)

Единицы:
- Парсинг `meeting_id` → `(date, time, title)` для валидных/невалидных имён.
- Парсинг frontmatter с 4 корзинами (`projects/tools/rooms/contacts`), включая пустые списки, `null`, и wiki-link без пайпа.
- Извлечение тела: корректное отсечение frontmatter (`---...---`) и transcript-header (первый `---` после метаданных).
- sha1/mtime-инкрементальность: измени файл — попадёт в скоуп; не менял — не попадёт.
- Обработка отсутствующего transcript (`transcript_present=0`, `transcript_path=NULL`).
- Отражение реестра MOFS (`mofs_status`, `objects_version`) — включая `unmarked` для встречи, отсутствующей в реестре.

Интеграция:
- `--rebuild` на фикстуре из 5 встреч (2 с транскриптом, 1 без summary, 1 битый frontmatter, 1 полноценная) → таблицы содержат ровно ожидаемые записи.
- `--from/--to` — сужение работает и для upsert, и для detect-deletions (deletion работает только на полном проходе).
- Инкрементальный проход после мутации одного summary → обновляется ровно 1 запись.
- Хук в конце `mofs run` (mock pipeline) вызывает reindex ровно с processed meeting_ids.
- Failing hook не роняет `mofs run` (proc возвращает 0, но stderr содержит WARN).

Query API:
- `search_meetings(slugs={'projects':['ai_analitik']})` возвращает те же встречи, что видит `mofs review --bucket projects --slug ai_analitik`.
- `search_meetings(query='DWH', date_from='2026-06-01')` работает (FTS+дата).
- `slug_mode='all'` для двух slug'ов даёт пересечение, `'any'` — объединение.
- `get_transcript_snippets` возвращает не пустой список при явном матче в транскрипте.
- Отсутствие БД / устаревшая схема → чистая ошибка с подсказкой `--rebuild`, а не Traceback.

Производительность (smoke):
- На фикстуре в 200 сгенерированных пар summary+transcript — полная перестройка укладывается в 5 с, `search_meetings` c FTS < 20 мс (на CI-железе; в проде — быстрее).

## 13. Совместимость и версии

- Python ≥ 3.11 (как остальная MOFS-семья).
- SQLite ≥ 3.34 (FTS5 включён по умолчанию в `sqlite3` из стандартной библиотеки Python на RHEL 9 — проверить в `mofs index verify`).
- `schema_version = 1` в v0.1.0. Любой breaking change схемы → бамп minor + инструкция `--rebuild`.

## 14. Что дальше (не входит в v0.1)

- **v0.2 — оптимизация `search_meetings(FTS+дата)`**: замер 21.07.2026 показал 20.5 мс при цели <10 мс на 575 встречах. Причина: FTS-строка сейчас содержит только `slugs_flat` без раздельной колонки для дат, поэтому фильтр по `meeting_date` идёт через JOIN на `meetings`, а не через FTS-предикат. План: добавить `date_bucket` (например, `YYYY-MM`) в FTS5 как отдельную индексированную колонку, чтобы `MATCH 'date_bucket:2026-07*'` отсекал документы до FTS-скана тела. Ожидание: <10 мс.
- Индексация ТЗ (`Hermes-Backlog/TZ/**/*.md`) отдельной таблицей `docs` в той же БД — потенциальная замена файлового поиска в `workvault-rag` по ТЗ.
- Экспорт агрегатов в Telegram-бот (`/last_meetings_by_slug X`).
- Мониторинг рассинхронизаций frontmatter vs `_mark_objects_registry.json` (сейчас реестр считается вторичным; при расхождениях — WARN в `mofs index verify`).

## 15. Результаты реализации v0.1.0 (21.07.2026) — РЕАЛИЗОВАНО

Версия v0.1.0 реализована Sonnet 21.07.2026, все целевые показатели производительности достигнуты (кроме одного, вынесенного в v0.2). Тесты зелёные.

### 15.1 Место установки

- **Пакет:** `/home/tkachenkoav/USERTOOLS/MofsIndex/`
- **Venv (общий с MOFS-семьёй):** `/home/tkachenkoav/USERTOOLS/ProtocolFromSummary/.venv`
- **БД:** `/home/tkachenkoav/USERTOOLS/MofsIndex/state/index.sqlite` (WAL)

### 15.2 Тесты

- **MofsIndex (unit + integration + API):** 65/65 ✅
- **MOFS с интеграционными хуками (`run`/`rematch`/`edit`):** 108/108 ✅

### 15.3 Замеры производительности (реальные данные, 575 встреч)

| Операция | Цель | Факт | Статус |
|---|---|---|---|
| Full rebuild | <10 с | 4.9 с | ✅ |
| `search_meetings(slug)` | <5 мс | 1.69 мс | ✅ |
| `search_meetings(FTS + date)` | <10 мс | 20.5 мс | ⚠️ → v0.2 (см. §14) |
| `get_meeting(id)` | <2 мс | 0.91 мс | ✅ |
| Размер БД после `vacuum` | <60 MB | 57 MB | ✅ |

### 15.4 Архитектурные отклонения от исходного ТЗ (обоснование)

1. **FTS5 standalone вместо `content=meetings` (external content).**
   ТЗ §4.3 предполагал возможность связи FTS через external content. На практике `content=meetings` в SQLite несовместим с поадресным `DELETE FROM meetings_fts WHERE meeting_id=?` в upsert-транзакции (external-content FTS требует триггеров или полного пересчёта rowid). Решение: FTS5 standalone, синхронизируется вручную в той же транзакции, что описано в §4.3 (пункт «Синхронизация … вручную в upsert-транзакции») — то есть отклонение только по флагу `content=`, семантика сохранена.

2. **Поля `summary_body` / `transcript_body` удалены из таблицы `meetings`.**
   Первоначальная схема §4.1 не декларировала эти поля в `meetings`, но в ходе реализации возник соблазн держать тела в обеих таблицах для read-only утилит. Замер показал дублирование ~45 MB на 575 встречах. Решение: тела живут **только** в `meetings_fts`; при необходимости получить сырое тело — читаем `.md` по `summary_path` (быстрее и без дубля). Влияние на API: `get_meeting` возвращает пути, не тела; `get_transcript_snippets` работает через `snippet()` FTS — как и заложено в §7.

3. **Фильтр `WHERE (bucket, slug) IN ((...), (...))` заменён на набор OR-условий.**
   Row-value syntax `(a,b) IN ((x,y), (z,w))` не поддерживается SQLite 3.34 (RHEL 9 системный sqlite). Решение: генерируем `((bucket=? AND slug=?) OR (bucket=? AND slug=?) OR …)` с параметризацией. Функционально идентично, index `idx_slugs_by_slug(bucket, slug)` используется корректно.

4. **Параллельный парсинг (ThreadPoolExecutor) не добавлен.**
   Обсуждалось для ускорения full rebuild. На практике: python-парсинг frontmatter+тела упирается в GIL, sha1 короткий, узкое место — не CPU, а FTS5 tokenize внутри SQLite (однопоточный). Реальное ускорение full rebuild достигнуто разбиением на 3 транзакции (`meetings` → `meeting_slugs` → `meetings_fts`) с одним `commit` на batch: 4.9 с укладываются в цель <10 с с запасом × 2. Параллелизация принесла бы <10 % при вдвое большей сложности кода — отклонили.

### 15.5 Итог по §11 (решения брифа Q1-Q6)

Все шесть решений исполнены без отклонений: одна FTS5-таблица с двумя колонками, встреча без summary не индексируется, хук в `mofs edit` есть, WAL, миграции через `--rebuild`. Порог 200 MB для v0.2-разделения FTS **не достигнут** (57 MB на 575 встреч) — раздельная `transcript_fts` в v0.2 **не нужна**, вместо неё в v0.2 идёт оптимизация `date_bucket` в FTS (см. §14).

## Доработка: fix editable install (22.07.2026) — РЕАЛИЗОВАНО

**Проблема.** `pyproject.toml` использовал `[tool.setuptools.packages.find]` — setuptools при editable-install регистрировал `mofs_index` как **namespace package** (PEP 420). Следствие: `__init__.py` НЕ выполнялся, реэкспорт публичного API отсутствовал, а `from mofs_index import search_meetings` падал с `ImportError: cannot import name 'search_meetings' from 'mofs_index'`. Проявилось в скилле `workvault-rag` и во всех вызовах API из хука MOFS `reindex_batch`.

**Фикс.** В `pyproject.toml` заменить namespace-эвристику на явный список пакетов:

```toml
[tool.setuptools]
packages = ["mofs_index"]
```

(секция `[tool.setuptools.packages.find]` полностью удалена).

**Применение фикса.**

```bash
pip uninstall -y mofs-index
pip install -e /home/tkachenkoav/USERTOOLS/MofsIndex
```

**Проверка.**

```bash
python3 -c "from mofs_index import search_meetings; print('OK')"
# → OK
```

После фикса `mofs_index` — обычный regular-пакет, `__init__.py` выполняется, все реэкспорты доступны, хук `reindex_batch` в MOFS работает без sys.path-костылей (см. п.3 доработки MOFS 22.07.2026 — скилл `workvault-rag` v2.3, `sys.path` workaround удалён).

## Доработка: Индексация ТЗ (v0.5, 2026-07-27)

### Ц.1 Цель

Дать `backlog_analyst.py` и `workvault-rag` быстрый полнотекстовый поиск по документам ТЗ в `Hermes-Backlog/TZ/**/` через FTS5 — чтобы косвенные связи вида «bk-задача про ownCloud FileNameTooLong ↔ `MoveFromFF_TZ.md`» находились одним SQL-запросом, а не grep-обходом всего каталога.

### Ц.2 Новая таблица `docs`

Файл БД — тот же `~/USERTOOLS/MofsIndex/state/index.sqlite` (не отдельная БД: те же WAL, тот же процесс индексации, тот же venv).

```sql
CREATE TABLE docs (
    doc_id       TEXT PRIMARY KEY,   -- относительный путь от WorkVault, напр. 'Hermes-Backlog/TZ/MofsIndex/MofsIndex_TZ.md'
    doc_type     TEXT NOT NULL,      -- 'tz' в v0.5; зарезервировано под 'impl_plan', 'brief', 'appendix', ...
    title        TEXT,               -- из H1 файла (первая строка вида '# ...'); fallback — имя файла без .md
    tool_name    TEXT,               -- frontmatter tool: (может быть NULL)
    status       TEXT,               -- frontmatter status: (active/draft/archived/...)
    version      TEXT,               -- frontmatter version: (строкой, как в исходнике)
    mtime        INTEGER NOT NULL,   -- os.stat().st_mtime_ns
    sha1         TEXT NOT NULL,      -- sha1 тела без frontmatter — детектор изменений
    indexed_at   TEXT NOT NULL       -- UTC ISO-8601
);
CREATE INDEX idx_docs_by_tool   ON docs(tool_name);
CREATE INDEX idx_docs_by_type   ON docs(doc_type);
```

Тело документа в самой `docs` **не хранится** — живёт только в FTS5 (тот же приём, что для `meetings`, см. §15.4.2). Для сырого текста читаем `.md` по `doc_id`.

### Ц.3 FTS5-таблица `docs_fts`

```sql
CREATE VIRTUAL TABLE docs_fts USING fts5(
    doc_id UNINDEXED,
    title,
    body,                              -- полный текст .md без frontmatter
    tokenize = 'unicode61 remove_diacritics 2'
);
```

Синхронизация с `docs` — вручную в upsert-транзакции, как и для `meetings_fts` (см. §15.4.1 — standalone FTS, не external content).

### Ц.4 Скоуп индексации

- Корень: `~/WorkVault/Hermes-Backlog/TZ/`
- Включаются файлы, соответствующие glob'ам:
  - `**/*_TZ.md` — основные ТЗ (`doc_type='tz'`)
  - `**/*_impl_plan.md` — планы имплементации (`doc_type='impl_plan'`)
- **Исключаются:** `appendix_*.md`, `*_brief.md`, `MAIN_TZ_INVENTORY.md`, любые файлы вне `TZ/` (например, `Hermes-Backlog/Ideas/`, `Hermes-Backlog/Sasha_bklog.md`).
- Скрытые каталоги (`.git`, `.obsidian`) — пропускаются.

Символьный (не строгий) фильтр реализуется в `docs_indexer.iter_doc_files()` — единственная точка правды по скоупу; расширение на новые типы = добавить glob + маппинг в `doc_type`.

### Ц.5 CLI

Отдельная подкоманда, симметричная `mofs index`:

```
mofs index docs [--rebuild] [--dry-run] [--json]
```

**Флаги:**
- (по умолчанию) — инкрементальный проход: сравнивает `mtime`/`sha1` со строкой в `docs`, upsert только изменённых.
- `--rebuild` — `DROP TABLE docs; DROP TABLE docs_fts;` + полная переиндексация. Требует `--yes` в реальном режиме.
- `--dry-run` — план (сколько upsert/delete), БД не трогается.
- `--json` — машиночитаемая статистика.

**Пример вывода:**
```
$ mofs index docs
SCOPE: 14 docs in Hermes-Backlog/TZ, mode=real
UPSERT: 2 changed, 12 unchanged, 0 deleted
indexed_at: 2026-07-27T09:14:03Z
```

**Хуки:** автохуков нет (в отличие от `meetings`, которые тянутся за `mofs run/rematch/edit`). ТЗ правятся руками и редко; кроны не создаём (Саша не просил). Ре­индексация — по явному вызову `mofs index docs`.

### Ц.6 Python API

Модуль `mofs_index.query` пополняется:

```python
from dataclasses import dataclass

@dataclass
class DocHit:
    doc_id: str
    doc_type: str
    title: str | None
    tool_name: str | None
    status: str | None
    version: str | None
    rank: float                # FTS5 bm25 rank
    snippet: str               # snippet() из body, ~40 слов вокруг матча

def search_docs(
    query: str,                          # FTS5 MATCH-выражение по title+body
    doc_type: str | None = None,         # 'tz' / 'impl_plan' / None (все)
    tool_name: str | None = None,        # точный фильтр по frontmatter tool:
    limit: int = 20,
) -> list[DocHit]:
    ...

def get_doc(doc_id: str) -> dict | None:
    """Полная карточка (метаданные, без body). Body — читать .md по doc_id."""
```

Read-only, как и `search_meetings`. Устаревшая схема / отсутствие таблицы `docs` → чистая ошибка с подсказкой `mofs index docs --rebuild --yes`.

### Ц.7 Интеграция с `backlog_analyst.py`

Расположение: `~/USERTOOLS/DialogBacklog/backlog_analyst.py`.

**До (файловый поиск):** при обработке bk-задачи с формулировкой «доработать X» скрипт делал `search_files`/`rg` по `Hermes-Backlog/TZ/` — линейно, без ранжирования, без нормализации диакритики, дублирующе на каждый прогон.

**После (через `search_docs`):**

```python
from mofs_index import search_docs

def find_related_tz(bk_task_text: str, keywords: list[str]) -> list[DocHit]:
    # Ключевые слова уже извлечены анализатором (существующая логика — не трогаем).
    fts_query = " OR ".join(f'"{kw}"' for kw in keywords if kw)
    if not fts_query:
        return []
    return search_docs(fts_query, doc_type="tz", limit=5)
```

Результат `find_related_tz` используется анализатором как «кандидаты для косвенной связи» — прикрепляется к отчёту bk-анализа как список `(tool_name, doc_id, rank, snippet)`, окончательное решение о связывании остаётся за Сашей / за более высоким слоем.

**Fallback:** если `search_docs` бросает исключение (нет БД, старая схема) — `backlog_analyst.py` логирует WARN и возвращается к старому файловому поиску (симметрично политике fail-soft `workvault-rag`).

### Ц.8 Что НЕ трогаем

- Таблицы `meetings`, `meeting_slugs`, `meetings_fts`, `meta` — вообще не меняются. Схема `docs`/`docs_fts` живёт рядом.
- Существующий API (`search_meetings`, `get_meeting`, `get_transcript_snippets`, `list_slugs`) — без изменений.
- Подкоманда `mofs index` (без `docs`) — прежняя семантика, прежние флаги, прежние хуки.
- Frontmatter `.md`-файлов ТЗ — только чтение, никогда не пишем.
- `MAIN_TZ_INVENTORY.md` — не индексируется автоматически (это оглавление, не документ; при желании добавить — отдельный `doc_type='inventory'` в будущем).
- Кроны — не создаём. Ре­индексация docs — ручным `mofs index docs`.

### Ц.9 Связи с экосистемой

```
Hermes-Backlog/TZ/**/*_TZ.md ─►  mofs index docs
                                        │
                                        ▼
                          index.sqlite: docs + docs_fts
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
                backlog_analyst.py            workvault-rag
                (search_docs как             (доп. источник поиска
                 замена grep по ТЗ)           по документам)
```

- **Источник истины:** `.md`-файлы ТЗ (frontmatter + тело). Индекс — производный, восстановим `--rebuild`.
- **Общая БД с `meetings`:** одна и та же `index.sqlite`, один WAL, один процесс-писатель за раз. Отдельный DDL для `docs`/`docs_fts` не конфликтует с `meetings`.
- **`workvault-rag`:** получает `search_docs` в свой набор инструментов вторым источником рядом с `search_meetings`. Скилл может вызывать оба параллельно, если запрос неоднозначен («был ли митинг про X + есть ли ТЗ про X»).
- **`schema_version`:** бампается до `2` в `meta` (добавлены `docs`, `docs_fts`, индексы). При старом `schema_version=1` — стандартное сообщение и `--rebuild --yes` (миграция как в §4.4/Q6).

### Ц.10 Решения брифа (2026-07-27)

Три открытых вопроса первичного драфта v0.5 закрыты Сашей на брифе 2026-07-27. Решения интегрированы в §Ц.4-§Ц.6 выше; здесь — сводка и обоснование.

1. **Impl_plan индексировать в v0.5 — ДА.**
   `*_TZ.md` → `doc_type='tz'`, `*_impl_plan.md` → `doc_type='impl_plan'`. Оба типа попадают в БД при `mofs index docs`. Дефолтный `search_docs(doc_type=None)` ищет по обоим типам, что удобно для `workvault-rag`. `backlog_analyst.find_related_tz()` вызывает `search_docs(...)` **без ограничения по типу** — impl_plan часто содержит ссылки на смежные ТЗ и полезен как источник контекста. Опт-аут: явно `doc_type='tz'` в вызове. Риск шума признан приемлемым: impl_plan-файлов сейчас 2 из 24, вклад в rank незначителен.

2. **Weight-boost для матчей в `title` — отложен на v0.5.1.**
   В v0.5 используется стандартный BM25 (`bm25(docs_fts)` без весов). Гипотеза «title×10, body×1» проверяется после накопления реальных запросов от `backlog_analyst` (нужно ≥50 прогонов на живых bk-задачах, чтобы отделить сигнал от шума). Если по данным этих прогонов BM25 будет давать релевантный результат ≥ 80 % случаев — веса не вводим.

3. **Prune «висящих» записей при переименовании — отложен на v0.5.1.**
   `doc_id` = относительный путь. Переименование файла оставляет старую запись в БД до следующего полного прохода `mofs index docs` без фильтров — тогда работает штатный detect-deletions (см. §6). В v0.5 отдельного `--prune` не делаем: (а) переименования ТЗ редки, (б) `--rebuild --yes` — быстро (`<1 с` на 24 файла) и полностью решает вопрос. Мёртвые записи не мешают поиску — они не попадают в верх выдачи, если файла нет.

### Ц.11 Открытые пункты v0.5.1

Кандидаты для следующего минора (по мере накопления данных):

- Weight-boost BM25 в title при подтверждённом снижении релевантности.
- `mofs index docs --prune` без полного rebuild — если переименования участятся.
- Разделение `docs_fts` на отдельные `tz_fts` / `impl_plan_fts` — если impl_plan шумит.

## Контракты экосистемы

### Источник истины
- Владелец записи: MofsIndex (`state/index.sqlite`, ключи — `meeting_id`, `doc_id`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| objects_version | str | optional | MarkObjectsFromSummary (`_mark_objects_registry.json`) | версия объекта из `json:mark_objects_registry` |
| status | str | optional | MarkObjectsFromSummary (`_mark_objects_registry.json`) | статус встречи из `json:mark_objects_registry` |
| bucket | enum[projects, tools, rooms, contacts] | required | MarkObjectsFromSummary (frontmatter встречи) | 4 корзины MOFS |
| slug | str | required | MarkObjectsFromSummary (frontmatter встречи) | slug из wiki-link `[[slug\|display]]` |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| meeting_id | str | workvault-rag | ID встречи (имя файла без суффикса), `sqlite:mofs_index_v1` |
| meeting_date | str | workvault-rag | YYYY-MM-DD |
| title | str | workvault-rag | название встречи |
| summary_path | str | workvault-rag | путь к summary.md |
| transcript_present | int | workvault-rag | 0 или 1 |
| doc_id | str | DialogBacklog (`backlog_analyst.py`), workvault-rag | путь к ТЗ относительно WorkVault |
| doc_type | enum[tz, impl_plan] | DialogBacklog (`backlog_analyst.py`), workvault-rag | тип документа ТЗ |
| snippet | str | DialogBacklog (`backlog_analyst.py`), workvault-rag | FTS5 snippet (~40 слов вокруг матча) |

### Зависимости
- Получает от: [MarkObjectsFromSummary]
- Отдаёт: [DialogBacklog, workvault-rag]

### Breaking changes policy
- Версионирование формата: `schema_version` в служебной таблице `meta` в `index.sqlite` (сейчас version 2)
- При breaking change схемы БД: `schema_version` бампается, потребители пересоздают индекс через `mofs index --rebuild --yes` или `mofs index docs --rebuild --yes`

### Границы («что НЕ трогать»)
- Не модифицировать `_mark_objects_registry.json` (только чтение)
- Не изменять frontmatter и файлы `.md` в `WorkVault/Meetings/` и `Hermes-Backlog/TZ/` (read-only)
- Не создавать автоматические кроны (индексация ТЗ по явному вызову `mofs index docs`)

