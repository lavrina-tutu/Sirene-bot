# Внешние инструменты, невидимые в state.db (PFS/MFF/MOFS)

## Проблема (08.2026 прецедент)

Саша увидел в биллинге `llm-gateway-admin.tutu.ru` расход на `deepseek/deepseek-v4-pro`
за 15–17.08. Архитектор в Cursor проверил `~/.hermes/state.db` (sessions, session_model_usage),
`cron/jobs.json`, логи `agent.log`, конфиги `~/.hermes/` и честно заключил: «0 записей → расхода нет,
строка x_search просто мёртвая». Это было НЕВЕРНО.

Настоящий источник — **ProtocolFromSummary (PFS)**, отдельный инструмент вне Hermes-агента:
```
~/USERTOOLS/ProtocolFromSummary/protocolfromsummary/config.py
  DEDUP_LLM_MODEL = os.environ.get("DEDUP_LLM_MODEL", "deepseek/deepseek-v4-pro")
  DEDUP_LLM_PROVIDER = os.environ.get("DEDUP_LLM_PROVIDER", "default")   # → tutu gateway
  DEDUP_LLM_REASONING_EFFORT = os.environ.get("DEDUP_LLM_REASONING_EFFORT", "high")
```
PFS ходит на `llm-gateway.tutu.ru` **своим API-ключом**, минуя Hermes, поэтому его вызовы
не попадают ни в `state.db`, ни в `agent.log`, ни в `session_model_usage`. В биллинге же
по УЗ Саши они видны (общий счётчик гейтвея). Запускается из `pipeline.py`, вызывается
кронами `pfs_batch` (agent-driven) и `pfs_notify` (no_agent) — оба активны.

## Правило источника истины

- `state.db` — это оценка Hermes по **публичному** прайсу модели (колонка `estimated_cost_usd`),
  от «взрослых» сессий агента. Он НЕ включает расход сторонних инструментов и не равен биллингу.
- Настоящий счёт — в админке гейтвея: `https://llm-gateway-admin.tutu.ru/usage?preset=7d`
  (под учётной записью пользователя). Если юзер говорит «я вижу расход на X в биллинге» —
  это приоритетнее «0 записей в state.db». Не оспаривай факт на основе данных агента.
- При любом аудите «кто жжёт модель M» ищи **за пределами** `~/.hermes/`:
  - `grep -rn "<model-slug>" ~/USERTOOLS/` (PFS, MFF, MOFS, MoveFrom*, ...)
  - дефолты в `*/config.py`/`*.py`/`*.sh`: `*.get("SOME_LLM_MODEL", "provider/model")`
  - `DEDUP_*` в PFS, аналогичные env-переменные моделей в других инструментах.
- Hermes-конфиги (`x_search.model`, `auxiliary.*`, `model.default`) — лишь часть карты.

## Как менять модель внешнего инструмента

- Не by ручное редактирование кода из чата — это правка внешнего инструмента, по правилам
  через Cursor (композер-исполнитель), с бэкапом и проверкой.
- Точная правка: дефолт `DEDUP_LLM_MODEL` → нужная модель + понизить `DEDUP_LLM_REASONING_EFFORT`
  (например с `high` на `low` — флэш-класс моделей не тянет `high`-мышление как pro).
- Проверить, нет ли override через env в скриптах запуска (чтобы правка дефолта перекрылась).
- После правки прогнать инструмент на тестовом файле и проверить по биллингу/логам, что уходит
  на нужную модель.

## Гигиена после смены основной модели

После перехода основной модели (pro → flash и т.п.) проверить, что слаг старой модели не остался
в трёх зонах: (1) `config.yaml`: `x_search.model`, не-auto `auxiliary.*`; (2) `cron/jobs.json`
agent-driven модели; (3) **внешние инструменты**: `DEDUP_LLM_MODEL` в PFS и аналоги. Всё, что
не является белым списком `custom_providers.tutu.models`, — активная ссылка и требует замены.
