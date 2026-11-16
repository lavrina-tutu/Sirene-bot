"""Isolated plan API tests: deny network and SQLite outside pytest's root."""
from pathlib import Path
import socket
import sqlite3

import pytest


@pytest.fixture(autouse=True)
def isolated_plan_environment(tmp_path, tmp_path_factory, monkeypatch):
    root = tmp_path_factory.getbasetemp().resolve()
    protected = (Path.home() / "WorkVault", Path.home() / "USERTOOLS/MofsIndex/state", Path.home() / ".hermes")
    if any(root == path.resolve() or path.resolve() in root.parents or root in path.resolve().parents for path in protected):
        raise AssertionError("production test root forbidden")
    original_connect = sqlite3.connect
    def connect(path, *args, **kwargs):
        raw = str(path)
        if raw != ":memory:":
            candidate = Path(raw.removeprefix("file:").split("?")[0]).resolve()
            if root not in candidate.parents:
                raise AssertionError(f"SQLite outside isolated root: {candidate}")
        return original_connect(path, *args, **kwargs)
    def no_network(*args, **kwargs):
        raise AssertionError("network forbidden in MofsIndex plan tests")
    monkeypatch.setattr(sqlite3, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    wv = tmp_path / "WorkVault"
    cache = tmp_path / "cache"
    wv.mkdir()
    cache.mkdir()
    monkeypatch.setenv("WORKVAULT_PATH", str(wv))
    monkeypatch.setenv("TMPDIR", str(cache))
