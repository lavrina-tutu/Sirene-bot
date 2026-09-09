"""GRAPH SoT: edge types parent|child|links_to|seed only."""
from __future__ import annotations

import json

from deepmine.graph import collect_sot_edges
from deepmine.graph_build import build_graph, graph_fingerprint, seed_ids
from deepmine.project_config import load_project_config


def test_seed_ids(mini_workvault):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  seeds = seed_ids(cfg)
  assert "493477568" in seeds
  assert "490166551" in seeds


def test_build_graph_edge_types(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  from deepmine.manifest import load_manifest

  manifest = load_manifest(mini_overlay, slug="TestProject")
  graph = build_graph(cfg, manifest.pages, mini_workvault)
  types = {e["type"] for e in graph["edges"]}
  assert types <= {"parent", "child", "links_to", "seed"}
  assert "related" not in types
  assert "backlink" not in types


def test_graph_fingerprint_stable(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  from deepmine.manifest import load_manifest

  manifest = load_manifest(mini_overlay, slug="TestProject")
  g1 = build_graph(cfg, manifest.pages, mini_workvault)
  g2 = build_graph(cfg, manifest.pages, mini_workvault)
  assert graph_fingerprint(g1) == graph_fingerprint(g2)


def test_collect_sot_edges_no_related(mini_workvault, mini_overlay):
  from deepmine.manifest import load_manifest

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  manifest = load_manifest(mini_overlay, slug="TestProject")
  edges = collect_sot_edges(manifest.pages, mini_workvault, seed_ids(cfg))
  kinds = {e[2] for e in edges}
  assert "related" not in kinds
  assert "backlink" not in kinds
