# Карта инструментов автоматизации — Vision

> **Автор:** Hermes (Opus), для Александра Ткаченко (ТУТУ).
> **Главный принцип:** Собирать контекст из разнообразных источников → структурировать по сущностям → вести проекты по формализованным правилам (PMBOK). Каждый инструмент имеет самостоятельную ценность, но вместе они строят единую систему.
> **Финальная цель:** Раннее выявление рисков проектов на основе **реальных данных**, а не придуманных в Excel — сигналы из живого потока (просрочки в Jira, напряжённость в Zulip, изменения повестки во встречах, паттерны в почте) + автоматические предложения мер.

---

## 0. Архитектурные принципы (унаследовано из personal-ai-assistant и FF-Obsidian)

1. **WorkVault как source-of-truth для человека** — Markdown-файлы в Obsidian-совместимой структуре (`projects/`, `meetings/`, `contacts/`, `themes/`).
2. **SQLite как source-of-truth для машины** — состояние ингестации, чек-суммы, связи сущностей, история сигналов. ACID, JOIN-ы, дешевизна.
3. **Гибрид MD + SQLite** — MD генерируется/обновляется из SQLite; пользовательские правки в MD синхронизируются обратно (feedback loop).
4. **Каждая интеграция (Move*) — это «глаз» в один источник.** Никакой бизнес-логики, только нормализованная выгрузка.
5. **Структурирование (Mark*, Link*)** — отдельные инструменты поверх сырья. Они и есть «мозг».
6. **Router-паттерн для LLM** (из FF-Obsidian ARCH): 80% обработки локально (NER/regex/эмбеддинги), и только 20% — внешняя сильная LLM. Контроль затрат.
7. **Алиасы сущностей** — обязательно. «Саша», «Александр», «AT» — один контакт. Решается через таблицу `entity_aliases` + fuzzy/семантический матчинг.
8. **Защита от prompt injection** — внешний контент (письма, транскрипты) только данные, не команды.

---

## 1. Доменная модель сущностей (единый словарь)

| Сущность | Файл/таблица | Ключевые поля | Источники-доноры |
|----------|--------------|---------------|-------------------|
| **Contact** | `contacts/*.md` + `contacts` | ФИО, email, tg, отдел, алиасы, роли в проектах | FF (участники), Exchange (from/to), Zulip (mentions), CorpInfo |
| **Project** | `projects/*.md` + `projects` | SMART-цель, срок, бюджет, статус, owner, jira-ключ | MarkObjectsFromSummary, Jira, ручной онбординг |
| **Theme** | `themes/*.md` + `themes` | Описание, RUN/инициатива, owner | MarkObjectsFromSummary |
| **Meeting** | `meetings/*.md` + `meetings` | ID FF, дата, участники, summary, project_ref | MoveFromFF |
| **Task** | `tasks.md` + `tasks` | Описание, owner, DL, статус, источник (jira/FF/manual), project_ref | Jira, FF, ручное |
| **Decision** | `decisions/*.md` + `decisions` | Что, кем, когда, в какой встрече/треде | MarkObjectsFromSummary, Zulip |
| **Agreement** (договорённость) | в `meetings/`/`tasks` | Кто кому что обещал, срок | FF, Exchange, Zulip |
| **Signal** (риск-сигнал) | `risks/signals.md` + `signals` | Тип, источник, severity, project_ref, дата, raw_link | Все инструменты Watch* |
| **Risk** | `risks/*.md` + `risks` | Описание, триггеры, mitigation, owner, status | RiskRegistry |

---

## 2. Карта инструментов (слои)

### Слой A — Ingest (выгрузка из источников → WorkVault, нормализация)
Каждый инструмент: stateful (SQLite checksum), идемпотентный, cron-friendly.

| # | Название | Источник → Выход | Создаёт сущности | Сложность |
|---|----------|-------------------|-------------------|-----------|
| A1 | **MoveFromFF** ✅ DONE | Fireflies → `meetings/raw` + `meetings/summaries` | Meeting (сырое) | — |
| A2 | **MoveFromJira** | Jira → `jira/issues/*.md` | Task, Project (по ключу) | M |
| A3 | **MoveFromConfluence** | Confluence → `confluence/*.md` | Project (контекст), Decision | M |
| A4 | **MoveFromExchange** | EWS почта+календарь → `mail/inbox/`, `calendar/*.md` | Meeting (план), Contact, Agreement | L |
| A5 | **MoveFromZulip** | Zulip → `zulip/streams/*.md` | Agreement, Decision (mentions/quotes) | M |

### Слой B — Structure (выделение и связывание сущностей)
Работают поверх артефактов слоя A. Сильно завязаны на LLM/NER + fuzzy-match.

| # | Название | Вход → Выход | Создаёт/обогащает | Сложность |
|---|----------|----------------|-------------------|-----------|
| B1 | **MarkObjectsFromSummary** 🎯 NEXT | `meetings/summaries/*.md` → `contacts.md`, `projects.md`, `themes.md`, `tasks.md` | Contact, Project, Theme, Task | M |
| B2 | **LinkEntities** (alias resolver) | Все MD + SQLite → таблица алиасов, обновлённые ссылки `[[Project_X]]` | связи между сущностями | M |
| B3 | **ContactsEnricher** | `contacts.md` + CorpInfo API + Exchange GAL → обогащённые карточки | Contact (email, tg, отдел) | S |
| B4 | **TaskUnifier** | Jira issues + Action Items из FF + email-обещания → единый `tasks` со ссылками на источники | Task (deduped) | M |
| B5 | **ProjectBriefBuilder** | Все сущности проекта → `projects/X.md` (живая страница: статус, последние решения, задачи, риски) | Project (агрегат) | M |

### Слой C — Watch (мониторинг сигналов; основа риск-реестра)
Запускаются по cron, пишут в таблицу `signals`. Это **мост к финальной цели**.

| # | Название | Что ловит | Сигнал → проект | Сложность |
|---|----------|------------|-----------------|-----------|
| C1 | **WatchJiraOverdue** | Просроченные/застрявшие задачи, рост WIP, переоткрытия | severity по проекту | S |
| C2 | **WatchMeetingDrift** | Сдвиг повестки FF: одна и та же тема всплывает N раз без решения; рост частоты статусных встреч | возможные срывы сроков | M |
| C3 | **WatchZulipTension** | Тон коммуникаций (sentiment), пинги без ответа > X часов, конфликтные паттерны, эскалации к руководителям | напряжённость в команде | L |
| C4 | **WatchMailPatterns** | Письма «когда будет?», эскалации, CC++ руководства, повторные напоминания | давление от стейкхолдеров | M |
| C5 | **WatchCalendarChurn** | Постоянные переносы/отмены ключевых встреч, отсутствие owner-а | признак рассинхрона | S |

### Слой D — Decide (PMBOK-движок поверх сигналов)

| # | Название | Что делает | Сложность |
|---|----------|--------------|-----------|
| D1 | **RiskRegistry** | Реестр рисков по PMBOK: probability × impact, триггеры, response plan, owner | M |
| D2 | **RiskCorrelator** | Агрегирует сигналы C1–C5 по проекту → предлагает риски и mitigation на базе шаблонов PMBOK + истории закрытых рисков | L |
| D3 | **MorningBriefing** | Утренний дайджест: что произошло за ночь по каждому проекту, новые сигналы, риски, на что обратить внимание | S |
| D4 | **WeeklyReview** | Еженедельный обзор проектов (статус, движение, риски) в формате PM-отчёта; публикация в Confluence/Telegram | M |

---

## 3. Порядок разработки (roadmap)

```
Фаза 1: Сырьё (Ingest)            Фаза 2: Структура              Фаза 3: Мониторинг          Фаза 4: Решения
─────────────────────────        ──────────────────────         ─────────────────────       ─────────────────
[✅ MoveFromFF]──┐                                              
                 ├─► [🎯 B1 MarkObjectsFromSummary]──┐          
[MoveFromJira]───┤                                   │          
[MoveFromConfl.]─┤                                   │          
[MoveFromExch.]──┤   [B3 ContactsEnricher]──────────►├─► [B2 LinkEntities]──┐
[MoveFromZulip]──┘   [B4 TaskUnifier]────────────────┤                       │
                                                     │                       ▼
                                                     └─► [B5 ProjectBriefBuilder]
                                                                     │
                                                                     ▼
                                       [C1 WatchJiraOverdue]──┐
                                       [C2 WatchMeetingDrift] │
                                       [C3 WatchZulipTension] ├─► [D1 RiskRegistry]──► [D2 RiskCorrelator]
                                       [C4 WatchMailPatterns] │              │              │
                                       [C5 WatchCalendarChurn]┘              ▼              ▼
                                                                     [D3 MorningBriefing] [D4 WeeklyReview]
```

**Рекомендуемый порядок (1 = сейчас):**

1. **B1 MarkObjectsFromSummary** — на готовых summary FF; даёт первые `projects.md`, `contacts.md`, `tasks.md`. **Без этого все остальные слои висят.**
2. **A2 MoveFromJira** — второй критический источник (задачи и проектные ключи).
3. **B2 LinkEntities** + **B3 ContactsEnricher** — приводим в порядок «один человек = одна карточка», ссылки `[[Project]]`.
4. **B4 TaskUnifier** — сводим Jira-таски и FF action items в единый список без дублей.
5. **A4 MoveFromExchange** — почта + календарь. Большой источник договорённостей.
6. **B5 ProjectBriefBuilder** — рождает «живые» страницы проектов. Здесь система впервые видна целиком.
7. **A3 MoveFromConfluence** + **A5 MoveFromZulip** — закрываем оставшиеся источники.
8. **C1 WatchJiraOverdue** — самый простой и сразу полезный watcher. Доказательство концепта сигналов.
9. **C2, C4, C5** — следующие watchers (по сложности).
10. **D1 RiskRegistry** + **D3 MorningBriefing** — PMBOK-каркас и ежедневная польза.
11. **C3 WatchZulipTension** + **D2 RiskCorrelator** — самые «умные» компоненты; делаем последними, когда есть достаточно данных.
12. **D4 WeeklyReview** — финал, замыкающий цикл управления.

---

## 4. Общие технические решения

- **Стек:** Python 3.11+, SQLAlchemy + SQLite, httpx, loguru, pydantic-settings, typer/click для CLI, schedule/cron для запуска.
- **Хранилище состояния:** единая БД `WorkVault/.hermes/state.db` для всех инструментов (общие таблицы entities, aliases, signals).
- **LLM Router:** общая обёртка `hermes.llm` с дешёвыми (локальные эмбеддинги, spaCy, regex) и дорогими (Claude/GPT) путями. Кэш промптов.
- **CLI единый:** `hermes <tool> <action>` — единая точка входа, как уже сделано в Hermes-agent.
- **Логи и трассировка:** каждое действие пишется с ссылкой на источник (FF meeting_id, Jira key, email message-id) — это критично для риск-аналитики «откуда сигнал».
- **Feedback loop:** правки пользователя в MD-файлах (например, переименование контакта) отслеживаются и синхронизируются обратно в SQLite — как в FF-Obsidian ADR 6.
- **Idempotency:** все Move* и Mark* — повторный запуск безопасен; обновляем только то, что изменилось (checksum).

---

## 5. Связь с финальной целью — почему так

Каждый инструмент **уже** вкладывается в риск-аналитику:

| Инструмент | Сигнал для риск-реестра |
|------------|--------------------------|
| MoveFromFF + B1 | Темы, всплывающие много встреч подряд без решения |
| MoveFromJira | Метрики потока: lead time, WIP, переоткрытия |
| MoveFromExchange | Эскалации, тон писем, нарушение SLA ответов |
| MoveFromZulip | Sentiment, пинги без ответа, концентрация негатива |
| Calendar | Перенос ключевых встреч (lead-индикатор срыва сроков) |

То есть **сбор уже = аналитика**. Когда инструменты слоёв A+B+C готовы — слой D (PMBOK) собирается из готовых сигналов сравнительно дёшево.

---

## 6. Принципы выбора «делать / не делать»

- ✅ **Делать**, если: инструмент даёт ценность отдельно + создаёт хотя бы одну сущность из доменной модели + есть путь к сигналу в риск-реестр.
- ❌ **Не делать**, если: чисто косметика, дублирует MCP/готовый плагин Obsidian, или не оставляет следа в `state.db`.
- 📐 **Минимальный размер инструмента**: один источник → одна сущность → одна таблица. Если получается «комбайн» — резать на два.

---

*Версия 1.0 — 2026-05-22*
