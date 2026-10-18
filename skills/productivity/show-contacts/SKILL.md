---
name: show-contacts
description: "покажи контакты: AnywhereContacts (contacts.enc)"
  Безопасный показ контактов из AnywhereContacts (contacts.enc).
  Триггеры: «найди контакт», «email», «телефон», «тег», «кто на связи»,
  «расписание», «кто работает», «контакт по имени», «login сотрудника».
---

# show-contacts — безопасный показ контактов

## Обязательное правило (PII)

При **любом** выводе контакта пользователю (чат, CLI-ответ, summary, список):

1. **НЕ** читать `ContactStore.read()` / `get_contact()` / `find_contacts()` напрямую для показа.
2. **Использовать** только результат wrapper `show_contacts.sh`, который внутри использует
   `store.find_contacts_for_display(query)` / `render_contact(level="summary")` — вывод
   замаскирован. `level="full"` — **только** если пользователь явно просит полный
   email/телефон («покажи полный email», «reveal»); wrapper с `--full` возвращает
   email/phone контакта.
3. **Запрещено** печатать `email`, `login`, `telegram`, `zulip`, `phone` в открытом виде без маскирования.

## Боевой вызов (единственный разрешённый путь)

Скилл **обязан** выполнять поиск только через subprocess на боевой python инструмента:

```bash
~/.hermes/scripts/show_contacts.sh "иванов"          # summary (по умолчанию, замаскирован)
~/.hermes/scripts/show_contacts.sh "иванов" --full   # только по явной просьбе пользователя
```

Инвариант I1 (EcosystemIntegration §10.12): боевой python ключа `anywhere_contacts` —
`~/USERTOOLS/AnywhereContacts/venv_linux/bin/python` (3.11), где есть
`loguru` / `pydantic` / `yaml` и пакет импортируется. **Запрещён in-process
`from anywhere_contacts import …` в рантайме Hermes** (Hermes 3.14 не содержит
`loguru`/`pydantic_core`; это и была корневая дыра AC-002). В проде wrapper
`cd` в каталог инструмента → пакет резолвится, а `sys.executable` — venv_linux.

Результат wrapper — строки `ФИО | статус` (и `email=…/phone=…` только при `--full`),
либо `not-found from enc`. Если пользователю нужен email/телефон замаскированно —
summary достаточно; полный email только по явной просьбе.

## OrgLookup CLI

Для резолва через Exchange GAL:

```bash
orglookup who "Фамилия"           # email замаскирован
orglookup who "Фамилия" --reveal  # полный email (только по явной просьбе)
orglookup manager login           # summary
```

## Что можно показывать в summary

- ФИО / display_name
- должность, департамент, команда
- статус (active/inactive)
- **замаскированные** email, login, messenger handles

## Что нельзя

- Генерировать или обновлять `tutu-contacts.md` (удалён; только `contacts.enc`).
- Дампить contacts.enc или JSON с полными email в чат/лог без маски.
- Вызывать `from anywhere_contacts import …` in-process в Hermes.

## Внутренний матчинг (не трогать)

`contacts_resolver`, matcher в AggregateFromMeetings / ProtocolFromSummary / MarkObjectsFromSummary
могут использовать полный email **внутри** пайплайна — это не пользовательский вывод.