# Выбор кейса dev-поезда под точечную правку скилла

Режим работающего канбана (13.11): фазы-компрессоры `TZ:compress`/`HF:compress` сломаны и НЕ запускаются (system defect публикации extract). Это делает полные кейсы CHANGE/SKILL-CHANGE/DEV непригодными для точечной правки скилла: их рецепт содержит компрессор, а оркестраторские фазы (`SK:preflight`/`TZ:stabilize`) требуют отдельных `preflight --mode create` + `complete-phase` до ролей.

## Правило выбора

- Точечная правка скилла/ТЗ механикой invoke-role → кейс БЕЗ компрессорных фаз: `CHANGE-LIGHT`.
- Полный кейс (CHANGE/SKILL-CHANGE/DEV) — только когда компрессор снова заработает и поезду реально нужен полный цикл с компрессией master.

`CHANGE-LIGHT` рецепт: `TZ:patch → TZ:finalize → GATE:take-into-work → HF:impl → HF:test → HF:docs-handoff → GATE:done`.
Нет фазы REV и нет HF:plan/REV:plan. Уже созданный полный поезд переключается штатно:

```bash
pipeline set-case --slug <slug> --case CHANGE-LIGHT
```

Смена кейса меняет `recipe` в state. Проверить rc=0 + `case` в `read_state`. После смены первая ролевая фаза — сразу `TZ:patch` (architect): брать `next --slug` → `WORK`; не эмитить SK:preflight/TZ:stabilize (их больше нет в рецепте).

## Контракт под CHANGE-LIGHT

`write_scope` обязан покрывать И каталог поезда, И master-ТЗ (TZ:patch/TZ:finalize), И путь скилла (HF:impl/HF:test/HF:docs-handoff). Владельческое решение («публиковать как есть», новая директива по допуску) даётся архитектору ОТДЕЛЬНЫМ evidence-файлом `evidence/owner-directive-<дата>.md`, зарегистрированным в `inputs` контракта — не только текстом в чат.

Питфолл шага: `set-case` принимает ТОЛЬКО флаги `--slug SLUG --case CASE`; позиционные аргументы (`set-case <slug> <case>`) дают мгновенный rc=2 `usage error`.

## Дуги допуска как предмет правки

Когда публикация плана блокируется finding-ом категории schedule-affecting (напр. `unsupported_semantics`, row 8, exit 5) и `proposals` в operation show пуст — штатный `resume --accept-proposal` не сработает и флаг «игнорировать предупреждения» выдумывать нельзя (правило скилла). Правильное действие владельца «публиковать как есть всегда» — это ПЕРЕНОС блокера в `display_only` по владельческой директиве через механизм owner-decision (пример: milestone_interval_conflict → publish_collapsed для edit-plan-confluence). Это dev-правка скилла, а не resume: ведётся поездом CHANGE-LIGHT, после неё исходная операция резюмится как есть. Архив снимка при этом уже сохранён (`archive=verified`) и остаётся.
