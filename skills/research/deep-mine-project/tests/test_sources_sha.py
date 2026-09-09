"""sources_sha computation."""
from __future__ import annotations

from deepmine.facts_run import run_facts
from deepmine.graph_build import build_graph
from deepmine.project_config import load_project_config
from deepmine.sources_sha import catalog_version, compute_sources_sha


def test_catalog_version_is_string():
  assert isinstance(catalog_version(), str)


def test_compute_sources_sha_stable(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  from deepmine.manifest import load_manifest

  manifest = load_manifest(mini_overlay, slug="TestProject")
  graph = build_graph(cfg, manifest.pages, mini_workvault)
  facts = run_facts(cfg, mini_overlay, mini_workvault, manifest.pages, skip_llm=True)
  sha1 = compute_sources_sha("charter", cfg, graph, facts, manifest.pages, mini_workvault)
  sha2 = compute_sources_sha("charter", cfg, graph, facts, manifest.pages, mini_workvault)
  assert sha1 == sha2
  assert len(sha1) == 64
