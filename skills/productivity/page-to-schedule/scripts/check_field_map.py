#!/usr/bin/env python3
"""Fail-loud check: FIELD_MAP + complexity-map before grok (C0/C1)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REQUIRED_FIELD_MAP_KEYS = ("source_page_id", "columns", "resource_name", "start_date")
REQUIRED_COLUMNS = ("feature", "gap", "complexity")


def validate_field_map(path: Path) -> list[str]:
  errors: list[str] = []
  if not path.is_file():
    return [f"FIELD_MAP not found: {path}"]
  try:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
  except yaml.YAMLError as exc:
    return [f"FIELD_MAP parse error: {exc}"]
  if not isinstance(data, dict):
    return ["FIELD_MAP must be a YAML mapping"]
  for key in REQUIRED_FIELD_MAP_KEYS:
    if not data.get(key):
      errors.append(f"FIELD_MAP missing or empty: {key}")
  columns = data.get("columns") or {}
  if not isinstance(columns, dict):
    errors.append("FIELD_MAP columns must be a mapping")
  else:
    for col in REQUIRED_COLUMNS:
      if not columns.get(col):
        errors.append(f"FIELD_MAP columns missing: {col}")
  return errors


def validate_complexity_map(path: Path) -> list[str]:
  errors: list[str] = []
  if not path.is_file():
    return [f"complexity-map not found: {path}"]
  try:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
  except yaml.YAMLError as exc:
    return [f"complexity-map parse error: {exc}"]
  if not isinstance(data, dict):
    return ["complexity-map must be a YAML mapping"]
  entries = data.get("entries")
  if not entries:
    errors.append("complexity-map has no entries")
  return errors


def check(field_map: Path, complexity_map: Path) -> list[str]:
  return validate_field_map(field_map) + validate_complexity_map(complexity_map)


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(
    description="Verify FIELD_MAP and complexity-map exist (stop before grok)",
  )
  parser.add_argument("--field-map", type=Path, required=True)
  parser.add_argument(
    "--complexity-map",
    type=Path,
    default=Path(__file__).resolve().parents[1] / "references" / "complexity-map.yaml",
  )
  args = parser.parse_args(argv)
  errors = check(args.field_map, args.complexity_map)
  if errors:
    for err in errors:
      print(err, file=sys.stderr)
    return 1
  print("ok")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
