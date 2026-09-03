"""Pytest fixtures for page-to-schedule scripts."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
REFS = SKILL_ROOT / "references"

if str(SCRIPTS) not in sys.path:
  sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def skill_root() -> Path:
  return SKILL_ROOT


@pytest.fixture
def refs_dir() -> Path:
  return REFS


@pytest.fixture
def complexity_map_path(refs_dir: Path) -> Path:
  return refs_dir / "complexity-map.yaml"


@pytest.fixture
def holidays_path(refs_dir: Path) -> Path:
  return refs_dir / "rf-holidays.yaml"
