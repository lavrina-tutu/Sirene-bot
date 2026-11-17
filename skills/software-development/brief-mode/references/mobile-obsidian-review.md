> Historical source, 2026; preserved as recorded, not current instructions. Verify against the current entrypoint and implementation.

## Подача ссылок на файлы Obsidian (мобильный Telegram)

`obsidian://open?vault=...` ссылки **не открываются** в Telegram на мобильном (iOS/Android блокируют кастомные протоколы в inline-ссылках).

**Решение:** создать review-заметку в WorkVault с wiki-ссылками. PM открывает её в Obsidian на телефоне — там всё кликабельно.

```python
# Шаблон файла: WorkVault/Inbox/unclear_review.md
content = """---
created: YYYY-MM-DD
type: review
---

# 🔍 [Заголовок] — разбор N встреч

1. ДД.ММ.ГГГГ — [[имя-файла-без-расширения|Краткое название]]
2. ДД.ММ.ГГГГ — [[имя-файла-без-расширения|Краткое название]]
...
"""
```

**Имя файла wiki-ссылки** = имя файла без `.md` и без полного пути. Obsidian находит файл по имени независимо от папки.

После создания файла — `rclone sync WorkVault owncloud:WorkVault` и дождаться синка FolderSync на телефоне.

**Антипаттерн:** давать нумерованный список с `[открыть в Obsidian](obsidian://...)` — выглядит кликабельно в десктопном Telegram, но не работает на мобильном.

