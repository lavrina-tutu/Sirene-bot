---
type: appendix
title: "Аудит выполнения exchange-contact-upsert vs план (архитектор 08.09)"
date: 2026-09-08
source: архитектор session e82c8f9e (cursor-grok-4.6-high)
status: feedback (требует доработки перед GATE:done)
related: appendix_exchange-resume_20260908.md, GLOSSARY v0.2.0, DevKanbanPipeline
---

# Аудит выполнения exchange-contact-upsert vs плановая логика

**Вердикт: частично.** Код по сути CHANGE сделан, AC-тесты живые, но цепочка 08.09 шла мимо канбана, со свёрнутым TZ-WRITE, без HF:plan/GATE:plan-approve, без доказанного REV:tz, без полноценного HF:docs-handoff. **Задачу закрывать рано.**

## План vs факт (по фазам)
| Фаза | Вердикт |
|---|---|
| BRF(light) | да (в TG, зачли appendix) |
| BRIEF-CLOSE | **нет** — графа нет, kanban.db пуст |
| TZ:stabilize / compress | **нет** — отдельные вызовы не было |
| TZ:patch | частично (свёрнут в 1 вызов composer, роль смешана) |
| REV:tz | **не подтверждён** (нет сессии sonnet) |
| TZ:finalize | частично (секции есть, но статус в ТЗ не обновлён; bump 0.2.2 ≠ 0.3.0) |
| take-into-work | да (по смыслу) |
| HF:compress / HF:plan | **нет** (обязательны по плану задачи) |
| REV:plan | да (OFF, задумано) |
| GATE:plan-approve | **нет** (не было) |
| backup | да |
| impl/test | частично (смешаны, плана не было) |
| docs-handoff | **нет** (в ТЗ до сих пор «на диске: нет») |
| ORCH | частично (инвариант «только Сирень» соблюдён, но дописаны 5 чужих ТЗ) |
| GATE:done | **нет** |

## Отклонения — критично
1. Нет графа после BRIEF-CLOSE (сломан audit trail, карточка≠фазы).
2. PLAN-IMPL-TAIL обрезан: нет HF:plan и GATE:plan-approve.
3. TZ-WRITE(full) свёрнут в 1 вызов исполнителя (должен быть архитектор + компрессор) — нарушен «1 agent -p = 1 роль».
4. REV:tz заявлен, но не найден (нет доказательств sonnet).
5. HF:docs-handoff не закрыт — в обоих *_TZ.md статус «на диске: нет».
6. GATE:done не снят — нельзя считать закрытой.

## Отклонения — качество vs ТЗ v0.3.0
7. Нет реэкспорта `upsert_from_source` из `__init__.py` (явный шаг ТЗ).
8. Тесты OrgLookup покрывают старый md-merge, НЕ критерии v0.3.0 (upsert create/dry-run/VPN/KeyError-regression) — «4/4» не про эту доработку.
9. `cmd_bootstrap` всё ещё через md-merge как persist, не через upsert.
(мелочи: версия 0.2.2 vs заявлено 0.3.0; __version__=0.1.0; email не required в коде)

## Что хорошо
Черновик upsert заменён; lookup/status/идемпотентность/reports_to/reactivate/dry_run в AC — по семантике ТЗ; cmd_add — VPN exit 2, живой --dry-run, запись через upsert_gal_result; бэкап есть; манифест исполнитель не писал; 07.09-граф не поднимали. Тесты AC (6) — не заглушки.

## Что доделать перед GATE:done
1. **HF:docs-handoff**: сменить в обоих *_TZ.md статус на «реализовано 08.09», сверить с инвентарём.
2. **Ретро-план HF:plan** (короткий факт: что сделано/нет: bootstrap, реэкспорт, тесты OrgLookup) — наличие объекта для plan-approve.
3. **Дописать тесты OrgLookup** по критериям 1-6 (upsert create, dry-run, VPN→exit 2, login не теряется).
4. **ТЗ-дыры в коде**: реэкспорт upsert в __init__.py; bootstrap — upsert/merge_to_enc_only.
5. **Граф**: завести канонический DEV/exchange-contact-upsert и закрыть фазы комментариями «done off-board» ИЛИ явно зафиксировать исключение «работали без канбана 08.09».
6. **REV:tz**: либо реальный прогон sonnet по двум секциям, либо явно снять флаг.
7. **GATE:done НЕ ставить** до закрытия 1-6.

Итог: продукт частично есть, процесс CHANGE — нет; «закрыта» — нет.