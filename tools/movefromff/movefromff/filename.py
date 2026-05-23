"""Filename helpers — sanitization, UTC formatting, FF-format regex.

ТЗ §5:
- Дата/время в UTC, формат `YYYY-MM-DD HH-MM-SS Title - {transcript|summary|actions}.md`
- Запрещённые Windows символы (`\\ / : * ? " < > |`) → `_`
- Имя > 200 символов → обрезается с `…`
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional, Tuple

# Windows-invalid chars (NOT including ` -`, which is our separator)
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')
_MULTI_SPACE = re.compile(r"\s+")

# Max length of the *title* portion (we keep overall name under 200 chars).
MAX_FILENAME_LEN = 200

# Trailing dots/spaces are illegal on Windows.
_TRAIL_BAD = re.compile(r"[ .]+$")

FF_FILENAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}-\d{2}-\d{2}) "
    r"(?P<title>.+) - (?P<kind>transcript|summary|actions)\.md$"
)

KINDS = ("transcript", "summary", "actions")


def sanitize_title(title: str) -> str:
    """Replace Windows-invalid chars with `_`, collapse whitespace, trim trail."""
    if not title:
        return "untitled"
    cleaned = _INVALID_CHARS.sub("_", title)
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()
    cleaned = _TRAIL_BAD.sub("", cleaned)
    if not cleaned:
        return "untitled"
    return cleaned


def ms_to_utc(ms: int | float) -> datetime:
    """FF date (ms UTC) → aware datetime in UTC."""
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)


def utc_iso(dt: datetime) -> str:
    """Aware UTC datetime → ISO-8601 with `Z` suffix (seconds precision)."""
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def utc_now_iso() -> str:
    return utc_iso(utc_now())


def filename_date_part(dt: datetime) -> Tuple[str, str]:
    """Return (`YYYY-MM-DD`, `HH-MM-SS`) in UTC."""
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H-%M-%S")


def build_filename(meeting_dt: datetime, title: str, kind: str) -> str:
    """Build a meeting filename of the form
    `YYYY-MM-DD HH-MM-SS Title - kind.md` with truncation to keep name ≤200.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    date_part, time_part = filename_date_part(meeting_dt)
    safe = sanitize_title(title)
    suffix = f" - {kind}.md"
    prefix = f"{date_part} {time_part} "
    budget = MAX_FILENAME_LEN - len(prefix) - len(suffix)
    if budget < 1:
        budget = 1
    if len(safe) > budget:
        # Reserve 1 char for ellipsis
        safe = safe[: max(1, budget - 1)].rstrip() + "…"
    return f"{prefix}{safe}{suffix}"


def parse_filename(name: str) -> Optional[dict]:
    """Parse a filename created by `build_filename` (or a manual file matching
    the FF regex). Returns dict with keys `date`, `time`, `title`, `kind` or None.
    """
    m = FF_FILENAME_RE.match(name)
    if not m:
        return None
    return m.groupdict()


def base_key(meeting_dt: datetime, title: str) -> str:
    """Stable per-meeting base key (without ` - kind.md`)."""
    date_part, time_part = filename_date_part(meeting_dt)
    safe = sanitize_title(title)
    return f"{date_part} {time_part} {safe}"
