---
name: mofs-operations
description: "Use when: работа с инструментом MarkObjectsFromSummary (MOFS) — запуск прогонов, диагностика, bootstrap архива, управление entities.json, contacts из тела summary. Триггеры: mofs run, mofs rematch, entities.json, словарь тегов, тегирование встреч, wiki-ссылки Obsidian, contacts, ФИО участников, mofs index."
version: 1.0.0
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [mofs, entities, obsidian, workvault, tagging]
    related_skills: [tz-workflow, movefrom-instruments]
---

# MOFS — операционный скилл

Работа с MarkObjectsFromSummary (MOFS) — инструмент разметки `NewMeetings/*-summary.md`
wiki-ссылками Obsidian по 4 корзинам: projects, tools, rooms, contacts.

## Текущий статус (21.07.2026)

- **Версия кода:** v0.8.0, 103/103 тестов ✅
- **ТЗ:** `~/WorkVault/Hermes-Backlog/TZ/MarkObjectsFromSummary/MarkObjectsFromSummary_TZ.md` v0.8.0
- **entities.json:** `~/WorkVault/Registries/entities.json` (19 сущностей)
- **Реестр:** `~/USERTOOLS/MarkObjectsFromSummary/_mark_objects_registry.json`
- **Июль 2026:** projects/tools/rooms ✅ (60 встреч). Contacts + date: — реальный прогон НЕ запущен (ждёт этапа 2)
- **Бэкап перед этапом 2:** `WorkVault_full_2026-07-21_16-55-48.tgz` (full-workvault-backup, 16M). Откат через `mofs bootstrap --undo latest --yes` если нужно откатить только MOFS-разметку.
- **Contacts:** ✅ реализован v0.2 — матчинг ФИО из тела (28/60 встреч, 251 запись в dry-run)
- **date: во frontmatter:** ✅ реализован — проставляется из имени файла при каждом run/rematch
- **Кроны:** НЕ созданы — ждут явного «ставь кроны» от Саши после этапа 4 (проверка Саши)

## Запуск прогонов — обязательный порядок

**Всегда начинать с dry-run:**
```bash
cd ~/USERTOOLS/MarkObjectsFromSummary
source ~/USERTOOLS/ProtocolFromSummary/.venv/bin/activate

# 1. dry-run — убедиться в плане
mofs run --dry-run --from 2026-07-01 --to 2026-07-31

# 2. только после проверки плана — реальный прогон
mofs run --from 2026-07-01 --to 2026-07-31

# 3. точечно — одна встреча
mofs run --meeting-id "2026-07-08 11-05-00 Кирилл 1-1" --dry-run
```

**Safeguard (v0.7.0):**
- `run`/`rematch` без скоупа → `exit 2`
- `rematch --all` без `--yes` → показывает N встреч, требует `--yes`
- `--mode=cron` — safeguard не применяется

## Bootstrap всего архива (когда крон поработает 1-2 недели)

```bash
# 1. снапшот
mofs bootstrap --snapshot

# 2. dry-run — убедиться
mofs rematch --all --dry-run

# 3. только после проверки — реальный прогон
mofs rematch --all --yes
```

При bootstrap создаётся манифест `state/bootstrap_manifest_<ts>.json`.
Откат: `mofs bootstrap --undo latest --yes`.

## Управление entities.json

**Только через `entity-registry` CLI — никогда не редактировать вручную.**

```bash
# Просмотр
entity-registry list

# Добавить alias к существующей сущности
entity-registry edit <slug> aliases "<alias>" --append -y

# Удалить alias
entity-registry edit <slug> aliases "<alias>" --remove-item -y

# Добавить новую сущность
entity-registry add <slug> --kind project --display-name "Название" --aliases "алиас1,алиас2"
```

## MofsIndex — SQLite+FTS5 индекс (реализован 21.07.2026)

**Пакет:** `~/USERTOOLS/MofsIndex/` (editable в `ProtocolFromSummary/.venv`)
**ТЗ:** `~/WorkVault/Hermes-Backlog/TZ/MofsIndex/MofsIndex_TZ.md` v0.2.0
**Команды:**
```bash
mofs-index index --rebuild --yes   # полная перестройка
mofs-index stats                   # размер БД, число записей
mofs-index verify                  # несогласованности файлов и БД
mofs-index vacuum                  # оптимизация FTS5
```
**БД:** `~/USERTOOLS/MofsIndex/state/index.sqlite` (~57 MB, WAL-режим)
**Хуки:** автоматически после `mofs run`, `mofs rematch`, `mofs edit` (только real-mode)
**Отключить хуки:** `MOFS_INDEX_AUTO=0`

**API для workvault-rag:**
```python
from mofs_index import search_meetings, get_meeting, get_transcript_snippets
hits = search_meetings(slugs={'projects': ['kirill_1on1']})   # 1.69мс
hits = search_meetings(query='Криворотов', date_from='2026-07-01')  # 20.5мс ⚠️
snippets = get_transcript_snippets(meeting_id, 'ключевое слово')
```

**Замеры (575 встреч):**
| Операция | Результат | Цель |
|---|---|---|
| Full rebuild | 4.9с | <10с ✅ |
| search по slug | 1.69мс | <10мс ✅ |
| search FTS+дата | 20.5мс | <10мс ⚠️ тикет v0.2 |
| Размер БД | 57 MB | <60 MB ✅ |

**Архитектурные решения (отклонения от ТЗ — обоснованы техническими ограничениями):**
- FTS5 standalone (не `content=meetings`) — external content не поддерживает DELETE по meeting_id в SQLite 3.34
- `summary_body`/`transcript_body` только в FTS, не дублируются в `meetings` — экономия ~50 MB
- `OR`-условия вместо `WHERE (bucket,slug) IN (...)` — row-value syntax не поддерживается SQLite 3.34

**Тесты:** MofsIndex 65/65 + MOFS 108/108 (103 оригинальных + 5 интеграционных)

## Паттерн alias — коротких кириллические аббревиатуры

**Проблема:** alias `"цу "` (substring + пробел) цепляет окончания слов
(«страни**цу** », «табли**цу** »), даже после нормализации текста.

**Решение:** только `"цу."` (с точкой → startswith по строке).
Ловит строки вида «ЦУ. поставило задачу…» — только начало строки.

**Правило:** для аббревиатур из 2-3 букв (кириллица) — alias с точкой (`"цу."`, `"нб."`),
не пробельный вариант. Substring слишком широк.

**Прецедент 21.07.2026:** `tsu` с alias `"цу "` ложно матчил «страницу», «таблицу» в 8 встречах.
Фикс: убрать `"цу "`, оставить только `"цу."` → 0 ложных срабатываний.

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

## entities.json — топ сущностей

Топ июль 2026 (N = число встреч):
`kirill_1on1` (26), `aralov_1on1` (23), `ai_analitik` (17), `ab_platforma` (12),
`trisigma` (11), `zhirov_1on1` (11), `ml_platforma` (9), `omd` (5), `datatalks` (4).

## Пополнение entities.json (словарь тегов)

Массовый NER-прогон по архиву 563 самари → кандидаты на новые сущности.

**Рекомендуемая LLM:** Haiku (внешние провайдеры недоступны, только Anthropic).
~3.3М токенов на весь архив → оценка ~$3-4 суммарно.

## date: во frontmatter (реализовано 21.07.2026)

`date:` проставляется автоматически из имени файла при каждом `run`/`rematch`.
Идемпотентно — не перезаписывает если поле уже есть.

```python
# pipeline.py — в process_meeting после merge корзин
if not fm.get("date"):
    m_date = _FILE_DATE_RE.match(summary_path.name)
    if m_date:
        fm["date"] = m_date.group(1)
```

## Связь summary ↔ transcript

Детерминированная — по имени файла, суффикс меняется:
```
2026-07-08 11-05-00 Кирилл 1-1 - summary.md
2026-07-08 11-05-00 Кирилл 1-1 - transcript.md
```
Хранить ссылку в frontmatter не нужно — вычисляется на лету заменой суффикса.

## Зафиксированный план (Саша, 21.07.2026)

| Этап | Задачи | Статус |
|---|---|---|
| **1. Инфраструктура** | `date:` в MOFS ✅ → `mofs index` (SQLite+FTS5) ✅ | ✅ Готов |
| **2. Июль** | rematch --all июль (contacts + date за один проход) | ⏳ |
| **3. Поиск** | обновить `workvault-rag` → три режима + индекс | ⏳ |
| **4. Проверка Саши** | смотрит результаты в Obsidian + поиск из TG → корректировки | ⏳ |
| **5. Архив** | bootstrap + rematch всего архива | ⏳ |
| **6. Крон** | ежедневный `mofs run --mode=cron` | ⏳ |

**ВАЖНО:** не ставить крон без явного «ставь» от Саши (только после этапа 4).

## workvault-rag — архитектура поиска (решение 21.07.2026)

Единый скилл `workvault-rag` покрывает три режима:
- **Поиск встреч** — SQL к `mofs index` (SQLite+FTS5), <5мс
- **Детали встречи** — читает summary.md конкретной встречи
- **Цитаты из транскрипта** — читает transcript.md, отвечает через LLM

**Два отдельных инструмента НЕ создаём** — всё в одном `workvault-rag`.
Ripgrep (вариант 2) при наличии SQLite+FTS5 не нужен — медленнее на порядок.

## Obsidian-ссылки для проверки файлов

Генерация кликабельных ссылок:
```python
import urllib.parse
vault = "WorkVault"
file_path = "Meetings/NewMeetings/2026-07-08 11-05-00 Кирилл 1-1 - summary.md"
encoded = urllib.parse.quote(file_path, safe='/')
print(f"obsidian://open?vault={vault}&file={encoded}")
```

## Питфоллы

- **Бэкап перед массовым прогоном — только `full-workvault-backup`**, не `mofs bootstrap --snapshot`. Bootstrap-снапшот фиксирует только MOFS-реестр (не содержимое файлов WorkVault), не подходит как полный бэкап. Правильно: `bash ~/.hermes/scripts/full_workvault_backup.sh` перед этапами 2 и 5. Прецедент 21.07.2026: был создан bootstrap-снапшот → Саша явно исправил на full-workvault-backup.
- **Не запускать `rematch --all` без dry-run** — прецедент 16.07.2026: 564 встречи изменены,
  откат через bootstrap undo (517 файлов, 1315 карточек).
- **Smoke-test dry-run:** `mofs run --meeting-id X --dry-run` → проверить `mtime` файла до/после.
  Если изменился — dry-run сломан, не запускать на архиве.
- **Диагностические задачи:** `enabled_toolsets: ["file"]` (без terminal).
  Команду передавать ДОСЛОВНО с `--dry-run`.
- **Alias для коротких аббревиатур** — только с точкой (startswith), не substring.
- **entities.json** — только через `entity-registry` CLI, не вручную.
- **idempotency при contacts rematch:** `run` пропускает уже обработанные встречи.
  Для перепрогона только contacts — `mofs rematch --bucket contacts --from X --to Y --dry-run`.
- **cwd не важен** — с v0.7.0 `.env` читается по абсолютному пути из `config.py`.
  Крон можно запускать из любой директории.
- **Порядок поштучного ревью dry-run:** сначала dry-run → поштучный разбор проблем → фикс aliases → повторный dry-run → реальный прогон. Не торопиться к реальному прогону.

## References

- `references/mofs-v07-status.md` — детальный статус v0.7.0, таблица сущностей, баг contacts
- `references/mofsindex-v01-architecture.md` — архитектура MofsIndex v0.1.0: схема БД, отклонения от ТЗ, замеры производительности, интеграция с MOFS
