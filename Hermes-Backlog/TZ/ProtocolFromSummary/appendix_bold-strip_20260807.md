# Fix: Strip Markdown Bold (`**`) перед резолвом — 07.08.2026

## Проблема

Fireflies оборачивает имена исполнителей, дедлайны и имена в секции «Риски» в markdown-звёздочки `**`:

```
- **Олег Литвин**: Подготовить документацию / **14 августа**
- **Ткаченко Александр Владимирович**: риск / Высокая
```

Это ломает substring-поиск в `contacts_resolver` — `"**Олег Литвин**"` не совпадает с `"Олег Литвин"` в contacts.enc. Результат: даже существующие контакты (Ткаченко, Гладких) не резолвятся, задачи публикуются без `<ac:link>`.

## Решение

Функция `_strip_bold()` в `summary_parser.py`, применяется в трёх точках:

| Место | Что чистит | Было | Стало |
|---|---|---|---|
| `_parse_task_line()` | assignee_raw | `**Олег Литвин**` | `Олег Литвин` |
| `parse_summary_file()` | participants | `**Полина**` | `Полина` |
| `parse_summary_file()` | risks | `**Ткаченко**: риск...` | `Ткаченко: риск...` |

### Код

```python
def _strip_bold(s: str) -> str:
    """Убирает markdown-обёртку `**...**` из строки."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s)
```

### Файл

`~/USERTOOLS/ProtocolFromSummary/protocolfromsummary/summary_parser.py`

### Изменения

1. Добавлена `_strip_bold()` после `_strip_bullet()` (строка ~63)
2. `_parse_task_line()`: `line = _strip_bold(raw)` вместо `line = raw`
3. `parse_summary_file()`: `participants=[_strip_bold(p) for p in ...]`
4. `parse_summary_file()`: `risks=[_strip_bold(r) for r in ...]`

## Верификация

- `pytest tests/test_summary_parser.py` → 11 passed
- Republish встречи «Trisigma. Обсуждение вопросов с мобильным SDK» → Гладких и Ткаченко получили `<ac:link>` в Confluence
- Решения/блокеры: `**` остаются в тексте (это контент, не имя) — корректно, `_strip_bold` применяется только к участникам, задачам, рискам

## Статус

✅ Применено 07.08.2026, переопубликовано page_id 490170597
