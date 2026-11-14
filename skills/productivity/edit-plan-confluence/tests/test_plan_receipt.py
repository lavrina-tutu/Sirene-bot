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
