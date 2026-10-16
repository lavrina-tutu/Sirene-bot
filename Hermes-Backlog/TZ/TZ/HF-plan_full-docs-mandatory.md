---
title: "HF:plan — full-docs-mandatory (контекст-промпт emit-prompt/check; план impl)"
slug: full-docs-mandatory
case: BUGFIX (полный, НЕ LIGHT)
phase: HF:plan
source: _fix_plan_20260925_full-docs-mandatory.md (v2)
binding-delta: решение Саши 26.09 «правило БЕЗ ИСКЛЮЧЕНИЙ»
date: 2026-09-26
---

# План реализации — full-docs-mandatory (HF:plan → HF:impl/test/docs-handoff/ORCH)

## 1. Контекст и binding-delta (Саша 26.09)

Механика: один скрипт-перехватчик `~/WorkVault/Registries/pipeline_context_bundle.py`
(`emit-prompt` + `check`), stdlib, без LLM. Он НЕ копирует документы в workspace;
собирает промпт `/tmp/task.md` с блоком обязательных абс-путей (digest + GLOSSARY +
мастер-ТЗ инструмента + необязательные extras из `links[]`) и отказывается писать
`--out`, если тройка неполная. `agent -p` по инструменту легален только с export 0
`emit-prompt`.

**Binding-delta Саши 26.09 (приоритет сверх исходного ТЗ v0.3.6):**
- Скрипт и `check` блокируют старт **ВСЕГДА, без обходов**.
- В коде и скиллах **не должно быть** `flag-waived` (как обход context-bundle) и
  `--force-bypass-sasha-ok`.
- Канонический текст DKP дорабатывается: убрать «Обход тройки только flag-waived:
  Sasha» (5 мест в DKP v0.3.6) → «обхода нет».

**Не трогается (отдельный механизм):** `flag-waived: Sasha` как **skip-путь REV**
(GLOSSARY §5.2, preflight #4 `REV_WAIVED_MARKER`). Это про `REV:tz`, не про
context-bundle. Plan v2 §7 «существующие guard-скрипты не переписывать» — в силе.

## 2. Фактическое состояние (собрано 26.09)

| Артефакт | Путь на диске | Статус |
|---|---|---|
| скрипт | `~/WorkVault/Registries/pipeline_context_bundle.py` | **нет (создать)** |
| тест | `~/WorkVault/Registries/test_pipeline_context_bundle.py` | **нет (создать)** |
| digest | `/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.digest.md` | есть (updated 2026-09-24) |
| манифест | `/home/tkachenkoav/WorkVault/Registries/EcosystemManifest.json` | есть; `tools`=dict ключом snake_case, все 45 имеют `tz_ref`; `links[]` поле `from`/`to`/`relation`/`note` |
| GLOSSARY | `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md` | v0.2.9 (уже содержит §6 «контекст-промпт», стр.223; bump до 0.2.10) |
| DKP ТЗ | `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/DevKanbanPipeline_TZ.md` | v0.3.6 (содержит 5 ссылок на «обход только flag-waived» — править; bump до 0.3.7) |
| скилл hermes-feature | `~/hermes-workspace/skills/devops/hermes-feature/SKILL.md` (git) | v2.8.0 → 2.9.0; emit-prompt-шаг ещё НЕТ |
| скилл tz-workflow | `~/hermes-workspace/skills/devops/tz-workflow/SKILL.md` (git) | v2.5.0 → 2.6.0; emit-prompt-шаг ещё НЕТ |
| скилл cursor-cli | `~/.hermes/skills/devops/cursor-cli/SKILL.md` (реал. каталог, НЕ git) | v1.1.3 → 1.2.0; emit-prompt-шаг ещё НЕТ |
| скилл cursor-task-context | `~/.hermes/skills/devops/cursor-task-context/SKILL.md` (реал. каталог, НЕ git) | v1.1.1 → 1.2.0; emit-prompt-шаг ещё НЕТ |
| инвентарь | `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md` | обновляется на `TZ:finalize` (уже исполнен на 0.3.6/0.2.9; bump 0.3.7/0.2.10 — exception через ORCH, см. §6) |

**Ключевая поправка к плану v2 §3.П.7:** четыре скилла лежат в **двух** деревьях
(2 git-в-hermes-workspace + 2 реальных в `~/.hermes/skills/devops`), не в одном.
Физически корней impl **четыре**, а не три:
1. `/home/tkachenkoav/hermes-workspace/skills` — hermes-feature, tz-workflow
2. `/home/tkachenkoav/.hermes/skills/devops` — cursor-cli, cursor-task-context
3. `/home/tkachenkoav/WorkVault/Registries` — скрипт + pytest
4. `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ` — GLOSSARY + DKP

Порядок и параллельность — §4.1.

## 3. IAC-трассировка AC-001..005

| IAC | phase_from→phase_to | path | verify | depends | covers |
|---|---|---|---|---|---|
| IAC-01 | impl→impl | `Registries/pipeline_context_bundle.py` emit-prompt | pytest + сухой прогон (ниже) | — | AC-001, AC-003, AC-004 |
| IAC-02 | impl→impl | `Registries/pipeline_context_bundle.py` check | pytest + сухой прогон | IAC-01 | AC-002, AC-005 |
| IAC-03 | impl→impl | `Registries/test_pipeline_context_bundle.py` | pytest зелёный; grep «нет flag-waived / нет --force / нет *.extract.md» | IAC-01, IAC-02 | AC-004, AC-005, delta 26.09 |
| IAC-04 | impl→impl | 4× `SKILL.md` + GLOSSARY + DKP | grep по версии + emit-prompt-шаг присутствует; «нет обхода» | IAC-01..03 | delta 26.09 (канон) |
| IAC-05 | impl→test | весь пакет | `python3 -m pytest` целевых тестов зелёный | IAC-04 | AC-005 |
| IAC-06 | test→docs-handoff | `check` на синтетической карточке | сухой прогон exit 0 (с тройкой) / exit 1 (без) | IAC-05 | AC-003, AC-005 |
| IAC-07 | docs-handoff→orch | DKP/GLOSSARY текст + manifest_hints | grep «нет --force-bypass-sasha-ok» во всех | IAC-06 | delta 26.09 |

## 4. HF:impl — пофайловые шаги (4 корня, один исполнитель composer-2.5)

### 4.1 Порядок вызовов `agent -p`

Одна карточка `HF:impl`. Четыре последовательных вызова, разные `--workspace`:

```bash
# (1) Дерево слоев/скиллов (git) — hermes-feature + tz-workflow
agent -p "$(cat /tmp/task.md)" -f --model composer-2.5 \
  --workspace /home/tkachenkoav/hermes-workspace/skills \
  --output-format json
# (2) Дерево скиллов (~/.hermes) — cursor-cli + cursor-task-context
agent -p "$(cat /tmp/task.md)" -f --model composer-2.5 \
  --workspace /home/tkachenkoav/.hermes/skills/devops \
  --output-format json
# (3) Registries — скрипт + pytest
agent -p "$(cat /tmp/task.md)" -f --model composer-2.5 \
  --workspace /home/tkachenkoav/WorkVault/Registries \
  --output-format json
# (4) TZ — GLOSSARY + DKP
agent -p "$(cat /tmp/task.md)" -f --model composer-2.5 \
  --workspace /home/tkachenkoav/WorkVault/Hermes-Backlog/TZ \
  --output-format json
```

Разрешено ускорить: (1)∥(2) параллельно (два непересекающихся дерева, лимит 2 фона),
затем (3), затем (4). Шаг (4) с (1–3) не параллелить. `--resume` своей сессии на
каждый workspace; `session_id` каждого — в `kanban_comment`.

> Правило: каждый вызов — отдельная промпт-транзакция через `emit-prompt`. Пока
> скрипта нет, воркер фиксирует тройку путей вручную (абс-пути выше) и помечает
> «check-вызов появится с HF:impl» — это разрешено телом фазы HF:plan.

### 4.2 Корень 3 — `Registries/pipeline_context_bundle.py` (новая, stdlib)

Стиль и exit-контракт — как `pipeline_gate_done_preflight.py` (argparse; exit
0/1/2; read-only к канону и kanban.db). CLI:

```bash
python3 ~/WorkVault/Registries/pipeline_context_bundle.py emit-prompt \
  --tool <Name> --card <id> --task-file <abs> --out /tmp/task.md
python3 ~/WorkVault/Registries/pipeline_context_bundle.py check \
  --card <id> [--tool <Name>]
```

Поведение `emit-prompt` (по плану v2 П.1, С БИНДИНГ-ДЕЛЬТОЙ 26.09):
1. Резолв `--tool`: матч по `tools[*].name` (напр. `ProtocolFromSummary`) или по
   snake_case-ключу манифеста. Нет записи / нет `TZ/<Name>/<Name>_TZ.md` на диске
   → **exit 1**, `--out` не создавать/не перезаписывать.
2. Проверить существование digest + GLOSSARY на канонических путях. Любой из трёх
   отсутствует → **exit 1**, `--out` не писать.
3. Extras: обойти `EcosystemManifest.json["links"]` (поле `from`/`to`); где один
   конец равен каноническому имени инструмента — второй конец резолвить в
   `tools{}` (snake_case-ключ) с существующим `tz_ref` → добавить abs-путь `TZ_ROOT/<tz_ref>`.
   Дедуп, себя не включать, сущности без `tz_ref` пропускать. Пустой extras — не ошибка.
   CLI `--extra` **нет** (не opt-in обход графа).
4. Снять `version` YAML + `st_mtime` ISO UTC мастер-ТЗ.
5. Собрать `--out`: обязательный блок (абс-пути тройки + extras + version/mtime +
   инструкция «прочитай сам, без обрезки») **плюс** тело `--task-file`. Если в
   comment есть экстракт `TZ:compress` — вставить текст (не на диск). Экстракт в
   файл **не** писать.
6. Писать `--out` только после 1–5. `/tmp/task.md` — эфемерный промпт.
7. Read-only к канону.

Поведение `check` (по П.2, **С дельтой 26.09**):
- Читает `body` / `comments` карточки. Не читает workspace-копии, не пишет kanban.db.
- Тройка digest+GLOSSARY+ТЗ — **default-on**, флагов `--require-*` нет.
- **exit 0** = в body/comment есть маркер `context-bundle:` с тремя **существующими**
  abs-путями (или те же три явно перечислены).
- **exit 1** = тройка неполная/путь не на диске → stderr список недостающего.
- **exit 2** = нет карточки / ошибка вызова.
- **Скрипт НЕ содержит: обход `flag-waived`, CLI `--force`, `--force-bypass-sasha-ok`.**
  comment с `flag-waived` БЕЗ тройки → exit 1 (обход невозможен).

`check != 0` (и нет валидной тройки) → `kanban_block`, `agent -p` не вызывать.

Канон вызова после успеха `emit-prompt`:

```bash
python3 …/pipeline_context_bundle.py emit-prompt --tool <N> --card <id> \
  --task-file /tmp/task_body.md --out /tmp/task.md
# только при exit 0:
agent -p "$(cat /tmp/task.md)" -f --model <MODEL> --workspace <ABS_DIR> \
  --output-format json
```

После успеха воркер пишет `kanban_comment` маркером:
`context-bundle: digest=<abs> glossary=<abs> tz=<abs> tz_version=… tz_mtime=… extras=[…]`.

### 4.3 Корень 3 — `Registries/test_pipeline_context_bundle.py` (новая)

pytest (стиль `test_pipeline_gate_done_preflight.py`, фикстуры tmp_path + синтетический
манифест). Обязательный набор (план v2 П.5, **с дельтой 26.09**):

- emit-prompt при живой тройке на фикстурах пишет `--out` с тремя abs-путями;
- emit-prompt при отсутствии любого из трёх файлов → exit 1 и `--out` не создан;
- check без тройки в comment/body → exit 1; с маркером `context-bundle:` → exit 0;
- emit-prompt **не** создаёт `*.extract.md` / копий digest/GLOSSARY рядом с `--out`;
- **`flag-waived: Sasha` в comment без тройки → check exit 1 (НЕ обход)**;
- **нет CLI `--force` / `--force-bypass-sasha-ok`** (парсер их не принимает);
- extras резолвятся из фикстуры `links[]`, не из инвентаря;
- реализация до plan-approve — не этот скрипт (`pipeline_hf_plan_diskfact.py`).

### 4.4 Корень 1+2 — четыре SKILL.md (emit-prompt/check шаг, bump версии)

В каждый из 4 SKILL.md добавить обязательный шаг emit-prompt/check до `agent -p`
(точечно в профильные места):

1. `hermes-feature` → Блок 6В (`BUG:diagnose`) и HF-фазы: «перед любым `agent -p`
   по инструменту — `emit-prompt` (exit 0), иначе стоп». Версия 2.8.0 → **2.9.0**.
2. `tz-workflow` → `TZ-WRITE` (patch/finalize): то же. Версия 2.5.0 → **2.6.0**.
3. `cursor-cli` → единственный легальный `agent -p` = `$(cat emit-prompt.out)`.
   Версия 1.1.3 → **1.2.0**.
4. `cursor-task-context` → 3-слойная подача = `emit-prompt` (абс-пути в `/tmp/task.md`),
   не копии. Версия 1.1.1 → **1.2.0**.

В формулировках скиллов **не допускать** `flag-waived` или `--force` как обход
context-bundle (дельта 26.09).

### 4.5 Корень 4 — GLOSSARY + DKP (канонический текст, дельта 26.09)

- `GLOSSARY.md`: версия 0.2.9 → **0.2.10**; добавить changelog
  `## v0.2.10 — БЕЗ ИСКЛЮЧЕНИЙ (решение Саши 26.09)` (рядом с v0.2.6–v0.2.9 внизу
  файла). §6 стр.223 уже описывает контекст-промпт — дополнить фразой «обхода
  (flag-waived/--force) нет; скрипт/check блокируют всегда».
- `DevKanbanPipeline_TZ.md`: версия 0.3.6 → **0.3.7**. Аналогичный changelog.
  В 5 местах заменить «Обход тройки только flag-waived: Sasha» → «обхода нет:
  скрипт/check блокируют старт всегда (решение Саши 26.09)». Это строки
  v0.3.6-возникшие: 110, 501, 526, 1041, 1196.
- `--force-bypass-sasha-ok` во всём каноне не оставлять как легитимный (только как
  «не вводить» — и то убрать упоминание как обхода, оставить «CLI --force/--force-bypass
  отсутствует»).

## 5. HF:test — воспроизводимые команды

```bash
cd /home/tkachenkoav/WorkVault/Registries
python3 -m pytest test_pipeline_context_bundle.py -q                      # целевой
python3 -m pytest test_pipeline_gate_done_preflight.py -q                # регресс (не трогаем)
```

Сухой прогон check (синтетическая карточка): с тройкой → exit 0; без → exit 1.

Grep-проверки (запрещённые обходы/кэши) — по абс-путям первой строкой:

```bash
grep -rn "flag-waived\|--force\|--force-bypass-sasha-ok" \
  /home/tkachenkoav/WorkVault/Registries/pipeline_context_bundle.py 2>/dev/null || true
# допускается 0 совпадений в новом скрипте; в скиллах/каноне — только «обхода нет»,
# без «обход только flag-waived» в контексте context-bundle.
find /home/tkachenkoav/WorkVault/Registries -name "*.extract.md" 2>/dev/null   # → пусто
find /home/tkachenkoav/WorkVault/Registries -name "ecosystem-digest.md" -o -name "glossary.md" 2>/dev/null
# → пусто (нет копий digest/GLOSSARY)
```

Требование Саши 26.09 (зафиксировано в comment HF:plan): в карточку/prompt попадают
**только** нужные ТЗ (релевантные инструменту); входящие ТЗ перечислять в промпте
**явным списком** (чтобы Саша видел состав). Включить в AC/тесты — фикстуры check
используют список из ровно трёх (или трёх+extras) путей, не тянут смежные вслепую.

## 6. HF:docs-handoff / ORCH:shared-state

- `HF:docs-handoff` (composer-2.5): актуализировать текст 4 скиллов + GLOSSARY + DKP
  (версии выше); **не** писать манифест/инвентарь — только `manifest_hints`.
- `ORCH:shared-state` (dir `…/WorkVault/Registries`): `restore-all-skills.sh` +
  запись манифеста/digest по hints. **Exception к плану v2 §6:** bump DKP/GLOSSARY до
  0.3.7/0.2.10 уже ПОСЛЕ исполненного `TZ:finalize` (инвентарь на 0.3.6/0.2.9).
  Поэтому ORCH обновляет версии DKP+GLOSSARY в `MAIN_TZ_INVENTORY.md` (перейти на
  LOCK_EX, согласованно) — это легитимное исключение, флаг для REV:plan.
- Исполнитель манифест/инвентарь не пишет.

## 7. Что НЕ трогать

- Ядро канбана, `pipeline_gate_done_preflight.py`, `pipeline_hf_plan_diskfact.py`.
- Skip-путь `flag-waived: Sasha` для **REV** (preflight #4) — отдельный механизм.
- Текст чужих ТЗ инструментов (только чтение путей).
- Gateway, кроны, `.env`, `jobs.json`, `config.yaml`.
- Диск-кэш экстракта, CLI `--force`/`--force-bypass-sasha-ok` — не вводить.

## 8. Прогресс выполнения

- [ ] HF:impl корень 1 (hermes-feature, tz-workflow) 2.9.0/2.6.0
- [ ] HF:impl корень 2 (cursor-cli, cursor-task-context) 1.2.0/1.2.0
- [ ] HF:impl корень 3 (скрипт + pytest)
- [ ] HF:impl корень 4 (GLOSSARY 0.2.10, DKP 0.3.7)
- [ ] HF:test зелёный + grep-проверки + сухой прогон check
- [ ] HF:docs-handoff текст канона/скиллов + manifest_hints
- [ ] ORCH:shared-state restore + инвентарь (version cell 0.3.7/0.2.10)