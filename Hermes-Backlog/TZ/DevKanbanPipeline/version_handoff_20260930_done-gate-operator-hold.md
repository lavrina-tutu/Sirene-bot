# version-handoff — done-gate operator-hold (2026-09-30)

Граф: `DEV/done-not-final-REAL` (канон «не закрывать карточку, пока не выполнены ВСЕ работы (вкл. действия Саши)»)
Карточка плана: `t_afff228d` · фаза handoff: `HF:docs-handoff`
Исполнитель: composer-2.5 (код/скиллы/скрипты реализованы в `HF:impl`/`HF:test`; здесь — docs + верификация IAC-09)

## Скоуп пакета

Закрытие дыр **(а)** operator-hold проглочен на `GATE:done` (прецедент `DEV/tg-topic-duplicate`, `t_07c4913c`) и **(б)** хвост оборван без `GATE:done` (прецедент `DEV/pfs-task-human-slug`, `HF:plan` done, `children=[]`). W0-канон текста уже на диске; этот граф — механика W1–W2 (скрипты + скиллы + pytest), W3–W4 — restore + смоук (следующие фазы).

**Вне скоупа:** `DialogBacklogToKanban_TZ.md`; §29 PFS / `pfs-task-slug-not-created`; ретро-hold duplicate (П.7); патч ядра канбана; `jobs.json` / крон сторожа `998664fd5843` (every 5m, без изменений).

## Версии канона (W0, без правок в этой фазе)

| Артефакт | Версия | Суть для done-gate |
|---|---|---|
| `GLOSSARY.md` | **0.2.12** | Слой S/O/C; «выполнение operator-AC ≠ показ»; auto-набор гейтов §5 не расширен |
| `DevKanbanPipeline_TZ.md` | **0.4.2** (`mtime` 2026-09-30T11:25:21Z) | Таблица S/O/C; preflight п.10–11; AC-D01…D08; `review-required: operator-action:<verb>` |
| `EcosystemManifest.digest.md` | 2026-09-29T18:59:22+00:00 | **Не обновлялся** этим графом — регенерация в `ORCH:shared-state` |

## Что изменилось на диске (W1–W2, подтверждает docs-handoff)

### `~/WorkVault/Registries/pipeline_gate_done_preflight.py` (W1)

- Парсеры `operator-holds` / `open-questions` из comment корня ∪ `GATE:take-into-work`; опциональный grep `depends: operator:<verb>` в master-ТЗ по `tz_path`.
- Проверки `--mode done`: open hold без `operator-done` + `evidence` → FAIL; висящий `Q-n` → FAIL; анти-фикшн O-AC (⏳/ОЖИДАЕТ на AC из holds при наличии `AC-delivered:`); доп. ветка «pfs-форма» (после done `HF:plan` без `GATE:plan-approve`/`HF:impl` для не-LIGHT).
- `GATE_NO_AUTO_PASS` = `{GATE:go, GATE:block-accept}` — **не расширен** operator-hold.
- `--mode create` не требует `operator-done`.

### `~/WorkVault/Registries/test_pipeline_gate_done_preflight.py` (W1)

- Тесты **T-OH1…T-OH7** + регресс T28–T30 (`GATE_NO_AUTO_PASS` узкий набор).

### `~/.hermes/scripts/kanban_stuck_monitor.py` (W1)

- **Правило 7** — operator-hold reminder в **origin** графа (`kanban_notify_subs`), throttle 4ч, эскалация hold >8ч; без `:7`/DM; без выполнения глагола / gateway / `jobs.json`.
- **Правило 8** — broken-tail mid-graph (`review-required: broken-tail: …` или алерт при фиктивно done корне); throttle 4ч.
- Правила 1–6 по смыслу не менялись.

### `~/WorkVault/Registries/test_kanban_stuck_monitor.py` (W1)

- Dry-run OH/broken-tail, throttle, тишина при 0 инцидентов, без `set-model`/`reclaim` в 7–8.

### Скиллы (W2, workspace → restore в ORCH)

| Скилл | До | После | Коммит |
|---|---|---|---|
| `tz-workflow` | 2.8.0 | **2.9.0** | `c641c144313fb330709ee704da7922a6021903f7` (`hermes-workspace` main) |
| `hermes-feature` | 2.11.0 | **2.12.0** | тот же |

**tz-workflow 2.9.0:** отказ `kanban_create` при open `open-questions`; durable `Q-n` на корне + `operator-action: answer:Q-n`; после `TZ:finalize` — блок `operator-holds:` на корень/`GATE:take-into-work`; гейты: preflight 0 включает снятые holds и пустые Q.

**hermes-feature 2.12.0:** на `GATE:done` — нельзя ✅ на O-AC open; preflight 1 → block `operator-action:`; запрет `kanban_complete` корня до done `GATE:done`; `HF:plan` + `children=[]` → `broken-tail`; чеклист verification дополнен.

Копии `pipeline_gate_done_preflight.py` внутри `tz-workflow/` — **не канон** (SoT = `WorkVault/Registries/`).

## Манифест (для ORCH:shared-state)

`EcosystemManifest.json`: поле `version` у записей скиллов по-прежнему отсутствует; триггеры/tools этим пакетом не менялись. Ожидаемые шаги ORCH: `restore-all-skills.sh`, `render_manifest.py` / `--check-drift` при отсутствии дрейфа вне слага; **`jobs.json` не трогать**.

## Верификация docs (фаза HF:docs-handoff)

### IAC-09 — «preflight 0 достаточен» / preflight exit 0

| Файл | Строка | Оговорка operator-hold / open-questions |
|---|---|---|
| `hermes-feature/SKILL.md` | 248 | «preflight 0 достаточен **после снятия operator-holds `operator-done`+evidence и пустых open-questions**» |
| `hermes-feature/SKILL.md` | 253 | «Preflight exit 0 **достаточен** … **после снятия holds и пустых Q**» |
| `tz-workflow/SKILL.md` | 357 | «preflight exit 0 **после снятия operator-holds и пустых open-questions**» |

Точная подстрока «preflight 0 достаточен» встречается только в `hermes-feature` (2×), обе с оговоркой. В `tz-workflow` эквивалент на строке 357. Схема CHANGE-LIGHT (стр. 244) — краткая цепочка фаз; норматив гейтов — § «Гейты — оба канала» (стр. 357).

### Прочее

- Frontmatter: `tz-workflow=2.9.0`, `hermes-feature=2.12.0`.
- `rg` в скиллах: `operator-holds`, `open-questions`, `operator-action:` — присутствуют; `kind=needs_input` на TZ/HF — запрет сохранён.
- Pytest (канон Registries, tmp `HERMES_KANBAN_DB`): **63 passed** (`test_pipeline_gate_done_preflight.py` + `test_kanban_stuck_monitor.py`), включая T-OH1…T-OH7.
- DKP changelog в этой фазе **не** бампался (master уже 0.4.2).

## Следующие шаги (не эта фаза)

1. `ORCH:shared-state` — restore скиллов, digest при необходимости.
2. Смоук **W4** по плану `_smoke-plan-done-gate-20260930.md` (slug `_smoke-train-done-gate` или guard `_smoke-train`).
3. Таблица результатов смоука — `appendix_done-gate_smoke_YYYYMMDD.md` (оркестратор / `GATE:done`).

## Метаданные `kanban_complete` (HF:docs-handoff)

```yaml
role: исполнитель
model: composer-2.5
tz_version: 0.4.2
tz_mtime: 2026-09-30T11:25:21Z
iac_passed: [IAC-09]
changed_files:
  - ~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/version_handoff_20260930_done-gate-operator-hold.md
  - ~/WorkVault/Hermes-Backlog/TZ/DevKanbanPipeline/_smoke-plan-done-gate-20260930.md
git_proof:
  hermes-workspace: c641c144313fb330709ee704da7922a6021903f7  # tz-workflow 2.9.0, hermes-feature 2.12.0
cursor_session_id: unavailable-in-cli-worker
```
