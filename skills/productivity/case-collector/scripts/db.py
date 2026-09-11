"""Read-only SQLite access to Hermes state.db sessions and messages."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

CONNECT_TIMEOUT_SEC: float = 30.0
REQUIRED_SESSION_COLS: tuple[str, ...] = ("id", "source", "started_at")
REQUIRED_MESSAGE_COLS: tuple[str, ...] = ("id", "session_id", "role", "content", "timestamp")
OPTIONAL_SESSION_COLS: tuple[str, ...] = (
    "user_id",
    "model",
    "parent_session_id",
    "ended_at",
    "end_reason",
    "message_count",
    "title",
    "session_key",
    "chat_id",
    "chat_type",
    "thread_id",
    "display_name",
    "origin_json",
    "profile_name",
    "last_activity_at",
    "archived",
)
OPTIONAL_MESSAGE_COLS: tuple[str, ...] = (
    "tool_name",
    "token_count",
    "active",
    "compacted",
)
WRITE_SQL_HEADS: tuple[str, ...] = (
    "insert",
    "update",
    "delete",
    "replace",
    "drop",
    "alter",
    "create",
    "vacuum",
    "reindex",
    "attach",
    "detach",
    "pragma wal_",
    "pragma journal_",
)

_ALLOWED_TABLES = frozenset({"sessions", "messages"})


class DbError(Exception):
    pass


class DbNotFoundError(DbError):
    pass


class SchemaMismatchError(DbError):
    pass


class WriteAttemptError(DbError):
    pass


@dataclass
class SessionRow:
    id: str
    source: str
    started_at: float
    user_id: str | None = None
    title: str | None = None
    session_key: str | None = None
    chat_id: str | None = None
    chat_type: str | None = None
    thread_id: str | None = None
    display_name: str | None = None
    origin_json: str | None = None
    profile_name: str | None = None
    message_count: int | None = None
    archived: int | None = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class MessageRow:
    id: int
    session_id: str
    role: str
    content: str | None
    timestamp: float
    tool_name: str | None = None
    token_count: int | None = None
    active: int | None = None
    compacted: int | None = None


def sqlite_uri(path: Path) -> str:
    resolved = path.resolve().as_posix()
    return f"file:{resolved}?mode=ro"


def _is_allowed_sql(sql: str) -> bool:
    stripped = sql.lstrip().lower()
    if stripped.startswith("select"):
        return True
    if stripped.startswith("pragma query_only"):
        return True
    if stripped.startswith("pragma table_info("):
        rest = stripped[len("pragma table_info(") :].rstrip(")")
        if rest in ("sessions", "messages"):
            return True
        return False
    for head in WRITE_SQL_HEADS:
        if stripped.startswith(head):
            return False
    return False


def execute_ro(
    conn: sqlite3.Connection, sql: str, params: tuple | dict = ()
) -> sqlite3.Cursor:
    if not _is_allowed_sql(sql):
        raise WriteAttemptError(f"SQL not allowed in read-only mode: {sql[:80]!r}")
    return conn.execute(sql, params)


def connect_ro(path: Path, timeout: float = CONNECT_TIMEOUT_SEC) -> sqlite3.Connection:
    if not path.exists():
        raise DbNotFoundError(f"Database file not found: {path}")
    uri = sqlite_uri(path)
    conn = sqlite3.connect(uri, uri=True, timeout=timeout, check_same_thread=True)
    conn.row_factory = sqlite3.Row
    execute_ro(conn, "PRAGMA query_only=ON")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Table not allowed: {table}")
    cur = execute_ro(conn, f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def assert_required_schema(conn: sqlite3.Connection) -> None:
    for table, required in (
        ("sessions", REQUIRED_SESSION_COLS),
        ("messages", REQUIRED_MESSAGE_COLS),
    ):
        try:
            cols = set(table_columns(conn, table))
        except sqlite3.OperationalError as e:
            raise SchemaMismatchError(f"Missing table {table}: {e}") from e
        missing = [c for c in required if c not in cols]
        if missing:
            raise SchemaMismatchError(
                f"Table {table} missing required columns: {', '.join(missing)}"
            )


def present_optional_columns(
    conn: sqlite3.Connection, table: str, candidates: tuple[str, ...]
) -> list[str]:
    cols = set(table_columns(conn, table))
    return [c for c in candidates if c in cols]


def _session_row_from_row(row: sqlite3.Row, optional: list[str]) -> SessionRow:
    data = dict(row)
    known = {
        "id",
        "source",
        "started_at",
        "user_id",
        "title",
        "session_key",
        "chat_id",
        "chat_type",
        "thread_id",
        "display_name",
        "origin_json",
        "profile_name",
        "message_count",
        "archived",
    }
    extra = {k: v for k, v in data.items() if k not in known and k in optional}
    return SessionRow(
        id=data["id"],
        source=data["source"],
        started_at=float(data["started_at"]),
        user_id=data.get("user_id"),
        title=data.get("title"),
        session_key=data.get("session_key"),
        chat_id=data.get("chat_id"),
        chat_type=data.get("chat_type"),
        thread_id=data.get("thread_id"),
        display_name=data.get("display_name"),
        origin_json=data.get("origin_json"),
        profile_name=data.get("profile_name"),
        message_count=data.get("message_count"),
        archived=data.get("archived"),
        extra=extra,
    )


def _message_row_from_row(row: sqlite3.Row) -> MessageRow:
    data = dict(row)
    return MessageRow(
        id=int(data["id"]),
        session_id=data["session_id"],
        role=data["role"],
        content=data.get("content"),
        timestamp=float(data["timestamp"]),
        tool_name=data.get("tool_name"),
        token_count=data.get("token_count"),
        active=data.get("active"),
        compacted=data.get("compacted"),
    )


def _source_filter_sql(
    exclude_sources: Sequence[str],
    include_sources: Sequence[str] | None,
) -> tuple[str, list]:
    parts: list[str] = []
    params: list = []
    if exclude_sources:
        placeholders = ",".join("?" * len(exclude_sources))
        parts.append(f"s.source NOT IN ({placeholders})")
        params.extend(exclude_sources)
    if include_sources is not None:
        placeholders = ",".join("?" * len(include_sources))
        parts.append(f"s.source IN ({placeholders})")
        params.extend(include_sources)
    return (" AND ".join(parts), params) if parts else ("", [])


def select_sessions(
    conn: sqlite3.Connection,
    *,
    since_epoch: float,
    until_epoch: float,
    exclude_sources: Sequence[str],
    include_sources: Sequence[str] | None,
    limit: int | None,
) -> list[SessionRow]:
    sess_opt = present_optional_columns(conn, "sessions", OPTIONAL_SESSION_COLS)
    msg_opt = present_optional_columns(conn, "messages", OPTIONAL_MESSAGE_COLS)
    has_active = "active" in msg_opt
    has_archived = "archived" in sess_opt

    select_cols = ["s.id", "s.source", "s.started_at"]
    for c in sess_opt:
        select_cols.append(f"s.{c}")

    active_clause = ""
    if has_active:
        active_clause = " AND (m.active = 1 OR m.active IS NULL)"

    archived_clause = ""
    if has_archived:
        archived_clause = "(s.archived IS NULL OR s.archived != 1)"

    src_sql, src_params = _source_filter_sql(exclude_sources, include_sources)

    where_parts = [
        "s.started_at >= ?",
        "s.started_at < ?",
        archived_clause.strip(),
        f"""EXISTS (
            SELECT 1 FROM messages m
            WHERE m.session_id = s.id
              AND m.role = 'user'
              AND m.content IS NOT NULL
              AND TRIM(m.content) <> ''
              {active_clause}
        )""",
    ]
    if src_sql:
        where_parts.append(src_sql)

    where_sql = " AND ".join(p for p in where_parts if p)

    sql = f"""
        SELECT {", ".join(select_cols)}
        FROM sessions s
        WHERE {where_sql}
        ORDER BY s.started_at ASC
    """
    params: list = [since_epoch, until_epoch, *src_params]
    cur = execute_ro(conn, sql, tuple(params))
    rows = [_session_row_from_row(r, sess_opt) for r in cur.fetchall()]
    if limit is not None:
        rows = rows[:limit]
    return rows


def count_sessions_with_activity_in_window_started_outside(
    conn: sqlite3.Connection,
    *,
    since_epoch: float,
    until_epoch: float,
    exclude_sources: Sequence[str],
    include_sources: Sequence[str] | None,
) -> int:
    sess_opt = present_optional_columns(conn, "sessions", OPTIONAL_SESSION_COLS)
    has_archived = "archived" in sess_opt
    archived_clause = ""
    if has_archived:
        archived_clause = "(s.archived IS NULL OR s.archived != 1)"

    src_sql, src_params = _source_filter_sql(exclude_sources, include_sources)

    where_parts = [
        "(s.started_at < ? OR s.started_at >= ?)",
        archived_clause.strip(),
        """EXISTS (
            SELECT 1 FROM messages m
            WHERE m.session_id = s.id
              AND m.timestamp >= ?
              AND m.timestamp < ?
        )""",
    ]
    if src_sql:
        where_parts.append(src_sql)

    where_sql = " AND ".join(p for p in where_parts if p)
    sql = f"SELECT COUNT(*) FROM sessions s WHERE {where_sql}"
    params: list = [since_epoch, until_epoch, since_epoch, until_epoch, *src_params]
    cur = execute_ro(conn, sql, tuple(params))
    return int(cur.fetchone()[0])


def fetch_messages(conn: sqlite3.Connection, session_id: str) -> list[MessageRow]:
    msg_opt = present_optional_columns(conn, "messages", OPTIONAL_MESSAGE_COLS)
    cols = ["id", "session_id", "role", "content", "timestamp"]
    for c in msg_opt:
        if c not in cols:
            cols.append(c)
    sql = f"""
        SELECT {", ".join(cols)}
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC, id ASC
    """
    cur = execute_ro(conn, sql, (session_id,))
    return [_message_row_from_row(r) for r in cur.fetchall()]
