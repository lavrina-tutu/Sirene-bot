# Канон имён, ролей и G6

Это рабочее зеркало имён из `/home/tkachenkoav/WorkVault/Hermes-Backlog/TZ/GLOSSARY.md`. Норма процесса — Б55 master-ТЗ DevWorkflow и `../SKILL.md`; при расхождении побеждает master. Модели, backend и fallback определяются YAML `tools.dev_workflow`, а не этой страницей.

## Десять кейсов

| Кейс | Когда |
|---|---|
| `DEV` | новый инструмент или крупная фича |
| `CHANGE` | доработка существующего, полный цикл ТЗ |
| `CHANGE-LIGHT` | суженный CHANGE после установленного объёма |
| `BUGFIX` | баг с `BUG:diagnose` |
| `BUGFIX-LIGHT` | суженный BUGFIX после `GATE:diagnose-review` |
| `RESEARCH` | анализ без кода |
| `MIGRATION` | миграция инфраструктуры |
| `DECOMM` | снятие инструмента |
| `SKILL-DEV` | новый скилл |
| `SKILL-CHANGE` | правка или удаление скилла |

Новый тип работы требует строки в каноне и согласования Саши. Кейс выбирается по `cases-guide.md`; архитектор не меняет кейс и не сокращает рецепт.

## Роли

| Роль | Ответственность |
|---|---|
| Оркестратор | факты, FIFO, state, штатный вызов ролей и auto-gate; не решает содержание |
| Архитектор | ТЗ, план/IAC, диагноз, риски и вопросы к Саше; не пишет финальный боевой код |
| Ревизор | независимый вердикт `APPROVE`/`REQUEST-CHANGES`; не ведёт процесс |
| Исполнитель | код и тесты по согласованному плану; крупное отклонение возвращает архитектору |
| Компрессор | выжимка-индекс, не источник смысла |
| Координатор | backup, инвентарь и адресное применение согласованных системных replacement |

Один `invoke-role` = одна роль. Роль запускается только через `emit-prompt` → `invoke-role`; конкретная модель — YAML.

## Префиксы фаз

`BRF:`, `GATE:`, `TZ:`, `HF:`, `REV:`, `BUG:`, `RS:`, `MIG:`, `DEC:`, `SK:`, `ORCH:` — только в канонической форме с двоеточием. Рецепт берётся из `Registries/pipeline/pipeline_recipe.py`; нет строки в рецепте — не изобретать фазу.

## Гейты и operator-словарь

Auto-гейты требуют их evidence, но не сообщения Саши: `GATE:take-into-work`, `GATE:plan-approve`, `GATE:diagnose-review`, `GATE:done`. `GATE:done` дополнительно требует доставленный AC-отчёт. Never-auto: `GATE:go`, `GATE:block-accept`.

Закрытый operator-словарь: `поднимай` · `ставь кроны` · `удаляй` · `answer:Q-n` · `rollback-to-kanban`. Новое слово — только через изменение master-ТЗ.

## Guard-ы G1–G6

| Guard | Смысл |
|---|---|
| G1 | рецепт, версия/mtime ТЗ и extract согласованы с диском |
| G2 | перед complete TZ/HF/BUG/REV есть `context-used:` |
| G3 | перед `HF:test`/`GATE:done` свой impl write-set доказан git-proof |
| G4 | рецепт полного кейса существует |
| G5 | обязательные фазы не пропущены и кейс не подменён |
| G6 | роль, имя фазы и канонные артефакты совпадают |

### G6 — фаза → роль

| Фазы | Роль / владелец |
|---|---|
| `TZ:patch`, `TZ:finalize`, `HF:plan`, `BUG:diagnose`, `RS:collect`, `RS:analyze`, `MIG:plan`, `MIG:block-k`, `DEC:inventory`, `IDEA:analyze` | `architect` |
| `REV:tz`, `REV:plan`, `REV:report` | `reviewer` |
| `HF:impl`, `HF:test`, `DEC:exec` | `executor` |
| `TZ:compress`, `HF:compress` | `compressor` |
| `TZ:stabilize`, `SK:preflight`, `HF:backup`, `HF:docs-handoff`, `ORCH:shared-state`, гейты | оркестратор |

Несовпадение — G6 fail. `HF:impl` и `HF:test` всегда разные фазы и отдельные вызовы. Живой wrapper запрещает `next`, `complete-phase`, `recover` и второй invoke; notify не доказывает его завершение.
