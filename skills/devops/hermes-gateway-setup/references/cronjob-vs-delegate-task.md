# cronjob vs delegate_task — когда что использовать

## История проблемы (25 мая 2026, устарело — см. апдейт ниже)

`delegate_task` с тяжёлыми Opus-задачами вызывал падение gateway:

```
Subagent 0 appears stale (no progress for 15 heartbeat cycles)
Stream stale for 180s — Killing connection
gateway.exit_nonzero (повторяется десятки раз 22-25 мая)
```

Причина: `reasoning_effort=high` + `child_timeout=1200` держал родительский HTTP-стрим открытым слишком долго. Gateway убивал соединение, Telegram-сессия рвалась.

## Апдейт 06.07.2026: root cause пофикшен апстримом

Апстрим hermes-agent (наша текущая версия v0.18.0) устранил оба бага:
- `0cc63043e` (апрель) — heartbeat stale-пороги: idle 150→450с, in-tool 600→1200с
- `bba9b519a` (июнь, #45149) — дефолтный `child_timeout_seconds`: 600→0 (без лимита), субагент падает только от реальных ошибок

**Статус: контролируемый пилот идёт (bk-115, `WorkVault/Hermes-Backlog/dialog-backlog.md`).**
`child_timeout_seconds` в конфиге поднят 1200→1800 (страховка, не апстрим-дефолт 0). Первый тяжёлый Opus-delegate_task протестирован 06.07.2026. Итоговая проверка статистики/падений — крон на 13.07.2026. До этой даты правило ниже остаётся действующим по умолчанию; после — обновить таблицу по факту решения.

## Правило выбора (действует до пересмотра по bk-115, ~13.07.2026)

| Критерий | cronjob | delegate_task |
|---|---|---|
| Ожидаемое время | >5 минут | <2 минут |
| Нужен контекст разговора | Нет (пишем полный prompt) | Да |
| Нужна обратная связь от пользователя | Нет | Да |
| Тип задачи | Разработка, исследования, ТЗ, настройка Hermes | Быстрые вопросы, уточнения |
| Модель | Opus (по умолчанию) | Sonnet/Haiku |

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

## Паттерн: точечный пилот Opus через delegate_task (используется с 06.07.2026)

`delegate_task` не поддерживает выбор модели per-call — только через глобальный `delegation.model` в config.yaml. Для контролируемого теста:
```bash
hermes config set delegation.model claude-opus-4-7
hermes config set delegation.reasoning_effort high
```
Запустить delegate_task с реальной, но не критичной задачей (анализ/ревизия, без изменений в файлах). Затем **сразу откатить**:
```bash
hermes config set delegation.model claude-sonnet-5
hermes config set delegation.reasoning_effort medium
```
Не оставлять delegation.model=opus как постоянное состояние до завершения пилота (bk-115) — другие текущие delegate_task вызовы в сессии иначе тоже улетят на Opus.

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
- Контролируемый пилот Opus-задач (см. выше) — до итога bk-115

## Конфигурация delegation в config.yaml (актуальна на 06.07.2026)

```yaml
delegation:
  model: claude-sonnet-5
  provider: anthropic
  reasoning_effort: medium
  max_iterations: 50
  child_timeout_seconds: 1800
  max_concurrent_children: 3
```

Это применяется ко всем delegate_task вызовам. Передать `model=` явно в аргументах delegate_task невозможно (поля нет в схеме инструмента) — только через глобальный config.yaml, отсюда паттерн "temp-set → run → revert" выше.
