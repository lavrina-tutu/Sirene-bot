from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from child_page import build_child_storage, create_child_page, default_child_title


def test_default_child_title():
    t = default_child_title("Родитель")
    assert t.startswith("Родитель. План ")
    assert "План" in t


def test_build_child_storage():
    s = build_child_storage("<p>itogo</p>", "<p>macro</p>")
    assert s.index("itogo") < s.index("macro")


@pytest.fixture(autouse=True)
def isolate_receipts(tmp_path, monkeypatch):
    wv = tmp_path / "WorkVault"
    monkeypatch.setattr("plan_receipt.get_workvault_path", lambda: wv)
    return wv


def _client_with_parent():
    client = MagicMock()
    client.get_page.return_value = {"id": "1", "space": {"key": "SP"}}
    client.create_page.return_value = {"id": "999"}
    return client


def test_create_child_page_without_attempt_id_always_creates():
    client = _client_with_parent()
    page, *_ = create_child_page(client, "1", "Title", "<p>itogo</p>")
    assert page["id"] == "999"
    client.create_page.assert_called_once()


def test_create_child_page_resume_reuses_existing_page_id():
    """AC-109: после сбоя upload повтор с тем же attempt_id не создаёт
    вторую дочку, использует сохранённый page_id."""
    client = _client_with_parent()
    page1, macro_id1, param_id1, _ = create_child_page(
        client, "1", "Title", "<p>itogo</p>", attempt_id="attempt-resume-1",
    )
    assert client.create_page.call_count == 1

    # A receipt alone is not proof: resume must receive actual macro/storage.
    storage=client.create_page.call_args.args[2]
    client.get_page.return_value = {"id": "999",'version':{'number':1},'body':{'storage':{'value':storage}}}
    page2, macro_id2, param_id2, _ = create_child_page(
        client, "1", "Title", "<p>itogo</p>", attempt_id="attempt-resume-1",
    )
    assert client.create_page.call_count == 1  # не вызван повторно
    assert page2["id"] == page1["id"] == "999"
    assert macro_id2 == macro_id1
    assert param_id2 == param_id1


@pytest.mark.parametrize("failure", ["false", "hash", "download"])
def test_child_rejects_attachment_failure(failure, fake_confluence, prepared_input, monkeypatch):
    import pipeline
    from gantt_attachment import UploadVerificationConflict
    from plan_receipt import read_receipt
    client = fake_confluence
    if failure == "false":
        monkeypatch.setattr(pipeline, "verify_uploaded", lambda *a, **k: (False, b""))
    elif failure == "hash":
        monkeypatch.setattr(pipeline, "verify_uploaded", lambda *a, **k: (True, b"wrong"))
    else:
        client.download_error = TimeoutError("after child POST")
    with pytest.raises((UploadVerificationConflict, TimeoutError)):
        pipeline.create_child_with_plan(client, "test-page", "лей", mpp_path=prepared_input, attempt_id="child-fail")
    assert not any(c[0] == "PUT" for c in client.calls)
    assert read_receipt("child-fail", "child_complete") is None
    failure_receipt = read_receipt("child-fail", "failure-child_upload")
    assert failure_receipt["published"] is None
    assert failure_receipt["external_effect"] == "partial"


@pytest.mark.parametrize("kind", ["duplicate", "macro_id", "param_id", "param_hash", "attachment", "itogo", "extra_itogo", "labour", "foreign"])
def test_child_storage_corruption(kind, fake_confluence, prepared_input):
    import pipeline
    from plan_receipt import read_receipt
    from plan_verify import PublicationVerificationError
    from test_pipeline import _corrupt
    client = fake_confluence
    def mutate(page):
        if page["id"] == "test-child":
            storage = page["body"]["storage"]["value"]
            # Child has no neighboring paragraph; add an unexpected foreign block.
            page["body"]["storage"]["value"] = storage + "<p>unexpected</p>" if kind == "foreign" else _corrupt(storage, kind)
        return page
    client.mutate_get = mutate
    with pytest.raises(PublicationVerificationError):
        pipeline.create_child_with_plan(client, "test-page", "лей", mpp_path=prepared_input, attempt_id="child-storage")
    assert read_receipt("child-storage", "child_complete") is None
    assert read_receipt("child-storage", "failure-storage_verify")["published"] is None


def test_resume_rechecks_actual_bytes(fake_confluence, prepared_input):
    import pipeline
    from gantt_attachment import UploadVerificationConflict
    client = fake_confluence
    first = pipeline.create_child_with_plan(client, "test-page", "лей", mpp_path=prepared_input, attempt_id="child-resume")
    second = pipeline.create_child_with_plan(client, "test-page", "лей", mpp_path=prepared_input, attempt_id="child-resume")
    assert first.attachment_version == second.attachment_version
    assert sum(c[0] == "POST_PAGE" for c in client.calls) == 1
    assert sum(c[0] == "POST_ATTACHMENT" for c in client.calls) == 1
    client.blobs[(client.uploaded.filename, client.uploaded.version)] = b"corrupt after receipt"
    with pytest.raises(UploadVerificationConflict):
        pipeline.create_child_with_plan(client, "test-page", "лей", mpp_path=prepared_input, attempt_id="child-resume")
    assert sum(c[0] == "POST_ATTACHMENT" for c in client.calls) == 1


def test_child_resume_changed_current_version_rejected(fake_confluence, prepared_input):
    import pipeline
    from gantt_attachment import UploadVerificationConflict
    client = fake_confluence
    pipeline.create_child_with_plan(client, "test-page", "лей", mpp_path=prepared_input, attempt_id="child-latest")
    client.uploaded.version += 1
    client.blobs[(client.uploaded.filename, client.uploaded.version)] = b"foreign latest"
    with pytest.raises(UploadVerificationConflict):
        pipeline.create_child_with_plan(client, "test-page", "лей", mpp_path=prepared_input, attempt_id="child-latest")
    assert sum(c[0] == "POST_ATTACHMENT" for c in client.calls) == 1


def test_old_confirmed_child_upload_receipt_not_proof(fake_confluence, prepared_input):
    import pipeline
    from plan_receipt import write_receipt
    from gantt_attachment import UploadVerificationConflict
    write_receipt("old-child", "child_upload", {
        "status": "confirmed", "page_id": "test-child", "filename": "gantt-chart-old.json", "attachment_version": 1,
    })
    with pytest.raises(UploadVerificationConflict):
        pipeline._upload_child_attachment_with_receipt(fake_confluence, "old-child", "test-child", "gantt-chart-old.json", {})
    assert not fake_confluence.calls


@pytest.mark.parametrize('effect',['page','attachment'])
def test_legacy_child_lost_response_is_read_before_replay(fake_confluence, prepared_input, monkeypatch, effect):
    import pipeline
    from test_publish_resume import ProcessDeath
    client=fake_confluence
    owner,name=(client,'create_page') if effect=='page' else (pipeline,'upload_gantt_json')
    original=getattr(owner,name)
    def lose(*args,**kwargs):
        original(*args,**kwargs)
        raise ProcessDeath()
    monkeypatch.setattr(owner,name,lose)
    with pytest.raises(ProcessDeath):
        pipeline.create_child_with_plan(client,'test-page','лей',mpp_path=prepared_input,attempt_id='legacy-lost')
    monkeypatch.setattr(owner,name,original)
    result=pipeline.create_child_with_plan(client,'test-page','лей',mpp_path=prepared_input,attempt_id='legacy-lost')
    assert result.page_id=='test-child'
    assert sum(c[0]=='POST_PAGE' for c in client.calls)==sum(c[0]=='POST_ATTACHMENT' for c in client.calls)==1
