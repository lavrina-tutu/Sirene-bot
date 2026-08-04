---
name: backlog-collector
description: "DialogBacklog Сборщик v1.5. Читает новые сессии/сообщения с last_scan_at, находит открытые задачи и пишет их в ~/WorkVault/Hermes-Backlog/dialog-backlog.md с полем idea_summary. Не сверяет с реализацией — только сбор."
version: 1.5.0
author: agent
license: MIT
platforms: [linux, macos, windows]
triggers:
  - "собери бэклог"
  - "прогнать сборщик бэклога"
---

# DialogBacklog Collector (скилл 1)

## Назначение
Единственная ответственность: **собирать открытые задачи из диалогов** и писать
в `~/WorkVault/Hermes-Backlog/dialog-backlog.md`. Не сверяет с реализацией — это
делает скилл `backlog-analyst` (запускается через 5 минут).

## Расписание
`0 8 * * 1-5` — пн–пт 08:00 МСК. Заменяет старый крон `defc4425a957` (каждые 2ч).

## Модель
`claude-haiku-4-5` (tutu). Обоснование:
- поток инкрементный (за сутки — десятки–сотни сообщений, укладывается в контекст Haiku);
- формат `plan.json` строго структурирован — Haiku 4.5 стабильно выдаёт валидный JSON при чётких промптах;
- цена/скорость: гонять ежедневно на Sonnet избыточно, а Opus — тем более;
- Sonnet стоит держать только для еженедельных «глубоких» ретро-сводок, а этот скилл — рутина.

## Алгоритм
1. Читаешь frontmatter `dialog-backlog.md` → `last_scan_at`.
2. `python3 ~/USERTOOLS/DialogBacklog/backlog_fetch.py --since "<last_scan_at>"` → JSON сообщений.
3. Анализируешь: находишь открытые задачи по правилам v1.3 (`## Правила наполнения бэклога` в ТЗ).
4. Для каждой новой bk-задачи **обязательно** формируешь `idea_summary` — выжимку сути идеи из ~10 последних сообщений по теме (2–3 фразы, не более 200 симв).
5. Формируешь `plan.json`:
   ```json
   {
     "add_items": [{
       "section": "🔧 Hermes / Сирень",
       "text": "Доработать X — <короткое>",
       "context": "Упомянуто 27.07 в топике Tools",
       "idea_summary": "суть идеи в 1-2 предложениях",
       "created": "YYYY-MM-DD",
       "updated": "YYYY-MM-DD"
     }],
     "update_items": [{"anchor": "bk-098", "context": "новый контекст", "updated": "YYYY-MM-DD"}],
     "new_last_scan_at": "<now ISO+03:00>"
   }
   ```
   `suggest_close` **не заполняешь** — это задача скилла-аналитика.
6. `python3 ~/USERTOOLS/DialogBacklog/backlog_merge.py --plan /tmp/plan.json`.
7. Формируешь Telegram-сводку в топик Backlog (`telegram:-1004300127777:6`) в формате v1.3 («Новые», «Обновлено», при пустом — `[SILENT]`).
8. Пишешь запись в журнал через `cron-journal-write`.

## Что НЕ делает
- Не сверяет со скиллами и `MAIN_TZ_INVENTORY` — это скилл `backlog-analyst`.
- Не ставит `[x]` — только Саша вручную.
- Не переписывает текст существующих пунктов (`update_items.text` не использует).

## Формат новой задачи в файле
```
- [ ] Доработать ExchangeMonitor — фильтр по отделу ^bk-149
  - 💬 Контекст: 27.07 в Tools
  - 💡 `idea_summary:: фильтровать письма только от сотрудников своего отдела`
  - 📅 `created:: 2026-07-27` · `updated:: 2026-07-27`
```

## В финале — журнал
Загрузи скилл `cron-journal-write` и запиши строку итога.
