# version-handoff — pfs-task-slug-regress (2026-10-15)

Граф: `DEV/pfs-task-slug-regress` (корень t_14eae0a1)
Карточки: `t_ccea01d9` (GATE:take-into-work, auto-pass) · `t_3415f6cc` (HF:impl) ·
`t_79bb8809` (HF:test) · **`t_2019ccba` (HF:docs-handoff, эта досье)** · `t_00df30b7` (GATE:done, следующий)
Исполнитель docs: Сирень (default), фаза `HF:docs-handoff`; код/тесты — HF:impl/HF:test (ed7878a).

## Скоуп пакета (BUGFIX-LIGHT, §33)

Регрессия: задача «Протестировать учет действий MCP AI аналитика…» встречи
`2026-10-14 09-30-00 Кирилл 1-1` (row_anchor `pfsrow-71c15c31462e`) публиковалась БЕЗ task_slug,
хотя текст содержит проектный сигнал `ai_analitik`. 13.10 тот же picker работал (задачи получили
`AI-аналитик.`/`АДМ.`) → регрессия 13–14.10.

Фикс **ed7878a** (14.10 22:23 MSK, HEAD): детектор project-signal = assignee ∪ `task.text`;
детерминированный fallback при пустом/невалидном ответе LLM: ровно 1 уникальный проект
closed_list в `task.text` → `canonical_task_slug + orig_text`, 0 → fail-soft, ≥2 → fail-soft
(не угадывать). Notes/YAML `projects:`/встреча — вне uniqueness. §33 в master-ТЗ v1.28.1 (TZ:finalize 14.10, REV:tz APPROVE).

## Версии канона (после пакета, код на диске = HEAD ed7878a)

| Артефакт | Версия | Суть |
|---|---|---|
| `ProtocolFromSummary_TZ.md` | **1.28.1** | §33 «Сигнал проекта = assignee ∪ текст задачи» задокументирован (TZ:finalize 14.10) |
| `protocolfromsummary/task_slug.py` | HEAD `ed7878a` | детектор сигнала + детерминированный fallback |
| `tests/test_task_slug.py` | 27 passed | детектор/fallback/notes-вне-uniqueness |
| PFS-сюита (оффлайн+live_confluence) | **456 passed** (518s) | регресс всего пакета после правки |
| `entities.json` | schema 1.2, closed_list 14 | Решение Саши 12.10 (supersede AC-002) |

## Аудит встреч окна 13.10 13:39 – 14.10 21:59 (эта фаза)

Окно = код между 5ec3f97 (13.10 13:39 MSK) и ed7878a (14.10 22:23 MSK).
Скоуп аудита — встречи kind **1-1 / unknown / sync_aid** за 13–14.10, обработанные до 21:59 MSK 14.10.

Проверено по NewMeetings (все файлы 13–14.10) + реестру `_registry.json` + живой странице 508804979 (GET).

| Встреча | kind | Опубликована | Задачи с проект. сигналом → slug на живой странице | Действие |
|---|---|---|---|---|
| `2026-10-14 09-30-00 Кирилл 1-1` | one_on_one | 13:14 MSK (старый код, **регрессия** MCP-задачи без slug) → republished 22:26 MSK (фикс) | «MCP AI аналитика» → **`AI-аналитик.`** ✓ (anchor 71c15c31462e); остальные 5 задач без сигнала → честная пустота | **уже исправлено** republish 22:26; на цели GET-подтверждён префикс |
| `2026-10-13 07-35-00 Кирилл 1-1` | one_on_one | 11:12 MSK (вне окна, до 13:39) | «бэкапы платформы»→`AI-аналитик.`, «Self-Review»→`АДМ.`, «AI-продукт»→`AI-аналитик.` ✓ (anchor 94fdad07e276) | **не требуется** — slug уже проставлены, без регрессии |
| `2026-10-13 12-30 AI-мультиагентная…` | project (ai_analitik) | вне скоупа аудита (kind=project) | — | не требуется |
| `2026-10-14 12-00 AI-ready…` | project (ai_ready) | вне скоупа аудита (kind=project) | — | не требуется |

**Итог аудита:** задач с проектным сигналом, у которых slug отсутствует, в окне НЕТ.
Единственная пострадавшая (14.10, MCP-задача) уже ре-публикована с фиксом 22:26 MSK и подтверждена на
цели. → **delete+reingest/republish для других встреч НЕ требуется.**

## Открытый вопрос MOFS — НЕ блокер пакета (требует решения Саши/архитектора)

Встреча `2026-10-15 07-30-00 Кирилл 1-1` (опубликована 11:14 MSK, уже с фиксом ed7878a),
площадка 523032632, задача «Создать аналитику по использованию тест-бота продуктами и
соответствию задач Jira». MOFS `project_bind` = `ai_analitik` (hypothesized), но PFS picker
**не** проставил slug: в `task.text` нет identity из closed_list → fail-soft (AC-006).

Несовпадение **гипотезы MOFS (project_bind) и строгого PFS-матчинга** (assignee ∪ task.text
по закрытому списку). Вопрос для решения: **должна ли гипотеза MOFS (`project_bind`) влиять на
`task_slug`?** — вынесен из пакета, требует отдельного решения Саши/архитектора. Не блокирует
GATE:done (вне этого багфикса).

## Верификация docs (эта фаза)

| Проверка | Результат |
|---|---|
| Связь с живой страницей 508804979 | GET OK (len 107246), 60 anchor-строк; обе строки 13.10/14.10 найдены по anchor |
| Фактическое наличие slug 14.10 MCP-задачи | `AI-аналитик.Протестировать…` в storage ✓ |
| Фактическое наличие slug 13.10 | `AI-аналитик.`/`АДМ.`/`AI-аналитик.` ✓ |
| Аудит окна | пострадавших без slug не осталось; delete+reingest не требуется |
| Master-ТЗ | §33 уже в master 1.28.1 (записан TZ:finalize, не этой фазой) |
| Реестр `_registry.json` | schema_version 1.1, без изменений этой фазой |

## Метаданные `kanban_complete` (HF:docs-handoff)

```yaml
role: исполнитель (docs)
model: deepseek/deepseek-v4-flash-0731
code_commit: ed7878a          # сделано HF:impl/HF:test
tz_version: 1.28.1            # §33 в master
tests: test_task_slug 27 / full-suite 456 (HF:test t_79bb8809)
audit_window: 13.10 13:39 – 14.10 21:59 MSK (5ec3f97..ed7878a)
audit_scope: kind 1-1/unknown/sync_aid, даты 13–14.10
audit_findings:
  - '2026-10-14 09-30 Кирилл 1-1: MCP-задача была без slug → уже republished 22:26 MSK с фиксом; на цели AI-аналитик. GET-подтверждён'
  - '2026-10-13 07-35 Кирилл 1-1: slug уже проставлены (AI-аналитик./АДМ.), вне окна, action не требуется'
  - 'delete+reingest/republish иных встреч окна НЕ требуется'
open_questions:                    # вне пакета, на решение Саши/архитектора
  - 'MOFS project_bind(ai_analitik) vs строгий PFS-матчинг: должна ли гипотеза MOFS влиять на task_slug? (встреча 15.10)'
changed_files: []
not_touched:
  - ProtocolFromSummary_TZ.md      # §33 записан TZ:finalize 14.10, не этой фазой
  - _registry.json
  - jobs.json / Gateway / cron
notify: next card t_00df30b7 (GATE:done, preflight BUGFIX-LIGHT auto)
```

## Следующие шаги

1. `GATE:done` (`t_00df30b7`) — preflight BUGFIX-LIGHT, auto. Открытый MOFS не блокирует.
2. Решение Саши/архитектора по MOFS project_bind → task_slug (отдельный вопрос, вне пакета).