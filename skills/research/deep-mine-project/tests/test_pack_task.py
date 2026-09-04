"""Pack --task: PACK.md, BRIEF.md, MANIFEST check."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from deepmine.pack import run_pack
from deepmine.fail import ValidationError


def _write_fresh_digest(overlay: Path, page_id: str) -> None:
  leaves_dir = overlay / "digest" / "leaves"
  leaves_dir.mkdir(parents=True, exist_ok=True)
  (leaves_dir / f"p{page_id}.md").write_text(
    f"""---
page_id: "{page_id}"
status: fresh
---
## Источники

- Digest: [[p{page_id}]]

Pack facts.
""",
    encoding="utf-8",
  )


def _write_manifest(overlay: Path, page_id: str, local_path: str) -> None:
  data = {
    "schema_version": "1.0",
    "slug": "TestProject",
    "pages": {
      page_id: {
        "title": "Feature compare",
        "space": "DPAN",
        "confluence_url": f"https://dom.tutu.ru/pages/viewpage.action?pageId={page_id}",
        "version": "12",
        "local_path": local_path,
        "content_sha256": "abc" * 21 + "a",
        "digest_slug": f"p{page_id}",
        "digest_path": f"digest/leaves/p{page_id}.md",
        "digest_status": "fresh",
      }
    },
    "attachments": [],
    "digests": {},
  }
  (overlay / "MANIFEST.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_pack_creates_inbox(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  project_yaml = mini_overlay / "PROJECT.yaml"
  text = project_yaml.read_text(encoding="utf-8")
  project_yaml.write_text(
    text + "\nconfluence:\n  tasks:\n    feature_compare: \"514903239\"\n",
    encoding="utf-8",
  )
  # fix duplicate confluence key — rewrite properly
  project_yaml.write_text(
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

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  _write_fresh_digest(mini_overlay, page_id)
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
  assert "digest/leaves/p514903239.md" in pack
  assert "local_path:" not in pack
  assert "Confluence/" not in pack


def _setup_pack_project(mini_overlay: Path, *, themes: list[str] | None = None) -> None:
  themes_block = ""
  if themes:
    themes_block = "themes:\n" + "".join(f"  - {t}\n" for t in themes)
  (mini_overlay / "PROJECT.yaml").write_text(
    f"""schema_version: "1.0"
slug: TestProject
display_name: Test
entity_slug: trisigma
confluence:
  root_page_id: "493477568"
  root_title: Root
  space_primary: DPAN
  pmo_seeds:
    - {{ page_id: "490166551", title: PMO, space: PMO }}
  tasks:
    feature_compare: "514903239"
mpp:
  expected_name: test.mpp
  project_title: Test
meetings:
  project_slugs: [trisigma]
{themes_block}""",
    encoding="utf-8",
  )


def test_pack_includes_fresh_theme_digest(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  _setup_pack_project(mini_overlay, themes=["pmo", "architecture"])

  leaves_dir = mini_overlay / "digest" / "leaves"
  leaves_dir.mkdir(parents=True, exist_ok=True)
  (leaves_dir / "p514903239.md").write_text(
    """---
page_id: "514903239"
status: fresh
related:
  - pmo
---
## Источники

- L0: `Confluence/DPAN/child/index.md`

| Feature | Status |
|---------|--------|
| A | ok |
""",
    encoding="utf-8",
  )

  themes_dir = mini_overlay / "digest" / "themes"
  themes_dir.mkdir(parents=True, exist_ok=True)
  (themes_dir / "pmo.md").write_text(
    """---
kind: theme
slug: pmo
status: fresh
---
## Источники

- Leaves: p514903239

PMO theme facts from leaves.
""",
    encoding="utf-8",
  )
  (themes_dir / "journal-theme.md").write_text(
    """---
kind: theme
slug: journal-theme
status: rejected
related:
  - pmo
---
## Источники

Digest записан: сжал до 39,8% от L0.
""",
    encoding="utf-8",
  )

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  _write_fresh_digest(mini_overlay, page_id)
  pack_dir = run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")
  pack = (pack_dir / "PACK.md").read_text(encoding="utf-8")
  assert "digest/themes/pmo.md" in pack
  assert "theme: pmo" in pack
  assert "journal-theme" not in pack
  assert "architecture" not in pack or "digest/themes/architecture" not in pack
  brief = (pack_dir / "BRIEF.md").read_text(encoding="utf-8")
  assert "theme `pmo`" in brief


def test_pack_missing_theme_does_not_fail(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  _setup_pack_project(mini_overlay, themes=["pmo", "security"])

  leaves_dir = mini_overlay / "digest" / "leaves"
  leaves_dir.mkdir(parents=True, exist_ok=True)
  (leaves_dir / "p514903239.md").write_text(
    """---
page_id: "514903239"
status: fresh
related:
  - pmo
  - security
---
## Источники

- L0: `Confluence/DPAN/child/index.md`
""",
    encoding="utf-8",
  )

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  _write_fresh_digest(mini_overlay, page_id)
  pack_dir = run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")
  pack = (pack_dir / "PACK.md").read_text(encoding="utf-8")
  assert "(none)" in pack.split("## Theme digests")[1].split("##")[0]


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

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  with pytest.raises(ValidationError, match="not in MANIFEST"):
    run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")


def test_pack_missing_digest_fails(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  _setup_pack_project(mini_overlay)

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  with pytest.raises(ValidationError, match="status=missing"):
    run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")


def test_pack_rejected_digest_fails(mini_workvault: Path, mini_overlay: Path):
  page_id = "514903239"
  _write_manifest(mini_overlay, page_id, "Confluence/DPAN/child/index.md")
  _setup_pack_project(mini_overlay)
  leaves_dir = mini_overlay / "digest" / "leaves"
  leaves_dir.mkdir(parents=True, exist_ok=True)
  (leaves_dir / "p514903239.md").write_text(
    """---
page_id: "514903239"
status: rejected
---
## Источники

Rejected digest.
""",
    encoding="utf-8",
  )

  from deepmine.project_config import load_project_config

  cfg = load_project_config("TestProject", workvault=mini_workvault)
  with pytest.raises(ValidationError, match="status=rejected"):
    run_pack(cfg, mini_overlay, mini_workvault, "feature_compare")


def test_pack_tables_uses_extracts_not_l0(mini_workvault: Path, mini_overlay: Path, table_l0_setup: Path):
  page_id = "514903239"
  data = {
    "schema_version": "1.0",
    "slug": "TestProject",
    "pages": {
      page_id: {
        "title": "Table page",
        "local_path": "Confluence/DPAN/table_page/index.md",
        "version": "1",
        "digest_slug": f"p{page_id}",
        "digest_status": "fresh",
        "has_tables": True,
      }
    },
    "attachments": [],
    "digests": {},
  }
  (mini_overlay / "MANIFEST.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
  _setup_pack_project(mini_overlay)
  _write_fresh_digest(mini_overlay, page_id)

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
