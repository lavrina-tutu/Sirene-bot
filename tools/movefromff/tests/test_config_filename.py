"""Unit-тесты v2.0 — конфигурация + filename helpers."""
import os
from pathlib import Path

import pytest

from movefromff.config import Settings
from movefromff.filename import (
    build_filename,
    ms_to_utc,
    sanitize_title,
    utc_iso,
    utc_now,
)


def test_sanitize_replaces_invalid_chars():
    assert sanitize_title('a/b:c*d?e"f<g>h|i\\j') == "a_b_c_d_e_f_g_h_i_j"


def test_sanitize_handles_empty():
    assert sanitize_title("") == "untitled"
    assert sanitize_title("   ") == "untitled"


def test_build_filename_format():
    from datetime import datetime, timezone

    dt = datetime(2026, 5, 20, 11, 30, 0, tzinfo=timezone.utc)
    name = build_filename(dt, "Встреча с клиентом", "transcript")
    assert name == "2026-05-20 11-30-00 Встреча с клиентом - transcript.md"


def test_build_filename_truncates_long_title():
    from datetime import datetime, timezone

    dt = datetime(2026, 5, 20, 11, 30, 0, tzinfo=timezone.utc)
    long_title = "A" * 300
    name = build_filename(dt, long_title, "summary")
    assert len(name) <= 200
    assert name.endswith(" - summary.md")


def test_ms_to_utc():
    # 2026-05-20 11:30:00 UTC = 1779276600000 ms
    dt = ms_to_utc(1779276600000)
    assert dt.year == 2026 and dt.month == 5 and dt.day == 20
    assert dt.hour == 11 and dt.minute == 30


def test_utc_iso_ends_with_z():
    from datetime import datetime, timezone

    dt = datetime(2026, 5, 20, 11, 30, 0, tzinfo=timezone.utc)
    assert utc_iso(dt) == "2026-05-20T11:30:00Z"


def test_settings_paths_derive(tmp_path: Path):
    s = Settings(
        workvault_path=tmp_path / "vault",
        project_path=tmp_path / "proj",
        fireflies_api_key="x",
    )
    assert s.new_meetings_dir == tmp_path / "vault" / "Meetings" / "NewMeetings"
    assert s.registry_json.name == "_registry.json"
    assert s.registry_md.name == "_registry.md"
    assert s.log_md.name == "_log.md"
    assert s.jsonl_log == tmp_path / "proj" / "logs" / "movefromff.jsonl"
    assert s.lock_file.name == "movefromff.lock"
