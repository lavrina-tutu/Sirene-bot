# Telegram Notifications: Codebase Details

## Problem Statement
User receives many intermediate status messages in Telegram (e.g., "Loading skills...", "Testing...", "Running...") with push notifications, creating noise. Goal: deliver these messages silently (visible in chat history, but no sound/vibration).

## Root Cause Analysis

**Telegram Bot API** supports per-message notification control via the `disable_notification` parameter:
```python
await bot.send_message(
    chat_id=chat_id,
    text="Loading skills...",
    disable_notification=True  # ← silent delivery
)
```

Hermes gateway implements this via a **notification mode system** that determines whether to pass `disable_notification=True` on each message send.

## Code Flow

### 1. Mode Loading (`gateway/run.py` lines 5917–5938)

When `TelegramAdapter` is created:

```python
# Line 5920-5937
_notify_mode = os.getenv("HERMES_TELEGRAM_NOTIFICATIONS", "")
if not _notify_mode:
    try:
        _gw_cfg = _load_gateway_config()
        _raw = cfg_get(_gw_cfg, "display", "platforms", "telegram", "notifications")
        if _raw not in {None, ""}:
            _notify_mode = str(_raw).strip().lower()
    except Exception:
        pass
_notify_mode = _notify_mode or "important"
if _notify_mode not in {"all", "important"}:
    logger.warning(
        "Unknown telegram notifications mode '%s', defaulting to 'important'",
        _notify_mode,
    )
    _notify_mode = "important"
adapter._notifications_mode = _notify_mode  # Store on adapter instance
```

**Priority (highest to lowest):**
1. `HERMES_TELEGRAM_NOTIFICATIONS` env var
2. `display.platforms.telegram.notifications` in config.yaml
3. Default: `"important"`

**Valid modes:**
- `important` — interim messages silent, only important ones notify
- `all` — all messages trigger notifications

### 2. Message Filtering (`gateway/run.py` lines 225–238)

Agent emits status via `status_callback()` → gateway's `_status_callback_sync()` calls `_prepare_gateway_status_message()`:

```python
def _prepare_gateway_status_message(platform: Any, event_type: str, message: str) -> Optional[str]:
    """Filter/sanitize agent status callbacks before platform delivery."""
    text = str(message or "").strip()
    if not text:
        return None
    if _gateway_platform_value(platform) != "telegram":
        return text
    
    text = _redact_gateway_user_facing_secrets(text)
    if _TELEGRAM_NOISY_STATUS_RE.search(text):
        return None  # Drop auxiliary messages entirely
    if _looks_like_gateway_provider_error(text):
        return _gateway_provider_error_reply(text)  # Rewrite errors to user-safe text
    return text
```

**This filters out:**
- Noisy/transient status (compression failures, rate limit retries, etc.)
- Raw provider errors (replaced with "⚠️ Provider failed...")
- Secrets (API keys in error messages)

**Messages that pass through** are sent to `_status_adapter.send()` with metadata.

### 3. Notification Kwargs (`gateway/platforms/telegram.py` lines 472–485)

When sending, adapter checks the mode:

```python
class TelegramAdapter(BasePlatformAdapter):
    def __init__(self, config):
        # ... other init ...
        self._notifications_mode: str = "important"  # Default
    
    def _notification_kwargs(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Return disable_notification kwargs when in 'important' mode."""
        if getattr(self, "_notifications_mode", "important") != "important":
            return {}  # Mode is "all" → notify
        if (metadata or {}).get("notify"):
            return {}  # Explicit notify request → notify
        return {"disable_notification": True}  # Interim message → silent
```

**Logic:**
- If mode is NOT "important" (i.e., "all"), return `{}` (no disable_notification flag)
- If metadata explicitly sets `notify=True`, return `{}` (important message)
- Otherwise, return `{"disable_notification": True}` (silent)

This is applied to **every send**:

```python
# Line 1761, 1775, 2145, etc.
msg = await self._bot.send_message(
    chat_id=int(chat_id),
    text=chunk,
    parse_mode=ParseMode.MARKDOWN_V2,
    **thread_kwargs,
    **self._link_preview_kwargs(),
    **self._notification_kwargs(metadata),  # ← HERE
)
```

---

## Message Types & Metadata

**Interim/tool progress messages** (sent by `_status_callback_sync()`):
- Metadata has no `notify` key or `notify=False`
- Mode "important" → silent (`disable_notification=True`)
- Mode "all" → notify (`{}`)

**Important messages** (final response, approvals, slash confirmations):
- Metadata includes `notify=True`
- Both modes → notify (no disable_notification flag)

**Example:** Tool progress event:

```python
# In _status_callback_sync (gateway/run.py line 16065-16070)
_fut = safe_schedule_threadsafe(
    _status_adapter.send(
        _status_chat_id,
        prepared_message,  # e.g., "Tool: running search..."
        metadata=_status_thread_metadata,  # no "notify" key
    ),
    ...
)
```

Later, when actually sending:

```python
# adapter.send() calls _notification_kwargs(metadata)
# metadata has no "notify" key
# If mode == "important", _notification_kwargs returns {disable_notification: True}
# Message sent with disable_notification=True → silent delivery
```

---

## Noisy Messages: Filtered Entirely

Some messages never reach `send()` — they're dropped by `_prepare_gateway_status_message()` after matching `_TELEGRAM_NOISY_STATUS_RE`:

```python
# gateway/run.py lines 69–85
_TELEGRAM_NOISY_STATUS_RE = re.compile(
    r"("
    r"auxiliary\s+.+\s+failed"
    r"|compression\s+summary\s+failed"
    r"|fallback\s+context\s+marker"
    r"|configured\s+compression\s+model\s+.+\s+failed"
    r"|no\s+auxiliary\s+llm\s+provider\s+configured"
    r"|auto-lowered\s+compression\s+threshold"
    r"|preflight\s+compression"
    r"|rate\s+limited\.\s+waiting\s+\d"
    r"|retrying\s+in\s+\d"
    r"|max\s+retries\s+\(\d+\).*(?:trying\s+fallback|exhausted|invalid\s+responses)"
    r"|stream\s+(?:drop|drop\s+mid\s+tool-call).+retry\s+\d"
    r"|stale\s+connections\s+from\s+a\s+previous\s+provider\s+issue"
    r")",
    re.IGNORECASE | re.DOTALL,
)
```

**Matched → dropped entirely** (logged, not sent):
- "Compression summary failed"
- "Rate limited. waiting 10 seconds"
- "Stream drop mid tool-call... retry 1"

**Not matched → pass to `send()` with notification control:**
- "Loading skills..."
- "Testing model..."
- "Running agent..."

---

## Error Rewriting

Provider errors are sanitized to user-friendly text:

```python
def _gateway_provider_error_reply(text: str) -> str:
    """Map raw provider/API errors to short user-safe Telegram reply."""
    if _GATEWAY_AUTH_ERROR_RE.search(text):
        return "⚠️ Provider authentication failed. Check credentials..."
    if _GATEWAY_PROVIDER_POLICY_RE.search(text):
        return "⚠️ The model provider rejected the request. I kept raw details in logs..."
    if _GATEWAY_RATE_LIMIT_RE.search(text):
        return "⏱️ The model provider is rate-limiting. Please wait and try again."
    return "⚠️ The model provider failed. Raw details are in logs..."
```

Raw error like:
```
HTTP 401 Unauthorized: Invalid API key for model 'gpt-4o' at provider 'openai'
```

Becomes:
```
⚠️ Provider authentication failed. Check the configured credentials; raw provider details are in the gateway logs.
```

---

## Testing & Verification

### 1. Check Current Mode
```bash
# Read from config
hermes config show | grep -A 3 'display:' | grep -A 3 'platforms:'

# Or check logs
grep "telegram notifications mode" ~/.hermes/logs/gateway.log
```

### 2. Set via Config (Persistent)
```yaml
# ~/.hermes/config.yaml
display:
  platforms:
    telegram:
      notifications: important
```

Then: `hermes gateway restart`

### 3. Test via Env Var (One-Time)
```bash
export HERMES_TELEGRAM_NOTIFICATIONS=important
hermes gateway run
```

Check logs:
```bash
tail -20 ~/.hermes/logs/gateway.log | grep -i "notifications"
```

### 4. Verify in Telegram
- Send a message to bot
- Agent starts working (skill loading, testing, etc.)
- Intermediate messages should appear in chat history
- Should NOT trigger phone notifications (no sound/vibration)
- Final response SHOULD trigger notification (if marked important)

---

## Known Limitations

1. **Client-side override** — `disable_notification=True` is a server hint; user's phone settings (Do Not Disturb, mute notifications) take precedence. Flag suppresses Telegram's server-side notification, but phone's local settings still apply.

2. **No per-message importance marking** — All interim messages are treated equally. Future: could split into "verbose" (very noisy) vs "important interim" (tool started, tool finished).

3. **No batching** — Each interim message is a separate `send_message()` call. Discord/Slack would benefit from grouping related messages. Future: adapter could queue and batch.

4. **Config scope** — Mode is global to all chats using Telegram. Future: could add per-chat override (user mutes specific bot, etc.).

---

## References

- **File:** `gateway/platforms/telegram.py` (line 470 init, 472 method)
- **File:** `gateway/run.py` (line 225 filter, 5917 mode load, 16049 callback)
- **Telegram Bot API:** https://core.telegram.org/bots/api#sendmessage — `disable_notification` parameter
- **Related issue:** User receives many notifications during agent thinking/tool execution
