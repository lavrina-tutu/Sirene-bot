---
name: C1-skill-hygiene-agents-map
description: "C1: гигиена индекса скиллов (description ≤60, триггер первым) + prune stale/0-use через skills.disabled + цифры и retrieval-led в AGENTS.md. Не новый инструмент, не treedocs."
version: 0.1.0
date: 2026-10-18
status: ready
author: архитектор (cursor-grok-4.6-high, TZ:patch, slug c1-gigiena-skillov-i-karta-v-agents)
platforms: [linux]
tags: [skills, AGENTS.md, hygiene, C1, SKILL-CHANGE]
tool: _misc
last-section-added: 2026-10-18 — v0.1.0 TZ:patch C1 по RESEARCH-отчёту
packet_slug: c1-gigiena-skillov-i-karta-v-agents
source_research: Hermes-Backlog/dev/sravnit-skills-vs-tree-docs-dlya-navigatsii-agen/RS-collect-analyze-report.md
---

# C1 — гигиена скиллов и карта в AGENTS.md

выжимка ≠ SoT. При расхождении открыть этот файл, затем RESEARCH-отчёт (§4 C1) и код `SKILL_PROMPT_DESC_LIMIT`.
`[NEW-ENTITY, требует согласования Саши]` в этом пакете **нет** (вариант C2 / USERTOOLS Treedocs **не** входит).

**Оркестратору:** это master-ТЗ пакета. Сменить `tz_path` / `tz_version` с RESEARCH-отчёта на:

- path: `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/_misc/TZ-c1-skill-hygiene-agents-map-20261018.md`
- version: `0.1.0`

Инвентарь (`MAIN_TZ_INVENTORY.md`, секция `TZ/_misc/`) — на `TZ:finalize`, не в этом ходе.

**Факт объёма (не команда skip / не LIGHT):** live-индекс с `os.walk(..., followlinks=True)` даёт **73** SKILL.md с `description` > 60; плюс 2× `AGENTS.md`, тело `skill-authoring-principles` (и зеркало нормы в `hermes-agent-skill-authoring`), `config.yaml` (`skills.disabled`). >>3 файлов. Рецепт SKILL-CHANGE полный, `REV:tz` остаётся. Архитектор кейс не меняет (G5).

---

## Цель

Реализовать **C1** из исследования 2026-10-18: скиллы = поведение; карта структуры = уже существующие `AGENTS.md` + `EcosystemManifest.digest.md` + `entities.json`. Не A (только описания без карты), не B (дерево вместо скиллов), не C2.

Сирень на Telegram видит индекс Hermes (`SKILL_PROMPT_DESC_LIMIT = 60` → обрезка `[:57]+"..."`). Триггер обязан быть в первых 57 символах **исходной** `description`, иначе маршрут слепой. 68 нулевых имён засоряют индекс; файлы не удалять.

---

## Reuse-first

| Уже есть | Почему не закрывает | Что делаем |
|---|---|---|
| `agent/skill_utils.py` `SKILL_PROMPT_DESC_LIMIT=60` + обрезка | режет хвост, **не** чинит источник | не трогать код обрезки; переписать frontmatter |
| `skill_linter` / `skill_manager_tool` — 60 на **новых** скиллах | старые не мигрированы | миграция live-индекса |
| `skills.disabled` в `config.yaml` + `get_disabled_skill_names()` | ключ отсутствует/пуст | заполнить stale∩zero-use |
| `all-skills-hygiene` | delete только с императивом; индекса не чистит | строка: prune = `skills.disabled`, не delete |
| `~/AGENTS.md`, `WorkVault/AGENTS.md` | устаревшие «24+» / «~200+»; нет retrieval-led | поправить цифры + одна строка |
| `EcosystemManifest.digest.md` | карта **инструментов**, не индекс скиллов | указатель из AGENTS.md, не дублировать манифест |
| DandyLyons/treedocs | macOS-only, Swift, нет на VM | **не** ставить; **[NEW-ENTITY]** C2 не создавать |

---

## Постановка (диск, 2026-10-18)

Источник смысла: `dev/sravnit-skills-vs-tree-docs-dlya-navigatsii-agen/RS-collect-analyze-report.md` (version=`research-2026-10-18`). Q-1 отчёта («C1 сразу / eval / C2») закрыт самим поездом SKILL-CHANGE C1.

| Замер | Значение |
|---|---|
| Имена в Telegram-индексе (`hermes prompt-size`) | 224 |
| Live `SKILL.md` без followlinks | 151; с followlinks (как индекс) | больше; уникальных resolved ~237 |
| Live `description` >60 **без** followlinks | 15 (замер RESEARCH — неполный) |
| Live `description` >60 **с** followlinks | **73** (норматив этого ТЗ) |
| `.usage.json` | 222: 143 active, 79 stale, pinned=0 |
| `use=0` ∧ `view=0` | 68 (57 stale + 11 active) |
| `entities.json` | 47 сущностей |
| `Entities/` top-level dirs | 33 |
| `TZ/**/*_TZ.md` | 100 |
| `~/AGENTS.md` | правила + Paths; цифр 350/200+/24+ **нет** |
| `WorkVault/AGENTS.md` | деревья; «24+ инструмента», «~200+ сущностей» |

T4 (Claude cache tax) и T5 (1% listing drop) на DeepSeek/Hermes **не переносятся**. Код обрезки и `SKILL_PROMPT_DESC_LIMIT` не менять.

Два рантайма: Сирень видит Hermes-индекс; Cursor CLI — Cursor skills + `WorkVault/AGENTS.md`. Этот пакет чинит **оба AGENTS.md** и **Hermes-индекс**. Cursor `<available_skills>` не является индексом Hermes.

---

## P0 — маршрутизация скиллов

### P0.1 Норма description

Для каждого SKILL.md, который попадает в индекс Сирени (скан `~/.hermes/skills` с `followlinks=True`, как `iter_skill_index_files`):

1. `description` во frontmatter: **≤ 60 символов** (`len` Unicode, как в `skill_utils`).
2. Триггер — в **первых 57** символах (окно до `"..."`).
3. Тело скилла не переписывать, кроме P0.2 и короткой строки в `all-skills-hygiene` (P0.3).

**Алгоритм переписи (исполнителю, не свободный рерайт):**

- Если первые 57 уже содержат рабочий триггер (`Use when:`, явное RU-слово из старого хвоста `Triggers:`, имя команды) — **сжать на месте**: оставить первый триггерный клауз, отрезать хвост так, чтобы `len≤60`. Не выдумывать новый триггер у живых процедурных скиллов (`hermes-feature`, `tz-workflow`, `protocolfromsummary`, …).
- Если триггер только в хвосте — **перенести в позицию 0**, затем уложиться в 60.
- Канон файла: есть копия в `~/hermes-workspace/skills/` → править **workspace** (live = симлинк или sync). Нет в workspace → править только live `~/.hermes/skills/`.
- Два пути одного `name` (`mattermost-loop-api` live root **и** `productivity/`) — одинаковый ≤60 текст в обоих; **не удалять** ни один файл.
- Version bump: description-only = patch (`x.y.Z`), если поле `version` есть.

**Именованные слепые / redirect (рецепт, не единственные в sweep):**

| name | Смысл | Рецепт ≤60 (можно короче, триггер первым) |
|---|---|---|
| `hermes-prompt-architecture` | триггер «проверь промпт» отрезан | `проверь промпт: стек SOUL, AGENTS, profile` |
| `charter-fill` | REDIRECT | `заполни устав: REDIRECT pmo-charter-fill` |
| `project-charter-authoring` | REDIRECT | `устав/бриф: REDIRECT pmo-charter-fill` |
| `confluence-doc-edit-cursor` | REDIRECT | `правим Confluence устав: REDIRECT pmo-charter-fill` |
| `confluence-page-editing` | REDIRECT split | `правка Confluence: tutu-confluence-jira / page-to-schedule` |
| `mattermost-loop-api` | триггеры в хвосте, 2 копии | `loop api / mattermost api: Loop ТУТУ REST v4` |
| `skill-authoring-principles` | 237, триггер в хвосте | `создай скилл / патч скилла: нормы authoring` |
| `all-skills-hygiene` | 290, триггер в хвосте | `проверь скиллы: аудит дублей и stale` |
| `confluence-gantt-plan` | DEPRECATED | `DEPRECATED: use edit-plan-confluence` |
| `workvault-sync` | trigger-only | `rclone / синк хранилища: systemd WorkVault, без вопросов` |
| `hermes-multi-profile-skills` | live-only, 350 | `скиллы пропали: git hermes-workspace → симлинки профиля` |
| `skill-dedup-merge-workflow` | live-only, 339 | `слей скиллы: аудит дублей Hermes → merge` |

Остальные из 73 — по алгоритму выше. Цель не «оставить 15», а **весь индекс ≤60**. Замер RESEARCH «15» получен без followlinks и **проигрывает** walk как у индексатора.

### P0.2 Норма authoring (два лимита)

В `skill-authoring-principles` (все вхождения, сейчас ≥4: post-flight, pitfalls, find-команда, checklist) и в `hermes-agent-skill-authoring` (описание / checklist «≤ 1024»):

- **60** = лимит **индекса** (`SKILL_PROMPT_DESC_LIMIT`); триггер в первых 57.
- **1024** = лимит **загрузки файла** (`MAX_DESCRIPTION_LENGTH`); превышение → скилл не грузится.

Не писать, что 1024 — норма description для промпта. Константу загрузки в коде **не** менять.

### P0.3 Prune индекса, не delete

Не удалять SKILL.md. Не `skill_manage(action='delete')`.

**Критерий disable (снимок 2026-10-18 = 57 имён, приложение А):**

```
state == "stale"
AND use_count == 0 AND view_count == 0
AND NOT pinned
AND name ∉ ESSENTIAL_SKILLS   # сейчас только hermes-agent
```

Механика: существующий ключ `skills.disabled` в `~/.hermes/config.yaml` через `hermes_cli.skills_config.save_disabled_skills` (или эквивалентный CLI), **не** строка-JSON в YAML (pitfall `parse_config_string_list`). Перед записью — бэкап конфига в фазе `HF:backup`, не в TZ:patch.

**Не disable:**

- 11 **active** zero-use (в т.ч. `resume-cv-authoring` от 2026-10-14) — бар 60 дней `all-skills-hygiene` не пройден.
- 22 stale **с** use/view (`hermes-cost-audit` 33, `pmo-charter-fill` 9, `cursor-code` 9, …) — маршрутизация живая.
- `hermes-agent`.

В `all-skills-hygiene` добавить одну строку/ряд таблицы: шум индекса = `skills.disabled` по критерию выше; NEVER auto-delete остаётся.

После правки конфига **не** рестартить gateway. Новый индекс — в новой сессии Сирени; `skill_view` по явному имени для disabled может не пройти scan-filter — для stale∩zero это приемлемо (файлы на диске, enable = убрать из списка).

---

## P1 — пассивная карта (AGENTS.md)

Не дублировать манифест. AGENTS.md = указатель.

### `~/WorkVault/AGENTS.md` (CWD Cursor)

- `Все ТЗ (24+ инструмента)` → актуальная цифра **100** файлов `*_TZ.md` **или** «см. `MAIN_TZ_INVENTORY.md`» без «24+» как текущего факта.
- `~200+ сущностей` → **47** в `Registries/entities.json` (каталог `Entities/`: 33 top-level dirs; SoT счёта = json).
- Строка «Активные инструменты (24+):» → не выдавать 24+ за текущий счёт; имена оставить как указатель, SoT = digest.
- Добавить retrieval-led (структурные вопросы, не «который час электричка»):

  > Для структурного поиска: сначала `Registries/EcosystemManifest.digest.md` и таблица Paths; код не Grep-ить, пока не известен корень.

Цифры «~350 skills» в этих двух AGENTS.md **нет** (это был бриф RESEARCH). Не выдумывать строку «350». При желании одной строкой: в индексе Telegram 224 имени — только если есть естественное место, не раздувать дерево.

### `~/AGENTS.md` (CWD Сирень)

Цифр 24+/200+ нет. Добавить ту же retrieval-led строку в секцию Paths (или сразу после Skill priority). Не копировать ASCII-деревья WorkVault сюда.

---

## P2 — вне пакета

YAML/JSON-карта durable-корней, `explore`, drift-check нового дерева, Linux-клон treedocs, USERTOOLS «Treedocs» = **C2 [NEW-ENTITY, требует согласования Саши]**. Этот поезд **не** делает P2.

---

## Критерии приёмки (AC)

Все класс **S** (поезд не ждёт Сашу). Operator-hold нет.

| ID | Класс | Формулировка |
|---|---|---|
| AC-001 | S | У каждого SKILL.md в скане `~/.hermes/skills` с `followlinks=True` (как `iter_skill_index_files`) `len(description)≤60`. Verify: walk + `hermes prompt-size --json --platform telegram` — в блоке skills нет обрезанных хвостов `"..."` из-за исходного >60 |
| AC-002 | S | У тех же description триггер (сохранённый клауз или слово из старого `Triggers:`/`Use when:`) входит в первые 57 символов. Именованные слепые: `hermes-prompt-architecture` — «проверь промпт» в первых 57; четыре redirect — имя целевого скилла **и** триггер в первых 57 |
| AC-003 | S | `skill-authoring-principles` и `hermes-agent-skill-authoring`: текст различает 60 (индекс) и 1024 (загрузка); ни одна норма не утверждает «description ≤1024» как лимит индекса |
| AC-004 | S | `skills.disabled` содержит ровно критерий P0.3 на снимке impl (эталон приложения А = 57 имён; допуск: пересечение с эталоном, минус те, кто к impl перестали быть stale∩zero). Не содержит `hermes-agent`, pinned, 11 active zeros, stale-with-use |
| AC-005 | S | `hermes prompt-size --json --platform telegram`: имена из `skills.disabled` **отсутствуют** в индексе |
| AC-006 | S | `WorkVault/AGENTS.md`: нет «~200+» и «24+» как текущего факта; есть 47/100 или указатель на inventory/digest; есть retrieval-led строка |
| AC-007 | S | `~/AGENTS.md`: есть та же retrieval-led строка |
| AC-008 | S | Код обрезки не менялся: `SKILL_PROMPT_DESC_LIMIT=60`; `extract_skill_description` / алгоритм `[:57]+"..."` — пустой diff относительно baseline `HF:backup`. `memory.provider` остаётся `honcho` |
| AC-009 | S | Ни один SKILL.md не удалён (сравнение множества путей live+workspace с baseline). Дубль `mattermost-loop-api` оба ≤60, оба на диске |
| AC-010 | S | Нет каталога USERTOOLS/Treedocs, нет нового инструмента в манифесте, нет маркера `[NEW-ENTITY]` в diff пакета. Gateway не рестартовали (нет evidence restart в journal) |

---

## Что НЕ трогать

- Удаление скилл-файлов и `skill_manage(action='delete')` без императива Саши (`удаляй`).
- `memory.provider` (honcho).
- `SKILL_PROMPT_DESC_LIMIT`, тело `extract_skill_description`, compact_categories / `agent.coding_context`, T4/T5-механики.
- Рестарт gateway. Кроны (`ставь кроны` не было).
- Master-ТЗ инструментов (`TZ/<Tool>/<Tool>_TZ.md`), включая `SkillsImprovement_TZ.md` (чужой контур Trisigma) и `DevWorkflow_TZ.md`.
- Тела процедурных скиллов кроме description и оговорённых строк authoring/hygiene. Баннер dual-path в `hermes-feature` / `tz-workflow` не трогать.
- Новый USERTOOLS, treedocs, Swift, npm-fork, YAML-карта корней (P2/C2).
- SQL/кэш выжимок DevWorkflow. `kanban.db`.
- `.usage.json` как SoT (это телеметрия; не затирать use_count, чтобы «почистить»).
- Профили кроме тех, куда ORCH и так делает restore симлинков.

---

## Связи с экосистемой

| Компонент | Роль | Как вызывать | Ограничение |
|---|---|---|---|
| RESEARCH-отчёт C1 | постановка | читать §4, AC-RS-* | не SoT после этого файла |
| `skill_utils.py` / `prompt_builder.py` | индекс, disable, обрезка | read-only в этом пакете | не патчить обрезку |
| `hermes_cli.skills_config.save_disabled_skills` | запись `skills.disabled` | CLI/API, не raw JSON-string | ESSENTIAL_SKILLS не disable |
| `all-skills-hygiene` | норма «не auto-delete» + строка prune | SKILL.md | не cron delete |
| `skill-authoring-principles` | норма 60 vs 1024 | SKILL.md | не менять MAX в коде |
| `~/AGENTS.md`, `WorkVault/AGENTS.md` | пассивная карта | указатель | не копия манифеста |
| `EcosystemManifest.digest.md` | SoT инструментов | Path + retrieval-led | не плодить дерево файлов |
| `entities.json` | SoT счёта сущностей | 47 | не путать с dirs=33 |
| `restore-all-skills.sh` | симлинки workspace→live | фаза ORCH | не копировать git→WorkVault |
| `SkillsImprovement` | чужое зонтичное ТЗ | не патчить | Trisigma A/B/C |

---

## Контракты (кратко)

**Источник истины description:** frontmatter SKILL.md (workspace, если файл там есть). Индекс = производная (`extract_skill_description` + `skills.disabled`).

**Вход prune:** `.usage.json` поля `state`, `use_count`, `view_count`, `pinned`.

**Выход prune:** `config.yaml` `skills.disabled: [names…]` (YAML list).

**Breaking:** имена из disabled пропадают из `<available_skills>`. Enable = убрать имя из списка. Неbreaking для файлов.

---

## Открытые вопросы

Блокирующих нет. Поезд = C1 сразу (Q-1 RESEARCH закрыт).

Зафиксированные решения архитектора (смена = `TZ:patch`, не молчаливый impl):

1. Disable = stale∩zero (57), не все 68 нулей и не все 79 stale.
2. Sweep description = весь followlinks-индекс >60, не «15 без симлинков».
3. P2/C2 не входят. `[NEW-ENTITY]` нет.

---

## Порядок реализации (намёк для `HF:plan`, не IAC)

1. Baseline: список SKILL.md, `prompt-size`, `.usage.json`, `config.yaml`, оба AGENTS.md.
2. `HF:backup` конфигов + skills.
3. Description sweep (P0.1) → authoring text (P0.2) → hygiene row (P0.3).
4. `skills.disabled` по критерию.
5. AGENTS.md (P1).
6. Не restore/gateway из impl; ORCH — симлинки как обычно.
7. Verify AC-001…010 командами walk + `prompt-size` + grep запретов.

---

## Приложение А — снимок stale∩zero на 2026-10-18 (57)

`airtable`, `apple-notes`, `apple-reminders`, `architecture-diagram`, `arxiv`, `ascii-art`, `ascii-video`, `baoyu-infographic`, `blogwatcher`, `claude-design`, `codebase-inspection`, `comfyui`, `computer-use`, `confluence-people-resolve`, `design-md`, `docx`, `dogfood`, `evaluating-llms-harness`, `excalidraw`, `findmy`, `github-auth`, `github-code-review`, `github-issues`, `github-pr-workflow`, `github-repo-management`, `grounded-citations`, `hermes-docker-pitfalls`, `himalaya`, `huggingface-hub`, `humanizer`, `imessage`, `inspecting-hermes-desktop-dom`, `llama-cpp`, `llm-wiki`, `manim-video`, `maps`, `nano-pdf`, `node-inspect-debugger`, `notion`, `openhue`, `p5js`, `popular-web-designs`, `powerpoint`, `pretext`, `python-debugpy`, `requesting-code-review`, `serving-llms-vllm`, `simplify-code`, `sketch`, `songwriting-and-ai-music`, `systematic-debugging`, `teams-meeting-pipeline`, `test-driven-development`, `touchdesigner-mcp`, `weights-and-biases`, `xurl`, `youtube-content`.

11 active zeros **не** в списке: `background-agent-run`, `box`, `competitor-news-monitor`, `email-inbox-triage`, `github`, `hermes-mcp-setup`, `meeting-action-items`, `product-price-monitor`, `project-context-digest`, `resume-cv-authoring`, `weekly-review-planning`.

---

## Приложения к ТЗ

| Файл | Содержание |
|---|---|
| `dev/sravnit-skills-vs-tree-docs-dlya-navigatsii-agen/RS-collect-analyze-report.md` | RESEARCH C1; не копировать в `TZ/_misc/` |

## Статус

Ready v0.1.0 (2026-10-18), `TZ:finalize`. REV:tz APPROVE. **Реализовано в HF:impl + HF:test (зелёный)**:

- AC-001: весь live-walk `~/.hermes/skills` (followlinks) description ≤60 — 0 над предел;
- AC-002: триггер в первых 57 у всех 77 переписанных; заглушка отсутствует;
- AC-003: authoring нормы 60 (индекс) vs 1024 (загрузка) в 2 скиллах;
- AC-004: `skills.disabled` = 57 stale∩zero; AC-005: не в индексе (проверено prompt-size);
- AC-006/007: оба AGENTS.md — цифры 100/47 + retrieval-led;
- AC-008: код обрезки не менялся (diff пуст), `memory.provider=honcho`;
- AC-009: ни один SKILL.md не удалён (live 151); дубль mattermost жив;
- AC-010: нет Treedocs / `[NEW-ENTITY]` / рестарта gateway.

Workspace git: `356256c` (impl) + `9de6b84` (rework trigger-first). Бэкап: `~/.hermes/_Archives/hermes-backup-20261018-1305-c1/`. Подробности: `HF-plan.md`, `p0-description-rewrites.tsv`, отчёт HF:test (`/tmp/HF-test-result.md`).
