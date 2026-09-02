"""T2: collect does not copy L0 bodies into overlay."""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deep_mine.py"


def test_collect_no_confluence_id_in_overlay_bodies(mini_workvault, mini_overlay):
  entity = mini_workvault / "Entities" / "trisigma"
  entity.mkdir(parents=True)
  (entity / "card.md").write_text("card", encoding="utf-8")

  with patch("deepmine.meetings._import_search_meetings") as imp:
    imp.return_value = lambda **kw: []
    subprocess.run(
      [
        sys.executable,
        str(SCRIPT),
        "collect",
        "--slug",
        "TestProject",
        "--workvault",
        str(mini_workvault),
        "--skip-a",
        "--skip-b",
        "--skip-c",
      ],
      cwd=SCRIPT.parent,
      check=True,
      capture_output=True,
      text=True,
    )

  for md in mini_overlay.rglob("*.md"):
    if "pointers" in md.parts or md.name in {"TREE.md", "SOURCES.md"}:
      continue
    text = md.read_text(encoding="utf-8")
    assert "confluence_id:" not in text
