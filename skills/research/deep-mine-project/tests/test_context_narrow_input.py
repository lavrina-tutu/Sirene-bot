"""narrow_input: full bodies only for body_page_ids."""
from __future__ import annotations

from deepmine.context_prompt import narrow_input
from deepmine.facts_run import run_facts
from deepmine.graph_build import build_graph
from deepmine.project_config import load_project_config


def test_narrow_input_no_digest(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  from deepmine.manifest import load_manifest

  manifest = load_manifest(mini_overlay, slug="TestProject")
  graph = build_graph(cfg, manifest.pages, mini_workvault)
  facts = run_facts(cfg, mini_overlay, mini_workvault, manifest.pages, skip_llm=True)
  cfg.contexts.charter_body_page_ids = ["493477568"]
  text = narrow_input("charter", cfg, graph, facts, manifest.pages, mini_workvault)
  assert "digest/leaves/p" not in text
  assert "digest/themes/" not in text
  assert "FULL pageId=493477568" in text
  assert "pageId=490166551" in text
