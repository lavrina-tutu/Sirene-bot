---
name: hermes-dev-glossary
description: "Use when сокращения фаз цепочек разработки Hermes."
version: 0.1.0
author: Сирень
platforms: [linux]
metadata:
  hermes:
    tags: [dev, glossary, process, tz, hermes-feature, kanban, terminology]
---

# Hermes Dev Glossary — однозначность терминов пайплайна разработки

## Когда и зачем
В процессе разработки Hermes (доработка ТЗ, каталог цепочек, канбан-фазы, согласование с Сашей) используются сокращения фаз и термины. Без единого справочника агент и Саша «сбиваются»: неочевидные акронимы (пример: `BRF`), и семантические коллизии (путаница между скиллом, фазой, ролью и кейсом). Этот скилл кодирует правила, чтобы каждый ход начинался уже с однозначных терминов.

## Канон глоссария
- **Единый источник правды (канон):** `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`. Не appendix, не скилл, не копия в USER/MEMORY. Дрейф лечится правкой ОДНОГО файла + version bump — не трёх копий.
- **Дизайн трёх слоёв (решение архитектора, appendix_glossary-architecture_20260908.md):**
  1. Канон `TZ/GLOSSARY.md` — полный текст (3–5 КБ, ~1–2k ток). Не инжектится сам → не жрёт токены постоянно.
  2. Компакт-индекс в `USER.md` (~213 симв.) — коллизии + путь. TG-бриф Сирени (cwd=`~`) видит USER всегда.
  3. Якорь в `TZ/AGENTS.md` (4–6 строк) — только когда cwd = каталог ТЗ (Cursor `cd TZ`).
- **Обязательный `read_file` канона** в `tz-workflow` и `hermes-feature` ПЕРЕД первым `PREFIX:фаза`.

## Нейминг фаз
Формат: **`PREFIX:фаза`**. Префикс = слой, НЕ кейс.

| PREFIX | Слой | Не путать с |
|---|---|---|
| `BRF:` | бриф в Telegram, **не карточка** | — |
| `GATE:` | гейт-подтверждение Саши | — |
| `TZ:` | фаза записи ТЗ | скилл `tz-workflow`, документ «ТЗ» |
| `HF:` | фаза реализации hermes-feature | скилл `hermes-feature` |
| `ORCH:` | ТОЛЬКО фаза shared-state (`ORCH:shared-state`) | роль «оркестратор»/Сирень |
| `REV:` | ревизор (флаг кейса) | — |
| `BUG:`/`RS:`/`MIG:`/`DEC:`/`SK:` | диагностика/research/миграция/удаление/скилл-изменение | кейсы BUGFIX/RESEARCH/MIGRATION/DECOMM/SKILL-* |

## Правила однозначности терминов
1. **Запрет** голых `TZ`/`HF`/`ORCH`/`DEV` без контекста. `DEV:impl` — сбой (DEV = кейс, не фаза).
2. **Запрет синонимов** вне канона: `HF:fix` → `HF:impl`; `TZ:architect` как бриф → `BRF:*` (бриф уже в TG); **`TZ:analyze` / `TZ:architect` как ФАЗЫ — не существуют** (содержание старых шагов 1–3 живёт в `BRF` + `TZ-WRITE`; именно эти две лишние фазы — корень раздувания графа и неоднозначности процесса).
3. **Первое упоминание** (Саше / в appendix): акроним + русская расшифровка, дальше — канон. Пример: `HF:impl (реализация, скилл hermes-feature)` → далее `HF:impl`.
4. **Слои токена:** Кейс ≠ Роль ≠ Скилл ≠ Документ ≠ Фаза. Проверка: фраза должна оставаться однозначной без контекста чата.
5. **Коллизии (писать так):**
   - Документ = «ТЗ», `master-ТЗ`, `TZ/<Tool>/<Tool>_TZ.md` (не «TZ» про файл).
   - Скилл ТЗ = `tz-workflow`. Скилл реализации = `hermes-feature` (не «HF» про скилл).
   - Роль = оркестратор / Сирень (не «ORCH»). `ORCH:shared-state` — только фаза.
   - Кейсы = DEV/CHANGE/BUGFIX/RESEARCH/MIGRATION/DECOMM/SKILL-DEV/SKILL-CHANGE — полные имена в речи; короткие коды DEV/CHG/BUG/RS/MIG/DEC/SK только в таблицах/id/компакте USER.

## Кейсы (8) — коротко
DEV (новый инструмент/фича) · CHANGE (доработка существующего) · BUGFIX · RESEARCH (анализ без кода) · MIGRATION · DECOMM (удаление) · SKILL-DEV · SKILL-CHANGE. Полные цепочки — в каталоге кейсов (`DevKanbanPipeline_TZ` / `ProcessImprovement/appendix_chains-and-skills-audit`).

## Блоки и каркас (единая библиотека, не 8 рукописных цепочек)
Целевая модель Саши: **НЕ клонировать план-цепочку в каждый кейс, а собрать кейс из переиспользуемых блоков** (как функции/библиотеку). Кейс = конкатенация блоков + свои особые фазы. Полный отчёт: `ProcessImprovement/appendix_chains-unification_20260908.md`.

**Три слоя токена:**
| Слой | Как писать | Карточка канбана? |
|---|---|---|
| Кейс | полное имя | нет (корень `DEV/<slug>`) |
| **Блок** | `ALL-CAPS` / `PREFIX-TAIL` | **нет** — блок разворачивается в фазы |
| Фаза | `PREFIX:фаза` | **да** |

Запрет: карточка-имя блока (`PLAN-IMPL-TAIL`, `HF-хвост`), голый блок в title. Заголовок карточки — только фаза §канон.

**Библиотека блоков:**
- `BRF` (бриф в TG; режимы full/light/delta/scope/confirm) — `BRF` и есть и префикс фаз, и блок (как `TZ` = только префикс фазы); имя `BRIEF` не вводить (коллизия с `BRF`).
- `BRIEF-CLOSE` (GATE:brief-closed + создать граф parents).
- `TZ-WRITE` (стабилизация/запись ТЗ; режимы new/full/patch/freeze).
- `REV` (крючок: REV:tz внутри TZ-WRITE, REV:plan внутри PLAN-IMPL-TAIL, REV:report в RESEARCH).
- `TAKE-INTO-WORK` (GATE:take-into-work).
- `HF-COMPRESS` (опц. префикс плана; skip на stub/BUGFIX/мелочи).
- **`PLAN-IMPL-TAIL` (ключевой общий)** = `HF:plan → [REV:plan] → GATE:plan-approve → HF-TAIL`. Сашин «от плана до регистрации в экосистеме».
- `HF-TAIL` (суффикс) = `HF:backup → impl → test → docs-handoff → ORCH:shared-state → GATE:done`.
- `DX` (только BUGFIX) = `BUG:diagnose → GATE:diagnose-review`.
- `RS` (research без кода) = `RS:collect → analyze → [REV:report] → GATE:done`.
- `MIG-TAIL` = `MIG:plan → plan-approve → backup → (MIG:block-k → block-accept)* → ORCH → done`.
- `DEC-PRE` + `DECOMM-TAIL` (замена `HF-TAIL-min`) = `DEC:inventory → GATE:go`; `HF:backup → EXEC → ORCH → done` (EXEC ∈ {DEC:exec, MIG:exec}).
- `SK-PRE` (SKILL-CHANGE, `SK:preflight`).

**Сборка кейсов (одна строка):**
- DEV = BRF(full)→BRIEF-CLOSE→TZ-WRITE(new)→TAKE-INTO-WORK→[HF-COMPRESS]→PLAN-IMPL-TAIL
- CHANGE = BRF(light)→BRIEF-CLOSE→TZ-WRITE(full)→take→[comp]→PLAN-IMPL-TAIL
- BUGFIX = DX→BRF(delta)→TZ-WRITE(patch)→take→PLAN-IMPL-TAIL (compress skip, REV OFF)
- RESEARCH = BRF(scope)→RS (нет TZ-WRITE/TAKE-INTO-WORK/PLAN-IMPL-TAIL/ORCH)
- MIGRATION = BRF(light)→BRIEF-CLOSE→TZ-WRITE(freeze)→take→MIG-TAIL
- DECOMM = BRF(confirm)→DEC-PRE→DECOMM-TAIL
- SKILL-DEV = DEV {workspace=skills, REV ON, ORCH restore}; SKILL-CHANGE = SK-PRE→CHANGE | SK-PRE→DECOMM (удаление); ≤2 файла compress skip/REV OFF

**Инварианты каркаса:**
1. Кейс НЕ содержит скопированной развёртки `PLAN-IMPL-TAIL` — только вызов блока.
2. Один `agent -p` = одна модель = одна роль.
3. Бриф не карточка; граф после `BRIEF-CLOSE`.
4. Реализация только после `TAKE-INTO-WORK` (DECOMM: после `GATE:go`).
5. Манифест/restore/.env/jobs.json — только `ORCH:shared-state` (Сирень), исполнитель туда не пишет.
6. One-pass auto: `take-into-work`, `plan-approve`, `done`. Никогда: `diagnose-review`, `GATE:go`, `GATE:block-accept`.
7. Parent `HF:impl` = `HF:backup` (+ при необходимости `GATE:plan-approve`), НЕ `TZ:stabilize`.

## Роли и модели (Cursor-пул/подписка)
- Оркестратор = Сирень (default Hermes) — бриф в TG, не придумывает.
- Архитектор = `cursor-grok-4.6-high`.
- Ревизор = `claude-sonnet-5-medium` (опционален, флаг кейса).
- Исполнитель/Компрессор/Координатор(механика) = `composer-2.5`.

## Питфоллы
- **НЕ создавать** отдельный скилл-глоссарий («No router/index/hub»), **НЕ** вшивать полный глоссарий в tz-workflow/hermes-feature (дубль+дрейф; на карточку — 1 скилл), **НЕ** весь текст в USER/MEMORY (лимиты: USER ~1000 цель, MEMORY ограничен; процедуры в память нельзя).
- **USER.md лимит:** Саша требует держать профиль ≤ ~1000 символов ВКЛЮЧАЯ компактный глоссарий; официальный потолок Hermes (1375) НЕ ориентир — у Саши жёстче.
- **Не «живёт сам по себе»:** файл, который никто не обязан читать → дрейф. Лечится обязанностью `read_file` в скиллах, НЕ новым скиллом.

## Где смотреть детали
- Дизайн глоссария: `~/WorkVault/Hermes-Backlog/TZ/ProcessImprovement/appendix_glossary-architecture_20260908.md`
- Каталог цепочек + аудит скиллов: `~/WorkVault/Hermes-Backlog/TZ/ProcessImprovement/appendix_chains-and-skills-audit_20260907.md`
- **Единый каркас (библиотека блоков, кейс=сборка):** `~/WorkVault/Hermes-Backlog/TZ/ProcessImprovement/appendix_chains-unification_20260908.md` — источник блока `PLAN-IMPL-TAIL` и формул сборки кейсов. Согласуется с этим скиллом; при расхождении править одновременно (консистентность глоссарий↔цепочки↔скиллы).