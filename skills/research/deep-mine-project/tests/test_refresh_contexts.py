"""refresh triggers graph/facts without digest."""
from __future__ import annotations

from unittest.mock import patch

from deepmine.manifest import migrate_manifest_p0, rebuild_all
from deepmine.project_config import load_project_config
from deepmine.refresh import refresh_pages


def test_refresh_calls_graph_not_digest(mini_workvault, mini_overlay):
  rebuild_all(
    mini_overlay, mini_workvault,
    slug="TestProject", root_page_id="493477568",
    pmo_seeds=[{"page_id": "490166551"}],
  )
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  manifest = migrate_manifest_p0(
    __import__("json").loads((mini_overlay / "MANIFEST.json").read_text()),
    slug="TestProject",
  )
  with patch("deepmine.refresh.poll_version", return_value=99):
    with patch("deepmine.refresh.run_pull"):
      with patch("deepmine.refresh._meetings_changed", return_value=False):
        with patch("deepmine.refresh.write_diff"):
          with patch("deepmine.refresh.run_graph") as mock_graph:
            with patch("deepmine.refresh.run_facts"):
              with patch("deepmine.context_run.run_context"):
                with patch("deepmine.digest_run.run_digest") as mock_digest:
                  refresh_pages(cfg, manifest, mini_overlay, mini_workvault, dry_run=False, skip_llm=True)
  mock_graph.assert_called_once()
  mock_digest.assert_not_called()
