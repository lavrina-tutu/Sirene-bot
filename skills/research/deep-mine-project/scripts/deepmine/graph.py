"""Digest graph utilities and SoT edge types for GRAPH.json."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_PAGE_ID_RE = re.compile(r"pageId=(\d+)")


def extract_outbound_page_ids(md_body: str) -> set[str]:
  return set(_PAGE_ID_RE.findall(md_body))


def recompute_backlinks(digests: dict[str, dict[str, Any]]) -> None:
  """Digest-only backlinks for digest/links.md (not GRAPH SoT)."""
  for digest in digests.values():
    digest["backlinks"] = []
  for slug, digest in digests.items():
    related = digest.get("related") or []
    children = digest.get("children") or []
    for target in related + children:
      if target in digests:
        backlinks = digests[target].setdefault("backlinks", [])
        if slug not in backlinks:
          backlinks.append(slug)


def write_links_md(
  edges: list[tuple[str, str, str]],
  path: Path,
  generated_at: str | None = None,
) -> None:
  """Write digest/links.md (legacy digest graph, not GRAPH SoT)."""
  lines = [
    "# digest/links.md — граф связей",
    "",
  ]
  if generated_at:
    lines.append(f"generated_at: {generated_at}")
    lines.append("")
  lines.append("from,to,edge")
  for frm, to, edge in edges:
    lines.append(f"{frm},{to},{edge}")
  path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_edges(
  digests: dict[str, dict[str, Any]],
  pages: dict[str, dict[str, Any]],
) -> list[tuple[str, str, str]]:
  """Digest overlay edges including related/backlink (digest only, not GRAPH)."""
  edges: list[tuple[str, str, str]] = []
  page_to_slug = {pid: p.get("digest_slug") or f"p{pid}" for pid, p in pages.items()}
  for pid, page in pages.items():
    parent = page.get("parent")
    child_slug = page_to_slug.get(pid)
    if parent and child_slug:
      parent_slug = page_to_slug.get(str(parent))
      if parent_slug:
        edges.append((parent_slug, child_slug, "parent"))
        edges.append((child_slug, parent_slug, "child"))
  for slug, digest in digests.items():
    for target in digest.get("related") or []:
      if target in digests:
        edges.append((slug, target, "related"))
    for bl in digest.get("backlinks") or []:
      if bl in digests:
        edges.append((bl, slug, "backlink"))
  return edges


def collect_sot_edges(
  pages: dict[str, dict[str, Any]],
  workvault: Path,
  seeds: set[str],
) -> list[tuple[str, str, str]]:
  """GRAPH SoT edges: parent|child|links_to|seed only."""
  from .paths import l0_abs

  edges: list[tuple[str, str, str]] = []
  for page_id in seeds:
    edges.append((page_id, page_id, "seed"))
  for page_id, page in pages.items():
    parent = page.get("parent")
    if parent and str(parent) in pages:
      edges.append((str(parent), page_id, "child"))
      edges.append((page_id, str(parent), "parent"))
    local = page.get("local_path")
    if not local:
      continue
    l0 = l0_abs(workvault, local)
    if not l0.exists():
      continue
    body = l0.read_text(encoding="utf-8")
    for target_id in extract_outbound_page_ids(body):
      if target_id in pages:
        edges.append((page_id, target_id, "links_to"))
  return edges


def collect_related_unresolved(pages: dict[str, dict[str, Any]], workvault: Path) -> set[str]:
  from .paths import l0_abs

  known = set(pages.keys())
  unresolved: set[str] = set()
  for page in pages.values():
    local = page.get("local_path")
    if not local:
      continue
    l0 = l0_abs(workvault, local)
    if not l0.exists():
      continue
    body = l0.read_text(encoding="utf-8")
    for pid in extract_outbound_page_ids(body):
      if pid not in known:
        unresolved.add(pid)
  return unresolved
