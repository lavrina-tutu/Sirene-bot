# Какой кейс когда

Закрытый список — **ровно 10**. Выбор **Саша + оркестратор на старте**. Архитектор не меняет кейс и не укорачивает рецепт.

Мастер-ТЗ: DevWorkflow **Б6.1**, рецепты — `Registries/pipeline/pipeline_recipe.py`.

## Триггеры → кейс

| Саша говорит (смысл) | Кейс | Примечание |
|---|---|---|
| новый инструмент, новая USERTOOL, «с нуля» | **DEV** | полный TZ-WRITE без stabilize для нового файла |
| доработай, расширь, «как CHANGE» | **CHANGE** | полный цикл; эталон `cases/CHANGE.md` |
| маленькая правка, ≤3 файла, без новых сущностей | **CHANGE-LIGHT** | после оценки на `TZ:patch` → `set-case` |
| баг, не работает, ошибка | **BUGFIX** | сначала `BUG:diagnose` |
| баг мелкий, после диагноза ≤3 файла | **BUGFIX-LIGHT** | после `GATE:diagnose-review` |
| исследуй, проанализируй, без кода | **RESEARCH** | `RS:collect` → `RS:analyze` |
| миграция, переезд, волна W* | **MIGRATION** | план миграции + ORCH |
| сними, выключи, DECOMM | **DECOMM** | `GATE:go` ждёт «удаляй» |
| новый скилл Hermes | **SKILL-DEV** | как DEV, workspace skills, ORCH restore |
| правка / удаление скилла | **SKILL-CHANGE** | `SK:preflight` → CHANGE или DECOMM |

«В бэклог / идея» — не DEV-поезд: `RESEARCH` или IDEA-triage (`references/canon.md`, Б28 ТЗ).

## LIGHT — не отдельный «быстрый кейс с потолка»

- **CHANGE-LIGHT** — то же семейство CHANGE, укороченный рецепт после известного объёма.
- **BUGFIX-LIGHT** — после ревью диагноза (`GATE:diagnose-review`).

Оркестратор: `pipeline set-case --case …`. Уже завершённые фазы сохраняются.

## Dual-path (W2+)

Если слаг **не** в `orchestration.pilot_slugs` — старый маршрут (`hermes-feature` / канбан). Если в списке — только `dev-workflow` (`SKILL.md`).

## Куда читать дальше

| Кейс | Файл |
|---|---|
| CHANGE (полный) | `cases/CHANGE.md` |
| остальные | отличия от CHANGE в мастер-ТЗ Б19–Б27 (в скилле — кратко в canon + рецепт в Python) |

## Императивы Саши

- «ставь кроны» — только тогда кроны; DevWorkflow сам минутный dispatch не ставит.
- «делай» / «сделай» — содержательная работа в текущей фазе, не смена кейса.
