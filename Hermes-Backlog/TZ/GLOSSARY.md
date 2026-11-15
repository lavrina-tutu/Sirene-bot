---
type: glossary
title: Глоссарий пайплайна разработки Hermes
version: 0.3.1
date: 2026-11-15
status: active (D1–D9/Q1/Q2; DevWorkflow на штатном канбане; G1–G6; firewall, 10 кейсов, фазы и S/O/C сохранены; runtime NOT_RUN)
revision: '2026-11-15 — адресная синхронизация D6/B3 по REV: основной provider worker75/78; внешний invoke block/manual resume; повторная REV требуется, B3 proof NOT_RUN / ENV-03 NOT_PROVEN'
owner: ProcessImprovement
canonical: ~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md
source: appendix_chains-and-skills-audit_20260907.md
---

# GLOSSARY — пайплайн разработки

Единый язык кейсов, ролей, скиллов, фаз и артефактов. Не процедура и не каталог графов.
При конфликте с чатом / скиллом / appendix — править этот файл, не плодить синонимы.

> **Активный процесс:** DevWorkflow — предметный процесс на штатном канбане Hermes; devops/dev-workflow — единственный владелец процедуры, recipe задаёт план, исполнение/runs/events принадлежат канбану, master — SoT требований. Роль = assignee-профиль; dispatcher запускает worker, invoke_role — adapter внутри него. EcoConfig хранит пути/роли→профили/рецепты, штатный Hermes config — физически читаемые модели/dispatcher; карточка refs/version, не дубль значений. Имена 10 кейсов, фаз и S/O/C сохраняются. Нормы: [master](DevWorkflow/DevWorkflow_TZ.md), [решения](../dev/pochinka-dev-workflow-20261112/out/DECISIONS-KANBAN-TZ.md), [REV-a-pack-v2](../dev/pochinka-dev-workflow-20261112/out/REV-a-pack-v2.md).

## 0. Как читать

1. Фаза канбана = `PREFIX:kebab-case`. Без двоеточия PREFIX — не фаза.
2. Первое упоминание Саше/в appendix: акроним + русская расшифровка; дальше — канон.
3. Кейс ≠ роль ≠ скилл ≠ документ ≠ фаза ≠ граф. См. §0.1 и §1.
4. Предметная фаза называется по §5; root/supporting и author/review различаются по §0.1. Синонимы HF:fix/TZ:architect как бриф запрещены.
5. Инструменты USERTOOLS — имена из `MAIN_TZ_INVENTORY.md`, не из этого файла.

## 0.1 Определения (граф / карточка / фаза) — «§0.1 Определения»

| Термин | Определение |
|---|---|
| **Граф** | Экземпляр версии recipe на штатной доске: root запроса/итога, работы и зависимости; строит Сирень по выбранному со Сашей кейсу. Root не предшественник своих фаз; partial graph заблокирован до структурной проверки. |
| **Карточка** | Штатная task с identity board+task_id: root, phase work или supporting diagnostic. Author/review могут быть одной карточкой с отдельными каноническими фазами/runs и независимым reviewer-профилем. HF:impl/HF:test раздельны; _state.json не владелец карточек. |
| **Фаза** | Имя шага графа (`PREFIX:kebab-case`). Указывает действие: `TZ:patch` = написать правку ТЗ, `HF:plan` = план разработки и тестирования (IAC), `HF:impl` = написать код, `HF:test` = прогнать тесты плана, `REV:tz` = проверить ТЗ, `GATE:done` = финальная приёмка. |

Кейс ≠ граф: кейс — **тип работы** (§2, закрытый список из 10); граф — конкретная развёртка кейса на доске. Архитектор не выбирает ни кейс, ни состав графа.

## 1. Слои токена (коллизии)

| Слой | Как писать | Примеры |
|---|---|---|
| Кейс | полное имя; коротко только в id | DEV, CHANGE, CHANGE-LIGHT, BUGFIX, BUGFIX-LIGHT, RESEARCH, MIGRATION, DECOMM, SKILL-DEV, SKILL-CHANGE |
| **Блок** | `ALL-CAPS` / `PREFIX-TAIL` | `PLAN-IMPL-TAIL`, `TZ-WRITE` |
| Роль | по-русски | оркестратор, архитектор, ревизор, исполнитель |
| Скилл | backtick-имя | `dev-workflow` и предметные references |
| Документ | «ТЗ», `master-ТЗ` | не «TZ» |
| Фаза | `PREFIX:фаза` | `TZ:finalize`, `HF:impl`, `ORCH:shared-state` |

Блок разворачивается в канонические фазы §5. Карточка бывает root/supporting work либо работой, включая author/review пару с отдельными фазами/runs и независимым reviewer. Имя блока не заменяет фазу; HF:impl/HF:test раздельны. D1/D2/D5, FINAL §2.1–2.2/4.2; P01/P04/P33, IAC-03/04.

Особые коллизии:
- **TZ** — только префикс фазы. Владелец процесса = `dev-workflow`; хранение ТЗ — предметные references. Документ = «ТЗ».
- **HF** — только префикс фазы. Владелец процесса = `dev-workflow`; implementation/QA — предметные references.
- **ORCH** — не писать голое. Роль = оркестратор (Сирень). Фаза = `ORCH:shared-state`.
- **BRF** — и префикс фаз (BRF:…), и блок брифа (как TZ=префикс фазы).
- **DEV / CHG / BUG / RS / MIG / DEC / SK** — только кейсы, не роли и не фазы.

## 2. Кейсы (сборка из блоков)

| Кейс | Код | Что это | Сборка (блоки) |
|---|---|---|---|
| DEV | DEV | новый инструмент/фича | `BRF(full)` → `BRIEF-CLOSE` → `TZ-WRITE(new)` → `TAKE-INTO-WORK` → `[HF-COMPRESS]` → `PLAN-IMPL-TAIL` |
| CHANGE | CHG | доработка существующего | `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(full)` → `TAKE-INTO-WORK` → `[HF-COMPRESS]` → `PLAN-IMPL-TAIL` |
| CHANGE-LIGHT | CHG-L | доработка существующего ≤3 файла кода + тест + SKILL.md, аддитивная секция ТЗ, без новых сущностей/cron/.env | `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(light)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL-LIGHT` |
| BUGFIX | BUG | баг | `DX` → `BRF(delta)` → `TZ-WRITE(patch)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL` (compress skip; REV OFF при ≤3 файла); DX обязателен и при cold-start/крон-ошибке (первый шаг — карточка BUG:diagnose, не прямой agent -p) |
| BUGFIX-LIGHT | BUG-L | лёгкий баг ≤3 файла кода+тесты, без новых сущностей/cron/.env/манифеста, вне shared-модулей; классификация LIGHT — после GATE:diagnose-review | `DX` → `TZ-WRITE(patch)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL-LIGHT` (HF:plan/GATE:plan-approve/HF:backup/ORCH/REV skip; план утверждён на diagnose-review) |
| RESEARCH | RS | анализ без кода | `BRF(scope)` → `RS` (нет TZ-WRITE/TAKE-INTO-WORK/PLAN-IMPL-TAIL/ORCH) |
| MIGRATION | MIG | миграция | `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(freeze)` → `TAKE-INTO-WORK` → `MIG-TAIL` |
| DECOMM | DEC | удаление | `BRF(confirm)` → `DEC-PRE` → `DECOMM-TAIL(exec=DEC:exec)` |
| SKILL-DEV | SK | новый скилл | как DEV {workspace=hermes-workspace/skills, REV ON, ORCH restore} |
| SKILL-CHANGE | SK | правка/удаление скилла | SK-PRE → CHANGE или DECOMM; create/change: strict >15000 байт требует compress независимо числа файлов, ≤15000 и ≤3 implementation-файлов — skip только по канону LIGHT; DECOMM любого размера — полный inventory/read без compress/fake master, delete только go «удаляй» + backup |

Развёртка блоков — в §5.1. Кейс не содержит копию `PLAN-IMPL-TAIL` — только вызов блока.

**Закрытый список: ровно эти 10 кейсов.** Новый тип работы = новая строка в этой таблице (согласование Саши), не ad-hoc граф архитектора и не «сокращённый хвост для скорости».

Семейство кейса (DEV / CHANGE / BUGFIX / RESEARCH / MIGRATION / DECOMM / SKILL-DEV / SKILL-CHANGE) выбирают **Саша и оркестратор на старте**. LIGHT (`CHANGE-LIGHT` / `BUGFIX-LIGHT`) — **сужение того же семейства** после известного объёма (для BUGFIX — после `GATE:diagnose-review`; для CHANGE — после оценки на `TZ:patch`). Сужение графа делает **оркестратор** по таблице §5.2, не архитектор. Находка архитектора «похоже на ≤3 файла» — факт в диагнозе/ТЗ, не команда skip фаз.

## 3. Роли

| Роль | Кто | Модель | Делает | Не делает |
|---|---|---|---|---|
| Оркестратор | Сирень, default профиль | refs единственного config owner/reader Б14; carrier ≠ executor | бриф в TG; **выбор кейса со Сашей на старте**; **создание графа** (`kanban_create`-батч); ведение процесса; structural-preflight после create; `ORCH:shared-state`; сигнал блокера сразу | не придумывает содержание ТЗ/плана; не пишет код; **не предлагает слаги** (`dev/<slug>/` и `entities.task_slug`); **не даёт технические варианты/решения**; не подменяет архитектора; **не даёт собственных мнений/рекомендаций/предложений по слагам, техническим развилкам, судьбе карточек, классификациям и архитектуре при работе по канону** (Саша 15.10, Б16.2 п.6, AC-056) |
| Архитектор | Assignee-профиль роли | refs единственного config owner/reader Б14; carrier ≠ executor | исполняет **поставленную** задачу: ТЗ, план разработки **и** тестирования (IAC), риски, исследование, вопросы Саше | **не** решает ход процесса; **не** строит граф; **не** выбирает кейс/LIGHT-skip; **не** разворачивает и не укорачивает фазы |
| Ревизор | Независимый reviewer-профиль | refs единственного config owner/reader Б14; carrier ≠ executor | слабые места ТЗ/плана; возврат на доработку. Исключение: лёгкие BUGFIX/SKILL-CHANGE ≤3 файла — без ревизора (08.09.2026) | не решает ход процесса; не строит граф |
| Исполнитель | Assignee-профиль роли | refs единственного config owner/reader Б14; carrier ≠ executor | код **и** прогон тестов (`HF:test`) по IAC плана архитектора, молча | не пишет ТЗ/план; не выбирает кейс; отдельной роли «тестировщик» нет |
| Компрессор | Assignee-профиль роли | refs resolver/capabilities native или Codex, Б60; carrier отдельно | Содержательная выжимка по Б60; Python — единственный publisher | — |
| Координатор | Сирень, механика | refs единственного config owner/reader Б14; carrier ≠ executor | бэкап, инвентарь, операторка | не содержание ТЗ |

Один logical invoke — одна роль; carrier+external executor считаются одним invoke Б49. Три backend: Hermes internal/Codex/Cursor; Cursor live availability отдельно от обязательного contract coverage. Exact model/effort/session/branch сохраняются в native accepted run. D6/B3 — master Б13.2/[FINAL §4.3](../dev/pochinka-dev-workflow-20261112/out/FINAL-TZ-dev-workflow-kanban.md): основной provider-путь Hermes сохраняет actual worker75 transient/cooldown и worker78 terminal_provider/sticky; внешний invoke, включая отдельный SDK native-Компрессора и Codex-Компрессор, — typed transient/terminal failure → устойчивый штатный block собственной задачи без auto-run/resend → manual resume (terminal после исправления причины). Local rc не worker outcome; ENV-03 NOT_PROVEN, B3 proof NOT_RUN, внутри attempt retry/fallback запрещены. Адресная синхронизация по REV 15.11 отражена в [отчёте D6/B3](../dev/pochinka-dev-workflow-20261112/out/D6-B3-DELTA.md); новой REV или runtime PASS эта запись не присваивает.

**Процесс vs содержание (v0.2.12, инцидент `DEV/pfs-task-slug-not-created`).** Решения о ходе процесса (какой кейс, какой граф, какие фазы есть/нет) принимают **только Саша и оркестратор, и только на старте** (LIGHT-сужение — оркестратор после объёма, см. §2). Архитектору дают полный контекст (`emit-prompt`); он отдаёт только: ТЗ, или план, или вопросы Саше. `kanban_create` кейсового графа / смена `--case` / skip обязательных фаз §5.2 из карточки архитектора = `protocol_violation`.

**Тестирование — не отдельная роль.** Архитектор на `HF:plan` пишет план разработки **и** тестирования (таблица `IAC-##` с `path` / `verify` / `depends` / `covers`). Исполнитель на `HF:impl` пишет код и на `HF:test` **сам** гоняет проверки плана, молча. Отчёт AC — на `GATE:done`. Роли «тестировщик» в пайплайне нет (решение Саши 29.09.2026).

**Слой AC/IAC (долг v0.3.2, HITL-hold снят v0.2.11):** `AC-###` в master-ТЗ пакета; `IAC-##` в `HF:plan` (`path`/`verify`/`depends`/`covers`). Это артефакты, не фазы и не скиллы. Омоним: САНКТ `IAC-01..10` ≠ пайплайнные `IAC-##`. Карточки `GATE:take-into-work` (AC-список) и `GATE:done` (отчёт AC) **остаются** узлами графа. **Показ AC ≠ ожидание:** доставка списка/отчёта в origin не держит поезд **для класса S**.

**Выполнение operator-AC ≠ показ (v0.2.12, императив 28.09).** Три класса участия Саши — тег на AC / вопрос + `block-reason` на корне или `GATE:done`, **не** новая фаза (набор §5.2 не расширять):

| Класс | Что это | Блокирует `GATE:done`? | Напоминание |
|---|---|---|---|
| **S — show-only** | Саша *видит* артефакт. Поезд идёт. | нет | нет (R5 `notify+wake` = показ) |
| **O — operator-hold** | Саша *должен сделать* действие, без которого AC пакета неверен. | **да** | **да, повторно** (сторож) |
| **C — crisis** | уже канон v0.2.11 / DKP v0.4.0 | поезд стоит на корне | R5 terminal `blocked` |

Default AC = класс S (поезд не ждёт). Класс O — **только** явная строка архитектора в master-ТЗ пакета: `depends: operator:<verb>`. Без строки — не hold. Архитектор **обязан** поставить тег, если AC нельзя закрыть кодом/тестом без глагола Саши. `REV:tz` проверяет покрытие: operator-AC без тега (ложный auto-done) и тег на train-completable AC (ложный hold).

Закрытый словарь operator-глаголов (не расширять без `TZ:patch` DevWorkflow): `поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n` · `rollback-to-kanban`. Сторож эти глаголы **не** выполняет (не рестартует gateway, не пишет `jobs.json` кроме своего job). Имя rollback-to-kanban означает откат версии integration при сохранённой доске/истории, не legacy dispatcher.

Снятие hold: оркестратор после **факта** действия пишет на `GATE:done` или корень `operator-done: <verb>` + `evidence:` (ISO + rc/цитата). Фраза Саши без evidence факта ≠ `operator-done`. Reason блока: `review-required: operator-action: <verb>` — fail preflight, не новый never-auto гейт и не «ждать готово».

Есть **две разные** «модели». Их нельзя подставлять одну вместо другой. Формулировка канонизирует `kanban-dev-cases` (прецедент `t_2c8ee3b2`), без жаргона.

- **D1. Модель карточки (carrier)** — Hermes managed worker из штатного profile config либо обоснованный native override данной работы; external model slug нельзя подставлять в carrier.
- **D2. Модель работы внутри (executor)** — модель выбранного adapter/backend по единственному owner/resolver Б13/Б14. Codex/Cursor вызывается внутри run без board authority; профиль worker соответствует роли, не произвольный default.
- D1/D2 здесь — слои модели, не номера решений. Оба effective значения и sources различаются в evidence.

| Слой | Владелец / reader | Проверка |
|---|---|---|
| D1 carrier | Штатный config assignee/reviewer, читает Hermes | Совместимая native модель/override и фактическая загрузка |
| D2 executor | Config выбранной adapter-ветки, Б13.2/Б60.4 | Exact model/effort/session/workspace, missing до send, без чужой ветки/fallback |

Канон фаза→роль — G6 master Б6. Профиль назначает Сирень, запускает native dispatcher; механические stabilize/SK:preflight/ORCH/гейты без содержательного invoke, compressor — native/Codex по Б60. BRF-факты — Сирень, содержательные варианты — архитектор. Own terminal/review tools worker разрешены после writers и identity/gates; очередь/чужие runs/raw board mutation внешнему executor запрещены. После terminal write запрещён; выход всего Hermes turn не граница.

## 4. Скиллы пайплайна

| Скилл | За что | Не за что |
|---|---|---|
| dev-workflow | Единственный владелец предметного процесса; references: ТЗ/inventory, diagnosis, IAC/QA, backup/ORCH/DECOMM/research | Не второй dispatcher/lifecycle |
| Штатные kanban tools и sdlc-review | Native execution/review guidance; независимая предметная REV сохраняется | Не подмена master/G1–G6/firewall |

Функции tz-workflow/hermes-feature и применимых references переносятся по 41-source map A1-A3/PREP-01 до архивации прежнего owner. Отсутствующие cursor-cli/cursor-task-context не оживлять как обязательные скиллы; external launch — invoke_role adapter. Префиксы TZ/HF сохраняются. Удаление/restore требуют собственного scope; документная доставка не доказывает source/consumer/delete closure.

## 5. Фазы по префиксам

### BRF: — бриф в Telegram (не карточка)
`BRF:intake` · `BRF:questions` · `BRF:ask*` · `BRF:rewrite*` · `BRF:scope` · `BRF:delta` · `BRF:confirm`

### GATE: — гейт Саши
`GATE:brief-closed` · `GATE:take-into-work` · `GATE:plan-approve` · `GATE:diagnose-review` · `GATE:block-accept` · `GATE:go` · `GATE:done`
Штатный поезд / любой режим (в т.ч. one-pass): **auto** = `GATE:take-into-work` (`auto-pass: ac-shown` после показа AC-списка в origin), `GATE:plan-approve` (`auto-pass: architect-plan`), `GATE:done` (после preflight exit 0 и отчёта AC в origin), `GATE:diagnose-review` (после артефакта плана: `_fix_plan_*.md` или непустой body `BUG:diagnose`). **Never auto** = `GATE:go`, `GATE:block-accept`. Auto-набор **не** менять: `GATE:done` остаётся auto **после preflight 0**; preflight 0 включает снятие operator-hold (`operator-done:` + evidence) и пустой реестр `open-questions`. Карточки гейтов не skip. **Показ AC ≠ ожидание (класс S).** Выполнение operator-AC ≠ показ (класс O блокирует `GATE:done`, напоминается сторожем). Не skip фаз и не склейка в один `agent -p`. Набор фаз — §5.2. IDEA `blocked` до «разбери» / отказа — HITL бэклога, не DEV-поезд.

### TZ: — запись ТЗ (предметный справочник dev-workflow)
`TZ:stabilize` · `TZ:compress` · `TZ:patch` · `TZ:finalize`
Не фаза: `TZ:architect` как бриф (бриф уже в TG).

### HF: — реализация и проверки (предметный справочник dev-workflow)
`HF:compress` · `HF:plan` · `HF:backup` · `HF:impl` · `HF:test` · `HF:docs-handoff`
HF:compress — опциональный префикс плана вне PLAN-IMPL-TAIL; обязательный create/change compress по strict >15000 байт не снимается числом файлов. DECOMM любого размера без compress, с полным inventory/read; остальные skip — по канону кейса.

### ORCH: — только shared state
`ORCH:shared-state` — манифест, digest/render, `restore-all-skills.sh`, `.env` / `jobs.json` / `entities.json`. Workspace: `dir:/home/tkachenkoav/WorkVault/Registries`. Исполнитель сюда не пишет.

### REV: / BUG: / RS: / MIG: / DEC: / SK:
`REV:tz` · `REV:plan` · `REV:report`
`BUG:diagnose` (read-only, `_fix_plan_YYYYMMDD.md`)
`RS:collect` · `RS:analyze`
`MIG:plan` · `MIG:block-k` · `MIG:exec`
`DEC:inventory` · `DEC:exec`
SK:preflight — wc -c; только create/change strict >15000 байт → compress; DECOMM → полный inventory/read без compress/master fabrication.

## 5.1 Блоки-компоненты (переиспользуемые)
Блок разворачивается в канонические фазы §5. Карточка бывает root/supporting work либо работой, включая author/review пару с отдельными фазами/runs и независимым reviewer. Имя блока не заменяет фазу; HF:impl/HF:test раздельны. D1/D2/D5, FINAL §2.1–2.2/4.2; P01/P04/P33, IAC-03/04.
Фазы сохраняют отдельные роли/runs/packet bindings; author/review пара не склеивает обязанности. Raw agent -p в обход adapter запрещён.

```
BRF(mode) · BRIEF-CLOSE · TZ-WRITE(mode) · REV (крючок) · TAKE-INTO-WORK
HF-COMPRESS? · PLAN-IMPL-TAIL · HF-TAIL · DX · RS · MIG-TAIL
DEC-PRE · DECOMM-TAIL · SK-PRE
```

Определения ключевых блоков:
```
BRF(mode)     = BRF:intake → BRF:questions → BRF:ask* → BRF:rewrite* (в appendix);
               режимы: full/light/delta/scope/confirm
BRIEF-CLOSE   = GATE:brief-closed + создать граф (parents)
TZ-WRITE(mode)= [TZ:stabilize]→[TZ:compress]→TZ:patch→[REV:tz]→TZ:finalize(+инвентарь);
               режимы: new/full/patch/freeze; [stabilize]/[compress] — по кейсу (§5.2)
REV           = REV:tz (в TZ-WRITE) · REV:plan (в PLAN-IMPL-TAIL) · REV:report (в RS)
TAKE-INTO-WORK= GATE:take-into-work
                # карточка-узел графа (payload=AC-список в origin), не стоп Саши;
                # auto-pass: ac-shown после показа; фраза/дашборд = идемпотентный no-op
HF-COMPRESS?  = HF:compress (опц., не в PLAN-IMPL-TAIL)
TZ-WRITE(light)= TZ:patch(+indent.y) → [REV:tz skip при ≤3 файла вне shared-модулей] → TZ:finalize(+инвентарь);
                # stabilize/compress skip; версия/bump в том же TZ:patch
PLAN-IMPL-TAIL-LIGHT = HF:impl → HF:test → HF:docs-handoff → GATE:done
                # HF:plan/backup/ORCH/REV:plan/GATE:plan-approve skip для ≤3 файлов
BUGFIX-LIGHT-GRAPH = BUG:diagnose → GATE:diagnose-review → TZ:patch → TZ:finalize
                #   → GATE:take-into-work → HF:impl → HF:test → HF:docs-handoff → GATE:done
                # (план = _fix_plan_*.md ИЛИ непустой body BUG:diagnose, утверждён на diagnose-review;
                #  GATE:diagnose-review — карточка обязательна; HITL Саши нет (v0.3.2); skip HF:plan/GATE:plan-approve/HF:backup/ORCH/REV)
PLAN-IMPL-TAIL= HF:plan → [REV:plan] → GATE:plan-approve → HF-TAIL
HF-TAIL       = HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done
DX            = BUG:diagnose → GATE:diagnose-review (только BUGFIX)
RS            = RS:collect → RS:analyze → [REV:report] → GATE:done
MIG-TAIL      = MIG:plan → GATE:plan-approve → HF:backup → (MIG:block-k → GATE:block-accept)* → ORCH:shared-state → GATE:done
DEC-PRE       = DEC:inventory → GATE:go (R3 «удаляй»)
DECOMM-TAIL   = HF:backup → EXEC → ORCH:shared-state → GATE:done; EXEC ∈ {DEC:exec, MIG:exec}
SK-PRE        = SK:preflight (create/change >15000 байт → compress; DECOMM → inventory/read, без compress)
```

Сборка кейсов из блоков — в §2. Модели — §3.

## 5.2 Обязательный набор фаз по кейсу

Норматив обязательных фаз DEV / CHANGE / BUGFIX. Развёртка блоков — §5.1, сборка кейсов — §2. Skip — только по таблице или явный `flag-waived: Sasha` (REV ниже), не «для скорости» и не «одним agent -p».

Базовые блоки (для сверки набора):

```
TZ-WRITE(m)    = [TZ:stabilize]→[TZ:compress]→TZ:patch→[REV:tz]→TZ:finalize
                 # CHANGE: TZ:stabilize+TZ:compress обязательны; DEV: опциональны
                 #   (карточка в графе → must be done; нет в графе → пропускается)
PLAN-IMPL-TAIL = HF:plan → [REV:plan] → GATE:plan-approve → HF-TAIL
HF-TAIL        = HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done
DX             = BUG:diagnose → GATE:diagnose-review   # только BUGFIX
```

| Кейс | TZ-WRITE | Хвост | Skip / opt |
|---|---|---|---|
| DEV | new | PLAN-IMPL-TAIL полный | `HF:compress` opt; `TZ:stabilize`/`TZ:compress` opt (если в графе → must be done); REV по флагу (default ON) |
| CHANGE | full | PLAN-IMPL-TAIL полный | `HF:compress` opt; `TZ:stabilize`+`TZ:compress` обязательны |
| BUGFIX | patch | PLAN-IMPL-TAIL полный | `HF:compress` skip; `REV:tz` OFF при ≤3 файлах |
| BUGFIX-LIGHT | patch (light) | PLAN-IMPL-TAIL-LIGHT (HF:impl→test→docs→GATE:done) | `HF:plan`/`GATE:plan-approve`/`HF:backup`/`REV:tz`/`ORCH` skip (≤3 файла вне shared-модулей; план на diagnose-review); **всегда** `BUG:diagnose`+`GATE:diagnose-review` |
| CHANGE-LIGHT | light | PLAN-IMPL-TAIL-LIGHT (HF:impl→test→docs→GATE:done) | `TZ:stabilize`/`TZ:compress`/`REV:tz` skip (≤3 файла вне shared-модулей); `HF:plan`/`HF:backup`/`ORCH` skip; HF:docs версия-bump в том же ходе |

**REV / skip:** `REV:tz` снимается **только** явной фразой Саши → на карточке/скрипте фиксируется как `flag-waived: Sasha` (+ фактический session/run, если прогон был). Это легитимный явный skip-путь для **любого** кейса (не только BUGFIX), равнозначный «REV done». Авто-skip `REV:tz` OFF при ≤3 файлах (строка BUGFIX) — отдельное табличное правило, не замена явного waive. Скрипт preflight принимает `REV:tz` done **или** `flag-waived: Sasha`.

Инварианты:
1. Полный набор `TZ-WRITE` + `HF-TAIL` (для DEV/CHANGE/BUGFIX). Skip только по таблице или явный `flag-waived: Sasha`.
2. HF:impl ≠ HF:test — разные карточки, отдельные native runs/accepted invocations.
3. Штатный поезд / любой режим: **auto** = `GATE:take-into-work`, `GATE:plan-approve`, `GATE:done`, `GATE:diagnose-review`. **Never auto:** `GATE:go`, `GATE:block-accept`. Показ AC-списка / AC-отчёта в origin ≠ ожидание Саши **(класс S)**: карточка complete воркером после доставки артефакта. Класс O (operator-hold / открытый Q-n) — preflight ≠ 0, `GATE:done` не complete, сторож напоминает; это не never-auto гейт и не «ждать готово». Auto ≠ skip: механический гейт имеет проверенное evidence до downstream; отдельная содержательная LLM-карточка не требуется, родительская работа фаз не пропускается. Снятие с дашборда / фраза Саши на auto-гейтах — идемпотентный no-op. Хвост §5.2 обязателен; `kanban_complete` корня до `GATE:done` = done запрещён.
4. `ORCH:shared-state` только после `HF:docs-handoff`.
5. M1: manual CLI/dashboard/API action допустим к предметной приёмке при том же verifier до действия, same revision/identity и независимом post-readback полных evidence без drift. Off-board/retro comment без этого — bypass, даже board=done не accepted; post-hook не отменяет transaction.
6. `HF:plan` обязателен до `GATE:plan-approve` — общее правило DEV/CHANGE/BUGFIX (§5.1), не специфика CHANGE.
7. DX (`BUG:diagnose` → `GATE:diagnose-review`) **не** one-pass.
8. One-pass не создаёт второй канал исполнения: native dispatcher запускает профиль; raw agent -p/codex exec вне adapter, cronjob/delegate как второй диспетчер запрещены. BUG-триггер, включая cold start, сначала регистрирует root и диагноз. Manual — M1, retro acceptance не замена допуска.
9. BUGFIX создаёт root/BUG:diagnose/recipe без runnable partial graph: blocked root/works, зависимости и structural check, затем открытие входа. Root не предшественник своих фаз, повтор create идемпотентен; ретро-корень запрещён. LIGHT только после GATE:diagnose-review; пустой auto-pass не evidence.
10. External Cursor/Codex slug не подменяет carrier model карточки; D2 ≠ D1, owners/override — §3.
11. **Ход процесса — оркестратор.** Архитектор/исполнитель/ревизор не создают кейсовый граф, не выбирают кейс, не skip обязательных фаз. Находка «LIGHT» ≠ команда укоротить граф. Own terminal/review передача после writers и identity/gates разрешена, после неё write запрещён; очередь/чужие runs/raw board mutation внешним executor запрещены.
12. Structural-preflight — до открытия входа созданного графа и содержательной работы/external send; на GATE:done дополнительно проверяется принятие всех фаз. Partial graph недопущен. Q1 не обещает бесплатный первый Hermes turn или перехват всех manual surfaces.
13. Root DEV/<slug> закрывается только после полного хвоста и принятого GATE:done. Раннее закрытие запрещено. Живой root + диагноз без diagnose-review → review-required: broken-bugfix-tail; done root без done-гейта → operator-action: premature-close и штатная диагностика/reopen законным владельцем, не nudge/backfill. Корректные done/archived не тревожатся. Старые rule8/rule9 watcher-команды не активная процедура: root guard сохраняется в едином verifier, без нового daemon.

## 5.3 Guard-ы процесса

Норматив — master DevWorkflow Б6/Б17/Б56, один verifier, не второй enum. Protected agent route проверяет до работы/external send и own terminal tools; hook error/exception/timeout — fail closed. Manual/bypass — M1 §5.2.

| Guard | Условие |
|---|---|
| G1 | Фаза/recipe и актуальные master/version/mtime/hash/extract applicability |
| G2 | Immutable packet/render/ReadRef и exact accepted native binding; текстового context-used недостаточно |
| G3 | Собственный committed write-set и каждый repo proof до test/docs/done |
| G4 | Полный recipe до допуска и принятый обязательный хвост на done |
| G5 | Роль не меняет case/recipe/skip и не управляет чужой работой |
| G6 | Канонические фаза→роль/profile, basename/result и нормализованный slug_source; нет строки → отказ |

## 6. Артефакты и пути

| Артефакт | Путь / имя |
|---|---|
| master-ТЗ | `TZ/<Tool>/<Tool>_TZ.md` |
| appendix | `TZ/<Tool>/appendix_<тема>_YYYYMMDD.md` |
| инвентарь | `TZ/MAIN_TZ_INVENTORY.md` |
| этот глоссарий | `TZ/GLOSSARY.md` |
| каталог цепочек | master DevWorkflow и references/canon.md, версия recipe; исполняет штатный канбан |
| research | `Hermes-Backlog/research/` |
| код инструмента | `USERTOOLS/<Tool>/` |
| код скилла | `hermes-workspace/skills/` |
| бэкап | `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` |
| манифест | `EcosystemManifest.json`, `restore-all-skills.sh` |
| digest | `EcosystemManifest.digest.md` |
| контекст-промпт | Master Б56: immutable packet/1.0 → deterministic render/sidecar, ReadRef/MUST-read и exact native accepted binding; один context owner, без ручного prompt/--force |
| structural-preflight | Единый verifier master Б6/Б17/Б56: create/admission/terminal, 10 кейсов; pipeline_context_bundle.py/pipeline_gate_done_preflight.py не обязательные активные пути |
| git-proof реализации | preflight G3: пути из `HF:impl` `changed_files`, лежащие в git-worktree, должны быть закоммичены (не untracked). Не-git деревья (vault ТЗ) — наличие на диске, не git |

## 7. Запрещённые синонимы

| Нельзя | Вместо |
|---|---|
| TZ (про скилл или файл) | `dev-workflow` / «ТЗ» / `TZ:фаза` |
| HF (про скилл) | `dev-workflow` / `HF:фаза` |
| ORCH (голое) | оркестратор / `ORCH:shared-state` |
| DEV (про человека) | исполнитель / архитектор |
| `HF:fix` | `HF:impl` или `BUG:diagnose` |
| `TZ:architect` как бриф | `BRF:*` в TG |
| `TZ:analyze` | не фаза (содержание в BRF + TZ-WRITE) |
| карточка BRF | бриф только в TG |
| карточка-имя блока | развернуть в `PREFIX:фаза` |
| `HF-хвост` / «хвост DEV» | `PLAN-IMPL-TAIL` |
| `HF-TAIL-min` | `DECOMM-TAIL` |
| `HF:docs` / «docs» | `HF:docs-handoff` |
| «backup» без префикса | `HF:backup` |
| `BRIEF` как синоним BRF | `BRF` / `BRIEF-CLOSE` |
| «одним заходом» = один `agent -p` | отдельные канонические фазы/runs/packet bindings; допустимая author/review пара — §0.1; one-pass = вестигиальный ярлык (не склеивать роли); auto-гейты штатного поезда — §5 GATE |
| «воздух воркера» / «модель воздуха» / «ВОЗДУХ-воркера» | D1 «модель карточки» |
| «архитектор строит граф» / «архитектор выбрал LIGHT» | оркестратор строит граф; LIGHT-сужение — оркестратор по §2 |
| роль «тестировщик» | исполнитель на `HF:test` по IAC архитектора |

## 8. Инструменты (указатель)

Полный список имён — `MAIN_TZ_INVENTORY.md`. Здесь не дублировать. Не выдумывать аббревиатуры инструментов. Исключение протокола выдачи MFE/MFL — в USER.md, не в пайплайне.

## Changelog — доставка 2026-11-14

Адресные D1–D9/Q1/Q2 по A1-A3-TRACE изд.2 после REV-a-pack-v2 APPROVE: штатный канбан, root/work/review, профили/carrier/executor, own terminal, G1–G6/immutable binding, Q2 create/change vs DECOMM. Owner ProcessImprovement, имена фаз, firewall, S/O/C и история сохранены. Версия во frontmatter. [Master](DevWorkflow/DevWorkflow_TZ.md), [решения](../dev/pochinka-dev-workflow-20261112/out/DECISIONS-KANBAN-TZ.md), [REV](../dev/pochinka-dev-workflow-20261112/out/REV-a-pack-v2.md), [exact diff/hash отчёт](../dev/pochinka-dev-workflow-20261112/out/A-FINALIZE-DONE.md). Runtime NOT_RUN, D6 NOT_PROVEN.

## Исторический changelog (read-only)

Версии ниже — история своих пакетов, не текущий PASS. Активный DevWorkflow — предметный процесс на штатном канбане по master; старые процедуры файловой машины/модели не активный маршрут.

## v0.2.6 — долг DKP v0.3.2 AC/IAC HITL (2026-09-25)
1. Слой артефакта: `AC-###` в master-ТЗ пакета; `IAC-##` в `HF:plan` (`path`/`verify`/`depends`/`covers`). Не фазы и не скиллы. Омоним: САНКТ `IAC-01..10` ≠ пайплайнные `IAC-##`.
2. HITL Саши в DEV-цикле **ровно две** точки: `GATE:take-into-work` (AC-список) и `GATE:done` (отчёт AC).
3. §5 `GATE:` и инвариант 3: one-pass / любой режим = auto **только** `GATE:plan-approve` (`auto-pass: architect-plan`). `GATE:take-into-work` и `GATE:done` — **never auto**. Не skip фаз, не склейка в один `agent -p`.
4. `GATE:diagnose-review` остаётся в графе DX; **не** HITL Саши (архитектор + `REV:tz`). Требование 4 отменено.
5. CHANGE-LIGHT §2: убран «HF:plan (вшит)» — хвост = `PLAN-IMPL-TAIL-LIGHT`; IAC LIGHT = 1–3 строки в секции ТЗ / `_fix_plan` / body `BUG:diagnose`, не полный `HF:plan`.

## v0.2.7 — покрытие фаза→механизм (2026-09-25)
- Указатель на таблицу DKP «Фазы ↔ скиллы» (v0.3.3); строки без Cursor; BRF-гибрид; epic/aggregate «не этот пайплайн» в §4.

## v0.2.8 — D1/D2 модель карточки vs работа внутри (2026-09-25)
- §3: канон D1/D2 из `kanban-dev-cases` (прецедент `t_2c8ee3b2`), критерий одной фразой, таблица; без жаргона «воздух».
- §5.2.10: D2 ≠ D1; §7: синонимы «воздух воркера» → D1.

## v0.2.9 — контекст-промпт emit-prompt (2026-09-25)
- §6: артефакт «контекст-промпт» — `pipeline_context_bundle.py emit-prompt`; обязателен для `BUG:diagnose` / TZ-WRITE / HF-фаз; диск-кэша экстракта нет.

## v0.2.10 — БЕЗ ИСКЛЮЧЕНИЙ (решение Саши 26.09)
- Канонизированы `emit-prompt` / `check` (`pipeline_context_bundle.py`). Обход тройки context-bundle (`flag-waived` / `--force`) снят: скрипт и `check` блокируют старт всегда, без исключений.
- §6: дополнена фразой об отсутствии обхода.

## v0.2.11 — поезд без HITL-стопа AC (2026-09-28)
- §3: снят «HITL ровно две точки never auto». Слой AC/IAC остаётся артефактом (список/отчёт); карточки гейтов остаются узлами.
- Норма: **показ AC ≠ ожидание** (класс S; класс O — слой v0.2.12, не откат этой нормы).
- §5 `GATE:`: auto = `take-into-work`, `plan-approve`, `done`, `diagnose-review`; never auto = `go`, `block-accept`.
- §5.1 `TAKE-INTO-WORK` = карточка-узел, не стоп Саши.
- §5.2 инвариант 3 переписан (был «auto только plan-approve»). Инвариант 8 без изменений.

## v0.2.12 — процесс vs содержание + 5 guard-ов + operator-hold (2026-09-29 / 2026-09-30)
- §0.1: определения граф / карточка / фаза.
- §2: закрытый список 10 кейсов; семейство на старте (Саша+оркестратор); LIGHT-сужение — оркестратор после объёма.
- §3: процесс vs содержание; архитектор не строит граф; тестирование без отдельной роли (IAC на `HF:plan`, прогон на `HF:test`).
- §3 слой AC/IAC: **выполнение operator-AC ≠ показ** (аддитив 30.09, номер версии сохранён). Классы S (show-only, поезд идёт) / O (operator-hold, блокирует `GATE:done` + напоминание сторожа) / C (crisis, уже канон v0.2.11). Закрытый словарь: `поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n`. Тег `depends: operator:<verb>`; снятие `operator-done: <verb>` + evidence факта (фраза без факта ≠ done). Показ AC ≠ ожидание **остаётся** для класса S; v0.2.11 не откатывается.
- §5 `GATE:`: auto-набор без изменений (`take-into-work` / `plan-approve` / `done` / `diagnose-review`); `GATE:done` auto после preflight 0, где preflight 0 включает operator-hold и open-questions. Never auto = `go` / `block-accept`.
- §5.2 инвариант 3: оговорка O; complete корня до `GATE:done` запрещён. Инварианты 11–12; §5.3 guard-ы G1–G5 (канон DKP v0.4.1 / содержание v0.4.2).
- §6: `context-used:`, structural-preflight на create, git-proof реализации.
- §7: синонимы «архитектор строит граф» / роль «тестировщик».
- Прецеденты: `DEV/pfs-task-slug-not-created` (укороченный граф + untracked); `DEV/tg-topic-duplicate` `t_07c4913c` (operator-AC «поднимай» проглочен при `AC-delivered:`).

## v0.2.15 — строгое правило «не давать мнений» (2026-10-16, пакет `v-dev-workflow-zakrepit-avtomaticheskuyu-ochered`, AC-057)
- §3 таблица ролей, колонка «Не делает» оркестратора: аддитив — «не даёт собственных мнений/рекомендаций/предложений по слагам, техническим развилкам, судьбе карточек, классификациям и архитектуре при работе по канону» (Саша 15.10, Б16.2 п.6, AC-056). Рекомендация — только по явному запросу Саши. Кейсы §2, фазы §5, классы S/O/C — без правок.

## v0.2.14 — файрвол оркестратора в колонке «Не делает» (2026-10-14, пакет `devworkflow-task-slug`, AC-051)

- §3 таблица ролей, колонка «Не делает» оркестратора: аддитив «не предлагает слаги» (`dev/<slug>/` и `entities.task_slug`) и «не даёт технические варианты/решения». Кейсы §2, фазы §5, классы S/O/C — без правок.
- Зеркало файрвола DevWorkflow Б6.4 / Б37; канон содержания не пересматривается.

## v0.2.13 — инвариант раннего закрытия корня / rule9 (2026-10-13, пакет kanban-orchestration-root, DKP v0.4.4)
- §5.2 инвариант 13: корень `DEV/<slug>` закрывается (`kanban_complete`/done) только после создания хвоста до `GATE:done` и `GATE:done` = done (усиление инварианта 3); нарушение = **раннее закрытие корня**, не допустимый сценарий. Сторож `kanban_stuck_monitor.py` `rule9_bugfix_broken_tail`: корень жив + DX done без `GATE:diagnose-review` → block `review-required: broken-bugfix-tail`; корень done и `GATE:done` нет/не done → `operator-action: premature-close` (needs-operator restore/re-open, не nudge). rule8 пропускает BUGFIX-LIGHT — обрыв после DX ловит rule9.
- Полный батч BUGFIX = один `kanban_create` корня+DX+`GATE:diagnose-review`+хвост (инвариант 9); двухшагового unfold нет.
