"""Unit-тесты v2.0 — рендеринг 3 файлов на встречу + writer + registry.md."""
from pathlib import Path

import pytest

from movefromff.ff_schema import FFMeeting, FFSentence, FFSummary
from movefromff.registry import MeetingRecord, Registry
from movefromff.renderer import (
    render_actions,
    render_registry_md,
    render_summary,
    render_transcript,
)
from movefromff.writer import write_meeting_files


def _make_meeting(**over) -> FFMeeting:
    default = {
        "id": "mid-001",
        "title": "Test meeting",
        "date": 1779276600000,  # 2026-05-20T11:30:00Z
        "duration": 5.0,
        "participants": ["a@b.com", "c@d.com"],
        "sentences": [
            FFSentence(speaker_id="A", speaker_name="Иван", text="Привет", start_time=1.0),
            FFSentence(speaker_id="B", speaker_name=None, text="Здарова", start_time=2.5),
            FFSentence(speaker_id="A", speaker_name="Иван", text="Как дела?", start_time=4.0),
        ],
        "summary": FFSummary(
            overview="Overview text",
            action_items="- сделать раз\n- сделать два",
            keywords=["a", "b"],
        ),
    }
    default.update(over)
    return FFMeeting.model_validate(default)


def test_render_transcript_contains_title_and_speakers():
    m = _make_meeting()
    md = render_transcript(m)
    assert "Test meeting" in md
    assert "2026-05-20T11:30:00Z" in md
    assert "**Meeting ID:** mid-001" in md
    assert "**Иван:**" in md
    # пустого speaker_name → Speaker N
    assert "Speaker" in md  # для второго спикера


def test_render_transcript_empty_sentences():
    m = _make_meeting(sentences=[])
    md = render_transcript(m)
    assert "Транскрипт пуст" in md


def test_render_summary_renders_sections():
    m = _make_meeting()
    md = render_summary(m)
    assert "Саммари: Test meeting" in md
    assert "## Overview" in md
    assert "Overview text" in md
    assert "## Action Items" in md
    assert "## Keywords" in md
    assert "a, b" in md


def test_render_summary_skips_empty_sections():
    m = _make_meeting(summary=FFSummary(overview=None, action_items=None, keywords=None))
    md = render_summary(m)
    # Заголовки секций не выводятся, когда тело пусто.
    assert "## Overview" not in md
    assert "## Action Items" not in md
    assert "## Keywords" not in md


def test_render_actions_present():
    m = _make_meeting()
    md = render_actions(m)
    assert "Action items: Test meeting" in md
    assert "сделать раз" in md


def test_render_actions_empty_placeholder():
    m = _make_meeting(summary=FFSummary(action_items=None))
    md = render_actions(m)
    assert "Нет action items" in md


def test_write_meeting_files_writes_three(tmp_path: Path):
    m = _make_meeting()
    files = write_meeting_files(m, tmp_path)
    assert set(files.keys()) == {"transcript", "summary", "actions"}
    for kind, fn in files.items():
        p = tmp_path / fn
        assert p.exists(), f"{kind} file missing"
        assert kind in fn  # имя содержит kind
    # Проверим, что имя — детерминированное по дате+title
    assert "2026-05-20 11-30-00" in files["transcript"]


def test_write_meeting_files_rollback_on_failure(tmp_path: Path, monkeypatch):
    """Если при записи одной из секций возникает ошибка — все ранее записанные
    файлы должны быть удалены (rollback)."""
    m = _make_meeting()

    # Заставим renderer.render_actions упасть.
    import movefromff.writer as writer_mod

    def boom(_m):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(writer_mod, "render_actions", boom)

    with pytest.raises(RuntimeError, match="synthetic"):
        write_meeting_files(m, tmp_path)

    leftovers = list(tmp_path.iterdir())
    assert leftovers == [], f"rollback не очистил файлы: {leftovers}"


def test_render_registry_md_table():
    reg = Registry()
    reg.meetings["mid-1"] = MeetingRecord(
        title="One",
        meeting_date="2026-05-20T11:30:00Z",
        status="completed",
    )
    reg.meetings["mid-2"] = MeetingRecord(
        title="Two",
        meeting_date="2026-05-21T11:30:00Z",
        status="error",
    )
    md = render_registry_md(reg)
    assert "Реестр встреч MoveFromFF" in md
    assert "`completed`" in md
    assert "`error`" in md
    assert "mid-1" in md and "mid-2" in md
    assert "**Schema:** `2.0`" in md
