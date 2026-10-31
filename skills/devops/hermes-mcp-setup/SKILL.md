---
name: hermes-mcp-setup
description: "Use when: подключение MCP, OAuth-логин headless-ВМ."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, mcp, integration, oauth, config]
    related_skills: [hermes-feature, hermes-gateway-setup, cursor-cli]
---

# hermes-mcp-setup — подключение внешних MCP-серверов к Hermes

## Overview

Как подключить внешний MCP-сервер (HTTP/StreamableHTTP или stdio) к Hermes, выбрать способ аутентификации и — главное — пройти интерактивный OAuth на **headless-ВМ без GUI и браузера**. Класс задачи: любой внешний MCP (Miro, GitHub, внутренние corp-серверы).

> **Внимание:** bundled-скилл `native-mcp` устарел — описывает только stdio и HTTP+headers. Актуальный Hermes CLI поддерживает OAuth 2.1 (`hermes mcp add --auth oauth` + `hermes mcp login`). Источник истины — `hermes mcp --help`, а не описания скиллов.

## Где и что настраивается

- CLI: `hermes mcp add <name> --url <url> [--auth {oauth,header}] [--connect-timeout N]` затем `hermes mcp login <name>`.
- Конфиг пишется в `mcp_servers` в `~/.hermes/config.yaml` (вручную тоже можно).
- OAuth-токен сохраняется на диск в `~/.hermes/mcp-tokens/` (каталог появляется после первого логина; до этого его нет).
- Обзор: `hermes mcp list`. Инструменты появляются с префиксом `mcp_<server>_<tool>` и **только после переподъёма процесса** (нет hot-reload).
- `hermes mcp status` — НЕ существует (invalid choice; см. `hermes mcp list`).

## Два способа аутентификации (выбор)

| Способ | `--auth` | Кому подходит |
|---|---|---|
| **OAuth 2.1** (PKCE + DCR + localhost-callback + refresh) | `oauth` | «каждый работает от своего имени»; интерактив; первый вход делает пользователь |
| **Статичный токен / заголовок** | `header` (+ `--env KEY=VAL` для stdio) | одно общее приложение/аккаунт на всех; быстро, без браузерного входа |

Если требование — **per-user** («каждый пользователь от своего имени») → OAuth. Статичный токен не различает пользователей.

## Headless OAuth (без dashboard, без GUI на ВМ)

`hermes mcp login` на headless-ВМ поднимает localhost-callback и ждёт. Рабочие пути (dashboard НЕ обязателен):

**1. SSH-проброс порта (рекомендуется, консольный).**
На ВМ: `hermes mcp add <name> --url <url> --auth oauth` → `hermes mcp login <name>` — напечатает порт (напр. `127.0.0.1:8765`) и authorization URL. На ноуте пользователя:
```bash
ssh -N -L 8765:127.0.0.1:8765 user@<VM>   # держать открытым
```
Открыть `http://127.0.0.1:8765` в браузере ноута → OAuth → выбрать команду (Miro team) → callback пробрасывается на ВМ → login получает код, пишет токен на диск.

**2. Paste-back URL (без SSH/портов).**
`hermes mcp login` печатает authorization URL. Пользователь открывает его браузером на ноуте, проходит OAuth, копирует URL из адресной строки (с `?code=...`) и возвращает в консоль ВМ / агенту. Токен сохраняется.

**3. SSH-TTY / Hermes Dashboard** — применимо в других случаях запуска.

## Подготовка перед OAuth

- Для корпоративных (Enterprise) планов провайдера MCP может быть **выключен админом** по умолчанию (Miro: Admin → Apps & Integrations → MCP). Проверить у админа, что тумблер включён, ДО развода OAuth.
- Уточнить какую **команду/team** выбирать — MCP видит только доски/данные выбранной команды.
- Узнать, как пользователь попадает на ВМ (SSH vs Hermes Desktop) — определяет способ логина.
- Проверить, нет ли уже следов/токена этого MCP у других агентов на этой ВМ (`grep -ril '<name>' ~/.hermes ~/USERTOOLS ~/WorkVault`, `.env`, `~/.hermes/mcp-tokens/`) — переиспользование быстрее.

## Верификация

- `hermes mcp list` — сервер в списке.
- `ls ~/.hermes/mcp-tokens/` — после логина есть токен.
- После переподъёма процесса искать инструменты `mcp_<server>_*`.

## Питфоллы

- **`hermes mcp status` не существует** — только `list`.
- **Переподъём процесса нужен**, чтобы инструменты появились (нет hot-reload). Gateway-рестарт часто под запретом — согласовывать с пользователем.
- **`~/.hermes/mcp-tokens/` отсутствует до первого логина** — его отсутствие ≠ поломка.
- **Первый OAuth логин — ручная операция пользователя** (нужна его авторизация + выбор команды); после кэша токенов cron/агент ходят сами через refresh.

## Связанные файлы

- `references/miro-mcp.md` — практический разбор подключения официального Miro MCP к Hermes (команды, auth, ограничения).