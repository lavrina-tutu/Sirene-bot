#!/usr/bin/env python3
"""Map complexity labels to working-day duration (C1)."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def _normalize_label(s: str) -> str:
  return " ".join(str(s).strip().lower().split())


def map_complexity(label: str, cmap: dict[str, Any]) -> int:
  """Resolve label → days. Empty or unknown → ValueError (fail-loud)."""
  if label is None or not str(label).strip():
    raise ValueError("empty complexity label")
  norm = _normalize_label(str(label))
  for entry in cmap.get("entries") or []:
    for raw in entry.get("labels") or []:
      if _normalize_label(raw) == norm:
        days = entry.get("days")
        if days is None:
          raise ValueError(f"no days mapped for label {label!r}")
        return int(days)
  raise ValueError(f"unknown complexity label: {label!r}")


def load_complexity_map(path: Path) -> dict[str, Any]:
  if not path.is_file():
    raise FileNotFoundError(f"complexity map not found: {path}")
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError(f"invalid complexity map: {path}")
  return data


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Map complexity label to days")
  parser.add_argument("label", help="Complexity label from page")
  parser.add_argument(
    "--map",
    type=Path,
    default=Path(__file__).resolve().parents[1] / "references" / "complexity-map.yaml",
  )
  args = parser.parse_args(argv)
  cmap = load_complexity_map(args.map)
  days = map_complexity(args.label, cmap)
  print(days)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
