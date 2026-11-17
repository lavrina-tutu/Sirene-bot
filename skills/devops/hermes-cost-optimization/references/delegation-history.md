> Historical source, 2026; preserved as recorded, not current instructions. Verify against the current entrypoint and implementation.

## Code observation, 2026-11-17

In `<HERMES_REPO>/tools/delegate_tool.py`, the base task schema has no model field; `delegate_tool_routes.py::schema_extension` permits the active delegation backend to add per-task fields. Thus availability depends on that backend. `delegate_tool_config.py::_load_config` reads the delegation section via the read-only loader, with a legacy fallback. This source inspection does not establish which code or configuration a running process has loaded.

The same file's `_resolve_child_fallback_chain` documents that pinned children do not inherit the parent fallback chain; unpinned children can inherit it if `fallback_providers` is absent or null, while an explicit empty list disables it. The old unconditional fallback claim below is historical. Verify the deployed version and effective route.

### delegate_task model resolution (codebase reference)

`delegate_task` **не принимает per-task model/provider** (проверено: `tools/delegate_tool.py:2066` — `model=creds["model"]` всегда из delegation.model). Вся цепочка:
1. `delegate_tool.py:2459 _load_config()` — читает `delegation:` из `CLI_CONFIG`
2. `delegate_tool.py:2345 _resolve_delegation_credentials()` — if `delegation.base_url` → direct endpoint; else if `delegation.provider` → `resolve_runtime_provider`; else наследование от родителя.
3. `delegate_tool.py:875 _build_child_agent()` — подставляет `model=creds["model"]`
4. `delegate_tool.py:1021–1036` — `effective_model = model or parent_agent.model`. **api_mode НЕ наследуется когда provider отличается** (баг #20558): иначе MiniMax/DeepSeek роутятся не на ту API.
5. `delegate_tool.py:1050` — если задан `override_provider` без `override_acp_command`, ACP-транспорт принудительно сбрасывается.

**Cron — другая дверь:** `cronjob` принимает `model={"model":..., "provider":...}` напрямую (см. `cron/scheduler.py:1416–1556`). Результат доставляется отдельным сообщением, не в текущий контекст.

## 10. Gateway-безопасное делегирование тяжёлых задач (tkachenkoav, май 2026)

**Проблема:** `delegate_task` с Opus (`reasoning_effort=high`, `child_timeout=1200`) держит родительский stream. При длинных задачах gateway падает с "Stream stale for 180s — Killing connection" и перезапускается. Сессия рвётся.

**Решение — cronjob вместо delegate_task для тяжёлых Opus-задач:**

```python
# Вместо delegate_task (блокирует gateway):
cronjob(action='create',
    name='my-task',
    prompt='...',
    model={'model': 'claude-opus-4-7', 'provider': 'anthropic'},
    schedule='1m',      # запуск через 1 минуту
    repeat=1,           # один раз
    deliver='origin',   # результат в текущий чат
    enabled_toolsets=['file', 'terminal']
)
```

**Правила:**
- Задачи >5 мин (разработка, исследования, ТЗ, настройка Hermes) → **cronjob**
- Короткие задачи (<2 мин) → **delegate_task** на Sonnet/Haiku

**Минусы cronjob:**
- Нет контекста разговора — всё нужно писать в prompt явно
- Нет обратной связи в процессе — итерации дороже
- Задержка 1+ мин до старта
- Нельзя видеть прогресс (только через `cronjob action='log'` пока running)

**Паттерн промпта для cronjob-задачи:** передавай максимум контекста явно: пути к файлам, что уже сделано, что именно нужно сделать, что нельзя трогать. Иначе Opus начнёт с нуля. There is no native per-delegation fallback — use manual switch scripts or a cron job.
- Changes to `delegation.*` take effect immediately for new `delegate_task` calls — no `/reset` needed.
- Changes to `auxiliary.*` also take effect immediately.
- exo signing key = the model name string shown on the integrations page, NOT a token/secret.
- When `delegation.base_url` is set, also set `delegation.provider custom` — otherwise Hermes may route to the wrong backend.
- **`delegate_task` игнорирует `delegation.model` из config.yaml.** Подтверждено дважды в реальных сессиях: subagent запускается на `claude-opus-4-7` даже при `delegation.model: claude-haiku-4-5`. Наследование от родительской сессии тоже не работает (parent=sonnet → child=opus). **Единственный надёжный workaround:** явно передавать `model={"model": "claude-haiku-4-5", "provider": "anthropic"}` в параметре каждого вызова `delegate_task`. Без явного параметра — модель непредсказуема.
- `fallback_model` в config.yaml применяется только к **основной модели**, NOT к delegation.
- **`hermes config show` не отображает секцию `delegation`** — это UX-баг CLI. Параметры в config.yaml есть и работают, просто не показываются в выводе команды.
- **exo chat completions may return empty body** if the target model is not loaded in memory yet. First request to a cold model times out silently. Fix: send a warm-up request via the exo web UI (`http://<host>:<port>`) before using the endpoint programmatically.

