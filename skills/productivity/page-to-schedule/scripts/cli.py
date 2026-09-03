#!/usr/bin/env python3
"""page-to-schedule pipeline CLI (C2): pull → pack → CSV → optional GS."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
DEFAULT_WORKVAULT = Path.home() / "WorkVault"
DEEP_MINE = (
  Path.home()
  / "hermes-workspace"
  / "skills"
  / "research"
  / "deep-mine-project"
  / "scripts"
  / "deep_mine.py"
)
VENV_PYTHON = Path.home() / "hermes-agent" / ".venv" / "bin" / "python3"
CONFLUENCE_SYNC = Path.home() / "USERTOOLS" / "ConfluenceSync"


def _python() -> str:
  return str(VENV_PYTHON if VENV_PYTHON.is_file() else Path(sys.executable))


def load_field_map(path: Path) -> dict:
  data = yaml.safe_load(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError("FIELD_MAP must be a YAML mapping")
  return data


def step_check_field_map(field_map: Path, complexity_map: Path) -> int:
  from check_field_map import check

  errors = check(field_map, complexity_map)
  if errors:
    for err in errors:
      print(err, file=sys.stderr)
    return 1
  return 0


def step_pull(page_id: str, *, skip: bool = False) -> int:
  if skip:
    print("skip: confluencesync pull")
    return 0
  cmd = [
    _python(),
    "-m",
    "confluencesync",
    "pull",
    str(page_id),
    "--no-recursive",
    "--resync",
  ]
  print("+", " ".join(cmd))
  proc = subprocess.run(cmd, cwd=str(CONFLUENCE_SYNC))
  return proc.returncode


def step_pack(slug: str, task: str, *, skip: bool = False) -> int:
  if skip:
    print("skip: deep_mine pack")
    return 0
  cmd = [_python(), str(DEEP_MINE), "pack", "--slug", slug, "--task", task]
  print("+", " ".join(cmd))
  proc = subprocess.run(cmd)
  return proc.returncode


def find_extract_csv(pack_dir: Path, page_id: str) -> Path:
  extracts = pack_dir / "extracts"
  if not extracts.is_dir():
    raise FileNotFoundError(f"extracts/ missing in {pack_dir}")
  candidates = sorted(extracts.glob("*.csv"))
  if not candidates:
    raise FileNotFoundError(f"No CSV in {extracts}")
  for path in candidates:
    if page_id in path.name:
      return path
  return candidates[0]


def step_build_csv(
  extract: Path,
  field_map: Path,
  output: Path,
  *,
  complexity_map: Path,
  wbs: Path | None = None,
) -> int:
  field_data = load_field_map(field_map)
  start = field_data.get("start_date", "")
  resource = field_data.get("resource_name", "")
  cmd = [
    _python(),
    str(SCRIPTS / "build_import_csv.py"),
    "--extract", str(extract),
    "--field-map", str(field_map),
    "--complexity-map", str(complexity_map),
    "--start-date", str(start),
    "--resource-name", str(resource),
    "--output", str(output),
  ]
  if wbs and wbs.is_file():
    cmd.extend(["--wbs", str(wbs)])
  print("+", " ".join(cmd))
  proc = subprocess.run(cmd)
  return proc.returncode


def step_push_gs(
  csv_path: Path,
  *,
  title: str | None,
  spreadsheet_id: str | None,
  share: list[str],
) -> int:
  cmd = [_python(), str(SCRIPTS / "push_import_gs.py"), str(csv_path)]
  if title:
    cmd.extend(["--title", title])
  if spreadsheet_id:
    cmd.extend(["--spreadsheet-id", spreadsheet_id])
  for email in share:
    cmd.extend(["--share", email])
  print("+", " ".join(cmd))
  proc = subprocess.run(cmd)
  return proc.returncode


def run_pipeline(
  slug: str,
  task: str,
  field_map: Path,
  *,
  workvault: Path = DEFAULT_WORKVAULT,
  complexity_map: Path | None = None,
  wbs: Path | None = None,
  output_csv: Path | None = None,
  gs_title: str | None = None,
  spreadsheet_id: str | None = None,
  share: list[str] | None = None,
  push_gs: bool = False,
  skip_pull: bool = False,
  skip_pack: bool = False,
) -> int:
  cmap = complexity_map or (SKILL_ROOT / "references" / "complexity-map.yaml")

  rc = step_check_field_map(field_map, cmap)
  if rc != 0:
    return rc

  data = load_field_map(field_map)
  page_id = str(data["source_page_id"])

  rc = step_pull(page_id, skip=skip_pull)
  if rc != 0:
    return rc

  rc = step_pack(slug, task, skip=skip_pack)
  if rc != 0:
    return rc

  pack_dir = workvault / "Projects" / slug / "docs" / "_inbox" / task
  try:
    extract = find_extract_csv(pack_dir, page_id)
  except FileNotFoundError as exc:
    print(exc, file=sys.stderr)
    return 1

  out = output_csv or (pack_dir / "import.csv")
  rc = step_build_csv(extract, field_map, out, complexity_map=cmap, wbs=wbs)
  if rc != 0:
    return rc

  if push_gs:
    rc = step_push_gs(
      out,
      title=gs_title,
      spreadsheet_id=spreadsheet_id,
      share=share or [],
    )
    if rc != 0:
      return rc

  print(f"import_csv:{out}")
  return 0


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="page-to-schedule full pipeline")
  sub = parser.add_subparsers(dest="command", required=True)

  run_p = sub.add_parser("run", help="pull → pack → import CSV → optional GS")
  run_p.add_argument("--slug", required=True, help="PROJECT.yaml slug (e.g. TrisigmaFull)")
  run_p.add_argument("--task", required=True, help="task_id (e.g. feature_compare)")
  run_p.add_argument("--field-map", type=Path, required=True, help="FIELD_MAP.yaml in pack")
  run_p.add_argument("--workvault", type=Path, default=DEFAULT_WORKVAULT)
  run_p.add_argument("--complexity-map", type=Path, default=None)
  run_p.add_argument("--wbs", type=Path, help="Optional WBS JSON from grok (names/preds only)")
  run_p.add_argument("--output", type=Path, help="import CSV path (default: pack/import.csv)")
  run_p.add_argument("--gs-title", help="GS title when creating")
  run_p.add_argument("--spreadsheet-id", help="Update existing spreadsheet")
  run_p.add_argument("--share", action="append", default=[], help="Share email (repeatable)")
  run_p.add_argument("--push-gs", action="store_true", help="Live GS upload (marked @live in tests)")
  run_p.add_argument("--skip-pull", action="store_true")
  run_p.add_argument("--skip-pack", action="store_true")

  args = parser.parse_args(argv)

  if args.command == "run":
    return run_pipeline(
      args.slug,
      args.task,
      args.field_map,
      workvault=args.workvault,
      complexity_map=args.complexity_map,
      wbs=args.wbs,
      output_csv=args.output,
      gs_title=args.gs_title,
      spreadsheet_id=args.spreadsheet_id,
      share=args.share,
      push_gs=args.push_gs,
      skip_pull=args.skip_pull,
      skip_pack=args.skip_pack,
    )

  return 1


if __name__ == "__main__":
  raise SystemExit(main())
