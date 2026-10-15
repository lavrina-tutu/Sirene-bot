
Решение «v0.3.2 HITL overlay не трогать» **снято**. Overlay остаётся нормативом; вычищаются leftover-абзацы, которые ему противоречат.

---

# A. MITIGATION

## A0. Шесть замечаний ревизора → закрытие

| # | Замечание | Решение в этом плане |
|---|---|---|
| 1 | ONE-PASS вестигиален; старый раздел DKP не переписан | **B1 закрывает явно.** Норматив = секция «Критерии приёмки (AC / IAC) — канон v0.3.2». Leftover «Режим / Триггер «делай в 1 проход»» и зеркала (решения п.8–9/16, граф, таблица фаз, HITL, критерии успеха, `metadata.one_pass`, скиллы) **переписать** под: `GATE:take-into-work` HITL never auto; `GATE:done` never auto; `GATE:plan-approve` always auto **во всех режимах**. Фраза не меняет гейты (no-op). Сохраняется только: не skip фаз, не склейка ролей в один `agent -p`, корневой one-pass не плодит хвост карточек. |
| 2 | Два changeset на GLOSSARY 0.2.6 | **Развести.** `0.2.6` = обещанное DKP v0.3.2 (AC/IAC HITL). `0.2.7` = покрытие фаза→механизм этого пакета. Один write файла, frontmatter **0.2.7**, две changelog-секции. |
| 3 | Инвентарь 0.3.1, файл 0.3.2, прыжок на 0.3.3 теряет AC/IAC | **B8 одним ходом:** зафиксировать v0.3.2 (AC/IAC) **и** v0.3.3 (coverage + one-pass leftover). GLOSSARY в инвентаре → 0.2.7 (с пометкой, что 0.2.6 = AC/IAC). |
| 4 | `hermes-feature/SKILL.md:44` «take-into-work авто, требование 4» | **B4:** строка 40 + абзац ~123 + зеркала гейтов ~164–202. Требование 4 отменено (HITL вариант 1). |
| 5 | Блок 6Б namespace vs `t_2c8ee3b2` | **Не «другой namespace» и не «вне scope, безопасно».** 6Б = воздух Hermes (`cronjob`/`delegate_task` → `hermes chat -m`), тот же класс, что kanban `model_override`. Cursor-slug в колонке «Модель» как воздух **запрещён**. B4 — САНКТ-сноска. Д4 (живой `DEV/<slug>` → только `agent -p`) остаётся. |
| 6 | CHANGE, не LIGHT; в C/E нет `REV:tz` / stabilize/compress | **Кейс CHANGE.** C/E: `TZ:stabilize` + `TZ:compress` + `REV:tz` ON. `flag-waived` **не** ставить. |

## A1. Дыры Д1–Д8 / нарушения Н1–Н4 (из исходного плана, без отката)

| ID | Фаза / место | Решение | Роль | Slug / механизм |
|---|---|---|---|---|
| Д1 | `RS:collect` / `RS:analyze` | закрыть | архитектор | `cursor-grok-4.6-high` → `agent -p` |
| Д1 | `REV:report` | закрыть | ревизор | `claude-sonnet-5-medium` → `agent -p` |
| Д1 | `MIG:plan` / `DEC:inventory` | закрыть | архитектор | grok `agent -p` |
| Д1 | `MIG:block-k` / `MIG:exec` / `DEC:exec` | закрыть | исполнитель | `composer-2.5` `agent -p` |
| Д1 | `SK:preflight` | без Cursor | оркестратор | `wc -c`; >15k → compress (deepseek, без `agent -p`) |
| Д1 | `GATE:go` / `GATE:block-accept` | без Cursor | Саша HITL | нет модели |
| Д2 | Блок 8 | = кейс RESEARCH | collect/analyze=grok; `REV:report`=sonnet | `agent -p`; граф `RS:*` |
| Д3 | Блок 6А | исключение, не `PREFIX:фаза` | — | крон-чеклист; канон тестов = `HF:test` |
| Д4 | Блок 6Б | не канон живого графа | — | на `DEV/<slug>` только `agent -p` (инвариант 8) |
| Д4+зам.5 | колонка «Модель» 6Б | **тот же namespace, что `t_2c8ee3b2`** | — | запрет cursor/composer slug в `cronjob(model=)` / `delegate_task(model=)` |
| Д5 | `TZ:stabilize` | без Cursor | воркер | path/`version`/`mtime`; не `agent -p` |
| Д6 | `BRF:*` | гибрид | оркестратор + grok при вариантах | TG без карточки; варианты постановки = grok `agent -p` до ответа Саше |
| Д7 | `ORCH:shared-state` | без Cursor | оркестратор Сирень | `deepseek-v4-flash-0731` напрямую (не composer) |
| Д8 | `BUG:diagnose` | закрыть | архитектор | grok `agent -p`; убрать «оркестратор/self» |
| Н1 | kanban-dev-cases + case-chains | выровнять | компрессор | deepseek без Cursor |
| Н2 | orchestration Питфолл 3b | выровнять | компрессор | deepseek без Cursor |
| Н3 | корневой one-pass | сузить | — | не плодит хвост; **серия** `agent -p` по ролям, не один промпт ТЗ+код |
| Н4 | epic / aggregate | не трогать | — | пометка «не этот пайплайн» |
| — | `kanban_create --model` | не трогать запрет | — | сноску не ослаблять |
| — | cursor-cli | не трогать | — | компрессор там уже канон |

Канон-таблица (столбец модели = внутренний `agent -p`, **не** `kanban --model`) — вставить в DKP, см. B1.

**Факт по 6Б (зам.5), не гипотеза:** инструменты `cronjob(repeat=1)` / `delegate_task`; `enabled_toolsets: ["file","terminal","web"]`; «Cron-сессии НЕ получают MEMORY» — это Hermes-воркер, не бинарник `agent`. Slug `cursor-grok-4.6-high` / `composer-2.5` в `model=` этих tools = воздух tutu/OpenRouter, allowlist **без** этих slug → HTTP 400 / 0 tool-calls / `protocol_violation` (`t_2c8ee3b2`). Это **не** нативный Cursor CLI subagent.

---

# B. ТОЧНЫЕ ПРАВКИ

Пути:

| Файл | Где править | Runtime |
|---|---|---|
| GLOSSARY, DKP, MAIN_TZ, `_fix_plan` | `~/WorkVault/Hermes-Backlog/TZ/…` | диск |
| `tz-workflow`, `hermes-feature`, `kanban-dev-pipeline-orchestration` | `~/hermes-workspace/skills/devops/<name>/SKILL.md` | symlink `~/.hermes/skills/devops/<name>` |
| `kanban-dev-cases` | **только** `~/.hermes/skills/devops/kanban-dev-cases/` | нет в hermes-workspace |
| `cursor-cli` | не править | только `~/.hermes/skills/devops/cursor-cli/` |

Править 4/5/7 **в hermes-workspace**, не через разыменованный путь профиля как «другой файл».

## Версии (разведены)

| Артефакт | Было на диске | Этот пакет |
|---|---|---|
| DKP | **0.3.2** (AC/IAC уже в файле) | **0.3.3** |
| GLOSSARY | **0.2.5** | write **0.2.7**; секция changelog **0.2.6** (долг DKP 0.3.2) затем **0.2.7** (coverage) |
| MAIN_TZ DKP-строка | **0.3.1** (отстаёт от файла 0.3.2) | **0.3.2 + 0.3.3** в одном абзаце |
| MAIN_TZ GLOSSARY-строка | 0.2.5 | **0.2.7** (в тексте: 0.2.6=AC/IAC, 0.2.7=coverage) |
| tz-workflow | 2.4.1 | **2.4.2** |
| hermes-feature | 2.7.1 | **2.7.2** |
| orchestration | 1.1.1 | **1.1.2** |
| kanban-dev-cases | YAML version нет | не заводить |

### Что класть в GLOSSARY **0.2.6** (долг DKP v0.3.2, таблица «Целевые правки скиллов»)

1. Слой артефакта: `AC-###` в master-ТЗ пакета; `IAC-##` в `HF:plan` (`path`/`verify`/`depends`/`covers`). Не фазы и не скиллы. Омоним: САНКТ `IAC-01..10` ≠ пайплайнные `IAC-##`.
2. HITL Саши в DEV-цикле **ровно две** точки: `GATE:take-into-work` (AC-список) и `GATE:done` (отчёт AC).
3. §5 `GATE:` и инвариант 3: one-pass / любой режим = auto **только** `GATE:plan-approve` (`auto-pass: architect-plan`). `GATE:take-into-work` и `GATE:done` — **never auto**. Не skip фаз, не склейка в один `agent -p`.
4. `GATE:diagnose-review` остаётся в графе DX; **не** HITL Саши (архитектор + `REV:tz`). Требование 4 отменено.
5. CHANGE-LIGHT §2: убрать «`HF:plan` (вшит)» — конфликт со skip §5.2 / `PLAN-IMPL-TAIL-LIGHT`. IAC LIGHT = 1–3 строки в секции ТЗ / `_fix_plan` / body `BUG:diagnose`, не возврат полного `HF:plan`.

### Что класть в GLOSSARY **0.2.7** (этот пакет)

Указатель на таблицу DKP «Фазы ↔ скиллы»; строки без Cursor; BRF-гибрид; epic/aggregate «не этот пайплайн» одной фразой в §4 (таблицу фаз **не** копировать).

---

### B1. `TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` (0.3.2 → **0.3.3**)

**YAML:** `version: 0.3.3`; `last-section-added: 2026-09-25 — v0.3.3 leftover one-pass вычищен под канон v0.3.2; покрытие фаза→роль→механизм (RS/MIG/DEC/SK, ORCH без Cursor)`.

#### B1.1 ONE-PASS leftover — **обязательное закрытие зам.1**

Норматив **не менять**: секция «Критерии приёмки (AC / IAC) — канон v0.3.2» (стр. ~705–882) остаётся каноном гейтов.

**Переписать** все leftover, которые всё ещё описывают pre-0.3.2 (auto take-into-work / auto done / plan-approve только в one-pass). Якоря на диске:

| Якорь | Сейчас | Стало (v0.3.3 = зеркало v0.3.2) |
|---|---|---|
| Решения Саши **п.8** (~61) | фраза auto `take-into-work`+`plan-approve`+`done` | п.8 **перекрыт v0.3.2**. Фраза не снимает AC-гейты. `GATE:plan-approve` always auto и без фразы. `GATE:take-into-work` / `GATE:done` HITL never auto. Фраза сохраняется как UX-ярлык «не клей роли / не skip фаз / не плодить хвост». |
| п.9 (~62) | пошагово HITL плана; one-pass auto | **always auto** (`auto-pass: architect-plan`); `HF:plan` обязателен там, где в графе; Саша план не согласовывает |
| п.16 (~69) | багфикс auto take-into-work (т.4) | **отменено v0.3.2**. Багфикс: `GATE:diagnose-review` не HITL Саши; `GATE:take-into-work` ждёт AC |
| Scope (~88) | «1 проход» = auto HITL; done auto после preflight 0 | фраза не меняет гейты; preflight 0 **необходим, не достаточен** для `GATE:done` |
| «Что НЕ трогать» (~113) | one-pass done auto после preflight 0 | не auto-complete `GATE:done` / `GATE:take-into-work` ни в каком режиме |
| Граф LIGHT (~297, 306–308) | one-pass → авто take-into-work/done | гейты всегда создаются; снятие: take-into-work/done = Саша; plan-approve = always auto. Строка «меняется только HITL vs auto-complete в 1 проход» — **удалить** |
| **«### Режим «делай в 1 проход»» (~312–326)** | auto take-into-work+plan-approve; done auto после preflight | **полная перепись**, не абзац-уточнение. См. целевой текст ниже |
| Таблица фаз `GATE:*` (~401, 405, 411) | «1 проход»: авто take-into-work/plan-approve/done | take-into-work: HITL never auto, payload=AC; plan-approve: always auto; done: HITL never auto, payload=отчёт AC, preflight 0 недостаточен |
| tz-workflow канбан-шаг п.5 (~448–449) | one-pass авто take-into-work | после `TZ:finalize` — список AC в чат; гейт HITL never auto |
| hermes-feature канбан-шаг (~456–462) | вход по one-pass auto; plan-approve one-pass auto; done auto | вход только если take-into-work снят **Сашей**; plan-approve always auto; done never auto + отчёт AC |
| «Гейты HITL» таблица (~528–544) + «### Триггер» (~542–544) | фраза ставит auto трёх гейтов | фраза **не** ставит auto take-into-work/done. Триггер-enum `one_pass` можно оставить как no-op + запрет склейки |
| «Багфикс — авто take-into-work» (~536) | т.4 | **удалить норматив**; одна строка «отменено v0.3.2, см. AC/IAC» |
| «Что менять в файлах» п.16 (~702) | вшить т.4 | заменить: вшить отмену т.4 + never auto take-into-work |
| Критерии успеха (~891–893, 902) | фраза auto трёх гейтов; т.4 | выровнять под v0.3.2 таблицу гейтов |
| `metadata.one_pass` (~949) | true=auto take-into-work+plan-approve+done | `true` = не клей роли / не плодить хвост; **не** auto AC-гейтов. plan-approve auto независимо от флага |
| Контракт «Отдаёт» (~955) | auto-pass plan-approve и done-после-preflight в one-pass | plan-approve always auto; done never auto |

**Целевой текст раздела «Режим «делай в 1 проход»» (заменить целиком ~312–326):**

```
### Режим «делай в 1 проход»

Триггер-фраза Саши: «делай в 1 проход».

После канона v0.3.2 фраза **не меняет снятие гейтов** (вестигиальна / no-op для HITL):
- GATE:take-into-work — HITL never auto (payload = AC-список), в том числе после этой фразы;
- GATE:plan-approve — always auto (auto-pass: architect-plan), и без фразы;
- GATE:done — HITL never auto (payload = отчёт AC); preflight exit 0 необходим, не достаточен.

Что фраза по-прежнему означает (и только это):
1. Не skip фаз и не склейка PREFIX:фаза / ролей в один agent -p (GLOSSARY §5.2).
2. Корневой one-pass не плодит полный хвост карточек (правило C hermes-feature).
3. Если корень сам ведёт цикл: серия agent -p по ролям (grok → composer), не один промпт «ТЗ+код+тесты».
4. GATE:diagnose-review / GATE:go / GATE:block-accept фраза не обходит (инвариант 7). DX не one-pass.

Условия входа в «не плодить хвост»: мастер-ТЗ на диске; открытых вопросов нет; не обход diagnose-review.
```

**Н3** в этом же разделе (не отдельный «не менять auto трёх гейтов» — это и было дырой ревизора):

Корневой one-pass = не создавать полный хвост. Это **не** «один `agent -p` на ТЗ+код+тесты». Склейка ролей запрещена.

#### B1.2 Таблица «Фазы ↔ скиллы» (~392–433)

Сноску `--model` / САНКТ **не переписывать**, не переименовывать САНКТ `IAC-01..10`.

1. Строка `ORCH:shared-state` (~410): `composer-2.5 (механика)` → `deepseek-v4-flash-0731 (Hermes, без Cursor)`.

2. После `IDEA:analyze` вставить:

```
| `RS:collect` | hermes-feature Блок 8 / RS | `cursor-grok-4.6-high` | Сбор (read-only) | факты в comment / research-файл |
| `RS:analyze` | hermes-feature Блок 8 / RS | `cursor-grok-4.6-high` | Анализ + AC RESEARCH | отчёт; HITL = GATE:done |
| `REV:report` | ревизор (RS) | `claude-sonnet-5-medium` | Слабые места отчёта | comment |
| `MIG:plan` | hermes-feature MIG-TAIL | `cursor-grok-4.6-high` | План миграции | план на диске |
| `MIG:block-k` | MIG-TAIL | `composer-2.5` | Блок k | metadata блока |
| `MIG:exec` | DECOMM-TAIL EXEC | `composer-2.5` | Исполнение миграции | changed_files |
| `DEC:inventory` | DEC-PRE | `cursor-grok-4.6-high` | Инвентарь удаления | список путей |
| `DEC:exec` | DECOMM-TAIL EXEC | `composer-2.5` | Удаление после GATE:go | changed_files |
| `SK:preflight` | SK-PRE | — (без Cursor, `wc -c`) | >15k → compress | metadata `bytes` |
| `GATE:go` / `GATE:block-accept` | HITL Саша | — | never auto (запрос решения, не AC) | фраза / дашборд |
```

3. Skills-список: `RS:*` / `REV:report` / `MIG:*` / `DEC:*` = `hermes-feature`,`cursor-cli`; `SK:preflight` = только `hermes-feature`.

4. **Н4** в «Границы»: `epic-development` и `aggregate-tz-opus-workflow` — не этот пайплайн (Cursor через zip/пакет, не `agent -p` канбана). Не грузить на DEV (GLOSSARY §4). **Не менять эти скиллы в этом цикле.**

5. Changelog:

```
## v0.3.3 — leftover one-pass + покрытие моделей фаз (2026-09-25)
- Вычищены leftover «1 проход» под канон v0.3.2 (take-into-work/done never auto; plan-approve always auto; фраза = no-op для гейтов).
- Таблица фаз: RS/MIG/DEC/SK/GATE:go/block-accept; ORCH = deepseek без Cursor.
- epic/aggregate помечены «не этот пайплайн».
- Запрет kanban_create --model без изменений. САНКТ IAC-01..10 без переименования.
```

**Не делать:** откатывать HITL v0.3.2; трогать САНКТ-список; менять сноску `kanban --model`; править `pipeline_gate_done_preflight.py` (там `GATE_ONE_PASS_OK` ещё содержит take-into-work — **вне скоупа**; риск D-preflight).

---

### B2. `TZ/GLOSSARY.md` (0.2.5 → **0.2.7** через секцию **0.2.6**)

**YAML:** `version: 0.2.7`; `date: 2026-09-25`.

**Секция 0.2.6** (после текущего конца / перед 0.2.7) — содержимое «Что класть в 0.2.6» выше. Конкретные диффы:

| Место | Было | Стало |
|---|---|---|
| §5 `GATE:` (~100–102) | One-pass = auto take-into-work, plan-approve, done | auto **только** `GATE:plan-approve`; take-into-work/done never auto |
| инвариант 3 (~191) | auto трёх гейтов; never auto diagnose/go/block-accept | auto только plan-approve; never auto: take-into-work, done, diagnose-review (как HITL Саши), go, block-accept. diagnose-review карточка остаётся, HITL Саши нет |
| §2 CHANGE-LIGHT (~51) | `HF:plan` (вшит) → `PLAN-IMPL-TAIL-LIGHT` | убрать «HF:plan вшит»; хвост = `PLAN-IMPL-TAIL-LIGHT`; IAC 1–3 строки в ТЗ/`_fix_plan` |
| §3 после таблицы ролей | нет слоя AC/IAC | абзац: AC-### / IAC-## — артефакты, не фазы; HITL две точки |
| BUGFIX-LIGHT-GRAPH comment (~150) | `GATE:diagnose-review` HITL never auto | карточка обязательна; HITL Саши нет (выровнять с v0.3.2) |

**Секция 0.2.7** — после таблицы §3:

```
Канон «PREFIX:фаза → роль → модель/механизм» — таблица «Фазы ↔ скиллы» в DevKanbanPipeline_TZ.md (v0.3.3).
Строки «без Cursor» (stabilize, compress, ORCH, SK:preflight, BRF-диалог, GATE HITL Саши) — не agent -p.
BRF: варианты постановки — только архитектор (agent -p cursor-grok-4.6-high) до ответа Саше; фактология BRF — оркестратор в TG.
```

§4: одна фраза «epic-development / aggregate-tz-opus-workflow на DEV не грузить; не этот пайплайн». Полную таблицу фаз **не** копировать.

---

### B3. `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md` (2.4.1 → **2.4.2**)

Таблица «Шаг | Роль | Модель» (~47–53) — после BRF:

`| TZ:stabilize | воркер (диск) | — (без agent -p) | path, version, mtime в metadata |`

BRF-строка:

`| BRF | оркестратор | deepseek (TG, без Cursor) | диалог; варианты постановки — сначала agent -p cursor-grok-4.6-high, затем ответ Саше |`

Таблица канбан-шага (~262+): `| stabilize | TZ:stabilize | — (без agent -p; stat/YAML) |`

Канбан-шаг после `TZ:finalize`: **не** «one-pass авто take-into-work». После finalize — выдать AC-список в чат; `GATE:take-into-work` HITL never auto (зам.1 зеркало).

Запрет `kanban_create --model` не ослаблять.

---

### B4. `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md` (2.7.1 → **2.7.2**)

| Место | Правка |
|---|---|
| **:40** (зам.4) | Удалить хвост «После **одобренного** `GATE:diagnose-review` + ТЗ-решения → `GATE:take-into-work` авто (one-pass), фраза не требуется (требование 4)». Заменить: после `TZ:finalize` (багфикс-ТЗ) `GATE:take-into-work` HITL never auto, payload=AC; `GATE:diagnose-review` не ждёт фразу Саши (не HITL Саши). Требование 4 отменено (DKP v0.3.2, HITL вариант 1). |
| **~123** тот же т.4 | Та же замена. Не оставлять вторую копию. |
| Вход HF (~57) | Убрать «или `auto-pass: one-pass mode`» как снятие take-into-work. Вход только если гейт снял Саша (фраза/дашборд). |
| GATE:plan-approve (~164–167) | Убрать развилку «пошаговый HITL / one-pass auto». Always auto (`auto-pass: architect-plan`). `HF:plan` обязателен до гейта. |
| GATE:done (~175–190) | Убрать «one-pass: auto-complete после preflight 0». Never auto; preflight 0 необходим; payload = отчёт AC; complete только после Саши. |
| «Режим «делай в 1 проход»» (~192–202) | Выровнять с B1.1: фраза no-op для гейтов; не клей роли; DX не обходится. |
| ~204–218 «One-pass не плодит хвост» | После «Работа уже в корневом `agent -p`»: работа в корне = **серия** `agent -p` по ролям (grok затем composer), не один промпт ТЗ+код+тесты. Хвост карточек не плодить. Строка «один воркер на корне закрывает ТЗ-правку, код, тесты» — уточнить: один воркер-корень, **несколько** вызовов `agent -p`. |
| Блок 6А ~384–390 | «Не PREFIX:фаза. Не обязательный `agent -p`. Канон покрытия тестами пайплайна — `HF:test` (`composer-2.5`). 6А — только hotfix без плана 1А.» |
| **Блок 6Б ~394–404 (зам.5)** | Перед таблицей вставить блок ниже. Колонку «Модель» не читать как `cronjob(model=cursor-grok-…)`. |
| Блок 6В шаг 1 ~432 | «Карточка-воркер (оркестратор/self) делает root cause» → «Воркер карточки вызывает `agent -p --model cursor-grok-4.6-high` (архитектор). Оркестратор **не** пишет `_fix_plan` сам. `kanban_create` **без** `--model`.» |
| Блок 8 ~464–472 | collect/analyze = grok `agent -p`; `REV:report` = sonnet; постановка = карточки `RS:*`, не свободный чат без графа RESEARCH. |

**Текст сноски 6Б (зам.5) — вставить целиком перед таблицей ~396:**

```
Таблица 6Б — не канон PREFIX:фаза и не канон живого графа DEV/<slug>.
На живом графе: только agent -p по таблице DKP (инвариант 8). cronjob/delegate_task
на диспатчащихся детях запрещены.

Namespace (прецедент t_2c8ee3b2): cronjob(repeat=1) и delegate_task — воздух
Hermes-воркера (hermes chat -m / toolsets file|terminal|web), НЕ нативный
Cursor CLI subagent и НЕ kanban_create. Передавать cursor-grok-* /
composer-2.5 / claude-sonnet-* в cronjob(model=) / delegate_task(model=)
запрещено (HTTP 400 tutu, 0 tool-calls, protocol_violation).
Если 6Б всё же вне пайплайна: воздух = NULL или tutu vendor/model;
роль Cursor — только внутри уже живого воркера через agent -p --model.
Колонка «Модель» ниже — slug внутреннего agent -p, не аргумент cronjob/delegate.
```

Не превращать 6А/6Б в обязательный `agent -p` «на всякий случай».

---

### B5. `~/.hermes/skills/devops/kanban-dev-cases/SKILL.md`

Строка 14:

**Было:** `| Исполнитель/Компрессор/Координатор | composer-2.5 | механика |`

**Стало:**

```
| Исполнитель / Координатор | `composer-2.5` | Cursor, механика |
| Компрессор | `deepseek-v4-flash-0731` | оркестратор Hermes, **без** `agent -p` |
```

YAML `version` не заводить.

---

### B6. `~/.hermes/skills/devops/kanban-dev-cases/references/case-chains.md`

Строка 6:

**Было:** `Исп/Комп/Коорд=composer-2.5`

**Стало:** `Исп/Коорд=composer-2.5; Комп=deepseek-v4-flash-0731 без Cursor`

---

### B7. `~/hermes-workspace/skills/devops/kanban-dev-pipeline-orchestration/SKILL.md` (1.1.1 → **1.1.2**)

Питфолл 3b ~94–96:

**Было:** `(компрессор/исполнитель = composer-2.5, архитектор = cursor-grok-4.6-high,`

**Стало:** `(компрессор = deepseek-v4-flash-0731 без Cursor; исполнитель = composer-2.5; архитектор = cursor-grok-4.6-high,`

Питфолл 11 (`--model`) **не трогать**.

---

### B8. `TZ/MAIN_TZ_INVENTORY.md` (зам.3)

YAML `updated:`:

`2026-09-25 (GLOSSARY v0.2.7 [0.2.6 AC/IAC HITL + 0.2.7 покрытие фаза→механизм] + DevKanbanPipeline v0.3.3; инвентарь подтянул пропущенный v0.3.2 AC/IAC; ядро не трогали)`

**Строка GLOSSARY (~56):** версия **0.2.7**; в комментарии явно два бампа: *v0.2.6 — слой AC/IAC, HITL две точки, one-pass auto только plan-approve, diagnose-review не HITL Саши, фикс CHANGE-LIGHT «HF:plan вшит»; v0.2.7 — указатель на таблицу DKP v0.3.3, строки без Cursor, BRF-гибрид*.

**Строка DevKanbanPipeline (~66):** сейчас **0.3.1** при файле **0.3.2**. В одной ячейке, **не** прыжок мимо 0.3.2:

- Версия колонки: **0.3.3**
- Комментарий **сначала v0.3.2, затем v0.3.3**:
  - **v0.3.2 (25.09, уже на диске master):** канон AC/IAC, HITL вариант 1, т.4 отменено, `GATE:done` never auto, тишина notify, `GATE:plan-approve` always auto.
  - **v0.3.3 (этот пакет):** leftover one-pass вычищен под 0.3.2; таблица RS/MIG/DEC/SK; ORCH=deepseek без Cursor; epic/aggregate «не этот пайплайн».

Не оставлять инвентарь на 0.3.1 и не писать только 0.3.3.

---

### B9. `TZ/DevKanbanPipeline/_fix_plan_20260925_cursor-model-coverage.md`

Исполнитель кладёт **этот** финальный план в начале `HF:impl`. Сейчас не создавать.

### Явно не править

`~/hermes-agent/**`, `~/.hermes/config.yaml`, gateway, `failure_limit`, `kanban_db.py`, `pipeline_gate_done_preflight.py` + его тест (только pytest), `cursor-cli`, `kanban-worker`, `epic-development`, `aggregate-tz-opus-workflow`, ProcessImprovement appendix, `tz-compressor-prompt.md`.

---

# C. ТЕСТ + ПРОЦЕСС CHANGE

Прогон — `HF:test` (composer). Живой RESEARCH `agent -p` не обязателен.

**Граф этого пакета (зам.6) — не LIGHT:**

```
TZ:stabilize → TZ:compress → TZ:patch → REV:tz → TZ:finalize
→ GATE:take-into-work          # HITL Саша, never auto, payload=AC-001…012
→ HF:plan → REV:plan → GATE:plan-approve   # plan-approve always auto
→ HF:backup → HF:impl → HF:test → HF:docs-handoff
→ ORCH:shared-state            # Сирень deepseek, без Cursor
→ GATE:done                    # HITL Саша, never auto, отчёт AC
```

Skip `REV:tz` / stabilize / compress **запрещён**. `flag-waived: Sasha` на этот пакет **не** ставится.

### C1. rg-якоря

```bash
# Н1/Н2
rg -n 'Исполнитель/Компрессор/Координатор.*composer-2.5|компрессор/исполнитель = composer-2.5|Исп/Комп/Коорд.=composer-2.5' \
  ~/.hermes/skills/devops/kanban-dev-cases/SKILL.md \
  ~/.hermes/skills/devops/kanban-dev-cases/references/case-chains.md \
  ~/hermes-workspace/skills/devops/kanban-dev-pipeline-orchestration/SKILL.md
# 0 hits

rg -n 'Компрессор.*deepseek-v4-flash-0731' ~/.hermes/skills/devops/kanban-dev-cases/SKILL.md
rg -n 'компрессор = deepseek-v4-flash-0731 без Cursor' \
  ~/hermes-workspace/skills/devops/kanban-dev-pipeline-orchestration/SKILL.md

# Д1
rg -n '`RS:collect`|`RS:analyze`|`REV:report`|`MIG:plan`|`MIG:block-k`|`MIG:exec`|`DEC:inventory`|`DEC:exec`|`SK:preflight`' \
  ~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md

# Д5 / Д7
rg -n 'TZ:stabilize' ~/hermes-workspace/skills/devops/tz-workflow/SKILL.md | head
rg -n 'ORCH:shared-state' ~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md
# в строке таблицы: deepseek, НЕ composer-2.5

# Д8
rg -n 'оркестратор/self' ~/hermes-workspace/skills/devops/hermes-feature/SKILL.md
# 0 hits

# зам.4 — требование 4 / авто take-into-work в классификаторе
rg -n 'требование 4' ~/hermes-workspace/skills/devops/hermes-feature/SKILL.md
# 0 hits в смысле «авто take-into-work»; допустимо «требование 4 отменено»

# зам.1 — leftover «1 проход» auto take-into-work+done как норматив
rg -n 'auto-complete `GATE:take-into-work`, `GATE:plan-approve` и `GATE:done`' \
  ~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md
# 0 hits (кроме исторических changelog v0.2.x, которые не норматив)

rg -n 'вестигиальн|не меняет снятие гейтов|always auto' \
  ~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md

# зам.5 — 6Б namespace
rg -n 't_2c8ee3b2' ~/hermes-workspace/skills/devops/hermes-feature/SKILL.md
rg -n 'Блок 6Б' -A 25 ~/hermes-workspace/skills/devops/hermes-feature/SKILL.md | rg -n 'запрещено|воздух Hermes|не нативный Cursor'

# Н3
rg -n 'ТЗ-правку, код, тесты' ~/hermes-workspace/skills/devops/hermes-feature/SKILL.md
# строка уточнена (серия вызовов)

# Н4
rg -n 'не этот пайплайн' ~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md
git -C ~/hermes-workspace diff --stat -- skills/devops/epic-development skills/devops/aggregate-tz-opus-workflow
# пусто

# GLOSSARY разведение
rg -n '^version: 0.2.7' ~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md
rg -n '## .*0\.2\.6' ~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md
rg -n 'HF:plan` \(вшит\)' ~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md
# 0 hits

# B8 инвентарь через 0.3.2
rg -n 'DevKanbanPipeline' ~/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md
# есть и v0.3.2 AC/IAC, и v0.3.3; нет «только 0.3.3» без 0.3.2

# запрет --model жив
rg -n 'kanban_create --model|НЕ kanban --model' \
  ~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md \
  ~/hermes-workspace/skills/devops/tz-workflow/SKILL.md \
  ~/hermes-workspace/skills/devops/hermes-feature/SKILL.md
```

### C2. pytest 20/20

```bash
python3 -m pytest ~/WorkVault/Registries/test_pipeline_gate_done_preflight.py -q
# collect 20, passed 20
```

Скрипт не менять. `PHASE_ROLE` (stabilize=координатор, compress=компрессор, ORCH=оркестратор) не трогать. `GATE_ONE_PASS_OK` пока содержит take-into-work — **не чинить в этом пакете** (риск D-preflight).

### C3. git hermes-agent чисто

```bash
git -C ~/hermes-agent status --porcelain
git -C ~/hermes-agent diff --stat
# оба пусто
```

### C4. restore-all-skills

```bash
bash ~/.hermes/scripts/restore-all-skills.sh
test -d ~/.hermes/skills/devops/kanban-dev-cases && test -d ~/.hermes/skills/devops/cursor-cli
readlink -f ~/.hermes/skills/devops/tz-workflow    # → hermes-workspace
readlink -f ~/.hermes/skills/devops/hermes-feature
# Gateway НЕ рестартовать. config.yaml не бэкапить.
```

Если restore стёр `kanban-dev-cases`/`cursor-cli` — стоп, не complete.

### C5. IAC-COV (не путать с САНКТ IAC-01..10)

| IAC | from→to | path | verify | covers |
|---|---|---|---|---|
| IAC-COV-01 | TZ:patch→TZ:finalize | DKP таблица ~394+ | rg Д1-фазы; ORCH без composer | AC-001, AC-003 |
| IAC-COV-02 | TZ:patch→TZ:finalize | GLOSSARY.md | version **0.2.7**; секция **0.2.6** AC/IAC; нет «HF:plan вшит»; инвариант 3 = auto только plan-approve | AC-001, AC-005, AC-011 |
| IAC-COV-03 | HF:impl | tz-workflow | rg `TZ:stabilize` + `без agent -p`; нет «one-pass авто take-into-work» как норматив | AC-001, Д5 |
| IAC-COV-04 | HF:impl | hermes-feature 6А/6Б/6В/8/one-pass/:40 | 0 hits «требование 4» как авто; 6Б содержит t_2c8ee3b2 + запрет model=; 0 hits оркестратор/self | AC-004, AC-005, AC-012, Д2–Д4, Д8, Н3 |
| IAC-COV-05 | HF:impl | kanban-dev-cases + case-chains + orchestration 3b | 0 hits «Комп=composer» | AC-002, Н1, Н2 |
| IAC-COV-06 | HF:test | test_pipeline_gate_done_preflight.py | pytest **20/20** | AC-009 |
| IAC-COV-07 | HF:test | ~/hermes-agent | git status empty | AC-007 |
| IAC-COV-08 | HF:docs-handoff | MAIN_TZ | DKP комментарий содержит **v0.3.2 и v0.3.3**; GLOSSARY **0.2.7** | AC-001, AC-011 |
| IAC-COV-09 | HF:impl | epic/aggregate | git diff empty + пометка в DKP | AC-006 |
| IAC-COV-10 | HF:impl | сноска `--model` | rg запрет на месте | AC-008 |
| IAC-COV-11 | TZ:patch→finalize | DKP «Режим 1 проход» | rg «не меняет снятие гейтов»; 0 hits нормативного auto take-into-work+done вне changelog | AC-005 |
| IAC-COV-12 | HF:impl | hermes-feature:394–404 | сноска namespace Hermes air ≠ Cursor CLI | AC-012 |

### Итоговые AC (в секцию DKP при `TZ:finalize`)

| AC | current | target |
|---|---|---|
| AC-001 | RS/MIG/DEC/SK нет в таблице DKP | каждая фаза §5 имеет строку: `agent -p` **или** явно без Cursor |
| AC-002 | компрессор=composer в трёх зеркалах | компрессор = deepseek без Cursor |
| AC-003 | ORCH=composer в DKP | ORCH = Сирень deepseek без Cursor |
| AC-004 | 6В = оркестратор/self | диагноз = grok `agent -p`; create без `--model` |
| AC-005 | leftover one-pass = auto трёх гейтов | фраза no-op для гейтов; leftover переписан; не клей ролей; plan-approve always auto; take-into-work/done never auto |
| AC-006 | epic/aggregate не помечены | не изменены; пометка «не этот пайплайн» |
| AC-007 | — | hermes-agent без диффа; config/gateway/failure_limit не менялись |
| AC-008 | — | запрет `kanban_create --model` со slug Cursor сохранён |
| AC-009 | — | pytest preflight 20/20 |
| AC-010 | — | BRF: варианты постановки = grok `agent -p` до ответа Саше |
| AC-011 | инвентарь DKP=0.3.1; GLOSSARY долг 0.2.6 | инвентарь содержит 0.3.2 **и** 0.3.3; GLOSSARY 0.2.6+0.2.7 в одном файле 0.2.7 |
| AC-012 | 6Б передаёт cursor-slug в cronjob/delegate без сноски | сноска: тот же namespace, что `t_2c8ee3b2`; slug запрещён как воздух; на живом графе 6Б запрещён |

HITL после пакета: список AC в чате на `GATE:take-into-work`; отчёт AC на `GATE:done`.

---

# D. РИСКИ (с учётом 6 замечаний)

| Риск | Митигация |
|---|---|
| Зам.1: исполнитель «уточнит абзац» вместо переписи раздела ~312 | B1.1 — таблица якорей + целевой текст целиком; IAC-COV-11; запрет «не менять auto трёх гейтов» |
| Зам.2: снова один номер 0.2.6 на два changeset | frontmatter 0.2.7 + две секции; IAC-COV-02 |
| Зам.3: инвентарь прыгнет на 0.3.3 без 0.3.2 | B8 шаблон комментария; IAC-COV-08 |
| Зам.4: починят :40, оставят ~123 | B4 оба якоря; rg «требование 4» |
| Зам.5: пометят «вне scope, безопасно» без проверки | в плане зафиксирован факт: 6Б = Hermes air. Сноска обязательна. Не утверждать «нативный Cursor CLI» |
| Зам.6: impl пойдёт как LIGHT без REV:tz/stabilize/compress | граф CHANGE в C/E; preflight `--case CHANGE` без `--flag-rev`; оркестратор не complete без `REV:tz` done |
| Исполнитель заменит 6А/6Б на agent -p везде | запрет в E; 6А остаётся исключением; 6Б остаётся off-graph + namespace-сноска |
| Исполнитель «починит» `GATE_ONE_PASS_OK` в preflight | вне скоупа; риск: скрипт ещё считает auto take-into-work легитимным. Follow-up, не этот пакет |
| restore сотрёт kanban-dev-cases | C4 `test -d`; не копировать скилл в workspace без ТЗ |
| САНКТ IAC-01..10 vs IAC-COV / пайплайнные IAC | якоря `IAC-COV-##`; САНКТ не переименовывать |
| Dual-write GLOSSARY+DKP | 0.2.6 только HITL/AC; полные строки фаз — только DKP 0.3.3 |
| Appendix ProcessImprovement с composer-компрессором | не трогать (история). Канон = GLOSSARY+DKP+три скилла |
| cursor-cli:343 координатор=gemini | вне скоупа; хвост в comment `HF:docs-handoff` |

---

# E. ТЗ ИСПОЛНИТЕЛЮ (`composer-2.5`)

**Роль:** механика текста по §A/§B. Модели не выдумывать. **Код не писать.**

**Кейс:** CHANGE (не LIGHT, не BUGFIX-LIGHT). Обязательны:

1. `TZ:stabilize` (диск, без `agent -p`)
2. `TZ:compress` (deepseek, без Cursor)
3. `TZ:patch` (уже содержание этого плана)
4. **`REV:tz`** (`claude-sonnet-5-medium`) — **ON**. `flag-waived: Sasha` **не** ставить.
5. `TZ:finalize` + инвентарь под `LOCK_EX`
6. `GATE:take-into-work` — ждать Сашу (AC-список). Не auto.
7. `HF:plan` (этот документ) → `REV:plan` → `GATE:plan-approve` always auto
8. `HF:backup` → `HF:impl` (правки B1–B9) → `HF:test` (C) → `HF:docs-handoff`
9. `ORCH:shared-state` — Сирень, deepseek, без Cursor
10. `GATE:done` — ждать Сашу (отчёт AC). Не auto.

**Порядок `HF:impl`:** (1) скопировать план в `_fix_plan_20260925_cursor-model-coverage.md` (2) B1 (сначала B1.1 leftover, потом таблица) → B2 (0.2.6 затем 0.2.7 в одном write) → B3 → B4 (**обязательно :40, ~123, 6Б-сноска**) → B5–B7 → B8 (**0.3.2 и 0.3.3**) → B9 уже создан (3) rg+pytest+git (4) bump version скиллов (5) `restore-all-skills.sh` (6) проверка profile-only скиллов.

**Файлы (ровно эти):**

1. `~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md`
2. `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`
3. `~/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md`
4. `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md`
5. `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md`
6. `~/.hermes/skills/devops/kanban-dev-cases/SKILL.md`
7. `~/.hermes/skills/devops/kanban-dev-cases/references/case-chains.md`
8. `~/hermes-workspace/skills/devops/kanban-dev-pipeline-orchestration/SKILL.md`
9. `TZ/DevKanbanPipeline/_fix_plan_20260925_cursor-model-coverage.md` (create)

**Нельзя:**

- ядро, config, gateway, `failure_limit`, `kanban_db.py`, preflight-скрипт (только pytest)
- `cursor-cli`, `kanban-worker`, epic, aggregate
- ослаблять запрет `kanban_create --model`
- возвращать auto `GATE:take-into-work` / `GATE:done` (в т.ч. «ради one-pass»)
- ставить `composer-2.5` на ORCH или компрессор
- один абзац «корневой one-pass = один agent на всё»
- писать GLOSSARY только 0.2.6 **или** только 0.2.7 без секции-долга 0.2.6
- прыгать инвентарём на 0.3.3 без записи v0.3.2
- оставить `hermes-feature` :40 / ~123 с «требование 4 авто»
- пометить 6Б «нативный Cursor CLI» или «вне scope, безопасно» — это ложь относительно факта namespace
- skip `REV:tz` / `TZ:stabilize` / `TZ:compress`
- restore без проверки `kanban-dev-cases`/`cursor-cli`
- рестарт Gateway; бэкап конфигов не нужен

**Done:**

- Версии: DKP **0.3.3**, GLOSSARY **0.2.7** (секции 0.2.6+0.2.7), tz-workflow **2.4.2**, hermes-feature **2.7.2**, orchestration **1.1.2**, инвентарь синхронен (**0.3.2 и 0.3.3**)
- IAC-COV-01..12 зелёные (rg + pytest 20/20 + git hermes-agent empty + restore)
- AC-001…012 по чеклисту C, не «на глаз»
- `kanban_complete.metadata`: `changed_files`, `registry_touches=[]`, `iac_passed=IAC-COV-01..12`

**После impl:** `HF:docs-handoff` — список для ORCH (bump версий скиллов в манифесте, если ключи есть; иначе no-op). `ORCH:shared-state` делает Сирень (deepseek, без Cursor).