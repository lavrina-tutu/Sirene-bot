# Cursor CLI — проверенные паттерны и pitfall'ы

## Паттерн вызова (headless)

```bash
agent -p "задача" -f --model <model> --output-format json
```

- `-p` — print-mode, неинтерактивный
- `-f` — force, **обязателен** для headless (без него — диалог Workspace Trust)
- `--output-format json` — structured output: `usage`, `session_id`, `duration_ms`
- `--model` — конкретная модель (список: `agent --list-models`)

## Установка

```bash
# Правильно (вывод в stdout, не через -o):
curl -fsS https://cursor.com/install > /tmp/install.sh && bash /tmp/install.sh

# НЕПРАВИЛЬНО (сервер отдаёт HTML при -o):
curl -fsS -o /tmp/install.sh https://cursor.com/install  # ← не работает!
```

**Причина:** `cursor.com/install` определяет контекст вызова. При `-o` (сохранение в файл) сервер отдаёт HTML-страницу. При выводе в stdout — bash-скрипт.

Бинарник: `~/.local/bin/agent` (симлинк на `~/.local/share/cursor-agent/versions/<version>/cursor-agent`)

## Аутентификация

1. Получить User API Key: **Cursor Dashboard → API Keys** (левое меню, блок «Управление данными»)
2. Ключ формата: `crsr_...` (показывается один раз)
3. Установить в `~/.hermes/.env` и `~/.hermes/profiles/<profile>/.env`:
   ```bash
   CURSOR_API_KEY=crsr_...
   ```

## Доступные семейства моделей

Claude (Opus, Sonnet, Fable), GPT-5.x, Cursor Grok, Composer, Gemini, Kimi, GLM.

**DeepSeek отсутствует.**

## Модели Cursor по ролям (принятая схема)

| Роль | Модель | Назначение |
|---|---|---|
| Архитектор | `claude-sonnet-5-thinking-high` | ТЗ, планы, архитектурные решения |
| Исполнитель | `composer-2.5` | Код, тесты, механические правки |
| Координатор | `gemini-3.6-flash-low` | Сбор данных, лёгкая механика |

## Pitfall: Workspace Trust

Без `-f` Cursor CLI запрашивает подтверждение доверия к директории:

```
⚠ Workspace Trust Required
  Cursor Agent can execute code and access files in this directory.
  To proceed: pass --trust, --yolo, or -f
```

**Решение:** всегда `-f` в headless-режиме.

## Pitfall: git repo required

Cursor CLI требует git-репозиторий. Для scratch-задач:
```bash
cd $(mktemp -d) && git init && agent -p "..." -f --output-format json
```

## Интеграция с Hermes terminal()

```bash
terminal("agent -p 'задача' -f --model composer-2.5 --output-format json", workdir="...", timeout=300)
```
