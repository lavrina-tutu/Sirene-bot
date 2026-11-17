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
| SUMMARY_PROFILE | summary-v1 | установленный версионированный профиль |
| PLUGIN_PROFILE | installed-gantt-profile | проверенный профиль и ссылки на evidence |

Размеры и верхние границы — выбранная ограничительная политика, проверяемая тестами, без заявления о benchmark или максимальной ёмкости MPXJ. Проверены schema/ranges и точная граница MPP/ZIP size checker (limit принимается, limit+1 отклоняется). Защита ZIP и HTTP-настройки подключены в выполненных этапах 03/10. Статус и fingerprint каждого профиля фиксируются фактическим контекстом операции.

`PlanContext.resolve(db=..., workvault=..., cache_dir=...)` принимает явные глобальные CLI overrides без перезаписи YAML. Публичные флаги доступны через cli.py. Snapshot содержит несекретные значения, sources, пути, версии/fingerprints профилей и fingerprint контекста; operation resume использует зафиксированный snapshot. Конфигурационные snapshots не являются semantic hash плана.

Python MPXJ использует штатное окружение процесса; в проверенном окружении `PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages`. Фактически проверены MPXJ 16.4.0, JPype 1.7.1 и чтение бинарных fixtures. Runtime-зависимости CLI зафиксированы в `requirements.txt` (PyYAML, jsonschema); MPXJ не устанавливается во второй interpreter автоматически.

Перед изменением E создан прикладной backup. В git сохраняются минимальный config diff, schema diff и контракт в stage-02/config; полный YAML и credentials в git не копируются. При повреждении cache перестраивать его только из verified frozen/archive bytes; отсутствие/неверный SHA источника — ошибка. БД, страницы, Gateway и расписания при проверках этапа 02 не изменяются.

## Вход и долговечные поступления: этап 03

Внутренний профиль `input-v1` использует те же значения MPP/ZIP из таблицы выше; E/schema не изменяются. `mpp_input.freeze_input(..., operation_id=..., workvault=..., settings=...)` получает явные зависимости, преобразует строковые лимиты unified loader по существующей schema и сохраняет байты до reader. Рабочее место — отдельный staging-каталог внутри `WorkVault/_plan-receipts/<operation-id>/input/`; проверяются открытый inode/device, size, mtime_ns, ctime_ns, повторное контрольное чтение и read-back копии. Файлы и каталог синхронизируются через fsync; завершение каталога атомарно. Исходный путь не перемещается.

ZIP определяется содержимым. Контейнер сохраняется отдельно с SHA-256; архив не распаковывается по недоверенным именам. Проверяются все записи, включая не-MPP: POSIX/Windows абсолютные пути и drive, `..`, обратные слеши, пустые компоненты, Unicode NFC/casefold-коллизии и конфликты файл/каталог, symlink и специальные типы, шифрование, число записей, суммарные и фактические распакованные байты, коэффициент распаковки, размер MPP и CRC. Размеры на точной границе разрешены. `multiple_mpp_candidates` содержит список; выбранного MPP и snapshot нет. Принятые транспортные байты остаются долговечными также при ошибке выбора; поступление хранит locator и hash контейнера.

`plan_operation.begin_import()` регистрирует operation/item до разрешения проекта и создаёт attempt. Повтор с известным operation ID сохраняет item и зафиксированный effective context, создаёт новый attempt ID и событие в MofsIndex. Неизвестный проект остаётся NULL; фиктивный plan/snapshot не создаётся. После freeze локатор/hash фиксируются typed writer; продолжение читает frozen source, проверяет его и ZIP-контейнер, не принимает изменённый исходный путь под прежним item.

Миграции `0007_durable_imports` и `0008_snapshot_semantics` добавляются после неизменённых 0001–0006. Перестроение nullable attempt и назначения выполняется транзакционно по схеме create/copy/drop/rename; foreign_keys временно отключается только на idle connection и восстанавливается в finally, перед commit обязателен foreign_key_check. До будущей миграции production следует использовать существующие `backup_to()` и `verify_backup()`; этап 03 мигрирует исключительно тестовые БД. `mofs_index/migrate.py` в текущем компоненте отсутствует; owner plan-миграций — `mofs_index/plan/migrate.py`.

`writer.commit_import_snapshot()` выполняет один BEGIN IMMEDIATE: snapshot → version-данные → item.snapshot_id → событие `snapshot_committed` → COMMIT. Вложенный независимый commit запрещён. Ключ включает plan, lineage, MPP SHA, representation, fingerprint нормализации с версиями reader/MPXJ/export/schema и normalized IANA timezone либо `unknown`; ограничения уникальности действуют в SQLite. Прежние snapshot с NULL-профилем сохраняются вне авто-дедупликации. Имя, ZIP hash, received_at и source_version_date не входят в область. До повторного использования проверяются artifact bytes/hash/размер, normalized JSON/hash и количества родительских/дочерних version-данных.

`plan_reconcile.reconcile_import()` сначала читает committed item/event, затем выполняет archive read-back и только затем вызывает необязательный writer файлового зеркала. Сбой после SQL commit, перед read-back или квитанцией оставляет те же ID; повторный reader/ingest не вызывается. Повреждение архива требует восстановления тех же байтов и нового read-back. Успешное локальное восстановление сообщает `published:false`, `external_effect:none`, `verification.archive:verified`. Работа с Confluence в этом контракте отсутствует.

Публичный однопроходный save, глобальные пути и batch freeze-all/обработка подключены этапами 04–06. Архивная lineage проекта стабильна и не зависит от имени файла; старые линии сохранены отдельно.

## Сетевые стадии и восстановление (этап 10)

Публичный вход — `scripts/cli.py`. Настройки читает существующий unified loader;
нового `.env`, сервиса, БД или расписания нет. Контекст операции фиксирует
эффективные значения и источники. Resume использует этот контекст.

| Параметр | Текущее значение | Контракт |
|---|---:|---|
| `HTTP_TIMEOUT_SECONDS` | 120 секунд | integer 1…86400; таймаут одного HTTP-вызова/чтения сокета |
| `HTTP_RETRY_LIMIT` | 1 | integer 0…10; число дополнительных попыток |
| `MPP_READ_TIMEOUT_SECONDS` | 180 секунд | отдельный timeout reader, без изменений этапом 10 |

Значения находятся в `Registries/EcosystemConfig.yaml`, типы и диапазоны —
в существующей schema и `references/schemas/settings.schema.json`.
Этап 10 не меняет конфиги и прежние миграции. Указанные числа — установленный
контракт, не измеренная гарантия производительности.

Транспорт повторяет только GET, максимум `1 + HTTP_RETRY_LIMIT` попыток:
408/429/500/502/503/504 и транспортные ошибки. Между ними 0.25, 0.5, … секунд,
не более секунды на паузу. Остальные HTTP-ошибки возвращаются сразу.
POST/PUT транспорт автоматически не повторяет. Исход записи сначала
разрешается свежими GET. После 409 новый патч строится из свежего storage;
число PUT в операции ограничено тем же `1 + HTTP_RETRY_LIMIT`, включая resume.
Для незавершённого upload/create каждая разрешённая повторная запись также
требует чтения фактической цели и ограничена сохранённым счётчиком намерений.
`conflictPolicy=override` не используется.

GET конкретного вложения передаёт `version=N`, без `status`. Metadata обязаны
совпасть по page/container, ID, title и версии; затем скачиваются байты N.
Текущая версия проверяется отдельно. Историческая N не заменяет текущую N+1.

Стадии: `prepared → archived → admitted → attachment_uploaded →
attachment_verified → storage_written → storage_verified → confirmed`.
Стадия может завершиться чтением уже существующего результата без записи.
Перед эффектом в MofsIndex добавляется intent и файловое зеркало; после —
наблюдение. Ошибка журнала или зеркала блокирует дальнейшую запись/успех.
Архивные байты, admission, версии профилей и исходный snapshot проверяются
повторно до исполнения. Prepared JSON отправляется сохранёнными байтами.

```text
cli.py --db <тот-же-index.sqlite> --workvault <тот-же-WorkVault> --cache-dir <cache> operation show --operation-id <id>
cli.py --db <тот-же-index.sqlite> --workvault <тот-же-WorkVault> --cache-dir <cache> resume --operation-id <id>
```

Для AB требуется заново передать `--allow-live-ab` перед `resume`.
Отсутствующий обязательный slug/однозначный binding и старый неполный сетевой
контекст дают `operation_context_incomplete`: нужен новый `diff --project-slug`.

| Наблюдение | Продолжение |
|---|---|
| POST мог состояться | Найти точное вложение; проверить ID/ожидаемый переход версии и bytes; подходящее не загружать повторно |
| PUT мог состояться | Проверить свежие storage и актуальное вложение; подходящее зарегистрировать локально без PUT |
| Изменился только соседний блок | Сохранить чужое содержимое; при необходимости патчить свежую версию |
| Изменился весь макрос, управляемый блок или актуальная версия вложения | `conflict / 4`; старую операцию не исправлять записью |
| Тот же source/profile/target актуален | `unchanged`, `published:true`, POST=PUT=0, без дублирующей публикации |
| Новая подготовка меняет только ожидаемое «Итого» | Только PUT storage; существующие bytes/версия вложения сохраняются |
| Ответ GET недоступен после записи | Неподтверждённый исход, `published:null`; восстановить доступ и выполнить resume |
| SQL подтверждён, файловое зеркало не записалось | Ошибка текущего вызова; resume проверяет цель и восстанавливает зеркало без новой публикации |
| Расписание впервые расходится после записи | Сохранить `schedule:mismatch` и внешний эффект; `failed / 5`, без автоматического rollback/подтверждения |

Конфликт или schedule mismatch требует разбора и новой подготовки по применимым
правилам; старую историю не редактировать. Само отсутствие наблюдения плагина
остаётся `schedule:not_verified`. Успешные байты и storage не повышают его.

`published:false` — до сетевого эффекта; `null` — после неподтверждённого эффекта;
`true` — только подтверждённая публикация/актуальный `unchanged`.
`external_effect`: `none`, `attachment_written`, `storage_written`, `unknown`.
Полное подтверждение одной транзакцией связывает snapshot, artifact,
page observation, admission, профили, diagnostics и квитанцию. Только этот
путь создаёт `verified_v1`; старые регистрации не повышаются автоматически.

Блокировка использует kernel flock в `_plan-receipts/.target-locks` общего
WorkVault: namespace/page и namespace/page/macro. Она не зависит от DB/cache
override. PID диагностический; живость определяет ядро. После смерти процесса
блокировка освобождается. Файлы блокировок не удалять: удаление inode позволяет
двум процессам получить разные блокировки. Для созданной дочки дополнительно
блокируется её фактическая цель. Это локальная блокировка общего WorkVault;
внешние процессы/другие хосты выявляются проверками версий и hashes.

Для создания дочки сохранены title, parent, macro IDs и storage. После потери
ответа выполняется полный поиск по точным parent/title и проверка макроса,
управляемого блока и актуального parent. Чужая/неоднозначная страница не
усыновляется, новые UUID при восстановлении не генерируются. Совместимый
адаптер без MPP остаётся `legacy_unverified`, с проверкой квитанций и эффектов.

Перед будущей миграцией рабочей БД необходим штатный backup MofsIndex и
`verify_backup`; приёмка использует только изолированные БД/WorkVault/cache.
Никакой автоматической миграции production-БД этим этапом не выполняется.

## Эксплуатация и источники — этап 12

Актуальные значения и sources фиксируются фактическим `PlanContext.snapshot()`
в evidence stage-12/config-sources.json; таблица выше — текущая политика,
а не обещание производительности. Проверять источники через `env.load_settings`
и `usertools_config.resolve_key`, не печатать всё окружение.

| Параметры | Владелец/источник при отсутствии override |
|---|---|
| WORKVAULT_PATH, CONFLUENCE_URL | shared в Registries/EcosystemConfig.yaml |
| CACHE_DIR, MPXJ_PYTHON | tools.edit_plan_confluence в том же YAML |
| MPP_READ_TIMEOUT_SECONDS, HTTP_TIMEOUT_SECONDS, HTTP_RETRY_LIMIT | tools.edit_plan_confluence |
| MPP_MAX_BYTES, ZIP_MAX_BYTES, ZIP_MAX_ENTRIES, ZIP_MAX_UNPACKED_BYTES, ZIP_MAX_RATIO | tools.edit_plan_confluence |
| NORMALIZATION_PROFILE, SUMMARY_PROFILE, PLUGIN_PROFILE | tools.edit_plan_confluence, содержание profiles/*.json из git |
| db | mofs_index.db.DEFAULT_DB_PATH, кроме явного --db |
| корни MppReader/MofsIndex | существующие tools.mpp_reader/mofs_index в EcosystemManifest.json |
| credentials | process env → usertools_env._HERMES_ENV (фактически ~/.config/hermes/.env) |

Приоритет loader: process env → установленный overlay → tool YAML → shared YAML →
central env → разрешённый по migration mode legacy. Секретные ключи не берутся из
YAML; `env.py` архивный путь их не загружает. Для credentials локальный ConfluenceSync
.env допустим только в not_started/dual_read или явном legacy mode;
фактический confluence_sync — unified_only. Не source-ить .env и не менять
~/.hermes/config.yaml. `--workvault/--cache-dir/--db` сильнее defaults только
для запуска; resume использует сохранённый context, не новые defaults.
Python probe JVM — 60 секунд на кандидата (env.select_mpxj_python), reader —
180 секунд; проверенный PYTHONPATH см. выше. JSON settings validation fail закрывает
подготовку до сетевых записей. Скрипт CLI запускается `/usr/bin/python3`.

## Backup перед будущей миграцией рабочей БД

Текущая приёмка мигрирует исключительно T/stage-12/state и fixtures. Рабочая БД
`/home/tkachenkoav/USERTOOLS/MofsIndex/state/index.sqlite` не открывается для записи.
Перед отдельной будущей миграцией нужен согласованный online backup с WAL через
существующий typed `mofs_index.plan.backup`, не сырое cp sqlite-файла.
Сохранить также content-addressed artifacts/normalized и _plan-receipts в
существующий backup/ownCloud-контур: БД не содержит единственных исходных bytes.
Наличие файла не доказывает завершение ownCloud sync.

Пример процедуры на **изолированной** БД; перенос на рабочий путь — отдельная
операция. Новый файл backup выбирать с timestamp, т.к. backup_to заменяет dest.

```python
from pathlib import Path
from mofs_index.plan.backup import backup_to, verify_backup, restore_from
source = Path('/isolated/state/index.sqlite')
backup = Path('/isolated/backups/index-before-migration.sqlite')
assert backup_to(backup, src_path=source).ok
assert verify_backup(backup).ok
assert restore_from(backup, Path('/isolated/restore/index.sqlite'), dry_run=True).ok
# Реальное восстановление только в отдельное дерево после проверки source:
assert restore_from(backup, Path('/isolated/restore/index.sqlite'),
                    dry_run=False, confirm=True).ok
```

После восстановления сверить artifacts/receipt hashes, версии схемы, counts,
baseline/selection и ссылки через typed API, затем read-back. Не удалять историю
для «починки». Инфраструктура после сбоя должна быть восстановлена до resume.

## Частичные эффекты, вывод и доставка скиллов

`operation show` → `resume` выполняет reconciliation раньше повторной записи.
Успешные batch items не повторяются, retryable failed только --retry-failed,
решения только --retry-decisions. Cache можно удалить; frozen/архивные bytes
нужны с прежними hashes. При смене контекста создать новый batch/операцию.
Не удалять lock-файлы и не сбрасывать счётчики retries ручной правкой БД.

В квитанциях/логах запрещены credentials, Authorization и полный export.
Reader stdout перехватывается, полный admission остаётся по details_ref.
Оператор не включает set -x, env dump или curl -v с токеном. Примеры содержат
вымышленные IDs; secret-redaction проверяется canary-тестами и сканированием
поставляемого evidence, без сохранения реальных значений секретов.

Доставка: workspace → `restore-all-skills.sh` → default profile;
живое дерево ~/.hermes/skills — отдельный слой. По регламенту
`devops/hermes-multi-profile-skills` проверить hub ownership, сохранить обычный
кастомный каталог в ~/.hermes/_Archives, подключить live symlink к профилю и
повторить restore. Проверить настоящие skill_view обоих имён, физические paths,
возвращённый текст и SHA-256. Самостоятельную копию канона в A не создавать.
Загрузчик/Gateway и скрипты restore/sync при этом не изменяются.
