"""sources_sha computation for context layer C (J8)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .facts_run import facts_sha
from .graph_build import graph_fingerprint
from .paths import PRO_CATALOG, l0_abs
from .project_config import ProjectConfig


def catalog_version() -> str:
  if PRO_CATALOG.is_file():
    return hashlib.sha256(PRO_CATALOG.read_bytes()).hexdigest()[:16]
  return "missing"


def _body_shas(page_ids: list[str], pages: dict[str, Any], workvault: Path) -> list[str]:
  shas: list[str] = []
  for page_id in sorted(page_ids):
    page = pages.get(page_id) or {}
    local = page.get("local_path")
    if not local:
      shas.append(f"{page_id}:missing")
      continue
    l0 = l0_abs(workvault, local)
    if l0.is_file():
      shas.append(hashlib.sha256(l0.read_bytes()).hexdigest())
    else:
      shas.append(f"{page_id}:missing")
  return shas


def compute_sources_sha(
  kind: str,
  cfg: ProjectConfig,
  graph: dict[str, Any],
  facts: dict[str, Any],
  pages: dict[str, Any],
  workvault: Path,
) -> str:
  if kind == "charter":
    body_ids = cfg.contexts.charter_body_page_ids
  else:
    body_ids = cfg.contexts.architecture_body_page_ids

  payload = {
    "kind": kind,
    "graph_fp": graph_fingerprint(graph),
    "facts_sha": facts.get("facts_sha") or facts_sha(facts),
    "body_shas": _body_shas(body_ids, pages, workvault),
    "catalog_version": catalog_version(),
    "themes": cfg.contexts.architecture_themes if kind == "architecture" else [],
  }
  return hashlib.sha256(
    json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
  ).hexdigest()
