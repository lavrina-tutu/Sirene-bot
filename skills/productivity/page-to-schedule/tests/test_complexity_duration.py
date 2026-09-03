"""complexity_duration unit tests (C1)."""
from __future__ import annotations

import pytest
import yaml

from complexity_duration import load_complexity_map, map_complexity

@pytest.fixture
def cmap(complexity_map_path):
  return load_complexity_map(complexity_map_path)


def test_one_week_five_days(cmap):
  assert map_complexity("1 неделя", cmap) == 5


def test_less_than_week_three_days(cmap):
  assert map_complexity("менее 1 недели", cmap) == 3


def test_one_two_weeks_ten_days(cmap):
  assert map_complexity("1–2 недели", cmap) == 10
  assert map_complexity("1-2 недели", cmap) == 10


def test_empty_fails(cmap):
  with pytest.raises(ValueError, match="empty"):
    map_complexity("", cmap)
  with pytest.raises(ValueError, match="empty"):
    map_complexity("   ", cmap)


def test_unknown_fails(cmap):
  with pytest.raises(ValueError, match="unknown"):
    map_complexity("2 недели", cmap)
