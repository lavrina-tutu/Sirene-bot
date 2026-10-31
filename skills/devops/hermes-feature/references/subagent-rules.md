# Subagent delegation rules

> Detailed delegation and prompt-contract rules moved from `SKILL.md`.

## Блок 6Б: Делегирование субагентов

Таблица 6Б — не канон PREFIX:фаза и не канон живого графа DEV/<slug>.
На живом графе: только agent -p по таблице DKP (инвариант 8). cronjob/delegate_task
на диспатчащихся детях запрещены.

Namespace (прецедент t_2c8ee3b2): cronjob(repeat=1) и delegate_task — D1
модель Hermes-воркера cronjob/delegate (hermes chat -m / toolsets file|terminal|web), НЕ нативный
Cursor CLI subagent и НЕ pipeline init. Передавать cursor-grok-* /
composer-2.5 / claude-sonnet-* в cronjob(model=) / delegate_task(model=)
запрещено (HTTP 400 tutu, 0 tool-calls, protocol_violation).
Если 6Б всё же вне пайплайна: D1 = NULL или tutu vendor/model;
роль Cursor (D2) — только внутри уже живого воркера через agent -p --model.
Колонка «Модель» ниже — slug внутреннего agent -p, не аргумент cronjob/delegate.

| Задача | Модель | Инструмент | Таймаут |
|---|---|---|---|
| Архитектор: ТЗ / план / анализ | `cursor-grok-4.6-high` | `cronjob(repeat=1)` | — |
| Архитектор: реализация (fallback) | то же | `cronjob(repeat=1)` | — |
| Исполнитель: реализация >5 мин | `composer-2.5` | `cronjob(repeat=1)` | — |
| Исполнитель: короткая <5 мин | `composer-2.5` | `delegate_task` | 300с |
| Координатор: справочный | `composer-2.5` | `delegate_task` | 120с |

НЕ для диагностики/починки багов инструментов и кронов — это кейс DevWorkflow BUG:diagnose (Блок 6В), а не одноразовый cronjob-аутсорсинг. Архитектор на диагностику бага вызывается только как воркер фазы `BUG:diagnose`.

### Toolsets

| Задача | enabled_toolsets |
|---|---|
| Архитектор: ТЗ / план | `["file", "terminal"]` |
| Исполнитель: реализация | `["file", "terminal"]` |
| Исполнитель: тестирование | `["file", "terminal"]` |
| Исследование с web | `["file", "terminal", "web"]` |

### Что передавать в промпт

1. Роль и среда, абсолютные пути
2. Полный текст ТЗ или плана: `cat` без `head`/`truncate`. Если не влезает в один промпт — абсолютный путь к файлу + «прочитай сам», либо явно «часть 1/N». Запрещено молча обрезать и выдавать обрывок как полный документ. Wiki-ссылки / URL без тела по-прежнему недостаточно. (Канон: pitfall cursor-cli.)
3. Граница автономности: «механическое — делай сам; семантическое — СТОП»
4. Формат отчёта, явные запреты
5. **Критичные факты из MEMORY — явно в промпт.** Cron-сессии НЕ получают MEMORY/USER PROFILE.
6. **Reuse-first (см. references/reuse-first-rule.md):** субагент не внедряет новые сущности без явного согласования Саши.

Полные правила: `references/subagent-rules.md`.
