from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

MOFS_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_ROOT))

from mofs_index.db import connect, initialize  # noqa: E402
from mofs_index.plan.migrate import ensure_plan_schema  # noqa: E402
from mofs_index.plan import writer as plan_writer  # noqa: E402

import plan_archive as pa  # noqa: E402
import plan_reconcile as pr  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "index.sqlite"
    c = connect(db_path, durable=True)
    initialize(c)
    ensure_plan_schema(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def isolate_workvault(tmp_path, monkeypatch):
    wv = tmp_path / "WorkVault"
    monkeypatch.setattr("plan_archive.get_workvault_path", lambda: wv)
    monkeypatch.setattr("plan_receipt.get_workvault_path", lambda: wv)
    return wv


class FakeClient:
    def __init__(self, attachments, blobs):
        self._attachments = attachments
        self._blobs = blobs  # (attach_id, version) -> bytes

    def list_attachments(self, page_id):
        return self._attachments

    def download_attachment(self, page_id, filename, version=None):
        key = (filename, version)
        if key not in self._blobs:
            raise FileNotFoundError(key)
        return self._blobs[key]


def _prep_attempt(conn, expected_sha256: str, page_id: str = "537561928") -> str:
    plan_id = plan_writer.ensure_plan(conn, "zd")
    lineage_id = plan_writer.ensure_lineage(conn, plan_id, pa.CONFLUENCE_NAMESPACE, page_id=page_id)
    return plan_writer.begin_attempt(conn, plan_writer.AttemptSpec(
        plan_id=plan_id, lineage_id=lineage_id, prepared_sha256=expected_sha256,
    ))


def test_reconcile_single_candidate_does_not_confirm_operation(conn):
    payload = b'{"ok": true}'
    sha = hashlib.sha256(payload).hexdigest()
    attempt_id = _prep_attempt(conn, sha)
    client = FakeClient(
        attachments=[{"id": "A1", "title": "gantt-chart-x.json", "version": {"number": 2}}],
        blobs={("gantt-chart-x.json", 2): payload},
    )
    outcome = pr.reconcile_attempt(client, attempt_id, conn=conn)
    assert outcome.status == "unknown"
    assert outcome.attachment_id == "A1"
    assert conn.execute("SELECT COUNT(*) FROM plan_publication").fetchone()[0] == 0
    assert conn.execute("SELECT status FROM plan_import_attempt WHERE attempt_id=?", (attempt_id,)).fetchone()[0] != "confirmed"


def test_reconcile_two_candidates_same_version_gives_unknown(conn):
    """AC-106: две одинаковые публикации при недостаточном evidence дают
    unknown, а не придуманную confirmed-связь."""
    payload = b'{"ok": true}'
    sha = hashlib.sha256(payload).hexdigest()
    attempt_id = _prep_attempt(conn, sha)
    client = FakeClient(
        attachments=[
            {"id": "A1", "title": "gantt-chart-x.json", "version": {"number": 2}},
            {"id": "A2", "title": "gantt-chart-y.json", "version": {"number": 2}},
        ],
        blobs={
            ("gantt-chart-x.json", 2): payload,
            ("gantt-chart-y.json", 2): payload,
        },
    )
    outcome = pr.reconcile_attempt(client, attempt_id, conn=conn)
    assert outcome.status == "unknown"


def test_reconcile_no_candidate_gives_unknown(conn):
    attempt_id = _prep_attempt(conn, "deadbeef" * 8)
    client = FakeClient(attachments=[], blobs={})
    outcome = pr.reconcile_attempt(client, attempt_id, conn=conn)
    assert outcome.status == "unknown"


def test_reconcile_writes_event_and_receipt(conn, tmp_path):
    payload = b"abc"
    sha = hashlib.sha256(payload).hexdigest()
    attempt_id = _prep_attempt(conn, sha)
    client = FakeClient(
        attachments=[{"id": "A1", "title": "f.json", "version": {"number": 1}}],
        blobs={("f.json", 1): payload},
    )
    pr.reconcile_attempt(client, attempt_id, conn=conn)
    events = conn.execute(
        "SELECT stage, status FROM plan_attempt_event WHERE attempt_id=?", (attempt_id,)
    ).fetchall()
    assert ("attachment_verify", "confirmed") in [tuple(r) for r in events]


def test_import_reconcile_missing_link_is_not_reimported(conn):
    from mofs_index.plan import query as q
    operation=plan_writer.create_operation(conn,plan_writer.OperationSpec("save"))
    item=plan_writer.create_import_item(conn,plan_writer.ImportItemSpec(operation,"unbound.mpp","/unbound.mpp"))
    assert pr.reconcile_import(conn,item) is None
    assert q.get_import_item(conn,item)["snapshot_id"] is None
    assert conn.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0]==0
