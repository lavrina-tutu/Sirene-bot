# MPP Row Background Colors via mpxj

## Summary

Row background colors in MS Project are readable via mpxj, but NOT through `TaskField`.
They live in `GanttChartView.getTableFontStyles()`.

## How colors are stored in MPP

- **Not** in `TaskField` — iterating all 1009 TaskField values yields only `Hide Bar` and `Bar Name` as color-adjacent fields; neither carries row color.
- **Not** in custom Text/Flag/Number fields (Text1–Text30, Flag1–Flag20, etc.)
- **Location**: `GanttChartView` → `getTableFontStyles()` → list of `ColumnFontStyle` objects

## Working code

```python
from collections import Counter

def _collect_background_colors(project) -> dict[int, str]:
    """Returns {task_unique_id: "#RRGGBB"}"""
    per_task: dict[int, Counter] = {}
    try:
        views = list(project.getViews() or [])
    except Exception:
        return {}
    for v in views:
        try:
            cls_name = v.getClass().getName()
        except Exception:
            continue
        if "GanttChartView" not in cls_name:
            continue
        try:
            tfs = v.getTableFontStyles()
        except Exception:
            tfs = None
        if not tfs:
            continue
        for s in list(tfs):
            try:
                uid = s.getRowUniqueID()
                bg = s.getBackgroundColor()
            except Exception:
                continue
            if uid is None or bg is None:
                continue
            try:
                rgb = (int(bg.getRed()), int(bg.getGreen()), int(bg.getBlue()))
            except Exception:
                continue
            if rgb == (255, 255, 255):
                continue  # default/empty style artifact
            per_task.setdefault(int(uid), Counter())[rgb] += 1
    out: dict[int, str] = {}
    for uid, c in per_task.items():
        rgb = c.most_common(1)[0][0]
        out[uid] = "#{:02X}{:02X}{:02X}".format(*rgb)
    return out
```

## Key details

- Key is **UniqueID** (not ID). `ColumnFontStyle.getRowUniqueID()` returns the task's UID.
- Multiple `ColumnFontStyle` entries can exist per task (one per column). Counter picks the most common color.
- `#FFFFFF` is filtered — it appears as a default artifact in styles that don't explicitly set a background.
- In ND ML plan: 29 tasks had colors — mostly `#FFF200` (bright yellow), some `#FFFF00`.
- `UniversalProjectReader` works fine; no need for low-level `MPPReader`.

## Applying in Google Sheets

In `push_to_gs.py`, after collecting `row_formats = [(row_num, outline_level, is_summary, bg_hex), ...]`:

```python
if bg_hex:
    r = int(bg_hex[1:3], 16) / 255
    g = int(bg_hex[3:5], 16) / 255
    b = int(bg_hex[5:7], 16) / 255
    fmt_requests.append({"repeatCell": {
        "range": {"sheetId": sheet_id,
                  "startRowIndex": gs_row, "endRowIndex": gs_row + 1},
        "cell": {"userEnteredFormat": {
            "backgroundColor": {"red": r, "green": g, "blue": b}
        }},
        "fields": "userEnteredFormat.backgroundColor"
    }})
```

## Text fields (Text1–Text6)

Custom MS Project text fields are read via:
```python
from org.mpxj import TaskField
# Must be imported inside the function AFTER JVM start
val = _to_str(t.get(TaskField.valueOf("TEXT1")))
```

`TaskField.valueOf("TEXT1")` through `TEXT6` all work. Values are plain strings, max 500 chars recommended.
