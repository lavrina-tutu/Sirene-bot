# Cursor-модель-форензика: какая модель РЕАЛЬНО гонялась в Cursor CLI

Сценарий: «Я вижу, что где-то использовалась модель X (kimi / gpt-5.6-terra / muse-spark / …) — зачем, кем, и нужна ли она?». Ответ требует отличать каталог от факта.

## Корень ложных срабатываний

Cursor CLI **вкладывает весь каталог доступных моделей в системный промпт** каждой сессии. Поэтому простой `grep -ri "kimi" ~/.cursor/chats ~/.cursor/ai-tracking ~/.hermes/logs/agent.log` даёт десятки «попаданий» у моделей, которые **никогда не исполнялись** — это лишь список `- kimi-k2.7-code`, `- kimi-k3-low/high/max`, `- muse-spark-1.3-*`, `- gpt-5.6-terra-*` внутри system-блоба. Это не реальные прогоны.

Аналогично `config.yaml` содержит блок подключённых провайдеров (`moonshotai/kimi-k3`, `kimi-k2.7-code`, `gpt-5.6-terra`, `muse-spark-1.3`) — это **каталог доступного**, не маршрут задач. Наличие строки ≠ использование.

## Как проверить, реально ли модель исполнялась (по убыванию надёжности)

1. **agent.log — хвост самых длинных строк с `--model <name>` в фактических вызовах `agent -p`.** Реальный прогон всегда оставляет `agent -p "…" --model cursor-grok-4.6-high --output-format json 2>&1`. Если `--model kimi` не встречается — модель не запускалась из Hermes-пайплайна. (`model_calls` собирать regex'ом `--model ([a-z0-9./_-]+)` по строкам.)
2. **store.db сессии → первая строка system-блоба `blobs.data`** = `"You are an AI coding assistant, powered by <Model>."` Это то, что **реально** исполнялось в этой сессии (grok 4.6 / Composer / Claude Sonnet 5 / Gemini 3.6 Flash), а не каталог.
3. **meta-таблица store.db** — поля про model/usage часто пустые (`{}`); не полагаться, искать в блобах.

Схема: `~/.cursor/chats/<project-hash>/<session-uuid>/store.db`, таблицы `blobs` + `meta`. Прочесть через python `sqlite3` (на ВМ нет `sqlite3` CLI — только `python3`).

## Минимальный рецепт проверки

```python
import sqlite3, os, re
# сессии за дату: find ~/.cursor/chats -name store.db -newermt "YYYY-MM-DD 00:00"
# для каждой — реальная модель из system-блоба:
cur.execute("SELECT data FROM blobs")
for (blob,) in cur:
    txt = blob.decode('utf-8','ignore')
    m = re.search(r'powered by ([^.\n]+)', txt)
    if m: print(m.group(1))   # реальная модель сессии
# каталог-ложанки kimi искать НЕ по факту исполнения, а игнорировать
```

## Вывод кимки (прецедент 09.09)

`kimi` в чатах Cursor = только каталог в system-промпте + строки провайдера в config.yaml. Реально **не исполнялась** ни в одном прогоне: `--model kimi` = 0 вхождений в agent.log, system-блобы сессий показывают grok/composer/sonnet/gemini. Каталог и конфиг без факта прогона — не признак использования.

## Питфоллы

- Не верь `grep -ri <model>` по `~/.cursor/*` как доказательству исполнения — это каталог.
- Не верь строке провайдера в config.yaml — это доступность, не маршрут.
- `agent.log` единственный греп из всего этого грепа — мой собственный `grep -ri "kimi"` бьёт как «Hardline block» (я ищу сам себя); отбрасывать такие строки по префиксу `tools.approval: Hardline block`.