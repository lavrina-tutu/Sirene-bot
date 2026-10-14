# Баннер dual-path (W2) для чужих скиллов

Исключение из «не трогать чужие SKILL.md»: **только** 10–15 строк **вверху** `hermes-feature/SKILL.md` и `tz-workflow/SKILL.md`. Тело процедуры, references, блоки 0–8 — не менять.

Ставит **ORCH / W2**, не локальный форк. Откат: `git checkout` двух файлов + `restore-all-skills.sh`.

## Смысл (человечески)

Пока включён переходный режим, для слагов из списка пилота новая машина ведёт задачу. Для остальных — старые скиллы и канбан. Два процесса на одном slug нельзя.

## Текст-эталон (согласовать с конфигом)

```markdown
# Dual-path (DevWorkflow W2)

Пока `tools.dev_workflow.orchestration.mode` ≠ `workflow-only`:
- не начинай новый поезд через канбан/hermes-feature/tz-workflow для slug ∈ `orchestration.pilot_slugs`;
- если slug в списке и нет живого kanban-running на нём — стоп, отдай управление скиллу `dev-workflow`;
- иначе работай по этому скиллу как раньше;
- два поезда на одном slug запрещены.

Конфиг: `EcosystemConfig.yaml` → `tools.dev_workflow.orchestration`.
```

## Конфиг на W2 (пример)

```yaml
orchestration:
  mode: dual-path
  pilot_slugs:
    - eco-config-w3
```

W1: `mode: kanban-primary`, `pilot_slugs: []` — баннер можно не ставить.

## Проверка

- Фикстура для pytest: `~/WorkVault/Registries/pipeline/tests/fixtures/dual_path_banner.md`
- AC-043 в мастер-ТЗ DevWorkflow v0.3.2

## Снятие баннера

- Откат всего dual-path → `rollback.md` (checkout SKILL.md).
- Снятие одного слага с пилота → баннер **остаётся**.
