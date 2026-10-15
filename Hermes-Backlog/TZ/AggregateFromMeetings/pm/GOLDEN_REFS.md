---
tool: AggregateFromMeetings
type: golden-reference
created: 2026-06-25
status: active
---

# Golden References — эталоны для автопроверки

> Confluence «Задачи и договорённости (Минутки)» = **эталон**, собранный вручную.
> Автосборка decisions + action_items должна **как минимум покрывать** эталон (recall).

## Критерии сравнения

1. **recall decisions** — все решения из Confluence есть в автосборке
2. **recall action_items** — все задачи есть, со сроками
3. **резолв ФИО** — примерно как в эталоне (ContactStore)
4. **дедуп** — одна задача на N встреч = одна запись
5. **статус** — open vs closed совпадает с эталоном

## Эталоны по проектам

| Slug | Confluence pageId | URL | Sandbox для сравнения | Статус |
|------|------------------:|-----|----------------------|--------|
| `ml-platforma` | 490169504 | [открыть](https://dom.tutu.ru/pages/viewpage.action?pageId=490169504) | [[_review/Projects/ml-platforma/ai/]] | ✅ задан PM |
| `trisigma` | 490170597 | [открыть](https://dom.tutu.ru/pages/viewpage.action?pageId=490170597) | [[_review/Projects/trisigma/ai/]] | ✅ задан PM |
| `parsing` | — | _нужен URL_ | [[_review/Projects/parsing/ai/]] | ⏳ |
| `antibot` | — | _нужен URL_ | [[_review/Projects/antibot/ai/]] | ⏳ |
| `ai-transformaciya` | — | _нужен URL_ | | ⏳ |
| `metroteka` | — | _nужен URL_ | | ⏳ |
| _+10 проектов_ | — | | | ⏳ |

## Особенности

- **trisigma:** задачи по AB-платформе явно помечены в названии — не смешивать с чистым trisigma
- **ml-platforma:** фильтровать решения с 1-1 по портфельной приоритизации

## Автосравнение (когда «начинай обработку»)

```
Confluence (эталон) ──compare──► _review/ или новая сборка
  ├─ recall decisions
  ├─ recall action_items + сроки
  ├─ fuzzy match ФИО
  └─ dedup check
```

Локальных копий Confluence-страниц на VM **пока нет** — нужна выкачка через ConfluenceSync в `_review/golden/`.
