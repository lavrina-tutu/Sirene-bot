"""compress_with_llm: Hermes LLM path and cursor fallback."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deepmine.cursor_jobs import (
  ARCHITECT_MODEL,
  COMPRESSOR_LLM_SLUG,
  AgentResult,
  analyze,
  compress_with_llm,
  document,
  EXECUTOR_MODEL,
)
from deepmine.project_config import load_project_config


def _fake_llm_response(content: str) -> MagicMock:
  response = MagicMock()
  response.choices = [MagicMock()]
  response.choices[0].message.content = content
  return response


def test_compress_with_llm_uses_call_llm(mini_overlay):
  digest = "---\nslug: test\n---\n## Источники\n\nFacts."
  with patch("deepmine.cursor_jobs.call_text", return_value=digest) as mock_text:
    result = compress_with_llm("compress this", mini_overlay)
  assert result == digest
  mock_text.assert_called_once_with("compress this", timeout=300.0)


def test_compress_with_llm_empty_content_raises(mini_overlay):
  with patch("deepmine.cursor_jobs.call_text", side_effect=RuntimeError("LLM returned empty content")):
    with pytest.raises(RuntimeError, match="empty content"):
      compress_with_llm("compress this", mini_overlay)


def test_compress_with_llm_cursor_fallback(mini_overlay, monkeypatch):
  monkeypatch.setenv("DEEP_MINE_COMPRESSOR", "cursor")
  digest = "---\nslug: test\n---\n## Источники\n\nFacts."
  fake_result = AgentResult(0, digest, "", "composer-2.5")
  with patch("deepmine.cursor_jobs.run_agent", return_value=fake_result) as mock_agent:
    result = compress_with_llm("compress this", mini_overlay)
  assert result == digest
  mock_agent.assert_called_once_with(
    "compress this",
    "composer-2.5",
    mini_overlay,
    source_mode="l0_allowed",
    mode="ask",
  )


def test_analyze_still_uses_run_agent_grok(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  overlay = mini_overlay
  (overlay / "digest").mkdir(exist_ok=True)
  (overlay / "digest" / "_index.md").write_text("---\nslug: _index\n---\n# index\n", encoding="utf-8")
  (overlay / "digest" / "themes").mkdir(exist_ok=True)
  (overlay / "docs" / "_inbox").mkdir(parents=True, exist_ok=True)
  (overlay / "docs" / "_inbox" / "diff.md").write_text("# diff\n", encoding="utf-8")
  fake = AgentResult(0, '{"result":"ok"}', "", ARCHITECT_MODEL)
  with patch("deepmine.cursor_jobs.run_agent", return_value=fake) as mock_agent:
    analyze(overlay, cfg, full_archive=True)
  mock_agent.assert_called_once()
  args, kwargs = mock_agent.call_args
  assert args[1] == ARCHITECT_MODEL
  assert kwargs.get("source_mode") == "context_only"
  assert "mode" not in kwargs or kwargs.get("mode") is None


def test_document_still_uses_run_agent_composer(mini_workvault, mini_overlay):
  cfg = load_project_config("TestProject", workvault=mini_workvault)
  overlay = mini_overlay
  (overlay / "docs").mkdir(exist_ok=True)
  (overlay / "digest").mkdir(exist_ok=True)
  (overlay / "docs" / "architect-plan.md").write_text(
    "Plan referencing page_id: `514903239`\n",
    encoding="utf-8",
  )
  (overlay / "digest" / "_index.md").write_text("---\n---\n# index\n", encoding="utf-8")
  fake = AgentResult(0, '{"result":"ok"}', "", EXECUTOR_MODEL)
  with patch("deepmine.cursor_jobs.run_agent", return_value=fake) as mock_agent:
    document(overlay, cfg)
  mock_agent.assert_called_once()
  args, kwargs = mock_agent.call_args
  assert args[1] == EXECUTOR_MODEL
  assert kwargs.get("source_mode") == "context_only"
  assert "mode" not in kwargs or kwargs.get("mode") is None
