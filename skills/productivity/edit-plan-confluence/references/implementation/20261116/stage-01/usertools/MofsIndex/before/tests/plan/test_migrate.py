"""Тесты миграционного раннера plan_* (P0.SAFE.3)."""
from __future__ import annotations

import pytest

from mofs_index.db import connect, initialize
from mofs_index.plan.migrate import ensure_plan_schema, applied_migrations


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "index.sqlite"
    c = connect(db_path, durable=True)
    initialize(c)
    yield c
    c.close()


def test_ensure_plan_schema_creates_registry(conn):
    applied = ensure_plan_schema(conn)
    assert "0001_phase0_baseline" in applied

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='plan_schema_migration'"
    ).fetchall()
    assert len(rows) == 1


def test_ensure_plan_schema_idempotent_across_calls(conn):
    first = ensure_plan_schema(conn)
    second = ensure_plan_schema(conn)
    assert first == [
        "0001_phase0_baseline", "0002_phase1_core", "0003_phase2_snapshot",
        "0004_phase3_analysis", "0005_phase3_fts",
    ]
    assert second == []


def test_applied_migrations_records_checksum(conn):
    ensure_plan_schema(conn)
    rows = applied_migrations(conn)
    assert len(rows) == 5
    migration_id, applied_at, checksum = rows[0]
    assert migration_id == "0001_phase0_baseline"
    assert applied_at  # не пусто
    assert len(checksum) == 64  # sha256 hex
    migration_id2, _, checksum2 = rows[1]
    assert migration_id2 == "0002_phase1_core"
    assert len(checksum2) == 64
    migration_id3, _, checksum3 = rows[2]
    assert migration_id3 == "0003_phase2_snapshot"
    assert len(checksum3) == 64
    migration_id4, _, checksum4 = rows[3]
    assert migration_id4 == "0004_phase3_analysis"
    assert len(checksum4) == 64
    migration_id5, _, checksum5 = rows[4]
    assert migration_id5 == "0005_phase3_fts"
    assert len(checksum5) == 64
