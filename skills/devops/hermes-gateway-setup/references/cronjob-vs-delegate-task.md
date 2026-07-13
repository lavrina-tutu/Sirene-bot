# cronjob vs delegate_task — когда что использовать (обновлено 13.07.2026)

## История проблемы (решена апстримом)

До апреля-июня 2026 `delegate_task` с тяжёлыми Opus-задачами вызывал падение gateway:

```
Subagent 0 appears stale (no progress for 15 heartbeat cycles)
Stream stale for 180s — Killing connection
```

Причина: `reasoning_effort=high` + `child_timeout=1200` держал родительский HTTP-стрим открытым слишком долго, ложно триггеря heartbeat-stale детекцию.

**Апстрим-фиксы (уже в hermes-agent v0.18.0+, которым мы пользуемся):**
- `0cc63043e` (апрель) — heartbeat-пороги: idle 150→450с, in-tool 600→1200с
- `bba9b519a` (июнь, #45149) — дефолтный `child_timeout_seconds`: 600→0 (без лимита)

**Наш пилот (bk-115, 06.07–13.07.2026):** child_timeout_seconds поднят до 1800 на неделю проверки, gateway чист весь период (0 падений). 13.07.2026 лимит снят окончательно — `child_timeout_seconds: 0`.

## Текущее правило выбора (с 13.07.2026)

Оба инструмента теперь одинаково безопасны для Opus. Выбор — по контексту задачи, не по модели:

| Критерий | cronjob | delegate_task |
|---|---|---|
| Нужен контекст текущего диалога | Нет (пишем полный самодостаточный prompt) | Да |
| Должна пережить закрытие сессии | Да | Нет (background, теряется при /new или падении процесса) |
| Нужна обратная связь от пользователя в процессе | Нет | Да (через основной чат) |
| Расписание/повтор | Да | Нет (одноразовый вызов) |
| Параллельный запуск нескольких задач | Ограниченно | До 3 одновременно (max_concurrent_children) |

## Паттерн: cronjob для самодостаточной задачи (когда сессия может закрыться)

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

## Паттерн: delegate_task для параллельной/диалоговой работы

Модель для delegate_task пина через `config.yaml` (поля в самом вызове delegate_task нет):

```yaml
delegation:
  model: claude-opus-4-7   # временный пин, если нужен именно Opus для конкретного вызова
  provider: anthropic
  reasoning_effort: high
  child_timeout_seconds: 0   # без лимита — текущий дефолт
```

Не забыть откатить `delegation.model` обратно на `claude-sonnet-5` после точечного пина — иначе последующие delegate_task-вызовы в сессии тоже улетят на Opus.

## Минусы cronjob (по-прежнему актуальны)

1. **Нет контекста разговора** — cronjob запускается в чистой сессии, всё нужно писать в prompt явно.
2. **Нет обратной связи в процессе** — если Opus наткнулся на проблему, он не может спросить.
3. **Задержка старта** — минимум 1 минута (минимальное значение schedule).
4. **Нельзя остановить плавно** — только `cronjob(action='remove', job_id=...)`.

## Минусы delegate_task

1. **Не durable** — если сессия закрыта (`/new`) или процесс упал до завершения, работа субагента теряется.
2. **Модель нельзя выбрать per-call** — только через глобальный пин в config.yaml (действует на все параллельные delegate_task в сессии).
3. **Нет расписания/повтора** — разовый запуск, не для периодических задач.

## Конфигурация delegation в config.yaml (текущее состояние, 13.07.2026)

```yaml
delegation:
  model: claude-sonnet-5
  provider: anthropic
  reasoning_effort: medium
  max_iterations: 50
  child_timeout_seconds: 0   # без лимита, апстрим-дефолт
  max_concurrent_children: 3
  max_spawn_depth: 1
```
