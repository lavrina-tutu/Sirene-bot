from __future__ import annotations

import sqlite3
import stat
from pathlib import Path
from unittest import mock

import pytest

from db import (
    DbNotFoundError,
    SchemaMismatchError,
    WriteAttemptError,
    connect_ro,
    count_sessions_with_activity_in_window_started_outside,
    execute_ro,
    select_sessions,
    sqlite_uri,
)
from conftest import TEST_SINCE, TEST_UNTIL, TS_IN, TS_OUT_START


def test_connect_ro_uri_mode(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    sqlite3.connect(db).close()
    captured = {}
    real_connect = sqlite3.connect

    def fake_connect(database, timeout=5.0, **kwargs):
        captured["uri"] = database
        captured["timeout"] = timeout
        captured["kwargs"] = kwargs
        return real_connect(str(db))

    monkeypatch.setattr(sqlite3, "connect", fake_connect)
    connect_ro(db)
    assert "mode=ro" in captured["uri"]
    assert "immutable" not in captured["uri"]


def test_query_only_pragma(fixture_db):
    conn = connect_ro(fixture_db)
    cur = execute_ro(conn, "PRAGMA query_only")
    row = cur.fetchone()
    assert row[0] == 1
    conn.close()


def test_execute_ro_rejects_insert(fixture_db):
    conn = connect_ro(fixture_db)
    with pytest.raises(WriteAttemptError):
        execute_ro(conn, "INSERT INTO sessions VALUES ('x','y',1.0)")
    conn.close()


def test_execute_ro_rejects_wal_checkpoint(fixture_db):
    conn = connect_ro(fixture_db)
    with pytest.raises(WriteAttemptError):
        execute_ro(conn, "PRAGMA wal_checkpoint")
    conn.close()


def test_no_write_mtime(fixture_db):
    before = fixture_db.stat()
    conn = connect_ro(fixture_db)
    select_sessions(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=["cron"],
        include_sources=None,
        limit=None,
    )
    conn.close()
    after = fixture_db.stat()
    assert before.st_mtime == after.st_mtime
    assert before.st_size == after.st_size


def test_missing_file(tmp_path):
    with pytest.raises(DbNotFoundError):
        connect_ro(tmp_path / "nope.db")


def test_missing_required_column(tmp_path):
    db = tmp_path / "bad.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sessions (id TEXT, source TEXT)")
    conn.execute(
        "CREATE TABLE messages (id INTEGER, session_id TEXT, role TEXT, content TEXT, timestamp REAL)"
    )
    conn.commit()
    conn.close()
    conn_ro = connect_ro(db)
    with pytest.raises(SchemaMismatchError):
        from db import assert_required_schema

        assert_required_schema(conn_ro)
    conn_ro.close()


def test_optional_column_degrade(fixture_db_minimal_cols):
    conn = connect_ro(fixture_db_minimal_cols)
    rows = select_sessions(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=[],
        include_sources=None,
        limit=None,
    )
    assert len(rows) == 1
    assert rows[0].thread_id is None
    conn.close()


def test_window_by_started_at(fixture_db):
    conn = connect_ro(fixture_db)
    rows = select_sessions(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=["cron", "kanban", "subagent"],
        include_sources=None,
        limit=None,
    )
    ids = {r.id for r in rows}
    assert "S-outside-win" not in ids
    conn.close()


def test_exclude_sources(fixture_db):
    conn = connect_ro(fixture_db)
    rows = select_sessions(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=["cron", "kanban", "subagent"],
        include_sources=None,
        limit=None,
    )
    sources = {r.source for r in rows}
    assert "cron" not in sources
    assert "kanban" not in sources
    assert "subagent" not in sources
    conn.close()


def test_include_sources_intersection(fixture_db):
    conn = connect_ro(fixture_db)
    rows = select_sessions(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=["cli"],
        include_sources=["telegram", "cli"],
        limit=None,
    )
    sources = {r.source for r in rows}
    assert "cli" not in sources
    assert "telegram" in sources
    conn.close()


def test_archived_excluded(fixture_db):
    conn = connect_ro(fixture_db)
    rows = select_sessions(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=[],
        include_sources=None,
        limit=None,
    )
    assert "S-arch" not in {r.id for r in rows}
    conn.close()


def test_no_user_message_excluded(fixture_db):
    conn = connect_ro(fixture_db)
    rows = select_sessions(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=[],
        include_sources=None,
        limit=None,
    )
    assert "S-tool" not in {r.id for r in rows}
    conn.close()


def test_oq4_counter(fixture_db):
    conn = connect_ro(fixture_db)
    n = count_sessions_with_activity_in_window_started_outside(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=[],
        include_sources=None,
    )
    assert n >= 1
    rows = select_sessions(
        conn,
        since_epoch=TEST_SINCE.timestamp(),
        until_epoch=TEST_UNTIL.timestamp(),
        exclude_sources=[],
        include_sources=None,
        limit=None,
    )
    assert "S-out" not in {r.id for r in rows}
    conn.close()


def test_no_fts_in_sql(scripts_dir):
    text = (scripts_dir / "db.py").read_text(encoding="utf-8")
    assert "messages_fts" not in text


def test_timeout_default(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    sqlite3.connect(db).close()
    captured = {}
    real_connect = sqlite3.connect

    def fake_connect(database, timeout=5.0, **kwargs):
        captured["timeout"] = timeout
        return real_connect(str(db))

    monkeypatch.setattr(sqlite3, "connect", fake_connect)
    connect_ro(db)
    assert captured["timeout"] >= 30
