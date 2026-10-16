---
name: dev-workflow
version: 0.4.4
description: Оркестрация разработки Hermes (файловое состояние, 10 кейсов)
---

# Dual-path (переход W0–W4)

Пока в конфиге `tools.dev_workflow.orchestration.mode` не равен `workflow-only`:

- не вызывай `pipeline init` для слагов **вне** списка `orchestration.pilot_slugs` (на W1 список пустой);
- если слаг в `pilot_slugs` и на нём **нет** живого канбан-running — **стоп**, веди задачу только этим скиллом;
- для остальных слагов — по-прежнему `hermes-feature` / `tz-workflow` и канбан;
- два поезда на одном слаге запрещены.

Подробности: `references/rollback.md`, текст баннера для чужих скиллов — `references/dual_path_banner.md`.

**Баннер в чужие SKILL.md брать ТОЛЬКО дословно из фикстуры канона** `Registries/pipeline/tests/fixtures/dual_path_banner.md` (**12–19** непустых строк = dual-path + файрвол, покрывается `test_dual_path_banner.py`). Не переписывать «по памяти»/своими словами — отклонение от фикстуры ломает AC-050/IAC-32. `git diff --numstat` должен быть только ±баннер в двух SKILL.md (живая вставка W2 — отдельная фаза).

# dev-workflow — процедура оркестратора

Единый процесс разработки вместо связки «канбан + несколько скиллов». Норматив смысла (кейсы, фазы, гейты, роли) — в `references/canon.md`. Мастер-ТЗ инструмента: `~/WorkVault/Hermes-Backlog/TZ/DevWorkflow/DevWorkflow_TZ.md` (актуальная версия — из `version:` в шапке файла, не парь по тексту скилла).

**Кто ты:** Сирень (профиль default). Ты ведёшь фазы, зовёшь роли через Python, не пишешь ТЗ и код сама.

**Помощник на диске:** `Registries/pipeline/` — состояние в `dev/<slug>/_state.json`, команды через `scripts/pipeline.sh` или `python3 -m pipeline.cli`.

## Когда включать скилл

| Фраза / ситуация | Действие |
|---|---|
| разработай, доработай, почини, напиши ТЗ, исследуй, в бэклог | см. таблицу кейсов в `references/cases-guide.md` |
| слаг в `pilot_slugs` (W2+) | только `dev-workflow`, канбан для этого слага на паузе |
| после `hermes update` | `restore-all-skills.sh`, затем `pipeline status --check` (exit 0 обязателен) |

## Очередь задач (конвенция, всегда)

Любую задачу Саши (разработка, доработка, багфикс, исследование, настройка) заводить `pipeline init` слагом **сразу, в очередь**, даже если Саша НЕ сказал «в очередь» и даже если другой поезд сейчас в `in_phase`. Не ждать явного «ставь в очередь» — это правило по умолчанию для всех кейсов. Пока текущий поезд занят, новый слаг живёт в T1 как `idle` (рецепт есть, `invoke_role` на нём **нет**). Когда текущий поезд освобождается (`GATE:done` / `aborted` / иначе не занимает воркер) — следующий из очереди запускать **самому, без напоминания Саши**: `pipeline next --slug <следующий>`. **Не** минутный тик и **не** скилл, который сам себя будит (Б33 п.7). По одному поезду на Cursor/воркере (не запускать два `invoke-role` параллельно, чтобы не пересекались по одному провайдеру/воркеру).

## Файрвол ролей (Б16.2 / Б37, AC-044…045)

Оркестратор **собирает факты** (что сломалось, пути, имя встречи) и ведёт поезд; **не** пишет ТЗ и код. **Не предлагай слаги / технические варианты** (`dev/<slug>/`, `entities.task_slug`, варианты починки) — только факты, `suggest-slug` или `sasha-verbatim`, затем архитектор.

- **Слаг поезда** — только `pipeline suggest-slug --title …` (один кандидат в JSON, не список Саше) или `--slug-source sasha-verbatim` (дословно из фразы Саши). `entities.task_slug` и префиксы задач — зона архитектора **другого** инструмента (PFS), не меню оркестратора.
- **«Баг / не работает / почини»** (в т.ч. рядом с именами встреч или task_slug) → кейс **BUGFIX сразу**: собери факты → `pipeline init --case BUGFIX` → пакет `BUG:diagnose`. Не меню из шести префиксов и не нумерованный выбор слагов до `invoke_role --role architect`.
- **R3** (нумерованные варианты + рекомендация) **запрещён** для слагов и технических развилок. R3 остаётся для `Q-n` архитектора (после его формулировки) и operator-глаголов (`references/canon.md`).
- **Строгое правило (Саша, 15.10): при работе по канону оркестратор НЕ даёт собственных мнений, рекомендаций и предложений по слагам/техническим развилкам/судьбе карточек/классификациям/архитектуре.** Только: факты по диску, `suggest-slug`, `sasha-verbatim`, вопросы Саше по одному (контекст + варианты — **без** своей рекомендации, кроме случая, когда Саша явно её запросил: «как думаешь», «рекомендуй») ИЛИ передача архитектору / ревизору / **Саше** на вердикт. Нарушение: если я уже дал мнение — пометить его как своё, не выдавать за вердикт архитектора/ревизора, и передать решение по канону.

Кейс по смыслу запроса — таблица триггеров в `references/cases-guide.md`, не меню слагов.

## Старт задачи

1. **Бриф в Telegram** — факты и один уточняющий вопрос по кейсу, если неясно (не технические варианты). Бриф не пишется в рецепт на диске.
2. **Закрытие брифа** — зафиксируй кейс (таблица триггеров), периметр. Пока бриф открыт — `init` не делай.
3. **`pipeline init`** — `--case`, `--title`, `--origin-chat`, `--origin-thread`; `--slug` и `--slug-source` (`suggest-cli` | `sasha-verbatim` | `reuse`, default `suggest-cli`). Пример — `references/install.md`.
4. **Preflight create (G4)** — в `recipe[]` должны быть все фазы выбранного кейса. Ошибка → init не считается завершённым.

## Основной цикл (без cron и «тиков»)

Движение только когда: Саша написал, роль вернула результат, или ты сознательно вызываешь `next` в том же ходе.

```
pipeline next
  → читаешь action (WORK | AUTO_GATE | WAIT_SASHA | DONE | INTERRUPTED | BLOCKED)
  → действуешь по таблице ниже
  → при успехе: complete-phase --reason … --evidence …
  → при сбое роли: interrupt (не авто-ретрай)
```

| action | Что делать |
|---|---|
| **WORK** | `emit-prompt` → при exit 0 → `invoke-role` (не `agent -p` напрямую) → проверить артефакт на диске → `complete-phase` |
| **AUTO_GATE** | показать/проверить улику (AC-список, план, отчёт…) → `complete-phase` с reason+evidence |
| **WAIT_SASHA** | сообщить в **origin**-топик (не Errors), `waiting_operator`, **остановиться** (нет фонового опроса) |
| **DONE** | preflight закрытия → отчёт AC в origin |
| **INTERRUPTED** | сообщить Саше; не перезапускать фазу сама |
| **BLOCKED** | техника → ErrorBus; кейс → origin |

Перед каждой содержательной фазой (TZ/HF/BUG/REV): только цепочка **emit-prompt → invoke-role**. Обход и `--force` запрещены. Пакет контекста: `references/context.md`.

**`invoke-role` запускать только в фоне** (`terminal background=true, notify=true, persist_on_release=true`). Роль (cursor-grok/claude/composer) отвечает минуты — foreground-терминал с таймаутом 180с убивает вызов до ответа: фаза остаётся `doing` с пустыми `pid/started_at` в `_state.json` и без дописи в `journal.md`, результат теряется. После запуска фона `next`/`complete-phase` делай только на момент завершения роли, прекращай ход; не перезапускай фазу молча.

**LIGHT:** после известного объёма — `pipeline set-case --case CHANGE-LIGHT` или `BUGFIX-LIGHT` (не решает архитектор).

## Согласование ТЗ и плана (REV)

После `TZ:patch` и `HF:plan`:

1. `complete-phase` архитектора с evidence.
2. `next` → `REV:*` → emit-prompt → `invoke-role --role reviewer`.
3. Ревизор пишет вердикт **только** в канон `dev/<slug>/REV-tz.md` или `REV-plan.md` (`APPROVE` | `REQUEST-CHANGES` в блоке `## Вердикт` и/или `verdict=`). Иное имя (`REV-tz-2.md` …) → `invoke_role` exit ≠ 0 (G6/канон артефакта); не плодить суффиксы — один файл на фазу. Архив прошлых итераций — отдельное имя (`REV-tz-1-REQUEST.md`), гейт его не читает.
4. **APPROVE** → `complete-phase` REV → следующая фаза. `rev_verdict()` смотрит **только** блок `## Вердикт` / `verdict=` (цитата истории в теле не блокирует APPROVE — это Python, не обязанность оркестратора).
5. **REQUEST-CHANGES** → `complete-phase` REV запрещён; возврат архитектору через `pipeline_state.write_state` (см. ниже), повтор REV до APPROVE или waive Саши.
   - `interrupt` на REV с REQUEST-CHANGES НЕ перематывает: фаза остаётся `doing`, `status=interrupted`, `next` даёт `INTERRUPTED`. Каноничный возврат архитектору — `write_state` напрямую: `status='idle'` (не `in_phase`), `phase=None`, `phases[предыдущая]={'status':'doing'}`, `phases[REV]={'status':'todo'}`, `pid=None`, событию обязателен ключ `event`+`actor`.
   - **`emit-prompt` на предыдущей фазе (HF:plan/TZ:patch) НЕ переносит блокер ревизора.** Промпт собирается из state/extract и пуст по контексту REQUEST-CHANGES — архитектор правил бы без знания замечаний. После emit-prompt вручную дописать в конец промпт-файла: вердикт REQ-CHANGES + что именно исправить (цитату блокера). Проверить `grep`'ом по ключевому слову, что дописка легла.

**rc=0 ≠ артефакт записан:** `invoke-role` возвращает единицу, а роль фактически записывает файл(ы) на диск (extract.md, REV-*.md, ТЗ) и НЕ завершает фазу — она остаётся `doing`, журнал без дописи. Оркестратор обязан после фона проверить артефакт по пути на диске (существование + mtime), сам дописать `journal.md` evidence/`context-used:` (если гейт G2 требует маркер) и вызвать `complete-phase`. Не доверяй DONE_EXIT=0 как «фаза закрыта».

**Никогда не редактируй `_state.json` hardcode-сбросом вне `pipeline_state`.** Прямой `json.dump`/`write_text` в `_state.json` ломает `state_sha256`: следующий `read_state` умирает с `CRISIS: state_sha256 mismatch` (exit 1), и весь CLI (включая `repair`/`next`) встаёт до исправления хэша. Все изменения состояния — только через `pipeline_state.write_state(state, event={...})` (и `read_state` для чтения): он пересчитывает `state_sha256` и пишет атомарно. Если `read_state` уже не проходит (хэш испорчен), собери объект `PipelineState(...)` напрямую из сырого dict (`raw = json.loads(path.read_text()); PipelineState(schema=..., slug=..., phases=raw.get('phases'), ...)`), проигнорировав `state_sha256`, поправь поля, и запиши через `write_state` — он пересчитает хэш и восстановит согласованность; после этого `read_state`/`next` снова живы.

Хэш ломается не только прямым сбросом: **аддитив новой схемы** (например, добавление поля `slug_source` в `to_dict`) тоже даёт CRISIS-рассинхрон на старом файле — `from_dict`→`to_dict` добавляет новое поле в имёжное содержимое, пересчитанный hash разъезжается со stored даже без правок «руками» (raw-sha по файлу матчится, а из объекта — нет). Симптом: ручной sha по сырому dict совпадает, а `read_state` всё равно падает. Лечится тем же: собрать объект из raw, `write_state` — он запишет файл уже с новым полем и пересчитает хэш консистентно.

**После rebuild/migration объекта верни `phases[PHASE]['role']` (и `started_at` при необходимости).** Сборка `PipelineState` напрямую из старого dict теряет `role`, который `invoke_role` записал ранее (`role: None`). `complete-phase` на фазе с ожидаемой Cursor-ролью упадёт по G6 «role None != executor» — упрёшься и фаза не закроется. Проставляй поле роли заново в этом же `write_state` (например, `phases['HF:impl']['role']='executor'`), иначе после «починки хэша» застрянешь на следующем гейте.

**Возврат фазы в `doing` после REQUEST-CHANGES:** `repair` НЕ переводит фазу назад (он только переиндексирует `queue.json`), а `next` на `interrupted` фазу даёт `INTERRUPTED`. Ручной возврат архитектору — через `write_state`: `status='idle'` (НЕ `in_phase` — `in_phase`+`doing` с мёртвым pid заставляет `next` снова ставить `interrupted`), `phase=None`, `phases['TZ:patch']={'status':'doing'}`, `phases['REV:tz']={'status':'todo'}`, `pid=None`. Затем `next` даёт `WORK`/`TZ:patch`. Событию нужен ключ `event` (+ `actor`) — иначе `Incomplete log event: missing event/actor`, мутация молча теряется.

Детали: `references/canon.md` (роли), `references/invoke.md`.

**Верификация «соседи не тронуты» (IAC/AC вида «git diff соседей пуст») — всегда baseline-diff, не абсолютно пустой diff.** Упасть может на уже существующей незакоммиченной работе в соседних инструментах (MoveFromFF/ProtocolFromSummary/MarkObjectsFromSummary и т.п.), не связанной с этим слагом. В плане: перед impl зафиксировать текущий diff соседей (`git status --porcelain` + `git diff --stat`) как baseline (в journal/state); в HF:test сравнивать прирост (текущее vs baseline), а не «диф абсолютно пуст». Инструменты вне git (реестры-каталоги без `.git`) — либо исполняемая команда проверки, либо явное исключение из IAC с обоснованием.

**Baseline для non-git соседей снимать РОВНО той командой, что verify-блок плана (относительные пути `./…`, те же исключения `build/`/`venv_linux/`/`state/`/`logs/`/`*.egg-info/`), не своей вариацией.** Если оркестратор снимет baseline своей командой (абсолютные пути, без исключений), а исполнитель на HF:test сравнит той функцией, что в плане, — получится ложный red по каждому файлу (abs vs rel + лишние `build/`/venv_linux). Исполнитель корректно остановится (норма «не красить тест зелёным»), и оркестратору придётся переснимать baseline. Снимай baseline дословно из блока плана (копия функции/команды) и проверь, что verify той же функцией даёт 0 прироста, ДО `complete-phase HF:backup`.

## HITL и уведомления

- Остановка поезда — только класс **O** (operator-hold) и never-auto гейты (`GATE:go`, `GATE:block-accept`).
- Показ AC (класс **S**) поезд **не** останавливает.
- Глаголы Саши — закрытый список в `references/canon.md` (`поднимай`, `ставь кроны`, `удаляй`, `answer:Q-n`, `rollback-to-kanban`).
- Снятие hold: `pipeline operator-done --verb … --evidence …` после **факта**, не после одной фразы.
- Ход кейса → origin; сбои CLI/инвариантов → ErrorBus (`references/invoke.md`).

## Запреты (кратко)

- Хранение ТЗ и три контура архивации — `references/storage-and-archival.md` (не дублировать полный Б15 в этом файле).
- Не склеивать фазы (`HF:impl` и `HF:test` — разные вызовы).
- Не вызывать `agent -p` в обход `invoke-role`.
- Не использовать `--continue` у cursor-cli.
- Не выбирать кейс и не пропускать фазы за архитектора (G5).
- Не ставить кроны без «ставь кроны»; не рестартовать gateway из этого процесса.

Полный список неприемлемого поведения — Б33 мастер-ТЗ.

## Миграция W0–W4 и откат

Волны, пилот, возврат на канбан: `references/rollback.md`.

## Справочники (содержание, не процедура)

| Файл | О чём |
|---|---|
| `references/canon.md` | кейсы, фазы, гейты, роли, G1–G5 |
| `references/cases-guide.md` | какой кейс когда |
| `references/cases/CHANGE.md` | эталон полного цикла |
| `references/context.md` | два источника, MUST-read, emit-prompt |
| `references/invoke.md` | бэкенды, фаталы провайдера |
| `references/cursor-cli-notes.md` | детали бэкенда cursor-cli |
| `references/rollback.md` | W0–W4, rollback-to-kanban |
| `references/install.md` | установка на голый Hermes (AC-042) |
| `references/handoff.md` | перенос живого слага (Б13.4) |
| `references/onboarding.md` | для специалиста без разработки |
| `references/config.example.yaml` | ключи `tools.dev_workflow` |
| `references/kanban-mechanics.md` | что сохранили из канбана без диспетчера |
| `references/storage-and-archival.md` | хранение ТЗ, снапшот/DECOMM, три контура бэкапа (A/B/C), откат |
| `references/dual_path_banner.md` | баннер W2 в hermes-feature/tz-workflow |

Комплект для нового хоста: `README.md` → `install.md` → `onboarding.md`.
