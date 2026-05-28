# cronjob vs delegate_task — когда что использовать (25 мая 2026)

## Проблема

`delegate_task` с тяжёлыми Opus-задачами вызывает падение gateway:

```
Subagent 0 appears stale (no progress for 15 heartbeat cycles)
Stream stale for 180s — Killing connection
gateway.exit_nonzero (повторяется десятки раз 22-25 мая)
```

Причина: `reasoning_effort=high` + `child_timeout=1200` держит родительский HTTP-стрим открытым слишком долго. Gateway убивает соединение, Telegram-сессия рвётся.

## Правило выбора

| Критерий | cronjob | delegate_task |
|---|---|---|
| Ожидаемое время | >5 минут | <2 минут |
| Нужен контекст разговора | Нет (пишем полный prompt) | Да |
| Нужна обратная связь от пользователя | Нет | Да |
| Тип задачи | Разработка, исследования, ТЗ, настройка Hermes | Быстрые вопросы, уточнения |
| Модель | Opus | Sonnet/Haiku |

## Паттерн: cronjob для Opus-задачи

```python
cronjob(
    action='create',
    name='описание-задачи',
    prompt='Полный самодостаточный prompt с контекстом...',
    schedule='1m',           # минимальная задержка
    repeat=1,                # одноразово
    deliver='origin',        # ответ в текущий чат
    model={'model': 'claude-opus-4-7', 'provider': 'anthropic'},
    enabled_toolsets=['file', 'terminal', 'skills']
)
```

**Важно:** `deliver='origin'` — ответ придёт в тот же чат откуда была команда.

## Минусы cronjob (честно)

1. **Нет контекста разговора** — cronjob запускается в чистой сессии. Всё нужно писать в prompt явно.
2. **Нет обратной связи в процессе** — если Opus наткнулся на проблему, он не может спросить.
3. **Задержка старта** — минимум 1 минута (минимальное значение schedule).
4. **Нельзя остановить плавно** — только `cronjob(action='remove', job_id=...)`.
5. **Итерации дороже** — одна проблема = один cronjob, не диалог.

## delegate_task — когда всё ещё уместен

- Короткие задачи Sonnet/Haiku (<2 мин): поиск в файлах, простые правки
- Когда нужен немедленный результат и задача точно короткая
- Параллельный запуск 2-3 независимых коротких задач

## Конфигурация delegation в config.yaml

```yaml
delegation:
  model: claude-opus-4-7
  provider: anthropic
  reasoning_effort: high
  max_iterations: 50
  child_timeout_seconds: 1200
  max_concurrent_children: 3
```

Это применяется ко всем delegate_task вызовам. Передать `model=` явно в аргументах delegate_task невозможно (поля нет в схеме инструмента).
