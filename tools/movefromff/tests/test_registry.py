"""Unit-тесты v2.0 для `_registry.json` (schema 2.0 + миграция)."""
import json
from pathlib import Path

import pytest

from movefromff.registry import (
    SCHEMA_VERSION,
    MeetingRecord,
    Registry,
    load_registry,
    make_empty_record,
    save_registry,
)


def test_empty_registry_round_trip(tmp_path: Path):
    path = tmp_path / "_registry.json"
    reg = load_registry(path)
    assert reg.schema_version == SCHEMA_VERSION
    assert reg.meetings == {}
    save_registry(reg, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "2.0"
    assert data["meetings"] == {}


def test_save_and_reload_preserves_record(tmp_path: Path):
    path = tmp_path / "_registry.json"
    reg = Registry()
    rec = MeetingRecord(
        title="Hello",
        meeting_date="2026-05-20T11:30:00Z",
        duration_minutes=47.3,
        participants=["a@b.com"],
        files={
            "transcript": "x - transcript.md",
            "summary": "x - summary.md",
            "actions": "x - actions.md",
        },
        status="completed",
        fetched_at="2026-05-22T14:30:05Z",
    )
    reg.meetings["mid-1"] = rec
    save_registry(reg, path)

    reg2 = load_registry(path)
    assert "mid-1" in reg2.meetings
    r2 = reg2.meetings["mid-1"]
    assert r2.title == "Hello"
    assert r2.duration_minutes == 47.3
    assert r2.participants == ["a@b.com"]
    assert r2.status == "completed"
    assert r2.files["transcript"] == "x - transcript.md"


def test_save_is_atomic_no_tmp_left(tmp_path: Path):
    path = tmp_path / "_registry.json"
    reg = Registry()
    save_registry(reg, path)
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith("_registry-")]
    assert leftovers == []


def test_invalid_json_raises(tmp_path: Path):
    p = tmp_path / "_registry.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_registry(p)


def test_migration_from_v1_completed_with_files_present(tmp_path: Path):
    """v1.x → v2.0: запись completed, файлы на диске → status=completed."""
    new_dir = tmp_path / "NewMeetings"
    new_dir.mkdir()
    # «положим» файлы
    for fn in ("x-tr.md", "x-su.md", "x-ac.md"):
        (new_dir / fn).write_text("dummy", encoding="utf-8")

    legacy = {
        "schema_version": "1.1",
        "updated_at": "2026-05-01T00:00:00Z",
        "meetings": {
            "old-1": {
                "meeting_id": "old-1",
                "title": "Old meeting",
                "meeting_date": "2026-05-01T10:00:00Z",
                "duration_minutes": 30.0,
                "participants": ["a@b.com"],
                "transfer_status": "completed",
                "integrity": "ok",
                "audio_url": "https://...",  # должен быть отброшен
                "sha256": "abc",  # отброшено
                "keywords": ["k1", "k2"],  # отброшено
                "errors": [{"timestamp": "x", "error_message": "y"}],  # отброшено
                "files": {
                    "transcript": {"filename": "x-tr.md", "sha256": "...", "size_bytes": 5},
                    "summary": {"filename": "x-su.md", "sha256": "...", "size_bytes": 5},
                    "actions": {"filename": "x-ac.md", "sha256": "...", "size_bytes": 5},
                },
                "fetched_at": "2026-05-01T10:00:05Z",
            }
        },
    }
    path = new_dir / "_registry.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    reg = load_registry(path, new_dir)
    assert reg.schema_version == SCHEMA_VERSION
    assert "old-1" in reg.meetings
    rec = reg.meetings["old-1"]
    assert rec.title == "Old meeting"
    assert rec.status == "completed"
    assert rec.files == {
        "transcript": "x-tr.md",
        "summary": "x-su.md",
        "actions": "x-ac.md",
    }
    # Запрещённые поля точно не сохранились (модель их игнорирует).
    dumped = rec.model_dump()
    assert "sha256" not in dumped
    assert "audio_url" not in dumped
    assert "keywords" not in dumped
    assert "errors" not in dumped
    assert "transfer_status" not in dumped
    assert "integrity" not in dumped


def test_migration_from_v1_completed_files_missing(tmp_path: Path):
    """v1.x → v2.0: completed, но файлов нет → status=error."""
    new_dir = tmp_path / "NewMeetings"
    new_dir.mkdir()
    legacy = {
        "schema_version": "1.0",
        "updated_at": "2026-05-01T00:00:00Z",
        "meetings": {
            "old-1": {
                "title": "Old",
                "transfer_status": "completed",
                "files": {"transcript": {"filename": "missing.md"}},
            }
        },
    }
    path = new_dir / "_registry.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    reg = load_registry(path, new_dir)
    assert reg.meetings["old-1"].status == "error"


def test_make_empty_record():
    r = make_empty_record()
    assert r.status == "pending"
    assert r.files == {}
    assert r.participants == []
