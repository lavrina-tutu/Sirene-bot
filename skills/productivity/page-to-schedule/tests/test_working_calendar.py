"""working_calendar unit tests (C1)."""
from __future__ import annotations

from datetime import date

import pytest

from working_calendar import (
  add_working_days,
  ceil_days,
  holiday_window_warning,
  is_working_day,
  load_holidays,
  next_working_day,
)

@pytest.fixture
def holidays(holidays_path):
  return load_holidays(holidays_path)


def test_new_year_not_working(holidays):
  assert not is_working_day(date(2026, 1, 1), holidays)


def test_start_on_holiday_shifts(holidays):
  # 2026-01-01 is holiday → next working day is 2026-01-09 (Fri) per RF calendar
  shifted = next_working_day(date(2026, 1, 1), holidays)
  assert shifted == date(2026, 1, 9)
  assert is_working_day(shifted, holidays)


def test_add_five_working_days_from_monday(holidays):
  # 2026-09-07 is Monday
  start = date(2026, 9, 7)
  end = add_working_days(start, 5, holidays)
  assert end == date(2026, 9, 11)  # Fri


def test_ceil_fractional():
  assert ceil_days(361.875) == 362
  assert ceil_days(5.0) == 5
  assert ceil_days(5.1) == 6


def test_holiday_window_warning():
  w = holiday_window_warning(date(2026, 12, 30), date(2027, 1, 5))
  assert w is not None
  assert "новогоднее" in w.lower() or "31.12" in w


def test_no_warning_outside_window():
  assert holiday_window_warning(date(2026, 9, 1), date(2026, 9, 15)) is None
