"""Step C (CSV): Gantt-JSON parser with MppReader fallback."""
from __future__ import annotations

import csv
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fail import mpp_failed, plan_failed
from .paths import MPP_READER, VENV_PYTHON, l0_abs

PLAN_DIGEST_KEY = "plan"
LEGACY_PLAN_DIGEST_KEY = "mpp-plan"
GANTT_JSON_PREFIX = "gantt-chart-"
EFFORT_SOURCE_L0 = "l0-page-total"

# L0 «Итого» — канон трудозатрат/стоимости (не сумма листьев JSON).
_EFFORT_RE = re.compile(
  r"Трудозатраты:\s*([\d\s\xa0]+)\s*челове[кк]-час",
  re.IGNORECASE,
)
_ITOGO_RE = re.compile(
  r"Итого:\s*с\s*(\d{2}\.\d{2}\.\d{2})\s*по\s*(\d{2}\.\d{2}\.\d{2})\s*-\s*([\d\s\xa0]+)\s*рабочих\s+дн",
  re.IGNORECASE,
)
_CID_LINE_RE = re.compile(r"^confluence_id:\s*['\"]?(\d+)['\"]?\s*$", re.M)

TASK_FIELDS = [
  "id",
  "parent_id",
  "wbs",
  "outline_level",
  "name",
  "duration",
  "duration_unit",
  "start",
  "finish",
  "percent_complete",
  "milestone",
  "summary",
  "rollup",
  "effort",
  "effort_unit",
  "cost_rub",
  "constraint_type",
  "unscheduled",
  "predecessors",
]
RESOURCE_FIELDS = ["id", "name", "resource_type", "parent_id"]
ASSIGNMENT_FIELDS = ["id", "task_id", "resource_id", "resource_name", "units"]


@dataclass
class CsvTriple:
  tasks: Path | None
  resources: Path | None
  assignments: Path | None
  stem: str
  kind: str = "mpp"
  effort_hours: float = 0.0
  rate_rub_per_hour: float = 0.0
  cost_rub: float = 0.0
  duration_days: float = 0.0
  start_date: str = ""
  end_date: str = ""
  summary_path: Path | None = None
  effort_source: str = ""


def export_csv(mpp_path: Path, out_dir: Path) -> CsvTriple:
  out_dir.mkdir(parents=True, exist_ok=True)
  cmd = [
    str(VENV_PYTHON),
    str(MPP_READER),
    str(mpp_path),
    "--format",
    "both",
    "--out-dir",
    str(out_dir),
  ]
  proc = subprocess.run(cmd, capture_output=True, text=True)
  if proc.returncode != 0:
    mpp_failed(proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
  stem = mpp_path.stem
  tasks = out_dir / f"{stem}__tasks.csv"
  resources = out_dir / f"{stem}__resources.csv"
  assignments = out_dir / f"{stem}__assignments.csv"
  return CsvTriple(
    tasks=tasks if tasks.exists() else None,
    resources=resources if resources.exists() else None,
    assignments=assignments if assignments.exists() else None,
    stem=stem,
    kind="mpp",
  )


def is_gantt_json(path: Path) -> bool:
  if path.suffix.lower() != ".json":
    return False
  if path.name.lower().startswith(GANTT_JSON_PREFIX):
    return True
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return False
  return isinstance(data, dict) and "eventsData" in data


def _walk_events(
  nodes: list[dict[str, Any]],
  *,
  level: int = 1,
  wbs_prefix: str = "",
) -> list[dict[str, Any]]:
  rows: list[dict[str, Any]] = []
  for i, node in enumerate(nodes, start=1):
    wbs = str(i) if not wbs_prefix else f"{wbs_prefix}.{i}"
    children = list(node.get("children") or [])
    rollup = bool(node.get("rollup")) or bool(children)
    duration = node.get("duration") if node.get("duration") is not None else 0
    effort = node.get("effort") if node.get("effort") is not None else 0
    try:
      duration_f = float(duration)
    except (TypeError, ValueError):
      duration_f = 0.0
    rows.append(
      {
        "id": node.get("id"),
        "parent_id": node.get("parentId"),
        "wbs": wbs,
        "outline_level": level,
        "name": node.get("name") or "",
        "duration": duration,
        "duration_unit": node.get("durationUnit") or "day",
        "start": node.get("startDate") or "",
        "finish": node.get("endDate") or "",
        "percent_complete": node.get("percentDone") or 0,
        "milestone": (not rollup) and duration_f == 0,
        "summary": rollup,
        "rollup": rollup,
        "effort": effort,
        "effort_unit": node.get("effortUnit") or "hour",
        "constraint_type": node.get("constraintType") or "",
        "unscheduled": bool(node.get("unscheduled")),
        "predecessors": [],
      }
    )
    rows.extend(_walk_events(children, level=level + 1, wbs_prefix=wbs))
  return rows


def _digits(raw: str) -> str:
  return re.sub(r"\D", "", raw.replace("\xa0", " ").replace("&nbsp;", " "))


def _dmyy_to_iso(display: str) -> str:
  parts = display.strip().split(".")
  if len(parts) != 3:
    return display
  dd, mm, yy = parts
  year = int(yy)
  if year < 100:
    year += 2000
  return f"{year:04d}-{int(mm):02d}-{int(dd):02d}"


@dataclass
class ItogoTotals:
  effort_hours: float
  duration_days: float | None = None
  start_date: str = ""
  end_date: str = ""
  start_display: str = ""
  end_display: str = ""


def parse_l0_itogo(text: str) -> ItogoTotals:
  """Read effort (required) and period (optional) from L0 «Итого» block."""
  normalized = text.replace("\xa0", " ").replace("&nbsp;", " ")
  effort_match = _EFFORT_RE.search(normalized)
  if not effort_match:
    plan_failed(
      "L0 «Итого» has no «Трудозатраты: N человек-часа» "
      f"(pattern {_EFFORT_RE.pattern})"
    )
    raise AssertionError("unreachable")
  digits = _digits(effort_match.group(1))
  if not digits:
    plan_failed("L0 «Трудозатраты» matched but contained no digits")
    raise AssertionError("unreachable")
  effort_hours = float(digits)
  totals = ItogoTotals(effort_hours=effort_hours)
  itogo_match = _ITOGO_RE.search(normalized)
  if itogo_match:
    totals.start_display = itogo_match.group(1)
    totals.end_display = itogo_match.group(2)
    totals.start_date = _dmyy_to_iso(totals.start_display)
    totals.end_date = _dmyy_to_iso(totals.end_display)
    dur_digits = _digits(itogo_match.group(3))
    if dur_digits:
      totals.duration_days = float(dur_digits)
  return totals


def find_l0_by_page_id(workvault: Path, page_id: str) -> Path | None:
  if not page_id:
    return None
  root = workvault / "Confluence"
  if not root.is_dir():
    return None
  for path in root.rglob("index.md"):
    try:
      head = path.read_text(encoding="utf-8")[:1500]
    except OSError:
      continue
    match = _CID_LINE_RE.search(head)
    if match and match.group(1) == str(page_id):
      return path
  return None


def resolve_plan_l0_page(
  workvault: Path,
  *,
  gantt_page_id: str,
  manifest: Any | None = None,
) -> Path:
  """Locate L0 index.md for the Gantt page. Fail-loud if missing."""
  if not gantt_page_id:
    plan_failed("plan.gantt_page_id missing — cannot read L0 «Итого» for effort/cost")
  if manifest is not None:
    page = (getattr(manifest, "pages", None) or {}).get(gantt_page_id)
    if page:
      rel = page.get("local_path") or ""
      if rel:
        path = l0_abs(workvault, rel)
        if path.is_file():
          return path
  found = find_l0_by_page_id(workvault, gantt_page_id)
  if found:
    return found
  plan_failed(
    f"L0 page {gantt_page_id} not found under {workvault / 'Confluence'} — "
    "pull the Gantt page so «Итого»/Трудозатраты are on disk"
  )
  raise AssertionError("unreachable")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> Path:
  with path.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
      out = {}
      for key in fieldnames:
        val = row.get(key)
        if val is None:
          out[key] = ""
        elif isinstance(val, list):
          out[key] = json.dumps(val, ensure_ascii=False)
        elif isinstance(val, bool):
          out[key] = str(val)
        else:
          out[key] = val
      writer.writerow(out)
  return path


def gantt_to_csv(
  gantt_path: Path,
  out_dir: Path,
  *,
  rate_rub_per_hour: float = 3000,
  l0_page: Path | None = None,
) -> CsvTriple:
  """Parse gantt-chart-planner JSON → CSV; cost from L0 «Итого», not JSON sum."""
  out_dir.mkdir(parents=True, exist_ok=True)
  if l0_page is None:
    plan_failed("L0 page path required for Gantt cost (блок «Итого» / Трудозатраты)")
    raise AssertionError("unreachable")
  if not l0_page.is_file():
    plan_failed(f"L0 page not found: {l0_page}")
  try:
    l0_text = l0_page.read_text(encoding="utf-8")
  except OSError as exc:
    plan_failed(f"cannot read L0 page {l0_page}: {exc}")
    raise AssertionError("unreachable")
  totals = parse_l0_itogo(l0_text)

  try:
    data = json.loads(gantt_path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as exc:
    plan_failed(f"invalid Gantt JSON {gantt_path.name}: {exc}")
  if not isinstance(data, dict) or "eventsData" not in data:
    plan_failed(f"{gantt_path.name} has no eventsData")

  events = list(data.get("eventsData") or [])
  rows = _walk_events(events)
  preds_by_to: dict[Any, list[Any]] = {}
  for dep in data.get("dependenciesData") or []:
    if dep.get("active") is False:
      continue
    to_id = dep.get("to")
    from_id = dep.get("from")
    if to_id is None or from_id is None:
      continue
    preds_by_to.setdefault(to_id, []).append(from_id)
  for row in rows:
    row["predecessors"] = preds_by_to.get(row["id"], [])
    try:
      effort = float(row.get("effort") or 0)
    except (TypeError, ValueError):
      effort = 0.0
    if row.get("summary"):
      row["cost_rub"] = ""
    else:
      row["cost_rub"] = effort * rate_rub_per_hour

  res_rows = []
  res_by_id: dict[Any, str] = {}
  for res in data.get("resourcesData") or []:
    rid = res.get("id")
    name = res.get("name") or ""
    res_by_id[rid] = name
    res_rows.append(
      {
        "id": rid,
        "name": name,
        "resource_type": res.get("resourceType") or "",
        "parent_id": res.get("parentId"),
      }
    )

  asg_rows = []
  for asg in data.get("assignmentsData") or []:
    rid = asg.get("resource")
    asg_rows.append(
      {
        "id": asg.get("id"),
        "task_id": asg.get("event"),
        "resource_id": rid,
        "resource_name": res_by_id.get(rid, ""),
        "units": asg.get("units"),
      }
    )

  stem = gantt_path.stem
  tasks_path = _write_csv(out_dir / f"{stem}__tasks.csv", TASK_FIELDS, rows)
  resources_path = _write_csv(out_dir / f"{stem}__resources.csv", RESOURCE_FIELDS, res_rows)
  assignments_path = _write_csv(
    out_dir / f"{stem}__assignments.csv", ASSIGNMENT_FIELDS, asg_rows
  )

  root = events[0] if events else {}
  effort_hours = totals.effort_hours
  cost_rub = effort_hours * rate_rub_per_hour
  try:
    json_duration = float(root.get("duration") or 0)
  except (TypeError, ValueError):
    json_duration = 0.0
  duration_days = (
    totals.duration_days if totals.duration_days is not None else json_duration
  )
  start_date = totals.start_date or str(root.get("startDate") or data.get("startDate") or "")
  end_date = totals.end_date or str(root.get("endDate") or "")
  summary = {
    "source": "gantt",
    "gantt_file": gantt_path.name,
    "start_date": start_date,
    "end_date": end_date,
    "duration_days": duration_days,
    "effort_hours": effort_hours,
    "effort_hours_ceil": int(effort_hours) if float(effort_hours).is_integer() else effort_hours,
    "rate_rub_per_hour": rate_rub_per_hour,
    "cost_rub": cost_rub,
    "effort_source": EFFORT_SOURCE_L0,
    "l0_page": str(l0_page),
    "task_count": len(rows),
    "resource_count": len(res_rows),
    "assignment_count": len(asg_rows),
  }
  if totals.start_display:
    summary["start_date_display"] = totals.start_display
    summary["end_date_display"] = totals.end_display
  summary_path = out_dir / f"{stem}__summary.json"
  summary_path.write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return CsvTriple(
    tasks=tasks_path,
    resources=resources_path,
    assignments=assignments_path,
    stem=stem,
    kind="gantt",
    effort_hours=effort_hours,
    rate_rub_per_hour=float(rate_rub_per_hour),
    cost_rub=cost_rub,
    duration_days=float(duration_days or 0),
    start_date=start_date,
    end_date=end_date,
    summary_path=summary_path,
    effort_source=EFFORT_SOURCE_L0,
  )


def export_plan(
  path: Path,
  out_dir: Path,
  *,
  rate_rub_per_hour: float = 3000,
  l0_page: Path | None = None,
  workvault: Path | None = None,
  gantt_page_id: str = "",
  manifest: Any | None = None,
) -> CsvTriple:
  """Gantt JSON → CSV; fallback to MppReader for .mpp/.mpx/.xml."""
  if is_gantt_json(path) or path.suffix.lower() == ".json":
    if l0_page is None:
      if workvault is None:
        plan_failed("L0 page path required for Gantt cost (блок «Итого» / Трудозатраты)")
      l0_page = resolve_plan_l0_page(
        workvault, gantt_page_id=gantt_page_id, manifest=manifest
      )
    return gantt_to_csv(
      path, out_dir, rate_rub_per_hour=rate_rub_per_hour, l0_page=l0_page
    )
  return export_csv(path, out_dir)


def find_gantt_json(attachments_dir: Path, instance: str = "") -> Path | None:
  if not attachments_dir.is_dir():
    return None
  if instance:
    exact = attachments_dir / f"{GANTT_JSON_PREFIX}{instance}.json"
    if exact.is_file():
      return exact
  matches = sorted(
    p for p in attachments_dir.glob(f"{GANTT_JSON_PREFIX}*.json") if p.is_file()
  )
  return matches[0] if matches else None


def find_mpp_attachment(attachments_dir: Path, expected_name: str) -> Path | None:
  if not attachments_dir.is_dir():
    return None
  for path in attachments_dir.iterdir():
    if expected_name and expected_name.lower() in path.name.lower():
      if path.suffix.lower() == ".json" and not path.name.lower().startswith(GANTT_JSON_PREFIX):
        continue
      return path
  for ext in (".mpp", ".mpx", ".xml", ".zip"):
    matches = list(attachments_dir.glob(f"*{ext}"))
    if matches:
      return matches[0]
  return None


def find_plan_source(
  attachments_dir: Path,
  *,
  gantt_instance: str = "",
  expected_name: str = "",
) -> Path | None:
  """Prefer gantt-chart-*.json over MPP."""
  gantt = find_gantt_json(attachments_dir, gantt_instance)
  if gantt:
    return gantt
  return find_mpp_attachment(attachments_dir, expected_name)


def register_local_mpp(
  manifest,
  mpp_path: Path,
  overlay: Path,
  *,
  page_id: str = "local",
) -> None:
  import hashlib
  from datetime import datetime, timezone

  data = mpp_path.read_bytes()
  now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  record = {
    "filename": mpp_path.name,
    "page_id": page_id,
    "download_url": f"file://{mpp_path}",
    "local_path": str(mpp_path.relative_to(overlay)),
    "sha256": hashlib.sha256(data).hexdigest(),
    "filesize": len(data),
    "format_hint": "json" if mpp_path.suffix.lower() == ".json" else "ole2",
    "synced_at": now,
    "source": "local_attachment",
  }
  manifest.attachments = [r for r in manifest.attachments if r.get("filename") != mpp_path.name]
  manifest.attachments.append(record)


def get_plan_digest(manifest) -> dict[str, Any]:
  """Read ``digests['plan']``, falling back to legacy ``mpp-plan``."""
  digests = manifest.digests or {}
  if PLAN_DIGEST_KEY in digests:
    return digests[PLAN_DIGEST_KEY]
  return dict(digests.get(LEGACY_PLAN_DIGEST_KEY) or {})


def register_plan_in_manifest(manifest, csv: CsvTriple, overlay: Path) -> None:
  entry = get_plan_digest(manifest)
  entry.update(
    {
      "kind": csv.kind,
      "csv_tasks": str(csv.tasks.relative_to(overlay)) if csv.tasks else None,
      "csv_resources": str(csv.resources.relative_to(overlay)) if csv.resources else None,
      "csv_assignments": str(csv.assignments.relative_to(overlay)) if csv.assignments else None,
      "plan_path": "mpp/plan.md",
      "status": "pending_compress",
      "effort_hours": csv.effort_hours,
      "rate_rub_per_hour": csv.rate_rub_per_hour,
      "cost_rub": csv.cost_rub,
      "duration_days": csv.duration_days,
      "start_date": csv.start_date,
      "end_date": csv.end_date,
      "effort_source": csv.effort_source,
    }
  )
  if csv.summary_path and csv.summary_path.exists():
    entry["summary_path"] = str(csv.summary_path.relative_to(overlay))
  manifest.digests[PLAN_DIGEST_KEY] = entry


def register_mpp_in_manifest(manifest, csv: CsvTriple, overlay: Path) -> None:
  """Backward-compat wrapper — writes ``digests['plan']``."""
  register_plan_in_manifest(manifest, csv, overlay)
