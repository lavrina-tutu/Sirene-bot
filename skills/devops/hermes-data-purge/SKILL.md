---
name: hermes-data-purge
description: "Use when удалить персональные сессии из живого state.db."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pii, data-reduction, state-db, purge, handover, backup]
    related_skills: [pii-protection, hermes-memory-hygiene]
---

# Hermes Data Purge — вычитка персональных данных из живого state.db

## When to Use

Запускать, когда Саша просит удалить персональные/пользовательские диалоги из Hermes перед передачей инстанса другому человеку или при чистке ПДн («передаём инстанс», «чистка персональных данных», «чтобы новый человек не смог найти по истории»). Работает с живой БД `~/.hermes/state.db`, требует явный императив «удаляй» до необратимых действий. Связанный ТЗ-проект: `data-redaction-hermes`.

Адресное удаление пользовательских (интерактивных) сессий Саши из живой БД `~/.hermes/state.db` с сохранением работоспособности Hermes и без возможности «глубоко найти» старое через полнотекстовый поиск.

Это операция УДАЛЕНИЯ из живой БД. Она требует явного императива Саши («удаляй»). Сначала backup, затем согласовать точный объём (какие сессии=удаляем), затем выполнить. Никогда не удалять текущую активную сессию посреди работы — её обрабатывают последним отдельным шагом.

## Процедура

### 0. Классифицировать объём (до удаления)

state.db — единая БД ВСЕХ сессий (не разделена на интерактивные/cron). Классификация по `source`, `user_id` **и `chat_type`**:

- **Интерактивные с Сашей (личные ДМ)** = `source='telegram' AND user_id='400307920' AND chat_type='dm'` (или его telegram-id). Это ТО что удаляем. **Обязательно фильтровать `chat_type='dm'`** — без него тот же предикат поймает сессии групповых ТОПИКОВ «Сирень Workspace» (и любых других групп), где Саша пишет под своим telegram-id: purge снеся все топики (General, Tools, WorkVault, Backlog, Monitoring, Messages, Errors), а gateway-маршруты топиков после этого молча ломаются. Групповые/thread сессии (`chat_type='group'|'thread'`, `chat_id!=-'400307920'`) — НЕ персональные ДМ, их не трогать, даже если `user_id` совпадает.
- **Служебные — НЕ трогать**: `cron`, `kanban`, `subagent`, `weixin`, `webhook`, `desktop`, `oneshot`, `tui`.
- Исключить **текущую активную сессию** (id берётся из контекста) — обработать последним шагом.
- **Не строить классификацию только по целевому `user_id`** — у старых интерактивных ДМ бывают чужие/легаси `user_id` (напр. `u1`, `user-1` — исторические тест/альтернативные идентификаторы, сотни DM-сессий за старый период). Вычислить `SELECT user_id, chat_type, count(*) FROM sessions WHERE source='telegram' GROUP BY user_id, chat_type` и предъявить Саше всё, кроме очевидно служебного, как отдельное решение. Иначе после «основного» purge в живом останется второй пласт персонального контента.

```python
import sqlite3
con=sqlite3.connect('/home/tkachenkoav/.hermes/state.db')
cur=con.cursor()
cur.execute("SELECT source,count(*) FROM sessions GROUP BY source")  # посмотреть раскладку
cur.execute("SELECT source,chat_type,count(*) FROM sessions WHERE user_id='400307920' GROUP BY chat_type")  # ДМ vs групповые топики
cur.execute("SELECT count(*) FROM sessions WHERE user_id='400307920' AND source='telegram' AND chat_type='dm'")  # только личные
```

### 1. Backup ОБЯЗАТЕЛЕН (перед любым удалением)

`sqlite3` CLI может отсутствовать в PATH — используйте Python-модуль `sqlite3`. Снапшот через **SQLite backup API**, а не `cp` живого файла (согласованный снимок, не рваная копия):

```python
import sqlite3
src=sqlite3.connect('/home/tkachenkoav/.hermes/state.db')
dst=sqlite3.connect('/home/tkachenkoav/_backup_<date>/state.db.backup')
with dst: src.backup(dst)
```

Папку бэкапа создать на ВМ отдельной (потом удалить её вместе с прочими архивами). Проверить целостность: прочитать счётчики `sessions`/`messages` из `.backup` и сравнить с живыми — должны совпасть до удаления.

### 2. Схема и триггер-гард (критично)

Таблицы: `sessions(id, source, user_id, ...)`, `messages(session_id → sessions.id, content, ...)`, `session_model_usage`, `session_admissions(target_session_id)`, `worker_executions(session_id)`, `system_prompts`, `gateway_routing`, `async_delegations`, `session_turn_leases`, `conversation_generations`, `worker_receipts`, `hosted_room_*`.

**Гард-триггер `sessions_runtime_ledger_delete_guard`** не даёт удалить сессию, на которую ссылаются `session_admissions.target_session_id` ИЛИ `worker_executions.session_id`. Удаление такой сессии падает с `sqlite3.IntegrityError` (текст про «gateway runtime history»). Обход — **сначала удалить ссылки** из этих двух таблиц в той же транзакции.

**Колонка в `session_admissions` — `target_session_id`, НЕ `session_id`.** Писать в цикле по колонкам и таблицам условием `PRAGMA table_info(<t>)` — только те таблицы, где реально есть session-колонка; иначе словить `no such column`.

### 3. Транзакция удаления

```python
# TEMP-таблица с целевыми id (cur.execute два отдельных statement — нельзя ';' в одном execute)
cur.execute("CREATE TEMP TABLE IF NOT EXISTS del_ids(id TEXT PRIMARY KEY)")
cur.execute("DELETE FROM del_ids")
cur.executemany("INSERT INTO del_ids VALUES(?)", [(i,) for i in ids])

cur.execute("DELETE FROM messages WHERE session_id IN (SELECT id FROM del_ids)")
cur.execute("DELETE FROM session_model_usage WHERE session_id IN (SELECT id FROM del_ids)")
cur.execute("DELETE FROM session_admissions WHERE target_session_id IN (SELECT id FROM del_ids)")
cur.execute("... worker_executions ... другие связанные таблицы с реальной session-колонкой ...")
cur.execute("DELETE FROM sessions WHERE id IN (SELECT id FROM del_ids)")  # последней, после ссылок
# самоссылка на удалённого предка — висячий FK, почистить той же транзакцией:
cur.execute("UPDATE sessions SET parent_session_id=NULL WHERE parent_session_id IS NOT NULL AND parent_session_id NOT IN (SELECT id FROM sessions)")
con.commit()  # в конце; до commit любая ошибка = полный rollback
```

`execute()` допускает **ОДИН statement за раз** — разделить `CREATE...; DELETE...` на два вызова, иначе `ProgrammingError: only one statement at a time`.

### 4. FTS — «чтобы нельзя было найти глубоко»

`messages_fts` и `messages_fts_trigram` (FTS5) **поддерживаются триггерами на `messages` INSERT/DELETE/UPDATE** — при удалении сообщений FTS чистится автоматически, ничего руками не трогать.

НЕ выполнять ручной `DELETE FROM messages_fts` + `'rebuild'`: `rebuild` работает только для external-content FTS, для этой (inline) оставляет индекс **пустым** (verify: `messages_fts` = 2–4 строки при тысячах сообщений). Если уже очистил — восстановить через триггерное выражение:

```python
con.execute("INSERT INTO messages_fts(rowid, content) SELECT m.id, (выражение из messages_fts_insert) FROM messages m")
```

### 5. Проверка (обязательно после COMMIT)

- `SELECT count(*) FROM sessions/messages` — уменьшились на ожидаемое.
- Текущая сессия жива (`count WHERE id='<cur>'` == 1).
- Осталось только служебное + текущая по телеграму.
- FTS: `integrity-check` чист; убедиться, что старые фрагменты не находятся через `MATCH`.
- `PRAGMA foreign_key_check` — после большого purge показать возможные висячие самоссылки; если родители удалены, почистить `parent_session_id` (лучше в той же транзакции, смотри §3).
- Hermes отвечает (агент жив) — Gateway не упал.

## Питфоллы

- **Удалить текущую активную сессию посреди работы** → агент обрывает сам себя. Всегда исключать её из первого прохода, обрабатывать отдельным финальным шагом.
- **НЕ фильтровать `chat_type='dm'`** → purge удаляет сессии групповых топиков по совпавшему `user_id` и ломает их gateway-маршруты (входящие приходят в поллинг, но не дают ответа). Классифицировать только личные ДМ `source='telegram' AND user_id=<id> AND chat_type='dm'`; групповые/thread-сессии не трогать.
- **После большого purge топик может замолчать из-за lock во время транзакции** → большой purge/бэкап держит write-lock state.db >20s, и `gateway.session: single-entry routing save failed ... (database is locked)` роняет маршрут топика (у одного «полуживого» топика). Свежее входящее сообщение в топик пересоздаёт сессию и маршрут (работает для большинства); если ответа нет после этого — маршрут битый, нужен адресный ремонт/рестарт gateway.
- **Топик молчит, в `gateway.log` — `session_authority: Session ... paused: unknown_execution`, а flush виден** → НЕ пересоздание сообщением: прерванный purge оставил в `session_admissions` строку `status='unknown'` (admission оборонная mid-flight) и/или протухший `session_turn_leases` на ту же сессию. `session_authority` держит сессию paused, новые входящие тихо падают в `queued` и не выполняются (`inbound`/`response` в логе отсутствуют). Ремонт (по разрешению, сперва бэкап строк `CREATE TABLE _bak... AS SELECT * FROM session_admissions`): `UPDATE session_admissions SET status='terminal', outcome='completed' WHERE target_session_id='<sid>' AND status='unknown'`; её `queued`-хвосты той же сессии → `status='terminal', outcome='dropped'`; `DELETE FROM session_turn_leases WHERE conversation_id='<sid>' AND expires_at < now` (только протухший, не трогать свежий lease текущей DM). Другие сессии не трогать. Если после этого топик всё ещё молчит — authority закэшировал паузу в памяти процесса, нужен рестарт gateway.
- **После большого purge `PRAGMA foreign_key_check` выводит `('sessions', N, 'sessions', 0)`** → это самоссылки `parent_session_id` оставшихся сессий на удалённых предков (робкое, не ломает работу, но работа Hermes их не создаёт и они «оживают» при каждом следующем purge). Правило: `UPDATE sessions SET parent_session_id=NULL WHERE parent_session_id NOT IN (SELECT id FROM sessions)` выполнять в той же транзакции после удаления сессий, а не оставлять хвост на потом.
- **Пропустить backup** → необратимо. Backup-first, проверка целостности до удаления.
- **`session_admissions` использовать как `session_id`** → `no such column`; колонка называется `target_session_id`. Ошибка в начале цикла = не удалили адмиссии → гард-триггер блокирует удаление сессий и вся транзакция откатывается (это хорошо — целостность сохранилась).
- **Пустой или ручной FTS после `'rebuild'`** → `rebuild` на inline-FTS не заполняет индекс; полагаться на триггеры messages или восстановить через выражение триггера INSERT.
- **`cp` живого state.db вместо backup API** → снапшот рваный. Использовать `src.backup(dst)`.
- **Один-два-разовые удаления файлов широким `find -delete` по дереву блокируются hardline-guardом** (мой широкий `find . -xdev ... -delete` в `~/WorkVault/Hermes-Backlog/dev` вернул `BLOCKED: recursive/any delete of the Python interpreter`). Это не «нельзя удалять» — это приглашение удалять адресно: `find` выдать как список, проверить, потом `rm -v <явные пути...>` по перечисленным строкам. То же логично для любых `.bak-*`/`*.tgz`: сначала `ls`/`find` (увидеть состав), затем точечный `rm`.
- **Прибольшом удалении архивов искать по полному маске, а не одному суффиксу** — `kanban.db.bak_tzpatch_invertedfix` (с `_`) не поймал glob `kanban.db.bak-*`; аналогично `reconcile.py.bak-*` остался после `events.db.bak-*`. После каждой партии делать контрольный `ls`/`find`, чтобы словить не-попавшие копии (согласны `_`/`.`/другие суффиксы).
- **Один `execute()` с двумя statements через ';'** → `ProgrammingError`. Разбивать на отдельные вызовы.
- **Своим кодом подтверждать полную очистку** → нельзя обещать физического стирания: это логическая очистка доступных локальных хранилищ. Проверять по каждой локальной зоне, внешние копии вне scope (согласовано в ТЗ-проекте data-redaction-hermes).

## Удаление архивов и копий при передаче (помимо state.db)

Когда очистка шире, чем session-пласт (все бэкапы/архивы на ВМ перед передачей инстанса), порядок работы фиксирован предпочтением Саши:

1. **Каждое удаление предъявлять отдельно** — что именно удаляю, почему, что НЕ трогаю (живой активный файл/реестр отдельно), сколько это занимает. Дождаться явного «да» до `rm`.
2. **Порядок: от наименее опасных к наиболее опасным** для работы Hermes. Идти по группам (разбор по категориям и подсказки по риску — `references/archive-cleanup-order.md`): служебные `.bak` → во̆лбэки dev-workflow → ротационные `.curator_backups` → изолированные крупные копии → бэкап own purge последним (он единственная точка отката, его удалять только после подтверждения, что остальная чистка ок).
3. После каждой партии — контрольный `ls`/`find` и счётчик живого оригинала (не тронут).

## WorkVault content (персональные данные ВНУТРИ живого vault)

Следующий scope после бэкапов — личная персоналка в живом `~/WorkVault/` (не бэкапы, а именно данные). Полные правила и подача — `references/workvault-content-redaction.md`. Ключевое: `Personal/` — целиком; `Inbox/`/`Outbox/` — ОПУСТОШИТЬ, папки оставить (иначе ломается скилл `workvault-outbox`); протоколы 1-1 удалять поимённо даже в проектных деревьях; контакты не трогать без явного решения Саши (их читает скилл `show-contacts`). Рецензию подавать пронумерованными блоками по порядку папок.

## Связанные материалы

- `pii-protection` — детекция/инциденты ПДн (дополняет, не дублирует удаление).
- ТЗ проекта очистки: `~/WorkVault/Hermes-Backlog/TZ/data-redaction-hermes/` (границы, AC-101 разрешение на необратимое удаление, Q-1..Q-5 решения Саши).
