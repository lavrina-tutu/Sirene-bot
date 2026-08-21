---
name: fireflies-autojoin
description: "Автоприглашение Fireflies-бота Fred на Zoom-встречи из Outlook через API addToLiveMeeting (без почтового инвайта боту). Диагностика, dry-run, cron tick/fire. Триггеры: fireflies-autojoin, Fred, автозапись встречи, пригласи бота на встречу, статус fireflies, почему Fred не пришёл."
version: "1.0.0"
author: Sirene
license: MIT
platforms: [linux]
tags: [fireflies, exchange, ews, zoom, meetings, cron, tutu]
metadata:
  hermes:
    tags: [fireflies, exchange, ews, zoom, cron, tutu]
    related_skills: [exchange-monitor, fireflies-transcripts, tz-workflow]
---

# Fireflies auto-join (Fred)

## Где код

`~/USERTOOLS/FirefliesAutojoin/` — Python-пакет `ffjoin/`, обёртка `bin/run.sh`, cron-скрипты в `scripts/`.

Апстрим: [fireflies-autojoin v0.2.1](https://stash.tutu.ru/projects/DATA-SCIENCE/repos/fireflies-autojoin) (DATA-SCIENCE). Sirene-форк: `0.2.1+sirene1`, пароль Exchange из общего `.env`.

## Механика tick / fire

| Команда | Расписание cron | Что делает |
|---|---|---|
| `tick` | `*/30` в CRON_HOURS/CRON_DAYS | Единственный, кто читает Exchange. Фильтрует встречи, извлекает Zoom-URL, пишет `state/plan.json`. |
| `fire` | `*` (каждую минуту) | Читает только локальный план. При `now >= start` и в окне 15 мин вызывает `addToLiveMeeting`. |

Разделение исключает двойное приглашение от двух процессов. `flock` на `state/tick.lock` и `state/fire.lock`.

**Лимит Fireflies:** 3 вызова `addToLiveMeeting` за 20 минут (`state/rate.json`, `MAX_ATTEMPTS=3`).

## Что скипается

Fred **не** приходит на:

- отменённые (`cancelled`);
- «весь день» (`all_day`);
- с вашим отказом (`declined`);
- Private/Confidential в Outlook (`private`, `SKIP_PRIVATE=true` по умолчанию).

## Креды

Загрузка через `usertools_env` из `~/.config/hermes/.env` + локальный `~/USERTOOLS/FirefliesAutojoin/.env` (только настройки, **без секретов**):

| Ключ | Откуда |
|---|---|
| `TUTU_DOMAIN_PASSWORD` | `~/.config/hermes/.env` |
| `FIREFLIES_API_KEY` | `~/.config/hermes/.env` |
| `LOOP_TOKEN` | `~/.config/hermes/.env` (алерты в Loop) |
| `EXCHANGE_EMAIL`, `EXCHANGE_SERVER`, cron, TLS | локальный `.env` |

Не использовать `source ~/.config/hermes/.env` — только `load_usertools_env()`.

## Cron

**Системный crontab пользователя**, не Hermes gateway. Установка: `./scripts/install-cron.sh`. Маркер: `# fireflies-autojoin`. Две строки: tick (30 мин) и fire (1 мин). Расписание — timezone сервера (`timedatectl`), не `TIMEZONE` из `.env`.

## Диагностика

```bash
cd ~/USERTOOLS/FirefliesAutojoin
./bin/run.sh status
tail -50 logs/cron.log
cat state/health.json
```

`status` → `fireflies_key: true`, `exchange: true`, `plan_stale`, `last_tick_error`, список `planned`.

Типичные причины сбоя: истёк пароль / VPN / TLS (`EXCHANGE_VERIFY_TLS=false`), квота Fireflies, встреча без Zoom-ссылки в теле.

## Питфоллы

- **Windows-ноут Саши не участвует** — сервис на Linux-ВМ с cron. Fred появляется в участниках Zoom с момента старта встречи (видно на Windows).
- **Транскрипт** появляется в [app.fireflies.ai](https://app.fireflies.ai) через несколько минут после окончания, не мгновенно.
- **План раз в 30 мин** — встречу, отменённую после последнего tick, бот может посетить.
- **`UnconfirmedInvite` (таймаут Fireflies)** — не ретраится: риск второго бота в комнате важнее пропуска записи.
- Каталог **не** под ownCloud/WorkVault (`state/`, `logs/` — 700, `.env` — 600).

## Связанные материалы

- README инструмента: `~/USERTOOLS/FirefliesAutojoin/README.md`
- ТЗ / бриф: процесс через скилл `tz-workflow`; архитектурный план развёртывания — `WorkVault/Hermes-Backlog/` (fireflies-autojoin)
