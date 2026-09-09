"""Refresh: poll Confluence version, stale tracking, diff, graph/facts/context."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .attachments import (
  download_attachment,
  expected_attachment_names,
  is_ole2_or_zip,
  list_whitelist,
)
from .confluence_pull import run_pull
from .cursor_jobs import write_diff
from .digest_io import mark_stale_manifest, utc_now_iso
from .fail import ValidationError, confluence_down
from .facts_run import run_facts
from .graph_build import run_graph
from .manifest import rebuild_all, save_manifest
from .meetings import index_meetings, write_meetings_pointer
from .models import Manifest
from .mpp_run import (
  PLAN_DIGEST_KEY,
  export_plan,
  find_gantt_json,
  find_plan_source,
  get_plan_digest,
  register_plan_in_manifest,
)
from .paths import CONFLUENCE_SYNC_CWD
from .project_config import ProjectConfig


@dataclass
class RefreshReport:
  checked: int = 0
  skipped: int = 0
  stale: list[str] = field(default_factory=list)
  diff_entries: list[dict[str, str]] = field(default_factory=list)
  dry_run: bool = False
  graph: bool = False
  facts: bool = False
  contexts: list[str] = field(default_factory=list)


def _client():
  if str(CONFLUENCE_SYNC_CWD) not in sys.path:
    sys.path.insert(0, str(CONFLUENCE_SYNC_CWD))
  from confluencesync.config import get_settings  # type: ignore
  from confluencesync.confluence_client import ConfluenceClient  # type: ignore

  settings = get_settings()
  return ConfluenceClient(settings.confluence_url, settings.confluence_token)


def poll_version(client: Any, page_id: str) -> int | None:
  try:
    page = client.get_page(page_id, expand="version")
    version = (page.get("version") or {}).get("number")
    return int(version) if version is not None else None
  except Exception:
    return None


def _meetings_changed(overlay: Path, cfg: ProjectConfig) -> bool:
  pointer = overlay / "pointers" / "meetings.md"
  old = pointer.read_text(encoding="utf-8") if pointer.exists() else ""
  rows = index_meetings(cfg.meeting_project_slugs)
  new_ids = sorted(r.meeting_id for r in rows)
  old_ids = sorted(line.split("|")[1].strip() for line in old.splitlines() if line.startswith("|") and "|" in line[1:])
  return new_ids != old_ids


def _assert_task_pages_in_manifest(cfg: ProjectConfig, manifest: Manifest) -> None:
  for entry in cfg.task_pages:
    page_id = str(entry.get("page_id") or "")
    if not page_id:
      continue
    if page_id not in manifest.pages:
      role = entry.get("role") or page_id
      raise ValidationError(
        f"task_pages role={role} page_id={page_id} not in MANIFEST — "
        "добавь в task_pages и collect"
      )


def _is_gantt_source(cfg: ProjectConfig) -> bool:
  return str(cfg.plan.get("source") or "").lower() == "gantt" and bool(cfg.gantt_page_id)


def _sync_gantt_attachments(cfg: ProjectConfig, manifest: Manifest, overlay: Path) -> None:
  """Download whitelist attachments from the Gantt page; merge, do not drop other files."""
  page_id = cfg.gantt_page_id
  if not page_id:
    return
  client = _client()
  if not client.ping():
    confluence_down("ping failed")
  expected = expected_attachment_names(cfg)
  dest = overlay / "attachments"
  now = utc_now_iso()
  downloaded: list[dict[str, Any]] = []
  for meta in list_whitelist(page_id, client, expected):
    local = download_attachment(meta, client, dest)
    data = local.read_bytes()
    downloaded.append(
      {
        "filename": meta.filename,
        "page_id": meta.page_id,
        "download_url": meta.download_url,
        "local_path": str(local.relative_to(overlay)),
        "sha256": hashlib.sha256(data).hexdigest(),
        "filesize": len(data),
        "format_hint": is_ole2_or_zip(local),
        "synced_at": now,
      }
    )
  if not downloaded:
    return
  names = {row["filename"] for row in downloaded}
  kept = [row for row in manifest.attachments if row.get("filename") not in names]
  manifest.attachments = kept + downloaded


def refresh_pages(
  cfg: ProjectConfig,
  manifest: Manifest,
  overlay: Path,
  workvault: Path,
  *,
  dry_run: bool = False,
  extract_tables: bool = False,
  skip_llm: bool = False,
) -> RefreshReport:
  report = RefreshReport(dry_run=dry_run)
  _assert_task_pages_in_manifest(cfg, manifest)
  client = _client()
  stale_slugs: list[str] = []
  stale_page_ids: set[str] = set()

  for page_id, page in manifest.pages.items():
    report.checked += 1
    local_v = int(page.get("version") or 0)
    remote_v = poll_version(client, page_id)
    if remote_v is None:
      page["digest_status"] = "missing_remote"
      slug = page.get("digest_slug") or f"p{page_id}"
      report.stale.append(slug)
      report.diff_entries.append({"slug": slug, "old": str(local_v), "new": "missing"})
      stale_page_ids.add(page_id)
      continue
    if remote_v == local_v:
      report.skipped += 1
      continue
    slug = page.get("digest_slug") or f"p{page_id}"
    report.stale.append(slug)
    report.diff_entries.append({"slug": slug, "old": str(local_v), "new": str(remote_v)})
    mark_stale_manifest(manifest, slug)
    stale_slugs.append(slug)
    stale_page_ids.add(page_id)
    if not dry_run:
      run_pull(page_id, recursive=False, resync=True)
      page["digest_status"] = "stale"

  if not dry_run:
    rebuild_all(
      overlay, workvault,
      slug=cfg.slug, root_page_id=cfg.root_page_id, pmo_seeds=cfg.pmo_seeds,
    )
    manifest = json.loads((overlay / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest_obj = Manifest(
      schema_version=manifest["schema_version"],
      slug=manifest["slug"],
      pages=manifest["pages"],
      attachments=manifest.get("attachments", []),
      digests=manifest.get("digests", {}),
      contexts=manifest.get("contexts", {}),
    )
    manifest = manifest_obj
    for slug in stale_slugs:
      mark_stale_manifest(manifest, slug)

  if _meetings_changed(overlay, cfg) and not dry_run:
    rows = index_meetings(cfg.meeting_project_slugs)
    write_meetings_pointer(overlay, rows)
    mark_stale_manifest(manifest, "m-index")
    if "m-index" not in report.stale:
      report.stale.append("m-index")

  att_dir = overlay / "attachments"
  old_sha_by_name = {a.get("filename"): a.get("sha256") for a in manifest.attachments}
  if _is_gantt_source(cfg) and not dry_run:
    _sync_gantt_attachments(cfg, manifest, overlay)

  plan_path = find_plan_source(
    att_dir,
    gantt_instance=cfg.gantt_instance,
    expected_name=str(cfg.plan.get("expected_name") or ""),
  )
  gantt_page_id = cfg.gantt_page_id
  gantt_page_stale = False
  if gantt_page_id and gantt_page_id in manifest.pages:
    gantt_slug = manifest.pages[gantt_page_id].get("digest_slug") or f"p{gantt_page_id}"
    gantt_page_stale = gantt_slug in report.stale

  if plan_path:
    new_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    old_sha = old_sha_by_name.get(plan_path.name)
    sha_changed = old_sha != new_sha
    switched_to_gantt = (
      _is_gantt_source(cfg)
      and plan_path.name.lower().startswith("gantt-chart-")
      and get_plan_digest(manifest).get("kind") != "gantt"
    )
    if (sha_changed or gantt_page_stale or switched_to_gantt) and not dry_run:
      csv = export_plan(
        plan_path,
        overlay / "mpp",
        rate_rub_per_hour=cfg.rate_rub_per_hour,
        workvault=workvault,
        gantt_page_id=cfg.gantt_page_id,
        manifest=manifest,
        project_title=str(cfg.plan.get("project_title") or cfg.display_name),
      )
      register_plan_in_manifest(manifest, csv, overlay)
      manifest.digests.setdefault(PLAN_DIGEST_KEY, get_plan_digest(manifest))
      manifest.digests[PLAN_DIGEST_KEY]["status"] = "stale"
      if PLAN_DIGEST_KEY not in report.stale:
        report.stale.append(PLAN_DIGEST_KEY)
    elif dry_run and (gantt_page_stale or switched_to_gantt or sha_changed):
      if PLAN_DIGEST_KEY not in report.stale:
        report.stale.append(PLAN_DIGEST_KEY)
  elif _is_gantt_source(cfg) or gantt_page_stale:
    if PLAN_DIGEST_KEY not in report.stale:
      report.stale.append(PLAN_DIGEST_KEY)

  if dry_run and _is_gantt_source(cfg) and find_gantt_json(att_dir, cfg.gantt_instance) is None:
    if PLAN_DIGEST_KEY not in report.stale:
      report.stale.append(PLAN_DIGEST_KEY)

  if report.diff_entries and not dry_run:
    write_diff(overlay, report.diff_entries)

  if not dry_run:
    save_manifest(manifest, overlay)

  if extract_tables and not dry_run:
    from .table_extract import extract_for_task_pages

    extract_for_task_pages(cfg, overlay, workvault, manifest)

  if stale_page_ids or report.stale:
    if not dry_run:
      run_graph(cfg, overlay, workvault)
      report.graph = True
      run_facts(
        cfg, overlay, workvault, manifest.pages,
        skip_llm=skip_llm,
        only_page_ids=stale_page_ids if stale_page_ids else None,
      )
      report.facts = True
      from .context_run import run_context

      for kind in ("charter", "architecture"):
        try:
          run_context(cfg, overlay, workvault, kind, skip_llm=skip_llm)
          report.contexts.append(kind)
        except Exception:
          pass

  return report
