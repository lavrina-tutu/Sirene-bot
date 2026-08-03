# Восстановление one-shot cron задачи

**Проблема:** Задача `repeat: "once"` была запланирована на конкретное время, но не выполнилась (gateway был перезапущен, занят или недоступен). `last_run_at: null`, `next_run_at: null`, папки output нет.

---

## Диагностика

```python
# Признаки пропущенной one-shot задачи:
# - last_run_at: null
# - last_status: null  
# - next_run_at: null
# - schedule: "once at YYYY-MM-DD HH:MM" (время в прошлом)
# - output folder отсутствует: ~/.hermes/profiles/anthropic/cron/output/<job_id>/
```

**Проверка через `cronjob(action='list')`:** если задача показывает все три null — она не выполнилась.

---

## Восстановление

```
cronjob(action='run', job_id='<job_id>')
```

**Важно:** после `run` one-shot задача **выполняется и исчезает из списка** — это норма. `last_run_at` не обновляется в списке потому что задача удаляется.

**Где найти результат:**
```bash
ls ~/.hermes/profiles/anthropic/cron/output/<job_id>/
# файл: YYYY-MM-DD_HH-MM-SS.md
cat ~/.hermes/profiles/anthropic/cron/output/<job_id>/YYYY-MM-DD_HH-MM-SS.md
```

Результат в файле начинается с `## Response` — это то что вернул агент.

---

## Доставка вручную

Если задача выполнилась но не доставилась в Telegram (deliver был указан в job, но сессия другая), вывод из файла можно прочитать и переслать вручную через `send_message`.

---

## Питфоллы

- **jobs.json структура:** это `{"jobs": [...], "updated_at": "..."}`, не массив напрямую. При парсинге Python: `data['jobs']`, поле `job_id` — ключ внутри каждого элемента.
- **После `run` job_id пропадает** — если нужно перезапустить снова, придётся создавать новую задачу через `cronjob(action='create')`.
- **Output папка создаётся только при реальном выполнении** — если папки нет, задача точно не запускалась.
- **tutu-contacts.md путь:** `WorkVault/Contacts/` (заглавная C), команда `zip -j` не принимает путь с `~/` напрямую в сочетании с `-j`, использовать абсолютный путь или сменить `cd`.

---

## Питфолл: неверный chat_id в deliver → Chat not found

**Симптом:** крон-задачи выполняются (output папки есть, логи показывают завершение), но отчёты в Telegram не приходят. В gateway.log строки `telegram.error.BadRequest: Chat not found`.

**Причина:** при создании задачи через `cronjob(action='create')` был указан несуществующий `chat_id` в `deliver`. Например `-1002254762742` вместо правильного `-1004300127777`.

**Диагностика:**
```bash
# Ищем Chat not found в логах
grep -a 'Chat not found' ~/.hermes/profiles/anthropic/logs/gateway.log | head -5

# Смотрим deliver у всех задач
python3 -c "
import json
with open('/home/tkachenkoav/.hermes/profiles/anthropic/cron/jobs.json') as f:
    data = json.load(f)
for item in data['jobs']:
    print(item.get('name','')[:40], '->', item.get('deliver',''))
"
```

**Исправление:** `cronjob(action='update', job_id='<job_id>', deliver='telegram:-1004300127777:3')`

**Правило:** при создании крон-задач **всегда** использовать `"origin"` как deliver (доставляет в текущий чат/тред автоматически) — или проверять ID через `send_message(action='list')` перед указанием явного значения.

**Проверенные chat_id для Сирени Workspace:**
- Основная группа: `-1004300127777`
- Тред 3 (🛠Tools): `telegram:-1004300127777:3`
- Тред 7 (🔔Monitoring): `telegram:-1004300127777:7`
- Личный чат Саши: `400307920`

**Актуальный лог gateway:** `~/.hermes/profiles/anthropic/logs/gateway.log` (не `~/.hermes/logs/gateway.log` — тот устарел, последняя запись июнь 3).

---

## Контекст

Этот паттерн применялся 22.06.2026 при восстановлении задачи `tz-brief-round2-opus` (a8d51e4ace04) — one-shot Opus для фиксации решений брифа ВОП-1–9 по AggregateFromMeetings.
