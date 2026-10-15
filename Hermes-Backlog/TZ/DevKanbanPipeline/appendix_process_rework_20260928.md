# `_fix_plan_20260928` — DEV/dev-process-rework

**Кейс:** CHANGE канона процесса (GLOSSARY + DKP + скиллы + сторож). Не USERTOOL, ядро канбана не трогать.  
**Роль:** архитектор. Фаза: BUG:diagnose, read-only. Реализация — отдельные фазы после GATE:diagnose-review.  
**Императив Саши (28.09):** поезд «старт → финиш» без ожидания «берём в работу» / «готово»; Саша только бриф + кризис; дубли и зависания недопустимы.

---

## 0. Диагноз одной фразой

Канбан как рельсы не сломан. Сломан слой «ждём Сашу» (HITL never auto v0.3.2) плюс слой «координатор спит» (Питфолл 12) плюс слой «хвост графа создаётся вторым ходом после гейта». Ревизор работал правильно. Убирать канбан — регресс фазности, ревью, тестов и восстановления сессии.

---

## 1. Вердикт по рекомендации 1–8

Канон, от которого отталкиваемся: DKP v0.3.9, GLOSSARY v0.2.10, `hermes-feature` v2.9.0, `tz-workflow` v2.6.0. Инвентарь врёт по глоссарию (строка `0.2.9`) — поправить на `TZ:finalize`.

### 1. Канбан не убирать — **подтвердить**

Саша предложил убрать канбан, потому что видел зависания, не рельсы. Без графа `parents` снова потеря прогресса при обрыве сессии (проблема, ради которой DKP заводили). Снимаем трение, не движок.

Не менять: `kanban_db.py`, статусы, `auto_decompose: false`, один профиль `default`, `TERMINAL_KINDS`.

### 2. Убрать стоп-фразы «берём в работу» / «готово» как условие продолжения — **подтвердить с уточнением**

Карточки `GATE:take-into-work` и `GATE:done` **оставить** (аудит, `parents`, preflight, R5-показ AC). Меняется семантика, не имя фазы (GLOSSARY §7: синонимы запрещены).

| Было (DKP v0.3.2 / GLOSSARY §3, §5.2.3, долг v0.2.6) | Станет |
|---|---|
| HITL Саши **ровно две** точки, **never auto** | Эти две точки — **always auto** после доставки артефакта |
| `TZ:finalize` → AC в чат → `kanban_block` → ждать фразу/дашборд | AC в origin-топик → `auto-pass: ac-shown` → complete → хвост сам `ready` |
| `GATE:done`: preflight 0 **необходим, не достаточен**; ждать «готово» | preflight 0 **достаточен**; complete воркером; отчёт AC уже в чате |

Снятие с дашборда / фраза Саши на этих гейтах становится идемпотентным no-op (гейт уже done).

### 3. Авто-поезд штатного хода — **подтвердить с двумя доработками**

Авто по-прежнему: запись ТЗ, REV, правки по замечаниям, план, код, тесты, docs, ORCH, закрытие после preflight 0, перезапуск упавшего воркера, повтор REV после правок.

**Доработка A — разворот графа одним батчем.** Сейчас дыра вшита в скиллы:

- `tz-workflow` v2.6.0 после `GATE:brief-closed` создаёт только `TZ-WRITE` + `GATE:take-into-work` (строка ~150, граф ~161–167).
- `hermes-feature` v2.9.0 разворачивает `PLAN-IMPL-TAIL` **после снятия** `GATE:take-into-work` (строка ~80).

DKP-диаграмма (строки 261–284) уже рисует полный хвост от корня. Факт скиллов — второй ход, который координатор забывает → `children=[]`, фазы complete без детей (выходные 26–28.09). Целевое: **весь кейсовый граф одним `kanban_create`-батчем** сразу после закрытого брифа (BUGFIX: корень+DX в том же батче, инвариант 9). Диспетчер сам промоутит по `parents`. Второго «разворота хвоста» нет.

**Доработка B — `GATE:diagnose-review`.** DKP v0.3.2: never auto, `kanban_complete` «архитектор вручную», вариант (б) скриптового auto-pass **отклонён**. Это не HITL Саши, но это второй человеческий клик, который выходные проспали. Перекрыть: воркер гейта complete сам, когда `BUG:diagnose` done и на диске есть `_fix_plan_*.md` **или** непустой body. Классификация LIGHT — в том же ходе, без ожидания Саши. REV качества ТЗ остаётся `REV:tz` в `TZ-WRITE`, не на этом гейте.

### 4. Участие Саши — **подтвердить**, явно перечислить исключения

Саша участвует:

1. `BRF:*` в TG (требования). Без закрытого брифа графа нет.
2. Кризис: невыполнимо / неоптимально / разрушающе. Архитектор пишет в origin и ставит `kanban_block` **корня** `review-required: crisis: …`. Поезд стоит, пока Саша не решит.
3. `GATE:go` («удаляй») и `GATE:block-accept` (приём блока миграции) — **never auto**, это и есть кризисный HITL.
4. IDEA-бэклог: `IDEA:analyze` → `blocked` до «разбери» / отказа. Это не DEV-поезд.
5. «поднимай» / «ставь кроны» / «удаляй» — как сейчас (R3). Сторож **не** рестартует gateway и **не** пишет `jobs.json`, кроме заранее утверждённого job этого плана.

Саша **смотрит** AC-список и AC-отчёт (сообщение в origin). Просмотр **не блокирует**.

**Не кризис, не ждать Сашу:** freshness-gate «неясно» (сейчас DKP v0.2.7 → HITL). Станет: complete «неактуально» **или** архитектор решает сам. `needs_input` на TZ/HF по-прежнему запрещён.

### 5. Стоп-кран = безмозглый скрипт, не LLM — **подтвердить с фактическими путями**

«Координатор» — не отдельный бинарь. Это роль GLOSSARY §3 (Cursor `composer-2.5`, механика) + оркестратор Сирень + скилл:

`/home/tkachenkoav/hermes-workspace/skills/devops/kanban-dev-pipeline-orchestration/SKILL.md` v1.1.2  
тот же inode: `~/.hermes/skills/devops/kanban-dev-pipeline-orchestration/SKILL.md`  
**Питфолл 12** (строки 237–258): координатор не проверяет графы между гейтами и говорит «всё в порядке».

Существующий «сторож» **не делает** того, что нужно:

| Объект | Путь / id | Факт |
|---|---|---|
| `kanban_stuck_monitor.py` | `~/.hermes/scripts/kanban_stuck_monitor.py` | только сводка в Monitoring `:7`; пороги ready 2ч / running 1.5ч **от started_at** / blocked 6ч; **нет действий** |
| cron | `998664fd5843` every 30m, `no_agent` | зовёт скрипт выше |
| `gateway_watchdog.sh` | cron `0e33f12eed3a` */15 | gateway up, не канбан |
| `watchdog_tools.sh` | `~/.hermes/scripts/watchdog_tools.sh` | диск/git/gateway, не карточки |
| LLM-отчёт 10 мин | cron `52c5ecec44c6` | жжёт токены по трём графам, ничего не чинит |

Целевой сторож: **расширить** `kanban_stuck_monitor.py` (или сосед `kanban_train_watchdog.py` в том же каталоге, тот же cron). Не USERTOOL, не новая сущность манифеста, не LLM.

Правила (детерминированные):

1. `running` и нет heartbeat **>20 мин** → reclaim + unblock/retry (не wall-clock от `started_at`: легитимный `agent -p` идёт часами, если heartbeat живой). DKP сейчас требует heartbeat «раз в час», `dispatch_stale_timeout_seconds=14400` (4ч) — для поезда слишком поздно; канон heartbeat ужесточить до ≤10 мин на фазах с `agent -p`.
2. `protocol_violation` + D1 Cursor-slug (`cursor-*` / `composer-*` / `claude-sonnet-*` / `gemini-*` без `/`) → `hermes kanban set-model <id> none` + unblock. Канон уже есть в `kanban-worker` (~строка 175) и GLOSSARY §3 D1/D2 — сторож **исполняет**, воркер не ждёт постановщика.
3. REV `CHANGES_REQUIRED` / `REQUEST_CHANGES` → **не** голый unblock. Создать child рабочей фазы (`TZ:patch` / `HF:plan` / `HF:impl`), ключ `devpipe:<slug>:<phase>:rework:<n>:<tz_version>`. Parents = рабочая фаза, **не** REV. После done rework — новая `REV:*` с ключом версии. Питфолл 7 + 12 стыкуются.
4. `running` >4ч при живом heartbeat → notify координатору (origin графа, не обязательно Саше).
5. `running` >8ч или 2 неудачных авто-рестарта → notify Саше в origin + `kanban_block` корня `review-required: stalled-train`.
6. `ready` >20 мин при закрытых parents → алерт координатору (диспетчер не берёт). Не трогать `triage` IDEA.

Питфолл 12 остаётся **поверх** скрипта: при любом сообщении Саши координатор сначала `kanban list` + `show` по живым DEV, не отвечает по памяти. Скрипт не заменяет эту гигиену, он закрывает дыру «Саша молчит → никто не смотрит».

### 6. Идемпотентность, запрет второго канала, целый хвост — **подтвердить с уточнением ключа**

DKP уже пишет `devpipe:<slug>:<phase>:<tz_version_or_none>` — **не соблюдается**. Канон:

- каждый `kanban_create` фазы — с ключом;
- lookup до create; дубль = no-op (уже ProcessImprovement Блок 3, slug-guard DKP п.14);
- rework: суффикс `:rework:<n>:<tz_version>`, иначе второй REV под тем же parent (выходные);
- ручной `agent -p` на фазы живого графа — запрет (GLOSSARY §5.2.8 / Питфолл 6). Off-board только после `dispatch-paused: off-board`;
- после `TZ:finalize` хвост уже существует (батч п.3A). Preflight (и сторож) ловят **«граф оборван»**: обязательная следующая фаза отсутствует или `children=[]` у узла, у которого по §5.2 дети быть должны.

Ложный preflight «PHASE: slug» (двоеточие vs тире) — починить парсер `phase_of_title()` в `pipeline_gate_done_preflight.py`, не заставлять UPDATE title вручную (`dev-pipeline-reliability` инвариант №3, питфолл заголовков).

### 7. Канон HITL v0.3.2 отменяется — **подтвердить**, список шире рекомендации

Править не только названную пятёрку. Двойной канон уже был (DKP сам предупреждает: до HF на диске два текста). Этот пакет **обязан** вычистить leftover, иначе снова «never auto» из скилла победит новый DKP.

Дополнительно к рекомендации: `ProcessImprovement_TZ.md` (контур B: one-pass = auto трёх гейтов — частично совпадёт с новым, но формулировку выровнять под **всегда auto**, не «только фраза 1 проход»), `_TZ-WORKFLOW-RULES.md`, `WorkVault/AGENTS.md`, `TZ/AGENTS.md`, `kanban-dev-cases`, `dev-pipeline-reliability` (v1.1.0 до сих пор: one-pass = auto take-into-work/plan-approve/done — ближе к цели, но привязан к фразе; и инвариант 3б «blocked GATE:done ждать готово = норма» **инвертировать**).

Фраза «делай в 1 проход» остаётся вестигиальной для гейтов (они и так auto) и по-прежнему значит: не склеивать роли, корневой one-pass не плодит второй полный хвост.

### 8. Три живых графа не смешивать; PFS-дыра отдельно — **подтвердить**

| Граф | Статус для этого пакета |
|---|---|
| `DEV/tg-topic-duplicate` | не трогать; ждёт «поднимай»; identity-стопкран DKP v0.3.8 жив **только** для origin-routing |
| `DEV/topic-origin-routing` | не трогать; идёт своим хвостом; этот план **не ждёт** его (императив 28.09: стартовать сразу) |
| MOFS / `mofs-llm-from-hermes-default` | не трогать |
| PFS `task_slug` / 2 слага не в коде | **другой** BUGFIX/CHANGE по `ProtocolFromSummary`; в этот граф не класть. Довести отдельной карточкой после поезда или параллельно **другим** слагом |

Этот пакет = новый слаг `dev-process-rework` (или как назовёт постановщик). Смоук — `DEV/_smoke-train`, не тройка выходных.

`DialogBacklogToKanban_TZ.md` v0.2.0: DEV-цикл и гейты DKP **не** его scope. В этом пакете его не править. Единственное пересечение: фраза «берём в работу» для IDEA→DEV. После патча IDEA по-прежнему HITL; меняется только DEV-хвост после «разбери».

---

## 2. Целевой поезд (после брифа)

```
BRF:* (Саша, TG) → GATE:brief-closed
→ ОДИН create-батч полного графа кейса (ключ на каждую фазу, D1 model=NULL)
→ TZ-WRITE → [REV:tz ⇄ rework-ребёнок TZ:patch] → TZ:finalize
→ AC-список в origin (показ) → GATE:take-into-work auto-pass
→ HF:plan → [REV:plan ⇄ rework] → GATE:plan-approve auto
→ HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state
→ AC-отчёт в origin + маркер AC-delivered: → preflight exit 0
→ GATE:done auto-complete → корень done
```

Стоп только: кризис на корне; `GATE:go` / `GATE:block-accept`; нет брифа; preflight ≠ 0 (чинить граф, не ждать Сашу); сторож исчерпал ретраи (>8ч).

BUGFIX: тот же поезд, голова = `BUG:diagnose` + `GATE:diagnose-review` auto после артефакта плана.

LIGHT: тот же принцип, короткий хвост GLOSSARY §5.2 без возврата полного `HF:plan`.

---

## 3. Пофайловый план правок

Канон скиллов писать в `~/hermes-workspace/skills/...`, затем `ORCH:shared-state` → `restore-all-skills.sh`. Не форкать bundled `kanban-orchestrator` / `kanban-worker` ядро; user-owned `kanban-worker` — только уточнение, что D1-heal делает сторож.

### 3.1 Канон ТЗ / глоссарий

| Файл | Сейчас | Суть правки |
|---|---|---|
| `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md` | v0.2.10 | §3 снять «HITL ровно две точки never auto». §5 `GATE:`: auto = `take-into-work`, `plan-approve`, `done`, `diagnose-review`; never auto = `go`, `block-accept`. §5.1 `TAKE-INTO-WORK` = карточка-узел, не стоп Саши. §5.2 инвариант 3 переписать (был «auto только plan-approve»). Инвариант 8 оставить. Новая норма: показ AC ≠ ожидание. Лог v0.2.11. |
| `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` | v0.3.9 | Новая секция, перекрывающая v0.3.2 «две точки never auto» и п.6–8 «Решения Саши» в части гейтов. Граф: полный батч, не unfold после take-into-work. Preflight 0 достаточен для `GATE:done`. Вход/выход, «Что НЕ трогать» (строки 119, 1138), критерии успеха, таблица фаз, раздел «Гейты HITL». Версия **0.4.0** (ломающее поведение HITL). R5-набор: гейты AC оставить `notify+wake` как **показ**, не как hold. Стопкран identity duplicate **не** переносить на этот слаг. |
| `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/ProcessImprovement/ProcessImprovement_TZ.md` | v0.4.2 | Блок 5 / контур B: one-pass ≠ единственный способ auto-гейтов; штатный DEV = поезд. Не переписывать историю 08.09 — аддитивный канон v0.4.3. |
| `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/_TZ-WORKFLOW-RULES.md` | v1.3 | Строка AC-### оставить. Добавить: согласование ТЗ ≠ стоп реализации; после `TZ:finalize` поезд идёт сам. Версия зеркала синхронизировать с `tz-workflow` после патча (сейчас файл врёт «скилл 1.7.0»). |
| `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md` | GLOSSARY указан 0.2.9 | `TZ:finalize`: GLOSSARY 0.2.11, DKP 0.4.0, ProcessImprovement bump. |
| `/home/tkachenkoav/WorkVault/AGENTS.md` | «Ждать берём в работу» | Заменить: после брифа реализация без фразы; «берём в работу» не стоп. |
| `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/AGENTS.md` | «Wait for берём в работу» | То же. |

Не править этим пакетом: `DialogBacklogToKanban_TZ.md` (кроме косвенного IDEA HITL, который уже верный).

### 3.2 Скиллы пайплайна

| Файл | Сейчас | Суть правки |
|---|---|---|
| `/home/tkachenkoav/hermes-workspace/skills/devops/tz-workflow/SKILL.md` | v2.6.0 | Create после брифа = **полный** граф кейса (TZ-WRITE + take-into-work + PLAN-IMPL-TAIL/LIGHT), ключи, D1 NULL. После finalize: AC в origin, **не** `kanban_block` wait. Убрать leftover «требование 4» / never auto (~236, 308, 312) — DKP v0.3.4 уже помечал расхождение 233/295. IDEA режимы A/B не ломать. → **2.7.0** |
| `/home/tkachenkoav/hermes-workspace/skills/devops/hermes-feature/SKILL.md` | v2.9.0 | Вход HF: корень есть, take-into-work **done/auto**, не фраза Саши. Снять unfold хвоста после гейта (~80). `GATE:done`: после preflight 0 → `kanban_complete`, не block «ждать готово» (~186–206). Чеклист (~541, 547): убрать «явное берём в работу» и «готово только Саша». Diagnose-review auto по артефакту. Кризис → block корня. → **2.10.0** |
| `/home/tkachenkoav/hermes-workspace/skills/devops/kanban-dev-pipeline-orchestration/SKILL.md` | v1.1.2 | Питфолл 7: голый unblock запрещён, только rework-ребёнок рабочей фазы. Питфолл 12: скрипт-сторож = первичный контур; LLM-координатор не имеет права сказать «всё в порядке» без list/show; не ждать следующего HITL. Питфолл 11: heal D1 = сторож, не «эскалация постановщику» как единственный путь. → **1.2.0** |
| `/home/tkachenkoav/.hermes/skills/devops/dev-pipeline-reliability/SKILL.md` | v1.1.0; **нет** копии в hermes-workspace | Инвариант 1: auto-гейты — штат, не привилегия фразы. Инвариант 3б **инвертировать**: hold «ждать готово» после preflight 0 = дефект поезда. Починить описание `phase_of_title`. Пороги сторожа. При impl — завести копию в workspace **или** осознать user-only skill в ORCH. → **1.2.0** |
| `/home/tkachenkoav/.hermes/skills/devops/kanban-dev-cases/SKILL.md` | зеркало кейсов; нет в workspace | Зеркало GLOSSARY §2/§5.2 после HITL-смены. |
| `/home/tkachenkoav/hermes-workspace/skills/devops/kanban-worker/SKILL.md` | v2.0.x, D1/D2 есть | Одна строка: protocol_violation+Cursor-slug → сторож `set-model none`+retry; воркер не complete «успех». Не раздувать skill. |
| `cursor-cli` / `cursor-task-context` | — | Не обязаны, если emit-prompt и запрет `--continue` уже на месте. Точечно: heartbeat ≤10 мин на длинном `agent -p` (сейчас DKP «раз в час»). |

`kanban-orchestrator` v3.0.1: на DEV не грузить (GLOSSARY §4). Не патчить, кроме случая явного leftover «не назначай себе» — его DKP уже перекрывает.

### 3.3 Скрипты и крон

| Файл | Суть |
|---|---|
| `/home/tkachenkoav/WorkVault/Registries/pipeline_gate_done_preflight.py` + `test_pipeline_gate_done_preflight.py` | (1) `GATE:take-into-work` / `GATE:done` допускают auto-pass маркер `auto-pass: ac-shown` / preflight 0. (2) Проверка «граф оборван»: обязательные фазы §5.2 существуют. (3) `phase_of_title()` принимает и `PHASE: slug`, и `PHASE — slug`. (4) `GATE_NO_AUTO_PASS` сузить до `go` / `block-accept`. Не требовать «Саша сказал готово». Тесты расширить. |
| `/home/tkachenkoav/.hermes/scripts/kanban_stuck_monitor.py` (или новый sibling) | Из репортера в исполнителя правил п.5. Read-only SQL/CLI + `hermes kanban` mutate только по правилам. Молчание при 0 инцидентов сохранить. Алерт 4ч → origin графа; 8ч → Саша. Сводку в `:7` не дублировать, если origin другой (канон R5). |
| `~/.hermes/cron/jobs.json` job `998664fd5843` | Интервал 30м → **5–10 мин** (сторож «20 мин heartbeat»). Пишет ORCH, не исполнитель HF. |
| job `52c5ecec44c6` (LLM каждые 10 мин по тройке графов) | Не часть кода поезда. Рекомендация: выключить или сузить после закрытия тройки — это отдельная фраза по кронам, не скрытый side-effect impl. |

Не трогать: `gateway_watchdog.sh`, `watchdog_tools.sh`, `pipeline_context_bundle.py` (запрет `--force` оставить). `pipeline_shared_state_lock.py` на диске **нет** (долг DKP v0.2.7) — **не** включать в этот пакет (другой долг, смешает scope).

### 3.4 Что сторож / координатор **не** являются

- Не `kanban-orchestrator` (bundled playbook мультипрофиля).
- Не ядро dispatcher.
- Не LLM-крон «проверь три графа».

---

## 4. Порядок реализации (чтобы не сломать живое)

Граф этого пакета — обычный BUGFIX/CHANGE по **новому** канону писать нельзя, пока скиллы старые: этот diagnose и хвост ещё едут по v0.3.2. После согласования плана:

| Волна | Что | Зависимости | Запрет |
|---|---|---|---|
| **W0** | `TZ:patch` DKP 0.4.0 + GLOSSARY 0.2.11 + appendix этого плана. `REV:tz`. `TZ:finalize` + инвентарь. | нет | не править скиллы до finalize; не трогать тройку графов |
| **W1** | Скрипты: preflight (оборванный граф + auto-done + parser title) + сторож-действия. Pytest preflight. | W0 | не ставить крон до смоука скрипта `--dry-run`; не `set-model` на чужих живых карточках в тесте |
| **W2** | Скиллы: `tz-workflow` → `hermes-feature` → orchestration Питфолл 7/12 → reliability → kanban-dev-cases → AGENTS.md. Полный граф в create. | W0; W1 желателен до первого живого поезда | не unfold хвоста на `topic-origin` / `tg-topic` / mofs «заодно» |
| **W3** | `ORCH:shared-state`: restore-all-skills, digest при смене skill version. Крон сторожа 5–10 мин. | W2 | gateway не рестартовать; `jobs.json` только job сторожа |
| **W4** | Смоук `DEV/_smoke-train`: бриф-заглушка, батч графа, auto take-into-work, fake-crisis block корня, protocol_violation-fixture → set-model none, REV CHANGES_REQUIRED → rework child, preflight 0 → auto done, archive смоука | W3 | не смоукить на боевых слагах |
| **W5 отдельно** | PFS 2 слага / `task_slug` не в коде | свой слаг | не parents на process-rework |
| **вне пакета** | `topic-origin-routing` HF:impl после identity + «поднимай» | свой граф | этот план не снимает identity-стопкран |

Параллелить W5 с W1–W4 можно только при disjoint workspace (`USERTOOLS/ProtocolFromSummary` vs `TZ`+skills процесса) и капе writers. Не два `agent -p` в `hermes-workspace/skills/devops` одновременно.

W2 не стартовать, пока на диске живой `HF:impl` чужого слага в том же дереве скиллов — дождаться complete/reclaim, не мержить вручную.

---

## 5. Критерии приёмки поезда

Наблюдаемые, без «Саша сказал готово».

1. **AC-P01.** После закрытого брифа на доске полный набор фаз кейса (GLOSSARY §5.2) с `parents` и ключами `devpipe:…`. Повтор create того же ключа = 0 дублей.
2. **AC-P02.** Между `TZ:finalize` и `HF:plan` нет `blocked review-required` ожидания Саши. AC-список есть в origin (comment + факт сообщения). `GATE:take-into-work` = done с `auto-pass: ac-shown`.
3. **AC-P03.** После preflight exit 0 `GATE:done` = done без фразы «готово». Корень закрыт. Отчёт AC в origin + маркер `AC-delivered:`.
4. **AC-P04.** `GATE:go` / `GATE:block-accept` / IDEA `blocked` / crisis-block корня **не** auto.
5. **AC-P05.** REV `CHANGES_REQUIRED` → за 1 tick сторожа или воркера появляется rework-ребёнок рабочей фазы; голого unblock нет; повторный REV с новым ключом.
6. **AC-P06.** Карточка с D1 `cursor-grok-*` → сторож снимает model, retry; нет висения `protocol_violation` >20 мин.
7. **AC-P07.** `running` без heartbeat 20 мин → retry. Живой heartbeat 3ч → нет ложного kill.
8. **AC-P08.** Узел с обязательными детьми по §5.2 не может быть done при `children=[]`; preflight exit 1 «граф оборван».
9. **AC-P09.** Пока граф `todo/ready/running`, второй `agent -p` координатора на ту же фазу не запускается (инвариант 8).
10. **AC-P10.** Смоук W4 прошёл; тройка выходных графов не изменилась этим пакетом (`kanban` list тех слагов = тот же набор id, что до W2).
11. **AC-P11.** `rg` по скиллам пайплайна: нет рабочего «never auto» на `GATE:take-into-work` / `GATE:done` (допустим changelog/история в DKP левая колонка).
12. **AC-P12.** Фазы по-прежнему отдельные карточки / отдельные `agent -p`; `HF:impl` ≠ `HF:test`.

---

## 6. Что НЕ трогать

- Ядро: `kanban_db.py`, `kanban_db_notify.py`, `TERMINAL_KINDS`, dashboard plugin.
- Gateway, «поднимай».
- Профили кроме патча скиллов `default` через restore.
- `auto_decompose`.
- Origin-routing identity / `DEV/tg-topic-duplicate` / `DEV/topic-origin-routing` / MOFS-граф.
- Код PFS `task_slug` (другой слаг).
- `EcosystemManifest.json` руками исполнителя (только ORCH).
- `pipeline_context_bundle.py` исключения `--force`.
- Новые USERTOOL / новый скилл «поезд».
- `sdd-writer`, ядро hermes-agent.

---

## 7. Риски

| Риск | Митигация |
|---|---|
| Саша не видит AC, поезд уже в коде | R5 `notify+wake` на take-into-work/done + пост в origin **до** auto-complete (порядок как сейчас: сначала чат, потом complete) |
| Кризис проглочен | явный `review-required: crisis:`; архитектор обязан стопнуть корень; не `needs_input` на фазе |
| Сторож убивает живой длинный impl | heartbeat, не started_at; порог 20 мин только при тишине heartbeat |
| Сторож плодит rework-дубли | ключ `:rework:<n>:`; lookup |
| Двойной канон на диске снова | W0 сначала текст DKP/GLOSSARY, W2 вычищает скиллы одним хвостом; AC-P11 |
| Этот diagnose-граф сам застрянет на старом HITL | GATE:diagnose-review этого слага ещё старый; после W2 новые графы — поезд. Текущий слаг закрыть смоуком/ручным auto после W2, не ждать Сашу на take-into-work |
| Токены LLM-крона 10 мин | не трогать без фразы по кронам; в отчёте W3 напомнить |

---

## 8. Рекомендация по классификации

После этого diagnose: **CHANGE** канона процесса (много файлов скиллов+ТЗ, не LIGHT: GLOSSARY/DKP/несколько скиллов + скрипт + крон). Не BUGFIX-LIGHT. REV:tz **ON** (ломаем HITL-инвариант). `HF:backup` обязателен перед правкой скиллов.

Открытых вопросов Саше в штатном ходе нет: императив 28.09 закрывает HITL-точки. Единственное, что может встать на `GATE:go`-класс — если исполнитель захочет выключить job `52c5ecec44c6` (это крон). По умолчанию **не выключать** в этом пакете.