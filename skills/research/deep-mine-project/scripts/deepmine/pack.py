"""Pack task context for architect steps G/H (A0)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .digest_io import leaf_digest_path, leaf_slug_page, parse_digest, theme_digest_path
from .digest_validate import l0_has_table
from .fail import ValidationError
from .manifest import load_manifest
from .paths import ARCHITECT_BRIEF_TEMPLATE, l0_abs
from .project_config import ProjectConfig
from .table_extract import extract_tables


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


def _leaf_related_themes(overlay: Path, page_id: str) -> set[str]:
  """Themes linked from the task leaf digest frontmatter (built from leaves, not L0)."""
  digest_path = leaf_digest_path(overlay, page_id)
  if not digest_path.is_file():
    return set()
  fm, _ = parse_digest(digest_path)
  return {str(t) for t in (fm.get("related") or [])}


def _pack_theme_entries(
  cfg: ProjectConfig,
  overlay: Path,
  page_id: str,
) -> list[tuple[str, Path, str]]:
  """Fresh theme digests relevant to pack: cfg.themes ∩ leaf.related; missing/rejected skipped."""
  configured = set(cfg.themes)
  leaf_related = _leaf_related_themes(overlay, page_id)
  if leaf_related:
    candidates = configured & leaf_related
  else:
    candidates = configured

  entries: list[tuple[str, Path, str]] = []
  for theme in sorted(candidates):
    path = theme_digest_path(overlay, theme)
    if not path.is_file():
      continue
    fm, _ = parse_digest(path)
    status = str(fm.get("status") or "unknown")
    if status == "rejected":
      continue
    entries.append((theme, path, status))
  return entries


def _pack_index_lines(
  task_id: str,
  page_id: str,
  page: dict[str, Any],
  overlay: Path,
  cfg: ProjectConfig,
) -> list[str]:
  slug = page.get("digest_slug") or leaf_slug_page(page_id)
  digest_path = overlay / "digest" / "leaves" / f"{slug}.md"
  digest_status = page.get("digest_status", "missing")
  if digest_path.exists():
    fm, _ = parse_digest(digest_path)
    digest_status = str(fm.get("status") or digest_status)

  lines = [
    f"# Pack: {task_id}",
    "",
    f"- page_id: `{page_id}`",
    f"- title: {page.get('title', '')}",
    f"- version: {page.get('version', '?')}",
    f"- local_path: `{page.get('local_path', '')}`",
    f"- digest: `digest/leaves/{slug}.md` (status: {digest_status})",
    "",
    "## Theme digests",
    "",
    "Theme digests built from **leaf** compress (not raw L0). "
    "Same «no journal» contract as leaf digests. "
    "Missing theme file is OK (not compressed yet); `rejected` themes omitted.",
  ]
  theme_entries = _pack_theme_entries(cfg, overlay, page_id)
  if theme_entries:
    for theme, path, status in theme_entries:
      rel = path.relative_to(overlay)
      lines.append(f"- `{rel}` (theme: {theme}, status: {status})")
  else:
    lines.append("(none)")

  mpp_dir = overlay / "mpp"
  csv_files = sorted(mpp_dir.glob("*__tasks.csv")) if mpp_dir.is_dir() else []
  if csv_files:
    lines.extend(["", "## MPP CSV"])
    for csv in csv_files:
      lines.append(f"- `{csv.relative_to(overlay)}`")

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

  pack_dir = overlay / "docs" / "_inbox" / task_id
  pack_dir.mkdir(parents=True, exist_ok=True)
  extracts_dir = pack_dir / "extracts"
  extracts_dir.mkdir(exist_ok=True)

  local_path = str(page.get("local_path") or "")
  l0_path = l0_abs(workvault, local_path) if local_path else None
  l0_body = l0_path.read_text(encoding="utf-8") if l0_path and l0_path.is_file() else None

  if l0_path and l0_path.is_file():
    extract_tables(l0_path, extracts_dir, resolved_page_id, task_id)

  if l0_body and l0_has_table(l0_body):
    csv_files = list(extracts_dir.glob("*.csv"))
    if not csv_files:
      raise ValidationError(
        f"L0 page {resolved_page_id} has table but no CSV extract in {extracts_dir} — "
        "run collect --extract-tables or fix table_extract"
      )

  pack_md = pack_dir / "PACK.md"
  pack_md.write_text(
    "\n".join(_pack_index_lines(task_id, resolved_page_id, page, overlay, cfg)) + "\n",
    encoding="utf-8",
  )

  theme_path_lines = [
    f"- theme `{theme}`: `{path.relative_to(overlay)}`"
    for theme, path, _ in _pack_theme_entries(cfg, overlay, resolved_page_id)
  ]
  pack_paths = "\n".join([
    f"- `{pack_md.relative_to(overlay)}`",
    f"- digest: `digest/leaves/{page.get('digest_slug', leaf_slug_page(resolved_page_id))}.md`",
    f"- L0: `{page.get('local_path', '')}`",
    *theme_path_lines,
  ])
  brief_md = pack_dir / "BRIEF.md"
  brief_md.write_text(_brief_skeleton(task_id, pack_paths), encoding="utf-8")

  digest_path = leaf_digest_path(overlay, resolved_page_id)
  if digest_path.exists():
    fm, _ = parse_digest(digest_path)
    if fm.get("status") == "rejected":
      raise ValidationError(f"digest {digest_path.name} is rejected — re-compress before pack")

  return pack_dir
