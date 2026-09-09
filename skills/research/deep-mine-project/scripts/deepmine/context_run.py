"""Run context synthesis (layer C) with J8 idempotency."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .context_batches import run_architecture_batches, run_charter_batches
from .context_render import render_context_md
from .context_validate import raise_on_errors, validate_assembled_md
from .facts_run import run_facts
from .graph_build import run_graph
from .manifest import load_manifest, save_manifest
from .paths import ARCH_MD, CHARTER_MD
from .project_config import ProjectConfig
from .sources_sha import compute_sources_sha


def _read_existing_sha(path: Path) -> str | None:
  if not path.is_file():
    return None
  text = path.read_text(encoding="utf-8")
  match = re.search(r'^sources_sha:\s*["\']?([a-f0-9]+)', text, re.MULTILINE)
  return match.group(1) if match else None


def _context_path(overlay: Path, kind: str) -> Path:
  return overlay / (CHARTER_MD if kind == "charter" else ARCH_MD)


def run_context(
  cfg: ProjectConfig,
  overlay: Path,
  workvault: Path,
  kind: str,
  *,
  skip_llm: bool = False,
  dry_run: bool = False,
  llm_calls: list[str] | None = None,
) -> dict[str, Any]:
  graph_path = overlay / "GRAPH.json"
  facts_path = overlay / "facts.json"
  if not graph_path.is_file():
    graph = run_graph(cfg, overlay, workvault, dry_run=dry_run)
  else:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
  if not facts_path.is_file():
    manifest = load_manifest(overlay, slug=cfg.slug)
    facts = run_facts(cfg, overlay, workvault, manifest.pages, skip_llm=skip_llm, dry_run=dry_run)
  else:
    facts = json.loads(facts_path.read_text(encoding="utf-8"))

  manifest = load_manifest(overlay, slug=cfg.slug)
  sources_sha = compute_sources_sha(kind, cfg, graph, facts, manifest.pages, workvault)
  out_path = _context_path(overlay, kind)

  existing_sha = _read_existing_sha(out_path)
  if existing_sha == sources_sha and out_path.is_file() and not dry_run:
    return {
      "kind": kind,
      "path": str(out_path),
      "sources_sha": sources_sha,
      "llm_calls": 0,
      "skipped": True,
    }

  if skip_llm or dry_run:
    batch_results = (
      run_charter_batches(cfg, overlay, graph, facts, manifest.pages, workvault, dry_run=True)
      if kind == "charter"
      else run_architecture_batches(cfg, overlay, graph, facts, manifest.pages, workvault, dry_run=True)
    )
    return {"kind": kind, "sources_sha": sources_sha, "batches": len(batch_results), "dry_run": True}

  if kind == "charter":
    batch_results = run_charter_batches(
      cfg, overlay, graph, facts, manifest.pages, workvault, llm_calls=llm_calls,
    )
    batches = list(range(1, 6))
    body_ids = cfg.contexts.charter_body_page_ids
  else:
    batch_results = run_architecture_batches(
      cfg, overlay, graph, facts, manifest.pages, workvault, llm_calls=llm_calls,
    )
    batches = cfg.contexts.architecture_themes
    body_ids = cfg.contexts.architecture_body_page_ids

  md = render_context_md(kind, cfg.slug, sources_sha, batches, graph, body_ids, batch_results)
  errors = validate_assembled_md(md.split("---", 2)[-1] if md.startswith("---") else md)
  raise_on_errors(kind, overlay, md[:500], errors)

  out_path.write_text(md + "\n", encoding="utf-8")
  manifest.contexts[kind] = {
    "path": out_path.name,
    "sha": sources_sha,
    "status": "fresh",
    "sources_sha": sources_sha,
  }
  save_manifest(manifest, overlay)

  return {
    "kind": kind,
    "path": str(out_path),
    "sources_sha": sources_sha,
    "llm_calls": len(llm_calls or []),
    "batches": len(batch_results),
  }
