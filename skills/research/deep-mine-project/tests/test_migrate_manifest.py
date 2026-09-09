"""T1: P0 manifest migration."""
import json

from deepmine.manifest import is_p0_manifest, migrate_manifest_p0, rebuild_all


def test_migrate_p0_to_schema(mini_overlay, mini_workvault):
  raw = json.loads((mini_overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  assert is_p0_manifest(raw)
  m = migrate_manifest_p0(raw, slug="TestProject")
  assert m.schema_version == "1.1"
  assert len(m.pages) == 3
  assert "493477568" in m.pages
  assert m.pages["493477568"]["title"] == "Root"


def test_migrate_idempotent(mini_overlay):
  raw = json.loads((mini_overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  m1 = migrate_manifest_p0(raw, slug="TestProject").to_dict()
  m2 = migrate_manifest_p0(m1, slug="TestProject")
  assert m2.schema_version == "1.1"
  assert len(m2.pages) == 3


def test_rebuild_sets_full_sha(mini_overlay, mini_workvault):
  manifest = rebuild_all(
    mini_overlay,
    mini_workvault,
    slug="TestProject",
    root_page_id="493477568",
    pmo_seeds=[{"page_id": "490166551"}],
  )
  sha = manifest.pages["493477568"]["content_sha256"]
  assert len(sha) == 64
  assert sha != "deadbeef"
