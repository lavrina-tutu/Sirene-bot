---
tool: EcosystemIntegration
version: 0.7.0
date: 2026-10-25
status: active
maintainer: Hermes + Cursor
last-section-added: 2026-10-25 — TZ:patch пакет eco-config-w3 v0.1.0 (OverlayConfig, волна 3; 30 чистых регистраций)
---

# ТЗ: EcosystemIntegration

## §1 Цель

Единый машиночитаемый манифест экосистемы Hermes/USERTOOLS (`EcosystemManifest.json`) с компактными рендерами для человека и Cursor, промпт-компрессором ТЗ и автоматической сверкой drift — чтобы Сирень, архитектор и исполнитель работали из одного актуального индекса инструментов, сущностей, связей и конфликтов без ручной синхронизации десятков ТЗ.

## §2 Проблема

- **Фрагментация контекста:** 24+ инструментов, десятки ТЗ, реестры и API; связи описаны разрозненно в `MAIN_TZ_INVENTORY.md` и master-ТЗ.
- **Дубли и drift:** `_mark_objects_registry.json` в нескольких местах; USERTOOLS-папки не всегда совпадают с инвентарём; tz_ref устаревает.
- **Перегруз промптов:** полное ТЗ инструмента — накопительная история (10–100+ КБ); архитектор и исполнитель тратят контекст на повторы и устаревшие секции.
- **Смешение моделей:** один вызов Cursor с разными ролями (компрессия + план + код) даёт неконсистентный результат и нарушает cost/latency-матрицу Hermes.

## §3 Компоненты

### 3.1 EcosystemManifest.json + schema

Канонический JSON-реестр: `tools{}`, `entities{}`, `links[]`, `conflicts[]`. Валидируется `EcosystemManifest.schema.json` (Draft-07). Индексирует существующие ТЗ — **не заменяет** их содержимое.

### 3.2 render_manifest.py

CLI (stdlib only):

| Режим | Артефакт | Назначение |
|---|---|---|
| `--render` | `EcosystemManifest.render.md` | Полная human-версия: инструменты по категориям, сущности по типу, таблица связей, открытые конфликты |
| `--digest` | `EcosystemManifest.digest.md` | Компактный digest (~300–800 токенов) для Cursor: имена инструментов + entities/conflicts одной строкой |
| `--check-drift` | stdout | Сверка tz_ref, USERTOOLS↔tools, Registries/*.json↔entities, TZ↔tools; exit ≠0 при расхождениях |

Идемпотентен, детерминированная сортировка.

### 3.3 tz-compressor-prompt.md

Промпт-компрессор ТЗ: из полного master-ТЗ (накопительная история) — «актуальная спецификация» 3–5 КБ с **full-coverage** (100% сущностей/полей/API/лимитов, имена дословно).

- **Модель:** `gemini-3.6-flash-low` (запасная `gemini-3.7-flash-low`). **НЕ** composer.
- **Без кэша:** экстракты не сохраняются между задачами.

### 3.4 Правки скиллов (tz-workflow, hermes-feature)

Раздельные задачи Cursor по моделям — координирует Сирень (default), **не смешивать** модели в одном вызове:

1. Шаг 0 — gemini (компрессия ТЗ)
2. Шаг 1 — claude-sonnet-5-thinking-medium (архитектор: ТЗ/план)
3. Шаг 2 — composer-2.5 (реализация)
4. Шаг 3 — composer-2.5 / контроль (тесты)

### 3.5 MAIN_TZ_INVENTORY + drift-check

Инструмент зарегистрирован в инфраструктурном разделе инвентаря. После изменений ТЗ/кода — обязательное обновление манифеста и `render_manifest.py --check-drift` (крон `ecosystem_drift_check` — только по явной команде «ставь»).

## §4 Конвейер (раздельные задачи по моделям)

```
Сирень (default)
  │
  ├─► Cursor #0  gemini-3.6-flash-low + tz-compressor-prompt
  │       вход: полное ТЗ инструмента (+ зависимые ТЗ при необходимости)
  │       выход: актуальная спецификация 3–5 КБ (в памяти сессии, без кэша)
  │
  ├─► Cursor #1  claude-sonnet-5-thinking-medium
  │       вход: EcosystemManifest.digest.md + экстракты Шага 0 + бриф Саши
  │       выход: драфт/план ТЗ или пофайловый план реализации
  │
  ├─► Cursor #2  composer-2.5
  │       вход: план архитектора + экстракты
  │       выход: код, тесты, правки скиллов/конфигов
  │
  └─► Cursor #3  composer-2.5 (контроль)
          вход: план + diff
          выход: pytest/CLI-верификация, отчёт
```

**Инвариант:** один вызов `agent -p` = одна модель = одна роль.

## §5 Связи

| Компонент | Читает | Пишет |
|---|---|---|
| EcosystemIntegration | MAIN_TZ_INVENTORY, USERTOOLS/*, Registries/*, Hermes-Backlog/TZ/* | EcosystemManifest.json, *.render.md, *.digest.md |
| tz-workflow | EcosystemManifest.digest, tz-compressor-prompt | master-ТЗ, MAIN_TZ_INVENTORY |
| hermes-feature | digest + экстракты + план | код USERTOOLS, манифest (после Шага 2/3) |
| ProtocolFromSummary, TaskRefresh, workvault-rag | entities.json | — |
| MarkObjectsFromSummary, MofsIndex | _mark_objects_registry.json, entities.json | frontmatter, MOFS-реестр |
| EntityRegistryCLI | entities.json | entities.json (через CLI) |

## §6 НЕ трогать

- Содержимое существующих `TZ/<Tool>/<Tool>_TZ.md` (история) — только индексация через `tz_ref`. Исключение графа `DEV/ecosystem-drift-reconcile`: ретрофит раздела `## Контракты экосистемы` в ТЗ инструментов — не произвольная правка содержимого и не переписывание истории назначения.
- `entities.json` / `entities.schema.json` — только запись-ссылка `entities_json_registry` в манифесте.
- Gateway-процесс Hermes — не рестартовать из этого инструмента.
- Крон `ecosystem_drift_check` — не создавать автоматически.
- Отдельный скилл `ecosystem-manifest` — не создавать (логика в EcosystemIntegration + hermes-feature/tz-workflow).

## §7 Критерии готовности

- [ ] `EcosystemManifest.json` валиден по schema; ≥24 инструмента из MAIN_TZ_INVENTORY; `entities_json_registry` присутствует.
- [ ] `render_manifest.py --render` и `--digest` генерируют детерминированные файлы; digest ≤ ~3200 символов.
- [ ] `--check-drift` возвращает построчный отчёт; exit 1 при реальных расхождениях.
- [ ] Скиллы tz-workflow (Шаг 0–1) и hermes-feature (Блок 1, 4, 7) обновлены; cursor-cli-patterns — канон в hermes-feature.
- [ ] `tz-compressor-prompt.md` описывает full-coverage, модели gemini, запрет кэша.
- [ ] MAIN_TZ_INVENTORY содержит строку EcosystemIntegration в инфраструктурном разделе.

## §8 Доработка v0.4.0: applications + reuse-first + QMD-удаление

Утверждено Сашей 2026-08-21. Три независимых изменения: (1) новый top-level блок `applications` в манифесте, (2) обязательное правило reuse-first во всех dev-промптах, (3) полное удаление QMD-Search из активных индексов.

### 8.1 Новый top-level блок `applications`

`EcosystemManifest.schema.json`: minor bump **0.3.0 → 0.4.0** (новый required top-level key — обратно несовместимо для строгих валидаторов, но не ломает существующие консьюмеры `tools/entities/links/conflicts`).

**Назначение:** индексировать внешние/встроенные приложения-платформы, которые используют USERTOOLS как клиенты/движки, отдельно от `tools{}` (USERTOOLS-инструментов) и `entities{}` (сущности vault).

**Структура записи `applications.<key>`:**

| Поле | Тип | Описание |
|---|---|---|
| `name` | string | Человекочитаемое имя приложения |
| `kind` | enum | Один из: `database_engine`, `file_format_reader`, `ml_component`, `knowledge_app`, `communication_platform`, `project_tracker`, `cloud_workspace`, `notification_channel` |
| `status` | string | `active` / `deprecated` / и т.п. (как в `tools{}`) |
| `used_by` | array[string] | Список ключей `tools{}`, использующих приложение |
| `purpose` | string | Краткое назначение (1 фраза) |
| `entity_ref` | string \| null | Ссылка на ключ `entities.api_*` при наличии (single source of truth — purpose/owner_tool не дублируются); `null`, если сущности в `entities.json` нет |

**Инвентарь 13 приложений (проверено по коду, зафиксировано на 2026-08-21):**

| # | Приложение | kind | used_by | entity_ref |
|---|---|---|---|---|
| 1 | SQLite/FTS5 | `database_engine` | MofsIndex | null |
| 2 | MS Project (.mpp/mpx/xml/MSPDI) | `file_format_reader` | MppReader (mpxj+JPype+Java, read_mpp.py) | null |
| 3 | Hugging Face (эмбеддинги) | `ml_component` | Honcho (self-hosted, `~/honcho`) | null |
| 4 | Obsidian | `knowledge_app` | скиллы obsidian, workvault-entities, get-obsidian-link, MOFS-wiki | null |
| 5 | Fireflies | `communication_platform` | MoveFromFF (GraphQL API, импорт встреч) | null |
| 6 | Outlook/Exchange (EWS) | `communication_platform` | ExchangeMonitor, ExchangeOrgLookup, ExchangeMeeting | `api_exchange` |
| 7 | Zoom | `communication_platform` | MoveFromFF, ZoomAPI | `api_zoom` |
| 8 | Loop/Mattermost (ТУТУ) | `communication_platform` | MoveFromLoop | `api_loop` |
| 9 | Zulip | `communication_platform` | MoveFromZulip | null |
| 10 | Jira | `project_tracker` | OKRTool, SRTool, MoveFromJira | `api_jira` |
| 11 | Confluence | `cloud_workspace` | ConfluenceSync, ProtocolFromSummary, TaskRefresh | `api_confluence` |
| 12 | Google (Sheets/Drive/Workspace) | `cloud_workspace` | google-workspace, read-mpp | null |
| 13 | Telegram | `notification_channel` | gateway/уведомления | `api_telegram` |

**Правило single source of truth:** для приложений с `entity_ref ≠ null` (Confluence, Jira, Exchange, Zoom, Loop, Telegram) поля `purpose`/`owner_tool`/детали доступа НЕ дублируются в `applications{}` — авторитетный источник этих данных `entities.api_*` в `entities.json`. В `applications{}` для них остаётся только краткий `purpose` (одна фраза, для читаемости рендеров) и ссылка `entity_ref`.

### 8.2 Reuse-first rule — обязательное правило dev-промптов

Правило Саши, обязательное для **всех** dev-промптов (архитектор и исполнитель, ТЗ-workflow и hermes-feature), канонический текст:

> 1) Решение задачи в первую очередь опирается на существующие приложения/сущности экосистемы (USERTOOLS, external applications из `applications{}`, реестры `Registries/*`, сущности vault).
> 2) Новые приложения/сущности — ТОЛЬКО если существующие не решают задачу.
> 3) Любое предложение НОВЫХ сущностей (ТЗ/план/багфикс/доработка, любой уровень) — сначала на согласование Саше, самому не внедрять.

**Канонический файл:** `references/reuse-first-rule.md` — единый источник текста правила, размещается в обеих папках скиллов (`tz-workflow/references/` и `hermes-feature/references/`); оба скилла ссылаются на него, а не копируют текст инлайн (избежать drift между копиями).

**Точки внедрения:**

- `tz-workflow`: Шаг 0 (компрессия ТЗ) — тег `[NEW-ENTITY]` при упоминании кандидата на новую сущность; Шаг 1 (анализ архитектора) — явная проверка reuse перед предложением нового; инвариант 6 (новый); checklist — новый пункт «reuse-first проверен».
- `hermes-feature`: Блок 1 (setup), Блок 1А, Блок 2 (impl), Блок 7, Блок 6Б — явная ссылка на `reuse-first-rule.md`; checklist — новый пункт.

Данный пункт — правка **скиллов**, а не EcosystemIntegration-кода; выполняется в отдельной dev-задаче hermes-feature (Блок 1/2), не в рамках данного ТЗ-файла.

### 8.3 QMD-Search — полное удаление из активных индексов

Решение Саши: «чтобы больше о нём не слышать». Полное, не архивное удаление из всех активных индексов экосистемы (файл мастер-ТЗ на диске не удаляется физически, но выводится из индексации).

Действия (выполняются вне EcosystemIntegration в соответствующих компонентах):

1. Удалить ключ `tools.qmd_search` из `EcosystemManifest.json`.
2. Добавить `"QMD-Search"` в `skip_dirs` внутри `check_drift()` в `render_manifest.py` — чтобы drift-check не пытался сопоставить отсутствующую USERTOOLS-папку/ключ.
3. Убрать строку `QMD-Search` из `MAIN_TZ_INVENTORY.md` полностью (без переноса в архивный раздел инвентаря).
4. `EcosystemManifest.render.md` и `EcosystemManifest.digest.md` — перегенерировать через `render_manifest.py`, вручную не редактировать.
5. Файл `TZ/QMD-Search/QMD-Search_TZ.md` остаётся на диске как исторический артефакт, но вне активных индексов (не в `tools{}`, не в `MAIN_TZ_INVENTORY.md`).

### 8.4 Правки `render_manifest.py`

1. Новая функция `sorted_applications()` — детерминированная сортировка по `kind`, затем по `name.lower()` (аналогично существующей сортировке `tools`/`entities`).
2. `render_markdown()`: новый блок `## Applications` — таблица с колонками `key | name | kind | status | used_by | purpose`; позиция — **после** `## Tools by category`, **перед** `## Skills ↔ Tools`.
3. `render_digest()`: построчный компакт-формат `App:<name>|<used_by>|<purpose, обрезанный до ~40–50 символов>` — одна строка на приложение, после tool-строк, перед секцией conflicts. Заголовок digest дополняется счётчиком `applications=K` (по аналогии с существующими `tools=N`, `entities=M`).

Данный пункт — код `render_manifest.py`, реализуется отдельной dev-задачей (Cursor #2, composer-2.5); в рамках текущего ТЗ-файла фиксируется как требование к реализации.

### 8.5 Версия и документация

- `EcosystemManifest.schema.json` и `EcosystemManifest.json`: `schema_version` 0.3.0 → 0.4.0, `updated_at` = 2026-08-21.
- `EcosystemIntegration_TZ.md` (этот файл): версия во frontmatter 0.3.0 → 0.4.0 (выполнено выше), добавлена данная секция §8.
- `MAIN_TZ_INVENTORY.md`: обновить строку `EcosystemIntegration` (версия 0.4.0, дата, краткое упоминание блока `applications`) — выполняется отдельно при импле (не входит в правки данного ТЗ-файла архитектором).

### 8.6 Критерии готовности v0.4.0

- [ ] `EcosystemManifest.schema.json` и `.json` бампнуты до `schema_version: "0.4.0"`; блок `applications{}` валиден, содержит все 13 приложений из §8.1 с полями `name, kind, status, used_by, purpose, entity_ref`.
- [ ] Для 6 приложений с `entity_ref` (Confluence, Jira, Exchange, Zoom, Loop, Telegram) — ссылка указывает на существующий `entities.api_*`; purpose/owner_tool не задублированы за пределами краткой фразы.
- [ ] `render_manifest.py`: реализованы `sorted_applications()`, блок `## Applications` в `render_markdown()` (после Tools by category, перед Skills ↔ Tools), строки `App:...` в `render_digest()` (перед conflicts) с заголовком `applications=K`.
- [ ] `EcosystemManifest.render.md` / `.digest.md` перегенерированы (не правлены руками) и содержат раздел Applications.
- [ ] `tools.qmd_search` отсутствует в `EcosystemManifest.json`; `"QMD-Search"` в `skip_dirs` в `check_drift()`; строка QMD-Search отсутствует в `MAIN_TZ_INVENTORY.md`; `--check-drift` не сообщает об ошибке по QMD-Search.
- [ ] `references/reuse-first-rule.md` создан и идентичен в `tz-workflow/references/` и `hermes-feature/references/`; оба скилла ссылаются на него из указанных в §8.2 точек (не копируют текст инлайн).
- [ ] `tz-workflow` checklist и `hermes-feature` checklist содержат явный пункт «reuse-first проверен / новые сущности не введены без согласования».
- [ ] `MAIN_TZ_INVENTORY.md` содержит обновлённую строку EcosystemIntegration (0.4.0) и не содержит строку QMD-Search.

## Контракты экосистемы

### Источник истины
- Владелец записи: EcosystemIntegration (`EcosystemManifest.json`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| tool | str | optional | master-ТЗ инструментов (`TZ/<Tool>/<Tool>_TZ.md`) | YAML-frontmatter `tool:` |
| version | str | required | master-ТЗ инструментов (`TZ/<Tool>/<Tool>_TZ.md`) | YAML-frontmatter `version:` |
| status | str | required | master-ТЗ инструментов (`TZ/<Tool>/<Tool>_TZ.md`) | YAML-frontmatter `status:` |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| schema_version | str | tz-workflow, hermes-feature, render_manifest | "0.4.0", `json:ecosystem_manifest_v0_4` |
| updated_at | str | tz-workflow, hermes-feature, render_manifest | YYYY-MM-DD |
| tools | dict | tz-workflow, hermes-feature, render_manifest | словарь инструментов экосистемы |
| applications | dict | render_manifest | словарь внешних приложений/API (13 приложений) |
| entities | dict | render_manifest | словарь сущностей vault |
| links | list | render_manifest, tz-workflow | список связей между инструментами/сущностями |

### Зависимости
- Получает от: [tz-workflow, MAIN_TZ_INVENTORY]
- Отдаёт: [tz-workflow, hermes-feature, ecosystem-scheme]

### Breaking changes policy
- Версионирование формата: semver в поле `schema_version` внутри `EcosystemManifest.json` (сейчас "0.4.0")
- При breaking change: бамп `schema_version`, обновление `EcosystemManifest.schema.json` и `render_manifest.py`

### Границы («что НЕ трогать»)
- Не изменять содержимое master-ТЗ инструментов (`TZ/<Tool>/<Tool>_TZ.md`), кроме индексации через `tz_ref`
- Не рестартовать Gateway-процесс Hermes
- Не модифицировать `entities.json` напрямую (только чтение через `entities_json_registry`)

## §9 Доработка v0.4.1/v0.4.2: lifecycle-фильтр drift + чек-точка finalize/DECOMM

Утверждено на `GATE:diagnose-review` графа `DEV/ecosystem-drift-reconcile` (FULL BUGFIX, 2026-09-27). Закрывает повторяющийся класс находок крона `ecosystem_drift_check` (`render_manifest.py --check-drift`): файл ТЗ на диске не сходится с `tools{}` / контрактами, а чекер не умеет закрыть lifecycle. Код чекера, тесты, манифест и скиллы — в `PLAN-IMPL-TAIL` / `ORCH:shared-state`; здесь фиксируются правила.

### 9.1 Фильтр lifecycle в `--check-drift`

Если `tools.<key>.status` ∈ `{archived, completed}`:

- не требовать раздел `## Контракты экосистемы` (`check_missing_contracts_section` — skip);
- симметрично skip для `check_manifest_contract_not_in_tz` и `check_contract_format_mismatch`;
- `tz_not_in_manifest` для такого инструмента **не** закрывается `skip_dirs` и **не** объявлением «контрактов никогда не было»: архивный/завершённый инструмент остаётся в `tools{}` как исторический индекс (живой `tz_ref`, исторические `links` допустимы). Пока запись в `tools{}` есть — rel в `indexed_tz`, находки `tz_not_in_manifest` нет.

`draft` / `active` / `paused` / фактический `released` — проверять секцию контрактов как раньше (пример: EntityRegistry `draft` + links без секции должен флагироваться, пока секции нет).

Не закрывать archived-находку текстом «Нет внешних контрактов» в stale-ТЗ: DECOMM останавливает контракт, а не объявляет, что его не было.

### 9.2 Политика `SKIP_TZ_DIRS` vs tools-запись

`SKIP_TZ_DIRS` (`skip_dirs` в `check_drift`) — **только** для не-инструментов и сознательно выведенных из индекса, файл на диске оставлен. Канон на момент v0.4.2: `QMD-Search` (§8.3), `EntitiesSchemaV12`.

Не расширять `skip_dirs` активными или архивными инструментами с живым `tz_ref`. Активные/архивные получают **tools-запись** (пишет только `ORCH:shared-state`), не fake-skip.

Скан `TZ/`: игнорировать `appendix_*_TZ.md` и `*_v[0-9]*_TZ.md` (лишние файлы рядом с каноническим `*_TZ.md`, уже в `indexed_tz`). После этого канонические каталоги вроде MarkObjectsFromSummary / EcosystemIntegration / TZ-Workflow не нуждаются в `skip_dirs`, если primary `tz_ref` уже в `tools{}`.

Пример: `TgTopicDuplicate` (`TZ/tg-topic-duplicate/…`) — tools-запись, не `skip_dirs`. `DialogBacklog` после DECOMM — `status=archived` в `tools{}`, не `skip_dirs`.

### 9.3 Чек-точка после `TZ:finalize` / DECOMM

Манифест должен сходиться с диском в момент появления нового/изменённого `tz_ref`, а не только в конце `HF-TAIL`:

- после `TZ:finalize` (+инвентарь): если на диске `tz_ref`, которого нет в `tools{}` — stub-запись `tools{}` (status из инвентаря) **или** явная карточка `ORCH:shared-state` с AC «`tools.tz_ref` зарегистрирован»;
- после DECOMM (`DECOMM-TAIL` / `ORCH:shared-state`): `status=archived`, path архива, `tz_ref` можно оставить, исторические links допустимы **потому что** чекер фильтрует archived (§9.1); AC — `--check-drift` exit 0 **или** остаток не про этот slug.

Полная запись links/contracts — по-прежнему после `GATE:take-into-work` / хвоста `ORCH:shared-state`. Ядро `~/hermes-agent` вне скоупа этого правила.

### 9.4 Чекер не читает инвентарь

SoT индекса инструментов для `--check-drift` — `EcosystemManifest.json` (`tools{}.tz_ref` → `indexed_tz`). Чекер **не** читает `MAIN_TZ_INVENTORY.md`. Схождение инвентарь ↔ манифест даёт чек-точка §9.3, не второй SoT внутри `check_drift`.

### 9.5 Версия и критерии готовности v0.4.2

- `EcosystemIntegration_TZ.md` (этот файл): frontmatter `version` 0.4.1 → 0.4.2; добавлена данная секция §9; в §6 уточнено исключение ретрофита контрактов.
- Строка `MAIN_TZ_INVENTORY.md` — на `TZ:finalize` (не в этом файле).
- Код фильтра / `SKIP_TZ_DIRS` / тесты / tools-запись TgTopicDuplicate / правки скиллов — `HF:impl` / `HF:test` / `ORCH:shared-state`.

Критерии:

- [ ] `--check-drift`: инструмент `archived`/`completed` + links + ТЗ без секции контрактов → нет `missing_contracts_section`; `draft`/`active` + links + без секции → флаг есть.
- [ ] `SKIP_TZ_DIRS` не содержит активных инструментов; QMD-Search и EntitiesSchemaV12 тихие; appendix/versioned `*_TZ.md` не дают `tz_not_in_manifest`.
- [ ] После `TZ:finalize` / DECOMM манифест сходится с диском (tools-запись или явный non-index); чекер инвентарь не читает.
- [ ] Ретрофит `## Контракты экосистемы` в ТЗ инструментов — только исключение §6 этого графа, история назначения не переписывается.

## §10 Доработка v0.5.0: модуль 0 «Единый конфиг экосистемы» (OverlayConfig)

Утверждено брифом 2026-09-30 (постановка — `appendix_module0_postanovka_20260930.md`, источник истины решений). Кейс CHANGE существующего `EcosystemIntegration`: новый USERTOOL в `tools{}` **не** заводится. Код лоадера/схем/YAML — `HF:impl` / `HF:test`; запись индекса `config.tools.<key>` — `ORCH:shared-state`. Эта секция — требования, не реализация.

**I1.** `current`: инструменты читают разрозненные per-tool `.env` и литералы путей/моделей/токенов в `config.py`; общий лоадер — только `~/.hermes/lib/usertools_env.py` (`setdefault` shared `~/.config/hermes/.env` + optional local `.env`); манифест на диске `schema_version: "0.5.0"` без top-level `config` (required: `schema_version`, `updated_at`, `maintainer`, `tools`, `applications`, `skills`, `entities`, `links`, `conflicts`); SoT секретов уже shared `.env`; SoT LLM уже `~/.hermes/config.yaml`. Исторический раздел `## Контракты экосистемы` (снимок §8) фиксирует выходной `schema_version` как `"0.4.0"` — **не переписывать**.  
`target`: OverlayConfig (Вариант A): required top-level `config` в манифесте (указатель + реестр миграции/отката, не payload значений); несекретный SoT — `EcosystemConfig.yaml` (`shared:` + `tools.<key>:`); схема YAML; единый лоадер `~/.hermes/lib/usertools_config.py` (расширение `usertools_env.py`); каскад dual-read на волнах 0–3; после per-tool приёмки — `migration_status: accepted` → выпил legacy этого tool → `unified_only`; после волны 4 — ветки overlay/legacy вырезаны из лоадера, нет ключа → fail loud. Живой `schema_version` манифеста этого пакета: **`"0.6.0"`** (бамп с факта диска `"0.5.0"`, не с исторического снимка `"0.4.0"`).

### 10.1 Цель модуля

Единый конфиг экосистемы Hermes/USERTOOLS через OverlayConfig (Вариант A): топ-level `config`-указатель в манифесте + несекретный `EcosystemConfig.yaml` (`shared` + `tools.<key>`) с собственной схемой + единый лоадер `usertools_config.py`, чтобы инструменты читали конфиг из одного места вместо разрозненных `.env`/литералов `config.py`.

### 10.2 Артефакты (требования; на `TZ:patch` не создаются)

| Артефакт | Роль |
|---|---|
| `~/WorkVault/Registries/EcosystemManifest.schema.json` | Required top-level `config`. Указатель + реестр миграции/отката, **не** payload значений. Бамп schema **0.5.0 → 0.6.0** (breaking для строгих валидаторов: новый required key при `additionalProperties: false`). |
| `~/WorkVault/Registries/EcosystemManifest.json` | Живой индекс: `schema_version: "0.6.0"` + объект `config`. Пишет `ORCH:shared-state`. |
| `~/WorkVault/Registries/EcosystemConfig.yaml` | SoT несекретных значений: `shared:` + `tools.<key>:`. Ключ `<key>` = ключ `tools{}` манифеста (`fireflies_autojoin`, не имя папки). |
| `~/WorkVault/Registries/EcosystemConfig.schema.json` | Схема YAML (собственный semver, независим от манифеста 0.6.0). Новый ключ в YAML — сначала в схему, иначе дефект. |
| `~/.hermes/lib/usertools_config.py` | Единый лоадер. Расширение `~/.hermes/lib/usertools_env.py`, **не** новый USERTOOL. API: чтение конфига tool, `explain <tool>`, per-tool каскад, `get_llm(tool_key=None)`. |
| `~/.hermes/lib/usertools_env.py` | Существующий env-лоадер. На волнах 0–3 остаётся; слой секретов/legacy идёт через него. После волны 4 ветка local `.env` (`local_env_path`) из боевого каскада уходит. |
| `~/.config/hermes/.env` | SoT секретов (shared `.env`). В YAML не копируются. |
| `~/.hermes/config.yaml` | SoT LLM (`model.default` / `provider` / `custom_providers`). Per-tool override — только секция `tools.<key>.llm` в YAML, не второй Hermes-конфиг. |
| `~/USERTOOLS/<Tool>/config.overlay.yaml` | Временный overlay **только** при `migration_status=dual_read`. После accepted — файла нет. |
| `~/.hermes/_Archives/ecosystem-config/<tool>/<timestamp>.yaml` | Снимок секции YAML для отката после per-tool приёмки. Путь фиксируется в `config.tools.<key>.rollback_snapshot`. |

`config` в манифесте (не значения):

| Поле | Смысл |
|---|---|
| `config.path` | Путь к `EcosystemConfig.yaml` |
| `config.schema_path` | Путь к `EcosystemConfig.schema.json` |
| `config.tools.<key>.enabled` | `true`/`false`; `false` = стоп инструмента без отката данных |
| `config.tools.<key>.migration_status` | `not_started` \| `dual_read` \| `accepted` \| `unified_only` |
| `config.tools.<key>.overlay` | Путь к `config.overlay.yaml` либо `null`; поле живое **только** при `dual_read` |
| `config.tools.<key>.rollback_snapshot` | Путь к архивному YAML либо `null` |

Digest (`render_manifest.py --digest`): путь конфига + счётчики `not_started` / `dual_read` / `accepted` / `unified_only`. **Не** значения ключей. **Не** секреты. **Не** содержимое `.env`.

Владелец индекса — EcosystemIntegration + `ORCH:shared-state`. Запись OverlayConfig как отдельного инструмента в `tools{}` запрещена.

### 10.3 Слои хранения (пять слоёв, не смешивать с семислойным каскадом §10.4)

1. **Индекс экосистемы** — `EcosystemManifest.json` (`config`-указатель, статусы миграции).
2. **Несекретный runtime** — `EcosystemConfig.yaml` (`shared:` + `tools.<key>:`).
3. **Секреты** — shared `~/.config/hermes/.env`.
4. **LLM** — Hermes `~/.hermes/config.yaml`; optional override — `tools.<key>.llm` в YAML.
5. **Бизнес-правила инструмента** (`loop_rules.yaml`, `contract_rules.yaml`, `translit.yaml`) — не инфраструктурный конфиг. В единый YAML **не** переезжают. Волной удаления legacy **не** трогаются.

`config.py` после приёмки **может** остаться тонкой оболочкой: типизированный доступ, сборка `ROUTES` из `entities.json`. Литералы путей / моделей / токенов / дублей env — удаляются. Пустой per-tool `.env` удаляется целиком; уникальные секреты сначала переезжают в shared `.env`.

### 10.4 Каскад чтения (dual-read, волны 0–3, временный)

Побеждает более высокий слой. Ключ, найденный выше, не перекрывается ниже.

| # | Слой | Когда жив |
|---|---|---|
| 1 | Process env, вкл. аварийный `USERTOOLS_CONFIG_MODE=legacy` **только** для этого процесса/инструмента | Волны 0–3; после волны 4 переменная из лоадера вырезана |
| 2 | `~/USERTOOLS/<Tool>/config.overlay.yaml` | Только `migration_status=dual_read` |
| 3 | `tools.<key>` в `EcosystemConfig.yaml` | Всегда после волны 0 |
| 4 | `shared:` в `EcosystemConfig.yaml` | Всегда после волны 0 |
| 5 | LLM: Hermes `config.yaml`, затем optional `tools.<key>.llm` | Всегда |
| 6 | Секреты из shared `.env` | Всегда |
| 7 | Legacy: старый per-tool `.env` / литералы `config.py` | Пока tool не accepted |

**I2 (каскад).** `current` (волны 0–3): семь слоёв, dual-read, YAML побеждает overlay/legacy при равном ключе, кроме process env.  
`target` (после per-tool accepted): слои 2 и 7 **этому** tool запрещены (`explain` → 0 × `source=overlay`/`source=legacy`; нет ключа → fail loud, не «подхватить старое»). После экосистемной приёмки (волна 4) ветки 2 и 7 **удаляются из лоадера**; `USERTOOLS_CONFIG_MODE` больше не читается.

Новый или дорабатываемый инструмент с волны 0 читает лоадер, не плодит `.env`, не пишет пути литералом, стартует сразу `unified_only`. Dual-read — только для ещё не принятых старых.

### 10.5 Откат (per-tool требование)

| Фаза | Как вернуть один инструмент | Соседи |
|---|---|---|
| Dual-read | `USERTOOLS_CONFIG_MODE=legacy` **или** overlay на старые файлы | Не трогать |
| После per-tool приёмки | Старых файлов нет. Restore секции YAML из `~/.hermes/_Archives/ecosystem-config/<tool>/<timestamp>.yaml` по `rollback_snapshot`. `enabled: false` — стоп без отката данных | Не трогать |
| После экосистемной чистки (волна 4) | Архив YAML / правка единого YAML. Веток legacy в коде нет; «как в июне» старыми `.env` восстановить нельзя | — |

### 10.6 Приёмка per-tool → `migration_status: accepted`

Приёмка — **Вариант 1**: только после **явной** реплики Саши по каждому инструменту. Волна 3 (нет своего конфиг-файла) — одна пакетная реплика на список чистых регистраций.

**Привязка `Q-n` (AC-009).** Каждая per-tool приёмка волн 1–2 и каждая пакетная реплика волны 3 формулируется как **отдельный** пронумерованный вопрос `Q-n` на карточке `ORCH:shared-state`, которая пишет `config.tools.<key>` этого tool (волна 3 — одна карточка на список чистых регистраций). `depends: operator:answer:Q-n` сопоставляется 1:1 с этой карточкой/tool и с `config.tools.<key>` (волна 3 — 1:1 с пакетным списком ключей этой реплики). Identity вопроса — пара `(card_id карточки ORCH:shared-state, n)`; `n` уникален на этой карточке (обычно `Q-1` = принять этот tool / этот пакет). Body карточки содержит: `Q-n`, `tool_key: <key>` либо `package_keys: [<key>, …]`, формулировку «принять / не принять». Снятие hold: `operator-done: answer:Q-n` + `evidence:` (ISO + цитата реплики Саши) на `GATE:done` или корне; без этой записи `migration_status` не менять.

Улики (пакет до реплики; без реплики статус не менять, legacy не удалять):

1. `usertools_config explain <tool>`: каждый несекретный ключ `source=ecosystem_config` (или `shared` для унаследованных), секрет `source=shared_env`, **ноль** `source=legacy` / `source=overlay`.
2. Реальный цикл, не dry-run: крон ≥3 подряд успешных тика в обычном окне **или** один полный рабочий день (что раньше); по запросу ≥1 реальный вызов Саши/скилла с ожидаемым результатом. Волна 3: `explain` без недостающих ключей + один реальный вызов, если есть боевой вход.
3. ErrorBus: в окне приёмки нет **новых** событий этого tool про конфиг / env / missing key / YAML parse.
4. Фиксация: `ORCH:shared-state` **после** явной реплики Саши пишет `migration_status: accepted` (затем, после удаления legacy — `unified_only`) и актуальный `rollback_snapshot`.

Удаление legacy-файлов — отдельный императив на уже `accepted` инструмент («работает, удаляй legacy»). Без `depends: operator:удаляй` файлы не сносить.

Экосистема «единый конфиг единственный»: все `active` / `draft` / `paused` в `tools{}` имеют `migration_status: unified_only`; `--check-drift` без дублей путей конфига; из лоадера вырезаны dual-read / legacy / overlay-к-старым; digest показывает `unified_only`.

### 10.7 Волны

Принял инструмент → сразу выпил его legacy → в конце (волна 4) выпил механизм fallback из лоадера.

| Волна | Состав | Статус / файлы |
|---|---|---|
| 0 каркас | Схема `config` в манифесте 0.6.0; `EcosystemConfig.yaml` (`shared:` + ключи tools хотя бы `enabled`); схема YAML; лоадер dual-read + `explain`; все существующие tools — `migration_status: not_started` | Старые `.env` / литералы на месте |
| 1 пилот | `fireflies_autojoin` (FirefliesAutojoin), `move_from_ff` (MoveFromFF), `confluence_sync` (ConfluenceSync), `protocol_from_summary` (ProtocolFromSummary) | Dual-read, YAML побеждает. После приёмки каждого: accepted → удалить его дубли `.env` / литералы в его `config.py` / его overlay → уникальные секреты в shared `.env` → `unified_only` |
| 2 остальные | Остальные USERTOOLS с `.env` / `config.py` | Цикл по одному; удаление строго per-tool после accepted |
| 3 без файла | Инструменты без своего конфиг-файла: регистрация в YAML (часто `enabled` + конвенция logs) | Пакетная реплика Саши на список чистых регистраций |
| 4 единая чистка | Когда последний `active`/`draft`/`paused` = `accepted`/`unified_only` | Вырезать legacy / overlay / `USERTOOLS_CONFIG_MODE` из лоадера; снести осиротевшие пустые `.env` и мёртвые ссылки; `--check-drift` «второй источник = 0»; чеклист `tz-workflow` / `hermes-feature`: новый ключ только в YAML+схеме; литерал / новый `.env` = дефект |

Итог после волны 4: откат только архивом YAML и бэкапом `_Archives`, не старыми `.env`.

### 10.8 Секреты и границы хранения

- Секреты **только** в shared `.env`. В `EcosystemConfig.yaml` / overlay / манифесте / digest — запрещены (схема YAML отклоняет ключи с именами `*TOKEN*` / `*SECRET*` / `*PASSWORD*` / `*API_KEY*` и значения, похожие на секреты, не являются заменой: канон — ключ секрета в YAML отсутствует).
- Бизнес-YAML (`loop_rules.yaml`, `contract_rules.yaml`, `translit.yaml`) в единый конфиг не переезжают и волной удаления не трогаются.
- Инвариант разработки (с волны 0): любой новый/дорабатываемый инструмент читает лоадер, не плодит `.env`, не пишет пути литералом. Dual-read — только для не принятых старых. После `unified_only` возврат литералов = регресс.

Модуль 1 (FF-самаризатор, IDEA `t_609e8869`) в этот пакет не входит. Будущий потребитель: `get_llm("ff_summarizer")` — default Hermes `config.yaml`, override только `tools.ff_summarizer.llm` или process env.

### 10.9 Что НЕ трогать (модуль 0)

- Исторические §§1–9 и исторический `## Контракты экосистемы` (снимок `schema_version` `"0.4.0"`). Норма живого манифеста этого пакета — §10 / `"0.6.0"`.
- `MAIN_TZ_INVENTORY.md` — фаза `TZ:finalize`, не эта запись.
- Новый ключ в `tools{}` под OverlayConfig / `usertools_config` — не заводить.
- Бизнес-YAML инструментов (`loop_rules.yaml`, `contract_rules.yaml`, `translit.yaml`) — не переносить, не удалять волнами 1–4.
- `entities.json` / `entities.schema.json` — не менять ради модуля 0 (тонкая оболочка `config.py` может **читать** `entities.json` для `ROUTES`).
- Gateway Hermes — не рестартовать. Кроны — не создавать автоматически (только по «ставь кроны»).
- Содержимое master-ТЗ других инструментов — не переписывать; пилоты волны 1 меняют свой runtime-конфиг в `HF:impl` своих графов / хвоста этого эпика, не «заодно» чужой master-файл.
- Модуль 1 (FF-самаризатор) и IDEA `t_609e8869` — вне скоупа.
- Ядро `~/hermes-agent`, `jobs.json` (кроме будущего явного «ставь кроны»), секреты в git/YAML.

### 10.10 Связи с экосистемой

| Кто | Связь |
|---|---|
| EcosystemIntegration | Владелец манифеста и `config`-указателя; `render_manifest.py --digest` / `--check-drift` |
| `ORCH:shared-state` | Пишет `schema_version`, `config.tools.<key>.*`, не пишет секреты |
| `usertools_env.py` | База лоадера; не заменяется новым USERTOOL |
| Все USERTOOLS (`tools{}` digest: 46) | Потребители `usertools_config.py`; волна 1 = четыре пилота выше |
| ErrorBus | Улика приёмки: тишина событий конфиг/env/missing key/YAML parse |
| `tz-workflow`, `hermes-feature` | С волны 4 (чеклист с волны 0 как инвариант): новый ключ только YAML+схема; литерал / новый `.env` = дефект |
| Hermes `config.yaml` | SoT LLM |
| `~/.config/hermes/.env` | SoT секретов |
| `entities.json` | Только чтение тонкой оболочкой `config.py` (ROUTES); не слой OverlayConfig |
| IDEA `t_609e8869` | Будущий модуль 1; `get_llm("ff_summarizer")` — контракт лоадера, реализация не в этом пакете |

Reuse-first: новый USERTOOL не предлагается; расширяется существующий `~/.hermes/lib/usertools_env.py`. Файлы YAML/схема в `Registries/` — артефакты индекса, согласованы брифом 2026-09-30, не новые сущности vault.

### 10.11 Волна 1 — пилоты dual_read

Конкретизация строки «1 пилот» таблицы §10.7. Каскад, откат, per-tool приёмка и тексты AC **не** дублируются: норматив — §10.4 / §10.5 / §10.6 и якоря AC-007…AC-014, AC-017, AC-019. Этот подраздел задаёт состав, переход, поштучную приёмку и критерий готовности волны.

#### 10.11.1 Состав (ровно 4 ключа)

Ключ = ключ `tools{}` манифеста, не имя папки USERTOOLS и не имя master-ТЗ.

| # | `tool_key` | Инструмент (имя из инвентаря) |
|---|---|---|
| 1 | `fireflies_autojoin` | FirefliesAutojoin |
| 2 | `move_from_ff` | MoveFromFF |
| 3 | `confluence_sync` | ConfluenceSync |
| 4 | `protocol_from_summary` | ProtocolFromSummary |

Состав волны 1 **закрыт**. Не расширять, не подменять ключи, не добавлять пятый пилот.

Digest (`tools=46`): 4 пилота + остальные 42. Волна 1 проверяет каскад dual-read **только** на этих четырёх; остальные 42 на `dual_read` не переводятся.

#### 10.11.2 Цель

Проверить семислойный каскад dual-read (§10.4) на четырёх боевых инструментах: YAML побеждает overlay/legacy на совпадающем ключе; соседи из 42 не меняют `migration_status` и не получают overlay/правки `.env`/`config.py` «заодно».

#### 10.11.3 Переход каждого пилота на `dual_read`

Для каждого `tool_key` из §10.11.1 — **по одному**, не пакетом на всех четырёх:

1. Включить лоадер `usertools_config` (слои каскада §10.4). Новый per-tool `.env` не плодить.
2. Перенести несекретные литералы и дубли env из per-tool `.env` / `config.py` в `EcosystemConfig.yaml`: блок `tools.<key>:` и при необходимости `shared:`. Новый ключ — сначала в `EcosystemConfig.schema.json` (§10.2), иначе дефект.
3. Секреты — только в shared `~/.config/hermes/.env`. В YAML / overlay / манифест / digest не копировать (§10.8). Уникальные секреты пилота **переносятся** в shared `.env` (не дублируются в YAML), чтобы `explain` видел `source=shared_env`. Сам per-tool `.env` на этом шаге не удаляется — снос файла только после `accepted` и императива «удаляй» (§10.11.4).
4. Карточка `ORCH:shared-state` пишет `config.tools.<key>.migration_status: dual_read` (и путь overlay, пока overlay жив). YAML побеждает overlay и legacy на совпадающем ключе (AC-007).
5. Соседние 42 ключа остаются в своём статусе вне волны 1 (на старте волны — `not_started`); их `.env` / `config.py` / overlay не трогать.

#### 10.11.4 Поштучная приёмка (AC-008 → AC-009)

Приёмка — **Вариант 1** (§10.6): `migration_status: accepted` только после **явной** реплики Саши по этому пилоту. Без реплики статус не менять, legacy не удалять. Зелёный пакет улик ≠ акцепт.

**Пакет улик AC-008** (собирается **до** вопроса Саше; без пакета `Q-n` на приёмку не ставить):

| # | Улика | Наблюдаемо |
|---|---|---|
| (a) | `usertools_config explain <tool>` | каждый несекретный ключ `source=ecosystem_config` (или `shared` для унаследованных из `shared:`); секрет `source=shared_env`; **ноль** `source=legacy` / `source=overlay` |
| (b) | Боевой цикл, не dry-run | ≥3 подряд успешных тика крона в обычном окне **или** один полный рабочий день (что раньше) |
| (c) | ErrorBus | в окне приёмки нет **новых** событий этого tool про конфиг / env / missing key / YAML parse |

Артефакт пакета: вывод `explain` + ссылки на `job_id` / логи крона.

**Связка `Q-n` (AC-009), 1:1 на пилот:**

- Каждая per-tool приёмка = отдельный пронумерованный вопрос `Q-n` на карточке `ORCH:shared-state` **этого** пилота (карточка пишет `config.tools.<key>`). Четыре пилота → четыре карточки / четыре `Q-n`, не один пакетный вопрос на всех.
- Body карточки содержит: `Q-n` + `tool_key: <key>` + формулировку «принять / не принять».
- `depends: operator:answer:Q-n` сопоставляется 1:1 с этой карточкой и `config.tools.<key>`. Identity вопроса — пара `(card_id карточки ORCH:shared-state, n)`; `n` уникален на этой карточке (обычно `Q-1` = принять этот tool).
- Снятие hold: `operator-done: answer:Q-n` + `evidence:` (ISO + цитата реплики Саши) на `GATE:done` или корне. Фраза без evidence ≠ `operator-done`. Без этой записи `migration_status` не менять.
- Не писать `accepted` по умолчанию, по тишине, по «пакет улик зелёный» или по реплике на соседний пилот (AC-009).

**После реплики «принять» (AC-010):** карточка `ORCH:shared-state` пишет `config.tools.<key>.migration_status: accepted` и `rollback_snapshot` на `~/.hermes/_Archives/ecosystem-config/<tool>/<timestamp>.yaml`. Соседей не трогать.

**Выпил legacy (AC-011 / AC-012) — отдельный императив.** На уже `accepted` пилот нужна явная фраза Саши «работает, удаляй legacy». После неё: удалить дубли per-tool `.env`, литералы путей/моделей/токенов/дублей env в его `config.py`, его overlay; уникальные секреты к этому моменту уже в shared `.env`; затем `unified_only`. Без `depends: operator:удаляй` файлы не сносить. После `accepted` слои 2 и 7 **этому** tool запрещены (`explain` → 0 × `source=overlay` / `source=legacy`; нет ключа → fail loud, не silent fallback).

#### 10.11.5 Откат волны 1

Норматив §10.5; здесь — привязка к пилотам:

| Фаза пилота | Как вернуть этот tool | Соседи |
|---|---|---|
| `dual_read` | `USERTOOLS_CONFIG_MODE=legacy` **или** overlay на старые файлы (AC-013) | Не меняются: `explain` соседа без этой переменной тот же |
| После `accepted` | Restore секции YAML из `rollback_snapshot` (AC-014). Ветки чтения старого `.env` для него нет | Не меняются |

`enabled: false` — стоп этого tool без отката данных (§10.5).

#### 10.11.6 Что НЕ делать в волне 1

- Не переводить остальные 42 инструмента на `dual_read`.
- Не трогать бизнес-YAML пилотов (`loop_rules.yaml`, `contract_rules.yaml`, `translit.yaml` и т.п.) — AC-019; пути на диске, если были, сохраняются.
- Не менять содержимое чужих master-ТЗ (пилоты меняют runtime-конфиг в `HF:impl` своих графов / хвоста этого эпика, не «заодно» чужой master-файл).
- Не выпиливать механизм fallback из лоадера (слои 2/7, `USERTOOLS_CONFIG_MODE`) — это волна 4, AC-015 / AC-016.
- Не писать `accepted` / `unified_only` без явной реплики Саши и без `operator-done: answer:Q-n` + evidence (AC-009).
- Не сносить legacy-файлы без императива «удаляй» (AC-011).
- Не копировать секреты в YAML / overlay / манифест / digest (§10.8).
- Не заводить OverlayConfig как ключ `tools{}`.
- Не создавать кроны автоматически; Gateway не рестартовать.

#### 10.11.7 Критерий готовности волны 1

Волна 1 **готова к поштучной приёмке Саши**, когда одновременно:

1. Четыре пилота в `config.tools.<key>.migration_status = dual_read` для `fireflies_autojoin`, `move_from_ff`, `confluence_sync`, `protocol_from_summary`; YAML побеждает overlay/legacy на совпадающем ключе (AC-007).
2. По каждому пилоту собран пакет улик AC-008.
3. На каждую карточку `ORCH:shared-state` пилота заведён `Q-n` (body: `Q-n` + `tool_key: <key>` + «принять / не принять») с `depends: operator:answer:Q-n`.
4. `render_manifest.py --check-drift` без новых дублей SoT конфига (AC-017).

`accepted` / `unified_only` **не** входят в критерий готовности волны 1: они закрываются поштучно после реплики (AC-009…AC-012) и не держат перевод остальных пилотов на `dual_read`.

### 10.12 Системный класс battle-interpreters (v0.7.0)

Утверждено требованием оператора 13.10.2026 (граф `DEV/anywhere-contacts`, кейс BUGFIX полный). Продолжение модуля 0 OverlayConfig: тот же лоадер `usertools_config.py` и те же волны §10.7, **другой** инвариант — какой **python реально исполняет** инструмент. Источник диагноза: `_fix_plan_20261013.md` (AnywhereContacts) + материнский `GATE:diagnose-review`. Код, environment, манифест JSON/YAML значений — **не** эта запись (`TZ:patch`); артефакты реестра/probe — `HF:impl` / `HF:test`.

Третий инструмент того же класса после MoveFromFF (PyYAML) и FirefliesAutojoin (PyYAML): верификация eco-config (`HF:test`) зелёная на per-tool venv, боевой вход (скилл/крон/wrapper) идёт другим python. Root cause AC-002 (диск 13.10): `show-contacts` делает `from anywhere_contacts import ...` в рантайме Hermes (`hermes-agent/.venv`, Python **3.14.5**), где нет `loguru`; `anywhere_contacts/logger.py:9` падает; per-tool `.venv`/`venv_linux` (3.11.13) импортируют пакет успешно. Системный `python3` 3.9.25 — не боевой.

**I1 (боевой интерпретатор, локальный маркер §10.12).** Не заменяет I1 overlay-артефактов и I2 каскада в начале §10.  
`current`: `HF:test` волн eco-config гоняет pytest / CLI под per-tool venv или PFS `.venv`; скилл/крон с `#!/usr/bin/env python3` исполняется интерпретатором Hermes 3.14 (или системным env), в котором нет объявленных пакетов инструмента (`loguru` / `pydantic` / `yaml`); карта 16 ключей волн 1–2 есть в диагнозе, построчное подтверждение closure на диске — не закрыто; чеклиста `hermes-feature` на этот AC нет.  
`target`: у каждого ключа волн 0–4 задокументирован и проверен **боевой python** = closure реального входа (крон / wrapper / skill / shebang → `sys.executable` процесса, который импортирует tool); в **нём** `import yaml`, `import usertools_config` и зависящие от объявленных (`pydantic`/`loguru`/…); реестр `battle_interpreters.yaml` + `probe_battle_venv.py` — обязательный AC `HF:test` **любой** волны eco-config; pytest в PFS/hermes этот AC **не** закрывает; пакеты ставятся только в фактический боевой venv ключа, не слепо во все и не в `hermes-agent`.

#### 10.12.1 Инвариант «боевой интерпретатор»

**Боевой интерпретатор** ключа `tools{}` — бинарник python, которым **реально** идёт вход:

| Вид входа | Closure (как снять `sys.executable`) |
|---|---|
| крон `jobs.json` `script=*.py` | wrapper `.sh`, иначе Hermes `project_python` (канон MFL §15/§16: shebang `env python3` у `.py` **не** действует) |
| wrapper `~/.hermes/scripts/*.sh` | `exec` внутри скрипта |
| скилл Hermes | subprocess на бинарник tool; **запрещён** in-process `from <pkg> import` в рантайме Hermes |
| CLI / shebang | тот же бинарник, что в shebang после резолва, не «удобный» venv из плана теста |

Проверки, которые **не** закрывают инвариант: `pytest` в дереве инструмента; `pytest` в PFS; импорт под `.venv` при боевом входе через другой python; `explain` под чужим интерпретатором.

#### 10.12.2 Карта 16 ключей (волны 1–2, факт диска 13.10)

Ключ = `tools{}` манифеста. Волна 1 = 4 пилота §10.11.1. Волна 2 = **ровно 12**: `anywhere_contacts`, `contract_assistant`, `exchange_monitor`, `loop_channel_digest`, `mark_objects_from_summary`, `move_from_jira`, `move_from_loop`, `move_from_zulip`, `obsidian_from_confluence`, `proxy_check_linux`, `srtool`, `task_refresh`. Состав закрыт.

Построчное подтверждение на диске (venv/wrapper 13.10) + норматив действия. `HF:test` **обязан** подтвердить каждую из 16 строк заново: closure входа, боевой python, импорты. Отсутствие дыры у ключа = строка PASS, не skip ключа. Та же ошибка класса (боевой интерпретатор / closure / пакет не в том venv) проверяется **во всех 12** волны 2.

| # | `tool_key` | Волна | Venv на диске 13.10 | Боевой python (target) | Вход / closure | Действие |
|---|---|---|---|---|---|---|
| 1 | `fireflies_autojoin` | 1 | `FirefliesAutojoin/venv_linux` | этот `venv_linux` | `run.sh` / крон FF | yaml есть; pydantic **не** ставить на путь FF, если боевой модуль его не импортирует |
| 2 | `move_from_ff` | 1 | `MoveFromFF/.venv` | этот `.venv` | крон/CLI MFF | yaml OK; loguru — если logger на cron/CLI |
| 3 | `confluence_sync` | 1 | `ConfluenceSync/.venv` | этот `.venv` | крон/CLI | yaml OK; loguru — если logger на cron/CLI |
| 4 | `protocol_from_summary` | 1 | `ProtocolFromSummary/.venv` | этот `.venv` | крон/CLI PFS | yaml OK; loguru — если logger на cron/CLI |
| 5 | `anywhere_contacts` | 2 | `.venv` + `venv_linux` (оба 3.11.13, import OK) | **должен** `AnywhereContacts/venv_linux`; **факт 13.10** `hermes-agent/.venv` 3.14.5 | скилл `show-contacts`: in-process import | скилл **только** через этот бинарь (subprocess); in-process в Hermes запрещён |
| 6 | `contract_assistant` | 2 | `ContractAssistant/venv_linux` | этот `venv_linux` | факт: `~/.hermes/scripts/ca_watch.py` shebang `#!/usr/bin/env python3` | слой B: wrapper → `venv_linux` (канон MFL) |
| 7 | `exchange_monitor` | 2 | **своего venv нет** | `MoveFromLoop/venv_linux` | urgent/digest уже через `mfl_*_cron.sh` | отдельный venv **не** заводить |
| 8 | `loop_channel_digest` | 2 | `LoopChannelDigest/venv_linux` | этот `venv_linux` | крон/CLI | declare в pyproject **и** `uv sync` в этот venv |
| 9 | `mark_objects_from_summary` | 2 | `MarkObjectsFromSummary/.venv` | этот `.venv` | крон/CLI | declare **и** sync в этот venv |
| 10 | `move_from_jira` | 2 | `MoveFromJira/venv_linux` | этот `venv_linux` | крон/CLI | declare **и** sync в этот venv |
| 11 | `move_from_loop` | 2 | `MoveFromLoop/venv_linux` | этот `venv_linux` | wrappers `mfl_urgent_check_cron.sh` / `mfl_digest_cron.sh` | канон MFL уже есть; extras — declare **и** sync сюда |
| 12 | `move_from_zulip` | 2 | `.venv` + `venv_linux` | `venv_linux` (канон Zulip) | крон/CLI | declare **и** sync в боевой, не в соседний |
| 13 | `obsidian_from_confluence` | 2 | каталога `USERTOOLS/ObsidianFromConfluence` **нет** | `ProtocolFromSummary/.venv` | `~/.hermes/scripts/ofc_sync.sh` | режим PFS; свой venv OFC не заводить |
| 14 | `proxy_check_linux` | 2 | venv в `proxycheck/linux-agent` **нет** | python closure реального входа агента (каталог `~/USERTOOLS/proxycheck/linux-agent/`) | CLI/agent shebang | PyYAML уже в `requirements.txt`; install **в тот** python; чужой venv не заводить |
| 15 | `srtool` | 2 | `SRTool/.venv` | этот `.venv` | крон/CLI | declare **и** sync в этот venv |
| 16 | `task_refresh` | 2 | своего venv **нет** | `ProtocolFromSummary/.venv` | `~/USERTOOLS/TaskRefresh/tr` | режим PFS; `tr` уже `exec` PFS python |

#### 10.12.3 Слои фикса (A / B)

Фикс — **по фактическому боевому интерпретатору** ключа. Запрещено: «поставить пакет слепо во все venv»; ставить пакеты в `hermes-agent/.venv`.

**Слой B (вход).** Скрипты `~/.hermes/scripts/*.py` с `#!/usr/bin/env python3`, которые импортируют USERTOOLS (`ca_watch.py` и прочие того же класса): обёртка `.sh` → `venv` инструмента (канон MFL: `mfl_urgent_check_cron.sh` / `mfl_digest_cron.sh`). Скилл, который сейчас импортирует пакет in-process в Hermes (`show-contacts` → `anywhere_contacts`): только subprocess на боевой бинарник. Пакеты в hermes-agent **не** ставить: управляемый venv Hermes — исполнитель крона/агента, не venv инструмента. Гибрид «процесс 3.14 + site-packages 3.11» недопустим.

**Слой A (зависимости).** Где боевой модуль **реально** импортирует `pydantic` / `loguru` / `yaml` / иное: строка в `requirements.txt` или `pyproject.toml` **и** install (`uv sync` / pip) **в этот** боевой venv. Declare без sync = дыра класса `pfs-anywhere-contacts-dep`. Пакет, которого модуль не импортирует, в venv не добавлять «на всякий случай».

После слоя B боевой python ключа — venv инструмента (или явно разделяемый, как PFS для OFC/TaskRefresh и MFL для ExchangeMonitor). Слой A ставит пакеты туда.

#### 10.12.4 Реестр `battle_interpreters.yaml` + `probe_battle_venv.py`

Артефакты (латиница; на `TZ:patch` **не** создаются; новый ключ `tools{}` под них **не** заводить):

| Артефакт | Роль |
|---|---|
| `~/WorkVault/Registries/battle_interpreters.yaml` | Реестр: на каждый ключ волн 1–4 — `battle_python` (abs), `entry_kind` (`cron` / `wrapper` / `skill` / `shebang`), `entry` (job_id / путь wrapper / имя скилла / CLI), `wave`, `declared_imports` (то, что боевой модуль реально импортирует сверх `yaml` и `usertools_config`). Не секреты. Не payload OverlayConfig. |
| `~/.hermes/lib/probe_battle_venv.py` | Probe: для каждого ключа реестра запускает **боевой** python; в нём `import yaml`, `import usertools_config`, импорты из `declared_imports`; сверяет closure входа (`sys.executable` реального входа = `battle_python`). Строка FAIL → **exit 1**. Без ключа в реестре при живом входе волны = FAIL. |

Reuse-first: расширение индекса в `Registries/` + скрипт рядом с `usertools_config.py`. Не USERTOOL, не сущность vault.

#### 10.12.5 Обязательный probe-AC в плане разработки и тестирования всех волн (w1, w2, w3, w4)

Норматив **сразу** для `HF:plan` / `HF:test` каждой волны eco-config, не «добавить задним числом» на w3/w4. Исторический §10.11 (dual_read пилотов) **не** переписывается: probe — **дополнительный** AC, не замена AC-007…AC-014.

Для **каждого** ключа волны в `HF:plan` фиксируется строка IAC:

| Поле IAC | Содержание |
|---|---|
| `path` | боевой python + вход (wrapper/скилл/крон/shebang) |
| `verify` | `probe_battle_venv.py` PASS по этому ключу: `import yaml` + `import usertools_config` + declared; closure = этот python; разовый реальный вход той же командой + `usertools_config explain <tool>` **тем же** python |
| `covers` | AC-B01 и AC волны (w1: пилоты; w2: 12 ключей; w3/w4: ключи той волны) |

**pytest в PFS / hermes / per-tool venv этот AC не закрывает.** Зелёный pytest без PASS probe = `HF:test` FAIL.

**Волна 1.** Четыре пилота §10.11.1: тот же probe-AC на их боевом python (таблица §10.12.2). Пакет улик AC-008 собирается `explain`-ом **тем же** python. Поштучный `Q-n` AC-009 пилота — после PASS probe этого ключа.

**Волна 2.** Все 12 ключей. Критерий **выхода** волны 2 (AC-B07): все 12 подтверждены на своём боевом python (closure), probe зелёный по каждому. **Только после этого** Саша рассматривает приёмку AC-009 по инструментам волны 2. Карточку `ORCH:shared-state` с `Q-n` «принять / не принять» на ключ волны 2 **не** заводить, пока AC-B07 не зелёный. AC-009 (класс O, `depends: operator:answer:Q-n`) не меняется.

**Волны 3 и 4.** В `HF:plan` волны 3 (нет конфиг-файла) и волны 4 (вырез fallback) probe-AC входит **с первого драфта** плана, на каждый ключ волны. Волна 3: даже «чистая регистрация» `enabled` + конвенция logs имеет боевой вход, если он есть — probe по нему; нет боевого входа — строка реестра `entry_kind` + явное «входа нет», probe всё равно гоняет `import yaml` / `usertools_config` на python, которым инструмент вызвали бы. Волна 4: после выреза слоёв 2/7 лоадера probe повторяется на тех же боевых python (регресс «пакет был только в legacy-пути»).

#### 10.12.6 Реальный вход (разово, не dry-run)

На ключ с боевым входом: та же команда крона или CLI **тем же** shebang/wrapper, что в проде, плюс `usertools_config explain <tool>` тем же python. Смоук `HF:test` под другим интерпретатором не зачёт.

Якорь живого поиска (AC-B08): `show-contacts` через `AnywhereContacts/venv_linux/bin/python` находит «Федотова Андрей» **или** честно «не найден из enc» (без `ModuleNotFoundError`). В отчёт — found/not-found, без дампа полей enc.

#### 10.12.7 Связи с экосистемой

| Кто | Связь |
|---|---|
| EcosystemIntegration §10 | Владелец инварианта и AC-B*; overlay-каскад без изменений |
| `hermes-feature` | Чеклист `HF:test`: probe обязателен на любой волне eco-config |
| `tz-workflow` | Не плодить литерал интерпретатора / новый `.env`; dual-read не для новых tools |
| MoveFromLoop §15/§16 | Канон wrapper → `venv_linux`; слой B копирует **этот** паттерн, не гибрид sys.path |
| AnywhereContacts / `show-contacts` | Представитель класса; слой B для скилла |
| ProtocolFromSummary `.venv` | Боевой python `task_refresh` и `obsidian_from_confluence` |
| ExchangeMonitor | Боевой python = MFL `venv_linux`; свой venv не заводить |
| `usertools_config.py` | Импорт yaml на боевом python; `explain` тем же бинарником |
| ErrorBus | Негатив: `ModuleNotFoundError` на боевом входе = событие конфиг/import |

Reuse-first: новый USERTOOL / новая сущность vault не предлагаются. Реестр — файл в `Registries/`, probe — `~/.hermes/lib/`.

#### 10.12.8 Что НЕ трогать

- Исторические §§1–9 и исторический H2 `## Контракты экосистемы` (снимок `"0.4.0"`).
- Тексты AC-001…AC-020 и §10.11 (dual_read пилотов) — не ретрофит; probe дополняет.
- Ядро `~/hermes-agent` (в т.ч. `scheduler_script.py`, пересборка `.venv` Hermes «чтобы поставить loguru»).
- Пакеты в `hermes-agent/.venv` / «pip во все venv».
- Новый ключ `tools{}` под OverlayConfig / probe / реестр интерпретаторов.
- Свой venv для `exchange_monitor`, `obsidian_from_confluence`, `task_refresh`.
- Бизнес-YAML; `entities.json`; Gateway; авто-кроны.
- Содержимое чужих master-ТЗ «заодно» (секция AnywhereContacts — отдельная запись, не этот файл).
- Слаг графа `DEV/anywhere-contacts`; merge в blocked `eco-config-w2`; reopen archived `pfs-anywhere-contacts-dep`.
- Модуль 1 / IDEA `t_609e8869`.

#### Контракты экосистемы (дополнение модуля 0: battle-interpreters)

Не ретрофит исторического H2. Потребители probe читают этот блок; overlay-контракт выше остаётся SoT `config` / YAML значений.

##### Источник истины
- Владелец реестра боевых интерпретаторов: EcosystemIntegration (`~/WorkVault/Registries/battle_interpreters.yaml`)
- Владелец probe: EcosystemIntegration (`~/.hermes/lib/probe_battle_venv.py`)
- Владелец боевого venv ключа: каталог USERTOOLS / разделяемый venv по таблице §10.12.2, не hermes-agent

##### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| tools.<key>.battle_python | str | required | battle_interpreters.yaml | abs-путь бинарника python |
| tools.<key>.entry_kind | enum[cron, wrapper, skill, shebang] | required | battle_interpreters.yaml | вид реального входа |
| tools.<key>.entry | str | required | battle_interpreters.yaml | job_id / путь / имя скилла / CLI |
| tools.<key>.wave | enum[1, 2, 3, 4] | required | battle_interpreters.yaml | волна eco-config |
| tools.<key>.declared_imports | str | optional | pyproject/requirements + код модуля | имена модулей через запятую; только реальный import |

##### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| probe.exit | int | HF:test любой волны eco-config | 0=все ключи PASS; 1=есть FAIL |
| probe.row | str | HF:test, GATE:done | "<key> PASS\|FAIL" на каждый ключ реестра |
| battle_python | str | слой A/B, explain | abs; совпадает с sys.executable closure |

##### Зависимости
- Получает от: [USERTOOLS/<Tool> venv, ~/.hermes/scripts wrappers, скиллы входа, usertools_config.py]
- Отдаёт: [HF:test волн eco-config, hermes-feature чеклист, AC-009 (гейт: не ставить Q-n волны 2 до PASS)]

##### Breaking changes policy
- Semver в `schema_version` YAML реестра (независимо от манифеста `"0.6.0"`).
- Смена `battle_python` ключа = правка реестра + повтор probe; молчаливая подмена интерпретатора в тесте = дефект.

##### Границы («что НЕ трогать»)
- Не ставить пакеты в hermes-agent
- Не заводить реестр как `tools{}`
- Не закрывать probe pytest-ом PFS/hermes

#### Критерии приёмки (AC)

Только пакет системного класса battle-interpreters (`DEV/anywhere-contacts`, §10.12). Наблюдаемое: команда или артефакт на диске. **Класс S** (показ ≠ ожидание). Нет новых `depends: operator:` — гейт приёмки волны 2 к AC-009 остаётся существующим `depends: operator:answer:Q-n` на AC-009. Payload `GATE:take-into-work` этого слага. Код/скилл закрывают AC на `HF:impl` / `HF:test`; эта запись фиксирует канон.

#### AC-B01 — probe зелёный на боевом входе всех 16

`python3 ~/.hermes/lib/probe_battle_venv.py` (или эквивалент тем же файлом) exit 0. В выводе PASS по всем 16 ключам §10.12.2. Каждый PASS = import `yaml` + `usertools_config` + `declared_imports` **боевым** python ключа и совпадение closure входа с `battle_python`. Один FAIL → exit 1. Pytest PFS/hermes / импорт под не-боевым venv **не** засчитывается.

#### AC-B02 — инвариант в ТЗ и чеклист `hermes-feature`

В §10.12 есть I1 `current`/`target` инварианта «боевой интерпретатор» и карта 16 ключей без строки «остальные». В `hermes-feature` (чеклист Блока 3 / фазы `HF:test`) есть пункт: «волна eco-config (w1–w4): `probe_battle_venv.py` PASS на боевом python каждого ключа волны; pytest PFS/hermes этот AC не закрывает». Наблюдаемо: `rg` в `SKILL.md` скилла.

#### AC-B03 — построчное подтверждение 12 ключей волны 2 на диске

`HF:test` волны 2 (и probe этого графа) для каждого из 12 ключей §10.12.2 фиксирует: путь боевого python, вид входа, результат `import yaml` / `usertools_config` / declared. Класс ошибки (боевой интерпретатор / closure / пакет не в том venv) проверен на всех 12. Ключ без дыры = PASS, не исключение из карты.

#### AC-B04 — слой B: wrapper на venv инструмента, не пакеты в hermes-agent

`ca_watch` и прочие `~/.hermes/scripts/*.py` с `env python3`, импортирующие USERTOOLS, исполняются через `.sh`-wrapper на venv инструмента (паритет MFL). `show-contacts` не делает in-process import в python Hermes. `rg` по `hermes-agent` requirements/pyproject: новые строки `loguru`/`pydantic`/`PyYAML` «ради USERTOOLS» отсутствуют. Наблюдаемо: `sys.executable` прогона wrapper/скилла указывает в venv инструмента.

#### AC-B05 — слой A: declare и sync в тот же боевой venv

Если боевой модуль импортирует `pydantic`/`loguru`/`yaml`/иное — строка есть в `pyproject.toml` или `requirements.txt` **и** пакет установлен в боевой venv этого ключа (`uv sync` / pip). Declare без install в этом venv = FAIL (дыра `pfs-anywhere-contacts-dep`). Пакет не ставится в соседние venv «оптом».

#### AC-B06 — probe-AC в `HF:plan` всех волн eco-config с старта

Планы разработки **и** тестирования волн w1, w2, w3, w4 содержат IAC probe (§10.12.5) в первом драфте, не поздней вставкой. На каждый ключ волны: боевой python = closure входа; в нём yaml + usertools_config + declared. Волна без строки probe в плане = дефект `HF:plan`.

#### AC-B07 — выход волны 2 до рассмотрения AC-009

Все 12 ключей волны 2: closure подтверждён, probe PASS. Только после этого оркестратор ставит `Q-n` AC-009 на приёмку ключей волны 2. Наблюдаемо: нет карточки `ORCH:shared-state` волны 2 с `Q-n` «принять», пока AC-B01/AC-B03 по 12 ключам не PASS; `migration_status` волны 2 не `accepted` раньше этого.

#### AC-B08 — живой поиск «Федотова Андрей» через `venv_linux`

Команда поиска контактов исполняется `~/USERTOOLS/AnywhereContacts/venv_linux/bin/python` (не python Hermes). Результат: контакт найден **или** честно «не найден из enc». Нет `ModuleNotFoundError` (`loguru` / `pydantic_core` / `yaml`). В отчёт — found/not-found, без полей enc.

### Контракты экосистемы (модуль 0: config-указатель и лоадер)

Норматив **этого пакета**. Исторический H2 `## Контракты экосистемы` (после §8) — снимок формата v0.4.0, его таблицы не менять. Потребители модуля 0 читают контракт ниже и `schema_version: "0.6.0"`, не строку `"0.4.0"` исторического блока.

#### Источник истины
- Владелец указателя: EcosystemIntegration (`EcosystemManifest.json` → `config`)
- Владелец несекретных значений: EcosystemIntegration (`EcosystemConfig.yaml`)
- Владелец секретов: shared `~/.config/hermes/.env` (не манифест)
- Владелец LLM-дефолта: Hermes `~/.hermes/config.yaml`
- Писатель индекса статусов: `ORCH:shared-state`

#### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| config.path | str | required | EcosystemIntegration (манифест) | путь к EcosystemConfig.yaml (`~/WorkVault/Registries/EcosystemConfig.yaml`) |
| config.schema_path | str | required | EcosystemIntegration (манифест) | путь к EcosystemConfig.schema.json |
| config.tools.<key>.enabled | bool | required | ORCH:shared-state | true=работать, false=стоп без отката данных |
| config.tools.<key>.migration_status | enum[not_started, dual_read, accepted, unified_only] | required | ORCH:shared-state | per-tool; ключ = tools{} |
| config.tools.<key>.overlay | str | optional | ORCH:shared-state | путь overlay; только dual_read, иначе null |
| config.tools.<key>.rollback_snapshot | str | optional | ORCH:shared-state | путь ~/.hermes/_Archives/ecosystem-config/<tool>/<timestamp>.yaml |
| USERTOOLS_CONFIG_MODE | enum[legacy] | optional | process env | только dual_read и только этот процесс; после волны 4 отсутствует |
| tools.<key>.* | str | optional | EcosystemConfig.yaml | несекретные значения; ключ сначала в EcosystemConfig.schema.json |
| shared.* | str | optional | EcosystemConfig.yaml | несекретные общие пути/флаги |
| tools.<key>.llm | str | optional | EcosystemConfig.yaml | per-tool override LLM; дефолт не дублировать |
| SECRET keys | str | optional | ~/.config/hermes/.env | только .env; в YAML запрещены |

#### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| schema_version | str | tz-workflow, hermes-feature, render_manifest | живой канон пакета `"0.6.0"` (не исторический снимок `"0.4.0"`) |
| config.path | str | render_manifest --digest, usertools_config | путь; без значений и секретов |
| config.status_counts | str | render_manifest --digest | счётчики not_started/dual_read/accepted/unified_only |
| explain[].key | str | приёмка per-tool, Саша | имя ключа |
| explain[].source | enum[process_env, overlay, ecosystem_config, shared, hermes_llm, tool_llm, shared_env, legacy] | приёмка per-tool | после accepted запрещены overlay и legacy |
| resolved config | str | USERTOOLS через usertools_config.py | каскад §10.4; missing key после accepted/волны 4 = fail loud |

#### Зависимости
- Получает от: [usertools_env.py, Hermes config.yaml, ~/.config/hermes/.env, USERTOOLS/<Tool> overlay (временно), entities.json (только ROUTES в тонкой оболочке)]
- Отдаёт: [все USERTOOLS, render_manifest, tz-workflow, hermes-feature, ErrorBus (негатив: события конфига), будущий get_llm(ff_summarizer)]

#### Breaking changes policy
- Версионирование манифеста: semver в `EcosystemManifest.json` `schema_version`. Факт диска до пакета: `"0.5.0"`. Этот пакет: `"0.6.0"` (required `config`). Историческая строка `"0.4.0"` в H2-контрактах — архив §8, не SoT.
- Версионирование YAML: semver в `EcosystemConfig.schema.json` / поле `schema_version` YAML; независим от манифеста.
- Вырезание слоёв 2 и 7 из лоадера — breaking API лоадера, только волна 4 после `unified_only` на всех `active`/`draft`/`paused`.
- При breaking: бамп соответствующей schema, `migrate` потребителей из «Отдаёт», `--check-drift` exit 0.

#### Границы («что НЕ трогать»)
- Не класть секреты в YAML / манифест / digest
- Не заводить OverlayConfig как `tools{}`
- Не переносить бизнес-YAML в EcosystemConfig.yaml
- Не переписывать исторический H2 `## Контракты экосистемы`

### Критерии приёмки (AC)

Только пакет модуля 0 (`DEV/eco-config`, OverlayConfig). Наблюдаемое: команда или артефакт на диске. Payload показа на `GATE:take-into-work` этого слага. Код закрывает AC без тега `depends:`; с тегом — hold класса O до `operator-done:` + evidence.

### AC-001 — манифест schema 0.6.0 + required `config`

`EcosystemManifest.schema.json`: `config` в `required`; `additionalProperties` по-прежнему false на корне. `EcosystemManifest.json`: `schema_version` = `"0.6.0"`, объект `config.path` / `config.schema_path` / `config.tools` присутствует. Валидация Draft-07 проходит. Исторический H2-контракт со строкой `"0.4.0"` на диске **не** изменён.

### AC-002 — YAML SoT + схема

Файлы `~/WorkVault/Registries/EcosystemConfig.yaml` и `EcosystemConfig.schema.json` на диске. YAML валиден по схеме. Есть блоки `shared:` и `tools.<key>:` (ключи = `tools{}`). Секретных ключей в YAML нет.

### AC-003 — лоадер, не USERTOOL

`~/.hermes/lib/usertools_config.py` существует, расширяет/импортирует `usertools_env.py`. В `EcosystemManifest.json` `tools{}` **нет** нового ключа под конфиг-модуль. API: загрузка конфига tool, `explain <tool>`, per-tool каскад, `get_llm`.

### AC-004 — `explain` наблюдаем

Команда `python3 ~/.hermes/lib/usertools_config.py explain <tool>` (или эквивалентный CLI лоадера) печатает по каждому ключу `source=` из enum выходного контракта. На волне 0 для немигрированного tool допустимы `legacy`; после accepted — нет.

### AC-005 — каскад dual-read

На tool с `migration_status=dual_read`: слой с большим приоритетом побеждает (process env > overlay > `tools.<key>` > `shared` > LLM Hermes затем `tools.<key>.llm` > shared `.env` > legacy). Соседний tool без overlay не меняет значения. Смоук-тест лоадера это показывает.

### AC-006 — digest без значений и секретов

`render_manifest.py --digest`: есть путь `EcosystemConfig.yaml` и счётчики статусов `config`. Нет значений ключей YAML и нет секретов `.env`.

### AC-007 — пилот волны 1 на dual_read

Четыре ключа `fireflies_autojoin`, `move_from_ff`, `confluence_sync`, `protocol_from_summary` в `config.tools` со статусом `dual_read` (пока не приняты) либо дальше по §10.7, если уже приняты. YAML побеждает их прежний литерал/`.env` на совпадающем ключе.

### AC-008 — пакет улик per-tool

Для кандидата на accepted: (a) `explain` без `source=legacy`/`source=overlay`; (b) ≥3 подряд успешных тика крона в обычном окне **или** один полный рабочий день; (c) ErrorBus без новых событий этого tool про конфиг/env/missing key/YAML parse. Артефакт: вывод `explain` + ссылки на job_id/логи.

### AC-009 — явная реплика Саши → `accepted`

`migration_status: accepted` пишется **только** после явной реплики Саши по этому tool (волна 3 — одна пакетная реплика на список чистых регистраций). Без реплики статус не `accepted` и не `unified_only`.

Привязка `Q-n`: каждая per-tool приёмка и каждая пакетная реплика волны 3 = отдельный `Q-n` на карточке `ORCH:shared-state` этого tool (волна 3 — карточка пакетного списка); `answer:Q-n` ↔ 1:1 карточка/tool/`config.tools.<key>` (волна 3 — ↔ `package_keys` этой реплики). Наблюдаемо: (1) body карточки `ORCH:shared-state` содержит `Q-n` + `tool_key: <key>` либо `package_keys: [<key>, …]`; (2) `operator-done: answer:Q-n` + `evidence:` (ISO + цитата реплики) на `GATE:done` или корне; (3) только после (2) в `~/WorkVault/Registries/EcosystemManifest.json` поле `config.tools.<key>.migration_status` = `accepted` (волна 3 — для каждого ключа из `package_keys` этой реплики).
`depends: operator:answer:Q-n`

### AC-010 — фиксация `ORCH:shared-state`

После реплики AC-009 карточка `ORCH:shared-state` записывает в манифест `accepted` (затем `unified_only` после AC-011) и `rollback_snapshot` на файл в `~/.hermes/_Archives/ecosystem-config/<tool>/`.

### AC-011 — выпил legacy после accepted

На уже `accepted` tool удалены: его overlay, пустой/дублирующий per-tool `.env`, литералы путей/моделей/токенов/дублей env в его `config.py`. Уникальные секреты перенесены в shared `.env` **до** удаления. Тонкая оболочка `config.py` допустима.  
`depends: operator:удаляй`

### AC-012 — после accepted слои 2 и 7 запрещены этому tool

Повторный `explain <tool>`: 0 × overlay/legacy. Отсутствие ключа → исключение/exit ≠ 0, не silent fallback на старый файл (даже если файл ещё лежит на диске до AC-011). `enabled: false` останавливает tool без restore данных.

### AC-013 — откат dual_read не трогает соседей

На tool в `dual_read`: `USERTOOLS_CONFIG_MODE=legacy` или overlay возвращает его к старым файлам; `explain` соседа без этой переменной не меняется.

### AC-014 — откат после accepted из архива YAML

Restore секции YAML из `rollback_snapshot` поднимает несекретные значения этого tool. Ветка чтения старого `.env` в коде для него отсутствует.

### AC-015 — волна 4: fallback вырезан из лоадера

Когда все `active`/`draft`/`paused` = `unified_only`: в `usertools_config.py` нет веток overlay / legacy / `USERTOOLS_CONFIG_MODE` (`rg` пустой). Нет ключа → fail loud. Digest: счётчик `unified_only` = число таких tools.

### AC-016 — волна 4: осиротевшие `.env` и мёртвые ссылки

Пустые per-tool `.env` и ссылки на них в коде/скиллах снесены. Бизнес-YAML на месте.  
`depends: operator:удаляй`

### AC-017 — drift «второй источник = 0»

`render_manifest.py --check-drift` не сообщает дубль SoT конфига (нет второго канонического пути кроме YAML + shared `.env` + Hermes LLM). Чекер по-прежнему не читает `MAIN_TZ_INVENTORY.md` (§9.4).

### AC-018 — чеклист разработки

`tz-workflow` и `hermes-feature`: пункт чеклиста «новый конфиг-ключ только в `EcosystemConfig.yaml` + схема; литерал пути/модели/токена и новый per-tool `.env` = дефект». Dual-read в чеклисте помечен как запрет для новых tools.

### AC-019 — бизнес-YAML вне волн удаления

`loop_rules.yaml` / `contract_rules.yaml` / `translit.yaml` не входят в `EcosystemConfig.yaml` и не удалены волнами 0–4 (пути на диске пилотов волны 1 сохранены, если были).

### AC-020 — маркеры I1 / I2 и якоря AC пакета

В §10 есть I1 `current`/`target` (overlay-артефакты), I2 (каскад) `current`/`target` и этот подраздел с якорями AC-001…AC-020. Исторические §§1–9 без ретрофита AC. Системный класс battle-interpreters: I1 локальный §10.12 + якоря AC-B01…AC-B08 — не ретрофит AC-001…AC-020.

## Приложения к ТЗ

| Файл | Тема |
|---|---|
| `TZ/EcosystemIntegration/appendix_module0_postanovka_20260930.md` | Зафиксированная постановка модуля 0 (решения Саши 2026-09-30; источник истины для §10) |
| `TZ/AnywhereContacts/_fix_plan_20261013.md` | Диагноз 13.10: системный класс battle-interpreters, карта 16 ключей, слои A/B |

## Пакет `perevesti-kron-ecosystem-drift-check-na-no-agent` (версия пакета 0.1.2, `TZ:patch`, 2026-10-25)

Формат выбран по канону хранения ТЗ: это новая датированная секция в единственном master-файле `TZ/EcosystemIntegration/EcosystemIntegration_TZ.md`, а не второй live-файл инструмента. Существующие §§1–10.12, исторические контракты и AC не переписываются. Версия `0.1.2` фиксирует rework после `REV:plan`; версия master-файла остаётся `0.7.0` до отдельного решения о выпуске на `TZ:finalize`.

### Каноническое разделение stored/runtime

Нормативное значение поля `jobs.json.script` и аргумента `hermes cron edit --script` — относительное имя `drift_check_noagent.sh` (stored value). Физический runtime-файл — абсолютный `/home/tkachenkoav/.hermes/scripts/drift_check_noagent.sh`; этот путь используется для проверки существования/исполняемости и разрешения stored-имени, но не записывается в `jobs.json` и не передаётся в `--script`. Такое разделение следует штатному `_validate_cron_script_path`: CLI принимает имя внутри `~/.hermes/scripts/`, а scheduler затем разрешает его в физический путь. Обход валидатора, ручной JSON patch и upstream-изменение Hermes в этот пакет не входят.

### Цель

Перевести существующий крон `05265ebdfaa4` «Ecosystem drift-check (страховка)» с агентного запуска Hermes/DeepSeek на детерминированный `no_agent`-скрипт, который выполняет `render_manifest.py --check-drift`, дописывает находки в `ecosystem-drift.log` и отдаёт результат в существующий Telegram-топик Monitoring `:7`.

### Scope

В пакет входит ровно один уже существующий job:

| Поле | Норма после реализации |
|---|---|
| `id` | `05265ebdfaa4` |
| `name` | `Ecosystem drift-check (страховка)` без переименования |
| `schedule` | `0 4 * * 0` (воскресенье, 04:00) без изменения |
| `enabled` | `true` без изменения |
| `no_agent` | `true` |
| `script` | `drift_check_noagent.sh` (stored value; runtime file `/home/tkachenkoav/.hermes/scripts/drift_check_noagent.sh`) |
| `deliver` | `telegram:-1004300127777:7` без изменения маршрута |

Скрипт является runtime-обёрткой Hermes и живёт в `~/.hermes/scripts/`, потому что штатный `hermes cron edit` принимает job scripts из этого каталога. Он читает `~/WorkVault/Registries/render_manifest.py`, пишет только `~/WorkVault/Registries/ecosystem-drift.log` и не вызывает модель. `render_manifest.py --check-drift` остаётся единственным источником решения о наличии drift.

Согласованный механизм изменения job — штатная команда `hermes cron edit 05265ebdfaa4` с `--script`, `--no-agent` и сохранением `--deliver`. Перед изменением делается резервная копия текущей записи `jobs.json` в `~/.hermes/_Archives/ecosystem-drift-check-noagent-<timestamp>/jobs.json`; прямое редактирование `jobs.json` не используется. Это изменение `jobs.json` разрешено явным решением Саши «Делаем по канону только 1-2-3» и ограничено этой записью.

Рекомендуемая форма команды (значения `--prompt`, `--model`, `--provider` очищаются, чтобы в записи не оставался исполняемый агентный вход): `hermes cron edit 05265ebdfaa4 --script drift_check_noagent.sh --no-agent --prompt "" --model "" --provider "" --deliver telegram:-1004300127777:7`. CLI принимает только относительное имя внутри `~/.hermes/scripts/`; физический файл остаётся `/home/tkachenkoav/.hermes/scripts/drift_check_noagent.sh`.

### Non-goals

- Не переводить другие кроны; это только шаг 1: drift-check → `no_agent`.
- Не менять self-check, гибридные задания или шаг 4 `fallback_providers`.
- Не создавать новые кроны и не менять расписание, имя, включённость или маршрут доставки этого job.
- Не менять `EcosystemManifest.json`, `EcosystemManifest.schema.json`, `EcosystemConfig.yaml` и digest/render ради перевода job; `--check-drift` читает их в режиме проверки. `MAIN_TZ_INVENTORY` получает только служебную строку этого пакета по канону хранения ТЗ, без изменения манифеста.
- Не менять `render_manifest.py` и не переносить его логику в обёртку.
- Не рестартовать Gateway Hermes, не патчить `~/hermes-agent`, ErrorBus или секреты.

### I1 → target

`current`: job хранит агентный prompt, `no_agent=false`, `script=null`, модельный snapshot `deepseek/deepseek-v4-flash-0731`; агент запускает проверку, разбирает stdout и пишет находки.

`target`: тот же job с `no_agent=true`, stored `script=drift_check_noagent.sh` и script-only dispatch; это имя разрешается в физический runtime-файл `/home/tkachenkoav/.hermes/scripts/drift_check_noagent.sh`; stdout скрипта доставляется Hermes напрямую в `telegram:-1004300127777:7`; ни prompt, ни model/provider не участвуют в исполнении. Логика результата полностью детерминирована локальными файлами и `render_manifest.py`.

### Контракты выполнения

#### Скрипт `drift_check_noagent.sh`

1. Запускает `python3 /home/tkachenkoav/WorkVault/Registries/render_manifest.py --check-drift` и захватывает stdout и код завершения без вызова Hermes/LLM.
2. При чистом результате публикует в stdout ровно `No drift`, не изменяя `ecosystem-drift.log`.
3. При реальных строках drift (вывод содержит таблицу `path | drift_type | recommendation`) дописывает их в `/home/tkachenkoav/WorkVault/Registries/ecosystem-drift.log` под новым заголовком `## Ecosystem drift (<YYYY-MM-DD>)`, сохраняя append-only порядок. В stdout отдаёт тот же наблюдаемый отчёт для доставки в `:7`.
4. Обёртка нормализует итоговый код. Если stdout содержит одну или более валидных строк drift (`path | drift_type | recommendation`), она дописывает строки в лог, отдаёт наблюдаемый отчёт в stdout и завершается с `rc=0`, даже если дочерний `--check-drift` вернул ненулевой код. Если валидных строк нет и дочерняя проверка чистая (`rc=0`), скрипт печатает `No drift` и завершается с `rc=0`. Ошибка запуска/парсинга либо ненулевой код без валидного отчёта — операционная ошибка: скрипт печатает короткое детерминированное сообщение, не копирует provider stderr в лог и завершается с `rc≠0`; LLM и автоматический retry не вызываются.
5. Запись лога не перезаписывает существующие записи и не меняет манифест. При повторном чистом тике новых строк в логе нет.

#### Job и доставка

- Scheduler видит `no_agent=true` и непустой `script`; stdout скрипта является телом уведомления, а пустой stdout не создаёт сообщение.
- `deliver` остаётся ровно `telegram:-1004300127777:7`; новый Telegram-топик, отдельный канал или прямой вызов Telegram API не заводятся.
- Устаревшие `prompt`, `model` и `provider` очищаются штатными аргументами `hermes cron edit`, если это поддерживается текущим CLI. `model_snapshot` может сохраниться как историческое поле записи: он не является исполняемым входом `no_agent`-ветки и проверяется только по run-record.
- Сохраняются job id, расписание, enabled и политика failure delivery; изменяются только script/no_agent и необходимые поля, отключающие агентный prompt.

#### Проверка drift

До применения изменения на `HF:impl` сохраняется неизменяемый baseline snapshot прямого запуска: полный stdout, дочерний `rc` и разобранные валидные строки drift. На момент этого пакета известный baseline содержит одну pre-existing находку `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/HomeCutover/HomeCutover_TZ.md | tz_not_in_manifest` (рекомендация `Add tools entry with tz_ref=TZ/HomeCutover/HomeCutover_TZ.md`) и `rc=1`; snapshot не изменяет живой манифест или журнал.

После применения изменения выполняется:

`python3 /home/tkachenkoav/WorkVault/Registries/render_manifest.py --check-drift`

Результат сравнивается с сохранённым baseline: множество новых валидных строк (`after - baseline`) должно быть пустым. Pre-existing строки, включая `HomeCutover`, допускаются; поэтому прямой `--check-drift` может сохранить `rc=1`, если baseline drift остался, и это не блокирует пакет. Если после сравнения нет новых строк, скрипт не исправляет drift автоматически и не меняет baseline; reconciliation baseline остаётся отдельной задачей владельца манифеста.

### Контракты экосистемы

| Контракт | Источник | Потребитель | Проверка |
|---|---|---|---|
| `render_manifest.py --check-drift` и его exit code | `/home/tkachenkoav/WorkVault/Registries/render_manifest.py` | `drift_check_noagent.sh` | stdout + rc сохраняются до классификации |
| журнал находок | `/home/tkachenkoav/WorkVault/Registries/ecosystem-drift.log` | оператор/следующий аудит | новый заголовок + строки append, старые записи целы |
| cron job | `/home/tkachenkoav/.hermes/cron/jobs.json`, запись `05265ebdfaa4` | Hermes scheduler | `no_agent=true`, `script` непуст, schedule/deliver неизменны |
| уведомление | `telegram:-1004300127777:7` | Monitoring :7 | фактическое сообщение после тестового тика |
| модельный вызов | отсутствует | — | run-record не содержит LLM session/provider call; DeepSeek не запускается |

### Что НЕ трогать в этом пакете

- Кроны, кроме `05265ebdfaa4`; особенно не менять self-check, `pfs_batch`, гибриды и другие job id.
- `fallback_providers` и любые конфиги fallback-моделей.
- `~/hermes-agent`, `gateway/session.py`, scheduler и Gateway; Gateway не рестартовать.
- `EcosystemManifest.json`, его schema, render/digest и `render_manifest.py`, если отдельная проверка не обнаружит самостоятельную drift-проблему.
- `ecosystem-drift.log` до первого реального drift-прогона; не чистить и не переписывать историю.
- Секреты, `EcosystemConfig.yaml`, чужие master-ТЗ и существующие Telegram-топики.
- Автоматическое создание нового cron; этот пакет только меняет явно согласованный существующий job.

### Критерии приёмки (AC)

Класс всех AC — **S**: наблюдаемая проверка, без нового `depends: operator:`. Реализация кода и job выполняется после этого `TZ:patch`; текущая фаза изменяет только текст ТЗ.

#### AC-021 — cron переведён в no_agent

`hermes cron list --all` и запись `05265ebdfaa4` на диске показывают `no_agent=true`, stored `script=drift_check_noagent.sh`, `enabled=true`, schedule `0 4 * * 0`, name без изменения и `deliver=telegram:-1004300127777:7`; этот stored value разрешается в исполняемый файл `/home/tkachenkoav/.hermes/scripts/drift_check_noagent.sh`.

#### AC-022 — скрипт существует и исполняем

Файл `/home/tkachenkoav/.hermes/scripts/drift_check_noagent.sh` существует, исполняем, проходит `bash -n`; в нём есть вызов `render_manifest.py --check-drift` и путь к `ecosystem-drift.log`. Скрипт не вызывает `hermes`, `agent`, Codex, DeepSeek или Telegram API.

#### AC-023 — чистый прогон

На фикстуре без drift скрипт завершает работу с rc 0, печатает ровно `No drift`, не добавляет строку в `ecosystem-drift.log` и не создаёт пустое уведомление.

#### AC-024 — drift логируется append-only и доставляется штатно

На фикстуре с одной или несколькими валидными строками drift скрипт добавляет новый `## Ecosystem drift (<YYYY-MM-DD>)` и строки `path | drift_type | recommendation`, не удаляя предыдущий журнал; stdout содержит наблюдаемый отчёт для доставки, а итоговый `drift_check_noagent.sh` завершается с `rc=0`, даже если дочерний `--check-drift` вернул `rc≠0`.

#### AC-025 — доставка в Monitoring :7

Тестовый запуск изменённого job доставляет `No drift` либо отчёт drift в `telegram:-1004300127777:7`; новый topic/channel не появляется, `deliver` побитно совпадает с контрактом.

#### AC-026 — DeepSeek не вызывается

Run-record изменённого job показывает script/no-agent execution без LLM session/provider call, model usage и token spend; `deepseek/deepseek-v4-flash-0731` отсутствует среди вызовов этого запуска. Повторный тик не создаёт агентную сессию.

#### AC-027 — drift-check не добавляет новых расхождений

До применения job-изменения сохранён baseline snapshot с stdout, дочерним `rc` и валидными строками. После изменения прямой `python3 /home/tkachenkoav/WorkVault/Registries/render_manifest.py --check-drift` сравнивается с этим snapshot: `after - baseline` пуст, манифест не изменён, а pre-existing `HomeCutover` допускается. Безусловный `exit 0` не требуется: `rc=1` допустим, если прямой checker по-прежнему сообщает только baseline drift; при чистом результате допустим `rc=0`.

#### AC-028 — scope ограничен одним job

Diff/снимок `jobs.json` показывает изменение только записи `05265ebdfaa4`; расписания и payload других jobs, `fallback_providers`, Gateway и ядро Hermes не изменены.

#### AC-029 — штатный механизм и резервная копия

В evidence есть резервная копия исходной записи `05265ebdfaa4`, а изменение выполнено через `hermes cron edit`, а не ручной JSON patch; после команды `hermes cron list --all` подтверждает целостность job.

#### AC-030 — откат воспроизводим

Из резервной копии можно штатной командой `hermes cron edit` с `--agent --script ""` вернуть прежние `no_agent=false`, stored `script=null`, prompt/model/provider и сохранить исходные schedule/name/deliver; абсолютный runtime-путь не является значением rollback-поля. Откат не меняет другие jobs и не требует рестарта Gateway.

#### AC-031 — ошибка проверки видима и не вызывает LLM

При ошибке запуска/парсинга или ненулевом коде `--check-drift` без валидных строк drift скрипт завершает `rc≠0` с коротким детерминированным сообщением; raw stderr не дописывается в `ecosystem-drift.log`, stdout не выдаётся как штатный drift-отчёт, агентный fallback и автоматический retry отсутствуют. Ненулевой дочерний `rc` при валидных строках проверяется по AC-024 и обязан нормализоваться обёрткой до `rc=0`.

### IAC-ориентир для `HF:plan`

| IAC | Переход | Артефакт | Verify | Covers |
|---|---|---|---|---|
| IAC-01 | `HF:impl` → `HF:test` | запись job `05265ebdfaa4` | `hermes cron list --all` + diff snapshot: `no_agent=true`, stored `script=drift_check_noagent.sh`, resolved runtime `/home/tkachenkoav/.hermes/scripts/drift_check_noagent.sh`, deliver/schedule/enabled/name/failure policy unchanged | AC-021, AC-028, AC-029 |
| IAC-02 | `HF:impl` → `HF:test` | `drift_check_noagent.sh` | `test -x`, `bash -n`, изолированный harness с копией скрипта и подменёнными temp-путями к checker/log (живые манифест и журнал не записываются): clean → stdout `No drift`, `rc=0`; valid drift при child `rc≠0` → отчёт, append в temp-log, wrapper `rc=0`; error/no valid rows → короткое сообщение, wrapper `rc≠0` | AC-022–024, AC-031 |
| IAC-03 | `HF:test` → `GATE:done` | cron run + Monitoring :7 | run-record без LLM + фактическая доставка в `telegram:-1004300127777:7`; сохранённый `model_snapshot`, если остался в записи, проверяется только как неисполняемое историческое поле | AC-025, AC-026 |
| IAC-04 | `HF:test` → `GATE:done` | baseline snapshot + manifest drift check | сохранить stdout/child `rc`/valid rows до изменения; после изменения проверить `after - baseline = ∅`, манифест unchanged, `HomeCutover` baseline допустим; прямой checker `rc=1` при сохранённом baseline допустим, безусловный `rc=0` не требовать | AC-027 |
| IAC-05 | `HF:docs-handoff` → `GATE:done` | rollback snapshot | штатное восстановление job, соседние jobs unchanged | AC-030 |

### Preflight перед `HF:impl` и production edit

После записи runtime-файла и до единственного production-вызова `hermes cron edit` проверяется:

1. команда передачи job использует только `--script drift_check_noagent.sh`; ожидаемое значение `jobs.json.script` — ровно это относительное имя;
2. `test -x /home/tkachenkoav/.hermes/scripts/drift_check_noagent.sh` подтверждает физический runtime-файл, который является разрешением stored-имени, а не stored-значением;
3. pre-edit snapshot и diff-контроль не содержат абсолютного пути в поле `script`, не затрагивают соседние jobs и сохраняют backup/rollback evidence.

### Откат и граница текущей фазы

Откат runtime выполняется только восстановлением сохранённой записи через `hermes cron edit`; скрипт можно оставить на диске как неиспользуемый артефакт до отдельного решения, удалять его автоматически нельзя. До явного согласования реализации этот пакет не пишет `/home/tkachenkoav/.hermes/scripts/`, `jobs.json`, конфиги, манифест, лог или Gateway: `TZ:patch` добавляет только эту текстовую секцию. `[NEW-ENTITY, требует согласования Саши]` нет; Q-n нет; шаги 2–4 и fallback остаются вне скоупа.

### Финализация пакета (`TZ:finalize`, 2026-10-25)

Пакет `perevesti-kron-ecosystem-drift-check-na-no-agent` v0.1.2 зафиксирован после `REV:tz APPROVE` (архитектор и ревизор; rework). Это финальный штамп корпуса `TZ:patch` без переписывания исторических контрактов и AC; версия master-ТЗ сохраняется `0.7.0`. Реализация, cron, `jobs.json`, манифест и прочие защищённые артефакты этой фазой не изменяются.

## Пакет `eco-config-w3` (версия пакета 0.1.0, `TZ:patch`, 2026-10-25)

Это аддитивная запись к модулю 0 OverlayConfig. Версия master-ТЗ остаётся `0.7.0`; исторические §§1–10.12, контракты и AC не переписываются. Канонический указатель фазы: `dev/eco-config-w3/TZ-patch.md`.

### Цель и идентичность

Волна 3 регистрирует в `/home/tkachenkoav/WorkVault/Registries/EcosystemConfig.yaml` ровно пакет из 30 инструментов без собственного конфиг-файла. Для каждой записи допустимы `enabled` и только уже подтверждённая конвенция логов; новых runtime-ключей, путей, моделей и секретов не добавлять. На диске для этого пакета уже наблюдается целевая форма: 28 записей с `enabled: true`, `dialog_backlog` и `dialog_backlog_to_kanban` с `enabled: false`.

Пакетный список (`body` карточки `ORCH:shared-state`):

```yaml
Q-1: Принять / не принять пакет чистых регистраций OverlayConfig, волна 3.
package_keys:
  - aggregate_from_meetings
  - case_collector
  - deep_mine_project
  - dev_kanban_pipeline
  - dialog_backlog
  - dialog_backlog_to_kanban
  - ecosystem_integration
  - edit_plan_confluence
  - entities_migration
  - entity_registry
  - entity_registry_cli
  - error_bus
  - exchange_org_lookup
  - honcho_integration
  - meeting_scheduler
  - mofs_index
  - mpp_reader
  - okr_sheets_exporter
  - okr_tool
  - piiscan
  - process_improvement
  - skills_improvement
  - status_snapshot
  - sync_aralov
  - telegram_group_topics
  - tg_topic_duplicate
  - tz_dev_cleanup
  - tz_dev_decommission
  - tz_workflow
  - vestnik_theme
```

Identity вопроса — `(card_id ORCH:shared-state, Q-1)`. До `operator-done: answer:Q-1` с ISO-временем и цитатой реплики Саши `migration_status` не менять. После ответа: пакетно `accepted`, затем `unified_only` по AC-010…AC-012; соседние tools не менять.

### Границы и запреты

- `dev_kanban_pipeline`, `honcho_integration`, `tz_dev_cleanup`, `tz_dev_decommission`, `tz_workflow` не переносят Hermes `config.yaml` в OverlayConfig.
- `dialog_backlog` и `dialog_backlog_to_kanban` остаются `enabled: false`: индекс, без runtime.
- Новый `tools{}` для OverlayConfig, probe, реестра интерпретаторов или `EcosystemConfig` не заводить.
- Секреты остаются только в shared `.env`; в YAML, манифест и digest их не добавлять.
- `loop_rules.yaml`, `contract_rules.yaml`, `translit.yaml` не переносить и не удалять.
- Слои 2/7 и `USERTOOLS_CONFIG_MODE` не вырезать: это волна 4, AC-015/AC-016.
- Не удалять legacy, `.env`, Hermes `config.yaml`, `jobs.json`, Gateway, `entities.json` или чужие master-ТЗ. AC-011 выполняется только после принятия и отдельного императива `удаляй`.

### Probe-AC с первого драфта `HF:plan`

Для каждого из 30 ключей план обязан иметь отдельную IAC-строку (`IAC-W3-01`…`IAC-W3-30`) с `covers: AC-B01 + AC волны 3`. Артефакты: `~/WorkVault/Registries/battle_interpreters.yaml` и `~/.hermes/lib/probe_battle_venv.py`. В строке реестра фиксируются `wave: 3`, абсолютный `battle_python`, `entry_kind` (`cron`/`wrapper`/`skill`/`shebang`) и `entry`; при отсутствии боевого входа явно записывается «входа нет». Боевой python обязан пройти `import yaml`, `import usertools_config` и declared imports, а `usertools_config.py explain <key>` выполняется тем же python. Pytest PFS/hermes этого AC не закрывает. Боевой python, `entry` и declared imports в TZ-патче не угадываются.

### Связь с AC

Пакет закрывает постановку регистраций для AC-002 и готовит evidence для AC-009, AC-010, AC-011, AC-012, AC-017, AC-B01, AC-B05 и AC-B06. Связанные AC-B02/AC-B03/AC-B04/AC-B07/AC-B08 сохраняются без подмены: AC-B03/AC-B07 относятся к выходу волны 2, AC-B08 — к живому поиску AnywhereContacts, AC-B02/AC-B04 — к системному инварианту и wrapper-слою при применимости. `accepted`/`unified_only` не выставляются этим текстом без `answer:Q-1`; probe и runtime-проверка выполняются в `HF:impl`/`HF:test`, запись статусов — на `ORCH:shared-state`. `[NEW-ENTITY, требует согласования Саши]` нет.

Канонический артефакт: `/home/tkachenkoav/WorkVault/Hermes-Backlog/dev/eco-config-w3/TZ-patch.md`. Выжимка `/home/tkachenkoav/WorkVault/Hermes-Backlog/dev/eco-config-w3/extract.md` остаётся индексом; при расхождении действует этот master.
