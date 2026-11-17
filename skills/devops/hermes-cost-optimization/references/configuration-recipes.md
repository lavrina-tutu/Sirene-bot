> Historical source, 2026; preserved as recorded, not current instructions. Verify against the current entrypoint and implementation.

## 1. Delegation (Subagents) → Cheap Model

When Hermes spawns subagents via `delegate_task`, they use the `delegation.*` config:

```bash
hermes config set delegation.model claude-haiku-4-5
hermes config set delegation.provider anthropic
```

Savings: Haiku is ~20x cheaper than Sonnet. Subagents handle ~30-50% of tokens in complex sessions.

---

## 2. Auxiliary Tasks → Cheap Model

Context compression, session search, and vision analysis each have their own model slot.

**⚠️ Compression model ≠ session_search model** — у каждой задачи свой слот, выбирай осознанно.

**Важно для compression:** модель сжатия должна иметь контекст **не меньше** порога сжатия основной модели. Иначе при каждом старте сессии будет предупреждение «Auto-lowered this session's threshold». Два варианта:
- Использовать **Sonnet** как compression model (контекст 1M, порог 500K работает)
- Использовать **Haiku** (200K) + снизить `compression.threshold: 0.17` (170K < 200K)

**Текущая конфигурация для tkachenkoav (май 2026):** compression → Sonnet (claude-sonnet-4-6), session_search → Haiku

```bash
# Compression → Sonnet (дороже, но порог 500K корректен, Opus не теряет контекст)
hermes config set auxiliary.compression.model claude-sonnet-4-6
hermes config set auxiliary.compression.provider anthropic

# Session search → Haiku (дёшево, достаточно для поиска)
hermes config set auxiliary.session_search.model claude-haiku-4-5
hermes config set auxiliary.session_search.provider anthropic

# Vision → Haiku
hermes config set auxiliary.vision.model claude-haiku-4-5
hermes config set auxiliary.vision.provider anthropic
```

## Quick Bulk Apply (Recommended Baseline)

```bash
# Delegation → Haiku
hermes config set delegation.model claude-haiku-4-5
hermes config set delegation.provider anthropic

# Compression → Sonnet (важно: Haiku 200K не покрывает threshold 500K)
hermes config set auxiliary.compression.model claude-sonnet-4-6
hermes config set auxiliary.compression.provider anthropic

# Session search + Vision → Haiku
hermes config set auxiliary.session_search.model claude-haiku-4-5
hermes config set auxiliary.session_search.provider anthropic
hermes config set auxiliary.vision.model claude-haiku-4-5
hermes config set auxiliary.vision.provider anthropic

# Security
hermes config set security.redact_secrets true
```

⚠️ После настройки — проверить `auxiliary.session_search.base_url` и `auxiliary.session_search.api_key`: если там остались значения от старой конфигурации (например кастомный эндпоинт), очистить:
```bash
hermes config set auxiliary.session_search.base_url ""
hermes config set auxiliary.session_search.api_key ""
```

No restart needed — takes effect on the next session or tool invocation.

---

## Cron Auto-Switch Script

A ready-made script lives in `scripts/switch_delegation_model.py`. It:
- Pings the corporate endpoint (3s timeout)
- Switches delegation config only when state changes (idempotent)
- Stays silent when no change → cron `no_agent=true` won't spam notifications

Deploy:
```bash
# Script is already at ~/.hermes/scripts/switch_delegation_model.py
# Create cron job:
hermes cron create "every 5m" --name "Auto-switch delegation model"
# Then edit the job to set: script=switch_delegation_model.py, no_agent=true, deliver=local
```
Or via Hermes tool:
```python
cronjob(action="create", name="Auto-switch delegation model (exo/haiku)",
        schedule="every 5m", no_agent=True,
        script="switch_delegation_model.py", deliver="local")
```

Edit the constants at the top of the script to change host/port/models.

---

