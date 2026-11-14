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

    client.get_page.return_value = {"id": "999"}  # resume GET of created page
    page2, macro_id2, param_id2, _ = create_child_page(
        client, "1", "Title", "<p>itogo</p>", attempt_id="attempt-resume-1",
    )
    assert client.create_page.call_count == 1  # не вызван повторно
    assert page2["id"] == page1["id"] == "999"
    assert macro_id2 == macro_id1
    assert param_id2 == param_id1
