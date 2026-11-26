---
name: ecosystem-manifest-ops
description: "Use when запись в EcosystemManifest (ORCH) или drift-check."
---
# EcosystemManifest — запись и проверка дрейфа

Манифест: `~/WorkVault/Registries/EcosystemManifest.json` (+ render/digest). Источник правил структуры: `EcosystemManifest.schema.json`; правила ТЗ-инвентаря: `MAIN_TZ_INVENTORY.md` (статусы/версии брать из инвентаря, НЕ из frontmatter ТЗ — там бывает устаревший).

## R3-гейт
Запись в манифест — по явному «берём в работу» Саши; **исключение:** stub `tools{}` (минимальные поля, `status` из инвентаря) сразу после `TZ:finalize`, чтобы не оставлять `tz_ref` без записи. Полные `links`/контракты — после take-into-work / ORCH хвоста. Проработка/план манифест НЕ пишет (план → kanban_comment → отдельная ORCH:shared-state-карточка). Ревизор APPROVE на план не заменяет отмашки.

## Процедура записи (один писатель)
1. Убедиться, что нет другого running-писателя общих файлов (манифест, entities.json, MAIN_TZ_INVENTORY, restore-all-skills.sh). Параллельные ORCH-записи запрещены — last-write-wins затирает.
2. Бэкап: `mkdir -p ~/.hermes/_Archives/hermes-backup-$(date +%Y%m%d-%H%M%S) && cp Registries/EcosystemManifest.json туда/`.
3. Правка JSON скриптом (python3+json): tools как dict по slug-key (в т.ч. `entity_registry`, НЕ `entities_registry`); `links` — flat list `{from,to,relation,note?}`; дедуп `(from,to,relation)`.
4. Обновить `updated_at` = now ISO.
5. `python3 render_manifest.py --render` затем `--digest` (оба обязательны, отдельно).
6. `python3 render_manifest.py --check-drift`: остаток — починить либо осознанный non-index (`SKIP_TZ_DIRS` в render_manifest.py) с комментарием в карточке; waiver на `missing_contracts_section` нет.
7. Тесты: `python3 -m pytest test_render_manifest.py -q`.
8. Комментарий в карточку: что записано + диф + путь бэкапа + остатки дрейфа.

## Питфоллы
- **Конфиг-ключи в ORCH копировать ДОСЛОВНО из ТЗ (§12/Q-ответы), никогда не изобретать/сокращать.** «Похожий» value проходит schema (тип string) и unit-тесты, но валится в живом API (403 scope/unknown user). После ORCH-записи обязателен живой smoke (`--mode test --dry-run` против реального API), не только schema-валидация.
- `tools.<key>.version` может **отставать на несколько мажоров** от реальной версии — не бампать «+1» от манифеста. Канонический источник версии — `MAIN_TZ_INVENTORY.md` в WorkVault (git-зеркало `~/hermes-workspace` может не синкаться/стагнировать). Сверить с инвентарем/ТЗ/кодом, бампать до неё.
- **Фикс в SHARED-компоненте = bump версии И потребителя, И владельца**, даже если в теле ORCH-карточки назван только потребитель. Строка `updated:` в инвентаре несёт оба bump'а в одной записи — читать ВСЮ строку, решать «какие `tools.*.version` трогать» из неё. У владельца `version` может отсутствовать — создать целиком, не бампать `None`.
- `tools.<key>.version` **не входит** в render-таблицу и в обязательные поля schema. После bump проверять в JSON напрямую (`python3 -c` по `tools.<key>.version`), не grep render.md; digest подтверждает только deep-ссылки.
- `render_markdown` требует `link['note']` — без него KeyError. Если паттерн «note опционально» не в render_manifest.py — сначала патч (`link.get('note','')`), потом записи.
- Дрейф «ТЗ есть, tools-записи нет» — stub/full засвись **или** `SKIP_TZ_DIRS`; решение согласовать с архитектором, фейковый tool не заводить.
- Если план предусматривал `contracts` у tool без него — создать ключ целиком (dict с owner_of), не точечно.
- WorkVault не git: коммитить некуда, бэкап в _Archives — единственная страховка.

## OverlayConfig-миграция: `migration_status` и приёмка AC-009
Волн же (w1..w4). Статус `config.tools.<key>.migration_status`: `not_started → dual_read → accepted → unified_only`.
- **ORCH ставит `dual_read` после переноса, но НЕ пишет `accepted`** — это отдельный операторный гейт AC-009: только после явной реплики Саши «принять» (поштучно или пакетно для w3). `accepted` не выводится из explain-зелёности/тестов.
- **`GATE:done` графа НЕ равен приёмке.** Граф может закрыться (preflight PASS) при 0× `accepted` — волны формально неприняты, legacy держится до «принять»+«удаляй». Не сообщать «волна закрыта» как «всё принято».
- Legacy выпиливается per-tool после приёма (AC-011 «удаляй»); волна 4 — снос fallback из лоадера. Секреты — только в shared `.env`, НЕ в YAML.
- **При переводе инструмента на единый конфиг старый источник УДАЛЯЮТ (не держат legacy рядом); бэкап объединённого конфига обязателен и хранится для отката.** Перед стартом миграционной волны снять полный слепок каскада лоадера + YAML/манифеста (для OverlayConfig: `usertools_config.py`, `usertools_env.py`, `EcosystemConfig.yaml`, `schema.json`, `EcosystemManifest.json`, `battle_interpreters.yaml`, `probe_battle_venv.py` + `baseline.sha256`) в `~/.hermes/_Archives/hermes-backup-eco-config-<wave>-<ts>/`. Откат — versioned restore **кода+YAML из бэкапа**, НЕ возврат старого `.env` (`.env` не является SoT и не восстанавливается). Перевод партиями: сначала перевести когорту (напр. 7 `accepted`, затем по 10), ловя ошибки на ней, и только потом следующую; старый источник каждого инструмента удаляется в момент перехода на единый.
- Поштучные Q-n на приёмку заводит ORCH (по одному на tool_key); answer+evidence пишет Сирень после реплики Саши.

### ORCH:shared-state перевод партии `accepted → unified_only` — исполнение ПОСЛЕ глагола `удаляй`
Когда Саша дал операторский глагол `удаляй` (перевод партии, напр. A0 = 7 `accepted`), НЕ иди через `operator-done` — на миграционной партии нет явно заведённого `hold` (state.operator_holds пуст), и `operator-done --verb удаляй` падает «operator-done requires evidence» + «Incomplete log event: missing phase». Порядок исполнения — прямой батч-записи манифеста + `complete-phase`:
1. **Перед удалением сверить, что ничего не теряется:** несекретные значения уже в едином конфиге (напр. `CONFLUENCE_URL`→`shared`, `WORKVAULT_PATH`→`shared`, пути/`TELEGRAM_CHAT_ID`→`tools.<key>`), секреты уже в `~/.config/hermes/.env` (`grep -c '^KEY='` ≥1). Только после этого `rm` legacy `~/USERTOOLS/<Tool>/.env`.
2. Батч-запись манифеста (python3+json): для каждого ключа партии `migration_status='unified_only'`, `overlay=None`, `rollback_snapshot=<путь к Archived YAML>` (лежит в `~/.hermes/_Archives/eco-config-w4-*/ecosystem-config/<tool>.yaml`).
3. Сверить счётчики `config.tools` (напр. `30/9/0/7`) и что `accepted=0`.
4. `render_manifest.py --check-drift` (→ `No drift detected.`) + `--digest` + `--render` (все три, отдельно).
5. Написать карточку `dev/<slug>/ORCH-shared-state.md` (решение Саши, пакет ключей, действия, счётчики, границы).
6. `complete-phase --phase ORCH:shared-state --reason ... --evidence path=.../ORCH-shared-state.md`; затем `next` → `AUTO_GATE GATE:done` → `complete-phase GATE:done`.
Legacy-ветки в самих `config.py` инструментов вырезаются на финальном 4-clean (когда все 46 → `unified_only`), НЕ в этой фазе.

### Снимок 4a/4b и статус миграции: читать `config.tools`, НЕ `tools`
`migration_status` живёт в `manifest.config.tools.<key>.migration_status` — это **отдельная карта от `manifest.tools.<key>.status`** (тот — статус сущности `active/draft/released/archived/completed`). Зелёный снимок волны 4 (4a/4b): все active/draft/paused записи `config.tools` = `unified_only`, т.е. счётчики `not_started=0 dual_read=0 accepted=0 unified_only=46`. Источник счётчиков — `_config_migration_counts()` в `render_manifest.py`; `dev_workflow` — отдельная 47-я строка `battle_interpreters.yaml`, не `config.tool`, и в снимок не входит. `dialog_backlog`/`dialog_backlog_to_kanban` остаются `enabled:false` в пакете.

### Волна 4 (cutover из лоадера) — предусловие-гейт, `HF:impl` даёт только reviewable-патч
Вырезка `overlay`/`legacy`/`USERTOOLS_CONFIG_MODE`/`local_env_path` из `usertools_config.py`/`usertools_env.py` разрешена только при зелёном 4a/4b. До этого `HF:impl` корректно останавливается **до live-edit**: готовит reviewable `HF-impl-patch.diff`, production-лоадер/манифест/YAML/`.env` не трогает (хэши = baseline бэкапа). Фраза «завершаем волну» при красном предусловии **двусмысленна** — переспроси Сашу, какой из двух смыслов: (а) довести поезд до `GATE:done` честно с тестом «патч готов, cutover заблокирован 4a/4b, production=baseline», либо (б) начать миграцию инструментов партиями (A0: 7 `accepted` → потом по 10), что и есть фактический разблокер cutover. Это развилка по судьбе карточки — не решай сам.

### runtime-real приёмки: свежие живые тики боевого крона закрывают гейт без повторного прогона
Критерий «три последовательных cron-тика / полный рабочий день» не требует wall-clock ожидания суток. Сначала сверь `cronjob list`: если у инструмента есть **живой боевой крон** с недавним `last_status=ok` (`last_run_at` свежее), его уже состоявшиеся тики **и есть** runtime-real evidence — гонять заново не нужно. Разово прогнать нужно **только** инструменты без собственного боевого крона (entry=shebang/wrapper без своего job) — их штатным venv, с фиксацией rc/stdout.

**Pitfall — не клонируй side-effecting боевые кроны в разовые копии.** Клонирование скрипта боевого крона в разовый джоб рискует гонкой: `mfl_urgent` тикает ~3 мин, `pfs_notify` — ~5, разовая копия падает в тот же слот и даёт двойной прогон. Эти скрипты не dry-run (реально двигают сообщения/шлют уведомления). Для суб-часовых кронов бери уже состоявшиеся тики, не дублируй запуск — иначе ложный red/двойной сайд-эффект. Прежде чем предлагать «разовые копии боевых кронов», свери расписание живого крона.

### Приёмка большой волны: triage после repeated blocks ≠ провал
Если воркер реально завершил перенос и упёрся в AC-009 (не может выставить `accepted` без Саши), диспетчер после repeated `block_loop_detected` рутит в triage. Это «работа сделана, ждёт HITL», не зависание. Разбор: читать последний `task_comments` + attachments (если `*_final_verification.txt` приложен, все tool_key `dual_read`, импл верифицирован) → вынести поштучные Q-n Саше по **названиям инструментов**; НЕ перезапускать воркер/не диспатчить повторно. `accepted` не выставлять до явной реплики.

### Долгоживущая волна в ready/review петляет в stalled-train — паркуй в needs_input
Направление «отказ от канбана как оркестрации → скилл dev-orchestrator + файловое состояние» — согласованный вердикт архитектора (`references/no-kanban-dev-orchestrator-design.md`). План ждёт «берём в работу»; `DEV/kanban-stalled-train-age` НЕ реализовывать.

Сторож stalled-train мерит «возраст» от `started_at`, а **не** от последнего перехода/`last_heartbeat_at`. Большая сквозная карточка при выходе в `ready`/`review` блокируется мгновенно (~90с) причиной `review-required: stalled-train …>Nч` → `block_loop_detected` → triage. Это не сбой воркера, а неверный домен возраста.

**Правильный дом — `needs_input`:** `hermes kanban block <id> --kind needs_input "…"` — защищён от stalled-train, карточка честно «ждёт человека». НЕ ставить `unblock`→`dispatch` на готовую работу в `ready`/`review` — вернёт ту же петлю. `accepted` — только после реплики Саши; после приёмки карточка→done (из реестра), рендер+digest+drift.

### Статус-отчёт канбана: показывать ВСЕ активные статусы включая scheduled/ready
`kanban_status_report.py` (cron eco-config) фильтровал только blocked/running/todo/triage — `scheduled`/`ready` молча выпадали, волна «пропадала». Перечислять ВСЕ: blocked / scheduled (подвисшие) / ready / running / todo / triage; done/archived — по запросу. Фильтр по статусам в репорте = источник «задача то есть, то нет», не реальное исчезновение.

### ⚠️ dual_read приёмка = реальный запуск инструмента в ЕГО battle-интерпретаторе, не dry-run в тестовом venv
Лоадер `usertools_config.py` (`~/.hermes/lib/usertools_config.py`) имеет **top-level `import yaml`** — это ХАРД-зависимость каждого подключённого инструмента. Прецедент 12.10.2026: MoveFromFF и FirefliesAutojoin после волны 1 падали `ModuleNotFoundError: No module named 'yaml'` на каждом тике боевого крона, т.к. в их `.venv`/`venv_linux` PyYAML не был установлен (ConfluenceSync/PFS работали — у них был).

**Почему тест не поймал:** приёмка шла через venv PFS (PyYAML есть), а боевой крон запускается СВОИМ venv. «Зелёный» dry-run в чужом venv маскирует сломанный боевой venv.

**Нюанс (17.10.2026):** НЕ гоняй вслепую `import pydantic_core`/`loguru` по всем `.venv` и не делай вывод «сломано». Лоадер импортирует **только `yaml`**; pydantic/loguru нужны лишь инструментам, использующим их в коде — у них сбой на **интерпретаторе Hermes 3.14 in-process** (скиллы показываются внутри сессии агента), а не в собственном venv. **Правило: сначала определи РЕАЛЬНЫЙ battle-интерпретатор** — кроны (`*.sh` → свой `.venv`/`venv_linux`), скиллы (Hermes 3.14 in-process), shebang/wrapper. `battle_interpreters.yaml` + `probe_battle_venv.py` — стандартный AC; pytest в venv PFS/hermes его НЕ закрывает.

**Правило приёмки (AC для каждой волны/инструмента):**
1. Проверить top-level импорты лоадера и что каждый пакет есть в venv, которым КРОН реально запускается (`.venv`/`venv_linux`/systemd).
2. Эмулировать реальный запуск: одноразовый крон (`cronjob repeat=1`) или прямой запуск той же команды в боевом venv — реальный тик, 0 ошибок импорта, реальный вызов API.
3. При переносе — добавить PyYAML в requirements/pyproject + установить в venv ещё в HF:impl.
4. У части инструментов вместо `.venv` — `venv_linux` (FirefliesAutojoin): проверять реальный.

См. master-ТЗ `EcosystemIntegration` и appendix модуля 0.

### Архитектурные решения по миграции — гейт согласования + блок волны
Выбрано архитектурное решение (напр. «PyYAML в venv» vs ленивый импорт) — НЕ начинать реализацию сразу: маршрутизировать на согласование архитектору (cursor-grok через cursor-cli) и **заблокировать волну** до вердикта: `hermes kanban block <task_id> --kind needs_input "Ожидание вердикта архитектора по <вопросу>"` (реализация HF:impl — после). Составить постановку с оценкой и предложенного решения, и альтернативы.

### GATE:done blocked «по upstream-дефектам» — почини граф/метаданные, не пересобирай
GATE:done может быть `blocked` из-за upstream-свойств графа, не тела AC: (1) оборвано ребро «рабочая фаза → следующая» по канону BUGFIX-LIGHT (`TZ:patch→TZ:finalize`), а в графе они братья под общим `GATE:diagnose-review`; (2) git-proof G3/AC-H07: `changed_files` `HF:impl` с суффиксом `(new)` и/или **относительно корня git-репо**, а префлайт резолвит от `$HOME` → путь не существует, либо код не закоммичен (`M/??`).

**Порядок (оркестратор, без пересборки):**
1. Прочесть полный reason блокировки — там перечислены upstream-дефекты.
2. Оборванное ребро: `hermes kanban link <рабочая> <следующая>` + `unlink <общий-родитель> <следующая>` (следующий — один канонный родитель). Проверить `parents`.
3. git-proof: закоммитить файлы фикса отдельным коммитом (не чужой мусор рядом); поправить `changed_files` в `task_runs.metadata` на **абсолютные** пути (`~/USERTOOLS/.../file.py`) и **без** `(new)`. Раздельно исправить одну часть = проигрыш — оба.
4. `pipeline_gate_done_preflight.py --slug <slug> --case <кейс> --mode done` → PASS → `kanban unblock` GATE:done.

### CLI-канон: `--reason` не существует; block→`--kind`+message, complete→`--result`/`--summary`
У `hermes kanban` НЕТ `--reason` ни у `block`, ни у `complete` (оба падают `unrecognized arguments`).
- `block` → `hermes kanban block <id> --kind needs_input "<причина>"` (причина → комментарий).
- `complete` → `hermes kanban complete <id> --result "<summary>"` (+`--summary`, `--metadata`).
Это отсутствующий флаг CLI, НЕ сигнал чинить ядро. Обоснование-комментарий добавлять отдельным `hermes kanban comment` перед закрытием.

### `--body`-аргумент с нераскрытой переменной пишет литерал `{var}`
`hermes kanban edit <id> --body "$VAR"` без подстановки уходит **строкой `{body}`** → воркер корректно распознаёт плейсхолдер и **блокирует** задачу (`block_loop_detected` «тело = плейсхолдер»), волна в triage.

**Правило:** перед `edit --body` проверить в БД (`SELECT body FROM tasks WHERE id=?`) что тело ≠ `{body}`. Если ушёл плейсхолдер — записать правильное тело (`UPDATE tasks SET body=?` через python), вернуть статус (triage→specify→ready), диспатчить один раз. Это защитное поведение диспетчера, не «воркер завис». В subprocess всегда раскрывать переменную.

## Разбор накопившихся blocked-карточек (порядок)
Пачка blocked → отдать архитектору на сверку актуальности (факты на диске, дубли, зависимости) → закрыть готовые проработки (параллельно) → строгая последовательность для записей в общие файлы → докатка хвостов. Перед каждой карточкой проверять, не сделана ли работа уже off-board — «берём в работу» по устаревшему гейту разворачивает дубль графа.