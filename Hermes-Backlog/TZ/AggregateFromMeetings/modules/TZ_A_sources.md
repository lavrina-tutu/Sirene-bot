---
module: A_sources
parent: TZ_aggregate_main
version: 1.7
status: закрыт
date: 2026-06-30
updated: 2026-06-30 (Q-B7: обязательный вопрос PM о недостающих уставах перед bootstrap)
---

# Модуль A. Источники данных

<!-- изменено 2026-06-22: R1/R3/R8 -->

## Константы

- **OWNER** = `tkachenkoav@tutu.ru` — владелец пайплайна (PM). Используется как базовая точка отсчёта для правила owner-participants (R3) и для построения `hierarchy_hint` в B (см. TZ_B).
  Формат: full email. Login часть (`tkachenkoav`) используется при сопоставлении с AC.

## Назначение
Сбор и подготовка всех входных данных для пайплайна: FF summary + transcript из `Meetings/NewMeetings/`, прошлые срезы из `Projects/<slug>/snapshots/`, карточки `Projects/<slug>/card.md` и `Projects/<slug>/context.md`, контакты из AnywhereContacts, 1‑1 заметки. Нормализация форматов, чтение метаданных, выдача унифицированного «пакета встречи» для модуля B.

## Что уже зафиксировано
- Источник истины по людям — AnywhereContacts (research v0.1, В4).
- **Резолв имён** — файл `~/WorkVault/Contacts/tutu-contacts.md` как единый источник (ВОП-3, бриф 22.06). Пайплайн читает резолв оттуда. Содержит поля: login, ФИО, aliases, reports_to.
- **Оргструктура АИД** — поле `reports_to` в tutu-contacts.md определяет иерархию (aralov → tkachenkoav → kkrivorotov и др.). Используется для `hierarchy_hint` в B.Роутере.

### Единый путь данных `reports_to` (M6)

| Этап | Где живёт | Действие |
|------|-----------|----------|
| Источник (editable) | `~/WorkVault/Contacts/tutu-contacts.md` | PM правит вручную |
| Bootstrap-импорт | `AnywhereContacts` (`schema.py`: поле `reports_to`) | `ac_sync_from_tutu.py` копирует поле при синке |
| Runtime-чтение | AnywhereContacts (`ContactStore`) | B.Роутер и E.Люди читают `hierarchy_hint` из AC, **не** из tutu-contacts.md |

⚠️ **Правило:** правки оргструктуры всегда в `tutu-contacts.md`. Пайплайн runtime читает только из AC. Дублирующих источников нет.
- Confluence — подключается как источник для bootstrap-обогащения (см. A3 ниже).
- Обрабатываем все встречи без skip-листа (research v0.1, В7).
- Bootstrap по всем summary с 12.08.2025, далее инкремент от `last_processed_at` (research v0.1, В2).
- Стабильные секции FF summary разобраны в `research/AggregateFrom-project-entity-v0.1.md`, Блок 0.

## Карточка модуля

🎯 **Функция:** Определяет откуда берутся данные и нормализует их для передачи в пайплайн.
⬅️ **Вход:** Файловая система WorkVault (FF summary, card.md, context.md)
➡️ **Выход:** Нормализованный набор документов с метаданными → модули B и C
🔗 **Зависимости:** нет (фундаментальный модуль)

## Решения брифа

- **В1 — Источники MVP v1:** FF summary + card.md проектов. Transcript, срезы, 1-1 — следующая итерация.
- **В2 — Формат передачи:** Python dataclass `MeetingPackage` (в памяти, строго типизировано).
  Поля, заполняемые A.Сборщиком:
  - `summary_path: str` — путь к FF summary
  - `date: str` (YYYY-MM-DD) — дата встречи
  - `summary_text: str` — прочитанный текст summary
  - `title: str` — заголовок встречи из FF-summary (первая строка / frontmatter title) <!-- изменено 2026-06-22: N5 fix -->
  - `transcript_path: Optional[str]` — путь к FF transcript (если есть), Фаза 2
  - `participants_raw: list[str]` — участники. <!-- изменено 2026-06-22: R1 --> Источник — **парный transcript** (`**Участники:**` секция → speaker labels фоллбэк), не summary. См. раздел «Парсер участников и даты». В FF-summary этой секции нет by design.
  - `card_paths: list[str]` — пути к карточкам проектов (заполняется ПОСЛЕ B по найденным slug-ам)
  - `card_frontmatter: dict[str, dict]` — `{slug: frontmatter}` для каждой карточки проекта
  - `card_sections: dict[str, dict]` — `{slug: {goal, criteria, assumptions, constraints}}`
  - `context_text: dict[str, Optional[str]]` — `{slug: context.md text | None}`
  Поля, заполняемые B.Роутером (см. TZ_B_classification, В1):
  - `route: Literal["project", "1on1", "multisync", "unclear"]`
  - `project_slugs: list[str]` — список slug-ов проектов (а не одиночный!)
  - `sync_slug: Optional[str]` — slug синка (если route=multisync)
  - `route_project_slug: Optional[str]` — slug проекта из 1-1 встречи (ВОП-9). Заполняет B.Роутер, когда в заголовке 1-1 есть явная project-привязка (напр. «1-1 Кирилл / antibot»). Читается E.Люди для записи `project_roles` в AC. Для route ≠ 1on1 — `None`.
  - `people_hint: list[str]` — участники после первичной нормализации
  - `confidence: dict[str, Literal["high","medium","low"]]` — по каждому slug
  - `matched_aliases: dict[str, list[str]]` — какие алиасы совпали (по slug)
  ⚠️ **Важно:** A.Сборщик формирует «скелет» MeetingPackage без `project_slugs`/`route`. B.Роутер дозаполняет маршрут и slug-и, затем A догружает `card_*` и `context_text` по найденным slug-ам и передаёт обогащённый пакет в C.
- **В3 — Отслеживание новых встреч:** State-файл `USERTOOLS/AggregateFromMeetings/state.json` (см. главное ТЗ §8 — единая карта state-хранилищ, C3). Владелец — F.Дирижёр. Поле `processed_meetings[filename]` хранит `last_processed_at`, статусы модулей, route. Исходные файлы summary не трогаем. Сброс = удалить файл → переобработает всё. ⚠️ Ранее упоминаемый `~/.cache/hermes/aggregate_state.json` — устарел.

  **Идемпотентность — встречи не пересинкиваются (PD-037, OQ-003):** <!-- изменено 2026-06-29 --> если встреча уже обработана (`processed_meetings[filename]=done`), она **не пересинкивается и не переобрабатывается никогда** автоматически — даже если MoveFromFF/Fireflies задним числом изменил текст summary. Переобработка одной встречи или полный реплей проекта — **только в ручном режиме с явными вводными PM**. Корректировки в обычном потоке вносятся через PM Notes в срезе G (PD-027/037), а не через перепрогон. Это снимает прежний открытый вопрос «пересинк summary задним числом» (главное ТЗ §6.3).
- **В4 — Встречи без summary (только transcript):** MVP — пропускать (skip). v2 — логировать как «ожидает summary», повторная проверка через сутки.
- **В5 — Личные встречи:** Обрабатывать все без фильтрации. Личные 1-1 попадают в карточки контактов (модуль E). Модерация — через блоки `### PM Notes (tasks|decisions|risks)` среза (формат PD-053…058, см. TZ_G §5). ⚠️ Флаг `pm_locked: true` в frontmatter — **deprecated (m1)**: снят в D (см. TZ_D, открытый вопрос 7 — закрыт), E (TZ_E, открытый вопрос 3 — pm_locked не нужен), G (TZ_G, §6 project-snapshot — pm_locked не реализуется в v1). Перезаписей в карточках нет (append-only поток), блоки `### PM Notes (...)` среза — единственный механизм модерации.

- **В6 — Состав MeetingPackage:**
  - Из card.md: frontmatter (`slug`, `short_id`, `status`, `last_meeting`, `pm_locked`) + критерии приёмки + допущения + цель проекта + ограничения
  - Из context.md: весь текст как строка `context_text` (None если файла нет)
  - summary_text: прочитанный текст summary
  - Читаем один раз в модуле A, остальные модули работают с пакетом

## Парсер участников и даты (R1, R3, R8)

<!-- изменено 2026-06-22: R1/R3/R8 -->

### R1. Источник `participants_raw` — transcript, а не summary

**Проблема (аудит 22.06):** FF summary by design **не содержит** секцию `**Участники:**` — она живёт только в парном transcript-файле. Прежняя реализация `a_sources.scan_new_meetings()` + `ff_parser` искала участников в summary → `participants_raw=[]` почти везде → каскадно ломалось правило B (всё уходило в `unclear`).

**Правило (новое):** Для каждого FF-summary A.Сборщик подтягивает **парный transcript** и парсит участников оттуда.

1. Парный transcript ищется в той же папке `Meetings/NewMeetings/` по совпадению базового имени (соглашение MoveFromFF — `<base>.summary.md` ↔ `<base>.transcript.md` / `<base>.md`). MoveFromFF трогать не нужно.
2. `utils/ff_parser.parse_transcript_participants(transcript_text)` извлекает секцию `**Участники:**` (точное соответствие маркера FF в transcript) и возвращает `list[str]`.
3. **Фоллбэк 1 — speaker labels.** Если секция отсутствует, содержит `(нет)` или пуста — извлекаем уникальные speaker labels из тела transcript по паттерну `**Имя:**` (строки реплик). Дедуплицируем, тримим.
4. **Фоллбэк 2 — transcript отсутствует.** Тогда `participants_raw = []` и B обязан вернуть `route=unclear` (см. R3).

`participants_raw` пишется в `MeetingPackage` (как раньше), но теперь это **транскриптные участники**, не summary-участники.

### R3. Правило owner-participants

<!-- изменено 2026-06-22: R3 -->

**Owner** = `OWNER` (см. константы выше; login = `tkachenkoav`). После парсинга `participants_raw` A передаёт нормализованный список в B. B применяет правило (дублируется в TZ_B):

| Состав `participants_raw` (нормализованный) | Решение route |
|---|---|
| owner + 1 другой участник | `1on1` |
| owner + 2+ других участников | каскад (см. ниже) <!-- изменено 2026-06-22: I4 fix --> |
| только owner (или пусто, или `(нет)`) | `unclear` — невозможно определить тип встречи |

**Каскад для «owner + 2+ участников»** (критерий по числу алиасов, идентично TZ_B стр. 102): <!-- изменено 2026-06-22: J1 fix -->
1. Есть матч алиаса синка → `multisync`.
2. Иначе 2+ алиасов проекта → `multisync` (Шаг 5 TZ_B).
3. Иначе ровно 1 алиас проекта → `project` (Шаг 1 TZ_B).
4. Иначе → `unclear`.

⚠️ Owner-правило — **фоллбэк**, не override Шагов 0–6. Шаги 0–6 TZ_B применяются первыми; owner-правило уточняет интерпретацию при ≥2 участниках.

Owner определяется по строгому матчу email `tkachenkoav@tutu.ru` ИЛИ по разрезолву FIO/алиаса в `tkachenkoav` через ContactStore.

### R8. Дата встречи — fallback из имени файла

<!-- изменено 2026-06-22: R8 -->

В FF-summary поле даты иногда отсутствует или нечитаемо. Правило fallback:

1. `ff_parser.parse_ff_summary()` пытается найти дату в тексте summary (как раньше).
2. **Если не нашёл — берём первые 10 символов имени файла** в формате `YYYY-MM-DD`. Имя файла FF всегда префиксуется датой (соглашение MoveFromFF).
3. Если ни то ни другое — `date=None`, и B/F обязаны логировать `unclear` причиной «no_date».


## Источник A3 — Confluence-страницы проектов (добавлено 2026-06-21, расширено 2026-06-29)

> Решение по брифу 21.06.2026: Confluence — официальный источник по проектам АИД (см. главное ТЗ §7.1).
>
> ⚠️ **Расширение scope 29.06 (C4/PD-030):** <!-- изменено 2026-06-29 --> для проектов/инициатив бриф/устав из Confluence — это не только обогащение алиасов/участников/синков, но и **сид начального набора D-артефактов** (decisions + action_items + risks). При bootstrap устав подаётся как **«встреча №0»** — самая ранняя точка хронологического Haiku-прохода (см. TZ_C «Архитектура (единый проход)», шаг 1.1). Если устава нет — шаг пропускается, начинаем сразу с FF-встреч. Основной поток сигналов по-прежнему из FF-summary. Операционный prerequisite: выкачка Confluence (ConfluenceSync) до bootstrap проекта.

### Назначение

Подтянуть в локальную файловую систему официальные документы проектов (Confluence пространство DPAN) и извлечь:
- **aliases** — официальные названия → `classification_memory.json` (B)
- **participants** — команды проектов → `project_roles` в AC (E)
- **синки** — регулярные встречи → `syncs_memory.json` (H)
- **даты** — start_date/end_date → frontmatter `card.md` (D)
- **decisions / action_items / risks из устава** — сид D-артефактов как «встреча №0» (C/D, PD-030). <!-- изменено 2026-06-29 --> Только для проектов/инициатив; обрабатывается Haiku тем же проходом, что и FF-встречи.

### Структура хранения

```
WorkVault/Projects/<slug>/
├── card.md                       # frontmatter содержит confluence_id
├── confluence/
│   ├── _index.md                 # реестр страниц (см. главное ТЗ §7.1)
│   ├── <sanitized_title>.md      # текст страниц (HTML→MD), плоско
│   └── ...
```

Плоская структура (без вложенных папок) — все потомки корневой Confluence-страницы лежат рядом.

### Триггер выкачки

**Ночной cron 03:00 МСК (ВОП-5), не при каждом запуске пайплайна.** Скрипт `scripts/confluence_resync.py` (модуль A в Bootstrap + cron):
1. Для каждого slug ∈ active projects читаем `Projects/<slug>/card.md` → `confluence_id`.
2. Если `confluence_id is None` → skip (slug без Confluence — допустимо для исторических).
3. Иначе вызываем `ConfluenceSync.sync(root_id=confluence_id, dest_dir=Projects/<slug>/confluence/)`.
4. ConfluenceSync сравнивает Confluence `updated_at` с `last_synced_at` из `_index.md` и качает только обновлённые страницы.
5. Обновляет `_index.md`.

### API ConfluenceSync

Инструмент готов: `~/USERTOOLS/ConfluenceSync/`. Доступ: `CONFLUENCE_URL` + `CONFLUENCE_TOKEN` (Bearer) в `~/.config/hermes/.env`.

```python
from confluence_sync import ConfluenceSync
cs = ConfluenceSync(url=os.environ["CONFLUENCE_URL"], token=os.environ["CONFLUENCE_TOKEN"])
report = cs.sync_subtree(
    root_id=480923430,                              # из card.md → confluence_id
    dest_dir=Path("Projects/trisigma/confluence/"),
    skip_images=True,                                # без картинок
    flat=True,                                       # плоская структура
)
# report = {"pages_total": 12, "pages_updated": 3, "pages_skipped": 9}
```

### Извлечение метаданных

После выкачки A.Сборщик передаёт **обогащающие сигналы** в B/E/H через специальный bootstrap-вызов (не на каждую встречу!):

```python
def confluence_extract_signals(slug: str) -> ConfluenceExtractedSignals:
    """Вызывается раз в сутки (или по триггеру PM)."""
    return {
        "aliases": [...],          # заголовки страниц + bold-выделения → в classification_memory
        "participants": [...],     # таблицы команд → в AC.add_project_role()
        "syncs": [...],            # упоминания регулярных встреч с составом → в syncs_memory
        "dates": {"start": ..., "end": ...},  # из карточек → в card.md frontmatter
    }
```

### Bootstrap-волна 1 (21.06.2026)

Перед запуском первого end-to-end-прогона пайплайна — однократно качаем все Confluence-IDs из реестра §3.2 главного ТЗ + DataTalks (331125745) + Синк Руководителей АИД (331125844). См. RUN_IMPLEMENTATION / IMPLEMENTATION_PLAN.

### Запрос уставов перед bootstrap (PD-048, Q-A9, бриф 30.06)

<!-- изменено 2026-06-30 -->

Шаг до bootstrap каждого проекта:

1. **Запросить устав** по каждому проекту из реестра slug-ов — PM предоставляет Confluence URL/документ устава (по мере готовности, PD-029).
2. **Устав предоставлен** → парсинг устава в сигналы → сид `decisions / action_items / risks` как «встреча №0» (самая ранняя точка Haiku-прохода, TZ_C шаг 1.1).
3. **Устава нет** → aliases-only: bootstrap проекта начинается с первой FF-встречи, D не сидируется.
4. **Парсинг даёт мусор** → откат на aliases-only без сидирования D (защита от загрязнения).
5. Проверить качество сид-парсинга на `trisigma` и `ml-platforma` (есть golden refs).

**Обязательный вопрос PM перед стартом bootstrap (Q-B7, бриф 30.06):** агент **не запускает bootstrap молча** — сначала выводит PM список проектов из реестра slug-ов с разметкой статуса устава:
- какие уставы уже подтверждены (есть Confluence URL): на старте — `trisigma`, `ml-platforma`;
- по каким уставов **нет** — спросить у PM: «дать URL устава сейчас или запускать bootstrap без сидирования D (aliases-only)?».

PM отвечает по каждому недостающему проекту (URL или «без устава»). Только после ответа bootstrap стартует. Вопрос операционный, не блокирует разработку кода Фазы B.

### Открытые вопросы по A3

- **Глубина выкачки subtree** — без ограничений (бриф 21.06 В17).
- ~~**Resync на ходу** — фоном при каждом запуске A, или отдельный cron?~~ ✅ **Закрыто (ВОП-5, бриф 22.06):** Confluence resync — **отдельный ночной cron раз в сутки**, не при каждом запуске AggregateFromMeetings. См. IMPLEMENTATION_PLAN, Фаза 0 — cron-job `confluence_resync.py`.
- **Что делать с DataTalks/Синк АИД** — они описывают синки, не проекты; класть в `Syncs/<slug>/confluence/` (по аналогии)? — пока кладём как обогащение `syncs_memory`.

## Назад
- ↑ [[../TZ_aggregate_main]]
