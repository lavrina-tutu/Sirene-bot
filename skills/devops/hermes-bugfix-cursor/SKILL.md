---
name: hermes-bugfix-cursor
description: "Используй только если одновременно выполнены все условия: Hermes gateway сломан после update; явно указана конкретная ImportError, SchemaError, KeyError или ModuleNotFoundError; явно требуется ручная Remote-SSH процедура с journalctl/systemctl и rollback по SHA, restart или smoke-test. Общие «баг», «ошибка», «почини» не активируют этот скилл: обычный BUGFIX → dev-workflow; самостоятельный code fix → codex."
version: 1.0.1
author: agent
tags: [hermes, bugfix, cursor, ssh, emergency]
platforms: [linux]
---

# Нештатная починка Hermes через Cursor

Используй когда: обновление сломало gateway, появился ImportError/SchemaError/KeyError, нужно вручную исправить код или откатиться.

## Подключение к VM в Cursor

1. Открыть Cursor → `Ctrl+Shift+P` → **Remote-SSH: Connect to Host**
2. Хост: `tkachenkoav@<VM_IP>` (или alias из `~/.ssh/config`)
3. Открыть папку: `~/hermes-agent`

## Диагностика — первым делом

```bash
# Статус gateway
systemctl --user status hermes-gateway.service --no-pager

# Последние ошибки
journalctl --user -u hermes-gateway.service -n 50 --no-pager | grep -iE "error|exception|traceback|importerror"

# Полный лог с хвоста
journalctl --user -u hermes-gateway.service -f
```

Что искать:
- `ImportError: cannot import name X from Y` → что-то переименовали в новой версии
- `KeyError: 'X'` в config → ключ переименован/удалён в DEFAULT_CONFIG
- `SchemaError` → изменилась схема config.yaml
- `ModuleNotFoundError` → нужен `pip install -e .`

## Откат к предыдущей версии (если всё сломано)

```bash
# Узнать SHA до обновления (из лога обновления)
git -C ~/hermes-agent log --oneline | head -5

# Откатиться к конкретному коммиту
git -C ~/hermes-agent checkout <СТАРЫЙ_SHA>

# Рестарт
systemctl --user restart hermes-gateway.service
sleep 3
systemctl --user status hermes-gateway.service --no-pager | head -5
```

После отката — восстановить config из бэкапа если нужно:
```bash
cp ~/.hermes/profiles/anthropic/config.yaml.bak.YYYYMMDD ~/.hermes/profiles/anthropic/config.yaml
```

## Типичные баги после обновления

### ImportError / переименование
Найти в коде где раньше импортировалось:
```bash
grep -r "from X import Y" ~/hermes-agent --include="*.py" | head -10
```
Исправить импорт в нужном файле через Cursor.

### KeyError в config.yaml
Сравнить свой config с DEFAULT_CONFIG:
```bash
grep -A 200 "DEFAULT_CONFIG" ~/hermes-agent/hermes_constants.py | head -100
```
Добавить/переименовать недостающий ключ в `~/.hermes/profiles/anthropic/config.yaml`.

### pip-зависимости не обновлены
```bash
cd ~/hermes-agent
pip install -e . 2>&1 | tail -10
```

### Gateway не видит новый код после правки
```bash
systemctl --user restart hermes-gateway.service
sleep 5
journalctl --user -u hermes-gateway.service -n 20 --no-pager
```

## Тест после починки

```bash
# Быстрый smoke-test: проверить что gateway принимает сообщения
# Отправить сообщение в Telegram и посмотреть в логе:
journalctl --user -u hermes-gateway.service -f
# Должны появиться строки с "incoming message" или аналог
```

## Применить точечный фикс из upstream (cherry-pick)

Если upstream уже пофиксил баг, но мы откатились:
```bash
# Найти SHA фикса в upstream
git -C ~/hermes-agent log origin/main --oneline | grep "fix(X)"

# Cherry-pick
git -C ~/hermes-agent cherry-pick <SHA_ФИКСА>

# Рестарт
systemctl --user restart hermes-gateway.service
```

## Структура кода — ключевые файлы

```
~/hermes-agent/
├── run_agent.py          # AIAgent — основной агент-луп
├── hermes_constants.py   # DEFAULT_CONFIG — схема config.yaml
├── gateway/run.py        # Точка входа gateway
├── gateway/session.py    # Сессии gateway
├── gateway/platforms/telegram/  # Telegram-адаптер
├── tools/                # Инструменты агента
├── cron/scheduler.py     # Планировщик задач
└── agent/                # Провайдеры, память, кеш
```

## Связанные скиллы

- `upstream-dependency-monitor` — процедура планового обновления (git pull + Weekly QA через Opus-крон). Шаблон промпта: `templates/opus_update_and_qa.md`
- `hermes-agent` — общая документация по конфигурации и структуре Hermes

## Pitfalls

- **Не делать git pull на открытом репо в Cursor** — Cursor может держать файловые дескрипторы. Лучше pull через терминал, потом F5 в Cursor.
- **После правки .py — всегда рестарт** gateway. Python не перезагружает модули на лету.
- **Бэкапы config** создаются автоматически при обновлении (`.bak.YYYYMMDD`). Не затирать.
- **`git checkout <SHA>`** переводит в detached HEAD. Чтобы вернуться на main: `git checkout main`.
- **Cursor remote работает через SSH** — нужен VPN если VM не публичная.
