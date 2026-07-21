# MOFS v0.7.0 — детальный статус (21.07.2026)

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
- **Итого: 101/101 тестов**

### Прочее
- `README.md` переписан, ТЗ → v0.7.0, инвентарь обновлён
- `tsu` alias: убран `"цу "`, оставлен `"цу."` (startswith)
- `.env` симлинк: `~/USERTOOLS/MarkObjectsFromSummary/.env` → `~/USERTOOLS/AnywhereContacts/.env`

## Реализованные изменения v0.7.0 (Safety — детально)

**pipeline.py:**
- `run_pipeline(dry_run, date_from, date_to)` — при dry_run не пишет файлы и реестр,
  возвращает `(stats, plan)` где `plan` = список `{meeting_id, would_add, cards_to_create}`
- `process_meeting(dry_run)` — при dry_run пропускает `write_frontmatter` и `card_writer`
- `filter_by_date(files, date_from, date_to)` — фильтрация по дате в имени файла

**cli.py:**
- `mofs run`: `--dry-run`, `--from`, `--to`, `--meeting-id`, `--all`
  safeguard: без скоупа в ручном режиме → exit 2 (кроме --mode=cron)
  префлайт `SCOPE: N meetings, bucket=X, mode=dry-run|real` в stderr
- `mofs rematch`: `--dry-run`, `--from`, `--to`, `--yes`
  safeguard: без скоупа → exit 2; `--all` без `--yes` → показывает N, требует подтверждения
  dry-run не снимает снапшот
- `mofs edit`: `--dry-run` — валидация без записи
- `mofs bootstrap --snapshot --dry-run` — план снапшота без создания файла
- `_validate_date_flags()` — валидация YYYY-MM-DD и to >= from

**manual_edit.py:**
- `add_entry(dry_run)` — при True: валидация + план, без записи
- `remove_entry(dry_run)` — то же

## Статус по корзинам (июль 2026, 60 встреч)

| Корзина | Встреч с данными | Уникальных | Статус |
|---|---|---|---|
| projects | 60/60 | 15 | ✅ реальный прогон выполнен |
| tools | 5/60 | 1 (omd) | ✅ |
| rooms | 10/60 | 6 | ✅ |
| contacts | 28/60 (dry-run) | ~80+ | ⏳ ждёт `rematch --bucket contacts` |

## Следующие шаги

1. `mofs rematch --bucket contacts --from 2026-07-01 --to 2026-07-31 --yes`
2. Саша проверяет в Obsidian (Properties + Graph view)
3. NER-прогон по архиву на Haiku → пополнение entities.json
4. Крон mofs_daily — только после «ок» от Саши

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
| cu | project | ЦУ (Central University) | 1 |
| tsu | unknown | ЦУ → неразобранное | 0 |
| devrel | project | DevRel | 0 |
| vstrechi_nerazobrannoe | unknown | Встречи — неразобранное | 0 |

## Alias tsu — диагностика и фикс (21.07.2026)

**Проблема:** alias `"цу "` (substring + пробел) ложно матчил
«страницу», «таблицу» в 8 встречах июля.

**Диагностика:**
```bash
grep -oi ".{0,20}цу.{0,20}" "path/to/summary.md"
# показал: "страницу" и "таблицу" — окончания слов, не аббревиатура
```

**Фикс:**
```bash
entity-registry edit tsu aliases "цу " --remove-item -y
# оставить только "цу." (startswith)
```

**Результат:** 0 ложных срабатываний на 60 встречах июля.

**Правило:** для 2-3-буквенных кириллических аббревиатур — ТОЛЬКО alias с точкой.
Substring слишком широк для коротких слов.
