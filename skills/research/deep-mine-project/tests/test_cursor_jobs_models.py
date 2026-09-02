"""Cursor jobs: model selection and analyze prompt boundaries."""
from __future__ import annotations

from pathlib import Path

from deepmine.cursor_jobs import (
  ARCHITECT_MODEL,
  COMPRESSOR_MODEL,
  build_analyze_prompt,
  build_compress_prompt,
)
from deepmine.paths import COMPRESSOR_PROMPT
from deepmine.project_config import load_project_config


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
  prompt = build_analyze_prompt(overlay, cfg)
  assert "_index.md" in prompt
  assert "diff.md" in prompt
  assert "SECRET L0 BODY" not in prompt
  assert "Confluence/DPAN/root/index.md" not in prompt
