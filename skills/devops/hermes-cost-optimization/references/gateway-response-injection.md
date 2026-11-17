# Gateway response injection — как гарантированно дописать текст к каждому ответу

Класс задачи: «нужно, чтобы перед/после каждого ответа в Telegram появлялась строка X, и модель не может это пропустить». Типичные кейсы: индикатор активной модели, runtime metadata, политический баннер, watermark.

## Что НЕ работает

### system_prompt
Инструкция «выводи строку X в начале каждого ответа» в `agent.system_prompt`. **Sonnet/Haiku регулярно её пропускают** — особенно в длинных диалогах после компрессии или в коротких ответах. Это не гарантия, а просьба.

### Gateway hooks (`gateway/hooks.py`)
`HookRegistry.emit(event_type, context)` — fire-and-forget. В `agent:end` хуке:
- `gateway/hooks.py:174–181` — return value игнорируется. Нельзя «вернуть изменённый response».
- `gateway/run.py:8560–8563` — в context уходит `response[:500]` (обрезка для логирования), а не сам объект для мутации.
- `emit_collect` существует и собирает return values, но в `agent:end` не используется — придётся править gateway, что эквивалентно прямому патчу.

Вывод: хук может **наблюдать** ответ или отправить **отдельным сообщением**, но не дописать к существующему bubble.

### prefill_messages (Anthropic prefill)
Параметр есть в `AIAgent.__init__` (run_agent.py:393), инжектится в `agent/conversation_loop.py:808–812`. Но это **диалоговый prefill** (отдельные сообщения после system prompt), не «префикс ассистентского ответа в одном сообщении». Не подходит для нужного UX.

## Что работает — паттерн `runtime_footer`

В `gateway/runtime_footer.py` уже реализован канонический механизм добавления текста к финальному response. Используется в `gateway/run.py:8542–8557`:

```python
_footer_line = ""
try:
    from gateway.runtime_footer import build_footer_line as _bfl
    _footer_line = _bfl(
        user_config=_load_gateway_config(),
        platform_key=_platform_config_key(source.platform),
        model=agent_result.get("model"),
        context_tokens=agent_result.get("last_prompt_tokens", 0) or 0,
        context_length=agent_result.get("context_length") or None,
        cwd=os.environ.get("TERMINAL_CWD", ""),
    )
except Exception as _footer_err:
    logger.debug("runtime_footer build failed: %s", _footer_err)
    _footer_line = ""
if _footer_line and response and not agent_result.get("already_sent"):
    response = f"{response}\n\n{_footer_line}"
```

Это: (а) **гарантированно** срабатывает на финальный response; (б) умеет обходить уже отправленный стриминговый текст (`already_sent` guard); (в) per-platform config через `display.platforms.<platform>.runtime_footer`.

## Зеркальный header — план реализации

### Файл 1: `gateway/runtime_footer.py`
Добавить функцию рядом с `build_footer_line`:
```python
def build_header_line(*, user_config, platform_key, model):
    cfg = (user_config or {}).get("display") or {}
    hdr = cfg.get("runtime_header") or {}
    if platform_key:
        plat = (cfg.get("platforms") or {}).get(platform_key) or {}
        plat_hdr = plat.get("runtime_header")
        if isinstance(plat_hdr, dict):
            hdr = {**hdr, **plat_hdr}
    if not hdr.get("enabled"):
        return ""
    template = hdr.get("template") or "🤖 **Модель: {model}**"
    m = (model or "").rsplit("/", 1)[-1]
    if not m:
        return ""
    return template.format(model=m)
```

### Файл 2: `gateway/run.py`
Сразу после блока footer (после строки 8557) — параллельный блок:
```python
_header_line = ""
try:
    from gateway.runtime_footer import build_header_line as _bhl
    _header_line = _bhl(
        user_config=_load_gateway_config(),
        platform_key=_platform_config_key(source.platform),
        model=agent_result.get("model"),
    )
except Exception as _hdr_err:
    logger.debug("runtime_header build failed: %s", _hdr_err)
if _header_line and response and not agent_result.get("already_sent"):
    response = f"{_header_line}\n\n{response}"
```

### Файл 3: `~/.hermes/config.yaml`
```yaml
display:
  runtime_header:
    enabled: true
    template: "🤖 **Модель: {model}**"
  platforms:
    telegram:
      runtime_header:
        enabled: true   # включить только для Telegram
```

После применения **удалить** соответствующую инструкцию из `agent.system_prompt` — она больше не нужна, экономит токены и убирает источник несогласованности.

## Подводные камни

- **Стриминг**: при `already_sent: true` блок не сработает (текст уже ушёл по чанкам). Для стриминговых платформ нужен аналог `send_trailing_footer()` для шапки — отдельным сообщением. Обычно header важнее footer для UX, так что лучше отключать стриминг там, где включён header.
- **`agent_result.get("model")`** возвращает то, на чём агент реально завершил ход (после возможного fallback), а не то, на чём начинал. Это правильное поведение для индикатора, но может удивить если был тихий fallback.
- **Не применяется к tool-progress сообщениям** — только к финальному `response`. Это то что нужно, не баг.
- **Slash-команды** обрабатываются в gateway до агента и могут идти отдельным путём — header может не сработать на ответах слэш-команд (`/help` и т.п.). Проверять в каждом конкретном кейсе.

## Альтернатива без патча кода — отдельный bubble

Если код gateway трогать нельзя — `~/.hermes/hooks/model_header/handler.py` с подпиской на `agent:start`, читающий модель из `~/.hermes/config.yaml` или session state и отправляющий «🤖 Модель: X» через адаптер до того, как агент начнёт. Минусы: отдельное сообщение (не одно bubble), `agent:start` не знает финальную модель если будет fallback, нужно вручную писать платформенный send.



## Historical entrypoint notes

> Historical source, 2026; preserved as recorded, not current instructions. Verify against the current entrypoint and implementation.

### Indicator активной модели (Telegram)

Показ активной модели решён штатно через `display.runtime_footer` в config.yaml (см. Способ B ниже) — гейтвей дописывает модель + % контекста автоматически на каждый ответ. Не изобретать текстовые префиксы вида `🤖 Модель: ...` внутри ответа — это дублирует runtime_footer.

**Способ A (устарел, ненадёжный):** `agent.system_prompt` — модели Sonnet/Haiku регулярно пропускали инструкцию, к тому же создавало задвоение с runtime_footer.
**Способ B (актуальный, гарантированный):** `runtime_footer` (штатная функция, `display.runtime_footer.enabled: true`, `fields: [model, context_pct]`) — рисуется гейтвеем автоматически, модель в этом процессе не участвует. Детали в `references/gateway-response-injection.md`.

## 7. Постоянные инструкции в системный промпт

Для добавления дополнительных инструкций к каждой сессии используй `agent.system_prompt`:

```bash
hermes config set agent.system_prompt 'Инструкция на русском языке'
```

- Загружается через `_load_ephemeral_system_prompt()` при каждом запуске агента
- Приоритет ниже env-переменной `HERMES_EPHEMERAL_SYSTEM_PROMPT` (если задана — перекрывает)
- Требует перезапуска сессии (`/reset` или `hermes gateway restart`) — читается при инициализации
- Альтернатива `agent.personalities` (словарь персон, нужно активировать явно через `/personality`) — `agent.system_prompt` проще и работает всегда

**Пример — не для индикации модели.** Раньше здесь была рекомендация класть в `agent.system_prompt` инструкцию вида «указывай модель в начале каждого ответа» — **это неверно и устарело**. Показ модели/контекста — штатная функция гейтвея через `display.runtime_footer` (`config.yaml`), рисуется автоматически, без участия модели. НЕ дублировать вручную текстом в ответе — будет задвоение. Используй `agent.system_prompt` только для правил, которые модель должна реально *учитывать при рассуждении* (делегирование, маршрутизация задач по сложности) — не для вывода метаданных, которые гейтвей и так добавляет сам.

---
