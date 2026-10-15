# Хранение ТЗ и архивация

Операционная копия для оркестратора `dev-workflow`. **Норматив смысла:** master `~/WorkVault/Hermes-Backlog/TZ/DevWorkflow/DevWorkflow_TZ.md` **Б15**, **Б38**; на диске также `TZ/TZ-Workflow/TZ-storage-system.md`, `TZ/_TZ-WORKFLOW-RULES.md`, инварианты скилла `tz-workflow`.

**Выжимка `extract.md` и этот файл ≠ SoT.** При расхождении с master-ТЗ или дисковыми правилами — открыть master / `TZ-storage-system`.

Процедура фазы `HF:backup` и рецепты — `canon.md`, `cases/CHANGE.md` (здесь не дублируем `pipeline next`). Волны W0–W4 и откат на канбан — `rollback.md`. Read-only архив канбана — `kanban-mechanics.md`.

---

## Хранение ТЗ

| Что | Куда |
|---|---|
| Живое master-ТЗ | `TZ/<Tool>/<Tool>_TZ.md` (версия **только** во frontmatter; папка и файл — **латиница**) |
| Доработка | новая датированная секция **в том же файле**, не новый живой файл |
| Приложение | `TZ/<Tool>/appendix_<тема>_YYYYMMDD.md` + таблица `## Приложения к ТЗ` в master |
| Реестр | `TZ/MAIN_TZ_INVENTORY.md` — после любой **структурной** записи ТЗ (`LOCK_EX`) |
| Снапшот перед крупной перепиской | `~/WorkVault_backup/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz` |
| Архив ТЗ | только при **DECOMM** инструмента → `~/WorkVault_backup/Hermes-Backlog/TZ/_archived/<Tool>/` |
| Runtime | **не** в `TZ/<Tool>/` — state слага `dev/<slug>/`, код `pipeline/` / `USERTOOLS/<Tool>/` |

Инварианты (не ослаблять):

1. Один живой master-файл на инструмент — не множить `v1.md` / `v2.md` в активной папке.
2. Новые имена файлов и папок — только ASCII (латиница).
3. Версия — YAML-frontmatter (`version:`), не в имени живого файла.
4. Брифы, research, runtime-json, логи, `_sandbox/` — в директории инструмента, не в `TZ/<Tool>/`.
5. Точечное ТЗ не к инструменту: `TZ/_misc/TZ-<topic>-<YYYYMMDD>.md` (topic латиницей).
6. **`TZ:finalize`** любого кейса = запись/секция master-ТЗ **и** строка инвентаря. Без инвентаря finalize не complete (evidence — оба пути).

Полный TZ-WRITE (стабилизация, compress, REV) — скилл `tz-workflow`; машина фаз — этот скилл.

---

## Три контура архивации

Контуры **не смешивать**. Ночной полный tgz WorkVault (контур C) не заменяет фазу `HF:backup` (контур A).

| Контур | Что защищает | Куда | Когда | Кто | Ретеншн |
|---|---|---|---|---|---|
| **A. Прикладной / конфиги Hermes** | затронутые деревья: скилл, `pipeline/`, при необходимости `config.yaml` / `jobs.json` | `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` | фаза **`HF:backup`** до `HF:impl`; задачи архитектора — всегда; исполнитель — если тронут `config.yaml` или `jobs.json` | оркестратор (**G6:** Cursor-роль на `HF:backup` **не** звать) | 2 недели, ≤1 бэкап в день; self-check чистит |
| **B. Снапшот master-ТЗ** | папка `TZ/<Tool>/` | `~/WorkVault_backup/Hermes-Backlog/TZ/<Tool>/<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz` | перед крупной перепиской (см. ниже) | оркестратор / TZ-WRITE по правилу снапшота | последние **5** tgz на инструмент |
| **C. Полный WorkVault** | весь `~/WorkVault/` | `~/WorkVault_backup/_full-WorkVault-backup/WorkVault_full_YYYY-MM-DD_HH-MM-SS.tgz` | крон **`full_workvault_backup`** ежедневно **23:30**; или прямая команда Саши («сделай бэкап WorkVault») | скилл `full-workvault-backup` + `~/.hermes/scripts/full_workvault_backup.sh` | последние **5** архивов |

Контур C — защита от **логических** ошибок (случайное удаление/перезапись через rclone), не от падения ВМ целиком. Скрипт архивирует `~/WorkVault`, не `~/WorkVault_backup`. rclone sync — `workvault-sync-infra`, не этот контур.

`~/WorkVault_backup/` — VM-only, **не** синкается ownCloud. С ноутбука виден только `~/WorkVault/`; архивацию с удалённой LLM делать на ВМ.

Детали контура C (триггеры, питфолы): скилл `full-workvault-backup`. Детали контура A (откат авария vs план): `hermes-feature` Блок 5 — смысл совпадает с таблицей выше.

---

## Снапшот ТЗ и DECOMM

Зеркало путей WorkVault в `~/WorkVault_backup/`:

1. **Крупная правка** (>20% содержимого или смена major) — tgz всей папки инструмента: `…/<Tool>_TZ_snapshots-YYYYMMDD-HHMM.tgz` (контур B).
2. **Мелкая правка важного ТЗ** — `.bak` в backup (хранить **1**, перезапись).
3. Старая версия полностью перекрыта — файл в backup: `<Tool>_TZ_v<old>_YYYYMMDD.md`.
4. **Инструмент снят (DECOMM)** — вся `TZ/<Tool>/` → `…/TZ/_archived/<Tool>/`; в инвентаре `archived`.

**Пока инструмент используется**, master остаётся `active` в WorkVault. Завершение доработки ≠ архивация. Решение — явная фраза Саши (`удаляй` / DECOMM), **без автотаймера**.

Ретеншн снапшотов: **5** tgz на инструмент; `.bak` — 1; устаревшие `.md` в backup — пока Саша не сказал чистить. Журнал переносов: `~/WorkVault_backup/_moved-YYYY-MM-DD.log` (один файл на день, append). Явный мусор (пустые, идентичные дубли, `*.md~`) — удалять, не архивировать.

---

## Откат и CRISIS

| Ситуация | Действие |
|---|---|
| Откат контура A (прикладной) | **Авария** → архитектор восстанавливает немедленно; **плановый** → архитектор предлагает, ждёт ОК Саши |
| Старые скиллы процесса (W0–W4) | git-история `hermes-workspace` + tarball `~/.hermes/_Archives/hermes-backup-…` и целевой `…/devworkflow-W4-old-skills-…`; retention до явного «удаляй», не автотаймер |
| CRISIS «в индексе есть, папки нет» | восстановление из `_Archives` / git, не «из воздуха» |
| `abort` / откат слага | папку `dev/<slug>/` **не** удалять — read-only архив попытки |
| Откат на канбан | `rollback.md`; **не** `rm` `kanban.db`; **не** `rm` `_state.json` пилота |

---

## Что не делать

- Заводить **четвёртый** корень архива или USERTOOL «ради бэкапа».
- Ставить **второй** крон полного WorkVault без глагола Саши **`ставь кроны`**.
- Считать ночной tgz (контур C) заменой **`HF:backup`** (контур A).
- Класть runtime слага (`_state.json`, выжимки, журнал) в `TZ/<Tool>/`.
- **`rm`** `kanban.db` или `_state.json` при откате.
- Переписывать **тела** `hermes-feature`, `tz-workflow`, `full-workvault-backup` вместо ссылок из этого справочника.
- Заводить **`[NEW-ENTITY]`** для бэкапа/архива без согласования Саши.
