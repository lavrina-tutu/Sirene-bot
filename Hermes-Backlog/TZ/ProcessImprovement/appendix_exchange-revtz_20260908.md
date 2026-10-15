---
type: appendix
title: "REV:tz revexchange-contact-upsert (ревизор sonnet-5-med, 08.09)"
date: 2026-09-08
source: ревизор session 90ddb715 (claude-sonnet-5-medium)
status: 2 блокера устранены (см. appendix_exchange-finish-reliability / конец)
related: AnywhereContacts_TZ.md v0.3.0, ExchangeOrgLookup_TZ.md v0.3.0, HF-plan_exchange-contact-upsert
---

# REV:tz — ревью секций v0.3.0 exchange-contact-upsert

## Вердикт по секциям
- **AnywhereContacts_TZ.md v0.3.0**: ок по контракту/семантике; документное замечание (см. блокер 1).
- **ExchangeOrgLookup_TZ.md v0.3.0**: ок по контракту/семантике; то же замечание.
- **Согласованность AC↔OrgLookup**: ок. `_gal_result_to_record()` отдаёт ровно поля входного контракта AC; форма `conflicts[]` идентична в обоих ТЗ и коде.

**Код на диске перепроверен построчно:**
- create без email → unchanged+conflicts, диск не пишется (store.py:213-228) — соответствует A2.3 ✅
- реэкспорт в __init__.py:11 — есть ✅
- reports_to/реактивация/dry_run/unchanged без write — все ветки (store.py:275-345) соответствуют семантике 1:1 ✅
- cmd_bootstrap → upsert_gal_result (не md-merge) — cli.py:182-189 ✅
- cmd_add: VPN→exit 2, --dry-run прокидывается ✅
- test_upsert_gal.py: 11 не-заглушечных тестов по 6 критериям ✅
- AC pytest 46 passed ✅

## Блокеры (перед GATE:done) — устранены после ревью
1. **Противоречие секций**: вверху «реализовано», но в конце остались старые `**Реализация на диске:** нет (ожидает HF:impl)` (AnywhereContacts:415, ExchangeOrgLookup:424) + «Атомарные шаги/Пофайловый план» со старыми формулировками. → Убраны, актуализированы под факт «сделано».
2. **Команда прогона OrgLookup из плана не воспроизводится** без PYTHONPATH (ModuleNotFoundError: anywhere_contacts) — эко-дыра venv. → Команда исправлена (добавлен PYTHONPATH) в плане/ТЗ.

## Рекомендации (не критично)
- Реэкспорт как unbound метод — рабочий; в ТЗ стоит оговорить форму (метод vs standalone).
- `merge_to_enc_only` не используется — в ТЗ отметить «зарезервирован, не задействован».

## Итог после устранения
Содержательная часть (контракт, идемпотентность, конфликты, границы, согласованность AC↔OrgLookup) — **реально сделано и проверено кодом на диске**. Блокеры устранены → задача готова к GATE:done (после A6-канбан).