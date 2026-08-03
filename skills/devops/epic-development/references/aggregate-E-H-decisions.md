# AggregateFromMeetings — решения модулей E.Люди и H.Синки (2026-06-19)

## Модуль E.Люди — ключевые решения

| Вопрос | Решение |
|---|---|
| В1 — Алгоритм 1on1 | Правило 16 (шаг 0 syncs_memory → шаги 1-7). Владелец — B.Роутер. |
| В2 — Формат commitments | Разделённые секции `### Мои обязательства` / `### Обязательства [Имя]`, #N сквозная по контакту |
| В3 — Granularity карточек | Только прямые участники встречи. 3-е лица из текста не создаём. |
| В4а — API алиасов в AC | `add_alias(login, alias, source="aggregate_from") -> bool` — атомарный append, Python-импорт |
| В4б — Подтверждение PM | Батч через F.Дирижёр (дайджест) + TG-команды ручного управления |
| В4в — Порядок резолва | Полный каскад: email → fio → alias → token_subset → fuzzy (threshold 0.85). При ошибке — PM правит через PM Notes |
| pm_locked | Не нужен (всё append-only). Вместо этого — PM Notes блоки в каждом файле |

### Карточка People/{login}/
**YAML frontmatter:**
```yaml
entity: person
login: kirill_ivanov          # ключ из AC, латиница
fio: "Иванов Кирилл"
display_name: "Кирилл"
department: "Продукт"
team: "AID"
position: "Tech Lead"
projects: ["antibot", "okr-tool"]   # унифицировано с Syncs
syncs: ["aid-sync"]
last_meeting: 2026-06-12
meetings_count: 14
last_processed_at: 2026-06-19
```

**Секции card.md:**
- ~~Контекст~~ — исключена
- ☑️ Открытые commitments — dataviewjs (аналог Projects/card.md)
- 🔗 Связанные проекты — dataviewjs `WHERE contains(people, login)`
- 🗂 Связанные синки — dataviewjs `WHERE contains(core_members, login)`
- Навигация: `☑️ commitments · 🤝 agreements · 📅 meetings`

**Подкарточки People/{login}/:**
| Файл | Назначение |
|---|---|
| `card.md` | Точка входа |
| `commitments.md` | Двусторонние задачи #N сквозная |
| `agreements.md` | Долгосрочные договорённости |
| `meetings/{дата}.md` | Протокол 1on1 |
| `meetings.md` | Авто-индекс |
| `snapshots/` | Генерируется G.Срез (не трогать) |

---

## Модуль H.Синки — ключевые решения

| Вопрос | Решение |
|---|---|
| В1 — Граница multisync vs project | По структуре. **Шаг 0 B.Роутера**: матч syncs_memory.json первичен. Без зарегистрированного синка — multisync не возникает. |
| В2 — Проброс в D.База | Вариант В: C единственный источник, F раздаёт по scope. H→D связки нет. Per-project сигналы с source_sync доставляет F. |
| В3 — action_items синка vs проекта | По владельцу: проектные → D.База, организационные синка → Syncs/action_items.md |
| В4 — Dormant | Не отслеживаем. `last_meeting` в card.md достаточно. |
| В5 — Bootstrap синков | PM создаёт вручную: `создай синк [название] slug [slug]` |
| cadence | Убрано полностью (не нужно даже в Фазе 2) |

### Карточка Syncs/{slug}/
**YAML frontmatter:**
```yaml
entity: sync
slug: aid-sync
title: "Синк АиД"
core_members: ["kirill_ivanov", "olga_p"]
projects: ["antibot", "okr-tool"]    # унифицировано с People
last_meeting: 2026-06-17
meetings_count: 23
last_processed_at: 2026-06-19
```

**Секции card.md:**
- ~~Назначение площадки~~ — исключена
- ~~Повестка~~ — исключена (и agenda.md убран)
- ☑️ Открытые action items — dataviewjs
- 🔗 Затронутые проекты — dataviewjs
- 👥 Участники — dataviewjs из meetings/ (S2∪S3 + AC). Exchange → Фаза 2.
- Навигация: `☑️ action_items · 🤝 decisions · 🔗 projects_touched · 📅 meetings`

**Подкарточки Syncs/{slug}/:**
| Файл | Назначение |
|---|---|
| `card.md` | Точка входа |
| `decisions.md` | Решения уровня синка, append-only |
| `action_items.md` | Организационные задачи #N сквозная |
| `meetings/{дата}.md` | Протокол синка |
| `meetings.md` | Авто-индекс |
| `projects_touched.md` | Индекс проектов |
| `snapshots/` | Генерируется G.Срез (не трогать) |

---

## Источники участников синка (исследование реальных FF-данных)

Поле `**Участники:**` в FF ненадёжно: ~50% встреч серии «Синк АиД» 2026 — только организатор.

| Источник | Надёжность | Сложность |
|---|---|---|
| S1: `**Участники:**` в transcript header | 🟡 50-70% | 🟢 regex |
| S2: Speaker labels `[mm:ss] **ФИО:**` | 🟢 95% | 🟢 regex |
| S3: Заголовки `**ФИО**` в `## Action items` | 🟢 ~90% | 🟢 парс |
| S5: AC нормализация (email↔ФИО↔alias) | 🟢 source of truth | 🟢 lookup |
| S7: Exchange/Calendar | 🟢 100% | 🔴 EWS нужен |

**MVP:** S2∪S3 + нормализация через AC (resolve_name()). Exchange → Фаза 2.

**Питфолл:** fred@fireflies.ai нужно жёстко фильтровать из всех источников.

---

## Принципы общие для People и Syncs

- **Ключ контакта везде — `login` (латиница)**, не кириллическое ФИО
- **PM Notes блоки** `<!-- pm: --><!-- /pm -->` — после каждой секции, в каждом файле
- **Нет сквозного PM Notes блока** в card.md (аналог Projects/card.md)
- **Нет pm_locked** — всё append-only, перезаписей нет
- **Поле `projects`** — унифицировано для обоих (People и Syncs используют одно имя)
- **dataviewjs везде** где данные динамически накапливаются (не static lists)
