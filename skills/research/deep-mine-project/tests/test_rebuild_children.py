"""T1: children = parent inversion despite L0 children:[]."""
from deepmine.manifest import rebuild_children, migrate_manifest_p0
import json


def test_rebuild_children_inverts_parent(mini_overlay):
  raw = json.loads((mini_overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  m = migrate_manifest_p0(raw, slug="TestProject")
  for pid, page in m.pages.items():
    page["parent"] = None
  m.pages["499549642"]["parent"] = "493477568"
  rebuild_children(m.pages)
  assert m.pages["493477568"]["children"] == ["499549642"]
  assert m.pages["499549642"]["children"] == []
