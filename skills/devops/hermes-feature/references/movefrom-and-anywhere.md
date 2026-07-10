# MoveFrom* / FF API / AnywhereContacts — питфоллы

Родственный скилл: `movefrom-instruments` (полные детали инструментов).

## FF API `outline` всегда null (research pitfall)

`extended_sections` содержит 4 секции: Blockers/Questions/Meeting Outline/Topics. `apps_preview.outputs` содержит ВСЕ AI Skills (встроенные `1:1`/`Meeting Summary Generator` + любые пользовательские Custom Skills, отличаются по `title`) — детали, GraphQL-запрос и ограничения (нет ретроактивного запуска через API) см. скилл `movefrom-instruments`.

## Реальный API может не совпасть с ТЗ

Фиксировать отклонение в финальном отчёте Opus. Делать живой запрос к API **перед реализацией** (блокер для ТЗ, не после). Пример: FF `extended_sections { title items text }` → реально `{ title content }`.

Opus должен:
1. Записать отклонение в отчёт.
2. Реализовать по реальной схеме.
3. Оставить опциональные поля из ТЗ для backward-compat с моками, если это разумно.

ТЗ **не переписывать** после отклонения — только финальный отчёт.

## Backfill-паттерн для MoveFrom*

Если нужно перекачать встречи/данные вне текущего временного окна — добавить второй проход по `pending`-записям с известным ID через прямой fetch по ID (минуя date-фильтр).

Лимит 50 записей/прогон, сортировка newest-first (`reverse=True`), чтобы свежее появлялось первым. Для разового массового backfill: временно поднять константу `BACKFILL_MAX_PER_RUN` до нужного числа, запустить вручную `--mode test`, вернуть обратно. Проверить остаток API-лимита перед запуском (`x-ratelimit-remaining-api` в ответе заголовков).

## Режимы запуска

- **`--mode manual`** требует `--from-date` и `--to-date`.
- **`--mode test`** — берёт окно последних 5 дней + запускает backfill по pending. Использовать для backfill без дат.
- **`--mode cron`** — только новые встречи в окне `last_synced_at → сейчас`.

## Дедупликация встреч

При наличии двух записей с одинаковым названием и разницей во времени ≤10 минут — дубль. Сравнивать по длине транскрипта (символы/строки), более короткий → статус `duplicate`, файлы удалять. Статус `duplicate` пропускается в синке как `completed`. Если транскрипт недоступен — сравнивать по `duration_minutes`. Email = первичный ключ контакта, ФИО не схлопывать.

## Bulk API rate-limit

Перед массовым запросом проверить заголовки `x-ratelimit-remaining-api` и `x-ratelimit-reset-api`. Оставлять запас ≥10 запросов. После исчерпания лимит сбрасывается автоматически (время в секундах в `x-ratelimit-reset-api`).

## Reconciliation как паттерн доработки инструментов

Если пользователь хочет, чтобы ручное удаление файлов запускало перекачку → добавить шаг reconciliation в начало синка: пройти по completed-записям реестра, проверить наличие файлов на диске, отсутствует ≥1 файл → сбросить статус в pending. Универсальный паттерн для всех MoveFrom*-инструментов с файловым реестром.

## Форсированный пересбор summary/transcript (MoveFromFF и аналоги с `reconcile_registry`)

Чтобы проверить, что изменение логики рендера (например, новая ветка custom-skill vs fallback) реально применяется к уже скачанным встречам — **не трогать `_registry_meet.json` руками**. Переименовать нужные существующие файлы (`... - summary.md` → `... - summary.md_old`, суффикс в конец имени, не удалять — нужен diff старое/новое).

При следующем запуске `reconcile_registry()` сам увидит отсутствие ожидаемого файла из `rec.files` и сбросит запись `completed → pending` (attempts/next_retry_at обнуляются) — это штатный механизм, специально его дёргать не нужно. Затем запустить `--mode manual --from-date YYYY-MM-DD --to-date YYYY-MM-DD` с окном, покрывающим нужный период — `manual`-режим гарантированно включает `fetch_range` по явному интервалу и подтянет все сброшенные в pending записи через основной цикл.

**Побочный эффект:** writer (`write_meeting_files`) пишет transcript+summary атомарно за один вызов — точечно перегенерировать только один файл нельзя, transcript тоже перезапишется (тем же содержимым, если исходные данные в FF не менялись).

## MoveFromZulip синк

Первичный ключ контакта = `login` (часть email до `@`), не полный email. Schema v2: `sources: {zulip: {email, synced_at, active}}`, `active = any(source.active)`. Zulip отдаёт всех одним запросом `GET /api/v1/users`. Фильтры: `is_bot=true` и `is_active=false` — не писать вообще. `messenger_ids` хранятся с `{value, source, synced_at}`, `source: manual` не перезаписывается коннектором.

## AnywhereContacts — PII при выводе

Функция `mask_contact(contact)` из `anywhere_contacts` **ОБЯЗАТЕЛЬНА** перед любым выводом контакта пользователю в Telegram или CLI. `store.read()` возвращает сырые данные намеренно (для записи в Jira/Confluence нужен настоящий email). Ошибка: показать `Криворотов Кирилл` вместо `Кр**в Ки**л`.

## AnywhereContacts — общий lock

Все коннекторы используют единый lock-файл `WorkVault/Contacts/.contacts.enc.lock`, не per-tool lock.

## AnywhereContacts API на VM

```python
ContactStore(path=Path('/home/tkachenkoav/WorkVault/Contacts/contacts.enc'),
             encryption_key=KEY)
```

- Python-интерпретер: `~/USERTOOLS/AnywhereContacts/.venv/bin/python3` (не системный).
- venv имеет структуру Windows (`Lib/`, `Scripts/`), активировать через `.venv/bin/python3` напрямую.
- `find_contacts(query)` возвращает `Dict[login, contact_dict]` — итерировать через `.items()`.
- Перед выводом: `mask_contact(c)` обязательно.

## USERTOOLS живут в `~/USERTOOLS/` на Linux VM

При запуске Opus — передавать этот путь.

## Триггер синка после USERTOOLS-инструментов

Паттерн: добавить в конец каждого инструмента, пишущего в WorkVault:

```python
subprocess.run(["systemctl", "--user", "start", "--no-block", "owncloud-sync.service"],
               check=False, timeout=5)
```

`--no-block` критичен — инструмент не ждёт завершения синка. `check=False` — не падать, если systemd недоступен.

## rclone `--size-only` (ownCloud синк)

Флаг `--size-only` пропускает изменения одного размера: правки строки в `.md` той же длины, ре-шифрование `contacts.enc`. **Убрать**; rclone по умолчанию сравнивает `size+mtime` — надёжнее. Зафиксировано 03.06.2026.

## `anywhere_contacts.store.ContactStore` не имеет `add_alias` (реальный API vs ожидания из ТЗ/плана)

Реальные методы: `get_contact`, `get_contact_by_email`, `find_contacts`, `update_contact`, `add_project_role`, `close_project_role`. Метода `add_alias` **нет** — многие ТЗ/планы (bk-098 ExchangeOrgLookup и др.) описывают его как готовый API по аналогии с `AggregateFromMeetings.utils.ac_client.ContactStore` (in-memory тестовая реализация, у неё `add_alias` есть, но это ДРУГОЙ класс, не настоящий AC-стор).

**Паттерн:** не переписывать ТЗ и не лезть в `contacts.enc` напрямую — обернуть официальный API тонким адаптером:
```python
class ContactStoreAdapter:
    def add_alias(self, login, alias, source="exchange_gal") -> bool:
        contact = self._store.get_contact(login)
        if contact is None:
            raise KeyError(login)
        aliases = list(contact.get("aliases") or [])
        if alias.lower() in {a.lower() for a in aliases}:
            return False
        aliases.append(alias)
        self._store.update_contact(login, {"aliases": aliases})
        return True
```
Зафиксировать расхождение в финальном отчёте (см. правило «реальный API vs ТЗ», Pitfall 15/16 в основном SKILL.md), не менять формулировку ТЗ.

## `pip install -e ~/USERTOOLS/AnywhereContacts` падает в чужом venv (flat-layout conflict)

`AnywhereContacts/` содержит `venv_linux/`/`venv/`/`.venv/` рядом с пакетом `anywhere_contacts/` и `pyproject.toml` в корне без `packages.find.include` — setuptools видит два top-level пакета (`venv_linux`, `anywhere_contacts`) и падает: `Multiple top-level packages discovered in a flat-layout`. Не чинить сам `pyproject.toml` без запроса (другой инструмент, другой жизненный цикл) — для нового инструмента, которому нужен только `anywhere_contacts.store.ContactStore` для чтения, добавить `sys.path.insert(0, str(USERTOOLS_ROOT))` и `import anywhere_contacts` напрямую из исходников, не через editable-install.

## Переиспользование `MeetingScheduler.exchange_client` для новых EWS-инструментов

Паттерн подтверждён на bk-098 (ExchangeOrgLookup): не реализовывать свою авторизацию Exchange — импортировать `MeetingScheduler.exchange_client.get_account()` / `check_vpn()` как есть (`sys.path.insert(0, str(Path(__file__).resolve().parents[2]))` до `USERTOOLS/`, затем `from MeetingScheduler.exchange_client import get_account, check_vpn`). Всегда сначала `check_vpn()` — при недоступности `cas.tutu.ru:443` кидать понятную ошибку, не пытаться авторизоваться вслепую.

**exchangelib-квирк:** `account.protocol.resolve_names(...)` при `ErrorNameResolutionNoResults`/похожих ошибках иногда НЕ поднимает исключение, а кладёт объект-исключение прямо в возвращаемый список результатов вместо кортежа `(Mailbox, Contact)`. Распаковка `for mailbox, contact in results` в этом случае падает `TypeError: cannot unpack non-iterable ErrorNameResolutionNoResults object`. Обязательно фильтровать: `if isinstance(item, Exception): continue` перед распаковкой каждого элемента.

**Двухшаговый резолв руководителя** (когда GAL отдаёт `manager` как display-name строку, а не email/mailbox): `email → ResolveNames(employee) → contact.manager (str) → ResolveNames(manager_str) → manager.email → login = local-part`. Кириллица не резолвится в EWS — транслитерировать (ГОСТ + словарь исключений) до запроса.

## MoveFromFF хранит дату/время в имени файла в UTC (намеренно, по ТЗ §6) — downstream-инструменты обязаны сами конвертировать в МСК

`movefromff/filename.py` (`build_filename`, `filename_date_part`) намеренно кладёт UTC-время в имя файла (`YYYY-MM-DD HH-MM-SS ... - summary.md`), это осознанное архитектурное решение MoveFromFF, **менять не нужно**. Любой downstream-инструмент, который парсит время прямо из этого имени файла (например `ProtocolFromSummary/summary_parser.py`, regex `(?P<time>\d{2}-\d{2}-\d{2})`), обязан явно прибавить +3 часа (Россия не переходит на летнее время, оффсет константный) **и** проверить переход через полночь — если после конвертации получилось `00:00-02:59`, `meeting_date` тоже сдвигается на +1 день. Надёжный способ: собрать `datetime(date, time, tzinfo=UTC) + timedelta(hours=3)`, взять `.date()`+`.strftime("%H:%M")` из результата — не городить ручные спецслучаи над голыми строками. Прецедент 10.07.2026 (ProtocolFromSummary): 3 встречи реально опубликованы в проде с UTC-временем вместо МСК (10:20 вместо 13:20 и т.д.) — баг обнаружен пользователем по факту, не при тестировании, потому что unit-тесты не проверяли смысл значения, только формат парсинга.

**Правило для смежных инструментов:** при подключении любого нового потребителя данных MoveFromFF (сегодня summary/transcript, в будущем — что угодно, использующее timestamp из имени файла) — явно сверить в ТЗ обеих сторон, в какой таймзоне хранится и в какой должна отображаться пользователю дата/время. Не предполагать, что timestamp «уже готов к показу».

## Резолв контакта по одинокой фамилии (без имени/отчества), совпадающей с несколькими записями `contacts.enc`

Summary-файлы иногда содержат задачу с исполнителем, записанным одной фамилией без имени-отчества (например «Ткаченко: сделать X» вместо «Ткаченко Александр Владимирович: сделать X») — обычно так составитель встречи ссылается на «дефолтного»/самого частого адресата, не на конкретного человека, если в компании несколько тёзок-однофамильцев. `contacts_resolver._resolve_one` в этом случае получает от `store.find_contacts(raw)` несколько кандидатов, `_narrow_candidates` не может сузить единственным словом «фамилия» (оно совпадает с обоими), и текущая логика (`len(candidates) != 1` → warning, `resolved=False`) оставляет упоминание как обычный текст — mention не резолвится, хотя человек в contacts.enc реально есть.

**Согласованное решение (10.07.2026, ProtocolFromSummary):** если среди неоднозначных кандидатов присутствует «свой» логин пользователя (например `tkachenkoav` — сам Саша, `DEFAULT_ASSIGNEE_LOGIN` в конфиге инструмента) — при неоднозначности резолвить в его пользу как дефолтного исполнителя, а не оставлять текстом. Обоснование: одинокая фамилия в задаче почти всегда означает «на меня», раз составитель поленился уточнить, и в контексте личных/командных summary большинство неразрешённых упоминаний фамилии без имени указывают на владельца инструмента. Реализовать как явную проверку в `_resolve_one` до финального `len(candidates) != 1` fallback: если `DEFAULT_ASSIGNEE_LOGIN in candidates` — вернуть его, иначе — прежнее поведение (оставить текстом).
