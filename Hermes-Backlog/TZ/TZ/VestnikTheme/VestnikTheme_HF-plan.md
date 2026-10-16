---
tool: VestnikTheme
type: hf-plan
title: "Анализ вариантов + пофайловый план (hermes-feature Блок 1 / 1А)"
version: 0.1.0
date: 2026-09-07
status: draft-plan
phase: hermes-feature-1A
source_tz: TZ/VestnikTheme/VestnikTheme_TZ.md
source_tz_version: 0.2.0
author: архитектор (cursor-grok-4.6-high, Cursor CLI)
recommended_variant: 1
---

# VestnikTheme — план реализации (Блок 1 / 1А)

Источник истины: `~/WorkVault/Hermes-Backlog/TZ/VestnikTheme/VestnikTheme_TZ.md` v0.2.0. Код не пишется до «берём в работу» по этому плану. Исполнитель (composer-2.5) идёт сверху вниз по волнам; промежуточные точки — молча.

Дом кода (канон, симлинк уже сходится):

```
~/hermes-workspace/skills/productivity/tutu-confluence-jira/
  = ~/.hermes/skills/productivity/tutu-confluence-jira   (realpath)
```

Писать только сюда. Каталог `~/USERTOOLS/VestnikTheme/` и скилл `productivity/vestnik-theme` **не** создавать.

---

## 1. Сводка рекомендации

**Вариант 1.** Модульные `scripts/vestnik_theme_*.py` в скилле `tutu-confluence-jira`. HTTP — urllib-стек уже существующего `section_patch.py` (`load_confluence_token`, `_api_request`, `build_put_payload`, `put_page`) с **локальным** GET `expand=body.storage,version,space,history` (контракт `section_patch.get_page` не менять: там только `body.storage,version`). Разбор ссылок — `ConfluenceSync.confluencesync.url_utils.parse_confluence_url` через импорт файла, **без** `from confluencesync import …` (пакетный `__init__.py` тянет `sync`/converter). Автор — `userkey_resolve.ConfluenceUserClient` + `resolve_user`, без `write_contacts`. «Блок» — `ContactStore.get_contact` / `find_contacts` (read-only) + inline EWS `ResolveNames` в `vestnik_theme_ews.py` через `MeetingScheduler/exchange_client.py` (file-import, не пакетный `__init__.py`). PUT только `--apply`, payload без `space`, `version.number+1`. Патч — string-splice первой пустой `<tr>` первой таблицы первого `horizontal-nav-item`. Verify — отдельный `vestnik_theme_verify.py` (не heading-`verify_skeleton.py`).

Почему не 2: `ConfluenceClient` требует `tenacity`; в каноническом EWS/AC venv (`AnywhereContacts/venv_linux`) tenacity нет, в `ConfluenceSync/.venv` нет `exchangelib`/`loguru`. Почему не 3: тот же стек, но один жирный файл хуже тестируется и дороже по токенам на каждую правку.

Отсеяно без номера: расширять `section_patch.py` / `verify_skeleton.py` режимом «таблица вкладок» — прямое нарушение ТЗ («не ломать контракт»).

Новых сущностей нет (нет USERTOOL, нет нового скилла, нет крона, `entities.json` не трогаем).

---

## 2. Варианты 1 / 2 / 3

Шкала по 4 критериям: **лучше / средне / хуже**.

### Вариант 1 — модули + urllib скилла + url_utils + AC read + inline EWS (рекомендуемый)

Состав: 9 скриптов `vestnik_theme*.py` + тесты + секция SKILL.md. HTTP = существующий urllib скилла. ConfluenceSync = только чистый `url_utils.py`. Userkey = импорт функций, файл не править. EWS = `get_account()` из `exchange_client.py` + `account.protocol.resolve_names` внутри `vestnik_theme_ews.py`. Live Python для GAL/AC: `~/USERTOOLS/AnywhereContacts/venv_linux/bin/python`. Юнит-тесты: системный `python3` + фейки (как сейчас 13 тестов скилла).

| Критерий | Оценка | Факт с диска |
|---|---|---|
| Токены | **лучше** | Маленькие модули; оркестратор тонкий; исполнитель правит один файл на шаг ТЗ. |
| Безопасность | **лучше** | Токен: `load_confluence_token` (не `source` всего `.env`). AC: только read, `render_contact(level="summary")` в превью. GAL in-memory, `contacts.enc` не писать. Userkey только после `GET /rest/api/user?key=`. PUT без `space`. LLM не собирает storage. |
| Консистентность | **лучше** | Тот же HTTP/PUT, что PFS/B0. Userkey-путь тот же, что `userkey_resolve.py`. Контакты — тот же `ContactStore`. EWS-креды — тот же `exchange_client.get_account` (OrgLookup TZ §6). |
| Поддерживаемость | **лучше** | Контракт трёх существующих скриптов не меняется. Откат = удалить новые файлы + вырезать секцию SKILL.md. Один runtime для AC+EWS (`venv_linux`); Confluence stdlib-urllib работает и там, и в системном python3. |

Риски (закрываются тестами, не архитектурой): вложенность `horizontal-nav-item`; `username` Confluence ≠ corp `login`; 409; отсутствие пустой `<tr>`.

### Вариант 2 — модули + класс `ConfluenceClient` как HTTP

Те же модули, но GET/PUT через `confluencesync.confluence_client.ConfluenceClient` (`get_page`, `update_page` без `space_key`, `resolve_ref_to_page_id`).

| Критерий | Оценка | Факт с диска |
|---|---|---|
| Токены | средне | Плюс: готовый `resolve_ref_to_page_id`. Минус: импорт пакета `confluencesync` исполняет `__init__.py` → `sync` (рядом converter, который ТЗ запрещает *использовать*; риск случайного импорта выше). |
| Безопасность | средне | `update_page(..., space_key=None)` корректно не кладёт `space`. Но `config.get_settings()` приоритетно читает `MoveFromConfluence/.env` — лишний секретный контур. `_req` ретраит `RequestException`, **не** HTTP 409 (`raise_for_status`) — 409 всё равно писать самим. Timeout клиента 20s vs 60s у `section_patch`. |
| Консистентность | хуже | Два HTTP-стека в одном скилле (urllib у B0/B1, requests у Вестника). `get_page` default expand **без** `history` — надо явно передать `expand=body.storage,version,space,history`. |
| Поддерживаемость | хуже | `venv_linux` (AC+EWS) **без tenacity**; `ConfluenceSync/.venv` **без exchangelib/loguru**. Либо `pip install tenacity` в чужой venv, либо два интерпретатора. Оба хуже варианта 1. |

### Вариант 3 — компакт: 3 скрипта, тот же стек что у 1

Файлы: `vestnik_theme.py` (CLI+intent+HTTP+author+EWS+errors), `vestnik_theme_patch.py`, `vestnik_theme_block.py`. Тесты те же по смыслу.

| Критерий | Оценка | Факт |
|---|---|---|
| Токены | хуже | Любая правка «Блока» грузит в контекст CLI/PUT/verify. |
| Безопасность | средне | Те же инварианты, но легче случайно вызвать `write_contacts` / `update_page(..., space_key=)`. |
| Консистентность | средне | Стек как у 1, граница модулей размыта. |
| Поддерживаемость | хуже | ТЗ шаги 1–14 не мапятся на файлы; регрессии B0/B1 ловятся позже. |

---

## 3. Выбранный вариант + обоснование

**Выбран вариант 1.**

1. Reuse-first без новых сущностей: дом = `tutu-confluence-jira/scripts/`; клиентские куски — уже существующие USERTOOLS (url_utils, ContactStore, MeetingScheduler.exchange_client, ErrorBus).
2. ТЗ явно разрешает PUT из `section_patch.py`; `section_patch.get_page` **нельзя** взять как есть (нет `history`/`space`) и **нельзя** расширять. Локальный GET на том же `_api_request` — единственный способ не ломать контракт и не плодить второй HTTP-клиент.
3. Единственный venv, где одновременно есть `exchangelib` + `loguru` (AC) — `AnywhereContacts/venv_linux`. Urllib не требует tenacity → `--apply` с GAL работает одним интерпретатором.
4. Импорт `userkey_resolve.ConfluenceUserClient` / `resolve_user` закрывает запрет «прямой PUT ri:userkey». `write_contacts` не вызывать.
5. String-splice `<tr>` (как `replace_section_inner`) сохраняет байт-в-байт остальной storage: PDF `view-file`, другие вкладки, jira/info/expand.

Не выбирать 2, пока Саша явно не скажет ставить `tenacity` в `venv_linux` и принять пакетный импорт `confluencesync`. Не выбирать 3: экономия файлов не окупает стоимость правок.

Живой EWS в юнит-тестах **нет** (как OrgLookup: `resolve_names_fn` инжектится). Маркер `@pytest.mark.live` — только опциональная проверка GET title страницы `324382467`, не в default CI.

---

## 4. Пофайловый план

Канонические пути: `/home/tkachenkoav/hermes-workspace/skills/productivity/tutu-confluence-jira/…`

Константы (в коде, не в реестрах):

```
VESTNIK_PAGE_ID = "324382467"
VESTNIK_TITLE = "Вестник Аналитики и Данных"
DEFAULT_BASE = "https://dom.tutu.ru"          # уже в section_patch
MATERIAL_EXPAND = "body.storage,version,space,history"
AID_HEADS = frozenset({
  "peretyatkova", "zhirov", "kotelnikova", "rasov",
  "nabieva", "alekseeva.ym", "sereda", "tkachenkoav",
})
AID_DIRECTOR = "aralov"
KNOWN_BLOCK_LABELS = {"DS", "BI", "MLE", "DA", "DE", "DS/MLE"}  # канон коротких ярлыков
HEAD_BLOCK_LABELS: dict[str, str] = {}  # login главы → ярлык; пусто на старте, если department/team уже ярлык — писать его
```

Страницу `383117988` / дерево `310322545` **не** GET-ать (ТЗ). `sereda` оставляем в `AID_HEADS` как в ТЗ v0.2.0 (даже если в другом скилле помечен уволившимся).

### 4.1. Файлы: создать

| Файл | Назначение |
|---|---|
| `scripts/vestnik_theme.py` | CLI `add`, оркестратор `run_add()`, точка `main()` |
| `scripts/vestnik_theme_intent.py` | ParseIntent |
| `scripts/vestnik_theme_confluence.py` | токен, GET с нужным expand, resolve URL→pageId, PUT+409 |
| `scripts/vestnik_theme_author.py` | FetchMaterial.createdBy + confirm userkey |
| `scripts/vestnik_theme_block.py` | ResolveAIDUnit (AC → GAL in-memory → walk) |
| `scripts/vestnik_theme_ews.py` | latin-only ResolveNames |
| `scripts/vestnik_theme_patch.py` | SelectFreshTab, Dedup, ComposeRow, RowPatch |
| `scripts/vestnik_theme_verify.py` | Verify после PUT (не heading-skeleton) |
| `scripts/vestnik_theme_errors.py` | ErrorBus Mode A + коды HITL |
| `tests/test_vestnik_theme_intent.py` | |
| `tests/test_vestnik_theme_confluence.py` | |
| `tests/test_vestnik_theme_author.py` | |
| `tests/test_vestnik_theme_block.py` | |
| `tests/test_vestnik_theme_ews.py` | |
| `tests/test_vestnik_theme_patch.py` | |
| `tests/test_vestnik_theme_verify.py` | |
| `tests/test_vestnik_theme_cli.py` | |
| `tests/fixtures/storage_vestnik_ok.xml` | 2 вкладки, 6 `<th>`, живая строка + пустые `<tr>`, эталон empty-tr из ТЗ |
| `tests/fixtures/storage_vestnik_no_empty.xml` | нет пустой строки |
| `tests/fixtures/storage_vestnik_wrong_cols.xml` | ≠ 6 `<th>` |
| `tests/fixtures/storage_vestnik_theme_conflict.xml` | та же тема, другие pageId/title |

### 4.2. Файлы: изменить

| Файл | Что менять | Чего не делать |
|---|---|---|
| `SKILL.md` | Новая секция «Вестник (VestnikTheme)» в конце, перед «Связанные скиллы» / «Ссылки»: триггеры фраз, CLI `--dry-run`/`--apply`, запрет LLM→storage, venv_linux для GAL, ErrorBus `--tool VestnikTheme --source-kind skill`. Bump `version:` frontmatter скилла (сейчас 1.7.0 → 1.8.0). | Не описывать крон. Не менять разделы section-patch / userkey / JIRA. |
| `tests/conftest.py` | Фикстуры `storage_vestnik_ok` и путь к новым XML. `sys.path` к `scripts/` уже есть. | Не ломать существующие `storage_ok` / `storage_heading_gone`. |

### 4.3. Файлы: не трогать (жёстко)

- `scripts/section_patch.py`, `scripts/userkey_resolve.py`, `scripts/verify_skeleton.py` — **ноль** правок (другие пайплайны).
- `~/USERTOOLS/ConfluenceSync/**` (converter, client, config).
- `~/USERTOOLS/AnywhereContacts/**` (schema, store write-API).
- `~/USERTOOLS/OrgLookup/**` (cli, `needs_gal.jsonl`, `hierarchy.CacheStore`, `md_writer`).
- `~/USERTOOLS/MeetingScheduler/exchange_client.py` — только импорт `get_account` / `check_vpn`.
- `entities.json`, `jobs.json`, Gateway, `MAIN_TZ_INVENTORY.md`, `contacts.enc`.
- `vestnik-aid-points` (другой скилл, страница баллов `496620177`).

### 4.4. Функции / классы / методы

#### `vestnik_theme_errors.py`

- `class VestnikError(Exception)` — `stage: str`, `message: str`, `exit_code: int = 1`.
- `class HitlStop(Exception)` — `kind: "contact_missing" | "theme_conflict"`, `message: str`, stdout Саше, **не** ErrorBus, `exit_code = 2`.
- `report_technical(stage: str, message: str, *, detail: str | None = None) -> None` — `subprocess` `~/.hermes/scripts/report_error.sh --tool VestnikTheme --source-kind skill --stage <stage> --message <…>` (`--detail` по желанию). Fail-soft скрипта ErrorBus не глотать как успех Вестника: после вызова всё равно `raise` / `return 1`.
- HITL **не** вызывать `report_error.sh`.

#### `vestnik_theme_intent.py`

- `MONTH_NAMES` — русские именительный + родительный («сентябрь», «сентября», …), без взятия месяца из `name` вкладки.
- `@dataclass Intent`: `page_ids: list[str]` (порядок, первый = тема), `raw_refs: list[str]`, `month: str | None`, `apply: bool`.
- `parse_intent(*, page_ids: list[str], command_text: str | None, apply: bool) -> Intent` — токены через `parse_confluence_url`; числовой id / `pageId=` / `/pages/{id}` сразу в список; `/display/SPACE/Title` оставлять как raw_ref на резолв сети в confluence-модуле. Дубликаты pageId схлопывать с сохранением первого вхождения. Пустой список → `VestnikError(stage="parse")`.
- Импорт `parse_confluence_url`: `sys.path` на `~/USERTOOLS/ConfluenceSync/confluencesync` **или** `importlib.util.spec_from_file_location` на `url_utils.py`. **Запрещено** `from confluencesync import …` / `from confluencesync.url_utils` через пакетный корень `ConfluenceSync/` (сработает `__init__.py`).

#### `vestnik_theme_confluence.py`

- `load_token()` → `section_patch.load_confluence_token`.
- `get_page(page_id, *, expand=MATERIAL_EXPAND, token=None) -> dict` — URL `{base}/rest/api/content/{id}?expand=…` через `section_patch._api_request("GET", …)`. Не вызывать `section_patch.get_page` (чужой expand).
- `resolve_ref(url_or_id, *, token=None) -> str` — если у `ConfluenceRef` есть `page_id` — вернуть; если `space_key+title` — `GET /rest/api/content?spaceKey=&title=&limit=1` через `_api_request`. 0 результатов → `VestnikError(stage="parse")`.
- `fetch_material(page_id, *, token=None) -> Material` — см. author-модуль, либо тонкая обёртка GET.
- `put_storage(page_id, *, title, current_version, storage, token=None) -> dict` — `payload = build_put_payload(title, current_version + 1, storage)`; assert `"space" not in payload`; `section_patch.put_page`. Пойманный `RuntimeError` с префиксом `"HTTP 409"` → наружу как `ConflictError`, не ретраить внутри этой функции (ретрай в оркестраторе).
- **Не** вызывать `ConfluenceClient.update_page` (внутренний `version+1` + tenacity).

#### `vestnik_theme_author.py`

- `@dataclass Material`: `page_id, title, space_key, created_by_username, created_by_userkey, created_by_display`.
- `material_from_page(page: dict, page_id: str) -> Material` — `title`, `space.key`, `history.createdBy.{username,userKey,displayName}`. **Не** `version.by`. Нет `createdBy` / пустой userKey → `VestnikError(stage="fetch")`.
- `confirm_userkey(userkey: str, *, client: UserClient, cache: dict) -> dict` — `userkey_resolve.resolve_user`. Пустой ответ / exception → `VestnikError(stage="userkey")` + ErrorBus. В ячейку Автора идёт **тот же** `userkey`, что подтвердил API (поле `userkey` из result).
- `write_contacts` **не** импортировать в оркестратор.

#### `vestnik_theme_ews.py`

- `is_latin_query(s: str) -> bool` — нет `[а-яёА-ЯЁ]`. Кириллица → не звать EWS (ТЗ: «кириллический GAL-поиск не использовать»). Транслит ФИО из OrgLookup `resolver.transliterate` **не** подключать.
- `@dataclass GalPerson`: `login, email, department, team, job_title, manager_display, reports_to_login` (`reports_to_login` может быть пуст на этом шаге).
- `resolve_names(query: str, *, account=None, protocol_resolve=None) -> list[GalPerson]` — сеть только если `protocol_resolve` не передан: `exchange_client.get_account()` затем `account.protocol.resolve_names(names=[query], return_full_contact_data=True, search_scope="ActiveDirectory")`. Разбор mailbox/contact — как в `OrgLookup/orglookup/ews_client.py:resolve_names` (логика, не импорт пакета `orglookup`). `login` = local-part email. Пустой список = not_found, не исключение. VPN: `check_vpn()` → нет VPN → `VestnikError(stage="block")` (технический, ErrorBus), очередь `needs_gal` не трогать.
- Импорт `get_account`/`check_vpn`: `sys.path` на `~/USERTOOLS/MeetingScheduler` + `import exchange_client` (модуль файла). **Запрещено** `from MeetingScheduler import …` / `from MeetingScheduler.exchange_client` — пакетный `__init__.py` импортирует `meeting_scheduler` → `exchangelib` CalendarItem и валит системный python3.
- Не импортировать `orglookup.cli`, `hierarchy`, `CacheStore`, `needs_gal.jsonl`.

#### `vestnik_theme_block.py`

- `Protocol ContactLookup`: `get_contact(login)`, `find_contacts(query)` — в проде `ContactStore`, в тестах dict-фейк.
- `_load_store()` — копия паттерна `userkey_resolve._load_store`: `sys.path` `~/USERTOOLS/AnywhereContacts`, `create_store(contacts.enc, CONTACTS_ENCRYPTION_KEY)` после `usertools_env.load_usertools_env()`. Ключ отсутствует → `VestnikError(stage="block")`. `update_contact` / `add_alias` **не вызывать**.
- `contact_to_node(contact: dict) -> OrgNode` (`login, department, team, reports_to`).
- `gal_to_node(person: GalPerson) -> OrgNode` — in-memory; `reports_to` из GAL только если уже login, иначе пусто (второй ResolveNames менеджера по display-name **не** делать в v0.1.0: это hierarchy OrgLookup + риск кириллицы). Нет `reports_to` → дальше walk не идёт → предупреждение, «Блок» пустой, строка **не** блокируется (ТЗ п.4.6 / п.6).
- `lookup_author(username: str, *, store: ContactLookup, userkey: str | None) -> OrgNode | None` — порядок: `get_contact(username.lower())`; `find_contacts(username)`; если ровно один хит — его. Не угадывать при >1.
- `lookup_or_gal(username: str, *, store, ews_resolve, email_hint: str | None) -> tuple[OrgNode, source]` где `source in {"ac","gal"}`. Нет в AC → EWS по `username` (латиница) и/или `{username}@tutu.ru` / `email_hint`. Нет в GAL → `HitlStop(kind="contact_missing")`. GAL hit → node in-memory, **не** писать store.
- `walk_aid_unit(node: OrgNode, *, store, gal_nodes: dict[str, OrgNode]) -> tuple[str, str]` → `(block_text, warning)`. Если `node.login in AID_HEADS` — блок из этого узла. Иначе вверх по `reports_to` (защита цикла, лимит ~20). Стоп на `AID_HEADS`. Стоп на `AID_DIRECTOR`: блок = `department`/`team` **предыдущего** узла. Нет цепи → `("", "контакт/блок не найден")`.
- `format_block(department: str, team: str, head_login: str | None) -> str` — `HEAD_BLOCK_LABELS.get(head_login)` если задан; иначе `department or team`; еслиstripped значение (casefold) совпало с `KNOWN_BLOCK_LABELS` — канонический ярлык; иначе текст как в контакте.
- Превью источника блока: `"AC"` / `"GAL"` / `"пусто"`. Для stdout превью контакта — `render_contact(contact, level="summary")` если объект из AC; raw email в превью не печатать.

#### `vestnik_theme_patch.py`

Парсер **только для поиска offset'ов в исходной строке**. Сериализация всего документа через lxml/BS4 **запрещена** (перепишет namespace/порядок, заденет другие вкладки).

- `count_nav_items(storage) -> int` — число `ac:name="horizontal-nav-item"`.
- `first_nav_item_span(storage) -> tuple[int,int,str]` — span первого item + параметр `name` (эталон «Август-Сентябрь 2026» на фикстуре; на живой странице имя может смениться — тест live не хардкодит вечность). Нет макроса / нет единственного `horizontal-nav-group` → `VestnikError(stage="tab")`.
- `itogovy_table_span(nav_inner: str) -> …` — после `<p>…Итоговый материал…</p>` первая `<table>…</table>` **внутри этого nav-item**. Считать `<th>`: ≠ 6 → `VestnikError(stage="tab")`.
- `iter_data_rows(table_html)` — `<tr>` после заголовка.
- `is_empty_row(tr_html) -> bool` — ровно 6 `<td>`, текст после strip tags пуст или только `<br/>` / `&nbsp;` / пробел в `<span>`.
- `first_empty_tr_span(table_html) -> tuple[int,int]` — нет пустой → `VestnikError(stage="patch")` (не append).
- `extract_ri_pages(table_html) -> list[tuple[space, title]]` и `extract_page_ids(table_html) -> set[str]` (из `pageId=` / `/pages/{id}`).
- `theme_texts(table_html) -> list[str]` — текст 3-й колонки (Тема), strip tags.
- `dedup(table_html, materials: list[Material], theme_title: str) -> Literal["noop","ok"] | no return, HitlStop`:
  - все входные `page_id` уже есть в `extract_page_ids` **или** все пары `(space_key, title)` уже есть в `ri:page` → `"noop"`;
  - текст темы совпал (нормализация пробелов/регистр — casefold), но набор pageId/пар другой → `HitlStop(kind="theme_conflict")`;
  - иначе `"ok"`.
- `escape_attr(s) -> str` — XML attr (`&quot;` `&amp;` `<`).
- `ri_page_link(space_key, title) -> str` — `<ac:link><ri:page ri:space-key="…" ri:content-title="…"/></ac:link>`. space-key **только** из GET материала.
- `compose_row_inner(*, month, block, materials, author_userkey) -> str` — **6 `<td>`**, обёртки как эталон ТЗ:

```
td1 month или <br />
td2 block или <span> </span>
td3 <p class="with-breadcrumbs" style="text-align: left;"> ri_page(materials[0]) </p>
td4 все ri_page через пробел/br; один pageId = дубль темы
td5 <br />
td6 <div class="content-wrapper"><ac:link><ri:user ri:userkey="…"/></ac:link></div>
```

  Колонка технологий всегда `<br />`. Месяц — только если `Intent.month` задан явно.
- `patch_first_empty_tr(storage, new_tr_inner) -> str` — заменить внутренность первой пустой `<tr>` целевой таблицы; остальной storage — срезы исходной строки. Diff обязан затрагивать только этот `<tr>`.

#### `vestnik_theme_verify.py`

Не вызывать `verify_skeleton.verify_skeleton` с heading (на Вестнике нет h1–h6 якоря). Паттерны брифа можно **скопировать константой** (не импортировать `find_section_span`).

- `@dataclass VestnikVerify`: `ok, checks: dict[str,bool], messages`.
- `verify_vestnik(*, before_storage, after_storage, before_version, after_version, expected_min_version, materials, author_userkey, first_tab_name) -> VestnikVerify`:
  1. `after_version >= expected_min_version` (или честно `>= before+1` после 409-ретрая);
  2. `count_nav_items(after) == count_nav_items(before)`;
  3. `name` первого item тот же;
  4. в целевой таблице 6 `<th>`; в новой/noop строке 6 `<td>`;
  5. title первой страницы и все `ri:space-key` материалов присутствуют в таблице; userkey автора есть;
  6. нет «Не копировать», «см. бриф», «Уточнить до ПК» (как в `BRIEF_LEAK_PATTERNS`);
  7. в патче нет `DATASC`, если GET материала сказал другой space (регрессия соседней ячейки).
- Провал любого пункта → не успех, ErrorBus `stage="verify"`.

#### `vestnik_theme.py`

```
add [--page-id ID ...] [--month NAME] [--command-text TEXT]
    [--dry-run | --apply] [--vestnik-page-id ID]
```

- Без `--apply` ⇒ dry-run (GET разрешён, PUT нет). `--dry-run` и `--apply` вместе → ошибка CLI.
- `run_add(argv) -> int`:
  1. parse_intent;
  2. resolve_ref каждого raw_ref (сеть);
  3. fetch + material_from_page каждого pageId; confirm_userkey по **первому** createdBy (автор строки = создатель **первой** страницы, ТЗ «Автора — createdBy»);
  4. lookup_or_gal + walk_aid_unit;
  5. GET Вестника (`VESTNIK_PAGE_ID`, тот же expand);
  6. schema guard + dedup;
  7. если noop: превью «идемпотентный no-op», exit 0, PUT нет даже при `--apply`;
  8. compose + (dry-run: печать 6 полей, title вкладки, pageId/space материалов, login автора, источник блока, version; PUT нет);
  9. `--apply`: patch → PUT; HTTP 409 → GET заново → шаги 5–9, **≤ 2 ретраев**; исчерпание → ErrorBus `stage="put"`, exit 1;
  10. GET verify; провал → ErrorBus, exit 1 (страницу «откатывать» скриптом не пытаться — Саша/архитектор, см. §4.7).
- stdout превью: стабильный текст/JSON (ключ `dry_run_preview`), без сырых email.
- `if __name__` → `SystemExit(main())`.

### 4.5. Тесты (все fixture-based, без VPN по умолчанию)

Существующие `tests/test_section_patch.py`, `test_userkey_resolve.py`, `test_verify_skeleton.py` — **13 passed** должно сохраниться без правок продакшен-скриптов.

| Файл теста | Кейсы (критерий) |
|---|---|
| `test_vestnik_theme_intent.py` | три id → длина 3, первый = тема; viewpage URL; `/display/SPACE/Title` остаётся raw_ref; месяц «в сентябре» заполняет `month`; имя вкладки в command_text **без** слова-месяца как колонки не считается; пустой ввод → ошибка |
| `test_vestnik_theme_confluence.py` | `build_put_payload` без `space` (регресс через наш wrapper); resolve числового id без HTTP; HTTP 409 из `RuntimeError("HTTP 409:…")` распознан; fake `_api_request` для display→pageId |
| `test_vestnik_theme_author.py` | страница как `517103930`: username `shubchik`, space не DATASC; `version.by` игнорируется; пустой userkey → VestnikError; Fake UserClient: ячейка автора = confirmed key |
| `test_vestnik_theme_block.py` | (1) hit AC + walk до главы → ярлык/department; (2) miss AC + hit GAL in-memory → source GAL, store.update не вызывался; (3) miss оба → HitlStop, PUT-флаг не ставится; (4) hit без reports_to → warning, block `""`, не HitlStop; (5) автор сам в AID_HEADS; (6) стоп на `aralov` → отдел предыдущего; (7) цикл reports_to не бесконечный |
| `test_vestnik_theme_ews.py` | кириллица → 0 вызовов protocol; латиница `shubchik` → 1 вызов; NoResults → `[]` |
| `test_vestnik_theme_patch.py` | фикстура ok: первый name задан, 6 th; empty tr = эталон ТЗ; compose 6 td, space-key из GET не из соседа; один pageId: Материалы дублируют Тема; три pageId: 3 ri:page в материалах; dedup все id → noop; тема совпала / id другие → HitlStop; нет пустой tr → VestnikError; patch: `before.replace(old_tr, new_tr)` только в одном месте, `count(horizontal-nav-item)` тот же, второй item байт-в-байт; brief-строк нет |
| `test_vestnik_theme_verify.py` | ok-путь; сломанный th-count; leak «Не копировать»; nav count изменился → fail |
| `test_vestnik_theme_cli.py` | `--help` exit 0; без `--apply` оркестратор с fake GET не вызывает put; `--apply` на noop не вызывает put; HitlStop → rc=2 и **нет** вызова `report_error.sh` (monkeypatch); VestnikError 404 материала → rc=1 и вызов ErrorBus с `--tool VestnikTheme --source-kind skill --stage fetch` |

`@pytest.mark.live` (не в default): GET `324382467` title == «Вестник Аналитики и Данных». Исполнитель не обязан гонять live в Блоке 3, если VPN нет.

Запуск юнитов (как сейчас):

```bash
cd ~/hermes-workspace/skills/productivity/tutu-confluence-jira
python3 -m pytest tests/ -q
```

Live GAL/AC (только когда Саша разрешит сеть):

```bash
~/USERTOOLS/AnywhereContacts/venv_linux/bin/python \
  ~/hermes-workspace/skills/productivity/tutu-confluence-jira/scripts/vestnik_theme.py \
  add --page-id 517103930 --dry-run
```

### 4.6. Порядок операций и точки проверки

Исполнитель проходит точки **молча**. Критерий точки = команда + ожидаемый результат.

**Волна 0 — каркас + инвариант «старые тесты живы»**

- Создать пустые модули с `__all__` / `main` stub, фикстуры XML (минимальный nav-group).
- Точка **П0**: `python3 -m pytest tests/test_section_patch.py tests/test_userkey_resolve.py tests/test_verify_skeleton.py -q` → 13 passed. `git diff`/`stat` на трёх старых `.py` — mtime/содержимое не менялись.

**Волна 1 — CLI + ParseIntent + токен (ТЗ шаги 1–3)**

- Реализовать `vestnik_theme.py` argparse, `intent`, `errors` (пока без сети).
- Точка **П1**: `python3 scripts/vestnik_theme.py add --help` → 0; pytest `test_vestnik_theme_intent.py` + `test_vestnik_theme_cli.py::test_help` green.
- Точка **П1b** (опционально live): dry-run с несуществующим pageId через fake/или live 404 → rc≠0, put-функция не вызывалась.

**Волна 2 — Confluence GET/PUT wrapper + userkey (ТЗ шаги 2, 4–5)**

- `vestnik_theme_confluence.py`, `vestnik_theme_author.py`.
- Точка **П2**: pytest confluence+author. Payload fixture: `"space" not in payload`. Fake page `history.createdBy.username == "shubchik"`, space ≠ DATASC.

**Волна 3 — Блок AC/GAL (ТЗ шаг 6)**

- `vestnik_theme_ews.py`, `vestnik_theme_block.py`.
- Точка **П3**: pytest block+ews — все 4 фикстуры ТЗ (hit AC / miss+GAL / miss оба / hit без reports_to) + кириллица не ходит в EWS. В GAL-ветке `store.update_contact` call_count == 0.

**Волна 4 — вкладка, строка, дедуп, verify (ТЗ шаги 7–10, 12)**

- `vestnik_theme_patch.py`, `vestnik_theme_verify.py`, XML-фикстуры довести до 6 колонок и эталонного empty `<tr>`.
- Точка **П4**: pytest patch+verify. На `storage_vestnik_ok.xml` первый item name задан в фикстуре; diff только target `<tr>`; повторный compose тех же pageId → noop; conflict-фикстура → HitlStop.

**Волна 5 — оркестратор + ErrorBus + SKILL.md (ТЗ шаги 9, 11, 13–14)**

- Собрать `run_add`: dry-run путь, `--apply` с fake put, 409 retry (fake: первый PUT 409, второй 200, третий не нужен; четвёртый вызов не происходит). ErrorBus monkeypatch.
- Точка **П5**: полный `python3 -m pytest tests/ -q` (без `-m live`) — все новые + 13 старых green. HITL rc=2 без ErrorBus. 404 материала → ErrorBus `--tool VestnikTheme --source-kind skill`.
- Точка **П5b**: секция VestnikTheme есть в `SKILL.md`; в секции есть запрет LLM-storage и `--dry-run` по умолчанию; крон не упомянут.

**Волна 6 — ручная сверка плана vs ТЗ (исполнитель, без PUT на 324382467 пока Саша не дал `--apply` на бой)**

- Чеклист инвариантов: нет `space` в PUT; нет `html_to_md`; нет `write_contacts`; нет вызова `orglookup` CLI; месяц только из `--month`/`command_text`; технологии пустые.

Боевой `--apply` на `324382467` **не** входит в Блок 2/3 по умолчанию (нужен отдельный императив Саши). Юниты с фикстурой достаточны для «точки плана пройдены».

### 4.7. Процедура отката

Предусловие Блока 2: бэкап `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (Блок 5 hermes-feature) **до** правок SKILL.md.

Код скилла не в git-репозитории USERTOOLS — откат файловый:

1. Удалить все `scripts/vestnik_theme*.py`, `tests/test_vestnik_theme_*.py`, `tests/fixtures/storage_vestnik_*.xml`.
2. Вернуть `tests/conftest.py` и `SKILL.md` из бэкапа архива (или вырезать секцию VestnikTheme, version скилла обратно).
3. Прогнать `python3 -m pytest tests/ -q` → снова 13 passed.
4. `restore-all-skills.sh` — только если SKILL.md уже уехал в профили; делает **координатор** (ORCH:shared-state), не исполнитель в HF:impl.

Confluence: юниты PUT не делают. Если боевой `--apply` уже прошёл и строка лишняя — **не** откатывать PUT скриптом в этой задаче (ТЗ: не удалять чужое на странице, которую человек правит). Сообщить Саше version + «вычистить строку вручную / отдельная команда».

---

## 5. Новые сущности

Новых сущностей в этом плане **нет**.

Не создавать (уже закрыто ТЗ / Q1 / Q9а): `~/USERTOOLS/VestnikTheme/`, скилл `productivity/vestnik-theme`, крон, запись в `entities.json` / `jobs.json`, импорт GAL → `contacts.enc` (Q9б).

Новые файлы внутри существующего скилла `tutu-confluence-jira` и его `tests/` — **не** новые сущности.

---

## 6. Чек-лист перед первой строкой кода (Блок 2 hermes-feature)

1. ТЗ `VestnikTheme_TZ.md` v0.2.0 согласовано; открытых вопросов нет (Q1–Q10 закрыты; Q9б вне скоупа).
2. Саша сказал **«берём в работу»** по **варианту 1** и по этому пофайловому плану (GATE:plan-approve). Согласование ТЗ ≠ эта команда.
3. Бэкап создан: `~/.hermes/_Archives/hermes-backup-YYYYMMDD-HHMMSS/` (затронем SKILL.md).
4. Новых сущностей на отдельное ОК нет (раздел 5 пуст).
5. Канбан: `GATE:plan-approve` = done/unblocked **или** auto-pass one-pass.
6. Исполнитель = composer-2.5; не менять `section_patch.py` / `userkey_resolve.py` / `verify_skeleton.py`.
7. Runtime live: `AnywhereContacts/venv_linux`; юниты: системный `python3`. Не ставить пакеты в venv без отдельного императива.
8. Боевой PUT `324382467` не делать в HF:impl, пока Саша явно не даст `--apply` на бой.
9. После SKILL.md: `restore-all-skills.sh` — зона ORCH:shared-state, не HF:impl.
10. Факты плана, проверенные 2026-09-07 (не перепроверять «на всякий случай» сетью в имплементации):
    - realpath скилла → `hermes-workspace/skills/productivity/tutu-confluence-jira`;
    - `section_patch.get_page` expand = `body.storage,version` (нет history);
    - `ConfluenceClient.update_page` сам делает `version+1`, `space_key` optional;
    - `venv_linux`: есть exchangelib+loguru+requests, **нет** tenacity;
    - `ConfluenceSync/.venv`: есть tenacity, **нет** exchangelib;
    - пакетный `import MeetingScheduler` падает на системном python3;
    - `report_error.sh` требует `--tool` и `--message`, `--source-kind` по умолчанию `cron_script` → всегда передавать `skill`;
    - текущие тесты скилла: 13 passed.

---

## Прогресс выполнения

Чекбоксы для исполнителя (Блок 2/3). Архитектор их не отмечает.

- [x] П0: 13 старых тестов green, три старых скрипта не изменены
- [x] Волна 1 / П1: CLI `--help` + ParseIntent
- [x] Волна 2 / П2: GET expand + userkey confirm, PUT payload без `space`
- [x] Волна 3 / П3: AC / GAL / HITL / warning-empty-block
- [x] Волна 4 / П4: tab + empty tr + dedup + compose + verify
- [x] Волна 5 / П5: оркестратор, 409, ErrorBus vs HITL, SKILL.md
- [x] Волна 6: инварианты ТЗ, полный pytest без live
- [x] Откат проверен ментально (список файлов на удаление актуален)

Статус «готово» на весь план ставит только Саша (пошаговый ход) либо auto-complete в режиме «делай в 1 проход».
