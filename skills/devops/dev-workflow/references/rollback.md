# Откат и волны миграции W0–W4

Мастер-ТЗ: DevWorkflow **Б31**, **Б31.1**. Канбан **не удалять** до W4 и явного согласования Саши.

## Волны (кратко)

| Волна | Суть | Канбан |
|---|---|---|
| **W0** | канон в скилле; DKP помечен superseded-runtime; старые скиллы на месте | живой |
| **W1** | `pipeline/` + тесты; боевые слаги не кормить pipeline | живой |
| **W2** | пилот **один** слаг в `pilot_slugs`; баннер dual-path в `hermes-feature` / `tz-workflow` | живой для остальных |
| **W3** | остальные кейсы по одному; `mode: dual-path` | запасной путь |
| **W4** | история в journal; dispatch off; старые скиллы в архив | выключен по плану |

Конфиг: `orchestration.mode` — `kanban-primary` (W1) → `dual-path` (W2–W3) → `workflow-only` (W4 / чистая установка). Список `pilot_slugs` — только слаги, которые ведёт `dev-workflow`.

## Откат на любой волне (приоритетная процедура)

1. **Не** `rm` `~/.hermes/kanban.db`.
2. **Не** `rm` `dev/<slug>/_state.json` пилота (папка остаётся для разбора).
3. Вернуть симлинки старых скиллов из git / `_Archives` при необходимости.
4. `restore-all-skills.sh`.
5. Dispatch: вернуть прежнее значение в конфиге (если меняли на W4).
6. `pipeline status --check` может быть красным после отката — нормально; зафиксировать info в ErrorBus «rollback».

## W2/W3: вернуть один слаг на канбан

Глагол operator: **`rollback-to-kanban`** (не разговорный синоним вне словаря).

1. Убрать slug из `orchestration.pilot_slugs` (или оставить dual-path только для других).
2. На канбане: снять паузу dispatch для слага (`dispatch-resume` / комментарий по процедуре канбана).
3. `pipeline operator-done --verb rollback-to-kanban --evidence "…"` с фактом (дата, rc, цитата).
4. Папку `dev/<slug>/` не удалять — read-only архив попытки.

Два поезда на одном slug запрещены: сначала остановить pipeline-ход, потом включить канбан.

## Откат dual-path целиком

Если `pilot_slugs=[]` и `mode=kanban-primary`:

1. Шаги общего отката выше.
2. **Снять баннер W2:** `git checkout` файлов `hermes-feature/SKILL.md` и `tz-workflow/SKILL.md` в hermes-workspace (только верхние 10–15 строк баннера, не тело скиллов).
3. `restore-all-skills.sh`.

Откат **одного** слага из allowlist баннер **не** снимает.

## Откат бэкенда Codex→Cursor (Б45.7, после flip)

Чеклист миграции `migrate-dev-roles-cursor-to-codex`. Выполняет **только ORCH** в ответственном окне, живой поезд завершён, wrapper'ы не живы.

1. **YAML** — в боевом `tools.dev_workflow.invoke`: `default_backend: cursor-cli`; `codex_pilot_slugs: []` (снять pilot, если остался). `roles_cursor.*` обязаны быть заполнены: architect `cursor-grok-4.6-high`, reviewer `claude-sonnet-5-medium`, executor `composer-2.5`.
2. **`roles.*` Codex можно оставить** в файле — resolver при `cursor-cli` их **не использует** (Б45.3); `executor_light` на Cursor **не** читается — LIGHT идёт в `roles_cursor.executor`.
3. **`invoke_role` контроль** — прогон на architect / reviewer / executor (обычный и LIGHT-кейс) должен звать `agent -p` с моделями `roles_cursor.*`; модель `phases[phase].model` = та же, что в argv, уже на `invoke_prepare`. Journal: `backend=cursor-cli`.
4. **Не откатывать частично** — код нового resolver+Codex остаётся (операционный откат это не трогает). Откат «старый resolver поверх новых roles» запрещён: только согласованный комплект pipeline+YAML из HF:backup.
5. `restore-all-skills.sh`, штатная сверка канонa.

## Что не делать при откате

- Не патчить `kanban_db.py` и ядро Hermes.
- Не импортировать kanban в `pipeline/`.
- Не удалять журнал `journal.md` пилота.

Текст баннера для W2: `dual_path_banner.md`. Эталон для тестов: `Registries/pipeline/tests/fixtures/dual_path_banner.md`.
