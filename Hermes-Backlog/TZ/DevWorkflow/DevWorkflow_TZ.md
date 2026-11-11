---
tool: DevWorkflow
type: infra_plan
title: "Процесс изменения Hermes/USERTOOLS: одна задача, FIFO и непрерывное продолжение"
version: 0.10.4
date: 2026-11-11
status: draft
author: архитектор (Codex exec)
case: BUGFIX
slug: adresnyy-remont-publikatsii-extract-v-kompressor
previous_slug: vnedrenie-konsolidirovannogo-master-tz-devworkfl
last-section-added: '2026-11-11 — Б60.1.2/60.3.4/60.8: CAPCONST-R10, однократные 90% публичных максимумов; draft до собственной REV:tz/TZ:finalize; CAP-R3 открыт'
depends_on:
  - TZ/GLOSSARY.md >= 0.2.15
  - TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md >= 0.4.4
  - TZ/TZ-Workflow/TZ-storage-system.md >= 1.1
  - TZ/EcosystemIntegration/EcosystemIntegration_TZ.md >= 0.7.0
  - TZ/ErrorBus/ErrorBus_TZ.md >= 0.3.1
  - TZ/ProcessImprovement/ProcessImprovement_TZ.md >= 0.4.3
consumers:
  - skill:dev-workflow (единственный активный процесс после W4)
  - profile:default (Сирень = оркестратор)
  - TZ/MAIN_TZ_INVENTORY.md
reuse_first: "не USERTOOL; код в Registries/pipeline/; скилл в hermes-workspace; ядро hermes-agent не трогать"
supersedes_runtime: TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md
---

# DevWorkflow — мастер-ТЗ процесса разработки

Консолидированный master по принятому CHANGE; границы документного перехода и объём внедрения — Б61. Основание первичного перехода — согласованный RESEARCH-проект и собственная REV:tz от 09.11.2026. Адресная нормативная дельта от 10.11.2026 по решению Саши — Б61.4; эта draft-редакция ожидает своей независимой REV:tz и TZ:finalize. Прежнее согласование не утверждает новые нормативные байты. Документная финализация требует разрешённой синхронизации master и inventory по Б15; evidence первичного перехода и приложения сохраняются отдельно. Адресная дельта NORM-R3 ремонта компрессора от 10.11.2026 — Б60.1/60.3.3/60.3.4; она согласована собственной REV:tz и документно финализирована по Б60.1; draft другого CHANGE в Б61.4 этим не утверждается, общий статус master остаётся draft. Адресный пересмотр client capacity policy по решению Саши от 11.11.2026 — Б60.1.1/60.3.4/60.8; эта дельта согласована собственной REV:tz и документно финализирована по Б60.1.1 без изменения согласованных требований. NORM-R3 сохраняет своё прежнее согласование; CAP-R3 и допуск реализации по REVPLAN-R2 остаются открытыми. Утверждение требований не означает implementation, installed или production runtime PASS.

Новая адресная дельта CAPCONST-R10 от 11.11.2026 по решению Саши о расчётной константе 90% — Б60.1.2/60.3.4/60.8. Она записана как draft и ожидает собственной независимой REV:tz и TZ:finalize; прежние согласования её не утверждают. CAP-R3 и допуск HF:impl остаются открытыми до требуемых доказательств.

История решений, changelog, прежние границы отдельных ходов, неутверждённые предложения и смежные предметные контракты хранятся в отдельном приложении. Оно не является входом штатного контекста ролей: не включается в inline, handoff.inputs, must_read или compressor source. Адресное исследование истории требует отдельной явно заданной ссылки; обычная работа читает только актуальные требования этого master и документы своего задания.

Номера сохранённых тематических блоков являются якорями. Отсутствующие старые номера не означают пропуск фазы или потерю требования. Старые AC/IAC/COD сохраняют исходного владельца и область проверки; они не становятся AC любого нового поезда.

## Б0. Назначение, имена и границы

DevWorkflow ведёт изменения Hermes/USERTOOLS: разработку, тесты, баги, настройки, документацию, скиллы, ТЗ и системные инструкции SOUL/AGENTS/profile/USER/MEMORY. Обычные поручения предметным инструментам находятся вне очереди; изменение самих инструментов входит в неё.

Три слоя: скилл dev-workflow ведёт процедуру; Python в Registries/pipeline/ проверяет детерминированные инварианты; файлы dev/<slug>/ сохраняют ход. Оркестратор — Сирень, роль профиля default. Отдельного скилла dev-orchestrator нет. Канбан не участвует в runtime новой машины. Граф означает recipe[], карточка — исторический синоним фазы.

| Объект | Единственный владелец |
|---|---|
| Ход задачи | dev/<slug>/_state.json, журнал journal.md; schema devworkflow-state/1.0 |
| Смысл требований | TZ/<Tool>/<Tool>_TZ.md на диске |
| Пути, backend, модели, effort | EcosystemConfig.yaml → tools.dev_workflow и shared |
| Выжимка | extract.md своего слага, производный индекс |
| Индекс очереди | queue.json, перестраивается из glob */_state.json |
| Манифест и digest | EcosystemIntegration; запись на ORCH:shared-state |
| Имена | GLOSSARY.md; references/canon.md — согласованный операционный указатель |

SQL не является SoT, кэшем выжимок или транспортом контекста. Общий sqlite/NFS-БД и второй реестр состояния не создаются. Read-only telemetry смежных инструментов не является состоянием DevWorkflow.

### Б0.3 Границы хода

Границы первичного документного перехода — Б61.1. Scope адресной правки continuation и её согласование — Б61.4; принятая NORM-R3 компрессора — Б60.1, принятая client capacity policy — Б60.1.1. Текущая адресная расчётная дельта CAPCONST-R10 и её отдельная цепочка согласования — Б60.1.2; нормативные изменения ограничены Б60.3.4/60.8.

Разрешения конкретной роли задаёт принятый packet и утверждённое задание/план. Наличие широкого корня в write_scope не расширяет согласованный пофайловый объём и не меняет роль. Архитектор пишет требования, план и документные evidence, боевой код выполняется на HF:impl; HF:test — отдельный вызов. Переходы процесса выполняет внешний оркестратор после выхода роли.

Предыдущие approvals относятся к своим редакциям и слагам. Б58/Б59 — отменённые поезда: не возобновлять, не применять historical reconcile-result или own legacy completion, не устанавливать candidates целиком. Общие G3 и byte snapshot перенесены в Б17.3 и Б56.4. Общая совместимость старого результата определена Б56.7; адресного backfill она не разрешает.

## Что НЕ трогать

Обязательные запреты и границы — Б33. Принятые packet/sidecar/prepare, история результатов, чужие counters и паузы не исправляются ролью ради прохождения guard. Исторические allowlist из приложения не являются разрешением текущей задачи.

## Б6. Кейсы, роли и guard-ы

| Кейс | Код | Что это | Сборка блоков |
|---|---|---|---|
| DEV | DEV | новый инструмент | бриф полный → закрытие брифа → запись ТЗ (new) → взять в работу → [сжатие] → план-код-хвост полный |
| CHANGE | CHG | доработка существующего | бриф короткий → закрытие брифа → запись ТЗ (full) → взять в работу → [сжатие] → план-код-хвост полный |
| CHANGE-LIGHT | CHG-L | доработка ≤3 implementation-файлов суммарно, секция ТЗ, без новых сущностей/cron/.env | бриф короткий → закрытие брифа → запись ТЗ (light) → взять в работу → короткий хвост |
| BUGFIX | BUG | баг | диагноз → бриф-дельта → запись ТЗ (patch) → взять в работу → план-код-хвост полный |
| BUGFIX-LIGHT | BUG-L | лёгкий баг ≤3 файлов; LIGHT **после** ревью диагноза | диагноз → запись ТЗ (patch) → взять в работу → короткий хвост |
| RESEARCH | RS | анализ без кода | бриф-рамка → сбор → анализ → [ревью отчёта] → готово |
| MIGRATION | MIG | миграция | бриф короткий → закрытие брифа → запись ТЗ (freeze) → взять в работу → план миграции → блоки с приёмкой Саши |
| DECOMM | DEC | удаление | бриф-подтверждение → инвентарь → гейт «удаляй» → бэкап → удаление |
| SKILL-DEV | SK | новый скилл | как DEV, workspace = skills, ревью вкл., ORCH restore |
| SKILL-CHANGE | SK | правка/удаление скилла | преflight размера → дальше CHANGE или DECOMM |

Кейс выбирается по references/cases-guide.md: «баг / не работает / почини» сразу означает BUGFIX. Вопрос о семействе нужен только при равноправных DEV/CHANGE, без меню слагов и технических развилок. Архитектор не меняет кейс и не сокращает рецепт. LIGHT — сужение того же семейства после установленного объёма, BUGFIX только после GATE:diagnose-review. Механика set-case — Б8; общий контракт LIGHT — Б20.

Префиксы BRF:, GATE:, TZ:, HF:, ORCH:, REV:, BUG:, RS:, MIG:, DEC:, SK:, IDEA: пишутся канонически. BRF и GATE:brief-closed обозначают бриф до init, не исполняемые фазы recipe[]. Новый кейс/фаза не изобретается.

| Роль | Обязанность | Граница |
|---|---|---|
| Оркестратор | Факты, FIFO, контекст, вызовы, гейты и ORCH | Не пишет ТЗ/код, не выбирает архитектуру, не предлагает слаги/технические решения |
| Архитектор | ТЗ, диагноз, HF-plan.md и IAC, риски и Q-n | Не финальный боевой код, не HF:test, не управление процессом |
| Ревизор | Независимая проверка источников, требований и покрытия | APPROVE / REQUEST-CHANGES; не ход процесса |
| Исполнитель | Код и каждый verify согласованного плана | Существенное отклонение возвращает архитектору |
| Компрессор | Содержательный индекс | Не SoT; canonical пишет Python, Б60 |
| Координатор | Backup, inventory, адресный shared-state | Фазы оркестратора; не отдельная содержательная роль |

Один invoke-role — одна роль. Значения моделей и effort читаются из YAML, не из таблиц истории.

| Guard | Условие допуска |
|---|---|
| G1 | Фаза в recipe; актуальные master/version/mtime, extract по политике Б56 и manifest Б60 |
| G2 | Успешный context-used и exact accepted binding Б56.6 |
| G3 | Собственный committed write-set, полный proof Б17.3 |
| G4 | Полный рецепт кейса на init и GATE:done |
| G5 | Кейс и обязательные фазы не подменены ролью |
| G6 | Канонические фаза, роль, результат и нормализованный slug_source |

G6 проверяет все фазы recipe[], включая RS/MIG/DEC; отсутствие строки — fail. CLI-default slug/source допустимы до нормализации; отсутствующий или подменённый provenance после неё отклоняется.

Таблица G6 **фаза → роль** (код, не промпт):

| Фазы | `--role` |
|---|---|
| `TZ:patch`, `TZ:finalize`, `HF:plan`, `BUG:diagnose`, `RS:collect`, `RS:analyze`, `MIG:plan`, `MIG:block-k`, `DEC:inventory`, `IDEA:analyze` | `architect` |
| `REV:tz`, `REV:plan`, `REV:report` | `reviewer` |
| `HF:impl`, `HF:test`, `DEC:exec` | `executor` |
| `TZ:compress`, `HF:compress` | `compressor` |
| `TZ:stabilize`, `SK:preflight`, `HF:backup`, `HF:docs-handoff`, `ORCH:shared-state`, гейты | оркестратор (Сирень); invoke-роль не звать |

Таблица **исчерпывающая** для фаз, которые попадают в `recipe[]` десяти кейсов (Б18–Б27). Нет строки = G6 fail (не «фаза не в таблице → не проверять»). `pipeline recipe-add` (`MIG:block-k` и динамические блоки) наследует роль строки `MIG:block-k` = `architect`; иной `--role` на блоке — только будущий `TZ:patch` этой таблицы, не ad-hoc оркестратора.

Применимость: `RS:collect` — architect, read-only как `BUG:diagnose`; `SK:preflight` — оркестратор, механический `wc -c` как `TZ:stabilize`; `MIG:block-k` — дефолт architect (контент блока не invents роль).

Несовпадение → emit-prompt / invoke_role / complete-phase **exit 1**, state не менять (кроме journal `g6_role_mismatch`).

HF:impl и HF:test выполняются раздельно. Auto-гейт остаётся фазой recipe и завершается после своей улики без LLM.

## Б8. CLI, состояние и журнал

Python-инварианты живут в Registries/pipeline/, скилл — в hermes-workspace/skills/devops/dev-workflow/. Код не размещается в USERTOOLS/DevWorkflow/ или hermes-agent. Существующие modules pipeline_state.py, pipeline_queue.py, pipeline_log.py, pipeline_recipe.py, pipeline_gates.py, pipeline_preflight.py, pipeline_gitproof.py, pipeline_context.py, invoke_role.py, paths.py, probe.py и pipeline_errorbus.py имеют одного владельца своей функции. Скилл хранит процедуру в SKILL.md, предметные подробности в references, scripts/pipeline.sh остаётся тонкой обёрткой.

Команды ниже — интерфейс, не предписание исполнять их из содержательной роли.

CLI (человеко-читаемые глаголы):

```
pipeline init --case CHANGE [--slug <slug>] --title <text> --origin-chat <id> --origin-thread <id> [--slug-source suggest-cli|sasha-verbatim|reuse]
pipeline suggest-slug --title <text> [--kind train]
pipeline next --slug <slug>
pipeline complete-phase --slug <slug> --phase <PHASE> --reason <text> --evidence <text>
pipeline hold --slug <slug> --verb <operator-verb> --reason <text>
pipeline operator-done --slug <slug> --verb <verb> --evidence <text>
pipeline emit-prompt --slug <slug> --phase <PHASE> --out <path>
pipeline check --slug <slug> --phase <PHASE>
pipeline status [--slug <slug>] [--check]
pipeline set-case --slug <slug> --case CHANGE-LIGHT
pipeline interrupt --slug <slug> --reason <text>
pipeline abort --slug <slug> --reason <text>     # не rm
pipeline recover --slug <slug> --reason <text> --evidence <text> [--class dead-pid|wrong-role|empty-result|rc0-no-complete|model-none]
pipeline doorbell [--slug <slug>]                # 0-токенный fingerprint очереди; не next, не recover
pipeline repair [--slug <slug>]
pipeline journal --slug <slug>                   # печать journal.md хвоста
```

complete-phase / hold / interrupt / abort / recover требуют --reason; complete-phase / operator-done / recover требуют --evidence. Отсутствующий аргумент: exit 2, state неизменен. Evidence содержит проверяемый path/version/hash либо session_id/rc/file; слово «готово» не proof.

suggest-slug --title возвращает один детерминированный lowercase kebab, транслит, не длиннее 48, с collision bool и source=suggest-cli. Kind только train; kind task и entities.task_slug — вне этого CLI. init допускает опущенные --slug и --slug-source: Python вычисляет один slug и default suggest-cli. Иные источники: sasha-verbatim — дословный slug из сообщения Саши, reuse — существующий каталог. G6 проверяет уже вычисленный результат. Меню кандидатов в origin запрещено.

set-case сужает recipe одной функцией и сохраняет done-фазы, второго init нет. После set_case(d, case) в cmd_set_case выполняется d.pop("state_sha256", None) до from_dict/write_state. from_dict с диска остаётся строгим; recipe не считает sha. repair перестраивает индекс, не ремонтирует sha/PID и не сбрасывает бюджет.

### Б10. Файловая запись

Членство в очереди — наличие _state.json. Повторный init незавершённого слага идемпотентен; done/aborted занимают имя навсегда. abort сохраняет каталог и историю; он не равен rm и не используется для освобождения исторического пилота. Удаление требует DECOMM.

Под существующим .queue.lock: прочитать state и сверить state_sha256; полностью проверить событие до мутации; временный файл в том же каталоге, atomic os.replace, append journal.md/queue.log.jsonl и rebuild queue.json. Ошибка записи не оставляет принятую половину перехода; rollback проверяет соответствующие preimages. Несколько файлов не объявляются crash-атомарными. Ни ручного JSON-write, ни долгого LLM/send под lock.

Папка без index — repair_reindex; index без папки и hash_mismatch — CRISIS, ErrorBus и явная диагностика. Не писать поверх несовпадающего hash, не создавать синтетический state отсутствующей папки. Восстановление из доказанного snapshot/git. repair_reindex и hash_mismatch описывают причину в reason/evidence существующих repair/crisis; отдельные event-имена из них не создаются.

State хранит schema, slug/title/case/status/phase/recipe, phases, origin, operator_holds, open_questions, recover_counts, tz/extract metadata и state_sha256. Фаза хранит status/started_at/ended_at/pid/session_id/backend/model/role/awaiting_invoke/changed_files/context_used/reason/evidence/proof. turn_count — аддитив int default 0; context_packet — optional object. Breaking schema требует migrate_vN_to_vN+1(), старый state без миграции не запускается. История завершённых фаз не переписывается.

### Б10.2 Закрытый словарь событий и provenance

| Назначение | event |
|---|---|
| Приём и движение | init, start, next, complete, interrupt, hold, operator_done, abort, set_case |
| Проверки и исправление | repair, crisis, suggest_slug, g6_role_mismatch, recover, canonical_artifact_fail |
| Вызов роли | invoke_prepare, invoke_role |
| Контекст | context_used |

Существующее событие отказа invoke и compatibility-события writer сохраняют прежние имена и читаются по проверенной закрытой таблице существующего pipeline_log.py. Таблица выше задаёт обязательные производственные события, а сохранённые compatibility-значения не создают фаз, разрешений или регламентов. Test-only события не являются производственным маршрутом. Единственный writer/validator полного словаря — pipeline_log.py; второй enum в скиллах не поддерживается.

actor описывает источник записи: sirene / architect / reviewer / executor / operator / pipeline / cli. CLI writer использует cli также в обычных переходах; это не G6-роль и не право закрыть чужую содержательную фазу. Фактическая роль отдельно проверяется по phases.<PHASE>.role и accepted invocation. После C01 этот actor не зависит от запрещённого legacy completion.

Каждая запись имеет ts с timezone, slug, event, actor и phase. init/root abort допускают отсутствие фазы; root set_case без active phase использует phase=- как поле журнала, не recipe-фазу. Обычные события и operator_done требуют active phase. reason обязателен для complete/hold/interrupt/abort/recover, evidence — complete/operator_done/recover. Процессный вызов сохраняет pid/session_id; мутация — state_sha256_before/after. Проверка до replace; неполная запись даёт exit 1.

context-used:, AC-shown:, AC-delivered: — маркеры evidence, не имена recipe/events. Structured context_used сохраняется: его читатель сверяет packet binding. transport_terminated и artifact_ready — evidence keys recover/canonical_artifact_fail, не новые события. Receipt исключает повторную запись принятого invoke.

## Б12. Обязательное чтение

| Источник | Роль | При конфликте |
|---|---|---|
| Выжимка `extract.md` | индекс: имена, CLI, лимиты, связи, «не трогать», `[NEW-ENTITY]` | проигрывает |
| Master-ТЗ на диске | SoT смысла | **побеждает** |

Пакет = digest графа + канон кейса + выжимка (или части 1/N) **плюс абсолютные пути** к digest / канону / master-ТЗ. Тела целиком **не** вклеивать: вклейка режется окном модели (молчаливая обрезка середины). Выжимка — топливо следующих ролей, **не замена** master-ТЗ. В пакет класть явную строку: «выжимка ≠ SoT; при расхождении — открыть master».

Маркер `[NEW-ENTITY, требует согласования Саши]` — норма пакета DevWorkflow (не только EcosystemIntegration §8.2). Компрессор не заменяет его общими словами; роль, увидев маркер, обязана открыть master.

| Фаза | Роль обязана открыть полный файл | Выжимки достаточно как индекса |
|---|---|---|
| `TZ:patch` / `TZ:finalize` / `REV:tz` | **не** весь master по умолчанию (Б56.4). Обязательные секции: frontmatter + Б0.3 (границы хода); «Что НЕ трогать»; Б33; Б34 сводка AC (таблица); секции задания по точной привязке ReadRef Б56.4. Полный файл — если роль **пишет или судит** норму вне этого набора, есть `[NEW-ENTITY]`, выжимка расходится с путём, или путь короче 5 КБ | как индекс; формулировки норм — с диска открытых секций |
| `HF:plan` | минимум секция AC + «не трогать» + контракты | ориентация; формулировки AC — с диска |
| `HF:impl` | план + IAC (`path` / `verify`); полное ТЗ — при расхождении IAC с выжимкой или при запретах | да, если IAC покрывает AC |
| `HF:test` | IAC.verify, не пересказ ТЗ | да |
| `REV:plan` | план + IAC + запреты master «не трогать» | нет как замены покрытия |
| `BUG:diagnose` | факты на диске (логи, код); ТЗ — при контракте бага | да как карта |
| **Всегда** | если выжимка и путь расходятся; путь короче 5 КБ «не влезло»; есть `[NEW-ENTITY]`; роль собирается обобщить имя | нет |

Чтение **без обрезки внутри выбранных секций** (блоками offset, не «пропусти середину секции»). Если роль открывает полный файл (исключения строки TZ/REV или другие фазы таблицы) — без обрезки файла. Доктрина двух источников (Б12) **не** отменяется: конфликт → диск. Священные имена Б60.3.2 компрессор по-прежнему не выбрасывает. Инструкция «без обрезки» в промпте не техническая; скилл обязан сказать роли: читать блоками, не опускать секции «не трогать» / AC / контракты / границы хода.

G2 доказывает, что `emit-prompt` **вызвали**, не что LLM **прочитала** файлы. Понимание ловят артефакт (IAC, REV по диску) и MUST-read, не маркер.

Ключ extract_key и история его применимости — Б56.3; публикация и reuse — Б60.6. Отдельные пересказы этих правил в фазах не вводятся. Размер готовой части extract — не более 5120 Unicode-символов с framing и эхо; полный алгоритм — Б60.5.

## Б13. Вызов роли и приём результата

Для каждой содержательной роли единственный путь — emit-prompt с rc=0, затем invoke-role --prompt-file --role --workspace. --workspace абсолютный; не scratch. Перед prepare проверяются G1/G3/G6, packet и scope/outputs. Ручной prompt, --force и raw agent -p/codex exec в обход adapter запрещены.

Для Hermes terminal используется один request с background=true, notify=true, persist_on_release=true; это поля инструмента. После получения session id тот же command не отправляется повторно. Validation error не retryable: сначала исправить вход. Foreground/terminate и `| head` / `| tail` / любой отсекатель stdout на invoke-role запрещены (SIGPIPE). Проверка AC-064: явный запрет есть в этом ТЗ и SKILL.md; фикстура/чеклист процедуры подтверждает фоновый вызов без пайпа. Не проверять SIGPIPE живым убийством агента. Эти поля не превращаются в shell-флаги другого транспорта.

На invoke_prepare writer записывает os.getpid() обёртки в st.pid и phases[phase].pid до spawn; backend/model — тот же resolved результат, что передан adapter, awaiting_invoke=false. role записывается после успешной приёмки результата, не на prepare. session_id берётся из структурного JSON/JSONL (Cursor session_id/sessionId, Codex штатное поле stream); пустой parse оставляет null и сам по себе не отменяет полный canonical. session_id не заменяет PID.

| Факт | Действие |
|---|---|
| Точный wrapper жив, даже если canonical уже записан | Никаких next/complete-phase/recover/второго invoke и второй задачи |
| Sirene-фаза с pid=None | WORK оркестратора в том же ходе, без содержательной invoke-роли |
| awaiting_invoke=true, pid=None до prepare | Штатный pre-invoke WORK; брошенное окно диагностируется |
| Wrapper вышел, role записан, canonical/result пригоден | Post-invoke WORK/RECONCILE, обычный complete с evidence |
| Role записан, required canonical отсутствует/не обновлён | empty-result / canonical_artifact_fail; Б16 и пределы Б55.5 |
| Role отсутствует, не awaiting_invoke, wrapper завершён и пригодного результата нет | Доказанный true-crash, классификация Б16 |
| Обрыв/143 после записи файла | Сверка writers, outcome, snapshot, канона/receipt по существующему пути; файл сам по себе не PASS |
| Уже принятый результат доставлен повторно | Verified no-op без второго side effect/complete/notify |

Notify будит внешнего оркестратора и не доказывает окончание wrapper. Неясный outcome/связанный writer означает ожидание/диагноз, а не слепой повтор. Успешный ответ adapter не закрывает фазу автоматически. Compressor имеет более строгий контракт Б60.6, files-only reconciliation для него запрещён.

Канон generic результата существует, непуст и обновлён после started_at либо отличается hash от preimage. Короткий stdout допустим при полном файле; rc=0 без канона не proof. Не-канонное имя даёт ненулевой rc и hint. Исторические соседние REV-файлы не читаются как текущий вердикт.

| Фаза | Канонический basename | Не-канон (fail invoke_role) |
|---|---|---|
| `REV:tz` | `REV-tz.md` | `REV-tz-2.md`, `REV-tz-1.md`, любой другой `REV-tz*.md` как *единственный* новый файл |
| `REV:plan` | `REV-plan.md` | `REV-plan-2.md` и аналоги |
| `TZ:compress` / `HF:compress` | `extract.md` (плюс `extract-k.md` при 1/N) | единственный выход с другим именем |
| `HF:plan` | `HF-plan.md` | `HF-plan-2.md` и аналоги |
| `TZ:patch` | `TZ-patch.md` | единственный выход с другим именем; master-ТЗ на диске **обязан** быть записан этим же ходом (SoT), `TZ-patch.md` — канон слага для гейта |
| `BUG:diagnose` | `_fix_plan_YYYYMMDD.md` | пустой journal-body без плана |
| `RS:collect` | `RS-collect.md` | иное имя как единственный выход |
| `RS:analyze` | `RS-analyze.md` | иное имя как единственный выход |
| `MIG:plan` | `MIG-plan.md` | иное имя как единственный выход |

### Б13.2 Backend и модель

Backend сначала: slug из invoke.codex_pilot_slugs использует codex, иначе invoke.default_backend. Затем explicit --model, иначе роли выбранного backend: codex → roles.<role>, LIGHT executor → roles.executor_light; cursor-cli, включая LIGHT → roles_cursor.<role>. Один resolved model передаётся argv и на prepare; отсутствие обязательной модели даёт exit 2. Hardcoded fallback composer-2.5 не допускается. Координатор остаётся sirene; compressor model/capabilities — Б60.4. Изменение backend для обхода quota запрещено.

Обычный codex adapter: codex exec -C <ABS> -m <id> -c model_reasoning_effort='"<effort>"' --skip-git-repo-check --json --sandbox danger-full-access и тело prompt как operand. Не codex run/--cwd/--full-auto/--yolo. Для compressor host-write ограничен ОС по Б60.4. Cursor rollback сохраняет agent -p, --output-format json и только explicit --resume сохранённой фазы; --continue запрещён. Native — hermes-internal, без внешнего CLI.

Provider-fatal классифицируется структурно. Валидный успешный JSON не сканируется FATAL_PATTERNS по содержательному result. Error envelope имеет приоритет; Codex JSONL проверяет любое error-событие до/после success. Не-JSON использует строгие сигнатуры реального client error, не голые timeout/credits/billing/payment. Цитата HTTP 401/token_expired/Request timed out в успешном result не failure. Подлинные auth/billing/429/5xx/90-90 дают ненулевой rc, interrupt/ErrorBus без автоматического retry/recover. FATAL_PATTERNS и TERMINAL_KILL_RCS не ослабляются.

Rc 124/137/143 сам по себе не provider-fatal и не разрешение retry: сначала lifecycle и пригодный результат, затем один применимый регламент Б55.5. Узкое benign models-refresh исключение допустимо только по точной воспроизведённой fixture Б60.7, не broad stderr suppression.

### Б13.3 Установка и комплект

Комплект для компании: скилл, Registries/pipeline/, README, references/config.example.yaml, onboarding.md, cases-guide.md, install.md и handoff.md. Человек, включая не-разработчика, даёт постановку и принимает AC; чтение Python не требуется. DevWorkflow не заменяет встречи/протоколы/контакты/Confluence и не становится новым USERTOOL.

На другом Hermes: checkout скилла, restore-all-skills.sh, pipeline/, YAML со своими путями, секреты только shared .env/auth storage; status --check rc=0; install-smoke RESEARCH одной фазы и abort с сохранением каталога. Та же sanity-проверка после hermes update. Нет systemd update-hook или патча ядра.

### Б13.4 Handoff

Живой слаг передаётся файловым bundle: весь dev/<slug>/ с AC/планами/REV/extract/частями/context/history и master либо его синхронная копия. /tmp/task.md и sidecar не возятся. На приёме пути state разрешаются из YAML нового хоста, G1/check и новый emit; архивные snapshot refs не переписываются. Extract reuse допускается только по проверенному ключу/manifest. Слаг активен на одном хосте: flock не межмашинный. Общая sqlite/NFS-БД не является транспортом.

## Б14. Конфигурация и внешние контракты

DevWorkflow использует unified_only в EcosystemConfig.yaml, без per-tool .env/overlay. Пути берёт paths.py через usertools_config.py. Литералы домашнего каталога в Python запрещены. Шаблон config.example.yaml содержит те же required ключи с путями принимающего хоста; старый неполный YAML-эскиз не применяется.

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| enabled | bool | required | EcosystemConfig.yaml (`tools.dev_workflow`) | true/false |
| DEV_STATE_ROOT | str | required | EcosystemConfig.yaml | абсолютный путь |
| TZ_ROOT | str | required | EcosystemConfig.yaml | абсолютный путь |
| PIPELINE_ROOT | str | required | EcosystemConfig.yaml | абсолютный путь |
| SKILL_ROOT | str | required | EcosystemConfig.yaml | абсолютный путь |
| DIGEST_PATH | str | required | EcosystemConfig.yaml | абсолютный путь к `EcosystemManifest.digest.md` |
| invoke.default_backend | enum[cursor-cli, codex, hermes-internal] | required | EcosystemConfig.yaml | v0.5.0 штат=`codex` **после** пилота (Б13); до flip — `cursor-cli` допустим |
| invoke.codex_pilot_slugs | list[str] | required | EcosystemConfig.yaml | pilot-prep `HF:test`: `[<пилотный слаг>]`, иначе `[]`; очистка на flip |
| roles.architect.model | str | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles_cursor.architect.model | str | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles_cursor.reviewer.model | str | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles_cursor.executor.model | str | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.architect.effort | enum[low, medium, high, xhigh] | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.architect.escalate_model | str | optional | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.architect.escalate_effort | enum[low, medium, high, xhigh] | optional | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.reviewer.model | str | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.reviewer.effort | enum[low, medium, high, xhigh] | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.executor.model | str | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.executor.effort | enum[low, medium, high, xhigh] | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.executor_light.model | str | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.executor_light.effort | enum[low, medium, high, xhigh] | required | EcosystemConfig.yaml | Значение выбранной роли/ветки из YAML; алгоритм Б13.2/Б60.4 |
| roles.compressor.model | str | optional | EcosystemConfig.yaml | выбор compressor проверяется по Б60.4 |
| digest_body | str | required | EcosystemManifest.digest.md | markdown; не секреты |
| tz_path | str | optional | master-ТЗ на диске / TZ:stabilize | абсолютный путь; required после finalize |
| tz_version | str | optional | YAML-frontmatter master-ТЗ | semver X.Y.Z |
| tz_mtime | datetime(iso8601) | optional | stat() master-ТЗ | UTC |
| extract_key | str | optional | pipeline после compress | `tz_path`+`tz_version`+`tz_mtime`+prompt_hash; required после первого compress слага |
| extract_sha256 | str | optional | pipeline после compress | hex sha256 файла(ов) выжимки |
| extract_of_tz_version | str | optional | pipeline после compress | semver master, от которой сжато |
| git_head | str | optional | git worktree фазы (G3) | hex sha; required с HF:impl |
| origin.chat_id | str | required | сессия Telegram / resolve_origin | id группы |
| origin.thread_id | str | required | сессия Telegram / resolve_origin | id топика; `:11112` запрещён для кейса |
| origin.chat_type | enum[group] | required | resolve_origin | всегда group |
| trigger | enum[new_tz, enhance, bugfix, research, idea_feed] | required | фраза Саши | new_tz=разработай/напиши ТЗ; enhance=доработай; bugfix=почини; research=исследуй; idea_feed=в бэклог |
| orchestration.mode | enum[kanban-primary, dual-path, workflow-only] | required | EcosystemConfig.yaml (`tools.dev_workflow.orchestration`) | W1=`kanban-primary`; W2–W3=`dual-path`; W4 / голый install=`workflow-only`; нет ключа / неизвестное значение → exit 1 |
| orchestration.pilot_slugs | list[str] | required | EcosystemConfig.yaml (`tools.dev_workflow.orchestration`) | W1=`[]`; W2+: allowlist слагов; пустой список = не перехватывать триггеры |
| slug_source | enum[suggest-cli, sasha-verbatim, reuse] | required | `pipeline init` (v0.4.0) | CLI default `suggest-cli`; G6 проверяет нормализованное поле |
| phases.<PHASE>.role | enum[architect, reviewer, executor, compressor, sirene] | optional | invoke_role / оркестратор | required на complete TZ/HF/BUG/REV после включения G6 |
| phases.<PHASE>.model | str | optional | invoke_prepare (v0.4.8) | slug; required на complete architect/reviewer/executor |
| phases.<PHASE>.awaiting_invoke | bool | optional | `pipeline next` (v0.4.8) | true только в окне pre-invoke |
| recover_counts | str | optional | `pipeline recover` (v0.4.8) | JSON-объект `{phase:{class:int}}` внутри `_state.json`; не отдельный файл |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| schema | str | `pipeline_state` migrate / `status --check` | `devworkflow-state/N.N` внутри `_state.json` |
| tools.dev_workflow.enabled | bool | EcosystemIntegration / `render_manifest.py` | true/false; служебный YAML-ключ |
| tools.dev_workflow.migration_status | enum[unified_only] | EcosystemIntegration | сразу `unified_only` (новый контур) |
| error.tool | str | ErrorBus (`:11112`) | всегда `dev_workflow` |
| notify_text | str | origin-топик (`pipeline_notify`) | markdown; не ErrorBus |
| inventory_row | str | tz-workflow / наблюдатель инвентаря | строка `MAIN_TZ_INVENTORY.md` после TZ:finalize |

Digest манифеста видит: `enabled` + `default_backend` + факт наличия `pipeline/` — не значения секретов и не содержимое `_state.json`.

Breaking state format: bump schema и migrate_vN_to_vN+1() в pipeline_state.py; уведомить локальных потребителей, EcosystemIntegration и ErrorBus. Версия ТЗ не равна schema. Аддитивы не добавляются при старом round-trip так, чтобы нарушить исходный SHA; массового backfill нет. SQL-схемы канбана не мигрируются этим процессом.

## Б15. Хранение документов и backup

| Что | Куда |
|---|---|
| Живое master-ТЗ | `TZ/<Tool>/<Tool>_TZ.md` (версия только во frontmatter) |
| Доработка | новая датированная секция **в том же файле**, не новый файл |
| Приложение | `TZ/<Tool>/appendix_<тема>_YYYYMMDD.md` |
| Реестр | `TZ/MAIN_TZ_INVENTORY.md` — обновлять после любой структурной записи ТЗ |
| Снапшот перед большой перепиской | `WorkVault_backup/.../<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz` |
| Архив ТЗ | только когда **инструмент** снят (DECOMM), в `_archived/` |
| Runtime | **не** в `TZ/<Tool>/` (state — `dev/<slug>/`, код — `pipeline/`) |

После структурной записи master обновляется MAIN_TZ_INVENTORY.md под существующим LOCK_EX. TZ:finalize требует master, inventory и canonical TZ-finalize.md; evidence ссылает оба документа. Отсутствие inventory в разрешённом scope — дефект допуска: proposal не является записью и finalize не complete.

До изменений сохранить восстановимые preimages всего своего write-set, hashes/mode/symlink targets и dirty provenance. Конфиги — ~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/, retention 2 недели. Откат собственных файлов после прекращения writers адресный: сохраняет входные dirty и чужую работу, state/journal/queue/паузы/counters. git reset --hard и архивная перезапись state запрещены. После правок скиллов ORCH выполняет restore-all-skills.sh и проверяет workspace → профили, конечную загрузку и tested bytes.

## Б16. Ревизия и восстановление

### Б16.1 Согласование

REV обязателен там, где предусмотрен полным каноном/recipe. LIGHT skip допустим только по табличному маршруту либо flag-waived: Sasha. Архитектор пишет patch/план, ревизор проверяет master/план на диске, запреты, смысловое покрытие AC/IAC и соответствие extract. REQUEST-CHANGES не завершает REV и не продвигает к finalize/impl; работа возвращается к тому же canonical архитектора. Повтор замечания ограничен Б55.5. APPROVE требований не заменяет реализацию.

Вердикт читается только из канона: блок ## Вердикт до следующего h2/EOF, первый явный APPROVE или REQUEST-CHANGES/REQUEST CHANGES; допустим markdown-bold. Если блок пуст — verdict= в Evidence. Нет вердикта или конфликт двух полей — отказ. Поиск по всему телу и историческим файлам запрещён; цитата REQUEST-CHANGES в APPROVE-теле не меняет вердикт.

### Б16.6 Технические классы

| Класс | Действие при доказанном основании |
|---|---|
| dead-pid | Без пригодного результата и живого wrapper, не штатный pre-invoke: один recover → warn origin → next |
| wrong-role | G6 отказ до запуска: первый правильный invoke по таблице, без interrupt/reset |
| empty-result | Канона нет: один correction с файловой доставкой; resume только сохранённой session либо чистый вызов |
| rc0-no-complete | Пригодный post-invoke результат: обычный complete, не повтор invoke |
| model-none | Complete запрещён; исправление resolver/адресный возврат или один допустимый invoke с моделью из YAML |

recover использует write_state, записывает reason/evidence/class, увеличивает recover_counts[phase][class]; не spawn и не next. Второй recover той же пары запрещён. Не применять к live wrapper/provider-fatal/billing/90-90/явной паузе/CRISIS/never-auto. RECOVER с допустимым счётчиком выполняется оркестратором в том же ходе; исчерпанный/неприменимый класс — INTERRUPTED и диагноз. Warn класса S идёт в существующий origin, не создаёт канал.

### Б16.7 Doorbell

0-токенный детектор существующего пути, резервный wake при потере completion. Сегмент slug|status|phase|role|pid_alive|wrapper_alive[|canon_mtime=…]. canon_mtime опускается при живом pid или wrapper, иначе включается. Fingerprint включает queue=<n>: незавершённые готовые задачи, включая текущую, без idea/переданных idea/done/aborted. Проекция одна с Б55.6. Неизменный tick сообщает queue=<n>, без WAKE/LLM/next/recover; смена даёт WAKE и существующий wake оркестратору. Tick не spawn/kill/recover и не копирует dwka_guard.sh. Реальная доставка обязательна; печатный WAKE её не доказывает. Расписание только по «ставь кроны»; платформа с LLM на каждом неизменном тике не подходит.

## Б17. Гейты и собственный G3

Классификация AC и общий operator-hold заданы в Б17.5.

| Гейт | Обязательная улика |
|---|---|
| GATE:take-into-work | Непустой AC-list.md и AC-shown: с доставкой в origin |
| GATE:plan-approve | Предусмотренный кейсом план на диске, HF:plan либо MIG:plan done |
| GATE:diagnose-review | Непустой _fix_plan_YYYYMMDD.md либо предусмотренное тело диагноза |
| GATE:done | Полный preflight: фазы, G1/G2/G3, Q, holds, проверенный и доставленный AC-report |

Это auto-гейты без LLM; наличие улики не разрешает skip. GATE:go и каждый GATE:block-accept — never-auto с цитатой Саши и временем.

### Б17.3 Собственный committed write-set

Обычная успешная финализация HF:impl записывает проверенные changed_files, context_result, receipt и git proof одним локальным переходом. Источник — утверждённый план/allowlist и собственный baseline→HEAD diff. Directory output, stdout, git ls-files или список модели не являются write-set.

Для каждого repo проверяются top-level, baseline/HEAD/ancestry, принадлежность paths, rc/timeout/stderr каждого git вызова, tracking, чистые index/worktree, отсутствие лишних/пропущенных собственных изменений, HEAD blob/worktree hashes. Ошибка git с пустым stdout, non-repo, ignored/untracked/outside-repo — отказ. Законные add/delete/rename доказываются diff status/blob/tombstone, удалённый файл не объявляется untracked по одному отсутствию.

Пустой список при ожидаемом коде запрещён в success, complete HF:impl, next и прямых emit/invoke HF:test/HF:docs-handoff до writer/prepare/turn/send, preflight GATE:done. Один общий verifier вызывается всеми admission callers. Исправление старого завершённого proof задним числом запрещено.

no-code-change: допустим только при заранее утверждённом no-code плане/IAC с FileRef, конкретной причине, проверенном нулевом собственном diff, required outputs и proof, связанном с packet/prepare. Голая строка и changed_files=[] не заменяют основание. Если в recipe нет HF:impl, G3 неприменим, а не PASS пустого impl. Отменённые адресные nine/thirteen-file исключения не действуют.

### Б17.5 Классы AC и operator-hold

Класс AC по умолчанию **S**: показ не останавливает процесс и не требует ожидания фразы Саши. Класс **O** — только с явной строкой `depends: operator:<verb>` на конкретном AC в ТЗ пакета. В state ему соответствует `operator_holds[{verb, status:open, ac}]`: verb совпадает с объявленной зависимостью, ac указывает именно удерживаемый критерий. Открытый hold удерживает GATE:done; показ обычного S не создаёт операторской зависимости. Класс **C** — кризис: поток стоит до его снятия, правило S ожидание кризиса не отменяет.

Закрытый operator-словарь: поднимай · ставь кроны · удаляй · answer:Q-n · rollback-to-kanban. Новый глагол требует изменения master. Снятие: `pipeline operator-done --verb --evidence`. До записи проверяются закрытый verb, matching open hold и evidence с ISO timestamp плюс rc либо цитатой факта. Неизвестный verb, отсутствующий или несовпадающий hold и неполное evidence дают отказ до изменения state/journal; одна фраза оператора их не легализует. Одна фраза без факта не закрывает O. Preflight done красный, пока есть open holds; обязательные проверки фаз, Q и доставки AC-report сохраняются.

### Б17.8 Workspace

TZ, REV:tz и IDEA работают в TZ, код USERTOOL — …/USERTOOLS/<Tool>, скилл — hermes-workspace/skills, ORCH — Registries, кросс-контрактный диагноз — TZ. При двух деревьях одной фазы допускаются последовательные invoke той же роли с непересекающейся записью и единым доказанным write-set. Это не склейка HF:impl/HF:test и не параллель ролей.

## Б18. Полный цикл CHANGE

Закрытый бриф до init содержит постановку, периметр, факты и подтверждение exact редакции; технические развилки формулирует архитектор. Файл уже закрытого брифа можно механически сохранить в dev/<slug>/ после init как приложение, не вместо state и не как повторное согласование. Источник первичного acceptance — Б60.3.1. Полный recipe:

TZ:stabilize → TZ:compress → TZ:patch → REV:tz → TZ:finalize → GATE:take-into-work → [HF:compress] → HF:plan → REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done.

Optional фаза, включённая в recipe, становится обязательной. Обязательный compress/REV не удаляется ради контекста. Роль каждой фазы берётся из Б6; отдельные вызовы и accepted inputs — Б56.5.

| Фаза | Работа и результат |
|---|---|
| TZ:stabilize | Оркестратор фиксирует master path/version/mtime и проверяет подтверждённый brief/basis; complete либо явный interrupt в том же ходе |
| TZ:compress / HF:compress | Б60; HF после finalize использует актуальный master; producer сам фазу не закрывает |
| TZ:patch | Архитектор пишет master draft и canonical TZ-patch.md; reuse-first; без боевого кода |
| REV:tz | Независимое согласование Б16.1 |
| TZ:finalize | Б15: согласованные master + inventory + канон |
| HF:plan | Обязательный HF-plan.md с IAC: path / verify / depends / covers, полный write-set и oracle; appendix может дополнять, не заменять канон |
| REV:plan | Полный план/IAC и запреты master, исполнимость и покрытие |
| HF:backup | Оркестратор; весь будущий write-set и проверенные preimages |
| HF:impl | Исполнитель по плану; собственный commit/changed_files/G3 и implementation evidence |
| HF:test | Отдельный исполнитель выполняет каждый verify по зависимостям, tests_run/tests_passed/rc/logs/commit; probe_battle_venv боевого Python |
| HF:docs-handoff | Оркестратор принимает фактические docs/передачу, metadata для ORCH, связи плана/тестов/diff |
| ORCH:shared-state | Разрешённые manifest/digest/YAML/restore; check-drift и конечная загрузка, без самовольных jobs/секретов |

IAC покрывает каждый AC; полный regression не заменяет обязательный уникальный oracle. required/actual/missing и объяснённые extra сохраняются, когда набор задан планом. Component/stub, offline CLI, installed smoke, live provider и production runtime отражаются отдельно. NOT_RUN, FAIL, partial и no-entry не становятся PASS по числу зелёных тестов.

GATE:done: собрать AC-report.md для каждого AC с командой/логом/результатом; доставить в origin; сохранить AC-delivered: и тело/путь; preflight rc=0; только затем complete GATE:done и root done. AC-list не заменяет отчёт, голый marker не доказывает доставку. При O/Q/FAIL поток остаётся на задаче.

## Б19. DEV

Как полный CHANGE, режим new: TZ:patch создаёт master с reuse-first, REV:tz/TZ:finalize обязательны; stabilize/compress опциональны по recipe. До записи допустим planned master, только нового инструмента. Включённый compress требует завершения. Общие входы/выходы не копируются.

## Б20. LIGHT

Не более трёх изменяемых implementation-файлов суммарно: код, тесты, SKILL.md. Собственные plan/report/evidence и обязательные master/inventory считаются отдельно. Нет shared-модулей, новых сущностей, cron, .env или манифеста. Старые поезда автоматически не переклассифицируются.

CHANGE-LIGHT после оценки на TZ:patch: TZ:patch → TZ:finalize → GATE:take-into-work → HF:impl → HF:test → HF:docs-handoff → GATE:done. IAC — 1–3 строки секции master. Skip stabilize/compress/REV/HF:plan/backup/ORCH только по канону LIGHT и сохранённым done, не самовольным удалением уже обязательных фаз.

## Б21. BUGFIX

Любой баг начинается полным init до диагноза: BUG:diagnose → GATE:diagnose-review → TZ:patch → [REV:tz по recipe/объёму] → TZ:finalize → GATE:take-into-work → HF:plan → REV:plan → GATE:plan-approve → HF:backup → HF:impl → HF:test → HF:docs-handoff → ORCH:shared-state → GATE:done. HF:compress не добавляется ради отсутствующего extract.

BUG:diagnose — read-only архитектор: факты, гипотезы, план, оценка LIGHT в _fix_plan_YYYYMMDD.md. Конкретная дата Europe/Moscow фиксируется OutputRef при emit; при invoke после полуночи путь не пересчитывается. Диагноз не разрешает код «заодно».

## Б22. BUGFIX-LIGHT

Только после GATE:diagnose-review и улики объёма Б20. Сохраняет BUG:diagnose/GATE:diagnose-review, далее LIGHT-хвост. План — принятый _fix_plan с IAC; без выдуманного HF-plan/compress. Сужение только штатным set-case.

## Б23. RESEARCH

RS:collect → RS:analyze → [REV:report] → GATE:done. Нет реализации, TZ-WRITE, take-into-work или ORCH. Сбор — факты, анализ — отчёт/AC, review — независимый вердикт, done — доставленный отчёт. Документный проект не заменяет утверждённый master. G3 неприменим при отсутствии impl.

## Б24. MIGRATION

TZ-WRITE(freeze) → GATE:take-into-work → MIG:plan → GATE:plan-approve → HF:backup → (MIG:block-k → GATE:block-accept)* → ORCH:shared-state → GATE:done. Блоки добавляет штатный recipe-add по плану, роль architect сохраняется. Каждый блок требует собственного never-auto accept Саши.

Общий pipeline_mig_complete_guard допускает следующий slot, emit/invoke/direct complete только по собственным identity/evidence/hash/timestamp/receipt каждого предыдущего блока. Aggregate GATE:block-accept не proof. Ранний ORCH/done до последнего accept отказывает без мутации; sirene-фазы не получают packet/invoke.

## Б25. DECOMM

DEC:inventory → GATE:go → HF:backup → DEC:exec → ORCH:shared-state → GATE:done. Инвентарь всех путей, never-auto «удаляй» с цитатой/ts, проверенный backup, затем архивирование и shared-state. Рецепт не даёт rm без evidence. Откат на канбан не является разрешением DECOMM без собственной приёмки.

## Б26. SKILL-DEV

DEV в hermes-workspace/skills, REV default ON, размерный preflight и обязательный restore на ORCH. Крупный SKILL.md требует compress по Б27.

## Б27. SKILL-CHANGE

SK:preflight — механический wc -c оркестратора, затем подтверждённая CHANGE либо DECOMM ветка в skill_change_branch. Новый маршрут использует следующий приоритет:

| Условие | Следствие |
|---|---|
| SKILL.md больше 15 000 байт | Compress обязателен независимо от количества файлов |
| Размер равен порогу или меньше, implementation ≤3 файлов | Допустим малый маршрут/skip compress и REV по канону, если остальные ограничения LIGHT соблюдены |
| Больше трёх implementation-файлов, shared или другие ограничения | Полный соответствующий маршрут |
| Исторический индивидуальный skip | Только факт своего старого поезда; не прецедент для нового |

Это десятичный порог в байтах, strict >. Он уточняет прежнее 15k; размер части extract измеряется отдельно в Unicode, Б60.5. Already required compress нельзя убрать из recipe ради новой упаковки.

## Б28. Идеи

idea=true сохраняет запрос и origin без автостарта. Разбор только по явной постановке и после освобождения потока. Передача в готовую задачу связывает один обычный slug с origin.idea_slug; исходная idea получает ссылку передачи и не считается второй задачей. Готовность/FIFO — Б55.2.

## Б32. Ошибки и origin

Технические ошибки DevWorkflow: report_error.sh через pipeline_errorbus.py, --tool dev_workflow, :11112, --source-kind, не --source_kind; rc/stage/cmdline/log-path/llm-model/detail передаются с безопасной диагностикой. Не Monitoring :7. Кейсовые HITL, AC-shown/AC-delivered, WAIT/DONE/INTERRUPTED и warn — существующий origin chat/thread, без stdout роли. Severity/нотификация амортизируются по смыслу, не на каждый increment дедупа. Новый канал и ErrorBus cron не создаются.

## Б33. Запреты

- Ноль патчей hermes-agent, gateway/session.py, kanban_*; ноль systemd hooks на update и restart Gateway из этого процесса без установленного operator-допуска.
- Нет минутного dispatcher, heartbeat/reaper/claim_lock/max_in_progress, канбан-клона, возраста started_at как повода kill, живого kanban.db как SoT или SQL write состояния разработки.
- Нет нового сервиса, БД, очереди, канала, cron, budget engine или global mutex. **[NEW-ENTITY, требует согласования Саши]** не сглаживать. No new service, database, queue, channel, cron, budget engine or global mutex.
- Кроны только после «ставь кроны», удаление требующих этого объектов только после «удаляй». dwka_guard.sh не канон/механизм recover; не исполнять и не удалять в обход его hold.
- Секреты не в YAML/git/packet; per-tool .env запрещён. Исполнитель не пишет общий manifest/секреты/jobs; новые YAML-ключи не добавляются «на будущее».
- Нет ручной правки process state/journal/queue, accepted packet/sidecar/prepare, backfill proof, reset counters и переписывания чужой истории. Любая запись только штатным writer разрешённой фазы.
- Нет подмены case/recipe/G6, обязательной ревизии или операторского словаря; нет склейки ролей и HF:impl/HF:test, process commands из живой содержательной роли.
- Нет --force/ручного prompt/--continue, повторного invoke при живом wrapper, неверного canonical или complete без проверяемого evidence. PID обёртки не заменяется agent/pgid/session_id.
- Нет безлимитного retry, второго recover той же пары, обхода quota backend/моделью/аккаунтом/slug, перестановки FIFO без указания Саши. Лимиты ходов не переносятся в ядро/agent.max_turns/tool_loop_guardrails.warn_after.
- Не считать extract SoT, не обрезать имена/пакет/обязательные секции, не шарить extract между слагами; нет неявного отсутствия ранее произведённого extract.
- Не переносить recovery/case/phase ownership в cursor-cli, не удалять Cursor rollback. Компрессор использует выбранную YAML ветку по Б60; координатор остаётся sirene.
- Не возобновлять Б58/Б59, B3/B4/w3/w4 и иные явные паузы; не присваивать исторический candidate/done/approval другой задаче. Runtime FAIL/no-entry не становится PASS по закрытию процесса.
- Не подменять DevWorkflow профильными USERTOOLS; mfkt→MOFS→PFS→OFC, секреты/migration statuses EcosystemIntegration и предметные контракты меняются только своей разрешённой задачей.

## Б34. Приёмка

Классификация AC и объявление операторской зависимости — по единому контракту Б17.5.

Ниже один полный критерий на ID в действующем процессе. Общие обязанности заданы тематическими блоками, таблицы задают наблюдаемые проверки. Исторические/смежные AC и индивидуальные IAC хранят исходные oracle и владельцев в приложении; их перенос не является отменой или новым глобальным AC. Диапазон AC-052…057 зарезервирован за отсутствовавшим корпусом, номера не восстанавливаются догадкой.

| AC | Класс | Проверка |
|---|---|---|
| AC-001 | S | Три слоя на диске; ноль кода в hermes-agent; ноль импортов kanban_* в pipeline/ |
| AC-002 | S | SoT = `_state.json`; queue.json пересобирается из glob |
| AC-003 | S | flock + atomic rename + append journal; abort не rm |
| AC-004 | S | glob vs index: repair / CRISIS + ErrorBus; state_sha256 |
| AC-006 | S | CHANGE: полный recipe Б18, skip только табличный или flag-waived |
| AC-007 | S | complete-phase без --reason/--evidence → exit 2, state не меняется |
| AC-008 | S | мёртвый PID → interrupted, без reaper и авто-spawn. классификация interrupt остаётся; ход Сирени на recoverable — AC-071 (`RECOVER`), не этот AC |
| AC-009 | S | billing / 90-90 → interrupted + ErrorBus, без авто-ретрая |
| AC-010 | S | нет минутного цикла, нет heartbeat/claim/max_in_progress в коде pipeline |
| AC-011 | S | G3: changed_files HF:impl в git-worktree закоммичены до HF:test и GATE:done |
| AC-012 | S | Emit обязателен, --force отсутствует; полный immutable packet, доктрина/MUST-read, exact context-used binding Б56; готовая часть extract ≤5120 Unicode по Б60. |
| AC-013 | S | invoke_role: три бэкенда; скилл не вызывает `agent -p` в обход адаптера |
| AC-014 | S | конфиг только EcosystemConfig `tools.dev_workflow`; нет per-tool .env |
| AC-015 | S | ошибки инструмента в ErrorBus :11112; кейс — origin |
| AC-020 | S | `pipeline status --check` exit 1 если контур задет (нет скилла/pipeline/импорт kanban) |
| AC-021 | S | LIGHT = set-case одна функция; второго create-батча нет |
| AC-022 | S | status=done слага только после GATE:done done |
| AC-023 | S | S/O/C; operator-done требует evidence; open Q валит preflight |
| AC-025 | S | install.md: чистый `status --check` на конфиге другого корня (фикстура путей) |
| AC-026 | S | CLI: reason обязателен на complete/hold/interrupt/abort; также на `recover`; evidence — на complete/operator-done/`recover` |
| AC-027 | S | journal: все поля Б10.2; неполная запись → exit 1 |
| AC-028 | S | Полные действующие oracle A1–C15 определены в Б34.1; изолированные фикстуры/чеклист проверяют каждый, без чтения истории и без живого убийства агента. |
| AC-030 | S | HF:test зовёт probe боевого python |
| AC-031 | S | preflight перенесён: нет kanban.db, есть mandatory_phases/holds/AC-report/git_proof |
| AC-032 | S | имена фаз/кейсов = канон Б6; запрещённые синонимы GLOSSARY §7 соблюдены в скилле |
| AC-037 | S | цикл архитектор↔ревизор в новом движке (Б16.1): REQUEST-CHANGES не complete REV и не auto-promote к finalize; вердикт вернулся архитектору; повторный APPROVE; смена фазы без потери `_state.json` |
| AC-038 | S | reuse `extract.md` внутри слага при том же `extract_key` без повторного compress; между слагами файл не подхватывается |
| AC-039 | S | после bump `tz_version` / mtime emit-prompt не берёт старую выжимку; G1 красный, если `extract_sha256` не от текущей version |
| AC-040 | S | handoff-фикстура чужого `DEV_STATE_ROOT`: bundle без sqlite, перепись путей из YAML, `pipeline check` / G1 на приёме; `/tmp/task.md` не в bundle |
| AC-041 | S | complete `TZ:compress` / `HF:compress` запрещён при непокрытых священных именах master vs extract; часть 1/N вместо молчаливой обрезки |
| AC-042 | S | комплект поставки (скилл + pipeline + шаблон конфига + docs) разворачивается на чистом контуре по onboarding/install; пилотный смоук без знания внутренностей |
| AC-044 | S | Файрвол ролей: Сирень не пишет ТЗ/код, не предлагает слаги и технические варианты; архитектор — ТЗ/план/диагноз, не боевой код и не `HF:test`; ревизор — только проверка; исполнитель — только план, неясно → возврат архитектору |
| AC-045 | S | Вход «баг + слаги»: `init --case BUGFIX` сразу; в origin нет нумерованного меню слагов/решений от оркестратора до `invoke_role` architect |
| AC-046 | S | suggest-slug возвращает один kebab ≤48; init без --slug/--slug-source успешно вычисляет suggest-cli; отсутствующий/подменённый сохранённый slug_source отвергается. Kind task запрещён. |
| AC-047 | S | G6: таблица Б6 покрывает все фазы recipe десяти кейсов, включая RS:collect, MIG:block-k и SK:preflight; нет строки — exit 1. Для содержательных фаз сверяются `phases.<PHASE>.role` и accepted invocation. Обычный CLI writer с actor=cli и правильной принятой ролью проходит при прочих G1–G5; отсутствие/чужая принятая роль даёт exit 1 независимо от actor, в том числе actor=architect не легализует неверную роль. SK:preflight с содержательной invoke-ролью и emit/invoke с чужой ролью отказаны. Канонический basename и свежесть результата — Б13; неканонный файл даёт fail+hint. Вердикт и конфликт полей — Б16.1. |
| AC-048 | S | `pipeline status --slug` показывает стадию, кто делает, ход Саши |
| AC-049 | S | Origin = вход требований + выход отчётности; stdout роли в origin не копируется; оркестрация = файлы + subprocess. `[NEW-ENTITY]` канал не создаётся |
| AC-058 | S | Occupancy-дедлок: после `next`→WORK на sirene-фазе G6 — в том же ходе `complete-phase` или `interrupt`; leftover `in_phase`+`doing`+`pid=None` — дефект; CLI чужой слаг не mutex |
| AC-059 | S | На изолированном слаге abort сохраняет каталог и journal, устанавливает aborted; повторный init того же имени даёт exit 1. Interrupt до abort сохраняет имя незавершённой задачи и позволяет штатное продолжение через writer; ручной JSON-write запрещён. Правило членства и занятых имён — Б10. Исторические пилоты не возобновляются. |
| AC-060 | S | Sirene с pid=None → WORK без interrupt; true-crash invoke без role → RECOVER при счётчике 0, иначе INTERRUPTED; leftover --check красный без автоматической мутации. |
| AC-061 | S | `invoke_role` записывает `st.pid` и `phases[phase].pid` на `write_state` `invoke_prepare` **до** spawn адаптера (`os.getpid()` обёртки). После `invoke_prepare` (stub backend) `read_state().pid` = pid CLI и `pid_alive` |
| AC-062 | S | Post-invoke doing + role + мёртвый wrapper → WORK без dead-pid. При role is None true-crash использует AC-071 и Б16.6. |
| AC-063 | S | Leftover sirene ≠ живой invoke с незаписанным pid. Оркестратор не заводит второй поезд и не `next`/`interrupt` по `pid=None`, пока `ps` показывает `pipeline.cli invoke-role --slug <этот>`. `--check` leftover invoke только при `role is None`; живой pid после AC-061 = running. CLI-gate `complete-phase` тоже ждёт конца wrapper — AC-076/078, корпус этого AC не откатывать |
| AC-064 | S | Запрет отсекателя stdout (head/tail/SIGPIPE), фон без пайпа и полный безопасный oracle заданы в Б13. Фикстура/чеклист проверяет явный запрет в SKILL.md и этом ТЗ; живым убийством агента SIGPIPE не проверять. |
| AC-065 | S | Классификатор fatal структурно-осознанный: JSON `--output-format json` парсится как JSON (`is_error`/`type=="error"` → fatal); не-JSON — fallback на строгие сигнатуры провайдера, **без** голых `timeout`/`credits`/`billing`/`payment`; «выполнил, но в тексте есть бытовая лексика» → НЕ fatal. Юнит: `{"result":"timeout 120-300s"}` → False; `{"is_error":true}` / `iteration 90/90` / `http 503` → True. валидный JSON `is_error=false`/без error-поля → НЕ fatal при любом тексте в `result` (цитата `Request timed out` ≠ сбой провайдера). Трёхзначный control-flow и envelope-приоритет — Б13 / AC-119 (корпус 0.4.7 не откатывать) |
| AC-066 | S | Rc 124/137/143 сам по себе не provider-fatal и не retry: проверить writers/result/receipt, затем применимый регламент Б55.5; повтор без нового основания запрещён. |
| AC-067 | S | ErrorBus флаг согласован: `pipeline_errorbus` шлёт `--source-kind` (дефис), не `--source_kind`; событие несёт `--exit-code`/`--stage`/`--cmdline`/`--log-path`/`--llm-model`/`--detail`. Фикстура: событие содержит rc/role/слаг/причину, не пустые поля |
| AC-068 | S | Fatal-ветка invoke_role передаёт report detail/exit_code/stage/cmdline/llm_model с причиной, rc/ролью/slug и redacted командой; событие самодиагностируемо. Terminal kill классифицируется отдельно по AC-066, не объявляется provider-fatal по одному rc. |
| AC-069 | S | Severity/нотификация ErrorBus амортизированы по смыслу, не на каждый increment дедупа за 24 часа. Живой прогон слаг-паритета на штатном пути Б13.2/Б32: timeout/credits в успешном тексте роли даёт собранный статус без ErrorBus; искусственный http 503/iteration 90/90 даёт fatal с полным detail. Историческое закрытие чужого события не условие нового прогона. |
| AC-070 | S | Юнит-тесты `classify_provider_fatal`/`refuse_clean_exit_on_fatal`: «выполнил, но текст содержит timeout/credits/billing» → False; `is_error:true` / `iteration 90/90` / `http 503` → True; флаг ErrorBus `--source-kind` корректно парсится (не `--source_kind`). юнит `{"result":"…Request timed out…","is_error":false}` → False (дырка корпуса 0.4.7). Envelope `is_error=true` / не-JSON `Request timed out` → True. Б13 / AC-120 |
| AC-071 | S | Pre-invoke (`awaiting_invoke`+`pid=None`) ≠ dead-pid (`next`→WORK). True-crash invoke (мёртвый pid, `role is None`, нет live ps) → `action=RECOVER` при счётчике 0: `pipeline recover` (write_state, не spawn) + origin warn класс S + `next` в том же ходе. Второй тот же класс → INTERRUPTED. Нет крон/reaper/авто-spawn |
| AC-072 | S | G6 mismatch: exit 1 + journal `g6_role_mismatch`, state кроме journal не менять (корпус AC-047). Оркестратор в том же ходе зовёт `invoke_role` с ролью таблицы G6 (первый правильный вызов) + warn origin. Не interrupt, не второй поезд |
| AC-073 | S | Пустой/усечённый JSON `result` при rc=0 не proof. Канон расширен: `TZ-patch.md`, `_fix_plan_YYYYMMDD.md`, `RS-collect.md` / `RS-analyze.md`, `MIG-plan.md` (+ старые REV/extract/HF-plan). Нет канона → invoke_role ≠ 0; один correction-pass с файловой доставкой. Канон на диске + короткий `result` = успех |
| AC-074 | S | rc=0 ≠ фаза закрыта. Канон есть + `role` проставлен + `doing` → same-turn `complete-phase` (окно AC-062), не re-invoke. Канона нет → AC-073. `complete-phase` без evidence по-прежнему exit 2 |
| AC-075 | S | `invoke_prepare` пишет `phases[phase].model` (resolved `--model` / YAML roles) и `backend`; `complete-phase` architect/reviewer/executor при `model is None` → exit ≠ 0. `status --slug` показывает модель после prepare |
| AC-076 | S | После фонового invoke-role проверяются exact slug/phase, journal, канон/receipt и завершение wrapper по Б13/Б55.4. Записанный файл, invoke_role в journal или notify по отдельности не доказывают выход wrapper. Пока wrapper жив, next новой фазы/второй invoke/complete-phase запрещены. |
| AC-077 | S | `invoke_role` после rc=0 / correction пишет `phases[phase].session_id` из JSON агента. `--resume` AC-073 берёт поле, когда wrapper мёртв. Не SoT pid (AC-061 не переписывать) |
| AC-078 | S | Occupancy CLI: `complete-phase` / `next` (старт новой invoke-фазы / `st.pid=None`) / повторный `invoke-role` / `recover` → exit 1, пока `invoke_wrapper_alive(slug)`. Обнуление pid на `next` новой фазы (cli.py:83–85) остаётся для pre-invoke, **не** поверх живого предыдущего wrapper |
| AC-079 | S | Doorbell: 0-токенный `pipeline doorbell` считает fingerprint очереди; тот же отпечаток → молчание; смена → wake Сирень (существующий канал), она одна `pipeline next`. Не копия `dwka_guard.sh`. Не recover/spawn/kill. `jobs.json` в этом поезде не пишется; GATE:done **не** ждёт крона |
| AC-081 | S | `run_codex` собирает `codex exec -C <ABS> -m <id> -c model_reasoning_effort='"<effort>"' --skip-git-repo-check --json --sandbox danger-full-access` + operand = тело prompt-file. Нет `run`, нет `--cwd`, нет `--full-auto`. Юнит: argv фикстуры |
| AC-084 | S | Вызов из gateway несёт `--sandbox danger-full-access`. Смоук: роль **записывает** канонический файл (read-only sandbox → fail) |
| AC-085 | S | Каждый `codex exec` роли несёт `--skip-git-repo-check`. Смоук на workspace без `.git` (TZ / USERTOOLS) → rc не «not a git repo» |
| AC-088 | S | При выбранном default_backend: cursor-cli architect/reviewer/executor, включая LIGHT, используют только roles_cursor.<role>; roles.executor_light и Codex roles не читаются. Сохранены run_cursor_cli и agent -p; модель/override в argv и phases[phase].model на prepare совпадают. Проверка resolver — Б13.2; значения берутся из YAML. |
| AC-089 | S | `parse_agent_session_id` (или сосед) принимает Codex `--json` stream; `phases[phase].session_id` пишется. AC-061 pid=wrapper не менять |
| AC-090 | S | Backend-aware resolver Б13.2: codex + LIGHT executor использует roles.executor_light, codex без LIGHT — roles.executor, cursor-cli включая LIGHT — только roles_cursor.executor. Для architect/reviewer берётся соответствующая роль выбранной ветки. Явный override одинаково отражён в argv и phases[phase].model уже на invoke_prepare; значения модели/effort задаёт YAML. |
| AC-092 | S | Скилл `dev-workflow` не вызывает `agent -p` и не вызывает `codex exec` в обход `invoke_role`. Три бэкенда адаптера на месте (AC-013 не откатывать) |
| AC-093 | S | Codex auth/provider fatal **структурно** (Б13, корпус AC-119/120): True только при (а) событии ошибки в разобранном Codex `--json` JSONL (`is_error`/`type=="error"`/код клиента с 401 или `token_expired` в поле ошибки, не в `result` успешного события), либо (б) не-JSON stderr/stdout с сигнатурой отказа клиента (строгий fallback). Цитата `HTTP 401` / `token_expired` **внутри** содержательного текста успешного события → False. При смешанном потоке приоритет у **любого** структурного события ошибки. Реальный отказ → rc≠0, ErrorBus, **без** авто-ретрая (корпус AC-009). Не clean-exit 0 |
| AC-097 | S | references/context.md для TZ:patch содержит перечень MUST-read Б12 с точной привязкой ReadRef Б56.4; нет единственной обязанности «всегда весь master». Условия полного чтения и чтение выбранных секций без обрезки сохранены. |
| AC-098 | S | На изолированной фикстуре TZ:patch emit-prompt передаёт полный перечень MUST-read Б12 и ReadRef Б56.4 по принятому заданию; последний БNN/история не подменяют привязку. |
| AC-099 | S | Evidence фазы показывает чтение полных выбранных секций Б12/Б56.4; при условии обязательного полного master прочитан весь файл без обрезки. Для штатного sections-режима полный файл сверх перечня не требуется. |
| AC-102 | S | `pytest` `test_http_429_fatal` / `http 503` зелёные; нет нового модуля retry |
| AC-104 | S | Pytest: `next` на фазе из `AUTO_GATES` при улике → `complete-phase`, `invoke_role` не звался |
| AC-106 | S | Если проверка зелёная с первого раза — impl-дифф по гейтам пуст |
| AC-108 | S | HF 26-й / GATE 5-й / TZ 21-й invoke → budget_exhausted:phase-turns, backend не spawn; поле turn_count и limits Б49, без ослабления 90-90. |
| AC-109 | S | Pytest doorbell: тот же fp; живой pid+mtime канона → fp тот же; смерть pid+mtime → fp другой; tick `queue=<n>` без WAKE/next/recover; смена n → fp другой; нет копии `dwka_guard.sh` n считается по единой проекции готовых задач Б55.6. |
| AC-116 | S | `pipeline doorbell` / tick не импортирует и не exec `dwka_guard.sh` |
| AC-117 | S | `cmd_set_case`: после `set_case(d, case)` — `d.pop("state_sha256", None)` до `from_dict`/`write_state`. CLI `set-case` rc=0, stderr без `CRISIS: state_sha256 mismatch`; повтор на тот же LIGHT тоже 0; диск: `from_dict` не `SystemExit`, `read_state` ок, `case`/`recipe` сужены, sha файла = `to_dict`. `from_dict` и `set_case` без правок смысла |
| AC-118 | S | `pytest pipeline/tests/test_set_case_light.py`: (1) CLI round-trip как оператор; (2) unit: после `set_case` dict с живым старым sha → `from_dict` CRISIS; после `pop` — ок. Живые `_state.json` чужих слагов не трогать |
| AC-119 | S | Трёхзначный control-flow `_fatal_reason` / `classify_provider_fatal`: (а) валидный JSON `is_error=false`/без error-поля → не provider-fatal, `FATAL_PATTERNS` по `result` не гонять; (б) валидный JSON `is_error=true`/`type=="error"` → fatal, envelope выигрывает у цитат; (в) не-JSON → fallback на строгие сигнатуры (сообщение клиента/парсера). Список `FATAL_PATTERNS` не сокращать; `provider_fatal` non-recoverable |
| AC-120 | S | `pytest pipeline/tests/test_invoke_fatal.py`: JSON `{"result":"…Request timed out…","is_error":false}` и тот же result без `is_error` → `classify` False, `_fatal_reason` None, `refuse_clean_exit` False; `{"is_error":true,"error":"Request timed out"}` / `{"type":"error",…}` → True (json-ветка); не-JSON `"Request timed out"` → True (pattern); бытовое `"timeout 120-300s"` JSON и plain → False (регресс AC-065). Существующие AC-065/066/070 не ломать. Проверяемые файлы: `invoke_role.py` + `test_invoke_fatal.py` |

### Б34.1 Самостоятельные oracle A1–C15

AC-028 проверяется на изолированных фикстурах/чеклистом по всем строкам ниже. Метки сохраняют происхождение проверок, не требуют чтения истории и не создают новый маршрут. Старые исходы сопоставлены действующему процессу с учётом Б55; historical retry/triage не восстанавливаются.

| Метка | Полный наблюдаемый oracle | Действующая норма |
|---|---|---|
| A1 | Rc=0 без evidence/канона не закрывает фазу; пригодный результат после выхода wrapper принимается обычным complete однократно. Успешный JSON с цитатой ошибки не provider-fatal. Нет диспетчера, повторяющего вызов. | Б13, Б16.1, Б8 |
| A2 | Реальное exhaustion 90/90 даёт interrupted и ErrorBus; автоматического retry/spawn нет. | Б13.2, Б55.4 |
| A3 | Sirene без PID и штатный pre-invoke дают WORK; живой wrapper не interrupt; post-invoke с принятой ролью даёт WORK. True-crash без роли/результата допускает один RECOVER, затем INTERRUPTED. Running требует живого PID; check показывает leftover без автоматической мутации. | Б13, Б16.6, Б55.6 |
| A4 | Нет claim_lock/re-claim; продолжение читает файловую SoT и не повторяет принятый результат. | Б10, Б13, Б33 |
| A5 | Нет failure_limit/streak-диспетчера и его retry; применяются три ограниченных регламента с неизменяемыми счётчиками. | Б33, Б55.5 |
| B6 | Возраст started_at не запускает block/kill; нет rule4, минутного dispatcher/reaper. | Б33, Б55.6 |
| B7 | Operator-hold отражается waiting_operator и удерживает текущую задачу; класс O не создаёт recurrence/triage-поезд. | Б17, Б55.2 |
| B8 | На init есть полный recipe, G4 не пропускает обязательные фазы; LIGHT сужается одной set-case без карточных рёбер/второго init. | Б6, Б8, Б20 |
| B9 | Python не убивает PID как kill-on-restart dispatcher; работа live wrapper защищена. | Б13, Б33 |
| B10 | Idea не стартует сама и не выдёргивается из triage; продвижение связывает один обычный slug с источником, сохраняет FIFO. | Б28, Б55.2 |
| B11 | Нет claim; complete без evidence запрещён; пустой/усечённый результат без канона не proof. | Б8, Б13 |
| C12 | Отсутствующие reason/evidence дают предусмотренный CLI exit 2 без записи; status строится из state и показывает фазу/роль/ход Саши, без потерянной колонки. | Б8, Б55.6 |
| C13 | Ожидание оператора едино: waiting_operator с причиной и matching hold; blocked не скрывает HITL и не освобождает FIFO. | Б17, Б55.2, Б55.6 |
| C14 | Модель разрешает единый invoke adapter из выбранной YAML-ветки/допустимого override, не карточный model_override/D1; missing model/auth отказывает по своему классу без обхода. | Б13.2, Б60.4 |
| C15 | Journal/jsonl/state сохраняют обязательные события и provenance; история доступна без SQL/kanban show; неполное событие не мутирует state. | Б10.2 |

## Б49. Лимиты ходов фазы

Ход фазы — один принятый cmd_invoke_role пары slug/phase, включая resume/correction, не внутренний tool-call. turn_count увеличивается на prepare вместе с PID; invalid outer terminal request его не увеличивает. Перед spawn: следующий ход сверх лимита даёт budget_exhausted:phase-turns, interrupt/ErrorBus, ненулевой rc и ноль backend sends. GATE ≤ 4, TZ/REV ≤20, HF ≤ 25, BUG/RS/MIG/DEC ≤20. Для sirene-гейтов G6 запрещает invoke; лимит страхует ошибку. Не менять agent.max_turns/goals/delegation и tool_loop_guardrails ради этой нормы.

Предметные Telegram watcher/telemetry/anomaly scan, их AC-094…096/112/113/121…128 и точные fixtures находятся в отдельном приложении у прежних владельцев. Отсутствующая/нечитаемая lease запрещает закрытие; T1 требует проверенную истёкшую запись или принятое свидетельство освобождения. Это сохранение C02, не запуск watcher и не изменение jobs.

## Б55. Одна задача, FIFO и непрерывное продолжение

### Б55.2 Приём, готовность и FIFO

1. Оркестратор сохраняет каждый новый запрос с исходным текстом, origin и временем поступления. Повторная доставка того же запроса дополняет его запись, не создаёт второй исполняемый поезд. Пока другая задача занята, допустимы регистрация и приём фактов; вторую содержательную роль не звать.
2. **idea** — объём или требования ещё не закрыты. Использовать существующий `idea=true` и механизм Б28; `pipeline init --idea` не означает автозапуск `RS:collect`/`IDEA:analyze`. Разбор idea начинается только по явной постановке и после освобождения единственного потока. Нового кейса `idea` не вводить.
3. **Готовая задача** — проработанная постановка по существующему ТЗ либо срочный баг с достаточными фактами для канонного `BUG:diagnose`. Готовый запрос не ждёт повторного «берём в работу». Срочность бага не даёт автоматического права обогнать ранее готовые задачи.
4. Для планового изменения до исполнения известны master, объём, запреты и принятые требования; до `GATE:take-into-work` закрыты содержательные вопросы и пройдена требуемая ревизия. Для бага до диагноза не требуют известного root cause: диагноз входит в ту же единственную задачу. Неподготовленный запрос сохраняется в triage.
5. FIFO считается по **первой подтверждённой готовности к очереди**, а не по имени каталога, mtime, последнему `next` или возрасту сырой idea. Время приёма сохраняется отдельно для измерения ожидания. При одинаковом времени — порядок записи в существующем `queue.log.jsonl`, затем slug как стабильная развязка. Смена порядка — только дословная дополнительная инструкция Саши с origin и временем в журнале.
6. Для новых готовых запросов время `init` может служить временем готовности. Для ранее сохранённой idea готовность фиксируется отдельной датированной записью журнала с evidence закрытой постановки. Продвижение по существующему Б28 связывает idea и один обычный слаг; исходная idea получает ссылку «передано в <slug>» и больше не считается вторым незавершённым запросом. Массовое пересоздание слагов запрещено.
7. Выбранная первая задача владеет потоком **до её `GATE:done` и отчёта**, либо явной отмены Сашей с `aborted`. Межфазовый `idle`, ожидание ревизии/контекста/лимита, `blocked`, `interrupted` и `waiting_operator` владение не снимают. Следующую FIFO-задачу в этих случаях не стартовать. При явной отмене хранить причину; отменённая работа не называется выполненной.
8. Зависимости проверяются до дорогого вызова и отражаются в готовности. Зависимую задачу не объявлять готовой при известном незакрытом допуске. Если после выбора обнаружена зависимость от задачи позади неё, очередь не переставлять молча: архитектор с ревизором диагностируют причину и допустимое устранение внутри согласованного объёма. Иначе фиксируется ожидание/противоречие постановке по Б55.3, без второго поезда и без фиктивного done.
9. Выбор следующей задачи делает оркестратор по этим правилам, когда текущая закончена. Python хранит факты и показывает порядок; отдельного диспетчера, глобального mutex или сервиса в этом объёме нет. Одна роль работает в каждый момент; несколько workspace одной фазы обслуживаются последовательно.

Сохраняются `_state.json` схемы `devworkflow-state/1.0`, `idea`, `status`, `phase`, `phases`, `origin`, `operator_holds`, `open_questions`, `recover_counts`, `journal.md` и вычисляемый `queue.json`. Время готовности, назначение текущей задачи, причина ожидания, ссылка на приоритет и передача idea — датированные факты существующего журнала; это не новая схема task packet. Их запись использует `write_state`/существующие валидные события с `reason`/`evidence`; новые root-поля, event enum и CLI-флаги без необходимости не вводить. В `HF:plan` показать точное соответствие этим существующим механизмам и согласованное чтение после обрыва. Наличие одной записи `status=in_phase` не доказывает ни глобальный запрет, ни владение задачей до конца.

### Б55.3 Контекст и проверка допущений

Архитектор сначала самостоятельно читает доступные источники задания и адресные логи по проверенным путям, отделяет наблюдение от гипотезы и фиксирует FileRef использованных фактов. Если нужный источник отсутствует или недоступен в разрешённых границах, запрашивает его у оркестратора с точным объектом/путём и причиной. Оркестратор предоставляет недостающие сведения, master и источники; не выбирает содержательное решение за роль.

Предложение новой сущности допустимо только после доказанного отсутствия подходящего существующего решения: архитектор проверяет манифест, inventory и фактический каталог. Отсутствие записи в устаревшем digest не доказывает отсутствие инструмента. Маркер [NEW-ENTITY, требует согласования Саши] сохраняется; границы согласования — Б33.

Содержательные вопросы Саше закрываются при подготовке ТЗ. После детализации требований роли решают рабочие вопросы между собой по вводным; нехватка сведений означает запрос оркестратору и явное ожидание, без выдуманного ответа. Существенное отклонение возвращается архитектору существующим rework затронутого артефакта, без новой фазы или изменения recipe исполнителем.

**Проверка влияния возврата и допущений постановки.** При каждом возврате архитектор фиксирует причину, затронутые допущения и обоснованную границу повторной проверки. Если новая улика опровергает допущение постановки либо выявляет конфликт требований, запретов или разрешённого объёма, архитектор проверяет все связанные маршруты и зависимые предписания до выдачи исправленного решения — а не только предъявленный случай. Ревизор независимо проверяет основания выбранной границы, истинность существенных допущений (конкретный исходник, версия SDK, трасса либо изолированное воспроизведение; «так уже работает» и исторический зелёный regression недостаточны) и устранение связанных противоречий. Глубину выбирают по связям и риску: локальная незавершённость реализации — точечное исправление; противоречие постановки фактическому поведению кода/SDK или новому факту, затрагивающему запреты/scope — сквозная перепроверка всей затронутой границы; опровергнутое общее допущение с неустранимо широким влиянием — полная перепроверка постановки в пределах задачи. Результат включается в обычные plan/rework evidence и REV: `допущение → источник/версия → связанные ветви и требования → проверка → вывод`. Содержательное изменение плана проходит штатное согласование; незавершённость реализации его не запускает. Само наличие слова «owner», «scope» или «product-gap» глубину не определяет: существенен факт изменения основания разрешений и требований.

### Б55.4 Продолжение, круглосуточность и ожидание лимита

Основной триггер продолжения — **событие окончания роли** через существующий background completion/notify. Оно будит оркестратора; сам notify не является proof окончания wrapper. Оркестратор сверяет точный `(slug, phase)`, живость wrapper, журнал и канонный артефакт, затем закрывает фазу или применяет один из регламентов Б55.5. После закрытия берёт следующую фазу; после завершения задачи — следующую FIFO. Сообщение Саши для этих переходов не требуется.

| Наблюдение | Действие |
|---|---|
| Wrapper жив, в том числе файл уже записан | Ждать окончания; не `complete-phase`, не второй invoke и не переход другой задачи. Роль пишет свой артефакт; не мониторит собственный wrapper вместо результата. |
| Wrapper завершён, канон свежий, результат проверен | Обычный `complete-phase` с evidence; post-invoke WORK/RECONCILE не превращать в dead-pid. |
| Обрыв после записи результата, завершение фазы не записано | Сначала сверить/принять уже имеющийся результат по Б13, G1/G2 и канону; не перезапускать роль для повторной записи того же файла. Нет достаточных доказательств — явное ожидание/диагноз, без ложного PASS. |
| Повторное событие старой фазы или повторная доставка результата | Уже обработанный результат — no-op; не второй `complete`, invoke, уведомление или запуск следующего слага ещё раз. Использовать имеющийся receipt, если он реализован; при его отсутствии сверять канон и завершённые переходы. |
| Утрачен основной сигнал completion | Проверенный существующий doorbell обнаруживает смену состояния и будит оркестратора; это страховка, а не основная оркестрация. |
| Recoverable сбой без пригодного результата, wrapper мёртв | «Техническое восстановление» Б55.5. |
| Provider refusal, auth/billing, 5xx без признака восстановления | Ожидание причины и подтверждения её устранения; авто-restart/recover не делать. |
| Исчерпан возобновляемый лимит роли | Ожидание лимита с основанием и условием возобновления; после подтверждённого восстановления продолжить эту же фазу. |
| Явная пауза Саши / operator-действие / кризис | Ожидание с точной причиной; не снимать по таймеру и не пропускать вперёд очередь. |

Роли могут стартовать **24 часа в сутки, 7 дней в неделю**. Старое окно будней 19:00–09:00 MSK и его WAIT_WINDOW отменены. Лимит роли не обходят сменой аккаунта, backend/модели, очищением счётчиков, новым слагом или массовым reset. Штат Codex и Cursor как откат остаются; наличие отката не является разрешением обхода лимита.

Ожидание лимита имеет evidence ответа провайдера, время начала и известное условие возврата доступности. `Retry-After`/время reset, когда они действительно получены, задают ближайший допустимый момент проверки; выдумывать их нельзя. Возобновление выполняется по существующему сигналу доступности или поддерживаемому одноразовому отложенному wake с одной проверкой после указанного момента, без цикла пробных платных invoke. Неуспешная проверка сохраняет ожидание. При неизвестном сроке нужен внешний подтверждённый сигнал восстановления; watchdog не делает серию provider-запросов. Provider-fatal не становится recoverable: новая попытка после устранённого внешнего условия — явно записанное возобновление, не технический retry.

На `HF:plan` проверить фактическую доставку completion, wake страховки и доступность механизма отложенного события на этом хосте, с адресным исключением для текущего CHANGE по Б61.4: подтверждённые loader/candidate-load/primary facts достаточны для проектирования и независимого согласования плана; оставшиеся end-to-end fallback/availability доказываются на пилоте после `HF:test` prep до окончательного `HF:test` PASS. Для остальных задач момент проверки не меняется. Одного печатного `WAKE` в stdout недостаточно. Если механизм отсутствует или обязательная проверка не подтверждена к установленному моменту, фиксация «ожидание: продолжение не обеспечено» и провал соответствующего AC обязательны; новый сервис, крон или второй канал молча не добавляется. Существующий разрешённый механизм можно проверить и исправить в его границах. Установка расписаний всё ещё требует «ставь кроны»; это ТЗ не даёт такого глагола.

Doorbell сохраняет 0 токенов на неизменном состоянии, wake по смене fingerprint, запрет `next`/`recover`/spawn/kill из tick. Для обзора `queue=<n>` означает незавершённые **готовые** задачи, включая текущую; idea, переданные idea, done и aborted в `n` не входят. Исправление подсчёта использует ту же проекцию Б55.6, не второй набор состояний.

### Б55.5 Три разных регламента повторов

Они ведутся в журнале с разными названиями и причинами. Автоматические новые счётчики и бюджетные блокировки не разрабатываются. Уже имеющиеся `recover_counts`, phase-turn limits и ядровые ограничения сохраняются; отключать их ради нового регламента запрещено.

| Название | Что считается | Предел и действие | Что не является этим повтором |
|---|---|---|---|
| **Техническое восстановление** | Повтор той же фазы после доказанного recoverable сбоя того же класса; существующая пара `recover_counts[phase][class]` внутри слага | Один corrective повтор на класс и фазу. Повторный такой сбой — остановка для диагноза; нового invoke «пока не получится» нет. Смена слова причины не создаёт новый класс. | Приём уже записанного результата; первое исправление G6 до запуска правильной роли; правка решения по REV; изменение требований; ожидание лимита. |
| **Повтор замечания** | Одна и та же неустранённая ошибка повторяется в двух последовательных проверках ревизора: тот же объект, нарушенный контракт и суть дефекта, даже при другом номере/формулировке | Первый REQUEST-CHANGES — доработка. Второе подряд то же замечание — **до третьего круга** остановка и диагноз: почему исправление не устранило причину. Архитектор с ревизором фиксируют изменившийся способ решения и проверку устранения; только затем содержательная доработка продолжается. | Разные новые замечания; технический сбой доставки; новый ответ Саши, действительно меняющий требование. Произвольное переименование старого замечания повтор не обнуляет. |
| **Пересмотр требований** | Новое указание Саши меняет принятый контракт, AC или границы объёма | Отдельная запись: источник/дата, что изменилось, затронутые AC/план/тесты/документация и минимальный возврат к нужной фазе. Изменение согласует архитектор с ревизором; оркестратор исполняет. Числовой лимит смен требований Саша не задавал — не изобретать. | Технический retry, неустранённый баг и просьба «доделай» без изменения принятого содержания. |

Перед любым повтором назвать **один** применимый регламент, ссылку на предыдущее событие и ожидаемое новое evidence. Совпадение нескольких симптомов одного сбоя не даёт по одному повтору на каждый симптом. Отказ провайдера, явная пауза, живой wrapper и CRISIS не расходуют разрешение на автоматическое техническое восстановление и не лечатся им.

Диагноз стопа — работа внутри текущей задачи, без повторного запуска уже исчерпанного действия: разобрать имеющиеся логи/артефакты, назвать причину и проверить её устранение. Если это требует содержательной правки, вернуться к существующей фазе архитектора и ревизора; если внешняя причина не устранена — сохранить ожидание. Счётчики не обнуляются автоматически после диагноза, новой сессии, ревизии, смены требований или «доделай». Отдельное изменение разрешённого объёма не скрывает историю исчерпанного восстановления. Нет доказанного изменения основания — нет повторного invoke. После диагноза архитектор с ревизором различают новую содержательную работу на изменённых входах и запрещённый повтор того же технического действия; сохраняют ссылку на исчерпанный бюджет. Второй `recover` той же пары остаётся запрещённым. Изменение записи причины, модели или слага не считается новым основанием.

### Б55.6 Статусы, завершение и история

Источник — проверенные файлы процесса; `queue.json` перестраиваемый индекс. Обзор не требует отдельной доски. Чтение статуса не запускает работу и не выполняет скрытый recovery. Допустима пересборка производного индекса без изменения состояния задач; `status --check`/repair различаются явно.

| Видимый статус | Условие |
|---|---|
| **triage** | `idea=true`, постановка ещё не передана в готовую задачу; auto-start запрещён. |
| **в очереди** | Готовность подтверждена, рецепт не завершён, задача ещё не выбрана; отображается FIFO-позиция. `idle` само по себе недостаточно. |
| **в работе** | Выбрана текущая задача и реально исполняется её фаза: живой wrapper роли либо работа оркестратора в текущем ходе. Межфазовый переход относится к той же задаче. |
| **ожидание** | Текущая задача удерживает очередь: контекст/зависимость/лимит/диагноз/пауза/оператор/сбой. Показать причину, с какого времени, чей следующий шаг и проверяемое условие продолжения. При мёртвом процессе без результата «в работе» запрещено. |
| **завершение** | Результат и проверки готовы, но ещё выполняются доставка AC-report, shared-state или конечный гейт. Это не `done` и поток ещё занят. |
| **выполнено** | `GATE:done=done`, обязательные фазы/улики/доставка подтверждены, корень `status=done`. Запись исключена из рабочей очереди и сохранена в истории. |

`aborted` показывается в истории как «отменено», не «выполнено». Дата выполнения — подтверждённый `ended_at` конечного гейта; дата последнего изменения каталога её не заменяет. В обзоре по запросу блок выполненных ограничен **последними 48 часами** на момент запроса; более старые доступны в архиве по прямому запросу. Текущие triage/очередь/работа/ожидание показываются независимо от возраста.

Минимум строки: название/slug, статус, фаза, роль, последнее подтверждённое событие, время снимка; при ожидании — причина и следующий шаг. Отсутствующие факты выводятся как «не подтверждено». При ошибке обновления показать «данные устарели, проверены <ISO>; причина <…>», не повторять старую running-строку как актуальную. Возраст сам по себе не является поводом убить роль.

Архив выполненных — существующие каталоги слагов и журналы плюс вычисляемая выборка, без четвёртого корня, новой БД и переноса, меняющего ссылки. Для старого `idle` с done-гейтом сначала сверить финальные доказательства; затем через штатную запись привести корень к `done`, сохранив исходную историю и дату завершения. Если evidence расходятся — явная аномалия/ожидание; не повторный init, не автоматическое повторное исполнение и не выдуманный PASS. При закрытии новой задачи `complete-phase GATE:done` сохраняет `status=done` сразу, а `next` на исчерпанном рецепте не возвращает её в ready.

Стадия процесса, результат проверки и принятие предметной миграции различаются в отчёте. Runtime FAIL остаётся FAIL; no-entry не становится runtime PASS. Текущий новый пакет не завершается при незакрытом обязательном AC.

Для каждой снятой инструкции/обхода до изменения зафиксировать путь, текущих потребителей, владельца заменяющего правила и backup; после — проверить отсутствие активных ссылок и доступность восстановления. Из активных текстов действительно удаляются дубли и нерабочие указания, а не добавляется ещё один абзац приоритета поверх них. Старые частные инциденты остаются локальными ссылками/проверками, без новых общих веток процесса на каждый случай.

### Б55.9 Системные инструкции: сначала загрузка, затем владельцы

Первый шаг — инвентарь фактически загружаемых поверхностей для default, роли через `invoke-role` и применимого рабочего каталога: абсолютный путь, resolved path/симлинк, hash, способ и условие загрузки, порядок/приоритет, подтверждение trace/кода загрузчика. Минимум проверить корневой и `profiles/default/SOUL.md`, общий и проектный AGENTS, HERMES, профиль, фактические USER и MEMORY. Отсутствующие `~/.hermes/AGENTS.md`/`~/.hermes/USER.md` не создавать по предполагаемому имени. Не считать всё, что найдено на диске, одновременно загруженным. Секреты и личное содержимое в отчёт не копировать.

| Правило / данные | Единственный нормативный владелец после проверки загрузки |
|---|---|
| Персона и правила диалога | Фактически активный SOUL; остальные поверхности ссылаются на него. Личные предпочтения сохраняются. |
| Ограничения среды, каталога, разрешения на cron/restart | Применимый AGENTS; дочерний файл содержит только свою область и ссылку, без второй общей процедуры. |
| Процесс, очередь, continuation, recovery | Мастер Б55 задаёт требования; `dev-workflow` содержит одну исполняемую процедуру с отсылкой к этим требованиям, предметные скиллы маршрутизируют к ней. |
| Роли/модели/effort | Значения — существующий `EcosystemConfig.yaml`; инструкции читают его, не поддерживают свои конкурирующие значения. Исторические таблицы мастер-документа не становятся текущим конфигом. |
| Имена фаз/ролей/скиллов | `GLOSSARY.md`; `references/canon.md` — согласованный операционный указатель, не второй каталог синонимов. |
| USER | Предпочтения Саши; устаревшие «без гейтов»/«потом берём в работу» не сохраняются как отдельная норма процесса. |
| MEMORY | Проверенные сведения с источником/актуальностью; устаревшие модели, декомиссованные профили и команды запуска выводятся из активных сведений с сохранением истории. |

После установления фактической загрузки архитектор с ревизором утверждают адресный diff: что удалено, куда перенесён смысл, какие ссылки остались. Оркестратор не переписывает предпочтения и правила по собственному мнению. Скилл `dev-workflow` обязан иметь одну непротиворечивую таблицу действий, включая RECOVER и ожидание лимита; ссылки на отсутствующий корпус заменены Б55. Проверка после правок повторяет загрузку и проверяет конечный prompt, а не только `rg` по одному файлу.

### Б55.10 Реализация и передача управления

Порядок внутри существующего рецепта, без новых фаз:

1. `TZ:patch` → `REV:tz` → `TZ:finalize`: этот master, инвентарь и согласованные AC. При REQUEST-CHANGES — Б55.5. Архитектор не закрывает свою фазу и не вызывает ревизора изнутри живого wrapper; результат передаётся оркестратору.
2. `GATE:take-into-work` показывает AC; `HF:plan` дополняет матрицу требований текущего задания, проверяет фактические механизмы и пишет IAC `path/verify/depends/covers`. Для пилота план называет существующий способ загрузки изменённой процедуры до restore, способ передачи управления после выхода wrapper, точные команды/пути испытания, проверки трасс и конечной загрузки. Для текущего CHANGE по Б61.4 план допускается к независимой `REV:plan` с именованной TZ-зависимостью; до `HF:impl` необходимы собственные `TZ:patch → REV:tz → TZ:finalize`, актуальная связь master/плана/IAC/REV/packet и fresh backup. `REV:plan` проверяет выполнимость этой границы, отсутствие новых тяжёлых механизмов и циклических зависимостей. Затем auto-гейт плана и backup.
3. `HF:impl` исправляет минимальный основной путь и адресные инструкции. Зафиксировать baseline соседей до правок и неизменяемый на время прогона снимок версии процедуры в workspace. До общей синхронизации испытательный контур загружает эту версию через существующий поддерживаемый способ загрузки скилла/контекста Hermes с явными абсолютными путями; изолировать только данные недостаточно. Загрузку подтверждают по Б55.11. Если доступен лишь старый активный скилл или поддерживаемый способ не найден, пилот не готов, AC не закрывается; скрытый ранний общий restore или новый загрузчик не вводить. Shared-state и синхронизация — их штатные операции, не работа исполнителя за оркестратора.
4. `HF:test` — отдельная фаза с последовательной передачей управления, без новой фазы или изменения recipe. Для текущего CHANGE принимающий R0, лабораторный R1 и внешний freeze evidence определены Б61.4; новые guards не приписываются R0:
   - Исполнитель выполняет проверки отказов и подготавливает безопасный контур, входные данные, управляемые ответы ролей и сбор трасс по IAC. Он возвращает подготовленные артефакты и явно незавершённый результат пилота; затем его wrapper должен закончиться. До подтверждённого выхода этого wrapper пилот не стартует, `HF:test` не complete и следующая содержательная роль не вызывается.
   - После выхода wrapper оркестратор проверяет подготовку и запускает испытание Б55.11. Выбор/удержание задания и продолжение исполняет проверяемая изменённая процедура в контексте оркестратора Hermes, а не исполнитель или драйвер. P1…P5 — вложенные испытания текущего пакета в изолированных данных; текущая задача всё время удерживает единственный поток, другие боевые запросы не стартуют. Пилотные результаты содержательных ролей подаются управляемыми заменами; новых живых содержательных ролей внутри пилота нет. Проверяемый оркестратор остаётся оркестратором, новой G6-роли не возникает.
   - По окончании пилота и после прекращения его действий оркестратор передаёт собранные трассы исполнителю отдельным последовательным вызовом на той же `HF:test`. Исполнитель выполняет предусмотренные IAC проверки evidence и пишет окончательный тестовый отчёт; сам не проигрывает недостающие решения оркестратора. Это завершение проверки подготовленного испытания, не технический retry и не разрешение сбросить бюджеты. После выхода этого wrapper оркестратор принимает результат по IAC/AC; только полный PASS позволяет закрыть фазу. Невозможность загрузить новую процедуру, доставить wake, выполнить безопасный runtime или проверить обязательный AC сохраняется как FAIL/ожидание.
5. `HF:docs-handoff` связывает окончательный план, тесты и документацию с фактическим diff; устаревшие нормы удалены из активных поверхностей. `ORCH:shared-state` выполняет разрешённую синхронизацию и проверяет конечные загружаемые поверхности по Б55.11. `GATE:done` — после всех обязательных AC этого пакета, включая связь пилота с конечной загрузкой, с честным отчётом; только затем следующий готовый запрос.

Перед переводом старых записей — инвентарь незавершённых, completed и противоречивых состояний; не повторять законченное. B3/B4/w3/w4 остаются под явной паузой Саши. В частности, исторически done w3/w4 не открываются заново из-за поздней hold-строки; у паузы сохраняется источник и область действия. Совместить её со state можно только с доказательством, без выдуманного operator-done и без расширения словаря `hold`. Для новых задач порядок Б55 применяется после проверки. Старый путь не оставляется вторым активным исполнителем.

Откат исправлений — сохранённые snapshots кода/скиллов/адресных промптов с журналом причины. Не сбрасывать выполненные фазы, пользовательские паузы и бюджеты; не включать старый диспетчер, не рестартовать gateway. Если продолжение после отката не подтверждено, текущая задача остаётся в явном ожидании, очередь не перескакивает.

### Б55.11 Проверки отказов и пять последовательных пилотных заданий

Сначала выполнить проверки отказов Б55.13, затем **пять последовательных заданий** на штатном файловом пути в изолированном `DEV_STATE_ROOT`, с безопасным write-set и восстановлением. Это испытания текущей задачи в `IAC.verify` с передачей управления по Б55.10, а не пять посторонних боевых поездов поверх её живой роли.

**Объект испытания — изменённая исполняемая процедура оркестратора.** Именно она принимает запросы, выбирает следующий готовый запрос по FIFO, удерживает текущий при блокере/лимите/idle, проверяет wrapper и артефакт после completion, обрабатывает доставленный wake страховки и возобновляет ту же фазу. Драйвер подаёт исходные запросы, факты готовности/зависимости, результаты ролей и отказы; собирает трассы и сравнивает их с ожидаемым результатом. Он не выбирает следующий slug/фазу за оркестратора, не вызывает за него `next`/`complete-phase`/`recover` и не задаёт заранее переходы, удержание или возобновление. Порядок P1…P5 должен получиться из входных фактов и решений процедуры; ожидаемый порядок в проверке не является командой драйвера. Подмена ответов содержательных ролей не разрешает подменять саму оркестрацию.

Использовать реальные CLI, штатную запись состояния и фактическую доставку события в контекст проверяемого оркестратора. Изменённые инструкции должны быть доступны ему **до** пилота из workspace через подтверждённый в плане существующий способ загрузки, без отложенного общего restore; при новом ходе/перезапуске контекста сверять загрузку снова. Управляемые отказы моделировать без убийства рабочей роли, Gateway и БД. Только mock completion или напечатанный `WAKE` не доказывает доставку события без Саши.

Для каждой трассы P1…P5 сохраняется связь с реально загруженной версией: абсолютные исходные и resolved пути процедуры/зависимых инструкций, версия либо идентификатор снимка и SHA-256 загруженных байтов; идентификатор контекста/сессии оркестратора, время и trace загрузчика либо полученного контекста, подтверждающий использование этих путей/хешей. Отдельно фиксируется версия/hash master как нормативного источника. Хеш файла на диске без свидетельства загрузки недостаточен. Состав загруженных инструкций и их приоритет должны соответствовать утверждённой матрице Б55.9; старая конкурирующая процедура не должна управлять пилотом. Изменение процедуры во время прогона требует новой привязки и повторной проверки затронутых сценариев, а не переноса PASS со старой версии.

Evidence хранится раздельно с перекрёстными ссылками по заданию/фазе/событию:

| Слой | Обязательное evidence |
|---|---|
| Реальная оркестрация | Загруженная версия и контекст; входные факты и фактические решения оркестратора о FIFO, удержании, приёме результата и продолжении; снимки state/queue/journal до и после. Времена выхода подготовительного wrapper, действий пилота и последующего вызова проверки подтверждают последовательность Б55.10. |
| Транспорт | Отправка и получение completion/wake существующим механизмом с идентификатором/временем и связью с последовавшим действием процедуры. Для страховки отдельно видны пропуск основного сигнала, доставленный wake и продолжение. Поддельный приём события не зачёт. |
| CLI и файловые эффекты | Реальные вызовы с аргументами, rc, канонные артефакты/хеши и штатные переходы состояния; одно выполнение side effect и отсутствие второй исполняемой задачи. Прямое изготовление итогового state драйвером не зачёт. |
| Управляемые результаты ролей и отказы | Какой ответ/отказ подменён, чем и когда подан, исходник/параметры драйвера и их SHA-256; предел подмены и связь с запросом, который действительно выдал оркестратор. Эти данные не выдаются за живой invoke роли или отказ реального провайдера. |

**FAIL:** драйвер сам проиграл переходы P1…P5; нет наблюдаемых решений проверяемой процедуры; загружена старая/неподтверждённая версия; доказаны только CLI/транспорт; либо реальная доставка заменена mock. Отдельные зелёные компонентные проверки сохраняются в отчёте, но AC пилота не закрывают.

| № | Задание и обязательный сценарий | Наблюдаемый результат |
|---|---|---|
| P1 | Приём нового готового запроса во время текущего задания; отдельно поступает сырая idea | Оба запроса сохранены однократно; готовый ждёт FIFO, idea остаётся triage; нет второго активного рабочего задания. |
| P2 | Задание с явной зависимостью от результата P1 | До подтверждения допуска не стартует предметная запись/дорогая роль; после P1 берётся следующим без сообщения Саши, источник и версия актуальны. |
| P3 | Блокер во время задания, позади уже готово P4; контролируемая пауза по лимиту | Очередь стоит на P3; причина/следующий шаг видны. После доказанного устранения блокера/возврата лимита продолжает P3; лимит и бюджет не сбрасываются, P4 не обгоняет. |
| P4 | Обрыв между записью канонного результата и фиксацией завершения | Результат принят по проверке без нового выполнения side effect; состояние, журнал и тестовый отчёт согласованы; фаза закрыта один раз. |
| P5 | Двойная доставка completion и пропуск первого основного completion в отдельном прогоне страховки | Повторный сигнал не дублирует действие/уведомление; страховка доставляет wake; после освобождения потока продолжение и завершение происходят без сообщения Саши. |

Пять заданий проходят подряд в заданном порядке. Дополнительные прогоны отказов не подменяют недостающий успешный P1…P5. При исправлении дефекта сохранить неудачный прогон и повторить затронутые проверки; не обнулять историю и не объявлять успех по закрытому процессу. Пилот подтверждает только реально испытанный контур; production runtime не отмечается PASS по фикстуре.

После штатного `restore-all-skills.sh` на `ORCH:shared-state` нужны rc/лог restore, перечень конечных исходных/resolved путей и SHA-256, затем новая проверка фактической загрузки по Б55.9 в конечном контексте default/применимого каталога. Evidence связывает конечную исполняемую процедуру с испытанным снимком: совпадение байтов процедуры и зависимых норм, состава/приоритета их загрузки; допустимое изменение путей зеркал показано явно. Успешный restore сам по себе этого не доказывает. Если конечная загрузка меняет проверенные правила или их приоритет, соответствующие пилотные сценарии повторяются на фактически загружаемой версии через существующий rework, до `GATE:done`. Проверка старой процедуры не принимается как проверка новой, статический diff не заменяет P1…P5.

Из существующих журналов и доступной телеметрии собрать базу до изменений и результаты после: число первичных invokes, повторов **по каждому из трёх регламентов**, duplicate events без нового invoke, ожидание по причинам, длительность задачи, input/output/cache tokens и стоимость с валютой/источником. `invoke_prepare` и `invoke_role` одного вызова не суммировать; денежные данные без привязки к сессии — «не измерено», не ноль. Проценты экономии указывать только при сопоставимой базе/объёме. Денежный предел выбирается после замера отдельным решением; суммы и автоблокировки здесь не изобретаются.

### Б55.12 Отложенные работы

Автоматический учёт бюджетов/стоимости и программный глобальный mutex остаются самостоятельными idea без автостарта. **[NEW-ENTITY, требует согласования Саши]**. Отдельно одобренный формат пакета реализует только Б56 внутри существующего пути; прежняя triage-формулировка не отменяет его согласование. Существующие protective counters сохраняются. Нового инструмента/сервиса/БД/очереди/канала/cron эта редакция не вводит.

### Б55.13 Проверки процесса

Пакетные проверки матрицы октября и сравнения ответов сохраняются в приложении как собственные deliverables исходного поезда. Следующие критерии сохраняют наблюдаемое поведение и проверяют реально загруженную процедуру.

| AC | Наблюдаемая проверка и evidence |
|---|---|
| AC-RP-03 | Проверяемая изменённая процедура оркестратора принимает поданные драйвером готовый запрос и idea во время текущего пилотного задания; оба сохранены один раз, idea не стартует. Evidence содержит state/journal/исходный origin, решения процедуры и привязку загрузки по Б55.11; драйвер только подаёт входы. |
| AC-RP-04 | Три готовых задания с разными временем/именами выбирает оркестратор по FIFO готовности; одинаковое время разрешается стабильно; явная инструкция приоритета имеет источник. Трасса решений загруженной версии процедуры и процессов не содержит второй исполняемой задачи/роли; заданный драйвером порядок не зачёт. Тест не требует глобального CLI-mutex. |
| AC-RP-05 | При блокере/лимите/межфазовом idle текущей задачи проверяемая процедура сама удерживает её, следующая не стартует; причина и условие продолжения видны. Негативный сценарий зависимости от очереди позади не вызывает скрытой перестановки или второго поезда. Удержание подтверждено решениями оркестратора, а не паузой драйвера. |
| AC-RP-06 | Проверяемая изменённая процедура после реального получения completion сверяет wrapper/артефакт, закрывает фазу и продолжает фазу/задачу без сообщения Саши. Отдельный пропуск completion вызывает **доставленный** wake существующей страховки и действие той же процедуры; неизменный doorbell не вызывает LLM/роль. Evidence оркестрации/транспорта/CLI/подмен разделены по Б55.11. |
| AC-RP-07 | Конечный загружаемый prompt/скилл разрешает 24/7 и не содержит действующего ночного окна; проверяемая процедура в сценарии квоты сама ждёт подтверждённого восстановления, затем возобновляет ту же фазу без смены аккаунта/backend, reset и серии пробных invoke. Подмена ответа о квоте явно обозначена; решение о возобновлении не делегировано драйверу. Недоступность такого возобновления даёт FAIL, не условный PASS. |
| AC-RP-08 | При обрыве после результата и двух одинаковых completion проверяемая процедура принимает результат однократно: одно выполнение side effect/один переход и согласованные state/journal/artifact; rc=0 без канона не закрывает фазу. Проверены G1/G2, свежесть пути/выжимки и загруженная версия; драйвер не выполняет reconciliation вместо оркестратора. |
| AC-RP-09 | Трасса «Технического восстановления»: один корректирующий повтор того же класса/фазы; второй сбой — диагноз/ожидание. Provider-fatal, живой wrapper, явная пауза и просьба «доделай» не дают reset/recover. Существующие guard-тесты остаются зелёными. |
| AC-RP-10 | Два последовательных REV с той же сутью замечания вызывают диагноз до третьей доработки; архив предыдущих вердиктов сохранён, канон REV один. Отдельный сценарий нового требования имеет источник, затронутые AC/IAC и минимальный rework без сброса других регламентов. |
| AC-RP-11 | `pipeline status` на фикстуре различает шесть видимых состояний Б55.6 и отмену; `idle+GATE:done done` не попадает в рабочую очередь. Новый конечный complete сохраняет root `done`. Архив выполненных доступен; в сводке выполненных только последние 48 часов. |
| AC-RP-12 | Ошибка обновления обзора показывает время последнего подтверждения и устаревание; мёртвый PID без результата не выдаётся за работу. Отчёт отдельно сохраняет runtime FAIL/no-entry/частичный объём, процессный done не меняет вердикт теста. |
| AC-RP-13 | Инвентарь загрузки Б55.9 подтверждён resolved paths/hash и trace/кодом загрузчика до и после. Для P1…P5 есть привязка реально загруженного снимка процедуры/инструкций к сессии и действиям; после restore подтверждена конечная загрузка и её соответствие испытанному снимку по Б55.11. Матрица владельцев и diff показывают одну активную запись каждого правила; USER/MEMORY не содержат конкурирующих процедур. Личные предпочтения и проверенная история сохранены. |
| AC-RP-14 | По каждому удалённому дублю/обходу есть backup, потребители и ссылка на замену; поиск и проверка конечного prompt не находят активной второй оркестрации, прямого запуска ролей в обход адаптера, битых ссылок и master-дубля. Codex-штат, Cursor-откат и предметные проверки сохранены. |
| AC-RP-15 | IAC содержит точный write-set/verify/depends/covers, подготовку загрузки до restore и передачу управления Б55.10; `HF:impl` и `HF:test` — разные вызовы. Подготовительный wrapper `HF:test` вышел до пилота, проверяющий вызов исполнителя начался после пилота; задача сохраняла поток, второй живой содержательной роли не было. Финальные план, тестовый отчёт и docs ссылаются на фактические файлы/хеши. После правок скиллов есть evidence штатного restore и конечной загрузки; backup конфигурации проверен до её изменения. |
| AC-RP-16 | Пять последовательных заданий P1…P5 имеют отдельные трассы всех шести сценариев Саши и привязку path/версия-снимок/SHA-256/контекст к реально загруженной изменённой процедуре. Она сама выбирает, удерживает, принимает completion/wake и возобновляет задания. Evidence реальной оркестрации, транспорта, CLI и управляемых результатов ролей разделены по Б55.11; исходник/параметры драйвера проверены на отсутствие подмены решений. Только сценарий драйвера, только CLI/транспорт или старая/неподтверждённая процедура дают FAIL. Реальная доставка continuation проверена отдельно от mock; production runtime не подменён фикстурой. При любом обязательном FAIL пакет не объявлен выполненным. |
| AC-RP-17 | Сохранены база и итог измерений по Б55.11; причины повторов разнесены по трём названиям; ожидания и доступные tokens/cost имеют источник, неизвестные отмечены. Денежный предел не придуман; новая автоматическая блокировка не внедрена. |
| AC-RP-19 | Baseline-diff подтверждает границы Б33, отсутствие restart/новых cron/изменений предметных контрактов эко-конфиг и чужих результатов. Сверка старой очереди сохраняет паузу B3/B4/w3/w4 и доказанные даты done; новая задача после пакета выбирается только по Б55.2. |

## Б56. Immutable packet и контекст

### Б56.2 Единица передачи и жизненный цикл

Один конверт относится к одному `(slug, phase)` и одному вызову роли. Формат — UTF-8 JSON `schema="devworkflow-packet/1.0"`. Канон сериализации для hash: `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` в UTF-8, без завершающего LF; `packet_id` = lowercase SHA-256 этого объекта **без поля `packet_id`**. Timestamp входит в объект; повторный успешный emit создаёт новый снимок, старый не перезаписывается. Это не счётчик повторов/бюджета.

После проверки `emit-prompt` сохраняет неизменяемый снимок `dev/<slug>/context/<packet_id>.json`, формирует `--out /tmp/task.md` и sidecar `/tmp/task.packet.json` (для любого `--out`: `Path(out).with_suffix(".packet.json")`). Sidecar имеет те же байты, что снимок; текст содержит `packet_id` и абсолютный путь снимка. Содержимое текста — детерминированный render конверта, без дополнительных требований, написанных вручную. Hash текста хранится в `context-used`, а не в самом хешируемом конверте. Снимки — evidence входов, не архив master и не самостоятельный SoT хода задачи.

Порядок публикации: собрать/проверить все входы → временные файлы → atomic replace снимка/sidecar/текста → повторно проверить согласованность → штатная фиксация успешного emit. Несколько файлов не объявляются одной атомарной транзакцией: сбой между шагами не оставляет пригодного успешного маркера. `invoke-role` допускает только целую проверенную пару с соответствующим успешным маркером; осиротевшие файлы не являются допуском. Существующий writer/lock используется коротко, без удержания на время LLM. Пакет не содержит тела master, чата целиком, секретов, `.env`, USER/MEMORY и raw provider-логов.

Вызов остаётся `emit-prompt --slug --phase --out` → rc=0 → `invoke-role --prompt-file --role --workspace`. Снимок конверта не передаётся модели вместо текста. Запрещены ручной Markdown, подстановка чужого sidecar и fallback на старый текст при ошибке нового формата.

### Б56.3 Поля конверта

Все перечисленные ключи required; дополнительные ключи на каждом уровне запрещены. JSON Schema draft 2020-12 лежит в `Registries/pipeline/schemas/devworkflow-packet-1.0.schema.json` **после `HF:impl`**, валидатор исполняет также семантические проверки Б56.6. Версия схемы пакета независима от версии ТЗ и `devworkflow-state/1.0`.

| Поле | JSON-тип / значение | Смысл и источник |
|---|---|---|
| `schema` | string, const `devworkflow-packet/1.0` | Точная версия, без угадывания по расширению. |
| `packet_id` | string, 64 lowercase hex | Hash по Б56.2; проверяется пересчётом. |
| `emitted_at` | string, ISO-8601 с timezone | Время фактической сборки, не время начала фазы. |
| `task` | object `{slug,title,case,phase,role}`; все string | Из state; case/phase/role проверяются по recipe/G6, title не заменяет постановку. |
| `sources` | object `{digest,canon,glossary,context_rules,master,extract}` | Четыре первых — FileRef. `context_rules` = `references/context.md`; master/extract — структуры ниже. |
| `sources.master` | object `{status,ref,version,reason}` | status=`present`/`planned`/`absent`; при present ref=FileRef, version=string semver, reason=null; при planned ref=PlannedRef, version=null, reason=`new-tool`; при absent ref/version=null, reason из закрытого перечня ниже. Все четыре ключа required в каждой ветке. |
| `sources.extract` | object `{status,key,of_tz_version,parts,reason}` | status=`present` или `absent`; key/version — string либо null; parts=array FileRef в порядке частей; reason=null при present, иначе закрытая причина ниже. |
| `inline` | object `{digest,canon,context_rules,extract_parts}` | Первые три — полные string-тексты соответствующих файлов; extract_parts=array string, в том же порядке/числе, что parts. Их UTF-8 байты обязаны совпадать с hash ссылок. |
| `handoff` | object `{kind,from_phase,inputs,request}` | kind=`initial`/`forward`/`rework`; from_phase=string либо null только у initial; inputs=array InputRef; request=FileRef либо null вне rework. |
| `must_read` | непустой array ReadRef | Разрешённые обязательные чтения этой фазы, в том числе полные выбранные секции; Б12 применяется целиком. |
| `outputs` | непустой array OutputRef | Ожидаемый канонный результат; не заявление о существовании/успехе. |
| `boundaries` | object `{write_scope,prohibitions}` | Оба array string; первый — разрешённые абсолютные пути/каталоги из утверждённого задания/плана, второй — полные относящиеся запреты. Не извлекать новый write-set по мнению сборщика. |
| `doctrine` | string, const `выжимка ≠ SoT; при расхождении — открыть master` | Не теряется ни в JSON, ни в render. |

**Единая политика extract (кейс + фаза + история слага).** Проверяется на каждой передаче initial/forward/rework, без отдельного запрета по префиксу HF. Применяется следующий порядок:

1. На самой `TZ:compress`/`HF:compress` extract — выход. Разрешено `status=absent`, `reason=being-produced`, `key/of_tz_version=null`, `parts=[]`, `inline.extract_parts=[]`, в том числе при stale/повреждённом прежнем extract. Старый индекс не используется как актуальный вход, история его производства не стирается. Master должен быть present, оба промпта компрессора обязательны. Следующая потребляющая фаза требует успешно записанный и проверенный extract по Б60.3.2; исключение производства на неё не переносится.
2. Вне производства, если extract когда-либо производился или есть следы его существования, обязателен `status=present` и весь комплект актуальных файлов/частей и метаданных Б10/Б56.3/Б60: `extract_key`, `extract_sha256`, `extract_of_tz_version`, `extract_chars`, согласованный путь. В конверте `key` равен проверенному `extract_key`, `of_tz_version` — текущей версии master, reason=null. Следы — не только текущий файл: проверяются части, ненулевые метаданные state, успешный compress в phases/journal и ранее принятые снимки пакета. Канонное значение пути `extract.md` при остальных null само по себе следом производства не является. Удаление файла/части/метаданных, изменение recipe или сужение LIGHT не превращает ранее сжатый слаг в никогда не сжатый. Drift ключа/version/mtime/hash, неполные метаданные и противоречивая история дают отказ; нужен штатный compress, а не absent или чужая выжимка.
3. Только если индекс **никогда не производился**, файлов/частей/следов нет и история это подтверждает, разрешён `status=absent` с `key/of_tz_version=null`, `parts=[]`, `inline.extract_parts=[]`. Дополнительно все собственные входы и чтения фазы по Б56.5 должны быть готовы, а среди её обязательных предшественников по канону/фактическому recipe не должно быть незавершённого compress. Если compress в выбранной законной ветке отсутствует, reason=`not-applicable`; отсутствие допустимо на **всех** её передачах и возвратах, включая TZ/REV/HF, MIG и DEC. Если compress предусмотрен только позже текущей фазы, reason=`not-yet-compressed`; это разрешает ранний вход и rework до него, но не переход за него. Optional compress, уже включённый в recipe, обязателен для зависящих от него фаз по Б19. Обязательный compress по кейсу/ветке (в том числе по результату SK:preflight) нельзя объявить optional или убрать ради пакета; неверный recipe отвергается G4/G5. При неполной истории, не позволяющей доказать отсутствие производства, — диагностируемый отказ.

Таким образом, DEV/SKILL-DEV без optional compress, BUGFIX, CHANGE-LIGHT/BUGFIX-LIGHT, MIGRATION и DECOMM без compress проходят свои HF/MIG/DEC-фазы с собственными документами; SKILL-CHANGE следует подтверждённой ветке и preflight. CHANGE с обязательным compress и любой ранее сжатый слаг не получают этого исключения. Никогда не произведённый extract не становится stale от изменения master; каждый новый пакет всё равно сверяет реальные реквизиты master. Б56 не добавляет compress в канонический маршрут ради отсутствующего индекса. Межслаговый reuse запрещён во всех ветках.

**Master: три различимых состояния.** `present` обязателен на TZ/REV:tz, HF/REV:plan, MIG и compress по Б56.5; единственное исключение начальной записи — `planned` для отсутствующего будущего master **нового инструмента** в `TZ:patch` кейса DEV (SKILL-DEV — только если утверждённая постановка действительно создаёт такой master). Это не способ описать исследование, диагноз, снятие, существующий инструмент или произвольное отсутствие данных. На REV:tz и после записи/финализации master planned уже недопустим.

`absent` означает отсутствие предметного master, а не отсутствующий файл по известному пути. Допустим только при пустом `tz_path`, отсутствии прежней привязки present/planned в истории и наличии достаточной постановки/исходных документов. Закрытые причины и область:

| reason | Кейс / фазы | Достаточные собственные источники |
|---|---|---|
| `research-without-master` | RESEARCH: `RS:collect`, `RS:analyze`, `REV:report`, включая возвраты | Принятая рамка, вопросы/границы/AC исследования; предшествующие RS-артефакты по Б56.5. Исследование не пишет и не судит норму предметного master. |
| `diagnosis-without-contract` | BUGFIX/BUGFIX-LIGHT: `BUG:diagnose`, включая возврат до привязки master | Факты/логи/код и постановка, явно не требующая оценки контракта ТЗ. На последующей `TZ:patch` master уже нужен; диагноз не заменяет его. |
| `decommission-without-master` | DECOMM и подтверждённая DECOMM-ветка SKILL-CHANGE: `DEC:inventory`, `DEC:exec`, включая возвраты | Подтверждённый объём/границы снятия; для exec дополнительно инвентарь, never-auto `GATE:go` и backup. Предметные нормы master не затрагиваются. |

При absent отсутствующие version/mtime/hash не выдумываются: в конверте ref/version=null, в старых реквизитах контекста — null/пустое значение с явными status/reason; проверки свежести **неприменимы**, это не PASS свежести. `must_read` остаётся непустым и содержит реальные FileRef постановки и обязательных собственных входов; ссылка на отсутствующий master не создаётся. При planned путь является ожидаемым output, а не ReadRef; читаются реальные постановка/доступные нормы. Доктрина сохраняется дословно; render дополнительно сообщает статус/причину и применимые SoT-документы. Для present полностью действует Б12, в том числе полное чтение по NEW-ENTITY/конфликту. Если при работе без master выявлена необходимость писать/судить его контракт либо применимый триггер обязательного чтения, роль фиксирует нехватку в канонном результате и не формулирует эту норму до нового пакета с явной привязкой. Существующая/прежняя привязка, пропавший файл и недостающий обязательный master никогда не маскируются absent.

**Первичная привязка без смены маршрута.** Новый опциональный аргумент **существующего** `emit-prompt --master-tz <ABS>` применим к любой фазе-получателю из Б56.5 при ещё пустой привязке: в том числе initial `BUG:diagnose`, `RS:collect`, `DEC:inventory` и поздней `TZ:patch` после законного absent. Путь должен быть явно назван в принятой постановке, переданной проверенным InputRef; title, сходство имён и произвольный master не основание. Если фаза требует master и `tz_path` пуст, аргумент обязателен. Для законного absent аргумент не нужен, null-привязка сохраняется. Никакого нового аргумента `init`, ручной записи state или отдельной operator-команды не требуется.

Для существующего master обязательны реальные version/mtime/hash и FileRef. Отсутствующий путь допускает только узкий planned выше, иначе отказ. При уже установленном `tz_path` аргумент может лишь подтвердить **тот же** нормализованный абсолютный путь и resolved target; заменить привязку или обойти drift им нельзя. Привязку `tz_path/tz_version/tz_mtime` фиксирует штатный writer только при успешном emit вместе с его контекстом; до проверки/при отказе state не меняется. После разрешённой записи planned → present выполняется следующим emit по тому же пути с фактическими реквизитами, без повторного выбора master. Изменение master разрешённой ролью принимается по Б56.6 п.5. Неполная постановка/путь/входы вызывают диагностируемый отказ. Fallback на DevWorkflow или чужой master, фиктивный planned и поиск «похожего» ТЗ запрещены.

### Б56.4 Типы ссылок и содержательный контракт

`FileRef` = object с required `path` (string, абсолютный путь), `resolved_path` (string, реальный абсолютный путь после symlink), `sha256` (64 lowercase hex), `size_bytes` (integer ≥0), `mtime_ns` (integer ≥0). Чтение строго UTF-8 для текстов, без `errors=replace`; hash считается по исходным байтам. Изменение symlink target проверяется отдельно от hash. Для нетекстовых changed_files outputs действуют байтовый FileRef и полный snapshot ниже; строгий текстовый контракт сохраняется для текстовых потребителей. `PlannedRef` = object только с `path`; путь назначения абсолютный, ещё отсутствует, не выдаётся за прочитанный источник.

`InputRef` = object `{phase,ref,purpose}`: phase — каноническая фаза производителя или null для исходного брифа и его исходного подтверждения по Б60.3.1; ref=FileRef; purpose=непустая string с ролью входа. Входами являются **проверенные канонные файлы**, а не stdout и не «последний файл по mtime». Явное отсутствие ненужного входа — пустой список; отсутствие обязательного входа — отказ. При rework `request` указывает сохранённую ревизию/датированную постановку: объект, нарушенный контракт, суть дефекта или новые требования и затронутые AC. `from_phase` отражает источник текущей передачи; порядковый номер recipe не подменяет rework.

`ReadRef` = object `{ref,scope,sections,reason}`: ref=FileRef; scope=`full`/`sections`; sections=array string (пуст только при full), reason=непустая string. Каждый section — точный существующий заголовок с родительской цепочкой; повтор заголовка без цепочки недопустим. Читается вся секция до следующего равного/старшего заголовка. Frontmatter задаётся отдельным значением `frontmatter`. История не является штатным обязательным чтением. «Текущий пакет» определяется привязкой задания к секции master, не обязательно последним номером чужой доработки. Если выбрать секцию однозначно нельзя — отказ с запросом адресного контекста. Исключения полного чтения Б12 имеют приоритет над sections. Пакет передаёт также полный context_rules, чтобы таблица не исчезла при render.

`OutputRef` = object `{kind,path,required}`: kind=`canonical`/`master`/`inventory`/`changed_files`/`verification`; path=абсолютный путь файла или каталога для changed_files; required=bool. Обязательный канонный basename берётся из существующей таблицы/рецепта; `_fix_plan_YYYYMMDD.md` материализуется конкретной датой перед invoke. Для HF:impl перечисляется write-set из плана и его git-proof; для HF:test — существующий путь отчёта из IAC и сами IAC.verify. «verification» не запускает команду из JSON: исполнитель читает согласованный план. Optional outputs не заменяют required, новый JSON-отчёт от роли не требуется.

### Байтовый snapshot outputs

FileRef hash/size считаются по исходным bytes; текстовые packet/render/inline/canonical/extract читаются strict UTF-8, без errors=replace/ignore или binary fallback. Нетекстовый changed_files file/directory сохраняется как непрозрачные bytes независимо от расширения. То же содержимое, используемое текстовым input, отдельно проходит strict UTF-8.

Форма snapshot: dict[output_path] → FileRef | dict[child_path] → FileRef | null. Детерминированный полный обход, только прежнее исключение .git, без молчаливого пропуска fixture/cache/binary. Unreadable/non-regular/symlink/escape/смена target — отказ до небезопасного чтения. Проверяется стабильность состава и FileRef при add/delete/rename/замене/mtime/изменении bytes во время обхода и непосредственно перед commit/readback/G2. Пустой required каталог не результат; freshness/before=null исходного prepare не переснимаются. Receipt не даёт no-op изменённому дереву. Общая crash-атомарность/защита от произвольного конкурентного writer не обещается.

### Б56.5 Входы фаз и результаты между ними

Таблица — минимум поверх Б17–Б27; условные входы требуются тогда, когда соответствующая фаза присутствует в recipe. До вызова нельзя придумывать отсутствующий артефакт. План и IAC передаются ссылкой на полный файл, без копии таблицы в JSON. **На каждой строке**, в том числе rework, применяется единая политика extract Б56.3: актуальный present обязателен после производства/обязательного предшествующего compress; никогда не производившийся индекс допустимо отсутствует при законном маршруте без compress либо до будущего compress. Отсутствие extract не заменяет ни одного документа в таблице.

| Фаза-получатель | Обязательные входы / чтения | Допустимый master | Ожидаемый результат |
|---|---|---|---|
| `TZ:patch` initial | Принятая постановка с origin/датой в файле слага; MUST-read Б12 для present; для planned — реальные постановка/нормы и инвентарь | present; planned только нового инструмента по Б56.3 | Master и `TZ-patch.md`. |
| `REV:tz` | Master, `TZ-patch.md`, постановка; MUST-read Б12 | present | `REV-tz.md`; канон блока Вердикт сохраняется. |
| `TZ:patch` rework | Текущие master/канон и сохранённый REQUEST-CHANGES либо новая постановка; причины повтора Б55.5; MUST-read Б12 | present | Обновлённые master/`TZ-patch.md`; не новый recipe. |
| `TZ:finalize` | Master/patch, `REV-tz.md=APPROVE` либо доказанный штатный waive/табличный LIGHT; MUST-read Б12 | present | Master, inventory и `TZ-finalize.md` по действующему рецепту. |
| `HF:plan` | Master AC/запреты/контракты с диска, `AC-list.md`; BUGFIX — также утверждённый диагноз | present | `HF-plan.md` с IAC. |
| `REV:plan` | Полный `HF-plan.md`/IAC, запреты master | present | `REV-plan.md`. |
| `HF:plan` rework | Те же входы + архивированный REQUEST-CHANGES/новая постановка | present | Тот же `HF-plan.md` и IAC. |
| `HF:impl` | Утверждённый план/IAC, REV и backup evidence при наличии этих фаз в recipe; LIGHT — утверждённый `_fix_plan` с IAC (BUGFIX-LIGHT) либо секция IAC master (CHANGE-LIGHT); применимые запреты master | present | Свой changed_files и существующее impl evidence; G3. |
| `HF:test` | IAC.verify/план (для LIGHT — тот же `_fix_plan`/секция IAC), impl evidence/changed_files и git-proof | present | Проверки и канон отчёта из IAC, честные FAIL/no-entry. |
| `BUG:diagnose` | Принятая постановка, исходные факты/логи/код; master при затронутом контракте | present; absent только `diagnosis-without-contract` | `_fix_plan_YYYYMMDD.md`. |
| `RS:collect` / `RS:analyze` / `REV:report` | Рамка/AC исследования; для analyze — `RS-collect.md`, для REV — `RS-analyze.md`; предметный master и его применимые нормы, если исследование судит этот контракт | present; absent только `research-without-master` | Соответствующие канонные RS/REV файлы. |
| `MIG:plan` / `MIG:block-k` | Freeze master/инвентарь; для блока — MIG-план и доказанные предыдущие block-accept | present | `MIG-plan.md` либо артефакт блока по плану. |
| `DEC:inventory` / `DEC:exec` | Подтверждённый объём/границы; для exec — инвентарь, `GATE:go`, backup; применимые нормы предметного master при их затрагивании | present; absent только `decommission-without-master` | Канонный инвентарь либо evidence исполнения существующего рецепта. |
| `TZ:compress` / `HF:compress` | Полные master/оба промпта; полный acceptance с inventory — системный InputRef, полная обратимая ModelView — ReadRef модели по Б60.3.3; при наличии принятого error-digest — полный второй содержательный источник по Б60.3.4. Первично — подтверждённый brief/basis Б60.3.1; далее — pin/approved transition. Extract absent/being-produced по Б56.3 | present | Python extract/части/manifest и metadata после независимого completion Б60. |

Покрытие кейсов проверяется **трассами до последних ролей**, а не успешностью одного начального пакета:

| Кейс / ветка | Ветка без extract, если никогда не производился | Master / достаточные документы |
|---|---|---|
| DEV | Без optional compress: TZ:patch → REV:tz → rework TZ:patch при REQUEST-CHANGES → REV:tz → TZ:finalize → HF:plan → REV:plan → HF:impl → HF:test | Начальный present/planned, затем present; постановка, master/AC-list, план/IAC, ревизии и impl evidence по фазам. |
| CHANGE | Нет исключения после обязательного TZ:compress; present с проверенными метаданными и пересжатием при drift | present, полный маршрут Б18. |
| CHANGE-LIGHT | Все оставшиеся TZ/HF-роли без compress, включая HF:impl/test; после законного set-case уже произведённый extract всё равно проверяется | present, секция IAC master и impl evidence, без искусственного HF-plan/backup. |
| BUGFIX | BUG:diagnose → TZ:patch/REV:tz/rework → TZ:finalize → HF:plan/REV:plan → HF:impl/test, без compress Б21 | Диагноз present/absent по контракту; начиная с TZ:patch — present, диагноз/AC-list/план/IAC. |
| BUGFIX-LIGHT | Сохраняются диагноз и diagnose-review; далее TZ-роли → HF:impl/test без compress | Начиная с TZ:patch — present; утверждённый `_fix_plan` с IAC и impl evidence. |
| RESEARCH | RS:collect → RS:analyze → REV:report при наличии, включая rework | present либо законный absent на всём маршруте; рамка/AC и RS-артефакты. Создание master не требуется. |
| MIGRATION | TZ-роли → MIG:plan → каждый MIG:block-k и его rework без compress | present freeze master, инвентарь, MIG-план, предыдущие block-accept. |
| DECOMM | DEC:inventory → DEC:exec и возвраты без compress | present либо законный absent на обеих ролях; подтверждённый объём, инвентарь, GATE:go и backup. |
| SKILL-DEV | Как DEV без optional compress, если preflight не предписывает compress | Master и документы как DEV; restore остаётся обязательным в хвосте. |
| SKILL-CHANGE | Только законная ветка: малая CHANGE/LIGHT без compress либо DECOMM; ветка с обязательным compress исключения не имеет | Ветка CHANGE — present и IAC; DECOMM — как строка DECOMM. Результат SK:preflight и подтверждённая ветка обязательны. |

Стрелки в таблице показывают передачи **между ролями**, а не сокращённый recipe: все промежуточные гейты/backup/хвосты Б18–Б27 исполняются в своих местах, never-auto не ослабляются. Rework во всех строках добавляет проверенную архивную причину Б55.5 и сохраняет историю слага. Отсутствие compress в текущем recipe не отменяет проверку ранее произведённого extract; включённый optional/обязательный compress проверяется отдельно. Первичная привязка через `--master-tz` доступна и для стартов не с TZ:patch, и при переходе от допустимого absent к фазе с обязательным master.

Для sirene-фаз и auto-гейтов новый формат не создаёт invoke. Их факты/evidence могут быть входами следующей роли; Б17 остаётся процедурой без LLM. На `HF:plan` эта таблица сопоставляется с **реальными** канонами/проверками кода всех десяти кейсов; при отсутствии фиксированного имени оно задаётся утверждённым планом до emit, не выбирается исполнителем произвольно.

### Б56.6 Проверки и отказы

1. На emit: известная схема/типы/required/no-extra; slug/phase совпадают с заданием, phase есть в recipe, role соответствует G6. Сначала определяются применимость master/extract по Б56.3/56.5 и история производства; затем проверяются все FileRef: пути существуют и читаемы, bytes/hash/mtime/resolved target согласованы. При present master version/mtime и extract_key/все части соответствуют G1; при законном absent или planned не требуют реквизитов несуществующего файла, проверяют закрытую причину, допустимый кейс/фазу, историю и обязательные собственные источники/MUST-read. Неизвестная причина, absent вопреки прежней привязке/истории либо пропущенному обязательному compress, planned вне создания нового инструмента — fail. Для inline — точное совпадение байтов с FileRef; обрезка/замена символов запрещены. Digest не объявляется свежей runtime-аттестацией по одному наличию файла.
2. Проверяются матрица обязательных входов/чтений/выходов, `handoff.kind`, архивированная причина rework, явное основание границ. Пути слага после resolve остаются внутри его каталога; внешние источники разрешены только утверждёнными путями из постановки/плана/YAML. Подмена соседнего слага, неоднозначная часть extract или несуществующий заголовок — fail, без автоматического поиска «похожего» файла.
3. Перед spawn invoke заново проверяет снимок/sidecar, packet_id, детерминированный render и hash prompt; текущие slug/phase/G6, источники и существующие G1/G3/occupancy. Все проверки — **до invoke_prepare и платного backend**. Изменившийся source требует нового emit; старый пакет не разрешён по одному прежнему context_used=true. Backend/model/effort берутся из YAML/resolver, не из конверта.
4. Успешный `context-used:` сохраняет прежние поля и добавляет `packet_schema`, `packet_id`, `packet_path`, `prompt_sha256`, а также `master_status`/`master_reason` и `extract_status`/`extract_reason` из проверенного конверта. Реквизиты отсутствующего источника остаются null/пустыми; G1/G2 принимают их только вместе с допустимой веткой этого конкретного пакета, а не по одному пустому полю. При invoke_prepare штатный writer сохраняет первые четыре поля внутри `phases.<PHASE>.context_packet`; это аддитив optional object схемы state/1.0, не новый root и не state bump. Каждый новый успешный emit дописывает свой маркер; дедуп только по тому же packet_id, не по одному имени фазы. G2 на новых вызовах требует совпадения **slug + phase + packet_id** успешного emit и принятого invoke. Маркер другой фазы/слага или исторический context_used сам по себе не проходит.
5. Роль вправе изменить предназначенные для записи master/план/канон. Поэтому complete сверяет входной принятый снимок и output evidence относительно него, а не требует совпадения нового master с его **входным** hash. Изменения вне разрешённого write-set не становятся допустимыми благодаря этому исключению. Следующая фаза получает новый снимок; прежний пакет не редактируется. Исторические адресные исключения Б58/Б59 запрещены к применению; произвольный source drift не разрешён. G2 не означает автоматического APPROVE/complete.
6. Неверный ввод — exit 2 для CLI-синтаксиса, exit 1 для схемы/контекста; диагностика содержит поле/путь и причину, без секретов. Ни state/phase, ни успешный context-used, ни бюджет вызовов не меняются при отказе **до** публикации/prepare. Сбой фиксации после публикации оставляет недопущенные файлы, но не успешный emit. Неизвестная schema, повреждённый packet или drift не становятся provider_fatal/новым recover-классом; одинаковый ошибочный вызов не повторять.

Hash доказывает целостность/совпадение, не защищает от злонамеренного локального writer и не удостоверяет понимание LLM. Содержательную полноту проверяют IAC/REV по master. Новые учётчики повторов и глобальные lock-лимитаторы здесь не добавляются.

#### Согласованность recipe и handoff-contract до запуска роли

Дополнение по распоряжению Саши в актуальном брифе. Единственный владелец проверки — существующий pipeline_context.py; recipe-add, emit и invoke используют одну проверку пофазовой проекции контракта, без второго реестра разрешений. Основание — действующее утверждённое задание/план, выбранное установленным порядком: HF-plan.md с handoff-contract имеет приоритет над brief.md. Неполный выбранный контракт не дополняется из прежнего brief. Каноническое имя результата берётся из существующей таблицы G6/канонных артефактов и Б56.5; путь результата из IAC и конкретная дата диагноза определяются по Б56.4. Новый маршрут, CLI, схема пакета или state не вводятся.

До публикации packet/sidecar/Markdown и успешного context-used emit проверяет текущую роль-фазу фактического recipe: для неё явно заданы inputs, outputs и write_scope; пустой inputs допустим только при отсутствии обязательных входов по Б56.5. Отсутствующий ключ не равен пустому списку. Обязательный канон присутствует среди outputs с required=true; все остальные обязательные результаты таблицы/плана также объявлены. Каждый объявленный output, включая optional, должен помещаться в разрешённый scope по нормализованному абсолютному пути и resolved target; каталог разрешает только себя и потомков по компонентам пути, не строковому префиксу. Для будущего файла проверяются существующие родители, без требования заранее создать output; symlink/escape/non-regular отказываются по Б56.4. Полнота входов и фактические FileRef текущей фазы проверяются по Б56.5/56.6. Нельзя обойти отказ, исключив канон из outputs, сделав его optional, выбрав чужое имя либо расширив scope сборщиком. Широкий разрешённый каталог сохраняет границу Б0.3.

Перед фиксацией recipe-add та же проверка применяется к предлагаемому recipe и всем добавляемым роль-фазам: их декларации inputs/outputs/write_scope и канон должны быть согласованы заранее. Проверка структурная: будущий вход может ещё не существовать, но его производитель/путь/назначение уже объявлены; фактический FileRef проверит emit этой фазы. Зависимость должна соответствовать Б56.5 и допустимому маршруту, без цикла и ссылки на результат более поздней фазы. Гейты и фазы оркестратора проверяются по своему рецепту и не получают фиктивного LLM-контракта. Для отказа recipe/state/journal остаются прежними; повторное добавление уже имеющейся фазы остаётся штатным no-op и не заменяет проверку на emit. Незавершённые будущие планы и файлы не требуются для emit иной текущей фазы; старые завершённые фазы не переаттестуются. После set-case и на rework текущая роль-фаза проходит тот же допуск.

Проверка invoke до invoke_prepare повторно сопоставляет текущие recipe/G6 и эффективную проекцию inputs/outputs/write_scope/prohibitions выбранного контракта с неизменяемым packet; изменение относящихся к фазе разрешений или входов после emit требует нового emit, не правки принятого packet. Перед публикацией emit и записью recipe-add штатный writer под существующим коротким lock повторно сверяет захваченные state и источник контракта; drift даёт отказ. Проверка результата после выхода wrapper сохраняется: ранний допуск не доказывает фактические bytes/freshness результата и не ослабляет G2/G3 или occupancy.

Несогласованный контракт — context exit 1 с фазой, источником контракта, полем, ожидаемым каноном/путём и конкретной нехваткой разрешения/входа; без секретов. До публикации отказ оставляет packet/sidecar/Markdown, state/journal, успешный context-used, prepare/turn_count/result/receipt без изменений, backend не вызывается. Это дефект допуска, исправляемый владельцем задания/контракта в уже разрешённых границах; не новый Q-n, operator hold, recover или повтор роли на тех же входах. Расширение согласованных прав требует обычного согласования задания, а существующие разрешения не запрашиваются повторно.

Вариант реализации: общая чистая проверка в pipeline_context.py, вызов из существующего cmd_recipe_add до persist, из emit до публикации и из invoke до prepare; прежние post-invoke guards остаются. HF:plan закрепляет точные callers, типы и изолированные fixtures, REV:plan проверяет покрытие AC-PKT-04/06. Чтение контракта и сравнение путей выполняет Python: дополнительные обязательные чтения master/истории, повтор таблицы контракта в prompt и LLM-вызов для preflight не нужны. Стоимость — локальная валидация проекции и повторная сверка источника; экономия — отсутствие оплаченного запуска на детерминированно непригодном допуске. Размер добавления измеряется при согласовании документа; фиксированная экономия токенов или runtime PASS до внедрения не объявляются.

### Б56.7 Совместимость, включение и откат

Включение выполняется после зелёного изолированного `HF:test`, адресно на `ORCH:shared-state` обновлением единственного сборщика/проверяющего пути и `references/context.md`; новый YAML-флаг/второй dispatcher не нужен. Для текущего CHANGE действует переход R0→R1 по Б61.4: лабораторная проверка R1 предшествует live-включению, оба собственных вызова `HF:test` принимает R0, а live install допустим только после окончательного PASS и `HF:docs-handoff`. PREPARED/partial не является зелёным окончательным тестом. В одном выпуске обновляются emit/check/invoke/G2 и потребители текста. Выполняющийся старый wrapper принимается по своему сохранённому контексту, его не kill/re-emit. Адресное own legacy completion Б59 не применяется. Общий путь не допускает backfill. Первый **новый** invoke после включения требует Б56. Старые завершённые фазы и история `context-used` не переписываются и не объявляются невалидными задним числом; несовершённая старая фаза получает новый emit перед следующим invoke. Исторический результат, требующий reconciliation, не перезапускается ради изготовления пакета: принимается по Б13/Б55 с явным legacy evidence.

Пакеты неизвестной версии не «мигрируются» заменой поля schema. После изменения входов/путей/мажорной схемы конверт пересобирается штатным emit из SoT; архивный снимок остаётся прежним. Для последующей несовместимой версии требуется отдельная норма и уведомление локальных потребителей emit/check/invoke/G2/skills. Автоматической миграции state и массового backfill нет.

Handoff Б13.4 переносит snapshot evidence в составе слага, но абсолютные пути **архивного** пакета не переписывает. На приёме пути state разрешаются штатно из YAML, G1 проверяется, затем новый emit создаёт новый packet_id по местным путям. Старый `/tmp/task.md`/sidecar не возят и не исполняют.

Откат — проверенный snapshot кода/скилла до включения; только после выхода текущих wrapper, без рестарта Gateway, reset phase/recover_counts и повторного исполнения side effect. Форматы не смешиваются внутри принятого вызова. История нового пакета остаётся evidence, старый релиз её не объявляет пригодным legacy prompt. При невозможности проверить незавершённый результат — явное ожидание/диагноз; fallback на ручной prompt запрещён.

### Б56.8 Проверка и выпуск

HF-plan.md/IAC заранее сопоставляют матрицу входов со всеми десятью реальными рецептами, первичную привязку TZ/BUG/RS/DEC, законные absent, set-case history, rework и changed-master-after-role. Изолированные roots/stub проверяют протокол без живой очереди и платных негативов. Совместимость текущего выпуска дополнительно доказывается тремя трассами R0/R1/transition по Б61.4 до live-включения. Emit/check/invoke/G2 обновляются одним согласованным выпуском; после HF:test — адресный ORCH и проверка фактически загруженных paths/hash/restore/installed smoke. Исторический общий green не доказывает нужную дугу.

### Б56.9 Приёмка пакета

| AC | Наблюдаемая проверка / evidence |
|---|---|
| AC-PKT-01 | Master/REV подтверждают immutable packet Б56 внутри существующего пути, границы согласования NEW-ENTITY и reuse по Б55.3. Автоматический учёт бюджетов/стоимости и программный глобальный mutex остаются отложенными по Б55.12; они не внедрены этим пакетом. |
| AC-PKT-02 | Schema и semantic validator принимают валидный конверт и отвергают missing/unknown keys, неверные типы/enum/schema/hash, невалидный UTF-8. Для master проверены все present/planned/absent с required status/ref/version/reason, для extract — present и три закрытые причины absent Б56.3; невозможные сочетания отвергнуты. Валидны full/sections MUST-read для present и реальные обязательные чтения при planned/absent без фиктивного ReadRef. Доктрина и явные status/reason сохранены в render/маркере. |
| AC-PKT-03 | Реальный emit создаёт snapshot/sidecar/Markdown с одним packet_id; render воспроизводится byte-exact, digest/canon/context_rules и каждая часть extract полны; master body отсутствует. |
| AC-PKT-04 | На изолированном CLI проверены отсутствие обязательного входа, подмена slug/phase/G6, canonical filename и symlink target, устаревшие master version/mtime/hash и extract key/part hash; backend не вызван, state/успешный маркер неизменны. Допуск контракта Б56.6 проверен на RESEARCH с добавляемым REV:report: отсутствующий ключ inputs/outputs/write_scope, пропущенный или optional канон, output вне scope, совпадение только строкового префикса и escape через родителя дают отказ до публикации и backend; recipe-add также отказывает до записи предлагаемого recipe. После исправления разрешённого контракта recipe-add и emit проходят, будущий ещё не созданный RS-analyze.md допустим при добавлении REV:report, но обязателен как проверенный input на его emit. Законный пустой inputs принимается, будущий output не требуется создавать заранее. Покрыты HF:compress, последовательный MIG:block-k с его гейтом, set-case и rework; guard не расширяет scope и не добавляет роли/фазы. На ранних отказах packet/sidecar/Markdown, state/journal, context-used, prepare/turn_count/result/receipt неизменны; provider sends отсутствуют. |
| AC-PKT-05 | На изолированных CLI-фикстурах покрыты все 10 кейсов и их передачи/возвраты Б56.5. Положительные трассы без добавления compress/чужого extract: BUGFIX до HF:plan/impl/test; BUGFIX-LIGHT и CHANGE-LIGHT до HF:impl/test с собственным IAC; DEV/SKILL-DEV без optional compress до HF:plan/impl/test, включая REV:tz → TZ:patch rework до первого compress; MIG:plan → MIG:block-k; DEC:inventory → DEC:exec. RESEARCH без master проходит RS:collect → RS:analyze → REV:report при наличии; DEC без master проходит inventory/exec при законном объёме/гейте/backup; начальный BUG:diagnose без контракта проходит с absent, затем TZ:patch требует явный master. CHANGE/полная SKILL-CHANGE с обязательным compress, ветки с включённым optional compress и производство extract проверены отдельно. Sirene/auto-gates не получили invoke, промежуточные обязательные фазы не пропущены. |
| AC-PKT-06 | G2 отвергает маркер другого slug/phase/id и ручную правку Markdown/sidecar; перед prepare привязка совпадает с фактически переданным prompt. Проверен отказ после изменения source между emit и invoke. Изменение относящейся к фазе проекции выбранного handoff-contract или удаление фазы из recipe после emit отказывает до prepare/backend, packet не редактируется. Drift state/источника контракта до публикации emit либо записи recipe-add также отказывает без частичного успеха. Неполный HF-plan.md с контрактом не получает fallback на brief.md; иной будущий отсутствующий файл и завершённая история не требуют повторного invoke. Положительная трасса показывает одну успешную отправку после корректного emit, прежний post-invoke контроль outputs/freshness сохранён, размер обязательного контекста роли не вырос копией контракта/истории. |
| AC-PKT-07 | Положительные CLI-пакеты: первая TZ:patch с явным master present/законным planned; initial BUG:diagnose с --master-tz существующего предметного ТЗ; RESEARCH и DEC без предметного master, BUG:diagnose без контракта; переход от absent к TZ:patch с явной привязкой; маршруты без extract по AC-PKT-05 и успешное производство/пересжатие. Отрицательные: master отсутствует там, где обязателен (в т.ч. BUG при оценке контракта и последующая TZ:patch без пути); подмена уже установленной привязки/resolved target; planned для существующего инструмента/RS/DEC/после записи master; чужой fallback/чужой extract; удалённые extract/часть/метаданные ранее сжатого слага, в т.ч. после set-case LIGHT; drift version/mtime/key/hash; незавершённый обязательный предшествующий compress (в т.ч. включённый optional) и незаконное удаление обязательного compress из recipe. Законный absent не является одним из этих отказов. На отказах backend не вызван, state/успешный context-used не изменены; успешная первичная привязка записана только штатным emit writer. |
| AC-PKT-08 | Роль изменяет разрешённый master/план, complete принимает проверенный результат по входному snapshot; следующая фаза получает новый id/hash. Неизменённый или неканонный результат не проходит старую проверку по одному packet_id/rc=0. |
| AC-PKT-09 | Сбой на каждом шаге публикации/фиксации не допускает частичную пару к invoke; не возникает успешного context-used при неуспешном emit. Повторная сборка не повреждает архив. |
| AC-PKT-10 | Multi-part extract сохраняет порядок/все части/инвентарь имён и прежнюю проверку покрытия; нет молчаливой обрезки, reuse между слагами или UTF-8 replacement. |
| AC-PKT-11 | Старый завершённый результат/legacy reconciliation принимается без нового side effect; новый invoke после включения требует Б56. Откат и handoff на другой root проверены, старый snapshot не редактируется/не исполняется. |
| AC-PKT-12 | Существующие G1–G6/REV/provider-fatal/receipt/occupancy/recover/phase-turn тесты зелёные; pid=wrapper, штат Codex/откат Cursor и модели YAML сохранены. Формат пакета не сбрасывает счётчики. |
| AC-PKT-13 | Утверждённый IAC покрывает каждый AC-PKT; impl/test раздельны, backup/git-proof/конечная загрузка и restore подтверждены; smoke содержит реальные CLI/файлы и честно отделяет stub от live. |
| AC-PKT-14 | Baseline-diff показывает только разрешённые файлы; нет новой БД/сервиса/очереди/канала/cron, restart Gateway, массового переписывания state/journal и изменений эко-конфиг/чужих результатов. |

## Б60. Компрессор: один publisher и независимое завершение

### Б60.1 Адресная нормативная правка NORM-R3 — 10.11.2026

Задание — BUGFIX `adresnyy-remont-publikatsii-extract-v-kompressor`; основание пересмотра требований Б55.5 — директива Саши от 10.11.2026, сохранённая в `evidence/HF-plan-r3/sasha-directive.md` этого слага. Точная предложенная дельта — `evidence/HF-plan-r3/delivery-contract.md`; действующая норма после согласования — этот master. NORM-R3 заменяет доставку механического inventory модели обратимой ModelView, добавляет принятый error-digest как второй содержательный источник и локальный допуск вместимости. Полнота acceptance/inventory, bootstrap, один publisher, независимый completion, все AC-COMP и T01…T18 сохраняются. Чтение доступных фактов архитектором уточнено в Б55.3. Новых сущностей, полей packet/state, роли, фазы, CLI или budget engine эта дельта не вводит.

NORM-R3 согласована собственной независимой REV:tz от 10.11.2026: APPROVE относится к входному master SHA-256 `bee5331fb738020ebe488465f08d61b55c6a912bad9dc0f96ab2a60ca5894471` и сохранённой редакции TZ-patch.md для NORM-R3. Разрешённая документная TZ:finalize закрепляет эту дельту без изменения согласованных требований: master, MAIN_TZ_INVENTORY.md и канон `dev/adresnyy-remont-publikatsii-extract-v-kompressor/TZ-finalize.md`; точные pre/post snapshots, diff и проверки — `evidence/TZ-finalize-norm-r3/` этого слага. NORM-R3 документно финализирована; общий status=draft сохраняется из-за отдельной несогласованной дельты Б61.4. CAP-R3 и допуск реализации по REVPLAN-R2 остаются открытыми. Чужой Б61.4, старые approvals и документные synthetic fixtures не дают допуска реализации. До HF:impl необходимы отдельно подтверждённые CAP-R3 для обеих поддерживаемых backend-ветвей по Б60.3.4, положительные измерения exact Request и полного consumer на окончательных источниках, актуальные AC-list/план/IAC/REV/packet и backup. Отсутствующий authoritative input именуется до prepare; серия пробных платных вызовов, смена модели/лимитов и backfill запрещены; адресное исключение только для client policy выбранного consumer задано Б60.1.1/60.3.4/60.8. Установленный runtime и выполнение проверок этим документом не объявляются исправленными. Приём артефактов и переходы — внешний оркестратор после выхода роли.

#### Б60.1.1 Адресный пересмотр client capacity policy — 11.11.2026

Область — BUGFIX `adresnyy-remont-publikatsii-extract-v-kompressor`. Основание «Пересмотра требований» Б55.5 — решение Саши `evidence/HF-plan-r6/owner-decision-20261111.md` этого слага: выбран **Путь 1**, сохранить полную доставку и адресно согласовать client capacity policy выбранного consumer. Предшествующие исследование и предложение — `evidence/HF-plan-r6/CAP-R3-research.md` и `requirement-revision-request.md`; они не являются capability authority. Изменяется запрет самостоятельной смены policy в узких границах Б60.3.4/60.8. Путь 2 с иным модельным render не принят; Б56, полная доставка Б60.6, acceptance/ModelView/inventory/echo, один publisher и независимый completion сохраняются.

Дельта согласована собственной независимой REV:tz от 11.11.2026: APPROVE относится к входному master SHA-256 `8bb3094f529a77c7dc19fa781bb227fc2eb646c2399b9d4face46c87191e323e` и TZ-patch.md SHA-256 `4fd8b7bba78a7b58c8ac0c9212fc57c18a6268137a6dd6d87efdae2a47f1b91a`; REV-tz.md SHA-256 `428f7351b0bf1d73c3137ec7620115ee382ac2366ecc882f7050b2461518326b`. Собственная документная TZ:finalize от 11.11.2026 записывает master, MAIN_TZ_INVENTORY.md и канон TZ-finalize.md в разрешённом scope по Б15, без изменения согласованных требований. Точные pre/post snapshots, обратимые операции, diff, прежний канон NORM-R3 и проверки сохранены в `evidence/TZ-finalize-cap-policy/` этого слага. Дельта Пути 1 документно финализирована; это не назначение увеличенного окна, изменение настройки или допуск HF:impl. Прежний APPROVE NORM-R3 сохраняет свою область; process state и старые approvals не переписываются. Затем HF:plan/REV:plan закрепляют конкретный carrier, подтверждённое окно и полный witness. Решение владельца уже разрешает этот адресный путь, повторное согласие на тот же выбор не требуется; неизвестные технические факты архитектор исследует по Б55.3. CAP-R3 и REVPLAN-R2 остаются открытыми до собственных доказательств. Конфигурация, runtime, process state, counters и прежние approvals этим документом не изменяются; Б61.4 сохраняет собственный draft-статус. Новых сущностей/ролей/фаз/схем/CLI/ENV/YAML-ключей и budget engine нет.

#### Б60.1.2 Расчётная константа CAPCONST-R10 — 11.11.2026

Область — тот же BUGFIX `adresnyy-remont-publikatsii-extract-v-kompressor`. Основание «Пересмотра требований» Б55.5 — решение Саши `evidence/HF-plan-r9/owner-decision-capconst-20261111.md` с явной поправкой 75→90. Оставшееся 75% в п.5 исходного свидетельства не отменяет эту поправку; сам источник не переписывается. Точный проект — `evidence/HF-plan-r10/normative-delta.md` и восемь операций `master-operations.json`; числовые входы с provenance — `evidence/HF-plan-r10/public-limits.json`. Разрешённая TZ:patch переносит эти восемь операций в Б60.3.4 и policy-часть Б60.8 без иных нормативных изменений; собственные metadata, preimages, полный обратимый diff и документная проверка сохранены в `evidence/TZ-patch-capconst-r10/` этого слага.

Статус этой дельты — **draft, ожидает собственной независимой REV:tz и TZ:finalize**. Прежние APPROVE/finalize NORM-R3 и Пути 1 относятся только к своим редакциям и не утверждают новые bytes CAPCONST-R10; Б61.4 сохраняет собственный draft-статус. Решение владельца о методе уже принято и не требует повторного согласия. Требование числовой аттестации окна владельцем deployment заменяется правилом Б60.3.4; это не доказательство фактической загрузки настройки, tokenizer, framing или native route. AC-COMP-01…12 и T01…T18 сохранены без изменения, как и полная доставка Пути 1, каждый резерв, model/effort/backend и общий publisher/completion.

CAP-R3 и REVPLAN-R2 остаются OPEN; HF:impl не допущен, runtime NOT_RUN. После собственной документной цепочки HF:plan/REV:plan актуализируют окончательные refs и проверяют technical evidence, обе exact Request и весь consumer witness по Б60.3.4/60.8; старые synthetic approvals/расчёты не переаттестуются. MAIN_TZ_INVENTORY.md синхронизирует разрешённая TZ:finalize по Б15; текущий TZ:patch его не пишет вне scope. Приём результата и все переходы выполняет внешний оркестратор после выхода роли; process state, counters, принятый packet и прежние approvals неизменны.

### Б60.2 Ответственность системы и модели

| Владелец | Разрешённый результат |
|---|---|
| Заказчик подтверждённого brief; затем архитектор и независимый ревизор | Заказчик даёт первичное подтверждённое содержание; Python копирует его без решений по Б60.3.1. Архитектор/REV формируют технические AC/IAC, изменения и переходы. До compressor нет неявной REV или права оркестратора сочинять критерии. |
| Python emit/admission | Проверка утверждённого acceptance InputRef, immutable snapshot/pin и accepted packet. Мнение модели не источник критериев. |
| Модель-компрессор | Сжимает полный master и, когда задан, полный error-digest одним вызовом в содержательный текст семи секций Б60.5; получает полную ModelView с несжатыми criteria. Допустим корректный входной multipart. Полный inventory/его paging/эхо/headers canonical формирует Python. Не packet_id, hashes, manifest, proof, receipt, имена файлов или state writes; не диагностика неизвестной первопричины. |
| Native/codex transport | Ответ конкретного dispatch и transport facts; ни одного canonical/proof/state publication side effect. |
| Общий compressor finalizer `invoke_role` | Проверка ответа/captured context, единственный вызов publisher. Не send/retry и не fallback. |
| `publish_validated_extract` | Точный canonical комплект, immutable manifest и extract_production штатным writer. Не result/receipt/metadata/done. |
| Общая success-финализация | После publication verification — context_result и одинаковый phase receipt одним штатным переходом. |
| Обычный completion / `compressor_metadata` | Независимая проверка сохранённых связей/байтов; metadata и done одним штатным переходом. Не публикация и не достройка proof. |

Один codex dispatch означает один запуск выбранного CLI без второго backend/перезапуска; не выдавать это за доказательство одного внутреннего API-вызова агента. Для native сохраняется именно **один SDK send, max_retries=0**. Компрессору не поручают реализовать механический контракт и не требуют повторять identity в тексте.

### Б60.3 Закреплённый acceptance и capture до dispatch

Добавить только аддитивное сохранение `pinned.input-checklist` существующей сериализацией PipelineState: `{ref: FileRef, revision: string, basis: FileRef}`. Ref указывает `dev/<slug>/context/acceptance-<sha256>.json`; SHA имени — hash полных canonical JSON bytes, без self-hash в содержимом. Basis — проверяемый immutable источник независимого утверждения **этой** редакции, а не единоличное заявление автора. Pin пишет только штатный pipeline writer. Старое state без pin читается с прежним SHA: отсутствующее поле не добавлять как пустое при round-trip, проверку целостности не ослаблять, массовой миграции нет.

Снимок — локальный data-only документ существующего продукта. Нормативный минимум его закрытой структуры:

| Поле | Требование |
|---|---|
| `format`, `revision`, `task` | Одна версия формата acceptance, непустая редакция; точные slug/case и предметный master binding. Название формата и полные nested types закрепляет HF:plan/REV:plan один раз для общего primitive. |
| `source_refs` | Полные FileRef утверждённых исходных документов; strict UTF-8 для текста. Нельзя включать будущий hash самого snapshot/approval/result. |
| `criteria` | Уникальные полные строковые ID AC/IAC, kind, covers, oracle, verify, expected, evidence. Oracle/expected задаются до исполнения; команды verify — данные плана, admission их не запускает. Covers разрешаются на существующие полные ID. |
| `phases` | Явные пофазовые inputs/outputs/write_scope/prohibitions и выбор применимой проекции. Проекция определяется принятым заданием, не сжатым текстом и не перечнем прошедших тестов. |
| `compressor` | Заранее заданные правила совокупного текста, Python paging/локальных эхо/лимита и полный буквальный inventory с source/span для каждого элемента по Б60.3.2; все семейства ID. Ничего не выбирается по ответу модели. |

До HF:impl план закрепляет полную вложенную структуру, типы, канонизацию, fixtures и источник утверждения; незаполненный template не допускает вызов. JSON duplicate keys, NaN, unknown keys, неверные типы/bool вместо int, повтор ID, неразрешённые covers, symlink/non-regular/escape отвергаются. Не добавлять неизвестные поля в packet `devworkflow-packet/1.0`: использовать существующие `handoff.inputs` и ReadRef. Полный checklist вместе с inventory остаётся несжатым системным InputRef; модель и следующие содержательные роли полностью читают обратимую ModelView по Б60.3.3. Все criteria и их bindings передаются без сжатия; механический массив не дублируется в модельном Request. Вторую схему packet, автоматическое восстановление expected и новый реестр не создавать.

Первичная фиксация — штатный emit до prepare по полностью определённому маршруту Б60.3.1. Явно названные InputRef: подтверждённый brief и его independent approval basis, либо уже утверждённый acceptance. Python проверяет и копирует содержание; не выводит AC/oracle из extract/текущего master. IAC до HF-плана отсутствует явно. Добавление технических AC/IAC/смена требований требует approved revision и сохранения A. Обычный emit с существующим pin требует точного совпадения ref/revision/basis; молчаливый overwrite запрещён.

Минимальный **compressor-only переход A→B** нужен положительному accepted refresh и входит в этот primitive: новый явно названный acceptance InputRef и immutable независимый approval указывают exact прежний A, новый B и основание изменения. Для master refresh основание содержит проверенный output завершённой роли и штатное открытие существующего producer; для добавления IAC — утверждённый HF-план/REV. Перед prepare emit проверяет эту связь, актуальность B/источников/границ и отсутствие активного старого вызова; сохраняет ref/revision/basis A и approval/основание перехода в context_history, затем атомарно фиксирует B+новый emit binding существующим locked commit. Снимки A/B/старые packet/manifest неизменны. Неполная связь, иной текущий A, неутверждённый B и смешение результатов A/B отказываются, counters не сбрасываются. Полную nested форму transition evidence и отрицательные fixtures закрепляет HF:plan. Это не общий механизм пересмотра всех фаз/финальной биекции lock-поезда.

Snapshot публикуется и проверяется прежде единого locked commit pin+успешного emit binding. Ошибка оставляет недопущенный orphan, не активный pin/успешный marker. Если pin отсутствует у старого слага, нужен оформленный новый допуск на явно утверждённом документе; автоматического backfill нет. Доказывается закрепление **до данного dispatch**, не историческое наличие pin при init старой задачи. Для данного ремонта собственный документный AC-контракт утверждается до HF:impl; новый программный primitive проверяется на новых изолированных fixtures. Это не заявление, что сломанный старый runtime уже обеспечивал lock его разработки.

Exact ID сравниваются как полные значения, без substring/ограничения `AC-\d{3}`/`IAC-\d{2}`. Обязательные примеры: `AC-PKT-10`, `AC-SIMP-07`, `AC-PW-01`, `AC-RP-01`, `AC-P1`, `COD-C10`, `IAC-09a`, `IAC-09b`; `IAC-09` не покрывает suffix. Literal coverage индекса проверяется дополнительно по закреплённым source bytes/inventory, сохраняя прежние классы имён. Критерии не восстанавливаются из extract. Смысловую полноту индекса и корректность AC/IAC проверяют архитектор/REV по master. Совокупный inventory больше лимита части размещается положительно по Б60.5; до dispatch проверяется размещаемость каждого неделимого элемента с framing. Невозможный единичный элемент/неполнота источника дают fail-fast проверки выходного размещения. Отдельный обязательный допуск вместимости точного модельного Request задан Б60.3.4; большой inventory сам по себе не заменяет эту проверку и не является её отказом. Урезание и серия неизменных повторов запрещены.

Для обеих backend-веток расширить существующий AcceptedCompressorContext: immutable packet/render bytes+refs/prompt SHA, slug/phase, prepare identity `(wrapper_pid, turn_count, started_at)`, acceptance ref/revision/basis, все принятые источники и захваченные core/overlay/master bytes, полные A/inventory, ModelView и её inverse, error-digest при наличии, capability evidence и exact Request по Б60.3.3/60.3.4. Request digest считает Python по фактически отправляемому содержимому; ответ присоединяется к контексту создавшего его dispatch, а не к identity из модели или заново прочитанного prepare.

Перед prepare проверяются schema/G6, source/pin/model/capabilities, допустимость outputs и cleanup в write_scope. Перед replacement и отдельно перед result commit перечитываются state/packet/pin/refs и сравниваются **с захваченным**. Проверяются lexical/resolved path, hash/size/mtime, активная фаза/prepare и фактически прочитанные prompt operands. Исчезнувший master — отказ, не skip coverage. Разрешённый scope не разрешает сжимать другие bytes под прежним packet. Существующий queue lock короткий, без LLM/SDK/send под lock; защиты от произвольного злонамеренного writer/нового global mutex не обещать.

### Б60.3.1 Первичный A до первого compressor: происхождение и владельцы

Это исчерпывающее **узкое исключение** к фразе диагноза §4.1 «автор — архитектор с обязательной REV»: до первого `TZ:compress` технического ТЗ/IAC ещё нет. Автор исходного содержания — заказчик в подтверждённом brief; производитель его механической проекции — Python существующего emit. Независимый источник утверждения первичного A — **подтверждение заказчиком exact исходного brief**, независимое от Python/компрессора/записавшего факты оркестратора. Это не независимая техническая REV и не утверждение будущих AC/IAC; `TZ:patch → REV:tz` и `HF:plan → REV:plan` остаются на своих местах. Подтверждённый принятый исходный запрос, сам содержащий весь brief, является таким основанием; общее «делай» без однозначно связанной редакции или поздний пересказ оркестратора — нет.

Канонический первичный вход — `dev/<slug>/brief.md` плюс immutable сохранённый источник его принятия в существующем `evidence/` с origin, автором/датой/ID исходного сообщения, полными подтверждёнными bytes brief и их SHA-256. Связь exact bytes с исходным запросом/подтверждением проверяется по сохранённому источнику, не по одному полю `approved=true` или утверждению автора brief. Подтверждение относится к исходным требованиям, а не к дописанному позже handoff. Повторная фиксация копирует тот же подтверждённый payload; не требует нового сообщения Саши, если существующий источник достаточен. При отсутствии доказанной связи — именованный missing input до prepare; автоматического утверждения, backfill и пробного compressor нет.

Оркестратор на существующем приёме/закрытии brief (до init, либо механическое сохранение после init по Б18 (закрытый бриф)) сохраняет факты и исходное подтверждение. На `TZ:stabilize` проверяет path/version/mtime и наличие этих входов; не создаёт технические критерии. Для нового полного CHANGE порядок **принятый brief → init → stabilize → emit первого TZ:compress → invoke** сохраняется. Первый emit получает brief/basis через `handoff.inputs` с `phase=null`, строит immutable `context/acceptance-<sha256>.json`, добавляет его полный системный InputRef и полный ReadRef обратимой ModelView по Б60.3.3 в создаваемый packet и одним существующим locked commit фиксирует pin+emit. Snapshot/approval публикуются раньше commit; ни сирene-фаза, ни init не создают invoke роли. Новый CLI, phase/role/gate, перенос REV до compress и изменение recipe не вводятся.

Проекция A типа `brief-copy` проверяется **пересборкой и побайтным равенством**, а не семантическим выбором Python: полный подтверждённый payload brief остаётся несжатым; явные исходные номера/ID и весь текст пунктов приёмки копируются по порядку вместе с точными byte spans в source. Если явного списка нет, один requirement-text элемент содержит весь подтверждённый payload, без выдумывания AC. Если номера не являются ID, технические ключи строк `BRIEF-01`… задаются детерминированным порядком, не выдаются за утверждённые AC/IAC. Expected — дословный исходный пункт; oracle — заранее установленное этой нормой `review-against-source`, verify отсутствует (`null`), evidence — ссылка на этот source/span. Это требование к смысловой сверке будущими ролями, не изготовленный тест или новый runtime PASS. В A нет отсутствующих IAC/будущих команд. Ни один пункт/запрет/остальной payload не теряется; произвольные changed expected/extra/missing/duplicate/span/order дают отказ пересборки.

Механические compressor-правила, допустимые producer outputs/scope и полный inventory входят в A как **отдельная phase-проекция** установленного согласованного Б60, с immutable ref её нормативного основания; их не выводят из сжимаемого master и не изменяют по тексту brief. Фактический master FileRef — source operand, не новый автор expected. Write-scope берётся только из принятого data-only handoff; нехватка разрешения блокирует, не дополняется автоматически. Полные nested types и точный детерминированный parser source spans закрепляются HF:plan/REV:plan; перечисленные здесь владелец, момент, вход/основание и no-content-change правило не оставлены на выбор исполнителю.

После первого compressor архитектор в штатной `TZ:patch` формирует AC, `REV:tz` независимо утверждает **следующую редакцию**; добавление IAC — `HF:plan/REV:plan`. Любое содержание сверх literal brief-copy, неоднозначная переработка исходного списка или смена oracle/expected требует этого маршрута, а не requester-copy исключения. B ссылается на A и approved transition; A/brief/basis и прежние bindings неизменны. Минимальный A не объявляется уже готовым глобальным task-entry lock или финальной биекцией всех фаз.

### Б60.3.2 Полный inventory и проверка вместимости

Inventory — полный закреплённый массив буквальных значений с классом и source byte spans; никаких size-driven exclusions. До отправки он строится/проверяется Python по captured source bytes и согласованному правилу, полностью сохраняется несжатым системным входом и связывается с acceptance/manifest. Несжатая передача здесь означает полный доступный исходный массив и проверку Python, а не включение многомегабайтного массива/origins в LLM user content. Модельная доставка и обратная сборка — Б60.3.3; выходная размещаемость каждого literal и входная вместимость exact Request проверяются раздельно до prepare. Лексический нижний слой включает **все непустые inline-code spans вне fenced code, без исключения исторических секций/changelog**, все полные встреченные ID AC/IAC/COD и дословный NEW-ENTITY-маркер. Повторы значений объединяются с сохранением всех origins. Чтобы первичный A не зависел от ещё не состоявшейся подготовки/REV именного inventory, консервативная обязательная база дополнительно включает все максимальные непробельные spans исходного master, в том числе fenced/plain/changelog, с полными source byte spans. Это лексический словник с избытком, а не выбор актуальных требований. Правило задано Б60 до dispatch: полнота базы проверяется повторной детерминированной выборкой, отдельное предварительное утверждение словника или вызов архитектора не нужны. Составные literal имена сохраняются также целыми inline-code spans; дополнительные составные имена из исходного утверждённого inventory добавляются, не заменяя базу. Смысловую полноту индекса и невыделенные составные имена проверяют архитектор/REV в штатных последующих фазах по полному master; ни лексический PASS, ни эта консервативная база их работу не объявляют выполненной. Regex не выбирает применимость требований. Нет автоматического «актуального подмножества», удаления path потому, что он длинный, или замены буквального имени диапазоном.

### Б60.3.3 Обратимая ModelView и неизменный acceptance

`C(x)` — полные canonical UTF-8 JSON bytes по Б56.2, без LF, duplicate keys, NaN, Unicode/CRLF/trim нормализации. Acceptance A и независимый Pin.basis остаются SoT приёмки. Единственный context owner `pipeline_context.py` строит immutable content-addressed ModelView, а не семантическую выборку критериев:

1. Скопировать A целиком; заменить `format` на `devworkflow-compressor-model-view/1.0`.
2. Только ветку `compressor.inventory` заменить на `compressor.inventory_ref: FileRef` полного canonical массива, включая все origins. Сам A не менять.
3. Добавить ровно три корневых поля: `acceptance_ref=Pin.ref`, `approval_ref=Pin.basis`, `confirmed_payload` = конкатенация подтверждённых brief spans в исходном порядке; при законном отсутствии brief — пустая строка. Все остальные поля A, в том числе criteria с полными ID/kind/covers/oracle/verify/expected/evidence, phases, derivation и source refs, сохраняются целиком.

Inverse удаляет только эти три added fields, восстанавливает format A и подставляет прочитанный полный массив вместо inventory_ref. Обязателен `C(inverse(ModelView)) == bytes(Pin.ref)`; отдельно проверяются равенство added refs текущему pin и exact confirmed_payload/source spans. Один inverse не удостоверяет подменённые added fields. Missing/extra/changed поля или bindings, неполный inventory/origin, нечестный ref и любой drift дают отказ. Смысловую полноту и истинность источников по-прежнему проверяет независимая REV; побайтное равенство не становится semantic PASS.

Материализация ациклична: immutable исходные документы → полный inventory → A → независимое basis для exact A (requester-basis при первичной копии уже существует) → ModelView → packet/render → Request. Ни A, ни inventory не содержат будущих refs на собственные approval/ModelView/packet/Request; ModelView/Request не содержат своего FileRef. Snapshot failure оставляет недопущенный orphan, не успешный pin/emit. Нужный полный inventory уже входит в A как системный InputRef; отдельный inventory_ref даёт доступ к тому же массиву, а не создаёт новый управляющий purpose. Generated ModelView включается только как full ReadRef и operand, без включения зависящего от A ref обратно в предметные inputs A.

Для handoff сохраняется закрытое множество управляющих purpose: `compressor-brief`, `compressor-acceptance`, `compressor-approval`, `compressor-transition`. Только они исключены из хешируемой предметной проекции inputs; все четыре refs/связи проверяются полностью по pin/basis/transition. Пятый control-purpose или исключение предметного error-digest/model-capability не вводятся. План закрепляет nested типы и fixtures трёх положительных маршрутов brief-copy, explicit A и A→B; новый транспорт не переоткрывает закрытый дефект цикла R1 и не ослабляет проверки полного H/packet после capture.

На compressor и следующем consumer emit система читает A/inventory полностью и проверяет inverse до публикации packet. Полная ModelView является обязательным full ReadRef содержательной роли; A/inventory доступны по FileRef без обязательного повторного чтения механического JSON моделью ради сжатия. Полный master читается по действующему MUST-read и передаётся compressor целиком; summary его не заменяет. Оригинальные snapshots/render/inline не редактируются; packet остаётся `devworkflow-packet/1.0`. Перед prepare, replacement, result и независимым check/complete заново проверяются captured refs, inverse и исходные bytes. Boolean об успешной сборке ModelView не proof.

### Б60.3.4 Два содержательных источника и локальный допуск вместимости

`error-digest` — необязательный обычный предметный InputRef принятого handoff, а не управляющее исключение. Если задание его объявляет, нужен ровно один ref в H и точное совпадение с предметной проекцией A; отсутствие обязательного файла, дубликат, неизвестный digest либо request-текст без ref отказываются. Если задание его не содержит, `errors=null`, историю не сочинять. В Request передаётся весь текст digest byte-equal FileRef, не session dump. Размер ≤16384 UTF-8 bytes; уникальные записи E01…E99 содержат наблюдение, доказанную причину либо явно помеченную гипотезу/unknown и ссылки на конкретные логи/тесты. Превышение размера — адресный возврат автору, без truncate. Точный parser полей фиксирует HF:plan; semantic оценка причин принадлежит архитектору/REV. Digest ref входит в capture и manifest operands как source и проверяется до prepare/replacement/result/complete.

Модель сжимает master и digest одним ответом, сохраняя E-ID, ссылки и различие наблюдения/гипотезы/NOT_RUN внутри подходящих семи секций; восьмая секция не добавляется. Архитектор самостоятельно добирает нужные raw logs по E-ID/пути, фиксирует прочитанные FileRef в evidence фактов и сопоставляет их с master. Сжатая копия не SoT, изменение raw log не легализуется старым digest. Дополнительный LLM-preflight и новая compress-фаза BUGFIX запрещены.

Закрытая форма `Request` — `format="devworkflow-compressor-request/1.2"`, непустые строки `instruction`, `packet_render`, `core`, `overlay`, `master`, `model_view`, `backend` из `{codex,hermes-internal}`, непустая `model`, `effort` как непустая строка либо null и `errors` как null либо ровно `{ref:FileRef,text:непустая string}`. `model_view` — декодированный `C(ModelView)` без дополнительного summary. Core/overlay/master — полные captured bytes, packet_render — exact render принятого packet. Ни полного A, ни отдельной inline-копии inventory в Request нет. Native user content и Codex stdin равны exact `C(Request)`; native envelope остаётся model/messages/stream=false. Один native SDK send/retries=0 и один Codex CLI dispatch сохраняются. Старые Request/1.0 и /1.1 не fallback. Инструкцию семи секций/системной механики задаёт adapter; исторические core/overlay не выбирают модель и не требуют записи canonical.

**Capability evidence (CAP-R3)** — локальные data-only документы существующего owner, без новых ENV/YAML keys и без policy других ролей. Закрытые типы дополнения (S = непустая строка, Pos = integer ≥1, не bool; `?` = обязательное поле типа либо null):

```text
TokenizerSpec = record{encoding:S,implementation:S,version:S,asset_refs:array<FileRef>}
CapacityReserves = record{instructions_and_tools:Pos,response_and_reasoning:Pos,margin:Pos}
Capability = record{format:enum(devworkflow-compressor-capability/1.0),
                    backend:enum(codex,hermes-internal),model:S,route_identity:S,
                    tokenizer:TokenizerSpec,context_window:Pos,effective_percent:Pos,
                    reserves:CapacityReserves,cli_version:S?,cli_ref:FileRef?,
                    instruction_refs:array<FileRef>,authority_refs:array<FileRef>}
CapabilitySet = record{format:enum(devworkflow-compressor-capabilities/1.0),profiles:array<Capability>}
```

Все массивы refs и profiles непусты, дополнительные поля запрещены; effective_percent≤100. Пары backend/model уникальны, выбранная пара совпадает ровно с одним profile. Для Codex cli_version/ref обязательны, для native оба null. route_identity и refs не раскрывают credentials. CapabilitySet — обычный предметный InputRef purpose=`model-capability`, включённый в A до вычисления A; не содержит ссылки на A или собственное approval. Метод числовых лимитов CAP-R3 задаёт решение Саши от 11.11.2026 `evidence/HF-plan-r9/owner-decision-capconst-20261111.md` этого BUGFIX: брать **90% максимальных официально опубликованных провайдером значений exact модели**. Для каждого опубликованного context/input/output максимума `L_calc=floor(90*L_public_max/100)`; коэффициент применяется один раз, 75% не действует. Отдельное подтверждение чисел владельцем deployment не требуется. Независимая REV сверяет exact alias, официальный URL/дату, опубликованные максимумы и целочисленный расчёт; route/model, tokenizer/version/assets, CLI/instructions/tools/framing и достаточность резервов проверяются отдельно. Capability сохраняет context_window=публичный максимум и effective_percent=90; отдельные input/output пределы и источник метода фиксируются в существующих authority_refs без расширения CapabilitySet. Если отдельный максимум не опубликован, число не выдумывается и условие именуется отдельно. Самостоятельное число window, CLI cache, synthetic fixture или предположение о tokenizer по имени не становятся authority. Это расчётная константа владельца для ролевых моделей Б60, не утверждение о фактическом окне deployment и не глобальное изменение client defaults.

До prepare локально сверить выбранные backend/model/route/CLI/instruction refs с profile, прочитать только уже доступные локальные tokenizer assets по проверенным refs и посчитать exact `C(Request)`. `implementation` — закрытое поддержанное имя, не исполняемый код/команда из profile. Install/import-команды из документа, download/discovery и provider probe запрещены. Unknown profile/tokenizer/route, неподтверждённая граница framing/tools либо drift дают именованный отказ до prepare/turn/send, не приблизительный допуск. Прежние resolver-классы static/model отказов Б60.4/60.7 сохраняются.

Допуск: `count(C(Request)) + instructions_and_tools + response_and_reasoning + margin ≤ W_calc`, где `W_calc=floor(context_window*90/100)`. При отдельном опубликованном input maximum дополнительно `count(C(Request)) + instructions_and_tools + margin ≤ I_calc`. Резервы положительны, заранее закреплены проверенным profile; полный framing/tools сверх Request учтён. Response_and_reasoning — консервативный резерв контекста, не requested generation limit: он остаётся не меньше прежнего значения даже при меньшем O_calc. Допустимый планируемый output вместе с reasoning ограничен O_calc, для контекста списывается весь резерв; разница не возвращается вводу. На публичных 1050000/922000/128000 расчётные пределы равны 945000/829800/115200, резерв 128000 сохраняется. Подтверждённые более узкие локальные client/compaction bounds проверяются отдельно; константа не разрешает молчаливую обрезку. Wire envelope не меняется ради расчёта. Byte size не число токенов; лимит чтения raw response не резерв генерации. Уменьшение резервов ради PASS, самостоятельная смена window policy, смена модели/effort/backend, повтор send и новый budget engine запрещены. Единственное адресное разрешение изменить существующую client context policy выбранного consumer — ниже и в Б60.8; оно не меняет policy compressor или других потребителей. Равенство принимается, +1 отвергается; synthetic граничные профили проверяют арифметику, не удостоверяют реальный маршрут.

До допуска реализации нужны положительные exact requests обеих ветвей на окончательном полном master, полном inventory и принятых sources с independently проверенным CAP-R3. Кроме них IAC предъявляет полный consumer witness: весь render со всеми echo-частями, полная ModelView и остальные обязательные чтения/framing для фактически выбранного consumer. Нехватка вместимости ведёт к адресному возврату до consumer invoke, без skip частей/чтений. Это проверка конкретной поставки; нового глобального runtime guard/лимитатора других ролей нет. Неподтверждённые profile/вместимость остаются OPEN/NOT_PROVEN, не runtime PASS и не повод сделать пробный платный compress.

**Адресное исключение Пути 1 (Б60.1.1).** Для полного consumer witness этого BUGFIX разрешено согласовать изменение существующей client context policy того же выбранного Codex/model/effort/route. Исходная исследованная связка — Codex 0.163.0, `gpt-6-astra`, `high`; фактически выбранная связка и применимость доказательств заново закрепляются до допуска. Подстановка `xhigh`, другой модели/backend/deployment для получения большего окна этим решением не разрешена. Исключение относится к именованному consumer и его поставке; глобальное изменение default или policy остальных ролей из него не следует.

1. Конкретные carrier настройки, исходное/предлагаемое значение и область применения выбирает архитектор в HF:plan; независимая REV:plan проверяет поддержку **тем же** CLI/model/deployment и приоритет реально загружаемой настройки. Числовое основание окна — принятые 90% официального публичного максимума по правилу выше; отдельную deployment authority этих чисел не требовать. Cache max, историческое окно другого вызова и успешный parse настройки не доказывают её effective load. Нужны локальный effective load/framing proof для выбранного carrier/namespace, CLI version/hash и instruction/tool refs; приоритет и локальное усечение/compaction проверяются без подмены расчётной константы. Нет такого локального подтверждения — именованный missing input, CAP-R3 OPEN/NOT_PROVEN; факт загрузки не выдумывается. Автоподбор, download/discovery и пробные provider sends не добавляются.
2. Резервы не уменьшаются ни по одному компоненту. Исходные consumer значения из R6 — instructions_and_tools=50000, response_and_reasoning=128000, margin=2500 — сохраняются как нижние границы расчёта, **не** как подтверждённый upper bound framing или output authority. Если доказанный состав требует больше, резерв увеличивается и весь допуск пересчитывается. Exact tokenizer binding/assets и полный framing/tools по-прежнему требуют независимого основания. Числа input/output и effective percent проверяются по публичным максимумам и фиксированным 90%; ни один резерв не уменьшается, reserve и generation limit различаются по правилу выше. Разрешение policy не аттестует tokenizer/framing.
3. Полный consumer включает exact render со всеми parts/эхо/FileRef, полную ModelView/criteria и все обязательные чтения, включая полный master при соответствующем MUST-read. После изменения нормы/источников/настройки нужен новый witness на окончательных bytes и bindings, с учётом всех инструкций/tools/framing и указанных резервов. Применяются те же неравенства с W_calc/I_calc, полными резервами и отдельной проверкой более узких локальных client bounds; коэффициент 90% не применяется повторно к уже рассчитанному пределу. Нельзя сокращать delivery, скрывать эхо, заменять render указателем, сжимать criteria, отменять чтения или рассчитывать PASS за счёт молчаливой обрезки/compaction. Положительный исход старого synthetic witness не переносится на новую редакцию.
4. Новые capability/policy evidence сохраняются как data-only FileRef в существующих evidence и проверяются до допуска реализации. Форма packet/state/CapabilitySet не расширяется: необходимые authority/load документы связываются существующими refs; их команды не исполняются admission. Изменение model-capability как предметного input требует новой ацикличной сборки acceptance/basis/ModelView/packet/Request по действующему контракту. Старые pin/packets/manifest/approvals не исправляются; новый policy proof не приписывается прежнему dispatch.
5. До HF:impl по-прежнему обязательны положительные exact Requests **обеих** compressor-ветвей и полный consumer witness с подтверждёнными источниками. Разрешение изменить только consumer policy не аттестует Codex compressor namespace и native route. Отсутствие достаточного расчётного окна, доказанного local load, tokenizer/native identity/setup/framing evidence или положительного полного witness сохраняет отказ допуска; Путь 2 не включается автоматически. Следующий результат — точное противоречие для адресного пересмотра, без неизменного платного повтора, нового hold/Q-n или reset counters.

### Б60.4 Transport response и технический запрет записи

Codex compressor получает exact Request по Б60.3.4: полные core/overlay/master, обратимую ModelView, принятый error-digest при наличии и правило полного финального текста. Общая инструкция «запиши канон, верни резюме» в этом режиме не используется. Уникальный абсолютный `--output-last-message` относится только к этому dispatch; до запуска response path отсутствует. Accepted packet/render/sidecar не переписываются. stdout/stderr остаются исходными transport JSONL для существующих fatal/session parsers, а final-message — отдельным каналом текста.

После transport rc=0 и отсутствия fatal выполняется lstat/type check **до чтения**: только regular non-symlink file, strict UTF-8, непустой текст. Missing/empty/invalid UTF-8, directory/FIFO/device/symlink дают rc=4 без fallback на stdout/tool output/прежний extract/слова «файл записан». Response scratch/private caches очищаются в finally на всех путях; логи не содержат ключей/raw provider body.

Выбранная граница capabilities — существующий на хосте **bwrap** для compressor-подпроцесса: read-only корень/исходный workspace/master/prompts/state/context/pin/canonical/manifest/соседние слаги; writable только уникальные response scratch и минимальные private CLI caches/session storage. Child/tool processes наследуют mount namespace. Не открывать writable parent/alias, позволяющий обойти защиту. Auth/config доступны только для чтения; рабочие credentials не публикуются в evidence. Network для выбранного backend сохраняется без нового сервиса/маршрута. Наличие бинаря/одна ОС-проба не аттестуют полный Codex mode.

Прежнее требование `danger-full-access` не разрешает compressor писать host workspace. Если этот argv сохраняется внутри namespace, его host-доступ всё равно ограничен mounts; флаг сам по себе не proof. Обычные architect/reviewer/executor сохраняют свои argv/sandbox. Готовность режима проверяется до prepare без платного вызова. На HF:test и installed smoke настоящий executable stub пытается писать canonical/state/pin/master/соседа, в том числе child-процессом и по абсолютному пути; отказ обеспечивает ОС, bytes сохраняются. Затем publisher вне backend namespace успешно записывает canonical. Непригодный режим — pre-prepare refusal; запуск общего пишущего codex и native-only не закрывают ремонт.

Native adapter hermes-native означает hermes-internal и возвращает только text+transport outcome через системный канал; native worker/модель ничего не публикуют. Содержательный ответ не сканируется как plain provider stderr; сохраняется различение response text и error envelope. Один SDK send, retries=0, worker isolation, без discovery/fallback/rotation. Отсутствующие static model/key/base, worker/transport/provider failure — rc=3; HTTP-success без пригодного completion — local rc=4 без publication/result/receipt.

Codex compressor использует один resolved concrete model/effort: допустимый явный override, иначе `roles.compressor` YAML. Null/empty/whitespace/non-string/`hermes-native` для codex отказываются до prepare, rc=2; `HERMES_COMPRESSOR_MODEL` здесь не читается. Native выбирает explicit concrete --model, иначе roles.compressor.model; null/empty/native selector использует static HERMES_COMPRESSOR_MODEL. Whitespace/non-string/non-concrete ENV отказаны до SDK/send, static refusal — rc=3. YAML/ENV/default backend и секреты не изменяются и не обнаруживаются автоматически.

### Б60.5 Единственный publisher, части и manifest поколения

Контракт prompt-источников: `Registries/core-compressor-prompt.md` и `tz-compressor-prompt.md`. Содержательный текст содержит ровно семь секций в заданном порядке: `Назначение`, `Сущности`, `API / CLI`, `Связи`, `Конфиг`, `Ограничения`, `Источник`. Третье машинное имя — ровно `API / CLI`, без альтернативного написания. Проверяется восстановленный совокупный payload, не каждая транспортная часть; отсутствие, дубль или перестановка секции дают отказ без публикации. Полный перечень и порядок заданы только здесь.

Общий compressor finalizer выполняется после transport/fatal checks **для обеих веток**, до result/receipt. Входной splitter не теряет prefix: перед первым model multipart header допускаются только пробелы/пустые строки; содержательный prefix отвергает весь ответ. Входной multipart — ровно N последовательных `## Часть k/N`, k=1…N, N≥2, без пропусков/дублей/перестановки. Single-part без header допускается; malformed/1/1 не маскируется. Raw response целиком сохранён своим hash; служебные model headers отделены от содержательных payload. Их ordered конкатенация восстанавливает весь содержательный текст, без trim. Семь секций проверяются в этом тексте, а не в каждом его фрагменте.

**Python paging (единственный publisher):** берёт проверенный содержательный текст и полный pinned inventory, без требования повторения inventory моделью. Для расчёта framing до dispatch используется верхняя граница числа страниц `max(1, число Unicode-символов содержательного текста + число элементов inventory)`; для самого предварительного inventory feasibility достаточно границы по inventory и допустимой framing-схемы, проверенной планом. При ответе число разрядов этой границы резервируется под оба числа header. Детерминированно разбить текст слева направо на максимальные Unicode-подстроки, помещающиеся с framing и пустым эхо; ни один символ не теряется. Затем в порядке полного inventory положить целые строки `- <literal>\n` в свободное место последней страницы, далее в новые страницы. Каждая страница заканчивается `## Эхо инвентаря`; допустим пустой список либо inventory-only продолжение. Итоговый N/headers пишет Python. Пробелы/переводы строк исходного payload не удаляются; служебные разделители обратимо отличимы по manifest spans.

Ни одна **готовая** часть не больше 5120 Unicode-символов вместе с header/footer/эхо; часть в 5121 отвергается при readback/check/complete. Raw содержательный ответ в 5121 символ допустим, если корректно упакован в несколько частей: это явная смена прежнего требования лимита к части ответа модели. Совокупный inventory любого размещаемого размера добавляет страницы; N=12 и N>12 разрешены. Неделимый элемент, превышающий ёмкость собственной страницы с framing, отказывает до dispatch по Б60.3.2, без потери имени/повтора модели. HF:plan фиксирует framing/length-prefix или spans, канонический порядок inventory и проверку безопасной верхней границы; иной смысл или эвристический отбор имён не допускаются.

Независимая проверка восстанавливает содержательный текст по manifest spans и сверяет его hash/длину с captured logical response, проверяет семь секций по Б60.5, полное exact объединение локальных эхо с pinned inventory, каждый целый literal/его assignment и весь framing. Поддельный inventory в тексте модели не меняет закреплённый массив. Верификатор не получает права дописать потерянное имя/перепаковать canonical при complete.

| Ответ | Точный canonical комплект | Учёт |
|---|---|---|
| Одна часть | Только `extract.md` | Одна часть/один hash. |
| N≥2 | `extract-1.md`…`extract-N.md`, `extract.md` byte-equal part 1 | Numbered части в числовом порядке; alias не удваивает chars/aggregate. |

После полной проверки stage всего будущего комплекта; replacement; удаление только устаревших `extract-[1-9][0-9]*.md` собственного слага; повторная проверка точного набора/alias/bytes/identity/sources. N=12 и переходы 3→2→1/1→3 обязательны; лимит N=10 не вводить. Для любого canonical/stale target symlink/non-regular — безопасный отказ **до replacement**; не читать target и не удалять каталоги рекурсивно. Соседние файлы/слаги неизменны.

Manifest — immutable canonical JSON `context/extract-publication-<publication_id>.json`. Он содержит format, publication_id, slug/phase, packet/prompt/request/response SHA, acceptance ref/revision/basis, source/operand refs, captured prepare identity, ordered parts rows `{index, basename, ref: FileRef, chars}`, alias FileRef и aggregate SHA/total chars. Индекс и basename должны соответствовать друг другу. Manifest дополнительно связывает logical response SHA/число Unicode-символов, ordered payload spans и per-part assignments элементов inventory (индексы/полные значения/хеши). Проверяется точное восстановление payload и exact union эхо без потерь, лишних/повторных assignments. Ordered manifest защищает границы/порядок частей, которые не доказывает одна конкатенация bytes. Publication_id = SHA canonical объекта **без поля publication_id**; внешний FileRef manifest считает полные опубликованные bytes и не включается внутрь самого manifest. Полные nested types/канонизация закрепляются HF:plan до кода; self-reference нет.

После файлов и readback manifest сохраняется без overwrite; publisher под существующим writer фиксирует extract_production с FileRef manifest и captured bindings. Общий post-invoke повторно проверяет их и сохраняет result/receipt одним переходом. Compressor receipt дополнительно связан с publication_id/prepare; одна session_id не делает два turns одним результатом. Конкретная строковая форма compressor receipt закрепляется планом, остальные роли используют прежнюю форму. Старый `write_extract_after_validation` не остаётся production bypass: проверить callers, делегировать единственному validated пути с полным контекстом либо исключить из production. Второго publisher нет.

Ошибка до первого replacement оставляет canonical/production прежними. Между replace/unlink/manifest/proof/result возможен физически частичный набор/orphan manifest; crash-атомарность комплекта не заявляется. Но не возникает пригодного успешного result/receipt/done: consumer/check/complete требуют целую цепочку и отказывают. Старый proof не легализует новые bytes; недостающий proof не достраивается. Fault injection каждого шага и rollback существующего state commit обязательны. После publication без result — отказ/диагноз; повторно вызывать publisher из completion запрещено.

### Б60.6 Независимый completion, consumer и история

Один verifier связности используется finalizer и completion, но completion заново читает persistent packet/prepare, manifest/production, context_result/phase receipt, pin/approval и файлы. Проверяет точные identities, source/operand refs, request/response bindings, полный ordered набор, alias/лимиты/chars/aggregate/manifest SHA и закреплённый inventory. Boolean `publisher_success`, rc=0, mtime или свежий canonical поодиночке не доказательство. Metadata вычисляется из принятого manifest/source capture; другой текущий master не становится новым источником результата.

G2 и compressor-specific freshness допускают **byte-identical новый ответ**, когда Python действительно произвёл новую валидную publication захваченного prepare. Требование «канон обязан поменяться» для compressor заменяется publication identity; generic freshness остальных ролей не ослабляется. До already-done return compressor проходит ту же независимую проверку G2/publication/pin. Целая неизменная done-цепочка даёт verified no-op без state/journal/notify/dispatch/publisher; повреждённая часть/alias/manifest/pin/source/receipt даёт отказ и после done.

Consumer `_extract`, reuse и refresh получают список частей **из принятого manifest**, а не выбирают generation по glob/mtime. Glob используется только для обнаружения лишних stale файлов. Consumer packet сохраняет числовой порядок/все FileRef, полный несжатый acceptance с inventory как системный InputRef и full ReadRef ModelView; до emit Python полностью читает A/inventory и проверяет inverse и provenance по Б60.3.3. Все criteria/IDs/oracle/expected/source bindings доходят до роли несжатыми. Все bytes всех extract-частей, включая Python echo и inventory-only страницы, остаются в прежнем inline/FileRef контракте Б56 без обрезки; 3–5 КБ — цель содержательного резюме, не предел полного механически дополненного комплекта. N>12 разрешён; вместимость всего consumer проверяется по Б60.3.4. `extract_key` сохраняет прежние path/version/mtime/prompt_hash, дополнительно проверяется publication/acceptance binding; aggregate не включает alias дважды. Отсутствующий обязательный manifest не заменяется старым extract. Законные never-produced/без compress ветки Б56 сохраняются; сама producer-фаза получает absent/being-produced.

Законное последовательное замещение `TZ:compress → HF:compress` сохраняет accepted manifest A и его output refs в history, current указывает только B. Повторная проверка исторической A использует сохранённые immutable bytes/ref-свидетельства A и штатную цепочку замещения, а не требует, чтобы mutable canonical всё ещё был A. Для активной B всегда перечитывается canonical; отсутствие/порча активной B не маскируются history. Историческая A без сохранённых bytes/основания не получает PASS и не восстанавливается из B.

Перед новым prepare сохранить **полные** прежние context_packet/prepare/production/result/receipt/manifest bindings в существующей context_history, прежде удаления активных result/receipt. Recover/rework/accepted refresh сохраняют историю и counters; старые proof не принимаются для новой identity. Поздний response A после prepare B отказывает до canonical replacement/writer, даже при той же session/тексте. Повтор доставки уже принятого результата — verified no-op, не второй publisher.

Для compressor rc=143 не запускает generic artifact-based success/reconcile. Если целая publication/result/receipt уже была сохранена и независимо проверяется после выхода writers, внешний оркестратор использует обычный completion без нового send. Files-only, production без result, conflicting receipt — отказ/диагноз; backfill запрещён. Pre-manifest/старые публикации сохраняются как история; им не присваивается новый manifest по нынешним bytes. Не возникает нового historical exception Б59.

Accepted master refresh разрешён лишь по проверенному output прежней завершённой роли; источник изменения и сохранность прежней publication доказаны. Новый compressor получает свежий packet и соответствующий acceptance. Если принятой проекции недостаточно/требуется новая редакция pin, нужен предусмотренный утверждённый переход; пока его нет — явный блокер. Старый manifest/packet не исправляется, arbitrary source/prompt drift не проходит. Установка Б60 не снимает one-shot/turn limits и не разрешает второй recover той же пары.

### Б60.7 Отказы и неизменные защитные контракты

| Стадия | Обязательный результат |
|---|---|
| Packet/pin/source/scope/capability до prepare | Context rc=1; syntax rc=2. Backend/prepare/turn/publication/result delta=0; нет успешного marker/pin для частичного ввода. |
| Codex non-concrete model/effort | Rc=2 до prepare; ENV fallback/backend switch нет. |
| Native static/worker/provider/transport failure | Прежний rc=3/provider-fatal, без публикации/успешного receipt. Static route отказывает до SDK/send. |
| Native HTTP success без пригодного completion | Прежний rc=4/local refusal, не provider-fatal. |
| Rc=0 + настоящее structural/plain client fatal | Fatal приоритетен над текстом/каноном; нет publication/result/receipt, без retry/recover. |
| После успешного транспорта: unusable text/headers/coverage/source/pin/identity drift, publication I/O | Rc=4/local refusal с безопасной stage-диагностикой; прежний validator SystemExit тоже обрабатывается как локальный отказ. |
| Rc≠0/143 | Не публиковать новый ответ; только уже сохранённая целая цепочка отдельно проверяется внешним completion. |
| Result writer/readback failure | Rc≠0, нет половины success result/receipt; files/manifest не являются accepted result. |

Список FATAL_PATTERNS, non-recoverable provider-fatal, TERMINAL_KILL_RCS, timeout=3600s, session parsing/occupancy/pid=wrapper/G1–G6/MIG guard, пять recover-классов и budgets не ослабляются. Не переносить из старого candidate широкое игнорирование plain stderr при rc=0. Успешные JSONL quotes не fatal; error envelope до/после success и настоящий plain auth/429/503/timeout остаются fatal. Benign models-refresh исключение Б60.7 допускается только с точной воспроизведённой fixture: при её отсутствии NOT_RUN/FAIL, а не придуманная сигнатура или broad suppression.

### Б60.8 Проверка, установка и передача

Implementation allowlist и exact IAC/nodeids/roots/logs утверждаются HF:plan/REV:plan в рамках принятого задания. Candidate имеет проверенный baseline installed bytes с provenance, собственный baseline→HEAD commit/G3; import baseline не выдаётся за исправление. Runtime не git repo, git init в нём запрещён. Historical Б58/Б59 candidates read-only и целиком не устанавливаются. Если старый wrapper не принимает outputs без обхода guard, нужен адресный возврат, а не historical исключение.

До impl — требуемый полный набор T/IAC, required/actual/missing; после — отдельный HF:test каждого verify и полной suite из approved candidate, PYTHONDONTWRITEBYTECODE=1, PIPELINE_ERRORBUS_DISABLE=1, candidate PYTHONPATH, -B -m pytest -p no:cacheprovider. Негативы изолированы, executable stub пишет response/transport, runtime сам создаёт production/result/receipt. Installed новый процесс доказывает loaded paths/hash и capability smoke. Full green/helper grep не заменяет обязательный oracle.

Backup и rollback — Б15, docs-handoff связывает tested→installed manifest, ограничения и передачу. Для текущего CHANGE совместимость R0→R1 и порядок проверки/включения заданы Б61.4; лабораторный PASS не подменяет окончательный HF:test, docs или installed/load evidence. GATE:done требует все собственные AC-COMP, доставленный AC-report и preflight=0; чужая живая встреча/хвосты отменённых поездов не prerequisites. Новый допуск зависимому compressor использует existing exact подтверждение brief/basis и новый штатный packet/pin без backfill/reset; недостаток source-confirmation — missing input до prepare, не пробный compress. Б58/Б59 не возобновляются; чужие budgets/паузы/REV не изменяются.

**Применение Пути 1 в текущем BUGFIX.** После собственной REV:tz/TZ:finalize этой дельты архитектор пересобирает AC-list, HF-plan/IAC, companions и data-only handoff. План называет один существующий carrier consumer policy, точный path либо per-invocation operand, выбранный consumer/route, исходное значение, новое расчётное значение по правилу 90% Б60.3.4 и отдельное доказательство local load, область действия, применяющую фазу/владельца и пофайловый write-set. Приоритет — адресное применение без изменения defaults остальных ролей. Разрешение на исследование/проектирование не добавляет config path в текущий write_scope: применение допускается только в разрешённой будущей фазе после независимого согласования плана и fresh backup. Если поддерживаемый carrier требует общей policy или иных изменений сверх решения владельца, нужен адресный возврат, не расширение allowlist по умолчанию.

До HF:impl должны быть проверены публичные максимумы exact моделей и фиксированный расчёт 90%, effective resolution/loading выбранного carrier и вместимость по Б60.3.4 без преждевременного live install. Отдельная аттестация числового окна владельцем deployment не требуется; это исключение не заменяет tokenizer, route identity/setup и полный framing. Одних намерений измерить после dispatch недостаточно; если существующий разрешённый способ такой проверки недоступен, допуск остаётся закрыт. Для применения настройки сохраняются исходные bytes/mode/resolved path/dirty provenance (для operand — точная прежняя сборка вызова), backup, адресный rollback и проверка отсутствия влияния на остальные роли. Это не разрешение менять конфиг из TZ:patch/HF:plan или вызывать дополнительную роль для проверки окна.

IAC разворачивает проверки внутри существующих T08/T16/T17: положительный полный consumer на подтверждённой policy; отказ при неподдержанном/неприменённом значении, drift carrier/CLI/route/instructions/tokenizer, уменьшении любого резерва, пропущенной части/чтении или переполнении; отдельные equality/+1 fixtures не выдаются за authority. На HF:test и после адресного применения installed/load evidence нового процесса подтверждает совпадение **фактически действующей** policy/namespace/framing с проверенными refs, неизменность model/effort/backend и полноту доставки. Отказ/дрейф не заменяется старым PASS; принятие/установка прекращаются по существующему порядку. До GATE:done обязательны tested→installed связь, проверенный адресный rollback, все прежние T01…T18/AC-COMP и доставленный AC-report. Ни documentary approval, ни большее заявленное окно сами по себе CAP-R3 или runtime PASS не закрывают.

### Б60.9 Критерии и сценарии

AC-COMP-01…12 — класс S, обязательны в собственном полном BUGFIX ремонта публикации. Документная проверка не runtime PASS.

| AC | Что доказать | Действующие сценарии |
|---|---|---|
| AC-COMP-01 | Общая финализация обеих ветвей: rc=0 только с publication/result/receipt одного captured prepare; адаптеры не публикуют. | T01–T03. |
| AC-COMP-02 | Первичный A происходит из exact подтверждённого brief/basis до первого compressor; далее approved revisions. Pin/полные IDs/oracle/expected/source bytes закреплены до dispatch и несжатыми доходят до consumer через full ModelView; Python независимо читает полный A/inventory, проверяет inverse и added refs/payload. error-digest и model-capability остаются предметными inputs. | T04/T05; Б56. |
| AC-COMP-03 | Полный dispatch-bound final-message и доказанный запрет canonical/state/pin/master write ОС-границей codex. | T03/T06. |
| AC-COMP-04 | Чужой/старый/late response, новый prepare и source/pin drift отказаны до replacement/writer. | T05/T07. |
| AC-COMP-05 | Точное поколение/порядок/alias/hash/лимит/stale cleanup; Python paging полного oversized inventory с exact union локальных эхо и новая publication при identical text. | T08/T09. |
| AC-COMP-06 | Transport/text/I/O/state failure не оставляют пригодный success result/receipt/done. | T06/T10/T11. |
| AC-COMP-07 | Check/complete независимо перечитывают proof/files; intact duplicate no-op, corrupt already-done отказан. | T12/T13. |
| AC-COMP-08 | Recover/refresh/rework/rc143 не создают proof задним числом, сохраняют полную историю/counters. | T07/T13/T14. |
| AC-COMP-09 | Native model/retries/send/rc и остальные роли/guards сохранены; codex concrete model без ENV fallback. | T15/T16. |
| AC-COMP-10 | Реальные offline CLI-цепочки от принятого brief/init/stabilize, двух backend × двух producer-фаз до consumer, oversized inventory и accepted refresh. | T01/T02/T14. |
| AC-COMP-11 | Собственный backup/commit/G3, impl/test раздельны, loaded tested/installed hashes/smoke/rollback/scope доказаны; адресная consumer policy проходит доказательства и границы Б60.8. | T17/T18. |
| AC-COMP-12 | Abort/candidates/чужие state/budgets сохранены; новый допуск lock из exact brief/basis без цикла/backfill/предварительного сломанного compress. | T18. |

| ID | Вход / вмешательство | Обязательный oracle |
|---|---|---|
| T01 | Codex: новый полный CHANGE от подтверждённого исходного brief/source, штатные init/stabilize/emit строят первичный A; затем TZ:compress и законный HF:compress. Stub только final-message/events. | Реальные emit→invoke→publisher→result→check→complete→consumer emit. Dispatch=1/publisher=1/current result=receipt=1; wrapper вышел до complete. Все bindings/parts/FileRef/metadata совпадают. |
| T02 | Те же первичные трассы от подтверждённого brief/init/stabilize native через настоящий worker с mock HTTP; заранее изготовленный approved pin не заменяет bootstrap. | SDK send=1/retries=0, publisher=1 именно в общем finalizer; весь consumer комплект. Mock publisher не зачёт. |
| T03 | «Файл записан», короткий stdout; попытки stub/child писать canonical/state/pin/master/соседа/по alias. | Нет fallback; ОС отказывает записи, защищённые refs/bytes неизменны. Полный response отдельно проходит; Python publisher вне namespace записывает canonical. |
| T04 | Нет pin и утверждённого входа для первичной фиксации; чужой pin/revision/basis; changed oracle/expected; duplicate/missing/extra ID; invalid JSON/unknown keys/covers/symlink; fault snapshot→pin commit. | Отказ до prepare/send/turn, нет half pin/marker, orphan недопущен. Законная первичная фиксация из source-confirmed brief проходит отдельно; plain approved=true/подмена source-span/поздний handoff без подтверждения, fabricated oracle/verify и потеря одного из восьми пунктов lock отказываются. Проверена пересборка exact A; pin не перезаписан; полные семейства ID и suffix передаются несжатыми. Дополнительно: inverse(ModelView) восстанавливает exact A; changed criteria/derivation/phases, missing/extra поля, altered inventory/origins, подменённые acceptance_ref/approval_ref/confirmed_payload и fifth control-purpose отказываются. Error-digest/model-capability нельзя исключить из предметной проекции. |
| T05 | Drift emit→invoke и dispatch→publication: packet/render/prompt/master/hash/size/mtime/resolved target/core/overlay/pin/scope. | До prepare delta=0; после dispatch rc=4 до replacement/current result/receipt. Разрешённый scope не разрешает другой source. Дополнительно: drift ModelView/inventory_ref/error-digest/capability/route/CLI/tokenizer/instructions до prepare даёт delta=0; изменение captured source operands после dispatch отказывает до replacement и отдельно до result. Текст digest без принятого ref, missing/duplicate digest, oversize >16384 bytes и повтор E-ID отвергнуты; errors=null допустим лишь при отсутствии этого входа в задании. |
| T06 | Missing/empty/invalid UTF-8 response, неверные семь совокупных секций Б60.5 (missing/duplicate/перестановка), symlink/dir/FIFO/device/read exception. | Быстрый rc=4 без FIFO hang/fallback; прежний canonical/proof сохранён; finally cleanup на success/отказах/exception. |
| T07 | Задержанный ответ A, recover/new prepare B; по одному меняются packet_id/wrapper/turn/started_at/session bindings. | A не публикуется как B; прежние полные bindings в history; counters не сброшены. |
| T08 | Single/2/N=12/N>12, 3→2→1/1→3, identical response; готовые части 5120/5121 chars и raw payload 5121; полный oversized inventory актуального DevWorkflow master (включая REV witness), семь секций всего payload по Б60.5. | Точный набор/numeric order/alias/manifest boundaries/hash/chars; alias не удваивается. Identical bytes допустимы только с новой настоящей publication. Oversized полный inventory успешно разбит Python; exact union локальных эхо полон, payload восстановлен побайтно. Готовая часть 5121 отказана, raw payload 5121 допускает несколько частей. Дополнительно: два положительных exact Request/1.2 (Codex stdin/native user content) на полном окончательном master с полным inventory, inverse и digest; mocks сверяют реальные bytes/hash и применяют доказанный размерный gate. Отдельно полный consumer render/ReadRefs/echo witness. Подтверждённые profile/reserves достаточны; synthetic или pre-prepare refusal не закрывает положительную реальную вместимость. Сохранены E-ID/ссылки/статусы digest в семи секциях, точное имя API / CLI. |
| T09 | Missing/reordered/duplicate headers, inconsistent N, nonwhite/white prefix, malformed 1/1, потерянный/лишний/дублированный echo assignment, неделимый элемент > ёмкости собственной страницы; symlink/non-regular/stale-directory targets. | Плохой ответ/повреждённый canonical отказан целиком, пробельный prefix допустим; ничего не отрезано. Неделимый oversized элемент отказывает до prepare/send/turn; большой совокупный inventory сам по себе не причина отказа. Targets не читаются/не удаляются рекурсивно, сосед/target symlink неизменны. |
| T10 | Rc≠0/143 до publication; JSONL error до/после success при rc=0; genuine plain auth/429/503/timeout и success quote. | У ошибок нет publication/current receipt. Quotes не fatal; benign warning только воспроизведённой fixture. Нет второго dispatch/send. |
| T11 | Fault stage/каждого replace/unlink/manifest/proof/result writer/readback; drift между проверкой и commit. | До replacement прежние bytes целы; после возможна physical partial, но check/complete/consumer отказывают. Нет half success receipt; проверен state rollback; hard kill не объявлен crash-atomic. |
| T12 | После success по одному изменить part/alias/manifest order/hash/pin/source/receipt/result.packet_id/prepare. | Прямые check/complete отказывают по сохранённым bytes/bindings. Ни backend/publisher, ни достройки proof из complete нет. Дополнительно: check/complete независимо повторяют inverse и проверку added fields/источников ModelView; сохранённый boolean не заменяет чтение A/inventory. |
| T13 | Intact repeat complete done, затем corrupt done; rc143 files-only и целая ранее сохранённая цепочка. | Intact verified no-op, corrupt отказ до early rc0. Files-only не accepted; сохранённая целая цепочка принимается ordinary complete без нового send/publication. |
| T14 | Разрешённый master output/accepted refresh и утверждённый compressor-only A→B pin transition; отдельно arbitrary source/prompt drift, иной A/неутверждённый B и recover/rework. | Положительная трасса нового packet/pin/publication/consumer проходит; старые manifest/history сохранены. Mixed/неутверждённая revision отказана, counters не сброшены. Первичный A и поздний B с AC/IAC различаются; законное замещение canonical сохраняет проверяемую A history, порча активной B отказывает. |
| T15 | Native regression Б60.4 и существующего `tests/test_context_packet.py` (H01…H10), static model/key/base, invalid completion/HTTP/provider/worker fault. | Прежние priority/static refusal до SDK, send=1/retries=0/no fallback, rc=3/4; HTTP-success empty не provider-fatal. Дополнительно: native user content byte-equal C(Request/1.2), HTTP envelope и полные master/core/overlay/ModelView/error bytes сохранены; authority/tokenizer/route/framing/reserves неизвестны либо drift — локальный pre-prepare отказ без SDK/send, прежний static/provider rc=3 не переименован. |
| T16 | Codex null/empty/white/non-string/native marker/explicit concrete, другой ENV model; обычные роли/parser/MIG/occupancy/G1–G6/turn/recover. | Non-concrete отказ до prepare; ENV не участвует, concrete одинаков в prepare/argv. Полная suite отдельно, прежние guards зелёные. Дополнительно: exact Codex stdin C(Request/1.2), Request/1.0 и /1.1 не fallback; CapabilitySet unknown/duplicate/wrong pair, неподтверждённый tokenizer/CLI/instructions, zero reserves и input overflow отказываются до prepare. Equality/+1 проверены synthetic profiles отдельно от двух реальных положительных CAP-R3; нет download/provider probe/нового budget engine. |
| T17 | Candidate/installed новые процессы, CLI и confinement smoke; baseline→HEAD/backup/required-actual-missing. | Loaded bytes = tested/installed manifest, собственный commit/G3 и весь verify набор; stub/live_provider=false указан, живая очередь не fixture. |
| T18 | Scope/abort/history/handoff и адресный rollback. | Б58/Б59 aborted/candidates read-only, чужие state/journal/паузы/counters неизменны. Изолированный двойник lock начинает с его настоящего brief/8 пунктов/истории без pin; новый source-confirmed допуск → A → обе ветки publisher/complete/consumer проходит штатными writers. Нет старого proof, reset/recover или предварительного сломанного compress. Откат только собственного write-set. |

HF:plan развернёт группы в exact executable nodeids/CLI traces и paths/logs, включая позитивы и негативы. Required−actual=∅, дубли/extra объяснены. Наличие теста/helper и общий regression PASS не заменяют обязательный oracle.


## Б61. Внедрение консолидированного master и раннего scope guard — 09.11.2026

### Б61.1 Основание, результат этой фазы и границы

Текущий CHANGE — `vnedrenie-konsolidirovannogo-master-tz-devworkfl`. Основание — принятый `brief.md` от 09.11.2026 с распоряжением Саши «Берем тз в разработку по канону. Нужно внедрить скорее данный механизм в прод работу.» и независимый RESEARCH `master-tz-konsolidatsiya-dubli-protivorechiya`. Его `evidence/master-next.md` с SHA-256 `9edbd1a20269e4b09ae05ea2559e0abca587550e6d0b6753d05b04b9e2cface9` получил собственный `REV:report=APPROVE`. Это основание консолидации, а не заменитель `REV:tz`/`REV:plan` текущего CHANGE и не runtime evidence.

На текущей `TZ:patch` по packet `c6036e58145b828eeed20353429793b9f39dcea3466d395ed777b9036d9dd653` публикуются только этот master draft, канон `TZ-patch.md` и собственные документные snapshot/diff/FileRef/verification/handoff в каталоге текущего слага. Предыдущий master сохранён полностью до замены; согласованный нормативный корпус RESEARCH сохранён, служебные отличия перечислены в документном diff. Требования консолидации проходят независимую ревизию этого поезда. Реализация, HF:test, установка, фактическая загрузка и production runtime на этой фазе **NOT_RUN**.

`MAIN_TZ_INVENTORY.md` и целевой `TZ/DevWorkflow/appendix_history_20261109.md` отсутствуют в write_scope текущего packet. Поэтому реестр и целевое приложение сейчас не записываются; существующее `evidence/appendix-history.md` RESEARCH сохраняется неизменным. Точный data-only handoff передаёт их будущей разрешённой `TZ:finalize`: приложение переносится побайтно с проверкой исходного hash, реестр синхронизируется под существующим lock по фактической финальной редакции master. Proposal не является применением. До разрешённой записи обоих документов полная документная финализация не завершена. Резервный снимок этой фазы находится внутри разрешённого слага; штатный внешний backup выполняется только фазой с соответствующим scope.

История, старый master snapshot и приложение не включаются в ordinary inline, handoff.inputs, must_read или compressor source. Их сохранённые hashes/местоположение — адреса для механики архивации и сверки, без передачи тел обычной роли. Следующие роли читают новый master и свои обязательные входы. Старый extract текущего слага не объявляется свежим после смены master: новый пакет/штатный refresh выполняет внешний оркестратор с сохранением истории и счётчиков; текущая роль не редактирует extract или принятый packet.

Не менять боевой код/tests/скиллы/конфиг, process state/journal/queue, accepted packet/sidecar/prepare, чужие результаты/паузы/counters. Не вызывать next/complete-phase/recover/invoke-role и не мониторить собственный wrapper. Разрешённый master output принимает внешний оркестратор после выхода роли по входному snapshot и output evidence Б56.6 п.5. Отказ guard не разрешает обход или повтор неизменного вызова. **[NEW-ENTITY, требует согласования Саши]**. No new service, database, queue, channel, cron, budget engine or global mutex. Gateway не рестартовать; кроны только после «ставь кроны».

### Б61.2 Объём внедрения в существующий процесс

1. Выполнить разрешённый документный переход от прежнего master к консолидированной редакции с backup, отдельной историей и inventory по Б15. Сохранить тематические якоря и владельцев исторических AC/IAC; перенос в историю не отменяет их и не включает автоматически в AC нового CHANGE. Последующая адресная нормативная дельта Б61.4 имеет собственные diff/REV/finalize; её не выдавать за первичный служебный переход к RESEARCH-корпусу.
2. Реализовать общий ранний guard Б56.6 и расширенные AC-PKT-04/06 в существующем `pipeline_context.py`. Callers: `cmd_recipe_add` до persist предлагаемого recipe; emit до публикации packet/sidecar/Markdown/успешного marker; invoke до prepare/turn/backend. Сохранить последующую проверку фактического результата. Полный норматив guard остаётся только в Б56.6.
3. На HF:plan построить адресную матрицу всех действующих требований консолидированного master, в том числе Б18–Б27, Б55, Б56 и Б60: норма/применимый oracle → фактический код/инструкция/загрузка → проверенное reuse либо пробел → IAC/path/verify/depends/covers и фаза применения. Наличие старого APPROVE/done/общей зелёной suite не является подтверждением готовности. Каждому пробелу требуется реализация и проверка в разрешённом объёме; противоречие границам возвращается архитектору/ревизору до impl. Нельзя молча объявить незавершённую норму выполненной или вынести обязательную часть за пределы brief. Отменённые адресные Б58/Б59, бюджеты/global mutex и предметные контракты приложения не возобновляются.
4. Исполняемую процедуру `dev-workflow` и references привести к этой редакции по Б55.9/55.10: одна процедура, точные MUST-read/каноны, отсутствие штатного чтения истории. До правок план проверяет реальную загрузку и потребителей с учётом адресного порядка доказательства Б61.4; личные SOUL/AGENTS/USER/MEMORY не входят автоматически в write-set. Их изменение возможно только если явно покрыто принятым заданием и разрешённым scope соответствующей фазы. Код/скилл выпускаются согласованно; restore и проверка конечной загрузки выполняются штатной ORCH-фазой. YAML/default backend/секреты не меняются ради этого guard.
5. Guard не добавляет LLM-preflight, обязательное чтение истории/master сверх Б12 или копию таблицы контракта в prompt. Полный write-set, nodeids/CLI-сценарии, paths/logs, baseline/backup/G3, проверка installed версии и rollback определяются HF:plan/REV:plan до HF:impl. Проверки изолированы от живой очереди; отдельный HF:test не подменяется документным аудитом этой фазы.

### Б61.3 Приёмка текущего CHANGE

Все критерии ниже — класс S. Это обязательный объём AC-list текущего поезда вместе с относящимися проверками AC-PKT-04/06 и применимыми oracle матрицы HF:plan. Исторические личные AC других слагов сохраняют владельцев. NOT_RUN/FAIL не закрывает собственный GATE:done.

| AC | Наблюдаемая проверка / evidence |
|---|---|
| AC-CONS-01 | Исходный master восстановим побайтно; первичный переход содержит одобренный RESEARCH-корпус без неоговорённых нормативных изменений. Его служебные metadata/статус/границы и Б61 перечислены в exact operations/diff; обратная сборка первичного перехода даёт точный hash одобренного проекта. К текущему master ведёт отдельная цепочка решения Б61.4 → разрешённая нормативная дельта → собственные REV:tz и TZ:finalize; старый APPROVE не утверждает новую норму. Обе цепочки проверяемы, версия только во frontmatter. |
| AC-CONS-02 | Итоговое приложение истории byte-equal согласованному источнику, исходник сохранён. Inventory под прежним lock отражает фактические version/date/status/hash master, включая разрешённую дельту Б61.4. Обычные packet/render/ReadRef/InputRef и compressor source исключают историю/старые snapshots; действующие ReadRef адресуют секции задания, а не последний чужой БNN. Есть положительная CLI-трасса следующей роли на новой редакции и штатный refresh при drift; прежний extract не принят как свежий. Evidence первичного перехода не переписывается. |
| AC-CONS-03 | AC-PKT-04: RESEARCH с добавляемым REV:report отказывает на missing inputs/outputs/write_scope, omitted/optional/wrong canonical, любом output вне scope, sibling prefix и symlink/parent escape до записи recipe-add либо публикации emit. После исправления разрешённого контракта добавление/emit проходят. Future RS-analyze допустим при структурном recipe-add и обязателен при emit REV; lawful empty inputs и ещё отсутствующий output проходят. |
| AC-CONS-04 | AC-PKT-06: изменение относящейся к фазе проекции выбранного контракта/recipe между emit и invoke отказывает до prepare/backend; HF-plan с неполным контрактом не получает fallback на brief. Drift state/контракта перед persist/publication отказывает. На ранних отказах packet/sidecar/Markdown/state/journal/context-used/prepare/turn/result/receipt неизменны; sends=0. Исправленный контекст допускает один штатный вызов; post-invoke output/freshness проверки сохранены. |
| AC-CONS-05 | Общий verifier вызывается всеми тремя callers; изолированные traces покрывают HF:compress, MIG:block-k с собственным accept, set-case и rework без новой роли/фазы. Sirene/gates не получили LLM-контракт, завершённая история не переаттестуется. Положительные маршруты и регресс G1–G6/G2/G3/receipt/occupancy/native/codex/turn/recover сохранены. Полный набор oracle утверждён в IAC до кода. |
| AC-CONS-06 | Измерены размер исходного и итогового master/обычного render, источник tokenizer/метрика указаны. Guard работает локально в Python; нет дополнительного provider/LLM-preflight, обязательных чтений или inline-копии контракта/истории. Отказ вызывает ноль оплаченных dispatch. Проценты размера документа не выдаются за измеренную экономию runtime tokens/cost. |
| AC-CONS-07 | Матрица Б61.2 п.3 покрывает действующие нормы и применимые oracle без потери требований; у каждого есть конкретное подтверждённое reuse либо выполненный IAC на испытанной/установленной версии. Процедура/контекст проверены на реально загруженных bytes по Б55 с порядком Б61.4, compressor — по Б60, когда соответствующая граница затронута/не подтверждена. Все обязательные test-stage oracle, включая end-to-end fallback/availability, пройдены до окончательного HF:test PASS. Component/offline/installed/live/production статусы раздельны. Все обязательные пробелы закрыты до GATE:done; исторический PASS не присвоен текущей версии. |
| AC-CONS-08 | Свои impl/test раздельны, утверждены актуальные план/REV и backup, есть собственный committed write-set/G3, tested→installed hashes, конечная загрузка/restore, installed smoke и адресный rollback. Переход R0→R1 проверен по Б61.4: prep exit → ORCH pilot/freeze → отдельный reader → окончательный PASS → docs → live install; PREPARED/partial фазу не закрывает. Baseline/after подтверждают разрешённый scope и сохранность process state/чужих результатов/пауз/counters; нет новых сущностей/cron/restart/секретов. Собственный AC-report с фактическими проверками доставлен до обычного GATE:done. |

Технический факт этой TZ:patch: установленный `_outputs` ещё создаёт default canonical, а `_in_scope` вызывается из `check_result_outputs` после роли; `cmd_recipe_add` сохраняет recipe без общего guard. Read-only инспекция подтверждает необходимость изменения и не является runtime воспроизведением/PASS. Конкретные source refs и диапазоны переданы в TZ-patch.md. Полный HF-план этой фазой не подменяется.

### Б61.4 Адресный порядок доказательства continuation и переход R0→R1 — 10.11.2026

Область — только CHANGE `vnedrenie-konsolidirovannogo-master-tz-devworkfl`. Основание пересмотра требований по Б55.5 — решение Саши от 10.11.2026 в `dev/vnedrenie-konsolidirovannogo-master-tz-devworkfl/ARCH-DIAG-REV24-LOADER-FACTS.md`, §9 (SHA-256 `0c4f00b0bd3b429991981e655137d96c33eb6a9b520ebf7b7bbdc9daf8a0aed1`): выбран Путь 2 для REV24-01; вариант A для REV24-02 принят в §3. Точное задание дельты — HF-plan.md §7.1; независимая REV:plan rev31 сохраняет условие REV24-01-TZ до реализации. Это адресное изменение момента доказательства и порядка включения, без отмены AC или общего переноса требований других задач. Б61.1 описывает первичный переход, его evidence остаётся отдельным неизменным основанием.

1. **Проектирование и допуск реализации.** Подтверждённые loader/candidate-load/primary facts справки достаточны для проектирования и независимой `REV:plan` с явной зависимостью REV24-01-TZ; повтор того же transport факт-пакета до review не требуется. Загрузка candidate через поддерживаемый Hermes `read_file` по абсолютным путям с pagination не объявляется включением candidate в каталог loader. После `HF:impl` и prep перед P1 оркестратор загружает final committed skill/references в принимающий Hermes-контекст, фиксирует source/resolved paths, hashes, session/time и приоритет по Б55.9/55.11; при новом ходе/смене bytes повторяет сверку. До `HF:impl` обязательны разрешённые `TZ:patch → REV:tz → TZ:finalize`, запись master/inventory, штатный refresh при drift, согласованная актуальная связь master/плана/IAC/REV/packet и fresh backup. Прежние approvals/packets не исправляются; старый metadata-only brief не расширяет права этого вызова.
2. **Момент transport proof.** Оставшиеся end-to-end fallback/availability проверяются после выхода `HF:test` prep-wrapper в испытании P1…P5 по Б55.10/55.11 до окончательного `HF:test` PASS. Требуются настоящий completion send→receive→действие процедуры; отдельный lost-primary→доставленный wake→продолжение; unchanged doorbell без LLM; ожидание лимита и возобновление той же фазы по подтверждённой доступности. Поддерживаемое событие или существующий одноразовый отложенный wake проверяются фактически; известный срок берётся только из подтверждённого источника, при неизвестном сроке нужен внешний подтверждённый сигнал. Нет provider polling, reset, смены аккаунта/backend или нового scheduler/consumer/канала/cron. Печатный WAKE, local note, job status=ok и mock receive доставку не доказывают. Неуспех или отсутствие обязательного доказательства оставляет AC-RP-06/07/16 FAIL и фазу незавершённой.
3. **R0 и R1.** R0 — установленный runtime, принимающий текущий поезд; R1 — собственный committed candidate из HF:impl. До окончательного `HF:test` и `HF:docs-handoff` оба настоящих вызова HF:test и их обычное принятие/complete выполняются через R0; R1 CLI работает только в изолированных lab roots. Подготовительный отчёт PREPARED/partial не разрешает complete; на R0 это обеспечивает внешний оркестратор, без утверждения, что старый runtime уже имеет новый guard. После выхода prep-wrapper проверяемая изменённая процедура сама исполняет пилот; драйвер подаёт факты/управляемые результаты и собирает трассы, не выбирает переходы. После прекращения пилота отдельный последовательный reader на той же HF:test проверяет evidence. Текущая задача удерживает поток; второй живой содержательной роли и других боевых поездов нет. PREPARED/VERIFIED — поля канона отчёта, без новой process-фазы/status/schema/CLI.
4. **Внешний freeze на R0.** До второго prepare оркестратор сохраняет полные прежние packet/prepare/result/receipt bindings и accepted output bytes prep-вызова, затем замораживает ровно восемь regular UTF-8 файлов `evidence/B55-pilot-v23/` текущего слага: load.json, handoff.json, orchestration.jsonl, transport.jsonl, cli.jsonl, managed-results.jsonl, snapshots.json, metrics.json. Их полный состав и пути закреплены IAC.verify. Handoff содержит refs семи остальных; собственный ref handoff и SHA всего набора фиксируются внешней freeze-сверкой, без self-reference. R0 reader читает весь набор по фиксированному IAC.verify readset; оркестратор независимо сравнивает все восемь FileRef непосредственно до и после reader. Это внешние immutable observations, без backfill state.context_history, ручных additions к packet/prompt или выдуманных InputRef/ReadRef. Missing/mixed/modified/nonregular/extra child либо нарушение хронологии дают READ FAIL и запрет приёмки; reader не достраивает пилот и не меняет frozen evidence.
5. **Совместимость до установки.** IAC G10 доказывает три изолированные трассы: R0→R0 prep/reader с внешним полным freeze и честно показанным отсутствием нового guard; R1→R1 с отказом complete PREPARED, восемью full ReadRef в штатном reader packet, отказом missing/changed child до prepare и программным сохранением полной history; R0 завершённый результат→R1 check/new invoke→адресный runtime rollback с сохранением state/history. Существующий единственный context owner материализует R1 ReadRefs без новых полей packet; до замены active bindings полная history сохраняется штатным writer. Новые защиты R1 не служат предпосылкой собственной установки и не приписываются R0. Исходные accepted bytes/counters неизменны. Неуспешная совместимость не лечится ручным proof или ранним live install.
6. **Окончательное принятие и выпуск.** Окончательный VERIFIED/PASS требует FULL/PROBE/G10, реального пилота, READ всех 16 test-stage AC-RP и всех остальных обязательных test-stage IAC. Затем — docs, адресная установка tested committed bytes на ORCH:shared-state, штатный restore, конечная фактическая загрузка, installed smoke/RELEASE и доставленный общий AC-report до GATE:done. Первый новый вызов после установки использует R1 с полными действующими guards Б56/Б60. Accepted HF:test output не переписывается при release; отчёт и доставка принадлежат оркестратору. Component/offline/installed/live/production статусы сохраняются отдельно; обязательный FAIL/NOT_RUN блокирует соответствующее принятие.
7. **Две документные цепочки.** Первичный approved RESEARCH→консолидация доказывается прежними immutable operations/diff/REV/finalize. Новое решение §9→эта разрешённая нормативная дельта→собственные REV:tz/finalize→актуальные master/inventory/refresh доказывается отдельными refs/diff. Обратная сборка дельты восстанавливает прежний master; к нему применимы прежние evidence, а текущие нормативные bytes не объявляются byte-equal прежнему RESEARCH-проекту. AC-CONS-01/02/07/08 сохраняют полный объём с этой цепочкой. История/appendix/старые master snapshots не передаются обычным ролям. Новый extract/acceptance при необходимости получает только штатный подтверждённый переход Б56/Б60, без fabricated pin/manifest и без reset.
8. **Граница отказа.** Если пилот не подтверждает разрешённый transport, Путь 1 — адресно исправить доказанный дефект существующего механизма внутри утверждённого scope с backup/rollback и повторной проверкой; Путь 2 — вернуть точное противоречие transport/scope архитектору и ревизору для разрешённой нормативной/пофайловой дельты. Рекомендован Путь 1 при локальном разрешённом дефекте; необходимость менять jobs/core/чужой binding или вводить механизм требует Пути 2. Ни один путь автоматически не расширяет allowlist. Это исключение не разрешает ранний live install, подмену доставки, пропуск AC, правку process state/accepted packet/prepare/counters или восстановление пауз. **[NEW-ENTITY, требует согласования Саши]**. No new service, database, queue, channel, cron, budget engine or global mutex. Gateway не рестартовать; кроны только после «ставь кроны».
