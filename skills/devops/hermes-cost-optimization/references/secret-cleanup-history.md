> Historical source, 2026; preserved as recorded, not current instructions. Verify against the current entrypoint and implementation.

Do not execute this historical recipe without a separately authorized procedure.

## 6. Security Alongside Cost Config

Apply together with cost changes:
```bash
hermes config set security.redact_secrets true   # hide API keys from logs/context
```

---

## Очистка секретов из state.db

Если секрет (пароль, токен) засветился в сессии — он попадает в `state.db` и FTS-индекс. Процедура очистки:

```python
import sqlite3
db = '/home/tkachenkoav/.local/share/hermes/state.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

# Заменяем в messages
for col in ['content', 'tool_calls']:
    cur.execute(f"SELECT rowid, {col} FROM messages WHERE {col} LIKE ?", ('%SECRET%',))
    for rowid, val in cur.fetchall():
        cur.execute(f"UPDATE messages SET {col}=? WHERE rowid=?",
                    (val.replace('SECRET', '[REDACTED]'), rowid))

conn.commit()

# Перестраиваем FTS-индексы
cur.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
cur.execute("INSERT INTO messages_fts_trigram(messages_fts_trigram) VALUES('rebuild')")
conn.commit()
conn.close()
```

**Также чистить:** `logs/agent.log`, `logs/gateway.log` — через Python `str.replace()` (sed не работает на активных файлах Windows).

**Остаток после чистки:** grep-команды поиска секрета в tool_calls — безопасно, содержат паттерн поиска, не сам секрет.

---



