

# Material moved from MOFS SKILL.md

> История исходника (даты указаны внутри), не текущая инструкция; актуальные условия — в SKILL.md.

## Contacts — архитектура v0.2 (реализована 21.07.2026)

**Принцип:** все 4 корзины ищутся только в ТЕЛЕ summary, не во frontmatter.
Contacts — ФИО из разделов `## Участники:` и `## Задачи:`.

**Файлы:**
- `text_extractor.py` — `extract_fio_from_body(body)` + `_extract_section()` + `_is_fio()`
- `matcher_contacts.py` — `resolve_contacts(body, store, logger)` (D2+D3 логика)
- `pipeline.py` — ContactStore открывается один раз в `run_pipeline`, передаётся вниз

**Логика неоднозначности:**
- 1 результат `find_contacts` → match
- 0 результатов → unmatched_candidates
- >1 результата + 2+ слова → unmatched + WARN в лог
- >1 результата + 1 слово → unmatched (без WARN, ожидаемо)

**_is_fio валидатор:** 2–3 слова, каждое с заглавной кириллицы, допускает дефисы.
Отсекает однословные («Саванна»), фразы, латиницу, email.

**ContactStore:** открывать ОДИН РАЗ в `run_pipeline`, передавать в `process_meeting`.
НЕ открывать на каждую встречу — store кэширует расшифровку в памяти.

**`.env` и ключ шифрования:** прописан абсолютный путь в `config.py`:
```python
env_file=str(Path(__file__).parent.parent / ".env")
```
Симлинк `.env` → `~/USERTOOLS/AnywhereContacts/.env`. Работает из любого cwd.

## NER-backfill contacts по старому архиву (ТЗ готово 22.07.2026)

94% встреч до июля 2026 (~494 файла) — формат MoveFromFF без раздела «Участники». Contacts нельзя извлечь regex-ом — нужен NER.

**Решение:** подкоманда `mofs backfill-contacts` (ТЗ: `appendix_ner_archive_contacts_TZ.md`):
- **S1** (regex email-header транскрипта) → ~85% встреч бесплатно, точность 99%
- **S2** (regex спикер-метки) → +5–10%
- **S3** (Haiku по телу summary) → остаток ~150 файлов, $0.5

**Confidence:** `--min-confidence 0.90` первый прогон, потом 0.80.
**Неизвестные:** в `unmatched_candidates.json`, не в contacts.enc.
**Периодичность:** только ручной запуск (не крон).

## matcher_contacts — известные ограничения (диагностировано 23.07.2026)

**Пропущенные контакты несмотря на наличие в contacts.enc:**

| Причина | Пример | Статус |
|---|---|---|
| Порядок «Имя Фамилия» вместо «Фамилия Имя» | «Никита Лысенко» → `lysenko` не находится | ТЗ в MarkObjectsFromSummary_TZ.md v0.9.1 |
| Уменьшительное имя | «Лёша Белов» → Белов Алексей не матчится | Там же |
| Ambiguous (5 однофамильцев) | «Алексей Белов» → 5 совпадений → `contacts_ambiguous` | Ожидаемо по дизайну |
| Одно слово | «Арут», «Качанов» в разделе Блокеры | Ожидаемо — `_is_fio` требует 2-3 слова |

**Диагностика:** `mofs rematch --bucket contacts` НЕ помогает при ошибке в матчере — если frontmatter не изменился после rematch, значит проблема в алгоритме, а не в кэше.

**Реализованные доработки (ТЗ v0.9.1, 23.07.2026, Sonnet):**
- Словарь `HYPOCORISTICS` в `matcher_contacts.py` (Лёша→Алексей, Саша→Александр и др.)
- Порядок попыток для 2-словного ФИО: raw → reversed → hypo+word2 → word2+hypo
- При >1 совпадении → `contacts_ambiguous` (принцип «не угадывать»)
- 3-словные ФИО в обратном порядке — НЕ пробовать (риск ложного матча)
- Тест-кейсы добавлены в `test_matcher_contacts.py`, все зелёные
- Smoke-test: `mofs rematch` на встрече 23.07.2026 Trisigma подтвердил работу

