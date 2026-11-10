# DevWorkflow core runbook

> Detailed operational rules moved from `SKILL.md`; read for live DevWorkflow cases.

# Dual-path (DevWorkflow W2)

Пока `orchestration.mode` ≠ `workflow-only`:
не `pipeline init` вне `pilot_slugs`.
slug ∈ `pilot_slugs` → стоп, отдай `dev-workflow`.
Иначе канбан + `hermes-feature` / `tz-workflow`.
Два поезда на slug запрещены.
Конфиг: `EcosystemConfig.yaml` → `tools.dev_workflow.orchestration`.
W1: `pilot_slugs: []`, `mode: kanban-primary`.
Откат W2: `git checkout` SKILL.md + `restore-all-skills.sh`.
Баннер 10–15 строк — не переписывать тело старых скиллов.
Только маршрутизация dual-path.
Стоп при живом kanban-running на том же slug.
Пилот один слаг за раз (W2).
## Термины
Перед первым `PREFIX:фаза` читать `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`.
Имена фаз/ролей/скиллов только из канона. Голые TZ/HF/ORCH/DEV без двоеточия запрещены.

## Overview

Единый процесс работы над фичами Hermes и USERTOOLS: от ТЗ до кода, тестов, документации, диагностики и отката. Содержательные роли выполняются **только через codex CLI** (`invoke-role`): архитектор (gpt-6-astra) планирует, ревизор (gpt-6-astra) проверяет, исполнитель (gpt-6.1-sol) пишет и тестирует, компрессор (gpt-6.1-terra) извлекает/переупаковывает факты. Cursor CLI (`agent -p`, roles_cursor.*) — отменён.

**ЖЁСТКОЕ ПРАВИЛО:** Архитектор default (Сирень) НЕ пишет ТЗ, планы, анализ самостоятельно в чате. Все задачи архитектора — ТОЛЬКО через codex CLI (`invoke-role`, роль `architect`, модель `gpt-6-astra`). Текущий агент default (Сирень) координирует: вызывает роли через `invoke-role`, передаёт контекст, принимает результат. Полный документ (план / ТЗ / appendix / research / файл) в контексте роли — без обрезки: полный `cat`, либо путь + «прочитай сам», либо явно «часть 1/N». Никаких попыток «написать план самому» без codex роли. ИСКЛЮЧЕНИЕ из „жёсткого правила": диагностика и план починки бага — НЕ напрямую, а через фазу `BUG:diagnose` BUG:diagnose (см. Блок 6В) ДО любого invoke-role / cronjob(repeat=1) / делегирования. Прямой invoke-role на диагностику/план/реализацию по багу-триггеру без существующей фазы `BUG:diagnose` = нарушение инварианта 8.

## When to Use

- «разработай», «новый инструмент», «напиши код», «реализуй» — Блоки 0–4
- «ошибка», «баг», «не работает», «упало», «разберись», «починить» — Блок 7 (диагностика)
- «проанализируй», «исследуй», «найди», «посчитай», «сравни» — Блок 8 (исследование)
- «обновить гермес», «merge upstream» — Блок 1 + `references/hermes-upgrade-pattern.md`
- Задача с 3+ изменениями конфига/скиллов/инструментов — Блок 6А (QA)

Не для: правок стиля общения (см. `hermes-memory-hygiene`), простой рутины без ТЗ и вариантов.

### Классификатор маршрута (баг vs прямой ответ)

| Триггерные слова | Маршрут (ОБЯЗАТЕЛЬНО) |
|---|---|
| «баг», «ошибка», «не работает», «упало», «почини», «починка», «разберись», «проанализируй ошибки», «cron run failed», «отдай на разбор/план починки», «fix», «root cause» | кейс BUGFIX (DevWorkflow) = BUG:diagnose → GATE:diagnose-review → TZ-WRITE(patch/light) → PLAN-IMPL-TAIL(-LIGHT). ПЕРВЫЙ шаг оркестратора — `pipeline init --case BUGFIX` (рецепт с `BUG:diagnose`) для slug, ДО любого invoke-role / cronjob / delegate. Ретро-корень запрещён (инвариант 9). Классификация LIGHT — после GATE:diagnose-review (≤3 файла вне shared). После `TZ:finalize` (багфикс-ТЗ) `GATE:take-into-work` **auto-pass** (`auto-pass: ac-shown`), payload=AC; `GATE:diagnose-review` **auto** по артефакту `_fix_plan_*.md`/непустому body (императив 28.09, старт→финиш) |
| «спроси», «проверь», «вычисли», «найди данные», «найди в архиве», «сколько», «покажи» | прямой ответ (без кода/процесса; без DevWorkflow-slug) |
| «одношаговый ответ», RESEARCH-триггеры («проанализируй», «исследуй» без починки) | прямой ответ / RS-граф (по DPK-исключениям) |

Правило сверху: «Работа с кодом/процессом (любое изменение) по баг-триггеру — ТОЛЬКО через DevWorkflow (`pipeline init`, кейс BUGFIX). Прямой ответ — только когда НЕТ кода/процесса. Сомнение — всегда в сторону фазы `BUG:diagnose`.»

**Провайдер-недоступность LLM ≠ внутренний баг:** ошибку провайдера НЕ чинить и НЕ заводить BUGFIX-поезд — сообщать по-человечески («провайдер недоступен, система штатна»), Саша такие не чинит. Обычные ошибки (канбан/воркер/интеграция) — чинить по канону, но починку начинать только после «запусти в работу».

**Связь с tz-workflow:** после `TZ:finalize` AC показ в origin → `GATE:take-into-work` auto-pass, поезд идёт сам — этот скилл для реализации, без фразы «берём в работу».

---

## DevWorkflow-шаг

> DevWorkflow (`skills/devops/dev-workflow`, `dev/<slug>/_state.json`, `journal.md`). Оркестратор ведёт slug через `pipeline init` / `next` / `complete-phase`; роли — `emit-prompt` → `invoke-role`. Исполнители **не** пишут в `EcosystemManifest.json` / `entities.json` / `.env` / `jobs.json` — только `ORCH:shared-state`.

### Вход

- Любой HF `invoke-role` без корня `DEV/<slug>` → **стоп** + оркестратор. Исключения DPK: `BRF:*` в TG; одношаговый ответ; RESEARCH.
- Вход в HF-ветку: корень `DEV/<slug>` существует **и** `GATE:take-into-work` **done/auto-pass** (`auto-pass: ac-shown`) — не фраза Саши (императив 28.09). Постановщик завёл полный граф одним батчем, гейт авто-прошёлся после `TZ:finalize`.
- **Все задачи по умолчанию ложатся в план** (кейс DevWorkflow `DEV/<slug>`) после триггера «разработай/доработай/почини» и далее проводятся по канону, без дополнительной команды Саши (требование 1).
- **Slug-guard:** перед `pipeline init` корня `DEV/<slug>` (в т.ч. багфикс-батча) — проверка активного графа по слагу (`todo|ready|running|blocked`, не `done`/`archived`); дубли запрещены (кейс 1, прецедент pfs-notify-link-unprocessed). При совпадении — reuse существующего графа или `interrupt` до разрешения.
- `GATE:plan-approve` / `HF:backup` / `HF:impl`: если `HF:plan` не `done` → **стоп** (GLOSSARY инвариант 6). Не skip плана в one-pass.
- Off-board: **предусловие** — зафиксировать паузу slug в `journal.md` (см. `dev-workflow` `references/handoff.md`), не вызывать `pipeline next` на живой slug; затем допустим прямой `invoke-role` с retro-учётом session ids. Параллельный «ручной» codex CLI (invoke-role) на активной фазе того же slug запрещён (инвариант 8).
- **Снятие устаревшего slug (легаси/другой канал):** если работа уехала из DevWorkflow — закрыть незавершённые фазы через оркестратора (`complete-phase` / пометки в `journal.md`), довести slug до `done` или явно archived; не оставлять «висящие» фазы в `_state.json`.
- **Модели только в `invoke-role`:** на `pipeline init` и в рецепте фаз **не** задавать model override (D1). Штатные роли (architect/reviewer/executor/compressor) — codex CLI внутри `invoke-role`.

Граф HF-фаз — развёртка `PLAN-IMPL-TAIL` + `HF-TAIL` (GLOSSARY §5.1; сборка кейсов — §2):

```
GATE:take-into-work  (уже снят)
├─ HF:compress          parents=[GATE:take-into-work]   # опц., skip на stub/BUGFIX/…
├─ HF:plan              parents=[HF:compress]
├─ REV:plan             parents=[HF:plan]               # по умолчанию; искл. лёгкие BUGFIX/SKILL-CHANGE ≤3 файла
├─ GATE:plan-approve    parents=[REV:plan|HF:plan]
├─ HF:backup            parents=[GATE:plan-approve]
├─ HF:impl              parents=[HF:backup]
├─ HF:test              parents=[HF:impl]
├─ HF:docs-handoff      parents=[HF:test]
├─ ORCH:shared-state    parents=[HF:docs-handoff]
└─ GATE:done            parents=[ORCH:shared-state]
```

Граф выше — **полный граф кейса, создан одним батчем после брифа** (tz-workflow «Вход триггера»): `GATE:take-into-work` + `PLAN-IMPL-TAIL` + `HF-TAIL` уже в графе с parents и ключами `devpipe:<slug>:<phase>`. **Unfold хвоста после гейта НЕТ** (дыра: второй ход → `children=[]`, фазы complete без детей). В **корневом** one-pass (корень сам делает работу) дочерний хвост **не создавать** вообще — см. «One-pass не плодит хвост».

Skills: HF-* / GATE после take-into-work — `hermes-feature`. ORCH:shared-state — только `hermes-feature`.

#### Origin и уведомления (DevWorkflow)

При `pipeline init` зафиксировать `--origin-chat` и `--origin-thread` (диалог/топик инициатора; не Monitoring `:7`, не Errors `:11112`). Ход кейса, AC и паузы на Сашу — в **origin**; техника CLI/инвариантов — ErrorBus. Норматив: скилл `dev-workflow` («HITL и уведомления», `references/invoke.md`). Команды `hermes kanban notify-*` и таблица `kanban_notify_subs` — **legacy**, не использовать (диспетчер снят с W4).

Terminal `blocked` / `waiting_operator` трактовать как «ждёт Сашу» в origin, не как зависание фонового dispatch. Рестарт gateway — только по фразе Саши «поднимай» (AC-010), не из этого скилла.



### Воркер HF-фаз

1. `pipeline status --slug <slug>` → сверка TZ version/mtime → workspace фазы из `_state.json`.
2. **Перед ролью на фазе** (`HF:plan`, `HF:impl`, `HF:test`, `HF:docs-handoff`, `HF:backup`, `REV:plan`, …): `pipeline emit-prompt --slug <slug> --phase <PHASE> --out /tmp/task.md` — **exit 0 обязателен**, иначе **СТОП**. Затем `invoke-role` (фон) с `/tmp/task.md`; прямой вызов роли в обход — только внутри invoke-role (codex CLI; см. `dev-workflow`).
3. `session_id` роли → `journal.md` после первого вызова.
4. Промпт codex CLI (`invoke-role`) — **одна роль, одна фаза:**

```
Одна роль: {role} ({model}). Только фаза {phase}. Чужие фазы не выполнять.
G5: не строй кейсовый граф / не меняй --case / не skip фаз / не выбирай LIGHT — это оркестратор.
```

Роли/модели (PI B3), всё через codex CLI: compress=компрессор `gpt-6.1-terra`; plan/patch/finalize=архитектор `gpt-6-astra` (CHANGE-LIGHT ≤3 файла: medium-effort); REV=ревизор `gpt-6-astra`; impl/test/docs-handoff=исполнитель `gpt-6.1-sol` (LIGHT: executor_light `gpt-6-luna`); backup=координатор (Сирень, Hermes, без Codex); ORCH=оркестратор. Cursor roles_cursor.* — отменён.

5. `complete-phase` с metadata:

```json
{
  "changed_files": ["..."],
  "registry_touches": [],
  "manifest_hints": ["tools.<key> fields to set"],
  "skills_to_sync": ["tz-workflow"],
  "tz_version": "0.1.0",
  "tz_mtime": "2026-09-05T12:00:00Z",
  "codex_session_ids": ["..."],
  "role": "исполнитель",
  "model": "gpt-6.1-sol",
  "pipeline_schema": "1.0"
}
```

6. **Свёртка по `changed_files`:** на фазах **исполнителя** `HF:impl` и `HF:test`: если `changed_files` содержит путь `*_TZ.md` **или** `HF-plan*` → не complete, а `interrupt(reason="review-required: collapsed-chain")`. Не применять к `HF:plan` (план — его артефакт) и к `HF:docs-handoff` (ТЗ — его артефакт).
7. **Машинный факт на диске для read-only фаз `HF:plan`/`REV:plan`** (контроль premature-impl, инвариант 8/Блок 1А). На фазе планирования целевой каталог скилла не должен получать impl-артефактов:
   - **до** `invoke-role`: снимок `disk_before` целевого каталога скилла из ТЗ — `python3 ~/WorkVault/Registries/pipeline_hf_plan_diskfact.py snapshot --skill-dir <abs>` → `journal.md` (JSON).
   - после: `disk_after` + `diff --before --after`. Если `PREMATURE_IMPL` (появились `SKILL.md`/`scripts/`/`tests/`/`references`/`cli.py`, которых не было в before) → `interrupt(reason="review-required: impl-before-plan-approve")`; self-report «каталог есть» при `disk_before.exists=false` = это же block.
   - Легальный черновик (каталог был в before, код в этой фазе не менялся) → complete ок; `HF:impl` затем сверяет с планом, не пишет второй раз.
   - В `complete-phase.metadata` класть `disk_before`, `disk_after`, `premature_impl: false|true`, `allowed_writes` (план-файлы `HF-plan_*.md`).


Непустой `registry_touches` → `interrupt(kind=capability, reason="executor touched shared state")`.

### GATE:plan-approve

- **Always auto** (`auto-pass: architect-plan`); `HF:plan` обязателен до гейта. Саша план не согласовывает.

### Блок 4 — владелец общего state

- Исполнитель = `HF:docs-handoff`: текст скилла/ТЗ-секции **кроме** манифеста; `manifest_hints` в metadata.
- Запись манифеста, digest/render, `restore-all-skills.sh`, `.env`/`jobs.json`/`entities.json` — **только** `ORCH:shared-state` (после `done` всех инструментных фаз).
- **`ORCH:shared-state` (HF-TAIL и `DECOMM-TAIL`):** AC фазы — `python3 ~/WorkVault/Registries/render_manifest.py --check-drift` exit 0 **или** остаток дрейфа явно не про slug этого кейса/DECOMM.
- **После `DEC:exec` (`DECOMM-TAIL`):** в `tools{}` — `status=archived`, `path` = каталог архива; `tz_ref` можно оставить; исторические `links` допустимы — contract-check в `render_manifest.py` пропускает `archived`/`completed`.
- `ORCH:shared-state` workspace: `dir:/home/tkachenkoav/WorkVault/Registries`.

### GATE:done — статус «готово»

Порядок воркера `GATE:done` (контракт AC-delivered):

1. `pipeline status --slug <slug>`.
2. Собрать отчёт AC-### → как тестировали (команда, лог/артефакт, результат).
3. Опубликовать отчёт AC в **диалог = origin-топик** графа (откуда пришёл запрос; не ops-канал Monitoring `:7`, не Errors `:11112`, не личный DM оркестратору; если origin сам `:7` — дубля в другой топик нет).
4. В `journal.md` на фазе `GATE:done`: маркер `AC-delivered: origin` + тело отчёта:
   ```
   AC-delivered: origin
   ## Отчёт AC
   AC-001 → команда / лог / результат
   ```
   Маркер — ТОЛЬКО после реального поста в origin. Не считать комментарий GATE:take-into-work
   (список AC-001) и подписку-уведомление Monitoring `:7` доставкой отчёта, **если origin другой**.
5. Запустить preflight:
   `python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py --slug <slug> --case <DEV|CHANGE|CHANGE-LIGHT|BUGFIX|BUGFIX-LIGHT|RESEARCH|MIGRATION|DECOMM|SKILL-DEV|SKILL-CHANGE> --mode done [--flag-rev]` (`--case` ∈ 10 имён AC-H02, `--mode done` явно)
6. **exit 0 → `complete-phase`** (`auto-pass: preflight-0`), НЕ block «ждать готово» (императив 28.09; preflight 0 достаточен **после снятия operator-holds `operator-done`+evidence и пустых open-questions**). **Нельзя** ✅ на operator-AC со `status=open` в отчёте — честно ⏳; при O open preflight → exit 1 → `interrupt` `review-required: operator-action: <verb>`, complete запрещён. Корень `DEV/<slug>` закрывается **только** после `GATE:done` done (запрет `complete-phase` корня, пока `GATE:done` не done).
7. exit 1 или 2 → comment чек-лист stderr; `interrupt`; **запрет** complete. reason: `review-required: preflight GATE:done` (exit 1) — чинить граф, не ждать Сашу; operator-hold → `review-required: operator-action: <verb>`; или `review-required: collapsed-chain` (exit 2).

**G3 git-proof (AC-H07):** перед `complete-phase` фаз `HF:test` и перед вызовом preflight `GATE:done` — impl-пути из `changed_files` HF:impl, лежащие в git-worktree, **должны быть закоммичены** (`git status --porcelain -- <path>` пуст). Untracked / modified → не complete. Если `emit-prompt` на `HF:test`/`HF:docs-handoff` дал exit 1 из-за untracked — `invoke-role` **не** звать (AC-H05b).

**Always auto** (и в one-pass). Preflight exit 0 **достаточен** для `GATE:done` **после снятия holds и пустых Q**. Фраза Саши «готово» на этом гейте — идемпотентный no-op (гейт уже done). Отчёт AC уже доставлен в origin до auto-complete.

**Воркер `HF:plan`:** после `complete-phase` плана проверить рецепт в `_state.json` — если хвост PLAN-IMPL-TAIL отсутствует (legacy unfold), `interrupt` `review-required: broken-tail: HF:plan без хвоста`, **не** complete «план готов». На каноне v0.4.0+ полный рецепт задаётся при `pipeline init`.

**Процедура H на `HF:plan`:** недосказанный бриф → стоп, `open-questions: Q-n` на корне, block корня `review-required: operator-action: answer:Q-n`, не `needs_input` на HF.

### Режим «делай в 1 проход»

Условия: мастер-ТЗ на диске; открытых вопросов нет; не обход diagnose-review.

Фраза **no-op для снятия AC-гейтов** (DKP 0.4.0): `GATE:take-into-work` / `GATE:done` — **always auto**; `GATE:plan-approve` — always auto.

**Не auto** (кризисный HITL): `GATE:go`, `GATE:block-accept`, IDEA `blocked`, crisis-block корня (`review-required: crisis`). `GATE:diagnose-review` — auto по артефакту.

One-pass — **не** склейка нескольких **дочерних** фаз в одном промпте (`TZ:patch`+`HF:impl` — запрещено GLOSSARY). `BUG:diagnose` — отдельная фаза в рецепте. Баг-триггер начинается с неё.

#### One-pass не плодит хвост (оркестратор, правило C)

**Когда:** режим «делай в 1 проход» и корень `DEV/<slug>` **сам** выполняет цикл — один воркер-корень, **несколько** вызовов `invoke-role` по ролям (architect `gpt-6-astra` затем executor `gpt-6.1-sol` через codex CLI), не один промпт «ТЗ+код+тесты»; на корне — пометка one-pass.

**При постановке — не разворачивать полный хвост (~16 фаз):** вместе с корнем **не** создавать через `pipeline init` типовой граф `TZ-WRITE` (`TZ:stabilize` → … → `GATE:take-into-work`, см. `tz-workflow`) **плюс** `PLAN-IMPL-TAIL` + `HF-TAIL` (`HF:compress` → … → `ORCH:shared-state` → `GATE:done`, см. граф выше). Работа уже в корневом `invoke-role`; дочерний граф после `complete` корня только дублирует её и съедает дублирующий рецепт.

Допустимые варианты:

- **Только корень** (предпочтительно для «корень сделал всё»).
- **Корень + гейты** без промежуточных TZ/HF-фаз (три гейта для audit: `GATE:plan-approve` / `GATE:take-into-work` / `GATE:done` — always auto).
- **Минимальный граф** по кейсу (например `CHANGE-LIGHT` в GLOSSARY §5.1), если размер задачи совпадает — не полный DEV/CHANGE.

> **Ограничение G4/one-pass (AC-H08/H09):** укорочение графа / выбор «минимального» / корневой one-pass — решение **оркестратора + Саши** на постановке; архитектор на `TZ:patch`/`REV:tz` **не** решает сократить граф по собственной инициативе.

Полный хвост «на всякий случай» при корневом one-pass **запрещён**.

**Пошаговый one-pass** (редко, если хвост уже нужен по размеру): промежуточные фазы — **отдельные** invoke-role на каждую фазу; гейты — auto-pass. Не путать с корневым one-pass.

**После `complete-phase` корневого one-pass**, если в рецепте **лишние** фазы остались (legacy init):

1. `pipeline status --slug <slug>` — незавершённые фазы рецепта.
2. Каждую пометить `archived` в `journal.md` + `complete-phase` с reason `auto-archived: one-pass root done` **без** нового invoke-role.
3. `GATE:done`: отчёт AC в origin → `journal.md` с `AC-delivered: origin` → preflight → `complete-phase`.
4. В journal: `one-pass tail archived: <N> phases` (audit).

**XOR-канал координатора (инвариант 8, GLOSSARY §5.2):** пока slug в DevWorkflow «в поезде» (`pipeline status` — незавершённые фазы), координатор **не** дублирует работу параллельным `invoke-role` на те же фазы. Прежде чем сделать любой **ручной** codex CLI / invoke-role по слагу:
1. `pipeline status --slug <slug>`: есть незавершённые фазы → свой `invoke-role` **стоп** (ждать `next` / auto-pass гейтов).
2. Нужен прямой ход (crash-spawn, спешка) → **сначала** пауза slug в `journal.md` (см. `dev-workflow` `references/handoff.md`), не вызывать `next` → затем retro-учёт session ids; для кода — только после `GATE:plan-approve` done. Два параллельных исполнителя одной фазы запрещены.
