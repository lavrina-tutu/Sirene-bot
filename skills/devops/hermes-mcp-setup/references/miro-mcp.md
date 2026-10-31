# Miro MCP → Hermes (практический разбор, 09.2026)

## Что такое Miro MCP
- Официальный HTTP-сервер `https://mcp.miro.com/` (return 401 без Bearer — protected resource).
- Аутентификация только **OAuth 2.1** + DCR + PKCE. Отдельного статичного API-ключа под MCP нет.
- Токен живёт в сторе клиента, НЕ в `~/.claude.json` (там только URL).
- Правило **«last one wins»**: 1 пользователь ↔ активная команда ↔ по сути 1 живая MCP-сессия. Логин во второй клиент роняет первый. Три клиента разом не работают.
- Команда/team выбирается в OAuth-флоу; MCP видит только доски **выбранной команды**.
- Enterprise: включить MCP у админа (Admin → Apps & Integrations → MCP); по умолчанию выключен.
- Лимиты вызовов/сутки: Free 100 / Starter 500 / Business 2000 / Enterprise 10000 (UTC). Часть read-вызовов (`context_get`) тратит AI credits.

## Команды установки (Hermes на ВМ)
```bash
hermes mcp add miro-mcp --url https://mcp.miro.com/ --auth oauth
hermes mcp login miro-mcp
```
Затем переподъём процесса, чтобы появились `mcp_miro_*` инструменты.

## Конфиг-шаблон (эквивалент)
```yaml
mcp_servers:
  miro-mcp:
    url: "https://mcp.miro.com/"
    auth: oauth
```

## Ключевые факты проверки среды (сборка материала)
- `claude`/Claude Code на ВМ НЕТ, `~/.claude.json`/`~/.claude` отсутствуют. Ссылка-установщик (`miro-mcp.ps1`) патчит `~/.claude.json` → это **Claude Code на Windows-ноуте**, не наша ВМ.
- PowerShell-установщик добавляет `mcpServers.miro-mcp = {type: http, url: https://mcp.miro.com/}`.
- Hermes: `mcp_servers` в config.yaml = `{}` изначально; `~/.hermes/mcp-tokens/` отсутствует до первого логина.
- Среда headless: DISPLAY/WAYLAND нет, stdin не TTY, Firefox есть но GUI без дисплея не откроет.
- НЕ путать: официальный MCP (`mcp.miro.com`) vs community npm-пакет `@k-jarzyna/mcp-miro` (требует MIRO_ACCESS_TOKEN через env) — это разные интеграции.

## Диагностика
- `curl -sSI https://mcp.miro.com/` → HTTP 401 `www-authenticate: Bearer` = сервер жив, авторизация не пройдена (штатно).
- `hermes mcp list` — проверить наличие сервера.
- `ls ~/.hermes/mcp-tokens/` — проверить сохранённый OAuth-токен.

## Ограничения/риски для автоматики
- OAuth-токены из Claude Code ↔ Hermes не переносимы: разные OAuth-клиенты.
- Agent с write-тулами (`board_create`, `layout_create`, `diagram_create`, …) с Telegram может менять живые доски.
- Для детерминированной автоматики Miro сами рекомендуют REST API, не MCP.