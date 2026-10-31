---
name: hermes-desktop-remote
description: "Use when: удалённое подключение Hermes Desktop к ВМ."
version: 1.0.0
author: agent
tags: [hermes, desktop, remote, gateway, serve, vpn, windows]
platforms: [linux, windows]
---

# Hermes Desktop Remote Setup

Настройка `hermes serve` на Linux-ВМ и подключение к нему из Hermes Desktop на Windows-ноутбуке.

## Когда использовать

Пользователь хочет:
- работать с Hermes на ВМ через Desktop-приложение на ноутбуке
- единый инстанс агента (сессии, память, скиллы, кроны) и через Telegram, и через Desktop
- без локального агента на ноутбуке (только клиент)

## Принцип

- На ВМ: `hermes serve --host 0.0.0.0 --port 9119` — HTTP+WebSocket-сервер для Desktop
- Desktop на ноутбуке: режим Remote gateway
- Telegram-gateway (если есть) — отдельный процесс на ВМ
- Desktop и Telegram управляют **одним** агентом

## Prerequisites

- SSH-доступ к ВМ с ноутбука
- Hermes CLI установлен на ВМ
- Hermes Desktop установлен на Windows
- Сеть: ноутбук → ВМ по IP/хостнейму (VPN/корпсеть)
- sudo на ВМ для firewall

## Шаг 1 — На ВМ: креды dashboard

В `~/.hermes/.env`:

```bash
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin
HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=<password>
HERMES_DASHBOARD_BASIC_AUTH_SECRET=$(openssl rand -base64 32)
chmod 600 ~/.hermes/.env
```

> `HERMES_DASHBOARD_BASIC_AUTH_SECRET` — стабильная подпись сессий. Без неё Desktop теряет логин при каждом рестарте serve.

## Шаг 2 — На ВМ: сборка web-UI

```bash
cd ~/hermes-agent/web && npm install --no-audit --no-fund && npm run build
```

Флаг `--skip-build` позволяет не пересобирать при каждом рестарте.

## Шаг 3 — На ВМ: systemd-юнит

`~/.config/systemd/user/hermes-serve.service`:

```ini
[Unit]
Description=Hermes Dashboard backend
After=network-online.target

[Service]
Type=simple
EnvironmentFile=%h/.hermes/.env
ExecStart=%h/hermes-agent/.venv/bin/hermes serve --host 0.0.0.0 --port 9119 --skip-build
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-serve.service
```

Проверка: `ss -tlnp | grep 9119` → слушает `0.0.0.0:9119`.

## Шаг 4 — На ВМ: firewall (nftables)

Доступ к 9119 — **только** из доверенной подсети (VPN/корпсеть).

`/etc/nftables.conf`:

```bash
table inet hermes_dash {
    chain input {
        type filter hook input priority filter; policy accept;
        iif lo accept
        ip saddr <trusted-subnet> tcp dport 9119 accept
        tcp dport 9119 reject with icmp port-unreachable
    }
}
```

```bash
sudo nft -f /etc/nftables.conf
sudo systemctl enable nftables
```

> Подсеть ноутбука — из `ss -tnp | grep ':22 '`.

## Шаг 5 — Проверка на ВМ

```bash
# /api/status → auth_required: true, auth_providers: ["basic"]
curl -s http://127.0.0.1:9119/api/status | python3 -m json.tool

# POST /auth/password-login → HTTP 200
curl -s -c /tmp/cookies.txt -X POST http://127.0.0.1:9119/auth/password-login \
  -H 'Content-Type: application/json' \
  -d '{"provider":"basic","username":"admin","password":"<password>"}'

# Авторизованный вызов → HTTP 200
curl -s -b /tmp/cookies.txt http://127.0.0.1:9119/api/sessions
```

## Шаг 6 — На Windows: установка Desktop

```powershell
irm https://hermes-agent.nousresearch.com/install.ps1 | iex
```

В мастере:
- **3 — Blank Slate** (без локального gateway)
- Gateway start → **n** (чтобы не было конфликта поллинга с ВМ)

## Шаг 7 — На Windows: подключение к ВМ

1. `hermes desktop` (или ярлык из Пуска)
2. **Settings → Gateway**
3. Выбрать **Remote gateway**
4. **Remote URL:** `http://<хост-вм>:9119`
5. **Sign in**: `admin` / пароль из `.env` на ВМ
6. **Save and reconnect**

Проверка: написать сообщение в Desktop — агент отвечает.

## Шаг 8 — Финальная проверка

- Desktop отвечает ✅
- Telegram (если настроен) отвечает ✅
- Оба канала — один агент (одни сессии/память/кроны)

## Pitfalls

1. **Конфликт Telegram-токена.** Если в локальном `.env` на ноутбуке оказался `TELEGRAM_BOT_TOKEN` с ВМ — Blank Slate обязателен. Два poller'а на один токен роняют gateway.

2. **Локальный firewall на ноутбуке.** Проверить: `Test-NetConnection <хост> -Port 9119`.

3. **Serve на localhost.** Без `--host 0.0.0.0` биндится на `127.0.0.1` — снаружи не виден.

4. **nftables блокирует localhost.** Нужно `iif lo accept`, иначе curl с ВМ тоже не пройдёт.

5. **Нет SECRET.** Без `HERMES_DASHBOARD_BASIC_AUTH_SECRET` Desktop теряет сессию при рестарте serve.

6. **auth_flows: cookie, не basic-header.** Desktop логинится через POST `/auth/password-login`, не через `Authorization: Basic`.

7. **Старый конфиг на ноутбуке.** Предыдущая установка Hermes может подтянуть конфиг — Blank Slate решает.

## Переменные окружения

| Переменная | Где | Назначение |
|---|---|---|
| `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` | `.env` на ВМ | Логин dashboard |
| `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` | `.env` на ВМ | Пароль dashboard |
| `HERMES_DASHBOARD_BASIC_AUTH_SECRET` | `.env` на ВМ | Подпись сессий |

## Полезные команды

```bash
systemctl --user status hermes-serve.service
journalctl --user -u hermes-serve.service --no-pager -n 50
curl -s http://127.0.0.1:9119/api/status | python3 -m json.tool
ss -tlnp | grep 9119
sudo nft list table inet hermes_dash
```