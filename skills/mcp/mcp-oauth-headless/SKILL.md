---
name: mcp-oauth-headless
description: "Use when: OAuth MCP (Miro, Figma) на headless-ВМ Hermes."
version: 1.2.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [mcp, oauth, headless, miro, integration, config]
    related_skills: [native-mcp, hermes-gateway-setup]
---

# MCP OAuth на headless-ВМ Hermes

## Overview

Подключение remote MCP-серверов, защищённых **OAuth 2.1** (Miro MCP `https://mcp.miro.com/`, Figma, Linear и др.), к агенту Hermes на **ВМ без GUI/браузера**. OAuth требует интерактивного входа пользователем своим аккаунтом — на headless-сервере это делается через **SSH port-forward** на loopback-callback Hermes.

## Ключевые факты Miro MCP (проверено 09.2026)

- URL сервера: `https://mcp.miro.com/` — без токена отдаёт `HTTP 401`; auth по OAuth 2.1 protected-resource.
- Team-specific: при OAuth пользователь выбирает одну команду Miro; MCP видит только доски выбранной команды.
- «Last one wins»: 1 юзер ↔ ~1 активная OAuth-сессия MCP. Логин во второй клиент роняет первое подключение того же юзера. Для каждого пользователя вход своим аккаунтом.
- Корпоративные (Enterprise) планы: MCP по умолчанию выключен — нужен тумблер у админа (Admin → Apps & Integrations → MCP), применяется к конкретной команде.

## Правило Саши (жёсткое)

При постановке интерактивного шага давать Саше ТОЛЬКО его готовую точную команду — без плейсхолдеров `<порт>`, «подставь X». Порт подставляется только после фактического получения (из реального вывода `login`). Пока значение неизвестно — честно сказать «получу порт и дам готовую команду», не совать заглушку.

## Шаги установки (verified 14.09.2026 — Miro установлен, ✓ Connected, 61 tool)

### 0. РЕАЛЬНОСТЬ: SSH port-forward на эту ВМ НЕ работает
Сервер принимает только key-auth (id_ed25519 + passphrase), пароль отключён, **TCP-форвардинг закрыт** — `ssh -N -L ...` падает `Permission denied` даже при валидном ключе. Рабочий путь — **paste-back**: пользователь сам логинится в СВОЕЙ SSH-сессии и вставляет redirect URL обратно в терминал. Dashboard не нужен.

### 1. Добавить сервер с OAuth
```bash
cd ~/.hermes
printf 'y\ny\n' | hermes mcp add miro-mcp --url https://mcp.miro.com/ --auth oauth
```
Питфолл: на headless `--auth oauth` НЕ записывает `auth: oauth` в конфиг. Причина (`hermes_cli/mcp_config.py::cmd_mcp_add`): `get_or_build_provider()` кидает `OAuthNonInteractiveError` → ветка «Continue without authentication?» → сервер сохраняется с `enabled: false` и БЕЗ `auth`. Это штатно, не ошибка add. Все интерактивные промпты add/remove требуют piped-ответов: `printf 'y\ny\n' | ...` (первый `y` = «Continue without auth», второй = «Save config anyway»).

### 2. Проставить auth вручную (guard блокирует прямой patch config.yaml)
```bash
hermes config set mcp_servers.miro-mcp.auth oauth
```
Проверить: `grep -nA5 mcp_servers: config.yaml` → `url`, `auth: oauth`, `enabled: false`.

### 3. Login делает СА ПОЛЬЗОВАТЕЛЬ в своей SSH-сессии (не оркестратор в фоне!)
Порядок:
1. Саша заходит `ssh tkachenkoav@hermes-agents.devel.tutu.ru` (passphrase ключа).
2. Запускает `hermes mcp login miro-mcp` — печатаются OAuth-URL + порт callback.
3. Открывает URL в браузере ноута, входит в Miro, выбирает команду.
4. Браузер падает на `http://127.0.0.1:<ПОРТ>/callback?...` (страница НЕ откроется — норма) → **копирует весь адрес из адресной строки**.
5. Вставляет его в промпт login в SSH-сессии → `Got authorization code from paste` → `✓ Authenticated (N tools)`.
Фоновый запуск login оркестратором тоже работает (свой порт), но упростить путь не даёт — paste-back делает сам юзер, оркестратор только даёт шаги.

### 4. КРИТИЧНО: только ОДИН login одновременно
Второй параллельный login умирает: `OAuth callback port <ПОРТ> is already in use ([Errno 98])`. Каждый старт берёт НОВЫЙ случайный порт, а первый login держит свой. Перед новым login проверить/убить старый процесс (`ps aux | grep 'mcp login'`). URL/state/code_challenge при каждом рестарте новые — старые URL протухают.

### 5. Включение и проверка
```bash
hermes config set mcp_servers.miro-mcp.enabled true
hermes mcp test miro-mcp    # → ✓ Connected (Nms), Tools discovered: 61
```
`hermes mcp enable` НЕ существует. Инструменты `mcp_miro_*` появляются в сессиях только после переподнятия gateway. Токены: `~/.hermes/mcp-tokens/<name>.json` (+`.meta.json`, `.client.json`), refresh автоматический.

## Работа с досками Miro (после подключения, verified 15.09.2026)

Инструменты `mcp_miro_*` (61) доступны напрямую агенту. Чтение досок — через canvas-пару, не старые deprecated-инструменты:

- **`board_search_boards`** — список досок команды (name + miro_url). Возвращает `total` и `nextCursor`, пагинация `limit`(≤50)/`offset`. **`modified_at`/`created_at` всегда `null`** → определить «последнюю редактировавшуюся доску» по API НЕЛЬЗЯ (идемпотентно пустые метаданные). Не повторять этот бесполезный запрос — если Саша спрашивает «последняя правленая», просить ссылку/название или смотреть «Рецент» в Miro.
- **`canvas_search`** (result_mode=`overview`) по `miro_url` — выдаёт контейнеры (frame/diagram) с заголовками, item_count и **scope {x,y,width,height}**. Это обязательный первый шаг для чтения.
- **`canvas_read_as_svg`** ТРЕБУЕТ явный scope: либо `scope_x/y/width/height` из canvas_search, либо `widget_ids`. Без scope → `"Unscoped canvas reads are disabled"`. Нужен фрейм → либо 4 координаты scope, либо `miro_url?moveToWidget=<frame_id>` + scope.
- **Deprecated на 14.09.2026** (везде заменять на canvas_*): `layout_read`→`canvas_read_as_svg`, `context_get`→`canvas_search`/`canvas_read_as_svg`, `board_list_items`→`canvas_search`, `diagram_create_mermaid`/`layout_get_dsl`→`canvas_get_canvas_composer_skill`+`canvas_create_from_svg`.
- **Лимит чтения:** area-read падает выше ~500 widgets («fail above 500 widgets») — сужать scope/брать по фреймам.
- Большая доска (напр. оргструктура АИД): 1000+ элементов, 6+ фреймов. Каждый фрейм — отдельный блок; два похожих фрейма с датами = старая и актуальная версии, их не путать при резюме.
- Пример полного пути чтения фрейма: `canvas_search(miro_url, overview)` → взять scope интересного фрейма → `canvas_read_as_svg(miro_url, scope_x/y/w/h)` → вернуть `svg` с `data-content` и `data-shape` (текст и типы элементов).

Дальше — по обычным правилам: чтение/поиск/создание свободно; деструктивное (удаление досок/секций, смена доступа/ролей) — только по явной команде Саши с подтверждением.

## Питфоллы

- `--auth oauth` не пишется headless — фикс через `hermes config set` + piped `printf 'y\ny\n'` на промпты add.
- `hermes mcp enable` не существует — включение через `hermes config set mcp_servers.<name>.enabled true` после успешного login.
- Прямой patch config.yaml блокируется guard — только `hermes config set`.
- **SSH port-forward на ВМ закрыт** (`Permission denied` даже с ключом) — туннель не строится, только paste-back.
- Local Hermes Dashboard для OAuth не нравится Саше — paste-back в его SSH-сессии.
- Второй параллельный login падает «port already in use» — один login за раз, старый процесс убивать.
- Piped-ввод в интерактивные промпы add ненадёжен — проверять реальный конфиг после.
- `hermes mcp login` НЕ принимает имя сервера в background-PTY-запуске оркестратора, если сервер ещё без auth в конфиге — сначала шаг 2 (`auth: oauth` в конфиге), потом login.

## Проверка

```bash
hermes mcp list            # miro-mcp должна появиться
grep -nA5 mcp_servers: ~/.hermes/config.yaml   # url + auth: oauth
ls ~/.hermes/mcp-tokens/   # после login — файлы токенов
```
После успешного login — переподнять процесс Hermes, чтобы `mcp_miro_*` инструменты в тулсетах.