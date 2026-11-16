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
    def __getattr__(self, name):
        return getattr(self._real, name)

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


def _profiled_case(conn,tmp_path,*,profile="a"*64,timezone="unknown",source=b"mpp bytes"):
    import hashlib
    plan=w.ensure_plan(conn,"archive-project")
    lineage=w.ensure_lineage(conn,plan,"local-archive-v1")
    path=tmp_path/(hashlib.sha256(source).hexdigest()+".mpp");path.write_bytes(source)
    sha=hashlib.sha256(source).hexdigest()
    artifact=w.record_artifact(conn,sha,"mpp",str(path),size_bytes=len(source))
    op=w.create_operation(conn,w.OperationSpec("save"))
    item=w.create_import_item(conn,w.ImportItemSpec(op,"original.mpp","/original.mpp",source_mpp_sha256=sha))
    attempt=w.begin_operation_attempt(conn,op,item)
    spec=w.SnapshotSpec(plan, "mpp",lineage_id=lineage,source_artifact_id=artifact,source_mpp_sha256=sha,
        normalization_profile_fingerprint=profile,resolved_timezone=timezone,
        tasks=(w.TaskVersionSpec("t",duration_amount="0.123456789012345678901",duration_units="HOURS"),),
        collections=(w.CollectionStatusSpec("tasks","complete",1),))
    return item,attempt,spec,path


def test_atomic_import_records_link_event_and_decimal(conn,tmp_path):
    from mofs_index.plan import query as q
    item,attempt,spec,_=_profiled_case(conn,tmp_path)
    result=w.commit_import_snapshot(conn,item,attempt,spec)
    assert result.status=="saved"
    assert q.get_committed_import(conn,item)["snapshot"]["dedup_key"]==w.snapshot_dedup_key(spec)
    row=conn.execute("SELECT duration_amount,typeof(duration_amount) FROM plan_task_version").fetchone()
    assert tuple(row)==("0.123456789012345678901","text")
    assert w.commit_import_snapshot(conn,item,attempt,spec)==result


def test_dedup_scope_and_legacy_exclusion(conn,tmp_path):
    from dataclasses import replace
    item,attempt,spec,_=_profiled_case(conn,tmp_path)
    legacy=w.ingest_snapshot(conn,w.SnapshotSpec(spec.plan_id,"mpp",lineage_id=spec.lineage_id,source_artifact_id=spec.source_artifact_id))
    first=w.commit_import_snapshot(conn,item,attempt,spec)
    assert first.snapshot_id!=legacy
    for profile,zone,same in [("a"*64,"unknown",True),("b"*64,"unknown",False),("a"*64,"Europe/Moscow",False)]:
        other,attempt2,second,_=_profiled_case(conn,tmp_path,profile=profile,timezone=zone)
        result=w.commit_import_snapshot(conn,other,attempt2,second)
        assert (result.snapshot_id==first.snapshot_id) is same
        assert (result.status=="unchanged") is same
    key=conn.execute("SELECT dedup_key FROM plan_snapshot WHERE snapshot_id=?",(legacy,)).fetchone()[0]
    assert key is None


@pytest.mark.parametrize("damage",["artifact","missing","versions","normalized"])
def test_corrupt_existing_snapshot_not_successful_duplicate(conn,tmp_path,damage):
    item,attempt,spec,path=_profiled_case(conn,tmp_path)
    w.commit_import_snapshot(conn,item,attempt,spec)
    other,attempt2,second,_=_profiled_case(conn,tmp_path)
    if damage=="artifact":
        path.write_bytes(b"corrupt")
    elif damage=="missing":
        path.unlink()
    elif damage=="versions":
        conn.execute("DELETE FROM plan_task_version");conn.commit()
    else:
        conn.execute("UPDATE plan_snapshot SET source_json='corrupt'");conn.commit()
    with pytest.raises(w.PlanWriterError):
        w.commit_import_snapshot(conn,other,attempt2,second)
    assert conn.execute("SELECT snapshot_id FROM plan_import_item WHERE item_id=?",(other,)).fetchone()[0] is None


def test_atomic_import_failure_rolls_back_item_and_event(conn,tmp_path):
    item,attempt,spec,_=_profiled_case(conn,tmp_path)
    flaky=_FlakyConnProxy(conn,"INSERT INTO plan_attempt_event")
    with pytest.raises(RuntimeError):
        w.commit_import_snapshot(flaky,item,attempt,spec)
    assert conn.execute("SELECT count(*) FROM plan_snapshot").fetchone()[0]==0
    assert conn.execute("SELECT snapshot_id FROM plan_import_item WHERE item_id=?",(item,)).fetchone()[0] is None
    assert conn.execute("SELECT count(*) FROM plan_attempt_event WHERE event_kind='snapshot_committed'").fetchone()[0]==0
    assert not conn.in_transaction


def test_nested_transaction_is_not_committed(conn,tmp_path):
    item,attempt,spec,_=_profiled_case(conn,tmp_path)
    conn.execute("BEGIN")
    with pytest.raises(w.PlanWriterError,match="idle connection"):
        w.commit_import_snapshot(conn,item,attempt,spec)
    assert conn.in_transaction
    conn.rollback()


def test_full_export_v2_lossless_exact_fields_and_parallel_assignments(conn,tmp_path):
    import json
    from mofs_index.plan.ingest_mpp import build_snapshot_spec
    field=lambda v:{"value":v,"quality":"ok"}
    quantity={"amount":"-0.123456789012345678901","units":"ELAPSED_HOURS","source_units":"eh","elapsed":True}
    duration={"value":"-0.123456789012345678901 eh","quantity":quantity,"quality":"ok"}
    export={"tasks":[{"task_key":"t","id":0,"uid":1,"parent_task_key":field(None),"calendar_key":field("c"),
                       "duration":duration,"segments":field([{"start":"2026-01-01","finish":"2026-01-02"}]),
                       "baseline_values":[{"slot":0,"duration":quantity,"cost":"1.00000000000000001"}]}],
        "dependencies":[{"predecessor_task_key":"t","successor_task_key":"t","link_type":"SF","lag_value":field(quantity),"lag":"-.1 eh"}],
        "resources":[{"resource_key":"r","max_units":field("12.00000000000000001"),"calendar_key":field("c")}],
        "assignments":[{"assignment_key":key,"task_key":"t","resource_key":"r","units":field("33.3333333333333333333"),"work":duration,
                        "timephased":[{"period_start":field("2026-01-01"),"period_end":field("2026-01-02"),"work":duration}]} for key in ("a1","a2")],
        "calendars":[{"calendar_key":"c","parent_key":field("base"),"weekdays":[{"day":"MON","working":field(True),
            "intervals":field([{"start":"08:00","end":"12:00"},{"start":"13:00","end":"17:00"}])}],
            "exceptions":[{"from_date":field("2026-01-01"),"to_date":field("2026-01-01"),"working":field(False),"intervals":field([])}],
            "work_weeks":[{"name":"special"}]}],"project":{"conversion":{"minutes_per_day":field("480")}}}
    item,attempt,base,_=_profiled_case(conn,tmp_path)
    spec=build_snapshot_spec(export,plan_id=base.plan_id,lineage_id=base.lineage_id,source_artifact_id=base.source_artifact_id,
        source_mpp_sha256=base.source_mpp_sha256,normalization_profile_fingerprint="a"*64)
    result=w.commit_import_snapshot(conn,item,attempt,spec)
    assert conn.execute("SELECT duration_amount FROM plan_task_version").fetchone()[0]==quantity["amount"]
    assert conn.execute("SELECT lag_amount FROM plan_dependency_version").fetchone()[0]==quantity["amount"]
    assert conn.execute("SELECT count(*) FROM plan_assignment_version").fetchone()[0]==2
    assert conn.execute("SELECT units_decimal FROM plan_assignment_version LIMIT 1").fetchone()[0]=="33.3333333333333333333"
    assert conn.execute("SELECT count(*) FROM plan_calendar_interval").fetchone()[0]==3
    assert json.loads(conn.execute("SELECT source_json FROM plan_calendar_version").fetchone()[0])==export["calendars"][0]
    assert json.loads(conn.execute("SELECT source_json FROM plan_snapshot WHERE snapshot_id=?",(result.snapshot_id,)).fetchone()[0])==export
    assert conn.execute("SELECT baseline_cost_decimal FROM plan_embedded_baseline_value").fetchone()[0]=="1.00000000000000001"
    assert conn.execute("SELECT work_amount FROM plan_assignment_timephased LIMIT 1").fetchone()[0]==quantity["amount"]


def test_snapshot_normalization_fingerprint_includes_runtime_and_profile():
    from copy import deepcopy
    from mofs_index.plan.ingest_mpp import build_snapshot_spec
    data={"normalized_data":{"normalization":{"id":"normalization-v1","fingerprint":"profile-sha"},
        "source_identity":{"sha256":"a"*64,"reader":"v2","mpxj":"16.4","jpype":"1.7"},"export_version":"full-export-v2"},"schema_version":1}
    first=build_snapshot_spec(data,plan_id="p")
    changed=deepcopy(data);changed["normalized_data"]["source_identity"]["mpxj"]="17"
    assert build_snapshot_spec(changed,plan_id="p").normalization_profile_fingerprint!=first.normalization_profile_fingerprint
    changed=deepcopy(data);changed["normalized_data"]["normalization"]["fingerprint"]="other"
    assert build_snapshot_spec(changed,plan_id="p").normalization_profile_fingerprint!=first.normalization_profile_fingerprint
    assert w.normalize_timezone(None)=="unknown"
    assert w.normalize_timezone("US/Eastern")=="America/New_York"


def test_import_preserves_nonempty_baseline_selections(conn,tmp_path):
    item,attempt,spec,_=_profiled_case(conn,tmp_path)
    old=w.ingest_snapshot(conn,w.SnapshotSpec(spec.plan_id,"mpp",lineage_id=spec.lineage_id))
    w.select_snapshot_baseline(conn,spec.lineage_id,old,is_explicit=True,basis="owner")
    w.select_plan_baseline(conn,spec.plan_id,old,0,is_explicit=True,basis="owner")
    tables=("plan_baseline_selection","plan_snapshot_selection")
    before={t:[tuple(r) for r in conn.execute("SELECT * FROM "+t)] for t in tables}
    w.commit_import_snapshot(conn,item,attempt,spec)
    assert all(before.values())
    assert {t:[tuple(r) for r in conn.execute("SELECT * FROM "+t)] for t in tables}==before


def test_missing_boolean_and_known_false_are_distinct(conn,tmp_path):
    from mofs_index.plan.ingest_mpp import build_snapshot_spec
    item,attempt,base,_=_profiled_case(conn,tmp_path)
    export={"tasks":[{"task_key":"missing","milestone":None,"summary":False}],
        "calendars":[{"calendar_key":"c","weekdays":[{"day":"MON","working":{"value":None,"quality":"unsupported"}},
            {"day":"TUE","working":{"value":False,"quality":"ok"}}]}]}
    spec=build_snapshot_spec(export,plan_id=base.plan_id,lineage_id=base.lineage_id,source_artifact_id=base.source_artifact_id,
        source_mpp_sha256=base.source_mpp_sha256,normalization_profile_fingerprint="a"*64)
    w.commit_import_snapshot(conn,item,attempt,spec)
    assert tuple(conn.execute("SELECT milestone,summary FROM plan_task_version").fetchone())==(None,0)
    assert [row[0] for row in conn.execute("SELECT working FROM plan_calendar_interval ORDER BY day_or_date")]==[None,0]
