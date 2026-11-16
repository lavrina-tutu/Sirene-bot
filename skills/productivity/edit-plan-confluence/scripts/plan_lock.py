"""Local interprocess locks. Kernel ownership survives neither exit nor crash.

The stable inode is never unlinked: deleting a lock file would permit two owners
on different inodes. PID text is diagnostic only, never evidence of ownership.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path


class PlanLockBusy(RuntimeError):
    code = "batch_busy"


@contextmanager
def batch_lock(db: Path, batch_id: str):
    """Nonblocking flock, scoped to the actual DB and batch, independent of cache."""
    database = Path(db).resolve()
    directory = database.parent / ("." + database.name + ".plan-locks")
    directory.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(batch_id.encode()).hexdigest() + ".lock"
    fd = os.open(directory / name, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PlanLockBusy("batch_busy") from exc
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
