## DevWorkflow-шаг

> DevWorkflow (`skills/devops/dev-workflow`). Рецепт в `dev/<slug>/_state.json` после `pipeline init`.

### Когда создавать граф

Создавать граф `DEV/<slug>/…`, если: цикл 2+ шагов tz-workflow/hermes-feature; работа должна пережить обрыв сессии; есть гейт Саши; нужен audit trail. **Не создавать** для одношагового ответа / `delegate_task` / однострочного вопроса Саши.

### Вход триггера (после BRIEF-CLOSE)

Бриф (`BRF:full` / `light` / `delta` / `scope` / `confirm`) — **только в TG** через оркестратора (Сирень), не фаза на диске. **Не вызывать `pipeline init`**, пока на slug (или в сессии брифа до init) есть `open-questions:` с `Q-n` в `status=open` — сначала закрыть вопрос. `pipeline init` / смена `--case` / skip §5.2 делает **ТОЛЬКО оркестратор после `GATE:brief-closed`** — не архитектор на `TZ:patch`/`TZ:finalize`/`REV:tz` (AC-H03/H09). После `GATE:brief-closed` — **один** `pipeline init` с полным рецептом кейса: `TZ-WRITE(mode)` + `GATE:take-into-work` + `PLAN-IMPL-TAIL` (или `-LIGHT` по GLOSSARY §2). `--case`/`mode` — из GLOSSARY §2 (`new` / `full` / `patch` / `freeze`).

После батча — **структурный preflight G4** (AC-H08): `python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py --slug <slug> --case <CASE> --mode create`. Fail → `interrupt` **корня** `kind=dependency`, воркеров не стартовать.

**Полный рецепт сразу после брифа** (императив 28.09): второй «разворот хвоста» после гейта запрещён (legacy unfold). Оркестратор ведёт фазы через `pipeline next`. `GATE:take-into-work` в рецепте и auto-pass после `TZ:finalize`.

- **Запрет `model` на create:** на `TZ:*`, `REV:tz`, `HF:*`, `BUG:*` и `IDEA:analyze` — **без** `--model` / `model=` (D1 = NULL, воркер default Hermes; анти-пример: `invoke-role` с model override (запрещено) на `TZ:patch` → HTTP 400 у Hermes-воркера, `protocol_violation`, прецедент `t_2c8ee3b2`). Кодекс roles — только D2 внутри `invoke-role`.
- **Ключ на КАЖДУЮ фазу при create:** `devpipe:<slug>:<phase>:<tz_version_or_none>` (lookup до create, дубль = no-op; rework — суффикс `:rework:<n>:<tz_version>`).

- **Все задачи по умолчанию** после триггера «разработай/доработай/почини» ложатся в план (кейс DevWorkflow `DEV/<slug>`) и далее проводятся по канону, без дополнительной команды Саши.
- **Slug-guard (перед `pipeline init` для `<slug>`):** если `dev/<slug>/_state.json` уже живой (не `done`) — **не** второй init; reuse или `interrupt` до разрешения. Два поезда на slug запрещены (прецедент pfs-notify-link-unprocessed).
- **Идеи `triage` (`IDEA:*`)** НЕ переводятся в DEV-работу без явного «разбери»/«берём в работу» — это не противоречит «все задачи в план»: идеи в бэклоге — до постановки, по команде Саши (ЖЦ разделён, неконфликтующая формулировка).

Граф кейса — ОДИН батч: TZ-WRITE(mode) + `GATE:take-into-work` + `PLAN-IMPL-TAIL` (parents обязательны). Для DEV/CHANGE (полный) граф:

```
DEV/<slug>                          корень (живёт до GATE:done)
├─ TZ:stabilize
├─ TZ:compress          parents=[TZ:stabilize]
├─ TZ:patch             parents=[TZ:compress]     # архитектор, --resume
├─ REV:tz               parents=[TZ:patch]        # по умолчанию во всех dev-задачах
├─ TZ:finalize          parents=[REV:tz]          # + MAIN_TZ_INVENTORY.md
├─ GATE:take-into-work  parents=[TZ:finalize]     # auto-pass: ac-shown (показ AC ≠ ждать)
└─ PLAN-IMPL-TAIL: HF:plan (parents=[GATE:take-into-work]) ─ [REV:plan] ─ GATE:plan-approve (auto) ─ HF-TAIL (HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done)
```

LIGHT-кейсы (BUGFIX-LIGHT / CHANGE-LIGHT ≤3 файла) — короткий хвост в том же батче (GLOSSARY §5.2): `TZ:patch → TZ:finalize → GATE:take-into-work → HF:impl → HF:test → HF:docs-handoff → GATE:done`. Весь граф создаётся одним ``pipeline init` после брифа после брифа; второго unfold нет.

`workspace_kind`: `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` для TZ-шагов. Skills на фазах: `tz-workflow`. Idempotency каждой фазы: `devpipe:<slug>:<phase>:<tz_version_or_none>`.

#### Origin и уведомления (DevWorkflow)

При `pipeline init` зафиксировать `--origin-chat` и `--origin-thread` (диалог/топик инициатора; не Monitoring `:7`, не Errors `:11112`). Ход кейса, AC и паузы на Сашу — в **origin**; техника CLI/инвариантов — ErrorBus. Норматив: скилл `dev-workflow` («HITL и уведомления», `references/invoke.md`). Команды `hermes kanban notify-*` и таблица `kanban_notify_subs` — **legacy**, не использовать (диспетчер снят с W4).

Terminal `blocked` / `waiting_operator` трактовать как «ждёт Сашу» в origin, не как зависание фонового dispatch. Рестарт gateway — только по фразе Саши «поднимай» (AC-010), не из этого скилла.

#### Быстрый путь CHANGE-LIGHT (опционально, ≤3 файла)

Для малых доработок существующего инструмента (без новых сущностей/cron/.env),
когда канон `GLOSSARY §2/§5.1` выбран кейс `CHANGE-LIGHT` (6 карточек вместо полного графа):

```
TZ:patch (секция + version bump + инвентарь в том же ходе, stabilize/compress skip)
  → HF:impl → HF:test → HF:docs-handoff (создаёт version-handoff)
  → GATE:done (auto-pass после preflight exit 0)
```

- `TZ:stabilize`/`TZ:compress` — **skip** (архитектор читает целевые §, не весь master-ТЗ).
- `REV:tz` — **OFF** при ≤3 файлах кода вне shared/foundational-модулей
  (не трогать общие модули: парсинг дат, запись задач, резолв людей).
- `HF:plan`/`GATE:plan-approve`/`HF:backup`/`ORCH:shared-state` — **skip** для ≤3 файлов
  (бэккап = git/копия 3 файлов; манифест не меняется).
- Такая карточка НЕ содержит «склейку фаз одним invoke-role» — каждая из
  TZ:patch / HF:impl / HF:test / HF:docs-handoff — отдельная карточка/вызов.

- **Выбор LIGHT — оркестратор + Саша на старте** (семейство `*-LIGHT`); сужение
  CHANGE→CHANGE-LIGHT / BUGFIX→BUGFIX-LIGHT делает **оркестратор** после оценки
  объёма на `TZ:patch` / `GATE:diagnose-review`, **не архитектор** (AC-H10).
  Оценка «≤3 файла» в ТЗ — факт для решения, не команда skip.

`GLOSSARY` канон — источник истины; этот раздел — сокращённая шпаргалка.

#### Багфикс (кейс BUGFIX / BUGFIX-LIGHT)

Триггер «баг/ошибка/не работает/почини/разберись/cron run failed» — **первый tool-шаг**:
`pipeline init` корня `DEV/<slug>` **И** `BUG:diagnose` в одном create-батче
(инвариант 9, GLOSSARY §2/§5.2), **до** любого invoke-role / cronjob / delegate.
Ретро-корень запрещён (прецедент pfs-promote-bugfix 22.09 → preflight красный).

```
корень DEV/<slug> + BUG:diagnose      # ОДИН create-батч, до invoke-role
GATE:diagnose-review    parents=[BUG:diagnose]   # auto по артефакту _fix_plan_*.md / непустому body; не HITL Саши
→ TZ-WRITE(patch) → GATE:take-into-work (auto-pass: ac-shown) → ...
```

`GATE:diagnose-review` — **auto** (доработка B плана process-rework): воркер гейта complete сам, когда `BUG:diagnose` done и на диске есть `_fix_plan_*.md` **или** непустой body. Классификация LIGHT — в том же ходе, без ожидания Саши. REV качества ТЗ остаётся `REV:tz` в `TZ-WRITE`, не на этом гейте.

`GATE:take-into-work` — **always auto** (`auto-pass: ac-shown` после показа AC в origin), включая BUGFIX/BUGFIX-LIGHT (императив 28.09).

### Чек-лист TZ-WRITE(full)

Режим `full` = кейс CHANGE (GLOSSARY §2). Все пункты — **отдельные карточки**; parents как в графе выше:

- [ ] `TZ:stabilize` done (path, `version`, `mtime` в metadata)
- [ ] `TZ:compress` done (экстракт 3–5 КБ, без кэша, модель `gpt-6.1-terra` через codex CLI)
- [ ] `TZ:patch` done (архитектор `gpt-6-astra`, `--resume` своей сессии)
- [ ] `REV:tz` done **или** comment `flag-waived: Sasha` (default ON для CHANGE)
- [ ] `TZ:finalize` done (запись `TZ/<Tool>/<Tool>_TZ.md` + инвентарь) — **только после** родителей ниже
- [ ] на каждой фазе TZ-WRITE / `REV:tz` при create: `model_override` IS NULL (проверка `pipeline status --slug <slug>`)
- [ ] ни один из шагов не выполнен «тем же» `invoke-role`, что соседний

Для `TZ-WRITE(new)` / `(patch)` — тот же запрет склейки; набор карточек по §5.2 (stabilize/compress в скобках §5.1).

### Шаги 0–4 (воркер)

На каждом Шаге 0–4:

1. `pipeline status --slug <slug>` — статус мог смениться (blocked/archived → стоп).
2. Сверка `version`/`mtime` мастер-ТЗ с диска.
3. На фазах с запуском роли (`TZ:patch`, `TZ:finalize`, `REV:tz`, …) — сначала `emit-prompt` по контракту «TZ-WRITE: emit-prompt перед invoke-role» (exit 0, иначе СТОП).
4. `фоновый invoke-role` на длинных запусках роли.
5. По успеху — `complete-phase` текущей фазы (metadata: `tz_path`, `tz_version`, `tz_mtime`, `extract_chars` для compress).
6. Следующая фаза станет `ready` автоматически (`auto_promote_children`).

D1 ≠ D2: на create `model_override` NULL; codex CLI только D2 внутри `invoke-role`. Канон GLOSSARY §3.

| Шаг | Фаза | Модель (codex CLI, не `pipeline init --model`) |
||---|---|---|
| stabilize | TZ:stabilize | — (без invoke-role; stat/YAML) |
| 0 | TZ:compress | gpt-6.1-terra (compressor) |
| TZ-WRITE | TZ:patch | gpt-6-astra (architect, `--resume`) |
| REV | REV:tz | gpt-6-astra (reviewer) |
| finalize | TZ:finalize | gpt-6-astra (architect) — запись `TZ/<Tool>/<Tool>_TZ.md` + `MAIN_TZ_INVENTORY.md` |

### TZ-WRITE (`TZ:patch`, `TZ:finalize`): emit-prompt перед `invoke-role`

Перед **любым** запуском роли (`invoke-role`/codex CLI) на фазах `TZ:patch` и `TZ:finalize` (по инструменту):

- `pipeline emit-prompt --slug <slug> --phase <PHASE> --out /tmp/task.md
- exit 0 → **скопировать блок `context-used:` из `/tmp/task.md` в `journal.md`** (G2/AC-H06), затем `invoke-role` с промптом из `/tmp/task.md` (модель роли из YAML `tools.dev_workflow`, кодекс CLI как backend).
- exit ≠ 0 → **СТОП**, роль не запускать (`invoke-role` не вызывать)
- перед `complete-phase` фазы TZ-WRITE / `REV:tz`: `pipeline_context_bundle.py pipeline check --slug <slug> --phase <PHASE> <slug>` — exit 0 обязателен, иначе complete запрещён (G2)

Легальный запуск роли — только от файла `--out` (`$(cat /tmp/task.md)`), не произвольная строка промпта.

**Обхода context-bundle нет (решение Саши 26.09, без исключений):** ни `flag-waived`, ни `--force` / `--force-bypass-sasha-ok` как обход тройки digest+GLOSSARY+мастер-ТЗ; `emit-prompt`/`check` блокируют всегда. (`flag-waived: Sasha` для skip `REV:tz` — отдельный механизм, не context-bundle.)

`TZ:finalize` — роль архитектора, не исполнителя HF. Перед записью master-ТЗ воркер `TZ:finalize`:

1. `pipeline status --slug <slug>` текущей и родителей.
2. Parents: `TZ:compress` done, `TZ:patch` done, и (`REV:tz` done **или** waive `flag-waived: Sasha`). Если REV-карточки нет и кейс DEV с opt REV — parent = `TZ:patch` (как DPK граф `parents=[REV:tz|TZ:patch]`).
3. Любой parent не done → **стоп**, не писать ТЗ (карточка не complete).
4. Metadata complete: `role=архитектор`, `model=gpt-6-astra` (codex CLI), `tz_path`/`tz_version`/`tz_mtime` (PI B3).

**Усиление:** TZ `invoke-role` без корня `DEV/<slug>` → **стоп** (не создавать корень «по памяти»).

**Промпт архитектора TZ-WRITE** (то, что попадает в `/tmp/task.md`): «исполняй поставленную задачу; не строй граф и не создавай недостающие карточки; выбор LIGHT / смену `--case` / skip фаз не делай — это оркестратор; вопросы Саше — через оркестратора» (AC-H03/H09).

### HITL-вопросы (процедура H / R3)

**Запрет** `interrupt(kind=needs_input)` на TZ-фазах и HF-фазах: бриф и вопросы — **в TG** через оркестратора (`BRF:*`) **и** durable на корне. Любой вопрос архитектора/воркера → на корне `open-questions: Q-n: … status=open` + пост в origin (один вопрос, варианты, рекомендация); `interrupt` **корня** `review-required: operator-action: answer:Q-n`. Не `needs_input` на TZ/HF. Не додумывать бриф за Сашу.

Гейты Саши — только `$GATE:*` через `journal.md` + `interrupt(reason="review-required: …")`. Снятие: ответ/фраза в Telegram **или** unblock на дашборде — равнозначны; Сирень: `journal.md` + `operator-done`. Повторное снятие — no-op.

**HITL-приёмка (AC-009-класс) — легальная пауза, не блок-цикл:** на HITL-гейте после успешного ревью воркер/ревизор **блокирует** фазу `kind=needs_input` и ждёт Сашу (например «по 12 инструментам нужна твоя реплика „принят"»). Это НЕ зависание и НЕ воркер-цикл: на HITL оркестратор ставит `waiting_operator` (см. `dev-workflow`). Сторож и `pipeline status` трактуют `blocked(needs_input)` как **«ждёт Сашу»**, а не «подвисла». Не путать с техническим `needs_input`-rekind (`dependency` без живого родителя) — тот по-прежнему эскалируется в triage как невозможный wait.

### После TZ:finalize

Порядок **одного хода** (не параллельно):

1. **СНАЧАЛА** — нумерованный список `AC-001`…`AC-NNN` **дословно** из master-ТЗ в **диалог = origin-топик** графа (не ops-канал Monitoring `:7`, не Errors `:11112`; если origin сам `:7` — дубля в другой топик нет). Показ AC ≠ ожидание **(класс S)**: доставка артефакта, не стоп Саши. Для AC с `depends: operator:<verb>` — в origin явно: «эти AC закрываются только после вашего `<verb>`; граф не станет done без operator-done + evidence».
2. **ЗАТЕМ** — на корень и `GATE:take-into-work` машинный блок `operator-holds:` (все O-AC из пакета, `status=open` на finalize) для строк `depends: operator:<verb>` в master-ТЗ; плюс `journal.md` payload на `GATE:take-into-work` = тот же список AC (маркер `auto-pass: ac-shown`). Hold на take-into-work **не** ставить — это показ (S) + предупреждение.
3. `GATE:take-into-work` — **auto-pass** (`auto-pass: ac-shown`), `complete-phase`, **не** `interrupt` (императив 28.09: старт→финиш, фраза «берём в работу» не стоп). Хвост сам становится `ready` по `parents`.
4. **Манифест vs диск (не ждать HF-хвоста):** если master-ТЗ/`tz_ref` уже на диске и в `MAIN_TZ_INVENTORY.md`, но пути нет в `EcosystemManifest.json` `tools{}` → stub-запись `tools{}` (`status` из инвентаря, не из frontmatter ТЗ) **или** явная карточка `ORCH:shared-state` с AC «`tools.<tz_ref>` зарегистрирован». Полные `links`/контракты — после auto take-into-work / ORCH хвоста.

Hermes-feature стартует без снятия гейта Сашей: хвост уже в рецепте; `pipeline next` после `GATE:take-into-work` done.

### Гейты — оба канала

`GATE:take-into-work` и `GATE:done` — **always auto** (auto-pass по канону: `ac-shown` / preflight exit 0 **после снятия operator-holds и пустых open-questions**). Снятие Сашей / фраза «готово» на них — идемпотентный no-op (гейт уже done). Hold класса O = fail preflight (`review-required: operator-action:<verb>`), не never-auto гейт. `GATE:plan-approve` — always auto (`auto-pass: architect-plan`). **Не auto** (кризисный HITL): `GATE:go`, `GATE:block-accept`, IDEA `blocked`, crisis-block корня (`review-required: crisis`). Повторное снятие — no-op.

### Ручной feed идеи (бэклог)

Два режима — **не смешивать**. См. `TZ/DialogBacklogToKanban/DialogBacklogToKanban_TZ.md`.

#### A) «Положить в бэклог» / «в triage» (passive-inbox)

Триггеры: «положи в бэклог», «положить в triage», «сохрани идею в бэклог», миграция. Показ triage («бэклог», «что в бэклоге») — скиллы `backlog-collector` / `backlog-analyst` (READ only). **Без** слова «разбери».

1. Passive-запись в IDEA-triage (Б28 DevWorkflow_TZ) для `IDEA/<slug>` — без DEV-`pipeline init`.
2. **Не** создавать child `IDEA:analyze`.
3. **Не** запускать `IDEA:analyze` — запись остаётся в triage.
4. Body при ручном feed: без `migrate:passive` (это маркер миграции); idempotency: `dialogbacklog-feed:<iso-timestamp>:<short-hash>`.

#### B) «Разбери идею» (analyze)

Триггеры: «разбери идею», «разбери bk-NNN», «разбери <slug>`. **Не** запускать DEV-граф до «берём в работу» по заключению.

1. Если записи `IDEA/<slug>` нет — создать в triage (Б28).
2. Оркестратор: рецепт с фазой `IDEA:analyze` (RESEARCH/IDEA, Б28).
3. `pipeline next` → `IDEA:analyze` → emit-prompt → invoke-role; без автопромоута без оркестратора.
4. Заключение в `journal.md` и origin; `WAIT_SASHA` до решения Саши.
5. «Берём в работу» → `complete-phase` `IDEA:analyze` → `pipeline init` DEV/CHANGE; IDEA → `done`.

Idempotency analyze: `devpipe:idea:<slug>:analyze`.

**Запрет:** на passive-inbox с `migrate:passive` без явного «разбери» — **не** создавать `IDEA:analyze`.

### TZ drift / reclaim

Расхождение disk vs `_state.json` → `journal.md`: `TZ drift: …` + `interrupt(kind=dependency, reason="TZ master changed on disk")`. Mid-flight bump → пересборка той же фазы с новым `tz_version` в рецепте; старый прогон — `superseded` в journal.
