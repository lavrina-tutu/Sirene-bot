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
        "0004_phase3_analysis", "0005_phase3_fts", "0006_publication_trust",
    ]
    assert second == []


def test_applied_migrations_records_checksum(conn):
    ensure_plan_schema(conn)
    rows = applied_migrations(conn)
    assert len(rows) == 6
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


def test_legacy_false_confirmed_preserves_history_and_downgrades_trust(conn, monkeypatch):
    import mofs_index.plan.migrate as migrate
    from mofs_index.plan import writer as w
    all_migrations = migrate.MIGRATIONS
    monkeypatch.setattr(migrate, "MIGRATIONS", all_migrations[:5])
    ensure_plan_schema(conn)
    plan = w.ensure_plan(conn, "legacy-test")
    lineage = w.ensure_lineage(conn, plan, "confluence", page_id="test-page")
    attempt = w.begin_attempt(conn, w.AttemptSpec(plan_id=plan, lineage_id=lineage))
    w.set_attempt_status(conn, attempt, "confirmed")
    w.record_event(conn, attempt, "storage_put", "confirmed", detail="legacy false success fixture")
    artifact = w.record_artifact(conn, "a" * 64, "prepared_json", "fixture.json")
    conn.execute("INSERT INTO plan_publication(publication_id,plan_id,lineage_id,artifact_id,source_namespace,attachment_id,attachment_version,page_id,recorded_at,raw_sha256) VALUES ('legacy-pub',?,?,?,?,?,1,'test-page','2026-01-01',?)",
                 (plan,lineage,artifact,"confluence","actual-id","a" * 64))
    conn.execute("INSERT INTO plan_page_observation(observation_id,plan_id,page_id,page_version,fetched_at,itogo_raw,quality) VALUES ('legacy-obs',?,'test-page',1,'2026-01-01','unverified PUT body','ok')",(plan,))
    conn.commit()
    w.link_publication_page(conn,"legacy-pub","legacy-obs",confidence="confirmed")
    snap = w.ingest_snapshot(conn, w.SnapshotSpec(plan_id=plan,lineage_id=lineage,representation="mpp"))
    w.select_snapshot_baseline(conn,lineage,snap,is_explicit=True,basis="owner")
    w.select_plan_baseline(conn,plan,snap,0,is_explicit=True,basis="owner")
    preserved = ("plan_attempt_event","plan_publication_page_link","plan_snapshot","plan_snapshot_selection","plan_baseline_selection","plan_artifact")
    before = {name:[tuple(r) for r in conn.execute("SELECT * FROM " + name)] for name in preserved}
    publication_before = tuple(conn.execute("SELECT * FROM plan_publication").fetchone())
    attempt_before = tuple(conn.execute("SELECT * FROM plan_import_attempt").fetchone())
    monkeypatch.setattr(migrate,"MIGRATIONS",all_migrations)
    assert ensure_plan_schema(conn) == ["0006_publication_trust"]
    for name, rows in before.items():
        assert [tuple(r) for r in conn.execute("SELECT * FROM " + name)] == rows
    assert tuple(conn.execute("SELECT * FROM plan_publication").fetchone())[:len(publication_before)] == publication_before
    assert tuple(conn.execute("SELECT * FROM plan_import_attempt").fetchone())[:len(attempt_before)] == attempt_before
    assert tuple(conn.execute("SELECT trust,historical_status FROM plan_publication").fetchone()) == ("legacy_unverified","registered")
    assert tuple(conn.execute("SELECT status,historical_status FROM plan_import_attempt").fetchone()) == ("confirmed","confirmed")
    assert conn.execute("SELECT verification_status FROM plan_page_observation").fetchone()[0] == "not_verified"
    assert ensure_plan_schema(conn) == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_applied_migration_checksum_mismatch_rejected(conn):
    ensure_plan_schema(conn)
    conn.execute("UPDATE plan_schema_migration SET checksum='wrong' WHERE migration_id='0006_publication_trust'")
    conn.commit()
    with pytest.raises(ValueError,match="checksum mismatch"):
        ensure_plan_schema(conn)
