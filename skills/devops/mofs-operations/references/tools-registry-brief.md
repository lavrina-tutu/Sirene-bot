# Бриф по реестру инструментов (entities.json tools)

Паттерн пополнения корзины tools в entities.json — зафиксирован 22.07.2026.

## Алгоритм

1. **Подсчитать частоту** упоминания кандидатов в архиве встреч:

```bash
python3 -c "
import glob, re
from collections import Counter
files = glob.glob('/home/tkachenkoav/WorkVault/Meetings/NewMeetings/*summary.md')
tools_patterns = {
    'jira': r'\bjira\b|\bджира\b',
    'confluence': r'\bconfluence\b|\bконфлюенс\b',
    'clickhouse': r'\bclickhouse\b|\bкликхаус\b',
    # ... добавить нужные
}
counts = Counter()
for f in files:
    content = open(f).read().lower()
    for tool, pat in tools_patterns.items():
        if re.search(pat, content, re.IGNORECASE):
            counts[tool] += 1
print(f'Всего файлов: {len(files)}')
for tool, cnt in counts.most_common():
    if cnt >= 2:
        print(f'{cnt:4d} встреч — {tool}')
"
```

2. **Показать Саше таблицу** от наиболее к наименее частым — с числом встреч.
3. **Брифовать по одному** (да=1 / нет=2) — от частых к редким.
4. **Уточнять нюансы** по ходу — например Loop vs Zulip (один инструмент под разными именами).
5. **Фиксировать оба списка** — добавленные и исключённые навсегда.

## Сохранение результатов

- Добавить entries в `~/WorkVault/Registries/entities.json` (kind=tool, aliases)
- Создать приложение: `TZ/EntityRegistry/appendix_tools_registry_<YYYYMMDD>.md`
- В ТЗ `EntityRegistry_TZ.md` сверху добавить строку в таблицу «Приложения к ТЗ»
- **НЕ** создавать отдельный файл в `Registries/` — только в `TZ/EntityRegistry/`

## Стоп-лист (исключены навсегда, 22.07.2026)

Не добавлять без явного решения Саши:
`python, docker, mlflow, redis, postgres, dbt, jenkins, gitlab, superset, slack`

Полные причины: `TZ/EntityRegistry/appendix_tools_registry_22072026.md`

## Нюансы по aliases

- **Loop/Zulip:** единая сущность `loop` — aliases включают оба имени (loop, луп, лупп, zulip, зулип, mattermost, матермост). Loop = новый мессенджер ТУТУ на базе Mattermost; Zulip отключён.
- **DWH:** aliases = ["dwh", "дата-вархаус", "хранилище данных"]
- **Для коротких кириллических аббревиатур** — alias с точкой (startswith), не substring. Например "цу." а не "цу ".

## После изменения entities.json

```bash
cd ~/USERTOOLS/MarkObjectsFromSummary
source ~/USERTOOLS/ProtocolFromSummary/.venv/bin/activate

# dry-run по нужному периоду
mofs rematch --bucket tools --from 2025-01-01 --to 2026-12-31 --dry-run

# реальный прогон
mofs rematch --bucket tools --from 2025-01-01 --to 2026-12-31 --yes

# rebuild индекса
mofs-index index --rebuild --yes
mofs-index stats
```
