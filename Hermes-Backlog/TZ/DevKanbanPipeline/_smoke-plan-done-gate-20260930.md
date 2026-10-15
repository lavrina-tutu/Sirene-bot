# Смоук-план W4 — done-gate operator-hold (IAC-11)

**Граф-источник:** `DEV/done-not-final-REAL` · план `t_afff228d`  
**Дата плана:** 2026-09-30  
**Исполнитель смоука:** оркестратор (не архитектор `HF:plan`)  
**Связь:** `version_handoff_20260930_done-gate-operator-hold.md`

Это **не pytest**. Живой канбан-граф с лагом `_smoke-train-done-gate` (если имя занято — lookup slug-guard и вариант `_smoke-train`). В конце — **archive** всех карточек смоука.

## Предусловия

- W1–W2 на диске: `pipeline_gate_done_preflight.py`, `kanban_stuck_monitor.py` (правила 7–8), скиллы **2.9.0** / **2.12.0** после `ORCH:shared-state` (`restore-all-skills.sh`).
- Крон сторожа `998664fd5843` (every 5m) — без изменений; для проверки nudge достаточно `kanban_stuck_monitor.py --dry-run` или ближайший тик.
- Origin графа: forum-топик `-1004300127777` с непустым `thread_id` (не `:7`, не `11112`).

## Запреты смоука

- **Не** смоукить на `tg-topic-duplicate`, `pfs-task-*`, `mofs`.
- **Не** restart gateway, **не** «поднимай» сторожем, **не** править `jobs.json`.
- **Не** unfold/repair чужих живых графов.

## Шаги и ожидания

| # | Шаг | Действие | Ожидание | AC |
|---|---|---|---|---|
| 1 | Подготовка | Оркестратор создаёт укороченный поезд смоука (CHANGE или учебный хвост до `GATE:done`) под slug `_smoke-train-done-gate` | Граф изолирован от боевых слагов | AC-D08 (косвенно) |
| 2 | **S-гейт** | Показ AC на `GATE:take-into-work` **без** тегов `depends: operator:<verb>` | `GATE:take-into-work` **auto** (`auto-pass: ac-shown`); поезд едет дальше без hold Саши | AC-D07 / регресс v0.4.0 |
| 3 | **O-AC фикстура** | В master-ТЗ/пакете смоука один AC с `depends: operator:поднимай`; на корне `operator-holds:` open; **без** `operator-done` + `evidence` | Довести до попытки `GATE:done`: preflight **exit 1**; `GATE:done` **blocked** `review-required: operator-action: поднимай`; complete корня запрещён | AC-D02 |
| 3b | Nudge сторожа | `~/.hermes/scripts/kanban_stuck_monitor.py --db … --dry-run` (или ждать ≤5m) | В плане/stdout: send в **origin** (slug, verb, AC, одна фраза для Саши); **не** `:7`, **не** DM; без hermes-мутаций в dry-run | AC-D05 |
| 4 | Снятие O-hold | После фиктивного «действия» оркестратор пишет `operator-done: поднимай` + `evidence:` (ISO + цитата) на корень или `GATE:done` | Preflight может пройти при прочем PASS; `GATE:done` auto после exit 0 | AC-D02 |
| 5 | **Q-n** | На корне `open-questions: Q-1: … status=open` | `pipeline_gate_done_preflight.py --mode done` → **exit 1** (`висящий вопрос Q-1`) | AC-D04 |
| 5b | Закрытие Q | `status=closed` + цитата ответа на корне | Preflight **может** exit 0 (если holds сняты и остальной чеклист PASS) | AC-D04 |
| 6 | **Archive** | `hermes kanban archive` (или канон archive) всех карточек смоука | Смоук-граф в `archived`; `hermes kanban list` не показывает мусор; боевые `tg-topic-duplicate` / `pfs` / `mofs` **не изменены** | AC-D08 |

## Критерий PASS IAC-11

- Шаги 2–5b выполнены с ожиданиями из таблицы.
- Нет побочных правок вне slug смоука.
- Результаты фиксируются оркестратором в `TZ/DevKanbanPipeline/appendix_done-gate_smoke_YYYYMMDD.md` (вне scope `HF:docs-handoff` архитектора).

## Справка: что смоук **не** покрывает

- П.7 ретро-hold на `t_07c4913c` / duplicate — отдельно оркестратором после W1.
- П.8 §29 PFS — граф `pfs-task-slug-not-created`.
- Правило 8 broken-tail на реальном `pfs-task-human-slug` — только учебная фикстура или отдельный repair-slug, не боевой pfs.
