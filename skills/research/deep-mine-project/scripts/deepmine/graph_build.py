"""Build GRAPH.json from L0 pages without LLM."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .follow import classify_outbound, extract_non_page_links, parse_follow_outbound, stub_reason
from .graph import extract_outbound_page_ids
from .l0 import parse_l0_page
from .models import GraphEdge, GraphNode, VALID_EDGE_TYPES
from .paths import GRAPH_JSON, LINKS_MD, l0_abs
from .project_config import ProjectConfig


def utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def seed_ids(cfg: ProjectConfig) -> set[str]:
  ids = {cfg.root_page_id}
  for seed in cfg.pmo_seeds:
    ids.add(str(seed["page_id"]))
  for task in cfg.task_pages:
    ids.add(str(task["page_id"]))
  if cfg.gantt_page_id:
    ids.add(cfg.gantt_page_id)
  return ids


def load_l0_nodes(
  pages: dict[str, dict[str, Any]],
  workvault: Path,
) -> dict[str, GraphNode]:
  nodes: dict[str, GraphNode] = {}
  for page_id, page in pages.items():
    local_rel = page.get("local_path")
    if not local_rel:
      continue
    l0 = l0_abs(workvault, local_rel)
    if not l0.exists():
      continue
    rec = parse_l0_page(l0, local_path=local_rel)
    nodes[page_id] = GraphNode(
      page_id=page_id,
      title=rec.title,
      space=rec.space,
      kind="page",
      local_path=local_rel,
      version=rec.version,
      content_sha256=rec.content_sha256,
    )
  return nodes


def children_from_l0_or_api(
  page_id: str,
  page: dict[str, Any],
  workvault: Path,
) -> list[str]:
  local_rel = page.get("local_path")
  if local_rel:
    l0 = l0_abs(workvault, local_rel)
    if l0.exists():
      rec = parse_l0_page(l0, local_path=local_rel)
      if rec.children:
        return rec.children
  return [str(c) for c in (page.get("children") or [])]


def outbound_from_body(
  page_id: str,
  body: str,
) -> set[str]:
  return extract_outbound_page_ids(body)


def pull_follow_targets(
  cfg: ProjectConfig,
  pages: dict[str, dict[str, Any]],
  workvault: Path,
  *,
  dry_run: bool = False,
) -> tuple[set[str], list[str]]:
  """Return (new_page_ids_to_pull, warnings)."""
  policy = cfg.follow
  if not policy.enabled:
    return set(), []
  known_spaces = set(policy.allowed_spaces)
  seeds = seed_ids(cfg)
  to_pull: set[str] = set()
  warnings: list[str] = []
  pull_count = 0
  for page_id in seeds:
    page = pages.get(page_id)
    if not page:
      continue
    local_rel = page.get("local_path")
    if not local_rel:
      continue
    l0 = l0_abs(workvault, local_rel)
    if not l0.exists():
      continue
    rec = parse_l0_page(l0, local_path=local_rel)
    for target_id in parse_follow_outbound(rec.body):
      if target_id in pages or target_id in to_pull:
        continue
      space = None
      title = None
      action, reason = classify_outbound(
        target_id,
        space=space,
        title=title,
        policy=policy,
        known_spaces=known_spaces,
        pull_count=pull_count,
      )
      if action == "pull" and not dry_run:
        from .confluence_pull import run_pull

        run_pull(target_id, recursive=False, resync=True)
        to_pull.add(target_id)
        pull_count += 1
      elif action == "stub":
        warnings.append(f"stub {target_id}: {reason}")
  return to_pull, warnings


def build_graph(
  cfg: ProjectConfig,
  pages: dict[str, dict[str, Any]],
  workvault: Path,
  *,
  extra_warnings: list[str] | None = None,
) -> dict[str, Any]:
  seeds = seed_ids(cfg)
  nodes: dict[str, GraphNode] = {}
  edges: list[GraphEdge] = []
  warnings = list(extra_warnings or [])

  for page_id, page in pages.items():
    local_rel = page.get("local_path")
    if local_rel and l0_abs(workvault, local_rel).exists():
      rec = parse_l0_page(l0_abs(workvault, local_rel), local_path=local_rel)
      nodes[page_id] = GraphNode(
        page_id=page_id,
        title=rec.title,
        space=rec.space,
        kind="page",
        seed=page_id in seeds,
        local_path=local_rel,
        version=rec.version,
        content_sha256=rec.content_sha256,
      )
    else:
      nodes[page_id] = GraphNode(
        page_id=page_id,
        title=str(page.get("title") or page_id),
        space=str(page.get("space") or ""),
        kind="stub",
        seed=page_id in seeds,
        stub_reason="missing L0",
      )

  for page_id in seeds:
    if page_id in nodes:
      edges.append(GraphEdge(page_id, page_id, "seed"))

  for page_id, page in pages.items():
    parent = page.get("parent")
    if parent and str(parent) in nodes:
      edges.append(GraphEdge(str(parent), page_id, "child"))
      edges.append(GraphEdge(page_id, str(parent), "parent"))

  for page_id, page in pages.items():
    local_rel = page.get("local_path")
    if not local_rel:
      continue
    l0 = l0_abs(workvault, local_rel)
    if not l0.exists():
      continue
    rec = parse_l0_page(l0, local_path=local_rel)
    for target_id in outbound_from_body(page_id, rec.body):
      if target_id in nodes:
        edges.append(GraphEdge(page_id, target_id, "links_to"))
    for frag, kind in extract_non_page_links(rec.body):
      edges.append(GraphEdge(page_id, frag[:40], "links_to", target_kind=kind))

  return {
    "schema_version": "1.0",
    "slug": cfg.slug,
    "generated_at": utc_now_iso(),
    "follow_policy": cfg.follow.mode,
    "warnings": warnings,
    "nodes": {pid: node.to_dict() for pid, node in nodes.items()},
    "edges": [e.to_dict() for e in edges if e.type in VALID_EDGE_TYPES],
  }


def graph_fingerprint(graph: dict[str, Any]) -> str:
  payload = {
    "nodes": graph.get("nodes") or {},
    "edges": sorted(
      (e.get("from"), e.get("to"), e.get("type"))
      for e in (graph.get("edges") or [])
    ),
  }
  return hashlib.sha256(
    json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
  ).hexdigest()


def write_graph_json(graph: dict[str, Any], overlay: Path) -> Path:
  path = overlay / GRAPH_JSON
  path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  return path


def write_links_md(graph: dict[str, Any], overlay: Path) -> Path:
  path = overlay / LINKS_MD
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
  return path


def run_graph(
  cfg: ProjectConfig,
  overlay: Path,
  workvault: Path,
  *,
  dry_run: bool = False,
) -> dict[str, Any]:
  from .manifest import load_manifest, rebuild_all

  manifest = load_manifest(overlay, slug=cfg.slug)
  extra_warnings: list[str] = []
  if cfg.follow.enabled and not dry_run:
    pulled, warnings = pull_follow_targets(cfg, manifest.pages, workvault, dry_run=dry_run)
    extra_warnings.extend(warnings)
    if pulled:
      manifest = rebuild_all(
        overlay, workvault,
        slug=cfg.slug, root_page_id=cfg.root_page_id, pmo_seeds=cfg.pmo_seeds,
      )
  graph = build_graph(cfg, manifest.pages, workvault, extra_warnings=extra_warnings)
  if not dry_run:
    write_graph_json(graph, overlay)
    write_links_md(graph, overlay)
    from .tree_sources import write_tree_from_graph

    write_tree_from_graph(graph, overlay / "TREE.md", cfg_root=cfg.root_page_id)
  return graph
