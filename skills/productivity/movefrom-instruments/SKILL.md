---
name: movefrom-instruments
description: "Семейство инструментов MoveFrom* — выгрузка данных из корпоративных сервисов в локальный WorkVault (Obsidian). Общая архитектура, принципы, бэклог."
version: 1.0.0
author: agent
tags: [workvault, obsidian, sync, pipeline, jira, confluence, exchange, zulip, fireflies]
platforms: [windows]
---

# MoveFrom* — инструменты выгрузки данных в WorkVault

Семейство Python-инструментов для выгрузки данных из корпоративных и внешних сервисов в локальный Obsidian vault (`WorkVault`). Каждый инструмент — поставщик данных для конвейера обработки.

## Принципы (обязательны для всех инструментов)

1. **Минимум файлов на единицу данных** — не обрабатывать смысл, только перенести как есть. Количество файлов определяется ценностью: `actions.md` для FF — дубль `summary.md`, поэтому не нужен. Не добавлять файлы ради полноты — только если несут уникальную ценность.
2. **Идемпотентность через `_registry.json`** — не качать повторно уже загруженное
3. **Никакой постобработки** — это зона следующих инструментов конвейера (MarkObjectsFromSummary и др.)
4. **Минимальная статусная машина загрузки:** `pending` / `completed` / `error`
5. **`_registry.md`** — рендерится из JSON через Jinja2, без доп. запросов к API
6. **TG-алерты только при ручном запуске** с ошибкой. Cron — тишина, всё в `_log.md`
7. **Атомарная запись:** `tmp + os.replace` для всех файлов и реестра
8. **Разработка и ТЗ — только через Opus** (`delegate_task model=claude-opus-4-7`)

## Структура инструмента (шаблон)

```
MoveFrom<Service>/
├── movefrom<service>/
│   ├── __main__.py      ← CLI оркестрация: preflight → ping → skip-or-download → finalize
│   ├── config.py        ← Settings из .env
│   ├── client.py        ← API клиент (requests + tenacity retry)
│   ├── schema.py        ← Pydantic модели данных
│   ├── writer.py        ← запись файлов, атомарная, rollback при ошибке
│   ├── renderer.py      ← _registry.md из JSON через Jinja2
│   ├── registry.py      ← _registry.json: load/save/migrate, portalocker
│   ├── lock.py          ← portalocker single-instance guard
│   ├── logger.py        ← _log.md (одна строка/запуск) + jsonl events
│   ├── tg.py            ← TG-алерты (только manual mode; cron молчит)
│   └── templates/
│       ├── registry.md.j2
│       └── *.md.j2      ← шаблоны файлов
├── tests/
├── .env
└── .venv/
```

**Количество файлов на единицу данных определяется ценностью, не полнотой.** Не добавлять файлы ради полноты. Пример: MoveFromFF — 2 файла (transcript + summary), actions убран как дубль.

## Коды выхода CLI (стандарт)

| Код | Значение |
|---|---|
| 0 | Успех |
| 1 | Частичный успех (часть записей упала) |
| 2 | Lock занят / preflight провален |
| 3 | Сервис недоступен / auth-ошибка |
| 4 | Фатальная ошибка |

## Режимы CLI (стандарт)

| Режим | Описание |
|---|---|
| `--mode test` | Последние 5 дней |
| `--mode cron` | Новые с момента `_last_sync - overlap` |
| `--mode manual --from-date ... --to-date ...` | Произвольный период |

## 🎯 Цели департамента — главный контекст

Все проекты — кусочки для достижения **целей департамента Аналитики и данных (ТУТУ)**.
Проекты — временные рамки. Цель департамента — главное.

**При оценке любой идеи или задачи — сначала спросить:**
> "Как это соотносится с целями департамента?"

Цели фиксируются в Jira проект **OKRAID**. Проекты — **OKRS**.
Задача: выгрузить OKRAID + OKRS → разметить все проекты по принадлежности к целям.

---

## 🚀 Быстрая постановка задачи через TG

```
Пользователь наговариваешь задачу
→ Сирень показывает: кому / что / срок
→ Задаёт вопросы по одному:
   1. К какой цели департамента? (OKRAID)
   2. К какому проекту? (OKRS)
→ Пользователь подтверждает/правит
→ Публикация в Jira
```

Когда OKRAID+OKRS загружены в кэш — предлагать цель/проект сам, не спрашивать каждый раз.

---

## Две главные цели системы (зафиксировано 22 мая 2026)

1. **Задача доходит правильно** — чёткая формулировка + правильный исполнитель + срок. Лучше уточнить чем опубликовать неправильно.
2. **Риски выявляются рано** — из реальных данных, до того как стало поздно. PMBOK-подход. Риски оперативные — сегодняшнего дня. Возможности = риски со знаком плюс.

**⚠️ Риск-модуль заморожен до готовности сбора контекста.** Сначала: собрать контекст со всех каналов → страница проекта с текущей ситуацией → PMBOK-разметка.

## Железное правило публикации

Система **никогда не публикует задачи автономно** в Jira, мессенджеры и публичные каналы. Только через человека:
1. Система нашла задачу → пишет в TG для подтверждения (в т.ч. резолвит ambiguous сущности)
2. Пользователь подтверждает или правит
3. Только после подтверждения → публикация

## Шаблон страницы проекта (зафиксировано 22 мая 2026)

Ориентир: `personal-ai-assistant-master@79d67c32f4c/workflows/PROJECT_ONBOARDING_WORKFLOW.md`

```markdown
# Название проекта
## Цель
## Ближайшие ключевые задачи
## 🔴 Critical (не понимаем как / активно обсуждается)
## Открытые вопросы
## Ключевые решения (память договорённостей)
## Всё остальное
```

Принцип: сверху — что нужно прямо сейчас, снизу — архив.
Critical ≠ Открытые вопросы: Critical = не знаем как решить или активный конфликт мнений.
Формат уточняется по мере работы с реальными страницами проектов.

## Классификация встреч по проектам

Не требует ручной разметки. LLM читает саммари → определяет контекст → пользователь правит если не так. Реестр проектов с `aliases` подаётся как контекст для резолвера.

## Две страницы проекта (зафиксировано 22 мая 2026)

| Тип | Где | Назначение |
|---|---|---|
| **Локальная** | WorkVault (Obsidian) | Рабочая черновая версия. Обновляется автоматически из всех источников. Только для нас двоих. |
| **Публичная** | Confluence | Видит команда. Публикуется только по команде пользователя после просмотра локальной. |

**Схема публикации в Confluence:**
```
Локальная страница обновилась
→ пользователь говорит "опубликуй проект X"
→ Сирень показывает что именно изменилось
→ пользователь подтверждает
→ публикация через Confluence API (credentials в .env)
```

## Стиль работы с пользователем (Саша / Сирень)

- **Диалог с уточняющими вопросами** — задавать один вопрос за раз, не монолог
- Вопросы помогают отрезать лишнее и двигаться к сути быстрее
- При постановке задачи через TG — всегда спрашивать: 1) к какой цели департамента, 2) к какому проекту
- Когда OKRAID+OKRS загружены в кэш — предлагать сам, не спрашивать каждый раз
- Лишний раз не переспрашивать если можно догадаться самой

## Архитектура хранилища сущностей (зафиксировано 22 мая 2026)

- **Хранилище + редактирование** → `.md файлы в WorkVault` с YAML frontmatter (Obsidian)
- **Аналитика и запросы** → Obsidian Dataview plugin (SQL-подобный синтаксис по YAML frontmatter)
- **Один источник правды** — никакой параллельной БД рядом с .md файлами
- Пользователь знает SQL → Dataview не потребует обучения

**Почему не SQLite рядом:** два источника правды сложнее поддерживать. .md+Dataview — нативно для Obsidian, уже установлен, ручное редактирование — открыл файл, исправил, закрыл.

## Wiki-ссылки и карточки сущностей (зафиксировано 24 мая 2026)

**Все сущности в frontmatter summary.md — wiki-ссылки Obsidian:**
```yaml
---
contacts:
  - "[[Иван Иванов]]"
  - "[[Мария Петрова]]"
projects:
  - "[[Тризигма]]"
  - "[[Аналитика данных 2026]]"
---
```

**Формат имени контакта:** `[[Имя Фамилия]]` — сокращённое (без отчества).

**Карточки контактов:** для каждого смаченного контакта создаётся/обновляется файл `Contacts/Иван Иванов.md`. Wiki-ссылка должна вести на реальный файл — иначе в Obsidian «сломанная» ссылка. MarkObjectsFromSummary создаёт эти файлы автоматически из contacts.enc.

**Структура карточки контакта:**
```yaml
---
email: ivan.ivanov@tutu.ru
fio_full: Иванов Иван Иванович
department: Аналитика и данные
team: BI
position: Руководитель группы
is_internal: true
aliases:
  - Ваня
  - Иванов
messengers:
  telegram: "@iivanov"
  zulip: "ivan.ivanov"
---
# Иван Иванов
```

**Источник правды — `contacts.enc`.** Карточка `.md` — только отображение для Obsidian, генерируется/обновляется автоматически. Карточка НЕ удаляется инструментом — только создаётся и обновляется.

**Папка карточек:** `Contacts/` в WorkVault. Старые файлы (до перехода на contacts.enc) — удаляет пользователь вручную разово.

**Проекты тоже wiki-ссылки:** `[[Тризигма]]` ведёт на файл проекта. Файл проекта создаётся отдельным инструментом (не MarkObjectsFromSummary v0.1). В v0.1 — только контакты.

## Entity Resolver — правила (зафиксировано 22 мая 2026)

**Три состояния:**
- `resolved` — высокая уверенность: точное совпадение с `canonical_name` или `aliases`, либо email совпал с Exchange GAL
- `ambiguous` — текст в файле помечается суффиксом `(?)`, например `ML платформа TUTU (?)` — сигнал для ручного ревью в Obsidian
- `unknown` — сущность не тронута, оставлена сырым текстом из саммари

**Главное правило: не угадывать.** Лучше пропустить чем соврать. Резолвер матчит только при высокой уверенности.

**Ключи сущностей:**
- **Контакт** → `email` (из Exchange GAL, универсальный ключ)
- **Проект** → `canonical_name` + список `aliases` в файле проекта

**Почему aliases решают проблему проектов:** в ТУТУ за 5 лет не повторилось ни одного проекта. Пользователь маркирует встречи. Коллизии крайне маловероятны. Реестр aliases пополняется и процент авторезолва растёт сам.

**Исключение:** один термин может означать разные сущности (например "АБ платформа" = старая ТУТУ или новая Trisigma). В этом случае резолвер → `ambiguous (?)`, не угадывает по контексту.

## Архитектура многослойного конвейера

```
Слой 0 — Сбор (MoveFrom*): сырые данные из источников, без обработки смысла
Слой 1 — Резолвер сущностей (Entity Resolver): Exchange GAL как "золотые записи" людей
          email = универсальный ключ связи между всеми источниками
Слой 2 — Структурирование (MarkObjects*/ProcessFrom*): извлечение сущностей, YAML-frontmatter
Слой 3 — Аналитика (PMBOK + риски): выявление сигналов из реального потока данных
```

**Принцип распределения ответственности:**
- Fireflies (и другие внешние сервисы) — дешёвая первичная обработка 24/7 (STT, черновые таски)
- MoveFrom* — минимальный транспорт, не оценивает качество данных источника
- Entity Resolver + Opus — качественная обработка только на уже структурированных данных

### Приоритет инструментов (пересмотрено 22 мая 2026)

1. **MoveFromExchange (contacts/GAL)** — эталонный справочник людей (email = универсальный ключ)
2. **MoveFromJira (только OKRAID + OKRS)** — цели департамента и проекты. Нужен для быстрой постановки задач через TG — без него не работает
3. **Быстрая постановка задачи через TG** — реализовать после п.1 и п.2

**Источники целей:**
- Цели департамента → Jira проект **OKRAID**
- Проекты → Jira проект **OKRS**

**Если предлагается разработка другого инструмента раньше Exchange contacts или Jira OKRAID/OKRS — напомнить про этот порядок.**

---

### Приоритет #1: MoveFromExchange (режим contacts/GAL)

Без эталонных записей людей все инструменты конвейера работают вслепую.
Exchange GAL даёт: ФИО (полное, официальное), email (уникальный ключ), должность, отдел.

Email как универсальный ключ связывает:
- Fireflies → участники встреч (`participants[]`)
- Zoom → участники по email
- Jira → маппинг логин ↔ email
- Zulip → email при регистрации
- Exchange → сам является источником эталона

Результат: один раз загрузил GAL → "золотые записи" для резолвера всех остальных инструментов.

**Если предлагается разработка другого инструмента раньше Exchange contacts — напомнить про эту договорённость.**

## MoveFromFF — полная карта полей Fireflies API (исследовано 27.05.2026)

GraphQL-запрос для полного summary (все полезные поля):
```graphql
query {
  transcripts(limit: N) {
    id title date
    summary {
      overview short_summary gist bullet_gist shorthand_bullet
      outline action_items keywords
      extended_sections { title content }
    }
    apps_preview {
      outputs { app_id title response created_at }
    }
  }
}
```

**Стабильно заполнены (все встречи):**
- `overview` — 5 буллетов, executive summary (~570–750 символов)
- `short_summary` — один связный абзац (~650 символов), удобен для уведомлений
- `gist` — одна фраза, цель встречи (~100 символов). Уникальный источник
- `bullet_gist` — те же 5 пунктов что overview, но с эмодзи. Уникальный источник
- `shorthand_bullet` — таймлайн встречи по фазам с таймкодами (MM:SS-MM:SS) + эмодзи-заголовки (~1500–1800 символов). Уникальный взгляд «как шла встреча по времени»
- `action_items` — plain-text строка, задачи сгруппированы по ФИО исполнителя с таймкодами. Единственный нативный источник «задача → человек»
- `keywords` — list[str], ~6 тегов. Для тегирования/поиска
- `extended_sections` — стабильно 4 секции: `Blockers`, `Questions`, `Meeting Outline`, `Topics`. Единственный источник блокеров и открытых вопросов с таймкодами
- `apps_preview.outputs` — 2 элемента: `1:1` и `Meeting Summary Generator`. Meeting Summary Generator — самый полный протокол (4.5–7 КБ): список участников с ФИО, расширенное обсуждение, блокеры с ответственными, задачи по людям со сроками

**Маппинг FF UI → API поля (проверено на встрече 01KSJ49AGHYFJTRARWAD088Q7N, 27.05.2026):**

| Блок в FF UI | API поле | Примечание |
|---|---|---|
| Bullet points вверху страницы | `summary.overview` | 5 буллетов с жирным заголовком |
| **Notes** | `summary.extended_sections` | FF называет их "Notes", рендерит 4 секции: Blockers / Questions / Meeting Outline / Topics |
| **1:1** (голубая карточка Custom Skill) | `apps_preview.outputs` где `title="1:1"` | Gist + Key Topics Discussed + Key Takeaways + Action Items + Decisions Made |
| **Meeting Summary Generator** (жёлтая карточка Custom Skill) | `apps_preview.outputs` где `title="Meeting Summary Generator"` | Самый полный протокол на русском: участники, обсудили, блокеры, задачи по людям |

Все три блока (Notes, 1:1, Meeting Summary Generator) — **отдельные визуальные блоки** в FF UI, не один блок.

**`outline` — ВСЕГДА null.** Не использовать. Структуру встречи даёт `extended_sections[title="Meeting Outline"]`.

**`notes` — НОВОЕ ПОЛЕ (обнаружено 27.05.2026).** Содержит тематический нарратив ~6KB с подзаголовками. В FF UI отображается как блок "Notes" сразу после Bullet points. Это НЕ `extended_sections` — отдельное поле типа String. Добавить в GraphQL-запрос и в шаблон summary.md.j2. ТЗ: `WorkVault/Hermes-Backlog/_Done/ТЗ-MoveFromFF-summary-fields-20260527.md`.

**Реальная форма `extended_sections`:** поле называется `content` (не `items`). Структура: `{ title: String, content: String }`. `items` не существует на нашем тарифе.

**Возможен полностью пустой summary** (короткая/прерванная запись) — все поля null, `apps_preview.outputs = []`. Код должен обрабатывать корректно.

**Рекомендации по использованию:**
- Компактный превью → `short_summary` или `overview`
- Визуальная шпаргалка → `bullet_gist` или `shorthand_bullet`
- Задачи по людям → `action_items` (нативно) или `apps_preview[Meeting Summary Generator]` (детальнее)
- Блокеры/вопросы с таймкодами → `extended_sections`
- Полный архивный протокол → `apps_preview.outputs[Meeting Summary Generator].response`

Тестовый скрипт: `USERTOOLS/MoveFromFF/test_ff_full_summary.py`

## MoveFromFF — архитектурные решения (22 мая 2026, КОД ЗАМОРОЖЕН)

Код заморожен до финализации ТЗ. Только обсуждение и документирование решений.

**Что качать из Fireflies:**
- ✅ **summary** — основной рабочий материал. Структурирован, компактный, ФИО полные. Черновые таски Fireflies здесь — тоже ценны как отправная точка.
- ✅ **transcript** — архив. Хранить, не обрабатывать постоянно. Использовать точечно: "что именно было сказано про X?"
- ❌ **actions** — дубль Action Items из summary. **ФИНАЛЬНОЕ РЕШЕНИЕ: не скачивать** (май 2026). В ТЗ v2.0 нужно убрать из алгоритма, схемы реестра и шаблонов.

**Роль Fireflies в конвейере:**
Только STT (speech-to-text) + первичная разметка спикеров. Саммари и таски от FF — черновик, не финал. Качественную обработку (извлечение сущностей, правильная атрибуция задач) делаем своими моделями (Opus) с контекстом Exchange GAL.

**Почему так:** Fireflies не знает оргструктуру, не знает кто есть кто → кривые таски, размытые саммари. После подключения Exchange GAL точность резолвера вырастет автоматически.

## AnywhereContacts — статус реализации (28.05.2026)

**✅ Реализован и работает.** Opus выполнил все 4 этапа:
- `USERTOOLS/AnywhereContacts/` — пакет создан, 22/22 теста зелёные
- MoveFromExchange рефакторнут в тонкий коннектор, 32/32 теста зелёные
- MoveFromZulip создан, боевой синк выполнен: **2148 контактов** (1747 Exchange + 401 только Zulip)
- Schema v2 с `sources` в production
- migration v1→v2 происходит автоматически при первом чтении

**Zulip синк:** воскресенье 03:00 (job_id: `50a30903f503`)

**PII Masking при выводе контактов (КРИТИЧНО):**
Функция `mask_contact(contact)` экспортируется из `anywhere_contacts`.
Вызывать ВСЕГДА перед выводом в Telegram или CLI.
```python
from anywhere_contacts import mask_contact
hits_for_display = {k: mask_contact(v) for k, v in hits.items()}
```
Правильно: `Кр**в Ки**л`, `kr**v@tutu.ru`. Без маскировки — ошибка.

Общая библиотека для всех коннекторов MoveFrom*. MoveFrom* становятся тонкими коннекторами.

### Что переезжает в AnywhereContacts
- `crypto.py` — шифрование AES-256-GCM (полностью generic)
- `store.py` — ContactStore, create_store (публичный API)
- `logger.py` — SyncLogger + PII-маскеры (расширяемые через register_pii_masker)
- `lock.py` — FileLock (общий lock на contacts.enc)
- `merger.py` — рефакторинг: ContactMerger.merge(local, incoming, strategy) + MergeStrategy
- `settings.py` — ContactsBaseSettings (pydantic, базовый класс для всех коннекторов)
- `schema.py` — dataclass Contact + константы полей

### Что остаётся в коннекторах
- `filters.py` — правила что отбрасывать (Exchange: 4 правила; Zulip: is_bot/is_active)
- `<source>_client.py` — API-клиент к источнику
- `mapper.py` — нормализация raw API record → стандартный contact dict
- `config.py` — только специфичные credentials/URL (наследует ContactsBaseSettings)
- `sync.py` — оркестрация синка через MergeStrategy

### Ключевые архитектурные решения (28.05.2026)

**Первичный ключ — `login` (не email).** Причина: у одного человека может быть @tutu.ru в Exchange и @tutu.tech в Zulip. Логин одинаков, email разный. По логину мержим в один контакт.

**Schema v2 — multi-source.** Структура sources внутри контакта:
```json
{
  "login": "sereda",
  "email": "sereda@tutu.ru",
  "sources": {
    "exchange": {"email": "sereda@tutu.ru", "synced_at": "...", "active": true},
    "zulip":    {"email": "sereda@tutu.tech", "synced_at": "...", "active": true}
  },
  "active": true
}
```
`active` верхнего уровня = `any(source.active)`. Требует migration contacts.enc v1 → v2.

**Общий lock — `WorkVault/Contacts/.contacts.enc.lock`.** Один файл на всех коннекторов. Параллельный запуск двух коннекторов безопасен.

**messenger_ids с source.** Каждое значение фиксирует источник:
```json
"messenger_ids": {
  "telegram": {"value": "@sereda", "source": "zulip", "synced_at": "..."},
  "zulip_id":  {"value": 12345,    "source": "zulip", "synced_at": "..."}
}
```
`source: "manual"` — коннектор не перезаписывает. `source: "zulip"` — перезаписывает при синке.

**is_active=false из Zulip — НЕ пишем в contacts.** Просто пропускаем.

### Минимум кода для нового коннектора (~150 строк)
mapper.py + filters.py + client.py + config.py + sync.py + __main__.py.
MergeStrategy описывает поведение: source, authoritative_fields, filter_fn.

### Структура пакетов
```
USERTOOLS/
├── AnywhereContacts/          ← библиотека (не CLI)
│   └── anywhere_contacts/
│       ├── crypto.py, store.py, logger.py, lock.py, merger.py
│       ├── schema.py, settings.py, connector.py
│       └── __init__.py        ← публичный API (re-exports)
├── MoveFromZulip/             ← тонкий коннектор
│   └── movefromzulip/
│       ├── zulip_client.py, mapper.py, filters.py, config.py, sync.py
│       └── __main__.py
└── MoveFromExchange/          ← рефакторинг: остаются только exchange-специфичные части
```

## Статус инструментов

**MoveFromZulip** — бриф согласован 2026-05-28, ТЗ не написано (следующий шаг).
Детали брифа: `references/movefromzulip-brief-v1.md`.
Zulip — основной источник контактов (1 запрос `GET /api/v1/users`). Exchange — верификация.

| Инструмент | Сервис | Статус | ТЗ |
|---|---|---|---|
| MoveFromFF | Fireflies.ai | ✅ **v2.2 готов** — 8 секций summary (Bullet points/Notes/Action items/Blockers/Questions/Meeting Outline/Topics/Keywords), reconciliation (сброс в pending при удалении файлов), backfill (fetch по ID, лимит 50/прогон, newest-first), 83 теста ✅. Крон: пн–пт 10:00–20:00 МСК каждые 2ч (job_id: 1e62e18ae399). | `USERTOOLS/MoveFromFF/MoveFromFF_TZ_v2.2.md` (обновить) |
| MoveFromExchange | Exchange (ТУТУ) | 🟡 **v1.0 работает, v1.1 в разработке** — 1787 контактов (после фильтрации ~944). ТЗ v1.1 согласовано 27.05.2026: filters.py (4 правила), XLSX убран, contacts.jsonl с маскировкой, TG-поиск контактов с маскировкой (Ив**в, iv**v@tutu.ru). Крон-путь сломан (старый), починить после реализации v1.1. | `USERTOOLS/MoveFromExchange/MoveFromExchange_TZ_v1.1.md` |
| MarkObjectsFromSummary | WorkVault | 🟡 **Бриф завершён (блоки A-F+G), ТЗ не написано.** БЛОКЕР: нужен письменный список проектов/тем/инициатив от Саши с точными названиями и алиасами → файл `projects.md`. Без него ТЗ v0.1 можно написать (только контакты), но в реализацию v0.2+ не идти. | `hermes-workspace/docs/tz/MarkObjectsFromSummary_TZ_v0.1.md` (не создан) |
| MoveFromJira | Jira (ТУТУ) | 🥈 **Приоритет #2** — только OKRAID + OKRS (цели и проекты). Нужен для быстрой постановки задач через TG. Jira доступна без VPN (`dom.tutu.ru`, PAT в `.env`). | — |
| ConfluenceSync | Confluence (`dom.tutu.ru`) | ✅ **v1.0 реализован (28.05.2026).** 47/47 тестов зелёные. `pip install -e .` выполнен. CLI: `confluencesync pull/push/resync/log`. Двусторонний (read + write). PAT работает из дома без VPN. Путь проекта: `USERTOOLS/ConfluenceSync/`. Хранение: `WorkVault/Confluence/<Space>/<Страница>/index.md`. Скилл: `movefrom-confluence`. Логи: `WorkVault/_meta/ConfluenceSync/_sync_log.jsonl`. Режимы: `--to-file`, `--to-context`, `--to-both`. Флаг `confirm=True` по умолчанию, `confirm=False` для программных вызовов. Credentials: `USERTOOLS/MoveFromConfluence/.env`. **Питфолл:** передавать конкретный URL страницы (pageId или /display/SPACE/Title), не корень домена. | `USERTOOLS/ConfluenceSync/TZ.md` |
| MoveFromZulip | Zulip (ТУТУ) | ⏸ **КРОН ОСТАНОВЛЕН (29.05.2026)** — Zulip отключают, переходят на Loop (Mattermost). Крон на паузе чтобы не перетёрлись контакты. 2148 контактов сохранены. | `USERTOOLS/MoveFromZulip/TZ.md` |
| MoveFromLoop | Loop/Mattermost (ТУТУ) | 🆕 **Планируется** — Loop это Mattermost API v4 (loop.tutu.ru/api/v4). АКЦ остаётся в Zulip (zulip-outsource.tutu.ru). Нужен Personal Access Token: Loop → Настройки → Безопасность → Токены доступа. | — |

## Credentials (корпоративные сервисы ТУТУ)

Единая доменная учётка `tkachenkoav@tutu.ru` работает для Confluence, Jira, Exchange, Zulip.

**Хранить как Personal Access Token (не пароль):**
- Confluence/Jira: профиль → Personal Access Tokens → Create (администратор не нужен)
- Zulip: Settings → Your account → API key
- Exchange: on-premise → basic auth логин+пароль; Office 365 → OAuth client (нужен admin)

**В `.env` каждого проекта:**
```
TUTU_USERNAME=tkachenkoav@tutu.ru
TUTU_TOKEN=<personal_access_token>
TUTU_BASE_URL=https://dom.tutu.ru
TG_ALERT_CHAT_ID=400307920
```

`redact_secrets: true` в Hermes config уже включён — токены в логах маскируются.

## Правило хранения ТЗ (зафиксировано 27.05.2026)

**Master-ТЗ** хранится в папке инструмента: `USERTOOLS/<tool>/<Tool>_TZ_vX.Y.md`
- Обновляется при каждой доработке
- Это единая точка правды по инструменту

**История точечных изменений** → `WorkVault/Hermes-Backlog/_Done/ТЗ-<Tool>-<feature>-YYYYMMDD.md`

При любой доработке инструмента — обновлять master-ТЗ в папке инструмента.

## MoveFromExchange — маскировка персданных (27.05.2026)

Правило для contacts.jsonl и TG-отображения:
- **ФИО:** первые 2 + последняя буква открыты, середина `**` → `Ив**в Ал**р`
- **Email:** первые 2 + последняя до `@` открыты, домен открыт → `iv**v@tutu.ru`
- **Логин:** аналогично email → `iv**v`
- **Telegram handle:** `@iv**v`

TG-поиск контактов: по имени/фамилии, до 5 результатов, поля: ФИО, email, логин, отдел, команда, должность, алиасы, мессенджеры — все с маскировкой.

## MoveFromFF — reconciliation + backfill (27.05.2026)

**reconcile_registry()** в `registry.py`: при каждом синке проверяет completed-записи на наличие файлов на диске. Если файл удалён → статус сбрасывается в `pending`.

**Backfill второй проход** в `__main__.py`: после основного fetch_range — делает fetch_meeting(id) для всех pending-записей с известным ID. Лимит 50/прогон, сортировка **newest-first** (`reverse=True`). Rate limit → прерывает backfill, оставшиеся в pending подхватятся на следующем cron.

Результат: удалил файл руками → следующий cron перекачал автоматически в правильном формате.

## Правило хранения ТЗ (зафиксировано 27.05.2026)

**Живое полное ТЗ** каждого инструмента хранится в папке инструмента:
`USERTOOLS/<Инструмент>/<Инструмент>_TZ_vX.Y.md`

Примеры:
- `USERTOOLS/MoveFromFF/MoveFromFF_TZ_v2.1.md` — обновляется при каждой доработке
- `USERTOOLS/MoveFromExchange/MoveFromExchange_TZ_v1.1.md` — создан 27.05.2026

`WorkVault/Hermes-Backlog/_Done/` = **история точечных изменений** (ТЗ на конкретную фичу).

**При каждой доработке инструмента:** обновлять master-ТЗ в папке инструмента, не только создавать точечное ТЗ.

## Все ТЗ и бэклог

`/home/tkachenkoav/WorkVault/Hermes-Backlog/`

## Ежедневный self-check Сирени (крон 03:00 МСК, Opus)

Задача: `e7a53b2e2cf2` — каждую ночь в 03:00 Opus:
1. Проверяет консистентность скиллов и настроек
2. Аудит распределения задач по моделям (Haiku/Sonnet/Opus)
3. Проверяет новые коммиты в hermes-agent от разработчиков
4. Ищет улучшения на hermes-agent.nousresearch.com
5. Сохраняет отчёт: `WorkVault/Hermes-Backlog/self-check-YYYY-MM-DD.md`

**Принцип распределения моделей:**
- Opus — анализ, разработка, планирование, глубокие вопросы
- Sonnet — основное общение с Сашей
- Haiku — простые терминальные задачи (git push, cp, ls), шутки, лёгкий разговор

**⚠️ Способ делегирования на Opus — через cronjob, не delegate_task:**
`delegate_task` с Opus (reasoning_effort=high, child_timeout=1200) держит родительский стрим и вызывает gateway-зависания (подтверждено логами: "Stream stale for 180s", "Subagent stale"). Длинные задачи (>5 мин) — всегда через `cronjob(repeat=1, model={"model":"claude-opus-4-7",...})`. `delegate_task` — только для коротких задач на Sonnet/Haiku.

## Правила разработки и ТЗ (ОБЯЗАТЕЛЬНО)

- **ТЗ пишет и правит — всегда Opus** (`delegate_task model=claude-opus-4-7`). Даже мелкие правки — Opus. Haiku для ТЗ недопустим.
- **После любой правки ТЗ — Opus проверяет все смежные ТЗ** инструментов на непротиворечивость. Смежные = инструменты которые читают/пишут общие файлы или вызывают друг друга.
- **Код пишет Opus** (delegate_task model=claude-opus-4-7)
- **Финальная проверка кода — Haiku** читает код и ТЗ, находит расхождения, докладывает
- **Справочные вопросы** («как работает X», «что написано в ТЗ») → Haiku с fallback на Sonnet
- **⛔ СТРОГОЕ ПРАВИЛО: разработку любого инструмента/фичи запускать ТОЛЬКО по ТЗ и ТОЛЬКО после явного "ок, берём в работу" от Саши в TG.** Никакой реализации "по ходу" или "на основе обсуждения". Обсуждение → ТЗ на согласование → явное подтверждение → только тогда cronjob/delegate_task на реализацию.

## MarkObjectsFromSummary — архитектурные решения брифа (24 мая 2026)

**Область v0.1:** только матчинг контактов (email из participants → contacts.enc → wiki-ссылки в frontmatter + карточки Contacts/).

**Отдельный реестр `_mark_objects_registry.json`** — инструмент не трогает `_registry.json` MoveFromFF. Структура:
```json
{
  "schema_version": "1.0",
  "meetings": {
    "<meeting_id>": {
      "processed_at": "2026-05-24T14:00:00+03:00",
      "status": "ok",
      "contacts_matched": 3,
      "contacts_unmatched": 1,
      "unmatched_speakers": ["Speaker 1"],
      "files": { "summary": "path/to/summary.md" }
    }
  }
}
```

**Статусы встречи:** `ok` / `empty` (встреча без слов) / `no_participants` (участников нет) / `error`. Пустые и без участников не пропускать — фиксировать в реестре.

**Классификация контактов:**
- Внутренние домены: `@tutu.ru`, `@tutu.tech` (пополнять по результатам Exchange)
- Внешние → contacts.enc с `is_internal: false` (единый файл для всех)
- Служебные ящики (`noreply@`, `vendor@`) → игнорировать, не заводить
- Внутренний не найден в GAL → статус `undefined`
- Speaker без email → `unmatched_speakers` в реестре, не в contacts.enc
- `ignore: true` в contacts.enc → инструмент навсегда пропускает этот email

**Крон:** сразу после MoveFromFF (каждые 2 часа пн–пт 10–20 МСК).

**Режим `--rematch`:** перематчить уже обработанные встречи — по одной (`--meeting-id`), за период (`--from`/`--to`), все (`--all`). Нужен когда контакт добавлен в contacts.enc задним числом.

**Папки по МСК** (Europe/Moscow).

**Жизненный цикл заготовки:** заготовка «готова» после прохода MoveFromExchange (GAL заполнил ФИО/должность). Но функционально — рабочая как только матчим на неё задачи из summary, даже если поля неполные.

**Уведомления:** нет. Только лог. Сводки — по запросу пользователя.

**Проекты в v0.1:** не размечаются. БЛОКЕР для v0.2+: Саша должен передать письменный список проектов/тем/инициатив с точными названиями и алиасами → файл `projects.md`.

## Паттерн массовой загрузки исторических данных

При первичной загрузке большого периода (например, полгода встреч из FF):
1. Загружать помесячно через `--mode manual --from-date ... --to-date ...`
2. Делать паузу 10 секунд между месяцами (`sleep 10`)
3. Можно запустить одной shell-командой с цепочкой `&&`
4. Rate limit FF сбрасывается в **00:00 UTC** каждые сутки — если исчерпан, ждать до 03:00 МСК
5. Первый месяц с данными = месяц начала использования сервиса (до него — `downloaded=0, skipped=0`)

**Пример (декабрь 2025 → январь 2025):**
```bash
cd .../MoveFromFF && .venv/Scripts/python.exe -m movefromff --mode manual \
  --from-date 2025-12-01 --to-date 2025-12-31 --verbose 2>&1 && sleep 10 && \
  .venv/Scripts/python.exe -m movefromff --mode manual \
  --from-date 2025-11-01 --to-date 2025-11-30 --verbose 2>&1 && sleep 10 && ...
```
Timeout для всей цепочки: 600 секунд (10 минут на 12 месяцев).

## Zulip как первичный источник контактов (25 мая 2026)

contacts.enc первично заполнен из Zulip (не Exchange). 1167 активных людей загружены 25.05.2026.

**Поля из Zulip:** email, login, fio (full_name), display_name, zulip user_id в messenger_ids.zulip.
**Чего нет в Zulip:** department, position, team — эти поля будут обогащены из Exchange GAL позже.

Exchange GAL нужен для: обогащения contacts.enc полями department/position, будущих инструментов создания встреч и анализа почты.

**Скрипт повторной заливки Zulip → contacts.enc:** `MoveFromExchange/reimport_zulip.py`

## merger.py — исправленный баг (25 мая 2026)

При создании НОВОГО контакта (не существующего в базе) поля `aliases`, `messenger_ids`, `notes`, `custom_updated_at` теперь берутся из входного контакта, а не жёстко пустые `{}` / `[]`. Это критично для Zulip-импорта где messenger_ids.zulip содержит реальный ID.

```python
# ДО (баг):
"messenger_ids": {},
# ПОСЛЕ (исправлено):
"messenger_ids": contact.get("messenger_ids", {}),
```



Для данных требующих шифрования (контакты, персональные данные):
- Один файл `<name>.enc` (AES-256-GCM)
- Ключ 32 байта, base64-encoded, в `.env` как `<NAME>_ENCRYPTION_KEY`
- Nonce генерируется каждый раз при записи, хранится в начале файла
- При отсутствии ключа → сгенерировать и вывести инструкцию
- Экспорт для просмотра: `--export` → `.xlsx` через openpyxl, отправить в TG, удалить

## Реорганизация файловой структуры (согласовано май 2026)

**Принцип:** WorkVault = данные, CursorProjects = исходники, hermes-agent/USERTOOLS = все пользовательские инструменты.

### Целевая структура

```
WorkVault/
├── Contacts/
│   ├── contacts.enc              ← единый для всех инструментов (Zulip + Exchange merge)
│   ├── _registry_cont.json
│   └── _registry_cont.md
├── Meetings/
│   └── NewMeetings/
│       ├── _registry_meet.json   ← было: _registry.json
│       ├── _registry_meet.md     ← было: _registry.md
│       └── _log_meet.md          ← было: _log.md
├── Projects/
│   ├── _registry_proj.json
│   └── _registry_proj.md
├── Tasks/
│   ├── _registry_task.json
│   └── _registry_task.md
└── _meta/
    ├── MoveFromFF/               ← логи и jsonl
    ├── MoveFromExchange/
    └── MoveFromConfluence/

hermes-agent/USERTOOLS/
├── MoveFromFF/                   ← исходники (из CursorProjects/MoveFromFF)
├── MoveFromExchange/
├── MoveFromConfluence/
└── MarkObjectsFromSummary/
```

### Соглашение по именованию реестров

Реестры **всегда** имеют суффикс сущности — не просто `_registry.json`:

| Сущность | Суффикс | Файлы |
|---|---|---|
| Meetings | `_meet` | `_registry_meet.json`, `_registry_meet.md`, `_log_meet.md` |
| Contacts | `_cont` | `_registry_cont.json`, `_registry_cont.md` |
| Projects | `_proj` | `_registry_proj.json`, `_registry_proj.md` |
| Tasks | `_task` | `_registry_task.json`, `_registry_task.md` |
| (новые) | `_[3-4 буквы]` | аналогично |

### contacts.enc — единый файл

- Один `WorkVault/Contacts/contacts.enc` для всех инструментов
- Источник истины: 1167 записей из Zulip (май 2026)
- contacts.enc в MoveFromExchange — только 2 тестовые записи → **удалить**
- При обогащении из Exchange GAL — merge в единый файл

### Чеклист миграции (стадии)

**Стадии запускаются последовательно через Opus-cronjob. К следующей стадии переходить только если все тесты стадии GREEN.**

- **Стадия 0** — Подготовка: создать папки, git commit, резервные копии contacts.enc
- **Стадия 1** — MoveFromFF (пилот): данные → WorkVault/Contacts/ и _meta/MoveFromFF/, исходники → USERTOOLS/MoveFromFF/, обновить .env + config.py, переименовать _registry.json → _registry_meet.json, обновить крон 1e62e18ae399
- **Стадия 2** — MoveFromExchange: удалить тестовый contacts.enc, логи → _meta/MoveFromExchange/, исходники → USERTOOLS/MoveFromExchange/, обновить крон 58ab10e1ee15
- **Стадия 3** — MoveFromConfluence: исходники → USERTOOLS/MoveFromConfluence/, логи → _meta/MoveFromConfluence/
- **Стадия 4** — MarkObjectsFromSummary: исходники → USERTOOLS/ (ТЗ ещё нет, только папка)
- **Стадия 5** — Финальная проверка: CursorProjects/ без данных, все кроны работают, Hermes memory обновлена

## Тестирование с нуля (clean-install verification)

Для подтверждения успешной миграции или после крупных изменений структуры — запускать тесты в свежем venv.

**Паттерн:**
```bash
python -m venv /tmp/test_venv_fresh
source /tmp/test_venv_fresh/Scripts/activate  # Windows (Git Bash)

# Установить все инструменты + pytest-плагины
pip install -q -e USERTOOLS/MoveFromFF -e USERTOOLS/MoveFromExchange -e USERTOOLS/MoveFromConfluence
pip install -q pytest pytest-mock pytest-xdist pytest-timeout

# Запускать КАЖДЫЙ инструмент из его собственной директории
cd USERTOOLS/MoveFromFF && python -m pytest tests/ -v --tb=short \
  --override-ini="addopts=" --timeout-method=thread

cd ../MoveFromExchange && python -m pytest tests/ -v --tb=short \
  --override-ini="addopts=" --timeout-method=thread

cd ../MoveFromConfluence && python -m pytest tests/ -v --tb=short \
  --override-ini="addopts=" --timeout-method=thread

rm -rf /tmp/test_venv_fresh
```

**⚠️ Критические питфоллы:**
- **Нельзя запускать все тесты из корня hermes-agent** — корневой `pyproject.toml` содержит `addopts = -n --timeout-method=signal`, что ломает pytest на Windows (нет `signal.SIGALRM`) и конфликтует с дочерними пакетами
- **`--override-ini="addopts="`** — обязателен для сброса корневых `addopts` при запуске из директории инструмента (иначе pytest тянет корневой конфиг по иерархии)
- **`--timeout-method=thread`** — заменяет `signal` для Windows-совместимости
- **`.venv/` в каждом инструменте — НЕ удалять** — это рабочие окружения для кронов
- **`*.egg-info/` — НЕ удалять** — нужны для `pip install -e` (editable install)

**Что проверяет clean-install тест:**
- ✅ Зависимости правильно задекларированы в `pyproject.toml`
- ✅ Пути и конфиги работают на реальной файловой структуре
- ✅ Нет "призраков" старого окружения
- ❌ Не проверяет: реальные API-запросы (мокируются), работу кронов в production

**Мусор после прогона тестов (можно чистить):**
```bash
# __pycache__ и .pytest_cache — только из исходников, не из .venv
find USERTOOLS -maxdepth 3 -type d -name "__pycache__" ! -path "*/.venv/*" -exec rm -rf {} + 2>/dev/null
find USERTOOLS -maxdepth 2 -type d -name ".pytest_cache" ! -path "*/.venv/*" -exec rm -rf {} + 2>/dev/null
```

## QA-верификация проектов против ТЗ

**Когда ТЗ обновляется (особенно mid-version addenda типа 2026-05-25):**
Используйте `references/qa-verification-checklist.md` для систематической проверки всех MoveFrom* проектов на соответствие новым требованиям. Чек-лист включает:
- Фазы поиска ТЗ и чтения актуального текста
- Проверку spec-vs-code дрифта (версии, флаги API, переменные)
- Common pitfalls (exchangelib версия, custom fields merge, is_internal, TG alerts в cron)
- Шаблон audit-отчёта

**exchangelib-специфичный питфолл (2026-05-25):** Explicit version Build (e.g. `Version(build=Build(15,2,1544,14))`) может противоречить ТЗ, которое требует auto-discovery. Старый workaround для 401-ошибок, но обновлённое ТЗ предпочитает дать exchangelib определить версию автоматически. При ТЗ-конфликте: remove build spec, add comment с датой решения.

**Кастомные поля (не из API-источника) не перезаписываются при синке** — это iron rule.
Пример в MoveFromExchange: `aliases`, `messenger_ids`, `notes`, `custom_updated_at` — только ручное редактирование через TG-команды `/contact edit`.

- **Не писать ad-hoc скрипты к API** — только через инструмент MoveFrom*. Если сценарий не поддерживается — сначала доработать инструмент.
- **Exchange/VPN — решено (25.05.2026):** В офисе (домен ТУТУ) EWS работает через Windows Kerberos без пароля. Пароль в .env НЕ нужен (`TUTU_PASSWORD=***` — плейсхолдер). `access_type=DELEGATE` обязателен. Версию exchangelib НЕ указывать явно — мешает Kerberos negotiate. Дома без VPN — не работает. `Configuration(timeout=...)` → TypeError в новых версиях exchangelib — убрать.
- **fetch_gal() тихо возвращает 0** — причина: голый `except Exception: pass` глотает UnauthorizedError на каждом паттерне wildcards. Всегда логировать исключения в клиентах API, иначе silent failure невозможно отладить.
- **Субагент на Haiku портит .env и contacts.enc** — при делегировании задач диагностики Exchange субагент подставлял тестовые credentials и удалял contacts.enc. Явно запрещать эти действия в промпте: "не удалять contacts.enc и .env".
- **Confluence Keycloak SSO:** В браузере — SSO/Kerberos в домене, 2FA дома. Однако **PAT-токен через REST API (`/rest/api/space`) работает из дома без VPN** (проверено 28.05.2026: HTTP 200). API-разработку ConfluenceSync можно вести и дома. Разрабатывать только в домене — устаревшее правило.
- **EXCHANGE_PASSWORD в MoveFromExchange/.env был `***`** — плейсхолдер, не реальный пароль. Реальная аутентификация через Kerberos (доменная сессия Windows). Не пытаться «восстановить» пароль — это не нужно.
- **Проверяй что субагент не написал заглушку** — после делегирования разработки API-клиента явно проверяй что метод `fetch_*` не возвращает `[]` из mock-ветки. Паттерн: `grep -n "return \[\]" client.py` или читать тело метода перед первым боевым тестом.
- **XLSX-экспорт убран из MoveFromExchange (v1.1):** никаких выгрузок персданных в открытый файл. contacts.enc остаётся (AES-256-GCM). Восстановление при потере — пересинхронизация из Exchange (кастомные поля теряются, это приемлемо).
- **Переговорки не синхронизируем:** fetch_rooms() убрать из scope MoveFromExchange.
- **List-запрос не должен тянуть тяжёлые поля** — иначе cost-limit API молча возвращает пустой массив без ошибки. Паттерн: лёгкий list → fetch полных данных только для новых записей (N+1 по числу реально новых).
- **Корпоративные токены** — хранить только как Personal Access Token, не доменный пароль. PAT можно отозвать не меняя пароль.
- **Реальный путь USERTOOLS (КРИТИЧНО для cronjob-ов):** `C:\\Users\\tkachenkoav\\Documents\\Cursor_projects\\hermes-agent\\USERTOOLS\\` — НЕ `WorkVault\\USERTOOLS\\`. При создании cronjob-ов всегда использовать полный путь. WorkVault — только для данных (`contacts.enc`, `Meetings/`, `_meta/` и т.д.).
- **ConfluenceSync — чтение страниц в контекст агента (`--to-context`):** при получении ссылки на Confluence от пользователя — вызвать `confluencesync pull <url> --to-context --no-recursive`, вывод передаётся прямо в контекст. Пользователь может спросить «о чём здесь речь?» — читать через инструмент, не через браузер. Если ConfluenceSync даёт ошибку конвертера — использовать прямой REST API через `execute_code` (urllib + json + regex для strip HTML тегов).
- **execute_code vs terminal для Python на Windows:** `python3` и `python3.11` в терминале могут не работать (uv trampoline, MS Store alias). Для быстрых Python-скриптов предпочитать `execute_code` — он использует правильный интерпретатор напрямую.
- **Postobработка — не зона MoveFrom*** — только перенос файлов как есть. Всё остальное делают следующие инструменты конвейера.

## References

- `references/loop-mattermost-api.md` — Loop API справочник: Loop = Mattermost API v4, эндпоинты пользователей, аутентификация через PAT, маппинг полей для MoveFromLoop.
- `references/confluence-obsidian-storage-design.md` — архитектура хранения Confluence страниц в Obsidian: структура папок (гибрид), frontmatter, кросс-ссылки, что переиспользовать из текущего кода, питфоллы именования файлов.
- `references/movefrom-confluence.md` — MoveFromConfluence полное ТЗ: двусторонняя синхронизация задач Confluence ↔ WorkVault, публикация summary встреч, CLI, TG-команды, парсинг action items / @mention / таблиц.
- `references/movefrom-exchange-contacts.md` — MoveFromExchange полное ТЗ + contact-resolution: синхронизация Exchange GAL → contacts.enc (AES-256-GCM), Zulip bootstrap, filters.py (4 правила фильтрации), маскировка персданных, exchangelib Kerberos-конфиг; резолвинг свободных упоминаний людей (alias/nickname/login) по contacts.enc через AnywhereContacts API, PII-маскировка при выводе, три состояния резолвера (resolved/ambiguous/unknown).
- `references/exchange-version-configuration.md` — детали exchangelib Configuration: version, auth_type, access_type, почему нельзя указывать Build явно в домене ТУТУ.
- `references/qa-verification-checklist.md` — чек-лист QA-верификации проектов против ТЗ (spec-vs-code drift).
- `references/confluencesync-brief-v1.md` — ConfluenceSync бриф v1 (28.05.2026): архитектура, use cases, режимы вывода, логирование, тесты.
- `references/tutu-corporate-integrations.md` — credentials и auth-паттерны для всех корпоративных сервисов ТУТУ: Confluence (Keycloak SSO, PAT устарел), Jira, Exchange EWS (Kerberos/Basic, exchangelib шаблон), Zulip (HTTP Basic + verify=False), GitHub PAT. Правило минимизации авторизаций.
