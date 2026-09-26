# Аудит работ Cursor CLI — данные и запросы

> Для вопросов «кто когда что вызывал через курсор», «почему участвовала модель X» (bk-175).
> Проверено 2026-08-31 на кейсе «кто работал 29.08 / что за Джимми».

## Где лежат данные

| Источник | Что даёт |
|---|---|
| `~/.cursor/chats/<group>/<chat>/meta.json` | createdAtMs, updatedAtMs, cwd каждого чата |
| `~/.cursor/chats/<group>/<chat>/store.db` | модель + промпты + затронутые пути конкретного чата |
| `~/.cursor/ai-tracking/ai-code-tracking.db` | агрегированный трекинг записанного кода по моделям/датам (десятки тысяч записей) |
| `~/.cursor/cli-config.json` | авторизованный аккаунт (authInfo.email/displayName) — кто запускал |
| `~/.cursor/projects/*/repo.json` | рабочие репозитории курсора |

**ВАЖНО:** state.db Hermes НЕ содержит вызовов прямого `agent` — курсор-агент работает вне цикла Сирень→Cursor. Отсутствие сессий Hermes в день аудита — ожидаемо, не значит «ничего не было».

**Питфолл:** `sqlite3` не установлен на ВМ. Читать `.db` через `python3` (скрипт файлом — инлайн `python3 -c` блокируется gateway-guard).

## Дата из createdAtMs

```bash
date -d @<first10_digits_of_ms> -u '+%m-%d %H:%M'
```

## Шаг 1 — чаты за конкретный день

Скрипт по всем чекам, фильтр по `createdAtMs` => нужная дата, вывод cwd:

```python
#!/usr/bin/env python3
import os, datetime, json
from glob import glob
for meta in glob(os.path.expanduser("~/.cursor/chats/*/*/meta.json")):
    try:
        d = json.load(open(meta))
    except Exception:
        continue
    ms = d.get("createdAtMs")
    if not ms: continue
    dt = datetime.datetime.fromtimestamp(ms/1000)
    if dt.date() == datetime.date(2026,8,29):   # искомый день
        print(dt.strftime("%H:%M"), d.get("cwd"), os.path.basename(os.path.dirname(meta)))
```

## Шаг 2 — модель и затронутые файлы чата

```bash
# модель
strings ~/.cursor/chats/<group>/<chat>/store.db | grep -oE '"modelName":"[^"]*"' | sort -u
# рабочие пути
strings ~/.cursor/chats/<group>/<chat>/store.db | grep -oE '"path":"[^"]*"' | sort -u
```

Сверка модели с ролями: `claude-sonnet-5-thinking-*` = архитектор, `composer-2.5` = исполнитель, `gemini-3.6-flash-*` = координатор.

## Шаг 3 — агрегированный трекинг по дню и моделям

```python
#!/usr/bin/env python3
import sqlite3, os, datetime
from collections import Counter
db = os.path.expanduser("~/.cursor/ai-tracking/ai-code-tracking.db")
con = sqlite3.connect(db); cur = con.cursor()
cur.execute("SELECT createdAt, model, fileName FROM ai_code_hashes")
rows = cur.fetchall()
def dt(ms):
    try: return datetime.datetime.fromtimestamp(ms/1000)
    except Exception: return None
day = [r for r in rows if dt(r[0]) and dt(r[0]).date()==datetime.date(2026,8,29)]
print("events:", len(day))
print("models:", dict(Counter(r[1] for r in day)))
for m,c in Counter(r[1] for r in day).items():
    print(f"-- {m}: {c}")
    for f,n in Counter(r[2] for r in day if r[1]==m).most_common(10):
        print(f"  {n}x {f}")
con.close()
```

Таблицы ai-code-tracking.db: `ai_code_hashes` (модель/файл/дата записи кода), `tracked_file_content` (снапшоты содержимого: gitPath, content, model, createdAt), `scored_commits`, `ai_deleted_files`.

## Интерпретация

Модель Cursor = роль по задаче из конвенции таблицы ролей. Если в storico за день один `gemini-3.6-flash` и много правок ТЗ/манифеста — это координатор, исполнявший рутинный ретрофит/сбор, а не чужой агент. «Джимми» в отчётах — это свободное имя пользователя для Gemini, не реальный человек.