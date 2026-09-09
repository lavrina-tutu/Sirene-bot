"""Gantt-JSON plan source: CSV export, cost, config, digest key."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from deepmine.attachments import WHITELIST_EXT, is_whitelisted
from deepmine.fail import ValidationError
from deepmine.models import Manifest
from deepmine.mpp_run import (
  EFFORT_SOURCE_L0,
  PLAN_DIGEST_KEY,
  export_plan,
  find_plan_source,
  gantt_to_csv,
  get_plan_digest,
  parse_l0_itogo,
  register_plan_in_manifest,
)
from deepmine.project_config import (
  default_trisigma_yaml,
  validate_project_config,
)

FIXTURES = Path(__file__).parent / "fixtures" / "gantt"
MINI_GANTT = FIXTURES / "mini.json"
L0_ITOGO = FIXTURES / "l0_itogo.md"


def test_whitelist_includes_json():
  assert ".json" in WHITELIST_EXT
  assert is_whitelisted("gantt-chart-abc.json", set())
  assert is_whitelisted("notes.pdf", set()) is False


def test_parse_l0_itogo_hours():
  totals = parse_l0_itogo(L0_ITOGO.read_text(encoding="utf-8"))
  assert totals.effort_hours == 6512.0
  assert totals.duration_days == 252.0
  assert totals.start_date == "2026-09-07"
  assert totals.end_date == "2027-09-13"


def test_gantt_to_csv_and_cost(tmp_path: Path):
  csv_triple = gantt_to_csv(
    MINI_GANTT, tmp_path, rate_rub_per_hour=3000, l0_page=L0_ITOGO
  )
  assert csv_triple.kind == "gantt"
  assert csv_triple.tasks is not None
  assert csv_triple.resources is not None
  assert csv_triple.assignments is not None
  assert csv_triple.effort_hours == 6512.0
  assert csv_triple.cost_rub == 19_536_000.0
  assert csv_triple.effort_source == "l0-page-total"
  assert csv_triple.duration_days == 252.0
  assert csv_triple.start_date == "2026-09-07"
  assert csv_triple.end_date == "2027-09-13"
  assert csv_triple.summary_path is not None and csv_triple.summary_path.is_file()

  with csv_triple.tasks.open(encoding="utf-8") as fh:
    tasks = list(csv.DictReader(fh))
  assert len(tasks) == 3
  leaves = [r for r in tasks if r["summary"] != "True"]
  assert {r["name"] for r in leaves} == {"Leaf A", "Leaf B"}
  leaf_a = next(r for r in leaves if r["name"] == "Leaf A")
  assert float(leaf_a["cost_rub"]) == 8 * 3000
  leaf_b = next(r for r in leaves if r["name"] == "Leaf B")
  assert json.loads(leaf_b["predecessors"]) == [2]

  with csv_triple.resources.open(encoding="utf-8") as fh:
    resources = list(csv.DictReader(fh))
  assert resources[0]["name"] == "Alice"

  with csv_triple.assignments.open(encoding="utf-8") as fh:
    assignments = list(csv.DictReader(fh))
  assert assignments[0]["task_id"] == "2"
  assert assignments[0]["resource_name"] == "Alice"

  summary = json.loads(csv_triple.summary_path.read_text(encoding="utf-8"))
  assert summary["effort_hours"] == 6512.0
  assert summary["cost_rub"] == 19_536_000.0
  assert summary["effort_source"] == "l0-page-total"
  assert summary["rate_rub_per_hour"] == 3000
  assert summary["duration_days"] == 252.0


def test_gantt_to_csv_fail_loud_without_l0(tmp_path: Path):
  from deepmine.fail import MppError

  with pytest.raises(MppError, match="L0 page"):
    gantt_to_csv(MINI_GANTT, tmp_path, rate_rub_per_hour=3000)


def test_gantt_to_csv_fail_loud_without_itogo_number(tmp_path: Path):
  from deepmine.fail import MppError

  l0 = tmp_path / "index.md"
  l0.write_text("# no totals here\n", encoding="utf-8")
  with pytest.raises(MppError, match="Трудозатраты"):
    gantt_to_csv(MINI_GANTT, tmp_path / "out", rate_rub_per_hour=3000, l0_page=l0)


def test_find_plan_source_prefers_gantt_json(tmp_path: Path):
  att = tmp_path / "attachments"
  att.mkdir()
  mpp = att / "plan.mpp"
  mpp.write_bytes(b"\xd0\xcf\x11\xe0rest")
  gantt = att / "gantt-chart-b10931f5-7163-4270-95c4-b8d1ca9d23ac.json"
  gantt.write_text(MINI_GANTT.read_text(encoding="utf-8"), encoding="utf-8")
  found = find_plan_source(
    att,
    gantt_instance="b10931f5-7163-4270-95c4-b8d1ca9d23ac",
    expected_name="plan.mpp",
  )
  assert found == gantt
  fallback = find_plan_source(att / "missing", expected_name="plan.mpp")
  assert fallback is None
  only_mpp = tmp_path / "only_mpp"
  only_mpp.mkdir()
  (only_mpp / "plan.mpp").write_bytes(mpp.read_bytes())
  assert find_plan_source(only_mpp, expected_name="plan.mpp").name == "plan.mpp"


def test_export_plan_dispatches_json(tmp_path: Path):
  dest = tmp_path / "gantt-chart-mini.json"
  dest.write_text(MINI_GANTT.read_text(encoding="utf-8"), encoding="utf-8")
  csv_triple = export_plan(
    dest, tmp_path / "out", rate_rub_per_hour=3000, l0_page=L0_ITOGO
  )
  assert csv_triple.kind == "gantt"
  assert csv_triple.cost_rub == 19_536_000.0
  assert csv_triple.effort_source == EFFORT_SOURCE_L0


def test_register_plan_digest_key(tmp_path: Path):
  overlay = tmp_path
  (overlay / "mpp").mkdir()
  csv_triple = gantt_to_csv(
    MINI_GANTT, overlay / "mpp", rate_rub_per_hour=3000, l0_page=L0_ITOGO
  )
  manifest = Manifest(schema_version="1.0", slug="T", pages={}, attachments=[], digests={})
  register_plan_in_manifest(manifest, csv_triple, overlay)
  assert PLAN_DIGEST_KEY in manifest.digests
  entry = manifest.digests[PLAN_DIGEST_KEY]
  assert entry["kind"] == "gantt"
  assert entry["cost_rub"] == 19_536_000.0
  assert entry["effort_source"] == "l0-page-total"
  assert entry["status"] == "pending_compress"


def test_get_plan_digest_reads_legacy_mpp_plan():
  manifest = Manifest(
    schema_version="1.0",
    slug="T",
    pages={},
    digests={"mpp-plan": {"kind": "mpp", "status": "stale"}},
  )
  entry = get_plan_digest(manifest)
  assert entry["kind"] == "mpp"
  assert entry["status"] == "stale"


def test_project_config_plan_section():
  raw = {
    "schema_version": "1.0",
    "slug": "T",
    "display_name": "T",
    "entity_slug": "t",
    "confluence": {
      "root_page_id": "1",
      "root_title": "R",
      "space_primary": "X",
    },
    "plan": {
      "source": "gantt",
      "gantt_page_id": "519492770",
      "gantt_instance": "b10931f5-7163-4270-95c4-b8d1ca9d23ac",
      "rate_rub_per_hour": 3000,
    },
    "meetings": {"project_slugs": []},
  }
  cfg = validate_project_config(raw, slug="T")
  assert cfg.plan["source"] == "gantt"
  assert cfg.gantt_page_id == "519492770"
  assert cfg.rate_rub_per_hour == 3000
  assert cfg.mpp is cfg.plan
  assert "519492770" in cfg.attachment_page_ids


def test_project_config_accepts_legacy_mpp():
  raw = {
    "schema_version": "1.0",
    "slug": "T",
    "display_name": "T",
    "entity_slug": "t",
    "confluence": {
      "root_page_id": "1",
      "root_title": "R",
      "space_primary": "X",
    },
    "mpp": {"expected_name": "test.mpp", "project_title": "T"},
    "meetings": {},
  }
  cfg = validate_project_config(raw, slug="T")
  assert cfg.plan["expected_name"] == "test.mpp"
  assert cfg.rate_rub_per_hour == 3000


def test_project_config_requires_plan_or_mpp():
  raw = {
    "schema_version": "1.0",
    "slug": "T",
    "display_name": "T",
    "entity_slug": "t",
    "confluence": {
      "root_page_id": "1",
      "root_title": "R",
      "space_primary": "X",
    },
    "meetings": {},
  }
  with pytest.raises(ValidationError, match="plan"):
    validate_project_config(raw, slug="T")


def test_default_trisigma_yaml_plan_gantt():
  text = default_trisigma_yaml()
  assert "plan:" in text
  assert "gantt_page_id: \"519492770\"" in text
  assert "b10931f5-7163-4270-95c4-b8d1ca9d23ac" in text
  assert "rate_rub_per_hour: 3000" in text
  assert "\nmpp:" not in text


def test_refresh_marks_plan_stale_on_gantt_sha_change(mini_workvault, mini_overlay):
  from unittest.mock import patch

  from deepmine.manifest import migrate_manifest_p0, rebuild_all
  from deepmine.project_config import load_project_config
  from deepmine.refresh import refresh_pages

  rebuild_all(
    mini_overlay,
    mini_workvault,
    slug="TestProject",
    root_page_id="493477568",
    pmo_seeds=[{"page_id": "490166551"}],
  )
  l0_rel = "Confluence/DPAN/timeline/index.md"
  l0_path = mini_workvault / l0_rel
  l0_path.parent.mkdir(parents=True, exist_ok=True)
  l0_path.write_text(L0_ITOGO.read_text(encoding="utf-8"), encoding="utf-8")

  yaml_path = mini_overlay / "PROJECT.yaml"
  yaml_path.write_text(
    """schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  pmo_seeds:
    - { page_id: "490166551", title: PMO, space: PMO }
plan:
  source: gantt
  gantt_page_id: "519492770"
  rate_rub_per_hour: 3000
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )

  att_dir = mini_overlay / "attachments"
  att_dir.mkdir(parents=True, exist_ok=True)
  gantt = att_dir / "gantt-chart-mini.json"
  gantt.write_text(MINI_GANTT.read_text(encoding="utf-8"), encoding="utf-8")

  raw = json.loads((mini_overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  raw.setdefault("attachments", [])
  raw["attachments"] = [
    {"filename": gantt.name, "sha256": "0" * 64, "local_path": f"attachments/{gantt.name}"}
  ]
  raw.setdefault("pages", {})
  raw["pages"]["519492770"] = {
    "title": "Timeline",
    "local_path": l0_rel,
    "digest_slug": "p519492770",
    "version": "2",
  }
  (mini_overlay / "MANIFEST.json").write_text(
    json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
  )

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  manifest = migrate_manifest_p0(raw, slug="TestProject")

  def fake_poll(client, page_id):
    return int(manifest.pages[page_id].get("version") or 0)

  with patch("deepmine.refresh.poll_version", side_effect=fake_poll):
    with patch("deepmine.refresh._meetings_changed", return_value=False):
      with patch("deepmine.refresh.write_diff"):
        report = refresh_pages(cfg, manifest, mini_overlay, mini_workvault, dry_run=False)

  assert "plan" in report.stale
  disk = json.loads((mini_overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  assert disk["digests"]["plan"]["kind"] == "gantt"
  assert disk["digests"]["plan"]["status"] == "stale"
  assert disk["digests"]["plan"]["cost_rub"] == 19_536_000.0
  assert disk["digests"]["plan"]["effort_source"] == "l0-page-total"
  assert list((mini_overlay / "mpp").glob("*__tasks.csv"))
