> Historical source, 2026; preserved as recorded, not current instructions. Verify against the current entrypoint and implementation.

## Расхождение числа unclear между реестром и Bootstrap

Bootstrap всегда пересчитывает unclear из `classification_memory.json` — он не видит `unclear_registry.md`. Поэтому:
- **Бриф снижает unclear** только если алиасы вносятся в `classification_memory.json`
- `unclear_registry.md` применяется только в продовом пайплайне (Фаза 1+)
- Если Bootstrap показывает 77 а ожидали 9 — нужно внести алиасы из брифа в classification_memory и перезапустить Bootstrap
- **Правило:** после брифа Opus вносит решения в **оба** места: unclear_registry.md + classification_memory.json (алиасы для проектов)

## Ловушки Bootstrap unclear (AggregateFromMeetings)

После перезапуска Bootstrap `unclear_queue.md` может показывать больше записей, чем реально нераскрытых. Причины ложных позитивов:

1. **«Action items» вместо «Саммари»** — Bootstrap создаёт записи типа `Action items:` для некоторых встреч. Парсер unclear_queue ищет `— Саммари:`, поэтому action-items-записи парсятся как `? | ?`. Это не новые unclear — это те же встречи (Кирилл 1-1, Илья 1-1 и т.д.), уже решённые.
2. **Системные файлы** — `_log_meet.md` и `_registry_meet.md` попадают в unclear со статусом «нет реальных участников». Добавить в skip-список в `unclear_registry.md`.
3. **Решения брифа не применяются при Bootstrap** — `unclear_registry.md` хранит ручные решения, но Bootstrap их не читает — он классифицирует заново по `classification_memory.json`. Реальный % unclear = записи в секции unclear в реестре / total_files.

**Правило проверки:** после Bootstrap сравнить новый `unclear_queue.md` с решениями брифа программно (Python-скрипт). Если все «новые» — это уже решённые или системные файлы → gate пройден, идти к следующему этапу.

