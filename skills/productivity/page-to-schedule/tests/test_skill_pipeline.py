"""Full pipeline tests for page-to-schedule (C2)."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PYTHON = sys.executable


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


@pytest.fixture
def mini_pack(tmp_path: Path, sample_field_map: Path) -> Path:
  """Minimal pack dir with extract CSV (no live pull/pack)."""
  pack = tmp_path / "Projects" / "Mini" / "docs" / "_inbox" / "feature_compare"
  extracts = pack / "extracts"
  extracts.mkdir(parents=True)
  (extracts / "p519489611__feature_compare.csv").write_text(
    "Название задачи,Текст1,Длительность\n"
    "Фича A,Gap A,1 неделя\n",
    encoding="utf-8",
  )
  field_map = pack / "FIELD_MAP.yaml"
  field_map.write_text(sample_field_map.read_text(encoding="utf-8"), encoding="utf-8")
  return pack


def test_cli_without_field_map_exits_nonzero(tmp_path: Path, complexity_map_path: Path):
  proc = subprocess.run(
    [
      PYTHON,
      str(SCRIPTS / "cli.py"),
      "run",
      "--slug", "Mini",
      "--task", "feature_compare",
      "--field-map", str(tmp_path / "missing.yaml"),
      "--complexity-map", str(complexity_map_path),
      "--skip-pull",
      "--skip-pack",
      "--workvault", str(tmp_path),
    ],
    capture_output=True,
    text=True,
  )
  assert proc.returncode != 0
  assert "FIELD_MAP" in proc.stderr or "not found" in proc.stderr.lower()


def test_pipeline_builds_eight_column_csv(
  mini_pack: Path,
  tmp_path: Path,
  complexity_map_path: Path,
):
  field_map = mini_pack / "FIELD_MAP.yaml"
  out = mini_pack / "import.csv"
  proc = subprocess.run(
    [
      PYTHON,
      str(SCRIPTS / "cli.py"),
      "run",
      "--slug", "Mini",
      "--task", "feature_compare",
      "--field-map", str(field_map),
      "--complexity-map", str(complexity_map_path),
      "--workvault", str(tmp_path),
      "--output", str(out),
      "--skip-pull",
      "--skip-pack",
    ],
    capture_output=True,
    text=True,
  )
  assert proc.returncode == 0, proc.stderr
  assert out.is_file()
  with out.open(encoding="utf-8") as f:
    reader = csv.reader(f)
    headers = next(reader)
    rows = list(reader)
  assert len(headers) == 8
  assert headers[0] == "No"
  assert headers[-1] == "Предшественники"
  assert len(rows) == 1


def test_import_range_h_n_plus_1():
  from push_import_gs import import_range

  assert import_range(0) == "A1:H1"
  assert import_range(1) == "A1:H2"
  assert import_range(10) == "A1:H11"


def test_read_import_csv_validates_columns(tmp_path: Path):
  from push_import_gs import read_import_values

  bad = tmp_path / "bad.csv"
  bad.write_text("a,b\n1,2\n", encoding="utf-8")
  with pytest.raises(ValueError, match="8 columns"):
    read_import_values(bad)

  good = tmp_path / "good.csv"
  good.write_text(
    "No,Название задачи,Длительность,Названия ресурсов,Текст1,Начало,Окончание,Предшественники\n"
    "1,T,5 дней,R,g,пн 07.09.26,пт 11.09.26,\n",
    encoding="utf-8",
  )
  rows = read_import_values(good)
  assert len(rows) == 2
  assert len(rows[0]) == 8


@pytest.mark.live
def test_push_import_gs_live_requires_oauth():
  """Live GS upload — only with VPN and explicit --push-gs; not in default pytest."""
  pytest.skip("live: run manually with --push-gs")
