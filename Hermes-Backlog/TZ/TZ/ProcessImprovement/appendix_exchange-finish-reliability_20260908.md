---
type: appendix
title: "Досбор exchange-contact-upsert + безотказность цепочек (архитектор 08.09)"
date: 2026-09-08
source: архитектор session 10630f74 (cursor-grok-4.6-high, resume)
status: draft (согласуется Сашей; два контура внедрения)
related: appendix_exchange-audit_20260908.md, appendix_exchange-finish-task.md
---

# A. Досбор exchange-contact-upsert (кейс CHANGE)

Важно: это остаток PLAN-IMPL-TAIL, не новый TZ-WRITE. Секции v0.3.0 на диске есть (frontmatter 0.2.2). `GATE:done` — только после A1-A6.

**Ретро-факт на диске** (что сделано/нет): AC store.py — upsert жив; нет email-required; нет реэкспорта в __init__.py; OrgLookup cmd_add — VPN exit 2, --dry-run, upsert_gal_result; cmd_bootstrap persist всё ещё через md-merge (нарушение ТЗ); тестов OrgLookup по v0.3.0 нет; ТЗ статус «на диске: нет», версия 0.2.2≠0.3.0; канбан-графа нет.

**Порядок:** `HF:plan`(план на диск) → GATE:plan-approve (one-pass) → HF:impl (дыры) → HF:test → HF:docs-handoff → REV:tz (ретро) → ORCH → GATE:done.

- **A1 Ретро-план** (архитектор grok): файл `HF-plan_exchange-contact-upsert_20260908.md` (таблица факт + шаги A3-A4). Объект для plan-approve.
- **A2 Дыры кода** (исполнитель composer): реэкспорт `upsert_from_source` в `__init__.py`; `cmd_bootstrap` → цикл `upsert_gal_result`/merge_to_enc_only (не md-merge persist); email required (create без email → не создавать, status=unchanged+conflicts).
- **A3 Тесты OrgLookup** (новый `test_upsert_gal.py`): upsert create, dry-run не трогает enc, VPN→exit 2, login не теряется, KeyError-regression, bootstrap без md-merge persist. Прогон обоих проектов.
- **A4 docs-handoff** (после green A2-A3): оба ТЗ → статус «реализовано 08.09», версия 0.3.0, убрать «на диске: нет»; инвентарь 0.3.0+факт тестов.
- **A5 REV:tz**: реальный прогон `claude-sonnet-5-medium` по разделам (рекомендую, флаг был ON); снимать только явной фразой Саши.
- **A6 Граф**: завести канонический `DEV/exchange-contact-upsert` (audit trail); off-board фазы → complete + comment `done off-board, session ids`; unarchive 07.09 нельзя.

# B. Безотказность цепочек (ключевое требование Саши)

**Корень 08.09:** оркестратор интерпретировал «делай в 1 проход» как «один agent -p исполнителя»; скилл помогал (двусмысленность «одним заходом»). One-pass по канону = авто-снятие HITL-гейтов, НЕ склейка ролей/фаз.

**Решение (карточки + гейт-инвариант + preflight):**
- **B1** GLOSSARY §5.2: таблица обязательных фаз по кейсу (TZ-WRITE+HF-TAIL полный набор; skip только по правилам кейса).
- **B2** Скрипт `~/WorkVault/Registries/pipeline_gate_done_preflight.py`: проверяет наличие графа, всех фаз done, артефактов (план, ТЗ без «на диске: нет»), REV-флаг, эвристику свёртки (один session_id на разных ролях). Exit≠0 → GATE:done запрещён, comment с чек-листом.
- **B3** Модель/роль на карточке (metadata), воркер `agent -p` только свою роль; шаблон «одна роль; чужие фазы не выполнять».
- **B4** Создание графа после BRIEF-CLOSE: любой TZ/HF `agent -p` без корня → стоп.

**Как оркестратору «1 проход» правильно:** не схлопывать фазы. TZ-WRITE = stabilize/compress/patch/[REV]/finalize отдельными карточками и `agent -p`. HF:plan обязателен перед plan-approve. GATE:done — только после preflight exit 0.

**Правки:** GLOSSARY 0.2.1, tz-workflow 2.2.0, hermes-feature 2.3.0 (главный фикс формулировки «одним заходом»→авто-гейты), DevKanbanPipeline 0.2.2 (каталог, preflight, off-board, вычистить «GATE:done запрещён»), ProcessImprovement Блок 5 закрывается.

**Не делать:** новый скилл chain-guard; форк kanban-worker; правка schema; авто-крон preflight.

# Порядок внедрения (два контура, не смешивать)
- **Контур 1 — закрыть exchange (A):** граф → план-файл → impl дыр → тесты → docs → REV:tz → preflight → GATE:done.
- **Контур 2 — безотказность (B):** отдельный CHANGE (DEV/chain-enforcement или секция ProcessImprovement): GLOSSARY → скиллы → DevKanbanPipeline → скрипт. Исполнителю A не давать править скиллы, и наоборот. Два последовательных PLAN-IMPL-TAIL.