from __future__ import annotations

import json

import pytest

import plan_receipt as pr


@pytest.fixture(autouse=True)
def isolate_workvault(tmp_path, monkeypatch):
    wv = tmp_path / "WorkVault"
    monkeypatch.setattr("plan_receipt.get_workvault_path", lambda: wv)
    return wv


def test_mask_secrets_by_key():
    payload = {"CONFLUENCE_TOKEN": "s3cr3t", "Authorization": "Bearer abc.def", "ok": "value"}
    masked = pr.mask_secrets(payload)
    assert masked["CONFLUENCE_TOKEN"] == "***MASKED***"
    assert masked["Authorization"] == "***MASKED***"
    assert masked["ok"] == "value"


def test_mask_secrets_bearer_string_anywhere():
    payload = {"detail": "sent header Bearer abcdef123.ghijk"}
    masked = pr.mask_secrets(payload)
    assert "abcdef123" not in masked["detail"]
    assert "Bearer ***MASKED***" in masked["detail"]


def test_write_receipt_no_secrets_on_disk(tmp_path):
    path = pr.write_receipt("attempt-1", "event-1", {
        "stage": "archive",
        "headers": {"Authorization": "Bearer tok123"},
    })
    text = path.read_text(encoding="utf-8")
    assert "tok123" not in text
    assert "bearer" not in text.lower() or "masked" in text.lower()


def test_write_receipt_idempotent_path():
    p1 = pr.write_receipt("attempt-1", "event-1", {"a": 1})
    p2 = pr.write_receipt("attempt-1", "event-1", {"a": 2})
    assert p1 == p2
    data = json.loads(p2.read_text(encoding="utf-8"))
    assert data["a"] == 2


def test_read_receipt_roundtrip():
    pr.write_receipt("attempt-2", "event-9", {"x": "y"})
    out = pr.read_receipt("attempt-2", "event-9")
    assert out == {"x": "y"}


def test_read_receipt_missing_returns_none():
    assert pr.read_receipt("no-such-attempt", "no-event") is None


def test_single_receipt_all_required_nullable_fields():
    import copy
    import jsonschema
    receipt = pr.single_receipt()
    pr.validate_single_receipt(receipt)
    assert receipt["published"] is False and receipt["page_id"] is None and receipt["page_url"] is None
    assert receipt["verification"]["schedule"]["status"] == "not_verified"
    for key in receipt:
        broken = copy.deepcopy(receipt)
        del broken[key]
        with pytest.raises(jsonschema.ValidationError):
            pr.validate_single_receipt(broken)
    for field in ("archive", "attachment", "storage", "schedule"):
        broken = copy.deepcopy(receipt)
        del broken["verification"][field]
        with pytest.raises(jsonschema.ValidationError):
            pr.validate_single_receipt(broken)
    for obj in ("source",):
        for key in receipt[obj]:
            broken = copy.deepcopy(receipt)
            del broken[obj][key]
            with pytest.raises(jsonschema.ValidationError):
                pr.validate_single_receipt(broken)
    for key in receipt["verification"]["schedule"]:
        broken = copy.deepcopy(receipt)
        del broken["verification"]["schedule"][key]
        with pytest.raises(jsonschema.ValidationError):
            pr.validate_single_receipt(broken)


@pytest.mark.parametrize("field,value", [("published", True), ("page_id", "123"), ("page_url", "https://invalid"),
                                         ("external_effect", "storage_written"), ("attachment_version", 2)])
def test_single_receipt_save_invariants_reject_remote_effect(field, value):
    import jsonschema
    receipt = pr.single_receipt()
    receipt[field] = value
    with pytest.raises(jsonschema.ValidationError):
        pr.validate_single_receipt(receipt)


def test_atomic_mirror_failure_keeps_previous_json(tmp_path, monkeypatch):
    path = pr.write_receipt("op", "save", {"status":"old"})
    original = path.read_bytes()
    def fail(*a, **k):
        raise OSError("replace failed")
    monkeypatch.setattr(pr.os, "replace", fail)
    with pytest.raises(OSError):
        pr.write_receipt("op", "save", {"status":"new"})
    assert path.read_bytes() == original
    assert not list(path.parent.glob(".receipt-*"))


@pytest.mark.parametrize("value", ["Authorization: Basic c2VjcmV0", "CONFLUENCE_TOKEN=s3cr3t", "token: s3cr3t", "Bearer s3cr3t"])
def test_mask_driver_strings(value):
    assert "s3cr3t" not in pr.mask_secrets(value)
    assert "c2VjcmV0" not in pr.mask_secrets(value)


@pytest.mark.parametrize("attempt,event", [("../escape", "save"), ("op", "../save")])
def test_receipt_rejects_path_escape(attempt, event):
    with pytest.raises(ValueError):
        pr.write_receipt(attempt, event, {})


def test_source_value_receipt_does_not_verify_schedule():
    r = pr.single_receipt()
    r['verification']['source_values']['status'] = 'verified'
    assert r['verification']['schedule']['status'] == 'not_verified'
    pr.validate_single_receipt(r)
    del r['verification']['source_values']
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):
        pr.validate_single_receipt(r)
