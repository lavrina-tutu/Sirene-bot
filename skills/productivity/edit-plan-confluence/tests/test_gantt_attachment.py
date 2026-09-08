from __future__ import annotations

import json
from unittest.mock import MagicMock

from gantt_attachment import find_gantt_attachment, upload_gantt_json
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
        resp.read.return_value = json.dumps({"results": [{"version": {"number": 5}}]}).encode()
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
    assert ver == 5
    assert calls[0][1] == "POST"
    assert "/data?conflictPolicy=override" in calls[0][0]
