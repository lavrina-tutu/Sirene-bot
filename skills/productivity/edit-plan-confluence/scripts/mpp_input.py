"""Resolve .mpp / .zip input and invoke read_mpp.py for CSV export."""
from __future__ import annotations

import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

VENV_PYTHON = Path.home() / "hermes-agent" / ".venv" / "bin" / "python3"
SYSTEM_PYTHON = Path("/usr/bin/python3")
# Системный python с mpxj/jpype (RHEL9: python3.9; в python3.11/venv mpxj нет)
SYSTEM_MPXJ_PYTHON = Path("/usr/bin/python3.9")
READ_MPP = Path.home() / "USERTOOLS" / "MppReader" / "read_mpp.py"


def _pick_python() -> str:
    """venv может не иметь mpxj (питфолл read-mpp) — выбрать интерпретатор с mpxj."""
    import shutil
    import subprocess
    import sys

    cands: list[Path] = []
    if VENV_PYTHON.is_file():
        cands.append(VENV_PYTHON)
    if SYSTEM_PYTHON.is_file():
        cands.append(SYSTEM_PYTHON)
    if SYSTEM_MPXJ_PYTHON.is_file():
        cands.append(SYSTEM_MPXJ_PYTHON)
    sp = shutil.which("python3")
    if sp:
        cands.append(Path(sp))
    if not cands:
        cands.append(Path(sys.executable))
    for py in cands:
        try:
            r = subprocess.run(
                [str(py), "-c", "import mpxj, jpype"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode == 0:
                return str(py)
        except Exception:
            continue
    return str(cands[0])


@dataclass
class MppCsvPaths:
    mpp_path: Path
    tasks_csv: Path
    resources_csv: Path
    assignments_csv: Path
    out_dir: Path


def resolve_mpp_path(path: str | Path) -> Path:
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"MPP input not found: {p}")
    if p.suffix.lower() == ".zip":
        return _extract_mpp_from_zip(p)
    if p.suffix.lower() == ".mpp":
        return p
    raise ValueError(f"Expected .mpp or .zip, got: {p}")


def _extract_mpp_from_zip(zip_path: Path) -> Path:
    out_dir = zip_path.parent / f"{zip_path.stem}_unzipped"
    out_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        mpp_names = [n for n in zf.namelist() if n.lower().endswith(".mpp")]
        if not mpp_names:
            raise ValueError(f"No .mpp inside zip: {zip_path}")
        target = out_dir / Path(mpp_names[0]).name
        with zf.open(mpp_names[0]) as src, open(target, "wb") as dst:
            dst.write(src.read())
    return target


def export_csv(mpp_path: Path, out_dir: Path | None = None) -> MppCsvPaths:
    mpp_path = mpp_path.resolve()
    out = out_dir or mpp_path.parent
    out.mkdir(parents=True, exist_ok=True)
    python = _pick_python()
    cmd = [
        python,
        str(READ_MPP),
        str(mpp_path),
        "--format",
        "csv",
        "--out-dir",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"read_mpp.py failed: {proc.stderr or proc.stdout}")
    stem = mpp_path.stem
    tasks = out / f"{stem}__tasks.csv"
    resources = out / f"{stem}__resources.csv"
    assignments = out / f"{stem}__assignments.csv"
    for f in (tasks, resources, assignments):
        if not f.is_file():
            raise FileNotFoundError(f"Expected CSV missing: {f}")
    return MppCsvPaths(
        mpp_path=mpp_path,
        tasks_csv=tasks,
        resources_csv=resources,
        assignments_csv=assignments,
        out_dir=out,
    )
