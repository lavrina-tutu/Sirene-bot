---
name: gateway-platform-configuration
description: Configure per-platform display and notification behavior in the Hermes gateway (Telegram, Discord, Slack, etc.). Manage interim messages, push notifications, streaming, and message delivery modes.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [gateway, configuration, messaging, platforms, display, notifications]
    related_skills: [hermes-agent]
---

# Gateway Platform Configuration

Hermes Gateway runs a unified agent across 15+ messaging platforms (Telegram, Discord, Slack, WhatsApp, Signal, Email, Matrix, etc.). Each platform has its own capabilities and constraints — some support threads, others don't; some batch edit notifications, others require per-message control.

This skill covers **platform-specific display and notification configuration** — how to customize interim message behavior, push notification modes, streaming, and message delivery per platform via `~/.hermes/config.yaml`.

**When to use this:** User wants to control whether intermediate agent status messages (tool progress, "Loading skills...", "Testing...") trigger push notifications, or configure platform-specific streaming/display behavior.

---

## Quick Answer: Telegram Interim Messages (No Push Notifications)

**Problem:** User receives many intermediate status messages in Telegram with push notifications.

**Solution:** Add to `config.yaml`:

```yaml
display:
  platforms:
    telegram:
      notifications: important  # silently deliver interim messages (no push)
```

**Or via env var (one-time test):**
```bash
export HERMES_TELEGRAM_NOTIFICATIONS=important
hermes gateway run
```

**Modes:**
- `important` (default when set) — tool progress, streaming, status messages sent with `disable_notification=True` (visible in chat, no sound/vibration). Only final responses and approvals trigger push notifications.
- `all` — legacy mode; all messages trigger push notifications.

---

## Config Structure: `display.platforms`

The `display` section in `config.yaml` has a `platforms` subsection for per-platform overrides:

```yaml
display:
  # ... global display settings ...
  platforms:
    telegram:
      notifications: important
      interim_messages: false    # (optional) hide interim status entirely
      streaming: true             # (optional) override global streaming
    discord:
      streaming: false            # disable streaming for Discord only
    slack:
      notifications: all          # override global setting per-platform
```

**Top-level display settings** (apply to all platforms unless overridden):
- `interim_assistant_messages` (bool, default true) — show assistant's thinking/planning as it works
- `tool_progress` (str, default "all") — how verbose tool output is ("off", "compact", "all")
- `streaming` (bool, default true) — stream responses as tokens arrive
- `show_reasoning` (bool, default false) — surface model reasoning blocks

**Per-platform overrides** (added under `display.platforms.<platform>`):
- `notifications` (str) — platform-specific notification mode ("important", "all")
- `interim_messages` (bool) — override interim assistant message visibility for this platform
- `streaming` (bool) — override streaming for this platform
- Any other platform-specific display setting

---

## How Interim Messages Work in Gateway

1. **Agent emits status events** → `status_callback()` called with event_type (e.g., "skill_loading", "tool_call_progress") and text message
2. **Gateway receives callback** → `_status_callback_sync()` in `gateway/run.py` (line 16049)
3. **Message filtering** → `_prepare_gateway_status_message()` (line 225) filters noisy/auxiliary messages and applies platform-specific rules
4. **Platform adapter sends** → Telegram adapter's `_notification_kwargs()` (line 472 in `gateway/platforms/telegram.py`) returns `disable_notification=True` if mode is "important"

**Key insight:** The `disable_notification` parameter is a Telegram Bot API flag that delivers the message silently (no push, no sound, no badge). Message still appears in chat history.

---

## Telegram: Detailed Behavior

**File locations in codebase:**
- Mode loading: `gateway/run.py` lines 5917–5938 (set up during TelegramAdapter creation)
- Mode application: `gateway/platforms/telegram.py` lines 472–485 (`_notification_kwargs()`)
- Message filtering: `gateway/run.py` lines 225–238 (`_prepare_gateway_status_message()`)

**Mode: `important` (recommended)**
```
Agent emits "Loading skills..." 
  ↓
Gateway prepares message
  ↓
_notification_kwargs() returns {disable_notification: True}
  ↓
send_message(..., disable_notification=True)
  ↓
Message appears in chat, but triggers NO push notification
```

**Mode: `all` (legacy)**
```
Same flow, but _notification_kwargs() returns {} (empty dict)
  ↓
send_message() sent without disable_notification flag
  ↓
Platform defaults trigger push notification (sound/vibration)
```

---

## Discord / Slack / Other Platforms

Currently, Telegram is the only platform with an explicit `notifications` mode because:
- Telegram's Bot API supports per-message `disable_notification` flag
- Discord/Slack do not have equivalent per-message silent delivery (they use webhooks/reactions)
- Other platforms (Signal, Matrix, Email) don't have push notifications

**Future work:** Discord could use thread-muting or reaction suppression instead of notifications toggle. Slack could use app-level notification settings.

For now:
- Discord, Slack, Signal, etc. ignore `display.platforms.<platform>.notifications`
- Use Discord's native settings → mute channels/threads
- Use Slack's native settings → Do Not Disturb, notification rules

---

## Filtering: What Messages Are Already Suppressed

Even in "all" mode, some messages are filtered entirely (never sent):

**Noisy/auxiliary messages** (regex in `gateway/run.py` lines 69–85):
- Compression summary failures
- Fallback context marker
- Rate limiting retries
- Stale connection notices
- Auto-lowered compression threshold

Example: "Compression summary failed" → dropped (logged only, not sent to Telegram).

**Provider errors** are rewritten to user-safe text (lines 149–166):
- Raw auth failure becomes → "⚠️ Provider authentication failed..."
- Safety policy rejection → "⚠️ The model provider rejected the request..."

This filtering happens **before** the notification mode is applied, so filtered messages never reach the platform at all.

---

## Interim Messages: Disable Entirely

If you want **zero** intermediate messages (only final response shown), set:

```yaml
display:
  interim_assistant_messages: false
  platforms:
    telegram:
      notifications: important
```

This disables the agent from emitting thinking/planning messages. You'll see only:
1. Your message
2. Final response

No tool calls, no "thinking...", no streaming.

---

## Streaming Configuration

By default, Telegram messages stream in as tokens arrive (if `display.streaming: true`).

**To disable streaming for Telegram only:**
```yaml
display:
  streaming: true           # global: stream for all platforms
  platforms:
    telegram:
      streaming: false      # except Telegram — send whole message at once
```

Streaming in Telegram means:
- Each token/chunk arrives as a separate message edit (visible as "..." becoming "Hello w", "Hello wo", "Hello wor", etc.)
- Can be jarring if the network is slow; reduces latency perception if fast
- Increases API calls (one per chunk)

---

## Environment Variable Overrides

For quick testing without editing `config.yaml`:

**Telegram notifications mode:**
```bash
export HERMES_TELEGRAM_NOTIFICATIONS=important
hermes gateway run
```

This env var is checked first; if unset, gateway falls back to config.yaml. Takes effect immediately on gateway startup.

**Reload at runtime:** Gateway must be restarted to pick up config changes. Send `/restart` in a managed gateway, or restart the service:
```bash
hermes gateway restart
```

---

## Troubleshooting

### "I still see lots of messages with notifications"
1. Verify config was saved: `hermes config show | grep -A 5 'platforms:'`
2. Restart gateway: `hermes gateway restart`
3. Check gateway logs for errors: `tail -50 ~/.hermes/logs/gateway.log`

### "Config changes don't take effect"
- Config is loaded once at gateway startup
- After editing, run `hermes gateway restart`
- Or test with env var first: `HERMES_TELEGRAM_NOTIFICATIONS=important hermes gateway run`

### "Messages still have sound even with `notifications: important`"
- Verify Telegram app settings: Settings → Notifications → Mute all sounds
- Or use Do Not Disturb mode
- The `disable_notification` flag is a server-side hint; client-side settings override it

### "I want ONLY final responses, nothing else"
```yaml
display:
  interim_assistant_messages: false   # Hide thinking/planning
  tool_progress: off                   # Hide tool calls
  platforms:
    telegram:
      notifications: important
```

---

## Автоматическая строка модели в каждом ответе (25 мая 2026)

**Проблема:** Инструкция в `agent.system_prompt` добавлять строку «🤖 Модель: X» ненадёжна — модель иногда пропускает её.

**Решение: `display.runtime_header`** — детерминированная UI-шапка, рендерится на уровне gateway, не зависит от модели:

```yaml
display:
  runtime_header:
    enabled: true
    template: "🤖 **Модель: {model}**"
```

- `{model}` подставляется автоматически (берётся из `agent_result["model"]`)
- Применяется к каждому финальному ответу перед отправкой в платформу
- Работает для обычных ответов и для результатов cronjob
- После включения — убрать дублирующую инструкцию из `agent.system_prompt` и memory

**⚠️ Дублирование:** если инструкция добавлять строку есть и в `runtime_header`, и в `system_prompt`, и в memory — строка появится несколько раз. Оставить ТОЛЬКО `runtime_header`, остальное удалить.

**Аналог:** `display.runtime_footer` работает так же, только в конце ответа. Формат: `model · 35% · ~/proj`.

See `references/cronjob-vs-delegate-task.md` for the full decision guide on when to use cronjob vs delegate_task for Opus tasks (gateway crash pattern, tradeoffs, code template).

See `references/gateway-telegram-notifications.md` for:
- Complete codebase walkthrough (lines cited)
- Noisy message regex patterns
- Error handling and rewriting logic
- Examples of mode changes in production

---

## delegate_task → Gateway Crash Pattern (25 мая 2026)

**Проблема:** `delegate_task` с тяжёлыми Opus-задачами (разработка, исследования, `reasoning_effort=high`, `child_timeout=1200`) блокирует родительский стрим. Логи показывают: `Subagent 0 appears stale (no progress for 15 heartbeat cycles)` → `Stream stale for 180s — Killing connection` → gateway падает, Telegram-сессия рвётся.

**Решение: cronjob для всех длинных задач.**

| Тип задачи | Инструмент | Почему |
|---|---|---|
| Разработка, исследования, ТЗ, настройка Hermes (>5 мин) | `cronjob(repeat=1, schedule='1m', model=opus)` | Изолирован, не блокирует gateway |
| Быстрые вопросы, уточнения (<2 мин) | `delegate_task` (Sonnet) | Короткий вывод, не нагружает стрим |
| Итеративные задачи с вопросами к пользователю | `delegate_task` с малым контекстом | Нужна обратная связь |

**Минусы cronjob:** нет контекста разговора (нужно писать полный prompt), нет обратной связи в процессе, задержка старта минимум 1 минута.

**Конфиг delegation (config.yaml):**
```yaml
delegation:
  model: claude-opus-4-7
  provider: anthropic
  reasoning_effort: high
  max_iterations: 50
  child_timeout_seconds: 1200
  max_concurrent_children: 3
```
Субагенты через `delegate_task` берут модель из этой секции — явно передавать `model=` в аргументах инструмента невозможно (поля нет в схеме).

## Pitfalls

1. **Forgetting to restart gateway** — config changes require `hermes gateway restart`, not just reloading the file.
2. **Mixing global and per-platform settings** — per-platform always wins; `display.platforms.telegram.notifications` overrides global `display.streaming` is independent of per-platform override.
3. **Expecting client-side behavior** — `disable_notification=True` is a Telegram server hint; user's phone settings (Do Not Disturb, sound muting) take precedence. The flag silences it server-side, but client can re-enable.
4. **Assuming other platforms support `notifications`** — only Telegram reads this setting. Discord, Slack, etc. ignore it; use platform-native settings instead.
6. **cronjob не видит контекст разговора** — при создании cronjob для Opus-задач нужно явно и полно описать контекст в prompt: пути к файлам, что уже сделано, что нельзя трогать. Субагент начинает с чистой сессии.
7. **Субагент (Haiku) может испортить данные** — без явного запрета в промпте субагент может изменить .env, удалить contacts.enc, подставить тестовые credentials. Всегда писать в prompt: "НЕ удалять X, НЕ изменять Y".
