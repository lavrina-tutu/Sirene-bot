"""Cursor agent jobs: compress (F), analyze (G), document (H)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
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
from .digest_validate import rejection_reason, validate_digest_body
from .fail import DigestError, ValidationError, digest_failed
from .llm_json import COMPRESSOR_LLM_SLUG, call_text
from .paths import ARCH_MD, CHARTER_MD, COMPRESSOR_PROMPT, GRAPH_JSON, l0_abs
from .project_config import ProjectConfig
from .source import require_fresh_context, require_fresh_digest

COMPRESSOR_MODEL = "deepseek-v4-flash-0731"
ARCHITECT_MODEL = "cursor-grok-4.6-high"
EXECUTOR_MODEL = "composer-2.5"
SOURCES_HEADER = "## Источники"


def _ensure_hermes_on_path() -> None:
  _HERMES = Path.home() / "hermes-agent"
  if str(_HERMES) not in sys.path:
    sys.path.insert(0, str(_HERMES))

_FM_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


@dataclass
class AgentResult:
  returncode: int
  stdout: str
  stderr: str
  model: str


def run_agent(
  prompt: str,
  model: str,
  cwd: Path,
  *,
  source_mode: str | None = None,
  mode: str | None = None,
) -> AgentResult:
  cmd = ["agent", "-p", prompt, "-f", "--model", model, "--output-format", "json"]
  if mode:
    cmd.extend(["--mode", mode])
  env = os.environ.copy()
  if source_mode:
    env["DEEP_MINE_SOURCE_MODE"] = source_mode
  proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
  return AgentResult(proc.returncode, proc.stdout, proc.stderr, model)


def compress_with_llm(prompt: str, overlay: Path, *, timeout: float = 300.0) -> str:
  if os.environ.get("DEEP_MINE_COMPRESSOR", "hermes") == "cursor":
    result = run_agent(prompt, "composer-2.5", overlay, source_mode="l0_allowed", mode="ask")
    if result.returncode != 0:
      raise RuntimeError(result.stderr or result.stdout)
    return extract_md_from_agent(result)
  return call_text(prompt, timeout=timeout)


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


_CONTEXT_ONLY_LINE = (
  "Факты только из charter-context.md, architecture-context.md, GRAPH.json и pack extracts; "
  "Confluence/**/index.md и WorkVault/Confluence/** запрещены. digest/leaves не SoT."
)


def build_analyze_prompt(
  overlay: Path,
  cfg: ProjectConfig,
  *,
  pack_dir: Path | None = None,
  full_archive: bool = False,
) -> str:
  if pack_dir is not None:
    assert_brief_ready(pack_dir)
    parts = [
      "Ты — архитектор проекта. Анализируй только каталог pack, не весь overlay.",
      f"Проект: {cfg.display_name} ({cfg.slug})",
      "",
      f"## {pack_dir / 'PACK.md'}",
    ]
    pack_md = pack_dir / "PACK.md"
    parts.append(pack_md.read_text(encoding="utf-8") if pack_md.exists() else "(missing PACK.md)")
    brief_md = pack_dir / "BRIEF.md"
    parts.append(f"\n## {brief_md}")
    parts.append(brief_md.read_text(encoding="utf-8") if brief_md.exists() else "(missing BRIEF.md)")
    parts.append(
      f"\nЧитай контексты по путям из PACK.md — не инлайнить полные L0 в ответ.\n"
      f"{_CONTEXT_ONLY_LINE}\n"
      "Выход: docs/architect-plan.md с выводами и рекомендациями."
    )
    return "\n".join(parts)

  if not full_archive:
    raise ValueError("build_analyze_prompt requires pack_dir or full_archive=True")

  parts = [
    "Ты — архитектор проекта. Анализируй контексты v1.0.0, не сырые L0 Confluence.",
    f"Проект: {cfg.display_name} ({cfg.slug})",
    "",
    f"## {CHARTER_MD}",
  ]
  charter = overlay / CHARTER_MD
  parts.append(charter.read_text(encoding="utf-8")[:12000] if charter.exists() else "(missing)")
  parts.append(f"\n## {ARCH_MD}")
  arch = overlay / ARCH_MD
  parts.append(arch.read_text(encoding="utf-8")[:12000] if arch.exists() else "(missing)")
  parts.append(f"\n## {GRAPH_JSON}")
  graph = overlay / GRAPH_JSON
  parts.append(graph.read_text(encoding="utf-8")[:4000] if graph.exists() else "(missing)")
  diff = overlay / "docs" / "_inbox" / "diff.md"
  parts.append("\n## docs/_inbox/diff.md")
  parts.append(diff.read_text(encoding="utf-8") if diff.exists() else "(no changes)")
  parts.append(
    f"\n{_CONTEXT_ONLY_LINE}\n"
    "Выход: docs/architect-plan.md с выводами и рекомендациями."
  )
  return "\n".join(parts)


_INVARIANT_ROW = re.compile(r"^\|\s*\d+\s*\|", re.MULTILINE)
_INVARIANT_STATUS = re.compile(r"\|\s*(да|нет|нп)\s*\|", re.IGNORECASE)


def assert_brief_ready(pack_dir: Path) -> None:
  brief = pack_dir / "BRIEF.md"
  if not brief.is_file():
    raise ValueError(f"BRIEF.md missing in {pack_dir}")
  text = brief.read_text(encoding="utf-8")
  rows = _INVARIANT_ROW.findall(text)
  if len(rows) < 6:
    raise ValueError("BRIEF.md checklist invariants incomplete (need 6 filled rows)")
  statuses = _INVARIANT_STATUS.findall(text)
  if len(statuses) < 6:
    raise ValueError("BRIEF.md checklist invariants must be да/нет/нп for each row")
  for status in statuses[:6]:
    if status.lower() not in ("да", "нет", "нп"):
      raise ValueError("BRIEF.md checklist has empty invariant status")


def _page_ids_from_plan_and_packs(overlay: Path) -> set[str]:
  ids: set[str] = set()
  plan = overlay / "docs" / "architect-plan.md"
  if plan.is_file():
    text = plan.read_text(encoding="utf-8")
    ids.update(re.findall(r"page_id:\s*`?(\d+)`?", text))
    ids.update(re.findall(r"\bp(\d{6,})\b", text))
  inbox = overlay / "docs" / "_inbox"
  if inbox.is_dir():
    for pack_md in inbox.glob("*/PACK.md"):
      text = pack_md.read_text(encoding="utf-8")
      match = re.search(r"page_id:\s*`(\d+)`", text)
      if match:
        ids.add(match.group(1))
  return ids


def document_preflight(overlay: Path, cfg: ProjectConfig, manifest) -> None:
  plan = overlay / "docs" / "architect-plan.md"
  if not plan.is_file():
    raise ValidationError("architect-plan.md missing — run analyze first")
  require_fresh_context(overlay, "charter", slug=cfg.slug)
  require_fresh_context(overlay, "architecture", slug=cfg.slug)


def build_document_prompt(overlay: Path, cfg: ProjectConfig) -> str:
  plan = overlay / "docs" / "architect-plan.md"
  plan_text = plan.read_text(encoding="utf-8")
  charter = overlay / CHARTER_MD
  arch = overlay / ARCH_MD
  charter_text = charter.read_text(encoding="utf-8")[:8000] if charter.exists() else "(missing)"
  arch_text = arch.read_text(encoding="utf-8")[:8000] if arch.exists() else "(missing)"
  return (
    "Ты — исполнитель проектной документации.\n"
    f"Вход architect-plan:\n{plan_text}\n\n"
    f"## {CHARTER_MD}\n{charter_text}\n\n"
    f"## {ARCH_MD}\n{arch_text}\n\n"
    f"{_CONTEXT_ONLY_LINE}\n"
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


def _validate_and_apply_digest(
  path: Path,
  md_text: str,
  sources: str | None,
  *,
  fallback_fm: dict[str, Any] | None = None,
  l0_body: str | None = None,
) -> tuple[dict[str, Any], str]:
  fm = _apply_digest_output(path, md_text, sources, fallback_fm=fallback_fm)
  _, body = parse_digest(path)
  status = validate_digest_body(body, l0_body=l0_body)
  if status == "rejected":
    fm["status"] = "rejected"
    write_digest(path, fm, body)
    digest_failed(rejection_reason(body, l0_body=l0_body))
  fm["status"] = "fresh"
  write_digest(path, fm, body)
  return fm, status


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
  md = extract_md_from_agent(
    AgentResult(0, compress_with_llm(prompt, overlay), "", COMPRESSOR_MODEL)
  )
  sources = _sources_block(l0, rec.confluence_url, slug)
  fallback = _leaf_frontmatter(page_id, page, rec, slug)
  try:
    _validate_and_apply_digest(dest, md, sources, fallback_fm=fallback, l0_body=rec.body)
    page["digest_status"] = "fresh"
  except DigestError:
    page["digest_status"] = "rejected"
    raise
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
  summaries = sorted(mpp_dir.glob("*__summary.json"))
  source = f"CSV в {mpp_dir}: " + ", ".join(p.name for p in csv_files)
  if summaries:
    source += "; summary: " + ", ".join(p.name for p in summaries)
  if dry_run:
    return
  parts = [build_compress_prompt(source, cfg, existing)]
  rate = cfg.rate_rub_per_hour
  parts.append(
    "\nПравило стоимости: трудозатраты из блока «Итого» L0-страницы плана "
    f"(не сумма листьев Gantt JSON) × {rate} ₽/чел-час. "
    "Длительность периода — из «Итого»; ИСР, даты задач и ресурсы — из CSV/JSON.\n"
  )
  for summary in summaries[:2]:
    parts.append(f"\n### {summary.name}\n```\n{summary.read_text(encoding='utf-8')[:4000]}\n```")
  for csv in csv_files[:3]:
    parts.append(f"\n### {csv.name}\n```\n{csv.read_text(encoding='utf-8')[:8000]}\n```")
  md = extract_md_from_agent(
    AgentResult(0, compress_with_llm("\n".join(parts), overlay), "", COMPRESSOR_MODEL)
  )
  title = cfg.plan.get("project_title") or "Project plan"
  kind = "gantt" if summaries or cfg.plan.get("source") == "gantt" else "mpp"
  fallback = {
    "schema_version": "1.0",
    "kind": kind,
    "slug": "plan",
    "title": title,
    "source_kind": kind,
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
  fm.setdefault("kind", kind)
  fm.setdefault("slug", "plan")
  fm.setdefault("status", "fresh")
  fm.setdefault("generated_by", COMPRESSOR_MODEL)
  write_digest(plan_path, fm, body)


def compress_theme(theme: str, overlay: Path, cfg: ProjectConfig, *, dry_run: bool = False) -> str | None:
  """Build theme digest from leaf digests only (never raw L0)."""
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
  md = extract_md_from_agent(
    AgentResult(0, compress_with_llm(prompt, overlay), "", COMPRESSOR_MODEL)
  )
  try:
    _validate_and_apply_digest(dest, md, l0_body=None)
  except DigestError:
    raise
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


def analyze(
  overlay: Path,
  cfg: ProjectConfig,
  *,
  pack_dir: Path | None = None,
  full_archive: bool = False,
  dry_run: bool = False,
) -> AgentResult | str:
  prompt = build_analyze_prompt(overlay, cfg, pack_dir=pack_dir, full_archive=full_archive)
  if dry_run:
    return prompt
  return run_agent(prompt, ARCHITECT_MODEL, overlay, source_mode="context_only")


def document(overlay: Path, cfg: ProjectConfig, *, dry_run: bool = False) -> AgentResult | str:
  prompt = build_document_prompt(overlay, cfg)
  if dry_run:
    return prompt
  return run_agent(prompt, EXECUTOR_MODEL, overlay, source_mode="context_only")
