# ErrorBus триаж: «исследуй и почини ошибки по канону»

Когда Саша шлёт дайджест ErrorBus («3 ошибок, 2 уникальных») и просит `почини ошибки по канону` — цель разделить открытые записи на **реальные баги** (канон BUGFIX через `hermes-feature`) и **не-баги** (провайдер-недоступность / уже починенные FPR / фоновые аудиты) и закрыть последние. Канон: провайдер-недоступность LLM ≠ баг, система штатна; только внутренние дефекты чинятся.

## CLI-инструмент триажа

`~/.hermes/scripts/error_bus_cli.py` (БД `~/.hermes/error_bus/events.db`):

```bash
python3 error_bus_cli.py status                        # open_errors / open_critical / last_event
python3 error_bus_cli.py list --status open --limit 30 # все открытые
python3 error_bus_cli.py list --tool <Name>            # по инструменту
python3 error_bus_cli.py show <id>                     # деталь записи
python3 error_bus_cli.py resolve <id> --note "..."     # закрыть с причиной
```

## Порядок триажа

1. `status` + `list --status open` — полная картина (дайджест за 24ч ≠ весь список open; открытых всегда больше).
2. Для каждого `-critical` `show <id>` → читать **`detail`**, НЕ только `message` (сообщение одинаковое, механизм разный).
3. Классифицировать по `detail` (см. таблицу ниже). Реальные баги — в канон BUGFIX (отдельный граф для каждого слага). Не-баги — `resolve` с `--note` на русском: «класс, почему не баг, что стало с поездом». Через CLI, ни `DELETE`, ни сырого `UPDATE` в events.db.
4. Для каждого слага из `detail` (`slug=... phase=...`) проверить, дошёл ли поезд до `GATE:done`: `grep 'GATE:done' '~/WorkVault/Hermes-Backlog/dev/<slug>/journal.md'` + `python3 -c "import json;json.load(open('~/WorkVault/Hermes-Backlog/dev/<slug>/_state.json'))['status']"`. Если поезд доведён до done — сбой был транзиентным, запись закрывается.

## Таблица классификации по `detail`

| detail | Класс | Действие |
|---|---|---|
| `provider-fatal: rc=1 json error: Selected model is at capacity` | провайдер-недоступность (модель перегружена) | resolve — не баг, поезд при повторном invoke-role доехал |
| `provider-fatal: rc=0 pattern='request timed out' hit='request timed out'` | **ложный** provider_fatal по цитате паттерна — корень починен (классификатор `_fatal_reason` трёхзначный, не бьёт по цитате) | resolve — уже починенный FPR-класс |
| `provider-fatal: rc=2 (rc in [2, 3])` | провайдер-недоступность Codex | resolve — не баг |
| `ActionRequiredError: out of usage` в detail аудита | provider failure, НЕ audit evidence | не баг; решение о реальной аномалии — только детерминированный SQL, не этот текст |
| реальный дефект пайплайна/инструмента | внутренний баг | канон BUGFIX (см. `hermes-feature` Блок 6В) |

## Ключевой питфолл

`dev_workflow ... role=architect|reviewer|executor backend=codex` — почти всегда провайдер-недоступность Codex/Cursor (модель gpt-6.1-sol перегружена, таймаут, rc∈[2,3]), а НЕ баг пайплайна. НЕ заводить BUGFIX-граф по каждой такой записи влет. Правило: читать `detail`, проверить что слага-поезд дошёл до `GATE:done`, затем **resolve**. Отдельная грань — «класс ошибки откатился»: если `dev_workflow` падает ПОСЛЕ закрытого багфикс-графа, сверить `detail` свежих событий: другой механизм (лимит vs лексика vs транспорт) = другой баг, новый BUGFIX под новым слагом, не ре-опен старого.

## Гигиена после закрытия

- Сверять `status` до/после — `open_errors` должен упасть на число закрытых.
- Реальные находки (например `SkillSizeMonitor` переразмеры >25k) — НЕ resolve как FPR: это работа по канону `all-skills-hygiene` (делегированное сжатие), их показать и спросить.
- Реальные «сигналы» (PIIScan находки, UpstreamMonitor breaking changes, LLMAnomalyScan monster) — фоновые аудиты, отдельные от задачи «почини ошибки»; трогать только при явном запросе.
