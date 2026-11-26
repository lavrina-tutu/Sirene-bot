---
name: dev-transport-admission
description: "Допуск транспорта C/I/R в поезде: цепь звеньев до пилота"
version: 0.1.1
author: sirene
license: private
metadata:
  hermes:
    tags: [dev-workflow, transport, iac, pilot, hermes]
    related_skills: [dev-workflow, webhook-subscriptions, hermes-feature]
---
# Допуск транспорта C/I/R в поезде (предпилотные IAC)

## When to Use

Используй, когда в dev-поезде надо доказать транспорт wake/completion (критерии C/I/R) до запуска зависимых испытаний/пилота, проектировать script-only watchdog или webhook-событие возобновления, или ревизовать допуск «механизм работает» против «экземпляр установлен и пришёл». Триггеры: «транспорт», «страховка/возобновление», «IAC-16.pre», «doorbell», «webhook route», «доставка wake/completion».


Тема: доказать транспорт wake/completion прежде, чем запускать зависимые F/пилоты. Применимо к любым HF-поездам dev-workflow с транспортом (doorbell, wake, completion, webhook).

> Примечание окружения: канонический дом этой темы — `devops/dev-workflow` (SKILL.md + references), но в текущем окружении запись в него падает «Skill not found in active profile» (коллизия tier-резолва, см. `skill-write-probe`); этот скилл создан отдельно как рабочий хост процедуры. При устранении коллизии содержимое слить в `dev-workflow/references/transport-admission.md` и удалить.

## Полный допуск — цепь звеньев

Документированный механизм ≠ работающий экземпляр ≠ источник разрешения ≠ адресный receiver ≠ квитанция. Предпилотный gate (IAC-16.pre) = load ∧ C ∧ I ∧ R; отсутствие ЛЮБОГО звена — FAIL готовности, зависимые испытания (F07/F14/F15 → P1…P5) не запускаются.

НЕ заменять звено: названием механизма из доков, paused/local staging, HTTP 200/ack, mirror, outbound message-id, queued/claimed admission, cache файлом (cache = последний выданный stdout, не ACK).

Типовые звенья: публичный producer/параметры → экземпляр (actual id) + полномочие (permission ref/SHA) → route (реальный listener, не только конфиг) → входящий receiver ТОЙ ЖЕ проверяемой процедуры (load/owner/история) → исходный receive receipt (event/process/время).

## Нативные механизмы Hermes

- **I (страховка)** — script-only cron watchdog: `no_agent=true` (0 токенов LLM), тикер gateway 60с, schedule «* * * * *». Изменение fp → WAKE-вывод; unchanged → пустой stdout ИЛИ явный `wakeAgent=false` (непустой stdout доставляется). Script-root gate: скрипт обязан лежать в `<active-home>/scripts/` (resolved path), symlink наружу не проходит. Имя занято чужим — стоп, не перезаписывать.
- **R (возобновление после квоты)** — ДВА независимых способа, выбирается по наличию внешнего источника. Смена backend/model/account для обхода квоты запрещена: `fallback_model`/credential pool НЕ принимаются как resume; scheduler `hermes resume`/catch-up возобновляют расписания, не квоту роли.
  - **Через внешний webhook route** (когда есть реальный producer): POST с HMAC V2 (Timestamp+X-Request-ID+Signature), payload c scope/wait_evidence/availability. NATIVE agent-mode webhook создаёт ОТДЕЛЬНУЮ session identity (profile, route, delivery_id) — не текущую сессию; `deliver-only`/`mirror` отправляют текст, вход процедуре НЕ дают.
  - **Через независимый script-only R-probe** (когда внешнего producer нет — Саша прямо разрешает сделать независимый опрос): подробная схема, два сценария по известности периода, авто-подъём крона только на время инцидента, тихий monitoring, человеческое касание — см. `references/r-probe-independent.md`. Ключевое: raise-on-demand (крон существует ТОЛЬКО при встреченном отказе), один реальный probe-запрос к тому же endpoint/provider/model/account/limit (не HEAD/health/истечение времени), успех ≠ достаточно квоты для большой роли.
- **Источник фактов** — docs с этой машины блокируются sandbox; SoT точного API/поведения — локальный checkout `/home/tkachenkoav/hermes-agent` (read-only): cron parser/script gate/runner/delivery, `gateway/platforms/webhook.py`, bot-chat delivery. Код доказывает наличие возможности, а не то, что она уже образует разрешённый адресный маршрут.
- **Разрешение**: создание cron/webhook/script — новая сущность, явное согласование Саши. Полномочие снимает запрет ровно в перечисленном объёме (один job + один route); повторное «ставь кроны» для него НЕ нужно; иной канал/receiver/смена контекста — новый согласованный объём.
- **Полномочие PRESENT ≠ допуск**: полномочие разрешает установку, но не даёт PASS транспорта. После paused/local установки компонентов I/R по-прежнему FAIL readiness, пока нет адресного receiver (та же процедура/load/owner/история), внешнего producer и исходных receipts. ADJUST архитектора после полномочия — это нормально: разрешение канала ≠ подтверждение входа. Не объявлять pre готовым только потому, что script/job/route существуют.
- **Фактический persisted id receiver не выдумывается — он читается** из роутинг-индекса `~/.hermes/sessions/sessions.json` (файл помечен LEGACY MIRROR; primary — `gateway_routing` в `~/.hermes/shared-state.db`). Ключ `agent:main:telegram:group:<chat_id>:<thread_id>` → поле `session_id`. Совпадение этого session_id с текущей процедурной сессией/контекстом поезда превращает `cron local:<session_id>` из «кандидата» в допускаемый адресный вход I wake/R resume. Это read-only lookup, не создание сущности; до него адресный receiver — FAIL, а не предмет архитектурной догадки. НЕ подставлять session_key Telegram или выдуманный id вместо прочитанного persisted session_id.

## Скрипт-детектор: root gate

Если детектор дёргает публичный CLI (например `pipeline.cli doorbell`), он обязан сверять root тем же путём, что CLI: тот же `ECOSYSTEM_CONFIG_PATH`, тот же loader (`usertools_config`), `DEV_STATE_ROOT` из YAML (env override НЕ применяется — удалять наследуемый env с этим именем). Resolved YAML root = resolved binding root, иначе — явный отказ (exit 2, stderr-диагностика, stdout пуст) ДО fingerprint и ЛЮБОГО cache/lock/temp I/O. Только после равенства — scope из сверенного root и subprocess с timeout.

Тесты root gate: A/B (два существующих root) → отказ без subprocess/cache; A/A и B/B → changed/unchanged с раздельными cache; relative/`~`/symlink через resolve; missing/invalid/disabled YAML → отказ. Проверять отсутствующий и существующий cache; inherited env с именем YAML-ключа не спасает mismatch.

## Процесс: архитектор → ревизор → backup → impl → install → решение receiver → pre

1. Решение по спорному пункту (разрешён ли механизм, объём полномочия) — архитектору С ПОЛНЫМ КОНТЕКСТОМ (мастер-ТЗ SHA, план SHA, диагноз, факты, документация/сообщество); оркестратор рекомендаций не даёт.
2. REV-цикл: каждое изменение плана — новая итерация + независимый REV:plan нового SHA; REQUEST-CHANGES = адресная правка архитектора → повторная REV. Повтор замечания дважды подряд — стоп до диагноза.
3. После APPROVE: HF:backup (before.json: absent-before, свободные имена, permission ref; приватный архив с mode 0700/0600, проверка извлечения) → HF:impl (готовит компоненты; установку делает координатор) → paused/local staging через native cron create → адресное решение ingress/source (отдельное согласование) → активация → полный pre. Конкретный рецепт установки — `references/install-staging.md` (script/binding в active-home/scripts с mode, readback SHA, literal cron create, job-id из реального ответа, install.json с null/NOT_INSTALLED).
4. Квитанции: отсутствующий экземпляр = `NOT_INSTALLED`, поле = null, не выдуманный job-id/event-id/время. Вердикт APPROVE не снимает FAIL готовности и не создаёт квитанции.
5. Прогон процедурных сценариев F07/F14/F15 и P1…P5 делается на изолированном `DEV_STATE_ROOT` с fixture backend вместо платных ролей (реальный pipeline CLI, оркестратор решает, драйвер подаёт входы). Полный рецепт: структура, изолированный `EcosystemConfig.yaml`, парсинг `slug:`/`phase:` из emit-промпта, control-файлы сценариев, слои evidence под `test_b55_pilot_evidence.py` — `references/pilot-isolation.md`.

## Compressor-публикация и write_scope

Закрытие compressor-фазы после агента — не complete по факту записи `extract.md`, а штатная публикация через `publish_validated_extract` с полным AC/IAC-покрытием и пересчётом `output_snapshot` (иначе G2 `result output changed`). write_scope: каталог без трэйл-слеш не допускает подфайлы — писать каталоги со слешём + точные пути канонов. Полный рецепт — [references/compressor-publication.md](references/compressor-publication.md).

- **TZ:compress/HF:compress — ролевые фазы (compressor), не sirene-фазы.** Их нельзя закрыть оркестраторным «написать extract и complete»: G2 требует accepted context packet (prepare/result/receipt). Штатный путь — `emit-prompt` → `invoke-role --role compressor --slug … --phase …` (оба флага обязательны; без них — `invoke-role requires --slug and --phase`), затем complete через `compressor_metadata`.
- **Пустой `write_scope` в packet compressor-фазы = нет прочитанного fenced `handoff-contract` в `brief.md`** (авто-расширение scope есть только для compress/diagnose, но контракт всё равно должен существовать). Агент тогда честно отрабатывает полный проход и пишет `extract.md`, а полная публикация и приёмка падают (`extract_production` отсутствует / `output outside write_scope`). Диагностировать по packet: `boundaries.write_scope == []`. Фикс: завести `brief.md` с fenced `handoff-contract` (write_scope/outputs для compress), сделать СВЕЖИЙ `emit-prompt` (новая packet_id), затем повторный `invoke-role` — старый неопубликованный artefact не легализуется задним числом.
- **Перед заведением нового ремонтного поезда на уже известный дефект — искать существующий/aborted поезд и мастер-пункт (напр. Б58) на тот же класс** (поиск `ls dev/* | grep <тема>`, затем `_state.json` статус aborted/done, journal-причины): готовый согласованный проект (TZ-patch/HF-plan/REV-plan) может лежать в aborted-поезде и быть реанимированным с адресными дополнениями вместо дубликата. Запрос «почему отменён» до создания нового.

## Ловушки CLI и готовности очереди

- `suggest-slug` печатает JSON `{"slug": …}`, а не голый slug: передавать его вывод прямиком в `init --slug` нельзя — создастся директория с именем-JSON. Парсить `json.loads(...)['slug']` (в shell — через python, не `jq`-less substring), затем init; после init проверять `_state.json` в новом слаге.
- `complete-phase` в параллель с завершающимся `invoke-role` даёт «wrapper alive» (rc=0, фаза не закрыта) — это гонка, не dead-pid: дождаться выхода wrapper (sleep ~2) и повторить complete: проходит чисто.
- `ready_at` не ставится самим `init`: его пишет отдельное событие `reason=Б55:готовность` (`evidence=ready_at=…`) через штатный `write_state`. Для P2/FIFO-тестов сначала записать готовность обоих слагов, потом читать проекцию. `pipeline_queue.project()` принимает `pathlib.Path`; строка даёт `TypeError: unsupported operand type(s) for /: 'str' and 'str'`.
- `preflight --slug X --mode done` не принимает `--phase`; вердикт «phase … not done» при закрытых предшествующих фазах означает, что сама целевая фаза ещё не завершена `complete-phase`, а не дефект префлайта.

## Ловушки

- `next()` после `complete-phase` в rework-цепочках уводит на HF:test преждевременно — сверять карту фаз (done/todo), переоткрывать целевую фазу штатным writer'ом (REWORK, event=repair), а не `next`-ом.
- REV:plan может вернуть REQUEST-CHANGES, если declared candidate не исполняется из своей среды: candidate-only `PYTHONPATH` обязан содержать полный import closure (paths, state, extract, gates, recipe, status, preflight, probe) и packet schema, иначе `pytest`/`probe` падают `ImportError`/`ModuleNotFoundError`. Отсутствие runtime-зависимостей в candidate — блокер допуска к HF:impl/HF:test, не повод подмешивать live root в runner (нарушает B60.8/G3 load-binding). Не объявлять `9 passed`/`py_compile rc=0` PASS, если collection из заявленного candidate не запускается.
- `complete-phase --evidence` не принимает голый `verdict=...`: обязателен ключ `path=<abs>` (или `sha256=`/`session_id=`), иначе молча «evidence must include path= or sha256= or session_id=». Всегда указывать `path=`.

## Восстановление фазы и консультативный вызов роли

Когда роль завершилась, оставив мёртвый PID/фазу `doing`, или нужен ответ роли без движения поезда — см. `references/owner-invoke-and-recover.md`. Ключевое: правильный API `pipeline_state.read_state`+`write_state(st, event={...})` (функции `write_event` нет); событие `repair`/`actor=sirene` очищает PID и возвращает фазу к `todo`+`awaiting_invoke` без трогания счётчиков; ответ консультативного invoke читается из новейшего `~/.codex/sessions/<date>/rollout-*.jsonl` (последний assistant `output_text`), НЕ из stdout bg-процесса. Честный `PARTIAL_IMPLEMENTATION_PENDING_MATRIX` / `FAIL_MATRIX_INCOMPLETE` — незавершённая реализация (точечное исправление на том же исполнителе), НЕ эскалация; правило стоп-доклада срабатывает только на возврате исполнителя к архитектору.
- Не принимать дизайнерские имена/порты/конфиг за установленные экземпляры: «имя route — проектное, не заявление о существовании».
- Paused/local job, HTTP 200, mirror и queued admission — это не входящий receiver и не доставка процедуре.
- Периодический опрос провайдера — новая polling-петля, план и канон запрещают плодить её по умолчанию; она допустима ТОЛЬКО по явному полномочию Саши и работает raise-on-demand (поднимается лишь на время инцидента, а не живёт постоянно).
- Авто-arm критичен: script-only R-probe поднимает сам себя ТОЛЬКО из уже вошедшего в отказ обработчика. Если провайдер глушит саму процедуру ДО arm, независимый крон неоткуда взять (остановленный контекст не исполняет tool по инструкции). Держать `ARM_UNAVAILABLE` FAIL до наличия существующего исполняемого error-handler→arm; не выдавать заранее установленный крон за решение этого случая.
- Период опроса выбирается по фактическому ответу исходного scope, а не по чужим докам: точный retry-период даёт один разовый once-запуск, его отсутствие — ~часовой опрос. См. `references/r-probe-independent.md`, раздел «Таймбары».
- CLI cron не имеет deliver в произвольную session: `telegram:chat:thread` — исходящее человеку, `bot-chat` — отдельный canonical вход, не текущая сессия.
- Cron запускает no_agent-скрипт на dependency-venv поезда (`project_python`), а не на venv, где прошли component-тесты. Прогон скрипта под `hermes-agent/.venv`/`/usr/bin/python3` не доказывает cron-совместимость: зависимость вида `usertools_config` (тянет `yaml`) падает на cron-тике `ModuleNotFoundError` при ручном rc=0. Воспроизводить под интерпретатором cron перед активацией — рецепт в `references/install-staging.md`, шаг 3b.
