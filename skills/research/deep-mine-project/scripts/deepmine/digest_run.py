"""Digest orchestration (step F)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cursor_jobs import compress_leaf, compress_plan, compress_theme, rebuild_graph
from .digest_io import list_stale, utc_now_iso
from .manifest import load_manifest
from .project_config import ProjectConfig


def _page_by_slug(manifest, slug: str) -> tuple[str, dict[str, Any]] | None:
  for page_id, page in manifest.pages.items():
    if page.get("digest_slug") == slug:
      return page_id, page
  return None


def run_digest(
  cfg: ProjectConfig,
  overlay: Path,
  workvault: Path,
  *,
  only: str | None = None,
  all_stale: bool = False,
  plan_only: bool = False,
  dry_run: bool = False,
) -> dict[str, Any]:
  manifest = load_manifest(overlay, slug=cfg.slug)
  generated_at = utc_now_iso()
  compressed: list[str] = []

  if plan_only:
    compress_plan(overlay, cfg, dry_run=dry_run)
    if not dry_run:
      manifest.digests.setdefault("mpp-plan", {})["status"] = "fresh"
    _save_manifest(overlay, manifest)
    return {"compressed": ["mpp-plan"], "plan_only": True}

  targets: list[tuple[str, dict[str, Any]]] = []
  if only:
    found = _page_by_slug(manifest, only)
    if found:
      targets.append(found)
    elif only.startswith("p") and only[1:] in manifest.pages:
      targets.append((only[1:], manifest.pages[only[1:]]))
  elif all_stale:
    for slug in list_stale(manifest):
      found = _page_by_slug(manifest, slug)
      if found:
        targets.append(found)
  else:
    targets = list(manifest.pages.items())

  for page_id, page in targets:
    slug = compress_leaf(page_id, page, overlay, workvault, cfg, dry_run=dry_run)
    if slug:
      compressed.append(slug)

  if not dry_run:
    full_run = only is None and not all_stale
    if full_run:
      for theme in cfg.themes:
        compress_theme(theme, overlay, cfg, dry_run=False)

      mpp_info = manifest.digests.get("mpp-plan", {})
      if mpp_info.get("status") in ("pending_compress", "stale", None):
        if list((overlay / "mpp").glob("*__tasks.csv")):
          compress_plan(overlay, cfg)
          mpp_info["status"] = "fresh"

    rebuild_graph(overlay, manifest, generated_at)
    for page_id, page in manifest.pages.items():
      if page.get("digest_slug") in compressed:
        page["digest_status"] = "fresh"
    _save_manifest(overlay, manifest)

  return {"compressed": compressed, "generated_at": generated_at}


def _save_manifest(overlay: Path, manifest) -> None:
  (overlay / "MANIFEST.json").write_text(
    json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
