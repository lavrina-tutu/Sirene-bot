---
tool: MarkObjectsFromSummary
status: active
version: 0.10.1
author: Opus (черновик для Саши)
created: 2026-07-16
updated: 2026-09-28
decisions_locked: 2026-07-17 (D1-D6); 2026-07-18 (D7 — решение Саши: provenance + `mofs edit` + fallback detection); 2026-07-18 (v0.6.0 — команда `mofs review` для инспекции матчей, чистая изолированная фильтр-логика); 2026-07-21 (v0.7.0 — Safety: dry-run для run/rematch/edit, scope enforcement, preflight, --from/--to, дата-валидация; реализовано 103/103 тестов); 2026-07-21 (v0.8.0 — contacts v0.2: ФИО из тела summary, date: во frontmatter; брифовые решения D1-D5 зафиксированы); 2026-07-22 (v0.9.0 — backfill-contacts NER Q11.1-Q11.8 все приняты Сашей; диагностические фиксы П.1-П.6; tools-корзина расширена до 13 tools; тесты 148/148); 2026-07-23 (v0.9.1 — план доработки matcher_contacts: обратный порядок ФИО «Имя Фамилия» + словарь гипокористик; принцип «не угадывать» сохранён)
last-section-added: "LLM-конфиг из Hermes config.yaml — mofs-llm-from-hermes-default (TZ:finalize 28.09.2026, v0.10.1)"
depends_on:
  - EntityRegistry v0.2.0 (реализован; `WorkVault/Registries/entities.json` — единственный канонический источник алиасов)
  - EntityRegistryCLI v0.2.0 (реализован; единственный write-path в `entities.json`)
  - AnywhereContacts v0.1.0 (реализован; `contacts.enc` — единственное хранилище контактов)
  - MoveFromFF v2.2 (реализован; поставщик summary+transcript)
  - ExchangeOrgLookup (`orglookup rooms` → `WorkVault/Contacts/meeting-rooms.md`)
---

# MarkObjectsFromSummary v0.2 — резолв контактов, проектов, инструментов и переговорок в summary Fireflies

## Цель

Расширить существующий (архитектурно спроектированный, но физически ещё не реализованный) MOFS v0.1 c одной корзины сущностей (контакты) на **четыре** — контакты + проекты/темы + инструменты + переговорки. Результат — YAML-frontmatter каждого `NewMeetings/*-summary.md` содержит wiki-ссылки Obsidian на все распознанные сущности, что открывает нативную навигацию (граф + Dataview) по проектам БЕЗ semantic search / RAG и БЕЗ отдельной карточки проекта (`Projects/<slug>/card.md` — задача AFM модуля D, здесь НЕ реализуется).

Дополнительная цель: подготовить frontmatter-разметку, которую позже (после реализации AFM модуля D) прочитает агрегатор карточек проектов — без изменений в MOFS.

## Контекст

### Что уже есть

- **`entities.json`** (19 записей на 16.07.2026) — канонический реестр проектов/тем/инструментов с полями `slug/kind/parent/display_name/aliases` и опциональным блоком `pfs`. Пишется только через `entity-registry` CLI.
- **`contacts.enc`** — 2148 контактов, зашифрованный AES-256-GCM. API: `AnywhereContacts.ContactStore` (`read`, `get_contact`, `get_contact_by_email`, `find_contacts`).
- **`WorkVault/Contacts/meeting-rooms.md`** — 31 переговорка, markdown-таблица (`orglookup rooms`, обновляется вручную по запросу).
- **`NewMeetings/*-summary.md`** — файлы, поставляемые MoveFromFF. Frontmatter уже содержит поле `participants` (список email-ов от Fireflies).
- **`entities.schema.json`** (Draft-07) — валидирует записи; `additionalProperties: false` на уровне записи и внутри `pfs`.

### Что добавляется v0.2 vs v0.1

| Что | v0.1 (спроектировано, кода нет) | v0.2 (это ТЗ) |
|---|---|---|
| Контакты (participants → contacts.enc → `[[Имя Фамилия]]` + `Contacts/*.md`) | ✅ | ✅ (не переделываем) |
| Проекты/темы (тело summary → `entities.json` aliases → `projects: [[slug]]`) | ❌ | ✅ |
| Инструменты (тело summary → `entities.json` `kind=tool` или `tags=["tool"]`) | ❌ | ✅ |
| Переговорки (тело summary → `meeting-rooms.md` → `rooms: [[Название]]`) | ❌ | ✅ |
| Очередь несмэтченных кандидатов + еженедельный дайджест | ❌ | ✅ |
| Крон | — | Отдельный: раз в день после 20:00 (v0.1 контакты — тот же такт что MoveFromFF; v0.2 сущности — отдельный дневной такт) |

### Ссылки

- Архитектура MOFS v0.1 (контакты) — скилл `about_usr_skills` раздел «MarkObjectsFromSummary (архитектура брифа 24.05.2026)». Форматы `_mark_objects_registry.json`, статусы, режим `--rematch`, классификация контактов, крон — оттуда.
- Решения брифа 16.07.2026 по интеграции с EntityRegistry — скилл `about_usr_skills` раздел «EntityRegistry ↔ MarkObjectsFromSummary (MOFS) / AggregateFromMeetings (AFM) — бриф 16.07.2026», 7 пунктов, использованы здесь как заданные требования, повторно не открываются.
- Аналоги детерминированного матчинга по `aliases`:
  - PFS `route.py::_match_by_name` (регистронезависимо, тег с точкой на конце ⇒ startswith, свободный алиас ⇒ substring).
  - Скилл `workvault-rag` Шаг 3.
- Формат ТЗ — образцом взяты `TZ/EntityRegistry/EntityRegistry_TZ.md` и `TZ/EntityRegistryCLI/EntityRegistryCLI_TZ.md`.

### Технический факт: физического кода MOFS v0.1 НЕТ

`~/USERTOOLS/` (на 16.07.2026): `AggregateFromMeetings/`, `AnywhereContacts/`, `ConfluenceSync/`, `DialogBacklog/`, `EntityRegistryCLI/`, `ExchangeMeeting/`, `MeetingScheduler/`, `MoveFromFF/`, `MoveFromJira/`, `MoveFromZulip/`, `MppReader/`, `OKRTool/`, `OrgLookup/`, `ProtocolFromSummary/`, `SRTool/`, `TaskRefresh/`, `ZoomAPI/` — **никакого `MarkObjectsFromSummary/` там нет**, `grep -R "_mark_objects_registry"` тоже пуст.

⇒ Это ТЗ проектирует **v0.1 и v0.2 вместе, с нуля**, единой архитектурой, но с явной пометкой в пофайловом плане, что относится к v0.1-корзине (контакты) и что к v0.2 (проекты/инструменты/переговорки). Крон v0.2 стартует после того как v0.1-часть отработала хотя бы день на новых встречах (см. §Критерии успеха).

## Архитектура

### Расширение схемы `entities.json` / `entities.schema.json`

Добавляются два опциональных поля верхнего уровня записи:

```jsonc
{
  "slug": {
    "kind": "project | one_on_one | multisync | sync_aid | unknown | tool",
    "parent": "…",
    "display_name": "…",
    "aliases": ["…"],
    "pfs": { … },                              // как есть
    "charter": {                               // НОВОЕ, опционально
      "confluence_id": "480923430"             // строка из цифр — pageId устава/index-страницы проекта
    },
    "tags": ["tool", "…"]                      // НОВОЕ, опционально, свободный список меток
  }
}
```

**Правила:**

1. **`charter`** — симметричен `pfs`: опциональный объект, `additionalProperties: false` внутри, `required: ["confluence_id"]`, `confluence_id` = строка из цифр (та же валидация паттерном что `pfs.page_id`). MOFS/AFM — **только read**; пишет только человек через `entity-registry edit <slug> charter --set '{"confluence_id":"…"}'` (EntityRegistryCLI автоматически подхватит новое поле через schema-интроспекцию, кода менять не нужно). Разрешён технически для любого `kind` — field-level инвариант «charter только для project» **не добавляется** (см. решение 10 брифа).
2. **`tags`** — массив строк, свободный словарь, применение сейчас: одно значение `"tool"` для случая двойной классификации (проект, который одновременно инструмент — например, `metroteka`, `kind=project, tags=["tool"]`). Схема: `{"type":"array","items":{"type":"string"},"uniqueItems":true}`. MOFS v0.2 при матчинге считает запись «инструментом» если `kind == "tool"` ИЛИ `"tool" in tags`.
3. **Обратная совместимость.** Существующие 19 записей продолжают проходить валидацию без изменений (оба поля опциональные; `additionalProperties: false` на уровне записи расширяется добавлением новых полей в `properties`).
4. **Валидация EntityRegistryCLI.** После расширения schema никаких правок Python-кода CLI не требуется (интроспекция схемы уже реализована в `schema_loader.py`); нужно только обновить сам файл `entities.schema.json`. Бизнес-инварианты (уникальность `slug`, `parent`-ссылки, уникальность `(pfs.page_id, pfs.tag)`) не затрагиваются. Для `charter`/`tags` бизнес-инварианты **не** добавляются.

### Формат `_mark_objects_registry.json`

Расширяется структура на встречу (в поле `meetings.<id>` добавляются четыре подсекции по одной на корзину):

```jsonc
{
  "schema_version": "2.1",                     // v0.1 = "1.0"; v0.2 = "2.0"; v0.5 = "2.1" (добавлено поле provenance на уровне записи)
  "meetings": {
    "<meeting_id>": {
      "processed_at": "2026-07-17T20:10:03+03:00",
      "status": "ok",                          // ok / empty / no_participants / error
      "files": { "summary": "NewMeetings/…-summary.md" },
      "contacts": {                            // v0.1
        "matched": [
          { "key": "ivan.ivanov@tutu.ru", "provenance": "mofs_auto" },
          { "key": "petya.petrov@tutu.ru", "provenance": "manual_via_mofs", "note": "звал устно, добавил вручную" }
        ],
        "unmatched_speakers": ["Speaker 1"]
      },
      "projects": {                            // v0.2
        "matched": [
          { "slug": "trisigma",     "provenance": "mofs_auto" },
          { "slug": "ml_platforma", "provenance": "mofs_llm_fallback", "confidence": 0.91 },
          { "slug": "sputnik",      "provenance": "manual_via_mofs", "added_at": "2026-07-18T11:03:00+03:00", "note": "упомянут в ходе встречи, не пойман алиасами" }
        ]
        // Поле matched_via_llm убрано в 2.1 — LLM-пойманные различаются по provenance="mofs_llm_fallback" внутри matched.
        // Метрика «сколько поймано LLM» = count(item.provenance=="mofs_llm_fallback").
      },
      "tools": {
        "matched": [
          { "slug": "metroteka", "provenance": "mofs_auto" }
        ]
      },
      "rooms": {
        "matched": [
          { "slug": "dzhungli", "provenance": "mofs_auto" }
        ],
        "unmatched": []
      },
      "objects_version": "0.5.0"               // версия алгоритма прогона, для форс-переразметки при следующем bump
    }
  }
}
```

**Значения `provenance` (обязательное поле каждой записи в `matched` во всех 4 корзинах):**

- `mofs_auto` — детерминированный матч по `entities.json`/`contacts.enc`/`meeting-rooms.md` (Шаг 2 или 3 алгоритма).
- `mofs_llm_fallback` — пойман LLM-фолбэком (Шаг 4), опционально сопровождается полем `confidence`.
- `manual_via_mofs` — добавлено вручную через `mofs edit --add` (см. §Ручные правки frontmatter — `mofs edit`), опционально сопровождается полями `added_at` (ISO-timestamp) и `note` (свободный текст, из `--note`).

**Миграция 2.0 → 2.1** (первый прогон v0.5): все существующие строки `matched` (простые slug/email) оборачиваются в объекты с `provenance = "mofs_auto"`. Для тех, что были в `matched_via_llm` — `provenance = "mofs_llm_fallback"`. Поле `matched_via_llm` удаляется. Миграция атомарная (`tmp+rename`), выполняется под single-instance lock.

**Миграция v0.1 → v0.2.** При первом прогоне v0.2: если `schema_version == "1.0"` — атомарно переписать header в `"2.0"`, для каждой существующей записи добавить пустые подсекции `projects/tools/rooms` (проставить `objects_version="0.1.0"`), контакты не трогать. Дальше — каждый прогон дописывает недостающие подсекции по мере обработки.

### Алгоритм резолва одной встречи (v0.2 такт)

Вход: путь к `-summary.md`. Выход: обновлённый frontmatter файла + запись в `_mark_objects_registry.json` + инкременты в `unmatched_candidates.json`.

**Шаг 0 — идемпотентность.** Прочитать запись реестра: если `objects_version == "0.2.0"` И `--rematch` не задан ⇒ пропустить (return early без открытия файла).

**Шаг 1 — извлечь текст.** Разобрать `.md`: frontmatter → `participants` (для v0.1-контактов, тут не переделываем); тело → чистый текст без markdown-разметки для матчинга v0.2.

**Шаг 2 — детерминированный матч по `entities.json` (проекты + инструменты).**

Один проход, идентичен `route.py::_match_by_name` и `workvault-rag` Шаг 3:

```python
text_lower = normalize(text)  # lowercase, схлопнутые пробелы
for slug, ent in entities.items():
    for alias in ent["aliases"]:
        a = alias.lower().strip()
        if a.endswith("."):                     # тег с точкой ⇒ startswith по абзацу
            if any(line.strip().lower().startswith(a) for line in text.splitlines()):
                hit(slug); break
        else:                                    # свободный алиас ⇒ substring
            if a in text_lower:
                hit(slug); break
```

Классификация попадания в корзину:

- `kind == "tool"` ИЛИ `"tool" in ent.get("tags", [])` ⇒ **инструмент** (в `tools.matched`).
- Иначе (project/multisync/one_on_one/sync_aid/unknown) ⇒ **проект/тема** (в `projects.matched`).
- Двойная классификация (`kind=project` + `tags=["tool"]`, как `metroteka`) ⇒ запись попадает в **обе** корзины одновременно, это ожидаемое поведение (не дубль — сознательное).

**Шаг 3 — детерминированный матч по переговоркам.**

Загрузить `meeting-rooms.md` один раз в начале прогона, распарсить markdown-таблицу в `[{name, aliases_derived}]`. Матч по `name` (substring, case-insensitive) и по производным алиасам:

- Каноническое `name` из первой колонки (напр. «Джунгли (16) - Zoom»).
- Производные: имя без пометки вместимости и суффикса ` - Zoom` (`Джунгли`), имя до первой скобки (fallback).

Хиты попадают в `rooms.matched`. Совпадений с `entities.json` быть не должно — переговорки НИКОГДА не заводятся в `entities.json` (решение 4 брифа).

**Шаг 4 — LLM-фолбэк на непойманный текстовый остаток.**

Только если в тексте есть **потенциальные** упоминания проектов/инструментов, не пойманные Шагом 2. Кандидаты — существительные с большой буквы / англ. термины / кавычки — извлекаются простым regex-эвристиком (`\b[А-ЯЁA-Z][\wА-Яа-яЁё-]{2,}\b` + фильтр стоп-слов). Если после Шага 2 таких «неопознанных» кандидатов ноль — LLM НЕ вызывается (экономия).

LLM-контекст: список кандидатов + весь `entities.json` (aliases для контекста, ~19 записей, дёшево). Задача LLM: для каждого кандидата вернуть `{"candidate": "...", "match_slug": "trisigma"|null, "confidence": 0..1}`. Порог `confidence >= 0.85` ⇒ считать матчем (в `matched_via_llm`), ниже — в очередь несмэтченных.

Модель: **Haiku** (задача узкая, детерминированный контекст, дорого гонять Sonnet/Opus каждый день). Prompt-темплейт — в `templates/llm_fallback.j2`.

**Шаг 5 — накопление несмэтченных.**

Кандидаты, не пойманные ни Шагом 2, ни Шагом 4, идут в `unmatched_candidates.json`:

```jsonc
{
  "schema_version": "1.0",
  "candidates": {
    "метротека 2.0": {                         // нормализованная форма (lowercase, схлопнутые пробелы)
      "count": 7,
      "first_seen": "2026-07-17",
      "last_seen": "2026-07-23",
      "seen_in_meetings": ["<meeting_id>", "…"],
      "example_sentences": ["…", "…", "…"]     // до 3, первые попавшиеся, для контекста в дайджесте
    }
  }
}
```

**Идемпотентность счётчика.** Ключом дедупликации выступает `(candidate_normalized, meeting_id)`: `count` инкрементится только если этот `meeting_id` ещё не был учтён для этого кандидата (`meeting_id not in seen_in_meetings`). При `--rematch` конкретной встречи её вклад в `count` пересчитывается: сначала все её `meeting_id`-упоминания вычитаются из всех кандидатов, затем прогон записывает заново. Это гарантия неудвоения при повторных прогонах.

**Шаг 6 — обновление frontmatter.**

Идентично v0.1-паттерну для `contacts`. Добавляемые поля в YAML:

```yaml
projects:
  - "[[trisigma|Trisigma]]"
  - "[[ml_platforma|ML-платформа]]"
tools:
  - "[[metroteka|Метротека]]"
rooms:
  - "[[dzhungli|Джунгли]]"
```

- Формат wiki-ссылки — **pipe-alias Obsidian**: `[[<target>|<display>]]`, где `target` — стабильный ключ (для projects/tools — `slug` из `entities.json`; для rooms — производный `slug` от канонического имени переговорки, snake_case, транслит: `Джунгли` → `dzhungli`, `Метротека` → `metroteka`), а `display` — читабельное имя (`display_name` из `entities.json` для projects/tools; каноническое имя без пометки вместимости и суффикса ` - Zoom` для rooms). Такой формат даёт (а) стабильность target — Dataview/backlinks/граф Obsidian матчат по target, не по видимому тексту, поэтому переименование `display_name` через `entity-registry edit` НЕ ломает граф; (б) читаемость в графе — узел подписан `Trisigma`, не `trisigma`. Стоимость реализации — одна строка в шаблоне `frontmatter.py` (интерполяция `f"[[{slug}|{display_name}]]"`).
- Для rooms — target генерируется детерминированным транслитом канонического имени в snake_case (реализация — `rooms_reader.py::slugify_room`), результат кешируется в памяти на прогон; коллизии слагов между комнатами (маловероятно на 31 записи) → WARN в лог + fallback на добавление порядкового суффикса `_2`.

**Шаг 6.5 — idempotent-создание карточек-заглушек (`card_writer.py`).**

Для каждого свежесматченного slug/room-slug, попавшего в frontmatter на Шаге 6, проверяется существование соответствующего файла-карточки в vault:

- `WorkVault/Projects/<slug>.md` — для записей из корзины `projects`.
- `WorkVault/Tools/<slug>.md` — для записей из корзины `tools` (если запись двойной классификации `kind=project` + `tags=["tool"]` — создаются **обе** карточки, `Projects/<slug>.md` и `Tools/<slug>.md`, с идентичным содержимым; это цена сознательной двойной классификации).
- `WorkVault/Rooms/<room_slug>.md` — для записей из корзины `rooms`.

**Поведение строго idempotent:** если файл уже существует — MOFS **не открывает и не трогает его вообще**, ни на первом прогоне, ни на всех последующих, ни при `--rematch`. Предполагается, что Саша дополняет карточку вручную (тезисы, ссылки, статус), и автоматика не имеет права затирать эти правки. Если файл отсутствует — создаётся один раз по шаблону `templates/entity_card.md.j2` (см. §Пофайловый план).

**Содержимое карточки** (шаблон `entity_card.md.j2`):

Для projects/tools:
```md
---
kind: {{ kind }}
---

# {{ display_name }}

## Backlinks

```dataview
list from [[{{ slug }}]]
```
```

- Frontmatter содержит **только** `kind` (значение из `entities.json` на момент создания). Поле `aliases` сознательно **не включается**: `aliases` часто меняется через `entity-registry edit`, а карточка создаётся один раз и никогда не перезаписывается — если бы `aliases` дублировался сюда, он неизбежно устарел бы и создал тихое расхождение с источником правды `entities.json`. `kind` практически не меняется после создания записи (проекты становятся `sync_aid`/`unknown` крайне редко, и это осознанное действие Саши), риск устаревания минимальный и принят.
- `display_name` — из `entities.json` на момент создания. При последующем переименовании через `entity-registry edit` заголовок в карточке НЕ обновится автоматически (это ручная операция, если вообще нужна — Dataview-list всё равно продолжает работать по стабильному `slug`).
- `Dataview list from [[<slug>]]` — единственная точка автоматической агрегации: собирает все `-summary.md`, ссылающиеся на этот slug (за счёт pipe-alias формата на Шаге 6, target=slug). Это НЕ дублирует будущую функциональность AFM модуля D (карточка проекта с decisions/risks/action_items — там), а даёт минимальную «якорную» страницу здесь и сейчас, чтобы (а) не было красных ссылок в графе, (б) появилась единая точка входа для поиска через `workvault-rag` и будущих Dataview-запросов.

Для rooms — карточка **без frontmatter** (поле `kind` семантически не применимо к переговорке, а вводить искусственное `type: room` только ради симметрии — раздувание схемы; переговорки достаточно опознаются по расположению в директории `Rooms/`):
```md
# {{ display_name }}

## Встречи в этой переговорке

```dataview
list from [[{{ room_slug }}]]
```
```

**Почему решение изменилось от первоначальной рекомендации Opus** (первоначально было «НЕ создавать, красные ссылки как ожидаемое состояние»): (а) единая точка агрегации backlinks для каждого проекта/инструмента/переговорки нужна прямо сейчас, до реализации AFM модуля D — это ускоряет будущие запросы `workvault-rag` и даёт человеко-читаемый вход для навигации; (б) Dataview-list в заглушке — узкая, не пересекающаяся с AFM ответственность (только сырые backlinks, никаких decisions/risks); (в) idempotent-контракт защищает ручные правки Саши, поэтому «раз создали и забыли» не мешает дальнейшему обогащению.

**Шаг 7 — запись реестра и очереди атомарно** (`tmp + os.replace`, portalocker single-instance).

### Еженедельный дайджест несмэтченных

**Файл-дайджест:** `WorkVault/Hermes-Backlog/MOFS/unmatched-YYYY-MM-DD.md` (директория `MOFS/` создаётся; формат имени — дата понедельника прогона).

**Содержимое:** заголовок, дата, общее число уникальных кандидатов, топ-N (без ограничения — весь список) отсортирован по `count` убыв., затем по `last_seen` убыв.:

```md
# Несмэтченные кандидаты MOFS — неделя 2026-07-20

Всего уникальных: 42. Прогон: 2026-07-20 09:00 МСК.

| Кандидат | Встреч | Первое | Последнее | Пример |
|---|---|---|---|---|
| «метротека 2.0» | 7 | 2026-07-17 | 2026-07-23 | «обсудили метротеку 2.0 с командой» |
| «RAG-платформа» | 3 | 2026-07-19 | 2026-07-22 | «…» |
```

После рендера — **очередь НЕ обнуляется** (Саша может обработать частично, счётчики продолжают жить и расти в следующей неделе).

**TG-уведомление** (только текст, не файл — файл смотреть отдельно в Obsidian):

> MOFS дайджест 2026-07-20: 42 новых уникальных кандидата, макс. вхождений — 7 («метротека 2.0»). Полный список: `Hermes-Backlog/MOFS/unmatched-2026-07-20.md`

Каналом TG-уведомления — тот же `TG_ALERT_CHAT_ID=400307920` через утилиту `tg.py` (шаблон из MoveFromFF).

### Крон

**Основной такт MOFS v0.2** — `mofs_daily` (`0 21 * * 1-5`, пн-пт 21:00 МСК): один прогон в день, ПОСЛЕ последнего вечернего синка MoveFromFF (`0 20`) с запасом 1 часа на обработку. Обрабатывает все `NewMeetings/*-summary.md`, у которых в реестре `objects_version < "0.2.0"` (или запись отсутствует), режим `cron`.

**Дайджест-крон** — `mofs_digest_weekly` (`0 9 * * 1`, каждый понедельник 09:00 МСК): один прогон в неделю, СИНХРОНЕН/независим от `mofs_daily`, читает `unmatched_candidates.json`, рендерит `unmatched-YYYY-MM-DD.md`, шлёт TG.

**Почему два крона, а не один с внутренним «если понедельник».** Разные ответственности, разное расписание (5 дневных vs 1 недельный), разные failure-модes (сломанный дайджест не должен блокировать матчинг). Стандарт MoveFrom* — «один инструмент — одно назначение крона». Наблюдаемость проще: отдельные строки в `cronjob(action='list')`, отдельные логи, отдельная возможность приостановить дайджест не трогая матчинг.

**MOFS v0.1 (контакты)** — отдельный крон `mofs_contacts_hourly`, такт MoveFromFF (`5 10-20 * * 1-5`, +5 мин после каждого синка). Отдельно от v0.2, потому что (а) резолв контактов дешёвый и хочется свежие карточки контактов сразу после синка, (б) LLM-фолбэк тут не нужен вообще (email — детерминированный ключ).

## Пофайловый план

```
~/USERTOOLS/MarkObjectsFromSummary/
├── markobjectsfromsummary/
│   ├── __init__.py
│   ├── __main__.py                  # python -m markobjectsfromsummary
│   ├── cli.py                       # argparse: run / rematch / digest / validate
│   ├── config.py                    # pydantic Settings (пути к entities.json, contacts.enc, rooms.md, NewMeetings, реестрам)
│   ├── registry.py                  # _mark_objects_registry.json: load/save/migrate v1.0→v2.0, portalocker
│   ├── candidates.py                # unmatched_candidates.json: инкремент, вычет по meeting_id, rebuild
│   ├── entities_reader.py           # тонкий read-адаптер: entities.json + schema-based нормализация aliases
│   ├── rooms_reader.py              # meeting-rooms.md парсер (markdown table → list[Room]) + производные алиасы
│   ├── frontmatter.py               # YAML frontmatter read/merge/write (idempotent)
│   ├── text_extractor.py            # .md → чистый текст тела для матчинга; regex-эвристик кандидатов LLM
│   ├── matcher_contacts.py          # v0.1: participants → contacts.enc → wiki-ссылки + карточки Contacts/
│   ├── matcher_entities.py          # v0.2: детерминированный проход по entities.json (проекты + инструменты)
│   ├── matcher_rooms.py             # v0.2: детерминированный проход по meeting-rooms.md
│   ├── llm_fallback.py              # v0.2: Haiku-запрос по остатку; парсит JSON-ответ; порог confidence 0.85
│   ├── digest.py                    # v0.2: рендер unmatched-YYYY-MM-DD.md + TG-уведомление
│   ├── card_writer.py               # v0.2: idempotent-создание карточек-заглушек Projects/Tools/Rooms
│   ├── bootstrap_snapshot.py        # v0.2: снапшот frontmatter+реестров ДО бутстрапа, undo по манифесту (см. §Bootstrap — снапшот и откат)
│   ├── manual_edit.py               # v0.5: команда `mofs edit` — штатный путь ручной правки frontmatter встреч через MOFS (см. §Ручные правки frontmatter)
│   ├── review.py                    # v0.6: чистая изолированная функция фильтрации `apply_filters(registry_data, filters) -> list[MatchedMeeting]` + рендер вывода (текст/count/json). Не зависит от argparse/CLI. Готова к выносу в общий пакет, если появится второй реальный потребитель.
│   ├── pipeline.py                  # оркестратор одной встречи: шаги 0..7 (см. алгоритм выше)
│   ├── lock.py                      # portalocker single-instance guard
│   ├── logger.py                    # _log.md одна строка/запуск + jsonl events
│   ├── tg.py                        # TG-нотификации (дайджест + manual-ошибки)
│   └── templates/
│       ├── llm_fallback.j2
│       ├── digest.md.j2
│       └── entity_card.md.j2       # шаблон карточки-заглушки (варианты для projects/tools и для rooms)
├── tests/
│   ├── test_matcher_entities.py
│   ├── test_matcher_rooms.py
│   ├── test_matcher_contacts.py
│   ├── test_candidates_frequency.py
│   ├── test_frontmatter_idempotent.py
│   ├── test_card_writer.py
│   ├── test_digest_sort.py
│   ├── test_registry_migration_v1_v2.py
│   ├── test_manual_edit.py          # v0.5: `mofs edit --add/--remove`, provenance manual_via_mofs, формат pipe-alias
│   ├── test_review_filters.py       # v0.6: apply_filters — one filter / composed / provenance / --count / --json / AND-логика (см. тесты ниже)
│   └── fixtures/
│       ├── entities.sample.json
│       ├── contacts.sample.enc
│       ├── rooms.sample.md
│       └── summaries/
│           ├── clean.md             # чистая встреча (все смэтчены)
│           ├── with_llm_fallback.md
│           ├── all_unmatched.md
│           └── ambiguous.md
├── state/                           # runtime-каталог: манифесты бутстрапа (bootstrap_manifest_<ts>.json), не под git
├── .env
├── pyproject.toml                   # editable install, entry-point `mofs`
└── README.md
```

**Venv** — общий с ProtocolFromSummary/TaskRefresh/EntityRegistryCLI (`~/USERTOOLS/ProtocolFromSummary/.venv/`), решение симметрично EntityRegistryCLI (не плодить venv-ы, все инструменты одного семейства читают одни и те же файлы). `pip install -e ~/USERTOOLS/MarkObjectsFromSummary/` в этот venv.

**Entry-points:** `mofs run`, `mofs rematch --all|--meeting-id X|--from Y --to Z [--bucket contacts|projects|tools|rooms|all]`, `mofs digest`, `mofs validate`, `mofs bootstrap --snapshot`, `mofs bootstrap --undo <manifest_timestamp>|latest [--dry-run]`, `mofs edit --meeting-id <id> --bucket contacts|projects|tools|rooms (--add <slug> | --remove <slug>) [--note "..."]`, `mofs review [--bucket ...] [--slug ...] [--from YYYY-MM-DD --to YYYY-MM-DD] [--provenance mofs_auto|mofs_llm_fallback|manual_via_mofs] [--count | --json]`.

**`--rematch --bucket`** — новый под-флаг: перепрогонять не всё, а выбранную корзину (напр. только `projects` после `entity-registry add`). Актуально для точечного обогащения архива задним числом. По умолчанию `--bucket all`.

## Схема расширения `entities.schema.json` (patch)

Добавить в `properties` записи два ключа:

```jsonc
"charter": {
  "type": "object",
  "required": ["confluence_id"],
  "properties": {
    "confluence_id": { "type": "string", "pattern": "^[0-9]+$" }
  },
  "additionalProperties": false
},
"tags": {
  "type": "array",
  "items": { "type": "string" },
  "uniqueItems": true
}
```

**Всё.** Никакого field-level инварианта «charter только для kind=project» (решение 10 брифа). Никакой валидации содержимого `tags` (свободный словарь; интерпретация `"tool"` — на стороне matcher_entities, не схемы).

**Обратная совместимость.** Существующие 19 записей проходят валидацию без изменений (оба поля опциональные). `additionalProperties: false` на уровне записи уже присутствует — новые ключи добавляются в `properties`.

## Что НЕ трогать

- **`contacts.enc` write-path / AnywhereContacts** — MOFS только читает. Никаких `store.update_contact()` из MOFS. Карточки `Contacts/*.md` создаются как в v0.1 (генерация из данных `contacts.enc`, не запись обратно).
- **`entities.json` write-path** — только через `entity-registry` CLI. MOFS никогда не пишет в этот файл (ни `charter`, ни `tags`, ни новые сущности из очереди — Саша сам добавляет через CLI).
- **`route.py` / PFS ROUTES / TaskRefresh ProjectRegistry** — потребители `entities.json`, MOFS их код не трогает, работает параллельно.
- **AFM модуль D / `Projects/<slug>/card.md`** — «богатые» карточки проекта (decisions/risks/action_items, агрегация артефактов встреч) — задача AFM. MOFS создаёт **только** минимальные карточки-заглушки `Projects/<slug>.md` / `Tools/<slug>.md` / `Rooms/<room_slug>.md` (заголовок + Dataview list from [[slug]] + `kind` во frontmatter для projects/tools). Idempotent: если карточка существует — не трогается никогда. AFM модуль D, когда появится, будет либо расширять эти заглушки (аккуратно, не через MOFS), либо жить рядом (`Projects/<slug>/card.md` — отдельный файл в поддиректории; заглушка `Projects/<slug>.md` остаётся якорем для backlinks).
- **`meeting-rooms.md`** — только читать. Обновление списка комнат — задача `orglookup rooms` (ExchangeOrgLookup), не MOFS.
- **`_registry_meet.json` MoveFromFF** — не трогать (у MOFS свой `_mark_objects_registry.json`).
- **Ручная правка frontmatter встреч в текстовом редакторе / Obsidian** — соглашение: правится **только через `mofs edit`** (симметрично «люди → `contacts.enc`», «сущности → `entity-registry`», «переговорки → `orglookup rooms`»). MOFS не может физически запретить прямое редактирование текстового файла — это правило соглашения, не техническое ограничение. Нарушение соглашения: fallback safety-net undo обнаружит расхождение с манифестом и защитно пропустит встречу целиком (см. §Bootstrap — снапшот и откат).

## Тесты (минимум)

1. **`test_matcher_entities.py`**
   - Матч по exact alias, регистронезависимо, startswith на теге с точкой, substring на свободном алиасе.
   - Двойная классификация: `metroteka` (kind=project, tags=["tool"]) → попадает в обе корзины.
   - `kind=tool` без `tags` → только tools.
   - Отсутствие ложных матчей на подстроки внутри слов (граница слова).

2. **`test_matcher_rooms.py`**
   - Матч по каноническому name (с пометкой вместимости).
   - Матч по производному алиасу (без ` - Zoom`, без скобок вместимости).
   - НЕ матчит переговорки как проекты (перекрёстная изоляция корзин).

3. **`test_matcher_contacts.py`** (v0.1 регресс)
   - participants → contacts.enc match, генерация `[[Имя Фамилия]]` + карточки.
   - unmatched_speakers для speakers без email.
   - `ignore: true` пропускается.

4. **`test_candidates_frequency.py`**
   - Идемпотентность: два прогона одной встречи не удваивают `count`.
   - `--rematch` конкретной встречи: её вклад корректно вычитается и перезаписывается.
   - Сортировка `count DESC, last_seen DESC` стабильная.

5. **`test_frontmatter_idempotent.py`**
   - Повторный прогон не дублирует wiki-ссылки в `projects/tools/rooms/contacts`.
   - Сохраняет ручные правки в frontmatter (merge, не overwrite).
   - Формат wiki-ссылки — строго pipe-alias `[[<target>|<display>]]`, а не голый `[[slug]]`. Тест собирает regex по всем добавленным строкам `projects/tools/rooms` и падает, если хотя бы одна не содержит `|`.
   - При переименовании `display_name` через `entity-registry edit` следующий прогон MOFS **обновляет** видимую часть (после `|`) в frontmatter уже размеченных встреч только если запись помечена `--rematch`; без `--rematch` старые встречи остаются как есть (стабильность истории).

6. **`test_digest_sort.py`**
   - Порядок в `.md` совпадает с TG (одна и та же сортировка).
   - Топ TG-уведомления — реальный топ по `count`.

7. **`test_registry_migration_v1_v2.py`**
   - Загрузка `_mark_objects_registry.json` v1.0 (только contacts) → добавляются пустые проекты/инструменты/переговорки, `schema_version` = 2.0, контакты не тронуты.

9. **`test_card_writer.py`**
   - Создание карточки при **первом** матче: файл `Projects/<slug>.md` не существовал → появился после прогона, содержит `# <display_name>`, frontmatter `kind: project`, блок ```dataview\nlist from [[<slug>]]```. НЕТ поля `aliases` во frontmatter.
   - **Idempotent-контракт:** если Саша вручную дописал произвольный текст в существующую карточку (напр. добавил заметки под заголовком) — следующий прогон MOFS оставляет файл байт-в-байт (`os.stat().st_mtime` не меняется, содержимое сохраняется). Тест форс-меняет содержимое → прогоняет MOFS → сверяет hash.
   - Двойная классификация `metroteka` (kind=project + tags=[tool]) → создаются **обе** карточки `Projects/metroteka.md` и `Tools/metroteka.md` с одинаковым содержимым (кроме frontmatter — обе содержат `kind: project`, так как источник — одна и та же запись `entities.json`).
   - Карточка комнаты `Rooms/dzhungli.md` создаётся **без frontmatter**, только заголовок + Dataview-list.
   - Транслит room-slug детерминирован: `Джунгли` → `dzhungli`, `Метротека` → `metroteka`, `Красный (10) - Zoom` → `krasnyy` (без пометки вместимости и суффикса).
   - При `--rematch` уже существующие карточки НЕ пересоздаются и НЕ трогаются (это требование ортогонально `--rematch` — тот флаг про frontmatter встреч и реестр, не про карточки).

10. **`test_pipe_alias_format.py`**
    - Строка frontmatter, генерируемая `frontmatter.py`, для projects/tools имеет вид `[[<slug>|<display_name>]]`, где `slug` совпадает с ключом в `entities.json`, `display_name` — с полем той же записи.
    - Для rooms — `[[<room_slug>|<canonical_display>]]`, `room_slug` из `slugify_room`, `canonical_display` — имя без пометки вместимости и ` - Zoom`.
    - Backwards-scan: если во входном файле уже есть старая ссылка формата `[[slug]]` (без pipe, от гипотетического старого прогона) — MOFS её **не апгрейдит** без `--rematch --bucket <bucket>` (стабильность истории), но при `--rematch` — апгрейдит.

8. **`test_schema_charter_tags.py`**
   - Существующие 19 записей entities.json продолжают валидироваться после патча схемы.
   - `charter` со строкой не из цифр → validation error.
   - `charter` у `kind=one_on_one` — валиден (нет field-level инварианта).
   - `tags: ["tool", "tool"]` (не-уникальные) → validation error.

11. **`test_bootstrap_undo.py`** *(добавлено в v0.4.0)*
    - **Snapshot фиксирует состояние ДО.** Прогон бутстрапа на sandbox-архиве из 3 встреч → в `state/` появился ровно один `bootstrap_manifest_<ts>.json`, его `meetings[].frontmatter_before` для каждой из 3 встреч байт-в-байт совпадает с тем, что было в файле до вызова CLI.
    - **`--dry-run` undo не мутирует.** `mofs bootstrap --undo latest --dry-run` → sha256 всех файлов встреч, карточек, реестров идентичны состоянию ПОСЛЕ бутстрапа. Ни одного изменения на диске. stdout содержит план.
    - **Реальный undo без ручных правок — byte-exact rollback.** После бутстрапа сразу `--undo latest --yes` → frontmatter каждой встречи идентичен snapshotу ДО (sha256 канонизированного YAML). Тело файла ниже frontmatter — не тронуто. Карточки, созданные бутстрапом, — удалены. Карточки, существовавшие ДО, — на месте. Реестры — байт-в-байт как в snapshot.
    - **Undo не трогает pre-existing карточки.** Фикстура: `Projects/metroteka.md` существует до бутстрапа с ручным содержимым. Бутстрап фиксирует её в `cards_existing_before[projects]`. Undo НЕ удаляет.
    - **Undo не трогает карточки, дополненные вручную после бутстрапа.** Бутстрап создал `Tools/newtool.md`. Симулируем ручную дописку. Undo видит расхождение sha256 → пропускает, лог `WARN: card ... skipped from undo`.
    - **Записи `manual_via_mofs` не откатываются никогда (D7 п.2).** Между бутстрапом и undo Саша выполнил `mofs edit --meeting-id X --bucket projects --add sputnik --note "..."` — в реестре появилась запись `{slug:"sputnik", provenance:"manual_via_mofs", ...}`, во frontmatter — `[[sputnik|Sputnik]]`. Undo применяется → запись `sputnik` в реестре и frontmatter **остаётся**, `mofs_auto`-записи бутстрапа — вычеркнуты. Никаких WARN.
    - **Прямая правка frontmatter в обход `mofs edit` → безусловный skip всей встречи (D7 п.3 — fallback safety-net).** Между бутстрапом и undo симулируем прямую правку файла: во frontmatter встречи в `projects` руками добавили `[[somesluginfile]]` (без обращения к `mofs edit`, поэтому в реестре записи нет и `frontmatter_after_bootstrap` из манифеста не совпадает с текущим состоянием). Undo видит расхождение → встреча помечается `SKIPPED_CONFLICT`, файл не тронут, лог: `WARN: встреча ... пропущена при undo — обнаружено расхождение frontmatter с манифестом, не объяснённое provenance manual_via_mofs`.
    - **`mofs_auto`-запись, не изменённая в обход, — откатывается нормально.** Стандартный случай: между бутстрапом и undo Саша ничего не трогал → undo вычёркивает все `mofs_auto`/`mofs_llm_fallback`-записи из frontmatter и реестра, файл возвращается к состоянию `frontmatter_before`.
    - **Тексты summary/transcript не тронуты никогда.** sha256 `*-transcript.md` до бутстрапа == после бутстрапа == после undo.
    - **Ротация манифестов.** 6 последовательных `--snapshot` → в `state/` ровно 5 самых свежих. `.pinned.json` — не удаляется.
    - **Каскадный undo запрещён.** Повторный `--undo` уже отменённого манифеста → отказ. `--undo` более старого при наличии свежего `.undone.json` → отказ. `--force --yes-i-really-mean-it` — работает.

12. **`test_manual_edit.py`** *(добавлено в v0.5.0)*
    - `mofs edit --add <slug>` создаёт запись в реестре с `provenance == "manual_via_mofs"`, полями `added_at` (валидный ISO) и `note` (если передан).
    - Wiki-ссылка во frontmatter встречи побайтово идентична той, что создаёт автоматический матчинг для того же slug (общий рендерер `frontmatter.py::render_link()`).
    - `--add` для slug, отсутствующего в источнике-истине (`entities.json` / `contacts.enc` / `meeting-rooms.md`), — ошибка, никаких мутаций.
    - `--add` для slug, уже присутствующего в реестре встречи, — ошибка «already present», никаких мутаций.
    - `--add --bucket tools <slug>`, где `<slug>` в `entities.json` имеет `kind=project` без `tags=["tool"]` — ошибка.
    - `--remove <slug>` удаляет запись из реестра и wiki-ссылку из frontmatter (match по `target`); разрешено для любого `provenance`.
    - `--remove` для отсутствующей записи — ошибка «not present», никаких мутаций.
    - Атомарность: симулируем падение записи реестра после успешной правки frontmatter → компенсирующий rollback возвращает frontmatter к предыдущему состоянию.
    - `mofs edit` не мутирует другие ключи frontmatter — тест сверяет байт-в-байт всё, кроме целевой корзины.

13. **`test_review_filters.py`** *(добавлено в v0.6.0)*
    - **Фильтр по одному условию (slug).** Реестр-фикстура с 5 встречами, где `projects.matched` содержит `trisigma` у трёх из них. `apply_filters(data, {"slug": "trisigma"})` возвращает ровно эти 3 встречи, в остальных полей `matches` нет.
    - **Комбинация slug+date_range (AND, не OR).** Из тех же 3 встреч с `trisigma` две попадают в диапазон `--from 2026-07-10 --to 2026-07-20`, одна — вне. `apply_filters(data, {"slug": "trisigma", "date_from": "2026-07-10", "date_to": "2026-07-20"})` возвращает 2 встречи. Отдельная проверка: если бы логика была OR — вернула бы 4+ (все с trisigma ИЛИ все в диапазоне). Значит проверяем AND явно.
    - **Фильтр по provenance.** Фикстура: 4 встречи, из них 2 имеют `mofs_llm_fallback`-запись, 1 — `manual_via_mofs`, 3 — `mofs_auto`. `apply_filters(data, {"provenance": "mofs_llm_fallback"})` → 2 встречи, в возвращаемых `matches` — только записи с этим provenance (не все записи встречи).
    - **Фильтр по bucket.** `apply_filters(data, {"buckets": ["tools"]})` возвращает только встречи с непустой `tools.matched`, во всех остальных корзинах фильтр не проверяется.
    - **Мульти-bucket.** `apply_filters(data, {"buckets": ["projects", "tools"]})` возвращает встречи, где хотя бы одна из двух корзин удовлетворяет остальным критериям (при отсутствии других — где непустая projects ИЛИ непустая tools). Внутри одной встречи возвращаются оба bucket-блока, если оба удовлетворяют.
    - **`count()` — корректное число.** `count(apply_filters(data, filters))` совпадает с `len(apply_filters(data, filters))` — тривиальная проверка, но фиксирует контракт, что `--count` не запускает отдельного второго прохода с другой логикой.
    - **`render_json()` — валидный JSON.** `json.loads(render_json(results))` не падает, структура соответствует описанной в §Просмотр и ревью матчей (каждый элемент — dict с ключами `meeting_id, meeting_path, meeting_date, bucket, matches`).
    - **`render_text()` — детерминированность.** Двойной вызов на одном и том же входе даёт байт-в-байт идентичный вывод (сортировка стабильна).
    - **Пустой фильтр.** `apply_filters(data, {})` возвращает все встречи со всеми непустыми корзинами (deconstruction реестра в плоский список, без потерь).
    - **Отсутствующий slug.** `apply_filters(data, {"slug": "nonexistent"})` → пустой список (не ошибка).
    - **Изоляция от CLI.** Файл `test_review_filters.py` НЕ импортирует ни `cli.py`, ни `argparse` — работает только с `review.py::apply_filters` и рендер-функциями. Это структурное подтверждение чистоты модуля.
    - **`--count` и `--json` взаимоисключающи в CLI.** Отдельный тонкий тест на уровне `cli.py` (в том же файле): вызов CLI с обоими флагами одновременно → non-zero exit code + сообщение об ошибке в stderr.

## Ручные правки frontmatter — `mofs edit`
*Раздел добавлен 18.07.2026 (v0.5.0) как реализация D7 (решение Саши).*

### Мотивация и принцип

В экосистеме MOFS уже действуют жёсткие соглашения о единственном пути правки для каждого источника: **люди — только через `contacts.enc`** (AnywhereContacts), **сущности — только через `entity-registry` CLI**, **переговорки — только через `orglookup rooms`**. По симметрии frontmatter встреч в части MOFS-ключей (`contacts`/`projects`/`tools`/`rooms`) правится **только через MOFS** — либо автоматически (матчинг), либо вручную через штатную команду `mofs edit`. Прямая правка в текстовом редакторе / Obsidian физически возможна (MOFS не может запретить редактирование текстового файла), но выходит из-под гарантий инструмента: fallback-детекция undo будет считать такие правки конфликтом и защитно пропускать встречу.

### Команда

```
mofs edit --meeting-id <id> --bucket contacts|projects|tools|rooms --add <slug>    [--note "..."]
mofs edit --meeting-id <id> --bucket contacts|projects|tools|rooms --remove <slug>
```

- `--meeting-id` — идентификатор встречи (тот же, что и в `_mark_objects_registry.json.meetings.<id>`; ассоциация с файлом — через `files.summary`).
- `--bucket` — одна из четырёх корзин. Правка сразу в нескольких корзинах — отдельными вызовами.
- `--add <slug>` — добавить запись:
  - Валидировать, что `<slug>` существует в источнике-истине корзины: `contacts.enc` (для `contacts`, ключ = email), `entities.json` (для `projects`/`tools`; для tools дополнительно проверка `kind == "tool"` OR `"tool" in tags`), `meeting-rooms.md` (для `rooms`, ключ = `slugify_room(canonical_name)`). Если нет — ошибка, никаких мутаций.
  - Прочитать текущий frontmatter файла встречи, добавить wiki-ссылку в формате pipe-alias `[[<slug>|<display>]]`, идентичном автоматическому матчингу (Шаг 6 алгоритма). Дедупликация: если ссылка на этот `slug` уже есть — ошибка «already present» (никаких молчаливых no-op).
  - Записать в `_mark_objects_registry.json.meetings.<id>.<bucket>.matched` новую запись `{ "slug": "...", "provenance": "manual_via_mofs", "added_at": "<ISO-timestamp>", "note": "<...>"? }`. Note — только если передан `--note`.
  - Атомарная запись обоих файлов (frontmatter встречи и реестр) под single-instance lock (`portalocker`), сначала tmp+rename для файла встречи, затем для реестра; если второй шаг падает — компенсирующий rollback первого шага из in-memory snapshot.
- `--remove <slug>` — удалить запись:
  - Валидировать, что запись с этим slug реально есть в реестре для этой встречи (иначе ошибка, никаких no-op).
  - **Разрешено удалять записи с любым `provenance`** (в том числе `mofs_auto` / `mofs_llm_fallback`) — это единственный штатный способ убрать ложноположительный матч и правильно пометить факт удаления. Удаление регистрирует в реестре аудит-запись — TODO v0.6: пока в v0.5 запись просто вычёркивается из `matched`, без отдельного лога «удалено вручную». Если по факту эксплуатации окажется, что аудит-трейл нужен — добавить в v0.6 массив `removed_manually: [{slug, at, note}]` в подсекцию корзины.
  - Из frontmatter встречи вычеркивается wiki-ссылка на этот slug (match по `target`, display игнорируется).

### Гарантии

- **Формат wiki-ссылки идентичен автоматическому** — та же `frontmatter.py::render_link()` вызывается и матчингом, и `mofs edit`. Тест `test_manual_edit.py` проверяет побайтовую эквивалентность результата.
- **`mofs edit` — не мутирует другие ключи frontmatter** (заголовок, participants, кастомные пометки Саши) — только целевая корзина.
- **Идемпотентности как таковой у команды нет** (в отличие от `mofs run`): повторный `--add` даёт ошибку «already present», повторный `--remove` — «not present». Это сознательный выбор — команда императивная, не декларативная.

## Просмотр и ревью матчей — `mofs review`

*Раздел добавлен 18.07.2026 (v0.6.0). Мотивация — после тестового прогона (например, dry-run на диапазоне июнь-июль или после первого реального бутстрапа) Саше нужен способ посмотреть, что именно смэтчилось на каждую сущность, не ходя в Obsidian и не читая `_mark_objects_registry.json` руками. Основной use-case — оценка качества матчинга по конкретной сущности и поиск ложных срабатываний.*

### Назначение

Дать инструмент инспекции матчей по сущностям/корзинам/датам/провенансу — чтобы отличить два сценария:

- **Сценарий А — плохой/слишком широкий алиас в `entities.json`.** Много встреч смэтчилось на один slug ошибочно. Решение — правка `aliases` через `entity-registry edit`, затем `mofs rematch --bucket projects --all`.
- **Сценарий Б — конкретная встреча смэтчена неверно.** Точечная правка через уже спроектированную `mofs edit --remove <slug>` / `--add <slug>`.

`mofs review` — read-only, никаких мутаций ни в frontmatter, ни в реестре, ни в карточках. Читает только `_mark_objects_registry.json` (плюс, при необходимости, имена файлов встреч для отображения). Никаких side-effects.

### Команда и фильтры

```
mofs review [--bucket <b>[,<b>...]|--bucket <b> --bucket <b>]
            [--slug <slug>]
            [--from YYYY-MM-DD --to YYYY-MM-DD]
            [--provenance mofs_auto|mofs_llm_fallback|manual_via_mofs]
            [--count | --json]
```

- `--bucket contacts|projects|tools|rooms` — какая корзина. Можно несколько (через запятую или повторный флаг, по аналогии с `--bucket` в `rematch`). По умолчанию — все четыре.
- `--slug <slug>` — конкретная сущность (проект/инструмент/переговорка/контакт-ключ). Матч по ключу записи в `matched` (для contacts ключ — email, для остальных — slug).
- `--from <YYYY-MM-DD> --to <YYYY-MM-DD>` — диапазон дат по имени файла встречи (тот же парсер даты из имени, что используется в `mofs rematch --from --to`; обе границы включительно).
- `--provenance <val>` — фильтр по происхождению матча (`mofs_auto` / `mofs_llm_fallback` / `manual_via_mofs`). Особо полезно для `--provenance mofs_llm_fallback` — прицельный просмотр менее надёжных LLM-матчей.
- **Композиция — логическое AND**: все указанные условия одновременно. Не OR. Отсутствие фильтра — «любое значение».

### Вывод

**Дефолт** (без `--count` и без `--json`) — компактный текстовый список в stdout, по одной встрече на блок:

```
2026-07-15  NewMeetings/2026-07-15-standup-summary.md  [projects]
  - trisigma          (mofs_auto)
  - ml_platforma      (mofs_llm_fallback, confidence=0.91)
2026-07-17  NewMeetings/2026-07-17-review-summary.md   [projects]
  - trisigma          (manual_via_mofs, note="упомянут устно")
```

- Строка встречи: дата (из имени файла) + путь + список корзин, по которым встреча попала под фильтр (в квадратных скобках).
- Строки матчей: slug, provenance; для `mofs_llm_fallback` — `confidence` из реестра; для `manual_via_mofs` — `note` если есть.
- Сортировка — по дате встречи ASC (старые сверху; переопределяемый в будущем через `--sort`, но в v0.6 — фиксированная).

**`--count`** — вместо списка, единственное число в stdout (сколько встреч попало под фильтр). Полезно для быстрой оценки масштаба перед `mofs review ... > /tmp/out.md`.

**`--json`** — массив объектов, валидный JSON, для машинной обработки (пример — Саша хочет проанализировать через `execute_code`):

```jsonc
[
  {
    "meeting_id": "abc123",
    "meeting_path": "NewMeetings/2026-07-15-standup-summary.md",
    "meeting_date": "2026-07-15",
    "bucket": "projects",
    "matches": [
      { "slug": "trisigma", "provenance": "mofs_auto" },
      { "slug": "ml_platforma", "provenance": "mofs_llm_fallback", "confidence": 0.91 }
    ]
  }
]
```

Комбинации `--count --json` запрещены (взаимоисключающие) — CLI отвергает с ошибкой на этапе argparse.

### Архитектурное требование — изоляция фильтр-логики

**Реализовать функцию `apply_filters(registry_data: dict, filters: dict) -> list[MatchedMeeting]`** (`review.py`) как **изолированный, чистый модуль**, где:

- Вход — уже загруженное содержимое `_mark_objects_registry.json` (обычный `dict`) + структура-описание фильтров (`{"buckets": [...], "slug": ..., "date_from": ..., "date_to": ..., "provenance": ...}`).
- Выход — плоский список результатов (dataclass или TypedDict `MatchedMeeting` с полями `meeting_id, meeting_path, meeting_date, bucket, matches`). Никакого форматирования, никакого stdout, никаких argparse-объектов.
- Функция чистая: без чтения диска, без сети, без глобального state, без логгирования. Идентичный вход → идентичный выход.
- CLI-слой (`cli.py`) остаётся тонким: парсит `argparse.Namespace` → строит `filters: dict` → вызывает `apply_filters()` → форматирует результат в text/count/json. Никакой фильтр-логики (условий, циклов по `matched`) в `cli.py` быть не должно — только парсинг аргументов и вывод.
- Рендер-функции — тоже отдельные: `render_text(results) -> str`, `render_json(results) -> str`, `count(results) -> int`. В `review.py` рядом с `apply_filters`, но каждая — узкая, тестируемая изолированно.

**Зачем такая строгость.** Если в будущем появится второй реальный потребитель фильтрации по entities.json-сущностям (например, `TaskRefresh` или `AggregateFromMeetings` захотят инспектировать свой аналог реестра теми же критериями), функцию `apply_filters` можно будет за 10 минут вынести в общий пакет `~/USERTOOLS/common/registry_filters/` без переписывания. Сейчас она живёт внутри MOFS.

### Что решено НЕ делать сейчас (важно, зафиксировано)

**НЕ строим общую переиспользуемую библиотеку фильтров для всей экосистемы USERTOOLS в v0.6.** Это преждевременное обобщение (тот же YAGNI-принцип, что применялся весь день к остальным решениям — минимальный вариант, не полноценная фича про запас). У `TaskRefresh` уже есть **своя** рабочая логика фильтров F1-F6 — её не трогаем, она не является потребителем `_mark_objects_registry.json` и работает по другому источнику данных. Общий модуль `common/registry_filters/` — **future work**, если появится ВТОРОЙ реальный потребитель с похожими требованиями по фильтрации по entities.json-сущностям. Пока такой потребитель один (сам MOFS через `mofs review`) — обобщать нечего. Единственное, что делается сейчас в счёт будущего выноса, — архитектурная изоляция функции `apply_filters` внутри MOFS (см. выше), чтобы момент выноса был дешёвым.

### Что `mofs review` НЕ делает

- Не изменяет ни один файл (read-only).
- Не вызывает LLM (никакого re-scoring, никаких «а точно ли это Trisigma?»).
- Не открывает файлы встреч (кроме отображения пути в выводе) — все данные берутся из реестра.
- Не работает с `unmatched_candidates.json` — это отдельная задача дайджеста (`mofs digest`).
- Не показывает «сколько было бы смэтчено при других алиасах» — это не симулятор, а инспектор факта.

## Bootstrap — снапшот и откат (`--undo`)

*Раздел добавлен 17.07.2026 (v0.4.0), обновлён 18.07.2026 (v0.5.0 — решение D7: поведение undo при ручных правках теперь строится на provenance-модели, см. §Ручные правки frontmatter — `mofs edit`).*

### Мотивация

Бутстрап (`mofs rematch --all --bucket projects,tools,rooms`) — редкая, тяжёлая, широкоохватная мутация: правит frontmatter сотен файлов встреч и создаёт десятки/сотни новых карточек-заглушек. Если по итогу выяснится, что качество матчинга кривое (много false-positive, ошибка в новом алиасе, забытая коллизия), — ручной откат нереален. Нужен машинный undo с гарантиями:

- **Тексты встреч (summary/transcript) — неприкосновенны.** Undo НИКОГДА не трогает тело `*-summary.md`/`*-transcript.md` ниже YAML-frontmatter.
- **Ручная работа Саши — неприкосновенна.** Карточки, созданные вручную ДО бутстрапа, и карточки, дополненные вручную ПОСЛЕ него, — undo не трогает вообще.
- **Другие frontmatter-ключи — неприкосновенны.** Undo убирает ТОЛЬКО те значения из `contacts`/`projects`/`tools`/`rooms`, которые реально добавил ЭТОТ прогон бутстрапа. Ключи, значения и разметка v0.1 (частичные контакты, добавленные раньше) — остаются.

### Снапшот ДО бутстрапа

**Триггер.** Автоматически как **шаг 0** любого прогона в bootstrap-режиме. Bootstrap-режим — это `mofs rematch --all` с любой из корзин `projects/tools/rooms/all` (не `contacts`), либо явный `mofs bootstrap --snapshot` (снимает снапшот без запуска бутстрапа — используется для отладки/страховки перед экспериментами). Обычные ежедневные `mofs run` снапшот НЕ снимают (это не бутстрап, а инкремент по 1-5 новым встречам за такт — риск-профиль другой, откат делается через git NewMeetings-репо или руками).

**Файл манифеста.** `~/USERTOOLS/MarkObjectsFromSummary/state/bootstrap_manifest_<UTC-timestamp>.json`, где timestamp — `YYYYMMDDTHHMMSSZ` (например `20260717T183045Z`). Права `0600`. JSON, schema_version `1.0`.

**Содержимое манифеста:**

```jsonc
{
  "schema_version": "1.0",
  "created_at_utc": "2026-07-17T18:30:45Z",
  "mofs_version": "0.4.0",
  "cli_invocation": "mofs rematch --all --bucket projects,tools,rooms",
  "buckets": ["projects", "tools", "rooms"],
  "meetings": [
    {
      "path": "/home/tkachenkoav/WorkVault/NewMeetings/2026-07-15-standup-summary.md",
      "meeting_id": "abc123",
      "frontmatter_before": { /* полный dict YAML-шапки ДО бутстрапа */ },
      "frontmatter_sha256": "…",   // хэш канонизированного YAML-дампа frontmatter_before, для детекта конфликта на undo
      "expected_added_by_bootstrap": {  // v0.5: что ИМЕННО этот бутстрап добавил (по корзинам) — источник истины для undo
        "contacts": [],
        "projects": ["trisigma", "ml_platforma"],
        "tools":    ["metroteka"],
        "rooms":    ["dzhungli"]
      },
      "frontmatter_after_bootstrap": { /* полный dict YAML-шапки СРАЗУ ПОСЛЕ записи бутстрапом — используется fallback-детекцией undo для сверки, что frontmatter не правили в обход `mofs edit` */ }
    },
    …
  ],
  "cards_existing_before": {
    "projects": ["metroteka", "trisigma", …],   // slug-и, для которых Projects/<slug>.md УЖЕ существовал
    "tools":    ["jira", …],
    "rooms":    ["dzhungli", …]
  },
  "registry_snapshot": {
    "path_original": "/home/tkachenkoav/USERTOOLS/MarkObjectsFromSummary/_mark_objects_registry.json",
    "content": { /* полное содержимое файла ДО бутстрапа */ }
  },
  "candidates_snapshot": {
    "path_original": "/home/tkachenkoav/USERTOOLS/MarkObjectsFromSummary/unmatched_candidates.json",
    "content": { /* полное содержимое ДО бутстрапа */ }
  }
}
```

**Почему `frontmatter_before` целиком, а не только MOFS-ключи.** Чтобы undo мог посчитать точный diff «что MOFS добавил в бутстрапе» через сравнение `frontmatter_before` vs `frontmatter_now`. Без полного `before` невозможно отличить, добавил ли значение бутстрап или это уже было. Frontmatter — компактный (обычно <2КБ), сотни встреч × 2КБ = <1МБ манифест, приемлемо.

**Атомарность записи манифеста.** Пишется через `tmp+rename` (atomic write); только после успешной записи манифеста бутстрап начинает мутировать первую встречу. Если снапшот падает — бутстрап не стартует, встречи не тронуты.

**`--dry-run` бутстрапа.** `mofs rematch --all --dry-run` — снапшот НЕ пишется (нет реальных мутаций), только лог планируемых изменений.

### Откат (`mofs bootstrap --undo`)

**Синтаксис.**

```
mofs bootstrap --undo <manifest_timestamp>    # откат конкретного манифеста
mofs bootstrap --undo latest                  # откат самого свежего манифеста в state/
mofs bootstrap --undo <ts|latest> --dry-run   # показать, что будет откачено, БЕЗ мутаций (обязательно перед реальным undo)
mofs bootstrap --list-manifests               # список манифестов в state/ + timestamp + краткая сводка (сколько встреч, сколько карточек)
```

**Алгоритм undo (реальный, не dry-run):**

1. Загрузить манифест `bootstrap_manifest_<ts>.json`. Валидировать `schema_version`.
2. **Фаза planning (проход без мутаций).** Для каждой встречи из `meetings[]`:
   - Прочитать текущий frontmatter файла (`frontmatter_now`) и текущую запись реестра `_mark_objects_registry.json.meetings[<id>]` (`registry_now`).
   - Разделить провенансы в `registry_now.<bucket>.matched` на три группы:
     - `to_undo = { item | item.provenance ∈ {"mofs_auto", "mofs_llm_fallback"} ∧ item.slug ∈ manifest.expected_added_by_bootstrap[<id>][<bucket>] }` — записи, которые именно этот бутстрап реально добавил (пересечение с манифестом обязательно, чтобы не откатить чужой прогон).
     - `to_keep_manual = { item | item.provenance == "manual_via_mofs" }` — **никогда** не трогаются undo, ни по каким условиям (D7-решение Саши, п.2). Это ядро контракта: `manual_via_mofs` = «человек через штатный путь», undo видит и обходит.
     - `to_keep_other = registry_now.<bucket>.matched \ (to_undo ∪ to_keep_manual)` — записи, добавленные другими прогонами (например, ежедневным `mofs run` между бутстрапом и undo) — тоже сохраняются.
   - **Fallback safety-net (D7-решение Саши, п.3) — обнаружение расхождения frontmatter ↔ манифест для записей, помеченных как `mofs_auto`/`mofs_llm_fallback`:**
     - Для каждого элемента `to_undo` проверить, что соответствующая wiki-ссылка `[[<slug>|<display>]]` физически присутствует в текущем `frontmatter_now.<bucket>` в том же формате, в котором её записал бутстрап (сравнение через нормализацию: match по `target` = `slug`, display-часть игнорируется — переименование через `entity-registry edit` display'я не считается конфликтом).
     - Дополнительно — сверить набор `target`-ов в `frontmatter_now.<bucket>` (только `mofs_auto`/`mofs_llm_fallback`-часть, вычисляемая по `registry_now.<bucket>.matched`) с тем, что зафиксировано в манифесте (`meeting.frontmatter_after_bootstrap[<bucket>]`, добавляемое в манифест на этапе снапшота).
     - Если **любое** расхождение обнаружено (кто-то — Саша или другой процесс — руками отредактировал frontmatter в обход `mofs edit`: добавил, убрал, изменил target `mofs_auto`-записи) — встреча целиком помечается `SKIPPED_CONFLICT`, undo этой встречи **не применяется вообще** (файл не трогается), лог: `WARN: встреча <path> пропущена при undo — обнаружено расхождение frontmatter с манифестом, не объяснённое provenance manual_via_mofs (возможна прямая правка frontmatter в обход mofs edit)`.
     - Если расхождений нет — undo применяется: из frontmatter вычёркиваются ровно wiki-ссылки, соответствующие `to_undo`; записи `to_keep_manual` и `to_keep_other` остаются нетронутыми (это гарантия безопасности штатного пути правок через `mofs edit`, работает детерминированно, без эвристик).
3. **Фаза planning для карточек.** Для каждой корзины `projects/tools/rooms`:
   - Найти все карточки, СЕЙЧАС существующие в `Projects/`/`Tools/`/`Rooms/`, соответствующие slug-ам из `_mark_objects_registry.json` бутстрап-прогона.
   - Кандидаты на удаление = `{slug сейчас существующих} - {cards_existing_before[bucket]}` — то есть только реально созданные ЭТИМ бутстрапом.
   - Для каждой карточки-кандидата — проверить, не менялся ли её `mtime`/`sha256` относительно того, что записал бутстрап (в `_mark_objects_registry.json` фиксируется sha256 карточки на момент создания). Если хэш совпадает — карточка не тронута руками, удалить. Если хэш другой — Саша дописал что-то, карточка помечается `SKIPPED_CONFLICT`, не удаляется, в лог: `WARN: card <path> skipped from undo — modified after creation`.
4. **Фаза planning для реестров.** `_mark_objects_registry.json` и `unmatched_candidates.json` — полная перезапись из `registry_snapshot.content` / `candidates_snapshot.content`. Тут конфликта нет: файлы целиком принадлежат MOFS, ручных правок в них по контракту не бывает. Но: если между бутстрапом и undo был обычный ежедневный `mofs run` — он мог дописать новых записей за новые встречи; их полная перезапись СНЕСЁТ. Это **допустимое** поведение undo (undo — операция крупноблочная, обычные daily-обновления после undo надо перезапустить через `mofs rematch --meeting-id <X>` по нужным встречам). В логе undo — предупреждение: `INFO: registry rewound to bootstrap-time snapshot; N daily entries after bootstrap will be lost, run 'mofs rematch --from <bootstrap_ts>' to re-mark them`.
5. **Атомарность.** До начала мутаций — вывести plan-summary (сколько встреч будет откачено, сколько пропущено по конфликту, сколько карточек удалено, сколько пропущено). Если пользователь не подтвердил (`--yes` обязателен для реального undo вне `--dry-run`) — abort. При старте мутаций — сначала пишется файл-локер `state/undo_in_progress_<ts>`. Если процесс падает посередине — при следующем запуске undo, если найден локер, спросить: продолжить с места падения (по journal-у, см. ниже) или abort. Практически: undo пишет journal (`state/undo_journal_<ts>.jsonl`) построчно перед каждой мутацией — на случай fault-recovery. По окончании успешного undo локер и journal удаляются, манифест переименовывается в `bootstrap_manifest_<ts>.undone.json` (не удаляется — история).
6. **Порядок применения:**
   1. Frontmatter встреч (по одной, atomic tmp+rename).
   2. Карточки-заглушки (удаление файлов).
   3. Реестры (полная перезапись из snapshot).
7. **Лог отката.** В общий `_log.md` MOFS одна итоговая строка формата: `UNDO 2026-07-18T09:12:00 manifest=20260717T183045Z meetings=487/512(25 skipped) cards_removed=34/38(4 skipped) registry=rewound`. Плюс jsonl-events per-file — как в остальном MOFS.

**`--dry-run` undo.** Ровно тот же planning-проход (шаги 1–3), но никаких мутаций и никакого journal-а. Вывод на stdout — план в человекочитаемом виде + сводка + список skipped-конфликтов с указанием, что именно Саша поменял (diff-выжимка). Обязателен перед реальным undo как контракт: любой реальный `--undo` без предваряющего `--dry-run` в CLI выводит warning и требует явного `--yes --i-know-what-i-do`.

### Ротация манифестов

Бутстрап — редкая операция (не чаще раза в 2-4 недели ожидается; после первого прогона повторные бутстрапы будут при добавлении крупных пачек новых сущностей или при пересмотре D3-порога). Держать вечно все манифесты не нужно (каждый — до 1МБ + journal), но и агрессивно чистить не стоит — на разбор проблемы может уйти месяц.

**Правило:** хранить последние **5** манифестов в `state/`. При каждом новом `--snapshot` — старше 5-го удаляются (файлы `bootstrap_manifest_*.json`, включая `.undone.json`). Обоснование: EntityRegistryCLI держит 20 бэкапов, потому что write-ов в реестр много и они частые; MOFS-бутстрапов ожидается на порядки меньше, 5 покрывает историю на квартал-полгода. Если Саша хочет сохранить конкретный манифест дольше — руками переименовать в `bootstrap_manifest_<ts>.pinned.json` (суффикс `.pinned` выводит из ротации; реализация — простой skip по маске имени).

### Что запрещено undo (правила безопасности)

- **Нет крона на undo.** Undo — только ручной вызов Саши. Никогда не по расписанию, никогда не автоматически как реакция на что-либо (даже на «плохой лог бутстрапа»). Симметрично тому, что EntityRegistryCLI НЕ имеет pre-commit hook (решение Саши: инвазивные автоматизации должны требовать явной команды). Это **инвариант**, не рекомендация.
- **Нет undo для `mofs run` (обычный ежедневный такт).** Undo только для bootstrap-манифестов. Обычный такт мутирует 1-5 файлов, откат делается через git архива `NewMeetings` или ручной правкой frontmatter — писать под это отдельный механизм не окупается.
- **Нет каскадного undo.** Manifest A → undo применён → потом Manifest B (более старый) → undo НЕЛЬЗЯ применить (реестр уже не соответствует состоянию до B). CLI отказывается, если находит более свежий `.undone.json` манифест, чем запрашиваемый. Обход — только через `--force` + явное `--yes-i-really-mean-it` (не документируется в help, только в этом ТЗ).

## Крон-планы

```
# Основной такт MOFS v0.2 — раз в день после последнего синка FF
mofs_daily     0 21 * * 1-5   mofs run --mode cron

# Еженедельный дайджест несмэтченных
mofs_digest_weekly   0 9 * * 1   mofs digest

# MOFS v0.1 — контакты, сразу после каждого синка MoveFromFF
mofs_contacts_hourly   5 10-20 * * 1-5   mofs run --mode cron --bucket contacts
```

Все три через `cronjob(action='create', ...)` Hermes, с осмысленными именами (не hex job_id).

**Правило: undo НЕ имеет крона.** `mofs bootstrap --undo` не появляется ни в одном расписании — ни здесь, ни где-либо ещё. Только ручной вызов Саши после явного разбора причины и `--dry-run`. Обоснование симметрично решению Саши по EntityRegistryCLI (нет pre-commit hook): инвазивные, широкоохватные, потенциально разрушительные операции — только по явной команде, никогда не по расписанию и никогда как автоматическая реакция на что-либо.

## Критерии успеха

1. **Схема `entities.schema.json`** обновлена, все 19 существующих записей продолжают проходить валидацию (`entity-registry validate` → OK).
2. **MOFS v0.1 (контакты)** реализован и отработал минимум 1 полный день на новых встречах, `_mark_objects_registry.json` содержит валидные записи contacts для всех новых summary с датой ≥ дня запуска, ни одна встреча не потеряна.
3. **MOFS v0.2** реализован и отработал первый вечерний прогон: для каждой обработанной встречи frontmatter содержит поля `projects/tools/rooms` (могут быть пустые списки, но поля есть), реестр содержит подсекции. Ложных матчей нет (ручная проверка первых 5 встреч).
4. **Очередь несмэтченных** — файл `unmatched_candidates.json` создан, накопление корректное на 5+ прогонах подряд (счётчики монотонно неубывают без `--rematch`).
5. **Дайджест** — первый понедельник прогона рендерит `.md`-файл с сортировкой по `count DESC`, TG-уведомление доставлено, топ-1 в TG совпадает с топ-1 в файле.
6. **Идемпотентность** — повторный `mofs run` без изменений на диске: 0 новых обработок, реестр не тронут, очередь не тронута, frontmatter не тронут.
7. **`--rematch --bucket projects --all`** после `entity-registry add <new_slug>` — новая сущность подхватывается на всём архиве, старые контакты не переразмечаются (не подцепляется побочно).
8. **Формат pipe-alias корректен.** Ручная проверка первых 5 обработанных встреч: все строки `projects/tools/rooms` во frontmatter имеют вид `[[<target>|<display>]]`, ни одной голой ссылки `[[slug]]`. Автотест `test_pipe_alias_format.py` зелёный.
9. **`card_writer.py` idempotent.** После первого прогона в `WorkVault/Projects/`, `Tools/`, `Rooms/` появились файлы-заглушки для всех уникальных матчей. Ручная правка одной из карточек (добавить произвольную строку) → повторный прогон MOFS: файл сохранён байт-в-байт (`sha256` до и после совпадает), `_mark_objects_registry.json` не отмечает попытку записи. Автотест `test_card_writer.py` зелёный.
10. **Все тесты (~35 тестов) зелёные.** Baseline PFS 151/151 и TaskRefresh 112/112 после патча `entities.schema.json` — прежние.
11. **Не тронуты:** `route.py`, `entities.json` содержимое (кроме случаев, когда Саша сам добавляет `charter`/`tags`), `contacts.enc` write-path, PFS ROUTES, TaskRefresh ProjectRegistry, meeting-rooms.md. Ранее созданные вручную карточки в `Projects/`/`Tools/`/`Rooms/` — не тронуты (idempotent-контракт).
12. **Bootstrap undo работает end-to-end** *(v0.4.0)*. На тестовом sandbox-архиве из ≥3 встреч: (а) `mofs rematch --all` пишет manifest в `state/`; (б) `mofs bootstrap --undo latest --dry-run` показывает корректный план без мутаций; (в) `mofs bootstrap --undo latest --yes` возвращает frontmatter встреч и реестры к точному состоянию ДО бутстрапа (sha256 совпадает), удаляет только карточки, реально созданные бутстрапом; (г) тексты `*-summary.md` ниже frontmatter и все `*-transcript.md` — sha256-неизменны на всех трёх этапах; (д) карточка, дописанная руками после бутстрапа, пропускается undo с WARN; (е) встреча с ручной правкой в MOFS-ключах пропускается undo с WARN (поведение варианта B — до подтверждения D7). Автотест `test_bootstrap_undo.py` зелёный.
13. **`mofs review` работает и композирует фильтры корректно** *(v0.6.0)*. На той же sandbox-фикстуре: (а) `mofs review --slug trisigma` возвращает список встреч, реально содержащих `trisigma` в `matched`; (б) `mofs review --slug trisigma --from <D1> --to <D2>` возвращает подмножество (AND, не OR) — ровно те, что и в реестре И в диапазоне; (в) `mofs review --provenance mofs_llm_fallback` возвращает только LLM-фолбэк-матчи, `manual_via_mofs`- и `mofs_auto`-записи в выводе отсутствуют; (г) `mofs review --count` даёт число, совпадающее с `wc -l` списочного вывода того же запроса; (д) `mofs review --json | python -c "import json,sys; json.load(sys.stdin)"` не падает; (е) `mofs review` не пишет ни в один файл (проверка через `find <vault> <state> -newer <t0>` до и после — пусто); (ж) `test_review_filters.py` зелёный. Функция `apply_filters` не импортирует ничего из `cli.py`/`argparse` (структурный контракт изоляции).

## Решения Саши (бриф 16-18.07.2026 — D1-D7 закрыты)

Все семь решений закрыты (D1-D6 — бриф 16-17.07.2026; D7 — решение Саши 18.07.2026, зафиксировано в v0.5.0).

**D1. Формат wiki-ссылки — `[[slug|display_name]]` (pipe-alias Obsidian) во ВСЕХ трёх корзинах (projects/tools/rooms).**

*Отличается от первоначальной рекомендации Opus в v0.2.0* (было: голый `[[slug]]` с расчётом на будущий Dataview-хук в AFM модуле D). Финальное решение принято после дополнительного под-вопроса Саши о влиянии на скорость поиска: pipe-alias даёт читаемость в графе (`Trisigma`, `Метротека`, `Джунгли` вместо `trisigma`/`metroteka`/`dzhungli`) **без ущерба для стабильности target** — Dataview, backlinks и Obsidian-граф матчат по target=slug, а не по видимому тексту. Переименование `display_name` через `entity-registry edit` не ломает существующие ссылки. Стоимость реализации — одна строка в `frontmatter.py`. Для rooms target — детерминированный snake_case-транслит канонического имени (`Джунгли` → `dzhungli`), реализация в `rooms_reader.py::slugify_room`.

**D2. Создавать карточки-заглушки при первом матче — ДА, idempotent, по фиксированному шаблону.**

*Отличается от первоначальной рекомендации Opus в v0.2.0* (было: НЕ создавать, красные ссылки как сознательное состояние; передать ответственность в AFM модуль D). Финальное решение Саши: создаём **минимальные** заглушки прямо сейчас, потому что (а) единая точка агрегации backlinks нужна до реализации AFM модуля D — ускоряет `workvault-rag` и Dataview-запросы; (б) содержимое заглушки узкое и не пересекается с AFM (только `# display_name` + `dataview list from [[slug]]` + `kind` во frontmatter для projects/tools); (в) idempotent-контракт защищает ручные правки Саши — карточка создаётся один раз и никогда не перезаписывается, даже при `--rematch`; (г) для rooms — карточка без frontmatter (semантика `kind` неприменима к переговорке, искусственное `type: room` — раздувание схемы). Детали шаблона — Шаг 6.5 алгоритма и `templates/entity_card.md.j2` в §Пофайловый план. **Реализация — `card_writer.py`**.

**D3. Порог confidence LLM-фолбэка — 0.85 на старте, ревизия через 2 недели.**

Подтверждено Сашей. Соответствует первоначальной рекомендации Opus. Калибровка — по факту ручной проверки первой недели прогона (сколько ложноположительных на пороге 0.85). Пересмотр возможен в обе стороны (0.75 если очередь распухает без реального шума / 0.9 если ложных матчей больше 5%).

**D4. Гранулярность `--rematch --bucket` — 4 корзины: `contacts | projects | tools | rooms | all`.**

Подтверждено Сашей. Projects и tools матчатся одним циклом по `entities.json` — искусственное дробление на два независимых прохода не даёт выгоды. Rooms и contacts — отдельные корзины, потому что разные источники (`meeting-rooms.md` vs `contacts.enc`).

**D5. Коллизия алиасов между записями `entities.json` — multi-match + WARN в лог.**

Подтверждено Сашей. Оба (все) slug-а попадают в `matched`, в лог пишется `WARN: alias '<X>' matched multiple slugs: <s1>, <s2>`. Разбирается Сашей через `entity-registry edit`. Никаких скрытых приоритетов по `kind` или порядку записей — только явный WARN.

**D6. Бутстрап архива NewMeetings — без LLM-бюджета на старте.**

Подтверждено Сашей. Ретро-прогон запускается через 1-2 недели после старта на новых встречах командой `mofs rematch --all --bucket projects,tools,rooms`. Оценка: ~1000 встреч × ~5% LLM-фолбэк ≈ 50 Haiku-запросов, копейки. Если по факту окажется дороже (например, LLM-фолбэк срабатывает не 5%, а 30% из-за плохо покрытых алиасов) — добавить флаг `--llm-budget N` (лимит N вызовов на прогон, остальное в очередь). Пока флаг не реализуется.

*Уточнение v0.4.0:* срок «через 1-2 недели» теперь МЯГКИЙ — с появлением механики `--undo` (см. §Bootstrap — снапшот и откат) допустимо запустить бутстрап и раньше, если после нескольких дней ежедневного прогона качество матчинга кажется приемлемым. Undo как страховка снимает риск раннего запуска. Формальное решение о моменте запуска — за Сашей.

**D7. Поведение undo при ручных правках frontmatter между бутстрапом и `--undo` — РЕШЕНИЕ САШИ (18.07.2026).**

Саша принял третий, более фундаментальный подход, чем изначально предложенные варианты A («слепой diff-откат») и B («detect conflict → skip»). Вместо разрешения конфликта эвристиками — устраняется сам источник конфликта через провенанс-модель, симметричную уже действующим правилам «люди только через `contacts.enc`», «сущности только через `entity-registry` CLI», «переговорки только через `orglookup rooms`».

**Правило: frontmatter встреч в части MOFS-ключей (`contacts`/`projects`/`tools`/`rooms`) правится ТОЛЬКО через MOFS** — либо автоматически (Шаги 2-4 алгоритма матчинга), либо вручную через штатную команду `mofs edit` (см. §Ручные правки frontmatter — `mofs edit`).

**Механизм состоит из трёх частей:**

1. **Provenance на уровне каждой записи в реестре.** В `_mark_objects_registry.json.meetings.<id>.<bucket>.matched` каждая запись — объект с обязательным полем `provenance ∈ { "mofs_auto", "mofs_llm_fallback", "manual_via_mofs" }`. Первые два ставит алгоритм матчинга, третий — команда `mofs edit --add`. Формат подробнее — §Формат `_mark_objects_registry.json`, миграция 2.0 → 2.1.

2. **`bootstrap --undo` безусловно игнорирует записи с `provenance == "manual_via_mofs"`** — не сравнивает, не пытается угадать конфликт, просто никогда их не трогает. Откатывает только `mofs_auto`/`mofs_llm_fallback`-записи, реально добавленные конкретным бутстрапом (по `expected_added_by_bootstrap` из манифеста). Это делает undo для штатного пути (правки через `mofs edit`) полностью безопасным и детерминированным, без эвристик. Ручной труд Саши через штатную команду — неприкосновенен по контракту.

3. **Fallback safety-net на случай прямой правки frontmatter в обход `mofs edit`.** MOFS не может физически запретить редактирование текстового файла, только дать соглашение. Для случая нарушения соглашения (кто-то — Саша, другой процесс, ещё что-то — руками поменял frontmatter, не через `mofs edit`): undo при обработке каждой встречи из манифеста сверяет текущий frontmatter с `frontmatter_after_bootstrap` (что MOFS сам туда положил, зафиксировано в манифесте) в части `mofs_auto`/`mofs_llm_fallback`-записей. Если обнаружено расхождение, не объяснимое provenance-ом `manual_via_mofs` — undo для этой встречи пропускается **целиком** (файл не трогается вообще, никаких частичных откатов), лог: `WARN: встреча <id> пропущена при undo — обнаружено расхождение с манифестом, не объяснённое provenance manual_via_mofs (возможна прямая правка frontmatter в обход mofs edit)`.

**Плюсы решения:**
- Устраняет источник конфликта, а не борется с ним. Штатный путь правки через `mofs edit` не требует эвристик detect/skip — undo просто видит provenance и обходит.
- Симметрия с существующими правилами `contacts.enc`/`entity-registry`/`orglookup` — узнаваемый паттерн, не изобретение уникального механизма для MOFS.
- Fallback защищает от нарушения соглашения без риска потери данных: скорее пропустит встречу с WARN, чем откатит что-то поверх ручной правки.
- Обе автоматические стороны (матчинг и undo) — детерминированные и тестируемые.

**Минусы, принятые Сашей:**
- Требуется миграция реестра 2.0 → 2.1 (простая, атомарная).
- Появляется новая команда `mofs edit` и связанные тесты — стоимость реализации ~1 модуль + ~1 тестовый файл.
- Прямая правка в Obsidian по-прежнему возможна — MOFS не может её запретить, только детектировать и защитно пропускать при undo. Это принято как компромисс между удобством (иногда правка в Obsidian удобнее) и гарантиями (штатный путь даёт полные гарантии).

## Ссылки

- `TZ/EntityRegistry/EntityRegistry_TZ.md` v0.2.0 — базовая архитектура реестра.
- `TZ/EntityRegistryCLI/EntityRegistryCLI_TZ.md` v0.2.0 — единственный write-path в `entities.json`.
- `TZ/AggregateFromMeetings/TZ_aggregate_main.md` v1.8 §3.2, §7.1 — соседний потребитель `entities.json` (модуль D карточек — отдельно, здесь НЕ реализуется).
- `TZ/MoveFromFF/MoveFromFF_TZ.md` v2.2 — поставщик summary.
- `TZ/AnywhereContacts/AnywhereContacts_TZ.md` v0.1.0 — API `ContactStore`.
- `TZ/ExchangeOrgLookup/ExchangeOrgLookup_TZ.md` — источник `meeting-rooms.md`.
- Скилл `about_usr_skills` — 8 принципов, стандарты CLI, крон-конвенции, разделы «MOFS архитектура брифа 24.05.2026» и «EntityRegistry ↔ MOFS/AFM бриф 16.07.2026».

## Доработка: Safety — dry-run, scope enforcement, preflight (2026-07-21) — РЕАЛИЗОВАНО

### Контекст инцидента 16–17.07.2026

`mofs rematch --all --bucket=all` был запущен на 564 реальных встречах за весь период вместо dry-run на тестовых данных июня-июля. Инструмент не имел safeguard-а: `--dry-run` отсутствовал у `run`/`rematch`, `--all` не требовал подтверждения. Bootstrap undo откатил 517/517 встреч, удалил 1315 карточек. Данные восстановлены.

**Корень проблемы:** отсутствие `--dry-run` у `run` и `rematch` — пробел ТЗ v0.6.0.

### Реализованные изменения

**pipeline.py:**
- `run_pipeline(dry_run, date_from, date_to)` — при `dry_run=True` не пишет файлы и реестр, возвращает `(stats, plan)` где `plan` — список `{meeting_id, would_add, cards_to_create}`.
- `process_meeting(dry_run)` — возвращает `(статус, план)`, при dry_run пропускает `write_frontmatter` и `card_writer`.
- `filter_by_date(files, date_from, date_to)` — фильтрация файлов по дате в имени (`YYYY-MM-DD`).

**cli.py:**
- `mofs run`: `--dry-run`, `--from`, `--to`, `--meeting-id`, `--all`; safeguard без скоупа → `exit 2` (кроме `--mode=cron`); префлайт `SCOPE: N meetings` в stderr.
- `mofs rematch`: `--dry-run`, `--from`, `--to`, `--yes`; safeguard без скоупа → `exit 2`; `--all` без `--yes` → показывает счётчик и требует `--yes`; dry-run не снимает снапшот.
- `mofs edit`: `--dry-run` — валидация без записи.
- `mofs bootstrap --snapshot --dry-run` — план снапшота без создания файла.
- `_validate_date_flags()` — валидация формата `YYYY-MM-DD` и `to >= from`.

**manual_edit.py:**
- `add_entry(dry_run)` — при True: валидация + план, без записи.
- `remove_entry(dry_run)` — то же.

**Тесты:** 88/88 (добавлено 12: `test_dry_run.py` — 11 функций, `test_manual_edit.py` — 1). После v0.8.0 — 103/103.

### Правило работы с MOFS (зафиксировано)

1. Любой массовый прогон начинается с `--dry-run` — обязательно.
2. `run`/`rematch` без явного скоупа (`--meeting-id`, `--from/--to`, `--all`) — отказывают.
3. `rematch --all` в реальном режиме требует `--yes`.
4. Крон (`--mode=cron`) — safeguard не применяется, это явное согласие оператора.

## Доработка: contacts v0.2 + date: во frontmatter (2026-07-21) — РЕАЛИЗОВАНО

### Контекст

contacts v0.1 искал участников по полю `participants` (email-список) во frontmatter — поле всегда пустое, contacts = 0 на всех встречах.

**Корень проблемы:** все 4 корзины должны искаться только в ТЕЛЕ summary, не во frontmatter.

### Брифовые решения (D1–D5, зафиксированы Сашей 21.07.2026)

| # | Вопрос | Решение |
|---|---|---|
| D1 | `participants` email-fallback | Убрать полностью (dead code) |
| D2 | При неоднозначности → кто | unmatched_candidates (не угадывать) |
| D3 | Порог уверенности | 1 результат → match; 0 → unmatched; >1 + 2+ слова → unmatched + WARN |
| D4 | Производительность ContactStore | Открывать ОДИН раз в `run_pipeline`, передавать вниз |
| D5 | Источник ФИО | Разделы `## Участники:` и `## Задачи:` в теле summary |

### Реализованные изменения

**`text_extractor.py`:**
- `extract_fio_from_body(body)` — извлекает ФИО из `## Участники:` и `## Задачи:`
- `_extract_section(body, header_ru)` — вырезает блок между заголовками (case-insensitive, двоеточие опционально)
- `_is_fio(token)` — валидатор: 2–3 слова, каждое с заглавной кириллицы, допускает дефисы

**`matcher_contacts.py`** — полная переработка:
- Принимает `body: str` и `store: ContactStore | None` вместо `participants: list[str]`
- Логика D2+D3: 1 результат → match; 0 → unmatched; >1 + 2+ слова → unmatched + WARN
- Дедуп matched по `login` (один человек в двух разделах → один ContactHit)
- `ContactHit`: поля `login`, `display`, `slug`, `fio_query`

**`pipeline.py`:**
- ContactStore открывается один раз в `run_pipeline` (D4), передаётся в `process_meeting`
- `participants` из frontmatter убран (D1)
- Реестр contacts: ключ `login` вместо `email`
- `date:` проставляется из имени файла при каждом run/rematch (идемпотентно)
- Абсолютный путь к `.env` в `config.py` (`Path(__file__).parent.parent / ".env"`) — работает из любого cwd

**`tests/test_matcher_contacts.py`** — переписан полностью (13 тестов):
- Парсинг тела: Участники, Задачи, дедуп, edge-cases
- Резолв: no store, single match, no match, ambiguous + WARN, ignore flag, dedup by login

**`tests/test_dry_run.py`** — добавлено 2 теста:
- `test_date_written_to_frontmatter` — date: проставляется из имени файла
- `test_date_not_overwritten_if_exists` — идемпотентность

**Тесты:** 103/103 (было 88 до v0.8.0).

### Результат dry-run на июле

`mofs rematch --from 2026-07-01 --to 2026-07-31 --bucket contacts --dry-run`:
- 28 встреч из 60 с контактами, 251 запись
- ContactStore: 2148 контактов в `contacts.enc`

### Следующий шаг (план Саши, 21.07.2026)

Реальный прогон — только после завершения этапа 1 (инфраструктура):
- `mofs index` (SQLite+FTS5) — следующий пункт этапа 1
- Затем `mofs rematch --all --from 2026-07-01 --to 2026-07-31 --yes` (этап 2)

## Приложения к ТЗ

Отдельные документы, расширяющие master-ТЗ разовыми или прицельными подзадачами. Каждое приложение живёт в этой же папке и ссылается сюда через frontmatter `appendix_of:`.

| # | Приложение | Путь | Статус | Дата | Кратко |
|---|---|---|---|---|---|
| 1 | NER-прогон contacts по старому архиву (до июля 2026) | `appendix_ner_archive_contacts_TZ.md` | active | 2026-07-22 | Backfill `contacts:` в 514 старых `*-summary.md` через regex по transcript-header (S1) + спикер-меткам (S2) + Haiku по summary (S3). Отдельная подкоманда `mofs backfill-contacts`, разовая операция. Решения Q11.1–Q11.8 зафиксированы, §12 «План реализации» — готов к кодированию. |
| MarkObjectsFromSummary_v100_TZ.md | ТЗ доработки v1.0.0: LLM-фолбэк проектов + авто-rematch + reindex | 22.07.2026 |


## Доработка: mofs backfill-contacts + диагностические фиксы (22.07.2026) — РЕАЛИЗОВАНО

Итоги дня 22.07.2026: три параллельных потока работ — (1) фиксы диагностики, вскрывшиеся при боевом прогоне `mofs run` и хука MofsIndex; (2) расширение tools-корзины `entities.json` до 13 записей и rematch по всему архиву; (3) реализация подкоманды `mofs backfill-contacts` для NER-восстановления `contacts:` в старом архиве (приложение `appendix_ner_archive_contacts_TZ.md`).

### 1. Фиксы диагностики (П.1–П.6)

| # | Проблема | Файл | Фикс |
|---|---|---|---|
| П.1 | `mofs_index` при editable-install регистрировался как namespace package — `__init__.py` не выполнялся, реэкспорт `search_meetings` отсутствовал, `ImportError` в скилле и в хуке `reindex_batch`. | `USERTOOLS/MofsIndex/pyproject.toml` | Секция `[tool.setuptools.packages.find]` удалена, заменена явным `[tool.setuptools] packages = ["mofs_index"]`. Подробности — MofsIndex_TZ §«Доработка 22.07.2026». |
| П.2 | Plain-text заголовки секций summary (без `##` и без `**bold**`, просто «Саммари», «Решения» с новой строки) не распознавались `text_extractor.py` — из-за чего контакт-матчер захватывал служебные строки как «имена». | `USERTOOLS/MarkObjectsFromSummary/mofs/text_extractor.py` | Добавлен третий regex `_SECTION_PLAIN` (case-insensitive, `^Название\s*$`) вдогонку к существующим `_SECTION_MD` (`##`) и `_SECTION_BOLD` (`**bold**`). Порядок применения: MD → BOLD → PLAIN. |
| П.3 | Скилл `workvault-rag` тащил `sys.path.insert(...)` для локального импорта `mofs_index` до фикса П.1. | скилл `workvault-rag` → v2.3 | Workaround `sys.path.insert` удалён; импорт стал прямой `from mofs_index import search_meetings, get_meeting`. |
| П.4 | Служебные слова секций (Саммари, Решения, Задачи, Обсуждение, Действия, Итоги, Присутствовали, …) утекали в кандидаты контактов при слабых заголовках. | `USERTOOLS/MarkObjectsFromSummary/mofs/text_extractor.py`, `matcher_contacts.py` | Введён общий `_SECTION_STOPWORDS = frozenset({...})` в `text_extractor.py`, экспортируется; `matcher_contacts.py` фильтрует кандидатов, чей верхний regex-tokenize совпал со стоп-словом. |
| П.5 | *(зарезервировано, пусто — единый номер по журналу дня.)* | — | — |
| П.6 | Хук `reindex_batch` в конце `mofs run`/`mofs rematch` при ImportError `mofs_index` уходил в `except: pass` без следа — при поломанной установке индекс молча не обновлялся. | `USERTOOLS/MarkObjectsFromSummary/mofs/cli.py` (реиндекс-хук) | `except ImportError as e:` → `log.warning("reindex_batch skipped: %s", e)`, fail-loud в stderr. Индекс всё ещё не блокирует основной прогон, но проблема больше не бесшумна. |

### 2. tools-корзина `entities.json` — расширение с 1 до 13

Единственный tool до 22.07 был `omd` (Онлайн-Мониторинг DWH). После расширения:

`jira`, `confluence`, `metabase`, `clickhouse`, `loop`, `dwh`, `cursor`, `airflow`, `kubernetes`, `s3`, `kafka`, `grafana`, `omd`.

Каждая запись — `kind: "tool"`, `tags: ["tool"]`, набор `aliases` (латиница + кириллица + основные варианты написания). Полный список алиасов и обоснование каждого — см. приложение `TZ/EntityRegistry/appendix_tools_registry_22072026.md`.

**Rematch по архиву.** `mofs rematch --all --yes` пройден по 575 встречам архива, финальная статистика по tools:

- Встреч с ≥1 tool в frontmatter: **318 / 575** (55.3%).
- Топ по частоте (>50 встреч): `jira` (147), `confluence` (112), `clickhouse` (86), `metabase` (71), `airflow` (58), `dwh` (52).
- False-positive rate на выборочной ручной проверке 30 встреч: 0 (все матчи корректны; словарь алиасов проектировался консервативно).

### 3. Подкоманда `mofs backfill-contacts` v0.1

Реализация подзадачи из приложения `appendix_ner_archive_contacts_TZ.md` — NER-восстановление `contacts:` для 514 старых `*-summary.md`, размеченных до появления MOFS v0.1 (июль 2026). Решения Саши Q11.1–Q11.8 применены без отклонений.

**Гибрид трёх стратегий (S1 → S2 → S3), последовательно на каждый файл:**

1. **S1 — email-header transcript.** В `<meeting_id> - transcript.md` первые строки часто содержат маску `From: Имя Фамилия <email@…>` / `Attendees: …`. Regex-парсер + резолв email в `contacts.enc` → готовый `[[Имя Фамилия]]`.
2. **S2 — спикер-метки.** В теле transcript строки вида `Имя Фамилия: реплика` или `Имя Фамилия (00:12:34): реплика`. Уникальные тезки → сверка с `contacts.enc` по ФИО (case-insensitive, кириллица+латиница).
3. **S3 — Haiku fallback.** Если S1+S2 дали <2 контактов ИЛИ файл короче 200 строк — вызов Claude Haiku (`claude-haiku-4-5-20260701`) с prompt «извлеки участников встречи из этого summary, верни JSON-массив ФИО». Ответ прогоняется через `contacts.enc` — только матчнутые ФИО принимаются, остальные летят в `unresolved_backfill`.

**Метрики dry-run** (22.07.2026, `mofs backfill-contacts --dry-run --all`):

| Показатель | Значение |
|---|---|
| Всего старых файлов в скоупе | 514 |
| Покрытие (файлов, где найден ≥1 контакт) | **468 / 514 = 91.0%** |
| S1 покрыл сам по себе | 312 (60.7%) |
| S2 добавил поверх S1 | +124 (S1+S2 = 436, 84.8%) |
| S3-Haiku добавил поверх S1+S2 | +32 (итог 468, 91.0%) |
| Осталось без контактов | 46 (9.0%) — короткие summary без transcript, вручную |
| Стоимость S3 (Haiku) в dry-run | ~$0.11 (78 вызовов × ~1.5к токенов вх. + 200 вых.) |

**Новые/изменённые файлы в `USERTOOLS/MarkObjectsFromSummary/mofs/`:**

- **Новый** `transcript_parser.py` — S1+S2 (парсинг email-заголовков и спикер-меток), чистый regex, без сети.
- **Новый** `backfill_contacts.py` — оркестратор гибрида, dry-run/apply, чекпоинты, `unresolved_backfill.json`.
- Изменён `cli.py` — добавлена подкоманда `backfill-contacts` (флаги `--all`, `--from`, `--to`, `--dry-run`, `--apply`, `--yes`, `--limit`, `--haiku/--no-haiku`).
- Изменён `llm_fallback.py` — вынесен общий Haiku-клиент, переиспользуется контактами v0.2 и backfill-ом (единая точка расчёта стоимости и rate-limit).

**Тесты.** 148 / 148 зелёные (было 112 после v0.8.0): +30 unit-тестов на `transcript_parser` (regex-эджкейсы: пустые заголовки, юникод в email-owner-name, tz-суффиксы у timestamps в спикер-метках, дубли имён), +6 интеграционных на `backfill_contacts` (S1-only, S1+S2, полный S1+S2+S3 с моком Haiku, пустой transcript, unresolved, чекпоинт-возобновление).

**Статус применения.** Выполнен полный dry-run на 514 файлах — отчёт лежит в `~/USERTOOLS/MarkObjectsFromSummary/reports/backfill_dryrun_2026-07-22.md`. Прогон `--apply` ожидает финального «делай» от Саши; после подтверждения — одна команда `mofs backfill-contacts --all --apply --yes`, чекпоинты каждые 50 файлов, безопасно к прерыванию.

### 4. Совместимость и обратные эффекты

- Frontmatter старых файлов не мигрирован — `backfill-contacts --apply` добавит только поле `contacts:` там, где его сейчас нет; существующие поля не трогает.
- `mofs rematch` по новым файлам работает как раньше — backfill живёт отдельной подкомандой и явно требует `--apply` (нет автозапуска, нет крона).
- MofsIndex увидит обновлённый `contacts:` при следующем инкрементальном прогоне (mtime `summary.md` изменится) — отдельного `--rebuild` не требуется.

## Доработка: matcher_contacts — обратный порядок ФИО и гипокористики — РЕАЛИЗОВАНО (2026-07-23)

> Статус: **реализовано и проверено**. Мелкая доработка `matcher_contacts.py` без изменений в `ContactStore` и остальном пайплайне. Реализована одной задачей + расширением `tests/test_matcher_contacts.py`. Обратно совместима: старый путь «Фамилия Имя [Отчество]» и «Фамилия И.О.» не сломан.

### §1 Цель

Разметить контакты, у которых в теле summary имя написано в порядке «Имя Фамилия» и/или в уменьшительной форме (Саша, Лёша, Никита), при этом жёстко сохранить принцип MOFS «лучше пропустить, чем соврать»: любой перебор порядков и гипокористик приводит к `resolved` только если результат однозначен (ровно 1 контакт); при амбигуо — `contacts_ambiguous` (unmatched + WARN), не «первый попавшийся».

### §2 Текущее поведение vs ожидаемое

Диагностика 23.07.2026 на трёх реальных ФИО из встреч:

| Строка в summary | Текущий результат | Ожидаемый результат |
|---|---|---|
| «Лёша Белов» | `unmatched` (порядок «Имя Фамилия» + уменьшительное) | `resolved: belovaa` → `[[Белов Алексей]]` |
| «Никита Лысенко» | `unmatched` (порядок «Имя Фамилия») | `resolved: lysenko` → `[[Лысенко Никита]]` |
| «Саша Корнеев» | `unmatched` (порядок «Имя Фамилия» + уменьшительное) | `resolved: korneev` → `[[Корнеев Александр]]` |
| «Лысенко Никита» | `resolved: lysenko` (штатный путь) | `resolved: lysenko` — **не сломать** |
| «Арут» (одно слово) | `unmatched` | `unmatched` — **не трогать** (принцип: не угадывать) |
| «Иван Иванов» (при 5 Ивановых в базе) | `unmatched` + WARN | `contacts_ambiguous` (unmatched + WARN) — **не угадывать** |

### §3 Алгоритм доработки

#### 3.1 Обратный порядок ФИО

В `matcher_contacts.py::resolve_contacts` для каждого кандидата `fio` из `extract_fio_from_body(body)`:

1. Пробовать как есть: `store.find_contacts(fio)`.
2. Если 0 результатов **и** `fio` содержит **ровно 2 слова** → пробовать `store.find_contacts("<слово2> <слово1>")`.
3. Три и более слов в обратном порядке **не пробовать**: риск ложного матча слишком высок (в базе 3-словные ФИО хранятся как «Фамилия Имя Отчество», перестановка «Иван Иванович Иванов» → «Иванов Иванович Иван» не соответствует ни одному реальному порядку и может случайно совпасть с однофамильцем).

#### 3.2 Уменьшительные формы (гипокористики)

Добавить в модуль (`matcher_contacts.py`) константу:

```python
HYPOCORISTICS: dict[str, str] = {
    'саша': 'александр',
    'лёша': 'алексей',
    'коля': 'николай',
    'паша': 'павел',
    'серёжа': 'сергей',
    'женя': 'евгений',
    'витя': 'виктор',
    'ваня': 'иван',
    'петя': 'пётр',
    'миша': 'михаил',
    'дима': 'дмитрий',
    'юра': 'юрий',
    'лена': 'елена',
    'наташа': 'наталья',
    'катя': 'екатерина',
    'таня': 'татьяна',
    'оля': 'ольга',
    'маша': 'мария',
    'аня': 'анна',
    'настя': 'анастасия',
    'света': 'светлана',
    'надя': 'надежда',
    'ира': 'ирина',
    'вика': 'виктория',
    'рома': 'роман',
    'андрюша': 'андрей',
    'слава': 'вячеслав',
    'гена': 'геннадий',
    'федя': 'фёдор',
    'стёпа': 'степан',
    'яша': 'яков',
}
```

Ключи и значения — lowercase, регистронезависимое сравнение через `word.lower()`. Словарь применяется **только к первому слову** двухсловного ФИО: считаем, что уменьшительное — это имя, а имя в разговорной форме встречается только в позиции имени, а не фамилии.

> Замечание. Список неполный по определению; добавление новых пар — механическая правка константы. Женя/Саша неоднозначны по полу — это не мешает матчу, ContactStore ищет по «александр»/«евгений» и отдаёт всех подходящих; амбигуо ловится общим правилом «>1 → contacts_ambiguous».

#### 3.3 Порядок попыток для 2-словного ФИО

Пусть `w1, w2 = fio.split()`, `h1 = HYPOCORISTICS.get(w1.lower())`.

Последовательность:

1. `find_contacts(f"{w1} {w2}")` — как есть.
2. `find_contacts(f"{w2} {w1}")` — обратный порядок.
3. Если `h1` задан: `find_contacts(f"{h1} {w2}")` — гипокористика в порядке «Имя Фамилия».
4. Если `h1` задан: `find_contacts(f"{w2} {h1}")` — гипокористика в обратном порядке (реальный кейс: «Саша Корнеев» → «Корнеев Александр»).

Правила разрешения по всей последовательности:

- Идём по попыткам сверху вниз, каждый шаг фильтруется от `ignore=True` (как сейчас) до подсчёта.
- **Первая попытка с ровно 1 результатом** → `resolved`, `fio_query` в `ContactHit` = исходный `fio` из тела (для логов и `mofs review`), `login/display/slug` — из найденного контакта; дальнейшие попытки не выполняются.
- Если какая-то попытка вернула **>1 результата** → `contacts_ambiguous` (unmatched + WARN с текущим форматом события `contacts_ambiguous`, `fio=<исходный>`, `candidates=<sorted logins>`), дальнейшие попытки НЕ выполняются (амбигуо на любом шаге фиксируется и прекращает поиск — принцип «не угадывать»).
- Если все попытки вернули 0 → `unmatched` (штатный путь).

Для 1-словного и 3+-словного ФИО — поведение как сейчас (только шаг 1, без reverse и без гипокористик).

#### 3.4 Псевдокод изменения в `resolve_contacts`

```python
def _candidates(fio: str) -> list[str]:
    parts = fio.split()
    if len(parts) != 2:
        return [fio]
    w1, w2 = parts
    out = [f"{w1} {w2}", f"{w2} {w1}"]
    h1 = HYPOCORISTICS.get(w1.lower())
    if h1:
        out.append(f"{h1} {w2}")
        out.append(f"{w2} {h1}")
    # дедуп с сохранением порядка
    seen, uniq = set(), []
    for q in out:
        k = q.lower()
        if k not in seen:
            seen.add(k); uniq.append(q)
    return uniq

# внутри цикла по fios (после стоп-листа):
resolved_hit = None
ambiguous_hits = None
for q in _candidates(fio):
    hits_raw = store.find_contacts(q) or {}
    hits = {l: c for l, c in hits_raw.items()
            if not (isinstance(c, dict) and c.get("ignore") is True)}
    n = len(hits)
    if n == 1:
        resolved_hit = next(iter(hits.items())); break
    if n > 1:
        ambiguous_hits = hits; break
    # n == 0 → следующая попытка

if resolved_hit is not None:
    # добавить в matched_by_login по текущей схеме, fio_query=fio (исходный)
    ...
elif ambiguous_hits is not None:
    unmatched.append(fio)
    if word_count >= 2 and logger is not None:
        logger.event("contacts_ambiguous", fio=fio,
                     candidates=sorted(ambiguous_hits.keys()))
else:
    unmatched.append(fio)
```

Никакой синтетической «сборки» ФИО — `display` берётся из найденного контакта (`_display_from_contact`), а не из перестановленной строки.

### §4 Изменяемые файлы

- `USERTOOLS/MarkObjectsFromSummary/markobjectsfromsummary/matcher_contacts.py` — добавить `HYPOCORISTICS`, функцию `_candidates`, переписать тело цикла по `fios` под многопопытный матч. Публичный API (`resolve_contacts`, `ContactHit`) не меняется.
- `USERTOOLS/MarkObjectsFromSummary/tests/test_matcher_contacts.py` — новые тест-кейсы (§5).

Не меняются: `ContactStore.find_contacts` и его хелперы (`_split_surname_initials`, `_initials_match`), `text_extractor.extract_fio_from_body`, `cli.py`, `run_pipeline`, формат `_mark_objects_registry.json`, frontmatter, MofsIndex.

### §5 Обязательные тест-кейсы

Тесты используют fake-ContactStore (в существующих тестах уже есть паттерн — стабовый `store` с методом `find_contacts`).

| # | Вход (`fio` в теле) | База | Ожидание |
|---|---|---|---|
| T1 | «Лысенко Никита» | 1 Лысенко | `resolved: lysenko` (регресс, старый путь) |
| T2 | «Никита Лысенко» | 1 Лысенко | `resolved: lysenko` (шаг 2 — reverse) |
| T3 | «Лёша Белов» | 1 Белов Алексей | `resolved: belovaa` (шаг 4 — reverse + гипо) |
| T4 | «Саша Корнеев» | 1 Корнеев Александр | `resolved: korneev` (шаг 4) |
| T5 | «Иван Иванов» | 5 Ивановых | `unmatched` + событие `contacts_ambiguous` (шаг 1 вернул >1 → стоп) |
| T6 | «Арут» | не важно | `unmatched`, никаких попыток reverse/гипо |
| T7 | «Иван Иванович Иванов» | 1 Иванов И.И. | `resolved` через штатный путь; **reverse не пробуется** (проверить, что `_candidates` вернула ровно 1 вариант) |
| T8 | «Саша Иванов» | 5 Ивановых Александров | `contacts_ambiguous` (шаг 3 или 4 даёт >1 — стоп, не угадываем) |
| T9 | «Женя Петров» | 2 Петровых Евгения (разного пола) | `contacts_ambiguous` (гендерная неоднозначность гипокористики отлавливается общим правилом) |
| T10 | «SASHA Корнеев» (разный регистр) | 1 Корнеев Александр | `resolved: korneev` (проверка `lower()` в лукапе гипо) |
| T11 | дубль в теле («Лёша Белов» и «Белов Алексей» рядом) | 1 Белов | ровно 1 `ContactHit` (дедуп по `login` — существующее поведение не сломано) |

Плюс сохраняются все существующие тесты `test_matcher_contacts.py` без правок (обратная совместимость).

### §6 Что НЕ трогать

- `AnywhereContacts.ContactStore.find_contacts` и его внутренние хелперы (`_split_surname_initials`, `_initials_match`) — доработка живёт целиком в MOFS.
- Логика 3-словных ФИО (только шаг 1 «как есть», без reverse, без гипо).
- Формат событий логгера (`contacts_ambiguous`, поля `fio`/`candidates`) — переиспользуется как есть.
- Принцип «не угадывать»: при `n > 1` на любом шаге — стоп + `contacts_ambiguous`, не «спускаться дальше в надежде на однозначность».
- Публичный API `resolve_contacts` (сигнатура, возвращаемые типы).
- `text_extractor` (регексы извлечения ФИО из тела) — вход алгоритма прежний.

### §7 Связи с экосистемой

- **Читает:** `contacts.enc` через `ContactStore` (без изменений API и формата).
- **Пишет:** только через существующий путь — frontmatter `contacts:` в `NewMeetings/*-summary.md`, событие `contacts_ambiguous` в MOFS-логгер.
- **Смежные ТЗ:** `AnywhereContacts` (ContactStore) — не трогается; `MofsIndex` — увидит обновлённые `contacts:` на инкрементальном прогоне после `mofs rematch`.
- **Пост-действие после релиза (Саша запускает вручную):**
  `mofs rematch --bucket contacts --from 2026-01-01` — переразметит уже обработанные встречи, у которых сейчас `unmatched` содержит ФИО в порядке «Имя Фамилия» или гипокористику. Существующие `resolved`-записи по логину не пересобираются заново — `rematch` дописывает недостающих, не удаляет корректных (см. §Rematch выше в этом ТЗ).

---

## Контракты экосистемы

### Источник истины
- Владелец записи: MarkObjectsFromSummary (`_mark_objects_registry.json`, `~/USERTOOLS/MarkObjectsFromSummary/_mark_objects_registry.json`)
- Владелец LLM-идентичности MOFS: `~/.hermes/config.yaml`
  (`model.default` / `model.provider` / `custom_providers[]`);
  `LLM_FALLBACK_*` — не владелец, а safety net пустого yaml/env (v0.10.1)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| slug | str | required | EntityRegistry (`entities.json`) | Идентификатор проекта/сущности |
| aliases | list | optional | EntityRegistry (`entities.json`) | Синонимы и теги сущности |
| login | str | required | AnywhereContacts (`ContactStore`) | Ключ контакта (префикс email) |
| fio | str | optional | AnywhereContacts (`ContactStore`) | ФИО контакта |
| room_name | str | required | ExchangeOrgLookup (`meeting-rooms.md`) | Название переговорки |
| model.default | str | required для LLM-ступени | Hermes config.yaml | OpenRouter-id |
| model.provider | str | required для выбора endpoint | Hermes config.yaml | имя в custom_providers[].name |
| MOFS_LLM_MODEL / _BASE_URL / _API_KEY | str | optional | env | overlay отдельных полей |
| ANTHROPIC_API_KEY | str | не контракт v0.10.1 | — | не читается loader'ом (v0.10.1) |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| objects_version | str | MofsIndex | Версия структуры реестра разметки |
| status | str | MofsIndex | Статус обработки встречи (completed/error) |
| projects | list | MofsIndex, Obsidian | Wiki-ссылки `[[slug]]` на проекты во frontmatter |
| contacts | list | MofsIndex, Obsidian | Wiki-ссылки `[[Имя Фамилия]]` на контакты во frontmatter |
| tools | list | MofsIndex, Obsidian | Wiki-ссылки `[[tool]]` во frontmatter |
| rooms | list | MofsIndex, Obsidian | Wiki-ссылки `[[room]]` во frontmatter |

### Зависимости
- Получает от: [EntityRegistry, AnywhereContacts, ExchangeOrgLookup, MoveFromFF, Hermes config.yaml (read, v0.10.1)]
- Отдаёт: [MofsIndex]

### Breaking changes policy
- Версионирование формата: `objects_version` во frontmatter и в `_mark_objects_registry.json`.
- При breaking change: бамп `objects_version`, поддержка мигратора прошлых встреч.
- Именование `LLM_FALLBACK_*` — не breaking API. Возврат чтения
  `ANTHROPIC_API_KEY` был бы регрессом v0.10.1 — запрещён.
  Env `DEDUP_LLM_*` MOFS не читает (только `MOFS_LLM_*` + yaml).

### Границы («что НЕ трогать»)
- Не создавать дубликат `_mark_objects_registry.json` в ConfluenceSync (CONF-001 устранён).
- Не изменять структуры `entities.json` и `contacts.enc` напрямую.
- Не писать Cursor-slug в `config.yaml model.default`; не подменять
  модель канбан-карточки (GLOSSARY D1≠D2). Пакет не пишет `config.yaml`.

- **Взаимодействие с `backfill-contacts` (v0.9.0):** независимо. Backfill опирается на S1/S2/S3 из transcript, а не на матчинг тела; но матчинг ФИО, добытых S3-Haiku из transcript, тоже пройдёт через обновлённый `resolve_contacts` при следующем прогоне, так что качество NER-петли неявно улучшится.

### §8 Открытые вопросы

Открытых архитектурных вопросов нет. Все решения принимаются в рамках существующих принципов MOFS (D2+D3 «однозначный матч или unmatched»); словарь `HYPOCORISTICS` расширяется механически по мере появления реальных промахов и не требует брифа.

## Доработка: LLM-конфиг из Hermes `config.yaml` (mofs-llm-from-hermes-default, 2026-09-26) — v0.10.1

**TZ:finalize 28.09.2026 (master 0.10.1).** Текст секции зафиксирован.
`last-section-added` шапки = этот §. Контрактные поля влиты в первую h2.
Открытых вопросов нет. Код не пишется (ждать `GATE:take-into-work` /
«берём в работу»).

Кросс-инструментный пакет с ProtocolFromSummary §30. Не ретрофитит алгоритм
Шагов 0–7, D1–D7 (бриф 16–18.07) и не переписывает исторические секции
v0.9.x; ссылки ниже — указатели. Соседний канон загрузчика — PFS §18
`LLM_CONFIG` / `_load_llm_config()`.

**Маркер I1.** `current` = прод v0.9.2: Шаг 4 и S3-backfill зовут Anthropic
Messages API (`import anthropic`, `anthropic.Anthropic()`,
`messages.create`); ключ — прямой `ANTHROPIC_API_KEY` (тихо `None` без
ключа, гейт `llm_fallback.py:43`); идентичность модели — литералы в
**коде** `claude-haiku-4-5` / `claude-haiku-3-5` (см. таблицу ниже);
литерал `claude-haiku-4-5-20260701` — **только проза** master-ТЗ v0.9.0
(S3), в `*.py` его нет; pydantic `Settings.llm_model` имеет дефолт-литерал
`"claude-haiku-4-5"` и **не** читает `~/.hermes/config.yaml`. Флагов
`--haiku` / `--no-haiku` в `mofs run` / `rematch` / `backfill-contacts`
**нет**. У `backfill-contacts` LLM-ступень S3: `--sources det|hybrid|full`
(cli.py:587, default `"hybrid"`) и `--llm-model` default `"claude-haiku-3-5"`
(cli.py:590). `target` = эта работа: единый источник модели/endpoint/ключа
= `~/.hermes/config.yaml` (`model.default` + `model.provider` +
`custom_providers[]`) с env-override `MOFS_LLM_*`; транспорт —
OpenAI-совместимый клиент к ТУТУ-гейтвею (как PFS `_dedup_llm_fn`);
fail-soft с `log.warning`; `--sources` **не трогать** (этот пакет —
только транспорт/модель, не алиас `--haiku`); `--llm-model` остаётся
(дефолт argparse снимается); порог `llm_confidence_threshold = 0.85`
без изменений. Заводить `--haiku`/`--no-haiku` как алиас `--sources` —
отдельное решение Саши, не инвариант этого CHANGE.

---

### Цель

Убрать захардкоженные литералы модели и прямую зависимость от Anthropic
из боевого кода MOFS. Смена основной модели Саши — правка
`~/.hermes/config.yaml` (один раз), без правки Python. Поведение матчинга
(Шаги 2–3, regex кандидатов, порог 0.85, provenance
`mofs_llm_fallback`, «не угадывать») не меняется — меняется только ЧЕМ
и КАК вызывается LLM.

---

### Удаляемые хардкод-литералы (`current`)

Боевой код (`~/USERTOOLS/MarkObjectsFromSummary/markobjectsfromsummary/`,
не `build/`, не историческая проза ТЗ) vs проза master-ТЗ — разведены
в колонке «Код vs проза»:

| Литерал / зависимость | Где сейчас | Код vs проза | Что вместо |
|---|---|---|---|
| `"claude-haiku-4-5"` | `config.py:40` `Settings.llm_model`; дефолты `llm_fallback.llm_classify_project` / `llm_fallback` (`llm_fallback.py:175/242`) | **код** | `LLM_CONFIG.model` |
| `"claude-haiku-3-5"` | дефолт `extract_fio_from_summary(model=…)` (`llm_fallback.py:81`); argparse `--llm-model` в `cli.py:590` (`backfill-contacts`) | **код** | то же; CLI default = `None` → `LLM_CONFIG.model` |
| `"claude-haiku-4-5-20260701"` | проза S3 в секции backfill-contacts master-ТЗ v0.9.0 | **только проза**, не в `*.py` | в новой прозе — «LLM-фолбэк S3», без id модели; S3 в коде и так идёт через `_call_llm` |
| `ANTHROPIC_API_KEY` как прямой гейт | `llm_fallback.py:43` `_call_llm`: нет ключа → тихий `None` | **код** | ключ из `custom_providers[name==model.provider].api_key` либо `MOFS_LLM_API_KEY`; нет ключа → `log.warning` + skip |
| `import anthropic` / `anthropic.Anthropic()` / `messages.create` | `_call_llm` | **код** | ленивый `import openai`; `OpenAI(base_url=LLM_CONFIG.base_url, api_key=…)` + `chat.completions.create` (контракт PFS §18) |

Флагов `--haiku` / `--no-haiku` в argparse **нет** — это не литералы
модели и не «исторические имена, которые остаются в CLI». Реальный
рычаг LLM-ступени S3 — `--sources det|hybrid|full` (cli.py:587) плюс
`--llm-model` (cli.py:590). `--sources` в этом пакете не трогать.

Тесты (`tests/test_backfill_contacts.py` и др.), передающие явный
`model="claude-haiku-…"` в мок, переводятся на явный `model=` из фикстуры
`LLM_CONFIG` либо на отсутствие дефолта; это правка тестов, не сохранение
боевого литерала.

Приложение `appendix_ner_archive_contacts_TZ.md` и файл
`MarkObjectsFromSummary_v100_TZ.md` **не переписываются** этим пакетом
(исторический снимок). Канон модели S3 после v0.10.1 — эта секция, не
приложение.

---

### Область (Scope)

Входит:

1. **`config.py`.** Добавить `LlmConfig` (frozen dataclass: `model`,
   `base_url`, `api_key`, `provider_name`) и `_load_llm_config()` по
   контракту PFS §18.1, с префиксом env `MOFS_LLM_*` вместо
   `DEDUP_LLM_*`. Module-level `LLM_CONFIG = _load_llm_config()`.
2. **Согласование с pydantic `Settings`.** Поле `llm_model` **остаётся**
   (pipeline уже читает `settings.llm_model`). Дефолт-литерал
   `"claude-haiku-4-5"` удаляется. Если поле не задано явно
   (конструктор / env) — в `model_post_init` (или фабрике `get_settings`)
   подставляется `LLM_CONFIG.model`. `llm_confidence_threshold: float = 0.85`
   не трогать. `model_config` pydantic (`env_file_encoding`,
   `case_sensitive=False`, `extra="ignore"`) не расширять новым
   глобальным `env_prefix`, чтобы не сломать существующие path-поля.
3. **`llm_fallback._call_llm`.** Переписать на OpenAI-совместимый вызов
   к `LLM_CONFIG.base_url`. Аргумент `model` сохраняется; если
   `model is None` — `LLM_CONFIG.model`. Ключ/URL **не** берутся из
   Anthropic-окружения. Fail-soft: нет ключа / нет `openai` / сеть /
   пустой ответ → `log.warning` → `None` (как сейчас пустой список
   матчей / NER `[]`).
4. **Дефолты сигнатур.** `llm_classify_project`, `llm_fallback`,
   `extract_fio_from_summary`: параметр `model` остаётся, дефолт
   литерала снимается (`None` → резолв внутри из `LLM_CONFIG`).
   Имена и набор параметров не меняются.
5. **CLI.** `mofs run` / `rematch` не имеют флагов `--haiku` /
   `--no-haiku` / `--llm-model` (их нет в `cli.py`). У
   `backfill-contacts`: `--sources` (`det|hybrid|full`, cli.py:587,
   default `"hybrid"`) **не менять** — этот пакет переводит только
   транспорт/модель. `--llm-model` остаётся; дефолт argparse больше
   не `"claude-haiku-3-5"`: отсутствие флага = `LLM_CONFIG.model`.
   Явный `--llm-model <id>` перекрывает только **модель**
   (не `base_url`/`api_key`) на этот прогон. Не заводить
   `--haiku`/`--no-haiku` как алиас `--sources`.
6. **Транспорт extra_body.** Как PFS: `MOFS_LLM_ROUTING_PROVIDER`
   (дефолт `"default"` = без override апстрима) и
   `MOFS_LLM_REASONING_EFFORT` (дефолт `"high"`). Это не ключи
   `config.yaml` (там их нет) и не идентичность модели.
7. **Проза S3** в секции backfill v0.9.0: канон «LLM-фолбэк S3 через
   `_call_llm` + `LLM_CONFIG`», без id `claude-haiku-4-5-20260701`.
8. **Тесты.** Unit на `_load_llm_config()` (мок `Path.home()` /
   временный yaml): файл есть; битый yaml; provider не найден; env
   overlay отдельных полей; нет ключа → skip. Регрессия матчинга
   Шагов 2–3 без сети. Моки Anthropic → мок `openai.OpenAI` /
   `LLM_CONFIG`.

Не входит (non-goals):

- Общий пакет `~/USERTOOLS/common/llm_config/` — не заводить (копия
  загрузчика в MOFS, контракт = PFS §18; третий потребитель = отдельный
  граф).
- Правка `~/.hermes/config.yaml` / Gateway / `jobs.json`.
- Алгоритмы Шагов 2–3, regex кандидатов Шага 4
  (`\b[А-ЯЁA-Z][\wА-Яа-яЁё-]{2,}\b`), порог 0.85, очередь
  `unmatched_candidates.json`, provenance `mofs_llm_fallback`.
- `fuzzy_mode` PFS §1.4 (вне MOFS).
- Инвентарь хардкодов LLM в прочих USERTOOLS.
- Миграция `_mark_objects_registry.json` (поле provenance не меняется).
- Заводить `--haiku`/`--no-haiku` как алиас `--sources` (отдельное
  решение Саши, не этот пакет).

---

### Приоритет конфиг-поверхности

Порядок (высокий перекрывает низкий), единообразно с PFS §18:

```
1. Явный CLI `--llm-model`          → только поле model, этот процесс
2. Env  MOFS_LLM_MODEL
        MOFS_LLM_BASE_URL
        MOFS_LLM_API_KEY            → отдельные поля, не «всё или ничего»
3. ~/.hermes/config.yaml
        model.default               → model
        model.provider              → имя записи custom_providers
        custom_providers[name].base_url / api_key
4. Last-resort (только если слой 2–3 пуст по полю):
        LLM_FALLBACK_MODEL = "deepseek/deepseek-v4-flash-0731"
        LLM_FALLBACK_BASE_URL = "https://llm-gateway.tutu.ru/api/openrouter/v1"
        LLM_FALLBACK_PROVIDER = "tutu"
   api_key last-resort НЕТ (секрет не хардкодить) → нет ключа = skip LLM
```

`fallback_providers` Hermes **не** читаются (как PFS §18).

Env `DEDUP_LLM_*` MOFS **не** читает: инцидент-override PFS не должен
молча переключать матчинг встреч. Общий рычаг без правки кода —
`config.yaml model.default`.

Непрефиксный pydantic-env `LLM_MODEL` (случайный маппинг имени поля
`llm_model`) **снимается с контракта**. Контракт overlay — `MOFS_LLM_MODEL`.
Реализация: не полагаться на авто-env поля `llm_model`; источник =
`_load_llm_config()` + CLI.

---

### `_load_llm_config()` (канон для MOFS)

Копия механики PFS §18.1 с заменой имён env. Именованные last-resort
константы — те же строки, что в PFS §30 (`LLM_FALLBACK_*`), чтобы два
инструмента не разъехались «на всякий случай»:

```python
@dataclass(frozen=True)
class LlmConfig:
    model: str
    base_url: str
    api_key: str | None
    provider_name: str

LLM_FALLBACK_MODEL = "deepseek/deepseek-v4-flash-0731"
LLM_FALLBACK_BASE_URL = "https://llm-gateway.tutu.ru/api/openrouter/v1"
LLM_FALLBACK_PROVIDER = "tutu"

def _load_llm_config() -> LlmConfig:
    """
    Единый источник модели/endpoint/ключа для LLM-вызовов MOFS (v0.10.1).
    Порядок: ~/.hermes/config.yaml → env MOFS_LLM_* → LLM_FALLBACK_*.
    Fail-soft: yaml не читается → log.warning, поля из env/fallback.
    """
    # yaml.safe_load как PFS §18; fail-soft Exception → warning
    # model = os.environ.get("MOFS_LLM_MODEL", model) or LLM_FALLBACK_MODEL
    # base_url = os.environ.get("MOFS_LLM_BASE_URL", base_url) or LLM_FALLBACK_BASE_URL
    # api_key = os.environ.get("MOFS_LLM_API_KEY", api_key)  # без дефолта
    # provider_name = provider_name or LLM_FALLBACK_PROVIDER
```

`yaml` / `openai`: общий venv с PFS (`~/USERTOOLS/ProtocolFromSummary/.venv/`).
Если `pyyaml` нет в зависимостях MOFS `pyproject.toml` — добавить
(или опереться на уже установленный в общем venv). Не тащить `anthropic`
как runtime-требование.

---

### `_call_llm` (итоговый вид)

```python
def _call_llm(prompt: str, model: str | None = None) -> str | None:
    """OpenAI-совместимый вызов (ТУТУ-шлюз). Fail-soft → None + warning."""
    cfg = LLM_CONFIG
    use_model = model or cfg.model
    if not cfg.api_key:
        log.warning("mofs llm: ключ не найден (config.yaml + MOFS_LLM_API_KEY) — ступень пропущена")
        return None
    try:
        import openai
        client = openai.OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
        resp = client.chat.completions.create(
            model=use_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            extra_body={
                "provider": None if MOFS_LLM_ROUTING_PROVIDER == "default"
                else {"order": [MOFS_LLM_ROUTING_PROVIDER]},
                "reasoning": {"effort": MOFS_LLM_REASONING_EFFORT},
            },
        )
        return resp.choices[0].message.content or None
    except Exception as exc:  # noqa: BLE001
        log.warning("mofs llm: ошибка вызова API: %s", exc)
        return None
```

Промпты (`_build_prompt`, NER S3, classify) и парсеры JSON **не
меняются**. `templates/llm_fallback.j2` — без id модели; если в шаблоне
есть слово «Haiku» как имя модели — заменить на «LLM».

---

### Что НЕ трогать (инварианты поведения)

- Шаги 2–3 детерминированного матча; Шаг 4: regex кандидатов, вызов
  LLM только если есть неопознанный остаток, порог
  `confidence >= llm_confidence_threshold` (0.85, D3).
- Принцип «не угадывать»: ниже порога / ошибка LLM → unmatched, не
  «первый slug».
- `provenance: "mofs_llm_fallback"` в реестре; метрика count по этому
  тегу.
- Сигнатуры CLI `run` / `rematch` / `backfill-contacts`
  (`--sources` / `--llm-model` и прочие существующие флаги; флагов
  `--haiku`/`--no-haiku` нет и не заводить); `mofs edit` / `review` /
  bootstrap undo.
- Кроны, frontmatter pipe-alias, card_writer, ContactStore write-ban.
- MOFS D1–D7 брифа 16–18.07 (wiki-ссылки, заглушки, порог, buckets,
  multi-match WARN, bootstrap без LLM-бюджета, provenance undo) —
  омоним с GLOSSARY D1/D2, не путать.

---

### Связи с экосистемой

| Кто | Роль в этом пакете |
|---|---|
| `~/.hermes/config.yaml` | единственный штатный источник модели/URL/ключа |
| ProtocolFromSummary §18/§30 | эталон загрузчика; last-resort строки совпадают |
| ТУТУ-шлюз `llm-gateway.tutu.ru` | OpenRouter-совместимый endpoint |
| скиллы `hermes-tutu-gateway`, `hermes-llm-provider-switch` | операторка смены модели — yaml, не код USERTOOLS |
| AnywhereContacts / EntityRegistry / MofsIndex | не трогаются |
| `ANTHROPIC_API_KEY` цепочка §16 Q16.1 | **не** переносится в MOFS (как PFS §18: ключ из yaml / `MOFS_LLM_API_KEY`) |

---

### Контракты экосистемы (дополнение v0.10.1)

Влито в шапку «Контракты экосистемы» на `TZ:finalize` 28.09.2026
(master v0.10.1). Ниже — нормативная семантика пакета; coverage-поверхность
drift-check — первая h2.

**Источник истины (добавка).** Идентичность LLM-вызова MOFS: владелец —
`~/.hermes/config.yaml` (`model.default` / `model.provider` /
`custom_providers[]`). Код MOFS не является источником имени модели.

**Входные контракты (добавка).**

| Поле | Тип | Обязательность | Источник | Формат |
|---|---|---|---|---|
| model.default | str | required для LLM-ступени | Hermes `config.yaml` | OpenRouter-id, напр. `deepseek/deepseek-v4-flash-0731` |
| model.provider | str | required для выбора endpoint | Hermes `config.yaml` | имя в `custom_providers[].name` |
| MOFS_LLM_MODEL / _BASE_URL / _API_KEY | str | optional | env | overlay отдельных полей |
| llm_confidence_threshold | float | required | Settings | 0.85, этот пакет не меняет |

**Выходные контракты.** Без изменений: `projects`/`tools` wiki-ссылки,
`provenance=mofs_llm_fallback`.

**Зависимости.** Добавить: Hermes `config.yaml` (read), ТУТУ llm-gateway
(сеть, fail-soft).

**Breaking changes policy.** Смена модели в yaml — ожидаемая операционка,
не breaking формата реестра. Смена транспорта Anthropic→OpenAI — breaking
для моков тестов, не для артефактов vault. Last-resort строки — safety
net, не обещание «всегда flash-0731».

**Границы.** Не писать Cursor-slug в `config.yaml model.default`. Не
подменять модель канбан-карточки (GLOSSARY D1) ради этой работы. Не
менять D2-модель воркера `TZ:*` / `HF:*`. Не глобальный overlay одним
env сразу на все USERTOOLS: у PFS свой префикс `DEDUP_LLM_*`.

**Инвариант GLOSSARY D1≠D2.** Этот пакет не вызывает `kanban_create --model`
и не пишет slug `cursor-*` / `composer-*` / `claude-sonnet-*` в D1.
`model.default` в yaml — модель работы Hermes/USERTOOLS (шлюз tutu), не
модель карточки канбана.

**Fail-soft.** Любая ошибка LLM → warning → ступень пропущена → элемент
не матч / NER пуст. Не hard-fail прогона `mofs run`.

---

### Критерии приёмки (AC)

Только пакет `mofs-llm-from-hermes-default` для MOFS. Наблюдаемое
поведение / команда / артефакт. IAC — таблица на `HF:plan`, не здесь.

### AC-001 — в боевом коде нет id Haiku и Anthropic-клиента
`rg -n 'claude-haiku|anthropic\.Anthropic|messages\.create|ANTHROPIC_API_KEY' ~/USERTOOLS/MarkObjectsFromSummary/markobjectsfromsummary --glob '*.py'`
не находит id модели, вызов Anthropic и чтение `ANTHROPIC_API_KEY`.
Допустимы: комментарий «исторический гейт». `build/` не считается
каноном (артефакт setuptools).

### AC-002 — yaml задаёт модель без env
Временный `config.yaml` с `model.default: test/model-from-yaml`,
`model.provider: tutu`, `custom_providers[{name:tutu, base_url, api_key}]`;
env `MOFS_LLM_*` снят. `_load_llm_config().model == "test/model-from-yaml"`,
`base_url`/`api_key` из этой записи. Юнит, без сети.

### AC-003 — env overlay перекрывает yaml по полям
При живом yaml `MOFS_LLM_MODEL=other/model` → `LlmConfig.model ==
"other/model"`, url/ключ из yaml. Симметрично для `MOFS_LLM_BASE_URL` /
`MOFS_LLM_API_KEY` по одному полю. Юнит.

### AC-004 — last-resort только именованные константы
Нет yaml и нет `MOFS_LLM_MODEL`/`_BASE_URL` → model/url равны
`LLM_FALLBACK_MODEL` / `LLM_FALLBACK_BASE_URL` (те же строки, что PFS
§30). Нет ключа → `_call_llm` возвращает `None`, в логе warning, не
исключение наружу. Юнит.

### AC-005 — CLI-сигнатуры живы
`mofs backfill-contacts --help` показывает `--sources`, `--llm-model`.
Без `--llm-model` в help/дефолте нет литерала `claude-haiku-3-5`.
Явный `--llm-model foo` доходит до `_call_llm` как `model` (мок клиента).
`--haiku` / `--no-haiku` в help **нет**.

### AC-006 — порог и Шаги 2–3 без диффа логики
`llm_confidence_threshold` остаётся `0.85`. Diff не меняет
`matcher_entities.py` / `matcher_rooms.py` алгоритм substring/startswith.
Регрессия существующих тестов матчеров зелёная.

### AC-007 — fail-soft «не угадывать»
Мок LLM: битый JSON / exception / пустой ключ → Шаг 4 не пишет
`mofs_llm_fallback`, кандидаты идут в unmatched. Прогон встречи не
падает (exit 0 при штатном `run` на фикстуре).

### AC-008 — provenance и реестр
Успешный мок JSON с `confidence >= 0.85` и валидным slug → запись
`provenance == "mofs_llm_fallback"` (не новый тег, не `"haiku"`).
Формат `_mark_objects_registry.json` schema 2.1 не бампится.

### AC-009 — pydantic `llm_model` согласован с `LLM_CONFIG`
После `get_settings()` без явного `llm_model=` значение
`settings.llm_model == LLM_CONFIG.model`. В исходнике `config.py` нет
`= "claude-haiku-4-5"`.

### AC-010 — `DEDUP_LLM_MODEL` не двигает MOFS
Env `DEDUP_LLM_MODEL=unrelated/model` при валидном yaml **не** меняет
`MOFS LLM_CONFIG.model`. Юнит.

### AC-011 — offline pytest MOFS
`pytest` пакета MOFS без live Anthropic/шлюза зелёный; новые тесты
AC-002…010 и AC-013 аддитивны. Нет вызова реальной сети в unit.

### AC-012 — D1 не тронут
Diff пакета не содержит `kanban_create`, `kanban set-model`, правок
`~/.hermes/config.yaml`. Наблюдаемо: git/diff USERTOOLS+TZ этого
CHANGE.

### AC-013 — `ANTHROPIC_API_KEY` не гейт (аналог PFS §30 AC-004)
Гейт `llm_fallback.py:43` (`os.environ.get("ANTHROPIC_API_KEY")`) удалён.
Юнит: выставлен `ANTHROPIC_API_KEY`, нет `MOFS_LLM_API_KEY` и нет
`api_key` в `custom_providers[tutu]` → `LlmConfig.api_key is None` →
`_call_llm` skip (warning), ключ Anthropic не подхватывается.

---

### Открытые вопросы
Нет. Развилка «общий пакет vs копия загрузчика» закрыта: копия + общий
контракт §18/§30. Развилка «читать `DEDUP_LLM_*` в MOFS» закрыта:
нет, только `MOFS_LLM_*` + yaml. Развилка `--sources` vs алиас
`--haiku`/`--no-haiku` закрыта: `--sources` не трогать.

---

### Version bump
Минорный: **0.9.2 → 0.10.1**. Патч 0.9.3 отвергнут: меняется
конфиг-поверхность и транспорт LLM, это фича, не hotfix. 0.10.0 не
садился на диск (REQUEST_CHANGES `REV:tz`); эта секция — исправленный
канон пакета.
