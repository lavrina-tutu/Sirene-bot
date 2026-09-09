"""MANIFEST.json migration and rebuild."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .l0 import parse_l0_page
from .models import PAGE_KIND, SCHEMA_VERSION, Manifest
from .paths import l0_abs
from .tree_sources import write_sources_md, write_tree_md


def is_p0_manifest(raw: dict[str, Any]) -> bool:
  return "schema_version" not in raw and "pages" not in raw


def migrate_manifest_p0(raw: dict[str, Any], *, slug: str) -> Manifest:
  if is_p0_manifest(raw):
    pages = {str(k): dict(v) for k, v in raw.items()}
    attachments: list[dict[str, Any]] = []
    digests: dict[str, Any] = {}
    contexts: dict[str, Any] = {}
  else:
    pages = {str(k): dict(v) for k, v in (raw.get("pages") or {}).items()}
    attachments = list(raw.get("attachments") or [])
    digests = dict(raw.get("digests") or {})
    contexts = dict(raw.get("contexts") or {})
  manifest = Manifest(
    schema_version=raw.get("schema_version") or SCHEMA_VERSION,
    slug=slug,
    pages=pages,
    attachments=attachments,
    digests=digests,
    contexts=contexts,
  )
  if manifest.schema_version == "1.0":
    manifest.schema_version = SCHEMA_VERSION
  return manifest


def save_manifest(manifest: Manifest, overlay: Path) -> None:
  (overlay / "MANIFEST.json").write_text(
    json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )


def rebuild_children(pages: dict[str, dict[str, Any]]) -> None:
  for page in pages.values():
    page["children"] = []
  for page_id, page in pages.items():
    parent = page.get("parent")
    if parent and str(parent) in pages:
      children = pages[str(parent)].setdefault("children", [])
      if page_id not in children:
        children.append(page_id)


def leaf_slug_page(page_id: str) -> str:
  return f"p{page_id}"


def _enrich_page_from_l0(
  page_id: str,
  page: dict[str, Any],
  workvault: Path,
) -> dict[str, Any]:
  local_rel = page.get("local_path")
  if not local_rel:
    return page
  l0_path = l0_abs(workvault, local_rel)
  if not l0_path.exists():
    return page
  rec = parse_l0_page(l0_path, local_path=local_rel)
  page.update(
    {
      "title": rec.title or page.get("title"),
      "space": rec.space or page.get("space"),
      "confluence_url": rec.confluence_url or page.get("confluence_url"),
      "version": rec.version or page.get("version"),
      "parent": rec.parent,
      "local_path": rec.local_path,
      "content_sha256": rec.content_sha256,
      "synced_at": rec.synced_at or page.get("synced_at"),
      "kind": PAGE_KIND,
      "digest_slug": leaf_slug_page(page_id),
      "digest_path": f"digest/leaves/{leaf_slug_page(page_id)}.md",
    }
  )
  return page


def rebuild_all(
  overlay: Path,
  workvault: Path,
  *,
  slug: str,
  root_page_id: str | None = None,
  pmo_seeds: list[dict[str, str]] | None = None,
) -> Manifest:
  manifest_path = overlay / "MANIFEST.json"
  if manifest_path.exists():
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
  else:
    raw = {}
  manifest = migrate_manifest_p0(raw, slug=slug)
  for page_id, page in list(manifest.pages.items()):
    manifest.pages[page_id] = _enrich_page_from_l0(page_id, page, workvault)
  rebuild_children(manifest.pages)
  manifest_path.write_text(
    json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  write_tree_md(
    manifest,
    overlay / "TREE.md",
    cfg_root=root_page_id,
    pmo_seeds=pmo_seeds,
  )
  write_sources_md(manifest, overlay / "SOURCES.md")
  return manifest


def load_manifest(overlay: Path, *, slug: str) -> Manifest:
  raw = json.loads((overlay / "MANIFEST.json").read_text(encoding="utf-8"))
  return migrate_manifest_p0(raw, slug=slug)
