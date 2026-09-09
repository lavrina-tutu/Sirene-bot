"""PROJECT.yaml v1.1 migration."""
from __future__ import annotations

from deepmine.project_config import migrate_project_yaml, validate_project_config


def test_migrate_project_yaml_idempotent(tmp_path):
  path = tmp_path / "PROJECT.yaml"
  path.write_text(
    """schema_version: "1.0"
slug: Test
display_name: Test
entity_slug: x
confluence:
  root_page_id: "1"
  root_title: R
  space_primary: DPAN
  follow_outbound: pmo-from-root
mpp:
  project_title: T
meetings:
  project_slugs: [x]
""",
    encoding="utf-8",
  )
  assert migrate_project_yaml(path) is True
  raw = path.read_text(encoding="utf-8")
  assert "1.1" in raw
  assert "charter_body_page_ids" in raw
  assert migrate_project_yaml(path) is False


def test_validate_schema_11():
  cfg = validate_project_config({
    "schema_version": "1.1",
    "slug": "S",
    "display_name": "D",
    "entity_slug": "e",
    "confluence": {
      "root_page_id": "1",
      "root_title": "R",
      "space_primary": "DPAN",
      "follow_outbound": {"mode": "same-space-plus-allowed-pmo", "depth": 1},
    },
    "plan": {"project_title": "T"},
    "meetings": {"project_slugs": []},
    "contexts": {"charter_body_page_ids": ["1"]},
  })
  assert cfg.schema_version == "1.1"
  assert cfg.follow.depth == 1
