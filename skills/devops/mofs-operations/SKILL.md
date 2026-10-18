---
name: mofs-operations
description: "Use when: работа с инструментом MarkObjectsFromSummary (MOFS"
version: 1.3.3
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [mofs, entities, obsidian, workvault, tagging]
    related_skills: [tz-workflow, about_usr_skills]
---

# MOFS — операционный скилл

Работа с MarkObjectsFromSummary (MOFS) — инструмент разметки `NewMeetings/*-summary.md`
wiki-ссылками Obsidian по 4 корзинам: projects, tools, rooms, contacts.

## Текущий статус (22.07.2026)

- **Версия кода:** v1.0.0, 186/186 тестов ✅ (MOFS v0.9.0 + LLM-фолбэк + авто-rematch)
- **ТЗ:** `~/WorkVault/Hermes-Backlog/TZ/MarkObjectsFromSummary/MarkObjectsFromSummary_TZ.md` v0.9.0; приложение v1.0.0: `MarkObjectsFromSummary_v100_TZ.md`
- **entities.json:** `~/WorkVault/Registries/entities.json` (~44 сущности: проекты/1-1/синки + 13 tools + adm/okr/sr/vestnik/atribuciya/antibot/dayana_1on1/alfa/adm и др. добавлены 22.07)
- **Реестр:** `~/USERTOOLS/AnywhereContacts/_mark_objects_registry.json` (**не** в папке MarkObjectsFromSummary!); `mofs_unmatched.md` → `~/WorkVault/Registries/mofs_unmatched.md`
- **Архив:** 575 встреч, 573/575 с projects, contacts backfill S1+S2 468/514 ✅ (S3 не потребовался)
- **MofsIndex:** v0.4.0, 575 встреч, 72 MB, `~/USERTOOLS/MofsIndex/state/index.sqlite`
- **Кроны:**
  - `mofs_run_cron` (job_id: aeeccba37e4a) — `16 8-19 * * 1-5`, no_agent, deliver=local. Молчит при processed=0, ⚠️ при unmatched_count>0.
  - `mofs_index_rebuild` (job_id: 7e013cd5c6f9) — `0 23 * * *`, no_agent, deliver=local. Ежедневный full-rebuild как страховка.
  - Цепочка: MoveFromFF XX:05 → PFS-batch XX:10 → PFS-notify XX:15 → MOFS XX:16.
  - **Ошибка крона MOFS → канбан, не самому (21.09.2026).** При ошибке `mofs_run_cron` (job aeeccba37e4a) или `mofs_index_rebuild` (job 7e013cd5c6f9) НЕ чинить самому и НЕ звать архитектора напрямую через `agent -p`. Постановка на канбан: `BUG:diagnose` (root cause + план П.1…П.N) → `GATE:diagnose-review` → `HF:impl`/`HF:test` (по hermes-feature Блок 6В). План починки — `_fix_plan_YYYYMMDD.md` рядом с инструментом (`~/USERTOOLS/MarkObjectsFromSummary/`). Локальный обход средствами скилла (rematch/entity-registry) — только как одношаговый ответ, не как реализация фикса кода `pipeline.py`. Прецедент: NameError parse_rooms 19.09.2026 — починено через BUG:diagnose-граф, не напрямую.

**LLM-конфиг (MOFS v0.10.1):** источник = `~/.hermes/config.yaml` (`model.default` + `model.provider` + `custom_providers`); OpenAI-совместимый клиент к `llm-gateway.tutu.ru`; env-override `MOFS_LLM_MODEL` / `_BASE_URL` / `_API_KEY` / `_ROUTING_PROVIDER` (default) / `_REASONING_EFFORT` (high); CLI `--llm-model` (только `backfill-contacts`, перекрывает только модель); last-resort `LLM_FALLBACK_MODEL` / `LLM_FALLBACK_BASE_URL` / `LLM_FALLBACK_PROVIDER`. `ANTHROPIC_API_KEY` не читается; нет ключа → warning → skip (fail-soft). Смена модели — правка `config.yaml`, не код.

## Запуск прогонов — обязательный порядок

**Всегда начинать с dry-run:**
```bash
cd ~/USERTOOLS/MarkObjectsFromSummary
source ~/USERTOOLS/ProtocolFromSummary/.venv/bin/activate

# 1. dry-run — убедиться в плане
mofs run --dry-run --from 2026-07-01 --to 2026-07-31

# 2. только после проверки плана — реальный прогон
mofs run --from 2026-07-01 --to 2026-07-31

# 3. точечно — одна встреча (только через --meeting-id, БЕЗ пути к файлу!)
mofs run --meeting-id "2026-07-08 11-05-00 Кирилл 1-1" --dry-run
```

**⚠️ КРИТИЧНО: `mofs run` НЕ принимает путь к файлу как позиционный аргумент.**
`mofs run "/path/to/summary.md" --yes` → `error: unrecognized arguments` (exit 2).
`--meeting-id` принимает строку meeting_id формата `YYYY-MM-DD HH-MM-SS Название` — **без суффикса ` - summary.md`**.

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

# Добавить новую сущность (--parent-null обязателен для проектов без родителя!)
entity-registry add <slug> --kind project --display-name "Название" --alias "алиас1" --alias "алиас2" --parent-null -y
# ВАЖНО: --aliases "a,b,c" не работает — только --alias повторяется для каждого значения
# ВАЖНО: без --parent-null будет ошибка "missing_required: parent"
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

**MofsIndex v0.5 — индексация TZ-документов (27.07.2026):**
```bash
# Индексировать ТЗ-документы (инкрементально, <1 сек)
mofs-index index docs

# Полная перестройка индекса ТЗ
mofs-index index docs --rebuild --yes
```

Новая таблица `docs` + `docs_fts` в той же БД `index.sqlite`. Скоуп: `~/WorkVault/Hermes-Backlog/TZ/**/*_TZ.md` + `*_impl_plan.md`. Типы: `doc_type='tz'` / `'impl_plan'`.

**API для поиска по ТЗ:**
```python
from mofs_index import search_docs, get_doc
# Полнотекстовый поиск по всем ТЗ (используется backlog_analyst)
hits = search_docs('FileNameTooLong ownCloud', limit=5)
# → top-1: MoveFromFF_TZ.md, rank=-6.18 (косвенная связь через FTS5)
doc = get_doc('Hermes-Backlog/TZ/MoveFromFF/MoveFromFF_TZ.md')
```

**Важно:** после создания/правки ТЗ вызвать `mofs-index index docs` — иначе `backlog_analyst` и `workvault-rag` не увидят новое ТЗ до ночного rebuild. Хук встроен в процедуры A/B/C/D скилла `tz-workflow`.

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

## Пополнение entities.json — паттерн брифа по проектам

При обнаружении встреч без projects — сначала подсчитать N смысловых групп, затем брифовать «X из N». **Явно называть N в первом же вопросе** — «1 из N» без числа нарушает паттерн. Не начинать бриф пока N не подсчитан.
1. **Считать N заранее** — сгруппировать встречи по смыслу, назвать общее число вопросов ДО начала брифа. «1 из N» без явного N — нарушение паттерна брифа.
2. **Сортировка:** от наиболее частого и позднего к наиболее редкому и раннему (`sort(key=lambda x: (-count, last_date))`). Саша всегда хочет видеть важное первым.
3. **Читать тело встречи** для безымянных/непонятных — не задавать вопрос вслепую. Достаточно первых 200 символов тела после frontmatter.
4. Один вопрос — одно сообщение. `1` = добавить, `2` = пропустить.
5. **Мусор — не спрашивать, предлагать пропустить сразу:**
   - `Fireflies Demo Meeting`, `VPN Access and SSH Key Setup` — технические/демо
   - `Jun 12, 07_30 PM` / `Apr 17, 02_06 PM` — безымянные Fireflies
   - `email@tutu.ru - Date - Untitled` — читать тело, потом решать
   - Личные встречи (экспедиции, природа, нерабочие)
   - `Daily` без контекста
6. **Проверять совпадение с существующими сущностями** перед созданием новой:
   - «ЦУ», «ЦУ-ТУТУ», «ЦУ-отток» → уже есть `cu`, просто не было русского alias → `entity-registry edit cu aliases "цу" --append -y`
   - «ИИ-зация», «AI-зация» → уже есть `ai_ready` → добавить aliases
   - Только если реально не существует → `entity-registry add <slug> ...`
4. Скрипт выявления встреч без projects:
```bash
python3 -c "
import glob, re
nm = 'WorkVault/Meetings/NewMeetings/'
files = sorted(glob.glob(nm + '*summary.md'))
no_projects = []
for f in files:
    c = open(f).read()
    fm_end = c.find('\n---', 3)
    fm = c[4:fm_end] if fm_end > 0 else ''
    if not re.search(r\"projects:\s*\n- '\", fm):
        name = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2} ', '', f.split('/')[-1])
        no_projects.append(re.sub(r' - summary\.md$', '', name))
for n in sorted(set(no_projects)): print(n)
"
```

## Пополнение entities.json — паттерн брифа tools (22.07.2026)

Когда нужно решить какие инструменты добавить в реестр — сначала посчитать реальную частоту по архиву, потом брифовать по убыванию:

```bash
python3 -c "
import glob, re
from collections import Counter
tools_patterns = {
    'jira': r'\bjira\b|\bджира\b',
    'confluence': r'\bconfluence\b|\bконфлюенс\b',
    # ... и т.д.
}
counts = Counter()
for f in glob.glob('/home/tkachenkoav/WorkVault/Meetings/NewMeetings/*summary.md'):
    content = open(f).read().lower()
    for tool, pattern in tools_patterns.items():
        if re.search(pattern, content, re.IGNORECASE):
            counts[tool] += 1
for tool, cnt in counts.most_common():
    print(f'{cnt:4d} встреч — {tool}')
"
```

**Формат брифа:** один инструмент — одно сообщение. `1` = добавить, `2` = нет. По убыванию частоты. Стоп-лист исключённых сохранять в `TZ/EntityRegistry/appendix_tools_registry_YYYYMMDD.md` с таблицей «Приложения» в ТЗ сверху.

**Стоп-лист (нельзя без явного решения Саши):** python, docker, mlflow, redis, postgres, dbt, jenkins, gitlab, superset, slack. Полный список: `TZ/EntityRegistry/appendix_tools_registry_22072026.md`.

Массовый NER-прогон по архиву 563 самари → кандидаты на новые сущности.

**LLM для NER-прогона:** конфиг из `~/.hermes/config.yaml` (OpenAI-клиент к `llm-gateway.tutu.ru`), last-resort `LLM_FALLBACK_*`; `ANTHROPIC_API_KEY` не используется.
~3.3М токенов на весь архив → оценка ~$3-4 суммарно (зависит от выбранной модели в конфиге).

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
| **2. Июль** | rematch --all июль (contacts + date) | ✅ Готов (61 встреча) |
| **3. Поиск** | обновить `workvault-rag` → три режима + индекс | ✅ Готов (v2.2.0) |
| **4. Проверка Саши** | смотрит результаты в Obsidian + поиск из TG → корректировки | ✅ Пройдена (22.07.2026) |
| **5. Архив** | backfill-contacts + rematch tools по архиву | ✅ Готов (tools 575 встреч, contacts 468/514) |
| **6. Крон** | ежечасный `mofs run --mode=cron` XX:16 пн-пт | ✅ Создан (job: mofs_run_cron, `16 8-19 * * 1-5`) |

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

## Tools — брифовые решения (22.07.2026)

В реестре `entities.json` корзина tools — полный список после брифа с Сашей по 575 встречам архива:

| slug | Название | Встреч | aliases |
|---|---|---|---|
| `omd` | OMD (OpenMetaData) | 15 | omd, openmetadata, кумд |
| `jira` | Jira | 128 | jira, джира |
| `confluence` | Confluence | 96 | confluence, конфлюенс |
| `metabase` | Metabase | 68 | metabase, метабейс |
| `clickhouse` | ClickHouse | 55 | clickhouse, кликхаус |
| `loop` | Loop (Mattermost) | 50 | loop, луп, лупп, zulip, зулип, mattermost, матермост |
| `dwh` | DWH | 38 | dwh, дата-вархаус, хранилище данных |
| `cursor` | Cursor | 26 | cursor, курсор |
| `kubernetes` | Kubernetes | 23 | kubernetes, k8s, кубер |
| `airflow` | Apache Airflow | 16 | airflow, эйрфлоу |
| `kafka` | Apache Kafka | 11 | kafka, кафка |
| `grafana` | Grafana | 10 | grafana, графана |
| `s3` | S3 / MinIO | 9 | s3, minio, минио |

**Исключены навсегда** (не добавлять без решения Саши): python, docker, mlflow, redis, postgres, dbt, jenkins, gitlab, superset, slack.
Полный список с причинами: `TZ/EntityRegistry/appendix_tools_registry_22072026.md`.

**Loop = Zulip:** Loop — новый корпоративный мессенджер ТУТУ на базе Mattermost. Zulip отключён, но встречается в старых встречах — оба слова в aliases одной сущности `loop`.

После изменения entities.json — `mofs rematch --bucket tools --from 2026-07-01 --dry-run` чтобы проверить, затем реальный прогон.

## NER-backfill contacts по старому архиву (ТЗ готово 22.07.2026)

94% встреч до июля 2026 (~494 файла) — формат MoveFromFF без раздела «Участники». Contacts нельзя извлечь regex-ом — нужен NER.

**Решение:** подкоманда `mofs backfill-contacts` (ТЗ: `appendix_ner_archive_contacts_TZ.md`):
- **S1** (regex email-header транскрипта) → ~85% встреч бесплатно, точность 99%
- **S2** (regex спикер-метки) → +5–10%
- **S3** (Haiku по телу summary) → остаток ~150 файлов, $0.5

**Confidence:** `--min-confidence 0.90` первый прогон, потом 0.80.
**Неизвестные:** в `unmatched_candidates.json`, не в contacts.enc.
**Периодичность:** только ручной запуск (не крон).

## MOFS v1.0.0 — реализованные решения (22.07.2026) ✅

| Решение | Статус | Детали |
|---|---|---|
| LLM-фолбэк при projects=[] | ✅ | LLM из `~/.hermes/config.yaml` при `entity_hits==[]`, threshold=0.90; last-resort `LLM_FALLBACK_*` |
| Low-confidence очередь | ✅ | `mofs_unmatched.md` автоматически, бриф по запросу |
| Убрать дубль reindex из bash | ✅ | Hook в pipeline достаточен; отдельный крон `mofs_index_rebuild` 23:00 |
| Частота MOFS крона | ✅ | Оставить ежечасно XX:16 |
| Авто-rematch по хэшу entities.json | ✅ | SHA-256 8 hex; при изменении → полный rematch в том же прогоне |
| Порог confidence | ✅ | 0.90 |
| TG-уведомление при unmatched | ✅ | «⚠️ MOFS: N встреч без проекта» в крон-выводе |

**Бэклог:** создать скилл + крон для разбора `mofs_unmatched.md` — по всем типам сущностей, сортировка по частоте встречаемости (в `todo`).

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

## Питфоллы

- **Матчинг проектов — смотреть на тело summary, не только на название файла (22.07.2026).** Название встречи часто не содержит slug проекта. Читать тело (первые ~200 символов), выдвигать гипотезу, предлагать Саше. Прецеденты: «Daily» → `datatalks`, «Custom Agent Aralov» → `aralov_1on1`. В v1.0.0 закроется LLM-фолбэком при `projects=[]`.

- **Бриф по проектам — N называть ЯВНО до первого вопроса (22.07.2026).** Посчитать смысловые группы, объявить N: «1 из 8». «1 из N» без числа — нарушение, Саша указал явно. Порядок: частое+позднее → редкое+раннее.

- **⚠️ ФОРМАТ ВАРИАНТОВ В БРИФЕ — ТОЛЬКО ЧИСЛА 1/2/3, НИКОГДА НЕ A/B/C (22.07.2026).** Саша явно запретил буквенные варианты: «не удобно абц или abc — так неприемлемо». Каждый вариант под отдельным пронумерованным числом. Рекомендацию Opus — указывать явно: «Рекомендация: 1». Работает для всех брифов, не только MOFS.

- **Перед созданием новой сущности — проверить существующие aliases.** «ЦУ» → уже есть `cu` без русского alias. «ИИ-зация» → уже есть `ai_ready`. `entity-registry list | grep -i <ключевое слово>`. Добавить alias дешевле чем создавать дубль.

- **Опечатки в названиях файлов — добавлять alias с опечаткой.** Прецедент: «Мониториг конкурентов» (без «н») не матчил `parsing`. Решение: `entity-registry edit parsing aliases "мониториг конкурентов" --append -y` — единственный способ без правки оригинальных файлов.

- **`entity-registry add` — обязательные флаги (22.07.2026).** Команда `--aliases "a,b,c"` не работает — ошибка `unrecognized arguments`. Правильно: каждый alias отдельным `--alias "значение"`. Без `--parent-null` при kind=project будет `missing_required: parent`. Шаблон: `entity-registry add <slug> --kind project --display-name "..." --alias "алиас1" --alias "алиас2" --parent-null -y`

- **После изменений entities.json — всегда rematch + rebuild индекса.** Добавление aliases не даёт эффекта пока не запущен `mofs rematch --from X --to Y --bucket projects --yes` и `mofs-index index --rebuild --yes`. Встречи с уже проставленным `objects_version` не перематчиваются автоматически (до реализации авто-rematch по хэшу в v1.0.0).

- **Дубль reindex в mofs_run_cron.sh — архитектурный баг (22.07.2026).** Bash-скрипт вызывает `mofs-index index` (полный rebuild) после того как hook `reindex_batch` в pipeline.py уже сделал инкрементную переиндексацию. Лишний IO (~2-5с). Правильно: убрать `mofs-index index` из bash, добавить отдельный weekly-крон (воскресенье) для full-reindex как safety net.

- **Задним числом alias не срабатывает без rematch.** После добавления alias в entities.json встречи с уже проставленным `objects_version` НЕ перематчиваются автоматически. Нужен явный `mofs rematch --bucket projects --from X --to Y --yes`. Auto-rematch по хэшу entities.json — запланировано (MOFS backlog), не реализовано.

- **backfill-contacts — порядок источников:** сначала `--sources det` (S1+S2, детерминированные, нулевой риск) → apply по всему архиву → даёт 91% покрытие (468/514). Потом отдельно `--sources s3 --only-empty-contacts` (Haiku) только для файлов где S1+S2 не дали результата (~48 файлов). S3 не запускать по всем 514 — избыточно. S3 требует ручной сверки ~10 файлов перед массовым apply.
- **backfill vs rematch:** `mofs backfill-contacts` — для архива старого формата (без раздела «Участники»). `mofs rematch --bucket contacts` — для встреч нового формата (есть раздел «Участники»). Не путать.
- **Бэкап перед массовым прогоном — только `full-workvault-backup`**, не `mofs bootstrap --snapshot`. Bootstrap-снапшот фиксирует только MOFS-реестр (не содержимое файлов WorkVault), не подходит как полный бэкап. Правильно: `bash ~/.hermes/scripts/full_workvault_backup.sh` перед этапами 2 и 5. Прецедент 21.07.2026: был создан bootstrap-снапшот → Саша явно исправил на full-workvault-backup.
- **Contacts plain-text заголовок (КРИТИЧНО v0.8.2):** MoveFromFF генерирует ТРИ формата заголовков секций — все три должны распознаваться `_extract_section`:
  1. `## Участники:` — markdown H2 (~36 файлов)
  2. `**Участники:**` — bold (~23 файла)
  3. `Участники:` — plain-text без разметки (~24 файла)
  При contacts = [] у части встреч — проверять формат заголовков: `grep "Участники" file.md`. В text_extractor.py добавлен `_SECTION_PLAIN = re.compile(r"^([А-ЯЁA-Z][А-Яа-яЁёA-Za-z ]{2,30}):\s*$", re.MULTILINE)`.
  **Ограничение `_SECTION_PLAIN`:** паттерн требует заглавной буквы + 2-30 символов + двоеточие без текста после — чтобы не съедать строки-исполнители типа `Скворцова Диана: задача`.
- **editable install namespace-package ловушка:** `pip install -e .` с `[tool.setuptools.packages.find] include = ["pkg*"]` может создать namespace-package вместо regular-package — `__init__.py` не выполняется, публичный API недоступен. Симптомы: `pkg.__file__ is None`, `ImportError: cannot import name 'func' from 'pkg'`. **Фикс:** заменить `packages.find` на явный `[tool.setuptools] packages = ["pkg"]` и переустановить. Прецедент: mofs_index 21.07.2026.
- **unmatched_candidates замусоривание:** если unmatched_candidates.json > 500 записей на 60 встреч — значит служебные слова (Саммари, Участники, Решения, Блокеры, высокая, среднее…) попадают в кандидаты. Добавить `_SECTION_STOPWORDS` в text_extractor.py и фильтровать в resolve_contacts перед матчингом.

- **⚠️ MOFS генерирует `## Секция` (без двоеточия) — было несовместимо с PFS (28–29.07.2026, РЕШЕНО).** MOFS записывает заголовки как `## Участники`, `## Задачи` и т.д. (markdown H2, без двоеточия). До 29.07.2026 `summary_parser.py` в PFS требовал двоеточие в конце → секции не найдены → PFS публиковал пустую строку. **Системный фикс реализован 29.07.2026** — в `summary_parser._find_sections()` строка 130 расширен regex: двоеточие стало опциональным (`[^:\\n]*:?` вместо `.*:`). Теперь оба формата (`Участники:` и `## Участники`) парсируются корректно. Если снова появляются пустые протоколы — проверить `grep "## Участники\|Участники:" <summary>.md` и убедиться что `summary_parser.py` строка 130 содержит `[^:\\n]*:?`.

- **Smoke-test dry-run:** `mofs run --meeting-id X --dry-run` → проверить `mtime` файла до/после.
  Если изменился — dry-run сломан, не запускать на архиве.
- **Диагностические задачи:** `enabled_toolsets: ["file"]` (без terminal).
  Команду передавать ДОСЛОВНО с `--dry-run`.
- **Alias для коротких аббревиатур** — только с точкой (startswith), не substring.
- **entities.json** — только через `entity-registry` CLI, не вручную.
- **Сущность без блока `pfs` не попадает в PFS ROUTES.** `_load_routes_from_registry()` пропускает записи без `pfs` — встреча уходит в fallback «неразобранное» даже если alias совпадает. Фикс: добавить `pfs: {page_id: "...", tag: "ИМЯ."}`. Прецедент 28.07.2026: OKR-встреча не резолвилась — у сущности `okr` был alias, но не было блока `pfs`.
- **Fallback `vstrechi_nerazobrannoe` обязан присутствовать в entities.json.** Если запись отсутствует — при любом fallback в PFS будет `KeyError: 'vstrechi_nerazobrannoe'`. Симптом в отчёте PFS: `error: 'vstrechi_nerazobrannoe'`. Прецедент 28.07.2026.
- **⚠️ Расширение aliases → PFS публикует старый архив (22.07.2026).** При добавлении новых aliases к PFS-сущностям в entities.json — старые встречи (до CUTOVER_DATE) начинают матчиться на ROUTES PFS. Если их нет в реестре PFS — `process_pending` публикует как новые. Перед масштабным добавлением aliases: `grep -rl "<новый alias>" ~/WorkVault/Meetings/NewMeetings/*summary* | wc -l`. При наличии CUTOVER_DATE guard в PFS pipeline.py (с 22.07.2026) — встречи до 2026-07-10 защищены автоматически.

- **MOFS v1.0.0 (22.07.2026): LLM-фолбэк + авто-rematch реализованы.** При `projects=[]` после regex → LLM (конфиг `~/.hermes/config.yaml`, OpenAI-клиент к шлюзу; last-resort `LLM_FALLBACK_*`) классифицирует по entities.json (threshold=0.90). Low-confidence → `mofs_unmatched.md`. При изменении entities.json → авто-rematch по SHA-256 хэшу файла. Ежедневный full-reindex — крон `mofs_index_rebuild` (23:00, job: 7e013cd5c6f9). Скрипт: `~/.hermes/scripts/mofs_index_rebuild.sh`.

- **idempotency при contacts rematch:** `run` пропускает уже обработанные встречи.
  Для перепрогона только contacts — `mofs rematch --bucket contacts --from X --to Y --dry-run`.
- **cwd не важен** — с v0.7.0 `.env` читается по абсолютному пути из `config.py`.
  Крон можно запускать из любой директории.
- **Порядок поштучного ревью dry-run:** сначала dry-run → поштучный разбор проблем → фикс aliases → повторный dry-run → реальный прогон. Не торопиться к реальному прогону.

- **⚠️ MoveFromFF иногда возвращает Bullet points вместо Custom Summary (28.07.2026).** Симптом: summary содержит только `## Bullet points` + `## Notes` без секций `Участники:/Задачи:/Решения:`. Причина: Custom AI Skill в Fireflies не вернул output для встречи. PFS публикует пустую строку в протокол. Диагностика: `grep "## Bullet" <summary>.md` — если есть, Custom Skill не сработал. Решение — принудительный refetch: (1) найти meeting_id из `_registry_meet.json` по title, (2) удалить запись из registry, (3) удалить файл summary, (4) `python3 -m movefromff --mode manual --meeting-id <id> --no-tg --verbose`, (5) проверить `## Участники:`, (6) republish через PFS с `--confirm-republish`.

- **⚠️ Диагностика "skipped=N, processed=0" при ручном запуске (28.07.2026).** Если `mofs run --from X --to Y` возвращает `skipped=N` для встреч у которых внешне frontmatter кажется пустым или неполным — это означает что реестр `~/USERTOOLS/AnywhereContacts/_mark_objects_registry.json` уже содержит запись с `objects_version=0.6.0` (крон отработал раньше). Диагностика:
  ```python
  import json
  with open('/home/tkachenkoav/USERTOOLS/AnywhereContacts/_mark_objects_registry.json') as f:
      reg = json.load(f)
  meeting_id = '2026-07-28 12-30-00 Название'
  entry = (reg.get('meetings') or {}).get(meeting_id, {})
  print('objects_version:', entry.get('objects_version'))
  print('processed_at:', entry.get('processed_at'))
  ```
  Если `objects_version` совпадает с `OBJECTS_VERSION` в `pipeline.py` (сейчас `0.6.0`) — встреча уже обработана, skipped — норма. Frontmatter при этом уже корректный.
  Для принудительного перепрогона: `mofs rematch --meeting-id "..." --bucket all`.

## References

- `references/mofs-v07-status.md` — детальный статус v0.7.0/v0.8.x, архитектура MofsIndex v0.1.0, таблица сущностей
- `references/mofsindex-v01-architecture.md` — архитектура MofsIndex v0.1.0 (SQLite+FTS5, WAL, хуки)
- `references/tools-registry-brief.md` — паттерн брифа по реестру tools: скрипт подсчёта частоты, итоги брифа 22.07.2026, стоп-лист исключённых инструментов
- `references/projects-brief-22072026.md` — итоги брифа по проектам 22.07.2026: новые сущности, расширенные aliases, решения по неочевидным кейсам, остаток 29 мусорных встреч
- `references/mofs-cron-analysis-22072026.md` — анализ Opus инкрементной работы крона: проблемы P1-P5, варианты LLM-выявления новых сущностей с оценкой токенов, 7 открытых вопросов к Саше
