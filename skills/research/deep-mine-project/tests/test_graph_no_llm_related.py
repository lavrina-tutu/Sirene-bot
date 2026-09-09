"""GRAPH must not include LLM-related from digest."""
from __future__ import annotations

from deepmine.graph_build import build_graph
from deepmine.project_config import load_project_config


def test_graph_ignores_digest_related(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  from deepmine.manifest import load_manifest

  manifest = load_manifest(mini_overlay, slug="TestProject")
  leaves = mini_overlay / "digest" / "leaves"
  leaves.mkdir(parents=True, exist_ok=True)
  (leaves / "p493477568.md").write_text(
    "---\nrelated: [p490166551]\n---\n## Источники\n\nx\n",
    encoding="utf-8",
  )
  graph = build_graph(cfg, manifest.pages, mini_workvault)
  for edge in graph["edges"]:
    assert edge["type"] != "related"
    assert edge["type"] != "backlink"
