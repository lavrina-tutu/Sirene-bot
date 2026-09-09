"""Canonical source resolver: digest-only for document work."""
from __future__ import annotations

from pathlib import Path

import pytest

from deepmine.fail import ValidationError
from deepmine.manifest import load_manifest
from deepmine.source import (
  canonical_source,
  context_readiness,
  digest_readiness,
  list_unready_pages,
  require_fresh_context,
  require_fresh_digest,
)


def _write_digest(overlay: Path, page_id: str, status: str) -> Path:
  path = overlay / "digest" / "leaves" / f"p{page_id}.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(
    f"""---
page_id: "{page_id}"
status: {status}
---
## Источники

- Digest: [[p{page_id}]]

Facts.
""",
    encoding="utf-8",
  )
  return path


def test_fresh_returns_path(mini_overlay: Path):
  page_id = "514903239"
  _write_digest(mini_overlay, page_id, "fresh")
  status, path = digest_readiness(mini_overlay, page_id)
  assert status == "fresh"
  assert path is not None
  assert require_fresh_digest(mini_overlay, page_id) == path


def test_missing_raises_validation_error(mini_overlay: Path):
  with pytest.raises(ValidationError, match="status=missing"):
    require_fresh_digest(mini_overlay, "999999999", slug="TestProject")


def test_rejected_raises_validation_error(mini_overlay: Path):
  page_id = "514903239"
  _write_digest(mini_overlay, page_id, "rejected")
  with pytest.raises(ValidationError, match="status=rejected"):
    require_fresh_digest(mini_overlay, page_id, slug="TestProject")


def test_stale_raises_by_default(mini_overlay: Path):
  page_id = "514903239"
  _write_digest(mini_overlay, page_id, "stale")
  with pytest.raises(ValidationError, match="status=stale"):
    require_fresh_digest(mini_overlay, page_id, slug="TestProject")


def test_stale_allowed_with_flag(mini_overlay: Path):
  page_id = "514903239"
  path = _write_digest(mini_overlay, page_id, "stale")
  assert require_fresh_digest(mini_overlay, page_id, allow_stale=True) == path


def test_canonical_source_never_confluence_index(mini_overlay: Path):
  page_id = "514903239"
  path = canonical_source(mini_overlay, page_id)
  text = str(path)
  assert "Confluence/" not in text
  assert "index.md" not in text
  assert text.endswith(f"p{page_id}.md")


def test_context_fresh(mini_overlay: Path):
  path = mini_overlay / "charter-context.md"
  path.write_text("---\nstatus: fresh\n---\n## Источники\n\nx\n", encoding="utf-8")
  status, ctx_path = context_readiness(mini_overlay, "charter")
  assert status == "fresh"
  assert require_fresh_context(mini_overlay, "charter") == ctx_path


def test_context_missing_raises(mini_overlay: Path):
  with pytest.raises(ValidationError, match="status=missing"):
    require_fresh_context(mini_overlay, "charter", slug="TestProject")


def test_list_unready_pages(mini_overlay: Path):
  manifest = load_manifest(mini_overlay, slug="TestProject")
  _write_digest(mini_overlay, "493477568", "fresh")
  unready = list_unready_pages(mini_overlay, manifest)
  ids = {p["page_id"] for p in unready}
  assert "493477568" not in ids
  assert len(ids) >= 2
