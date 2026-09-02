"""T0: no USERTOOLS/DeepMineProject in skill."""
from pathlib import Path


def test_no_usertools_deepmine_package(skill_root: Path):
  text = ""
  for path in skill_root.rglob("*"):
    if "tests" in path.parts:
      continue
    if path.suffix in {".md", ".py"}:
      text += path.read_text(encoding="utf-8", errors="ignore")
  assert "USERTOOLS/DeepMineProject" not in text
