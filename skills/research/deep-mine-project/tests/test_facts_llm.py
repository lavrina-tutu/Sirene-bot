"""facts_llm: llm_assisted extraction via call_json."""
from __future__ import annotations

from unittest.mock import patch

from deepmine.facts_llm import extract_people_assignments
from deepmine.manifest import load_manifest


def test_extract_people_assignments_mock(mini_workvault, mini_overlay):
  manifest = load_manifest(mini_overlay, slug="TestProject")
  page_id = "493477568"
  page = manifest.pages[page_id]
  with patch("deepmine.facts_llm.call_json") as mock_json:
    mock_json.side_effect = [
      {"people": [{"fio": "Иванов", "role": "PM", "source_page_id": page_id, "confidence": "high"}]},
      {"assignments": [{"text": "сделать", "assignee": "Иванов", "source_page_id": page_id, "confidence": "medium"}]},
    ]
    result = extract_people_assignments(page_id, page, mini_workvault)
  assert len(result["people"]) == 1
  assert result["people"][0]["source_kind"] == "llm"
