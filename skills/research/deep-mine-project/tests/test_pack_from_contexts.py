"""pack uses contexts + GRAPH, not digest."""
from __future__ import annotations

import json
from pathlib import Path

from deepmine.pack import run_pack
from deepmine.paths import CHARTER_MD, GRAPH_JSON


def _write_charter(overlay: Path) -> None:
  (overlay / CHARTER_MD).write_text(
    """---
schema_version: "1.0"
kind: charter
status: fresh
sources_sha: "deadbeef"
---
## Источники

- GRAPH.json
""",
    encoding="utf-8",
  )


def _setup(mini_overlay: Path) -> None:
  (mini_overlay / "PROJECT.yaml").write_text(
    """schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  tasks:
    feature_compare: "514903239"
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )
  data = {
    "schema_version": "1.1",
    "slug": "TestProject",
    "pages": {
      "514903239": {
        "title": "Feature",
        "version": "1",
        "local_path": "Confluence/DPAN/child/index.md",
      }
    },
    "attachments": [],
    "digests": {},
    "contexts": {},
  }
  (mini_overlay / "MANIFEST.json").write_text(json.dumps(data), encoding="utf-8")
  _write_charter(mini_overlay)
  (mini_overlay / GRAPH_JSON).write_text('{"nodes": {}, "edges": []}', encoding="utf-8")


def test_pack_from_contexts(mini_workvault, mini_overlay):
  _setup(mini_overlay)
  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  pack_dir = run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")
  pack = (pack_dir / "PACK.md").read_text(encoding="utf-8")
  assert CHARTER_MD in pack
  assert GRAPH_JSON in pack
  assert "digest/leaves" not in pack
