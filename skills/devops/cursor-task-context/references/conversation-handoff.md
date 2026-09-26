# Сборка handoff-файла для Cursor из переписки за день

Команда Саши вида «отдай переписку за сегодня в курсор на доработку ТЗ» / «отдай
все кейсы в курсор архитектору». Сирень сама собирает самодостаточный промпт из
фактической переписки (агент/крон НЕ наследуют историю чата — промпт обязан быть
self-contained, см. pitfall в SKILL.md).

## 1. Найти релевантную сессию

session_search (discovery, sort=newest) → сессии за день. Отобрать по теме
(напр. `MeetingScheduler`, «встречи»). Учитывай, что одна повседневная сессия
может содержать и бытовые запросы, и dev-цепочку — вытаскивай из неё целиком.

## 2. Извлечь переписку из state.db (схема таблиц)

- БД: `~/.hermes/state.db`, таблицы `sessions`/`messages`.
- Схема `messages` (важно — НЕ `created_at`, а `timestamp REAL`):
  `id, session_id, role, content, tool_call_id, tool_calls, tool_name,
   timestamp, ...`
- **Схема `sessions` (актуализировано 04.09):** у `sessions` НЕТ `created_at`.
  Поле времени — `started_at` (REAL, epoch). Для поиска сессии за день — колонки
  `started_at, title, source, chat_type, thread_id`. Крон-сессии имеют
  `id` с префиксом `cron_<jobid>_` и `chat_type=None`; по `title` типа
  `pfs_batch · …` их отсекать — брать только живые `chat_type='group'`.
- Читать ТОЛЬКО через `python3 /tmp/x.py` файлом, НЕ инлайн `python3 -c`
  (gateway-guard блокирует инлайн; см. cursor-cli). `sqlite3`-CLI на ВМ НЕ
  установлен — всегда через `python3`.
- Строки таблицы отдаются кортежами — индексируй по позиции `r[0]..r[3]`,
  а не по имени колонки (row_factory не задан по умолчанию).

```python
import sqlite3, datetime
con = sqlite3.connect('/home/tkachenkoav/.hermes/state.db')
cur = con.cursor()
sid = '<session_id>'
rows = cur.execute(
    'SELECT id, role, timestamp, content FROM messages '
    'WHERE session_id=? AND role IN ("user","assistant") ORDER BY id',
    (sid,)).fetchall()
out = []
for r in rows:
    ts = datetime.datetime.fromtimestamp(r[2]).strftime('%m-%d %H:%M')
    c = (r[3] or '').strip()
    if '[IMPORTANT: Background process' in c:   # отсечь системный шум крон/фона
        continue
    if not c:
        continue
    out.append(f'[{ts}] {r[1]}:\n{c}\n')
open('/tmp/<tool>-conversation.md','w').write('\n'.join(out))
```

## 3. Что отфильтровать / учесть

- **Отсечь** `[IMPORTANT: Background process ...]` — это системные уведомления о
  фоновых процессах (exit code фона), шум для архитектора.
- **Пропускать пустые** assistant-сообщения (прерванные/без контента).
- Источник требований — в основном **user-сообщения** (решения Саши) и его
  подтверждения («да», «супер», «не верно», правки). Assistant-сообщения дают
  контекст и уже зафиксированные формулировки — включать тоже.
- Сохранять `session_id` — может понадобиться для `--resume`.

## 4. Собрать handoff-промпт (два файла, без инлайна)

1. `/tmp/<tool>-architect.md` — бриф: роль/модель, git-контекст (путь к master-ТЗ),
   digest экосистемы (`~/WorkVault/Registries/EcosystemManifest.digest.md`),
   раздел «Что зафиксировать в ТЗ» по пунктам из переписки, формат работы,
   ограничения (не реализуешь код, правишь master-ТЗ файлом, чеклист готовности,
   НЕ задаёшь вопросы Саше — ты в автономном прогоне).
2. Склеить единый промпт: бриф + разделитель + полная переписка:
   ```bash
   cat > /tmp/<tool>-handoff.md < <(cat /tmp/<tool>-architect.md; \
     echo "=== ПЕРЕПИСКА ==="; cat /tmp/<tool>-conversation.md)
   ```
3. Запустить архитектора фоном через Cur o CLI:
   ```bash
   cd ~/WorkVault/Hermes-Backlog/TZ && \
     agent -p "$(cat /tmp/<tool>-handoff.md)" -f \
       --model cursor-grok-4.6-high --output-format json
   ```
   в `terminal(background=true, notify_on_complete=true)` + сообщить Саше
   модель/процесс/что ждём «дай знак — позадаю вопросы».

## Pitfall — архитектор, записывающий правки в master-ТЗ

Когда промпт велит архитектору САМОМУ вносить правки в `TZ/<Tool>/<Tool>_TZ.md`
(«внеси изменения непосредственно в master-файл»), НЕ верь self-report «записал»:
верифицируй на диске сам (wc -c / grep новых секций / поиск поднятой версии в
frontmatter). Содержательный текст пишет архитектор, но факт правки подтверждает
Сирень. См. pitfall про self-report в cursor-cli.

## Проверено

2026-09-01, MeetingScheduler_TZ.md (v1.8 → доработка). Переписка из сессии
`20260901_105329_b60b5482`: 165 сообщений (после фильтра фона/пустых) → 101 КБ
файл → handoff 110 КБ → архитектор cursor-grok-4.6-high запущен фоном.
