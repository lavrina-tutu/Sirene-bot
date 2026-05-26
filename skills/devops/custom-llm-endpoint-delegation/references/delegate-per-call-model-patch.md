# Per-call model в delegate_task — план патча

`delegate_task` намеренно не принимает `model` в схеме инструмента. Если пользователю реально нужна гибкость «Opus для одних подзадач, Sonnet для других в одном батче» — вот точные 4 точки в `tools/delegate_tool.py`, которые нужно тронуть. Используй ТОЛЬКО когда профили Hermes и `cronjob(model=...)` не покрывают кейс.

## Точки изменения

### 1. Схема — top-level `model`
В `DELEGATE_TASK_SCHEMA["parameters"]["properties"]` (около строки 2677) добавить:
```python
"model": {
    "type": "string",
    "description": "Optional per-call model override (e.g. 'claude-opus-4-7'). Falls back to delegation.model in config.yaml.",
},
```

### 2. Схема — per-task `model` в батче
Внутри `tasks.items.properties` (около строки 2710) добавить аналогичное поле — иначе батч не сможет дать каждой задаче свою модель.

### 3. Реестр (строки 2787–2796)
В `lambda args, **kw: delegate_task(...)` пробросить `model=args.get("model")`. Это потребует добавить `model: Optional[str] = None` в сигнатуру `delegate_task` (около строки 1900).

### 4. Per-task override в цикле
В цикле `for i, t in enumerate(task_list)` (около строки 2056) перед `_build_child_agent`:
```python
task_model = t.get("model") or model or creds["model"]
task_creds = creds
if task_model != creds["model"]:
    # Пересобрать creds через resolve_runtime_provider, иначе будет
    # рассинхрон provider↔model (например Opus с base_url MiniMax).
    from hermes_cli.runtime_provider import resolve_runtime_provider
    rt = resolve_runtime_provider(
        requested=creds.get("provider"),
        target_model=task_model,
    )
    task_creds = {**creds, "model": task_model, **rt}
```
Затем `model=task_creds["model"], override_provider=task_creds["provider"], ...`.

## Подводные камни

- **api_mode**. В `_build_child_agent:1031–1036` есть защита: «если provider отличается от родителя — `api_mode = None` чтобы пересчитать». Если ты в патче меняешь только model но не provider, api_mode не перевыбирается — может попасть запрос на старый endpoint. Чисто-Anthropic кейс (Opus↔Sonnet↔Haiku) безопасен, переключение через провайдеров (Anthropic↔MiniMax) — нет.
- **ACP transport**. Если родитель на ACP (Copilot), override credentials не работают (строки 1037–1058). Патч не помогает на ACP-родителе.
- **fallback_chain** наследуется (строка 1083). При override модели fallback может оказаться на «не той» провайдер-цепочке. Возможно надо чистить.
- **OpenRouter provider filters** (строки 1092–1104) — чистятся только при `override_provider`, но не при чистом override model. Если родитель ограничен `only=["Anthropic"]` а ты переключаешь на не-Anthropic модель — silent fallback на родительский провайдер.

## Когда НЕ делать этот патч

- Если задача — «все субагенты на Opus, родитель на Sonnet» — это уже работает через `delegation.model: claude-opus-4-7` в config.yaml. Никакого кода трогать не надо.
- Если задача — «одноразовый запуск тяжёлой модели» — `cronjob(action='create', schedule='+0s', repeat=1, model={'model':'claude-opus-4-7','provider':'anthropic'})` дешевле.
- Если задача — «маршрутизация по типу запроса» — лучше профили Hermes (см. основной SKILL.md).
