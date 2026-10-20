---
tool: AnywhereContacts
version: "0.3.1"
date: 2026-10-20
status: active
---

# AnywhereContacts — общее ядро коннекторов контактов

Версия: 0.2.0 (живой документ, накопительный)

## 1. Что это и зачем

`AnywhereContacts` — это **общая библиотека** (Python-пакет), которой пользуются все
коннекторы синхронизации контактов: `MoveFromExchange`, `MoveFromZulip`, и любые
следующие (Slack/Mattermost/AD/whatever). Цель — вынести из коннекторов всё, что
к источнику данных не относится:

- шифрование (AES-256-GCM) и атомарная запись `contacts.enc`;
- общая схема контакта (schema v2) с поддержкой множества источников;
- merge-стратегия с защитой "ручных" custom-полей;
- единый файл-лок на `contacts.enc` (несколько коннекторов одновременно не пишут);
- логирование с маскированием PII;
- базовые настройки (пути, ключ шифрования).

Коннектор остаётся **тонким**: знает только про конкретный источник
(`*_client.py`), фильтры (`filters.py`), маппинг сырой записи в `Contact`
(`mapper.py`) и оркестрацию `sync.py`.

## 2. Schema v2 (формат контакта)

```json
{
  "schema_version": "2.0",
  "updated_at": "2026-05-28T09:53:00Z",
  "contacts": {
    "<login>": {
      "login": "ivan.petrov",
      "fio": "Иван Петров",
      "display_name": "Иван Петров",
      "department": "...",
      "team": "...",
      "position": "...",
      "is_room": false,
      "active": true,
      "sources": {
        "exchange": {
          "email": "ivan.petrov@tutu.ru",
          "synced_at": "2026-05-28T09:53:00Z",
          "active": true
        },
        "zulip": {
          "email": "ivan.petrov@tutu.ru",
          "synced_at": "2026-05-28T09:53:01Z",
          "active": true
        }
      },
      "aliases": ["Ваня"],
      "messenger_ids": {
        "telegram": {
          "value": "@ivanp",
          "source": "manual",
          "synced_at": "2026-04-01T10:00:00Z"
        }
      },
      "notes": "",
      "custom_updated_at": "2026-04-01T10:00:00Z",
      "synced_at": "2026-05-28T09:53:01Z"
    }
  }
}
```

Ключевое:
- **Первичный ключ контакта — `login`** (часть email до `@`), а не email.
- Поле `sources` хранит per-source метаданные. У каждого источника свой `email`,
  `synced_at` и `active`.
- `active` верхнего уровня = `any(s.active for s in sources.values())`.
- `messenger_ids[*]` — это объекты `{value, source, synced_at}`.
  Если `source == "manual"`, коннектор НЕ перезаписывает значение.
- `email` верхнего уровня для совместимости — это `sources[<canonical>].email`
  (выбирается по приоритету: первый из `["exchange", "zulip", ...]`, фактический
  любой не-пустой).

## 3. Migration v1 → v2

`migrate_v1_to_v2(data)` принимает dict v1 (`schema_version` == `"1.0"` либо
отсутствует) и возвращает dict v2.

Алгоритм:
1. Для каждой записи `email -> contact_v1`:
   - `login = contact_v1["login"] or email.split("@")[0]`;
   - создаём запись по ключу `login`;
   - переносим базовые поля (`fio`, `display_name`, `department`, `team`,
     `position`, `is_room`, `aliases`, `notes`, `custom_updated_at`);
   - создаём `sources = {"exchange": {"email": email,
     "synced_at": contact_v1.get("synced_at"), "active": contact_v1["active"]}}`
     (v1 = только Exchange);
   - `active = contact_v1["active"]`;
   - `messenger_ids`: каждое значение оборачиваем
     `{"value": <old>, "source": "manual", "synced_at": custom_updated_at}`;
   - `synced_at = contact_v1.get("synced_at")`.
2. `schema_version = "2.0"`.
3. Если на входе уже v2 — возвращаем как есть.

Миграция вызывается автоматически в `ContactStore.read()`.

## 4. Публичный API

```python
from anywhere_contacts import (
    # crypto
    generate_key, encrypt_data, decrypt_data,
    read_contacts_enc, write_contacts_enc,
    # store
    ContactStore, create_store,
    # merger
    ContactMerger, MergeStrategy,
    # schema
    empty_payload, migrate_v1_to_v2, CUSTOM_FIELDS,
    # lock
    FileLock, lock_context, LockError, default_lock_path,
    # logger
    SyncLogger, create_logger, mask_pii, PII_MASKERS,
    # settings
    ContactsBaseSettings,
)
```

### Ключевые сигнатуры

```python
class ContactStore:
    def __init__(self, path: Path, encryption_key: str): ...
    def read(self) -> dict:  # auto-migrates v1→v2
    def write(self, data: dict) -> None: ...
    def get_contact(self, login: str) -> dict | None: ...
    def get_contact_by_email(self, email: str) -> dict | None: ...
    def find_contacts(self, query: str) -> dict[str, dict]: ...

class ContactMerger:
    def __init__(self, source: str): ...           # 'exchange' | 'zulip' | ...
    def merge(self, local: dict, incoming: list[dict]) -> tuple[dict, dict]: ...
    # incoming = mapper-output (записи в формате schema v2 для своего источника).

class ContactsBaseSettings(BaseSettings):
    contacts_encryption_key: Optional[str]
    workvault_path: Path
    contacts_path: Optional[Path]   # default: <workvault>/Contacts/
    logs_path: Optional[Path]
    tool_dir: Optional[Path]

    @property
    def contacts_enc_path(self) -> Path        # <contacts_path>/contacts.enc
    @property
    def contacts_lock_path(self) -> Path       # <contacts_path>/.contacts.enc.lock
    @property
    def sync_log_path(self) -> Path            # <logs_path>/_sync_log.md
    @property
    def contacts_jsonl_path(self) -> Path      # <logs_path>/contacts.jsonl
```

## 5. Merge-стратегия

```python
ContactMerger(source="zulip").merge(local, incoming)
```

Для каждой `incoming`-записи (уже отфильтрованной коннектором):
1. `login = incoming["login"]`.
2. Если `login` нет в local → создаём контакт; `sources = {source: {...}}`,
   `active = True`.
3. Если `login` есть в local:
   - обновляем "плоские" поля от источника (`fio`, `display_name`, `department`,
     `team`, `position`) **только если в local они пустые** ИЛИ источник
     является "приоритетным" (на v0.1 — без приоритетов, берём первый
     непустой; коннектор задаёт стратегию `MergeStrategy.overwrite_basic`
     или `MergeStrategy.fill_only_empty`);
   - обновляем `sources[source] = {email, synced_at, active=True}`;
   - **custom-поля не трогаем** (`aliases`, `notes`, `custom_updated_at`);
   - `messenger_ids`: для каждого `k, v` из incoming:
     - если в local нет `k` → добавляем `{value:v, source:"<source>", synced_at:now}`;
     - если есть и `source == "manual"` → НЕ трогаем;
     - если есть и `source == <тот же source>` → обновляем `value` и `synced_at`.

Для каждой `local`-записи, у которой есть `sources[source]`, но в incoming
её нет: `sources[source].active = False`. После прохода:
`active = any(s.active for s in sources.values())`.

`merge()` возвращает `(updated_data, stats)` со счётчиками `new`, `updated`,
`inactive`, `synced`, `total`.

## 6. Структура пакета

```
AnywhereContacts/
├── pyproject.toml
├── TZ.md
└── anywhere_contacts/
    ├── __init__.py
    ├── schema.py        # CUSTOM_FIELDS, empty_payload(), migrate_v1_to_v2(), now_iso()
    ├── crypto.py        # AES-256-GCM (как в MoveFromExchange)
    ├── store.py         # ContactStore (login-key, auto-migrate)
    ├── merger.py        # ContactMerger(source=...), MergeStrategy
    ├── logger.py        # PII masking, SyncLogger
    ├── lock.py          # FileLock + default_lock_path(contacts_path)
    └── settings.py      # ContactsBaseSettings
```

## 7. Как добавить новый коннектор

Минимум шагов:
1. `pip install -e ../AnywhereContacts`.
2. Создать `<connector>/`:
   - `config.py`: `class Settings(ContactsBaseSettings)` + свои URL/токены.
   - `<source>_client.py`: один метод `fetch_all() -> list[dict]` (сырьё).
   - `filters.py`: `partition(records) -> (live, filtered, stats)`.
   - `mapper.py`: `to_contact_record(raw) -> dict` (готовый под schema v2:
     `{login, fio, display_name, department, team, position, email, ...}`).
   - `sync.py`: `run_sync(settings, dry_run)` — fetch → filter → map → merge → write
     под `lock_context(settings.contacts_lock_path)`.
   - `__main__.py`: argparse `--mode manual|cron`, `--dry-run`.
3. Регистрировать source-имя один раз (строкой) — оно идёт в `sources` ключом.

## 8. Тесты

`AnywhereContacts/tests/`:
- `test_schema_migration.py` — v1→v2 на synthетике;
- `test_store_roundtrip.py` — write/read, миграция при чтении;
- `test_merger.py` — новый/обновлённый/inactive, manual messenger_ids
  не перезаписывается, multi-source `active`;
- `test_logger_masking.py` — портируем из MoveFromExchange.

Коннекторы оставляют только свои тесты (`test_filters.py`, `test_mapper.py`).

## 9. PII-защита вывода (v0.2.0)

Реализовано 2026-08-27: разделение «хранения/внутреннего использования» и
«показа пользователю» для всех данных контактов.

**`anywhere_contacts/display.py` — `render_contact(contact, level="summary"|"full")`:**
- `level="summary"` (по умолчанию) — открыты `fio`/`display_name`, `department`,
  `team`, `position`, `status`, `active`; поля `email`, `login`,
  `messenger_ids`, `sources[*].email`/`username`/`handle` — маскируются
  через существующие `PII_MASKERS` из `logger.py`.
- `level="full"` — полная копия контакта без маскирования. Используется
  **только** при явном запросе (пользователь просит показать полный
  email/логин).

**`ContactStore` — новые display-методы** (не заменяют существующие):
- `get_contact_for_display(login, level="summary")`,
- `find_contacts_for_display(query, level="summary")`.

Внутри читают через штатные `get_contact`/`find_contacts` и прогоняют
результат через `render_contact`. Сами `get_contact`/`find_contacts`
**не изменены** — их продолжают использовать внутренние потребители,
которым нужен полный контакт (не вывод).

`render_contact` и оба display-метода реэкспортированы из
`anywhere_contacts/__init__.py`.

**OrgLookup CLI** (`orglookup/cli.py`, команды `who`/`manager`/`bootstrap`/`add`):
вывод по умолчанию идёт через `render_contact(..., level="summary")`; полный
email/логин без маски — только по явному флагу `--reveal`.

**OrgLookup `md_writer.py`:** добавлены `PlaintextContactsMdForbidden` и
`guard_plaintext_contacts_write()` — генерация файла контактов в открытом
виде (plaintext, без маскирования) теперь запрещена на уровне guard'а;
`serialize_table()` маскирует `email`/`telegram` при сериализации таблицы.

**Хранение:** `~/WorkVault/Contacts/tutu-contacts.md` удалён — открытый
список контактов в системах больше не хранится. Единственный источник
данных — `contacts.enc`; для показа — только через `render_contact` /
`*_for_display`.

**Рантайм-скилл `show-contacts`**
(`~/.hermes/skills/productivity/show-contacts/SKILL.md`): обязывает агента
при любом выводе контакта пользователю использовать `render_contact`/
`*_for_display`, не читать raw `ContactStore` напрямую для показа и не
печатать `email`/`login`/`telegram`/`zulip`/`phone` в открытом виде.

**Инвариант (важно):** внутренние consumer-пайплайны, которым нужен полный
email для матчинга (`contacts_resolver`, matcher в `AggregateFromMeetings`,
`ProtocolFromSummary`, `MarkObjectsFromSummary`), **не относятся к выводу**
и продолжают использовать полный email через существующие
`get_contact`/`find_contacts` — это легитимное внутреннее использование,
не подпадающее под ограничения показа.

## Контракты экосистемы

### Источник истины
- Владелец записи: AnywhereContacts (`ContactStore`, `contacts.enc`, ключ — `login`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| login | str | required | ExchangeOrgLookup / коннекторы источников | login = email до "@", `json:contact_v2` |
| fio | str | optional | коннекторы источников | ФИО как строка, "Фамилия Имя" |
| email | str | required | коннекторы источников | валидный email, маскируется при выводе |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| contact.sources | dict | ProtocolFromSummary, TaskRefresh, MeetingScheduler | ключ — имя источника (exchange/zulip/...), значение — {email, synced_at, active}, `json:contact_v2` |
| contact.sources[*].active | bool | ProtocolFromSummary (matcher) | true/false, any() по источникам определяет "живой" контакт |

### Зависимости
- Получает от: [ExchangeOrgLookup]
- Отдаёт: [ProtocolFromSummary, TaskRefresh, MeetingScheduler]

### Breaking changes policy
- Версионирование формата: semver на поле `schema_version` внутри `contacts.enc` (сейчас "2.0")
- При breaking change: добавить `migrate_vN_to_vN+1()` в `schema.py`, уведомить потребителей из списка «Отдаёт»

### Границы («что НЕ трогать»)
- Не менять `login` как первичный ключ без миграции всех потребителей
- Не выводить raw `email`/`login` пользователю без маскирования через `render_contact`

---

## Exchange upsert (v0.3.0, 08.09)

**Статус: реализовано и протестировано 08.09.2026** (контур A): `upsert_from_source` в `store.py` живой (create/FILL_ONLY_EMPTY/reports_to/reactivate/dry_run/unchanged; email required на create), реэкспорт в `__init__.py`, тесты 46 passed (6 upsert-критериев + регресс). План досбора: `HF-plan_exchange-contact-upsert_20260908.md`.

**Контекст (срез A):** новый инструмент не нужен. ExchangeOrgLookup и другие коннекторы импортируют контакт из Exchange/GAL в `contacts.enc` через единый API upsert по источнику — вместо ad-hoc `add_alias`/`update_contact` и markdown-merge.

**Must-fix на диске:** в `~/USERTOOLS/AnywhereContacts/anywhere_contacts/store.py` лежит **черновик** `upsert_from_source` (утечка теневой ветки 07.09) — **заменить целиком**, не спасать. Известные дефекты черновика:
- `contacts.get(login or {})` — неверный lookup (пустой login / ложный miss);
- `status` не пересчитывается после union алиасов (остаётся `unchanged`, хотя `changed=True`).

Сопутствующий `tests/test_upsert_from_source.py` (опечатки, не green) — переписать вместе с методом, не считать готовым.

### Сигнатура

Добавить в `ContactStore` (`store.py`), реэкспорт из `anywhere_contacts/__init__.py`:

```python
def upsert_from_source(
    self,
    source: str,
    record: dict,
    strategy: MergeStrategy = MergeStrategy.FILL_ONLY_EMPTY,
    dry_run: bool = False,
) -> dict:
    ...
```

**Вход `record`** (минимум для ExchangeOrgLookup / GAL):
| Поле | Тип | Обязательность | Примечание |
|---|---|---|---|
| login | str | required | ключ контакта, lower-case |
| email | str | required | попадает в `sources[source].email` |
| fio / display_name / department / team / position | str | optional | basic fields |
| reports_to / manager_login | str | optional | `reports_to` — custom field |
| name_raw | str | optional | union в `aliases` |
| aliases | list[str] | optional | union в `aliases` |
| is_room | bool | optional | default False |

**Выход:**

```python
{
    "status": "created" | "updated" | "unchanged",
    "aliases_added": int,
    "conflicts": list[{"login", "field", "current", "incoming", "source"}],
    "login": str,
}
```

### Семантика (честный upsert по source)

1. **Create:** если `login` нет в `contacts` — новая запись schema v2 с `sources[source]={email, synced_at, active=True}`, `active=True`, пустые custom-поля; `fio`/`display_name` из record (fallback `name_raw`).
2. **Update basic fields:** по `strategy` — `FILL_ONLY_EMPTY` (default): только пустые; `OVERWRITE_BASIC`: перезапись отличий. Поля — `SOURCE_BASIC_FIELDS` + отдельно `is_room` (только False→True).
3. **`reports_to`:** заполнить только если пусто; при расхождении с непустым текущим — **conflict**, не перезаписывать молча.
4. **`sources[source]`:** всегда обновить `email`, `synced_at`, `active=True`; если merger ранее деактивировал источник — реактивировать; `active` верхнего уровня = `recompute_active()`.
5. **Aliases:** union `record.aliases` + `name_raw` (dedup case-insensitive); custom field, не затирать существующие.
6. **`dry_run=True`:** вычислить diff и вернуть результат, **не писать** на диск.
7. **`unchanged`:** если diff пуст — **не вызывать** `write()` (идемпотентность).
8. **Lock:** read-modify-write под `lock_context(default_lock_path(...))` (кроме `dry_run` без записи — по тому же паттерну, что `merge()` в коннекторах).

Не деактивировать другие источники — upsert одной записи, не batch-merge.

### Критерии успеха (проверяемые)

1. `upsert_from_source("exchange", record)` создаёт контакт, если login отсутствует; повтор с теми же данными → `status=unchanged`, файл не перезаписывается.
2. `name_raw` попадает в `aliases` без дубликатов при повторном upsert.
3. Конфликт `reports_to`: непустое локальное значение ≠ incoming → запись в `conflicts`, поле не меняется.
4. После `ContactMerger` с `sources.exchange.active=False` upsert реактивирует exchange и пересчитывает top-level `active`.
5. `dry_run=True` — diff корректен, `read()` после вызова без записи не меняется.
6. Fixture-тесты в `AnywhereContacts/tests/test_upsert_from_source.py` green без реального EWS.

### Что НЕ трогать

- Схему `contacts.enc` / `schema_version` 2.0, первичный ключ `login`.
- `ContactMerger.merge()` — batch-синк коннекторов; upsert — точечный API для OrgLookup/GAL.
- §9 PII: plaintext не возвращать потребителям; upsert пишет только в `contacts.enc`.
- `render_contact` / `*_for_display` — без изменений.
- Общий state канбана, манифест, ядро DevKanbanPipeline.

### Контракты (дополнение к §«Контракты экосистемы»)

| Направление | Контракт |
|---|---|
| **Потребитель → AnywhereContacts** | ExchangeOrgLookup вызывает `ContactStore.upsert_from_source(source="exchange", record=…)` |
| **Выход API** | Только зашифрованный `contacts.enc`; plaintext markdown (`tutu-contacts.md`) **запрещён** |
| **Breaking** | Сигнатура и семантика `upsert_from_source` — semver инструмента; смена полей `conflicts[]` — согласование с ExchangeOrgLookup |

### Атомарные шаги реализации (после «берём в работу»)

1. Удалить черновик `upsert_from_source` из `store.py`, реализовать по семантике выше.
2. Реэкспорт + docstring; при необходимости константы рядом с `merger.py` (reuse `SOURCE_BASIC_FIELDS`, `recompute_active`).
3. Переписать `tests/test_upsert_from_source.py` (create, idempotent, reports_to conflict, reactivate inactive source, dry_run, FILL_ONLY_EMPTY).
4. Регресс: `pytest AnywhereContacts/tests/` green.

**Реализация на диске:** реализовано (08.09.2026, контур A) — `upsert_from_source` в `store.py`, реэкспорт в `__init__.py`, тесты 46 passed. Черновик теневой ветки заменён.

---

## find_contacts: token-set fallback «Имя Фамилия» (v0.3.1, 20.10.2026)

Пакет BUGFIX DEV/pfs-name-resolve-fail. Канон поведения и AC —
§35 ProtocolFromSummary_TZ.md v1.30.0. Здесь — контракт метода.

`ContactStore.find_contacts(query)`:

1. Pass 1 — substring login / fio / email / aliases (без изменений).
   Непустой результат возвращается сразу.
2. Pass 2 — только если Pass 1 пуст и в query ≥2 токенов:
   все токены query ⊆ токены(fio ∪ display_name ∪ aliases),
   сравнение lowercase, токен = целое слово. 0/1/N без скоринга.

Сигнатура, schema_version 2.0, ключ `login`, PII display,
`upsert_from_source`, `ContactMerger` — без изменений.
Гипокористики и «Фамилия И.О.» — не этот метод (MOFS /
PFS §12 соответственно).

Потребители (PFS, MOFS, TaskRefresh через PFS, display)
патчить не обязаны: тот же вызов, больше хитов на reverse ФИО.
