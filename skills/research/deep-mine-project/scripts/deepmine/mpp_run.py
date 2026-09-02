"""Step C (CSV): MppReader subprocess."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .fail import mpp_failed
from .paths import MPP_READER, VENV_PYTHON


@dataclass
class CsvTriple:
  tasks: Path | None
  resources: Path | None
  assignments: Path | None
  stem: str


def export_csv(mpp_path: Path, out_dir: Path) -> CsvTriple:
  out_dir.mkdir(parents=True, exist_ok=True)
  cmd = [
    str(VENV_PYTHON),
    str(MPP_READER),
    str(mpp_path),
    "--format",
    "both",
    "--out-dir",
    str(out_dir),
  ]
  proc = subprocess.run(cmd, capture_output=True, text=True)
  if proc.returncode != 0:
    mpp_failed(proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
  stem = mpp_path.stem
  tasks = out_dir / f"{stem}__tasks.csv"
  resources = out_dir / f"{stem}__resources.csv"
  assignments = out_dir / f"{stem}__assignments.csv"
  return CsvTriple(
    tasks=tasks if tasks.exists() else None,
    resources=resources if resources.exists() else None,
    assignments=assignments if assignments.exists() else None,
    stem=stem,
  )


def find_mpp_attachment(attachments_dir: Path, expected_name: str) -> Path | None:
  if not attachments_dir.is_dir():
    return None
  for path in attachments_dir.iterdir():
    if expected_name.lower() in path.name.lower():
      return path
  for ext in (".mpp", ".mpx", ".xml", ".zip"):
    matches = list(attachments_dir.glob(f"*{ext}"))
    if matches:
      return matches[0]
  return None


def register_local_mpp(
  manifest,
  mpp_path: Path,
  overlay: Path,
  *,
  page_id: str = "local",
) -> None:
  import hashlib
  from datetime import datetime, timezone

  data = mpp_path.read_bytes()
  now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  record = {
    "filename": mpp_path.name,
    "page_id": page_id,
    "download_url": f"file://{mpp_path}",
    "local_path": str(mpp_path.relative_to(overlay)),
    "sha256": hashlib.sha256(data).hexdigest(),
    "filesize": len(data),
    "format_hint": "ole2",
    "synced_at": now,
    "source": "local_attachment",
  }
  manifest.attachments = [r for r in manifest.attachments if r.get("filename") != mpp_path.name]
  manifest.attachments.append(record)


def register_mpp_in_manifest(manifest, csv: CsvTriple, overlay: Path) -> None:
  manifest.digests.setdefault("mpp-plan", {})
  manifest.digests["mpp-plan"].update(
    {
      "kind": "mpp",
      "csv_tasks": str(csv.tasks.relative_to(overlay)) if csv.tasks else None,
      "csv_resources": str(csv.resources.relative_to(overlay)) if csv.resources else None,
      "csv_assignments": str(csv.assignments.relative_to(overlay)) if csv.assignments else None,
      "plan_path": "mpp/plan.md",
      "status": "pending_compress",
    }
  )
