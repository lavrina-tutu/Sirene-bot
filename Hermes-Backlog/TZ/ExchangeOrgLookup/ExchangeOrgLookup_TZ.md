---
tool: ExchangeOrgLookup
type: mini-tz
version: 0.3.0
date: 2026-09-08
status: active
last-section-added: "Exchange upsert (v0.3.0, 08.09)"
owner: Саша Ткаченко
epic: aggregate-from-meetings
backlog: bk-098
refs:
  - WorkVault/Hermes-Backlog/TZ/AggregateFromMeetings/modules/TZ_E_1on1.md (каскад резолва)
  - WorkVault/Hermes-Backlog/research/bk-098-exchange-org-lookup.md (исследование 2026-06-22)
  - PD-026, PD-042, PD-047
---

# Мини-ТЗ: Exchange Org Lookup (bk-098)

> Отдельный USERTOOL для пакетного резолва контактов через Exchange GAL (Global Address List).
> Фаза A.2 — пишется до старта кодирования модуля E (PD-047).

## 1. Цель (Назначение)

Резолвить ФИО/фрагменты имён, которые не нашлись в ContactStore штатным каскадом
(`email → fio → alias → token_subset → fuzzy`), обращаясь к корпоративному Exchange GAL,
и пополнять ContactStore найденными данными. Работает **батчем**, не inline — основной
пайплайн AggregateFromMeetings не блокируется сетевыми вызовами.

## 2. Контекст — место в системе

```
AggregateFromMeetings (E.Люди)
   └─ резолв не удался (not_found после fuzzy)
        → запись в очередь state/needs_gal.jsonl
                                   │
                                   ▼ (батч, по расписанию / вручную)
                        ExchangeOrgLookup
                          ├─ читает очередь needs_gal
                          ├─ запрос к Exchange GAL по ФИО/фрагменту
                          ├─ пишет результат в ContactStore (add_alias / новый контакт)
                          └─ помечает запись в очереди resolved
                                   │
                                   ▼
              AggregateFromMeetings ретригит встречи (штатный резолв из ContactStore)
```

⚠️ **ContactStore остаётся единственным writable store алиасов контактов (C4).**
Exchange GAL — источник данных, не хранилище. ExchangeOrgLookup только читает GAL и пишет в ContactStore.

## 3. Шаги — интерфейс и режим работы

### 3.1. Вход
- Очередь `USERTOOLS/AggregateFromMeetings/state/needs_gal.jsonl` (append-only JSON Lines).
  Запись:
  ```json
  {
    "name_raw": "Иванов Пётр",
    "meeting_id": "2026-06-19 Sync.md",
    "context": "обсуждали парсинг",
    "queued_at": "2026-06-19T18:00:00",
    "status": "needs_gal"
  }
  ```
- Допустимый вход — ФИО целиком или фрагмент (фамилия / имя+фамилия).

### 3.2. Выход
Для каждого разрешённого имени:
```json
{
  "name_raw": "Иванов Пётр",
  "email": "pivanov@tutu.ru",
  "login": "pivanov",
  "manager": "tkachenkoav",
  "match_confidence": "high|medium|low",
  "resolved_at": "..."
}
```
- `email` — корпоративный адрес из GAL
- `login` — login-часть email (для ключа People/{login}/)
- `manager` — руководитель из GAL (поле `reports_to` для иерархии, см. TZ_A `reports_to`)

### 3.3. Запись результатов
- `ContactStore.add_alias(login, alias=name_raw, source="exchange_gal")` — если контакт уже есть.
- Создание нового контакта в ContactStore с `email`, `login`, `reports_to=manager` — если контакта нет.
- Запись в очереди помечается `status=resolved` (или `not_found`, если GAL пуст).

### 3.4. Режим работы
- **Батч** — обходит всю очередь `needs_gal` за один прогон.
- **Триггер:** по расписанию (cron, частота — см. открытый вопрос) **и** ручной запуск.
- Не вызывается inline из основного цикла AggregateFromMeetings.
- После прогона — сигнал AggregateFromMeetings ретригнуть встречи с разрешёнными именами.

### 3.5. Каскад и фоллбэки
1. Точный матч ФИО в GAL → `high`.
2. Частичный (фамилия + инициал / фрагмент) с единственным кандидатом → `medium`.
3. Несколько кандидатов в GAL → не выбираем автоматически: запись `ambiguous` → в дайджест PM на подтверждение (как `unclear_names`).
4. GAL ничего не вернул → `not_found` → имя уходит в `state/unclear_names.jsonl` (PM подтверждает/создаёт вручную).

## 4. Критерии успеха

1. `orglookup bootstrap` пробегает все строки `tutu-contacts.md` c `reports_to ∈ {—, ?}` и резолвит ≥80% через EWS без сетевых таймаутов.
2. Двухшаговый резолв `email → contact.manager (display_name) → ResolveNames → manager_email → login = local-part` работает и корректно заполняет `reports_to` в ContactStore.
3. Disambiguation по `department` при >1 кандидатов работает; при отсутствии hint запись уходит в `ambiguous`, а не выбирается молча.
4. Конфликт с уже стоящим значением `reports_to`/`aliases` в ContactStore/`tutu-contacts.md` не перезаписывается молча: показывается diff + запись в `~/WorkVault/_meta/OrgLookup/_log.jsonl`.
5. Инструмент не блокирует основной пайплайн AggregateFromMeetings — все вызовы EWS идут только в батч-режиме, инлайн-триггера из E.Люди нет.
6. Fixture-based тесты (без реального EWS) покрывают: успешный резолв, ambiguous (>1 кандидата), not_found, конфликт merge, двухшаговый manager-chain.
7. При отсутствии VPN до `cas.tutu.ru:443` инструмент завершается ошибкой с понятным сообщением, очередь не портится.

## 5. Что НЕ трогать

- **ContactStore (AnywhereContacts) остаётся единственным writable store алиасов контактов.** Exchange GAL — источник, не хранилище. Прямая запись в `contacts.enc` мимо `ContactStore.add_alias`/API — запрещена.
- **Основной пайплайн AggregateFromMeetings** не блокируется синхронными вызовами EWS. Только батч-режим по расписанию/руками, не inline из E.Люди.
- **LDAP не реализовывать** — недоступен (см. §7, подтверждено исследованием 2026-06-22).
- **Ручные `reports_to` / `aliases` в `tutu-contacts.md`** — не перезаписывать молча. При конфликте — diff + лог + ручное решение PM.
- **MeetingScheduler.exchange_client** и venv `~/USERTOOLS/AnywhereContacts/venv_linux/` — переиспользуем как есть, не форкать/копировать.

## 6. Доступ и секреты

- Exchange доступ через **EWS** (см. §7 «Решения»). Креды — `~/.config/hermes/.env` (по аналогии с `CONFLUENCE_TOKEN`, реально: `TUTU_DOMAIN_PASSWORD` + учётка `tkachenkoav@tutu.ru`, авторизация через `MeetingScheduler.exchange_client.get_account()`).
- Зависимость от корп-VPN до `cas.tutu.ru:443` — как у MeetingScheduler.

## 7. Решения (утверждено исследованием 2026-06-22)

- **Протокол доступа к GAL — EWS.** LDAP/389 наружу закрыт (`Connection refused` на `tutu.ru`, `cas.tutu.ru`; `ad.tutu.ru`/`dc.tutu.ru`/`tutu.local` → NXDOMAIN). MS Graph не рассматривался — EWS уже покрывает 100% кейсов. Библиотека `exchangelib==5.6.0` уже в `~/USERTOOLS/AnywhereContacts/venv_linux/`.
- **Модель данных из EWS:** `Contact.manager` приходит как **display-name строка** (`"Aralov Aleksandr"`), а не email; `manager_mailbox`/`direct_reports` пустые. → двухшаговый резолв: `ResolveNames(employee) → contact.manager (str) → ResolveNames(str) → manager.email → login = local-part`.
- **Cyrillic-поиск в GAL не работает** (`No results were found` на `"Криворотов"`, `"Ткаченко"`). Резолвить только латиницей: приоритет `email → surname-latin` (транслит-словарь `translit.yaml` + ГОСТ, ручные исключения по факту).
- **Файловая структура:** отдельный `~/USERTOOLS/OrgLookup/` (не лезть в AnywhereContacts — другой жизненный цикл и store).

## 8. Решения (утверждено Сашей 06.07.2026)

### Q1. Частота батча
**Решено:** ночной cron 1 раз в сутки (03:00) + ручной запуск командой. Обоснование: EWS-батч на 30–50 имён = 15–40 сек, ночью не мешает пайплайну, ретриг встреч после утреннего прогона AggregateFromMeetings уже видит свежий ContactStore.

### Q2. Политика для `ambiguous` (>1 кандидата в GAL)
**Решено (альтернативный вариант):** автоселект топ-1 c `match_confidence=low` (сортировка по department-совпадению → по алфавиту email) и логированием; PM ретроспективно чинит через `orglookup fix`.

### Q3. Поле `manager` в GAL — гарантии доступности
**Решено:** не гарантировать 100% — при пустом `manager` запись в ContactStore без `reports_to`, отдельная очередь `state/missing_manager.jsonl` для последующей ручной простановки.

## 9. Связь с бэклогом

- ^bk-098 — Exchange Org Lookup.
- Зависимость AggregateFromMeetings: TZ_E «Exchange GAL fallback» (каскад + очередь `needs_gal`).

---

## Доработка: выгрузка переговорных комнат (2026-07-09)

### Цель

Дать инструменту `orglookup` команду выгрузить из Exchange GAL список **переговорных комнат ТУТУ** (resource mailboxes — «Тайга», «Пустыня», «Мутный материк» и т.п.) и сохранить их отдельным Markdown-файлом в WorkVault. Файл — источник правды для внешних потребителей (в первую очередь — скилл `workvault-rag`).

### Контекст

- Бизнес-триггер: скиллу `workvault-rag` нужен признак «встреча проведена в переговорке» → в Fireflies-summary такие Action Items с большой вероятностью **ошибочно атрибутируются переговорке как спикеру**. При наличии списка переговорок эти AI по умолчанию будут переназначены на самого Сашу.
- Названия комнат тематические (не по этажам), точный список неизвестен — его и нужно получить из GAL.
- Исторический контекст: в скилле `about_usr_skills` есть отказ «fetch_rooms() убрать из scope» — это решение относилось к **другому, ныне decommissioned** инструменту MoveFromExchange v1.1 (весна 2026, общий контакт-синк). **Не применимо** к текущей задаче: другой инструмент, другая цель (не синк контактов, а отдельный справочник переговорок для RAG-фильтрации).
- Physical placement: `MoveFromExchange` decommissioned, кода нет (`find` в `$HOME` подтвердил). Единственный живой Exchange-инструмент — `~/USERTOOLS/OrgLookup/` (пакет `orglookup`). Доработка встраивается сюда.

### Где хранить результат — решено

- Отдельный файл: **`~/WorkVault/Contacts/meeting-rooms.md`** — простая Markdown-таблица.
- Формат (минимум):

  ```markdown
  ---
  type: reference
  source: exchange-gal
  updated: YYYY-MM-DD
  generator: orglookup rooms
  ---

  # Переговорные комнаты ТУТУ

  | Название | Email (resource mailbox) | Вместимость |
  |---|---|---|
  | Тайга | taiga@tutu.ru | 8 |
  | Пустыня | desert@tutu.ru | 4 |
  | Мутный материк | murky-continent@tutu.ru | — |
  ```

- Колонка «Вместимость» — best-effort: заполняется, если GAL/`Room` возвращает такое поле; иначе `—`.
- **НЕ смешивать** с `contacts.enc` / `tutu-contacts.md` — переговорки не люди, отдельная сущность, отдельный источник правды. ContactStore (AnywhereContacts) для комнат не используется.

### Технические решения

- **EWS API — доступен в exchangelib==5.6.0** (проверено 2026-07-09 в `~/USERTOOLS/AnywhereContacts/venv_linux/`):
  - `account.protocol.get_roomlists() -> list[RoomList]` — возвращает настроенные в Exchange списки комнат (distribution groups с флагом `IsRoomList`).
  - `account.protocol.get_rooms(roomlist) -> list[Room]` — для каждого списка возвращает мейлбоксы комнат (name + email_address).
  - Дополнительно (best-effort): по email комнаты можно сделать `resolve_names(email, return_full_contact_data=True)` — если Exchange хранит capacity в `Contact.physical_addresses`/`department`/custom-полях, дозаполнить.
- **Фоллбэк (обязательный)** — если `get_roomlists()` вернёт пусто (у ТУТУ Exchange может не быть настроенных Room Lists — это административная фича, включается вручную админом), инструмент **обязан не падать**: логировать ворнинг и предлагать заполнить `meeting-rooms.md` вручную (или из явно переданного файла-сида).
- **Не резолвим кириллицу** через ResolveNames (см. §7 основного ТЗ). Название комнаты берём как есть из `Room.name` (там уже человекочитаемый display-name, кириллица в результате EWS-ответа приходит нормально — это только `search_string` не работает по-русски).
- **Кэш/лог:** `~/USERTOOLS/OrgLookup/cache.jsonl` уже используется — не мешаем. Сырой ответ EWS для аудита пишем в `~/WorkVault/_meta/OrgLookup/_log.jsonl` записью типа `{"op":"fetch_rooms", ...}`.

### Шаги

1. Новый модуль `orglookup/rooms.py`: dataclass `MeetingRoom(name, email, capacity, source_roomlist)` + функция `fetch_rooms(account=None, resolve_names_fn=None) -> list[MeetingRoom]`. Один сетевой вход, полностью тестируемая через inject-функцию (по паттерну `resolver.resolve_names_fn`).
2. Новый writer `orglookup/rooms_writer.py` (или расширение `md_writer.py` функцией `render_rooms_md(rooms, updated_at) -> str`): рендер таблицы + frontmatter, идемпотентно (одинаковый вход → одинаковый выход).
3. Новая CLI-команда `orglookup rooms` в `cli.py`: `--dry-run` (печатает MD в stdout), `--file <path>` (по умолчанию `~/WorkVault/Contacts/meeting-rooms.md`), `--from-seed <path>` (заполнить из локального JSON/YAML, минуя EWS — фоллбэк).
4. Fixture-based тесты: `tests/test_rooms.py` (парсинг ответа EWS через фейковый `get_roomlists`/`get_rooms` → `list[MeetingRoom]`), `tests/test_rooms_writer.py` (рендер таблицы + идемпотентность). Фикстуры — `tests/fixtures/rooms_*.json`. **Без реального EWS.**
5. Пустой ответ EWS = не ошибка. `fetch_rooms()` возвращает `[]`, CLI печатает ворнинг в stderr, файл не перезаписывается пустым (сохраняется предыдущий, если есть).
6. README / usage: короткая заметка в `~/USERTOOLS/OrgLookup/README.md` (если файл есть — дописать секцию `## Rooms`; если нет — не создавать, оставить `--help`).

### Критерии успеха

1. `orglookup rooms --dry-run` при живом VPN выводит на stdout валидный Markdown с таблицей переговорок (≥1 строка), либо явно печатает `WARN: GAL не вернул room lists (у Exchange не настроены RoomLists)` и ненулевой exit code.
2. `orglookup rooms` (без `--dry-run`) записывает файл `~/WorkVault/Contacts/meeting-rooms.md` идемпотентно (повторный запуск при неизменных данных → файл байт-в-байт тот же, кроме поля `updated:` в frontmatter).
3. При отсутствии VPN — понятная ошибка `RuntimeError`/`VPNError`, файл не тронут.
4. `orglookup rooms --from-seed <file>` работает без сети — конвертирует seed (JSON: `[{"name":..., "email":..., "capacity":...}]`) в тот же `meeting-rooms.md`. Фоллбэк для случая «Exchange не даёт данных».
5. Fixture-based тесты покрывают: (а) успешный fetch с 1 roomlist + N rooms, (б) успешный fetch с 0 roomlist → `[]`, (в) rendering таблицы + идемпотентность, (г) seed-режим CLI (без EWS).
6. Никаких изменений в `contacts.enc`, `tutu-contacts.md`, ContactStore, `.env`, других venv-ах.

### Что НЕ трогать

- ContactStore / `contacts.enc` / `tutu-contacts.md` — переговорки идут отдельным файлом, никакого пересечения.
- Существующие команды `who` / `manager` / `add` / `bootstrap` / `tree` — не менять их поведение и подписи, только добавить новую `rooms`.
- Авторизацию: переиспользуем `ews_client.get_account()` (который уже переиспользует `MeetingScheduler.exchange_client.get_account()`) — своей авторизации не заводим.
- `venv_linux/` других инструментов — только чтение (для проверки версий), никаких `pip install`.

### Открытые вопросы / риски

- **R1 (частично снят).** exchangelib 5.6.0 подтверждён — API `get_roomlists`/`get_rooms` есть. **Не подтверждено**, что в Exchange ТУТУ настроены Room Lists (это делает Exchange-админ командой `New-DistributionGroup -RoomList`). Если нет — `get_roomlists()` вернёт пусто. **Митигация:** фоллбэк `--from-seed` (шаг 3) + возможность попросить админа ТУТУ включить Room List (отдельная задача, не блокер).
- **R2.** Capacity в `Room` через EWS может не приходить (поле не гарантировано). Митигация: колонка «Вместимость» толерантна к `None` → `—`.
- **R3.** Название переговорки в кириллице (`"Тайга"`) — приходит корректно из `Room.name` (это response, а не search_string). Проверить на первом реальном запуске; если приедет транслитом — задача Sonnet прописать маппинг seed-файлом.

## Пофайловый план реализации (для Sonnet)

Все пути относительно `~/USERTOOLS/OrgLookup/`. Патч архитектуру существующих модулей **не меняет** — только добавляет.

### Файлы к созданию

1. **`orglookup/rooms.py`** (~80 строк)
   - `@dataclass class MeetingRoom`: `name: str`, `email: str`, `capacity: Optional[int] = None`, `source_roomlist: str = ""`.
   - `def fetch_rooms(account=None, get_roomlists_fn=None, get_rooms_fn=None) -> list[MeetingRoom]`:
     - inject-параметры `get_roomlists_fn` / `get_rooms_fn` = для тестов (по паттерну `resolver.resolve` c `resolve_names_fn`).
     - Дефолт: `account = account or ews_client.get_account()`; `get_roomlists_fn = account.protocol.get_roomlists`; `get_rooms_fn = account.protocol.get_rooms`.
     - Проход: для каждого `rl` в `get_roomlists_fn()` → для каждого `room` в `get_rooms_fn(rl)` → нормализовать в `MeetingRoom`.
     - Дедуп по email (одна комната может числиться в двух roomlist-ах).
     - Пустой ответ → `[]`, ошибки сети — пробросить как есть (CLI обрабатывает).
   - Логирование: `_log_op("fetch_rooms", {"roomlists": [...], "rooms_count": N})` в `_meta/OrgLookup/_log.jsonl` (по паттерну из `md_writer.py`, вынести общий хелпер если нужно).
   - **Критерий готовности:** импорт работает, unit-тест на inject-функцию проходит.

2. **`orglookup/rooms_writer.py`** (~60 строк) — отдельно от `md_writer.py`, т.к. схема таблицы и семантика идемпотентности другие.
   - `def render_rooms_md(rooms: list[MeetingRoom], updated: date | None = None) -> str`: frontmatter + заголовок + таблица. Сортировка комнат по `name` (стабильная). `capacity=None → "—"`.
   - `def write_rooms_md(rooms, path, dry_run=False) -> str`: если `dry_run` — вернуть текст; иначе — записать в `path`. При пустом `rooms` — **не перезаписывать** (сохранить предыдущий файл), вернуть предупреждение отдельным маркером/exception.
   - **Критерий готовности:** повторный вызов на одних и тех же `rooms` (и одном `updated`) даёт байт-в-байт одинаковый результат.

3. **`tests/test_rooms.py`** (~60 строк) — fixture-based, без сети.
   - `test_fetch_rooms_single_list_ok`: fake `get_roomlists_fn`/`get_rooms_fn` из `fixtures/rooms_single_list.json` → 3 комнаты.
   - `test_fetch_rooms_empty_gal_returns_empty_list`: fake `get_roomlists_fn` → `[]`. Ассерт: `fetch_rooms(...)` = `[]`, исключений нет.
   - `test_fetch_rooms_dedup_across_roomlists`: одна комната в двух списках → одна запись в результате.
   - `test_fetch_rooms_capacity_optional`: комната без capacity → `MeetingRoom.capacity is None`.

4. **`tests/test_rooms_writer.py`** (~50 строк).
   - `test_render_rooms_md_snapshot`: детерминированный вход → сравнение со сниппетом-эталоном.
   - `test_render_rooms_md_idempotent`: `render_rooms_md(rooms, updated=D) == render_rooms_md(rooms, updated=D)`.
   - `test_write_rooms_md_does_not_overwrite_on_empty`: если `rooms=[]` и файл существует — файл не тронут.
   - `test_render_capacity_none_dash`: `capacity=None` рендерится как `—`.

5. **`tests/fixtures/rooms_single_list.json`** — фейковый ответ (структура: `{"roomlists": [{"name":..., "email":...}], "rooms": {"<roomlist_email>": [{"name":"Тайга","email":"taiga@tutu.ru","capacity":8}, ...]}}`).
6. **`tests/fixtures/rooms_empty.json`** — `{"roomlists": []}`.
7. **`tests/fixtures/rooms_dedup.json`** — одна комната в двух списках.

### Файлы к изменению

8. **`orglookup/cli.py`** — добавить:
   - `def cmd_rooms(args)`: три ветки — `--from-seed` (читать JSON, минуя EWS), обычный (fetch через EWS), `--dry-run` (печать в stdout вместо записи файла). При отсутствии VPN — `stderr` + exit 2 (по паттерну `cmd_bootstrap`).
   - Регистрация в `build_parser()`:
     ```
     p_rooms = sub.add_parser("rooms", help="Выгрузить список переговорок из GAL в WorkVault")
     p_rooms.add_argument("--file", default=None)         # ~/WorkVault/Contacts/meeting-rooms.md
     p_rooms.add_argument("--from-seed", default=None)    # fallback: JSON без EWS
     p_rooms.add_argument("--dry-run", action="store_true")
     p_rooms.set_defaults(func=cmd_rooms)
     ```
   - Дефолт пути: `DEFAULT_ROOMS_MD = Path.home() / "WorkVault" / "Contacts" / "meeting-rooms.md"`.

9. **`orglookup/__init__.py`** — расширить `__all__` (если он там есть), добавить `rooms`, `rooms_writer` в реэкспорт (по паттерну).

10. **`README.md`** (опционально, только если файл существует) — секция `## Rooms` с примерами: `orglookup rooms --dry-run` / `orglookup rooms` / `orglookup rooms --from-seed rooms.json`.

### Что делать не надо

- Не менять `ews_client.py` — API `get_account()` и `resolve_names()` достаточно; новые EWS-вызовы (`get_roomlists`/`get_rooms`) вызываются через `account.protocol.*` прямо из `rooms.py`. Если понадобится вынести — отдельным рефакторингом позже.
- Не заводить cron: команда `orglookup rooms` запускается **по требованию** (список переговорок меняется редко — раз в квартал в худшем случае). Cron — отдельная задача, если/когда появится.
- Не добавлять запись в ContactStore. Комнаты — отдельный источник.

## Прогресс выполнения

- [x] Шаг 1. `orglookup/rooms.py` — `MeetingRoom` + `fetch_rooms()` с inject-функциями. (2026-07-09, Sonnet)
- [x] Шаг 2. `orglookup/rooms_writer.py` — `render_rooms_md()` + `write_rooms_md()` с идемпотентностью и защитой от пустого ответа. (2026-07-09, Sonnet)
- [x] Шаг 3. `cli.py` — команда `rooms` (`--dry-run`, `--file`, `--from-seed`) + регистрация в парсере. (2026-07-09, Sonnet)
- [x] Шаг 4. Фикстуры `tests/fixtures/rooms_single_list.json`, `rooms_empty.json`, `rooms_dedup.json`. (2026-07-09, Sonnet)
- [x] Шаг 5. `tests/test_rooms.py` (4 теста) — прогон `pytest tests/test_rooms.py` зелёный. (2026-07-09, Sonnet)
- [x] Шаг 6. `tests/test_rooms_writer.py` (4 теста) — прогон зелёный. (2026-07-09, Sonnet)
- [x] Шаг 7. Живой прогон при VPN: `orglookup rooms --dry-run` → MD на stdout **или** явный WARN о пустом GAL. (2026-07-09, Sonnet: живой ответ, 31 переговорка в dry-run, R1 не подтвердился — Room Lists у ТУТУ настроены)
- [x] Шаг 8. Живой прогон (если EWS дал данные) без `--dry-run`: файл `~/WorkVault/Contacts/meeting-rooms.md` создан, повторный запуск идемпотентен. (2026-07-09, Sonnet: 32 переговорки, md5 идентичен при повторном запуске)
- [x] Шаг 9. Если EWS данных не даёт — smoke seed-режима: `orglookup rooms --from-seed sample.json` → файл создан. (2026-07-09, Sonnet: НЕ ПОТРЕБОВАЛОСЬ — EWS дал реальные данные (шаг 7-8), R1 не реализовался на практике; фоллбэк-код `--from-seed` реализован и покрыт готовностью к отдельному smoke по требованию)
- [x] Шаг 10. Обновить `MAIN_TZ_INVENTORY.md` (дата ExchangeOrgLookup) — уже сделано на этапе доработки ТЗ.

---

## Контракты экосистемы

### Источник истины
- Владелец корпоративных учетных записей и структуры подчинения: Exchange GAL (`api_exchange`)
- Владелец реестра контактов WorkVault: AnywhereContacts (`ContactStore`, `contacts.enc`, ключ — `login`)
- Владелец справочника переговорных комнат: ExchangeOrgLookup (`~/WorkVault/Contacts/meeting-rooms.md`)

### Входные контракты
| Поле | Тип | Обязательность | Источник (кто отдаёт) | Формат/enum |
|---|---|---|---|---|
| name_raw | str | required | AggregateFromMeetings (`needs_gal.jsonl`) | ФИО или фрагмент имени для резолва |
| meeting_id | str | optional | AggregateFromMeetings (`needs_gal.jsonl`) | Имя файла встречи / ID |
| context | str | optional | AggregateFromMeetings (`needs_gal.jsonl`) | Контекстное описание встречи |
| queued_at | datetime(iso8601) | optional | AggregateFromMeetings (`needs_gal.jsonl`) | Время постановки в очередь |
| status | enum[needs_gal, resolved, not_found, ambiguous] | optional | AggregateFromMeetings (`needs_gal.jsonl`) | Статус записи в очереди |

### Выходные контракты
| Поле | Тип | Потребитель (кто получает) | Формат/enum |
|---|---|---|---|
| login | str | AnywhereContacts | `json:contact_v2`, login-часть email до "@" |
| email | str | AnywhereContacts | `json:contact_v2`, валидный корпоративный email (@tutu.ru) |
| reports_to | str | AnywhereContacts | login руководителя из GAL |
| alias | str | AnywhereContacts | исходное `name_raw` как псевдоним |
| name | str | workvault-rag (`meeting-rooms.md`) | название переговорной комнаты |
| email | str | workvault-rag (`meeting-rooms.md`) | resource mailbox email переговорки |
| capacity | int | workvault-rag (`meeting-rooms.md`) | вместимость комнаты (или "—" при отсутствии) |

### Зависимости
- Получает от: [AggregateFromMeetings, Exchange GAL]
- Отдаёт: [AnywhereContacts, workvault-rag]

### Breaking changes policy
- Совместимость полей ContactStore: при изменении схемы вызова `ContactStore.add_alias` или формата создания контакта требуется согласование с AnywhereContacts.
- Формат `meeting-rooms.md`: сохранять структуру Markdown-таблицы с frontmatter (`type: reference`, `source: exchange-gal`).

### Границы («что НЕ трогать»)
- ContactStore (AnywhereContacts) остаётся единственным writable store алиасов контактов. Прямая запись в `contacts.enc` запрещена.
- Основной пайплайн AggregateFromMeetings не блокируется синхронными вызовами EWS (только батч/cron).
- Ручные `reports_to` / `aliases` в `tutu-contacts.md` не перезаписываются молча при конфликте.

---

## Exchange upsert (v0.3.0, 08.09)

**Статус: реализовано и протестировано 08.09.2026** (контур A): `cmd_add` — VPN exit 2, живой `--dry-run`, запись через `upsert_gal_result`; `cmd_bootstrap` persist — через `upsert_gal_result` (не md-merge); `upsert_gal_result` в `md_writer.py`; KeyError:pass убран; тесты OrgLookup 37 passed (26 старых + 11 новых по v0.3.0). План досбора: `TZ/AnywhereContacts/HF-plan_exchange-contact-upsert_20260908.md`.

**Код инструмента:** `~/USERTOOLS/OrgLookup/` (пакет `orglookup`).

**Контекст:** импорт контакта из Exchange GAL в `contacts.enc` — через `ContactStore.upsert_from_source()`, а не через markdown-merge + `add_alias` на несуществующем login.

**Must-fix на диске:**

1. **`md_writer.py:217-221`** — при создании нового контакта вызывается `contact_store.add_alias(login, …)`, `KeyError` глотается (`pass`). Контакт в `contacts.enc` **не создаётся**. Заменить путь записи на `upsert_from_source`.
2. **`cli.py` `cmd_add`** — флаг `--dry-run` зарегистрирован в argparse, но **не читается** в теле функции (мёртвый). Должен: резолв GAL → upsert с `dry_run=True` → JSON на stdout, без записи, exit 0.
3. **`cli.py` `cmd_add`** — нет проверки VPN до EWS (в отличие от `cmd_bootstrap` / `cmd_rooms`). Добавить `ews_client.check_vpn()` в начале; при отсутствии доступа до `cas.tutu.ru:443` — stderr + **exit 2** (тот же паттерн, что bootstrap/rooms).

### Цель

`orglookup add` и batch-пути (`bootstrap`, merge из GAL) пишут контакт **честно** в `contacts.enc` одним upsert-вызовом; конфликты `reports_to` и прочие — в `conflicts[]` upsert + лог; plaintext markdown не используется.

### Семантика `md_writer` / `cmd_add`

**Было (неверно):** `merge()` строит in-memory markdown-таблицу; для нового login — строка в таблице + best-effort `add_alias` (KeyError → pass).

**Станет:**
- Запись в ContactStore **только** через `ContactStore.upsert_from_source(source="exchange", record=resolved_dict)`.
- `record` — dict после `resolver` + `hierarchy.get_manager_login` (поля как в AnywhereContacts § v0.3.0).
- Конфликты из upsert → `_log_conflict()` в `~/WorkVault/_meta/OrgLookup/_log.jsonl` (существующий паттерн).
- `merge()` для **plaintext md** — deprecated для записи контактов; допустимо оставить parse/serialize для тестов legacy, но **production-путь add/bootstrap** не пишет `tutu-contacts.md` и не полагается на md-строки как store.

**`cmd_add` (поведение после реализации):**

1. VPN check → exit 2 если нет.
2. `resolver.resolve(name, hint_department=dept)`.
3. `not_found` → JSON + exit 1 (как сейчас).
4. Собрать `record`, вызвать `store.upsert_from_source(..., dry_run=args.dry_run)`.
5. `--dry-run`: JSON с результатом upsert + `render_contact(..., level=…)`, **без** записи, exit 0.
6. Без `--dry-run`: upsert пишет в `contacts.enc`; JSON с `status`, `aliases_added`, `conflicts`, masked contact.

**`cmd_bootstrap`:** аналогично перевести финальную запись с `md_writer.merge(..., contact_store=adapter)` на цикл `upsert_from_source` (batch остаётся batch, но store — upsert, не md-merge). `--dry-run` уже работает — сохранить семантику.

### Критерии успеха (проверяемые)

1. `orglookup add "Новый Сотрудник"` при отсутствии login в store создаёт запись в `contacts.enc` (не только JSON stdout).
2. Повторный `add` с теми же GAL-данными → upsert `unchanged`, без лишней записи на диск.
3. `orglookup add --dry-run …` не меняет `contacts.enc` (mtime/содержимое).
4. `orglookup add` без VPN → exit 2, понятное сообщение, store не тронут.
5. Конфликт `reports_to` → в stdout `conflicts`, в `_log.jsonl` запись, поле в store не перезаписано молча.
6. Fixture-тесты OrgLookup (без EWS) покрывают: create via upsert, dry-run, KeyError-regression (новый контакт не теряется).

### Что НЕ трогать

- ContactStore — единственный writable store; прямой crypto/write мимо API запрещён.
- Plaintext `tutu-contacts.md` — **не возвращать** (guard `PlaintextContactsMdForbidden` остаётся).
- Команды `who` / `manager` / `tree` / `rooms` — поведение без изменений (кроме общих хелперов, если вынесут upsert-wrapper).
- `ews_client`, `resolver`, `hierarchy` — контракты GAL без изменений.
- AggregateFromMeetings pipeline, `needs_gal.jsonl`, LDAP.
- Общий state канбана, манифест, ядро DevKanbanPipeline.

### Контракты (дополнение)

| Направление | Контракт |
|---|---|
| **ExchangeOrgLookup → AnywhereContacts** | `upsert_from_source(source="exchange", record=…)` — единственный write-path для GAL-import |
| **Выход пользователю** | JSON + `render_contact(level=summary\|full)`; plaintext contacts.md **не генерировать** |
| **Зависимость версий** | OrgLookup v0.3.0 реализация **после** AnywhereContacts `upsert_from_source` в пакете (HF:plan — сначала AC, потом OrgLookup) |

### Пофайловый план (после «берём в работу»)

Пути относительно `~/USERTOOLS/OrgLookup/`:

1. **`orglookup/md_writer.py`** — убрать KeyError-pass путь; функция upsert-записи (или thin wrapper над `ContactStore.upsert_from_source`); bootstrap/add вызывают её вместо md-merge write.
2. **`orglookup/cli.py`** — `cmd_add`: VPN exit 2, обработка `--dry-run`, вызов upsert.
3. **`orglookup/cli.py`** — `cmd_bootstrap`: финальная запись через upsert (не `merge`→adapter для persist).
4. **`tests/`** — регресс create-контакта, dry-run, VPN mock; обновить тесты, завязанные на `merge`+adapter.
5. README/`--help` — при наличии файла, одна строка про `--dry-run` у `add`.

### План досбора (HF-plan)

→ `TZ/AnywhereContacts/HF-plan_exchange-contact-upsert_20260908.md` (общий план на slug `exchange-contact-upsert`).

**Реализация на диске:** реализовано (08.09.2026, контур A) — `upsert_gal_result` в `md_writer.py`, `cmd_add` (VPN exit 2, `--dry-run`), `cmd_bootstrap`→upsert; тесты OrgLookup 37 passed. KeyError:pass устранён.

