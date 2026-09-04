"""CLI commands for deep-mine-project."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .attachments import sync_attachments
from .confluence_pull import pull_seed_tree
from .entity import write_entity_pointer
from .fail import DeepMineError, ValidationError, exit_from_error
from .manifest import load_manifest, rebuild_all
from .meetings import index_meetings, write_meetings_pointer
from .mpp_run import export_csv, find_mpp_attachment, register_mpp_in_manifest
from .paths import ensure_overlay_dirs, overlay_dir, workvault_root
from .project_config import (
  default_trisigma_yaml,
  load_project_config,
  project_yaml_path,
)


def _add_common(sp: argparse.ArgumentParser) -> None:
  sp.add_argument("--slug", required=True, help="Project overlay slug, e.g. TrisigmaFull")
  sp.add_argument("--workvault", default=None, help="WorkVault root (default ~/WorkVault)")
  sp.add_argument("--dry-run", action="store_true", help="Report only, no writes")
  sp.add_argument("--json", dest="json_out", action="store_true", help="Machine-readable summary")


def cmd_init(args: argparse.Namespace) -> int:
  wv = workvault_root(args.workvault)
  overlay = overlay_dir(wv, args.slug)
  overlay.mkdir(parents=True, exist_ok=True)
  ensure_overlay_dirs(overlay)
  yaml_path = project_yaml_path(wv, args.slug)
  if not yaml_path.exists():
    if args.slug == "TrisigmaFull":
      yaml_path.write_text(default_trisigma_yaml(), encoding="utf-8")
    else:
      print(f"Create PROJECT.yaml manually: {yaml_path}", file=sys.stderr)
      return 2
  result = {"overlay": str(overlay), "project_yaml": str(yaml_path)}
  if args.json_out:
    print(json.dumps(result, ensure_ascii=False))
  else:
    print(f"init ok: {overlay}")
  return 0


def cmd_collect(args: argparse.Namespace) -> int:
  wv = workvault_root(args.workvault)
  cfg = load_project_config(args.slug, workvault=wv)
  overlay = overlay_dir(wv, args.slug)
  ensure_overlay_dirs(overlay)
  summary: dict = {"slug": args.slug, "steps": []}

  if not args.skip_a:
    pull_seed_tree(cfg)
    summary["steps"].append("A:confluence_pull")

  manifest = None
  if not args.skip_b:
    if manifest is None:
      manifest = rebuild_all(
        overlay, wv, slug=cfg.slug,
        root_page_id=cfg.root_page_id, pmo_seeds=cfg.pmo_seeds,
      )
    att = sync_attachments(cfg, manifest, overlay)
    summary["steps"].append(f"B:attachments:{att['downloaded']}")

  if not args.skip_c:
    mpp_path = find_mpp_attachment(overlay / "attachments", cfg.mpp.get("expected_name", ""))
    if mpp_path:
      csv = export_csv(mpp_path, overlay / "mpp")
      if manifest is None:
        manifest = load_manifest(overlay, slug=cfg.slug)
      register_mpp_in_manifest(manifest, csv, overlay)
      summary["steps"].append("C:mpp_csv")
    else:
      summary["steps"].append("C:mpp_csv:skipped_no_file")

  if not args.skip_d:
    rows = index_meetings(cfg.meeting_project_slugs)
    write_meetings_pointer(overlay, rows)
    summary["steps"].append(f"D:meetings:{len(rows)}")

  if not args.skip_entity:
    write_entity_pointer(wv, overlay, cfg.entity_slug)
    summary["steps"].append("entity:pointer")

  if not args.skip_e:
    manifest = rebuild_all(
      overlay, wv, slug=cfg.slug,
      root_page_id=cfg.root_page_id, pmo_seeds=cfg.pmo_seeds,
    )
    summary["steps"].append(f"E:manifest:{len(manifest.pages)}")
  elif manifest is not None:
    from .manifest import Manifest as M
    import json as _json
    (overlay / "MANIFEST.json").write_text(
      _json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
      encoding="utf-8",
    )

  if getattr(args, "extract_tables", False):
    from .table_extract import extract_for_task_pages

    manifest = load_manifest(overlay, slug=cfg.slug)
    written = extract_for_task_pages(cfg, overlay, wv, manifest)
    summary["steps"].append(f"extract_tables:{len(written)}")

  if args.json_out:
    print(json.dumps(summary, ensure_ascii=False))
  else:
    print("collect ok:", ", ".join(summary["steps"]))
  return 0


def cmd_refresh(args: argparse.Namespace) -> int:
  from .refresh import refresh_pages

  wv = workvault_root(args.workvault)
  cfg = load_project_config(args.slug, workvault=wv)
  overlay = overlay_dir(wv, args.slug)
  manifest = load_manifest(overlay, slug=cfg.slug)
  report = refresh_pages(
    cfg, manifest, overlay, wv,
    dry_run=args.dry_run,
    extract_tables=getattr(args, "extract_tables", False),
  )
  out = {
    "checked": report.checked,
    "skipped": report.skipped,
    "stale": report.stale,
    "dry_run": report.dry_run,
  }
  if args.json_out:
    print(json.dumps(out, ensure_ascii=False))
  else:
    print(f"refresh: checked={report.checked} stale={len(report.stale)}")
  return 0


def cmd_digest(args: argparse.Namespace) -> int:
  from .digest_run import run_digest

  wv = workvault_root(args.workvault)
  cfg = load_project_config(args.slug, workvault=wv)
  overlay = overlay_dir(wv, args.slug)
  result = run_digest(
    cfg, overlay, wv,
    only=args.only,
    all_stale=args.all_stale,
    plan_only=args.plan_only,
    dry_run=args.dry_run,
  )
  if args.json_out:
    print(json.dumps(result, ensure_ascii=False))
  else:
    print(f"digest ok: {len(result.get('compressed', []))} leaves")
  return 0


def cmd_mine(args: argparse.Namespace) -> int:
  rc = cmd_collect(args)
  if rc != 0:
    return rc
  digest_args = argparse.Namespace(**vars(args))
  digest_args.plan_only = False
  digest_args.only = None
  digest_args.all_stale = False
  return cmd_digest(digest_args)


def cmd_pack(args: argparse.Namespace) -> int:
  from .pack import run_pack

  wv = workvault_root(args.workvault)
  cfg = load_project_config(args.slug, workvault=wv)
  overlay = overlay_dir(wv, args.slug)
  pack_dir = run_pack(
    cfg, overlay, wv, args.task,
    page_id=getattr(args, "page_id", None),
  )
  result = {"pack_dir": str(pack_dir), "task": args.task}
  if args.json_out:
    print(json.dumps(result, ensure_ascii=False))
  else:
    print(f"pack ok: {pack_dir}")
  return 0


def cmd_analyze(args: argparse.Namespace) -> int:
  from .cursor_jobs import analyze
  from .pack import resolve_task_page_id
  from .source import list_unready_pages, require_fresh_digest

  wv = workvault_root(args.workvault)
  cfg = load_project_config(args.slug, workvault=wv)
  overlay = overlay_dir(wv, args.slug)
  task = getattr(args, "task", None)
  full_archive = getattr(args, "full_archive", False)
  allow_stale = getattr(args, "allow_stale", False)

  if bool(task) == bool(full_archive):
    raise ValidationError("нужен --task или --full-archive (исключающе)")

  manifest = load_manifest(overlay, slug=cfg.slug)
  pack_dir = None

  if full_archive:
    unready = list_unready_pages(overlay, manifest)
    if allow_stale:
      unready = [p for p in unready if p["status"] != "stale"]
    if unready:
      lines = [f"  - {p['page_id']} ({p['status']}): {p['digest_path']}" for p in unready]
      raise ValidationError(
        "digest archive not ready for full-archive analyze:\n" + "\n".join(lines)
      )
  else:
    page_id = resolve_task_page_id(cfg, task, page_id=getattr(args, "page_id", None))
    page = manifest.pages.get(page_id)
    require_fresh_digest(
      overlay,
      page_id,
      allow_stale=allow_stale,
      manifest_page=page,
      slug=cfg.slug,
      task_hint=task,
    )
    pack_dir = overlay / "docs" / "_inbox" / task

  result = analyze(
    overlay,
    cfg,
    pack_dir=pack_dir,
    full_archive=full_archive,
    dry_run=args.dry_run,
  )
  if args.dry_run:
    print(result)
    return 0
  if args.json_out:
    print(json.dumps({"returncode": result.returncode, "model": result.model}))
  else:
    print(f"analyze: exit={result.returncode}")
  return 0 if result.returncode == 0 else 1


def cmd_document(args: argparse.Namespace) -> int:
  from .cursor_jobs import document, document_preflight

  wv = workvault_root(args.workvault)
  cfg = load_project_config(args.slug, workvault=wv)
  overlay = overlay_dir(wv, args.slug)
  manifest = load_manifest(overlay, slug=cfg.slug)
  document_preflight(overlay, cfg, manifest)
  result = document(overlay, cfg, dry_run=args.dry_run)
  if args.dry_run:
    print(result)
    return 0
  if args.json_out:
    print(json.dumps({"returncode": result.returncode, "model": result.model}))
  else:
    print(f"document: exit={result.returncode}")
  return 0 if result.returncode == 0 else 1


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog="deep_mine", description="deep-mine-project CLI")
  sub = parser.add_subparsers(dest="command", required=True)

  p_init = sub.add_parser("init", help="Create overlay skeleton + PROJECT.yaml")
  _add_common(p_init)

  p_collect = sub.add_parser("collect", help="Run pipeline A→B→C→D→E")
  _add_common(p_collect)
  p_collect.add_argument("--skip-a", action="store_true")
  p_collect.add_argument("--skip-b", action="store_true")
  p_collect.add_argument("--skip-c", action="store_true")
  p_collect.add_argument("--skip-d", action="store_true")
  p_collect.add_argument("--skip-e", action="store_true")
  p_collect.add_argument("--skip-entity", action="store_true")
  p_collect.add_argument(
    "--extract-tables",
    action="store_true",
    help="Extract L0 tables to docs/_inbox/<role>/extracts/ for task_pages",
  )

  p_refresh = sub.add_parser("refresh", help="Incremental refresh")
  _add_common(p_refresh)
  p_refresh.add_argument(
    "--extract-tables",
    action="store_true",
    help="Extract L0 tables for task_pages after refresh",
  )

  for name, handler in (
    ("digest", cmd_digest),
    ("mine", cmd_mine),
    ("analyze", cmd_analyze),
    ("document", cmd_document),
  ):
    p = sub.add_parser(name)
    _add_common(p)
    if name == "digest":
      p.add_argument("--only", default=None)
      p.add_argument("--all-stale", action="store_true")
      p.add_argument("--plan-only", action="store_true")
    if name == "analyze":
      p.add_argument("--task", default=None, help="Task id for pack-based analyze (G)")
      p.add_argument(
        "--full-archive",
        action="store_true",
        help="Analyze full digest archive (all pages must have fresh digest)",
      )
      p.add_argument(
        "--allow-stale",
        action="store_true",
        help="Allow stale digests (analyze only, read-only)",
      )

  p_pack = sub.add_parser("pack", help="Build task pack for architect (PACK.md + BRIEF.md)")
  _add_common(p_pack)
  p_pack.add_argument("--task", required=True, help="Task id from PROJECT.yaml")
  p_pack.add_argument("--page-id", default=None, help="Override page id")

  return parser


def main(argv: list[str] | None = None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)
  handlers = {
    "init": cmd_init,
    "collect": cmd_collect,
    "refresh": cmd_refresh,
    "digest": cmd_digest,
    "mine": cmd_mine,
    "pack": cmd_pack,
    "analyze": cmd_analyze,
    "document": cmd_document,
  }
  try:
    return handlers[args.command](args)
  except DeepMineError as exc:
    return exit_from_error(exc)


if __name__ == "__main__":
  raise SystemExit(main())
