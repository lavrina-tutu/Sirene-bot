"""Render charter/architecture context markdown."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .llm_json import CONTEXT_MODEL


def utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def render_frontmatter(
  kind: str,
  slug: str,
  sources_sha: str,
  batches: list[int] | list[str],
) -> str:
  lines = [
    "---",
    'schema_version: "1.0"',
    f"kind: {kind}",
    f"slug: {slug}",
    "status: fresh",
    f'sources_sha: "{sources_sha}"',
    f"generated_at: {utc_now_iso()}",
    f"generated_by: {CONTEXT_MODEL}",
    f"batches: {json.dumps(batches)}",
    "---",
  ]
  return "\n".join(lines)


def render_sources_block(
  graph: dict[str, Any],
  body_page_ids: list[str],
) -> str:
  lines = [
    "## Источники",
    "",
    f"- GRAPH.json nodes: {len(graph.get('nodes') or {})}",
    f"- Full bodies: {', '.join(body_page_ids)}",
    "",
  ]
  return "\n".join(lines)


def render_sections(batch_results: list[dict[str, Any]]) -> str:
  lines: list[str] = []
  for batch in batch_results:
    for section in batch.get("sections") or []:
      field = section.get("field") or "?"
      content = section.get("content") or "нет в источниках"
      page_id = section.get("source_page_id") or "?"
      lines.append(f"## {field}")
      lines.append("")
      lines.append(f"{content}")
      lines.append("")
      lines.append(f"*source pageId: {page_id}*")
      lines.append("")
  return "\n".join(lines)


def render_context_md(
  kind: str,
  slug: str,
  sources_sha: str,
  batches: list[int] | list[str],
  graph: dict[str, Any],
  body_page_ids: list[str],
  batch_results: list[dict[str, Any]],
) -> str:
  fm = render_frontmatter(kind, slug, sources_sha, batches)
  body = render_sources_block(graph, body_page_ids) + "\n" + render_sections(batch_results)
  return fm + "\n" + body
