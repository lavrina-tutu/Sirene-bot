from __future__ import annotations

import sys
from pathlib import Path

import pytest

MOFS_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_ROOT))

from mofs_index.db import connect, initialize  # noqa: E402
from mofs_index.plan.migrate import ensure_plan_schema  # noqa: E402

import plan_archive as pa  # noqa: E402


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


def test_resolve_plan_binding_requires_slug_for_new_page(conn):
    with pytest.raises(pa.PlanBindingError):
        pa.resolve_plan_binding("111", conn=conn)


def test_resolve_plan_binding_creates_and_is_idempotent(conn):
    b1 = pa.resolve_plan_binding("537561928", "zd", conn=conn)
    assert b1["project_slug"] == "zd"
    # повторный вызов без project_slug — уже привязано, не требует явного slug
    b2 = pa.resolve_plan_binding("537561928", conn=conn)
    assert b2["plan_id"] == b1["plan_id"]
    assert b2["lineage_id"] == b1["lineage_id"]


def test_resolve_plan_binding_different_pages_different_lineage(conn):
    b1 = pa.resolve_plan_binding("111", "zd", conn=conn)
    b2 = pa.resolve_plan_binding("222", "zd", conn=conn)
    assert b1["plan_id"] == b2["plan_id"]  # один проект
    assert b1["lineage_id"] != b2["lineage_id"]  # разные линии


def test_store_artifact_dedup_survives_tmp_deletion(conn, tmp_path):
    src = tmp_path / "src.json"
    src.write_bytes(b'{"a": 1}')
    artifact_id, sha = pa.store_artifact(src, "prepared_json", project_slug="zd", conn=conn)
    row = conn.execute("SELECT path FROM plan_artifact WHERE artifact_id=?", (artifact_id,)).fetchone()
    archived_path = Path(row[0])
    assert archived_path.is_file()

    src.unlink()  # имитация удаления временного каталога
    assert archived_path.is_file()
    assert archived_path.read_bytes() == b'{"a": 1}'

    import hashlib
    assert sha == hashlib.sha256(b'{"a": 1}').hexdigest()

    # повторный вызов с теми же байтами не создаёт вторую копию
    artifact_id2, sha2 = pa.store_artifact(b'{"a": 1}', "prepared_json", project_slug="zd", conn=conn)
    assert artifact_id2 == artifact_id
    assert sha2 == sha
    count = conn.execute("SELECT COUNT(*) FROM plan_artifact").fetchone()[0]
    assert count == 1
