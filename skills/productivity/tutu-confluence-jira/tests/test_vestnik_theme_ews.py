"""EWS ResolveNames unit tests."""
from __future__ import annotations

from vestnik_theme_ews import is_latin_query, resolve_names


def test_cyrillic_no_protocol_calls():
  calls = []

  def fake_resolve(**kwargs):
    calls.append(kwargs)
    return []

  result = resolve_names("Иванов", protocol_resolve=fake_resolve)
  assert result == []
  assert calls == []


def test_latin_one_call():
  calls = []

  def fake_resolve(names, **kwargs):
    calls.append(names)
    return []

  resolve_names("shubchik", protocol_resolve=fake_resolve)
  assert calls == [["shubchik"]]


def test_no_results_empty_list():
  def fake_resolve(names, **kwargs):
    raise Exception("No results were found")

  assert resolve_names("nobody", protocol_resolve=fake_resolve) == []
