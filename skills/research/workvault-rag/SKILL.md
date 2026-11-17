---
name: workvault-rag
description: "Use when: 'найди в архиве', 'архив', 'найди в базе', 'найди"
version: 2.7.2
author: Sirene
license: MIT
platforms: [linux]
tags: [Obsidian, WorkVault, meetings, search, knowledge-base]
metadata:
  hermes:
    tags: [Obsidian, WorkVault, meetings, search, knowledge-base]
    related_skills: [obsidian, tz-workflow, about_usr_skills]
---

# WorkVault — поиск по MD-заметкам (встречи, ТЗ)

## Overview

Поиск по WorkVault (Obsidian MD-заметки: встречи, ТЗ, Confluence) — основной путь
через `mofs index` (SQLite+FTS5, `~/USERTOOLS/MofsIndex`), fallback — `search_files`/
`read_file`/`grep` напрямую по файлам. qmd (semantic search) отключён и не используется —
история и rollback в `references/known-limits.md`.

## When to Use

Триггер срабатывает на любой из этих типов запроса:

- Вопросы про **встречи**: "что обсуждали с X", "какая была встреча про Y", "когда говорили про Z"
- Вопросы про **задачи/поручения**: "какие задачи ждёт от меня X", "что я обещал сделать", "что поручили Y"
- Вопросы про **решения**: "что решили по X", "какое было решение насчёт Y"
- Вопросы про **риски/блокеры**: "какие риски по X", "что блокирует Y"
- Вопросы **по ТЗ** (Hermes-Backlog/TZ): "что написано в ТЗ по X", "какой статус у Y"
- PM Briefing в начале сессии — «что важного по проектам?»
- Поиск по 1000+ файлам NewMeetings без явных ключевых слов

## Три режима поиска (архитектура)

Использовать `mofs index` (SQLite+FTS5, `~/USERTOOLS/MofsIndex`) ПЕРВЫМ при любом
структурном запросе (slug/дата/текст). Grep/`read_file` по файлам — fallback, только
если индекс не построен (`mofs-index verify` покажет) или для точечных случаев ниже.

| Вопрос | Режим | Источник |
|---|---|---|
| «Какие встречи по ML в июле?» | 1. Поиск | `search_meetings()` |
| «Что решили на встрече 10 июля?» | 2. Детали | `get_meeting_body(meeting_id)` |
| «Кто реально что сказал про ML?» | 3. Транскрипт | `get_transcript_snippets()` / `get_meeting_body(..., include_transcript=True)` |
| «Что написано в ТЗ по X?» | ТЗ | `search_docs()` / `get_doc()` |
| «Что согласовано в протоколе проекта?» | Протокол Confluence | `search_protocols()` |
| «Что поменялось в плане X?» / «на сколько дней уехал финал?» | План (gantt/mpp) | `diff_versions()` / `task_history()` — см. ниже |

**Импорт:** `sys.path.insert(0, '/home/tkachenkoav/USERTOOLS/MofsIndex')`, затем `from mofs_index import search_meetings, get_meeting_body, get_transcript_snippets, search_docs, get_doc, search_protocols` (полный пример — `references/mofs-index-usage.md`).

**Режим 1** — `search_meetings(query=..., date_from=..., date_to=..., slugs={'projects': [...], 'contacts': [...]}, slug_mode='any')` → список `MeetingHit` (атрибуты, не dict!): `.meeting_id`, `.meeting_date`, `.title`, `.obsidian_url`, `.matched_slugs`.

**Режим 2 (главный способ читать тело встречи)** — `get_meeting_body(meeting_id)` → `str | None | ''`, тело одним SQL-запросом из `meetings_fts`, **без чтения файла с диска** (`include_transcript=True` — тело транскрипта). В связке с `search_meetings()` — точечное чтение тел отобранных встреч без открытия N файлов. `get_meeting(meeting_id)` даёт метаданные+slugs, но **не** тело.

**Режим 3** — `get_transcript_snippets(meeting_id, query, max_snippets=5, window=40)` → сниппеты с контекстом; для «кто что реально сказал» (summary часто не фиксирует мотивацию, только решения).

**ТЗ** — `search_docs(query, doc_type='tz'|'impl_plan'|None, tool_name=None)` → `DocHit` (title, snippet, rank BM25) вместо файлового grep+read по `Hermes-Backlog/TZ/`; `get_doc(doc_id)` — карточка документа.

**Протокол проекта (Confluence, OFC)** — `search_protocols(query, entity_slug=None)` → `DocHit` с `doc_type='protocol'`; в индексе `tool_name` = `entity_slug` из frontmatter `Entities/<slug>/protocol.md`.

**Подпись слоя в ответе (обязательно, не смешивать без пометки):**
- результаты `search_meetings()` → префикс «Найдено во встречах (FF, черновик)»;
- результаты `search_protocols()` → префикс «Найдено в протоколе проекта (Confluence, согласовано)».

При запросах про задачи/решения по проекту вызывать **оба** источника параллельно, если релевантны.

Полное руководство и code-snippets (`list_slugs`, проверка индекса, Obsidian-ссылка, grep-дополнение) — `references/mofs-index-usage.md`.

## Алгоритм поиска по встречам (структурные запросы: дата/участники/проект + тип сущности)

Применять к любому запросу вида "какие [задачи/решения/риски/блокеры] по [X/за период Y]",
когда `search_meetings()` даёт слишком широкий/узкий набор и нужна ручная досборка.

### Шаг 1 — период

- Дата/период явно указан ("с 16.06", "за последние 2 недели", "в июне") → `date_from`/`date_to` в `search_meetings()` на этот период.
- Период не указан → по умолчанию последние **6 месяцев**.

### Шаг 2 — участники

- Человек назван в запросе → `search_meetings(slugs={'contacts': [...]})` (покрытие 93%, основной путь).
- Если пусто/участник не резолвится — fallback grep **только по секции «Участники:»** файла (`re.search(r'Участники:([\s\S]{0,600})', text)`, искать имя только в этом блоке), никогда по всему телу — полнотекстовый grep даёт шум (человек упоминается в чужих Action Items), набор раздувается в разы. Детали ограничений матчера контактов (формат ФИО, гипокористики) — `references/known-limits.md`.

### Шаг 3 — проект/тема

- Проект/тема названы в запросе → сузить через `search_meetings(slugs={'projects': [...]})` или проверить упоминание в тексте.
- **Канонический реестр сущностей — `WorkVault/Registries/entities.json`** (EntityRegistry, схема `{slug: {kind, parent, display_name, aliases, pfs?}}`, полная схема — `WorkVault/Registries/README.md`). Единый источник правды для проектов/сущностей — из него читают PFS (`ROUTES`), TaskRefresh и этот скилл.
- **Матчинг:** 1) прочитать `entities.json`; 2) пройти по `aliases` регистронезависимо, startswith/substring (как `route.py:_match_by_name`); 3) множественные матчи → приоритет `kind`: `project` > `multisync` > `one_on_one` > `unknown` > `tool`, иначе спросить Сашу; 4) `parent` + запрос про родителя («что по DevRel») → собрать дочерние (`devrel` → `cu`); 5) нет совпадения → сказать Саше «проекта нет в реестре, кандидат на добавление».
- Питфолл: «AB-платформа» = ТУТУ или Trisigma — разруливается отдельными slug'ами `trisigma`/`ab_platforma`, сверяться с `aliases`, не угадывать по контексту.

### Шаг 4 — извлечение сущностей

- **Файлов >10 после фильтрации → делегировать Haiku (`delegate_task`, таймаут 120с) ОБЯЗАТЕЛЬНО**, не читать инлайн Sonnet'ом (24 файла × ~3k символов ≈ ~72k лишних токенов). Задача Haiku: прочитать список встреч (`read_file` по путям или тела через `get_meeting_body`), извлечь по каждой дату, Action Items/Решения/Риски с упоминанием нужного лица, вернуть блоками «дата | краткая цитата», пропуская встречи без упоминания. `toolsets=["file"]`.
- **Файлов ≤10** — читать напрямую, предпочтительно `get_meeting_body(meeting_id)` по каждому (без `read_file`).
- **Запрошены НЕ задачи** (решения/риски/блокеры) → все найденные сущности этого типа, без фильтра по лицу.
- **Запрошены задачи** → только Action Items, где ответственный явно указан по имени в строке (не implicit по контексту). Про себя ("что мне поручили") — то же правило.

### Быстрый путь: "последняя встреча с X"

Не нужен весь 4-шаговый алгоритм: `search_meetings(slugs={'contacts': [X]}, limit=1, order='date_desc')` → `get_meeting_body(hit.meeting_id)`. Саммари уже структурировано — доп. поиск не нужен.

### Путь: "как менялась постановка X во времени" (эволюция темы)

Нужна **упорядоченная последовательность** файлов, не срез на одну дату: 1) собрать набор через Шаги 1-3 (период — не сужать до 6 месяцев, брать всю историю проекта); 2) `search_meetings(..., order='date_asc')` — хронология, не релевантность/убывание; 3) для каждой встречи через `get_meeting_body` вытащить раздел про постановку/цель/скоуп (не весь Action Items), короткой цитатой с датой; 4) собрать таймлайн `YYYY-MM-DD — <формулировка на тот момент>`, отмечая точки изменения. Тот же путь для "человек+дата+тема" — сначала Шаг 2 сужает набор, затем этот путь вместо Шага 4.

## Признак "неясная запись / переговорка"

На встречах в переговорках (мультисинки, 1-1 с несколькими говорящими в одной комнате)
Fireflies часто **неверно атрибутирует Action Items конкретному спикеру**. Такие задачи
**по умолчанию относить к самому Саше**, а не к формальному адресату Fireflies, и явно
пометить в ответе, что атрибуция неясна и требует ручной проверки.

**Признаки (совпадение любых 2 из 3 = считать неясной):** 1) файл — загрузка
аудио/видео (`.m4a`/`.mp4` в имени), не прямая интеграция с онлайн-звонком; 2) Action
Items без разделения "Имя: задача" — общий список без явного автора; 3) название
встречи совпадает с переговоркой ТУТУ — список `WorkVault/Contacts/meeting-rooms.md`
(обновляется `orglookup rooms`; проверить `updated:` в frontmatter на актуальность).

## Планы (gantt/mpp)

Канон действий — `skill_view(name="edit-plan-confluence")`,
[SKILL.md](../../productivity/edit-plan-confluence/SKILL.md).
«Залей» → publish, «только в архив» → save, «все MPP из Inbox» → batch save.
История и compare читают тот же typed API без свободного SQL.
«Какая версия опубликована» — отдельно последняя подтверждённая версия
с точными page/attachment/publication IDs, trust/временем и текущее наблюдение;
при необходимости GET-only publication verify выбранной записи.


Для «хронология планов», «какие файлы загрузили сегодня» использовать
`from mofs_index.plan.history import history, HistoryRequest` — тот же typed API,
что `edit-plan-confluence history`. По умолчанию view=files (все поступления,
включая дубликаты/ошибки), snapshots — уникальные снимки, publications — регистрации
с сохранённым trust. Разделять received/recorded/source/published; «сегодня» задавать
локальными границами суток с offset, полуинтервалом [since, until). Порядок source
не меняет поле фильтра. Неизвестные времена и даты выводятся отдельно; cursor
передавать непрозрачно. Примеры и поля ответа — `references/plan-queries.md`,
раздел «История поступлений». Сеть/reader для запроса истории не нужны.


Архив слепков плана (MofsIndex `mofs_index/plan/`) — SQLite-истина по версиям плана
проекта (Confluence Gantt JSON + сохранённые MPP), typed query API (`mofs_index/plan/
query.py`), НЕ свободный SQL. Пилот — проект `zd` (`Entities/zd/Pages/zd.ganttchart.md`,
рендер из SQL, Q2 решения владельца). Источник истины — SQL; MD-витрина — производная
(может отставать на один рендер, числа всегда проверять через typed-функции, не только
по тексту MD).

**Импорт:** `from mofs_index import resolve_plan, list_versions, diff_versions,
task_history, compare_baseline, explain_finish_change` (после `sys.path.insert(0,
'/home/tkachenkoav/USERTOOLS/MofsIndex')`). Каждая функция возвращает dict с полем
`receipt` (план/версии/representation/mapping/calendar/timezone/completeness/known_at)
— всегда приводить вместе с числом, не только голое число.

**Два представления одной версии** — не путать идентичность: Confluence-публикация
(Gantt JSON, `{"kind": "publication", "publication_id": "..."}`, числовой gantt-id,
без UID) и MPP-снимок (`{"kind": "snapshot", "snapshot_id": "..."}`, локальный
`uid`, доступные ES/EF/LS/LF). Смешение представлений в одном `diff_versions()` —
`representation_mismatch / 4` без подтверждённого mapping точной пары.
Оба селектора проверяются по проекту; публикация также по странице, attachment,
snapshot и качеству связи. Один номер v2 не определяет публикацию.

| Русский сценарий (§8.4 ТЗ) | Typed-функция |
|---|---|
| «Что поменялось в ZD [между версиями]?» | `list_versions()` → выбрать пару → `diff_versions()` |
| «На сколько дней уехал финал?» | `diff_versions()` → `result["root"]["finish_delta_calendar_days"]` |
| «Как менялись сроки у юристов/конкретной задачи?» | `task_history(conn, plan_id, uid, from_snapshot_id=..., to_snapshot_id=..., mapping_revision_id=...)` — только прямые доказанные пары |
| «Какие связи удалили?» | `diff_versions()` → `result["links_removed"]` |
| «За счёт каких работ финал сдвинулся?» | `explain_finish_change()` — группы изменений с блокерами; без подтверждённого schedule replay причинность не установлена |
| «Что знали на дату X (known_at)?» | `list_versions()` + `receipt.known_at` каждой функции — снимок знания на момент вызова, не "текущая правда задним числом" |

Неоднозначность версии («последняя», «текущая») разрешается `list_versions()` +
выбором точного `publication_id`/`snapshot_id` ДО вызова `diff_versions`/
`task_history` — не угадывается по тексту MD-витрины.

Сравнение показывает revision/evidence, полные связи с лагами, календари,
назначения и структурные несопоставленные остатки. Неизвестная идентичность —
`mapping:unknown`; неизвестная timezone не даёт абсолютного date delta.
Timezone не означает полноту календаря. Связь MPP-источника с публикацией
не подтверждает позиционные Gantt ID.

`publication verify --project-slug <slug> --publication-id <id>` — GET-only
перепроверка через CLI edit-plan-confluence, с `--scope current_state|historical_version`.
Append-only наблюдение содержит verified_at, scope и результат; исходный trust
и историческая дата не повышаются. Недостаточные bytes/storage/snapshot-link —
`not_verified / 5`. Текущее совпадение не доказывает состояние прежней даты.
Без свежего наблюдения говорить «последняя известная регистрация на момент …».
Подробные selectors, API/CLI, mapping и trust — `references/plan-queries.md`.

## Связанные файлы

- Ограничения contacts-матчера, история отказа от qmd, "связи vs RAG", changelog — `references/known-limits.md`
- Полное API-руководство `mofs_index` (все режимы, code snippets, grep, проверка индекса) — `references/mofs-index-usage.md`
- Planы (gantt/mpp) typed query API, реальные числа ZD, 6 сценариев §8.4 — `references/plan-queries.md`
- Мастер-ТЗ qmd (архивный статус) — `WorkVault/Hermes-Backlog/TZ/QMD-Search/QMD-Search_TZ.md`
- EntityRegistry↔MOFS/AFM (naming-конфликты слугов, 4 корзины NER) — `about_usr_skills`, секция «EntityRegistry ↔ MOFS/AFM»

## Топики для поиска

- **WorkVault (thread=5)** — основной топик для поиска по архиву встреч
- **Tools (thread=3)** — дополнительный
- Chat: `-1004300127777`

Триггеры загрузки скилла: «найди в архиве», «архив», «найди в базе», «найди во встречах».

## Verification Checklist

- [ ] Структурный запрос (дата/участник/проект + сущность) прошёл алгоритм (mofs index первым, ручной 4-шаговый — при недостаточной точности), не угадан на глаз
- [ ] Проект/тема матчились по `aliases` записей `entities.json`, не по интуитивному совпадению — если проекта нет в реестре, это явно отмечено Саше
- [ ] Запрос "как менялась постановка X" — файлы отсортированы по `order='date_asc'` (хронология), не по релевантности/убыванию
- [ ] Широкий запрос (>10 файлов) — фильтрация делегирована Haiku, не читается инлайн Sonnet целиком
- [ ] "Неясная запись" — при совпадении 2+ признаков задача отнесена к Саше, источник явно помечен
- [ ] Не предлагать/не пытаться восстанавливать qmd без явного запроса Саши
- [ ] `MeetingHit`/`MeetingRecord` — dataclass, не dict: `h.meeting_date`/`.title`/`.meeting_id`, НЕ `h.get('...')` (AttributeError)
- [ ] Тело встречи — через `get_meeting_body(meeting_id)`; прямого поля с телом на `MeetingRecord`/`MeetingHit` не существует
- [ ] «Кто что сказал / детально обсуждалось» → `get_transcript_snippets()`/`get_meeting_body(..., include_transcript=True)`, не summary; если ответа нет в summary — проверить transcript до «не нашла»
- [ ] Вопрос по ТЗ — `search_docs()`/`get_doc()`, не файловый grep+read по `Hermes-Backlog/TZ/`
- [ ] Запрос про задачи/решения по проекту — вызваны оба источника (`search_meetings` и `search_protocols`), результат подписан по слою («Найдено во встречах (FF, черновик)» / «Найдено в протоколе проекта (Confluence, согласовано)»), не смешан без пометки
- [ ] Contacts покрывают 93% встреч (`search_meetings(slugs={'contacts': [...]})` — основной путь). Пустой результат/редкое или уменьшительное имя → grep-fallback строго по секции «Участники:» (детали — `references/known-limits.md`), не по всему телу файла
- [ ] Вопрос про план/gantt/mpp — `diff_versions()`/`task_history()`/`explain_finish_change()` (typed query API `mofs_index/plan/query.py`), не чтение `<slug>.ganttchart.md` как единственного источника и не свободный SQL; версия/snapshot выбраны явно через `list_versions()`, не угаданы; каждое число сопровождено `receipt`; publication (Gantt-id) и snapshot (MPP-uid) не смешаны в одном сравнении
