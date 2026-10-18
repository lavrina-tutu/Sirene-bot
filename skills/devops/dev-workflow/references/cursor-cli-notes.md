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

JSON stdout парсится для `session_id` и диагностики. Фаталы провайдера — структурный классификатор (`is_error`/`type=="error"` в JSON, строгие сигнатуры: `Iteration budget exhausted`, `(90/90)`, `No API key`, `HTTP 5xx/429`, `request timed out`; rc ∈ {2,3}), полная таблица — в `invoke.md`. Голые `timeout`/`credits`/`billing` в тексте роли — **не** фатал; rc=0 с фатальным текстом — только если это валидный JSON с `is_error=true` или строгий паттерн.

## Workspace

Абсолютный каталог репозитория/дерева, где роль пишет файлы. Для ORCH — `Registries`; для скилла — `hermes-workspace/skills`. Не использовать `/tmp` как workspace для impl.
