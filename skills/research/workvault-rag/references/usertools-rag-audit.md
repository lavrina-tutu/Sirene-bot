# USERTOOLS → WorkVault RAG Audit (2026-07-01)

## Vault stats
- Meetings/NewMeetings: 1071 MD-файлов (summary + transcript пары)
- Projects: ~15 проектов, jira_snapshot.json (не MD)
- Confluence: 2 MD-файла (ConfluenceSync почти не используется)
- People: card.md на каждого (~9 человек)
- Contacts: contacts.enc (зашифрован)

## Как MoveFromFF читает встречи (a_sources.py)

Сканирует NewMeetings/ рекурсивно (`rglob("*.md")`), исключает файлы с
`transcript` в имени, для каждого summary ищет парный transcript по эвристике
замены слова. Читает весь текст сразу (`p.read_text()`). Фильтрует уже
обработанные через state — не перечитывает всё при каждом запуске.

## Cron vm_movefromff
- Schedule: `0 10,12,14,16,18,20 * * 1-5` (каждые 2ч, рабочие дни)
- Model: claude-haiku-4-5
- Deliver: telegram:400307920 (личка)
- Toolsets: terminal only

## MoveFromJira детали
- Пишет: `~/WorkVault/Projects/<slug>/jira_snapshot.json`
- Known slugs: adm, antibot, okr-tool (из jira_snapshot.json файлов на диске)
- slug_overrides в sync.py для русских имён проектов
- Нет Hermes cron — нужно создать если нужен регулярный синк

## ConfluenceSync детали
- Пишет в: `~/WorkVault/Confluence/`
- Нет Hermes cron
- Конфиг из env: WORKVAULT_PATH или ~/WorkVault по умолчанию

## AnywhereContacts детали
- Хранит: `~/WorkVault/Contacts/contacts.enc` (AES-зашифрован)
- Для RAG недоступен — нужна отдельная стратегия (расшифровка в память агента)

## Рекомендованный порядок внедрения enzyme

1. `hermes plugin install jshph/enzyme-skill`
2. `cd ~/WorkVault && enzyme refresh` (первичная компиляция, ~20с)
3. Добавить в cron `vm_movefromff`: `&& cd ~/WorkVault && enzyme refresh`
4. При желании: `qmd collection add` + `qmd embed` для qmd
5. Доработать MoveFromJira: добавить генерацию card.md в sync.py
6. Создать cron для ConfluenceSync с enzyme refresh в конце
