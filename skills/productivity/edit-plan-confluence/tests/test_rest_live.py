"""Live Confluence tests — skipped unless EDITPLAN_LIVE=1."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live


def test_live_get_test_page():
    if os.environ.get("EDITPLAN_LIVE") != "1":
        pytest.skip("live REST only with EDITPLAN_LIVE=1")
    from conf_client import ConfluenceClient

    client = ConfluenceClient()
    page = client.get_page("519501810")
    assert page["id"] == "519501810"


def test_live_apply_plan_ok(mpp_fixture, monkeypatch):
    if os.environ.get("EDITPLAN_LIVE") != "1":
        pytest.skip("live REST only with EDITPLAN_LIVE=1")
    from conf_client import ConfluenceClient
    from pipeline import apply_plan

    monkeypatch.setattr("pipeline.upload_gantt_json", lambda *a, **k: 1)

    client = ConfluenceClient()
    result = apply_plan(client, "519501810", mpp_fixture, "лей")
    assert result.page_id == "519501810"
    assert result.page_url.startswith("https://dom.tutu.ru/")
