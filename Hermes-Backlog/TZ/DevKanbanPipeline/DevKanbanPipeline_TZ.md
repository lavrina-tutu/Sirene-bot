---
tool: DevKanbanPipeline
type: infra_plan
title: "Перевод цикла разработки Hermes под канбан (очередь на default)"
version: 0.4.4
date: 2026-10-13
status: approved
runtime_superseded_by: TZ/DevWorkflow/DevWorkflow_TZ.md
runtime_note: "Боевой runtime процесса разработки с W4 — DevWorkflow (скилл dev-workflow + pipeline/). Канбан остаётся архивом до миграции; тело DKP не переписывается этой пометкой."
author: архитектор (cursor-grok-4.6-high, Cursor CLI)
last-section-added: 2026-10-13 — v0.4.4 TZ:finalize guard закрытия корня / premature-close / rule9; TZ:patch rework #1 полный батч BUGFIX (один create-батч, AC-H10 без переписи хвоста)
depends_on:
  - skill:tz-workflow >= 2.0.0
  - skill:hermes-feature >= 2.1.0
  - skill:kanban-orchestrator >= 3.0.0
  - skill:kanban-worker >= 2.0.0
  - skill:cursor-task-context >= 1.0.0
  - skill:cursor-cli
  - TZ/TZ-Workflow/TZ-storage-system.md >= 1.1
  - TZ/TzDevDecommission/TzDevDecommission_TZ.md >= 0.1.0
  - TZ/EcosystemIntegration/EcosystemIntegration_TZ.md >= 0.4.1
  - TZ/tg-topic-duplicate/tg-topic-duplicate_TZ.md  # identity session key; HF:impl R5-origin после GATE:done duplicate
consumers:
  - skill:tz-workflow
  - skill:hermes-feature
  - skill:cursor-cli
  - profile:default (Сирень)
reuse_first: "не USERTOOL и не новый скилл; доработка разделов tz-workflow + hermes-feature + точечные правки cursor-cli/cursor-task-context + config.yaml kanban"
---

# DevKanbanPipeline — канбан-очередь цикла разработки на профиле `default`

## Цель

Сделать цикл разработки Hermes (новое ТЗ → реализация → тесты → документы → «готово») durable-очередью с графом зависимостей на канбане Hermes, оставаясь на одном профиле `default`, без потери прогресса при обрыве сессии и без смены внешних триггеров/гейтов для Саши. Второе применение той же доски — ручной бэклог идей (`triage` → заключение архитектора → HITL).

## Форма ТЗ (reuse-first)

Это **инфраструктурный план**, не USERTOOL и не новый скилл.

Проверено 2026-09-05 по `MAIN_TZ_INVENTORY.md` и `EcosystemManifest.digest.md`: отдельного инструмента/скилла «dev-pipeline на канбане» нет. Есть:

| Что есть | Почему не закрывает задачу |
|---|---|
| Скиллы `tz-workflow`, `hermes-feature` | Описывают шаги, но координация живёт в памяти чата |
| Скиллы `kanban-orchestrator`, `kanban-worker` | Общий движок очереди; не знают шагов ТЗ/фичи и рассчитаны на мультипрофиль |
| `TZ-storage-system` | Хранение/версионирование ТЗ, не runtime-очередь |
| `TzDevDecommission` / `TzDevCleanup` | «Остаёмся на default» — прецедент; канбан не описывают |
| `EcosystemIntegration` | Манифест и компрессор ТЗ; не очередь |
| `SkillsImprovement` | Прецедент «зонтичное ТЗ = патч существующих скиллов» |
| `DialogBacklog` | Автосбор незаконченного контекста — **не** этот план (отложено «после») |

**Решение:** патч существующих скиллов `tz-workflow` и `hermes-feature` (канбан-шаг на каждый этап) + точечные дополнения `cursor-cli` / `cursor-task-context` + значения `kanban:` в `~/.hermes/config.yaml`. Ядро канбана Hermes **не менять**. Новый USERTOOL **не вводится**. Имя папки `DevKanbanPipeline` — **утверждено** (имя плана, как `TzDevDecommission`, не сущности экосистемы). Путь `TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` не переименовывать.

## Решения Саши (принятые)

1. **Один профиль `default`.** Мультипрофильная схема (default-оркестратор + N dev-исполнителей) отклонена: пустая доска, нет файловых замков на общий state, скиллы синкаются только в default, один Cursor-пул, запрет split-профилей после боли с `tz-dev` 13.08.
2. **Канбан = очередь + граф `parents` на default.** Один assignee сериализует dispatch — это полезно для манифеста. Гейты Саши — `review-required` / `kanban_block`, не отдельная колонка «review» (её нет в движке).
3. **Параллелизм без профилей:** при необходимости до двух фоновых `agent -p` с разными `--workspace` на заведомо непересекающиеся деревья, с `--resume`, без `--continue`.
4. **Владелец общего state:** `EcosystemManifest.json`, `entities.json`, `MAIN_TZ_INVENTORY.md`, `.env`, `jobs.json`, запуск `restore-all-skills.sh` — пишет только оркестратор **Сирень** (`default`), фаза `ORCH:shared-state`, отдельной карточкой **после** `done` инструментных карточек (`parents=[...]`). Исполнители сдают diff-список в `kanban_complete.metadata`, реестры не трогают.
5. **Актуальность ТЗ:** экстракты без кэша; первый шаг воркера — перечитать `version`/`mtime` мастер-ТЗ с диска; расхождение → `kanban_block(kind=dependency, ...)`; mid-flight bump → `hermes kanban reclaim` + comment + **новая** child с parents (не re-run той же карточки).
6. **Скиллы доработать, базовый UX не ломать.** На каждый этап пайплайна — завести/двинуть карточку. Прежние триггеры («разработай» / «доработай» / «почини») остаются. Фразы «берём в работу» / «готово» **не hold** штатного поезда (v0.4.0): показ AC ≠ ожидание **(класс S)**. Класс O (operator-hold) — отдельный тег `depends: operator:<verb>`, не откат never-auto на AC-гейтах. Добавлены (не вместо): фраза «делай в 1 проход» (вестигиальна для гейтов); ручной feed идеи в `triage`; дашборд как канал **кризисного** HITL (`GATE:go` / `GATE:block-accept` / IDEA).
7. **Гейты HITL — оба канала** (п.7 **перекрыт v0.4.0** в части AC). Кризисные гейты (`GATE:go`, `GATE:block-accept`, IDEA до «разбери») снимаются **и** фразой в Telegram, **и** дашбордом. На `GATE:take-into-work` / `GATE:done` фраза/дашборд — идемпотентный no-op, если гейт уже auto-complete после показа артефакта.
8. **Режим «делай в 1 проход».** П.8 **перекрыт v0.3.2**, затем **v0.4.0** (см. «Поезд — канон v0.4.0»). Фраза вестигиальна для гейтов: штатный поезд и так auto на `GATE:take-into-work` / `GATE:plan-approve` / `GATE:done` / `GATE:diagnose-review`. Фраза сохраняет: не skip фаз, не склейка ролей в один `agent -p`, корневой one-pass не плодит второй полный хвост карточек.
9. **`GATE:plan-approve`.** **Always auto** (`auto-pass: architect-plan`); `HF:plan` обязателен там, где GLOSSARY §5.2 его требует; Саша план не согласовывает. Auto-pass ≠ skip фазы.
10. **`auto_decompose: false` глобально.** Подтверждено. Граф задают скиллы; decomposer на одном профиле не включать, пока нет specialist-профилей. На пустой доске побочных потребителей нет.
11. **Имя папки/плана — `DevKanbanPipeline`.** Путь `TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` окончательный.
12. **Второе применение канбана — бэклог идей (ручной feed в `triage`).** Саша вручную (фраза/команда, не автокрон) кладёт сырую заметку / незакрытое исследование в карточку `triage`. Silent-воркер `default` (тот же dispatcher, отдельный профиль не нужен) вызывает Cursor-архитектора (`agent -p --model cursor-grok-4.6-high`), пишет заключение в `kanban_comment`, карточка → `blocked` (ждёт Сашу). Когда Саша открыл доску и сказал «берём в работу» — переход в обычный цикл `tz-workflow` → `hermes-feature`. Автокрон сбора незаконченного контекста (паттерн DialogBacklog) в это ТЗ **не входит**, отложено «после».
13. **Все задачи по умолчанию ложатся в план и далее проводятся по канону** (требование 1, 24.09). После триггера «разработай/доработай/почини» — канбан-граф `DEV/<slug>` и цикл по канону, без дополнительной команды Саши. Идеи `triage` (`IDEA:*`) — только по явному «разбери» (ЖЦ разделён, неконфликтующая формулировка).
14. **Валидация задач и рекомендации по постановке — только от архитектора** (требование 2, 24.09). Сирень (Hermes) НЕ предлагает собственное мнение/варианты решений — передаёт архитектору (`cursor-grok-4.6-high` через Cursor CLI), выполняет по его рекомендациям. Мнение «от Hermes» не предлагается.
15. **П.15 / т.3 24.09 перекрыты 26.09 (v0.3.8).** Было: репорты канбана только в Monitoring `:7`, без дублей в ДМ. **Стало:** коммуникация по кейсу/графу — **только** в origin-топике инициатора (forum-топик группы `-1004300127777`, из которого оркестратор завёл корень `DEV/<slug>` или `IDEA/<slug>`). Канал wake/notify = колонка `kanban_notify_subs.thread_id`, не metadata карточки. Контракт: `--thread-id <ORIGIN> --chat-type group`. Monitoring `:7` остаётся **только** для кронов/ops (`jobs.json` `deliver`). ErrorBus `:11112` — отдельно (никогда кейсовый notify). DM не подписывать. Явное указание Саши («пиши в :N») переопределяет канал графа.
16. **Требование 4 отменено v0.3.2; hold AC снят v0.4.0.** Багфикс: `GATE:diagnose-review` не HITL Саши — auto после артефакта плана. `GATE:take-into-work` — карточка-узел с показом AC-списка, **always auto** (`auto-pass: ac-shown`), не стоп Саши.

## Проблема (факты)

Сейчас `tz-workflow` → `hermes-feature` идёт в одном чате Сирени: бриф → компрессия → ТЗ → «берём в работу» → план → код → тесты → документы. Статус «готово» ставит только Саша. Между шагами нет durable-состояния: потеря сессии = потеря прогресса; нет гарантии, что следующий ход начнётся с нужного блока.

Канбан на ВМ уже включён как движок (`dispatch_in_gateway: true`, интервал 60 с), доска пустая. `orchestrator_profile` и `default_assignee` пусты (fallback = активный default). `max_in_progress*` не заданы (unlimited). `auto_decompose: true`. В `toolsets` профиля `default` есть только `hermes-cli` — в обычном чате `kanban_*` инструменты **не** в схеме (появятся у dispatcher-воркера через `HERMES_KANBAN_TASK`, либо после явного включения toolset `kanban`).

Статусы движка: `triage | todo | ready | running | blocked | done | archived`. Колонки `review` нет: HITL-ревью = `blocked` с префиксом `review-required: ` в `reason` (скилл `kanban-worker`).

## Scope

Описывается перевод **цикла разработки** (новый инструмент / доработка / багфикс) под канбан как очередь на `default`, плюс **второе применение** той же доски — ручной бэклог идей.

Внутри:

- заведение графа карточек на входе;
- канбан-шаг каждого блока `tz-workflow` (0–4) и `hermes-feature` (0 / 1А / 2 / 3 / 4, плюс 6В для багфикса);
- гейты AC (`GATE:take-into-work`, `GATE:done`) — **показ** в origin + auto-complete; кризисный HITL — Telegram **и** дашборд (`GATE:go` / `GATE:block-accept` / IDEA);
- режим «делай в 1 проход» (вестигиален для гейтов; preflight exit 0 **достаточен** для auto `GATE:done`; не skip фаз);
- preflight `GATE:done` (`pipeline_gate_done_preflight.py`);
- контекст-промпт `pipeline_context_bundle.py emit-prompt` до любого `agent -p` по инструменту;
- off-board / retro-graph (прецедент exchange 08.09);
- владелец общего state;
- актуальность ТЗ (version/mtime, reclaim при bump);
- конфигурация канбана под этот сценарий (`auto_decompose: false` глобально);
- ручной feed сырых заметок/незакрытых исследований в карточку `triage` (`IDEA:*`) → silent-воркер `default` → Cursor-архитектор → `kanban_comment` → `blocked` → по желанию Саши «берём в работу» в обычный цикл.

Не входит (отложено «после», не этот план):

- автокрон сбора незаконченного контекста по образцу DialogBacklog.

## Что НЕ трогать

- Не создавать dev-профили (только `default`). Отдельный профиль для silent-воркера бэклога идей не нужен: dispatcher уже фоновый OS-процесс.
- Не менять код ядра канбана Hermes (`hermes-agent`, `kanban_db`, `kanban_db_notify.py`, `kanban_tools.py` `_maybe_auto_subscribe` — reuse, не патч, dashboard plugin).
- `gateway/session.py` / `kanban_watchers_notifier.py` — граф `DEV/tg-topic-duplicate`, не этот план.
- Не стартовать `HF:impl` политики origin-routing, пока identity `DEV/tg-topic-duplicate` не закрыт (предпочтительно `GATE:done`; см. «Уведомления графа» / стоп-кран).
- Не массово UPDATE исторических `kanban_notify_subs` на «угаданный origin» (origin неизвестен). Этот канон — только **новые** подписки после вшивки скилла.
- Не ломать одношаговые задачи: `delegate_task` / прямой ответ в чате — канбан не нужен.
- Не заменять детерминированные `no_agent` кроны (MoveFromFF / MOFS / backup и т.п.).
- Не рестартовать gateway.
- Не реализовывать скиллы/скрипты/крон в рамках записи ТЗ (W0 = только канон текста; impl — волны W1+).
- Не кэшировать экстракты компрессора ТЗ на диск.
- CLI `--force` / `--force-bypass` на `pipeline_context_bundle.py` отсутствует. Обхода нет: скрипт/check блокируют старт всегда (решение Саши 26.09) для тройки путей (digest+GLOSSARY+ТЗ).
- Не класть runtime-state канбана в `TZ/DevKanbanPipeline/` (только master-ТЗ + приложения).
- Не писать в `EcosystemManifest.json` / `entities.json` / `.env` / `jobs.json` из карточек исполнителя.
- Bundled-скиллы `kanban-orchestrator` / `kanban-worker` не форкать: исключения однопрофильного режима живут в `tz-workflow` / `hermes-feature`.
- Не включать автокрон сбора незаконченного контекста (DialogBacklog-паттерн) — отложено «после».
- Не auto-complete **кризисные** гейты: `GATE:go`, `GATE:block-accept`. `GATE:take-into-work` / `GATE:done` / `GATE:plan-approve` / `GATE:diagnose-review` — **always auto** после артефакта (v0.4.0). Preflight exit 0 **достаточен** для `GATE:done` (в т.ч. все operator-holds сняты `operator-done` + evidence и `open-questions` пуст). Hold класса O = fail preflight (`review-required: operator-action:<verb>`), не новый never-auto гейт и не «ждать готово».
- Стопкран identity `DEV/tg-topic-duplicate` **не** переносить на слаг `dev-process-rework` (жив только для origin-routing).
- Не переименовывать папку/план `DevKanbanPipeline`.
- Не выполнять канбан-карточку вслепую, если freshness-gate сказал «неактуально» / «неясно».
- Не писать в защищаемые общие файлы без `LOCK_EX` на единый lockfile; writers этих путей **параллельно никогда**.
- Не плодить второй lockfile и не класть замок в `TZ/` / USERTOOLS / ядро канбана (`kanban_db*`).
- Не делать `max_in_progress_per_profile=1` постоянной архитектурой (только временный рубильник); кап `=3` не снижать этим патчем.
- Не фиксировать в этом master-ТЗ **конкретную** классификацию CHANGE vs CHANGE-LIGHT для чужого инструмента — сужение LIGHT делает оркестратор по объёму (GLOSSARY §2), не текст этого ТЗ и не архитектор.
- Не реализовывать freshness-gate / lock-скрипт / патч скиллов / guard-скрипты G1–G5 в рамках этой записи ТЗ (W1–W2, не эта фаза).
- Не давать архитектору/исполнителю `kanban_create` кейсового графа и не принимать skip обязательных фаз «для скорости».

## Вход / выход

### Вход

| Поле | Кто даёт | Когда |
|---|---|---|
| Триггер Саши | чат Telegram / gateway | «разработай X» / «доработай Y» / «почини баг» / «напиши ТЗ» / «делай в 1 проход» / ручной feed идеи в бэклог |
| Мастер-ТЗ на диске | `TZ/<Tool>/<Tool>_TZ.md` | всегда для доработки и после Шага 4 нового ТЗ; обязательно до «делай в 1 проход» |
| Digest экосистемы | `EcosystemManifest.digest.md` | Шаг 0/1 tz-workflow и Блок 0/1А hermes-feature |
| Гейт-фразы Саши | чат **или** дашборд канбана | кризис: «удаляй» / приём блока миграции; IDEA «разбери»; на AC-гейтах фраза = no-op, если уже auto |
| Сырая идея / незакрытое исследование | Саша, вручную | явная фраза/команда положить в бэклог (`triage`); не автокрон |
| Факт канбана | `~/.hermes/config.yaml` + `~/.hermes/kanban.db` | при любом ходе пайплайна |

### Выход

| Артефакт | Кто пишет | Когда |
|---|---|---|
| Граф карточек (`DEV/<slug>/…`) | оркестратор `default` (чат или корневая карточка) | на входе триггера разработки |
| Карточка `IDEA/<slug>` | оркестратор `default` | на ручном feed в бэклог |
| Заключение по идее | silent-воркер `IDEA:analyze` (архитектор) | `kanban_comment`; затем `blocked` |
| Master-ТЗ + строка инвентаря | карточка `TZ:finalize` (роль архитектор) | tz-workflow Шаг 4 |
| Код/тесты/скилл-патч | карточки `HF:impl` / `HF:test` | после auto `GATE:take-into-work` (`auto-pass: ac-shown`; не стоп Саши) |
| `kanban_complete.metadata` (diff-список) | исполнитель | `done` инструментной карточки |
| Манифест, `restore-all-skills.sh`, при необходимости `.env`/`jobs.json`/`entities.json` | карточка `ORCH:shared-state` | после `done` всех инструментных |
| Статус «готово» на корне | воркер `GATE:done` после preflight exit 0 (достаточен) + отчёт AC в origin; фраза Саши = no-op | финал после ORCH; показ AC ≠ ожидание |

## Модель ролей на одном профиле

`default` — и оркестратор, и воркер. Правило bundled-скилла «не делай работу сам / не назначай карточки себе» **не применяется** к этому пайплайну (специалистов нет). Замены:

| Bundled-правило | Правило этого ТЗ |
|---|---|
| Разные профили на разные роли | Все карточки `assignee=default` |
| Оркестратор не пишет код | Оркестратор в **чате** только: HITL, `kanban_create`/`link`/`comment`/`unblock`, не параллелит файловые правки с running-воркером |
| Воркер не фанутит | Воркер шага **не** создаёт кейсовый граф. Допустимо только reclaim-замена **той же** phase (TZ drift); id только из return `kanban_create`. Rework-ребёнок AC-P05, `ORCH:shared-state` и переход IDEA→DEV — **оркестратор или сторож**, не архитектор |
| `auto_decompose` на triage | **Выключен глобально (решение Саши).** Граф создаёт скилл/оркестратор, не decomposer (иначе выдумает несуществующих assignee). Карточки `IDEA:*` садятся в `triage` только как inbox: скилл сразу переводит их в `ready` без decomposer |

Чат Сирени остаётся HITL-каналом Саши. Дашборд канбана — второй равноправный HITL-канал на гейтах. Dispatcher поднимает воркеров `default` на `ready`-карточки — это отдельные OS-процессы с `HERMES_KANBAN_TASK` (silent; для бэклога идей отдельный профиль не заводится). Пока карточка `running`, чат не пишет в workspace этой карточки и в список общего state.

Бэклог идей делит тот же лимит `max_in_progress_per_profile=1` с циклом разработки: пока идёт `DEV/*`, `IDEA:analyze` ждёт в `ready`.

### Процесс vs содержание (v0.4.1)

Норматив 29.09.2026 (инцидент `DEV/pfs-task-slug-not-created`: архитектор сам укоротил граф; реализация осталась untracked). Канон имён — GLOSSARY §0.1 / §3.

| Слой | Кто | Что |
|---|---|---|
| **Процесс** (какой кейс, какой граф, какие фазы) | Саша + оркестратор, **на старте** | выбор из 10 кейсов; `kanban_create`-батч (BUGFIX: корень+DX+diagnose-review+хвост в одном батче); LIGHT — оркестратор (BUGFIX: выбранный хвост в том же create, не перепись после DX); structural-preflight; блокеры сразу в origin |
| **Содержание** | архитектор | ТЗ, план разработки **и** тестирования (IAC), риски, исследование, вопросы Саше. Беспрекословно по поставленной задаче |
| **Код + тесты** | исполнитель | `HF:impl` + `HF:test` по IAC; молча; отдельной роли тестировщика нет |
| **Проверка качества** | ревизор | `REV:tz` / `REV:plan`; возврат на доработку; не ход процесса |

**Запрет архитектору:** строить/укорачивать граф; выбирать кейс или LIGHT-skip; `kanban_create` фаз кейса; решать «достаточно plan→impl→test без TZ-WRITE». Находка в диагнозе ≠ команда на процесс.

`IDEA:analyze`: архитектор пишет заключение; граф `DEV/<slug>` после «разбери» создаёт **оркестратор**.

## Когда канбан нужен

Создавать граф, если выполняется любое:

- цикл из 2+ шагов `tz-workflow` / `hermes-feature`;
- работа должна пережить обрыв сессии;
- есть кризисный гейт Саши (`GATE:go`, `GATE:block-accept`) или бэклог IDEA;
- нужен audit trail шагов;
- Саша вручную кладёт идею/заметку в бэклог (`IDEA:*`).

Не создавать:

- одношаговый ответ / `delegate_task`;
- `no_agent` кроны;
- правки стиля общения / MEMORY без ТЗ;
- автосбор незаконченного контекста (нет крона в этом ТЗ).

## Конфигурация канбана (выставить при реализации)

Факт на 2026-09-05:

```yaml
kanban:
  dispatch_in_gateway: true
  dispatch_interval_seconds: 60
  failure_limit: 2
  orchestrator_profile: ''
  default_assignee: ''
  auto_decompose: true
  auto_decompose_per_tick: 3
  dispatch_stale_timeout_seconds: 14400
# max_in_progress* — отсутствуют (= unlimited)
```

Целевые значения (менять только секцию `kanban:` + `toolsets`; gateway не рестартовать; подхват — следующий tick / новая сессия):

| Ключ | Значение | Зачем |
|---|---|---|
| `auto_decompose` | `false` | **Подтверждено Сашей глобально.** Граф пайплайна задают скиллы; decomposer на одном профиле вреден |
| `orchestrator_profile` | `default` | Явный владелец корня (сейчас пусто = тот же fallback) |
| `default_assignee` | `default` | Несуществующий assignee не зависает в `ready` навсегда |
| `max_in_progress_per_profile` | `1` | Один running-воркер `default` — нет гонки на манифест/скиллы |
| `max_in_progress` | `1` | На машине один профиль; дублирующий предохранитель |
| `dispatch_in_gateway` | `true` | Уже так; не трогать |
| `toolsets` профиля `default` | добавить `kanban` рядом с `hermes-cli` | Чат-оркестратор видит `kanban_*` без shell-обхода |

`auto_promote_children` оставить default `true`: дети с закрытыми parents сами станут `ready`.

### Workspace kinds карточек

`scratch` **запрещён** для пайплайна (удаляется при complete). `worktree` не использовать как default: деревья TZ/USERTOOLS/скиллов — разные корни, не один git-repo задачи.

| Тип карточки | `workspace_kind` |
|---|---|
| TZ-шаги | `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` |
| `IDEA:analyze` | `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` (чтение заметок/черновиков ТЗ; при необходимости — чтение Inbox/research без записи runtime в `TZ/`) |
| Реализация USERTOOL | `dir:/home/tkachenkoav/USERTOOLS/<Tool>` (абсолютный) |
| Патч скилла | `dir:/home/tkachenkoav/hermes-workspace/skills` (канон; `~/.hermes/skills` — симлинк) |
| `ORCH:shared-state` | `dir:/home/tkachenkoav/WorkVault/Registries` + чтение/запись перечисленных файлов общего state |
| Диагностика 6В USERTOOL | `dir:/home/tkachenkoav/USERTOOLS/<Tool>` |
| Диагностика 6В только скилл | `dir:/home/tkachenkoav/hermes-workspace/skills` |
| Диагностика 6В кросс-канон пайплайна (GLOSSARY / DKP / Registries / несколько скиллов) | `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` |

Относительные `dir:` движок отвергает. Путь в карточке — всегда абсолютный. Промпт `emit-prompt` несёт abs-пути тройки (digest / GLOSSARY / ТЗ могут лежать вне `--workspace`).

## Именование и идемпотентность

- Корень разработки: `DEV/<slug>` где `<slug>` = латиница инструмента (`MoveFromLoop`) или `bug-<short>` / `tz-<short>`.
- Шаги разработки: `DEV/<slug>/<phase>` из таблицы фаз ниже.
- Корень бэклога идей: `IDEA/<slug>` (латиница короткого имени идеи).
- Шаг анализа идеи: `IDEA/<slug>/analyze`.
- Idempotency key (если API карточки его принимает): `devpipe:<slug>:<phase>:<tz_version_or_none>` для DEV; `devpipe:idea:<slug>:analyze` для IDEA. Повтор входа в тот же цикл не плодит дубли.
- Tenant не использовать (один хозяин).

## Каталог кейсов (канон GLOSSARY §2)

Один «граф на всё» **не** используется. Каждый триггер Саши → кейс → сборка из блоков GLOSSARY §5.1. Обязательный набор фаз DEV/CHANGE/BUGFIX — **GLOSSARY §5.2**. Канон фаз/ролей: `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`. **Закрытый список: ровно 10 кейсов.** Семейство выбирают Саша и оркестратор **на старте**; LIGHT-сужение — оркестратор после объёма (не архитектор).

| Кейс | Код | Сборка (блоки) |
|---|---|---|
| Новый инструмент/фича | DEV | `BRF(full)` → `BRIEF-CLOSE` → `TZ-WRITE(new)` → `TAKE-INTO-WORK` → `[HF-COMPRESS]` → `PLAN-IMPL-TAIL` |
| Доработка | CHANGE | `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(full)` → `TAKE-INTO-WORK` → `[HF-COMPRESS]` → `PLAN-IMPL-TAIL` |
| Лёгкая доработка (≤3 файла кода+тест+скилл, без новых сущностей/cron/.env) | CHANGE-LIGHT | `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(light)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL-LIGHT` |
| Баг | BUGFIX | `DX` → `BRF(delta)` → `TZ-WRITE(patch)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL` |
| Лёгкий баг (≤3 файла, вне shared) | BUGFIX-LIGHT | `DX` → `TZ-WRITE(patch)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL-LIGHT` (классификация LIGHT — оркестратор/Саша **на старте**, AC-H10; хвост в том же create-батче) |
| Исследование | RESEARCH | `BRF(scope)` → `RS` (без TZ-WRITE/PLAN-IMPL-TAIL) |
| Миграция | MIGRATION | `BRF(light)` → `BRIEF-CLOSE` → `TZ-WRITE(freeze)` → `TAKE-INTO-WORK` → `MIG-TAIL` |
| Удаление | DECOMM | `BRF(confirm)` → `DEC-PRE` → `DECOMM-TAIL` |
| Новый скилл | SKILL-DEV | как DEV {workspace=hermes-workspace/skills, REV ON, ORCH restore} |
| Правка/удаление скилла | SKILL-CHANGE | `SK-PRE` → `CHANGE` \| удаление `SK-PRE` → `DECOMM`; ≤3 файла compress skip, REV OFF |

Бриф (`BRF:*`) — **только в TG** через оркестратора Сирень, не карточка. На TZ/HF-фазах **запрещён** `kanban_block(kind=needs_input)`.

Ниже — развёртка типового кейса DEV/CHANGE (блок `TZ-WRITE` + `PLAN-IMPL-TAIL` + `HF-TAIL`).

## Граф карточек (DEV/CHANGE — типовой кейс)

Все карточки: `assignee=default`. Родители передавать **в том же** `kanban_create` (`parents=[...]`), не линковать позже. Сначала создать родителей, взять `task_id` из return, затем детей.

**Полный батч (v0.4.0).** После `GATE:brief-closed` — **один** `kanban_create`-батч всего кейсового графа (TZ-WRITE + `GATE:take-into-work` + PLAN-IMPL-TAIL / LIGHT, ключ на каждую фазу, D1 `model=NULL`). Второго «разворота хвоста» после `GATE:take-into-work` **нет**. Диспетчер сам промоутит по `parents`.

```
DEV/<slug>                          корень (живёт до GATE:done)
│
├─ TZ:stabilize
├─ TZ:compress          parents=[TZ:stabilize]
├─ TZ:patch             parents=[TZ:compress]     # архитектор, HITL в TG
├─ REV:tz               parents=[TZ:patch]        # опц., флаг кейса
├─ TZ:finalize          parents=[REV:tz|TZ:patch]
├─ GATE:take-into-work  parents=[TZ:finalize]    # auto-pass: ac-shown; payload=AC; не стоп Саши
├─ HF:compress          parents=[GATE:take-into-work]   # опц.
├─ HF:plan              parents=[HF:compress]    # Блок 1А
├─ REV:plan             parents=[HF:plan]        # опц.
├─ GATE:plan-approve    parents=[REV:plan|HF:plan]  # always auto (architect-plan)
├─ HF:backup            parents=[GATE:plan-approve]
├─ HF:impl              parents=[HF:backup]
├─ HF:test              parents=[HF:impl]
├─ HF:docs-handoff      parents=[HF:test]        # diff в metadata, без манифеста
├─ ORCH:shared-state    parents=[HF:docs-handoff]  # Сирень (оркестратор)
└─ GATE:done            parents=[ORCH:shared-state]
```

Багфикс — **тот же** полно-батчевый `kanban_create`, что DEV/CHANGE (не исключение). Все узлы ниже — в **одном** батче, сразу со связями `parents` (инвариант 9: корень+`BUG:diagnose` не ретро; плюс `GATE:diagnose-review` и LIGHT/полный хвост в том же create).

Инвариант tz-workflow: даже с известным root cause нет перехода сразу в hermes-feature без ТЗ-файла.

**Полный батч BUGFIX** (семейство BUGFIX, хвост = TZ-WRITE(patch) + PLAN-IMPL-TAIL; всё в одном `kanban_create`):

```
корень DEV/<slug>
  + BUG:diagnose                          # инвариант 9, не ретро
  + GATE:diagnose-review   parents=[BUG:diagnose]  # auto после артефакта плана (v0.4.0)
  + TZ-WRITE(patch)        parents=[GATE:diagnose-review]  # секция в master-ТЗ, без шортката
  + GATE:take-into-work    parents=[TZ:finalize]   # auto-pass: ac-shown
  + PLAN-IMPL-TAIL         parents=[GATE:take-into-work]  # HF:plan → … → GATE:done
```

**BUGFIX-LIGHT** (≤3 файла кода+тесты, вне shared-модулей; классификация LIGHT/полный — оркестратор/Саша **на старте**, AC-H10; не архитектор; карточки выбранного хвоста — в том же батче):

```
корень DEV/<slug>
  + BUG:diagnose                          # инвариант 9, не ретро; ОДИН create-батч со всем ниже
  + GATE:diagnose-review   parents=[BUG:diagnose]  # auto после артефакта плана; HITL Саши нет
  + TZ:patch               parents=[GATE:diagnose-review]
  + TZ:finalize            parents=[TZ:patch]
  + GATE:take-into-work    parents=[TZ:finalize]    # auto-pass: ac-shown; payload=AC
  + HF:impl                parents=[GATE:take-into-work]
  + HF:test                parents=[HF:impl]
  + HF:docs-handoff        parents=[HF:test]        # version/skill, НЕ манифест
  + GATE:done              parents=[HF:docs-handoff]  # preflight --case BUGFIX-LIGHT
```

skip: `HF:plan`, `GATE:plan-approve`, `HF:backup`, `REV:tz`/`REV:plan`, `HF:compress`, `ORCH:shared-state`. План = `_fix_plan_*.md` **или** непустой body `BUG:diagnose` (утв. на diagnose-review). Не генерировать пустые `auto-pass`-флаги.

**Полный батч BUGFIX (один `kanban_create`, не двухшаговый unfold).** Багфикс-батч создаёт **полный** граф в одном `kanban_create`: корень `DEV/<slug>` + `BUG:diagnose` (инвариант 9) + `GATE:diagnose-review` (`parents=[BUG:diagnose]`) + LIGHT/полный хвост (`TZ:patch→…→GATE:done`) со связями `parents`. Диспетчер фазы не создаёт (только промоутит `parents`). Авто-разворота хвоста через LLM в ядре **нет** и **не** предлагается как основной (вариант 1 плана `_fix_plan_20261012.md`). Двухшагового unfold (расшивка хвоста вторым ходом оркестратора после done DX) **больше нет**. `rule9` (два класса) — **защитный** сторож от обрыва, не основной маршрут и не требование до-разворота.

После done `BUG:diagnose` карточка `GATE:diagnose-review` уже `ready` — диспетчер подхватывает сразу (не ждёт второго хода оркестратора). После done `GATE:diagnose-review` (auto по артефакту плана) хвост `TZ:patch→…→GATE:done` уже в графе — поезд едет до `GATE:done` без второго unfold. Классификация LIGHT/полный — решение оркестратора/Саши на старте (AC-H10); карточки выбранного хвоста создаются в том же батче. Уточнение LIGHT → полный тайл не меняет график в одном батче (это не второй unfold).

Анти-паттерн (прецеденты 30.09–12.10: `pfs-empty-entity-guard`, `pfs-sink-aid-unrouted`, `pfs-task-slug-picker`, `pfs-notify-stale`): корень+DX без полного хвоста в первом батче → граф умирает после диагноза (~15 ч на `pfs-empty-entity-guard`). Канон — одно-батчевый полный граф. Исторические рабочие двухшаговые ходы (`mfl-exchange-lxml`, `pfs-task-slug-fix`) — прецедент дыры, не канон.

**ИНВАРИАНТ (guard закрытия корня).** Корень `DEV/<slug>` закрывается (`kanban_complete`, status=done) **только** когда в графе создан хвост до `GATE:done` **и** `GATE:done` = done. `kanban_complete` корня до `GATE:done` **запрещён** (GLOSSARY §5.2 инвариант 3). `GATE:done` — единственное законное место закрытия корня. Нарушение = **раннее закрытие корня** (не допустимый сценарий, не «корень как DX-контейнер уже можно закрыть»).

Сторож `kanban_stuck_monitor.py` правило `rule9_bugfix_broken_tail` (два класса, **не смешивать**; код — `HF:impl`):

| Класс | Условие | Действие |
|---|---|---|
| **корень ещё жив** | `BUG:diagnose` done, нет `GATE:diagnose-review` в графе, root status ≠ done | `kanban block <root> "review-required: broken-bugfix-tail: BUG:diagnose done без GATE:diagnose-review"` — блок корня (как rule8) |
| **раннее закрытие корня** | root status=done **и** (`GATE:done` нет в графе **или** не done) | `kanban block <root> "operator-action: premature-close: root done до GATE:done без хвоста BUG:diagnose done без GATE:diagnose-review"` — эскалация needs-operator на restore/re-open, **не** nudge-комментарий |

То же разведение классов, если `GATE:diagnose-review` done и нет первой фазы хвоста (`TZ:patch` LIGHT / `TZ:stabilize` full). Не срабатывать на корректно завершённом графе (корень done **и** `GATE:done` done) / archived. Троттлинг operator-action отдельно от nudge (не чаще 1 на граф в тик). На четырёх мёртвых графах-прецедентах срабатывает ветка **раннее закрытие**, не «корень ещё жив».

Корень не complete'ится воркером до `GATE:done`. Закрытие корня — воркер после auto `GATE:done` (preflight exit 0 **достаточен**); отчёт AC уже в origin.

`GATE:take-into-work`, `GATE:plan-approve` и `GATE:done` **всегда создаются** (граф и idempotency key не ветвятся). Снятие: все три — **always auto** после артефакта (`ac-shown` / `architect-plan` / preflight 0). Auto-pass ≠ skip: карточка гейта есть, parents обязательны, работа фаз выполняется.

После `GATE:brief-closed` (кейсы с брифом): `kanban_create` корня `DEV/<slug>` + **полный** набор фаз кейса с parents **в том же create**. Любой TZ/HF `agent -p` без корня `DEV/<slug>` → **стоп** (не «по памяти чата»). Исключения: `BRF:*` в TG; одношаговый ответ; RESEARCH без DEV-корня. Unfold хвоста **после** `GATE:take-into-work` **запрещён**.

BUGFIX / BUGFIX-LIGHT — обычный полно-батчевый кейс: исключения двухшагового unfold **нет**. Классификация LIGHT/полный — на старте (оркестратор/Саша, AC-H10); уточнение LIGHT → полный тайл не меняет график в одном батче. Это не unfold после take-into-work.

### Режим «делай в 1 проход»

Триггер-фраза Саши: «делай в 1 проход».

После канона v0.4.0 фраза **не нужна**, чтобы гейты AC стали auto (вестигиальна / no-op для HITL):
- GATE:take-into-work — always auto (`auto-pass: ac-shown`) после показа AC-списка в origin;
- GATE:plan-approve — always auto (`auto-pass: architect-plan`), и без фразы;
- GATE:done — always auto после preflight exit 0 (достаточен) и отчёта AC в origin;
- GATE:diagnose-review — always auto после артефакта плана.

Что фраза по-прежнему означает (и только это):
1. Не skip фаз и не склейка PREFIX:фаза / ролей в один agent -p (GLOSSARY §5.2).
2. Корневой one-pass не плодит полный хвост карточек (правило C hermes-feature).
3. Если корень сам ведёт цикл: серия agent -p по ролям (grok → composer), не один промпт «ТЗ+код+тесты».
4. GATE:go / GATE:block-accept фраза не обходит. DX не склеивается в один `agent -p`.

Условия входа в «не плодить хвост»: мастер-ТЗ на диске; открытых вопросов нет; не обход diagnose-review.

Корневой one-pass = не создавать полный хвост. Это **не** «один `agent -p` на ТЗ+код+тесты». Склейка ролей запрещена.

### Preflight GATE:done **и** create (structural)

Скрипт (**реализовано 08.09**, контур B chain-enforcement; **17/17** pytest green; G1/G3/G4 — **target** v0.4.1, impl W1):

`~/WorkVault/Registries/pipeline_gate_done_preflight.py`

Тесты: `~/WorkVault/Registries/test_pipeline_gate_done_preflight.py`.

**Вызов:**
```
python3 ~/WorkVault/Registries/pipeline_gate_done_preflight.py \
  --slug <slug> --case DEV|CHANGE|CHANGE-LIGHT|BUGFIX|BUGFIX-LIGHT|RESEARCH|MIGRATION|DECOMM|SKILL-DEV|SKILL-CHANGE \
  --mode create|done [--flag-rev]
```

`--mode create` (G4, **до** первого TZ/HF `agent -p`): фазы канона кейса **есть** в графе (не обязаны `done`). Fail → `kanban_block` корня `kind=dependency`, воркеры не стартуют. Кто: оркестратор сразу после create-батча; сторож — при мутации детей.

BUGFIX / BUGFIX-LIGHT: `--mode create` на **первом** батче структурно требует полный граф по кейсу, включая хвост и `GATE:diagnose-review` с `parents=[BUG:diagnose]` (инвариант 9 + «Полный батч BUGFIX»). Повторной проверки после второго хода нет: второго хода unfold нет. Сторож `rule9_bugfix_broken_tail` — защитный, не требование до-разворота. `--mode done` по-прежнему требует полный набор кейса `done`. AC-H08: «полный батч» BUGFIX = один create-батч всего графа.

`--mode done` (как сейчас, воркер `GATE:done`): фазы **done** + артефакты + G3 git-proof. `--mode` по умолчанию = `done` (совместимость).

**Кто вызывает done-режим:** воркер `GATE:done` / `hermes-feature` **после** доставки отчёта AC в диалог Саши и записи маркера; fallback — `dev-pipeline-reliability`. Preflight **не** доставляет отчёт и **не** пишет в чат. `exit 0` → воркер **сам** `kanban_complete` (достаточно; не ждать фразу «готово»).

**Порядок воркера `GATE:done`** (доставка ≠ проверка; список AC ≠ отчёт AC):

1. Собрать отчёт `AC-###` → как тестировали (команда, лог/артефакт, результат).
2. Опубликовать его в **диалог Саши = origin-топик** графа (не ops-канал Monitoring `:7`, не Errors `:11112`, не DM). Если origin сам `:7` — дубля в другой топик не делать.
3. `kanban_comment` на карточку `GATE:done`: маркер `AC-delivered: dialog` (допустим хвост `chat=<id> msg=<id>`) **и** тело отчёта.
4. Запустить preflight — он лишь проверяет маркер + тело.
5. `exit 0` → `kanban_complete` воркером (preflight 0 **достаточен**, включая п.10–11 operator-hold / open-questions). Не `kanban_block` «ждать готово».
6. `exit ≠ 0` → comment чек-листа, `kanban_block`, complete запрещён. Operator-hold: reason `review-required: operator-action: <verb>`. Иначе чинить граф, не ждать Сашу.

Список AC (приёмка на `GATE:take-into-work`) и отчёт AC (доставка на `GATE:done`) — **разные артефакты**. Наличие AC-артефакта (якорь `AC-###` в comment/файле/body) **не** есть доставка.

**Проверки (`--mode done`):**
1. Граф `DEV/<slug>` существует.
2. Фазы GLOSSARY §2 / §5.2 done; auto-гейты (`take-into-work` / `plan-approve` / `done` / `diagnose-review`) — done или маркер `auto-pass:`; never auto (`go` / `block-accept`) — только done.
3. Артефакты: план на диске; в `*_TZ.md` нет «на диске: нет» / «ожидает HF:impl».
4. REV: карточка done **или** `flag-waived: Sasha` (явный skip любого кейса, GLOSSARY §5.2; + sonnet `session_id`, если прогон был).
5. Свёртка: один `session_id` на разных role/model → collapsed.
6. Маркер доставки: comment карточки `GATE:done` содержит `AC-delivered:` с непустым хвостом (канон `AC-delivered:\s+\S+`). Голый `AC-delivered:` — FAIL. Маркер только на `GATE:done` (не корень, не `GATE:take-into-work`, не `HF:test`). `tasks.result` GATE:done в момент preflight — не доказательство доставки.
7. Тело отчёта: comment `GATE:done` и/или файл `AC-report_<slug>*.md`. Не принимать список AC с `GATE:take-into-work`. Не считать наличие AC-артефакта доставкой. Не парсить формулировки AC **класса S**. Узкий анти-фикшн класса O: якорь `AC-###` + маркер ожидания (`ОЖИДАЕТ` / `НЕ выполнен` / `⏳`) **и** этот AC в operator-holds → FAIL даже при `AC-delivered:` (прецедент `t_07c4913c`).
8. **G3 git-proof (v0.4.1).** Если в графе есть `HF:impl`: каждый путь из `kanban_complete.metadata.changed_files`, лежащий внутри git-worktree, должен быть **закоммичен** (`git ls-files` знает файл **и** `git status --porcelain` по пути пуст). Untracked / modified-unstaged / staged-but-uncommitted → FAIL (инцидент «виртуальной» реализации). Нет `changed_files` при кейсе с `HF:impl` → FAIL, кроме comment `no-code-change: <reason>`. Пути вне git (vault ТЗ) — только наличие на диске. RESEARCH без `HF:impl` — skip G3.
9. **G2 context-used.** Карточки TZ/HF/BUG/REV в графе, которые звали `agent -p`, несут маркер `context-used:` (см. «Контекст-промпт»).
10. **operator-done (план done-gate: «п.8» относительно чеклиста v0.4.0 1–7).** Все `operator-holds` с `status=open` (comment корня / `GATE:take-into-work` / тег `depends: operator:<verb>` пакета) имеют парный `operator-done: <verb>` + `evidence:` на `GATE:done` или корне. Иначе FAIL `operator-hold не снят: <verb>`. Hold = fail preflight, не расширение `GATE_NO_AUTO_PASS`.
11. **open-questions empty (план done-gate: «п.9» относительно чеклиста v0.4.0 1–7).** Любой `Q-n` с `status=open` на корне → FAIL `висящий вопрос Q-n`.

**Проверки (`--mode create`):** п.1 + фазы канона **присутствуют** как карточки (не обязаны done) + `--case` ∈ закрытого списка 10. `MIG:block-k` / `GATE:block-accept` — опциональны на create (добавляются по плану миграции). SKILL-CHANGE: оркестратор фиксирует ветку CHANGE vs DECOMM в metadata корня `skill_change_branch=` до create.

| exit | Смысл |
|---|---|
| 0 | OK → create: можно стартовать воркеров; done: воркер complete `GATE:done` (достаточно) |
| 1 | провал чек-листа (граф / фазы / артефакты / REV / нет маркера или тела отчёта AC / G3 untracked / G2 нет context-used / operator-hold open / open-questions) |
| 2 | collapsed-chain или ошибка вызова |

`exit ≠ 0` → `GATE:done` запрещён; comment с чек-листом; `kanban_block`. Авто-крон preflight **не** ставится.

### off-board / retro-graph

Прецедент: exchange-contact-upsert 08.09 (работы шли без канонического графа; unarchive 07.09 нельзя).

- Off-board = **исключение**, не замена графа. Фазы, сделанные вне карточек: `kanban_create` retro-графа `DEV/<slug>` + complete + comment `done off-board, session ids`.
- Без audit (retro-create + comment) off-board запрещён.
- Любой TZ/HF `agent -p` без корня `DEV/<slug>` → стоп + оркестратор (не мягкое «создать HF если нет» из памяти чата).
- Исключения без DEV-корня: `BRF:*` в TG; одношаговый ответ; RESEARCH.

### Бэклог идей (ручной feed → `triage`)

Второе применение доски, не ветка `DEV/<slug>`. Отдельный профиль не нужен.

```
IDEA/<slug>                         корень бэклога (живёт, пока Саша не решил)
└─ IDEA:analyze                     inbox = статус triage на create;
                                    скилл сразу → ready (без decomposer)
                                    silent worker default → architect
                                    → kanban_comment (заключение)
                                    → blocked (ждёт Сашу)
```

Порядок:

1. Саша явно (фраза/команда, формулировка свободная, намерение «положить в бэклог / triage / разбери идею») даёт сырую заметку или указывает незакрытое исследование / ТЗ в разработке.
2. Оркестратор в чате: `kanban_create` корня `IDEA/<slug>` + `IDEA:analyze`. Посадка — статус `triage` (сырой inbox). Сразу в том же ходе скилл переводит `IDEA:analyze` в `ready` **без** decomposer (`auto_decompose: false` — иначе карточка зависнет в triage навсегда).
3. Dispatcher (уже silent OS-процесс) поднимает воркера `default`.
4. Воркер вызывает `agent -p --model cursor-grok-4.6-high` (архитектор), дорабатывает идею, кладёт заключение в `kanban_comment`, затем `kanban_block` (`review-required: заключение по идее, ждать Сашу`).
5. Когда Саша вспомнил — открывает доску, читает заключение. По желанию «берём в работу» (Telegram **или** дашборд) → `IDEA:analyze` complete; оркестратор создаёт граф `DEV/<slug>` обычного цикла (tz-workflow → hermes-feature), в comment/parents — ссылка на IDEA. Корень `IDEA/<slug>` → `done` или `archived`.
6. Если Саша не берёт в работу — карточка остаётся `blocked`; авто-эскалации нет.

Автокрон, который сам ищет незаконченный контекст (как DialogBacklog), **не** ставится этим ТЗ.

### Фазы ↔ скиллы

> **Модель в таблице ниже** — это модель **внутреннего** вызова `agent -p`, **НЕ** модель воркера канбана. **НЕ** передавай эти slug в `kanban_create --model` / `model=` на карточке. Воркер фазы = default Hermes (`model_override` NULL); роль (архитектор/ревизор/исполнитель) выбирается внутри воркера через `cursor-cli`.

| phase | Скилл / блок | Модель внутреннего `agent -p` (НЕ `kanban --model`) | Terminal action | Done-критерий карточки |
|---|---|---|---|---|
| `TZ:stabilize` | tz-workflow | — (чтение диска) | Зафиксировать path, `version`, `mtime` в metadata | metadata заполнена; для нового ТЗ — `tz_version=null` |
| `TZ:compress` | tz-workflow Шаг 0 | `deepseek-v4-flash-0731` (Hermes, без Cursor) | Компрессия по `tz-compressor-prompt.md`, без кэша | экстракт в `kanban_comment` + metadata `extract_chars` |
| `TZ:patch` | tz-workflow TZ-WRITE | `cursor-grok-4.6-high` | reuse-first, архитектура, драфт; `--resume` | драфт/анализ в comment или файле ТЗ (ещё не финал) |
| `REV:tz` | ревизор (опц.) | `claude-sonnet-5-medium` | слабые места ТЗ | comment с замечаниями |
| `TZ:finalize` | tz-workflow TZ-WRITE | `cursor-grok-4.6-high` | Запись `TZ/<Tool>/<Tool>_TZ.md` + `MAIN_TZ_INVENTORY.md` | файлы на диске проверены оркестратором (не self-report) |
| `GATE:take-into-work` | — | — | always auto (`auto-pass: ac-shown`); payload=AC-список в origin; показ ≠ ожидание | воркер после показа AC |
| `HF:compress` | hermes-feature Блок 0/1 шаг 0 | `deepseek-v4-flash-0731` (Hermes, без Cursor) | Снова компрессия с диска, без кэша | + сверка version/mtime |
| `HF:plan` | Блок 1А | `cursor-grok-4.6-high` | План разработки **и** тестирования: таблица `IAC-##` (`path`/`verify`/`depends`/`covers`) | план на диске / в comment; IAC покрывает AC пакета |
| `REV:plan` | ревизор (опц.) | `claude-sonnet-5-medium` | слабые места плана (в т.ч. покрытие IAC) | comment с замечаниями |
| `GATE:plan-approve` | Блок 1А completion | — | always auto (`auto-pass: architect-plan`); `HF:plan` обязателен | auto-complete (не HITL Саши) |
| `HF:backup` | Блок 5 | `composer-2.5` | `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` | путь бэкапа в metadata |
| `HF:impl` | Блок 2 | `composer-2.5` | Код по плану; запрет общего state | `changed_files`, без registry_touches |
| `HF:test` | Блок 3 | `composer-2.5` | Исполнитель **сам** гоняет `verify` IAC плана; отдельной роли тестировщика нет | `tests_run` / `tests_passed`; `metadata.iac_passed` |
| `HF:docs-handoff` | Блок 4 подготовка | `composer-2.5` | Текст скилла/ТЗ-секции **кроме** манифеста | metadata: что оркестратору внести в манифест |
| `ORCH:shared-state` | оркестратор Сирень | `deepseek-v4-flash-0731` (Hermes, без Cursor) | Манифест, digest/render, `restore-all-skills.sh` по списку | `--check-drift` без новых дыр по затронутым ключам |
| `GATE:done` | Блок 3 «completed» | — | always auto после preflight exit 0 (достаточен); доставка отчёта AC в origin **до** preflight; маркер `AC-delivered:`; payload=отчёт AC; показ ≠ ожидание | воркер после preflight 0 |
| `BUG:diagnose` | Блок 6В | `cursor-grok-4.6-high` | Read-only, `_fix_plan_YYYYMMDD.md` | план на диске |
| `IDEA:analyze` | tz-workflow (анализ идеи) | `cursor-grok-4.6-high` | Доработать сырую заметку; заключение в comment | comment с заключением + `blocked` до решения Саши; complete — только после «берём в работу» или явного отказа |
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


`kanban_create` для всех фаз-воркеров в таблице — **без** `--model` / `model=` (только `assignee=default`, skills по строке ниже).

**САНКТ-список предотвращения** (namespace моделей, прецедент `t_2c8ee3b2`):

| | |
|---|---|
| **С** (симптом) | HTTP 400 `must include upstream provider prefix`; Messages: 1 (0 tool calls); `rc=0`; диспетчер — `protocol_violation` |
| **А** (антипример) | `kanban_create(..., model=cursor-grok-4.6-high)` на `TZ:patch` → `t_2c8ee3b2`; тот же класс для любого `--model` / `model=` с Cursor-slug на create фазы-воркера |
| **Н** (namespace) | D1 модель карточки: `model_override` **NULL** или tutu `vendor/model`. D2 модель работы внутри: внутренний `agent -p --model` с Cursor-slug. Не путать. |
| **К** (канон-якоря) | `GLOSSARY.md` §3 / §5.2.10; таблица выше; запрет create в `tz-workflow` / `hermes-feature`; pitfall `kanban-worker`; развёртка — `kanban-dev-cases` + `cursor-cli` |
| **Т** (тест) | IAC-01..10 (`_fix_plan_20260925.md` §П.10; ops П.1 — оркестратор) |

Skills на карточке (`kanban_create(..., skills=[...])`):

- TZ-*: `tz-workflow`, `cursor-cli`, `cursor-task-context`
- HF-* / GATE после take-into-work: `hermes-feature`, `cursor-cli`, `cursor-task-context`
- RS:* / REV:report / MIG:* / DEC:*: `hermes-feature`, `cursor-cli`
- SK:preflight: только `hermes-feature`
- BUG:diagnose: `hermes-feature`, `cursor-cli`, `cursor-task-context`
- ORCH:shared-state: `hermes-feature`
- IDEA:analyze: `tz-workflow`, `cursor-cli`, `cursor-task-context`

## Канбан-шаги, которые вшить в скиллы

Не отдельный скилл «запусти канбан». Предпочтение Саши (cursor-task-context): триггеры в существующих скиллах, иначе забудет.

### `tz-workflow/SKILL.md` — новый раздел «Канбан-шаг»

После определения триггера (создание/доработка ТЗ) и **до** Шага 0:

1. Если графа ещё нет — после `GATE:brief-closed` **оркестратор** `kanban_create` корня `DEV/<slug>` + **полного** набора фаз кейса (TZ-WRITE + `GATE:take-into-work` + PLAN-IMPL-TAIL / LIGHT) с `parents` **в том же create**. Ключ на каждую фазу, D1 `model=NULL`. Затем **structural-preflight `--mode create`** (G4); fail → block корня, не стартовать воркеров. TZ `agent -p` без корня → стоп. Unfold хвоста позже **запрещён**. Архитектор **не** создаёт этот батч.
2. На каждом Шаге 0–4: heartbeat; по успеху — `kanban_complete` текущей фазы (metadata ниже); следующая сама станет `ready`.
3. Вопрос Саше по брифу/архитектуре — **только в TG** (`BRF:*` через оркестратора). **Не** `kanban_block(kind=needs_input)` на TZ/HF-фазах.
4. `TZ:finalize`: запись ТЗ + инвентарь — роль архитектора, не исполнителя HF.
5. После `TZ:finalize`: выдать AC-список в **диалог = origin-топик** (не ops `:7`, не `:11112`); затем auto-complete `GATE:take-into-work` (`auto-pass: ac-shown`). **Не** `kanban_block` wait. Показ AC ≠ ожидание **(класс S)**. Класс O не hold на take-into-work: код/тесты едут; hold срабатывает на `GATE:done`. Хвост уже в графе (батч п.1).
6. Ручной feed идеи: создать `IDEA/<slug>` + `IDEA:analyze` (посадка `triage` → сразу `ready`), не запускать DEV-граф, пока Саша не сказал «берём в работу» по заключению.
7. Снятие гейта: фраза в Telegram **или** факт unblock на дашборде — равнозначны; не требовать оба.
8. На каждом Шаге 0–4 (и на `TZ:finalize`): после `kanban_show` — freshness-gate; `TZ:finalize` пишет `MAIN_TZ_INVENTORY.md` только под `LOCK_EX` единого lockfile.

### `hermes-feature/SKILL.md` — новый раздел «Канбан-шаг»

1. Вход только если корень `DEV/<slug>` существует и `GATE:take-into-work` = **done/auto** (`auto-pass: ac-shown`). Иначе стоп + текст «take-into-work ещё не auto». Фраза Саши «берём в работу» **не** требуется.
2. Любой HF `agent -p` без корня `DEV/<slug>` → **стоп** + оркестратор. Не продолжать «по памяти чата» и не мягкое «создать HF если нет».
3. Блок 6В при триггере багфикса — **первый tool-шаг** `kanban_create` полного графа: корень `DEV/<slug>` + `BUG:diagnose` + `GATE:diagnose-review` + LIGHT/полный хвост в одном батче (инвариант 9 + «Полный батч BUGFIX»). После done DX поезд едет без второго unfold (`GATE:diagnose-review` уже `ready`). Ретро-корень запрещён. Корень не `kanban_complete` до создания хвоста и `GATE:done` (guard закрытия корня).
4. Перед первой строкой кода — чеклист Блока 2 остаётся; пункт «канбан: GATE:plan-approve = done/unblocked **или** auto-pass one-pass» добавляется.
5. `GATE:plan-approve`: always auto (`auto-pass: architect-plan`); `HF:plan` обязателен до гейта.
6. Блок 4: исполнитель = `HF:docs-handoff` (список правок манифеста в metadata). Запись манифеста = только `ORCH:shared-state`.
7. `GATE:done`: always auto после preflight exit 0 (**достаточен**); доставка отчёта AC в **диалог = origin-топик** **до** preflight (не ops `:7`, не `:11112`; если origin сам `:7` — дубля нет); затем comment с маркером `AC-delivered:` + тело; preflight проверяет маркер, не доставляет; payload=отчёт AC, не список AC с `GATE:take-into-work`; **не** `kanban_block` «ждать готово»; complete воркером.
8. Чек-лист фаз: **первый шаг любого воркера** (после `kanban_show`) — freshness-gate; при неактуальности — complete «неактуально» **или** `kanban_block(kind=dependency)` + сигнал оркестратору, не вслепую, не другой граф. Канон — секция «Freshness-gate и сериализация writers».
9. Сериализация writers общих файлов: `LOCK_EX` на `~/WorkVault/Registries/.shared-state.lock`; второй writer ждёт; RMW + `os.replace`. Параллельно — никогда. Writer-фаза не стартует, пока есть running writer тех же путей (defer/семафор — второй минимум).
10. Смена R5-канала (origin-routing): `HF:impl` **стоп**, пока не выполнен чеклист identity `DEV/tg-topic-duplicate` (раздел «Уведомления графа»). Не подписывать diagnose. ORIGIN на хвосте — копия с корня. Стопкран identity **не** переносить на слаг `dev-process-rework`.
11. **G5:** воркер HF не `kanban_create` кейсовый граф и не skip фаз. **G3:** перед complete `HF:test` / `GATE:done` — impl-файлы закоммичены. **G2:** `check --card` до complete.

### `cursor-cli/SKILL.md` — точечно

Единственный легальный `agent -p` по инструменту (`BUG:diagnose` / TZ-WRITE / HF-фазы): сначала `emit-prompt` (exit 0), затем:

```text
agent -p "$(cat /tmp/task.md)" -f --model <MODEL> --workspace <ABS_DIR> --resume <session_id> --output-format json
```

`/tmp/task.md` — **только** выход `pipeline_context_bundle.py emit-prompt`. Любой `agent -p` по инструменту в обход `emit-prompt` — запрещён. CLI `--force` / `--force-bypass` отсутствует. Обхода нет: скрипт/check блокируют старт всегда (решение Саши 26.09) для тройки путей (digest+GLOSSARY+ТЗ). После emit-prompt — comment с `context-used:` (G2). Перед complete TZ/HF/BUG/REV — `check --card` exit 0.

Запрет в пайплайне: `--continue` (берёт «последнюю сессию каталога», ломается при двух workspace). Лимит параллели: 2 процесса, деревья `--workspace` не пересекаются. `session_id` писать в `kanban_comment` сразу после первого вызова.

Для `IDEA:analyze` модель фиксирована: `cursor-grok-4.6-high`.

### `cursor-task-context/SKILL.md` — точечно

Первый шаг любого воркера с ТЗ: сверка `version`/`mtime` (см. ниже) — **часть freshness-gate** (после `kanban_show`; канон v0.2.7). Без кэша экстрактов — уже есть, повторить как обязательный чеклист воркера.

3-слойная подача = `pipeline_context_bundle.py emit-prompt` (абс-пути digest + GLOSSARY + мастер-ТЗ в `/tmp/task.md`), **не** копии документов в workspace. Skills `BUG:diagnose` включают этот скилл (v0.3.6).

### Контекст-промпт (`emit-prompt`) — v0.3.6, усиление v0.4.1 (G1/G2), наблюдаемость G1 п.3 — v0.4.2

Скрипт `~/WorkVault/Registries/pipeline_context_bundle.py` (класс `pipeline_gate_done_preflight.py`: exit 0/1/2; ядро канбана не патчить). Реализация усилений G1/G2 — `HF:impl`, не эта запись.

Перед любым `agent -p` по инструменту (`BUG:diagnose` / TZ-WRITE / HF-фазы / `REV:*`):

```
python3 ~/WorkVault/Registries/pipeline_context_bundle.py emit-prompt \
  --tool <Name> --card <id> \
  --task-file <abs path фазы> \
  --out /tmp/task.md
```

Только при exit 0: `agent -p "$(cat /tmp/task.md)" …`. `--out` не писать при неполной тройке. Диск-кэша экстракта нет (экстракт — comment/сессия или «прочитай сам» по abs-пути). CLI `--force` / `--force-bypass` отсутствует. Обхода нет: скрипт/check блокируют старт всегда (решение Саши 26.09).

**G1 — сверх наличия файлов (v0.4.1, target; наблюдаемость п.3 — v0.4.2).** `emit-prompt` exit 1, если любое:

1. `--card` не найден в `kanban.db`, **или** карточка не достижима от корня `DEV/<slug>` / `IDEA/<slug>` (обход parents). Исключения без DEV-корня: `BRF:*` в TG; одношаговый ответ; RESEARCH (`RS:*` от своего корня, если граф RESEARCH без `DEV/`).
2. В body/metadata карточки есть `tz_version` / `tz_mtime` и они **расходятся** с YAML `version:` / `st_mtime` мастер-ТЗ на диске (тот же drift, что «Актуальность ТЗ»).
3. Для фаз **после** `HF:impl` (`HF:test`, `HF:docs-handoff`): G3 git-proof уже красный (untracked / uncommitted impl) — не стартовать тест и не стартовать `HF:docs-handoff` «по виртуальному коду». Наблюдаемо: `emit-prompt --card` на живой карточке `HF:test` / `HF:docs-handoff` при красном G3 → **exit 1**; `agent -p` этой фазы **не** вызывается. Смоук — AC-H05b (фикстура kanban.db). Пункты 1–2 — AC-H05; G3 на `GATE:done` — AC-H07 (другая точка: финал, не старт).

В `--out` emit-prompt добавляет машинный блок (воркер копирует в `kanban_comment` **до** `agent -p`):

```
context-used:
  card: <id>
  root: DEV/<slug> | IDEA/<slug>
  phase: <PREFIX:фаза>
  tz_version: <semver|none>
  tz_mtime: <ISO UTC>
  emitted_at: <ISO UTC>
```

Режим `check --card <id>`: нет тройки → `kanban_block`, `agent -p` не вызывать. **G2 (v0.4.1):** нет блока `context-used:` с `card` = этот id и `tz_version` = диск → exit 1. `kanban_complete` TZ/HF/BUG/REV **запрещён** при `check` ≠ 0.

Доказательство «воркер вызвал emit-prompt» = наличие `context-used:` на карточке **до** complete. Цитаты из ТЗ не требуются (не верифицируются скриптом); `REV:tz` / `REV:plan` ловят содержание, расходящееся с текущей version.

## Уведомления графа

Рабочий канал wake/notify кейса — колонка **`kanban_notify_subs.thread_id`**, не body/metadata карточки. Wake собирает `SessionSource` только из строки подписки (`gateway/kanban_watchers_notifier.py`). Карточка без подписки с нужным `thread_id` = тишина или чужой топик.

Используется **штатный** `hermes kanban notify-subscribe`. Ядро (`kanban_db.py`, `kanban_db_notify.py`, `TERMINAL_KINDS`, `kanban_tools.py` `_maybe_auto_subscribe`) **не трогать** — auto-sub на create **переиспользуем**, скилл выравнивает явный R5-subscribe с origin и снимает stray.

### Старое → новое (канал R5, перекрытие 26.09 / v0.3.8)

| Старое (п.15 / т.3 24.09, v0.3.0–0.3.7) | Новое (эта секция) |
|---|---|
| Репорты канбана только Monitoring `:7` | Кейс/граф → **origin-топик инициатора**; `:7` не хардкодить |
| Snippet `notify-subscribe` без `--thread-id` | Обязательны `--thread-id <ORIGIN> --chat-type group`; без `--thread-id` **запрещено** |
| Подписать все `task_id` батча / багфикс «обе» / все фазы хвоста | Набор R5 **не менять**: только корень + AC/HITL-гейты (таблица ниже). Не расширять обратно |
| Канал по умолчанию — Monitoring `:7` | Канал = origin (`thread_id` подписки); набор карточек тот же |
| AC-список / AC-отчёт «не Monitoring :7» (негатив) | Диалог Саши = **origin-топик** (позитив). Если origin сам `:7` — дубля нет |
| Фоллбек неизвестного origin → `:7` | **SILENCE**: subscribe не вызывать; `:7` не подставлять |

### Три канала экосистемы (не смешивать)

| Канал | thread | Кто пишет | Кто не пишет |
|---|---|---|---|
| **Кейс / граф** | origin | R5 `notify-subscribe` | кроны, ErrorBus |
| **Ops / мониторинг кронов** | Monitoring `:7` | `jobs.json` `deliver`, штатный cron-пинг | кейсовый диалог пайплайна |
| **Техника ошибок** | Errors `:11112` | ErrorBus `report_error.sh` | kanban notify, AC-список, AC-отчёт |

Явное указание Саши («пиши в :N» / «канал = …») переопределяет канал **этого** графа. Дубль кейса в `:7` запрещён, если origin другой. Каталог 7 топиков (TelegramGroupTopics: 1/3/5/6/7/8 + Errors 11112) — предпочтение, не фильтр: origin вне каталога (кроме `:11112`) разрешён.

### Резолв origin

Идентификатор канала кейса: `(platform=telegram, chat_id=-1004300127777, thread_id=ORIGIN, chat_type=group)`.

```
resolve_origin(kind=root|child, root_id):
  1. Явный override Саши на этом графе («пиши в :N» / «канал = …») → N.
  2. kind=child: notify-list(root_id) → единственная telegram-подписка
     на -1004300127777 с непустым thread_id ∉ {11112}. Нет такой → SILENCE.
  3. kind=root: env HERMES_SESSION_PLATFORM=telegram
     AND HERMES_SESSION_CHAT_ID=-1004300127777
     AND HERMES_SESSION_THREAD_ID непустой
     (пустая строка thread_id = отсутствие origin → не шаг 3, а SILENCE)
     AND thread_id ≠ 11112
     AND chat_type ∉ {dm, direct, private}
     AND chat_id ≠ 400307920
     → thread_id (каталог 1/3/5/6/7/8 предпочтителен; origin побеждает,
       если это реальный топик той же группы, кроме Errors).
  4. DM / неизвестно / CLI / Cursor без TG-env / Errors :11112 → SILENCE.
  5. SILENCE: notify-subscribe НЕ вызывать; :7 НЕ подставлять.
```

Origin резолвится **на корне**. Поздние `GATE:*` часто создаёт воркер без `HERMES_SESSION_THREAD_ID` origin'а. Для детей канал = **копия `thread_id` с подписки корня**, не текущий env.

`HERMES_SESSION_CHAT_TYPE=thread` на корне **нормализовать в `group`** в команде подписки (колонка), не копировать в sub.

### Когда подписывать (набор R5 — не расширять)

Сразу после `kanban_create` (в том же ходе) — **только** выбранные id. Наследования по `parents` нет. **Не** подписывать все `task_id` батча. **Не** подписывать `BUG:diagnose` («багфикс — обе» — leftover, снят).

| Карточка | Подписка | `delivery-mode` |
|---|---|---|
| Корень `DEV/<slug>` или `IDEA/<slug>` | да | `notify+wake` |
| `GATE:take-into-work`, `GATE:done` | да | `notify+wake` (**показ** AC, не hold) |
| `GATE:go`, `GATE:block-accept`, `IDEA:analyze` | да | `notify+wake` |
| `TZ:*`, `HF:*`, `REV:*`, `BUG:diagnose`, `ORCH:*`, `RS:*`, `GATE:plan-approve`, `GATE:diagnose-review` | **нет** | — |

Багфикс-батч: подписать **только корень** `DEV/<slug>`, не `BUG:diagnose`. Ручной feed: корень `IDEA/<slug>` + `IDEA:analyze` (это набор R5, не «все фазы»). После `GATE:take-into-work` на хвосте: ORIGIN **с корня**, не из сессии воркера. `notify+wake` на AC-гейтах = **показ** списка/отчёта в origin **до** auto-complete, не hold поезда.

### Фиксированный контракт

```bash
hermes kanban notify-subscribe <task_id> \
  --platform telegram --chat-id -1004300127777 --thread-id <ORIGIN> \
  --chat-type group \
  --delivery-mode notify+wake --notifier-profile default
```

`<ORIGIN>` обязателен. Команда **без** `--thread-id` **запрещена** (пустой thread → фактически General `:1`).

DM по умолчанию не подписывать. Дублирование в личный чат `400307920` не выполняется.

### SILENCE-unsubscribe (после каждого create R5-карточки)

Ядро `_maybe_auto_subscribe` при create из gateway-сессии может записать env-канал (в т.ч. DM) **до** явного R5. Скилл выравнивает, ядро не патчить.

После create R5-карточки:

1. `hermes kanban notify-list <task_id>`.
2. Если origin = SILENCE — `notify-unsubscribe` **все** telegram-подписки этой задачи (включая auto-sub DM `400307920` и пустой thread). Иначе [AC-005](#AC-005) (тишина из DM) не сойдётся.
3. Если origin есть — оставить **ровно одну** telegram-строку `(chat_id=-1004300127777, thread_id=ORIGIN, chat_type=group, mode=notify+wake)`; снять прочие (пустой thread → General, другой thread, DM, `:11112`).
4. Не снимать подписку на ORIGIN. Не подписывать DM «на всякий случай». Не слать кейс в `:11112`.

Исторические dual-sub (`''` + `7/thread`) **не** массово мигрировать на угаданный origin — отдельная команда Саши. Identity-duplicate чистит только `chat_type=thread` → `group`.

### Прекондиция identity (`HF:impl` origin-routing)

Реализация R5-origin в скиллах **не стартует**, пока не снят identity-прекондицион `DEV/tg-topic-duplicate`. Смена канала до фикса `build_session_key` / wake размножит вилки `telegram:thread:…` на каждый origin-топик, не только `:7`.

**Стопкран identity жив только для origin-routing / `DEV/tg-topic-duplicate`.** На слаг `DEV/dev-process-rework` **не** переносить.

Корень duplicate `done` при живом хвосте **не** трактовать как «identity закрыт». Смотреть `HF:impl` / `HF:test` / `GATE:done`.

**Предпочтительно:** карточка `GATE:done` графа `DEV/tg-topic-duplicate` = `done`. Ускоренный порог (`HF:test` + П.1–П.3 того ТЗ + «поднимай») — только если Саша явно сказал не ждать HITL done.

Чеклист на входе `HF:impl` этого канона (воркер **стоп**, если любой пункт ложен → `kanban_block(kind=dependency, reason="wait DEV/tg-topic-duplicate identity + поднимай")`):

1. `build_session_key(TELEGRAM, chat_type='thread', thread_id=N)` → слот `:group:`, не `:thread:`.
2. Wake: TELEGRAM + `thread_id` → `SessionSource.chat_type=='group'`.
3. `kanban_notify_subs`: 0 строк `chat_id='-1004300127777' AND chat_type='thread'`.
4. Нет живой вилки `telegram:thread:-1004300127777:*` в `state.db`.

Не начинать impl «под честное слово». Не origin-subscribe «уже сейчас с `chat_type=group`» в обход duplicate: auto-sub всё равно запишет env `chat_type=thread`, пока identity не влит и gateway не поднят («поднимай» — только на графе duplicate). Gateway из этого плана не рестартовать.

### Какие события

Только ключевые терминальные (по `TERMINAL_KINDS` уведомителя): `completed`/`GATE:done`, `blocked`, `gave_up`, `crashed`, `timed_out`. Не каждую фазу графа — это шум. Список `TERMINAL_KINDS` не менять.

### Бэкап при merge upstream

Перед merge upstream — бэкап `~/.hermes/kanban.db` в канон бэкапа (рядом с `config.yaml`: `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`), т.к. апстрим может менять схему `kanban_notify_subs`/`TERMINAL_KINDS`/`delivery_mode`. См. риск «Канбан-уведомитель дрейфует при merge upstream».

## Гейты HITL

Канон v0.4.0 **перекрывает** v0.3.2 «ровно две точки never auto». Карточки гейтов **остаются** (аудит, `parents`, preflight, R5-показ). Меняется семантика, не имя фазы.

**Never auto (кризисный HITL Саши):** `GATE:go` («удаляй»), `GATE:block-accept` (приём блока миграции), IDEA `blocked` до «разбери» / отказа, кризис-block корня (`review-required: crisis:`).

**Always auto после артефакта (не hold класса S):** `GATE:take-into-work` (`auto-pass: ac-shown` после AC-списка в origin), `GATE:plan-approve` (`auto-pass: architect-plan`), `GATE:done` (preflight exit 0 **достаточен** — в т.ч. п.10–11 operator-hold / open-questions — + отчёт AC в origin), `GATE:diagnose-review` (после `_fix_plan_*.md` или непустого body `BUG:diagnose`).

**Показ AC ≠ ожидание (класс S).** `notify+wake` на `GATE:take-into-work` / `GATE:done` — показ в origin **до** auto-complete, не hold. Фраза «берём в работу» / «готово» / снятие с дашборда на этих гейтах — идемпотентный no-op, если гейт уже done.

**Hold класса O — не never-auto гейт и не «ждать готово».** `review-required: operator-action:<verb>` на корне или `GATE:done` — **не** auto-complete (fail preflight → `kanban_block` с этим reason). Не путать с дефектом «ждать готово»: фраза Саши на AC-гейтах по-прежнему no-op; набор never auto (`go` / `block-accept`) **не** расширять. `GATE_NO_AUTO_PASS` operator-hold не включает: hold = exit 1 preflight.

| Канал | Где действует | Кто пишет в канбан |
|---|---|---|
| Telegram | кризисные гейты; бриф `BRF:*`; IDEA «разбери» | Сирень: `kanban_comment` + `kanban_unblock` / `kanban_block` корня при кризисе |
| Дашборд канбана | те же кризисные гейты | сам дашборд / API; Сирень не обязана дублировать фразу |
| Воркер (auto) | AC-гейты и diagnose-review | `kanban_complete` после артефакта |

| Гейт | Механика | Снимает |
|---|---|---|
| Вопросы брифа / архитектуры | бриф в TG (`BRF:*`), не карточка; **запрет** `needs_input` на TZ/HF | Саша отвечает в Telegram |
| AC-список (ТЗ) | `GATE:take-into-work`: карточка-узел; payload=AC в origin; **always auto** | воркер после показа (`auto-pass: ac-shown`) |
| План 1А | `GATE:plan-approve` — always auto | auto (`auto-pass: architect-plan`) |
| Ревью диагноза 6В | `GATE:diagnose-review` — карточка обязательна; **always auto** после артефакта плана | воркер (не фраза Саши) |
| Заключение по идее | `IDEA:analyze` → `blocked` после comment | «разбери» / «берём в работу» **или** явный отказ — HITL бэклога, не DEV-поезд |
| AC-отчёт | `GATE:done` always auto; preflight exit 0 **достаточен** (в т.ч. operator-holds сняты, open-questions empty); payload=отчёт AC | воркер после preflight 0 |
| Operator-hold (класс O) | `review-required: operator-action:<verb>` на корне или `GATE:done`; **не** auto-complete; не «ждать готово» | оркестратор после **факта** (`operator-done:` + evidence) |
| Удаление / блок миграции | `GATE:go` / `GATE:block-accept` | **never auto**; фраза / дашборд |
| Кризис | `kanban_block` **корня** `review-required: crisis:` | Саша решает; поезд стоит |

Шаблон блока ревью (кризис / IDEA): сначала `kanban_comment` со structured JSON, потом `kanban_block(reason="review-required: …")`. На auto-гейтах AC **не** ставить `review-required` wait. Повторный block с тем же reason уходит в `triage` — для кризисных гейтов: не re-block, ждать.

### Триггер «делай в 1 проход»

Фраза целиком: **«делай в 1 проход»**. Enum `one_pass` — вестигиален для снятия AC-гейтов (они и так auto). Не схлопывает фазы в один `agent -p`. Не обходит `GATE:go` / `GATE:block-accept`.

## Актуальность ТЗ

1. `TZ:stabilize` (и повторно каждый HF-воркер) читает с диска YAML `version:` и `mtime` (`st_mtime` ISO UTC) мастер-файла.
2. Значения пишутся в body/metadata карточки: `tz_path`, `tz_version`, `tz_mtime`.
3. Экстракт компрессора живёт только в comment/сессии. Диск-кэша нет.
4. Расхождение диска с карточкой → comment «TZ drift: disk version=… mtime=… card version=… mtime=…» + `kanban_block(kind=dependency, reason="TZ master changed on disk")`.
5. Mid-flight bump (Саша/архитектор дописали секцию, version++):
   - `hermes kanban reclaim <running_id>` (или tool-эквивалент);
   - comment на reclaimed: «не retry этой карточки, TZ bumped»;
   - новая `TZ:stabilize` с актуальными version/mtime;
   - **новая** child той же phase с `parents=[новая stabilize + остальные неизменные parents]`;
   - старую карточку не `kanban_complete` как успешную реализацию — `archived` или `done` с summary `superseded`.

## Владелец общего state

Запрещено исполнителям (`HF:impl`, `HF:test`, `HF:docs-handoff`, Cursor `--workspace` на USERTOOLS/skills):

- `~/WorkVault/Registries/EcosystemManifest.json` (+ `.render.md` / `.digest.md` как производные)
- `~/WorkVault/Registries/entities.json`
- `~/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md` — исключение: пишет `TZ:finalize`
- `~/.hermes/.env`
- `~/.hermes/cron/jobs.json`
- запуск `restore-all-skills.sh`
- единый lockfile `~/WorkVault/Registries/.shared-state.lock` (не содержимое реестров; только inode для `flock`)

Исполнитель в `kanban_complete.metadata` обязан отдать:

```json
{
  "changed_files": ["..."],
  "registry_touches": [],
  "manifest_hints": ["tools.<key> fields to set"],
  "skills_to_sync": ["tz-workflow"],
  "tz_version": "0.1.0",
  "tz_mtime": "2026-09-05T12:00:00Z",
  "cursor_session_ids": ["..."]
}
```

Если `registry_touches` непустой — карточка не complete, а `kanban_block(kind=capability, reason="executor touched shared state")`.

`ORCH:shared-state` стартует только когда parents `done`. Писатели перечисленных путей (в т.ч. `TZ:finalize` → инвентарь; кросс-граф) — **строго по очереди** через advisory `LOCK_EX` на единый lockfile (v0.2.7); `max_in_progress_per_profile=1` сам по себе гонку кросс-графа не закрывает.

## Параллельные `agent -p`

Внутри **одной** running-карточки, не два kanban-воркера:

- максимум 2 фона;
- разные `--workspace` на непересекающиеся деревья (пример: `USERTOOLS/Foo` и `USERTOOLS/Foo/tests` — пересекаются, **нельзя**; `USERTOOLS/Foo` и `hermes-workspace/skills/productivity/bar` — можно);
- каждый вызов с `--resume <id>` своей сессии;
- `--continue` запрещён;
- промпт файлом (`-p "$(cat /tmp/task.md)"`), не инлайн (pitfall gateway-guard); `/tmp/task.md` — **только** выход `emit-prompt` (exit 0);
- пока ждут — `kanban_heartbeat` не реже раза в час (иначе reclaim по `dispatch_stale_timeout_seconds=14400`).

## Протокол воркера (обязательный порядок)

1. `kanban_show()` (статус мог смениться: blocked/archived → стоп).
2. **Freshness-gate** (любая карточка; канон — секция ниже). Если неактуально — complete с summary «неактуально» **или** `kanban_block(kind=dependency)` + сигнал оркестратору; **не** HITL-wait Саши; **не** выполнять шаг вслепую; **не** выбирать другой кейс/граф.
3. Сверка TZ version/mtime, если в body есть `tz_path` (вход freshness-gate; деталь — «Актуальность ТЗ»).
4. `cd` в `$HERMES_KANBAN_WORKSPACE` / указанный `--workspace`.
5. Работа шага. Перед любым `agent -p` по инструменту — `emit-prompt` (см. «Контекст-промпт», G1). Скопировать блок `context-used:` в `kanban_comment` **до** `agent -p` (G2). Heartbeat на длинных `agent -p`. Writer общих файлов — только под `LOCK_EX` единого lockfile; второй writer ждёт.
6. Не `delegate_task` вместо `kanban_create`. **Не** `kanban_create` кейсового графа / не менять `--case` / не skip обязательных фаз (G5). Расхождение с каноном → `kanban_block` + сигнал оркестратору.
7. Финал: `check --card` exit 0 (G2), затем `kanban_complete` **или** `kanban_block`. Выход без них = `protocol_violation`. Complete при `check` ≠ 0 запрещён.
8. `created_cards` — только id reclaim-замены той же phase из return текущего прогона (не новые фазы кейса).

## Freshness-gate и сериализация writers общих файлов (v0.2.7)

Норматив 24.09.2026 (постановка Саши; прецедент анализа `t_eba18cd9`, 23.09). Патч скиллов и lock-скрипт **не** входят в эту запись ТЗ — волны W1–W2. Классификация LIGHT vs полный **не** зашита статически в этом ТЗ: семейство кейса — на старте (Саша+оркестратор); LIGHT — оркестратор (для BUGFIX — на старте, выбранный хвост в том же create-батче, не перепись после DX); архитектор не классифицирует граф.

Этот раздел **перекрывает** постоянный режим сериализации v0.2.0–0.2.6, где `max_in_progress_per_profile=1` был единственной защитой общего state. Кап `max_in_progress_per_profile=3` **оставить**. Единый последовательный пул (`per_profile=1`) — **только временный рубильник**. Постоянно: параллель disjoint-работы + сериализация writers общих файлов через advisory flock.

### Freshness-gate

Первый шаг **любого** воркера канбан-карточки (TZ / HF / ORCH / BUG / IDEA / GATE — после `kanban_show()` и **до** работы шага):

1. Статус карточки и графа: `blocked` / `archived` / `done` / superseded → стоп, не работать.
2. Не решена ли задача уже другими правками (диск vs body/metadata: `tz_version` / `tz_mtime`, listed files, план, фактический diff).
3. Не изменились ли условия/файлы задачи (включая «Актуальность ТЗ»: `version`/`mtime` мастер-ТЗ).
4. Карточка не заменена reclaim / новой child той же phase.

Вердикт:

| Исход | Действие |
|---|---|
| Актуальна | продолжать протокол воркера |
| Явно неактуальна / уже сделана | `kanban_complete` с summary «неактуально» (это не успех реализации) |
| Неясно, нужна ли ещё | complete «неактуально» **или** `kanban_block(kind=dependency)` + сигнал оркестратору; **не** HITL-wait Саши; **не** другой кейс/граф. `needs_input` на TZ/HF запрещён |

**Запрет:** выполнять работу карточки вслепую при провале freshness-gate.

Вшить при реализации: «Протокол воркера» (шаг после `kanban_show`); чек-лист фаз `hermes-feature` / `tz-workflow` / `cursor-task-context`.

### Сериализация writers общих файлов

**Правило:** шаги/воркеры, пишущие в общие файлы, идут **строго по очереди**. Параллельно — **никогда**. Второй writer **ждёт**, не затирает.

Дыра, которую закрыть первой (`t_eba18cd9`): кросс-графовая запись манифеста/инвентаря без lock.

Единый блокирующий file-lock (не плодить второй):

| Что | Путь |
|---|---|
| Lockfile | `~/WorkVault/Registries/.shared-state.lock` |
| Скрипт-замок | `~/WorkVault/Registries/pipeline_shared_state_lock.py` (stdlib: `fcntl.flock(..., LOCK_EX)`; аналог `pipeline_gate_done_preflight.py`; не USERTOOL и не новая сущность экосистемы) |

Механика:

- Advisory `LOCK_EX` на единый lockfile на **весь** read-modify-write защищаемого пути.
- Второй writer блокируется на `flock`, не пишет в обход, не «мержит руками».
- После мутации — атомарный `os.replace` (tempfile в том же каталоге → replace).
- Crash/kill владельца fd снимает flock (OS); pid-steal **не** изобретать. Подозрение на зависший holder → HITL, не `rm` lockfile вслепую.
- Чистый read без последующей записи lock не обязан; любой RMW — обязан.

Защищаемые пути (писатели: `ORCH:shared-state`; `TZ:finalize` → инвентарь; чат Сирени, если пишет те же файлы):

- `~/WorkVault/Registries/EcosystemManifest.json`
- `~/WorkVault/Registries/EcosystemManifest.render.md`
- `~/WorkVault/Registries/EcosystemManifest.digest.md`
- `~/WorkVault/Registries/entities.json`
- `~/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md`
- запуск `restore-all-skills.sh`
- `~/.hermes/.env`
- `~/.hermes/cron/jobs.json`

Не защищает (параллель disjoint при капе 3 разрешена): деревья разных USERTOOLS, патч скилла вне restore, master-ТЗ одного инструмента (кроме инвентаря).

Второй минимум (грубее flock, **не вместо**): перед запуском writer-фазы (`TZ:finalize`, `ORCH:shared-state`) — defer/семафор, если уже есть running writer тех же путей. Ждать complete / снятия lock; второго writer не стартовать.

`max_in_progress_per_profile=1` как постоянная архитектура этим разделом **запрещён**; допустим только как временный рубильник.

### Куда вшить при реализации (не эта фаза)

- `hermes-feature/SKILL.md`: чек-лист фаз — первый шаг воркера = freshness-gate; секция сериализации writers (lock + список путей + `os.replace`).
- `tz-workflow/SKILL.md`: freshness-gate в протокол Шагов 0–4; `TZ:finalize` держит `LOCK_EX` на инвентарь.
- `cursor-task-context/SKILL.md`: freshness-gate ⊇ сверка `version`/`mtime`.
- Служебный скрипт + тесты в `~/WorkVault/Registries/` (тот же класс, что `pipeline_gate_done_preflight.py` / `pipeline_hf_plan_diskfact.py`).

## Что менять в файлах (атомарные шаги реализации)

Реализация скиллов/скриптов — волны W1–W2 после этого канона (v0.4.0). Порядок:

1. Бэкап `~/.hermes/config.yaml` в `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/`.
2. Выставить ключи `kanban:` и добавить toolset `kanban` (таблица конфигурации). Gateway не рестартовать.
3. Раздел «Канбан-шаг» + чеклист в `tz-workflow/SKILL.md` (граф DEV, авто-проход «1 проход», dual-HITL, ручной `IDEA:*`); bump version скилла.
4. То же в `hermes-feature/SKILL.md` (включая 6В, ORCH:shared-state, auto-pass `GATE:plan-approve`; `GATE:done` auto после preflight 0; полный граф уже в батче, без unfold; без корня → стоп).
5. `cursor-cli/SKILL.md` + `references/cursor-cli-patterns.md`: `--workspace`, запрет `--continue` в пайплайне, модель `cursor-grok-4.6-high` для `IDEA:analyze`.
6. `cursor-task-context/SKILL.md`: чеклист сверки version/mtime.
7. `restore-all-skills.sh` (карточка ORCH, не исполнитель).
8. Запись `tools.dev_kanban_pipeline` (категория `infra_service`) в `EcosystemManifest.json` + `--render` / `--digest` — карточка ORCH после скиллов.
9. Смоук без живой разработки: создать тестовый граф `DEV/_smoke-train/...`, проверить `todo→ready` по parents, auto take-into-work после показа AC, auto done после preflight 0; never auto только `GATE:go` / `GATE:block-accept`; карточку `IDEA/_smoke` (triage→ready→comment→blocked); отсутствие карточек на однострочном вопросе; затем archive тестовых карточек. Не смоукить на боевых слагах выходных.
10. Не ставить кроны (в т.ч. автосбор незаконченного контекста).
11. `hermes-feature/SKILL.md`: в чек-лист фаз — freshness-gate как первый шаг воркера (после `kanban_show`); новая секция сериализации writers общих файлов (`LOCK_EX`, lockfile, `os.replace`, defer writer-фазы). Bump version скилла.
12. Служебный скрипт-замок `~/WorkVault/Registries/pipeline_shared_state_lock.py` + lockfile `~/WorkVault/Registries/.shared-state.lock` + тесты (второй writer ждёт; нет lost-update на concurrent RMW; crash снимает flock). Не плодить второй lockfile. Аналог `pipeline_gate_done_preflight.py`.
13. `tz-workflow/SKILL.md` + `cursor-task-context/SKILL.md`: freshness-gate в протокол воркера; `TZ:finalize` пишет инвентарь только под `LOCK_EX`.
14. **Slug-guard (кейс 1, 24.09):** перед `kanban_create` графа `DEV/<slug>` — проверка активного графа по слагу (карточки в `todo|ready|running|blocked`, не `done`/`archived`). Дубликаты графа на один слаг запрещены (прецедент pfs-notify-link-unprocessed). При совпадении — reuse существующего графа; при неоднозначности — `kanban_block` с причиной (не создавать параллельный граф). Вшить в `tz-workflow` («Вход триггера») и `hermes-feature` («Вход HF-ветки»).
15. **Канал уведомлений (т.3/кейс 2, 24.09) — перекрыт 26.09 / v0.3.8:** контракт подписки графа → origin-топик инициатора (`-1004300127777`, `--thread-id <ORIGIN> --chat-type group`); без `--thread-id` команда **запрещена**; `:7` не хардкодить как канал кейса. Реализация R5-origin в скиллах — **после** identity `DEV/tg-topic-duplicate` (стоп-кран на `HF:impl`). Monitoring `:7` = ops/cron; Errors `:11112` не кейс.
16. **v0.4.0 поезд:** вшить always auto `GATE:take-into-work` / `GATE:done` / `GATE:diagnose-review` + полный батч графа в `tz-workflow` и `hermes-feature`. Never auto только `go` / `block-accept`. (W2, не эта запись.)
17. **Валидация только архитектором (т.2/кейс 5, 24.09):** правило «Сирень не предлагает своё мнение, рекомендации только от архитектора» в «Правила автономии»/«Модели» `tz-workflow` и Блок 0/1А `hermes-feature`. **Содержание** — архитектор; **ход процесса** — оркестратор (v0.4.1 G5). Не путать.
18. **v0.4.1 G1–G5 (W1, не эта запись):** `pipeline_context_bundle.py` — принадлежность `--card` графу, сверка version/mtime, блок `context-used:`; `check` требует маркер. `pipeline_gate_done_preflight.py` — `--mode create|done`, `--case` на 10 кейсов, G3 git-proof. Скиллы `tz-workflow` / `hermes-feature` / `cursor-cli` / `cursor-task-context` / `kanban-dev-cases`: оркестратор строит граф; архитектор не create-батч; `check` до complete; commit impl до `HF:test`/`GATE:done`. GLOSSARY v0.2.12 уже в этой записи.

## Критерии приёмки (AC / IAC) — канон v0.3.2

> **Перекрыто v0.4.0** в части HITL never auto на `GATE:take-into-work` / `GATE:done` и «ровно две точки». Слой AC/IAC (`AC-###` / `IAC-##`), набор R5-карточек, запрет sdd-writer — живы. Норматив гейтов штатного поезда — секция «Поезд — канон v0.4.0» сразу после этой. Левая колонка таблиц ниже — история.

Норматив этой секции — **принятые решения Саши 25.09.2026** (история). Источник: архитектурный анализ R1–R5 + идеи `IDEA/bk-178` (I1/I2/I3); sdd-writer целиком **не** ставится. Реализация скиллов — волны W1–W2, не эта запись.

**Старое → новое (перекрытие до HF; каркас фаз GLOSSARY §5.1/§5.2 не ломается — фазы не добавляются и не удаляются):**

| Старое (до правки скиллов/GLOSSARY) | Новое (эта секция) |
|---|---|
| «Решения Саши» п.8: one-pass auto `GATE:take-into-work` / `GATE:plan-approve` / `GATE:done` | auto только `GATE:plan-approve`; take-into-work и done — never auto |
| «Решения Саши» п.9: пошаговый HITL плана | `GATE:plan-approve` always auto; Саша план не согласовывает |
| «Решения Саши» п.16 / «Гейты HITL»: багфикс авто take-into-work (требование 4) | требование 4 **отменено**; take-into-work HITL по AC и для BUGFIX |
| «Уведомления графа»: подписать все `task_id` батча, единый `notify+wake` | подписка не на все фазы; `notify+wake` — корень + HITL-гейты AC/решения |
| «Критерии успеха»: auto take-into-work / HITL плана / auto done | перекрыто этой секцией |
| «Решения Саши» п.15 / v0.3.0 т.3: репорты только Monitoring `:7` | **перекрыто 26.09 (v0.3.8):** кейс → origin-топик; `:7` = ops/cron; Errors `:11112` отдельно |
| Snippet subscribe без `--thread-id` | `--thread-id <ORIGIN> --chat-type group`; без `--thread-id` запрещено |

До правки скиллов/GLOSSARY на диске будет **двойной канон**. Норматив до HF = эта секция.

### Что меняется в каноне (явные конфликты с GLOSSARY / скиллами)

| # | Конфликт | Статус |
|---|---|---|
| П1 | Требование 4 от 24.09 (авто take-into-work после одобренного диагноза) **отменено**. Прямой конфликт с GLOSSARY §2, `hermes-feature` (Блок 6В) и memory-инвариантом «багфиксы не ждут решения Саши» | до правки скиллов/GLOSSARY — двойной канон на диске |
| П2 | `GATE:plan-approve` always auto **и в пошаговом ходе**. Прямой конфликт с GLOSSARY §5.1/§5.2 инвариант 6 и старым п.9 «Решения Саши» (второе «берём в работу» по плану). Это **реальное изменение поведения**: контроль Саши над планом снят | GLOSSARY §5.2 инвариант 6 будет перезаписан отдельной карточкой |
| П3 | GLOSSARY §5.2 **инвариант 3** (one-pass auto гейтов `take-into-work` / `plan-approve` / `done`) **устаревает**. **§5.2.3** будет переформулирован: auto только `GATE:plan-approve` | отдельная карточка GLOSSARY |
| П4 | LIGHT: покрытие IAC vs `AC-###` никем не верифицируется (`REV:plan` skip по определению LIGHT) | **принятый риск** (таблица рисков ниже) |

### Решения Саши 25.09 (факты)

1. Два уровня критериев приёмки: **итоговые** по ТЗ (`AC-###` в master-ТЗ этой работы) и **промежуточные** между блоками/фазами (`IAC-##` в `HF:plan`). Нормативный язык (`ДОЛЖНА`, ДАНО/КОГДА/ТОГДА) **необязателен**; якоря `AC-###` **стабильны**.
2. **Вариант 1 (R4.1).** Доскональная проверка итоговых AC Сашей = `GATE:take-into-work` **после** `TZ:finalize`, со списком AC в диалоговом чате. `GATE:diagnose-review`: **выбран вариант (а)** — HITL остаётся, субъект = архитектор + `REV:tz`, не Саша; **never auto** сохранено. Программный auto-pass (б) **не** выбран. `kanban_complete` на `GATE:diagnose-review` вызывает **архитектор вручную** (архитектор + `REV:tz` = субъект HITL; не скрипт, не цепочка фаз). Ручное решение архитектора «диагноз хороший» обязательно. Требование 4 от 24.09 (авто take-into-work после одобренного диагноза) **отменяется** (П1).
3. **Две точки AC-приёмки** для всех кейсов **с ТЗ-циклом**: DEV / CHANGE / BUGFIX / LIGHT / RESEARCH / process / skills. (1) финализация ТЗ по AC-списку из чата; (2) готовность функционала — отчёт о прохождении **всех** итоговых AC с деталями, **как** тестировали каждый критерий. MIGRATION / DECOMM — **не** кейсы DEV-приёмки AC: `GATE:go` / `GATE:block-accept` остаются HITL как **запрос решения** (удаление / приём блока миграции), это отдельный HITL-набор, к AC-канону «ровно двух точек» не относится.
4. `GATE:plan-approve` — **always auto** (`HF:plan` обязателен там, где GLOSSARY §5.2 его требует; `REV:plan` остаётся). Саша план не согласовывает (П2).
5. **One-pass как режим Саши** означает **только** авто-проход плана (`GATE:plan-approve` always auto). **Не** сокращение HITL-точек: `GATE:take-into-work` и `GATE:done` остаются **never auto и в one-pass**. `GATE:done` — Саша закрывает по отчёту AC. Сознательный обмен относительно one-pass v0.2.2+. GLOSSARY §5.2 инвариант 3 / **§5.2.3** устаревает (П3).
6. Тишина о промежуточных фазах: подписывать **не** все карточки батча. `notify+wake` — корень `DEV/<slug>` (терминальные block/crash/gave_up/timed_out/drift будят оркестратора) **и** HITL-гейты AC (`GATE:take-into-work`, `GATE:done`). Промежуточные фазы не подписаны — их `completed` тихий. Ядро канбана / `TERMINAL_KINDS` не трогать.
7. I2 (`AC-###`) — несущая конструкция. I1 (current/target) — разметка **новой** секции master-ТЗ. I3 (`path` / `verify` / `depends`) — трассировка IAC в `HF:plan` (синтаксис tasks.md), без новых фаз канбана.

### Два уровня (R1)

| Уровень | Идентификатор | Где живёт | Кто выявляет | Саше в чат |
|---|---|---|---|---|
| Итоговые по ТЗ этой работы | `AC-###` (стабильный якорь, не номер §) | секция **этого** пакета в master-ТЗ `TZ/<Tool>/<Tool>_TZ.md` | архитектор на `TZ:patch`; фиксирует `TZ:finalize` после `REV:tz` | **да** — после `TZ:finalize`, до снятия `GATE:take-into-work` |
| Промежуточные между блоками/фазами | `IAC-##` пайплайна | таблица в `HF-plan_*.md` (полный хвост) **или** 1–3 строки в секции ТЗ / `_fix_plan_*.md` / body `BUG:diagnose` (LIGHT) | архитектор на `HF:plan` (R3); `REV:plan` проверяет покрытие `AC-###` **в полном хвосте** (не LIGHT — П4) | **нет** — доступ через план / comment `HF:plan` |

**Омоним (не путать).** Строка «Т (тест) | IAC-01..10» в САНКТ-списке под «Фазы ↔ скиллы» (v0.3.1, `_fix_plan_20260925.md` §П.10) — **тесты инварианта namespace моделей**, не промежуточные критерии приёмки этой секции. Пайплайнные `IAC-##` сюда не подмешивать и САНКТ-список не переименовывать.

`FR-###` — опционально, не норматив этой секции. Линтер / `validate_sdd.py` / дерево `docs/sdd/` — **не** вводить (bk-178).

### Итоговые `AC-###` (R2, I2)

Выявление — `TZ:patch`. В новой секции master-ТЗ:

- маркер I1: `current` (уже в проде) vs `target` (эта работа);
- подраздел `### Критерии приёмки (AC)` — **только AC этого пакета**, не ретрофит всего корпуса;
- якорь вида `AC-001`, `AC-002`, … стабилен при вставке соседних §; формулировка проверяема (наблюдаемое поведение / команда / артефакт). Нормативный язык — стиль, не парсер-гейт.
- опциональное поле класса O (не парсер всего корпуса — **только пакет этой работы**, как I2; ретрофит всех master-ТЗ **не** делать):

```
depends: operator:<verb>
```

  Default = класс S (без строки поезд не ждёт). `<verb>` ∈ закрытого словаря: `поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n`. `REV:tz` ловит operator-AC без тега и тег на train-completable AC.

Фиксация — `TZ:finalize` (роль архитектор, GLOSSARY §3). Один master-файл: AC **не** выносить во второй документ.

**Порядок выдачи (один ход `TZ:finalize` → `GATE:take-into-work`).** Сирень **сначала** публикует нумерованный список `AC-001 … AC-NNN` дословно из ТЗ в **диалог = origin-топик**, **затем** ставит `kanban_block` на `GATE:take-into-work`. Последовательно, не параллельно: Саша видит список **в момент** появления блокирующей карточки — не заранее отдельным сообщением и не позже. В ops-канал Monitoring `:7` список AC **не** дублировать (если origin сам `:7` — дубля в другой топик нет). Не публиковать AC в Errors `:11112`.

`GATE:take-into-work` (HITL Саши, never auto, **и в one-pass**): payload = тот же AC-список. Снятие фразой «берём в работу» **или** дашборд = AC приняты **и** старт HF-ветки. Инвариант «согласование ТЗ ≠ реализация» сохранён: до снятия гейта `HF:impl` не стартует.

**RESEARCH** (нет `TZ-WRITE`): итоговые AC — в отчёте `RS:analyze`; единственный HITL AC-приёмки = `GATE:done` с этим списком (две точки совпадают).

**IDEA/\*** — до постановки, вне двух точек AC-приёмки. `IDEA:analyze` → `blocked` остаётся HITL бэклога (решение «разбери» / отказ), не третья точка DEV-приёмки AC.

### Промежуточные `IAC-##` (R3, I3)

Архитектор на `HF:plan` (Блок 1А `hermes-feature`) вшивает таблицу (синтаксис tasks.md, без файла `tasks.md` и без новых фаз):

```
IAC-## | phase_from→phase_to | path | verify | depends | covers AC-###
```

- `path` — затрагиваемый файл/артефакт;
- `verify` — команда или именованный тест, не «на глаз»;
- `depends` — предшествующие `IAC-##` / T-строки;
- `covers` — трассировка на итоговый `AC-###`.

Исполнитель проходит IAC на границах `HF:impl` / `HF:test` **молча** (уже дух Блока 1А). Done-критерий карточки: `kanban_complete.metadata.iac_passed`. В чат Саше IAC не попадают.

**LIGHT** (CHANGE-LIGHT / BUGFIX-LIGHT): канон **до** правки GLOSSARY = §5.2 (`HF:plan` не возвращать, токен-регресс). Строка GLOSSARY §2 «HF:plan (вшит)» — известный баг глоссария (bk-178), **не** факт текущего поведения; перенесена на отдельную карточку правки GLOSSARY. 1–3 строки IAC — в секции ТЗ или в `_fix_plan_*.md` / body `BUG:diagnose`. Прогон `verify` — на `HF:test`. Покрытие IAC vs `AC-###` на LIGHT **никем не верифицируется** (`REV:plan` skip) — принятый риск П4.

**MIGRATION:** IAC на стыке `MIG:block-k`. Это не точка AC-приёмки DEV-цикла. Саша — только если нужен `GATE:block-accept` (запрос решения, вне «двух точек AC»).

### HITL — вариант 1 (R4)

Цикл `TZ-WRITE` → `PLAN-IMPL-TAIL` / `HF-TAIL` (кейсы **с ТЗ-циклом**):

```
BRF:*                         ← сбор требований (не процессный гейт; GLOSSARY §5 BRF)
TZ-WRITE → TZ:finalize
  → чат: список AC-###  (сначала)
  → kanban_block take-into-work  (затем)
GATE:take-into-work           ← HITL AC (1): Саша
HF:plan → [REV:plan]
GATE:plan-approve             ← always auto (карточка есть; skip фазы запрещён)
HF-TAIL (backup / impl / test / docs / ORCH)
  → чат: отчёт AC-### → как тестировали   (доставка в диалог Саши ДО preflight)
  → comment GATE:done: AC-delivered: … + тело отчёта
  → preflight (проверяет маркер + тело; сам не доставляет)
GATE:done                     ← HITL AC (2): Саша по отчёту; never auto
```

| Гейт | Норматив v0.3.2 | Кто снимает |
|---|---|---|
| `GATE:take-into-work` | HITL Саши, never auto **и в one-pass**. Payload = AC-список из чата. Требование 4 **отменено** и для BUGFIX/BUGFIX-LIGHT | Саша (Telegram **или** дашборд) |
| `GATE:plan-approve` | **always auto** (`auto-pass: architect-plan`). `HF:plan` обязателен до гейта там, где план в графе. `REV:plan` — качество плана, не Саша | скилл / воркер |
| `GATE:done` | HITL Саши, **never auto** (и в one-pass). Доставка отчёта в диалог **до** preflight. Preflight exit 0 — необходимое, не достаточное: проверяет маркер `AC-delivered:` на comment GATE:done **и** тело отчёта; наличие AC-артефакта ≠ доставка. Payload = отчёт по **каждому** `AC-###` (команда, лог/артефакт, результат), не список AC с `GATE:take-into-work` | Саша (Telegram **или** дашборд) |
| `GATE:diagnose-review` | Карточка DX **остаётся** (GLOSSARY §5.2, инвариант 7/9; DX не one-pass; классификация LIGHT после этой фазы). **Вариант (а):** HITL остаётся, субъект = архитектор + `REV:tz`, не Саша. **Never auto.** `kanban_complete` вызывает **архитектор вручную**; не скрипт, не цепочка фаз. Ручное решение «диагноз хороший» обязательно. Вариант (б) (программный auto-pass) **не выбран** | архитектор вручную (не фраза Саши, не скрипт) |
| `GATE:go` / `GATE:block-accept` | **Не** точки DEV-приёмки AC. HITL **запроса решения** для MIGRATION/DECOMM (удаление / приём блока). Вне «двух точек AC-приёмки» | Саша |
| Бриф `BRF:*` | Сбор требований; не процессный гейт AC-приёмки | Саша отвечает в TG |

`notify+wake` на `GATE:take-into-work` / `GATE:done` будит **оркестратора** в origin-топике графа, не прямой телефон Саши и не ops-канал `:7` (если origin другой); список/отчёт AC Саша получает в том же origin-диалоге.

Блок 1 / completion 1А `hermes-feature` («ждать второе «берём в работу» по плану / варианту») — **снять при реализации скилла**: варианты закрыты на `BRF`/`TZ:patch`; план Саше не показывают.

### One-pass

**One-pass как режим Саши** = **только** авто-проход плана (`GATE:plan-approve` always auto). **Не** сокращение HITL-точек: `GATE:take-into-work` и `GATE:done` остаются never auto **и в one-pass**. Фраза «делай в 1 проход» их **не** обходит. Не склейка фаз и не skip родительской работы (auto ≠ skip фазы). GLOSSARY §5.2 **инвариант 3** / **§5.2.3** устаревает (П3): будет «auto только `GATE:plan-approve`».

| Гейт | v0.3.0 / one-pass 0.2.2+ | v0.3.2 |
|---|---|---|
| `GATE:take-into-work` | one-pass auto; BUGFIX auto после diagnose (т.4) | HITL AC Саши, never auto (и в one-pass) |
| `GATE:plan-approve` | пошагово HITL; one-pass auto | always auto (единственный auto-гейт one-pass) |
| `GATE:done` | one-pass auto после preflight 0 | HITL Саши, never auto; отчёт AC |
| `GATE:diagnose-review` | HITL Саши, never auto | вариант (а): HITL архитектора + `REV:tz`, never auto; `kanban_complete` вручную архитектором; не скрипт |

Сознательный обмен: хвост длиннее one-pass 0.2.2+ на решение Саши по отчёту AC.

### Тишина уведомлений (R5)

Рычаг — **набор подписываемых `task_id`** и `delivery-mode`. `hermes kanban notify-subscribe` без фильтра видов событий. Ядро (`kanban_db.py`, `kanban_db_notify.py`, `TERMINAL_KINDS`) **не трогать**. **Канал по умолчанию = origin-топик** (`kanban_notify_subs.thread_id`, группа `-1004300127777`, `--chat-type group`); набор карточек тот же. П.15 / т.3 24.09 («всегда Monitoring :7») **перекрыты** v0.3.8. Wake будит оркестратора в origin, не Сашу напрямую и не в ops `:7`, если origin другой. DM и `:11112` — не канал кейса. SILENCE → не подставлять `:7`.

| Карточка | Подписка | `delivery-mode` |
|---|---|---|
| Корень `DEV/<slug>` | да | `notify+wake` (все терминальные события корня: block / crashed / gave_up / timed_out / drift — активный алерт оркестратору) |
| `GATE:take-into-work`, `GATE:done` | да | `notify+wake` |
| `GATE:go`, `GATE:block-accept`, `IDEA:analyze` (нужно решение) | да | `notify+wake` |
| `TZ:*`, `HF:*`, `REV:*`, `BUG:diagnose`, `ORCH:shared-state`, `RS:*`, `GATE:plan-approve`, `GATE:diagnose-review` | **нет** | — (промежуточный `completed` тих) |

Наследования подписки по `parents` по-прежнему нет: подписывать явно выбранные id, не «все из батча».

Протокол воркера (без ядра): `crashed` / `gave_up` / `timed_out` / drift на неподписанной фазе → `kanban_block` **корня** с `review-required:`. Корень на `notify+wake` → терминальный block/crash корня **активно будит** оркестратора/архитектора в origin. Гарантированный канал = активный алерт, не пассивная строка в ops-Monitoring. Промежуточные `completed` остаются тихими (эти фазы не подписаны).

Список AC (`GATE:take-into-work`, приёмка) и отчёт AC (`GATE:done`, доставка) — **разные артефакты**; оба — **диалог Саши = origin-топик**, не ops-карточка Monitoring `:7` (если origin другой). Наличие файла/comment с якорем `AC-###` ≠ доставка отчёта.

### Согласование с GLOSSARY, системным промптом и скиллами

Канон имён — `GLOSSARY.md` (правка глоссария — **отдельная фаза**, не эта запись). Эта секция не плодит синонимов фаз (`HF:fix` запрещён; `TZ:architect` как бриф запрещён).

| Слой | Как стыкуется |
|---|---|
| GLOSSARY §1/§6 | Документ = «ТЗ»; один master-файл; AC/IAC — артефакты внутри ТЗ/`HF:plan`, не фазы и не скиллы |
| GLOSSARY §3 роли | Архитектор: `AC-###` на `TZ:patch`, `IAC-##` на `HF:plan`; **вручную** `kanban_complete` на `GATE:diagnose-review`. Ревизор: `REV:tz` / `REV:plan`. Исполнитель: прогон `verify`. Оркестратор: выдача AC-списка и отчёта в чат; не придумывает критерии (требование 2 / v0.3.0 п.14) |
| GLOSSARY §4 | На карточку — один скилл фазы (`tz-workflow` **или** `hermes-feature`). sdd-writer / второй канон документации на карточку не грузить |
| GLOSSARY §5.2 | Набор фаз прежний. **До правки GLOSSARY для LIGHT каноничен §5.2** (`HF:plan` skip, IAC = 1–3 строки). Строка §2 «HF:plan (вшит)» — баг bk-178, не текущее поведение (отдельная карточка). `GATE:diagnose-review` остаётся в графе DX, never auto, HITL субъекта = архитектор + `REV:tz` (вариант а). Инварианты 2, 7, 8, 9, 10 — без изменений по фазам. **§5.2.3** (инвариант 3) и инвариант 6 — будут перезаписаны (П2, П3) |
| Системный промпт / `tz-workflow` / `hermes-feature` | Содержание ТЗ — архитектор. Согласование ТЗ ≠ impl. «берём в работу» = приёмка AC; «готово» = приёмка отчёта AC. Кроны не авто. Gateway не рестартовать |

Целевые правки скиллов (HF после «берём в работу», **не** эта фаза):

| Файл | Что вшить |
|---|---|
| `tz-workflow/SKILL.md` | Шаг 4: секция `AC-###` + I1-маркер; ход finalize: сначала AC-список в origin-диалог, затем `kanban_block`; `GATE:take-into-work` HITL Саши, never auto; т.4 отменить; `GATE:diagnose-review`: `kanban_complete` архитектор вручную, never auto, субъект HITL = архитектор + `REV:tz`; subscribe-set R5 (корень `notify+wake`) + контракт `--thread-id <ORIGIN> --chat-type group`; SILENCE-unsubscribe; дети копируют origin с корня |
| `hermes-feature/SKILL.md` | Блок 1А: таблица IAC + `covers`; убрать HITL Саши по плану/варианту; `GATE:plan-approve` always auto; `GATE:done` never auto; доставка отчёта AC в origin-диалог **до** preflight + маркер `AC-delivered:`; LIGHT: IAC в `_fix_plan` / body diagnose; subscribe-set origin; стоп-кран identity duplicate на `HF:impl` при смене R5-канала; Блок 6В: подписать **корень**, не diagnose; complete diagnose-review — архитектор вручную |
| `GLOSSARY.md` | Слой артефакта AC/IAC; две точки AC-приёмки для ТЗ-цикла; **переформулировать §5.2.3 (инвариант 3):** auto только `GATE:plan-approve`; перезаписать инвариант 6 (план не HITL Саши); diagnose-review never auto, HITL = архитектор + `REV:tz`; починить §2 «HF:plan (вшит)» vs §5.2 skip (баг bk-178) |
| `pipeline_gate_done_preflight.py` | Требовать маркер `AC-delivered:` в comment карточки GATE:done И тело отчёта (comment GATE:done или файл AC-report_<slug>*.md). Не принимать список AC с GATE:take-into-work и не считать наличие AC-артефакта доставкой. Не парсить формулировки AC |
| `_TZ-WORKFLOW-RULES.md` | Одна строка: новые требования — `AC-###` в той же секции master-ТЗ |
| `kanban-dev-cases` | Зеркало GLOSSARY, если иначе разъедется |

Не вшивать: новый скилл, новые фазы, ядро канбана, `config.yaml` notify, кроны.

### Что НЕ трогать (эта концепция)

- Не ставить `sdd-writer`, не плодить `docs/sdd/`, не делать AC обязательным парсером на исторический корпус.
- Не ретрофитить все master-ТЗ якорями; AC — **только пакет этой работы**.
- Не добавлять и не склеивать фазы канбана; не возвращать полный `HF:plan` на LIGHT «ради IAC».
- Не путать пайплайнные `IAC-##` с САНКТ `IAC-01..10` (v0.3.1).
- Не менять `kanban_db.py` / `kanban_db_notify.py` / `TERMINAL_KINDS`.
- Не дублировать AC-список в ops-канал Monitoring `:7`, если Саша уже получил его в origin-диалоге (если origin сам `:7` — дубля в другой топик нет).
- Не авто-complete `GATE:done` и `GATE:take-into-work` ни в one-pass, ни для багфиксов.
- Не ставить скриптовый auto-pass на `GATE:diagnose-review` (вариант б запрещён).
- Не писать `GLOSSARY.md` / скиллы / инвентарь в этой записи `TZ:patch`.

### Канон текста — приёмка

- В master-ТЗ любой новой работы (после вшивки скилла) есть якоря `AC-###` пакета; после `TZ:finalize` Саша видит список в **origin-топике** **в момент** `kanban_block` на `GATE:take-into-work`.
- `HF:plan` полного хвоста содержит `IAC-##` с `path` / `verify` / `depends` / `covers`; чат на промежуточных фазах молчит.
- `GATE:plan-approve` complete без фразы Саши; `HF:plan` при этом done.
- `GATE:diagnose-review`: `kanban_complete` — архитектор вручную, never auto; Саша на этом гейте не нужен; `GATE:take-into-work` после багфикс-ТЗ — ждёт AC-проверку Саши.
- `GATE:done` не complete без доставки отчёта «AC-### → как тестировали» в **диалог = origin-топик** (маркер `AC-delivered:` на comment GATE:done + тело) и без фразы/дашборда Саши; наличие AC-артефакта без маркера ≠ доставка; preflight 0 недостаточен.
- Подписка батча ≠ все фазы; `notify+wake` на корне и AC-гейтах; промежуточный `completed` не будит.
- САНКТ-список v0.3.1 и строка `IAC-01..10` на месте, без переименования.

### Риски этой секции

| Риск | Митигация |
|---|---|
| Двойной канон до HF (П1–П3) | норматив = эта секция; HF вычищает скиллы; GLOSSARY — отдельная карточка (§5.2.3, инвариант 6, т.4) |
| Снятие HITL Саши с плана: неверный IAC (полный хвост) | `REV:plan` обязателен **в полном хвосте**; Саша ловит на отчёте AC |
| LIGHT: покрытие IAC vs `AC-###` никем не верифицируется (`REV:plan` skip) (П4) | **принятый риск:** самопроверка архитектора на `TZ:patch`/diagnose; Саша ловит на финальном отчёте AC по `GATE:done` |
| `GATE:done` never-auto длиннее one-pass 0.2.2+ | сознательно (решение 25.09) |
| Crash на неподписанной фазе / потеря wake | корень `notify+wake` → терминальный block/crash корня **активно будит**; гарантированный канал = активный алерт оркестратору/архитектору; потеря wake при crash **устранена** переводом корня на `notify+wake` |
| Гигантский корпус (ProtocolFromSummary) — AC всего ТЗ в патче | только AC **этого** пакета |
| Омоним IAC САНКТ vs пайплайн | явный абзац выше; не переименовывать САНКТ |
| Случайный скриптовый auto-pass diagnose-review (вариант б) | запрет в тексте: complete только архитектор вручную; never auto |

## Поезд — канон v0.4.0

Норматив **28.09.2026** (императив Саши: поезд «старт → финиш» без ожидания «берём в работу» / «готово»). Источник: `appendix_process_rework_20260928.md`. **Перекрывает** v0.3.2 «две точки never auto» и п.6–8 «Решения Саши» в части гейтов. Каркас фаз GLOSSARY §5.1/§5.2 не ломается — фазы не добавляются и не удаляются. Скиллы — W2, не эта запись.

**I1.** `current`: HITL never auto на `GATE:take-into-work` / `GATE:done`; хвост графа unfold после take-into-work; preflight 0 необходим, не достаточен.  
`target`: штатный DEV-поезд; полный батч графа; preflight 0 достаточен; показ AC ≠ ожидание.

| Было (v0.3.2) | Стало (v0.4.0) |
|---|---|
| HITL Саши **ровно две** точки, **never auto** | Эти две точки — **always auto** после доставки артефакта |
| `TZ:finalize` → AC в чат → `kanban_block` → ждать фразу/дашборд | AC в origin → `auto-pass: ac-shown` → complete → хвост сам `ready` |
| `GATE:done`: preflight 0 необходим, не достаточен; ждать «готово» | preflight 0 **достаточен**; complete воркером; отчёт AC уже в origin |
| Граф TZ-WRITE + take-into-work; хвост unfold после гейта | **Один** create-батч полного кейсового графа; unfold **нет** |
| `GATE:diagnose-review` never auto, complete архитектор вручную | auto после артефакта плана (`_fix_plan_*.md` или непустой body) |
| One-pass = единственный путь auto трёх гейтов (история 0.2.2) / затем «auto только plan-approve» (0.3.2) | Штатный поезд **и так** auto на AC-гейтах; фраза «1 проход» вестигиальна |

Снятие с дашборда / фраза Саши на auto-гейтах = идемпотентный no-op.

**Классы участия Саши (аддитив operator-hold, содержание v0.4.2; поезд v0.4.0 не откатывается):**

| Класс | Что это | Блокирует `GATE:done`? | Напоминание | Примеры |
|---|---|---|---|---|
| **S — show-only** | Саша *видит* артефакт. Поезд идёт. | нет | нет (уже R5 `notify+wake` показ) | AC-список на take-into-work; AC-отчёт по train-completable AC; freshness «неясно»; «берём в работу» / «готово» |
| **O — operator-hold** | Саша *должен сделать* действие, без которого AC пакета неверен. | **да** | **да, повторно** (сторож; канон обязывает, текст ТЗ сам TG не шлёт) | «поднимай»; «ставь кроны» (если AC требует живой job); «удаляй» уже `GATE:go`; ответ на открытый вопрос Q-n; недосказанный бриф |
| **C — crisis** | уже канон v0.4.0 | поезд стоит на корне | R5 terminal `blocked` | `review-required: crisis:`; `GATE:go` / `GATE:block-accept`; IDEA до «разбери» |

Default AC = класс S. Класс O — только тег в master-ТЗ пакета:

```
depends: operator:<verb>
```

Закрытый словарь (не расширять без `TZ:patch` DKP): `поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n`. Сторож глаголы **не** выполняет. Снятие: `operator-done: <verb>` + `evidence:` факта на `GATE:done` или корне. Фраза без evidence ≠ `operator-done`.

**Саша участвует.** Класс **O** (`depends: operator:<verb>` / открытый Q-n / `review-required: operator-action:<verb>`) **блокирует `GATE:done`** (preflight ≠ 0) **и напоминается сторожем**. Класс **S** (показ AC-списка / AC-отчёта, freshness «неясно», фразы «берём в работу» / «готово») **не** блокирует и не напоминается как hold. Класс **C**: `BRF:*` в TG; кризис (`review-required: crisis:` на корне); `GATE:go` / `GATE:block-accept`; IDEA до «разбери». R3-глаголы «поднимай» / «ставь кроны» / «удаляй» — класс O (или C, если это `GATE:go`), не show-only.

Хвост GLOSSARY §5.2 обязателен; `kanban_complete` корня до `GATE:done` запрещён (**ИНВАРИАНТ / guard закрытия корня**; нарушение = operator-action premature-close, сторож `rule9_bugfix_broken_tail`, не nudge). Механика сторожа — `HF:impl`; канон — эта отсылка + раздел графа BUGFIX v0.4.4.

**R5:** набор карточек не расширять. `notify+wake` на `GATE:take-into-work` / `GATE:done` = **показ**, не hold. Стопкран identity duplicate **не** переносить на `dev-process-rework`.

### Критерии приёмки (AC)

Только пакет `dev-process-rework` (DKP v0.4.0). Наблюдаемое поведение. Payload показа на `GATE:take-into-work` этого слага. Скиллы/сторож закрывают AC на W1–W4; эта запись фиксирует канон.

### AC-P01 — полный батч графа
После закрытого брифа на доске полный набор фаз кейса (GLOSSARY §5.2) с `parents` и ключами `devpipe:…`. Повтор create того же ключа = 0 дублей.

### AC-P02 — take-into-work без hold
Между `TZ:finalize` и `HF:plan` нет `blocked review-required` ожидания Саши. AC-список есть в origin (comment + факт сообщения). `GATE:take-into-work` = done с `auto-pass: ac-shown`.

### AC-P03 — done после preflight 0
После preflight exit 0 `GATE:done` = done без фразы «готово». Корень закрыт. Отчёт AC в origin + маркер `AC-delivered:`.

### AC-P04 — кризисный HITL не auto
`GATE:go` / `GATE:block-accept` / IDEA `blocked` / crisis-block корня **не** auto.

### AC-P05 — REV rework-ребёнок
REV `CHANGES_REQUIRED` → за 1 tick сторожа или воркера появляется rework-ребёнок рабочей фазы; голого unblock нет; повторный REV с новым ключом.

### AC-P06 — D1 Cursor-slug
Карточка с D1 `cursor-grok-*` → сторож снимает model, retry; нет висения `protocol_violation` >20 мин.

### AC-P07 — heartbeat сторожа
`running` без heartbeat 20 мин → retry. Живой heartbeat 3ч → нет ложного kill.

### AC-P08 — граф оборван
Узел с обязательными детьми по §5.2 не может быть done при `children=[]`; preflight exit 1 «граф оборван».

### AC-P09 — второй канал запрещён
Пока граф `todo/ready/running`, второй `agent -p` координатора на ту же фазу не запускается (GLOSSARY инвариант 8).

### AC-P10 — смоук не трогает тройку
Смоук W4 прошёл; тройка выходных графов не изменилась этим пакетом.

### AC-P11 — leftover never auto
`rg` по скиллам пайплайна: нет рабочего «never auto» на `GATE:take-into-work` / `GATE:done` (допустим changelog/история в DKP левая колонка).

### AC-P12 — фазы не склеиваются
Фазы по-прежнему отдельные карточки / отдельные `agent -p`; `HF:impl` ≠ `HF:test`.

### Критерии приёмки (AC) — пакет done-gate / operator-hold

Только пакет done-gate (аддитив к поезду v0.4.0; номер DKP **v0.4.2** сохранён). Наблюдаемое. **Нет** `depends: operator:` на этих AC (поезд процесса не должен ждать Сашу, кроме смоука O-фикстуры). Payload `GATE:take-into-work` этого слага. Скрипты/скиллы закрывают AC на W1–W4; эта запись фиксирует канон.

| ID | Критерий |
|---|---|
| **AC-D01** | GLOSSARY + DKP различают S/O/C; leftover «просмотр AC не блокирует» с оговоркой O |
| **AC-D02** | AC с `depends: operator:поднимай` + нет `operator-done` → preflight exit 1, `GATE:done` не complete |
| **AC-D03** | Реплика отчёта `t_07c4913c` (AC-005 ⏳ при `AC-delivered:`) → exit 1 |
| **AC-D04** | Open Q-n на корне → нет brief-closed create **или** preflight 1, если граф уже есть |
| **AC-D05** | Сторож: open operator-hold → сообщение в origin ≤1-го тика; повтор <4ч не дублирует |
| **AC-D06** | `HF:plan` done + `children=[]` + нет следующей фазы §5.2 → сторож rule8 broken-tail (живое) / алерт (корень уже done). **Не** покрывает BUGFIX-LIGHT (в них нет `HF:plan`) — то `rule9_bugfix_broken_tail` (v0.4.4, AC-B03/B04) |
| **AC-D07** | Граф без operator-holds: preflight 0 как v0.4.0 (регресс поезда нет) |
| **AC-D08** | Код §29 PFS **не** входит в diff этого слага; `pfs-task-slug-not-created` не parents на этот граф |

### AC-D01 — S/O/C и leftover показа
GLOSSARY §3 слой AC/IAC и DKP «Поезд — канон v0.4.0» различают классы S / O / C. Leftover «показ AC ≠ ожидание» / «просмотр не блокирует» несёт оговорку класса O.

### AC-D02 — operator-hold блокирует done
AC с `depends: operator:поднимай` и нет `operator-done` → preflight exit 1, `GATE:done` не complete.

### AC-D03 — анти-фикшн отчёта O-AC
Реплика отчёта `t_07c4913c` (AC-005 ⏳ / ОЖИДАЕТ при `AC-delivered:`) → preflight exit 1.

### AC-D04 — open Q-n
Open Q-n на корне → нет `GATE:brief-closed` create **или** preflight 1, если граф уже есть.

### AC-D05 — сторож напоминает hold
Сторож: open operator-hold → сообщение в origin ≤1-го тика; повтор <4ч не дублирует.

### AC-D06 — оборванный хвост
`HF:plan` done + `children=[]` + нет следующей фазы §5.2 → сторож rule8 broken-tail (живое) / алерт (корень уже done). rule8 начинается с наличия `HF:plan` и **пропускает** BUGFIX-LIGHT. Обрыв после DX / раннее закрытие корня — `rule9_bugfix_broken_tail` (v0.4.4).

### AC-D07 — регресс поезда S
Граф без operator-holds: preflight 0 как v0.4.0.

### AC-D08 — PFS §29 вне этого слага
Код §29 PFS **не** входит в diff этого слага; `pfs-task-slug-not-created` не parents на этот граф.

## Канон процесса v0.4.1 — определения, роли, guard-ы

Норматив **29.09.2026**. Источник: обсуждение Саша↔оркестратор (инцидент `DEV/pfs-task-slug-not-created`: архитектор укоротил граф BUGFIX до plan→impl→test; код на диске untracked; preflight `GATE:done` упал только в конце). **Не ломает** каркас фаз GLOSSARY §5.1/§5.2 и поезд v0.4.0. Скиллы/скрипты — W1, не эта запись. GLOSSARY — v0.2.12 (эта же `TZ:patch`).

**I1.** `current`: emit-prompt проверяет только наличие тройки файлов; complete фазы без доказательства контекста; git-commit impl не проверяется; structural-полнота графа только на `GATE:done`; архитектор может выбрать кейс/укоротить граф.  
`target`: G1–G5 закрыты; определения граф/карточка/фаза; закрытый список 10 кейсов; процесс = оркестратор, содержание = архитектор; тестирование без отдельной роли.

### Определения

Как GLOSSARY §0.1: **граф** = один пошаговый план одной задачи; **карточка** = один шаг графа; **фаза** = имя шага `PREFIX:фаза`. Кейс ≠ граф.

### Десять кейсов

Таблица «Каталог кейсов» выше — полный закрытый список (DEV, CHANGE, CHANGE-LIGHT, BUGFIX, BUGFIX-LIGHT, RESEARCH, MIGRATION, DECOMM, SKILL-DEV, SKILL-CHANGE). Сборка — GLOSSARY §2. Семейство — Саша+оркестратор на старте. LIGHT — оркестратор, не архитектор (BUGFIX: выбранный LIGHT/полный хвост — в том же create-батче, не перепись после `GATE:diagnose-review`).

### Тестирование без отдельной роли

Решение Саши 29.09: роль «тестировщик» не вводится. Архитектор на `HF:plan` пишет IAC с `verify`. Исполнитель (`composer-2.5`) пишет код (`HF:impl`) и сам гоняет тесты (`HF:test`) по плану, молча. Отчёт AC — `GATE:done`. LIGHT: 1–3 строки IAC в секции ТЗ / `_fix_plan` / body `BUG:diagnose`; прогон на `HF:test`.

### Guard-ы G1–G5

| # | Пробел | Механика (target W1) | Где канон |
|---|---|---|---|
| G1 | emit-prompt не знал граф / version / «запланированное в git» | `--card` ∈ граф; disk version/mtime = card; post-impl фазы не стартуют при untracked impl | «Контекст-промпт» |
| G2 | фаза complete без доказательства контекста | маркер `context-used:` до `agent -p`; `check --card` exit 0 обязателен для complete TZ/HF/BUG/REV | протокол воркера п.5/7 |
| G3 | «виртуальная» реализация (untracked) | preflight `--mode done` п.8: `changed_files` в git-worktree закоммичены | «Preflight» |
| G4 | неполный граф ловился только на `GATE:done` | `--mode create` сразу после батча; fail → block корня | «Preflight» |
| G5 | архитектор решал ход процесса | `kanban_create` графа = оркестратор; воркер архитектора не create фаз кейса, не skip, не LIGHT-rewrite | «Процесс vs содержание»; GLOSSARY §3 |

Reuse-first: новые USERTOOL/скиллы **не** вводятся. Патч `pipeline_context_bundle.py` + `pipeline_gate_done_preflight.py` + разделы канбан-шаг в `tz-workflow` / `hermes-feature` / `cursor-cli` / `cursor-task-context` / зеркало `kanban-dev-cases`. Ядро канбана не трогать.

### Критерии приёмки (AC)

Только пакет `dev-process-tz-hardening` (DKP v0.4.1; AC-H05b — v0.4.2). Наблюдаемое поведение. Скрипты/скиллы закрывают AC на W1; эта запись фиксирует канон.

### AC-H01 — определения
В `GLOSSARY.md` §0.1 и в этом ТЗ есть определения **граф** / **карточка** / **фаза** в формулировке «одна задача = один граф; карточка = шаг; фаза = PREFIX:фаза». Наблюдаемо: `rg -n "§0.1 Определения" ~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md` находит секцию.

### AC-H02 — десять кейсов
Каталог DKP и GLOSSARY §2 содержат ровно 10 имён: DEV, CHANGE, CHANGE-LIGHT, BUGFIX, BUGFIX-LIGHT, RESEARCH, MIGRATION, DECOMM, SKILL-DEV, SKILL-CHANGE. `pipeline_gate_done_preflight.py --case` (после W1) принимает этот enum и отвергает 11-й.

### AC-H03 — процесс vs содержание
Оркестратор создаёт граф; архитектор на TZ/HF/BUG-карточке не вызывает `kanban_create` кейсового батча. Наблюдаемо после W1: смоук — create-батч из роли архитектора → `protocol_violation` или block; из оркестратора → граф на доске.

### AC-H04 — тестирование без отдельной роли
`HF:plan` done-критерий включает таблицу IAC с `verify`; `HF:test` = исполнитель `composer-2.5`; в GLOSSARY §3 нет роли «тестировщик». Наблюдаемо: строки таблицы «Фазы ↔ скиллы» для `HF:plan` / `HF:test`.

### AC-H05 — G1 emit-prompt граф + version
После W1: `emit-prompt --card` чужой/без корня → exit 1; `--card` живого ребёнка графа + тройка на диске → exit 0; drift `tz_version` card vs YAML → exit 1. Смоук на фикстуре kanban.db. (Пункты 1–2 G1; пункт 3 — AC-H05b.)

### AC-H05b — G1 emit-prompt не стартует HF:test / HF:docs-handoff по untracked impl
После W1: `emit-prompt --card` на живой карточке `HF:test` или `HF:docs-handoff`, когда G3 git-proof уже red (`HF:impl` `changed_files` untracked/uncommitted в git-worktree) → **exit 1**. Тест и документирование **не** стартуют по незакоммиченному impl-коду (`agent -p` этой фазы не вызывается). Смоук на фикстуре kanban.db. (Пункт 3 G1; G3 на `GATE:done` — AC-H07.)

### AC-H06 — G2 context-used
После W1: `kanban_complete` TZ/HF без comment `context-used:` с совпадающим `card` и `tz_version` диска → запрещён (`check` exit 1). Карточка с маркером, выписанным emit-prompt → `check` exit 0.

### AC-H07 — G3 git-proof
После W1: фикстура `HF:impl` `changed_files` = untracked файл в git-worktree → preflight `--mode done` exit 1. Тот же файл `git add && git commit` → проверка G3 проходит (при прочих OK). Vault-путь вне git не требует commit.

### AC-H08 — G4 structural на create
После W1: граф BUGFIX без `TZ:patch`/`TZ:finalize` → `--mode create` exit 1 **до** любого TZ/HF `agent -p`. Полный батч канона → exit 0. `--mode done` по-прежнему требует фазы `done`.

### AC-H09 — G5 запрет архитектору решать процесс
В GLOSSARY §3 и DKP «Процесс vs содержание» явно: архитектор не строит граф, не выбирает кейс, не skip фаз. Смоук W1: промпт архитектора на `TZ:patch` / `BUG:diagnose` не содержит инструкции «создай граф / выбери LIGHT / skip TZ-WRITE»; содержит «исполняй поставленную задачу; вопросы Саше через оркестратора».

### AC-H10 — LIGHT только оркестратор
Семейство BUGFIX и LIGHT vs полный хвост выбирают Саша+оркестратор **на старте**. Карточки выбранного хвоста — в том же `kanban_create` (корень+`BUG:diagnose`+`GATE:diagnose-review`+хвост); **переписи хвоста** после `GATE:diagnose-review` нет. Архитектор в `_fix_plan` может указать оценку файлов; `kanban_create` LIGHT-хвоста им запрещён. Наблюдаемо: каталог DKP (строка BUGFIX-LIGHT) + блок «Полный батч BUGFIX»; GLOSSARY §2 — кто сужает (оркестратор), не команда второго unfold.

### Что НЕ трогать (этот пакет)

- Ядро канбана, Gateway, кроны, HITL-канон v0.4.0 (auto/never auto).
- Не вводить роль тестировщика и не добавлять фазу сверх GLOSSARY §5.
- Не новый USERTOOL / скилл; не `--force` на context-bundle.
- Не git-commit vault ТЗ (не worktree) как обязательный G3.
- Не переносить стопкран identity duplicate на этот слаг.
- Инвентарь `MAIN_TZ_INVENTORY.md` — `TZ:finalize`, не эта фаза.

### Риски этой секции

| Риск | Митигация |
|---|---|
| G2 маркер скопирован без чтения тройки | скрипт не доказывает comprehension; `REV:tz`/`REV:plan` + «прочитай сам без обрезки»; version-match отсекает stale extract |
| G3 ложные fail на не-git путях | только git-worktree; vault ТЗ = диск |
| G4 create vs поздние `MIG:block-k` | опциональны на create (канон выше) |
| LIGHT после diagnose vs «кейс на старте» | семейство+хвост BUGFIX на старте в одном батче; сужение — оркестратор, не архитектор (AC-H10); второго unfold нет |
| Архитектор «решает сам» freshness (старый текст) | перекрыто: block + оркестратор |

## Критерии успеха

- На триггер «разработай X» / «доработай Y» / «почини» на доске появляется корень + **полный** набор фаз кейса с `parents` (один батч); панель отражает текущий шаг без памяти чата.
- После kill сессии Сирени dispatcher поднимает следующую `ready` карточку `default`; прогресс не требует пересказа истории.
- Однострочный вопрос Саши не создаёт карточек.
- `HF:impl` не стартует, пока `TZ:finalize` и `GATE:take-into-work` не done (ребёнок в `todo` до parents); фраза «берём в работу» не требуется.
- Кризисный гейт снимается **и** фразой в Telegram, **и** с дашборда; повторное снятие — no-op. На AC-гейтах фраза/дашборд — no-op, если уже auto.
- «делай в 1 проход» не склеивает фазы; штатный поезд auto на take-into-work / plan-approve / done / diagnose-review; never auto = `go` / `block-accept`.
- `GATE:plan-approve` always auto; Саша план не согласовывает.
- `GATE:done` complete воркером после preflight exit 0 (**достаточен**, включая operator-hold сняты и open-questions empty); показ отчёта AC ≠ ожидание «готово» **(класс S)**; класс O блокирует done + напоминается.
- Ручной feed идеи → карточка `IDEA:*` → заключение архитектора в comment → `blocked`; «разбери» / «берём в работу» стартует обычный DEV-цикл (HITL бэклога). Автокрон сбора контекста не создан.
- Исполнитель не меняет манифест/entities/inventory/.env/jobs.json; ORCH-карточка — единственный писатель после инструментных `done`.
- Воркер при bump ТЗ блокируется `kind=dependency` либо заменяется новой child после reclaim; той же карточкой работу не продолжают.
- `auto_decompose: false` (глобально, решение Саши); `max_in_progress_per_profile: 1`; `assignee` всегда `default`.
- Новый профиль не создан. Gateway не рестартован в ходе внедрения. Папка плана — `DevKanbanPipeline`.
- `grep` по скиллам пайплайна: есть явные `kanban_create`/`kanban_complete`/`kanban_block` на каждый перечисленный phase.
- Перед `kanban_create` графа `DEV/<slug>` активный граф по слагу не дублируется (slug-guard); параллельных графов на один слаг нет.
- Уведомления графа идут в **origin-топик** инициатора (`-1004300127777`, `thread_id=<ORIGIN>`, `chat_type=group`), не в DM, не в Errors `:11112`; Monitoring `:7` — только ops/cron (и кейс, **если** origin сам `:7` — без дубля). Явное указание Саши переопределяет канал графа.
- `GATE:take-into-work` / `GATE:done` / `GATE:diagnose-review` — always auto после артефакта; `GATE:go` / `GATE:block-accept` — never auto.
- После create-батча structural-preflight `--mode create` exit 0 (граф полон по кейсу) **до** первого TZ/HF `agent -p`; неполный граф не дожидается `GATE:done`.
- `emit-prompt --card` принадлежит графу; complete TZ/HF/BUG/REV с `context-used:`; `HF:impl` `changed_files` в git-worktree закоммичены до `GATE:done`; `emit-prompt` перед `HF:test` / `HF:docs-handoff` при untracked impl → exit 1 (тест/docs не стартуют по виртуальному коду).
- Архитектор не создаёт кейсовый граф и не выбирает кейс; оркестратор строит граф на старте. Тестирование без отдельной роли (IAC на `HF:plan`, прогон на `HF:test`).

## Связи с экосистемой

- `tz-workflow` / `TZ-storage-system` — канон master-файла, латиница, инвентарь, «согласование ТЗ ≠ стоп реализации». Этот план добавляет runtime-очередь, схему хранения ТЗ не меняет.
- `hermes-feature` — канон блоков 0–8; канбан — обёртка, не замена блоков.
- `kanban-orchestrator` / `kanban-worker` — API карточек, block kinds, review-required, reclaim; однопрофильные исключения описаны здесь.
- `cursor-cli` / `cursor-task-context` — вызовы моделей и компрессия; без кэша экстрактов.
- `EcosystemIntegration` — ORCH:shared-state обновляет манифест по Блоку 4.
- `TzDevDecommission` — инвариант «dev на default»; это ТЗ его продолжает и запрещает откат к split-профилям.
- `ErrorBus` — не обязан; protocol_violation/gave_up канбана видны на доске. Не подключать новые кроны ErrorBus в этом плане.
- `DialogBacklog` — паттерн автосбора незаконченного контекста **не** переносится сюда (отложено «после»). Ручной feed `IDEA:*` — отдельный, по команде Саши.
- USERTOOLS (MoveFromFF и др.) — потребители пайплайна, файлы инструментов этим ТЗ не меняются.

## Контракты экосистемы

### Источник истины

- Владелец записи карточек: канбан Hermes (`~/.hermes/kanban.db`), пишет профиль `default` через `kanban_*` / `hermes kanban`.
- Владелец master-ТЗ инструмента: `tz-workflow` (файл `TZ/<Tool>/<Tool>_TZ.md`).
- Владелец манифеста: `EcosystemIntegration` / карточка `ORCH:shared-state`.
- `kanban_notify_subs` — канал wake/notify кейса; владелец записи = `hermes kanban notify-subscribe` (+ `_maybe_auto_subscribe` на create); ядро `kanban_db*.py` / `TERMINAL_KINDS` не трогать.
- Этот план карточки чужих USERTOOLS не пишет.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| trigger | enum[new_tz, enhance, bugfix, one_pass, idea_feed] | required | фраза Саши в чате | new_tz=разработай/напиши ТЗ; enhance=доработай; bugfix=почини; one_pass=делай в 1 проход; idea_feed=ручной бэклог/triage |
| tz_path | str | optional | TZ:stabilize / диск | абсолютный путь master-ТЗ; пусто на new_tz до TZ:finalize; required для one_pass |
| tz_version | str | optional | YAML-frontmatter master-ТЗ | semver X.Y.Z |
| tz_mtime | datetime(iso8601) | optional | stat() master-ТЗ | UTC |
| gate_phrase | enum[take_into_work, done, finalize, one_pass] | optional | Саша (Telegram) | take_into_work=берём в работу; done=готово; finalize=финализируй; one_pass=делай в 1 проход |
| gate_channel | enum[telegram, dashboard] | optional | факт снятия гейта | telegram=фраза в чате; dashboard=unblock/approve на доске; оба валидны |
| idea_payload | str | optional | Саша при idea_feed | сырой текст заметки / путь к незакрытому исследованию |
| assignee | str | required | этот план | всегда "default" |
| origin_thread_id | str | required | `resolve_origin`: env корня (`HERMES_SESSION_THREAD_ID`) ИЛИ копия с подписки родителя | каталог топиков 1/3/5/6/7/8 (предпочтение) + origin вне каталога той же группы; `:11112` запрещён; пустая строка ≠ это поле (SILENCE, не шаг 3) |
| origin_chat_type | enum[group] | required | `resolve_origin` / команда `notify-subscribe` | всегда `group` для R5; DM/CLI/Cursor → SILENCE (subscribe не вызывать) |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| task_id | str | следующая карточка, Саша (доска) | id из return kanban_create |
| status | enum[todo, ready, running, blocked, done] | доска, dispatcher | review нет; ревью=blocked+prefix; IDEA inbox кратковременно triage→ready |
| metadata.changed_files | str | ORCH:shared-state | JSON-список путей в metadata |
| metadata.registry_touches | str | ORCH:shared-state | должно быть "[]" у исполнителя |
| metadata.tz_version | str | HF-воркер (сверка) | semver |
| metadata.tz_mtime | datetime(iso8601) | HF-воркер (сверка) | UTC |
| metadata.cursor_session_ids | str | --resume после reclaim | JSON-список UUID |
| metadata.one_pass | bool | GATE-карточки, hermes-feature | true=не клей роли / не плодить второй хвост; AC-гейты auto независимо от флага |
| block.kind | enum[dependency, needs_input, capability, transient] | dispatcher | dependency→todo auto-resume; остальные→HITL |
| notify_channel | str | wake (`kanban_watchers_notifier.py` / SessionSource), оркестратор origin-диалога | `kanban_notify_subs.thread_id` (канал wake/notify кейса); **не** metadata/body карточки |

### Зависимости

- Получает от: [tz-workflow, hermes-feature, kanban-orchestrator, kanban-worker, cursor-cli, cursor-task-context, EcosystemIntegration, TzDevDecommission]
- Отдаёт: [tz-workflow (раздел канбан-шаг + IDEA feed + полный батч графа), hermes-feature (канбан-шаг + plan-approve always auto; done auto после preflight 0), cursor-cli (флаги), EcosystemIntegration (запись infra_service после impl)]

### Breaking changes policy

- Версионирование формата: semver на поле `pipeline_schema` внутри `kanban_complete.metadata` (старт `"1.0"`). Схема SQLite канбана не наша — не мигрировать.
- При breaking change ключей metadata: бамп `pipeline_schema`, описать `migrate` в новой секции этого ТЗ, воркеры старых карточек блокировать `kind=dependency`, не додумывать поля.

### Границы («что НЕ трогать»)

- Не менять `hermes_cli/kanban_db.py` и статусы движка.
- Не вводить профиль-исполнитель (в т.ч. для бэклога идей).
- Не использовать `scratch` workspace для фаз пайплайна.
- CLI `--force` / `--force-bypass` на `pipeline_context_bundle.py` отсутствует. Обхода нет: скрипт/check блокируют старт всегда (решение Саши 26.09).
- Не вызывать decomposer для `DEV/<slug>` и `IDEA/<slug>`.
- Не ставить автокрон сбора незаконченного контекста.
- Не auto-complete **кризисные** гейты `GATE:go` / `GATE:block-accept`. `GATE:done` auto после preflight exit 0 (**достаточен**).
- `epic-development` и `aggregate-tz-opus-workflow` — **не этот пайплайн** (Cursor через zip/пакет, не `agent -p` канбана). На DEV не грузить (GLOSSARY §4). Эти скиллы в этом цикле не менять.

## Риски

| Риск | Митигация |
|---|---|
| Чат `default` и running-воркер `default` пишут одни файлы | `max_in_progress_per_profile=1`; чат во время running только HITL |
| `auto_decompose: true` разнесёт triage в выдуманный граф | выключить **глобально** (решение Саши); DEV-карточки сразу `todo`/`ready`; IDEA — triage только как inbox, скилл сразу → `ready` |
| protocol_violation если модель «ответила текстом» | чеклист complete/block; failure_limit уже 2. **Не** единственный класс — см. питфолл v0.4.4 (billing/транспорт rc=0; литерал `{body}`; не MarkdownV2) |
| BUGFIX-граф умирает после DX / корень done до `GATE:done` | полный батч BUGFIX в одном create (корень+BUG:diagnose+GATE:diagnose-review+хвост); сторож `rule9` (живое → block; раннее закрытие → operator-action premature-close); авто-разворот LLM не основной; двухшагового unfold нет |
| `--continue` смешает сессии | запрет в cursor-cli для пайплайна |
| Повторный `kanban_block` одного гейта → triage | один block на гейт; ждать unblock |
| Исполнитель «заодно» обновит манифест | запрет путей + непустой `registry_touches` → block |
| «1 проход» склеит роли | сознательно запрещено; auto-гейты ≠ skip фаз; `GATE:done` auto только после preflight 0; Сирень показывает итог в origin |
| Известное расхождение: tz-workflow:233/295 («требование 4», GATE:take-into-work auto one-pass) vs hermes-feature:44 (т.4 отменено, DKP v0.3.2) | вне scope v0.3.4; follow-up отдельным BUGFIX/CHANGE; в этом пакете 233/295 не править |
| Гейт снят дважды (Telegram + дашборд) | идемпотентный unblock, без re-block |
| IDEA зависает в `triage` при `auto_decompose: false` | скилл create сразу переводит `IDEA:analyze` в `ready` |
| IDEA и DEV дерутся за воркера | один `max_in_progress_per_profile=1`; очередь FIFO на `ready` |
| Канбан-уведомитель (апстрим `kanban_notify_subs`, `TERMINAL_KINDS`, `delivery_mode`, `notify-subscribe`) дрейфует при merge upstream | не трогать ядро (ни `kanban_db.py`, ни `kanban_db_notify.py`, ни список `TERMINAL_KINDS`); подписка — только `hermes kanban notify-subscribe` по фиксированному контракту «Уведомления графа»; перед merge upstream — бэкап `~/.hermes/kanban.db` в канон бэкапа |
| `HF:impl` origin-routing до identity `DEV/tg-topic-duplicate` | стоп-кран чеклиста в «Уведомления графа»; предпочтительно ждать `GATE:done` duplicate + «поднимай»; не origin-subscribe в обход |
| Архитектор укорачивает граф / untracked impl (pfs-task-slug) | G5 + G4 create-preflight + G3 git-proof; блокеры сразу оркестратору |

## Приложения к ТЗ

| Приложение | Путь | Статус |
|---|---|---|
| План CHANGE канона процесса (поезд HITL) | `TZ/DevKanbanPipeline/appendix_process_rework_20260928.md` | канон W0 2026-09-28; источник `_fix_plan_20260928.md` |
| План CHANGE done-gate (operator-hold) | `TZ/DevKanbanPipeline/_fix_plan_done-gate_20260929.md` | канон W0 2026-09-30 (П.1 текст); скрипты/скиллы — W1–W2 |
| План BUGFIX хвост после DX + protocol_violation | `TZ/DevKanbanPipeline/_fix_plan_20261012.md` | канон W0 `TZ:finalize` 2026-10-13 (П.2 текст + П.1 классы сторожа); код сторожа/тесты — `HF:impl` |

Справочные таблицы смоука W4 — `TZ/DevKanbanPipeline/appendix_<тема>_YYYYMMDD.md` после реализации.

## Открытые вопросы

Все закрыты брифом Саши 2026-09-05. Открытых вопросов нет.

| № | Вопрос (v0.1.0) | Решение | Где в этом ТЗ |
|---|---|---|---|
| 1 | HITL-доставка гейтов: только Telegram vs только дашборд | **Оба канала одновременно.** Снять гейт можно фразой в Telegram и действием на дашборде; Саша выбирает на конкретном гейте | «Гейты HITL», решение Саши п.7 |
| 2 | `auto_decompose` глобально `false` vs только «не класть DEV в triage» | **`false` глобально**, пока нет specialist-профилей | «Решения Саши» п.10, таблица конфигурации |
| 3 | Нужен ли отдельный `GATE:plan-approve` | **Да в пошаговом ходе** (второе «берём в работу» по плану). **В режиме «1 проход» auto-complete (карточка не skip)** | «Решения Саши» п.8–9, граф, «Гейты HITL» |
| 4 | Имя папки `DevKanbanPipeline` vs `HermesDevKanban` / `KanbanDevCycle` | **Оставить `DevKanbanPipeline`.** Путь не переименовывать | «Решения Саши» п.11, «Форма ТЗ» |

Дополнительно зафиксировано в том же брифе (не было отдельным открытым вопросом v0.1.0): режим «делай в 1 проход»; второе применение — ручной бэклог идей в `triage`; автокрон DialogBacklog-типа — не в этом ТЗ.

## v0.2.0 — финализация брифа (2026-09-05)

Нормативные формулировки — в разделах выше. Кратко, что вошло:

- Dual-HITL: Telegram + дашборд канбана.
- Режим «делай в 1 проход»: авто-проход `GATE:take-into-work` и `GATE:plan-approve`; `GATE:done` ручной. *(v0.2.2: `GATE:done` в one-pass auto после preflight exit 0; «ручной всегда» снято.)*
- `GATE:plan-approve` сохранён для пошагового хода.
- `auto_decompose: false` — явное решение Саши.
- Имя плана `DevKanbanPipeline` утверждено.
- Scope расширен бэклогом идей (`IDEA:*`, ручной feed, silent-воркер `default`, архитектор `cursor-grok-4.6-high`).
- Автокрон незаконченного контекста — вне scope.
- Статус ТЗ: `approved`. Реализация по-прежнему ждёт отдельного «берём в работу».

## v0.2.2 — контур B chain-enforcement (2026-09-08)

Канон one-pass (GLOSSARY §5.2): auto-complete HITL-гейтов, не skip фаз и не один `agent -p`.

- Подраздел **Preflight GATE:done**: путь `~/WorkVault/Registries/pipeline_gate_done_preflight.py`, вызов `--slug`, exit 0/1/2.
- Подраздел **off-board / retro-graph**: прецедент exchange 08.09; comment `done off-board, session ids`; TZ/HF без корня → стоп.
- Auto-pass ≠ skip parent work; `HF:plan` обязателен до `GATE:plan-approve`.
- Снято противоречие «`GATE:done` auto запрещён»: one-pass auto done **после** preflight exit 0; пошагово — только Саша.
- Скрипт и правки скиллов — реализованы HF:impl 08.09 (см. v0.2.4).

## v0.2.3 — REV skip-путь `flag-waived` (2026-09-08)

Preflight №4 согласован с GLOSSARY §5.2: `flag-waived: Sasha` — легитимный явный skip `REV:tz` для любого кейса (равнозначен REV done); sonnet `session_id` — если прогон был.

## v0.2.4 — docs-handoff контур B (2026-09-08)

- Preflight `pipeline_gate_done_preflight.py` **на диске**; `test_pipeline_gate_done_preflight.py` — **17/17** passed; exit 0/1/2.
- Скиллы `tz-workflow` **2.2.0**, `hermes-feature` **2.3.0** (HF:impl контура B).
- Вызов preflight: `--slug` + `--case DEV|CHANGE|BUGFIX|BUGFIX-LIGHT|CHANGE-LIGHT` (+ опц. `--flag-rev`).

## v0.2.6 — авто-подписка графов на уведомления в TG (2026-09-23)

Реализовано (вариант 1 по исследованию upstream, решение Саши 23.09): автоматическая подписка карточек графа на события при создании. Ядро канбана **не тронуто** — используется штатный апстрим-механизм `hermes kanban notify-subscribe`.

- Новый раздел **«Уведомления графа»** (контракт ниже): фиксированная подписка на все `task_id` графа сразу после `kanban_create` (наследования по `parents` после батча нет), `--delivery-mode notify+wake`, профиль `default`.
- Уведомитель шлёт только ключевые терминальные события (`TERMINAL_KINDS`: `completed`/`GATE:done`, `blocked`, `gave_up`, `crashed`, `timed_out`), не каждую фазу (шум).
- Риск: добавлен «Канбан-уведомитель дрейфует при merge upstream» — митигация: бэкап `~/.hermes/kanban.db` в канон бэкапа перед merge.
- Скиллы: `tz-workflow` **2.3.1**, `hermes-feature` **2.6.1** (шаг notify-subscribe после kanban_create + Блок 6В).

## v0.2.7 — freshness-gate + сериализация writers (2026-09-24)

Аддитивная секция (постановка Саши 24.09; прецедент `t_eba18cd9` 23.09). Реализация скиллов/скрипта **не** в этой записи.

- **Freshness-gate:** первый шаг любого воркера карточки (после `kanban_show`) — проверка актуальности (не решено другими правками; условия/файлы не изменились; статус карточки/графа). Неактуально → complete «неактуально» **или** HITL; вслепую — запрет. Вшито в «Протокол воркера», чек-листы `hermes-feature` / `tz-workflow` / `cursor-task-context` (целевая архитектура).
- **Сериализация writers:** единый advisory `flock` `LOCK_EX` на `~/WorkVault/Registries/.shared-state.lock`; скрипт-замок `pipeline_shared_state_lock.py` (аналог preflight, не плодить). RMW под lock + атомарный `os.replace`. Второй writer ждёт, не затирает. Параллельно — никогда. Дыра №1 — кросс-графовая запись манифеста/инвентаря без lock. Второй минимум — defer/семафор writer-фазы при running writer.
- Кап `max_in_progress_per_profile=3` оставить; `per_profile=1` — только временный рубильник (перекрывает постоянный режим v0.2.0–0.2.6).
- Классификация CHANGE vs CHANGE-LIGHT — на гейте, не в этом ТЗ.

## v0.2.5 — кейс BUGFIX-LIGHT (2026-09-22)

- Каталог §2: добавлен кейс BUGFIX-LIGHT (≤3 файла, вне shared, классификация после GATE:diagnose-review).
- Граф: корень `DEV/<slug>` + `BUG:diagnose` в одном create-батче (инвариант 9, ретро-корень запрещён); LIGHT-хвост PLAN-IMPL-TAIL-LIGHT.
- Preflight `pipeline_gate_done_preflight.py`: новые `--case BUGFIX-LIGHT` и `CHANGE-LIGHT`; план = `_fix_plan_*.md` ИЛИ непустой body `BUG:diagnose`; `test_pipeline_gate_done_preflight.py` — **20/20** passed.
- Скиллы `hermes-feature` **2.6.0** (классификатор, Блок 6В, чеклист).

## v0.3.0 — hardening dev-процесса (2026-09-24)

Аддитивная секция (постановка Саши 24.09; 4 дословных требования + 3 разобранных противоречия; отработана кейсами дня 24.09). Реализация скиллов **не** в этой записи — отдельным hermes-feature по «берём в работу».

Требования Саши → зафиксированные правила (см. «Решения Саши» п.13–16, «Гейты HITL», «Уведомления графа»):

1. **Все задачи по умолчанию в план и по канону** (т.1). Идеи `triage` (`IDEA:*`) — только по явному «разбери» (ЖЦ разделён, неконфликтующая формулировка).
2. **Валидация только архитектором** (т.2): Сирень не предлагает своё мнение/варианты по постановке — передаёт архитектору, выполняет по его рекомендациям.
3. **Репорты канбана — только Monitoring :7**, без дублей в ДМ (т.3). Контракт подписки — группа `-1004300127777`, `--chat-type group`.
4. **Багфикс авто take-into-work** (т.4): после одобренного `GATE:diagnose-review` + ТЗ-решения → `GATE:take-into-work` авто (one-pass) для BUGFIX/BUGFIX-LIGHT; `GATE:diagnose-review` остаётся HITL (never auto).

Из кейсов дня: **slug-guard** (кейс 1) — проверка активного графа по слагу перед `kanban_create`, дубли запрещены (прецедент pfs-notify-link-unprocessed); **freshness-gate** (кейс 4) — уже в v0.2.7, не дублирован.

Ограничения (подтверждены): ядро канбана (`kanban_db.py`, `kanban_db_notify.py`, `TERMINAL_KINDS`) **не трогать**; кроны не создавать автоматически; реализация скиллов — отдельным hermes-feature.

Скиллы-версии (целевые): `tz-workflow` → **2.4.0**, `hermes-feature` → **2.7.0** (запишет HF после «берём в работу»).

## v0.3.1 — инвариант namespace моделей (2026-09-25)

BUGFIX kanban-cursor-model-override (`protocol_violation` / HTTP 400): зафиксирован инвариант двух namespace (воздух Hermes-воркера vs роль `agent -p`), прецедент `t_2c8ee3b2`, **САНКТ-список** под таблицей «Фазы ↔ скиллы». Guards в `GLOSSARY.md` §3/§5.2.10, `kanban-worker` 2.0.2; сноска и столбец таблицы — без переписывания (v0.3.0). Ядро `hermes-agent` / `kanban_db.py` **не трогали**; ops `set-model`/`unblock` — оркестратор.

## v0.3.2 — критерии приёмки AC/IAC в каноне (2026-09-25)

Аддитивная секция (решения Саши 25.09; анализ R1–R5 + bk-178 I1/I2/I3; **вариант 1** для R4.1). Реализация скиллов / `GLOSSARY.md` / preflight **не** в этой записи.

- Норматив: раздел **«Критерии приёмки (AC / IAC) — канон v0.3.2»** (перед «Критерии успеха»).
- Два уровня: итоговые `AC-###` в master-ТЗ пакета (I2, язык необязателен); промежуточные `IAC-##` в `HF:plan` с `path`/`verify`/`depends` (I3). I1 — current/target в новой секции.
- HITL Саши в DEV-цикле ровно две точки: `GATE:take-into-work` после `TZ:finalize` (список AC в чате); `GATE:done` по отчёту прохождения всех AC. `GATE:plan-approve` always auto. `GATE:diagnose-review` не HITL Саши. Требование 4 (авто take-into-work багфиксов) **отменено**.
- One-pass: `GATE:done` never auto (обмен относительно v0.2.2+). Фраза не обходит AC-гейты.
- Тишина: подписка не на все карточки батча; `notify` на корне; `notify+wake` только на AC-гейтах. Ядро / `TERMINAL_KINDS` не трогать.
- Омоним: САНКТ `IAC-01..10` (v0.3.1) ≠ пайплайнные `IAC-##`.
- Перекрытие старых п.8–9/16 до вычистки скиллами на HF. sdd-writer не ставится. Инвентарь — `TZ:finalize`.

## v0.3.3 — leftover one-pass + покрытие моделей фаз (2026-09-25)
- Вычищены leftover «1 проход» под канон v0.3.2 (take-into-work/done never auto; plan-approve always auto; фраза = no-op для гейтов).
- Таблица фаз: RS/MIG/DEC/SK/GATE:go/block-accept; ORCH = deepseek без Cursor.
- epic/aggregate помечены «не этот пайплайн».
- Запрет kanban_create --model без изменений. САНКТ IAC-01..10 без переименования.

## v0.3.4 — leftover GATE:done + САНКТ «Н» D1/D2 (2026-09-25)
- Строка 410 и leftover 700/705/1003/1016: `GATE:done` never auto (и в one-pass); preflight exit 0 необходим, не достаточен; auto только `GATE:plan-approve`.
- САНКТ **Н**: D1 модель карточки vs D2 модель работы внутри (`agent -p --model`).
- Риск: расхождение tz-workflow:233/295 vs hermes-feature (т.4 отменено) — follow-up вне этого пакета.
- Changelog v0.2.x и **левая** колонка таблицы one-pass (~834–836) — история, не норма; канон — правая колонка и §310–317.

## v0.3.5 — контракт маркера AC-delivered (2026-09-25)
BUGFIX-LIGHT `preflight-ac-report-delivery` (диагноз `t_da2b0fa2`, план `_fix_plan_20260925_preflight-ac-report-delivery.md` п.7). Реализация скрипта/тестов/скилла — `HF:impl`, не эта запись.

- Preflight `GATE:done`: требовать маркер `AC-delivered:` в comment карточки GATE:done **и** тело отчёта (comment GATE:done или файл `AC-report_<slug>*.md`). Не принимать список AC с `GATE:take-into-work`. Наличие AC-артефакта ≠ доставка. Не парсить формулировки AC.
- Порядок воркера `GATE:done`: доставка отчёта в диалог Саши **до** запуска preflight; preflight лишь проверяет маркер. Список AC (приёмка) и отчёт AC (доставка) — разные артефакты.

## v0.3.6 — контекст-промпт emit-prompt (full-docs-mandatory) (2026-09-25)
BUGFIX `full-docs-mandatory` (диагноз `t_b6ae7121`, план `_fix_plan_20260925_full-docs-mandatory.md` v2 §3.П.4). Реализация скрипта / тестов / четырёх скиллов — `HF:impl`, не эта запись. Инвентарь — `TZ:finalize`.

- Перед любым `agent -p` по инструменту — `pipeline_context_bundle.py emit-prompt` (`--out /tmp/task.md`); `agent -p` только от выхода emit-prompt (exit 0).
- Skills `BUG:diagnose`: += `cursor-task-context` (3-слойная подача на DX).
- Workspace DX кросс-канон пайплайна (GLOSSARY / DKP / Registries / несколько скиллов): `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ`. `scratch` запрещён.
- CLI `--force` / `--force-bypass` на скрипте отсутствует. Обхода нет: скрипт/check блокируют старт всегда (решение Саши 26.09) для тройки context-bundle.
- Диск-кэш экстрактов не вводить (GLOSSARY §6 «контекст-промпт»).

## v0.3.7 — БЕЗ ИСКЛЮЧЕНИЙ (решение Саши 26.09)
- Канонизированы `emit-prompt` / `check` (`pipeline_context_bundle.py`). Обход тройки context-bundle (`flag-waived` / `--force`) снят: скрипт и `check` блокируют старт всегда, без исключений.

## v0.3.8 — R5 origin-топик инициатора (2026-09-26)
BUGFIX `topic-origin-routing` (`DEV/topic-origin-routing`, диагноз `_fix_plan_20260926_topic-origin-routing.md`). Эта запись — только текст DKP + bump. Инвентарь — `TZ:finalize`. Скиллы — `HF:impl` **после** identity `DEV/tg-topic-duplicate`. Ядро / GLOSSARY / ErrorBus / каталог 7 топиков / `DialogBacklogToKanban` / `jobs.json` — не трогать.

- П.15 / т.3 24.09 **перекрыты**: кейс/граф → origin-топик; Monitoring `:7` = ops/cron; Errors `:11112` отдельно.
- Контракт `notify-subscribe`: обязательны `--thread-id <ORIGIN> --chat-type group`; без `--thread-id` запрещено.
- Набор R5 не менять (корень + AC/HITL-гейты). Leftover «подписать все фазы / багфикс обе» снят.
- `resolve_origin`: корень = env `HERMES_SESSION_*`; дети = копия `thread_id` с подписки корня; DM / CLI / `:11112` → SILENCE (`:7` не подставлять).
- SILENCE-unsubscribe: после create R5 — `notify-list`; SILENCE → снять все telegram-sub (в т.ч. auto-sub DM); иначе одна строка `(group, ORIGIN, notify+wake)`.
- AC-список / AC-отчёт / preflight `GATE:done`: диалог = origin; если origin сам `:7` — дубля нет.
- Стоп-кран: `HF:impl` этой политики не стартует до identity duplicate (предпочтительно `GATE:done`).

## v0.3.9 — TZ:patch-rework topic-origin-routing (2026-09-28)

TZ:patch-rework по `REV:tz`: добавлен подраздел AC-### пакета (подвязан AC-005 DM-тишина), формализован контракт `kanban_notify_subs` (`origin_thread_id` / `origin_chat_type` / `notify_channel`) в «Контракты экосистемы». Семантика R5 не менялась; второго rewrite канала нет. Инвентарь / `MAIN_TZ_INVENTORY.md` — `TZ:finalize`, не эта фаза. Скиллы — `HF:impl` **после** identity `DEV/tg-topic-duplicate`.

**I1.** `current`: семантика R5-origin в тексте v0.3.8, якорей `AC-###` пакета нет, ссылка AC-005 висячая, `kanban_notify_subs` без строки-владельца и без полей origin в таблицах контрактов.  
`target`: якоря AC-001…AC-010 пакета; AC-005 = DM-тишина; контракт `kanban_notify_subs` формализован; в `resolve_origin` шаг 3 — addendum П.1δ (пустая строка `thread_id` = SILENCE).

### Критерии приёмки (AC)

Только пакет `topic-origin-routing` (DKP v0.3.9). Наблюдаемое поведение / команда / артефакт. Этот список — payload `GATE:take-into-work` (дословно в origin-диалог Саше).

### AC-001 — контракт подписки `--thread-id` + `--chat-type group`
В `tz-workflow` и `hermes-feature` команда `hermes kanban notify-subscribe` содержит `--thread-id <ORIGIN>` и `--chat-type group`. Команда без `--thread-id` на группу `-1004300127777` запрещена (0 попаданий `rg` по snippet без `--thread-id`).

### AC-002 — набор R5 не расширен
Подписываются только корень `DEV/<slug>` (или `IDEA/<slug>`) + `GATE:take-into-work` / `GATE:done` / `GATE:go` / `GATE:block-accept` / `IDEA:analyze`. Leftover «подписать все фазы / багфикс обе» снят: `BUG:diagnose` и промежуточные `TZ:*` / `HF:*` / `REV:*` не подписаны. Наблюдаемо: `notify-list` смоука + `rg` скиллов.

### AC-003 — `:7` = ops/cron, `:11112` = Errors
Monitoring `:7` не хардкодится как канал кейса (`--thread-id 7` / «всегда Monitoring :7» в контракте subscribe = 0). Errors `:11112` не встречается в новых R5-подписках. `:7` жив для кронов: `jobs.json` `deliver` этим графом не перенастраивался (diff пуст).

### AC-004 — wake читает `kanban_notify_subs.thread_id`
Канал wake/notify = колонка `kanban_notify_subs.thread_id`, не body/metadata карточки. Наблюдаемо: `notify-list` + SQL read-only к `kanban_notify_subs`; в metadata карточки нет второго поля «канал origin».

<a id="AC-005"></a>
### AC-005 — DM-тишина
Origin = SILENCE (create из DM `400307920` / CLI / Cursor без TG-env): `notify-unsubscribe` снимает **все** telegram-подписки этой задачи, включая auto-sub DM `400307920` и пустой thread. Смоук: 0 telegram-sub на задаче, нет пинга в `:7`.

### AC-006 — пустая строка `thread_id` = SILENCE (П.1δ)
В каноне `resolve_origin` шаг 3 есть строка «пустая строка thread_id = отсутствие origin → не шаг 3, а SILENCE». Наблюдаемо: `rg -n "пустая строка thread_id" DevKanbanPipeline_TZ.md`.

### AC-007 — дети копируют origin корня; dual-sub не мигрируются
`GATE:*` / дети получают `thread_id` копией с подписки корня, не из env воркера. Исторические dual-sub (`''` + `7/thread`) массово не UPDATE. Наблюдаемо: смоук корень из Tools `:3` → гейты `thread_id=3`; в DKP нет массового rewrite исторических sub.

### AC-008 — одна telegram-строка на R5-задачу
При наличии origin: ровно одна строка `(chat_id=-1004300127777, thread_id=ORIGIN, chat_type=group, mode=notify+wake)`. Нет пары `''` + `7`. Наблюдаемо: `notify-list` смоука.

### AC-009 — identity сначала
`HF:impl` origin-routing не стартует до чеклиста identity `DEV/tg-topic-duplicate` (предпочтительно `GATE:done` duplicate + «поднимай»). Наблюдаемо: `kanban_comment` карточки `HF:impl` содержит блок `identity-checklist:` с фактами 4 пунктов (ключ без слота `thread:`; wake `chat_type=group`; SQL `chat_type='thread'` = 0; нет живой вилки `telegram:thread:-1004300127777:*`).

### AC-010 — wake в origin-топике
После «поднимай» duplicate: terminal `blocked` корня смоука будит сессию `group:-1004300127777:<ORIGIN>`; сообщение в том топике; копии в General `:1` и Monitoring `:7` нет (если ORIGIN другой). Наблюдаемо: смоук + отсутствие пинга в чужом топике.

## v0.4.0 — поезд HITL (2026-09-28)

Ломающее поведение HITL. CHANGE канона процесса (`dev-process-rework`). Источник: `appendix_process_rework_20260928.md`. Инвентарь — `TZ:finalize`, не эта фаза. Скиллы — W2.

- Норматив: раздел **«Поезд — канон v0.4.0»** (после v0.3.2). Перекрывает v0.3.2 «две точки never auto» и п.6–8 «Решения Саши» в части гейтов.
- Auto: `GATE:take-into-work` / `GATE:plan-approve` / `GATE:done` / `GATE:diagnose-review`. Never auto: `GATE:go` / `GATE:block-accept`. Показ AC ≠ ожидание **(класс S; класс O — аддитив содержания v0.4.2, не откат этой строки)**.
- Граф = полный батч после brief-closed; unfold хвоста после take-into-work запрещён.
- Preflight exit 0 **достаточен** для `GATE:done`.
- R5 `notify+wake` на AC-гейтах = показ, не hold. Стопкран identity duplicate **не** переносить на этот слаг.
- AC-P01…P12 пакета. GLOSSARY v0.2.11. ProcessImprovement v0.4.3 (аддитивно).

## v0.4.1 — process hardening (2026-09-29)

CHANGE канона процесса (`dev-process-tz-hardening`). Инцидент: `DEV/pfs-task-slug-not-created`. Инвентарь — `TZ:finalize`, не эта фаза. Скрипты/скиллы — W1.

- Норматив: раздел **«Канон процесса v0.4.1»**. GLOSSARY v0.2.12 (§0.1, §3 процесс vs содержание, §5.3 G1–G5).
- Определения граф / карточка / фаза. Закрытый список 10 кейсов в каталоге DKP (добавлены CHANGE-LIGHT, SKILL-DEV, SKILL-CHANGE).
- Процесс = оркестратор (граф на старте); содержание = архитектор; код+тесты = исполнитель; проверка = ревизор. Тестирование без отдельной роли.
- Guard-ы G1–G5: emit-prompt ∈ граф + version; `context-used:` на complete; git-proof impl; structural-preflight на create; запрет архитектору решать ход.
- AC-H01…H10 пакета. Поезд v0.4.0 (auto/never auto) не меняется.
- **Presence log operator-hold (вписано 30.09, номер v0.4.1 не бампался повторно):** классы S/O/C, тег `depends: operator:<verb>`, preflight operator-done / open-questions и AC-D01…D08 живут как аддитив содержания **v0.4.2** (см. changelog v0.4.2). Не второй канон HITL и не откат поезда.

## v0.4.2 — TZ:patch-rework AC-H05b + operator-hold (2026-09-29 / 2026-09-30)

TZ:patch-rework по `REV:tz` (`t_5ad505f0`, 29.09): AC-H05 покрывал только пункты 1–2 G1 (card ∈ граф, version/mtime). Пункт 3 G1 (`emit-prompt` перед `HF:test` / `HF:docs-handoff` при красном G3) не наблюдался — дыра инцидента `DEV/pfs-task-slug-not-created` (тест по виртуальному коду). Инвентарь — `TZ:finalize`, не эта фаза. GLOSSARY не затронут той правкой (AC пакета DKP).

- Добавлен **AC-H05b**: `emit-prompt --card` на `HF:test` / `HF:docs-handoff` при untracked/uncommitted `HF:impl` → exit 1; тест и документирование **не** стартуют (`agent -p` не вызывается). Смоук на фикстуре kanban.db.
- G1 п.3: уточнена наблюдаемость (exit 1 на старте фазы ≠ G3 на `GATE:done` / AC-H07). AC-H01…H04, AC-H06…H10 без изменения смысла; AC-H05 — ссылка на AC-H05b для п.3.
- Ядро канбана, Gateway, кроны, роли, фазы GLOSSARY §5 — не менялись.

**TZ:patch 30.09 (волна W0 done-gate, `t_3a71237e`, номер v0.4.2 сохранён).** Содержание operator-hold, которого не было при накате версии. Источник: `_fix_plan_done-gate_20260929.md` П.1. Скрипты/скиллы — W1–W2, не эта запись. Поезд v0.4.0 (auto/never auto на take-into-work / plan-approve / done / diagnose-review) **не** откатывается.

- Секция «Поезд — канон v0.4.0»: таблица S/O/C; участие класса O блокирует `GATE:done` + напоминается сторожем; класса S — нет; тег `depends: operator:<verb>`; снятие `operator-done:` + evidence.
- «Гейты HITL»: `review-required: operator-action:<verb>` на корне или `GATE:done` — не auto-complete (hold, fail preflight); не путать с «ждать готово».
- Preflight `--mode done`: п.10 operator-done (все holds сняты), п.11 open-questions empty. В плане done-gate относительно чеклиста v0.4.0 (1–7) это были «п.8–9»; п.8–9 master заняты G3/G2 v0.4.1.
- AC-D01…D08 пакета done-gate. GLOSSARY v0.2.12 (слой operator-AC). Зеркало одной строкой: ProcessImprovement / `_TZ-WORKFLOW-RULES.md`. `DialogBacklogToKanban_TZ.md` не трогать.

## v0.4.3 — сторож rule3: русские вердикты REV и REQUEST-CHANGES (2026-10-01)

BUGFIX `kanban-stuck-russian-verdicts` (диагноз `_fix_plan_20261001`, карточка `BUG:diagnose` / `TZ:patch`). Эта запись — **только текст DKP + bump**. Инвентарь `MAIN_TZ_INVENTORY.md` — `TZ:finalize`, не эта фаза. Код сторожа / тесты — `HF:impl` после `GATE:take-into-work`. GLOSSARY, `DialogBacklogToKanban_TZ.md`, ядро канбана, `jobs.json`, крон, gateway — **не трогать**.

Канон AC-P05 **не переписывается**: поведение остаётся «REV changes → rework-ребёнок рабочей фазы; голого unblock нет; повторный REV с новым ключом». Имя токена в AC-P05 не обязано быть единственным regex. Этот пакет фиксирует, **как** сторож `kanban_stuck_monitor.py` **видит** вердикт.

**I1.** `current`: `rule3` ищет только `CHANGES_REQUIRED|REQUEST_CHANGES` в `tasks.result` + `last_failure_error` + последних 8 комментариях. Живой вердикт REV лежит в `task_events.payload.reason` (`kind='blocked'`), часто по-русски или с дефисом `REQUEST-CHANGES`. Карточки `REV:*` зависают в `blocked`; AC-P05 не выполняется.  
`target`: `rule3` читает latest `blocked.payload.reason` первым; матчит EN (underscore / hyphen / space) и RU («требует правок» / «требуется доработка»); APPROVE / УТВЕРЖДАЮ и голое `needs_input` не дают rework; открытый rework-ребёнок → spawn no-op.

Проверено read-only `~/.hermes/kanban.db` (2026-10-01): `t_cc070a0d` (`rework required` + «Требуется доработка» в payload, result/lfe пустые); `t_adeedb30` (`REQUEST-CHANGES`); `t_4832adad` («ТРЕБУЕТ ПРАВОК»); `t_2e66fdbe` (`REQUEST_CHANGES` только в payload). Текущий `rule3` на всех молчит.

Сторож **не ломает** spawn: он **не видит** вердикт. Комментарий `t_cc070a0d` формулирует дефект прозой без EN-токена — payload.reason единственный устойчивый канал.

### Что чинить (5 пунктов)

1. **Детект (regex).** После `NUDGE_RE`: `REV_CHANGES_RE` (`CHANGES[_ \-]REQUIRED` | `REQUEST[_ \-]CHANGES` | `rework required` | `defect confirmed` | `требует(?:ся)? правок` | `требует(?:ся)? доработк[аие]`, `re.I`) и `REV_APPROVE_RE` (`\bAPPROVE(?:D)?\b` | `УТВЕРЖДАЮ`). **Не** матчить голое `needs_input` (это `block_kind` JSON, ложный rework на любой blocked REV) и голое `rework` (comment «superseded: rework t_…» / title ребёнка).
2. **Канал вердикта.** Latest `task_events` `kind='blocked'` → `payload.reason`. Хелперы: `payload_reason` (`json.loads` → `reason`; не JSON / нет ключа → сырой payload; пусто → `""`); `is_rev_changes_verdict` (`REV_CHANGES_RE.search`). APPROVE в том же тексте **не** отменяет CHANGES; чистый APPROVE/УТВЕРЖДАЮ без changes → False. `Board._load`: зеркально `proto_violations` грузить `blocked_reasons` (`SELECT task_id, payload … WHERE kind='blocked' ORDER BY id DESC`, первая встреча task_id = latest). Не фильтровать по статусу — `rule3` сам требует `status=='blocked'`.
3. **Приоритет источника в `rule3`** (не конкатенация: старый «ТРЕБУЕТ ПРАВОК» в comments + новый «УТВЕРЖДАЮ» в reason дали бы ложный rework): (1) `board.blocked_reasons[tid]`; (2) иначе `result` + `last_failure_error`; (3) иначе последние 8 `task_comments.body` (из `board.comments`, без повторного SQL). Первый источник, в котором есть **либо** CHANGES-токен, **либо** APPROVE-токен — единственный, по которому зовём `is_rev_changes_verdict`. Нет токена нигде → молчание. Фильтр карточки без изменений: `phase.startswith("REV:")` и `status=="blocked"`.
4. **Guard открытого rework.** В `spawn_rework_child` **до** `kanban create`: если у `work_id` уже есть ребёнок с `"rework"` в title и `status ∉ {done, archived}` → no-op (ключ `n` не инкрементировать). Done/archived rework + новый blocked REV того же `work_id` → следующий `n` (повторный цикл AC-P05). Голый `unblock` REV по-прежнему запрещён. Маппинг фаз (`REV:tz`→`TZ:patch`, `REV:plan`→`HF:plan`) и формат ключа `devpipe:…:rework:N` **не** менять.
5. **Тесты.** В `test_kanban_stuck_monitor.py`: колонка `payload TEXT` у `task_events` в `_init_schema`; хелпер `_blocked(conn, task_id, reason, kind="needs_input")`; восемь новых тестов `rule3` (dry-run, без `hermes kanban` на живой доске). Существующие тесты 7–8 / `test_zero_incidents_silent` остаются зелёными.

### Пофайловый план

#### 1.1 `~/.hermes/scripts/kanban_stuck_monitor.py` — единственный runtime-файл

Ядро `kanban_db.py` / dispatcher **не** трогать. Мутации по-прежнему только `hermes kanban create` через уже существующий `spawn_rework_child`.

| Место (срез 2026-10-01) | Правка |
|---|---|
| константы после `NUDGE_RE` (~стр. 68–70) | `REV_CHANGES_RE`, `REV_APPROVE_RE` |
| хелперы после `is_cursor_slug` (~стр. 101–102) | `payload_reason`, `is_rev_changes_verdict` |
| `Board._load()` (стр. 120–163) | `self.blocked_reasons`; SELECT `payload` у `kind='blocked'` |
| `Monitor.rule3_rev_changes_required()` (стр. 371–387) | приоритет источника §п.3 |
| `spawn_rework_child` (стр. 291–335) | guard открытого ребёнка **до** create |

Тестовая схема pytest **без** колонки `payload` сломает `_load` (сторож ловит exception и exit 0 → молчание). Чинится в 1.2.

#### 1.2 `~/WorkVault/Registries/test_kanban_stuck_monitor.py`

Докстринг расширить с «правила 7–8» на rule3. `_init_schema`: `task_events.payload TEXT` (как живая БД). `_blocked` — INSERT JSON `{"reason": reason, "kind": kind}`.

| Тест | Фикстура | Ожидание |
|---|---|---|
| `test_rule3_payload_rework_required` | REV:plan blocked, result/lfe/comments пустые, payload = текст `t_cc070a0d` | `3.rework` |
| `test_rule3_payload_request_hyphen` | как `t_adeedb30`: `REQUEST-CHANGES` только в payload | `3.rework` |
| `test_rule3_payload_ru_trebuet_pravok` | как `t_4832adad`: «ТРЕБУЕТ ПРАВОК» только в payload | `3.rework` |
| `test_rule3_compat_underscore_in_result` | result=`CHANGES_REQUIRED`, событий blocked нет | `3.rework` (регресс EN) |
| `test_rule3_approve_not_rework` | payload «вердикт УТВЕРЖДАЮ» / `APPROVE` | нет `3.rework` |
| `test_rule3_needs_input_kind_only` | payload JSON `kind=needs_input`, reason без вердикта («emit-prompt G1…») | нет `3.rework` |
| `test_rule3_source_priority_reason_over_old_comment` | comment «ТРЕБУЕТ ПРАВОК», latest blocked reason «УТВЕРЖДАЮ», status=blocked | нет `3.rework` |
| `test_rule3_skip_if_open_rework_exists` | changes-вердикт + child `HF:plan rework #0` status=todo | нет второго `3.rework` |

### IAC (LIGHT: 1–3 строки)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `~/.hermes/scripts/kanban_stuck_monitor.py` (`_load`, `rule3_rev_changes_required`, `payload_reason` / `is_rev_changes_verdict`, guard в `spawn_rework_child`) | `python3 -m pytest ~/WorkVault/Registries/test_kanban_stuck_monitor.py -k rule3 -q` → все новые тесты §1.2 passed | — | AC-R01…R08, AC-P05: вердикт из `blocked.payload.reason`; EN+RU; не APPROVE; guard открытого ребёнка |
| **IAC-02** | `~/WorkVault/Registries/test_kanban_stuck_monitor.py` (схема `payload` + тесты rule3) | `python3 -m pytest ~/WorkVault/Registries/test_kanban_stuck_monitor.py -q` → весь файл зелёный, включая rule7/8 и zero-incidents | IAC-01 | AC-R09: нет регресса сторожа |
| **IAC-03** | тот же скрипт, dry-run | `python3 ~/.hermes/scripts/kanban_stuck_monitor.py --dry-run --db <копия фикстуры с репликой трёх payload>` → в отчёте `3.rework` на RU/hyphen, нет `3.rework` на APPROVE; **не** `--db` боевого `kanban.db` с мутацией | IAC-01 | AC-R01, AC-R05, AC-R10: ручной смоук без записи в live |

Нет `depends: operator:` (класс S). Нет `depends: operator:` на IAC.

### Точки проверки (сокращённо)

1. Реплика `t_cc070a0d` / `t_adeedb30` / `t_4832adad`: пустые result/lfe/comments + payload.reason → `3.rework`.
2. Старый путь: `CHANGES_REQUIRED` в `result` без события `blocked` → `3.rework`.
3. `REQUEST-CHANGES` (дефис) ≠ только underscore.
4. «ТРЕБУЕТ ПРАВОК» / «требуется доработка» при любом регистре.
5. УТВЕРЖДАЮ / APPROVE → нет rework.
6. `"kind": "needs_input"` в JSON без changes-токена в reason → нет rework.
7. Открытый rework-ребёнок → второй create на том же tick/следующем не планируется.
8. Карточка не `REV:*` или не `blocked` → rule3 молчит.
9. 0 инцидентов → тишина (exit 0, нет сводки).
10. Боевой `kanban.db` на impl **не** мутировать; после выкладки первый live-tick — смотреть `--dry-run` оркестратором.

### Что НЕ трогать (этот пакет)

- Ядро канбана (`kanban_db.py`, dispatcher, статусы, `auto_decompose`), скилл `kanban-worker`.
- `jobs.json`, крон сторожа, gateway (не рестартовать).
- Живые карточки: impl **не** unblock и не `kanban create` на боевой доске; реплика — pytest-фикстура / копия БД для `--dry-run`.
- Тексты канона AC-P05 в разделе «Поезд — канон v0.4.0» и GLOSSARY — не переписывать; только фиксация поведения сторожа.
- `DevKanbanPipeline_TZ.md` кроме **этой** changelog-секции и frontmatter bump; `GLOSSARY.md`; `DialogBacklogToKanban_TZ.md` (DEV-цикл не его).
- Маппинг фаз / формат ключа `spawn_rework_child` (кроме guard открытого ребёнка).
- Сущности / cron / `.env` / манифест / `MAIN_TZ_INVENTORY.md` (инвентарь — `TZ:finalize`).
- Опциональный leftover (не в объём LIGHT): одна строка в `dev-pipeline-reliability` «токены RU + `payload.reason`». Если оркестратор возьмёт полный BUGFIX — можно добавить; для LIGHT не трогать.

Классификация **BUGFIX-LIGHT** (≤3 файла: скрипт + тесты, вне ядра / shared / сущностей / cron / `.env` / манифеста) — **рекомендация оркестратору** после `GATE:diagnose-review` (AC-H10). Архитектор граф не строит и LIGHT не включает.

### Связи с экосистемой

- **Сторож канбана** `~/.hermes/scripts/kanban_stuck_monitor.py` (правило 3 / appendix `appendix_process_rework_20260928.md` §1.5 п.3): единственный runtime этого пакета; исполняет AC-P05, не LLM.
- **Ревизор канона** `REV:tz` / `REV:plan`: пишет вердикт в `kanban_block` → `task_events.payload.reason`; сторож читает этот канал. Не меняет промпт ревизора.
- **Поезд v0.4.0 AC-P05**: поведение «changes → rework-ребёнок» без голого unblock; этот пакет закрывает дыру детекта.
- **Appendix §7** («Сторож плодит rework-дубли»): закрывается guard открытого ребёнка, не сменой ключа.
- `DialogBacklogToKanban` — **не** в scope (IDEA-inbox / DECOMM DialogBacklog, не DEV-цикл сторожа).
- `ErrorBus` / новые кроны / `ORCH:shared-state` — не нужны (тот же job сторожа).

### Критерии приёмки (AC)

Только пакет `kanban-stuck-russian-verdicts` (DKP v0.4.3). Наблюдаемое поведение / команда / артефакт. **Класс S** (показ ≠ ожидание). **Нет** `depends: operator:` на этих AC. Payload `GATE:take-into-work` этого слага. Код/тесты закрывают AC на `HF:impl` / `HF:test`; эта запись фиксирует канон.

### AC-R01 — payload.reason первичный канал
Реплика `t_cc070a0d` / `t_adeedb30` / `t_4832adad`: `REV:*` `blocked`, пустые `result` / `last_failure_error` / comments, вердикт только в `task_events.payload.reason` → сторож планирует `3.rework`. Наблюдаемо: pytest `-k rule3` (`test_rule3_payload_rework_required`, `test_rule3_payload_request_hyphen`, `test_rule3_payload_ru_trebuet_pravok`).

### AC-R02 — регресс EN underscore в result
`result=CHANGES_REQUIRED`, событий `blocked` нет → `3.rework`. Наблюдаемо: `test_rule3_compat_underscore_in_result`.

### AC-R03 — дефис REQUEST-CHANGES
Токен `REQUEST-CHANGES` (и `CHANGES-REQUIRED`) матчится так же, как underscore. Regex не равен только `REQUEST_CHANGES`. Наблюдаемо: `test_rule3_payload_request_hyphen`.

### AC-R04 — русские вердикты
«ТРЕБУЕТ ПРАВОК» / «требует правок» / «требуется доработка» / «Требуется доработка» при любом регистре (юникод-кейс `re.I`) → `3.rework`. Наблюдаемо: `test_rule3_payload_ru_trebuet_pravok`.

### AC-R05 — APPROVE / УТВЕРЖДАЮ не rework
Payload «вердикт УТВЕРЖДАЮ» / `APPROVE` / `APPROVED` без CHANGES-токена → нет `3.rework`. Наблюдаемо: `test_rule3_approve_not_rework`.

### AC-R06 — голое needs_input не вердикт
JSON payload `"kind": "needs_input"` при reason без changes-токена (например «emit-prompt G1…») → нет `3.rework`. Наблюдаемо: `test_rule3_needs_input_kind_only`.

### AC-R07 — приоритет latest blocked.reason над старым comment
Comment «ТРЕБУЕТ ПРАВОК», latest blocked reason «УТВЕРЖДАЮ», status=blocked → нет `3.rework` (не конкатенация источников). Наблюдаемо: `test_rule3_source_priority_reason_over_old_comment`.

### AC-R08 — guard открытого rework-ребёнка
Changes-вердикт + child с `"rework"` в title и `status ∉ {done, archived}` → второй `3.rework` / второй `kanban create` не планируется; ключ `n` не инкрементируется. Done/archived rework + новый blocked REV того же `work_id` → следующий `n`. Наблюдаемо: `test_rule3_skip_if_open_rework_exists`.

### AC-R09 — фильтр фазы/статуса и тишина
Карточка не `REV:*` или не `blocked` → rule3 молчит. 0 инцидентов → exit 0, нет сводки. Существующие тесты правил 7–8 зелёные. Наблюдаемо: pytest всего файла `-q`; `test_zero_incidents_silent`.

### AC-R10 — боевую доску не мутировать
`HF:impl` / `HF:test` не пишут в live `~/.hermes/kanban.db` (нет unblock, нет create). Смоук IAC-03 — `--dry-run --db` **копии** фикстуры. Первый live-tick после выкладки смотрит оркестратор `--dry-run` на боевой БД **без** мутации в этой фазе.

## v0.4.4 — guard закрытия корня / premature-close / rule9 (2026-10-13)

**TZ:finalize 13.10.2026 (master 0.4.4).** Текст пакета `kanban-orchestration-root` зафиксирован. Открытых вопросов нет. Инвентарь `MAIN_TZ_INVENTORY.md` обновлён (0.4.3→0.4.4). Код сторожа / тесты ждут `HF:impl`. Pre-impl маркеры «инвентарь — не этот ход» сняты. HITL `needs_input`→triage (П.8–П.13 `_fix_plan_20261012.md`, кейс `DEV/kanban-hitl-routed-to-triage`) **не** этот пакет.

BUGFIX `kanban-orchestration-root` (диагноз `_fix_plan_20261012.md`, карточки `BUG:diagnose` `t_079caef7` / `REV:plan` `t_6c839d91` / `TZ:patch`). Эта запись — **канон-текст DKP + bump** (П.2 плана + классы сторожа П.1). Код сторожа / тесты — `HF:impl` после `GATE:take-into-work`. Ядро `kanban_db*.py` / `cli.py`, `GLOSSARY.md`, `DialogBacklogToKanban_TZ.md`, `jobs.json`, крон, gateway — **не трогать**. Авто-разворот хвоста через LLM (вариант 1) **не** основной. Глобальный `agent.max_turns` **не** поднимать (П.6 — per-task, не этот пакет).

Канон поезда v0.4.0 / G5 **не переписывается**. AC-H10 (LIGHT = оркестратор, не архитектор) **сохраняет смысл**; leftover «перепись хвоста» после `GATE:diagnose-review` снят (rework #1). Этот пакет фиксирует дыру, которой канон «полный батч / unfold после take-into-work запрещён» **не** покрывал: BUGFIX-граф без хвоста в первом батче умирает после DX; rule8 требует `HF:plan` и пропускает LIGHT; корень часто уже `done` до `GATE:done`. **TZ:patch rework #0 (13.10, REV:tz CHANGES_REQUIRED):** двухшаговый unfold снят — багфикс-батч = один `kanban_create` полного графа. **TZ:patch rework #1 (13.10):** leftover AC-H10 «перепись хвоста» / «сужение после diagnose-review» вычищен из живого канона; IAC-01 verify покрывает «не двухшаговый unfold». Версия 0.4.4 без bump (тот же пакет). ИНВАРИАНТ / rule9 / питфолл без изменения.

**I1.** `current`: первый батч = корень+BUG:diagnose+GATE:diagnose-review+LIGHT/полный хвост целиком; двухшагового unfold нет; rule8 broken-tail skip LIGHT; `kanban_complete` корня до `GATE:done` запрещён словами, сторож на раннее закрытие не эскалирует. `protocol_violation` читается как «модель ответила текстом» / гипотеза MarkdownV2.  
`target`: одно-батчевый **полный** граф BUGFIX; двухшаговый unfold запрещён/не существует; **ИНВАРИАНТ** «корень done только после создания хвоста и `GATE:done`» и rule9 (два класса) без изменения; guard закрытия корня; сторож `rule9_bugfix_broken_tail` с двумя классами (живое → block; раннее закрытие → operator-action premature-close, не nudge); питфолл `protocol_violation` разведён (billing/транспорт ≠ формат `{body}` ≠ MarkdownV2).

### Что чинить (канон; код — `HF:impl`)

1. **ИНВАРИАНТ / guard закрытия корня (П.2).** Корень `DEV/<slug>` → `kanban_complete` / status=done **только** после создания хвоста и `GATE:done` = done. Для BUGFIX-LIGHT хвост = `TZ:patch→TZ:finalize→GATE:take-into-work→HF:impl→HF:test→HF:docs-handoff→GATE:done` (parents от `GATE:diagnose-review`; все узлы — в том же create-батче); `GATE:diagnose-review` parents=`[BUG:diagnose]`. Соответствует GLOSSARY §5.2 инвариант 3. Нарушение = раннее закрытие корня, не допустимый сценарий.
2. **Полный батч BUGFIX.** Бугфикс-граф создаётся одним `kanban_create`-батчем (корень+BUG:diagnose+GATE:diagnose-review+LIGHT/полный хвост), диспетчер подхватывает после done DX сразу. Не авто-разворот LLM, не unfold после take-into-work, не двухшаговый unfold.
3. **Сторож `rule9_bugfix_broken_tail` (П.1) — два класса, не смешивать.** Живой корень без `GATE:diagnose-review` после done DX → `review-required: broken-bugfix-tail`. Root already done и `GATE:done` нет/не done → `operator-action: premature-close` (needs-operator restore/re-open, **не** nudge). На 4 мёртвых прецедентах — ветка premature-close. Рабочие (`mfl-*`, `pfs-task-slug-fix`) не тревожить.
4. **Питфолл формата блока / `protocol_violation` (явление B).** Не единая причина и не Telegram MarkdownV2 (нефатальный WARNING notifier). Три разных класса — см. подраздел ниже. Дифф ядра billing→exit 75 — П.3, только с ревизором, **не этот пакет**.

### Питфолл: формат блока и `protocol_violation` (не смешивать)

| Класс | Симптом | Что это | Что делать / не делать |
|---|---|---|---|
| **Billing / транспорт** | HTTP 403 `Key limit exceeded`; CLI rc=0; диспетчер `protocol_violation`; быстрые ретраи без backoff. Прецедент `t_273cf112` | Известный класс «фатал провайдера → rc=0 → protocol_violation». **Не** формат тела карточки | Канон-фикс ядра (П.3: маппинг в exit 75 / cooldown) — только с ревизором. До него сторож П.4: cooldown, не ретраить тот же тик. Не чинить как MarkdownV2 |
| **Литерал-плейсхолдер `{body}`** | Body карточки = `{body}` / `{title}` / пустой шаблон; воркер не интерпретирует задачу; block_loop. Прецедент `t_fc25892c` run 905 (в БД единично) | **Настоящий** дефект формата: spec не подставился | Сторож П.5: карточка `ready`/`running` с литералом `{body}`/`{title}` → block `needs_input` корня + алерт оркестратору. **Не** давать воркеру «угадывать» мусор |
| **Бюджет итераций 90/90** | `Iteration budget exhausted (90/90)` на большой one-pass. Прецедент eco-config-w2 run 911 | `agent.max_turns`=90, не таймаут по времени | Per-task `max_turns_override` / разбить на волны. **Не** поднимать глобальный `agent.max_turns` ради одного кейса (П.6 — не этот пакет) |
| **MarkdownV2 `.` reserved** | WARNING notifier-адаптера, fallback на plain text | Нефатальный warning. К жизни воркера **не** относится | **Не** чинить как причину подвеса (опровергнуто `_fix_plan_20261012.md`) |

Закрытый словарь operator-глаголов Саши (`поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n`) **не** расширяется: `premature-close` — reason сторожа / needs-operator на restore графа, не новая R3-фраза Саши.

### IAC (LIGHT: 1–3 строки)

| IAC | path | verify | depends | covers |
|---|---|---|---|---|
| **IAC-01** | `TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` (граф BUGFIX, Полный батч BUGFIX, ИНВАРИАНТ, rule9-таблица, питфолл) | `rg -n "Полный батч BUGFIX|корень\\+BUG:diagnose\\+GATE:diagnose-review|не двухшаговый unfold|один .{0,2}kanban_create|premature-close|rule9_bugfix_broken_tail|guard закрытия корня" DevKanbanPipeline_TZ.md` → секция графа + changelog v0.4.4 + AC-B02; предписывающего «перепись хвоста» в живом каноне нет (только отрицания и changelog rework #1); `version: 0.4.4` в YAML | — | AC-B01, AC-B02, AC-B06, AC-B07 |
| **IAC-02** | `~/.hermes/scripts/kanban_stuck_monitor.py` (`rule9_bugfix_broken_tail`) | unit: корень жив + DX done без `GATE:diagnose-review` → block `broken-bugfix-tail`; unit: root done + DX done без diagnose-review → `operator-action: premature-close` (не nudge); pytest `-k rule9` | — | AC-B03, AC-B04, AC-B05 |
| **IAC-03** | тот же скрипт, `--dry-run` | `--dry-run --db` **копии** живого снимка → 4 мёртвых слага (`pfs-empty-entity-guard`, `pfs-sink-aid-unrouted`, `pfs-task-slug-picker`, `pfs-notify-stale`) = premature-close; `mfl-*` / `pfs-task-slug-fix` тишина. **Не** мутировать live `kanban.db` | IAC-02 | AC-B05, AC-B08 |

Нет `depends: operator:` на этих AC/IAC (класс S для текста канона; restore мёртвых графов — ops оркестратора после сторожа, не hold этого пакета).

IAC-01 закрыт на `TZ:patch` и подтверждён этой `TZ:finalize`. IAC-02/IAC-03 — `HF:impl` / `HF:test`.

### Точки проверки (сокращённо)

1. В живом каноне графа (не только changelog): ИНВАРИАНТ «корень done только после хвоста/`GATE:done`» + таблица двух классов rule9.
2. После done `BUG:diagnose` карточка `GATE:diagnose-review` уже `ready` (создана в первом батче) — диспетчер подхватывает сразу; второго хода unfold нет.
3. Unfold после take-into-work по-прежнему запрещён; двухшагового DX-unfold нет (не исключение).
4. rule8 / AC-D06 не выдаются за покрытие LIGHT.
5. Питфолл: billing-`protocol_violation` ≠ `{body}` ≠ MarkdownV2.
6. 4 мёртвых графа → premature-close; рабочие эталоны тишина.
7. Ядро / глобальный `max_turns` / авто-LLM-unfold в этом пакете не меняются.

### Что НЕ трогать (этот пакет)

- Ядро канбана (`kanban_db*.py`, `cli.py`, dispatcher, статусы, `auto_decompose`) — П.3 только с ревизором, отдельным диффом.
- Авто-разворот хвоста через LLM как основной (вариант 1).
- Глобальный `agent.max_turns`.
- `GLOSSARY.md` (зеркало инварианта 3 уже есть; словарём R3 не расширять); `DialogBacklogToKanban_TZ.md`.
- `jobs.json`, крон сторожа, gateway (не рестартовать).
- Живые карточки: `TZ:patch` / `TZ:finalize` **не** restore/re-open мёртвых графов и не мутируют `kanban.db`.
- `MAIN_TZ_INVENTORY.md` — обновлён на этой `TZ:finalize` (0.4.4); повторно не править на `HF:impl`.
- `_route_block` / genuine HITL `needs_input` → triage (П.8–П.13 `_fix_plan_20261012.md`, кейс `DEV/kanban-hitl-routed-to-triage`) — **не** этот пакет (ядро канбана, отдельный граф).
- Поезд v0.4.0 auto/never auto; G5; AC-H10 (LIGHT — оркестратор **на старте**, хвост в том же батче; не перепись после DX).

Классификация **BUGFIX-LIGHT** (≤3 файла: канон-текст сейчас; скрипт сторожа + тесты на `HF:impl`, вне ядра / сущностей / cron / `.env` / манифеста) — **решение оркестратора/Саши на старте** (AC-H10: LIGHT = оркестратор, не архитектор); карточки выбранного хвоста — в том же create-батче. Архитектор граф не строит и LIGHT не включает.

### Связи с экосистемой

- **Сторож канбана** `~/.hermes/scripts/kanban_stuck_monitor.py` (rule8 broken-tail + новое rule9): runtime П.1; исполняет guard закрытия корня, не LLM.
- **Оркестратор (Сирень):** строит **полный граф одним батчем** сразу после `GATE:brief-closed` (BUGFIX — на старте кейса, в том же `kanban_create`); вторых unfold-ходов нет.
- **Поезд v0.4.0 / GLOSSARY инвариант 3:** `kanban_complete` корня до `GATE:done` запрещён; этот пакет закрывает дыру детекта и раннего закрытия.
- **П.3–П.6** плана `_fix_plan_20261012.md` (billing exit 75, cooldown, `{body}`-guard runtime, per-task max_turns) — **не** эта запись; питфолл зафиксирован, код — отдельные шаги/`HF:impl` с ревизором где ядро.
- `DialogBacklogToKanban` — **не** в scope.
- `ErrorBus` / новые кроны / `ORCH:shared-state` — не нужны (тот же job сторожа).

### Критерии приёмки (AC)

Только пакет `kanban-orchestration-root` (DKP v0.4.4). Наблюдаемое поведение / команда / артефакт. **Класс S** (показ ≠ ожидание). **Нет** `depends: operator:` на этих AC. Payload `GATE:take-into-work` этого слага. Текст канона закрывает AC-B01/B02/B06/B07 на `TZ:patch`/`TZ:finalize`; сторож/тесты — `HF:impl` / `HF:test`.

### AC-B01 — инвариант: корень done только после хвоста
В разделе «Граф карточек» (BUGFIX / BUGFIX-LIGHT) есть явный **ИНВАРИАНТ (guard закрытия корня)**: `kanban_complete` корня до создания хвоста и `GATE:done` = done **запрещён**. Наблюдаемо: `rg -n "guard закрытия корня" DevKanbanPipeline_TZ.md` в теле графа, не только changelog.

### AC-B02 — полный батч BUGFIX (один create-батч всего графа)
Полный граф BUGFIX создаётся в одном `kanban_create`-батче (корень+BUG:diagnose+GATE:diagnose-review+LIGHT/полный хвост). После done DX `GATE:diagnose-review` уже `ready`, диспетчер подхватывает сразу; unfold после take-into-work по-прежнему запрещён; авто-разворот LLM не основной. Двухшагового unfold нет (нет «переписи хвоста» после diagnose-review). Наблюдаемо: блок «Полный батч BUGFIX» в графе; AC-H10 без команды второго хода.

### AC-B03 — класс «корень ещё жив»
`BUG:diagnose` done, нет `GATE:diagnose-review`, root status ≠ done → сторож планирует `kanban block` с `review-required: broken-bugfix-tail:`. Наблюдаемо после `HF:impl`: pytest unit на этот класс.

### AC-B04 — класс «раннее закрытие корня» = operator-action premature-close
Root status=done **и** `GATE:done` нет в графе или не done → сторож планирует `operator-action: premature-close` (needs-operator restore/re-open), **не** alert+nudge. На 4 мёртвых прецедентах — эта ветка, не «корень ещё жив». Наблюдаемо после `HF:impl`: unit + `--dry-run` на копии БД.

### AC-B05 — рабочие графы не тревожить
`mfl-exchange-lxml`, `mfl-digest-lxml`, `pfs-task-slug-fix` (корень+DX, затем diagnose-review, затем хвост) → rule9 тишина. Наблюдаемо: IAC-03.

### AC-B06 — питфолл protocol_violation / формат блока
В DKP зафиксированы четыре несмешиваемых класса: billing/транспорт rc=0; литерал `{body}`; 90/90 per-task; MarkdownV2 не причина подвеса. Наблюдаемо: `rg -n "питфолл.*protocol_violation|Литерал-плейсхолдер" DevKanbanPipeline_TZ.md`.

### AC-B07 — YAML bump 0.4.4
Frontmatter `version: 0.4.4`, `date: 2026-10-13`, `last-section-added` указывает `TZ:finalize` этой секции. Инвентарь `MAIN_TZ_INVENTORY.md`: строка DevKanbanPipeline = 0.4.4 / 2026-10-13.

### AC-B08 — боевую доску не мутировать этой записью
`TZ:patch` / `TZ:finalize` не делают restore/re-open мёртвых графов и не пишут в live `kanban.db`. Смоук rule9 — `--dry-run --db` копии. Первый live-tick после выкладки сторожа — оркестратор.

### Критерии готовности ТЗ (шаг 4 `tz-workflow`)

- [x] Цель одним предложением (ИНВАРИАНТ / guard закрытия корня + rule9 два класса)
- [x] Входы/выходы явны (граф BUGFIX, сторож, оркестратор)
- [x] Шаги атомарны (канон-текст сейчас; код сторожа — `HF:impl`)
- [x] Успех проверяем (AC-B01…B08, IAC-01…03)
- [x] «Что НЕ трогать» заполнен (ядро, LLM-unfold, global max_turns, GLOSSARY, HITL-route, live `kanban.db`)
- [x] Связи с экосистемой заполнены
- [x] Контракты: новых полей нет; питфолл `protocol_violation` вшит в таблицу рисков
- [x] Открытые вопросы — нет (нечего спрашивать Сашу; restore мёртвых графов — ops оркестратора после сторожа, не hold этого пакета)
- Финализация файла на диске ≠ стоп реализации: `GATE:take-into-work` auto после показа AC (класс S)
