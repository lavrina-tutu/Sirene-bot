# PII-защита вывода и хранения контактов — ПЛАН РЕАЛИЗАЦИИ

Дата: 2026-08-27
Инструмент(ы): AnywhereContacts, OrgLookup, runtime-скилл show-contacts
Статус: согласован Сашей («выполнить всё необходимое, закрыть источники, поставить блок, маскировать что нельзя удалить, удалить что не несёт контекста»)

## Решения владельца (зафиксированы)
- **Вариант: гибрид (в).** Единая `render_contact(contact, level="summary"|"full")`. Все точки вывода контакта редактируют до входа в контекст модели. По умолчанию `summary`. Полный — по явному запросу + audit.
- **`tutu-contacts.md` — удалить**, в открытом виде в наших системах не хранить, на экран без маскирования не показывать. Списки — только через `contacts.enc` + штатное секьюрное извлечение (`render_contact`).
- **Поставить блок** на саму возможность генерации/появления таких plaintext-файлов.
- **Исторические натекшие данные:** маскировать всё, что нельзя удалить (контекст-сессии), удалить всё, что контекста не несёт (крон-логи, дампы).
- Внутренних потребителей полных данных (contacts_resolver, matcher в AggregateFromMeetings/PFS/MOFS) НЕ трогаем — им нужен полный email для матчинга (это внутренняя логика, не вывод).

## Пункты работы
1. **`~/USERTOOLS/AnywhereContacts/anywhere_contacts/logger.py`** — экспортировать (или собрать в отдельном модуле) единую `render_contact(contact, level)`: summary = имя/должность/департамент + маскированные email/handle; full = все поля, только по явному level="full". Использовать существующие `mask_contact()/PII_MASKERS`.
2. **`anywhere_contacts/store.py`** — добавить методы `get_contact_for_display(login, level="summary")` / `find_contacts_for_display(query, level="summary")`, которые читают как сейчас, но возвращают уже прогон по `render_contact`. Существующие raw-методы оставить (внутренние потребители).
3. **`anywhere_contacts/__init__.py`** — реэкспорт новых API показа.
4. **`~/USERTOOLS/OrgLookup/orglookup/cli.py`** (`cmd_who`, `cmd_manager`, `cmd_bootstrap`) — заменить прямой вывод `email/login/department/job_title` на `render_contact(...)`. Полный email — только с явным флагом `--reveal`.
5. **`~/WorkVault/Contacts/tutu-contacts.md`** — УДАЛИТЬ (не хранить в открытом виде).
6. **`~/USERTOOLS/OrgLookup/orglookup/md_writer.py`** — УБРАТЬ генерацию plaintext-таблиц контактов (написал блок: не создавать файл). Если списки нужны — только маскированные через `render_contact(summary)` из `contacts.enc`.
7. **Просканировать весь `~/USERTOOLS/*` и `~/.hermes/skills/*`** на другие места, генерирующие контакты в открытом виде (только чтение/отчёт) — заблокировать/маскировать аналогично.
8. **Рантайм-скилл** — создать/актуализировать скилл показа контактов с триггерами «найди контакт/email/телефон/тег/кто на связи», который предписывает Сирене вызывать `render_contact`/`*_for_display`, НЕ читать ContactStore напрямую.
9. **Исторические данные (~/.hermes/sessions, cron/output):**
   - заменить корпоративные email/и flare/Логины открытым текстом у окруженной шифро-цифрой маски (mask_pii) там, где файл нужен для контекста (session-архивы);
   - удалить крон-вывод/дампы, не несущие контекста.
   Не трогать целостность JSON — маскировать только значения, сохраняя структуру.
10. **Тесты** в `AnywhereContacts/tests` + краткий отчёт о найденных/заблокированных источниках.

## Верификация
- `grep -rl "@tutu.ru" ~/WorkVault/Contacts/` → пусто (кроме contacts.enc).
- `grep -rl "email|telegram"` в новых выводах — только маскированные.
- `find ~/WorkVault/Contacts -name "*.md"` → tutu-contacts.md отсутствует.
- `render_contact` unit-тест (summary/full, пустой email и т.п.) зелёный.
- Отчёт о просканированных источниках.

## Ограничение
Не менять внутренние consumer-логику (contacts_resolver, matcher). Их сырой доступ к полному email — легален (внутренний), они не выводят на экран. Реализацию выполняет Cursor-исполнитель (composer-2.5).
---

## Приложение. Предотвращение оседания ПДн — решение 09.09.2026

Канон и подробный план: `~/.hermes/skills/devops/pii-data-scanning/references/pii-rule-20260909.md`. Реализация — CHANGE-карточка DEV/PIIScan-pii-hygiene.

**Правило ПДн:** инцидент = полное ФИО/ФИ (2-3 слова кириллицей) + атрибут (email/тел/@handle/должность) в одном контексте. Голый логин без ФИО — **НЕ ПДн**.

1. **Детектор** (`~/.hermes/pii_scan/pii_scan.py`, `patterns.py`): идентификатор только `FIO_PATTERN`; `INTERNAL_LOGIN` выведен из набора идентификаторов (`login+*` исчезают); `PHONE` без ветки `\d{10,15}`; `SECRET_ASSIGNMENT` с `(?<![A-Za-z0-9_])`; Miro URL-token (`boardAccessToken` слева `https://miro.com`) не кред; `.json` — контекст по одному строковому полю (`scan_json_file`, не декартово).
2. **Whitelist +3:** `Confluence/`, `Projects/` (**ВЕСЬ Projects/** — финальное решение Саши 09.09, перекрывает правку ревизора «только TrisigmaFull»; Саша знает, что там 1-1 заметки сотрудников — сознательный выбор в пользу исключения всей зоны), `Meetings/`.
3. **Гигиена на записи (не дать осесть):** `redact.py::redact_fio_email_phone`; gateway `run.py` убрать `msg=`/`reply_to_text=` из INFO; MFL `format_post` и ExchangeMonitor `format_email` суть — через redact (`@username` сохраняется); `error_bus_cli.py cmd_show` redact; `llm_anomaly_scan.sh` — компакт `{subtype,is_error,result}`.
4. **TTL 5 дней:** TaskRefresh `session_store.prune_history()` (history/*.json; current/pending не трогать), llm-anomaly-audits `find -mtime +5 -delete`.
5. **Не делалось (решение Саши 09.09):** `pfs_batch` НЕ переведён в no_agent; `_db.py`/`report_error.sh`/`state.db` не менялись; ручная чистка накопленного не проводилась (TTL/ротация снимут сами).
