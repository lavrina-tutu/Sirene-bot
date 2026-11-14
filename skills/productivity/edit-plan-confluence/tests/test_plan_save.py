"""P4.ACC.2 (R-008, AC-144): ``save`` создаёt snapshot, НЕ публикует и НЕ
сдвигает baseline. Использует предпосчитанный ``export`` (словарь в формате
``plan_export.export_full()``), чтобы не требовать JVM/mpxj в unit-тесте —
``run_export_full`` (реальный subprocess) покрыт отдельно негативным тестом
на ошибку/отсутствие интерпретатора."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

MOFS_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
if str(MOFS_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_ROOT))

import plan_save as ps  # noqa: E402


def _fake_export() -> dict:
    """Минимальный валидный ``export_full()``-словарь: 2 задачи, 1 связь."""
    return {
        "project": {"status_date": {"value": None, "quality": "missing"}},
        "collections": {
            "tasks": {"status": "complete", "count": 2},
            "dependencies": {"status": "complete", "count": 1},
        },
        "tasks": [
            {
                "task_key": "1", "uid": 1, "wbs": "1", "name": "A",
                "outline_level": 1,
                "start": {"value": "2026-01-01", "quality": "ok"},
                "finish": {"value": "2026-01-10", "quality": "ok"},
                "duration": {"value": 10, "quality": "ok"},
            },
            {
                "task_key": "2", "uid": 2, "wbs": "2", "name": "B",
                "outline_level": 1,
                "start": {"value": "2026-01-10", "quality": "ok"},
                "finish": {"value": "2026-01-20", "quality": "ok"},
                "duration": {"value": 10, "quality": "ok"},
            },
        ],
        "dependencies": [
            {"predecessor_task_key": "1", "successor_task_key": "2", "link_type": "FS", "lag": 0},
        ],
        "external_dependencies": [],
        "resources": [],
        "assignments": [],
        "calendars": [],
        "diagnose_graph": {"multiple_roots": False, "has_cycle": False, "has_service_row": False},
    }


@pytest.fixture
def fake_mpp(tmp_path) -> Path:
    p = tmp_path / "fake.mpp"
    p.write_bytes(b"not a real mpp, content-addressed bytes only")
    return p


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    from mofs_index.db import connect as mofs_connect, initialize
    from mofs_index.plan.migrate import ensure_plan_schema

    db_path = tmp_path / "plan_index.sqlite"

    def fake_connect_durable(path=None):
        c = mofs_connect(db_path, durable=True)
        initialize(c)
        ensure_plan_schema(c)
        return c

    monkeypatch.setattr("plan_save.connect_durable", fake_connect_durable)
    monkeypatch.setattr("plan_archive.connect_durable", fake_connect_durable)
    wv = tmp_path / "WorkVault"
    monkeypatch.setattr("plan_archive.get_workvault_path", lambda: wv)
    monkeypatch.setattr("plan_receipt.get_workvault_path", lambda: wv)
    return db_path


def _counts(db_path: Path) -> dict[str, int]:
    from mofs_index.db import connect

    c = connect(db_path, durable=True)
    try:
        out = {}
        for table in (
            "plan_snapshot", "plan_publication", "plan_publication_snapshot",
            "plan_snapshot_selection", "plan_baseline_selection", "plan_task_version",
        ):
            out[table] = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return out
    finally:
        c.close()


def test_save_creates_snapshot_without_page_id(fake_mpp, isolate):
    result = ps.save_snapshot(fake_mpp, project_slug="zd-acc-test", export=_fake_export())
    assert result.snapshot_id
    assert result.task_count == 2
    assert result.dependency_count == 1
    assert result.published is False

    counts = _counts(isolate)
    assert counts["plan_snapshot"] == 1
    assert counts["plan_task_version"] == 2
    # AC-144: НЕ публикует, НЕ сдвигает baseline
    assert counts["plan_publication"] == 0
    assert counts["plan_publication_snapshot"] == 0
    assert counts["plan_snapshot_selection"] == 0
    assert counts["plan_baseline_selection"] == 0


def test_save_twice_does_not_publish_and_appends_second_snapshot(fake_mpp, isolate):
    """Два save-only прохода подряд — по-прежнему ноль публикаций/baseline
    (AC-144 не нарушается многократным сохранением)."""
    ps.save_snapshot(fake_mpp, project_slug="zd-acc-test2", export=_fake_export())
    ps.save_snapshot(fake_mpp, project_slug="zd-acc-test2", export=_fake_export())

    counts = _counts(isolate)
    assert counts["plan_snapshot"] == 2  # export без snapshot_id → два разных снимка
    assert counts["plan_publication"] == 0
    assert counts["plan_baseline_selection"] == 0


def test_save_requires_project_slug_without_page_id(fake_mpp, isolate):
    with pytest.raises(ps.PlanSaveError):
        ps.save_snapshot(fake_mpp, export=_fake_export())


def test_save_with_page_id_reuses_existing_lineage(fake_mpp, isolate):
    import plan_archive as pa

    # предварительно создаём lineage как это сделал бы archive-history/apply
    from mofs_index.db import connect

    c = connect(isolate, durable=True)
    try:
        from mofs_index.plan.migrate import ensure_plan_schema
        ensure_plan_schema(c)
        binding = pa.resolve_plan_binding("900001", "zd-acc-test3", conn=c)
    finally:
        c.close()

    result = ps.save_snapshot(fake_mpp, page_id="900001", export=_fake_export())
    assert result.plan_id == binding["plan_id"]
    assert result.lineage_id == binding["lineage_id"]

    counts = _counts(isolate)
    assert counts["plan_publication"] == 0
    assert counts["plan_baseline_selection"] == 0


def test_save_rejects_missing_mpp(tmp_path, isolate):
    with pytest.raises(FileNotFoundError):
        ps.save_snapshot(tmp_path / "nope.mpp", project_slug="zd-acc-test4", export=_fake_export())
