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
