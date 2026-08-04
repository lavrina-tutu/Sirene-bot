---
name: backlog-analyst
description: "DialogBacklog Аналитик v1.5. Читает dialog-backlog.md, сверяет открытые задачи со скиллами и MAIN_TZ_INVENTORY, помечает реализованные `suggest close`. Ничего не создаёт и не пишет в бэклог кроме пометок."
version: 1.5.0
author: agent
license: MIT
platforms: [linux, macos, windows]
triggers:
  - "что в бэклоге"
  - "проверь бэклог"
  - "прогнать аналитик бэклога"
---

# DialogBacklog Analyst (скилл 2)

## Назначение
Единственная ответственность: **сверять открытые задачи с реализацией** и предлагать
`suggest close` для того, что уже сделано. Не собирает новые задачи — это скилл
`backlog-collector`.

## Расписание
`5 8 * * 1-5` — пн–пт 08:05 МСК (через 5 минут после сборщика). Также запускается
по фразе «что в бэклоге» / «проверь бэклог». Заменяет старый крон `vm_dialogbacklog`.

## Модель
`claude-haiku-4-5` (tutu). Обоснование: сверка на строго структурированных промптах A/B/C
(см. `backlog_analyst.py`), без креатива, JSON-only ответы — Haiku здесь оптимальна.

## Алгоритм
1. Читаешь `~/WorkVault/Hermes-Backlog/dialog-backlog.md`, собираешь открытые `[ ]`.
2. Через модуль `backlog_analyst` (Python):
   - парсинг бэклога: `parse_backlog(text)` → пропускает `epic-*` и уже помеченные `<!-- AI: suggest close`;
   - загрузка скиллов: `load_skills()` (пробует `hermes skills list --json`, иначе — файловая система);
   - загрузка инвентаря: `load_inventory(MAIN_TZ_INVENTORY.md)`.
3. Для каждой открытой задачи прогоняешь три промпта (константы `PROMPT_A_INTENT`, `PROMPT_B_MATCH`, `PROMPT_C_IMPROVE_VERDICT` в модуле):
   - **A**: намерение — `create` / `improve` / `other`.
   - **B**: сверка объекта со скиллами и активным/completed инвентарём.
   - **C** (только для `improve`): по ТЗ и `idea_summary` — реализована ли конкретно эта доработка.
4. Кандидаты собираются в `plan.json`:
   ```json
   {"suggest_close": [
     {"anchor": "bk-093", "reason": "инструмент MeetingScheduler в реестре, status=active (v1.3)"}
   ]}
   ```
5. `python3 ~/USERTOOLS/DialogBacklog/backlog_merge.py --plan /tmp/plan.json`.
6. Telegram-сводка в топик Backlog: блок `💡 Suggest close (N)`. Если предложений нет → `[SILENT]`.
7. Журнал через `cron-journal-write`.

## Правила приоритета вердикта
- Эпики (`^epic-*`) — пропускать на входе.
- Уже помеченные `<!-- AI: suggest close` — пропускать.
- `status: draft` в инвентаре — **НЕ** считается реализацией.
- `status: active` / `status: completed` — считаются реализацией.
- `verdict: undetermined` в C — **не** предлагать закрытие (лучше пропустить, чем ложный вердикт).

## Что НЕ делает
- Не собирает новые задачи (`add_items` пустой).
- Не меняет формулировки открытых пунктов (`update_items` пустой).
- Не ставит `[x]` — только `<!-- AI: suggest close: <reason> -->`.

## Быстрый запуск (для проверки)
```bash
cd ~/USERTOOLS/DialogBacklog
python backlog_analyst.py --stub-llm --dry-run   # smoke без LLM
```

## В финале — журнал
Загрузи скилл `cron-journal-write` и запиши строку итога.
