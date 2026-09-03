"""SKILL.md trigger coverage for pmo-charter-fill."""
from __future__ import annotations

from pathlib import Path

SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"

TRIGGERS = [
  "заполни устав",
  "доработай устав",
  "проектные документы полного внедрения",
]


def test_skill_description_contains_charter_triggers():
  text = SKILL_MD.read_text(encoding="utf-8")
  frontmatter = text.split("---", 2)[1]
  for trigger in TRIGGERS:
    assert trigger in frontmatter or trigger in text
