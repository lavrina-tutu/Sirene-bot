---
name: workvault-entities
description: "Структура WorkVault/Entities/<slug>/ — единое хранилище всех сущностей (проекты, 1-1, люди, мультисинки). Миграция из Projects/+People/. Правила именования, создания новых сущностей через Сирень, связь с entities.json. Триггеры: создай сущность, добавь проект в vault, структура WorkVault, Entities, папка проекта, 1-1 папка."
version: 1.0.0
author: Sirene
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [workvault, entities, obsidian, structure, migration]
    related_skills: [mofs-operations, obsidian, about_usr_skills]
---

# WorkVault Entities — структура и правила

## Целевая структура (после миграции 23-24.07.2026)

```
WorkVault/
  Entities/
    <slug>/
      <slug>.md        # карточка сущности (имя файла = slug)
      Messages/        # саммари Loop/встреч (YYYY-MM-DD.md)
      Pages/           # документы из Confluence (brief, charter и др.)
      ...              # прочие файлы сущности
  Meetings/            # не трогать
  Confluence/          # не трогать
  Contacts/            # не трогать
  Registries/
    entities.json      # реестр всех сущностей
```

## Слаги — правила именования

- Только латиница, цифры, подчёркивание: `trisigma`, `aralov_1on1`, `ml_platforma`
- Без дефисов в новых slug'ах (дефисы — наследие старой схемы)
- Кириллица в именах папок — ЗАПРЕЩЕНА
- Slug совпадает с ключом в `entities.json`

## Текущие сущности (после миграции, 30 папок)

| Тип | Примеры |
|---|---|
| project | trisigma, ab_platforma, ml_platforma, cu, devrel, okr, parsing, vestnik, alpha, ai_ready, ai_analitik, antibot, metroteka |
| one_on_one | aralov_1on1, kirill_1on1, zhirov_1on1, ilya_1on1, dayana_1on1 |
| person | alekseeva, kotelnikova, maly, peretyatkova, sereda |
| multisync | datatalks, sink_aid |
| misc | pmo, adm |

**kind: tool** — только запись в entities.json, папки НЕ создаются (`folder: null`).

## Создание новой сущности через Сирень

1. Сирень спрашивает slug (латиница) и kind
2. Если slug не найден в entities.json → Сирень спрашивает подтверждения перед созданием
3. Создаётся папка `Entities/<slug>/`
4. Создаётся `Entities/<slug>/<slug>.md` с минимальным frontmatter
5. Добавляется запись в entities.json через `entity-registry add`

```bash
entity-registry add <slug> --kind project --display-name "Название" \
  --alias "русский алиас" --parent-null -y
mkdir -p ~/WorkVault/Entities/<slug>
# создать <slug>.md
```

## Подключение Loop-канала к сущности

Команда Сирени: «подключи канал #pm-team к проекту Trisigma»

1. Сирень резолвит slug через entities.json
2. Если slug не найден → предлагает создать новую сущность или уточнить название
3. Добавляет запись в `loop_rules.yaml`:
```yaml
channel_mappings:
  pm-team: trisigma
```
4. Саммари канала будет писаться в `Entities/trisigma/Messages/YYYY-MM-DD.md`

## Wikilinks в Obsidian

После миграции все ссылки используют `[[Entities/<slug>/...]]`:
- `[[Entities/trisigma/trisigma|Trisigma]]`
- `[[Entities/aralov_1on1/aralov_1on1|Аралов]]`

Wikilinks по именам файлов без пути — Obsidian резолвит автоматически.

## История миграции (23-24.07.2026) — ЗАВЕРШЕНА ✅

- `WorkVault/Projects/<slug>/` → `WorkVault/Entities/<slug>/` (16 папок)
- `WorkVault/People/<ФИО>/` → `WorkVault/Entities/<slug>/` (9 папок, merge с 1-1)
- Плоские `.md` файлы 1-1 (`aralov_1on1.md`) → `Entities/aralov_1on1/aralov_1on1.md`
- `Projects/Pages/<proj>_brief.md` → `Entities/<slug>/Pages/`
- Wikilinks обновлены скриптом (python re.sub) — не через Obsidian
- `Projects/sr-tool/` и `Projects/_research/` — удалены
- `Projects/` и `People/` — удалены

**Снапшот перед миграцией:** `~/WorkVault_backup/Hermes-Backlog/TZ/EntitiesMigration/pre-migration-20260724-0552.tgz`

**ТЗ миграции:** `~/WorkVault/Hermes-Backlog/TZ/EntitiesMigration/EntitiesMigration_TZ.md` v0.2.0, status: completed

## Питфоллы

- **Не создавать папки для kind:tool** — только запись в entities.json с `folder: null`
- **Slug — без дефисов** — старые `ai-mas`, `ml-platforma` уже переименованы в `ai_analitik`, `ml_platforma`
- **Кириллица в имени папки** — категорически нельзя, Obsidian и rclone имеют проблемы с нормализацией Unicode
- **Перед созданием — проверить aliases** в entities.json: `entity-registry list | grep -i <ключевое слово>`
- **wikilinks с путём сломаются при переименовании** — если путь указан явно (`[[Entities/trisigma/card]]`), при переименовании файла нужен ручной rewrite или обновление через Obsidian
- **Messages/ создавать только при подключении Loop-канала** — не заранее пустые папки
- **Wikilinks с [[People/...]] и [[Projects/...]] — обновлять скриптом, не ждать Obsidian (24.07.2026).** Obsidian авто-обновление работает только если vault открыт локально с включённым «Automatically update internal links». На VM без GUI — python `re.sub` по всем .md. Паттерн: `re.sub(r'\\[\\[People/([^\\]|]+)(\\|[^\\]]+)?\\]\\]', replace_fn, text)`. Проверять остаток: `grep -r '\\[\\[People/' ~/WorkVault --include='*.md' -l`. Ссылки-примеры в `_test/` и ТЗ-документах — НЕ переписывать (они иллюстративные, не живые).
- **После скриптового rewrite wikilinks — проверять оставшиеся вхождения двумя проходами:** (1) реальные файлы (не `_test/`, не `TZ/`, не `Hermes-Backlog/`) — нулевой остаток обязателен; (2) тестовые/ТЗ-шаблоны — содержат [[People/...]] как иллюстрацию, не трогать.
- **_test/ и TZ-документы** — ссылки `[[People/...]]` в тестовых шаблонах и ТЗ-документах — это иллюстративные примеры, не живые ссылки. Не переписывать — в них это часть описания архитектуры.
- **Бэкап contacts.enc перед MoveFromLoop sync** — `cp ~/WorkVault/Contacts/contacts.enc ~/WorkVault_backup/Contacts/contacts_pre-MFL-$(date +%Y%m%d-%H%M).enc`
- **Папки без записи в entities.json** — при миграции оказалось 9 папок-сирот (`ai-mas`, `alpha`, `chatbot` и др.). Паттерн разбора: вывести список → поштучный бриф → для каждой: алиас к существующему slug ИЛИ новая запись ИЛИ удалить. **Критерий алиаса:** есть запись в entities.json с похожим display_name или уже содержащая этот slug в aliases. Проверять: `python3 -c "import json; d=json.load(open('entities.json')); [print(k, v.get('display_name'), v.get('aliases')) for k,v in d.get('entities',d).items() if any(x in str(v).lower() for x in ['ключевое_слово'])]"`
- **kind:unknown** — служебные маршруты PFS (`tsu`, `vstrechi_nerazobrannoe`) не являются реальными сущностями. Удалять из entities.json, папки не создавать.
