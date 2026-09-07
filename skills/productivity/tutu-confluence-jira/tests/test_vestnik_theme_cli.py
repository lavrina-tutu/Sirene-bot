"""CLI / orchestrator unit tests."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from vestnik_theme import main, run_add
from vestnik_theme_author import Material
from vestnik_theme_block import OrgNode
from vestnik_theme_errors import HitlStop


def test_help():
  with pytest.raises(SystemExit) as exc:
    from vestnik_theme import _build_parser
    _build_parser().parse_args(["add", "--help"])
  assert exc.value.code == 0


def test_dry_run_no_put(storage_vestnik_ok: str, monkeypatch):
  put_calls = []
  monkeypatch.setattr(
    "vestnik_theme.confirm_userkey",
    lambda uk, **kw: {"userkey": uk, "username": "shubchik", "displayName": "X"},
  )

  def fake_get(page_id, **kwargs):
    if page_id == "324382467":
      return {
        "title": "Вестник",
        "version": {"number": 10},
        "body": {"storage": {"value": storage_vestnik_ok}},
      }
    return {
      "title": "Материал",
      "space": {"key": "TRAVELCENTER"},
      "history": {
        "createdBy": {
          "username": "shubchik",
          "userKey": "key1",
          "displayName": "Шубчик",
        },
      },
      "version": {"number": 1},
      "body": {"storage": {"value": ""}},
    }

  def fake_put(*args, **kwargs):
    put_calls.append(args)
    return {}

  rc = run_add(
    ["add", "--page-id", "517103930"],
    get_page_fn=fake_get,
    put_fn=fake_put,
    lookup_fn=lambda u: (OrgNode("shubchik", "DS", "DS", "zhirov"), "ac"),
    walk_fn=lambda n: ("DS", ""),
  )
  assert rc == 0
  assert put_calls == []


def test_apply_noop_no_put(storage_vestnik_ok: str, monkeypatch):
  put_calls = []
  monkeypatch.setattr(
    "vestnik_theme.confirm_userkey",
    lambda uk, **kw: {"userkey": uk, "username": "shubchik", "displayName": "X"},
  )

  def fake_get(page_id, **kwargs):
    storage = storage_vestnik_ok.replace(
      'ri:content-title="Существующая тема"',
      'ri:content-title="Существующая тема" pageId=517103930',
    )
    if page_id == "324382467":
      return {
        "title": "Вестник",
        "version": {"number": 10},
        "body": {"storage": {"value": storage}},
      }
    return {
      "title": "Существующая тема",
      "space": {"key": "TRAVELCENTER"},
      "history": {
        "createdBy": {"username": "shubchik", "userKey": "key1", "displayName": "X"},
      },
      "version": {"number": 1},
      "body": {"storage": {"value": ""}},
    }

  rc = run_add(
    ["add", "--page-id", "517103930", "--apply"],
    get_page_fn=fake_get,
    put_fn=lambda *a, **k: put_calls.append(1),
    lookup_fn=lambda u: (OrgNode("shubchik", "DS", "DS", "zhirov"), "ac"),
    walk_fn=lambda n: ("DS", ""),
  )
  assert rc == 0
  assert put_calls == []


def test_hitl_no_errorbus(monkeypatch, storage_vestnik_ok: str):
  calls = []
  monkeypatch.setattr(
    "vestnik_theme.report_technical",
    lambda *a, **k: calls.append(a),
  )
  monkeypatch.setattr(
    "vestnik_theme.confirm_userkey",
    lambda uk, **kw: {"userkey": uk, "username": "x", "displayName": "X"},
  )

  def fake_get(page_id, **kwargs):
    return {
      "title": "Материал",
      "space": {"key": "TRAVELCENTER"},
      "history": {"createdBy": {"username": "x", "userKey": "k", "displayName": "X"}},
      "version": {"number": 1},
      "body": {"storage": {"value": ""}},
    }

  def lookup_fail(u):
    raise HitlStop(kind="contact_missing", message="контакт не найден")

  rc = run_add(
    ["add", "--page-id", "517103930"],
    get_page_fn=fake_get,
    lookup_fn=lookup_fail,
  )
  assert rc == 2
  assert calls == []


def test_404_material_errorbus(monkeypatch):
  calls = []
  monkeypatch.setattr(
    "vestnik_theme.report_technical",
    lambda stage, msg, **k: calls.append((stage, msg)),
  )
  monkeypatch.setattr("vestnik_theme.load_token", lambda: "tok")

  def fake_get(page_id, **kwargs):
    raise RuntimeError("HTTP 404: not found")

  rc = run_add(
    ["add", "--page-id", "999999"],
    get_page_fn=fake_get,
  )
  assert rc == 1
  assert any(c[0] == "fetch" for c in calls)


def test_apply_409_retry_then_success(storage_vestnik_ok: str, monkeypatch):
  put_calls = []
  state = {"storage": storage_vestnik_ok, "version": 10}

  monkeypatch.setattr(
    "vestnik_theme.confirm_userkey",
    lambda uk, **kw: {"userkey": uk, "username": "shubchik", "displayName": "X"},
  )

  def fake_get(page_id, **kwargs):
    if page_id == "324382467":
      return {
        "title": "Вестник",
        "version": {"number": state["version"]},
        "body": {"storage": {"value": state["storage"]}},
      }
    return {
      "title": "Новая тема",
      "space": {"key": "TRAVELCENTER"},
      "history": {"createdBy": {"username": "shubchik", "userKey": "key1", "displayName": "X"}},
      "version": {"number": 1},
      "body": {"storage": {"value": ""}},
    }

  from vestnik_theme_errors import ConflictError
  from vestnik_theme_patch import compose_row_inner, patch_first_empty_tr
  from vestnik_theme_author import Material

  mat = Material(
    page_id="517103930",
    title="Новая тема",
    space_key="TRAVELCENTER",
    created_by_username="shubchik",
    created_by_userkey="key1",
    created_by_display="X",
  )

  def fake_put(page_id, *, title, current_version, storage, token=None):
    put_calls.append(current_version)
    if len(put_calls) == 1:
      raise ConflictError("HTTP 409: conflict")
    state["version"] = current_version + 1
    state["storage"] = storage
    return {"version": {"number": state["version"]}}

  rc = run_add(
    ["add", "--page-id", "517103930", "--apply"],
    get_page_fn=fake_get,
    put_fn=fake_put,
    lookup_fn=lambda u: (OrgNode("shubchik", "DS", "DS", "zhirov"), "ac"),
    walk_fn=lambda n: ("DS", ""),
  )
  assert rc == 0
  assert put_calls == [10, 10]
  inner = compose_row_inner(month="август", block="DS", materials=[mat], author_userkey="key1")
  assert inner in state["storage"]
