"""Cursor jobs: model selection and analyze prompt boundaries."""
from __future__ import annotations

from pathlib import Path

import pytest

from deepmine.cursor_jobs import (
  ARCHITECT_MODEL,
  COMPRESSOR_MODEL,
  build_analyze_prompt,
  build_compress_prompt,
  build_document_prompt,
  document_preflight,
)
from deepmine.fail import ValidationError
from deepmine.manifest import load_manifest
from deepmine.paths import COMPRESSOR_PROMPT
from deepmine.project_config import load_project_config


def _write_fresh_digest(overlay: Path, page_id: str) -> None:
  path = overlay / "digest" / "leaves" / f"p{page_id}.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(
    f"""---
page_id: "{page_id}"
status: fresh
---
## Источники

Facts.
""",
    encoding="utf-8",
  )


def test_compress_uses_composer_and_compressor_prompt(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  prompt = build_compress_prompt("L0 test", cfg, ["p493477568"])
  assert COMPRESSOR_MODEL == "composer-2.5"
  assert str(COMPRESSOR_PROMPT) in prompt or COMPRESSOR_PROMPT.name in prompt
  assert "project-context-compressor" in COMPRESSOR_PROMPT.read_text(encoding="utf-8")


def test_analyze_prompt_uses_grok_model():
  assert ARCHITECT_MODEL == "cursor-grok-4.6-high"


def test_analyze_prompt_no_confluence_bodies(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  overlay = mini_overlay
  (overlay / "digest").mkdir(exist_ok=True)
  (overlay / "digest" / "_index.md").write_text("---\nslug: _index\n---\n# index\n", encoding="utf-8")
  (overlay / "digest" / "themes").mkdir(exist_ok=True)
  (overlay / "docs" / "_inbox").mkdir(parents=True, exist_ok=True)
  (overlay / "docs" / "_inbox" / "diff.md").write_text("# diff\n", encoding="utf-8")
  l0_body = "SECRET L0 BODY confluence_id marker"
  confluence_path = mini_workvault / "Confluence" / "DPAN" / "root" / "index.md"
  confluence_path.write_text(f"---\nconfluence_id: '493477568'\n---\n{l0_body}\n", encoding="utf-8")
  prompt = build_analyze_prompt(overlay, cfg, full_archive=True)
  assert "_index.md" in prompt
  assert "diff.md" in prompt
  assert "SECRET L0 BODY" not in prompt
  assert "Confluence/DPAN" not in prompt
  assert "- L0:" not in prompt
  assert "digest/themes" in prompt


def test_analyze_task_prompt_no_l0(mini_workvault, mini_overlay, skill_root):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  pack_dir = mini_overlay / "docs" / "_inbox" / "feature_compare"
  pack_dir.mkdir(parents=True)
  (pack_dir / "PACK.md").write_text(
    "# Pack\n\n- page_id: `514903239`\n- digest: `digest/leaves/p514903239.md`\n",
    encoding="utf-8",
  )
  template = (skill_root / "references" / "architect-brief.template.md").read_text(encoding="utf-8")
  (pack_dir / "BRIEF.md").write_text(
    template.replace("{{inv_ceil}}", "да")
    .replace("{{inv_pilot}}", "да")
    .replace("{{inv_source}}", "да")
    .replace("{{inv_format}}", "да")
    .replace("{{inv_budget}}", "да")
    .replace("{{inv_dates}}", "да")
    .replace("{{task_id}}", "feature_compare")
    .replace("{{role_goal}}", "test")
    .replace("{{pack_paths}}", "- digest")
    .replace("{{fields_questions}}", "q")
    .replace("{{open_gaps}}", "g"),
    encoding="utf-8",
  )
  prompt = build_analyze_prompt(mini_overlay, cfg, pack_dir=pack_dir)
  assert "Confluence/DPAN" not in prompt
  assert "- L0:" not in prompt
  assert "local_path:" not in prompt
  assert "digest/leaves" in prompt


def test_document_prompt_no_l0(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  overlay = mini_overlay
  (overlay / "docs").mkdir(exist_ok=True)
  (overlay / "digest").mkdir(exist_ok=True)
  (overlay / "docs" / "architect-plan.md").write_text(
    "Plan referencing page_id: `514903239`\n",
    encoding="utf-8",
  )
  (overlay / "digest" / "_index.md").write_text("---\n---\n# index\n", encoding="utf-8")
  _write_fresh_digest(overlay, "514903239")
  pack_dir = overlay / "docs" / "_inbox" / "feature_compare"
  pack_dir.mkdir(parents=True)
  (pack_dir / "PACK.md").write_text("- page_id: `514903239`\n", encoding="utf-8")

  prompt = build_document_prompt(overlay, cfg)
  assert "Confluence/DPAN" not in prompt
  assert "- L0:" not in prompt
  assert "digest/leaves/p514903239.md" in prompt
  assert "_index.md" in prompt


def test_document_preflight_fails_without_digest(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  (mini_overlay / "docs").mkdir(exist_ok=True)
  (mini_overlay / "docs" / "architect-plan.md").write_text(
    "page_id: `514903239`\n",
    encoding="utf-8",
  )
  manifest = load_manifest(mini_overlay, slug="TestProject")
  with pytest.raises(ValidationError, match="status=missing"):
    document_preflight(mini_overlay, cfg, manifest)
