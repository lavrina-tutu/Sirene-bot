"""T0: compressor prompt exists; no tz-compressor in skill."""
from pathlib import Path

from deepmine.paths import ARCHITECT_BRIEF_TEMPLATE, COMPRESSOR_PROMPT


def test_compressor_prompt_exists():
  assert COMPRESSOR_PROMPT.is_file()
  text = COMPRESSOR_PROMPT.read_text(encoding="utf-8")
  assert "журнал" in text.lower() or "Digest записан" in text
  assert "deepseek" in text.lower()


def test_architect_brief_template_exists():
  assert ARCHITECT_BRIEF_TEMPLATE.is_file()
  text = ARCHITECT_BRIEF_TEMPLATE.read_text(encoding="utf-8")
  assert "Чеклист инвариантов" in text
  assert text.count("## ") >= 6


def test_skill_has_no_tz_compressor_in_code(skill_root: Path):
  hits = []
  for path in (skill_root / "scripts").rglob("*.py"):
    if "tz-compressor-prompt" in path.read_text(encoding="utf-8", errors="ignore"):
      hits.append(str(path))
  assert hits == []
