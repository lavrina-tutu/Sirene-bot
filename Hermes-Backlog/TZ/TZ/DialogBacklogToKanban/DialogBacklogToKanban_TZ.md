---
tool: DialogBacklogToKanban
type: infra_plan
title: "Перенос открытых пунктов DialogBacklog в канбан-карточки IDEA/* (triage)"
version: 0.2.0
date: 2026-09-23
status: draft
author: архитектор (cursor-grok-4.6-high, Cursor)
last-section-added: 2026-09-23 — v0.2.0 репоинт бэклог-скиллов на triage + полный DECOMM DialogBacklog
depends_on:
  - TZ/DialogBacklog/DialogBacklog_TZ.md >= 1.5
  - TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md >= 0.2.0
  - skill:tz-workflow >= 2.1.0
  - skill:backlog-collector >= 1.5.0
  - USERTOOLS/DialogBacklog/backlog_fetch.py
  - USERTOOLS/DialogBacklog/backlog_analyst.py (parse_backlog — только как образец парсера)
consumers:
  - skill:tz-workflow (различение passive-triage vs IDEA:analyze)
  - skill:backlog-collector (переписывается на фид IDEA/*, не md)
  - profile:default (Сирень)
  - ~/.hermes/kanban.db
reuse_first: "не новый USERTOOL и не новый скилл; одноразовый скрипт миграции + перепись backlog-collector; канбан уже внедрён"
---

# DialogBacklogToKanban — перенос бэклога идей на карточки `triage`

## Цель

Перенести **только открытые** пункты `[ ]` из `dialog-backlog.md` в карточки канбана `IDEA/<slug>` со статусом `triage`, так чтобы они лежали пассивно (воркер не трогает, в `ready` сами не уходят), и после успешного переноса убрать markdown-хранилище и лишние инструменты DialogBacklog. Автокрон сбора не ставится.

## Форма ТЗ (почему отдельный файл)

Это **инфраструктурный план миграции/декомиссии**, не USERTOOL и не секция внутри существующих master-файлов.

| Альтернатива | Почему не выбрана |
|---|---|
| Секция в `DialogBacklog_TZ.md` | Тот файл — спецификация markdown-пайплайна (fetch → plan.json → merge → `dialog-backlog.md`). Миграция его **заменяет**, а не дорабатывает. Канон «один файл на инструмент» сохраняется: DialogBacklog остаётся, пока жив markdown; это ТЗ — отдельный план вывода. Прецедент: `TzDevDecommission`. |
| Секция в `DevKanbanPipeline_TZ.md` | Цикл `DEV/<slug>` и гейты **не меняем** (non-goal этого брифа). DevKanbanPipeline явно отложил автосбор DialogBacklog «после». Смешивать одноразовую миграцию 9 карточек с утверждённым пайплайном разработки — шум. На реализации — короткая отсылка в «Связи» DevKanbanPipeline, без переписывания графа. |

Проверено 2026-09-05 по `MAIN_TZ_INVENTORY.md` и `EcosystemManifest.json`: отдельного плана «бэклог → triage» нет. Канбан-механизм `IDEA:*` уже описан и внедрён (`auto_decompose: false`, `dispatch_in_gateway: true`).

---

## Инвентарь текущего состояния (срез 2026-09-05)

### Источник данных

| Артефакт | Путь | Состояние |
|---|---|---|
| Живой бэклог | `~/WorkVault/Hermes-Backlog/dialog-backlog.md` | ~863 строки, ~101 КБ; frontmatter `last_scan_at: 2026-09-02T09:00:00+03:00`, `next_id: 178` |
| Сводка в файле | «Открыто задач: **8**» | **устарела**: фактически **9** открытых `- [ ]` |
| Закрытые `[x]` | тот же файл, секция `## ✅ Закрытые (архив)` + хвосты по темам | **156** строк `- [x]` |
| Локальные копии рядом | `dialog-backlog.md.bak`, `.pre-fin2-20260902`, `.pre-final-20260902`, `.pre-close-20260902`, `.pre-merge-20260902`, `.pre-canon-20260831` | рабочие снимки консолидации; в live-источник не входят |
| Git-копии (вне scope правок) | `~/hermes-config-repo/Hermes-Backlog/dialog-backlog.md`, `~/hermes-config/Hermes-Backlog/dialog-backlog.md` | зеркала репозиториев конфига; **не трогать** (`_TZ-WORKFLOW-RULES.md`) |

### Открытые `[ ]` — полезная нагрузка миграции (9)

| Якорь | Секция | `idea_summary` | `created` / `updated` | 💬 |
|---|---|---|---|---|
| `bk-154` | 📌 Сводка (сирота над EPIC) | нет | 2026-07-28 / 2026-07-28 | да |
| `bk-049` | 🏗️ EPIC: AggregateFromMeetings | нет | нет | нет |
| `bk-050` | то же | нет | нет | нет |
| `bk-087` | то же | нет | нет | нет |
| `bk-089` | то же | нет | 2026-06-16 / 2026-06-24 | да |
| `bk-155` | то же (опросы АИД — тематически не EPIC) | нет | 2026-07-28 / 2026-07-28 | да |
| `bk-174` | 🔧 Hermes / Сирень | да (SQL вместо md) | 2026-08-31 / 2026-08-31 | да |
| `bk-177` | то же | да (промпты транскриптов) | 2026-09-03 / 2026-09-03 | да |
| `bk-176` | 🔐 Confluence — доступ к протоколам | да | 2026-09-02 / 2026-09-02 | да |

Не карточки (в файл есть, в канбан **не** переносить):

- секция `🔎 Cursor CLI — разбор работ за 29.08` — цитата без `[ ]`;
- блок `📄 Постановки и архитектурные решения` — ссылки в `research/`, не задачи;
- все `- [x]` и архив;
- заметки без якоря `^bk-NNN`.

`bk-174` («хранить DialogBacklog на SQL») **переносится как обычная IDEA-карточка**, не авто-закрывается. Канбан (`kanban.db`) закрывает «уйти с markdown», но не дословно статусы `recorded/выполнено/отменено` из формулировки. Решение по закрытию — за Сашей после миграции.

### USERTOOLS `~/USERTOOLS/DialogBacklog/`

| Файл | Роль | После миграции |
|---|---|---|
| `backlog_fetch.py` | Читает `state.db` (`sessions.source='telegram'`) → JSON сообщений с `--since` | **Оставить.** Источник ручного фида |
| `backlog_merge.py` | Детерминированно пишет `dialog-backlog.md` из `plan.json`; `.bak`; зовёт `trigger_sync.sh dialogbacklog` | **Удалить** после успешного переноса (потребитель — только md) |
| `backlog_analyst.py` | Парсер открытых + сверка со скиллами/`MAIN_TZ_INVENTORY` → `suggest_close` | **Не удалять в фазе 1.** Парсер — образец для миграции. Логика сверки — Phase 2 (вне обязательного scope) |
| `backlog_stamp_dates.py` | Разовая ретро-датировка md | **Удалить** (md-only, уже отработал) |
| `test_backlog_v15.py` | Тесты merge + analyst | **Удалить** вместе с merge; при Phase 2 analyst — новые тесты на канбан |
| `requirements.txt` | Пометка «только stdlib» | **Оставить**, пока жив `backlog_fetch.py` |
| `README.md` | Документация md-пайплайна | **Переписать** под фид в triage |
| `.pytest_cache/` | кэш | **Удалить** |
| `scripts/dedup_anchors.py` | в этом каталоге **нет** | лежит в мёртвом скилле `productivity/dialog-backlog` |

CLI `backlog_fetch.py`: `--since` обязателен, `--db` default `~/.hermes/state.db`, `--limit` 1000, `--topics` stub (warning). Фильтра топиков в SQL нет — делает LLM.

`parse_backlog()` в analyst **не** читает `📅 created/updated` и заголовок секции — миграционный парсер должен собрать их сам (расширение, не вызов as-is).

### Скиллы

| Скилл | Путь | Триггеры | Судьба |
|---|---|---|---|
| `backlog-collector` v1.5.0 | `~/.hermes/skills/devops/backlog-collector/SKILL.md` | «собери бэклог», «прогнать сборщик бэклога» | **Переписать**: выход = `IDEA/*` в `triage`, не md. Крон **не** ставить |
| `backlog-analyst` v1.5.0 | `~/.hermes/skills/devops/backlog-analyst/SKILL.md` | «что в бэклоге», «проверь бэклог», «прогнать аналитик бэклога» | **Phase 2 / вне scope.** После удаления md скилл без входа — не вызывать. Удаление скилла — после решения по Phase 2 |
| `backlog-consolidation` v1.0.0 | `~/.hermes/skills/devops/backlog-consolidation/SKILL.md` | «сведи бэклог», «почини бэклог», … | **Удалить** (md-only: якоря, архивная секция, преамбула) |
| `dialog-backlog` v1.0.0 (легаси) | `~/.hermes/profiles/default/skills/productivity/dialog-backlog/` и `~/hermes-workspace/skills/productivity/dialog-backlog/` | «проверь бэклог», «что в бэклоге» | **Мёртвый дубль.** В каноне `~/.hermes/skills/productivity/` **нет**. Удалить копии в workspace/profile (канон skills — через `restore-all-skills.sh`, git-репо `hermes-workspace` править только если Саша явно скажет про git) |
| `sirene-chat-friends` reference | `~/.hermes/skills/persona/sirene-chat-friends/references/dialog-backlog.md` | — | **Заменить** короткой отсылкой на канбан triage |
| `check-cron-results` reference | `~/.hermes/skills/devops/check-cron-results/references/dialogbacklog-report-format.md` | формат `vm_dialogbacklog` | **Удалить** (крон мёртв) |
| `tz-workflow` | раздел «Ручной feed идеи» | «положить в бэклог / triage / **разбери идею**» сейчас = create + сразу `specify` → `ready` | **Дополнить** (не ломая DEV-граф): развести passive vs analyze |

### Кроны

В актуальном `~/.hermes/cron/jobs.json` (срез 2026-09-05) **нет** `backlog-collector`, `backlog-analyst`, `vm_dialogbacklog`. Исторически были `6af39b43255d` / `b6806ebec6e6` (пн–пт 08:00/08:05) — следы в `cron-journal.md`, curator backups, `about_usr_skills/references/tools-status.md`. **Новые кроны не ставить.**

### Канбан (уже внедрён, не переписывать ядро)

- БД: `~/.hermes/kanban.db`
- Конфиг `~/.hermes/config.yaml` → `kanban:`: `dispatch_in_gateway: true`, интервал 60 с, `auto_decompose: false`, `orchestrator_profile: default`, `default_assignee: default`, `max_in_progress_per_profile: 1`
- Статусы движка: `triage | todo | ready | running | blocked | done | archived`
- Dispatcher поднимает только `ready`. Карточка, оставленная в `triage` без `hermes kanban specify`, **воркером не берётся**. Это и есть пассивный inbox.
- Переход triage → ready: **`hermes kanban specify`**, не `promote`.
- Текущий IDEA-поток в `tz-workflow`: `kanban_create` корня + child `IDEA:analyze` с `--triage`, затем **сразу** specify в `ready`. Для **миграции и команды «собери идеи» этот авто-specify запрещён.**

### Прочие упоминания (чистить на шаге docs, не в миграции карточек)

| Где | Что |
|---|---|
| `TZ/DialogBacklog/DialogBacklog_TZ.md` | master markdown-инструмента; после приёмки → `status: archived` + строка в инвентаре |
| `TZ/DevKanbanPipeline` | «автосбор DialogBacklog не в этом ТЗ» — на impl добавить ссылку на это ТЗ |
| `TZ/MofsIndex` | контракт: `backlog_analyst.py` потребитель `search_docs()` |
| `MAIN_TZ_INVENTORY.md` | строка DialogBacklog `active` |
| `EcosystemManifest.json` → `tools.dialog_backlog`, `skills.backlog_collector` | обновить purpose/called_by после переписи скилла |
| `WorkVault/Home.md` | Dataview `TASK FROM "Hermes-Backlog/dialog-backlog"` |
| `WorkVault/AGENTS.md`, `TZ/AGENTS.md` | имя в списке активных инструментов |
| `skills-registry.md` | `dialog-backlog`, `vm_dialogbacklog` |
| `productivity/about_usr_skills/references/tools-status.md` | «v1.5 в проде», job_id кронов |
| `UserManuals/hermes-models-and-providers.md` | таблица моделей кронов collector/analyst |
| `PIIScan` baseline | путь `dialog-backlog.md` как источник находок (файл с ПДн в контексте задач) |
| `~/WorkVault/Tools/DialogBacklog/README.md` | указатель на ТЗ |
| `trigger_sync.sh` | вызывается из merge как `dialogbacklog` — после удаления merge вызов исчезнет сам |

Git-репозитории `~/hermes-config`, `~/hermes-config-repo`, `~/hermes-workspace` — **не трогать** этим ТЗ, кроме явно согласованного удаления скилла в workspace при `restore-all-skills.sh`.

---

## Решения брифа (зафиксированы архитектором 2026-09-05)

1. **Механика переноса.** Одноразовый Python-скрипт (`~/USERTOOLS/DialogBacklog/migrate_to_kanban.py`) с `--dry-run` (обязательный первый прогон) и явным `--apply` (без `--apply` диск и `kanban.db` не меняются). Не вручную через скилл: 9 карточек, идемпотентность, сверка якорей — работа скрипта.
2. **`backlog_fetch.py`.** Сохранить. Переиспользовать как источник ручного фида: команда Саши «собери идеи в бэклог» / «собери бэклог» → fetch с watermark → LLM отбирает идеи → `kanban_create` `IDEA/*` в **`triage` без specify**. Автокрон не ставить.
3. **`backlog_analyst.py`.** Обязательный scope этой миграции — **нет**. Phase 2 (отложено): сверка IDEA-карточки с реализацией при «берём в работу» / «разбери идею». Промпты A/B/C и `parse_backlog` не выкидывать с диска, пока Phase 2 не решён.
4. **Закрытые `[x]` и архив.** В карточки не переносить. Файл `dialog-backlog.md` после verify: полный снимок в бэкап, live-файл → **заглушка** (куда перенесено), затем удаление заглушки на последнем шаге чистки — только по явной фразе Саши («удаляй файл бэклога» / часть «удали лишнее» после сверки).
5. **Бэкап.** Обязателен **дважды**: (а) перед первым `--apply` миграции; (б) перед любым удалением инструментов/скиллов/live-md. Каталог: `~/.hermes/_Archives/dialogbacklog-YYYYMMDD-HHMMSS/` (не смешивать с полным `hermes-backup-*`, чтобы можно было откатиться точечно).

---

## Два режима IDEA (дополнение к DevKanbanPipeline, цикл DEV не трогать)

| Режим | Триггер | Что создаётся | Статус после create | Воркер |
|---|---|---|---|---|
| **passive-inbox** | миграция; «собери идеи в бэклог»; «положи в бэклог» / «в triage» **без** «разбери» | только корень `IDEA/<slug>` | остаётся `triage` | не берёт |
| **analyze** | «разбери идею» / «разбери bk-NNN» / «разбери <slug>» | если корня нет — создать; child `IDEA:analyze`; `hermes kanban specify` на analyze | analyze → `ready` | silent `default` → архитектор → comment → `blocked` |

Сейчас `tz-workflow` склеивает «положить в бэклог» и «разбери идею» в один путь со specify. Это **ломает** требование «перенесённые карточки не обрабатывать без явного запуска». На реализации: развести фразы в разделе «Ручной feed идеи». Граф `DEV/<slug>`, гейты, one-pass, `auto_decompose: false` — без изменений.

Из `triage` в работу по-прежнему только `specify`, не `promote`.

---

## Контракт карточки после миграции

Каждый открытый пункт → **ровно одна** карточка.

- **title:** `IDEA/bk-NNN: <текст пункта>` (текст без якоря и без `<!-- AI: suggest close -->`). Если длиннее лимита CLI — обрезать title, полный текст в body.
- **slug / идемпотентность:** NNN нормализуется до 3+ цифр (`bk-49` → `bk-049`). Ключ: `dialogbacklog-migrate:bk-049`.
- **assignee:** `default`
- **create:** `hermes kanban create ... --triage --assignee default --idempotency-key <ключ>`
- **не создавать** child `IDEA:analyze`
- **не вызывать** `specify` / `promote`

**body** (обязательные блоки, дословно из md, ничего не выдумывать):

```
source: dialog-backlog.md
bk_anchor: bk-NNN
section: <заголовок ## на момент пункта>
created: YYYY-MM-DD | unknown
updated: YYYY-MM-DD | unknown
idea_summary: <как в файле> | (нет)
waits_sasha: true | false   # префикс 🙋 в тексте

Текст:
<полный текст пункта>

Контекст:
<строка 💬 или (нет)>

migrate:passive
```

`idea_summary` для пунктов без 💡 — поле `(нет)`, **не** генерировать LLM на миграции.

Трассируемость: `bk-NNN` в title, в `--idempotency-key`, в body `bk_anchor`.

### Идемпотентность

Повторный `--apply` **не дублирует** карточки:

1. Перед create — `hermes kanban list` (или SQL read-only к `kanban.db`): есть задача с `idempotency_key` или title-префиксом `IDEA/bk-NNN:` → skip, в отчёт `already_exists`.
2. `--idempotency-key` на create — второй предохранитель движка.
3. Скрипт не archive/delete существующих карточек.
4. `--dry-run` печатает план: `create | skip | error` по каждому якорю, без записи.

Критерий: два `--apply` подряд → вторая сводка `create=0`, `skip=9` (или `skip=N` открытых на момент прогона).

---

## Процедура реализации (атомарные шаги)

Реализация **не** стартует с этого ТЗ. Ждать «берём в работу». Кроны не ставить. Gateway не рестартовать.

### Фаза 0 — бэкап (перед любым `--apply`)

Скопировать в `~/.hermes/_Archives/dialogbacklog-YYYYMMDD-HHMMSS/`:

- `~/USERTOOLS/DialogBacklog/` (целиком)
- `~/WorkVault/Hermes-Backlog/dialog-backlog.md` + все `dialog-backlog.md.*` рядом
- скиллы: `backlog-collector`, `backlog-analyst`, `backlog-consolidation`
- `~/WorkVault/Tools/DialogBacklog/README.md`
- манифест-фрагмент не обязателен (файл маленький; достаточно git-less copy манифеста целиком — нет, слишком широко). Достаточно перечисленных путей.

Проверка: каталог не пустой, `dialog-backlog.md` в нём совпадает по `wc -c` с live.

### Фаза 1 — скрипт миграции

1. Написать `migrate_to_kanban.py` (stdlib + вызов `hermes kanban`).
2. Парсер: только строки, начинающиеся с `- [ ]` и содержащие `^bk-`; суб-буллеты до следующего пункта/`##`/`---`; секция = ближайший `##` выше; даты из `📅`; 💡 / 💬 как есть.
3. `--dry-run` → таблица 9 строк. Сверить с инвентарём этого ТЗ (якоря). Расхождение → стоп, не `--apply`.
4. Показ Саше dry-run (в чате). `--apply` — только после его «гоняй apply» / «делай перенос» (отдельный императив, не это ТЗ).
5. `--apply`: create 9 карточек в `triage`. Отчёт: `task_id` по якорю.
6. Verify:
   - `hermes kanban list` — 9 (или N) карточек `IDEA/bk-*` в `triage`;
   - ни одна не `ready`/`running`;
   - нет child `IDEA:analyze` у них;
   - `[x]` карточек нет;
   - повторный `--apply` → 0 create.
7. 60–120 с подождать dispatcher tick: карточки **остались** `triage`. Если какая-то ушла в `ready` — стоп, `kanban` reclaim/архив ошибочных, чинить specify-баг скилла, не продолжать удаление md.

### Фаза 2 — ручной фид (перепись `backlog-collector`)

1. Watermark: больше не frontmatter md. Файл `~/USERTOOLS/DialogBacklog/state.json`: `{ "last_scan_at": "<ISO+03:00>", "schema_version": "1.0" }`. Стартовое значение — текущий `last_scan_at` из md (`2026-09-02T09:00:00+03:00`), чтобы не пересканировать всю историю.
2. Алгоритм скилла: прочитать watermark → `backlog_fetch.py --since` → LLM по правилам наполнения из `DialogBacklog_TZ.md` v1.3 (что заносить / не заносить) → для каждой новой идеи `kanban_create --triage` без specify, ключ `dialogbacklog-feed:<iso-timestamp>:<short-hash>` (не bk-NNN: новые идеи якоря md не получают).
3. `suggest_close` / запись в md / `backlog_merge.py` — не вызывать.
4. Отчёт — в чат, откуда пришла команда. Топик Telegram Backlog (`:6`) **не обязателен**.
5. Расписание крона в SKILL.md удалить. Триггеры оставить/добавить: «собери бэклог», «собери идеи в бэклог».
6. После правок скилла — `restore-all-skills.sh` (когда Саша подтвердит синк профилей; не автоматически в этом ТЗ как отдельный побочный крон).

### Фаза 3 — чистка после успешного переноса

Порядок: бэкап (второй) → заглушка md → правки ссылок → удаление кода → архивация ТЗ DialogBacklog.

**Сразу можно удалять (md-only, после verify фазы 1):**

- `backlog_merge.py`
- `backlog_stamp_dates.py`
- `test_backlog_v15.py` (если analyst ещё на диске — вынести/оставить только тесты analyst; проще удалить v15 целиком и не тестировать мёртвый merge)
- `.pytest_cache/`
- скилл `backlog-consolidation`
- reference `dialogbacklog-report-format.md`
- локальные `dialog-backlog.md.bak` и `.pre-*` (они уже в архиве фазы 0)

**Переписать, не удалять:**

- `backlog-collector/SKILL.md`
- `USERTOOLS/DialogBacklog/README.md`
- `sirene-chat-friends/references/dialog-backlog.md` → «открытые идеи: канбан `IDEA/*` status=triage»
- `Home.md` — убрать Dataview TASK по `dialog-backlog`; одна строка: бэклог идей на доске канбана (`hermes kanban list` / дашборд), статус `triage`
- `EcosystemManifest.json` — `dialog_backlog.purpose` / `called_by` (через ORCH:shared-state по hermes-feature, не руками исполнителя в обход Блока 4 — если чистка идёт как HF)
- `about_usr_skills/references/tools-status.md` — кроны остановлены, фид ручной
- `MAIN_TZ_INVENTORY.md` — DialogBacklog → `archived` **только когда** Саша принял перенос; это ТЗ → `approved`/`completed` по факту

**Не удалять в этом ТЗ:**

- `backlog_fetch.py`, `state.json`, каталог `USERTOOLS/DialogBacklog/`
- `backlog_analyst.py` + скилл `backlog-analyst` (Phase 2)
- `kanban.db`, ядро канбана, скиллы `kanban-worker` / `kanban-orchestrator`
- `DialogBacklog_TZ.md` до явной архивации (сначала `status: archived` в frontmatter + инвентарь, файл не сносить)
- git-репо конфигов

**Live `dialog-backlog.md`:** заменить заглушкой (~15 строк: дата переноса, путь архива, «не писать», как смотреть triage). Физическое удаление заглушки — отдельная фраза Саши после того, как Home.md и скиллы больше на файл не ссылаются.

### Фаза 4 — docs/инвентарь экосистемы

- DialogBacklog в инвентаре: `archived`, «куда переехало: канбан IDEA/triage + DialogBacklogToKanban».
- Это ТЗ: `completed` после чистки.
- MofsIndex: `mofs index docs` по новым/изменённым ТЗ (инкремент).
- Упоминания в `skills-registry.md`, `UserManuals/hermes-models-and-providers.md` — по факту или пометкой устарело.

---

## Что переиспользуем / что нет

| Существующее | Решение |
|---|---|
| `hermes kanban create --triage` + `--idempotency-key` | да, единственная запись в доску |
| `hermes kanban specify` | да, **только** в режиме analyze по команде Саши |
| `backlog_fetch.py` | да |
| Правила наполнения DialogBacklog v1.3 | да, для ручного фида |
| `parse_backlog()` | образец; для миграции расширить (секция + даты) |
| `backlog_merge.py` / md как SoT | нет, выводится |
| Новый скилл с новым именем | **нет** (reuse-first). Переписываем `backlog-collector` |
| Новая сущность EcosystemManifest | нет; тот же `dialog_backlog`, смена purpose |
| Автокрон | нет |
| Кастомная SQL-таблица «как bk-174» | нет в этом ТЗ; SoT = `kanban.db` |

---

## Критерии успеха

- Dry-run показывает ровно открытые якоря из живого файла (на срезе ТЗ — 9: 154, 049, 050, 087, 089, 155, 174, 177, 176).
- После `--apply`: столько же карточек `IDEA/bk-*` в `triage`; 0 в `ready`/`running` из этой пачки; 0 карточек из `[x]`.
- Повторный `--apply` не создаёт дублей.
- Через ≥1 tick dispatcher карточки миграции всё ещё `triage`.
- Команда «собери бэклог» не пишет в `dialog-backlog.md` (после фазы 2).
- Команда «разбери идею bk-NNN» — единственный путь, который делает specify / IDEA:analyze.
- После фазы 3: `backlog_merge.py` нет на диске; live md либо заглушка, либо удалён по фразе Саши; бэкап лежит в `_Archives/dialogbacklog-*`.
- DEV-граф, `auto_decompose: false`, HITL-гейты, one-pass — без регрессии (smoke существующего DevKanbanPipeline не ломаем; новый полный smoke DEV не обязателен, достаточно не вызывать specify на пачке миграции).

---

## Что НЕ трогать

- Основной цикл `DEV/<slug>` и гейты DevKanbanPipeline.
- `hermes_cli/kanban_db.py`, статусы движка, `auto_decompose`.
- Закрытые `[x]` — не создавать карточки, не переписывать архив до копирования в бэкап.
- Автокрон сбора идей.
- Gateway — не рестартовать.
- Профили кроме `default`; не создавать dev-профили.
- `~/hermes-config`, `~/hermes-config-repo` (git).
- USERTOOLS других инструментов; `entities.json`; контакты.
- Реализация кода в сессии написания этого ТЗ.

---

## Связи с экосистемой

- `DialogBacklog` — исходный инструмент; после приёмки архивируется, fetch остаётся как фид.
- `DevKanbanPipeline` — приёмник карточек; это ТЗ дополняет IDEA-inbox режимом passive, не меняя DEV.
- `tz-workflow` — правки только в «Ручной feed идеи» (разведение фраз).
- `EcosystemIntegration` — обновление `tools.dialog_backlog` / скилла collector на шаге docs.
- `MofsIndex` — потребитель analyst через `search_docs`; пока analyst жив, контракт MofsIndex не ломать. После удаления analyst — правка контракта MofsIndex отдельной доработкой (не обязательный шаг этой миграции).
- `PIIScan` — `dialog-backlog.md` в baseline; после удаления/заглушки исчезновение находок резолвится штатно (не руками чистить baseline в этом ТЗ).
- `ErrorBus` — новые job_id не нужны (крона нет).
- `HonchoIntegration` — «потенциальная синергия» в том ТЗ; не реализуется здесь.

---

## Контракты экосистемы

### Источник истины

- До `--apply`: владелец открытых идей — `dialog-backlog.md` (пункты `[ ]`).
- После `--apply`: владелец открытых идей — канбан Hermes (`~/.hermes/kanban.db`), карточки `IDEA/bk-NNN:*` в `triage` (и последующие статусы по DevKanbanPipeline).
- Watermark скана диалогов: `~/USERTOOLS/DialogBacklog/state.json` (`last_scan_at`), владелец — переписанный `backlog-collector`.
- Архив закрытых `[x]`: снимок md в `~/.hermes/_Archives/dialogbacklog-YYYYMMDD-HHMMSS/`. Канбан их не хранит.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| bk_anchor | str | required | dialog-backlog.md (`^bk-NNN`) | `bk-` + цифры, нормализация ≥3 |
| item_text | str | required | строка `- [ ]` | без якоря и HTML-комментария suggest close |
| section | str | optional | ближайший `##` | заголовок как в md |
| idea_summary | str | optional | строка 💡 | дословно; пусто = "(нет)" |
| context | str | optional | строка 💬 | дословно |
| created | str | optional | строка 📅 `created::` | YYYY-MM-DD или unknown |
| updated | str | optional | строка 📅 `updated::` | YYYY-MM-DD или unknown |
| last_scan_at | datetime(iso8601) | required | frontmatter md, затем state.json | ISO с offset |
| trigger | enum[migrate, manual_feed, analyze] | required | Саша / скрипт | migrate=скрипт; manual_feed=собери идеи; analyze=разбери идею |
| assignee | str | required | этот план | всегда "default" |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| task_id | str | отчёт миграции, Саша (доска) | id kanban_create |
| status | enum[triage, todo, ready, running, blocked, done, archived] | dispatcher, доска | после migrate/manual_feed = triage; analyze после specify = ready |
| idempotency_key | str | повторный migrate / feed | migrate: `dialogbacklog-migrate:bk-NNN`; feed: `dialogbacklog-feed:<iso>:<hash>` |
| body.bk_anchor | str | трассировка, analyze, Phase 2 | `bk-NNN` |
| body.migrate_marker | str | tz-workflow (не specify пачкой) | литерал `migrate:passive` у passive-inbox |
| last_scan_at | datetime(iso8601) | следующий manual_feed | запись в state.json |

### Зависимости

- Получает от: [DialogBacklog (md + fetch), DevKanbanPipeline (карточки/статусы), tz-workflow (фразы IDEA)]
- Отдаёт: [kanban.db / доска Саши, backlog-collector (фид), tz-workflow (разведение фраз)]

### Breaking changes policy

- Версионирование: `schema_version` в `state.json` (старт `"1.0"`).
- Схему SQLite канбана не мигрировать.
- Смена формата body/якоря: бамп `schema_version`, описать в новой секции этого ТЗ; старые карточки не переписывать скриптом без `--rewrite` (такого флага в v0.1.0 нет).

### Границы («что НЕ трогать»)

- Не вызывать `specify` на карточках миграции и ручного фида.
- Не создавать `IDEA:analyze` в тех же операциях.
- Не ставить `[x]` и не писать `plan.json` в md после фазы 2.
- Не включать `auto_decompose`.
- Не переносить `[x]`.

---

## Риски

| Риск | Митигация |
|---|---|
| `tz-workflow` сразу specify'ит IDEA (как сейчас) | сначала правка скилла **или** миграция без фразы «разбери»; verify tick'ом dispatcher; маркер `migrate:passive` в body |
| Дубли карточек при втором прогоне | idempotency-key + предпроверка list; `--apply` без ключа — запрещён |
| Парсер пропустит пункт без дат / без 💡 | это норма; 6 из 9 без summary; не генерировать |
| Сводка «8 открытых» vs 9 `[ ]` | источник истины — grep `- [ ]`, не цифра в сводке |
| `bk-174` путают с «миграция уже сделала SQL» | карточка переносится; закрытие только Саша |
| Analyst/collector крон «воскреснет» из старого промпта | в jobs.json их нет; не создавать; из SKILL убрать расписание |
| ПДн из md попадут в body карточки | как в исходном файле; канбан на той же ВМ; не расширять рассылку в Telegram topic 6 |
| Удаление md до правки Home.md/скиллов | сначала заглушка; delete — отдельная фраза |
| `parse_backlog` без секции/дат | свой парсер в migrate-скрипте |
| Легаси `productivity/dialog-backlog` перехватит «проверь бэклог» | удалить/не восстанавливать в канон skills |
| Исполнитель полезет в git hermes-workspace | запрет в «Что НЕ трогать»; restore-all-skills — только по команде |

---

## Критерии готовности ТЗ (шаг 4 tz-workflow)

- [x] Цель одним предложением
- [x] Входы/выходы явны
- [x] Шаги атомарны
- [x] Успех проверяем
- [x] «Что НЕ трогать» заполнен
- [x] Связи с экосистемой заполнены
- [x] Контракты по стандарту
- [x] Открытые вопросы — только то, что нельзя закрыть без Саши
- Финализация файла на диске ≠ «берём в работу»

---

## v0.1.0 → v0.2.0 — решение Саши 23.09.2026

Нормативные формулировки — в подразделах ниже. Где они расходятся с разделами v0.1.0 (фазы 1–4, «оставить fetch/analyst», «переписать README»), **канон после 23.09.2026 — эта секция.** Текст v0.1.0 остаётся историческим планом миграции 9 пунктов.

**Бриф-решение Саши 23.09.2026:** выпилить DialogBacklog **полностью** из экосистемы (подтверждение: «выпилить… я это подтверждаю точно»). Похоронить phased-миграцию «миграция → заглушка → частичная чистка с живым fetch/analyst». Перейти на два параллельных контура:

| Было (v0.1.0) | Стало (v0.2.0) |
|---|---|
| Перенос `[ ]` → IDEA/* triage, md → заглушка, fetch оставить как ручной фид | Миграция якорей уже сделана (09-06). SoT открытых идей — канбан `IDEA/*` `triage` |
| `backlog-collector` пишет IDEA/*; `backlog-analyst` — Phase 2 / вне scope | (А) **репоинт** бэклог-скиллов: фраза «бэклог» → read-запрос triage, не таблицы инструмента |
| Phase 3: удалить md-only код, **оставить** `backlog_fetch.py` / `backlog_analyst.py` / каталог USERTOOLS | (Б) **полный DECOMM** инструмента: скиллы, кроны, скрипты, таблицы/данные, реестры, GLOSSARY-упоминания |
| Открытый вопрос 1: заглушка vs удаление md (рекомендация — вечная заглушка) | Решение Саши: live → заглушка → **удаление** по явной фразе «удаляй файл бэклога» на последнем шаге чистки |
| Открытый вопрос 2: analyst на диске до брифа Phase 2 (рекомендация — оставить) | Решение Саши: **удаление при DECOMM**, промпты A/B/C только в архиве |

Канон сборки: кейс **SKILL-CHANGE** (репоинт скиллов) + кейс **DECOMM** по GLOSSARY §2 / §5.1. Это ТЗ фиксирует **намерение и контракт**. Физический вывод и правка скиллов — раздельные lane (см. «Разграничение»).

Что вошло в v0.2.0:

- Контракт фразы «бэклог» → `hermes kanban list --status triage` / `kanban_*`, не `dialog-backlog.md`.
- Судьбы канонных скиллов `backlog-collector` / `backlog-analyst` / `backlog-consolidation` и workspace-копий.
- Полная карта DECOMM по инвентарю `DEC:inventory` (`t_3f60b929`).
- Закрытие открытых вопросов 1–2 брифа v0.1.0.
- Границы: ядро канбана, IDEA/* triage, `state.db`, git-зеркала, Gateway, автокрон.

### Репоинт бэклог-скиллов (SKILL-CHANGE)

**Тактика.** При фразах «бэклог» / «что в бэклоге» / «проверь бэклог» / «покажи бэклог» показывать карточки `IDEA/*` со статусом `triage` (`hermes kanban list --status triage` / `kanban_*`), **а не** `dialog-backlog.md` и не таблицы инструмента DialogBacklog.

Канон скиллов — реальные каталоги `~/.hermes/skills/devops/` (**не** симлинки на workspace).

| Скилл | Путь / срез | Судьба |
|---|---|---|
| `backlog-collector` | `~/.hermes/skills/devops/backlog-collector/SKILL.md` (канон v2.0.0, 5108B, уже triage-фид) | **Переписать / заменить** на read-запрос triage (`kanban list --status triage`). Не писать md, не звать USERTOOLS DialogBacklog |
| `backlog-analyst` | `~/.hermes/skills/devops/backlog-analyst/SKILL.md` (канон v1.5.0, 6077B, ещё md) | **Переписать / заменить** на тот же read-запрос triage. Phase 2 «сверка с реализацией» **не делается** — скилл не остаётся md-аналитиком |
| `backlog-consolidation` | `~/.hermes/skills/devops/backlog-consolidation/SKILL.md` (v1.0.0, 5939B, md-only) | **УДАЛИТЬ.** В triage-модели места нет (якоря, архивная секция, преамбула md) |

**hermes-workspace-копии** (`~/hermes-workspace/skills/devops/backlog-*`) — синхронизировать с репоинтом / удалением (см. `DEC:inventory` §4b). Конкретный sync — в рамках `HF:impl` / `ORCH:shared-state`; здесь фиксируется намерение, не команда на git.

**Референс-файлы**

| Файл | Судьба |
|---|---|
| `persona/sirene-chat-friends/references/dialog-backlog.md` | **Заменить** короткой отсылкой на kanban triage |
| `devops/check-cron-results/references/dialogbacklog-report-format.md` | **Удалить** (крон мёртв) |

Зона исполнения репоинта — SKILL-CHANGE-lane этого борда (`HF:impl`), не `DEC:exec`.

**Реализовано 23.09.2026 (SKILL-CHANGE lane, канон → workspace идентичны):**

| Объект | Диск (канон `~/.hermes/skills/`) | Версия |
|---|---|---|
| `backlog-collector` | переписан на READ-запрос triage, не пишет md / не зовёт USERTOOLS DialogBacklog | **3.0.0** |
| `backlog-analyst` | переписан на тот же READ-контракт (исторический алиас), md-аналитик снят | **2.0.0** |
| `backlog-consolidation` | **удалён** (md-only, якоря/архив/преамбула) | — |
| `persona/sirene-chat-friends/references/dialog-backlog.md` | заменён коротким стабом-отсылкой на kanban triage | — |
| `devops/check-cron-results/references/dialogbacklog-report-format.md` | **удалён** (крон мёртв) | — |
| `productivity/dialog-backlog` (легаси-дубль) | **удалён** | — |
| `tz-workflow` §«Ручной feed идеи» | разведены passive-inbox (triage) vs analyze (`IDEA:analyze`) | — |

Вывод: фраза «бэклог» → `hermes kanban list --status triage` / `kanban_*` → карточки `IDEA/*` (title, status, body-превью). Манифест/digest/`restore-all-skills.sh`/git-коммит hermes-workspace — **ORCH:shared-state**, не эта фаза.

### Полный вывод инструмента DialogBacklog (DECOMM)

Полная инвентаризация: карточка `DEC:inventory` (`t_3f60b929`), приложение `DEC-inventory-dialogbacklog.md`. Ниже — что удаляется / оставляется, **дословно по категориям инвентаря**. Исполнение — DECOMM-lane, не эта правка ТЗ.

#### Скрипты `~/USERTOOLS/DialogBacklog/` — УДАЛИТЬ (инструмент выводится целиком)

| Файл | Размер / роль | Судьба |
|---|---|---|
| `backlog_analyst.py` | 29KB, парсер + сверка → `suggest_close` | **УДАЛИТЬ** |
| `backlog_fetch.py` | 3KB, читает `state.db` (`sessions.source='telegram'`) | **УДАЛИТЬ** |
| `backlog_merge.py` | 17KB, пишет `dialog-backlog.md` из `plan.json` | **УДАЛИТЬ** |
| `backlog_stamp_dates.py` | 7KB, разовая ретро-датировка md | **УДАЛИТЬ** |
| `migrate_to_kanban.py` | 8.7KB, одноразовая миграция `[ ]` → IDEA/* | **УДАЛИТЬ** (уже отработала 09-06) |
| `test_backlog_v15.py` | 12KB, тесты merge + analyst | **УДАЛИТЬ** |
| `requirements.txt` | «только stdlib» | **УДАЛИТЬ** |
| `README.md` | документация md-пайплайна | **УДАЛИТЬ** |
| `.pytest_cache/` | кэш | **УДАЛИТЬ** |
| `state.json` | watermark ручного фида | **УДАЛИТЬ** |

Каталог инструмента `~/USERTOOLS/DialogBacklog/` **удалить целиком.** Также `~/WorkVault/Tools/DialogBacklog/README.md` — УДАЛИТЬ (указатель на ТЗ).

#### Живой md и снапшоты

`~/WorkVault/Hermes-Backlog/dialog-backlog.md` (9 открытых `[ ]` + 156 закрытых `[x]`) + 6 снапшотов (`.bak` / `.pre-*`): полный снимок в бэкап; live → заглушка; **окончательное удаление — по явной фразе Саши «удаляй файл бэклога».**

| Файл | Судьба |
|---|---|
| `dialog-backlog.md` | снимок → `_Archives/dialogbacklog-*`; live → заглушка → удаление по фразе |
| `dialog-backlog.md.bak` | в бэкап |
| `dialog-backlog.md.pre-canon-20260831` | в бэкап |
| `dialog-backlog.md.pre-close-20260902` | в бэкап |
| `dialog-backlog.md.pre-fin2-20260902` | в бэкап |
| `dialog-backlog.md.pre-final-20260902` | в бэкап |
| `dialog-backlog.md.pre-merge-20260902` | в бэкап |

#### Kanban IDEA/* triage — ОСТАВИТЬ (преемник бэклога)

DECOMM их **не трогает:**

| Карточка | Примечание |
|---|---|
| `t_15b1bf50` | IDEA/* triage |
| `t_d2b5a44b` | IDEA/* triage |
| `t_b441ecac` | IDEA/* triage |
| `t_67d9beec` | IDEA/* triage |
| `t_d743ff5b` | IDEA/* triage |
| `t_37e3d752` | IDEA/* triage |

#### `state.db` — НЕ удалять

`~/.hermes/state.db` (2GB, `sessions.source=telegram`) — общий Hermes-стор. Удалить только скрипт-потребитель (`backlog_fetch.py`).

#### Кроны

Прямых DialogBacklog-кронов в live `~/.hermes/cron/jobs.json` **нет** (уже сняты). Новые кроны **не ставить.**

| Объект | Судьба |
|---|---|
| `05265ebdfaa4` Ecosystem drift-check | пишет в `dialog-backlog.md` → **перенаправить запись** (файл уходит) |
| `vm_selfcheck` | проверить отсутствие зависимости (прямой не найдено) |
| Исторические cron-id `6af39b43255d`, `b6806ebec6e6`, `vm_dialogbacklog`, `defc4425a957` | только следы в `tools-status.md` — убрать при чистке ссылок |

#### ТЗ-файлы

| Файл | Судьба |
|---|---|
| `TZ/DialogBacklog/DialogBacklog_TZ.md` (v1.5) | `status: archived` + пометка в `MAIN_TZ_INVENTORY.md` |
| этот master-файл `DialogBacklogToKanban_TZ.md` | `status: completed` / `archived` **после приёмки** (сейчас `draft`) |

Эта правка ТЗ **не** меняет инвентарь и status — то зона `TZ:finalize` / `ORCH:shared-state` / DECOMM-lane.

#### Скиллы-дубли — удалить (мёртвые)

| Путь | Судьба |
|---|---|
| `~/.hermes/profiles/default/skills/productivity/dialog-backlog/` | симлинк; **удалить** |
| `~/hermes-workspace/skills/productivity/dialog-backlog/` | `SKILL.md` + `references/dedup-anchors.md` + `scripts/dedup_anchors.py`; **удалить**. Git править **только по явному слову Саши** |

#### Реестры / ссылки (~15 файлов, `DEC:inventory` §5)

Чистить / перенацелить (исполнение — `ORCH:shared-state` / DECOMM-lane, не этот патч):

| Где | Что сделать |
|---|---|
| `EcosystemManifest.json` (+ render + digest) | убрать `tools.dialog_backlog` и skill-связку; перегенерация render/digest |
| `MAIN_TZ_INVENTORY.md` | DialogBacklog → `archived`; DialogBacklogToKanban → `completed` |
| `skills-registry.md` | убрать dialog-backlog / vm_dialogbacklog / связанные строки |
| `Home.md` (Dataview) | убрать `TASK FROM "Hermes-Backlog/dialog-backlog"` |
| `WorkVault/AGENTS.md` | убрать DialogBacklog из списка активных |
| `TZ/AGENTS.md` | проверить / убрать упоминания |
| `crons-registry.md` | убрать C-03 `vm_dialogbacklog` и связанные строки |
| `.hermes/scripts/` `cleanup_after_sync.sh`, `watchdog_tools.sh`, `sync_hermes_config.sh`, `trigger_sync.sh` | убрать ссылки на `dialog-backlog.md` |
| PIIScan baseline | пересчитать после удаления md |
| `.usage.json` | обновить после удаления скиллов |

GLOSSARY-упоминания DialogBacklog как живого инструмента — снять в том же контуре docs (не в этой правке).

#### НЕ трогать (из инвентаря)

- `~/WorkVault_backup/`
- `~/.hermes/_Archives/dialogbacklog-20260906-100453/`
- git-зеркала `~/hermes-config/` / `~/hermes-config-repo/`
- `~/hermes-workspace/docs/backlog.md`

### Разграничение с параллельной DECOMM-карточкой

На этой доске две lane. Это ТЗ описывает **оба** контура (контракт), исполнители **разделены** — двойной работы нет.

| Lane | Карточки (канон GLOSSARY) | Что делает | Чего не делает |
|---|---|---|---|
| **SKILL-CHANGE** (эта задача / репоинт) | `HF:impl` (+ хвост SKILL-CHANGE по §5.1) | Переписать `backlog-collector` / `backlog-analyst` на read-запрос triage; удалить `backlog-consolidation`; заменить/удалить референсы скиллов | Не сносит `~/USERTOOLS/DialogBacklog/`, live md, манифест, инвентарь |
| **DECOMM** (`dialogbacklog-decomm`) | `DEC:inventory` → `GATE:go` → `HF:backup` → `DEC:exec` → `ORCH:shared-state` → `GATE:done` | Физический вывод инструмента: скрипты, md (снимок/заглушка), дубли скиллов, реестры, drift-check redirect | Не переписывает канон «бэклог»→triage (это SKILL-CHANGE); не трогает IDEA/* triage |

`DEC:inventory` (`t_3f60b929`) уже выполнен — источник карты удаления. `GATE:go` ждёт R3 «удаляй». Репоинт скиллов **не** входит в `DEC:exec`.

### Контракт «бэклог» после репоинта

| Поле | Значение |
|---|---|
| Выход | `hermes kanban list --status triage` → карточки `IDEA/*` (title, status, body-превью). **Не** `dialog-backlog.md` |
| Триггеры | «бэклог», «что в бэклоге», «проверь бэклог», «покажи бэклог» |
| НЕ показывает | закрытые `[x]`, архив md, историю md |

SoT открытых идей после репоинта: `~/.hermes/kanban.db`, статус `triage`. Dispatcher по-прежнему поднимает только `ready`; карточки triage воркер не берёт.

### Критерии успеха

- Фраза «бэклог» → список triage-карточек канбана, не таблиц инструмента DialogBacklog.
- Через ≥1 tick dispatcher triage-карточки не подхватываются воркером (остаются `triage`).
- Скрипты DialogBacklog отсутствуют на диске после DECOMM-вывода.
- `dialog-backlog.md` после решения Саши — удалён / заглушка; бэкап в `~/.hermes/_Archives/dialogbacklog-*`.
- Нет регрессии графа `DEV/<slug>`, `auto_decompose: false`, HITL-гейтов.

### Что НЕ трогать (границы)

- Ядро канбана (`kanban_db`, статусы, `auto_decompose`), граф `DEV/<slug>`, гейты.
- IDEA/* triage карточки (в т.ч. шесть id выше).
- `state.db`, git-зеркала конфигов, `WorkVault_backup`.
- Gateway — не рестартовать. Автокрон не ставить.

---

## Приложения к ТЗ

| Приложение | Путь | Статус |
|---|---|---|
| Инвентаризация DECOMM DialogBacklog | карточка `DEC:inventory` (`t_3f60b929`), файл `DEC-inventory-dialogbacklog.md` | выполнена 2026-09-23 |
| Dry-run миграции `[ ]` → IDEA/* | `TZ/DialogBacklogToKanban/appendix_dry_run_<YYYYMMDD>.md` | после dry-run реализации (таблица якорь → task_id), если ещё понадобится |

---

## Открытые вопросы

Нет. Вопросы 1–2 v0.1.0 закрыты брифом Саши 23.09.2026 (см. секцию v0.2.0):

1. **Заглушка vs удаление `dialog-backlog.md`.** Решение: полный снимок в бэкап → live-заглушка → **удаление** на последнем шаге чистки по явной фразе «удаляй файл бэклога» (не вечный указатель).
2. **Судьба analyst.** Решение: **удаление при DECOMM** (`backlog_analyst.py` + md-вход скилла). Phase 2 на канбане не делается; промпты A/B/C — только в `_Archives/dialogbacklog-*`.
