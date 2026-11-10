---
name: pmo-charter-fill
description: "Use when: заполни устав, доработай устав, проектные документы полного внедрения. Оркестрация заполнения устава/брифа ПРО в Confluence: pack --task charter + MPP CSV + 3 пачки grok (MPP / стратегические / контекстные), цифры скриптом (ceil, ФОТ, бюджет), вставка только B0 section-patch + verify. Не PUT из grok."
version: 1.0.0
author: agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [confluence, charter, pmo, mpp, deep-mine, trisigma]
    related_skills: [deep-mine-project, tutu-confluence-jira, page-to-schedule, read-mpp, pm-briefing]
---

# pmo-charter-fill — заполнение устава ПРО в Confluence

Консолидированный скилл оркестрации устава/брифа проекта. Заменяет `charter-fill`, `project-charter-authoring`, `confluence-doc-edit-cursor` (redirect).

## When to Use

- «заполни устав», «доработай устав», «проектные документы полного внедрения»
- Драфт устава (Confluence `page_id`) + шаблон пилота (`page_id`) + MPP полного внедрения
- «переформулировать» = переписать под **новый** проект, не копировать пилот

**Don't use:** только digest без pack (`deep-mine-project` collect); точечный Q&A (`workvault-rag`); план-график в GS (`page-to-schedule`).

## Входы

1. `page_id` драфта устава (напр. `519487958`)
2. `page_id` шаблона (напр. устав пилота `490167911`)
3. `deep_mine.py pack --slug <Slug> --task charter` → `PACK.md` + `BRIEF.md`
4. MPP CSV в overlay (`mpp/*__assignments.csv`, `*__tasks.csv`)

## Роли (один agent -p = одна модель)

| Роль | Модель | Делает |
|------|--------|--------|
| Координатор | Сирень | чеклист инвариантов, pack, брифы пачек |
| Архитектор | gpt-6-astra (codex CLI) | тексты полей (markdown), 3 пачки |
| Исполнитель | gpt-6.1-sol (codex CLI) | section-patch, verify, `fot_budget.py` |
| Grok | — | **не** PUT, **не** ceil/бюджет/даты |

## Три пачки grok (не 17)

См. `references/pro-field-catalog.md`.

1. **MPP** — сроки, описание/границы, КТ, ИСР, календарный/ресурсный план.
2. **Стратегические** — эффекты, цель, финмодель, ключевые поставки, бюджет (текст; суммы — скрипт).
3. **Контекстные** — стейкхолдеры, коммуникации, допущения, ограничения, риски.

Каждая пачка: бриф из `references/architect-brief.template.md` + пути pack. Результат → `Projects/<Slug>/docs/_charter_draft/NN_<batch>.md`.

## Цифры — только скрипт

```bash
~/hermes-agent/.venv/bin/python3 \
  ~/hermes-workspace/skills/productivity/pmo-charter-fill/scripts/fot_budget.py
```

- `parse_hours("80.0 h")` → 80.0
- `ceil_days(361.875)` → 362
- Бюджет = vendor + rate×hours (дефолт ставка `3000` ₽/ч)

Модель не считает ФОТ, ceil, бюджет.

## Вставка в Confluence (B0)

Только `tutu-confluence-jira`:
1. `section_patch.py` — GET → замена **внутренности** секции по заголовку → PUT
2. `verify_skeleton.py` — 7-пунктовый чеклист после PUT

Запрещено: grok/composer генерирует полный `body.storage` или PUT напрямую.

## Чеклист до grok

`references/invariants-checklist.md` — пустой = не стартовать.

## Инварианты Trisigma-класса

- Ceil дней вверх
- Пилот вычищен из всех полей кроме явно разрешённого
- Источник — актуальный MPP, не пилотный план
- Сроки — `<time datetime="YYYY-MM-DD" />`
- Бюджет = договор вендора + ФОТ (assignments × ставка)

## Связки

- `deep-mine-project` — pack, digest, overlay
- `tutu-confluence-jira` — section-patch, verify, userkey batch
- `page-to-schedule` — план-график (отдельный скилл)
- `read-mpp` — MPP→CSV если нет в overlay

## Verification

```bash
~/hermes-agent/.venv/bin/python3 -m pytest \
  ~/hermes-workspace/skills/productivity/pmo-charter-fill/tests -q -m "not live"
```

Live PUT — только по явной команде пользователя.
