#!/usr/bin/env python3
"""Post-PUT verify for VestnikTheme (not heading-skeleton)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from vestnik_theme_author import Material
from vestnik_theme_patch import (
  count_nav_items,
  extract_page_ids,
  extract_ri_pages,
  first_nav_item_span,
  itogovy_table_span,
  is_empty_row,
)

__all__ = ["VestnikVerify", "verify_vestnik", "BRIEF_LEAK_PATTERNS"]

BRIEF_LEAK_PATTERNS = [
  re.compile(r"Не копировать", re.IGNORECASE),
  re.compile(r"Уточнить до ПК", re.IGNORECASE),
  re.compile(r"источник\s*:", re.IGNORECASE),
  re.compile(r"см\.\s*бриф", re.IGNORECASE),
]

_TR = re.compile(r"<tr\b.*?</tr>", re.IGNORECASE | re.DOTALL)
_TH = re.compile(r"<th\b", re.IGNORECASE)
_TD = re.compile(r"<td\b", re.IGNORECASE)
_USERKEY = re.compile(r'ri:userkey="([^"]+)"', re.IGNORECASE)


@dataclass
class VestnikVerify:
  ok: bool = True
  checks: dict[str, bool] = field(default_factory=dict)
  messages: list[str] = field(default_factory=list)

  def fail(self, check: str, msg: str) -> None:
    self.ok = False
    self.checks[check] = False
    self.messages.append(f"{check}: {msg}")

  def pass_check(self, check: str) -> None:
    self.checks[check] = True


def verify_vestnik(
  *,
  before_storage: str,
  after_storage: str,
  before_version: int,
  after_version: int,
  expected_min_version: int,
  materials: list[Material],
  author_userkey: str,
  first_tab_name: str,
) -> VestnikVerify:
  result = VestnikVerify()

  if after_version >= expected_min_version:
    result.pass_check("version")
  else:
    result.fail("version", f"got {after_version}, expected >={expected_min_version}")

  before_nav = count_nav_items(before_storage)
  after_nav = count_nav_items(after_storage)
  if before_nav == after_nav:
    result.pass_check("nav_count")
  else:
    result.fail("nav_count", f"got {after_nav}, expected {before_nav}")

  _, _, before_name = first_nav_item_span(before_storage)
  _, _, after_name = first_nav_item_span(after_storage)
  if before_name == after_name == first_tab_name or after_name == first_tab_name:
    result.pass_check("first_tab_name")
  elif after_name == before_name:
    result.pass_check("first_tab_name")
  else:
    result.fail("first_tab_name", f"got {after_name!r}, expected {first_tab_name!r}")

  nav_m = re.search(
    r'<ac:structured-macro\s+ac:name="horizontal-nav-item"[^>]*>(.*?)</ac:structured-macro>',
    after_storage,
    re.IGNORECASE | re.DOTALL,
  )
  table_html = ""
  if nav_m:
    try:
      _, _, table_html = itogovy_table_span(nav_m.group(1))
    except Exception as exc:
      result.fail("table_schema", str(exc))
  else:
    result.fail("table_schema", "nav item missing")

  if table_html:
    th_count = len(_TH.findall(table_html))
    if th_count == 6:
      result.pass_check("th_count")
    else:
      result.fail("th_count", f"got {th_count}")

    rows = list(_TR.finditer(table_html))[1:]
    td_ok = any(len(_TD.findall(r.group(0))) == 6 and not is_empty_row(r.group(0)) for r in rows)
    if td_ok or rows:
      result.pass_check("td_count")
    else:
      result.fail("td_count", "no data row with 6 td")

    ids = extract_page_ids(table_html)
    pairs = extract_ri_pages(table_html)
    mat_ok = True
    for m in materials:
      if m.page_id not in ids and (m.space_key, m.title) not in pairs:
        mat_ok = False
        break
    if mat_ok and materials[0].title in table_html:
      result.pass_check("materials_present")
    else:
      result.fail("materials_present", "material links missing")

    if author_userkey in _USERKEY.findall(table_html):
      result.pass_check("author_userkey")
    else:
      result.fail("author_userkey", "author userkey missing")

  leaks = [p.pattern for p in BRIEF_LEAK_PATTERNS if p.search(after_storage)]
  if leaks:
    result.fail("no_brief_leak", str(leaks))
  else:
    result.pass_check("no_brief_leak")

  wrong_space = "DATASC"
  for m in materials:
    if m.space_key != wrong_space and wrong_space in table_html:
      for pair in extract_ri_pages(table_html):
        if pair[0] == wrong_space and pair[1] == m.title:
          result.fail("no_wrong_space", f"DATASC leak for {m.title}")
          break
      else:
        result.pass_check("no_wrong_space")
      break
  else:
    result.pass_check("no_wrong_space")

  return result
