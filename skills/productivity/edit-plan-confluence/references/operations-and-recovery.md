# Контекст и настройки: этап 02

Источник несекретных значений — `WorkVault/Registries/EcosystemConfig.yaml`, секция существующего `tools.edit_plan_confluence`, и shared WORKVAULT_PATH/CONFLUENCE_URL. Адаптер `scripts/env.py` использует установленный `~/.hermes/lib/usertools_config.py` с явным списком ключей и его штатным приоритетом. Нового `.env` или env-алиасов нет. Архивный контекст не вызывает credential loader. Секретный источник — штатный usertools_env (в этом окружении `~/.config/hermes/.env`) и процессное окружение; при unified_only локальный ConfluenceSync `.env` не читается. Явный аргумент legacy `load_confluence_env(path)` оставлен для совместимости.

| Ключ | Значение | Единицы / границы |
|---|---|---|
| CACHE_DIR | `~/.cache/edit-plan-confluence` | disposable каталог; тесты передают путь T |
| MPXJ_PYTHON | `/usr/bin/python3.9` | проверяется запуском JVM и API reader; отказ не считается успехом |
| MPP_READ_TIMEOUT_SECONDS | 180 | секунды; 1–86400; сохранён прежний timeout экспорта |
| HTTP_TIMEOUT_SECONDS | 120 | секунды; 1–86400; прежний timeout ConfluenceClient |
| HTTP_RETRY_LIMIT | 1 | 0–10; прежний одиночный conflict retry |
| MPP_MAX_BYTES | 67108864 | байты; 1–1099511627776 |
| ZIP_MAX_BYTES | 67108864 | байты; 1–1099511627776 |
| ZIP_MAX_ENTRIES | 128 | записи; 1–1000000 |
| ZIP_MAX_UNPACKED_BYTES | 268435456 | байты; 1–1099511627776 |
| ZIP_MAX_RATIO | 100 | безразмерное отношение; 1–1000000 |
| NORMALIZATION_PROFILE | normalization-v1 | установленный versioned профиль и fingerprint |
| SUMMARY_PROFILE | summary-v1 | выбранное имя; файл и применение — этап 08 |
| PLUGIN_PROFILE | installed-gantt-profile | выбранное имя; файл и проверка — этап 08 |

Размеры и верхние границы — выбранная ограничительная политика, проверяемая тестами, без заявления о benchmark или максимальной ёмкости MPXJ. Проверены schema/ranges и точная граница MPP/ZIP size checker (limit принимается, limit+1 отклоняется). Реальная защита распаковки ZIP относится к этапу 03; HTTP-настройки подключаются к сетевым стадиям в этапе 10. Выбор имён будущих профилей не означает их доступность/проверенность: snapshot показывает not_installed и null fingerprint.

`PlanContext.resolve(db=..., workvault=..., cache_dir=...)` принимает явные зависимости будущих глобальных CLI overrides без перезаписи YAML. Публичные флаги подключаются на этапе 04. Snapshot содержит несекретные значения, sources, пути, версии/fingerprints профилей и fingerprint контекста; operation resume позднее использует зафиксированный snapshot. Конфигурационные snapshots не являются semantic hash плана.

Python MPXJ использует штатное окружение процесса; в проверенном окружении `PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages`. Фактически проверены MPXJ 16.4.0, JPype 1.7.1 и чтение бинарных fixtures. Runtime-зависимости CLI зафиксированы в `requirements.txt` (PyYAML, jsonschema); MPXJ не устанавливается во второй interpreter автоматически.

Перед изменением E создан прикладной backup. В git сохраняются минимальный config diff, schema diff и контракт в stage-02/config; полный YAML и credentials в git не копируются. При повреждении cache перестраивать его только из verified frozen/archive bytes; отсутствие/неверный SHA источника — ошибка. БД, страницы, Gateway и расписания при проверках этапа 02 не изменяются.

## Вход и долговечные поступления: этап 03

Внутренний профиль `input-v1` использует те же значения MPP/ZIP из таблицы выше; E/schema не изменяются. `mpp_input.freeze_input(..., operation_id=..., workvault=..., settings=...)` получает явные зависимости, преобразует строковые лимиты unified loader по существующей schema и сохраняет байты до reader. Рабочее место — отдельный staging-каталог внутри `WorkVault/_plan-receipts/<operation-id>/input/`; проверяются открытый inode/device, size, mtime_ns, ctime_ns, повторное контрольное чтение и read-back копии. Файлы и каталог синхронизируются через fsync; завершение каталога атомарно. Исходный путь не перемещается.

ZIP определяется содержимым. Контейнер сохраняется отдельно с SHA-256; архив не распаковывается по недоверенным именам. Проверяются все записи, включая не-MPP: POSIX/Windows абсолютные пути и drive, `..`, обратные слеши, пустые компоненты, Unicode NFC/casefold-коллизии и конфликты файл/каталог, symlink и специальные типы, шифрование, число записей, суммарные и фактические распакованные байты, коэффициент распаковки, размер MPP и CRC. Размеры на точной границе разрешены. `multiple_mpp_candidates` содержит список; выбранного MPP и snapshot нет. Принятые транспортные байты остаются долговечными также при ошибке выбора; поступление хранит locator и hash контейнера.

`plan_operation.begin_import()` регистрирует operation/item до разрешения проекта и создаёт attempt. Повтор с известным operation ID сохраняет item и зафиксированный effective context, создаёт новый attempt ID и событие в MofsIndex. Неизвестный проект остаётся NULL; фиктивный plan/snapshot не создаётся. После freeze локатор/hash фиксируются typed writer; продолжение читает frozen source, проверяет его и ZIP-контейнер, не принимает изменённый исходный путь под прежним item.

Миграции `0007_durable_imports` и `0008_snapshot_semantics` добавляются после неизменённых 0001–0006. Перестроение nullable attempt и назначения выполняется транзакционно по схеме create/copy/drop/rename; foreign_keys временно отключается только на idle connection и восстанавливается в finally, перед commit обязателен foreign_key_check. До будущей миграции production следует использовать существующие `backup_to()` и `verify_backup()`; этап 03 мигрирует исключительно тестовые БД. `mofs_index/migrate.py` в текущем компоненте отсутствует; owner plan-миграций — `mofs_index/plan/migrate.py`.

`writer.commit_import_snapshot()` выполняет один BEGIN IMMEDIATE: snapshot → version-данные → item.snapshot_id → событие `snapshot_committed` → COMMIT. Вложенный независимый commit запрещён. Ключ включает plan, lineage, MPP SHA, representation, fingerprint нормализации с версиями reader/MPXJ/export/schema и normalized IANA timezone либо `unknown`; ограничения уникальности действуют в SQLite. Прежние snapshot с NULL-профилем сохраняются вне авто-дедупликации. Имя, ZIP hash, received_at и source_version_date не входят в область. До повторного использования проверяются artifact bytes/hash/размер, normalized JSON/hash и количества родительских/дочерних version-данных.

`plan_reconcile.reconcile_import()` сначала читает committed item/event, затем выполняет archive read-back и только затем вызывает необязательный writer файлового зеркала. Сбой после SQL commit, перед read-back или квитанцией оставляет те же ID; повторный reader/ingest не вызывается. Повреждение архива требует восстановления тех же байтов и нового read-back. Успешное локальное восстановление сообщает `published:false`, `external_effect:none`, `verification.archive:verified`. Работа с Confluence в этом контракте отсутствует.

Публичная сборка нового однопроходного save и глобальные CLI overrides относятся к этапу 04; batch freeze-all/обработка — к этапам 05–06. Этап 03 предоставляет внутренние API и доказательства их границ. Единственная адресная правка старого save — стабильная архивная lineage проекта вместо имени файла; старые линии сохранены отдельно.
