"""Canonical document-work source resolver (context SoT for G/H/pack)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .digest_io import leaf_digest_path, leaf_slug_page, parse_digest
from .fail import ValidationError
from .paths import ARCH_MD, CHARTER_MD

FRESH = "fresh"
STALE = "stale"


def _read_context_status(path: Path) -> tuple[str, str | None]:
  if not path.is_file():
    return "missing", None
  text = path.read_text(encoding="utf-8")
  match = re.search(r"^status:\s*(\w+)", text, re.MULTILINE)
  status = match.group(1) if match else "unknown"
  sha_match = re.search(r'^sources_sha:\s*["\']?([a-f0-9]+)', text, re.MULTILINE)
  return status, sha_match.group(1) if sha_match else None


def context_readiness(overlay: Path, kind: str) -> tuple[str, Path | None]:
  path = overlay / (CHARTER_MD if kind == "charter" else ARCH_MD)
  status, _ = _read_context_status(path)
  return status, path


def require_fresh_context(
  overlay: Path,
  kind: str = "charter",
  *,
  slug: str | None = None,
) -> Path:
  status, path = context_readiness(overlay, kind)
  rel = CHARTER_MD if kind == "charter" else ARCH_MD
  if status == FRESH:
    return path  # type: ignore[return-value]
  slug_part = slug or "<slug>"
  raise ValidationError(
    f"context not ready for {kind}: status={status}\n"
    f"file: {rel}\n"
    f"fix: python3 .../deep_mine.py {kind} --slug {slug_part}"
  )


def digest_readiness(
  overlay: Path,
  page_id: str,
  *,
  manifest_page: dict[str, Any] | None = None,
) -> tuple[str, Path | None]:
  """Return ``(status, path)``. *path* is the digest file when it exists."""
  digest_path = leaf_digest_path(overlay, page_id)
  manifest_status = str(manifest_page.get("digest_status") or "") if manifest_page else ""

  if manifest_status == "missing_remote" and not digest_path.is_file():
    return "missing_remote", digest_path

  if not digest_path.is_file():
    if manifest_status == "missing_remote":
      return "missing_remote", digest_path
    return "missing", digest_path

  fm, _ = parse_digest(digest_path)
  file_status = str(fm.get("status") or manifest_status or "unknown")
  if file_status in ("rejected", "stale", "fresh", "missing_remote"):
    return file_status, digest_path
  if manifest_status:
    return manifest_status, digest_path
  return "missing", digest_path


def _digest_fix_line(slug: str, page_id: str) -> str:
  leaf = leaf_slug_page(page_id)
  return (
    f"fix: python3 .../deep_mine.py digest --slug {slug} --only {leaf}"
  )


def require_fresh_digest(
  overlay: Path,
  page_id: str,
  *,
  allow_stale: bool = False,
  manifest_page: dict[str, Any] | None = None,
  slug: str | None = None,
  task_hint: str | None = None,
) -> Path:
  """Fail-loud (exit 2) unless digest is fresh (or stale when *allow_stale*)."""
  status, digest_path = digest_readiness(overlay, page_id, manifest_page=manifest_page)
  rel = f"digest/leaves/{leaf_slug_page(page_id)}.md"
  if status == FRESH:
    return digest_path  # type: ignore[return-value]
  if status == STALE and allow_stale:
    return digest_path  # type: ignore[return-value]

  hint = f" ({task_hint})" if task_hint else ""
  slug_part = slug or "<slug>"
  raise ValidationError(
    f"digest not ready for page {page_id}{hint}: status={status}\n"
    f"file: {rel}\n"
    f"{_digest_fix_line(slug_part, page_id)}"
  )


def canonical_source(overlay: Path, page_id: str) -> Path:
  """Return digest leaf path — legacy; prefer context SoT."""
  return leaf_digest_path(overlay, page_id)


def list_unready_contexts(overlay: Path) -> list[dict[str, str]]:
  unready: list[dict[str, str]] = []
  for kind, rel in (("charter", CHARTER_MD), ("architecture", ARCH_MD)):
    status, path = context_readiness(overlay, kind)
    if status == FRESH:
      continue
    unready.append({
      "kind": kind,
      "status": status,
      "path": rel,
    })
  return unready


def list_unready_pages(overlay: Path, manifest) -> list[dict[str, str]]:
  """Pages without a fresh digest (legacy coordinator report)."""
  unready: list[dict[str, str]] = []
  for page_id, page in manifest.pages.items():
    status, path = digest_readiness(overlay, page_id, manifest_page=page)
    if status == FRESH:
      continue
    rel = (
      str(path.relative_to(overlay))
      if path and path.is_file()
      else f"digest/leaves/{leaf_slug_page(page_id)}.md"
    )
    unready.append({
      "page_id": page_id,
      "status": status,
      "digest_path": rel,
      "title": str(page.get("title") or ""),
    })
  return unready
