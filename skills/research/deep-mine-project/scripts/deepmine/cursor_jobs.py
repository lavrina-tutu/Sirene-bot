"""Cursor agent jobs: compress (F), analyze (G), document (H)."""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .digest_io import (
  archive_history,
  ensure_sources_first,
  leaf_digest_path,
  leaf_slug_page,
  load_all_digests,
  parse_digest,
  theme_digest_path,
  utc_now_iso,
  write_digest,
  write_index_md,
)
from .graph import collect_edges, recompute_backlinks, write_links_md
from .l0 import parse_l0_page
from .paths import COMPRESSOR_PROMPT, l0_abs
from .project_config import ProjectConfig

COMPRESSOR_MODEL = "composer-2.5"
ARCHITECT_MODEL = "cursor-grok-4.6-high"
EXECUTOR_MODEL = "composer-2.5"
SOURCES_HEADER = "## Источники"

_FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


@dataclass
class AgentResult:
  returncode: int
  stdout: str
  stderr: str
  model: str


def run_agent(prompt: str, model: str, cwd: Path) -> AgentResult:
  cmd = ["agent", "-p", prompt, "-f", "--model", model, "--output-format", "json"]
  proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=os.environ.copy())
  return AgentResult(proc.returncode, proc.stdout, proc.stderr, model)


def build_compress_prompt(
  source_desc: str,
  cfg: ProjectConfig,
  existing_slugs: list[str],
) -> str:
  base = COMPRESSOR_PROMPT.read_text(encoding="utf-8")
  themes = ", ".join(cfg.themes)
  slugs = ", ".join(existing_slugs) if existing_slugs else "(none)"
  return (
    f"{base}\n---\n"
    f"Сожми источник: {source_desc}\n"
    f"PROJECT.yaml themes: {themes}\n"
    f"Существующие digest-slug: {slugs}\n"
    "Выход: полный MD digest-файл с YAML frontmatter. "
    "Блок «## Источники» первым в теле. backlinks: []\n"
  )


def build_analyze_prompt(overlay: Path, cfg: ProjectConfig) -> str:
  parts = [
    "Ты — архитектор проекта. Анализируй digest-архив, не сырые L0 Confluence.",
    f"Проект: {cfg.display_name} ({cfg.slug})",
    "",
    "## digest/_index.md",
  ]
  index = overlay / "digest" / "_index.md"
  parts.append(index.read_text(encoding="utf-8") if index.exists() else "(empty)")
  parts.append("\n## digest/themes")
  themes_dir = overlay / "digest" / "themes"
  if themes_dir.is_dir():
    for path in sorted(themes_dir.glob("*.md")):
      parts.append(f"\n### {path.name}\n{path.read_text(encoding='utf-8')}")
  diff = overlay / "docs" / "_inbox" / "diff.md"
  parts.append("\n## docs/_inbox/diff.md")
  parts.append(diff.read_text(encoding="utf-8") if diff.exists() else "(no changes)")
  parts.append(
    "\nЗапрещено использовать Confluence/**/index.md. "
    "Выход: docs/architect-plan.md с выводами и рекомендациями."
  )
  return "\n".join(parts)


def build_document_prompt(overlay: Path) -> str:
  plan = overlay / "docs" / "architect-plan.md"
  text = plan.read_text(encoding="utf-8") if plan.exists() else ""
  return (
    "Ты — исполнитель проектной документации.\n"
    f"Вход architect-plan:\n{text}\n"
    "Создай docs/*.md со status: draft по плану архитектора."
  )


def extract_md_from_agent(result: AgentResult) -> str:
  raw = result.stdout.strip()
  if not raw:
    raise ValueError("empty agent output")
  try:
    data = json.loads(raw)
    if isinstance(data, dict):
      for key in ("result", "text", "content", "message"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
          raw = val.strip()
          break
  except json.JSONDecodeError:
    pass
  if raw.startswith("```"):
    raw = re.sub(r"^```(?:markdown|md)?\s*\n", "", raw)
    raw = re.sub(r"\n```\s*$", "", raw)
  if raw.startswith("---"):
    return raw
  match = _FM_RE.search(raw)
  if match:
    return raw[match.start():]
  return raw


def _sources_block(l0_path: Path, url: str, slug: str) -> str:
  return (
    f"{SOURCES_HEADER}\n\n"
    f"- L0: `{l0_path}`\n"
    f"- Confluence: {url}\n"
    f"- Digest: [[{slug}]]"
  )


def _leaf_frontmatter(
  page_id: str,
  page: dict[str, Any],
  rec,
  slug: str,
) -> dict[str, Any]:
  return {
    "schema_version": "1.0",
    "kind": "leaf",
    "slug": slug,
    "title": rec.title,
    "source_kind": "confluence_page",
    "page_id": page_id,
    "confluence_url": rec.confluence_url,
    "local_path": rec.local_path,
    "version": rec.version,
    "source_sha": rec.content_sha256,
    "parent": rec.parent,
    "children": page.get("children") or [],
    "related": [],
    "backlinks": [],
    "status": "fresh",
    "generated_at": utc_now_iso(),
    "generated_by": COMPRESSOR_MODEL,
  }


def _apply_digest_output(
  path: Path,
  md_text: str,
  sources: str | None = None,
  *,
  fallback_fm: dict[str, Any] | None = None,
) -> dict[str, Any]:
  try:
    fm, body = parse_digest_text(md_text)
  except ValueError:
    if not fallback_fm:
      raise
    fm, body = fallback_fm, md_text
  if sources:
    body = ensure_sources_first(body, sources)
  write_digest(path, fm, body)
  return fm


def parse_digest_text(text: str) -> tuple[dict[str, Any], str]:
  import yaml

  match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
  if not match:
    raise ValueError("digest output missing frontmatter")
  fm = yaml.safe_load(match.group(1)) or {}
  body = text[match.end():]
  return fm, body


def compress_leaf(
  page_id: str,
  page: dict[str, Any],
  overlay: Path,
  workvault: Path,
  cfg: ProjectConfig,
  *,
  dry_run: bool = False,
) -> str | None:
  local_rel = page.get("local_path", "")
  l0 = l0_abs(workvault, local_rel)
  if not l0.exists():
    return None
  slug = page.get("digest_slug") or leaf_slug_page(page_id)
  dest = leaf_digest_path(overlay, page_id)
  existing = sorted(load_all_digests(overlay))
  rec = parse_l0_page(l0, local_path=local_rel)
  source = f"L0 `{local_rel}` (pageId={page_id}, title={rec.title})"
  if dry_run:
    return slug
  old = dest.read_text(encoding="utf-8") if dest.exists() else None
  if old:
    archive_history(overlay, slug, rec.version, rec.content_sha256)
  prompt = build_compress_prompt(source, cfg, existing)
  prompt += f"\nСодержимое L0:\n\n{l0.read_text(encoding='utf-8')}"
  result = run_agent(prompt, COMPRESSOR_MODEL, overlay)
  if result.returncode != 0:
    raise RuntimeError(result.stderr or result.stdout)
  md = extract_md_from_agent(result)
  sources = _sources_block(l0, rec.confluence_url, slug)
  fallback = _leaf_frontmatter(page_id, page, rec, slug)
  _apply_digest_output(dest, md, sources, fallback_fm=fallback)
  page["digest_status"] = "fresh"
  return slug


def compress_plan(overlay: Path, cfg: ProjectConfig, *, dry_run: bool = False) -> None:
  mpp_dir = overlay / "mpp"
  csv_files = sorted(mpp_dir.glob("*__tasks.csv"))
  if not csv_files and dry_run:
    return
  if not csv_files:
    return
  plan_path = mpp_dir / "plan.md"
  existing = sorted(load_all_digests(overlay))
  source = f"CSV в {mpp_dir}: " + ", ".join(p.name for p in csv_files)
  if dry_run:
    return
  parts = [build_compress_prompt(source, cfg, existing)]
  for csv in csv_files[:3]:
    parts.append(f"\n### {csv.name}\n```\n{csv.read_text(encoding='utf-8')[:8000]}\n```")
  result = run_agent("\n".join(parts), COMPRESSOR_MODEL, overlay)
  if result.returncode != 0:
    raise RuntimeError(result.stderr or result.stdout)
  md = extract_md_from_agent(result)
  fallback = {
    "schema_version": "1.0",
    "kind": "mpp",
    "slug": "mpp-plan",
    "title": cfg.mpp.get("project_title", "MPP plan"),
    "source_kind": "mpp",
    "status": "fresh",
    "generated_at": utc_now_iso(),
    "generated_by": COMPRESSOR_MODEL,
    "related": [],
    "backlinks": [],
  }
  try:
    fm, body = parse_digest_text(md)
  except ValueError:
    fm, body = fallback, md
  fm.setdefault("kind", "mpp")
  fm.setdefault("slug", "mpp-plan")
  fm.setdefault("status", "fresh")
  fm.setdefault("generated_by", COMPRESSOR_MODEL)
  write_digest(plan_path, fm, body)


def compress_theme(theme: str, overlay: Path, cfg: ProjectConfig, *, dry_run: bool = False) -> str | None:
  leaves = load_all_digests(overlay)
  themed = [s for s, d in leaves.items() if theme in (d.get("related") or []) or theme in str(d.get("title", "")).lower()]
  if not themed and dry_run:
    return None
  if not themed:
    return None
  dest = theme_digest_path(overlay, theme)
  if dry_run:
    return theme
  bodies = []
  for slug in themed:
    path = overlay / "digest" / "leaves" / f"{slug}.md"
    if path.exists():
      bodies.append(path.read_text(encoding="utf-8"))
  prompt = build_compress_prompt(f"theme:{theme} из листьев {themed}", cfg, list(leaves))
  prompt += "\n\n" + "\n---\n".join(bodies)
  result = run_agent(prompt, COMPRESSOR_MODEL, overlay)
  if result.returncode != 0:
    raise RuntimeError(result.stderr or result.stdout)
  md = extract_md_from_agent(result)
  _apply_digest_output(dest, md)
  return theme


def write_diff(overlay: Path, stale_entries: list[dict[str, str]]) -> Path:
  path = overlay / "docs" / "_inbox" / "diff.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  lines = ["# Refresh diff", "", f"generated_at: {utc_now_iso()}", ""]
  for entry in stale_entries:
    lines.append(f"- {entry['slug']}: {entry.get('old', '?')} → {entry.get('new', '?')}")
  if len(lines) <= 4:
    lines.append("(no stale changes)")
  path.write_text("\n".join(lines) + "\n", encoding="utf-8")
  return path


def rebuild_graph(overlay: Path, manifest, generated_at: str) -> None:
  digests = load_all_digests(overlay)
  recompute_backlinks(digests)
  edges = collect_edges(digests, manifest.pages)
  write_links_md(edges, overlay / "digest" / "links.md", generated_at)
  write_index_md(overlay, digests, generated_at)


def analyze(overlay: Path, cfg: ProjectConfig, *, dry_run: bool = False) -> AgentResult | str:
  prompt = build_analyze_prompt(overlay, cfg)
  if dry_run:
    return prompt
  return run_agent(prompt, ARCHITECT_MODEL, overlay)


def document(overlay: Path, *, dry_run: bool = False) -> AgentResult | str:
  prompt = build_document_prompt(overlay)
  if dry_run:
    return prompt
  return run_agent(prompt, EXECUTOR_MODEL, overlay)
