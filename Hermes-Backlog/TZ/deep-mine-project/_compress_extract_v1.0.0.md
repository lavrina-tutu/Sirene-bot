## Назначение
   - ## Сущности
   - ## API / CLI
   - ## Связи
   - ## Конфиг
   - ## Ограничения
   - ## Источник

3. **Сборка и проверка дословности названий.**
   - Убедимся, что все имена файлов, команд, флагов, ENV и ключей PROJECT.yaml точно совпадают с ТЗ.
   - Упоминание [NEW-ENTITY, требует согласования Саши] сохранено.
## Назначение
Полуавтоматический сбор полного контекста проекта из канонических источников WorkVault в двуслойный MD-архив (L0 канон + L1 overlay), построение графа связей без LLM, извлечение фактов (`facts.json`) и однократный синтез двух производных контекстов (`charter-context.md` и `architecture-context.md`) с использованием `cursor-grok-4.6-high` и API-JSON. Служит для ответов на уставные и архитектурные вопросы без сжатия каждой страницы отдельно.

## Сущности
- **L0 канон (SoT источников):**
  - `WorkVault/Confluence/<space>/.../index.md` — полные тела MD и frontmatter
  - `WorkVault/Meetings/NewMeetings/` — оригиналы протоколов/транскриптов
  - `WorkVault/Entities/<entity_slug>/` — карточки сущностей
- **L1 overlay (рабочий стол проекта):**
  - `WorkVault/Projects/<Slug>/` — корень проекта (пример: `WorkVault/Projects/TrisigmaFull/`)
  - `WorkVault/Projects/<Slug>/MANIFEST.json` — манифест проекта (`schema_version: "1.1"`)
  - `WorkVault/Projects/<Slug>/PROJECT.yaml` — главный конфиг проекта
  - `WorkVault/Projects/<Slug>/TREE.md` — иерархия родитель-ребенок из GRAPH
  - `WorkVault/Projects/<Slug>/SOURCES.md` — таблица `pageId` → `local_path` + wiki-ссылка
  - `WorkVault/Projects/<Slug>/GRAPH.json` — граф узлов и типизированных рёбер без LLM
  - `WorkVault/Projects/<Slug>/LINKS.md` — текстовая таблица связей `from`, `to`, `type`
  - `WorkVault/Projects/<Slug>/facts.json` — факты (`script_only` + `llm_assisted`)
  - `WorkVault/Projects/<Slug>/charter-context.md` — слой C, поля устава по каталогу ПРО
  - `WorkVault/Projects/<Slug>/architecture-context.md` — слой C, архитектура и ИБ
  - `WorkVault/Projects/<Slug>/charter-context.rejected.json` — дамп ошибок при сбое J1–J8
  - `WorkVault/Projects/<Slug>/architecture-context.rejected.json` — дамп ошибок архитектуры
  - `WorkVault/Projects/<Slug>/attachments/` — скачанные whitelist-вложения
  - `WorkVault/Projects/<Slug>/mpp/` — CSV плана и `plan.md`
  - `WorkVault/Projects/<Slug>/pointers/` — `meetings.md`, `entity.md`
  - `WorkVault/Projects/<Slug>/digest/` — наследие v0.2.0 (не SoT для ответов)
  - `WorkVault/Projects/<Slug>/docs/` — `_inbox/`, `_charter_draft/` (черновики документов)
- **Индексация overlay `Projects/` в `mofs-index`** — [NEW-ENTITY, требует согласования Саши].

## API / CLI
- **`deep_mine.py` CLI / скилл `deep-mine-project`:**
  - `deep_mine.py init --slug <Slug>` — создание скелета overlay и `PROJECT.yaml`
  - `deep_mine.py collect --slug <Slug>` — сбор сырья A–E без LLM
  - `deep_mine.py graph --slug <Slug>` — построение слоя A (`GRAPH.json`, `LINKS.md`, `TREE.md`)
  - `deep_mine.py facts --slug <Slug>` — сбор слоя B (`facts.json`: `script_only` + `llm_assisted`)
  - `deep_mine.py charter --slug <Slug>` (или `context --slug <Slug> --context charter`) — синтез `charter-context.md`
  - `deep_mine.py architecture --slug <Slug>` (или `context --slug <Slug> --context architecture`) — синтез `architecture-context.md`
  - `deep_mine.py mine --slug <Slug>` — полный цикл `collect` → `graph` → `facts` → `charter` → `architecture`
  - `deep_mine.py refresh --slug <Slug>` — сверка версий/`sources_sha`, докачка и пересинтез stale-контекстов
  - `deep_mine.py pack --slug <Slug>` — сборка `PACK.md` из контекстов, GRAPH и CSV
  - `deep_mine.py analyze --slug <Slug>` — шаг G (план архитектора `docs/_inbox/architect-plan.md`)
  - `deep_mine.py document --slug <Slug>` — шаг H (исполнитель `composer-2.5` формирует `docs/*.md`)
  - `deep_mine.py digest --slug <Slug>` — наследие F (пересжатие `digest/leaves`, не входит в default `mine`/`refresh`)
- **Внешние CLI:**
  - `python3 -m confluencesync pull <pageId> [--depth N] [--no-recursive] [--resync] [--to-file]` — скачивание страниц из Confluence REST
  - `read_mpp.py --format both` — MppReader fallback для чтения файлов `.mpp`
- **Exit codes и лимиты:**
  - `exit 6` — fail-loud сброс с записью `*.rejected.json` при нарушении контракта J1–J8
  - `follow_outbound.depth: 1` — ограничение глубины обхода исходящих ссылок
  - `max_outbound_pull: 24` — верхний лимит скачивания исходящих страниц за один проход

## Связи
- **Читает:**
  - Confluence REST API (`https://dom.tutu.ru`)
  - L0 хранилище WorkVault (`WorkVault/Confluence/`, `WorkVault/Meetings/NewMeetings/`, `WorkVault/Entities/`)
  - MofsIndex / `workvault-rag` (индекс встреч `search_meetings`)
  - EntityRegistry (`entities.json` / `Entities/<entity_slug>/`)
  - `pmo-charter-fill` (`~/hermes-workspace/skills/productivity/pmo-charter-fill/references/pro-field-catalog.md`)
  - USERTOOLS/MppReader (`read_mpp.py`)
- **Пишет:**
  - L1 overlay (`WorkVault/Projects/<Slug>/`)
- **Потребляют:**
  - `skill:tz-workflow`, `skill:hermes-feature`, `skill:pmo-charter-fill`
  - Hermes Q&A (`deepseek` в Сирени)
  - Cursor CLI (`cursor-grok-4.6-high`, API-JSON)

## Конфиг
- **ENV:**
  - `CONFLUENCE_TOKEN` — токен авторизации Confluence (из `~/USERTOOLS/ConfluenceSync/.env`)
- **Ключи `PROJECT.yaml`:**
  - `schema_version`: версия схемы (например, `"1.1"`)
  - `slug`: идентификатор проекта в overlay (например, `TrisigmaFull`)
  - `display_name`: понятное имя проекта
  - `entity_slug`: slug сущности в EntityRegistry (например, `trisigma`)
  - `confluence.root_page_id`: коренная страница Confluence
  - `confluence.root_title`: заголовок коренной страницы
  - `confluence.space_primary`: основной space (например, `DPAN`)
  - `confluence.pmo_seeds`: список объектов `{ page_id, title, space }`
  - `confluence.task_pages`: список объектов `{ page_id, role, space }`
  - `confluence.follow_outbound`: параметры `{ mode, depth, allowed_spaces, denylist_title_substrings, unknown_space, max_outbound_pull }`
  - `plan.source`: источник плана (`gantt` или `mpp`)
  - `plan.gantt_page_id`: `pageId` страницы с макросом `gantt-chart-planner`
  - `plan.gantt_instance`: UUID инстанса макроса
  - `plan.rate_rub_per_hour`: часовая ставка (например, `3000`)
  - `plan.project_title`: название проекта в плане
  - `meetings.project_slugs`: список слагами встреч (`[trisigma]`)
  - `contexts.charter_body_page_ids`: массив `pageId` полных тел для `charter-context.md`
  - `contexts.architecture_themes`: темы для архитектуры (`[architecture, security]`)
  - `contexts.architecture_body_page_ids`: массив `pageId` полных тел для `architecture-context.md`
- **Cron expressions:**
  - Кроны **отсутствуют и запрещены** к автоматическому созданию (запуск только вручную до явного указания «ставь кроны»).

## Ограничения
- **Fail-soft / Fail-loud:**
  - S3/REST HTTP 401, 403, VPN-ошибки → fail-loud, моментальная остановка пайплайна (не помечать ресурсы как fresh).
  - Сбой контракта J1–J8 при синтезе слоя C → fail-loud, сохранение `*.rejected.json`, завершение с `exit 6`, запрет перезаписи текущих канонических `.md`.
- **Правила сжатия и источников:**
  - Запрещено использовать per-page `digest/leaves` как SoT для ответов Q&A, pack и задач архитектора.
  - Запрещено выполнять синтез C за один монолитный проход (обязателен батчевый синтез по 5 пачкам полей устава или темам архитектуры).
  - Обязательно использование API-level structured output (`response_format` / `json_schema`); `--output-format json` в Cursor CLI не является выполнением J3.
  - Цифры из `facts.script_only` имеют абсолютный приоритет и побеждают данные из `llm_assisted` или модели при конфликтах.
  - Каждая запись факта в слое C должна содержать явную ссылку на `source pageId`.
- **«Не трогать»:**
  - Запрещено дублировать, переносить или удалять файлы канона L0 (`WorkVault/Confluence/`, `WorkVault/Meetings/`, `WorkVault/Entities/`).
  - Запрещено изменять файл `tz-compressor-prompt.md`.
  - Запрещено перезапускать Gateway.

## Источник
- **Путь:** `TZ/deep-mine-project/deep-mine-project_TZ.md`
- **Версия:** `1.0.0`
- **Дата:** `2026-09-09`