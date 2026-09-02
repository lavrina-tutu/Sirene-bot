"""Refresh dry-run marks stale without compress."""
from __future__ import annotations

from unittest.mock import patch

from deepmine.manifest import migrate_manifest_p0, rebuild_all
from deepmine.models import Manifest
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
