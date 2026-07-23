# Анализ bloat скиллов и план доработки (22.07.2026)

## Корневая причина разрастания скиллов

1. **Append безопаснее edit+compress** — LLM предпочитает добавить в конец (низкий риск потери контента, меньше токенов на операцию), а не переработать существующее.
2. **LLM не видит текущий размер** скилла при добавлении — нет автоматического размерного ограничения.
3. **Питфолл принадлежит скиллу-обнаружения, не скиллу-применения** — обнаружил баг в MOFS, добавил питфолл в `hermes-feature`, хотя он должен быть в `mofs-operations`.
4. **skill-authoring v1.0 молчит** про размер, дедуп, язык.

## Реальные размеры (22.07.2026)

| Скилл | Размер | Статус |
|---|---|---|
| `about_usr_skills` | ~117k | 🔴 критично — нужна структуризация в references/ |
| `hermes-feature` | ~88k | 🔴 критично |
| `mofs-operations` | ~35k | 🟡 borderline |
| `skill-authoring-principles` | ~4k | ✅ хорошо |

12+ скиллов пробили soft-порог 14-20k.

## Стратегия языка (рекомендация Opus)

**Гибрид (вариант 2):**
- English: правила, процедуры, чек-листы, таблицы (−40% токенов, upstream-совместимо)
- Русский только: прямые цитаты Саши, даты+имена-специфичных прецедентов, блоки `> Context (RU):`

Полный English теряет grep по русским фразам-триггерам. Полный русский избыточен по токенам.

## Открытые вопросы (бриф с Сашей, начат 22.07.2026)

1. `skill-health-check.sh` расположение: `~/.hermes/scripts/` или `~/WorkVault/Hermes-Backlog/scripts/`?
2. Порог oversized_soft: 15k или 20k?
3. Семантический дедуп питфоллов — в v2.0 или отдельным ТЗ позже?
4. Миграция русских скиллов в гибрид — массово через крон или по-одному при следующей правке?

## Детальный план — файл

`~/WorkVault/Hermes-Backlog/TZ/skill-authoring-selfcheck-plan.md`

## Краткий план действий

**A. skill-authoring-principles → v2.0** (Sonnet по плану из файла выше)
- Добавить: Write Discipline (merge>append, size gates 15k/25k, version bump, compression pass)
- Добавить: Pitfall Ownership, Size Budget & References, Language Policy, Self-Check Hooks
- Добавить: Self-update workflow (create vs update, cross-ref check, backup rules, semver, post-update verify)
- Добавить: Python-скиллы и MCP-скиллы (структура, зависимости, тестирование, граница 200 строк)
- Убрать: раздел «Критерий выбора модели» (зона hermes-feature)
- Убрать: раздел «Синхронизация с зеркалами» → в tz-workflow или references/
- Итог: ~4-5k SKILL.md + references/

**B. Создать `~/.hermes/scripts/skill-health-check.sh`** (no_agent bash)
- Метрики: размеры, broken related_skills, orphan .usage.json, frontmatter lint, version-bump эвристика
- Вывод: `--json` (парсеры) и `--report` (5-10 строк для vm_selfcheck)

**C. Патч vm_selfcheck**
- Добавить шаг «Гигиена скиллов»: запуск скрипта из B
- При hard-oversize/broken refs → рекомендация в отчёт (не inline-правка)
- Добавить `skill-authoring-principles` в `skills: [...]` крона

**D. Тестирование**
- Валидный JSON, отчёт ≤10 строк
- Через 4 недели: число >15k скиллов не выросло, ≥1 сокращён, 0 broken refs
