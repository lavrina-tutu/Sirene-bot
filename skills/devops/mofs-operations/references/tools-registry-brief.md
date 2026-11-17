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


# Material moved from MOFS SKILL.md

> История исходника (даты указаны внутри), не текущая инструкция; актуальные условия — в SKILL.md.

## Пополнение entities.json — паттерн брифа tools (22.07.2026)

Когда нужно решить какие инструменты добавить в реестр — сначала посчитать реальную частоту по архиву, потом брифовать по убыванию:

```bash
python3 -c "
import glob, re
from collections import Counter
tools_patterns = {
    'jira': r'\bjira\b|\bджира\b',
    'confluence': r'\bconfluence\b|\bконфлюенс\b',
    # ... и т.д.
}
counts = Counter()
for f in glob.glob('/home/tkachenkoav/WorkVault/Meetings/NewMeetings/*summary.md'):
    content = open(f).read().lower()
    for tool, pattern in tools_patterns.items():
        if re.search(pattern, content, re.IGNORECASE):
            counts[tool] += 1
for tool, cnt in counts.most_common():
    print(f'{cnt:4d} встреч — {tool}')
"
```

**Формат брифа:** один инструмент — одно сообщение. `1` = добавить, `2` = нет. По убыванию частоты. Стоп-лист исключённых сохранять в `TZ/EntityRegistry/appendix_tools_registry_YYYYMMDD.md` с таблицей «Приложения» в ТЗ сверху.

**Стоп-лист (нельзя без явного решения Саши):** python, docker, mlflow, redis, postgres, dbt, jenkins, gitlab, superset, slack. Полный список: `TZ/EntityRegistry/appendix_tools_registry_22072026.md`.

Массовый NER-прогон по архиву 563 самари → кандидаты на новые сущности.

**LLM для NER-прогона:** конфиг из `~/.hermes/config.yaml` (OpenAI-клиент к `llm-gateway.tutu.ru`), last-resort `LLM_FALLBACK_*`; `ANTHROPIC_API_KEY` не используется.
~3.3М токенов на весь архив → оценка ~$3-4 суммарно (зависит от выбранной модели в конфиге).

## Tools — брифовые решения (22.07.2026)

В реестре `entities.json` корзина tools — полный список после брифа с Сашей по 575 встречам архива:

| slug | Название | Встреч | aliases |
|---|---|---|---|
| `omd` | OMD (OpenMetaData) | 15 | omd, openmetadata, кумд |
| `jira` | Jira | 128 | jira, джира |
| `confluence` | Confluence | 96 | confluence, конфлюенс |
| `metabase` | Metabase | 68 | metabase, метабейс |
| `clickhouse` | ClickHouse | 55 | clickhouse, кликхаус |
| `loop` | Loop (Mattermost) | 50 | loop, луп, лупп, zulip, зулип, mattermost, матермост |
| `dwh` | DWH | 38 | dwh, дата-вархаус, хранилище данных |
| `cursor` | Cursor | 26 | cursor, курсор |
| `kubernetes` | Kubernetes | 23 | kubernetes, k8s, кубер |
| `airflow` | Apache Airflow | 16 | airflow, эйрфлоу |
| `kafka` | Apache Kafka | 11 | kafka, кафка |
| `grafana` | Grafana | 10 | grafana, графана |
| `s3` | S3 / MinIO | 9 | s3, minio, минио |

**Исключены навсегда** (не добавлять без решения Саши): python, docker, mlflow, redis, postgres, dbt, jenkins, gitlab, superset, slack.
Полный список с причинами: `TZ/EntityRegistry/appendix_tools_registry_22072026.md`.

**Loop = Zulip:** Loop — новый корпоративный мессенджер ТУТУ на базе Mattermost. Zulip отключён, но встречается в старых встречах — оба слова в aliases одной сущности `loop`.

После изменения entities.json — `mofs rematch --bucket tools --from 2026-07-01 --dry-run` чтобы проверить, затем реальный прогон.
