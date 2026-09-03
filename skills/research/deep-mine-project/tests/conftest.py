"""Pytest fixtures for deep-mine-project."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
  sys.path.insert(0, str(SCRIPTS))

FIXTURES = Path(__file__).parent / "fixtures"
MINI_L0 = FIXTURES / "mini_l0"


@pytest.fixture
def table_l0_setup(mini_workvault: Path) -> Path:
  """Copy table_page fixture into mini WorkVault."""
  rel = "Confluence/DPAN/table_page/index.md"
  src = MINI_L0 / "table_page" / "index.md"
  dest = mini_workvault / rel
  dest.parent.mkdir(parents=True, exist_ok=True)
  dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
  return dest


@pytest.fixture
def skill_root() -> Path:
  return SKILL_ROOT


@pytest.fixture
def mini_workvault(tmp_path: Path) -> Path:
  """Mini WorkVault with 3 L0 pages and P0 manifest."""
  wv = tmp_path / "WorkVault"
  root_rel = "Confluence/DPAN/root/index.md"
  child_rel = "Confluence/DPAN/child/index.md"
  pmo_rel = "Confluence/PMO/pmo/index.md"
  for src, rel in (
    (MINI_L0 / "root" / "index.md", root_rel),
    (MINI_L0 / "child" / "index.md", child_rel),
    (MINI_L0 / "pmo" / "index.md", pmo_rel),
  ):
    dest = wv / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

  overlay = wv / "Projects" / "TestProject"
  overlay.mkdir(parents=True)
  p0 = {
    "493477568": {
      "title": "Root",
      "space": "DPAN",
      "confluence_url": "https://dom.tutu.ru/pages/viewpage.action?pageId=493477568",
      "version": "4",
      "local_path": root_rel,
      "content_sha256": "deadbeef",
      "synced_at": "2026-09-02T12:00:00Z",
    },
    "499549642": {
      "title": "Child",
      "space": "DPAN",
      "confluence_url": "https://dom.tutu.ru/pages/viewpage.action?pageId=499549642",
      "version": "13",
      "local_path": child_rel,
      "content_sha256": "cafebabe",
      "synced_at": "2026-09-02T12:00:00Z",
    },
    "490166551": {
      "title": "PMO Brief",
      "space": "PMO",
      "confluence_url": "https://dom.tutu.ru/pages/viewpage.action?pageId=490166551",
      "version": "41",
      "local_path": pmo_rel,
      "content_sha256": "baadf00d",
      "synced_at": "2026-09-02T12:00:00Z",
    },
  }
  (overlay / "MANIFEST.json").write_text(json.dumps(p0, indent=2), encoding="utf-8")
  (overlay / "PROJECT.yaml").write_text(
    """schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  pmo_seeds:
    - { page_id: "490166551", title: PMO, space: PMO }
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )
  return wv


@pytest.fixture
def mini_overlay(mini_workvault: Path) -> Path:
  return mini_workvault / "Projects" / "TestProject"
