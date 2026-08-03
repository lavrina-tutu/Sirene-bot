# История верификаций AggregateFromMeetings ТЗ

## Уроки итераций 22.06.2026

### Почему было много циклов
1. Opus менял TZ_B, не обновлял IMPLEMENTATION_PLAN → Cursor находил рассинхрон → ещё 2 итерации
2. Попытка отправить Cursor «только изменённые файлы» → Cursor находил проблемы в «уже проверенном» → ещё итерация
3. Правка I4 (каскад owner+2+) была выполнена по критерию участников вместо критерия алиасов → J1 → ещё итерация
4. R10 (LLM-fallback) вставлен внутрь `determine_route` → противоречие с принципом «B без LLM» → MAJOR-A → вынесен в оркестратор

### Правило атомарности изменений
При изменении концепции алгоритма B (Шаги 0–6):
- TZ_B_classification.md
- IMPLEMENTATION_PLAN.md §1 B.determine_route
- IMPLEMENTATION_PLAN.md Этап 1.10
- TZ_A_sources.md (если касается owner-правила)

При изменении API модулей D/E:
- TZ_D/TZ_E
- IMPLEMENTATION_PLAN §1 D/E
- IMPLEMENTATION_PLAN Этапы 4/5

При добавлении нового поля в MeetingPackage (пример: `title`):
- TZ_A_sources.md §В2 (список полей)
- IMPLEMENTATION_PLAN §0.2 (models.py)
- Реальный `models.py` в USERTOOLS
- `ff_parser.py` / `a_sources.py` (где заполняется)

### Ключевые инварианты ТЗ (проверять при каждой правке)
- Алгоритм B: шаги 0, 0.5, 1, 1', 2, 3, 4, 5, 6 — ветки 1on1 (Шаг 2) и multisync (Шаг 5) достижимы
- **B — чистый Python без LLM** — инвариант нарушать запрещено. LLM-fallback (R10) живёт в оркестраторе (F/bootstrap), не в `determine_route`
- owner-правило = фоллбэк, не override Шагов 0–6
- Каскад owner+2+ ветвится по числу АЛИАСОВ (не участников): 2+ алиасов→multisync, 1 алиас→project
- Сигнал «1-1» + 2 участника → route=1on1 ДО Шага 1 (Шаг 0.5)
- negative_keywords блокирует алиас, не проект
- route_project_slug живёт в MeetingPackage (не MeetingSignals)
- Таблица имён — через ContactStore из tutu-contacts.md, не Python-константа
- `pre_classify` сигнатура: `(summary_text, title, known_projects, context) → PreClassifyResult` — не старая `(pkg, classification_memory) → str|None`

## Карта верификаций
| Версия/Пакет | Итог | Главная причина отказа |
|--------|------|----------------------|
| v1.5 | CHANGES REQUESTED | 3 CRITICAL (slug-хаос, route_project_slug, Confluence trigger) |
| v1.5.1 | APPROVED | — |
| v1.5.3 | CHANGES REQUESTED | Шаг1/Шаг6 противоречие, negative_keywords |
| v1.5.4 | CHANGES REQUESTED | R4 сломал ветки 1on1/multisync, route=1on1 не работал для «1-1/alias» |
| v1.5.5 | CHANGES REQUESTED | Рассинхрон план↔TZ_B (менялся только TZ_B) |
| v1.5.6 | APPROVED | — |
| v14 (1-я ред.) | CHANGES REQUESTED | MAJOR-A: R10 вставлен в determine_route (нарушение «B без LLM»); MAJOR-B: сигнатура pre_classify в плане vs TZ_C |
| v14 (2-я ред.) | APPROVED | — (5 косметических MINOR, не блокеры) |
