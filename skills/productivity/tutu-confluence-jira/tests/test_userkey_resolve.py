"""Userkey batch-resolve unit tests (B1)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from userkey_resolve import (
  ConfluenceUserClient,
  extract_userkeys,
  resolve_all,
  resolve_user,
  write_contacts,
)

STORAGE_SAMPLE = """
<p><ac:link><ri:user ri:userkey="KEY_A"/></ac:link></p>
<p><ac:link><ri:user ri:userkey="KEY_B"/></ac:link></p>
<p><ac:link><ri:user ri:userkey="KEY_A"/></ac:link></p>
"""


def test_extract_userkeys_unique_order():
  keys = extract_userkeys(STORAGE_SAMPLE)
  assert keys == ["KEY_A", "KEY_B"]


def test_duplicate_userkey_single_http():
  calls: list[str] = []

  class FakeClient:
    def get_user_by_key(self, userkey: str) -> dict:
      calls.append(userkey)
      return {"username": f"u_{userkey}", "displayName": f"User {userkey}"}

  cache: dict = {}
  keys = ["KEY_A", "KEY_A", "KEY_B"]
  unique = list(dict.fromkeys(keys))
  rows = resolve_all(unique, FakeClient(), cache)

  assert calls == ["KEY_A", "KEY_B"]
  assert len(rows) == 2
  assert rows[0]["username"] == "u_KEY_A"
  assert resolve_user("KEY_A", cache, FakeClient())["username"] == "u_KEY_A"
  assert len(calls) == 2  # cache hit on second resolve_user


def test_json_contract_keys():
  client = MagicMock()
  client.get_user_by_key.return_value = {
    "username": "sereda",
    "displayName": "Середа Илья",
  }
  row = resolve_user("abc123", {}, client)
  assert set(row.keys()) == {"userkey", "username", "displayName"}
  assert row == {
    "userkey": "abc123",
    "username": "sereda",
    "displayName": "Середа Илья",
  }


def test_write_contacts_no_md_files(tmp_path: Path, monkeypatch):
  """Update existing contact only; no Contacts/*.md created."""
  contacts_dir = tmp_path / "Contacts"
  contacts_dir.mkdir()
  enc = contacts_dir / "contacts.enc"

  class FakeStore:
    def __init__(self):
      self.data = {
        "contacts": {
          "sereda": {"login": "sereda", "fio": "Середа Илья"},
        },
      }
      self.updates: list[tuple[str, dict]] = []

    def read(self):
      return self.data

    def update_contact(self, login: str, updates: dict):
      self.updates.append((login, updates))
      self.data["contacts"][login].update(updates)

  fake = FakeStore()

  def fake_load_store():
    return fake

  monkeypatch.setattr("userkey_resolve._load_store", fake_load_store)

  updated = write_contacts([
    {"userkey": "k1", "username": "sereda", "displayName": "Середа Илья"},
  ])
  assert updated == ["sereda"]
  assert fake.updates[0][1]["confluence_login"] == "sereda"
  assert fake.updates[0][1]["confluence_userkey"] == "k1"
  assert list(contacts_dir.glob("*.md")) == []


def test_cli_storage_file_json(tmp_path: Path, monkeypatch):
  from userkey_resolve import main

  storage = {"body": {"storage": {"value": STORAGE_SAMPLE}}}
  sf = tmp_path / "page.json"
  sf.write_text(json.dumps(storage), encoding="utf-8")

  class FakeClient:
    def get_user_by_key(self, userkey: str) -> dict:
      return {"username": userkey.lower(), "displayName": userkey}

  monkeypatch.setattr("userkey_resolve.ConfluenceUserClient", lambda token: FakeClient())
  monkeypatch.setattr("userkey_resolve.load_confluence_token", lambda: "tok")

  import io
  import contextlib

  buf = io.StringIO()
  with contextlib.redirect_stdout(buf):
    rc = main(["--storage-file", str(sf)])
  assert rc == 0
  data = json.loads(buf.getvalue())
  assert len(data) == 2
  assert data[0]["userkey"] == "KEY_A"
