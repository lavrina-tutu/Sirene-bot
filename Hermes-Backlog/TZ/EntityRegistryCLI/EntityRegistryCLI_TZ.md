---
tool: EntityRegistryCLI
status: draft
version: 0.2.1
author: Opus (черновик для Саши)
created: 2026-07-16
updated: 2026-08-29 (решения Саши зафиксированы после построчного брифа; добавлен раздел ## Контракты экосистемы)
depends_on: EntityRegistry v0.2.0 (реализован, PFS 151/151, TaskRefresh 112/112)
---

# EntityRegistryCLI — CRUD-инструмент для `WorkVault/Registries/entities.json`

## Контракты экосистемы

### Источник истины
- Владелец спецификации и схемы: EntityRegistry (`WorkVault/Registries/entities.schema.json`)
- Владелец реестра данных: EntityRegistryCLI (`WorkVault/Registries/entities.json`, CRUD-мутации)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| schema_version | str | required | entities_schema | semver версия схемы |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| slug | str | ProtocolFromSummary, TaskRefresh, workvault-rag | Ключ записи (json:entities_v1), ^[a-z0-9_]+$ |
| kind | enum[project, one_on_one, tool, team, room, contact, meeting, other] | ProtocolFromSummary, TaskRefresh | Тип сущности |
| parent | str | ProtocolFromSummary, TaskRefresh | slug родительской сущности или null |
| display_name | str | ProtocolFromSummary, TaskRefresh | Отображаемое имя сущности |
| aliases | str | ProtocolFromSummary, TaskRefresh, workvault-rag | Список альтернативных имен (JSON array) |
| pfs | dict | ProtocolFromSummary, TaskRefresh | Блок настроек PFS ({page_id, tag, page_layout, content_column_index}) |
| pfs.page_id | int | ProtocolFromSummary, TaskRefresh | Confluence pageId |
| pfs.tag | str | ProtocolFromSummary, TaskRefresh | Префикс-тег проекта (напр. "Trisigma.") |
| pfs.page_layout | str | ProtocolFromSummary, TaskRefresh | Лейаут страницы Confluence |
| pfs.content_column_index | int | ProtocolFromSummary, TaskRefresh | Индекс колонки с контентом |

### Зависимости
- Получает от: [entities_schema]
- Отдаёт: [ProtocolFromSummary, TaskRefresh, workvault-rag]

### Breaking changes policy
- Версионирование формата: semver на поле `schema_version` внутри `entities.json`
- При breaking change схемы `entities.schema.json`: запустить `entity-registry validate`, проверить миграцию потребителей (PFS, TaskRefresh)

### Границы («что НЕ трогать»)
- Не редактировать `entities.json` без прохождения валидации (JSON Schema + бизнес-инварианты)
- Не выполнять деструктивные мутации над записями с блоком `pfs` без явного подтверждения (confirm/--yes)
- Не изменять бизнес-логику чтения реестра в коде потребителей (PFS `config.py`, TaskRefresh `project_registry.py`)

## Цель

Дать Саше удобный и безопасный способ **добавлять, удалять, изменять и просматривать** сущности в едином каноническом реестре `WorkVault/Registries/entities.json`, не редактируя JSON руками (риск ошибок валидации, синтаксиса, потери атомарности) и **не переписывая сам CLI при каждом расширении схемы** (набор полей заведомо будет меняться — сегодня добавили `kind=tool`, `parent`-иерархию, блок `pfs`, завтра появится, например, `owner_login` или `slack_channel`).

Ключевые свойства:

1. **Схемо-независимость.** Инструмент читает `entities.schema.json` в рантайме и работает по актуальному списку полей/типов/enum'ов. Хардкода списка полей в Python-коде нет.
2. **Безопасность прод-потребителей.** Любая мутация проходит валидацию (JSON Schema + бизнес-инварианты) до записи; операции над записями с блоком `pfs` (= затрагивают PFS ROUTES и TaskRefresh) требуют явного подтверждения.
3. **Атомарность и восстановимость.** Запись через `tmp + os.replace`, бэкап перед деструктивной операцией.
4. **Не трогает код потребителей.** PFS/TaskRefresh/workvault-rag продолжают читать `entities.json` как и сейчас; CLI только меняет данные.

## Контекст

- Реестр `WorkVault/Registries/entities.json` — единый источник правды. Три потребителя:
  - **PFS** — `protocolfromsummary/config.py::_load_routes_from_registry()` собирает `ROUTES` из записей с блоком `pfs` при импорте модуля.
  - **TaskRefresh** — `taskrefresh/project_registry.py::ProjectRegistry.load()` читает записи с блоком `pfs` через адаптер (legacy-fallback: `WorkVault/Tools/TaskRefresh/project_registry.json`).
  - **workvault-rag** — Sonnet/Opus агентом через file-tools, матчит проекты по `aliases`.
- Схема реестра — `WorkVault/Registries/entities.schema.json` (Draft-07): корень `{schema_version, entities}`; ключ записи — slug (`^[a-z0-9_]+$`); обязательные поля записи — `kind` (enum), `parent` (string|null), `display_name` (string), `aliases` (array<string>); опциональный блок `pfs` = `{page_id: /^[0-9]+$/, tag: string|null, page_layout?: string, content_column_index?: int}`. `additionalProperties: false` — и на уровне записи, и внутри `pfs`.
- Бизнес-инварианты (не из JSON Schema, а из ТЗ EntityRegistry §Шаг 3):
  - Уникальность `slug` (обеспечивается тем, что `entities` — dict).
  - Все `parent` указывают на существующий `slug` либо `null`.
  - Уникальность пары `(pfs.page_id, pfs.tag)` среди записей с блоком `pfs`. Дубли `page_id` между разными `tag` разрешены (пример: `trisigma`/`ab_platforma` → `490170597`; `vstrechi_nerazobrannoe`/`tsu` → `508804852`).
  - Для записей БЕЗ блока `pfs` допустим любой из enum `kind`, включая `tool`.
- Regression-снимок реестра: PFS `pytest` 151/151, TaskRefresh 112/112 — на **любой** мутации инструмент обязан не создавать состояний, ломающих эти прогоны (см. §Критерии успеха, п.2).

## Название и расположение — рекомендация

**Имя инструмента: `EntityRegistryCLI`. Путь: `~/USERTOOLS/EntityRegistryCLI/`.**

Взвешенные варианты:

| Вариант | «+» | «−» |
|---|---|---|
| **A. `~/USERTOOLS/EntityRegistryCLI/`** (рекомендация) | Конвенция USERTOOLS (MoveFromFF, ProtocolFromSummary, TaskRefresh — все там); `tests/`, `README.md`; git-история отделена от WorkVault; удобно расширять зависимостями (например `rich` для `list`, `jsonschema` для валидации). **Venv — общий с ProtocolFromSummary/TaskRefresh** (см. §Решения Саши, п.3). | Ещё одна точка деплоя. |
| B. Скрипт рядом с данными: `WorkVault/Registries/manage.py` | Данные и код инструмента в одной директории — интуитивно; не требует отдельного venv, если обойтись stdlib. | Ломает конвенцию (WorkVault — про данные и ТЗ, не про код инструментов); `jsonschema` в stdlib нет — либо тащить в PFS-venv, либо писать валидатор руками; сложнее версионировать код независимо от данных. |

**Рекомендация: A.** Инструмент — самостоятельная утилита с зависимостями (`jsonschema`), которую логичнее держать по общей конвенции USERTOOLS. Путь до реестра — константа с ENV-override `ENTITIES_REGISTRY_PATH` (симметрично PFS/TaskRefresh; полезно для unit-тестов на временных JSON-фикстурах).

## Архитектура

### Модули (пофайловый план)

```
~/USERTOOLS/EntityRegistryCLI/
├── entityregistrycli/
│   ├── __init__.py
│   ├── __main__.py                     # python -m entityregistrycli
│   ├── cli.py                          # argparse: подкоманды add/remove/edit/list/validate
│   ├── registry_io.py                  # чтение/запись entities.json (tmp+os.replace, бэкапы)
│   ├── schema_loader.py                # чтение entities.schema.json + интроспекция полей
│   ├── validator.py                    # JSON Schema + бизнес-инварианты
│   ├── operations.py                   # add/remove/edit — чистая логика над dict, без I/O
│   ├── prompts.py                      # интерактивные confirm-диалоги (для pfs-мутаций)
│   └── audit_log.py                    # форматирование stderr key=value строк (см. D9)
├── references/
│   └── flags-reference.md              # ЧЕЛОВЕЧЕСКИЙ reference по всем флагам add/edit/remove/list/validate;
│                                       # синхронизируется при расширении схемы (см. §Решения Саши, п.2)
├── tests/
│   ├── conftest.py                     # фикстура: временная копия entities.json + schema
│   ├── test_add.py
│   ├── test_remove.py
│   ├── test_edit.py
│   ├── test_list.py
│   ├── test_validate.py
│   ├── test_schema_evolution.py        # ключевой тест на schema-independence
│   ├── test_audit_log_format.py        # проверка формата key=value в stderr (см. D9)
│   └── fixtures/
│       ├── entities_min.json
│       └── entities.schema.json
├── README.md                           # примеры вызовов, флаги, ссылка на references/flags-reference.md
├── requirements.txt                    # jsonschema>=4, (опционально rich) — ставится в ОБЩИЙ venv
└── pyproject.toml                      # entry-point entity-registry → entityregistrycli.cli:main
```

**Venv:** свой `.venv/` **НЕ создаётся**. Инструмент использует существующий общий venv
`~/USERTOOLS/ProtocolFromSummary/.venv/` (там уже живут PFS и TaskRefresh). Запуск:
`~/USERTOOLS/ProtocolFromSummary/.venv/bin/python -m entityregistrycli ...`
или через entry-point `entity-registry`, зарегистрированный в этом же venv через `pip install -e ~/USERTOOLS/EntityRegistryCLI`. Обоснование и риск — см. §Решения Саши, п.3 и §Регрессионный риск.

**Файл `references/flags-reference.md`.** Отдельный документ (не только `--help` argparse и не только README) с полной таблицей флагов для каждой подкоманды, типами значений, обязательностью, примерами и краткой ссылкой на поле схемы. Синхронизируется вручную при любом расширении `entities.schema.json`. **Опциональная автогенерация (nice-to-have, не обязательно):** сделать в `cli.py` или отдельном `tools/regen_flags_reference.py` команду, которая берёт `SchemaIntrospector.list_fields()` и печатает markdown-таблицу флагов; тогда синхронизация сводится к запуску этой команды и коммиту diff'а. Если реализация автогенерации нетривиальна — оставляем как ручной документ и упоминаем это в README §«Как расширить схему».

### Ключевые дизайн-решения

**D1. Интроспекция схемы вместо хардкода.**
`schema_loader.py::SchemaIntrospector` при инициализации читает `entities.schema.json` и вычисляет:
- `required_fields: list[str]` — из `properties.entities.patternProperties["^[a-z0-9_]+$"].required`.
- `optional_fields: list[str]` — все `properties` минус `required`.
- `field_type(name) -> {"type": ..., "enum": ..., "nested_schema": ...}` — тип каждого поля (в т.ч. `pfs` как вложенный объект со своими required/optional).
- Публичное API: `list_fields()`, `is_required(field)`, `validate_field_value(field, value) -> Ok|Err`.
Никаких `FIELDS = ["kind","parent",...]` в коде. Если завтра в схему добавится `owner_login: string` — `add --owner-login ...` заработает автоматически (см. §D3).

**D2. Флаги `add` — динамически из схемы.**
Флаги для `add` строятся программно из `SchemaIntrospector.list_fields()`. Пример: поле `kind` (enum) → `--kind {project|one_on_one|...}`; поле `aliases` (array) → `--alias STR` (repeatable, `action="append"`); вложенный блок `pfs` → флаги с префиксом (`--pfs-page-id`, `--pfs-tag`, `--pfs-page-layout`, `--pfs-content-column-index`). Слуг записи (`slug`) — позиционный аргумент (это ключ dict, а не поле объекта записи).

**D3. Пример: как переживём расширение схемы.**
Кто-то дописал в `entities.schema.json`: `"owner_login": {"type": "string"}` в `properties` записи. Ожидаемое поведение CLI **без единой правки его кода**:
- `add --owner-login sasha ...` — валидируется как string, попадает в JSON.
- `edit <slug> owner_login petr` — валидируется, применяется.
- `list` — колонка `owner_login` появляется в `--verbose`-режиме (см. D6).
- `validate` — если новое поле стало `required` в схеме, а в реестре есть записи без него — валидация падает с внятным сообщением по каждой такой записи (миграционный алерт).
- **Что нужно сделать вручную:** обновить `references/flags-reference.md` — добавить строку про новый флаг (или запустить автогенератор, если реализован).

**D4. Валидация — двухслойная.**
- Слой 1: `jsonschema.validate(instance, schema)` — синтаксис, типы, enum, `additionalProperties: false`.
- Слой 2: `validator.py::business_invariants(instance)` — уникальность пары `(pfs.page_id, pfs.tag)`, целостность `parent`-ссылок.
Обе проверки прогоняются **до** записи на диск на каждой мутации; провал → операция отклоняется с exit-code 2 и человеко-читаемым сообщением, файл не тронут.

**D5. Атомарность и бэкапы.**
- `registry_io.py::write_atomic(path, data)`: пишет в `path.with_suffix(".json.tmp")` + `os.replace` → атомарная замена.
- Перед `remove` / `edit` существующего значения / `add` с уже занятым slug (запрет, но всё равно) — создаётся бэкап в поддиректории `WorkVault/Registries/.backups/entities-YYYYMMDD-HHMMSS.json`. Ротация: держать **последние 20** бэкапов, старые удалять.
- `add` новой записи (slug ранее не было) — бэкап **не** обязателен (операция аддитивная, откат = `remove`), но по флагу `--backup` можно принудить.

**D6. UX `list`.**
- Дефолт: компактная таблица `slug | kind | parent | display_name | pfs?` (иконка `📄` для записей с блоком `pfs`).
- `--verbose` — добавляет `aliases`, `pfs.page_id`, `pfs.tag`, а также ВСЕ прочие поля, найденные `SchemaIntrospector` (авто-подхват новых полей).
- `--filter kind=project` / `--filter parent=devrel` / `--filter has-pfs` — простые фильтры.
- `--json` — сырой дамп (для пайплайнов).
- Библиотека вывода: `rich.table` (опционально; fallback на plain-print, если `rich` не установлен).

**D7. Confirm-диалог для мутаций с `pfs`.**
Любая операция, затрагивающая запись с блоком `pfs` (`remove`, `edit` любого поля этой записи, `add` с блоком `pfs`), — печатает предупреждение и требует ввода `yes` в stdin. Флаг `--yes` / `-y` пропускает диалог (для скриптов). Без TTY и без `--yes` — операция отклоняется с exit-code 3.
Формулировка предупреждения (пример для `remove trisigma`):
```
⚠️  Запись 'trisigma' имеет блок pfs (page_id=490170597, tag='Trisigma.').
    Удаление затронет ПРОД PFS ROUTES и TaskRefresh при следующем импорте/запуске:
    — PFS перестанет резолвить встречи с тегом 'Trisigma.' в этот проект;
    — TaskRefresh перестанет обновлять задачи на странице 490170597.
    Продолжить? [yes/N]:
```
Аналогичное предупреждение при `remove` записи, на которую ссылаются другие через `parent` (например `remove devrel` при существующем `cu` с `parent=devrel`) — по умолчанию **отказ** (exit-code 4); с `--force` — предупреждение + confirm + сиротская ссылка остаётся (но `validate` начнёт падать, пока Саша не поправит).

**D8. Поведение `edit` для несуществующего поля.**
**Решение: отказ** с exit-code 5 и сообщением «поле X не описано в entities.schema.json — сначала обнови схему». Обоснование: `edit` — точечная операция, добавление новых полей должно идти через изменение схемы (осознанный акт), а не через опечатку в CLI. Если Саша хочет свободного добавления — есть отдельный флаг `--allow-new-field` (по умолчанию OFF), который создаёт поле без валидации типа (плохая практика, но иногда нужна для эксперимента). Аналогично для `add --unknown-flag` — ругаемся, не создаём.

**D9. Логирование операций — stderr в формате `key=value`.**
На каждую **успешную или ошибочную** мутацию (`add`/`remove`/`edit`) CLI печатает в stderr одну строку в компактном машинно-читаемом формате `key=value` (пары через пробел). Цель формата — быстрый `grep` и парсинг моделью (Haiku при отладке), **не** человеческое чтение прозой. `list` и `validate` в этот лог не пишут (read-only).

Обязательные ключи в каждой строке:
- `op` — `add` | `remove` | `edit`
- `slug` — ключ записи
- `result` — `ok` | `error` (при `error` добавляется `error_code=<int>` и `error=<short_reason>`)

Операционно-специфичные ключи:
- `add`: `kind`, `parent` (может быть `null`), `pfs` (`true`/`false`), опц. `backup=<filename|none>`
- `remove`: `pfs` (`true`/`false`), `confirmed` (`yes`/`no`/`skipped`), `backup=<filename>`
- `edit`: `field`, `old`, `new` (значения в кавычках при наличии пробелов/спецсимволов; `null` без кавычек)

Примеры строк (эталон формата):
```
op=add slug=devrel kind=project parent=null pfs=false result=ok backup=none
op=remove slug=trisigma pfs=true confirmed=yes backup=entities-20260716-153000.json result=ok
op=edit slug=cu field=display_name old="ЦУ" new="ЦУ (Central University)" result=ok
op=add slug=devrel kind=project parent=null pfs=false result=error error_code=1 error=slug_exists
```

Модуль-владелец формата: `entityregistrycli/audit_log.py::emit(op, slug, result, **kwargs)`. Формат строки покрыт unit-тестом `test_audit_log_format.py` (порядок ключей, экранирование значений с пробелами, поведение `null`).

## Операции — детальная спецификация

### `add <slug> [--kind ...] [--parent ...] [--display-name ...] [--alias A --alias B ...] [--pfs-page-id ...] [--pfs-tag ...] [-y]`
- Читает реестр, проверяет что `slug` свободен (иначе exit-code 1).
- Собирает объект записи из флагов; отсутствующие обязательные поля → интерактивный prompt (или отказ с `--no-interactive`).
- Прогоняет валидацию (JSON Schema + инварианты) на **финальном** реестре с уже добавленной записью.
- Если новая запись содержит блок `pfs` → confirm-диалог (D7).
- Пишет атомарно, эмитит stderr-строку (D9).

### `remove <slug> [--force] [-y]`
- Читает, проверяет что `slug` существует (иначе exit-code 1).
- Проверяет наличие блока `pfs` → confirm (D7).
- Проверяет child-ссылки (`parent==slug` у других записей) → отказ, если найдены (exit-code 4), либо предупреждение с `--force`.
- Бэкап → удаление из dict → валидация оставшегося → атомарная запись → stderr-строка (D9).

### `edit <slug> <field> <value> [-y]`
- `field` — dot-path (`kind`, `aliases`, `pfs.page_id`, `pfs.tag`, `pfs.page_layout`); для массивов есть `--append`/`--remove-item` варианты (например `edit trisigma aliases "новый_алиас" --append`).
- Значение парсится по типу поля из `SchemaIntrospector`:
  - `string`/`enum` → как есть;
  - `integer` → `int(value)` с проверкой;
  - `array<string>` без `--append`/`--remove-item` — интерпретируется как замена целиком через JSON (`--value-json '["a","b"]'`) либо через запятую (простой случай);
  - `null` — специальный литерал `--null` (флаг), потому что позиционный `null` в shell двусмысленный.
- Специальный случай `edit <slug> pfs --remove` — удаляет весь блок `pfs` (обязателен confirm, D7); `edit <slug> pfs --set '{"page_id":"123","tag":"X."}'` — добавляет/заменяет блок целиком.
- Бэкап (значение существующего поля меняется) → мутация → валидация → атомарная запись → stderr-строка (D9).

### `list [--verbose] [--filter K=V] [--json]`
- Read-only. Не требует бэкапа. Никаких мутаций. В stderr-лог D9 не пишет.

### `validate [--path /alt/entities.json]`
- Явный запуск полной валидации (JSON Schema + инварианты).
- Exit-code 0 = ок; ≠0 = нашли проблемы, печатаем список.
- Запускается **вручную**, без pre-commit hook (решение Саши, п.6).

## Шаги реализации

**Шаг 1. Каркас инструмента (использует общий venv).**
- Создать `~/USERTOOLS/EntityRegistryCLI/` **без собственного `.venv/`**.
- Проверить наличие `jsonschema` в общем venv:
  `~/USERTOOLS/ProtocolFromSummary/.venv/bin/pip show jsonschema`.
- Если нет — установить: `~/USERTOOLS/ProtocolFromSummary/.venv/bin/pip install "jsonschema>=4"`.
  Если в `~/USERTOOLS/ProtocolFromSummary/` есть `requirements.txt` (или эквивалент — `pyproject.toml`/`setup.py`) — добавить туда `jsonschema>=4` для воспроизводимости окружения; проверить фактическое имя файла перед правкой.
- Создать пустой пакет `entityregistrycli/` со всеми модулями-заглушками (см. §Модули).
- `pyproject.toml` с entry-point `entity-registry` → `entityregistrycli.cli:main`; `pip install -e .` в общий venv.
- Smoke-тест: `~/USERTOOLS/ProtocolFromSummary/.venv/bin/python -m entityregistrycli --help` работает.
- **Критерий успеха этого шага (обязательный regression-guard):** после установки `jsonschema` в общий venv прогнать
  `cd ~/USERTOOLS/ProtocolFromSummary && .venv/bin/python -m pytest` → **151/151**,
  `cd ~/USERTOOLS/TaskRefresh && .venv/bin/python -m pytest` → **112/112**.
  Если любой из прогонов красный — откатить установку (`pip uninstall jsonschema` или `pip install jsonschema==<предыдущая версия>`) и остановиться до выяснения.

**Шаг 2. `schema_loader.py` — интроспекция схемы.**
- `SchemaIntrospector(schema_path)` с публичным API (см. §D1).
- Unit-тесты: на текущей `entities.schema.json` возвращает ровно `["kind","parent","display_name","aliases"]` как required; `field_type("kind")` возвращает enum со всеми 6 значениями; `field_type("pfs")` возвращает nested-объект с `page_id`, `tag` в required.
- **Ключевой тест schema-evolution:** подменяем schema-фикстуру (добавляем `owner_login: {"type":"string"}`) → `list_fields()` включает новое поле, `is_required("owner_login")` = False, `validate_field_value("owner_login","sasha")` = Ok.

**Шаг 3. `registry_io.py` — атомарная запись + бэкапы.**
- `load(path) -> dict`, `write_atomic(path, data)`, `make_backup(path) -> Path` (кладёт в `.backups/entities-YYYYMMDD-HHMMSS.json` относительно директории реестра), `rotate_backups(backups_dir, keep=20)`.
- Unit-тесты: запись выживает при симуляции сбоя (mock `os.replace` бросает — исходный файл не тронут); бэкапы называются корректно; ротация оставляет ровно N=20.

**Шаг 4. `validator.py`.**
- `validate_schema(instance, schema) -> Result` (обёртка над `jsonschema`).
- `validate_invariants(instance) -> list[Issue]`: уникальность `(pfs.page_id, pfs.tag)`, целостность `parent`.
- Unit-тесты: битый `parent` → Issue; дубликат пары `(page_id,tag)` → Issue; валидные дубли `page_id` при разных `tag` → нет Issue.

**Шаг 5. `operations.py` + `audit_log.py` — чистая логика.**
- `add(instance, slug, fields, schema_intro) -> new_instance`, аналогично `remove`, `edit`. Без I/O.
- `audit_log.emit(op, slug, result, **kwargs) -> str` — форматирует `key=value` строку по спецификации D9, экранирует значения с пробелами кавычками, `null` печатает без кавычек.
- Unit-тесты: дубль slug → ValueError; edit несуществующего поля → ValueError; `pfs` целиком заменяется корректно; `aliases --append` не создаёт дублей; `test_audit_log_format.py` проверяет порядок ключей, экранирование, `null`, error-строку.

**Шаг 6. `cli.py` + `prompts.py` — сборка.**
- argparse-подкоманды `add`/`remove`/`edit`/`list`/`validate`.
- Динамическое построение флагов `add` из `SchemaIntrospector`.
- Confirm-диалоги (D7). Stderr-логирование через `audit_log.emit` (D9).
- Exit-коды: 0 ок / 1 «объект не найден или уже существует» / 2 «валидация не прошла» / 3 «нет TTY и нет --yes» / 4 «есть child-ссылки без --force» / 5 «поле не в схеме без --allow-new-field».
- Integration-тесты через `subprocess.run([python, "-m", "entityregistrycli", ...])` на временном реестре, с проверкой формата stderr.

**Шаг 7. `README.md` + `references/flags-reference.md` + примеры.**
- Примеры для всех операций.
- Раздел «Как расширить схему»: (1) правь `entities.schema.json`; (2) прогоняешь `entity-registry validate` — увидишь миграционные проблемы; (3) правишь данные `entity-registry edit ...`; (4) **обнови `references/flags-reference.md`** — добавь строку про новый флаг (или запусти автогенератор, если реализован); (5) CLI-код НЕ трогаешь.
- Раздел «Flags reference»: короткое описание + ссылка на `references/flags-reference.md` как источник правды по флагам; в README держим только 3–5 самых частых примеров, полный перечень — в reference-файле.
- Раздел «Синхронизация с прод-потребителями (толкать нечего):** объяснить архитектурно, почему `--restart-cron` **не** реализуется и не нужен:
  > PFS-кроны (`pfs_batch`, `pfs_notify`) — недолгоживущие процессы, запускаемые по расписанию (не демон): каждый тик = новый Python-процесс = свежий импорт `config.py` = автоматическое чтение актуального `entities.json`. Задержка появления новой сущности в проде — максимум до следующего планового тика (~1 час для PFS, ~5 минут для `notify_pending`, если он в шедуле). TaskRefresh — интерактивный CLI без фонового процесса, следующий вызов сразу видит правку, задержки нет вообще. **Долгоживущего процесса с закешированным состоянием entities.json в системе нет — значит forced-restart не даёт практической пользы.**
- Раздел «После мутации»: прогнать regression PFS 151/151 и TaskRefresh 112/112, если правка затронула запись с блоком `pfs`.

**Шаг 8. Регистрация в MAIN_TZ_INVENTORY.md.**
- Добавить строку в §Активные ТЗ (см. ниже §«Обновление MAIN_TZ_INVENTORY»).

## Тесты (обязательный минимум)

| Тест | Кейс | Ожидание |
|---|---|---|
| `test_add.py::test_add_ok` | новый slug + все поля | запись появилась, валидна |
| `test_add.py::test_add_duplicate_slug` | slug уже есть | exit-code 1, файл не тронут |
| `test_add.py::test_add_without_required_field_no_interactive` | нет `--kind`, флаг `--no-interactive` | отказ, exit-code 2 |
| `test_add.py::test_add_with_pfs_requires_confirm` | флаги `--pfs-*`, нет `-y`, нет TTY | exit-code 3 |
| `test_remove.py::test_remove_ok` | простая запись без pfs, без детей | удалилась, бэкап создан в `.backups/` |
| `test_remove.py::test_remove_with_children_no_force` | у записи есть `parent`-child | exit-code 4 |
| `test_remove.py::test_remove_with_children_force` | `--force -y` | удалилась, `validate` падает на сироте |
| `test_remove.py::test_remove_pfs_requires_confirm` | запись с блоком `pfs`, нет `-y`, нет TTY | exit-code 3 |
| `test_edit.py::test_edit_scalar` | `edit trisigma display_name "New"` | ок |
| `test_edit.py::test_edit_unknown_field` | `edit trisigma foo bar` | exit-code 5 |
| `test_edit.py::test_edit_unknown_field_allow_new` | тот же кейс с `--allow-new-field` | ок, поле добавилось |
| `test_edit.py::test_edit_alias_append` | `--append` в массив | без дублей |
| `test_edit.py::test_edit_pfs_remove_requires_confirm` | `edit trisigma pfs --remove` без `-y` | exit-code 3 |
| `test_list.py::test_list_default` | вывод в stdout | все slug присутствуют |
| `test_list.py::test_list_filter_kind_project` | `--filter kind=project` | только project'ы |
| `test_validate.py::test_validate_ok` | текущий реестр | exit-code 0 |
| `test_validate.py::test_validate_duplicate_page_id_tag` | подмешать битую пару | exit-code 2, конкретное сообщение |
| `test_validate.py::test_validate_broken_parent` | `parent="ghost"` | exit-code 2 |
| `test_schema_evolution.py::test_new_field_added_to_schema` | добавили `owner_login` в фикстуру-схему | `add --owner-login ...` работает, `list --verbose` показывает колонку, код CLI не менялся |
| `test_audit_log_format.py::test_add_ok_line` | эмит после успешного add | строка `op=add slug=... kind=... parent=... pfs=... result=ok ...` |
| `test_audit_log_format.py::test_edit_quoted_value` | значение с пробелом | old/new в двойных кавычках |
| `test_audit_log_format.py::test_error_line` | ошибочная операция | строка содержит `result=error error_code=<N> error=<slug_reason>` |

## Критерии успеха

1. Все 20+ unit/integration-тестов зелёные (включая `test_audit_log_format.py` и `test_schema_evolution.py`).
2. **Regression-guard прод-потребителей после установки `jsonschema` в общий venv** (критерий Шага 1): `pytest` в `~/USERTOOLS/ProtocolFromSummary/` → **151/151**, в `~/USERTOOLS/TaskRefresh/` → **112/112**. Прогон обязателен **до** того, как продолжать реализацию; красный прогон — сигнал откатить установку зависимости.
3. **Regression-guard после мутаций реестра:** после любых экспериментов с CLI на реальном `entities.json` те же два прогона остаются 151/151 и 112/112. В README указано: «после мутации `entities.json` рекомендуется прогнать оба regression-набора».
4. Добавление нового поля в `entities.schema.json` **не требует** правки кода CLI (проверяется тестом `test_schema_evolution.py`). Требуется только обновить `references/flags-reference.md`.
5. Все деструктивные операции создают бэкап в `WorkVault/Registries/.backups/entities-<timestamp>.json`; ротация держит последние 20.
6. Все мутации, затрагивающие запись с блоком `pfs`, требуют явного подтверждения (interactive или `--yes`).
7. **Формат stderr-лога `key=value`** соблюдается на каждой мутации; порядок ключей, экранирование значений с пробелами и `null` покрыты unit-тестом. Проза-логи запрещены.
8. `validate` — идемпотентная read-only команда, exit-code корректно отражает состояние реестра.
9. README содержит примеры для всех 5 операций, раздел «Как расширить схему», раздел «Синхронизация с прод-потребителями (толкать нечего)», ссылку на `references/flags-reference.md`.

## Регрессионный риск

**Общий venv `~/USERTOOLS/ProtocolFromSummary/.venv/` — потенциальная точка неявной связности.** Добавление `jsonschema>=4` (или обновление его версии в будущем) в общий venv **теоретически** может повлиять на PFS/TaskRefresh, если у них появится транзитивный конфликт зависимостей или если `jsonschema` начнёт трогать общий кэш. Практический риск оценивается как низкий (`jsonschema` — узкая библиотека без монки-патчей глобального рантайма), но **обязательный митигейт:** после `pip install jsonschema` в общий venv **до** любых дальнейших шагов Шага 1 прогнать PFS `pytest` 151/151 и TaskRefresh `pytest` 112/112. Красный прогон = откат установки, эскалация Саше. См. Шаг 1 и Критерий успеха 2.

Аналогичный митигейт применяется при любом будущем обновлении зависимостей в общем venv (не только в контексте этого инструмента, но фиксируем практику здесь).

## Что НЕ трогать

- `protocolfromsummary/config.py::_load_routes_from_registry()` — код чтения реестра PFS.
- `taskrefresh/project_registry.py::ProjectRegistry.load()` — код чтения реестра TaskRefresh.
- `~/.hermes/skills/research/workvault-rag/SKILL.md` — код скилла.
- `WorkVault/Registries/entities.schema.json` — как **артефакт**, не как код (CLI её читает, но не редактирует; правки схемы — вручную Сашей).
- `route.py`, `_match_by_name`, любые правила резолва PFS.
- Legacy `WorkVault/Tools/TaskRefresh/project_registry.json` — legacy-fallback TaskRefresh, живёт своей жизнью до отдельного follow-up на удаление.
- `contacts.enc` / `AnywhereContacts` — люди, не сущности.
- **`--restart-cron` / любой forced-restart прод-потребителей** — НЕ реализовывать даже как заглушку (обоснование — §Решения Саши, п.8 и Шаг 7 README).
- **Собственный `.venv/` внутри `~/USERTOOLS/EntityRegistryCLI/`** — НЕ создавать; использовать общий с PFS/TaskRefresh (§Решения Саши, п.3).
- **Pre-commit hook на `validate`** — НЕ подключать; только ручной запуск (§Решения Саши, п.6).

## Решения Саши (бриф завершён 16.07.2026)

Все восемь пунктов ниже — **принятые Сашей решения**, а не рекомендации. Там, где решение отклоняется от рекомендации Opus в v0.1.0, это отмечено явно.

1. **Имя CLI-команды: `entity-registry`.** ✅ Совпадает с рекомендацией Opus. Самодокументируемо; при желании — alias `ereg` в bash.

2. **Wizard vs флаги для `add`: гибрид (флаги + prompt на недостающие обязательные), `--no-interactive` выключает prompt.** ✅ Механизм совпадает с рекомендацией Opus. **Дополнение Саши:** описания флагов ведутся в отдельном **связанном reference-файле** `references/flags-reference.md` (а не только в `--help` argparse и README) — этот документ синхронизируется при каждом расширении схемы. Автогенерация reference-файла из `SchemaIntrospector.list_fields()` — nice-to-have, не обязательное требование; если реализуется просто — сделать команду-регенератор, иначе поддерживать вручную. Отражено в §Модули (`references/flags-reference.md`), в D3 («что нужно сделать вручную при расширении схемы») и в Шаге 7 README.

3. **Venv: ОБЩИЙ с `~/USERTOOLS/ProtocolFromSummary/.venv/`.** ⚠️ **ОТКЛОНЕНИЕ от рекомендации Opus** (была: свой отдельный venv). Обоснование Саши: PFS и TaskRefresh уже делят этот venv, инструмент логически часть той же экосистемы, меньше дублирования окружений и версий. **Практические следствия:**
   - Собственный `.venv/` в дереве инструмента не создаётся (см. §Модули).
   - `jsonschema>=4` устанавливается в общий venv, если ещё не установлен; при наличии `requirements.txt`/`pyproject.toml` у PFS — добавить туда.
   - Запуск CLI — через `~/USERTOOLS/ProtocolFromSummary/.venv/bin/python -m entityregistrycli` или через entry-point в этом же venv.
   - **Риск:** обновление/добавление зависимостей в общий venv может теоретически повлиять на PFS/TaskRefresh — обязателен regression PFS 151/151 + TaskRefresh 112/112 **сразу после установки** `jsonschema`, до продолжения Шага 1 (см. §Регрессионный риск и Критерий успеха 2).

4. **Ротация бэкапов: 20.** ✅ Совпадает с рекомендацией Opus. ~месяц истории при типичной частоте мутаций, <200 KB суммарно.

5. **Место бэкапов: поддиректория `.backups/`.** ✅ Совпадает с рекомендацией Opus. Путь: `WorkVault/Registries/.backups/entities-YYYYMMDD-HHMMSS.json`. Основная директория `Registries/` остаётся чистой (README + schema + данные, без визуального шума от бэкапов).

6. **Validate в CI/pre-commit: только ручной запуск, без pre-commit hook.** ✅ Совпадает с рекомендацией Opus. Pre-commit hook — potential follow-up, если поймаем инцидент с невалидной ручной правкой; пока — не подключаем.

7. **Логирование: stderr-строка в формате `key=value`.** ✅ Механизм (stderr, не audit-log и не молча) совпадает с рекомендацией Opus. **Уточнение Саши по формату:** строка оптимизирована **для машинного чтения** (Haiku при отладке, `grep`, парсеры) — компактные `key=value` пары через пробел, **не** разговорное предложение. Обязательные ключи: `op` (`add`/`remove`/`edit`), `slug`, `result` (`ok`/`error`). Операционно-специфичные ключи — см. §D9. Формат покрыт тестом `test_audit_log_format.py`. Проза-логи запрещены.

8. **Синхронизация с PFS/TaskRefresh — НЕ толкать.** ✅ Совпадает с рекомендацией Opus. **Архитектурное обоснование, зафиксированное в брифе:** PFS-кроны (`pfs_batch`, `pfs_notify`) — недолгоживущие процессы, запускаемые по расписанию (не демон): каждый тик = новый Python-процесс = свежий импорт `config.py` = автоматическое чтение актуального `entities.json`. Задержка появления новой сущности в проде — максимум до следующего планового тика cron (~1 час для PFS). TaskRefresh — интерактивный CLI без фонового процесса, следующий вызов сразу видит правку, задержки нет вообще. **Долгоживущего процесса с закешированным состоянием entities.json в системе нет — forced-restart не даёт практической пользы.** `--restart-cron` не реализуется даже как заглушка (см. §Что НЕ трогать и Шаг 7 README).

## Обновление MAIN_TZ_INVENTORY

В `WorkVault/Hermes-Backlog/TZ/MAIN_TZ_INVENTORY.md` в секцию «Активные ТЗ» добавить строку:

```
| EntityRegistryCLI | `TZ/EntityRegistryCLI/EntityRegistryCLI_TZ.md` | 0.2.0 | 2026-07-16 | draft | решения зафиксированы 16.07.2026, ждёт «берём в работу» от Саши |
```

(вставить между `EntityRegistry` и `ProtocolFromSummary` — алфавит + логическая близость).
