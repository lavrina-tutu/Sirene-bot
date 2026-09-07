"""Author / userkey unit tests."""
from __future__ import annotations

import pytest

from vestnik_theme_author import confirm_userkey, material_from_page
from vestnik_theme_errors import VestnikError


PAGE_SHUBCHIK = {
  "title": "Новый экран поездок",
  "space": {"key": "TRAVELCENTER"},
  "history": {
    "createdBy": {
      "username": "shubchik",
      "userKey": "8a8383b593a26ea60194abdf8d090020",
      "displayName": "Шубчик",
    },
  },
  "version": {
    "by": {"username": "editor", "userKey": "WRONG"},
  },
}


def test_material_from_page_shubchik():
  m = material_from_page(PAGE_SHUBCHIK, "517103930")
  assert m.created_by_username == "shubchik"
  assert m.space_key == "TRAVELCENTER"
  assert m.space_key != "DATASC"


def test_version_by_ignored():
  m = material_from_page(PAGE_SHUBCHIK, "517103930")
  assert m.created_by_username == "shubchik"


def test_empty_userkey_raises():
  page = dict(PAGE_SHUBCHIK)
  page["history"] = {"createdBy": {"username": "x", "userKey": ""}}
  with pytest.raises(VestnikError, match="userKey"):
    material_from_page(page, "1")


def test_confirm_userkey_uses_api_key():
  class FakeClient:
    def get_user_by_key(self, userkey: str) -> dict:
      return {
        "username": "shubchik",
        "displayName": "Шубчик",
        "userKey": "confirmed-key-xyz",
      }

  result = confirm_userkey("orig-key", client=FakeClient(), cache={})
  assert result["userkey"] == "orig-key"
