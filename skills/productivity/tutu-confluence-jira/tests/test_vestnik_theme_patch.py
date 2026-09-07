"""Patch / dedup / compose unit tests."""
from __future__ import annotations

import re

import pytest

from vestnik_theme_author import Material
from vestnik_theme_errors import HitlStop, VestnikError
from vestnik_theme_patch import (
  compose_row_inner,
  count_nav_items,
  dedup,
  first_empty_tr_span,
  first_nav_item_span,
  is_empty_row,
  itogovy_table_span,
  patch_first_empty_tr,
)


EMPTY_TR = (
  '<tr><td style="vertical-align: top;"><br /></td>'
  '<td style="vertical-align: top;"><span> </span></td>'
  '<td><p class="with-breadcrumbs" style="text-align: left;"><br /></p></td>'
  '<td style="vertical-align: top;"><br /></td>'
  '<td style="vertical-align: top;"><br /></td>'
  '<td style="vertical-align: top;"><div class="content-wrapper"><br /></div></td></tr>'
)


def _material(pid: str, space: str = "TRAVELCENTER", title: str = "Тема") -> Material:
  return Material(
    page_id=pid,
    title=title,
    space_key=space,
    created_by_username="shubchik",
    created_by_userkey="key1",
    created_by_display="Шубчик",
  )


def test_first_nav_name_and_six_th(storage_vestnik_ok: str):
  _, _, name = first_nav_item_span(storage_vestnik_ok)
  assert name == "Август-Сентябрь 2026"
  nav_m = re.search(
    r'<ac:structured-macro\s+ac:name="horizontal-nav-item"[^>]*>(.*?)</ac:structured-macro>',
    storage_vestnik_ok,
    re.IGNORECASE | re.DOTALL,
  )
  _, _, table = itogovy_table_span(nav_m.group(1))
  assert table.count("<th") == 6


def test_empty_tr_is_canonical(storage_vestnik_ok: str):
  nav_m = re.search(
    r'<ac:structured-macro\s+ac:name="horizontal-nav-item"[^>]*>(.*?)</ac:structured-macro>',
    storage_vestnik_ok,
    re.IGNORECASE | re.DOTALL,
  )
  _, _, table = itogovy_table_span(nav_m.group(1))
  start, end = first_empty_tr_span(table)
  row = table[start:end]
  assert is_empty_row(row)
  assert _normalize_tr(row) == _normalize_tr(EMPTY_TR)


def _normalize_tr(s: str) -> str:
  return re.sub(r"\s+", "", s)


def test_compose_six_td_space_from_material():
  inner = compose_row_inner(
    month=None,
    block="DS",
    materials=[_material("517103930", "TRAVELCENTER", "Новый экран")],
    author_userkey="confirmed-key",
  )
  assert inner.count("<td") == 6
  assert 'ri:space-key="TRAVELCENTER"' in inner
  assert "DATASC" not in inner
  assert "<br />" in inner.split("</td>")[4]


def test_one_pageid_materials_duplicate_theme():
  m = _material("517103930", title="Одна тема")
  inner = compose_row_inner(month=None, block="", materials=[m], author_userkey="k")
  assert inner.count("ri:page") == 2


def test_three_pageids_three_links():
  mats = [_material("1", title="A"), _material("2", title="B"), _material("3", title="C")]
  inner = compose_row_inner(month="сентябрь", block="BI", materials=mats, author_userkey="k")
  assert inner.count("ri:page") == 4


def test_dedup_all_ids_noop(storage_vestnik_ok: str):
  nav_m = re.search(
    r'<ac:structured-macro\s+ac:name="horizontal-nav-item"[^>]*>(.*?)</ac:structured-macro>',
    storage_vestnik_ok,
    re.IGNORECASE | re.DOTALL,
  )
  _, _, table = itogovy_table_span(nav_m.group(1))
  mats = [_material("999", title="Существующая тема")]
  table_with_id = table.replace(
    'ri:content-title="Существующая тема"',
    'ri:content-title="Существующая тема" pageId=999',
  )
  assert dedup(table_with_id, mats, "Существующая тема") == "noop"


def test_dedup_theme_conflict(storage_vestnik_theme_conflict: str):
  nav_m = re.search(
    r'<ac:structured-macro\s+ac:name="horizontal-nav-item"[^>]*>(.*?)</ac:structured-macro>',
    storage_vestnik_theme_conflict,
    re.IGNORECASE | re.DOTALL,
  )
  _, _, table = itogovy_table_span(nav_m.group(1))
  mats = [_material("999", title="Существующая тема")]
  with pytest.raises(HitlStop, match="тема"):
    dedup(table, mats, "Существующая тема")


def test_no_empty_tr_raises(storage_vestnik_no_empty: str):
  nav_m = re.search(
    r'<ac:structured-macro\s+ac:name="horizontal-nav-item"[^>]*>(.*?)</ac:structured-macro>',
    storage_vestnik_no_empty,
    re.IGNORECASE | re.DOTALL,
  )
  _, _, table = itogovy_table_span(nav_m.group(1))
  with pytest.raises(VestnikError, match="empty tr"):
    first_empty_tr_span(table)


def test_patch_only_target_tr(storage_vestnik_ok: str):
  before = storage_vestnik_ok
  inner = compose_row_inner(
    month=None,
    block="MLE",
    materials=[_material("517103930", title="Новая тема")],
    author_userkey="key-x",
  )
  after = patch_first_empty_tr(before, inner)
  assert count_nav_items(after) == count_nav_items(before)
  assert "SECOND_TAB_MARKER" in after
  assert before.count("horizontal-nav-item") == after.count("horizontal-nav-item")
  diff_positions = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
  assert diff_positions
