"""ResolveAIDUnit unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vestnik_theme_block import (
  AID_DIRECTOR,
  AID_HEADS,
  OrgNode,
  contact_to_node,
  format_block,
  lookup_or_gal,
  walk_aid_unit,
)
from vestnik_theme_ews import GalPerson
from vestnik_theme_errors import HitlStop


class FakeStore:
  def __init__(self, contacts: dict | None = None):
    self.contacts = contacts or {}
    self.update_contact = MagicMock()

  def get_contact(self, login: str):
    return self.contacts.get(login.lower())

  def find_contacts(self, query: str):
    return []


def test_ac_hit_walk_to_head():
  store = FakeStore({
    "shubchik": {
      "login": "shubchik",
      "department": "Data Science",
      "team": "DS",
      "reports_to": "zhirov",
    },
    "zhirov": {
      "login": "zhirov",
      "department": "Аналитика",
      "team": "DS",
      "reports_to": "aralov",
    },
  })
  node = contact_to_node(store.get_contact("shubchik"))
  block, warning = walk_aid_unit(node, store=store, gal_nodes={})
  assert block == "DS"
  assert warning == ""


def test_gal_in_memory_no_store_write():
  store = FakeStore()
  person = GalPerson(
    login="newuser",
    email="newuser@tutu.ru",
    department="BI",
    team="BI",
    job_title="",
    manager_display="",
    reports_to_login="",
  )

  def ews_resolve(q):
    return [person]

  node, source = lookup_or_gal("newuser", store=store, ews_resolve=ews_resolve)
  assert source == "gal"
  assert store.update_contact.call_count == 0


def test_miss_both_hitl():
  store = FakeStore()

  def ews_resolve(q):
    return []

  with pytest.raises(HitlStop, match="контакт не найден"):
    lookup_or_gal("nobody", store=store, ews_resolve=ews_resolve)


def test_hit_without_reports_to_warning():
  store = FakeStore()
  node = OrgNode(login="orphan", department="X", team="Y", reports_to="")
  block, warning = walk_aid_unit(node, store=store, gal_nodes={})
  assert block == ""
  assert "не найден" in warning


def test_author_in_aid_heads():
  store = FakeStore()
  node = OrgNode(login="tkachenkoav", department="АИД", team="DS", reports_to="aralov")
  block, warning = walk_aid_unit(node, store=store, gal_nodes={})
  assert block == "DS"
  assert warning == ""


def test_stop_at_aralov_previous_dept():
  store = FakeStore({
    "worker": {"login": "worker", "department": "BI", "team": "BI", "reports_to": AID_DIRECTOR},
  })
  node = contact_to_node(store.get_contact("worker"))
  block, warning = walk_aid_unit(node, store=store, gal_nodes={})
  assert block == "BI"


def test_cycle_not_infinite():
  store = FakeStore({
    "a": {"login": "a", "department": "X", "team": "X", "reports_to": "b"},
    "b": {"login": "b", "department": "Y", "team": "Y", "reports_to": "a"},
  })
  node = contact_to_node(store.get_contact("a"))
  block, warning = walk_aid_unit(node, store=store, gal_nodes={})
  assert block == ""


def test_format_block_known_label():
  assert format_block("ds", "ds", None) == "DS"
