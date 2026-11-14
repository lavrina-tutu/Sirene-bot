"""Pytest fixtures for edit-plan-confluence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = Path(__file__).parent / "fixtures"
MOFS_INDEX_ROOT = Path.home() / "USERTOOLS" / "MofsIndex"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(MOFS_INDEX_ROOT) not in sys.path:
    sys.path.insert(0, str(MOFS_INDEX_ROOT))


@pytest.fixture
def skill_root() -> Path:
    return SKILL_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def tasks_csv(fixtures_dir: Path) -> Path:
    return fixtures_dir / "ab_080926_пункт12__tasks.csv"


@pytest.fixture
def resources_csv(fixtures_dir: Path) -> Path:
    return fixtures_dir / "ab_080926_пункт12__resources.csv"


@pytest.fixture
def assignments_csv(fixtures_dir: Path) -> Path:
    return fixtures_dir / "ab_080926_пункт12__assignments.csv"


@pytest.fixture
def mpp_fixture(fixtures_dir: Path) -> Path:
    return fixtures_dir / "ab_080926_пункт12.mpp"


@pytest.fixture
def empty_template(skill_root: Path) -> dict:
    return json.loads((skill_root / "references" / "empty-gantt-template.json").read_text(encoding="utf-8"))


@pytest.fixture
def gantt_test_template(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "gantt-test-template.json").read_text(encoding="utf-8"))


@pytest.fixture
def isolated_plan_db(tmp_path, monkeypatch):
    """Изолированная plan_*-БД + WorkVault-каталог для тестов, задействующих
    ``plan_archive``/``pipeline`` preflight archive (R-039: изолированные
    fixtures, не боевая БД/боевой Confluence)."""
    from mofs_index.db import connect as mofs_connect, initialize
    from mofs_index.plan.migrate import ensure_plan_schema

    db_path = tmp_path / "plan_index.sqlite"

    def fake_connect_durable(path=None):
        c = mofs_connect(db_path, durable=True)
        initialize(c)
        ensure_plan_schema(c)
        return c

    monkeypatch.setattr("mofs_index.db.connect_durable", fake_connect_durable)
    monkeypatch.setattr("plan_archive.connect_durable", fake_connect_durable)

    wv = tmp_path / "WorkVault"
    monkeypatch.setattr("plan_archive.get_workvault_path", lambda: wv)
    monkeypatch.setattr("plan_receipt.get_workvault_path", lambda: wv)
    return db_path
