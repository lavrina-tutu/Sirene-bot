---
type: appendix
tool: CaseCollector
title: Драфт ТЗ скилла case-collector (TZ:patch)
version: 0.1.0-draft
date: 2026-09-11
status: draft
phase: TZ:patch
case: SKILL-DEV
author: архитектор (cursor-grok-4.6-high)
brief_closed: 2026-09-11
source: канбан-корень DEV/case-collector
not_master: true
---

# CaseCollector — драфт ТЗ скилла `case-collector`

**Это приложение-драфт, не master-ТЗ.** Master-файл `CaseCollector_TZ.md` и запись в `MAIN_TZ_INVENTORY.md` — только на фазе `TZ:finalize`. Код скилла в этой фазе не пишется. Реализация — после «берём в работу».

Бриф закрыт 11.09.2026. Вопросы Саше в этой фазе не задаются: семантические развилки зафиксированы в §11 как допущения с рекомендацией.

Разведка Linux-инстанса (`~/.hermes/state.db`, только `SELECT`, `mode=ro`, 11.09.2026): 4605 сессий, 105185 сообщений, размер БД ≈ 1.68 ГБ. Схема `sessions`/`messages` совпала с брифом Сирень.

---

## 0. Решения брифа (final, не переоткрывать)

1. Кейсы — **по смыслу** (смена предмета задачи в диалоге), **не** по 24-часовой границе сессии.
2. Выход — таблица **пользователь × тема × период** (дата-время начала и завершения).
3. Источник — `state.db` таблицы `sessions`/`messages`, **только read-only**.
4. Переносимость: путь к БД/логам параметризуется. Windows-адаптацию делает принимающий агент.
5. Маппинг на Jira **не входит** (ручной шаг Саши с таблицей).
6. Режим запуска — интерактивный скилл по запросу Саши, **не крон**.
7. Интерфейс LLM-вызова абстрагировать, модель не хардкодить.
8. Reuse-first: нового инструмента в реестре нет. `MoveFromJira` — не пересечение.

---

## 1. Цель

По запросу Саши прочитать логи сессий Hermes (`state.db`, только чтение) за указанный период и собрать таблицу: какой пользователь какие смысловые задачи (кейсы) решал через LLM и в какие интервалы — чтобы Саша отдал список людям, а они вручную сопоставили строки с задачами Jira и поставили заключение «успешно / неуспешно».

---

## 2. Входы

### 2.1 Источник данных

Канон на Linux-инстансе разработки: `~/.hermes/state.db` (SQLite).

Читать **только** таблицы:

| Таблица | Зачем |
|---|---|
| `sessions` | отбор окна, идентичность (source/user_id/chat_id/thread_id/session_key/origin_json), границы сессии, `title` как подсказка, `message_count` |
| `messages` | текст и время реплик для семантического разбиения |

Остальные таблицы (`messages_fts*`, `session_model_usage`, `gateway_routing`, `system_prompts`, …) **не читать**. FTS не использовать.

Подключение: `sqlite3.connect("file:<path>?mode=ro", uri=True)` + `PRAGMA query_only=ON`. Без `immutable=1` (нужен доступ к WAL живой БД гейтвея). Без `INSERT`/`UPDATE`/`DELETE`/`WAL checkpoint`. `timeout` соединения ≥ 30 с. CLI `sqlite3` на ВМ может отсутствовать — доступ только через Python.

Параметр `--db` (обязателен к наличию, дефолт `Path.home() / ".hermes" / "state.db"`) — единственная привязка к пути. На Windows принимающий агент подставляет свой путь.

### 2.2 Фактически проверенная схема (Linux, 11.09.2026)

`sessions` (релевантные поля): `id TEXT PK`, `source TEXT`, `user_id TEXT`, `model TEXT`, `parent_session_id TEXT`, `started_at REAL`, `ended_at REAL`, `end_reason TEXT`, `message_count INTEGER`, `title TEXT`, `session_key TEXT`, `chat_id TEXT`, `chat_type TEXT`, `thread_id TEXT`, `display_name TEXT`, `origin_json TEXT`, `profile_name TEXT`, `last_activity_at REAL`, `archived INTEGER`.

`messages` (релевантные поля): `id INTEGER PK`, `session_id TEXT`, `role TEXT`, `content TEXT`, `tool_name TEXT`, `timestamp REAL`, `token_count INTEGER` (на Linux-выборке 3 дней часто `NULL`), `active INTEGER`, `compacted INTEGER`.

`origin_json` на Linux (telegram): ключи `platform, chat_id, chat_name, chat_type, user_id, user_name, thread_id, chat_topic, message_id`. На проверенной выборке `chat_topic` = `null`. `session_key` вида `agent:main:telegram:group:<chat_id>:<thread_id>`.

Индексы есть: `idx_sessions_started`, `idx_sessions_source`, `idx_sessions_session_key`, `idx_messages_session_id` / `idx_messages_session`. Отбор окна — по `sessions.started_at`, не полным сканом FTS.

На целевом Windows-инстансе схема **может отличаться** (Mattermost-топики). Скилл читает поля через слой доступа с явным списком колонок и деградирует, если колонки нет (см. §5, OQ-3).

### 2.3 Период

Обязательные параметры: `--since`, `--until` (ISO-8601, таймзона по умолчанию `Europe/Moscow` / `+03:00`).

Сессия попадает в окно, если `started_at` ∈ `[since, until)` **или** (допущение OQ-4) есть хотя бы одно user-сообщение с `timestamp` в окне. Рекомендация v1: **отбор по `started_at`**, плюс явное предупреждение в отчёте о сессиях, начатых до окна, но активных внутри него.

Для доказательного прогона на Linux: последние 3 дня. На 11.09.2026 факт:

| Срез | Сессий |
|---|---|
| все источники, 3 дня | 170 |
| без `cron`/`kanban`/`subagent` | 41 (все `telegram`) |
| из них без user-сообщений | 17 |
| пригодны к LLM-проходу | **24** |

Оценка брифа «3 дня ≈ 150 сессий» — ориентир **целевого** (Windows, много пользователей), не Linux-доказательства. Скилл обязан переживать оба масштаба (см. §8).

### 2.4 Фильтр источников

Параметры: `--exclude-sources` (дефолт `cron,kanban,subagent`), `--include-sources` (если задан — белый список, пересечение с exclude).

Дефолт исключает служебные прогоны: кроны, канбан-воркеры, субагенты. Их диалоги — не «пользователь решал задачу через LLM» в смысле брифа.

Прочие источники Linux-инстанса (`cli`, `tui`, `desktop`, `weixin`, `webhook`) в дефолтный exclude **не** входят; на 3-дневной выборке их не было. На Windows ожидается Mattermost-подобный `source` — имя **не выдумывать**, задаётся параметром/маппингом (OQ-3).

Дополнительно исключать (жёстко, не параметром):

- `archived = 1`;
- сессии без ни одного user-сообщения с непустым `content` и `active=1`;
- сообщения `role IN ('tool', 'session_meta')` — не подавать в LLM;
- `active=0` или `compacted=1` — не подавать как живой диалог (OQ-5).

### 2.5 Карта пользователей

Файл `--user-map` (YAML/JSON, опционален). Ключи (первый матч побеждает):

1. `session_key`
2. `source:chat_id:thread_id`
3. `thread_id` (если уникален в выборке)
4. `user_id`

Значение — отображаемое имя в колонке «пользователь».

Если карты нет: слой резолва §6.2. На Linux-доказательстве почти все живые сессии — один Telegram-аккаунт (`user_id=400307920`, `origin_json.user_name=Alex Tkachenko`), а «разные люди» целевого инстанса моделируются **топиками** (`thread_id`). Поэтому колонка «пользователь» на Linux-прогоне — это в первую очередь **топик/канал**, не ФИО из `user_id` (иначе вся таблица схлопнется в одну строку-человека). На Windows карта «Mattermost-топик → аналитик» — зона принимающего агента.

### 2.6 Параметры LLM

Не хардкодить slug модели. Резолв (первый заданный):

1. `--model`
2. env `CASE_COLLECTOR_LLM_MODEL`
3. `model.default` из `~/.hermes/config.yaml` (на Linux сейчас `deepseek/deepseek-v4-flash-0731`, provider `tutu`)
4. явный отказ: exit ≠ 0, «модель не задана»

Провайдер/база/ключ — через абстракцию §4.3, **не** копировать ключ в код скилла.

### 2.7 Прочие входы запуска

| Параметр | Дефолт | Зачем |
|---|---|---|
| `--output` | `~/WorkVault/Inbox/case-collector_<since>_<until>.xlsx` | артефакт; Inbox уже есть, новую сущность `Tools/CaseCollector/` не заводить без согласования |
| `--user-map` | нет | §2.5 |
| `--dry-run` | выкл | выгрузить инвентарь сессий без LLM |
| `--limit` | нет (для теста: 150) | потолок сессий на прогон |
| `--max-input-chars` | 12000 | чанк компакт-транскрипта |
| `--include-assistant-stubs` | выкл | в промпт — обрезки assistant ≤200 символов |
| `--concurrency` | 1 | параллельные LLM-вызовы; v1 рекомендует 1 |

Крон, watermark, запись в канбан — **не входы**.

---

## 3. Выход

### 3.1 Таблица для Саши

Одна строка = один смысловой кейс внутри одной сессии. Кросс-сессионное слияние одинаковых тем **в v1 нет** (OQ-6): если тема продолжилась в новой 24ч-сессии — две строки, Саша/пользователь склеит при разговоре.

**Обязательные колонки** (кириллица, без транслита — конвенция `spreadsheet-deliverables`):

| Колонка | Смысл |
|---|---|
| пользователь | резолв §6.2 |
| тема кейса | краткая формулировка предмета задачи (5–15 слов) |
| начало | дата-время начала работы над кейсом, ISO-8601 с оффсетом `+03:00` |
| конец | дата-время завершения (timestamp последней реплики кейса) |

**Колонки трассировки** (нужны, чтобы сверять разбиение; Саша может скрыть в Excel):

| Колонка | Смысл |
|---|---|
| session_id | `sessions.id` |
| source | `sessions.source` |
| chat_id | как в БД |
| thread_id | как в БД |
| session_title | `sessions.title` (может быть пустым) |
| confidence | `high` / `medium` / `low` от LLM |
| flags | служебное: `chunked`, `overlap`, `llm_retry`, `empty_skip` |
| start_msg_id / end_msg_id | границы по `messages.id` |

Лист 2 «Сессии» (инвентарь прогона): session_id, пользователь, source, started_at, message_count, user_msgs, user_chars, status (`ok` / `skipped_empty` / `llm_error` / `over_limit`). Чтобы отличать «кейсов нет» от «прогон упал».

### 3.2 Формат файла

- **Основной:** `.xlsx` через `openpyxl` по скиллу `spreadsheet-deliverables`: первая строка — заголовки, жирный + светлая заливка, ширина по контенту, каждое поле — своя колонка, кириллица как есть. Не CSV как основной артефакт: в ru-локали Excel CSV с `,` схлопывается в одну ячейку (прецедент ProxyCheckLinux, 27.08.2026).
- **Fallback:** `.csv` с разделителем `;`, UTF-8 с BOM (`utf-8-sig`), рядом с xlsx (`--output` меняет только stem), если `openpyxl` недоступен или запись xlsx упала. В отчёте в чат явно сказать, какой файл открывать.
- В чат **не** ретранслировать таблицу целиком — только путь, число строк, число пользователей, число ошибок.

Тела сообщений, tool_calls, system prompt в xlsx **не писать**.

### 3.3 Сообщения в чат после прогона

Кратко: период, `--db`, сколько сессий отобрано / пропущено / прогнано через LLM, сколько кейсов, путь к xlsx, оценка токенов/стоимости (если адаптер вернул usage), список `llm_error` id.

---

## 4. Семантическое разбиение сессии на кейсы

### 4.1 Принцип

Единица разбиения — **сессия** (`sessions.id`). Внутри неё LLM выделяет один или несколько кейсов по смене **предмета задачи**, а не по паузе и не по `ended_at`.

Одна сессия → ≥1 кейс (или 0, если рабочего предмета нет — строку в основной лист не писать, в инвентаре `skipped_empty` / `no_task`).

Смена кейса: пользователь явно переходит к другой задаче («теперь другое», новая Jira-ссылка как **другой** предмет, новая тема с нуля). Не смена: уточнения, «ок», «поправь», продолжение той же работы, бытовой шум внутри той же темы.

`sessions.title` — подсказка, не истина (на Linux часто пустой или автосгенерированный).

### 4.2 Компакт-транскрипт (что вообще давать LLM)

На сессию собрать упорядоченный список **user**-реплик (`role='user'`, `active=1`, `compacted=0`, непустой `content`), поля:

```
id, ts_iso, text
```

Шум вырезать до промпта:

- системные вставки `[IMPORTANT: Background process` (паттерн `conversation-handoff`);
- пустые / whitespace-only.

Опция `--include-assistant-stubs`: для каждой user-реплики — следующий assistant, обрезанный до 200 символов, без tool JSON. **По умолчанию выкл.** На Linux 3 дня user+assistant ≈ mean 27 к символов/сессия (p90 ≈ 55 к, max ≈ 130 к) против user-only mean ≈ 3.9 к (p90 ≈ 5.9 к, max ≈ 40 к). Tool-роли раздувают ещё сильнее (`messages.role='tool'` ≈ 40% всех сообщений инстанса) — в промпт **запрещены**.

`token_count` в `messages` на выборке часто `NULL` — оценку токенов брать как `len(text)/2.5` (смесь RU/EN, консервативно). Не вызывать tokenizer.

### 4.3 Абстракция LLM-вызова

Скилл **не** вызывает модель текущей сессии «как есть» (иначе Windows/Linux разъедутся и нельзя считать токены). Внутренний интерфейс:

```
complete(messages: list[{role, content}], *, timeout, max_tokens) -> LlmResult(text, usage?)
```

Адаптеры (реализация — HF, в ТЗ — контракт):

| Адаптер | Когда |
|---|---|
| `HermesCallLlmAdapter` | Linux: `agent.auxiliary_client.call_llm`, ленивый импорт, venv `~/hermes-agent/.venv`. Паттерн `hermes-tutu-gateway/references/call-llm-from-external-tool.md`. Брать **только** `message.content`, не `reasoning_details`. |
| `OpenAICompatAdapter` | переносимый: `base_url` + `api_key` из env (`CASE_COLLECTOR_LLM_BASE_URL` / `CASE_COLLECTOR_LLM_API_KEY`) либо из `custom_providers` в `config.yaml` по имени провайдера. Ключ в репозиторий скилла не класть. |

Выбор адаптера: `--llm-backend hermes|openai-compat|auto`. `auto`: есть `call_llm` → hermes, иначе openai-compat, иначе fail-loud.

Модель — аргумент адаптера, не константа класса. На Linux-доказательстве ожидаема `deepseek/deepseek-v4-flash-0731` через tutu; в коде slug не прошивать.

Запрещено: `agent -p` / Cursor CLI как движок разбиения (дорого, tools, журнал в ответе).

### 4.4 Промпт и JSON-контракт ответа

Системная инструкция (смысл, не финальный текст SKILL.md):

- Разбей диалог на смысловые рабочие кейсы.
- Новый кейс = смена предмета задачи, не смена времени.
- Тема — по-русски, 5–15 слов, без транслита, без кавычек-обёрток, без «пользователь просит…».
- Верни **только JSON**, без markdown-ограды.
- Границы — **id сообщений из входа**, не выдуманные даты.
- Если рабочей задачи нет — `"cases": []`.

Входной payload:

```json
{
  "session_id": "<id>",
  "timezone": "Europe/Moscow",
  "turns": [
    {"id": 123, "ts": "2026-09-10T16:06:54+03:00", "role": "user", "text": "..."}
  ]
}
```

Контракт ответа (`schema_version` = `1.0`):

```json
{
  "schema_version": "1.0",
  "session_id": "<id>",
  "cases": [
    {
      "topic": "настройка доступов к протоколам встреч",
      "start_msg_id": 123,
      "end_msg_id": 140,
      "confidence": "high"
    }
  ]
}
```

**Канонические `начало`/`конец` считает скрипт**, не LLM: min/max `messages.timestamp` среди user-реплик с `id` в `[start_msg_id, end_msg_id]` этой сессии. LLM плохо держит абсолютное время; доверять его ISO-полям нельзя (если пришлёт — игнорировать).

Валидация:

- JSON после strip fences / `json.loads`;
- `session_id` совпал;
- `start_msg_id`/`end_msg_id` существуют во входных turns, `start ≤ end`;
- `topic` непустой, длина ≤ 200 символов;
- `confidence` ∈ {high, medium, low} (иначе `medium`);
- один retry при битом JSON (в промпт — «верни только JSON по схеме»);
- после второго отказа — сессия в инвентаре `llm_error`, прогон **не** падает целиком.

Перекрытия кейсов: не удалять молча, обе строки в таблицу, `flags=overlap`.

### 4.5 Большие сессии (чанки)

Порог: длина компакт-транскрипта (символы user-текста) > `--max-input-chars` (дефолт 12000 ≈ 5 к токенов).

Алгоритм v1:

1. Резать по **user-репликам**, не по байтам середины сообщения.
2. Чанк ≈ 8000 символов, overlap = 2 последние user-реплики предыдущего чанка.
3. Каждый чанк — отдельный LLM-вызов, в payload поле `chunk: {i, n, overlap_ids}`.
4. Склейка: кейсы по порядку; если тема последнего кейса чанка i и первого кейса i+1 совпадает после нормализации (lowercase, схлопнуть пробелы) — слить в один (min start, max end), `flags=chunked`.
5. Не делать второй «merge-LLM» в v1 (дорого и без закрытого вопроса о качестве).

На Linux-выборке 3 дней user-only max ≈ 40 к символов → 4–5 чанков на худшую сессию; p90 укладывается в один вызов. Жёсткий лимит контекста flash (~1.3M) не проблема; режем ради качества и стоимости.

Батчинг нескольких **сессий** в один LLM-вызов в v1 **запрещён** (риск склеить чужие кейсы). Параллелизм — только `--concurrency` независимых сессий, дефолт 1.

### 4.6 Порядок прогона

```
1. SELECT sessions по окну и фильтрам
2. dry-run? → xlsx лист «Сессии», выход
3. для каждой сессии: компакт-транскрипт
4. LLM complete (чанк при необходимости)
5. валидация JSON → строки кейсов
6. резолв пользователя
7. запись xlsx (+ csv fallback)
8. отчёт в чат
```

Идемпотентность: каждый запуск перезаписывает `--output` (или пишет новый timestamped файл, если путь — директория). Watermark нет.

---

## 5. Переносимость (Linux → Windows)

Скилл разрабатывается и доказывается на Linux-инстансе Саши, затем **отдаётся** Windows-агенту. Windows-код в этом ТЗ не реализуется.

Точки адаптации (контракт для принимающего агента):

| Точка | Linux-дефолт | Что меняет Windows |
|---|---|---|
| `--db` | `~/.hermes/state.db` | свой путь к state.db / копии |
| `--llm-backend` | `auto` → hermes `call_llm` | скорее `openai-compat` + локальный gateway |
| `--model` | из config.yaml | своя основная модель, не flash-slug Linux |
| `--exclude-sources` / `--include-sources` | cron,kanban,subagent | фактические `source` Mattermost |
| `--user-map` | топик Telegram → ярлык | Mattermost-топик → ФИО аналитика |
| колонки identity | `chat_id`+`thread_id`+`session_key` | если имена колонок другие — тонкий `IdentityAdapter` |
| пути | `pathlib.Path` | без хардкода `/home/...` |
| xlsx | `openpyxl` | та же библиотека |

Не переносить: Linux-специфичные id чата `-1004300127777`, Telegram `user_id` Саши, пути WorkVault Inbox как единственно возможные (остаются дефолтом, перекрываются `--output`).

Доказательство на Linux считается успешным, если на коротком окне (3 дня) получается валидный xlsx с обязательными колонками и хотя бы несколькими строками кейсов. Качество имён тем на Windows-диалогах аналитиков — зона доводки принимающего агента (можно подкрутить промпт, не схему таблицы).

---

## 6. Детект пользователя (топик/чат → человек)

### 6.1 Факты Linux vs цель Windows

| | Linux (этот инстанс) | Windows (заказ) |
|---|---|---|
| Транспорт | Telegram, `chat_type=group`, топики `thread_id` ∈ {1,3,5,6,7,8,11112,6556,…} | Mattermost, отдельный топик на пользователя |
| `user_id` | почти всегда аккаунт Саши (`400307920` / `u1`) | может быть id аналитика **или** бота — неизвестно |
| `display_name` | имя чата «Сирень Workspace», не человек | неизвестно |
| `origin_json.user_name` | `Alex Tkachenko` | неизвестно |
| `origin_json.chat_topic` | `null` | **кандидат** на имя топика, если Windows-шлюз его пишет |

Вывод: `sessions.user_id` **нельзя** считать колонкой «пользователь» на целевом инстансе без проверки. Стабильный ключ идентичности v1: `session_key` если есть, иначе `source + chat_id + thread_id`.

### 6.2 Алгоритм резолва имени

```
mapped = user_map[session_key] or user_map[source:chat_id:thread_id]
      or user_map[thread_id] or user_map[user_id]
if mapped: return mapped
# fallback, без выдумывания ФИО:
if chat_topic in origin_json and nonempty: return chat_topic
return f"{source}:{chat_id}:{thread_id}"   # стабильный суррогат
```

`origin_json.user_name` / `display_name` **не** брать как дефолт на Linux-доказательстве: они дают одного человека / имя воркспейса и прячут топики. Их можно включить опцией `--prefer-origin-user-name` (для Windows, если там это ФИО аналитика) — OQ-2.

Карта `--user-map` в репозиторий скилла не коммитится (может содержать ФИО). Пример-схема — в `references/` без реальных id.

---

## 7. Привязка к Jira

**Не входит.** Скилл не вызывает Jira API, не читает `MoveFromJira` / `jira_snapshot.json`, не угадывает ключи вида `ABCD-123` как канон (если ключ встретился в теме — это просто текст темы). Колонок «jira» / «успешно» в v1 нет: их заполняют люди после выдачи таблицы.

Не добавлять пустые колонки «Jira» / «вердикт» «на вырост» (OQ-7: если Саша потом попросит — отдельная секция ТЗ).

---

## 8. Режим запуска и стоимость LLM-проходов

### 8.1 Режим

Интерактивный скилл по фразе Саши («собери кейсы», «выгрузи темы за 3 дня», «case-collector»). **Крон не ставить**, `jobs.json` не трогать, ErrorBus не подключать в v1 (ошибки — в чат + инвентарь).

Класс: on-demand analytical skill, как `loop-channel-digest`, не семейство `MoveFrom*`.

### 8.2 Оценка объёма и токенов

Замеры Linux, окно 3 дня, `source=telegram`, без cron/kanban/subagent, только `active` user-текст (11.09.2026):

| Метрика | Значение |
|---|---|
| сессий пригодных | 24 |
| user-реплик на сессию | p50=5, mean≈10, max=33 |
| символов user на сессию | p50≈1.8 к, mean≈3.9 к, p90≈5.9 к, max≈40 к |
| символов user+assistant | p50≈9.8 к, mean≈27 к, p90≈55 к, max≈130 к |
| `token_count` в БД | NULL — оценка `chars/2.5` |

Оценка **на 1 сессию** (рекомендуемый режим: только user, без assistant, без tool):

- вход: ~0.8–2.5 к токенов типичная, до ~16 к на выбросе + ~400 токенов системного промпта;
- выход JSON: ~150–600 токенов (1–N кейсов).

Оценка **прогона 150 сессий** (цифра брифа, Windows-масштаб; Linux-доказательство ≈ 24 вызова):

| Режим | Вход (порядок) | Выход | Вызовов |
|---|---|---|---|
| user-only, 1 сессия = 1 вызов | ~0.4–0.6 M ток. | ~0.03–0.09 M | 150 |
| user+assistant stubs | ~1.5–2.5 M | тот же выход | 150 |
| плюс tool-дампы | не закладывать | — | запрещено |

Каталог OpenRouter в кэше Hermes (не счёт ТУТУ): `deepseek/deepseek-v4-flash-0731` ≈ **$0.065 / 1M input**, **$0.18 / 1M output**. Прогон 150 сессий user-only на flash — **порядка $0.03–0.08**. Фактический биллинг ТУТУ может отличаться; это оценка порядка, не смета.

Итог: бюджет жжёт не flash×150, а (а) случайный прогон на Pro/reasoning-high, (б) протаскивание tool/assistant-простыней, (в) retry-шторм. Ограничения ниже — про это.

На Linux 3 дня собственные сессии агента стоили ≈ $12.4 `estimated_cost_usd` — это **стоимость исходных диалогов**, не стоимость case-collector.

### 8.3 Ограничения, чтобы не сжечь бюджет и время

1. Дефолтная модель — flash-класса из конфига инстанса, не Pro.
2. В промпт — только user (assistant stubs опционально, tools никогда).
3. `--limit` на доказательстве; без лимита — предупреждение если сессий > 200.
4. `--max-input-chars=12000` + чанки, не «весь диалог включая tools».
5. `--dry-run` обязателен в скилле как первый шаг отладки.
6. `--concurrency` дефолт 1; верх 3 (шлюз tutu).
7. Retry JSON ровно 1 раз на чанк.
8. Fail-loud если адаптер не сконфигурирован; не молча ходить на случайный endpoint.
9. Сводка usage в конце (если есть), чтобы Саша видел расход.

Латентность: 150 последовательных вызовов × 5–15 с ≈ 15–40 мин. Для интерактивного запроса приемлемо; в скилле предупредить. `--limit 20` для дымового прогона.

---

## 9. Что НЕ трогать

- `~/.hermes/state.db`: никакой записи, смены схемы, `VACUUM`, checkpoint, правок FTS. Даже «почистить секрет» — вне скоупа (это `hermes-cost-optimization` / ручная процедура).
- `MAIN_TZ_INVENTORY.md` и `CaseCollector_TZ.md` — не в фазе `TZ:patch`.
- Кроны / `~/.hermes/cron/jobs.json`. Gateway не рестартовать.
- Jira, Confluence, Loop API, `MoveFromJira`, карточки канбана.
- `PIIScan` / правило «не читать state.db»: исключение PIIScan **не** распространяется на этот скилл — ему **разрешено читать** state.db, но **не** писать. Не ослаблять запрет PIIScan.
- Не класть сырой текст диалогов в Inbox/xlsx/логи крона. Не коммитить `--user-map` с ФИО.
- Профили `tz-dev` / `anthropic` / `openai` (декомиссия 17.08) — не реанимировать.
- Чужие скиллы: не патчить `backlog-collector`, `backlog_fetch.py`, `hermes-cost-audit`, `loop-channel-digest` «заодно».
- Windows-инстанс и его БД — не трогаем с Linux.

---

## 10. Связи с экосистемой

### 10.1 Reuse-first (реестр 11.09.2026)

Нового инструмента «сбор кейсов из логов сессий» в `MAIN_TZ_INVENTORY.md` / `EcosystemManifest.digest.md` **нет**. Новая сущность скилла — обоснована. Отдельный USERTOOLS-пакет **не заводить в v1** (требует согласования Саши по reuse-first); код — `scripts/` внутри скилла, прецеденты `edit-plan-confluence`, `deep-mine-project`. Если объём + тесты вырастут за разумный skill-scripts порог — вынести в USERTOOLS отдельным решением, не молча.

Соседи, **не** поглощать и **не** пересекать по выходу:

| Сосед | Почему не он |
|---|---|
| `MoveFromJira` | тянет снимок проекта из Jira API в `jira_snapshot.json`; не читает логи сессий и не режет диалог по смыслу |
| `backlog-collector` / `DialogBacklog` | идеи Саши из telegram-диалогов → карточки `IDEA/*`; плоский поток `user+assistant`, без группировки по сессии/топику, `--topics` stub. Паттерн read-only sqlite **можно скопировать**, скрипт **не** переиспользовать как ядро |
| `hermes-cost-audit` | FinOps по `sessions` (токены/стоимость), не темы задач |
| `LoopChannelDigest` | дайджест постов Loop/Mattermost, не Hermes `state.db` |
| `PIIScan` | сознательно **не** открывает state.db |
| `cursor-task-context` / conversation-handoff | выгрузка одной сессии архитектору; не таблица по пользователям |

Инфраструктура, на которую **опираемся**:

- Hermes `state.db` (владелец — gateway);
- `call_llm` / tutu gateway (`hermes-tutu-gateway`);
- конвенция таблиц `spreadsheet-deliverables` + `openpyxl` (уже в экосистеме, ProxyCheckLinux);
- канон скилла: `~/hermes-workspace/skills/` + `restore-all-skills.sh` на `ORCH:shared-state` (после реализации, не сейчас).

Предлагаемое место скилла: `productivity/case-collector` (on-demand аналитика, рядом с `loop-channel-digest`). Платформы в манифесте скилла: `linux, macos, windows`.

После реализации (не эта фаза): регистрация в EcosystemManifest как `hermes_skill`, restore профилей. Кроны не создавать.

### 10.2 Контракты экосистемы

### Источник истины

- Живые сессии/сообщения: Hermes gateway, файл `state.db`. CaseCollector — **только читатель**.
- Выходная таблица: файл, который пишет CaseCollector; потребитель — человек (Саша), не другой инструмент.

### Входные контракты

| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| sessions.id | str | required | Hermes state.db | TEXT PK сессии |
| sessions.source | str | required | Hermes state.db | telegram/cron/kanban/subagent/… |
| sessions.started_at | datetime(iso8601) | required | Hermes state.db | REAL epoch → ISO+03:00 |
| sessions.chat_id | str | optional | Hermes state.db | id чата платформы |
| sessions.thread_id | str | optional | Hermes state.db | id топика |
| sessions.session_key | str | optional | Hermes state.db | `agent:main:<platform>:…` |
| sessions.origin_json | str | optional | Hermes state.db | JSON origin шлюза |
| messages.id | int | required | Hermes state.db | INTEGER PK |
| messages.session_id | str | required | Hermes state.db | FK на sessions.id |
| messages.role | enum[user,assistant,tool,session_meta] | required | Hermes state.db | в LLM только user (+опц. assistant stub) |
| messages.content | str | optional | Hermes state.db | текст реплики |
| messages.timestamp | datetime(iso8601) | required | Hermes state.db | REAL epoch → ISO+03:00 |
| messages.active | int | optional | Hermes state.db | 1=живое; 0 не подавать |
| user_map.entry | str | optional | файл --user-map (оператор) | ключ identity → отображаемое имя |

### Выходные контракты

| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| пользователь | str | Саша (xlsx) | имя из user-map или суррогат source:chat:thread |
| тема кейса | str | Саша (xlsx) | кириллица, 5–15 слов |
| начало | datetime(iso8601) | Саша (xlsx) | min timestamp реплик кейса, +03:00 |
| конец | datetime(iso8601) | Саша (xlsx) | max timestamp реплик кейса, +03:00 |
| session_id | str | Саша (трассировка) | sessions.id |
| schema_version | str | парсер ответа LLM | "1.0" в JSON разбиения |

### Зависимости

- Получает от: [Hermes state.db, операторский user-map, LLM через абстрактный клиент]
- Отдаёт: [файл xlsx/csv для Саши; не отдаёт другим USERTOOLS]

### Breaking changes policy

- Версионирование формата: `schema_version` в JSON ответа LLM и (при появлении машиночитаемого потребителя) в xlsx. Сейчас потребитель — человек, колонки v1 фиксированы §3.1.
- Breaking change колонок xlsx — новая секция master-ТЗ, не молчаливое переименование.

### Границы («что НЕ трогать»)

- Не писать в `state.db`.
- Не вызывать Jira.
- Не менять контракты `MoveFromJira` / DialogBacklog / PIIScan.

---

## 11. Открытые вопросы (зафиксированы как допущения)

Бриф закрыт, Сашу не спрашиваем. Каждое допущение — с рекомендацией; снять может только Саша на ревью драфта / `TZ:finalize`.

**OQ-1. Класс поставки: скилл+scripts vs USERTOOLS-пакет.**  
Допущение: v1 = Hermes-скилл `productivity/case-collector` + `scripts/` внутри скилла, без новой записи USERTOOLS. Новый пакет — только с явным согласованием Саши.  
Рекомендация: так и делать (как EditPlanConfluence / deep-mine).

**OQ-2. Что писать в колонку «пользователь» без `--user-map`.**  
Допущение: суррогат `source:chat_id:thread_id` или `origin_json.chat_topic`, если непустой. Не подставлять Linux `user_name=Alex Tkachenko` как дефолт. Опция `--prefer-origin-user-name` для Windows.  
Рекомендация: для Linux-доказательства завести локальный user-map thread_id → ярлык топика (не коммитить), чтобы таблица была читаемой.

**OQ-3. Имя `source` и набор колонок на Windows/Mattermost.**  
Допущение: неизвестно; скилл падает понятной ошибкой, если нет `sessions`/`messages` или нет `started_at`/`timestamp`, и пропускает отсутствующие optional-колонки.  
Рекомендация: принимающий агент заполняет `--include-sources` и IdentityAdapter по факту `PRAGMA table_info`.

**OQ-4. Сессия началась до окна, но реплики внутри окна.**  
Допущение v1: отбор только по `sessions.started_at`.  
Рекомендация: в отчёте печатать count «сессий с репликами в окне, но started_at вне» (read-only EXISTS), не тащить их молча. Если Саша потом скажет «бери по activity» — одна секция ТЗ.

**OQ-5. `compacted=1` / сжатые саммари.**  
Допущение: не подавать compacted-сообщения в LLM (это уже сжатый журнал, не живые реплики пользователя). Если после фильтра user-реплик не осталось — skip.  
Рекомендация: не восстанавливать кейсы из саммари в v1.

**OQ-6. Склейка одной темы across сессий (24ч TTL).**  
Допущение v1: **не склеивать**. Две сессии = минимум две строки, даже если тема похожа. Это сознательно: бриф требует период **смысловой части**, а кросс-сессионный merge — отдельная семантика и риск ложно склеить разных людей/топики.  
Рекомендация: оставить как есть; Саша при разговоре с аналитиком увидит две строки.

**OQ-7. Пустые колонки Jira / успешно.**  
Допущение: не добавлять.  
Рекомендация: не засорять таблицу. Если понадобится шаблон для заполнения людьми — отдельная доработка.

**OQ-8. Куда писать xlsx.**  
Допущение: `~/WorkVault/Inbox/case-collector_<since>_<until>.xlsx`, перекрывается `--output`. Папку `TZ/CaseCollector/` не использовать под артефакты. Новую `Tools/CaseCollector/` не создавать без согласования (новая сущность).  
Рекомендация: Inbox.

**OQ-9. Нужен ли ErrorBus.**  
Допущение: нет в v1.  
Рекомендация: интерактив + инвентарь листа 2 достаточно.

**OQ-10. Нужен ли merge-LLM после чанков.**  
Допущение: нет, только нормализация строки темы.  
Рекомендация: сначала посмотреть Linux-доказательство; если темы-дубли соседних чанков будут плохими — точечно добавить.

**OQ-11. Батч нескольких коротких сессий в один LLM-вызов.**  
Допущение: запрещён в v1.  
Рекомендация: 24–150 вызовов flash дешевле риска смешать кейсы.

**OQ-12. Таймзона вывода.**  
Допущение: `Europe/Moscow` (`+03:00`), независимо от TZ хоста Windows.  
Рекомендация: параметр `--tz` с этим дефолтом.

**OQ-13. Профиль `profile_name`.**  
Допущение: не фильтровать (на Linux основная масса `NULL` = default).  
Рекомендация: параметр `--profile` на потом, не в v1.

**OQ-14. PII в темах кейсов.**  
Допущение: тема может содержать ФИО/логины из диалога; это рабочий артефакт для Саши, не публиковать в общий чат и не класть в cron/output. Маскирование тем в v1 не делать (исказит смысл для получателей-аналитиков).  
Рекомендация: файл в Inbox, в Telegram — только путь и счётчики.

**OQ-15. Критерий «сессия с несколькими кейсами» на Linux-доказательстве.**  
Допущение: успех v1 не требует обязательно найти multi-case сессию (на 24 сессиях её может не быть). Успех = таблица по схеме + прогон read-only + исключение cron/kanban/subagent. Наличие multi-case — желательный, но не blocking, пункт приёмки; если ни одной — зафиксировать в отчёте прогона.  
Рекомендация: для проверки алгоритма иметь fixture-диалог с двумя предметами в тестах HF, не надеяться на живой Linux-трафик.

---

## 12. Место поставки и функциональные блоки (для поздней HF, не реализовывать сейчас)

Предлагаемая раскладка (не код):

```
~/hermes-workspace/skills/productivity/case-collector/
  SKILL.md                 # триггеры, параметры, запреты, путь к CLI
  scripts/case_collector.py
  scripts/db.py            # read-only sqlite
  scripts/transcript.py    # компакт-транскрипт + чанки
  scripts/split_llm.py     # промпт, JSON, адаптеры
  scripts/identity.py      # user-map + fallback
  scripts/xlsx_out.py      # openpyxl + csv fallback
  references/user-map.example.yaml
  references/split-prompt.md
```

CLI (черновик):

```
python3 scripts/case_collector.py \
  --since 2026-09-08 --until 2026-09-11 \
  [--db ~/.hermes/state.db] \
  [--exclude-sources cron,kanban,subagent] \
  [--user-map ./user-map.yaml] \
  [--model deepseek/deepseek-v4-flash-0731] \
  [--llm-backend auto] \
  [--output ~/WorkVault/Inbox/case-collector.xlsx] \
  [--dry-run] [--limit 150]
```

Блоки: (1) отбор сессий, (2) транскрипт, (3) LLM-split, (4) identity, (5) xlsx. Один скилл, два внутренних модуля extract/split — **не** два скилла (в отличие от backlog-collector/analyst: там разные продукты и разные потребители).

---

## 13. Критерии успеха v1 (проверяемые)

1. Прогон с `mode=ro` не меняет `mtime`/`size` `state.db` и не делает write-SQL.
2. На Linux за 3 дня создаётся xlsx с обязательными колонками §3.1; csv-fallback отрабатывает при недоступном openpyxl (тест можно на mock).
3. Сессии `source IN (cron, kanban, subagent)` отсутствуют в основном листе при дефолтных фильтрах.
4. Строки кейсов не содержат сырой `content` сообщений.
5. Модель берётся из `--model` / env / config, в исходниках нет захардкоженного slug.
6. `--db /tmp/nonexistent.db` → ненулевой exit и понятная ошибка, без записи куда-либо.
7. Битый JSON LLM на одной сессии не убивает прогон остальных.
8. Нет вызовов Jira/Loop/Exchange, нет записей в `jobs.json`.
9. `--dry-run` не вызывает LLM (можно проверить моком адаптера).

---

## 14. Атомарные шаги реализации (после «берём в работу», не сейчас)

1. Каркас скилла + CLI argparse + read-only `db.py` + dry-run инвентарь.
2. Компакт-транскрипт + фильтры ролей/active/compacted/шум.
3. JSON-контракт + фейковый адаптер (fixture) + чанки.
4. Боевые адаптеры `call_llm` / openai-compat, модель из конфига.
5. Identity + user-map.
6. xlsx + csv fallback по spreadsheet-deliverables.
7. Pytest: fixture sqlite (не живой state.db), overlap, chunk merge, exclude sources, no-write.
8. Ручной Linux-прогон 3 дня, отчёт Саше, затем пакет скилла Windows-агенту.
9. `ORCH:shared-state`: restore-all-skills, манифест — по канону hermes-feature, не в `TZ:patch`.

---

## 15. Граница фазы

Сделано: этот файл.  
Не сделано и **не делать** в `TZ:patch`: master `CaseCollector_TZ.md`, инвентарь, код, кроны, запись в БД.

Следующая фаза канбана: `REV:tz` (ревизор), затем `TZ:finalize` (архитектор пишет master + инвентарь) — по графу `TZ-WRITE`, без склейки в один `agent -p`.
