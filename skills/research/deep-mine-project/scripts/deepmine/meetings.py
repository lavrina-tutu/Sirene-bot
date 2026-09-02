"""Meeting index via MofsIndex → pointers/meetings.md."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .fail import meetings_failed
from .paths import MOFS_INDEX_ROOT

MEETINGS_LIMIT = 500


@dataclass
class MeetingRow:
  meeting_id: str
  meeting_date: str
  title: str | None
  obsidian_url: str | None
  transcript_present: bool


def _import_search_meetings():
  if str(MOFS_INDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_INDEX_ROOT))
  from mofs_index import search_meetings  # type: ignore

  return search_meetings


def index_meetings(project_slugs: list[str]) -> list[MeetingRow]:
  search_meetings = _import_search_meetings()
  try:
    hits = search_meetings(
      query=None,
      slugs={"projects": project_slugs},
      slug_mode="any",
      limit=MEETINGS_LIMIT,
    )
  except Exception as exc:
    meetings_failed(str(exc))
  rows: list[MeetingRow] = []
  for hit in hits:
    transcript_present = False
    if hasattr(hit, "transcript_present"):
      transcript_present = bool(hit.transcript_present)
    rows.append(
      MeetingRow(
        meeting_id=hit.meeting_id,
        meeting_date=hit.meeting_date,
        title=hit.title,
        obsidian_url=getattr(hit, "obsidian_url", None),
        transcript_present=transcript_present,
      )
    )
  rows.sort(key=lambda r: (r.meeting_date, r.meeting_id), reverse=True)
  return rows


def write_meetings_pointer(overlay: Path, rows: list[MeetingRow]) -> Path:
  out = overlay / "pointers" / "meetings.md"
  out.parent.mkdir(parents=True, exist_ok=True)
  now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  lines = [
    "---",
    "kind: meetings_pointer",
    f"generated_at: {now}",
    f"count: {len(rows)}",
    "---",
    "",
    "# Указатель встреч",
    "",
    "Только метаданные и ссылки на summary. Транскрипты не копируются.",
    "",
    "| Дата | meeting_id | Title | Summary | transcript_present |",
    "|---|---|---|---|---|",
  ]
  for row in rows:
    title = (row.title or "").replace("|", "\\|")
    link = row.obsidian_url or f"Meetings/NewMeetings/{row.meeting_id} - summary.md"
    lines.append(
      f"| {row.meeting_date} | {row.meeting_id} | {title} | [[{link}]] | {row.transcript_present} |"
    )
  out.write_text("\n".join(lines) + "\n", encoding="utf-8")
  return out
