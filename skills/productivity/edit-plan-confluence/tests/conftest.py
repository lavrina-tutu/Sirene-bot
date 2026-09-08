"""Pytest fixtures for edit-plan-confluence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = Path(__file__).parent / "fixtures"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


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
