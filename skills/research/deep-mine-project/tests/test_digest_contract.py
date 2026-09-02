"""Digest contract: slug, frontmatter, Источники first, history."""
from __future__ import annotations

from pathlib import Path

from deepmine.digest_io import (
  SOURCES_HEADER,
  archive_history,
  ensure_sources_first,
  leaf_slug_page,
  parse_digest,
  write_digest,
)


def test_leaf_slug_page():
  assert leaf_slug_page("493477568") == "p493477568"


def test_write_digest_sources_first(tmp_path: Path):
  path = tmp_path / "digest" / "leaves" / "p493477568.md"
  fm = {
    "schema_version": "1.0",
    "kind": "leaf",
    "slug": "p493477568",
    "status": "fresh",
    "generated_by": "composer-2.5",
  }
  body = "Compressed facts here."
  sources = f"{SOURCES_HEADER}\n\n- L0: `Confluence/root/index.md`"
  write_digest(path, fm, body, sources_block=sources)
  text = path.read_text(encoding="utf-8")
  assert text.startswith("---\n")
  parsed_fm, parsed_body = parse_digest(path)
  assert parsed_fm["slug"] == "p493477568"
  assert parsed_fm["status"] == "fresh"
  assert parsed_body.lstrip().startswith(SOURCES_HEADER)


def test_ensure_sources_first():
  body = "Facts\n"
  sources = f"{SOURCES_HEADER}\n\n- link"
  out = ensure_sources_first(body, sources)
  assert out.startswith(sources)


def test_archive_history(tmp_path: Path):
  overlay = tmp_path / "overlay"
  leaf = overlay / "digest" / "leaves" / "p493477568.md"
  leaf.parent.mkdir(parents=True)
  leaf.write_text("---\nslug: p493477568\n---\nbody\n", encoding="utf-8")
  dest = archive_history(overlay, "p493477568", "5", "abcd1234" * 8)
  assert dest is not None
  assert dest.exists()
  assert dest.parent.name == "_history"
