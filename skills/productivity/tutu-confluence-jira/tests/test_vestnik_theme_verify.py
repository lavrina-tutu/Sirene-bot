"""Verify unit tests."""
from __future__ import annotations

import re

from vestnik_theme_author import Material
from vestnik_theme_patch import first_nav_item_span, itogovy_table_span, patch_first_empty_tr, compose_row_inner
from vestnik_theme_verify import verify_vestnik


def _material() -> Material:
  return Material(
    page_id="517103930",
    title="Новая тема",
    space_key="TRAVELCENTER",
    created_by_username="shubchik",
    created_by_userkey="key-ok",
    created_by_display="Шубчик",
  )


def test_verify_ok_path(storage_vestnik_ok: str):
  inner = compose_row_inner(
    month=None,
    block="DS",
    materials=[_material()],
    author_userkey="key-ok",
  )
  after = patch_first_empty_tr(storage_vestnik_ok, inner)
  _, _, tab = first_nav_item_span(storage_vestnik_ok)
  result = verify_vestnik(
    before_storage=storage_vestnik_ok,
    after_storage=after,
    before_version=10,
    after_version=11,
    expected_min_version=11,
    materials=[_material()],
    author_userkey="key-ok",
    first_tab_name=tab,
  )
  assert result.ok


def test_verify_wrong_th_count(storage_vestnik_wrong_cols: str):
  result = verify_vestnik(
    before_storage=storage_vestnik_wrong_cols,
    after_storage=storage_vestnik_wrong_cols,
    before_version=1,
    after_version=2,
    expected_min_version=2,
    materials=[_material()],
    author_userkey="key-ok",
    first_tab_name="Август-Сентябрь 2026",
  )
  assert not result.ok


def test_verify_brief_leak(storage_vestnik_ok: str):
  leaked = storage_vestnik_ok + "<p>Не копировать</p>"
  result = verify_vestnik(
    before_storage=storage_vestnik_ok,
    after_storage=leaked,
    before_version=1,
    after_version=2,
    expected_min_version=2,
    materials=[_material()],
    author_userkey="key-ok",
    first_tab_name="Август-Сентябрь 2026",
  )
  assert not result.ok
  assert result.checks.get("no_brief_leak") is False


def test_verify_nav_count_changed(storage_vestnik_ok: str):
  broken = storage_vestnik_ok.replace(
    'ac:name="horizontal-nav-item"',
    'ac:name="horizontal-nav-item-extra"',
    1,
  )
  result = verify_vestnik(
    before_storage=storage_vestnik_ok,
    after_storage=broken,
    before_version=1,
    after_version=2,
    expected_min_version=2,
    materials=[_material()],
    author_userkey="key-ok",
    first_tab_name="Август-Сентябрь 2026",
  )
  assert not result.ok
