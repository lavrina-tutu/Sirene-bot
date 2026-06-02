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
confluencesync push "/home/tkachenkoav/WorkVault/Confluence/<Space>/<Page>/index.md" --no-confirm

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

## Перебор API ключей (ОБЯЗАТЕЛЬНО перед любым обращением к Confluence)

Два ключа: **KEY1** — работает из офиса, **KEY2** — работает из дома. Заранее неизвестно какой сейчас активен.

### Алгоритм (4 попытки, потом отказ)

```
K1 → K2 → K1 → K2 → ❌ "Нет доступа к Confluence (ни один ключ не работает)"
```

Нашёлся рабочий → **кешируем** в `/tmp/hermes_confluence_token` и используем до перезапуска gateway.

### Bash-реализация

```bash
check_token() {
  # Возвращает 0 если токен рабочий (не Anonymous)
  DISPLAY=$(curl -s --max-time 5 -H "Authorization: Bearer $1" \
    "https://dom.tutu.ru/rest/api/user/current" | grep -o '"displayName":"[^"]*"')
  echo "$DISPLAY" | grep -v Anonymous | grep -q displayName
}

get_confluence_token() {
  # 1. Сначала проверяем кеш сессии
  CACHE=/tmp/hermes_confluence_token
  if [ -f "$CACHE" ]; then
    TOKEN=$(cat "$CACHE")
    check_token "$TOKEN" && echo "$TOKEN" && return 0
    rm -f "$CACHE"  # кеш протух — сбрасываем
  fi

  # 2. Читаем оба ключа
  KEY1=$(grep "^CONFLUENCE_TOKEN=" /c/Users/tkachenkoav/Documents/Cursor_projects/hermes-agent/USERTOOLS/MoveFromConfluence/.env | cut -d= -f2)
  KEY2=$(grep "^CONFLUENCE_TOKEN_PREV=" /c/Users/tkachenkoav/Documents/Cursor_projects/hermes-agent/USERTOOLS/MoveFromConfluence/.env | cut -d= -f2)

  # 3. Перебор: K1 → K2 → K1 → K2
  for TOKEN in "$KEY1" "$KEY2" "$KEY1" "$KEY2"; do
    if check_token "$TOKEN"; then
      echo "$TOKEN" > "$CACHE"   # кешируем на сессию
      echo "$TOKEN"
      return 0
    fi
  done

  echo "❌ Нет доступа к Confluence — ни один ключ не работает (офис/дом?)" >&2
  return 1
}

# Использование:
TOKEN=$(get_confluence_token) || exit 1
CONFLUENCE_TOKEN="$TOKEN" confluencesync pull "..." --to-context --no-recursive
```

### Правила

- **Кеш** живёт в `/tmp/hermes_confluence_token` — сбрасывается при перезапуске Windows/gateway
- При перезапуске gateway — перебор запускается заново
- **Не обновлять `.env` файлы** — ключи там постоянные, меняется только кеш сессии
- Если оба ключа не работают — сообщить пользователю: *"Нет доступа к Confluence — возможно, нужен VPN или ключи устарели"*

## Pitfalls (известные грабли)

1. **Два ключа: офисный и домашний** — всегда запускай `get_confluence_token()` перед работой. Алгоритм K1→K2→K1→K2, кеш в `/tmp/hermes_confluence_token`. Не трогай `.env` файлы.
2. **VPN обязателен.** `dom.tutu.ru` доступен только через корпоративный VPN. Если получаешь connection error / timeout — первое, что предлагать пользователю: проверить VPN.
3. **Токен протухает.** Если `curl -H "Authorization: Bearer $TOKEN" https://dom.tutu.ru/rest/api/user/current` возвращает `"type":"anonymous"` — запускай `get_confluence_token()` для перебора всех ключей.
4. **IndexError в конвертере макросов.**
   - попробуй `--no-recursive` (возможно, падает одна из дочерних)
   - попробуй другую страницу
   - сообщи пользователю баг и попроси скинуть пример страницы для фикса
3. **Push без `confluence_id` → создание новой страницы.** Если у локального `index.md` в frontmatter нет `confluence_id`, push НЕ обновит существующую — он создаст новую подстраницу под `parent`. Если `parent` тоже отсутствует — ошибка. Перед push к существующей странице проверь frontmatter.
4. **Version conflict при push.** Если на сервере страница изменилась с момента последнего pull — push блокируется. Сделай сперва `pull --resync`, помёрджи правки руками, потом push.
5. **Wiki-ссылки `[[Title]]` при push.** Резолвятся в `<ac:link>` по title в том же Space. Если страница с таким title не найдена — оставляется plain text + warning в лог.
6. **Windows-санитизация имён.** Папки в vault урезаются до 80 символов и без `<>:"/\|?*`. Если ищешь страницу по title и не находишь — посмотри сокращённый вариант.
7. **`.env` живёт в MoveFromConfluence.** Реальный путь: `USERTOOLS/MoveFromConfluence/.env` (там `CONFLUENCE_URL=https://dom.tutu.ru` и `CONFLUENCE_TOKEN`). ConfluenceSync ищет `.env` в порядке: `USERTOOLS/MoveFromConfluence/.env` → `USERTOOLS/MoveFromExchange/.env` → локальный `.env` рядом с пакетом. Не плоди отдельный `.env` в `USERTOOLS/ConfluenceSync/`.
8. **Короткие URL `/x/XXXXX`** — ConfluenceSync не умеет их резолвить. Сначала раскрой через curl: `curl -sv "https://dom.tutu.ru/x/XXXXX" 2>&1 | grep Location` — получишь редирект на tinyurl.action, а оттуда grep `pageId=` из HTML-тела. Потом используй `pageId` в обычном URL `/pages/viewpage.action?pageId=NNN`.
9. **Python для ConfluenceSync** — запускать через `/c/Users/tkachenkoav/AppData/Local/Programs/Python/Python311/python.exe -m confluencesync`, не через `python` или `python3.11` (uv trampoline ломается). Переменная `CONFLUENCE_TOKEN` передаётся как env: `CONFLUENCE_TOKEN="$TOKEN" python.exe -m confluencesync ...`
8. **Короткие URL (`/x/XXXXX`) не поддерживаются напрямую.** ConfluenceSync не умеет резолвить tiny-URL формата `https://dom.tutu.ru/x/QBHcE` → `ValueError: Cannot extract page id/space from URL`. Резолви pageId так:
   ```bash
   TOKEN=$(get_confluence_token)
   curl -s -H "Authorization: Bearer $TOKEN" -L \
     "https://dom.tutu.ru/pages/tinyurl.action?urlIdentifier=XXXXX" \
     | grep -o 'pageId=[0-9]*' | head -1
   # Затем используй: https://dom.tutu.ru/pages/viewpage.action?pageId=<ID>
   ```
   Редирект 302 → tinyurl.action → страница с несколькими pageId в HTML — берём первый.

8. **Короткие Confluence URL (`/x/XXXXX`)** — ConfluenceSync не умеет их резолвить. Решение: сделать curl-редирект чтобы получить pageId:
   ```bash
   curl -sv -H "Authorization: Bearer $TOKEN" "https://dom.tutu.ru/x/QBHcE" 2>&1 | grep Location
   # Даёт: /pages/tinyurl.action?urlIdentifier=QBHcE
   # Затем грузить страницу как HTML и grep pageId=[0-9]*
   ```
10. **`confluencesync` запускать через Python 3.11 напрямую**, не через `python` (uv trampoline ломается). Рабочий вызов:
    ```bash
    /c/Users/tkachenkoav/AppData/Local/Programs/Python/Python311/python.exe -m confluencesync pull "..." --to-both --no-recursive
    ```
    Команда `confluencesync` в PATH не работает из git-bash из-за uv trampoline.

## Пример полного UC-1 диалога

Пользователь: «Сирень, прочти https://dom.tutu.ru/pages/viewpage.action?pageId=499551841 и настрой по ней dev-окружение».

Сирень:
1. `confluencesync pull "https://dom.tutu.ru/pages/viewpage.action?pageId=499551841" --to-context --no-recursive`
2. Получает MD-инструкцию в stdout.
3. Выполняет шаги из инструкции в терминале.
4. Отчитывается пользователю, что сделано / где запнулась.

**Не пишет страницу в WorkVault** — это разовое чтение.
