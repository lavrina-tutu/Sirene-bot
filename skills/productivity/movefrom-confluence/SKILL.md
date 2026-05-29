---
name: movefrom-confluence
description: "ConfluenceSync — двусторонняя синхронизация страниц Confluence dom.tutu.ru ↔ Obsidian WorkVault. Используй когда пользователь даёт ссылку на dom.tutu.ru и просит изучить/настроить/применить инструкцию, или когда другой инструмент встречает ссылку на Confluence и её нужно обогатить контентом."
version: 1.0.0
author: Сирень
tags: [confluence, tutu, workvault, obsidian, sync, dom.tutu.ru]
platforms: [windows, telegram, cli]
---

# movefrom-confluence (ConfluenceSync)

Инструмент `confluencesync` — двусторонняя синхронизация страниц on-prem Confluence (`https://dom.tutu.ru`) и локального Obsidian-vault (`C:\Users\tkachenkoav\WorkVault\Confluence\`).

Полная спецификация: `C:\Users\tkachenkoav\Documents\Cursor_projects\hermes-agent\USERTOOLS\ConfluenceSync\TZ.md`.
Заметки по реализации: `references/confluencesync-implementation-notes.md`.

## Когда запускать (триггеры)

### A. Пользователь дал ссылку на Confluence
Если в сообщении есть URL вида `https://dom.tutu.ru/...` (`/display/...`, `/pages/viewpage.action?pageId=...`, `/spaces/.../pages/...`) **и** пользователь просит что-то сделать со страницей — изучить, прочитать, настроить по инструкции, применить, обобщить:

→ Запусти `confluencesync pull "<url>" --to-context --no-recursive` — получишь Markdown-контент страницы в stdout, **без записи на диск**. Используй его как контекст и выполняй инструкцию пользователя.

Примеры формулировок:
- «настрой dev-окружение по этой странице …»
- «прочти и сделай как написано …»
- «что там написано на странице …»
- «суммаризируй …»

### B. Другой инструмент встретил ссылку на Confluence
При обработке встреч (MoveFromFF), писем (MoveFromExchange), задач (MoveFromConfluence-tasks) встречена ссылка на dom.tutu.ru:

→ Вызови `confluencesync pull "<url>" --to-file --no-recursive` — страница сохранится в `WorkVault/Confluence/<Space>/<Title>/index.md`, путь верни вызывающему инструменту для вставки рядом с сущностью.

### C. Пользователь явно правил локальный `index.md` и сказал «залей обратно / обнови в Confluence»
→ `confluencesync push "<путь к md>" --no-confirm`

## Команды

```bash
# UC-1 «прочитай и сделай» — stdout, без записи
confluencesync pull "<url>" --to-context --no-recursive

# UC-2 «обогати» — в файл WorkVault
confluencesync pull "<url>" --to-file --no-recursive

# Оба варианта одновременно
confluencesync pull "<url>" --to-both --no-recursive

# Полное дерево с дочерними
confluencesync pull "<url>" --to-file              # рекурсивно по умолчанию
confluencesync pull "<url>" --to-file --depth 2

# Push обновления существующей страницы (по confluence_id из frontmatter)
confluencesync push "C:/Users/tkachenkoav/WorkVault/Confluence/<Space>/<Page>/index.md" --no-confirm

# Создание новой подстраницы (если в frontmatter нет confluence_id, но есть parent)
confluencesync push "путь/к/новой/странице.md"

# Перезаписать локальные файлы свежей версией с сервера
confluencesync pull "<url>" --to-file --resync

# Лог операций
confluencesync log --tail 20
```

## Программный API (для других инструментов)

```python
from confluencesync import ConfluenceSync

cs = ConfluenceSync()

# UC-1: получить MD-контент в строку (для контекста агента)
md = cs.pull(url="https://dom.tutu.ru/...", to="context")

# UC-2: сохранить в WorkVault, получить путь
path = cs.pull(url="https://dom.tutu.ru/...", to="file")

# UC-3: автообновление без подтверждения
cs.push(md_path="...", confirm=False)

# Создание новой подстраницы
cs.push_new(parent_id="123", title="...", content_md="...", confirm=False)
```

## Где что лежит

| Что | Путь |
|---|---|
| Vault со страницами | `C:\Users\tkachenkoav\WorkVault\Confluence\<Space>\<Title>\index.md` |
| Credentials (`.env`) | `USERTOOLS/MoveFromConfluence/.env` (читает `CONFLUENCE_URL=https://dom.tutu.ru`, `CONFLUENCE_TOKEN`) |
| Локальный `.env.example` | `USERTOOLS/ConfluenceSync/.env.example` |
| Лог синхронизации | `C:\Users\tkachenkoav\WorkVault\_meta\ConfluenceSync\_sync_log.jsonl` |
| Лок-файл | `WorkVault\_meta\ConfluenceSync\.lock` |
| Код | `USERTOOLS/ConfluenceSync/confluencesync/` |
| ТЗ | `USERTOOLS/ConfluenceSync/TZ.md` |

## Frontmatter в `index.md`

```yaml
---
confluence_id: "499551841"
title: "..."
confluence_url: "https://dom.tutu.ru/pages/viewpage.action?pageId=499551841"
space: "SPACE"
parent: "499551840"
children: ["...", "..."]
author: "..."
last_modified: "2026-05-28T10:00:00Z"
synced_at: "2026-05-28T22:00:00Z"
---
```

Для push новой подстраницы — обязательно укажи в frontmatter `parent: "<id>"` и `title`, поле `confluence_id` оставь пустым/удали.

## Дефолты, которые я (Сирень) держу в голове

- **По умолчанию `pull` рекурсивен** — для обычного сценария «прочитай и сделай» добавляй `--no-recursive`, иначе утянешь всё поддерево.
- **По умолчанию `pull` пишет в файл.** Для UC-1 (контекст агента) ОБЯЗАТЕЛЬНО ставь `--to-context`, иначе создашь мусор в WorkVault.
- **Ре-синк только по запросу.** Без `--resync` существующие локальные файлы не перезаписываются (статус `skipped_exists`).
- **`push` по умолчанию спрашивает подтверждение.** При программном вызове из другого инструмента — `--no-confirm` / `confirm=False`.

## Pitfalls (известные грабли)

1. **VPN обязателен.** `dom.tutu.ru` доступен только через корпоративный VPN. Если получаешь connection error / timeout — первое, что предлагать пользователю: проверить VPN.
2. **IndexError в конвертере макросов.** Конвертер `converter.py` может падать с `IndexError: list index out of range` в `_replace_macros` на сложных страницах (вложенные/неполные `<ac:structured-macro>`). Обходной путь:
   - попробуй `--no-recursive` (возможно, падает одна из дочерних)
   - попробуй другую страницу
   - сообщи пользователю баг и попроси скинуть пример страницы для фикса
3. **Push без `confluence_id` → создание новой страницы.** Если у локального `index.md` в frontmatter нет `confluence_id`, push НЕ обновит существующую — он создаст новую подстраницу под `parent`. Если `parent` тоже отсутствует — ошибка. Перед push к существующей странице проверь frontmatter.
4. **Version conflict при push.** Если на сервере страница изменилась с момента последнего pull — push блокируется. Сделай сперва `pull --resync`, помёрджи правки руками, потом push.
5. **Wiki-ссылки `[[Title]]` при push.** Резолвятся в `<ac:link>` по title в том же Space. Если страница с таким title не найдена — оставляется plain text + warning в лог.
6. **Windows-санитизация имён.** Папки в vault урезаются до 80 символов и без `<>:"/\|?*`. Если ищешь страницу по title и не находишь — посмотри сокращённый вариант.
7. **`.env` живёт в MoveFromConfluence.** Реальный путь: `USERTOOLS/MoveFromConfluence/.env` (там `CONFLUENCE_URL=https://dom.tutu.ru` и `CONFLUENCE_TOKEN`). ConfluenceSync ищет `.env` в порядке: `USERTOOLS/MoveFromConfluence/.env` → `USERTOOLS/MoveFromExchange/.env` → локальный `.env` рядом с пакетом. Не плоди отдельный `.env` в `USERTOOLS/ConfluenceSync/`.
8. **VPN нужен даже для проверки токена.** Exchange и Confluence (`dom.tutu.ru`) — оба за корпоративным VPN. Простая проверка `curl ... | python` может не работать из-за отсутствия `python3` в PATH на Windows — использовать `execute_code` или `python3.11` явно.

## Пример полного UC-1 диалога

Пользователь: «Сирень, прочти https://dom.tutu.ru/pages/viewpage.action?pageId=499551841 и настрой по ней dev-окружение».

Сирень:
1. `confluencesync pull "https://dom.tutu.ru/pages/viewpage.action?pageId=499551841" --to-context --no-recursive`
2. Получает MD-инструкцию в stdout.
3. Выполняет шаги из инструкции в терминале.
4. Отчитывается пользователю, что сделано / где запнулась.

**Не пишет страницу в WorkVault** — это разовое чтение.
