# Cursor CLI — справочник вызовов

## Базовый синтаксис

```bash
agent -p "задача" -f --model <MODEL> --output-format json
```

## Флаги

| Флаг | Назначение | Обязателен? |
|---|---|---|
| `-p, --print` | Неинтерактивный режим (выход после выполнения) | ✅ всегда |
| `-f, --force` | Пропуск диалогов доверия к workspace | ✅ всегда для headless |
| `--model <id>` | Конкретная модель | ✅ всегда |
| `--output-format json` | Структурированный вывод (usage, session_id, duration_ms) | Рекомендован |
| `--output-format stream-json` | Потоковый вывод (для долгих задач) | Опционально |
| `--mode plan` | Только чтение/планирование (без правок) | Для анализа |
| `--mode ask` | Вопросы/объяснения (без правок) | Для справок |
| `--resume <session_id>` | Продолжить конкретную сессию | Для цепочек |
| `--continue` | Продолжить последнюю сессию в директории | Для цепочек |

## Модели по ролям

| Роль | Модель | reasoning |
|---|---|---|
| Архитектор | `claude-sonnet-5-thinking-high` | Высокий (ТЗ, планы, архитектура) |
| Исполнитель | `composer-2.5` | Средний (код, тесты) |
| Координатор | `gemini-3.6-flash-low` | Низкий (сбор данных, механика) |

## JSON-вывод (--output-format json)

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 6978,
  "result": "...текст результата...",
  "session_id": "a438790e-8336-4315-9ac0-79ff757fd641",
  "usage": {
    "inputTokens": 14381,
    "outputTokens": 181,
    "cacheReadTokens": 2816,
    "cacheWriteTokens": 0
  }
}
```

**Ключевые поля:**
- `session_id` — сохранить для `--resume`
- `subtype` — `success` / `error_max_turns` / `error_budget`
- `duration_ms` — время выполнения
- `usage.inputTokens` / `outputTokens` — расход токенов

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

## Возобновление сессий

```bash
# Продолжить конкретную сессию
agent -p "Продолжи работу: [контекст]" -f --model composer-2.5 --resume <session_id> --output-format json

# Продолжить последнюю сессию в этой директории
agent -p "Продолжи работу: [контекст]" -f --model composer-2.5 --continue --output-format json
```

## Обработка ошибок

| Ошибка | Причина | Действие |
|---|---|---|
| `Authentication required` | Нет ключа | Установить `CURSOR_API_KEY` |
| `Workspace Trust Required` | Нет `-f` | Добавить `-f` |
| `subtype: error_max_turns` | Закончились ходы | Увеличить задачу или разбить на части |
| `subtype: error_budget` | Закончился бюджет | Проверить лимиты подписки |
| Зависание > timeout | Модель думает | Увеличить timeout до 600с |

## Таймауты

| Роль | Рекомендованный timeout |
|---|---|
| Координатор | 120с |
| Исполнитель | 300с |
| Архитектор | 600с |
