"""Isolated binary copies for stage-02 reader/CSV tests; no network or DB."""
from __future__ import annotations

import hashlib
import json
import shutil
import socket
from pathlib import Path

import pytest

SKILL = Path.home() / "hermes-workspace/skills/productivity/edit-plan-confluence"


@pytest.fixture(scope="module", autouse=True)
def copied_legacy_mpp(request, tmp_path_factory):
    if not hasattr(request.module, "FIXTURE_MPP"):
        yield
        return
    original = request.module.FIXTURE_MPP
    target = tmp_path_factory.mktemp("legacy-mpp") / original.name
    shutil.copy2(original, target)
    # CSV fixtures are read-only expectations, copied beside the binary.
    for source in original.parent.glob(original.stem + "__*.csv"):
        shutil.copy2(source, target.parent / source.name)
    # Regression consumer expects references at parent.parent/references.
    references = target.parent.parents[1] / "references"
    references.mkdir(exist_ok=True)
    shutil.copy2(SKILL / "references/empty-gantt-template.json", references / "empty-gantt-template.json")
    request.module.FIXTURE_MPP = target
    yield
    request.module.FIXTURE_MPP = original


@pytest.fixture(scope="session")
def synthetic_dir(tmp_path_factory):
    source = SKILL / "tests/fixtures/synthetic"
    target = tmp_path_factory.mktemp("binary") / "synthetic"
    shutil.copytree(source, target)
    manifest = json.loads((target / "manifest.json").read_text())
    for row in manifest["fixtures"]:
        if "path" in row:
            data = (target / row["path"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == row["sha256"]
    return target


@pytest.fixture(scope="session")
def real_cases(tmp_path_factory):
    source = SKILL / "tests/fixtures/real"
    manifest = json.loads((source / "manifest.json").read_text())
    target = tmp_path_factory.mktemp("trisigma")
    rows = []
    for row in manifest["fixtures"]:
        path = source / row["path"]
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == row["sha256"]
        assert len(data) == row["size_bytes"]
        copy = target / row["path"]
        copy.write_bytes(data)
        rows.append({**row, "copy": copy})
    return rows


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("network forbidden in reader tests")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
