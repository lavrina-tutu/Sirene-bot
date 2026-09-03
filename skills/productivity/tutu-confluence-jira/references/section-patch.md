# Section patch (B0)

Патч **одной секции** Confluence storage — не PUT всего `body.storage` моделью.

## Алгоритм

1. `GET ?expand=body.storage,version` → JSON-файл (не inline stdout как единственный путь).
2. `find_section_span(storage, heading)` — заголовок и пояснение **вне** replace-span.
3. `replace_section_inner` — замена только внутренности (таблица/абзацы до следующего заголовка того же уровня).
4. `build_put_payload(title, version+1, storage)` — **без** `space`.
5. `PUT` с Bearer из `~/USERTOOLS/ConfluenceSync/.env`.

## Запрет LLM → storage

Grok/composer выдаёт markdown/текст поля. В `body.storage` вставляет **только** `section_patch.py`.  
Скрипт **не** принимает полный storage из stdin как единственный путь — только `--inner-file` для внутренности секции.

## CLI

```bash
python3 scripts/section_patch.py get PAGE_ID --out /tmp/page.json
python3 scripts/section_patch.py patch PAGE_ID \
  --heading "Ключевые поставки и сроки" \
  --inner-file /tmp/deliveries_inner.html
```

После PUT — `verify_skeleton.py` (повторный GET координатором).
