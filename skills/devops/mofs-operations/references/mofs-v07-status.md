# MOFS v0.7.0/v0.8.x — детальный статус + MofsIndex v0.1.0

## Что сделано в сессии 21.07.2026

### Safety (пп. 1–15 плана Opus)
- `--dry-run` для `run`, `rematch`, `edit`, `bootstrap --snapshot`
- Scope enforcement: без явного скоупа → exit 2
- `rematch --all` без `--yes` → показывает N, требует подтверждения
- `--from/--to` фильтр по дате; валидация дат
- Префлайт SCOPE в stderr; `filter_by_date()` в pipeline.py
- `test_dry_run.py` — 11 тестов; `test_manual_edit.py` +1 тест

### Contacts v0.2 (ФИО из тела)
- `text_extractor.py`: `extract_fio_from_body()`, `_extract_section()`, `_is_fio()`
- `matcher_contacts.py`: тело+store вместо participants; логика D2+D3
- `pipeline.py`: ContactStore один раз на run_pipeline
- `config.py`: абсолютный путь к `.env` → cwd-независимость
- `test_matcher_contacts.py`: полностью переписан (13 тестов)

### Contacts v0.2.1 — поддержка bold-формата (v0.8.1)
MoveFromFF генерирует заголовки разделов в двух форматах:
- Markdown: `## Участники:` / `## Задачи:` — 36/61 встреч
- Bold: `**Участники:**` / `**Задачи:**` — 23/61 встреч (Trisigma и др.)

Фикс в `text_extractor.py`:
- Добавлен `_SECTION_BOLD = re.compile(r"^\*\*([^\n*]+?)\*?\*?:?\s*$", re.MULTILINE)`
- `_extract_section` собирает кандидатов обоих форматов, сортирует по позиции
- `_is_fio` и логика разделов не изменились
- Добавлены 2 теста в `test_matcher_contacts.py`: `test_extract_fio_bold_header_participants`, `test_extract_fio_bold_tasks_section`
- **Итого: 110/110 тестов**

При добавлении новых форматов заголовков — расширять `_extract_section`, не дублировать логику.

### date: во frontmatter
- `pipeline.py` — в `process_meeting` после merge корзин: `fm["date"] = m_date.group(1)` (идемпотентно)

### MofsIndex (SQLite+FTS5, реализован 21.07.2026)

**Архитектура:**
```
meetings          -- метаданные + mtime/sha1 для инкремента
meeting_slugs     -- (bucket, slug) с индексом
meetings_fts      -- FTS5 standalone: title + summary_body + transcript_body
meta              -- schema_version, last_full_reindex_at
```

**Отклонения от ТЗ (SQLite 3.34 ограничения):**
1. FTS5 standalone (не `content=meetings`) — external content несовместим с DELETE по meeting_id
2. Тела только в FTS (не дублируются в meetings) — 57 MB vs ~108 MB
3. OR-условия вместо `WHERE (bucket,slug) IN (...)` — row-value syntax не поддерживается
4. ThreadPoolExecutor не добавлен — GIL; 3 транзакции (parse → meetings+slugs → FTS+optimize)

**Замеры (575 встреч):**
| Операция | Результат | Цель |
|---|---|---|
| Full rebuild | 4.9с | <10с ✅ |
| search по slug | 1.69мс | <10мс ✅ |
| search FTS+дата | 20.5мс | <10мс ⚠️ тикет v0.2 |
| get_meeting | 0.91мс | <2мс ✅ |
| Размер БД | 57 MB | <60 MB ✅ |

**Тесты:** MofsIndex 65/65 + MOFS 108/108 (103 + 5 интеграционных)

**Пути:**
```
~/USERTOOLS/MofsIndex/mofs_index/
  db.py, parser.py, indexer.py, searcher.py, cli.py, hooks.py
~/USERTOOLS/MofsIndex/state/index.sqlite  (WAL)
```
Установлен editable в `ProtocolFromSummary/.venv`.

## Статус по корзинам (июль 2026, 61 встреча)

| Корзина | Встреч с данными | Статус |
|---|---|---|
| projects | 61/61 | ✅ |
| tools | 5/61 | ✅ |
| rooms | 10/61 | ✅ |
| contacts | ~30/61 | ✅ v0.8.1 (оба формата) |
| date | 61/61 | ✅ |

## entities.json — полная таблица (19 сущностей)

| slug | kind | display | N (июль) |
|---|---|---|---|
| kirill_1on1 | one_on_one | Кирилл 1-1 | 26 |
| aralov_1on1 | one_on_one | Аралов 1-1 | 23 |
| ai_analitik | project | AI-аналитик | 17 |
| ab_platforma | project | AB-платформа | 12 |
| trisigma | project | Trisigma | 11 |
| zhirov_1on1 | one_on_one | Жиров 1-1 | 11 |
| ml_platforma | project | ML-платформа | 9 |
| omd | tool | OMD (OpenMetaData) | 5 |
| datatalks | multisync | DataTalks | 4 |
| ai_ready | project | AI-ready | 3 |
| ilya_1on1 | one_on_one | Илья 1-1 | 3 |
| parsing | project | Парсинг | 2 |
| vstrechi_pro | multisync | ПРО (гильдия РП) | 2 |
| sink_aid | sync_aid | Синк АиД | 2 |
| metroteka | project | Метротека | 1 |
| cu | project | ЦУ | 1 |
| tsu | unknown | ЦУ неразобранное | 0 |
| devrel | project | DevRel | 0 |
| vstrechi_nerazobrannoe | unknown | неразобранное | 0 |

## Alias tsu — диагностика и фикс (21.07.2026)

**Проблема:** alias `"цу "` (substring + пробел) ложно матчил «страницу», «таблицу» в 8 встречах.

**Фикс:** убрать `"цу "`, оставить только `"цу."` (startswith) → 0 ложных срабатываний.

**Правило:** для 2-3-буквенных кириллических аббревиатур — ТОЛЬКО alias с точкой.
