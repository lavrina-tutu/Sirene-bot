---
type: tz
title: Система хранения и работы с ТЗ (Hermes/USERTOOLS)
version: 1.1
date: 2026-07-03
author: Сирень (по заданию Саши Ткаченко)
tool: TZ-storage-system
status: active
last-section-added: 2026-07-03
scope: WorkVault/Hermes-Backlog, WorkVault_backup, USERTOOLS, WorkVault/Tools/AggregateFromMeetings
changelog:
  - 2026-07-03 v1.0: первичная версия
  - 2026-07-03 v1.1: правки после ревью Саши — латиница во всех новых именах файлов/папок; устранены противоречия §3↔§6, §4↔§9; учтено правило "версия только во frontmatter"; добавлен шаг бэкапа перед миграцией; добавлена проверка ссылок на старые пути; добавлен раздел §14 "Открытые вопросы Саше"
---

# ТЗ — Единая система хранения и работы с техническими заданиями

## 1. Цель

Навести единый порядок хранения, версионирования и архивации всех технических заданий (ТЗ) по инструментам Hermes/USERTOOLS. Устранить разброс ТЗ по трём разным местам, ввести единую точку правды, единый реестр и машиночитаемые правила, которые сможет применять любая LLM — как локальная (Hermes на ВМ), так и внешняя (Cursor на ноутбуке через синхронизированный WorkVault).

## 2. Контекст (кратко)

Сейчас ТЗ живут в трёх разных местах без общей схемы:

- `WorkVault/Hermes-Backlog/` (корень) — активные ТЗ вперемешку с реестрами, аналитикой и PMO-файлами.
- `WorkVault/Hermes-Backlog/_Done/` — архив завершённых точечных ТЗ (4 файла по MoveFromFF от 27.05.2026).
- `USERTOOLS/<tool>/<Tool>_TZ_vX.Y.md` — «живое» master-ТЗ каждого инструмента лежит в папке самого инструмента (правило от 27.05.2026, эталон — `USERTOOLS/MoveFromFF/MoveFromFF_TZ_v2.1.md`, 292 строки, живой файл дописывается секциями). **Внимание:** в имени этого файла зашита версия `v2.1` — противоречит вводимому §4 правилу «версия только во frontmatter». См. §14 (открытые вопросы).
- `WorkVault/Tools/AggregateFromMeetings/` — отдельный инструмент со своей сложной структурой (main + modules + pm/sessions + checklist), master v1.8.
- `~/WorkVault_backup/` — уже существует с 02.07.2026, не синхронизируется с ownCloud (rclone таргетит только `~/WorkVault/`, backup лежит вне этого пути — exclude-лист не нужен), уже содержит правила `_Backup-Rules.md` и 21 перенесённый устаревший файл (лог `_moved-2026-07-02.log`).
- `~/WorkVault/2026-07-02_WORKVAULT_INVENTORY.md` — отчёт инвентаризации от 02.07.2026.

Задача — свести всё активное в одну точку `WorkVault/Hermes-Backlog/TZ/<Tool>/`, всё устаревшее в `~/WorkVault_backup/` по существующим правилам, поднять два индекса (`MAIN_TZ_INVENTORY.md` и `MAIN_WORKVAULT_INVENTORY.md`) и оформить процесс как скилл + машиночитаемый файл правил в самом vault.

**Вне скоупа:** git-репозитории `hermes-config-repo/`, `hermes-config/`, `hermes-workspace/` (там свои старые копии ТЗ — история git-синка Hermes-конфига, не трогать); рабочие данные `Projects/`, `People/`, `Meetings/`, `Contacts/` — не трогать.

## 2A. Требование к именам файлов/папок (Obsidian-vault)

**Все новые имена файлов и папок внутри WorkVault — ТОЛЬКО латиница (ASCII).** Кириллица в путях внутри Obsidian-вольта создаёт broken wiki-links, ломает сортировку и поиск. Правило действует для:

- всех новых master-ТЗ (`<Tool>_TZ.md`);
- всех новых точечных ТЗ (`TZ-<topic>-<YYYYMMDD>.md` — topic латиницей, транслит или английский перевод);
- всех вспомогательных файлов (`_TZ-WORKFLOW-RULES.md`, `MAIN_TZ_INVENTORY.md` и т.п.).

Уже существующие архивные файлы с кириллическими именами (`ТЗ-MoveFromFF-*.md` в `_Done/`, сам этот файл ТЗ) — их судьба зафиксирована в §14 как открытые вопросы (переименовывать при переносе или оставить).

## 3. Целевая структура папок

```
~/WorkVault/                                              # синхронизируется (ownCloud/rclone)
├── MAIN_WORKVAULT_INVENTORY.md                           # общий инвентарь vault (переим. из 2026-07-02_WORKVAULT_INVENTORY.md)
├── Hermes-Backlog/
│   ├── TZ/                                               # ← ЕДИНАЯ точка правды для всех активных ТЗ
│   │   ├── _TZ-WORKFLOW-RULES.md                         # машиночитаемые правила для любой LLM
│   │   ├── MAIN_TZ_INVENTORY.md                          # реестр всех ТЗ по инструментам
│   │   ├── _misc/                                        # точечные ТЗ не привязанные к инструменту
│   │   │   └── TZ-<topic>-<YYYYMMDD>.md                  # только латиница
│   │   ├── MoveFromFF/
│   │   │   └── MoveFromFF_TZ.md                          # живой master-файл (версия/дата в шапке)
│   │   ├── AggregateFromMeetings/
│   │   │   ├── TZ_aggregate_main.md
│   │   │   ├── BUILD_CHECKLIST.md
│   │   │   ├── modules/
│   │   │   │   ├── TZ_A_*.md ... TZ_H_*.md
│   │   │   └── pm/
│   │   │       ├── PM_DECISIONS_LOG.md
│   │   │       └── sessions/*.md
│   │   └── <OtherTool>/
│   │       └── <OtherTool>_TZ.md
│   ├── (реестры, аналитика, PMO — как было, ТЗ отсюда уезжают в TZ/)
│   └── _Done/                                            # опустеет после миграции (файлы уедут в backup)
└── ... (Projects/, People/, Meetings/, Contacts/ — не трогаем)

~/WorkVault_backup/                                       # НЕ синхронизируется, только ВМ
├── _Backup-Rules.md                                      # актуализируется под новую схему
├── _moved-YYYY-MM-DD.log                                 # журнал всех переносов
├── Hermes-Backlog/
│   ├── TZ/
│   │   ├── MoveFromFF/
│   │   │   ├── MoveFromFF_TZ_v2.1_20260527.md            # снапшоты старых версий (версия в имени — только у архивных!)
│   │   │   └── MoveFromFF_TZ_snapshots-YYYYMMDD.tgz
│   │   └── AggregateFromMeetings/
│   │       ├── tz-final-qc-20260630-1500.tgz             # переехавший эталонный снапшот
│   │       └── ...
│   └── _Done/                                            # старые точечные ТЗ из бывшего _Done/
│       └── (см. §14 п.2 — судьба кириллических имён обсуждается)
└── USERTOOLS/                                            # старые *_TZ_v*.md из папок инструментов
    └── MoveFromFF/
        └── MoveFromFF_TZ_v2.0_YYYYMMDD.md
```

Структура backup **зеркалит** относительные пути WorkVault — как и требует существующий `_Backup-Rules.md`.

### 3.1 Что НЕ кладётся в `TZ/<Tool>/`

`TZ/<Tool>/` — это **только про сам документ ТЗ** (master + модули, которые являются его частями, + `pm/` как журнал решений по этому ТЗ). Всё остальное, что порождается или потребляется инструментом, живёт в его собственной директории:

- Код-инструменты (Python-пакеты) → `USERTOOLS/<Tool>/`
- Vault-инструменты (данные и конфиг в vault) → `WorkVault/Tools/<Tool>/`

Никогда не переезжают в `TZ/<Tool>/`:
- `briefs/` — исходники брифов (переписки, дампы обсуждений, из которых родилось ТЗ). Хранятся в структуре инструмента.
- `research/` — research-заметки/brainstorm.
- `_review/` — артефакты QA-агентов, отчёты по патчам.
- `*.json` runtime-state — `classification_memory.json`, `syncs_memory.json`, кэши, история решений инструмента.
- `_sandbox/` — тестовые снэпшоты, sample-входы.
- Логи, временные файлы.

Правило: если файл — *описание того, что должен делать инструмент* → `TZ/<Tool>/`. Если файл — *то, что инструмент ест или производит*, либо *входной материал, который LLM разжёвывала, готовя ТЗ* → директория инструмента.

Формально это же правило продублировано в машиночитаемом `_TZ-WORKFLOW-RULES.md` (обязательный для чтения любой LLM, работающей с vault).

## 4. Правило именования файлов ТЗ

**Один живой master-файл на инструмент**, дописывается новыми секциями по датам. Версия в имя файла **НЕ** зашивается — она живёт только в шапке.

- Имя файла: `<Tool>_TZ.md` (например `MoveFromFF_TZ.md`; для составных ТЗ — сохраняются оригинальные имена, см. Исключение ниже).
- Имя инструмента и файла — **только латиница**, без пробелов и кириллицы.
- В шапке YAML-frontmatter:
  ```yaml
  ---
  tool: MoveFromFF
  version: 2.1
  date: 2026-05-27
  status: active
  last-section-added: 2026-06-15  # опционально
  ---
  ```
- Новые доработки → **дописываются секциями в конец** (как §10 Дедупликация, §11 Санитизация в MoveFromFF), с датой в подзаголовке.
- Секция «Планируемая доработка» / draft — в самом низу, до подтверждения PM.
- **НЕ множим** файлы `v1.md`, `v2.md`, `v3.md` в активной папке. Такие файлы — признак старой схемы, их место в backup.

**Точечные ТЗ (не привязаны к инструменту):** имя `TZ-<topic>-<YYYYMMDD>.md`, где `<topic>` — латиница (транслит или английский перевод русского термина).

**Исключение:** составные ТЗ (типа AggregateFromMeetings) сохраняют внутреннюю структуру `main + modules/ + pm/` — переносится как есть, единый master — файл `TZ_aggregate_main.md`.

**Соответствие правилу «версия только во frontmatter»:** старое имя `MoveFromFF_TZ_v2.1.md` содержит версию — это старая схема. При переносе в новую точку правды файл должен быть переименован в `MoveFromFF_TZ.md` (версия 2.1 переезжает в frontmatter). См. §14 п.1 — это открытый вопрос: подтвердить переименование или оставить старое имя.

## 5. Правило архивации

База — существующий `~/WorkVault_backup/_Backup-Rules.md`, дополнить под новую схему:

**Когда переносить в backup:**
1. Перед крупной правкой активного ТЗ (>20% содержимого, смена версии major) — сделать `tgz`-снапшот всей папки инструмента в `WorkVault_backup/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz`.
2. Перед мелкой правкой важного ТЗ — положить `.bak` рядом с оригиналом (не в vault, в backup, тем же путём).
3. Когда старая версия ТЗ полностью перекрыта новой (например, v2.0 → v2.1) — переносим старый файл в backup с суффиксом даты: `<Tool>_TZ_v<old>_YYYYMMDD.md` (**в имени архивной копии версия допустима — это дескриптор снапшота, не действующий файл**).
4. Когда сам инструмент выведен из эксплуатации/удалён (не просто доработка реализована!) — переносим всю папку `WorkVault/Hermes-Backlog/TZ/<Tool>/` в `WorkVault_backup/Hermes-Backlog/TZ/_archived/<Tool>/`, в `MAIN_TZ_INVENTORY.md` меняем статус на `archived`. **Пока инструмент используется — его ТЗ навсегда остаётся в WorkVault, реализация отдельной доработки не повод для архивации.** Решение принимает только Саша явно, без автотаймера (см. §14 п.4).

**Именование архивных файлов:**
- Точечные снапшоты старых версий: `<OriginalName>_YYYYMMDD.md`
- tgz-архивы папок: `<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz`
- `.bak` перед правкой: `<OriginalName>.bak` (перезаписывается)

**Сколько версий держать (из существующих правил, подтверждаем):**
- `tgz`-архивы ТЗ на инструмент — **последние 5**, старше — удалять с записью в лог.
- `.bak` одного файла — **последний 1** (перезапись).
- Устаревшие `.md`-версии — **бессрочно**, пока PM явно не скажет чистить.
- Opus/legacy прогоны — **бессрочно**.

**Журнал:** каждая операция переноса/удаления пишется в `~/WorkVault_backup/_moved-YYYY-MM-DD.log` (одна дата = один файл, дозаписывается).

**Что НЕ архивируем, а удаляем сразу:** явный мусор (пустые файлы, дубли с идентичным содержимым, случайно созданные `.md~`).

## 6. Пошаговый план миграции

Ничего не удаляем — только переносим и создаём. Порядок:

### Фаза 0 — подготовка (без переносов)

0. **[Обязательный шаг перед стартом миграции — из правил hermes-feature Блок 5]** Создать полный бэкап затрагиваемых деревьев ДО первой операции:
   ```
   tar czf ~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/pre-tz-migration.tgz \
       ~/WorkVault/Hermes-Backlog ~/USERTOOLS/*/[A-Za-z]*_TZ*.md \
       ~/WorkVault/Tools/AggregateFromMeetings ~/WorkVault_backup
   ```
   Убедиться, что архив создан и читается. Только после этого продолжать.
1. Создать пустую директорию `~/WorkVault/Hermes-Backlog/TZ/` и подпапку `TZ/_misc/`.
2. Создать в ней `_TZ-WORKFLOW-RULES.md` (см. §10) и пустой `MAIN_TZ_INVENTORY.md` (см. §7).
3. Актуализировать `~/WorkVault_backup/_Backup-Rules.md` — дописать раздел про новую схему `Hermes-Backlog/TZ/`.
4. Переименовать `~/WorkVault/2026-07-02_WORKVAULT_INVENTORY.md` → `~/WorkVault/MAIN_WORKVAULT_INVENTORY.md`, обновить содержимое под новую структуру (см. §8).

### Фаза 1 — перенос активных master-ТЗ в `TZ/<Tool>/`

| Источник | Назначение | Действие |
|---|---|---|
| `USERTOOLS/MoveFromFF/MoveFromFF_TZ_v2.1.md` | `WorkVault/Hermes-Backlog/TZ/MoveFromFF/MoveFromFF_TZ.md` | скопировать + обновить frontmatter (version: 2.1, date: 2026-05-27), убрать `v2.1` из имени. **Судьба исходника в USERTOOLS — см. §14 п.3** |
| `WorkVault/Tools/AggregateFromMeetings/TZ_aggregate_main.md` | `WorkVault/Hermes-Backlog/TZ/AggregateFromMeetings/TZ_aggregate_main.md` | переместить целиком |
| `WorkVault/Tools/AggregateFromMeetings/modules/*.md` | `WorkVault/Hermes-Backlog/TZ/AggregateFromMeetings/modules/*.md` | переместить папку |
| `WorkVault/Tools/AggregateFromMeetings/pm/*` | `WorkVault/Hermes-Backlog/TZ/AggregateFromMeetings/pm/*` | переместить папку |
| `WorkVault/Tools/AggregateFromMeetings/BUILD_CHECKLIST.md` | `WorkVault/Hermes-Backlog/TZ/AggregateFromMeetings/BUILD_CHECKLIST.md` | переместить |
| `WorkVault/Hermes-Backlog/ТЗ-MoveFromFF-apps-preview-summary.md` (актив в корне) | `WorkVault/Hermes-Backlog/TZ/MoveFromFF/` (влить как секцию в master) ИЛИ `TZ/_misc/TZ-MoveFromFF-apps-preview-summary-<date>.md` (латиница) | по одному, с уточнением у Саши |
| Прочие активные ТЗ в корне `WorkVault/Hermes-Backlog/` (если найдутся) | `TZ/<Tool>/<Tool>_TZ.md` или `TZ/_misc/TZ-<topic>-<YYYYMMDD>.md` | по одному, с уточнением у PM |

Прочие USERTOOLS-инструменты, у которых сейчас есть `*_TZ_v*.md` — перебрать по списку, для каждого создать `TZ/<Tool>/<Tool>_TZ.md` из последней версии.

### Фаза 2 — перенос устаревших/завершённых ТЗ в backup

| Источник | Назначение |
|---|---|
| `WorkVault/Hermes-Backlog/_Done/ТЗ-MoveFromFF-dedup-20260527.md` | `~/WorkVault_backup/Hermes-Backlog/_Done/…` (имя — см. §14 п.2) |
| `WorkVault/Hermes-Backlog/_Done/ТЗ-MoveFromFF-backfill-20260527.md` | `~/WorkVault_backup/Hermes-Backlog/_Done/…` |
| `WorkVault/Hermes-Backlog/_Done/ТЗ-MoveFromFF-reconciliation-20260527.md` | `~/WorkVault_backup/Hermes-Backlog/_Done/…` |
| `WorkVault/Hermes-Backlog/_Done/ТЗ-MoveFromFF-summary-fields-20260527.md` | `~/WorkVault_backup/Hermes-Backlog/_Done/…` |
| Старые `*_TZ_v<old>*.md` из `USERTOOLS/<tool>/` (если есть версии ниже актуальной) | `~/WorkVault_backup/USERTOOLS/<tool>/<name>_YYYYMMDD.md` |
| `~/WorkVault_backup/Tools/AggregateFromMeetings/_archive/tz-final-qc-20260630-1500.tgz` | `~/WorkVault_backup/Hermes-Backlog/TZ/AggregateFromMeetings/tz-final-qc-20260630-1500.tgz` (перекладываем в новую зеркальную структуру) |

Всё, что уже лежит в `~/WorkVault_backup/` от 02.07.2026 (21 файл) — оставить, где лежит, только при необходимости привести пути к новой зеркальной структуре и обновить лог.

### Фаза 2A — проверка/обновление ссылок на старые пути

**До Фазы 3** пройтись по всем местам, где могут быть жёстко зашиты старые пути ТЗ:

1. `~/.hermes/` — все скиллы, MEMORY.md, USER.md, jobs.json (cron-промпты). Поиск:
   ```
   search_files(pattern="USERTOOLS/MoveFromFF/MoveFromFF_TZ|WorkVault/Tools/AggregateFromMeetings|Hermes-Backlog/_Done/ТЗ-|Hermes-Backlog/ТЗ-", path="~/.hermes")
   ```
2. `~/WorkVault/Hermes-Backlog/skills-registry.md`, `crons-registry.md`, `PMO-analysis.md` — обновить ссылки на ТЗ.
3. Скилл `hermes-feature` (`~/.hermes/skills/devops/hermes-feature/SKILL.md`) — содержит правила:
   - Блок 0: `WorkVault/Hermes-Backlog/ТЗ-[название].md` — **обновить** на `WorkVault/Hermes-Backlog/TZ/_misc/TZ-<topic>-<YYYYMMDD>.md` (для точечных) или `TZ/<Tool>/<Tool>_TZ.md` (для master).
   - Блок 4: `_Done/ТЗ-[название]-YYYYMMDD.md` — **обновить** траекторию: точечные ТЗ переезжают из `TZ/_misc/` в `~/WorkVault_backup/Hermes-Backlog/_Done/` (не в vault).
   - Питфолл про «master-ТЗ в USERTOOLS/<tool>/» — **обновить** на новую точку правды `WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md`.
4. USERTOOLS-код — grep по `MoveFromFF_TZ`, `TZ_aggregate_main` в исходниках Python (`~/USERTOOLS/**/*.py`).

Все найденные ссылки — обновить в отдельном коммите/операции с записью в лог миграции.

### Фаза 3 — очистка исходников и апдейт индексов
1. После проверки PM удалить опустевший `WorkVault/Hermes-Backlog/_Done/` (папка) — файлы уже в backup.
2. Проверить `WorkVault/Tools/AggregateFromMeetings/` — если пустая, удалить папку или оставить симлинк-заглушку.
3. Записать все операции в `~/WorkVault_backup/_moved-2026-07-03.log`.
4. Заполнить `MAIN_TZ_INVENTORY.md` по итоговому состоянию.
5. Обновить `MAIN_WORKVAULT_INVENTORY.md` — раздел про ТЗ переписать под новую схему.

### Фаза 4 — скилл и рулбук
1. Создать скилл `tz-workflow` (см. §9).
2. Финальная проверка: любая LLM, прочитавшая только `TZ/_TZ-WORKFLOW-RULES.md`, должна корректно создать/дописать/заархивировать ТЗ без дополнительных инструкций.
3. **Явно НЕ рестартовать gateway** в рамках этой миграции — это правило hermes-feature Блок 5А. Никаких cron-рестартов не ставим.

## 7. Формат `MAIN_TZ_INVENTORY.md`

Расположение: `~/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md`.

Обязательные секции:

### 7.1 Шапка
```yaml
---
type: index
title: MAIN TZ INVENTORY
updated: 2026-07-03
maintainer: Hermes + Cursor (совместно, через WorkVault sync)
---
```

### 7.2 Таблица активных ТЗ

| Инструмент | Путь актуального ТЗ | Версия | Дата посл. изменения | Статус | Архив старых версий |
|---|---|---|---|---|---|
| MoveFromFF | `TZ/MoveFromFF/MoveFromFF_TZ.md` | 2.1 | 2026-05-27 | active | `~/WorkVault_backup/Hermes-Backlog/TZ/MoveFromFF/` |
| AggregateFromMeetings | `TZ/AggregateFromMeetings/TZ_aggregate_main.md` | 1.8 | 2026-06-30 | active | `~/WorkVault_backup/Hermes-Backlog/TZ/AggregateFromMeetings/` |
| ... | ... | ... | ... | ... | ... |

### 7.3 Таблица завершённых/архивных ТЗ

| Инструмент | Финальная версия | Дата завершения | Куда переехало |
|---|---|---|---|

### 7.4 Точечные ТЗ (не привязаны к инструменту)
Список одиночных ТЗ вида `TZ-<topic>-<YYYYMMDD>.md`, если такие лежат в `TZ/_misc/`.

Статусы: `active` / `draft` / `paused` / `archived` / `completed`.

## 8. Формат `MAIN_WORKVAULT_INVENTORY.md`

Расположение: `~/WorkVault/MAIN_WORKVAULT_INVENTORY.md` (переименовано из `2026-07-02_WORKVAULT_INVENTORY.md`).

Секции:
1. **Назначение** — что за файл, для кого.
2. **Верхнеуровневая структура WorkVault** — что где лежит: `Hermes-Backlog/`, `Projects/`, `People/`, `Meetings/`, `Contacts/`, `Tools/` и т.п.
3. **ТЗ** — ссылка на `Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md` (без дублирования содержимого).
4. **Backup** — что и по какому принципу вынесено в `~/WorkVault_backup/`, ссылка на `_Backup-Rules.md`.
5. **Синхронизация** — что синкается через ownCloud/rclone, что нет, куда таргетит rclone.
6. **Журнал крупных изменений структуры** — дата, что перестроили, кем.
7. **Что НЕ трогать** — git-репозитории `hermes-config-repo/`, `hermes-config/`, `hermes-workspace/`; рабочие папки Projects/People/Meetings/Contacts.

Файл обновляется при любой перестройке структуры vault (не при каждом мелком изменении внутри рабочих папок).

## 9. Скилл `tz-workflow`

**Роль скилла:** скилл — это **правила для агента**, которые применяет любая модель, работающая с ТЗ. По правилу hermes-feature Блок 0 **сам контент ТЗ (текст) всегда пишет Opus** — Sonnet/другие модели могут править инвентарь, переносить файлы, применять frontmatter, но не генерировать новое содержимое ТЗ. Это ограничение отражено в тексте скилла явно.

**Метаданные (frontmatter — соответствует hermes-agent-skill-authoring):**

```yaml
---
name: tz-workflow
description: "Use when creating, editing, or archiving TZ (technical specs) in WorkVault. Enforces single-master-per-tool layout, YAML frontmatter versioning, and mirrored backup. Triggers: TZ, техническое задание, MoveFromFF_TZ, AggregateFromMeetings, WorkVault/Hermes-Backlog/TZ."
version: 1.0.0
author: agent
tags: [workflow, tz, workvault, hermes]
platforms: [linux, macos, windows]
---
```

- **Не использовать `platforms: [all]`** — по питфоллу hermes-feature это ломает индексацию скилла. Перечислять конкретно.
- **Категория/путь скилла:** `~/.hermes/skills/workflow/tz-workflow/SKILL.md`.
- Объёмные материалы (шаблоны, детальные примеры) — в `templates/` и `references/`, а не в самом SKILL.md (правило hermes-agent-skill-authoring про размер 8–14k символов).
- **Триггеры (в description):** `ТЗ`, `техническое задание`, `technical spec`, работа с файлами `*_TZ*.md`, работа в `WorkVault/Hermes-Backlog/TZ/`, доработка любого USERTOOLS-инструмента, слова `MoveFromFF`, `AggregateFromMeetings` в контексте документации.

**Что скилл делает:**

1. **При создании нового ТЗ для инструмента:**
   - Проверяет, есть ли `TZ/<Tool>/`. Если нет — создаёт.
   - **Написание содержимого делегируется Opus** (по правилу hermes-feature Блок 0). Скилл готовит каркас: пустой файл `TZ/<Tool>/<Tool>_TZ.md` с шаблонным frontmatter и заголовками стандартных разделов (Цель / Шаги / Критерии успеха / Что НЕ трогать — обязательный минимум hermes-feature; далее по образцу MoveFromFF: Источники данных, Алгоритм, Схема, Константы, Коды событий, Уведомления).
   - Добавляет запись-заглушку в `MAIN_TZ_INVENTORY.md`, статус `draft`.

2. **При доработке существующего ТЗ:**
   - Если правка мелкая — просто дописывает новую секцию с датой в конец файла, обновляет `last-section-added` в frontmatter.
   - Если правка крупная (смена major-версии, переписывание больше 20%) — сначала делает `tgz`-снапшот текущего состояния в `WorkVault_backup/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz`, потом правит, потом обновляет frontmatter (`version`, `date`) и `MAIN_TZ_INVENTORY.md`.
   - Содержательные правки (не механические переносы/бампы) — снова через Opus.

3. **При завершении работы над конкретной доработкой:**
   - Обновляет `last-section-added` в frontmatter, дописывает секцию с датой.
   - **ТЗ остаётся `active` и в WorkVault** — завершение доработки не меняет статус на `completed`/`archived`. Master-ТЗ живёт, пока живёт инструмент.
   - Статус `archived` + перенос в `WorkVault_backup/Hermes-Backlog/TZ/_archived/<Tool>/` — только когда сам инструмент выведен из эксплуатации/удалён, и только по явному решению Саши (см. §14 п.4, без автотаймера).

4. **При работе над точечными задачами (не привязанными к инструменту):**
   - Создаёт файл в `TZ/_misc/TZ-<topic>-<YYYYMMDD>.md` (**topic — латиница**).
   - После завершения — переносит в `WorkVault_backup/Hermes-Backlog/_Done/`.

5. **Постоянные инварианты:**
   - Никогда не множит `v1/v2/v3` в активной папке (версия — только во frontmatter).
   - Никогда не использует кириллицу в новых именах файлов/папок.
   - Всегда пишет операции переноса в `~/WorkVault_backup/_moved-YYYY-MM-DD.log`.
   - Всегда синхронизирует изменения с `MAIN_TZ_INVENTORY.md` в той же операции.
   - Не трогает git-репозитории и рабочие данные.
   - **Никакого рестарта gateway** — скилл только правит файлы, инфраструктуру не перезагружает (правило hermes-feature Блок 5А).

**Файлы скилла:**
- `SKILL.md` — описание, триггеры, короткие процедуры + ссылки на `references/`.
- `templates/tool-tz-template.md` — шаблон нового master-ТЗ (frontmatter + стандартные разделы hermes-feature Блок 0).
- `templates/misc-tz-template.md` — шаблон точечного ТЗ.
- `references/archiving.md` — подробные примеры команд tar/mv (если решим не делать bash-скрипт — см. §14 п.5).
- (опционально) `scripts/archive-tz.sh` — bash-обёртка для tgz-снапшота + записи в лог. **Целесообразность — открытый вопрос, §14 п.5.**

## 10. Содержание `TZ/_TZ-WORKFLOW-RULES.md`

Машиночитаемый файл в самом vault (синхронизируется на ноутбук, доступен Cursor и любой другой LLM). Никаких Hermes-специфичных вызовов — только файловые правила.

Структура:

```markdown
---
type: workflow-rules
scope: WorkVault/Hermes-Backlog/TZ
audience: LLM (Hermes, Cursor, любой агент)
version: 1.0
updated: 2026-07-03
---

# TZ Workflow Rules

## Where to put TZ files
- Active master TZ for a tool: WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md
- Composite TZ (like AggregateFromMeetings): keep internal structure inside TZ/<Tool>/
- Ad-hoc / one-off TZ: WorkVault/Hermes-Backlog/TZ/_misc/TZ-<topic>-<YYYYMMDD>.md
- ALL new filenames and folder names — ASCII only (no Cyrillic). Obsidian vault requirement.

## Naming
- One live file per tool. No v1/v2/v3 in filename. Version and date live in YAML frontmatter.
- Frontmatter template: tool, version, date, status, last-section-added

## How to edit
- Small addition: append a new dated section at the end. Bump last-section-added.
- Big rewrite: first snapshot current file (see Archiving), then rewrite, then bump version+date.
- TZ *content* is authored by Opus. Other models handle file mechanics (move, rename, index update, frontmatter bump).

## Archiving (mirror to ~/WorkVault_backup/)
- Path mirrors WorkVault relative path.
- Snapshot before big edits: tgz to WorkVault_backup/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz
- Old superseded versions: WorkVault_backup/.../<Tool>_TZ_v<old>_YYYYMMDD.md (version-in-name allowed for archived copies only)
- Retention: last 5 tgz per tool, last 1 .bak per file, .md versions indefinitely.
- Log every move to ~/WorkVault_backup/_moved-YYYY-MM-DD.log (one file per day, append).
- **A tool's master TZ stays in WorkVault as long as the tool is in use.** Finishing a specific enhancement/feature does NOT move the TZ to backup — it stays `active` and gets a new dated section. Move to WorkVault_backup/Hermes-Backlog/TZ/_archived/<Tool>/ ONLY when the tool itself is decommissioned/deleted, and only on Sasha's explicit instruction. No auto-timer, ever.

## Inventory
- After any structural change to a TZ: update WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md
- After any restructure of vault itself: update WorkVault/MAIN_WORKVAULT_INVENTORY.md

## Do not touch
- ~/hermes-config-repo, ~/hermes-config, ~/hermes-workspace (git repos, out of scope)
- WorkVault/Projects, People, Meetings, Contacts (working data)
- Gateway process — no restart from this workflow. Ever.

## For remote LLMs (e.g. Cursor on laptop)
- ~/WorkVault_backup/ is VM-only, NOT synced. From laptop you see only WorkVault/.
- If archiving is needed, either do it on the VM (via Hermes) or note the intent in MAIN_TZ_INVENTORY.md for later.
```

## 11. Критерии успеха (чеклист)

- [ ] Бэкап `pre-tz-migration.tgz` создан до старта миграции (Фаза 0 п.0).
- [ ] Папка `WorkVault/Hermes-Backlog/TZ/` создана и содержит подпапку на каждый активный инструмент + `_misc/`.
- [ ] Ни в `WorkVault/Hermes-Backlog/` корне, ни в `USERTOOLS/<tool>/`, ни в `WorkVault/Tools/AggregateFromMeetings/` больше не лежит ни одного активного `*_TZ*.md`.
- [ ] Все новые имена файлов/папок в `TZ/` — только латиница.
- [ ] `WorkVault/Hermes-Backlog/_Done/` пуст или удалён, все 4 файла — в `~/WorkVault_backup/Hermes-Backlog/_Done/`.
- [ ] `MAIN_TZ_INVENTORY.md` содержит все инструменты с корректными путями, версиями и датами.
- [ ] `MAIN_WORKVAULT_INVENTORY.md` существует (переименован), актуален, содержит ссылку на MAIN_TZ_INVENTORY.
- [ ] `_TZ-WORKFLOW-RULES.md` лежит в `TZ/` и достаточен для внешней LLM без доп. контекста.
- [ ] `_Backup-Rules.md` обновлён под новую схему.
- [ ] Скилл `tz-workflow` установлен, виден в `hermes skills list`, триггерится на ключевые слова.
- [ ] Все ссылки на старые пути ТЗ в `~/.hermes/` (скиллы, MEMORY, cron-промпты) и в реестрах Hermes-Backlog обновлены (Фаза 2A).
- [ ] Скилл `hermes-feature` (Блок 0, Блок 4, питфолл про master-ТЗ) обновлён на новые пути.
- [ ] Все операции переноса залогированы в `~/WorkVault_backup/_moved-2026-07-03.log`.
- [ ] Gateway НЕ рестартовался в ходе миграции.
- [ ] Проведён smoke-тест: попросить чистую LLM-сессию создать новое ТЗ для гипотетического инструмента `TestTool` — она должна положить его строго в `TZ/TestTool/TestTool_TZ.md` (латиница) и добавить строку в инвентарь.

## 12. Что НЕ трогать

- Git-репозитории: `~/hermes-config-repo/`, `~/hermes-config/`, `~/hermes-workspace/` — там свои копии ТЗ (v1, v1.1, v2.0) как история git-синка Hermes-конфига. Вне скоупа этого ТЗ.
- Рабочие данные vault: `WorkVault/Projects/`, `WorkVault/People/`, `WorkVault/Meetings/`, `WorkVault/Contacts/` — только чтение и упоминание в общем инвентаре.
- Всё, что уже лежит в `~/WorkVault_backup/` от 02.07.2026 (21 файл), — оставляем как есть; при необходимости только уточняем зеркальность путей и дописываем лог.
- Процесс gateway — никаких рестартов в рамках миграции.

## 13. Риски и порядок действий

**Риски:**
1. **Потеря живых правок при перемещении.** → Митигация: `cp -a` вместо `mv` на первом проходе, удалять оригинал только после ручной проверки PM. Плюс общий бэкап Фазы 0.
2. **Ссылки на старые пути в скиллах/скриптах Hermes.** → Митигация: явная Фаза 2A с поиском и обновлением (см. §6).
3. **Cursor на ноутбуке не знает про новые правила.** → Митигация: `_TZ-WORKFLOW-RULES.md` лежит в синкаемом vault; после первого синка ноут его видит.
4. **Расхождение MAIN_TZ_INVENTORY.md с реальностью.** → Митигация: скилл обязан обновлять инвентарь в той же операции, что и правку ТЗ; периодический аудит (можно поставить cron раз в неделю).
5. **Составная структура AggregateFromMeetings.** → Митигация: переносим папку целиком, внутреннюю структуру не ломаем.
6. **Противоречие «версия в имени» у эталона MoveFromFF_TZ_v2.1.md.** → Митигация: явное решение по §14 п.1 до старта миграции.

**Порядок действий (агрегировано):**
1. Согласовать это ТЗ с Сашей, получить решения по §14.
2. Фаза 0 — **обязательный полный бэкап** + создание пустой структуры + рулбук + переименование инвентаря.
3. Фаза 1 (копирование активных ТЗ в новое место, оригиналы пока не трогаем).
4. Ручная проверка PM: всё ли на месте, всё ли читается.
5. Фаза 2 (перенос устаревших и завершённых в backup).
6. Фаза 2A (проверка/обновление ссылок на старые пути в Hermes и реестрах).
7. Фаза 3 (очистка исходников после проверки, апдейт индексов).
8. Фаза 4 (скилл + smoke-тест).
9. Финальный отчёт в чат.

---

## 14. Открытые вопросы Саше

Ниже — места, где я как автор ТЗ приняла решение сама или где решение действительно требует твоего слова. Мои рекомендации даю честно, но окончательное решение — за тобой.

1. **Версия в имени файла для эталона MoveFromFF_TZ_v2.1.md.**
   Правило §4 говорит «версия только во frontmatter, не в имени», но существующий эталонный файл `USERTOOLS/MoveFromFF/MoveFromFF_TZ_v2.1.md` этот принцип нарушает.
   **Моя рекомендация:** при переносе в `TZ/MoveFromFF/` переименовать в `MoveFromFF_TZ.md`, версию 2.1 положить во frontmatter — единое правило для всех активных файлов, чище индексация.
   **Альтернатива:** оставить `MoveFromFF_TZ_v2.1.md` как исключение (не ломать устоявшийся паттерн). Но тогда правило §4 придётся смягчить формулировкой «для новых ТЗ».

2. **Кириллические имена архивных `ТЗ-MoveFromFF-*.md` в `_Done/`.**
   4 файла уже существуют с русскими именами.
   **Моя рекомендация:** оставить как есть при переносе в `~/WorkVault_backup/Hermes-Backlog/_Done/` — это архив, вне навигации Obsidian, переименование добавляет операций и разрывает историю. Правило «только латиница» применяем только для новых файлов.
   **Альтернатива:** переименовать при переносе в `TZ-MoveFromFF-*-20260527.md` для консистентности.

3. **Судьба папки `USERTOOLS/<tool>/` после переноса master-ТЗ в WorkVault.**
   Сейчас master живёт рядом с кодом инструмента. После переноса в vault — что оставить в USERTOOLS?
   **Моя рекомендация:** оставить короткий `README.md` в `USERTOOLS/<tool>/` со ссылкой на новый путь ТЗ (`See WorkVault/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ.md`). Симлинк — хуже (ломается при отсутствии vault, например если Opus работает на другом хосте).
   **Альтернатива:** ничего не оставлять — единая точка правды, разработчику достаточно `MAIN_TZ_INVENTORY.md`. Минус: Opus, работающий над кодом инструмента, не увидит подсказки где ТЗ.

4. **Когда архивировать ТЗ инструмента.**
   В прошлой версии я писала «через месяц после completed» — путала завершение доработки с выводом инструмента из эксплуатации.
   **Уточнённая рекомендация:** пока инструмент используется — его master-ТЗ всегда остаётся в `WorkVault`, независимо от того, сколько доработок реализовано. В `WorkVault_backup` ТЗ переезжает только когда сам инструмент удалён/выведен из эксплуатации, и только по твоему явному решению («этот инструмент больше не используем, убираем ТЗ в архив»). Никакого автотаймера.

5. **Реализация архивации: bash-скрипт vs текстовые инструкции.**
   Я предложила `scripts/archive-tz.sh` внутри скилла.
   **Моя рекомендация:** без скрипта. Агент и так умеет `tar czf … && echo … >> _moved-*.log` через terminal-тул, а bash-скрипт добавляет поверхность отказа (пути, permissions, дистрибутивные различия). Оставить в `references/archiving.md` эталонные команды текстом.
   **Альтернатива:** тонкий скрипт-обёртка (10 строк) — плюс: единообразное имя `.tgz` и запись в лог одним вызовом. Минус: ещё один исполняемый файл.

6. **Имя самого файла этого ТЗ.**
   Файл лежит как `ТЗ-система-хранения-ТЗ.md` — кириллица.
   **Моя рекомендация:** после согласования переименовать в `TZ-storage-system.md` (или `TZ-tz-storage.md`) и положить в `TZ/_misc/`. Сама по себе миграция должна следовать правилам, которые вводит.
   **Альтернатива:** оставить кириллицу до финализации, переименовать вместе со всеми остальными на Фазе 1.

7. **Куда девать активный `ТЗ-MoveFromFF-apps-preview-summary.md` в корне Hermes-Backlog?**
   Это точечное ТЗ по MoveFromFF, статус неясен.
   **Моя рекомендация:** проверить, дореализовано ли — если да, влить как секцию в master `MoveFromFF_TZ.md` и оригинал в `_Done/`; если нет — перенести в `TZ/_misc/TZ-MoveFromFF-apps-preview-summary-20260703.md` (латиница) как активное точечное.
   **Альтернатива:** оставить в корне до отдельного решения.

8. **Обновление скилла `hermes-feature` в рамках этой миграции.**
   Скилл содержит явные строки со старыми путями (Блок 0: `WorkVault/Hermes-Backlog/ТЗ-[название].md`; Блок 4: `_Done/ТЗ-[название]-YYYYMMDD.md`; питфолл про master в USERTOOLS).
   **Моя рекомендация:** обновлять в той же миграции (Фаза 2A) — иначе агент будет продолжать создавать ТЗ по старым правилам, ломая только что введённую схему.
   **Альтернатива:** сначала завершить миграцию, скилл обновить отдельной задачей (риск: агент успеет создать файл по старому пути).

---

**Итого:** после реализации у нас один и только один путь до любого активного ТЗ (`WorkVault/Hermes-Backlog/TZ/<Tool>/`), один инвентарь ТЗ, один инвентарь vault, один рулбук в самом vault (виден Cursor), одна папка backup с зеркальной структурой и один скилл, который следит, чтобы правила не разъезжались. Ждём твоих решений по §14 — без них миграцию не запускаем.
