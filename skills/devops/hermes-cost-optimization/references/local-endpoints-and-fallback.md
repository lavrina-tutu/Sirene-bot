> Historical source, 2026; preserved as recorded, not current instructions. Verify against the current entrypoint and implementation.

### Hermes Profiles для маршрутизации по моделям

Правильный способ «разные модели для разных задач» — профили, не per-task параметры:

```bash
# Профиль для быстрых задач на Qwen (корп. сервер)
hermes profile create qwen-fast --clone --description "Простые задачи на Qwen"
hermes -p qwen-fast config set model.default "mlx-community/Qwen3.6-35B-A3B-8bit"
hermes -p qwen-fast config set model.provider custom
hermes -p qwen-fast config set model.base_url "http://10.8.4.100:52415/v1"
hermes -p qwen-fast config set model.api_key "dummy"    # обязателен даже для local
hermes -p qwen-fast config set delegation.reasoning_effort ""   # exo не поддерживает
hermes -p qwen-fast config set agent.reasoning_effort ""

# Fallback профиль на Haiku
hermes profile create haiku-fallback --clone
hermes -p haiku-fallback config set model.default "claude-haiku-4-5"
hermes -p haiku-fallback config set model.provider anthropic
hermes -p haiku-fallback config set delegation.base_url ""
```

Использование из основной сессии:
```python
terminal(command='hermes -p qwen-fast chat -q "простая задача"', timeout=120)
```

## 4. Connect a Local / Corporate LLM Endpoint

If a local or corporate OpenAI-compatible endpoint is available (e.g. **exo cluster**, LM Studio, Ollama):

### As delegation model (recommended — keeps main chat on cloud model):
```bash
hermes config set delegation.model <model-name>
hermes config set delegation.base_url http://<host>:<port>/v1
hermes config set delegation.api_key <signing-key-or-empty>
hermes config set delegation.provider custom
```

### As main model:
```bash
hermes config set model.base_url http://<host>:<port>/v1
hermes config set model.api_key <signing-key>
hermes config set model.default <model-name>
hermes config set model.provider custom
```

### exo cluster specifics
**exo** (distributed local inference) exposes three endpoints:
- OpenAI-compatible: `http://<host>:<port>/v1`
- Claude-compatible: `http://<host>:<port>`
- Ollama-compatible: `http://<host>:<port>/ollama`

The **signing key** shown in exo's `/#/integrations` page is the model name (e.g. `mlx-community/Qwen1.6-35B-A3B-8bit`). Use the OpenAI-compatible URL for Hermes.

---

## 5. VPN-Gated Corporate LLM — Fallback Pattern

When a corporate LLM is only reachable over VPN, there is no built-in per-delegation fallback. Options:

**Option A — Manual switch scripts (simplest):**
```bash
# VPN on — use corporate LLM
hermes config set delegation.model mlx-community/Qwen3.6-35B-A3B-8bit
hermes config set delegation.base_url http://10.8.4.100:52415/v1
hermes config set delegation.api_key mlx-community/Qwen1.6-35B-A3B-8bit
hermes config set delegation.provider custom

# VPN off — fall back to Haiku
hermes config set delegation.model claude-haiku-4-5
hermes config set delegation.provider anthropic
hermes config set delegation.base_url ''
hermes config set delegation.api_key ''
```

**Option B — Cron auto-switch (automatic):**
Create a cron job every 5 minutes that pings `http://10.8.4.100:52415` and switches delegation config based on reachability.

**Option C — `fallback_model` chain (for main model only):**
`fallback_model` in config.yaml applies to the main model, not delegation. Use it if running corporate LLM as the primary:
```yaml
fallback_model:
  - provider: custom
    model: mlx-community/Qwen3.6-35B-A3B-8bit
    base_url: http://10.8.4.100:52415/v1
    api_key: mlx-community/Qwen1.6-35B-A3B-8bit
  - provider: anthropic
    model: claude-haiku-4-5
```

---

