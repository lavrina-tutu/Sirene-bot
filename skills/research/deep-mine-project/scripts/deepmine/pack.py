"""Pack task context for architect steps G/H (A0)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fail import ValidationError
from .manifest import load_manifest
from .paths import ARCHITECT_BRIEF_TEMPLATE, ARCH_MD, CHARTER_MD, GRAPH_JSON
from .project_config import ProjectConfig
from .source import require_fresh_context


def resolve_task_page_id(
  cfg: ProjectConfig,
  task_id: str,
  *,
  page_id: str | None = None,
) -> str:
  if page_id:
    return str(page_id)
  tasks = cfg.tasks
  if task_id in tasks:
    return str(tasks[task_id])
  raise ValidationError(
    f"task_id '{task_id}' not found in PROJECT.yaml tasks/task_pages; "
    f"use --page-id or add task_pages and collect"
  )


def _brief_skeleton(task_id: str, pack_paths: str) -> str:
  template = ARCHITECT_BRIEF_TEMPLATE.read_text(encoding="utf-8")
  replacements = {
    "{{task_id}}": task_id,
    "{{role_goal}}": f"Анализ пачки `{task_id}` по pack (заполнить координатору).",
    "{{inv_ceil}}": "да",
    "{{inv_pilot}}": "да",
    "{{inv_source}}": "да",
    "{{inv_format}}": "да",
    "{{inv_budget}}": "да",
    "{{inv_dates}}": "да",
    "{{pack_paths}}": pack_paths,
    "{{fields_questions}}": "(заполнить координатору)",
    "{{open_gaps}}": "(заполнить координатору)",
  }
  text = template
  for key, val in replacements.items():
    text = text.replace(key, val)
  return text


def _pack_index_lines(
  task_id: str,
  page_id: str,
  page: dict[str, Any],
  overlay: Path,
  cfg: ProjectConfig,
) -> list[str]:
  lines = [
    f"# Pack: {task_id}",
    "",
    f"- page_id: `{page_id}`",
    f"- title: {page.get('title', '')}",
    f"- version: {page.get('version', '?')}",
    "",
    "## Context SoT (v1.0.0)",
    "",
    f"- `{CHARTER_MD}`",
    f"- `{ARCH_MD}`",
    f"- `{GRAPH_JSON}`",
  ]

  graph_path = overlay / GRAPH_JSON
  if graph_path.is_file():
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    lines.append(f"- GRAPH nodes: {len(graph.get('nodes') or {})}")

  mpp_dir = overlay / "mpp"
  csv_files = sorted(mpp_dir.glob("*__tasks.csv")) if mpp_dir.is_dir() else []
  if csv_files:
    lines.extend(["", "## Plan CSV"])
    for csv in csv_files:
      lines.append(f"- `{csv.relative_to(overlay)}`")
    summary = sorted(mpp_dir.glob("*__summary.json"))
    for path in summary:
      lines.append(f"- `{path.relative_to(overlay)}`")

  extracts_dir = overlay / "docs" / "_inbox" / task_id / "extracts"
  lines.extend(["", "## Extracts"])
  if extracts_dir.is_dir() and any(extracts_dir.glob("*.csv")):
    for csv in sorted(extracts_dir.glob("*.csv")):
      lines.append(f"- `{csv.relative_to(overlay)}`")
  else:
    lines.append("(none yet)")

  return lines


def run_pack(
  cfg: ProjectConfig,
  overlay: Path,
  workvault: Path,
  task_id: str,
  *,
  page_id: str | None = None,
) -> Path:
  resolved_page_id = resolve_task_page_id(cfg, task_id, page_id=page_id)
  manifest = load_manifest(overlay, slug=cfg.slug)
  page = manifest.pages.get(resolved_page_id)
  if page is None:
    raise ValidationError(
      f"page_id {resolved_page_id} not in MANIFEST — добавь в task_pages и collect"
    )

  require_fresh_context(overlay, "charter", slug=cfg.slug)

  pack_dir = overlay / "docs" / "_inbox" / task_id
  pack_dir.mkdir(parents=True, exist_ok=True)
  extracts_dir = pack_dir / "extracts"
  extracts_dir.mkdir(exist_ok=True)

  csv_files = list(extracts_dir.glob("*.csv"))
  if page.get("has_tables") and not csv_files:
    raise ValidationError(
      f"page {resolved_page_id} has_tables but no CSV extract in {extracts_dir} — "
      "run collect --extract-tables"
    )

  pack_md = pack_dir / "PACK.md"
  pack_md.write_text(
    "\n".join(_pack_index_lines(task_id, resolved_page_id, page, overlay, cfg)) + "\n",
    encoding="utf-8",
  )

  path_lines = [
    f"- `{pack_md.relative_to(overlay)}`",
    f"- `{CHARTER_MD}`",
    f"- `{ARCH_MD}`",
    f"- `{GRAPH_JSON}`",
  ]
  if csv_files:
    for csv in sorted(csv_files):
      path_lines.append(f"- extract: `{csv.relative_to(overlay)}`")
  mpp_dir = overlay / "mpp"
  if mpp_dir.is_dir():
    for csv in sorted(mpp_dir.glob("*__tasks.csv")):
      path_lines.append(f"- plan: `{csv.relative_to(overlay)}`")
    for summary in sorted(mpp_dir.glob("*__summary.json")):
      path_lines.append(f"- plan summary: `{summary.relative_to(overlay)}`")
  pack_paths = "\n".join(path_lines)
  brief_md = pack_dir / "BRIEF.md"
  brief_md.write_text(_brief_skeleton(task_id, pack_paths), encoding="utf-8")

  return pack_dir
