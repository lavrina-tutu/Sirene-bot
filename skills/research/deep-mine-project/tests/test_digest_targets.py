"""Regression: digest target selection (default=stale, --full=all)."""
from __future__ import annotations

import json
from unittest.mock import patch

from deepmine.digest_run import run_digest
from deepmine.manifest import rebuild_all
from deepmine.project_config import load_project_config


def _prepare_manifest(mini_workvault, mini_overlay):
  rebuild_all(
    mini_overlay,
    mini_workvault,
    slug="TestProject",
    root_page_id="493477568",
    pmo_seeds=[{"page_id": "490166551"}],
  )
  raw = json.loads((mini_overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  for page_id, page in raw["pages"].items():
    page["digest_status"] = "fresh"
  raw["pages"]["499549642"]["digest_status"] = "stale"
  (mini_overlay / "MANIFEST.json").write_text(
    json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return load_project_config("TestProject", workvault=mini_workvault)


def _run_with_mock(cfg, overlay, workvault, **kwargs):
  compressed_ids: list[str] = []

  def fake_compress_leaf(page_id, page, *_args, **_kwargs):
    compressed_ids.append(page_id)
    return page.get("digest_slug")

  with patch("deepmine.digest_run.compress_leaf", side_effect=fake_compress_leaf):
    with patch("deepmine.digest_run.compress_theme"):
      with patch("deepmine.digest_run.compress_plan"):
        with patch("deepmine.digest_run.rebuild_graph"):
          run_digest(cfg, overlay, workvault, dry_run=True, **kwargs)
  return compressed_ids


def test_run_digest_default_compresses_only_stale(mini_workvault, mini_overlay):
  cfg = _prepare_manifest(mini_workvault, mini_overlay)
  ids = _run_with_mock(cfg, mini_overlay, mini_workvault)
  assert ids == ["499549642"]


def test_run_digest_all_stale_same_as_default(mini_workvault, mini_overlay):
  cfg = _prepare_manifest(mini_workvault, mini_overlay)
  ids = _run_with_mock(cfg, mini_overlay, mini_workvault, all_stale=True)
  assert ids == ["499549642"]


def test_run_digest_full_compresses_all_pages(mini_workvault, mini_overlay):
  cfg = _prepare_manifest(mini_workvault, mini_overlay)
  ids = _run_with_mock(cfg, mini_overlay, mini_workvault, full=True)
  assert sorted(ids) == ["490166551", "493477568", "499549642"]
