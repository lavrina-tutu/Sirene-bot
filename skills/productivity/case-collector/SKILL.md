---
name: case-collector
description: "Use when: собери кейсы, выгрузи темы за N дней, case-collect"
  Use when: собери кейсы, выгрузи темы за N дней, case-collector,
  таблица пользователь × тема × период + вердикт решённости по диалогу
  из логов сессий Hermes state.db.
  Read-only sqlite; LLM-split по смыслу; выход xlsx в Inbox.
version: 0.2.1
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [sessions, cases, xlsx, analytics, state-db]
    related_skills: [spreadsheet-deliverables]
---

# case-collector

Скилл собирает таблицу **пользователь × тема кейса × начало × конец** из read-only логов `state.db` за окно дат. Разбиение по смыслу — через LLM; промпт в `references/split-prompt.md`, пример карты пользователей — `references/user-map.example.yaml`.

## Триггеры

«собери кейсы», «выгрузи темы за N дней», `case-collector`.

## Запуск

Интерпретатор: venv `Path.home()/hermes-agent/.venv/bin/python3` если есть, иначе `python3`.

```bash
python3 scripts/case_collector.py --since ISO --until ISO [опции]
```

## Параметры CLI

| Аргумент | Default | Описание |
|---|---|---|
| `--since` | — | обязателен, ISO-8601 |
| `--until` | — | обязателен, `[since, until)` |
| `--tz` | Europe/Moscow | зона вывода |
| `--db` | `~/.hermes/state.db` | путь к БД |
| `--output` | `~/WorkVault/Inbox/case-collector_*.xlsx` | файл или каталог |
| `--exclude-sources` | cron,kanban,subagent | CSV |
| `--include-sources` | — | белый список |
| `--user-map` | — | YAML/JSON, не коммитить боевую карту |
| `--model` | — | приоритет 1 резолва модели |
| `--llm-backend` | auto | hermes \| openai-compat \| auto |
| `--dry-run` | выкл | инвентарь без LLM |
| `--limit` | — | потолок сессий |
| `--max-input-chars` | 12000 | порог чанков |
| `--include-assistant-stubs` | выкл | assistant ≤200 |
| `--concurrency` | 1 | max 3 |
| `--prefer-origin-user-name` | выкл | Windows |
| `--config` | `~/.hermes/config.yaml` | model.default |

## Поведение агента

1. Период из фразы Саши; если нет — спросить один раз.
2. Без явного «в бой» — сначала `--dry-run --limit 20`.
3. `--db` не хардкодить; `--user-map` только если Саша дал файл.
4. Запускать CLI, **не** `agent -p`.
5. В чат — только отчёт CLI (период, db, счётчики, путь, usage, llm_error). Без таблицы и сырого диалога.
6. Если >200 сессий без `--limit` — CLI предупреждает; пересказать, не запрещать.
7. Латентность: ~150 вызовов × 5–15 с; дым `--limit 20`.

## Запреты

- Крон, `jobs.json`, ErrorBus — не трогать.
- Jira, Confluence, Loop, MoveFromJira — не вызывать.
- `state.db` — только SELECT; без VACUUM/checkpoint/записи.
- Модель не подставлять из текущей сессии и не хардкодить slug.
- PIIScan для других скиллов не ослаблять; этот скилл только читает БД.
- Сырой диалог не класть в Inbox/xlsx/логи.
- Windows-инстанс с Linux не трогать.
