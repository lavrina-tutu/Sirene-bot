# ConfluenceSync — заметки по реализации (28.05.2026)

## Статус
- ✅ Реализован: 22 файла, 47/47 unit-тестов зелёных
- ✅ Скилл создан: `skills/productivity/movefrom-confluence/SKILL.md`
- ⚠️ Баг конвертера (IndexError) — починен Opus в той же сессии

## Архитектурные решения

### Изображения
Не скачиваем, пишем `📎 [рисунок](ссылка_на_confluence_страницу)`.

### Ре-синк
Только по явному запросу (`--resync`). Без флага — существующие файлы пропускаются (`skipped_exists`).

### Конфирмация записи
- `confirm=True` (default) — всегда спрашивать перед push
- `confirm=False` — для программных вызовов от других инструментов (pass-through)

### Режимы вывода
- `--to-file` (default): записать в `WorkVault/Confluence/...`
- `--to-context`: stdout, без файла (для UC-1 "прочитай и сделай")
- `--to-both`: и файл, и stdout

## Известные баги

### IndexError в _replace_macros (converter.py)
**Симптом:** `IndexError: list index out of range` в `placeholder.append(BeautifulSoup(...))`.
**Причина:** вложенные или незакрытые `<ac:structured-macro>` теги на некоторых страницах.
**Статус:** починен Opus 28.05 при создании скилла.
**Обходной путь (если снова появится):** `--no-recursive` + попробовать другую страницу.

## Пути

```
Код:         C:\Users\tkachenkoav\Documents\Cursor_projects\hermes-agent\USERTOOLS\ConfluenceSync\
ТЗ:          USERTOOLS\ConfluenceSync\TZ.md
Credentials: USERTOOLS\MoveFromConfluence\.env
Vault:       C:\Users\tkachenkoav\WorkVault\Confluence\<Space>\<Title>\index.md
Лог:         C:\Users\tkachenkoav\WorkVault\_meta\ConfluenceSync\_sync_log.jsonl
```

## Проверенные форматы URL
- `https://dom.tutu.ru/pages/viewpage.action?pageId=499551841` ✅
- `https://dom.tutu.ru/display/SPACE/Title` ✅
- Числовой page_id как строка ✅
- Корень домена `https://dom.tutu.ru` ❌ — нужна конкретная страница
