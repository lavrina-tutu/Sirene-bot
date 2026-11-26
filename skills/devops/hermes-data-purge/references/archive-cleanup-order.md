# Archive/backup cleanup order before VM handover

Порядок удаления архивов и копий при передаче инстанса — от наименее опасных к наиболее опасным для работы Hermes. Каждый шаг: предъявить состав (`search_files target=files`), «удаляй» от Саши, точечный `rm`, контрольный пересчёт живого оригинала.

## Группы (в порядке)

### 1. Служебные операционные `.bak` (не трогают runtime)
- `~/.hermes/error_bus/*.bak-*` — бэкапы журнала ошибок (живой `events.db` отдельно).
- `WorkVault/ProtocolFromSummary/_registry.json.bak-*`, `Meetings/NewMeetings/_registry_meet.json.bak-*` — копии реестров перед роутинг-фиксами (живые `_registry.json`/`_registry_meet.json` отдельно).

### 2. Резервные копии dev-workflow
- `WorkVault/Hermes-Backlog/dev/<task>/backup/*.tgz` и `evidence/*.tar.gz` — снапшоты invoke-этапов (живые `journal.md`/`_state.json`/evidence `.json` не трогать). Широкий `find -delete` тут блокируется — собирать список и `rm` по явным путям.

### 3. Ротационные снапшоты навыков (curator)
- `.curator_backups/` в `~/.hermes/`, `~/.hermes/skills/`, `~/.local/share/hermes/skills/`, `hermes-workspace/skills/`, `hermes-config/skills/`, `hermes-config-repo/skills/`. Удалять папки `.curator_backups` целиком; живое дерево навыков (`SKILL.md` рядом) не трогать — сверять счётчик SKILL.md до/после.

### 4. Изолированные крупные копии данных (не runtime, но большие)
- `~/WorkVault_backup/` — полный tgz WorkVault (живой `~/WorkVault/` отдельно).
- `~/WorkVault/Hermes-Archive-1/hermes-data-*.tar.gz` — архив данных Hermes.
- `~/windows-cutover-staging/` — пакеты переноса (держать, пока проект переноса не завершён, потом удалить).

### 5. Бэкап own purge — последним
- `~/_sasha_handback_backup_<date>/` — снимок state.db для отката очистки; единственная точка восстановления. Удалять только после подтверждения, что вся прочая чистка успешна (Q-3: личную recovery-копию не оставлять).

## Ловушка glob-ов
Файлы одной семьи с разными суффиксами не ловятся одним паттерном: `kanban.db.bak-*` пропускает `kanban.db.bak_tzpatch_invertedfix`, `events.db.bak-*` пропускает `reconcile.py.bak-*`. После каждой удачной партии делать контрольный `search_files target=files` на весь каталог, а не на уже использованный glob.
