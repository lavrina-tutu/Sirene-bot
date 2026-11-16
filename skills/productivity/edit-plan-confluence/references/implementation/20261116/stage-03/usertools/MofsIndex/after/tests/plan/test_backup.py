"""Тесты online backup/restore (P0.SAFE.5/7)."""
from __future__ import annotations

import pytest

from mofs_index.db import connect, initialize
from mofs_index.plan.migrate import ensure_plan_schema
from mofs_index.plan.backup import backup_to, verify_backup, restore_from, BackupError


@pytest.fixture
def src_db(tmp_path):
    db_path = tmp_path / "src.sqlite"
    conn = connect(db_path, durable=True)
    initialize(conn)
    ensure_plan_schema(conn)
    conn.execute("INSERT INTO meta(key, value) VALUES ('probe', 'hello')")
    conn.commit()
    conn.close()
    return db_path


def test_backup_to_creates_valid_copy(tmp_path, src_db):
    dest = tmp_path / "backup.sqlite"
    report = backup_to(dest, src_db)
    assert report.ok
    assert dest.exists()

    conn = connect(dest, read_only=True)
    row = conn.execute("SELECT value FROM meta WHERE key='probe'").fetchone()
    assert row[0] == "hello"
    conn.close()


def test_backup_to_idempotent_overwrite(tmp_path, src_db):
    dest = tmp_path / "backup.sqlite"
    backup_to(dest, src_db)
    report2 = backup_to(dest, src_db)  # повторный запуск не должен падать
    assert report2.ok


def test_backup_missing_source_raises(tmp_path):
    with pytest.raises(BackupError):
        backup_to(tmp_path / "out.sqlite", tmp_path / "does-not-exist.sqlite")


def test_verify_backup_ok(tmp_path, src_db):
    dest = tmp_path / "backup.sqlite"
    backup_to(dest, src_db)
    report = verify_backup(dest)
    assert report.ok


def test_restore_dry_run_does_not_write(tmp_path, src_db):
    backup_path = tmp_path / "backup.sqlite"
    backup_to(backup_path, src_db)

    restore_dest = tmp_path / "restored.sqlite"
    report = restore_from(backup_path, restore_dest, dry_run=True)
    assert report.ok
    assert not restore_dest.exists(), "dry-run не должен ничего писать"


def test_restore_without_confirm_is_noop(tmp_path, src_db):
    backup_path = tmp_path / "backup.sqlite"
    backup_to(backup_path, src_db)
    restore_dest = tmp_path / "restored2.sqlite"
    # dry_run=False, но confirm не передан -> restore_from требует оба условия
    report = restore_from(backup_path, restore_dest, dry_run=False, confirm=False)
    assert report.ok
    assert not restore_dest.exists()


def test_restore_real_reproduces_data(tmp_path, src_db):
    backup_path = tmp_path / "backup.sqlite"
    backup_to(backup_path, src_db)
    restore_dest = tmp_path / "restored3.sqlite"

    report = restore_from(backup_path, restore_dest, dry_run=False, confirm=True)
    assert report.ok
    assert restore_dest.exists()

    conn = connect(restore_dest, read_only=True)
    row = conn.execute("SELECT value FROM meta WHERE key='probe'").fetchone()
    assert row[0] == "hello"
    conn.close()


def test_backup_preserves_unresolved_receipts_and_wal_events(tmp_path,src_db):
    from mofs_index.plan import writer as w,query as q
    conn=connect(src_db,durable=True)
    operation=w.create_operation(conn,w.OperationSpec("save",context_json='{"frozen":"context"}'))
    item=w.create_import_item(conn,w.ImportItemSpec(operation,"pending.mpp","/input/pending.mpp"))
    attempt=w.begin_operation_attempt(conn,operation,item)
    event=w.record_operation_event(conn,attempt,"input_pending")
    dest=tmp_path/"migration-backup.sqlite"
    assert backup_to(dest,src_db).ok
    assert verify_backup(dest).ok
    copy=connect(dest,read_only=True)
    assert q.get_import_item(copy,item)==q.get_import_item(conn,item)
    assert q.get_operation_events(copy,operation)==q.get_operation_events(conn,operation)
    assert q.get_operation_events(copy,operation)[-1]["event_id"]==event
    copy.close();conn.close()
