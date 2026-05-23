"""Логирование: console + `logs/movefromff.jsonl` + `_log.md` (одна строка-итог).

v2.0: jsonl — одна строка JSON на событие; `_log.md` — append-only одна строка
на запуск (см. ТЗ §8).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

_INITIALISED = False
_JSONL_PATH: Optional[Path] = None


def _utc_iso_now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def setup_logging(jsonl_path: Path, verbose: bool = False) -> None:
    """Настроить loguru: stderr + JSONL-файл с ротацией."""
    global _INITIALISED, _JSONL_PATH
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "<level>{level: <7}</level> {message}"
        ),
        backtrace=False,
        diagnose=False,
    )
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        jsonl_path,
        level="DEBUG",
        serialize=True,
        rotation="10 MB",
        retention=5,
        encoding="utf-8",
    )
    _JSONL_PATH = jsonl_path
    _INITIALISED = True


def get_logger():
    return logger


def log_event(event: str, **fields: Any) -> None:
    """Записать структурированное событие в jsonl (одна строка JSON).

    Безопасно вызывать до `setup_logging` (в этом случае печатает в stderr).
    """
    row: Dict[str, Any] = {"ts": _utc_iso_now(), "event": event}
    row.update(fields)
    line = json.dumps(row, ensure_ascii=False)
    if _JSONL_PATH is not None:
        try:
            _JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_JSONL_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
    # Дополнительно в loguru — чтобы в консоли тоже видеть.
    try:
        logger.info(f"event={event} " + " ".join(f"{k}={v}" for k, v in fields.items()))
    except Exception:
        pass


def append_log_md(
    log_md_path: Path,
    mode: str,
    downloaded: int,
    skipped: int,
    errors: int,
    duration_sec: float,
) -> None:
    """Дописать строку-итог в `_log.md` (формат из ТЗ §8)."""
    ts = _utc_iso_now().replace("T", " ")
    line = (
        f"{ts} [{mode}] downloaded={downloaded} skipped={skipped} "
        f"errors={errors} duration={duration_sec:.1f}s\n"
    )
    log_md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_md_path, "a", encoding="utf-8") as f:
        f.write(line)
