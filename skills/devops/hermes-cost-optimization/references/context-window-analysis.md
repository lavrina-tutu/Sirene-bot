# Context Window Analysis — Reference

## Задача
Узнать, сколько токенов занято в текущем контекстном окне и сколько осталось до лимита.

## Источники данных

### 1. state.db — история сессий
Файл: `~/.hermes/state.db`  
Таблица `sessions` — ключевые колонки:

| Колонка | Значение |
|---|---|
| `id` | ID сессии (например `20260626_095345_9fe0b346`) |
| `source` | платформа: `telegram`, `tui`, `cron`, … |
| `model` | модель (например `claude-sonnet-4-6`) |
| `input_tokens` | **новые** токены (не из кеша) |
| `cache_read_tokens` | токены прочитанные из Anthropic cache |
| `cache_write_tokens` | токены записанные в Anthropic cache |
| `output_tokens` | выходные токены |
| `api_call_count` | число API-вызовов за сессию |
| `estimated_cost_usd` | оценочная стоимость |
| `system_prompt` | текст системного промпта |

Таблица `messages` — ключевые колонки:

| Колонка | Значение |
|---|---|
| `session_id` | FK к sessions.id |
| `role` | `user`, `assistant`, `tool` |
| `content` | текст сообщения |
| `token_count` | токены сообщения (если заполнено) |
| `timestamp` | REAL (unix timestamp) |
| `active` | 1 = активное, 0 = сжатое/удалённое |
| `compacted` | 1 = было сжато компрессором |

### 2. Anthropic API — реальные лимиты моделей

```python
import anthropic
client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
for m in client.models.list().data:
    print(m.id, 'max_input:', m.max_input_tokens, 'max_output:', m.max_tokens)
```

### 3. count_tokens API — точная оценка

```python
result = client.messages.count_tokens(
    model='claude-sonnet-4-6',
    system=system_prompt_text,
    messages=[{'role': 'user', 'content': 'test'}]
)
print('Системный промпт:', result.input_tokens, 'токенов')
```

## Лимиты моделей (актуально: июнь 2026)

| Модель | max_input | max_output |
|---|---|---|
| claude-sonnet-4-6 | **1,000,000** | 128,000 |
| claude-opus-4-7 | **1,000,000** | 128,000 |
| claude-opus-4-8 | **1,000,000** | 128,000 |
| claude-haiku-4-5 | 200,000 | 64,000 |
| claude-opus-4-5 | 200,000 | 64,000 |

## Расшифровка метрик сессии

**Почему `input_tokens` почти ноль (21)?**  
Это только **новые** токены — текст сообщения пользователя, которого не было в кеше.  
Системный промпт (~6,357 токенов) + история (~36,000 токенов) — всё читается из Anthropic cache (`cache_read_tokens`).

**Среднее на API-вызов = реальный размер окна:**
```
total_effective = input_tokens + cache_read_tokens + cache_write_tokens
avg_per_call = total_effective / api_call_count
```

**Пример из сессии 20260626:**
- Среднее на вызов: ~42,776 токенов = 4.3% от 1M
- Системный промпт: ~6,357 токенов
- 44 сообщения в истории → ~37,000 токенов истории
- Стоимость: $0.64 (дорого из-за cache_write на большой sys_prompt)

## Готовый скрипт анализа

```python
import os, sqlite3
from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/.config/hermes/.env'))
import anthropic

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

# Лимиты моделей
for m in client.models.list().data:
    if any(x in m.id for x in ['sonnet-4-6', 'opus-4-7', 'haiku-4-5']):
        print(f"{m.display_name}: input={m.max_input_tokens:,}, output={m.max_tokens:,}")

# Текущая сессия (заменить SESSION_ID)
db = os.path.expanduser('~/.hermes/state.db')
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
cur = con.cursor()

SESSION_ID = '20260626_095345_9fe0b346'  # <-- заменить
cur.execute("""
    SELECT id, model, input_tokens, output_tokens,
           cache_read_tokens, cache_write_tokens, api_call_count,
           estimated_cost_usd, system_prompt
    FROM sessions WHERE id=?
""", (SESSION_ID,))
s = dict(cur.fetchone())
sp = s.pop('system_prompt') or ''

# Токены системного промпта
sp_tokens = client.messages.count_tokens(
    model='claude-sonnet-4-6', system=sp,
    messages=[{'role': 'user', 'content': 'x'}]
).input_tokens

total_in = s['input_tokens'] + s['cache_read_tokens'] + s['cache_write_tokens']
avg = total_in // s['api_call_count'] if s['api_call_count'] else 0

print(f"Сессия: {s['id']} | Модель: {s['model']}")
print(f"API-вызовов: {s['api_call_count']} | Стоимость: ${s['estimated_cost_usd']:.4f}")
print(f"Cache read: {s['cache_read_tokens']:,} | Cache write: {s['cache_write_tokens']:,}")
print(f"Sys prompt: ~{sp_tokens:,} токенов")
print(f"Среднее на вызов: ~{avg:,} = {avg/1_000_000*100:.1f}% от 1M")
```

## Как найти ID текущей сессии

```python
cur.execute("""
    SELECT id, source, model, started_at 
    FROM sessions ORDER BY started_at DESC LIMIT 5
""")
```

Или через логи:
```bash
grep "conversation turn" ~/.hermes/logs/agent.log | tail -5
```

## Важные наблюдения

- **Большой system_prompt → дорогой cache_write.** Текущий sys_prompt Сирени: ~6,357 токенов → каждый новый вызов пишет ~6K в cache (платно).
- **Cache read дёшево.** Cache read = $0.30/MTok vs $3/MTok для новых токенов (экономия в 10x).
- **Compression срабатывает при 50% окна** (порог 500K). При среднем 42K на вызов — до компрессии далеко.
- **Telegram-сессии стартуют с `history=0`** — каждое сообщение = новая сессия. История строится за счёт кеша.
