"""Step A: ConfluenceSync pull via subprocess."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .fail import confluence_down
from .paths import CONFLUENCE_SYNC_CWD, VENV_PYTHON
from .project_config import ProjectConfig


@dataclass
class PullResult:
  page_id: str
  returncode: int
  stdout: str
  stderr: str


def _check_pull_output(result: PullResult) -> None:
  blob = f"{result.stdout}\n{result.stderr}"
  if result.returncode != 0:
    confluence_down(f"pull exit {result.returncode}: {result.stderr.strip()}")
  for token in ("401", "403", "Connection refused", "ConnectionError", "Name or service not known"):
    if token in blob:
      confluence_down(token)


def run_pull(
  page_id: str,
  *,
  depth: int | None = None,
  recursive: bool = True,
  resync: bool = False,
) -> PullResult:
  cmd = [str(VENV_PYTHON), "-m", "confluencesync", "pull", str(page_id), "--to-file"]
  if not recursive:
    cmd.append("--no-recursive")
  if depth is not None:
    cmd.extend(["--depth", str(depth)])
  if resync:
    cmd.append("--resync")
  proc = subprocess.run(
    cmd,
    cwd=CONFLUENCE_SYNC_CWD,
    capture_output=True,
    text=True,
  )
  result = PullResult(page_id=page_id, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
  _check_pull_output(result)
  return result


def pull_seed_tree(cfg: ProjectConfig) -> None:
  run_pull(cfg.root_page_id, depth=6, recursive=True, resync=True)
  for seed in cfg.pmo_seeds:
    run_pull(str(seed["page_id"]), recursive=False, resync=True)
