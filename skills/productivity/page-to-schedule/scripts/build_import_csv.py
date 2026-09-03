#!/usr/bin/env python3
"""Build GS import-profile CSV (8 columns) from extract + FIELD_MAP (C1)."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from complexity_duration import load_complexity_map, map_complexity
from working_calendar import holiday_window_warning, load_holidays, next_working_day, task_end_date

SKILL_ROOT = Path(__file__).resolve().parents[1]

IMPORT_HEADERS = [
  "No",
  "Название задачи",
  "Длительность",
  "Названия ресурсов",
  "Текст1",
  "Начало",
  "Окончание",
  "Предшественники",
]

DAYS_RU = {0: "пн", 1: "вт", 2: "ср", 3: "чт", 4: "пт", 5: "сб", 6: "вс"}


def fmt_date(d: date | str) -> str:
  """пн DD.MM.YY — copy of gantt_csv_to_gs.fmt_date logic."""
  if not d:
    return ""
  if isinstance(d, str):
    if not d.strip() or d.strip() in ("", "null"):
      return ""
    try:
      dt = datetime.fromisoformat(d.strip().replace(" ", "T"))
      d = dt.date()
    except ValueError:
      return d.strip()
  return DAYS_RU[d.weekday()] + " " + d.strftime("%d.%m.%y")


def fmt_dur(d: int | float | str) -> str:
  """день/дня/дней — copy of gantt_csv_to_gs.fmt_dur logic."""
  if d is None or str(d).strip() in ("", "0", "null"):
    return "0 дней"
  try:
    n = float(d)
    ni = int(n) if n == int(n) else round(n, 2)
    abs_n = abs(ni)
    if abs_n % 10 == 1 and abs_n % 100 != 11:
      word = "день"
    elif 2 <= abs_n % 10 <= 4 and not (12 <= abs_n % 100 <= 14):
      word = "дня"
    else:
      word = "дней"
    return f"{ni} {word}"
  except (TypeError, ValueError):
    return str(d)


def load_field_map(path: Path) -> dict[str, Any]:
  if not path.is_file():
    raise FileNotFoundError(f"FIELD_MAP not found: {path}")
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError("FIELD_MAP must be a mapping")
  return data


def read_extract_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
  with path.open(encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    headers = list(reader.fieldnames or [])
    rows = [dict(r) for r in reader]
  return headers, rows


def load_wbs(path: Path | None) -> dict[int, dict[str, Any]]:
  """Optional WBS tree from grok: task_no → {name, predecessors, is_summary, children}."""
  if path is None:
    return {}
  data = json.loads(path.read_text(encoding="utf-8"))
  tasks = data.get("tasks") or data
  out: dict[int, dict[str, Any]] = {}
  if isinstance(tasks, list):
    for t in tasks:
      no = int(t["no"])
      out[no] = t
  elif isinstance(tasks, dict):
    for k, t in tasks.items():
      out[int(k)] = t
  return out


def _col_value(row: dict[str, str], header: str) -> str:
  return (row.get(header) or "").strip()


def build_rows(
  extract_rows: list[dict[str, str]],
  field_map: dict[str, Any],
  cmap: dict[str, Any],
  start_date: date,
  resource_name: str,
  holidays: set[date],
  wbs: dict[int, dict[str, Any]] | None = None,
) -> tuple[list[list[str]], list[str]]:
  columns = field_map["columns"]
  feat_col = columns["feature"]
  gap_col = columns["gap"]
  cx_col = columns["complexity"]

  warnings: list[str] = []
  out: list[list[str]] = []
  end_by_no: dict[int, date] = {}
  cur_start = next_working_day(start_date, holidays)
  task_no = 1

  for row in extract_rows:
    name = _col_value(row, feat_col)
    if not name:
      continue
    gap = _col_value(row, gap_col)
    cx_label = _col_value(row, cx_col)
    duration = map_complexity(cx_label, cmap)

    wbs_entry = (wbs or {}).get(task_no, {})
    preds = str(wbs_entry.get("predecessors") or "").strip()
    is_summary = bool(wbs_entry.get("is_summary"))

    if preds:
      pred_dates: list[date] = []
      for part in preds.split(";"):
        part = part.strip()
        if not part:
          continue
        pno = int(part)
        if pno in end_by_no:
          pred_dates.append(end_by_no[pno])
      if pred_dates:
        cur_start = next_working_day(max(pred_dates) + timedelta(days=1), holidays)

    start = cur_start
    end = task_end_date(start, duration, holidays)
    end_by_no[task_no] = end

    warn = holiday_window_warning(start, end)
    if warn:
      warnings.append(warn)

    out.append([
      str(task_no),
      name,
      fmt_dur(duration),
      "" if is_summary else resource_name,
      gap,
      fmt_date(start),
      fmt_date(end),
      preds,
    ])

    cur_start = next_working_day(end + timedelta(days=1), holidays)
    task_no += 1

  # Summary rows: duration = sum of children
  if wbs:
    for no, entry in wbs.items():
      if not entry.get("is_summary"):
        continue
      children = entry.get("children") or []
      child_durations = 0
      child_starts: list[date] = []
      child_ends: list[date] = []
      for cno in children:
        cno = int(cno)
        for r in out:
          if r[0] == str(cno):
            # parse duration back from formatted string
            dur_part = r[2].split()[0]
            child_durations += int(float(dur_part))
            break
        if cno in end_by_no:
          child_ends.append(end_by_no[cno])
      for r in out:
        if r[0] == str(no):
          r[2] = fmt_dur(child_durations)
          r[3] = ""
          if child_starts and child_ends:
            r[5] = fmt_date(min(child_starts)) if child_starts else r[5]
            r[6] = fmt_date(max(child_ends)) if child_ends else r[6]
          break

  return out, warnings


def write_import_csv(path: Path, rows: list[list[str]]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(IMPORT_HEADERS)
    writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Build GS import CSV (8 columns)")
  parser.add_argument("--extract", type=Path, required=True)
  parser.add_argument("--field-map", type=Path, required=True)
  parser.add_argument(
    "--complexity-map",
    type=Path,
    default=SKILL_ROOT / "references" / "complexity-map.yaml",
  )
  parser.add_argument("--start-date", required=True, help="ISO YYYY-MM-DD")
  parser.add_argument("--resource-name", required=True)
  parser.add_argument("--wbs", type=Path, help="Optional WBS JSON from grok")
  parser.add_argument("--output", type=Path, required=True)
  args = parser.parse_args(argv)

  # Fail-loud before processing
  from check_field_map import check

  errors = check(args.field_map, args.complexity_map)
  if errors:
    for err in errors:
      print(err, file=sys.stderr)
    return 1

  field_map = load_field_map(args.field_map)
  cmap = load_complexity_map(args.complexity_map)
  holidays = load_holidays()
  _, extract_rows = read_extract_csv(args.extract)
  wbs = load_wbs(args.wbs)

  start = date.fromisoformat(args.start_date)
  resource = args.resource_name or field_map.get("resource_name") or ""

  rows, warnings = build_rows(
    extract_rows, field_map, cmap, start, resource, holidays, wbs,
  )
  write_import_csv(args.output, rows)

  for w in warnings:
    print(w, file=sys.stderr)
  print(args.output)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
