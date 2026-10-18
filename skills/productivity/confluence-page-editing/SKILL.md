---
name: confluence-page-editing
description: "правка Confluence: tutu-confluence-jira+page-to-schedule"
version: 1.0.3
status: redirect
platforms: [linux]
metadata:
  hermes:
    tags: [confluence, rest, storage, redirect]
    related_skills: [tutu-confluence-jira, pmo-charter-fill, page-to-schedule]
---

# confluence-page-editing — REDIRECT

**Не исполняет пайплайн.** Маршрутизация по задаче:

| Задача | Скилл |
|--------|-------|
| Заполнение/доработка устава ПРО | **`pmo-charter-fill`** |
| Патч одной секции (B0 section-patch + verify) | **`tutu-confluence-jira`** |
| План-график из страницы → GS (import 8 кол.) | **`page-to-schedule`** |

## Триггеры

- «заполни/доработай устав» → **`pmo-charter-fill`**
- «внеси поля в Confluence», «замени таблицу на странице» → **`tutu-confluence-jira`**
- «план-график из страницы», «залей фичи в GS как mpp» → **`page-to-schedule`**

## Донорский reference

`references/plan-graph-workflow.md` — исторический контекст; **канон пайплайна и скриптов** — скилл **`page-to-schedule`** v0.3.0+.

## См. также

- `pmo-charter-fill` — оркестрация устава
- `tutu-confluence-jira/references/section-patch.md` — патч секции
- `page-to-schedule/SKILL.md` — полный пайплайн C2
