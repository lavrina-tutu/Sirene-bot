---
tool: AggregateFromMeetings
type: pm-hub
created: 2026-06-25
updated: 2026-06-25
status: active
---

# PM-контекст AggregateFromMeetings

> **Зачем эта папка:** единая точка для решений PM **до ТЗ**, открытых вопросов и handoff между LLM.
> ТЗ и код меняются **только** после `accepted` + команды PM **«начинай обработку»**.

---

## Два агента — одна цепочка

```
┌─────────────────┐     pm/ (решения, OQ)      ┌──────────────────────┐
│  LLM для брифа  │ ─────────────────────────► │  LLM реализации      │
│  (Obsidian/     │     sessions/, golden      │  (Cursor + VM,       │
│   ChatGPT/…)    │                            │   hermes-vm)         │
└─────────────────┘                            └──────────────────────┘
        ▲                                                  │
        │  PM (Саша)                                       ▼
        └──────── ревью, ответы ──────────────►  TZ + код + BUILD_CHECKLIST
```

| Роль | Где работает | Что делает | Что **не** делает |
|------|--------------|------------|-------------------|
| **PM (вы)** | Obsidian | Ревью, ответы, «принято», «начинай» | — |
| **LLM брифа** | любая LLM | Читает контекст, помогает решить OQ, пишет в `pm/` | Не правит ТЗ, не трогает код на VM |
| **LLM реализации** | Cursor + `hermes-vm` | ТЗ → код → тесты → BUILD_CHECKLIST | Не начинает без «начинай обработку» |

**Готовый промпт для другой LLM:** [[pm/BRIEFING_PROMPT]]

---

## Карта файлов (WorkVault)

| Путь | Назначение |
|------|------------|
| **`pm/README.md`** | этот файл — навигация и правила |
| **`pm/BRIEFING_PROMPT.md`** | скопировать в другую LLM целиком |
| **`pm/PM_DECISIONS_LOG.md`** | журнал решений PD-xxx |
| **`pm/OPEN_QUESTIONS.md`** | реестр вопросов OQ-xxx |
| **`pm/GOLDEN_REFS.md`** | эталоны Confluence для автопроверки |
| **`pm/IMPLEMENTATION_QUEUE.md`** | очередь шагов для агента реализации |
| **`pm/sessions/`** | протоколы сессий ревью/брифа |
| **`pm/sessions/_TEMPLATE.md`** | шаблон новой сессии |
| **`_review/`** | sandbox-вывод для ревью (не боевой Vault) |
| **`CURSOR_CONTEXT.md`** | снимок состояния для Cursor на VM |
| **`TZ_aggregate_main.md`** | главное ТЗ v1.4 |
| **`BUILD_CHECKLIST.md`** | гейты H0–H8, фазы 0–9 |
| **`~/USERTOOLS/AggregateFromMeetings/`** | код на VM |

---

## Для PM: быстрый старт

1. Открыть **`pm/OPEN_QUESTIONS.md`** — ответить на открытые OQ
2. Продолжить ревью **`_review/Projects/`** и **`_review/signals/`**
3. Новые мысли → **`PM_DECISIONS_LOG.md`** или новая **`sessions/YYYY-MM-DD_*.md`**
4. Для брифа с другой LLM → скопировать **`pm/BRIEFING_PROMPT.md`**
5. Когда готовы к коду → **`IMPLEMENTATION_QUEUE.md`** + команда **«начинай обработку»** в Cursor

---

## Для LLM брифа: что читать (порядок)

1. [[pm/BRIEFING_PROMPT]] — ваш системный промпт
2. [[pm/sessions/2026-06-25_gate-h6-review]] — текущая сессия
3. [[pm/PM_DECISIONS_LOG]] — уже принятые решения (не пересматривать без PM)
4. [[pm/OPEN_QUESTIONS]] — что нужно закрыть
5. [[pm/GOLDEN_REFS]] — эталоны Confluence
6. [[_review/_REVIEW_GUIDE]] + [[_review/Projects/]] — что ревьюили
7. [[TZ_aggregate_main]] — только для понимания gap, **не редактировать**

---

## Для LLM брифа: куда писать

### Новое решение PM

Файл: **`pm/PM_DECISIONS_LOG.md`**, секция текущей даты, **сверху**.

```markdown
| **PD-026** | _формулировка одним предложением_ | _источник: сессия / OQ / ревью_ | `draft` | — |
```

После подтверждения PM → статус **`accepted`**.

### Ответ на вопрос

Файл: **`pm/OPEN_QUESTIONS.md`**, строка OQ-xxx:

1. Заполнить колонку **Answer**
2. Перенести строку в секцию «Отвеченные» или пометить статус
3. Обновить счётчик в «Сводка»

### Новая сессия

Скопировать **`pm/sessions/_TEMPLATE.md`** → `pm/sessions/YYYY-MM-DD_<topic>.md`

### Golden ref

Файл: **`pm/GOLDEN_REFS.md`** — добавить строку slug + Confluence pageId + URL

### Задача для реализации

Файл: **`pm/IMPLEMENTATION_QUEUE.md`** — только после PM сказал «готовим к реализации»:

```markdown
- [ ] **IQ-001** | _шаг_ | blocked_by: — | PD-024, OQ-007 | агент реализации
```

---

## Для LLM реализации (Cursor + hermes-vm): handoff

### Триггер старта

PM пишет в Cursor: **«начинай обработку»** (или поэтапно — см. OQ-014).

### Что прочитать перед работой

1. **`pm/PM_DECISIONS_LOG.md`** — все строки со статусом `accepted`
2. **`pm/OPEN_QUESTIONS.md`** — все `answered` (ещё не `in_tz`)
3. **`pm/IMPLEMENTATION_QUEUE.md`** — очередь шагов
4. **`pm/sessions/`** — последняя сессия
5. **`BUILD_CHECKLIST.md`** — что уже `[x]`, что `[ ]`
6. **`~/USERTOOLS/AggregateFromMeetings/`** на VM — фактическое состояние кода
7. SSH: `ssh hermes-vm`, код: `~/USERTOOLS/AggregateFromMeetings/`

### Алгоритм реализации

```
accepted PD + answered OQ
    → обновить TZ (modules/, TZ_aggregate_main.md)
    → пометить PD/OQ как in_tz + TZ ref
    → изменить код на VM
    → pytest / mypy / ruff
    → обновить BUILD_CHECKLIST + IMPLEMENTATION_QUEUE
    → dev-log.md (USERTOOLS) — технические решения
```

### Контроль выполнения

| Артеfact | Где проверять |
|----------|---------------|
| Гейты H0–H8 | `BUILD_CHECKLIST.md` |
| Фазы 0–9 | `BUILD_CHECKLIST.md` + `IMPLEMENTATION_QUEUE.md` |
| Тесты | `pytest -q` на VM (сейчас 126 passed) |
| PM-решения в ТЗ | все `accepted` → `in_tz` |
| Боевой WorkVault | **не писать** до GATE H6 (OQ-012) |

### После каждого шага реализации

1. `[x]` в **`IMPLEMENTATION_QUEUE.md`**
2. `[x]` в **`BUILD_CHECKLIST.md`** (если применимо)
3. **`dev-log.md`** — что сделано технически
4. **`CHANGELOG.md`** — если менялся контракт инструмента

---

## Статусы (шпаргалка)

**Решения:** `draft` → `accepted` → `in_tz` | `superseded`

**Вопросы:** `open` → `answered` → `in_tz` | `wontfix`

**Очередь реализации:** `[ ]` → `[~] blocked` → `[x] done`

---

## Текущее состояние (на 2026-06-25)

| Область | Статус |
|---------|--------|
| Код модулей A–H | ✅ написан, 126 тестов |
| Sandbox Opus + D | ✅ есть в `_sandbox/`, качество не принято |
| PM-решения PD-016…025 | `accepted`, ждут ТЗ |
| Открытые OQ | 14 шт., см. OPEN_QUESTIONS |
| Реализация | ⏸ до «начинай обработку» |
| GATE H6 | ⏸ ревью в `_review/` |

---

## Связанные материалы

- [[briefs/brief_round2_results]] — бриф 22.06 (архив)
- [[unclear_registry]] — маршруты unclear
- [[CURSOR_CONTEXT]] — контекст для Cursor на VM
- [[Entities/_template/status_snapshot]] — шаблон среза
