# SRTool: реализовано vs не реализовано (2026-08-10)

## Реализованные команды CLI (`~/USERTOOLS/SRTool/`)
- `python3 -m srtool report SR-XXXXX` — интерактивный бриф + заливка итогов (transition 271, блоки 4-6)
- `python3 -m srtool preview SR-XXXXX` — read-only превью без записи

## НЕ реализовано
- `srtool plan` — режим планирования начала периода (блоки 1-3). Код отсутствует.
  При ручном планировании:
  1. Поиск предыдущего SR → извлечение каркаса KR (Блок 3, `customfield_44403`)
  2. Сбор данных по OKR-ключам — **батч-запрос** `POST /search` с `jql=key in (A,B,C...)` (не N отдельных GET)
  3. Расчёт целевого %: ≥50% остатка (сейчас 30% → цель ≥65%)
  4. Заливка через `POST /transitions?id=61`, только 44401-44403

## Структура кода (12 модулей)
```
~/USERTOOLS/SRTool/srtool/
├── jira_client.py       # GET/POST к Jira API v2, transition 61/271
├── confluence_sources.py # Парсинг <ac:task> из минуток
├── task_mapper.py       # Гибридный маппинг задач на критерии
├── formatting.py        # Plain-text для Jira (CRLF, middle dot)
├── draft_manager.py     # Сохранение/загрузка _draft.md, resume
├── brief.py             # Поштучный бриф
├── preview.py           # Read-only режим
├── selfcheck.py         # Оркестратор end-of-period
├── cli.py               # CLI (argparse)
├── config.py            # Конфигурация
├── __init__.py
└── __main__.py
```

## Питфол: скилл `tutu-jira-sr` — симлинк, skill_manage не работает
Скиллы шарятся через симлинки workspace→default→tz-dev. `skill_manage(action='patch')` отвергает симлинки.
**Решение:** править файл в `~/hermes-workspace/skills/...` напрямую через `patch`/`write_file`.

## ТЗ SRTool
`~/WorkVault/Hermes-Backlog/TZ/SRTool/SRTool_TZ.md` — v2.0, включает и начало (v1.1), и конец (v2.0) периода.
