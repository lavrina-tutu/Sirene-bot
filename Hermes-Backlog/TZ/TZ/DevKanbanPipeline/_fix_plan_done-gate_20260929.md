# `_fix_plan_done-gate` — done-гейт не финален

**Кейс:** CHANGE канона процесса (GLOSSARY + DKP + preflight + сторож + скиллы). Не USERTOOL, ядро канбана не трогать.
**Роль:** архитектор. Фаза: `BUG:diagnose`, read-only. Реализация — отдельные фазы после `GATE:diagnose-review`.
**Императив Саши (28.09, дословно):** не закрывать карточку, пока не выполнены все действия, в том числе от Саши (пример: gateway restart); напоминать, не молчать; контролировать вопросы Саши в пайплайне; бриф недосказан — открыть вопрос, не идти дальше.

**Канон, от которого отталкиваемся:** DKP v0.4.0, GLOSSARY v0.2.11, `pipeline_gate_done_preflight.py` (AC-P08 «граф оборван» уже есть), `kanban_stuck_monitor.py` (правила 1–6, напоминаний operator-hold нет), `appendix_process_rework_20260928.md`.

---

## 0. Диагноз одной фразой

v0.4.0 правильно снял HITL с **просмотра** AC («поезд не ждёт Сашу»), но не различил это с **действиями** Саши, без которых AC пакета физически не выполняется. Preflight проверяет наличие отчёта AC, не выполнение operator-зависимых AC. Вопросы живут только в TG и не являются durable-состоянием графа. Сторож не напоминает. Итог: граф выглядит `done`, работа не закончена.

Две дыры:

| | (а) operator-hold проглочен | (б) хвост оборван |
|---|---|---|
| Прецедент | `DEV/tg-topic-duplicate` `GATE:done` `t_07c4913c` done 28.09 12:58. Отчёт AC явно: «AC-005 ОЖИДАЕТ поднимай. НЕ выполнен». Preflight 0, потому что якорь `AC-###` + маркер `AC-delivered:` есть. Напоминаний не было. | `DEV/pfs-task-human-slug` `t_ff6e1ba9` root done. `HF:plan` `t_683d1fd3` done 27.09 22:28, `children=[]`. `REV:plan` / `GATE:plan-approve` / `HF:impl`…/`GATE:done` не созданы. Код §29 в `USERTOOLS/ProtocolFromSummary` отсутствует. |
| Почему preflight не спас | Канон DKP: «Не парсить формулировки AC». Проверка = артефакт отчёта, не статус каждого AC. `depends: operator` в каноне нет. | AC-P08 ловит done-узел без детей **только если** воркер `GATE:done` вообще запустился. Здесь `GATE:done` не создан, корень закрыт вне preflight (unfold-дыра до W0 + complete корня раньше хвоста). Сторож правила «хвост оборван mid-graph» не имеет. |

v0.4.0 **оставить**: показ AC-списка / AC-отчёта ≠ ожидание; `GATE:take-into-work` / `GATE:plan-approve` / `GATE:diagnose-review` auto; фразы «берём в работу» / «готово» = no-op. Не возвращать never-auto на эти гейты.

Добавить **третий класс**, которого в каноне нет: operator-hold.

---

## 1. Классификация участия Саши (закрывает императив «поезд не ждёт бесконечно»)

Не новая фаза (GLOSSARY §5.2: фазы не добавлять). Это **тег на AC / вопрос + block-reason на корне или `GATE:done`**.

| Класс | Что это | Блокирует `GATE:done`? | Напоминание | Примеры |
|---|---|---|---|---|
| **S — show-only** | Саша *видит* артефакт. Поезд идёт. | нет | нет (уже R5 `notify+wake` показ) | AC-список на take-into-work; AC-отчёт по train-completable AC; freshness «неясно»; «берём в работу» / «готово» |
| **O — operator-hold** | Саша *должен сделать* действие, без которого AC пакета неверен. | **да** | **да, повторно** | «поднимай»; «ставь кроны» (если AC требует живой job); «удаляй» уже `GATE:go`; ответ на открытый вопрос Q-n; недосказанный бриф |
| **C — crisis** | уже канон v0.4.0 | поезд стоит на корне | R5 terminal `blocked` | `review-required: crisis:`; `GATE:go` / `GATE:block-accept`; IDEA до «разбери» |

Закрытый словарь operator-глаголов (не расширять без TZ:patch DKP): `поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n`. Сторож **не** выполняет эти глаголы (как сейчас: не рестартует gateway, не пишет `jobs.json` кроме своего job).

Default AC = класс S. Класс O **только** явной строкой архитектора в master-ТЗ:

```
### AC-005 — после «поднимай»: один лейни
depends: operator:поднимай
```

Без строки — поезд не ждёт. Архитектор **обязан** поставить тег, если AC нельзя закрыть кодом/тестом без глагола Саши. `REV:tz` проверяет покрытие: есть ли operator-AC без тега (ложный auto-done) и тег на train-completable AC (ложный hold).

Снятие hold: оркестратор после **факта** действия (restart выполнен / крон в `jobs.json` / ответ Саши процитирован) пишет на `GATE:done` или корень:

```
operator-done: поднимай
evidence: <ISO> restart_gateway.sh rc=0 | quote: «…»
```

Фраза Саши «поднимай» **без** evidence факта ≠ `operator-done` (иначе снова фиктивный done: сказал, gateway не поднят).

---

## П.1 Канон O vs S — GLOSSARY + DKP

**Write-owner:** канон. Фазы: `TZ:patch` → `REV:tz` → `TZ:finalize` этого багфикса (кейс **CHANGE** процесса, не LIGHT: GLOSSARY + DKP + скрипты + 2 скилла; REV ON).

**Что поменять**

- `GLOSSARY.md` §3 слой AC/IAC: после «Показ AC ≠ ожидание» — абзац **«выполнение operator-AC ≠ показ»**. §5 `GATE:`: auto-набор не менять. `GATE:done` остаётся auto **после preflight 0**; preflight 0 теперь включает operator-hold и open-questions. Never auto по-прежнему `go` / `block-accept`. Лог v0.2.12.
- `DevKanbanPipeline_TZ.md` → **v0.4.1** (аддитивно к v0.4.0, не откат поезда). Секция «Поезд — канон v0.4.0»: таблица S/O/C; строка 1077 («Саша участвует: … поднимай») переписать: участие O **блокирует done + напоминается**, участие S — нет. Preflight-чеклист: пункты 8–9 (operator-done, open-questions empty). «Гейты HITL»: `review-required: operator-action:<verb>` на корне или `GATE:done` — не auto-complete; не путать с «ждать готово» (по-прежнему дефект). Новые AC пакета: AC-D01…D08 (ниже §10).
- `ProcessImprovement_TZ.md` / `_TZ-WORKFLOW-RULES.md`: одна строка-зеркало, без второго канона.
- `DialogBacklogToKanban_TZ.md` **не** трогать (DEV-цикл не его scope).

**Дыра:** (а) канон. (б) канон только отсылкой «хвост §5.2 обязателен; complete корня до `GATE:done` запрещён» — механика в П.5.

**Напоминание:** канон обязывает сторож; сам текст не шлёт TG.

**Фазы кейсов GLOSSARY §5.2:** все с `GATE:done` — DEV / CHANGE / BUGFIX / BUGFIX-LIGHT / CHANGE-LIGHT; плюс MIG/DEC хвосты с `GATE:done`. `GATE:take-into-work` / `plan-approve` / `diagnose-review` **не** меняют семантику auto. BRF / BRIEF-CLOSE — П.3.

**Верификация:** `rg` leftover «Саша смотрит AC… Просмотр не блокирует» без оговорки O; DKP v0.4.1 + GLOSSARY v0.2.12 в инвентаре на `TZ:finalize`. REV:tz ловит двойной канон с v0.3.2 leftover.

---

## П.2 Маркировка AC и выдача hold на finalize

**Write-owner:** канон (контракт) + скилл `tz-workflow` (исполнение). Фазы: `TZ:patch` (форма тега) / `HF:impl` скилла.

**Что поменять**

- Контракт в DKP «Итоговые AC-###»: опциональное поле `depends: operator:<verb>`. Не парсер всего корпуса — **только пакет этой работы** (как I2). Ретрофит всех master-ТЗ **не** делать.
- `TZ:finalize` / ход take-into-work: вместе с AC-списком в origin выдать **подсписок O** (если есть): «эти AC закрываются только после вашего `<verb>`; граф не станет done без этого». Это показ (S) плюс предупреждение, не hold на take-into-work — код/тесты едут.
- В comment `GATE:take-into-work` и корня — машинный блок:

```
operator-holds:
- AC-005 depends: operator:поднимай status=open
```

  `status=open|done`. На finalize все O = `open`.

**Дыра:** (а) — без тега preflight не знает, что AC-005 особый. (б) не этот пункт.

**Верификация:** юнит/смоук: ТЗ с `depends: operator:поднимай` → блок в comment корня; ТЗ без тега → блока нет; REV:tz чеклист «operator-AC без тега = CHANGES_REQUIRED».

---

## П.3 Контроль вопросов Саши и недосказанный бриф

**Write-owner:** канон + `tz-workflow` (BRF / процедура H). Фазы: BRF:* (оркестратор в TG) + `TZ:patch` (если вопрос вскрылся на записи ТЗ).

**Что поменять**

Durable-реестр на **корне** (comment, не `needs_input` на TZ/HF — запрет DKP/GLOSSARY сохранить):

```
open-questions:
- Q-1: <текст> asked=<ISO> status=open
```

Правила:

1. `GATE:brief-closed` / create-батч графа **запрещены**, пока в сессии брифа есть незакрытый вопрос (оркестратор не зовёт `kanban_create` полного графа). Это уже дух tz-workflow «контекст read-only до закрытия вопросов» — сделать проверяемым, не памятью чата.
2. Если архитектор на `TZ:patch` / `HF:plan` видит недосказанный бриф — **стоп**: вопрос в origin (процедура H: один, варианты, рекомендация), строка Q-n на корне, `kanban_block` **корня** `review-required: operator-action: answer:Q-n`. Не додумывать бриф. Не `kanban_block(kind=needs_input)` на TZ/HF.
3. Ответ Саши в TG → оркестратор: `status=closed` + цитата, unblock корня. Поезд продолжает.
4. Preflight `GATE:done`: любой `status=open` → exit 1 (П.4).
5. Вопрос Саши **к уже едущему графу** (не бриф): та же схема Q-n. Не теряется в чате.

Не вводить карточку-фазу `BRF:questions` (GLOSSARY: бриф не карточка).

**Дыра:** (а) вопросы. Неполный бриф больше не проходит в код.

**Напоминание:** Q-n с `status=open` = operator-hold → П.5.

**Верификация:** смоук `_smoke-train`: бриф с открытым Q → графа нет; mid-TZ вопрос → корень blocked; ответ → unblock; `GATE:done` при open Q → preflight 1.

---

## П.4 Preflight `GATE:done` — operator-hold + questions + не врать в отчёте

**Write-owner:** скрипт `~/WorkVault/Registries/pipeline_gate_done_preflight.py` + `test_pipeline_gate_done_preflight.py`. Фазы: `HF:impl` / `HF:test` этого пакета. Вызов воркера `GATE:done` уже канон.

**Что поменять** (поверх существующих 1–7; не ломать AC-P08 / auto-pass / parser title)

Новые проверки, exit 1:

1. **operator-holds.** Собрать `depends: operator:` из comment корня / `GATE:take-into-work` / (опц.) grep `depends: operator:` в master-ТЗ слага, если `tz_path` известен. Для каждого `status=open` без парного `operator-done: <verb>` на `GATE:done` или корне → FAIL `operator-hold не снят: <verb> (AC-xxx)`.
2. **open-questions.** Любой Q-n `status=open` на корне → FAIL `висящий вопрос Q-n`.
3. **Анти-фикция отчёта (узкий, не NLP формулировок AC).** Если в comment `GATE:done` есть строка с якорем `AC-###` и маркером ожидания (`ОЖИДАЕТ` / `НЕ выполнен` / `⏳`) **и** этот AC в operator-holds — FAIL даже при `AC-delivered:`. Это ровно прецедент `t_07c4913c` (отчёт честно написал, что AC-005 не выполнен, preflight пропустил). Не парсить смысл остальных AC (канон «не парсить формулировки» остаётся для класса S).
4. **Корень.** Если `--slug` найден, а `GATE:done` гонит complete при корне уже `done` и хвосте неполном — по-прежнему phases_done_ok + graph_broken_ok. Дополнительно: `HF:plan` done ∈ графа и в `--case` не LIGHT → в графе должны быть `GATE:plan-approve` (или skip LIGHT) и `HF:impl`. Это ловит pfs-форму, **если** preflight вообще вызван.

`GATE_NO_AUTO_PASS` не расширять operator-hold: hold = fail preflight, не новый never-auto гейт. Воркер уже: exit ≠ 0 → `kanban_block`, complete запрещён. Reason канонизировать:

`review-required: operator-action: <verb>`

Не `ждать готово`.

**Дыра:** (а) напрямую. (б) частично — только когда `GATE:done` существует.

**Верификация (обязательные тесты):**

| ID | Фикстура | Ожидание |
|---|---|---|
| T-OH1 | граф PASS как сейчас + `operator-holds: AC-005 поднимай open` без `operator-done` | exit 1 |
| T-OH2 | то же + `operator-done: поднимай` + evidence | exit 0 |
| T-OH3 | comment GATE:done как у `t_07c4913c` (AC-005 ОЖИДАЕТ, AC-delivered есть) | exit 1 |
| T-OH4 | open-questions Q-1 open | exit 1 |
| T-OH5 | Q-1 closed | exit 0 (остальное PASS) |
| T-OH6 | нет operator-holds, отчёт S-класса | exit 0 (регресс v0.4.0) |
| T-OH7 | LIGHT без HF:plan | не требовать operator с плана; graph_broken как сейчас |

Существующие T28–T30 не ломать.

---

## П.5 Сторож: напоминания + оборванный хвост без `GATE:done`

**Write-owner:** скрипт `~/.hermes/scripts/kanban_stuck_monitor.py` (тот же cron `998664fd5843` every 5m). Фазы: `HF:impl` этого пакета. Крон **не** менять в этом пакете (уже 5 мин). Ядро канбана не трогать. Мутации только `hermes kanban`.

**Что поменять** — два новых правила (7 и 8). Молчание при 0 инцидентов сохранить.

### Правило 7 — operator-hold reminder (дыра а)

Детект read-only: корень DEV с comment `operator-holds` `status=open` **или** `block_kind`/`result` содержит `review-required: operator-action:` **или** `GATE:done` в `blocked` с тем же reason.

Действие:

- Не complete, не restart gateway, не `jobs.json`.
- Напоминание в **origin** графа (R5: `kanban_notify_subs.thread_id` корня; не хардкод `:7`; не DM `400307920` по умолчанию). Текст: слаг, глагол, какой AC, что сделать Саше одной фразой.
- Throttle: не чаще 1 раза / 4 ч на пару `(slug, verb)` (state: comment `operator-nudge:<verb>:<unix>` на корне, lookup до send). Первый nudge — сразу при первом тике после hold.
- Эскалация >8 ч hold: второе сообщение в origin с пометкой «граф не done»; **не** auto-skip. Кризис 8ч running (правило 5) не путать с тихим hold.

### Правило 8 — хвост оборван mid-graph (дыра б)

Детект: у корня `DEV/<slug>` есть done-фаза из обязательного набора §5.2, у которой нет ребёнка **и** следующей обязательной фазы нет в reachable-графе, **и** `GATE:done` отсутствует либо не done.

Прецедент: `HF:plan` `t_683d1fd3` done, children=[], нет `REV:plan`/`GATE:plan-approve`/`HF:impl`.

Действие:

- `hermes kanban block <root>` `review-required: broken-tail: <phase> без детей`.
- Если корень уже `done` (pfs) — **не** un-complete задним числом (ядро/история). Алерт origin: «граф фиктивно done, хвост оборван у `<phase>`; нужен repair-slug» + comment на корне. Create rework **не** из сторожа (ключи/батч — оркестратор / отдельный BUGFIX). Сторож только детект+block живого / алерт мёртвого.
- Throttle 4 ч, тот же паттерн nudge.

**Напоминание:** здесь.

**Верификация:** `--dry-run` на копии фикстуры (не боевой `kanban.db` в тесте): OH open → план send origin, 0 мутаций; повтор <4ч → 0 send; broken-tail HF:plan → block reason; 0 инцидентов → тишина. Не `set-model` / reclaim на чужих карточках в тесте.

---

## П.6 Скиллы `tz-workflow` / `hermes-feature`

**Write-owner:** скиллы (`~/hermes-workspace/skills/devops/…`, затем `ORCH:shared-state` → restore). Фазы: `HF:impl` / `HF:docs-handoff`. Бандл `kanban-orchestrator`/`kanban-worker` не форкать.

**tz-workflow**

- После `GATE:brief-closed`: отказ create, если open-questions непусты.
- `TZ:finalize`: записать `operator-holds` из тегов AC; origin-пост с подсписком O.
- Процедура H: любой вопрос → Q-n на корне. Запрет `needs_input` на TZ сохранить.
- Leftover «код не пишется, ждать берём в работу» в чужих ТЗ не чистить этим пакетом.

**hermes-feature**

- Воркер `GATE:done`: порядок тот же (отчёт → origin → `AC-delivered:` → preflight). Новое: в отчёт **нельзя** ставить ✅ на operator-AC со `status=open`; если O ещё open — честно ⏳ **и** не ожидать PASS (preflight 1 → block `operator-action:`).
- Запрет `kanban_complete` **корня**, пока `GATE:done` не done (инвариант уже в DKP; вшить чеклист явно — прецедент pfs).
- После `HF:plan` complete: дети хвоста уже должны быть в батче (W0 v0.4.0). Если воркер плана обнаружил `children=[]` у себя — `kanban_block` `broken-tail`, не complete «план готов». Это закрывает unfold leftover на старых графах, которые ещё едут.
- Identity-стопкран duplicate / «не рестартовать gateway» не трогать.

**Дыра:** (а) воркер больше не complete при ⏳. (б) план без детей не complete; корень не done без `GATE:done`.

**Верификация:** `rg` по скиллам: нет «preflight 0 достаточен» без оговорки operator-hold; есть `operator-action:`; чеклист корня. Смоук W4 дополнить одним O-AC.

---

## П.7 Инцидент `DEV/tg-topic-duplicate` — операционный хвост, не код фикса

**Write-owner:** оркестратор (Сирень), не исполнитель кода процесса. **Не** смешивать в `HF:impl` скиллов.

Факт: код П.1–П.3 того ТЗ на диске; AC-005/П.4 не выполнен; граф уже `GATE:done`. Откатывать done всего графа не нужно.

После W1 (preflight+сторож на диске):

1. Comment на `t_07c4913c` / корень `t_ff1191b0`: `operator-holds: AC-005 depends: operator:поднимай status=open` (ретро, идемпотентно).
2. Напоминание в origin того графа (Personal `:8` — туда ушёл отчёт): «для закрытия AC-005 нужна фраза „поднимай“; без рестарта фикс identity в процессе не живой».
3. Сторож подхватывает правило 7.
4. Когда Саша скажет «поднимай» — оркестратор рестартит, пишет `operator-done: поднимай` + evidence. Отдельный `GATE:done` не переоткрывать; это **дозакрытие AC**, не новый поезд. Смоук AC-005 по тому ТЗ — после рестарта, не в этом пакете.

**Фазы:** не фазы этого CHANGE. Операционка после W1.

**Не** включать restart в смоук процесса.

---

## П.8 Довоз `pfs-task-human-slug` / §29 — **отдельным шагом, не этот фикс**

**Write-owner:** отдельный граф CHANGE/BUGFIX `ProtocolFromSummary` (уже есть живой `DEV/pfs-task-slug-not-created`, `GATE:diagnose-review` `t_3ee5cdf5` **running**). Workspace: `USERTOOLS/ProtocolFromSummary` + master `ProtocolFromSummary_TZ.md` §29. Disjoint с деревом скиллов процесса.

Канон appendix 28.09 п.8 / W5: код `task_slug` **не** класть в process-rework. Этот diagnose подтверждает: `HF:plan` `t_683d1fd3` оборван, §29 в коде нет, корень `t_ff6e1ba9` фиктивно done.

Этот пакет:

- чинит **процесс**, чтобы такое не проходило preflight/сторож (П.4–П.6);
- **не** пишет picker / `pipeline.py` / EntityRegistry `task_slug`.

После `GATE:diagnose-review` слага `pfs-task-slug-not-created`: обычный `TZ-WRITE(patch)` при необходимости + полный `PLAN-IMPL-TAIL` §29 (не LIGHT: PFS shared). Rework старого `t_683d1fd3` не unfold-ить руками в этом фиксе.

**Фазы чужого кейса:** BUGFIX (или CHANGE) PFS: `DX` уже частично есть → `TZ-WRITE(patch)` → `TAKE-INTO-WORK` auto → `PLAN-IMPL-TAIL` полный (`HF:plan` → `REV:plan` → … → `GATE:done`). Не BUGFIX-LIGHT.

**Верификация того шага (не этого пакета):** тесты AC-001…015 §29; picker в `protocol_publish`; preflight `--case CHANGE` или BUGFIX PASS без operator-hold.

---

## П.9 Порядок волн и границы

Как `dev-process-rework`, не ломая живое:

| Волна | Что | Запрет |
|---|---|---|
| **W0** | `TZ:patch` DKP 0.4.1 + GLOSSARY 0.2.12 + этот план как appendix. `REV:tz`. `TZ:finalize` + инвентарь | не править скиллы/скрипты до finalize |
| **W1** | preflight + тесты T-OH* + сторож правила 7–8 | не mutate боевые карточки в pytest; не gateway |
| **W2** | скиллы tz-workflow + hermes-feature | не unfold чужих живых графов «заодно» |
| **W3** | `ORCH:shared-state` restore/digest | `jobs.json` не трогать (крон сторожа уже 5м) |
| **W4** | смоук `_smoke-train`: S-гейт auto; O-AC без «поднимай» → GATE:done blocked + nudge; ответ Q-n; archive смоука | не смоукить на tg-topic-duplicate / pfs / mofs |
| **W-inc** | П.7 ретро-hold duplicate | только comment + nudge |
| **W5 отдельно** | П.8 §29 код | другой слаг, другой workspace |

Кейс этого пакета после diagnose: **CHANGE** процесса (не BUGFIX-LIGHT, не CHANGE-LIGHT). `HF:backup` обязателен перед правкой скиллов. `ORCH:shared-state` в хвосте.

**Что НЕ трогать**

- Ядро: `kanban_db.py`, `kanban_db_notify.py`, `TERMINAL_KINDS`, dashboard.
- Новая фаза `GATE:*` / карточка BRF.
- Откат v0.4.0 (never auto на take-into-work/done).
- Gateway, «поднимай» исполнением сторожа.
- `DialogBacklogToKanban_TZ.md`.
- Код PFS / Topic-origin-routing identity-стопкран.
- `pipeline_context_bundle.py` `--force`.
- `needs_input` на TZ/HF (вопросы только TG + durable comment корня).

---

## П.10 AC этого пакета (payload `GATE:take-into-work`)

Только пакет done-gate / DKP v0.4.1. Наблюдаемое. **Нет** `depends: operator:` на этих AC (поезд процесса не должен ждать Сашу, кроме смоука O-фикстуры).

| ID | Критерий |
|---|---|
| **AC-D01** | GLOSSARY + DKP различают S/O/C; leftover «просмотр AC не блокирует» с оговоркой O |
| **AC-D02** | AC с `depends: operator:поднимай` + нет `operator-done` → preflight exit 1, `GATE:done` не complete |
| **AC-D03** | Реплика отчёта `t_07c4913c` (AC-005 ⏳ при `AC-delivered:`) → exit 1 |
| **AC-D04** | Open Q-n на корне → нет brief-closed create **или** preflight 1, если граф уже есть |
| **AC-D05** | Сторож: open operator-hold → сообщение в origin ≤1-го тика; повтор <4ч не дублирует |
| **AC-D06** | `HF:plan` done + `children=[]` + нет следующей фазы §5.2 → сторож broken-tail (живое) / алерт (корень уже done) |
| **AC-D07** | Граф без operator-holds: preflight 0 как v0.4.0 (регресс поезда нет) |
| **AC-D08** | Код §29 PFS **не** входит в diff этого слага; `pfs-task-slug-not-created` не parents на этот граф |

---

## Сводка write-owner × дыра

| Пункт | Owner | (а) | (б) | Напоминание | Preflight учится |
|---|---|---|---|---|---|
| П.1 | канон | да | отсылка | норма | определяет O |
| П.2 | канон + tz-workflow | да | нет | подсписок O в origin | источник `operator-holds` |
| П.3 | канон + tz-workflow | вопросы | нет | через O | open-questions |
| П.4 | скрипт preflight | да | если GATE:done есть | нет (block) | holds + Q + ⏳ на O-AC |
| П.5 | сторож | да | да (mid-graph) | правило 7/8 | не он |
| П.6 | скиллы | да | да | нет | вызывает preflight |
| П.7 | оркестратор | инцидент | нет | ретро | после W1 |
| П.8 | **другой** граф PFS | нет | **довоз кода** | нет | свой GATE:done |

**Rework/tail pfs-task-human-slug в этом же фиксе: нет.** Отдельный шаг П.8. В этом фиксе — только чтобы процесс больше не ставил такой корень в done.
