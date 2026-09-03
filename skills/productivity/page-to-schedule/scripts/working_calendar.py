#!/usr/bin/env python3
"""Working calendar: Mon–Fri minus RF holidays (C1)."""
from __future__ import annotations

import argparse
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOLIDAYS = SKILL_ROOT / "references" / "rf-holidays.yaml"


def load_holidays(path: Path = DEFAULT_HOLIDAYS) -> set[date]:
  if not path.is_file():
    raise FileNotFoundError(f"holidays file not found: {path}")
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  out: set[date] = set()
  for year_dates in (data.get("years") or {}).values():
    for raw in year_dates or []:
      out.add(date.fromisoformat(str(raw)))
  return out


def is_working_day(d: date, holidays: set[date]) -> bool:
  return d.weekday() < 5 and d not in holidays


def next_working_day(d: date, holidays: set[date]) -> date:
  """First working day on or after d."""
  cur = d
  while not is_working_day(cur, holidays):
    cur += timedelta(days=1)
  return cur


def add_working_days(start: date, n: int, holidays: set[date]) -> date:
  """
  Add n working days to start (inclusive counting).
  n=1 → start if working, else next working day.
  n=5 from Mon → Fri.
  """
  if n <= 0:
    return next_working_day(start, holidays)
  cur = next_working_day(start, holidays)
  remaining = n - 1
  while remaining > 0:
    cur += timedelta(days=1)
    if is_working_day(cur, holidays):
      remaining -= 1
  return cur


def task_end_date(start: date, duration_days: int, holidays: set[date]) -> date:
  """End date for inclusive working-day duration."""
  if duration_days <= 0:
    return next_working_day(start, holidays)
  return add_working_days(start, duration_days, holidays)


def ceil_days(value: float) -> int:
  """361.875 → 362."""
  return int(math.ceil(value))


def holiday_window_warning(start: date, end: date) -> str | None:
  """
  Warn if task interval crosses New Year window 31.12–08.01.
  Returns warning string or None.
  """
  years = {start.year, end.year}
  for year in years:
    window_start = date(year, 12, 31)
    window_end = date(year + 1, 1, 8)
    if start <= window_end and end >= window_start:
      return (
        f"Задача {start.isoformat()}–{end.isoformat()} пересекает "
        f"новогоднее окно {window_start.isoformat()}–{window_end.isoformat()}"
      )
  return None


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Working calendar helpers")
  sub = parser.add_subparsers(dest="cmd", required=True)

  p_add = sub.add_parser("add", help="Add working days")
  p_add.add_argument("start", help="ISO start date")
  p_add.add_argument("days", type=int)

  p_ceil = sub.add_parser("ceil", help="Ceil fractional days")
  p_ceil.add_argument("value", type=float)

  p_warn = sub.add_parser("warn", help="Holiday window warning")
  p_warn.add_argument("start")
  p_warn.add_argument("end")

  args = parser.parse_args(argv)
  holidays = load_holidays()

  if args.cmd == "add":
    result = add_working_days(date.fromisoformat(args.start), args.days, holidays)
    print(result.isoformat())
    return 0
  if args.cmd == "ceil":
    print(ceil_days(args.value))
    return 0
  if args.cmd == "warn":
    w = holiday_window_warning(date.fromisoformat(args.start), date.fromisoformat(args.end))
    print(w or "")
    return 0
  return 2


if __name__ == "__main__":
  raise SystemExit(main())
