"""T2: entity pointer paths only."""
from deepmine.entity import write_entity_pointer


def test_entity_pointer_paths_only(mini_workvault, mini_overlay, tmp_path):
  entity = mini_workvault / "Entities" / "trisigma"
  entity.mkdir(parents=True)
  (entity / "card.md").write_text("# Card\nsecret body", encoding="utf-8")
  (entity / "context.md").write_text("# Context\nmore secret", encoding="utf-8")

  path = write_entity_pointer(mini_workvault, mini_overlay, "trisigma")
  text = path.read_text(encoding="utf-8")
  assert "Entities/trisigma/card.md" in text
  assert "secret body" not in text
  assert "more secret" not in text
