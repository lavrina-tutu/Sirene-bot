# Извлечение sticky-имён из persisted SVG-квадранта

Когда большой `canvas_read_as_svg` для квадранта персистится в файл
(`/tmp/hermes-results/call_*.txt`, «tool result was too large»), парсить его python-скриптом,
а НЕ `read_file` (длинные строки → «Binary file - cannot display as text»).

Файл — JSON строка с экранированным SVG внутри `svg`-поля. Форма контейнера нестабильна:
может быть `obj["svg"]` напрямую, а может — `result`-обёртка (`json.loads(data["result"])["svg"]`).
Обе пробовать: `svg = data.get("svg") or json.loads(data["result"]).get("svg")`.

**Атрибуты в теге идут в произвольном порядке** — регексп `data-type="sticky".*?data-content="..."`
пропускает карточки, где `data-content` стоит ПЕРЕД `data-type`. Вытаскивать по блоку тега,
а не ждать фиксированного порядка:

```python
import re, html

svg = data.get("svg") or json.loads(data["result"]).get("svg", "")
idx, entries = 0, []
while True:
    i = svg.find('data-type="sticky"', idx)
    if i == -1:
        break
    start = svg.rfind('<', 0, i)     # границы открывающего тега
    end = svg.find('>', i)
    tag = svg[start:end+1]
    m = re.search(r'data-content="([^"]*)"', tag)   # ищем в САМИХ границах тега
    if m:
        c = html.unescape(m.group(1))
        c = re.sub(r'<[^>]+>', ' ', c)   # снять html-теги
        c = re.sub(r'\s+', ' ', c).strip()
        entries.append(c)
    idx = end+1
```

Замечания:
- Искать маркер `data-type="sticky"` (двойные кавычки) — карточки людей пишутся именно так. Одинарные кавычки встречаются редко; если нужно — второй проход с `data-type='sticky'`.
- `data-content` в SVG-выводе экранировано: `&lt;p&gt;Цветкова Лена&lt;/p&gt;`; после снятия тегов `p` → «Цветкова Лена».
- Синонимы регистра: часть данных `data-content="Ларьков Саша"` без `<p>`, часть с `<p>` — оба варианта снимать.
- Роль/статус часто дописана в тексте стикера в скобках: `Максимов Владислав (frontend-разработчик)`, `Суровин Денис (стажер)` — для дедупа и фильтра стажёров нормализовывать `(…)` к имени и проверять подстроку `стаж`.
- Результаты всех квадрантов слить в один список (см. `count-and-dedup-people.md`) и продедуплицировать.