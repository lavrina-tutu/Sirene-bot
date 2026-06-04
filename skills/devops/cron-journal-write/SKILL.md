---
name: cron-journal-write
description: "Записать итог крон-задачи в ~/.hermes/cron-journal.md. Загружать в конце каждого Opus-крона."
triggers:
  - "завершение крон-задачи"
  - "записать в журнал"
---

# Cron Journal Write

## Назначение
Этот скилл загружается в **конце каждого крон-задания** и инструктирует агента записать краткий итог в общий журнал, который Сирень видит при старте каждой сессии.

## Обязательный финальный шаг (выполнить ДО финального ответа)

После завершения основной задачи — дозапиши одну строку в `~/.hermes/cron-journal.md`:

```python
from pathlib import Path
from datetime import datetime

journal = Path.home() / ".hermes" / "cron-journal.md"
now = datetime.now().strftime("%Y-%m-%d %H:%M")
status = "OK"  # или "PROBLEM" если были ошибки
tl_dr = "краткое описание результата (1 строка)"
job_name = "имя задачи"
output_path = "~/.hermes/cron/output/<job_id>/<файл>.md"

line = f"- {now} | {job_name} | {status} | {tl_dr} | output: {output_path}\n"

# Читаем текущий файл
content = journal.read_text(encoding="utf-8") if journal.exists() else ""

# Добавляем строку после заголовка (первые 5 строк — шапка)
lines = content.splitlines(keepends=True)
header_end = 5  # строки 0-4 это шапка
body = lines[header_end:]

# Ротация: оставляем последние 49 + новая = 50
body = body[-49:] if len(body) >= 49 else body
body.append(line)

new_content = "".join(lines[:header_end]) + "".join(body)
journal.write_text(new_content, encoding="utf-8")
```

Предпочтительный способ — запустить готовый скрипт из этого скилла:
```bash
python3 ~/.hermes/skills/devops/cron-journal-write/scripts/write_journal.py \
  --job "имя задачи" --status OK --tl-dr "краткий итог" --output "путь к output"
```
Или inline через `python3 -c "..."` если скрипт недоступен.

## Правила
- `status = "OK"` если задача выполнена без критических ошибок
- `status = "PROBLEM"` если были ошибки, частичное выполнение, или что-то требует внимания Саши
- `tl_dr` — одна строка, максимум 80 символов, по-русски
- Не падать если журнал недоступен — `try/except pass`
- Выполнять **после** основной задачи, не вместо неё

## Подтверждено работает (03.06.2026)
- Скрипт `scripts/write_journal.py` — протестирован, запись появляется в журнале
- `vm_selfcheck` и `vm_dialogbacklog` подключены через `skills=["cron-journal-write"]`
- Журнал автозагружается в каждую сессию через `~/.hermes/hermes.md`

## Ложные тревоги self-check — НЕ считать проблемами
При проверке VM следующее является **нормой**, не ошибкой:
- Отсутствие `.venv` в `DialogBacklog/` — скрипты используют только stdlib
- Отсутствие `hermes-cron.service` — кроны идут через `hermes-gateway.service`
- Windows-пути в legacy-коде — фиксируются по мере обнаружения
