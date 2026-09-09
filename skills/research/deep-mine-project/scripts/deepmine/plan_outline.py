"""Mechanical plan.md outline from CSV (no composer)."""
from __future__ import annotations

import csv
from pathlib import Path


def write_plan_md_from_csv(mpp_dir: Path, *, project_title: str = "Project plan") -> Path | None:
  csv_files = sorted(mpp_dir.glob("*__tasks.csv"))
  if not csv_files:
    return None
  plan_path = mpp_dir / "plan.md"
  lines = [
    f"# {project_title}",
    "",
    "## Tasks (from CSV)",
    "",
    "| WBS | Name | Start | Finish | Effort |",
    "|---|---|---|---|---|",
  ]
  for csv_path in csv_files[:1]:
    with csv_path.open(encoding="utf-8") as fh:
      reader = csv.DictReader(fh)
      for row in reader:
        lines.append(
          f"| {row.get('wbs', '')} | {row.get('name', '')} | "
          f"{row.get('start', '')} | {row.get('finish', '')} | {row.get('effort', '')} |"
        )
  plan_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
  return plan_path
