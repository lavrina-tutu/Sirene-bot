"""Pytest fixtures for case-collector."""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from db import MessageRow  # noqa: E402
from split_llm import FakeLlmAdapter  # noqa: E402

assert os.environ.get("CASE_COLLECTOR_TEST_FORBID_LIVE_DB", "1") == "1"

TEST_SINCE = datetime(2026, 9, 8, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))
TEST_UNTIL = datetime(2026, 9, 11, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))
TEST_SINCE_ISO = "2026-09-08T00:00:00+03:00"
TEST_UNTIL_ISO = "2026-09-11T00:00:00+03:00"
TS_IN = datetime(2026, 9, 9, 12, 0, tzinfo=ZoneInfo("Europe/Moscow")).timestamp()
TS_OUT_START = datetime(2026, 9, 7, 12, 0, tzinfo=ZoneInfo("Europe/Moscow")).timestamp()
TS_MSG_OUTSIDE = datetime(2026, 9, 9, 14, 0, tzinfo=ZoneInfo("Europe/Moscow")).timestamp()


def _session_cols_full() -> str:
    return """
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        started_at REAL NOT NULL,
        user_id TEXT,
        model TEXT,
        parent_session_id TEXT,
        ended_at REAL,
        end_reason TEXT,
        message_count INTEGER,
        title TEXT,
        session_key TEXT,
        chat_id TEXT,
        chat_type TEXT,
        thread_id TEXT,
        display_name TEXT,
        origin_json TEXT,
        profile_name TEXT,
        last_activity_at REAL,
        archived INTEGER
    """


def _message_cols_full() -> str:
    return """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT,
        timestamp REAL NOT NULL,
        tool_name TEXT,
        token_count INTEGER,
        active INTEGER,
        compacted INTEGER
    """


def _create_schema(conn: sqlite3.Connection, *, minimal: bool = False) -> None:
    if minimal:
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, started_at REAL NOT NULL)"
        )
        conn.execute(
            """CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                timestamp REAL NOT NULL
            )"""
        )
    else:
        conn.execute(f"CREATE TABLE sessions ({_session_cols_full()})")
        conn.execute(f"CREATE TABLE messages ({_message_cols_full()})")
    conn.commit()


def _ins_sess(
    conn: sqlite3.Connection,
    sid: str,
    source: str,
    started: float,
    *,
    archived: int | None = None,
    thread_id: str | None = None,
    chat_id: str = "chat-example",
    session_key: str | None = None,
    origin_json: str | None = None,
    user_id: str | None = "u-test",
) -> None:
    conn.execute(
        """INSERT INTO sessions (
            id, source, started_at, user_id, title, session_key, chat_id, thread_id,
            origin_json, archived, message_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sid,
            source,
            started,
            user_id,
            f"title-{sid}",
            session_key,
            chat_id,
            thread_id,
            origin_json,
            archived,
            0,
        ),
    )


def _ins_msg(
    conn: sqlite3.Connection,
    session_id: str,
    mid: int,
    role: str,
    content: str,
    ts: float,
    *,
    active: int = 1,
    compacted: int = 0,
) -> None:
    conn.execute(
        """INSERT INTO messages (id, session_id, role, content, timestamp, active, compacted)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (mid, session_id, role, content, ts, active, compacted),
    )


def _populate_fixture(conn: sqlite3.Connection) -> None:
    _ins_sess(conn, "S-tg-1", "telegram", TS_IN, thread_id="t-1", chat_id="chat-example")
    for i, text in enumerate(
        ["msg1 a", "msg2 a", "msg3 a", "msg4 b", "msg5 b", "msg6 b"], start=1
    ):
        _ins_msg(conn, "S-tg-1", 100 + i, "user", text, TS_IN + i)

    _ins_sess(conn, "S-tg-2", "telegram", TS_IN, thread_id="t-2")
    _ins_msg(conn, "S-tg-2", 201, "user", "one", TS_IN + 1)
    _ins_msg(conn, "S-tg-2", 202, "user", "two", TS_IN + 2)

    _ins_sess(conn, "S-cli", "cli", TS_IN, thread_id="t-cli")
    _ins_msg(conn, "S-cli", 301, "user", "cli msg", TS_IN)

    _ins_sess(conn, "S-cron", "cron", TS_IN)
    _ins_msg(conn, "S-cron", 401, "user", "cron", TS_IN)
    _ins_sess(conn, "S-kan", "kanban", TS_IN)
    _ins_msg(conn, "S-kan", 501, "user", "kan", TS_IN)
    _ins_sess(conn, "S-sub", "subagent", TS_IN)
    _ins_msg(conn, "S-sub", 601, "user", "sub", TS_IN)

    _ins_sess(conn, "S-arch", "telegram", TS_IN, archived=1)
    _ins_msg(conn, "S-arch", 701, "user", "arch", TS_IN)

    _ins_sess(conn, "S-tool", "telegram", TS_IN)
    _ins_msg(conn, "S-tool", 801, "tool", "tool body", TS_IN)

    _ins_sess(conn, "S-comp", "telegram", TS_IN)
    _ins_msg(conn, "S-comp", 901, "user", "comp", TS_IN, compacted=1)

    _ins_sess(conn, "S-out", "telegram", TS_OUT_START, thread_id="t-out")
    _ins_msg(conn, "S-out", 1001, "user", "outside start", TS_MSG_OUTSIDE)

    _ins_sess(conn, "S-noise", "telegram", TS_IN)
    _ins_msg(
        conn,
        "S-noise",
        1101,
        "user",
        "[IMPORTANT: Background process handoff",
        TS_IN,
    )

    _ins_sess(conn, "S-outside-win", "telegram", TS_OUT_START - 86400)
    _ins_msg(conn, "S-outside-win", 1201, "user", "old session", TS_IN)

    conn.commit()


@pytest.fixture
def skill_root() -> Path:
    return SKILL_ROOT


@pytest.fixture
def scripts_dir(skill_root: Path) -> Path:
    return skill_root / "scripts"


@pytest.fixture
def tz_moscow() -> ZoneInfo:
    return ZoneInfo("Europe/Moscow")


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "mini.db"
    conn = sqlite3.connect(db_path)
    _create_schema(conn)
    _populate_fixture(conn)
    conn.close()
    return db_path


@pytest.fixture
def fixture_db_minimal_cols(tmp_path: Path) -> Path:
    db_path = tmp_path / "minimal.db"
    conn = sqlite3.connect(db_path)
    _create_schema(conn, minimal=True)
    conn.execute(
        "INSERT INTO sessions (id, source, started_at) VALUES (?, ?, ?)",
        ("S-min", "telegram", TS_IN),
    )
    conn.execute(
        "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        ("S-min", "user", "hello", TS_IN),
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def sample_messages() -> list[MessageRow]:
    ts = TS_IN
    return [
        MessageRow(1, "s1", "user", "  hello  ", ts, active=1, compacted=0),
        MessageRow(2, "s1", "tool", "ignored", ts),
        MessageRow(3, "s1", "session_meta", "meta", ts),
        MessageRow(4, "s1", "user", "", ts, active=1),
        MessageRow(5, "s1", "user", "inactive", ts, active=0),
        MessageRow(6, "s1", "user", "compacted", ts, active=1, compacted=1),
        MessageRow(
            7,
            "s1",
            "user",
            "[IMPORTANT: Background process x",
            ts,
            active=1,
        ),
        MessageRow(8, "s1", "assistant", "short reply", ts + 1, active=1),
        MessageRow(
            9,
            "s1",
            "assistant",
            '{"tool": "x", "name": "y"}' + "x" * 300,
            ts + 2,
            active=1,
        ),
    ]


@pytest.fixture
def user_map_file(tmp_path: Path) -> Path:
    path = tmp_path / "map.yaml"
    path.write_text(
        """
session_key:
  "agent:main:telegram:group:chat-example:topic-1": "Mapped SK"
source_chat_thread:
  "telegram:chat-example:t-2": "Mapped SCT"
thread_id:
  "t-1": "Mapped TID"
user_id:
  "u-test": "Mapped UID"
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def fake_adapter() -> FakeLlmAdapter:
    def mapping(payload: dict) -> str:
        sid = payload["session_id"]
        if sid == "S-tg-1":
            return (
                '{"schema_version":"1.1","session_id":"S-tg-1","cases":['
                '{"topic":"тема первая","start_msg_id":101,"end_msg_id":103,'
                '"confidence":"high","resolution":"unclear","resolution_reason":"нет вердикта в ответе LLM"},'
                '{"topic":"тема вторая","start_msg_id":104,"end_msg_id":106,'
                '"confidence":"medium","resolution":"unclear","resolution_reason":"нет вердикта в ответе LLM"}'
                "]}"
            )
        if sid == "S-tg-2":
            return (
                '{"schema_version":"1.1","session_id":"S-tg-2","cases":['
                '{"topic":"одна тема","start_msg_id":201,"end_msg_id":202,'
                '"confidence":"high","resolution":"resolved","resolution_reason":"готово"}'
                "]}"
            )
        return f'{{"schema_version":"1.1","session_id":"{sid}","cases":[]}}'

    return FakeLlmAdapter(mapping)


@pytest.fixture
def isolated_output(tmp_path: Path) -> Path:
    return tmp_path / "out.xlsx"
