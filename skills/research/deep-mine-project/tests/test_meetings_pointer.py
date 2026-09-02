"""T2: meetings pointer without transcript."""
from unittest.mock import MagicMock, patch

from deepmine.meetings import MEETINGS_LIMIT, index_meetings, write_meetings_pointer


def test_meetings_pointer_content(mini_overlay):
  hit = MagicMock()
  hit.meeting_id = "2026-01-01 10-00-00 Test"
  hit.meeting_date = "2026-01-01"
  hit.title = "Standup"
  hit.obsidian_url = "Meetings/NewMeetings/2026-01-01 10-00-00 Test - summary.md"
  hit.transcript_present = True

  with patch("deepmine.meetings._import_search_meetings") as imp:
    imp.return_value = lambda **kw: [hit] if kw.get("limit", 0) >= MEETINGS_LIMIT else []
    rows = index_meetings(["trisigma"])
  assert len(rows) == 1
  path = write_meetings_pointer(mini_overlay, rows)
  text = path.read_text(encoding="utf-8")
  assert "2026-01-01 10-00-00 Test" in text
  assert "- transcript.md" not in text
  assert "transcript_present" in text


def test_meetings_limit_500():
  captured = {}

  def fake_search(**kwargs):
    captured.update(kwargs)
    return []

  with patch("deepmine.meetings._import_search_meetings", return_value=fake_search):
    index_meetings(["trisigma"])
  assert captured.get("limit") == 500
