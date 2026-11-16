"""Тесты typed writer API core plan_*-таблиц (P1.SCHEMA.4/5, R-016, R-026)."""
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


def test_ensure_plan_idempotent(conn):
    p1 = w.ensure_plan(conn, "zd", name="ZD")
    p2 = w.ensure_plan(conn, "zd", name="ZD (другой вызов)")
    assert p1 == p2
    rows = conn.execute("SELECT COUNT(*) FROM plan").fetchone()[0]
    assert rows == 1


def test_ensure_lineage_idempotent(conn):
    plan_id = w.ensure_plan(conn, "zd")
    l1 = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="537561928")
    l2 = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="537561928")
    assert l1 == l2
    l3 = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="999")
    assert l3 != l1


def test_record_artifact_dedup_by_hash(conn):
    a1 = w.record_artifact(conn, "deadbeef" * 8, "mpp", "/tmp/x.mpp", size_bytes=10)
    a2 = w.record_artifact(conn, "deadbeef" * 8, "mpp", "/tmp/other-path.mpp", size_bytes=10)
    assert a1 == a2
    rows = conn.execute("SELECT COUNT(*) FROM plan_artifact").fetchone()[0]
    assert rows == 1


def test_begin_attempt_idempotent(conn):
    plan_id = w.ensure_plan(conn, "zd")
    spec = w.AttemptSpec(plan_id=plan_id, attempt_id="attempt-fixed-1")
    a1 = w.begin_attempt(conn, spec)
    a2 = w.begin_attempt(conn, spec)
    assert a1 == a2 == "attempt-fixed-1"
    rows = conn.execute("SELECT COUNT(*) FROM plan_import_attempt").fetchone()[0]
    assert rows == 1


def test_record_event_idempotent_by_event_id(conn):
    plan_id = w.ensure_plan(conn, "zd")
    attempt_id = w.begin_attempt(conn, w.AttemptSpec(plan_id=plan_id))
    e1 = w.record_event(conn, attempt_id, "archive", "prepared", event_id="ev-1")
    e2 = w.record_event(conn, attempt_id, "archive", "prepared", event_id="ev-1")
    assert e1 == e2
    rows = conn.execute("SELECT COUNT(*) FROM plan_attempt_event WHERE event_id='ev-1'").fetchone()[0]
    assert rows == 1


def test_record_event_rejects_unknown_stage(conn):
    plan_id = w.ensure_plan(conn, "zd")
    attempt_id = w.begin_attempt(conn, w.AttemptSpec(plan_id=plan_id))
    with pytest.raises(w.PlanWriterError):
        w.record_event(conn, attempt_id, "bogus_stage", "prepared")


def test_record_event_rejects_unknown_status(conn):
    plan_id = w.ensure_plan(conn, "zd")
    attempt_id = w.begin_attempt(conn, w.AttemptSpec(plan_id=plan_id))
    with pytest.raises(w.PlanWriterError):
        w.record_event(conn, attempt_id, "archive", "bogus_status")


def test_record_event_check_constraint_enforced_at_sql_level(conn):
    """Даже обходя writer, прямой SQL с неразрешённым stage отклоняется
    CHECK-constraint (не только писательской валидацией Python)."""
    plan_id = w.ensure_plan(conn, "zd")
    attempt_id = w.begin_attempt(conn, w.AttemptSpec(plan_id=plan_id))
    with pytest.raises(Exception):
        conn.execute(
            "INSERT INTO plan_attempt_event(event_id, attempt_id, stage, status, created_at) "
            "VALUES ('x', ?, 'not_a_stage', 'prepared', '2026-01-01')",
            (attempt_id,),
        )


def test_record_publication_unique_key(conn):
    plan_id = w.ensure_plan(conn, "zd")
    spec = w.PublicationSpec(
        plan_id=plan_id,
        source_namespace="confluence:dom.tutu.ru",
        attachment_id="537561929",
        attachment_version=5,
        raw_sha256="hash5",
    )
    pub1 = w.record_publication(conn, spec)
    pub2 = w.record_publication(conn, spec)  # same key+hash -> idempotent
    assert pub1 == pub2


def test_record_publication_same_key_diff_hash_conflicts(conn):
    plan_id = w.ensure_plan(conn, "zd")
    spec = w.PublicationSpec(
        plan_id=plan_id,
        source_namespace="confluence:dom.tutu.ru",
        attachment_id="537561929",
        attachment_version=5,
        raw_sha256="hashA",
    )
    w.record_publication(conn, spec)
    spec2 = w.PublicationSpec(
        plan_id=plan_id,
        source_namespace="confluence:dom.tutu.ru",
        attachment_id="537561929",
        attachment_version=5,
        raw_sha256="hashB",
    )
    with pytest.raises(w.PublicationConflict):
        w.record_publication(conn, spec2)


def test_cross_plan_lineage_fk_rejected(conn):
    """P1.SCHEMA.5 / AC-116: попытка/публикация с lineage_id другого плана
    отклоняется составным FK (lineage_id, plan_id) -> plan_lineage, не
    молчаливой записью."""
    plan_a = w.ensure_plan(conn, "zd")
    plan_b = w.ensure_plan(conn, "other")
    lineage_b = w.ensure_lineage(conn, plan_b, "confluence:dom.tutu.ru", page_id="1")

    with pytest.raises(Exception):
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO plan_import_attempt(attempt_id, plan_id, lineage_id, status, created_at) "
            "VALUES ('bad-attempt', ?, ?, 'prepared', '2026-01-01')",
            (plan_a, lineage_b),
        )
        conn.execute("COMMIT")


def test_page_observation_and_link(conn):
    plan_id = w.ensure_plan(conn, "zd")
    pub_id = w.record_publication(conn, w.PublicationSpec(
        plan_id=plan_id,
        source_namespace="confluence:dom.tutu.ru",
        attachment_id="537561929",
        attachment_version=1,
        raw_sha256="h1",
    ))
    obs_id = w.record_page_observation(conn, w.PageObservationSpec(
        plan_id=plan_id,
        page_id="537561928",
        page_version=1,
        itogo_text="Итого: с 01.01.26 по 02.02.26 - 10 рабочих дней",
        quality="ok",
    ))
    link_id = w.link_publication_page(conn, pub_id, obs_id, confidence="inferred")
    assert link_id

    # разные publication/observation с разными номерами не склеиваются по
    # совпадению N (AC-110): второе наблюдение без связи — не ошибка.
    obs2 = w.record_page_observation(conn, w.PageObservationSpec(
        plan_id=plan_id, page_id="537561928", page_version=2, quality="unknown",
    ))
    assert obs2 != obs_id


def test_foreign_key_check_clean_after_all_writes(conn):
    plan_id = w.ensure_plan(conn, "zd")
    lineage_id = w.ensure_lineage(conn, plan_id, "confluence:dom.tutu.ru", page_id="537561928")
    attempt_id = w.begin_attempt(conn, w.AttemptSpec(plan_id=plan_id, lineage_id=lineage_id))
    w.record_event(conn, attempt_id, "archive", "prepared")
    artifact_id = w.record_artifact(conn, "abc123", "mpp", "/tmp/x.mpp")
    pub_id = w.record_publication(conn, w.PublicationSpec(
        plan_id=plan_id, lineage_id=lineage_id, artifact_id=artifact_id,
        source_namespace="confluence:dom.tutu.ru", attachment_id="1",
        attachment_version=1, raw_sha256="h",
    ))
    obs_id = w.record_page_observation(conn, w.PageObservationSpec(
        plan_id=plan_id, page_id="537561928",
    ))
    w.link_publication_page(conn, pub_id, obs_id)
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert violations == []


@pytest.mark.parametrize("trust", ["verified_v1", "verified_observation", "verification_failed", "invented"])
def test_partial_legacy_writer_cannot_promote_publication(conn, trust):
    plan = w.ensure_plan(conn, "test")
    with pytest.raises(w.PlanWriterError):
        w.record_publication(conn, w.PublicationSpec(plan_id=plan, source_namespace="test",
                            attachment_id="actual-id", attachment_version=1, trust=trust))
    assert conn.execute("SELECT COUNT(*) FROM plan_publication").fetchone()[0] == 0


def test_observation_without_full_readback_evidence_is_not_verified(conn):
    plan = w.ensure_plan(conn, "test")
    with pytest.raises(w.PlanWriterError):
        w.record_page_observation(conn, w.PageObservationSpec(plan_id=plan, page_id="test-page",
                                  verification_status="verified_observation", verification_scope="current_state"))


def test_publication_default_trust_is_legacy_unverified(conn):
    plan = w.ensure_plan(conn, "test")
    pub = w.record_publication(conn, w.PublicationSpec(plan_id=plan, source_namespace="test",
                               attachment_id="actual-id", attachment_version=1))
    assert conn.execute("SELECT trust FROM plan_publication WHERE publication_id=?", (pub,)).fetchone()[0] == "legacy_unverified"


def test_cross_project_observation_link_rejected(conn):
    a, b = w.ensure_plan(conn,"a"), w.ensure_plan(conn,"b")
    pub = w.record_publication(conn,w.PublicationSpec(plan_id=a,source_namespace="test",attachment_id="actual",attachment_version=1))
    obs = w.record_page_observation(conn,w.PageObservationSpec(plan_id=b,page_id="test-page"))
    with pytest.raises(w.PlanWriterError):
        w.link_publication_page(conn,pub,obs,confidence="confirmed")


def test_registration_cannot_link_unverified_observation(conn):
    plan = w.ensure_plan(conn,"a")
    obs = w.record_page_observation(conn,w.PageObservationSpec(plan_id=plan,page_id="test-page",page_version=1))
    with pytest.raises(w.PlanWriterError):
        w.record_publication(conn,w.PublicationSpec(plan_id=plan,source_namespace="test",attachment_id="actual",
                             attachment_version=1,page_id="test-page",page_version=1,observation_id=obs))
