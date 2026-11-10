---
name: tz-workflow
version: 2.13.0
description: "Содержание, хранение и inventory ТЗ Hermes/USERTOOLS"
---

# tz-workflow

Этот скилл хранит предметные правила ТЗ и inventory. Он не запускает автономный цикл, очередь, модели или роли: маршрут фаз, FIFO, `emit-prompt`/`invoke-role` и G6 принадлежат `devops/dev-workflow` и Б55 master-ТЗ DevWorkflow. Модели/backend — только YAML `tools.dev_workflow`.

## Правила ТЗ

1. Один инструмент — один master: `TZ/<Tool>/<Tool>_TZ.md`; версия находится во frontmatter, изменения добавляются секциями существующего master.
2. После изменения обновляется `MAIN_TZ_INVENTORY.md`. Новые имена файлов/каталогов латинские; приложения — `appendix_<тема>_<YYYYMMDD>.md` и отражены в master.
3. Содержательные нормы, AC, контракты и «не трогать» формулирует архитектор в канонном файле. Исполнитель/координатор выполняют только разрешённую механику.
4. Новая сущность отмечается **[NEW-ENTITY, требует согласования Саши]**; до согласования она не проектируется и не создаётся.
5. После `TZ:finalize` показ AC не является ожиданием: продолжение идёт по dev-workflow, а не по самостоятельному tail этого скилла.

Перед фазой читать GLOSSARY и `dev-workflow/references/context.md`. Точные фазы `TZ:stabilize`, `TZ:compress`, `TZ:patch`, `REV:tz`, `TZ:finalize` остаются каноническими именами, но их рецепт/владелец/запуск определяет dev-workflow.

Полезные проверки качества, contracts и inventory перечислены в references; они не заменяют процесс.
