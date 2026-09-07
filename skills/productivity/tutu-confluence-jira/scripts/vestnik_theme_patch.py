#!/usr/bin/env python3
"""Tab-aware row patch for VestnikTheme storage."""
from __future__ import annotations

import re
from typing import Literal

from vestnik_theme_author import Material
from vestnik_theme_errors import HitlStop, VestnikError

__all__ = [
  "count_nav_items",
  "first_nav_item_span",
  "itogovy_table_span",
  "iter_data_rows",
  "is_empty_row",
  "first_empty_tr_span",
  "extract_ri_pages",
  "extract_page_ids",
  "theme_texts",
  "dedup",
  "escape_attr",
  "ri_page_link",
  "compose_row_inner",
  "patch_first_empty_tr",
]

_NAV_GROUP = re.compile(r'<ac:structured-macro\s+ac:name="horizontal-nav-group"', re.IGNORECASE)
_NAV_ITEM = re.compile(
  r'<ac:structured-macro\s+ac:name="horizontal-nav-item"[^>]*>(.*?)</ac:structured-macro>',
  re.IGNORECASE | re.DOTALL,
)
_NAME_PARAM = re.compile(
  r'<ac:parameter\s+ac:name="name"[^>]*>(.*?)</ac:parameter>',
  re.IGNORECASE | re.DOTALL,
)
_ITOGOVY = re.compile(r"<p[^>]*>.*?Итоговый\s+материал.*?</p>", re.IGNORECASE | re.DOTALL)
_TABLE = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)
_TR = re.compile(r"<tr\b.*?</tr>", re.IGNORECASE | re.DOTALL)
_TH = re.compile(r"<th\b", re.IGNORECASE)
_TD = re.compile(r"<td\b", re.IGNORECASE)
_RI_PAGE = re.compile(
  r'<ri:page\s+[^>]*ri:space-key="([^"]*)"[^>]*ri:content-title="([^"]*)"',
  re.IGNORECASE,
)
_PAGE_ID = re.compile(r'pageId=(\d+)|/pages/(\d+)', re.IGNORECASE)
_TAG_STRIP = re.compile(r"<[^>]+>")


def count_nav_items(storage: str) -> int:
  return len(_NAV_ITEM.findall(storage or ""))


def first_nav_item_span(storage: str) -> tuple[int, int, str]:
  if not _NAV_GROUP.search(storage or ""):
    raise VestnikError(stage="tab", message="horizontal-nav-group not found")
  m = _NAV_ITEM.search(storage)
  if not m:
    raise VestnikError(stage="tab", message="horizontal-nav-item not found")
  inner = m.group(1)
  name_m = _NAME_PARAM.search(inner)
  name = _TAG_STRIP.sub("", name_m.group(1)).strip() if name_m else ""
  return m.start(), m.end(), name


def itogovy_table_span(nav_inner: str) -> tuple[int, int, str]:
  itog = _ITOGOVY.search(nav_inner)
  if not itog:
    raise VestnikError(stage="tab", message="Итоговый материал paragraph not found")
  rest = nav_inner[itog.end():]
  tbl = _TABLE.search(rest)
  if not tbl:
    raise VestnikError(stage="tab", message="table after Итоговый материал not found")
  table_html = tbl.group(0)
  th_count = len(_TH.findall(table_html))
  if th_count != 6:
    raise VestnikError(stage="tab", message=f"expected 6 th, got {th_count}")
  abs_start = itog.end() + tbl.start()
  abs_end = itog.end() + tbl.end()
  return abs_start, abs_end, table_html


def iter_data_rows(table_html: str):
  rows = list(_TR.finditer(table_html))
  if not rows:
    return
  for row in rows[1:]:
    yield row.group(0)


def _td_inners(tr_html: str) -> list[str]:
  return re.findall(r"<td\b[^>]*>(.*?)</td>", tr_html, re.IGNORECASE | re.DOTALL)


def _cell_texts(tr_html: str) -> list[str]:
  texts: list[str] = []
  for inner in _td_inners(tr_html):
    text = _TAG_STRIP.sub("", inner)
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE).strip()
    texts.append(text)
  return texts


def is_empty_row(tr_html: str) -> bool:
  inners = _td_inners(tr_html)
  if len(inners) != 6:
    return False
  for inner in inners:
    text = _TAG_STRIP.sub("", inner)
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE).strip()
    if text:
      return False
  return True


def first_empty_tr_span(table_html: str) -> tuple[int, int]:
  for row in iter_data_rows(table_html):
    if is_empty_row(row):
      start = table_html.index(row)
      return start, start + len(row)
  raise VestnikError(stage="patch", message="no empty tr in table")


def extract_ri_pages(table_html: str) -> list[tuple[str, str]]:
  return [(m.group(1), m.group(2)) for m in _RI_PAGE.finditer(table_html)]


def extract_page_ids(table_html: str) -> set[str]:
  ids: set[str] = set()
  for m in _PAGE_ID.finditer(table_html):
    ids.add(m.group(1) or m.group(2))
  return ids


def theme_texts(table_html: str) -> list[str]:
  rows = list(_TR.finditer(table_html))
  texts: list[str] = []
  for row in rows[1:]:
    tr = row.group(0)
    cells = _cell_texts(tr)
    if len(cells) >= 3 and cells[2].strip():
      texts.append(cells[2].strip())
  return texts


def _norm_theme(s: str) -> str:
  return re.sub(r"\s+", " ", s).strip().casefold()


def dedup(
  table_html: str,
  materials: list[Material],
  theme_title: str,
) -> Literal["noop", "ok"]:
  input_ids = {m.page_id for m in materials}
  existing_ids = extract_page_ids(table_html)
  if input_ids and input_ids <= existing_ids:
    return "noop"

  input_pairs = {(m.space_key, m.title) for m in materials}
  existing_pairs = set(extract_ri_pages(table_html))
  if input_pairs and input_pairs <= existing_pairs:
    return "noop"

  theme_norm = _norm_theme(theme_title)
  for existing in theme_texts(table_html):
    if _norm_theme(existing) == theme_norm:
      if not (input_ids <= existing_ids or input_pairs <= existing_pairs):
        raise HitlStop(
          kind="theme_conflict",
          message=f"тема «{theme_title}» уже есть с другими pageId",
        )
  return "ok"


def escape_attr(s: str) -> str:
  return (
    s.replace("&", "&amp;")
    .replace('"', "&quot;")
    .replace("<", "&lt;")
  )


def ri_page_link(space_key: str, title: str) -> str:
  return (
    f'<ac:link><ri:page ri:space-key="{escape_attr(space_key)}" '
    f'ri:content-title="{escape_attr(title)}"/></ac:link>'
  )


def compose_row_inner(
  *,
  month: str | None,
  block: str,
  materials: list[Material],
  author_userkey: str,
) -> str:
  td1 = month if month else "<br />"
  td2 = block.replace("&", "&amp;").replace("<", "&lt;") if block else "<span> </span>"

  theme_link = ri_page_link(materials[0].space_key, materials[0].title)
  td3 = f'<p class="with-breadcrumbs" style="text-align: left;"> {theme_link} </p>'

  mat_links = [ri_page_link(m.space_key, m.title) for m in materials]
  if len(mat_links) == 1:
    td4 = f" {mat_links[0]} "
  else:
    td4 = " ".join(mat_links)

  td5 = "<br />"
  td6 = (
    f'<div class="content-wrapper"><ac:link>'
    f'<ri:user ri:userkey="{escape_attr(author_userkey)}"/></ac:link></div>'
  )

  return (
    f'<td style="vertical-align: top;">{td1}</td>'
    f'<td style="vertical-align: top;">{td2}</td>'
    f"<td>{td3}</td>"
    f'<td style="vertical-align: top;">{td4}</td>'
    f'<td style="vertical-align: top;">{td5}</td>'
    f'<td style="vertical-align: top;">{td6}</td>'
  )


def patch_first_empty_tr(storage: str, new_tr_inner: str) -> str:
  _, _, nav_inner_start = first_nav_item_span(storage)
  nav_m = _NAV_ITEM.search(storage)
  if not nav_m:
    raise VestnikError(stage="patch", message="nav item not found")
  nav_inner = nav_m.group(1)
  _, _, table_html = itogovy_table_span(nav_inner)
  tr_start, tr_end = first_empty_tr_span(table_html)
  old_tr = table_html[tr_start:tr_end]
  new_tr = f"<tr>{new_tr_inner}</tr>"
  new_table = table_html[:tr_start] + new_tr + table_html[tr_end:]
  new_nav_inner = nav_inner.replace(table_html, new_table, 1)
  return storage[:nav_m.start(1)] + new_nav_inner + storage[nav_m.end(1):]
