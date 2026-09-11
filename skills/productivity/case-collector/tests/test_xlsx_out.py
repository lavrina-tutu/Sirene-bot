from __future__ import annotations

import sys
from unittest import mock

import pytest

from xlsx_out import (
    CASE_HEADERS,
    SESSION_HEADERS,
    CaseRow,
    SessionInventoryRow,
    assert_no_raw_content,
    write_deliverable,
    write_xlsx,
)


def test_xlsx_headers_and_two_sheets(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    path = tmp_path / "out.xlsx"
    write_xlsx(path, [], [])
    wb = load_workbook(path)
    assert "Кейсы" in wb.sheetnames
    assert "Сессии" in wb.sheetnames
    assert list(wb["Кейсы"].iter_rows(min_row=1, max_row=1, values_only=True))[0] == tuple(
        CASE_HEADERS
    )


def test_header_bold_fill(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    path = tmp_path / "out.xlsx"
    write_xlsx(path, [], [])
    wb = load_workbook(path)
    cell = wb["Кейсы"]["A1"]
    assert cell.font.bold
    assert cell.fill.fgColor.rgb is not None or cell.fill.patternType


def test_cyrillic_intact(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    row = CaseRow(
        user="u",
        topic="настройка доступов",
        start="s",
        end="e",
        session_id="sid",
        source="telegram",
        chat_id="c",
        thread_id="t",
        session_title="",
        confidence="high",
        flags="",
        start_msg_id=1,
        end_msg_id=2,
    )
    path = tmp_path / "out.xlsx"
    write_xlsx(path, [row], [])
    wb = load_workbook(path)
    val = wb["Кейсы"]["B2"].value
    assert val == "настройка доступов"


def test_no_content_column(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    path = tmp_path / "out.xlsx"
    write_xlsx(path, [], [])
    wb = load_workbook(path)
    headers = [c.value for c in wb["Кейсы"][1]]
    for bad in ("content", "text", "body"):
        assert bad not in headers


def test_no_jira_columns(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    path = tmp_path / "out.xlsx"
    write_xlsx(path, [], [])
    wb = load_workbook(path)
    headers = [c.value for c in wb["Кейсы"][1]]
    assert "Jira" not in " ".join(str(h) for h in headers)
    assert "вердикт" not in headers


def test_csv_fallback_delimiter(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    path = tmp_path / "out.xlsx"
    out, kind = write_deliverable(path, [], [])
    assert kind == "csv"
    data = out.read_bytes()
    assert data[:3] == b"\xef\xbb\xbf"
    assert b";" in data


def test_csv_fallback_on_write_error(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("xlsx_out.write_xlsx", boom)
    path = tmp_path / "out.xlsx"
    out, kind = write_deliverable(path, [], [])
    assert kind == "csv"
    assert out.suffix == ".csv"


def test_flags_overlap_written(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    row = CaseRow(
        user="u",
        topic="t",
        start="s",
        end="e",
        session_id="sid",
        source="telegram",
        chat_id="c",
        thread_id="t",
        session_title="",
        confidence="high",
        flags="overlap",
        start_msg_id=1,
        end_msg_id=2,
    )
    path = tmp_path / "out.xlsx"
    write_xlsx(path, [row], [])
    wb = load_workbook(path)
    flags_idx = list(CASE_HEADERS).index("flags")
    col_letter = chr(ord("A") + flags_idx)
    assert "overlap" in str(wb["Кейсы"][f"{col_letter}2"].value)


def test_dry_run_sessions_only(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    sess = SessionInventoryRow(
        session_id="s",
        user="u",
        source="telegram",
        started_at="t",
        message_count=1,
        user_msgs=1,
        user_chars=3,
        status="ok",
    )
    path = tmp_path / "out.xlsx"
    write_xlsx(path, [], [sess])
    wb = load_workbook(path)
    assert wb["Кейсы"].max_row == 1
    assert wb["Сессии"].max_row == 2


def test_assert_no_raw_content():
    row = CaseRow(
        user="u",
        topic="t",
        start="s",
        end="e",
        session_id="sid",
        source="telegram",
        chat_id="c",
        thread_id="t",
        session_title="",
        confidence="high",
        flags="",
        start_msg_id=1,
        end_msg_id=2,
    )
    assert_no_raw_content(row)


def test_resolution_columns_in_headers_order():
    assert "решённость" in CASE_HEADERS
    assert "обоснование вердикта" in CASE_HEADERS
    sid_i = CASE_HEADERS.index("session_id")
    src_i = CASE_HEADERS.index("source")
    assert CASE_HEADERS.index("решённость") == sid_i + 1
    assert CASE_HEADERS.index("обоснование вердикта") == sid_i + 2
    assert src_i == sid_i + 3


def test_resolution_values_in_xlsx(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    row = CaseRow(
        user="u",
        topic="t",
        start="s",
        end="e",
        session_id="sid",
        resolution="resolved",
        resolution_reason="подтверждено в чате",
        source="telegram",
        chat_id="c",
        thread_id="t",
        session_title="",
        confidence="high",
        flags="",
        start_msg_id=1,
        end_msg_id=2,
    )
    path = tmp_path / "out.xlsx"
    write_xlsx(path, [row], [])
    wb = load_workbook(path)
    headers = list(wb["Кейсы"].iter_rows(min_row=1, max_row=1, values_only=True))[0]
    res_i = headers.index("решённость")
    reason_i = headers.index("обоснование вердикта")
    data = list(wb["Кейсы"].iter_rows(min_row=2, max_row=2, values_only=True))[0]
    assert data[res_i] == "resolved"
    assert data[reason_i] == "подтверждено в чате"


def test_csv_fallback_has_resolution_columns(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "openpyxl", None)
    row = CaseRow(
        user="u",
        topic="t",
        start="s",
        end="e",
        session_id="sid",
        resolution="unresolved",
        resolution_reason="нет итога",
        source="telegram",
        chat_id="c",
        thread_id="t",
        session_title="",
        confidence="high",
        flags="",
        start_msg_id=1,
        end_msg_id=2,
    )
    path = tmp_path / "out.xlsx"
    out, kind = write_deliverable(path, [row], [])
    assert kind == "csv"
    text = out.read_text(encoding="utf-8-sig")
    assert "решённость" in text.split("\n")[0]
    assert "unresolved" in text
    assert "нет итога" in text
