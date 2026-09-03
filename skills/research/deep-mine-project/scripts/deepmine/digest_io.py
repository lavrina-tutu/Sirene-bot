"""Digest I/O: frontmatter, history, stale tracking, index."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .l0 import split_frontmatter

SOURCES_HEADER = "## Источники"


def leaf_slug_page(page_id: str) -> str:
  return f"p{page_id}"


def leaf_digest_path(overlay: Path, page_id: str) -> Path:
  return overlay / "digest" / "leaves" / f"{leaf_slug_page(page_id)}.md"


def theme_digest_path(overlay: Path, theme: str) -> Path:
  return overlay / "digest" / "themes" / f"{theme}.md"


def parse_digest(path: Path) -> tuple[dict[str, Any], str]:
  return split_frontmatter(path.read_text(encoding="utf-8"))


def ensure_sources_first(body: str, sources_block: str) -> str:
  stripped = body.lstrip()
  if stripped.startswith(SOURCES_HEADER):
    return body
  return f"{sources_block.rstrip()}\n\n{stripped}"


def write_digest(
  path: Path,
  fm: dict[str, Any],
  body: str,
  *,
  sources_block: str | None = None,
) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  if sources_block:
    body = ensure_sources_first(body, sources_block)
  header = yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip()
  text = f"---\n{header}\n---\n{body}"
  if not text.endswith("\n"):
    text += "\n"
  path.write_text(text, encoding="utf-8")


def set_digest_status(path: Path, status: str) -> None:
  """Update frontmatter status (e.g. ``rejected``)."""
  fm, body = parse_digest(path)
  fm["status"] = status
  write_digest(path, fm, body)


def archive_history(overlay: Path, slug: str, version: str, source_sha: str) -> Path | None:
  for sub in ("leaves", "themes"):
    src = overlay / "digest" / sub / f"{slug}.md"
    if src.exists():
      ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
      sha8 = (source_sha or "00000000")[:8]
      dest = overlay / "digest" / "_history" / f"{slug}_v{version}_{sha8}_{ts}.md"
      dest.parent.mkdir(parents=True, exist_ok=True)
      dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
      return dest
  return None


def mark_stale_page(page: dict[str, Any]) -> None:
  page["digest_status"] = "stale"


def mark_stale_manifest(manifest, slug: str) -> None:
  for page in manifest.pages.values():
    if page.get("digest_slug") == slug:
      mark_stale_page(page)
      return
  entry = manifest.digests.get(slug)
  if entry:
    entry["status"] = "stale"


def list_stale(manifest) -> list[str]:
  slugs: list[str] = []
  for page in manifest.pages.values():
    if page.get("digest_status") == "stale":
      slugs.append(str(page.get("digest_slug") or ""))
  for key, dig in manifest.digests.items():
    if dig.get("status") == "stale":
      slugs.append(str(key))
  return sorted({s for s in slugs if s})


def load_all_digests(overlay: Path) -> dict[str, dict[str, Any]]:
  digests: dict[str, dict[str, Any]] = {}
  for sub in ("leaves", "themes"):
    d = overlay / "digest" / sub
    if not d.is_dir():
      continue
    for path in sorted(d.glob("*.md")):
      fm, _ = parse_digest(path)
      slug = str(fm.get("slug") or path.stem)
      digests[slug] = fm
  return digests


def write_index_md(overlay: Path, digests: dict[str, dict[str, Any]], generated_at: str) -> None:
  fm = {
    "schema_version": "1.0",
    "kind": "index",
    "slug": "_index",
    "generated_at": generated_at,
    "generated_by": "deep-mine",
  }
  lines = ["# Digest index", ""]
  for slug in sorted(digests):
    d = digests[slug]
    title = d.get("title", slug)
    status = d.get("status", "unknown")
    lines.append(f"- [[{slug}]] — {title} ({status})")
  write_digest(overlay / "digest" / "_index.md", fm, "\n".join(lines) + "\n")


def utc_now_iso() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
