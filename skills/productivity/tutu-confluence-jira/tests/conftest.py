"""Pytest fixtures for tutu-confluence-jira scripts."""
from __future__ import annotations

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
def storage_ok(fixtures_dir: Path) -> str:
  return (fixtures_dir / "storage_deliveries_ok.xml").read_text(encoding="utf-8")


@pytest.fixture
def storage_heading_gone(fixtures_dir: Path) -> str:
  return (fixtures_dir / "storage_deliveries_heading_gone.xml").read_text(encoding="utf-8")


@pytest.fixture
def storage_vestnik_ok(fixtures_dir: Path) -> str:
  return (fixtures_dir / "storage_vestnik_ok.xml").read_text(encoding="utf-8")


@pytest.fixture
def storage_vestnik_no_empty(fixtures_dir: Path) -> str:
  return (fixtures_dir / "storage_vestnik_no_empty.xml").read_text(encoding="utf-8")


@pytest.fixture
def storage_vestnik_wrong_cols(fixtures_dir: Path) -> str:
  return (fixtures_dir / "storage_vestnik_wrong_cols.xml").read_text(encoding="utf-8")


@pytest.fixture
def storage_vestnik_theme_conflict(fixtures_dir: Path) -> str:
  return (fixtures_dir / "storage_vestnik_theme_conflict.xml").read_text(encoding="utf-8")
