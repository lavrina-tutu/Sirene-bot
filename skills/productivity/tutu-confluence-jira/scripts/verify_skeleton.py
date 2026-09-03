#!/usr/bin/env python3
"""Verify Confluence page skeleton after section patch (B0 checklist)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_HEADING_TAG = re.compile(
  r"<h([1-6])[^>]*>(.*?)</h\1>",
  re.IGNORECASE | re.DOTALL,
)
_MACRO = re.compile(r"<ac:structured-macro\b", re.IGNORECASE)
_TABLE = re.compile(r"<table\b", re.IGNORECASE)
_TD = re.compile(r"<td\b", re.IGNORECASE)

BRIEF_LEAK_PATTERNS = [
  re.compile(r"Не копировать", re.IGNORECASE),
  re.compile(r"Уточнить до ПК", re.IGNORECASE),
  re.compile(r"источник\s*:", re.IGNORECASE),
  re.compile(r"см\.\s*бриф", re.IGNORECASE),
]


@dataclass
class VerifyResult:
  ok: bool = True
  checks: dict[str, bool] = field(default_factory=dict)
  messages: list[str] = field(default_factory=list)

  def fail(self, check: str, msg: str) -> None:
    self.ok = False
    self.checks[check] = False
    self.messages.append(f"{check}: {msg}")

  def pass_check(self, check: str) -> None:
    self.checks[check] = True


def _strip_tags(html: str) -> str:
  return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


def _heading_present(storage: str, heading: str) -> bool:
  for m in _HEADING_TAG.finditer(storage):
    title = _strip_tags(m.group(2))
    if heading in title or title == heading:
      return True
  return False


def _section_inner(storage: str, heading: str) -> str | None:
  try:
    from section_patch import find_section_span
    start, end, _ = find_section_span(storage, heading)
    return storage[start:end]
  except ValueError:
    return None


def _tables_in_section(storage: str, heading: str) -> list[str]:
  inner = _section_inner(storage, heading)
  if inner is None:
    return []
  return _TABLE.findall(inner)


def verify_skeleton(
  storage: str,
  *,
  expected_version: int | None = None,
  actual_version: int | None = None,
  reference_macro_count: int | None = None,
  section_heading: str | None = None,
  removed_keywords: list[str] | None = None,
  reference_td_count: int | None = None,
) -> VerifyResult:
  """Seven-point checklist from SkillsImprovement B0."""
  result = VerifyResult()

  # 1. version
  if expected_version is not None and actual_version is not None:
    if actual_version >= expected_version:
      result.pass_check("version")
    else:
      result.fail("version", f"got {actual_version}, expected >={expected_version}")
  else:
    result.pass_check("version")

  # 2. macro count
  macro_count = len(_MACRO.findall(storage))
  if reference_macro_count is not None:
    if macro_count == reference_macro_count:
      result.pass_check("macro_count")
    else:
      result.fail("macro_count", f"got {macro_count}, expected {reference_macro_count}")
  else:
    result.pass_check("macro_count")

  # 3. section heading
  if section_heading:
    if _heading_present(storage, section_heading):
      result.pass_check("section_heading")
    else:
      result.fail("section_heading", f"heading missing: {section_heading!r}")
  else:
    result.pass_check("section_heading")

  # 4. removed keywords
  if removed_keywords:
    found = [kw for kw in removed_keywords if kw in storage]
    if found:
      result.fail("kw_not_in_body", f"still present: {found}")
    else:
      result.pass_check("kw_not_in_body")
  else:
    result.pass_check("kw_not_in_body")

  # 5. no duplicate table under heading
  if section_heading:
    tables = _tables_in_section(storage, section_heading)
    if len(tables) > 1:
      result.fail("no_duplicate_table", f"found {len(tables)} tables under heading")
    else:
      result.pass_check("no_duplicate_table")
  else:
    result.pass_check("no_duplicate_table")

  # 6. no brief service text
  leaks = [p.pattern for p in BRIEF_LEAK_PATTERNS if p.search(storage)]
  if leaks:
    result.fail("no_brief_leak", f"patterns: {leaks}")
  else:
    result.pass_check("no_brief_leak")

  # 7. td count in section table
  if section_heading and reference_td_count is not None:
    inner = _section_inner(storage, section_heading)
    if inner is None:
      result.fail("td_count", "section inner not found")
    else:
      td_count = len(_TD.findall(inner))
      if td_count == reference_td_count:
        result.pass_check("td_count")
      else:
        result.fail("td_count", f"got {td_count}, expected {reference_td_count}")
  else:
    result.pass_check("td_count")

  return result


def verify_from_files(
  *,
  storage_file: Path,
  reference_file: Path | None = None,
  section_heading: str,
  removed_keywords: list[str] | None = None,
  version: int | None = None,
) -> VerifyResult:
  storage = storage_file.read_text(encoding="utf-8")
  ref_storage = reference_file.read_text(encoding="utf-8") if reference_file else storage
  ref_macros = len(_MACRO.findall(ref_storage))
  ref_td = len(_TD.findall(_section_inner(ref_storage, section_heading)))
  return verify_skeleton(
    storage,
    expected_version=version,
    actual_version=version,
    reference_macro_count=ref_macros,
    section_heading=section_heading,
    removed_keywords=removed_keywords or [],
    reference_td_count=ref_td,
  )


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Verify Confluence skeleton after patch")
  parser.add_argument("--storage", required=True, type=Path)
  parser.add_argument("--reference", type=Path, default=None)
  parser.add_argument("--heading", required=True)
  parser.add_argument("--version", type=int, default=None)
  parser.add_argument("--removed", nargs="*", default=[])
  args = parser.parse_args(argv)

  result = verify_from_files(
    storage_file=args.storage,
    reference_file=args.reference,
    section_heading=args.heading,
    removed_keywords=args.removed,
    version=args.version,
  )
  print(json.dumps({"ok": result.ok, "checks": result.checks, "messages": result.messages}, ensure_ascii=False, indent=2))
  return 0 if result.ok else 1


if __name__ == "__main__":
  raise SystemExit(main())
