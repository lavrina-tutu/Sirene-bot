from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from transcript import (
    ASSISTANT_STUB_MAX,
    build_compact_transcript,
    chunk_turns,
    estimate_tokens,
    ts_to_iso,
    user_char_count,
)
from transcript import Turn


def test_drops_tool_and_session_meta(sample_messages, tz_moscow):
    turns = build_compact_transcript(sample_messages, tz=tz_moscow)
    roles = {t.role for t in turns}
    assert "tool" not in roles
    assert all(t.role in ("user", "assistant") for t in turns)


def test_drops_inactive_and_compacted(sample_messages, tz_moscow):
    turns = build_compact_transcript(sample_messages, tz=tz_moscow)
    texts = {t.text for t in turns}
    assert "inactive" not in texts
    assert "compacted" not in texts


def test_drops_noise_and_whitespace(sample_messages, tz_moscow):
    turns = build_compact_transcript(sample_messages, tz=tz_moscow)
    assert not any("[IMPORTANT: Background process" in t.text for t in turns)


def test_stubs_off_by_default(sample_messages, tz_moscow):
    turns = build_compact_transcript(sample_messages, tz=tz_moscow)
    assert all(t.role == "user" for t in turns)


def test_stubs_truncated_200(sample_messages, tz_moscow):
    turns = build_compact_transcript(
        sample_messages, tz=tz_moscow, include_assistant_stubs=True
    )
    stubs = [t for t in turns if t.role == "assistant"]
    assert len(stubs) == 1
    assert len(stubs[0].text) <= ASSISTANT_STUB_MAX
    assert not stubs[0].text.lstrip().startswith("{")


def test_empty_after_filter(tz_moscow):
    from db import MessageRow
    from conftest import TS_IN

    msgs = [MessageRow(1, "s", "tool", "x", TS_IN)]
    assert build_compact_transcript(msgs, tz=tz_moscow) == []


def test_estimate_tokens_no_tokenizer(scripts_dir):
    text = (scripts_dir / "transcript.py").read_text(encoding="utf-8")
    assert "tiktoken" not in text
    assert estimate_tokens("abcde") == 2


def test_single_chunk_under_limit():
    turns = [
        Turn(1, "t", "user", "x" * 1000),
    ]
    chunks = chunk_turns(turns, max_input_chars=12000)
    assert len(chunks) == 1
    assert chunks[0].total == 1


def test_chunk_by_user_not_mid_message():
    turns = [Turn(i, "t", "user", "word " * 500) for i in range(20)]
    chunks = chunk_turns(turns, max_input_chars=12000, chunk_chars=8000)
    assert len(chunks) >= 2
    for ch in chunks:
        for t in ch.turns:
            assert t.text.endswith(" ") or t.text == "word " * 500


def test_chunk_overlap_two_user_ids():
    turns = [Turn(i, "t", "user", "x" * 3000) for i in range(10)]
    chunks = chunk_turns(
        turns, max_input_chars=12000, chunk_chars=8000, overlap_n=2
    )
    if len(chunks) >= 2:
        assert len(chunks[1].overlap_ids) <= 2


def test_ts_iso_moscow(tz_moscow):
    ts = datetime(2026, 9, 9, 12, 0, tzinfo=ZoneInfo("Europe/Moscow")).timestamp()
    iso = ts_to_iso(ts, tz_moscow)
    assert "+03:00" in iso
