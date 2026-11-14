"""Load Confluence credentials from ConfluenceSync .env (CONFLUENCE_TOKEN only)."""
from __future__ import annotations

import os
from pathlib import Path

ENV_PATH = Path.home() / "USERTOOLS" / "ConfluenceSync" / ".env"
CONFLUENCE_BASE = "https://dom.tutu.ru"


def load_confluence_env(env_path: Path | None = None) -> dict[str, str]:
    """Read CONFLUENCE_TOKEN (and optional WORKVAULT_PATH) without sourcing whole .env."""
    path = env_path or ENV_PATH
    out: dict[str, str] = {}
    if not path.is_file():
        raise FileNotFoundError(f"Confluence .env not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in ("CONFLUENCE_TOKEN", "WORKVAULT_PATH") and value:
            out[key] = value
    if not out.get("CONFLUENCE_TOKEN"):
        raise RuntimeError("CONFLUENCE_TOKEN missing in ConfluenceSync .env")
    return out


def get_token() -> str:
    return load_confluence_env()["CONFLUENCE_TOKEN"]


def page_url(page_id: str | int) -> str:
    return f"{CONFLUENCE_BASE}/pages/viewpage.action?pageId={page_id}"


def get_workvault_path() -> Path:
    """Разрешённый корень архива (R-005..R-007): ``WORKVAULT_PATH`` из
    ConfluenceSync ``.env``, иначе дефолт ``~/WorkVault`` (P1.W1.2)."""
    try:
        env = load_confluence_env()
    except (FileNotFoundError, RuntimeError):
        env = {}
    raw = env.get("WORKVAULT_PATH") or os.environ.get("WORKVAULT_PATH")
    return Path(raw).expanduser() if raw else Path.home() / "WorkVault"
