"""T1: L0 sha256 is 64 hex of body without frontmatter."""
from pathlib import Path

from deepmine.l0 import parse_l0_page, sha256_body


def test_sha256_body_length():
  fixtures = Path(__file__).parent / "fixtures" / "mini_l0" / "root" / "index.md"
  rec = parse_l0_page(fixtures, local_path="Confluence/DPAN/root/index.md")
  assert len(rec.content_sha256) == 64
  assert rec.content_sha256 == sha256_body(rec.body)


def test_p0_short_sha_not_used_as_is(mini_overlay, mini_workvault):
  from deepmine.manifest import rebuild_all

  manifest = rebuild_all(mini_overlay, mini_workvault, slug="TestProject")
  for page in manifest.pages.values():
    assert len(page["content_sha256"]) == 64
