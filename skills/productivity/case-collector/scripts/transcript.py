"""Compact session transcript for LLM split."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence
from zoneinfo import ZoneInfo

from db import MessageRow

NOISE_PREFIXES: tuple[str, ...] = (
    "[IMPORTANT: Background process",
)
ASSISTANT_STUB_MAX: int = 200
DEFAULT_CHUNK_CHARS: int = 8000
DEFAULT_OVERLAP_TURNS: int = 2
CHARS_PER_TOKEN: float = 2.5


@dataclass(frozen=True)
class Turn:
    id: int
    ts_iso: str
    role: str
    text: str


@dataclass(frozen=True)
class Chunk:
    index: int
    total: int
    overlap_ids: tuple[int, ...]
    turns: tuple[Turn, ...]
    char_count: int


def is_live_user(msg: MessageRow) -> bool:
    if msg.role != "user":
        return False
    if msg.content is None or not msg.content.strip():
        return False
    if msg.active is not None and msg.active != 1:
        return False
    if msg.compacted is not None and msg.compacted != 0:
        return False
    return True


def is_noise(text: str) -> bool:
    if not text or not text.strip():
        return True
    for prefix in NOISE_PREFIXES:
        if text.startswith(prefix):
            return True
    return False


def strip_noise(text: str) -> str | None:
    if is_noise(text):
        return None
    return text.strip()


def _looks_like_tool_json(text: str) -> bool:
    s = text.lstrip()
    if not s.startswith("{"):
        return False
    low = s[:80].lower()
    return '"tool' in low or '"name"' in low


def next_assistant_stub(messages: Sequence[MessageRow], after_index: int) -> str | None:
    for msg in messages:
        if msg.id <= after_index:
            continue
        if msg.role == "tool":
            continue
        if msg.role != "assistant":
            continue
        if msg.active is not None and msg.active != 1:
            continue
        if msg.compacted is not None and msg.compacted != 0:
            continue
        content = msg.content or ""
        if _looks_like_tool_json(content):
            return None
        return content[:ASSISTANT_STUB_MAX]
    return None


def ts_to_iso(ts: float, tz: ZoneInfo) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(ts, tz=tz).isoformat()


def build_compact_transcript(
    messages: Sequence[MessageRow],
    *,
    tz: ZoneInfo,
    include_assistant_stubs: bool = False,
) -> list[Turn]:
    ordered = sorted(messages, key=lambda m: (m.timestamp, m.id))
    turns: list[Turn] = []
    for msg in ordered:
        if not is_live_user(msg):
            continue
        cleaned = strip_noise(msg.content or "")
        if cleaned is None:
            continue
        turns.append(
            Turn(
                id=msg.id,
                ts_iso=ts_to_iso(msg.timestamp, tz),
                role="user",
                text=cleaned,
            )
        )
        if include_assistant_stubs:
            stub = next_assistant_stub(ordered, msg.id)
            if stub:
                turns.append(
                    Turn(
                        id=msg.id,
                        ts_iso=ts_to_iso(msg.timestamp, tz),
                        role="assistant",
                        text=stub,
                    )
                )
    return turns


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def user_char_count(turns: Sequence[Turn]) -> int:
    return sum(len(t.text) for t in turns if t.role == "user")


def chunk_turns(
    turns: Sequence[Turn],
    *,
    max_input_chars: int = 12000,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_n: int = DEFAULT_OVERLAP_TURNS,
) -> list[Chunk]:
    if not turns:
        return []
    if user_char_count(turns) <= max_input_chars:
        return [
            Chunk(
                index=0,
                total=1,
                overlap_ids=(),
                turns=tuple(turns),
                char_count=user_char_count(turns),
            )
        ]

    user_indices: list[int] = [i for i, t in enumerate(turns) if t.role == "user"]
    if not user_indices:
        return []

    chunks: list[tuple[int, int]] = []
    start_ui = 0
    while start_ui < len(user_indices):
        char_sum = 0
        end_ui = start_ui
        while end_ui < len(user_indices):
            ui = user_indices[end_ui]
            char_sum += len(turns[ui].text)
            if char_sum > chunk_chars and end_ui > start_ui:
                break
            end_ui += 1
            if char_sum >= chunk_chars:
                break
        if end_ui == start_ui:
            end_ui = start_ui + 1
        turn_start = user_indices[start_ui]
        turn_end = user_indices[end_ui - 1]
        chunks.append((turn_start, turn_end))
        if end_ui >= len(user_indices):
            break
        start_ui = max(start_ui + 1, end_ui - overlap_n)

    n = len(chunks)
    result: list[Chunk] = []
    for idx, (t_start, t_end) in enumerate(chunks):
        overlap_ids: tuple[int, ...] = ()
        if idx > 0:
            prev_start, prev_end = chunks[idx - 1]
            prev_user_ids = [
                turns[i].id for i in range(prev_start, prev_end + 1) if turns[i].role == "user"
            ]
            overlap_ids = tuple(prev_user_ids[-overlap_n:])
        slice_turns = turns[t_start : t_end + 1]
        result.append(
            Chunk(
                index=idx,
                total=n,
                overlap_ids=overlap_ids,
                turns=tuple(slice_turns),
                char_count=user_char_count(slice_turns),
            )
        )
    return result
