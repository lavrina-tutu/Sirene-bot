# Cursor CLI — справочник вызовов

> Детальный справочник. Краткая версия — в теле скилла `cursor-cli`.

## Базовый синтаксис

```bash
agent -p "задача" -f --model <MODEL> --output-format json
```

## Полная таблица флагов

| Флаг | Назначение | Обязателен? |
|---|---|---|
| `-p, --print` | Неинтерактивный режим (выход после выполнения) | ✅ всегда |
| `-f, --force` | Пропуск диалогов доверия к workspace | ✅ всегда для headless |
| `--model <id>` | Конкретная модель из `agent --list-models` | ✅ всегда |
| `--output-format json` | Структурированный вывод (usage, session_id, duration_ms) | Рекомендован |
| `--output-format stream-json` | Потоковый вывод (для долгих задач) | Опционально |
| `--output-format text` | Plain-text вывод (по умолчанию) | Для отладки |
| `--mode plan` | Только чтение/планирование (без правок) | Для анализа |
| `--mode ask` | Вопросы/объяснения (без правок) | Для справок |
| `--resume <session_id>` | Продолжить конкретную сессию | Для цепочек |
| `--continue` | Продолжить последнюю сессию в директории | **Запрещён в DevKanbanPipeline** (см. ниже) |
| `--workspace <ABS_DIR>` | Рабочая директория агента (абсолютный путь) | **Обязателен в DevKanbanPipeline** |
| `--api-key <key>` | API-ключ (альтернатива `CURSOR_API_KEY`) | Если нет в env |

## Модели по ролям (с примерами reasoning-уровней)

| Роль | Основная модель | Альтернативы | reasoning |
|---|---|---|---|
| Архитектор | `claude-sonnet-5-thinking-high` | `claude-opus-4-8-thinking-high`, `gpt-5.6-sol-xhigh` | Высокий |
| Исполнитель | `composer-2.5` | `claude-sonnet-5-medium`, `cursor-grok-4.5-medium` | Средний |
| Координатор | `gemini-3.6-flash-low` | `gpt-5.4-mini`, `claude-sonnet-5-low` | Низкий |

## Полный JSON-вывод

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 6978,
  "duration_api_ms": 6978,
  "result": "...текст результата...",
  "session_id": "a438790e-8336-4315-9ac0-79ff757fd641",
  "request_id": "6a48c92c-68ea-4def-8725-d0d71d703e01",
  "usage": {
    "inputTokens": 14381,
    "outputTokens": 181,
    "cacheReadTokens": 2816,
    "cacheWriteTokens": 0
  }
}
```

### Ключевые поля

- `session_id` — сохранить для `--resume` при цепочках вызовов
- `subtype` — `success` / `error_max_turns` (исчерпаны ходы) / `error_budget` (исчерпан бюджет)
- `duration_ms` — время выполнения
- `usage.inputTokens` / `outputTokens` — расход токенов
- `usage.cacheReadTokens` — попадания в кеш (экономия)
- `request_id` — для отладки/логирования

## Примеры вызовов

### Архитектор — ТЗ/план
```bash
cd /path/to/project && agent -p "Составь ТЗ для инструмента FooBar. Прочитай MAIN_TZ_INVENTORY.md, проанализируй связи." \
  -f --model claude-sonnet-5-thinking-high --output-format json
```

### Архитектор — анализ (read-only)
```bash
agent -p "Проанализируй архитектуру проекта. Только чтение, без правок." \
  -f --model claude-sonnet-5-thinking-high --mode plan --output-format json
```

### Исполнитель — реализация
```bash
cd /path/to/project && agent -p "Реализуй по плану: [план]. Файлы: [список]." \
  -f --model composer-2.5 --output-format json
```

### Исполнитель — тестирование
```bash
cd /path/to/project && agent -p "Напиши тесты для [модуль]. Запусти pytest -v, убедись что все проходят." \
  -f --model composer-2.5 --output-format json
```

### Координатор — сбор данных
```bash
agent -p "Найди в кодовой базе все использования [паттерн]. Выведи список файлов и строк." \
  -f --model gemini-3.6-flash-low --output-format json
```

## Цепочки вызовов (сессии)

```bash
# Первый вызов — сохранить session_id
RESPONSE=$(agent -p "$(cat /tmp/task.md)" -f --model composer-2.5 --workspace /abs/path --output-format json)
SESSION_ID=$(echo "$RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['session_id'])")

# Продолжить ту же сессию
agent -p "$(cat /tmp/task-followup.md)" -f --model composer-2.5 --workspace /abs/path --resume "$SESSION_ID" --output-format json
```

### DevKanbanPipeline (канбан-воркер)

- `--workspace <ABS_DIR>` — обязателен; путь из `$HERMES_KANBAN_WORKSPACE` / карточки.
- `--resume <session_id>` — единственный способ продолжения сессии в пайплайне.
- `--continue` — **запрещён** (смешивает сессии при двух workspace на одной машине).
- Параллель: макс. 2 процесса, деревья `--workspace` не пересекаются.
- `IDEA:analyze`: модель `cursor-grok-4.6-high`.
- `session_id` → `kanban_comment` сразу после первого вызова.

```bash
# ❌ Запрещено в пайплайне
agent -p "..." -f --model composer-2.5 --continue --output-format json

# ✅ Правильно
agent -p "$(cat /tmp/task.md)" -f --model composer-2.5 \
  --workspace /home/tkachenkoav/USERTOOLS/Foo --resume "$SESSION_ID" --output-format json
```

## Обработка ошибок

| Ошибка | Причина | Действие |
|---|---|---|
| `Authentication required` | Нет `CURSOR_API_KEY` или ключ невалидный | Проверить `echo $CURSOR_API_KEY`, перевыпустить в дашборде |
| `Workspace Trust Required` | Нет `-f` | Добавить `-f` |
| `subtype: error_max_turns` | Слишком много ходов в print-mode | Разбить задачу на части |
| `subtype: error_budget` | Исчерпан бюджет подписки | Проверить лимиты в Cursor Dashboard |
| 403 при скачивании | Geo/IP блокировка `downloads.cursor.com` | Использовать `curl > file` (shell redirect), не `curl -o` |
| Зависание > timeout | Модель глубоко думает | Увеличить timeout до 600с (архитектор) |
| Foreground-вызов убит инструментом терминала (~420с кэп ниже рекомендованных 600с) | Тяжёлые архитекторские/аналитические прогоны (чтение ТЗ+кода+БД, input 500K+) не укладываются | Запускать фоном с выводом в файл: `agent -p "$(cat /tmp/task.md)" ... --output-format json > /tmp/run.json 2>&1; echo EXIT=$?`, затем читать JSON и проверять артефакт на диске. Не гнать тяжёлый прогон foreground «с большим timeout» — кэп инструмента ниже |
| `git init` required | Cursor CLI требует git-репозиторий | `git init` в рабочей директории |

## Таймауты

| Роль | Рекомендованный timeout | Обоснование |
|---|---|---|
| Координатор | 120с | Быстрые справки, поиск |
| Исполнитель | 300с | Код, тесты, средние задачи |
| Архитектор | 600с | ТЗ, планы, сложный анализ |

## Установочный pitfall

При установке Cursor CLI **не использовать** `curl -o`:
```bash
# ❌ НЕПРАВИЛЬНО — сервер возвращает HTML вместо скрипта
curl -fsS https://cursor.com/install -o install.sh

# ✅ ПРАВИЛЬНО — через shell redirect
curl -fsS https://cursor.com/install > install.sh
bash install.sh
```

Причина: сервер `cursor.com` проверяет, является ли вывод pipe'ом. Если цель — файл (`-o`), отдаёт HTML-страницу. Если pipe/stdout — отдаёт bash-скрипт.
