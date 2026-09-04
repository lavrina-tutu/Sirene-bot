"""task_pages in PROJECT.yaml, pull, refresh, pack integration (A1)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deepmine.confluence_pull import pull_seed_tree
from deepmine.fail import ValidationError
from deepmine.pack import run_pack
from deepmine.project_config import default_trisigma_yaml, load_project_config
from deepmine.refresh import refresh_pages
from deepmine.models import Manifest


def test_default_trisigma_yaml_has_task_pages():
  text = default_trisigma_yaml()
  assert "task_pages:" in text
  assert "519487958" in text
  assert "519489611" in text
  assert "514903239" in text
  assert "490167911" not in text.split("task_pages:")[1].split("follow_outbound")[0]


def test_project_config_task_pages_property(mini_workvault: Path, mini_overlay: Path):
  (mini_overlay / "PROJECT.yaml").write_text(
    """schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  task_pages:
    - { page_id: "514903239", role: feature_compare }
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  assert len(cfg.task_pages) == 1
  assert cfg.tasks["feature_compare"] == "514903239"


@patch("deepmine.confluence_pull.run_pull")
def test_pull_seed_tree_includes_task_pages(mock_pull: MagicMock):
  from deepmine.project_config import ProjectConfig

  cfg = ProjectConfig(
    schema_version="1.0",
    slug="T",
    display_name="T",
    entity_slug="t",
    confluence={
      "root_page_id": "1",
      "root_title": "R",
      "space_primary": "X",
      "pmo_seeds": [{"page_id": "2"}],
      "task_pages": [{"page_id": "514903239", "role": "feature_compare"}],
    },
    mpp={},
    meetings={},
  )
  pull_seed_tree(cfg)
  pulled_ids = [c.args[0] for c in mock_pull.call_args_list]
  assert "514903239" in pulled_ids
  assert mock_pull.call_args_list[-1].kwargs.get("recursive") is False


def _manifest_with_page(page_id: str, local_path: str) -> Manifest:
  return Manifest(
    schema_version="1.0",
    slug="TestProject",
    pages={
      page_id: {
        "title": "T",
        "space": "DPAN",
        "confluence_url": f"https://dom.tutu.ru/pages/viewpage.action?pageId={page_id}",
        "version": "1",
        "local_path": local_path,
        "content_sha256": "a" * 64,
        "digest_slug": f"p{page_id}",
      }
    },
    attachments=[],
    digests={},
  )


def test_refresh_fails_task_page_not_in_manifest(mini_workvault: Path, mini_overlay: Path):
  (mini_overlay / "PROJECT.yaml").write_text(
    """schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  task_pages:
    - { page_id: "999999999", role: feature_compare }
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  manifest = _manifest_with_page("493477568", "Confluence/DPAN/root/index.md")
  with patch("deepmine.refresh._client") as mock_client:
    mock_client.return_value.get_page.return_value = {"version": {"number": 4}}
    with pytest.raises(ValidationError, match="not in MANIFEST"):
      refresh_pages(cfg, manifest, mini_overlay, mini_workvault, dry_run=True)


def test_pack_with_table_extracts_csv(mini_workvault: Path, mini_overlay: Path, table_l0_setup):
  page_id = "514903239"
  rel = "Confluence/DPAN/table_page/index.md"
  data = {
    "schema_version": "1.0",
    "slug": "TestProject",
    "pages": {
      page_id: {
        "title": "Features",
        "space": "DPAN",
        "confluence_url": f"https://dom.tutu.ru/pages/viewpage.action?pageId={page_id}",
        "version": "12",
        "local_path": rel,
        "content_sha256": "a" * 64,
        "digest_slug": f"p{page_id}",
        "digest_status": "fresh",
        "has_tables": True,
      }
    },
    "attachments": [],
    "digests": {},
  }
  (mini_overlay / "MANIFEST.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
  (mini_overlay / "PROJECT.yaml").write_text(
    """schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  task_pages:
    - { page_id: "514903239", role: feature_compare }
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )
  leaves_dir = mini_overlay / "digest" / "leaves"
  leaves_dir.mkdir(parents=True, exist_ok=True)
  (leaves_dir / f"p{page_id}.md").write_text(
    f"""---
page_id: "{page_id}"
status: fresh
---
## Источники

Facts.
""",
    encoding="utf-8",
  )
  extracts_dir = mini_overlay / "docs" / "_inbox" / "feature_compare" / "extracts"
  extracts_dir.mkdir(parents=True, exist_ok=True)
  (extracts_dir / f"{page_id}__feature_compare.csv").write_text("H1,H2\na,b\n", encoding="utf-8")
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  pack_dir = run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")
  csv_path = pack_dir / "extracts" / "514903239__feature_compare.csv"
  assert csv_path.is_file()
  pack = (pack_dir / "PACK.md").read_text(encoding="utf-8")
  assert "514903239__feature_compare.csv" in pack


def test_pack_table_without_csv_path_fails(
  mini_workvault: Path, mini_overlay: Path, table_l0_setup,
):
  """Pack must fail when has_tables and no CSV extract (no L0 read)."""
  page_id = "514903239"
  rel = "Confluence/DPAN/table_page/index.md"
  data = {
    "schema_version": "1.0",
    "slug": "TestProject",
    "pages": {
      page_id: {
        "title": "Features",
        "local_path": rel,
        "version": "1",
        "digest_slug": f"p{page_id}",
        "has_tables": True,
      }
    },
    "attachments": [],
    "digests": {},
  }
  (mini_overlay / "MANIFEST.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
  (mini_overlay / "PROJECT.yaml").write_text(
    """schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  task_pages:
    - { page_id: "514903239", role: feature_compare }
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
""",
    encoding="utf-8",
  )
  leaves_dir = mini_overlay / "digest" / "leaves"
  leaves_dir.mkdir(parents=True, exist_ok=True)
  (leaves_dir / f"p{page_id}.md").write_text(
    f"""---
page_id: "{page_id}"
status: fresh
---
## Источники

Facts.
""",
    encoding="utf-8",
  )
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  with pytest.raises(ValidationError, match="has_tables but no CSV"):
    run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")
