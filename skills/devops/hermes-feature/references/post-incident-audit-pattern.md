# Post-Incident Audit — паттерн (из инцидента 2026-06-24/25)

## Когда применять
После любого сбоя gateway (цикл рестартов, ModuleNotFoundError, сетевая нестабильность).

## Эпик в бэклоге
Создать секцию `## 🛡️ Эпик: Post-Incident Audit — [дата] ^epic-incident-audit` с задачами bk-NNN.

## 4 стандартных аудита (параллельно через Opus-кроны)

| Аудит | Что проверять |
|-------|--------------|
| Безопасность | `allowed_chats`, `guest_mode`, `require_mention`, логи `_should_process` |
| Логирование | уровень `[DBG]` строк, PII в логах, ротация по размеру и времени |
| Privacy mode | нужен ли `disabled`, риски, покрывает ли `allowed_chats` |
| Инцидент | root cause из `gateway-exit-diag.log`, git log, systemd статус |

## Ключевые находки 2026-06-25

### Логирование
- `[DBG]` строки в `plugins/platforms/telegram/adapter.py` были захардкожены на уровне `logger.info` — не фильтровались при `logging.level: INFO`
- Исправление: `logger.info("[Telegram][DBG]...")` → `logger.debug(...)`
- `inbound message: msg='текст'` в `gateway/run.py` — заменить на `msg_len=N`
- TTL-ротация: создать `~/.hermes/logrotate.conf` + crontab entry

### Startup notification
- Уведомление о старте шлётся ТОЛЬКО при `planned_restart_notification_pending` (planned /restart или SIGUSR1)
- При `systemctl restart` (SIGTERM) — молчит
- Исправление: убрать условие `if planned_restart_notification_pending` вокруг `_send_home_channel_startup_notifications`
- Доп. каналы: `TELEGRAM_ADDITIONAL_STARTUP_CHANNELS=-1004300127777:1` в `.env` + поддержка в `gateway/config.py` и `run.py`

### Root cause инцидента
- `ModuleNotFoundError: hermes_plugins` в кроне — **by design**, не баг (namespace плагины не импортируются вне процесса gateway)
- Цикл рестартов 04:43–05:10 — сетевая нестабильность Telegram API, systemd self-healing
- `SystemExit: 0` на `gateway/run.py:17878` — ожидаемое поведение при штатном выходе

### Безопасность
- `guest_mode: true` → закрыть (`guest_mode: false`) для персонального ассистента
- `require_mention: false` в группе — оставить если группа только для владельца
- `allowed_chats` фильтрует по chat_id, но не по user_id внутри чата

## Процедура безопасного обновления Hermes
1. `git -C ~/hermes-agent fetch origin`
2. Запустить `upstream_monitor.sh` — получить рекомендацию 🟢/🟡/🔴
3. При 🟢: `git -C ~/hermes-agent pull --ff-only`
4. `pip install -e ~/hermes-agent` в venv
5. Рестарт gateway через no_agent cron
6. Проверить лог на `startup notification` + отсутствие ошибок
