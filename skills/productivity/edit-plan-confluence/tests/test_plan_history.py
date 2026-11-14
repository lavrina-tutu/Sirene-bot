from __future__ import annotations

import hashlib
import socket
import sys
from pathlib import Path

import pytest

MOFS_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_ROOT))

from mofs_index.db import connect, initialize  # noqa: E402
from mofs_index.plan.migrate import ensure_plan_schema  # noqa: E402

from conf_client import ConfluenceError  # noqa: E402
import plan_history as ph  # noqa: E402


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
    return wv


class FakeHistoryClient:
    """Имитирует 6 версий ZD: v1-v3 одинаковый JSON, v4/v5/v6 разные."""

    def __init__(self, failures: dict[int, Exception] | None = None):
        self.failures = failures or {}
        self._blobs = {
            1: b'{"rev":"a"}', 2: b'{"rev":"a"}', 3: b'{"rev":"a"}',
            4: b'{"rev":"b"}', 5: b'{"rev":"c"}', 6: b'{"rev":"d"}',
        }

    def list_attachments(self, page_id):
        return [{"id": "537561929", "title": "gantt-chart-efd25ba.json", "version": {"number": 6}}]

    def download_attachment(self, page_id, filename, version=None):
        if version in self.failures:
            raise self.failures[version]
        return self._blobs[version]


def test_import_history_six_events_four_unique_hashes(conn):
    client = FakeHistoryClient()
    report = ph.import_history(client, "537561928", "537561929", range(1, 7), conn=conn)
    assert report.event_count == 6
    assert len(report.unique_hashes) == 4


def test_import_history_repeat_does_not_increase_counts(conn):
    client = FakeHistoryClient()
    ph.import_history(client, "537561928", "537561929", range(1, 7), conn=conn)
    report2 = ph.import_history(client, "537561928", "537561929", range(1, 7), conn=conn)
    assert report2.event_count == 6
    assert len(report2.unique_hashes) == 4
    count = conn.execute("SELECT COUNT(*) FROM plan_publication").fetchone()[0]
    assert count == 6  # не выросло повторным импортом


def test_import_history_distinguishes_403_404_timeout(conn):
    client = FakeHistoryClient(failures={
        2: ConfluenceError(403, "forbidden"),
        3: ConfluenceError(404, "not found"),
        4: socket.timeout("timed out"),
    })
    report = ph.import_history(client, "537561928", "537561929", range(1, 7), conn=conn)
    by_version = {o.version: o.status for o in report.outcomes}
    assert by_version[2] == "forbidden"
    assert by_version[3] == "not_found"
    assert by_version[4] == "timeout"
    assert by_version[1] == "ok"
    assert by_version[5] == "ok"
    assert by_version[6] == "ok"


def test_import_history_resume_attempt_id_does_not_duplicate_attempt(conn):
    """Хвост Фазы 1 (P1.W1.10): внешний resume-ключ переиспользует
    существующую строку plan_import_attempt, не плодит новую."""
    client = FakeHistoryClient()
    report1 = ph.import_history(client, "537561928", "537561929", range(1, 7), conn=conn)
    assert report1.attempt_id

    report2 = ph.import_history(
        client, "537561928", "537561929", range(1, 7), conn=conn,
        resume_attempt_id=report1.attempt_id,
    )
    assert report2.attempt_id == report1.attempt_id

    count = conn.execute("SELECT COUNT(*) FROM plan_import_attempt").fetchone()[0]
    assert count == 1


def test_import_history_without_resume_key_creates_new_attempt_each_call(conn):
    client = FakeHistoryClient()
    report1 = ph.import_history(client, "537561928", "537561929", range(1, 7), conn=conn)
    report2 = ph.import_history(client, "537561928", "537561929", range(1, 7), conn=conn)
    assert report1.attempt_id != report2.attempt_id
    count = conn.execute("SELECT COUNT(*) FROM plan_import_attempt").fetchone()[0]
    assert count == 2


def test_import_history_missing_version_recorded_in_quality_issue(conn):
    """Хвост Фазы 2 (AC-111): пропуски версий получают персистентную
    отметку plan_quality_issue, не только эфемерное событие попытки."""
    client = FakeHistoryClient(failures={
        2: ConfluenceError(403, "forbidden"),
        4: socket.timeout("timed out"),
    })
    ph.import_history(client, "537561928", "537561929", range(1, 7), conn=conn)
    rows = conn.execute(
        "SELECT detail FROM plan_quality_issue WHERE issue_kind='missing_source_version' "
        "ORDER BY detail"
    ).fetchall()
    assert len(rows) == 2
    details = " ".join(r[0] for r in rows)
    assert "version=2" in details and "status=forbidden" in details
    assert "version=4" in details and "status=timeout" in details


def test_find_mpp_by_hash_missing_file_not_fabricated(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    present = root / "present.mpp"
    present.write_bytes(b"real-bytes")
    present_hash = hashlib.sha256(b"real-bytes").hexdigest()
    known = {"present": present_hash, "missing": "f" * 64}
    found = ph.find_mpp_by_hash(known, [root])
    assert found["present"] == present
    assert found["missing"] is None
