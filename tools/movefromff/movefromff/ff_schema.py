"""Pydantic models for Fireflies GraphQL response + transcript normalization (v2.0)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .filename import ms_to_utc


class FFSentence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index: Optional[int] = None
    speaker_name: Optional[str] = None
    speaker_id: Optional[Any] = None
    text: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class FFSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    overview: Optional[str] = None
    action_items: Optional[str] = None
    keywords: Optional[Union[str, List[str]]] = None
    outline: Optional[str] = None


class FFMeeting(BaseModel):
    """Сырой ответ FF (минимум полей; audio_url не используем — ТЗ §2)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: Optional[str] = None
    date: Optional[Union[int, float]] = None  # ms UTC
    duration: Optional[float] = None  # minutes (float)
    participants: List[str] = Field(default_factory=list)
    sentences: List[FFSentence] = Field(default_factory=list)
    summary: Optional[FFSummary] = None

    @field_validator("title", mode="before")
    @classmethod
    def _title_default(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return "Untitled meeting"
        return v

    @field_validator("participants", mode="before")
    @classmethod
    def _participants_clean(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        out: List[str] = []
        seen = set()
        for raw in v:
            if not raw:
                continue
            s = str(raw).strip().lower()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    @property
    def meeting_datetime(self) -> datetime:
        if self.date is None:
            raise ValueError(f"Meeting {self.id} has no date")
        return ms_to_utc(self.date)

    @property
    def display_title(self) -> str:
        return self.title or "Untitled meeting"


def format_timestamp(seconds: Optional[float]) -> str:
    """Float seconds → `[MM:SS]` или `[HH:MM:SS]` (≥ 3600 сек). None → `[00:00]`."""
    if seconds is None or seconds < 0:
        seconds = 0.0
    total = int(round(float(seconds)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"[{h:02d}:{m:02d}:{s:02d}]"
    return f"[{m:02d}:{s:02d}]"


def build_speaker_map(sentences: List[FFSentence]) -> dict:
    """1-based индекс уникальных спикеров в порядке появления."""
    idx = 1
    mapping: dict = {}
    for s in sentences:
        key = s.speaker_id if s.speaker_id is not None else (s.speaker_name or "")
        if key == "" and s.speaker_id is None:
            key = f"__anon_{idx}"
        if key not in mapping:
            mapping[key] = idx
            idx += 1
    return mapping


def speaker_label(sentence: FFSentence, mapping: dict) -> str:
    """Не-пустой лейбл спикера с фоллбеком `Speaker N`."""
    name = (sentence.speaker_name or "").strip()
    if name:
        return name
    key = sentence.speaker_id if sentence.speaker_id is not None else "__anon"
    n = mapping.get(key)
    if n is None:
        n = len(mapping) + 1
        mapping[key] = n
    return f"Speaker {n}"


def keywords_as_text(keywords: Optional[Union[str, List[str]]]) -> Optional[str]:
    """Для summary.md: строка как есть, list → через запятую."""
    if keywords is None:
        return None
    if isinstance(keywords, list):
        items = [str(k).strip() for k in keywords if str(k).strip()]
        if not items:
            return None
        return ", ".join(items)
    s = str(keywords).strip()
    return s or None
