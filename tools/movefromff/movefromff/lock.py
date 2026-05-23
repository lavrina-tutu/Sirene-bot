"""File lock via portalocker — single instance guard."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import portalocker


class LockBusy(RuntimeError):
    """Raised if the lock cannot be acquired (another instance is running)."""


@contextmanager
def acquire_lock(lock_path: Path) -> Iterator[None]:
    """Exclusive non-blocking lock at *lock_path*. Raises LockBusy on contention."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Use 'a+' so the file is created if missing but we don't truncate existing.
    fh = open(lock_path, "a+")
    try:
        try:
            portalocker.lock(fh, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except (portalocker.exceptions.LockException, BlockingIOError) as exc:
            fh.close()
            raise LockBusy(f"Lock busy: {lock_path}") from exc
        try:
            yield
        finally:
            try:
                portalocker.unlock(fh)
            except Exception:
                pass
    finally:
        try:
            fh.close()
        except Exception:
            pass
