"""Configuration via pydantic Settings + python-dotenv (v2.0).

Все пути берутся из .env (WORKVAULT_PATH, PROJECT_PATH). В коде —
никакого хардкода путей. Это обеспечит безболезненный переезд на Ubuntu VM.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator


_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for c in candidates:
        if c.exists():
            load_dotenv(c, override=False)
            break
    _ENV_LOADED = True


class Settings(BaseModel):
    """Runtime configuration loaded from environment."""

    workvault_path: Path
    project_path: Path
    fireflies_api_key: str
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    @field_validator("workvault_path", "project_path")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return Path(os.path.expandvars(str(v))).expanduser()

    # Derived paths -----------------------------------------------------
    @property
    def meetings_root(self) -> Path:
        return self.workvault_path / "Meetings"

    @property
    def new_meetings_dir(self) -> Path:
        return self.meetings_root / "NewMeetings"

    @property
    def registry_json(self) -> Path:
        return self.new_meetings_dir / "_registry.json"

    @property
    def registry_md(self) -> Path:
        return self.new_meetings_dir / "_registry.md"

    @property
    def log_md(self) -> Path:
        return self.new_meetings_dir / "_log.md"

    @property
    def logs_dir(self) -> Path:
        return self.project_path / "logs"

    @property
    def jsonl_log(self) -> Path:
        return self.logs_dir / "movefromff.jsonl"

    @property
    def locks_dir(self) -> Path:
        return self.project_path / ".locks"

    @property
    def lock_file(self) -> Path:
        return self.locks_dir / "movefromff.lock"


def load_settings() -> Settings:
    """Load Settings from environment / .env file. Validates required vars."""
    _ensure_env_loaded()

    def _req(name: str) -> str:
        val = os.environ.get(name)
        if not val:
            raise RuntimeError(f"Required env var missing: {name}")
        return val

    return Settings(
        workvault_path=Path(_req("WORKVAULT_PATH")),
        project_path=Path(_req("PROJECT_PATH")),
        fireflies_api_key=_req("FIREFLIES_API_KEY"),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
    )
