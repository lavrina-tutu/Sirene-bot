"""Pack --task: PACK.md, BRIEF.md, MANIFEST check."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from deepmine.pack import run_pack
from deepmine.fail import ValidationError
from deepmine.paths import CHARTER_MD, GRAPH_JSON


def _write_charter(overlay: Path, status: str = "fresh") -> None:
  (overlay / CHARTER_MD).write_text(
    f"""---
schema_version: "1.0"
kind: charter
status: {status}
sources_sha: "deadbeef"
---
## Источники

- GRAPH.json
""",
    encoding="utf-8",
  )
  (overlay / GRAPH_JSON).write_text('{"nodes": {}, "edges": []}', encoding="utf-8")


def _write_manifest(overlay: Path, page_id: str, local_path: str) -> None:
  data = {
    "schema_version": "1.1",
    "slug": "TestProject",
    "pages": {
      page_id: {
        "title": "Feature compare",
        "space": "DPAN",
        "confluence_url": f"https://dom.tutu.ru/pages/viewpage.action?pageId={page_id}",
        "version": "12",
        "local_path": local_path,
        "content_sha256": "abc" * 21 + "a",
      }
    },
    "attachments": [],
    "digests": {},
    "contexts": {},
  }
  (overlay / "MANIFEST.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _setup_pack_project(mini_overlay: Path) -> None:
  (mini_overlay / "PROJECT.yaml").write_text(
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
  tasks:
    feature_compare: "514903239"
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )


def test_pack_creates_inbox(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  _setup_pack_project(mini_overlay)
  _write_charter(mini_overlay)

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  pack_dir = run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")
  assert pack_dir.is_dir()
  assert (pack_dir / "PACK.md").is_file()
  assert (pack_dir / "BRIEF.md").is_file()
  assert (pack_dir / "extracts").is_dir()
  brief = (pack_dir / "BRIEF.md").read_text(encoding="utf-8")
  assert "да" in brief
  assert "Чеклист инвариантов" in brief
  pack = (pack_dir / "PACK.md").read_text(encoding="utf-8")
  assert "514903239" in pack
  assert CHARTER_MD in pack
  assert GRAPH_JSON in pack
  assert "local_path:" not in pack
  assert "Confluence/" not in pack


def test_pack_includes_context_sot(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  _setup_pack_project(mini_overlay)
  _write_charter(mini_overlay)

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  pack_dir = run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")
  pack = (pack_dir / "PACK.md").read_text(encoding="utf-8")
  assert "Context SoT" in pack
  assert "architecture-context.md" in pack
  assert "digest/themes" not in pack


def test_pack_missing_manifest_fails(mini_workvault: Path, mini_overlay: Path):
  project_yaml = mini_overlay / "PROJECT.yaml"
  project_yaml.write_text(
    """schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  tasks:
    feature_compare: "999999999"
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )
  _write_manifest(mini_overlay, "493477568", "Confluence/DPAN/root/index.md")
  _write_charter(mini_overlay)

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  with pytest.raises(ValidationError, match="not in MANIFEST"):
    run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")


def test_pack_missing_context_fails(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  _setup_pack_project(mini_overlay)

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  with pytest.raises(ValidationError, match="status=missing"):
    run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")


def test_pack_stale_context_fails(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  _setup_pack_project(mini_overlay)
  _write_charter(mini_overlay, status="stale")

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  with pytest.raises(ValidationError, match="status=stale"):
    run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")


def test_pack_tables_uses_extracts_not_l0(mini_workvault: Path, mini_overlay: Path, table_l0_setup: Path):
  page_id = "514903239"
  data = {
    "schema_version": "1.1",
    "slug": "TestProject",
    "pages": {
      page_id: {
        "title": "Table page",
        "local_path": "Confluence/DPAN/table_page/index.md",
        "version": "1",
        "has_tables": True,
      }
    },
    "attachments": [],
    "digests": {},
    "contexts": {},
  }
  (mini_overlay / "MANIFEST.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
  _setup_pack_project(mini_overlay)
  _write_charter(mini_overlay)

  extracts_dir = mini_overlay / "docs" / "_inbox" / "feature_compare" / "extracts"
  extracts_dir.mkdir(parents=True, exist_ok=True)
  (extracts_dir / f"{page_id}__feature_compare.csv").write_text("H1,H2\na,b\n", encoding="utf-8")

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  pack_dir = run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")
  brief = (pack_dir / "BRIEF.md").read_text(encoding="utf-8")
  pack = (pack_dir / "PACK.md").read_text(encoding="utf-8")
  assert "L0:" not in brief
  assert "Confluence/DPAN" not in brief
  assert "Confluence/DPAN" not in pack
  assert "extract" in brief
