from __future__ import annotations

import json

import pytest

from conf_client import ConfluenceError
from gantt_attachment import UploadVerificationConflict
from macro import build_macro_html, find_macro
from pipeline import LIVE_AB_PAGE, apply_plan, build_plan_empty, build_plan_from_mpp
from plan_verify import PublicationVerificationError


def _rows(path, sql):
    from mofs_index.db import connect
    with connect(path, durable=True) as conn:
        return [tuple(r) for r in conn.execute(sql)]


def test_build_plan_empty():
    g = build_plan_empty("Мой план")
    assert g["eventsData"][0]["name"] == "Мой план"
    assert g["eventsData"][0]["children"] == []


def test_build_plan_from_mpp_offline(mpp_fixture, gantt_test_template):
    g = build_plan_from_mpp(mpp_fixture, gantt_test_template)
    assert g["idCounter"] != 300000
    assert len(g["calendarsData"][0]["intervals"]) > 4


def test_live_ab_guard():
    from pipeline import _guard_page
    with pytest.raises(PermissionError):
        _guard_page(LIVE_AB_PAGE, allow_live_ab=False)


def test_apply_plan_without_confirm_writes_nothing(fake_confluence, prepared_input):
    with pytest.raises(PermissionError):
        apply_plan(fake_confluence, "test-page", prepared_input, "нет")
    assert not fake_confluence.calls


@pytest.mark.parametrize("failure", ["false", "hash", "download", "lying_true"])
def test_attachment_failure_blocks_put(failure, fake_confluence, prepared_input, isolated_plan_db, monkeypatch):
    import pipeline
    client = fake_confluence
    if failure == "false":
        monkeypatch.setattr(pipeline, "verify_uploaded", lambda *a, **k: (False, json.dumps(build_plan_empty("Plan"), ensure_ascii=False).encode()))
    elif failure == "lying_true":
        monkeypatch.setattr(pipeline, "verify_uploaded", lambda *a, **k: (True, b"wrong bytes"))
    elif failure == "download":
        client.download_error = TimeoutError("download after POST failed")
    else:
        original = client.upload
        def corrupt(*args):
            result = original(*args)
            client.blobs[(result.filename, result.version)] = b"corrupt"
            return result
        monkeypatch.setattr(pipeline, "upload_gantt_json", corrupt)
    with pytest.raises((UploadVerificationConflict, TimeoutError)):
        apply_plan(client, "test-page", prepared_input, "лей", project_slug="test")
    assert sum(c[0] == "POST_ATTACHMENT" for c in client.calls) == 1
    assert not any(c[0] == "PUT" for c in client.calls)
    assert _rows(isolated_plan_db, "SELECT COUNT(*) FROM plan_publication") == [(0,)]
    assert _rows(isolated_plan_db, "SELECT status FROM plan_import_attempt") == [("failed",)]
    from plan_receipt import read_receipt
    attempt_id = _rows(isolated_plan_db, "SELECT attempt_id FROM plan_import_attempt")[0][0]
    receipt = read_receipt(attempt_id, "failure-attachment_verify")
    assert receipt["published"] is None
    assert receipt["external_effect"] == "partial"


def test_success_records_get_observation_and_actual_id(fake_confluence, prepared_input, isolated_plan_db):
    client = fake_confluence
    result = apply_plan(client, "test-page", prepared_input, "лей", project_slug="test")
    assert result.attachment_version == 1
    order = [c[0] for c in client.calls]
    assert order.index("POST_ATTACHMENT") < order.index("GET_ATTACHMENT") < order.index("PUT")
    assert "GET" in order[order.index("PUT") + 1:]
    pub = _rows(isolated_plan_db, "SELECT attachment_id, trust FROM plan_publication")
    assert pub == [("actual-attachment-id", "legacy_unverified")]
    obs = _rows(isolated_plan_db, "SELECT itogo_raw, verification_status, verification_scope FROM plan_page_observation")
    assert obs == [(client.page["body"]["storage"]["value"], "verified_observation", "current_state")]
    assert _rows(isolated_plan_db, "SELECT COUNT(*) FROM plan_publication_page_link") == [(1,)]
    assert _rows(isolated_plan_db, "SELECT status FROM plan_import_attempt") == [("confirmed",)]


def _corrupt(storage, kind):
    macro = find_macro(storage)
    if kind == "duplicate":
        return storage + build_macro_html("other", "other", "other")
    if kind in ("macro_id", "param_id", "param_hash"):
        return storage.replace(getattr(macro, kind), "changed-" + kind)
    if kind == "attachment":
        return storage.replace(macro.param_id, "wrong-attachment")
    if kind == "itogo":
        return storage.replace("Итого: с", "Итого: с 01.01.00 вместо")
    if kind == "extra_itogo":
        return storage + "<p>Итого: с 01.01.26 по 02.01.26 - 2 рабочих дней</p>"
    if kind == "labour":
        return storage + "<p><strong>Трудозатраты:</strong> 123 ч-ч</p>"
    if kind == "foreign":
        return storage.replace("Соседний блок", "потерянный блок")
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["duplicate", "macro_id", "param_id", "param_hash", "attachment", "itogo", "extra_itogo", "labour", "foreign"])
def test_storage_readback_rejects_corruption(kind, fake_confluence, prepared_input, isolated_plan_db):
    client = fake_confluence
    def mutate(page):
        if any(c[0] == "PUT" for c in client.calls):
            page["body"]["storage"]["value"] = _corrupt(page["body"]["storage"]["value"], kind)
        return page
    client.mutate_get = mutate
    with pytest.raises(PublicationVerificationError):
        apply_plan(client, "test-page", prepared_input, "лей", project_slug="test")
    assert _rows(isolated_plan_db, "SELECT COUNT(*) FROM plan_publication") == [(0,)]
    assert _rows(isolated_plan_db, "SELECT verification_status FROM plan_page_observation") == [("verification_failed",)]
    assert _rows(isolated_plan_db, "SELECT status FROM plan_import_attempt") == [("failed",)]


def test_actual_current_attachment_changed(fake_confluence, prepared_input, isolated_plan_db):
    client = fake_confluence
    def mutate(page):
        if any(c[0] == "PUT" for c in client.calls):
            # Old uploaded bytes remain available and match, latest is foreign.
            client.uploaded.version = 2
            client.blobs[(client.uploaded.filename, 2)] = b"foreign latest"
        return page
    client.mutate_get = mutate
    with pytest.raises(UploadVerificationConflict):
        apply_plan(client, "test-page", prepared_input, "лей", project_slug="test")
    assert _rows(isolated_plan_db, "SELECT COUNT(*) FROM plan_publication") == [(0,)]


def test_apply_existing_macro_preserves_all_ids(fake_confluence, prepared_input, isolated_plan_db):
    client = fake_confluence
    client.page["body"]["storage"]["value"] += build_macro_html("stable-mid", "stable-id", "stable-hash")
    apply_plan(client, "test-page", prepared_input, "лей", project_slug="test")
    macro = find_macro(client.page["body"]["storage"]["value"])
    assert (macro.macro_id, macro.param_id, macro.param_hash) == ("stable-mid", "stable-id", "stable-hash")


def test_apply_plan_put_409_retries_only_storage_stage(fake_confluence, prepared_input, isolated_plan_db):
    client = fake_confluence
    client.conflicts = 1
    apply_plan(client, "test-page", prepared_input, "лей", project_slug="test")
    assert sum(c[0] == "POST_ATTACHMENT" for c in client.calls) == 1
    assert sum(c[0] == "PUT" for c in client.calls) == 2
    assert "Правка соседа" in client.page["body"]["storage"]["value"]
    assert client.page["version"]["number"] == 5


def test_apply_plan_put_409_exhausted_retries_raises(fake_confluence, prepared_input, isolated_plan_db):
    client = fake_confluence
    client.conflicts = 3
    with pytest.raises(ConfluenceError):
        apply_plan(client, "test-page", prepared_input, "лей", project_slug="test")
    assert sum(c[0] == "PUT" for c in client.calls) == 3
    assert _rows(isolated_plan_db, "SELECT COUNT(*) FROM plan_publication") == [(0,)]


def test_get_after_put_failure_is_unconfirmed(fake_confluence, prepared_input, isolated_plan_db):
    client = fake_confluence
    def fail(page):
        if any(c[0] == "PUT" for c in client.calls):
            raise TimeoutError("GET after PUT")
        return page
    client.mutate_get = fail
    with pytest.raises(TimeoutError):
        apply_plan(client, "test-page", prepared_input, "лей", project_slug="test")
    assert _rows(isolated_plan_db, "SELECT COUNT(*) FROM plan_publication") == [(0,)]


def test_apply_plan_preflight_failure_blocks_all_http(fake_confluence, prepared_input, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated SQL/file failure")
    monkeypatch.setattr("pipeline.preflight_archive", boom)
    with pytest.raises(RuntimeError):
        apply_plan(fake_confluence, "test-page", prepared_input, "лей", project_slug="test")
    assert all(c[0] == "GET" for c in fake_confluence.calls)
