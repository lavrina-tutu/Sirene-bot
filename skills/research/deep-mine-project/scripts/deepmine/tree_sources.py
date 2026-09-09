"""TREE.md, SOURCES.md, and LINKS table writers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Manifest


def _pmo_seed_ids(manifest: Manifest, pmo_seeds: list[dict[str, str]] | None) -> set[str]:
  if pmo_seeds:
    return {str(s["page_id"]) for s in pmo_seeds}
  return {pid for pid, p in manifest.pages.items() if p.get("space") == "PMO"}


def _tree_lines(
  pages: dict[str, dict[str, Any]],
  page_id: str,
  depth: int = 0,
) -> list[str]:
  page = pages.get(page_id)
  if not page:
    return []
  indent = "  " * depth
  title = page.get("title") or page_id
  version = page.get("version", "?")
  url = page.get("confluence_url", "")
  lines = [
    f"{indent}- {title}",
    f"{indent}  - id={page_id}",
    f"{indent}  - [открыть]({url}) · версия {version}",
  ]
  for child_id in sorted(page.get("children") or [], key=lambda c: (pages.get(c) or {}).get("title", c)):
    lines.extend(_tree_lines(pages, child_id, depth + 1))
  return lines


def write_tree_md(
  manifest: Manifest,
  path: Path,
  *,
  cfg_root: str | None,
  pmo_seeds: list[dict[str, str]] | None = None,
) -> None:
  pages = manifest.pages
  roots: list[str] = []
  if cfg_root and cfg_root in pages:
    roots.append(cfg_root)
  pmo_ids = _pmo_seed_ids(manifest, pmo_seeds)
  for pid in sorted(pmo_ids):
    if pid not in roots:
      roots.append(pid)
  if not roots:
    roots = [pid for pid, p in pages.items() if not p.get("parent") or p.get("parent") not in pages]

  lines = [
    f"# {manifest.slug} — карта архива (Confluence)",
    "",
    "## Сводка",
    f"- Страниц в архиве: **{len(pages)}**",
    f"- Overlay: `{path.parent}`",
    "",
    "## Дерево страниц (иерархия parent→children)",
    "",
  ]
  for root_id in roots:
    root = pages.get(root_id, {})
    lines.append(f"### {root.get('title', root_id)} (id={root_id})")
    lines.append("")
    for child_id in sorted(root.get("children") or [], key=lambda c: (pages.get(c) or {}).get("title", c)):
      lines.extend(_tree_lines(pages, child_id, depth=0))
    lines.append("")

  path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_tree_from_graph(
  graph: dict[str, Any],
  path: Path,
  *,
  cfg_root: str | None,
) -> None:
  nodes = graph.get("nodes") or {}
  edges = graph.get("edges") or []
  children_map: dict[str, list[str]] = {}
  for edge in edges:
    if edge.get("type") == "child":
      children_map.setdefault(edge.get("from"), []).append(edge.get("to"))

  def _lines(page_id: str, depth: int = 0) -> list[str]:
    node = nodes.get(page_id, {})
    indent = "  " * depth
    title = node.get("title") or page_id
    kind = node.get("kind", "page")
    lines = [f"{indent}- {title} (id={page_id}, kind={kind})"]
    for child_id in sorted(children_map.get(page_id, [])):
      lines.extend(_lines(child_id, depth + 1))
    return lines

  slug = graph.get("slug", "")
  lines = [
    f"# {slug} — карта архива (GRAPH)",
    "",
    f"generated_at: {graph.get('generated_at', '')}",
    "",
    "## Дерево",
    "",
  ]
  roots = [cfg_root] if cfg_root and cfg_root in nodes else []
  if not roots:
    roots = sorted(nodes.keys())[:5]
  for root_id in roots:
    lines.extend(_lines(root_id))
    lines.append("")
  path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_links_table(graph: dict[str, Any], path: Path) -> None:
  lines = [
    "# LINKS.md — граф связей",
    "",
    f"generated_at: {graph.get('generated_at', '')}",
    "",
    "from,to,edge",
  ]
  for edge in graph.get("edges") or []:
    lines.append(f"{edge.get('from')},{edge.get('to')},{edge.get('type')}")
  path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sources_md(manifest: Manifest, path: Path) -> None:
  lines = [
    f"# SOURCES.md — карта источников {manifest.slug}",
    "",
    "| pageId | Title | Версия | Локальный путь | Wiki |",
    "|---|---|---|---|---|",
  ]
  for page_id in sorted(manifest.pages.keys(), key=lambda x: int(x) if x.isdigit() else x):
    page = manifest.pages[page_id]
    title = (page.get("title") or "").replace("|", "\\|")
    version = page.get("version", "?")
    local_path = page.get("local_path", "")
    url = page.get("confluence_url", "")
    lines.append(
      f"| {page_id} | {title} | v{version} | `{local_path}` | [открыть]({url}) |"
    )
  path.write_text("\n".join(lines) + "\n", encoding="utf-8")
