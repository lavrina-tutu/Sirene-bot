"""Graph backlinks and edges."""
from __future__ import annotations

from deepmine.graph import collect_edges, recompute_backlinks


def test_recompute_backlinks():
  digests = {
    "p1": {"related": ["p2"], "backlinks": []},
    "p2": {"related": [], "backlinks": []},
    "p3": {"related": ["missing"], "backlinks": []},
  }
  recompute_backlinks(digests)
  assert "p1" in digests["p2"]["backlinks"]
  assert digests["p3"]["backlinks"] == []
  assert "missing" not in digests


def test_collect_edges_parent_child():
  pages = {
    "1": {"digest_slug": "p1", "parent": None, "children": ["2"]},
    "2": {"digest_slug": "p2", "parent": "1", "children": []},
  }
  digests = {
    "p1": {"related": ["p2"], "backlinks": ["p2"]},
    "p2": {"related": [], "backlinks": ["p1"]},
  }
  edges = collect_edges(digests, pages)
  kinds = {(a, b, c) for a, b, c in edges}
  assert ("p1", "p2", "parent") in kinds
  assert ("p2", "p1", "child") in kinds
  assert ("p1", "p2", "related") in kinds
