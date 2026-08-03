# Архитектура карточек сущностей AggregateFromMeetings

**Дата:** 2026-06-19  
**Модули:** E.Люди, H.Синки  
**Статус:** закрыто в брифе

---

## Общий паттерн карточек (People/ и Syncs/)

Одинаковое для всех сущностей:
- YAML frontmatter — машиночитаемые метаданные
- PM Notes блоки `<!-- pm: --><!-- /pm -->` после каждой секции
- Нет сквозного PM Notes блока (аналог Projects/card.md)
- Навигационная строка внизу — статическая
- dataviewjs для динамических секций (аналог Projects/card.md)

---

## People/{login}/card.md — YAML

```yaml
entity: person
login: kirill_ivanov
fio: "Иванов Кирилл"
display_name: "Кирилл"
department: "Продукт"
team: "AID"
position: "Tech Lead"
projects: ["antibot", "okr-tool"]
syncs: ["aid-sync"]
last_meeting: 2026-06-12
meetings_count: 14
last_processed_at: 2026-06-19
```

**Убрано:** `relation` (контекст → context.md текстом), `contact` (избыточен — login = ключ)

## People/ — секции card.md

| Секция | Тип | Решение |
|---|---|---|
| 🧭 Контекст | ❌ | Исключена |
| ☑️ Открытые commitments | dataviewjs | Аналог Projects/card.md |
| 🔗 Связанные проекты | dataviewjs | `WHERE contains(people, login)` |
| 🗂 Связанные синки | dataviewjs | `WHERE contains(core_members, login)` |
| Навигация | статическая | `☑️ commitments · 🤝 agreements · 📅 meetings` |

## People/ — подкарточки

| Файл | Назначение | #N |
|---|---|---|
| `card.md` | Точка входа | — |
| `commitments.md` | Двусторонние задачи (Мои / Имя) | сквозная по контакту |
| `agreements.md` | Долгосрочные договорённости | — |
| `meetings/{дата}.md` | Протокол 1on1 | — |
| `meetings.md` | Авто-индекс | — |
| `snapshots/` | Генерируется G.Срез | — |

---

## Syncs/{slug}/card.md — YAML

```yaml
entity: sync
slug: aid-sync
title: "Синк АиД"
core_members: ["kirill_ivanov", "olga_p"]
projects: ["antibot", "okr-tool"]
last_meeting: 2026-06-17
meetings_count: 23
last_processed_at: 2026-06-19
```

**Убрано:** `cadence` (полностью, не Фаза 2), `relation` (не нужен), `projects_touched` → переименован в `projects`

## Syncs/ — секции card.md

| Секция | Тип | Решение |
|---|---|---|
| 🎯 Назначение площадки | ❌ | Исключена |
| 📋 Повестка | ❌ | Исключена (и `agenda.md` убран) |
| ☑️ Открытые action items | dataviewjs | Аналог People/ |
| 🔗 Затронутые проекты | dataviewjs | Аналог People/ |
| 👥 Участники | dataviewjs | S2∪S3 из meetings/ + AC |
| Навигация | статическая | `☑️ action_items · 🤝 decisions · 🔗 projects_touched · 📅 meetings` |

## Syncs/ — подкарточки

| Файл | Назначение | #N |
|---|---|---|
| `card.md` | Точка входа | — |
| `decisions.md` | Решения уровня синка, append-only | — |
| `action_items.md` | Только организационные задачи синка | сквозная по синку |
| `meetings/{дата}.md` | Протокол встречи синка | — |
| `meetings.md` | Авто-индекс | — |
| `projects_touched.md` | Индекс проектов (двусторонний линк) | — |
| `snapshots/` | Генерируется G.Срез | — |

---

## Участники Syncs/ — источники данных

Поле `**Участники:**` в FF ненадёжно (~50% встреч теряют список, особенно серийные и forwarded).

| Источник | Надёжность | Сложность |
|---|---|---|
| S1: `**Участники:**` в transcript | 🟡 50–70% | 🟢 1 regex |
| S2: Speaker labels `[mm:ss] **ФИО:**` | 🟢 95% | 🟢 regex |
| S3: Заголовки action items `**ФИО**` | 🟢 90% | 🟢 парс |
| S5: tutu-contacts.md (нормализация) | 🟢 source of truth | 🟢 lookup |
| Exchange/Calendar | 🟢 100% | 🔴 EWS-коннектор → Фаза 2 |

**MVP:** S2∪S3 нормализованные через AC (E.Люди). Exchange → Фаза 2.
