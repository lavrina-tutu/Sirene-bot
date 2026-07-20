# Pitfall 62: send_path_degraded race при старте gateway (17.07.2026)

## Симптом

После рестарта gateway уведомление "♻️ Gateway online" не приходит. В `gateway.log`:
```
WARNING gateway.run: Home-channel startup notification failed for telegram:400307920: send_path_degraded
```

## Root cause

Upstream коммит `b8295cf6f7` (13.07.2026, "gate polling health on getUpdates progress"):
`TelegramAdapter._send_path_degraded=True` выставляется в `_begin_polling_generation()` при каждом старте новой polling-генерации и снимается только в `_record_polling_progress()` после первого успешного `getUpdates`.

Стартовые уведомления (`_send_home_channel_startup_notifications`) вызываются сразу после `[Telegram] Connected` — попадают в window до первого `getUpdates`. `adapter.send()` → `SendResult(success=False, error="send_path_degraded", retryable=True)`. Вызывающий код игнорировал `retryable=True` и только логировал WARNING.

## Фикс

`_send_with_polling_settle()` добавлен в `gateway/run.py`: при `retryable=True` ждёт `adapter._polling_progress_event` (timeout 15s), потом повторяет send один раз.

Затронуты оба пути: `_send_home_channel_startup_notifications` и `_send_restart_notification`.

## Статус

- Cherry-pick: `97202b86fa` на ветку `_test-cutover` (боевая ветка).
- Тесты: `tests/gateway/test_telegram_startup_notification_retry.py`, 9/9 green.
- PR: ветка `fix/startup-notification-send-path-degraded-race` в форке `ialextkachenko-byte/hermes-agent`. Нужен GitHub PAT для создания PR через `gh`.
