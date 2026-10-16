---
name: deep-mine-project
description: "Use when: глубокий анализ проекта, собери архив проекта, обнови архив проекта, deep-mine refresh, устав-контекст, charter-context, architecture-context, граф проекта, проектная документация полного внедрения. Полуавтоматический сбор полного контекста проекта (Confluence + план + встречи + сущность) в двуслойный MD-архив WorkVault; граф без LLM; facts.json; два производных контекста (устав + архитектура) синтезом grok с API-JSON. Per-page composer-digest не канон для ответов."
version: 1.0.0
date: 2026-09-09
status: finalized
author: архитектор (cursor-grok-4.6-high, Cursor CLI)
platforms: [linux]
tags: [workvault, confluence, graph, facts, charter-context, architecture-context, cursor-cli, trisigma]
tool: deep-mine-project
last-section-added: 2026-09-09 — РЕДИЗАЙН v1.0.0 (3 слоя A/B/C, отказ от per-page digest как канона)
depends_on:
  - ConfluenceSync >= 1.0.1
  - MofsIndex >= 0.5.1
  - skill:workvault-rag
  - USERTOOLS/MppReader
  - skill:pmo-charter-fill
consumers:
  - skill:tz-workflow
  - skill:hermes-feature
  - skill:pmo-charter-fill
  - Cursor CLI (cursor-grok-4.6-high, API-JSON)
  - Hermes Q&A (deepseek)
---

# deep-mine-project — глубокое бурение проекта

## Цель

Собрать полный контекст проекта из канонических источников WorkVault в двуслойный MD-архив (L0 тела + L1 overlay), построить граф связей без LLM, извлечь проверяемые факты и один раз синтезировать два производных документа (`charter-context.md`, `architecture-context.md`), чтобы отвечать по полям устава и по non-charter темам, не сжимая каждую страницу композером.

## When to Use

Триггеры (любой из них запускает скилл `deep-mine-project`):

- «глубокий анализ проекта», «глубокое бурение», «пробури проект»
- «собери архив проекта», «обнови архив <Проект>», «deep-mine refresh», «ресник проекта»
- «устав-контекст», «сожми устав», «charter-context», «architecture-context», «граф проекта», «факты проекта»
- «проектная документация», «подготовь документы внедрения»
- устаревшие: «digest проекта», «сожми контекст проекта» — в v1.0.0 ведут на слои B/C, не на per-page `digest/leaves`

Первый экземпляр — проект **Trisigma / полное внедрение AB-платформы** (`Projects/TrisigmaFull`, сущность `Entities/trisigma`). Скилл параметризуется (`slug`, `root_page_id`, `entity_slug`) и не зашит только в Trisigma.

Не применять: точечный вопрос по одной встрече/странице без проектного архива (это `workvault-rag`); синхронизация одной Confluence-страницы в vault (это `ConfluenceSync`); индексация ТЗ (это `mofs-index`); компрессия master-ТЗ инструментов (это `tz-compressor-prompt.md`); запись устава в Confluence (это `pmo-charter-fill` + `tutu-confluence-jira`).

## Проблема

Подготовка документации и ответы по полям устава требуют всего контекста: дерево Confluence (пилот + PMO-бриф/устав + task_pages + гант), план, встречи, карточка сущности. Сырые страницы — сотни КБ.

v0.2.0 сжимал **каждую** stale-страницу отдельным `composer-2.5` в `digest/leaves`. На TrisigmaFull (замер 09.09.2026) **45 из 66** листьев `rejected`: композер пишет в тело служебный журнал («Пишу digest…», «Digest записан…», «Сжал до N%») несмотря на запрет в промпте. Среди rejected — устав, бриф, риски, минутки, гант, драфт устава полного внедрения. Per-page digest как канон для ответов **системно ненадёжен**. Метрики стоимости и сложности слоя C считать от реального объёма (~66 узлов / 45 rejected), не от устаревшей оценки «9 листьев».

Нужен полуавтомат: полный MD-архив (L0 канон), граф и факты скриптом, два устойчивых производных контекста синтезом grok с API-JSON.

## Решения Саши (зафиксированы, не переоткрывать)

### v0.2.0 (02.09) — архив и роли

1. Весь архив проекта скачивать в MD: полные тела страниц + кликабельные ссылки на источники и связанные материалы.
2. Скачивать PMO-документы, куда ведут ссылки с основной страницы (Бриф, Устав, связанные) — не всё пространство PMO целиком.
3. Связи собирать сразу (граф для поиска/навигации).
4. Управлять из Hermes-агента (Сирень), по паттерну `tz-workflow` / `hermes-feature`: один `agent -p` = одна модель = одна роль.
5. Обновление: сверка версий Confluence, докачка изменённых. Триггер — только ручной, без крона, пока Саша не скажет «ставь кроны».
6. **Промпт проектного компрессора** (`project-context-compressor-prompt.md`) и шаг F — наследие v0.2.0; в v1.0.0 **не канон для ответов** (см. редизайн 09.09). `tz-compressor-prompt.md` не трогать.
7. **MPP/вложения.** Скрипт внутри скилла: REST-скачивание whitelist-вложений. ConfluenceSync в рамках этого ТЗ **не дорабатывать**. Флаг `--with-attachments` — отдельная секция ТЗ ConfluenceSync. На диске для Trisigma источник плана — Gantt JSON страницы `519492770` (макрос `gantt-chart-planner`); `.mpp` — fallback, если JSON нет.
8. **Обновление архива.** Ручной триггер «обнови архив <Проект>» / «deep-mine refresh».

Пункты v0.2.0 про «сжимать каждую страницу composer-2.5 в digest» и «отдавать G пакет листьев» — **сняты редизайном 09.09**. Не возвращать.

### Редизайн 09.09.2026 — устав-контекст (CHANGE)

Финальные, не переоткрывать.

1. **Отказ от per-page composer-digest как канона.** Сырьё L0 не сжимаем «по странице». Digest/leaves на диске не удалять в этой итерации, но **не использовать** как SoT для Q&A, pack/G и ответов по уставу.
2. **Три слоя.** A — граф (no-LLM). B — `facts.json` (script-only + llm-assisted). C — два производных документа: `charter-context.md` + `architecture-context.md`.
3. **Вопрос Саши «сжать vs не сжать» — вариант 2:** оба производных документа. Не «один charter на всё».
4. **Три контура ответа** (не бинарная развилка): уставные → charter-context; цитаты/таблицы/цифры → L0 + граф без сжатия; сквозные сверочные → drill-down по pageId.
5. **`follow_outbound` реализовать** (в v0.2.0 поле было мертвым комментарием). Политика: тот же space + разрешённые PMO, глубина 1, denylist шаблонов ПРО, неизвестный space → stub.
6. **Синтез C — только grok + API-JSON.** `composer-2.5` — только механика (collect/refresh/graph/facts-script). Q&A по проекту — deepseek в Hermes по контекстам + граф.
7. Реализация кода — ждать «берём в работу». Согласование ТЗ ≠ команда на реализацию.

## Scope / Non-goals

**В скоупе v1.0.0 (редизайн скилла + CLI, не новый USERTOOLS-пакет):**

- Скилл `research/deep-mine-project` + CLI `deep_mine.py`: сохранить рабочие `init` / `collect` / `refresh` / `pack` / `analyze` / `document`; добавить `graph`, `facts`, `charter`, `architecture` (допустим флаг `--context charter|architecture` вместо двух команд).
- L0 канон через существующие деревья WorkVault (не копии тел в overlay).
- L1 overlay: MANIFEST, TREE, SOURCES, план, указатели **плюс** `GRAPH.json`, `LINKS.md`, `facts.json`, `charter-context.md`, `architecture-context.md`.
- Pull seed: `root ∪ pmo_seeds ∪ task_pages ∪ gantt_page` + outbound по политике follow (глубина 1).
- Граф узлов и типизированных рёбер без LLM-`related` в SoT.
- `facts.json`: script-only (даты, таблицы→CSV, суммы, JIRA, гант/Итого) + llm-assisted (ФИО, поручения) дешёвым per-page JSON, не композером.
- Синтез C батчами по группам полей (прецедент `docs/_charter_draft`, 5 пачек) + контракт устойчивости J1–J8.
- Тестирование контракта J1–J8: sandbox-readonly, API-JSON, validate-then-save, reject → `.rejected.json` + exit 6, 5 батчей charter, повтор `sources_sha` = 0 LLM.
- Оба производных документа (вариант 2 Саши).
- Три контура ответа.
- Ручной `refresh`: версии L0 → stale графа/фактов/контекстов по `sources_sha`.
- Первый проект: TrisigmaFull. Метрики C — от реального объёма ~66 узлов / 45 rejected, не от «9 листьев».

**Не в скоупе v1.0.0:**

- Удаление уже лежащих `digest/leaves` / пересжатие всех 66 страниц композером «чтобы починить rejected».
- Per-page composer-digest как вход Q&A / G / pack (запрещён как канон).
- Обогащение глубже политики follow (глубина > 1, весь PMO, произвольные пространства) — отдельная секция ТЗ.
- Новый USERTOOLS-пакет «с нуля».
- Индексация overlay `Projects/` в `mofs-index` — **[NEW-ENTITY, требует согласования Саши]**.
- Push черновиков `docs/` / контекстов в Confluence — после приёмки Саши, отдельным `ConfluenceSync push` / `pmo-charter-fill`.
- Доработка ConfluenceSync (`--with-attachments`).
- Крон refresh — не в v1.0.0; только по «ставь кроны».
- Дублирование полных транскриптов в overlay.
- Компрессия порога `compression.threshold`.
- Правка `tz-compressor-prompt.md`.
- Реализация кода — ждать «берём в работу».

## Архитектура

### Два слоя архива (без изменения инварианта L0)

```
Источники (внешние)          L0 канон (не дублировать)              L1 overlay
─────────────────            ─────────────────────────              ──────────
Confluence REST  ──pull──►   WorkVault/Confluence/<space>/.../      WorkVault/Projects/<Slug>/
  DPAN + PMO                 index.md (полные тела + frontmatter)     MANIFEST.json
План (Gantt JSON / MPP)      (бинарник: overlay/attachments/)         TREE.md
Meetings FF      ──index──►  WorkVault/Meetings/NewMeetings/         SOURCES.md
                             * - summary.md / transcript.md          GRAPH.json, LINKS.md
Сущность         ──read──►   WorkVault/Entities/<entity_slug>/       facts.json
                             card.md, context.md, risks.md, ...      charter-context.md
                                                                     architecture-context.md
                                                                     pointers/, mpp/, docs/
                                                                     digest/  (наследие, не SoT)
```

**L0 — канон.** Полные MD источников живут в WorkVault. Overlay **не копирует** тела страниц, транскрипты и файлы сущности. Overlay хранит пути, sha, version, граф, факты и производные контексты.

**L1 — overlay.** Проектный рабочий стол. Производное: манифест, граф, факты, два контекста, план, черновики.

Инвариант: удаление overlay не уничтожает канон. Пересборка overlay из L0 + Confluence REST должна быть возможна.

### Каталог overlay (v1.0.0)

```
WorkVault/Projects/<Slug>/          # пример: TrisigmaFull
├── MANIFEST.json
├── PROJECT.yaml
├── TREE.md                         # иерархия parent→children из GRAPH
├── SOURCES.md                      # pageId → path + живая wiki-ссылка
├── GRAPH.json                      # [NEW] узлы + рёбра (SoT графа)
├── LINKS.md                        # [NEW] таблица from,to,edge из GRAPH
├── facts.json                      # [NEW] script_only + llm_assisted
├── charter-context.md              # [NEW] слой C, поля устава
├── architecture-context.md         # [NEW] слой C, architecture/security
├── charter-context.rejected.json   # только при fail валидации C
├── architecture-context.rejected.json
├── attachments/
├── mpp/                            # CSV + plan.md (Gantt JSON или MPP fallback)
├── pointers/{meetings.md,entity.md}
├── digest/                         # наследие v0.2.0; не SoT для ответов
└── docs/
    ├── _inbox/
    └── _charter_draft/             # прецедент 5 пачек (ручной прогон); контракт батчей C
```

`PROJECT.yaml` (TrisigmaFull, поля v1.0.0; неизвестные старые ключи читать как alias):

```yaml
schema_version: "1.1"
slug: TrisigmaFull
display_name: "Полное внедрение AB-платформы Trisigma"
entity_slug: trisigma
confluence:
  root_page_id: "480923430"
  root_title: "Trisigma проект"
  space_primary: DPAN
  pmo_seeds:
    - { page_id: "490166551", title: "Бриф", space: PMO }
    - { page_id: "490167911", title: "Устав", space: PMO }
  task_pages:
    - { page_id: "519487958", role: charter_draft, space: PMO }
    - { page_id: "519489611", role: feature_gap }
    - { page_id: "514903239", role: feature_compare }
  follow_outbound:
    mode: same-space-plus-allowed-pmo
    depth: 1
    allowed_spaces: [DPAN, PMO]
    denylist_title_substrings: ["Шаблон устава", "Шаблон брифа", "шаблон ПРО"]
    unknown_space: stub
    max_outbound_pull: 24
  # строка follow_outbound: pmo-from-root — alias той же политики (миграция)
plan:
  source: gantt
  gantt_page_id: "519492770"
  gantt_instance: b10931f5-7163-4276-95c4-b8d1ca9d23ac
  rate_rub_per_hour: 3000
  project_title: "Полное внедрение AB-платформы Trisigma"
meetings:
  project_slugs: [trisigma]
contexts:
  charter_body_page_ids:
    - "490167911"   # Устав пилота
    - "490166551"   # Бриф
    - "519487958"   # Драфт устава полного внедрения
    - "490170597"   # Минутки
    - "493453409"   # Риски перехода
    - "506248810"   # Риски развертывания
    - "511548749"   # ИБ риски
    - "519492770"   # Гант + «Итого»
  architecture_themes: [architecture, security]
  architecture_body_page_ids: []   # если пусто — взять узлы GRAPH с theme ∈ architecture_themes
```

`gantt_instance` в примере — из текущего overlay; при реализации читать с диска, не хардкодить расхождение.

### РЕДИЗАЙН пайплайна: три слоя

Слой collect (A–E v0.2.0: pull, вложения, план, встречи, манифест) **остаётся**. На него садятся три новых слоя. LLM только там, где указано.

```
collect (no-LLM)     слой A graph (no-LLM)     слой B facts              слой C contexts
───────────────      ─────────────────────     ──────────────────        ────────────────
L0 + MANIFEST   ──►  GRAPH.json                facts.json                charter-context.md
TREE/SOURCES         LINKS.md                  script_only: скрипт       architecture-context.md
mpp CSV, pointers    follow_outbound depth 1   llm_assisted: дешёвый     grok + API-JSON, батчи
                                               per-page JSON (не composer)
```

#### Слой A — граф (no-LLM)

Команда: `deep_mine.py graph --slug <Slug>`.

**Seed (pull обязателен):** `root ∪ pmo_seeds ∪ task_pages ∪ gantt_page`.

**Дерево:** `children(seed)` из frontmatter L0 / Confluence children API (не из макроса `pagetree` в теле).

**Исходящие ссылки:** из тел L0 (`pageId=` в markdown). Политика `follow_outbound`:

| Правило | Действие |
|---|---|
| Тот же `space_primary` или `allowed_spaces`, глубина 1, не denylist | pull `--no-recursive --resync --to-file`, узел `kind: page` |
| Пространство неизвестно / не в allowlist | узел `kind: stub` (title/url если известны), **не pull** |
| Заголовок содержит denylist-подстроку (шаблоны ПРО) | stub, не pull |
| Исходящих > `max_outbound_pull` | лишние — stub + запись в `GRAPH.warnings`; не расширять глубину |
| JIRA / вложения / якоря | ребро `links_to` с `target_kind: jira\|attachment\|anchor`, не страница |

Рёбра SoT (только эти типы; **LLM-`related` из digest в GRAPH не переносить**):

- `parent` / `child` — иерархия Confluence
- `links_to` — исходящая ссылка из тела
- `seed` — узел входит в seed-множество

Хранение: `GRAPH.json` + человекочитаемые `TREE.md`, `LINKS.md` (`from,to,edge`).

Идемпотентность: повторный `graph` при тех же L0 sha не меняет состав узлов/рёбер (допускается перезапись `generated_at`).

#### Слой B — факты

Команда: `deep_mine.py facts --slug <Slug>`.

`facts.json` **разделён** (правка ревизора, не один «детерминированный экстракт»):

| Секция | Кто пишет | Что |
|---|---|---|
| `script_only` | только скрипт, без LLM | даты (ISO/`<time datetime>`), таблицы → CSV (reuse `table_extract`), суммы/бюджет/«Итого» ганта (как шаг C collect: L0×ставка, не сумма листьев JSON), ключи JIRA `hq.tutu.ru/browse`, pageId, version |
| `llm_assisted` | дешёвый per-page JSON **с API-JSON**, не `composer-2.5`, не grok-high | ФИО, роли, поручения, «кто кому что» из произвольного MD |

ФИО и поручения **нельзя** считать script-only: Confluence MD шумный (упоминания, макросы user, таблицы без шапки). Помечать `confidence` и `source_page_id`. Противоречия — массив, не «победил последний».

Каждый факт: `value`, `source_page_id`, `source_kind` (`script` \| `llm`), опционально `source_sha`. Цифры из llm_assisted **не** перекрывают script_only при конфликте (script побеждает).

#### Слой C — два производных контекста (вариант 2)

Команды: `deep_mine.py charter --slug <Slug>` и `deep_mine.py architecture --slug <Slug>` **или** `deep_mine.py context --slug <Slug> --context charter|architecture`. Обе команды в релизе обязательны (не «сначала только устав»).

**Вход синтеза (узкий, не 66 полных тел):**

- каталог полей ПРО (`pmo-charter-fill/references/pro-field-catalog.md`, 20 полей);
- `facts.json` + `GRAPH.json`;
- **полные тела** только `contexts.charter_body_page_ids` (устав, бриф, риски, минутки, план/гант «Итого»);
- остальные узлы GRAPH — **заголовками** (pageId, title, space, kind), без тела.

**Выход charter-context.md:** разделы = поля каталога ПРО. Каждый факт в теле несёт `source pageId`. Пустое поле — явная пометка `нет в источниках` + список просмотренных pageId, не выдумка.

**Выход architecture-context.md:** темы `architecture`, `security` (SDK, сравнение платформ, ИБ, чеклисты). Тот же контракт источников. Для non-charter вопросов (сравнение фич, SDK Go/JS, ИБ) **не** пытаться ответить одним уставом.

**Батчи, не монолит (правка ревизора).** Синтез C — **не** один проход на все поля. Пачки как ручной прецедент `Projects/TrisigmaFull/docs/_charter_draft/` (5 файлов), затем сборка оркестратором:

| Пачка | Файл-прецедент | Поля (ориентир каталога ПРО) |
|---|---|---|
| 1 MPP | `01_mpp_fields.md` | Параметры/сроки, Описание и границы, КТ, ИСР, Календарный план, Ресурсный план, Критерии приёмки |
| 2 Стратегия | `02_strategy_fields.md` | Что получит Туту, Если проекта не будет, Как заказчик поймёт, Цель, Финмодель, Ключевые поставки, Бюджет (текст; цифры — script_only) |
| 3 Стейкхолдеры/риски | `03_stakeholders_risks.md` | Контекст, Реестр стейкхолдеров, Матрица коммуникаций, Допущения, Ограничения, Реестр угроз и рисков |
| 4 Исправления инвариантов | `04_fix6_fields.md` | Повтор полей с инвариантами (ceil дней, пилот вычищен, `<time datetime>`) |
| 5 Блоки закрытия | `05_blocks5_fields.md` | Дожим стейкхолдеров/рисков после пачки 4 (критерии приёмки — пачка 1) |

Architecture-context: отдельные батчи по themes (минимум `architecture`, `security`), не смешивать с пачками устава в одном `agent -p`.

`pmo-charter-fill` исторически гоняет **3** grok-пачки на запись в Confluence. Слой C **читает** каталог тех же 20 полей, но **синтезирует 5 батчами** по прецеденту диска. Не схлопывать в один вызов «ради экономии»: монолит на объёме ~66 узлов — дыра ревизора (потеря фактов, журнал, reject).

Сложность/стоимость C оценивать от **реального** архива (~66 страниц, 45 rejected leaves, узкий набор тел ~8 pageId + заголовки остальных), не от модели «9 плохих листьев».

### Развилка ответа: три контура

Не «сжать XOR архив». Сирень (Q&A) выбирает контур по типу вопроса:

| Контур | Когда | Что читает | Сжатие |
|---|---|---|---|
| 1. Уставный | кто / сроки / блокеры / риски / поручения / поля ПРО | `charter-context.md` (+ facts при сверке цифр) | да, слой C батчами |
| 2. Цитата / таблица / сверка цифр | «покажи таблицу», «сколько в Итого», дословная цитата | GRAPH → pageId → L0 `index.md` / CSV | нет |
| 3. Сквозная сверка | «в уставе X, а на странице Y?» | charter-context как **индекс** → pageId → нырок в L0 | контекст как указатель, канон — L0 |

Architecture/SDK/ИБ → `architecture-context.md` (контур 1 для non-charter) с тем же drill-down в L0 (контур 3).

Запрещено: отвечать по `digest/leaves` как по канону; кормить Q&A сырым пакетом всех `Confluence/**/index.md`.

### Роли и модели

Инвариант: **один вызов `agent -p` = одна модель = одна роль.** Сирень координирует цепочку.

| Роль | Модель | Что делает | Не делает |
|---|---|---|---|
| Координатор | Сирень + `composer-2.5` как оператор CLI | collect/refresh/graph, запись файлов overlay, validate→save, сборка батчей | семантику устава, ФИО «из головы» |
| Факты llm_assisted | дешёвый LLM + **API-JSON** (не composer, не grok-high) | per-page JSON ФИО/поручений | журнал, запись файлов, суммы/даты |
| Синтез C | **`cursor-grok-4.6-high` + API-JSON** | батч полей → JSON секций | запись в overlay, markdown-преамбула, цифры в обход facts.script_only |
| Синтез C (альтернатива) | `deepseek/deepseek-v4-pro` (Hermes, reasoning high) + API-JSON | тот же контракт C | то же |
| Q&A | deepseek в Hermes | ответы по charter/architecture-context + GRAPH | пересборка архива |
| Исполнитель документов | `composer-2.5` | `docs/*.md` по плану G из контекстов | синтез C, per-page digest как SoT |
| Компрессор F | `composer-2.5` | **наследие**; не вызывать в `mine`/`refresh` по умолчанию | канон ответов |

`--output-format json` у Cursor CLI — обёртка сессии, **не** API-level structured output модели. Для C и llm_assisted обязателен `response_format` / json_schema так, чтобы модель **физически** могла вернуть только JSON (J3). Промпт «не пиши ничего кроме JSON» **недостаточен**. Если текущий `agent -p` не умеет json_schema — вызов C идёт через API/SDK, который умеет; не ослаблять J3 «пока нет флага».

Паттерн механики:

```bash
cd ~/WorkVault/Projects/<Slug> && agent -p "задача" -f --model <MODEL> --output-format json
```

Для синтеза C cwd агента — **sandbox вне overlay** (или overlay read-only); единственный writer файлов контекста — скрипт скилла после валидации.

### Что уже построено (не проектировать заново)

- L0 Trisigma в `WorkVault/Confluence/.../index.md`. Frontmatter: `confluence_id`, `title`, `confluence_url`, `space`, `parent`, `children`, `version`, `author`, `last_modified`, `synced_at`.
- Overlay `Projects/TrisigmaFull/` (MANIFEST, TREE, SOURCES, digest наследие, mpp CSV, Gantt JSON, `_charter_draft`).
- CLI `deep_mine.py`: `init|collect|refresh|digest|pack|mine|analyze|document` (скилл на диске ~v0.5.2). v1.0.0 **добавляет** команды слоёв A/B/C; `digest` не входит в дефолтный `mine`.
- `ConfluenceSync`: `python3 -m confluencesync pull <pageId> --depth N [--no-recursive|--to-file|--resync]`. Venv `~/hermes-agent/.venv`. Токен `CONFLUENCE_TOKEN` из `~/USERTOOLS/ConfluenceSync/.env`.
- Живой URL: `https://dom.tutu.ru/pages/viewpage.action?pageId=<id>`.
- План Trisigma: страница `519492770`, вложение `gantt-chart-<instance>.json`; стоимость = «Трудозатраты» L0 «Итого» × `plan.rate_rub_per_hour`.
- SkillsImprovement A0–A2 (03.09): `digest_validate`, `pack --task`, `task_pages`, theme-digest, статус `rejected`. Контракт «журнал → rejected» **остаётся для наследия digest**; новую устойчивость C задаёт J1–J8, не промпт компрессора.
- Каталог полей ПРО: `~/hermes-workspace/skills/productivity/pmo-charter-fill/references/pro-field-catalog.md`.

## Контракт устойчивости синтеза (J1–J8)

Обязателен для слоя C и для `facts.llm_assisted`. Нарушение любого пункта = fail-loud, канон L0 и свежий контекст на диске не перетирать.

| ID | Правило | Проверка |
|---|---|---|
| **J1** | Модель **не пишет** в overlay. Cwd синтеза — sandbox / read-only. Выход модели — **только stdout**. | Тест: после вызова C mtime overlay-файлов не меняется, пока оркестратор не save |
| **J2** | Оркестратор (скрипт скилла) — **единственный writer** `charter-context.md` / `architecture-context.md` / `facts.json` llm-секции | Нет `Write`/`StrReplace` у агента синтеза в `Projects/<Slug>/` |
| **J3** | **API-level structured output** (`response_format` / json_schema): модель физически отдаёт JSON объекта батча, не «текст, в котором где-то JSON». Промпт-запрет преамбулы **не замена** J3 | Клиент API отклоняет non-JSON; схема батча валидируется |
| **J4** | **Validate → потом save.** Сначала schema + позитивный контракт J6, затем запись | На fail валидации целевой `.md` не меняется |
| **J5** | Reject → `<name>.rejected.json` + **exit 6**; канон L0 и предыдущий свежий контекст не трогать | Как digest exit 6; файл `.rejected.json` содержит raw + ошибки валидатора |
| **J6** | Позитивный контракт: все обязательные секции каталога (или батча) присутствуют; каждый факт с `source_page_id`; **запрет преамбулы/журнала**; перед валидацией — `strip_preamble` (на случай утечки вне JSON) | Нет «Пишу…», «Digest записан», YAML-дампа инструкций; пустая секция = явный `нет в источниках` |
| **J7** | **Батчевый синтез** по группам полей (5 пачек устава / отдельные themes архитектуры). **Запрещён** один монолитный проход на весь каталог | В логе ≥ N вызовов модели на полный charter; один вызов = одна пачка |
| **J8** | **Идемпотентность:** повтор с тем же `sources_sha` **не вызывает** LLM; отдаёт существующий fresh-контекст | Тест: второй `charter` без изменения L0/facts/GRAPH = 0 LLM-вызовов |

`sources_sha` = sha256 канонической сборки: GRAPH fingerprint + facts.json sha + sha тел `charter_body_page_ids` (или architecture set) + версия каталога полей. Хранить во frontmatter контекста и в MANIFEST (`contexts.charter.sources_sha`).

Partial-fail батчей (J7/J8): если пачка N из 5 упала, retry пересоздаёт только упавшие. Успешно синтезированная пачка кэшируется в overlay под ключом hash входов этой пачки; при retry успешные берутся из кэша, LLM не вызывается. Это усиливает J8 — идемпотентность по `sources_sha` на уровне пачки. Полный перезапуск всех 5 пачек отвергнут как неэкономный.

Сборка после батчей: оркестратор склеивает JSON-секции в один markdown по шаблону каталога, проставляет шапку, пишет файл. Модель **не** рендерит финальный монолитный MD.

## Шаги пайплайна

Вершина автоматизации: **высокая** = CLI без LLM; **средняя** = LLM по жёсткой схеме; **низкая** = экспертный анализ; **ручная** = Саша.

### Collect A–E — высокая (без изменения роли)

Инструменты и fail-loud v0.2.0 сохраняются.

**A. Pull Confluence.** Seed = root (depth как сейчас, типично 6) + `pmo_seeds` + `task_pages` + `gantt_page`, каждый non-root `--no-recursive --resync --to-file`. После слоя A (`graph`) — дополнительные pull только по политике follow. VPN/401/403 — стоп пайплайна, не помечать fresh.

```bash
source ~/hermes-agent/.venv/bin/activate
cd ~/USERTOOLS/ConfluenceSync
python3 -m confluencesync pull <root> --depth 6 --resync --to-file
python3 -m confluencesync pull <pmo_or_task_or_gantt> --no-recursive --resync --to-file
```

**B. Вложения.** Скрипт скилла, whitelist `.json` (gantt-chart) + `.mpp`/`.mpx`/`.xml` + имена из PROJECT.yaml. ConfluenceSync файлы не качает.

**C. План → CSV.** Gantt JSON предпочтителен; MppReader fallback (`read_mpp.py`, Java 17). Стоимость Trisigma: L0 «Итого» × ставка. `plan.md` в v1.0.0 — опциональный механический outline из CSV **скриптом**, не отдельный composer-проход (composer не канон сжатия).

**D. Индекс встреч.** `search_meetings` / `workvault-rag`. Тела в overlay не копировать. Ориентир Trisigma ~91 встреча.

**E. MANIFEST + TREE + SOURCES.** После A/B/refresh — целиком, идемпотентно. `TREE.md` в v1.0.0 строится из GRAPH (после команды `graph`), не плоский список по space.

### Graph / Facts / Charter / Architecture

См. слои A/B/C выше. Порядок в `mine`: `collect → graph → facts → charter → architecture`. `architecture` не блокирует `charter` и наоборот: оба обязательны в полном `mine`; поштучный запуск разрешён.

### Наследие F (digest) — не в дефолтном mine

Команда `digest` остаётся в CLI для совместимости SkillsImprovement A0–A2. Валидатор журнала и exit 6 сохраняются. **Не вызывать** из `mine`/`refresh` v1.0.0 по умолчанию. Pack/G не требуют fresh leaf digest, если есть fresh charter/architecture-context (см. критерии).

### G. Архитектор — низкая

Модель: `cursor-grok-4.6-high`. Вход: `charter-context.md` и/или `architecture-context.md` + GRAPH + `docs/_inbox/diff.md`. Не кормить сырым пакетом L0 и не кормить `digest/leaves` как SoT. Точечный нырок в L0 — по pageId из контекста (контур 3).

Выход: `docs/_inbox/architect-plan.md`. Не оформляет финальный MD (это H).

### H. Исполнитель — средняя

Модель: `composer-2.5`. Вход: план G + указанные контексты/CSV. Выход: `docs/*.md`. Push в Confluence — не этот шаг (`pmo-charter-fill`).

### I. Приёмка — ручная

Саша читает `docs/` и/или контексты. Push — отдельная команда.

### Команды скилла

| Команда | Шаги | Когда |
|---|---|---|
| `init` | скелет overlay + PROJECT.yaml | первый раз |
| `collect` | A→B→C→D→E | «собери сырьё» без синтеза |
| `graph` | слой A, follow_outbound | «граф проекта» |
| `facts` | слой B | «факты проекта» |
| `charter` | слой C, `--context charter` | «устав-контекст» |
| `architecture` | слой C, `--context architecture` | «architecture-context» |
| `mine` | collect→graph→facts→charter→architecture | «собери архив» / «пробури» |
| `refresh` | poll version → pull → graph/facts/C при изменении sources_sha | «обнови архив» / «deep-mine refresh» |
| `pack` | PACK.md из контекстов + GRAPH + CSV extracts (не из rejected leaves) | задача архитектору / pmo-charter-fill |
| `analyze` | G | «глубокий анализ» |
| `document` | H | «проектная документация» |
| `digest` | наследие F | явно «пересожми digest»; не default |

Кроны из скилла **не ставятся**.

## Сущности GRAPH / facts / контексты

### GRAPH.json

```json
{
  "schema_version": "1.0",
  "slug": "TrisigmaFull",
  "generated_at": "2026-09-09T12:00:00Z",
  "follow_policy": "same-space-plus-allowed-pmo",
  "warnings": [],
  "nodes": {
    "490167911": {
      "title": "Устав: …",
      "space": "PMO",
      "kind": "page",
      "seed": true,
      "local_path": "Confluence/PMO/.../index.md",
      "version": "11",
      "content_sha256": "<64 hex>",
      "stub_reason": null
    }
  },
  "edges": [
    { "from": "480923430", "to": "493477568", "type": "child" },
    { "from": "493477568", "to": "490167911", "type": "links_to" },
    { "from": "490167911", "to": "490167911", "type": "seed" }
  ]
}
```

`kind` ∈ `page` | `stub`. Stub без `local_path`. Ребро `type` ∈ `parent` | `child` | `links_to` | `seed`.

### facts.json

```json
{
  "schema_version": "1.0",
  "slug": "TrisigmaFull",
  "generated_at": "2026-09-09T12:00:00Z",
  "sources_sha": "<hex>",
  "script_only": {
    "dates": [{ "value": "2026-09-07", "source_page_id": "519492770", "label": "старт полного внедрения" }],
    "tables": [{ "page_id": "514903239", "csv_path": "docs/_inbox/feature_compare/extracts/…" }],
    "sums": [{ "label": "effort_hours", "value": 6512, "source_page_id": "519492770" }],
    "jira": [{ "key": "PROJ-1", "source_page_id": "…" }]
  },
  "llm_assisted": {
    "people": [{ "fio": "…", "role": "…", "source_page_id": "…", "confidence": "high" }],
    "assignments": [{ "text": "…", "assignee": "…", "source_page_id": "…", "confidence": "medium" }]
  }
}
```

### Frontmatter контекста (обязательная шапка)

```yaml
---
schema_version: "1.0"
kind: charter | architecture
slug: TrisigmaFull
status: fresh
sources_sha: "<hex>"
generated_at: 2026-09-09T12:00:00Z
generated_by: cursor-grok-4.6-high
batches: [1, 2, 3, 4, 5]
---
```

`status` ∈ `fresh` | `stale` | `rejected`. Тело начинается с блока «Источники» (GRAPH + список pageId тел), затем секции каталога. Wiki-ссылки на L0 по pageId.

## Наследие: модель digest'ов (v0.2.0)

Контракт листьев/тем/`digest/links.md` / slug `p{pageId}` / stale-протокол SkillsImprovement A0 **не переписывать** в этом релизе. Файлы на диске можно оставить. **Запрещено:** считать их SoT для G, Q&A, pack и ответов по уставу. LLM-`related` из digest **не** копировать в GRAPH.

Миграция MANIFEST: добавить ключ `contexts` (`charter` / `architecture`: path, sha, status, sources_sha). Старые `digests` не удалять.

## Обновление

### Триггеры

Только по требованию: «обнови архив <Проект>» / «deep-mine refresh». Крон не в v1.0.0.

### Алгоритм `refresh`

1. Для каждого `pageId` в MANIFEST/GRAPH (kind=page): GET `version.number`, retry 429 как ConfluenceSync.
2. remote = local → skip.
3. remote > local → `pull --no-recursive --resync --to-file`, обновить sha/version.
4. Удалена на сервере → L0 не удалять; узел GRAPH `missing_remote`; контексты stale.
5. Новые дети известных родителей — pull, добавить в GRAPH.
6. Новые исходящие — политика follow_outbound (глубина 1), не бесконечный crawl.
7. Вложения whitelist / Gantt JSON — перескачать при изменении metadata; пересчитать CSV.
8. Встречи — перезапрос `search_meetings`; указатель обновить без копий тел.
9. Пересобрать E + `graph` + `facts` (llm_assisted только для изменившихся pageId).
10. Если `sources_sha` контекста изменился — пометить stale и пересинтезировать **затронутый** контекст (батчи, J8). Не вызывать LLM, если sha совпал.
11. `docs/_inbox/diff.md` — список pageId old→new version, какие контексты пересобраны.
12. Не запускать H без запроса. Не запускать `digest` по умолчанию.

## Входные данные / выходные артефакты

### Вход

| Вход | Где | Кто отдаёт |
|---|---|---|
| Параметры проекта | `PROJECT.yaml` | Саша / Сирень |
| Страницы Confluence | REST `https://dom.tutu.ru` + L0 | ConfluenceSync |
| Seed | root, pmo_seeds, task_pages, gantt_page | PROJECT.yaml |
| Follow policy | `confluence.follow_outbound` | PROJECT.yaml |
| Каталог полей ПРО | `pmo-charter-fill/references/pro-field-catalog.md` | скилл pmo-charter-fill |
| Вложения / план | attachments + Gantt JSON / MppReader | скрипт B, шаг C |
| Встречи | `Meetings/NewMeetings/` | MofsIndex, workvault-rag |
| Сущность | `Entities/<entity_slug>/` | EntityRegistry (чтение) |
| Прецедент батчей | `docs/_charter_draft/` | ручной прогон 09.2026 |

### Выход

| Артефакт | Путь | Кто потребляет |
|---|---|---|
| L0 MD | `WorkVault/Confluence/.../index.md` | overlay, контур 2–3, человек |
| MANIFEST / TREE / SOURCES | `Projects/<Slug>/` | скилл, refresh |
| GRAPH.json / LINKS.md | overlay root | facts, C, Q&A, pack |
| facts.json | overlay root | C, сверка цифр |
| charter-context.md | overlay root | Q&A контур 1, G, pmo-charter-fill |
| architecture-context.md | overlay root | Q&A non-charter, G |
| `*.rejected.json` | overlay root | отладка, не канон |
| CSV плана / extracts | `mpp/`, `docs/_inbox/` | C, G, pmo-charter-fill |
| pointers | `pointers/` | человек, G |
| docs drafts | `docs/*.md` | Саша (I) |
| digest/ (наследие) | `digest/` | не SoT v1.0.0 |

## Критерии успеха

Проверяемые:

1. **L0 не дублирован в overlay.** Тела страниц и транскрипты не лежат под `Projects/<Slug>/` (кроме путей-ссылок).
2. **Покрытие seed.** Root + pmo_seeds + task_pages + gantt_page в MANIFEST и GRAPH kind=page, L0 файл существует.
3. **TREE иерархический** из GRAPH parent/child, не плоский список по space.
4. **`follow_outbound` живой.** Исходящая ссылка того же space / allowed PMO, глубина 1, не denylist → узел page с L0. Чужой space → stub без pull. Denylist ПРО-шаблонов не качается.
5. **GRAPH без LLM-related.** Рёбра только `parent|child|links_to|seed`.
6. **facts разделён.** `script_only` не содержит ФИО/поручений как единственный источник; `llm_assisted` имеет `source_page_id`. Конфликт суммы: побеждает script_only.
7. **Оба контекста.** После `mine` существуют `charter-context.md` и `architecture-context.md` со `status: fresh` и валидной шапкой.
8. **Каждый факт контекста с pageId.** Нет секции каталога без блока (либо явная «нет в источниках»).
9. **J1–J8.** Соблюдены; перечень тестов — пункт Scope «Тестирование контракта J1–J8».
10. **Три контура.** Маршрутизация в скилле/инструкции Сирени: уставный / цитата / drill-down. Q&A не читает `digest/leaves` как SoT.
11. **Digest не в default mine/refresh.** Команда существует, по умолчанию не вызывается.
12. **Роли не смешаны.** Синтез C не на composer; механика collect не на grok-high.
13. **Масштаб метрик.** Комментарий/тест/оценка стоимости C оперирует порядком **45/66**, не «9 rejected».
14. **Идемпотентность collect+graph.** Повтор без изменения L0 не плодит дубли узлов.
15. **Встречи без копий.** `pointers/meetings.md` → `Meetings/NewMeetings/`, transcript в overlay нет.
16. **План.** При Gantt JSON — CSV + стоимость из L0 «Итого»; ConfluenceSync-код не менялся.
17. **Reuse.** Нет нового пакета в `USERTOOLS/`.
18. **Ручной refresh.** Нет записи в `~/.hermes/cron/jobs.json` от этого скилла.
19. **`tz-compressor-prompt.md`** не изменён.
20. **Pack.** Если pack остаётся — индекс строится из контекстов + GRAPH + CSV, fail-loud на stale/rejected **контекста**, не требует 66 fresh leaves.

## Что НЕ трогать

- Канон L0: не переносить, не переименовывать, не дублировать `WorkVault/Confluence/`, `Meetings/NewMeetings/`, `Entities/<slug>/` внутрь overlay.
- Не сносить и не mass-`--resync` уже скачанные страницы без изменения version.
- Не копировать транскрипты встреч целиком в `Projects/`.
- Не писать в чужие профили Hermes; не рестартить Gateway.
- Не создавать кроны до «ставь кроны».
- Не вызывать `ConfluenceSync push` в collect/graph/facts/C/G/H.
- Не менять `tz-compressor-prompt.md`.
- Не дорабатывать код и ТЗ ConfluenceSync (`--with-attachments`) в рамках этого ТЗ.
- Не расширять `mofs-index` таблицами `Projects/` без согласования Саши.
- Не трогать `compression.threshold`.
- Не править `entities.json`, протоколы PFS, OFC, реестры MOFS.
- Не заводить USERTOOLS-пакет, пока шаг закрывается CLI + скриптом скилла.
- `TZ/<Tool>/` других инструментов не переписывать «заодно» (в т.ч. SkillsImprovement — ссылка, не дубль редизайна).
- Не возвращать per-page composer-digest как канон ответов «пока починим промпт».
- Не считать `--output-format json` Cursor CLI выполнением J3.
- Цифры (сроки ceil, ФОТ, бюджет, «Итого») — не считать моделью синтеза C.

## Связи с экосистемой

| Компонент | Роль в deep-mine | Как вызывать | Ограничение |
|---|---|---|---|
| **ConfluenceSync** | collect A, refresh, follow pull; B — метаданные вложений | `python3 -m confluencesync pull …`; `get_attachments` / `attachment_download_url` | Не качает файлы; `--with-attachments` **не** в этом ТЗ |
| **скрипт скилла (B, graph, facts-script, writer C)** | вложения, GRAPH, facts.script_only, save контекстов | внутри `deep-mine-project` | Пишет только overlay |
| **MppReader** | fallback плана | `read_mpp.py --format both` | Не пишет .mpp; JVM ~2–4 с |
| **скилл `read-mpp`** | не вызывать для бурения | — | GS/xlsx, не overlay CSV |
| **workvault-rag / MofsIndex** | D | `search_meetings`, `get_meeting_body` | Overlay не в `docs_fts` без согласования |
| **Cursor CLI / API-JSON** | синтез C, опционально llm_assisted | grok-high + `response_format` | J1–J3; одна модель на вызов |
| **Hermes deepseek** | Q&A по контекстам | сессия Сирени | Не writer overlay |
| **pmo-charter-fill** | потребитель charter-context + CSV | pack/контекст как вход grok-пачек записи в Confluence | PUT только B0 section-patch, не этот скилл |
| **tutu-confluence-jira** | не вызывать из deep-mine | — | патч секций — другой скилл |
| **tz-workflow / hermes-feature** | паттерн управления | Сирень | Не реализация до «берём в работу» |
| **tz-compressor-prompt.md** | не подходит | не вызывать, не менять | — |
| **project-context-compressor-prompt.md** | наследие F | не default | не канон ответов |
| **EntityRegistry / entities.json** | резолв slug | чтение | Не писать |
| **ErrorBus** | будущий крон | не в v1.0.0 | только при «ставь кроны» |
| **SkillsImprovement** | A0–A2 на диске | ссылка | не дублировать текст областей |

Согласованные новые сущности **этого** ТЗ (внедрять при hermes-feature, пометка не «спросить ещё раз» — Саша вариант 2 закрыл):

1. `GRAPH.json`, `LINKS.md` overlay.
2. `facts.json` (две секции).
3. `charter-context.md`, `architecture-context.md`.
4. CLI `graph` / `facts` / `charter` / `architecture`.
5. Реализация `follow_outbound`.

По-прежнему только на согласование:

- Индексация `Projects/` в mofs-index.
- `--with-attachments` в ConfluenceSync.
- USERTOOLS-пакет DeepMineProject — не предлагается.
- Обогащение глубже depth 1.

## Контракты экосистемы

### Источник истины

- Владелец тел страниц Confluence: `api_confluence` (REST `https://dom.tutu.ru`); локальная проекция L0 — ConfluenceSync (`WorkVault/Confluence/<Space>/.../index.md`).
- Владелец overlay, GRAPH, facts, производных контекстов: deep-mine-project (`WorkVault/Projects/<Slug>/`).
- Владелец встреч: `Meetings/NewMeetings/` (индекс — MofsIndex).
- Владелец сущности: `Entities/<entity_slug>/` + `entities.json`.
- Владелец CSV плана: скрипт скилла / MppReader; канон трудозатрат Trisigma — L0 «Итого» ганта.
- Владелец каталога полей ПРО: `pmo-charter-fill` (`pro-field-catalog.md`).
- Владелец бинарника плана v1: overlay `attachments/` (скрипт B).
- Digest/leaves — **не** источник истины для ответов v1.0.0.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| confluence_id | str | required | ConfluenceSync (frontmatter L0) | ID страницы Confluence |
| version | str | required | ConfluenceSync / api_confluence | номер версии, строка как в L0 |
| confluence_url | str | required | ConfluenceSync | `https://dom.tutu.ru/pages/viewpage.action?pageId=<id>` |
| local_path | str | required | ConfluenceSync | путь L0 относительно WorkVault, файл `index.md` |
| content_sha256 | str | required | overlay-механика | hex sha256 тела без frontmatter, 64 символа |
| parent | str | optional | ConfluenceSync | confluence_id родителя или пусто у root |
| children | str | optional | ConfluenceSync | JSON-массив confluence_id |
| page_id | str | required | api_confluence | ID для polling и GRAPH |
| version.number | int | required | api_confluence | целочисленная версия remote |
| meeting_id | str | required | MofsIndex | имя файла без ` - summary.md` |
| meeting_date | str | required | MofsIndex | `YYYY-MM-DD` |
| transcript_present | bool | required | MofsIndex | true если есть transcript |
| entity_slug | str | required | EntityRegistry | `trisigma` для первого проекта |
| slug | str | required | PROJECT.yaml | overlay-slug (`TrisigmaFull`) |
| root_page_id | str | required | PROJECT.yaml | seed дерева |
| follow_outbound.mode | enum[same-space-plus-allowed-pmo,off] | required | PROJECT.yaml | политика слоя A; alias строки `pmo-from-root` |
| follow_outbound.depth | int | required | PROJECT.yaml | 1 в v1.0.0 |
| contexts.charter_body_page_ids | str | required | PROJECT.yaml | JSON-массив pageId полных тел для C |
| plan.gantt_page_id | str | optional | PROJECT.yaml | канон плана-страницы |
| filename | str | optional | api_confluence (attachments) | имя вложения |
| download_url | str | optional | ConfluenceSync.attachment_download_url | REST URL |
| filesize | int | optional | api_confluence | байт |
| sources_sha | str | required | overlay-механика (вход повторного C) | hex sha256 сборки входов C |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| schema_version | str | refresh, миграция | semver данных, старт `"1.0"` для GRAPH/facts/context |
| graph_path | str | facts, C, Q&A | `GRAPH.json` относительно overlay |
| node.kind | enum[page,stub] | follow, Q&A | stub = нет L0 |
| edge.type | enum[parent,child,links_to,seed] | LINKS.md, Q&A | без LLM-related |
| facts.script_only | str | C, сверка цифр | JSON-объект дат/таблиц/сумм/JIRA |
| facts.llm_assisted | str | C (ФИО/поручения) | JSON-объект people/assignments |
| charter_path | str | Hermes Q&A, G, pmo-charter-fill | `charter-context.md` |
| architecture_path | str | Hermes Q&A, G | `architecture-context.md` |
| context_status | enum[fresh,stale,rejected] | refresh, Q&A, pack | fresh=синхронен с sources_sha |
| sources_sha | str | J8, refresh | sha входов на момент синтеза |
| generated_at | datetime(iso8601) | audit | UTC |
| digest_status | enum[fresh,stale,missing_remote,rejected] | только наследие F | не SoT ответов |
| slug | str | wiki overlay | overlay slug |

### Зависимости

- Получает от: [ConfluenceSync, api_confluence, MppReader, MofsIndex, workvault-rag, EntityRegistry, pmo-charter-fill (каталог полей)]
- Отдаёт: [Hermes Q&A (deepseek), Cursor CLI архитектор (cursor-grok-4.6-high), pmo-charter-fill, Сирень, Саша]

### Breaking changes policy

- Версионирование формата: semver на `schema_version` в `MANIFEST.json`, `GRAPH.json`, `facts.json`, frontmatter контекстов.
- Breaking: смена типов рёбер GRAPH, слияние script_only/llm_assisted, отказ от pageId в фактах контекста — инкремент schema + `migrate_vN_to_vN+1()` + уведомить «Отдаёт».
- Per-page digest перестаёт быть SoT — breaking для pack/G, заложен в v1.0.0: pack читает контексты.
- Смена правила seed slug страницы (`p{pageId}`) не требуется для C; наследие digest slug не менять без миграции `_history`.

### Границы («что НЕ трогать»)

- Не менять ключ страницы в MANIFEST с `confluence_id` на title.
- Не считать `tz-compressor-prompt.md` и `--output-format json` CLI входным контрактом J3.
- Не менять код/CLI ConfluenceSync как часть реализации этого ТЗ.
- Не писать тела контекстов и digest в L0 Confluence.
- Не отдавать Q&A/G сырые `Confluence/**/index.md` пакетом и не отдавать rejected digest как fresh.

## Питфоллы/риски

1. **Composer-digest гниёт.** Журнал в теле → 45/66 rejected на TrisigmaFull. Чинить промптом F — повторять провал. Канон ответов = L0 + GRAPH + facts + два контекста.
2. **J3 vs промпт.** «В промпте запретили преамбулу» не удерживает модель. Нужен API json_schema. `--output-format json` агента — не то.
3. **ФИО/поручения как script-only.** Regex по Confluence MD даст шум и пропуски. Только `llm_assisted` + pageId + confidence; цифры — script.
4. **Outbound-взрыв.** На пилоте порядка двух десятков внешних id. Без depth=1, allowlist space, denylist шаблонов ПРО и `max_outbound_pull` — crawl всего PMO.
5. **Монолитный синтез C.** Один grok-проход на 20 полей × ~66 заголовков + 8 тел — потеря фактов и снова журнал. Только батчи (J7).
6. **Один charter на SDK/ИБ.** Устав не содержит сравнение платформ и чеклист SDK. Без `architecture-context.md` контур 1 молчит — поэтому вариант 2.
7. **Цифры из модели.** Бюджет/ceil/«Итого» из grok расходятся с L0. Script_only побеждает.
8. **Stale контекст как fresh.** Обязательны `sources_sha` + status; Q&A не читает stale без оговорки.
9. **VPN / on-prem.** Fail-loud; не помечать skip как fresh.
10. **Вложения ≠ ссылки.** Без шага B нет ганта/MPP.
11. **Pagetree-макрос.** Иерархия из children API, не из тела макроса.
12. **ab_platforma ≠ trisigma.** Встречи не смешивать.
13. **Усечённый sha P0.** Нужен полный sha256.
14. **Крон без команды.** Запрещён.
15. **Пилот vs полное внедрение.** Противоречия держать явным массивом в фактах/контексте, не затирать «последним абзацем».
16. **Java 17** нужен только на MPP-fallback.

## Открытые вопросы

### Закрыты (не переоткрывать)

1. Промпт F и MPP-скрипт — бриф 02.09 (наследие).
2. **Сжать vs не сжать / второй документ — вариант 2** (09.09): оба `charter-context` и `architecture-context`.
3. Per-page digest как канон — **нет**.
4. API-JSON (J3), батчи (J7), split facts — **да**, правки ревизора приняты в это ТЗ.

### Отложены, не блокируют v1.0.0

1. Обогащение глубже depth 1 (какие пространства второй волны).
2. Dual-store бинарников с L0 `_attachments/` — когда появится флаг ConfluenceSync.
3. Индексация overlay в mofs-index.
4. Крон refresh — только по «ставь кроны».
5. Судьба файлов `digest/leaves` на диске (оставить / архивировать) — после приёмки C; не блокер синтеза.
6. Конкретный slug дешёвой модели для `facts.llm_assisted` — выбрать при hermes-feature (критерий: API-JSON + дешевле C); не composer и не grok-high.

## Приложения к ТЗ

| Файл | Содержание |
|---|---|
| — | приложений нет; брифы живут вне master (`_brief_for_architect.md` — вход, не часть master-ТЗ) |
| Каталог полей ПРО | `~/hermes-workspace/skills/productivity/pmo-charter-fill/references/pro-field-catalog.md` (вне `TZ/`, не копировать сюда) |
| Прецедент батчей | `~/WorkVault/Projects/TrisigmaFull/docs/_charter_draft/` (runtime, не appendix) |

## Доработка SkillsImprovement

Зонтичное ТЗ A0–A2 (digest rejected, pack, task_pages): **[SkillsImprovement_TZ.md](../SkillsImprovement/SkillsImprovement_TZ.md)**. Текст областей A/B/C SkillsImprovement в этом master не дублируется. Редизайн v1.0.0 **переопределяет** SoT для ответов (контексты вместо leaves); A0-валидатор digest остаётся для наследия F.

## Статус

Approved v1.0.0 (2026-09-09). РЕДИЗАЙН пайплайна записан: слои A/B/C, оба производных документа, J1–J8, три контура, `follow_outbound` в скоупе. Согласование ТЗ ≠ реализация. Ждать «берём в работу» → `hermes-feature`. Кроны не ставить. Код скилла этим файлом не меняется.
