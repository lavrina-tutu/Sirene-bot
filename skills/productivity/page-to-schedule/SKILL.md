---
name: page-to-schedule
description: "Use when: план-график из страницы Confluence, залей фичи в GS как mpp, pageId сравнения фич, FIELD_MAP, словарь сложности. Не пишет .mpp; полный пайплайн pull→pack→CSV→GS."
version: 0.3.0
platforms: [linux]
metadata:
  hermes:
    related_skills: [deep-mine-project, google-workspace, tutu-confluence-jira]
---

# page-to-schedule

План-график из Confluence-страницы → Google Sheets (профиль import, 8 колонок). **Не пишет .mpp.** Grok **не** переводит сложность в дни и **не** считает календарь.

## When to Use

- «план-график из страницы», «залей фичи в GS как mpp»
- pageId сравнения фич (`514903239`, `519489611`, …)
- нужен `FIELD_MAP.yaml` + `complexity-map.yaml` **до** любого grok

**Don't use:** экспорт из .mpp (`read-mpp` / MppReader `push_to_gs` export); патч секции устава (`pmo-charter-fill` / `tutu-confluence-jira`).

## Stop conditions (fail-loud)

Шаг 0 — **до** `agent -p` и до pull/pack:

1. `FIELD_MAP.yaml` — см. `references/FIELD_MAP.template.yaml`
2. `complexity-map.yaml` — см. `references/complexity-map.yaml` (пустая сложность → ошибка)

Без FIELD_MAP CLI завершается с exit ≠ 0; grok не вызывается.

## Полный пайплайн (C2)

| Шаг | Действие | Кто |
|-----|----------|-----|
| 0 | `check_field_map.py` | скрипт |
| 1 | `confluencesync pull <pageId> --no-recursive --resync` | скрипт |
| 2 | `deep_mine.py pack --slug <Slug> --task <task_id>` | скрипт |
| 3 | CSV-экстракт таблицы из pack `extracts/` | скрипт (A1) |
| — | **стоп**, если нет FIELD_MAP | — |
| 4 | Grok **опционально**: только WBS/summary-имена/предшественники → `wbs.json` | архитектор |
| 5 | `build_import_csv.py` → 8 колонок | скрипт |
| 6 | `push_import_gs.py` → лист `Лист1`, `A1:H<N+1>` | скрипт (live) |

Оркестрация одной командой:

```bash
~/hermes-agent/.venv/bin/python3 \
  ~/hermes-workspace/skills/productivity/page-to-schedule/scripts/cli.py \
  run --slug TrisigmaFull --task feature_compare \
  --field-map ~/WorkVault/Projects/TrisigmaFull/docs/_inbox/feature_compare/FIELD_MAP.yaml
```

С заливкой GS (live, только по явной команде):

```bash
... cli.py run ... --push-gs --gs-title "План фич Trisigma" \
  --share user@example.com
```

`--share` — параметр CLI, **не** хардкодить email в скилле. OAuth reuse `MppReader/push_to_gs.py` `get_services()` / `~/.hermes/profiles/default/google_token.json`.

## Complexity → duration (скрипт, не grok)

| Сложность на странице | Дни |
|---|---|
| менее 1 недели | 3 |
| 1 неделя | 5 |
| 1–2 недели (и `1-2 недели`) | 10 |
| пусто | **fail-loud** |

## Канон GS import

8 колонок: `No | Название задачи | Длительность | Названия ресурсов | Текст1 | Начало | Окончание | Предшественники`

- Длительность: `N день/дня/дней` (`gantt_csv_to_gs.fmt_dur`)
- Даты: `пн DD.MM.YY`
- Лист: **`Лист1`**, диапазон `A1:H<N+1>`

См. `references/gs-columns-canon.md`.

## Отдельные скрипты

```bash
# шаг 0
python3 .../scripts/check_field_map.py --field-map FIELD_MAP.yaml

# шаг 5
python3 .../scripts/build_import_csv.py \
  --extract extracts/table.csv --field-map FIELD_MAP.yaml \
  --start-date 2026-09-07 --resource-name "Гладких Юрий" \
  --output import.csv
# опционально: --wbs wbs.json

# шаг 6 (live)
python3 .../scripts/push_import_gs.py import.csv --title "..." --share email@tutu.ru
```

## Prerequisites

- `deep-mine-project` pack `--task` с CSV-экстрактом (A1)
- VPN для Confluence pull
- OAuth Google Sheets (`google-workspace` / MppReader token)

## References

| File | Purpose |
|---|---|
| `references/FIELD_MAP.template.yaml` | шаблон маппинга |
| `references/complexity-map.yaml` | словарь сложность → дни |
| `references/gs-columns-canon.md` | import 8 кол. + export |
| `references/rf-holidays.yaml` | праздники РФ 2026–2028 |
