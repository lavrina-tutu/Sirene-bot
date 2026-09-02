"""T0: compressor prompt exists; no tz-compressor in skill."""
from pathlib import Path

from deepmine.paths import COMPRESSOR_PROMPT


def test_compressor_prompt_exists():
  assert COMPRESSOR_PROMPT.is_file()


def test_skill_has_no_tz_compressor_in_code(skill_root: Path):
  hits = []
  for path in (skill_root / "scripts").rglob("*.py"):
    if "tz-compressor-prompt" in path.read_text(encoding="utf-8", errors="ignore"):
      hits.append(str(path))
  assert hits == []
