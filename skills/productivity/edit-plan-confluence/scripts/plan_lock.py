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


class TargetLockBusy(PlanLockBusy):
    code = 'target_busy'
    exit_code = 4


@contextmanager
def target_lock(workvault: Path, namespace: str, page_id: str, macro_id: str | None = None):
    """Host-wide ownership across DB/cache overrides in the same WorkVault.

    A page guard covers new/replaced macros too; the second lock identifies the
    exact namespace/page/macro. Kernel flock, not a stale PID, decides liveness.
    """
    directory = Path(workvault).resolve() / '_plan-receipts' / '.target-locks'
    directory.mkdir(parents=True, exist_ok=True)
    fds = []
    try:
        for key in ((namespace, str(page_id)), (namespace, str(page_id), macro_id or 'new')):
            name = hashlib.sha256(repr(key).encode()).hexdigest() + '.lock'
            fd = os.open(directory / name, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            fds.append(fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                owner = os.pread(fd, 256, 0).decode(errors='replace')
                raise TargetLockBusy('target_busy; live kernel owner: ' + owner) from exc
            os.ftruncate(fd, 0)
            os.write(fd, (str(os.getpid()) + ' ' + repr(key)).encode())
        yield
    finally:
        for fd in reversed(fds):
            os.close(fd)


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
