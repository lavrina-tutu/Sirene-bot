"""Тесты typed writer Фазы 2 (P2.SCHEMA.1-8, R-012-019): ingest_snapshot,
record_quality_issue, select_snapshot_baseline, select_plan_baseline."""
from __future__ import annotations

import pytest

from mofs_index.db import connect, initialize
from mofs_index.plan.migrate import ensure_plan_schema
from mofs_index.plan import writer as w


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "index.sqlite"
    c = connect(db_path, durable=True)
    initialize(c)
    ensure_plan_schema(c)
    yield c
    c.close()


def _full_snapshot_spec(plan_id: str, lineage_id: str, snapshot_id: str | None = None) -> w.SnapshotSpec:
    return w.SnapshotSpec(
        plan_id=plan_id,
        lineage_id=lineage_id,
        representation="mpp_full_export",
        timezone_hint="Europe/Moscow",
        snapshot_id=snapshot_id,
        collections=(
            w.CollectionStatusSpec("tasks", "complete", count=2),
            w.CollectionStatusSpec("baselines", "partial", count=1, reason="только слот 0 присутствует"),
        ),
        tasks=(
            w.TaskVersionSpec(
                task_key="t1", uid="100", name="Root", outline_level=1,
                start_raw="2026-01-01", finish_raw="2026-01-10",
                early_start="2026-01-01", late_start="2026-01-02",
                segments=(w.TaskSegmentSpec("2026-01-01", "2026-01-03"),),
                baseline_values=(w.BaselineValueSpec(baseline_slot=0, baseline_start="2026-01-01"),),
            ),
            w.TaskVersionSpec(task_key="t2", uid="101", name="Child", outline_level=2),
        ),
        dependencies=(
            w.DependencyVersionSpec("t1", "t2", link_type="FS", lag_raw="1 d"),
        ),
        external_dependencies=(
            w.ExternalDependencySpec("t2", direction="successor", reason="dangling", external_ref="ext:999"),
        ),
        resources=(
            w.ResourceVersionSpec(
                resource_key="r1", name="Исполнитель", max_units=1.0,
                availability=(w.ResourceAvailabilitySpec("2026-01-01", "2026-12-31", 1.0),),
            ),
        ),
        assignments=(
            w.AssignmentVersionSpec(
                task_key="t1", resource_key="r1", units=1.0, work_raw="40 h",
                timephased=(w.TimephasedSpec("2026-01-01", "2026-01-02", "8 h"),),
            ),
        ),
        calendars=(
            w.CalendarVersionSpec(
                calendar_key="standard", name="Standard", minutes_per_day=480,
                intervals=(w.CalendarIntervalSpec("weekday", "MON", True, "09:00", "18:00"),),
            ),
        ),
        quality_issues=(
            w.QualityIssueSpec("dangling_dependency", "warning", "t2 -> ext:999 не разрешена"),
        ),
    )


def test_ingest_snapshot_writes_full_graph_in_one_transaction(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="1")
    snapshot_id = w.ingest_snapshot(conn, _full_snapshot_spec(plan_id, lineage_id))

    assert conn.execute("SELECT COUNT(*) FROM plan_snapshot").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_task_version WHERE snapshot_id=?", (snapshot_id,)).fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM plan_task_segment").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_embedded_baseline_value").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_dependency_version").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_external_dependency").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_resource_version").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_resource_availability").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_assignment_version").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_assignment_timephased").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_calendar_version").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_calendar_interval").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_snapshot_collection").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM plan_quality_issue").fetchone()[0] == 1
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert violations == []


def test_ingest_snapshot_idempotent_by_explicit_snapshot_id(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="1")
    spec = _full_snapshot_spec(plan_id, lineage_id, snapshot_id="snap-fixed-1")
    s1 = w.ingest_snapshot(conn, spec)
    s2 = w.ingest_snapshot(conn, spec)
    assert s1 == s2 == "snap-fixed-1"
    assert conn.execute("SELECT COUNT(*) FROM plan_snapshot").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM plan_task_version").fetchone()[0] == 2  # не удвоилось


class _FlakyConnProxy:
    """Делегирует всё реальному sqlite3.Connection, кроме одного сбоя на
    заданном фрагменте SQL — симулирует сбой посреди ingest_snapshot без
    monkeypatch несъёмного C-типа ``sqlite3.Connection``."""

    def __init__(self, real_conn, fail_on_substring: str):
        self._real = real_conn
        self._fail_on = fail_on_substring

    def execute(self, sql, *args, **kwargs):
        if self._fail_on in sql:
            raise RuntimeError("simulated mid-ingest failure")
        return self._real.execute(sql, *args, **kwargs)


def test_ingest_snapshot_atomic_rollback_on_mid_failure(conn):
    """AC-116: искусственный сбой посреди вставок не оставляет полуснимок
    последним "полным" — ни одна строка снимка не сохраняется."""
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="1")

    broken = w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp_full_export",
        tasks=(
            w.TaskVersionSpec(task_key="t1", name="Root"),
        ),
        dependencies=(
            w.DependencyVersionSpec(predecessor_task_key="t1", successor_task_key="missing"),
        ),
    )

    flaky = _FlakyConnProxy(conn, "plan_dependency_version")
    with pytest.raises(RuntimeError):
        w.ingest_snapshot(flaky, broken)

    assert conn.execute("SELECT COUNT(*) FROM plan_snapshot").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM plan_task_version").fetchone()[0] == 0


def test_record_quality_issue_missing_mpp_version_persisted(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="1")
    issue_id = w.record_quality_issue(
        conn, plan_id, "missing_source_version", "warning",
        lineage_id=lineage_id, detail="MPP v3 missing: не найден по известным hash",
    )
    rows = conn.execute("SELECT issue_kind, severity FROM plan_quality_issue WHERE issue_id=?", (issue_id,)).fetchall()
    assert [tuple(r) for r in rows] == [("missing_source_version", "warning")]


def test_record_quality_issue_idempotent_by_issue_id(conn):
    plan_id = w.ensure_plan(conn, "zd")
    i1 = w.record_quality_issue(conn, plan_id, "cycle", "error", issue_id="issue-fixed-1")
    i2 = w.record_quality_issue(conn, plan_id, "cycle", "error", issue_id="issue-fixed-1")
    assert i1 == i2
    assert conn.execute("SELECT COUNT(*) FROM plan_quality_issue").fetchone()[0] == 1


def test_select_snapshot_baseline_default_is_first_available(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="1")
    s1 = w.ingest_snapshot(conn, _full_snapshot_spec(plan_id, lineage_id, snapshot_id="snap-1"))
    sel1 = w.select_snapshot_baseline(conn, lineage_id, s1)
    assert sel1

    row = conn.execute(
        "SELECT snapshot_id, is_explicit FROM plan_snapshot_selection WHERE selection_id=?", (sel1,)
    ).fetchone()
    assert tuple(row) == (s1, 0)


def test_select_snapshot_baseline_explicit_not_overridden_by_default(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="1")
    s1 = w.ingest_snapshot(conn, _full_snapshot_spec(plan_id, lineage_id, snapshot_id="snap-1"))
    s2 = w.SnapshotSpec(plan_id=plan_id, lineage_id=lineage_id, representation="mpp_full_export",
                         snapshot_id="snap-2")
    w.ingest_snapshot(conn, s2)

    # владелец явно выбирает более РАННИЙ snapshot как базу
    explicit_sel = w.select_snapshot_baseline(conn, lineage_id, s1, is_explicit=True)

    # поздний автоматический default-пересчёт (напр. новый импорт нашёл
    # "первую доступную" иначе) не переопределяет явный выбор
    auto_sel = w.select_snapshot_baseline(conn, lineage_id, "snap-2", is_explicit=False)
    assert auto_sel == explicit_sel

    row = conn.execute(
        "SELECT snapshot_id, is_explicit FROM plan_snapshot_selection WHERE selection_id=?",
        (explicit_sel,),
    ).fetchone()
    assert tuple(row) == (s1, 1)


def test_select_snapshot_baseline_append_only_history_preserved(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="1")
    s1 = w.ingest_snapshot(conn, _full_snapshot_spec(plan_id, lineage_id, snapshot_id="snap-1"))
    s2 = w.ingest_snapshot(conn, w.SnapshotSpec(
        plan_id=plan_id, lineage_id=lineage_id, representation="mpp_full_export", snapshot_id="snap-2",
    ))
    sel1 = w.select_snapshot_baseline(conn, lineage_id, s1, is_explicit=True)
    sel2 = w.select_snapshot_baseline(conn, lineage_id, s2, is_explicit=True)
    assert sel2 != sel1

    # старая строка не удалена/не изменена (append-only, R-016.3)
    old_row = conn.execute(
        "SELECT snapshot_id FROM plan_snapshot_selection WHERE selection_id=?", (sel1,),
    ).fetchone()
    assert tuple(old_row) == (s1,)
    new_row = conn.execute(
        "SELECT snapshot_id, supersedes FROM plan_snapshot_selection WHERE selection_id=?", (sel2,),
    ).fetchone()
    assert tuple(new_row) == (s2, sel1)


def test_select_plan_baseline_default_not_overriding_explicit(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="1")
    s1 = w.ingest_snapshot(conn, _full_snapshot_spec(plan_id, lineage_id, snapshot_id="snap-1"))

    explicit_sel = w.select_plan_baseline(conn, plan_id, s1, 2, is_explicit=True)
    auto_sel = w.select_plan_baseline(conn, plan_id, s1, 0, is_explicit=False)
    assert auto_sel == explicit_sel

    row = conn.execute(
        "SELECT baseline_slot, is_explicit FROM plan_baseline_selection WHERE baseline_selection_id=?",
        (explicit_sel,),
    ).fetchone()
    assert tuple(row) == (2, 1)


def test_cross_lineage_snapshot_fk_rejected(conn):
    """Составной FK (lineage_id, plan_id) -> plan_lineage отклоняет снимок
    чужого плана (аналог AC-116 Фазы 1, теперь на plan_snapshot)."""
    plan_a = w.ensure_plan(conn, "zd")
    plan_b = w.ensure_plan(conn, "other")
    lineage_b = w.ensure_lineage(conn, plan_b, "confluence:dom.tutu.ru", page_id="1")
    with pytest.raises(Exception):
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO plan_snapshot(snapshot_id, plan_id, lineage_id, representation, recorded_at) "
            "VALUES ('bad-snap', ?, ?, 'mpp_full_export', '2026-01-01')",
            (plan_a, lineage_b),
        )
        conn.execute("COMMIT")
