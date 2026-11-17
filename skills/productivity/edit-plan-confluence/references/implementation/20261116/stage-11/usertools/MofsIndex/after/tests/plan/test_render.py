"""Тесты render_plan_md (P3.MD.1-2, R-024/R-025, AC-127/128)."""
from __future__ import annotations

import json

import pytest

from mofs_index.db import connect, initialize
from mofs_index.plan.migrate import ensure_plan_schema
from mofs_index.plan import writer as w
from mofs_index.plan import render as r


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "index.sqlite"
    c = connect(db_path, durable=True)
    initialize(c)
    ensure_plan_schema(c)
    yield c
    c.close()


def _publish_json(conn, plan_id, lineage_id, version, body, tmp_path):
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
        page_id="p1", filename="gantt.json", raw_sha256=sha,
    ))


def test_render_plan_md_creates_file_with_frontmatter(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(r, "WORKVAULT_ROOT", tmp_path)
    plan_id = w.ensure_plan(conn, "testslug", name="Test", md_path="Entities/testslug/Pages/testslug.ganttchart.md")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": []}], "dependenciesData": []}
    _publish_json(conn, plan_id, lineage_id, 1, body, tmp_path)

    result = r.render_plan_md(conn, plan_id)
    assert result.status == "ok"
    assert result.generation == 1
    assert result.md_path.exists()
    text = result.md_path.read_text(encoding="utf-8")
    assert "plan_id:" in text
    assert "generation: 1" in text
    assert "testslug" in text


def test_render_plan_md_second_render_increments_generation(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(r, "WORKVAULT_ROOT", tmp_path)
    plan_id = w.ensure_plan(conn, "testslug2", md_path="Entities/testslug2/Pages/testslug2.ganttchart.md")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": []}], "dependenciesData": []}
    _publish_json(conn, plan_id, lineage_id, 1, body, tmp_path)

    r1 = r.render_plan_md(conn, plan_id)
    r2 = r.render_plan_md(conn, plan_id)
    assert r1.generation == 1
    assert r2.generation == 2


def test_render_plan_md_detects_manual_edit_as_conflict(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(r, "WORKVAULT_ROOT", tmp_path)
    plan_id = w.ensure_plan(conn, "testslug3", md_path="Entities/testslug3/Pages/testslug3.ganttchart.md")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence", page_id="p1")
    body = {"eventsData": [{"id": 1, "startDate": "2026-01-01T09:00:00", "endDate": "2026-01-10T18:00:00", "duration": 9.0, "children": []}], "dependenciesData": []}
    _publish_json(conn, plan_id, lineage_id, 1, body, tmp_path)

    r1 = r.render_plan_md(conn, plan_id)
    # Ручная правка в обход рендерера.
    r1.md_path.write_text(r1.md_path.read_text(encoding="utf-8") + "\nручная правка\n", encoding="utf-8")

    r2 = r.render_plan_md(conn, plan_id)
    assert r2.status == "conflict"
    assert r2.conflict_detail is not None


def test_render_plan_md_without_md_path_raises(conn):
    plan_id = w.ensure_plan(conn, "noslugpath")
    with pytest.raises(ValueError):
        r.render_plan_md(conn, plan_id)


def test_render_uses_exact_publication_ids_quality_and_linked_source(conn,tmp_path,monkeypatch):
    import hashlib
    monkeypatch.setattr(r,'WORKVAULT_ROOT',tmp_path)
    plan=w.ensure_plan(conn,'render-stage11',md_path='Entities/render-stage11/Pages/render-stage11.ganttchart.md')
    line=w.ensure_lineage(conn,plan,'confluence',page_id='p1')
    pub1=_publish_json(conn,plan,line,2,{'eventsData':[]},tmp_path)
    second=w.ensure_lineage(conn,plan,'confluence',page_id='p2')
    raw=b'{"eventsData":[]}'
    digest=hashlib.sha256(raw).hexdigest();path=tmp_path/'second.json';path.write_bytes(raw)
    artifact=w.record_artifact(conn,digest,'downloaded_json',str(path))
    pub2=w.record_publication(conn,w.PublicationSpec(plan,'confluence','att2',2,lineage_id=second,
        page_id='p2',filename='gantt.json',artifact_id=artifact,raw_sha256=digest))
    snap=w.ingest_snapshot(conn,w.SnapshotSpec(plan_id=plan,representation='mpp',tasks=(w.TaskVersionSpec('t1',uid='1'),)))
    w.link_publication_snapshot(conn,pub1,snap,confidence='confirmed',evidence='synthetic fixture link')
    result=r.render_plan_md(conn,plan)
    md=result.md_path.read_text()
    assert all(value in md for value in (pub1,pub2,'p1','p2','legacy_unverified',snap,'revision','unknown','partial'))
    assert 'восстановлена' not in md or 'не восстановлена' in md
    assert 'производная проекция' in md
