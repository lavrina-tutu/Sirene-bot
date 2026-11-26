---
name: dev-graph-train-ops
version: 0.1.0
description: "Use when ведёшь поезд dev-графа: перемотка, G1 drift."
---

# dev-graph-train-ops — операционные приёмы ведения поезда dev-графа

Профильный скилл для повторяющихся операционных приёмов при ведении поезда через dev-граф (pipeline.cli). Покрывает три класса техник, которые `dev-workflow` (глобальный) описывает на уровне процедуры, но не фиксирует как отдельные питфоллы. Если `dev-workflow` доступен для записи — перенести эти правила туда; здесь они живут как профильный слой.

## When to Use

- Перемотка поезда на `HF:plan`/`TZ:patch` для доплана или REQUEST-CHANGES.
- `check` вернул `G1 fail: tz version drift` на поезде после bump master другим поездом.
- План запрещает исполнителю править манифест, а причина P01 — пустой/отсутствующий `tools.<key>.path` (owner-fix).
- Запуск `invoke-role` (architect/reviewer/executor).

## Версии скилла и master независимы: «проверить/синкнуть скилл» = активный поезд

Нумерация скилла (frontmatter `version`, напр. dev-workflow `0.8.2`) и версия master-ТЗ (напр. `0.9.3`) — НЕЗАВИСИМЫЕ последовательности: разрыв между ними не означает рассинхрон и не требует «синка» версии вручную. Запрос «проверить/синкнуть скилл под master-ТЗ» означает править сам `SKILL.md` по новым требованиям master — а это реализация активного кейса SKILL-CHANGE (например, пакета Б57 с требованиями R1–R7/AC-SIMP), которую ведёт штатный поезд до `HF:impl`.

- Ответ на такой запрос НЕ начинается с бампа `version` или правки скилла: сначала открыть `dev/<slug>/_state.json` активного поезда — какая фаза, `recover_counts`, журнал поезда — и доложить реальное место поезда, а не «версии на диске». Прямое изменение `SKILL.md` или версии вне процесса — обход DevWorkflow, запрещён.
- Разрыв «скилл старее master» по определению покрыт активным SKILL-CHANGE-слагом этого же ТЗ; если поезда нет — это отдельный вопрос наличия ТЗ, а не тривиальный бамп.
- При разборе стопнутой фазы ТЗ-цикла (completer ещё НЕ вернул результат) свежий артефакт на диске при мёртвом wrapper = окно post-invoke с обрывом публикации: reconcile по диску/журналу/контексту → апдейт extract-полей state под новую версию → `complete-phase`; НЕ recover и НЕ re-invoke (второй recover той же пары запрещён AC-071).

## Перемотка для доплана (rewind scope)

**Перемотка поезда на `HF:plan` для доплана сбрасывает в `todo` ТОЛЬКО фазы от `HF:plan` и дальше; закрытая ТЗ-стадия (`TZ:stabilize`…`GATE:take-into-work`) остаётся `done`.** Мастер-ТЗ уже финализирован и согласован — его фазы не трогать.

- Перемотка-скрипт, который обнуляет ВСЕ фазы, ломает граф: `TZ:patch`/`REV:tz`/`TZ:finalize`/`GATE:take-into-work` снова станут `todo`, хотя их артефакты на диске актуальны.
- После такой перемотки обязательно восстановить закрытые фазы в `done` (через `pipeline_state.write_state`, событие `rev_request_changes_rewind`), оставив `HF:plan` в `doing`.
- Доплан меняет только `HF-plan.md`; ТЗ-стадия не пересобирается.
- Событие перемотки — из закрытого словаря `pipeline_log.py` (`rev_request_changes_rewind`), не `rewind`/`repair`.
- **Owner-пересмотр в CHANGE-LIGHT: реплей ВСЕГО хвоста от `TZ:patch`, не только HF:*.** Когда владельческая директива переопределяет норму master v-версией поверх v-версии (v1→v2 «календарь не смотрим»), откатывается НЕ только impl/test — реплей идёт от `TZ:patch` до конца рецепта (`TZ:patch→TZ:finalize→GATE:take-into-work→HF:impl→HF:test` все в `todo`, прежние receipt/packet/context в `proof.context_history`), т.к. §22 переписывается архитектором и AC/мастер меняются. Это «Второй ТЗ-круг», контракт — из того файла, где блок `handoff-contract` стоит первым (в CHANGE-LIGHT это `brief.md`, HF-plan отсутствует).
- **Имя события переоткрытия самой ранней не-REV фазы (`TZ:patch`) — открытое из словаря, напр. `start`**, а не самодельное `owner-rework-v2`: журнал отвечает `Incomplete log event: unknown event` и `write_state` НЕ применяется (состояние остаётся, скрипт печатает OK). Для REV-перемоток остаётся `rev_request_changes_rewind`.
- **Перемотка до `TZ:patch` (а не `HF:plan`) нужна, когда фикс требует изменения НОРМЫ master** (новое адресное исключение, bump версии): `TZ:patch` → `doing`, всё после него → `todo`. Фазы до `TZ:patch` (`TZ:stabilize`/`TZ:compress`) можно сбросить в `todo` — extract пересжимается под новую версию; не восстанавливать их в `done` вручную, это нормальный сброс для нового TZ-цикла. Решение Саши о новом исключении — императив на перемотку и bump, но сам текст нормы пишет архитектор в `TZ:patch`. После смены нормы старый HF-plan права на production-ремонт НЕ даёт: REV:tz-APPROVE одобряет только текст ТЗ («не подтверждает свежий runtime PASS, прежний план не разрешение»); нужен новый HF-plan под новую версию master и REV:plan именно его SHA.
- **Нюанс: если extract под новую версию пересчитан вручную через `repair` (а не повторным `TZ:compress`), то `TZ:stabilize`/`TZ:compress` фактически `done` — иначе после `complete TZ:patch` `next` зацикливается и снова возвращает `TZ:stabilize`.** Тогда восстановить обе фазы в `done` (write_state, `repair`) и явно выставить `st.phase = REV:tz` (вариант: `status=in_phase`); иначе `next` не продвинется к ревизии, хотя артефакты на месте и `check` зелёный. Это не противоречит сбросу в `todo` — сброс верен, только если compress реально перезапускается; при ручном re-key второй путь — восстановить done + синк фазы.

## Второй ТЗ-круг: контракт берётся из HF-plan.md, не brief.md

Когда перемотка нужна для ВТОРОГО прохода начальных фаз (TZ:patch → REV:tz → TZ:finalize…), а не достроя хвоста: закрытые `done`-фазы первого круга НЕ обязаны оставаться done — REV:tz (новая независимая ревизия нормы), TZ:finalize и GATE:take-into-work должны пройти заново. Иначе `complete-phase` текущей фазы упирается в оставшиеся `done` downstream-фазы, поезд приходит в `idle` с пустой стадией и `next` не продвигает.

- **`_contract` возвращает блок `handoff-contract` из ПЕРВОГО файла в порядке (HF-plan.md, brief.md), у которого он есть** — поэтому правка контракта в brief.md НЕ влияет, когда существует HF-plan.md с собственным блоком. План, написанный только под хвост рецепта (HF:plan→ORCH), не покрывает write_scope/outputs фаз второго ТЗ-круга → invoke падает `output outside write_scope` на TZ-patch.md. Дополнять write_scope/outputs контракта ПЛАНА (TZ:patch/REV:tz/TZ:finalize/GATE:take-into-work + их canonical-файлы) — правка уполномоченного writer плана по вердикту архитектора.
- **Не добавлять синтетический `rework_request` в `proof` вручную при оркестраторном возврате.** `emit-prompt`/`addressed_rework` ждут словарь с ключом `ref`; `{source, reason}` без `ref` роняет emit `KeyError: 'ref'` и не создаёт prompt-файл — фоновый invoke стартует против несуществующего файла и падает `No such file or directory`. Вернуть фазу чисто (без rework_request), emit построит обычный `forward` handoff.
- **`write_state(... event={...})` — имя event обязано быть в закрытом словаре `pipeline_log.CLOSED_EVENTS`.** Неизвестное имя (любое самодельное) поднимает `unknown event` и запись НЕ персистится — состояние остаётся прежним, а твой скрипт печатает success. Для оркестраторного возврата/перемотки использовать `event="rev_request_changes_rewind"` (с явной `phase`).
- **Элемент фазы с `proof: None` перед записью заменить на dict**: `p['proof'] = p.get('proof') or {}` и только потом `setdefault` — иначе `NoneType does not support item assignment`.
- Открытие второй ТЗ-стадии: REV:tz → doing/awaiting_invoke, TZ:finalize и GATE:take-into-work → todo, очисткой receipt/context_packet/context_result/fail_class/started_at/ended_at/reason; прежние receipts первого круга сохранить в `proof.context_history`. Зафиксировать `st.phase=<новая фаза>`, `st.status='in_phase'`, `st.pid=None`.

## Cross-train G1 drift

Когда один поезд финализирует master (bump версии), соседний поезд, финализировавший ТЗ под старой версией, падает на `check` с `G1 fail: tz version drift` — его `extract.md`/state указывают на старую версию, а master на диске уже новую. Тот же дрейф возникает ВНУТРИ поезда после собственного `TZ:patch`: архитектор поднял версию master, а `st.tz_version` ещё старая — `check` этой фазы падает G1. Процедура одна: дополнить extract.md новым нормативным пунктом, затем write_state (event `repair`) синхронизирует `tz_version`, `tz_mtime=int(os.stat(master).st_mtime)`, `extract_sha256`, `extract_chars`, `extract_of_tz_version`, и, если `check` вернул `extract_key drift`, также пересчитать `extract_key` через `make_extract_key`.

- Лечение то же, что внутри поезда: обновить заголовок `extract.md` под новую версию master + пересчитать extract-ключи через `write_state` (событие `repair`, actor `sirene`), затем перевыпустить `emit-prompt` для свежего `context-used`.
- Актуальная норма для поезда = версия master на диске, а не та, под которую он стартовал; вердикт архитектора опирается на текущую версию.
- `mark_context_used` не перезаписывает существующий маркер `phase=<X>`; повторный emit-prompt новый маркер для той же фазы НЕ дописывает (dedup по фазе). Устранять висящий маркер штатным путём: удалить старую строку `context-used: … phase=<X> …` из journal.md (patch), затем заново `emit-prompt` на той же фазе — он допишет свежий маркер с реальным `emitted_at` и актуальным sha. **НЕ заменять строку маркера вручную и НЕ проставлять время от себя:** ревизор фиксирует ручную подстановку (особенно с `emitted_at` в будущем/не из emit) как расхождение provenance — «происхождение маркера не подтверждено trace emit» — и это блокер R1. Единственный способ, который ревизия принимает, — это реально выполненный emit, создавший маркер.
- **G1-guard на `emit-prompt` для HF:* фаз — строгий и конкретный.** `cmd_emit_prompt` для `phase.startswith('HF:')` сверяет `sha256(файла на диске) == state.extract_sha256` И требует непустые `extract_key/extract_sha256/extract_of_tz_version/extract_chars`; после правки файла extract без синхронизации этих полей emit падает `G1 fail: validated extract metadata required` (rc=1), пакет не собирается. Обновляй на каждую правку extract: `extract_sha256` (новый hash файла), `extract_chars` (длина), `extract_of_tz_version = tz_version`. Механика: `mark_context_used` сам допишет маркер и обновит `extract_sha256/chars` после успешного emit — но до него guard требует уже консистентных полей.
- **Третий режим G1 — `extract_key drift` — лечится пересчётом ключа, не только полей sha/chars.** После правки extract И синка `tz_version/tz_mtime/extract_*` `check` всё ещё может вернуть `G1 fail: extract_key drift`: `extract_key` хранит `path|version|mtime|prompt_hash` и не обновляется автоматически. Пересчитать в том же `write_state` (событие `repair`): `state.extract_key = pipeline_extract.make_extract_key(state.tz_path, state.tz_version, state.tz_mtime, pipeline_extract.prompt_hash())`. Это третий шаг после tz version drift и validated metadata; без него `check` красный даже при консистентном файле.
- **Висящий старый маркер `context-used:` с прошлой версии — процессный дефект, а не косметика.** Если `mark_context_used` не перезаписывает существующий маркер `phase=<X>`, в journal остаётся `context-used: … tz_version=0.7.2` при живом master 0.7.5; ревизор фиксирует это в REV-отчёт как замечание оркестратору («актуальный маркер G2 штатным порядком, не дописывать задним числом») даже если сам пакет собран верно. Следи, чтобы перед повторным ходом роли маркер соответствовал текущей версии — иначе теряешь ход на процессном пункте ревизии.

## Выжимка длиннее 5120 симв. — build_packet обрезает хвост ДОСТАВЛЕННОГО пакета

`pipeline_context.build_packet` режет секцию Extract по `MAX_EXTRACT_CHARS = 5*1024` и добавляет маркер `…(truncated)`. Если `extract.md` длиннее — в `/tmp/task.md` попадают первые 5120 символов, а хвост (обычно `[NEW-ENTITY]`, AC-список, «Что НЕ трогать», запреты) теряется. При этом `pipeline check` остаётся exit 0 (он проверяет существование файла, ключ и G2-маркер, а не полноту доставленной секции), и ревизор дочитывает master сам, но блокирует (R1) именно обрезанный пакет.

- Передавай выжимку **в пределах 5120 символов**: сожми плотнее, сохрани критические имена (`AC-*`, `[NEW-ENTITY, требует согласования Саши]`, «Что НЕ трогать», запреты, пути). 12-14 КБ своей «полной» выжимкой в пакет не влезает.
- **После** `emit-prompt` проверяй фактический хвост `/tmp/task.md`, а не файл на диске: `grep` последних идentifiers (`AC-RP-19`, `NEW-ENTITY`) и отсутствие `…(truncated)`. Проверка «файл существует + hash совпал + check exit 0» НЕ доказывает доставку хвоста.

## Owner-fix write-set (манифест правит владелец, не исполнитель)

Когда план запрещает исполнителю править `EcosystemManifest.json`, а причина P01 — пустой/отсутствующий `tools.<key>.path`:

1. Оркестратор применяет owner-фикс сам как владелец манифеста: меняет РОВНО поля `tools.*.path` (по одному на ключ).
2. Снимает receipt: `old/new`, sha до/после, структурный diff — только эти поля, соседи/`config`/`tz_ref`/registry/YAML/schema/digest неизменны.
3. Затем исполнитель верифицирует с диска (читает исправленный манифест, не подстановку в evidence).

Питфоллы:
- **Зафиксировать `old`-значения из baseline ДО записи.** Если первый write упал ПОСЛЕ записи манифеста (например, на receipt из-за отсутствующего каталога evidence), повторный запуск прочитает уже новые значения как `old` — receipt станет ложным.
- Каталоги-цели проверить на существование до правки; каталог ради PASS не создавать.
- Не переносить адресное исключение (например, AD-R3-01) с одной партии на другую — каждая строка требует собственной подтверждённой closure.

## Invoke-role фоном

`invoke-role` — только фоновый вызов: `terminal(background=true, notify=true, persist_on_release=true)`. Foreground с `notify` возвращает «notify only applies to background commands» — не ретраить в foreground, сразу фон. Артефакт проверять на диске (mtime/версия), не верить rc=0.

- `--model`/`--backend` переопределяют ролевые модели на ОДИН инвойк (например, смена исполнителя по решению Саши «однократно»); конфиг ролей `EcosystemConfig.yaml tools.dev_workflow.roles` при этом не менять. Инвойк с явной моделью логируется в journal (`invoke_prepare ... model=...`).
- **`invoke-role --role <роль>` требует `--slug <slug> --phase <phase>` с ПЕРВОГО вызова** — без них команда честно пишет `invoke-role requires --slug and --phase` и выходит c rc=0 (потому что echo-обёртка `; echo RC=$?` возвращает реальный rc, а не код команды). Не запускать invoke без slug/phase в надежде, что роль сама догадается, на какой фазе она. (Это инвойк, а не консультация архитектора из `references` — там другой вызов.)
- **Зависшая фаза после foreground-таймаута: signs — journal показывает `invoke_prepare`, но `invoke_role` НЕ появился, а `ps` не видит ни wrapper, ни codex → backend-процесс не стартовал, в state мёртвый pid.** НЕ долбить фазу новыми foreground `invoke-role`: каждый повтор пишет ещё один `invoke_prepare` (мусор в journal), переписывает pid И сжигает ход фазы; а до того проверять живость codex — прежний wrapper мог остаться как orphan-процесс codex (тогда повторный invoke дублирует роль, а не чинит). Сброс: `write_state(event={'event':'repair',...})` выставить `pid=None`, проверить `ps` (нет живого codex), затем ровно один invoke через `background=true`.
- **Ложный provider-fatal при `rc=0`: fallback-скан не-JSON stderr.** Codex пишет безвредные предупреждения (`failed to refresh available models: request timed out`) даже на успешном запуске; `_fatal_reason` сканировал их как FATAL_PATTERNS и обрывал финализацию. Правило: структурные JSON error-envelope авторитетны для любого rc, а свободный stderr сканировать только при `rc != 0`. Проверять юнитом: `_fatal_reason(ok_stdout, benign_stderr, 0, backend='codex') is None`, а `rc=3`/error-envelope — по-прежнему fatal.
- **Роль завершилась `invoke_fatal` provider-fatal, но канонический артефакт записан ПОЛНО — это одна транспортная пауза, а не два дефекта; не правь proof руками.** Симптом на `complete-phase` с двумя guard подряд: `g6: phase <p> role None != <expected>` (invoke_fatal не проставил роль фазы в state), а после проставления роли — `G2: accepted prepare/result receipt mismatch` (transport не дофинализировал accepted context: `context_result`/result receipt отсутствуют). Обе причины — один обрыв финализации invoke после записи вывода роли. Лечение по канону post-invoke/true-crash, НЕ ручная дописка proof/`context_result` и НЕ ручная правка появившегося на диске артефакта: 1) reconcile по диску (артефакт цел) и проставить фактическую роль фазы writer-репом `repair` (у ролевых фаз вроде `BUG:diagnose` expected-роль берётся из `role_for_phase` — это `architect`, не отдельная роль-диагност); 2) тем же writer-репом сбросить dead-pid: `pid=None`, `fail_class=None`, `awaiting_invoke=True` (счётчики не трогать); 3) свежий `emit-prompt` (новый packet_id) → единственный фоновый `invoke-role` той же роли, который штатно перезапишет accepted подготовку/результат и receipt; 4) затем `complete-phase`. Второй голый повтор того же класса запрещён — только reconcile+повторный invoke, как выше.
- **Серия ошибочных foreground-запусков одной фазы копится в `budget_exhausted:phase-turns` — жёсткий NON_RECOVERABLE_FAIL.** Механизм: у фазы есть лимит фазовых ходов (`phase_turns`); каждый (не)запустившийся invoke считает ход, а мёртвый pid/`output=[empty]`/`rc=0` без `invoke_role` не сбрасывают его. После нескольких ошибочных повторов pipeline штатно пишет `interrupt ... reason=budget_exhausted:phase-turns`, и это в `NON_RECOVERABLE_FAIL` — НЕ технический recoverable, перезапуск молча запрещён. Разблокировка — только решение владельца (Саши) с явным запросом о сбросе бюджета; обход `NON_RECOVERABLE_FAIL` молчаливым сбросом счётчика = нарушение. Если реально был один класс почему-то нестартовавшего invoke поверх СУЩЕСТВУЮЩЕГО провала — это второй класс, не «повтори тот же».
- **Shell-level обёртки фоновых (`nohup`/`disown`/`setsid` в foreground команде) отклоняются платформой** (exit -1 «re-send WITHOUT the wrapper as terminal command with background=true») — фон — только параметр инструмента `background=true`/`notify=true`/`persist_on_release=true`, не shell-синтаксис. Ошибка «notify only applies to background commands» при foreground=`notify` — то же: сразу корректный фоновый вызов, не ретрай в foreground.
- Перед повторным invoke сверять фазу и pid в state: запуск invoke поверх уже done/мёртвой фазы или с лишними параллельными вызовами грязнит journal мусорными `invoke_prepare` и перетирает pid; остановиться, погасить лишние процессы, затем продолжать штатно.

## Оркестратор не исследует: CAP/недостающие факты — работа архитектора через поезд

Когда фаза блокируется на недостающих authority/фактах (лимиты, tokenizer, deployment, конфиги, провайдерские данные) — оркестратор НЕ собирает данные и НЕ пишет capability-справочники сам. Правило Саши: исследование делает архитектор, оркестратор только передаёт вопрос через поезд.

1. Записать директиву владельца `evidence/<phase>-r<N>/owner-directive-*.md` (распоряжение Саши дословно + что разрешено роли + что запрещено).
2. Добавить файл в **пофазные** `inputs` контракта нужной фазы (handoff-contract в HF-plan.md). Входы пофазны: добавление в inputs TZ:patch НЕ делает файл видимым в packet HF:plan — добавлять в каждую фазу, которой он нужен, и проверять по свежему emit.
3. Переоткрыть фазу штатным writer'ом (event `repair`, actor sirene: status WORK, awaiting_invoke=True, pid=None), нижестоящие фазы → todo.
4. Свежий `emit-prompt` → проверить, что новый файл реально вошёл в packet (grep имени в /tmp/task.md) → единственный фоновый `invoke-role`.

Питфоллы правки контракта:
- `purpose:` со значением, содержащим `: ` (двоеточие-пробел), кавычить строку целиком — иначе emit-prompt падает `mapping values are not allowed here` и не создаёт prompt-файл.
- Fuzzy/context_aware-патч по YAML-контракту может вложить элементы списка под anchor (`- &id006` становится вложенным списком, отступы съезжают молча) — после любой правки контракта проверять структуру списка ДО emit; ошибка YAML всплывёт при emit, но чинить структуру надо раньше.
- Вердикт исследования возвращает архитектор, ревизор оценивает независимо; оркестратор запускает роли и доставляет результат владельцу. Если вопрос без изменения графа — консультационный канал архитектора (раздел «Консультационный канал архитектора»), но не собственный сбор данных.

## Входы-артефакты до emit: AC-list.md (HF:plan), --master-tz + handoff-contract (TZ:patch)

`emit-prompt` по ряду фаз падает ДО генерации промпта, если в каталоге поезда нет обязательного входного файла — ошибка `required input missing: <path>`. Создать файл до emit, а не пересобирать промпт руками.

- **`HF:plan` не эмитится без `AC-list.md`.** Брать AC из раздела критериев приёмки мастер-ТЗ пакета (напр. Б58.6 → AC-138…149), добавить Non-goals и ссылку на раздел плана с IAC. После создания — повторный `emit-prompt` собирает packet со scope.
- **Новому поезду (init CHANGE) `brief.md` с блоком ```handoff-contract``` нужен ДО ПЕРВОГО emit — уже на `TZ:compress`, а не только к `TZ:patch`.** Без контракта первый компрессорный invoke падает `canonical_artifact_fail`/«output outside write_scope»: packet приходит с `write_scope: []`, роль пишет extract, приёмка отвергает. Это класс fence-contract, а НЕ дефект публикации компрессора — лечится созданием контракта и повторным emit→invoke, а не разбором публикации/не ручным «канонизированием». Контракт нового поезда объявляет write_scope/outputs/inputs для ВСЕХ фаз рецепта сразу (TZ:compress — каталог слага; TZ:patch — каталог слага + master; HF:impl/test — каталог слага + Registries/pipeline/; ORCH — Registries/), формат копировать из brief.md уже прошедшего поезда, не изобретать.
- **`TZ:patch` требует `--master-tz <путь>`** (иначе: `master binding required; DevWorkflow fallback is forbidden`) **и `brief.md` с блоком ```handoff-contract```** в каталоге поезда; без контракта packet приходит с `write_scope: []` → invoke падает `output outside write_scope` на первом артефакте.
- После emit сверять в свежем packet фактические роли и `write_scope` (не пустой, содержит каталог слага), а не доверять rc=0. Packet лежит в `dev/<slug>/context/<hash>.json` (свежий по mtime), а не рядом с `--out`-файлом; роль/фаза — `task.role`/`task.phase`, scope — `boundaries.write_scope`.

## HF:backup — оркестраторная фаза со снятием baseline до правок

`HF:backup` — роль `sirene`, не LLM (`emit-prompt` запрещён G6: `g6: emit forbidden for sirene phase`). Не dispatch — выполнить действие и закрыть `complete-phase` с уликой. По HF-plan §4 сохранить baseline **до** правок HF:impl:

1. Весь write-set из `evidence/HF-plan-allowlist.paths` (пути относительно `Registries/` runtime) + наличие/отсутствие новых тестов, bytes/hash/mode каждого файла + git HEAD + защищённые (read-only из плана) файлы.
2. Архив `backup/HF-backup-<UTC>/` с `manifest.txt` (sha256+mode+path) + указатель `evidence/HF-backup.md` (таблица файл/SHA/mode).
3. Верифицировать чтением+sha каждого файла из backup против runtime ДО записи в manifest; при несовпадении — переделать, не закрывать фазу.
4. Runtime `Registries/` может быть `no-git-in-runtime` — тогда G3/собственный commit идут из candidate C на HF:impl, не из runtime.

## HF:backup refresh — источник closure = принятый candidate, НЕ live-roots

Refresh между ревизиями НЕ должен пересобирать новую candidate-базу из live-roots поверх старого carry-over patch. Live не содержит фиксов предыдущей ревизии, которые пока живут только в принятом candidate (их правки вносит HF:impl, а в live они попадают лишь после GATE). Такая пересборка молча теряет уже принятый фикс и регрессирует ранее закрытый блокер — например, фикс `_in_scope` (покрытие детей каталога-в-scope без trailing slash) из рев. N пропадал из pipeline_context, и новый HF:test/prep снова падал `output outside write_scope` на каталоге без `/`.

- **Источник closure для refresh — последний ПРИНЯТЫЙ candidate HEAD (все его фиксы), а не live.** Переносить carry-over из ранее одобренных якорей недостаточно: адресные фиксы конкретной ревизии в старых якорях отсутствуют.
- **После refresh сверять результирующий candidate с прежним принятым HEAD по функциям/правкам ревизии, а не только по набору путей.** `git diff --name-status` покажет «те же 10 путей» и пройдёт `diff --check`, даже когда ранее закрытый признак (скоп каталога без `/`, контракт, refusal) вернулся к старой форме. Конкретно: сравнить тело функции (`grep -A3 '_in_scope'`) и проверить живым тестом `_in_scope(ABS_child_within_scope_no_slash, write_scope) == True`.
- Механизм регрессии: helper-функции могут прийти из carry-over (видны в candidate), но сам `_in_scope` остаться старой формой — отсюда ложное впечатление, что фикс на месте. Проверять именно целевую поведенческую ветку, не наличие помощников.
- Если ранее закрытый блокер рецидировал из-за этой механики — это повтор «стоп + диагноз» из-за rebuild, а не из-за нового дефекта исполнителя; в диагнозе архитектору указать, что фикс рев. N был потерян на refresh (live vs accepted candidate), не как регрессия кода.

## Возврат по не-rev-фазе (HF:test FAIL → HF:impl) — два шага, второй обязателен

`addressed_rework` мапит ТОЛЬКО review-источники (REV:tz→TZ:patch, REV:plan→HF:plan, REV:report→RS:analyze); для возврата от исполнительских фаз (HF:test/impl) контрактного rework-пути нет. После оркестраторного `write_state` возврата цели (`HF:impl`→doing, `HF:test`→done, событие `rev_request_changes_rewind`) ОБЯЗАТЕЛЬНО добавить evidence провалившейся фазы во `inputs.<target>` контракта (`evidence/HF-test.md` с `purpose`, описывающим exact missing: конкретные nodeids/оракулы). Без этого повторный `emit-prompt` даёт `kind: forward, request: null` — исполнитель НЕ увидит требование rework и воспроизведёт ту же незавершённость (напр. 7 coarse B59-тестов вместо 293 approved parametrized IAC nodeids). Правка контракта — адресная, уполномоченным writer'ом плана вне executor-фазы; сверять `_contract(st)['inputs'][target]` и только потом emit.

- Общий принцип: emit несёт в контекст роль только то, что объявлено во `inputs` контракта целевой фазы. Причина перемотки существовала в phase-объекте — достичь роли в промпте через контрактный вход.
- Приемлемый вердикт HF:test для доработки — FAIL/REQUEST-CHANGES; из него берём требование (exact nodeids минус фактическая collection = отсутствуют для всех IAC).

## Механический prerequisite подаётся в контракт evidence-файлом до emit

Если план объявляет вход с `purpose` «future actual … must exist before review/implementation, not fabricated» — оркестратор обязан создать его ДО REV/impl emit: emit падает `required input missing: …/evidence/<имя>` до генерации промпта. Пример — inventory sync после TZ:finalize: архитектор кладёт `TZ-finalize-r1-inventory.proposed.md` + `.diff` + `handoff.json` (`applied:false`, scope PENDING_AUTHORIZED). Оркестратор: сверяет preimage-хэш с текущим файлом инвентаря (совпадение обязатедьно, иначе stale), применяет proposed на `MAIN_TZ_INVENTORY.md` атомарно (чтение→tmp→replace), пишет `TZ-finalize-r1-inventory-sync.json` (before/after/proposed/master diff/readback) — и только тогда REV:plan/HF:impl emit проходит. Хэши после-файла и master сверять, не полагаться на rц/впечатление.

## complete-phase требует И --reason И --evidence — иначе тихий rc=2

`pipeline complete-phase --slug <s> --phase <p>` молча возвращает **rc=2 без сообщения на stderr**, когда опущено `--reason` ИЛИ `--evidence` (`cmd_complete_phase` делает `if not ns.reason or not ns.evidence: return 2`). Ф��за при этом остаётся `doing`, `next` возвращает прежнюю фазу — выглядит как «complete не сработал», хотя причина просто в недостающем аргументе.

- Давать оба аргумента с первого раза: `--reason "<вердикт>" --evidence "path=<abs> verdict=... "`. Один голый `--evidence` без reason не завершает.
- rc=0 + фаза всё ещё `doing`/`next` возвращает ту же фазу = проверять, оба ли аргумента были переданы, прежде чем лезть в state/guard. Тихий rc=2 маскируется под «guard заблокировал».
- Вывод команды собирается в stderr; при перенаправлении `>out 2>&1` и пустом stdout/пропавшем rc сверять реальный exit (`echo rc=$?` без pipe), а не полагаться на хвост пайпа.
- **`recover` предъявляет те же требования `--reason` И `--evidence` — без них тоже тихий rc=2.** `cmd_recover` делает `if not ns.reason or not ns.evidence: return 2` (одно из двух опущено — фаза не разблокируется, выглядит как «recover не сработал»). Давать оба аргумента сразу: `recover --class <cls> --reason "..." --evidence "path=... ..."`; `--evidence` на сбойный proveфайл/вывод инвойка, а не только на артефакт роли.

## Разблокировка budget_exhausted:phase-turns после решения владельца

`budget_exhausted:phase-turns` — NON_RECOVERABLE_FAIL: молчаливый перезапуск и сброс без явного решения Саши запрещены. Когда Саша дал адресное разрешение на разовый сброс, действуем штатным writer'ом, а не правкой JSON руками:

1. Бэкап `_state.json` в `evidence/` (путь сохранить в evidence события).
2. `st = pipeline_state.read_state(slug)`; в `ph = st.phases[<фаза>]`: `ph['turn_count']=0`, `ph['fail_class']=None`; на `st`: `status='in_phase'`, `phase=<фаза>`, `pid=None`, `ph['pid']=None`. Разблокировку прочих фаз не трогаем — только одна фаза исчерпания.
3. `write_state(st, event={'event':'repair','actor':'sirene','phase':<фаза>,'reason':<решение Саши + были turn_count/лимит/fail>, 'evidence':'backup=<путь> old_turn_count=… limit=… unlock_type=<фаза>-only'})`. В reason держать факт «разовый сброс по решению владельца» и указать, какие прочие счётчики (turn_count других фаз) НЕ менялись.
4. Проверить readback: `turn_count=0`, `fail_class=None`, `status='in_phase'`, `phase` верный.
5. Свежий `emit-prompt --phase <та же фаза>` → ЕДИНСТВЕННЫЙ фоновый `invoke-role` (`background=true`). Очередной транспортный срыв — стоп и диагноз, НЕ повторный сброс.

Механика и питфоллы:
- `import pipeline_state` падает (`ModuleNotFoundError`) — модуль является пакетом `pipeline.*`; правильный импорт при манипуляциях state: `sys.path.insert(0,'/home/tkachenkoav/WorkVault/Registries')` + `from pipeline import pipeline_state`. Тот же PYTHONPATH нужен для `python3 -m pipeline.cli`. execute_code-песочница `pipeline_state` не имеет — запускать через `terminal`/локальный python, а не через execute_code.
- `write_state` — модульная функция, не метод объекта: `pipeline_state.write_state(st, event={...})`. Объект `st` не имеет `write_state_event`; вызов `st.write_state_event(...)` падает `AttributeError` до записи. Мутировать поля напрямую на `st` (после `read_state`), записывать модульной `write_state(st, ...)`.
- Сброс только `turn_count` БЕЗ очистки `fail_class` не разблокирует: `classify_doing` смотрит `fail_class in NON_RECOVERABLE_FAIL` и продолжает возвращать INTERRUPTED. Чистить оба поля вместе.
- Лимит фазовых ходов зависит от префикса фазы (phase_turns.py): GATE=4, HF=25, остальные (TZ/REV/BUG/RS/MIG/DEC/default)=20. После сброса `turn_count=0` даёт один полный бюджет на повтор.
- Разрешение «доделай до финала» или «продолжай» само по себе НЕ сбрасывает бюджет — нужен явный запрос Саши на разовый адресный сброс, иначе это обход NON_RECOVERABLE_FAIL.
- Нет отдельной CLI-команды reset бюджета; `pipeline repair` восстанавливает индекс, а не бюджет. Разблокировка — только через штатный writer, как выше.

## Блокер границы write-set (исполнитель упёрся в read-only target)

Когда исполнитель честно возвращает `ARCHITECT_REVIEW_REQUIRED` / `PARTIAL_REWORK_COMPLETE` с `ready_for_HF_test=false` и scope-request, в котором два класса причин:

1. **Недоделка в рамках своего write-set** (матрица §5, test_case_trace, G01..G10, publication/multipart/rollback, A→B) — это НЕ повод везти на HF:test (получишь тот же FAIL) и НЕ повод молча гонять третий круг одного исполнителя после двух неполных результатов. По Б55.5 после 2-го круга того же класса — стоп и варианты Саше (смена модели / принять частичный с известным FAIL / пересмотр плана) с рекомендацией.
2. **Дефект в read-only файле вне approved write-set** (например `pipeline_gates.next_action` с повторяющимся GATE, или три фixture `test_invoke_fatal` без slug/phase, или doorbell-скрипт с hardcoded root) — канон адресного расширения, тот же что для doorbell:
   - оркестратор ВОЗВРАЩАЕТ фазу владельцу-архитектору (`HF:plan`), НЕ вызывает `invoke-role --role architect` на фазе исполнителя (G6 отклоняет: role != expected);
   - вердикт владельца: `REWORK_REQUIRED` + новая редакция плана с адресным расширением write-set (точные final/candidate mapping, узкая цель, сохранение never-auto/guards/recipe/G6/constants, БЕЗ ослабления AC/IAC и БЕЗ переноса выбора норм на HF:test);
   - `REV:plan` APPROVE новой редакции → **supplemental backup добавляемых файлов ДО их правки** → `HF:impl` продолжает тот же полный объём;
   - **Если write-set вырос на ДРУГОЙ редакции REV (например 23→25 поверх уже забэкапленного 21→23)** — новый supplemental backup нужен именно для новых target'ов (их candidate+active копии), привязанный к прежнему backup; старый backup не покрывает вновь добавленные файлы. Прежние до-правки не повторяются, кандидат не пересоздаётся.
   - адресный дефект вне write-set НЕ оформлять как BUG/known-issue вместо обязательного IAC (новый красный IAC не допускается); расширение — не новый запрос Саши, если контракт/AC не меняются.

Supplemental backup: копии candidate+active добавляемых файлов + manifest (path/exists/mode/size/sha256) + unpack-проверка перечитанным хешем. Write и verify обязаны строить путь К одинаково: расхождение (label-подкаталог против плоского имени) даёт FileNotFoundError в начале проверки.

## Стоп-гард Саши на эскалации: «при следующей эскалации — стоп» — императив выше авто-цикла

Когда Саша объявил стоп-условие по эскалациям (напр. «останови работы если будет ещё одна эскалация исполнителя к архитектору»), это ИМПЕРАТИВ, который перекрывает штатный авто-цикл «исполнитель → архитектор → независимая REV → продолжение HF:impl». Держать его как действующий стоп-режим на поезде, а не как одноразовую реплику в переписке.

- **Зафиксировать решение в памяти/привязке поезда сразу**, чтобы «стоп при N-й эскалации» не потерялся за ходом фаз. Пока эскалаций нет — поезд едет штатно; как только исполнитель вернул `ARCHITECT_REVIEW_REQUIRED`/`PENDING_REV` на этом поезде — СТОП и доклад Саше с вариантами (дать архитектору ещё один цикл / снять запреты плана разово, чтобы исполнитель сам закрывал такие случаи / пересмотр плана), рекомендация. САМ авто-возврат на архитектора не делать, пока Саша не решил.
- **Прогресс исполнителя внутри write-set без эскалации (PARTIAL_IMPLEMENTATION_PENDING_MATRIX, H0N устранён, кандидат чист) — НЕ триггер стоп-режима:** это штатный шаг к матрице/169, его продолжать. Стоп-режим срабатывает только на повторный возврат к архитектору.
- **После PARTIAL-завершения executor оставляет в state мёртвый pid (процесс уже вышел, exit!=0/finished) — очистить его штатным writer'ом перед следующим ходом:** `pipeline_state.read_state` → `st.pid=None`, `phases[<фаза>].status='todo'`, `phases[<фаза>].awaiting_invoke=True`, `write_state(event={'event':'repair','actor':'sirene',...})`. Счётчики (turn_count/recover_counts) НЕ трогать — PARTIAL-продолжение и смена модели по распоряжению не повторный трей. Затем свежий `emit-prompt` (новый packet) + единственный фоновый `invoke-role` той же фазы на том же кандидате, готовый к матрице/regression.

## Смена модели исполнителя посреди поезда по распоряжению Саши

**Потолок low-reasoning исполнителя — это не объём, а модель.** Когда исполнитель по АДРЕСНОМУ (узкому) раунду вернулся БЕЗ изменений кода и коммита — только пере-верификация прежних тестов и «осталось вернуть владельцу» — дальнейшие раунды той же модели на том же контракте не продвигают. Это не класс «разбей на W-части» (разбиение уже сделано), а потолок роли. Действие: (1) запросить у архитектора АДРЕСНЫЙ вердикт по остатку — по каждой группе OWN / DEPENDENCY (куда переносится) / ПЕРЕСМОТР КОНТРАКТА, с точными component assertions и коротким чек-листом следующего раунда; (2) если адресный раунд low-reasoning снова лёг без кода — поднять владельцу вопрос о СМЕНЕ МОДЕЛИ исполнителя на более сильную (codex-контур), не крутить N кругов одной модели. Стоимость сильной модели выше (3.5M input против 0.4M у low), но один её раунд закрывает то, что low не закрыл за 16. Границу «P22» и ослабление oracle — только через дельту архитектора + согласие владельца, не бесконечными раундами.

Перевод исполнителя на другую модель (напр. сол → terra «снимаю сол дол») — распоряжение владельца, применяется адресно, конфиг ролей не меняется:

1. Остановить работающий фоновый invoke (`kill` wrapper pid; уведомление-нотиф будет exit -15 SIGTERM — ожидаемо). Процесс codex уходит, evidence текущего шага остаётся.
2. Сбросить мёртвый pid штатным writer'ом: `write_state(event={'event':'repair','actor':'sirene',...})` → `pid=None` для фазы. Turn_count НЕ сбрасывать — это смена модели по распоряжению, не повторный трей.
3. Свежий `emit-prompt --phase <фаза>` (каждый emit = новый packet_id) и фоновый `invoke-role` БЕЗ `--model` — тогда резолвится дефолт роли из `EcosystemConfig.yaml tools.dev_workflow.roles.<role>.model` (напр. executor→gpt-5.6-terra). Проверить фактическую модель по rollout (`grep -oE 'gpt-[0-9.a-z-]+'` — преобладает новая), а не доверять строке status.
- Императив «снимаю модель X» = последующие invoke на роли идут на дефолт (БЕЗ `--model X`); разовое `--model` из прежних решений владельца больше НЕ использовать.

## Прерванный фоновый codex-прогон оставляет незакоммиченный срез, который может вешать тесты

The `background codex exec` (exit 143/SIGTERM, прибит таймаутом/внешне) оставляет правки в worktree НЕ закоммиченными и НЕ проверенными — финальный `agent_message` раунда может хвастать прогрессом, но срез может быть невалиден: полный pytest виснет даже с `-x` и bounded timeout (RC=124), значит тест зациклен/заблокирован. Не доверять прерыванию и его сообщению: прогнать pytest с bounded timeout в отдельный файл; если завис/упал — `git checkout -- <пути>` до стабильного HEAD и ПЕРЕЗАПУСТИТЬ раунд начисто. Незакоммиченный срез прерванного раунда не является evidence; HEAD не сдвинулся — откат безопасен и не теряет работу роли.

## `repair` CLI ≠ возврат фазы; возврат — событие `write_state(event=repair)` + `next`

`pipeline repair` (CLI, `pipeline_queue.cmd_repair`) — глобальный ремонт очереди (drain/индекс), НЕ механизм возврата фазы: после него `next` стабильно возвращает ту же активную фазу. Возврат FAIL→rework и перемотка на владельца-архитектора делаются ТОЛЬКО `pipeline_state.write_state` с событием `repair` (см. «Имя события в write_state — только закрытое» в references) и затем `next`. Имя события `repair` в записи удерживает вердикт FAIL/причину в `reason` и `evidence` с `path=`.

## Блокер в фазе роли: вердикт архитектора через ЕГО фазу, не через фазу блокера

Когда HF:test/impl-фаза (role=executor) упёрлась в блокер и нужно решение архитектора — НЕ вызывать `invoke-role --role architect` на этой фазе: G6 берёт роль из фазы (`expected executor for HF:test`) и отклоняет. Канонный путь — перемотка: writer-событием `repair` вернуть активную фазу на штатную фазу архитектора (HF:plan/REV:plan), `next` → `WORK`, emit→invoke там, вердикт записывается в канон этой фазы.

- **Просто перевести фазу-исполнителя в `todo` недостаточно, чтобы `next` ушёл на владельца-архитектора.** `next` возвращает первую не-done фазу по рецепту; если фаза-владелец (HF:plan) уже `done`, а исполнительская (HF:impl) — `todo`, `next` снова даст `WORK HF:impl`, а не перемотку. Чтобы принудительно получить роль владельца, выставлять явно writer-событием `repair`: фазу-владельца → `doing` + `awaiting_invoke=True` + `pid=None`, `st.phase=<владелец>`, `st.status='in_phase'`; только тогда `next` → `WORK` на нужной фазе.
- **Двухногая петля «вердикт архитектора → ревизия»: после `complete-phase HF:plan` `next` ПРОПУСКАЕТ REV:plan и прыгает на HF:impl.** Когда архитектор вернул `PENDING_REV`/`REWORK_PROPOSED_PENDING_REV`, независимая `REV:plan` новой редакции обязательна ДО продолжения реализации, но `next` после complete владельца идёт к первой не-done (импл). Надо отдельно переоткрыть REV:plan тем же writer-репом: `REV:plan` → `doing`+`awaiting_invoke=True`+`pid=None`, `HF:impl` → `todo`, `st.phase='REV:plan'`, затем `emit-prompt`+`invoke-role reviewer`. Сверять target `next` с задуманной фазой на каждом шаге петли (владелец → ревизия → импл), не доверять `next` сам по себе.

## Разбор первопричины серии возвратов: полная проверка постановки одним проходом

Когда исполнитель эскалирует к архитектору «план предписал одно, код ведёт себя иначе» несколько раз подряд (H01/H04, H05…), первопричина — не исполнитель и не модель, а архитектурная проработка: запретительная норма объявлена неизменяемой без проверки, что ВСЕ ветви реального control flow ведут себя как заложено; независимый REV согласовал эти неверные допущения. Владелец (Саша) спрашивает: можно ли ВСЕГДА так делать при возврате — архитектор заново перепроверяет всю постановку, ревизор перепроверяет допущения. Ответ architect: да, сужается по классу (не всякий возврат требует полного разбора, но повторяющаяся серия — точно).

**Методика формализована в регламент dev-процесса (норма Б55.3 «Проверка влияния возврата и допущений постановки» + блок в dev-workflow SKILL.md).** При каждом возврате архитектор фиксирует причину, затронутые допущения и границу повторной проверки; улика, опровергающая допущение постановки или конфликт запретов/scope, обязывает проверить все связанные маршруты одним проходом. Ревизор независимо проверяет основания границы и истинность существенных допущений (исходник/версия SDK/трасса/воспроизведение; «так уже работает» и исторический зелёный regression недостаточны). Глубина по классу: локальная незавершённость — точечно; противоречие постановки факту/SDK или затрагивающее запреты/scope — сквозная перепроверка всей границы; опровергнутое общее допущение — полная перепроверка. Это изменение регламента — внесено в Б55.3 ТЗ и в скилл; оркестратор обязан соблюдать.

- **Отличать PARTIAL_IMPLEMENTATION_PENDING_MATRIX / незавершённую матрицу от контракт/scope-конфликта.** Честный промежуточный PARTIAL (H0N устранён, кандидат чист) требует только продолжения реализации, НЕ архитектурного круга. Возврат оправдан лишь при настоящем конфликте нормы и поведения (можно частично принять/не того oracle и т.п.).
- **Лечение — не снятие запретов, а проверка допущений одним проходом.** Снять запрет менять смысл native response/provider policy = скрыть дефект планирования, а не устранить. Перед следующей большой порцией исполнитель делает ОДНУ сквозную проверку всех оставшихся границ с таблицей `§/IAC/ID → actual owner/call chain → input → expected rc/deltas → observed trace → allowed fix / conflict / NOT_RUN`; недостижимый node остаётся `NOT_IMPLEMENTED`, не PASS. Полный список границ и что в них сверять (resolver→SDK, SDK→worker→parent→classifier, split/coverage→publisher, MIG/fatal, handoff/legacy, выпуск/launcher) — `references/escalation-root-cause.md`.
- **Вердикт архитектора «продолжить согласованный r7, новая ревизия не нужна» (`CONTINUE_APPROVED_R<N>_NO_SCOPE_CHANGE`)** — когда оба конфликта уже имеют APPROVE+реализацию, а разбор фиксирует порядок работы без изменения IAC/write-set/AC/запретов. Тогда отдельная REV:plan ради самого разбора не требуется; но если дальнейшая улика меняет согласованное решение — предметная архитектура и независимая REV обязательны.
- **Architect-роль может завершиться `exit 4` с активным вердиктом в evidence**, если итог не оформлен как правка HF-plan.md («пиши в HF-plan.md, канон не обновлён»). Вердикт уже сохранён в `evidence/ARCHITECT-*-VERDICT.md`; принимать его оттуда, не теряя: полный вердикт + root-cause + порядок до GATE. Фазу завершать им же.
- **Ожидаемый выигрыш методики:** исчезают архитектурные/REV-круги ради уже разрешённой работы и промежуточных PARTIAL; связанные допущения проверяются одним проходом. Число НЕОБХОДИМЫХ независимых REV при изменении контракта сокращением правил НЕ снижается.

## HF:test `FAIL_MATRIX_INCOMPLETE` — семантика матрицы и путь возврата

Вердикт `FAIL_MATRIX_INCOMPLETE` на `HF:test` (matrix_required=169, collected_exact_nodes=76, missing=93) означает, что тест-узлы матрицы (parametrized scenario nodes) НЕ реализованы в корпусе — это незавершённость реализации, а не дефект runtime.

- **Матрица — спецификация ИСПОЛНЕНИЯ, не результат:** узлы создаются на `HF:impl` (parametrized test-functions), исполняются отдельно на `HF:test`. Полный зелёный regression при неполной collection НЕ даёт readiness — `FAIL_MATRIX_INCOMPLETE` остаётся FAIL даже если весь корпус зелёный.
- Возврат — `repair`-событием вернуть на `HF:impl` (owner-executor) добавить недостающие parametrized узлы. Это локальная незавершённость по Б55.3 (точечное исправление), НЕ эскалация к архитектору; architect-круг не нужен. Диагноз писать файлом в workspace.
- После доделки матрица собирается 169/169 `missing=[]`, и только тогда снова отдельный `HF:test`.

## `complete-phase --evidence` требует `path=`/`sha256=`/`session_id=`

`pipeline complete-phase --evidence "verdict=... ready=..."` без `path=`/`sha256=`/`session_id=` молча возвращает rc=0 с сообщением «evidence must include path= or sha256= or session_id=» и НЕ завершает фазу — выглядит как успех. Всегда включать `path=<абс>` на итоговый evidence-файл в дополнение к вердиктным полям.

## Повторный идентичный verdict — сигнал отсутствия прогресса, не случайный сбой

Два подряд прогона одной фазы, вернувшие одинаковый verdict с ОДИНАКОВЫМ evidence sha (напр. два `PARTIAL_DEV_ONLY` на одном IAC с одинаковым summary_sha256), означают «исполнитель не может закрыть пункт без изменения инструкции», а не транзиентный сбой. Сравнивать `summary_sha256`/`reason` соседних evidence; при совпадении — СТОП и доклад владельцу с вариантами (явно конкретизировать объём прогона / запросить архитектора по выполнимости на этой фазе / пересмотр плана), НЕ запускать третий идентичный прогон.

## Живой хвост: HF:test rework и ORCH rollout

После REV:plan APPROVE до GATE:done действуют процедуры rework-петли (HF:test FAIL → перемотка `repair` обеих фаз HF:impl/HF:test → emit ОДИН раз, диагнозы класть файлом в workspace, не править промпт) и rollout (ORCH:shared-state по write-set: mapping, только отличающиеся allowlist, restore-all-skills.sh, git-коммит скилла, импорт финальных модулей по `__file__`+sha, skill_view-content sha == candidate, installed-smoke из FINAL P, GATE:done после evidence). Полный текст — `references/live-tail-rework-and-rollout.md`.

- **`next` после переоткрытия ранней фазы прыгает на первую не-done, а не на переоткрытую.** `complete-phase` + `next` идут вниз по рецепту от текущей точки; переоткрытая перемоткой фаза не обязана стать следующей. Сверять target `next` с задуманной фазой, при расхождении выставлять активную фазу явно writer-событием `repair` (phase + status, без прямого JSON-write).
- Фоновый invoke архитектора может таймаутнуться (foreground 180 s) ПОСЛЕ записи `invoke_prepare` — остаётся мёртвый PID. Это recoverable `dead-pid` на той фазе (отдельный класс от `empty-result`), один corrective-повтор разрешён; `recover_counts[HF:plan][dead-pid]` считать и не обнулять.
- Разные классы сбоя (`empty-result` vs `dead-pid`) — независимые recover-счётчики на одну и ту же фазу. Второй голый повтор того же класса запрещён; смена причины/класса для обхода лимита — тоже обход, фиксируется как дефект.

## Bootstrap-петля: фикс, который разблокирует саму роль, вносит оркестратор

Когда первопричина пустого invoke — роль, увидев живой `st.pid` (свой wrapper), решает «работа уже идёт» и ждёт вместо выполнения, а лечащий фикс обязан писать тот же `invoke_role.py`, который LLM-роль не может внести, пока его не получит — это петля. Единственный размыкатель — **адресный не-LLM фикс оркестратора** в согласованном write-set (прецедент принят ревизором), затем повторный invoke с внедрённым исправлением. Сам исполнитель эту петлю не разорвёт.

- **Ремонтный поезд для дефекта финализации может сам упереться в тот же дефект на первой ролевой фазе.** Роль пишет полный артефакт, но `invoke_fatal`/G2 не даёт `complete`; третий идентичный invoke запрещён. Не гонять его и не править proof руками: собрать полный контекст (ТЗ, журналы обоих поездов, код, логи) и отдать архитектору на вердикт — он разложит дефект на составляющие (публикация / классификация fatal / packet) и назовёт адресный не-LLM фикс. Применять фикс оркестратором с бэкапом и юнит-проверкой, затем свежий `emit → invoke` той же фазы с сохранением `turn_count` и истории.

- Диагноз «роль не сделала» НЕ равен «guard заблокировал». Проверять сессию codex-rollout на вызовы `occupancy_blocked`/`invoke_wrapper_alive` — их отсутствие в tool-calls доказывает, что роль САМА решила ждать (ролевая инструкция, не программа). Гипотезу о программной защите опровергать трассами, а не названием `interrupt`.
- Лечение — `invocation_context` в начале промпта: slug/phase/role/PID wrapper + «живость wrapper ожидаема до твоего возврата; выполни работу и запиши артефакты; не жди/мониторь свой wrapper; не зови lifecycle CLI». Отдельный guard/`exclude_pid` для этого не нужен — менять передачу задачи, а не occupancy.
- **Расширение сигнатуры помощника ломает ручные mock-фикстуры в тестах, которые ты не гонял.** Добавил keyword-only `invocation_context` к `run_codex`/`run_cursor_cli` — падают `fake_run` в `test_turn_end.py`/`test_invoke_resolution.py`, подставившие прежнюю сигнатуру; они в shard'ах полного V1, которые точечный регресс не накрывает. Перед расширением сигнатуры `grep` по дереву тестов на вызываемый символ, обновить все fake_run/патчи вместе с контрактом; затем гонять ПОЛНЫЙ компонентный V1 (`pipeline/tests -k 'not procedure_trace and not pilot_trace'`), не только точечные тесты.

## Блокер публикации выжимки (TZ:compress): не ретраить, не канонизировать вручную

Когда `complete-phase TZ:compress` отклонён `compressor publication/prepare/result identity mismatch`, а `extract_key`/`extract_of_tz_version` в state остались на старой версии (затем `check`/emit на ЛЮБУЮ фазу падает `G1: extract version drift` — поезд заперт) — это обрыв публикации, а не дефект выжимки:

- codex-компрессор пишет `extract*.md` как артефакты, но `publish_validated_extract` вызывается только в native-пути (`run_hermes_internal`), не в codex-ветке. Симптом: файлы на диске есть, публикация в state не выполнена.
- **TZ:compress — РОЛЕВАЯ фаза (role=compressor), НЕ sirene.** После исправления `write_scope` (создан контракт, packet не пуст) `check` всё равно вернёт `G2: accepted context packet required`, и закрыть фазу оркестратором/`complete-phase` без принятого пакета нельзя — нужен реальный `emit-prompt → invoke-role compressor`, который и зарегистрирует accepted packet в `context_packet`. Не пытаться закрыть compress как sirene-фазу: `phase_requires_context('TZ:compress')` истина, гейт требует packet. Но и после успешного codex-invoke `complete` часто снова отказывает `compressor publication/prepare/result identity mismatch`, потому что `proof.extract_production` пуст (см. ниже) — это одна цепочка «роль записала → публикация не доведена», а не два отдельных дефекта.
- Не ретраить повторным `invoke-role`/`emit-prompt` — результат будет тем же: prepare-identity меняется, а публикации всё равно нет. Recovery-счётчики исчерпать легко; второй recover той же пары запрещён.
- Не «канонизировать вручную» и не вызвать `publish_validated_extract` в обход машины: части по канону обязаны иметь заголовок `## Часть N/M` (произвольные «# … часть 3/3» режутся на `forbid_silent_trim` как silent trim), а после публикации G2 сверяет файл со снapшотом `context_result.outputs` — расхождение даёт следующий блокер (`G2: result output changed`).
- Развилку (чинить codex-ветку публикации vs native-адаптер vs оформлять адресный ремонт конвейера) решает архитектор: собрать полный контекст (журнал поезда, state, неканонические extract-файлы, код invoke_role.py/pipeline_extract.py/pipeline_context.py, ТЗ пакета) и звать его консультационным каналом выше.
- **Вердикт A′ (codex-компрессор публикует сам):** в `run_codex` добавить `--output-last-message <уникальный файл>` и читать точный финальный ответ роли, а не разбирать JSONL-поток через `_split_compressor_parts(out)`; после успешного транспорта и fatal-проверки вызвать `publish_validated_extract` с identity текущего prepare, затем штатно писать `context_result`/receipt. Ошибка транспорта/coverage/identity не должна создавать успешный результат. Native-путь и остальные роли не менять.
- **Packet `BUG:diagnose` с литеральным именем канона:** `CANONICAL_ARTIFACT['BUG:diagnose']` хранит плейсхолдер `_fix_plan_YYYYMMDD.md`; `_outputs` объявлял его буквально, а роль пишет датированный файл → `check_result_outputs` режет `output outside write_scope`. Фикс: `_outputs` резолвит `BUG:diagnose` в конкретный `_fix_plan_<YYYYMMDD>.md`, а `build_packet_object` добавляет каталог задачи в `write_scope` (как для компрессоров). Проверять по свежему packet: `outputs[].path` — конкретный файл, `write_scope` содержит каталог слага.
- **Вердикт «адресный ремонт конвейера = отдельный пакет» — завстти НОВЫЙ BUGFIX-поезд на сам pipeline-код, а заблокированный поезд НЕ дорабатывать.** Когда дефект в runtime-коде конвейера (codex-ветка не публикует extract, и поезд заперт на TZ:compress) требует написания того же pipeline-кода, который LLM-роль не может внести в рамках своей фазы, — ремонт оформляется как отдельный поезд (`suggest-slug` → `init --case BUGFIX --origin-chat <chat> --origin-thread <thread>` → перевод в готовность writer-репом `Б55:готовность` с `phase=<первая фаза, у BUGFIX это BUG:diagnose>` → `next` → `WORK`), а не как адресная правка внутри текущего пакета. После внедрения ремонта вернуться к заблокированному поезду и штатно досжать extract под новую версию; диагноз поезд-ремонт и поезд-блокер не смешивать.

## `changed_files` каталогом и приём уже выполненного результата (3 препятствия)

Когда роль фактически сделала работу (артефакт на диске, diff=ровно write-set, G3 получен, свидетельство записано), но post-invoke верификация упала — это НЕ дефект реализации, а дефект декларации/финализации. Не переписывать код, не реинвокать, не править proof руками; разбирать по компонентам.

**Питфолл №1 — `changed_files` объявлен КАТАЛОГОМ в handoff-contract.** `output_snapshot` рекурсивно обходит все файлы через `_ref→_read`, который делает strict utf-8 decode; бинарный fixture в каталоге (`.sqlite`) роняет снимок (`'utf-8' codec can't decode byte ...`), и фаза падает на `check_result_outputs` ПОСЛЕ успешного invoke. План §4 требует changed_files = список файлов; каталог — распространённая ошибка контракта. Объявлять `changed_files` списком отдельных OutputRef (абсолютные пути по файлу), а не каталогом; бинарные fixtures не включать в declared write-set.

**Питфолл №2 — три самостоятельных препятствия при приёме уже выполненного результата.** (1) отсутствует `proof.context_result`/фазовый receipt (G2 требует принятый packet → prepare identity → result того же packet/prepare → совпадающий receipt → текущие outputs; `complete-phase` проверяет G2 ДО записи, поэтому отчёт+чистый candidate не заменяют конвейерный result); (2) drift входного плана — принятый packet пиннит FileRef плана по SHA+path+size+mtime, правка контракта после invoke меняет вход, возврат старого текста недостаточен; (3) старый packet объявляет свою форму outputs — нельзя записать новые outputs под старым packet_id, снимок всё равно снимется по старой форме. Все три независимы: один «починенный» (например, записанный ручной receipt) не закрывает остальные.

**Штатного `complete-phase`/`reconcile_invoke_result()`/`repair` для приёма нет** — они не восстанавливают пригодный context_result и не решают drift плана. Легитимный путь — отдельный спроектированный entrypoint исторической приёмки: (а) байтовый hash/size для нетекстовых outputs при строгом utf-8 для текстов (норма Б56.4), чтобы старый каталог с бинарным fixture принимал снимок; (б) проверенная последовательность без backend: подтвердить завершение точного wrapper и отсутствие связанных writers, проверить packet/prepare/backend-исход (отсутствие данных ≠ успех), адресно разрешить только точную связь old↔new FileRef диффа + независимый APPROVE, сверить baseline→tested commits/ровно changed paths/hashes/clean; (в) записать `context_result`+receipt+`changed_files` одним штатным `write_state(event=repair)` с readback/G2-проверкой; (г) reconciliation НЕ ставит фазу в done, фазу закрывает обычный completion. Повторная доставка того же proof — no-op; изменённый output/ref/identity — отказ.

**Когда ремонт — правка read-only конвейера (snapshot/entrypoint), заблокированный поезд не дорабатывать** — дефект вне write-set этапа, по канону адресного расширения/вердикта архитектора оформить отдельным BUGFIX-поездом на pipeline-код, а исходный поезд держать прерванным (candidate/evidence/state целы) до установки ремонта. Прогнать обе книги: экспорт и у себя, потом применить репорт к историческому вызову.

## Проверка целостности state: хэшировать НЕ весь файл

`_state.json` содержит поле `state_sha256` = хэш «тела» БЕЗ самого поля (canonical body через `to_dict`), а не сырой хэш файла. Сравнивать `sha256(файла)` с этим полем — всегда ложный CRISIS mismatch. Честную сверку даёт штатный `pipeline_state.read_state` (exit 0 = консистентно) — он пересчитывает из тела. Не перепроверять подлинность ручным sha файла; верить штатному read. `doorbell_tick.sh` в `CRISIS: state_sha256 mismatch` обрывается, только когда `read_state` сам упал — это настоящий сбой, не артефакт мануальной сверки.

## Где хранить уроки: `skill_manage` пишет только физические скиллы профиля

`skill_view` читает скиллы-симлинки на `~/hermes-workspace/skills/` (dev-workflow, hermes-multi-profile-skills), но `skill_manage` (patch/write_file) на них отвечает «Skill not found in active profile» — резолвер не ходит сквозь симлинк на git-репо. Имя с категорией (`devops/<name>`) не помогает. Уроки, относящиеся к `dev-workflow` (недоступен для записи), хранить здесь, в `dev-graph-train-ops` (физический профильный скилл), а непосредственные правки скилла делать в `~/hermes-workspace/skills/` файловыми инструментами + git.

## Строгая проекция не роняет весь индекс

`pipeline_queue.project()` валидирует checksum каждого `_state.json`; строгий `raise` на битом/чужом state (например, записанном старой схемой без поля, которое теперь входит в `to_dict`) роняет `rebuild_index`, а через него — `emit-prompt` И `write_state` для **всех** слагов, не только битого. Ошибку ловить per-slug: писать в `anomalies`, исключать слаг из `entries`/`ready`, `rebuild_index` всегда пишет индекс. Прежде чем добавлять строгую проверку в проекцию — продумать миграцию старых state или fallback в anomalies; чужой битый слаг не чинить (не наш write-set). Проверочная команда после фикса: `rebuild_index` даёт count остальных слагов и anomalies с именем битого.

## Системные файлы — protected-запись через approval-гейт

SOUL/AGENTS/HERMES и профильные memories идут через approval-гейт платформы; таймаут без ответа = НЕ согласие (`silence is not consent`). Повторять заблокированную запись и обходить через terminal/execute_code запрещено. Оркестратор при применении согласованных системных replacements (§3.2/§4 плана): применяет по одному файлу, фиксирует применённое в evidence, при блокировке останавливается и спрашивает Сашу с вариантами (применить оставшееся / частично / стоп), показывая частичное состояние. Системные правки планировать так, чтобы код и скиллы (не protected) применялись первыми, иначе пакет останется частичным без решения.

## Выбор codex-модели: алиас проверяется probe'ом, а не паттерном версии

Разные роли codex не следуют одной схеме версионного суффикса (`gpt-6.1-astra` НЕ существует при том, что `gpt-6-astra` есть; `gpt-6.1-sol`/`gpt-6.1-terra` — есть; `gpt-6-terra`/`gpt-6-sol` частью нет). Никогда не выводить правильный алиас роли из имени другой роли и не доверять строке в `EcosystemConfig.yaml`/статусе без проверки.

- **`model_not_found` HTTP 400 от codex = несуществующий алиас, а НЕ транспортный сбой.** Это не recover-класс, не dead-pid, не provider_fatal для повторного invoke той же роли: каждый `emit-prompt → invoke-role` этой роли будет падать на том же 400, пока не исправлен алиас в конфиге. Лечение — поправить `tools.dev_workflow.roles.<role>.model` на probe-подтверждённый алиас (через конфиг ролей, бэкап), затем свежий emit+invoke. Не тратить recover-класс и не гонять роль вслепую против заведомо мёртвого алиаса.
- **Проверять алиас до назначения роли/консультации** рабочей формой `run_codex`: `codex exec -C <ws> --skip-git-repo-check -m <alias> --json --sandbox danger-full-access -- "Reply with exactly: OK"`. `item.completed` + `agent_message "OK"` = алиас существует; error-envelope `model_not_found` 400 = нет. Probe даёт решение за секунды и экономит ход invoke.
- Когда `role.model` в конфиге неверный — исправлять ВЕЗДЕ, где роль упоминается (EcosystemConfig.yaml, `config.example.yaml`, нормализованные скиллы/`references`, где зафиксирован алиас), чтобы повторно не спотыкаться; проверять grep на старый строковой алиас после правки.
- Правка алиаса в конфиге ролей ≠ «смена модели по распоряжению»: тут правится постоянная модель роли (она была задана неверно), а не разовый override одного invoke.

## Консультационный канал архитектора (вопрос без изменения графа)

Когда поезд упёрся в блокер и нужно решение архитектора БЕЗ записи state и без трогания чужого поезда — вызывать консультацию архитектора напрямую через `codex exec`: роль/модель/effort из `~/WorkVault/Registries/EcosystemConfig.yaml` → `tools.dev_workflow.roles.architect` (напр. `gpt-6.1-sol` effort high), вердикт — последний `agent_message` из NDJSON-потока. Прямой вызов нужен и когда `pipeline emit-prompt` на архитекторскую фазу заблокирован конвейером (G1 extract version drift, exhausted recovery): тогда передать вопрос архитектору через этот канал, а не нести Саше свои варианты.

- `invoke-role` БЕЗ `--slug`/`--phase` — не предпочтителен: возвращает rc=0 и глотает stdout; вердикт надо выгребать из свежего codex-rollout (`ls -t ~/.codex/sessions/<YYYY/MM/DD>/*.jsonl | head -1`, парсить финальные `response_item.type=message → content[].output_text`).
- **Точная форма консультации через `codex exec` — только та, что использует `run_codex()` в `invoke_role.py` (сверяться с ней), а не произвольные флаги.** Рабочая команда: `codex exec -C <абс workspace> -m <модель> -c 'model_reasoning_effort="<effort>"' --skip-git-repo-check --sandbox danger-full-access -- "<промпт>"`. Промпт — позиционный аргумент ПОСЛЕ `--`, effort — через `-c model_reasoning_effort=` (флага effort у `codex exec` нет).
- **Три траты хода при самостоятельном подборе флагов `codex exec` (все отвергаются до запуска):** (1) `--role` — несуществующий флаг, ошибка `unexpected argument '--role'`; роль задаётся моделью из YAML, а не флагом. (2) `-p` — это `--profile` (имя `.codex/<name>.config.toml`), НЕ промпт; передача промпта в `-p` даёт `invalid value … pass a plain name such as work`. (3) запуск вне git-repo без `--skip-git-repo-check` падает `Not inside a trusted directory`. Не выдумывать флаги `codex exec` — копировать форму из `run_codex`, иначе поезд теряет ход на синтаксисе, а не на контенте.
- **Развилку/блокер решает архитектор — не выставляй Саше собственные нумерованные варианты с рекомендацией.** Саша требует «отдай архитектору подумать решение вопроса»: вопрос целиком уходит архитектору, вердикт подаётся как есть, без своих рекомендаций/добавок. Исключение — только когда Саша явно просит варианты с рекомендацией (тогда подавать ПРЕДМЕТНО по именам).
- **Запускать консультацию в фоне** (`background=true`, `persist_on_release=true`, `notify=true`): foreground `codex exec` упирается в таймаут (180–420 s) и обрывает процесс до финального ответа. Вердикт из `*.ndjson` — последний `agent_message` (см. ниже); при plain-text вызове (без `--json`) вердикт появляется в конце stdout, часто ПОВТОРЕННЫМ дважды — читать последнее вхождение `**Вердикт**:` (жирной + двоеточие), остальное до него — рабочий rollout кода agent. Искать вердикт в конце вывода, а не в начале.
- Финальный текст собирать так: из `*.ndjson` — блоки `item.completed` с `item.type == "agent_message"`; из plain-text — конец вывода. `turn.completed` может не содержать текста, а промежуточные agent_message — это анализ, не вердикт. Если процесс оборван таймаутом без `turn.completed`/вердикта, перезапустить в фоне с явной инструкцией «финальный ответ единым текстом в конце».
- Вердикт сохранить в `evidence/` слага как markdown-файл с источником (rollout-путь + дата), чтобы поезд имел осязаемый артефакт.
- Промпт для консультации: контекст блокера (master версия+sha, план rev, precondition/evidence), точные вопросы с вариантами, требование конкретного вердикта (кто владелец каждого фикса, что правится, критерий зелёный, судьба поезда).
- **Передавать архитектору ПОЛНЫЙ контекст — не узкое описание блокера:** вся история вопроса (журнал поезда, state, предыдущие попытки, история переписки/чата по задаче), релевантный код/файлы (абсолютные пути, ключевые строки), ТЗ на доработку дословно (выжимку/пересказ недостаточно), точные места логов/state и сами логи ошибок за весь период доработки. Саша явно требует: «передавай архитектору всегда полную информацию — историю вопроса, код, тз на доработку и где смотреть логи ошибки; только тогда он сделает правильное решение». Особенно когда вопрос — распространение адресного исключения (например, AD-R3-01) на другой ключ: включить дословный текст исключения, чтобы архитектор подтвердил/опроверг применимость по букве нормы.

## Выбор работы: `pipeline status` готовой-строки НЕ достаточно — сверять фазы в _state.json

Строка задачи в секции `ready` со `status=idle` НЕ означает, что задачу можно брать в работу: RESEARCH-задача может числиться ready/idle при том, что ВСЕ её фазы (включая GATE:done) уже `done` — в state не сфлипнулся финальный архивный статус. Доверие строке приводит к рекомендации «берём в работу» уже завершённой задачи.

- Перед рекомендацией взятия НЕ готовить по строке `status`: открыть `_state.json` задачи и проверить фактическое состояние фаз (`phases.<name>.status`) и `status`. Все фазы `done` (GATE:done в том числе) = работа выполнена, брать нечего; строка `idle/ready` — снапшот-аномалия (проекция не перевела задачу в archive).
- Результат завершённой RESEARCH-задачи может жить в ПОСЛЕДУЮЩЕЙ задаче (`razbor-*` → `tz-na-*-dev`): рекомендацию «что дальше» строить, проследив продолжение по журналу/заголовкам, а не пере-взяв задачу-производителя.
- При ответе «какие хвосты остались» учитывать: формально `done`-задача может держать deferred/after-AC (например `AC deferred по решению Саши`, `IAC-*.after`), а идеи из неё уходить в очередь как `todo` c `[NEW-ENTITY]` — это живые хвосты, хотя канон графа зелёный. Но перед тем как «доделывать» такой хвост — заглянуть в `evidence/`: пометки вида «ниже/далее» в AC-report часто означают «факт собран, не вписан в отчёт», а не «не выполнено» (пример: IAC-20/21/22 уже имели PASS-json на диске). Тогда хвост закрывается документированием в отчёт, а не повторной работой.

## Закрытие stale-idle поездов (все фазы done, status=idle)

Массовая гигиена бэклога: десятки поездов у которых все фазы `done` (включая GATE:done) но `status=idle` висят в `ready`-колонке отчёта, хотя закрыты — `_column_for('idle')` → 'ready' при том, что `effective_done` уже True.

- **Критерий закрытости — не `preflight --mode done`, а все фазы done + GATE:done done.** `preflight done` требует AC-report/AC-delivered/gitproof-маркеры, которых у legacy-закрытых RESEARCH/skill/лёгких поездов нет — он падает на них и не является признаком «не закрыто». Отбор по `_state.json`: `status==idle` И все `phases.*.status==done` И `recipe[-1]=='GATE:done'` И `phases['GATE:done'].status=='done'`.
- **Закрытие штатным writer (не прямой JSON-write):** прочитать `pipeline_state.read_state`, выставить `st.status='done'`, `st.phase=None`, `st.pid=None`, записать `write_state(event={'event':'repair','actor':'sirene','phase':'GATE:done', ...})`. Событие `repair` — из закрытого словаря, а не `rewind`/`complete`.
- **Событие repair требует phase**: `event={'event':'repair','phase':None}` роняет `ValueError: active phase required for non-root event` — root-события только init/abort/abort_root/set_case. Ставить в событии явную `phase='GATE:done'` (журнальная фаза может отличаться от `st.phase=None`).
- Сделать бэкап `_state.json` перед массовой правкой (напр. `/tmp/.../`), затем `pipeline_queue.rebuild_index`.
- После этого закрытые поезда уходят из `ready` в scheduled/archive и больше не показываются как «в очереди».

## Перевод идеи в готовую задачу (idea → ready)

Идея (`idea=True`, в triage) превращается в готовую RESEARCH-задачу штатным writer'ом: `read_state` → `st.idea=False`, `st.status='idle'`, `st.phase=None` → `write_state(event={'event':'repair','actor':'sirene','phase':<первая фаза рецепта>, 'reason':'Б55:готовность', 'evidence':'ready_at=<iso> path=<абс>'})`. `ready_at` подхватывается проекцией из `queue.log.jsonl` по `reason=='Б55:готовность'` (это же пишется и в journal.md), и задача встаёт в `ready` по FIFO. `ready_at` для нескольких задач проставлять в порядке взятия (первая по FIFO — самый ранний timestamp; подряд идущие с запасом в секунду, чтобы ординал совпадал с порядком).

## Закрытие RESEARCH-поезда до `preflight done`: AC-report + AC-delivered маркер

После `complete-phase GATE:done` RESEARCH-поезд показывает `status=done`, но `preflight --mode done` может всё ещё падать `AC-delivered marker missing`. `preflight done` требует ДВА независимых признака: файл `AC-report.md` (проверка `ac_report_ok`) И строку `AC-delivered: ...` в journal.md (`ac_delivered_ok`, regex `AC-delivered:\s+\S+`).

- Создать `AC-report.md` в каталоге слага (сводка AC-RS / результатов / артефактов / договорённостей).
- Проставить маркер штатным writer'ом: `write_state(event={'event':'repair','actor':'sirene','phase':'GATE:done', 'reason':'AC-delivered: <куда доставлен отчёт>', 'evidence':'path=<абс>'})` — причина должна начинаться с `AC-delivered:` и иметь непустой токен после двоеточия, чтобы regex совпал.
- `status=done` сам по себе НЕ означает, что preflight done зелёный; финальный `GATE:done` считаётся закрытым только когда `preflight done` вернул 0.

## TZ:patch после правки master — G2-complete отвергает «context packet missing or changed»

Фаза, которая **законно меняет master** (`TZ:patch`), сталкивается на `complete-phase` с отказом `G2: context packet missing or changed`, хотя артефакт записан и роль отработала. Механизм: `g2_complete_guard` через `_validate_refs_on_disk` сверяет sha/mtime master, зафиксированные в **принятом** контекстном пакете (`phases.<phase>.context_packet`), с текущим содержимым master на диске; роль master уже изменила → drift. archive-риск: это НЕ дефект роли и НЕ повод править packet/state руками.

Штатное восстановление — полный цикл ПОСЛЕ правки, чтобы пакет был снимком уже изменённого master:

1. заново `emit-prompt --phase <та же фаза>` (новый snapshot захватит актуальный master);
2. ещё один `invoke-role` той же роли (перепримет консистентный пакет в `context_packet`);
3. затем `complete-phase` — G2 пройдёт.

- Повторный `emit-prompt` БЕЗ повторного invoke не помогает: `context_packet` в state остаётся от первого invoke (старый hash master), и guard всё равно падает. Ключ — именно второй `invoke-role`, который перезаписывает принятый пакет.
- G2 не обходить и не редактировать `_state.json` руками; известный разрыв Б56.3/56.6 лечится только повторным emit→invoke либо адресным диагнозом процесса.

## G2-complete: править промпт после emit — пара packet/prompt расходится

`emit-prompt` фиксирует `prompt_sha256` выхода в пакете; правка `/tmp/task.md` ПОСЛЕ emit (дописывание замечаний REV, фактов и т.п.) даёт на `invoke-role` отказ `G2: emitted packet/prompt pair is missing, changed, or stale`. Роль видит весь workspace — факты/замечания докладывать ОТДЕЛЬНЫМ файлом в workspace (напр. `REV-*-N-REQUEST.md`, `evidence/*`), а не в содержимое emit-выхода. `--prompt-file` обязан быть ровно выход emit; пересобранный вручную промпт — обход, а не корректировка.

## G2-complete не требует accepted packet для sirene/оркестраторных фаз

`g2_complete_guard` покрывает фазы по ПРЕФИКСУ `TZ:/HF:/BUG:/REV:` — в том числе оркестраторные sirene-фазы (`HF:backup`, `HF:docs-handoff`, `TZ:stabilize`), у которых `emit-prompt` запрещён G6, а `invoke-role` не вызывается (роль-владелец = sirene), значит accepted context packet физически никогда не появляется, и `complete-phase` застревает на `G2: accepted context packet required`. Это bootstrap-дефект: лечащий фикс живёт в `g2_complete_guard` (pipeline_context.py), который по плану правится в HF:impl — ПОСЛЕ HF:backup, т.е. после фазы, которую guard блокирует.

- Размыкание — адресный не-LLM фикс оркестратора (прецедент F07/§4.2, accepted ревизором): исключить sirene-фазы из `g2_complete_guard` (версия «возвращай True для `_SIRENE_G2_EXEMPT` = `TZ:stabilize`/`HF:backup`/`HF:docs-handoff`»), с бэкапом файла (`/tmp/*.bak`) и подтверждением полным pytest до `complete-phase`. Ролевые фазы (HF:impl/test) должны ПРОДОЛЖАТЬ требовать packet — guard сужается, не снимается.
- Снять guard молча нельзя: оркестраторная sirene-фаза без пакета — штатное состояние, а не ошибка роли; вмешательство в guard фиксировать в evidence фазы как адресную правку с причиной-петлёй.

## REV:plan REQUEST-CHANGES — штатный rewind, не complete

Вердикт REQUEST-CHANGES НЕ является complete: guard запрещает `complete-phase` по REV-фазе с этим вердиктом, фаза остаётся `doing`. Возврат плана архитектору на доработку — штатный rewind, не ручное редактирование state:

1. канон `REV-plan.md` сохранить как историю `REV-plan-1-REQUEST.md` (именованный счётчик REQUEST-редакций, как в прецеденте) — артефакт ревизора не теряется и служит входом для следующей редакции;
2. `pipeline_state.write_state` событием `rev_request_changes_rewind`: фазу-получателя REV и фазу-источник (напр. `HF:plan`) вернуть в `todo`, снять fail-класс/pid;
3. `next` ведёт на источник (карта возвратов: REV:plan→HF:plan, REV:tz→TZ:patch, REV:report→RS:analyze);
4. свежий `emit-prompt` (новый packet_id) + единственный `invoke-role` с консистентным `--prompt-file` (НЕ править его после emit — см. выше).

- **Provider-fatal 401 на ревизоре после записи вердикта — артефакт валиден, фаза в `doing` `fail_class=provider_fatal`.** `invoke-role` пишет артефакт до сбоя токена; 401 возвращается уже после — REV-отчёт целиком на диске при exit code 3. Это НЕ потеря артефакта: guard REV REQUEST-CHANGES всё равно запрещает complete, поэтому rewind дальше делается по правилу выше независимо от provider-fatal (401 — провайдер, не дефект роли). Токен истёк — повторный invoke позже после обновления ключа, это техническое, не process-регламент.
- **Штатный `addressed_rework` срабатывает ТОЛЬКО когда текст REV-plan.md содержит обязательные маркеры канона rework-request** (`object|объект`, `contract|контракт`, `defect|дефект|требован`, `AC[-:]`, `Повтор замечания|Пересмотр требований`). Когда ревизор пишет сущ-языком без этих маркеров, `next` после REQUEST-CHANGES возвращает `INTERRUPTED` (не WORK) — `addressed_rework` не находит request, и эквивалент не к чему применить. Тогда выполнить rewind вручную штатным `write_state(event=repair)` тем же алгоритмом, что `apply_addressed_rework`: в `proof` хозяина-фазы дописать `rework_request={source:'REV:<ф>', ref}` и `context_history`, добавить sha в `consumed_requests`, сбросить `receipt/context_packet/started_at/ended_at`, хозяин→`doing`+`awaiting_invoke`, `st.phase=<хозяин>`, REV-фаза→`todo`; после этого `next` даёт `WORK` на хозяине и emit собирает packet `kind=rework` с REV-plan.md в `request`.
- **Поле `ref` в синтетическом `rework_request` ОБЯЗАНО быть полным fileRef** (`path`, `resolved_path`, `sha256`, `size_bytes`, `mtime_ns`), которое строит только `pipeline_context._ref(path)` — не собирать dict `{path, sha256}` вручную. Самодельный ref валится на emit schema validation (`is not valid under any of the given schemas`), emit не выпускает rework-packet; с `_ref()` emit проходит rc=0. После ручного rewind всегда пере-читать state и проверить: хозяин в `doing`+`awaiting_invoke`, REV-фаза в `todo`, затем `next` → WORK на хозяине.

## Фаза, легально пишущая master: контракт обязан объявить master как `kind: master` output

Фаза, которая меняет master (TZ:patch, TZ:finalize), ДОЛЖНА декларировать master как выход `kind: master` в контракте (write_scope + outputs), а не только в write_scope. Иначе после закрытия фазы поезд уходит на `next → TZ:compress` (штатный refresh производителя), но `refresh_producer` не находит accepted basis и отказывает `G1: external master or compressor prompt drift; no accepted refresh basis` — поезд заперт до починки. Это отдельный от G2-complete дефект (тут G2 той же фазы уже пройден; сломана связка фаза→следующий производитель).

- Признак дефекта контракта фазы: `next` возвращает TZ:compress, а сам `refresh_producer` падает при отсутствии `result.outputs[str(master)]` у принимающей фазы (сравнивает по `_ref` = path/sha256/size/mtime). Любая смена master — даже только metadata (status→approved в finalize) — меняет bytes/mtime и требует штатного refresh перед ПОТРЕБЛЯЮЩЕЙ фазой.
- Штатная починка (НЕ re-invoke, НЕ ручное JSON-write): зафиксировать в `result.outputs` принимающей фазы `pipeline_context._ref(tz_path)` через `write_state(event=repair)`, раз результат роли уже записан дисковой фазой (evidence в verification.json); затем `next` переоткрывает TZ:compress и досжимает extract под новый master.
- Прецедент: `TZ:patch` закрылся G2-чисто, `next` вернул compress, refresh отказал accepted-basis, потому что контракт поезда не объявлял master Kind-выходом. Фикс `_ref` в outputs принявшей фазы разблокировал связку.

**НЕ «обходить» G1 refresh откатом живого master после легальной TZ-правки.** Когда хочется убрать `G1: no accepted refresh basis` на `next` после TZ:patch, кажется очевидным вернуть живого master к preimage (pre-approved sha) — НО это молча стирает опубликованный архитектором результат фазы. Если затем идёт REV:tz, ревизор наблюдает master без заявленной дельты (master на диске = старая approved-версия) и честно блочит **REV-TZ-DELTA-01 «заявленный результат отсутствует в master SoT»** (норма: диск — SoT, Б12/Б13/Б18). Откат-как-dodge превращает корректную публикацию роли в rework-цикл ревизии. Правильное лечение G1 — контракт с master `kind: master` output / `_ref` в result.outputs (выше), а НЕ восстановление preimage. Живой master обязан ОСТАВАТЬСЯ опубликованным результатом роли до следующей легальной фазы-владельца (TZ:finalize); переигровка (restore preimage) — только когда сам вердикт роли признан ошибочным решением владельца, зафиксированным явно.
- Если откат-таки был сделан: вернуть опубликованную дельту в фактический master ПЕРЕД next на потребляющую фазу (re-apply master-delta.patch из evidence TZ:patch до точного claimed-sha) и восстановить mtime к сохранённому в state (`extract_key` содержит mtime — `cp` меняет его и даёт `extract_key drift`; вернуть `os.utime(ns=stored)`), иначе даже верный master провалит refresh по mtime.

## TZ:finalize — документная цепочка master→inventory→appendix обязана быть в контракте

`TZ:finalize` по Б15/Б61.1 — это НЕ отчёт: она физически пишет master (status→approved + frontmatter/provenance edits), синхронизирует `MAIN_TZ_INVENTORY.md` и ставит целевое приложение истории (`appendix_history_<date>.md`). Если только канон-файл фазы объявлен в контракте, а master/inventory/appendix вне write_scope+outputs — архитектор КОРРЕКТНО вернёт `NOT_COMPLETE` (дефект допуска, admission-scope), это не содержательная ошибка и не recover.

- `NOT_COMPLETE` от архитектора на finalize = дефект допуска, а не роли. Чинить контракт: `brief.md` по предложенному архитектором `handoff-proposed.md` (write_scope на master/inventory/appendix + inputs: brief/TZ-patch/REV-tz/master + outputs: canonical/master/inventory/changed_files), затем сброс фазы к WORK штатным writer и заново emit→invoke. НЕ запускать роль повторно с тем же неполным допуском.
- Замечание: когда `brief.md` уже содержит handoff-contract а отдельного HF-plan.md нет, `_contract` берёт контракт из brief — правка finalize-секции в brief действует. Как только появится HF-plan.md со своим блоком, контракт для последующих фаз берётся из ПЛАНА (см. «Второй ТЗ-круг»).
- Симптом `output outside write_scope` на приёмке после успешной документной роли почти всегда = пропущенная секция контракта для этой фазы, а не ошибка роли. Перед emit каждой документной фазы сверять, что каждый канон/master/inventory/appendix объявлен И в write_scope, И в outputs.

## Создание DEV-поезда на реализацию по завершённому RESEARCH

Когда завершённая RESEARCH-задача должна перейти во внедрение, а Саша дал императив «делай ТЗ и реализуй», НЕ пересобирать старый поезд и НЕ править research-поезд в recall — завсти НОВЫЙ DEV-поезд:

```text
pipeline suggest-slug --title "<человеческое название>"            # → {"slug": "..."}
pipeline init --case DEV --slug <slug> --title "<title>" --slug-source suggest-cli --origin-chat <chat> --origin-thread <thread>
```

- `origin-chat` и `origin-thread` передавать императивно (из известного топика, напр. chat `-1004300127777`, thread 6), иначе доставка потеряется.
- После init: перевод в готовность тем же writer-репом `reason='Б55:готовность'`, `phase=<первая фаза рецепта>` (у DEV это `TZ:patch`), `st.idea=False/status='idle'/phase=None` → `next` → `WORK`. Тогда задача стартует с TZ-цикла; привязка master идёт автоматически (у DEV `master:status=present` на `DevWorkflow_TZ.md`).
- Отдельные DEV-поезда на каждую идею — по одному; очередь без отдельного аппарата.
- Завершённый RESEARCH поezд НЕ удалять/не трогать — он остаётся done-фактом и входной точкой для нового DEV; в DEV-поезде ссылаться на его `RS-collect.md`/`RS-analyze.md` как на обоснование.
- Приоритет взятия нескольких DEV-поездов — FIFO по `ready_at` (первый в императиве Саши — самый ранний timestamp).

## Фоновый invoke завершился (notify) — это НЕ сообщение Саши, продолжай цикл

Когда фоновый `invoke-role` уведомляет о завершении (exit 0) — это системный notify платформы, а не поручение Саши. Не отвечать ему формально и не ждать: продолжить штатный цикл — RECONCILE (артефакт на диске), `complete-phase`, `next`, следующий emit→invoke в фоне. Целую цепочку фаз одного поезда (RS:collect→RS:analyze→GATE:done, или TZ→REV→…→GATE) гнать до конца по уведомлениям, без напоминаний Саши.

## Где искать поезд по цитате/«что по задаче» — не только `pipeline status`

Когда Саша цитирует фрагмент из переписки («архитектор пишет план… 68 nodeids») или спрашивает «что по этой задаче» — НЕ начинать с `pipeline status`. Он показывает только канонические поезда с `_state.json` в deque; часть активных работ живёт в ad-hoc-каталогах `dev/<slug>/` БЕЗ `_state.json`/journal.md (робочая директория с `in/`, `out/`, `candidate/`, `evidence/` и step-логами). Такие работы в status вообще не видны.

- Уникальный маркер задачи (число nodeids, имя вердикта `ARCH-*-DECOMPOSITION`, слаг с датой) искать grep по `dev/**/out/*.md` и `dev/**/journal.md`, а не по строке status.
- Определять поезд по НАЗВАНИЮ-слагу и таймстампам `out/*.md` (последний изменённый = актуальный вердикт), сверяя, что цитируемая дельта (например 68 = 57 исходных + 11 component) численно совпадает с найденным документом.
- Если нашёлся активный канонический поезд (WORK в status), но цитата про иную дельту — проверять соседние ad-hoc-директории, прежде чем приписывать цитату канону.

## Повторная незавершённость исполнителя: диагностика «перечитывание ≠ truncation» и лечение разбиением

Два подряд прогона исполнителя (HF:impl), оба сами выдали отчёт о незавершении при ЧИСТЫХ логах — это не лимит модели: диагностировать по JSON-метрикам usage (нет `turn.failed`/исчерпания контекста, ~94–96% входа `cached`, input накоплен повторным чтением больших grep-выводов и плана). Сильно кэшированный большой вход = многократное перечитывание общего scope, а не реальное окно. Не списывать на нехватку контекста и не приписывать результат конкретному лимиту модели без этих данных.

**Лечение (архитектор-одобренный путь):** НЕ давать третьему общему прогону («заверши IAC-02…08 и собери тесты») — разбить работу на N bounded serial-частей (W1-01…N), каждая со своим ограниченным контрактом, exact base HEAD, exact allowlist, обязательными проверками и собственным commit. Каждую часть запускает вызывающая роль с одной строкой задания (номер части, кrhiterii готовности, зависимости и команды проверки). Часть завершена ТОЛЬКО при одновременном выполнении: полный контракт + реальные fixtures на exact candidate-коде (без TODO/pass/NotImplemented) + commit с `git diff --check` чист + отчёт. Production-установка/полный collect — только в финальной части.
- **Тестовая дельта разбиения — [NEW-ENTITY, требует гейта Саши], не уже согласованное изменение.** Дополнительные component nodeids (напр. 11 → required=68 из исходных 57) — адресная дельта тестового manifest; пока не принята Сашей, исходная норма остаётся (57), исполнитель НЕ вводит nodes самовольно.
- Первый ограниченный run после разбиения — и ориентир длительности: если даже он не закрывается, пересматривать его конкретный контракт, а не увеличивать отчётность.
- Делить по границам проверяемых МЕХАНИЗМОВ (verifier+transports+context или весь Compressor в одном — плохо), а не по числу файлов: один `pipeline_extract.py` несёт больше приёмочных обязательств, чем несколько справочников.

## Статус многогэтапного acceptance-поезда (этапы 1-N) — не в pipeline status

Когда Саша спрашивает «статус» по working-поезду с ЭТАПАМИ 1-N («Этап N запущен»), где исполнитель — фоновый `codex exec` — такой поезд НЕ живёт в kanban `_state.json` и не виден в `pipeline status`: слаг может нести лишь фазовую запись (`HF:plan in_phase`), а собственно ход с артефактами происходит в отдельной acceptance-области. Состояние читать по ЖИВЫМ артефактам, а не по сообщению о запуске.

1. **Живость процесса первична:** `ps aux | grep -iE "codex|cursor|agent -p"` — живой `codex exec -m <модель>` с темой из промпта (пример «Этап 10 … сетевые стадии») = поезд ЕЩЁ идёт. Пока процесс жив, этап не завершён, даже если часть отчётов уже появилась.
2. **Область артефактов поезда** (два зеркальных места):
   - `~/.cache/<tool>-acceptance/<run-id>/stage-NN/reports/` — артефакты команды (junit, stdout/stderr, external-checks.json, initial-state, batch/identity/live-отчёты). Брать самый свежий `run-id` по `ls -lt` каталога.
   - `S/references/implementation/<ггггммдд>/stage-NN/` — зеркалируемая доставка (before/after, `changes.patch`, manifest), куда в конце ложится отчёт.
3. **Gate и прогресс:** `stage-NN/reports/external-checks.json` → `gate: passed|failed`; ранние проверки (например Mofs-регрессия 147/0) появляются РАНЬШЕ финального `stage-report.{json,md}` — их наличие НЕ значит, что этап доведён, только что актivity идёт.
4. **Остаток** читать из промпта живой команды: обязательные финальные шаги (отчёт + завершающий коммит + `git status` подтверждающий, что чужой файл остался вне коммита). Пока они не выполнены — этап в работе, gate/final отчёта нет.

Правила доклада: первый абзац — прямо по существу статуса; указать этап, что уже реально появилось, что осталось, и что финал придёт отдельным уведомлением после живого процесса. Не объявлять gate passed/failed, пока не прочитан готовый `external-checks.json`/`stage-report.md` финала с SHA коммита. Ранние отчёты — признак активности, не завершения; kanban `_state.json` не несёт прогресса этапного поезда поверх него.

## «Что требует ТЗ» — читать master напрямую, не пересказывать вердикт архитектора

Когда Саша спрашивает «какое решение соответствует ТЗ» по конкретной строке/ключу — открыть сам master-ТЗ (§10.x состав/критерий закрытия/запреты) и ответить по букве нормы. Вердикт архитектора — рекомендация; ТЗ — SoT. Часто буква ТЗ (например, `no-entry` требует буквального `entry=входа нет`, `safe-call-absent` не заменяет closure) сужает выбор до одного варианта, который архитектор оставил открытым.
