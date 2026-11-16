from __future__ import annotations

import hashlib
import json
import pytest
from unittest.mock import MagicMock

from gantt_attachment import find_gantt_attachment, upload_gantt_json, verify_uploaded
from macro import MacroInfo


def test_find_gantt_attachment():
    macro = MacroInfo("abc", "id", "hash", "gantt-chart-abc.json")
    attachments = [{"id": "1", "title": "gantt-chart-abc.json", "version": {"number": 3}}]
    att = find_gantt_attachment(attachments, macro)
    assert att is not None
    assert att.version == 3


def test_upload_uses_post_data(monkeypatch):
    macro = MacroInfo("abc", "id", "hash", "gantt-chart-abc.json")
    client = MagicMock()
    client.base_url = "https://dom.tutu.ru"
    client.token = "tok"
    calls = []

    def fake_urlopen(req, timeout=120):
        calls.append((req.full_url, req.method))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": [{"id": "9", "title": macro.attachment_name, "version": {"number": 5}}]}).encode()
        resp.__enter__ = lambda s: resp
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    import gantt_attachment as ga

    monkeypatch.setattr(ga, "urlopen", fake_urlopen)
    ver = upload_gantt_json(
        client,
        "519501810",
        macro.attachment_name,
        {"eventsData": []},
        find_gantt_attachment([{"id": "9", "title": macro.attachment_name, "version": {"number": 2}}], macro),
    )
    assert ver.version == 5
    assert ver.attach_id == "9"
    assert calls[0][1] == "POST"
    assert calls[0][0].endswith('/data') and 'conflictPolicy' not in calls[0][0]


def test_verify_uploaded_matches_version_specific_get():
    """P1.W1.5/AC-105: version-specific GET, не latest; сверка hash."""
    payload = b'{"a": 1}'
    sha = hashlib.sha256(payload).hexdigest()
    client = MagicMock()
    client.download_attachment_version.return_value = payload
    ok, raw = verify_uploaded(client, "519501810", "gantt-chart-x.json", 3, sha, attachment_id="actual-id")
    assert ok is True
    assert raw == payload
    client.download_attachment_version.assert_called_once_with("519501810", "actual-id", "gantt-chart-x.json", 3)


def test_verify_uploaded_hash_mismatch_is_conflict_not_crash():
    client = MagicMock()
    client.download_attachment_version.return_value = b"different-bytes"
    ok, raw = verify_uploaded(client, "519501810", "gantt-chart-x.json", 3, "deadbeef" * 8, attachment_id="actual-id")
    assert ok is False


@pytest.mark.parametrize("changed", ["id", "title", "version", "page"])
def test_download_requires_exact_metadata(changed, monkeypatch):
    from conf_client import ConfluenceClient
    client = ConfluenceClient(token="test-token", base_url="https://example.invalid")
    metadata = {"id": "A1", "title": "gantt.json", "version": {"number": 3}, "container": {"id": "P1"}}
    if changed == "version":
        metadata["version"]["number"] = 4
    elif changed == "page":
        metadata["container"]["id"] = "P2"
    else:
        metadata[changed] = "wrong"
    monkeypatch.setattr(client, "get_attachment", lambda *a, **k: metadata)
    download = MagicMock()
    monkeypatch.setattr(client, "download_attachment", download)
    with pytest.raises(ValueError):
        client.download_attachment_version("P1", "A1", "gantt.json", 3)
    download.assert_not_called()


def test_download_exact_historical_version_even_if_latest_changed(monkeypatch):
    from conf_client import ConfluenceClient
    client = ConfluenceClient(token="test-token", base_url="https://example.invalid")
    request = MagicMock(return_value={"id": "A1", "title": "gantt.json", "version": {"number": 3}, "container": {"id": "P1"}})
    monkeypatch.setattr(client, "_request", request)
    download = MagicMock(return_value=b"version 3")
    monkeypatch.setattr(client, "download_attachment", download)
    assert client.download_attachment_version("P1", "A1", "gantt.json", 3) == b"version 3"
    assert request.call_args.kwargs["query"]["version"] == "3"
    assert 'status' not in request.call_args.kwargs['query']
    download.assert_called_once_with("P1", "gantt.json", 3)


def test_no_fallback_to_unrelated_gantt_attachment():
    macro = MacroInfo("mid", "expected", "hash", "gantt-chart-expected.json")
    assert find_gantt_attachment([{"id": "wrong", "title": "gantt-chart-other.json", "version": {"number": 1}}], macro) is None


def test_upload_missing_identity_fails_closed(monkeypatch):
    import gantt_attachment as ga
    from gantt_attachment import UploadVerificationConflict
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = b'{"results":[{"version":{"number":1}}]}'
    monkeypatch.setattr(ga, "urlopen", lambda *a, **k: response)
    client = MagicMock(base_url="https://example.invalid", token="fake")
    with pytest.raises(UploadVerificationConflict):
        upload_gantt_json(client, "P1", "gantt.json", {}, None)
