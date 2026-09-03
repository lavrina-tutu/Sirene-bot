"""C0 contracts: FIELD_MAP, complexity-map, gs-columns canon, rf-holidays."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

SKILL_ROOT = Path(__file__).resolve().parents[1]
REFS = SKILL_ROOT / "references"

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


def _load_yaml(name: str) -> dict:
  path = REFS / name
  assert path.is_file(), f"missing {name}"
  return yaml.safe_load(path.read_text(encoding="utf-8"))


def _normalize_label(s: str) -> str:
  return " ".join(s.strip().lower().split())


def resolve_complexity(label: str, cmap: dict) -> int:
  """Resolve complexity label to days; empty → ValueError."""
  if not label or not str(label).strip():
    raise ValueError("empty complexity label")
  norm = _normalize_label(str(label))
  for entry in cmap.get("entries") or []:
    for raw in entry.get("labels") or []:
      if _normalize_label(raw) == norm:
        days = entry.get("days")
        if days is None:
          raise ValueError(f"no days for label {label!r}")
        return int(days)
  raise ValueError(f"unknown complexity label: {label!r}")


def test_yaml_files_load():
  _load_yaml("FIELD_MAP.template.yaml")
  _load_yaml("complexity-map.yaml")
  _load_yaml("rf-holidays.yaml")


def test_complexity_map_three_keys():
  cmap = _load_yaml("complexity-map.yaml")
  assert resolve_complexity("менее 1 недели", cmap) == 3
  assert resolve_complexity("1 неделя", cmap) == 5
  assert resolve_complexity("1-2 недели", cmap) == 10
  assert resolve_complexity("1–2 недели", cmap) == 10


def test_complexity_empty_label_fails():
  cmap = _load_yaml("complexity-map.yaml")
  with pytest.raises(ValueError, match="empty"):
    resolve_complexity("", cmap)
  with pytest.raises(ValueError, match="empty"):
    resolve_complexity("   ", cmap)


def test_import_profile_eight_headers_in_canon_order():
  canon = (REFS / "gs-columns-canon.md").read_text(encoding="utf-8")
  for h in IMPORT_HEADERS:
    assert h in canon
  # порядок в документе: No перед Название, Предшественники последний из восьми
  positions = [canon.index(h) for h in IMPORT_HEADERS]
  assert positions == sorted(positions)


def test_holidays_contain_new_year_dates():
  data = _load_yaml("rf-holidays.yaml")
  all_dates: set[str] = set()
  for year_dates in (data.get("years") or {}).values():
    all_dates.update(year_dates)
  assert "2026-01-01" in all_dates
  assert "2027-01-01" in all_dates
