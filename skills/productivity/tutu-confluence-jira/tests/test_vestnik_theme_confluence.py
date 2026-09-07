"""Confluence wrapper unit tests."""
from __future__ import annotations

import pytest

from section_patch import build_put_payload
from vestnik_theme_confluence import put_storage, resolve_ref
from vestnik_theme_errors import ConflictError, VestnikError


def test_build_put_payload_no_space():
  payload = build_put_payload("T", 3, "<p>x</p>")
  assert "space" not in payload


def test_resolve_numeric_id_no_http():
  assert resolve_ref("517103930", token="tok") == "517103930"


def test_put_storage_409(monkeypatch):
  def fake_put(*args, **kwargs):
    raise RuntimeError("HTTP 409: conflict")

  monkeypatch.setattr("vestnik_theme_confluence.put_page", fake_put)
  with pytest.raises(ConflictError):
    put_storage("1", title="T", current_version=1, storage="<p>x</p>", token="tok")


def test_resolve_display_url(monkeypatch):
  def fake_api(method, url, token):
    assert "spaceKey=DPAN" in url
    return {"results": [{"id": "999"}]}

  monkeypatch.setattr("vestnik_theme_confluence._api_request", fake_api)
  pid = resolve_ref(
    "https://dom.tutu.ru/display/DPAN/Test+Page",
    token="tok",
  )
  assert pid == "999"
