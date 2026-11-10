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

## Откат бэкенда Codex→Cursor — ОТМЕНЁН (решение Саши 10.11.2026)

**Курсор больше не используется.** Все роли dev-workflow и подскиллов работают **только через codex backend** (`default_backend: codex`), роли фиксированы: architect/reviewer `gpt-6-astra`, executor `gpt-6.1-sol`, compressor `gpt-6.1-terra`. Блок `roles_cursor` и миграция `migrate-dev-roles-cursor-to-codex` удалены/неприменимы. Откат на Cursor не производить.

## Что не делать при откате

- Не патчить `kanban_db.py` и ядро Hermes.
- Не импортировать kanban в `pipeline/`.
- Не удалять журнал `journal.md` пилота.

Текст баннера для W2: `dual_path_banner.md`. Эталон для тестов: `Registries/pipeline/tests/fixtures/dual_path_banner.md`.
