"""Digest contract: slug, frontmatter, Источники first, history, journal reject."""
from __future__ import annotations

from pathlib import Path

import pytest

from deepmine.digest_io import (
  SOURCES_HEADER,
  archive_history,
  ensure_sources_first,
  leaf_slug_page,
  parse_digest,
  write_digest,
)
from deepmine.digest_validate import validate_digest_body

FIXTURES = Path(__file__).parent / "fixtures" / "digest"


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


def test_journal_fixture_rejected():
  body = (FIXTURES / "p514903239_journal.md").read_text(encoding="utf-8")
  assert validate_digest_body(body) == "rejected"


def test_facts_fixture_ok():
  body = (FIXTURES / "p514903239_facts.md").read_text(encoding="utf-8")
  l0_with_table = "| A | B |\n|---|---|\n| 1 | 2 |\n"
  assert validate_digest_body(body, l0_body=l0_with_table) == "ok"


def test_l0_table_without_digest_table_rejected():
  body = "## Источники\n\n- L0: path\n\nТолько текст без таблицы."
  l0 = "<table><tr><td>x</td></tr></table>"
  assert validate_digest_body(body, l0_body=l0) == "rejected"
