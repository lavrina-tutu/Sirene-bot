"""T1: hierarchical TREE from parent inversion."""
from deepmine.manifest import rebuild_all


def test_tree_hierarchical_not_flat_by_space(mini_overlay, mini_workvault):
  rebuild_all(
    mini_overlay,
    mini_workvault,
    slug="TestProject",
    root_page_id="493477568",
    pmo_seeds=[{"page_id": "490166551"}],
  )
  tree = (mini_overlay / "TREE.md").read_text(encoding="utf-8")
  assert "иерархия parent→children" in tree
  assert "Child architecture page" in tree or "Child" in tree
  assert "490166551" in tree or "PMO Brief" in tree
  # child nested under root section
  root_pos = tree.find("493477568")
  child_pos = tree.find("499549642")
  assert root_pos >= 0 and child_pos > root_pos
