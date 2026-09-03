"""Section patch unit tests (B0)."""
from __future__ import annotations

import pytest

from section_patch import (
  build_put_payload,
  find_section_span,
  replace_section_inner,
)


def test_find_section_span_preserves_heading(storage_ok: str):
  start, end, level = find_section_span(storage_ok, "Ключевые поставки и сроки")
  assert level == 2
  inner = storage_ok[start:end]
  assert "<table" in inner
  assert "Ключевые поставки" not in inner
  assert "Прописываем в том случае" not in inner


def test_replace_section_inner(storage_ok: str):
  new_table = "<table><tbody><tr><td>NEW</td><td>2026</td></tr></tbody></table>"
  patched = replace_section_inner(storage_ok, "Ключевые поставки и сроки", new_table)
  assert "Ключевые поставки и сроки" in patched
  assert "Прописываем в том случае" in patched
  assert "NEW" in patched
  assert patched.count("<table") == 1
  assert "<h2>Бюджет</h2>" in patched


def test_heading_gone_raises(storage_heading_gone: str):
  with pytest.raises(ValueError, match="heading not found"):
    find_section_span(storage_heading_gone, "Ключевые поставки и сроки")


def test_build_put_payload_no_space():
  payload = build_put_payload("Title", 5, "<p>x</p>")
  assert "space" not in payload
  assert payload["version"]["number"] == 5
  assert payload["body"]["storage"]["value"] == "<p>x</p>"
  assert payload["type"] == "page"
