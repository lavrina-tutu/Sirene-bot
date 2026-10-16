---
name: EntitiesMigration
version: 0.2.0
status: completed
date: 2026-07-23
last-section-added: 2026-07-24 — реализовано
completed: 2026-07-24
---

# EntitiesMigration — ТЗ на унификацию структуры WorkVault

Автор: Opus (по заданию Саши Ткаченко). Версия 0.2.0 учитывает решения брифа Саши от 23.07.2026 (см. §9).

## §1 Цель

Унифицировать структуру WorkVault: **все сущности** (проекты, 1-1, мультисинки, sync-aid, люди) хранятся в `WorkVault/Entities/<slug>/` — одна папка на сущность, единый layout, латинский slug из `Registries/entities.json`. Инструменты (`kind: tool`) остаются только в реестре, папки в `Entities/` для них не создаются.

## §2 Текущее состояние (AS-IS)

Реальный срез файловой системы на 2026-07-23.

### 2.1 Типы сущностей и их расположения

| Тип (kind в entities.json) | Кол-во в реестре | Текущее расположение | Пример |
|---|---|---|---|
| `project` | 16 | `WorkVault/Projects/<slug>/` (папка) **и параллельно** `WorkVault/Projects/<slug>.md` (плоский обзор c dataview) | `Projects/trisigma/`, `Projects/trisigma.md` |
| `one_on_one` | 5 | `WorkVault/Projects/<slug>.md` (только плоский файл, папки НЕТ) | `Projects/aralov_1on1.md` |
| `multisync` | 2 | `WorkVault/Projects/<slug>.md` (плоский) | `Projects/datatalks.md`, `Projects/vstrechi_pro.md` |
| `sync_aid` | 1 | `WorkVault/Projects/<slug>.md` (плоский) | `Projects/sink_aid.md` |
| `tool` | 13 | нет отдельных папок в WorkVault, только запись в реестре | `jira`, `confluence`, `loop`, ... |
| `unknown` | 2 | нет папок | `tsu`, `vstrechi_nerazobrannoe` — **удаляются из реестра** (см. §9 Q9) |
| `person` (не в реестре) | 9 | `WorkVault/People/<Фамилия Имя>/` (**кириллица** в имени папки), внутри `card.md` (+ у некоторых `context.md`, `risks.md`, `status_snapshot.md`, `contract_vendor.md`) | `People/Аралов Александр/` |

Итого в реестре 39 записей; папок People — 9.

### 2.2 Дубли и пересечения

- **Проект-папка + проект-md**: для 12 из 16 проектов существует и `Projects/<slug>/`, и `Projects/<slug>.md`. У 4 (`ai_ready`, `ai_analitik`, `ab_platforma`, `ml_platforma`) — только `.md` (папки нет).
- **9 папок в `Projects/` без записи в реестре** — точный список и решения зафиксированы в §9 Q4:
  - `ai-mas`, `chatbot` → алиасы к `ai_analitik`;
  - `alpha` → новая запись `kind: project`, `display_name: «Альфа»`;
  - `okr-tool` → алиас к `okr`;
  - `parsery`, `parsing-zhd` → алиасы к `parsing`;
  - `vestnik-aid` → алиас к `vestnik`;
  - `ai-transformaciya` → алиас к `ai_ready`;
  - `sr-tool` → папка пустая, удаляется целиком.
- **1-1 vs person**: 1-1 сущности (`aralov_1on1`, `dayana_1on1`, `ilya_1on1`, `kirill_1on1`, `zhirov_1on1`) представляют встречи с людьми, у которых уже есть папка в `People/` (Аралов, Набиева, Середа, Криворотов, Жиров). По решению Q1 — **сливаются в одну папку** на человека.
- **People без 1-1** (4 карточки): Алексеева Юлия, Котельникова Ольга, Малый Денис, Перетяткова Екатерина — есть карточка в People, нет записи в entities.json. Решения по slug'ам зафиксированы в §9 Q2.

### 2.3 Служебные подпапки в Projects/

| Путь | Содержимое | Роль |
|---|---|---|
| `Projects/Pages/` | `*_brief.md`, `*_charter.md`, `*_report.md`, `_index.json`, `PMO/` (методология Confluence) | Публикуемые страницы/бриф/чартер по проектам + выгрузка PMO |
| `Projects/_template/` | `card.md`, `context.md`, `risks.md`, `status_snapshot.md` | Шаблон для новой карточки проекта |
| `Projects/_research/` | пусто | — удаляется (см. §9 Q8) |
| `Projects/Trisigma  вопросы.md` | одиночный файл (кириллица + двойной пробел) | Заметка, переезжает в `Entities/trisigma/` |

### 2.4 Формат `entities.json`

Верхний уровень: `{"schema_version": "1.0", "entities": {<slug>: {...}}}`. У записи — `kind`, `parent`, `display_name`, `aliases`, `pfs {page_id, tag}`. **Полей `folder_path`, `card_path` в реестре сейчас нет.**

## §3 Целевое состояние (TO-BE)

### 3.1 Единая структура

```
WorkVault/Entities/
  <slug>/
    card.md              # обязательный, frontmatter: kind, slug, display_name, ...
    <slug>.md            # (опц.) исторический плоский .md переехал сюда с тем же именем (см. §9 Q3)
    Messages/            # саммари Loop-каналов, треды переписки (опционально)
    Meetings/            # ссылки/индекс встреч (опционально)
    Pages/               # brief, charter, report — то, что публикуется в Confluence (опционально)
    context.md           # для проектов, из шаблона (опционально)
    risks.md             # опционально
    status_snapshot.md   # опционально
    jira_snapshot.json   # выгрузки, служебные файлы (опционально)
```

### 3.2 Правила slug'ов

- Slug — только `[a-z0-9_]`, латиница + подчёркивания. Кириллица и дефисы запрещены (дефис `-` → подчёркивание `_` для консистентности с существующими `ab_platforma`, `ml_platforma`).
- Источник slug'а:
  - для проектов/1-1/multisync/sync_aid — существующий slug из `entities.json`;
  - для 9 папок без реестра — см. §9 Q4 (алиас существующей записи или новая запись);
  - для 4 people без 1-1 — фиксированные slug'и из §9 Q2 (`alekseeva`, `kotelnikova`, `maly`, `peretyatkova`);
  - для people, у которых уже есть соответствующее 1-1 — **используется slug 1-1** (merge, см. §9 Q1).
- Имя папки = slug. Кириллические имена (`People/Аралов Александр/`) исключаются.

### 3.3 Целевые виды сущностей

`kind ∈ {project, one_on_one, multisync, sync_aid, tool, person}`. `unknown` удаляется из схемы (см. §9 Q9).

- `tool` — папка **не создаётся** в `Entities/`, только запись в реестре (см. §9 Q10). Поле `folder` = null.
- Person, у которого есть соответствующее 1-1 → merge: одна папка, `kind: one_on_one`.
- Person без 1-1 → `kind: person`, отдельная папка.

### 3.4 Обязательные поля `card.md`

```yaml
---
slug: aralov_1on1
kind: one_on_one
display_name: 1-1 Аралов Александр
parent: <опц., если сущность вложена>
aliases: [...]
status: active            # только для project
---
```

### 3.5 Расширение `entities.json`

Добавить в каждую запись, у которой есть папка, поле `folder: "Entities/<slug>"` (строка, относительный путь от корня WorkVault). Для `kind: tool` — `folder: null`. MOFS, workvault-rag и другие потребители читают путь оттуда, а не хардкодят `Projects/`/`People/`. `schema_version` → `"1.1"`.

## §4 Что мигрировать

### 4.1 Projects → Entities (проекты, 1-1, multisync, sync_aid)

| Кейс | Действие |
|---|---|
| `Projects/<slug>/` (полная папка, slug совпадает с реестром) | `mv` → `Entities/<slug>/` |
| `Projects/<slug>.md` + `Projects/<slug>/` (дубль) | папка → `Entities/<slug>/`; плоский `.md` переезжает **с тем же именем** внутрь папки: `Entities/<slug>/<slug>.md` (Q3: не переименовывать в `card.md`); `card.md` создаётся отдельно из шаблона, если его ещё нет |
| Только `Projects/<slug>.md` (папки нет: `ai_ready`, `ai_analitik`, `ab_platforma`, `ml_platforma`) | создать `Entities/<slug>/`, перенести `.md` как `Entities/<slug>/<slug>.md`, создать `card.md` из шаблона, обогатить frontmatter |
| Имя папки не соответствует slug'у реестра (напр. `ml-platforma` vs `ml_platforma`) | папка переименовывается в slug реестра при переносе |
| 9 папок без записи в реестре (`ai-mas`, `alpha`, `chatbot`, `okr-tool`, `sr-tool`, `parsery`, `vestnik-aid`, `ai-transformaciya`, `parsing-zhd`) | обработка по Q4 (§9): для алиасов — слить содержимое в целевую сущность и добавить исходное имя в `aliases`; для `alpha` — создать новую запись; `sr-tool` — удалить папку (пустая) |
| `Projects/aralov_1on1.md` и т.п. (5 файлов) | по решению Q1 (merge) — переезжают в общую папку человека, имя файла сохраняется: `Entities/aralov_1on1/aralov_1on1.md`; сама папка получает slug 1-1 |
| `Projects/Pages/*_brief.md`, `*_charter.md`, `*_report.md` | по решению Q5 — раскладываются в `Entities/<slug>/Pages/` по префиксу имени файла (напр. `trisigma_brief.md` → `Entities/trisigma/Pages/trisigma_brief.md`); нераспознанные — в `Entities/pmo/Pages/` |
| `Projects/Pages/PMO/` (методология) | переезжает в `Entities/pmo/Pages/PMO/` (PMO становится сущностью-контейнером для методологии) |
| `Projects/Pages/_index.json` | переезжает в `Entities/pmo/Pages/_index.json` (служебный индекс) |
| `Projects/_template/` | → `WorkVault/_templates/entity/` (вне `Entities/`, служебное) |
| `Projects/_research/` | пустая — **удалить** (Q8) |
| `Projects/Trisigma  вопросы.md` | перенести в `Entities/trisigma/Trisigma_вопросы.md` (сохранить смысл, убрать двойной пробел) |

### 4.2 People → Entities

| Кейс | Действие |
|---|---|
| `People/<ФИО>/`, у которого есть соответствующее 1-1 (5 чел.: Аралов, Набиева, Середа, Криворотов, Жиров) | merge (Q1): содержимое переезжает в `Entities/<1on1_slug>/` (напр. `aralov_1on1`). `kind` остаётся `one_on_one`. Конфликты имён файлов — сохранять оба, добавляя суффикс `_person` файлам из People (напр. `card.md` из People → `person_card.md`, если в 1-1 уже есть свой `card.md`) |
| `People/<ФИО>/` без 1-1 (4 чел.: Алексеева, Котельникова, Малый, Перетяткова) | добавить запись `kind: person` в реестр со slug'ами из Q2 (`alekseeva`, `kotelnikova`, `maly`, `peretyatkova`), содержимое → `Entities/<slug>/` |

### 4.3 entities.json — что дополнить

1. Добавить `folder: "Entities/<slug>"` во все записи, кроме `kind: tool` (там `folder: null`).
2. Добавить 4 записи `kind: person` для people без 1-1 (Q2).
3. Обработать 9 папок без реестра (Q4): 8 алиасов + 1 новая запись `alpha`; `sr-tool` — без записи, папка удаляется.
4. **Удалить** записи `tsu` и `vstrechi_nerazobrannoe` (`kind: unknown`, Q9).
5. Создать запись `pmo` (`kind: project` или новый `kind: knowledge_base` — уточняется при реализации) под контейнер методологии.
6. Bump `schema_version` → `"1.1"`.

## §5 Правила для новых сущностей (после миграции)

- Создание сущности через Сирень или CLI `entity-registry create` — атомарно:
  1. валидируется slug (regex `^[a-z0-9_]+$`);
  2. создаётся папка `Entities/<slug>/` + `card.md` из шаблона `_templates/entity/card.md`;
  3. добавляется запись в `entities.json` (с `folder`);
  4. запись в лог `Registries/_log/entities.log`.
- **Slug не найден в реестре** → Сирень **не создаёт молча, не гадает** — задаёт Саше уточняющий вопрос текстом («нашла папку/упоминание X, в реестре нет — создать новую сущность или это алиас существующей?»). Существующий контракт MoveFromLoop v0.3 уже такой; распространяется на всех потребителей.
- Кириллица и дефисы в именах папок под `Entities/` запрещены fail-loud (валидатор в CLI + pre-commit).
- `kind: tool` — папка в `Entities/` **не создаётся**, только запись в реестре.

## §6 Алгоритм миграции (пошагово, обратимый)

Принцип: **всё через копирование**, оригинал удаляется только после чек-листа §6.7. Симлинки для обратной совместимости **не создаются** (Q6).

### 6.1 Подготовка

1. Создать бэкап: `cp -a WorkVault WorkVault_backup_pre_entities_$(date +%Y%m%d)`.
2. Создать пустое дерево `WorkVault/Entities/`.
3. Создать `WorkVault/_templates/entity/` из `Projects/_template/`.
4. Убедиться, что в Obsidian включена опция «Automatically update internal links» (Q7).

### 6.2 Дополнить `entities.json`

Скрипт `scripts/migrate_entities/01_extend_registry.py`:
- добавить `folder` во все записи (`kind: tool` → `null`, остальные → `Entities/<slug>`);
- удалить записи `tsu`, `vstrechi_nerazobrannoe` (Q9);
- добавить 4 person-записи с фиксированными slug'ами из Q2;
- обработать Q4:
  - для 8 алиасов (`ai-mas`, `chatbot`, `okr-tool`, `parsery`, `parsing-zhd`, `vestnik-aid`, `ai-transformaciya` → соответствующие цели; см. Q4) — добавить исходное имя в `aliases` целевой записи, новую запись НЕ создавать;
  - создать новую запись `alpha` (kind: project, display_name: «Альфа», folder: `Entities/alpha`);
- добавить запись `pmo` под методологию;
- bump `schema_version` → `1.1`.

Ревью diff'а вручную, коммит.

### 6.3 Копирование Projects (проекты, 1-1, multisync, sync_aid)

`scripts/migrate_entities/02_copy_projects.py`:
```python
for slug, meta in registry.items():
    if meta["kind"] == "tool":
        continue  # tools — только реестр, папка не создаётся (Q10)
    src_dir_candidates = [WV / "Projects" / slug] + [WV / "Projects" / a for a in meta.get("aliases", [])]
    src_md_candidates  = [WV / "Projects" / f"{slug}.md"] + [WV / "Projects" / f"{a}.md" for a in meta.get("aliases", [])]
    dst = WV / "Entities" / slug
    dst.mkdir(parents=True, exist_ok=True)
    for src_dir in src_dir_candidates:
        if src_dir.is_dir():
            copytree(src_dir, dst, dirs_exist_ok=True)
    for src_md in src_md_candidates:
        if src_md.exists():
            # Q3: плоский .md сохраняет своё имя, НЕ переименовывается в card.md
            copy(src_md, dst / src_md.name)
    if not (dst / "card.md").exists():
        # создать card.md из шаблона с базовым frontmatter из реестра
        render_card_from_template(dst / "card.md", meta)
```

Отдельная обработка `sr-tool` — папка пустая, не копируется, оригинал удаляется на шаге 6.7.

### 6.4 Копирование People

`scripts/migrate_entities/03_copy_people.py`:
- маппинг ФИО → slug (жёстко, из Q1+Q2):
  - `Аралов Александр` → `aralov_1on1`
  - `Набиева Даяна` → `dayana_1on1`
  - `Середа Илья` → `ilya_1on1`
  - `Криворотов Кирилл` → `kirill_1on1`
  - `Жиров …` → `zhirov_1on1`
  - `Алексеева Юлия` → `alekseeva`
  - `Котельникова Ольга` → `kotelnikova`
  - `Малый Денис` → `maly`
  - `Перетяткова Екатерина` → `peretyatkova`
- для каждой папки `People/<ФИО>/` — copytree в `Entities/<slug>/`;
- при конфликте имён (в 1-1 уже лежит `card.md`, в People тоже `card.md`) — файл из People сохраняется с префиксом `person_` (напр. `person_card.md`); `context.md`, `risks.md`, `status_snapshot.md`, `contract_vendor.md` — обычно уникальны, копируются как есть.

### 6.5 Обработка Pages / служебных

`scripts/migrate_entities/04_move_pages.py`:
- для каждого файла в `Projects/Pages/*.md` определить slug по префиксу имени (`<slug>_brief.md`, `<slug>_charter.md`, `<slug>_report.md`);
- если slug найден в реестре (с учётом aliases) → `Entities/<slug>/Pages/<исходное_имя>.md`;
- нераспознанные → `Entities/pmo/Pages/<исходное_имя>.md` (Q5);
- `Projects/Pages/PMO/` целиком → `Entities/pmo/Pages/PMO/`;
- `Projects/Pages/_index.json` → `Entities/pmo/Pages/_index.json`;
- `Projects/_template/` → `WorkVault/_templates/entity/`;
- `Projects/_research/` — удалить (Q8);
- `Projects/Trisigma  вопросы.md` → `Entities/trisigma/Trisigma_вопросы.md`.

### 6.6 Верификация

`scripts/migrate_entities/05_verify.py`:
- для каждой записи реестра с `folder != null` — папка существует и содержит `card.md`;
- в `Entities/<slug>/` нет кириллицы и дефисов в имени;
- количество файлов до/после совпадает (или явно перечислены удалённые: `sr-tool/`, `_research/`);
- ни один файл из `Projects/`/`People/` не потерян (checksum-сверка через find + sha256sum);
- `kind: tool` записи имеют `folder: null` и в `Entities/` папок не имеют.

Отчёт в `Registries/_log/entities_migration_$(date +%Y%m%d).md`.

### 6.7 Удаление старого (только после ✅ верификации)

- `rm -rf WorkVault/Projects/` (Q6: без симлинков);
- `rm -rf WorkVault/People/`.

### 6.8 Обновить потребителей

- `workvault-rag` (Cursor skill) — заменить пути в поисковых шаблонах: `Projects/**`, `People/**` → `Entities/**`;
- MOFS — dry-run на 10 встречах (использует slug'и, но проверить, что нигде не хардкодит пути);
- MoveFromLoop — обновить target `Entities/<slug>/Messages/`;
- **Obsidian wikilinks не переписываем вручную** (Q7): при первом открытии vault с включённой опцией «Automatically update internal links» Obsidian сам обновит `[[People/…]]` и `[[Entities/…/card]]` на новые пути. Ручной sed-скрипт не пишем; после открытия vault — глазами проверить 5-10 случайных заметок и `git diff` по vault.

## §7 Что НЕ трогать

- `WorkVault/Meetings/` — встречи остаются как есть (сущности ссылаются на них, но не хранят).
- `WorkVault/Confluence/` — зеркало Confluence, не наше.
- `WorkVault/Contacts/` — реестр контактов, отдельная зона ответственности AnywhereContacts.
- `WorkVault/Rooms/`, `WorkVault/Tasks/`, `WorkVault/Inbox/`, `WorkVault/News/`, `WorkVault/Personal/`, `WorkVault/UserManuals/`, `WorkVault/Tools/`, `WorkVault/ProtocolFromSummary/`, `WorkVault/Conferences/`, `WorkVault/_meta/`, `WorkVault/_test/`, `WorkVault/Home.md`, `WorkVault/pages.json`, `WorkVault/MAIN_WORKVAULT_INVENTORY.md`.
- Записи `entities.json` — дополняем поле `folder`, удаляем только `tsu` и `vstrechi_nerazobrannoe` (Q9), остальные существующие записи сохраняются (только меняем `aliases` и добавляем `folder`).

## §8 Связи с экосистемой

| Компонент | Влияние | Действие |
|---|---|---|
| **EntityRegistry** (v0.2.0) | Схема реестра меняется: +`folder`, `schema_version` 1.0→1.1, добавляются person-записи, удаляются 2 unknown | Обновить ТЗ EntityRegistry (v0.3.0), CLI validate, документацию |
| **EntityRegistryCLI** | `create` создаёт папку в `Entities/` (кроме `kind: tool`), `validate` проверяет folder exists | Патч + тесты |
| **MOFS** | Матчер использует slug/aliases из реестра — не хардкодит пути. Aliases расширяются (Q4) — регресс-тест | dry-run + regress-тест на 50 встречах |
| **MofsIndex** | Хранит slug'и в FTS — путь к card.md для отчётов может браться из `folder` | dry-run |
| **ProtocolFromSummary** | Публикует в Confluence, читает `entities.json` для ROUTES — не читает Projects/People напрямую | не затронут (проверить `page_id` резолвинг) |
| **TaskRefresh** | ProjectRegistry читается из entities.json — не затронут | проверить, что `folder` игнорируется старым кодом |
| **MoveFromLoop** (draft v0.3) | Целевые пути `Entities/<slug>/Messages/` — фиксируется в этом ТЗ | синхронизировать v0.4 |
| **workvault-rag** (Cursor skill) | Ищет по путям `Projects/`, `People/` | Обновить skill: `Entities/**` |
| **Obsidian vault** | wikilinks `[[People/…]]`, `[[Entities/…/card]]` | Автообновление Obsidian при первом открытии (Q7); ручной rewrite не нужен |
| **AggregateFromMeetings** | Читает summary из Meetings/, не Projects/People | не затронут |
| **AnywhereContacts** | Contacts.enc — отдельно, не затронут | — |

## §9 Решения брифа (23.07.2026)

Все 10 вопросов из v0.1.0 закрыты. Формулировки решений — от Саши, зафиксированы дословно по смыслу.

**Q1 — 1-1 vs person, одна сущность или две?**
→ **merge**: одна папка на человека. `kind` остаётся `one_on_one` для тех, с кем идут регулярные 1-1 (5 человек); для остальных 4 — `kind: person`. Отдельных `person`-записей для тех, у кого уже есть 1-1, **не создаём**.

**Q2 — slug'и для 4 people без 1-1:**
- `alekseeva` — Алексеева Юлия
- `kotelnikova` — Котельникова Ольга
- `maly` — Малый Денис
- `peretyatkova` — Перетяткова Екатерина

**Q3 — плоские `.md` файлы:** плоский файл сохраняет своё исходное имя и переезжает внутрь папки сущности. Пример: `Projects/trisigma.md` → `Entities/trisigma/trisigma.md`. **НЕ переименовывать** в `card.md`. `card.md` создаётся отдельно из шаблона, если его ещё нет.

**Q4 — 9 папок без записи в реестре:**
- `ai-mas` → **алиас** к `ai_analitik`
- `alpha` → **новая запись** (kind: project, display_name: «Альфа»)
- `chatbot` → **алиас** к `ai_analitik`
- `okr-tool` → **алиас** к `okr`
- `sr-tool` → **удалить** папку (пустая)
- `parsery` → **алиас** к `parsing`
- `vestnik-aid` → **алиас** к `vestnik`
- `ai-transformaciya` → **алиас** к `ai_ready`
- `parsing-zhd` → **алиас** к `parsing`

**Q5 — Pages/:** каждый файл `Projects/Pages/*.md` переезжает в `Entities/<slug>/Pages/` соответствующего проекта — slug определяется по префиксу имени файла (`trisigma_brief.md` → `Entities/trisigma/Pages/trisigma_brief.md`). Нераспознанные файлы → `Entities/pmo/Pages/`. Подпапка `PMO/` (методология) целиком → `Entities/pmo/Pages/PMO/`.

**Q6 — обратная совместимость симлинками:** **нет**. Чистый перенос, старые папки `Projects/` и `People/` удаляются после верификации.

**Q7 — Obsidian wikilinks:** ручной rewrite **не нужен**. Obsidian обновит внутренние ссылки автоматически при первом открытии vault (в настройках включена опция «Automatically update internal links»). После открытия — глазами проверить 5-10 случайных заметок и `git diff` по vault.

**Q8 — `Projects/_research/`:** удалить (пустая папка).

**Q9 — `kind: unknown`:** удалить записи `tsu` и `vstrechi_nerazobrannoe` из `entities.json`. Значение `unknown` уходит из схемы.

**Q10 — `kind: tool`:** папки в `Entities/` для инструментов **не создаются** — только запись в реестре. Поле `folder` = `null`.

---

## Доработка: EntitiesMigration — РЕАЛИЗОВАНО (2026-07-24)

Миграция выполнена автоматически (Сирень/Sonnet), 2026-07-24:
- entities.json обновлён до v1.1: добавлены алиасы, 4 person-записи, alpha, pmo; удалены tsu и vstrechi_nerazobrannoe; поле folder проставлено для всех записей
- WorkVault/Entities/ создана, 30 папок сущностей
- Projects/ и People/ удалены после верификации
- Pages/ разложены по Entities/<slug>/Pages/
- _template/ скопирован в _templates/entity/
- Бэкап: ~/WorkVault_backup/Hermes-Backlog/TZ/EntitiesMigration/pre-migration-20260724-0552.tgz

## История доработок

- 2026-07-23 — v0.1.0, первый черновик (Opus): AS-IS, TO-BE, алгоритм миграции, 10 открытых вопросов Саше.
- 2026-07-23 — v0.2.0, решения брифа Саши: закрыты все 10 вопросов (§9), обновлены §2 (AS-IS с конкретными списками), §3 (TO-BE с merge-логикой и без папок для tools), §4 (пошаговые действия по кейсам), §5 (правило «slug не найден → Сирень спрашивает»), §6 (алгоритм с учётом всех решений, без симлинков, без ручного rewrite wikilinks).
- 2026-07-24 — реализация (Сирень/Sonnet): выполнена полная миграция, status → completed.
