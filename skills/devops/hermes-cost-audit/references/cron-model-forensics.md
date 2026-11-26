# Как выяснить, на какой модели реально исполняется крон-джоб

Применять, когда: пользователь подозревает крон на «нештатной» модели (например «на
отключенном API-ключе крутился крон на gemini»), publication задерживается, прогоны
падают с `Model generated invalid tool call: <name>` / `The <run> tool is not available`,
или нужен аудит «кто на какой модели гоняет».

## Ключевая ловушка: jobs.json `model: null` ≠ реальная модель

У агентного крона (`no_agent: false`) в `~/.hermes/cron/jobs.json` поле `model` может быть
`null`, хотя фактически крон исполняется на конкретной (иногда устаревшей/нештатной)
модели. Поэтому **не верь полю `model` в jobs.json как доказательству** — проверяй реальное
исполнение.

## Шаг 1 — фактическая модель по state.db (источник истины по исполнению)

```bash
python3 -c "
import sqlite3
c=sqlite3.connect('/home/tkachenkoav/.hermes/state.db'); cur=c.cursor()
cur.execute(\"SELECT model, source, COUNT(*), SUM(estimated_cost_usd) FROM sessions \
WHERE date(started_at,'unixepoch','localtime')>='YYYY-MM-DD' GROUP BY model,source ORDER BY 3 DESC\")
for r in cur.fetchall(): print(r)
c.close()"
```

- `source='cron'` + интересующая модель → какие крон-джобы на ней. Детально по каждому:
  `SELECT title, model, datetime(started_at,'unixepoch','localtime'), api_call_count,
   input_tokens, output_tokens, message_count FROM sessions WHERE title LIKE '%<job>%'
   ORDER BY started_at`.
- Пометка: если последний прогон перешёл на другую модель (напр. debounce deepseek после
  cost-оптимизации), это покажет переход — «было gemini → стало deepseek».

## Шаг 2 — историческая конфигурация модели крона

Текущий job может уже иметь `model: null`, а до правки стою реальная модель. Смотреть
бэкапы jobs.json и их содержимое по каждому найденному джобу:

```bash
ls -la ~/.hermes/cron/jobs.json*        # найти jobs.json.bak-<date>-<time>
python3 -c "
import json
for fn in ['~/.hermes/cron/jobs.json.bak-<file>']:
    d=json.load(open(fn))
    jobs=d if isinstance(d,list) else d.get('jobs',[])
    if isinstance(jobs,dict): jobs=list(jobs.values())
    for j in jobs:
        if isinstance(j,dict) and j.get('model') and '<модель>' in str(j.get('model')):
            print(j.get('id'),'|',j.get('name',''),'| model=',j.get('model'))"
```

## Шаг 3 — матчинг симптома сбоя к агрегатной модели

Если прогоны крона в `~/.hermes/cron/output/<job_id>/` содержат:
- `RuntimeError: Model generated invalid tool call: run` — агентная модель вызвала
  несуществующий тул (типично для слабой модели, напр. gemini-lite);
- `The run tool is not available` — тот же сбой, модель подставляет чужой tool-schema;
- `timeout and LLM errors` — модель зависла/не смогла завершить цепочку.

Это признак нештатной МОДЕЛИ крон-агента, а не бага инструмента (PFS/скрипта). Чинить
модель крона (перевести на `model.default`/deepseek, либо `no_agent` script), а не код
инструмента.

## Прецедент (18.08.2026)
Пользователь: «уведомление о встрече не пришло, крутился какой-то крон на gemini».
Диагноз: pfs_batch (агентный крон, `model: null` в jobs.json) реально исполнялся на
`google/gemini-2.5-flash-lite` (18 сессий в state.db за 17–18.08), сыпал `invalid tool
call: run` и timeout. Cost-оптимизация 17.08 сбросила model → `null` (дефолт deepseek);
последний прогон 18.08 14:10 уже на `deepseek-v4-flash-0731` и отработал чисто —
опубликовал встречу. Дополнительный фактор: `pfs_notify` (уведомитель) — детерминированный
no_agent-скрипт раз в час; `notified: false` в `_registry.json` = уведомление придёт на
следующем тике, это не потеря.