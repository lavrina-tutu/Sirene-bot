# Configuration history

> History (May 2026), not a current instruction. Claims about routing and required frontmatter conflict; check current code. Compression model, delegation and session_search are separate settings.

**`auxiliary.compression.model` (изменено 27.05.2026):** установлен `claude-sonnet-4-6` вместо `claude-haiku-4-5`. Haiku имеет контекст 200K, что меньше порога сжатия 500K для Sonnet/Opus (1M контекст). При несоответствии Hermes авто-понижает порог и выводит предупреждение каждую сессию. Решение: либо снизить `compression.threshold` до 0.17 (порог 170K), либо поставить Sonnet как compression model (текущее решение — Sonnet, threshold 0.5 корректен).

**Routing rules (добавлено 27.05.2026):** в `config.yaml` добавлена секция `routing` для маршрутизации коротких/социальных сообщений на Haiku. Haiku по-прежнему доступен для явного делегирования через `delegate_task`/`cronjob`.

## Config Options: What Does and Doesn't Exist

**Verified as of May 2026 — always grep before assuming a config key works:**

```bash
grep -rn "runtime_header" hermes-agent/ --include="*.py"  # → 0 results
```

**`routing:` секция в config.yaml — НЕ РАБОТАЕТ (проверено 27.05.2026).** Код Hermes её не читает — молча игнорируется при загрузке. Упоминается в AGENTS.md как `smart_model_routing` но нигде не реализована. Для реальной маршрутизации нужен плагин/хук или правила в MEMORY.md как рекомендации агенту. Не добавлять эту секцию ожидая что она сработает.

**`hermes skills list` не видит новый локальный скилл** — обязательные поля frontmatter: `name`, `description`, `version`, `author`, `tags`, `platforms`. Без `version` и `author` скилл есть на диске но не попадает в `.usage.json` индекс и не виден в списке. Setting it in config.yaml is silently ignored. The option was documented in memory/skills incorrectly.

**`display.runtime_footer` — EXISTS and works:**
```yaml
display:
  runtime_footer:
    enabled: true
    fields: [model, context_pct, cwd]  # renders: "claude-sonnet-4-6 · 35% · ~/proj"
```

**Rule:** Before writing config documentation or saving a "config option X works" memory entry, always verify with `grep -rn "option_name" hermes-agent/ --include="*.py"`. The config system does NOT warn on unknown keys — typos and non-existent options are silently ignored.

**Live toggle:** `/footer on|off` in-session toggles `runtime_footer` without restarting. Equivalent to flipping `display.runtime_footer.enabled` in config.yaml for the current session only.

---

### ⚠ Compression model context mismatch warning

**Symptom:** At session start: `"compression model claude-haiku-4-5 context is 200,000 tokens, but the main model claude-sonnet-4-6's compression threshold was 500,000 tokens. Auto-lowered this session's threshold to 200,000 tokens"`

**Root cause (verified May 2026, `run_agent.py::_check_compression_model_feasibility`):**
- `compression.threshold` (e.g. 0.5) × main model context (e.g. 1,000,000) = threshold_tokens (500,000)
- If `threshold_tokens > aux compression model context` → Hermes auto-lowers threshold to match compression model
- This fires every session startup — it's not a one-time warning

**The fix depends on your priorities:**

**Option A — Use Sonnet as compression model (recommended if you do long Opus sessions):**
```yaml
auxiliary:
  compression:
    provider: anthropic
    model: claude-sonnet-4-6   # 1M context — matches threshold 0.5 exactly
```
- Compression starts at ~500K tokens — Opus sessions don't lose detail
- Haiku remains available for explicit delegate_task calls (separate thing)
- Compression is more expensive but fires rarely

**Option B — Lower threshold to match Haiku:**
```yaml
compression:
  threshold: 0.17   # 1,000,000 × 0.17 = 170,000 < 200,000 Haiku limit
```
- Warning disappears, Haiku stays cheap
- Compression fires earlier (~170K tokens) — fine for most conversations

**Key internals:**
- `auxiliary.compression.model` and model used for `delegate_task` are **completely independent** — changing compression model does NOT affect Haiku availability for delegated tasks
- Per-model thresholds are NOT configurable via config.yaml — only one global `compression.threshold`
- `update_model()` in context_compressor carries `threshold_percent` across model switches — so after auto-lower, switching to Opus also gets the lowered threshold
- The only per-model override is hardcoded in `agent/auxiliary_client.py::_compression_threshold_for_model()` — requires source edit

---

