"""Unit tests for fot_budget.py."""
from __future__ import annotations

from fot_budget import budget_total, ceil_days, parse_hours, sum_work_hours


def test_parse_hours_80h():
  assert parse_hours("80.0 h") == 80.0


def test_ceil_days_fraction():
  assert ceil_days(361.875) == 362


def test_budget_fot_7506_hours_default_rate():
  hours = 7506.0
  vendor = 4_000_000.0
  assert budget_total(vendor, hours) == vendor + 7506 * 3000


def test_sum_work_hours():
  rows = [{"work": "80.0 h"}, {"work": "10.5 h"}]
  assert sum_work_hours(rows) == 90.5
