"""facts_script: script_only extraction."""
from __future__ import annotations

from pathlib import Path

from deepmine.facts_script import extract_dates, extract_jira, extract_sums
from deepmine.project_config import load_project_config

FIXTURES = Path(__file__).parent / "fixtures" / "gantt"
L0_ITOGO = FIXTURES / "l0_itogo.md"


def test_extract_dates_time_tag():
  body = '<time datetime="2026-09-07">7 сентября</time>'
  dates = extract_dates(body, "519492770")
  assert any(d["value"] == "2026-09-07" for d in dates)


def test_extract_jira():
  body = "See https://hq.tutu.ru/browse/PROJ-123"
  keys = extract_jira(body, "1")
  assert keys[0]["key"] == "PROJ-123"


def test_extract_sums_from_itogo():
  body = L0_ITOGO.read_text(encoding="utf-8")
  sums = extract_sums(body, "519492770", rate_rub_per_hour=3000)
  labels = {s["label"] for s in sums}
  assert "effort_hours" in labels
  assert "cost_rub" in labels


def test_build_script_only(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  from deepmine.manifest import load_manifest
  from deepmine.facts_script import build_script_only

  manifest = load_manifest(mini_overlay, slug="TestProject")
  data = build_script_only(cfg, manifest.pages, mini_overlay, mini_workvault)
  assert "dates" in data
  assert "meta" in data
