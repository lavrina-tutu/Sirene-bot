"""Тесты typed query API (P3.RAG.1-4/6, R-023/R-026, AC-124/125/126/129)."""
from __future__ import annotations

import json

import pytest

from mofs_index.db import connect, initialize
from mofs_index.plan.migrate import ensure_plan_schema
from mofs_index.plan import writer as w
from mofs_index.plan import query as q


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "index.sqlite"
    c = connect(db_path, durable=True)
    initialize(c)
    ensure_plan_schema(c)
    yield c
    c.close()


def _publish_json(conn, plan_id, lineage_id, version, body, filename="gantt.json", tmp_path=None):
    import hashlib
    raw = json.dumps(body).encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    path = artifact_dir / f"{sha}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    artifact_id = w.record_artifact(conn, sha, "downloaded_json", str(path), size_bytes=len(raw))
    return w.record_publication(conn, w.PublicationSpec(
        plan_id=plan_id, lineage_id=lineage_id, artifact_id=artifact_id,
        source_namespace="confluence", attachment_id="att1", attachment_version=version,
        page_id="p1", filename=filename, raw_sha256=sha,
    ))


def test_resolve_plan_found_and_not_found(conn):
    plan_id = w.ensure_plan(conn, "zd", name="zd")
    res = q.resolve_plan(conn, "zd")
    assert res["plan_id"] == plan_id
    assert "receipt" in res

    missing = q.resolve_plan(conn, "nonexistent")
    assert missing["result_class"] == "insufficient_data"


def test_diff_versions_identical_content(conn, tmp_path):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": []}], "dependenciesData": []}
    _publish_json(conn, plan_id, lineage_id, 1, body, tmp_path=tmp_path)
    _publish_json(conn, plan_id, lineage_id, 2, body, tmp_path=tmp_path)

    d = q.diff_versions(conn, plan_id,
                         {"kind": "publication", "attachment_version": 1},
                         {"kind": "publication", "attachment_version": 2})
    assert d["content_identical"] is True
    assert d["receipt"]["hash_a"] == d["receipt"]["hash_b"]


def test_diff_versions_detects_removed_link_and_finish_shift(conn, tmp_path):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body_a = {
        "eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": [
            {"id": 2, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-05T18:00:00", "duration": 4.0, "children": []},
        ]}],
        "dependenciesData": [{"from": 1, "to": 2}],
    }
    body_b = {
        "eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-24T18:00:00", "duration": 23.0, "children": [
            {"id": 2, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-05T18:00:00", "duration": 4.0, "children": []},
        ]}],
        "dependenciesData": [],
    }
    _publish_json(conn, plan_id, lineage_id, 1, body_a, tmp_path=tmp_path)
    _publish_json(conn, plan_id, lineage_id, 2, body_b, tmp_path=tmp_path)

    d = q.diff_versions(conn, plan_id,
                         {"kind": "publication", "attachment_version": 1},
                         {"kind": "publication", "attachment_version": 2})
    assert d["content_identical"] is False
    assert {"from": 1, "to": 2} in d["links_removed"]
    assert d["root"]["finish_delta_calendar_days"] == 14


def test_diff_versions_representation_mismatch_is_explicit(conn):
    plan_id = w.ensure_plan(conn, "zd")
    d = q.diff_versions(conn, plan_id,
                         {"kind": "publication", "attachment_version": 1},
                         {"kind": "snapshot", "snapshot_id": "snap1"})
    assert d["result_class"] == "representation_mismatch"


def test_task_history_by_uid_and_caveat(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "mpp_archive")
    spec_a = w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp",
        tasks=(w.TaskVersionSpec(task_key="t744", uid="744", name="Task", finish_raw="2026-11-12T18:00"),),
    )
    spec_b = w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp",
        tasks=(w.TaskVersionSpec(task_key="t744", uid="744", name="Task", finish_raw="2026-11-16T18:00"),),
    )
    w.ingest_snapshot(conn, spec_a)
    w.ingest_snapshot(conn, spec_b)

    hist = q.task_history(conn, plan_id, "744")
    assert hist["finish_delta_calendar_days"] == 4
    assert "caveat" in hist
    assert hist["receipt"]["mapping"] == "confirmed_uid"


def test_task_history_unknown_uid_is_insufficient_data(conn):
    plan_id = w.ensure_plan(conn, "zd")
    hist = q.task_history(conn, plan_id, "999999")
    assert hist["result_class"] == "insufficient_data"


def test_diff_snapshots_working_drift_unavailable_without_timezone(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "mpp_archive")
    snap_a = w.ingest_snapshot(conn, w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp", timezone_hint=None,
        tasks=(w.TaskVersionSpec(task_key="t1", uid="1", outline_level=1, finish_raw="2026-01-10"),),
    ))
    snap_b = w.ingest_snapshot(conn, w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp", timezone_hint=None,
        tasks=(w.TaskVersionSpec(task_key="t1", uid="1", outline_level=1, finish_raw="2026-01-14"),),
    ))
    d = q.diff_versions(conn, plan_id, {"kind": "snapshot", "snapshot_id": snap_a}, {"kind": "snapshot", "snapshot_id": snap_b})
    assert d["working_drift"] == "unavailable"


def test_compare_baseline_missing_slot_not_fabricated(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "mpp_archive")
    snap = w.ingest_snapshot(conn, w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp",
        tasks=(w.TaskVersionSpec(task_key="t1", uid="1", finish_raw="2026-01-10"),),
    ))
    result = q.compare_baseline(conn, plan_id, snap, baseline_slot=0)
    assert result["missing_baseline_count"] == 1
    assert result["comparisons"][0]["status"] == "baseline_missing"


def test_explain_finish_change_on_publications_gives_observed_diff_not_validated(conn, tmp_path):
    """AC-139: вопрос про историческую пару публикаций (без UID) не выдаёт
    validated_attribution — честный observed_diff с блокерами."""
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body_a = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": []}], "dependenciesData": []}
    body_b = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-24T18:00:00", "duration": 23.0, "children": []}], "dependenciesData": []}
    _publish_json(conn, plan_id, lineage_id, 4, body_a, tmp_path=tmp_path)
    _publish_json(conn, plan_id, lineage_id, 5, body_b, tmp_path=tmp_path)

    result = q.explain_finish_change(
        conn, plan_id,
        {"kind": "publication", "attachment_version": 4},
        {"kind": "publication", "attachment_version": 5},
    )
    assert result["result_class"] == "observed_diff"
    assert result["blockers"]
