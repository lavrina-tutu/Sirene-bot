# R10 LLM-fallback — отладка 2026-06-22

## Цепочка ошибок и фиксы

### Ошибка 1: `get_llm_client` не существует
**Симптом:** `ImportError: cannot import name 'get_llm_client'`  
**Причина:** Opus написал вызов несуществующей функции в bootstrap.py  
**Фикс:** заменить на `AnthropicLLM()` из `aggregate_from.utils.llm_client`

```python
# Было (неверно):
from aggregate_from.utils.llm_client import get_llm_client
llm_client = get_llm_client()

# Стало (верно):
from aggregate_from.utils.llm_client import AnthropicLLM
llm_client = AnthropicLLM()
```

### Ошибка 2: Неверное имя модели Haiku
**Симптом:** `anthropic.NotFoundError: model: claude-3-haiku`  
**Причина:** устаревшее имя модели в c_extractors.py  
**Фикс:** заменить `"claude-3-haiku"` → `"claude-haiku-4-5"` во всех 4 местах

```bash
sed -i 's/llm\.complete("claude-3-haiku"/llm.complete("claude-haiku-4-5"/g' aggregate_from/modules/c_extractors.py
```

### Ошибка 3: ANTHROPIC_API_KEY не найден
**Симптом:** `ANTHROPIC_API_KEY not found in env or ~/.env`  
**Причина:** llm_client.py искал только в `~/.env`, а ключ лежит в `~/.config/hermes/.env`  
**Фикс:** расширить поиск в `_load_api_key()`:

```python
for env_path in [
    Path.home() / ".env",
    Path.home() / ".config" / "hermes" / ".env",
    Path.home() / ".hermes" / ".env",
]:
    if env_path.exists():
        # ...парсим файл...
```

### Ошибка 4: summary_text всегда пустой (главный блокер R10)
**Симптом:** `R10 resolved: 0` — Haiku включился, но не классифицировал ни одной встречи  
**Причина:** FF-файлы не имеют секции `## Summary` — только `## Notes` и `## Bullet points`  
**Диагностика:**
```python
# Проверить что в unclear-встречах есть summary_text
for mf in files:
    pkg = a_sources.parse_meeting_file(mf.summary_path)
    route = b_router.determine_route(pkg, syncs_mem, class_mem)
    if route == Route.UNCLEAR:
        print(f"summary: {bool(pkg.summary_text)}")  # все False!
```
**Фикс 1:** добавить `notes` в `ff_parser.py`:
```python
notes_text = _extract_section(text, "Notes")
# в return dict добавить:
"notes": notes_text,
```
**Фикс 2:** в `a_sources.py` использовать fallback:
```python
summary_text=parsed["summary_text"] or "\n".join(parsed.get("bullet_points", [])) or parsed.get("notes", ""),
```
**Результат после фикса:** 65 из 74 unclear получили summary_text (ранее 0 из 74).

## Итог цепочки

```
enabled: false (get_llm_client не найден)
→ enabled: true, resolved: 0 (claude-3-haiku неверная модель → 404)
→ enabled: true, resolved: 0 (API ключ не найден)
→ enabled: true, resolved: 0 (summary_text пустой)
→ enabled: true, resolved: 65 (все фиксы применены)
```

## Правило на будущее

При unclear тупике в Bootstrap где нужно решение PM и поможет Haiku — включать R10:
```bash
AGGREGATE_LLM_FALLBACK=1 python3 scripts/bootstrap.py
```
Перед запуском проверить:
1. `AnthropicLLM()` импортируется без ошибок
2. Модель `claude-haiku-4-5` (не `claude-3-haiku`)
3. API ключ в `~/.config/hermes/.env`
4. `pkg.summary_text` не пустой (fallback на bullet_points/notes)
