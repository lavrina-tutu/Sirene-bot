"""FOT and budget helpers for charter fill (no LLM)."""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path


_HOURS_RE = re.compile(r"^([\d.]+)")


def parse_hours(value: str | None) -> float:
  """Parse MPP assignments work column, e.g. ``\"80.0 h\"`` → 80.0."""
  v = (value or "").strip()
  m = _HOURS_RE.match(v)
  return float(m.group(1)) if m else 0.0


def sum_work_hours(rows: list[dict[str, str]], *, column: str = "work") -> float:
  return sum(parse_hours(row.get(column)) for row in rows)


def ceil_days(value: float) -> int:
  return math.ceil(value)


def budget_total(
  vendor_rub: float,
  hours: float,
  *,
  rate_rub_per_hour: float = 3000.0,
) -> float:
  """Budget = external vendor contract + internal FOT (rate × hours)."""
  return vendor_rub + rate_rub_per_hour * hours


def load_assignments_csv(path: Path) -> list[dict[str, str]]:
  with path.open(encoding="utf-8", newline="") as fh:
    return list(csv.DictReader(fh))
