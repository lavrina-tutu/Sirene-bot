"""Jinja2 рендеринг — transcript / summary / actions / registry markdown (v2.0)."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .ff_schema import (
    FFMeeting,
    build_speaker_map,
    format_timestamp,
    keywords_as_text,
    speaker_label,
)
from .registry import Registry

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    env.filters["fmt_ts"] = format_timestamp
    return env


_env: Environment | None = None


def env() -> Environment:
    global _env
    if _env is None:
        _env = _make_env()
    return _env


def _date_iso(meeting: FFMeeting) -> str:
    return meeting.meeting_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")


def _duration_human(meeting: FFMeeting) -> str:
    if meeting.duration is None:
        return "—"
    return f"{float(meeting.duration):.1f}"


def render_transcript(meeting: FFMeeting) -> str:
    mapping = build_speaker_map(list(meeting.sentences))
    lines = []
    for s in meeting.sentences:
        text = (s.text or "").strip()
        if not text:
            continue
        lines.append({
            "ts": format_timestamp(s.start_time),
            "speaker": speaker_label(s, mapping),
            "text": text,
        })

    return env().get_template("transcript.md.j2").render(
        title=meeting.display_title,
        meeting_date_iso=_date_iso(meeting),
        duration=_duration_human(meeting),
        participants=meeting.participants,
        meeting_id=meeting.id,
        lines=lines,
    )


def render_summary(meeting: FFMeeting) -> str:
    s = meeting.summary
    kw = keywords_as_text(s.keywords) if s else None
    return env().get_template("summary.md.j2").render(
        title=meeting.display_title,
        overview=(s.overview if s else None),
        action_items=(s.action_items if s else None),
        keywords_text=kw,
    )


def render_actions(meeting: FFMeeting) -> str:
    s = meeting.summary
    text = (s.action_items if s else None) or ""
    text = text.strip()
    return env().get_template("actions.md.j2").render(
        title=meeting.display_title,
        action_items=text or None,
    )


def render_registry_md(reg: Registry) -> str:
    items = sorted(
        reg.meetings.items(),
        key=lambda kv: (kv[1].meeting_date or "", kv[1].title),
        reverse=True,
    )
    return env().get_template("registry.md.j2").render(
        schema_version=reg.schema_version,
        updated_at=reg.updated_at,
        meetings=[(mid, rec) for mid, rec in items],
        total=len(items),
    )
