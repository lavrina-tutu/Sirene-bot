"""context_render: frontmatter and sections."""
from __future__ import annotations

from deepmine.context_render import render_context_md


def test_render_context_md_starts_with_sources():
  md = render_context_md(
    "charter",
    "TestProject",
    "abc123",
    [1, 2, 3, 4, 5],
    {"nodes": {"1": {}}},
    ["493477568"],
    [{"sections": [{"field": "Цель", "content": "X", "source_page_id": "493477568"}]}],
  )
  assert md.startswith("---")
  assert "## Источники" in md
  assert "source pageId: 493477568" in md
