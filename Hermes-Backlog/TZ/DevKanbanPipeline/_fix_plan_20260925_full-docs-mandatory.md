---
title: _fix_plan — full-docs-mandatory (передача полной документации при работе с инструментами)
slug: full-docs-mandatory
version: 2
date: 2026-09-25
revised: 2026-09-25 (GATE:diagnose-review v2; REQUIRES_PLAN_V2)
case: BUGFIX  (НЕ LIGHT — инфраструктурный процесс, >3 файлов канона/скиллов + новый скрипт + shared Registries)
status: diagnose-review-v2
owner: ProcessImprovement / DevKanbanPipeline
kanban: DEV/full-docs-mandatory · корень = t_f0f3ca27 · BUG:diagnose = t_b6ae7121 · GATE:diagnose-review = t_0892ea84
supersedes: v1 (REVIEW_REQUIRED: build-копии, LIGHT-хвост, --force-bypass, opt-in --require-*, диск-кэш экстрактов)
---

# План починки — full-docs-mandatory (v2)

Требование Саши: **всегда при разработке/доработке/починке инструмента передавать
ПОЛНУЮ документацию** (digest экосистемы, сжатые ТЗ инструмента и смежных, GLOSSARY)
и сделать так, чтобы **не передать было НЕВОЗМОЖНО**.

Механика v2: скрипт-перехватчик **не копирует** документы в workspace.
Он **собирает промпт** (`emit-prompt` → `/tmp/task.md`) с блоком обязательных
абсолютных путей и **отказывается писать task.md**, если тройка неполная.
`agent -p` по инструменту легален **только** с выходом `emit-prompt`.

## 1. Прецедент и суть бага (диагноз)

Прецедент 25.09 (pfs-sync-meeting-not-promoted):
- канон DX: `t_41a38f0e` (blocked; comment «полный контекст не передан»);
- дубль: `t_5575e028` (archived).

В карточку BUG:diagnose ушёл только **краткий контекст** (текст бага + страницы +
`PFS_POST_SWITCH`), а НЕ:
- digest экосистемы (`~/WorkVault/Registries/EcosystemManifest.digest.md`);
- мастер-ТЗ инструмента (`TZ/ProtocolFromSummary/ProtocolFromSummary_TZ.md`);
- ТЗ смежных инструментов;
- GLOSSARY (`TZ/GLOSSARY.md`).

Разбор пошёл без мастер-ТЗ и карты экосистемы — не по канону
(`cursor-task-context` 3-слойная подача, tz-workflow handoff, DKP v0.3.5).

**Корень:** канон *описывает* обязательную 3-слойную подачу, но **ничего не
блокирует**, если её пропустить. Сборка контекста — ручной `kanban_create(body=…)`;
машиночитаемой проверки «тройка путей в промпте» нет.

**Сопутствующие дыры (v1 недоназвал, v2 фиксирует):**
1. DKP skills на `BUG:diagnose` = `hermes-feature` + `cursor-cli`, **без**
   `cursor-task-context` — 3-слойный скилл на DX не грузится.
2. Фактический `workspace_kind` DX = `scratch` (удаляется при complete), хотя DKP
   уже требует `dir:` корня инструмента. Scratch + краткий body = физически нет
   пути к ТЗ/digest.
3. Промпт Cursor самодостаточен и не наследует чат Сирени (pitfall cursor-cli).

**Целевое состояние:** ни один `agent -p` по инструменту не стартует без
`emit-prompt` exit 0. Скрипт не пишет производные экстракты на диск. Обхода
`--force` нет. Единственный HITL-исключение — канон `flag-waived: Sasha` в
comment карточки.

## 2. Затрагиваемые компоненты

| Артефакт | Путь | Роль |
|---|---|---|
| **новый** скрипт-перехватчик | `~/WorkVault/Registries/pipeline_context_bundle.py` | `emit-prompt` + `check`; stdlib; без LLM |
| **новый** тест | `~/WorkVault/Registries/test_pipeline_context_bundle.py` | pytest: emit/check 0/1/2, нет диск-кэша |
| скилл `hermes-feature` | `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md` | Блок 6В + HF-фазы: emit-prompt до `agent -p` |
| скилл `tz-workflow` | `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md` | TZ-WRITE: emit-prompt до `agent -p` |
| скилл `cursor-task-context` | `~/.hermes/skills/devops/cursor-task-context/SKILL.md` (канон-дерево: `hermes-workspace/skills`) | 3-слойная подача = emit-prompt, не копии |
| скилл `cursor-cli` | `~/hermes-workspace/skills/devops/cursor-cli/SKILL.md` | единственный легальный `agent -p` = `$(cat emit-prompt.out)` |
| GLOSSARY | `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md` | §6 артефакт «контекст-промпт»; bump 0.2.8 → 0.2.9 + лог версий |
| DKP ТЗ | `~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` | skills DX += cursor-task-context; workspace DX; bump 0.3.5 → 0.3.6 |
| инвентарь | `~/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md` | строка DKP + GLOSSARY на `TZ:finalize` (не HF:impl) |

Паттерн — класс существующих `pipeline_gate_done_preflight.py` /
`pipeline_hf_plan_diskfact.py` (exit 0/1/2, вызывается воркером до действия).
Ядро канбана не патчить. Нового ассемблера промпта в экосистеме нет — один скрипт,
не плодить логику в каждом скилле.

**Reuse-first (закрыто):** не копировать digest/GLOSSARY/ТЗ — они уже на
канонических путях. Не парсить `MAIN_TZ_INVENTORY.md` за смежными ТЗ —
граф `EcosystemManifest.json` → `links[]` (`from` / `to` / `relation`).

## 3. Механизм: emit-prompt + check (без диск-копий)

Один скрипт `~/WorkVault/Registries/pipeline_context_bundle.py`.
Без LLM внутри (компрессор — отдельный вызов оркестратора на Hermes
`deepseek-v4-flash-0731`, GLOSSARY §3; не роль DX-архитектора).
Режима `build` **нет** (снят в v2: копий `ecosystem-digest.md` /
`glossary.md` / `<Name>_TZ.extract.md` в workspace не создавать).

Канонические пути тройки (всегда, не opt-in):

| Компонент | Абсолютный путь |
|---|---|
| digest | `/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.digest.md` |
| GLOSSARY | `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md` |
| ТЗ инструмента | `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/<Name>/<Name>_TZ.md` |

### П.1 Режим `emit-prompt` — единственный легальный вход в `agent -p`

```
python3 ~/WorkVault/Registries/pipeline_context_bundle.py emit-prompt \
  --tool <Name> --card <id> \
  --task-file <abs path фазы> \
  --out /tmp/task.md
```

Поведение:
1. Резолвит `--tool` в `tools{}` манифеста (`name` или ключ). Нет записи /
   нет файла ТЗ на диске → **exit 1**, `--out` **не создаётся и не
   перезаписывается**.
2. Проверяет, что digest и GLOSSARY существуют на канонических путях.
   Любой из трёх отсутствует → **exit 1**, `--out` не писать.
3. Смежные ТЗ: обойти `links[]`, где `from` или `to` равен каноническому
   имени инструмента; второй конец, если он резолвится в `tools{}` с
   существующим `tz_ref` — добавить abs-путь этого ТЗ. Сущности без
   `tz_ref` пропускать. Дедуп, себя не включать. Пустой список extras —
   не ошибка (тройка своего инструмента всё равно обязательна).
   `--extra` CLI **не** заменяет `links[]` (не opt-in обход графа).
4. Снимает `version` YAML + `st_mtime` ISO UTC мастер-ТЗ (контракт TZ-drift
   cursor-task-context).
5. Собирает `--out` = обязательный блок (абс-пути тройки + extras +
   version/mtime + инструкция «прочитай сам, без обрезки») **плюс** тело
   `--task-file`. Экстракт ТЗ **не** писать в файл. Если в comment
   карточки уже есть экстракт `TZ:compress` — вставить его текст в промпт
   (память сессии/comment), не на диск.
6. Пишет `--out` **только** после пунктов 1–5. `/tmp/task.md` — эфемерный
   промпт, не кэш производных ТЗ.
7. Read-only относительно канона: не меняет digest, GLOSSARY, мастер-ТЗ,
   манифест, kanban.db.

Exit: `0` = task.md записан и содержит тройку; `1` = тройка неполная /
файла нет; `2` = ошибка вызова/инвариант.

После успеха воркер: `kanban_comment` маркером
`context-bundle: digest=<abs> glossary=<abs> tz=<abs> tz_version=… tz_mtime=… extras=[…]`
(для последующего `check --card`).

Легальный вызов Cursor:

```
python3 …/pipeline_context_bundle.py emit-prompt --tool <N> --card <id> \
  --task-file /tmp/task_body.md --out /tmp/task.md
# только при exit 0:
agent -p "$(cat /tmp/task.md)" -f --model <MODEL> --workspace <ABS_DIR> \
  --output-format json
```

Любой `agent -p` по инструменту в обход `emit-prompt` — запрещён
(`cursor-cli` + `hermes-feature` + `tz-workflow`).

### П.2 Режим `check` — блокирующая проверка карточки

```
python3 ~/WorkVault/Registries/pipeline_context_bundle.py check \
  --card <id> [--tool <Name>]
```

Читает **body / comments / (если есть) приложенный текст промпта** карточки.
Не читает workspace-копии бандла (их нет). Не пишет kanban.db.

Тройка digest+GLOSSARY+ТЗ — **default-on**. Флагов `--require-glossary` /
`--require-digest` / `--require-tz` **нет** (opt-in = дыра v1).

Exit:
- `0` = в body/comment есть маркер `context-bundle:` с тремя существующими
  abs-путями (или те же три пути явно перечислены);
- `1` = тройка отсутствует/путь не с диска — stderr: список недостающего;
- `2` = нет карточки / ошибка вызова.

Исключение HITL: comment содержит **`flag-waived: Sasha`** → exit 0 + stderr
WARN. CLI-флага `--force` / `--force-bypass-sasha-ok` **нет**.

`check ≠ 0` (и нет waive) → `kanban_block`, `agent -p` не вызывать.

### П.3 Точки встраивания

| Точка | Где | Поведение при emit-prompt/check ≠ 0 |
|---|---|---|
| BUG:diagnose (Блок 6В) | `hermes-feature` | `kanban_block` «диагноз без тройки путей» — DX `agent -p` нет |
| HF:plan / REV:plan | `hermes-feature` Блок 1А | стоп, не вызывать `agent -p` |
| HF:impl / HF:test / HF:docs-handoff | `hermes-feature` Блок 2–4 | стоп |
| TZ-WRITE (patch/finalize) | `tz-workflow` | стоп |
| Сборка промпта Cursor | `cursor-cli` + `cursor-task-context` | `agent -p` только от файла `emit-prompt` |

Компрессор (если нужен слой-1 экстракт в промпте): **отдельный** вызов
оркестратора до `emit-prompt`, результат в comment/сессии. Скрипт LLM не зовёт.
На DX, пока `TZ:compress` ещё не было: слой-1 = инструкция «прочитай сам»
мастер-ТЗ по abs-пути (канон hermes-feature: путь + «прочитай сам», не обрезка).

### П.4 Канонизация

- GLOSSARY §6: строка «контекст-промпт \| `pipeline_context_bundle.py emit-prompt` \|
  обязателен для BUG:diagnose / TZ-WRITE / HF-фаз; диск-кэша экстракта нет».
  Версия **0.2.8 → 0.2.9**, запись в лог версий внизу файла (как v0.2.6–0.2.8).
- DKP ТЗ **0.3.5 → 0.3.6**: перед любым `agent -p` по инструменту — `emit-prompt`;
  skills `BUG:diagnose` += `cursor-task-context`; workspace DX — §3.П.6;
  `--force` на скрипте запрещён; обход только `flag-waived: Sasha`.
- Четыре скилла: обязательный шаг emit-prompt/check до `agent -p`.

### П.5 Тесты (pytest)

`test_pipeline_context_bundle.py`:
- emit-prompt при живой тройке на фикстурах пишет `--out` с тремя abs-путями;
- emit-prompt при отсутствии любого из трёх файлов → exit 1 и `--out` нет;
- check без тройки в comment/body → exit 1; с маркером → exit 0;
- emit-prompt **не** создаёт `*.extract.md` / копий digest/GLOSSARY рядом с `--out`;
- `flag-waived: Sasha` в comment → check exit 0;
- нет CLI `--force`;
- extras резолвятся из фикстуры `links[]`, не из markdown-инвентаря;
- появление impl до plan-approve — **не** этот скрипт (`pipeline_hf_plan_diskfact.py`).

Сухой прогон на синтетической карточке (с тройкой / без) — **в scope `HF:test`**
(бывший v1 П.6 «вне scope» снят).

### П.6 Workspace DX (кросс-канонный фикс)

`scratch` для пайплайна **запрещён** (DKP: удаляется при complete).

| Класс бага | `workspace_kind` карточки BUG:diagnose |
|---|---|
| USERTOOL | `dir:/home/tkachenkoav/USERTOOLS/<Tool>` |
| только скилл | `dir:/home/tkachenkoav/hermes-workspace/skills` |
| кросс-канон пайплайна (GLOSSARY / DKP / Registries / несколько скиллов) — этот кейс | `dir:/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` |

Промпт всё равно несёт abs-пути тройки (они могут лежать вне `--workspace`).
Для **этого** графа `full-docs-mandatory` DX/TZ-карточки: `dir:…/TZ`.

### П.7 Multi-workspace HF:impl — решение (закрыто)

Правки impl лежат в **трёх непересекающихся** деревьях:

1. `/home/tkachenkoav/hermes-workspace/skills` — 4 SKILL.md
2. `/home/tkachenkoav/WorkVault/Registries` — скрипт + pytest
3. `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` — GLOSSARY + DKP ТЗ

**Выбор: одна карточка `HF:impl`, три последовательных `agent -p`
(один и тот же исполнитель `composer-2.5`), разные `--workspace`.**

Не выбираем:
- общий `--workspace /home/tkachenkoav` — слишком широко (`.env`, `kanban.db`,
  `config.yaml`);
- три параллельных фона — кап DKP «макс. 2 параллельных непересекающихся
  `--workspace`»;
- три child с выдуманными фазами `HF:impl-skills` и т.п. — карточка = только
  фаза GLOSSARY §5, синонимы запрещены.

Порядок внутри `HF:impl` (последовательно, `--resume` своей сессии на каждый
workspace; `session_id` в comment):
1. `--workspace …/hermes-workspace/skills`
2. `--workspace …/WorkVault/Registries`
3. `--workspace …/WorkVault/Hermes-Backlog/TZ`

Допускается ускорение: шаги 1 и 2 **параллельно** (два фона, деревья не
пересекаются), шаг 3 после обоих. Шаг 3 не параллелить с 1–2. `TZ:finalize`
уже запишет инвентарь; impl на дереве TZ правит только master DKP + GLOSSARY
по плану, инвентарь — фаза `TZ:finalize`.

`HF:test`: `--workspace …/WorkVault/Registries` (pytest скрипта) + grep скиллов
на дереве skills (второй вызов или чтение abs-путём).
`ORCH:shared-state`: `dir:…/WorkVault/Registries` + `restore-all-skills.sh`.

## 4. Критерии приёмки (AC наблюдаемы)

Диск-семантика v1 (AC «файлы бандла существуют в --out») **снята**.

- **AC-001:** `emit-prompt --tool <N> --task-file <f> --out /tmp/task.md` при
  существующих digest+GLOSSARY+`TZ/<N>/<N>_TZ.md` создаёт `/tmp/task.md`,
  в котором есть все три **абсолютных** пути (grep/assert).
- **AC-002:** `check --card <id>` без тройки в body/comment → exit 1 + stderr
  со списком недостающего; с полным маркером `context-bundle:` → exit 0.
- **AC-003:** `emit-prompt` при отсутствии любого из трёх канонических файлов
  **не** создаёт и не перезаписывает `--out`; exit 1.
- **AC-004:** pytest: после `emit-prompt` нет `*.extract.md` и нет копий
  `ecosystem-digest.md` / `glossary.md` в каталоге `--out` и в Registries
  (запрет дискового кэша экстракта, DKP «экстракт только в comment/сессии»).
- **AC-005:** `HF:test` — pytest `test_pipeline_context_bundle.py` зелёный
  (emit/check 0/1/2) **и** сухой прогон `check` на синтетической карточке
  с тройкой (exit 0) и без (exit 1). Бывший v1 П.6 входит в этот AC.

Канон на диске (проверяется `TZ:finalize` / `HF:docs-handoff`, трассируется
IAC на `HF:plan`): GLOSSARY §6 + лог v0.2.9; DKP skills `BUG:diagnose` содержит
`cursor-task-context`; четыре скилла содержат шаг emit-prompt до `agent -p`;
в скрипте и скиллах нет `--force-bypass-sasha-ok`.

## 5. Вердикт и граф

**BUGFIX (полный), НЕ LIGHT:** 4 скилла + GLOSSARY + DKP-ТЗ + новый скрипт +
тесты; shared-модуль `Registries/pipeline_*.py`; вне «≤3 файла кода+тесты,
вне shared». Приоритет: средний.

**Граф после этого GATE:diagnose-review** (GLOSSARY §2 BUGFIX =
`DX` → `BRF(delta)` → `TZ-WRITE(patch)` → `TAKE-INTO-WORK` → `PLAN-IMPL-TAIL`;
`HF:compress` skip; `REV:tz` **ON** — >3 файлов, не LIGHT):

```
DX (done)  BUG:diagnose t_b6ae7121 → GATE:diagnose-review t_0892ea84  # эта фаза
BRF(delta) в TG, не карточка; при уже зафиксированном требовании Саши — no-op,
           не замена TZ-WRITE
TZ:patch            parents=[GATE:diagnose-review]
REV:tz              parents=[TZ:patch]          # ON, >3 файлов
TZ:finalize         parents=[REV:tz]            # DKP+GLOSSARY+инвентарь, LOCK_EX
GATE:take-into-work parents=[TZ:finalize]       # HITL Саши, never auto, payload=AC
HF:plan             parents=[GATE:take-into-work]
REV:plan            parents=[HF:plan]
GATE:plan-approve   parents=[REV:plan]          # always auto
HF:backup           parents=[GATE:plan-approve]
HF:impl             parents=[HF:backup]         # 3 sequential --workspace, §3.П.7
HF:test             parents=[HF:impl]
HF:docs-handoff     parents=[HF:test]
ORCH:shared-state   parents=[HF:docs-handoff]   # restore-all-skills.sh; манифест по hints
GATE:done           parents=[ORCH:shared-state] # HITL Саши; preflight exit 0 необходим
```

**Запрещено:** хвост PLAN-IMPL-TAIL-LIGHT (`HF:impl` → `HF:test` →
`HF:docs-handoff` → `GATE:done` без plan/backup/ORCH/REV). v1 §5 содержал
эту ошибку — в v2 снята.

`ORCH:shared-state` **обязателен**: патч скиллов → `restore-all-skills.sh`.
Исполнитель манифест не пишет.

## 6. Изменяемые файлы (для HF:impl / TZ-WRITE)

- [новый] `~/WorkVault/Registries/pipeline_context_bundle.py`
- [новый] `~/WorkVault/Registries/test_pipeline_context_bundle.py`
- `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md` (bump version скилла)
- `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md` (bump version скилла)
- `~/hermes-workspace/skills/devops/cursor-task-context/SKILL.md` (bump version скилла)
- `~/hermes-workspace/skills/devops/cursor-cli/SKILL.md` (bump version скилла)
- `~/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md` — **version 0.2.8 → 0.2.9** + секция
  лога `## v0.2.9 — контекст-промпт emit-prompt (2026-09-25)`
- `~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` —
  **version 0.3.5 → 0.3.6** + changelog-секция
- `~/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md` — на `TZ:finalize` под `LOCK_EX`

## 7. Что НЕ трогать

- Ядро канбана (`kanban_db.py`, диспетчер, worker-вход).
- Существующие guard-скрипты (`pipeline_gate_done_preflight.py`,
  `pipeline_hf_plan_diskfact.py`) — не переписывать; новый скрипт рядом.
- Содержательный текст чужих ТЗ инструментов (только чтение путей).
- Gateway, кроны, `.env`, `jobs.json`.
- `EcosystemManifest.json` / digest — вход `links[]` и digest; запись манифеста
  только `ORCH:shared-state` по `manifest_hints`, если появятся.
- Диск-кэш экстрактов компрессора — **не вводить**.
- CLI `--force` / `--force-bypass-sasha-ok` — **не вводить**.
- Не inventить фазы `HF:impl-*`.
- Не общий `--workspace /home/tkachenkoav` на impl.

## 8. Закрытые решения (diagnose-review v2)

Открытых решений нет. v1 §8 снят целиком.

| Тема | Решение | Почему не HF:plan |
|---|---|---|
| Где хранить «бандл» | Нигде как копии. Маркер `context-bundle:` в comment + абс-пути в `/tmp/task.md` | zip/`kanban_attach` = запрещённый кэш; workspace DX не виден детям |
| Формат экстракта | Не файл. Comment/сессия компрессора или «прочитай сам» мастер-ТЗ | DKP: экстракт только в comment/сессии, диск-кэша нет |
| Смежные ТЗ | `EcosystemManifest.json` `links[]` (`from`/`to`/`relation`) → `tools[].tz_ref` | инвентарь — проза, не граф |
| Обход | только `flag-waived: Sasha` в comment | «невозможно»; новый `--force` = синоним дыры |
| HF:impl workspace | одна карточка, 3 последовательных `agent -p` (допустимы 2 параллели skills+Registries, затем TZ) | §3.П.7; кап 2 фона; нет безопасного общего корня |
| Workspace DX кросс-канон | `dir:…/Hermes-Backlog/TZ` | scratch запрещён; тройка всё равно abs-путями в промпте |
| Skills DX | += `cursor-task-context` | иначе 3-слойный скилл не на карточке |
| Граф | полный BUGFIX + REV:tz ON + ORCH | не LIGHT; 4 скилла → restore |
