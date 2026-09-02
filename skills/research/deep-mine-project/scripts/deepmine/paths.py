"""WorkVault overlay paths and constants."""
from __future__ import annotations

from pathlib import Path

DEFAULT_WORKVAULT = Path.home() / "WorkVault"
VENV_PYTHON = Path.home() / "hermes-agent" / ".venv" / "bin" / "python3"
CONFLUENCE_SYNC_CWD = Path.home() / "USERTOOLS" / "ConfluenceSync"
MOFS_INDEX_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"
MPP_READER = Path.home() / "USERTOOLS" / "MppReader" / "read_mpp.py"
COMPRESSOR_PROMPT = DEFAULT_WORKVAULT / "Registries" / "project-context-compressor-prompt.md"

OVERLAY_SUBDIRS = (
    "attachments",
    "mpp",
    "pointers",
    "digest/leaves",
    "digest/themes",
    "digest/_history",
    "docs/_inbox",
)


def workvault_root(path: str | Path | None) -> Path:
    return Path(path).expanduser() if path else DEFAULT_WORKVAULT


def overlay_dir(workvault: Path, slug: str) -> Path:
    return workvault / "Projects" / slug


def ensure_overlay_dirs(overlay: Path) -> None:
    for sub in OVERLAY_SUBDIRS:
        (overlay / sub).mkdir(parents=True, exist_ok=True)


def l0_abs(workvault: Path, local_path: str) -> Path:
    return workvault / local_path
