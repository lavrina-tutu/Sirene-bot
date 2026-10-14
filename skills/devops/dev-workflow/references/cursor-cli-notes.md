# Справочник: бэкенд cursor-cli

Это **не** единственный способ вызвать роль — см. `invoke.md` (codex, hermes-internal). Скилл всегда идёт через `pipeline invoke-role`.

## Команда (внутри invoke_role)

```text
agent -p "<prompt>" -f --model <slug> --workspace <ABS> --output-format json
```

Опционально: `--resume <session_id>` из записи фазы в `_state.json`.

## Запрещено

- **`--continue`** — в пайплайне не использовать (путает сессии в каталоге).
- Прямой вызов `agent -p` из SKILL.md в обход `invoke-role`.
- Подмена модели карточки канбана (D1) slug Cursor — в DevWorkflow карточек нет, но правило сохраняется для dual-path.

## Модели по ролям (default контура)

| Роль | model |
|---|---|
| architect | cursor-grok-4.6-high (LIGHT допустим medium) |
| reviewer | claude-sonnet-5-medium |
| executor | composer-2.5 |

Переопределение — только через YAML `tools.dev_workflow.roles` или флаги invoke-role, не из текста промпта архитектора.

## Выход

JSON stdout парсится для `session_id` и диагностики. Фаталы (billing, 90/90, 5xx) — см. таблицу в `invoke.md`; rc=0 с фатальным текстом не считать успехом.

## Workspace

Абсолютный каталог репозитория/дерева, где роль пишет файлы. Для ORCH — `Registries`; для скилла — `hermes-workspace/skills`. Не использовать `/tmp` как workspace для impl.
