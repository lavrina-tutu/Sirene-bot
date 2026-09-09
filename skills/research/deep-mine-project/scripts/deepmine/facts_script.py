"""Script-only facts extraction (layer B)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .l0 import parse_l0_page
from .mpp_run import parse_l0_itogo
from .paths import l0_abs
from .project_config import ProjectConfig

_DATE_RE = re.compile(r"<time\s+datetime=[\"'](\d{4}-\d{2}-\d{2})")
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_JIRA_RE = re.compile(r"hq\.tutu\.ru/browse/([A-Z][A-Z0-9]+-\d+)", re.IGNORECASE)


def extract_dates(body: str, page_id: str) -> list[dict[str, Any]]:
  dates: list[dict[str, Any]] = []
  seen: set[str] = set()
  for match in _DATE_RE.finditer(body):
    val = match.group(1)
    if val not in seen:
      seen.add(val)
      dates.append({"value": val, "source_page_id": page_id, "label": "time datetime"})
  for match in _ISO_DATE_RE.finditer(body):
    val = match.group(1)
    if val not in seen:
      seen.add(val)
      dates.append({"value": val, "source_page_id": page_id, "label": "iso date"})
  return dates


def extract_jira(body: str, page_id: str) -> list[dict[str, Any]]:
  return [
    {"key": match.group(1).upper(), "source_page_id": page_id}
    for match in _JIRA_RE.finditer(body)
  ]


def extract_tables(
  cfg: ProjectConfig,
  overlay: Path,
  page_id: str,
) -> list[dict[str, Any]]:
  extracts_dir = overlay / "docs" / "_inbox"
  results: list[dict[str, Any]] = []
  if not extracts_dir.is_dir():
    return results
  for task_dir in extracts_dir.iterdir():
    if not task_dir.is_dir():
      continue
    csv_dir = task_dir / "extracts"
    if not csv_dir.is_dir():
      continue
    for csv in csv_dir.glob(f"*{page_id}*.csv"):
      results.append({
        "page_id": page_id,
        "csv_path": str(csv.relative_to(overlay)),
      })
  return results


def extract_sums(
  body: str,
  page_id: str,
  *,
  rate_rub_per_hour: int | None = None,
) -> list[dict[str, Any]]:
  sums: list[dict[str, Any]] = []
  try:
    totals = parse_l0_itogo(body)
  except Exception:
    return sums
  sums.append({
    "label": "effort_hours",
    "value": totals.effort_hours,
    "source_page_id": page_id,
  })
  if totals.duration_days is not None:
    sums.append({
      "label": "duration_days",
      "value": totals.duration_days,
      "source_page_id": page_id,
    })
  if rate_rub_per_hour:
    sums.append({
      "label": "cost_rub",
      "value": totals.effort_hours * rate_rub_per_hour,
      "source_page_id": page_id,
    })
  return sums


def page_meta_facts(page: dict[str, Any], page_id: str) -> list[dict[str, Any]]:
  meta: list[dict[str, Any]] = []
  if page.get("version"):
    meta.append({
      "label": "version",
      "value": str(page["version"]),
      "source_page_id": page_id,
    })
  if page.get("content_sha256"):
    meta.append({
      "label": "content_sha256",
      "value": str(page["content_sha256"]),
      "source_page_id": page_id,
    })
  return meta


def build_script_only(
  cfg: ProjectConfig,
  pages: dict[str, dict[str, Any]],
  overlay: Path,
  workvault: Path,
) -> dict[str, Any]:
  dates: list[dict[str, Any]] = []
  tables: list[dict[str, Any]] = []
  sums: list[dict[str, Any]] = []
  jira: list[dict[str, Any]] = []
  meta: list[dict[str, Any]] = []

  gantt_id = cfg.gantt_page_id
  for page_id, page in pages.items():
    meta.extend(page_meta_facts(page, page_id))
    local_rel = page.get("local_path")
    if not local_rel:
      continue
    l0 = l0_abs(workvault, local_rel)
    if not l0.exists():
      continue
    rec = parse_l0_page(l0, local_path=local_rel)
    dates.extend(extract_dates(rec.body, page_id))
    jira.extend(extract_jira(rec.body, page_id))
    tables.extend(extract_tables(cfg, overlay, page_id))
    if page_id == gantt_id or "Итого" in rec.body:
      sums.extend(extract_sums(rec.body, page_id, rate_rub_per_hour=cfg.rate_rub_per_hour))

  return {
    "dates": dates,
    "tables": tables,
    "sums": sums,
    "jira": jira,
    "meta": meta,
  }
