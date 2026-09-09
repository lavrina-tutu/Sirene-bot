"""Prompt building and narrow input for context synthesis."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .l0 import parse_l0_page
from .paths import PRO_CATALOG, SKILL_ROOT, l0_abs
from .project_config import ProjectConfig


def load_pro_catalog() -> list[dict[str, str]]:
  if not PRO_CATALOG.is_file():
    return []
  fields: list[dict[str, str]] = []
  for line in PRO_CATALOG.read_text(encoding="utf-8").splitlines():
    if line.startswith("|") and "---" not in line:
      parts = [p.strip() for p in line.split("|") if p.strip()]
      if len(parts) >= 2 and parts[0] not in ("#", "Поле"):
        fields.append({"field": parts[0], "description": parts[1] if len(parts) > 1 else ""})
  return fields


def narrow_input(
  kind: str,
  cfg: ProjectConfig,
  graph: dict[str, Any],
  facts: dict[str, Any],
  pages: dict[str, Any],
  workvault: Path,
) -> str:
  """Full bodies only for body_page_ids; other nodes as headers; no digest/leaves."""
  if kind == "charter":
    body_ids = set(cfg.contexts.charter_body_page_ids)
  else:
    body_ids = set(cfg.contexts.architecture_body_page_ids)

  nodes = graph.get("nodes") or {}
  parts = [
    "# Narrow input",
    "",
    "## facts.json (summary)",
    json.dumps({
      "sums": facts.get("script_only", {}).get("sums") or [],
      "dates_count": len(facts.get("script_only", {}).get("dates") or []),
    }, ensure_ascii=False, indent=2),
    "",
    "## Nodes",
  ]
  for page_id, node in sorted(nodes.items(), key=lambda x: x[0]):
    title = node.get("title") or page_id
    space = node.get("space") or ""
    kind_node = node.get("kind") or "page"
    if page_id in body_ids:
      local = node.get("local_path")
      body = ""
      if local and l0_abs(workvault, local).is_file():
        rec = parse_l0_page(l0_abs(workvault, local), local_path=local)
        body = rec.body[:8000]
      parts.append(f"### FULL pageId={page_id} title={title} space={space}")
      parts.append(body)
    else:
      parts.append(f"- pageId={page_id} title={title} space={space} kind={kind_node}")
  parts.append("")
  parts.append("ЗАПРЕЩЕНО: digest/leaves, digest/themes.")
  return "\n".join(parts)


def batch_prompt(
  kind: str,
  batch_num: int,
  narrow: str,
  fields: list[str],
) -> str:
  prompt_file = SKILL_ROOT / "references" / (
    "charter-batch-prompt.md" if kind == "charter" else "architecture-batch-prompt.md"
  )
  base = prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""
  return (
    f"{base}\n\n"
    f"kind: {kind}\n"
    f"batch: {batch_num}\n"
    f"fields: {', '.join(fields)}\n\n"
    f"{narrow}\n"
  )
