"""Context J1-J8: batch count, reject, idempotency."""
from __future__ import annotations

from unittest.mock import patch

from deepmine.context_batches import run_charter_batches
from deepmine.context_run import run_context
from deepmine.context_schema import CHARTER_BATCH_FIELDS
from deepmine.facts_run import run_facts
from deepmine.graph_build import build_graph, run_graph
from deepmine.project_config import load_project_config


def _fake_batch(batch_num: int):
  return {
    "batch": batch_num,
    "sections": [
      {"field": f, "content": "test", "source_page_id": "493477568", "status": "ok"}
      for f in CHARTER_BATCH_FIELDS[batch_num]
    ],
  }


def test_charter_requires_five_batches(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  from deepmine.manifest import load_manifest

  manifest = load_manifest(mini_overlay, slug="TestProject")
  graph = build_graph(cfg, manifest.pages, mini_workvault)
  facts = run_facts(cfg, mini_overlay, mini_workvault, manifest.pages, skip_llm=True)
  llm_calls: list[str] = []
  with patch("deepmine.context_batches.call_json") as mock:
    mock.side_effect = [_fake_batch(i) for i in range(1, 6)]
    results = run_charter_batches(
      cfg, mini_overlay, graph, facts, manifest.pages, mini_workvault, llm_calls=llm_calls,
    )
  assert len(results) == 5
  assert len(llm_calls) == 5


def test_j8_skips_llm_when_sources_sha_matches(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  run_graph(cfg, mini_overlay, mini_workvault)
  from deepmine.manifest import load_manifest

  manifest = load_manifest(mini_overlay, slug="TestProject")
  run_facts(cfg, mini_overlay, mini_workvault, manifest.pages, skip_llm=True)
  llm_calls: list[str] = []
  with patch("deepmine.context_batches.call_json") as mock:
    mock.side_effect = [_fake_batch(i) for i in range(1, 6)]
    run_context(cfg, mini_overlay, mini_workvault, "charter", llm_calls=llm_calls)
  llm_calls.clear()
  result = run_context(cfg, mini_overlay, mini_workvault, "charter", llm_calls=llm_calls)
  assert result.get("skipped") is True
  assert len(llm_calls) == 0
