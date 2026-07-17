---
name: mpp-to-google-sheets
description: "Read .mpp (MS Project) files and push them to Google Sheets via the MppReader USERTOOLS pipeline."
version: 1.2.0
tags: [mpp, microsoft-project, google-sheets, plan, gantt]
platforms: [linux]
---

# MPP → Google Sheets Pipeline

Converts Microsoft Project `.mpp` files into a formatted Google Sheets document
using the established USERTOOLS pipeline at `~/USERTOOLS/MppReader/`.

## Trigger conditions

- User sends a `.mpp` file and says «закинь в GS», «залей в таблицу», «в гуглшитс» etc.
- File may arrive with a `.zip` extension — Telegram/Hermes renames binary files.
  Always run `file <path>` first to confirm it's an MS Project file before processing.

## Environment

- **venv**: `/home/tkachenkoav/hermes-agent/.venv` (has `mpxj==16.4.0`, `jpype1==1.7.1`)
- **java**: `java-17-openjdk-headless` (required by mpxj/JPype)
- **Google token**: `~/.hermes/profiles/anthropic/google_token.json`
- **HERMES_HOME** must be set to `profiles/anthropic` for USERTOOLS scripts

## Supported fields (as of 2026-06-26)

`push_to_gs.py` outputs these columns:
`№`, `% завершения`, `Название задачи`, `Длительность`, `Названия ресурсов`, `Предшественники`, `Начало`, `Окончание`, `Отклонение окончания`, `Базовое окончание`, `Текст1`–`Текст6`

Row background colors are extracted from `GanttChartView.getTableFontStyles()` via `ColumnFontStyle.getBackgroundColor()` and applied to Google Sheets.
`read_mpp.py` outputs fields: `text1`–`text6`, `background_color` (hex, e.g. `#FFF200`) per task.

## Pipeline — 3 steps

### Step 1: Check file type

```bash
file /path/to/uploaded.file
```

If output contains `Composite Document File V2` + `Microsoft Project` → it's an `.mpp`.
Copy to a clean path with explicit stem:
```bash
cp "/path/to/uploaded.file" /tmp/my_plan.mpp
```

### Step 2: Read MPP → CSV

```bash
source /home/tkachenkoav/hermes-agent/.venv/bin/activate
python3 ~/USERTOOLS/MppReader/read_mpp.py /tmp/my_plan.mpp --format csv --out /tmp/my_plan
```

Produces a **subdirectory** named after the stem inside `--out`:
- `/tmp/my_plan/my_plan__tasks.csv`  ← includes `background_color`, `text1`–`text6` fields
- `/tmp/my_plan/my_plan__assignments.csv`
- `/tmp/my_plan/my_plan__resources.csv`

⚠️ CSV files land inside a **subdirectory**, NOT directly in `/tmp/`. Pass `--dir /tmp/my_plan` to `push_to_gs.py`.

The JVM startup log line `Log4j API could not find a logging provider` is normal — not an error.

### Step 3: Push to Google Sheets

```bash
HERMES_HOME=/home/tkachenkoav/.hermes/profiles/anthropic \
python3 ~/USERTOOLS/MppReader/push_to_gs.py my_plan \
  --dir /tmp/my_plan \
  --title 'DOCUMENT TITLE HERE' \
  --mpp /tmp/my_plan.mpp
```

> `--dir` must point to the **subdirectory** created by `read_mpp.py`, not its parent.

`push_to_gs.py` will:
- Extract predecessors directly from MPP (more accurate than CSV)
- Read row background colors from `GanttChartView.getTableFontStyles()` (via `read_mpp.py`)
- Create a new GS document with the given title (appends `-2`, `-3` if name taken)
- Apply formatting: Calibri 11 base, frozen header, bold summaries, Calibri 16 level-1 summaries
- Apply **row background colors** from MPP (e.g. yellow `#FFF200`)
- Share with `tkachenkoav@tutu.ru` and `i.alex.tkachenko@gmail.com` (writer)
- Print `READY:<url>` on success

### Output

```
Извлекаю predecessors из MPP...
Создаю новый GS документ 'ND ML платформа ...'...
Документ создан: <file_id>
Заливаю N строк...
Раздаю права: tkachenkoav@tutu.ru...
Раздаю права: i.alex.tkachenko@gmail.com...
READY:https://docs.google.com/spreadsheets/d/<id>/edit
```

Send the `READY:` URL to the user.

## Output columns (Google Sheets)

| # | Column | Source |
|---|--------|--------|
| A | № | row number |
| B | % завершения | `percent_complete` |
| C | Название задачи | `name` |
| D | Длительность | `duration` |
| E | Названия ресурсов | from assignments |
| F | Предшественники | from MPP directly (accurate) |
| G | Начало | `start` |
| H | Окончание | `finish` |
| I | Отклонение окончания | hardcoded «0 дней» |
| J | Базовое окончание | hardcoded «НД» |
| K | Текст1 | custom field `TEXT1` |
| L | Текст2 | custom field `TEXT2` |
| M | Текст3 | custom field `TEXT3` |
| N | Текст4 | custom field `TEXT4` |
| O | Текст5 | custom field `TEXT5` |
| P | Текст6 | custom field `TEXT6` |

Row background colors from MPP are applied to matching rows.

## Title convention

Use the original filename (minus extension and `— копия` suffix) as the title.
Example: `ND_ML_платформа_Ресурсы_План_внедрения_v_1_5_260626` → `ND ML платформа Ресурсы План внедрения v1.5 260626`

## Pitfalls

- **File arrives as `.zip`**: Telegram saves binary attachments with `.zip`. Run `file` to confirm
  it's an MS Project Composite Document before processing. Extension doesn't matter to `mpxj`.
- **Google token expired**: `push_to_gs.py` raises `invalid_grant`. Token at
  `~/.hermes/profiles/anthropic/google_token.json` needs re-auth via `google-workspace` skill.
  After re-auth via `$GSETUP --auth-code "..."`, also copy: `cp ~/.hermes/google_token.json ~/.hermes/profiles/anthropic/google_token.json`
- **`$GSETUP --check` says NOT_AUTHENTICATED**: It reads `~/.hermes/google_token.json` (default profile),
  not the `profiles/anthropic` path. This is expected — don't rely on `--check` to verify the pipeline token.
- **`--services` / `--format json` not supported by setup.py**: Run `$GSETUP --auth-url` without extra flags.
- **Stem must match CSV filenames**: `push_to_gs.py stem --dir /tmp/stem` looks for `/tmp/stem/stem__tasks.csv`.
  Keep the stem consistent between `read_mpp.py --out` and `push_to_gs.py`, and point `--dir` at the subdirectory.
- **Row colors come from GanttChartView, not TaskField**: `TaskField` has no color fields. Colors are in
  `GanttChartView.getTableFontStyles()` → `ColumnFontStyle.getBackgroundColor()`, keyed by task `UniqueID` (not `ID`).
  White (`#FFFFFF`) is filtered out as it's a default/empty style artifact. See `references/mpxj-color-research.md`.

## Other scripts in MppReader

| Script | Purpose |
|--------|---------|
| `read_mpp.py` | Read .mpp → JSON/CSV via mpxj (includes background_color, text1–text6) |
| `push_to_gs.py` | CSV + MPP → new Google Sheets doc (full pipeline, applies row colors) |
| `mpp_to_gs_xlsx.py` | .mpp → .xlsx in GS template format (local file, no upload) |
| `extract_predecessors.py` | Extract task predecessors with type+lag from MPP |
| `gantt_csv_to_gs.py` | Push existing Gantt CSV to GS |

## References

- `references/mpxj-color-research.md` — how row background colors are stored in MPP and read via mpxj
- `references/google-sheets-api-pitfalls.md` — GS API quirks: locale-dependent sheet name («Лист1» vs «Sheet1»), empty columns dropped by `sheets get`
