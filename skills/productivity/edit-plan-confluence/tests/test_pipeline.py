from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline import LIVE_AB_PAGE, apply_plan, build_plan_empty, build_plan_from_mpp


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


def _mock_page_no_macro():
    return {
        "id": "519501810",
        "title": "Test Page",
        "version": {"number": 3},
        "body": {"storage": {"value": "<p>Some intro</p>"}},
    }


def test_apply_plan_without_confirm_writes_nothing(mpp_fixture):
    client = MagicMock()
    client.get_page.return_value = _mock_page_no_macro()
    with pytest.raises(PermissionError):
        apply_plan(client, "519501810", mpp_fixture, "нет")
    client.put_page.assert_not_called()
    client.list_attachments.assert_not_called()


def test_apply_plan_confirm_order_upload_then_put(mpp_fixture, monkeypatch):
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        {"version": {"number": 5}},
    ]
    client.list_attachments.return_value = []
    calls = []

    def track_upload(*args, **kwargs):
        calls.append("upload")
        return 2

    monkeypatch.setattr("pipeline.upload_gantt_json", track_upload)

    def track_put(*args, **kwargs):
        calls.append("put")
        return {}

    client.put_page.side_effect = track_put
    apply_plan(client, "519501810", mpp_fixture, "лей")
    assert calls == ["upload", "put"]
    client.put_page.assert_called_once()
    assert client.put_page.call_args[0][3] == 6


def test_apply_plan_put_version_is_incremented(mpp_fixture, monkeypatch):
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        {"version": {"number": 18}},
    ]
    client.list_attachments.return_value = []
    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)
    apply_plan(client, "519501810", mpp_fixture, "лей")
    assert client.put_page.call_args[0][3] == 19


def test_apply_plan_itogo_above_new_macro(mpp_fixture, monkeypatch):
    client = MagicMock()
    client.get_page.side_effect = [
        _mock_page_no_macro(),
        {"version": {"number": 4}},
    ]
    client.list_attachments.return_value = []
    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)
    apply_plan(client, "519501810", mpp_fixture, "лей")
    storage = client.put_page.call_args[0][2]
    macro_pos = storage.index("gantt-chart-planner")
    itogo_pos = storage.index("Итого:")
    assert itogo_pos < macro_pos
