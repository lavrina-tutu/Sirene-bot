"""Refresh dry-run marks stale without compress."""
from __future__ import annotations

import json
from unittest.mock import patch

from deepmine.digest_io import list_stale
from deepmine.manifest import migrate_manifest_p0, rebuild_all
from deepmine.project_config import load_project_config
from deepmine.refresh import refresh_pages


def test_stale_dry_run_single_page(mini_workvault, mini_overlay):
  rebuild_all(
    mini_overlay,
    mini_workvault,
    slug="TestProject",
    root_page_id="493477568",
    pmo_seeds=[{"page_id": "490166551"}],
  )
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  manifest = migrate_manifest_p0(
    __import__("json").loads((mini_overlay / "MANIFEST.json").read_text()),
    slug="TestProject",
  )

  def fake_poll(client, page_id):
    if page_id == "499549642":
      return 99
    local = int(manifest.pages[page_id].get("version") or 0)
    return local

  with patch("deepmine.refresh.poll_version", side_effect=fake_poll):
    with patch("deepmine.cursor_jobs.run_agent") as mock_agent:
      report = refresh_pages(cfg, manifest, mini_overlay, mini_workvault, dry_run=True)
  assert report.dry_run is True
  assert report.stale == ["p499549642"]
  assert len(report.stale) == 1
  mock_agent.assert_not_called()


def test_stale_non_dry_run_persists_after_rebuild(mini_workvault, mini_overlay):
  rebuild_all(
    mini_overlay,
    mini_workvault,
    slug="TestProject",
    root_page_id="493477568",
    pmo_seeds=[{"page_id": "490166551"}],
  )
  raw = json.loads((mini_overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  for page in raw["pages"].values():
    page["digest_status"] = "fresh"
  (mini_overlay / "MANIFEST.json").write_text(
    json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  manifest = migrate_manifest_p0(raw, slug="TestProject")

  def fake_poll(client, page_id):
    if page_id == "499549642":
      return 99
    local = int(manifest.pages[page_id].get("version") or 0)
    return local

  with patch("deepmine.refresh.poll_version", side_effect=fake_poll):
    with patch("deepmine.refresh.run_pull"):
      with patch("deepmine.refresh._meetings_changed", return_value=False):
        with patch("deepmine.refresh.write_diff"):
          report = refresh_pages(cfg, manifest, mini_overlay, mini_workvault, dry_run=False)

  assert report.dry_run is False
  assert report.stale == ["p499549642"]

  disk = json.loads((mini_overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  assert disk["pages"]["499549642"]["digest_status"] == "stale"
  manifest_after = migrate_manifest_p0(disk, slug="TestProject")
  assert list_stale(manifest_after) == ["p499549642"]
  for page_id in ("493477568", "490166551"):
    assert disk["pages"][page_id].get("digest_status") == "fresh"
