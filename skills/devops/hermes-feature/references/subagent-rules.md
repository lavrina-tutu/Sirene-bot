# Subagent delegation rules

> Detailed delegation and prompt-contract rules moved from `SKILL.md`.

## Блок 6Б: Делегирование субагентов

Таблица 6Б — не канон PREFIX:фаза и не канон живого графа DEV/<slug>.
На живом графе: только invoke-role (codex CLI) по таблице DKP (инвариант 8). cronjob/delegate_task
на диспатчащихся детях запрещены.

Namespace (прецедент t_2c8ee3b2): cronjob(repeat=1) и delegate_task — D1
модель Hermes-воркера cronjob/delegate (hermes chat -m / toolsets file|terminal|web), НЕ codex
CLI субagent и НЕ pipeline init. Передавать gpt-6.1-* / codex-роли
в cronjob(model=) / delegate_task(model=)
запрещено (HTTP 400 tutu, 0 tool-calls, protocol_violation).
Если 6Б всё же вне пайплайна: D1 = NULL или tutu vendor/model;
роль codex (D2) — только внутри уже живого воркера через invoke-role.
Колонка «Модель» ниже — slug внутреннего codex invoke-role, не аргумент cronjob/delegate.

| Задача | Модель | Инструмент | Таймаут |
|---|---|---|---|
| Архитектор: ТЗ / план / анализ | `gpt-6-astra` | `invoke-role` (codex) | — |
| Ревизор: ревью | `gpt-6-astra` | `invoke-role` (codex) | — |
| Исполнитель: реализация | `gpt-6.1-sol` | `invoke-role` (codex) | — |
| Компрессор: экстракт/переупаковка | `gpt-6.1-terra` | `invoke-role` (codex) | — |

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
2. Полный текст ТЗ или плана: `cat` без `head`/`truncate`. Если не влезает в один промпт — абсолютный путь к файлу + «прочитай сам», либо явно «часть 1/N». Запрещено молча обрезать и выдавать обрывок как полный документ. Wiki-ссылки / URL без тела по-прежнему недостаточно.
3. Граница автономности: «механическое — делай сам; семантическое — СТОП»
4. Формат отчёта, явные запреты
5. **Критичные факты из MEMORY — явно в промпт.** Cron-сессии НЕ получают MEMORY/USER PROFILE.
6. **Reuse-first (см. references/reuse-first-rule.md):** субагент не внедряет новые сущности без явного согласования Саши.

Полные правила: `references/subagent-rules.md`.
