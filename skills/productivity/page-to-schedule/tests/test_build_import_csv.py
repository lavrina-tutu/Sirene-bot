"""build_import_csv unit tests (C1)."""
from __future__ import annotations

import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

from build_import_csv import IMPORT_HEADERS, build_rows, fmt_date, fmt_dur, write_import_csv
from check_field_map import main as check_main
from complexity_duration import load_complexity_map
from working_calendar import load_holidays

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PYTHON = sys.executable


@pytest.fixture
def sample_extract(tmp_path: Path) -> Path:
  p = tmp_path / "extract.csv"
  p.write_text(
    "Название задачи,Текст1,Длительность\n"
    "Фича A,Gap A,1 неделя\n"
    "Фича B,Gap B,менее 1 недели\n",
    encoding="utf-8",
  )
  return p


@pytest.fixture
def sample_field_map(tmp_path: Path) -> Path:
  p = tmp_path / "FIELD_MAP.yaml"
  data = {
    "source_page_id": "519489611",
    "columns": {
      "feature": "Название задачи",
      "gap": "Текст1",
      "complexity": "Длительность",
    },
    "resource_name": "Гладких Юрий",
    "start_date": "2026-09-07",
  }
  p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
  return p


def test_fmt_dur_grammar():
  assert fmt_dur(1) == "1 день"
  assert fmt_dur(2) == "2 дня"
  assert fmt_dur(5) == "5 дней"
  assert fmt_dur(11) == "11 дней"


def test_fmt_date_weekday():
  s = fmt_date(date(2026, 9, 7))
  assert s.startswith("пн ")
  assert "07.09.26" in s


def test_eight_columns_order(sample_extract, sample_field_map, complexity_map_path, holidays_path):
  cmap = load_complexity_map(complexity_map_path)
  holidays = load_holidays(holidays_path)
  field_map = yaml.safe_load(sample_field_map.read_text(encoding="utf-8"))
  from build_import_csv import read_extract_csv

  _, rows_in = read_extract_csv(sample_extract)
  rows, _ = build_rows(
    rows_in,
    field_map,
    cmap,
    date(2026, 9, 7),
    "Гладких Юрий",
    holidays,
  )
  assert len(rows) == 2
  assert rows[0][0] == "1"
  assert "день" in rows[0][2] or "дня" in rows[0][2] or "дней" in rows[0][2]
  assert rows[0][5].startswith("пн ")


def test_write_csv_headers(tmp_path, sample_extract, sample_field_map, complexity_map_path, holidays_path):
  out = tmp_path / "out.csv"
  cmap = load_complexity_map(complexity_map_path)
  holidays = load_holidays(holidays_path)
  field_map = yaml.safe_load(sample_field_map.read_text(encoding="utf-8"))
  from build_import_csv import read_extract_csv

  _, rows_in = read_extract_csv(sample_extract)
  rows, _ = build_rows(
    rows_in, field_map, cmap, date(2026, 9, 7), "Гладких Юрий", holidays,
  )
  write_import_csv(out, rows)
  with out.open(encoding="utf-8") as f:
    reader = csv.reader(f)
    headers = next(reader)
  assert headers == IMPORT_HEADERS


def test_check_field_map_missing_fails(tmp_path):
  rc = check_main(["--field-map", str(tmp_path / "missing.yaml")])
  assert rc != 0


def test_build_cli_without_field_map_fails(sample_extract, complexity_map_path, tmp_path):
  out = tmp_path / "out.csv"
  proc = subprocess.run(
    [
      PYTHON,
      str(SCRIPTS / "build_import_csv.py"),
      "--extract", str(sample_extract),
      "--field-map", str(tmp_path / "nope.yaml"),
      "--complexity-map", str(complexity_map_path),
      "--start-date", "2026-09-07",
      "--resource-name", "Test",
      "--output", str(out),
    ],
    capture_output=True,
    text=True,
  )
  assert proc.returncode != 0
  assert not out.exists()
