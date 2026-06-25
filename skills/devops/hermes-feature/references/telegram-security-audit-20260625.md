# Telegram Security Audit — 2026-06-25

Результаты Post-Incident Audit (эпик bk-103…106) после сбоя gateway 24-25.06.2026.

## Итоговая конфигурация (применено)

```yaml
telegram:
  allowed_chats: 400307920,-1004300127777  # личка Саши + группа
  guest_mode: false       # закрыто 25.06
  require_mention: false  # группа только для Саши — упоминание не нужно
  exclusive_bot_mentions: false
  reactions: false
```

Home channel: `TELEGRAM_HOME_CHANNEL=400307920` (личка, в .env)

## Топики «Сирень Workspace» (chat=-1004300127777)

| Топик | Thread ID |
|-------|-----------|
| General | 1 |
| Tools | 3 |
| Hermes DEV | 4 |
| WorkVault | 5 |
| Backlog | 6 |
| Monitoring | 7 |
| Personal | 8 |

Источник: `gateway.log`, поле `reply_to_id` в строке `Flushing text batch`.

## bk-103: Безопасность — ЗАКРЫТО ✅

- `allowed_chats` настроен корректно, блокировка работает (подтверждено логами)
- `guest_mode: false` применено
- Состав группы: только Саша + бот → `require_mention: false` безопасен
- Если в группу добавят других → переключить `require_mention: true` или `exclusive_bot_mentions: true`

## bk-104: Логирование — ПРИМЕНЕНО ✅

**Сделано:**
- 10 строк `logger.info("[Telegram][DBG]...")` → `logger.debug(...)` в `adapter.py`
- `inbound message: msg='текст'` → `msg_len=N` в `gateway/run.py`
- TTL-ротация: `~/.hermes/logrotate.conf` + cron `0 4 * * *`

**Открыто:**
- Флаг `telegram.debug` в config.yaml (переключение без правки кода) — не реализован

## bk-105: Privacy mode — ОСТАВИТЬ ✅

Privacy mode disabled оправдан: бот читает весь текст в топиках (не только команды).
Риск «бот в чужой группе» закрыт через `allowed_chats`.

## bk-106: Инцидент с обновлением — ПОНЯТ ✅

**Root cause:** сетевая нестабильность Telegram API (04:43–05:10 UTC), не незавершённое обновление.
- `ModuleNotFoundError: hermes_plugins` в кроне — by-design артефакт namespace-плагинов, не баг
- `SystemExit: 0` на `gateway/run.py:17878` — ожидаемое поведение при запрошенном выходе
- `StartLimitIntervalSec=0` у systemd — корректно, без лимита gateway восстановился сам

**Открытые рекомендации (в бэклог):**
- Health-check после рестарта (≤60 сек)
- Алерт ≥3 рестартов за 15 мин → TG уведомление
- Бэкап SHA + `.venv` перед `git pull`

## Безопасная процедура обновления Hermes

1. `cd ~/hermes-agent && git fetch`
2. Убедиться нет активных сессий (подождать тишины в логах)
3. `git pull`
4. `pip install -e .` (в venv!)
5. Проверить `python -c "import hermes; print('ok')"` — НЕ `hermes_plugins` (он by-design недоступен вне gateway)
6. Сообщить Саше: «готово к рестарту»
7. Дождаться явного ОК → `systemctl --user restart hermes-gateway` из отдельного shell
