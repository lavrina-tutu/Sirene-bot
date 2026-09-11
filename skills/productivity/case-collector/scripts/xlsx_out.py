"""XLSX/CSV deliverables for case-collector."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

SHEET_CASES: str = "Кейсы"
SHEET_SESSIONS: str = "Сессии"
CSV_DELIMITER: str = ";"
CSV_ENCODING: str = "utf-8-sig"
HEADER_FILL_HEX: str = "D9E2F3"
MIN_COL_WIDTH: float = 10.0
MAX_COL_WIDTH: float = 60.0

CASE_HEADERS: tuple[str, ...] = (
    "пользователь",
    "тема кейса",
    "начало",
    "конец",
    "session_id",
    "решённость",
    "обоснование вердикта",
    "source",
    "chat_id",
    "thread_id",
    "session_title",
    "confidence",
    "flags",
    "start_msg_id",
    "end_msg_id",
)

SESSION_HEADERS: tuple[str, ...] = (
    "session_id",
    "пользователь",
    "source",
    "started_at",
    "message_count",
    "user_msgs",
    "user_chars",
    "status",
)


@dataclass
class CaseRow:
    user: str
    topic: str
    start: str
    end: str
    session_id: str
    source: str
    chat_id: str
    thread_id: str
    session_title: str
    confidence: str
    flags: str
    start_msg_id: int
    end_msg_id: int
    resolution: str = "unclear"
    resolution_reason: str = ""


@dataclass
class SessionInventoryRow:
    session_id: str
    user: str
    source: str
    started_at: str
    message_count: int
    user_msgs: int
    user_chars: int
    status: str


def style_header(ws: Any) -> None:
    from openpyxl.styles import Font, PatternFill

    fill = PatternFill("solid", fgColor=HEADER_FILL_HEX)
    bold = Font(bold=True)
    for cell in ws[1]:
        cell.font = bold
        cell.fill = fill
    ws.freeze_panes = "A2"


def autosize(ws: Any) -> None:
    for col in ws.columns:
        letter = col[0].column_letter
        max_len = max(len(str(c.value or "")) for c in col)
        width = min(max(max_len + 1, MIN_COL_WIDTH), MAX_COL_WIDTH)
        ws.column_dimensions[letter].width = width


def case_to_tuple(row: CaseRow) -> tuple:
    return (
        row.user,
        row.topic,
        row.start,
        row.end,
        row.session_id,
        row.resolution,
        row.resolution_reason,
        row.source,
        row.chat_id,
        row.thread_id,
        row.session_title,
        row.confidence,
        row.flags,
        row.start_msg_id,
        row.end_msg_id,
    )


def session_to_tuple(row: SessionInventoryRow) -> tuple:
    return (
        row.session_id,
        row.user,
        row.source,
        row.started_at,
        row.message_count,
        row.user_msgs,
        row.user_chars,
        row.status,
    )


def assert_no_raw_content(row: CaseRow) -> None:
    assert not hasattr(row, "content")


def write_xlsx(
    path: Path, cases: Sequence[CaseRow], sessions: Sequence[SessionInventoryRow]
) -> Path:
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws_cases = wb.active
    ws_cases.title = SHEET_CASES
    ws_cases.append(list(CASE_HEADERS))
    for row in cases:
        ws_cases.append(list(case_to_tuple(row)))
    style_header(ws_cases)
    autosize(ws_cases)

    ws_sess = wb.create_sheet(SHEET_SESSIONS)
    ws_sess.append(list(SESSION_HEADERS))
    for row in sessions:
        ws_sess.append(list(session_to_tuple(row)))
    style_header(ws_sess)
    autosize(ws_sess)

    wb.save(path)
    return path


def write_csv_pair(
    path_stem: Path, cases: Sequence[CaseRow], sessions: Sequence[SessionInventoryRow]
) -> tuple[Path, Path]:
    stem = path_stem
    if stem.suffix.lower() == ".xlsx":
        stem = stem.with_suffix("")
    cases_path = stem.with_suffix(".csv")
    sessions_path = Path(str(stem) + "_sessions.csv")
    path_stem.parent.mkdir(parents=True, exist_ok=True)
    with cases_path.open("w", encoding=CSV_ENCODING, newline="") as f:
        w = csv.writer(f, delimiter=CSV_DELIMITER, quoting=csv.QUOTE_MINIMAL)
        w.writerow(list(CASE_HEADERS))
        for row in cases:
            w.writerow(list(case_to_tuple(row)))
    with sessions_path.open("w", encoding=CSV_ENCODING, newline="") as f:
        w = csv.writer(f, delimiter=CSV_DELIMITER, quoting=csv.QUOTE_MINIMAL)
        w.writerow(list(SESSION_HEADERS))
        for row in sessions:
            w.writerow(list(session_to_tuple(row)))
    return cases_path, sessions_path


def write_deliverable(
    output: Path,
    cases: Sequence[CaseRow],
    sessions: Sequence[SessionInventoryRow],
) -> tuple[Path, str]:
    try:
        import openpyxl  # noqa: F401

        path = write_xlsx(output, cases, sessions)
        return path, "xlsx"
    except ImportError:
        cases_path, _ = write_csv_pair(output, cases, sessions)
        return cases_path, "csv"
    except OSError:
        cases_path, _ = write_csv_pair(output, cases, sessions)
        return cases_path, "csv"
