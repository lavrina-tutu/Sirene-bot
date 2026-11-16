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
